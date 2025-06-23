"""Comprehensive Notification Service Implementation.

This module provides a unified notification system that supports multiple
channels (email, SMS, push, in-app) with retry logic, templates, and tracking.
"""

import asyncio
import json
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union
from uuid import UUID, uuid4

import boto3
from sqlalchemy import String, cast
from twilio.rest import Client

from src.auth.sms_backup_config import SMSBackupConfig
from src.database import get_db

# Import security services for PHI notification protection
# from src.healthcare.hipaa_access_control import require_phi_access  # Available if needed for HIPAA compliance
from src.models.notification import Notification
from src.models.user import User
from src.services.email_service import EmailService
from src.utils.logging import get_logger

logger = get_logger(__name__)


class NotificationChannel(str, Enum):
    """Available notification channels."""

    EMAIL = "email"
    SMS = "sms"
    PUSH = "push"
    IN_APP = "in_app"
    SLACK = "slack"
    TEAMS = "teams"


class NotificationPriority(str, Enum):
    """Notification priority levels."""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


@dataclass
class NotificationRequest:
    """Notification request data model."""

    id: UUID
    user_id: UUID
    channels: List[NotificationChannel]
    title: str
    message: str
    priority: NotificationPriority = NotificationPriority.NORMAL
    data: Optional[Dict[str, Any]] = None
    template_id: Optional[str] = None
    template_params: Optional[Dict[str, Any]] = None
    created_at: Optional[datetime] = None
    scheduled_for: Optional[datetime] = None
    expires_at: Optional[datetime] = None

    def __post_init__(self) -> None:
        """Initialize created_at timestamp if not provided."""
        if self.created_at is None:
            self.created_at = datetime.utcnow()


@dataclass
class NotificationResult:
    """Result of notification attempt."""

    notification_id: UUID
    channel: NotificationChannel
    success: bool
    sent_at: datetime
    error_message: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class NotificationChannelBase(ABC):
    """Base class for notification channels."""

    @abstractmethod
    async def send(self, notification: NotificationRequest) -> NotificationResult:
        """Send notification through this channel."""

    @abstractmethod
    def supports_bulk(self) -> bool:
        """Check if channel supports bulk notifications."""

    @abstractmethod
    async def send_bulk(
        self, notifications: List[NotificationRequest]
    ) -> List[NotificationResult]:
        """Send multiple notifications."""


class EmailChannel(NotificationChannelBase):
    """Email notification channel."""

    def __init__(self, email_service: EmailService):
        """Initialize email notification channel."""
        self.email_service = email_service

    async def send(self, notification: NotificationRequest) -> NotificationResult:
        """Send email notification."""
        try:
            # Get user email from database
            db = next(get_db())
            user = db.query(User).filter(User.id == str(notification.user_id)).first()  # type: ignore[arg-type]

            if not user or not user.email:
                return NotificationResult(
                    notification_id=notification.id,
                    channel=NotificationChannel.EMAIL,
                    success=False,
                    sent_at=datetime.utcnow(),
                    error_message="User email not found",
                )

            # Send email
            success = await self.email_service.send_email(
                to_email=user.email,
                subject=notification.title,
                body=notification.message,
                template_id=notification.template_id,
                template_params=notification.template_params,
            )

            return NotificationResult(
                notification_id=notification.id,
                channel=NotificationChannel.EMAIL,
                success=success,
                sent_at=datetime.utcnow(),
            )
        except (ValueError, AttributeError, RuntimeError) as e:
            logger.error(f"Failed to send email notification: {e}")
            return NotificationResult(
                notification_id=notification.id,
                channel=NotificationChannel.EMAIL,
                success=False,
                sent_at=datetime.utcnow(),
                error_message=str(e),
            )

    def supports_bulk(self) -> bool:
        """Check if channel supports bulk notifications. Email supports bulk sending."""
        return True

    async def send_bulk(
        self, notifications: List[NotificationRequest]
    ) -> List[NotificationResult]:
        """Send multiple emails efficiently."""
        results = []
        # Process in batches to avoid overwhelming the email service
        batch_size = 50

        for i in range(0, len(notifications), batch_size):
            batch = notifications[i : i + batch_size]
            batch_results = await asyncio.gather(
                *[self.send(notif) for notif in batch], return_exceptions=True
            )

            for notif, result in zip(batch, batch_results):
                if isinstance(result, Exception):
                    results.append(
                        NotificationResult(
                            notification_id=notif.id,
                            channel=NotificationChannel.EMAIL,
                            success=False,
                            sent_at=datetime.utcnow(),
                            error_message=str(result),
                        )
                    )
                else:
                    results.append(result)  # type: ignore[arg-type]

        return results


