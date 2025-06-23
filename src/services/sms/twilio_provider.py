"""Twilio SMS provider implementation.

This module provides SMS functionality using the Twilio API.
"""

import logging
from datetime import datetime
from typing import TYPE_CHECKING

from src.services.sms.provider import (
    SMSDeliveryReport,
    SMSDeliveryStatus,
    SMSMessage,
    SMSProvider,
    SMSProviderInterface,
)
from src.utils.exceptions import SMSException

if TYPE_CHECKING:
    from twilio.base.exceptions import TwilioException
    from twilio.rest import Client
else:
    try:
        from twilio.base.exceptions import TwilioException
        from twilio.rest import Client
    except ImportError:
        TwilioException = Exception
        Client = None

logger = logging.getLogger(__name__)


class TwilioSMSProvider(SMSProviderInterface):
    """Twilio SMS provider implementation."""

    def __init__(self, account_sid: str, auth_token: str, from_number: str):
        """Initialize Twilio provider.

        Args:
            account_sid: Twilio account SID
            auth_token: Twilio auth token
            from_number: Default sender phone number
        """
        self.client = Client(account_sid, auth_token)
        self.from_number = from_number
        self._name = SMSProvider.TWILIO.value

    async def send_sms(self, message: SMSMessage) -> SMSDeliveryReport:
        """Send SMS via Twilio.

        Args:
            message: SMS message to send

        Returns:
            Delivery report
        """
        try:
            # Send message
            twilio_message = self.client.messages.create(
                body=message.body,
                to=message.to,
                from_=message.from_number or self.from_number,
                status_callback=message.metadata.get("status_callback_url"),
            )

            # Log success
            logger.info("SMS sent via Twilio: %s", twilio_message.sid)

            # Create delivery report
            return SMSDeliveryReport(
                message_id=twilio_message.sid,
                status=self._map_twilio_status(twilio_message.status),
                timestamp=datetime.utcnow(),
                provider=self._name,
                raw_response={
                    "sid": twilio_message.sid,
                    "status": twilio_message.status,
                    "to": twilio_message.to,
                    "from": twilio_message.from_,
                    "date_created": str(twilio_message.date_created),
                    "price": twilio_message.price,
                    "price_unit": twilio_message.price_unit,
                },
            )

        except (ValueError, AttributeError, KeyError) as e:
            error_msg = f"{type(e).__name__}: {str(e)}"
            logger.error("Error sending SMS: %s", error_msg)
            raise SMSException(error_msg) from e
        except TwilioException as e:
            error_msg = str(e)
            logger.error("Twilio SMS send failed: %s", error_msg)
            raise SMSException(f"Failed to send SMS via Twilio: {error_msg}") from e

    async def check_delivery_status(self, message_id: str) -> SMSDeliveryReport:
        """Check delivery status via Twilio.

        Args:
            message_id: Twilio message SID

        Returns:
            Delivery report
        """
        try:
            # Fetch message status
            twilio_message = self.client.messages(message_id).fetch()

            return SMSDeliveryReport(
                message_id=message_id,
                status=self._map_twilio_status(twilio_message.status),
                timestamp=datetime.utcnow(),
                provider=self._name,
                error_message=twilio_message.error_message,
                raw_response={
                    "sid": twilio_message.sid,
                    "status": twilio_message.status,
                    "error_code": twilio_message.error_code,
                    "error_message": twilio_message.error_message,
                },
            )

        except TwilioException as e:
            logger.error("Failed to check Twilio message status: %s", str(e))
            raise SMSException(f"Failed to check status: {str(e)}") from e

    async def validate_phone_number(self, phone_number: str) -> bool:
        """Validate phone number via Twilio Lookup API.

        Args:
            phone_number: Phone number to validate

        Returns:
            True if valid
        """
        try:
            phone = self.client.lookups.v1.phone_numbers(phone_number).fetch()
            return phone.phone_number is not None
        except (TwilioException, ValueError, AttributeError):
            return False

    @property
    def name(self) -> str:
        """Get provider name."""
        return self._name

    @property
    def supports_delivery_reports(self) -> bool:
        """Twilio supports delivery reports."""
        return True

    def _map_twilio_status(self, twilio_status: str) -> SMSDeliveryStatus:
        """Map Twilio status to internal status.

        Args:
            twilio_status: Twilio message status

        Returns:
            Internal delivery status
        """
        status_map = {
            "queued": SMSDeliveryStatus.PENDING,
            "sending": SMSDeliveryStatus.PENDING,
            "sent": SMSDeliveryStatus.SENT,
            "delivered": SMSDeliveryStatus.DELIVERED,
            "failed": SMSDeliveryStatus.FAILED,
            "undelivered": SMSDeliveryStatus.FAILED,
        }

        return status_map.get(twilio_status, SMSDeliveryStatus.UNKNOWN)
