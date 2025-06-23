"""
Integration module for feedback and metrics systems.

This module provides integration between the feedback collection system
and the metrics tracking system for comprehensive quality monitoring.
"""

import logging
from typing import Any, Dict, Optional, Tuple

from ..config import Language, TranslationMode
from .feedback_collector import FeedbackCollector, FeedbackItem, TranslationContext
from .metrics_tracker import MetricsTracker

logger = logging.getLogger(__name__)


class QualityMonitoringSystem:
    """Integrated quality monitoring system combining metrics and feedback."""

    def __init__(
        self,
        metrics_table: str = "translation_quality_metrics",
        feedback_table: str = "translation_feedback",
    ):
        """Initialize integrated monitoring system."""
        self.metrics_tracker = MetricsTracker(metrics_table)
        self.feedback_collector = FeedbackCollector(
            feedback_table, metrics_tracker=self.metrics_tracker
        )

    async def record_translation_quality(
        self,
        translation_context: TranslationContext,
        validation_metrics: Any,
        model_version: str,
    ) -> None:
        """Record both automated metrics and prepare for feedback."""
        # Track automated metrics
        await self.metrics_tracker.track_metrics(
            source_language=translation_context.source_language,
            target_language=translation_context.target_language,
            mode=translation_context.mode,
            metrics=validation_metrics,
            model_version=model_version,
            metadata={
                "translation_id": translation_context.translation_id,
                "confidence_score": translation_context.confidence_score,
            },
        )

    async def process_user_feedback(
        self, feedback_item: FeedbackItem, translation_context: TranslationContext
    ) -> None:
        """Process feedback and update quality metrics."""
        # Integrate feedback with metrics
        await self.feedback_collector.integrate_with_metrics(
            feedback_item, translation_context
        )

        # Log for continuous improvement pipeline
        logger.info(
            "Quality feedback processed: translation_id=%s, rating=%s",
            translation_context.translation_id,
            feedback_item.rating.value if feedback_item.rating else "N/A",
        )

    async def get_quality_summary(
        self,
        language_pair: Optional[Tuple[Language, Language]] = None,
        mode: Optional[TranslationMode] = None,
    ) -> Dict[str, Any]:
        """Get combined quality summary from metrics and feedback."""
        # Get recent metrics
        recent_metrics = await self.metrics_tracker.get_recent_metrics(
            language_pair=(
                (language_pair[0].value, language_pair[1].value)
                if language_pair
                else None
            ),
            mode=mode.name if mode else None,
        )

        # Get feedback analysis
        feedback_analysis = await self.feedback_collector.analyze_feedback(
            language_pair=language_pair, mode=mode
        )

        return {
            "automated_metrics": {
                "recent_count": len(recent_metrics),
                "average_confidence": (
                    sum(m.metrics.confidence_score for m in recent_metrics)
                    / len(recent_metrics)
                    if recent_metrics
                    else 0
                ),
            },
            "user_feedback": {
                "total_feedback": feedback_analysis.total_feedback,
                "average_rating": feedback_analysis.average_rating,
                "sentiment": feedback_analysis.sentiment_score,
                "top_issues": feedback_analysis.common_issues[:5],
            },
            "insights": feedback_analysis.actionable_insights,
        }

    async def close(self) -> None:
        """Clean up resources."""
        await self.metrics_tracker.close()
        await self.feedback_collector.close()
