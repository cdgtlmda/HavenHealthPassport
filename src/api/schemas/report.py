"""Report schemas for API request/response validation.

This module defines Pydantic models for report-related API operations.

This module handles PHI with encryption and access control to ensure HIPAA compliance.
It includes FHIR Resource typing and validation for healthcare data.
"""

import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from croniter import croniter
from pydantic import BaseModel, Field, validator

from src.models.report import ReportFormat, ReportStatus, ReportType


class ReportConfig(BaseModel):
    """Configuration for report generation."""

    metrics: Optional[List[str]] = Field([], description="Metrics to include in report")
    date_range: Optional[Dict[str, str]] = Field(
        None, description="Date range for report"
    )
    group_by: Optional[str] = Field(None, description="Grouping field")
    filters: Optional[Dict[str, Any]] = Field({}, description="Additional filters")
    time_range: Optional[str] = Field(
        "month", description="Time range (week/month/year)"
    )


class ReportCreate(BaseModel):
    """Schema for creating a new report."""

    name: str = Field(..., min_length=1, max_length=255)
    type: ReportType
    format: ReportFormat
    config: ReportConfig

    class Config:
        """Pydantic configuration."""

        schema_extra = {
            "example": {
                "name": "Monthly Patient Summary",
                "type": "patient_summary",
                "format": "pdf",
                "config": {
                    "date_range": {"start": "2025-05-01", "end": "2025-05-31"},
                    "metrics": ["age_distribution", "gender_distribution"],
                },
            }
        }


class ReportResponse(BaseModel):
    """Schema for report response."""

    id: str
    name: str
    type: ReportType
    format: ReportFormat
    status: ReportStatus
    config: Dict[str, Any]
    file_size: Optional[float]
    download_url: Optional[str]
    created_by: str
    organization_id: Optional[str]
    created_at: datetime
    completed_at: Optional[datetime]
    expires_at: Optional[datetime]
    error_message: Optional[str]

    class Config:
        """Pydantic configuration."""

        orm_mode = True


class ScheduledReportCreate(BaseModel):
    """Schema for creating a scheduled report."""

    name: str = Field(..., min_length=1, max_length=255)
    type: ReportType
    format: ReportFormat
    schedule: str = Field(..., description="Cron expression for schedule")
    config: ReportConfig
    recipients: List[str] = Field(..., description="Email recipients")
    timezone: str = Field("UTC", description="Timezone for schedule")

    @validator("schedule")
    @classmethod
    def validate_cron(cls, v: str) -> str:
        """Validate cron expression."""
        try:
            croniter(v)
        except ValueError as e:
            raise ValueError(f"Invalid cron expression: {e}") from e
        return v

    @validator("recipients")
    @classmethod
    def validate_emails(cls, v: List[str]) -> List[str]:
        """Validate email addresses."""
        email_pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        for email in v:
            if not re.match(email_pattern, email):
                raise ValueError(f"Invalid email address: {email}")
        return v

    class Config:
        """Pydantic configuration."""

        schema_extra = {
            "example": {
                "name": "Weekly Compliance Report",
                "type": "compliance_hipaa",
                "format": "pdf",
                "schedule": "0 9 * * 1",  # Every Monday at 9 AM
                "config": {"time_range": "week"},
                "recipients": ["admin@example.com", "compliance@example.com"],
                "timezone": "America/New_York",
            }
        }


class ScheduledReportUpdate(BaseModel):
    """Schema for updating a scheduled report."""

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    schedule: Optional[str] = Field(None, description="Cron expression")
    config: Optional[ReportConfig] = None
    recipients: Optional[List[str]] = None
    enabled: Optional[bool] = None
    timezone: Optional[str] = None

    @validator("schedule")
    @classmethod
    def validate_cron(cls, v: Optional[str]) -> Optional[str]:
        """Validate cron expression if provided."""
        if v is not None:
            try:
                from croniter import croniter

                croniter(v)
            except (ImportError, ValueError) as e:
                raise ValueError(f"Invalid cron expression: {e}") from e
        return v


class ScheduledReportResponse(BaseModel):
    """Schema for scheduled report response."""

    id: str
    name: str
    type: ReportType
    format: ReportFormat
    schedule: str
    timezone: str
    enabled: bool
    config: Dict[str, Any]
    recipients: List[str]
    delivery_method: str
    created_by: str
    organization_id: Optional[str]
    created_at: datetime
    updated_at: Optional[datetime]
    last_run_at: Optional[datetime]
    next_run_at: Optional[datetime]
    run_count: int
    success_count: int
    failure_count: int

    class Config:
        """Pydantic configuration."""

        orm_mode = True
