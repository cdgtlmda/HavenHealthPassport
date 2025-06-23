"""Email tracking and analytics service."""

import os
import urllib.parse
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from src.models.email_tracking import EmailEvent as EmailEventModel
from src.models.email_tracking import (
    EmailMessage,
    EmailUnsubscribe,
)
from src.utils.logging import get_logger

logger = get_logger(__name__)


class EmailEventType(str, Enum):
    """Types of email events."""

    SENT = "sent"
    DELIVERED = "delivered"
    OPENED = "opened"
    CLICKED = "clicked"
    BOUNCED = "bounced"
    COMPLAINED = "complained"
    UNSUBSCRIBED = "unsubscribed"
    FAILED = "failed"


class EmailTracker:
    """Service for tracking email events and analytics."""

    def __init__(self, db: Session):
        """Initialize email tracker.

        Args:
            db: Database session
        """
        self.db = db

    async def track_email_sent(
        self,
        message_id: str,
        recipient: str,
        subject: str,
        template_id: Optional[str] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Track that an email was sent.

        Args:
            message_id: Provider's message ID
            recipient: Recipient email address
            subject: Email subject
            template_id: Template used (if any)
            tags: Tags/categories
            metadata: Additional metadata
        """
        email_record = EmailMessage(
            message_id=message_id,
            recipient=recipient,
            subject=subject,
            template_id=template_id,
            tags=tags or [],
            metadata=metadata or {},
            sent_at=datetime.utcnow(),
            status=EmailEventType.SENT,
        )

        self.db.add(email_record)

        try:
            self.db.commit()
        except (ValueError, AttributeError, RuntimeError) as e:
            logger.error(f"Failed to track email sent: {e}")
            self.db.rollback()

    async def track_event(
        self,
        message_id: str,
        event_type: EmailEventType,
        timestamp: Optional[datetime] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Track an email event.

        Args:
            message_id: Provider's message ID
            event_type: Type of event
            timestamp: When event occurred
            metadata: Event-specific data
        """
        # Find the email message
        email_message = (
            self.db.query(EmailMessage)
            .filter(EmailMessage.message_id == message_id)
            .first()
        )

        if not email_message:
            logger.warning(f"Email message not found for tracking: {message_id}")
            return

        # Create event record
        event = EmailEventModel(
            email_id=email_message.id,
            event_type=event_type,
            timestamp=timestamp or datetime.utcnow(),
            metadata=metadata or {},
        )

        self.db.add(event)

        # Update message status
        if event_type in [
            EmailEventType.DELIVERED,
            EmailEventType.BOUNCED,
            EmailEventType.FAILED,
        ]:
            email_message.status = event_type

            if event_type == EmailEventType.DELIVERED:
                email_message.delivered_at = event.timestamp

        try:
            self.db.commit()
        except (ValueError, AttributeError, RuntimeError) as e:
            logger.error(f"Failed to track email event: {e}")
            self.db.rollback()

    async def track_open(
        self, tracking_id: str, user_agent: Optional[str] = None
    ) -> None:
        """Track email open via tracking pixel.

        Args:
            tracking_id: Tracking ID from email
            user_agent: User agent string
        """
        # Decode tracking ID to get message ID
        # In production, this would decode an encrypted tracking ID
        message_id = tracking_id  # Simplified for now

        await self.track_event(
            message_id=message_id,
            event_type=EmailEventType.OPENED,
            metadata={"user_agent": user_agent, "method": "pixel"},
        )

    async def track_click(
        self, tracking_id: str, url: str, user_agent: Optional[str] = None
    ) -> None:
        """Track link click in email.

        Args:
            tracking_id: Tracking ID from link
            url: URL that was clicked
            user_agent: User agent string
        """
        # Decode tracking ID
        message_id = tracking_id  # Simplified

        await self.track_event(
            message_id=message_id,
            event_type=EmailEventType.CLICKED,
            metadata={"url": url, "user_agent": user_agent},
        )

    async def get_email_stats(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        template_id: Optional[str] = None,
        recipient: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get email statistics.

        Args:
            start_date: Start of date range
            end_date: End of date range
            template_id: Filter by template
            recipient: Filter by recipient

        Returns:
            Statistics dictionary
        """
        # Base query
        query = self.db.query(EmailMessage)

        # Apply filters
        if start_date:
            query = query.filter(EmailMessage.sent_at >= start_date)
        if end_date:
            query = query.filter(EmailMessage.sent_at <= end_date)
        if template_id:
            query = query.filter(EmailMessage.template_id == template_id)
        if recipient:
            query = query.filter(EmailMessage.recipient == recipient)

        # Get counts
        total_sent = query.count()

        # Get event counts
        event_counts = {}
        for event_type in EmailEventType:
            count = (
                self.db.query(EmailEventModel)
                .join(EmailMessage)
                .filter(EmailEventModel.event_type == event_type)
            )

            if start_date:
                count = count.filter(EmailEventModel.timestamp >= start_date)
            if end_date:
                count = count.filter(EmailEventModel.timestamp <= end_date)
            if template_id:
                count = count.filter(EmailMessage.template_id == template_id)
            if recipient:
                count = count.filter(EmailMessage.recipient == recipient)

            event_counts[event_type.value] = count.count()

        # Calculate rates
        open_rate = (
            (event_counts.get("opened", 0) / total_sent * 100) if total_sent > 0 else 0
        )
        click_rate = (
            (event_counts.get("clicked", 0) / total_sent * 100) if total_sent > 0 else 0
        )
        bounce_rate = (
            (event_counts.get("bounced", 0) / total_sent * 100) if total_sent > 0 else 0
        )

        return {
            "total_sent": total_sent,
            "delivered": event_counts.get("delivered", 0),
            "opened": event_counts.get("opened", 0),
            "clicked": event_counts.get("clicked", 0),
            "bounced": event_counts.get("bounced", 0),
            "complained": event_counts.get("complained", 0),
            "failed": event_counts.get("failed", 0),
            "open_rate": round(open_rate, 2),
            "click_rate": round(click_rate, 2),
            "bounce_rate": round(bounce_rate, 2),
            "period": {
                "start": start_date.isoformat() if start_date else None,
                "end": end_date.isoformat() if end_date else None,
            },
        }

    async def get_template_performance(
        self, template_id: str, days: int = 30
    ) -> Dict[str, Any]:
        """Get performance metrics for a specific template.

        Args:
            template_id: Template to analyze
            days: Number of days to look back

        Returns:
            Performance metrics
        """
        start_date = datetime.utcnow() - timedelta(days=days)

        stats = await self.get_email_stats(
            start_date=start_date, template_id=template_id
        )

        # Add template-specific metrics
        # Get average time to open
        opened_emails = (
            self.db.query(EmailMessage)
            .filter(
                EmailMessage.template_id == template_id,
                EmailMessage.sent_at >= start_date,
                EmailMessage.delivered_at.isnot(None),
            )
            .all()
        )

        time_to_open_list = []
        for email in opened_emails:
            first_open = (
                self.db.query(EmailEventModel)
                .filter(
                    EmailEventModel.email_id == email.id,
                    EmailEventModel.event_type == EmailEventType.OPENED,
                )
                .order_by(EmailEventModel.timestamp)
                .first()
            )

            if first_open:
                time_to_open = (
                    first_open.timestamp - email.sent_at
                ).total_seconds() / 3600  # hours
                time_to_open_list.append(time_to_open)

        avg_time_to_open = (
            sum(time_to_open_list) / len(time_to_open_list) if time_to_open_list else 0
        )

        stats.update(
            {
                "template_id": template_id,
                "avg_time_to_open_hours": round(avg_time_to_open, 2),
                "unique_opens": len(time_to_open_list),
            }
        )

        return stats

    async def handle_unsubscribe(
        self, email: str, reason: Optional[str] = None
    ) -> None:
        """Handle email unsubscribe.

        Args:
            email: Email address unsubscribing
            reason: Optional reason for unsubscribe
        """
        unsub = EmailUnsubscribe(
            email=email, unsubscribed_at=datetime.utcnow(), reason=reason
        )

        self.db.add(unsub)

        try:
            self.db.commit()
            logger.info(f"Recorded unsubscribe for {email}")
        except SQLAlchemyError as e:
            logger.error(f"Failed to record unsubscribe: {e}")
            self.db.rollback()

    async def is_unsubscribed(self, email: str) -> bool:
        """Check if email is unsubscribed.

        Args:
            email: Email to check

        Returns:
            True if unsubscribed
        """
        return (
            self.db.query(EmailUnsubscribe)
            .filter(
                EmailUnsubscribe.email == email,
                EmailUnsubscribe.resubscribed_at.is_(None),
            )
            .first()
            is not None
        )

    def generate_tracking_pixel_url(self, message_id: str) -> str:
        """Generate tracking pixel URL for email open tracking.

        Args:
            message_id: Message to track

        Returns:
            Tracking pixel URL
        """
        # In production, encrypt the message_id
        tracking_id = message_id  # Simplified

        base_url = os.getenv("API_URL", "https://api.havenhealthpassport.org")
        return f"{base_url}/email/track/open/{tracking_id}.gif"

    def generate_click_tracking_url(self, message_id: str, original_url: str) -> str:
        """Generate click tracking URL.

        Args:
            message_id: Message to track
            original_url: Original URL

        Returns:
            Tracking URL that redirects to original
        """
        tracking_id = message_id  # Simplified
        base_url = os.getenv("API_URL", "https://api.havenhealthpassport.org")

        encoded_url = urllib.parse.quote(original_url, safe="")
        return f"{base_url}/email/track/click/{tracking_id}?url={encoded_url}"
