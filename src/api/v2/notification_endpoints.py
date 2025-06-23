"""Notification management REST API endpoints.

This module provides endpoints for managing notifications, communication channels,
and user preferences in the Haven Health Passport system.
"""

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends
from fastapi.security import HTTPBearer
from pydantic import BaseModel, Field

from src.core.database import get_db
from src.utils.logging import get_logger

router = APIRouter(prefix="/notifications", tags=["notifications"])
logger = get_logger(__name__)
security = HTTPBearer()

# Dependency injection
db_dependency = Depends(get_db)
security_dependency = Depends(security)


# Request/Response Models
class NotificationChannel(BaseModel):
    """Notification channel configuration."""

    channel_id: uuid.UUID
    channel_type: str = Field(..., pattern="^(email|sms|push|in_app)$")
    name: str
    enabled: bool = Field(default=True)
    destination: str = Field(..., description="Email, phone number, device token, etc.")
    verified: bool = Field(default=False)
    language: str = Field(
        default="en", description="Preferred language for this channel"
    )


class NotificationPreference(BaseModel):
    """User notification preferences."""

    preference_id: uuid.UUID
    user_id: uuid.UUID
    notification_type: str = Field(..., description="Type of notification")
    channels: List[str] = Field(..., description="Enabled channels for this type")
    frequency: str = Field(
        default="immediate", pattern="^(immediate|daily|weekly|never)$"
    )
    quiet_hours_start: Optional[str] = Field(
        None, pattern="^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$"
    )
    quiet_hours_end: Optional[str] = Field(
        None, pattern="^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$"
    )
    time_zone: str = Field(default="UTC")


class SendNotificationRequest(BaseModel):
    """Request to send a notification."""

    recipient_id: uuid.UUID = Field(..., description="User ID of recipient")
    notification_type: str = Field(..., description="Type of notification")
    subject: str = Field(..., max_length=200)
    message: str = Field(..., max_length=2000)
    priority: str = Field(default="normal", pattern="^(low|normal|high|urgent)$")
    channels: Optional[List[str]] = Field(None, description="Override default channels")
    data: Optional[Dict[str, Any]] = Field(None, description="Additional data payload")
    schedule_for: Optional[datetime] = Field(
        None, description="Schedule for future delivery"
    )


class NotificationResponse(BaseModel):
    """Notification send response."""

    notification_id: uuid.UUID
    status: str = Field(..., description="Status (sent, queued, failed)")
    channels_used: List[str]
    sent_at: Optional[datetime]
    scheduled_for: Optional[datetime]
    errors: Optional[List[str]] = None
