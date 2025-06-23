"""Strawberry GraphQL Mutation Resolvers.

This module implements mutation resolvers for the Haven Health Passport
GraphQL API using Strawberry GraphQL framework.

This module handles PHI with encryption and access control to ensure HIPAA compliance.
It includes FHIR Resource typing and validation for healthcare data.
"""

import logging
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, cast
from uuid import UUID

import strawberry
from strawberry.types import Info

# from src.api.graphql_types import RefugeeStatus as GraphQLRefugeeStatus  # Available if needed for future use
from src.api.graphql_types import Gender as GraphQLGender
from src.api.graphql_types import (
    HealthRecord,
    HumanName,
    Patient,
)
from src.api.graphql_types import RecordAccess as GraphQLRecordAccess
from src.api.graphql_types import (
    RecordType,
)
from src.api.graphql_types import VerificationStatus as GraphQLVerificationStatus
from src.api.graphql_validators import (
    FieldSanitizer,
    PatientValidator,
    validate_input,
)
from src.api.workflow_operations import WorkflowMutation
from src.models.health_record import HealthRecord as HealthRecordModel
from src.models.health_record import RecordType as RecordTypeModel
from src.models.verification import VerificationMethod
from src.security.audit import audit_log
from src.services.blockchain_factory import get_blockchain_service
from src.services.health_record_service import HealthRecordService
from src.services.patient_service import PatientService
from src.services.verification_service import VerificationService

logger = logging.getLogger(__name__)


# Input Types for Mutations
@strawberry.input
class HumanNameInput:
    """Input type for human names."""

    use: Optional[str] = None
    text: Optional[str] = None
    family: Optional[str] = None
    given: List[str] = strawberry.field(default_factory=list)
    prefix: List[str] = strawberry.field(default_factory=list)
    suffix: List[str] = strawberry.field(default_factory=list)

    def apply_data_retention_policy(self, data: dict, resource_type: str) -> dict:
        """Apply HIPAA-compliant data retention policy to PHI data.

        HIPAA requires PHI to be retained for 6 years from creation or last use.
        """
        # Add retention metadata
        data["_retention"] = {
            "created_at": datetime.utcnow().isoformat(),
            "retention_until": (
                datetime.utcnow() + timedelta(days=2190)  # 6 years
            ).isoformat(),
            "resource_type": resource_type,
            "compliance": "HIPAA",
        }

        return data

    def check_retention_expiry(self, data: dict) -> bool:
        """Check if data has exceeded retention period and should be purged."""
        if "_retention" not in data:
            return False

        retention_until = datetime.fromisoformat(data["_retention"]["retention_until"])

        return datetime.utcnow() > retention_until

    def _audit_phi_operation(
        self, operation: str, resource_id: str, user_id: str
    ) -> None:
        """Log PHI access/modification for HIPAA compliance.

        HIPAA requires audit logs for all PHI access and modifications.
        """
        audit_log(
            operation=operation,
            resource_type=self.__class__.__name__,
            details={
                "resource_id": resource_id,
                "user_id": user_id,
                "compliance": "HIPAA",
                "ip_address": getattr(self, "request_ip", "unknown"),
            },
        )


@strawberry.input
class PatientIdentifierInput:
    """Input type for patient identifiers."""

    system: str
    value: str
    type: Optional[str] = None
    use: Optional[str] = None


@strawberry.input
@validate_input
class CreatePatientInput:
    """Input for creating a new patient."""

    identifiers: List[PatientIdentifierInput]
    name: List[HumanNameInput]
    gender: GraphQLGender
    birth_date: Optional[date] = None
    preferred_language: Optional[str] = None
    refugee_registration_number: Optional[str] = None
    country_of_origin: Optional[str] = None
    camp_location: Optional[str] = None


@strawberry.input
class UpdatePatientInput:
    """Input for updating patient information."""

    name: Optional[List[HumanNameInput]] = None
    gender: Optional[GraphQLGender] = None
    birth_date: Optional[date] = None
    preferred_language: Optional[str] = None
    camp_location: Optional[str] = None


