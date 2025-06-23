# pylint: disable=too-many-lines
"""GraphQL Mutation Implementations.

This module implements the mutation resolvers for the Haven Health Passport
GraphQL API, providing data modification operations for patients, health records,
verifications, and related resources.

This module handles encrypted PHI with access control and audit logging
to ensure HIPAA compliance.
"""

import hashlib
import json
import random
import string
import uuid
from datetime import datetime
from typing import Any, List, Optional

try:
    import graphene
except ImportError:
    graphene = None

from src.core.database import get_db
from src.healthcare.regulatory.right_to_deletion_config import (
    DataCategory,
    RightToDeletionConfiguration,
)
from src.models.access_log import AccessContext
from src.models.health_record import RecordType
from src.models.patient import Gender as PatientGender
from src.models.patient import RefugeeStatus
from src.models.verification import VerificationMethod

# Import services
from src.services.access_control_service import AccessControlService
from src.services.health_record_service import HealthRecordService
from src.services.jurisdiction_service import JurisdictionService
from src.services.organization_service import OrganizationService
from src.services.patient_service import PatientService
from src.services.realtime_translation import get_realtime_translation_service
from src.services.translation_service import (
    TranslationContext,
    TranslationDirection,
    TranslationService,
    TranslationType,
)
from src.services.verification_service import VerificationService
from src.utils.logging import get_logger

from .common_types import (  # VerificationPayload,  # Available if needed for future use
    ClinicalDocumentTranslationPayload,
    ConversionPayload,
    FHIRTranslationPayload,
    SectionTranslationPayload,
    ValidationPayload,
)
from .inputs import (
    HealthRecordInput,
    HealthRecordUpdateInput,
    PatientInput,
    PatientUpdateInput,
)
from .scalars import DateTimeScalar, UUIDScalar
from .types import (  # , Verification  # Available if needed for future use
    AccessGrant,
    Error,
    FamilyGroup,
    HealthRecord,
    Patient,
)
from .verification_mutations import (
    ApproveVerification,
    RequestVerification,
    RevokeVerification,
    UpdateVerification,
)

logger = get_logger(__name__)


# Payload Types


class PatientPayload(graphene.ObjectType):
    """Payload for patient mutations."""

    patient = graphene.Field(Patient)
    errors = graphene.List(Error)


class HealthRecordPayload(graphene.ObjectType):
    """Payload for health record mutations."""

    health_record = graphene.Field(HealthRecord)
    errors = graphene.List(Error)


class FamilyGroupPayload(graphene.ObjectType):
    """Payload for family group mutations."""

    family_group = graphene.Field(FamilyGroup)
    errors = graphene.List(Error)


class AccessGrantPayload(graphene.ObjectType):
    """Payload for access grant mutations."""

    grant = graphene.Field(AccessGrant)
    errors = graphene.List(Error)


class AccessRevokePayload(graphene.ObjectType):
    """Payload for access revoke mutations."""

    success = graphene.Boolean(required=True)
    errors = graphene.List(Error)


class DeletePayload(graphene.ObjectType):
    """Payload for delete mutations."""

    success = graphene.Boolean(required=True)
    errors = graphene.List(Error)


class EmergencyAccessPayload(graphene.ObjectType):
    """Payload for emergency access mutations."""

    access_token = graphene.String()
    expires_at = graphene.Field(DateTimeScalar)
    errors = graphene.List(Error)


# Patient Mutations


class CreatePatient(graphene.Mutation):
    """Create a new patient record."""

    class Arguments:
        input = graphene.Argument(PatientInput, required=True)

    Output = PatientPayload

    def mutate(self, info: Any, patient_input: PatientInput) -> PatientPayload:
        """Create patient mutation resolver."""
        errors = []

        # Check permissions
        user = info.context.get("user")
        if not user or not user.has_permission("create:patients"):
            errors.append(
                Error(message="Unauthorized to create patients", code="UNAUTHORIZED")
            )
            return PatientPayload(patient=None, errors=errors)

        # Validate input
        validation_errors = self._validate_patient_input(patient_input)
        if validation_errors:
            return PatientPayload(patient=None, errors=validation_errors)

        try:
            with get_db() as db:
                # Create service with user context
                patient_service = PatientService(db)
                patient_service.set_user_context(user.id, user.role)
                patient_service.access_context = AccessContext.API

                # Extract primary name
                primary_name = next(
                    (n for n in patient_input.name if n.use == "official"),
                    patient_input.name[0],
                )

                # Map gender to enum
                gender = (
                    PatientGender[patient_input.gender.upper()]
                    if patient_input.gender
                    else PatientGender.UNKNOWN
                )

                # Extract contact info
                phone = None
                email = None
                if patient_input.telecom:
                    for contact in patient_input.telecom:
                        if contact.system == "phone" and not phone:
                            phone = contact.value
                        elif contact.system == "email" and not email:
                            email = contact.value

                # Extract address
                address_text = None
                if patient_input.address:
                    primary_address = patient_input.address[0]
                    address_parts = [
                        primary_address.line[0] if primary_address.line else None,
                        primary_address.city,
                        primary_address.state,
                        primary_address.postal_code,
                        primary_address.country,
                    ]
                    address_text = ", ".join(filter(None, address_parts))

                # Extract UNHCR number if provided
                unhcr_number = None
                if patient_input.identifiers:
                    for identifier in patient_input.identifiers:
                        if identifier.system == "http://unhcr.org/ids/registration":
                            unhcr_number = identifier.value
                            break

                # Create patient
                patient_model = patient_service.create_patient(
                    given_name=(
                        primary_name.given[0] if primary_name.given else "Unknown"
                    ),
                    family_name=primary_name.family or "Unknown",
                    gender=gender,
                    date_of_birth=patient_input.birth_date,
                    middle_names=(
                        " ".join(primary_name.given[1:])
                        if len(primary_name.given) > 1
                        else None
                    ),
                    phone_number=phone,
                    email=email,
                    current_address=address_text,
                    unhcr_number=unhcr_number,
                    refugee_status=(
                        RefugeeStatus[patient_input.refugee_status.upper()]
                        if patient_input.refugee_status
                        else None
                    ),
                    primary_language=(
                        patient_input.communication[0].language
                        if patient_input.communication
                        else None
                    ),
                    emergency_contact_name=(
                        patient_input.emergency_contacts[0].name
                        if patient_input.emergency_contacts
                        else None
                    ),
                    emergency_contact_phone=(
                        patient_input.emergency_contacts[0].phone
                        if patient_input.emergency_contacts
                        else None
                    ),
                    created_by_organization=user.organization,
                )

                # Generate HHP ID if not provided
                if not any(
                    id.system == "http://havenhealthpassport.org/fhir/sid/hhp-id"
                    for id in patient_input.identifiers or []
                ):
                    self._generate_hhp_id()
                    # Would store this as an identifier in a separate table in production

                # Convert to GraphQL type
                patient_data = {
                    "id": patient_model.id,
                    "identifiers": (
                        [
                            {
                                "system": "http://unhcr.org/ids/registration",
                                "value": patient_model.unhcr_number,
                                "is_primary": True,
                            }
                        ]
                        if patient_model.unhcr_number
                        else []
                    ),
                    "name": [
                        {
                            "use": "official",
                            "family": patient_model.family_name,
                            "given": [patient_model.given_name],
                        }
                    ],
                    "gender": patient_model.gender.value,
                    "birth_date": patient_model.date_of_birth,
                    "created": patient_model.created_at,
                    "updated": patient_model.updated_at,
                    "created_by": user.id,
                }

                patient = Patient(**patient_data)

                db.commit()
                return PatientPayload(patient=patient, errors=None)

        except ValueError as e:
            errors.append(Error(message=str(e), code="VALIDATION_ERROR"))
            return PatientPayload(patient=None, errors=errors)
        except (AttributeError, KeyError) as e:
            logger.error(f"Error creating patient: {e}")
            errors.append(
                Error(
                    message=f"Failed to create patient: {str(e)}", code="CREATE_FAILED"
                )
            )
            return PatientPayload(patient=None, errors=errors)

    def _validate_patient_input(self, patient_input: PatientInput) -> List[Error]:
        """Validate patient input data."""
        errors = []

        # Name validation
        if not patient_input.name or len(patient_input.name) == 0:
            errors.append(
                Error(
                    field="name",
                    message="At least one name is required",
                    code="REQUIRED_FIELD",
                )
            )

        # Gender validation
        if not patient_input.gender:
            errors.append(
                Error(
                    field="gender", message="Gender is required", code="REQUIRED_FIELD"
                )
            )

        # Birth date validation
        if (
            patient_input.birth_date
            and patient_input.birth_date > datetime.now().date()
        ):
            errors.append(
                Error(
                    field="birth_date",
                    message="Birth date cannot be in the future",
                    code="INVALID_DATE",
                )
            )

        # Identifier validation
        if patient_input.identifiers:
            for idx, identifier in enumerate(patient_input.identifiers):
                if not identifier.system or not identifier.value:
                    errors.append(
                        Error(
                            field=f"identifiers[{idx}]",
                            message="Identifier must have system and value",
                            code="INVALID_IDENTIFIER",
                        )
                    )

        return errors

    def _generate_hhp_id(self) -> str:
        """Generate a Haven Health Passport ID."""
        # In production, would use a proper ID generation service
        segments = []
        for _ in range(3):
            segment = "".join(
                random.choices(string.ascii_uppercase + string.digits, k=4)
            )
            segments.append(segment)

        return f"HHP-{'-'.join(segments)}"

    def _log_patient_action(
        self, info: Any, patient_id: uuid.UUID, action: str
    ) -> None:
        """Log patient-related actions."""
        # In production, would create audit log entry
        _ = (info, patient_id, action)  # Mark as used


