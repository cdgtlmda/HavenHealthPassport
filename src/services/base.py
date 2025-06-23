"""Base service class for common functionality."""

from typing import TYPE_CHECKING, Any, Dict, Generic, List, Optional, Type, TypeVar
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from src.models.base import BaseModel
from src.utils.logging import get_logger

if TYPE_CHECKING:
    from src.models.access_log import (  # noqa: F401
        AccessContext,
        AccessLog,
        AccessResult,
        AccessType,
    )

T = TypeVar("T", bound=BaseModel)

logger = get_logger(__name__)


class BaseService(Generic[T]):
    """Base service class with common CRUD operations."""

    model_class: Type[T]

    def __init__(self, session: Session):
        """Initialize service with database session."""
        from src.models.access_log import (  # pylint: disable=import-outside-toplevel # noqa: F811
            AccessContext,
        )

        self.session = session
        self.current_user_id: Optional[UUID] = None
        self.current_user_role: Optional[str] = None
        self.access_context = AccessContext.API

    def set_user_context(self, user_id: UUID, user_role: str) -> None:
        """Set the current user context for access logging."""
        self.current_user_id = user_id
        self.current_user_role = user_role

    def log_access(
        self,
        resource_id: UUID,
        access_type: "AccessType",
        purpose: str,
        patient_id: Optional[UUID] = None,
        result: Optional["AccessResult"] = None,
        **kwargs: Any,
    ) -> Optional["AccessLog"]:
        """Log access to a resource."""
        from src.models.access_log import (  # pylint: disable=import-outside-toplevel
            AccessLog,
            AccessResult,
        )

        if not self.current_user_id:
            logger.warning("No user context set for access logging")
            return None

        if result is None:
            result = AccessResult.SUCCESS

        log_entry: Optional[AccessLog] = AccessLog.log_access(
            session=self.session,
            user_id=self.current_user_id,
            resource_type=self.model_class.__name__.lower(),
            resource_id=resource_id,
            access_type=access_type,
            access_context=self.access_context,
            purpose=purpose,
            patient_id=patient_id,
            user_role=self.current_user_role,
            access_result=result,
            **kwargs,
        )

        return log_entry

    def get_by_id(self, entity_id: UUID, log_access: bool = True) -> Optional[T]:
        """Get a record by ID."""
        from src.models.access_log import (  # pylint: disable=import-outside-toplevel
            AccessResult,
            AccessType,
        )

        try:
            record = self.model_class.get_by_id(self.session, entity_id)

            if record and log_access:
                self.log_access(
                    resource_id=entity_id,
                    access_type=AccessType.VIEW,
                    purpose="View record details",
                    patient_id=getattr(record, "patient_id", None),
                )

            return record

        except (ValueError, AttributeError, KeyError) as e:
            logger.error(
                f"Error getting {self.model_class.__name__} by id {entity_id}: {e}"
            )
            if log_access:
                self.log_access(
                    resource_id=entity_id,
                    access_type=AccessType.VIEW,
                    purpose="View record details",
                    result=AccessResult.ERROR,
                    error_message=str(e),
                )
            return None

    def create(self, log_access: bool = True, **data: Any) -> T:
        """Create a new record."""
        from src.models.access_log import (  # pylint: disable=import-outside-toplevel
            AccessType,
        )

        try:
            record = self.model_class.create(self.session, **data)

            if log_access:
                self.log_access(
                    resource_id=record.id,
                    access_type=AccessType.CREATE,
                    purpose="Create new record",
                    patient_id=getattr(record, "patient_id", None),
                )

            return record

        except (ValueError, AttributeError, KeyError) as e:
            logger.error(f"Error creating {self.model_class.__name__}: {e}")
            self.session.rollback()
            raise

    def update(
        self, entity_id: UUID, log_access: bool = True, **data: Any
    ) -> Optional[T]:
        """Update an existing record."""
        from src.models.access_log import (  # pylint: disable=import-outside-toplevel
            AccessType,
        )

        try:
            record = self.get_by_id(entity_id, log_access=False)
            if not record:
                return None

            record.update(**data)
            self.session.flush()

            if log_access:
                self.log_access(
                    resource_id=entity_id,
                    access_type=AccessType.UPDATE,
                    purpose="Update record",
                    patient_id=getattr(record, "patient_id", None),
                    fields_accessed=list(data.keys()),
                )

            return record

        except (ValueError, AttributeError, KeyError) as e:
            logger.error(f"Error updating {self.model_class.__name__} {entity_id}: {e}")
            self.session.rollback()
            raise

    def delete(
        self, entity_id: UUID, hard: bool = False, log_access: bool = True
    ) -> bool:
        """Delete a record (soft delete by default)."""
        from src.models.access_log import (  # pylint: disable=import-outside-toplevel
            AccessType,
        )

        try:
            record = self.get_by_id(entity_id, log_access=False)
            if not record:
                return False

            record.delete(self.session, hard=hard, deleted_by_id=self.current_user_id)

            if log_access:
                self.log_access(
                    resource_id=entity_id,
                    access_type=AccessType.DELETE,
                    purpose="Delete record",
                    patient_id=getattr(record, "patient_id", None),
                )

            return True

        except (ValueError, AttributeError, KeyError) as e:
            logger.error(f"Error deleting {self.model_class.__name__} {entity_id}: {e}")
            self.session.rollback()
            return False

    def list(
        self,
        limit: int = 100,
        offset: int = 0,
        filters: Optional[Dict[str, Any]] = None,
        log_access: bool = True,
    ) -> List[T]:
        """List records with pagination."""
        from src.models.access_log import (  # pylint: disable=import-outside-toplevel
            AccessType,
        )

        try:
            query = self.model_class.query_active(self.session)

            # Apply filters if provided
            if filters:
                for key, value in filters.items():
                    if hasattr(self.model_class, key):
                        query = query.filter(getattr(self.model_class, key) == value)

            records = query.limit(limit).offset(offset).all()

            if log_access and records:
                # Log access to multiple records
                self.log_access(
                    resource_id=UUID(
                        "00000000-0000-0000-0000-000000000000"
                    ),  # Placeholder
                    access_type=AccessType.VIEW,
                    purpose="List records",
                    data_returned={
                        "count": len(records),
                        "limit": limit,
                        "offset": offset,
                    },
                )

            return records

        except (ValueError, AttributeError, KeyError) as e:
            logger.error(f"Error listing {self.model_class.__name__}: {e}")
            return []


class AsyncBaseService(Generic[T]):
    """Async version of base service class."""

    model_class: Type[T]

    def __init__(self, session: AsyncSession):
        """Initialize service with async database session."""
        from src.models.access_log import (  # pylint: disable=import-outside-toplevel # noqa: F811
            AccessContext,
        )

        self.session = session
        self.current_user_id: Optional[UUID] = None
        self.current_user_role: Optional[str] = None
        self.access_context = AccessContext.API

    async def set_user_context(self, user_id: UUID, user_role: str) -> None:
        """Set the current user context for access logging."""
        self.current_user_id = user_id
        self.current_user_role = user_role

    # Similar async implementations of all methods...
    # (Omitted for brevity - would include async versions of all BaseService methods)
