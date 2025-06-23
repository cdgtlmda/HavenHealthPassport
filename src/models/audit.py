"""Audit models for security and compliance tracking.

Critical for HIPAA compliance and security monitoring in refugee health system.
"""

from datetime import datetime
from typing import Any, Dict

from sqlalchemy import Boolean, Column, DateTime, Float, Integer, String, Text

from src.models.base import BaseModel
from src.models.db_types import JSONB, UUID

# @authorize_required: All audit log access requires authorization
# Access control enforced at API layer via role-based permissions


class LogoutEvent(BaseModel):
    """Track user logout events for security auditing.

    Critical for detecting suspicious activity and compliance reporting.
    """

    __tablename__ = "logout_events"

    # Core fields
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    session_token = Column(String(255), nullable=False)
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)

    # Logout details
    logout_type = Column(
        String(50),
        nullable=False,
        comment="Type: manual, timeout, forced, security, session_expired",
    )
    reason = Column(String(500), comment="Detailed reason for logout")

    # Session information
    session_duration_seconds = Column(
        Integer, comment="How long the session was active"
    )
    ip_address = Column(String(45), comment="IPv4 or IPv6 address")
    user_agent = Column(Text, comment="Browser/app user agent string")
    device_id = Column(String(255), comment="Device identifier if available")
    location_data = Column(JSONB, default=dict, comment="Geolocation if available")

    # Security flags
    was_forced = Column(Boolean, default=False, comment="Was this a forced logout")
    security_event = Column(Boolean, default=False, comment="Was this security-related")

    # Metadata
    additional_data = Column(JSONB, default=dict, comment="Any additional context")

    def __repr__(self) -> str:
        """Return string representation of LogoutEvent."""
        return f"<LogoutEvent(user_id={self.user_id}, type={self.logout_type}, timestamp={self.timestamp})>"


class SecurityEvent(BaseModel):
    """Track security events for monitoring and alerting.

    Used for tracking suspicious activities, breaches, and access violations.
    """

    __tablename__ = "security_events"

    # Event identification
    event_type = Column(String(100), nullable=False, index=True)
    severity = Column(
        String(20), nullable=False, index=True, comment="CRITICAL, HIGH, MEDIUM, LOW"
    )

    # Context
    user_id = Column(
        UUID(as_uuid=True), index=True, comment="User involved if applicable"
    )
    resource_type = Column(String(100), comment="Type of resource affected")
    resource_id = Column(UUID(as_uuid=True), comment="ID of affected resource")

    # Event details
    description = Column(Text, nullable=False)
    details = Column(JSONB, default=dict)
    ip_address = Column(String(45))
    user_agent = Column(Text)

    # Response
    action_taken = Column(Text, comment="What was done in response")
    alert_sent = Column(Boolean, default=False)
    resolved = Column(Boolean, default=False)
    resolved_at = Column(DateTime)
    resolved_by = Column(UUID(as_uuid=True))

    # Threat indicators
    threat_score = Column(Integer, comment="0-100 threat level")
    is_false_positive = Column(Boolean, default=False)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for notifications."""
        return {
            "id": str(self.id),
            "event_type": self.event_type,
            "severity": self.severity,
            "user_id": str(self.user_id) if self.user_id else None,
            "description": self.description,
            "timestamp": self.created_at.isoformat(),
            "details": self.details or {},
        }


class DataAccessLog(BaseModel):
    """Log all PHI data access for HIPAA compliance.

    Required for maintaining minimum necessary access audit trail.
    """

    __tablename__ = "data_access_logs"

    # Who accessed
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    user_role = Column(String(50))
    organization_id = Column(UUID(as_uuid=True))

    # What was accessed
    resource_type = Column(String(100), nullable=False, index=True)
    resource_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    patient_id = Column(UUID(as_uuid=True), index=True)

    # Access details
    access_type = Column(
        String(50), nullable=False, comment="read, write, update, delete, export, print"
    )
    purpose = Column(String(500), comment="Reason for access")
    legal_basis = Column(String(100), comment="HIPAA legal basis for access")

    # Data specifics
    fields_accessed = Column(JSONB, comment="Which specific fields were accessed")
    data_classification = Column(String(50), comment="Type of PHI accessed")

    # Context
    ip_address = Column(String(45))
    access_location = Column(String(200))
    device_info = Column(JSONB)

    # Compliance
    consent_verified = Column(Boolean, default=False)
    emergency_override = Column(Boolean, default=False)

    def __repr__(self) -> str:
        """Return string representation of DataAccessLog."""
        return f"<DataAccessLog(user={self.user_id}, resource={self.resource_type}:{self.resource_id})>"


class JWTKeyRotationLog(BaseModel):
    """Log JWT key rotation events for audit and security tracking.

    Critical for tracking all cryptographic key changes in the system.
    """

    __tablename__ = "jwt_key_rotation_logs"

    # Key identifiers
    old_kid = Column(String(255), nullable=False, comment="Previous key ID")
    new_kid = Column(String(255), nullable=False, comment="New key ID")

    # Rotation details
    rotation_type = Column(
        String(50), nullable=False, comment="SCHEDULED, FORCED, EMERGENCY"
    )
    rotation_reason = Column(String(500), comment="Detailed reason for rotation")
    rotated_by = Column(
        String(100), nullable=False, comment="User or system that initiated"
    )

    # Performance metrics
    rotation_duration_ms = Column(
        Float, comment="Time taken for rotation in milliseconds"
    )

    # Status tracking
    status = Column(String(50), nullable=False, comment="completed, failed, pending")
    error_message = Column(Text, comment="Error details if rotation failed")

    # Notification tracking
    security_team_notified = Column(DateTime, comment="When security team was notified")
    admin_notified = Column(DateTime, comment="When admins were notified")
    jira_ticket_id = Column(String(50), comment="Associated JIRA ticket if created")

    def __repr__(self) -> str:
        """Return string representation of JWTKeyRotationLog."""
        return f"<JWTKeyRotationLog(old_kid={self.old_kid}, new_kid={self.new_kid}, status={self.status})>"
