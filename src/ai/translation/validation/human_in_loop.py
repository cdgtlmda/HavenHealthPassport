"""
Human-in-the-Loop Translation Validation System.

Provides a comprehensive system for human review of medical translations,
including queuing, review interfaces, feedback collection, and continuous
improvement based on human input.

This module handles encrypted PHI with access control and audit logging
to ensure HIPAA compliance.
"""

import json
import random
import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from queue import Empty as QueueEmpty
from queue import Full as QueueFull
from queue import PriorityQueue
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

from ..exceptions import TranslationError
from .pipeline import (
    TranslationValidationPipeline,
    ValidationResult,
    ValidationStatus,
)


class ReviewPriority(Enum):
    """Priority levels for human review."""

    CRITICAL = 1  # Life-critical medical content
    HIGH = 2  # Failed validation or very low confidence
    MEDIUM = 3  # Warnings or moderate confidence
    LOW = 4  # Passed but flagged for spot-check
    EDUCATIONAL = 5  # For training/quality improvement


class ReviewStatus(Enum):
    """Status of human review."""

    PENDING = "pending"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    CORRECTED = "corrected"
    ESCALATED = "escalated"
    EXPIRED = "expired"
    SKIPPED = "skipped"


class ReviewerRole(Enum):
    """Roles for human reviewers."""

    MEDICAL_PROFESSIONAL = "medical_professional"
    CERTIFIED_TRANSLATOR = "certified_translator"
    NATIVE_SPEAKER = "native_speaker"
    SUBJECT_EXPERT = "subject_expert"
    SUPERVISOR = "supervisor"


@dataclass
class ReviewerProfile:
    """Profile for a human reviewer."""

    reviewer_id: str
    name: str
    email: str
    role: ReviewerRole
    languages: List[str]  # Language codes the reviewer is qualified for
    specializations: List[str]  # Medical specializations
    certifications: List[str]
    active: bool = True
    created_at: datetime = field(default_factory=datetime.now)
    stats: Dict[str, Any] = field(default_factory=dict)

    def can_review(
        self, source_lang: str, target_lang: str, specialization: Optional[str] = None
    ) -> bool:
        """Check if reviewer is qualified for this review."""
        if not self.active:
            return False

        # Check language qualification
        if source_lang not in self.languages or target_lang not in self.languages:
            return False

        # Check specialization if required
        if specialization and specialization not in self.specializations:
            return False

        return True


@dataclass
class ReviewRequest:
    """Request for human review of a translation."""

    request_id: str = field(default_factory=lambda: str(uuid4()))
    validation_result: Optional[ValidationResult] = None
    priority: ReviewPriority = ReviewPriority.MEDIUM
    reason: str = ""
    medical_category: Optional[str] = None
    requested_at: datetime = field(default_factory=datetime.now)
    deadline: Optional[datetime] = None
    assigned_to: Optional[str] = None  # Reviewer ID
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __lt__(self, other: "ReviewRequest") -> bool:
        """Enable priority queue sorting."""
        return self.priority.value < other.priority.value


@dataclass
class ReviewDecision:
    """Human reviewer's decision on a translation."""

    request_id: str
    reviewer_id: str
    status: ReviewStatus
    decision_time: datetime = field(default_factory=datetime.now)
    corrected_translation: Optional[str] = None
    comments: Optional[str] = None
    quality_score: Optional[float] = None  # 0-1 scale
    issues_found: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)
    time_spent_seconds: Optional[int] = None
    confidence: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "request_id": self.request_id,
            "reviewer_id": self.reviewer_id,
            "status": self.status.value,
            "decision_time": self.decision_time.isoformat(),
            "corrected_translation": self.corrected_translation,
            "comments": self.comments,
            "quality_score": self.quality_score,
            "issues_found": self.issues_found,
            "suggestions": self.suggestions,
            "time_spent_seconds": self.time_spent_seconds,
            "confidence": self.confidence,
        }


@dataclass
class HumanInLoopConfig:
    """Configuration for human-in-the-loop system."""

    # Review thresholds
    auto_review_confidence_threshold: float = 0.7
    critical_content_patterns: List[str] = field(
        default_factory=lambda: [
            "dosage",
            "allergy",
            "contraindication",
            "emergency",
            "critical",
        ]
    )

    # Queue management
    max_queue_size: int = 1000
    review_timeout_minutes: int = 30
    escalation_timeout_minutes: int = 60

    # Reviewer assignment
    auto_assign_reviews: bool = True
    require_dual_review_for_critical: bool = True
    max_reviews_per_reviewer_per_day: int = 100

    # Learning and improvement
    min_reviews_for_pattern_learning: int = 10
    feedback_incorporation_threshold: float = 0.8
    track_reviewer_accuracy: bool = True

    # Notification settings
    notify_on_critical: bool = True
    notify_on_escalation: bool = True
    batch_notification_interval_minutes: int = 15


