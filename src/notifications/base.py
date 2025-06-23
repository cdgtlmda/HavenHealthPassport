"""Base classes and interfaces for the notification system."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional


class NotificationPriority(Enum):
    """Notification priority levels."""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class NotificationType(Enum):
    """Notification type categories."""

    EMAIL = "email"
    SMS = "sms"
    PUSH = "push"
    IN_APP = "in_app"


class NotificationStatus(Enum):
    """Notification delivery status."""

    PENDING = "pending"
    QUEUED = "queued"
    SENDING = "sending"
    SENT = "sent"
    DELIVERED = "delivered"
    FAILED = "failed"
    BOUNCED = "bounced"


@dataclass
class NotificationRecipient:
    """Recipient information for notifications."""

    id: str
    email: Optional[str] = None
    phone: Optional[str] = None
    device_token: Optional[str] = None
    user_id: Optional[str] = None
    language_preference: str = "en"
    timezone: str = "UTC"


@dataclass
class Notification:
    """Base notification class."""

    id: str
    title: str
    message: str
    notification_type: NotificationType
    priority: NotificationPriority = NotificationPriority.NORMAL
    recipient: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    created_at: Optional[datetime] = None

    def __post_init__(self) -> None:
        """Initialize default values."""
        if self.created_at is None:
            self.created_at = datetime.utcnow()


@dataclass
class NotificationResult:
    """Result of a notification send attempt."""

    notification_id: str
    channel: str
    status: NotificationStatus
    delivered_at: Optional[datetime] = None
    error_message: Optional[str] = None
    provider_response: Optional[Dict[str, Any]] = None
    retry_count: int = 0
    next_retry_at: Optional[datetime] = None


class NotificationChannel(ABC):
    """Abstract base class for notification channels."""

    def __init__(self, config: Dict[str, Any]):
        """Initialize the notification channel with configuration."""
        self.config = config
        self.name = self.__class__.__name__

    @abstractmethod
    async def send(self, notification: Notification) -> NotificationResult:
        """
        Send a notification through this channel.

        Args:
            notification: The notification to send

        Returns:
            NotificationResult with delivery status
        """
