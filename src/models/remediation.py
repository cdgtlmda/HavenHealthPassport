"""Remediation models for data quality and compliance issues."""

from datetime import datetime
from enum import Enum

from sqlalchemy import JSON, Column, DateTime
from sqlalchemy import Enum as SQLEnum
from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import relationship

from src.core.database import Base


class RemediationStatus(str, Enum):
    """Status of a remediation action."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class IssueType(str, Enum):
    """Types of issues that can be remediated."""

    MISSING_DATA = "missing_data"
    DATA_VALIDATION_ERROR = "data_validation_error"
    COMPLIANCE_VIOLATION = "compliance_violation"
    SECURITY_ISSUE = "security_issue"
    DUPLICATE_RECORD = "duplicate_record"
    ACCESS_CONTROL = "access_control"
    DATA_QUALITY = "data_quality"
    OTHER = "other"


class RemediationTemplate(Base):
    """Template for remediation actions."""

    __tablename__ = "remediation_templates"

    id = Column(PGUUID(as_uuid=True), primary_key=True)
    issue_type: Column[IssueType] = Column(SQLEnum(IssueType), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(String(1000))
    steps = Column(JSON)  # List of steps to perform
    automation_script = Column(String)  # Optional automation script
    estimated_effort = Column(String(50))  # e.g., "5 minutes", "1 hour"
    priority = Column(String(20))  # critical, high, medium, low
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class RemediationAction(Base):
    """Record of a remediation action taken."""

    __tablename__ = "remediation_actions"

    id = Column(PGUUID(as_uuid=True), primary_key=True)
    resource_id = Column(
        PGUUID(as_uuid=True), nullable=False
    )  # ID of affected resource
    resource_type = Column(String(50))  # Type of resource (patient, record, etc.)
    issue_type: Column[IssueType] = Column(SQLEnum(IssueType))
    template_id = Column(PGUUID(as_uuid=True), ForeignKey("remediation_templates.id"))
    user_id = Column(PGUUID(as_uuid=True), ForeignKey("user_auth.id"), nullable=False)
    status: Column[RemediationStatus] = Column(
        SQLEnum(RemediationStatus), default=RemediationStatus.PENDING
    )
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    error_message = Column(String(1000))
    result = Column(JSON)  # Details of what was done
    notes = Column(String(2000))
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    template = relationship("RemediationTemplate")
    user = relationship("UserAuth")
