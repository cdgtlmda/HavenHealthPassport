"""Email service module."""

from .email_service import EmailService
from .email_tracker import EmailEventType, EmailTracker
from .enhanced_email_service import EnhancedEmailService, get_email_service
from .providers import (
    AWSSESProvider,
    EmailAddress,
    EmailAttachment,
    EmailMessage,
    EmailProvider,
    EmailResult,
    EmailStatus,
    SendGridProvider,
)
from .rate_limiter import EmailRateLimiter
from .template_manager import EmailTemplateManager

__all__ = [
    "EmailService",
    "EnhancedEmailService",
    "get_email_service",
    "EmailProvider",
    "EmailMessage",
    "EmailResult",
    "EmailStatus",
    "EmailAddress",
    "EmailAttachment",
    "AWSSESProvider",
    "SendGridProvider",
    "EmailRateLimiter",
    "EmailTemplateManager",
    "EmailTracker",
    "EmailEventType",
]
