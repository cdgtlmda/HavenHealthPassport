"""Translation queue model for human translation fallback."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID as UUIDType

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import BaseModel
from src.models.db_types import UUID


class TranslationQueueStatus(str, Enum):
    """Status of translation queue entries."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class TranslationQueuePriority(str, Enum):
    """Priority levels for translation queue."""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class TranslationQueueReason(str, Enum):
    """Reasons for queuing translation."""

    LOW_CONFIDENCE = "low_confidence"
    BEDROCK_ERROR = "bedrock_error"
    COMPLEX_MEDICAL = "complex_medical"
    USER_REQUEST = "user_request"
    VALIDATION_FAILED = "validation_failed"
    DIALECT_UNAVAILABLE = "dialect_unavailable"


class TranslationQueue(BaseModel):
    """Model for translation queue entries."""

    __tablename__ = "translation_queue"

    # Request information
    source_text = Column(Text, nullable=False)
    source_language = Column(String(10), nullable=False)
    target_language = Column(String(10), nullable=False)
    target_dialect = Column(String(20))
    translation_type = Column(String(50), nullable=False)
    translation_context = Column(String(50), nullable=False)

    # Queue metadata
    status = Column(
        String(20), default=TranslationQueueStatus.PENDING, nullable=False, index=True
    )
    priority = Column(
        String(20), default=TranslationQueuePriority.NORMAL, nullable=False, index=True
    )
    queue_reason = Column(String(50), nullable=False, index=True)

    # Bedrock attempt information
    bedrock_translation = Column(Text)
    bedrock_confidence_score = Column(Float)
    bedrock_error = Column(Text)
    bedrock_medical_validation = Column(JSON)

    # Human translation
    human_translation = Column(Text)
    translator_id: Mapped[Optional[UUIDType]] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    translation_notes = Column(Text)
    quality_score = Column(Float)

    # Processing information
    assigned_at = Column(DateTime)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    retry_count = Column(Integer, default=0)
    last_retry_at = Column(DateTime)

    # Context information
    patient_id: Mapped[Optional[UUIDType]] = mapped_column(
        UUID(as_uuid=True), index=True, nullable=True
    )
    document_id: Mapped[Optional[UUIDType]] = mapped_column(
        UUID(as_uuid=True), index=True, nullable=True
    )
    session_id: Mapped[Optional[str]] = mapped_column(
        String(100), index=True, nullable=True
    )

    # Medical context
    medical_terms_detected: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON, nullable=True
    )
    medical_category: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    cultural_notes: Mapped[Optional[List[str]]] = mapped_column(JSON, nullable=True)

    # User information
    requested_by: Mapped[UUIDType] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    organization_id: Mapped[Optional[UUIDType]] = mapped_column(
        UUID(as_uuid=True), index=True, nullable=True
    )

    # Additional metadata
    additional_metadata: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON, nullable=True
    )
    callback_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, index=True, nullable=True
    )

    # Create composite indexes for efficient queries
    __table_args__ = (
        Index("idx_queue_status_priority", "status", "priority"),
        Index("idx_queue_patient_status", "patient_id", "status"),
        Index("idx_queue_translator_status", "translator_id", "status"),
        Index("idx_queue_expires_status", "expires_at", "status"),
    )


class TranslationQueueFeedback(BaseModel):
    """Model for translation queue feedback and quality tracking."""

    __tablename__ = "translation_queue_feedback"

    # Reference to queue entry
    queue_entry_id: Mapped[UUIDType] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("translation_queue.id"),
        nullable=False,
        index=True,
    )

    # Feedback information
    feedback_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # accuracy, clarity, terminology
    rating: Mapped[int] = mapped_column(Integer, nullable=False)  # 1-5 scale
    comments: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Who provided feedback
    feedback_by: Mapped[UUIDType] = mapped_column(UUID(as_uuid=True), nullable=False)
    feedback_role: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # patient, provider, reviewer

    # Medical accuracy specific feedback
    terminology_issues: Mapped[Optional[List[Dict[str, str]]]] = mapped_column(
        JSON, nullable=True
    )
    suggested_corrections: Mapped[Optional[Dict[str, str]]] = mapped_column(
        JSON, nullable=True
    )


class TranslationQueueAssignment(BaseModel):
    """Model for tracking translator assignments."""

    __tablename__ = "translation_queue_assignment"

    # Queue and translator
    queue_entry_id: Mapped[UUIDType] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("translation_queue.id"),
        nullable=False,
        index=True,
    )
    translator_id: Mapped[UUIDType] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )

    # Assignment details
    assigned_by: Mapped[UUIDType] = mapped_column(UUID(as_uuid=True), nullable=False)
    assignment_reason: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)

    # Translator qualifications for this assignment
    language_pair_certified: Mapped[bool] = mapped_column(Boolean, default=False)
    medical_specialty_match: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True
    )
    dialect_expertise: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Assignment status
    status: Mapped[str] = mapped_column(
        String(20), default="active"
    )  # active, completed, reassigned
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    reassigned_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    reassignment_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
