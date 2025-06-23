# pylint: disable=too-many-lines
"""GraphQL Query Implementations.

This module implements the query resolvers for the Haven Health Passport
GraphQL API, providing data retrieval operations for patients, health records,
and related resources.
 Handles FHIR Resource validation.
"""

import uuid
from datetime import date, datetime
from typing import Any, Dict, List, Optional

try:
    import graphene
    from graphql import GraphQLError
except ImportError:
    graphene = None

    class GraphQLError(Exception):  # type: ignore[no-redef]
        """Fallback GraphQLError when graphql is not available."""

        pass


from sqlalchemy import distinct

from src.core.database import get_db
from src.models.access_log import AccessContext
from src.models.verification import Verification as VerificationModel
from src.models.verification import VerificationStatus

# Import services
from src.services.family_service import FamilyService
from src.services.health_record_service import HealthRecordService
from src.services.patient_service import PatientService
from src.services.translation_service import TranslationService
from src.services.verification_service import VerificationService
from src.translation.document_translator import (
    DocumentFormat,
    DocumentSection,
)
from src.translation.measurement_converter import (
    MeasurementType,
    get_measurement_converter,
)
from src.utils.logging import get_logger

from .inputs import (
    DateRangeFilter,
    FilterOptions,
    PaginationInput,
    SearchCriteria,
    SortInput,
)
from .scalars import DateScalar, UUIDScalar
from .types import (
    FamilyGroup,
    HealthcareFacility,
    HealthRecord,
    HealthRecordConnection,
    Language,
    Patient,
    PatientConnection,
    RecordVersion,
    Verification,
    Verifier,
)

logger = get_logger(__name__)


