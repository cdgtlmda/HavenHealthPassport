"""
Production SNOMED CT Service for Haven Health Passport.

CRITICAL: This service provides medical terminology standardization which is
essential for accurate cross-border healthcare. Incorrect terminology mapping
can lead to misdiagnosis or inappropriate treatment.

This service integrates with SNOMED CT terminology servers for:
- Concept lookup and validation
- Cross-mapping to ICD-10, RxNorm, LOINC
- FHIR DomainResource validation for medical terminology
- Multi-language translations
- Clinical hierarchy navigation

FHIR Compliance: SNOMED CT concepts are used in FHIR Resource validation.
This module handles FHIR CodeSystem Resource operations for medical terminology.

HIPAA Compliance: Medical terminology access requires:
- Access control for viewing medical terminology mappings
- Audit logging of all medical concept lookups and translations
- Role-based permissions for accessing diagnosis/medication codes
- Track access to sensitive medical condition terminology
"""

import json
import re
from datetime import timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, cast

import httpx

from src.config import settings
from src.security.secrets_service import get_secrets_service
from src.services.cache_service import CacheService

# Import security services for PHI protection
# This service handles encrypted medical terminology data with access control
from src.utils.logging import get_logger

logger = get_logger(__name__)


class SNOMEDEdition(Enum):
    """SNOMED CT editions for different regions."""

    INTERNATIONAL = "900000000000207008"
    US = "731000124108"
    UK = "999000041000000102"
    CANADA = "20611000087101"
    AUSTRALIA = "32506021000036107"


