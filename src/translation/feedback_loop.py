"""Translation Feedback Loop System.

This module implements a feedback loop for continuous improvement of medical
translations based on user feedback, expert corrections, and usage patterns.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID, uuid4

from sqlalchemy import JSON, Boolean, Column, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Session

from src.models.base import BaseModel
from src.translation.medical_glossary import MedicalGlossaryService
from src.translation.translation_memory import (
    SegmentType,
    TMSegment,
    TranslationMemoryService,
)
from src.utils.logging import get_logger

logger = get_logger(__name__)


class FeedbackType(str, Enum):
    """Types of translation feedback."""

    CORRECTION = "correction"
    QUALITY_RATING = "quality_rating"
    CULTURAL_ISSUE = "cultural_issue"
    MEDICAL_ACCURACY = "medical_accuracy"
    CLARITY_ISSUE = "clarity_issue"
    TERMINOLOGY = "terminology"
    CONTEXT_MISMATCH = "context_mismatch"


class FeedbackSource(str, Enum):
    """Sources of feedback."""

    END_USER = "end_user"
    MEDICAL_PROFESSIONAL = "medical_professional"
    TRANSLATOR = "translator"
    AUTOMATED_CHECK = "automated_check"
    EXPERT_REVIEWER = "expert_reviewer"
    COMMUNITY = "community"


class FeedbackPriority(str, Enum):
    """Priority levels for feedback."""

    CRITICAL = "critical"  # Safety-critical issues
    HIGH = "high"  # Important accuracy issues
    MEDIUM = "medium"  # Quality improvements
    LOW = "low"  # Minor suggestions


@dataclass
class TranslationFeedback:
    """Feedback on a translation."""

    feedback_id: UUID
    translation_id: UUID
    source_text: str
    original_translation: str
    feedback_type: FeedbackType
    feedback_source: FeedbackSource
    priority: FeedbackPriority
    description: str
    suggested_translation: Optional[str] = None
    context_info: Optional[Dict] = None
    submitted_by: Optional[UUID] = None
    submitted_at: Optional[datetime] = None


class TranslationFeedbackRecord(BaseModel):
    """Database model for translation feedback."""

    __tablename__ = "translation_feedback"

    # Feedback identification
    feedback_id = Column(String(36), default=lambda: str(uuid4()), unique=True)
    translation_id = Column(String(36), nullable=False, index=True)

    # Content
    source_text = Column(Text, nullable=False)
    original_translation = Column(Text, nullable=False)
    source_language = Column(String(10), nullable=False)
    target_language = Column(String(10), nullable=False)

    # Feedback details
    feedback_type = Column(String(30), nullable=False)
    feedback_source = Column(String(30), nullable=False)
    priority = Column(String(20), nullable=False)
    description = Column(Text, nullable=False)
    suggested_translation = Column(Text)

    # Context
    content_type = Column(String(50))
    medical_context = Column(JSON, default=dict)
    usage_context = Column(JSON, default=dict)

    # Tracking
    submitted_by = Column(String(36))
    submitted_at = Column(DateTime, default=datetime.utcnow)

    # Processing
    is_processed = Column(Boolean, default=False)
    processed_at = Column(DateTime)
    processing_notes = Column(Text)

    # Resolution
    is_resolved = Column(Boolean, default=False)
    resolved_at = Column(DateTime)
    resolution_type = Column(String(30))
    final_translation = Column(Text)

    # Impact tracking
    affected_translations_count = Column(Integer, default=0)
    improvement_applied = Column(Boolean, default=False)


class FeedbackAggregation(BaseModel):
    """Database model for aggregated feedback patterns."""

    __tablename__ = "feedback_aggregations"

    # Aggregation identification
    aggregation_id = Column(String(36), default=lambda: str(uuid4()), unique=True)
    pattern_type = Column(String(50), nullable=False)

    # Pattern details
    source_language = Column(String(10), nullable=False)
    target_language = Column(String(10), nullable=False)
    content_type = Column(String(50))

    # Pattern data
    pattern_description = Column(Text, nullable=False)
    example_cases = Column(JSON, default=list)
    occurrence_count = Column(Integer, default=1)

    # Improvement metrics
    avg_quality_improvement = Column(Float, default=0.0)
    resolution_rate = Column(Float, default=0.0)

    # Timestamps
    first_detected = Column(DateTime, default=datetime.utcnow)
    last_updated = Column(DateTime, default=datetime.utcnow)


class TranslationFeedbackLoop:
    """Manages feedback loop for translation improvement."""

    def __init__(
        self,
        session: Session,
        translation_memory: TranslationMemoryService,
        glossary_service: MedicalGlossaryService,
    ):
        """Initialize feedback loop system."""
        self.session = session
        self.translation_memory = translation_memory
        self.glossary = glossary_service
        self.improvement_handlers = self._init_improvement_handlers()

    def _init_improvement_handlers(self) -> Dict:
        """Initialize handlers for different feedback types."""
        return {
            FeedbackType.CORRECTION: self._handle_correction_feedback,
            FeedbackType.TERMINOLOGY: self._handle_terminology_feedback,
            FeedbackType.MEDICAL_ACCURACY: self._handle_medical_accuracy_feedback,
            FeedbackType.CULTURAL_ISSUE: self._handle_cultural_feedback,
            FeedbackType.CLARITY_ISSUE: self._handle_clarity_feedback,
        }

    def submit_feedback(
        self,
        translation_id: UUID,
        source_text: str,
        original_translation: str,
        source_language: str,
        target_language: str,
        feedback_type: FeedbackType,
        feedback_source: FeedbackSource,
        description: str,
        suggested_translation: Optional[str] = None,
        priority: Optional[FeedbackPriority] = None,
        submitted_by: Optional[UUID] = None,
        context_info: Optional[Dict] = None,
    ) -> TranslationFeedback:
        """Submit feedback on a translation."""
        # Determine priority if not provided
        if not priority:
            priority = self._determine_priority(feedback_type, description)

        # Create feedback record
        feedback_record = TranslationFeedbackRecord(
            translation_id=str(translation_id),
            source_text=source_text,
            original_translation=original_translation,
            source_language=source_language,
            target_language=target_language,
            feedback_type=feedback_type.value,
            feedback_source=feedback_source.value,
            priority=priority.value,
            description=description,
            suggested_translation=suggested_translation,
            submitted_by=str(submitted_by) if submitted_by else None,
            medical_context=context_info.get("medical", {}) if context_info else {},
            usage_context=context_info.get("usage", {}) if context_info else {},
        )

        self.session.add(feedback_record)
        self.session.commit()

        # Create feedback object
        feedback = TranslationFeedback(
            feedback_id=UUID(feedback_record.feedback_id),
            translation_id=translation_id,
            source_text=source_text,
            original_translation=original_translation,
            feedback_type=feedback_type,
            feedback_source=feedback_source,
            priority=priority,
            description=description,
            suggested_translation=suggested_translation,
            context_info=context_info,
            submitted_by=submitted_by,
            submitted_at=feedback_record.submitted_at,
        )

        logger.info(
            f"Feedback submitted: {feedback.feedback_id} - {feedback_type.value}"
        )

        # Process high-priority feedback immediately
        if priority == FeedbackPriority.CRITICAL:
            self._process_critical_feedback(feedback_record)

        return feedback

    def process_feedback_batch(self, batch_size: int = 100) -> Dict[str, int]:
        """Process a batch of pending feedback."""
        # Get unprocessed feedback
        pending_feedback = (
            self.session.query(TranslationFeedbackRecord)
            .filter(TranslationFeedbackRecord.is_processed.is_(False))
            .order_by(
                TranslationFeedbackRecord.priority.desc(),
                TranslationFeedbackRecord.submitted_at.asc(),
            )
            .limit(batch_size)
            .all()
        )

        results = {"processed": 0, "improvements_applied": 0, "errors": 0}

        for feedback in pending_feedback:
            try:
                improvement_applied = self._process_feedback(feedback)

                feedback.is_processed = True
                feedback.processed_at = datetime.utcnow()

                if improvement_applied:
                    feedback.improvement_applied = True
                    results["improvements_applied"] += 1

                results["processed"] += 1

            except (ValueError, AttributeError, TypeError) as e:
                logger.error(f"Error processing feedback {feedback.feedback_id}: {e}")
                results["errors"] += 1

        self.session.commit()

        # Update aggregations
        self._update_feedback_aggregations()

        return results

    def _process_feedback(self, feedback: TranslationFeedbackRecord) -> bool:
        """Process individual feedback item."""
        feedback_type = FeedbackType(feedback.feedback_type)

        # Get appropriate handler
        handler = self.improvement_handlers.get(feedback_type)

        if handler:
            return bool(handler(feedback))

        return False

    def _handle_correction_feedback(self, feedback: TranslationFeedbackRecord) -> bool:
        """Handle correction feedback."""
        if not feedback.suggested_translation:
            return False

        # Update translation memory
        segment = TMSegment(
            source_text=str(feedback.source_text),
            target_text=str(feedback.suggested_translation),
            source_language=str(feedback.source_language),
            target_language=str(feedback.target_language),
            segment_type=SegmentType.SENTENCE,
            metadata={
                "feedback_id": str(feedback.feedback_id),
                "corrected_from": str(feedback.original_translation),
                "correction_source": str(feedback.feedback_source),
            },
        )
        self.translation_memory.add_segment(
            segment=segment,
            source_type="human",
            quality_score=0.9,  # High score for human corrections
        )

        # Mark as resolved
        feedback.is_resolved = True
        feedback.resolved_at = datetime.utcnow()
        feedback.resolution_type = "correction_applied"
        feedback.final_translation = feedback.suggested_translation

        logger.info(f"Applied correction from feedback {feedback.feedback_id}")

        return True

    def _handle_terminology_feedback(self, feedback: TranslationFeedbackRecord) -> bool:
        """Handle terminology-related feedback."""
        # Extract term from feedback
        # In production, would use NLP to identify the specific term

        if feedback.suggested_translation:
            # Add to medical glossary
            term_parts = feedback.description.split("term:")
            if len(term_parts) > 1:
                term = term_parts[1].strip().split()[0]

                self.glossary.add_term_translation(
                    term=term,
                    translation=str(feedback.suggested_translation),
                    target_language=str(feedback.target_language),
                    source_language=str(feedback.source_language),
                    verified=str(feedback.feedback_source)
                    == FeedbackSource.MEDICAL_PROFESSIONAL.value,
                )

                logger.info(f"Updated terminology from feedback {feedback.feedback_id}")
                return True

        return False

    def _handle_medical_accuracy_feedback(
        self, feedback: TranslationFeedbackRecord
    ) -> bool:
        """Handle medical accuracy feedback."""
        # Flag translation for expert review
        if feedback.priority in [
            FeedbackPriority.CRITICAL.value,
            FeedbackPriority.HIGH.value,
        ]:
            # In production, would trigger expert validation workflow
            logger.warning(
                f"Medical accuracy issue reported: {feedback.feedback_id} - "
                f"Priority: {feedback.priority}"
            )

            # Add warning to translation memory
            segment = TMSegment(
                source_text=str(feedback.source_text),
                target_text=str(feedback.original_translation),
                source_language=str(feedback.source_language),
                target_language=str(feedback.target_language),
                segment_type=SegmentType.SENTENCE,
                metadata={
                    "medical_accuracy_issue": True,
                    "feedback_id": str(feedback.feedback_id),
                    "issue_description": str(feedback.description),
                },
            )
            self.translation_memory.add_segment(
                segment=segment,
                source_type="human",
                quality_score=0.3,  # Low score to discourage reuse
            )

            return True

        return False

    def _handle_cultural_feedback(self, feedback: TranslationFeedbackRecord) -> bool:
        """Handle cultural appropriateness feedback."""
        # Store cultural context information
        cultural_note = {
            "source_text": feedback.source_text,
            "issue": feedback.description,
            "context": feedback.usage_context,
            "suggested_approach": feedback.suggested_translation,
        }

        # In production, would update cultural adaptation rules
        logger.info(f"Cultural feedback recorded: {feedback.feedback_id}")
        logger.debug(f"Cultural note: {cultural_note}")

        return True

    def _handle_clarity_feedback(self, feedback: TranslationFeedbackRecord) -> bool:
        """Handle clarity/readability feedback."""
        # Lower quality score for unclear translations
        segment = TMSegment(
            source_text=str(feedback.source_text),
            target_text=str(feedback.original_translation),
            source_language=str(feedback.source_language),
            target_language=str(feedback.target_language),
            segment_type=SegmentType.SENTENCE,
            metadata={"clarity_issue": True, "feedback_id": str(feedback.feedback_id)},
        )
        self.translation_memory.add_segment(
            segment=segment,
            source_type="human",
            quality_score=0.5,  # Medium score
        )

        return True

    def _process_critical_feedback(self, feedback: TranslationFeedbackRecord) -> None:
        """Process critical feedback immediately."""
        logger.critical(
            f"CRITICAL feedback received: {feedback.feedback_id} - "
            f"{feedback.description}"
        )

        # In production, would:
        # 1. Notify medical team
        # 2. Flag all similar translations
        # 3. Prevent reuse of problematic translation
        # 4. Trigger immediate review

        # For now, mark translation as problematic
        segment = TMSegment(
            source_text=str(feedback.source_text),
            target_text=str(feedback.original_translation),
            source_language=str(feedback.source_language),
            target_language=str(feedback.target_language),
            segment_type=SegmentType.SENTENCE,
            metadata={
                "critical_issue": True,
                "feedback_id": str(feedback.feedback_id),
                "issue": str(feedback.description),
            },
        )
        self.translation_memory.add_segment(
            segment=segment,
            source_type="human",
            quality_score=0.0,  # Zero score to prevent reuse
        )

    def _determine_priority(
        self, feedback_type: FeedbackType, description: str
    ) -> FeedbackPriority:
        """Determine feedback priority based on type and content."""
        # Critical keywords
        critical_keywords = [
            "wrong dose",
            "incorrect dosage",
            "dangerous",
            "life-threatening",
            "fatal",
            "overdose",
            "allergy",
        ]

        description_lower = description.lower()

        # Check for critical issues
        if any(keyword in description_lower for keyword in critical_keywords):
            return FeedbackPriority.CRITICAL

        # Medical accuracy is high priority
        if feedback_type == FeedbackType.MEDICAL_ACCURACY:
            return FeedbackPriority.HIGH

        # Corrections are medium priority
        if feedback_type == FeedbackType.CORRECTION:
            return FeedbackPriority.MEDIUM

        # Everything else is low priority
        return FeedbackPriority.LOW

    def _update_feedback_aggregations(self) -> None:
        """Update feedback pattern aggregations."""
        # Find patterns in recent feedback
        recent_feedback = (
            self.session.query(TranslationFeedbackRecord)
            .filter(
                TranslationFeedbackRecord.submitted_at
                >= datetime.utcnow() - timedelta(days=7)
            )
            .all()
        )

        # Group by type and language pair
        patterns: Dict[
            Tuple[str, str, str, Optional[str]], List[TranslationFeedbackRecord]
        ] = {}

        for feedback in recent_feedback:
            key = (
                feedback.feedback_type,
                feedback.source_language,
                feedback.target_language,
                feedback.content_type,
            )

            if key not in patterns:
                patterns[key] = []

            patterns[key].append(feedback)

        # Update aggregations
        for key, feedback_list in patterns.items():
            if len(feedback_list) >= 3:  # Minimum threshold for pattern
                self._create_or_update_aggregation(key, feedback_list)

    def _create_or_update_aggregation(
        self, pattern_key: Tuple, feedback_list: List[TranslationFeedbackRecord]
    ) -> None:
        """Create or update feedback aggregation."""
        feedback_type, source_lang, target_lang, content_type = pattern_key

        # Check if aggregation exists
        aggregation = (
            self.session.query(FeedbackAggregation)
            .filter(
                FeedbackAggregation.pattern_type == feedback_type,
                FeedbackAggregation.source_language == source_lang,
                FeedbackAggregation.target_language == target_lang,
                FeedbackAggregation.content_type == content_type,
            )
            .first()
        )

        if not aggregation:
            # Create new aggregation
            aggregation = FeedbackAggregation(
                pattern_type=feedback_type,
                source_language=source_lang,
                target_language=target_lang,
                content_type=content_type,
                pattern_description=f"Recurring {feedback_type} issues",
            )
            self.session.add(aggregation)

        # Update aggregation
        aggregation.occurrence_count = len(feedback_list)
        aggregation.last_updated = datetime.utcnow()

        # Calculate resolution rate
        resolved_count = sum(1 for f in feedback_list if f.is_resolved)
        aggregation.resolution_rate = resolved_count / len(feedback_list)

        # Add examples
        aggregation.example_cases = [
            {"feedback_id": f.feedback_id, "description": f.description[:200]}
            for f in feedback_list[:5]  # Keep top 5 examples
        ]

    def get_feedback_analytics(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        language_pair: Optional[Tuple[str, str]] = None,
    ) -> Dict[str, Any]:
        """Get analytics on translation feedback."""
        query = self.session.query(TranslationFeedbackRecord)

        if start_date:
            query = query.filter(TranslationFeedbackRecord.submitted_at >= start_date)
        if end_date:
            query = query.filter(TranslationFeedbackRecord.submitted_at <= end_date)
        if language_pair:
            source_lang, target_lang = language_pair
            query = query.filter(
                TranslationFeedbackRecord.source_language == source_lang,
                TranslationFeedbackRecord.target_language == target_lang,
            )

        feedback_records = query.all()

        analytics: Dict[str, Any] = {
            "total_feedback": len(feedback_records),
            "by_type": {},
            "by_source": {},
            "by_priority": {},
            "resolution_rate": 0,
            "average_resolution_time": None,
            "improvement_rate": 0,
            "top_issues": [],
        }

        if not feedback_records:
            return analytics

        # Calculate metrics
        resolved = [f for f in feedback_records if f.is_resolved]
        analytics["resolution_rate"] = len(resolved) / len(feedback_records) * 100

        improvements = [f for f in feedback_records if f.improvement_applied]
        analytics["improvement_rate"] = len(improvements) / len(feedback_records) * 100

        # Resolution time
        resolution_times = []
        for f in resolved:
            if f.resolved_at and f.submitted_at:
                time_diff = (f.resolved_at - f.submitted_at).total_seconds() / 3600
                resolution_times.append(time_diff)

        if resolution_times:
            analytics["average_resolution_time"] = sum(resolution_times) / len(
                resolution_times
            )

        # Group by type
        for f in feedback_records:
            feedback_type = f.feedback_type
            analytics["by_type"][feedback_type] = (
                analytics["by_type"].get(feedback_type, 0) + 1
            )

        # Group by source
        for f in feedback_records:
            source = f.feedback_source
            analytics["by_source"][source] = analytics["by_source"].get(source, 0) + 1

        # Group by priority
        for f in feedback_records:
            priority = f.priority
            analytics["by_priority"][priority] = (
                analytics["by_priority"].get(priority, 0) + 1
            )

        # Get top issues from aggregations
        aggregations = (
            self.session.query(FeedbackAggregation)
            .order_by(FeedbackAggregation.occurrence_count.desc())
            .limit(10)
            .all()
        )

        analytics["top_issues"] = [
            {
                "pattern": agg.pattern_description,
                "type": agg.pattern_type,
                "occurrences": agg.occurrence_count,
                "resolution_rate": agg.resolution_rate,
            }
            for agg in aggregations
        ]

        return analytics

    def export_improvements(
        self, start_date: Optional[datetime] = None
    ) -> Dict[str, List[Dict]]:
        """Export improvements made based on feedback."""
        query = self.session.query(TranslationFeedbackRecord).filter(
            TranslationFeedbackRecord.improvement_applied.is_(True)
        )

        if start_date:
            query = query.filter(TranslationFeedbackRecord.processed_at >= start_date)

        improvements = query.all()

        export_data: Dict[str, List[Dict[str, Any]]] = {
            "translation_corrections": [],
            "terminology_updates": [],
            "quality_improvements": [],
        }

        for improvement in improvements:
            if improvement.feedback_type == FeedbackType.CORRECTION.value:
                export_data["translation_corrections"].append(
                    {
                        "source": improvement.source_text,
                        "original": improvement.original_translation,
                        "corrected": improvement.final_translation,
                        "languages": f"{improvement.source_language}->{improvement.target_language}",
                    }
                )
            elif improvement.feedback_type == FeedbackType.TERMINOLOGY.value:
                export_data["terminology_updates"].append(
                    {
                        "description": improvement.description,
                        "suggestion": improvement.suggested_translation,
                        "languages": f"{improvement.source_language}->{improvement.target_language}",
                    }
                )
            else:
                export_data["quality_improvements"].append(
                    {
                        "type": improvement.feedback_type,
                        "description": improvement.description,
                        "action_taken": improvement.processing_notes,
                    }
                )

        return export_data


# Feedback integration with ML models
class FeedbackMLIntegration:
    """Integrate feedback data with ML training."""

    @staticmethod
    def prepare_training_data(
        feedback_records: List[TranslationFeedbackRecord],
    ) -> List[Dict]:
        """Prepare feedback data for ML model training."""
        training_data = []

        for feedback in feedback_records:
            if feedback.suggested_translation and feedback.is_resolved:
                training_data.append(
                    {
                        "source": feedback.source_text,
                        "target": feedback.suggested_translation,
                        "source_lang": feedback.source_language,
                        "target_lang": feedback.target_language,
                        "quality_score": (
                            0.9
                            if feedback.feedback_source == "medical_professional"
                            else 0.8
                        ),
                        "context": {
                            "content_type": feedback.content_type,
                            "feedback_type": feedback.feedback_type,
                            "medical_context": feedback.medical_context,
                        },
                    }
                )

        return training_data
