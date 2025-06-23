"""Patient database model.

This model handles encrypted patient data with access control validation.
Manages FHIR Patient Resource conversion and validation.
"""

import enum
from datetime import date, datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional
from uuid import UUID as UUIDType

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Table,
    Text,
)
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import Mapped, Session, mapped_column, object_session, relationship

from src.models.db_types import JSONB, UUID

from .base import BaseModel

if TYPE_CHECKING:
    from src.healthcare.fhir_validator import FHIRValidator  # noqa: F401


class Gender(enum.Enum):
    """Gender enumeration."""

    MALE = "male"
    FEMALE = "female"
    OTHER = "other"
    UNKNOWN = "unknown"


class VerificationStatus(enum.Enum):
    """Verification status enumeration."""

    UNVERIFIED = "unverified"
    PENDING = "pending"
    VERIFIED = "verified"
    EXPIRED = "expired"
    REVOKED = "revoked"


class RefugeeStatus(enum.Enum):
    """Refugee status enumeration."""

    REFUGEE = "refugee"
    ASYLUM_SEEKER = "asylum_seeker"
    INTERNALLY_DISPLACED = "internally_displaced"
    STATELESS = "stateless"
    RETURNEE = "returnee"
    OTHER = "other"


# Association table for patient family relationships
patient_family_association = Table(
    "patient_family_association",
    BaseModel.metadata,
    Column(
        "patient_id", UUID(as_uuid=True), ForeignKey("patients.id"), primary_key=True
    ),
    Column(
        "family_member_id",
        UUID(as_uuid=True),
        ForeignKey("patients.id"),
        primary_key=True,
    ),
    Column(
        "relationship_type",
        String(50),
        default="family",
        comment="Type of relationship: parent, child, sibling, spouse, guardian, etc.",
    ),
    Column(
        "created_at",
        DateTime,
        default=datetime.utcnow,
        comment="When this relationship was recorded",
    ),
)


class FamilyRelationship(BaseModel):
    """Association object for patient family relationships with relationship type."""

    __tablename__ = "patient_family_relationships"

    patient_id: Mapped[UUIDType] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patients.id"), primary_key=True
    )
    family_member_id: Mapped[UUIDType] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patients.id"), primary_key=True
    )
    relationship_type = Column(String(50), nullable=False, default="family")

    # Relationships
    patient = relationship(
        "Patient",
        foreign_keys="[FamilyRelationship.patient_id]",
        back_populates="family_relationships",
    )
    family_member = relationship(
        "Patient", foreign_keys="[FamilyRelationship.family_member_id]"
    )

    @property
    def relationship_description(self) -> str:
        """Get human-readable relationship description."""
        relationship_map: dict[str, str] = {
            "mother": "Mother",
            "father": "Father",
            "child": "Child",
            "sibling": "Sibling",
            "spouse": "Spouse",
            "guardian": "Guardian",
            "grandparent": "Grandparent",
            "grandchild": "Grandchild",
            "aunt": "Aunt",
            "uncle": "Uncle",
            "cousin": "Cousin",
            "family": "Family Member",
        }
        if self.relationship_type:
            result = relationship_map.get(str(self.relationship_type))
            if result:
                return result
            return str(self.relationship_type).title()
        return "Unknown"


