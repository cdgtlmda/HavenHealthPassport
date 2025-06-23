"""SendGrid email provider implementation."""

import hashlib
import hmac
import json
import os
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from src.utils.logging import get_logger

from .base import (
    BounceNotification,
    ComplaintNotification,
    EmailMessage,
    EmailProvider,
    EmailResult,
    EmailStatus,
)

logger = get_logger(__name__)

# Try to import sendgrid
try:
    from sendgrid import SendGridAPIClient
    from sendgrid.helpers.mail import (
        Attachment,
        Content,
        Disposition,
        Email,
        FileContent,
        FileName,
        FileType,
        Mail,
        To,
    )

    SENDGRID_AVAILABLE = True
except ImportError:
    SENDGRID_AVAILABLE = False
    # Define placeholder types when SendGrid is not available
    Mail = Any
    Email = Any
    To = Any
    Content = Any
    Attachment = Any
    FileContent = Any
    FileName = Any
    FileType = Any
    Disposition = Any
    SendGridAPIClient = Any
    logger.warning("SendGrid library not available. Install with: pip install sendgrid")


class SendGridProvider(EmailProvider):
    """SendGrid email provider."""

    def __init__(self, api_key: Optional[str] = None):
        """Initialize SendGrid provider.

        Args:
            api_key: SendGrid API key (defaults to env var)
        """
        self.api_key = api_key or os.getenv("SENDGRID_API_KEY")
        self.webhook_key = os.getenv("SENDGRID_WEBHOOK_KEY", "")

        if not self.api_key:
            raise ValueError("SendGrid API key not provided")

        if SENDGRID_AVAILABLE:
            self.client = SendGridAPIClient(self.api_key)
        else:
            self.client = None
            logger.error("SendGrid client not available")

    def get_provider_name(self) -> str:
        """Get provider name."""
        return "SendGrid"

    async def test_connection(self) -> bool:
        """Test SendGrid connection."""
        if not SENDGRID_AVAILABLE or not self.client:
            return False

        try:
            # Try to get account info
            response = self.client.client.user.profile.get()
            logger.info(f"SendGrid connection successful: {response.status_code}")
            return bool(response.status_code == 200)
        except (ValueError, AttributeError, RuntimeError) as e:
            logger.error(f"SendGrid connection test failed: {e}")
            return False

    def _build_sendgrid_mail(self, message: EmailMessage) -> Mail:
        """Build SendGrid Mail object from EmailMessage."""
        # From address
        from_email = Email(
            (
                message.from_address.email
                if message.from_address
                else os.getenv("FROM_EMAIL", "noreply@havenhealthpassport.org")
            ),
            (
                message.from_address.name
                if message.from_address and message.from_address.name
                else None
            ),
        )

        # To addresses (SendGrid requires individual Mail objects for multiple recipients)
        to_emails = [To(addr.email, addr.name) for addr in message.to]

        # Create mail object
        mail = Mail(from_email=from_email)

        # Add recipients
        for to_email in to_emails:
            mail.add_to(to_email)

        # Subject
        mail.subject = message.subject

        # Content
        if message.text_body:
            mail.add_content(Content("text/plain", message.text_body))
        if message.html_body:
            mail.add_content(Content("text/html", message.html_body))

        # Reply-to
        if message.reply_to:
            mail.reply_to = Email(message.reply_to.email, message.reply_to.name)

        # CC and BCC
        if message.cc:
            for cc in message.cc:
                mail.add_cc(Email(cc.email, cc.name))
        if message.bcc:
            for bcc in message.bcc:
                mail.add_bcc(Email(bcc.email, bcc.name))

        # Attachments
        if message.attachments:
            for att in message.attachments:
                attachment = Attachment()
                attachment.file_content = FileContent(att.content.decode("latin-1"))
                attachment.file_type = FileType(att.content_type)
                attachment.file_name = FileName(att.filename)
                attachment.disposition = Disposition("attachment")
                if att.content_id:
                    attachment.content_id = att.content_id
                    attachment.disposition = Disposition("inline")
                mail.add_attachment(attachment)

        # Custom headers
        if message.headers:
            mail.headers = message.headers

        # Categories (tags)
        if message.tags:
            mail.categories = message.tags

        # Metadata
        if message.metadata:
            mail.custom_args = message.metadata

        return mail

    async def send_email(self, message: EmailMessage) -> EmailResult:
        """Send email via SendGrid."""
        if not SENDGRID_AVAILABLE or not self.client:
            return EmailResult(
                message_id="",
                status=EmailStatus.FAILED,
                timestamp=datetime.utcnow(),
                provider=self.get_provider_name(),
                error_message="SendGrid client not available",
            )

        try:
            if message.template_id:
                # Use dynamic template
                mail = Mail(
                    from_email=Email(
                        (
                            message.from_address.email
                            if message.from_address
                            else os.getenv("FROM_EMAIL")
                        ),
                        message.from_address.name if message.from_address else None,
                    ),
                    to_emails=[To(addr.email, addr.name) for addr in message.to],
                )
                mail.template_id = message.template_id
                mail.dynamic_template_data = message.template_params or {}
            else:
                # Regular email
                mail = self._build_sendgrid_mail(message)

            # Send email
            response = self.client.send(mail)

            # Extract message ID from headers
            message_id = ""
            if hasattr(response, "headers") and "X-Message-Id" in response.headers:
                message_id = response.headers["X-Message-Id"]

            return EmailResult(
                message_id=message_id,
                status=EmailStatus.SENT,
                timestamp=datetime.utcnow(),
                provider=self.get_provider_name(),
                raw_response={
                    "status_code": response.status_code,
                    "body": response.body,
                    "headers": (
                        dict(response.headers) if hasattr(response, "headers") else {}
                    ),
                },
            )

        except (ValueError, AttributeError, RuntimeError, OSError) as e:
            logger.error(f"SendGrid send failed: {e}")

            error_message = str(e)
            if hasattr(e, "body"):
                error_message = e.body

            return EmailResult(
                message_id="",
                status=EmailStatus.FAILED,
                timestamp=datetime.utcnow(),
                provider=self.get_provider_name(),
                error_message=error_message,
            )

    async def send_bulk_emails(self, messages: List[EmailMessage]) -> List[EmailResult]:
        """Send multiple emails efficiently using batch send."""
        if not SENDGRID_AVAILABLE or not self.client:
            return [
                EmailResult(
                    message_id="",
                    status=EmailStatus.FAILED,
                    timestamp=datetime.utcnow(),
                    provider=self.get_provider_name(),
                    error_message="SendGrid client not available",
                )
                for _ in messages
            ]

        # SendGrid batch API has limits, so chunk if needed
        batch_size = 1000  # SendGrid limit
        results = []

        for i in range(0, len(messages), batch_size):
            batch = messages[i : i + batch_size]

            # For now, send individually (could optimize with personalization API)
            for message in batch:
                result = await self.send_email(message)
                results.append(result)

        return results

    async def get_email_status(self, message_id: str) -> Optional[EmailStatus]:
        """Get email status via Activity API."""
        if not SENDGRID_AVAILABLE or not self.client:
            return None

        try:
            # Query activity API
            response = self.client.client.messages._(message_id).get()

            if response.status_code == 200:
                data = json.loads(response.body)
                # Map SendGrid status to our status
                sg_status = data.get("status", "").lower()

                status_map = {
                    "processed": EmailStatus.SENT,
                    "delivered": EmailStatus.DELIVERED,
                    "bounce": EmailStatus.BOUNCED,
                    "deferred": EmailStatus.PENDING,
                    "spam": EmailStatus.COMPLAINED,
                    "blocked": EmailStatus.FAILED,
                }

                return status_map.get(sg_status, EmailStatus.PENDING)

        except (ValueError, AttributeError, RuntimeError, OSError) as e:
            logger.error(f"Failed to get email status: {e}")

        return None

    async def handle_bounce(
        self, bounce_data: Union[Dict[str, Any], List[Dict[str, Any]]]
    ) -> BounceNotification:
        """Process SendGrid bounce webhook."""
        # SendGrid sends array of events
        event: Dict[str, Any]
        if isinstance(bounce_data, list) and bounce_data:
            event = bounce_data[0]
        else:
            # Type assertion: if not list, then it's Dict
            assert isinstance(bounce_data, dict)
            event = bounce_data

        return BounceNotification(
            message_id=event.get("sg_message_id", ""),
            email=event.get("email", ""),
            bounce_type="hard" if event.get("type") == "bounce" else "soft",
            bounce_subtype=event.get("reason", ""),
            timestamp=datetime.fromtimestamp(event.get("timestamp", 0)),
            diagnostic_code=event.get("response", ""),
            action="failed",
        )

    async def handle_complaint(
        self, complaint_data: Union[Dict[str, Any], List[Dict[str, Any]]]
    ) -> ComplaintNotification:
        """Process SendGrid spam report webhook."""
        # SendGrid sends array of events
        event: Dict[str, Any]
        if isinstance(complaint_data, list) and complaint_data:
            event = complaint_data[0]
        else:
            # Type assertion: if not list, then it's Dict
            assert isinstance(complaint_data, dict)
            event = complaint_data

        return ComplaintNotification(
            message_id=event.get("sg_message_id", ""),
            email=event.get("email", ""),
            complaint_type="spam",
            timestamp=datetime.fromtimestamp(event.get("timestamp", 0)),
            user_agent=event.get("useragent", ""),
            arrival_date=None,
        )

    async def verify_webhook(self, headers: Dict[str, str], body: bytes) -> bool:
        """Verify SendGrid webhook signature."""
        if not self.webhook_key:
            logger.warning("SendGrid webhook key not configured")
            return False

        try:
            # Get signature from headers
            signature = headers.get("X-Twilio-Email-Event-Webhook-Signature", "")
            timestamp = headers.get("X-Twilio-Email-Event-Webhook-Timestamp", "")

            if not signature or not timestamp:
                return False

            # Build payload
            payload = timestamp + body.decode("utf-8")

            # Calculate expected signature
            expected = hmac.new(
                self.webhook_key.encode("utf-8"),
                payload.encode("utf-8"),
                hashlib.sha256,
            ).hexdigest()

            # Compare signatures
            return hmac.compare_digest(expected, signature)

        except (ValueError, AttributeError, RuntimeError, OSError) as e:
            logger.error(f"SendGrid webhook verification failed: {e}")
            return False