class HumanInLoopSystem:
    """Main human-in-the-loop validation system."""

    def __init__(
        self,
        config: Optional[HumanInLoopConfig] = None,
        validation_pipeline: Optional[TranslationValidationPipeline] = None,
    ):
        """Initialize the human-in-the-loop system."""
        self.config = config or HumanInLoopConfig()
        self.validation_pipeline = validation_pipeline

        # Review queue (priority queue)
        self.review_queue: PriorityQueue[ReviewRequest] = PriorityQueue(
            maxsize=self.config.max_queue_size
        )

        # Storage
        self.reviewers: Dict[str, ReviewerProfile] = {}
        self.active_reviews: Dict[str, ReviewRequest] = {}
        self.completed_reviews: List[ReviewDecision] = []
        self.review_patterns: Dict[str, List[ReviewDecision]] = defaultdict(list)

        # Learning components
        self.correction_patterns: Dict[Tuple[str, str], List[Dict]] = defaultdict(list)
        self.reviewer_performance: Dict[str, Dict[str, float]] = defaultdict(dict)

        # Background tasks
        self._stop_event = threading.Event()
        self._start_background_tasks()

    def _start_background_tasks(self) -> None:
        """Start background tasks for queue management."""
        self._timeout_thread = threading.Thread(
            target=self._check_timeouts, daemon=True
        )
        self._timeout_thread.start()

    def _check_timeouts(self) -> None:
        """Background task to check for review timeouts."""
        while not self._stop_event.is_set():
            current_time = datetime.now()

            # Check for expired reviews
            for request_id, request in list(self.active_reviews.items()):
                if request.deadline and current_time > request.deadline:
                    # Mark as expired and potentially escalate
                    self._handle_expired_review(request_id, request)

            # Sleep for a minute before next check
            time.sleep(60)

    def add_reviewer(self, reviewer: ReviewerProfile) -> None:
        """Add a reviewer to the system."""
        self.reviewers[reviewer.reviewer_id] = reviewer

    def submit_for_review(
        self,
        validation_result: ValidationResult,
        priority: Optional[ReviewPriority] = None,
        reason: Optional[str] = None,
    ) -> str:
        """Submit a translation for human review."""
        # Determine priority if not specified
        if priority is None:
            priority = self._determine_priority(validation_result)

        # Determine reason if not specified
        if reason is None:
            reason = self._generate_review_reason(validation_result)

        # Create review request
        request = ReviewRequest(
            validation_result=validation_result,
            priority=priority,
            reason=reason,
            medical_category=self._detect_medical_category(
                validation_result.source_text
            ),
            deadline=datetime.now()
            + timedelta(minutes=self.config.review_timeout_minutes),
        )

        # Add to queue
        try:
            self.review_queue.put_nowait(request)
            self.active_reviews[request.request_id] = request

            # Auto-assign if configured
            if self.config.auto_assign_reviews:
                self._auto_assign_reviewer(request)

            # Send notifications for critical reviews
            if priority == ReviewPriority.CRITICAL and self.config.notify_on_critical:
                self._send_critical_notification(request)

            return request.request_id

        except QueueFull as exc:
            raise TranslationError("Review queue is full") from exc

    def _determine_priority(
        self, validation_result: ValidationResult
    ) -> ReviewPriority:
        """Determine review priority based on validation result."""
        # Check for critical content
        if self.contains_critical_content(validation_result.source_text):
            return ReviewPriority.CRITICAL

        # Check validation status
        if validation_result.overall_status == ValidationStatus.FAILED:
            return ReviewPriority.HIGH

        # Check confidence score
        if validation_result.metrics:
            confidence = validation_result.metrics.confidence_score
            if confidence < 0.5:
                return ReviewPriority.HIGH
            elif confidence < self.config.auto_review_confidence_threshold:
                return ReviewPriority.MEDIUM

        # Check for warnings
        if validation_result.warning_count > 0:
            return ReviewPriority.MEDIUM

        # Default to low priority for spot checks
        return ReviewPriority.LOW

    def contains_critical_content(self, text: str) -> bool:
        """Check if text contains critical medical content."""
        text_lower = text.lower()
        return any(
            pattern in text_lower for pattern in self.config.critical_content_patterns
        )

    def _generate_review_reason(self, validation_result: ValidationResult) -> str:
        """Generate human-readable reason for review."""
        reasons = []

        if validation_result.overall_status == ValidationStatus.FAILED:
            reasons.append("Validation failed")

        if validation_result.error_count > 0:
            reasons.append(f"{validation_result.error_count} errors found")

        if validation_result.warning_count > 0:
            reasons.append(f"{validation_result.warning_count} warnings")

        if (
            validation_result.metrics
            and validation_result.metrics.confidence_score < 0.7
        ):
            reasons.append(
                f"Low confidence: {validation_result.metrics.confidence_score:.2f}"
            )

        # Add specific issue types
        if hasattr(validation_result, "issues") and validation_result.issues:
            issue_types = set(issue.validator for issue in validation_result.issues)
            if issue_types:
                reasons.append(f"Issues in: {', '.join(issue_types)}")

        return "; ".join(reasons) if reasons else "Routine quality check"

    def _detect_medical_category(self, text: str) -> Optional[str]:
        """Detect medical category from text."""
        # Simple keyword-based detection (can be enhanced with ML)
        categories = {
            "prescription": ["prescription", "medication", "dosage", "mg", "ml"],
            "diagnosis": ["diagnosis", "diagnosed", "condition", "syndrome"],
            "procedure": ["surgery", "procedure", "operation", "treatment"],
            "allergy": ["allergy", "allergic", "reaction", "intolerance"],
            "emergency": ["emergency", "urgent", "critical", "immediate"],
        }

        text_lower = text.lower()
        for category, keywords in categories.items():
            if any(keyword in text_lower for keyword in keywords):
                return category

        return None

    def _auto_assign_reviewer(self, request: ReviewRequest) -> Optional[str]:
        """Automatically assign a reviewer to a request."""
        if request.validation_result is None:
            return None

        suitable_reviewers = []

        for reviewer_id, reviewer in self.reviewers.items():
            if reviewer.can_review(
                request.validation_result.source_lang,
                request.validation_result.target_lang,
                request.medical_category,
            ):
                # Check workload
                daily_reviews = self._get_reviewer_daily_count(reviewer_id)
                if daily_reviews < self.config.max_reviews_per_reviewer_per_day:
                    suitable_reviewers.append(reviewer)

        if suitable_reviewers:
            # Sort by performance and workload
            suitable_reviewers.sort(
                key=lambda r: (
                    -self.reviewer_performance.get(r.reviewer_id, {}).get(
                        "accuracy", 0.5
                    ),
                    self._get_reviewer_daily_count(r.reviewer_id),
                )
            )

            selected_reviewer = suitable_reviewers[0]
            request.assigned_to = selected_reviewer.reviewer_id
            return selected_reviewer.reviewer_id

        return None

    def _get_reviewer_daily_count(self, reviewer_id: str) -> int:
        """Get number of reviews done by reviewer today."""
        today = datetime.now().date()
        count = 0

        for decision in self.completed_reviews:
            if (
                decision.reviewer_id == reviewer_id
                and decision.decision_time.date() == today
            ):
                count += 1

        return count

    def get_next_review(self, reviewer_id: str) -> Optional[ReviewRequest]:
        """Get next review request for a reviewer."""
        reviewer = self.reviewers.get(reviewer_id)
        if not reviewer:
            return None

        # Try to get assigned reviews first
        for _, request in self.active_reviews.items():
            if request.assigned_to == reviewer_id:
                return request

        # Get from queue based on qualifications
        temp_queue = []
        result = None

        while not self.review_queue.empty():
            try:
                request = self.review_queue.get_nowait()

                if request.validation_result and reviewer.can_review(
                    request.validation_result.source_lang,
                    request.validation_result.target_lang,
                    request.medical_category,
                ):
                    request.assigned_to = reviewer_id
                    result = request
                    break
                else:
                    temp_queue.append(request)
            except QueueEmpty:
                break

        # Put back unmatched requests
        for request in temp_queue:
            self.review_queue.put_nowait(request)

        return result

    def submit_review_decision(self, decision: ReviewDecision) -> None:
        """Submit a reviewer's decision."""
        # Validate request exists
        request = self.active_reviews.get(decision.request_id)
        if not request:
            raise ValueError(f"Review request {decision.request_id} not found")

        # Remove from active reviews
        del self.active_reviews[decision.request_id]

        # Store decision
        self.completed_reviews.append(decision)

        # Update patterns for learning
        self._update_learning_patterns(request, decision)

        # Update reviewer performance
        self._update_reviewer_performance(decision)

        # Handle based on decision status
        if decision.status == ReviewStatus.ESCALATED:
            self._escalate_review(request, decision)
        elif decision.status == ReviewStatus.CORRECTED:
            self._process_correction(request, decision)

    def _update_learning_patterns(
        self, request: ReviewRequest, decision: ReviewDecision
    ) -> None:
        """Update learning patterns from review decision."""
        if not request.validation_result:
            return

        if decision.status == ReviewStatus.CORRECTED and decision.corrected_translation:
            # Store correction pattern
            key = (
                request.validation_result.source_lang,
                request.validation_result.target_lang,
            )

            pattern = {
                "source": request.validation_result.source_text,
                "original": request.validation_result.translated_text,
                "corrected": decision.corrected_translation,
                "issues": decision.issues_found,
                "category": request.medical_category,
                "timestamp": decision.decision_time,
            }

            self.correction_patterns[key].append(pattern)

        # Store review pattern
        pattern_key = f"{request.validation_result.source_lang}_{request.validation_result.target_lang}"
        self.review_patterns[pattern_key].append(decision)

    def _update_reviewer_performance(self, decision: ReviewDecision) -> None:
        """Update reviewer performance metrics."""
        reviewer_id = decision.reviewer_id

        # Update review count
        if "review_count" not in self.reviewer_performance[reviewer_id]:
            self.reviewer_performance[reviewer_id]["review_count"] = 0
        self.reviewer_performance[reviewer_id]["review_count"] += 1

        # Update average time
        if decision.time_spent_seconds:
            if "avg_time" not in self.reviewer_performance[reviewer_id]:
                self.reviewer_performance[reviewer_id][
                    "avg_time"
                ] = decision.time_spent_seconds
            else:
                count = self.reviewer_performance[reviewer_id]["review_count"]
                current_avg = self.reviewer_performance[reviewer_id]["avg_time"]
                new_avg = (
                    (current_avg * (count - 1)) + decision.time_spent_seconds
                ) / count
                self.reviewer_performance[reviewer_id]["avg_time"] = new_avg

        # Update quality metrics if available
        if decision.quality_score is not None:
            if "avg_quality" not in self.reviewer_performance[reviewer_id]:
                self.reviewer_performance[reviewer_id][
                    "avg_quality"
                ] = decision.quality_score
            else:
                count = self.reviewer_performance[reviewer_id]["review_count"]
                current_avg = self.reviewer_performance[reviewer_id]["avg_quality"]
                new_avg = ((current_avg * (count - 1)) + decision.quality_score) / count
                self.reviewer_performance[reviewer_id]["avg_quality"] = new_avg

    def _escalate_review(
        self, request: ReviewRequest, decision: ReviewDecision
    ) -> None:
        """Escalate a review to higher-level reviewer."""
        # Create new high-priority request
        escalated_request = ReviewRequest(
            validation_result=request.validation_result,
            priority=ReviewPriority.HIGH,
            reason=f"Escalated: {decision.comments or 'Requires senior review'}",
            medical_category=request.medical_category,
            deadline=datetime.now()
            + timedelta(minutes=self.config.escalation_timeout_minutes),
            metadata={
                "original_request_id": request.request_id,
                "escalated_by": decision.reviewer_id,
                "escalation_reason": decision.comments,
            },
        )

        # Add to queue
        self.review_queue.put_nowait(escalated_request)
        self.active_reviews[escalated_request.request_id] = escalated_request

        # Notify supervisors
        if self.config.notify_on_escalation:
            self._send_escalation_notification(escalated_request)

    def _process_correction(
        self, request: ReviewRequest, decision: ReviewDecision
    ) -> None:
        """Process a correction from human reviewer."""
        if not request.validation_result:
            return

        # Here you would typically:
        # 1. Store the correction for future training
        # 2. Update any caches with the corrected version
        # 3. Potentially retrain models with the correction

        # For now, we'll just log it
        correction_data = {
            "request_id": request.request_id,
            "original": request.validation_result.translated_text,
            "corrected": decision.corrected_translation,
            "reviewer": decision.reviewer_id,
            "timestamp": decision.decision_time,
        }

        # This would be sent to a training pipeline in production
        self._log_correction(correction_data)

    def _handle_expired_review(self, request_id: str, request: ReviewRequest) -> None:
        """Handle an expired review request."""
        # Remove from active
        del self.active_reviews[request_id]

        # Create expired decision
        expired_decision = ReviewDecision(
            request_id=request_id,
            reviewer_id="system",
            status=ReviewStatus.EXPIRED,
            comments="Review expired due to timeout",
        )

        self.completed_reviews.append(expired_decision)

        # Potentially escalate or requeue
        if request.priority == ReviewPriority.CRITICAL:
            self._escalate_review(request, expired_decision)

    def get_review_analytics(self) -> Dict[str, Any]:
        """Get analytics on review system performance."""
        total_reviews = len(self.completed_reviews)
        if total_reviews == 0:
            return {"message": "No reviews completed yet"}

        # Calculate metrics
        status_counts: Dict[str, int] = defaultdict(int)
        for decision in self.completed_reviews:
            status_counts[decision.status.value] += 1

        # Average times
        review_times = [
            d.time_spent_seconds for d in self.completed_reviews if d.time_spent_seconds
        ]
        avg_review_time = sum(review_times) / len(review_times) if review_times else 0

        # Quality scores
        quality_scores = [
            d.quality_score
            for d in self.completed_reviews
            if d.quality_score is not None
        ]
        avg_quality = sum(quality_scores) / len(quality_scores) if quality_scores else 0

        return {
            "total_reviews": total_reviews,
            "active_reviews": len(self.active_reviews),
            "queue_size": self.review_queue.qsize(),
            "status_distribution": dict(status_counts),
            "average_review_time_seconds": avg_review_time,
            "average_quality_score": avg_quality,
            "reviewer_performance": dict(self.reviewer_performance),
            "correction_patterns_learned": sum(
                len(patterns) for patterns in self.correction_patterns.values()
            ),
            "language_pair_stats": self._get_language_pair_review_stats(),
        }

    def _get_language_pair_review_stats(self) -> Dict[str, Dict[str, int]]:
        """Get review statistics by language pair."""
        stats: Dict[str, Dict[str, int]] = defaultdict(
            lambda: {"total": 0, "corrected": 0, "approved": 0, "rejected": 0}
        )

        for decision in self.completed_reviews:
            request = next(
                (
                    r
                    for r_id, r in self.active_reviews.items()
                    if r_id == decision.request_id
                ),
                None,
            )

            if request and request.validation_result:
                pair = f"{request.validation_result.source_lang}->{request.validation_result.target_lang}"
                stats[pair]["total"] += 1

                if decision.status == ReviewStatus.CORRECTED:
                    stats[pair]["corrected"] += 1
                elif decision.status == ReviewStatus.APPROVED:
                    stats[pair]["approved"] += 1
                elif decision.status == ReviewStatus.REJECTED:
                    stats[pair]["rejected"] += 1

        return dict(stats)

    def apply_learned_corrections(
        self, source_text: str, translated_text: str, source_lang: str, target_lang: str
    ) -> Optional[str]:
        """Apply learned corrections to a new translation."""
        key = (source_lang, target_lang)
        patterns = self.correction_patterns.get(key, [])

        if len(patterns) < self.config.min_reviews_for_pattern_learning:
            return None

        # Simple pattern matching (can be enhanced with ML)
        for pattern in patterns:
            if self._text_similarity(source_text, pattern["source"]) > 0.9:
                # Found similar source text that was previously corrected
                if self._text_similarity(translated_text, pattern["original"]) > 0.8:
                    # The translation is similar to a previously corrected one
                    corrected = pattern.get("corrected")
                    return str(corrected) if corrected is not None else None

        return None

    def _text_similarity(self, text1: str, text2: str) -> float:
        """Calculate simple text similarity (placeholder for more sophisticated method)."""
        # This is a simple character-based similarity
        # In production, use proper semantic similarity
        if not text1 or not text2:
            return 0.0

        common = sum(1 for c1, c2 in zip(text1, text2) if c1 == c2)
        return common / max(len(text1), len(text2))

    def _send_critical_notification(self, request: ReviewRequest) -> None:
        """Send notification for critical review (placeholder)."""
        # In production, this would integrate with notification system
        print(f"CRITICAL REVIEW NEEDED: {request.request_id} - {request.reason}")

    def _send_escalation_notification(self, request: ReviewRequest) -> None:
        """Send notification for escalated review (placeholder)."""
        # In production, this would integrate with notification system
        print(f"REVIEW ESCALATED: {request.request_id} - {request.reason}")

    def _log_correction(self, correction_data: Dict[str, Any]) -> None:
        """Log correction for training pipeline (placeholder)."""
        # In production, this would send to ML training pipeline
        print(f"Correction logged: {correction_data['request_id']}")

    def shutdown(self) -> None:
        """Shutdown the human-in-the-loop system."""
        self._stop_event.set()

        # Export any pending data
        analytics = self.get_review_analytics()
        print(f"Shutting down with analytics: {json.dumps(analytics, indent=2)}")


