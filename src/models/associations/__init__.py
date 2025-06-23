"""Association tables for many-to-many relationships in Haven Health Passport.

This module defines SQLAlchemy association tables for:
- Patient-Provider relationships
- Patient-Organization relationships
- Provider-Organization relationships

# FHIR Compliance: These associations map to FHIR CareTeam and PractitionerRole Resources
# All relationships are validated to ensure FHIR R4 compliance for care coordination
"""

from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String, Table, Text
from sqlalchemy.dialects.postgresql import UUID

from src.models.base import BaseModel

# Patient-Provider Association Table
patient_provider_association = Table(
    "patient_provider_association",
    BaseModel.metadata,
    Column(
        "patient_id",
        UUID(as_uuid=True),
        ForeignKey("patients.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "provider_id",
        UUID(as_uuid=True),
        ForeignKey("user_auth.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("relationship_type", String(50), nullable=False, default="primary_care"),
    Column("consent_given", Boolean, default=True, nullable=False),
    Column("consent_scope", Text),  # JSON string describing what access is granted
    Column(
        "valid_from", DateTime(timezone=True), default=datetime.utcnow, nullable=False
    ),
    Column("valid_until", DateTime(timezone=True)),  # NULL means no expiration
    Column(
        "created_at", DateTime(timezone=True), default=datetime.utcnow, nullable=False
    ),
    Column("created_by", UUID(as_uuid=True), ForeignKey("user_auth.id")),
    Column("notes", Text),
)


# Patient-Organization Association Table
patient_organization_association = Table(
    "patient_organization_association",
    BaseModel.metadata,
    Column(
        "patient_id",
        UUID(as_uuid=True),
        ForeignKey("patients.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "organization_id",
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("relationship_type", String(50), nullable=False, default="care_provider"),
    Column("consent_given", Boolean, default=True, nullable=False),
    Column("consent_scope", Text),  # JSON string describing what access is granted
    Column(
        "valid_from", DateTime(timezone=True), default=datetime.utcnow, nullable=False
    ),
    Column("valid_until", DateTime(timezone=True)),  # NULL means no expiration
    Column(
        "created_at", DateTime(timezone=True), default=datetime.utcnow, nullable=False
    ),
    Column("created_by", UUID(as_uuid=True), ForeignKey("user_auth.id")),
    Column("notes", Text),
    Column(
        "camp_location", String(200)
    ),  # Specific camp/location where relationship is valid
    Column("program_enrollment", Text),  # Programs the patient is enrolled in
)


# Provider-Organization Association Table (providers working for organizations)
provider_organization_association = Table(
    "provider_organization_association",
    BaseModel.metadata,
    Column(
        "provider_id",
        UUID(as_uuid=True),
        ForeignKey("user_auth.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "organization_id",
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("role", String(100), nullable=False, default="healthcare_provider"),
    Column("department", String(200)),
    Column("active", Boolean, default=True, nullable=False),
    Column(
        "start_date", DateTime(timezone=True), default=datetime.utcnow, nullable=False
    ),
    Column("end_date", DateTime(timezone=True)),
    Column(
        "created_at", DateTime(timezone=True), default=datetime.utcnow, nullable=False
    ),
    Column(
        "updated_at",
        DateTime(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    ),
)
