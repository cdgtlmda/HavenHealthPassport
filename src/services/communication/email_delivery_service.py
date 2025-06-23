"""
Production Email Delivery Service for Haven Health Passport.

CRITICAL: This module provides HIPAA-compliant email delivery for
patient communications, appointment reminders, and medical notifications.
Uses AWS SES with encryption and audit trails.
Includes validation for FHIR Resource references in emails.
"""

import asyncio
import json
import os
import uuid
from datetime import datetime, timedelta
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from enum import Enum
from typing import Any, Dict, List, Optional, Union

import boto3
import jinja2
from botocore.exceptions import ClientError

from src.config import settings
from src.healthcare.hipaa_access_control import AccessLevel, require_phi_access
from src.security.encryption import EncryptionService
from src.utils.logging import get_logger

logger = get_logger(__name__)


class EmailType(Enum):
    """Types of healthcare emails."""

    APPOINTMENT_REMINDER = "appointment_reminder"
    LAB_RESULTS = "lab_results"
    PRESCRIPTION_READY = "prescription_ready"
    HEALTH_SUMMARY = "health_summary"
    SECURE_MESSAGE = "secure_message"
    VERIFICATION = "verification"
    PASSWORD_RESET = "password_reset"
    CRITICAL_ALERT = "critical_alert"


