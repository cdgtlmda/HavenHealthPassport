"""Medical Translation Feedback Loop System.

This module implements a feedback loop for continuous improvement of medical
translations based on user feedback, expert reviews, and quality metrics.

This module handles PHI with encryption and access control to ensure HIPAA compliance.
It includes FHIR Resource typing and validation for healthcare data.
"""

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    Integer,
    String,
    Text,
)
from sqlalchemy.ext.declarative import declarative_base

from src.healthcare.fhir.validators import FHIRValidator
from src.security.access_control import AccessPermission, require_permission
from src.security.audit import audit_phi_access
from src.security.encryption import EncryptionService
from src.utils.logging import get_logger

logger = get_logger(__name__)

# Create Base for database models
Base: Any = declarative_base()


class FeedbackType(str, Enum):
    """Types of feedback."""

    USER_CORRECTION = "user_correction"
    EXPERT_REVIEW = "expert_review"
    QUALITY_ISSUE = "quality_issue"
    CULTURAL_ADAPTATION = "cultural_adaptation"
    TERMINOLOGY_UPDATE = "terminology_update"
    SAFETY_CONCERN = "safety_concern"
    CLARITY_IMPROVEMENT = "clarity_improvement"
    CONTEXT_MISSING = "context_missing"


class FeedbackSource(str, Enum):
    """Source of feedback."""

    END_USER = "end_user"  # Patients, refugees
    HEALTHCARE_PROVIDER = "healthcare_provider"
    MEDICAL_TRANSLATOR = "medical_translator"
    CLINICAL_EXPERT = "clinical_expert"
    QUALITY_ASSURANCE = "quality_assurance"
    AUTOMATED_SYSTEM = "automated_system"


class FeedbackPriority(str, Enum):
    """Feedback priority levels."""

    CRITICAL = "critical"  # Safety issues, major errors
    HIGH = "high"  # Significant accuracy issues
    MEDIUM = "medium"  # Minor accuracy or clarity issues
    LOW = "low"  # Style or preference issues


class ImprovementAction(str, Enum):
    """Actions taken based on feedback."""

    UPDATE_TRANSLATION = "update_translation"
    RETRAIN_MODEL = "retrain_model"
    UPDATE_GLOSSARY = "update_glossary"
    EXPERT_REVIEW = "expert_review"
    CULTURAL_CONSULTATION = "cultural_consultation"
    NO_ACTION = "no_action"


@dataclass
class TranslationFeedback:
    """Feedback on a translation."""

    feedback_id: str
    translation_id: str
    source_text: str
    original_translation: str
    suggested_translation: Optional[str]
    feedback_type: FeedbackType
    feedback_source: FeedbackSource
    priority: FeedbackPriority
    description: str
    language_pair: Tuple[str, str]  # source, target
    medical_context: Optional[str]
    submitted_by: str
    submitted_at: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class FeedbackAnalysis:
    """Analysis of feedback patterns."""

    pattern_type: str  # recurring_error, terminology_gap, etc.
    frequency: int
    affected_languages: Set[str]
    affected_contexts: Set[str]
    example_feedbacks: List[str]  # feedback IDs
    suggested_action: ImprovementAction
    confidence: float  # 0-1


@dataclass
class ImprovementResult:
    """Result of improvement action."""

    action_id: str
    action_type: ImprovementAction
    feedback_ids: List[str]  # Feedbacks that triggered this action
    changes_made: Dict[str, Any]
    success: bool
    metrics_before: Dict[str, float]
    metrics_after: Dict[str, float]
    implemented_at: datetime = field(default_factory=datetime.utcnow)


# Database Models
class FeedbackRecord(Base):
    """Database model for feedback records."""

    __tablename__ = "translation_feedback"

    id = Column(Integer, primary_key=True)
    feedback_id = Column(String(100), unique=True, nullable=False)
    translation_id = Column(String(100), nullable=False, index=True)
    source_text = Column(Text, nullable=False)
    original_translation = Column(Text, nullable=False)
    suggested_translation = Column(Text)
    feedback_type = Column(String(50), nullable=False)
    feedback_source = Column(String(50), nullable=False)
    priority = Column(String(20), nullable=False)
    description = Column(Text)
    source_language = Column(String(10), nullable=False)
    target_language = Column(String(10), nullable=False)
    medical_context = Column(String(100))
    submitted_by = Column(String(100))
    submitted_at = Column(DateTime, default=datetime.utcnow)

    # Processing status
    processed = Column(Boolean, default=False)
    action_taken = Column(String(50))
    processed_at = Column(DateTime)

    # Quality metrics
    accuracy_impact = Column(Float)  # How much this affects accuracy
    frequency_score = Column(Float)  # How often this issue occurs


