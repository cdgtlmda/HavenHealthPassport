"""Mock SMS provider for testing and development.

⚠️  DEVELOPER APPROVAL REQUIRED ⚠️
This mock implementation is ONLY acceptable for:
- Local development environment
- Non-production testing
- SMS provider integration testing

NEVER use in production - patient lives depend on real SMS communications.

This module provides a mock SMS provider that simulates SMS sending
without actually sending messages.
"""

import asyncio
import logging
import random
from datetime import datetime
from typing import Any, Dict, List

from src.services.sms.provider import (
    SMSDeliveryReport,
    SMSDeliveryStatus,
    SMSMessage,
    SMSProvider,
    SMSProviderInterface,
)
from src.utils.exceptions import SMSException

logger = logging.getLogger(__name__)


class MockSMSProvider(SMSProviderInterface):
    """Mock SMS provider for testing."""

    def __init__(
        self,
        failure_rate: float = 0.0,
        delivery_delay_seconds: float = 0.5,
        store_messages: bool = True,
    ):
        """Initialize mock provider.

        Args:
            failure_rate: Probability of failure (0.0 to 1.0)
            delivery_delay_seconds: Simulated delivery delay
            store_messages: Whether to store sent messages
        """
        self.failure_rate = failure_rate
        self.delivery_delay_seconds = delivery_delay_seconds
        self.store_messages = store_messages
        self._name = SMSProvider.MOCK.value
        self.sent_messages: List[Dict[str, Any]] = []

    async def send_sms(self, message: SMSMessage) -> SMSDeliveryReport:
        """Simulate sending SMS.

        Args:
            message: SMS message to send

        Returns:
            Delivery report
        """
        # Simulate network delay
        await asyncio.sleep(self.delivery_delay_seconds)

        # Simulate random failures
        if random.random() < self.failure_rate:
            logger.warning("Mock SMS send failed (simulated): %s", message.to)
            raise SMSException("Simulated SMS send failure")

        # Generate mock message ID
        message_id = (
            f"mock_{datetime.utcnow().timestamp()}_{random.randint(1000, 9999)}"
        )

        # Store message if configured
        if self.store_messages:
            self.sent_messages.append(
                {
                    "message_id": message_id,
                    "to": message.to,
                    "body": message.body,
                    "timestamp": datetime.utcnow(),
                    "metadata": message.metadata,
                }
            )

        # Log the mock send
        logger.info("Mock SMS sent to %s: %s...", message.to, message.body[:50])
        print(f"[MOCK SMS] To: {message.to}\nBody: {message.body}")

        # Create delivery report
        return SMSDeliveryReport(
            message_id=message_id,
            status=SMSDeliveryStatus.DELIVERED,
            timestamp=datetime.utcnow(),
            provider=self._name,
            raw_response={"mock": True, "stored": self.store_messages},
        )

    async def check_delivery_status(self, message_id: str) -> SMSDeliveryReport:
        """Check mock delivery status.

        Args:
            message_id: Message ID

        Returns:
            Delivery report
        """
        # Find message in store
        message_found = False
        if self.store_messages:
            for msg in self.sent_messages:
                if msg["message_id"] == message_id:
                    message_found = True
                    break

        status = (
            SMSDeliveryStatus.DELIVERED if message_found else SMSDeliveryStatus.UNKNOWN
        )

        return SMSDeliveryReport(
            message_id=message_id,
            status=status,
            timestamp=datetime.utcnow(),
            provider=self._name,
            raw_response={"mock": True, "found": message_found},
        )

    async def validate_phone_number(self, phone_number: str) -> bool:
        """Validate phone number (always returns True for mock).

        Args:
            phone_number: Phone number to validate

        Returns:
            True
        """
        # Mock provider accepts all properly formatted numbers
        return (
            phone_number.startswith("+")
            and phone_number[1:].isdigit()
            and 10 <= len(phone_number) <= 16
        )

    @property
    def name(self) -> str:
        """Get provider name."""
        return self._name

    @property
    def supports_delivery_reports(self) -> bool:
        """Mock provider supports delivery reports."""
        return True

    def get_sent_messages(self) -> List[Dict[str, Any]]:
        """Get all sent messages (for testing).

        Returns:
            List of sent messages
        """
        return self.sent_messages.copy()

    def clear_sent_messages(self) -> None:
        """Clear sent messages store (for testing)."""
        self.sent_messages.clear()