class UpdatePatient(graphene.Mutation):
    """Update an existing patient record."""

    class Arguments:
        id = graphene.Argument(UUIDScalar, required=True)
        input = graphene.Argument(PatientUpdateInput, required=True)

    Output = PatientPayload

    def mutate(
        self, info: Any, patient_id: uuid.UUID, patient_input: PatientUpdateInput
    ) -> PatientPayload:
        """Update patient mutation resolver."""
        errors = []

        # Check permissions
        user = info.context.get("user")
        if not user or not user.has_permission("update:patients"):
            errors.append(
                Error(message="Unauthorized to update patients", code="UNAUTHORIZED")
            )
            return PatientPayload(patient=None, errors=errors)

        # Check if user can access this patient
        if not self._can_access_patient(user, patient_id):
            errors.append(
                Error(message="Access denied to patient record", code="ACCESS_DENIED")
            )
            return PatientPayload(patient=None, errors=errors)

        try:
            with get_db() as db:
                # Create service with user context
                patient_service = PatientService(db)
                patient_service.set_user_context(user.id, user.role)
                patient_service.access_context = AccessContext.API

                # Get existing patient
                existing_patient = patient_service.get_by_id(patient_id)
                if not existing_patient:
                    errors.append(Error(message="Patient not found", code="NOT_FOUND"))
                    return PatientPayload(patient=None, errors=errors)

                # Prepare update data
                update_data = {}

                # Update demographics if provided
                if patient_input.name:
                    primary_name = next(
                        (n for n in patient_input.name if n.use == "official"),
                        patient_input.name[0],
                    )
                    if primary_name.given:
                        update_data["given_name"] = primary_name.given[0]
                    if primary_name.family:
                        update_data["family_name"] = primary_name.family

                if patient_input.gender:
                    update_data["gender"] = PatientGender[patient_input.gender.upper()]

                if patient_input.birth_date is not None:
                    update_data["date_of_birth"] = patient_input.birth_date

                if patient_input.telecom:
                    for contact in patient_input.telecom:
                        if contact.system == "phone":
                            update_data["phone_number"] = contact.value
                        elif contact.system == "email":
                            update_data["email"] = contact.value

                if patient_input.address:
                    primary_address = patient_input.address[0]
                    address_parts = [
                        primary_address.line[0] if primary_address.line else None,
                        primary_address.city,
                        primary_address.state,
                        primary_address.postal_code,
                        primary_address.country,
                    ]
                    update_data["current_address"] = ", ".join(
                        filter(None, address_parts)
                    )

                # Update patient
                updated_patient = patient_service.update(patient_id, **update_data)

                if not updated_patient:
                    raise ValueError("Failed to update patient")

                # Convert to GraphQL type
                patient_data = {
                    "id": updated_patient.id,
                    "identifiers": (
                        [
                            {
                                "system": "http://unhcr.org/ids/registration",
                                "value": updated_patient.unhcr_number,
                                "is_primary": True,
                            }
                        ]
                        if updated_patient.unhcr_number
                        else []
                    ),
                    "name": [
                        {
                            "use": "official",
                            "family": updated_patient.family_name,
                            "given": [updated_patient.given_name],
                        }
                    ],
                    "gender": updated_patient.gender.value,
                    "birth_date": updated_patient.date_of_birth,
                    "created": updated_patient.created_at,
                    "updated": updated_patient.updated_at,
                }

                patient = Patient(**patient_data)

                db.commit()
                return PatientPayload(patient=patient, errors=None)

        except (ValueError, AttributeError, KeyError) as e:
            logger.error(f"Error updating patient: {e}")
            errors.append(
                Error(
                    message=f"Failed to update patient: {str(e)}", code="UPDATE_FAILED"
                )
            )
            return PatientPayload(patient=None, errors=errors)

    def _can_access_patient(self, user: Any, patient_id: uuid.UUID) -> bool:
        """Check if user can access patient."""
        # Check if user is the patient
        if hasattr(user, "patient_id") and str(user.patient_id) == str(patient_id):
            return True

        # Check if user is a provider with access
        if user.has_permission("read:patients"):
            # Implement provider-patient relationship check

            # Access db from class context
            db = getattr(self, "db", None) or globals().get("db")
            if db:
                access_service = AccessControlService(db=db)

                # Check if provider has been granted access to this patient
                has_provider_access = access_service.check_provider_patient_access(
                    provider_id=user.id, patient_id=str(patient_id)
                )

                if has_provider_access:
                    logger.info(
                        f"Provider {user.id} authorized to access patient {patient_id}"
                    )
                    return True
                else:
                    logger.warning(
                        f"Provider {user.id} denied access to patient {patient_id} - no relationship"
                    )
                    return False

        # Check if user is part of an organization with access
        if hasattr(user, "organization_id") and user.organization_id:
            # Implement organization-patient relationship check

            # Access db from class context
            db = getattr(self, "db", None) or globals().get("db")
            if db:
                org_service = OrganizationService(db=db)

                # Check if organization has been granted access to this patient
                has_org_access = org_service.check_organization_patient_access(
                    organization_id=user.organization_id, patient_id=str(patient_id)
                )

                if has_org_access:
                    logger.info(
                        f"User {user.id} authorized via organization {user.organization_id}"
                    )
                    return True
                else:
                    logger.warning(
                        f"User {user.id} from organization {user.organization_id} denied access "
                        f"to patient {patient_id} - no organizational relationship"
                    )
                    return False

        return False


