"""Email service for sending reports and notifications.

This module provides email functionality for the Haven Health Passport system.
Now uses the enhanced email service with provider abstraction, rate limiting,
templates, and tracking.
"""

import asyncio
import os
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, Optional

from src.config import get_settings
from src.services.email.enhanced_email_service import get_email_service
from src.services.email.providers import EmailAddress, EmailAttachment, EmailStatus
from src.services.email.providers.base import EmailResult
from src.utils.logging import get_logger

if TYPE_CHECKING:
    import aiosmtplib
else:
    try:
        import aiosmtplib
    except ImportError:
        aiosmtplib = None

logger = get_logger(__name__)
settings = get_settings()


class EmailService:
    """Service for sending emails - now wraps the enhanced email service."""

    def __init__(self) -> None:
        """Initialize email service."""
        # Legacy SMTP settings for backward compatibility
        self.smtp_host = os.getenv("SMTP_HOST", "localhost")
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
        self.smtp_user = os.getenv("SMTP_USER", "")
        self.smtp_password = os.getenv("SMTP_PASSWORD", "")
        self.from_email = os.getenv("FROM_EMAIL", "noreply@havenhealthpassport.org")
        self.use_tls = os.getenv("SMTP_USE_TLS", "true").lower() == "true"

        # Get enhanced email service
        self.enhanced_service = get_email_service()

    async def send_password_changed_email_async(
        self, user: Any, locale: str = "en"
    ) -> bool:
        """Send password changed notification email.

        Args:
            user: User object with email address
            locale: User's locale for template selection

        Returns:
            True if email sent successfully, False otherwise
        """
        try:
            # Use enhanced email service with template
            result = await self.enhanced_service.send_email(
                to=EmailAddress(email=user.email, name=user.name),
                template_id="password_changed",
                template_params={
                    "user_name": user.name,
                    "changed_at": datetime.utcnow().isoformat(),
                    "support_email": "support@havenhealthpassport.org",
                },
                language=locale,
                subject="Password Changed",
            )
            return result.status != EmailStatus.FAILED
        except (ValueError, AttributeError, KeyError) as e:
            logger.error(f"Failed to send password changed email: {e}")
            return False

    async def send_report_email(
        self,
        to_email: str,
        report_name: str,
        report_type: str,
        attachment_data: bytes,
        attachment_name: str,
    ) -> bool:
        """Send an email with a report attachment."""
        try:
            # Create attachment
            attachment = EmailAttachment(
                filename=attachment_name,
                content=attachment_data,
                content_type="application/octet-stream",
            )

            # Use template if available
            template_params = {
                "report_name": report_name,
                "report_type": report_type.replace("_", " ").title(),
                "generated_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
            }

            # Try to use template, fall back to inline HTML
            try:
                result = await self.enhanced_service.send_email(
                    to=to_email,
                    subject=f"Haven Health Passport - {report_name}",
                    template_id="report_ready",
                    template_params=template_params,
                    attachments=[attachment],
                    tags=["report", report_type],
                )
            except ValueError:  # Template not found
                # Fall back to inline HTML
                body = self._generate_report_email_html(report_name, report_type)

                result = await self.enhanced_service.send_email(
                    to=to_email,
                    subject=f"Haven Health Passport - {report_name}",
                    html_body=body,
                    attachments=[attachment],
                    tags=["report", report_type],
                )

            return result.status != "failed"

        except (ValueError, AttributeError, KeyError, IOError) as e:
            logger.error(f"Failed to send report email to {to_email}: {str(e)}")
            return False

    async def send_notification_email(
        self, to_email: str, subject: str, body: str, is_html: bool = False
    ) -> bool:
        """Send a simple notification email."""
        try:
            if is_html:
                result = await self.enhanced_service.send_email(
                    to=to_email, subject=subject, html_body=body, tags=["notification"]
                )
            else:
                result = await self.enhanced_service.send_email(
                    to=to_email, subject=subject, text_body=body, tags=["notification"]
                )

            return result.status != "failed"

        except (ValueError, AttributeError, KeyError) as e:
            logger.error(f"Failed to send notification email to {to_email}: {str(e)}")
            return False

    def send_verification_email(self, user_auth: Any) -> bool:
        """Send email verification to user - updated to use enhanced service.

        Args:
            user_auth: UserAuth model instance with email and verification token

        Returns:
            bool: True if email sent successfully, False otherwise
        """
        try:
            # Create verification URL
            base_url = os.getenv("FRONTEND_URL", "http://localhost:3000")
            verification_url = (
                f"{base_url}/verify-email?token={user_auth.email_verification_token}"
            )

            # Template parameters
            template_params = {
                "user_name": user_auth.username,
                "verification_url": verification_url,
            }

            # Use async in sync context
            async def _send() -> EmailResult:
                return await self.enhanced_service.send_email(
                    to=user_auth.email,
                    subject="Verify Your Haven Health Passport Email",
                    template_id="verify_email",
                    template_params=template_params,
                    tags=["verification", "registration"],
                )

            # Run async function
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            try:
                result = loop.run_until_complete(_send())
                return result.status != EmailStatus.FAILED
            finally:
                loop.close()

        except (ValueError, AttributeError, KeyError, asyncio.TimeoutError) as e:
            logger.error(
                f"Failed to send verification email to {user_auth.email}: {str(e)}"
            )
            return False

    def _generate_report_email_html(self, report_name: str, report_type: str) -> str:
        """Generate HTML for report email (fallback when template not available)."""
        return f"""
        <html>
            <body>
                <h2>Your {report_type.replace('_', ' ').title()} Report is Ready</h2>
                <p>Hello,</p>
                <p>Your requested report "{report_name}" has been generated successfully and is attached to this email.</p>
                <p>Report Details:</p>
                <ul>
                    <li>Type: {report_type.replace('_', ' ').title()}</li>
                    <li>Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}</li>
                </ul>
                <p>If you have any questions, please contact your administrator.</p>
                <p>Best regards,<br>Haven Health Passport Team</p>
            </body>
        </html>
        """

    async def send_email(
        self,
        to_email: str,
        subject: str,
        body: str,
        template_id: Optional[str] = None,
        template_params: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Send email using enhanced service - for backward compatibility.

        Args:
            to_email: Recipient email
            subject: Email subject
            body: Email body (HTML)
            template_id: Optional template ID
            template_params: Optional template parameters

        Returns:
            True if sent successfully
        """
        try:
            result = await self.enhanced_service.send_email(
                to=to_email,
                subject=subject,
                html_body=body if not template_id else None,
                template_id=template_id,
                template_params=template_params,
            )

            return result.status != "failed"

        except (ValueError, AttributeError, KeyError) as e:
            logger.error(f"Failed to send email: {e}")
            return False
