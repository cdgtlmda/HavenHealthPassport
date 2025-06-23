"""Base model classes for database models."""

import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import Column, DateTime, event
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Mapped, Query, Session, mapped_column
from sqlalchemy.sql import func

from .db_types import UUID

Base: Any = declarative_base()


class TimestampMixin:
    """Mixin for adding timestamp fields to models."""

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        server_default=func.current_timestamp(),  # pylint: disable=not-callable
    )

    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        server_default=func.current_timestamp(),  # pylint: disable=not-callable
        onupdate=datetime.utcnow,
    )


class SoftDeleteMixin:
    """Mixin for soft delete functionality."""

    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    deleted_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )

    @property
    def is_deleted(self) -> bool:
        """Check if the record is soft deleted."""
        return self.deleted_at is not None

    def soft_delete(self, deleted_by_id: Optional[uuid.UUID] = None) -> None:
        """Soft delete this record."""
        self.deleted_at = datetime.utcnow()
        self.deleted_by = deleted_by_id

    def restore(self) -> None:
        """Restore a soft deleted record."""
        self.deleted_at = None
        self.deleted_by = None

    @classmethod
    def query_active(cls, session: Session) -> Query:
        """Query only active (non-deleted) records."""
        return session.query(cls).filter(cls.deleted_at.is_(None))


class BaseModel(Base, TimestampMixin, SoftDeleteMixin):
    """Base model class with common fields."""

    __abstract__ = True

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False
    )

    def __init__(self, **kwargs: Any) -> None:
        """Initialize base model."""
        super().__init__(**kwargs)
        if not self.id:
            self.id = uuid.uuid4()

    def to_dict(self) -> Dict[str, Any]:
        """Convert model to dictionary."""
        result = {}
        for column in self.__table__.columns:
            value = getattr(self, column.name)
            if isinstance(value, datetime):
                value = value.isoformat()
            elif isinstance(value, uuid.UUID):
                value = str(value)
            result[column.name] = value
        return result

    def update(self, **kwargs: Any) -> None:
        """Update model attributes."""
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)

    @classmethod
    def create(cls, session: Session, **kwargs: Any) -> "BaseModel":
        """Create and save a new instance."""
        instance = cls(**kwargs)
        session.add(instance)
        session.flush()
        return instance

    @classmethod
    def get_by_id(cls, session: Session, record_id: uuid.UUID) -> Optional["BaseModel"]:
        """Get instance by ID."""
        return (
            session.query(cls)
            .filter(cls.id == record_id)
            .filter(cls.deleted_at.is_(None))
            .first()
        )

    @classmethod
    def get_or_404(cls, session: Session, record_id: uuid.UUID) -> "BaseModel":
        """Get instance by ID or raise 404."""
        instance = cls.get_by_id(session, record_id)
        if not instance:
            raise ValueError(f"{cls.__name__} with id {record_id} not found")
        return instance

    def save(self, session: Session) -> None:
        """Save the current instance."""
        session.add(self)
        session.flush()

    def delete(
        self,
        session: Session,
        hard: bool = False,
        deleted_by_id: Optional[uuid.UUID] = None,
    ) -> None:
        """Delete the instance (soft delete by default)."""
        if hard:
            session.delete(self)
        else:
            self.soft_delete(deleted_by_id)
            self.save(session)

    def __repr__(self) -> str:
        """Return string representation."""
        return f"<{self.__class__.__name__}(id={self.id})>"


def auto_update_timestamp(mapper: Any, connection: Any, target: Any) -> None:
    """Automatically update the updated_at timestamp."""
    # Mark unused parameters that are required by SQLAlchemy event system
    _ = mapper  # Required by SQLAlchemy but not used
    _ = connection  # Required by SQLAlchemy but not used
    target.updated_at = datetime.utcnow()


# Register event listeners for timestamp updates
for class_ in Base.__subclasses__():
    if hasattr(class_, "updated_at"):
        event.listen(class_, "before_update", auto_update_timestamp)