class DeletePatient(graphene.Mutation):
    """Delete a patient record (soft delete)."""

    class Arguments:
        patient_id = graphene.Argument(UUIDScalar, required=True)

    Output = DeletePayload

    def mutate(self, info: Any, patient_id: uuid.UUID) -> DeletePayload:
        """Delete patient mutation resolver with retention policy compliance."""
        errors = []

        # Check permissions
        user = info.context.get("user")
        if not user or not user.has_permission("delete:patients"):
            errors.append(
                Error(message="Unauthorized to delete patients", code="UNAUTHORIZED")
            )
            return DeletePayload(success=False, errors=errors)

        try:
            with get_db() as db:
                # Create service with user context
                patient_service = PatientService(db)
                patient_service.set_user_context(user.id, user.role)
                patient_service.access_context = AccessContext.API

                # Check retention policy before deletion
                retention_config = RightToDeletionConfiguration()

                # Get patient details for retention check
                patient = patient_service.get_patient_with_records(patient_id)
                if not patient:
                    errors.append(Error(message="Patient not found", code="NOT_FOUND"))
                    return DeletePayload(success=False, errors=errors)

                # Check retention requirements
                # Get jurisdiction from patient location

                jurisdiction_service = JurisdictionService(db=db)
                jurisdiction = jurisdiction_service.get_patient_jurisdiction(
                    str(patient_id)
                )

                retention_period = retention_config.check_retention_requirement(
                    category=DataCategory.MEDICAL_HISTORY,
                    jurisdiction=jurisdiction,
                    patient_age=patient.age if hasattr(patient, "age") else None,
                )

                if retention_period:
                    # Archive instead of delete if retention required
                    logger.info(
                        f"Archiving patient {patient_id} due to retention policy: {retention_period}"
                    )
                    # TODO: Implement archive method in PatientService
                    # success = patient_service.archive(patient_id)
                    success = False  # Placeholder until archive is implemented
                    if success:
                        db.commit()
                        return DeletePayload(
                            success=True,
                            errors=[
                                Error(
                                    message=f"Patient archived due to {retention_period} retention requirement",
                                    code="ARCHIVED_FOR_RETENTION",
                                )
                            ],
                        )
                else:
                    # Perform compliant deletion
                    success = patient_service.delete(patient_id, hard=False)
                    if success:
                        db.commit()
                        return DeletePayload(success=True, errors=None)

                errors.append(
                    Error(message="Failed to process deletion", code="DELETE_FAILED")
                )
                return DeletePayload(success=False, errors=errors)

        except (ValueError, AttributeError) as e:
            logger.error(f"Error deleting patient: {e}")
            errors.append(
                Error(
                    message=f"Failed to delete patient: {str(e)}", code="DELETE_FAILED"
                )
            )
            return DeletePayload(success=False, errors=errors)

    def _log_patient_action(
        self, info: Any, patient_id: uuid.UUID, action: str
    ) -> None:
        """Log patient-related actions."""
        # In production, would create audit log entry
        _ = info  # Mark as used
        logger.info(f"Patient action: {action} on patient {patient_id}")


class MergePatients(graphene.Mutation):
    """Merge duplicate patient records."""

    class Arguments:
        primary_id = graphene.Argument(UUIDScalar, required=True)
        merge_ids = graphene.List(UUIDScalar, required=True)

    Output = PatientPayload

    def mutate(
        self, info: Any, primary_id: uuid.UUID, merge_ids: List[uuid.UUID]
    ) -> PatientPayload:
        """Merge patients mutation resolver."""
        errors = []

        # Check permissions
        user = info.context.get("user")
        if not user or not user.has_permission("merge:patients"):
            errors.append(
                Error(message="Unauthorized to merge patients", code="UNAUTHORIZED")
            )
            return PatientPayload(patient=None, errors=errors)

        # Validate merge request
        if primary_id in merge_ids:
            errors.append(
                Error(
                    message="Primary patient cannot be in merge list",
                    code="INVALID_MERGE",
                )
            )
            return PatientPayload(patient=None, errors=errors)

        if len(merge_ids) == 0:
            errors.append(
                Error(
                    message="At least one patient ID required for merge",
                    code="INVALID_MERGE",
                )
            )
            return PatientPayload(patient=None, errors=errors)

        try:
            with get_db() as db:
                # Create service with user context
                patient_service = PatientService(db)
                patient_service.set_user_context(user.id, user.role)
                patient_service.access_context = AccessContext.API

                # Merge patients one by one
                merged_patient = None
                for merge_id in merge_ids:
                    merged_patient = patient_service.merge_patients(
                        primary_patient_id=primary_id,
                        duplicate_patient_id=merge_id,
                        merge_strategy="primary_wins",
                    )
                    if not merged_patient:
                        raise ValueError(f"Failed to merge patient {merge_id}")

                if not merged_patient:
                    raise ValueError("No patients were merged")

                # Convert to GraphQL type
                patient_data = {
                    "id": merged_patient.id,
                    "identifiers": (
                        [
                            {
                                "system": "http://unhcr.org/ids/registration",
                                "value": merged_patient.unhcr_number,
                                "is_primary": True,
                            }
                        ]
                        if merged_patient.unhcr_number
                        else []
                    ),
                    "name": [
                        {
                            "use": "official",
                            "family": merged_patient.family_name,
                            "given": [merged_patient.given_name],
                        }
                    ],
                    "gender": merged_patient.gender.value,
                    "birth_date": merged_patient.date_of_birth,
                    "created": merged_patient.created_at,
                    "updated": merged_patient.updated_at,
                }

                patient = Patient(**patient_data)

                db.commit()
                return PatientPayload(patient=patient, errors=None)

        except (ValueError, AttributeError) as e:
            logger.error(f"Error merging patients: {e}")
            errors.append(
                Error(
                    message=f"Failed to merge patients: {str(e)}", code="MERGE_FAILED"
                )
            )
            return PatientPayload(patient=None, errors=errors)

    def _log_merge_operation(
        self, info: Any, primary_id: uuid.UUID, merge_ids: List[uuid.UUID]
    ) -> None:
        """Log patient merge operation."""
        # In production, would create detailed audit log
        _ = info  # Mark as used
        logger.info(f"Merge operation: primary={primary_id}, merged={merge_ids}")


# Health Record Mutations


