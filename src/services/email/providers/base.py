"""Base email provider interface."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class EmailStatus(str, Enum):
    """Email delivery status."""

    PENDING = "pending"
    SENT = "sent"
    DELIVERED = "delivered"
    BOUNCED = "bounced"
    COMPLAINED = "complained"
    FAILED = "failed"


@dataclass
class EmailAddress:
    """Email address with optional name."""

    email: str
    name: Optional[str] = None

    def __str__(self) -> str:
        """Return string representation of email address."""
        if self.name:
            return f'"{self.name}" <{self.email}>'
        return self.email


@dataclass
class EmailAttachment:
    """Email attachment."""

    filename: str
    content: bytes
    content_type: str = "application/octet-stream"
    content_id: Optional[str] = None  # For inline attachments


@dataclass
class EmailMessage:
    """Email message structure."""

    to: List[EmailAddress]
    subject: str
    html_body: Optional[str] = None
    text_body: Optional[str] = None
    from_address: Optional[EmailAddress] = None
    reply_to: Optional[EmailAddress] = None
    cc: Optional[List[EmailAddress]] = None
    bcc: Optional[List[EmailAddress]] = None
    attachments: Optional[List[EmailAttachment]] = None
    headers: Optional[Dict[str, str]] = None
    tags: Optional[List[str]] = None  # For tracking
    metadata: Optional[Dict[str, Any]] = None  # Provider-specific data
    template_id: Optional[str] = None
    template_params: Optional[Dict[str, Any]] = None


@dataclass
class EmailResult:
    """Result of email send operation."""

    message_id: str
    status: EmailStatus
    timestamp: datetime
    provider: str
    raw_response: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None


@dataclass
class BounceNotification:
    """Email bounce notification."""

    message_id: str
    email: str
    bounce_type: str  # hard, soft, transient
    timestamp: datetime
    bounce_subtype: Optional[str] = None
    diagnostic_code: Optional[str] = None
    action: Optional[str] = None  # failed, delayed


@dataclass
class ComplaintNotification:
    """Email complaint/spam notification."""

    message_id: str
    email: str
    complaint_type: str  # abuse, fraud, virus, other
    timestamp: datetime
    user_agent: Optional[str] = None
    arrival_date: Optional[datetime] = None


class EmailProvider(ABC):
    """Abstract base class for email providers."""

    @abstractmethod
    async def send_email(self, message: EmailMessage) -> EmailResult:
        """Send an email message.

        Args:
            message: Email message to send

        Returns:
            EmailResult with send status
        """

    @abstractmethod
    async def send_bulk_emails(self, messages: List[EmailMessage]) -> List[EmailResult]:
        """Send multiple emails efficiently.

        Args:
            messages: List of email messages

        Returns:
            List of EmailResult objects
        """

    @abstractmethod
    async def get_email_status(self, message_id: str) -> Optional[EmailStatus]:
        """Get the delivery status of an email.

        Args:
            message_id: Provider's message ID

        Returns:
            Current email status or None if not found
        """

    @abstractmethod
    async def handle_bounce(self, bounce_data: Dict[str, Any]) -> BounceNotification:
        """Process bounce notification from provider.

        Args:
            bounce_data: Raw bounce data from provider webhook

        Returns:
            Parsed bounce notification
        """

    @abstractmethod
    async def handle_complaint(
        self, complaint_data: Dict[str, Any]
    ) -> ComplaintNotification:
        """Process complaint notification from provider.

        Args:
            complaint_data: Raw complaint data from provider webhook

        Returns:
            Parsed complaint notification
        """

    @abstractmethod
    async def verify_webhook(self, headers: Dict[str, str], body: bytes) -> bool:
        """Verify webhook request is from the provider.

        Args:
            headers: HTTP headers
            body: Raw request body

        Returns:
            True if webhook is valid
        """

    @abstractmethod
    def get_provider_name(self) -> str:
        """Get the provider name."""

    @abstractmethod
    async def test_connection(self) -> bool:
        """Test if the provider is properly configured and accessible.

        Returns:
            True if connection successful
        """
