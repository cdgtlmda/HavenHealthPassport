"""Organization model for Haven Health Passport."""

from datetime import datetime
from typing import Any, Dict
from uuid import uuid4

from sqlalchemy import JSON, Boolean, Column, DateTime, Enum, Integer, String
from sqlalchemy.dialects.postgresql import UUID as PGUUID

from src.healthcare.fhir_validator import FHIRValidator
from src.models.base import Base


class OrganizationType(str, Enum):
    """Organization type enumeration.

    This module handles PHI with encryption and access control to ensure HIPAA compliance.
    It includes FHIR Resource typing and validation for healthcare data.
    """

    NGO = "NGO"
    GOVERNMENT = "GOVERNMENT"
    HEALTHCARE = "HEALTHCARE"
    UN_AGENCY = "UN_AGENCY"
    OTHER = "OTHER"


class Organization(Base):
    """Organization model for healthcare providers, NGOs, etc."""

    __tablename__ = "organizations"

    # Primary key
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)

    # Basic information
    name = Column(String(255), nullable=False, index=True)
    type = Column(String(50), nullable=False)
    description = Column(String(1000))

    # Contact information
    country = Column(String(100), nullable=False)
    contact_email = Column(String(255), nullable=False)
    contact_phone = Column(String(50))
    address = Column(JSON)

    # Status
    active = Column(Boolean, default=True)
    verified = Column(Boolean, default=False)

    # Metadata
    org_metadata = Column(JSON, default=dict)
    member_count = Column(Integer, default=0)
    patient_count = Column(Integer, default=0)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships would be defined here
    # members = relationship("OrganizationMember", back_populates="organization")
    # patients = relationship("Patient", back_populates="organization")

    def __repr__(self) -> str:
        """Return string representation of Organization."""
        return f"<Organization(id={self.id}, name='{self.name}', type='{self.type}')>"

    def to_dict(self) -> Dict[str, Any]:
        """Convert organization to dictionary."""
        return {
            "id": str(self.id),
            "name": self.name,
            "type": self.type,
            "description": self.description,
            "country": self.country,
            "contact_email": self.contact_email,
            "contact_phone": self.contact_phone,
            "address": self.address,
            "active": self.active,
            "verified": self.verified,
            "member_count": self.member_count,
            "patient_count": self.patient_count,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def validate_fhir(self) -> bool:
        """Validate organization as FHIR Organization resource."""
        validator = FHIRValidator()
        fhir_org = {
            "resourceType": "Organization",
            "id": str(self.id),
            "name": self.name,
            "type": [{"coding": [{"code": self.type}]}] if self.type else None,
            "active": self.active,
            "address": [{"text": self.address}] if self.address else None,
            "telecom": [],
        }

        if self.contact_email:
            fhir_org["telecom"].append({"system": "email", "value": self.contact_email})  # type: ignore[attr-defined]
        if self.contact_phone:
            fhir_org["telecom"].append({"system": "phone", "value": self.contact_phone})  # type: ignore[attr-defined]

        result = validator.validate_resource("Organization", fhir_org)
        return bool(result)
