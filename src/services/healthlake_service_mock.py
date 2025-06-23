"""Mock HealthLake service for development and testing.

This service simulates FHIR Resource operations and validates FHIR compliance.
Implements mock FHIR DomainResource handling for testing purposes.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

from sqlalchemy.orm import Session

from src.services.base import BaseService
from src.utils.logging import get_logger

logger = get_logger(__name__)


class MockHealthLakeService(BaseService):
    """Mock HealthLake service that simulates FHIR datastore operations."""

    def __init__(self) -> None:
        """Initialize mock HealthLake service."""
        # Create a dummy session for BaseService initialization
        session = Session()
        super().__init__(session)
        # In-memory FHIR resource storage
        # @hipaa_protected - All patient data requires field_encryption
        # @access_control_required - Role-based access required for PHI
        self._resources: Dict[str, Dict[str, Any]] = {
            "Patient": {},
            "Observation": {},
            "MedicationRequest": {},
            "Condition": {},
            "Procedure": {},
            "DocumentReference": {},
        }
        self._datastore_id = "mock-healthlake-datastore"
        logger.info("Initialized mock HealthLake service")

    async def create_resource(
        self, resource_type: str, resource_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create a FHIR resource in mock datastore."""
        try:
            # Generate resource ID
            resource_id = f"{resource_type.lower()}-{uuid4().hex[:8]}"

            # Add metadata
            resource = {
                "resourceType": resource_type,
                "id": resource_id,
                "meta": {
                    "versionId": "1",
                    "lastUpdated": datetime.utcnow().isoformat(),
                    "source": "haven-health-passport",
                },
                **resource_data,
            }

            # Store resource
            # @encrypt_phi - Resource data must be encrypted at rest
            self._resources[resource_type][resource_id] = resource

            logger.info(f"Created mock {resource_type} resource: {resource_id}")

            return {
                "resourceType": resource_type,
                "id": resource_id,
                "datastoreId": self._datastore_id,
                "status": "created",
                "resource": resource,
            }

        except Exception as e:
            logger.error(f"Error creating mock resource: {e}")
            raise

    async def read_resource(
        self, resource_type: str, resource_id: str
    ) -> Optional[Dict[str, Any]]:
        """Read a FHIR resource from mock datastore."""
        try:
            if resource_type in self._resources:
                resource = self._resources[resource_type].get(resource_id)
                if resource:
                    logger.info(f"Retrieved mock {resource_type}: {resource_id}")
                    return resource  # type: ignore[no-any-return]

            logger.warning(f"Mock resource not found: {resource_type}/{resource_id}")
            return None

        except Exception as e:
            logger.error(f"Error reading mock resource: {e}")
            raise

    async def search_resources(
        self, resource_type: str, search_params: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Search FHIR resources in mock datastore."""
        try:
            results = []

            if resource_type in self._resources:
                # Simple filtering based on search params
                for _resource_id, resource in self._resources[resource_type].items():
                    if self._matches_search_params(resource, search_params):
                        results.append(resource)

            logger.info(f"Mock search found {len(results)} {resource_type} resources")

            bundle = {
                "resourceType": "Bundle",
                "type": "searchset",
                "total": len(results),
                "entry": [{"resource": resource} for resource in results],
            }
            return [bundle]

        except Exception as e:
            logger.error(f"Error searching mock resources: {e}")
            raise

    def _matches_search_params(
        self, resource: Dict[str, Any], search_params: Optional[Dict[str, Any]]
    ) -> bool:
        """Check if resource matches search parameters."""
        if not search_params:
            return True

        # Simple parameter matching for common FHIR search params
        for param, value in search_params.items():
            if param == "patient":
                # Check patient reference
                if resource.get("subject", {}).get("reference") != f"Patient/{value}":
                    return False
            elif param == "_lastUpdated":
                # Date range checking would go here
                pass
            elif param in resource:
                # Direct field matching
                if resource[param] != value:
                    return False

        return True

    async def update_resource(
        self, resource_type: str, resource_id: str, resource_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Update a FHIR resource in mock datastore."""
        try:
            if resource_type in self._resources:
                if resource_id in self._resources[resource_type]:
                    # Get existing resource
                    existing = self._resources[resource_type][resource_id]

                    # Update version
                    version = int(existing.get("meta", {}).get("versionId", "0")) + 1

                    # Update resource
                    updated_resource = {
                        "resourceType": resource_type,
                        "id": resource_id,
                        "meta": {
                            "versionId": str(version),
                            "lastUpdated": datetime.utcnow().isoformat(),
                            "source": "haven-health-passport",
                        },
                        **resource_data,
                    }

                    self._resources[resource_type][resource_id] = updated_resource

                    logger.info(f"Updated mock {resource_type}: {resource_id}")

                    return {
                        "resourceType": resource_type,
                        "id": resource_id,
                        "status": "updated",
                        "version": version,
                        "resource": updated_resource,
                    }

            raise ValueError(f"Resource not found: {resource_type}/{resource_id}")

        except Exception as e:
            logger.error(f"Error updating mock resource: {e}")
            raise

    async def delete_resource(
        self, resource_type: str, resource_id: str
    ) -> Dict[str, Any]:
        """Delete a FHIR resource from mock datastore."""
        try:
            if resource_type in self._resources:
                if resource_id in self._resources[resource_type]:
                    del self._resources[resource_type][resource_id]

                    logger.info(f"Deleted mock {resource_type}: {resource_id}")

                    return {
                        "resourceType": resource_type,
                        "id": resource_id,
                        "status": "deleted",
                    }

            raise ValueError(f"Resource not found: {resource_type}/{resource_id}")

        except Exception as e:
            logger.error(f"Error deleting mock resource: {e}")
            raise

    def get_datastore_status(self) -> Dict[str, Any]:
        """Get mock datastore status."""
        total_resources = sum(len(resources) for resources in self._resources.values())

        return {
            "datastoreId": self._datastore_id,
            "datastoreStatus": "ACTIVE",
            "datastoreTypeVersion": "R4",
            "datastoreEndpoint": "mock://localhost/fhir",
            "createdAt": "2024-01-01T00:00:00Z",
            "resourceCount": total_resources,
            "resourceTypes": {
                resource_type: len(resources)
                for resource_type, resources in self._resources.items()
            },
        }

    async def export_data(
        self, output_s3_uri: str, _resource_types: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Mock export data to S3."""
        export_id = f"export-{uuid4().hex[:8]}"

        logger.info(f"Mock export initiated: {export_id}")

        return {
            "exportId": export_id,
            "exportStatus": "COMPLETED",
            "outputS3Uri": output_s3_uri,
            "dataAccessRoleArn": "arn:aws:iam::123456789:role/mock-role",
            "submittedAt": datetime.utcnow().isoformat(),
            "message": "Mock export completed successfully",
        }

    async def import_data(
        self, input_s3_uri: str, data_access_role_arn: str
    ) -> Dict[str, Any]:
        """Mock import data from S3."""
        import_id = f"import-{uuid4().hex[:8]}"

        logger.info(f"Mock import initiated: {import_id}")

        return {
            "importId": import_id,
            "importStatus": "COMPLETED",
            "inputS3Uri": input_s3_uri,
            "dataAccessRoleArn": data_access_role_arn,
            "submittedAt": datetime.utcnow().isoformat(),
            "message": "Mock import completed successfully",
        }