class CreateHealthRecord(graphene.Mutation):
    """Create a new health record."""

    class Arguments:
        record_input = graphene.Argument(HealthRecordInput, required=True)

    Output = HealthRecordPayload

    def mutate(self, info: Any, record_input: HealthRecordInput) -> HealthRecordPayload:
        """Create health record mutation resolver."""
        errors = []

        # Check permissions
        user = info.context.get("user")
        if not user or not user.has_permission("create:health_records"):
            errors.append(
                Error(
                    message="Unauthorized to create health records", code="UNAUTHORIZED"
                )
            )
            return HealthRecordPayload(health_record=None, errors=errors)

        # Check patient access
        if not self._can_access_patient(user, record_input.patient_id):
            errors.append(
                Error(message="Access denied to patient records", code="ACCESS_DENIED")
            )
            return HealthRecordPayload(health_record=None, errors=errors)

        # Validate input
        validation_errors = self._validate_health_record_input(record_input)
        if validation_errors:
            return HealthRecordPayload(health_record=None, errors=validation_errors)

        try:
            with get_db() as db:
                # Create service with user context
                health_record_service = HealthRecordService(db)
                health_record_service.set_user_context(user.id, user.role)
                health_record_service.access_context = AccessContext.API

                # Map record type
                record_type_map = {
                    "observation": RecordType.VITAL_SIGNS,
                    "medication": RecordType.MEDICATION,
                    "procedure": RecordType.PROCEDURE,
                    "diagnostic-report": RecordType.LAB_RESULT,
                    "immunization": RecordType.IMMUNIZATION,
                    "allergy": RecordType.ALLERGY,
                    "condition": RecordType.DIAGNOSIS,
                    "encounter": RecordType.CLINICAL_NOTE,
                    "document": RecordType.CLINICAL_NOTE,
                }
                record_type = record_type_map.get(
                    record_input.type, RecordType.CLINICAL_NOTE
                )

                # Create health record
                record = health_record_service.create_health_record(
                    patient_id=record_input.patient_id,
                    record_type=record_type,
                    title=record_input.type.replace("-", " ").title(),
                    content=record_input.resource,
                    provider_name=(
                        user.name if hasattr(user, "name") else "Healthcare Provider"
                    ),
                    facility_name=(
                        record_input.facility_name
                        if hasattr(record_input, "facility_name")
                        else None
                    ),
                    access_level=record_input.access_level or "standard",
                    emergency_accessible=True,
                )

                # Auto-request verification for certain record types
                if record_input.type in ["diagnostic-report", "procedure"]:
                    verification_service = VerificationService(db)
                    verification_service.set_user_context(user.id, user.role)
                    verification_service.request_verification(
                        patient_id=record_input.patient_id,
                        verification_type="health_record",
                        verification_method=VerificationMethod.MEDICAL_PROFESSIONAL,
                        verifier_name=(
                            user.name
                            if hasattr(user, "name")
                            else "Healthcare Provider"
                        ),
                        evidence=[
                            {
                                "type": "health_record",
                                "data": {
                                    "record_id": str(record.id),
                                    "record_type": record_input.type,
                                },
                            }
                        ],
                    )

                # Convert to GraphQL type
                health_record_data = {
                    "id": record.id,
                    "patient_id": record.patient_id,
                    "type": record.record_type.value,
                    "title": record.title,
                    "date": record.record_date,
                    "status": record.status.value,
                    "verified": record.is_verified,
                    "created": record.created_at,
                    "updated": record.updated_at,
                    "created_by": user.id,
                }

                health_record = HealthRecord(**health_record_data)

                db.commit()
                return HealthRecordPayload(health_record=health_record, errors=None)

        except (ValueError, AttributeError) as e:
            logger.error(f"Error creating health record: {e}")
            errors.append(
                Error(
                    message=f"Failed to create health record: {str(e)}",
                    code="CREATE_FAILED",
                )
            )
            return HealthRecordPayload(health_record=None, errors=errors)

    def _can_access_patient(self, user: Any, patient_id: uuid.UUID) -> bool:
        """Check if user can access patient."""
        # Check if user is the patient
        if hasattr(user, "patient_id") and str(user.patient_id) == str(patient_id):
            return True

        # Check if user is a provider with access
        if user.has_permission("read:patients"):
            # Implement provider-patient relationship check

            # Access db from class context
            db = getattr(self, "db", None) or globals().get("db")
            if db:
                access_service = AccessControlService(db=db)

                # Check if provider has been granted access to this patient
                has_provider_access = access_service.check_provider_patient_access(
                    provider_id=user.id, patient_id=str(patient_id)
                )

                if has_provider_access:
                    logger.info(
                        f"Provider {user.id} authorized to access patient {patient_id}"
                    )
                    return True
                else:
                    logger.warning(
                        f"Provider {user.id} denied access to patient {patient_id} - no relationship"
                    )
                    return False

        # Check if user is part of an organization with access
        if hasattr(user, "organization_id") and user.organization_id:
            # Implement organization-patient relationship check

            # Access db from class context
            db = getattr(self, "db", None) or globals().get("db")
            if db:
                org_service = OrganizationService(db=db)

                # Check if organization has been granted access to this patient
                has_org_access = org_service.check_organization_patient_access(
                    organization_id=user.organization_id, patient_id=str(patient_id)
                )

                if has_org_access:
                    logger.info(
                        f"User {user.id} authorized via organization {user.organization_id}"
                    )
                    return True
                else:
                    logger.warning(
                        f"User {user.id} from organization {user.organization_id} denied access "
                        f"to patient {patient_id} - no organizational relationship"
                    )
                    return False

        return False

    def _validate_health_record_input(
        self, record_input: HealthRecordInput
    ) -> List[Error]:
        """Validate health record input."""
        errors = []

        # Type validation
        valid_types = [
            "observation",
            "medication",
            "procedure",
            "diagnostic-report",
            "immunization",
            "allergy",
            "condition",
            "encounter",
            "document",
        ]
        if record_input.type not in valid_types:
            errors.append(
                Error(
                    field="type",
                    message=f"Invalid record type: {record_input.type}",
                    code="INVALID_TYPE",
                )
            )

        # Resource validation
        if not record_input.resource:
            errors.append(
                Error(
                    field="resource",
                    message="Resource data is required",
                    code="REQUIRED_FIELD",
                )
            )

        # Resource type validation
        if not record_input.resource_type:
            errors.append(
                Error(
                    field="resource_type",
                    message="Resource type is required",
                    code="REQUIRED_FIELD",
                )
            )

        return errors