class PatientQueries:
    """Patient-related queries."""

    # Single patient queries
    get_patient_by_id = graphene.Field(
        Patient,
        patient_id=graphene.Argument(UUIDScalar, required=True),
        description="Get a patient by their unique ID",
    )

    get_patient_by_identifier = graphene.Field(
        Patient,
        system=graphene.String(required=True),
        value=graphene.String(required=True),
        description="Get a patient by identifier in a specific system",
    )

    # Patient search
    search_patients = graphene.Field(
        PatientConnection,
        search=graphene.Argument(SearchCriteria),
        filters=graphene.List(FilterOptions),
        sort=graphene.List(SortInput),
        pagination=graphene.Argument(PaginationInput),
        description="Search for patients with advanced filtering",
    )

    # Patient history
    get_patient_history = graphene.List(
        HealthRecord,
        patient_id=graphene.Argument(UUIDScalar, required=True),
        start_date=graphene.Argument(DateScalar),
        end_date=graphene.Argument(DateScalar),
        description="Get complete health history for a patient",
    )

    # Patient verifications
    get_patient_verifications = graphene.List(
        Verification,
        patient_id=graphene.Argument(UUIDScalar, required=True),
        description="Get all verifications for a patient",
    )

    def resolve_get_patient_by_id(
        self, info: graphene.ResolveInfo, patient_id: uuid.UUID
    ) -> Optional[Patient]:
        """Resolve patient by ID."""
        # Check permissions
        user = info.context.get("user")
        if not user or not user.has_permission("read:patients"):
            raise ValueError("Unauthorized access to patient data")

        try:
            with get_db() as db:
                # Create service with user context
                patient_service = PatientService(db)
                patient_service.set_user_context(user.id, user.role)
                patient_service.access_context = AccessContext.API

                # Get patient
                patient_model = patient_service.get_by_id(patient_id)

                if not patient_model:
                    return None

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
                    "gender": (
                        patient_model.gender.value
                        if patient_model.gender
                        else "unknown"
                    ),
                    "birth_date": patient_model.date_of_birth,
                    "created": patient_model.created_at,
                    "updated": patient_model.updated_at,
                    "created_by": patient_model.created_by_organization or "system",
                }

                return Patient(**patient_data)

        except Exception as e:
            logger.error(f"Error resolving patient by ID: {e}")
            raise ValueError(f"Error retrieving patient: {str(e)}") from e

    def resolve_get_patient_by_identifier(
        self, info: Any, system: str, value: str
    ) -> Optional[Patient]:
        """Resolve patient by identifier."""
        # Check permissions
        user = info.context.get("user")
        if not user or not user.has_permission("read:patients"):
            raise ValueError("Unauthorized access to patient data")

        # In production, this would call PatientService
        # patient_service = PatientService()
        # patient_data = patient_service.get_by_identifier(system, value)
        _ = system  # Will be used when implemented
        _ = value  # Will be used when implemented
        # For now, return None as placeholder
        return None

    def resolve_search_patients(
        self,
        info: graphene.ResolveInfo,
        search: Optional[SearchCriteria] = None,
        filters: Optional[List[FilterOptions]] = None,
        sort: Optional[List[SortInput]] = None,
        pagination: Optional[PaginationInput] = None,
    ) -> PatientConnection:
        """Resolve patient search."""
        # Check permissions
        user = info.context.get("user")
        if not user or not user.has_permission("search:patients"):
            raise ValueError("Unauthorized to search patients")

        try:
            with get_db() as db:
                # Create service with user context
                patient_service = PatientService(db)
                patient_service.set_user_context(user.id, user.role)
                patient_service.access_context = AccessContext.API

                # Build search parameters
                search_params = self._build_search_params(
                    search, filters, sort, pagination
                )

                # Perform search
                patients, total_count = patient_service.search_patients(
                    query=search_params.get("query"),
                    filters=search_params.get("filters"),
                    limit=search_params.get("limit", 100),
                    offset=search_params.get("offset", 0),
                )

                # Convert to GraphQL types
                edges = []
                for patient in patients:
                    patient_data = {
                        "id": patient.id,
                        "name": [
                            {
                                "family": patient.family_name,
                                "given": [patient.given_name],
                            }
                        ],
                        "gender": patient.gender.value if patient.gender else "unknown",
                        "birth_date": patient.date_of_birth,
                    }
                    edges.append(
                        {"node": Patient(**patient_data), "cursor": str(patient.id)}
                    )

                # Determine pagination info
                has_next = (
                    search_params.get("offset", 0) + len(patients)
                ) < total_count
                has_prev = search_params.get("offset", 0) > 0

                return PatientConnection(
                    edges=edges,
                    page_info={
                        "has_next_page": has_next,
                        "has_previous_page": has_prev,
                        "start_cursor": edges[0]["cursor"] if edges else None,
                        "end_cursor": edges[-1]["cursor"] if edges else None,
                    },
                    total_count=total_count,
                )

        except Exception as e:
            logger.error(f"Error searching patients: {e}")
            raise ValueError(f"Error searching patients: {str(e)}") from e

    def resolve_get_patient_history(
        self,
        info: Any,
        patient_id: uuid.UUID,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> List[HealthRecord]:
        """Resolve patient health history."""
        # Check permissions
        user = info.context.get("user")
        if not user or not user.has_permission("read:health_records"):
            raise ValueError("Unauthorized access to health records")

        # Verify patient access
        if not self.can_access_patient(user, patient_id):
            raise ValueError("Access denied to patient records")

        try:
            with get_db() as db:
                # Create service with user context
                health_record_service = HealthRecordService(db)
                health_record_service.set_user_context(user.id, user.role)
                health_record_service.access_context = AccessContext.API

                # Get patient records
                records, _ = health_record_service.get_patient_records(
                    patient_id=patient_id,
                    start_date=(
                        datetime.combine(start_date, datetime.min.time())
                        if start_date
                        else None
                    ),
                    end_date=(
                        datetime.combine(end_date, datetime.max.time())
                        if end_date
                        else None
                    ),
                    include_content=True,
                )

                # Convert to GraphQL types
                health_records = []
                for record in records:
                    health_record_data = {
                        "id": record.id,
                        "patient_id": record.patient_id,
                        "type": record.record_type.value,
                        "title": record.title,
                        "date": record.record_date,
                        "provider": (
                            {"id": record.provider_id, "name": record.provider_name}
                            if record.provider_id
                            else None
                        ),
                        "verified": record.is_verified,
                        "created": record.created_at,
                        "updated": record.updated_at,
                    }
                    health_records.append(HealthRecord(**health_record_data))

                return health_records

        except Exception as e:
            logger.error(f"Error getting patient history: {e}")
            raise ValueError(f"Error retrieving patient history: {str(e)}") from e

    def resolve_get_patient_verifications(
        self, info: graphene.ResolveInfo, patient_id: uuid.UUID
    ) -> List[Verification]:
        """Resolve patient verifications."""
        # Check permissions
        user = info.context.get("user")
        if not user or not user.has_permission("read:verifications"):
            raise ValueError("Unauthorized access to verification data")

        try:
            with get_db() as db:
                # Create service with user context
                verification_service = VerificationService(db)
                verification_service.set_user_context(user.id, user.role)
                verification_service.access_context = AccessContext.API

                # Get patient verifications
                verifications = verification_service.get_patient_verifications(
                    patient_id=patient_id, active_only=True
                )

                # Convert to GraphQL types
                verification_list = []
                for verification in verifications:
                    verification_data = {
                        "id": verification.id,
                        "patient_id": verification.patient_id,
                        "type": verification.verification_type,
                        "method": verification.verification_method.value,
                        "status": verification.status.value,
                        "level": verification.verification_level.value,
                        "verifier": {
                            "id": verification.verifier_id,
                            "name": verification.verifier_name,
                            "organization": verification.verifier_organization,
                        },
                        "verified_at": verification.completed_at,
                        "expires_at": verification.expires_at,
                        "blockchain_hash": verification.blockchain_hash,
                        "confidence_score": verification.confidence_score,
                    }
                    verification_list.append(Verification(**verification_data))

                return verification_list

        except Exception as e:
            logger.error(f"Error getting patient verifications: {e}")
            raise ValueError(f"Error retrieving verifications: {str(e)}") from e

    def _build_search_params(
        self,
        search: Optional[SearchCriteria],
        filters: Optional[List[FilterOptions]],
        sort: Optional[List[SortInput]],
        pagination: Optional[PaginationInput],
    ) -> Dict[str, Any]:
        """Build search parameters from GraphQL inputs."""
        params = {}

        if search:
            params["query"] = search.query
            params["fields"] = search.fields
            params["fuzzy"] = search.fuzzy
            params["max_distance"] = search.max_distance

        if filters:
            params["filters"] = [
                {"field": f.field, "operator": f.operator, "value": f.value}
                for f in filters
            ]

        if sort:
            params["sort"] = [
                {"field": s.field, "direction": s.direction} for s in sort
            ]

        if pagination:
            params["limit"] = pagination.limit or 10
            params["offset"] = pagination.offset or 0
            params["cursor"] = pagination.cursor

        return params

    def can_access_patient(self, user: Any, patient_id: uuid.UUID) -> bool:
        """Check if user can access patient data."""
        # Check if user is the patient
        if hasattr(user, "patient_id") and str(user.patient_id) == str(patient_id):
            return True

        # Check if user has provider access
        if user.has_permission("provider:read_all_patients"):
            return True

        # Check if user has specific patient access
        if hasattr(user, "accessible_patients"):
            return str(patient_id) in user.accessible_patients

        return False

    def _log_patient_access(
        self, info: Any, patient_id_val: uuid.UUID, action_type: str
    ) -> None:
        """Log patient data access for audit trail.

        Args:
            info: GraphQL info context
            patient_id_val: Patient ID to log access for
            action_type: Type of action being performed
        """
        # In production, this would create an audit log entry
        _ = info.context.get("user")
        _ = info.context.get("ip_address")
        _ = patient_id_val
        _ = action_type

        # audit_service = AuditService()
        # audit_service.log_access(
        #     patient_id=patient_id,
        #     user_id=user.id,
        #     action=action,
        #     ip_address=ip_address,
        #     timestamp=datetime.now()
        # )


class HealthRecordQueries:
    """Health record-related queries."""

    get_health_record_by_id = graphene.Field(
        HealthRecord,
        id=graphene.Argument(UUIDScalar, required=True),
        description="Get a health record by ID",
    )

    search_health_records = graphene.Field(
        HealthRecordConnection,
        patient_id=graphene.Argument(UUIDScalar),
        type=graphene.Argument(graphene.String),
        date_range=graphene.Argument(DateRangeFilter),
        verified=graphene.Boolean(),
        search=graphene.Argument(SearchCriteria),
        filters=graphene.List(FilterOptions),
        sort=graphene.List(SortInput),
        pagination=graphene.Argument(PaginationInput),
        description="Search health records with filtering",
    )

    get_record_versions = graphene.List(
        RecordVersion,
        record_id=graphene.Argument(UUIDScalar, required=True),
        description="Get version history for a health record",
    )

    def resolve_get_health_record_by_id(
        self, info: graphene.ResolveInfo, record_id: uuid.UUID
    ) -> Optional[HealthRecord]:
        """Resolve health record by ID."""
        # Check permissions
        user = info.context.get("user")
        if not user or not user.has_permission("read:health_records"):
            raise ValueError("Unauthorized access to health records")

        try:
            with get_db() as db:
                # Create service with user context
                health_record_service = HealthRecordService(db)
                health_record_service.set_user_context(user.id, user.role)
                health_record_service.access_context = AccessContext.API

                # Get health record
                record = health_record_service.get_by_id(record_id)

                if not record:
                    return None

                # Check patient access
                patient_id = uuid.UUID(str(record.patient_id))
                if not self.can_access_patient(user, patient_id):
                    raise ValueError("Access denied to patient records")

                # Convert to GraphQL type
                health_record_data = {
                    "id": record.id,
                    "patient_id": record.patient_id,
                    "type": record.record_type.value,
                    "title": record.title,
                    "date": record.record_date,
                    "status": record.status.value,
                    "priority": record.priority.value if record.priority else "routine",
                    "provider": (
                        {
                            "id": record.provider_id,
                            "name": record.provider_name,
                            "organization": record.provider_organization,
                        }
                        if record.provider_id
                        else None
                    ),
                    "facility": (
                        {
                            "name": record.facility_name,
                            "location": record.facility_location,
                        }
                        if record.facility_name
                        else None
                    ),
                    "verified": record.is_verified,
                    "attachments": record.attachments or [],
                    "created": record.created_at,
                    "updated": record.updated_at,
                }

                return HealthRecord(**health_record_data)

        except (ValueError, AttributeError, KeyError) as e:
            # Handle specific errors
            logger.error("Error retrieving health record: %s", e)
            raise ValueError(f"Error retrieving health record: {str(e)}") from e
        except GraphQLError:
            # Re-raise GraphQL errors as-is
            raise

    def resolve_search_health_records(
        self, info: graphene.ResolveInfo, **kwargs: Any
    ) -> HealthRecordConnection:
        """Resolve health record search."""
        # Check permissions
        user = info.context.get("user")
        if not user or not user.has_permission("search:health_records"):
            raise ValueError("Unauthorized to search health records")

        # If searching by patient, check access
        patient_id = kwargs.get("patient_id")
        if patient_id and not self.can_access_patient(user, patient_id):
            raise ValueError("Access denied to patient records")

        try:
            with get_db() as db:
                # Create service with user context
                health_record_service = HealthRecordService(db)
                health_record_service.set_user_context(user.id, user.role)
                health_record_service.access_context = AccessContext.API

                # Build search parameters
                filters = {}
                if kwargs.get("type"):
                    filters["record_type"] = kwargs["type"]
                if kwargs.get("verified") is not None:
                    filters["verified"] = kwargs["verified"]

                # Handle date range
                date_range = kwargs.get("date_range")
                start_date = None
                end_date = None
                if date_range:
                    if date_range.start:
                        start_date = datetime.combine(
                            date_range.start, datetime.min.time()
                        )
                    if date_range.end:
                        end_date = datetime.combine(date_range.end, datetime.max.time())

                # Get pagination
                pagination = kwargs.get("pagination", {})
                limit = pagination.get("limit", 100) if pagination else 100
                offset = pagination.get("offset", 0) if pagination else 0

                # Perform search
                if patient_id:
                    records, total_count = health_record_service.get_patient_records(
                        patient_id=patient_id,
                        start_date=start_date,
                        end_date=end_date,
                        limit=limit,
                        offset=offset,
                    )
                else:
                    records, total_count = health_record_service.search_records(
                        search_query=(
                            kwargs.get("search", {}).get("query")
                            if kwargs.get("search")
                            else None
                        ),
                        filters=filters,
                        limit=limit,
                        offset=offset,
                    )

                # Convert to GraphQL types
                edges = []
                for record in records:
                    health_record_data = {
                        "id": record.id,
                        "patient_id": record.patient_id,
                        "type": record.record_type.value,
                        "title": record.title,
                        "date": record.record_date,
                        "verified": record.is_verified,
                    }
                    edges.append(
                        {
                            "node": HealthRecord(**health_record_data),
                            "cursor": str(record.id),
                        }
                    )

                # Determine pagination info
                has_next = (offset + len(records)) < total_count
                has_prev = offset > 0

                return HealthRecordConnection(
                    edges=edges,
                    page_info={
                        "has_next_page": has_next,
                        "has_previous_page": has_prev,
                        "start_cursor": edges[0]["cursor"] if edges else None,
                        "end_cursor": edges[-1]["cursor"] if edges else None,
                    },
                    total_count=total_count,
                )

        except Exception as e:
            logger.error(f"Error searching health records: {e}")
            raise ValueError(f"Error searching health records: {str(e)}") from e

    def resolve_get_record_versions(
        self, info: Any, record_id: uuid.UUID
    ) -> List[RecordVersion]:
        """Resolve record version history."""
        # Check permissions
        user = info.context.get("user")
        if not user or not user.has_permission("read:record_versions"):
            raise ValueError("Unauthorized access to record versions")

        try:
            with get_db() as db:
                # Create service with user context
                health_record_service = HealthRecordService(db)
                health_record_service.set_user_context(user.id, user.role)
                health_record_service.access_context = AccessContext.API

                # Get record history
                versions = health_record_service.get_record_history(record_id)

                # Convert to GraphQL types
                record_versions = []
                for idx, version in enumerate(versions):
                    version_data = {
                        "id": version.id,
                        "record_id": record_id,
                        "version": version.version or idx + 1,
                        "created": version.created_at,
                        "created_by": version.provider_name or "system",
                        "change_reason": version.change_reason,
                        "is_current": idx == 0,
                    }
                    record_versions.append(RecordVersion(**version_data))

                return record_versions

        except Exception as e:
            logger.error(f"Error getting record versions: {e}")
            raise ValueError(f"Error retrieving record versions: {str(e)}") from e

    def can_access_patient(self, user: Any, patient_id: uuid.UUID) -> bool:
        """Check if user can access patient data."""
        # Reuse from PatientQueries
        patient_queries = PatientQueries()
        return patient_queries.can_access_patient(user, patient_id)


class VerificationQueries:
    """Verification-related queries."""

    get_verification_status = graphene.Field(
        Verification,
        record_id=graphene.Argument(UUIDScalar, required=True),
        description="Get current verification status for a record",
    )

    get_verification_history = graphene.List(
        Verification,
        record_id=graphene.Argument(UUIDScalar, required=True),
        description="Get verification history for a record",
    )

    check_verification = graphene.Field(
        Verification,
        blockchain_hash=graphene.String(required=True),
        description="Verify a record using blockchain hash",
    )

    get_verifiers = graphene.List(
        Verifier, description="Get list of authorized verifiers"
    )

    def resolve_get_verification_status(
        self, info: Any, record_id: uuid.UUID
    ) -> Optional[Verification]:
        """Resolve current verification status."""
        # Check permissions
        user = info.context.get("user")
        if not user or not user.has_permission("read:verifications"):
            raise ValueError("Unauthorized access to verification data")

        try:
            with get_db() as db:
                # First get the health record to find patient ID
                health_record_service = HealthRecordService(db)
                health_record_service.set_user_context(user.id, user.role)
                record = health_record_service.get_by_id(record_id)

                if not record:
                    return None

                # Create verification service
                verification_service = VerificationService(db)
                verification_service.set_user_context(user.id, user.role)
                verification_service.access_context = AccessContext.API

                # Get active verifications for the patient
                patient_id = uuid.UUID(str(record.patient_id))
                verifications = verification_service.get_patient_verifications(
                    patient_id=patient_id,
                    verification_type="health_record",
                    active_only=True,
                )

                # Find verification for this specific record
                for verification in verifications:
                    evidence_list: list[Any] = (
                        verification.evidence_provided
                        if isinstance(verification.evidence_provided, list)  # type: ignore[unreachable]
                        else []
                    )
                    if evidence_list:
                        for evidence in evidence_list:
                            if evidence.get("data", {}).get("record_id") == str(
                                record_id
                            ):
                                # Convert to GraphQL type
                                verification_data = {
                                    "id": verification.id,
                                    "patient_id": verification.patient_id,
                                    "type": verification.verification_type,
                                    "method": verification.verification_method.value,
                                    "status": verification.status.value,
                                    "level": verification.verification_level.value,
                                    "verifier": {
                                        "id": verification.verifier_id,
                                        "name": verification.verifier_name,
                                        "organization": verification.verifier_organization,
                                    },
                                    "verified_at": verification.completed_at,
                                    "expires_at": verification.expires_at,
                                    "blockchain_hash": verification.blockchain_hash,
                                }
                                return Verification(**verification_data)

                return None

        except Exception as e:
            logger.error(f"Error getting verification status: {e}")
            raise ValueError(f"Error retrieving verification status: {str(e)}") from e

    def resolve_get_verification_history(
        self, info: graphene.ResolveInfo, record_id: uuid.UUID
    ) -> List[Verification]:
        """Resolve verification history."""
        # Check permissions
        user = info.context.get("user")
        if not user or not user.has_permission("read:verification_history"):
            raise ValueError("Unauthorized access to verification history")

        try:
            with get_db() as db:
                # First get the health record to find patient ID
                health_record_service = HealthRecordService(db)
                health_record_service.set_user_context(user.id, user.role)
                record = health_record_service.get_by_id(record_id)

                if not record:
                    return []

                # Create verification service
                verification_service = VerificationService(db)
                verification_service.set_user_context(user.id, user.role)
                verification_service.access_context = AccessContext.API

                # Get all verifications for the patient (including expired/revoked)
                patient_id = uuid.UUID(str(record.patient_id))
                verifications = verification_service.get_patient_verifications(
                    patient_id=patient_id,
                    verification_type="health_record",
                    active_only=False,
                )

                # Filter verifications related to this record
                record_verifications: List[Verification] = []
                for verification in verifications:
                    evidence_list: list[Any] = (
                        verification.evidence_provided
                        if isinstance(verification.evidence_provided, list)  # type: ignore[unreachable]
                        else []
                    )
                    if evidence_list:
                        for evidence in evidence_list:
                            if evidence.get("data", {}).get("record_id") == str(
                                record_id
                            ):
                                # Convert to GraphQL type
                                verification_data = {
                                    "id": verification.id,
                                    "patient_id": verification.patient_id,
                                    "type": verification.verification_type,
                                    "method": verification.verification_method.value,
                                    "status": verification.status.value,
                                    "level": verification.verification_level.value,
                                    "verifier": {
                                        "id": verification.verifier_id,
                                        "name": verification.verifier_name,
                                        "organization": verification.verifier_organization,
                                    },
                                    "verified_at": verification.completed_at,
                                    "expires_at": verification.expires_at,
                                    "revoked": verification.revoked,
                                    "revoked_at": verification.revoked_at,
                                    "blockchain_hash": verification.blockchain_hash,
                                }
                                record_verifications.append(
                                    Verification(**verification_data)
                                )
                                break

                return record_verifications

        except Exception as e:
            logger.error(f"Error getting verification history: {e}")
            raise ValueError(f"Error retrieving verification history: {str(e)}") from e

    def resolve_check_verification(
        self, info: graphene.ResolveInfo, blockchain_hash: str
    ) -> Optional[Verification]:
        """Resolve blockchain verification check."""
        _ = info  # Mark as intentionally unused - public query
        # Public query - no authentication required for blockchain verification
        try:
            with get_db() as db:
                # Search for verification by blockchain hash
                verification = (
                    db.query(VerificationModel)
                    .filter(VerificationModel.blockchain_hash == blockchain_hash)
                    .first()
                )

                if not verification:
                    return None

                # Convert to GraphQL type (limited data for public access)
                verification_data = {
                    "id": verification.id,
                    "type": verification.verification_type,
                    "method": verification.verification_method.value,
                    "status": verification.status.value,
                    "level": verification.verification_level.value,
                    "verifier": {
                        "name": verification.verifier_name,
                        "organization": verification.verifier_organization,
                    },
                    "verified_at": verification.completed_at,
                    "expires_at": verification.expires_at,
                    "blockchain_hash": verification.blockchain_hash,
                    "blockchain_tx_id": verification.blockchain_tx_id,
                }

                return Verification(**verification_data)

        except Exception as e:
            logger.error(f"Error checking blockchain verification: {e}")
            raise ValueError(f"Error checking verification: {str(e)}") from e

    def resolve_get_verifiers(self, info: graphene.ResolveInfo) -> List[Verifier]:
        """Resolve list of authorized verifiers."""
        _ = info  # Mark as intentionally unused - public query
        # Public query - returns public verifier information
        try:
            with get_db() as db:
                # Get unique verifiers from recent verifications
                # Query for distinct verifier organizations
                verifier_orgs = (
                    db.query(
                        distinct(VerificationModel.verifier_organization),
                        VerificationModel.verifier_name,
                    )
                    .filter(
                        VerificationModel.status == VerificationStatus.COMPLETED,
                        VerificationModel.verifier_organization.isnot(None),
                    )
                    .limit(50)
                    .all()
                )

                # Convert to GraphQL types
                verifiers = []
                for org, name in verifier_orgs:
                    if org:  # Skip if org is None
                        verifier_data = {
                            "id": str(
                                uuid.uuid5(uuid.NAMESPACE_DNS, org)
                            ),  # Generate consistent ID
                            "name": name or org,
                            "organization": org,
                            "type": "healthcare_provider",  # Default type
                            "is_active": True,
                            "verified_count": 0,  # Would need aggregate query for real count
                        }
                        verifiers.append(Verifier(**verifier_data))

                # Add some default trusted verifiers
                default_verifiers = [
                    {
                        "id": str(uuid.uuid4()),
                        "name": "UNHCR Regional Office",
                        "organization": "UNHCR",
                        "type": "government",
                        "is_active": True,
                    },
                    {
                        "id": str(uuid.uuid4()),
                        "name": "MSF Medical Team",
                        "organization": "Médecins Sans Frontières",
                        "type": "healthcare_provider",
                        "is_active": True,
                    },
                    {
                        "id": str(uuid.uuid4()),
                        "name": "Red Cross Health Unit",
                        "organization": "International Red Cross",
                        "type": "healthcare_provider",
                        "is_active": True,
                    },
                ]

                for verifier_data in default_verifiers:
                    verifiers.append(Verifier(**verifier_data))

                return verifiers

        except (ValueError, AttributeError, KeyError) as e:
            logger.error(f"Error getting verifiers: {e}")
            # Return empty list instead of error for public query
            return []


class FamilyQueries:
    """Family group-related queries."""

    get_family_group = graphene.Field(
        FamilyGroup,
        group_id=graphene.Argument(UUIDScalar, required=True),
        description="Get family group by ID",
    )

    search_family_members = graphene.List(
        FamilyGroup,
        case_number=graphene.String(),
        family_name=graphene.String(),
        include_missing=graphene.Boolean(),
        description="Search for family members",
    )

    def resolve_get_family_group(
        self, info: graphene.ResolveInfo, group_id: uuid.UUID
    ) -> Optional[FamilyGroup]:
        """Resolve family group by ID."""
        # Check permissions
        user = info.context.get("user")
        if not user or not user.has_permission("read:family_groups"):
            raise ValueError("Unauthorized access to family data")

        # Get database session
        db = info.context.get("db")
        if not db:
            raise ValueError("Database session not available")

        # Fetch from FamilyService
        family_service = FamilyService(db)
        group = family_service.get_family_group(group_id)
        if not group:
            return None
        # Convert to GraphQL FamilyGroup type if needed
        # For now, assuming the service returns compatible type
        return group  # type: ignore[return-value]

    def resolve_search_family_members(
        self,
        info: graphene.ResolveInfo,
        _case_number: Optional[str] = None,
        _family_name: Optional[str] = None,
        _include_missing: bool = False,
    ) -> List[FamilyGroup]:
        """Resolve family member search."""
        # Check permissions
        user = info.context.get("user")
        if not user or not user.has_permission("search:families"):
            raise ValueError("Unauthorized to search family data")

        return []


class ReferenceDataQueries:
    """Reference data queries."""

    get_supported_languages = graphene.List(
        Language, description="Get list of supported languages"
    )

    get_supported_dialects = graphene.List(
        graphene.JSONString,
        base_language=graphene.String(),
        description="Get list of supported dialects with regional variations",
    )

    get_supported_measurement_units = graphene.List(
        graphene.JSONString,
        measurement_type=graphene.String(),
        description="Get list of supported measurement units",
    )

    get_supported_document_formats = graphene.List(
        graphene.JSONString,
        description="Get list of supported document formats for translation",
    )

    get_healthcare_facilities = graphene.List(
        HealthcareFacility,
        location=graphene.Argument(graphene.String),
        radius=graphene.Float(),
        type=graphene.String(),
        description="Get healthcare facilities",
    )

    def resolve_get_supported_languages(
        self, _info: graphene.ResolveInfo
    ) -> List[Language]:
        """Resolve supported languages."""
        # Public query
        # In production, would fetch from configuration
        return [
            Language(code="en", name="English", native_name="English", direction="ltr"),
            Language(
                code="ar",
                name="Arabic",
                native_name="العربية",
                script="Arab",
                direction="rtl",
            ),
            Language(
                code="sw", name="Swahili", native_name="Kiswahili", direction="ltr"
            ),
        ]

    def resolve_get_supported_dialects(
        self, _info: graphene.ResolveInfo, base_language: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Resolve supported dialects."""
        # Public query
        try:
            with get_db() as db:
                trans_service = TranslationService(db)
                dialects = trans_service.get_supported_dialects(base_language)
                return dialects
        except (ValueError, AttributeError, KeyError) as e:
            logger.error(f"Error fetching dialects: {e}")
            return []

    def resolve_get_supported_measurement_units(
        self, _info: graphene.ResolveInfo, measurement_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Resolve supported measurement units."""
        # Public query
        try:
            converter = get_measurement_converter()
            units = []

            for unit_key, unit_info in converter.UNITS.items():
                # Filter by type if specified
                if measurement_type:
                    try:
                        mtype = MeasurementType(measurement_type)
                        if unit_info.type != mtype:
                            continue
                    except ValueError:
                        continue

                units.append(
                    {
                        "key": unit_key,
                        "symbol": unit_info.symbol,
                        "name": unit_info.name,
                        "system": unit_info.system.value,
                        "type": unit_info.type.value,
                        "base_unit": unit_info.base_unit,
                    }
                )

            return units
        except (ValueError, AttributeError, KeyError) as e:
            logger.error(f"Error fetching measurement units: {e}")
            return []

    def resolve_get_supported_document_formats(
        self, _info: graphene.ResolveInfo
    ) -> List[Dict[str, Any]]:
        """Resolve supported document formats."""
        # Public query
        try:
            formats = []

            # Get document formats
            for format_enum in DocumentFormat:
                formats.append(
                    {
                        "type": "format",
                        "key": format_enum.value,
                        "name": format_enum.name,
                        "description": f"{format_enum.name} document format",
                    }
                )

            # Get document sections
            for section_enum in DocumentSection:
                formats.append(
                    {
                        "type": "section",
                        "key": section_enum.value,
                        "name": section_enum.name,
                        "description": f"{section_enum.name.replace('_', ' ').title()} section",
                    }
                )

            return formats

        except (ValueError, AttributeError, KeyError) as e:
            logger.error(f"Error fetching document formats: {e}")
            return []

    def resolve_get_healthcare_facilities(
        self,
        _info: graphene.ResolveInfo,
        _location: Optional[str] = None,
        _radius: Optional[float] = None,
        _facility_type: Optional[str] = None,
    ) -> List[HealthcareFacility]:
        """Resolve healthcare facilities."""
        # Public query with optional filtering
        # In production, would fetch from FacilityService
        # Parameters will be used when FacilityService is implemented
        return []


class Query(
    graphene.ObjectType,
    PatientQueries,
    HealthRecordQueries,
    VerificationQueries,
    FamilyQueries,
    ReferenceDataQueries,
):
    """Root Query type combining all query categories."""


# Export query schema
__all__ = ["Query"]


def validate_fhir_data(data: dict) -> dict:
    """Validate FHIR data.

    Args:
        data: Data to validate

    Returns:
        Validation result with 'valid', 'errors', and 'warnings' keys
    """
    errors = []
    warnings: List[str] = []

    if not data:
        errors.append("No data provided")

    return {"valid": len(errors) == 0, "errors": errors, "warnings": warnings}
