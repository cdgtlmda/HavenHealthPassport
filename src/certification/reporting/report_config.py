"""Report configuration for certification compliance reporting."""

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..evidence.evidence_package import CertificationStandard


class ReportFormat(Enum):
    """Supported report output formats."""

    PDF = "pdf"
    HTML = "html"
    EXCEL = "excel"
    CSV = "csv"
    JSON = "json"
    MARKDOWN = "markdown"
    XML = "xml"
    DOCX = "docx"


class ReportFrequency(Enum):
    """Report generation frequency options."""

    DAILY = "daily"
    WEEKLY = "weekly"
    BIWEEKLY = "biweekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    ANNUALLY = "annually"
    ON_DEMAND = "on_demand"
    REAL_TIME = "real_time"


class ReportType(Enum):
    """Types of certification reports."""

    COMPLIANCE_SUMMARY = "compliance_summary"
    EVIDENCE_INVENTORY = "evidence_inventory"
    GAP_ANALYSIS = "gap_analysis"
    AUDIT_TRAIL = "audit_trail"
    PERFORMANCE_METRICS = "performance_metrics"
    RISK_ASSESSMENT = "risk_assessment"
    INCIDENT_REPORT = "incident_report"
    CERTIFICATION_STATUS = "certification_status"
    REQUIREMENT_TRACKING = "requirement_tracking"
    EVIDENCE_VALIDATION = "evidence_validation"


@dataclass
class ReportRecipient:
    """Configuration for report recipient."""

    name: str
    email: str
    role: str = ""
    report_types: List[ReportType] = field(default_factory=list)
    formats: List[ReportFormat] = field(default_factory=list)
    active: bool = True

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "email": self.email,
            "role": self.role,
            "report_types": [rt.value for rt in self.report_types],
            "formats": [f.value for f in self.formats],
            "active": self.active,
        }


@dataclass
class ReportSchedule:
    """Schedule configuration for automated report generation."""

    report_type: ReportType
    frequency: ReportFrequency
    day_of_week: Optional[int] = None  # 0=Monday, 6=Sunday
    day_of_month: Optional[int] = None  # 1-31
    time_of_day: str = "09:00"  # HH:MM format
    timezone: str = "UTC"
    active: bool = True
    last_run: Optional[datetime] = None
    next_run: Optional[datetime] = None

    def calculate_next_run(self) -> datetime:
        """Calculate next scheduled run time."""
        now = datetime.utcnow()

        if self.frequency == ReportFrequency.DAILY:
            next_run = now + timedelta(days=1)
        elif self.frequency == ReportFrequency.WEEKLY:
            days_ahead = (self.day_of_week or 0) - now.weekday()
            if days_ahead <= 0:
                days_ahead += 7
            next_run = now + timedelta(days=days_ahead)
        elif self.frequency == ReportFrequency.BIWEEKLY:
            next_run = now + timedelta(weeks=2)
        elif self.frequency == ReportFrequency.MONTHLY:
            # Calculate next month's date
            if now.month == 12:
                next_run = now.replace(
                    year=now.year + 1, month=1, day=self.day_of_month or 1
                )
            else:
                next_run = now.replace(month=now.month + 1, day=self.day_of_month or 1)
        elif self.frequency == ReportFrequency.QUARTERLY:
            next_run = now + timedelta(days=90)
        elif self.frequency == ReportFrequency.ANNUALLY:
            next_run = now.replace(year=now.year + 1)
        else:
            next_run = now

        # Set time
        hour, minute = map(int, self.time_of_day.split(":"))
        next_run = next_run.replace(hour=hour, minute=minute, second=0, microsecond=0)

        self.next_run = next_run
        return next_run

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "report_type": self.report_type.value,
            "frequency": self.frequency.value,
            "day_of_week": self.day_of_week,
            "day_of_month": self.day_of_month,
            "time_of_day": self.time_of_day,
            "timezone": self.timezone,
            "active": self.active,
            "last_run": self.last_run.isoformat() if self.last_run else None,
            "next_run": self.next_run.isoformat() if self.next_run else None,
        }


@dataclass
class ReportTemplate:
    """Template configuration for report generation."""

    name: str
    report_type: ReportType
    template_path: Path
    format: ReportFormat
    sections: List[str] = field(default_factory=list)
    parameters: Dict[str, Any] = field(default_factory=dict)
    custom_css: Optional[str] = None
    custom_headers: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "report_type": self.report_type.value,
            "template_path": str(self.template_path),
            "format": self.format.value,
            "sections": self.sections,
            "parameters": self.parameters,
            "custom_css": self.custom_css,
            "custom_headers": self.custom_headers,
        }


