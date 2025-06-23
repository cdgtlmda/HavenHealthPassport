"""
Notification Service Module for Haven Health Passport.

This module provides unified notification capabilities across multiple channels
including email, SMS, push notifications, and in-app messaging.
"""

from .base import Notification, NotificationChannel, NotificationResult
from .channels import EmailChannel, InAppChannel, PushChannel, SMSChannel
from .service import NotificationService
from .templates import NotificationTemplate, TemplateEngine

__all__ = [
    "NotificationChannel",
    "Notification",
    "NotificationResult",
    "EmailChannel",
    "SMSChannel",
    "PushChannel",
    "InAppChannel",
    "NotificationService",
    "NotificationTemplate",
    "TemplateEngine",
]
