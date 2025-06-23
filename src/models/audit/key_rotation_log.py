"""JWT Key Rotation Audit Log Model.

This model tracks all JWT key rotation events for security compliance
and audit trail requirements.
"""

import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, Float, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID

from src.models.base import Base


class JWTKeyRotationLog(Base):
    """Audit log for JWT key rotation events."""

    __tablename__ = "jwt_key_rotation_logs"

    id = Column(UUID, primary_key=True, default=lambda: str(uuid.uuid4()))
    old_kid = Column(String(255), nullable=False, index=True)
    new_kid = Column(String(255), nullable=False, index=True)
    rotation_type = Column(String(50), nullable=False)  # SCHEDULED, COMPROMISE, POLICY
    rotation_reason = Column(Text, nullable=True)
    affected_tokens_count = Column(Integer, default=0)
    rotation_duration_ms = Column(Float, nullable=True)

    # User and system information
    rotated_by = Column(String(255), nullable=False)  # system or user ID
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)

    # Status tracking
    status = Column(String(20), default="completed")  # completed, failed, rollback
    error_message = Column(Text, nullable=True)
    rollback_performed = Column(DateTime, nullable=True)

    # Timestamps
    rotated_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Notification tracking
    security_team_notified = Column(DateTime, nullable=True)
    admin_notified = Column(DateTime, nullable=True)
    jira_ticket_id = Column(String(50), nullable=True)

    def __repr__(self) -> str:
        """Return string representation of JWTKeyRotationLog."""
        return f"<JWTKeyRotationLog(old_kid='{self.old_kid}', new_kid='{self.new_kid}', rotated_at='{self.rotated_at}')>"