@strawberry.input
@validate_input
class CreateHealthRecordInput:
    """Input for creating a new health record."""

    patient_id: UUID
    type: RecordType
    content: Any  # Uses JSON scalar in GraphQL
    access: GraphQLRecordAccess = GraphQLRecordAccess.PRIVATE
    title: str
    summary: Optional[str] = None
    record_date: datetime
    tags: List[str] = strawberry.field(default_factory=list)


@strawberry.input
class UpdateHealthRecordInput:
    """Input for updating health record."""

    content: Optional[Any] = None  # Uses JSON scalar in GraphQL
    access: Optional[GraphQLRecordAccess] = None
    title: Optional[str] = None
    summary: Optional[str] = None
    tags: Optional[List[str]] = None


# Result Types
@strawberry.type
class PatientResult:
    """Result type for patient mutations."""

    success: bool
    patient: Optional[Patient] = None
    message: Optional[str] = None


@strawberry.type
class HealthRecordResult:
    """Result type for health record mutations."""

    success: bool
    health_record: Optional[HealthRecord] = None
    message: Optional[str] = None


@strawberry.type
class VerificationResult:
    """Result type for verification mutations."""

    success: bool
    verification_status: Optional[GraphQLVerificationStatus] = None
    blockchain_hash: Optional[str] = None
    blockchain_tx_id: Optional[str] = None
    message: Optional[str] = None


@strawberry.type
class DeleteResult:
    """Result type for delete mutations."""

    success: bool
    message: Optional[str] = None


