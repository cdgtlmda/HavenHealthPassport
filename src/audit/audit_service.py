"""
Audit Trail Service for Healthcare Standards Compliance.

Implements HIPAA-compliant audit logging for all system operations
"""

import asyncio
import hashlib
import json
import logging
import os
from dataclasses import asdict, dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, Optional

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text, create_engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

aiofiles: Any = None
aiofiles_open: Optional[Callable[..., Any]] = None
AIOFILES_AVAILABLE = False

try:
    import aiofiles as _aiofiles

    aiofiles = _aiofiles
    aiofiles_open = _aiofiles.open
    AIOFILES_AVAILABLE = True
except ImportError:
    aiofiles = None
    aiofiles_open = None
    AIOFILES_AVAILABLE = False

Base = declarative_base()  # type: Any
logger = logging.getLogger(__name__)

# Export audit_event for other modules
__all__ = [
    "AuditEventType",
    "AuditEvent",
    "AuditTrailService",
    "audit_event",
    "audit_service",
]


class AuditEventType(Enum):
    """HIPAA-defined audit event types."""

    USER_LOGIN = "user_login"
    USER_LOGOUT = "user_logout"
    PATIENT_ACCESS = "patient_access"
    PATIENT_CREATE = "patient_create"
    PATIENT_UPDATE = "patient_update"
    PATIENT_DELETE = "patient_delete"
    OBSERVATION_ACCESS = "observation_access"
    OBSERVATION_CREATE = "observation_create"
    MEDICATION_ACCESS = "medication_access"
    MEDICATION_PRESCRIBE = "medication_prescribe"
    REPORT_GENERATE = "report_generate"
    DATA_EXPORT = "data_export"
    PERMISSION_CHANGE = "permission_change"
    SYSTEM_ACCESS = "system_access"
    API_CALL = "api_call"


@dataclass
class AuditEvent:
    """Audit event data structure."""

    timestamp: datetime
    event_type: AuditEventType
    user_id: Optional[str]
    patient_id: Optional[str]
    resource_type: Optional[str]
    resource_id: Optional[str]
    action: str
    outcome: bool
    ip_address: Optional[str]
    user_agent: Optional[str]
    details: Optional[Dict[str, Any]]
    error_message: Optional[str]


class AuditLog(Base):
    """SQLAlchemy model for audit logs."""

    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime, nullable=False)
    event_type = Column(String(50), nullable=False)
    user_id = Column(String(255))
    patient_id = Column(String(255))
    resource_type = Column(String(50))
    resource_id = Column(String(255))
    action = Column(String(50), nullable=False)
    outcome = Column(Boolean, nullable=False)
    ip_address = Column(String(45))
    user_agent = Column(Text)
    details = Column(Text)
    error_message = Column(Text)
    checksum = Column(String(64), nullable=False)