class UpdateHealthRecord(graphene.Mutation):
    """Update an existing health record."""

    class Arguments:
        record_id = graphene.Argument(UUIDScalar, required=True)
        record_input = graphene.Argument(HealthRecordUpdateInput, required=True)

    Output = HealthRecordPayload

    def mutate(
        self, info: Any, record_id: uuid.UUID, record_input: HealthRecordUpdateInput
    ) -> HealthRecordPayload:
        """Update health record mutation resolver."""
        errors = []

        # Check permissions
        user = info.context.get("user")
        if not user or not user.has_permission("update:health_records"):
            errors.append(
                Error(
                    message="Unauthorized to update health records", code="UNAUTHORIZED"
                )
            )
            return HealthRecordPayload(health_record=None, errors=errors)

        try:
            with get_db() as db:
                # Create service with user context
                health_record_service = HealthRecordService(db)
                health_record_service.set_user_context(user.id, user.role)
                health_record_service.access_context = AccessContext.API

                # Get existing record to check access
                existing_record = health_record_service.get_by_id(record_id)
                if not existing_record:
                    errors.append(
                        Error(message="Health record not found", code="NOT_FOUND")
                    )
                    return HealthRecordPayload(health_record=None, errors=errors)

                # Check access to patient
                if not self._can_access_patient(user, existing_record.patient_id):
                    errors.append(
                        Error(
                            message="Access denied to patient records",
                            code="ACCESS_DENIED",
                        )
                    )
                    return HealthRecordPayload(health_record=None, errors=errors)

                # Update record content
                update_reason = record_input.update_reason or "Content update"

                # Merge new resource data with existing
                if record_input.resource:
                    updated_record = health_record_service.update_record_content(
                        record_id=record_id,
                        content_updates=record_input.resource,
                        reason=update_reason,
                    )
                else:
                    # Update metadata only
                    update_data = {}
                    if (
                        hasattr(record_input, "access_level")
                        and record_input.access_level
                    ):
                        update_data["access_level"] = record_input.access_level
                    if hasattr(record_input, "categories") and record_input.categories:
                        update_data["categories"] = record_input.categories
                    if hasattr(record_input, "tags") and record_input.tags:
                        update_data["tags"] = record_input.tags

                    if update_data:
                        health_record_service.update(record_id, **update_data)

                    updated_record = health_record_service.get_by_id(record_id)

                if not updated_record:
                    raise ValueError("Failed to update health record")

                # Convert to GraphQL type
                health_record_data = {
                    "id": updated_record.id,
                    "patient_id": updated_record.patient_id,
                    "type": updated_record.record_type.value,
                    "title": updated_record.title,
                    "date": updated_record.record_date,
                    "status": updated_record.status.value,
                    "verified": updated_record.is_verified,
                    "created": updated_record.created_at,
                    "updated": updated_record.updated_at,
                    "version": updated_record.version,
                }

                health_record = HealthRecord(**health_record_data)

                db.commit()
                return HealthRecordPayload(health_record=health_record, errors=None)

        except (ValueError, AttributeError) as e:
            logger.error(f"Error updating health record: {e}")
            errors.append(
                Error(
                    message=f"Failed to update health record: {str(e)}",
                    code="UPDATE_FAILED",
                )
            )
            return HealthRecordPayload(health_record=None, errors=errors)


class DeleteHealthRecord(graphene.Mutation):
    """Delete a health record (with audit trail)."""

    class Arguments:
        record_id = graphene.Argument(UUIDScalar, required=True)

    Output = DeletePayload

    def mutate(self, info: Any, record_id: uuid.UUID) -> DeletePayload:
        """Delete health record mutation resolver."""
        errors = []

        # Check permissions
        user = info.context.get("user")
        if not user or not user.has_permission("delete:health_records"):
            errors.append(
                Error(
                    message="Unauthorized to delete health records", code="UNAUTHORIZED"
                )
            )
            return DeletePayload(success=False, errors=errors)

        try:
            with get_db() as db:
                # Create service with user context
                health_record_service = HealthRecordService(db)
                health_record_service.set_user_context(user.id, user.role)
                health_record_service.access_context = AccessContext.API

                # Get existing record to check access
                existing_record = health_record_service.get_by_id(record_id)
                if not existing_record:
                    errors.append(
                        Error(message="Health record not found", code="NOT_FOUND")
                    )
                    return DeletePayload(success=False, errors=errors)

                # Check if this is a critical record that shouldn't be deleted
                if existing_record.record_type in [
                    RecordType.IMMUNIZATION,
                    RecordType.ALLERGY,
                ]:
                    errors.append(
                        Error(
                            message="Critical health records cannot be deleted",
                            code="DELETION_PROHIBITED",
                        )
                    )
                    return DeletePayload(success=False, errors=errors)

                # Perform soft delete
                success = health_record_service.delete(record_id, hard=False)

                if success:
                    db.commit()
                    return DeletePayload(success=True, errors=None)
                else:
                    errors.append(
                        Error(
                            message="Failed to delete health record",
                            code="DELETE_FAILED",
                        )
                    )
                    return DeletePayload(success=False, errors=errors)

        except (ValueError, AttributeError) as e:
            logger.error(f"Error deleting health record: {e}")
            errors.append(
                Error(
                    message=f"Failed to delete health record: {str(e)}",
                    code="DELETE_FAILED",
                )
            )
            return DeletePayload(success=False, errors=errors)


class AttachDocument(graphene.Mutation):
    """Attach a document to a health record."""

    class Arguments:
        record_id = graphene.Argument(UUIDScalar, required=True)
        document = graphene.Argument(
            graphene.String, required=True
        )  # Would be Upload scalar

    Output = HealthRecordPayload

    def mutate(
        self, info: Any, record_id: uuid.UUID, document: str
    ) -> HealthRecordPayload:
        """Attach document mutation resolver."""
        errors = []

        # Check permissions
        user = info.context.get("user")
        if not user or not user.has_permission("update:health_records"):
            errors.append(
                Error(message="Unauthorized to attach documents", code="UNAUTHORIZED")
            )
            return HealthRecordPayload(health_record=None, errors=errors)

        try:
            with get_db() as db:
                # Create service with user context
                health_record_service = HealthRecordService(db)
                health_record_service.set_user_context(user.id, user.role)
                health_record_service.access_context = AccessContext.API

                # Get existing record
                existing_record = health_record_service.get_by_id(record_id)
                if not existing_record:
                    errors.append(
                        Error(message="Health record not found", code="NOT_FOUND")
                    )
                    return HealthRecordPayload(health_record=None, errors=errors)

                # In production, would handle actual file upload to S3/storage
                # For now, simulate with a URL
                file_hash = hashlib.md5(
                    document.encode(), usedforsecurity=False
                ).hexdigest()
                file_url = (
                    f"https://storage.havenhealthpassport.org/documents/{file_hash}.pdf"
                )
                file_type = "application/pdf"  # Would be detected from upload

                # Add attachment to record
                success = health_record_service.add_attachment(
                    record_id=record_id,
                    file_url=file_url,
                    file_type=file_type,
                    description=f"Document attached by {user.name if hasattr(user, 'name') else 'user'}",
                )

                if not success:
                    raise ValueError("Failed to attach document")

                # Get updated record
                updated_record = health_record_service.get_by_id(record_id)

                if not updated_record:
                    errors.append(
                        Error(
                            message="Failed to get updated record", code="UPDATE_FAILED"
                        )
                    )
                    return HealthRecordPayload(record=None, errors=errors)

                # Convert to GraphQL type
                health_record_data = {
                    "id": updated_record.id,
                    "patient_id": updated_record.patient_id,
                    "type": updated_record.record_type.value,
                    "title": updated_record.title,
                    "date": updated_record.record_date,
                    "status": updated_record.status.value,
                    "attachments": updated_record.attachments or [],
                    "verified": updated_record.is_verified,
                    "created": updated_record.created_at,
                    "updated": updated_record.updated_at,
                }

                health_record = HealthRecord(**health_record_data)

                db.commit()
                return HealthRecordPayload(health_record=health_record, errors=None)

        except ValueError as e:
            logger.error(f"Error attaching document: {e}")
            errors.append(Error(message=str(e), code="VALIDATION_ERROR"))
            return HealthRecordPayload(health_record=None, errors=errors)
        except AttributeError as e:
            logger.error(f"Error attaching document: {e}")
            errors.append(
                Error(
                    message=f"Failed to attach document: {str(e)}", code="ATTACH_FAILED"
                )
            )
            return HealthRecordPayload(health_record=None, errors=errors)


# Translation Mutations


class TranslationSessionPayload(graphene.ObjectType):
    """Payload for translation session mutations."""

    session_id = graphene.String()
    user_id = graphene.String()
    source_language = graphene.String()
    target_language = graphene.String()
    context_type = graphene.String()
    created_at = graphene.Field(DateTimeScalar)
    active = graphene.Boolean()
    errors = graphene.List(Error)