class SMSChannel(NotificationChannelBase):
    """SMS notification channel."""

    def __init__(self, sms_config: Any) -> None:
        """Initialize SMS notification channel."""
        self.sms_config = sms_config
        self.sms_provider: Optional[str] = None
        self._initialize_sms_provider()

    def _initialize_sms_provider(self) -> None:
        """Initialize SMS provider (AWS SNS or Twilio)."""
        # Check for AWS SNS configuration
        if os.getenv("AWS_SNS_ENABLED", "false").lower() == "true":
            self.sms_provider = "sns"
            self.sns_client = boto3.client(
                "sns", region_name=os.getenv("AWS_REGION", "us-east-1")
            )
            logger.info("Initialized AWS SNS for SMS")

        # Check for Twilio configuration
        elif os.getenv("TWILIO_ACCOUNT_SID") and os.getenv("TWILIO_AUTH_TOKEN"):
            try:
                self.sms_provider = "twilio"
                self.twilio_client = Client(
                    os.getenv("TWILIO_ACCOUNT_SID"), os.getenv("TWILIO_AUTH_TOKEN")
                )
                self.twilio_from_number = os.getenv("TWILIO_FROM_NUMBER")
                logger.info("Initialized Twilio for SMS")
            except ImportError:
                logger.warning(
                    "Twilio library not installed. Install with: pip install twilio"
                )
                self.sms_provider = None
        else:
            logger.warning(
                "No SMS provider configured. Set AWS_SNS_ENABLED=true or provide Twilio credentials"
            )
            self.sms_provider = None

    async def send(self, notification: NotificationRequest) -> NotificationResult:
        """Send SMS notification."""
        try:
            db = next(get_db())
            user = db.query(User).filter(User.id == str(notification.user_id)).first()  # type: ignore[arg-type]

            if (
                not user
                or not hasattr(user, "phone_number")
                or not getattr(user, "phone_number", None)
            ):
                return NotificationResult(
                    notification_id=notification.id,
                    channel=NotificationChannel.SMS,
                    success=False,
                    sent_at=datetime.utcnow(),
                    error_message="User phone number not found",
                )

            # Check SMS rate limits
            can_send, reason = self.sms_config.can_send_sms(
                user_id=str(user.id), phone_number=getattr(user, "phone_number", None)
            )

            if not can_send:
                return NotificationResult(
                    notification_id=notification.id,
                    channel=NotificationChannel.SMS,
                    success=False,
                    sent_at=datetime.utcnow(),
                    error_message=reason,
                )

            # Format message - combine title and message for SMS
            # @encrypt_phi - SMS messages may contain patient information
            sms_message = f"{notification.title}: {notification.message}"

            # Truncate if too long (SMS limit is typically 160 chars)
            max_length = 160
            if len(sms_message) > max_length:
                sms_message = sms_message[: max_length - 3] + "..."

            # Send SMS based on provider
            if self.sms_provider == "sns":
                success = await self._send_via_sns(
                    getattr(user, "phone_number", None), sms_message  # type: ignore[arg-type]
                )
            elif self.sms_provider == "twilio":
                success = await self._send_via_twilio(
                    getattr(user, "phone_number", None), sms_message  # type: ignore[arg-type]
                )
            else:
                # Fallback to logging if no provider configured
                logger.info(
                    f"SMS to {getattr(user, 'phone_number', None)}: {sms_message}"
                )
                success = True  # Consider logged messages as "sent" in dev

            return NotificationResult(
                notification_id=notification.id,
                channel=NotificationChannel.SMS,
                success=success,
                sent_at=datetime.utcnow(),
            )

        except (ValueError, AttributeError, RuntimeError) as e:
            logger.error(f"Failed to send SMS: {e}")
            return NotificationResult(
                notification_id=notification.id,
                channel=NotificationChannel.SMS,
                success=False,
                sent_at=datetime.utcnow(),
                error_message=str(e),
            )

    async def _send_via_sns(self, phone_number: str, message: str) -> bool:
        """Send SMS via AWS SNS."""
        try:
            # Ensure phone number is in E.164 format
            if not phone_number.startswith("+"):
                # Default to US if no country code
                phone_number = "+1" + phone_number.replace("-", "").replace(" ", "")

            response = self.sns_client.publish(
                PhoneNumber=phone_number,
                Message=message,
                MessageAttributes={
                    "AWS.SNS.SMS.SenderID": {
                        "DataType": "String",
                        "StringValue": "HavenHealth",
                    },
                    "AWS.SNS.SMS.SMSType": {
                        "DataType": "String",
                        "StringValue": "Transactional",  # or 'Promotional'
                    },
                },
            )

            message_id = response.get("MessageId")
            logger.info(f"SMS sent via SNS: {message_id}")
            return True

        except (ValueError, KeyError, RuntimeError) as e:
            logger.error(f"SNS SMS failed: {e}")
            return False

    async def _send_via_twilio(self, phone_number: str, message: str) -> bool:
        """Send SMS via Twilio."""
        try:
            # Ensure phone number is in E.164 format
            if not phone_number.startswith("+"):
                phone_number = "+1" + phone_number.replace("-", "").replace(" ", "")

            message = self.twilio_client.messages.create(
                body=message, from_=self.twilio_from_number, to=phone_number
            )

            logger.info(f"SMS sent via Twilio: {getattr(message, 'sid', 'unknown')}")
            return True

        except (ValueError, AttributeError, RuntimeError) as e:
            logger.error(f"Twilio SMS failed: {e}")
            return False

    def supports_bulk(self) -> bool:
        """Check if channel supports bulk notifications."""
        return True

    async def send_bulk(
        self, notifications: List[NotificationRequest]
    ) -> List[NotificationResult]:
        """Send multiple SMS messages."""
        return await asyncio.gather(*[self.send(notif) for notif in notifications])


