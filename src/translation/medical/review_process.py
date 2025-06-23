"""Medical Translation Review Process.

This module manages the review process for medical translations,
including expert validation, approval workflows, and quality assurance.
"""

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, cast

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from src.models.base import Base
from src.security.access_control import AccessPermission, require_permission
from src.security.audit import audit_phi_access
from src.security.encryption import EncryptionService
from src.utils.logging import get_logger

# Removed circular import - reviewer_management imported dynamically when needed
# from src.services.reviewer_management import reviewer_management

logger = get_logger(__name__)


class ReviewStatus(str, Enum):
    """Translation review status."""

    PENDING = "pending"
    IN_REVIEW = "in_review"
    EXPERT_REVIEW = "expert_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    REVISION_REQUESTED = "revision_requested"
    FINAL_APPROVED = "final_approved"


class ReviewerRole(str, Enum):
    """Reviewer roles and expertise."""

    MEDICAL_TRANSLATOR = "medical_translator"
    CLINICAL_EXPERT = "clinical_expert"
    NATIVE_SPEAKER = "native_speaker"
    TERMINOLOGIST = "terminologist"
    QUALITY_ASSURANCE = "quality_assurance"
    SENIOR_REVIEWER = "senior_reviewer"


class ReviewPriority(str, Enum):
    """Review priority levels."""

    CRITICAL = "critical"  # Safety-critical content
    HIGH = "high"  # Important medical information
    MEDIUM = "medium"  # General medical content
    LOW = "low"  # Non-critical content


@dataclass
class ReviewCriteria:
    """Criteria for translation review."""

    medical_accuracy: bool = True
    terminology_consistency: bool = True
    cultural_appropriateness: bool = True
    readability: bool = True
    completeness: bool = True
    safety_compliance: bool = True
    regulatory_compliance: bool = False


@dataclass
class ReviewComment:
    """Review comment on translation."""

    reviewer_id: str
    reviewer_role: ReviewerRole
    comment_type: str  # error, suggestion, question, approval
    text: str
    severity: str  # critical, major, minor
    position: Optional[Tuple[int, int]] = None  # start, end position
    created_at: datetime = field(default_factory=datetime.utcnow)
    resolved: bool = False
    resolution: Optional[str] = None


@dataclass
class ReviewDecision:
    """Review decision for a translation."""

    reviewer_id: str
    reviewer_role: ReviewerRole
    decision: ReviewStatus
    score: float  # 0-100
    comments: List[ReviewComment]
    criteria_met: Dict[str, bool]
    reviewed_at: datetime = field(default_factory=datetime.utcnow)


# Database Models
class TranslationReview(Base):
    """Translation review record."""

    __tablename__ = "translation_reviews"

    id = Column(Integer, primary_key=True)
    translation_id = Column(String(100), nullable=False, index=True)
    source_text = Column(Text, nullable=False)
    translated_text = Column(Text, nullable=False)
    source_language = Column(String(10), nullable=False)
    target_language = Column(String(10), nullable=False)
    medical_context = Column(String(100))
    priority = Column(String(20), default=ReviewPriority.MEDIUM.value)
    status = Column(String(30), default=ReviewStatus.PENDING.value)

    # Review metadata
    submitted_at = Column(DateTime, default=datetime.utcnow)
    submitted_by = Column(String(100))
    completed_at = Column(DateTime)
    final_translation = Column(Text)

    # Scores
    accuracy_score = Column(Float)
    overall_score = Column(Float)

    # Relationships
    review_rounds = relationship("ReviewRound", back_populates="translation_review")
    assignments = relationship("ReviewAssignment", back_populates="translation_review")


class ReviewRound(Base):
    """Individual review round."""

    __tablename__ = "review_rounds"

    id = Column(Integer, primary_key=True)
    review_id = Column(Integer, ForeignKey("translation_reviews.id"))
    round_number = Column(Integer, default=1)
    status = Column(String(30))
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)

    # Review decisions
    decisions = Column(Text)  # JSON array of ReviewDecision
    consensus_reached = Column(Boolean, default=False)
    final_decision = Column(String(30))

    # Relationships
    translation_review = relationship(
        "TranslationReview", back_populates="review_rounds"
    )


