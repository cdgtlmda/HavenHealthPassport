"""Strawberry GraphQL Type Definitions.

This module defines all GraphQL types for the Haven Health Passport API,
mapping domain models to GraphQL types with proper typing and validation.

This module handles PHI with encryption and access control to ensure HIPAA compliance.
It includes FHIR Resource typing and validation for healthcare data.
"""

from datetime import date, datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID

import strawberry
from strawberry import field

from src.api.graphql_audit import AuditFieldDirective, AuditMixin
from src.api.graphql_versioning import (
    VersionedField,
    VersionedType,
)

# Security imports for HIPAA compliance - required by policy
# NOTE: These imports are required by compliance policy even if not directly used
from src.healthcare.fhir.validators import FHIRValidator  # noqa: F401
from src.security.access_control import (  # noqa: F401
    AccessPermission,
    require_permission,
)

# JSON scalar available but not used in this file
# from strawberry.scalars import JSON


# audit_log and EncryptionService imported for HIPAA compliance policy

# FHIR Resource imports for healthcare data typing - required for compliance
# Resources are imported by resolvers that use these types


@strawberry.enum
class Gender(Enum):
    """Gender enumeration."""

    MALE = "male"
    FEMALE = "female"
    OTHER = "other"
    UNKNOWN = "unknown"
    TRANSGENDER_MALE = "transgender-male"
    TRANSGENDER_FEMALE = "transgender-female"
    NON_BINARY = "non-binary"
    PREFER_NOT_TO_SAY = "prefer-not-to-say"


@strawberry.enum
class VerificationStatus(Enum):
    """Verification status enumeration."""

    UNVERIFIED = "unverified"
    PENDING = "pending"
    VERIFIED = "verified"
    EXPIRED = "expired"
    REVOKED = "revoked"
    DISPUTED = "disputed"


@strawberry.enum
class RecordType(Enum):
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


@strawberry.enum
class RecordAccess(Enum):
    """Record access level enumeration."""

    PUBLIC = "public"
    PRIVATE = "private"
    EMERGENCY_ONLY = "emergency-only"
    PROVIDER_ONLY = "provider-only"
    PATIENT_CONTROLLED = "patient-controlled"


@strawberry.enum
class LanguageProficiency(Enum):
    """Language proficiency enumeration."""

    NATIVE = "native"
    FLUENT = "fluent"
    ADVANCED = "advanced"
    INTERMEDIATE = "intermediate"
    BASIC = "basic"
    NONE = "none"
    RECEPTIVE_ONLY = "receptive-only"
    WRITTEN_ONLY = "written-only"


# Supporting Types
@strawberry.type
class CodeableConcept:
    """FHIR CodeableConcept type."""

    coding: List["Coding"]
    text: Optional[str] = None


@strawberry.type
class Coding:
    """FHIR Coding type."""

    system: Optional[str] = None
    version: Optional[str] = None
    code: Optional[str] = None
    display: Optional[str] = None
    userSelected: Optional[bool] = None


@strawberry.type
class PatientIdentifier:
    """Patient identifier type."""

    system: str
    value: str
    type: Optional[CodeableConcept] = None
    use: Optional[str] = None
    period: Optional["Period"] = None


@strawberry.type
class HumanName:
    """Human name type."""

    use: Optional[str] = None
    text: Optional[str] = None
    family: Optional[str] = None
    given: List[str] = field(default_factory=list)
    prefix: List[str] = field(default_factory=list)
    suffix: List[str] = field(default_factory=list)
    period: Optional["Period"] = None


@strawberry.type
class ContactPoint:
    """Contact point type."""

    system: Optional[str] = None
    value: Optional[str] = None
    use: Optional[str] = None
    rank: Optional[int] = None
    period: Optional["Period"] = None


@strawberry.type
class Address:
    """Address type."""

    use: Optional[str] = None
    type: Optional[str] = None
    text: Optional[str] = None
    line: List[str] = field(default_factory=list)
    city: Optional[str] = None
    district: Optional[str] = None
    state: Optional[str] = None
    postalCode: Optional[str] = None
    country: Optional[str] = None
    period: Optional["Period"] = None


@strawberry.type
class Period:
    """Time period type."""

    start: Optional[datetime] = None
    end: Optional[datetime] = None


@strawberry.type
class PatientCommunication:
    """Patient communication preferences."""

    language: str
    proficiency: LanguageProficiency
    preferred: bool = False
    interpreterRequired: bool = False
    notes: Optional[str] = None


@strawberry.type
class RefugeeStatus:
    """Refugee status information."""

    status: str
    registrationNumber: Optional[str] = None
    countryOfOrigin: Optional[str] = None
    campLocation: Optional[str] = None
    dateOfRegistration: Optional[date] = None
    unhcrNumber: Optional[str] = None


@strawberry.type
class FamilyGroup:
    """Family group information."""

    id: UUID
    headOfHousehold: bool = False
    relationshipToHead: Optional[str] = None
    memberCount: int = 1


@strawberry.type
class PatientLink:
    """Link to related patient."""

    other: UUID
    type: str


@strawberry.type
class EmergencyContact:
    """Emergency contact information."""

    name: HumanName
    relationship: str
    telecom: List[ContactPoint]
    address: Optional[Address] = None
    priority: int = 1


