"""FHIR server integration for AWS HealthLake."""

import json
import os
from typing import Any, Dict, List, Optional, Tuple

import boto3
from botocore.exceptions import ClientError
from fhirclient.models.medication import Medication as FHIRMedication
from fhirclient.models.meta import Meta
from fhirclient.models.observation import Observation as FHIRObservation
from fhirclient.models.patient import Patient as FHIRPatient
from fhirclient.models.procedure import Procedure as FHIRProcedure

from src.healthcare.hipaa_access_control import (
    AccessLevel,
    audit_phi_access,
    require_phi_access,
)
from src.healthcare.medication_resource import MedicationResource
from src.healthcare.observation_resource import ObservationResource
from src.healthcare.patient_resource import PatientResource
from src.healthcare.procedure_resource import ProcedureResource
from src.security.encryption import EncryptionService
from src.utils.logging import get_logger

logger = get_logger(__name__)


class FHIRServerClient:
    """Client for interacting with AWS HealthLake FHIR server."""

    def __init__(self) -> None:
        """Initialize FHIR server client."""
        aws_region = os.getenv("AWS_REGION", "us-east-1")
        self.healthlake_endpoint = os.getenv(
            "HEALTHLAKE_ENDPOINT",
            f"https://healthlake.{aws_region}.amazonaws.com",
        )
        self.datastore_id = os.getenv("HEALTHLAKE_DATASTORE_ID")

        # Initialize AWS HealthLake client
        self.healthlake_client = boto3.client(
            "healthlake",
            region_name=aws_region,
            aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
        )

        # Initialize FHIR client settings
        self.fhir_version = "R4"
        self.content_type = "application/fhir+json"

        # Initialize resource handlers
        self.patient_handler = PatientResource()
        self.observation_handler = ObservationResource()
        self.medication_handler = MedicationResource()
        self.procedure_handler = ProcedureResource()

        # KMS configuration for encryption
        self.kms_key_id = os.getenv("KMS_KEY_ID", "alias/haven-health-key")
        self.region = aws_region
        self.fhir_settings = {
            "app_id": "haven-health-passport",
            "api_base": f"{self.healthlake_endpoint}/datastore/{self.datastore_id}/r4/",
        }

        # Initialize resource handlers
        self.patient_handler = PatientResource()
        self.observation_handler = ObservationResource()
        self.medication_handler = MedicationResource()
        self.procedure_handler = ProcedureResource()

        # Batch operation settings
        self.batch_size = 100
        self.max_retries = 3

        # Initialize encryption service for PHI
        self._encryption_service = EncryptionService(self.kms_key_id, self.region)

    def validate_resource(self, resource: Any) -> Tuple[bool, List[str]]:
        """Validate a FHIR resource.

        Args:
            resource: FHIR resource to validate

        Returns:
            Tuple of (is_valid, errors)
        """
        try:
            # Use appropriate handler based on resource type
            if isinstance(resource, FHIRPatient):
                return self.patient_handler.validate(resource)  # type: ignore[return-value]
            elif isinstance(resource, FHIRObservation):
                return self.observation_handler.validate(resource)  # type: ignore[return-value]
            elif isinstance(resource, FHIRMedication):
                return self.medication_handler.validate(resource)  # type: ignore[return-value]
            elif isinstance(resource, FHIRProcedure):
                return self.procedure_handler.validate(resource)  # type: ignore[return-value]
            else:
                return False, ["Unsupported resource type"]

        except (ValueError, TypeError, AttributeError) as e:
            logger.error(f"Validation error: {e}")
            return False, [str(e)]

    @require_phi_access(AccessLevel.WRITE)
    @audit_phi_access("create_patient")
    def create_patient(self, patient_data: Dict[str, Any]) -> Optional[str]:
        """Create a patient resource in HealthLake.

        Args:
            patient_data: Patient data dictionary

        Returns:
            Patient resource ID or None
        """
        try:
            # Create FHIR Patient resource
            patient = self.patient_handler.create_resource(patient_data)

            # Validate resource
            is_valid, errors = self.validate_resource(patient)
            if not is_valid:
                logger.error(f"Invalid patient resource: {errors}")
                return None

            # Convert to JSON
            patient_json = patient.as_json()

            # Create in HealthLake
            response = self.healthlake_client.create_resource(
                DatastoreId=self.datastore_id,
                ResourceType="Patient",
                ClientToken=f"patient-{patient_data.get('id', 'new')}",
                ResourceContent=json.dumps(patient_json),
            )

            # Extract resource ID from response
            if response.get("ResourceId"):
                logger.info(f"Created patient {response['ResourceId']} in HealthLake")
                return response["ResourceId"]  # type: ignore[no-any-return]

            return None

        except ClientError as e:
            logger.error(f"Failed to create patient in HealthLake: {e}")
            return None

    def get_patient(self, patient_id: str) -> Optional[Dict[str, Any]]:
        """Get a patient resource from HealthLake.

        Args:
            patient_id: Patient resource ID

        Returns:
            Patient resource data or None
        """
        try:
            response = self.healthlake_client.read_resource(
                DatastoreId=self.datastore_id,
                ResourceType="Patient",
                ResourceId=patient_id,
            )

            if response.get("ResourceContent"):
                return json.loads(response["ResourceContent"])  # type: ignore[no-any-return]

            return None

        except ClientError as e:
            logger.error(f"Failed to get patient from HealthLake: {e}")
            return None

    def search_patients(
        self,
        search_params: Dict[str, Any],
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Search for patients in HealthLake.

        Args:
            search_params: Search parameters
            limit: Maximum results

        Returns:
            List of patient resources
        """
        try:
            # Build search query
            search_string = self._build_search_query(search_params)

            response = self.healthlake_client.search_with_post(
                DatastoreId=self.datastore_id,
                ResourceType="Patient",
                SearchString=search_string,
                MaxResults=limit,
            )

            results = []
            if response.get("Bundle"):
                bundle = json.loads(response["Bundle"])
                if bundle.get("entry"):
                    for entry in bundle["entry"]:
                        if entry.get("resource"):
                            results.append(entry["resource"])

            return results

        except ClientError as e:
            logger.error(f"Failed to search patients in HealthLake: {e}")
            return []

    def create_observation(
        self,
        observation_data: Dict[str, Any],
    ) -> Optional[str]:
        """Create an observation resource in HealthLake.

        Args:
            observation_data: Observation data

        Returns:
            Observation resource ID or None
        """
        try:
            # Create FHIR Observation resource
            observation = self.observation_handler.create_resource(observation_data)

            # Validate resource
            is_valid, errors = self.validate_resource(observation)
            if not is_valid:
                logger.error(f"Invalid observation resource: {errors}")
                return None

            # Convert to JSON
            observation_json = observation.as_json()

            # Create in HealthLake
            response = self.healthlake_client.create_resource(
                DatastoreId=self.datastore_id,
                ResourceType="Observation",
                ClientToken=f"observation-{observation_data.get('id', 'new')}",
                ResourceContent=json.dumps(observation_json),
            )

            if response.get("ResourceId"):
                logger.info(
                    f"Created observation {response['ResourceId']} in HealthLake"
                )
                return response["ResourceId"]  # type: ignore[no-any-return]

            return None

        except ClientError as e:
            logger.error(f"Failed to create observation in HealthLake: {e}")
            return None

    def batch_create_resources(
        self,
        resources: List[Tuple[str, Dict[str, Any]]],
    ) -> Dict[str, Any]:
        """Batch create multiple resources.

        Args:
            resources: List of (resource_type, resource_data) tuples

        Returns:
            Results dictionary
        """
        results = {
            "total": len(resources),
            "succeeded": 0,
            "failed": 0,
            "errors": [],
        }

        # Process in batches
        for i in range(0, len(resources), self.batch_size):
            batch = resources[i : i + self.batch_size]

            # Create bundle
            bundle_entries = []
            for resource_type, resource_data in batch:
                # Create appropriate resource
                if resource_type == "Patient":
                    resource = self.patient_handler.create_resource(resource_data)
                elif resource_type == "Observation":
                    resource = self.observation_handler.create_resource(resource_data)
                elif resource_type == "Medication":
                    resource = self.medication_handler.create_resource(resource_data)
                elif resource_type == "Procedure":
                    resource = self.procedure_handler.create_resource(resource_data)
                else:
                    continue

                # Validate resource
                is_valid, errors = self.validate_resource(resource)
                if not is_valid:
                    results["failed"] += 1  # type: ignore[operator]
                    results["errors"].append(  # type: ignore[attr-defined]
                        {
                            "resource_type": resource_type,
                            "errors": errors,
                        }
                    )
                    continue

                # Add to bundle
                bundle_entries.append(
                    {
                        "resource": resource.as_json(),
                        "request": {
                            "method": "POST",
                            "url": resource_type,
                        },
                    }
                )

            # Execute batch
            if bundle_entries:
                try:
                    bundle = {
                        "resourceType": "Bundle",
                        "type": "batch",
                        "entry": bundle_entries,
                    }

                    response = self.healthlake_client.create_resource(
                        DatastoreId=self.datastore_id,
                        ResourceType="Bundle",
                        ResourceContent=json.dumps(bundle),
                    )

                    # Process response
                    if response.get("ResourceContent"):
                        response_bundle = json.loads(response["ResourceContent"])
                        for entry in response_bundle.get("entry", []):
                            if (
                                entry.get("response", {})
                                .get("status", "")
                                .startswith("2")
                            ):
                                results["succeeded"] += 1  # type: ignore[operator]
                            else:
                                results["failed"] += 1  # type: ignore[operator]

                except ClientError as e:
                    logger.error(f"Batch operation failed: {e}")
                    results["failed"] += len(bundle_entries)  # type: ignore[operator]

        return results

    def _build_search_query(self, params: Dict[str, Any]) -> str:
        """Build FHIR search query string.

        Args:
            params: Search parameters

        Returns:
            Query string
        """
        query_parts = []

        # Map common search parameters
        param_mapping = {
            "name": "name",
            "family": "family",
            "given": "given",
            "identifier": "identifier",
            "birthdate": "birthdate",
            "gender": "gender",
            "address": "address",
            "telecom": "telecom",
        }

        for key, value in params.items():
            if key in param_mapping and value:
                query_parts.append(f"{param_mapping[key]}={value}")

        # Handle date range searches
        if "birthdate_range" in params:
            start, end = params["birthdate_range"]
            query_parts.append(f"birthdate=ge{start}")
            query_parts.append(f"birthdate=le{end}")

        return "&".join(query_parts)

    def validate_against_profile(
        self,
        resource: Any,
        profile_url: str,
    ) -> Tuple[bool, List[str]]:
        """Validate resource against a specific profile.

        Args:
            resource: FHIR resource
            profile_url: Profile URL

        Returns:
            Tuple of (is_valid, errors)
        """
        try:
            # Add profile to resource meta
            if not resource.meta:
                resource.meta = Meta()

            if not resource.meta.profile:
                resource.meta.profile = []

            if profile_url not in resource.meta.profile:
                resource.meta.profile.append(profile_url)

            # Perform validation
            return self.validate_resource(resource)

        except (ValueError, TypeError, AttributeError) as e:
            logger.error(f"Profile validation error: {e}")
            return False, [str(e)]

    def get_datastore_status(self) -> Optional[Dict[str, Any]]:
        """Get HealthLake datastore status.

        Returns:
            Datastore status or None
        """
        try:
            response = self.healthlake_client.describe_fhir_datastore(
                DatastoreId=self.datastore_id
            )

            if response.get("DatastoreProperties"):
                return {
                    "id": response["DatastoreProperties"]["DatastoreId"],
                    "status": response["DatastoreProperties"]["DatastoreStatus"],
                    "type": response["DatastoreProperties"]["DatastoreTypeVersion"],
                    "endpoint": response["DatastoreProperties"]["DatastoreEndpoint"],
                    "created_at": response["DatastoreProperties"]["CreatedAt"],
                }

            return None

        except ClientError as e:
            logger.error(f"Failed to get datastore status: {e}")
            return None
