"""Email Service implementation for Haven Health Passport.

This module provides a unified interface for sending emails with support
for multiple providers, rate limiting, and proper error handling.
"""

import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional

from src.utils.logging import get_logger

logger = get_logger(__name__)


class EmailStatus(Enum):
    """Email delivery status."""

    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"
    BOUNCED = "bounced"
    COMPLAINED = "complained"


@dataclass
class Email:
    """Email message structure."""

    to: List[str]
    subject: str
    body_html: str
    body_text: str
    from_email: Optional[str] = None
    reply_to: Optional[str] = None
    cc: List[str] = field(default_factory=list)
    bcc: List[str] = field(default_factory=list)
    headers: Dict[str, str] = field(default_factory=dict)
    attachments: List[Dict[str, Any]] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EmailResult:
    """Result of email send operation."""

    message_id: Optional[str]
    status: EmailStatus
    error: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
    provider_response: Dict[str, Any] = field(default_factory=dict)


class EmailProvider(ABC):
    """Abstract base class for email providers."""

    @abstractmethod
    async def send_email(self, email: Email) -> EmailResult:
        """Send an email through the provider."""

    @abstractmethod
    async def get_send_quota(self) -> Dict[str, Any]:
        """Get current send quota information."""

    @abstractmethod
    async def handle_bounce(self, bounce_data: Dict[str, Any]) -> None:
        """Handle email bounce notification."""

    @abstractmethod
    async def handle_complaint(self, complaint_data: Dict[str, Any]) -> None:
        """Handle email complaint notification."""


class RateLimiter:
    """Token bucket rate limiter for email sending."""

    def __init__(self, max_per_minute: int = 10, max_per_hour: int = 100):
        """Initialize rate limiter.

        Args:
            max_per_minute: Maximum emails per minute
            max_per_hour: Maximum emails per hour
        """
        self.max_per_minute = max_per_minute
        self.max_per_hour = max_per_hour
        self.minute_bucket: List[datetime] = []
        self.hour_bucket: List[datetime] = []
        self._lock = asyncio.Lock()

    async def acquire(self) -> bool:
        """Acquire permission to send an email.

        Returns:
            True if permitted, False if rate limit exceeded
        """
        async with self._lock:
            now = datetime.utcnow()

            # Clean old entries
            minute_ago = now - timedelta(minutes=1)
            hour_ago = now - timedelta(hours=1)

            self.minute_bucket = [t for t in self.minute_bucket if t > minute_ago]
            self.hour_bucket = [t for t in self.hour_bucket if t > hour_ago]

            # Check limits
            if len(self.minute_bucket) >= self.max_per_minute:
                logger.warning("Per-minute email rate limit exceeded")
                return False

            if len(self.hour_bucket) >= self.max_per_hour:
                logger.warning("Per-hour email rate limit exceeded")
                return False

            # Record send
            self.minute_bucket.append(now)
            self.hour_bucket.append(now)
            return True

    def get_status(self) -> Dict[str, Any]:
        """Get current rate limiter status."""
        now = datetime.utcnow()
        minute_ago = now - timedelta(minutes=1)
        hour_ago = now - timedelta(hours=1)

        minute_count = len([t for t in self.minute_bucket if t > minute_ago])
        hour_count = len([t for t in self.hour_bucket if t > hour_ago])

        return {
            "minute_count": minute_count,
            "minute_limit": self.max_per_minute,
            "hour_count": hour_count,
            "hour_limit": self.max_per_hour,
            "minute_remaining": max(0, self.max_per_minute - minute_count),
            "hour_remaining": max(0, self.max_per_hour - hour_count),
        }


