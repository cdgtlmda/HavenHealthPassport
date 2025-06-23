"""Notification service implementation."""

from datetime import datetime
from typing import Any, Dict, List

from src.notifications.base import (
    Notification,
    NotificationPriority,
    NotificationResult,
    NotificationStatus,
    NotificationType,
)
from src.notifications.channels import (
    ChannelType,
    EmailChannel,
    InAppChannel,
    PushChannel,
    SMSChannel,
)
from src.utils.logging import get_logger

logger = get_logger(__name__)


class NotificationService:
    """Main notification service implementation."""

    def __init__(self) -> None:
        """Initialize notification service with channels."""
        self.channels = {
            ChannelType.EMAIL: EmailChannel(),
            ChannelType.SMS: SMSChannel(),
            ChannelType.PUSH: PushChannel(),
            ChannelType.IN_APP: InAppChannel(),
        }

    async def send_notification(
        self,
        recipient: str,
        channel: str,
        message: Dict[str, Any],
        priority: str = "normal",
    ) -> NotificationResult:
        """Send notification through specified channel."""
        try:
            channel_type = ChannelType(channel)
            if channel_type not in self.channels:
                raise ValueError(f"Unsupported channel: {channel}")

            # Create notification object
            notification = Notification(
                id=str(datetime.utcnow().timestamp()),
                title=message.get("title", "Notification"),
                message=message.get("message", ""),
                notification_type=NotificationType(channel),
                priority=NotificationPriority(priority),
                recipient=recipient,
                metadata=message,
            )

            channel_impl = self.channels[channel_type]
            result = await channel_impl.send(notification)

            logger.info(
                "Notification sent successfully",
                extra={
                    "channel": channel,
                    "recipient": recipient,
                    "notification_id": result.notification_id,
                },
            )

            return result

        except (ValueError, RuntimeError, AttributeError) as e:
            logger.error(
                f"Failed to send notification: {str(e)}",
                extra={"channel": channel, "recipient": recipient, "error": str(e)},
            )
            return NotificationResult(
                notification_id=str(datetime.utcnow().timestamp()),
                channel=channel,
                status=NotificationStatus.FAILED,
                error_message=str(e),
            )

    async def send_bulk_notifications(
        self,
        recipients: List[str],
        channel: str,
        message: Dict[str, Any],
        priority: str = "normal",
    ) -> List[NotificationResult]:
        """Send notifications to multiple recipients."""
        results = []
        for recipient in recipients:
            result = await self.send_notification(recipient, channel, message, priority)
            results.append(result)
        return results
