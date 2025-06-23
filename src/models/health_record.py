"""Health record database model.

This model handles encrypted health records with access control validation.
Manages FHIR DocumentReference Resource conversion and validation.
"""

import enum
import json
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Union

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import Session, relationship

from src.healthcare.hipaa_access_control import (
    AccessLevel,
    audit_phi_access,
    require_phi_access,
)
from src.healthcare.medication_resource import MedicationResource
from src.healthcare.observation_resource import ObservationResource
from src.models.base import BaseModel
from src.models.db_types import JSONB, UUID
from src.utils.encryption import EncryptionService
from src.utils.key_rotation import KeyRotationManager

if TYPE_CHECKING:
    from src.healthcare.fhir_validator import FHIRValidator  # noqa: F401

# FHIR resource type for this model
__fhir_resource__ = "DocumentReference"


class RecordType(enum.Enum):
    """Type of health record."""

    VITAL_SIGNS = "vital_signs"
    LAB_RESULT = "lab_result"
    IMMUNIZATION = "immunization"
    MEDICATION = "medication"
    PROCEDURE = "procedure"
    DIAGNOSIS = "diagnosis"
    ALLERGY = "allergy"
    CLINICAL_NOTE = "clinical_note"
    IMAGING = "imaging"
    DISCHARGE_SUMMARY = "discharge_summary"
    REFERRAL = "referral"
    PRESCRIPTION = "prescription"
    VACCINATION_CERTIFICATE = "vaccination_certificate"
    SCREENING = "screening"
    EMERGENCY_CONTACT = "emergency_contact"


class RecordStatus(enum.Enum):
    """Status of the health record."""

    DRAFT = "draft"
    FINAL = "final"
    AMENDED = "amended"
    CORRECTED = "corrected"
    CANCELLED = "cancelled"
    ENTERED_IN_ERROR = "entered_in_error"


class RecordPriority(enum.Enum):
    """Priority level of the record."""

    ROUTINE = "routine"
    URGENT = "urgent"
    EMERGENCY = "emergency"
    STAT = "stat"


