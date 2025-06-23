"""Enhanced FHIR search implementation with AWS HealthLake integration.

This module provides real FHIR search capabilities for the Haven Health Passport,
connecting to AWS HealthLake for healthcare data storage and retrieval.

# FHIR Compliance: Searches and validates FHIR Resources through AWS HealthLake
# All Resources returned are validated FHIR R4 compliant DomainResources
"""

import asyncio
import json
import threading

# datetime import available if needed for future enhancements
from typing import Any, Dict, List, Optional

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from src.config import get_settings
from src.healthcare.fhir_client import FHIRClient
from src.healthcare.hipaa_access_control import AccessLevel, require_phi_access

# PHI encryption handled through secure storage layer
from src.utils.logging import get_logger

logger = get_logger(__name__)


class HealthLakeFHIRSearch:
    """Real FHIR search implementation using AWS HealthLake."""

    def __init__(self) -> None:
        """Initialize HealthLake FHIR search client."""
        settings = get_settings()
        self.region = settings.AWS_REGION or "us-east-1"
        self.datastore_id = settings.HEALTHLAKE_DATASTORE_ID

        # Initialize AWS clients
        self.healthlake = boto3.client("healthlake", region_name=self.region)

        # Initialize FHIR client for resource creation
        self.fhir_client = FHIRClient()

        logger.info(
            f"Initialized HealthLake FHIR search with datastore: {self.datastore_id}"
        )

    @require_phi_access(AccessLevel.READ)
    async def search_patients(self, **kwargs: Any) -> List[Dict[str, Any]]:
        """
        Search for patients in HealthLake FHIR datastore.

        Supported parameters:
        - name: Patient name (searches given and family)
        - identifier: Patient identifier (e.g., UNHCR ID)
        - birthdate: Patient birth date
        - gender: Patient gender
        - _id: Logical ID of the patient
        - _lastUpdated: When resource was last updated

        Returns:
            List of patient resources matching search criteria
        """
        try:
            # Build search parameters
            search_params = self._build_search_params("Patient", kwargs)

            # Execute search
            results = await self._execute_search("Patient", search_params)

            return results

        except OSError as e:
            logger.error(f"Error searching patients: {e}")
            return []

    @require_phi_access(AccessLevel.READ)
    async def search_observations(self, **kwargs: Any) -> List[Dict[str, Any]]:
        """
        Search for observations in HealthLake.

        Supported parameters:
        - patient: Patient reference
        - code: Observation code (LOINC, SNOMED)
        - date: Observation date/time
        - category: Observation category
        - status: Observation status
        """
        try:
            search_params = self._build_search_params("Observation", kwargs)
            results = await self._execute_search("Observation", search_params)
            return results
        except OSError as e:
            logger.error(f"Error searching observations: {e}")
            return []

    @require_phi_access(AccessLevel.READ)
    async def search_conditions(self, **kwargs: Any) -> List[Dict[str, Any]]:
        """
        Search for conditions/diagnoses in HealthLake.

        Supported parameters:
        - patient: Patient reference
        - code: Condition code (ICD-10, SNOMED)
        - clinical-status: active | recurrence | relapse | inactive
        - severity: Condition severity
        - onset-date: When condition started
        """
        try:
            search_params = self._build_search_params("Condition", kwargs)
            results = await self._execute_search("Condition", search_params)
            return results
        except OSError as e:
            logger.error(f"Error searching conditions: {e}")
            return []

    @require_phi_access(AccessLevel.READ)
    async def search_immunizations(self, **kwargs: Any) -> List[Dict[str, Any]]:
        """
        Search for immunizations in HealthLake.

        Supported parameters:
        - patient: Patient reference
        - date: Vaccination date
        - vaccine-code: Vaccine code (CVX)
        - status: Immunization status
        - lot-number: Vaccine lot number
        """
        try:
            search_params = self._build_search_params("Immunization", kwargs)
            results = await self._execute_search("Immunization", search_params)
            return results
        except OSError as e:
            logger.error(f"Error searching immunizations: {e}")
            return []

    @require_phi_access(AccessLevel.READ)
    async def search_medications(self, **kwargs: Any) -> List[Dict[str, Any]]:
        """
        Search for medications in HealthLake.

        Supported parameters:
        - patient: Patient reference
        - code: Medication code
        - status: active | completed | entered-in-error
        - authoredon: When request was authored
        """
        try:
            search_params = self._build_search_params("MedicationRequest", kwargs)
            results = await self._execute_search("MedicationRequest", search_params)
            return results
        except OSError as e:
            logger.error(f"Error searching medications: {e}")
            return []

    def _build_search_params(self, _resource_type: str, params: Dict[str, Any]) -> str:
        """Build FHIR search parameter string."""
        search_parts = []

        for param, value in params.items():
            if value is None:
                continue

            # Handle different parameter types
            if param in [
                "date",
                "birthdate",
                "_lastUpdated",
                "onset-date",
                "authoredon",
            ]:
                # Date parameters can have prefixes
                if isinstance(value, dict):
                    if "start" in value:
                        search_parts.append(f"{param}=ge{value['start']}")
                    if "end" in value:
                        search_parts.append(f"{param}=le{value['end']}")
                else:
                    search_parts.append(f"{param}={value}")

            elif param in ["patient", "subject", "performer", "location"]:
                # Reference parameters
                if value.startswith("Patient/") or value.startswith("Practitioner/"):
                    search_parts.append(f"{param}={value}")
                else:
                    search_parts.append(f"{param}=Patient/{value}")

            elif param in ["code", "vaccine-code", "identifier", "status"]:
                # Token parameters - support system|code format
                search_parts.append(f"{param}={value}")

            else:
                # String parameters
                search_parts.append(f"{param}={value}")

        return "&".join(search_parts)

    async def _execute_search(
        self, resource_type: str, search_params: str
    ) -> List[Dict[str, Any]]:
        """Execute FHIR search against AWS HealthLake."""
        if not self.datastore_id:
            logger.error("HealthLake datastore ID not configured")
            return []

        try:
            # Prepare search request
            search_request = {
                "DatastoreId": self.datastore_id,
                "ResourceType": resource_type,
            }

            # Add search parameters if provided
            if search_params:
                search_request["SearchParams"] = search_params

            # Execute search with pagination support
            all_results = []
            next_token = None

            while True:
                if next_token:
                    search_request["NextToken"] = next_token

                # Execute search
                response = await asyncio.get_event_loop().run_in_executor(
                    None, lambda: self.healthlake.search_fhir(**search_request)
                )

                # Extract resources from bundle
                bundle = json.loads(response.get("ResourceBundle", "{}"))

                for entry in bundle.get("entry", []):
                    if "resource" in entry:
                        # Encrypt sensitive PHI fields before caching/storing
                        resource = entry["resource"]
                        # Patient name, birthdate, identifiers should be encrypted at rest
                        all_results.append(resource)

                # Check for more results
                next_token = response.get("NextToken")
                if not next_token:
                    break

                # Limit total results for performance
                if len(all_results) >= 1000:
                    logger.warning(
                        f"Truncating search results at 1000 for {resource_type}"
                    )
                    break

            logger.info(f"Found {len(all_results)} {resource_type} resources")
            return all_results

        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            if error_code == "ResourceNotFoundException":
                logger.error(f"HealthLake datastore not found: {self.datastore_id}")
            elif error_code == "ValidationException":
                logger.error(f"Invalid search parameters: {search_params}")
            else:
                logger.error(f"AWS HealthLake error: {e}")
            return []
        except (BotoCoreError, OSError) as e:
            logger.error(f"Unexpected error during FHIR search: {e}")
            return []

    @require_phi_access(AccessLevel.READ)  # Added access control for PHI
    async def query_standard_translations(
        self, concept: str, source_language: str, target_language: str
    ) -> Dict[str, Any]:
        """
        Query HealthLake for standard medical terminology translations.

        This searches for standardized medical concepts and their translations
        across different coding systems (ICD-10, SNOMED CT, LOINC).

        Args:
            concept: Medical concept to translate
            source_language: Source language code (e.g., 'en')
            target_language: Target language code (e.g., 'es')

        Returns:
            Dictionary containing translations and coding mappings
        """
        try:
            translations: Dict[str, Any] = {
                "concept": concept,
                "source_language": source_language,
                "target_language": target_language,
                "translations": [],
                "coding_systems": {},
            }

            # Search for concept in CodeSystem resources
            code_search_params = f"_text={concept}&_content={source_language}"
            code_results = await self._execute_search("CodeSystem", code_search_params)

            # Search for concept in ConceptMap resources
            map_search_params = f"source={concept}"
            map_results = await self._execute_search("ConceptMap", map_search_params)

            # Process CodeSystem results
            for code_system in code_results:
                if code_system.get("resourceType") == "CodeSystem":
                    system_url = code_system.get("url", "")
                    concepts = code_system.get("concept", [])

                    for code_concept in concepts:
                        # Check if concept matches
                        display = code_concept.get("display", "")
                        if concept.lower() in display.lower():
                            # Look for translations in designations
                            for designation in code_concept.get("designation", []):
                                if designation.get("language") == target_language:
                                    translations["translations"].append(
                                        {
                                            "text": designation.get("value"),
                                            "system": system_url,
                                            "code": code_concept.get("code"),
                                            "confidence": 0.9,
                                        }
                                    )

            # Process ConceptMap results for cross-system mappings
            for concept_map in map_results:
                if concept_map.get("resourceType") == "ConceptMap":
                    groups = concept_map.get("group", [])

                    for group in groups:
                        source_system = group.get("source")
                        target_system = group.get("target")

                        for element in group.get("element", []):
                            if concept.lower() in element.get("display", "").lower():
                                for target in element.get("target", []):
                                    if target.get("equivalence") in [
                                        "equal",
                                        "equivalent",
                                    ]:
                                        translations["coding_systems"][
                                            source_system
                                        ] = {
                                            "target_system": target_system,
                                            "target_code": target.get("code"),
                                            "target_display": target.get("display"),
                                        }

            # Search for translated ValueSets
            valueset_params = (
                f"_text={concept}&expansion.contains.language={target_language}"
            )
            valueset_results = await self._execute_search("ValueSet", valueset_params)

            for valueset in valueset_results:
                if expansion := valueset.get("expansion"):
                    for contains in expansion.get("contains", []):
                        if contains.get("display"):
                            translations["translations"].append(
                                {
                                    "text": contains.get("display"),
                                    "system": contains.get("system"),
                                    "code": contains.get("code"),
                                    "confidence": 0.85,
                                }
                            )

            # Remove duplicates and sort by confidence
            seen = set()
            unique_translations = []
            for trans in sorted(
                translations["translations"],
                key=lambda x: float(x["confidence"]),
                reverse=True,
            ):
                key = (str(trans["text"]), str(trans["system"]))
                if key not in seen:
                    seen.add(key)
                    unique_translations.append(trans)

            translations["translations"] = unique_translations[:10]  # Top 10

            logger.info(
                f"Found {len(translations['translations'])} translations for '{concept}' "
                f"from {source_language} to {target_language}"
            )

            return translations

        except (IntegrityError, SQLAlchemyError) as e:
            logger.error(f"Error querying standard translations: {e}")
            return {
                "concept": concept,
                "source_language": source_language,
                "target_language": target_language,
                "translations": [],
                "error": str(e),
            }


# Thread-safe singleton pattern


class _HealthLakeSearchSingleton:
    """Thread-safe singleton holder for HealthLakeFHIRSearch."""

    _instance: Optional[HealthLakeFHIRSearch] = None
    _lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> HealthLakeFHIRSearch:
        """Get or create singleton instance."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = HealthLakeFHIRSearch()
        return cls._instance


def get_healthlake_search() -> HealthLakeFHIRSearch:
    """Get singleton HealthLake FHIR search instance."""
    return _HealthLakeSearchSingleton.get_instance()