@dataclass
class ReportConfiguration:
    """Main configuration for certification reporting tools."""

    id: str = field(default_factory=lambda: datetime.utcnow().strftime("%Y%m%d_%H%M%S"))
    name: str = "Certification Reporting Configuration"
    certification_standards: List[CertificationStandard] = field(default_factory=list)
    output_directory: Path = Path("certification/reports")
    archive_directory: Path = Path("certification/reports/archive")
    retention_days: int = 365

    # Report types configuration
    enabled_report_types: List[ReportType] = field(default_factory=list)
    default_formats: List[ReportFormat] = field(
        default_factory=lambda: [ReportFormat.PDF, ReportFormat.HTML]
    )

    # Templates
    templates: Dict[str, ReportTemplate] = field(default_factory=dict)

    # Scheduling
    schedules: List[ReportSchedule] = field(default_factory=list)
    enable_scheduling: bool = True

    # Distribution
    recipients: List[ReportRecipient] = field(default_factory=list)
    smtp_config: Dict[str, Any] = field(default_factory=dict)
    enable_email_distribution: bool = False

    # Dashboard configuration
    dashboard_enabled: bool = True
    dashboard_port: int = 8080
    dashboard_refresh_interval: int = 300  # seconds

    # Performance settings
    max_concurrent_reports: int = 3
    report_timeout: int = 300  # seconds
    enable_caching: bool = True
    cache_ttl: int = 3600  # seconds

    # Compliance settings
    include_evidence_validation: bool = True
    include_gap_analysis: bool = True
    include_recommendations: bool = True

    # Metadata
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def add_schedule(self, schedule: ReportSchedule) -> None:
        """Add a report schedule."""
        schedule.calculate_next_run()
        self.schedules.append(schedule)
        self.updated_at = datetime.utcnow()

    def add_recipient(self, recipient: ReportRecipient) -> None:
        """Add a report recipient."""
        self.recipients.append(recipient)
        self.updated_at = datetime.utcnow()

    def add_template(self, template: ReportTemplate) -> None:
        """Add a report template."""
        self.templates[template.name] = template
        self.updated_at = datetime.utcnow()

    def get_schedules_by_type(self, report_type: ReportType) -> List[ReportSchedule]:
        """Get all schedules for a specific report type."""
        return [s for s in self.schedules if s.report_type == report_type and s.active]

    def get_recipients_for_report(
        self, report_type: ReportType
    ) -> List[ReportRecipient]:
        """Get recipients who should receive a specific report type."""
        return [
            r
            for r in self.recipients
            if r.active and (not r.report_types or report_type in r.report_types)
        ]

    def get_templates_for_type(self, report_type: ReportType) -> List[ReportTemplate]:
        """Get all templates for a specific report type."""
        return [t for t in self.templates.values() if t.report_type == report_type]

    def validate_configuration(self) -> List[str]:
        """Validate the report configuration."""
        issues = []

        # Check output directories
        if not self.output_directory.exists():
            issues.append(f"Output directory does not exist: {self.output_directory}")

        # Check SMTP configuration if email is enabled
        if self.enable_email_distribution:
            required_smtp_fields = ["host", "port", "username", "password"]
            missing_fields = [
                f for f in required_smtp_fields if f not in self.smtp_config
            ]
            if missing_fields:
                issues.append(f"Missing SMTP configuration fields: {missing_fields}")

        # Check template paths
        for template in self.templates.values():
            if not template.template_path.exists():
                issues.append(f"Template file not found: {template.template_path}")

        # Check schedule conflicts
        for i, schedule1 in enumerate(self.schedules):
            for schedule2 in self.schedules[i + 1 :]:
                if (
                    schedule1.report_type == schedule2.report_type
                    and schedule1.frequency == schedule2.frequency
                    and schedule1.time_of_day == schedule2.time_of_day
                    and schedule1.active
                    and schedule2.active
                ):
                    issues.append(
                        f"Duplicate schedule for {schedule1.report_type.value} "
                        f"at {schedule1.frequency.value} frequency"
                    )

        return issues

    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "certification_standards": [
                cs.value for cs in self.certification_standards
            ],
            "output_directory": str(self.output_directory),
            "archive_directory": str(self.archive_directory),
            "retention_days": self.retention_days,
            "enabled_report_types": [rt.value for rt in self.enabled_report_types],
            "default_formats": [f.value for f in self.default_formats],
            "templates": {k: v.to_dict() for k, v in self.templates.items()},
            "schedules": [s.to_dict() for s in self.schedules],
            "recipients": [r.to_dict() for r in self.recipients],
            "smtp_config": self.smtp_config,
            "enable_email_distribution": self.enable_email_distribution,
            "dashboard_enabled": self.dashboard_enabled,
            "dashboard_port": self.dashboard_port,
            "dashboard_refresh_interval": self.dashboard_refresh_interval,
            "max_concurrent_reports": self.max_concurrent_reports,
            "report_timeout": self.report_timeout,
            "enable_caching": self.enable_caching,
            "cache_ttl": self.cache_ttl,
            "include_evidence_validation": self.include_evidence_validation,
            "include_gap_analysis": self.include_gap_analysis,
            "include_recommendations": self.include_recommendations,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    def save_to_file(self, file_path: Path) -> None:
        """Save configuration to JSON file."""
        with open(file_path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def load_from_file(cls, file_path: Path) -> "ReportConfiguration":
        """Load configuration from JSON file."""
        with open(file_path, "r") as f:
            data = json.load(f)

        # Reconstruct configuration
        config = cls(
            id=data["id"],
            name=data["name"],
            certification_standards=[
                CertificationStandard(cs) for cs in data["certification_standards"]
            ],
            output_directory=Path(data["output_directory"]),
            archive_directory=Path(data["archive_directory"]),
            retention_days=data["retention_days"],
            enabled_report_types=[
                ReportType(rt) for rt in data["enabled_report_types"]
            ],
            default_formats=[ReportFormat(f) for f in data["default_formats"]],
            enable_scheduling=data.get("enable_scheduling", True),
            smtp_config=data.get("smtp_config", {}),
            enable_email_distribution=data.get("enable_email_distribution", False),
            dashboard_enabled=data.get("dashboard_enabled", True),
            dashboard_port=data.get("dashboard_port", 8080),
            dashboard_refresh_interval=data.get("dashboard_refresh_interval", 300),
            max_concurrent_reports=data.get("max_concurrent_reports", 3),
            report_timeout=data.get("report_timeout", 300),
            enable_caching=data.get("enable_caching", True),
            cache_ttl=data.get("cache_ttl", 3600),
            include_evidence_validation=data.get("include_evidence_validation", True),
            include_gap_analysis=data.get("include_gap_analysis", True),
            include_recommendations=data.get("include_recommendations", True),
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
        )

        # Reconstruct templates
        for name, template_data in data.get("templates", {}).items():
            template = ReportTemplate(
                name=template_data["name"],
                report_type=ReportType(template_data["report_type"]),
                template_path=Path(template_data["template_path"]),
                format=ReportFormat(template_data["format"]),
                sections=template_data.get("sections", []),
                parameters=template_data.get("parameters", {}),
                custom_css=template_data.get("custom_css"),
                custom_headers=template_data.get("custom_headers", {}),
            )
            config.templates[name] = template

        # Reconstruct schedules
        for schedule_data in data.get("schedules", []):
            schedule = ReportSchedule(
                report_type=ReportType(schedule_data["report_type"]),
                frequency=ReportFrequency(schedule_data["frequency"]),
                day_of_week=schedule_data.get("day_of_week"),
                day_of_month=schedule_data.get("day_of_month"),
                time_of_day=schedule_data.get("time_of_day", "09:00"),
                timezone=schedule_data.get("timezone", "UTC"),
                active=schedule_data.get("active", True),
                last_run=(
                    datetime.fromisoformat(schedule_data["last_run"])
                    if schedule_data.get("last_run")
                    else None
                ),
                next_run=(
                    datetime.fromisoformat(schedule_data["next_run"])
                    if schedule_data.get("next_run")
                    else None
                ),
            )
            config.schedules.append(schedule)

        # Reconstruct recipients
        for recipient_data in data.get("recipients", []):
            recipient = ReportRecipient(
                name=recipient_data["name"],
                email=recipient_data["email"],
                role=recipient_data.get("role", ""),
                report_types=[
                    ReportType(rt) for rt in recipient_data.get("report_types", [])
                ],
                formats=[ReportFormat(f) for f in recipient_data.get("formats", [])],
                active=recipient_data.get("active", True),
            )
            config.recipients.append(recipient)

        return config
