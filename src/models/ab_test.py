"""
Database models for A/B testing tracking.

CRITICAL: This is a healthcare project. All A/B tests must maintain
patient safety as the top priority. Complete audit trails are mandatory.
"""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
)
from sqlalchemy.orm import relationship, validates

from .base import Base, TimestampMixin
from .db_types import UUID


class ABTest(Base, TimestampMixin):
    """A/B test configuration and tracking."""

    __tablename__ = "ab_tests"

    # Primary key
    id: uuid.UUID = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)  # type: ignore[assignment]

    # Test identification
    test_id = Column(String(36), unique=True, nullable=False, index=True)
    proposal_id = Column(String(36), nullable=False, index=True)

    # Test configuration
    improvement_type = Column(String(50), nullable=False)
    traffic_split = Column(Float, nullable=False, default=0.5)
    minimum_sample_size = Column(Integer, nullable=False, default=100)
    maximum_duration_hours = Column(Integer, nullable=False, default=72)
    confidence_threshold = Column(Float, nullable=False, default=0.95)
    minimum_effect_size = Column(Float, nullable=False, default=0.05)

    # Safety configuration
    safety_metrics = Column(
        JSON, nullable=False, default=lambda: ["accuracy", "medical_term_preservation"]
    )
    safety_thresholds = Column(
        JSON,
        nullable=False,
        default=lambda: {"accuracy": 0.95, "medical_term_preservation": 0.99},
    )

    # Test timing - CRITICAL: Track actual start/end times for audit trail
    start_time = Column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )
    end_time = Column(DateTime(timezone=True), nullable=True)

    # Test status
    status = Column(String(20), nullable=False, default="active")

    # Test configuration data
    control_config = Column(JSON, nullable=False)
    treatment_config = Column(JSON, nullable=False)

    # Results storage
    control_sample_size = Column(Integer, nullable=False, default=0)
    treatment_sample_size = Column(Integer, nullable=False, default=0)

    # Relationships
    metrics = relationship(
        "ABTestMetric", back_populates="test", cascade="all, delete-orphan"
    )
    results = relationship(
        "ABTestResult", back_populates="test", cascade="all, delete-orphan"
    )

    # Constraints
    __table_args__ = (
        CheckConstraint(
            "traffic_split >= 0 AND traffic_split <= 1", name="valid_traffic_split"
        ),
        CheckConstraint("minimum_sample_size > 0", name="positive_sample_size"),
        CheckConstraint(
            "confidence_threshold >= 0.9 AND confidence_threshold <= 0.99",
            name="valid_confidence",
        ),
        CheckConstraint(
            "status IN ('active', 'completed', 'aborted', 'failed')",
            name="valid_status",
        ),
        Index("idx_ab_test_status_start", "status", "start_time"),
    )

    @validates("status")
    def validate_status(self, _key: str, value: str) -> str:
        """Validate status transitions."""
        if self.status == "completed" and value != "completed":
            raise ValueError("Cannot change status of completed test")
        if self.status == "aborted" and value not in ["aborted", "failed"]:
            raise ValueError("Cannot reactivate aborted test")
        return value

    @property
    def is_active(self) -> bool:
        """Check if test is currently active."""
        return bool(self.status == "active" and self.end_time is None)

    @property
    def duration_hours(self) -> Optional[float]:
        """Calculate test duration in hours."""
        if not self.start_time:
            return None
        end = self.end_time or datetime.utcnow()
        duration: float = (end - self.start_time).total_seconds() / 3600
        return duration


