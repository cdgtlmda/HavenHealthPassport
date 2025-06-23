"""SMS Log model for tracking SMS messages sent for rate limiting."""

from uuid import UUID as UUIDType

from sqlalchemy import Column, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import BaseModel
from .db_types import UUID


class SMSLog(BaseModel):
    """Model for tracking SMS messages sent to users."""

    __tablename__ = "sms_logs"

    user_id: Mapped[UUIDType] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user_auth.id"), nullable=False, index=True
    )
    phone_number = Column(String(20), nullable=False, index=True)
    message_type = Column(
        String(50), nullable=False
    )  # e.g., "mfa_verification", "password_reset"
    status = Column(
        String(20), nullable=False, default="pending"
    )  # pending, sent, failed
    error_message = Column(Text, nullable=True)
    sent_at = Column(DateTime, nullable=True)

    # Cost tracking fields
    cost = Column(String(20), nullable=True)  # Cost in USD as decimal string
    provider = Column(String(50), nullable=True)  # SMS provider used
    country_code = Column(
        String(5), nullable=True, index=True
    )  # Country code for cost analysis

    # Relationship
    user = relationship("UserAuth", back_populates="sms_logs")

    def __repr__(self) -> str:
        """Return string representation of SMSLog."""
        return f"<SMSLog(id={self.id}, user_id={self.user_id}, type={self.message_type}, status={self.status})>"