class ReviewAssignment(Base):
    """Review assignment to specific reviewer."""

    __tablename__ = "review_assignments"

    id = Column(Integer, primary_key=True)
    review_id = Column(Integer, ForeignKey("translation_reviews.id"))
    reviewer_id = Column(String(100), nullable=False)
    reviewer_role = Column(String(30), nullable=False)
    assigned_at = Column(DateTime, default=datetime.utcnow)
    due_date = Column(DateTime)
    completed_at = Column(DateTime)
    status = Column(String(30), default="assigned")

    # Relationships
    translation_review = relationship("TranslationReview", back_populates="assignments")


class MedicalReviewProcess:
    """Manages the medical translation review process."""

    # Review requirements by context
    REVIEW_REQUIREMENTS = {
        "medication_instructions": {
            "min_reviewers": 2,
            "required_roles": [
                ReviewerRole.CLINICAL_EXPERT,
                ReviewerRole.MEDICAL_TRANSLATOR,
            ],
            "consensus_required": True,
        },
        "surgical_consent": {
            "min_reviewers": 3,
            "required_roles": [
                ReviewerRole.CLINICAL_EXPERT,
                ReviewerRole.MEDICAL_TRANSLATOR,
                ReviewerRole.SENIOR_REVIEWER,
            ],
            "consensus_required": True,
        },
        "emergency_procedures": {
            "min_reviewers": 2,
            "required_roles": [
                ReviewerRole.CLINICAL_EXPERT,
                ReviewerRole.MEDICAL_TRANSLATOR,
            ],
            "consensus_required": True,
        },
        "general_medical": {
            "min_reviewers": 1,
            "required_roles": [ReviewerRole.MEDICAL_TRANSLATOR],
            "consensus_required": False,
        },
    }

    def __init__(self) -> None:
        """Initialize review process manager."""
        self.active_reviews: Dict[str, TranslationReview] = {}
        self.reviewer_pool: Dict[ReviewerRole, List[str]] = {}
        self.review_metrics: Dict[str, Any] = {
            "total_reviews": 0,
            "approved": 0,
            "rejected": 0,
            "avg_review_time": timedelta(),
            "avg_rounds": 0,
        }
        self.encryption_service = EncryptionService(
            kms_key_id="alias/haven-health-default"
        )

    async def submit_for_review(
        self,
        translation_id: str,
        source_text: str,
        translated_text: str,
        source_language: str,
        target_language: str,
        medical_context: str,
        accuracy_score: Optional[float] = None,
        submitted_by: Optional[str] = None,
        priority: Optional[ReviewPriority] = None,
    ) -> str:
        """Submit translation for review."""
        # Determine priority if not specified
        if priority is None:
            priority = self._determine_priority(medical_context, accuracy_score)

        # Create review record
        review = TranslationReview(
            translation_id=translation_id,
            source_text=source_text,
            translated_text=translated_text,
            source_language=source_language,
            target_language=target_language,
            medical_context=medical_context,
            priority=priority.value,
            accuracy_score=accuracy_score,
            submitted_by=submitted_by,
        )

        # Assign reviewers based on requirements
        requirements = self.REVIEW_REQUIREMENTS.get(
            medical_context, self.REVIEW_REQUIREMENTS["general_medical"]
        )

        assignments = await self._assign_reviewers(review, requirements)

        # Store active review
        self.active_reviews[translation_id] = review

        logger.info(
            f"Translation {translation_id} submitted for review "
            f"with {len(assignments)} reviewers"
        )

        return str(review.id)

    def _determine_priority(
        self, medical_context: str, accuracy_score: Optional[float]
    ) -> ReviewPriority:
        """Determine review priority based on context and score."""
        # Critical contexts always get high priority
        critical_contexts = {
            "medication_instructions",
            "surgical_consent",
            "emergency_procedures",
            "allergy_warnings",
        }

        if medical_context in critical_contexts:
            return ReviewPriority.CRITICAL

        # Low accuracy scores increase priority
        if accuracy_score is not None:
            if accuracy_score < 80:
                return ReviewPriority.HIGH
            if accuracy_score < 90:
                return ReviewPriority.MEDIUM

        return ReviewPriority.LOW

    async def _assign_reviewers(
        self, review: TranslationReview, requirements: Dict[str, Any]
    ) -> List[ReviewAssignment]:
        """Assign appropriate reviewers to translation."""
        assignments = []

        # Get available reviewers for each required role
        for role in requirements["required_roles"]:
            available_reviewers = await self._get_available_reviewers(
                role,
                str(review.source_language),
                str(review.target_language),
                medical_context=(
                    str(review.medical_context) if review.medical_context else None
                ),
                urgency=(
                    "urgent"
                    if review.priority == ReviewPriority.CRITICAL.value
                    else "normal"
                ),
            )

            if available_reviewers:
                # Assign based on workload and expertise
                reviewer_id = self._select_best_reviewer(available_reviewers, review)

                due_date = self._calculate_due_date(str(review.priority))

                assignment = ReviewAssignment(
                    review_id=review.id,
                    reviewer_id=reviewer_id,
                    reviewer_role=role.value,
                    due_date=due_date,
                )
                assignments.append(assignment)

                # Notify reviewer management system
                # Import dynamically to avoid circular import
                from src.services.reviewer_management import (  # pylint: disable=import-outside-toplevel
                    reviewer_management,
                )

                await reviewer_management.assign_review(
                    reviewer_id=reviewer_id, review_id=str(review.id), due_date=due_date
                )
            else:
                logger.warning(
                    "No available reviewer for role %s ",
                    role,
                    f"for languages {review.source_language}->{review.target_language}",
                )

        return assignments

    async def _get_available_reviewers(
        self,
        role: ReviewerRole,
        source_language: str,
        target_language: str,
        medical_context: Optional[str] = None,
        urgency: str = "normal",
    ) -> List[str]:
        """Get available reviewers for role and language pair."""
        # Use real reviewer management system
        from src.services.reviewer_management import (  # pylint: disable=import-outside-toplevel
            reviewer_management,
        )

        available = await reviewer_management.get_available_reviewers(
            role=role,
            source_language=source_language,
            target_language=target_language,
            required_expertise=medical_context,
            document_type=medical_context,
            urgency=urgency,
        )

        return available

    def _select_best_reviewer(
        self,
        available_reviewers: List[str],
        _review: TranslationReview,
    ) -> str:
        """Select best reviewer based on workload and expertise."""
        if not available_reviewers:
            raise ValueError("No reviewers available")

        # The reviewer management system already returns reviewers
        # sorted by suitability, so we can just take the first one
        return available_reviewers[0]

    def _calculate_due_date(self, priority: str) -> datetime:
        """Calculate review due date based on priority."""
        due_times = {
            ReviewPriority.CRITICAL.value: timedelta(hours=4),
            ReviewPriority.HIGH.value: timedelta(hours=24),
            ReviewPriority.MEDIUM.value: timedelta(days=2),
            ReviewPriority.LOW.value: timedelta(days=5),
        }

        due_delta = due_times.get(priority, timedelta(days=2))
        return datetime.utcnow() + due_delta

    async def submit_review_decision(
        self,
        review_id: str,
        _reviewer_id: str,
        decision: ReviewDecision,  # pylint: disable=unused-argument
    ) -> bool:
        """Submit a review decision."""
        review = self.active_reviews.get(review_id)
        if not review:
            logger.error("Review %s not found", review_id)
            return False

        # Get current round
        current_round = self._get_current_round(review)
        if not current_round:
            # Create first round
            current_round = ReviewRound(
                review_id=review.id, round_number=1, status=ReviewStatus.IN_REVIEW.value
            )

        # Add decision to round
        decisions_str = getattr(current_round, "decisions", None) or "[]"
        decisions = json.loads(decisions_str)
        decisions.append(
            {
                "reviewer_id": decision.reviewer_id,
                "reviewer_role": decision.reviewer_role.value,
                "decision": decision.decision.value,
                "score": decision.score,
                "comments": [
                    {"type": c.comment_type, "text": c.text, "severity": c.severity}
                    for c in decision.comments
                ],
                "reviewed_at": decision.reviewed_at.isoformat(),
            }
        )
        current_round.decisions = json.dumps(decisions)

        # Check if round is complete
        if self._is_round_complete(review, current_round):
            await self._process_round_completion(review, current_round)

        return True

    def _get_current_round(self, review: TranslationReview) -> Optional[ReviewRound]:
        """Get current review round."""
        # Get latest incomplete round
        for review_round in sorted(
            review.review_rounds, key=lambda r: r.round_number, reverse=True
        ):
            if not review_round.completed_at:
                return cast(ReviewRound, review_round)
        return None

    def _is_round_complete(
        self, review: TranslationReview, review_round: ReviewRound
    ) -> bool:
        """Check if review round is complete."""
        # Get expected number of reviews
        requirements = self.REVIEW_REQUIREMENTS.get(
            (
                str(review.medical_context)
                if review.medical_context
                else "general_medical"
            ),
            self.REVIEW_REQUIREMENTS["general_medical"],
        )

        decisions_str = getattr(review_round, "decisions", None) or "[]"
        decisions = json.loads(decisions_str)
        min_reviewers_value = requirements.get("min_reviewers", 1)
        min_reviewers = (
            int(str(min_reviewers_value)) if min_reviewers_value is not None else 1
        )
        return bool(len(decisions) >= min_reviewers)

    async def _process_round_completion(
        self, review: TranslationReview, review_round: ReviewRound
    ) -> None:
        """Process completion of a review round."""
        decisions = json.loads(str(review_round.decisions))
        requirements = self.REVIEW_REQUIREMENTS.get(
            (
                str(review.medical_context)
                if review.medical_context
                else "general_medical"
            ),
            self.REVIEW_REQUIREMENTS["general_medical"],
        )

        # Check for consensus
        decision_values = [d["decision"] for d in decisions]
        unique_decisions = set(decision_values)

        if len(unique_decisions) == 1:
            # Consensus reached
            review_round.consensus_reached = True
            review_round.final_decision = decision_values[0]
            review_round.completed_at = datetime.utcnow()

            # Update review status
            if review_round.final_decision == ReviewStatus.APPROVED.value:
                review.status = ReviewStatus.FINAL_APPROVED.value
                review.completed_at = datetime.utcnow()
                self._update_metrics(review, "approved")
            elif review_round.final_decision == ReviewStatus.REJECTED.value:
                review.status = ReviewStatus.REJECTED.value
                review.completed_at = datetime.utcnow()
                self._update_metrics(review, "rejected")
        else:
            # No consensus
            if requirements["consensus_required"]:
                # Need another round or escalation
                await self._initiate_next_round(review, review_round)
            else:
                # Use majority decision
                majority_decision = max(unique_decisions, key=decision_values.count)
                review_round.final_decision = majority_decision
                review_round.completed_at = datetime.utcnow()
                review.status = majority_decision

    async def _initiate_next_round(
        self, review: TranslationReview, previous_round: ReviewRound
    ) -> None:
        """Initiate next review round."""
        # Create new round
        new_round = ReviewRound(
            review_id=review.id,
            round_number=previous_round.round_number + 1,
            status=ReviewStatus.EXPERT_REVIEW.value,
        )

        # Assign senior reviewer for conflict resolution
        senior_reviewer_id = await self._get_senior_reviewer(review)

        due_date = datetime.utcnow() + timedelta(hours=12)
        # assignment would be saved to database in production
        ReviewAssignment(
            review_id=review.id,
            reviewer_id=senior_reviewer_id,
            reviewer_role=ReviewerRole.SENIOR_REVIEWER.value,
            due_date=due_date,
        )

        # Notify reviewer management system
        from src.services.reviewer_management import (  # pylint: disable=import-outside-toplevel
            reviewer_management,
        )

        await reviewer_management.assign_review(
            reviewer_id=senior_reviewer_id,
            review_id=str(review.id),
            due_date=due_date,
        )

        logger.info(
            "Initiated round %d for review %s", new_round.round_number, review.id
        )

    async def _get_senior_reviewer(self, review: TranslationReview) -> str:
        """Get available senior reviewer."""
        from src.services.reviewer_management import (  # pylint: disable=import-outside-toplevel
            reviewer_management,
        )

        senior_reviewers = await reviewer_management.get_available_reviewers(
            role=ReviewerRole.SENIOR_REVIEWER,
            source_language=str(review.source_language),
            target_language=str(review.target_language),
            urgency="urgent",  # Senior reviews are usually urgent
        )

        if not senior_reviewers:
            logger.error("No senior reviewers available")
            # Fall back to any available clinical expert
            senior_reviewers = await reviewer_management.get_available_reviewers(
                role=ReviewerRole.CLINICAL_EXPERT,
                source_language=str(review.source_language),
                target_language=str(review.target_language),
                urgency="urgent",
            )

        if not senior_reviewers:
            raise ValueError("No senior reviewers available for conflict resolution")

        return senior_reviewers[0]

    @audit_phi_access("phi_access__update_metrics")
    @require_permission(AccessPermission.READ_PHI)
    def _update_metrics(self, review: TranslationReview, outcome: str) -> None:
        """Update review process metrics."""
        self.review_metrics["total_reviews"] += 1
        self.review_metrics[outcome] += 1

        # Calculate review time
        review_time = review.completed_at - review.submitted_at
        # Update average (simplified)
        avg_time = self.review_metrics["avg_review_time"]
        total_reviews = self.review_metrics["total_reviews"]
        self.review_metrics["avg_review_time"] = (
            avg_time * (total_reviews - 1) + review_time
        ) / total_reviews

    def get_review_status(self, review_id: str) -> Dict[str, Any]:
        """Get current status of a review."""
        review = self.active_reviews.get(review_id)
        if not review:
            return {"error": "Review not found"}

        current_round = self._get_current_round(review)

        return {
            "review_id": review_id,
            "status": review.status,
            "priority": review.priority,
            "current_round": current_round.round_number if current_round else 0,
            "submitted_at": review.submitted_at.isoformat(),
            "assignments": [
                {
                    "reviewer_id": a.reviewer_id,
                    "role": a.reviewer_role,
                    "status": a.status,
                    "due_date": a.due_date.isoformat() if a.due_date else None,
                }
                for a in review.assignments
            ],
        }

    def get_pending_reviews(self, reviewer_id: str) -> List[Dict[str, Any]]:
        """Get pending reviews for a reviewer."""
        pending = []

        for review in self.active_reviews.values():
            for assignment in review.assignments:
                if (
                    assignment.reviewer_id == reviewer_id
                    and assignment.status == "assigned"
                ):
                    pending.append(
                        {
                            "review_id": review.id,
                            "translation_id": review.translation_id,
                            "priority": review.priority,
                            "due_date": assignment.due_date.isoformat(),
                            "medical_context": review.medical_context,
                            "languages": f"{review.source_language} -> {review.target_language}",
                        }
                    )

        return sorted(pending, key=lambda x: x["due_date"])

    def get_review_metrics(self) -> Dict[str, Any]:
        """Get review process metrics."""
        metrics = self.review_metrics.copy()

        # Calculate approval rate
        total = metrics["total_reviews"]
        if total > 0:
            metrics["approval_rate"] = (metrics["approved"] / total) * 100
            metrics["rejection_rate"] = (metrics["rejected"] / total) * 100

        # Format average time
        avg_time = metrics["avg_review_time"]
        metrics["avg_review_hours"] = avg_time.total_seconds() / 3600

        return metrics


# Global review process manager
review_process = MedicalReviewProcess()