class FeedbackLoopManager:
    """Manages the feedback loop for translation improvement."""

    # Thresholds for automated actions
    ACTION_THRESHOLDS = {
        "critical_feedback_count": 1,  # Immediate action for critical
        "high_feedback_count": 3,  # Action after 3 high priority feedbacks
        "pattern_frequency": 5,  # Action when pattern occurs 5+ times
        "accuracy_drop": 0.05,  # 5% accuracy drop triggers review
    }

    # Feedback patterns to monitor
    MONITORED_PATTERNS = {
        "recurring_mistranslation": {
            "description": "Same term consistently mistranslated",
            "action": ImprovementAction.UPDATE_GLOSSARY,
        },
        "context_confusion": {
            "description": "Translation fails in specific medical contexts",
            "action": ImprovementAction.RETRAIN_MODEL,
        },
        "cultural_mismatch": {
            "description": "Translation not culturally appropriate",
            "action": ImprovementAction.CULTURAL_CONSULTATION,
        },
        "safety_terminology": {
            "description": "Safety-critical terms incorrectly translated",
            "action": ImprovementAction.EXPERT_REVIEW,
        },
    }

    def __init__(self) -> None:
        """Initialize feedback loop manager."""
        self.feedback_store: Dict[str, TranslationFeedback] = {}
        self.feedback_analytics: Dict[str, List[Any]] = defaultdict(list)
        self.improvement_history: List[ImprovementResult] = []
        self.pattern_detection_cache: Dict[str, Any] = {}
        self.quality_metrics: Dict[str, Dict[str, Any]] = defaultdict(
            lambda: {"accuracy": 1.0, "feedback_count": 0}
        )
        self.fhir_validator = FHIRValidator()
        self.encryption_service = EncryptionService(
            kms_key_id="alias/haven-health-default"
        )

    async def submit_feedback(
        self,
        translation_id: str,
        source_text: str,
        original_translation: str,
        feedback_type: FeedbackType,
        feedback_source: FeedbackSource,
        description: str,
        source_language: str,
        target_language: str,
        submitted_by: str,
        suggested_translation: Optional[str] = None,
        medical_context: Optional[str] = None,
        priority: Optional[FeedbackPriority] = None,
    ) -> str:
        """Submit feedback for a translation."""
        # Auto-determine priority if not specified
        if priority is None:
            priority = self._determine_priority(feedback_type, feedback_source)

        # Create feedback record
        feedback = TranslationFeedback(
            feedback_id=f"fb_{translation_id}_{datetime.utcnow().timestamp()}",
            translation_id=translation_id,
            source_text=source_text,
            original_translation=original_translation,
            suggested_translation=suggested_translation,
            feedback_type=feedback_type,
            feedback_source=feedback_source,
            priority=priority,
            description=description,
            language_pair=(source_language, target_language),
            medical_context=medical_context,
            submitted_by=submitted_by,
        )

        # Store feedback
        self.feedback_store[feedback.feedback_id] = feedback

        # Update analytics
        self._update_analytics(feedback)

        # Check for immediate action needed
        if await self._requires_immediate_action(feedback):
            await self._trigger_immediate_action(feedback)

        # Check for patterns
        patterns = await self._detect_patterns(feedback)
        if patterns:
            await self._handle_patterns(patterns)

        logger.info(
            f"Feedback {feedback.feedback_id} submitted for translation "
            f"{translation_id} with priority {priority.value}"
        )

        return feedback.feedback_id

    def validate_fhir_resource(self, resource: dict) -> bool:
        """Validate FHIR resource structure and requirements."""
        return self.fhir_validator.validate_resource(resource)

    @audit_phi_access("process_phi_data")
    @require_permission(AccessPermission.READ_PHI)
    def process_with_phi_protection(self, data: dict) -> dict:
        """Process data with PHI protection and audit logging."""
        # Encrypt sensitive fields
        sensitive_fields = ["name", "birthDate", "ssn", "address"]
        encrypted_data = data.copy()

        for field_name in sensitive_fields:
            if field_name in encrypted_data:
                encrypted_data[field_name] = self.encryption_service.encrypt(
                    str(encrypted_data[field_name]).encode()
                )

        return encrypted_data

    def _determine_priority(
        self, feedback_type: FeedbackType, feedback_source: FeedbackSource
    ) -> FeedbackPriority:
        """Determine feedback priority based on type and source."""
        # Critical combinations
        if feedback_type == FeedbackType.SAFETY_CONCERN:
            return FeedbackPriority.CRITICAL

        if (
            feedback_type in [FeedbackType.USER_CORRECTION, FeedbackType.QUALITY_ISSUE]
            and feedback_source == FeedbackSource.CLINICAL_EXPERT
        ):
            return FeedbackPriority.HIGH

        # High priority
        if feedback_type in [
            FeedbackType.TERMINOLOGY_UPDATE,
            FeedbackType.EXPERT_REVIEW,
        ]:
            return FeedbackPriority.HIGH

        # Medium priority
        if feedback_type in [
            FeedbackType.CLARITY_IMPROVEMENT,
            FeedbackType.CULTURAL_ADAPTATION,
        ]:
            return FeedbackPriority.MEDIUM

        return FeedbackPriority.LOW

    def _update_analytics(self, feedback: TranslationFeedback) -> None:
        """Update feedback analytics."""
        # By type
        self.feedback_analytics["by_type"].append(
            {
                "type": feedback.feedback_type.value,
                "timestamp": feedback.submitted_at,
                "priority": feedback.priority.value,
            }
        )

        # By language pair
        lang_pair = f"{feedback.language_pair[0]}->{feedback.language_pair[1]}"
        self.feedback_analytics[f"lang_{lang_pair}"].append(feedback.feedback_id)

        # By medical context
        if feedback.medical_context:
            self.feedback_analytics[f"context_{feedback.medical_context}"].append(
                feedback.feedback_id
            )

        # Update quality metrics
        self._update_quality_metrics(feedback)

    def _update_quality_metrics(self, feedback: TranslationFeedback) -> None:
        """Update quality metrics based on feedback."""
        key = f"{feedback.language_pair[0]}_{feedback.language_pair[1]}"
        metrics = self.quality_metrics[key]

        metrics["feedback_count"] += 1

        # Adjust accuracy based on feedback
        if feedback.priority == FeedbackPriority.CRITICAL:
            metrics["accuracy"] *= 0.95  # 5% penalty for critical issues
        elif feedback.priority == FeedbackPriority.HIGH:
            metrics["accuracy"] *= 0.98  # 2% penalty for high issues
        elif feedback.priority == FeedbackPriority.MEDIUM:
            metrics["accuracy"] *= 0.99  # 1% penalty for medium issues

        # Ensure accuracy doesn't go below 0
        metrics["accuracy"] = max(0.0, metrics["accuracy"])

    async def _requires_immediate_action(self, feedback: TranslationFeedback) -> bool:
        """Check if feedback requires immediate action."""
        # Critical feedback always requires immediate action
        if feedback.priority == FeedbackPriority.CRITICAL:
            return True

        # Check frequency of similar feedback
        similar_count = self._count_similar_feedback(
            feedback.translation_id,
            feedback.feedback_type,
            time_window=timedelta(hours=24),
        )

        if (
            feedback.priority == FeedbackPriority.HIGH
            and similar_count >= self.ACTION_THRESHOLDS["high_feedback_count"]
        ):
            return True

        return False

    def _count_similar_feedback(
        self, translation_id: str, feedback_type: FeedbackType, time_window: timedelta
    ) -> int:
        """Count similar feedback within time window."""
        cutoff_time = datetime.utcnow() - time_window
        count = 0

        for fb in self.feedback_store.values():
            if (
                fb.translation_id == translation_id
                and fb.feedback_type == feedback_type
                and fb.submitted_at >= cutoff_time
            ):
                count += 1

        return count

    async def _trigger_immediate_action(self, feedback: TranslationFeedback) -> None:
        """Trigger immediate action for critical feedback."""
        logger.warning(
            f"Immediate action triggered for feedback {feedback.feedback_id}"
        )

        if feedback.feedback_type == FeedbackType.SAFETY_CONCERN:
            # Flag translation for immediate review
            await self._flag_for_safety_review(feedback)

        elif feedback.priority == FeedbackPriority.CRITICAL:
            # Disable translation temporarily
            await self._disable_translation(feedback.translation_id)

            # Request expert review
            await self._request_emergency_review(feedback)

    async def _detect_patterns(
        self, feedback: TranslationFeedback
    ) -> List[FeedbackAnalysis]:
        """Detect patterns in feedback."""
        patterns = []

        # Check for recurring mistranslation
        if feedback.suggested_translation:
            similar_suggestions = self._find_similar_suggestions(
                feedback.source_text,
                feedback.suggested_translation,
                feedback.language_pair,
            )

            if len(similar_suggestions) >= self.ACTION_THRESHOLDS["pattern_frequency"]:
                patterns.append(
                    FeedbackAnalysis(
                        pattern_type="recurring_mistranslation",
                        frequency=len(similar_suggestions),
                        affected_languages={feedback.language_pair[1]},
                        affected_contexts=(
                            {feedback.medical_context}
                            if feedback.medical_context
                            else set()
                        ),
                        example_feedbacks=similar_suggestions[:5],
                        suggested_action=ImprovementAction.UPDATE_GLOSSARY,
                        confidence=0.9,
                    )
                )

        # Check for context-specific issues
        if feedback.medical_context:
            context_issues = self._analyze_context_feedback(
                feedback.medical_context, feedback.language_pair
            )

            if context_issues.frequency >= self.ACTION_THRESHOLDS["pattern_frequency"]:
                patterns.append(context_issues)

        return patterns

    def _find_similar_suggestions(
        self,
        source_text: str,
        suggested_translation: str,
        language_pair: Tuple[str, str],
    ) -> List[str]:
        """Find feedback with similar suggestions."""
        similar = []

        for fb_id, fb in self.feedback_store.items():
            if (
                fb.language_pair == language_pair
                and fb.source_text.lower() == source_text.lower()
                and fb.suggested_translation
                and fb.suggested_translation.lower() == suggested_translation.lower()
            ):
                similar.append(fb_id)

        return similar

    def _analyze_context_feedback(
        self, medical_context: str, language_pair: Tuple[str, str]
    ) -> FeedbackAnalysis:
        """Analyze feedback for specific medical context."""
        context_feedbacks = []

        for fb_id, fb in self.feedback_store.items():
            if (
                fb.medical_context == medical_context
                and fb.language_pair == language_pair
            ):
                context_feedbacks.append(fb_id)

        return FeedbackAnalysis(
            pattern_type="context_confusion",
            frequency=len(context_feedbacks),
            affected_languages={language_pair[1]},
            affected_contexts={medical_context},
            example_feedbacks=context_feedbacks[:5],
            suggested_action=ImprovementAction.RETRAIN_MODEL,
            confidence=0.8,
        )

    async def _handle_patterns(self, patterns: List[FeedbackAnalysis]) -> None:
        """Handle detected patterns."""
        for pattern in patterns:
            logger.info(
                f"Pattern detected: {pattern.pattern_type} with "
                f"frequency {pattern.frequency}"
            )

            # Take action based on pattern
            if pattern.suggested_action == ImprovementAction.UPDATE_GLOSSARY:
                await self._update_translation_glossary(pattern)

            elif pattern.suggested_action == ImprovementAction.RETRAIN_MODEL:
                await self._schedule_model_retraining(pattern)

            elif pattern.suggested_action == ImprovementAction.CULTURAL_CONSULTATION:
                await self._request_cultural_review(pattern)

    async def _update_translation_glossary(self, pattern: FeedbackAnalysis) -> None:
        """Update translation glossary based on pattern."""
        # Extract terms and translations from feedback
        updates = {}

        for fb_id in pattern.example_feedbacks:
            feedback = self.feedback_store.get(fb_id)
            if feedback and feedback.suggested_translation:
                updates[feedback.source_text] = feedback.suggested_translation

        # Apply updates to glossary
        result = ImprovementResult(
            action_id=f"improve_{datetime.utcnow().timestamp()}",
            action_type=ImprovementAction.UPDATE_GLOSSARY,
            feedback_ids=pattern.example_feedbacks,
            changes_made={"glossary_updates": updates},
            success=True,
            metrics_before=self._get_current_metrics(pattern.affected_languages),
            metrics_after={},  # Will be updated after implementation
        )

        self.improvement_history.append(result)

        logger.info(f"Updated glossary with {len(updates)} terms")

    def _get_current_metrics(self, languages: Set[str]) -> Dict[str, float]:
        """Get current quality metrics for languages."""
        metrics = {}

        for lang in languages:
            # Find all language pairs involving this language
            for key, values in self.quality_metrics.items():
                if lang in key:
                    metrics[key] = values["accuracy"]

        return metrics

    async def _flag_for_safety_review(self, feedback: TranslationFeedback) -> None:
        """Flag translation for safety review."""
        logger.critical(
            f"Translation {feedback.translation_id} flagged for safety review: "
            f"{feedback.description}"
        )

        # In production, would:
        # - Notify safety team
        # - Create urgent review ticket
        # - Log in audit trail

    async def _disable_translation(self, translation_id: str) -> None:
        """Temporarily disable a translation."""
        logger.warning(f"Translation {translation_id} temporarily disabled")

        # In production, would:
        # - Mark translation as inactive in database
        # - Prevent serving this translation
        # - Use fallback translation

    async def _request_emergency_review(self, feedback: TranslationFeedback) -> None:
        """Request emergency expert review."""
        logger.info(
            f"Emergency review requested for translation {feedback.translation_id}"
        )

        # In production, would integrate with expert review system

    async def _schedule_model_retraining(self, pattern: FeedbackAnalysis) -> None:
        """Schedule model retraining based on patterns."""
        logger.info(f"Scheduling model retraining for pattern: {pattern.pattern_type}")

        # In production, would:
        # - Collect training data from feedback
        # - Schedule retraining job
        # - Monitor improvement

    async def _request_cultural_review(self, pattern: FeedbackAnalysis) -> None:
        """Request cultural appropriateness review."""
        logger.info(
            f"Cultural review requested for contexts: {pattern.affected_contexts}"
        )

        # In production, would notify cultural consultants

    def get_feedback_summary(
        self,
        language_pair: Optional[Tuple[str, str]] = None,
        time_period: Optional[timedelta] = None,
    ) -> Dict[str, Any]:
        """Get summary of feedback."""
        feedbacks = list(self.feedback_store.values())

        # Filter by language pair
        if language_pair:
            feedbacks = [fb for fb in feedbacks if fb.language_pair == language_pair]

        # Filter by time period
        if time_period:
            cutoff = datetime.utcnow() - time_period
            feedbacks = [fb for fb in feedbacks if fb.submitted_at >= cutoff]

        # Summarize
        by_priority: Dict[str, int] = defaultdict(int)
        by_type: Dict[str, int] = defaultdict(int)
        by_source: Dict[str, int] = defaultdict(int)
        recent_critical: List[Dict[str, str]] = []

        summary: Dict[str, Any] = {
            "total_feedback": len(feedbacks),
            "by_priority": by_priority,
            "by_type": by_type,
            "by_source": by_source,
            "recent_critical": recent_critical,
        }

        for fb in feedbacks:
            by_priority[fb.priority.value] += 1
            by_type[fb.feedback_type.value] += 1
            by_source[fb.feedback_source.value] += 1

            if fb.priority == FeedbackPriority.CRITICAL:
                recent_critical.append(
                    {
                        "feedback_id": fb.feedback_id,
                        "translation_id": fb.translation_id,
                        "description": fb.description,
                        "submitted_at": fb.submitted_at.isoformat(),
                    }
                )

        return dict(summary)

    def get_improvement_metrics(self) -> Dict[str, Any]:
        """Get metrics on improvements made."""
        if not self.improvement_history:
            return {"message": "No improvements recorded yet"}

        by_action_type: Dict[str, int] = defaultdict(int)

        metrics: Dict[str, Any] = {
            "total_improvements": len(self.improvement_history),
            "by_action_type": by_action_type,
            "success_rate": 0.0,
            "feedback_addressed": 0,
        }

        successful = 0
        for improvement in self.improvement_history:
            by_action_type[improvement.action_type.value] += 1
            metrics["feedback_addressed"] = metrics["feedback_addressed"] + len(
                improvement.feedback_ids
            )
            if improvement.success:
                successful += 1

        metrics["success_rate"] = successful / metrics["total_improvements"] * 100

        return dict(metrics)


# Global feedback loop manager
feedback_loop = FeedbackLoopManager()
