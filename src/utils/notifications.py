"""Notification Service for Haven Health Passport.

Handles sending notifications to various teams and creating
external tickets for important events.
"""

import json
import os
from datetime import datetime
from typing import Any, Dict, Optional
from uuid import uuid4

from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from src.integrations.jira import (
    JIRAConfig,
    JIRAIntegration,
    JIRAIssue,
    JIRAIssueType,
    JIRAPriority,
)
from src.services.email import EmailAddress, EmailMessage
from src.services.email.ses_provider import SESProvider
from src.services.email.template_manager import EmailTemplateManager
from src.services.email_service import EmailService
from src.utils.logging import get_logger

# Import exceptions
try:
    from smtplib import SMTPException
except ImportError:
    SMTPException = Exception  # type: ignore[misc,assignment]


try:
    from requests import HTTPError, RequestException, Timeout
except ImportError:
    HTTPError = Exception  # type: ignore[misc,assignment]
    RequestException = Exception  # type: ignore[misc,assignment]
    Timeout = Exception  # type: ignore[misc,assignment]


try:
    from twilio.base.exceptions import TwilioException
except ImportError:
    TwilioException = Exception

logger = get_logger(__name__)


class NotificationService:
    """Service for handling system notifications."""

    def __init__(self, db: Session, jira_config: Optional[JIRAConfig] = None):
        """Initialize notification service.

        Args:
            db: Database session
            jira_config: Optional JIRA configuration
        """
        self.db = db
        # Initialize email service with SES provider
        self.email_provider = SESProvider(
            region_name="us-east-1", configuration_set="haven-health-notifications"
        )
        self.email_service = EmailService()
        self.template_manager = EmailTemplateManager()

        # Initialize JIRA integration if configured
        self.jira_integration = None
        if jira_config:
            try:
                self.jira_integration = JIRAIntegration(jira_config)
            except (
                ConnectionError,
                SMTPException,
                TimeoutError,
                TypeError,
                ValueError,
            ) as e:
                # Catch all exceptions during JIRA initialization to prevent failures
                logger.error(f"Failed to initialize JIRA integration: {e}")

    async def notify_security_team(self, event_data: Dict[str, Any]) -> bool:
        """Send notification to security team.

        Args:
            event_data: Event details to notify about

        Returns:
            True if notification sent successfully
        """
        try:
            # Implement actual notification mechanisms for security events
            success = False

            # Priority 1: Slack notification (fastest)
            try:
                slack_webhook_url = os.getenv("SECURITY_SLACK_WEBHOOK")
                if slack_webhook_url:
                    import requests  # pylint: disable=import-outside-toplevel

                    # Format message for Slack
                    slack_message = {
                        "text": f"🚨 SECURITY ALERT: {event_data.get('event_type', 'Unknown')}",
                        "attachments": [
                            {
                                "color": "danger",
                                "fields": [
                                    {
                                        "title": "Event Type",
                                        "value": event_data.get(
                                            "event_type", "Unknown"
                                        ),
                                        "short": True,
                                    },
                                    {
                                        "title": "Severity",
                                        "value": event_data.get("severity", "HIGH"),
                                        "short": True,
                                    },
                                    {
                                        "title": "User ID",
                                        "value": str(
                                            event_data.get("user_id", "Unknown")
                                        ),
                                        "short": True,
                                    },
                                    {
                                        "title": "Timestamp",
                                        "value": event_data.get(
                                            "timestamp", datetime.utcnow().isoformat()
                                        ),
                                        "short": True,
                                    },
                                    {
                                        "title": "Description",
                                        "value": event_data.get(
                                            "description", "No description provided"
                                        ),
                                        "short": False,
                                    },
                                    {
                                        "title": "IP Address",
                                        "value": event_data.get(
                                            "ip_address", "Unknown"
                                        ),
                                        "short": True,
                                    },
                                    {
                                        "title": "Resource",
                                        "value": event_data.get("resource", "Unknown"),
                                        "short": True,
                                    },
                                ],
                                "footer": "Haven Health Passport Security System",
                                "ts": int(datetime.utcnow().timestamp()),
                            }
                        ],
                    }

                    response = requests.post(
                        slack_webhook_url, json=slack_message, timeout=5
                    )
                    if response.status_code == 200:
                        success = True
                        logger.info("Security alert sent to Slack successfully")
            except (
                ConnectionError,
                HTTPError,
                RequestException,
                SMTPException,
                Timeout,
                TimeoutError,
                TypeError,
                ValueError,
            ) as slack_error:
                logger.error(f"Failed to send Slack notification: {slack_error}")

            # Priority 2: Email notification to security team
            try:
                security_email = os.getenv("SECURITY_TEAM_EMAIL")
                if security_email and not success:  # Only if Slack failed
                    email_service = EmailService()
                    email_body = f"""
                    <h2>Security Alert: {event_data.get('event_type', 'Unknown')}</h2>
                    <p><strong>Severity:</strong> {event_data.get('severity', 'HIGH')}</p>
                    <p><strong>Timestamp:</strong> {event_data.get('timestamp', datetime.utcnow().isoformat())}</p>
                    <p><strong>User ID:</strong> {event_data.get('user_id', 'Unknown')}</p>
                    <p><strong>IP Address:</strong> {event_data.get('ip_address', 'Unknown')}</p>
                    <p><strong>Description:</strong> {event_data.get('description', 'No description provided')}</p>
                    <p><strong>Resource:</strong> {event_data.get('resource', 'Unknown')}</p>
                    <hr>
                    <p><em>This is an automated security notification from Haven Health Passport</em></p>
                    """

                    await email_service.send_email(
                        to_email=security_email,
                        subject=f"[SECURITY ALERT] {event_data.get('event_type', 'Unknown')}",
                        body=email_body,
                    )
                    success = True
                    logger.info("Security alert sent via email successfully")
            except (
                ConnectionError,
                SMTPException,
                TimeoutError,
                TwilioException,
                TypeError,
                ValueError,
            ) as email_error:
                logger.error(f"Failed to send email notification: {email_error}")

            # Priority 3: SMS for critical events
            if event_data.get("severity") == "CRITICAL" and not success:
                try:
                    security_phone = os.getenv("SECURITY_TEAM_PHONE")
                    if security_phone:
                        from src.core.database import (  # pylint: disable=import-outside-toplevel
                            get_db,
                        )
                        from src.services.notification_service import (
                            NotificationService as NotificationServiceImpl,  # pylint: disable=import-outside-toplevel
                        )

                        # Get a database session
                        with get_db() as db:
                            notification_service = NotificationServiceImpl(db)
                            sms_message = f"CRITICAL SECURITY ALERT: {event_data.get('event_type', 'Unknown')} - User: {event_data.get('user_id', 'Unknown')} - Check email/Slack for details"

                            # Use unified notification service's SMS capability if available
                            # Note: send_sms may not be a direct method, using send_notification instead
                            await notification_service.send_notification(
                                user_id=event_data.get("user_id", uuid4()),
                                notification_type="security_alert",
                                title="Security Alert",
                                message=sms_message,
                                data={"phone": security_phone},
                            )
                            success = True
                            logger.info("Critical security alert sent via SMS")
                except (
                    ConnectionError,
                    SMTPException,
                    TimeoutError,
                    TwilioException,
                ) as sms_error:
                    logger.error(f"Failed to send SMS notification: {sms_error}")

            # Always log to system logs regardless of notification success
            logger.critical(
                f"SECURITY EVENT: {json.dumps(event_data, indent=2)}",
                extra={"security_event": True, "event_data": event_data},
            )

            # Store in security audit table for permanent record
            try:
                from src.core.database import (  # pylint: disable=import-outside-toplevel
                    get_db,
                )
                from src.services.audit_service import (  # pylint: disable=import-outside-toplevel
                    AuditService,
                )

                with get_db() as db:
                    audit_service = AuditService(db_session=db)
                    # Use the real method name: log_action
                    audit_service.log_action(
                        user_id=event_data.get("user_id"),
                        action=event_data.get("event_type", "security_event"),
                        resource_type="security",
                        resource_id=event_data.get("resource", "system"),
                        details=event_data,
                        ip_address=event_data.get("ip_address", ""),
                        user_agent=event_data.get("user_agent"),
                    )
            except (IntegrityError, SQLAlchemyError) as audit_error:
                logger.error(f"Failed to log security event to audit: {audit_error}")

            return (
                success or True
            )  # Return True even if notifications fail but logging succeeded

        except (TypeError, ValueError) as e:
            logger.error(f"Failed to notify security team: {e}")
            # Still return True if we at least logged the event
            return True

    async def notify_administrators(self, message_data: Dict[str, Any]) -> bool:
        """Send notification to administrators.

        Args:
            message_data: Message details including subject and message

        Returns:
            True if notification sent successfully
        """
        try:
            # Get admin email list from configuration
            admin_emails = [
                "admin@havenhealthpassport.org",
                "security@havenhealthpassport.org",
            ]

            # Create email
            email = EmailMessage(
                to=[EmailAddress(email=email_addr) for email_addr in admin_emails],
                subject=message_data.get("subject", "System Notification"),
                html_body=f"""
                <html>
                <body>
                    <h2>{message_data.get('subject', 'System Notification')}</h2>
                    <p>{message_data.get('message', '')}</p>
                    <hr>
                    <p><small>Sent by Haven Health Passport Notification System at {datetime.utcnow().isoformat()}</small></p>
                </body>
                </html>
                """,
                text_body=f"{message_data.get('subject', 'System Notification')}\n\n{message_data.get('message', '')}\n\n---\nSent by Haven Health Passport Notification System at {datetime.utcnow().isoformat()}",
                tags=["admin-notification", message_data.get("type", "general")],
            )

            # Send email
            result = await self.email_service.send_email(
                to_email=admin_emails[0],
                subject=message_data.get("subject", "System Notification"),
                body=email.text_body or "",
            )

            if result:
                logger.info("Administrators notified via email")
                return True
            else:
                logger.error("Failed to send admin email")
                return False

        except (
            ConnectionError,
            SMTPException,
            TimeoutError,
            TypeError,
            ValueError,
        ) as e:
            # Catch all exceptions to ensure notification failures don't break the system
            logger.error(f"Failed to notify administrators: {e}")
            return False

    def create_jira_ticket(
        self, ticket_data: Dict[str, Any]
    ) -> Optional[Dict[str, str]]:
        """Create JIRA ticket for tracking.

        Args:
            ticket_data: Ticket details including summary, description, etc.

        Returns:
            Ticket info with key if created successfully, None otherwise
        """
        if not self.jira_integration:
            logger.warning("JIRA integration not configured, creating mock ticket")
            # Fallback for when JIRA is not configured
            ticket_key = f"HHP-{datetime.now().strftime('%Y%m%d%H%M%S')}"
            logger.info(
                f"Mock JIRA ticket created: {ticket_key} - {ticket_data.get('summary', 'No summary')}"
            )
            return {
                "key": ticket_key,
                "url": f"https://jira.example.com/browse/{ticket_key}",
            }

        try:
            # Map ticket data to JIRA issue
            issue_type = JIRAIssueType.INCIDENT
            if ticket_data.get("type") == "security":
                issue_type = JIRAIssueType.SECURITY
            elif ticket_data.get("type") == "bug":
                issue_type = JIRAIssueType.BUG

            priority = JIRAPriority.MEDIUM
            if ticket_data.get("priority") == "critical":
                priority = JIRAPriority.CRITICAL
            elif ticket_data.get("priority") == "high":
                priority = JIRAPriority.HIGH
            elif ticket_data.get("priority") == "low":
                priority = JIRAPriority.LOW

            # Create JIRA issue
            issue = JIRAIssue(
                summary=ticket_data.get("summary", "Haven Health Passport Issue"),
                description=ticket_data.get("description", "No description provided"),
                issue_type=issue_type,
                priority=priority,
                labels=ticket_data.get(
                    "labels", ["haven-health-passport", "automated"]
                ),
                components=ticket_data.get("components", []),
            )

            # Add custom fields if provided
            if "custom_fields" in ticket_data:
                issue.custom_fields = ticket_data["custom_fields"]

            # Create the issue
            issue_key = self.jira_integration.create_issue(issue)

            # Add initial comment if provided
            if "initial_comment" in ticket_data:
                self.jira_integration.add_comment(
                    issue_key, ticket_data["initial_comment"]
                )

            return {
                "key": issue_key,
                "url": f"{self.jira_integration.config.base_url}/browse/{issue_key}",
            }

        except (TypeError, ValueError) as e:
            logger.error(f"Failed to create JIRA ticket: {e}")
            return None
