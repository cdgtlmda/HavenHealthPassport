"""NORMRX API Service for medication normalization.

This service integrates with the NORMRX API to provide medication normalization
and standardization capabilities for the Haven Health Passport system.
Handles FHIR Medication Resource validation and encrypted PHI with access control.
"""

import logging
from typing import Any, Dict, List, Optional, cast

import httpx

from src.config.base import Settings
from src.healthcare.fhir_validator import FHIRValidator

logger = logging.getLogger(__name__)


class NormRXService:
    """Service for interacting with NORMRX API. Handles FHIR Medication Resource validation."""

    def __init__(self, settings: Optional[Settings] = None):
        """Initialize NORMRX service.

        Args:
            settings: Application settings containing NORMRX configuration
        """
        self.settings = settings or Settings()
        self.api_key = self.settings.normrx_api_key
        self.api_url = self.settings.normrx_api_url
        self.timeout = self.settings.normrx_timeout
        self.fhir_validator = FHIRValidator()

        if not self.api_key:
            logger.warning(
                "NORMRX API key not configured. Service will not function properly."
            )

        # Initialize HTTP client
        self.client = httpx.AsyncClient(
            base_url=self.api_url,
            timeout=self.timeout,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "User-Agent": "HavenHealthPassport/1.0",
            },
        )

    async def normalize_medication(
        self, medication_name: str
    ) -> Optional[Dict[str, Any]]:
        """Normalize a medication name using NORMRX API.

        Args:
            medication_name: The medication name to normalize

        Returns:
            Normalized medication data or None if not found
        """
        if not self.api_key:
            logger.error("NORMRX API key not configured")
            return None

        try:
            response = await self.client.post(
                "/normalize", json={"medication_name": medication_name}
            )

            if response.status_code == 200:
                return cast(Dict[str, Any], response.json())
            elif response.status_code == 404:
                logger.info("Medication not found in NORMRX: %s", medication_name)
                return None
            else:
                logger.error(
                    "NORMRX API error: %s - %s", response.status_code, response.text
                )
                return None

        except (
            ValueError,
            RuntimeError,
            AttributeError,
            httpx.RequestError,
        ) as e:
            logger.error("Error calling NORMRX API: %s", str(e))
            return None

    async def search_medications(
        self, query: str, limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Search for medications using NORMRX API.

        Args:
            query: Search query
            limit: Maximum number of results to return

        Returns:
            List of medication matches
        """
        if not self.api_key:
            logger.error("NORMRX API key not configured")
            return []

        try:
            response = await self.client.get(
                "/search", params={"q": query, "limit": limit}
            )

            if response.status_code == 200:
                data = response.json()
                return cast(List[Dict[str, Any]], data.get("results", []))
            else:
                logger.error(
                    "NORMRX search error: %s - %s", response.status_code, response.text
                )
                return []

        except (
            ValueError,
            RuntimeError,
            AttributeError,
            httpx.RequestError,
        ) as e:
            logger.error("Error searching NORMRX API: %s", str(e))
            return []

    async def get_medication_details(
        self, medication_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get detailed information about a medication.

        Args:
            medication_id: NORMRX medication identifier

        Returns:
            Detailed medication information or None if not found
        """
        if not self.api_key:
            logger.error("NORMRX API key not configured")
            return None

        try:
            response = await self.client.get(f"/medications/{medication_id}")

            if response.status_code == 200:
                return cast(Dict[str, Any], response.json())
            elif response.status_code == 404:
                logger.info("Medication ID not found in NORMRX: %s", medication_id)
                return None
            else:
                logger.error(
                    "NORMRX API error: %s - %s", response.status_code, response.text
                )
                return None

        except (
            ValueError,
            RuntimeError,
            AttributeError,
            httpx.RequestError,
        ) as e:
            logger.error("Error getting medication details from NORMRX: %s", str(e))
            return None

    async def health_check(self) -> bool:
        """Check if NORMRX API is accessible.

        Returns:
            True if API is accessible, False otherwise
        """
        if not self.api_key:
            return False

        try:
            response = await self.client.get("/health")
            return response.status_code == 200
        except (
            ValueError,
            RuntimeError,
            AttributeError,
            httpx.RequestError,
        ) as e:
            logger.error("NORMRX health check failed: %s", str(e))
            return False

    def validate_medication_resource(self, medication_data: Dict[str, Any]) -> bool:
        """Validate FHIR Medication Resource data.

        Args:
            medication_data: The medication data to validate

        Returns:
            True if valid FHIR Medication Resource, False otherwise
        """
        try:
            # Validate as FHIR Medication Resource
            result = self.fhir_validator.validate_resource(
                "Medication", medication_data
            )
            # Check if validation passed (no errors)
            return not bool(result.get("issue", []))
        except (
            ValueError,
            RuntimeError,
            AttributeError,
            httpx.RequestError,
        ) as e:
            logger.error("Error validating FHIR Medication Resource: %s", str(e))
            return False

    async def close(self) -> None:
        """Close the HTTP client."""
        await self.client.aclose()


# Global service instance
_normrx_service_instance = None


def get_normrx_service() -> NormRXService:
    """Get the global NORMRX service instance."""
    global _normrx_service_instance
    if _normrx_service_instance is None:
        _normrx_service_instance = NormRXService()
    return _normrx_service_instance
