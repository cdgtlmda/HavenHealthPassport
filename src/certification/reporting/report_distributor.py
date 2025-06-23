"""Report distributor for sending certification reports to recipients."""

import asyncio
import logging
import smtplib
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import List

from .report_config import ReportConfiguration, ReportRecipient, ReportType

logger = logging.getLogger(__name__)


class ReportDistributor:
    """Handles distribution of certification reports to recipients."""

    def __init__(self, config: ReportConfiguration):
        """Initialize report distributor.

        Args:
            config: Report configuration
        """
        self.config = config

    async def distribute_reports(
        self,
        report_paths: List[Path],
        recipients: List[ReportRecipient],
        report_type: ReportType,
    ) -> None:
        """Distribute reports to recipients.

        Args:
            report_paths: List of report file paths
            recipients: List of recipients
            report_type: Type of report being distributed
        """
        if not self.config.enable_email_distribution:
            logger.info("Email distribution is disabled")
            return

        if not recipients:
            logger.info("No recipients configured for report distribution")
            return

        # Filter recipients who want this report type
        interested_recipients = [
            r
            for r in recipients
            if r.active and (not r.report_types or report_type in r.report_types)
        ]

        if not interested_recipients:
            logger.info(f"No recipients interested in {report_type.value} reports")
            return

        logger.info(
            f"Distributing {len(report_paths)} reports to {len(interested_recipients)} recipients"
        )

        # Send emails asynchronously
        tasks = []
        for recipient in interested_recipients:
            # Filter reports by recipient's preferred formats
            recipient_reports = [
                p
                for p in report_paths
                if not recipient.formats
                or any(p.suffix[1:] == fmt.value for fmt in recipient.formats)
            ]

            if recipient_reports:
                task = asyncio.create_task(
                    self._send_email_report(recipient, recipient_reports, report_type)
                )
                tasks.append(task)

        # Wait for all emails to be sent
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Log any errors
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.error(f"Failed to send report to recipient {i}: {result}")

    async def _send_email_report(
        self,
        recipient: ReportRecipient,
        report_paths: List[Path],
        report_type: ReportType,
    ) -> None:
        """Send email with report attachments.

        Args:
            recipient: Report recipient
            report_paths: List of report files to attach
            report_type: Type of report
        """
        try:
            # Create message
            msg = MIMEMultipart()
            msg["From"] = self.config.smtp_config.get(
                "from_address", "noreply@havenhealthpassport.org"
            )
            msg["To"] = recipient.email
            msg["Subject"] = (
                f"Haven Health Passport - {report_type.value.replace('_', ' ').title()} Report"
            )

            # Create email body
            body = self._create_email_body(recipient, report_type, report_paths)
            msg.attach(MIMEText(body, "html"))

            # Attach reports
            for report_path in report_paths:
                if report_path.exists():
                    self._attach_file(msg, report_path)

            # Send email
            await self._send_email(msg)

            logger.info(
                f"Successfully sent {report_type.value} report to {recipient.email}"
            )

        except Exception as e:
            logger.error(f"Failed to send email to {recipient.email}: {e}")
            raise

    def _create_email_body(
        self,
        recipient: ReportRecipient,
        report_type: ReportType,
        report_paths: List[Path],
    ) -> str:
        """Create HTML email body.

        Args:
            recipient: Report recipient
            report_type: Type of report
            report_paths: List of attached reports

        Returns:
            HTML email body
        """
        report_list = "<ul>"
        for path in report_paths:
            report_list += f"<li>{path.name}</li>"
        report_list += "</ul>"

        html = f"""
        <html>
        <body style="font-family: Arial, sans-serif;">
            <h2>Haven Health Passport Certification Report</h2>

            <p>Dear {recipient.name or 'Recipient'},</p>

            <p>Please find attached the latest <strong>{report_type.value.replace('_', ' ').title()}</strong>
            report for Haven Health Passport certification compliance.</p>

            <p><strong>Attached Reports:</strong></p>
            {report_list}

            <p>This report was automatically generated as part of our continuous compliance monitoring process.</p>

            <hr>

            <p style="font-size: 12px; color: #666;">
            This is an automated message from the Haven Health Passport Certification System.
            Please do not reply to this email. For questions or concerns, please contact the compliance team.
            </p>
        </body>
        </html>
        """

        return html

    def _attach_file(self, msg: MIMEMultipart, file_path: Path) -> None:
        """Attach a file to email message.

        Args:
            msg: Email message
            file_path: Path to file to attach
        """
        try:
            with open(file_path, "rb") as f:
                # Create attachment
                part = MIMEBase("application", "octet-stream")
                part.set_payload(f.read())
                encoders.encode_base64(part)

                # Add header
                part.add_header(
                    "Content-Disposition", f"attachment; filename= {file_path.name}"
                )

                # Attach to message
                msg.attach(part)

        except Exception as e:
            logger.error(f"Failed to attach file {file_path}: {e}")

    async def _send_email(self, msg: MIMEMultipart) -> None:
        """Send email using SMTP configuration.

        Args:
            msg: Email message to send
        """
        smtp_config = self.config.smtp_config

        # Validate SMTP configuration
        required_fields = ["host", "port", "username", "password"]
        missing_fields = [f for f in required_fields if f not in smtp_config]
        if missing_fields:
            raise ValueError(f"Missing SMTP configuration: {missing_fields}")

        # Send email in thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._send_email_sync, msg)

    def _send_email_sync(self, msg: MIMEMultipart) -> None:
        """Send email synchronously.

        Args:
            msg: Email message to send
        """
        smtp_config = self.config.smtp_config

        # Create SMTP connection
        if smtp_config.get("use_tls", True):
            server = smtplib.SMTP(smtp_config["host"], smtp_config["port"])
            server.starttls()
        else:
            server = smtplib.SMTP_SSL(smtp_config["host"], smtp_config["port"])

        try:
            # Login
            server.login(smtp_config["username"], smtp_config["password"])

            # Send email
            text = msg.as_string()
            server.sendmail(msg["From"], msg["To"], text)

        finally:
            server.quit()

    async def send_notification(
        self, recipients: List[str], subject: str, message: str
    ) -> None:
        """Send a notification email without attachments.

        Args:
            recipients: List of recipient email addresses
            subject: Email subject
            message: Email message body
        """
        if not self.config.enable_email_distribution:
            logger.info("Email distribution is disabled")
            return

        # Create recipient objects
        recipient_objects = [
            ReportRecipient(name="", email=email, active=True) for email in recipients
        ]

        # Send notifications
        tasks = []
        for recipient in recipient_objects:
            task = asyncio.create_task(
                self._send_notification_email(recipient, subject, message)
            )
            tasks.append(task)

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _send_notification_email(
        self, recipient: ReportRecipient, subject: str, message: str
    ) -> None:
        """Send a simple notification email.

        Args:
            recipient: Email recipient
            subject: Email subject
            message: Email message
        """
        try:
            msg = MIMEMultipart()
            msg["From"] = self.config.smtp_config.get(
                "from_address", "noreply@havenhealthpassport.org"
            )
            msg["To"] = recipient.email
            msg["Subject"] = f"Haven Health Passport - {subject}"

            # Create HTML body
            html = f"""
            <html>
            <body style="font-family: Arial, sans-serif;">
                <h2>Haven Health Passport Notification</h2>

                <p>{message}</p>

                <hr>

                <p style="font-size: 12px; color: #666;">
                This is an automated notification from the Haven Health Passport Certification System.
                </p>
            </body>
            </html>
            """

            msg.attach(MIMEText(html, "html"))

            await self._send_email(msg)

            logger.info(f"Successfully sent notification to {recipient.email}")

        except Exception as e:
            logger.error(f"Failed to send notification to {recipient.email}: {e}")
