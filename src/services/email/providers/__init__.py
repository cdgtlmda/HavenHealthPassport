"""Email providers package."""

from .aws_ses import AWSSESProvider
from .base import (
    BounceNotification,
    ComplaintNotification,
    EmailAddress,
    EmailAttachment,
    EmailMessage,
    EmailProvider,
    EmailResult,
    EmailStatus,
)
from .sendgrid import SendGridProvider

__all__ = [
    "EmailProvider",
    "EmailMessage",
    "EmailResult",
    "EmailStatus",
    "EmailAddress",
    "EmailAttachment",
    "BounceNotification",
    "ComplaintNotification",
    "AWSSESProvider",
    "SendGridProvider",
]
