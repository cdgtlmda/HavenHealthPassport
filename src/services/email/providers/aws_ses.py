"""AWS SES email provider implementation."""

import json
import os
from datetime import datetime
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Dict, List, Optional

import boto3
import requests
from botocore.exceptions import ClientError
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.x509 import load_pem_x509_certificate

from src.utils.logging import get_logger

from .base import (
    BounceNotification,
    ComplaintNotification,
    EmailMessage,
    EmailProvider,
    EmailResult,
    EmailStatus,
)

logger = get_logger(__name__)


class AWSSESProvider(EmailProvider):
    """AWS Simple Email Service provider."""

    def __init__(
        self, region: Optional[str] = None, configuration_set: Optional[str] = None
    ):
        """Initialize AWS SES provider.

        Args:
            region: AWS region (defaults to env var or us-east-1)
            configuration_set: SES configuration set for tracking
        """
        self.region = region or os.getenv("AWS_REGION", "us-east-1")
        self.configuration_set = configuration_set or os.getenv("SES_CONFIGURATION_SET")

        try:
            self.ses_client = boto3.client("ses", region_name=self.region)
            self.sesv2_client = boto3.client("sesv2", region_name=self.region)
        except Exception as e:
            logger.error(f"Failed to initialize AWS SES clients: {e}")
            raise

    def get_provider_name(self) -> str:
        """Get provider name."""
        return "AWS SES"

    async def test_connection(self) -> bool:
        """Test AWS SES connection."""
        try:
            # Try to get send quota
            response = self.ses_client.get_send_quota()
            logger.info(f"AWS SES quota: {response}")
            return True
        except (ClientError, ValueError, RuntimeError) as e:
            logger.error(f"AWS SES connection test failed: {e}")
            return False

    def _build_ses_message(self, message: EmailMessage) -> Dict[str, Any]:
        """Build SES message format from EmailMessage."""
        # Build destination
        destination = {"ToAddresses": [str(addr) for addr in message.to]}
        if message.cc:
            destination["CcAddresses"] = [str(addr) for addr in message.cc]
        if message.bcc:
            destination["BccAddresses"] = [str(addr) for addr in message.bcc]

        # Build message body
        body = {}
        if message.text_body:
            body["Text"] = {"Data": message.text_body, "Charset": "UTF-8"}
        if message.html_body:
            body["Html"] = {"Data": message.html_body, "Charset": "UTF-8"}

        # Build complete message
        ses_message = {
            "Subject": {"Data": message.subject, "Charset": "UTF-8"},
            "Body": body,
        }

        # Build parameters
        params: Dict[str, Any] = {
            "Source": (
                str(message.from_address)
                if message.from_address
                else os.getenv("FROM_EMAIL", "noreply@havenhealthpassport.org")
            ),
            "Destination": destination,
            "Message": ses_message,
        }

        # Add optional parameters
        if message.reply_to:
            params["ReplyToAddresses"] = [str(message.reply_to)]

        if self.configuration_set:
            params["ConfigurationSetName"] = self.configuration_set

        if message.tags:
            params["Tags"] = [{"Name": tag, "Value": "true"} for tag in message.tags]

        return params

    async def send_email(self, message: EmailMessage) -> EmailResult:
        """Send email via AWS SES."""
        try:
            if message.template_id:
                # Use template
                params = {
                    "Source": (
                        str(message.from_address)
                        if message.from_address
                        else os.getenv("FROM_EMAIL")
                    ),
                    "Template": message.template_id,
                    "Destination": {"ToAddresses": [str(addr) for addr in message.to]},
                    "TemplateData": json.dumps(message.template_params or {}),
                }
                if self.configuration_set:
                    params["ConfigurationSetName"] = self.configuration_set

                response = self.ses_client.send_templated_email(**params)
            else:
                # Regular email
                params = self._build_ses_message(message)

                # Handle attachments if present
                if message.attachments:
                    # Need to use send_raw_email for attachments
                    msg = MIMEMultipart("mixed")
                    msg["Subject"] = message.subject
                    msg["From"] = str(params["Source"])
                    destination = params["Destination"]
                    if isinstance(destination, dict) and "ToAddresses" in destination:
                        msg["To"] = ", ".join(destination["ToAddresses"])

                    # Add body
                    if message.html_body and message.text_body:
                        body = MIMEMultipart("alternative")
                        body.attach(MIMEText(message.text_body, "plain"))
                        body.attach(MIMEText(message.html_body, "html"))
                        msg.attach(body)
                    elif message.html_body:
                        msg.attach(MIMEText(message.html_body, "html"))
                    elif message.text_body:
                        msg.attach(MIMEText(message.text_body, "plain"))

                    # Add attachments
                    for attachment in message.attachments:
                        part = MIMEBase("application", "octet-stream")
                        part.set_payload(attachment.content)
                        encoders.encode_base64(part)
                        part.add_header(
                            "Content-Disposition",
                            f"attachment; filename={attachment.filename}",
                        )
                        if attachment.content_id:
                            part.add_header("Content-ID", f"<{attachment.content_id}>")
                        msg.attach(part)

                    # Send raw email
                    response = self.ses_client.send_raw_email(
                        Source=str(params["Source"]),
                        Destinations=(
                            destination["ToAddresses"]
                            if isinstance(destination, dict)
                            else []
                        ),
                        RawMessage={"Data": msg.as_string()},
                    )
                else:
                    response = self.ses_client.send_email(**params)

            return EmailResult(
                message_id=response["MessageId"],
                status=EmailStatus.SENT,
                timestamp=datetime.utcnow(),
                provider=self.get_provider_name(),
                raw_response=response,
            )

        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            error_message = e.response["Error"]["Message"]

            logger.error(f"AWS SES send failed: {error_code} - {error_message}")

            return EmailResult(
                message_id="",
                status=EmailStatus.FAILED,
                timestamp=datetime.utcnow(),
                provider=self.get_provider_name(),
                error_message=f"{error_code}: {error_message}",
                raw_response=e.response,
            )

        except (ValueError, AttributeError, RuntimeError) as e:
            logger.error(f"Unexpected error sending email: {e}")
            return EmailResult(
                message_id="",
                status=EmailStatus.FAILED,
                timestamp=datetime.utcnow(),
                provider=self.get_provider_name(),
                error_message=str(e),
            )

    async def send_bulk_emails(self, messages: List[EmailMessage]) -> List[EmailResult]:
        """Send multiple emails efficiently."""
        # SES doesn't have a specific bulk API, but we can optimize by reusing connection
        results = []
        for message in messages:
            result = await self.send_email(message)
            results.append(result)
        return results

    async def get_email_status(self, message_id: str) -> Optional[EmailStatus]:
        """Get email status - requires CloudWatch logs or event tracking."""
        # SES doesn't provide direct status lookup
        # This would require implementing CloudWatch logs parsing or SNS event tracking
        logger.warning("Email status tracking requires CloudWatch/SNS configuration")
        return None

    async def handle_bounce(self, bounce_data: Dict[str, Any]) -> BounceNotification:
        """Process SES bounce notification."""
        # Parse SNS message if wrapped
        if "Message" in bounce_data and isinstance(bounce_data["Message"], str):
            bounce_data = json.loads(bounce_data["Message"])

        bounce = bounce_data.get("bounce", {})

        # Get first recipient (SES can have multiple)
        recipients = bounce.get("bouncedRecipients", [])
        email = recipients[0]["emailAddress"] if recipients else "unknown"

        return BounceNotification(
            message_id=bounce_data.get("mail", {}).get("messageId", ""),
            email=email,
            bounce_type=bounce.get("bounceType", "unknown"),
            bounce_subtype=bounce.get("bounceSubType"),
            timestamp=datetime.fromisoformat(
                bounce.get("timestamp", datetime.utcnow().isoformat())
            ),
            diagnostic_code=recipients[0].get("diagnosticCode") if recipients else None,
            action=recipients[0].get("action") if recipients else None,
        )

    async def handle_complaint(
        self, complaint_data: Dict[str, Any]
    ) -> ComplaintNotification:
        """Process SES complaint notification."""
        # Parse SNS message if wrapped
        if "Message" in complaint_data and isinstance(complaint_data["Message"], str):
            complaint_data = json.loads(complaint_data["Message"])

        complaint = complaint_data.get("complaint", {})

        # Get first recipient
        recipients = complaint.get("complainedRecipients", [])
        email = recipients[0]["emailAddress"] if recipients else "unknown"

        return ComplaintNotification(
            message_id=complaint_data.get("mail", {}).get("messageId", ""),
            email=email,
            complaint_type=complaint.get("complaintFeedbackType", "unknown"),
            timestamp=datetime.fromisoformat(
                complaint.get("timestamp", datetime.utcnow().isoformat())
            ),
            user_agent=complaint.get("userAgent"),
            arrival_date=(
                datetime.fromisoformat(complaint.get("arrivalDate"))
                if complaint.get("arrivalDate")
                else None
            ),
        )

    async def verify_webhook(self, headers: Dict[str, str], body: bytes) -> bool:
        """Verify SNS webhook signature."""
        # SNS webhook verification
        try:
            # Parse message
            message = json.loads(body)

            # Get certificate URL
            cert_url = message.get("SigningCertURL", "")
            if not cert_url.startswith("https://sns.") or not cert_url.endswith(
                ".amazonaws.com/"
            ):
                logger.warning(f"Invalid certificate URL: {cert_url}")
                return False

            # Download certificate
            cert_response = requests.get(cert_url, timeout=30)
            cert = load_pem_x509_certificate(cert_response.content, default_backend())

            # Build string to sign based on message type
            if message["Type"] == "Notification":
                fields = [
                    "Message",
                    "MessageId",
                    "Subject",
                    "Timestamp",
                    "TopicArn",
                    "Type",
                ]
            else:  # SubscriptionConfirmation or UnsubscribeConfirmation
                fields = [
                    "Message",
                    "MessageId",
                    "SubscribeURL",
                    "Timestamp",
                    "Token",
                    "TopicArn",
                    "Type",
                ]

            # Build canonical string
            canonical = []
            for field in fields:
                if field in message:
                    canonical.append(field)
                    canonical.append(message[field])
                    canonical.append("\n")
            canonical_string = "".join(canonical).encode("utf-8")

            # Verify signature
            # Note: SHA1 is required here for AWS SNS signature verification compatibility
            signature = message.get("Signature", "").encode("latin-1")
            public_key = cert.public_key()

            # AWS SNS uses RSA signatures
            if not isinstance(public_key, rsa.RSAPublicKey):
                logger.error("Certificate does not contain an RSA public key")
                return False

            public_key.verify(
                signature,
                canonical_string,
                padding.PKCS1v15(),
                hashes.SHA1(),  # nosec B303 - SHA1 required by AWS
            )

            return True

        except (ValueError, AttributeError, RuntimeError) as e:
            logger.error(f"SNS webhook verification failed: {e}")
            return False
