"""Production Medical Terminology Service.

This module provides real-time validation and lookup of medical codes
against standard terminologies including SNOMED CT, LOINC, ICD-10, RxNorm, etc.
Includes validator functionality for FHIR Resource terminology compliance.
"""

import asyncio
import json
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import aiohttp
import redis.asyncio as redis

# Access control for medical terminology lookups is handled by API middleware
# from src.healthcare.hipaa_access_control import require_phi_access  # Available if needed for HIPAA compliance
from src.security.encryption import EncryptionService
from src.utils.logging import get_logger

logger = get_logger(__name__)


class TerminologySystem(Enum):
    """Supported medical terminology systems."""

    SNOMED_CT = "http://snomed.info/sct"
    LOINC = "http://loinc.org"
    ICD10 = "http://hl7.org/fhir/sid/icd-10"
    ICD10CM = "http://hl7.org/fhir/sid/icd-10-cm"
    ICD11 = "http://id.who.int/icd11/mms"
    RXNORM = "http://www.nlm.nih.gov/research/umls/rxnorm"
    CPT = "http://www.ama-assn.org/go/cpt"
    HCPCS = "http://www.cms.gov/Medicare/Coding/HCPCSReleaseCodeSets"
    NDC = "http://hl7.org/fhir/sid/ndc"
    UNII = "http://fdasis.nlm.nih.gov"
    UCUM = "http://unitsofmeasure.org"
    CVX = "http://hl7.org/fhir/sid/cvx"
    MESH = "http://id.nlm.nih.gov/mesh"
    ATC = "http://www.whocc.no/atc"


@dataclass
class CodeValidationResult:
    """Result of code validation."""

    valid: bool
    system: str
    code: str
    display: Optional[str]
    version: Optional[str]
    active: bool
    preferred_term: Optional[str]
    synonyms: List[str]
    parent_codes: List[str]
    child_codes: List[str]
    properties: Dict[str, Any]
    cross_mappings: Dict[str, List[str]]  # System -> codes
    validation_time: float


@dataclass
class ConceptRelationship:
    """Relationship between medical concepts."""

    source_system: str
    source_code: str
    target_system: str
    target_code: str
    relationship_type: str  # is-a, part-of, same-as, etc.
    strength: float  # 0-1 confidence


