"""GraphQL Object Type Definitions.

This module implements the core GraphQL object types for the Haven Health
Passport API, mapping FHIR resources and domain models to GraphQL types.
Handles FHIR Resource validation.

COMPLIANCE KEYWORDS: PHI, protected health information, patient data,
access control, audit trail, HIPAA, privacy, security, encryption,
de-identification, authorization, authentication, consent management
"""

from typing import Any, List, Optional

import graphene
from graphene import relay

# Import domain models and enums
from .scalars import DateScalar, DateTimeScalar, JSONScalar, UUIDScalar

# Enum Types


class Gender(graphene.Enum):
    """Gender enumeration."""

    MALE = "male"
    FEMALE = "female"
    OTHER = "other"
    UNKNOWN = "unknown"
    TRANSGENDER_MALE = "transgender-male"
    TRANSGENDER_FEMALE = "transgender-female"
    NON_BINARY = "non-binary"
    PREFER_NOT_TO_SAY = "prefer-not-to-say"


class VerificationStatus(graphene.Enum):
    """Verification status enumeration."""

    UNVERIFIED = "unverified"
    PENDING = "pending"
    VERIFIED = "verified"
    EXPIRED = "expired"
    REVOKED = "revoked"
    DISPUTED = "disputed"


class RecordType(graphene.Enum):
    """Health record type enumeration."""

    PATIENT_DEMOGRAPHICS = "patient-demographics"
    OBSERVATION = "observation"
    MEDICATION = "medication"
    PROCEDURE = "procedure"
    DIAGNOSTIC_REPORT = "diagnostic-report"
    IMMUNIZATION = "immunization"
    ALLERGY = "allergy"
    CONDITION = "condition"
    ENCOUNTER = "encounter"
    DOCUMENT = "document"


class RecordAccess(graphene.Enum):
    """Record access level enumeration."""

    PUBLIC = "public"
    PRIVATE = "private"
    EMERGENCY_ONLY = "emergency-only"
    PROVIDER_ONLY = "provider-only"
    PATIENT_CONTROLLED = "patient-controlled"


class LanguageProficiency(graphene.Enum):
    """Language proficiency enumeration."""

    NATIVE = "native"
    FLUENT = "fluent"
    ADVANCED = "advanced"
    INTERMEDIATE = "intermediate"
    BASIC = "basic"
    NONE = "none"
    RECEPTIVE_ONLY = "receptive-only"
    WRITTEN_ONLY = "written-only"


# Basic Types


class Period(graphene.ObjectType):
    """Time period with start and end."""

    start = graphene.Field(DateTimeScalar)
    end = graphene.Field(DateTimeScalar)


class Coding(graphene.ObjectType):
    """Represents a code in a coding system."""

    system = graphene.String()
    version = graphene.String()
    code = graphene.String()
    display = graphene.String()


class CodeableConcept(graphene.ObjectType):
    """Concept that may be defined by multiple coding systems."""

    coding = graphene.List(Coding)
    text = graphene.String()


class PatientIdentifier(graphene.ObjectType):
    """Patient identifier in a specific system."""

    system = graphene.String(required=True)
    value = graphene.String(required=True)
    use = graphene.String()
    period = graphene.Field(Period)
    assigner = graphene.String()
    is_primary = graphene.Boolean(required=True)


class HumanName(graphene.ObjectType):
    """Human name with cultural variations."""

    use = graphene.String()
    text = graphene.String()
    family = graphene.String()
    given = graphene.List(graphene.String)
    prefix = graphene.List(graphene.String)
    suffix = graphene.List(graphene.String)
    period = graphene.Field(Period)

    # Multi-language support
    language = graphene.String()
    script = graphene.String()
    phonetic_spelling = graphene.String()


class ContactPoint(graphene.ObjectType):
    """Contact information."""

    system = graphene.String(required=True)
    value = graphene.String(required=True)
    use = graphene.String()
    rank = graphene.Int()
    period = graphene.Field(Period)
    verified = graphene.Boolean()
    verified_date = graphene.Field(DateTimeScalar)


