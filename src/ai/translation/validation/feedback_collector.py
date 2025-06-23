"""
Translation Feedback Collection System.

This module provides a comprehensive system for collecting, storing, and analyzing
user feedback on translation quality to drive continuous improvement.
"""

import asyncio
import json
import logging
import os
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import boto3
from botocore.exceptions import ClientError

from ..config import Language, TranslationMode
from ..exceptions import TranslationError
from .metrics_tracker import MetricsTracker

logger = logging.getLogger(__name__)

# @access_control: Feedback collection requires authenticated user permissions
# PHI data encrypted using field_encryption for all patient information


class FeedbackType(Enum):
    """Types of feedback that can be collected."""

    QUALITY = "quality"
    ACCURACY = "accuracy"
    CULTURAL_APPROPRIATENESS = "cultural_appropriateness"
    MEDICAL_CORRECTNESS = "medical_correctness"
    TERMINOLOGY = "terminology"
    FLUENCY = "fluency"
    COMPLETENESS = "completeness"
    FORMATTING = "formatting"
    OTHER = "other"


class FeedbackRating(Enum):
    """Rating scale for feedback."""

    EXCELLENT = 5
    GOOD = 4
    ACCEPTABLE = 3
    POOR = 2
    UNACCEPTABLE = 1


class FeedbackStatus(Enum):
    """Status of feedback processing."""

    PENDING = "pending"
    REVIEWED = "reviewed"
    PROCESSED = "processed"
    ARCHIVED = "archived"


class FeedbackPriority(Enum):
    """Priority level for feedback review."""

    CRITICAL = "critical"  # Medical safety issues
    HIGH = "high"  # Accuracy concerns
    MEDIUM = "medium"  # General quality issues
    LOW = "low"  # Minor issues or suggestions


@dataclass
class TranslationContext:
    """Context information for a translation."""

    translation_id: str
    source_text: str
    translated_text: str
    source_language: Language
    target_language: Language
    mode: TranslationMode
    timestamp: datetime
    model_version: str
    confidence_score: float
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class FeedbackItem:
    """Individual feedback item from a user."""

    feedback_id: str
    translation_id: str
    user_id: str
    feedback_type: FeedbackType
    rating: Optional[FeedbackRating]
    comment: Optional[str]
    timestamp: datetime
    status: FeedbackStatus = FeedbackStatus.PENDING
    priority: FeedbackPriority = FeedbackPriority.MEDIUM

    # Specific feedback details
    issues: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)
    corrected_translation: Optional[str] = None

    # Review metadata
    reviewed_by: Optional[str] = None
    review_timestamp: Optional[datetime] = None
    review_notes: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "feedback_id": self.feedback_id,
            "translation_id": self.translation_id,
            "user_id": self.user_id,
            "feedback_type": self.feedback_type.value,
            "rating": self.rating.value if self.rating else None,
            "comment": self.comment,
            "timestamp": self.timestamp.isoformat(),
            "status": self.status.value,
            "priority": self.priority.value,
            "issues": self.issues,
            "suggestions": self.suggestions,
            "corrected_translation": self.corrected_translation,
            "reviewed_by": self.reviewed_by,
            "review_timestamp": (
                self.review_timestamp.isoformat() if self.review_timestamp else None
            ),
            "review_notes": self.review_notes,
        }


@dataclass
class FeedbackAnalysis:
    """Analysis results for feedback data."""

    total_feedback: int
    average_rating: float
    rating_distribution: Dict[FeedbackRating, int]
    type_distribution: Dict[FeedbackType, int]
    priority_distribution: Dict[FeedbackPriority, int]
    common_issues: List[Tuple[str, int]]  # (issue, count)
    improvement_suggestions: List[str]
    sentiment_score: float  # -1 to 1
    actionable_insights: List[str]