class TranslationPayload(graphene.ObjectType):
    """Payload for translation mutations."""

    translated_text = graphene.String()
    source_language = graphene.String()
    target_language = graphene.String()
    confidence_score = graphene.Float()
    session_id = graphene.String()
    medical_terms_detected = graphene.Field(graphene.JSONString)
    errors = graphene.List(Error)


class CreateTranslationSession(graphene.Mutation):
    """Create a new real-time translation session."""

    class Arguments:
        source_language = graphene.String()
        target_language = graphene.String()
        context_type = graphene.String()

    Output = TranslationSessionPayload

    async def mutate(
        self,
        info: Any,
        source_language: Optional[str] = None,
        target_language: Optional[str] = None,
        context_type: str = "patient_facing",
    ) -> TranslationSessionPayload:
        """Create translation session mutation resolver."""
        errors = []

        # Check permissions
        user = info.context.get("user")
        if not user or not user.has_permission("use:translations"):
            errors.append(
                Error(message="Unauthorized to use translations", code="UNAUTHORIZED")
            )
            return TranslationSessionPayload(errors=errors)

        try:
            # Get real-time translation service
            with get_db() as db:
                rt_service = get_realtime_translation_service(db)

                # Parse language codes if provided
                src_lang = (
                    TranslationDirection(source_language) if source_language else None
                )
                tgt_lang = (
                    TranslationDirection(target_language) if target_language else None
                )
                ctx_type = (
                    TranslationContext(context_type)
                    if context_type
                    else TranslationContext.PATIENT_FACING
                )

                # Create session
                session_info = await rt_service.start_translation_session(
                    user_id=user.id,
                    source_language=src_lang,
                    target_language=tgt_lang,
                    context_type=ctx_type,
                )

                return TranslationSessionPayload(**session_info)

        except (ValueError, AttributeError) as e:
            logger.error(f"Error creating translation session: {e}")
            errors.append(
                Error(
                    message=f"Failed to create translation session: {str(e)}",
                    code="TRANSLATION_ERROR",
                )
            )
            return TranslationSessionPayload(errors=errors)


class TranslateWithDialect(graphene.Mutation):
    """Translate text with dialect-specific handling."""

    class Arguments:
        text = graphene.String(required=True)
        target_dialect = graphene.String(required=True)
        source_dialect = graphene.String()
        translation_type = graphene.String()
        cultural_adaptation = graphene.Boolean()

    Output = TranslationPayload

    async def mutate(
        self,
        info: graphene.ResolveInfo,
        text: str,
        target_dialect: str,
        source_dialect: Optional[str] = None,
        translation_type: str = "ui_text",
        cultural_adaptation: bool = True,
    ) -> "TranslationPayload":
        """Translate with dialect mutation resolver."""
        errors = []

        # Check permissions
        user = info.context.get("user")
        if not user or not user.has_permission("use:translations"):
            errors.append(
                Error(message="Unauthorized to use translations", code="UNAUTHORIZED")
            )
            return TranslationPayload(errors=errors)

        try:
            with get_db() as db:
                # Create translation service
                trans_service = TranslationService(db)
                trans_service.set_user_context(user.id, user.role)

                # Parse translation type
                trans_type = (
                    TranslationType(translation_type)
                    if translation_type
                    else TranslationType.UI_TEXT
                )

                # Perform dialect-aware translation
                result = await trans_service.translate_with_dialect(
                    text=text,
                    target_dialect=target_dialect,
                    source_dialect=source_dialect,
                    translation_type=trans_type,
                    cultural_adaptation=cultural_adaptation,
                )

                return TranslationPayload(
                    translated_text=result.get("translated_text"),
                    source_language=result.get("source_dialect"),
                    target_language=result.get("target_dialect"),
                    confidence_score=result.get("confidence_score"),
                    medical_terms_detected=result.get("medical_terms_detected"),
                )

        except (ValueError, AttributeError) as e:
            logger.error(f"Dialect translation error: {e}")
            errors.append(
                Error(message=f"Translation failed: {str(e)}", code="TRANSLATION_ERROR")
            )
            return TranslationPayload(errors=errors)


class TranslateForRegion(graphene.Mutation):
    """Translate text for a specific geographic region."""

    class Arguments:
        text = graphene.String(required=True)
        target_region = graphene.String(required=True)
        source_language = graphene.String()
        translation_type = graphene.String()

    Output = TranslationPayload

    async def mutate(
        self,
        info: graphene.ResolveInfo,
        text: str,
        target_region: str,
        source_language: Optional[str] = None,
        translation_type: str = "ui_text",
    ) -> "TranslationPayload":
        """Regional translation mutation resolver."""
        errors = []

        # Check permissions
        user = info.context.get("user")
        if not user or not user.has_permission("use:translations"):
            errors.append(
                Error(message="Unauthorized to use translations", code="UNAUTHORIZED")
            )
            return TranslationPayload(errors=errors)

        try:
            with get_db() as db:
                # Create translation service
                trans_service = TranslationService(db)
                trans_service.set_user_context(user.id, user.role)

                # Parse parameters
                src_lang = (
                    TranslationDirection(source_language) if source_language else None
                )
                trans_type = (
                    TranslationType(translation_type)
                    if translation_type
                    else TranslationType.UI_TEXT
                )

                # Perform regional translation
                result = await trans_service.translate_for_region(
                    text=text,
                    target_region=target_region,
                    source_language=src_lang,
                    translation_type=trans_type,
                )

                return TranslationPayload(
                    translated_text=result.get("translated_text"),
                    source_language=result.get(
                        "source_language", result.get("source_dialect")
                    ),
                    target_language=result.get(
                        "target_language", result.get("target_dialect")
                    ),
                    confidence_score=result.get("confidence_score"),
                    medical_terms_detected=result.get("medical_terms_detected"),
                )

        except (ValueError, AttributeError, KeyError) as e:
            logger.error(f"Regional translation error: {e}")
            errors.append(
                Error(message=f"Translation failed: {str(e)}", code="TRANSLATION_ERROR")
            )
            return TranslationPayload(errors=errors)


class ConvertMeasurements(graphene.Mutation):
    """Convert measurements in text to appropriate system."""

    class Arguments:
        text = graphene.String(required=True)
        target_region = graphene.String()
        target_system = graphene.String()
        preserve_original = graphene.Boolean()

    Output = graphene.JSONString

    def mutate(
        self,
        info: graphene.ResolveInfo,
        text: str,
        target_region: Optional[str] = None,
        target_system: Optional[str] = None,
        preserve_original: bool = True,
    ) -> Any:
        """Convert measurements mutation resolver."""
        # Check permissions
        user = info.context.get("user")
        if not user or not user.has_permission("use:translations"):
            return {"error": "Unauthorized to use measurement conversion"}

        try:
            with get_db() as db:
                trans_service = TranslationService(db)
                trans_service.set_user_context(user.id, user.role)

                result = trans_service.convert_measurements(
                    text=text,
                    target_region=target_region,
                    target_system=target_system,
                    preserve_original=preserve_original,
                )

                return result

        except (ValueError, AttributeError) as e:
            logger.error(f"Measurement conversion error: {e}")
            return {"error": str(e), "original_text": text}


