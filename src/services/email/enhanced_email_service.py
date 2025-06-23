"""Enhanced email service with provider abstraction, rate limiting, and tracking."""

import json
import os
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from src.database import get_db
from src.services.email.email_tracker import EmailEventType, EmailTracker
from src.services.email.providers import (
    AWSSESProvider,
    EmailAddress,
    EmailAttachment,
    EmailMessage,
    EmailProvider,
    EmailResult,
    EmailStatus,
    SendGridProvider,
)
from src.services.email.rate_limiter import EmailRateLimiter
from src.services.email.template_manager import EmailTemplateManager
from src.utils.logging import get_logger

logger = get_logger(__name__)


class EnhancedEmailService:
    """Enhanced email service with full feature support."""

    def __init__(self) -> None:
        """Initialize enhanced email service."""
        # Initialize provider based on configuration
        self.provider = self._initialize_provider()

        # Initialize components
        self.rate_limiter = EmailRateLimiter(
            per_minute=int(os.getenv("EMAIL_RATE_PER_MINUTE", "10")),
            per_hour=int(os.getenv("EMAIL_RATE_PER_HOUR", "100")),
            per_day=int(os.getenv("EMAIL_RATE_PER_DAY", "1000")),
        )

        self.template_manager = EmailTemplateManager()

        # Email tracker will be initialized per request with DB session
        self._default_from = EmailAddress(
            email=os.getenv("FROM_EMAIL", "noreply@havenhealthpassport.org"),
            name=os.getenv("FROM_NAME", "Haven Health Passport"),
        )

    def _initialize_provider(self) -> EmailProvider:
        """Initialize the email provider based on configuration."""
        provider_name = os.getenv("EMAIL_PROVIDER", "ses").lower()

        if provider_name == "ses":
            return AWSSESProvider()
        elif provider_name == "sendgrid":
            api_key = os.getenv("SENDGRID_API_KEY")
            if not api_key:
                raise ValueError("SendGrid API key not configured")
            return SendGridProvider(api_key)
        else:
            raise ValueError(f"Unknown email provider: {provider_name}")

    async def send_email(
        self,
        to: Union[str, List[str], EmailAddress, List[EmailAddress]],
        subject: str,
        html_body: Optional[str] = None,
        text_body: Optional[str] = None,
        template_id: Optional[str] = None,
        template_params: Optional[Dict[str, Any]] = None,
        from_address: Optional[EmailAddress] = None,
        reply_to: Optional[EmailAddress] = None,
        attachments: Optional[List[EmailAttachment]] = None,
        tags: Optional[List[str]] = None,
        track_opens: bool = True,
        track_clicks: bool = True,
        user_id: Optional[str] = None,
        language: Optional[str] = None,
    ) -> EmailResult:
        """Send an email with full feature support.

        Args:
            to: Recipient(s)
            subject: Email subject
            html_body: HTML content (optional if using template)
            text_body: Plain text content (optional)
            template_id: Template to use
            template_params: Template parameters
            from_address: From address (defaults to system default)
            reply_to: Reply-to address
            attachments: List of attachments
            tags: Tags for categorization/tracking
            track_opens: Whether to track opens
            track_clicks: Whether to track clicks
            user_id: User ID for preferences
            language: Language override

        Returns:
            EmailResult with send status
        """
        # Normalize recipients
        recipients = self._normalize_recipients(to)

        # Check rate limits for first recipient
        if recipients:
            can_send = await self.rate_limiter.wait_if_needed(recipients[0].email)
            if not can_send:
                return EmailResult(
                    message_id="",
                    status=EmailStatus.FAILED,
                    timestamp=datetime.utcnow(),
                    provider=self.provider.get_provider_name(),
                    error_message="Rate limit exceeded",
                )

        # Check unsubscribe status
        db = next(get_db())
        tracker = EmailTracker(db)

        unsubscribed_recipients = []
        for recipient in recipients:
            if await tracker.is_unsubscribed(recipient.email):
                unsubscribed_recipients.append(recipient.email)

        if unsubscribed_recipients:
            logger.warning(
                f"Skipping unsubscribed recipients: {unsubscribed_recipients}"
            )
            recipients = [
                r for r in recipients if r.email not in unsubscribed_recipients
            ]

            if not recipients:
                return EmailResult(
                    message_id="",
                    status=EmailStatus.FAILED,
                    timestamp=datetime.utcnow(),
                    provider=self.provider.get_provider_name(),
                    error_message="All recipients are unsubscribed",
                )

        # Handle template rendering
        if template_id:
            html_content, text_content = await self.template_manager.render_template(
                template_id, template_params or {}, language=language, user_id=user_id
            )
            html_body = html_body or html_content
            text_body = text_body or text_content

        # Add tracking elements
        if html_body:
            if track_opens:
                # Will be added after we get message_id
                pass

            if track_clicks:
                # Process links for click tracking
                # This would parse HTML and wrap links
                pass

        # Create email message
        message = EmailMessage(
            to=recipients,
            subject=subject,
            html_body=html_body,
            text_body=text_body,
            from_address=from_address or self._default_from,
            reply_to=reply_to,
            attachments=attachments,
            tags=tags,
            template_id=template_id,
            template_params=template_params,
        )

        # Send email
        result = await self.provider.send_email(message)

        # Record send for rate limiting
        if result.status == EmailStatus.SENT:
            for recipient in recipients:
                await self.rate_limiter.record_send(recipient.email)

        # Track email
        if result.status == EmailStatus.SENT and result.message_id:
            await tracker.track_email_sent(
                message_id=result.message_id,
                recipient=recipients[0].email if recipients else "",
                subject=subject,
                template_id=template_id,
                tags=tags,
            )

        return result

    async def send_bulk_emails(
        self, messages: List[Dict[str, Any]], batch_size: int = 50
    ) -> List[EmailResult]:
        """Send multiple emails efficiently.

        Args:
            messages: List of message dictionaries (same args as send_email)
            batch_size: Size of batches for sending

        Returns:
            List of EmailResult objects
        """
        results = []

        # Process in batches
        for i in range(0, len(messages), batch_size):
            batch = messages[i : i + batch_size]

            # Send each email
            for msg_data in batch:
                try:
                    result = await self.send_email(**msg_data)
                    results.append(result)
                except (ValueError, AttributeError, RuntimeError, OSError) as e:
                    logger.error(f"Failed to send bulk email: {e}")
                    results.append(
                        EmailResult(
                            message_id="",
                            status=EmailStatus.FAILED,
                            timestamp=datetime.utcnow(),
                            provider=self.provider.get_provider_name(),
                            error_message=str(e),
                        )
                    )

        return results

    async def handle_webhook(
        self, provider: str, headers: Dict[str, str], body: bytes
    ) -> bool:
        """Handle provider webhook for bounces/complaints.

        Args:
            provider: Provider name
            headers: HTTP headers
            body: Request body

        Returns:
            True if handled successfully
        """
        # Verify webhook
        if not await self.provider.verify_webhook(headers, body):
            logger.warning("Invalid webhook signature")
            return False

        # Parse webhook data
        try:
            data = json.loads(body)
        except (json.JSONDecodeError, ValueError):
            logger.error("Invalid webhook body")
            return False

        # Handle based on provider
        db = next(get_db())
        tracker = EmailTracker(db)

        if provider == "ses":
            # AWS SNS notification
            message_type = data.get("Type")

            if message_type == "Notification":
                notification = json.loads(data.get("Message", "{}"))
                event_type = notification.get("notificationType")

                if event_type == "Bounce":
                    bounce = await self.provider.handle_bounce(data)
                    await tracker.track_event(
                        message_id=bounce.message_id,
                        event_type=EmailEventType.BOUNCED,
                        timestamp=bounce.timestamp,
                        metadata={
                            "bounce_type": bounce.bounce_type,
                            "diagnostic": bounce.diagnostic_code,
                        },
                    )

                elif event_type == "Complaint":
                    complaint = await self.provider.handle_complaint(data)
                    await tracker.track_event(
                        message_id=complaint.message_id,
                        event_type=EmailEventType.COMPLAINED,
                        timestamp=complaint.timestamp,
                        metadata={"complaint_type": complaint.complaint_type},
                    )

        elif provider == "sendgrid":
            # SendGrid events
            for event in data if isinstance(data, list) else [data]:
                event_type = event.get("event")

                if event_type == "bounce":
                    bounce = await self.provider.handle_bounce(event)
                    await tracker.track_event(
                        message_id=bounce.message_id,
                        event_type=EmailEventType.BOUNCED,
                        timestamp=bounce.timestamp,
                    )

                elif event_type == "spamreport":
                    complaint = await self.provider.handle_complaint(event)
                    await tracker.track_event(
                        message_id=complaint.message_id,
                        event_type=EmailEventType.COMPLAINED,
                        timestamp=complaint.timestamp,
                    )

        return True

    def _normalize_recipients(
        self, to: Union[str, List[str], EmailAddress, List[EmailAddress]]
    ) -> List[EmailAddress]:
        """Normalize recipient input to list of EmailAddress objects."""
        if isinstance(to, str):
            return [EmailAddress(email=to)]
        elif isinstance(to, EmailAddress):
            return [to]
        elif isinstance(to, list):
            recipients = []
            for item in to:
                if isinstance(item, str):
                    recipients.append(EmailAddress(email=item))
                elif isinstance(item, EmailAddress):
                    recipients.append(item)
            return recipients
        # Type checker ensures this is exhaustive
        raise TypeError(f"Invalid recipient type: {type(to)}")

    async def get_email_stats(self, **kwargs: Any) -> Dict[str, Any]:
        """Get email statistics.

        Args:
            **kwargs: Same as EmailTracker.get_email_stats

        Returns:
            Statistics dictionary
        """
        db = next(get_db())
        tracker = EmailTracker(db)
        return await tracker.get_email_stats(**kwargs)

    async def test_connection(self) -> bool:
        """Test email provider connection.

        Returns:
            True if connection successful
        """
        return await self.provider.test_connection()


_email_service_instance: Optional[EnhancedEmailService] = None


def get_email_service() -> EnhancedEmailService:
    """Get the singleton email service instance."""
    global _email_service_instance
    if _email_service_instance is None:
        _email_service_instance = EnhancedEmailService()
    return _email_service_instance
