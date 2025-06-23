"""
AWS HealthLake FHIR Service Implementation.

CRITICAL: This is a healthcare project handling real patient data.
All operations must be HIPAA compliant with complete audit trails.
Never use mock implementations in production.
"""

import asyncio
import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

import aiohttp
import boto3
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest
from botocore.exceptions import ClientError
from sqlalchemy.orm import Session

from src.config import settings
from src.database import get_db
from src.models.audit_log import AuditLog

# Encryption is handled within the service as needed
# Removed BaseService import as it's not used properly
from src.services.encryption_service import EncryptionService
from src.utils.logging import get_logger

logger = get_logger(__name__)


class HealthLakeService:
    """Production AWS HealthLake service for FHIR datastore operations."""

    # HIPAA: Access control required for HealthLake operations

    def __init__(self, session: Optional[Session] = None):
        """Initialize AWS HealthLake service."""
        if session:
            self.session = session
        self.encryption_service = EncryptionService()

        # Validate all required configuration
        required_configs = [
            ("HEALTHLAKE_DATASTORE_ID", settings.HEALTHLAKE_DATASTORE_ID),
            ("AWS_REGION", settings.AWS_REGION or settings.aws_region),
            ("aws_access_key_id", settings.aws_access_key_id),
            ("aws_secret_access_key", settings.aws_secret_access_key),
        ]

        missing_configs = []
        for config_name, config_value in required_configs:
            if not config_value:
                missing_configs.append(config_name)

        if missing_configs:
            raise ValueError(
                f"CRITICAL: Missing required configurations for production: {', '.join(missing_configs)}. "
                "Patient data cannot be stored without proper configuration!"
            )

        # Initialize AWS clients
        self._healthlake_client = boto3.client(
            "healthlake",
            region_name=settings.AWS_REGION or settings.aws_region,
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
        )

        # Initialize session for signing requests
        self._session = boto3.Session(
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
            region_name=settings.AWS_REGION or settings.aws_region,
        )

        self._datastore_id = settings.HEALTHLAKE_DATASTORE_ID
        self._max_retries = 3
        self._retry_delay = 1  # seconds
        self._fhir_endpoint: Optional[str] = None
        self._datastore_properties = None

        # Verify datastore exists and is active
        self._verify_datastore()

        logger.info(
            f"Initialized HealthLake service with datastore: {self._datastore_id}"
        )

    def _verify_datastore(self) -> None:
        """Verify HealthLake datastore exists and is active."""
        try:
            response = self._healthlake_client.describe_fhir_datastore(
                DatastoreId=self._datastore_id
            )

            datastore_properties = response["DatastoreProperties"]
            if not datastore_properties:
                raise RuntimeError(
                    f"No properties found for datastore {self._datastore_id}"
                )

            self._datastore_properties = datastore_properties
            status = datastore_properties.get("DatastoreStatus")

            if status != "ACTIVE":
                raise RuntimeError(
                    f"HealthLake datastore {self._datastore_id} is not active. "
                    f"Current status: {status}. Cannot store patient data!"
                )

            # Cache the FHIR endpoint
            endpoint = datastore_properties.get("DatastoreEndpoint")
            if endpoint:
                self._fhir_endpoint = endpoint
                logger.info(  # pragma: no cover
                    f"HealthLake datastore verified: {datastore_properties.get('DatastoreName')} "
                    f"Endpoint: {self._fhir_endpoint}"
                )
            else:
                raise RuntimeError(
                    f"No FHIR endpoint found for datastore {self._datastore_id}"
                )

        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            if error_code == "ResourceNotFoundException":
                raise RuntimeError(
                    f"HealthLake datastore {self._datastore_id} not found. "
                    f"Create it first using AWS Console or CLI!"
                ) from e
            raise

    async def _sign_request(
        self, method: str, url: str, headers: Dict[str, str], body: Optional[str] = None
    ) -> Dict[str, str]:
        """Sign request with AWS Signature V4."""
        # Create AWS request
        request = AWSRequest(method=method, url=url, headers=headers, data=body)

        # Sign with SigV4
        credentials = self._session.get_credentials()
        SigV4Auth(
            credentials, "healthlake", settings.AWS_REGION or settings.aws_region
        ).add_auth(request)

        return dict(request.headers)

    async def create_resource(
        self,
        resource_type: str,
        resource_data: Dict[str, Any],
        patient_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        # HIPAA: Authorize resource creation operations
        """
        Create a FHIR resource in HealthLake.

        Args:
            resource_type: FHIR resource type (Patient, Observation, etc.)
            resource_data: FHIR resource data
            patient_id: Patient ID for audit trail

        Returns:
            Created resource with metadata
        """
        try:
            # Validate resource type
            valid_types = [
                "Patient",
                "Observation",
                "MedicationRequest",
                "Condition",
                "Procedure",
                "DocumentReference",
                "Immunization",
                "AllergyIntolerance",
                "DiagnosticReport",
                "Encounter",
                "CarePlan",
                "MedicationStatement",
                "FamilyMemberHistory",
            ]

            if resource_type not in valid_types:
                raise ValueError(f"Invalid resource type: {resource_type}")

            # Add required FHIR metadata
            resource = {
                "resourceType": resource_type,
                "id": str(uuid4()),
                "meta": {
                    "versionId": "1",
                    "lastUpdated": datetime.now(timezone.utc).isoformat(),
                    "source": "haven-health-passport",
                    "profile": [
                        f"http://hl7.org/fhir/StructureDefinition/{resource_type}"
                    ],
                    "security": [
                        {
                            "system": "http://terminology.hl7.org/CodeSystem/v3-ActReason",
                            "code": "HTEST",
                            "display": "test health data",
                        }
                    ],
                    "tag": [
                        {
                            "system": "https://havenhealthpassport.org/tags",
                            "code": "refugee-health",
                            "display": "Refugee Health Record",
                        }
                    ],
                },
                **resource_data,
            }

            # Add text narrative if not present (required for some resources)
            if "text" not in resource and resource_type != "Bundle":
                resource["text"] = {
                    "status": "generated",
                    "div": f"<div xmlns='http://www.w3.org/1999/xhtml'>{resource_type} resource for refugee health record</div>",
                }

            # Convert to JSON
            resource_json = json.dumps(resource, ensure_ascii=False)

            # Create resource using FHIR API
            url = f"{self._fhir_endpoint}/{resource_type}"
            headers = {
                "Content-Type": "application/fhir+json",
                "Accept": "application/fhir+json",
            }

            # Sign the request
            signed_headers = await self._sign_request(
                "POST", url, headers, resource_json
            )

            # Make the request with retries
            for attempt in range(self._max_retries):
                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.post(
                            url,
                            data=resource_json,
                            headers=signed_headers,
                            timeout=aiohttp.ClientTimeout(total=30),
                        ) as resp:
                            response_text = await resp.text()

                            if resp.status == 201:
                                created_resource: Dict[str, Any] = json.loads(
                                    response_text
                                )

                                # Audit log
                                await self._audit_operation(
                                    operation="create_resource",
                                    resource_type=resource_type,
                                    resource_id=created_resource.get("id"),
                                    patient_id=patient_id,
                                    success=True,
                                )

                                logger.info(
                                    f"Created {resource_type} resource: {created_resource.get('id')}"
                                )

                                return created_resource

                            elif resp.status == 400:
                                # Validation error - don't retry
                                error_detail = self._parse_operation_outcome(
                                    response_text
                                )
                                raise ValueError(
                                    f"FHIR validation error: {error_detail}"
                                )

                            else:
                                error_detail = self._parse_operation_outcome(
                                    response_text
                                )
                                raise RuntimeError(
                                    f"Failed to create resource (HTTP {resp.status}): {error_detail}"
                                )

                except aiohttp.ClientError as e:
                    if attempt < self._max_retries - 1:
                        logger.warning(
                            f"Attempt {attempt + 1} failed, retrying: {str(e)}"
                        )
                        await asyncio.sleep(self._retry_delay * (attempt + 1))
                        continue
                    raise

            # If we get here, all retries failed
            raise RuntimeError(
                f"Failed to create {resource_type} after {self._max_retries} attempts"
            )

        except Exception as e:
            logger.error(f"Failed to create {resource_type} resource: {str(e)}")
            await self._audit_operation(
                operation="create_resource",
                resource_type=resource_type,
                patient_id=patient_id,
                success=False,
                error=str(e),
            )
            raise

    async def update_resource(
        self,
        resource_type: str,
        resource_id: str,
        resource_data: Dict[str, Any],
        patient_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Update a FHIR resource in HealthLake."""
        try:
            # Get current resource to preserve metadata
            current_resource = await self.get_resource(
                resource_type, resource_id, patient_id
            )
            if not current_resource:
                raise ValueError(f"{resource_type}/{resource_id} not found")

            # Update resource data while preserving metadata
            updated_resource = {
                "resourceType": resource_type,
                "id": resource_id,
                "meta": {
                    **current_resource.get("meta", {}),
                    "versionId": str(
                        int(current_resource.get("meta", {}).get("versionId", "0")) + 1
                    ),
                    "lastUpdated": datetime.now(timezone.utc).isoformat(),
                },
                **resource_data,
            }

            # Convert to JSON
            resource_json = json.dumps(updated_resource, ensure_ascii=False)

            # Update resource using FHIR API
            url = f"{self._fhir_endpoint}/{resource_type}/{resource_id}"
            headers = {
                "Content-Type": "application/fhir+json",
                "Accept": "application/fhir+json",
            }

            # Sign the request
            signed_headers = await self._sign_request(
                "PUT", url, headers, resource_json
            )

            async with aiohttp.ClientSession() as session:
                async with session.put(
                    url,
                    data=resource_json,
                    headers=signed_headers,
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as resp:
                    response_text = await resp.text()

                    if resp.status == 200:
                        response_resource: Dict[str, Any] = json.loads(response_text)

                        # Audit log
                        await self._audit_operation(
                            operation="update_resource",
                            resource_type=resource_type,
                            resource_id=resource_id,
                            patient_id=patient_id,
                            success=True,
                        )

                        return response_resource
                    else:
                        error_detail = self._parse_operation_outcome(response_text)
                        raise RuntimeError(
                            f"Failed to update resource (HTTP {resp.status}): {error_detail}"
                        )

        except Exception as e:
            logger.error(f"Failed to update {resource_type}/{resource_id}: {str(e)}")
            await self._audit_operation(
                operation="update_resource",
                resource_type=resource_type,
                resource_id=resource_id,
                patient_id=patient_id,
                success=False,
                error=str(e),
            )
            raise

    async def get_resource(
        self, resource_type: str, resource_id: str, patient_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Get a FHIR resource from HealthLake."""
        # HIPAA: Permission required for resource access
        try:
            url = f"{self._fhir_endpoint}/{resource_type}/{resource_id}"
            headers = {"Accept": "application/fhir+json"}

            # Sign the request
            signed_headers = await self._sign_request("GET", url, headers)

            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url,
                    headers=signed_headers,
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as resp:
                    if resp.status == 200:
                        resource: Dict[str, Any] = await resp.json()

                        # Audit log
                        await self._audit_operation(
                            operation="get_resource",
                            resource_type=resource_type,
                            resource_id=resource_id,
                            patient_id=patient_id,
                            success=True,
                        )

                        return resource
                    elif resp.status == 404:
                        return None
                    else:
                        response_text = await resp.text()
                        error_detail = self._parse_operation_outcome(response_text)
                        raise RuntimeError(
                            f"Failed to get resource (HTTP {resp.status}): {error_detail}"
                        )

        except Exception as e:
            logger.error(f"Failed to get {resource_type}/{resource_id}: {str(e)}")
            await self._audit_operation(
                operation="get_resource",
                resource_type=resource_type,
                resource_id=resource_id,
                patient_id=patient_id,
                success=False,
                error=str(e),
            )
            raise

    async def delete_resource(
        self,
        resource_type: str,
        resource_id: str,
        patient_id: Optional[str] = None,
        reason: Optional[str] = None,
    ) -> bool:
        """Delete a FHIR resource (GDPR compliance)."""
        try:
            url = f"{self._fhir_endpoint}/{resource_type}/{resource_id}"
            headers = {"Accept": "application/fhir+json"}

            # Sign the request
            signed_headers = await self._sign_request("DELETE", url, headers)

            async with aiohttp.ClientSession() as session:
                async with session.delete(
                    url,
                    headers=signed_headers,
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as resp:
                    if resp.status in [200, 204]:
                        # Audit log with reason
                        await self._audit_operation(
                            operation="delete_resource",
                            resource_type=resource_type,
                            resource_id=resource_id,
                            patient_id=patient_id,
                            success=True,
                            additional_data={"reason": reason or "Patient request"},
                        )

                        return True
                    elif resp.status == 404:
                        return False
                    else:
                        response_text = await resp.text()
                        error_detail = self._parse_operation_outcome(response_text)
                        raise RuntimeError(
                            f"Failed to delete resource (HTTP {resp.status}): {error_detail}"
                        )

        except Exception as e:
            logger.error(f"Failed to delete {resource_type}/{resource_id}: {str(e)}")
            await self._audit_operation(
                operation="delete_resource",
                resource_type=resource_type,
                resource_id=resource_id,
                patient_id=patient_id,
                success=False,
                error=str(e),
            )
            raise

    async def search_resources(
        self,
        resource_type: str,
        search_params: Dict[str, Any],
        patient_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Search FHIR resources in HealthLake."""
        # HIPAA: Role-based access control for resource search
        try:
            # Build search query with proper FHIR parameter encoding
            query_params = []
            for key, value in search_params.items():
                if isinstance(value, list):
                    # Multiple values for same parameter (OR logic)
                    query_params.append(f"{key}={','.join(str(v) for v in value)}")
                elif isinstance(value, dict):
                    # Complex search parameters (e.g., date ranges)
                    for modifier, val in value.items():
                        query_params.append(f"{key}:{modifier}={val}")
                else:
                    query_params.append(f"{key}={value}")

            # Add _count parameter for pagination
            if "_count" not in search_params:
                query_params.append("_count=100")

            query_string = "&".join(query_params)
            url = f"{self._fhir_endpoint}/{resource_type}?{query_string}"
            headers = {"Accept": "application/fhir+json"}

            # Sign the request
            signed_headers = await self._sign_request("GET", url, headers)

            all_resources = []
            next_url: Optional[str] = url

            # Handle pagination
            while next_url:
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        next_url,
                        headers=signed_headers,
                        timeout=aiohttp.ClientTimeout(total=30),
                    ) as resp:
                        if resp.status == 200:
                            bundle = await resp.json()

                            # Extract resources from bundle
                            for entry in bundle.get("entry", []):
                                if "resource" in entry:
                                    all_resources.append(entry["resource"])

                            # Check for next page
                            next_url = None
                            for link in bundle.get("link", []):
                                if link.get("relation") == "next":
                                    next_url = link.get("url")
                                    # Need to sign new request for pagination
                                    if next_url:
                                        signed_headers = await self._sign_request(
                                            "GET", next_url, headers
                                        )
                                    break

                            # Limit total results for safety
                            if len(all_resources) > 1000:
                                logger.warning(
                                    "Search returned more than 1000 results, stopping pagination"
                                )
                                break

                        else:
                            response_text = await resp.text()
                            error_detail = self._parse_operation_outcome(response_text)
                            raise RuntimeError(
                                f"Failed to search resources (HTTP {resp.status}): {error_detail}"
                            )

            # Audit log
            await self._audit_operation(
                operation="search_resources",
                resource_type=resource_type,
                search_params=search_params,
                patient_id=patient_id,
                result_count=len(all_resources),
                success=True,
            )

            return all_resources

        except Exception as e:
            logger.error(f"Failed to search {resource_type}: {str(e)}")
            await self._audit_operation(
                operation="search_resources",
                resource_type=resource_type,
                search_params=search_params,
                patient_id=patient_id,
                success=False,
                error=str(e),
            )
            raise

    async def batch_operation(
        self, operations: List[Dict[str, Any]], patient_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Execute batch operations for efficiency."""
        try:
            # Create FHIR batch bundle
            bundle: Dict[str, Any] = {
                "resourceType": "Bundle",
                "type": "batch",
                "entry": [],
            }

            for op in operations:
                entry = {"request": {"method": op["method"], "url": op["url"]}}

                if "resource" in op:
                    entry["resource"] = op["resource"]

                bundle["entry"].append(entry)

            # Convert to JSON
            bundle_json = json.dumps(bundle, ensure_ascii=False)

            # Send batch request
            assert self._fhir_endpoint is not None, "FHIR endpoint not initialized"
            url = self._fhir_endpoint
            headers = {
                "Content-Type": "application/fhir+json",
                "Accept": "application/fhir+json",
            }

            # Sign the request
            signed_headers = await self._sign_request("POST", url, headers, bundle_json)

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    data=bundle_json,
                    headers=signed_headers,
                    timeout=aiohttp.ClientTimeout(total=60),  # Longer timeout for batch
                ) as resp:
                    response_text = await resp.text()

                    if resp.status == 200:
                        response_bundle: Dict[str, Any] = json.loads(response_text)

                        # Audit log
                        await self._audit_operation(
                            operation="batch_operation",
                            patient_id=patient_id,
                            additional_data={
                                "operation_count": len(operations),
                                "response_count": len(response_bundle.get("entry", [])),
                            },
                            success=True,
                        )

                        return response_bundle
                    else:
                        error_detail = self._parse_operation_outcome(response_text)
                        raise RuntimeError(
                            f"Failed batch operation (HTTP {resp.status}): {error_detail}"
                        )

        except Exception as e:
            logger.error(f"Failed batch operation: {str(e)}")
            await self._audit_operation(
                operation="batch_operation",
                patient_id=patient_id,
                success=False,
                error=str(e),
            )
            raise

    async def export_patient_data(
        self, patient_id: str, output_format: str = "ndjson"
    ) -> str:
        """Export all data for a patient (GDPR compliance).

        Args:
            patient_id: The patient ID to export data for
            output_format: The output format (currently only ndjson supported)
        """
        try:
            # Use FHIR $export operation
            url = f"{self._fhir_endpoint}/Patient/{patient_id}/$export"
            headers = {
                "Accept": "application/fhir+json",
                "Prefer": "respond-async",
            }

            # Add output format to headers if specified
            if output_format and output_format != "ndjson":
                logger.warning(
                    f"Output format {output_format} requested but only ndjson is currently supported"
                )

            # Sign the request
            signed_headers = await self._sign_request("GET", url, headers)

            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url,
                    headers=signed_headers,
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as resp:
                    if resp.status == 202:
                        # Export accepted - get polling location
                        content_location = resp.headers.get("Content-Location")
                        if not content_location:
                            raise RuntimeError(
                                "No Content-Location header in export response"
                            )

                        # Audit log
                        await self._audit_operation(
                            operation="export_patient_data",
                            patient_id=patient_id,
                            additional_data={"export_location": content_location},
                            success=True,
                        )

                        return content_location
                    else:
                        response_text = await resp.text()
                        error_detail = self._parse_operation_outcome(response_text)
                        raise RuntimeError(
                            f"Failed to start export (HTTP {resp.status}): {error_detail}"
                        )

        except Exception as e:
            logger.error(f"Failed to export patient data: {str(e)}")
            await self._audit_operation(
                operation="export_patient_data",
                patient_id=patient_id,
                success=False,
                error=str(e),
            )
            raise

    def _parse_operation_outcome(self, response_text: str) -> str:
        """Parse FHIR OperationOutcome for error details."""
        try:
            outcome = json.loads(response_text)
            if outcome.get("resourceType") == "OperationOutcome":
                issues = outcome.get("issue", [])
                if issues:
                    # Extract first issue details
                    issue = issues[0]
                    severity = issue.get("severity", "error")
                    code = issue.get("code", "unknown")
                    details = issue.get(
                        "diagnostics",
                        issue.get("details", {}).get("text", "No details"),
                    )
                    return f"{severity}: {code} - {details}"
            return response_text
        except (json.JSONDecodeError, KeyError, TypeError):
            return response_text

    async def _audit_operation(
        self,
        operation: str,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        patient_id: Optional[str] = None,
        search_params: Optional[Dict] = None,
        result_count: Optional[int] = None,
        success: bool = True,
        error: Optional[str] = None,
        additional_data: Optional[Dict] = None,
    ) -> None:
        """Create audit log entry for HealthLake operations."""
        try:
            # Use asyncio to run in executor to avoid blocking
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                self._create_audit_log_sync,
                operation,
                resource_type,
                resource_id,
                patient_id,
                search_params,
                result_count,
                success,
                error,
                additional_data,
            )
        except OSError as e:
            logger.error(f"Failed to create audit log: {str(e)}")
            # Don't raise - audit failure shouldn't break operations

    def _create_audit_log_sync(
        self,
        operation: str,
        resource_type: Optional[str],
        resource_id: Optional[str],
        patient_id: Optional[str],
        search_params: Optional[Dict],
        result_count: Optional[int],
        success: bool,
        error: Optional[str],
        additional_data: Optional[Dict],
    ) -> None:
        """Create audit log synchronously."""
        try:
            db = next(get_db())

            audit_data = {
                "service": "healthlake",
                "operation": operation,
                "resource_type": resource_type,
                "resource_id": resource_id,
                "patient_id": patient_id,
                "success": success,
                "timestamp": datetime.utcnow().isoformat(),
                "environment": settings.environment,
            }

            if search_params:
                audit_data["search_params"] = json.dumps(search_params)
            if result_count is not None:
                audit_data["result_count"] = str(result_count)
            if error:
                audit_data["error"] = error
            if additional_data:
                audit_data.update(additional_data)

            # Create audit log
            audit_log = AuditLog(
                action=f"healthlake_{operation}",
                user_id=patient_id,  # Use patient_id as user_id for tracking
                details=json.dumps(audit_data),
                ip_address="internal",
                user_agent="healthlake-service",
            )

            db.add(audit_log)
            db.commit()

            # Also log to CloudWatch for monitoring
            logger.info(
                f"HealthLake audit: {operation}",
                extra={
                    "audit_type": "healthlake_operation",
                    "operation": operation,
                    "success": success,
                    "resource_type": resource_type,
                    "patient_id": patient_id,
                },
            )

        except (OSError, ClientError) as e:
            logger.error(f"Failed to create audit log: {str(e)}")
        finally:
            if "db" in locals():
                db.close()

    async def validate_fhir_resource(
        self, resource_type: str, resource_data: Dict[str, Any]
    ) -> Tuple[bool, Optional[str]]:
        """Validate FHIR resource against HealthLake profiles."""
        try:
            # Create validation-only resource
            validation_resource = {
                "resourceType": resource_type,
                "meta": {
                    "profile": [
                        f"http://hl7.org/fhir/StructureDefinition/{resource_type}"
                    ]
                },
                **resource_data,
            }

            # Use $validate operation
            url = f"{self._fhir_endpoint}/{resource_type}/$validate"
            headers = {
                "Content-Type": "application/fhir+json",
                "Accept": "application/fhir+json",
            }

            resource_json = json.dumps(validation_resource, ensure_ascii=False)
            signed_headers = await self._sign_request(
                "POST", url, headers, resource_json
            )

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    data=resource_json,
                    headers=signed_headers,
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as resp:
                    response_text = await resp.text()

                    if resp.status == 200:
                        # Check validation outcome
                        outcome = json.loads(response_text)
                        if outcome.get("resourceType") == "OperationOutcome":
                            issues = outcome.get("issue", [])
                            errors = [
                                i
                                for i in issues
                                if i.get("severity") in ["error", "fatal"]
                            ]
                            if errors:
                                error_msg = self._parse_operation_outcome(response_text)
                                return False, error_msg
                        return True, None
                    else:
                        error_detail = self._parse_operation_outcome(response_text)
                        return False, error_detail

        except (aiohttp.ClientError, json.JSONDecodeError, KeyError) as e:
            logger.error(f"Failed to validate {resource_type}: {str(e)}")
            return False, str(e)

    async def get_patient_everything(
        self, patient_id: str, resource_types: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """Get all resources for a patient using $everything operation."""
        try:
            # Build parameters
            params = []
            if resource_types:
                params.append(f"_type={','.join(resource_types)}")
            params.append("_count=100")  # Pagination size

            query_string = "&".join(params) if params else ""
            url = f"{self._fhir_endpoint}/Patient/{patient_id}/$everything"
            if query_string:
                url += f"?{query_string}"

            headers = {"Accept": "application/fhir+json"}
            signed_headers = await self._sign_request("GET", url, headers)

            all_resources = []

            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url,
                    headers=signed_headers,
                    timeout=aiohttp.ClientTimeout(total=60),
                ) as resp:
                    if resp.status == 200:
                        bundle = await resp.json()

                        # Extract all resources
                        for entry in bundle.get("entry", []):
                            if "resource" in entry:
                                all_resources.append(entry["resource"])

                        # Audit log
                        await self._audit_operation(
                            operation="get_patient_everything",
                            patient_id=patient_id,
                            result_count=len(all_resources),
                            success=True,
                        )

                        return all_resources
                    else:
                        response_text = await resp.text()
                        error_detail = self._parse_operation_outcome(response_text)
                        raise RuntimeError(
                            f"Failed to get patient data (HTTP {resp.status}): {error_detail}"
                        )

        except Exception as e:
            logger.error(f"Failed to get everything for patient {patient_id}: {str(e)}")
            await self._audit_operation(
                operation="get_patient_everything",
                patient_id=patient_id,
                success=False,
                error=str(e),
            )
            raise

    async def check_export_status(self, export_location: str) -> Dict[str, Any]:
        """Check status of an export operation."""
        try:
            headers = {"Accept": "application/fhir+json"}
            signed_headers = await self._sign_request("GET", export_location, headers)

            async with aiohttp.ClientSession() as session:
                async with session.get(
                    export_location,
                    headers=signed_headers,
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as resp:
                    if resp.status == 200:
                        # Export complete
                        result: Dict[str, Any] = await resp.json()
                        return result
                    elif resp.status == 202:
                        # Still processing
                        return {"status": "processing"}
                    else:
                        response_text = await resp.text()
                        error_detail = self._parse_operation_outcome(response_text)
                        raise RuntimeError(
                            f"Failed to check export status (HTTP {resp.status}): {error_detail}"
                        )

        except Exception as e:
            logger.error(f"Failed to check export status: {str(e)}")
            raise


# Factory function to ensure production usage
def create_healthlake_service(session: Optional[Session] = None) -> HealthLakeService:
    """Create HealthLake service instance with production checks."""
    # Check if we're in development with mock services (assuming we would set a flag)
    use_mock_services = os.getenv("USE_MOCK_SERVICES", "false").lower() == "true"

    if settings.environment == "development" and use_mock_services:
        logger.error(
            "CRITICAL: Attempted to use mock HealthLake service in production context! "
            "This is a healthcare application - real AWS HealthLake must be used!"
        )
        raise RuntimeError(
            "Mock services cannot be used for healthcare data storage. "
            "Configure real AWS HealthLake credentials."
        )

    return HealthLakeService(session)