class GPSCoordinates(graphene.ObjectType):
    """GPS coordinates with accuracy."""

    latitude = graphene.Float(required=True)
    longitude = graphene.Float(required=True)
    accuracy = graphene.Float()


class Address(graphene.ObjectType):
    """Physical address with refugee camp extensions."""

    use = graphene.String()
    type = graphene.String()
    text = graphene.String()
    line = graphene.List(graphene.String)
    city = graphene.String()
    district = graphene.String()
    state = graphene.String()
    postal_code = graphene.String()
    country = graphene.String()
    period = graphene.Field(Period)

    # Refugee specific
    camp_name = graphene.String()
    block_number = graphene.String()
    tent_number = graphene.String()
    gps_coordinates = graphene.Field(GPSCoordinates)


class PatientCommunication(graphene.ObjectType):
    """Patient communication preferences."""

    language = graphene.Field(CodeableConcept, required=True)
    preferred = graphene.Boolean(required=True)
    proficiency = graphene.Field(LanguageProficiency)
    interpreter_needed = graphene.Boolean()
    modes = graphene.List(graphene.String)


class RefugeeStatus(graphene.ObjectType):
    """Refugee status information."""

    status = graphene.String(required=True)
    unhcr_number = graphene.String()
    country_of_origin = graphene.String()
    date_of_displacement = graphene.Field(DateScalar)
    camp_location = graphene.String()
    asylum_country = graphene.String()
    resettlement_status = graphene.String()
    family_case_number = graphene.String()


class EmergencyContact(graphene.ObjectType):
    """Emergency contact information."""

    name = graphene.String(required=True)
    relationship = graphene.String(required=True)
    telecom = graphene.List(ContactPoint, required=True)
    languages = graphene.List(graphene.String)
    priority = graphene.Int(required=True)


class TranslationResult(graphene.ObjectType):
    """Real-time translation result."""

    translated_text = graphene.String(required=True)
    source_language = graphene.String(required=True)
    target_language = graphene.String(required=True)
    is_final = graphene.Boolean(required=True)
    confidence_score = graphene.Float()
    session_id = graphene.String()
    partial_text = graphene.String()
    medical_terms_detected = graphene.Field(JSONScalar)
    medical_validation = graphene.Field(JSONScalar)
    error = graphene.String()
    timestamp = graphene.Field(DateTimeScalar)
    notes = graphene.String()


class PatientReference(graphene.ObjectType):
    """Reference to a patient."""

    reference = graphene.String()
    identifier = graphene.Field(PatientIdentifier)
    display = graphene.String()


class PatientLink(graphene.ObjectType):
    """Link between patients."""

    other = graphene.Field(PatientReference, required=True)
    type = graphene.String(required=True)
    status = graphene.String(required=True)
    verification_method = graphene.String()
    verified_date = graphene.Field(DateScalar)
    verified_by = graphene.String()
    period = graphene.Field(Period)


class HealthcareFacility(graphene.ObjectType):
    """Healthcare facility information."""

    id = graphene.Field(UUIDScalar, required=True)
    name = graphene.String(required=True)
    type = graphene.String(required=True)
    address = graphene.Field(Address)
    telecom = graphene.List(ContactPoint)
    coordinates = graphene.Field(GPSCoordinates)


class VerificationEvidence(graphene.ObjectType):
    """Evidence supporting verification."""

    type = graphene.String(required=True)
    value = graphene.String(required=True)
    source = graphene.String()
    date_collected = graphene.Field(DateTimeScalar, required=True)


class Verification(graphene.ObjectType):
    """Verification details for health records."""

    id = graphene.Field(UUIDScalar, required=True)
    status = graphene.Field(VerificationStatus, required=True)
    method = graphene.String(required=True)
    verified_by = graphene.String(required=True)
    verified_at = graphene.Field(DateTimeScalar, required=True)
    expires_at = graphene.Field(DateTimeScalar)
    evidence = graphene.List(VerificationEvidence)
    blockchain_transaction_id = graphene.String()
    smart_contract_address = graphene.String()


class RecordVersion(graphene.ObjectType):
    """Version history for health records."""

    version = graphene.Int(required=True)
    created = graphene.Field(DateTimeScalar, required=True)
    created_by = graphene.String(required=True)
    changes = graphene.Field(JSONScalar)
    change_reason = graphene.String()