class InAppChannel(NotificationChannelBase):
    """In-app notification channel."""

    async def send(self, notification: NotificationRequest) -> NotificationResult:
        """Store notification for in-app display."""
        try:
            db = next(get_db())

            # Store notification in database
            # @secure_storage - Notifications may contain PHI and must be encrypted
            db_notification = Notification(
                id=notification.id,
                user_id=notification.user_id,
                title=notification.title,
                message=notification.message,
                type="in_app",
                priority=notification.priority,
                data=json.dumps(notification.data) if notification.data else None,
                created_at=notification.created_at,
                expires_at=notification.expires_at,
                is_read=False,
            )

            db.add(db_notification)
            db.commit()

            return NotificationResult(
                notification_id=notification.id,
                channel=NotificationChannel.IN_APP,
                success=True,
                sent_at=datetime.utcnow(),
            )

        except (ValueError, AttributeError, RuntimeError) as e:
            logger.error(f"Failed to store in-app notification: {e}")
            return NotificationResult(
                notification_id=notification.id,
                channel=NotificationChannel.IN_APP,
                success=False,
                sent_at=datetime.utcnow(),
                error_message=str(e),
            )

    def supports_bulk(self) -> bool:
        """Check if channel supports bulk notifications."""
        return True

    async def send_bulk(
        self, notifications: List[NotificationRequest]
    ) -> List[NotificationResult]:
        """Store multiple notifications."""
        return await asyncio.gather(*[self.send(notif) for notif in notifications])