class AuditTrailService:
    """Main audit trail service for healthcare compliance."""

    def __init__(self, database_url: str, file_backup_path: Optional[str] = None):
        """Initialize audit trail service with database connection."""
        try:
            self.engine = create_engine(database_url)
            Base.metadata.create_all(self.engine)
            self.SessionLocal = sessionmaker(bind=self.engine)
        except ImportError as e:
            # Handle missing database driver gracefully
            logger.warning(
                "Database driver not installed: %s. Using in-memory SQLite.", e
            )
            self.engine = create_engine("sqlite:///:memory:")
            Base.metadata.create_all(self.engine)
            self.SessionLocal = sessionmaker(bind=self.engine)
        self.file_backup_path = file_backup_path
        self._queue: asyncio.Queue = asyncio.Queue()
        self._running = False

    def _calculate_checksum(self, event: AuditEvent) -> str:
        """Calculate tamper-proof checksum for audit event."""
        data = f"{event.timestamp.isoformat()}{event.event_type.value}{event.user_id}"
        data += f"{event.resource_id}{event.action}{event.outcome}"
        return hashlib.sha256(data.encode()).hexdigest()

    async def log_event(self, event: AuditEvent) -> None:
        """Log an audit event asynchronously."""
        await self._queue.put(event)

    async def _process_queue(self) -> None:
        """Process audit events from queue."""
        while self._running:
            try:
                event = await asyncio.wait_for(self._queue.get(), timeout=1.0)
                await self._persist_event(event)
            except asyncio.TimeoutError:
                continue
            except (OSError, RuntimeError) as e:
                logger.error("Error processing audit event: %s", e)

    async def _persist_event(self, event: AuditEvent) -> None:
        """Persist audit event to database and optionally to file."""
        session = self.SessionLocal()
        try:
            # Create database record
            audit_log = AuditLog(
                timestamp=event.timestamp,
                event_type=event.event_type.value,
                user_id=event.user_id,
                patient_id=event.patient_id,
                resource_type=event.resource_type,
                resource_id=event.resource_id,
                action=event.action,
                outcome=event.outcome,
                ip_address=event.ip_address,
                user_agent=event.user_agent,
                details=json.dumps(event.details) if event.details else None,
                error_message=event.error_message,
                checksum=self._calculate_checksum(event),
            )
            session.add(audit_log)
            session.commit()

            # Backup to file if configured
            if self.file_backup_path:
                await self._backup_to_file(event)

        except (SQLAlchemyError, OSError) as e:
            logger.error("Failed to persist audit event: %s", e)
            session.rollback()
        finally:
            session.close()

    async def _backup_to_file(self, event: AuditEvent) -> None:
        """Backup audit event to file for redundancy."""
        if not AIOFILES_AVAILABLE or aiofiles is None:
            logger.warning("aiofiles not available - skipping file backup")
            return

        filename = (
            f"{self.file_backup_path}/audit_{event.timestamp.strftime('%Y%m%d')}.jsonl"
        )
        if aiofiles_open is not None:
            async with aiofiles_open(filename, mode="a") as f:
                await f.write(json.dumps(asdict(event), default=str) + "\n")

    async def start(self) -> None:
        """Start the audit service."""
        self._running = True
        asyncio.create_task(self._process_queue())
        logger.info("Audit trail service started")

    async def stop(self) -> None:
        """Stop the audit service."""
        self._running = False
        # Process remaining events
        while not self._queue.empty():
            event = await self._queue.get()
            await self._persist_event(event)
        logger.info("Audit trail service stopped")


# Global audit service instance
# Initialize with a default database URL - this should be configured properly in production
_database_url = os.getenv("DATABASE_URL", "sqlite:///./audit.db")


class AuditServiceManager:
    """Manager for singleton audit service instance."""

    _instance = None

    @classmethod
    def get_instance(cls) -> "AuditTrailService":
        """Get the audit service instance."""
        if cls._instance is None:
            cls._instance = AuditTrailService(_database_url)
        return cls._instance


def get_audit_service() -> "AuditTrailService":
    """Get the audit service instance."""
    return AuditServiceManager.get_instance()


# For backward compatibility - lazy load
class LazyAuditService:
    def __getattr__(self, name: str) -> Any:
        return getattr(get_audit_service(), name)


audit_service = LazyAuditService()


def audit_event(
    event_type: AuditEventType,
    user_id: str,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    ip_address: Optional[str] = None,
    action: Optional[str] = None,
    outcome: bool = True,
    error_message: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Log an audit event synchronously.

    This is a convenience function that wraps the async audit service.
    """
    event = AuditEvent(
        timestamp=datetime.utcnow(),
        event_type=event_type,
        user_id=user_id,
        patient_id=None,
        resource_type=resource_type,
        resource_id=resource_id,
        action=action or "",
        outcome=outcome,
        ip_address=ip_address,
        user_agent=None,
        details=metadata or {},
        error_message=error_message,
    )

    # Use asyncio to run the async method
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(audit_service.log_event(event))
    except RuntimeError:
        # No event loop running, create one
        asyncio.run(audit_service.log_event(event))
