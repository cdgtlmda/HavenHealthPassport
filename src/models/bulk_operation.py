"""Bulk Operation Model.

This module defines the database model for tracking scheduled and executed bulk operations.
"""

from datetime import datetime
from enum import Enum

from sqlalchemy import Column, DateTime
from sqlalchemy import Enum as SQLEnum
from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base


class BulkOperationType(str, Enum):
    """Types of bulk operations."""

    IMPORT = "import"
    EXPORT = "export"
    UPDATE = "update"
    DELETE = "delete"


class BulkOperationStatus(str, Enum):
    """Status of bulk operations."""

    SCHEDULED = "scheduled"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class BulkOperation(Base):
    """Model for tracking bulk operations."""

    __tablename__ = "bulk_operations"

    id = Column(String, primary_key=True)
    type: Mapped[BulkOperationType] = mapped_column(
        SQLEnum(BulkOperationType), nullable=False
    )
    status: Mapped[BulkOperationStatus] = mapped_column(
        SQLEnum(BulkOperationStatus),
        nullable=False,
        default=BulkOperationStatus.SCHEDULED,
    )

    # User and organization
    user_id = Column(String, ForeignKey("user_auth.id"), nullable=False)
    organization_id = Column(String, ForeignKey("organizations.id"), nullable=False)

    # Timing
    scheduled_at = Column(DateTime, nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Operation details
    parameters = Column(Text, nullable=True)  # JSON string of operation parameters
    result = Column(Text, nullable=True)  # JSON string of operation results
    error_message = Column(Text, nullable=True)

    # Relationships
    user = relationship("UserAuth", back_populates="bulk_operations")
    organization = relationship("Organization", back_populates="bulk_operations")

    def __repr__(self) -> str:
        """Return string representation of BulkOperation."""
        return f"<BulkOperation(id={self.id}, type={self.type}, status={self.status})>"
