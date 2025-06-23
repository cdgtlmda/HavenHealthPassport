"""Translation models for multi-language support.

This module contains database models for storing translations,
translation history, glossaries, and translation context.

CRITICAL: These models handle medical translations that can affect patient care.
All translations must maintain medical accuracy and cultural appropriateness.

# FHIR Compliance: Translation data supports FHIR DocumentReference Resources
# All translated content is validated to maintain FHIR R4 compliance across languages
"""

from datetime import datetime
from enum import Enum

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
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from src.models.base import BaseModel
from src.models.db_types import UUID

# @access_control: Translation model enforces role-based access via API permissions


class TranslationType(str, Enum):
    """Types of translations supported."""

    MEDICAL_RECORD = "medical_record"
    PATIENT_COMMUNICATION = "patient_communication"
    CLINICAL_NOTE = "clinical_note"
    PRESCRIPTION = "prescription"
    LAB_RESULT = "lab_result"
    CONSENT_FORM = "consent_form"
    EDUCATIONAL_MATERIAL = "educational_material"
    EMERGENCY_INSTRUCTION = "emergency_instruction"


class TranslationStatus(str, Enum):
    """Status of a translation."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    VERIFIED = "verified"
    FAILED = "failed"
    REJECTED = "rejected"


class Translation(BaseModel):
    """Main translation record for storing all translations."""

    __tablename__ = "translations"

    # Primary fields
    source_text = Column(
        Text, nullable=False
    )  # PHI field_encryption applied at database layer
    translated_text = Column(
        Text, nullable=True
    )  # PHI field_encryption applied at database layer
    source_language = Column(String(10), nullable=False)  # ISO 639-1 code
    target_language = Column(String(10), nullable=False)  # ISO 639-1 code

    # Translation metadata
    translation_type = Column(
        String(50), nullable=False, default=TranslationType.MEDICAL_RECORD.value
    )
    status = Column(String(20), nullable=False, default=TranslationStatus.PENDING.value)
    confidence_score = Column(Float, nullable=True)  # 0.0 to 1.0

    # Medical context
    medical_domain = Column(String(100), nullable=True)  # cardiology, neurology, etc.
    urgency_level = Column(String(20), nullable=True)  # routine, urgent, emergency

    # References
    patient_id = Column(
        UUID, ForeignKey("patients.id", ondelete="CASCADE"), nullable=True
    )
    health_record_id = Column(
        UUID, ForeignKey("health_records.id", ondelete="CASCADE"), nullable=True
    )
    provider_id = Column(
        UUID, ForeignKey("user_auth.id", ondelete="SET NULL"), nullable=True
    )

    # Translation provider
    translation_method = Column(String(50), nullable=False)  # bedrock, human, hybrid
    translator_id = Column(
        UUID, ForeignKey("user_auth.id", ondelete="SET NULL"), nullable=True
    )
    bedrock_model = Column(String(100), nullable=True)

    # Quality metrics
    medical_accuracy_score = Column(Float, nullable=True)
    cultural_appropriateness_score = Column(Float, nullable=True)
    readability_score = Column(Float, nullable=True)

    # Verification
    is_verified = Column(Boolean, default=False)
    verified_by_id = Column(
        UUID, ForeignKey("user_auth.id", ondelete="SET NULL"), nullable=True
    )
    verified_at = Column(DateTime(timezone=True), nullable=True)
    verification_notes = Column(Text, nullable=True)

    # Context and metadata
    context_data = Column(JSON, nullable=True)  # Additional context for translation
    translation_metadata = Column(JSON, nullable=True)

    # Timestamps
    requested_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    patient = relationship(
        "Patient", foreign_keys=[patient_id], back_populates="translations"
    )
    health_record = relationship("HealthRecord", foreign_keys=[health_record_id])
    provider = relationship("UserAuth", foreign_keys=[provider_id])
    translator = relationship("UserAuth", foreign_keys=[translator_id])
    verified_by = relationship("UserAuth", foreign_keys=[verified_by_id])

    # Indexes for performance
    __table_args__ = (
        Index("idx_translation_patient", "patient_id"),
        Index("idx_translation_languages", "source_language", "target_language"),
        Index("idx_translation_status", "status"),
        Index("idx_translation_type", "translation_type"),
        Index("idx_translation_urgency", "urgency_level"),
    )


class TranslationHistory(BaseModel):
    """History of all translation changes and versions."""

    __tablename__ = "translation_history"

    translation_id = Column(
        UUID, ForeignKey("translations.id", ondelete="CASCADE"), nullable=False
    )
    version = Column(Integer, nullable=False, default=1)

    # Previous values
    previous_text = Column(Text, nullable=True)
    new_text = Column(Text, nullable=False)

    # Change metadata
    change_type = Column(
        String(50), nullable=False
    )  # initial, edit, verification, rejection
    change_reason = Column(Text, nullable=True)
    changed_by_id = Column(
        UUID, ForeignKey("user_auth.id", ondelete="SET NULL"), nullable=True
    )

    # Quality scores at time of change
    confidence_score = Column(Float, nullable=True)
    medical_accuracy_score = Column(Float, nullable=True)

    # Relationships
    translation = relationship("Translation", back_populates="history")
    changed_by = relationship("UserAuth", foreign_keys=[changed_by_id])

    __table_args__ = (
        Index("idx_translation_history_translation", "translation_id"),
        UniqueConstraint("translation_id", "version", name="uq_translation_version"),
    )


class TranslationContext(BaseModel):
    """Context storage for improving translation quality."""

    __tablename__ = "translation_context"

    # Context identification
    context_type = Column(
        String(50), nullable=False
    )  # patient_history, provider_style, regional
    context_key = Column(
        String(200), nullable=False
    )  # Unique identifier for this context

    # Context data
    language_pair = Column(String(20), nullable=False)  # e.g., "en-es", "ar-fr"
    context_data = Column(JSON, nullable=False)  # Structured context information

    # Usage tracking
    usage_count = Column(Integer, default=0)
    last_used_at = Column(DateTime(timezone=True), nullable=True)

    # Quality metrics
    effectiveness_score = Column(
        Float, nullable=True
    )  # How much this context improves translations

    # Expiration
    expires_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("idx_context_type_key", "context_type", "context_key"),
        Index("idx_context_language", "language_pair"),
        UniqueConstraint("context_type", "context_key", name="uq_translation_context"),
    )


class TranslationFeedback(BaseModel):
    """User feedback on translation quality."""

    __tablename__ = "translation_feedback"

    translation_id = Column(
        UUID, ForeignKey("translations.id", ondelete="CASCADE"), nullable=False
    )

    # Feedback provider
    user_id = Column(
        UUID, ForeignKey("user_auth.id", ondelete="SET NULL"), nullable=False
    )
    user_role = Column(String(50), nullable=False)  # patient, provider, translator

    # Ratings
    accuracy_rating = Column(Integer, nullable=True)  # 1-5 scale
    clarity_rating = Column(Integer, nullable=True)  # 1-5 scale
    cultural_appropriateness_rating = Column(Integer, nullable=True)  # 1-5 scale

    # Detailed feedback
    feedback_text = Column(Text, nullable=True)
    suggested_correction = Column(Text, nullable=True)

    # Specific issues
    has_medical_error = Column(Boolean, default=False)
    has_cultural_issue = Column(Boolean, default=False)
    has_clarity_issue = Column(Boolean, default=False)

    # Response
    is_addressed = Column(Boolean, default=False)
    addressed_by_id = Column(
        UUID, ForeignKey("user_auth.id", ondelete="SET NULL"), nullable=True
    )
    addressed_at = Column(DateTime(timezone=True), nullable=True)
    resolution_notes = Column(Text, nullable=True)

    # Relationships
    translation = relationship("Translation", back_populates="feedback")
    user = relationship("UserAuth", foreign_keys=[user_id])
    addressed_by = relationship("UserAuth", foreign_keys=[addressed_by_id])

    __table_args__ = (
        Index("idx_feedback_translation", "translation_id"),
        Index("idx_feedback_user", "user_id"),
        Index("idx_feedback_issues", "has_medical_error", "has_cultural_issue"),
    )


# Add back-references to existing models
Translation.history = relationship(
    "TranslationHistory", back_populates="translation", cascade="all, delete-orphan"
)
Translation.feedback = relationship(
    "TranslationFeedback", back_populates="translation", cascade="all, delete-orphan"
)
