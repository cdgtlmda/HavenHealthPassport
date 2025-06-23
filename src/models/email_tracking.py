"""Email tracking models."""

from datetime import datetime
from enum import Enum
from uuid import UUID as UUIDType
from uuid import uuid4

from sqlalchemy import JSON, Column, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import BaseModel


class EmailStatus(str, Enum):
    """Email status enumeration."""

    SENT = "sent"
    DELIVERED = "delivered"
    BOUNCED = "bounced"
    COMPLAINED = "complained"
    FAILED = "failed"


class EmailMessage(BaseModel):
    """Email message tracking model."""

    __tablename__ = "email_messages"

    id: Mapped[UUIDType] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    message_id = Column(String(255), unique=True, nullable=False, index=True)
    recipient = Column(String(255), nullable=False, index=True)
    subject = Column(String(255), nullable=False)
    template_id = Column(String(100), nullable=True, index=True)
    tags = Column(JSON, default=list)
    email_metadata = Column(JSON, default=dict)

    sent_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    delivered_at = Column(DateTime, nullable=True)

    status = Column(String(20), default=EmailStatus.SENT, nullable=False, index=True)

    # Relationships
    events = relationship(
        "EmailEvent", back_populates="email_message", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("idx_email_messages_sent_at", "sent_at"),
        Index("idx_email_messages_status_sent_at", "status", "sent_at"),
    )


class EmailEvent(BaseModel):
    """Email event tracking model."""

    __tablename__ = "email_events"

    id: Mapped[UUIDType] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    email_id = Column(
        UUID(as_uuid=True), ForeignKey("email_messages.id"), nullable=False
    )
    event_type = Column(String(20), nullable=False, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    event_metadata = Column(JSON, default=dict)

    # Relationships
    email_message = relationship("EmailMessage", back_populates="events")

    __table_args__ = (
        Index("idx_email_events_email_id_type", "email_id", "event_type"),
        Index("idx_email_events_timestamp", "timestamp"),
    )


class EmailUnsubscribe(BaseModel):
    """Email unsubscribe tracking."""

    __tablename__ = "email_unsubscribes"

    id: Mapped[UUIDType] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    email = Column(String(255), unique=True, nullable=False, index=True)
    unsubscribed_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    resubscribed_at = Column(DateTime, nullable=True)
    reason = Column(Text, nullable=True)

    __table_args__ = (
        Index("idx_email_unsubscribes_email_status", "email", "resubscribed_at"),
    )