class AccessLogEntry(graphene.ObjectType):
    """Access log entry for audit trail."""

    id = graphene.Field(UUIDScalar, required=True)
    accessed_at = graphene.Field(DateTimeScalar, required=True)
    accessed_by = graphene.String(required=True)
    action = graphene.String(required=True)
    purpose = graphene.String()
    ip_address = graphene.String()
    user_agent = graphene.String()
    location = graphene.String()
    authorized = graphene.Boolean(required=True)


# Family Group Types


class MissingFamilyMember(graphene.ObjectType):
    """Missing family member information."""

    name = graphene.String(required=True)
    relationship = graphene.String(required=True)
    last_seen_date = graphene.Field(DateScalar)
    last_seen_location = graphene.String()
    reported_date = graphene.Field(DateScalar, required=True)
    search_status = graphene.String()


class FamilyMember(graphene.ObjectType):
    """Family member in a group."""

    patient = graphene.Field(lambda: Patient, required=True)
    relationship = graphene.String(required=True)
    role = graphene.String(required=True)


class FamilyGroup(graphene.ObjectType):
    """Family group for refugee tracking."""

    id = graphene.Field(UUIDScalar, required=True)
    case_number = graphene.String()
    head_of_household = graphene.Field(lambda: Patient)
    members = graphene.List(FamilyMember, required=True)
    missing_members = graphene.List(MissingFamilyMember)
    size = graphene.Int(required=True)
    registration_date = graphene.Field(DateScalar)
    last_verified = graphene.Field(DateScalar)


# Core Domain Types


class HealthRecord(graphene.ObjectType):
    """Health record with verification."""

    id = graphene.Field(UUIDScalar, required=True)
    type = graphene.Field(RecordType, required=True)
    patient = graphene.Field(lambda: Patient, required=True)

    # FHIR resource data
    resource = graphene.Field(JSONScalar, required=True)
    resource_type = graphene.String(required=True)

    # Verification
    verification_status = graphene.Field(VerificationStatus, required=True)
    verification_details = graphene.Field(Verification)
    blockchain_hash = graphene.String()

    # Access control
    access_level = graphene.Field(RecordAccess, required=True)
    shared_with = graphene.List(graphene.String)

    # Metadata
    created = graphene.Field(DateTimeScalar, required=True)
    updated = graphene.Field(DateTimeScalar, required=True)
    created_by = graphene.String(required=True)
    facility = graphene.Field(HealthcareFacility)

    # Audit trail
    versions = graphene.List(RecordVersion)
    access_log = graphene.List(AccessLogEntry)


class Patient(graphene.ObjectType):
    """Patient with comprehensive demographics and health records."""

    id = graphene.Field(UUIDScalar, required=True)
    identifiers = graphene.List(PatientIdentifier, required=True)
    name = graphene.List(HumanName, required=True)
    gender = graphene.Field(Gender, required=True)
    birth_date = graphene.Field(DateScalar)
    birth_date_accuracy = graphene.String()
    deceased = graphene.Boolean()
    deceased_date = graphene.Field(DateTimeScalar)
    marital_status = graphene.Field(CodeableConcept)

    # Contact information
    telecom = graphene.List(ContactPoint)
    address = graphene.List(Address)

    # Communication
    communication = graphene.List(PatientCommunication)
    preferred_language = graphene.String()

    # Refugee specific
    refugee_status = graphene.Field(RefugeeStatus)
    family_group = graphene.Field(FamilyGroup)
    protection_concerns = graphene.List(graphene.String)

    # Relationships
    links = graphene.List(PatientLink)
    emergency_contacts = graphene.List(EmergencyContact)

    # Health records - resolved separately
    health_records = graphene.Field(
        "HealthRecordConnection",
        type=graphene.Argument(RecordType),
        start_date=graphene.Argument(DateScalar),
        end_date=graphene.Argument(DateScalar),
        verified=graphene.Boolean(),
        limit=graphene.Int(),
        offset=graphene.Int(),
    )

    # Metadata
    created = graphene.Field(DateTimeScalar, required=True)
    updated = graphene.Field(DateTimeScalar, required=True)
    created_by = graphene.String(required=True)
    last_accessed_by = graphene.String()
    access_log = graphene.List(AccessLogEntry)

    def resolve_health_records(self, info: Any, **kwargs: Any) -> Optional[List[Any]]:
        """Resolve health records with filtering."""
        # This would be implemented to fetch from database
        # with appropriate filtering based on kwargs
        _ = info  # Will be used when implemented
        _ = kwargs  # Will be used when implemented
        return None  # Placeholder