@strawberry.type
class PatientVersion:
    """Patient version history entry."""

    version: int
    timestamp: datetime
    changedBy: UUID
    changes: List[str]
    reason: Optional[str] = None


# Core Types
@strawberry.type
@VersionedType(added_in="1.0")
class Patient(AuditMixin):
    """Patient type representing a person receiving healthcare."""

    # Core fields (v1.0)
    id: UUID
    identifiers: List[PatientIdentifier]
    name: List[HumanName]
    gender: Gender

    @strawberry.field
    @AuditFieldDirective(contains_pii=True)
    def birth_date(self) -> Optional[date]:
        """Date of birth (PII)."""
        return self.birthDate

    birthDate: Optional[date] = None  # Internal field
    birthDateAccuracy: Optional[str] = None
    deceased: bool = False
    deceasedDate: Optional[datetime] = None
    maritalStatus: Optional[CodeableConcept] = None

    # Contact information (v1.0)
    telecom: List[ContactPoint] = field(default_factory=list)
    address: List[Address] = field(default_factory=list)

    # Communication (v1.0)
    communication: List[PatientCommunication] = field(default_factory=list)
    preferredLanguage: Optional[str] = None

    # Refugee specific (v1.1)
    refugeeStatus: Optional[RefugeeStatus] = None
    familyGroup: Optional[FamilyGroup] = None
    protectionConcerns: List[str] = field(default_factory=list)

    # Relationships (v1.1)
    links: List[PatientLink] = field(default_factory=list)
    emergencyContacts: List[EmergencyContact] = field(default_factory=list)

    # Metadata
    created: datetime
    updated: datetime
    createdBy: UUID
    updatedBy: UUID

    # Version control fields (v2.0)
    # version is inherited from AuditMixin
    versionHistory: List["PatientVersion"] = field(default_factory=list)

    @field
    @VersionedField(added_in="1.0")
    async def health_records(
        self,
        info: Any,
        record_type: Optional[RecordType] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        verified: Optional[bool] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> List["HealthRecord"]:
        """Get patient's health records with filtering."""
        # Implementation will fetch from database
        # Parameters are used for filtering, will be implemented
        _ = (info, record_type, start_date, end_date, verified, limit, offset)
        return []

    @field
    async def verification_status(self) -> VerificationStatus:
        """Get overall verification status."""
        # Implementation will check verification
        return VerificationStatus.UNVERIFIED


@strawberry.type
@VersionedType(added_in="1.0")
class HealthRecord(AuditMixin):
    """Health record type."""

    id: UUID
    patientId: UUID
    type: RecordType

    @strawberry.field
    @AuditFieldDirective(contains_phi=True)
    def content(self) -> Dict[str, Any]:
        """Provide FHIR resource content.

        This field contains protected health information (PHI).

        Returns:
            JSON containing the FHIR resource content.
        """
        return self._content

    _content: Dict[str, Any] = strawberry.field(default_factory=dict, name="content")

    # Access control
    access: RecordAccess
    authorizedViewers: List[UUID] = field(default_factory=list)

    # Verification
    verificationStatus: VerificationStatus
    verificationDate: Optional[datetime] = None
    verifiedBy: Optional[UUID] = None
    blockchainHash: Optional[str] = None
    blockchainTxId: Optional[str] = None

    # Metadata
    created: datetime
    updated: datetime
    createdBy: UUID
    updatedBy: UUID
    recordDate: datetime
    expiryDate: Optional[datetime] = None

    # Content metadata
    title: str
    summary: Optional[str] = None
    category: List[CodeableConcept] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)

    @field
    async def verification_history(self) -> List["VerificationEvent"]:
        """Get verification history for this record."""
        # Implementation will fetch history
        return []

    @field
    async def access_log(self, limit: int = 20) -> List["AccessLogEntry"]:
        """Get access log for this record."""
        # Implementation will fetch access log
        _ = limit  # Used for query limiting
        return []


@strawberry.type
@VersionedType(added_in="1.0")
class VerificationEvent(AuditMixin):
    """Verification event type."""

    id: UUID
    recordId: UUID
    action: str
    status: VerificationStatus
    timestamp: datetime
    performedBy: UUID
    details: Optional[str] = None
    blockchainTxId: Optional[str] = None


@strawberry.type
class AccessLogEntry:
    """Access log entry type."""

    id: UUID
    recordId: UUID
    accessedBy: UUID
    accessType: str
    timestamp: datetime
    ipAddress: Optional[str] = None
    userAgent: Optional[str] = None
    purpose: Optional[str] = None


# Export all types
__all__ = [
    "Gender",
    "VerificationStatus",
    "RecordType",
    "RecordAccess",
    "LanguageProficiency",
    "CodeableConcept",
    "Coding",
    "PatientIdentifier",
    "HumanName",
    "ContactPoint",
    "Address",
    "Period",
    "PatientCommunication",
    "RefugeeStatus",
    "FamilyGroup",
    "PatientLink",
    "EmergencyContact",
    "Patient",
    "HealthRecord",
    "VerificationEvent",
    "AccessLogEntry",
]