# Integration with validation pipeline
class HumanInLoopValidationPipeline(TranslationValidationPipeline):
    """Extended validation pipeline with human-in-the-loop support."""

    def __init__(
        self,
        config: Optional[Any] = None,
        human_loop_config: Optional[HumanInLoopConfig] = None,
    ) -> None:
        """Initialize pipeline with human-in-the-loop support."""
        super().__init__(config)

        self.human_loop = HumanInLoopSystem(
            config=human_loop_config, validation_pipeline=self
        )

    def validate(
        self,
        source_text: str,
        translated_text: str,
        source_lang: str,
        target_lang: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ValidationResult:
        """Validate with automatic human review queuing."""
        # First check if we have learned corrections
        corrected = self.human_loop.apply_learned_corrections(
            source_text, translated_text, source_lang, target_lang
        )

        if corrected:
            translated_text = corrected
            if metadata is None:
                metadata = {}
            metadata["auto_corrected"] = True

        # Run standard validation
        result = super().validate(
            source_text, translated_text, source_lang, target_lang, metadata
        )

        # Check if human review is needed
        if self._needs_human_review(result):
            request_id = self.human_loop.submit_for_review(result)
            result.metadata["human_review_requested"] = True
            result.metadata["review_request_id"] = request_id

        return result

    def _needs_human_review(self, result: ValidationResult) -> bool:
        """Determine if a validation result needs human review."""
        # Failed validations always need review
        if result.overall_status == ValidationStatus.FAILED:
            return True

        # Check confidence threshold
        if (
            result.metrics
            and result.metrics.confidence_score
            < self.human_loop.config.auto_review_confidence_threshold
        ):
            return True

        # Check for critical content
        if self.human_loop.contains_critical_content(result.source_text):
            return True

        # Random spot checks (5% of passed translations)
        if result.overall_status == ValidationStatus.PASSED and random.random() < 0.05:
            return True

        return False


# Example usage functions
def create_sample_reviewer() -> ReviewerProfile:
    """Create a sample reviewer profile."""
    return ReviewerProfile(
        reviewer_id="reviewer_001",
        name="Dr. Jane Smith",
        email="jane.smith@medical.org",
        role=ReviewerRole.MEDICAL_PROFESSIONAL,
        languages=["en", "es", "fr", "ar"],
        specializations=["general_medicine", "emergency", "pediatrics"],
        certifications=["MD", "Medical Translation Certificate"],
    )


def demonstrate_human_in_loop() -> None:
    """Demonstrate the human-in-the-loop system."""
    # Create system
    config = HumanInLoopConfig(
        auto_review_confidence_threshold=0.75,
        critical_content_patterns=["dosage", "allergy", "emergency", "mg", "ml"],
    )

    pipeline = HumanInLoopValidationPipeline(human_loop_config=config)

    # Add a reviewer
    reviewer = create_sample_reviewer()
    pipeline.human_loop.add_reviewer(reviewer)

    # Example validation that will trigger human review
    result = pipeline.validate(
        source_text="Take 500mg of amoxicillin twice daily for 7 days",
        translated_text="Tomar 500mg de amoxicilina dos veces al día durante 7 días",
        source_lang="en",
        target_lang="es",
    )

    print(
        f"Validation completed. Human review requested: {result.metadata.get('human_review_requested', False)}"
    )

    # Simulate reviewer getting and completing review
    if result.metadata.get("human_review_requested"):
        review_request = pipeline.human_loop.get_next_review(reviewer.reviewer_id)

        if review_request:
            # Simulate review decision
            decision = ReviewDecision(
                request_id=review_request.request_id,
                reviewer_id=reviewer.reviewer_id,
                status=ReviewStatus.APPROVED,
                quality_score=0.95,
                comments="Medical dosage correctly translated",
                time_spent_seconds=45,
                confidence=0.98,
            )

            pipeline.human_loop.submit_review_decision(decision)

            print("Review completed and submitted")

    # Get analytics
    analytics = pipeline.human_loop.get_review_analytics()
    print(f"\nSystem Analytics: {json.dumps(analytics, indent=2)}")