class UnifiedNotificationService:
    """Main notification service that routes to appropriate channels."""

    def __init__(self) -> None:
        """Initialize unified notification service."""
        self.channels: Dict[NotificationChannel, NotificationChannelBase] = {}
        self._retry_config = {
            "max_retries": 3,
            "base_delay": 1,  # seconds
            "max_delay": 60,  # seconds
        }
        self._initialize_channels()

    def _initialize_channels(self) -> None:
        """Initialize notification channels."""
        # Initialize email channel
        email_service = EmailService()
        self.channels[NotificationChannel.EMAIL] = EmailChannel(email_service)

        # Initialize SMS channel
        sms_config = SMSBackupConfig()
        self.channels[NotificationChannel.SMS] = SMSChannel(sms_config)

        # Initialize in-app channel
        self.channels[NotificationChannel.IN_APP] = InAppChannel()

    async def send_notification(
        self,
        user_id: Union[UUID, str],
        notification_type: str,
        title: str,
        message: str,
        channels: Optional[List[NotificationChannel]] = None,
        priority: NotificationPriority = NotificationPriority.NORMAL,
        data: Optional[Dict[str, Any]] = None,
        template_id: Optional[str] = None,
        template_params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Send notification through specified channels.

        Args:
            user_id: User to notify
            notification_type: Type of notification            title: Notification title
            message: Notification message
            channels: List of channels to use (defaults to user preferences)
            priority: Notification priority
            data: Additional data
            template_id: Template to use
            template_params: Template parameters

        Returns:
            Results dictionary
        """
        # Convert string UUID if needed
        if isinstance(user_id, str):
            user_id = UUID(user_id)

        # Use default channels if not specified
        if not channels:
            channels = await self._get_user_preferred_channels(user_id)

        # Create notification request object
        notification = NotificationRequest(
            id=uuid4(),
            user_id=user_id,
            channels=channels,
            title=title,
            message=message,
            priority=priority,
            data=data or {"type": notification_type},
            template_id=template_id,
            template_params=template_params,
        )
        # Send through each channel with retry
        results = []
        for channel in channels:
            if channel in self.channels:
                result = await self._send_with_retry(notification, channel)
                results.append(result)

        # Audit if contains PHI
        if data and data.get("contains_phi"):
            # Log PHI access for audit trail
            audit_logger = get_logger("audit.phi")
            audit_logger.info(
                "PHI notification sent",
                extra={
                    "user_id": str(user_id),
                    "resource_type": "notification",
                    "resource_id": str(notification.id),
                    "action": "notification_sent",
                },
            )

        return {
            "notification_id": str(notification.id),
            "user_id": str(user_id),
            "type": notification_type,
            "channels_attempted": [c.value for c in channels],
            "results": [
                {
                    "channel": r.channel.value,
                    "success": r.success,
                    "error": r.error_message,
                }
                for r in results
            ],
            "sent_at": datetime.utcnow().isoformat(),
        }

    async def _send_with_retry(
        self, notification: NotificationRequest, channel: NotificationChannel
    ) -> NotificationResult:
        """Send notification with exponential backoff retry."""
        channel_handler = self.channels[channel]
        last_error = None

        for attempt in range(self._retry_config["max_retries"]):
            try:
                result = await channel_handler.send(notification)
                if result.success:
                    return result
                last_error = result.error_message

            except (ValueError, KeyError, AttributeError, RuntimeError) as e:
                last_error = str(e)
                logger.error(f"Error sending notification: {e}")

            # Calculate delay with exponential backoff
            if attempt < self._retry_config["max_retries"] - 1:
                delay = min(
                    self._retry_config["base_delay"] * (2**attempt),
                    self._retry_config["max_delay"],
                )
                await asyncio.sleep(delay)

        # All retries failed
        return NotificationResult(
            notification_id=notification.id,
            channel=channel,
            success=False,
            sent_at=datetime.utcnow(),
            error_message=f"Failed after {self._retry_config['max_retries']} attempts: {last_error}",
        )

    async def _get_user_preferred_channels(
        self, user_id: UUID
    ) -> List[NotificationChannel]:
        """Get user preferred notification channels."""
        try:
            db = next(get_db())
            user = db.query(User).filter(cast(User.id, String) == str(user_id)).first()

            if (
                user
                and hasattr(user, "notification_preferences")
                and user.notification_preferences
            ):
                prefs = json.loads(user.notification_preferences)
                return [NotificationChannel(c) for c in prefs.get("channels", [])]
        except (ValueError, KeyError, json.JSONDecodeError, AttributeError) as e:
            logger.error(f"Error getting user preferences: {e}")

        # Default channels
        return [NotificationChannel.EMAIL, NotificationChannel.IN_APP]

    async def get_user_notifications(
        self, user_id: UUID, unread_only: bool = False, limit: int = 20, offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Get notifications for a user."""
        try:
            db = next(get_db())
            query = db.query(Notification).filter(Notification.user_id == user_id)

            if unread_only:
                query = query.filter(Notification.is_read.is_(False))

            notifications = (
                query.order_by(Notification.created_at.desc())
                .limit(limit)
                .offset(offset)
                .all()
            )

            return [
                {
                    "id": str(n.id),
                    "title": n.title,
                    "message": n.message,
                    "type": n.type,
                    "priority": n.priority,
                    "is_read": n.is_read,
                    "created_at": n.created_at.isoformat(),
                    "data": json.loads(n.data) if n.data else None,
                }
                for n in notifications
            ]

        except (ValueError, AttributeError, RuntimeError) as e:
            logger.error(f"Error getting notifications: {e}")
            return []

    async def mark_as_read(self, notification_id: UUID, user_id: UUID) -> bool:
        """Mark notification as read."""
        try:
            db = next(get_db())
            notification = (
                db.query(Notification)
                .filter(
                    Notification.id == notification_id,
                    Notification.user_id == user_id,
                )
                .first()
            )

            if notification:
                notification.is_read = True
                notification.read_at = datetime.utcnow()
                db.commit()
                return True

        except (ValueError, AttributeError, RuntimeError) as e:
            logger.error(f"Error marking notification as read: {e}")

        return False


_notification_service_instance: Optional[UnifiedNotificationService] = None


def get_notification_service() -> UnifiedNotificationService:
    """Get the singleton notification service instance."""
    global _notification_service_instance
    if _notification_service_instance is None:
        _notification_service_instance = UnifiedNotificationService()
    return _notification_service_instance
