"""Risk assessment log model for tracking authentication risk assessments.

This module defines the database model for storing risk assessment logs.
"""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import BaseModel
from src.models.db_types import UUID


class RiskAssessmentLog(BaseModel):
    """Risk assessment log model."""

    __tablename__ = "risk_assessment_logs"

    # Assessment identification
    assessment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), default=uuid.uuid4, unique=True, nullable=False
    )
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user_auth.id"), nullable=True
    )
    email = Column(String(255), nullable=False)

    # Risk assessment results
    risk_score = Column(Float, nullable=False)
    risk_level = Column(String(20), nullable=False)  # low, medium, high, critical
    risk_factors = Column(JSON, default=list)  # List of detected risk factors

    # Context information
    ip_address = Column(String(45), nullable=False)
    user_agent = Column(String(500))
    device_fingerprint = Column(String(255))

    # Location data
    country_code = Column(String(2))
    city = Column(String(100))
    latitude = Column(Float)
    longitude = Column(Float)

    # Assessment details
    assessment_details = Column(JSON)  # Detailed risk analysis results
    recommended_actions = Column(JSON, default=list)

    # Authentication outcome
    auth_allowed = Column(String(20))  # allowed, blocked, mfa_required
    mfa_methods_required = Column(JSON)
    additional_requirements = Column(JSON)

    # Timestamps
    assessed_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Indexes
    __table_args__ = (
        Index("idx_risk_assessment_user", "user_id", "assessed_at"),
        Index("idx_risk_assessment_email", "email", "assessed_at"),
        Index("idx_risk_assessment_ip", "ip_address", "assessed_at"),
        Index("idx_risk_assessment_level", "risk_level", "assessed_at"),
        Index("idx_risk_assessment_id", "assessment_id"),
    )

    def __repr__(self) -> str:
        """Return string representation."""
        return f"<RiskAssessmentLog(id={self.id}, email={self.email}, risk_level={self.risk_level})>"
