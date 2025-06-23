"""
Example SQLAlchemy models with column encryption.

This module demonstrates how to use column encryption in
SQLAlchemy models for healthcare data.
"""

from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict

from sqlalchemy import JSON, Column, DateTime, Integer
from sqlalchemy.ext.declarative import declarative_base

from src.healthcare.hipaa_access_control import AccessLevel, require_phi_access

from .healthcare_encryption import FieldSensitivity, HealthcareFieldEncryption
from .sqlalchemy_encryption import EncryptedColumnMixin, EncryptedType

# FHIR Resource type imports
if TYPE_CHECKING:
    pass

# Create base class
Base = declarative_base()

# Initialize encryptor (in production, this would come from config)
healthcare_encryptor = HealthcareFieldEncryption(
    kms_key_id="arn:aws:kms:us-east-1:123456789012:key/your-key"
)


class Patient(Base, EncryptedColumnMixin):  # type: ignore[misc,valid-type]
    """Patient model with encrypted sensitive fields."""

    __tablename__ = "patients"
    __encryptor__ = healthcare_encryptor

    # Public fields
    patient_id = Column(Integer, primary_key=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Searchable sensitive fields (deterministic encryption)
    ssn: Column[str] = Column(
        EncryptedType(
            healthcare_encryptor,
            "patients",
            "ssn",
            FieldSensitivity.SEARCHABLE_SENSITIVE,
        )
    )
    medical_record_number: Column[str] = Column(
        EncryptedType(
            healthcare_encryptor,
            "patients",
            "medical_record_number",
            FieldSensitivity.SEARCHABLE_SENSITIVE,
        )
    )
    email: Column[str] = Column(
        EncryptedType(
            healthcare_encryptor,
            "patients",
            "email",
            FieldSensitivity.SEARCHABLE_SENSITIVE,
        )
    )
    phone: Column[str] = Column(
        EncryptedType(
            healthcare_encryptor,
            "patients",
            "phone",
            FieldSensitivity.SEARCHABLE_SENSITIVE,
        )
    )
    # Non-searchable sensitive fields (randomized encryption)
    first_name: Column[str] = Column(
        EncryptedType(
            healthcare_encryptor, "patients", "first_name", FieldSensitivity.SENSITIVE
        )
    )
    last_name: Column[str] = Column(
        EncryptedType(
            healthcare_encryptor, "patients", "last_name", FieldSensitivity.SENSITIVE
        )
    )
    date_of_birth: Column[str] = Column(
        EncryptedType(
            healthcare_encryptor,
            "patients",
            "date_of_birth",
            FieldSensitivity.SENSITIVE,
        )
    )
    address: Column[str] = Column(
        EncryptedType(
            healthcare_encryptor, "patients", "address", FieldSensitivity.SENSITIVE
        )
    )

    # Protected fields
    gender: Column[str] = Column(
        EncryptedType(
            healthcare_encryptor, "patients", "gender", FieldSensitivity.PROTECTED
        )
    )
    blood_type: Column[str] = Column(
        EncryptedType(
            healthcare_encryptor, "patients", "blood_type", FieldSensitivity.PROTECTED
        )
    )

    # FHIR resource cache
    fhir_resource = Column(JSON, nullable=True)

    @require_phi_access(AccessLevel.READ)
    def to_fhir(self) -> Dict[str, Any]:
        """Convert to FHIR Patient resource."""
        fhir_patient = {
            "resourceType": "Patient",
            "id": str(self.patient_id),
            "identifier": [
                {
                    "system": "http://havenhealthpassport.org/mrn",
                    "value": self.medical_record_number,
                }
            ],
            "name": [
                {
                    "use": "official",
                    "family": self.last_name,
                    "given": [self.first_name],
                }
            ],
            "telecom": [],
            "gender": self.gender.lower() if self.gender else None,
            "birthDate": self.date_of_birth.isoformat() if self.date_of_birth else None,
            "address": [],
        }

        # Add contact info if available
        if self.email:
            telecom = fhir_patient.get("telecom", [])
            if isinstance(telecom, list):
                telecom.append({"system": "email", "value": self.email, "use": "home"})

        if self.phone:
            telecom = fhir_patient.get("telecom", [])
            if isinstance(telecom, list):
                telecom.append(
                    {"system": "phone", "value": self.phone, "use": "mobile"}
                )

        # Add address if available
        if self.address:
            address = fhir_patient.get("address", [])
            if isinstance(address, list):
                address.append({"use": "home", "text": self.address})

        return fhir_patient

    def validate_fhir_compliance(self) -> bool:
        """Validate if model data is FHIR compliant."""
        # Patient must have at least identifier or name
        has_identifier = bool(self.medical_record_number or self.ssn)
        has_name = bool(self.first_name or self.last_name)

        return has_identifier or has_name


class MedicalRecord(Base, EncryptedColumnMixin):  # type: ignore[misc,valid-type]
    """Medical record model with encrypted fields."""

    __tablename__ = "medical_records"
    __encryptor__ = healthcare_encryptor

    # Public fields
    record_id = Column(Integer, primary_key=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Searchable sensitive
    patient_id: Column[int] = Column(
        EncryptedType(
            healthcare_encryptor,
            "medical_records",
            "patient_id",
            FieldSensitivity.SEARCHABLE_SENSITIVE,
        )
    )

    # Sensitive fields
    diagnosis: Column[str] = Column(
        EncryptedType(
            healthcare_encryptor,
            "medical_records",
            "diagnosis",
            FieldSensitivity.SENSITIVE,
        ),
        nullable=False,
    )

    # FHIR resource cache
    fhir_resource = Column(JSON, nullable=True)

    @require_phi_access(AccessLevel.READ)
    def to_fhir_observation(self) -> Dict[str, Any]:
        """Convert to FHIR Observation resource."""
        return {
            "resourceType": "Observation",
            "id": str(self.record_id),
            "status": "final",
            "code": {
                "coding": [
                    {
                        "system": "http://loinc.org",
                        "code": "29308-4",
                        "display": "Diagnosis",
                    }
                ],
                "text": "Diagnosis",
            },
            "subject": {"reference": f"Patient/{self.patient_id}"},
            "effectiveDateTime": self.created_at.isoformat() + "Z",
            "valueString": self.diagnosis,
        }

    def validate_fhir_compliance(self) -> bool:
        """Validate if medical record is FHIR compliant."""
        # Must have patient reference and diagnosis
        return bool(self.patient_id and self.diagnosis)
