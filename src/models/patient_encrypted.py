"""Example patient model with encrypted fields."""

from datetime import date, datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy import Boolean, Column, DateTime, Integer, String
from sqlalchemy.sql.schema import Column as ColumnType

from src.healthcare.fhir_validator import FHIRValidator
from src.healthcare.hipaa_access_control import AccessLevel, require_phi_access
from src.models.base import BaseModel
from src.models.db_types import UUID
from src.models.encrypted_fields import (
    EncryptedAddress,
    EncryptedEmail,
    EncryptedJSON,
    EncryptedPhone,
    EncryptedSSN,
    EncryptedString,
    EncryptedText,
)
from src.utils.logging import get_logger

logger = get_logger(__name__)


class PatientEncrypted(BaseModel):
    """Patient model with encrypted sensitive fields."""

    __tablename__ = "patients_encrypted_example"
    __fhir_resource__ = "Patient"  # FHIR Resource type

    # Non-encrypted fields (IDs, flags, etc.)
    patient_id: ColumnType[Any] = Column(
        UUID(as_uuid=True), unique=True, nullable=False
    )
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    created_by: ColumnType[Any] = Column(UUID(as_uuid=True))

    # Encrypted PII fields
    first_name: ColumnType[str] = Column(EncryptedString(), nullable=False)
    last_name: ColumnType[str] = Column(EncryptedString(), nullable=False)
    middle_name: ColumnType[str] = Column(EncryptedString())

    # Searchable encrypted email (allows equality searches)
    email: ColumnType[str] = Column(EncryptedEmail(), unique=True)

    # Encrypted contact information
    phone_primary: ColumnType[str] = Column(EncryptedPhone())
    phone_secondary: ColumnType[str] = Column(EncryptedPhone())

    # Encrypted sensitive identifiers
    ssn: ColumnType[str] = Column(EncryptedSSN())
    passport_number: ColumnType[str] = Column(EncryptedString())
    national_id: ColumnType[str] = Column(EncryptedString())

    # Encrypted date of birth (stored as string for encryption)
    date_of_birth_encrypted: ColumnType[str] = Column(EncryptedString())

    # Encrypted address as JSON
    address: ColumnType[str] = Column(EncryptedAddress())

    # Encrypted emergency contact
    emergency_contact: ColumnType[Any] = Column(EncryptedJSON())

    # Encrypted medical information
    blood_type: ColumnType[str] = Column(EncryptedString())
    allergies: ColumnType[Any] = Column(EncryptedJSON())
    medical_conditions: ColumnType[Any] = Column(EncryptedJSON())
    medications: ColumnType[Any] = Column(EncryptedJSON())

    # Encrypted notes
    medical_notes: ColumnType[str] = Column(EncryptedText())
    special_needs: ColumnType[str] = Column(EncryptedText())

    # Encryption metadata
    encryption_key_id = Column(String(255))
    encrypted_at = Column(DateTime)
    encryption_version = Column(Integer, default=1)

    def __init__(self, **kwargs: Any) -> None:
        """Initialize with FHIR validator."""
        super().__init__(**kwargs)
        self.validator = FHIRValidator()

    def validate_fhir(self) -> bool:
        """Validate FHIR Patient resource compliance.

        Returns:
            True if valid FHIR Patient resource
        """
        try:
            # Basic validation
            if not self.first_name or not self.last_name:
                return False

            # Validate identifiers if present
            if self.ssn and not self._validate_ssn_format():
                return False

            return True
        except (ValueError, AttributeError) as e:
            # Log validation error
            logger.error(f"Patient validation error: {e}")
            return False

    def _validate_ssn_format(self) -> bool:
        """Validate SSN format."""
        if not self.ssn:
            return True
        # Basic SSN validation
        ssn_clean = self.ssn.replace("-", "")
        return len(ssn_clean) == 9 and ssn_clean.isdigit()

    @property
    def date_of_birth(self) -> Optional[date]:
        """Get date of birth as date object."""
        if self.date_of_birth_encrypted:
            try:
                return date.fromisoformat(str(self.date_of_birth_encrypted))
            except (ValueError, TypeError) as e:
                logger.warning(f"Invalid date format in date_of_birth_encrypted: {e}")
                return None
        return None

    @date_of_birth.setter
    def date_of_birth(self, value: Optional[date]) -> None:
        """Set date of birth from date object."""
        if value:
            self.date_of_birth_encrypted = value.isoformat()  # type: ignore
        else:
            self.date_of_birth_encrypted = None  # type: ignore

    def get_full_name(self) -> str:
        """Get patient's full name."""
        parts = [self.first_name]
        if self.middle_name:
            parts.append(self.middle_name)
        parts.append(self.last_name)
        return " ".join(filter(None, [str(p) for p in parts if p]))

    def mask_ssn(self) -> str:
        """Get masked SSN for display."""
        if self.ssn and len(self.ssn) >= 4:
            return f"***-**-{self.ssn[-4:]}"
        return "***-**-****"

    @require_phi_access(AccessLevel.READ)
    def to_dict(self, include_pii: bool = False) -> Dict[str, Any]:
        """
        Convert to dictionary with PII control.

        Args:
            include_pii: Whether to include personally identifiable information

        Returns:
            Dictionary representation
        """
        base_dict = {
            "id": str(self.id),
            "patient_id": str(self.patient_id),
            "is_active": self.is_active,
            "is_verified": self.is_verified,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

        if include_pii:
            base_dict.update(
                {
                    "first_name": self.first_name,
                    "last_name": self.last_name,
                    "middle_name": self.middle_name,
                    "email": self.email,
                    "phone_primary": self.phone_primary,
                    "phone_secondary": self.phone_secondary,
                    "date_of_birth": (
                        self.date_of_birth.isoformat() if self.date_of_birth else None
                    ),
                    "address": self.address,
                    "emergency_contact": self.emergency_contact,
                    "blood_type": self.blood_type,
                    "allergies": self.allergies,
                    "medical_conditions": self.medical_conditions,
                    "medications": self.medications,
                }
            )
        else:
            # Return masked/limited information
            base_dict.update(
                {
                    "name_initials": f"{self.first_name[0] if self.first_name else ''}.{self.last_name[0] if self.last_name else ''}.",
                    "has_email": bool(self.email),
                    "has_phone": bool(self.phone_primary),
                    "has_emergency_contact": bool(self.emergency_contact),
                    "age_years": self._calculate_age() if self.date_of_birth else None,
                }
            )

        return base_dict

    def _calculate_age(self) -> Optional[int]:
        """Calculate age from date of birth."""
        if self.date_of_birth:
            today = date.today()
            age = today.year - self.date_of_birth.year
            if (today.month, today.day) < (
                self.date_of_birth.month,
                self.date_of_birth.day,
            ):
                age -= 1
            return age
        return None

    def encrypt_field(self, field_name: str, value: Any) -> None:
        """
        Manually encrypt a specific field.

        Args:
            field_name: Name of field to encrypt
            value: Value to encrypt
        """
        setattr(self, field_name, value)

        # Update encryption metadata
        self.encrypted_at = datetime.now(timezone.utc)  # type: ignore

        # Log encryption
        logger.info(f"Encrypted field {field_name} for patient {self.patient_id}")

    def rotate_encryption(self, new_key_id: str) -> None:
        """
        Rotate encryption to new key.

        Args:
            new_key_id: New encryption key ID
        """
        # This would be handled by the encryption service
        # Re-encrypting all fields with the new key
        old_key_id = self.encryption_key_id
        self.encryption_key_id = new_key_id  # type: ignore
        self.encryption_version += 1  # type: ignore
        self.encrypted_at = datetime.now(timezone.utc)  # type: ignore

        logger.info(
            f"Rotated encryption for patient {self.patient_id} "
            f"from key {old_key_id} to {new_key_id}"
        )

    @classmethod
    @require_phi_access(AccessLevel.READ)
    def search_by_email(cls, session: Any, email: str) -> Optional["PatientEncrypted"]:
        """
        Search for patient by email (using searchable encryption).

        Args:
            session: Database session
            email: Email to search for

        Returns:
            Patient if found
        """
        # The SearchableEncrypted field type handles the search
        return session.query(cls).filter(cls.email == email.lower().strip()).first()  # type: ignore

    def __repr__(self) -> str:
        """Return string representation."""
        return f"<PatientEncrypted(id={self.id}, patient_id={self.patient_id})>"


# Example usage functions
@require_phi_access(AccessLevel.WRITE)
def create_encrypted_patient(
    session: Any, patient_data: Dict[str, Any]
) -> PatientEncrypted:
    """
    Create a new patient with encrypted fields.

    Args:
        session: Database session
        patient_data: Patient data dictionary

    Returns:
        Created patient
    """
    patient = PatientEncrypted(
        patient_id=patient_data.get("patient_id"),
        first_name=patient_data.get("first_name"),
        last_name=patient_data.get("last_name"),
        middle_name=patient_data.get("middle_name"),
        email=patient_data.get("email"),
        phone_primary=patient_data.get("phone_primary"),
        phone_secondary=patient_data.get("phone_secondary"),
        ssn=patient_data.get("ssn"),
        date_of_birth=patient_data.get("date_of_birth"),
        address=patient_data.get("address"),
        emergency_contact=patient_data.get("emergency_contact"),
        blood_type=patient_data.get("blood_type"),
        allergies=patient_data.get("allergies", []),
        medical_conditions=patient_data.get("medical_conditions", []),
        medications=patient_data.get("medications", []),
        created_by=patient_data.get("created_by"),
        encrypted_at=datetime.now(timezone.utc),
    )

    session.add(patient)
    session.commit()

    logger.info(f"Created encrypted patient record: {patient.patient_id}")

    return patient


@require_phi_access(AccessLevel.WRITE)
def update_encrypted_field(
    session: Any, patient_id: UUID, field_name: str, new_value: Any
) -> bool:
    """
    Update a single encrypted field.

    Args:
        session: Database session
        patient_id: Patient ID
        field_name: Field to update
        new_value: New value

    Returns:
        Success status
    """
    try:
        patient = (
            session.query(PatientEncrypted)
            .filter(PatientEncrypted.patient_id == patient_id)
            .first()
        )

        if not patient:
            return False

        # Update field (encryption happens automatically)
        setattr(patient, field_name, new_value)
        patient.updated_at = datetime.now(timezone.utc)

        session.commit()

        logger.info(f"Updated encrypted field {field_name} for patient {patient_id}")

        return True

    except (ValueError, AttributeError, RuntimeError) as e:
        logger.error(f"Error updating encrypted field: {e}")
        session.rollback()
        return False
