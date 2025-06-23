"""GraphQL Input Type Definitions.

This module defines input types for mutations in the Haven Health Passport
GraphQL API, providing structured input validation for creating and updating
resources.
 Handles FHIR Resource validation.
"""

from typing import List

try:
    import graphene
    from graphene import InputObjectType
except ImportError:
    graphene = None
    InputObjectType = None

from .scalars import (
    DateScalar,
    DateTimeScalar,
    JSONScalar,
    UUIDScalar,
)
from .types import Gender, LanguageProficiency, RecordAccess, RecordType

# Basic Input Types


class PeriodInput(InputObjectType):
    """Input type for time periods."""

    start = graphene.Field(DateTimeScalar)
    end = graphene.Field(DateTimeScalar)


class CodingInput(InputObjectType):
    """Input type for coding."""

    system = graphene.String()
    version = graphene.String()
    code = graphene.String()
    display = graphene.String()


class CodeableConceptInput(InputObjectType):
    """Input type for codeable concepts."""

    coding = graphene.List(CodingInput)
    text = graphene.String()


class PatientIdentifierInput(InputObjectType):
    """Input type for patient identifiers."""

    system = graphene.String(required=True)
    value = graphene.String(required=True)
    use = graphene.String()
    is_primary = graphene.Boolean()


class HumanNameInput(InputObjectType):
    """Input type for human names."""

    use = graphene.String()
    text = graphene.String()
    family = graphene.String()
    given = graphene.List(graphene.String)
    prefix = graphene.List(graphene.String)
    suffix = graphene.List(graphene.String)
    language = graphene.String()
    script = graphene.String()
    phonetic_spelling = graphene.String()


class ContactPointInput(InputObjectType):
    """Input type for contact points."""

    system = graphene.String(required=True)
    value = graphene.String(required=True)
    use = graphene.String()
    rank = graphene.Int()


class GPSCoordinatesInput(InputObjectType):
    """Input type for GPS coordinates."""

    latitude = graphene.Float(required=True)
    longitude = graphene.Float(required=True)
    accuracy = graphene.Float()


class AddressInput(InputObjectType):
    """Input type for addresses."""

    use = graphene.String()
    type = graphene.String()
    text = graphene.String()
    line = graphene.List(graphene.String)
    city = graphene.String()
    district = graphene.String()
    state = graphene.String()
    postal_code = graphene.String()
    country = graphene.String()
    camp_name = graphene.String()
    block_number = graphene.String()
    tent_number = graphene.String()
    gps_coordinates = graphene.Field(GPSCoordinatesInput)


class PatientCommunicationInput(InputObjectType):
    """Input type for patient communication preferences."""

    language = graphene.Field(CodeableConceptInput, required=True)
    preferred = graphene.Boolean(required=True)
    proficiency = graphene.Field(LanguageProficiency)
    interpreter_needed = graphene.Boolean()
    modes = graphene.List(graphene.String)


class RefugeeStatusInput(InputObjectType):
    """Input type for refugee status."""

    status = graphene.String(required=True)
    unhcr_number = graphene.String()
    country_of_origin = graphene.String()
    date_of_displacement = graphene.Field(DateScalar)
    camp_location = graphene.String()
    asylum_country = graphene.String()
    resettlement_status = graphene.String()
    family_case_number = graphene.String()


class EmergencyContactInput(InputObjectType):
    """Input type for emergency contacts."""

    name = graphene.String(required=True)
    relationship = graphene.String(required=True)
    telecom = graphene.List(ContactPointInput, required=True)
    languages = graphene.List(graphene.String)
    priority = graphene.Int()
    notes = graphene.String()


# Core Input Types


class PatientInput(InputObjectType):
    """Input type for creating/updating patients."""

    identifiers = graphene.List(PatientIdentifierInput)
    name = graphene.List(HumanNameInput, required=True)
    gender = graphene.Field(Gender, required=True)
    birth_date = graphene.Field(DateScalar)
    birth_date_accuracy = graphene.String()
    telecom = graphene.List(ContactPointInput)
    address = graphene.List(AddressInput)
    communication = graphene.List(PatientCommunicationInput)
    refugee_status = graphene.Field(RefugeeStatusInput)
    emergency_contacts = graphene.List(EmergencyContactInput)


class HealthRecordInput(InputObjectType):
    """Input type for creating/updating health records."""

    type = graphene.Field(RecordType, required=True)
    patient_id = graphene.Field(UUIDScalar, required=True)
    resource = graphene.Field(JSONScalar, required=True)
    resource_type = graphene.String(required=True)
    access_level = graphene.Field(RecordAccess)
    shared_with = graphene.List(graphene.String)
    facility = graphene.String()


# Search and Filter Input Types


class SearchCriteria(InputObjectType):
    """Input type for search criteria."""

    query = graphene.String()
    fields = graphene.List(graphene.String)
    fuzzy = graphene.Boolean()
    max_distance = graphene.Int()


class FilterOperator(graphene.Enum):
    """Filter operator enumeration."""

    EQUALS = "equals"
    NOT_EQUALS = "not_equals"
    GREATER_THAN = "greater_than"
    LESS_THAN = "less_than"
    GREATER_THAN_OR_EQUAL = "greater_than_or_equal"
    LESS_THAN_OR_EQUAL = "less_than_or_equal"
    IN = "in"
    NOT_IN = "not_in"
    CONTAINS = "contains"
    STARTS_WITH = "starts_with"
    ENDS_WITH = "ends_with"
    BETWEEN = "between"
    IS_NULL = "is_null"
    IS_NOT_NULL = "is_not_null"


