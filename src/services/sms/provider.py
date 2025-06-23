"""SMS provider abstraction for multi-factor authentication.

This module provides a unified interface for sending SMS messages
through various providers like Twilio, AWS SNS, and others.
"""

import logging
from abc import ABC, abstractmethod
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field, validator

logger = logging.getLogger(__name__)


class SMSProvider(Enum):
    """Supported SMS providers."""

    TWILIO = "twilio"
    AWS_SNS = "aws_sns"
    MESSAGEBIRD = "messagebird"
    VONAGE = "vonage"
    MOCK = "mock"  # For testing


class SMSDeliveryStatus(Enum):
    """SMS delivery status."""

    PENDING = "pending"
    SENT = "sent"
    DELIVERED = "delivered"
    FAILED = "failed"
    UNKNOWN = "unknown"


class SMSMessage(BaseModel):
    """SMS message model."""

    to: str = Field(..., description="Recipient phone number in E.164 format")
    body: str = Field(..., description="Message body")
    from_number: Optional[str] = Field(None, description="Sender phone number")
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata"
    )

    @validator("to")
    @classmethod
    def validate_phone_number(cls, v: str) -> str:
        """Validate phone number format."""
        # Basic E.164 format validation
        if not v.startswith("+"):
            raise ValueError("Phone number must start with '+'")
        if not v[1:].isdigit():
            raise ValueError("Phone number must contain only digits after '+'")
        if len(v) < 10 or len(v) > 16:
            raise ValueError("Phone number must be between 10 and 16 digits")
        return v

    @validator("body")
    @classmethod
    def validate_body(cls, v: str) -> str:
        """Validate message body."""
        if not v or not v.strip():
            raise ValueError("Message body cannot be empty")
        if len(v) > 1600:  # SMS limit
            raise ValueError("Message body exceeds 1600 characters")
        return v


class SMSDeliveryReport(BaseModel):
    """SMS delivery report."""

    message_id: str
    status: SMSDeliveryStatus
    timestamp: datetime
    provider: str
    error_message: Optional[str] = None
    raw_response: Optional[Dict[str, Any]] = None


class SMSProviderInterface(ABC):
    """Abstract base class for SMS providers."""

    @abstractmethod
    async def send_sms(self, message: SMSMessage) -> SMSDeliveryReport:
        """Send SMS message.

        Args:
            message: SMS message to send

        Returns:
            Delivery report

        Raises:
            SMSException: If sending fails
        """

    @abstractmethod
    async def check_delivery_status(self, message_id: str) -> SMSDeliveryReport:
        """Check delivery status of a message.

        Args:
            message_id: Message ID to check

        Returns:
            Delivery report
        """

    @abstractmethod
    async def validate_phone_number(self, phone_number: str) -> bool:
        """Validate if phone number is reachable.

        Args:
            phone_number: Phone number to validate

        Returns:
            True if valid and reachable
        """

    @property
    @abstractmethod
    def name(self) -> str:
        """Get provider name."""

    @property
    @abstractmethod
    def supports_delivery_reports(self) -> bool:
        """Check if provider supports delivery reports."""


class SMSProviderConfig(BaseModel):
    """SMS provider configuration."""

    provider: SMSProvider
    enabled: bool = True
    priority: int = 0  # Lower number = higher priority

    # Rate limiting
    max_messages_per_minute: int = 60
    max_messages_per_hour: int = 1000
    max_messages_per_day: int = 10000

    # Retry configuration
    max_retries: int = 3
    retry_delay_seconds: int = 5

    # Provider-specific configuration
    config: Dict[str, Any] = Field(default_factory=dict)

    @validator("priority")
    @classmethod
    def validate_priority(cls, v: int) -> int:
        """Validate priority."""
        if v < 0:
            raise ValueError("Priority must be non-negative")
        return v

    @validator("max_messages_per_minute")
    @classmethod
    def validate_rate_limits(cls, v: int) -> int:
        """Validate rate limits."""
        if v <= 0:
            raise ValueError("Rate limits must be positive")
        return v
