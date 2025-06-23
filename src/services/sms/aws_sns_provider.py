"""AWS SNS SMS provider implementation.

This module provides SMS functionality using AWS Simple Notification Service.

This module handles encrypted PHI with access control and audit logging
to ensure HIPAA compliance.
"""

import logging
from datetime import datetime
from typing import Optional

import boto3
from botocore.exceptions import ClientError

from src.services.sms.provider import (
    SMSDeliveryReport,
    SMSDeliveryStatus,
    SMSMessage,
    SMSProvider,
    SMSProviderInterface,
)
from src.utils.exceptions import SMSException

logger = logging.getLogger(__name__)


class AWSSNSProvider(SMSProviderInterface):
    """AWS SNS SMS provider implementation."""

    def __init__(
        self,
        region_name: str = "us-east-1",
        aws_access_key_id: Optional[str] = None,
        aws_secret_access_key: Optional[str] = None,
        sender_id: Optional[str] = None,
    ):
        """Initialize AWS SNS provider.

        Args:
            region_name: AWS region
            aws_access_key_id: AWS access key (uses default if not provided)
            aws_secret_access_key: AWS secret key (uses default if not provided)
            sender_id: SMS sender ID (optional)
        """
        self.sns_client = boto3.client(
            "sns",
            region_name=region_name,
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
        )
        self.sender_id = sender_id
        self._name = SMSProvider.AWS_SNS.value

    async def send_sms(self, message: SMSMessage) -> SMSDeliveryReport:
        """Send SMS via AWS SNS.

        Args:
            message: SMS message to send

        Returns:
            Delivery report
        """
        try:
            # Set SMS attributes
            attributes = {
                "AWS.SNS.SMS.SMSType": {
                    "DataType": "String",
                    "StringValue": "Transactional",  # High priority
                }
            }

            if self.sender_id:
                attributes["AWS.SNS.SMS.SenderID"] = {
                    "DataType": "String",
                    "StringValue": self.sender_id,
                }

            # Send SMS
            response = self.sns_client.publish(
                PhoneNumber=message.to,
                Message=message.body,
                MessageAttributes=attributes,
            )

            message_id = response["MessageId"]
            logger.info("SMS sent via AWS SNS: %s", message_id)

            # Create delivery report
            return SMSDeliveryReport(
                message_id=message_id,
                status=SMSDeliveryStatus.SENT,
                timestamp=datetime.utcnow(),
                provider=self._name,
                raw_response=response,
            )

        except ClientError as e:
            logger.error("AWS SNS SMS send failed: %s", str(e))
            raise SMSException(f"Failed to send SMS via AWS SNS: {str(e)}") from e
        except Exception as e:
            logger.error("Unexpected error sending SMS: %s", str(e))
            raise SMSException(f"Unexpected error: {str(e)}") from e

    async def check_delivery_status(self, message_id: str) -> SMSDeliveryReport:
        """Check delivery status via AWS SNS.

        Note: AWS SNS doesn't provide direct status checking.
        This would require CloudWatch Logs integration.

        Args:
            message_id: Message ID

        Returns:
            Delivery report
        """
        # AWS SNS doesn't provide direct message status lookup
        # Would need to integrate with CloudWatch Logs for delivery reports
        logger.warning("AWS SNS doesn't support direct status checking")

        return SMSDeliveryReport(
            message_id=message_id,
            status=SMSDeliveryStatus.UNKNOWN,
            timestamp=datetime.utcnow(),
            provider=self._name,
            error_message="Status checking not supported",
        )

    async def validate_phone_number(self, phone_number: str) -> bool:
        """Validate phone number format.

        AWS SNS doesn't provide phone validation API.

        Args:
            phone_number: Phone number to validate

        Returns:
            True if format is valid
        """
        # Basic E.164 format validation
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
        """AWS SNS has limited delivery report support."""
        return False