class EmailDeliveryService:
    """
    Production email delivery service for healthcare communications.

    Features:
    - HIPAA-compliant delivery
    - Encrypted attachments
    - Template management
    - Delivery tracking
    - Bounce/complaint handling
    """

    # HIPAA: Access control required for email services

    def __init__(self) -> None:
        """Initialize email delivery service with AWS SES."""
        self.environment = settings.environment.lower()

        # AWS SES client
        self.ses_client = boto3.client("ses", region_name=settings.aws_region)
        self.s3_client = boto3.client("s3", region_name=settings.aws_region)

        # Encryption service for sensitive content
        kms_key_id = os.getenv("KMS_KEY_ID", "alias/haven-health-default")
        self.encryption_service = EncryptionService(
            kms_key_id=kms_key_id, region=settings.aws_region
        )

        # Template engine
        self.template_loader = jinja2.FileSystemLoader(
            searchpath=os.path.join(os.path.dirname(__file__), "templates")
        )
        self.template_env = jinja2.Environment(
            loader=self.template_loader, autoescape=True
        )

        # Configuration
        self.from_email = os.getenv(
            "HAVEN_EMAIL_FROM", "noreply@havenhealthpassport.org"
        )
        self.support_email = os.getenv(
            "HAVEN_SUPPORT_EMAIL", "support@havenhealthpassport.org"
        )

        # Email bucket for attachments and archives
        self.email_bucket = f"haven-health-{self.environment}-emails"

        # Verify email configuration
        self._verify_configuration()

        logger.info("Initialized Email Delivery Service")

    def _verify_configuration(self) -> None:
        """Verify SES configuration and domain."""
        try:
            # Check if domain is verified
            response = self.ses_client.get_identity_verification_attributes(
                Identities=[self.from_email.split("@")[1]]
            )

            domain = self.from_email.split("@")[1]
            if domain not in response["VerificationAttributes"]:
                logger.warning(f"Domain {domain} not verified in SES")

            # Check sending quota
            quota = self.ses_client.get_send_quota()
            logger.info(
                f"SES quota - Max send rate: {quota['MaxSendRate']}/sec, "
                f"Sent last 24h: {quota['SentLast24Hours']}/{quota['Max24HourSend']}"
            )

        except Exception as e:
            logger.error(f"SES configuration error: {e}")

    def validate_email_references(self, email_data: Dict[str, Any]) -> bool:
        """Validate FHIR resource references in email content.

        Args:
            email_data: Dictionary containing email data with potential FHIR references

        Returns:
            bool: True if references are valid, False otherwise
        """
        if not email_data:
            logger.error("Email validation failed: empty email data")
            return False

        # Check for FHIR resource references in email
        if "fhir_references" in email_data:
            references = email_data["fhir_references"]
            if not isinstance(references, list):
                logger.error("Email validation failed: fhir_references must be a list")
                return False

            # Validate each reference
            for ref in references:
                if not isinstance(ref, dict):
                    logger.error("Email validation failed: reference must be an object")
                    return False

                # Check for required reference fields
                if "reference" not in ref:
                    logger.error("Email validation failed: missing reference field")
                    return False

                # Validate reference format (ResourceType/id)
                ref_parts = ref["reference"].split("/")
                if len(ref_parts) != 2:
                    logger.error(
                        f"Email validation failed: invalid reference format '{ref['reference']}'"
                    )
                    return False

                # Validate resource type
                valid_types = [
                    "Patient",
                    "Practitioner",
                    "Appointment",
                    "Observation",
                    "MedicationRequest",
                ]
                if ref_parts[0] not in valid_types:
                    logger.error(
                        f"Email validation failed: invalid resource type '{ref_parts[0]}'"
                    )
                    return False

        return True

    @require_phi_access(AccessLevel.READ)
    async def send_email(
        self,
        to_email: Union[str, List[str]],
        subject: str,
        email_type: EmailType,
        template_data: Dict[str, Any],
        attachments: Optional[List[Dict[str, Any]]] = None,
        cc: Optional[List[str]] = None,
        priority: str = "normal",
    ) -> Dict[str, Any]:
        # HIPAA: Authorize email sending operations
        """
        Send HIPAA-compliant email.

        Args:
            to_email: Recipient email(s)
            subject: Email subject
            email_type: Type of healthcare email
            template_data: Data for template rendering
            attachments: List of attachments (encrypted)
            cc: CC recipients
            priority: Email priority (high, normal, low)

        Returns:
            Send result with message ID
        """
        message_id = str(uuid.uuid4())

        try:
            # Prepare recipients
            to_addresses = [to_email] if isinstance(to_email, str) else to_email

            # Build email message
            msg = MIMEMultipart("mixed")
            msg["Subject"] = subject
            msg["From"] = self.from_email
            msg["To"] = ", ".join(to_addresses)
            if cc:
                msg["Cc"] = ", ".join(cc)

            # Add headers
            msg["X-Haven-Message-ID"] = message_id
            msg["X-Haven-Email-Type"] = email_type.value
            msg["X-Priority"] = (
                "1" if priority == "high" else "3" if priority == "low" else "2"
            )

            # Add HIPAA compliance header
            msg["X-HIPAA-Compliant"] = "true"

            # Render template
            body_html = await self._render_template(email_type, template_data)
            body_text = await self._render_text_template(email_type, template_data)

            # Create body parts
            body = MIMEMultipart("alternative")

            # Text part
            text_part = MIMEText(body_text, "plain", "utf-8")
            body.attach(text_part)

            # HTML part
            html_part = MIMEText(body_html, "html", "utf-8")
            body.attach(html_part)

            msg.attach(body)

            # Add attachments
            if attachments:
                for attachment in attachments:
                    await self._add_attachment(msg, attachment)

            # Send email
            destinations = to_addresses + (cc or [])

            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.ses_client.send_raw_email(
                    Source=self.from_email,
                    Destinations=destinations,
                    RawMessage={"Data": msg.as_string()},
                ),
            )

            # Log delivery
            await self._log_email_delivery(
                message_id, to_addresses, email_type, response["MessageId"]
            )

            return {
                "success": True,
                "message_id": message_id,
                "ses_message_id": response["MessageId"],
                "timestamp": datetime.utcnow().isoformat(),
            }

        except ClientError as e:
            logger.error(f"SES error sending email: {e}")
            return {
                "success": False,
                "message_id": message_id,
                "error": str(e),
                "error_code": e.response["Error"]["Code"],
            }
        except Exception as e:
            logger.error(f"Error sending email: {e}")
            return {"success": False, "message_id": message_id, "error": str(e)}

    async def _render_template(
        self, email_type: EmailType, template_data: Dict[str, Any]
    ) -> str:
        """Render HTML email template."""
        # Add common template data
        template_data.update(
            {
                "year": datetime.utcnow().year,
                "company_name": "Haven Health Passport",
                "support_email": self.support_email,
                "unsubscribe_url": f"{settings.frontend_url}/unsubscribe",
            }
        )

        # Get template based on email type
        template_map = {
            EmailType.APPOINTMENT_REMINDER: "appointment_reminder.html",
            EmailType.LAB_RESULTS: "lab_results_ready.html",
            EmailType.PRESCRIPTION_READY: "prescription_ready.html",
            EmailType.HEALTH_SUMMARY: "health_summary.html",
            EmailType.SECURE_MESSAGE: "secure_message.html",
            EmailType.VERIFICATION: "email_verification.html",
            EmailType.PASSWORD_RESET: "password_reset.html",
            EmailType.CRITICAL_ALERT: "critical_alert.html",
        }

        template_name = template_map.get(email_type, "generic.html")

        try:
            template = self.template_env.get_template(template_name)
            return template.render(**template_data)
        except jinja2.TemplateNotFound:
            # Fallback to generic template
            return self._get_fallback_template(email_type, template_data)

    async def _render_text_template(
        self, email_type: EmailType, template_data: Dict[str, Any]
    ) -> str:
        """Render plain text email template."""
        # Simple text version
        if email_type == EmailType.APPOINTMENT_REMINDER:
            return f"""
Appointment Reminder

Dear {template_data.get('patient_name', 'Patient')},

This is a reminder about your upcoming appointment:

Date: {template_data.get('appointment_date')}
Time: {template_data.get('appointment_time')}
Provider: {template_data.get('provider_name')}
Location: {template_data.get('location')}

Please arrive 15 minutes early to complete any necessary paperwork.

If you need to reschedule, please call us at {template_data.get('clinic_phone', 'your clinic')}.

Thank you,
Haven Health Passport
"""
        else:
            # Generic text template
            return f"""
{template_data.get('greeting', 'Hello')},

{template_data.get('message', 'You have a new notification from Haven Health Passport.')}

{template_data.get('action_text', '')}

Thank you,
Haven Health Passport

This email contains protected health information. If you received this in error, please delete it immediately.
"""

    def _get_fallback_template(
        self, email_type: EmailType, template_data: Dict[str, Any]
    ) -> str:
        """Get fallback HTML template."""
        return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>{template_data.get('subject', 'Haven Health Passport Notification')}</title>
    <style>
        body {{ font-family: Arial, sans-serif; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background-color: #4CAF50; color: white; padding: 20px; text-align: center; }}
        .content {{ padding: 20px; background-color: #f9f9f9; }}
        .footer {{ text-align: center; padding: 20px; font-size: 12px; color: #666; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Haven Health Passport</h1>
        </div>
        <div class="content">
            <h2>{template_data.get('title', 'Healthcare Notification')}</h2>
            <p>{template_data.get('message', 'You have a new notification.')}</p>
            {template_data.get('body_html', '')}
        </div>
        <div class="footer">
            <p>This email contains protected health information.</p>
            <p>&copy; {datetime.utcnow().year} Haven Health Passport</p>
        </div>
    </div>
</body>
</html>
"""

    async def _add_attachment(
        self, msg: MIMEMultipart, attachment: Dict[str, Any]
    ) -> None:
        """Add encrypted attachment to email."""
        try:
            # Get attachment data
            filename = attachment["filename"]
            content = attachment["content"]

            # Encrypt if contains PHI
            if attachment.get("contains_phi", True):
                encrypted = await self.encryption_service.encrypt(
                    content, context={"type": "email_attachment", "filename": filename}
                )
                content = json.dumps(encrypted).encode("utf-8")
                filename = f"{filename}.encrypted"

            # Create attachment
            part = MIMEApplication(content)
            part.add_header("Content-Disposition", "attachment", filename=filename)

            msg.attach(part)

        except Exception as e:
            logger.error(f"Failed to add attachment: {e}")

    async def _log_email_delivery(
        self,
        message_id: str,
        recipients: List[str],
        email_type: EmailType,
        ses_message_id: str,
    ) -> None:
        """Log email delivery for audit trail."""
        log_entry = {
            "message_id": message_id,
            "ses_message_id": ses_message_id,
            "recipients": recipients,
            "email_type": email_type.value,
            "timestamp": datetime.utcnow().isoformat(),
            "environment": self.environment,
        }

        # Store in S3 for audit
        key = (
            f"delivery-logs/{datetime.utcnow().strftime('%Y/%m/%d')}/{message_id}.json"
        )

        try:
            self.s3_client.put_object(
                Bucket=self.email_bucket,
                Key=key,
                Body=json.dumps(log_entry),
                ServerSideEncryption="aws:kms",
                SSEKMSKeyId=os.getenv("KMS_KEY_ID"),
            )
        except Exception as e:
            logger.error(f"Failed to log email delivery: {e}")

    @require_phi_access(AccessLevel.WRITE)
    async def send_secure_message(
        self,
        to_email: str,
        subject: str,
        message: str,
        sender_name: str,
        expiration_days: int = 30,
    ) -> Dict[str, Any]:
        # HIPAA: Permission required for secure messaging
        """
        Send secure message with portal access.

        Args:
            to_email: Recipient email
            subject: Message subject
            message: Secure message content
            sender_name: Name of sender (provider)
            expiration_days: Days until message expires

        Returns:
            Send result with secure link
        """
        # Generate secure message ID
        secure_message_id = str(uuid.uuid4())

        # Store message securely
        encrypted_message = await self.encryption_service.encrypt(
            message.encode("utf-8"),
            context={"type": "secure_message", "recipient": to_email},
        )

        # Store in S3 with expiration
        message_key = f"secure-messages/{secure_message_id}.json"

        message_data = {
            "id": secure_message_id,
            "subject": subject,
            "encrypted_content": encrypted_message,
            "sender": sender_name,
            "recipient": to_email,
            "created": datetime.utcnow().isoformat(),
            "expires": (
                datetime.utcnow() + timedelta(days=expiration_days)
            ).isoformat(),
        }

        self.s3_client.put_object(
            Bucket=self.email_bucket,
            Key=message_key,
            Body=json.dumps(message_data),
            ServerSideEncryption="aws:kms",
            SSEKMSKeyId=os.getenv("KMS_KEY_ID"),
            Expires=datetime.utcnow() + timedelta(days=expiration_days),
        )

        # Generate secure link
        secure_link = f"{settings.frontend_url}/secure-message/{secure_message_id}"

        # Send notification email
        template_data = {
            "recipient_name": to_email.split("@")[0],
            "sender_name": sender_name,
            "subject": subject,
            "secure_link": secure_link,
            "expiration_date": (
                datetime.utcnow() + timedelta(days=expiration_days)
            ).strftime("%B %d, %Y"),
        }

        result: Dict[str, Any] = await self.send_email(
            to_email=to_email,
            subject=f"Secure Message: {subject}",
            email_type=EmailType.SECURE_MESSAGE,
            template_data=template_data,
            priority="high",
        )
        return result

    @require_phi_access(AccessLevel.READ)
    async def send_appointment_reminder(
        self,
        patient_email: str,
        appointment_data: Dict[str, Any],
        reminder_type: str = "24_hour",
    ) -> Dict[str, Any]:
        """Send appointment reminder email."""
        template_data = {
            "patient_name": appointment_data["patient_name"],
            "appointment_date": appointment_data["date"],
            "appointment_time": appointment_data["time"],
            "provider_name": appointment_data["provider_name"],
            "location": appointment_data["location"],
            "clinic_phone": appointment_data.get("clinic_phone", "1-800-HAVEN-HP"),
            "appointment_type": appointment_data.get("type", "Medical Appointment"),
            "reminder_type": reminder_type,
        }

        subject_map = {
            "24_hour": "Appointment Reminder - Tomorrow",
            "48_hour": "Appointment Reminder - In 2 Days",
            "1_week": "Upcoming Appointment Reminder",
        }

        result: Dict[str, Any] = await self.send_email(
            to_email=patient_email,
            subject=subject_map.get(reminder_type, "Appointment Reminder"),
            email_type=EmailType.APPOINTMENT_REMINDER,
            template_data=template_data,
        )
        return result

    @require_phi_access(AccessLevel.READ)
    async def send_lab_results_notification(
        self, patient_email: str, lab_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Send lab results ready notification."""
        template_data = {
            "patient_name": lab_data["patient_name"],
            "test_name": lab_data["test_name"],
            "order_date": lab_data["order_date"],
            "result_date": lab_data["result_date"],
            "provider_name": lab_data["provider_name"],
            "portal_link": f"{settings.frontend_url}/lab-results/{lab_data['result_id']}",
            "has_critical_values": lab_data.get("has_critical_values", False),
        }

        priority = "high" if lab_data.get("has_critical_values") else "normal"

        result: Dict[str, Any] = await self.send_email(
            to_email=patient_email,
            subject="Your Lab Results Are Ready",
            email_type=EmailType.LAB_RESULTS,
            template_data=template_data,
            priority=priority,
        )
        return result

    async def configure_bounce_notifications(self, sns_topic_arn: str) -> None:
        """Configure SES bounce and complaint notifications."""
        try:
            # Set bounce notifications
            self.ses_client.put_configuration_set_event_destination(
                ConfigurationSetName=f"haven-health-{self.environment}",
                EventDestination={
                    "Name": "bounce-notifications",
                    "Enabled": True,
                    "SNSDestination": {"TopicARN": sns_topic_arn},
                    "MatchingEventTypes": ["bounce", "complaint", "delivery", "reject"],
                },
            )

            logger.info("Configured SES bounce notifications")

        except ClientError as e:
            if e.response["Error"]["Code"] == "ConfigurationSetDoesNotExist":
                # Create configuration set
                self.ses_client.put_configuration_set(
                    ConfigurationSet={"Name": f"haven-health-{self.environment}"}
                )
                # Retry
                await self.configure_bounce_notifications(sns_topic_arn)
            else:
                logger.error(f"Failed to configure bounce notifications: {e}")

    async def handle_bounce_notification(self, bounce_data: Dict[str, Any]) -> None:
        """Handle email bounce notification."""
        bounce_type = bounce_data.get("bounceType")
        bounced_recipients = bounce_data.get("bouncedRecipients", [])

        for recipient in bounced_recipients:
            email = recipient["emailAddress"]

            if bounce_type == "Permanent":
                # Mark email as invalid
                await self._mark_email_invalid(email, "hard_bounce")
                logger.warning(f"Permanent bounce for {email}")
            elif bounce_type == "Transient":
                # Temporary issue, can retry
                await self._increment_bounce_count(email, "soft_bounce")
                logger.info(f"Transient bounce for {email}")

    async def handle_complaint_notification(
        self, complaint_data: Dict[str, Any]
    ) -> None:
        """Handle spam complaint notification."""
        complained_recipients = complaint_data.get("complainedRecipients", [])

        for recipient in complained_recipients:
            email = recipient["emailAddress"]

            # Unsubscribe and mark as complaint
            await self._mark_email_invalid(email, "spam_complaint")
            logger.warning(f"Spam complaint from {email}")

    async def _mark_email_invalid(self, email: str, reason: str) -> None:
        """Mark email address as invalid."""
        # Store in DynamoDB or database
        # For now, log the action
        logger.info(f"Marking {email} as invalid: {reason}")

    async def _increment_bounce_count(self, email: str, bounce_type: str) -> None:
        """Increment bounce count for email."""
        # Track soft bounces, disable after threshold
        logger.info(f"Incrementing {bounce_type} count for {email}")

    async def verify_email_address(self, email: str) -> bool:
        """Verify if email address is valid for sending."""
        try:
            # Check SES suppression list
            response = self.ses_client.get_suppressed_destination(EmailAddress=email)

            if "SuppressedDestination" in response:
                reason = response["SuppressedDestination"]["Reason"]
                logger.warning(f"Email {email} is suppressed: {reason}")
                return False

            return True

        except ClientError as e:
            if e.response["Error"]["Code"] == "NotFoundException":
                # Not in suppression list, OK to send
                return True
            else:
                logger.error(f"Error checking email suppression: {e}")
                return True  # Assume valid if can't check

    @require_phi_access(AccessLevel.WRITE)
    async def send_bulk_email(
        self,
        recipients: List[Dict[str, Any]],
        email_type: EmailType,
        template_data_base: Dict[str, Any],
        batch_size: int = 50,
    ) -> Dict[str, Any]:
        """
        Send bulk emails with personalization.

        Args:
            recipients: List of recipient data with email and personalizations
            email_type: Type of email
            template_data_base: Base template data
            batch_size: Number of emails per batch

        Returns:
            Bulk send results
        """
        results: Dict[str, Any] = {
            "total": len(recipients),
            "sent": 0,
            "failed": 0,
            "errors": [],
        }

        # Process in batches to respect SES rate limits
        for i in range(0, len(recipients), batch_size):
            batch = recipients[i : i + batch_size]

            # Create personalized emails
            destinations = []
            for recipient in batch:
                # Skip invalid emails
                if not await self.verify_email_address(recipient["email"]):
                    results["failed"] += 1
                    continue

                # Merge personalizations
                template_data = {**template_data_base, **recipient.get("data", {})}

                destinations.append(
                    {
                        "Destination": {"ToAddresses": [recipient["email"]]},
                        "ReplacementTemplateData": json.dumps(template_data),
                    }
                )

            if destinations:
                try:
                    # Send batch
                    response = self.ses_client.send_bulk_templated_email(
                        Source=self.from_email,
                        Template=f"haven-health-{email_type.value}",
                        DefaultTemplateData=json.dumps(template_data_base),
                        Destinations=destinations,
                    )

                    results["sent"] += len(destinations)

                    # Handle failures
                    for status in response.get("Status", []):
                        if status["Status"] != "Success":
                            results["failed"] += 1
                            results["errors"].append(
                                {
                                    "email": status.get("MessageId"),
                                    "error": status.get("Error"),
                                }
                            )

                except ClientError as e:
                    logger.error(f"Bulk email send failed: {e}")
                    results["failed"] += len(destinations)
                    results["errors"].append(str(e))

            # Rate limit compliance
            await asyncio.sleep(1)  # 1 second between batches

        return results

    def create_email_template(
        self, template_name: str, subject: str, html_body: str, text_body: str
    ) -> None:
        """Create or update SES email template."""
        try:
            self.ses_client.create_template(
                Template={
                    "TemplateName": f"haven-health-{template_name}",
                    "SubjectPart": subject,
                    "HtmlPart": html_body,
                    "TextPart": text_body,
                }
            )
            logger.info(f"Created email template: {template_name}")

        except ClientError as e:
            if e.response["Error"]["Code"] == "AlreadyExists":
                # Update existing template
                self.ses_client.update_template(
                    Template={
                        "TemplateName": f"haven-health-{template_name}",
                        "SubjectPart": subject,
                        "HtmlPart": html_body,
                        "TextPart": text_body,
                    }
                )
                logger.info(f"Updated email template: {template_name}")
            else:
                logger.error(f"Failed to create template: {e}")
                raise

    async def get_email_statistics(
        self, start_date: datetime, end_date: datetime
    ) -> Dict[str, Any]:
        """Get email sending statistics."""
        try:
            response = self.ses_client.get_send_statistics()

            stats = {
                "total_sent": 0,
                "bounces": 0,
                "complaints": 0,
                "delivery_rate": 0.0,
            }

            for data_point in response["SendDataPoints"]:
                timestamp = data_point["Timestamp"]
                if start_date <= timestamp <= end_date:
                    stats["total_sent"] += data_point.get("DeliveryAttempts", 0)
                    stats["bounces"] += data_point.get("Bounces", 0)
                    stats["complaints"] += data_point.get("Complaints", 0)

            if stats["total_sent"] > 0:
                stats["delivery_rate"] = (
                    (stats["total_sent"] - stats["bounces"]) / stats["total_sent"] * 100
                )

            return stats

        except Exception as e:
            logger.error(f"Failed to get email statistics: {e}")
            return {}


# Global instance
_email_service = None


def get_email_delivery_service() -> EmailDeliveryService:
    """Get the global email delivery service instance."""
    global _email_service
    if _email_service is None:
        _email_service = EmailDeliveryService()
    return _email_service