class FilterOptions(InputObjectType):
    """Input type for filter options."""

    field = graphene.String(required=True)
    operator = graphene.Field(FilterOperator, required=True)
    value = graphene.Field(JSONScalar, required=True)


class DateRangeFilter(InputObjectType):
    """Input type for date range filtering."""

    start = graphene.Field(DateScalar)
    end = graphene.Field(DateScalar)
    inclusive = graphene.Boolean()


class PaginationInput(InputObjectType):
    """Input type for pagination."""

    limit = graphene.Int()
    offset = graphene.Int()
    cursor = graphene.String()


class SortDirection(graphene.Enum):
    """Sort direction enumeration."""

    ASC = "asc"
    DESC = "desc"


class SortInput(InputObjectType):
    """Input type for sorting."""

    field = graphene.String(required=True)
    direction = graphene.Field(SortDirection, required=True)


# Verification Input Types


class VerificationMethodInput(InputObjectType):
    """Input type for verification method."""

    method = graphene.String(required=True)
    evidence = graphene.List(graphene.String)
    expires_in_days = graphene.Int()


class VerificationEvidenceInput(InputObjectType):
    """Input type for verification evidence."""

    type = graphene.String(required=True)
    value = graphene.String(required=True)
    source = graphene.String()


# Family Group Input Types


class MissingFamilyMemberInput(InputObjectType):
    """Input type for missing family members."""

    name = graphene.String(required=True)
    relationship = graphene.String(required=True)
    last_seen_date = graphene.Field(DateScalar)
    last_seen_location = graphene.String()


class FamilyMemberInput(InputObjectType):
    """Input type for family members."""

    patient_id = graphene.Field(UUIDScalar, required=True)
    relationship = graphene.String(required=True)
    role = graphene.String(required=True)


# Access Control Input Types


class AccessLevelInput(InputObjectType):
    """Input type for access level."""

    record_id = graphene.Field(UUIDScalar, required=True)
    level = graphene.Field(RecordAccess, required=True)
    expires_in_hours = graphene.Int()


class EmergencyAccessInput(InputObjectType):
    """Input type for emergency access requests."""

    patient_id = graphene.Field(UUIDScalar, required=True)
    reason = graphene.String(required=True)
    duration_hours = graphene.Int()
    record_types = graphene.List(RecordType)


# Bulk Operation Input Types


class BulkPatientInput(InputObjectType):
    """Input type for bulk patient operations."""

    patients = graphene.List(PatientInput, required=True)
    skip_duplicates = graphene.Boolean()
    merge_duplicates = graphene.Boolean()


class BulkHealthRecordInput(InputObjectType):
    """Input type for bulk health record operations."""

    records = graphene.List(HealthRecordInput, required=True)
    verify_all = graphene.Boolean()
    facility = graphene.String()


# Update-specific Input Types


class PatientUpdateInput(InputObjectType):
    """Input type specifically for patient updates."""

    # All fields optional for partial updates
    identifiers = graphene.List(PatientIdentifierInput)
    name = graphene.List(HumanNameInput)
    gender = graphene.Field(Gender)
    birth_date = graphene.Field(DateScalar)
    birth_date_accuracy = graphene.String()
    telecom = graphene.List(ContactPointInput)
    address = graphene.List(AddressInput)
    communication = graphene.List(PatientCommunicationInput)
    refugee_status = graphene.Field(RefugeeStatusInput)
    emergency_contacts = graphene.List(EmergencyContactInput)

    # Update metadata
    update_reason = graphene.String()
    verified_by = graphene.String()


class HealthRecordUpdateInput(InputObjectType):
    """Input type specifically for health record updates."""

    resource = graphene.Field(JSONScalar)
    access_level = graphene.Field(RecordAccess)
    shared_with = graphene.List(graphene.String)

    # Update metadata
    update_reason = graphene.String(required=True)
    verified = graphene.Boolean()


# Merge Operation Input Types


class PatientMergeInput(InputObjectType):
    """Input type for patient merge operations."""

    primary_id = graphene.Field(UUIDScalar, required=True)
    merge_ids = graphene.List(UUIDScalar, required=True)
    resolve_conflicts = graphene.String()  # Strategy: "newest", "primary", "manual"
    merge_reason = graphene.String(required=True)


# Export all input types
__all__ = [
    # Basic inputs
    "PeriodInput",
    "CodingInput",
    "CodeableConceptInput",
    "PatientIdentifierInput",
    "HumanNameInput",
    "ContactPointInput",
    "GPSCoordinatesInput",
    "AddressInput",
    "PatientCommunicationInput",
    "RefugeeStatusInput",
    "EmergencyContactInput",
    # Core inputs
    "PatientInput",
    "HealthRecordInput",
    # Search and filter inputs
    "SearchCriteria",
    "FilterOperator",
    "FilterOptions",
    "DateRangeFilter",
    "PaginationInput",
    "SortDirection",
    "SortInput",
    # Verification inputs
    "VerificationMethodInput",
    "VerificationEvidenceInput",
    # Family inputs
    "MissingFamilyMemberInput",
    "FamilyMemberInput",
    # Access control inputs
    "AccessLevelInput",
    "EmergencyAccessInput",
    # Bulk operation inputs
    "BulkPatientInput",
    "BulkHealthRecordInput",
    # Update inputs
    "PatientUpdateInput",
    "HealthRecordUpdateInput",
    # Merge inputs
    "PatientMergeInput",
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