class ABTestMetric(Base, TimestampMixin):
    """Individual metric measurement for an A/B test."""

    __tablename__ = "ab_test_metrics"

    # Primary key
    id: uuid.UUID = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)  # type: ignore[assignment]

    # Foreign key to test
    test_id: uuid.UUID = Column(UUID(as_uuid=True), ForeignKey("ab_tests.id"), nullable=False)  # type: ignore[assignment]

    # Metric identification
    variant = Column(String(20), nullable=False)  # 'control' or 'treatment'
    iteration_id = Column(String(36), nullable=False)  # Unique per translation

    # Core metrics
    accuracy_score = Column(Float, nullable=False)
    fluency_score = Column(Float, nullable=False)
    adequacy_score = Column(Float, nullable=False)

    # Medical-specific metrics
    medical_term_preservation = Column(Float, nullable=False)
    cultural_appropriateness = Column(Float, nullable=False)

    # Performance metrics
    translation_time_ms = Column(Integer, nullable=False)
    model_tokens_used = Column(Integer, nullable=True)

    # Context data
    source_language = Column(String(10), nullable=False)
    target_language = Column(String(10), nullable=False)
    domain = Column(String(50), nullable=True)

    # Metadata
    user_feedback_score = Column(Float, nullable=True)
    error_occurred = Column(Boolean, nullable=False, default=False)
    error_details = Column(JSON, nullable=True)

    # Relationships
    test = relationship("ABTest", back_populates="metrics")

    # Constraints
    __table_args__ = (
        CheckConstraint("variant IN ('control', 'treatment')", name="valid_variant"),
        CheckConstraint(
            "accuracy_score >= 0 AND accuracy_score <= 1", name="valid_accuracy"
        ),
        CheckConstraint(
            "medical_term_preservation >= 0 AND medical_term_preservation <= 1",
            name="valid_medical_preservation",
        ),
        Index("idx_ab_metric_test_variant", "test_id", "variant"),
        Index("idx_ab_metric_created", "created_at"),
    )


class ABTestResult(Base, TimestampMixin):
    """Aggregated results and analysis for an A/B test."""

    __tablename__ = "ab_test_results"

    # Primary key
    id: uuid.UUID = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)  # type: ignore[assignment]

    # Foreign key to test
    test_id: uuid.UUID = Column(  # type: ignore[assignment]
        UUID(as_uuid=True), ForeignKey("ab_tests.id"), nullable=False, unique=True
    )

    # Aggregated metrics
    control_metrics_summary = Column(JSON, nullable=False)
    treatment_metrics_summary = Column(JSON, nullable=False)

    # Statistical analysis
    statistical_significance = Column(JSON, nullable=False)
    p_values = Column(JSON, nullable=False)
    effect_sizes = Column(JSON, nullable=False)
    confidence_intervals = Column(JSON, nullable=False)

    # Safety analysis - CRITICAL for healthcare
    safety_violations = Column(JSON, nullable=False, default=dict)
    medical_accuracy_maintained = Column(Boolean, nullable=False, default=True)

    # Recommendation
    recommendation = Column(
        String(20), nullable=False
    )  # 'adopt', 'reject', 'inconclusive'
    recommendation_confidence = Column(Float, nullable=False)
    recommendation_rationale = Column(JSON, nullable=False)

    # Implementation status
    implemented = Column(Boolean, nullable=False, default=False)
    implementation_date = Column(DateTime(timezone=True), nullable=True)
    implementation_notes = Column(JSON, nullable=True)

    # Review and approval - CRITICAL for healthcare
    reviewed_by: Optional[uuid.UUID] = Column(UUID(as_uuid=True), nullable=True)  # type: ignore[assignment]
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    review_notes = Column(JSON, nullable=True)
    approved_by: Optional[uuid.UUID] = Column(UUID(as_uuid=True), nullable=True)  # type: ignore[assignment]
    approved_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    test = relationship("ABTest", back_populates="results", uselist=False)

    # Constraints
    __table_args__ = (
        CheckConstraint(
            "recommendation IN ('adopt', 'reject', 'inconclusive')",
            name="valid_recommendation",
        ),
        CheckConstraint(
            "recommendation_confidence >= 0 AND recommendation_confidence <= 1",
            name="valid_confidence",
        ),
        CheckConstraint(
            "NOT (implemented = true AND reviewed_by IS NULL)",
            name="require_review_before_implementation",
        ),
    )

    @validates("implemented")
    def validate_implementation(self, _key: str, value: bool) -> bool:
        """Ensure safety review before implementation."""
        if value and not self.reviewed_by:
            raise ValueError("Cannot implement without safety review")
        if value and not self.medical_accuracy_maintained:
            raise ValueError(
                "Cannot implement changes that compromise medical accuracy"
            )
        return value