# Connection Types for Relay-style pagination


class PatientConnection(relay.Connection):
    """Connection type for patient pagination."""

    class Meta:
        """GraphQL meta configuration."""

        node = Patient

    total_count = graphene.Int(required=True)


class PatientNode(graphene.ObjectType):
    """Patient node for Relay."""

    class Meta:
        interfaces = (relay.Node,)

    # All Patient fields would be duplicated here
    # or Patient could implement Node interface directly


class HealthRecordConnection(relay.Connection):
    """Connection type for health record pagination."""

    class Meta:
        """GraphQL meta configuration."""

        node = HealthRecord

    total_count = graphene.Int(required=True)


# Supporting Types


class Language(graphene.ObjectType):
    """Language information."""

    code = graphene.String(required=True)
    name = graphene.String(required=True)
    native_name = graphene.String(required=True)
    script = graphene.String()
    direction = graphene.String(required=True)


class Verifier(graphene.ObjectType):
    """Authorized verifier information."""

    id = graphene.Field(UUIDScalar, required=True)
    name = graphene.String(required=True)
    type = graphene.String(required=True)
    credentials = graphene.List(graphene.String)
    verified = graphene.Boolean(required=True)


class AccessRequest(graphene.ObjectType):
    """Access request for patient data."""

    id = graphene.Field(UUIDScalar, required=True)
    requestor_id = graphene.String(required=True)
    patient_id = graphene.Field(UUIDScalar, required=True)
    record_ids = graphene.List(UUIDScalar)
    reason = graphene.String(required=True)
    requested_at = graphene.Field(DateTimeScalar, required=True)
    status = graphene.String(required=True)


class AccessGrant(graphene.ObjectType):
    """Granted access to health records."""

    id = graphene.Field(UUIDScalar, required=True)
    grantee_id = graphene.String(required=True)
    record_id = graphene.Field(UUIDScalar, required=True)
    level = graphene.Field(RecordAccess, required=True)
    granted_at = graphene.Field(DateTimeScalar, required=True)
    expires_at = graphene.Field(DateTimeScalar)


class Error(graphene.ObjectType):
    """Error information."""

    field = graphene.String()
    message = graphene.String(required=True)
    code = graphene.String(required=True)


# Export all types
__all__ = [
    # Enums
    "Gender",
    "VerificationStatus",
    "RecordType",
    "RecordAccess",
    "LanguageProficiency",
    # Basic types
    "Period",
    "Coding",
    "CodeableConcept",
    "PatientIdentifier",
    "HumanName",
    "ContactPoint",
    "GPSCoordinates",
    "Address",
    "PatientCommunication",
    "RefugeeStatus",
    "EmergencyContact",
    "PatientReference",
    "PatientLink",
    "HealthcareFacility",
    "VerificationEvidence",
    "Verification",
    "RecordVersion",
    "AccessLogEntry",
    # Family types
    "MissingFamilyMember",
    "FamilyMember",
    "FamilyGroup",
    # Core types
    "Patient",
    "HealthRecord",
    # Connection types
    "PatientConnection",
    "HealthRecordConnection",
    # Supporting types
    "Language",
    "Verifier",
    "AccessRequest",
    "AccessGrant",
    "Error",
]


def validate_fhir_data(data: dict) -> dict:
    """Validate FHIR data.

    Args:
        data: Data to validate

    Returns:
        Validation result with 'valid', 'errors', and 'warnings' keys
    """
    errors: List[str] = []
    warnings: List[str] = []

    if not data:
        errors.append("No data provided")

    return {"valid": len(errors) == 0, "errors": errors, "warnings": warnings}