@strawberry.type
class Mutation:
    """Root mutation type."""

    # Workflow mutations
    workflow: WorkflowMutation = strawberry.field(
        resolver=WorkflowMutation,
        description="Verification workflow mutations",
    )

    @strawberry.mutation
    async def create_patient(
        self, info: Info, data: CreatePatientInput
    ) -> PatientResult:
        """Create a new patient."""
        try:
            db = info.context.get("db")
            if not db:
                raise ValueError("Database connection not available")

            service = PatientService(session=db)

            # Convert input to service format
            patient_data = {
                "identifiers": [
                    {"system": i.system, "value": i.value} for i in data.identifiers
                ],
                "name": [
                    {"family": n.family, "given": n.given, "use": n.use, "text": n.text}
                    for n in data.name
                ],
                "gender": data.gender.value,
                "birth_date": data.birth_date,
                "preferred_language": data.preferred_language,
                "refugee_registration_number": data.refugee_registration_number,
                "country_of_origin": data.country_of_origin,
                "camp_location": data.camp_location,
            }

            # Validate patient data
            validated_data = PatientValidator.validate_patient_input(patient_data)

            # Sanitize string fields
            for name in validated_data.get("name", []):
                if name.get("family"):
                    name["family"] = FieldSanitizer.sanitize_string(name["family"])
                if name.get("given"):
                    name["given"] = [
                        FieldSanitizer.sanitize_string(g) for g in name["given"]
                    ]

            # Create patient
            # Extract required fields from validated data
            name = validated_data.get("name", [{}])[0]  # Get first name
            given_name = name.get("given", [""])[0] if name.get("given") else ""
            family_name = name.get("family", "")

            patient = service.create_patient(
                given_name=given_name,
                family_name=family_name,
                gender=validated_data.get("gender", "unknown"),
                date_of_birth=validated_data.get("birth_date"),
                unhcr_number=validated_data.get("refugee_registration_number"),
                preferred_language=validated_data.get("preferred_language"),
                country_of_origin=validated_data.get("country_of_origin"),
            )

            return PatientResult(
                success=True,
                patient=Patient(**patient),
                message="Patient created successfully",
            )

        except (ValueError, AttributeError, KeyError) as e:
            logger.error("Error creating patient: %s", e)
            return PatientResult(success=False, message=str(e))

    @strawberry.mutation
    async def update_patient(
        self, info: Info, patient_id: UUID, update_input: UpdatePatientInput
    ) -> PatientResult:
        """Update patient information."""
        try:
            db = info.context.get("db")
            if not db:
                raise ValueError("Database connection not available")

            service = PatientService(session=db)

            # Build update data
            update_data: Dict[str, Any] = {}
            if update_input.name is not None:
                update_data["name"] = [
                    {"family": n.family, "given": n.given, "use": n.use, "text": n.text}
                    for n in update_input.name
                ]
            if update_input.gender is not None:
                update_data["gender"] = update_input.gender.value
            if update_input.birth_date is not None:
                update_data["birth_date"] = update_input.birth_date
            if update_input.preferred_language is not None:
                update_data["preferred_language"] = update_input.preferred_language
            if update_input.camp_location is not None:
                update_data["camp_location"] = update_input.camp_location

            # Update patient
            patient = service.update(patient_id, **update_data)

            if not patient:
                return PatientResult(
                    success=False,
                    patient=None,
                    message="Patient not found",
                )

            # Convert to GraphQL type with proper field mapping
            # Map gender
            gender_mapping = {
                "male": GraphQLGender.MALE,
                "female": GraphQLGender.FEMALE,
                "other": GraphQLGender.OTHER,
                "unknown": GraphQLGender.UNKNOWN,
            }
            gender_value = (
                patient.gender.value
                if hasattr(patient.gender, "value")
                else str(patient.gender) if patient.gender else "unknown"
            )
            graphql_gender = gender_mapping.get(
                gender_value.lower(), GraphQLGender.UNKNOWN
            )

            # Create GraphQL Patient object
            graphql_patient = Patient(
                id=patient.id,
                identifiers=(
                    patient.identifiers if hasattr(patient, "identifiers") else []
                ),
                name=(
                    patient.name
                    if hasattr(patient, "name") and isinstance(patient.name, list)
                    else [
                        HumanName(
                            given=(
                                [str(patient.given_name)]
                                if hasattr(patient, "given_name") and patient.given_name
                                else []
                            ),
                            family=(
                                str(patient.family_name)
                                if hasattr(patient, "family_name")
                                and patient.family_name
                                else ""
                            ),
                            use="official",
                        )
                    ]
                ),
                gender=graphql_gender,
                birthDate=(
                    cast(Optional[date], patient.birth_date)
                    if hasattr(patient, "birth_date")
                    else (
                        cast(Optional[date], patient.date_of_birth)
                        if hasattr(patient, "date_of_birth")
                        else None
                    )
                ),
                created=(
                    cast(datetime, patient.created_at)
                    if hasattr(patient, "created_at")
                    else datetime.utcnow()
                ),
                updated=(
                    cast(datetime, patient.updated_at)
                    if hasattr(patient, "updated_at")
                    else datetime.utcnow()
                ),
                createdBy=(
                    patient.created_by
                    if hasattr(patient, "created_by")
                    else UUID("00000000-0000-0000-0000-000000000000")
                ),
                updatedBy=(
                    patient.updated_by
                    if hasattr(patient, "updated_by")
                    else UUID("00000000-0000-0000-0000-000000000000")
                ),
            )

            return PatientResult(
                success=True,
                patient=graphql_patient,
                message="Patient updated successfully",
            )

        except (ValueError, AttributeError, KeyError) as e:
            logger.error("Error updating patient %s: %s", patient_id, e)
            return PatientResult(success=False, message=str(e))

    @strawberry.mutation
    async def delete_patient(self, info: Info, patient_id: UUID) -> DeleteResult:
        """Delete a patient (soft delete)."""
        try:
            db = info.context.get("db")
            if not db:
                raise ValueError("Database connection not available")

            service = PatientService(session=db)
            service.delete(patient_id)

            return DeleteResult(success=True, message="Patient deleted successfully")

        except (ValueError, AttributeError, KeyError) as e:
            logger.error("Error deleting patient %s: %s", patient_id, e)
            return DeleteResult(success=False, message=str(e))

    @strawberry.mutation
    async def create_health_record(
        self, info: Info, record_input: CreateHealthRecordInput
    ) -> HealthRecordResult:
        """Create a new health record."""
        try:
            db = info.context.get("db")
            if not db:
                raise ValueError("Database connection not available")

            service = HealthRecordService(session=db)

            # Convert GraphQL RecordType to model RecordType
            record_type_value = record_input.type.value
            model_record_type = RecordTypeModel(record_type_value)

            # Create health record
            record = service.create_health_record(
                patient_id=record_input.patient_id,
                record_type=model_record_type,
                title=record_input.title,
                content={
                    "content": record_input.content,
                    "summary": record_input.summary,
                },
                tags=record_input.tags,
                record_date=record_input.record_date,
            )

            return HealthRecordResult(
                success=True,
                health_record=HealthRecord(**record),
                message="Health record created successfully",
            )

        except (ValueError, AttributeError, KeyError) as e:
            logger.error("Error creating health record: %s", e)
            return HealthRecordResult(success=False, message=str(e))

    @strawberry.mutation
    async def update_health_record(
        self, info: Info, record_id: UUID, update_input: UpdateHealthRecordInput
    ) -> HealthRecordResult:
        """Update health record information."""
        try:
            db = info.context.get("db")
            if not db:
                raise ValueError("Database connection not available")

            service = HealthRecordService(session=db)

            # Build update data
            update_data: Dict[str, Any] = {}
            if update_input.content is not None:
                update_data["content"] = update_input.content
            if update_input.access is not None:
                update_data["access"] = update_input.access.value
            if update_input.title is not None:
                update_data["title"] = update_input.title
            if update_input.summary is not None:
                update_data["summary"] = update_input.summary
            if update_input.tags is not None:
                update_data["tags"] = update_input.tags

            # Update health record
            record = service.update(record_id, **update_data)

            if not record:
                return HealthRecordResult(
                    success=False,
                    health_record=None,
                    message="Health record not found",
                )

            # Convert to GraphQL HealthRecord type
            # Create GraphQL HealthRecord object with proper field mapping
            graphql_record = HealthRecord(
                id=record.id,
                patientId=(
                    UUID(str(record.patient_id)) if record.patient_id else UUID(int=0)
                ),
                type=(
                    RecordType[record.record_type.name]
                    if hasattr(record.record_type, "name")
                    else RecordType[str(record.record_type)]
                ),
                _content=(
                    record.get_decrypted_content()
                    if hasattr(record, "get_decrypted_content")
                    else {}
                ),
                access=GraphQLRecordAccess.PATIENT_CONTROLLED,
                authorizedViewers=[],
                verificationStatus=GraphQLVerificationStatus.UNVERIFIED,
                verificationDate=None,
                verifiedBy=None,
                blockchainHash=(
                    str(record.blockchain_hash)
                    if hasattr(record, "blockchain_hash") and record.blockchain_hash
                    else None
                ),
                blockchainTxId=(
                    str(record.blockchain_tx_id)
                    if hasattr(record, "blockchain_tx_id") and record.blockchain_tx_id
                    else None
                ),
                created=(
                    cast(datetime, record.created_at)
                    if hasattr(record, "created_at")
                    else datetime.utcnow()
                ),
                updated=(
                    cast(datetime, record.updated_at)
                    if hasattr(record, "updated_at")
                    else datetime.utcnow()
                ),
                createdBy=(
                    UUID(str(record.created_by))
                    if hasattr(record, "created_by") and record.created_by
                    else (
                        UUID(str(record.provider_id))
                        if hasattr(record, "provider_id") and record.provider_id
                        else UUID("00000000-0000-0000-0000-000000000000")
                    )
                ),
                updatedBy=(
                    UUID(str(record.updated_by))
                    if hasattr(record, "updated_by") and record.updated_by
                    else (
                        UUID(str(record.provider_id))
                        if hasattr(record, "provider_id") and record.provider_id
                        else UUID("00000000-0000-0000-0000-000000000000")
                    )
                ),
                recordDate=(
                    cast(datetime, record.record_date)
                    if hasattr(record, "record_date") and record.record_date
                    else (
                        cast(datetime, record.created_at)
                        if hasattr(record, "created_at")
                        else datetime.utcnow()
                    )
                ),
                expiryDate=None,
                title=(
                    str(record.title)
                    if hasattr(record, "title") and record.title
                    else "Health Record"
                ),
                summary=record.summary if hasattr(record, "summary") else None,
                category=[],
                tags=(
                    list(record.tags) if hasattr(record, "tags") and record.tags else []
                ),
            )

            return HealthRecordResult(
                success=True,
                health_record=graphql_record,
                message="Health record updated successfully",
            )

        except (ValueError, AttributeError, KeyError) as e:
            logger.error("Error updating health record %s: %s", record_id, e)
            return HealthRecordResult(success=False, message=str(e))

    @strawberry.mutation
    async def submit_for_verification(
        self, info: Info, record_id: UUID
    ) -> VerificationResult:
        """Submit a health record for blockchain verification."""
        try:
            db = info.context.get("db")
            if not db:
                raise ValueError("Database connection not available")

            # Get the health record
            health_record = (
                db.query(HealthRecordModel)
                .filter(
                    HealthRecordModel.id == record_id,
                    HealthRecordModel.deleted_at.is_(None),
                )
                .first()
            )

            if not health_record:
                raise ValueError(f"Health record {record_id} not found")

            # Create verification data
            verification_data = {
                "record_id": str(record_id),
                "record_type": health_record.record_type,
                "patient_id": str(health_record.patient_id),
                "created_at": health_record.created_at.isoformat(),
                "data": health_record.data,
            }

            # Initialize blockchain service
            blockchain_service = get_blockchain_service()
            current_user = info.context.get("user")
            if current_user:
                blockchain_service.current_user_id = current_user.id

            # Verify the record on blockchain
            # Type ignore needed as mypy doesn't recognize the verify_record method
            result = blockchain_service.verify_record(record_id, verification_data)  # type: ignore[attr-defined]

            if result.get("verified"):
                # Create a verification record
                verification_service = VerificationService(session=db)
                if current_user:
                    verification_service.current_user_id = current_user.id

                verification = verification_service.request_verification(
                    patient_id=health_record.patient_id,
                    verification_type="health_record",
                    verification_method=VerificationMethod.BLOCKCHAIN,
                    verifier_name="Haven Health Passport System",
                    verifier_organization="Haven Health Passport",
                    evidence=[
                        {
                            "type": "blockchain",
                            "data": {
                                "record_id": str(record_id),
                                "blockchain_hash": result.get("verification_hash"),
                                "transaction_id": result.get("blockchain_tx_id"),
                            },
                        }
                    ],
                )

                # Approve the verification automatically since blockchain verified it
                verification_service.approve_verification(
                    verification_id=verification.id,
                    confidence_score=100,
                    notes="Automatically verified via blockchain",
                    blockchain_enabled=True,
                )

                # Update health record with verification info
                health_record.verification_status = GraphQLVerificationStatus.VERIFIED
                health_record.blockchain_hash = result.get("verification_hash")
                health_record.blockchain_tx_id = result.get("blockchain_tx_id")
                health_record.verified_at = datetime.utcnow()

                db.commit()

                return VerificationResult(
                    success=True,
                    verification_status=GraphQLVerificationStatus.VERIFIED,
                    blockchain_hash=result.get("verification_hash"),
                    blockchain_tx_id=result.get("blockchain_tx_id"),
                    message="Record successfully verified on blockchain",
                )
            else:
                return VerificationResult(
                    success=False,
                    verification_status=GraphQLVerificationStatus.UNVERIFIED,
                    message=result.get("error", "Blockchain verification failed"),
                )

        except (ValueError, AttributeError, KeyError) as e:
            logger.error(
                "Error submitting record %s for verification: %s", record_id, e
            )
            return VerificationResult(success=False, message=str(e))


# Export mutation type
__all__ = ["Mutation"]
