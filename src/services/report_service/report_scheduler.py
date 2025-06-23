"""Report scheduler for managing scheduled report generation.

This module handles the scheduling and execution of periodic reports.
"""

import asyncio
import os
from datetime import datetime, timedelta
from typing import Any, List, Optional, cast

try:
    from croniter import croniter

    CRONITER_AVAILABLE = True
except ImportError:
    CRONITER_AVAILABLE = False
from sqlalchemy.orm import Session

from src.models.report import Report, ReportStatus, ScheduledReport
from src.services.email_service import EmailService
from src.utils.logging import get_logger

logger = get_logger(__name__)


class ReportScheduler:
    """Manages scheduled report generation."""

    def __init__(self, db: Session, report_service: Optional[Any] = None) -> None:
        """Initialize report scheduler.

        Args:
            db: Database session
            report_service: Optional ReportService instance to break circular dependency
        """
        self.db = db
        self._report_service = report_service
        self.email_service = EmailService()
        self.running = False

    @property
    def report_service(self) -> Any:
        """Get report service instance, creating if needed.

        This lazy initialization breaks the circular dependency.
        """
        if self._report_service is None:
            from src.services.report_service import (  # pylint: disable=import-outside-toplevel
                ReportService,
            )

            self._report_service = ReportService(self.db)
        return self._report_service

    async def start(self) -> None:
        """Start the report scheduler."""
        self.running = True
        logger.info("Report scheduler started")

        while self.running:
            try:
                await self._check_scheduled_reports()
                await asyncio.sleep(60)  # Check every minute
            except (ValueError, TypeError, IOError) as e:
                logger.error(f"Error in report scheduler: {str(e)}")
                await asyncio.sleep(60)

    def stop(self) -> None:
        """Stop the report scheduler."""
        self.running = False
        logger.info("Report scheduler stopped")

    async def _check_scheduled_reports(self) -> None:
        """Check and execute due scheduled reports."""
        now = datetime.utcnow()

        # Get enabled scheduled reports due for execution
        due_reports = (
            self.db.query(ScheduledReport)
            .filter(
                ScheduledReport.enabled.is_(True), ScheduledReport.next_run_at <= now
            )
            .all()
        )

        for scheduled_report in due_reports:
            try:
                await self._execute_scheduled_report(scheduled_report)
            except (ValueError, TypeError, IOError) as e:
                logger.error(
                    f"Failed to execute scheduled report {scheduled_report.id}: {str(e)}"
                )
                scheduled_report.failure_count = int(scheduled_report.failure_count or 0) + 1  # type: ignore[assignment]
                self.db.commit()

    async def _execute_scheduled_report(
        self, scheduled_report: ScheduledReport
    ) -> None:
        """Execute a scheduled report."""
        logger.info(f"Executing scheduled report: {scheduled_report.id}")

        try:
            # Create report
            report = await self.report_service.create_report(
                name=f"{scheduled_report.name} - {datetime.utcnow().strftime('%Y-%m-%d')}",
                report_type=scheduled_report.type,
                report_format=scheduled_report.format,
                config=scheduled_report.config,
                user_id=scheduled_report.created_by,
                organization_id=scheduled_report.organization_id,
            )

            # Wait for report generation to complete (simplified - in production use async task queue)
            max_wait = 300  # 5 minutes
            waited = 0
            while waited < max_wait:
                report_check = self.db.query(Report).filter_by(id=report.id).first()
                if report_check and report_check.status in [
                    ReportStatus.COMPLETED,
                    ReportStatus.FAILED,
                ]:
                    report = report_check
                    break
                await asyncio.sleep(5)
                waited += 5

            if report.status == ReportStatus.COMPLETED:
                # Send report to recipients
                recipients = getattr(scheduled_report, "recipients", [])
                recipients_list: List[str] = (
                    cast(List[str], recipients) if isinstance(recipients, list) else []
                )
                await self._deliver_report(report, recipients_list)

                # Update scheduled report stats
                scheduled_report.success_count = int(scheduled_report.success_count or 0) + 1  # type: ignore[assignment]
                scheduled_report.last_run_at = datetime.utcnow()  # type: ignore[assignment]
            else:
                scheduled_report.failure_count = int(scheduled_report.failure_count or 0) + 1  # type: ignore[assignment]
                logger.error(
                    f"Scheduled report {scheduled_report.id} generation failed"
                )

            # Update run count and next run time
            scheduled_report.run_count = int(scheduled_report.run_count or 0) + 1

            # Calculate next run time
            if CRONITER_AVAILABLE:
                cron = croniter(str(scheduled_report.schedule), datetime.utcnow())
                next_run_timestamp = cron.get_next()
                scheduled_report.next_run_at = datetime.fromtimestamp(
                    next_run_timestamp
                )
            else:
                # If croniter not available, schedule for tomorrow same time
                if scheduled_report.next_run_at:
                    scheduled_report.next_run_at = datetime.utcnow().replace(
                        hour=scheduled_report.next_run_at.hour,
                        minute=scheduled_report.next_run_at.minute,
                    ) + timedelta(days=1)
                else:
                    # Default to tomorrow at same time as now
                    scheduled_report.next_run_at = datetime.utcnow() + timedelta(days=1)

            self.db.commit()

        except Exception as e:
            logger.error(
                f"Error executing scheduled report {scheduled_report.id}: {str(e)}"
            )
            raise

    async def _deliver_report(self, report: Report, recipients: List[str]) -> None:
        """Deliver report to recipients."""
        if not recipients:
            return

        try:
            # Download report file
            # In production, this would download from storage service
            if report.file_path and os.path.exists(report.file_path):
                with open(report.file_path, "rb") as f:
                    file_content = f.read()

                # Send email to each recipient
                for recipient in recipients:
                    await self.email_service.send_report_email(
                        to_email=recipient,
                        report_name=str(report.name),
                        report_type=str(report.type.value if report.type else ""),
                        attachment_data=file_content,
                        attachment_name=f"{report.name}.{report.format.value if report.format else 'pdf'}",
                    )

                logger.info(
                    f"Report {report.id} delivered to {len(recipients)} recipients"
                )

        except Exception as e:
            logger.error(f"Failed to deliver report {report.id}: {str(e)}")
            raise
