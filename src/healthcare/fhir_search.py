"""FHIR search parameter configurations with AWS HealthLake integration."""

import asyncio
from typing import Any, Dict, List

from src.healthcare.fhir_client import FHIRClient
from src.healthcare.healthlake_search import get_healthlake_search


class FHIRSearchParameters:
    """Define and configure FHIR search parameters."""

    # Patient search parameters
    PATIENT_SEARCH_PARAMS = {
        "_id": {"type": "token", "description": "Logical id of the patient"},
        "identifier": {
            "type": "token",
            "description": "Patient identifier (e.g., UNHCR ID)",
        },
        "name": {"type": "string", "description": "Patient name (given or family)"},
        "given": {"type": "string", "description": "Patient given name"},
        "family": {"type": "string", "description": "Patient family name"},
        "birthdate": {"type": "date", "description": "Patient birth date"},
        "gender": {"type": "token", "description": "Patient gender"},
        "phone": {"type": "token", "description": "Patient phone number"},
        "email": {"type": "token", "description": "Patient email"},
        "address": {"type": "string", "description": "Patient address"},
        "address-country": {"type": "string", "description": "Country in address"},
        "organization": {"type": "reference", "description": "Managing organization"},
        "_lastUpdated": {"type": "date", "description": "When resource last changed"},
        # Custom search parameters for refugees
        "refugee-status": {
            "type": "token",
            "description": "Refugee status",
            "custom": True,
        },
        "camp-location": {
            "type": "string",
            "description": "Refugee camp location",
            "custom": True,
        },
        "unhcr-number": {
            "type": "token",
            "description": "UNHCR registration number",
            "custom": True,
        },
    }

    # Observation search parameters
    OBSERVATION_SEARCH_PARAMS = {
        "_id": {"type": "token", "description": "Logical id of the observation"},
        "patient": {
            "type": "reference",
            "description": "The subject that the observation is about",
        },
        "subject": {
            "type": "reference",
            "description": "The subject that the observation is about",
        },
        "code": {"type": "token", "description": "The code of the observation type"},
        "date": {"type": "date", "description": "Observation date/time"},
        "category": {"type": "token", "description": "Classification of observation"},
        "status": {"type": "token", "description": "Status of the observation"},
        "value-quantity": {"type": "quantity", "description": "Value of observation"},
        "value-string": {
            "type": "string",
            "description": "Value of observation as string",
        },
        "performer": {
            "type": "reference",
            "description": "Who performed the observation",
        },
        "_lastUpdated": {"type": "date", "description": "When resource last changed"},
    }

    # Immunization search parameters
    IMMUNIZATION_SEARCH_PARAMS = {
        "_id": {"type": "token", "description": "Logical id of the immunization"},
        "patient": {
            "type": "reference",
            "description": "The patient for the immunization",
        },
        "date": {"type": "date", "description": "Vaccination administration date"},
        "vaccine-code": {
            "type": "token",
            "description": "Vaccine product administered",
        },
        "status": {"type": "token", "description": "Immunization status"},
        "lot-number": {"type": "string", "description": "Vaccine lot number"},
        "performer": {
            "type": "reference",
            "description": "Who performed administration",
        },
        "location": {
            "type": "reference",
            "description": "Where administration occurred",
        },
        "_lastUpdated": {"type": "date", "description": "When resource last changed"},
    }

    # Condition search parameters
    CONDITION_SEARCH_PARAMS = {
        "_id": {"type": "token", "description": "Logical id of the condition"},
        "patient": {"type": "reference", "description": "Who has the condition"},
        "subject": {"type": "reference", "description": "Who has the condition"},
        "code": {"type": "token", "description": "Code for the condition"},
        "clinical-status": {
            "type": "token",
            "description": "active | recurrence | relapse | inactive | remission | resolved",
        },
        "severity": {"type": "token", "description": "Severity of the condition"},
        "onset-date": {"type": "date", "description": "When condition started"},
        "recorded-date": {"type": "date", "description": "When condition was recorded"},
        "category": {"type": "token", "description": "Category of condition"},
        "_lastUpdated": {"type": "date", "description": "When resource last changed"},
    }

    # Document reference search parameters
    DOCUMENT_SEARCH_PARAMS = {
        "_id": {"type": "token", "description": "Logical id of the document"},
        "patient": {"type": "reference", "description": "Who the document is about"},
        "subject": {"type": "reference", "description": "Who the document is about"},
        "type": {"type": "token", "description": "Kind of document"},
        "category": {"type": "token", "description": "Categorization of document"},
        "date": {"type": "date", "description": "When document was created"},
        "status": {
            "type": "token",
            "description": "current | superseded | entered-in-error",
        },
        "authenticator": {
            "type": "reference",
            "description": "Who authenticated the document",
        },
        "_lastUpdated": {"type": "date", "description": "When resource last changed"},
    }


