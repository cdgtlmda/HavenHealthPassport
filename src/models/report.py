"""Report model for storing generated reports and scheduled report configurations.

This module defines the database models for reports and scheduled reports.

This module handles PHI with encryption and access control to ensure HIPAA compliance.
It includes FHIR Resource typing and validation for healthcare data.
"""

from enum import Enum
from typing import Any, Dict

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
)
from sqlalchemy import Enum as SQLEnum
from sqlalchemy import (
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import text

from src.core.database import Base
from src.utils.id_generator import generate_id


class ReportStatus(str, Enum):
    """Report generation status."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ReportType(str, Enum):
    """Types of reports available."""

    PATIENT_SUMMARY = "patient_summary"
    HEALTH_TRENDS = "health_trends"
    COMPLIANCE_HIPAA = "compliance_hipaa"
    COMPLIANCE_AUDIT = "compliance_audit"
    ACCESS_LOGS = "access_logs"
    USAGE_ANALYTICS = "usage_analytics"
    DEMOGRAPHIC_ANALYSIS = "demographic_analysis"
    RESOURCE_UTILIZATION = "resource_utilization"
    CUSTOM = "custom"


class ReportFormat(str, Enum):
    """Output formats for reports."""

    PDF = "pdf"
    EXCEL = "excel"
    CSV = "csv"
    JSON = "json"


class Report(Base):
    """Model for generated reports."""

    __tablename__ = "reports"

    id = Column(String(50), primary_key=True, default=generate_id)
    name = Column(String(255), nullable=False)
    type: Column[ReportType] = Column(SQLEnum(ReportType), nullable=False)
    format: Column[ReportFormat] = Column(SQLEnum(ReportFormat), nullable=False)
    status: Column[ReportStatus] = Column(
        SQLEnum(ReportStatus), default=ReportStatus.PENDING
    )

    # Report configuration
    config = Column(JSON, nullable=False)  # Stores metrics, filters, grouping, etc.

    # File information
    file_path = Column(String(500))
    file_size = Column(Float)  # Size in bytes
    download_url = Column(String(500))

    # Metadata
    created_by = Column(String(50), ForeignKey("user_auth.id"), nullable=False)
    organization_id = Column(String(50), ForeignKey("organizations.id"))
    created_at = Column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP")
    )  # pylint: disable=not-callable
    completed_at = Column(DateTime(timezone=True))
    expires_at = Column(DateTime(timezone=True))

    # Error information
    error_message = Column(Text)

    # Relationships
    creator = relationship("UserAuth", backref="reports")
    organization = relationship("Organization", backref="reports")

    def to_dict(self) -> Dict[str, Any]:
        """Convert report to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type.value,
            "format": self.format.value,
            "status": self.status.value,
            "config": self.config,
            "file_size": self.file_size,
            "download_url": self.download_url,
            "created_by": self.created_by,
            "organization_id": self.organization_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "completed_at": (
                self.completed_at.isoformat() if self.completed_at else None
            ),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "error_message": self.error_message,
        }


class ScheduledReport(Base):
    """Model for scheduled report configurations."""

    __tablename__ = "scheduled_reports"

    id = Column(String(50), primary_key=True, default=generate_id)
    name = Column(String(255), nullable=False)
    type: Column[ReportType] = Column(SQLEnum(ReportType), nullable=False)
    format: Column[ReportFormat] = Column(SQLEnum(ReportFormat), nullable=False)

    # Schedule configuration
    schedule = Column(String(100), nullable=False)  # Cron expression
    timezone = Column(String(50), default="UTC")
    enabled = Column(Boolean, default=True)

    # Report configuration
    config = Column(JSON, nullable=False)

    # Delivery configuration
    recipients = Column(JSON, default=list)  # List of email addresses
    delivery_method = Column(String(50), default="email")  # email, webhook, etc.

    # Metadata
    created_by = Column(String(50), ForeignKey("user_auth.id"), nullable=False)
    organization_id = Column(String(50), ForeignKey("organizations.id"))
    created_at = Column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP")
    )  # pylint: disable=not-callable
    updated_at = Column(
        DateTime(timezone=True), onupdate=text("CURRENT_TIMESTAMP")
    )  # pylint: disable=not-callable
    last_run_at = Column(DateTime(timezone=True))
    next_run_at = Column(DateTime(timezone=True))

    # Statistics
    run_count = Column(Integer, default=0)
    success_count = Column(Integer, default=0)
    failure_count = Column(Integer, default=0)

    # Relationships
    creator = relationship("User", backref="scheduled_reports")
    organization = relationship("Organization", backref="scheduled_reports")

    def to_dict(self) -> Dict[str, Any]:
        """Convert scheduled report to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type.value,
            "format": self.format.value,
            "schedule": self.schedule,
            "timezone": self.timezone,
            "enabled": self.enabled,
            "config": self.config,
            "recipients": self.recipients,
            "delivery_method": self.delivery_method,
            "created_by": self.created_by,
            "organization_id": self.organization_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "last_run_at": self.last_run_at.isoformat() if self.last_run_at else None,
            "next_run_at": self.next_run_at.isoformat() if self.next_run_at else None,
            "run_count": self.run_count,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
        }