class TerminologyService:
    """Production terminology service for medical code validation."""

    # HIPAA: Access control required for terminology service access

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize terminology service with configuration."""
        self.config = config or self._get_default_config()
        self.encryption_service = EncryptionService(
            kms_key_id="alias/haven-health-terminology"
        )

        # API clients for terminology servers
        self.api_clients: Dict[str, Any] = {}
        self.session: Optional[aiohttp.ClientSession] = None

        # Redis cache for performance
        self.redis_client: Optional[redis.Redis] = None
        self.cache_ttl = 3600 * 24  # 24 hours

        # Local terminology data
        self.local_terminologies: Dict[str, Any] = {}
        self._load_local_terminologies()

        # Initialize connections - defer to avoid event loop issues during import
        self._initialized = False

    def _get_default_config(self) -> Dict[str, Any]:
        """Get default terminology service configuration."""
        return {
            "umls_api_key": "YOUR_UMLS_API_KEY",  # Set via environment
            "fhir_terminology_server": "https://r4.ontoserver.csiro.au/fhir",
            "tx_server_timeout": 30,
            "cache_enabled": True,
            "redis_url": "redis://localhost:6379/1",
            "local_terminology_path": "/opt/haven/terminologies",
            "enable_cross_mapping": True,
            "validation_strictness": "strict",  # strict, moderate, lenient
            "supported_languages": ["en", "es", "fr", "ar", "zh", "hi", "pt", "ru"],
        }

    async def _initialize_connections(self) -> None:
        """Initialize connections to terminology services."""
        try:
            # Initialize HTTP session
            self.session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.config["tx_server_timeout"])
            )

            # Initialize Redis cache
            if self.config["cache_enabled"]:
                self.redis_client = await redis.from_url(
                    self.config["redis_url"], decode_responses=True
                )
                await self.redis_client.ping()
                logger.info("Connected to Redis cache")

            # Test terminology server connection
            await self._test_terminology_server()

            logger.info("Terminology service initialized successfully")

        except (aiohttp.ClientError, redis.RedisError, OSError) as e:
            logger.error(f"Failed to initialize terminology service: {e}")

    def _load_local_terminologies(self) -> None:
        """Load local terminology files for offline support."""
        terminology_path = Path(self.config["local_terminology_path"])

        if terminology_path.exists():
            # Load essential code sets
            essential_files = {
                "icd10_codes.json": TerminologySystem.ICD10,
                "loinc_common.json": TerminologySystem.LOINC,
                "rxnorm_common.json": TerminologySystem.RXNORM,
                "cvx_vaccines.json": TerminologySystem.CVX,
            }

            for filename, system in essential_files.items():
                file_path = terminology_path / filename
                if file_path.exists():
                    try:
                        with open(file_path, "r", encoding="utf-8") as f:
                            self.local_terminologies[system.value] = json.load(f)
                        logger.info(f"Loaded local terminology: {filename}")
                    except (IOError, json.JSONDecodeError) as e:
                        logger.error(f"Failed to load {filename}: {e}")

    async def _ensure_initialized(self) -> None:
        """Ensure the service is initialized."""
        if not self._initialized:
            await self._initialize_connections()
            self._initialized = True

    async def validate_code(
        self,
        system: str,
        code: str,
        version: Optional[str] = None,
        display: Optional[str] = None,
        language: str = "en",
    ) -> CodeValidationResult:
        # HIPAA: Authorize access to code validation
        """
        Validate a medical code against its terminology system.

        Args:
            system: Terminology system URI
            code: Code to validate
            version: Optional version of terminology
            display: Optional display text to validate
            language: Language for display terms

        Returns:
            CodeValidationResult with validation details
        """
        await self._ensure_initialized()
        start_time = time.time()

        # Check cache first
        cache_key = f"code:{system}:{code}:{version}:{language}"
        if self.redis_client is not None:
            cached = await self.redis_client.get(cache_key)
            if cached:
                result = json.loads(cached)
                result["validation_time"] = time.time() - start_time
                result["from_cache"] = True
                return CodeValidationResult(**result)

        # Try local terminology first (for offline support)
        local_result = self._validate_local(system, code, version, display, language)
        if local_result:
            local_result.validation_time = time.time() - start_time
            await self._cache_result(cache_key, local_result)
            return local_result

        # Validate against terminology server
        try:
            result = await self._validate_remote(
                system, code, version, display, language
            )
            result.validation_time = time.time() - start_time

            # Cache result
            await self._cache_result(cache_key, result)

            return result

        except (aiohttp.ClientError, RuntimeError, OSError) as e:
            logger.error(f"Code validation failed for {system}:{code} - {e}")

            # Return basic validation result
            return CodeValidationResult(
                valid=False,
                system=system,
                code=code,
                display=display,
                version=version,
                active=False,
                preferred_term=None,
                synonyms=[],
                parent_codes=[],
                child_codes=[],
                properties={},
                cross_mappings={},
                validation_time=time.time() - start_time,
            )

    def _validate_local(
        self,
        system: str,
        code: str,
        version: Optional[str],
        display: Optional[str],
        language: str,
    ) -> Optional[CodeValidationResult]:
        """Validate against local terminology data."""
        _ = display  # Unused parameter
        if system not in self.local_terminologies:
            return None

        terminology = self.local_terminologies[system]
        code_data = terminology.get("codes", {}).get(code)

        if not code_data:
            return None

        # Build result from local data
        return CodeValidationResult(
            valid=True,
            system=system,
            code=code,
            display=code_data.get("display", {}).get(
                language, code_data.get("display", {}).get("en")
            ),
            version=version or terminology.get("version"),
            active=code_data.get("active", True),
            preferred_term=code_data.get("preferred_term"),
            synonyms=code_data.get("synonyms", []),
            parent_codes=code_data.get("parents", []),
            child_codes=code_data.get("children", []),
            properties=code_data.get("properties", {}),
            cross_mappings=code_data.get("mappings", {}),
            validation_time=0,
        )

    async def _validate_remote(
        self,
        system: str,
        code: str,
        version: Optional[str],
        display: Optional[str],
        language: str,
    ) -> CodeValidationResult:
        """Validate against remote terminology server."""
        # Use FHIR $validate-code operation
        url = f"{self.config['fhir_terminology_server']}/CodeSystem/$validate-code"

        params = {
            "system": system,
            "code": code,
            "display": display,
            "displayLanguage": language,
        }

        if version:
            params["version"] = version

        # Filter out None values from params
        filtered_params = {k: v for k, v in params.items() if v is not None}

        if self.session is None:
            raise RuntimeError("Session not initialized")
        async with self.session.get(url, params=filtered_params) as response:
            if response.status == 200:
                data = await response.json()

                # Parse FHIR Parameters response
                result_params = {
                    p["name"]: p.get("valueBoolean", p.get("valueString"))
                    for p in data.get("parameter", [])
                }

                # Get additional concept details
                concept_details = await self._get_concept_details(
                    system, code, language
                )

                return CodeValidationResult(
                    valid=result_params.get("result", False),
                    system=system,
                    code=code,
                    display=result_params.get("display", display),
                    version=version,
                    active=concept_details.get("active", True),
                    preferred_term=concept_details.get("preferred_term"),
                    synonyms=concept_details.get("synonyms", []),
                    parent_codes=concept_details.get("parents", []),
                    child_codes=concept_details.get("children", []),
                    properties=concept_details.get("properties", {}),
                    cross_mappings=await self._get_cross_mappings(system, code),
                    validation_time=0,
                )
            else:
                raise RuntimeError(f"Terminology server returned {response.status}")

    async def _get_concept_details(
        self, system: str, code: str, language: str
    ) -> Dict[str, Any]:
        """Get detailed concept information."""
        # Would query terminology server for full concept details
        # Simplified implementation
        _ = (system, code, language)  # Unused parameters - placeholder implementation
        return {
            "active": True,
            "preferred_term": code,
            "synonyms": [],
            "parents": [],
            "children": [],
            "properties": {},
        }

    async def _get_cross_mappings(self, system: str, code: str) -> Dict[str, List[str]]:
        """Get cross-mappings to other terminology systems."""
        if not self.config["enable_cross_mapping"]:
            return {}

        _ = (system, code)  # Unused parameters - placeholder implementation
        mappings: Dict[str, List[str]] = {}

        # Common cross-mappings
        # TODO: Implement cross-terminology mapping functionality
        # mapping_targets = {
        #     TerminologySystem.ICD10: [
        #         TerminologySystem.ICD11,
        #         TerminologySystem.SNOMED_CT,
        #     ],
        #     TerminologySystem.RXNORM: [TerminologySystem.ATC, TerminologySystem.NDC],
        #     TerminologySystem.LOINC: [TerminologySystem.SNOMED_CT],
        # }

        # Would query mapping services
        # Simplified for now
        return mappings

    async def _cache_result(self, key: str, result: CodeValidationResult) -> None:
        """Cache validation result."""
        if self.redis_client is not None:
            try:
                # Convert to dict and remove non-serializable fields
                result_dict = {
                    "valid": result.valid,
                    "system": result.system,
                    "code": result.code,
                    "display": result.display,
                    "version": result.version,
                    "active": result.active,
                    "preferred_term": result.preferred_term,
                    "synonyms": result.synonyms,
                    "parent_codes": result.parent_codes,
                    "child_codes": result.child_codes,
                    "properties": result.properties,
                    "cross_mappings": result.cross_mappings,
                }

                await self.redis_client.setex(
                    key, self.cache_ttl, json.dumps(result_dict)
                )
            except (redis.RedisError, json.JSONDecodeError) as e:
                logger.error(f"Failed to cache result: {e}")

    async def _test_terminology_server(self) -> None:
        """Test connection to terminology server."""
        try:
            url = f"{self.config['fhir_terminology_server']}/metadata"
            if self.session is None:
                raise RuntimeError("Session not initialized")
            async with self.session.get(url) as response:
                if response.status == 200:
                    logger.info("Successfully connected to terminology server")
                else:
                    logger.warning(f"Terminology server returned {response.status}")
        except (aiohttp.ClientError, RuntimeError, OSError) as e:
            logger.error(f"Failed to connect to terminology server: {e}")

    async def validate_batch(
        self,
        codes: List[Tuple[str, str]],  # List of (system, code) tuples
        language: str = "en",
    ) -> List[CodeValidationResult]:
        """Validate multiple codes in batch for performance."""
        # Validate concurrently
        tasks = [
            self.validate_code(system, code, language=language)
            for system, code in codes
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Handle exceptions
        validated_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Batch validation error for {codes[i]}: {result}")
                # Create failed result
                validated_results.append(
                    CodeValidationResult(
                        valid=False,
                        system=codes[i][0],
                        code=codes[i][1],
                        display=None,
                        version=None,
                        active=False,
                        preferred_term=None,
                        synonyms=[],
                        parent_codes=[],
                        child_codes=[],
                        properties={},
                        cross_mappings={},
                        validation_time=0,
                    )
                )
            elif isinstance(result, CodeValidationResult):
                validated_results.append(result)

        return validated_results

    async def search_concepts(
        self,
        text: str,
        systems: Optional[List[str]] = None,
        limit: int = 10,
        language: str = "en",
    ) -> List[Dict[str, Any]]:
        """Search for medical concepts across terminology systems."""
        # HIPAA: Permission required for concept search
        results = []

        # Default to common systems if not specified
        if not systems:
            systems = [
                TerminologySystem.SNOMED_CT.value,
                TerminologySystem.ICD10.value,
                TerminologySystem.LOINC.value,
            ]

        # Search each system
        for system in systems:
            system_results = await self._search_system(system, text, limit, language)
            results.extend(system_results)

        # Sort by relevance score
        results.sort(key=lambda x: x.get("score", 0), reverse=True)

        return results[:limit]

    async def _search_system(
        self, system: str, text: str, limit: int, language: str
    ) -> List[Dict[str, Any]]:
        """Search within a specific terminology system."""
        # Would implement full-text search against terminology server
        # Simplified for now
        _ = (
            system,
            text,
            limit,
            language,
        )  # Unused parameters - placeholder implementation
        return []

    async def get_concept_relationships(
        self, system: str, code: str, relationship_types: Optional[List[str]] = None
    ) -> List[ConceptRelationship]:
        """Get relationships for a medical concept."""
        _ = (system, code)  # Unused parameters - placeholder implementation
        relationships: List[ConceptRelationship] = []

        # Default relationship types
        if not relationship_types:
            relationship_types = ["is-a", "part-of", "has-component", "maps-to"]

        # Would query terminology server for relationships
        # Simplified implementation

        return relationships

    async def translate_code(
        self, source_system: str, source_code: str, target_system: str
    ) -> Optional[str]:
        """Translate a code from one system to another."""
        # First validate source code
        validation = await self.validate_code(source_system, source_code)

        if not validation.valid:
            return None

        # Check cross-mappings
        if target_system in validation.cross_mappings:
            mappings = validation.cross_mappings[target_system]
            if mappings:
                return mappings[0]  # Return first mapping

        # Try concept mapping service
        # Would implement FHIR ConceptMap lookup

        return None

    async def close(self) -> None:
        """Close connections."""
        if self.session:
            await self.session.close()
        if self.redis_client is not None:
            await self.redis_client.close()


# Global instance
terminology_service = TerminologyService()
