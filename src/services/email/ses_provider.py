"""AWS SES Email Provider implementation.

This module provides email sending capabilities using Amazon Simple Email Service (SES).
"""

import json
from typing import Any, Dict, List, Optional, Set

import boto3
from botocore.exceptions import ClientError

from src.services.email.email_service import (
    Email,
    EmailProvider,
    EmailResult,
    EmailStatus,
)
from src.utils.logging import get_logger

logger = get_logger(__name__)


class SESProvider(EmailProvider):
    """AWS SES email provider implementation."""

    def __init__(
        self,
        region_name: str = "us-east-1",
        aws_access_key_id: Optional[str] = None,
        aws_secret_access_key: Optional[str] = None,
        configuration_set: Optional[str] = None,
        suppress_list: Optional[Set[str]] = None,
    ):
        """Initialize SES provider.

        Args:
            region_name: AWS region
            aws_access_key_id: AWS access key (uses environment if not provided)
            aws_secret_access_key: AWS secret key (uses environment if not provided)
            configuration_set: SES configuration set name for tracking
            suppress_list: Set of email addresses to suppress sending to
        """
        self.ses_client = boto3.client(
            "ses",
            region_name=region_name,
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
        )
        self.configuration_set = configuration_set
        self.suppress_list = suppress_list or set()
        self._verified_identities_cache: Optional[Set[str]] = None

    async def send_email(self, email: Email) -> EmailResult:
        """Send email through AWS SES.

        Args:
            email: Email to send

        Returns:
            EmailResult with send status
        """
        # Check suppression list
        recipients = [r for r in email.to if r not in self.suppress_list]
        if not recipients:
            return EmailResult(
                message_id=None,
                status=EmailStatus.FAILED,
                error="All recipients are in suppression list",
            )

        # Verify sender identity
        if not email.from_email or not await self._is_identity_verified(
            email.from_email
        ):
            return EmailResult(
                message_id=None,
                status=EmailStatus.FAILED,
                error=f"Sender identity not verified: {email.from_email}",
            )

        try:
            # Prepare message
            message: Dict[str, Any] = {
                "Subject": {"Data": email.subject, "Charset": "UTF-8"},
                "Body": {},
            }

            if email.body_html:
                message["Body"]["Html"] = {"Data": email.body_html, "Charset": "UTF-8"}
            if email.body_text:
                message["Body"]["Text"] = {"Data": email.body_text, "Charset": "UTF-8"}

            # Prepare destination
            destination = {"ToAddresses": recipients}
            if email.cc:
                destination["CcAddresses"] = [
                    cc for cc in email.cc if cc not in self.suppress_list
                ]
            if email.bcc:
                destination["BccAddresses"] = [
                    bcc for bcc in email.bcc if bcc not in self.suppress_list
                ]

            # Send email
            params: Dict[str, Any] = {
                "Source": email.from_email,
                "Destination": destination,
                "Message": message,
            }

            if email.reply_to:
                params["ReplyToAddresses"] = [email.reply_to]

            if self.configuration_set:
                params["ConfigurationSetName"] = self.configuration_set

            if email.tags:
                params["Tags"] = [
                    {"Name": f"tag-{i}", "Value": tag}
                    for i, tag in enumerate(email.tags[:10])  # SES allows max 10 tags
                ]

            response = self.ses_client.send_email(**params)

            return EmailResult(
                message_id=response["MessageId"],
                status=EmailStatus.SENT,
                provider_response=response,
            )

        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            error_message = e.response["Error"]["Message"]

            logger.error(f"SES send failed: {error_code} - {error_message}")

            return EmailResult(
                message_id=None,
                status=EmailStatus.FAILED,
                error=f"{error_code}: {error_message}",
                provider_response=e.response,
            )

    async def get_send_quota(self) -> Dict[str, Any]:
        """Get SES sending quota information.

        Returns:
            Dictionary with quota information
        """
        try:
            response = self.ses_client.get_send_quota()
            return {
                "max_24_hour_send": response.get("Max24HourSend", 0),
                "max_send_rate": response.get("MaxSendRate", 0),
                "sent_last_24_hours": response.get("SentLast24Hours", 0),
                "remaining_24_hour": (
                    response.get("Max24HourSend", 0)
                    - response.get("SentLast24Hours", 0)
                ),
            }
        except ClientError as e:
            logger.error(f"Failed to get SES quota: {e}")
            return {}

    async def handle_bounce(self, bounce_data: Dict[str, Any]) -> None:
        """Handle SES bounce notification.

        Args:
            bounce_data: Bounce notification data
        """
        try:
            message = json.loads(bounce_data.get("Message", "{}"))
            bounce = message.get("bounce", {})
            bounced_recipients = bounce.get("bouncedRecipients", [])

            for recipient in bounced_recipients:
                email = recipient.get("emailAddress")
                if email:
                    self.suppress_list.add(email)
                    logger.warning(
                        f"Added {email} to suppression list due to bounce: "
                        f"{bounce.get('bounceType')} - {bounce.get('bounceSubType')}"
                    )

        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"Failed to process bounce notification: {e}")

    async def handle_complaint(self, complaint_data: Dict[str, Any]) -> None:
        """Handle SES complaint notification.

        Args:
            complaint_data: Complaint notification data
        """
        try:
            message = json.loads(complaint_data.get("Message", "{}"))
            complaint = message.get("complaint", {})
            complained_recipients = complaint.get("complainedRecipients", [])

            for recipient in complained_recipients:
                email = recipient.get("emailAddress")
                if email:
                    self.suppress_list.add(email)
                    logger.warning(
                        f"Added {email} to suppression list due to complaint: "
                        f"{complaint.get('complaintFeedbackType')}"
                    )

        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"Failed to process complaint notification: {e}")

    async def _is_identity_verified(self, identity: str) -> bool:
        """Check if email identity is verified in SES.

        Args:
            identity: Email address or domain to check

        Returns:
            True if verified
        """
        if self._verified_identities_cache is None:
            try:
                response = self.ses_client.list_verified_email_addresses()
                self._verified_identities_cache = set(
                    response.get("VerifiedEmailAddresses", [])
                )
            except ClientError as e:
                logger.error(f"Failed to list verified identities: {e}")
                return False

        # Check exact email match
        if identity in self._verified_identities_cache:
            return True

        # Check domain verification
        domain = identity.split("@")[-1]
        try:
            response = self.ses_client.get_identity_verification_attributes(
                Identities=[domain]
            )
            attrs = response.get("VerificationAttributes", {}).get(domain, {})
            return bool(attrs.get("VerificationStatus") == "Success")
        except ClientError:
            return False

    def add_to_suppression_list(self, email_addresses: List[str]) -> None:
        """Add email addresses to suppression list.

        Args:
            email_addresses: List of addresses to suppress
        """
        self.suppress_list.update(email_addresses)
        logger.info(f"Added {len(email_addresses)} addresses to suppression list")

    def remove_from_suppression_list(self, email_addresses: List[str]) -> None:
        """Remove email addresses from suppression list.

        Args:
            email_addresses: List of addresses to remove from suppression
        """
        self.suppress_list.difference_update(email_addresses)
        logger.info(f"Removed {len(email_addresses)} addresses from suppression list")
