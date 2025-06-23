"""FileCleanupTask model for sync service.

This model tracks files that need to be cleaned up after sync operations,
particularly after rollbacks or failed uploads.
"""

import enum

from sqlalchemy import Column, DateTime
from sqlalchemy import Enum as SQLAlchemyEnum
from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import BaseModel


class CleanupStatus(enum.Enum):
    """Status of file cleanup task."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class CleanupReason(enum.Enum):
    """Reason for file cleanup."""

    SYNC_ROLLBACK = "sync_rollback"
    UPLOAD_FAILED = "upload_failed"
    EXPIRED = "expired"
    USER_DELETED = "user_deleted"
    DUPLICATE = "duplicate"
    CORRUPTED = "corrupted"


class FileCleanupTask(BaseModel):
    """Model for tracking files that need cleanup.

    This is critical for maintaining storage hygiene in resource-constrained
    environments where storage space is limited (refugee camp devices).
    """

    __tablename__ = "file_cleanup_tasks"

    # File information
    file_path = Column(String, nullable=False)
    file_size = Column(Integer, nullable=True)  # Size in bytes
    file_type = Column(String, nullable=True)

    # Task scheduling
    scheduled_for = Column(DateTime, nullable=False)

    # Task metadata
    reason: Mapped[CleanupReason] = mapped_column(
        SQLAlchemyEnum(CleanupReason), nullable=False
    )
    status: Mapped[CleanupStatus] = mapped_column(
        SQLAlchemyEnum(CleanupStatus), default=CleanupStatus.PENDING, nullable=False
    )

    # Execution tracking
    attempted_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    attempt_count = Column(Integer, default=0)
    max_attempts = Column(Integer, default=3)

    # Error tracking
    last_error = Column(String, nullable=True)

    # Related entity information (for audit trail)
    entity_type = Column(
        String, nullable=True
    )  # e.g., "health_record", "patient_photo"
    entity_id = Column(String, nullable=True)

    def __repr__(self) -> str:
        """Return string representation of FileCleanupTask."""
        return f"<FileCleanupTask(id={self.id}, file_path={self.file_path}, status={self.status})>"

    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "id": str(self.id),
            "file_path": self.file_path,
            "file_size": self.file_size,
            "file_type": self.file_type,
            "scheduled_for": (
                self.scheduled_for.isoformat() if self.scheduled_for else None
            ),
            "reason": self.reason.value if self.reason else None,
            "status": self.status.value if self.status else None,
            "attempted_at": (
                self.attempted_at.isoformat() if self.attempted_at else None
            ),
            "completed_at": (
                self.completed_at.isoformat() if self.completed_at else None
            ),
            "attempt_count": self.attempt_count,
            "last_error": self.last_error,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
