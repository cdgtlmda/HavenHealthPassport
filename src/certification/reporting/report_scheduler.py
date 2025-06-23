"""Report scheduler for automated certification report generation."""

import asyncio
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from .report_config import (
    ReportConfiguration,
    ReportFrequency,
    ReportSchedule,
    ReportType,
)
from .report_distributor import ReportDistributor
from .report_generator import CertificationReportGenerator

logger = logging.getLogger(__name__)


class ReportScheduler:
    """Handles scheduling and automated generation of certification reports."""

    def __init__(self, config: ReportConfiguration, project_root: Path):
        """Initialize report scheduler.

        Args:
            config: Report configuration
            project_root: Root directory of the project
        """
        self.config = config
        self.project_root = project_root
        self.report_generator = CertificationReportGenerator(config, project_root)
        self.report_distributor = ReportDistributor(config)
        self._running = False
        self._tasks: Dict[str, asyncio.Task] = {}

    async def start(self) -> None:
        """Start the report scheduler."""
        if not self.config.enable_scheduling:
            logger.info("Report scheduling is disabled")
            return

        self._running = True
        logger.info("Starting report scheduler")

        # Schedule all active reports
        for schedule in self.config.schedules:
            if schedule.active:
                task = asyncio.create_task(self._schedule_report(schedule))
                self._tasks[
                    f"{schedule.report_type.value}_{schedule.frequency.value}"
                ] = task

        logger.info(f"Scheduled {len(self._tasks)} report tasks")

    async def stop(self) -> None:
        """Stop the report scheduler."""
        self._running = False
        logger.info("Stopping report scheduler")

        # Cancel all tasks
        for task_name, task in self._tasks.items():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                logger.debug(f"Cancelled task: {task_name}")

        self._tasks.clear()

    async def _schedule_report(self, schedule: ReportSchedule) -> None:
        """Schedule a single report for periodic generation.

        Args:
            schedule: Report schedule configuration
        """
        logger.info(
            f"Scheduling {schedule.report_type.value} report ({schedule.frequency.value})"
        )

        while self._running:
            try:
                # Calculate next run time
                next_run = schedule.calculate_next_run()

                # Wait until next run
                wait_seconds = (next_run - datetime.utcnow()).total_seconds()
                if wait_seconds > 0:
                    logger.info(
                        f"Next {schedule.report_type.value} report in {wait_seconds:.0f} seconds"
                    )
                    await asyncio.sleep(wait_seconds)

                # Check if we're still running before generating report
                # Note: _running can change during async sleep
                if self._running:
                    # Generate report
                    logger.info(
                        f"Generating scheduled {schedule.report_type.value} report"
                    )
                    report_paths = []

                    for format in self.config.default_formats:
                        try:
                            report_path = await self.report_generator.generate_report(
                                schedule.report_type, format
                            )
                            report_paths.append(report_path)
                        except Exception as e:
                            logger.error(
                                f"Failed to generate {schedule.report_type.value} report: {e}"
                            )

                    # Update schedule
                    schedule.last_run = datetime.utcnow()

                    # Distribute reports
                    if report_paths and self.config.enable_email_distribution:
                        recipients = self.config.get_recipients_for_report(
                            schedule.report_type
                        )
                        if recipients:
                            await self.report_distributor.distribute_reports(
                                report_paths, recipients, schedule.report_type
                            )

                    # Handle different frequencies
                    if schedule.frequency == ReportFrequency.ON_DEMAND:
                        # One-time report, deactivate schedule
                        schedule.active = False
                        break

            except Exception as e:
                logger.error(f"Error in scheduled report generation: {e}")
                # Wait before retrying
                await asyncio.sleep(300)  # 5 minutes

    async def generate_on_demand_report(
        self, report_type: ReportType, recipients: Optional[List[str]] = None
    ) -> List[Path]:
        """Generate a report on demand.

        Args:
            report_type: Type of report to generate
            recipients: Optional list of recipient emails

        Returns:
            List of paths to generated reports
        """
        logger.info(f"Generating on-demand {report_type.value} report")

        report_paths = []
        for format in self.config.default_formats:
            try:
                report_path = await self.report_generator.generate_report(
                    report_type, format
                )
                report_paths.append(report_path)
            except Exception as e:
                logger.error(
                    f"Failed to generate {report_type.value} report in {format.value} format: {e}"
                )

        # Distribute if recipients specified
        if report_paths and recipients:
            recipient_objects = [
                r for r in self.config.recipients if r.email in recipients
            ]
            if recipient_objects:
                await self.report_distributor.distribute_reports(
                    report_paths, recipient_objects, report_type
                )

        return report_paths

    async def run_all_scheduled_reports(self) -> Dict[str, List[Path]]:
        """Run all scheduled reports immediately.

        Returns:
            Dictionary mapping report types to generated file paths
        """
        results = {}

        for schedule in self.config.schedules:
            if schedule.active:
                try:
                    report_paths = []
                    for format in self.config.default_formats:
                        report_path = await self.report_generator.generate_report(
                            schedule.report_type, format
                        )
                        report_paths.append(report_path)

                    results[schedule.report_type.value] = report_paths

                    # Update last run time
                    schedule.last_run = datetime.utcnow()

                except Exception as e:
                    logger.error(
                        f"Failed to generate {schedule.report_type.value} report: {e}"
                    )
                    results[schedule.report_type.value] = []

        return results

    def get_schedule_status(self) -> List[Dict[str, Any]]:
        """Get status of all scheduled reports.

        Returns:
            List of schedule status information
        """
        status = []

        for schedule in self.config.schedules:
            status.append(
                {
                    "report_type": schedule.report_type.value,
                    "frequency": schedule.frequency.value,
                    "active": schedule.active,
                    "last_run": (
                        schedule.last_run.isoformat() if schedule.last_run else None
                    ),
                    "next_run": (
                        schedule.next_run.isoformat() if schedule.next_run else None
                    ),
                    "task_running": f"{schedule.report_type.value}_{schedule.frequency.value}"
                    in self._tasks,
                }
            )

        return status

    def update_schedule(
        self,
        report_type: ReportType,
        frequency: ReportFrequency,
        updates: Dict[str, Any],
    ) -> bool:
        """Update a report schedule.

        Args:
            report_type: Type of report
            frequency: Report frequency
            updates: Dictionary of updates to apply

        Returns:
            True if schedule was updated successfully
        """
        for schedule in self.config.schedules:
            if schedule.report_type == report_type and schedule.frequency == frequency:
                # Apply updates
                if "active" in updates:
                    schedule.active = updates["active"]
                if "time_of_day" in updates:
                    schedule.time_of_day = updates["time_of_day"]
                if "day_of_week" in updates:
                    schedule.day_of_week = updates["day_of_week"]
                if "day_of_month" in updates:
                    schedule.day_of_month = updates["day_of_month"]

                # Recalculate next run
                schedule.calculate_next_run()

                # Restart task if needed
                task_key = f"{report_type.value}_{frequency.value}"
                if task_key in self._tasks:
                    self._tasks[task_key].cancel()
                    if schedule.active and self._running:
                        self._tasks[task_key] = asyncio.create_task(
                            self._schedule_report(schedule)
                        )

                return True

        return False

    async def cleanup_old_reports(self, retention_days: Optional[int] = None) -> int:
        """Clean up old reports based on retention policy.

        Args:
            retention_days: Override configured retention days

        Returns:
            Number of reports cleaned up
        """
        retention_days = retention_days or self.config.retention_days
        cutoff_date = datetime.utcnow() - timedelta(days=retention_days)

        cleaned_count = 0

        # Check output directory
        if self.config.output_directory.exists():
            for report_file in self.config.output_directory.iterdir():
                if report_file.is_file():
                    # Check file modification time
                    mtime = datetime.fromtimestamp(report_file.stat().st_mtime)
                    if mtime < cutoff_date:
                        # Move to archive or delete
                        if self.config.archive_directory:
                            archive_path = (
                                self.config.archive_directory / report_file.name
                            )
                            archive_path.parent.mkdir(parents=True, exist_ok=True)
                            report_file.rename(archive_path)
                            logger.info(f"Archived old report: {report_file.name}")
                        else:
                            report_file.unlink()
                            logger.info(f"Deleted old report: {report_file.name}")

                        cleaned_count += 1

        logger.info(f"Cleaned up {cleaned_count} old reports")
        return cleaned_count
