"""CallbackTask model for managing async webhook callbacks.

This model tracks webhook callbacks that need to be executed asynchronously,
particularly for critical medical translation completions.
"""

import enum
from datetime import datetime, timedelta
from typing import Any, Dict

from sqlalchemy import JSON, Column, DateTime
from sqlalchemy import Enum as SQLAlchemyEnum
from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import BaseModel


class CallbackTaskStatus(enum.Enum):
    """Status of callback task."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    EXPIRED = "expired"


class CallbackTaskPriority(enum.Enum):
    """Priority of callback task."""

    CRITICAL = "critical"  # Medical emergency callbacks
    HIGH = "high"  # Medical translation callbacks
    NORMAL = "normal"  # Standard callbacks
    LOW = "low"  # Non-urgent callbacks


class CallbackTask(BaseModel):
    """Model for tracking async callback tasks.

    This is critical for ensuring medical translation callbacks are delivered
    reliably even in poor network conditions (refugee camp scenarios).
    """

    __tablename__ = "callback_tasks"

    # Entity reference
    entity_type = Column(
        String, nullable=False
    )  # e.g., "translation_queue", "verification"
    entity_id = Column(String, nullable=False)

    # Callback details
    callback_url = Column(String, nullable=False)
    http_method = Column(String, default="POST", nullable=False)

    # Payload
    payload = Column(JSON, nullable=False)
    headers = Column(JSON, nullable=True)

    # Task scheduling
    scheduled_for = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=True)

    # Task metadata
    priority: Mapped[CallbackTaskPriority] = mapped_column(
        SQLAlchemyEnum(CallbackTaskPriority),
        default=CallbackTaskPriority.NORMAL,
        nullable=False,
    )
    status: Mapped[CallbackTaskStatus] = mapped_column(
        SQLAlchemyEnum(CallbackTaskStatus),
        default=CallbackTaskStatus.PENDING,
        nullable=False,
    )

    # Retry configuration
    max_retries = Column(Integer, default=3)
    retry_count = Column(Integer, default=0)
    retry_delay_seconds = Column(Integer, default=60)  # Exponential backoff applied

    # Execution tracking
    last_attempted_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    # Response tracking
    last_response_status = Column(Integer, nullable=True)
    last_response_body = Column(String, nullable=True)
    last_error = Column(String, nullable=True)

    def __repr__(self) -> str:
        """Return string representation of CallbackTask."""
        return f"<CallbackTask(id={self.id}, entity={self.entity_type}:{self.entity_id}, status={self.status})>"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            "id": str(self.id),
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "callback_url": self.callback_url,
            "http_method": self.http_method,
            "payload": self.payload,
            "headers": self.headers,
            "scheduled_for": (
                self.scheduled_for.isoformat() if self.scheduled_for else None
            ),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "priority": self.priority.value if self.priority else None,
            "status": self.status.value if self.status else None,
            "max_retries": self.max_retries,
            "retry_count": self.retry_count,
            "last_attempted_at": (
                self.last_attempted_at.isoformat() if self.last_attempted_at else None
            ),
            "completed_at": (
                self.completed_at.isoformat() if self.completed_at else None
            ),
            "last_response_status": self.last_response_status,
            "last_error": self.last_error,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def should_retry(self) -> bool:
        """Check if task should be retried."""
        if self.status != CallbackTaskStatus.FAILED:
            return False

        if self.retry_count >= self.max_retries:
            return False

        if self.expires_at and datetime.utcnow() > self.expires_at:
            return False

        return True

    def calculate_next_retry_time(self) -> datetime:
        """Calculate next retry time with exponential backoff."""
        # Exponential backoff: delay * 2^(retry_count)
        delay_seconds = self.retry_delay_seconds * (2 ** int(self.retry_count))

        # Cap at 1 hour
        delay_seconds = min(delay_seconds, 3600)

        return datetime.utcnow() + timedelta(seconds=delay_seconds)
