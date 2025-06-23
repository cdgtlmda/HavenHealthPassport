"""File attachment model for storing file metadata and references.

This module defines the database model for file attachments including
metadata, virus scan results, and access control information.
Handles FHIR DocumentReference Resource validation for medical attachments.
"""

from datetime import datetime
from enum import Enum as PyEnum
from typing import Any, Dict
from uuid import UUID as UUIDType

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.healthcare.fhir_validator import FHIRValidator
from src.models.base import BaseModel
from src.models.db_types import UUID

# FHIR resource type for this model
__fhir_resource__ = "DocumentReference"


class FileStatus(PyEnum):
    """File status enumeration."""

    PENDING = "pending"
    UPLOADING = "uploading"
    PROCESSING = "processing"
    AVAILABLE = "available"
    QUARANTINED = "quarantined"
    DELETED = "deleted"
    ERROR = "error"


class FileAccessLevel(PyEnum):
    """File access level enumeration."""

    PUBLIC = "public"
    PRIVATE = "private"
    MEDICAL = "medical"
    RESTRICTED = "restricted"


class FileAttachment(BaseModel):
    """Model for file attachments with comprehensive metadata."""

    __tablename__ = "file_attachments"

    # FHIR validator will be initialized lazily
    _validator = None

    # File identification
    filename = Column(String(255), nullable=False)
    original_filename = Column(String(255), nullable=False)
    content_type = Column(String(100), nullable=False)
    size = Column(BigInteger, nullable=False)  # File size in bytes
    file_hash = Column(String(64), nullable=False, index=True)  # SHA-256 hash

    # Storage information
    storage_key = Column(String(500), nullable=False, unique=True)
    storage_bucket = Column(String(100))
    storage_region = Column(String(50))
    cdn_url = Column(String(500))

    # Status and processing
    status: Mapped[FileStatus] = mapped_column(
        Enum(FileStatus), default=FileStatus.PENDING, nullable=False
    )
    processing_status = Column(String(50))
    error_message = Column(String(500))

    # Virus scanning
    virus_scan_status = Column(String(50))  # pending, scanning, clean, infected, error
    virus_scan_result = Column(JSON, default=dict)  # Detailed scan results
    virus_scan_date = Column(DateTime)
    quarantine_reason = Column(String(500))

    # Access control
    access_level: Mapped[FileAccessLevel] = mapped_column(
        Enum(FileAccessLevel), default=FileAccessLevel.PRIVATE, nullable=False
    )
    encryption_status = Column(Boolean, default=True, nullable=False)
    encryption_key_id = Column(String(100))

    # Relationships
    patient_id: Mapped[UUIDType] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patients.id"), nullable=True, index=True
    )
    record_id: Mapped[UUIDType] = mapped_column(
        UUID(as_uuid=True), ForeignKey("health_records.id"), index=True, nullable=False
    )
    uploaded_by: Mapped[UUIDType] = mapped_column(UUID(as_uuid=True), nullable=False)

    # Metadata
    title = Column(String(255))
    description = Column(String(1000))
    tags = Column(JSON, default=list)  # List of tags for categorization
    file_metadata = Column(JSON, default=dict)  # Additional metadata

    # Audit fields
    upload_ip = Column(String(45))  # IPv4 or IPv6
    user_agent = Column(String(500))
    last_accessed = Column(DateTime)
    access_count = Column(Integer, default=0)
    download_count = Column(Integer, default=0)

    # Retention and lifecycle
    retention_date = Column(DateTime)  # When file can be deleted
    expires_at = Column(DateTime)  # When file expires
    archived = Column(Boolean, default=False)
    archive_date = Column(DateTime)

    # Relationships
    patient = relationship("Patient", back_populates="file_attachments")
    health_record = relationship("HealthRecord", back_populates="file_attachments")

    # Indexes
    __table_args__ = (
        Index("idx_file_patient_created", "patient_id", "created_at"),
        Index("idx_file_record_created", "record_id", "created_at"),
        Index("idx_file_hash_status", "file_hash", "status"),
        Index("idx_file_uploaded_by", "uploaded_by", "created_at"),
        CheckConstraint("size > 0", name="check_file_size_positive"),
    )

    def __repr__(self) -> str:
        """Return string representation."""
        return f"<FileAttachment(id={self.id}, filename={self.filename}, status={self.status.value})>"

    @property
    def validator(self) -> FHIRValidator:
        """Lazy initialization of FHIR validator."""
        if self._validator is None:
            self._validator = FHIRValidator()
        return self._validator

    @property
    def is_available(self) -> bool:
        """Check if file is available for access."""
        return bool(
            self.status == FileStatus.AVAILABLE
            and not self.deleted_at
            and (not self.expires_at or self.expires_at > datetime.utcnow())
        )

    @property
    def is_quarantined(self) -> bool:
        """Check if file is quarantined."""
        return bool(self.status == FileStatus.QUARANTINED)

    @property
    def is_expired(self) -> bool:
        """Check if file has expired."""
        return bool(self.expires_at and self.expires_at <= datetime.utcnow())

    @property
    def is_virus_clean(self) -> bool:
        """Check if file passed virus scan."""
        return bool(self.virus_scan_status == "clean")

    def get_size_mb(self) -> float:
        """Get file size in megabytes."""
        return float(self.size) / (1024 * 1024)

    def increment_access_count(self) -> None:
        """Increment access count and update last accessed time."""
        current_count = self.access_count if self.access_count is not None else 0
        self.access_count = int(current_count) + 1  # type: ignore[assignment]
        self.last_accessed = datetime.utcnow()  # type: ignore[assignment]

    def increment_download_count(self) -> None:
        """Increment download count."""
        current_count = self.download_count if self.download_count is not None else 0
        self.download_count = int(current_count) + 1  # type: ignore[assignment]
        self.increment_access_count()

    def mark_as_quarantined(self, reason: str) -> None:
        """Mark file as quarantined."""
        self.status = FileStatus.QUARANTINED
        self.quarantine_reason = reason  # type: ignore[assignment]
        self.virus_scan_status = "infected"  # type: ignore[assignment]

    def mark_as_available(self) -> None:
        """Mark file as available."""
        self.status = FileStatus.AVAILABLE
        self.processing_status = "complete"  # type: ignore[assignment]

    def set_virus_scan_result(self, clean: bool, result: Dict[str, Any]) -> None:
        """Set virus scan results."""
        self.virus_scan_date = datetime.utcnow()  # type: ignore[assignment]
        self.virus_scan_result = result  # type: ignore[assignment]

        if clean:
            self.virus_scan_status = "clean"  # type: ignore[assignment]
            if self.status == FileStatus.PROCESSING:
                self.mark_as_available()
        else:
            self.virus_scan_status = "infected"  # type: ignore[assignment]
            threats = result.get("threats", [])
            self.mark_as_quarantined(f"Threats detected: {', '.join(threats)}")

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "id": str(self.id),
            "filename": self.filename,
            "content_type": self.content_type,
            "size": self.size,
            "status": self.status.value,
            "access_level": self.access_level.value,
            "uploaded_by": str(self.uploaded_by),
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "patient_id": str(self.patient_id) if self.patient_id else None,
            "record_id": str(self.record_id) if self.record_id else None,
            "virus_scan_status": self.virus_scan_status,
            "tags": self.tags or [],
            "is_available": self.is_available,
            "is_expired": self.is_expired,
        }