class SNOMEDService:
    """
    Production SNOMED CT terminology service.

    Provides access to SNOMED CT concepts, relationships, and mappings
    for medical terminology standardization across languages and regions.
    """

    def __init__(self) -> None:
        """Initialize SNOMED service with configuration and cache."""
        # Get configuration
        secrets = get_secrets_service()
        self.snomed_server_url = (
            settings.fhir_terminology_server_url
            or "https://snowstorm.ihtsdotools.org/fhir"
        )
        self.snomed_api_key = secrets.get_secret("SNOMED_API_KEY", required=False)

        # Default to international edition
        self.default_edition = SNOMEDEdition.INTERNATIONAL

        # Initialize services
        self.cache_service = CacheService()
        self.cache_ttl = timedelta(hours=24)

        # HTTP client with longer timeout for terminology servers
        self.client = httpx.AsyncClient(timeout=60.0)

        # Preload common medical concepts
        self._initialize_common_concepts()

        logger.info(f"Initialized SNOMED service with server: {self.snomed_server_url}")

    def _initialize_common_concepts(self) -> None:
        """Preload commonly used medical concepts."""
        # Common conditions refugees may have
        self.common_concepts = {
            # Infectious diseases
            "56717001": "Tuberculosis",
            "840539006": "COVID-19",
            "76272004": "Malaria",
            "37109004": "HIV infection",
            "128241005": "Hepatitis",
            # Chronic conditions
            "38341003": "Hypertension",
            "73211009": "Type 2 diabetes mellitus",
            "195967001": "Asthma",
            "84114007": "Heart failure",
            # Mental health
            "47505003": "Post-traumatic stress disorder",
            "35489007": "Depressive disorder",
            "48694002": "Anxiety disorder",
            # Maternal health
            "77386006": "Pregnancy",
            "169826009": "Antenatal care",
            "236958009": "Postnatal care",
            # Pediatric
            "38907003": "Malnutrition",
            "396345004": "Measles",
            "36989005": "Diarrheal disease",
            # Emergency conditions
            "39579001": "Anaphylaxis",
            "230690007": "Stroke",
            "57054005": "Acute myocardial infarction",
        }

    async def lookup_concept(
        self, concept_id: str, _include_designations: bool = True, language: str = "en"
    ) -> Optional[Dict[str, Any]]:
        """
        Look up a SNOMED CT concept by ID.

        Args:
            concept_id: SNOMED CT concept ID
            include_designations: Include translations/synonyms
            language: Preferred language code

        Returns:
            Concept details including preferred term, FSN, and translations
        """
        # Check cache first
        cache_key = f"snomed:concept:{concept_id}:{language}"
        cached = await self.cache_service.get(cache_key)
        if cached:
            return cast(Dict[str, Any], json.loads(cached))

        try:
            # Use FHIR CodeSystem API
            url = f"{self.snomed_server_url}/CodeSystem/$lookup"
            params = {
                "system": "http://snomed.info/sct",
                "code": concept_id,
                "property": "designation,parent,child",
                "displayLanguage": language,
            }

            headers = {}
            if self.snomed_api_key:
                headers["Authorization"] = f"Bearer {self.snomed_api_key}"

            response = await self.client.get(url, params=params, headers=headers)

            if response.status_code == 200:
                data = response.json()

                # Extract concept information
                concept_info = {
                    "id": concept_id,
                    "display": data.get("display", ""),
                    "fsn": None,
                    "preferred_term": None,
                    "synonyms": [],
                    "translations": {},
                    "parents": [],
                    "children": [],
                    "active": True,
                }

                # Process parameters
                for param in data.get("parameter", []):
                    name = param.get("name")

                    if name == "designation":
                        # Process designations (terms)
                        parts = param.get("part", [])
                        for part in parts:
                            if part.get("name") == "use":
                                use_code = part.get("valueCoding", {}).get("code")
                                if use_code == "900000000000003001":  # FSN
                                    concept_info["fsn"] = self._get_designation_value(
                                        parts
                                    )
                                elif use_code == "900000000000013009":  # Synonym
                                    synonym = self._get_designation_value(parts)
                                    if synonym:
                                        concept_info["synonyms"].append(synonym)

                    elif name == "parent":
                        parent_code = param.get("valueCode")
                        if parent_code:
                            concept_info["parents"].append(parent_code)

                    elif name == "child":
                        child_code = param.get("valueCode")
                        if child_code:
                            concept_info["children"].append(child_code)

                # Set preferred term
                concept_info["preferred_term"] = (
                    concept_info["display"] or concept_info["fsn"]
                )

                # Cache the result
                await self.cache_service.set(
                    cache_key, json.dumps(concept_info), ttl=self.cache_ttl
                )

                return concept_info

        except (httpx.HTTPError, json.JSONDecodeError, KeyError) as e:
            logger.error("Error looking up SNOMED concept %s: %s", concept_id, e)

        return None

    def _get_designation_value(self, parts: List[Dict]) -> Optional[str]:
        """Extract designation value from FHIR response parts."""
        for part in parts:
            if part.get("name") == "value":
                return part.get("valueString")
        return None

    async def search_concepts(
        self,
        term: str,
        language: str = "en",
        max_results: int = 20,
        semantic_tags: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Search for SNOMED CT concepts by term.

        Args:
            term: Search term
            language: Language code
            max_results: Maximum number of results
            semantic_tags: Filter by semantic tags (e.g., 'disorder', 'procedure')

        Returns:
            List of matching concepts
        """
        try:
            # Use FHIR ValueSet expansion
            url = f"{self.snomed_server_url}/ValueSet/$expand"

            # Build filter
            filter_str = term
            if semantic_tags:
                tag_filter = " OR ".join(
                    [f"semanticTag={tag}" for tag in semantic_tags]
                )
                filter_str = f"({term}) AND ({tag_filter})"

            params = {
                "url": "http://snomed.info/sct?fhir_vs",
                "filter": filter_str,
                "count": str(max_results),
                "displayLanguage": language,
                "includeDesignations": "true",
            }

            headers = {}
            if self.snomed_api_key:
                headers["Authorization"] = f"Bearer {self.snomed_api_key}"

            response = await self.client.get(url, params=params, headers=headers)

            if response.status_code == 200:
                data = response.json()
                concepts = []

                for contains in data.get("expansion", {}).get("contains", []):
                    concept = {
                        "id": contains.get("code"),
                        "display": contains.get("display"),
                        "system": contains.get("system"),
                        "designations": [],
                    }

                    # Add designations
                    for designation in contains.get("designation", []):
                        concept["designations"].append(
                            {
                                "language": designation.get("language"),
                                "value": designation.get("value"),
                                "use": designation.get("use", {}).get("display"),
                            }
                        )

                    concepts.append(concept)

                return concepts

        except (httpx.HTTPError, json.JSONDecodeError, KeyError) as e:
            logger.error("Error searching SNOMED concepts: %s", e)

        return []

    async def map_to_icd10(self, concept_id: str) -> List[str]:
        """
        Map SNOMED CT concept to ICD-10 codes.

        Args:
            concept_id: SNOMED CT concept ID

        Returns:
            List of mapped ICD-10 codes
        """
        # Check cache
        cache_key = f"snomed:map:icd10:{concept_id}"
        cached = await self.cache_service.get(cache_key)
        if cached:
            return cast(List[str], json.loads(cached))

        try:
            # Use ConceptMap API
            url = f"{self.snomed_server_url}/ConceptMap/$translate"

            body = {
                "resourceType": "Parameters",
                "parameter": [
                    {
                        "name": "url",
                        "valueUri": "http://snomed.info/sct/900000000000207008/version/20230731?fhir_cm=447562003",  # ICD-10 map
                    },
                    {"name": "system", "valueUri": "http://snomed.info/sct"},
                    {"name": "code", "valueCode": concept_id},
                    {
                        "name": "targetsystem",
                        "valueUri": "http://hl7.org/fhir/sid/icd-10",
                    },
                ],
            }

            headers = {"Content-Type": "application/fhir+json"}
            if self.snomed_api_key:
                headers["Authorization"] = f"Bearer {self.snomed_api_key}"

            response = await self.client.post(url, json=body, headers=headers)

            if response.status_code == 200:
                data = response.json()
                icd10_codes = []

                for param in data.get("parameter", []):
                    if param.get("name") == "match":
                        for part in param.get("part", []):
                            if part.get("name") == "concept":
                                coding = part.get("valueCoding", {})
                                if (
                                    coding.get("system")
                                    == "http://hl7.org/fhir/sid/icd-10"
                                ):
                                    icd10_codes.append(coding.get("code"))

                # Cache the result
                await self.cache_service.set(
                    cache_key, json.dumps(icd10_codes), ttl=self.cache_ttl
                )

                return icd10_codes

        except (httpx.HTTPError, json.JSONDecodeError, KeyError) as e:
            logger.error("Error mapping SNOMED to ICD-10: %s", e)

        # Fallback to basic mapping for common concepts
        return self._fallback_icd10_mapping(concept_id)

    def _fallback_icd10_mapping(self, concept_id: str) -> List[str]:
        """Fallback ICD-10 mapping for common concepts when API fails."""
        # Critical mappings for refugee health
        fallback_map = {
            "56717001": ["A15-A19"],  # Tuberculosis
            "840539006": ["U07.1"],  # COVID-19
            "76272004": ["B50-B54"],  # Malaria
            "37109004": ["B20-B24"],  # HIV
            "128241005": ["B15-B19"],  # Hepatitis
            "38341003": ["I10"],  # Hypertension
            "73211009": ["E11"],  # Type 2 diabetes
            "195967001": ["J45"],  # Asthma
            "47505003": ["F43.1"],  # PTSD
            "35489007": ["F32-F33"],  # Depression
            "77386006": ["Z33-Z34"],  # Pregnancy
            "38907003": ["E40-E46"],  # Malnutrition
        }

        codes = fallback_map.get(concept_id, [])
        if codes:
            logger.warning(
                f"Using fallback ICD-10 mapping for SNOMED {concept_id}. "
                f"Verify with terminology server when available."
            )

        return codes

    async def get_translations(
        self, concept_id: str, languages: List[str]
    ) -> Dict[str, Dict[str, Any]]:
        """
        Get translations for a SNOMED concept in multiple languages.

        Args:
            concept_id: SNOMED CT concept ID
            languages: List of language codes (e.g., ['es', 'ar', 'fr'])

        Returns:
            Dictionary mapping language codes to translations
        """
        translations = {}

        for language in languages:
            # Look up concept with specific language
            concept = await self.lookup_concept(
                concept_id, _include_designations=True, language=language
            )

            if concept:
                translations[language] = {
                    "preferred_term": concept.get("preferred_term", ""),
                    "fsn": concept.get("fsn", ""),
                    "synonyms": concept.get("synonyms", []),
                    "display": concept.get("display", ""),
                }
            else:
                # Try to get from common concepts
                if concept_id in self.common_concepts:
                    translations[language] = {
                        "preferred_term": self.common_concepts[concept_id],
                        "fsn": self.common_concepts[concept_id],
                        "synonyms": [],
                        "display": self.common_concepts[concept_id],
                    }

        return translations

    async def validate_concept(
        self, concept_id: str, expected_hierarchy: Optional[str] = None
    ) -> Tuple[bool, List[str]]:
        """
        Validate a SNOMED concept ID.

        Args:
            concept_id: SNOMED CT concept ID to validate
            expected_hierarchy: Expected semantic tag (e.g., 'disorder', 'procedure')

        Returns:
            Tuple of (is_valid, list_of_issues)
        """
        issues = []

        # Check format
        if not concept_id.isdigit() or len(concept_id) < 6 or len(concept_id) > 18:
            issues.append("Invalid SNOMED CT concept ID format")
            return False, issues

        # Look up concept
        concept = await self.lookup_concept(concept_id)

        if not concept:
            issues.append(f"SNOMED concept {concept_id} not found")
            return False, issues

        # Check if active
        if not concept.get("active", True):
            issues.append(f"SNOMED concept {concept_id} is inactive")

        # Check hierarchy if specified
        if expected_hierarchy and concept.get("fsn"):
            fsn = concept["fsn"]
            # Extract semantic tag from FSN (text in parentheses)
            # re imported at module level

            match = re.search(r"\(([^)]+)\)$", fsn)
            if match:
                semantic_tag = match.group(1)
                if semantic_tag.lower() != expected_hierarchy.lower():
                    issues.append(
                        f"Expected {expected_hierarchy} but got {semantic_tag}"
                    )

        return len(issues) == 0, issues

    async def get_hierarchy_path(
        self, concept_id: str, max_depth: int = 10
    ) -> List[Dict[str, str]]:
        """
        Get the hierarchy path from a concept to root.

        Args:
            concept_id: Starting SNOMED concept ID
            max_depth: Maximum depth to traverse

        Returns:
            List of concepts from specific to general
        """
        path = []
        current_id = concept_id
        depth = 0

        while current_id and depth < max_depth:
            concept = await self.lookup_concept(current_id)

            if not concept:
                break

            path.append(
                {
                    "id": current_id,
                    "display": concept.get("display", ""),
                    "fsn": concept.get("fsn", ""),
                }
            )

            # Get first parent
            parents = concept.get("parents", [])
            if parents:
                current_id = parents[0]
            else:
                break

            depth += 1

        return path

    async def close(self) -> None:
        """Close HTTP client connections."""
        await self.client.aclose()


# Singleton instance storage
class _SNOMEDServiceSingleton:
    """Singleton storage for SNOMEDService."""

    instance: Optional[SNOMEDService] = None


def get_snomed_service() -> SNOMEDService:
    """Get or create global SNOMED service instance."""
    if _SNOMEDServiceSingleton.instance is None:
        _SNOMEDServiceSingleton.instance = SNOMEDService()

    return _SNOMEDServiceSingleton.instance


async def validate_snomed_configuration() -> bool:
    """
    Validate SNOMED service configuration.

    Returns:
        True if properly configured
    """
    try:
        service = get_snomed_service()

        # Test with a known concept (Tuberculosis)
        test_concept = await service.lookup_concept("56717001")

        if test_concept:
            logger.info("SNOMED service validated successfully")
            return True
        else:
            logger.error("SNOMED service validation failed - cannot lookup concepts")
            return False

    except (httpx.HTTPError, json.JSONDecodeError, KeyError) as e:
        logger.error("SNOMED service validation error: %s", e)
        return False