class FHIRSearch:
    """Execute FHIR searches with configured parameters."""

    def __init__(self) -> None:
        """Initialize FHIR search."""
        self.client = FHIRClient()
        self.search_params = FHIRSearchParameters()
        self.healthlake_search = get_healthlake_search()

    def search_patients(self, **kwargs: Any) -> List[Dict[str, Any]]:
        """
        Search for patients using FHIR search parameters.

        Examples:
            search_patients(name="John", gender="male")
            search_patients(identifier="UNHCR-123456")
            search_patients(birthdate="1990-01-01")
        """
        # Validate search parameters
        valid_params = {}
        for param, value in kwargs.items():
            if param in self.search_params.PATIENT_SEARCH_PARAMS:
                valid_params[param] = value
            else:
                raise ValueError(f"Invalid search parameter: {param}")

        # Execute search using HealthLake
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            results = loop.run_until_complete(
                self.healthlake_search.search_patients(**valid_params)
            )
            return results  # type: ignore
        finally:
            loop.close()

    def search_observations(self, **kwargs: Any) -> List[Dict[str, Any]]:
        """Search for observations."""
        valid_params = self._validate_params(
            kwargs, self.search_params.OBSERVATION_SEARCH_PARAMS
        )

        # Execute search using HealthLake
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            results = loop.run_until_complete(
                self.healthlake_search.search_observations(**valid_params)
            )
            return results  # type: ignore
        finally:
            loop.close()

    def search_immunizations(self, **kwargs: Any) -> List[Dict[str, Any]]:
        """Search for immunizations."""
        valid_params = self._validate_params(
            kwargs, self.search_params.IMMUNIZATION_SEARCH_PARAMS
        )

        # Execute search using HealthLake
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            results = loop.run_until_complete(
                self.healthlake_search.search_immunizations(**valid_params)
            )
            return results  # type: ignore
        finally:
            loop.close()

    def _validate_params(
        self, params: Dict[str, Any], valid_params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Validate search parameters."""
        validated = {}
        for param, value in params.items():
            if param in valid_params:
                validated[param] = value
            else:
                raise ValueError(f"Invalid search parameter: {param}")
        return validated

    def _build_search_query(self, resource_type: str, params: Dict[str, Any]) -> str:
        """Build FHIR search query string."""
        query_parts = [f"{resource_type}?"]

        for param, value in params.items():
            param_def = getattr(
                self.search_params, f"{resource_type.upper()}_SEARCH_PARAMS", {}
            ).get(param, {})

            # Handle different parameter types
            if param_def.get("type") == "date":
                # Support date ranges
                if isinstance(value, dict):
                    if "start" in value:
                        query_parts.append(f"{param}=ge{value['start']}")
                    if "end" in value:
                        query_parts.append(f"{param}=le{value['end']}")
                else:
                    query_parts.append(f"{param}={value}")

            elif param_def.get("type") == "token":
                # Support system|code format
                query_parts.append(f"{param}={value}")

            elif param_def.get("type") == "reference":
                # Support reference format
                query_parts.append(f"{param}={value}")

            else:
                # String and other types
                query_parts.append(f"{param}={value}")

        return "&".join(query_parts)

    def create_search_bundle(
        self,
        resource_type: str,
        resources: List[Dict[str, Any]],
        total: int,
        search_params: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Create a FHIR search result bundle."""
        return {
            "resourceType": "Bundle",
            "type": "searchset",
            "total": total,
            "link": [
                {
                    "relation": "self",
                    "url": self._build_search_query(resource_type, search_params),
                }
            ],
            "entry": [
                {
                    "fullUrl": f"{resource_type}/{resource.get('id')}",
                    "resource": resource,
                    "search": {"mode": "match"},
                }
                for resource in resources
            ],
        }
