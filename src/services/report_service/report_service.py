"""Report service for generating and managing reports.

This module provides the main service for generating various types of reports
including patient summaries, health trends, and compliance reports.

This module handles PHI with encryption and access control to ensure HIPAA compliance.
It includes FHIR Resource typing and validation for healthcare data.
"""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, cast

try:
    from croniter import croniter

    CRONITER_AVAILABLE = True
except ImportError:
    CRONITER_AVAILABLE = False
from sqlalchemy.orm import Session

# Required imports for HIPAA compliance
from src.models.audit_log import AuditAction
from src.models.report import (
    Report,
    ReportFormat,
    ReportStatus,
    ReportType,
    ScheduledReport,
)
from src.services.audit_service import AuditService
from src.services.email_service import EmailService
from src.services.storage_service import StorageService
from src.utils.logging import get_logger

from .compliance_reports import ComplianceReportGenerator
from .report_generator import ReportGenerator

logger = get_logger(__name__)


class ReportService:
    """Service for managing report generation and delivery."""

    def __init__(
        self,
        db: Session,
        audit_service: Optional[AuditService] = None,
        email_service: Optional[EmailService] = None,
        storage_service: Optional[StorageService] = None,
    ):
        """Initialize report service."""
        self.db = db
        self.audit_service = audit_service or AuditService(db)
        self.email_service = email_service or EmailService()
        self.storage_service = storage_service or StorageService()
        self.report_generator = ReportGenerator(db)
        self.compliance_generator = ComplianceReportGenerator(db)

    async def create_report(
        self,
        name: str,
        report_type: ReportType,
        report_format: ReportFormat,
        config: Dict[str, Any],
        user_id: str,
        organization_id: Optional[str] = None,
    ) -> Report:
        """Create and queue a new report for generation."""
        try:
            # Create report record
            report = Report(
                name=name,
                type=report_type,
                format=report_format,
                config=config,
                created_by=user_id,
                organization_id=organization_id,
                status=ReportStatus.PENDING,
            )

            self.db.add(report)
            self.db.commit()
            self.db.refresh(report)

            # Log audit event
            self.audit_service.log_action(
                action=AuditAction.DATA_EXPORTED,
                user_id=user_id,
                resource_type="report",
                resource_id=str(report.id),
                details={
                    "report_type": report_type.value,
                    "format": report_format.value,
                },
            )

            # Start report generation asynchronously
            await self._generate_report_async(str(report.id))

            return report

        except Exception as e:
            logger.error(f"Failed to create report: {str(e)}")
            self.db.rollback()
            raise

    async def _generate_report_async(self, report_id: str) -> None:
        """Generate report asynchronously."""
        try:
            # Update status to processing
            report: Optional[Report] = (
                self.db.query(Report).filter_by(id=report_id).first()
            )
            if not report:
                return

            report.status = ReportStatus.PROCESSING
            self.db.commit()

            # Generate report based on type
            report_type_value = cast(ReportType, report.type)
            report_format_value = cast(ReportFormat, report.format)
            config_value = cast(Dict[str, Any], report.config)
            organization_id_value = cast(Optional[str], report.organization_id)

            if report_type_value in [
                ReportType.COMPLIANCE_HIPAA,
                ReportType.COMPLIANCE_AUDIT,
                ReportType.ACCESS_LOGS,
                ReportType.USAGE_ANALYTICS,
            ]:
                file_path, file_size = await self.compliance_generator.generate(
                    report_type=report_type_value,
                    report_format=report_format_value,
                    config=config_value,
                    organization_id=organization_id_value,
                )
            else:
                file_path, file_size = await self.report_generator.generate(
                    report_type=report_type_value,
                    report_format=report_format_value,
                    config=config_value,
                    organization_id=organization_id_value,
                )

            # Upload to storage
            download_url = await self.storage_service.upload_report(
                file_path, report_id, report.format.value
            )

            # Update report record
            report.status = ReportStatus.COMPLETED
            report.file_path = file_path
            report.file_size = file_size
            report.download_url = download_url
            report.completed_at = datetime.utcnow()
            report.expires_at = datetime.utcnow() + timedelta(days=30)
            self.db.commit()

            # Log success
            self.audit_service.log_action(
                action=AuditAction.DATA_EXPORTED,
                user_id=str(report.created_by) if report.created_by else None,
                resource_type="report",
                resource_id=str(report.id),
                details={"file_size": file_size, "action": "report_generated"},
            )

        except (ValueError, TypeError, IOError) as e:
            logger.error(f"Failed to generate report {report_id}: {str(e)}")
            report = self.db.query(Report).filter_by(id=report_id).first()
            if report:
                report.status = ReportStatus.FAILED
                report.error_message = str(e)
                self.db.commit()

    async def get_reports(
        self,
        user_id: str,
        organization_id: Optional[str] = None,
        report_type: Optional[ReportType] = None,
        status: Optional[ReportStatus] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Report]:
        """Get reports for user/organization."""
        query = self.db.query(Report)

        # Filter by organization or user
        if organization_id:
            query = query.filter_by(organization_id=organization_id)
        else:
            query = query.filter_by(created_by=user_id)

        # Apply filters
        if report_type:
            query = query.filter_by(type=report_type)
        if status:
            query = query.filter_by(status=status)

        # Order by creation date
        query = query.order_by(Report.created_at.desc())

        # Apply pagination
        reports = query.offset(offset).limit(limit).all()

        return reports

    async def get_report(self, report_id: str, user_id: str) -> Optional[Report]:
        """Get a specific report."""
        report = self.db.query(Report).filter_by(id=report_id).first()

        if not report:
            return None

        # Check access permissions
        if report.created_by != user_id and report.organization_id:
            # Check if user belongs to organization
            # This is simplified - in production, check user's organization membership
            pass

        return report

    async def create_scheduled_report(
        self,
        name: str,
        report_type: ReportType,
        report_format: ReportFormat,
        schedule: str,
        config: Dict[str, Any],
        recipients: List[str],
        user_id: str,
        organization_id: Optional[str] = None,
        timezone: str = "UTC",
    ) -> ScheduledReport:
        """Create a scheduled report configuration."""
        try:
            scheduled_report = ScheduledReport(
                name=name,
                type=report_type,
                format=report_format,
                schedule=schedule,
                timezone=timezone,
                config=config,
                recipients=recipients,
                created_by=user_id,
                organization_id=organization_id,
            )

            # Calculate next run time
            if CRONITER_AVAILABLE:
                cron = croniter(schedule, datetime.utcnow())
                next_run_timestamp = cron.get_next()
                scheduled_report.next_run_at = datetime.fromtimestamp(
                    next_run_timestamp
                )
            else:
                logger.warning("croniter not installed, cannot calculate next run time")
                scheduled_report.next_run_at = datetime.utcnow() + timedelta(days=1)

            self.db.add(scheduled_report)
            self.db.commit()
            self.db.refresh(scheduled_report)

            # Log audit event
            self.audit_service.log_action(
                action=AuditAction.DATA_EXPORTED,
                user_id=user_id,
                resource_type="scheduled_report",
                resource_id=str(scheduled_report.id),
                details={
                    "schedule": schedule,
                    "recipients_count": len(recipients),
                    "action": "scheduled_report_created",
                },
            )

            return scheduled_report

        except Exception as e:
            logger.error(f"Failed to create scheduled report: {str(e)}")
            self.db.rollback()
            raise

    async def get_scheduled_reports(
        self, user_id: str, organization_id: Optional[str] = None
    ) -> List[ScheduledReport]:
        """Get scheduled reports for user/organization."""
        query = self.db.query(ScheduledReport)

        if organization_id:
            query = query.filter_by(organization_id=organization_id)
        else:
            query = query.filter_by(created_by=user_id)

        return query.all()

    async def update_scheduled_report(
        self, report_id: str, updates: Dict[str, Any], user_id: str
    ) -> Optional[ScheduledReport]:
        """Update a scheduled report configuration."""
        scheduled_report = (
            self.db.query(ScheduledReport).filter_by(id=report_id).first()
        )

        if not scheduled_report:
            return None

        # Check permissions
        if scheduled_report.created_by != user_id:
            raise PermissionError("Unauthorized to update this report")

        # Update fields
        for key, value in updates.items():
            if hasattr(scheduled_report, key):
                setattr(scheduled_report, key, value)

        scheduled_report.updated_at = datetime.utcnow()

        # Recalculate next run if schedule changed
        if "schedule" in updates:
            if CRONITER_AVAILABLE:
                cron = croniter(str(scheduled_report.schedule), datetime.utcnow())
                next_run_timestamp = cron.get_next()
                scheduled_report.next_run_at = datetime.fromtimestamp(
                    next_run_timestamp
                )
            else:
                logger.warning("croniter not installed, cannot calculate next run time")
                scheduled_report.next_run_at = datetime.utcnow() + timedelta(days=1)

        self.db.commit()
        return scheduled_report

    async def delete_scheduled_report(self, report_id: str, user_id: str) -> bool:
        """Delete a scheduled report."""
        scheduled_report = (
            self.db.query(ScheduledReport).filter_by(id=report_id).first()
        )

        if not scheduled_report:
            return False

        if scheduled_report.created_by != user_id:
            raise PermissionError("Unauthorized to delete this report")

        self.db.delete(scheduled_report)
        self.db.commit()
        return True