class EmailService:
    """Main email service with provider abstraction and rate limiting."""

    def __init__(
        self,
        provider: EmailProvider,
        rate_limiter: Optional[RateLimiter] = None,
        default_from_email: str = "noreply@havenhealthpassport.org",
        bounce_handler_enabled: bool = True,
    ):
        """Initialize email service.

        Args:
            provider: Email provider instance
            rate_limiter: Optional rate limiter
            default_from_email: Default sender email address
            bounce_handler_enabled: Whether to handle bounces/complaints
        """
        self.provider = provider
        self.rate_limiter = rate_limiter or RateLimiter()
        self.default_from_email = default_from_email
        self.bounce_handler_enabled = bounce_handler_enabled
        self._send_history: List[EmailResult] = []

    async def send_email(
        self, email: Email, retry_attempts: int = 3, retry_delay: float = 1.0
    ) -> EmailResult:
        """Send an email with rate limiting and retry logic.

        Args:
            email: Email to send
            retry_attempts: Number of retry attempts
            retry_delay: Delay between retries in seconds

        Returns:
            EmailResult with send status
        """
        # Apply rate limiting
        if not await self.rate_limiter.acquire():
            return EmailResult(
                message_id=None, status=EmailStatus.FAILED, error="Rate limit exceeded"
            )

        # Set default from email if not provided
        if not email.from_email:
            email.from_email = self.default_from_email

        # Attempt to send with retries
        last_error = None
        for attempt in range(retry_attempts):
            try:
                result = await self.provider.send_email(email)
                self._send_history.append(result)

                if result.status == EmailStatus.SENT:
                    logger.info(
                        f"Email sent successfully: {result.message_id} to {email.to}"
                    )
                    return result

                last_error = result.error

            except (ValueError, AttributeError, RuntimeError, OSError) as e:
                last_error = str(e)
                logger.error(f"Email send attempt {attempt + 1} failed: {e}")

            if attempt < retry_attempts - 1:
                await asyncio.sleep(retry_delay * (attempt + 1))

        # All attempts failed
        result = EmailResult(
            message_id=None,
            status=EmailStatus.FAILED,
            error=last_error or "Unknown error",
        )
        self._send_history.append(result)
        return result

    async def send_bulk(
        self, emails: List[Email], batch_size: int = 10, batch_delay: float = 1.0
    ) -> List[EmailResult]:
        """Send multiple emails in batches.

        Args:
            emails: List of emails to send
            batch_size: Number of emails per batch
            batch_delay: Delay between batches in seconds

        Returns:
            List of EmailResults
        """
        results = []

        for i in range(0, len(emails), batch_size):
            batch = emails[i : i + batch_size]
            batch_results = await asyncio.gather(
                *[self.send_email(email) for email in batch], return_exceptions=True
            )

            for _, result in enumerate(batch_results):
                if isinstance(result, Exception):
                    results.append(
                        EmailResult(
                            message_id=None,
                            status=EmailStatus.FAILED,
                            error=str(result),
                        )
                    )
                else:
                    # Type assertion: if not Exception, then it's EmailResult
                    assert isinstance(result, EmailResult)
                    results.append(result)

            if i + batch_size < len(emails):
                await asyncio.sleep(batch_delay)

        return results

    async def handle_webhook(self, webhook_data: Dict[str, Any]) -> None:
        """Handle webhook from email provider.

        Args:
            webhook_data: Webhook payload data
        """
        if not self.bounce_handler_enabled:
            return

        webhook_type = webhook_data.get("Type", "").lower()

        if webhook_type == "bounce":
            await self.provider.handle_bounce(webhook_data)
        elif webhook_type == "complaint":
            await self.provider.handle_complaint(webhook_data)
        else:
            logger.warning(f"Unknown webhook type: {webhook_type}")

    def get_statistics(self) -> Dict[str, Any]:
        """Get email sending statistics."""
        total_sent = len(self._send_history)
        successful = sum(1 for r in self._send_history if r.status == EmailStatus.SENT)
        failed = sum(1 for r in self._send_history if r.status == EmailStatus.FAILED)

        return {
            "total_sent": total_sent,
            "successful": successful,
            "failed": failed,
            "success_rate": successful / total_sent if total_sent > 0 else 0,
            "rate_limiter_status": self.rate_limiter.get_status(),
            "last_sent": (
                self._send_history[-1].timestamp if self._send_history else None
            ),
        }