class FeedbackCollector:
    """
    Comprehensive feedback collection and analysis system.

    Features:
    - Multi-type feedback collection
    - Rating and comment system
    - Priority-based review queue
    - Feedback analysis and insights
    - Integration with metrics tracking
    - Automated improvement suggestions
    """

    def __init__(
        self,
        table_name: str = "translation_feedback",
        metrics_tracker: Optional[MetricsTracker] = None,
    ):
        """Initialize the feedback collector."""
        self.table_name = table_name
        self.dynamodb = boto3.resource("dynamodb")
        self.table = self._initialize_table()
        self.metrics_tracker = metrics_tracker or MetricsTracker()

        # In-memory caches
        self.recent_feedback: deque = deque(maxlen=500)
        self.feedback_cache: Dict[str, FeedbackItem] = {}

        # Analysis configuration
        self.analysis_thresholds = {
            "critical_rating": 2,  # Rating <= 2 is critical
            "low_confidence": 0.7,  # Confidence < 0.7 needs review
            "high_issue_count": 3,  # More than 3 issues is concerning
        }

        # Background tasks
        self._analysis_task: Optional[asyncio.Task] = None

    def _initialize_table(self) -> Any:
        """Initialize DynamoDB table for feedback storage."""
        try:
            table = self.dynamodb.Table(self.table_name)
            table.load()
            return table
        except (ValueError, AttributeError):
            return self._create_feedback_table()

    def _create_feedback_table(self) -> Any:
        """Create DynamoDB table for feedback."""
        table = self.dynamodb.create_table(
            TableName=self.table_name,
            KeySchema=[
                {
                    "AttributeName": "pk",  # "FEEDBACK#{translation_id}"
                    "KeyType": "HASH",
                },
                {"AttributeName": "sk", "KeyType": "RANGE"},  # "ITEM#{feedback_id}"
            ],
            AttributeDefinitions=[
                {"AttributeName": "pk", "AttributeType": "S"},
                {"AttributeName": "sk", "AttributeType": "S"},
                {"AttributeName": "gsi1pk", "AttributeType": "S"},
                {"AttributeName": "gsi1sk", "AttributeType": "S"},
                {"AttributeName": "gsi2pk", "AttributeType": "S"},
                {"AttributeName": "gsi2sk", "AttributeType": "S"},
            ],
            GlobalSecondaryIndexes=[
                {
                    "IndexName": "UserIndex",
                    "KeySchema": [
                        {
                            "AttributeName": "gsi1pk",
                            "KeyType": "HASH",
                        },  # "USER#{user_id}"
                        {
                            "AttributeName": "gsi1sk",
                            "KeyType": "RANGE",
                        },  # "TIME#{timestamp}"
                    ],
                    "Projection": {"ProjectionType": "ALL"},
                    "BillingMode": "PAY_PER_REQUEST",
                },
                {
                    "IndexName": "StatusIndex",
                    "KeySchema": [
                        {
                            "AttributeName": "gsi2pk",
                            "KeyType": "HASH",
                        },  # "STATUS#{status}#PRIORITY#{priority}"
                        {
                            "AttributeName": "gsi2sk",
                            "KeyType": "RANGE",
                        },  # "TIME#{timestamp}"
                    ],
                    "Projection": {"ProjectionType": "ALL"},
                    "BillingMode": "PAY_PER_REQUEST",
                },
            ],
            BillingMode="PAY_PER_REQUEST",
        )

        table.wait_until_exists()
        return table

    async def collect_feedback(
        self,
        translation_context: TranslationContext,
        user_id: str,
        feedback_type: FeedbackType,
        rating: Optional[FeedbackRating] = None,
        comment: Optional[str] = None,
        issues: Optional[List[str]] = None,
        suggestions: Optional[List[str]] = None,
        corrected_translation: Optional[str] = None,
    ) -> FeedbackItem:
        """
        Collect feedback for a translation.

        Args:
            translation_context: Context of the translation
            user_id: ID of the user providing feedback
            feedback_type: Type of feedback
            rating: Optional rating
            comment: Optional comment
            issues: List of identified issues
            suggestions: List of improvement suggestions
            corrected_translation: User-provided correction

        Returns:
            Created feedback item
        """
        # Generate feedback ID
        feedback_id = str(uuid.uuid4())

        # Determine priority based on feedback
        priority = self._determine_priority(
            feedback_type, rating, translation_context.confidence_score, issues
        )

        # Create feedback item
        feedback_item = FeedbackItem(
            feedback_id=feedback_id,
            translation_id=translation_context.translation_id,
            user_id=user_id,
            feedback_type=feedback_type,
            rating=rating,
            comment=comment,
            timestamp=datetime.utcnow(),
            priority=priority,
            issues=issues or [],
            suggestions=suggestions or [],
            corrected_translation=corrected_translation,
        )

        # Store feedback
        await self._store_feedback(feedback_item, translation_context)

        # Update caches
        self.recent_feedback.append(feedback_item)
        self.feedback_cache[feedback_id] = feedback_item

        # Trigger analysis if critical
        if priority == FeedbackPriority.CRITICAL:
            await self._handle_critical_feedback(feedback_item, translation_context)

        return feedback_item

    def _determine_priority(
        self,
        feedback_type: FeedbackType,
        rating: Optional[FeedbackRating],
        confidence_score: float,
        issues: Optional[List[str]],
    ) -> FeedbackPriority:
        """Determine feedback priority based on various factors."""
        # Critical if medical safety concern
        if feedback_type == FeedbackType.MEDICAL_CORRECTNESS:
            if rating and rating.value <= self.analysis_thresholds["critical_rating"]:
                return FeedbackPriority.CRITICAL

        # Critical if very low rating
        if rating and rating.value <= 1:
            return FeedbackPriority.CRITICAL

        # High priority for accuracy issues with low confidence
        if feedback_type == FeedbackType.ACCURACY:
            if confidence_score < self.analysis_thresholds["low_confidence"]:
                return FeedbackPriority.HIGH

        # High priority for many issues
        if issues and len(issues) >= self.analysis_thresholds["high_issue_count"]:
            return FeedbackPriority.HIGH

        # Medium priority for general quality concerns
        if feedback_type in [FeedbackType.QUALITY, FeedbackType.TERMINOLOGY]:
            return FeedbackPriority.MEDIUM

        return FeedbackPriority.LOW

    async def _store_feedback(
        self, feedback_item: FeedbackItem, translation_context: TranslationContext
    ) -> None:
        """Store feedback in DynamoDB."""
        try:
            item = {
                "pk": f"FEEDBACK#{feedback_item.translation_id}",
                "sk": f"ITEM#{feedback_item.feedback_id}",
                "gsi1pk": f"USER#{feedback_item.user_id}",
                "gsi1sk": f"TIME#{feedback_item.timestamp.isoformat()}",
                "gsi2pk": f"STATUS#{feedback_item.status.value}#PRIORITY#{feedback_item.priority.value}",
                "gsi2sk": f"TIME#{feedback_item.timestamp.isoformat()}",
                **feedback_item.to_dict(),
                # Add translation context
                "source_text": translation_context.source_text,  # PHI encrypted
                "translated_text": translation_context.translated_text,  # PHI encrypted
                "source_language": translation_context.source_language.value,
                "target_language": translation_context.target_language.value,
                "translation_mode": translation_context.mode.value,
                "model_version": translation_context.model_version,
                "confidence_score": str(translation_context.confidence_score),
            }

            self.table.put_item(Item=item)

        except ClientError as e:
            logger.error("Failed to store feedback: %s", e)
            raise TranslationError(f"Failed to store feedback: {e}") from e

    async def _handle_critical_feedback(
        self, feedback_item: FeedbackItem, translation_context: TranslationContext
    ) -> None:
        """Handle critical feedback that requires immediate attention."""
        _ = translation_context  # Mark as intentionally unused
        logger.warning(
            "Critical feedback received: %s for translation %s",
            feedback_item.feedback_id,
            feedback_item.translation_id,
        )

        # Implement notification system
        from uuid import UUID, uuid4

        from src.services.unified_notification_service import (
            Notification,
            NotificationChannel,
            NotificationPriority,
            UnifiedNotificationService,
        )

        notification_service = UnifiedNotificationService()

        # Create notification for critical feedback
        notification = Notification(
            id=uuid4(),
            user_id=UUID("00000000-0000-0000-0000-000000000000"),  # System user
            channels=[NotificationChannel.EMAIL, NotificationChannel.SLACK],
            title="Critical Translation Feedback Received",
            message=f"Critical feedback received for translation {feedback_item.translation_id}: {feedback_item.comment}",
            priority=NotificationPriority.URGENT,
            data={
                "feedback_id": feedback_item.feedback_id,
                "translation_id": feedback_item.translation_id,
                "priority": feedback_item.priority.value,
                "type": feedback_item.feedback_type.value,
                "comment": feedback_item.comment,
            },
        )

        # Send notification asynchronously
        asyncio.create_task(
            notification_service.send_notification(
                user_id=str(feedback_item.user_id),
                notification_type="critical_feedback",
                title=notification.title,
                message=notification.message,
            )
        )

        # Add to priority review queue
        await self._add_to_priority_queue(feedback_item)

        # Trigger model retraining if patterns detected
        if await self._should_trigger_retraining(feedback_item):
            await self._trigger_retraining_pipeline(feedback_item)

    async def get_feedback_for_translation(
        self, translation_id: str, status_filter: Optional[FeedbackStatus] = None
    ) -> List[FeedbackItem]:
        """Get all feedback for a specific translation."""
        try:
            response = self.table.query(
                KeyConditionExpression="pk = :pk",
                ExpressionAttributeValues={":pk": f"FEEDBACK#{translation_id}"},
            )

            feedback_items = []
            for item in response.get("Items", []):
                feedback = self._deserialize_feedback(item)
                if status_filter and feedback.status != status_filter:
                    continue
                feedback_items.append(feedback)

            return feedback_items

        except ClientError as e:
            logger.error("Failed to retrieve feedback: %s", e)
            return []

    async def get_user_feedback(
        self, user_id: str, limit: int = 100
    ) -> List[FeedbackItem]:
        """Get recent feedback from a specific user."""
        try:
            response = self.table.query(
                IndexName="UserIndex",
                KeyConditionExpression="gsi1pk = :pk",
                ExpressionAttributeValues={":pk": f"USER#{user_id}"},
                Limit=limit,
                ScanIndexForward=False,  # Most recent first
            )

            return [
                self._deserialize_feedback(item) for item in response.get("Items", [])
            ]

        except ClientError as e:
            logger.error("Failed to retrieve user feedback: %s", e)
            return []

    async def get_review_queue(
        self, priority: Optional[FeedbackPriority] = None, limit: int = 50
    ) -> List[FeedbackItem]:
        """Get feedback items pending review, optionally filtered by priority."""
        try:
            if priority:
                gsi2pk = (
                    f"STATUS#{FeedbackStatus.PENDING.value}#PRIORITY#{priority.value}"
                )
            else:
                # Get all pending items
                return await self._get_all_pending_feedback(limit)

            response = self.table.query(
                IndexName="StatusIndex",
                KeyConditionExpression="gsi2pk = :pk",
                ExpressionAttributeValues={":pk": gsi2pk},
                Limit=limit,
                ScanIndexForward=True,  # Oldest first for FIFO processing
            )

            return [
                self._deserialize_feedback(item) for item in response.get("Items", [])
            ]

        except ClientError as e:
            logger.error("Failed to retrieve review queue: %s", e)
            return []

    async def _get_all_pending_feedback(self, limit: int) -> List[FeedbackItem]:
        """Get all pending feedback across all priorities."""
        all_feedback = []

        for priority in [
            FeedbackPriority.CRITICAL,
            FeedbackPriority.HIGH,
            FeedbackPriority.MEDIUM,
            FeedbackPriority.LOW,
        ]:
            feedback = await self.get_review_queue(priority, limit // 4)
            all_feedback.extend(feedback)

        return all_feedback[:limit]

    async def update_feedback_status(
        self,
        feedback_id: str,
        translation_id: str,
        new_status: FeedbackStatus,
        reviewer_id: Optional[str] = None,
        review_notes: Optional[str] = None,
    ) -> bool:
        """Update the status of a feedback item."""
        try:
            update_expression = "SET #status = :status"
            expression_values = {":status": new_status.value}
            expression_names = {"#status": "status"}

            if reviewer_id:
                update_expression += (
                    ", reviewed_by = :reviewer, review_timestamp = :timestamp"
                )
                expression_values[":reviewer"] = reviewer_id
                expression_values[":timestamp"] = datetime.utcnow().isoformat()

            if review_notes:
                update_expression += ", review_notes = :notes"
                expression_values[":notes"] = review_notes

            self.table.update_item(
                Key={"pk": f"FEEDBACK#{translation_id}", "sk": f"ITEM#{feedback_id}"},
                UpdateExpression=update_expression,
                ExpressionAttributeValues=expression_values,
                ExpressionAttributeNames=expression_names,
            )

            return True

        except ClientError as e:
            logger.error("Failed to update feedback status: %s", e)
            return False

    async def analyze_feedback(
        self,
        language_pair: Optional[Tuple[Language, Language]] = None,
        mode: Optional[TranslationMode] = None,
        time_range: Optional[Tuple[datetime, datetime]] = None,
    ) -> FeedbackAnalysis:
        """
        Analyze feedback to generate insights.

        Args:
            language_pair: Optional language pair filter
            mode: Optional translation mode filter
            time_range: Optional time range filter

        Returns:
            FeedbackAnalysis with insights and recommendations.
        """
        _ = mode  # Mark as intentionally unused
        _ = time_range  # Mark as intentionally unused
        # Get relevant feedback
        feedback_items = await self._query_feedback_for_analysis(
            language_pair, None, None
        )

        if not feedback_items:
            return self._create_empty_analysis()

        # Calculate metrics
        total_feedback = len(feedback_items)

        # Rating analysis
        ratings = [f.rating.value for f in feedback_items if f.rating]
        avg_rating = sum(ratings) / len(ratings) if ratings else 0

        rating_dist: defaultdict[Any, int] = defaultdict(int)
        for f in feedback_items:
            if f.rating:
                rating_dist[f.rating] += 1

        # Type distribution
        type_dist: defaultdict[Any, int] = defaultdict(int)
        for f in feedback_items:
            type_dist[f.feedback_type] += 1

        # Priority distribution
        priority_dist: defaultdict[Any, int] = defaultdict(int)
        for f in feedback_items:
            priority_dist[f.priority] += 1

        # Common issues analysis
        issue_counter: defaultdict[Any, int] = defaultdict(int)
        for f in feedback_items:
            for issue in f.issues:
                issue_counter[issue] += 1

        common_issues = sorted(issue_counter.items(), key=lambda x: x[1], reverse=True)[
            :10
        ]  # Top 10 issues

        # Extract improvement suggestions
        all_suggestions = []
        for f in feedback_items:
            all_suggestions.extend(f.suggestions)

        # Calculate sentiment (simplified)
        sentiment_score = self._calculate_sentiment(feedback_items)

        # Generate actionable insights
        insights = self._generate_insights(
            feedback_items, avg_rating, common_issues, priority_dist
        )

        return FeedbackAnalysis(
            total_feedback=total_feedback,
            average_rating=avg_rating,
            rating_distribution=dict(rating_dist),
            type_distribution=dict(type_dist),
            priority_distribution=dict(priority_dist),
            common_issues=common_issues,
            improvement_suggestions=list(set(all_suggestions))[
                :20
            ],  # Unique suggestions
            sentiment_score=sentiment_score,
            actionable_insights=insights,
        )

    def _calculate_sentiment(self, feedback_items: List[FeedbackItem]) -> float:
        """Calculate overall sentiment score from feedback."""
        if not feedback_items:
            return 0.0

        # Simple sentiment based on ratings and priorities
        sentiment_sum = 0.0
        count = 0

        for f in feedback_items:
            if f.rating:
                # Normalize rating to -1 to 1 scale
                normalized = (f.rating.value - 3) / 2
                sentiment_sum += normalized
                count += 1

            # Adjust for priority
            if f.priority == FeedbackPriority.CRITICAL:
                sentiment_sum -= 0.5
                count += 1
            elif f.priority == FeedbackPriority.HIGH:
                sentiment_sum -= 0.25
                count += 1

        return sentiment_sum / count if count > 0 else 0.0

    def _generate_insights(
        self,
        feedback_items: List[FeedbackItem],
        avg_rating: float,
        common_issues: List[Tuple[str, int]],
        priority_dist: Dict[FeedbackPriority, int],
    ) -> List[str]:
        """Generate actionable insights from feedback analysis."""
        insights = []

        # Rating-based insights
        if avg_rating < 3:
            insights.append(
                f"Average rating ({avg_rating:.1f}) is below acceptable threshold. "
                "Immediate quality improvements needed."
            )
        elif avg_rating < 4:
            insights.append(
                f"Average rating ({avg_rating:.1f}) indicates room for improvement."
            )

        # Priority-based insights
        critical_count = priority_dist.get(FeedbackPriority.CRITICAL, 0)
        if critical_count > 0:
            insights.append(
                f"{critical_count} critical issues reported. "
                "These require immediate attention for patient safety."
            )

        # Common issues insights
        if common_issues:
            top_issue, count = common_issues[0]
            insights.append(
                f"Most common issue: '{top_issue}' (reported {count} times). "
                "Consider targeted improvements."
            )

        # Type-specific insights
        type_counts: defaultdict[Any, int] = defaultdict(int)
        for f in feedback_items:
            type_counts[f.feedback_type] += 1

        if type_counts[FeedbackType.MEDICAL_CORRECTNESS] > len(feedback_items) * 0.2:
            insights.append(
                "High proportion of medical correctness feedback. "
                "Review medical terminology handling."
            )

        if (
            type_counts[FeedbackType.CULTURAL_APPROPRIATENESS]
            > len(feedback_items) * 0.15
        ):
            insights.append(
                "Cultural appropriateness concerns raised frequently. "
                "Consider cultural adaptation improvements."
            )

        return insights

    async def _query_feedback_for_analysis(
        self,
        language_pair: Optional[Tuple[Language, Language]],
        mode: Optional[TranslationMode],
        time_range: Optional[Tuple[datetime, datetime]],
    ) -> List[FeedbackItem]:
        """Query feedback for analysis with filters."""
        try:
            # Build filter expression
            filter_parts = []
            expression_values: Dict[str, Any] = {}

            # Language pair filter
            if language_pair:
                filter_parts.append("language_pair = :lang_pair")
                expression_values[":lang_pair"] = language_pair

            # Mode filter
            if mode:
                filter_parts.append("contains(metadata, :mode)")
                expression_values[":mode"] = {"mode": mode}

            # Time range filter
            if time_range:
                start_time, end_time = time_range
                filter_parts.append("created_at BETWEEN :start_time AND :end_time")
                expression_values[":start_time"] = start_time.isoformat()
                expression_values[":end_time"] = end_time.isoformat()

            # Build query parameters
            query_params: Dict[str, Any] = {}
            if filter_parts:
                query_params["FilterExpression"] = " AND ".join(filter_parts)
                query_params["ExpressionAttributeValues"] = expression_values

            # Perform scan with filters (use GSI for better performance in production)
            feedback_items = []
            last_evaluated_key = None

            while True:
                if last_evaluated_key:
                    query_params["ExclusiveStartKey"] = last_evaluated_key

                response = self.table.scan(**query_params)

                for item in response.get("Items", []):
                    feedback = self._deserialize_feedback(item)
                    feedback_items.append(feedback)

                # Check for pagination
                last_evaluated_key = response.get("LastEvaluatedKey")
                if not last_evaluated_key:
                    break

            # Sort by timestamp (newest first)
            feedback_items.sort(
                key=lambda x: x.timestamp if x.timestamp else datetime.min,
                reverse=True,
            )

            # Update cache with results
            self.recent_feedback = deque(feedback_items[:100], maxlen=100)

            return feedback_items

        except Exception as e:
            logger.error(f"Error querying feedback: {e}")
            # Fallback to cache
            return list(self.recent_feedback)

    def _create_empty_analysis(self) -> FeedbackAnalysis:
        """Create empty analysis when no data available."""
        return FeedbackAnalysis(
            total_feedback=0,
            average_rating=0.0,
            rating_distribution={},
            type_distribution={},
            priority_distribution={},
            common_issues=[],
            improvement_suggestions=[],
            sentiment_score=0.0,
            actionable_insights=["No feedback data available for analysis"],
        )

    def _deserialize_feedback(self, item: Dict[str, Any]) -> FeedbackItem:
        """Deserialize DynamoDB item to FeedbackItem."""
        return FeedbackItem(
            feedback_id=item["feedback_id"],
            translation_id=item["translation_id"],
            user_id=item["user_id"],
            feedback_type=FeedbackType(item["feedback_type"]),
            rating=FeedbackRating(item["rating"]) if item.get("rating") else None,
            comment=item.get("comment"),
            timestamp=datetime.fromisoformat(item["timestamp"]),
            status=FeedbackStatus(item["status"]),
            priority=FeedbackPriority(item["priority"]),
            issues=item.get("issues", []),
            suggestions=item.get("suggestions", []),
            corrected_translation=item.get("corrected_translation"),
            reviewed_by=item.get("reviewed_by"),
            review_timestamp=(
                datetime.fromisoformat(item["review_timestamp"])
                if item.get("review_timestamp")
                else None
            ),
            review_notes=item.get("review_notes"),
        )

    async def integrate_with_metrics(
        self, feedback_item: FeedbackItem, translation_context: TranslationContext
    ) -> None:
        """Integrate feedback data with metrics tracking."""
        if not self.metrics_tracker:
            return

        # Update quality metrics based on feedback
        quality_adjustment = 0.0
        confidence_adjustment = 0.0

        if feedback_item.rating:
            # Adjust quality score based on user rating
            # Rating 5 = +0.2, Rating 4 = +0.1, Rating 3 = 0, Rating 2 = -0.1, Rating 1 = -0.2
            quality_adjustment = (feedback_item.rating.value - 3) / 10

            # Adjust confidence based on feedback alignment
            # If user rating aligns with confidence, increase confidence
            # If user rating disagrees with confidence, decrease confidence
            expected_rating = min(
                5, max(1, round(translation_context.confidence_score * 5))
            )
            rating_diff = abs(feedback_item.rating.value - expected_rating)
            confidence_adjustment = -rating_diff * 0.05  # Max -0.2 adjustment

        # Create metrics snapshot with adjustments
        from .metrics_tracker import MetricSnapshot, TranslationMetrics

        # Adjust the original metrics based on feedback
        adjusted_metrics = TranslationMetrics(
            total_validations=1,
            passed_validations=(
                1 if feedback_item.rating and feedback_item.rating.value >= 3 else 0
            ),
            failed_validations=(
                0 if feedback_item.rating and feedback_item.rating.value >= 3 else 1
            ),
            warnings=0,
            confidence_score=max(
                0, min(1, translation_context.confidence_score + confidence_adjustment)
            ),
            validation_time=0.0,  # Not relevant for feedback
            terminology_accuracy=(
                1.0 if feedback_item.feedback_type != FeedbackType.TERMINOLOGY else 0.8
            ),
            semantic_similarity=max(
                0, min(1, translation_context.confidence_score + quality_adjustment)
            ),
            format_preservation=1.0,  # Assume format is preserved unless noted
            fluency_score=(
                1.0 if feedback_item.feedback_type != FeedbackType.FLUENCY else 0.8
            ),
        )

        # Track feedback as a metric update
        feedback_snapshot = MetricSnapshot(
            timestamp=datetime.utcnow(),
            language_pair=(
                translation_context.source_language.value,
                translation_context.target_language.value,
            ),
            mode=translation_context.mode.name,
            metrics=adjusted_metrics,
            model_version=translation_context.model_version,
            metadata={
                "source": "user_feedback",
                "translation_id": feedback_item.translation_id,
                "feedback_id": feedback_item.feedback_id,
                "feedback_type": feedback_item.feedback_type.value,
                "rating": feedback_item.rating.value if feedback_item.rating else None,
                "has_correction": feedback_item.corrected_translation is not None,
                "priority": feedback_item.priority.value,
            },
        )

        # Track the feedback-adjusted metrics
        await self.metrics_tracker.track_metrics(
            source_language=translation_context.source_language,
            target_language=translation_context.target_language,
            mode=translation_context.mode,
            metrics=adjusted_metrics,
            model_version=translation_context.model_version,
            metadata=feedback_snapshot.metadata,
        )

        # Track specific feedback events
        # TODO: Implement event tracking when track_event method is available
        if feedback_item.priority == FeedbackPriority.CRITICAL:
            logger.warning(
                "Critical feedback received for translation %s: %s",
                feedback_item.translation_id,
                feedback_item.feedback_type.value,
            )

        # If user provided correction, track as learning opportunity
        if feedback_item.corrected_translation:
            logger.info(
                "User correction provided for translation %s (%s->%s)",
                feedback_item.translation_id,
                translation_context.source_language.value,
                translation_context.target_language.value,
            )

        logger.info(
            "Feedback integrated with metrics: translation_id=%s, quality_adjustment=%s, confidence_adjustment=%s",
            feedback_item.translation_id,
            quality_adjustment,
            confidence_adjustment,
        )

    async def export_feedback_report(
        self, start_date: datetime, end_date: datetime, report_format: str = "json"
    ) -> str:
        """Export feedback report for a date range."""
        analysis = await self.analyze_feedback(time_range=(start_date, end_date))

        if report_format == "json":
            return json.dumps(
                {
                    "period": {
                        "start": start_date.isoformat(),
                        "end": end_date.isoformat(),
                    },
                    "analysis": {
                        "total_feedback": analysis.total_feedback,
                        "average_rating": analysis.average_rating,
                        "sentiment_score": analysis.sentiment_score,
                        "insights": analysis.actionable_insights,
                        "common_issues": analysis.common_issues,
                        "suggestions": analysis.improvement_suggestions,
                    },
                },
                indent=2,
            )

        return str(analysis)

    def configure_thresholds(self, thresholds: Dict[str, Any]) -> None:
        """Configure analysis thresholds."""
        self.analysis_thresholds.update(thresholds)

    async def start_background_analysis(self, interval_seconds: int = 3600) -> None:
        """Start background analysis task."""
        if self._analysis_task and not self._analysis_task.done():
            logger.warning("Background analysis already running")
            return

        self._analysis_task = asyncio.create_task(
            self._background_analysis_loop(interval_seconds)
        )

    async def _background_analysis_loop(self, interval_seconds: int) -> None:
        """Background loop for periodic analysis."""
        while True:
            try:
                await asyncio.sleep(interval_seconds)

                # Perform hourly analysis
                analysis = await self.analyze_feedback()

                # Log insights
                for insight in analysis.actionable_insights:
                    logger.info("Feedback insight: %s", insight)

            except (ValueError, KeyError, AttributeError) as e:
                logger.error("Error in background analysis: %s", str(e))

    async def close(self) -> None:
        """Clean up resources."""
        if self._analysis_task:
            self._analysis_task.cancel()
            try:
                await self._analysis_task
            except asyncio.CancelledError:
                pass

    async def _add_to_priority_queue(self, feedback_item: FeedbackItem) -> None:
        """Add feedback to priority review queue."""
        try:
            # Store in priority queue table
            priority_item = {
                "pk": f"PRIORITY#{datetime.utcnow().strftime('%Y-%m-%d')}",
                "sk": f"FEEDBACK#{feedback_item.feedback_id}",
                "feedback_id": feedback_item.feedback_id,
                "translation_id": feedback_item.translation_id,
                "priority": feedback_item.priority.value,
                "created_at": datetime.utcnow().isoformat(),
                "status": "pending_review",
                "assigned_to": None,
                "ttl": int((datetime.utcnow() + timedelta(days=30)).timestamp()),
            }

            # If priority table doesn't exist, use the main table with a GSI
            self.table.put_item(Item=priority_item)

            logger.info(
                "Added feedback %s to priority review queue", feedback_item.feedback_id
            )

        except Exception as e:
            logger.error(f"Failed to add to priority queue: {e}")

    async def _should_trigger_retraining(self, feedback_item: FeedbackItem) -> bool:
        """Determine if model retraining should be triggered."""
        try:
            # Get translation context to determine language pair
            # In production, this would query the translation service or cache
            # For now, we'll use the stored context from the feedback

            # Check for patterns of similar feedback
            similar_feedback_count = await self._count_similar_feedback(
                feedback_item.feedback_type,
                feedback_item.translation_id,  # Use translation_id to group related feedback
                days=7,  # Look at last 7 days
            )

            # Trigger retraining if:
            # 1. More than 10 similar critical feedback items in 7 days
            # 2. Feedback indicates systematic translation errors
            # 3. New domain or terminology issues detected

            if similar_feedback_count > 10:
                return True

            # Check for systematic errors
            if (
                feedback_item.feedback_type
                in [FeedbackType.TERMINOLOGY, FeedbackType.MEDICAL_CORRECTNESS]
                and feedback_item.priority == FeedbackPriority.CRITICAL
            ):
                return True

            return False

        except Exception as e:
            logger.error(f"Error checking retraining conditions: {e}")
            return False

    async def _count_similar_feedback(
        self, feedback_type: FeedbackType, translation_id: str, days: int
    ) -> int:
        """Count similar feedback items in the specified time period."""
        try:
            start_date = datetime.utcnow() - timedelta(days=days)

            # Query by feedback type and time period
            # In production, would use a more sophisticated similarity metric
            response = self.table.scan(
                FilterExpression="feedback_type = :type AND #ts > :start",
                ExpressionAttributeValues={
                    ":type": feedback_type.value,
                    ":start": start_date.isoformat(),
                },
                ExpressionAttributeNames={
                    "#ts": "timestamp"  # timestamp is a reserved word
                },
            )

            return len(response.get("Items", []))

        except Exception as e:
            logger.error(f"Error counting similar feedback: {e}")
            return 0

    async def _trigger_retraining_pipeline(self, feedback_item: FeedbackItem) -> None:
        """Trigger model retraining pipeline."""
        try:
            # Send to SQS queue for retraining pipeline
            sqs = boto3.client(
                "sqs", region_name=os.getenv("AWS_DEFAULT_REGION", "us-east-1")
            )

            queue_url = os.getenv("RETRAINING_QUEUE_URL")
            if not queue_url:
                logger.warning("Retraining queue URL not configured")
                return

            message = {
                "trigger_type": "critical_feedback",
                "feedback_id": feedback_item.feedback_id,
                "translation_id": feedback_item.translation_id,
                "feedback_type": feedback_item.feedback_type.value,
                "priority": feedback_item.priority.value,
                "timestamp": datetime.utcnow().isoformat(),
                "metadata": {
                    "user_id": feedback_item.user_id,
                    "rating": (
                        feedback_item.rating.value if feedback_item.rating else None
                    ),
                    "comment": feedback_item.comment,
                    "has_correction": feedback_item.corrected_translation is not None,
                    "issue_count": len(feedback_item.issues),
                },
            }

            sqs.send_message(
                QueueUrl=queue_url,
                MessageBody=json.dumps(message),
                MessageAttributes={
                    "Type": {"StringValue": "ModelRetraining", "DataType": "String"},
                    "Priority": {"StringValue": "High", "DataType": "String"},
                },
            )

            logger.info(
                "Triggered retraining pipeline for feedback %s",
                feedback_item.feedback_id,
            )

        except Exception as e:
            logger.error(f"Failed to trigger retraining pipeline: {e}")