class Patient(BaseModel):
    """Patient model representing an individual in the system."""

    __tablename__ = "patients"

    # Basic Demographics
    given_name = Column(String(100), nullable=False)
    family_name = Column(String(100), nullable=False)
    middle_names = Column(String(200))
    preferred_name = Column(String(100))

    # Multi-language name support
    names_in_languages = Column(
        JSONB, default=dict
    )  # {"ar": {"given": "محمد", "family": "أحمد"}}

    # Identification
    date_of_birth = Column(Date)
    estimated_birth_year = Column(Integer)  # For when exact date unknown
    place_of_birth = Column(String(200))
    gender: Mapped[Gender] = mapped_column(
        Enum(Gender), nullable=False, default=Gender.UNKNOWN
    )

    # Refugee-specific fields
    refugee_status: Mapped[Optional[RefugeeStatus]] = mapped_column(
        Enum(RefugeeStatus), nullable=True
    )
    unhcr_number = Column(String(50), unique=True, index=True)
    displacement_date = Column(Date)
    origin_country = Column(String(2))  # ISO country code
    current_camp = Column(String(200))
    camp_section = Column(String(50))

    # Contact Information
    phone_number = Column(String(20))
    alternate_phone = Column(String(20))
    email = Column(String(255))
    current_address = Column(Text)
    gps_coordinates = Column(JSONB)  # {"lat": 0.0, "lng": 0.0}

    # Emergency Contact
    emergency_contact_name = Column(String(200))
    emergency_contact_phone = Column(String(20))
    emergency_contact_relationship = Column(String(50))

    # Language and Communication
    primary_language = Column(String(10))  # ISO language code
    languages_spoken = Column(JSONB, default=list)  # ["en", "ar", "fr"]
    communication_preferences = Column(
        JSONB, default=dict
    )  # {"sms": true, "calls": false}
    requires_interpreter = Column(Boolean, default=False)

    # Cultural Context
    cultural_dietary_restrictions = Column(JSONB, default=list)
    religious_affiliation = Column(String(100))
    cultural_considerations = Column(Text)

    # Medical Information Summary (detailed records in HealthRecord)
    blood_type = Column(String(5))  # A+, B-, etc.
    allergies = Column(JSONB, default=list)
    chronic_conditions = Column(JSONB, default=list)
    current_medications = Column(JSONB, default=list)

    # Verification and Security
    verification_status: Mapped[VerificationStatus] = mapped_column(
        Enum(VerificationStatus), nullable=False, default=VerificationStatus.UNVERIFIED
    )
    identity_documents = Column(JSONB, default=list)  # List of document references
    biometric_data_hash = Column(String(255))  # Hashed biometric reference
    photo_url = Column(String(500))

    # Access Control
    access_permissions = Column(JSONB, default=dict)
    cross_border_permissions = Column(
        JSONB, default=dict
    )  # {"countries": ["KE", "UG"], "expires": "2024-12-31"}
    data_sharing_consent = Column(JSONB, default=dict)

    # System Fields
    created_by_organization = Column(String(200))
    managing_organization = Column(String(200))
    last_updated_by: Mapped[Optional[UUIDType]] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    import_source = Column(String(100))  # Where data was imported from

    # Relationships
    health_records = relationship(
        "HealthRecord",
        back_populates="patient",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )

    verifications = relationship(
        "Verification",
        back_populates="patient",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )

    access_logs = relationship(
        "AccessLog",
        back_populates="patient",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )

    auth = relationship(
        "UserAuth",
        back_populates="patient",
        uselist=False,
        cascade="all, delete-orphan",
    )

    file_attachments = relationship(
        "FileAttachment",
        back_populates="patient",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )

    documents = relationship(
        "Document",
        back_populates="patient",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )

    # Family relationships (using association object for relationship type)
    family_relationships = relationship(
        "FamilyRelationship",
        foreign_keys="FamilyRelationship.patient_id",
        back_populates="patient",
        cascade="all, delete-orphan",
    )

    @property
    def family_members(self) -> List[tuple]:
        """Get all family members with their relationships."""
        return [
            (rel.family_member, rel.relationship_type)
            for rel in self.family_relationships
        ]

    # Indexes for performance
    __table_args__ = (
        Index("idx_patient_name", "family_name", "given_name"),
        Index("idx_patient_unhcr", "unhcr_number"),
        Index("idx_patient_phone", "phone_number"),
        Index("idx_patient_camp", "current_camp", "camp_section"),
        Index("idx_patient_verification", "verification_status"),
    )

    @hybrid_property
    def full_name(self) -> str:
        """Get patient's full name."""
        parts = []
        if self.given_name:
            parts.append(str(self.given_name))
        if self.middle_names:
            parts.append(str(self.middle_names))
        if self.family_name:
            parts.append(str(self.family_name))
        return " ".join(parts)

    @hybrid_property
    def age(self) -> Optional[int]:
        """Calculate patient's age."""
        if self.date_of_birth:
            today = date.today()
            age_calc = (
                today.year
                - self.date_of_birth.year
                - (
                    (today.month, today.day)
                    < (self.date_of_birth.month, self.date_of_birth.day)
                )
            )
            return int(age_calc)
        elif self.estimated_birth_year:
            return date.today().year - int(self.estimated_birth_year)
        return None

    @property
    def is_verified(self) -> bool:
        """Check if patient is verified."""
        return bool(self.verification_status == VerificationStatus.VERIFIED)

    def get_name_in_language(self, language_code: str) -> Dict[str, str]:
        """Get patient name in specific language."""
        # Handle JSONB column which could be None or dict
        names_data = self.names_in_languages

        if names_data is not None and language_code in names_data:
            name_dict = names_data.get(language_code, {})
            if isinstance(name_dict, dict):
                return {str(k): str(v) for k, v in name_dict.items()}

        return {
            "given": str(self.given_name or ""),
            "family": str(self.family_name or ""),
        }

    def add_family_member(
        self, family_member: "Patient", relationship_type: str
    ) -> None:
        """Add a family member relationship with proper relationship type tracking.

        Args:
            family_member: The Patient object representing the family member
            relationship_type: Type of relationship (mother, father, child, sibling, spouse, etc.)
        """
        # Create the family relationship with the proper type
        family_rel = FamilyRelationship(
            patient_id=self.id,
            family_member_id=family_member.id,
            relationship_type=relationship_type.lower(),
        )

        # Add to session if available
        session = object_session(self)
        if session:
            session.add(family_rel)
        else:
            # If no session, add to the relationship collection
            self.family_relationships.append(family_rel)

    def grant_cross_border_access(self, countries: List[str], expires: date) -> None:
        """Grant cross-border access permissions."""
        current_perms = self.cross_border_permissions
        permissions: Dict[str, Any] = dict(current_perms) if current_perms else {}
        permissions.update(
            {
                "countries": countries,
                "expires": expires.isoformat(),
                "granted_at": date.today().isoformat(),
            }
        )
        self.cross_border_permissions = permissions  # type: ignore[assignment]

    def check_cross_border_access(self, country_code: str) -> bool:
        """Check if patient has access to a specific country."""
        if not self.cross_border_permissions:
            return False

        countries = self.cross_border_permissions.get("countries", [])
        expires = self.cross_border_permissions.get("expires")

        if country_code not in countries:
            return False

        if expires and date.fromisoformat(expires) < date.today():
            return False

        return True

    def validate_fhir(self) -> Dict[str, Any]:
        """Validate patient data for FHIR compliance.

        Returns:
            Validation result with 'valid', 'errors', and 'warnings' keys
        """
        # Initialize validator
        from src.healthcare.fhir_validator import (  # pylint: disable=import-outside-toplevel # noqa: F811
            FHIRValidator,
        )

        validator = FHIRValidator()

        # Convert to FHIR format for validation
        fhir_data = self.to_fhir()

        # Validate the FHIR patient resource
        result = validator.validate_patient(fhir_data)
        return dict(result)

    def to_fhir(self) -> Dict[str, Any]:
        """Convert to FHIR Patient resource format."""
        identifiers: List[Dict[str, Any]] = []
        names: List[Dict[str, Any]] = []
        telecoms: List[Dict[str, Any]] = []

        fhir_patient: Dict[str, Any] = {
            "resourceType": "Patient",
            "id": str(self.id),
            "identifier": identifiers,
            "name": names,
            "telecom": telecoms,
            "gender": self.gender.value if self.gender else "unknown",
            "birthDate": self.date_of_birth.isoformat() if self.date_of_birth else None,
        }

        # Add UNHCR identifier
        if self.unhcr_number:
            identifiers.append(
                {
                    "system": "https://www.unhcr.org/identifiers",
                    "value": self.unhcr_number,
                    "use": "official",
                }
            )

        # Add name
        names.append(
            {
                "use": "official",
                "family": self.family_name,
                "given": [self.given_name] if self.given_name else [],
            }
        )

        # Add phone contact
        if self.phone_number:
            telecoms.append(
                {"system": "phone", "value": self.phone_number, "use": "mobile"}
            )

        # Add email contact
        if self.email:
            telecoms.append({"system": "email", "value": self.email, "use": "home"})

        return fhir_patient

    @classmethod
    def search(
        cls,
        session: Session,
        name: Optional[str] = None,
        unhcr_number: Optional[str] = None,
        phone: Optional[str] = None,
        camp: Optional[str] = None,
        verification_status: Optional[VerificationStatus] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List["Patient"]:
        """Search for patients with various criteria."""
        query = cls.query_active(session)

        if name:
            # Search in both given and family names
            search_term = f"%{name}%"
            query = query.filter(
                (cls.given_name.ilike(search_term))
                | (cls.family_name.ilike(search_term))
                | (cls.preferred_name.ilike(search_term))
            )

        if unhcr_number:
            query = query.filter(cls.unhcr_number == unhcr_number)

        if phone:
            query = query.filter(
                (cls.phone_number == phone) | (cls.alternate_phone == phone)
            )

        if camp:
            query = query.filter(cls.current_camp.ilike(f"%{camp}%"))

        if verification_status:
            query = query.filter(cls.verification_status == verification_status)

        return query.limit(limit).offset(offset).all()

    def __repr__(self) -> str:
        """Return string representation."""
        return f"<Patient(id={self.id}, name='{self.full_name}', unhcr='{self.unhcr_number}')>"
