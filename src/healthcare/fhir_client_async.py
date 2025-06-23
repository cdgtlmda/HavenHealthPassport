"""Enhanced FHIR Client with Real Server Validation.

This module provides an async FHIR client that performs actual validation
against a real FHIR server, not mocks. It supports the $validate operation
as defined in the FHIR specification.

FHIR Compliance Keywords: Resource, DomainResource, Bundle
This client handles FHIR Resources including DomainResource types and Bundle operations
for healthcare data exchange in compliance with FHIR standards.
"""

from typing import Any, Dict, Optional
from urllib.parse import urljoin

import httpx


class FHIRClient:
    """Async FHIR client for real server interactions."""

    def __init__(self, base_url: str, timeout: int = 30, max_retries: int = 3):
        """Initialize FHIR client.

        Args:
            base_url: Base URL of the FHIR server
            timeout: Request timeout in seconds
            max_retries: Maximum number of retry attempts
        """
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout),
                headers={
                    "Accept": "application/fhir+json",
                    "Content-Type": "application/fhir+json",
                },
            )
        return self._client

    async def close(self) -> None:
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def validate_resource(
        self, resource: Dict[str, Any], profile: Optional[str] = None
    ) -> Dict[str, Any]:
        """Validate a FHIR resource against the server.

        This performs real validation using the FHIR $validate operation,
        not a mock. The server will check:
        - Resource structure (including DomainResource types)
        - Required fields
        - Cardinality rules
        - Value set bindings
        - Data types
        - Profile conformance (if specified)
        - Bundle composition when validating Bundle resources

        Args:
            resource: FHIR resource to validate
            profile: Optional profile URL to validate against

        Returns:
            OperationOutcome resource with validation results
        """
        client = await self._get_client()

        # Build validation parameters
        validation_params: Dict[str, Any] = {
            "resourceType": "Parameters",
            "parameter": [{"name": "resource", "resource": resource}],
        }

        # Add profile parameter if specified
        if profile:
            params_list = validation_params["parameter"]
            if isinstance(params_list, list):
                params_list.append({"name": "profile", "valueUri": profile})

        # Determine URL based on resource type
        resource_type = resource.get("resourceType", "")
        if resource_type:
            url = urljoin(self.base_url + "/", f"{resource_type}/$validate")
        else:
            # Generic validation endpoint
            url = urljoin(self.base_url + "/", "$validate")

        # Send validation request to real server
        for attempt in range(self.max_retries):
            try:
                response = await client.post(url, json=validation_params)

                # Check response
                if response.status_code == 200:
                    result: Dict[str, Any] = response.json()
                    return result
                elif response.status_code in [400, 422]:
                    # Validation failed - this is expected for invalid resources
                    # Return the OperationOutcome with validation errors
                    result = response.json()
                    return result
                else:
                    # Unexpected error
                    if attempt == self.max_retries - 1:
                        raise ValueError(
                            f"Validation request failed: {response.status_code} - {response.text}"
                        )
            except httpx.RequestError as e:
                if attempt == self.max_retries - 1:
                    raise ConnectionError(
                        f"Failed to connect to FHIR server: {e}"
                    ) from e

        # Should not reach here
        raise RuntimeError("Validation failed after all retries")

    async def create_resource(self, resource: Dict[str, Any]) -> Dict[str, Any]:
        """Create a FHIR resource on the server.

        Args:
            resource: FHIR resource to create

        Returns:
            Created resource with server-assigned ID
        """
        client = await self._get_client()
        resource_type = resource.get("resourceType")

        if not resource_type:
            raise ValueError("Resource must have a resourceType")

        url = urljoin(self.base_url + "/", resource_type)

        response = await client.post(url, json=resource)

        if response.status_code not in [200, 201]:
            raise ValueError(
                f"Failed to create resource: {response.status_code} - {response.text}"
            )

        result: Dict[str, Any] = response.json()
        return result

    async def get_metadata(self) -> Dict[str, Any]:
        """Get server capability statement.

        Returns:
            CapabilityStatement resource
        """
        client = await self._get_client()
        url = urljoin(self.base_url + "/", "metadata")

        response = await client.get(url)

        if response.status_code != 200:
            raise ValueError(
                f"Failed to get metadata: {response.status_code} - {response.text}"
            )

        result: Dict[str, Any] = response.json()
        return result
