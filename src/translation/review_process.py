"""
Medical Translation Review Process.

This module implements a structured review process for medical translations,
including workflow management, reviewer assignment, and approval tracking.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Session

from src.healthcare.hipaa_access_control import AccessLevel, require_phi_access
from src.models.base import BaseModel
from src.security.encryption import EncryptionService
from src.utils.logging import get_logger

logger = get_logger(__name__)


class ReviewStatus(str, Enum):
    """Translation review status."""

    PENDING = "pending"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    REVISION_REQUESTED = "revision_requested"
    EXPIRED = "expired"


class ReviewerRole(str, Enum):
    """Types of reviewers."""

    MEDICAL_PROFESSIONAL = "medical_professional"
    NATIVE_SPEAKER = "native_speaker"
    TRANSLATION_SPECIALIST = "translation_specialist"
    CLINICAL_REVIEWER = "clinical_reviewer"
    COMMUNITY_REVIEWER = "community_reviewer"


class ReviewPriority(str, Enum):
    """Review priority levels."""

    CRITICAL = "critical"  # Safety-critical content
    HIGH = "high"  # Important medical information
    NORMAL = "normal"  # Standard content
    LOW = "low"  # Non-critical content


@dataclass
class ReviewRequirements:
    """Requirements for translation review."""

    min_reviewers: int = 2
    required_roles: List[ReviewerRole] = field(default_factory=list)
    require_medical_reviewer: bool = True
    require_native_speaker: bool = True
    consensus_required: bool = True
    review_deadline_hours: int = 48


class TranslationReview(BaseModel):
    """Database model for translation reviews."""

    __tablename__ = "translation_reviews"

    # Review identification
    review_id = Column(String(36), default=lambda: str(uuid4()), unique=True)
    translation_id = Column(String(36), nullable=False, index=True)

    # Content
    source_text = Column(Text, nullable=False)
    translated_text = Column(Text, nullable=False)
    source_language = Column(String(10), nullable=False)
    target_language = Column(String(10), nullable=False)

    # Review metadata
    content_type = Column(String(50))  # prescription, diagnosis, etc.
    priority = Column(String(20), default=ReviewPriority.NORMAL.value)
    status = Column(String(30), default=ReviewStatus.PENDING.value)

    # Requirements
    requirements = Column(JSON, default=dict)

    # Tracking
    submitted_by = Column(String(36), nullable=False)
    submitted_at = Column(DateTime, default=datetime.utcnow)
    deadline = Column(DateTime)
    completed_at = Column(DateTime)

    # Results
    final_translation = Column(Text)
    approval_count = Column(Integer, default=0)
    rejection_count = Column(Integer, default=0)
    consensus_reached = Column(Boolean, default=False)


class ReviewAssignment(BaseModel):
    """Database model for reviewer assignments."""

    __tablename__ = "review_assignments"

    # Assignment identification
    assignment_id = Column(String(36), default=lambda: str(uuid4()), unique=True)
    review_id = Column(String(36), ForeignKey("translation_reviews.id"), nullable=False)
    reviewer_id = Column(String(36), nullable=False, index=True)

    # Reviewer info
    reviewer_role = Column(String(30), nullable=False)
    reviewer_languages = Column(JSON, default=list)

    # Assignment metadata
    assigned_at = Column(DateTime, default=datetime.utcnow)
    accepted_at = Column(DateTime)
    completed_at = Column(DateTime)

    # Review details
    decision = Column(String(30))  # approved, rejected, revision_requested
    comments = Column(Text)
    suggested_translation = Column(Text)
    quality_score = Column(Integer)  # 1-5

    # Issues found
    issues_found = Column(JSON, default=list)


class ReviewComment(BaseModel):
    """Database model for review comments."""

    __tablename__ = "review_comments"

    # Comment identification
    comment_id = Column(String(36), default=lambda: str(uuid4()), unique=True)
    review_id = Column(String(36), ForeignKey("translation_reviews.id"), nullable=False)

    # Comment details
    reviewer_id = Column(String(36), nullable=False)
    comment_text = Column(Text, nullable=False)
    comment_type = Column(String(30))  # general, correction, suggestion

    # Position in text (optional)
    start_position = Column(Integer)
    end_position = Column(Integer)
    highlighted_text = Column(String(500))

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    is_resolved = Column(Boolean, default=False)
    resolved_at = Column(DateTime)
    resolved_by = Column(String(36))


class MedicalReviewProcess:
    """Manages the medical translation review process."""

    # Review requirements by content type
    CONTENT_TYPE_REQUIREMENTS = {
        "prescription": ReviewRequirements(
            min_reviewers=3,
            required_roles=[
                ReviewerRole.MEDICAL_PROFESSIONAL,
                ReviewerRole.NATIVE_SPEAKER,
                ReviewerRole.CLINICAL_REVIEWER,
            ],
            require_medical_reviewer=True,
            require_native_speaker=True,
            consensus_required=True,
            review_deadline_hours=24,
        ),
        "diagnosis": ReviewRequirements(
            min_reviewers=2,
            required_roles=[
                ReviewerRole.MEDICAL_PROFESSIONAL,
                ReviewerRole.TRANSLATION_SPECIALIST,
            ],
            require_medical_reviewer=True,
            require_native_speaker=True,
            consensus_required=True,
            review_deadline_hours=48,
        ),
        "patient_instructions": ReviewRequirements(
            min_reviewers=2,
            required_roles=[
                ReviewerRole.NATIVE_SPEAKER,
                ReviewerRole.COMMUNITY_REVIEWER,
            ],
            require_medical_reviewer=False,
            require_native_speaker=True,
            consensus_required=False,
            review_deadline_hours=72,
        ),
        "lab_results": ReviewRequirements(
            min_reviewers=2,
            required_roles=[
                ReviewerRole.MEDICAL_PROFESSIONAL,
                ReviewerRole.TRANSLATION_SPECIALIST,
            ],
            require_medical_reviewer=True,
            require_native_speaker=False,
            consensus_required=True,
            review_deadline_hours=24,
        ),
    }

    def __init__(self, session: Session):
        """Initialize review process manager."""
        self.encryption_service = EncryptionService(
            kms_key_id="alias/haven-health-default"
        )
        self.session = session

    @require_phi_access(AccessLevel.WRITE)
    def submit_for_review(
        self,
        source_text: str,
        translated_text: str,
        source_language: str,
        target_language: str,
        content_type: str,
        submitted_by: UUID,
        priority: ReviewPriority = ReviewPriority.NORMAL,
        translation_id: Optional[UUID] = None,
    ) -> TranslationReview:
        """Submit a translation for review."""
        # Get requirements for content type
        requirements = self.CONTENT_TYPE_REQUIREMENTS.get(
            content_type, ReviewRequirements()
        )

        # Calculate deadline based on priority
        deadline_hours = requirements.review_deadline_hours
        if priority == ReviewPriority.CRITICAL:
            deadline_hours = min(6, deadline_hours)
        elif priority == ReviewPriority.HIGH:
            deadline_hours = min(24, deadline_hours)

        deadline = datetime.utcnow() + timedelta(hours=deadline_hours)

        # Create review record
        review = TranslationReview(
            translation_id=translation_id or uuid4(),
            source_text=source_text,
            translated_text=translated_text,
            source_language=source_language,
            target_language=target_language,
            content_type=content_type,
            priority=priority.value,
            submitted_by=str(submitted_by),
            deadline=deadline,
            requirements={
                "min_reviewers": requirements.min_reviewers,
                "required_roles": [r.value for r in requirements.required_roles],
                "require_medical_reviewer": requirements.require_medical_reviewer,
                "require_native_speaker": requirements.require_native_speaker,
                "consensus_required": requirements.consensus_required,
            },
        )

        self.session.add(review)
        self.session.commit()

        logger.info(f"Translation submitted for review: {review.review_id}")

        return review

    def assign_reviewer(
        self,
        review_id: str,
        reviewer_id: UUID,
        reviewer_role: ReviewerRole,
        reviewer_languages: List[str],
    ) -> ReviewAssignment:
        """Assign a reviewer to a translation."""
        # Check if review exists
        review = (
            self.session.query(TranslationReview)
            .filter(TranslationReview.review_id == review_id)
            .first()
        )

        if not review:
            raise ValueError(f"Review {review_id} not found")

        # Check if already assigned
        existing = (
            self.session.query(ReviewAssignment)
            .filter(
                ReviewAssignment.review_id == review.id,
                ReviewAssignment.reviewer_id == str(reviewer_id),
            )
            .first()
        )

        if existing:
            logger.warning(f"Reviewer {reviewer_id} already assigned to {review_id}")
            return existing

        # Create assignment
        assignment = ReviewAssignment(
            review_id=review.id,
            reviewer_id=str(reviewer_id),
            reviewer_role=reviewer_role.value,
            reviewer_languages=reviewer_languages,
        )

        self.session.add(assignment)

        # Update review status
        review.status = ReviewStatus.IN_REVIEW.value

        self.session.commit()

        logger.info(f"Reviewer {reviewer_id} assigned to review {review_id}")

        return assignment

    def submit_review_decision(
        self,
        review_id: str,
        reviewer_id: UUID,
        decision: str,
        comments: Optional[str] = None,
        suggested_translation: Optional[str] = None,
        quality_score: Optional[int] = None,
        issues: Optional[List[Dict]] = None,
    ) -> bool:
        """Submit a reviewer's decision."""
        # Get assignment
        assignment = (
            self.session.query(ReviewAssignment)
            .join(TranslationReview)
            .filter(
                TranslationReview.review_id == review_id,
                ReviewAssignment.reviewer_id == str(reviewer_id),
            )
            .first()
        )

        if not assignment:
            logger.error(
                f"Assignment not found for reviewer {reviewer_id} on {review_id}"
            )
            return False

        # Update assignment
        assignment.completed_at = datetime.utcnow()
        assignment.decision = decision
        assignment.comments = comments
        assignment.suggested_translation = suggested_translation
        assignment.quality_score = quality_score
        assignment.issues_found = issues or []

        # Get review
        review = (
            self.session.query(TranslationReview)
            .filter(TranslationReview.review_id == review_id)
            .first()
        )

        if review:
            # Update counts
            if decision == "approved":
                review.approval_count += 1
            elif decision == "rejected":
                review.rejection_count += 1

            # Check if review is complete
            self._check_review_completion(review)

        self.session.commit()

        logger.info(f"Review decision submitted: {review_id} - {decision}")

        return True

    def add_comment(
        self,
        review_id: str,
        reviewer_id: UUID,
        comment_text: str,
        comment_type: str = "general",
        start_position: Optional[int] = None,
        end_position: Optional[int] = None,
        highlighted_text: Optional[str] = None,
    ) -> ReviewComment:
        """Add a comment to a review."""
        # Get review
        review = (
            self.session.query(TranslationReview)
            .filter(TranslationReview.review_id == review_id)
            .first()
        )

        if not review:
            raise ValueError(f"Review {review_id} not found")

        # Create comment
        comment = ReviewComment(
            review_id=review.id,
            reviewer_id=str(reviewer_id),
            comment_text=comment_text,
            comment_type=comment_type,
            start_position=start_position,
            end_position=end_position,
            highlighted_text=highlighted_text,
        )

        self.session.add(comment)
        self.session.commit()

        return comment

    def _check_review_completion(self, review: TranslationReview) -> None:
        """Check if review meets completion criteria."""
        requirements = review.requirements

        # Get all assignments
        assignments = (
            self.session.query(ReviewAssignment)
            .filter(
                ReviewAssignment.review_id == review.id,
                ReviewAssignment.completed_at.isnot(None),
            )
            .all()
        )

        completed_count = len(assignments)

        # Check minimum reviewers
        if completed_count < requirements.get("min_reviewers", 2):
            return

        # Check required roles
        assigned_roles = {a.reviewer_role for a in assignments}
        required_roles = set(requirements.get("required_roles", []))

        if not required_roles.issubset(assigned_roles):
            return

        # Check consensus
        if requirements.get("consensus_required", True):
            # All reviewers must approve
            if review.approval_count == completed_count:
                review.status = ReviewStatus.APPROVED.value  # type: ignore[assignment]
                review.consensus_reached = True  # type: ignore[assignment]
                review.completed_at = datetime.utcnow()  # type: ignore[assignment]

                # Use most recent suggested translation if any
                latest_suggestion = None
                for assignment in assignments:
                    if assignment.suggested_translation:
                        latest_suggestion = assignment.suggested_translation

                review.final_translation = latest_suggestion or review.translated_text

            elif review.rejection_count > 0:
                review.status = ReviewStatus.REVISION_REQUESTED.value  # type: ignore[assignment]
                review.completed_at = datetime.utcnow()  # type: ignore[assignment]
        else:
            # Majority approval
            if review.approval_count > review.rejection_count:
                review.status = ReviewStatus.APPROVED.value  # type: ignore[assignment]
                review.completed_at = datetime.utcnow()  # type: ignore[assignment]
                review.final_translation = review.translated_text
            elif review.rejection_count > review.approval_count:
                review.status = ReviewStatus.REVISION_REQUESTED.value  # type: ignore[assignment]
                review.completed_at = datetime.utcnow()  # type: ignore[assignment]

    def get_pending_reviews(
        self,
        reviewer_id: Optional[UUID] = None,
        content_type: Optional[str] = None,
        language_pair: Optional[Tuple[str, str]] = None,
    ) -> List[TranslationReview]:
        """Get pending reviews with optional filters."""
        query = self.session.query(TranslationReview).filter(
            TranslationReview.status.in_(
                [ReviewStatus.PENDING.value, ReviewStatus.IN_REVIEW.value]
            )
        )

        if content_type:
            query = query.filter(TranslationReview.content_type == content_type)

        if language_pair:
            source_lang, target_lang = language_pair
            query = query.filter(
                TranslationReview.source_language == source_lang,
                TranslationReview.target_language == target_lang,
            )

        if reviewer_id:
            # Filter by assigned reviewer
            query = query.join(ReviewAssignment).filter(
                ReviewAssignment.reviewer_id == str(reviewer_id),
                ReviewAssignment.completed_at.is_(None),
            )

        return query.order_by(
            TranslationReview.priority.desc(), TranslationReview.deadline.asc()
        ).all()

    def get_review_statistics(
        self, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Get review process statistics."""
        query = self.session.query(TranslationReview)

        if start_date:
            query = query.filter(TranslationReview.submitted_at >= start_date)
        if end_date:
            query = query.filter(TranslationReview.submitted_at <= end_date)

        reviews = query.all()

        stats: Dict[str, Any] = {
            "total_reviews": len(reviews),
            "by_status": {},
            "by_content_type": {},
            "by_language_pair": {},
            "average_review_time": None,
            "consensus_rate": 0,
            "approval_rate": 0,
        }

        # Calculate statistics
        completed_reviews = [r for r in reviews if r.completed_at]

        if completed_reviews:
            # Average review time
            review_times = [
                (r.completed_at - r.submitted_at).total_seconds() / 3600
                for r in completed_reviews
            ]
            stats["average_review_time"] = sum(review_times) / len(review_times)

            # Consensus rate
            consensus_count = sum(1 for r in completed_reviews if r.consensus_reached)
            stats["consensus_rate"] = consensus_count / len(completed_reviews) * 100

            # Approval rate
            approved_count = sum(
                1 for r in completed_reviews if r.status == ReviewStatus.APPROVED.value
            )
            stats["approval_rate"] = approved_count / len(completed_reviews) * 100

        # Group by status
        for review in reviews:
            status = review.status
            stats["by_status"][status] = stats["by_status"].get(status, 0) + 1

        # Group by content type
        for review in reviews:
            content_type = review.content_type
            stats["by_content_type"][content_type] = (
                stats["by_content_type"].get(content_type, 0) + 1
            )

        # Group by language pair
        for review in reviews:
            pair = f"{review.source_language}->{review.target_language}"
            stats["by_language_pair"][pair] = stats["by_language_pair"].get(pair, 0) + 1

        return stats