class HealthRecord(BaseModel):
    """Health record model for storing medical information."""

    __tablename__ = "health_records"

    # Record Identification
    record_type: RecordType = Column(Enum(RecordType), nullable=False, index=True)  # type: ignore[assignment]
    record_subtype = Column(String(50))  # More specific categorization
    title = Column(String(255), nullable=False)

    # Patient Relationship
    patient_id: UUID = Column(  # type: ignore[assignment]
        UUID(as_uuid=True),
        ForeignKey("patients.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Record Content (Encrypted)
    encrypted_content = Column(Text, nullable=False)  # Main health data, encrypted
    content_type = Column(String(50), default="application/json")  # Content format
    encryption_key_id = Column(String(100))  # Which key was used for encryption

    # Metadata (Unencrypted for searching/filtering)
    record_date = Column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )
    effective_date = Column(
        DateTime(timezone=True)
    )  # When the information is clinically relevant
    status: RecordStatus = Column(Enum(RecordStatus), nullable=False, default=RecordStatus.DRAFT)  # type: ignore[assignment]
    priority: RecordPriority = Column(Enum(RecordPriority), default=RecordPriority.ROUTINE)  # type: ignore[assignment]

    # Provider Information
    provider_id: Optional[UUID] = Column(UUID(as_uuid=True))  # type: ignore[assignment]
    provider_name = Column(String(200))
    provider_organization = Column(String(200))
    facility_name = Column(String(200))
    facility_location = Column(String(200))

    # Categorization and Tags
    categories = Column(
        JSONB, default=list
    )  # ["diabetes", "hypertension", "routine-checkup"]
    tags = Column(JSONB, default=list)  # Custom tags for organization
    icd_codes = Column(JSONB, default=list)  # ICD-10 codes if applicable
    loinc_codes = Column(JSONB, default=list)  # LOINC codes for lab results

    # Attachments and Media
    attachments = Column(JSONB, default=list)  # List of attachment references
    thumbnail_url = Column(String(500))  # For imaging records

    # Access Control
    access_level = Column(
        String(20), default="standard"
    )  # standard, sensitive, restricted
    authorized_viewers = Column(JSONB, default=list)  # List of authorized user/org IDs
    require_2fa_to_view = Column(Boolean, default=False)

    # Audit Trail
    version = Column(Integer, default=1)
    previous_version_id: Optional[UUID] = Column(UUID(as_uuid=True))  # type: ignore[assignment]
    change_reason = Column(Text)
    verified_by: Optional[UUID] = Column(UUID(as_uuid=True))  # type: ignore[assignment]
    verified_at = Column(DateTime(timezone=True))

    # Emergency Access
    emergency_accessible = Column(Boolean, default=True)
    emergency_contact_notified = Column(Boolean, default=False)

    # Integration Fields
    source_system = Column(String(100))  # Which system created this
    external_id = Column(String(200))  # ID in source system
    import_timestamp = Column(DateTime(timezone=True))

    # Blockchain Reference
    blockchain_hash = Column(String(255))  # Hash stored on blockchain
    blockchain_tx_id = Column(String(255))  # Transaction ID

    # Relationships
    patient = relationship("Patient", back_populates="health_records")
    file_attachments = relationship("FileAttachment", back_populates="health_record")
    documents = relationship("Document", back_populates="health_record")

    # Indexes for performance
    __table_args__ = (
        Index("idx_health_record_patient_type", "patient_id", "record_type"),
        Index("idx_health_record_date", "record_date"),
        Index("idx_health_record_status", "status"),
        Index("idx_health_record_provider", "provider_id"),
        UniqueConstraint(
            "patient_id", "external_id", "source_system", name="uq_external_record"
        ),
    )

    def __init__(self, **kwargs: Any) -> None:
        """Initialize health record with encryption."""
        # Initialize instance attributes
        self._encryption_service = None
        self._fhir_validator = None  # Lazy load to avoid circular import

        # Extract content to encrypt it
        content = kwargs.pop("content", None)
        super().__init__(**kwargs)

        if content:
            self.set_content(content)

    @property
    def encryption_service(self) -> EncryptionService:
        """Get encryption service instance."""
        if not hasattr(self, "_encryption_service") or self._encryption_service is None:
            self._encryption_service = EncryptionService()
        return self._encryption_service

    @property
    def fhir_validator(self) -> "FHIRValidator":
        """Get FHIR validator instance (lazy loaded to avoid circular import)."""
        if not hasattr(self, "_fhir_validator") or self._fhir_validator is None:
            from src.healthcare.fhir_validator import (  # pylint: disable=import-outside-toplevel # noqa: F811
                FHIRValidator,
            )

            self._fhir_validator = FHIRValidator()
        return self._fhir_validator

    @require_phi_access(AccessLevel.WRITE)
    @audit_phi_access("set_health_record_content")
    def set_content(self, content: Union[Dict[str, Any], Any]) -> None:
        """Set and encrypt the record content."""
        # Convert content to JSON string
        if isinstance(content, dict):
            content_str = json.dumps(content)
        else:
            content_str = str(content)

        # Encrypt the content
        self.encrypted_content = self.encryption_service.encrypt(content_str)  # type: ignore[assignment]

        # Store the key ID used for encryption
        key_manager = KeyRotationManager()
        key_id, _ = key_manager.get_active_key()
        self.encryption_key_id = key_id  # type: ignore[assignment]

    @require_phi_access(AccessLevel.READ)
    @audit_phi_access("get_health_record_content")
    def get_content(self) -> Dict[str, Any]:
        """Decrypt and return the record content."""
        if not self.encrypted_content:
            return {}

        try:
            # Get the appropriate key if using key rotation
            if self.encryption_key_id:
                key_manager = KeyRotationManager()
                key = key_manager.get_key_by_id(self.encryption_key_id)  # type: ignore[arg-type]
                if key:
                    # Use specific key for decryption
                    # This would need custom implementation
                    pass

            # Decrypt the content
            decrypted = self.encryption_service.decrypt(self.encrypted_content)  # type: ignore[arg-type]

            # Parse JSON if applicable
            if self.content_type == "application/json":
                return json.loads(decrypted)  # type: ignore[no-any-return]
            return {"data": decrypted}

        except (json.JSONDecodeError, ValueError, TypeError) as e:
            # Log decryption failure
            return {"error": "Unable to decrypt content", "details": str(e)}

    @hybrid_property
    def is_emergency_record(self) -> bool:
        """Check if this is an emergency record."""
        return self.priority in [RecordPriority.EMERGENCY, RecordPriority.STAT]

    @hybrid_property
    def is_verified(self) -> bool:
        """Check if record has been verified."""
        return self.verified_by is not None and self.verified_at is not None

    def add_attachment(
        self, file_url: str, file_type: str, description: str = ""
    ) -> None:
        """Add an attachment reference to the record."""
        attachments_list = list(self.attachments)
        attachment = {
            "url": file_url,
            "type": file_type,
            "description": description,
            "uploaded_at": datetime.utcnow().isoformat(),
        }
        attachments_list.append(attachment)
        self.attachments = attachments_list  # type: ignore[assignment]

    def authorize_viewer(
        self, viewer_id: str, expiry: Optional[datetime] = None
    ) -> None:
        """Authorize a specific viewer for this record."""
        viewers_list = list(self.authorized_viewers)
        authorization = {
            "viewer_id": viewer_id,
            "authorized_at": datetime.utcnow().isoformat(),
            "expires_at": expiry.isoformat() if expiry else None,
        }
        viewers_list.append(authorization)
        self.authorized_viewers = viewers_list  # type: ignore[assignment]

    def check_access(self, user_id: str, user_role: Optional[str] = None) -> bool:
        """Check if a user has access to this record."""
        # Emergency access
        if self.emergency_accessible and user_role in ["emergency_responder", "doctor"]:
            return True

        # Check authorized viewers
        if self.authorized_viewers:
            viewers_list: List[Any] = (
                list(self.authorized_viewers) if self.authorized_viewers else []
            )
            for auth in viewers_list:
                if auth["viewer_id"] == user_id:
                    # Check expiry
                    if auth.get("expires_at"):
                        expiry = datetime.fromisoformat(auth["expires_at"])
                        if expiry < datetime.utcnow():
                            continue
                    return True

        # Check if user is the provider
        if str(self.provider_id) == user_id:
            return True

        return False

    def create_amended_version(
        self, changes: Dict[str, Any], reason: str
    ) -> "HealthRecord":
        """Create an amended version of this record."""
        # Create new record with same base data
        new_record = HealthRecord(
            patient_id=self.patient_id,
            record_type=self.record_type,
            record_subtype=self.record_subtype,
            title=self.title,
            provider_id=self.provider_id,
            provider_name=self.provider_name,
            provider_organization=self.provider_organization,
            facility_name=self.facility_name,
            facility_location=self.facility_location,
            categories=self.categories,
            tags=self.tags,
            access_level=self.access_level,
            emergency_accessible=self.emergency_accessible,
        )

        # Set the amended content
        current_content = self.get_content()
        current_content.update(changes)
        new_record.set_content(current_content)

        # Update version tracking
        new_record.version = self.version + 1  # type: ignore[assignment]
        new_record.previous_version_id = self.id  # type: ignore[assignment]
        new_record.status = RecordStatus.AMENDED
        new_record.change_reason = reason  # type: ignore[assignment]

        # Mark this record as superseded
        self.status = RecordStatus.AMENDED

        return new_record

    def validate_fhir_content(self, content: Dict[str, Any]) -> bool:
        """Validate content against FHIR DocumentReference schema.

        Args:
            content: Content to validate

        Returns:
            True if valid FHIR DocumentReference
        """
        if hasattr(self, "fhir_validator"):
            # Extract resource type from content
            resource_type = content.get("resourceType", "Unknown")
            result = self.fhir_validator.validate_resource(resource_type, content)
            return bool(result.get("valid", False))
        return True  # Default to valid if validator not available

    def to_fhir(self) -> Dict[str, Any]:
        """Convert to appropriate FHIR resource format."""
        content = self.get_content()

        # Map to appropriate FHIR resource based on record type
        if self.record_type == RecordType.VITAL_SIGNS:
            # Create observation resource
            obs_resource = ObservationResource()
            observation_data = {
                "id": str(self.id),
                "status": "final",
                "code": content.get(
                    "code",
                    {
                        "system": "http://loinc.org",
                        "code": "8867-4",
                        "display": "Heart rate",
                    },
                ),
                "subject": f"Patient/{self.patient_id}",
                "effective": (
                    self.date_recorded.isoformat() if self.date_recorded else None
                ),
                "value": content.get("value"),
                "interpretation": content.get("interpretation"),
                "reference_range": content.get("reference_range"),
            }
            obs = obs_resource.create_resource(observation_data)
            # Convert to dict - the resource might not have a dict() method
            return (
                obs
                if isinstance(obs, dict)
                else (
                    vars(obs)
                    if hasattr(obs, "__dict__")
                    else {"resourceType": "Observation", "data": observation_data}
                )
            )

        elif self.record_type == RecordType.MEDICATION:
            # Create medication resource
            med_resource = MedicationResource()
            medication_data = {
                "id": str(self.id),
                "code": content.get(
                    "code",
                    {
                        "system": "http://www.nlm.nih.gov/research/umls/rxnorm",
                        "code": "0",
                        "display": "Unknown",
                    },
                ),
                "status": content.get("status", "active"),
                "manufacturer": content.get("manufacturer"),
                "form": content.get("form"),
                "amount": content.get("amount"),
                "ingredient": content.get("ingredient", []),
                "batch": content.get("batch"),
            }
            medication = med_resource.create_resource(medication_data)
            # Convert to dict - the resource might not have a dict() method
            return (
                medication
                if isinstance(medication, dict)
                else (
                    vars(medication)
                    if hasattr(medication, "__dict__")
                    else {"resourceType": "Medication", "data": medication_data}
                )
            )

        # Default: return content as-is for other record types
        return content  # type: ignore[no-any-return]

    @classmethod
    def get_patient_records(
        cls,
        session: Session,
        patient_id: UUID,
        record_types: Optional[List[RecordType]] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        status: Optional[RecordStatus] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List["HealthRecord"]:
        """Get health records for a patient with filters."""
        query = cls.query_active(session).filter(cls.patient_id == patient_id)  # type: ignore[arg-type]

        if record_types:
            query = query.filter(cls.record_type.in_(record_types))  # type: ignore[attr-defined]

        if start_date:
            query = query.filter(cls.record_date >= start_date)

        if end_date:
            query = query.filter(cls.record_date <= end_date)

        if status:
            query = query.filter(cls.status == status)  # type: ignore[arg-type]

        return query.order_by(cls.record_date.desc()).limit(limit).offset(offset).all()

    def __repr__(self) -> str:
        """Return string representation."""
        return f"<HealthRecord(id={self.id}, type='{self.record_type.value}', patient={self.patient_id})>"
