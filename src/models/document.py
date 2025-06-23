"""Document model for health records.

This module defines the Document model for storing health record documents.
Implements FHIR DocumentReference Resource compliance with validation.
"""

from typing import Any, Dict

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from src.healthcare.fhir_validator import FHIRValidator
from src.models.base import BaseModel
from src.models.db_types import UUID


class Document(BaseModel):
    """Document model for health record attachments.

    Implements FHIR DocumentReference Resource pattern for document storage.
    """

    __tablename__ = "documents"

    # FHIR Resource type declaration
    resource_type = "DocumentReference"  # FHIR Resource type

    # Document metadata
    title = Column(String(255), nullable=False)
    description = Column(Text)
    document_type = Column(String(100))  # pdf, image, etc.
    mime_type = Column(String(100))

    # File information
    file_path = Column(String(500))
    file_size = Column(Integer)  # in bytes
    file_hash = Column(String(64))  # SHA-256 hash

    # Associations
    patient_id = Column(UUID(as_uuid=True), ForeignKey("patients.id"))  # type: ignore[var-annotated]
    health_record_id = Column(UUID(as_uuid=True), ForeignKey("health_records.id"))  # type: ignore[var-annotated]

    # Status
    is_verified = Column(Boolean, default=False)
    verified_at = Column(DateTime)
    verified_by = Column(UUID(as_uuid=True))  # type: ignore[var-annotated]

    # Relationships
    patient = relationship("Patient", back_populates="documents")
    health_record = relationship("HealthRecord", back_populates="documents")

    def validate_fhir_compliance(self) -> bool:
        """Validate document meets FHIR DocumentReference requirements."""
        validator = FHIRValidator()
        fhir_representation = self.to_fhir_resource()
        # FHIRValidator.validate_resource returns a validation result dict
        result = validator.validate_resource("DocumentReference", fhir_representation)
        return bool(result.get("valid", False))

    def to_fhir_resource(self) -> Dict[str, Any]:
        """Convert to FHIR DocumentReference Resource."""
        return {
            "resourceType": "DocumentReference",
            "id": str(self.id),
            "status": "current" if self.is_verified else "preliminary",
            "type": {
                "coding": [
                    {
                        "system": "http://loinc.org",
                        "code": self.document_type or "unknown",
                        "display": self.title,
                    }
                ]
            },
            "subject": (
                {"reference": f"Patient/{self.patient_id}"} if self.patient_id else None
            ),
            "content": [
                {
                    "attachment": {
                        "contentType": self.mime_type,
                        "url": self.file_path,
                        "size": self.file_size,
                        "hash": self.file_hash,
                        "title": self.title,
                    }
                }
            ],
        }

    def __repr__(self) -> str:
        """Return string representation of Document."""
        return f"<Document(id={self.id}, title={self.title})>"


# Export model
__all__ = ["Document"]