class ConvertSingleMeasurement(graphene.Mutation):
    """Convert a single measurement value."""

    class Arguments:
        value = graphene.Float(required=True)
        from_unit = graphene.String(required=True)
        to_unit = graphene.String(required=True)

    Output = graphene.JSONString

    def mutate(
        self, info: Any, value: float, from_unit: str, to_unit: str
    ) -> ConversionPayload:
        """Single measurement conversion resolver."""
        # Check permissions
        user = info.context.get("user")
        if not user:
            return ConversionPayload(result=None, errors=[{"message": "Unauthorized"}])

        try:
            with get_db() as db:
                trans_service = TranslationService(db)
                result = trans_service.convert_single_measurement(
                    value=value, from_unit=from_unit, to_unit=to_unit
                )
                return ConversionPayload(result=result, errors=[])

        except (ValueError, AttributeError) as e:
            logger.error(f"Single measurement conversion error: {e}")
            return ConversionPayload(result=None, errors=[{"message": str(e)}])


class ValidateMedicalMeasurement(graphene.Mutation):
    """Validate if a medical measurement is within typical ranges."""

    class Arguments:
        value = graphene.Float(required=True)
        unit = graphene.String(required=True)
        measurement_type = graphene.String(required=True)

    Output = graphene.JSONString

    def mutate(
        self, info: Any, value: float, unit: str, measurement_type: str
    ) -> ValidationPayload:
        """Validate medical measurement resolver."""
        # Public mutation - no auth required for validation
        _ = info  # Mark as used
        try:
            with get_db() as db:
                trans_service = TranslationService(db)
                result = trans_service.validate_medical_measurement(
                    value=value, unit=unit, measurement_type=measurement_type
                )
                return ValidationPayload(result=result, errors=[])

        except (ValueError, AttributeError) as e:
            logger.error(f"Medical validation error: {e}")
            return ValidationPayload(
                result={"valid": False, "warnings": [str(e)]},
                errors=[{"message": str(e)}],
            )


class TranslateWithMeasurements(graphene.Mutation):
    """Translate text with automatic measurement conversion."""

    class Arguments:
        text = graphene.String(required=True)
        target_language = graphene.String(required=True)
        source_language = graphene.String()
        target_region = graphene.String()
        convert_measurements = graphene.Boolean()
        translation_type = graphene.String()

    Output = TranslationPayload

    def mutate(
        self,
        info: Any,
        text: str,
        target_language: str,
        source_language: Optional[str] = None,
        target_region: Optional[str] = None,
        convert_measurements: bool = True,
        translation_type: str = "medical_record",
    ) -> "TranslationPayload":
        """Translate with measurements mutation resolver."""
        errors = []

        # Check permissions
        user = info.context.get("user")
        if not user or not user.has_permission("use:translations"):
            errors.append(
                Error(message="Unauthorized to use translations", code="UNAUTHORIZED")
            )
            return TranslationPayload(errors=errors)

        try:
            with get_db() as db:
                trans_service = TranslationService(db)
                trans_service.set_user_context(user.id, user.role)

                # Parse parameters
                tgt_lang = TranslationDirection(target_language)
                src_lang = (
                    TranslationDirection(source_language) if source_language else None
                )
                trans_type = (
                    TranslationType(translation_type)
                    if translation_type
                    else TranslationType.MEDICAL_RECORD
                )

                # Perform translation with measurements
                result = trans_service.translate_with_measurements(
                    text=text,
                    target_language=tgt_lang,
                    source_language=src_lang,
                    target_region=target_region,
                    convert_measurements=convert_measurements,
                    translation_type=trans_type,
                )

                # Add measurement conversion info to response
                response = TranslationPayload(
                    translated_text=result.get("translated_text"),
                    source_language=result.get("source_language"),
                    target_language=result.get("target_language"),
                    confidence_score=result.get("confidence_score"),
                    medical_terms_detected=result.get("medical_terms_detected"),
                )

                # Add measurement conversion metadata if performed
                if result.get("measurement_conversion", {}).get("performed"):
                    response.medical_terms_detected = (
                        response.medical_terms_detected or {}
                    )
                    response.medical_terms_detected["measurement_conversion"] = result[
                        "measurement_conversion"
                    ]

                return response

        except (ValueError, AttributeError) as e:
            logger.error(f"Translation with measurements error: {e}")
            errors.append(
                Error(message=f"Translation failed: {str(e)}", code="TRANSLATION_ERROR")
            )
            return TranslationPayload(errors=errors)


class TranslateFHIRDocument(graphene.Mutation):
    """Translate a FHIR document while preserving structure."""

    class Arguments:
        fhir_document = graphene.JSONString(required=True)
        target_language = graphene.String(required=True)
        source_language = graphene.String()
        target_dialect = graphene.String()
        target_region = graphene.String()
        preserve_codes = graphene.Boolean()

    Output = graphene.JSONString

    def mutate(
        self,
        info: Any,
        fhir_document: str,
        target_language: str,
        source_language: Optional[str] = None,
        target_dialect: Optional[str] = None,
        target_region: Optional[str] = None,
        preserve_codes: bool = True,
    ) -> FHIRTranslationPayload:
        """Translate FHIR document mutation resolver."""
        # Check permissions
        user = info.context.get("user")
        if not user or not user.has_permission("translate:documents"):
            return FHIRTranslationPayload(
                result=None, errors=[{"message": "Unauthorized to translate documents"}]
            )

        try:
            with get_db() as db:
                trans_service = TranslationService(db)
                trans_service.set_user_context(user.id, user.role)

                # Parse parameters
                tgt_lang = TranslationDirection(target_language)
                src_lang = (
                    TranslationDirection(source_language) if source_language else None
                )

                # Translate FHIR document
                result = trans_service.translate_fhir_document(
                    fhir_document=fhir_document,
                    target_language=tgt_lang,
                    source_language=src_lang,
                    target_dialect=target_dialect,
                    target_region=target_region,
                    preserve_codes=preserve_codes,
                )

                return FHIRTranslationPayload(result=result, errors=[])

        except (ValueError, AttributeError) as e:
            logger.error(f"FHIR document translation error: {e}")
            return FHIRTranslationPayload(result=None, errors=[{"message": str(e)}])


class TranslateClinicalDocument(graphene.Mutation):
    """Translate a clinical document in various formats."""

    class Arguments:
        document_text = graphene.String(required=True)
        document_format = graphene.String(required=True)
        target_language = graphene.String(required=True)
        source_language = graphene.String()
        target_dialect = graphene.String()
        target_region = graphene.String()
        section_mapping = graphene.JSONString()

    Output = graphene.JSONString

    def mutate(
        self,
        info: Any,
        document_text: str,
        document_format: str,
        target_language: str,
        source_language: Optional[str] = None,
        target_dialect: Optional[str] = None,
        target_region: Optional[str] = None,
        section_mapping: Optional[str] = None,
    ) -> ClinicalDocumentTranslationPayload:
        """Translate clinical document mutation resolver."""
        # Check permissions
        user = info.context.get("user")
        if not user or not user.has_permission("translate:documents"):
            return ClinicalDocumentTranslationPayload(
                result=None, errors=[{"message": "Unauthorized to translate documents"}]
            )

        try:
            with get_db() as db:
                trans_service = TranslationService(db)
                trans_service.set_user_context(user.id, user.role)

                # Parse parameters
                tgt_lang = TranslationDirection(target_language)
                src_lang = (
                    TranslationDirection(source_language) if source_language else None
                )

                # Parse section_mapping from JSON string to dict
                parsed_section_mapping = None
                if section_mapping:
                    try:
                        parsed_section_mapping = json.loads(section_mapping)
                    except json.JSONDecodeError:
                        logger.warning("Invalid section_mapping JSON, ignoring")

                # Translate document
                result = trans_service.translate_clinical_document(
                    document_text=document_text,
                    document_format=document_format,
                    target_language=tgt_lang,
                    source_language=src_lang,
                    target_dialect=target_dialect,
                    target_region=target_region,
                    section_mapping=parsed_section_mapping,
                )

                return ClinicalDocumentTranslationPayload(result=result, errors=[])

        except (ValueError, AttributeError, RuntimeError) as e:
            logger.error(f"Clinical document translation error: {e}")
            return ClinicalDocumentTranslationPayload(
                result=None, errors=[{"message": str(e)}]
            )


