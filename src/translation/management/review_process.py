"""Translation Review Process.

This module implements the review process for translations,
enabling quality control and approval workflows.
"""

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.translation.management.version_control import (
    TranslationVersion,
    TranslationVersionControl,
)
from src.utils.logging import get_logger

logger = get_logger(__name__)


class ReviewStatus(Enum):
    """Translation review status."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    APPROVED = "approved"
    REJECTED = "rejected"
    NEEDS_REVISION = "needs_revision"


class ReviewerRole(Enum):
    """Reviewer roles with different permissions."""

    TRANSLATOR = "translator"
    REVIEWER = "reviewer"
    MEDICAL_EXPERT = "medical_expert"
    LEAD_REVIEWER = "lead_reviewer"
    ADMIN = "admin"


@dataclass
class ReviewComment:
    """Comment on a translation review."""

    comment_id: str
    reviewer_id: str
    reviewer_role: ReviewerRole
    translation_key: str
    comment: str
    timestamp: datetime = field(default_factory=datetime.now)
    is_resolved: bool = False
    resolved_by: Optional[str] = None
    resolved_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        data = asdict(self)
        data["timestamp"] = self.timestamp.isoformat()
        data["reviewer_role"] = self.reviewer_role.value
        if self.resolved_at:
            data["resolved_at"] = self.resolved_at.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ReviewComment":
        """Create from dictionary."""
        data["timestamp"] = datetime.fromisoformat(data["timestamp"])
        data["reviewer_role"] = ReviewerRole(data["reviewer_role"])
        if data.get("resolved_at"):
            data["resolved_at"] = datetime.fromisoformat(data["resolved_at"])
        return cls(**data)


@dataclass
class TranslationReview:
    """Review record for a translation version."""

    review_id: str
    version_id: str
    language: str
    namespace: str
    status: ReviewStatus
    assigned_reviewers: List[str]
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    submitted_by: Optional[str] = None
    approved_by: Optional[str] = None
    rejected_by: Optional[str] = None
    comments: List[ReviewComment] = field(default_factory=list)
    quality_score: Optional[float] = None
    medical_accuracy_verified: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "review_id": self.review_id,
            "version_id": self.version_id,
            "language": self.language,
            "namespace": self.namespace,
            "status": self.status.value,
            "assigned_reviewers": self.assigned_reviewers,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "submitted_by": self.submitted_by,
            "approved_by": self.approved_by,
            "rejected_by": self.rejected_by,
            "comments": [c.to_dict() for c in self.comments],
            "quality_score": self.quality_score,
            "medical_accuracy_verified": self.medical_accuracy_verified,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TranslationReview":
        """Create from dictionary."""
        data["status"] = ReviewStatus(data["status"])
        data["created_at"] = datetime.fromisoformat(data["created_at"])
        data["updated_at"] = datetime.fromisoformat(data["updated_at"])
        data["comments"] = [ReviewComment.from_dict(c) for c in data["comments"]]
        return cls(**data)


class TranslationReviewProcess:
    """Manages the translation review process."""

    def __init__(
        self,
        repository_path: str,
        version_control: Optional[TranslationVersionControl] = None,
    ):
        """Initialize review process."""
        self.repository_path = Path(repository_path)
        self.reviews_dir = self.repository_path / ".translation_reviews"
        self.reviews_dir.mkdir(parents=True, exist_ok=True)

        # Use provided version control or create new
        self.version_control = version_control or TranslationVersionControl(
            repository_path
        )

        # Review index
        self.index_file = self.reviews_dir / "review_index.json"
        self.index = self._load_index()

    def _load_index(self) -> Dict[str, Any]:
        """Load review index."""
        if self.index_file.exists():
            with open(self.index_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                return dict(data) if isinstance(data, dict) else {}
        return {"reviews": {}, "active_reviews": {}, "reviewers": {}}

    def _save_index(self) -> None:
        """Save review index."""
        with open(self.index_file, "w", encoding="utf-8") as f:
            json.dump(self.index, f, indent=2)

    def _generate_review_id(self) -> str:
        """Generate unique review ID."""
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        # MD5 is used here only for generating unique identifiers, not for security
        random_part = hashlib.md5(
            f"{timestamp}{len(self.index['reviews'])}".encode(), usedforsecurity=False
        ).hexdigest()[:6]
        return f"rev_{timestamp}_{random_part}"

    def _generate_comment_id(self) -> str:
        """Generate unique comment ID."""
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
        return f"cmt_{timestamp}"

    def _save_review(self, review: TranslationReview) -> None:
        """Save review to file."""
        review_file = self.reviews_dir / f"{review.review_id}.json"

        with open(review_file, "w", encoding="utf-8") as f:
            json.dump(review.to_dict(), f, indent=2)

    def _load_review(self, review_id: str) -> Optional[TranslationReview]:
        """Load review from file."""
        review_file = self.reviews_dir / f"{review_id}.json"

        if not review_file.exists():
            return None

        with open(review_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        return TranslationReview.from_dict(data)

    def submit_for_review(
        self,
        version_id: str,
        language: str,
        namespace: str,
        submitted_by: str,
        assigned_reviewers: List[str],
        require_medical_review: bool = False,
    ) -> TranslationReview:
        """Submit a translation version for review."""
        # Verify version exists
        version = self.version_control.get_version(version_id)
        if not version:
            raise ValueError(f"Version {version_id} not found")

        # Create review
        review = TranslationReview(
            review_id=self._generate_review_id(),
            version_id=version_id,
            language=language,
            namespace=namespace,
            status=ReviewStatus.PENDING,
            assigned_reviewers=assigned_reviewers,
            submitted_by=submitted_by,
        )

        # Add medical expert if required
        if require_medical_review:
            # Find medical expert reviewers
            medical_experts = [
                r
                for r in self.index["reviewers"]
                if self.index["reviewers"][r].get("role")
                == ReviewerRole.MEDICAL_EXPERT.value
            ]
            if medical_experts:
                review.assigned_reviewers.extend(
                    medical_experts[:1]
                )  # Add first available

        # Save review
        self._save_review(review)

        # Update index
        lang_ns_key = f"{language}_{namespace}"
        self.index["reviews"][review.review_id] = {
            "language": language,
            "namespace": namespace,
            "version_id": version_id,
            "status": review.status.value,
            "created_at": review.created_at.isoformat(),
        }
        self.index["active_reviews"][lang_ns_key] = review.review_id
        self._save_index()

        logger.info(f"Submitted version {version_id} for review as {review.review_id}")

        return review

    def add_comment(
        self,
        review_id: str,
        reviewer_id: str,
        reviewer_role: ReviewerRole,
        translation_key: str,
        comment: str,
    ) -> ReviewComment:
        """Add a comment to a review."""
        review = self._load_review(review_id)
        if not review:
            raise ValueError(f"Review {review_id} not found")

        # Create comment
        review_comment = ReviewComment(
            comment_id=self._generate_comment_id(),
            reviewer_id=reviewer_id,
            reviewer_role=reviewer_role,
            translation_key=translation_key,
            comment=comment,
        )

        # Add to review
        review.comments.append(review_comment)
        review.updated_at = datetime.now()

        # Update status if needed
        if review.status == ReviewStatus.PENDING:
            review.status = ReviewStatus.IN_PROGRESS

        # Save review
        self._save_review(review)

        # Update index
        self.index["reviews"][review_id]["status"] = review.status.value
        self._save_index()

        logger.info(f"Added comment to review {review_id}")

        return review_comment

    def resolve_comment(
        self, review_id: str, comment_id: str, resolved_by: str
    ) -> None:
        """Mark a comment as resolved."""
        review = self._load_review(review_id)
        if not review:
            raise ValueError(f"Review {review_id} not found")

        # Find and update comment
        for comment in review.comments:
            if comment.comment_id == comment_id:
                comment.is_resolved = True
                comment.resolved_by = resolved_by
                comment.resolved_at = datetime.now()
                break
        else:
            raise ValueError(f"Comment {comment_id} not found")

        review.updated_at = datetime.now()
        self._save_review(review)

    def approve_review(
        self,
        review_id: str,
        approved_by: str,
        quality_score: Optional[float] = None,
        medical_accuracy_verified: bool = False,
    ) -> TranslationVersion:
        """Approve a review and merge to main branch."""
        review = self._load_review(review_id)
        if not review:
            raise ValueError(f"Review {review_id} not found")

        # Check if reviewer is authorized
        if approved_by not in review.assigned_reviewers:
            # Check if admin
            reviewer_info = self.index["reviewers"].get(approved_by, {})
            if reviewer_info.get("role") != ReviewerRole.ADMIN.value:
                raise ValueError(f"Reviewer {approved_by} not authorized")

        # Update review
        review.status = ReviewStatus.APPROVED
        review.approved_by = approved_by
        review.quality_score = quality_score
        review.medical_accuracy_verified = medical_accuracy_verified
        review.updated_at = datetime.now()

        self._save_review(review)

        # Update index
        self.index["reviews"][review_id]["status"] = review.status.value

        # Remove from active reviews
        lang_ns_key = f"{review.language}_{review.namespace}"
        if self.index["active_reviews"].get(lang_ns_key) == review_id:
            del self.index["active_reviews"][lang_ns_key]

        self._save_index()

        logger.info(f"Approved review {review_id}")

        # Return the version that was reviewed
        version = self.version_control.get_version(review.version_id)
        if not version:
            raise ValueError(f"Version {review.version_id} not found")
        return version

    def reject_review(self, review_id: str, rejected_by: str, reason: str) -> None:
        """Reject a review."""
        review = self._load_review(review_id)
        if not review:
            raise ValueError(f"Review {review_id} not found")

        # Add rejection comment
        self.add_comment(
            review_id=review_id,
            reviewer_id=rejected_by,
            reviewer_role=ReviewerRole.REVIEWER,
            translation_key="__review__",
            comment=f"REJECTED: {reason}",
        )

        # Update review
        review = self._load_review(review_id)  # Reload to get updated comments
        if not review:
            raise ValueError(f"Review {review_id} not found")
        review.status = ReviewStatus.REJECTED
        review.rejected_by = rejected_by
        review.updated_at = datetime.now()

        self._save_review(review)

        # Update index
        self.index["reviews"][review_id]["status"] = review.status.value
        self._save_index()

        logger.info(f"Rejected review {review_id}")

    def request_revision(
        self, review_id: str, reviewer_id: str, revision_notes: str
    ) -> None:
        """Request revisions for a review."""
        review = self._load_review(review_id)
        if not review:
            raise ValueError(f"Review {review_id} not found")

        # Add revision comment
        self.add_comment(
            review_id=review_id,
            reviewer_id=reviewer_id,
            reviewer_role=ReviewerRole.REVIEWER,
            translation_key="__review__",
            comment=f"REVISION REQUESTED: {revision_notes}",
        )

        # Update review
        review = self._load_review(review_id)  # Reload
        if not review:
            raise ValueError(f"Review {review_id} not found")
        review.status = ReviewStatus.NEEDS_REVISION
        review.updated_at = datetime.now()

        self._save_review(review)

        # Update index
        self.index["reviews"][review_id]["status"] = review.status.value
        self._save_index()

        logger.info(f"Requested revision for review {review_id}")

    def get_review(self, review_id: str) -> Optional[TranslationReview]:
        """Get a specific review."""
        return self._load_review(review_id)

    def get_active_reviews(
        self, language: Optional[str] = None, reviewer_id: Optional[str] = None
    ) -> List[TranslationReview]:
        """Get active reviews, optionally filtered."""
        active_reviews = []

        for review_id, review_info in self.index["reviews"].items():
            if review_info["status"] in [
                ReviewStatus.PENDING.value,
                ReviewStatus.IN_PROGRESS.value,
                ReviewStatus.NEEDS_REVISION.value,
            ]:
                review = self._load_review(review_id)
                if not review:
                    continue

                # Apply filters
                if language and review.language != language:
                    continue

                if reviewer_id and reviewer_id not in review.assigned_reviewers:
                    continue

                active_reviews.append(review)

        return active_reviews

    def register_reviewer(
        self,
        reviewer_id: str,
        role: ReviewerRole,
        languages: List[str],
        specializations: Optional[List[str]] = None,
    ) -> None:
        """Register a reviewer in the system."""
        self.index["reviewers"][reviewer_id] = {
            "role": role.value,
            "languages": languages,
            "specializations": specializations or [],
            "registered_at": datetime.now().isoformat(),
        }
        self._save_index()

        logger.info(f"Registered reviewer {reviewer_id} with role {role.value}")

    def get_review_stats(self) -> Dict[str, Any]:
        """Get review statistics."""
        stats: Dict[str, Any] = {
            "total_reviews": len(self.index["reviews"]),
            "by_status": {},
            "by_language": {},
            "average_review_time": None,
            "approval_rate": 0,
        }

        # Count by status
        for review_info in self.index["reviews"].values():
            status = review_info["status"]
            stats["by_status"][status] = stats["by_status"].get(status, 0) + 1

            language = review_info["language"]
            stats["by_language"][language] = stats["by_language"].get(language, 0) + 1

        # Calculate approval rate
        approved = stats["by_status"].get(ReviewStatus.APPROVED.value, 0)
        rejected = stats["by_status"].get(ReviewStatus.REJECTED.value, 0)
        if approved + rejected > 0:
            stats["approval_rate"] = approved / (approved + rejected)

        return stats
