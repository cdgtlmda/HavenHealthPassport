"""Emergency Medical Terminology Database Models.

CRITICAL: This module handles life-critical emergency medical terminology
that directly impacts patient safety during emergency situations.
"""

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from src.models.base import BaseModel
from src.models.db_types import UUID


class EmergencyMedicalTerm(BaseModel):
    """Critical emergency medical terminology for life-saving situations."""

    __tablename__ = "emergency_medical_terms"

    # Term identification
    term = Column(String(200), nullable=False)
    language_code = Column(String(10), nullable=False)  # ISO 639-1
    category = Column(
        String(100), nullable=False
    )  # airway, breathing, circulation, etc.

    # Medical classification
    severity_level = Column(String(20), nullable=False)  # critical, urgent, immediate
    icd10_codes = Column(JSON, nullable=True)  # Related ICD-10 codes
    snomed_codes = Column(JSON, nullable=True)  # SNOMED CT codes

    # Usage context
    clinical_context = Column(Text, nullable=True)
    usage_instructions = Column(Text, nullable=True)

    # Phonetic and visual aids
    phonetic_spelling = Column(String(500), nullable=True)  # For voice clarity
    visual_description = Column(Text, nullable=True)  # For non-literate users

    # Metadata
    is_active = Column(Boolean, default=True)
    validated_by = Column(UUID, ForeignKey("user_auth.id"), nullable=True)
    validation_date = Column(DateTime, nullable=True)

    # Relationships
    translations = relationship(
        "EmergencyTermTranslation", back_populates="source_term"
    )

    # Indexes for fast lookup
    __table_args__ = (
        Index("idx_emergency_term_language", "term", "language_code"),
        Index("idx_emergency_category", "category", "severity_level"),
        UniqueConstraint("term", "language_code", name="uq_emergency_term_language"),
    )


class EmergencyTermTranslation(BaseModel):
    """Validated translations for emergency medical terms."""

    __tablename__ = "emergency_term_translations"

    # Source and target
    source_term_id = Column(
        UUID,
        ForeignKey("emergency_medical_terms.id", ondelete="CASCADE"),
        nullable=False,
    )
    target_language = Column(String(10), nullable=False)
    translated_term = Column(String(200), nullable=False)

    # Translation quality
    medical_accuracy_score = Column(Float, nullable=False)  # 0.0-1.0
    cultural_appropriateness = Column(Float, nullable=False)  # 0.0-1.0
    clarity_score = Column(Float, nullable=False)  # 0.0-1.0

    # Validation
    validated_by_native_speaker = Column(Boolean, default=False)
    validated_by_medical_professional = Column(Boolean, default=False)
    validator_id = Column(UUID, ForeignKey("user_auth.id"), nullable=True)
    validation_notes = Column(Text, nullable=True)

    # Context variations
    regional_variations = Column(JSON, nullable=True)  # Dialect-specific terms
    gender_variations = Column(JSON, nullable=True)  # Gender-specific forms
    age_variations = Column(JSON, nullable=True)  # Pediatric vs adult terms

    # Relationships
    source_term = relationship("EmergencyMedicalTerm", back_populates="translations")

    # Indexes
    __table_args__ = (
        Index("idx_emergency_translation", "source_term_id", "target_language"),
        UniqueConstraint(
            "source_term_id",
            "target_language",
            "translated_term",
            name="uq_emergency_translation",
        ),
    )


class EmergencyProtocol(BaseModel):
    """Emergency medical protocols with multilingual instructions."""

    __tablename__ = "emergency_protocols"

    # Protocol identification
    protocol_code = Column(String(50), unique=True, nullable=False)
    name = Column(String(200), nullable=False)
    category = Column(String(100), nullable=False)  # cardiac, respiratory, trauma, etc.

    # Medical details
    conditions = Column(JSON, nullable=False)  # List of medical conditions
    symptoms = Column(JSON, nullable=False)  # Observable symptoms
    immediate_actions = Column(JSON, nullable=False)  # Step-by-step actions

    # Contraindications
    contraindications = Column(JSON, nullable=True)
    warnings = Column(JSON, nullable=True)

    # Multilingual support
    available_languages = Column(JSON, nullable=False)
    primary_language = Column(String(10), nullable=False)

    # Visual aids
    diagram_urls = Column(JSON, nullable=True)  # Visual instruction diagrams
    video_urls = Column(JSON, nullable=True)  # Instructional videos

    # Validation
    reviewed_by_medical_board = Column(Boolean, default=False)
    last_review_date = Column(DateTime, nullable=True)
    next_review_date = Column(DateTime, nullable=True)

    # Indexes
    __table_args__ = (
        Index("idx_emergency_protocol_category", "category"),
        Index("idx_emergency_protocol_code", "protocol_code"),
    )