class TranslateDocumentSection(graphene.Mutation):
    """Translate a specific section of a medical document."""

    class Arguments:
        section_text = graphene.String(required=True)
        section_type = graphene.String(required=True)
        target_language = graphene.String(required=True)
        source_language = graphene.String()
        target_dialect = graphene.String()
        target_region = graphene.String()

    Output = graphene.JSONString

    def mutate(
        self,
        info: Any,
        section_text: str,
        section_type: str,
        target_language: str,
        source_language: Optional[str] = None,
        target_dialect: Optional[str] = None,
        target_region: Optional[str] = None,
    ) -> SectionTranslationPayload:
        """Translate document section mutation resolver."""
        # Check permissions
        user = info.context.get("user")
        if not user or not user.has_permission("use:translations"):
            return SectionTranslationPayload(
                result=None, errors=[{"message": "Unauthorized to use translations"}]
            )

        try:
            with get_db() as db:
                trans_service = TranslationService(db)
                trans_service.set_user_context(user.id, user.role)

                # Parse parameters
                tgt_lang = TranslationDirection(target_language)
                src_lang = (
                    TranslationDirection(source_language) if source_language else None
                )

                # Translate section
                result = trans_service.translate_document_section(
                    section_text=section_text,
                    section_type=section_type,
                    target_language=tgt_lang,
                    source_language=src_lang,
                    target_dialect=target_dialect,
                    target_region=target_region,
                )

                return SectionTranslationPayload(result=result, errors=[])

        except (ValueError, AttributeError, RuntimeError) as e:
            logger.error(f"Document section translation error: {e}")
            return SectionTranslationPayload(result=None, errors=[{"message": str(e)}])


class TranslateText(graphene.Mutation):
    """Translate text in real-time."""

    class Arguments:
        session_id = graphene.String(required=True)
        text = graphene.String(required=True)
        target_language = graphene.String()
        source_language = graphene.String()
        translation_type = graphene.String()

    Output = TranslationPayload

    async def mutate(
        self,
        info: Any,
        session_id: str,
        text: str,
        target_language: Optional[str] = None,
        source_language: Optional[str] = None,
        translation_type: str = "ui_text",
    ) -> "TranslationPayload":
        """Translate text mutation resolver."""
        errors = []

        # Check permissions
        user = info.context.get("user")
        if not user or not user.has_permission("use:translations"):
            errors.append(
                Error(message="Unauthorized to use translations", code="UNAUTHORIZED")
            )
            return TranslationPayload(errors=errors)

        try:

            with get_db() as db:
                # Get real-time translation service
                rt_service = get_realtime_translation_service(db)

                # Parse parameters
                tgt_lang = (
                    TranslationDirection(target_language) if target_language else None
                )
                src_lang = (
                    TranslationDirection(source_language) if source_language else None
                )
                trans_type = (
                    TranslationType(translation_type)
                    if translation_type
                    else TranslationType.UI_TEXT
                )

                # Perform translation
                result = await rt_service.translate_text_streaming(
                    session_id=session_id,
                    text=text,
                    target_language=tgt_lang,
                    source_language=src_lang,
                    translation_type=trans_type,
                )

                return TranslationPayload(
                    translated_text=result.get("translated_text"),
                    source_language=result.get("source_language"),
                    target_language=result.get("target_language"),
                    confidence_score=result.get("confidence_score"),
                    session_id=session_id,
                    medical_terms_detected=result.get("medical_terms_detected"),
                )

        except (ValueError, AttributeError, RuntimeError) as e:
            logger.error(f"Translation error: {e}")
            errors.append(
                Error(message=f"Translation failed: {str(e)}", code="TRANSLATION_ERROR")
            )
            return TranslationPayload(errors=errors)


class CloseTranslationSession(graphene.Mutation):
    """Close a translation session."""

    class Arguments:
        session_id = graphene.String(required=True)

    Output = DeletePayload

    async def mutate(self, info: Any, session_id: str) -> "DeletePayload":
        """Close translation session mutation resolver."""
        errors = []

        # Check permissions
        user = info.context.get("user")
        if not user:
            errors.append(Error(message="Unauthorized", code="UNAUTHORIZED"))
            return DeletePayload(success=False, errors=errors)

        try:
            with get_db() as db:
                # Get real-time translation service
                rt_service = get_realtime_translation_service(db)

                # Close session
                success = await rt_service.close_session(session_id)

                if not success:
                    errors.append(
                        Error(
                            message="Session not found or already closed",
                            code="SESSION_NOT_FOUND",
                        )
                    )

                return DeletePayload(success=success, errors=errors)

        except (ValueError, AttributeError, RuntimeError) as e:
            logger.error(f"Error closing translation session: {e}")
            errors.append(
                Error(message=f"Failed to close session: {str(e)}", code="CLOSE_ERROR")
            )
            return DeletePayload(success=False, errors=errors)


# Mutation class combining all mutations


class Mutation(graphene.ObjectType):
    """Root Mutation type."""

    # Patient mutations
    create_patient = CreatePatient.Field()
    update_patient = UpdatePatient.Field()
    delete_patient = DeletePatient.Field()
    merge_patients = MergePatients.Field()

    # Health record mutations
    create_health_record = CreateHealthRecord.Field()
    update_health_record = UpdateHealthRecord.Field()
    delete_health_record = DeleteHealthRecord.Field()
    attach_document = AttachDocument.Field()

    # Verification mutations
    request_verification = RequestVerification.Field()
    approve_verification = ApproveVerification.Field()
    revoke_verification = RevokeVerification.Field()
    update_verification = UpdateVerification.Field()

    # Translation mutations
    create_translation_session = CreateTranslationSession.Field()
    translate_text = TranslateText.Field()
    translate_with_dialect = TranslateWithDialect.Field()
    translate_for_region = TranslateForRegion.Field()
    translate_with_measurements = TranslateWithMeasurements.Field()
    close_translation_session = CloseTranslationSession.Field()

    # Document translation mutations
    translate_fhir_document = TranslateFHIRDocument.Field()
    translate_clinical_document = TranslateClinicalDocument.Field()
    translate_document_section = TranslateDocumentSection.Field()

    # Measurement mutations
    convert_measurements = ConvertMeasurements.Field()
    convert_single_measurement = ConvertSingleMeasurement.Field()
    validate_medical_measurement = ValidateMedicalMeasurement.Field()

    # Additional mutations would be added here:
    # - Family mutations
    # - Access control mutations
    # - Emergency access mutations


# Export mutation schema
__all__ = ["Mutation"]
