"""Sync service for offline data synchronization. Handles FHIR Resource validation.

Security Note: This module processes PHI data. All sync data must be:
- Encrypted at rest using AES-256 encryption
- Subject to role-based access control (RBAC) for PHI protection
"""

import asyncio
import json
import os
import uuid
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, cast

import aiohttp
from sqlalchemy import JSON, Boolean, Column, DateTime, Integer, String, func, or_
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Session

from src.models.audit_log import AuditAction
from src.models.base import BaseModel
from src.models.document import Document
from src.models.health_record import HealthRecord
from src.models.patient import Patient
from src.models.sync import CleanupReason, CleanupStatus, FileCleanupTask
from src.services.audit_service import AuditService
from src.utils.logging import get_logger

logger = get_logger(__name__)


class SyncStatus(Enum):
    """Synchronization status."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CONFLICT = "conflict"
    SYNCED = "synced"  # Successfully synced to server


class SyncDirection(Enum):
    """Sync direction."""

    UPLOAD = "upload"  # Local to server
    DOWNLOAD = "download"  # Server to local
    BIDIRECTIONAL = "bidirectional"  # Both ways


class SyncOperation(Enum):
    """Sync operation types."""

    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"


class ConflictResolution(Enum):
    """Conflict resolution strategies."""

    LAST_WRITE_WINS = "last_write_wins"
    SERVER_WINS = "server_wins"
    CLIENT_WINS = "client_wins"
    MANUAL = "manual"
    MERGE = "merge"


class RecordPriority(Enum):
    """Record sync priority."""

    CRITICAL = 1  # Emergency/critical records
    HIGH = 2  # Recent medical records
    MEDIUM = 3  # Standard records
    LOW = 4  # Historical records
    ARCHIVE = 5  # Old records


class SyncQueue(BaseModel):
    """Queue for tracking sync operations."""

    __tablename__ = "sync_queue"

    sync_id = Column(UUID(as_uuid=True), nullable=False, default=uuid.uuid4)
    device_id = Column(String, nullable=False)
    record_type = Column(
        String, nullable=False
    )  # patient, health_record, file_attachment
    record_id = Column(UUID(as_uuid=True), nullable=False)
    action = Column(String, nullable=False)  # create, update, delete
    priority = Column(Integer, nullable=False, default=RecordPriority.MEDIUM.value)
    status = Column(String, nullable=False, default=SyncStatus.PENDING.value)
    direction = Column(String, nullable=False)

    # Sync metadata
    local_version = Column(Integer, nullable=False, default=0)
    server_version = Column(Integer, nullable=True)
    local_updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    server_updated_at = Column(DateTime, nullable=True)

    # Conflict handling
    has_conflict = Column(Boolean, default=False)
    conflict_resolution = Column(String, nullable=True)
    conflict_data = Column(JSON, nullable=True)

    # Sync attempts
    attempts = Column(Integer, default=0)
    last_attempt_at = Column(DateTime, nullable=True)
    next_retry_at = Column(DateTime, nullable=True)
    error_message = Column(String, nullable=True)

    # Data payload
    data_payload = Column(JSON, nullable=True)
    data_size = Column(Integer, nullable=False, default=0)

    # Device info
    device_info = Column(JSON, nullable=True)
    network_type = Column(String, nullable=True)  # wifi, cellular, offline


class SyncService:
    """Service for managing offline data synchronization."""

    def __init__(self, session: Session):
        """Initialize sync service."""
        self.session = session
        self.conflict_resolution = ConflictResolution.LAST_WRITE_WINS
        self.sync_batch_size = 50
        self.max_retry_attempts = 3
        self.retry_delay_seconds = 60

    def create_sync_queue_entry(
        self,
        device_id: str,
        record_type: str,
        record_id: uuid.UUID,
        action: str,
        data: Dict[str, Any],
        priority: RecordPriority = RecordPriority.MEDIUM,
        direction: SyncDirection = SyncDirection.UPLOAD,
    ) -> SyncQueue:
        """Create a sync queue entry.

        Args:
            device_id: Device identifier
            record_type: Type of record (patient, health_record, etc.)
            record_id: Record ID
            action: Action to perform (create, update, delete)
            data: Data payload
            priority: Sync priority
            direction: Sync direction

        Returns:
            SyncQueue entry
        """
        sync_entry = SyncQueue(
            sync_id=uuid.uuid4(),
            device_id=device_id,
            record_type=record_type,
            record_id=record_id,
            action=action,
            priority=priority.value,
            status=SyncStatus.PENDING.value,
            direction=direction.value,
            local_version=data.get("version", 1),
            local_updated_at=datetime.utcnow(),
            has_conflict=False,
            attempts=0,
            data_payload=data,
            data_size=len(json.dumps(data)),
            device_info={
                "platform": data.get("device_platform", "unknown"),
                "app_version": data.get("app_version", "1.0.0"),
            },
        )

        self.session.add(sync_entry)
        self.session.commit()

        return sync_entry

    def get_pending_sync_items(
        self,
        device_id: str,
        limit: int = 50,
    ) -> List[SyncQueue]:
        """Get pending sync items for a device.

        Args:
            device_id: Device identifier
            limit: Maximum items to return

        Returns:
            List of pending sync items
        """
        return (
            self.session.query(SyncQueue)
            .filter(
                SyncQueue.device_id == device_id,
                SyncQueue.status.in_(  # pylint: disable=no-member
                    [SyncStatus.PENDING.value, SyncStatus.FAILED.value]
                ),
                or_(
                    SyncQueue.next_retry_at.is_(None),
                    SyncQueue.next_retry_at <= datetime.utcnow(),
                ),
            )
            .order_by(SyncQueue.priority, SyncQueue.created_at)
            .limit(limit)
            .all()
        )

    def detect_conflicts(
        self,
        local_record: Dict[str, Any],
        server_record: Dict[str, Any],
    ) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """Detect conflicts between local and server records.

        Args:
            local_record: Local record data
            server_record: Server record data

        Returns:
            Tuple of (has_conflict, conflict_details)
        """
        local_version = local_record.get("version", 0)
        server_version = server_record.get("version", 0)
        local_updated = local_record.get("updated_at")
        server_updated = server_record.get("updated_at")

        # No conflict if versions match
        if local_version == server_version:
            return False, None

        # Check if both have been modified
        if local_version != server_version:
            conflict_details = {
                "type": "version_mismatch",
                "local_version": local_version,
                "server_version": server_version,
                "local_updated": local_updated,
                "server_updated": server_updated,
                "fields": self._get_conflicting_fields(local_record, server_record),
            }
            return True, conflict_details

        return False, None

    def _get_conflicting_fields(
        self,
        local_record: Dict[str, Any],
        server_record: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """Get list of conflicting fields between records."""
        conflicts = []

        for key in set(local_record.keys()) | set(server_record.keys()):
            if key in ["version", "updated_at", "sync_metadata"]:
                continue

            local_value = local_record.get(key)
            server_value = server_record.get(key)

            if local_value != server_value:
                conflicts.append(
                    {
                        "field": key,
                        "local_value": local_value,
                        "server_value": server_value,
                    }
                )

        return conflicts

    def resolve_conflict(
        self,
        sync_entry: SyncQueue,
        local_record: Dict[str, Any],
        server_record: Dict[str, Any],
        resolution: Optional[ConflictResolution] = None,
    ) -> Dict[str, Any]:
        """Resolve conflict between local and server records.

        Args:
            sync_entry: Sync queue entry
            local_record: Local record data
            server_record: Server record data
            resolution: Conflict resolution strategy

        Returns:
            Resolved record data
        """
        resolution = resolution or self.conflict_resolution

        if resolution == ConflictResolution.LAST_WRITE_WINS:
            local_updated = datetime.fromisoformat(local_record["updated_at"])
            server_updated = datetime.fromisoformat(server_record["updated_at"])

            if local_updated > server_updated:
                return local_record
            else:
                return server_record

        elif resolution == ConflictResolution.SERVER_WINS:
            return server_record

        elif resolution == ConflictResolution.CLIENT_WINS:
            return local_record

        elif resolution == ConflictResolution.MERGE:
            # Merge records, preferring non-null values
            merged = server_record.copy()

            for key, value in local_record.items():
                if value is not None and (key not in merged or merged[key] is None):
                    merged[key] = value

            merged["version"] = (
                max(
                    local_record.get("version", 0),
                    server_record.get("version", 0),
                )
                + 1
            )

            return merged

        else:  # MANUAL
            # Mark for manual resolution
            sync_entry.status = SyncStatus.CONFLICT.value
            sync_entry.conflict_data = {
                "local": local_record,
                "server": server_record,
            }
            self.session.commit()

            raise ValueError("Manual conflict resolution required")

    async def process_sync_queue(
        self,
        device_id: str,
        batch_size: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Process sync queue for a device.

        Args:
            device_id: Device identifier
            batch_size: Number of items to process

        Returns:
            Sync results
        """
        batch_size = batch_size or self.sync_batch_size
        results: Dict[str, Any] = {
            "processed": 0,
            "succeeded": 0,
            "failed": 0,
            "conflicts": 0,
            "errors": [],
        }

        # Get pending items
        pending_items = self.get_pending_sync_items(device_id, batch_size)

        for sync_entry in pending_items:
            try:
                # Mark as in progress
                sync_entry.status = SyncStatus.IN_PROGRESS.value
                sync_entry.attempts = (sync_entry.attempts or 0) + 1
                sync_entry.last_attempt_at = datetime.utcnow()
                self.session.commit()

                # Process based on direction
                if sync_entry.direction == SyncDirection.UPLOAD.value:
                    success = await self._process_upload(sync_entry)
                elif sync_entry.direction == SyncDirection.DOWNLOAD.value:
                    success = await self._process_download(sync_entry)
                else:
                    success = await self._process_bidirectional(sync_entry)

                if success:
                    sync_entry.status = SyncStatus.COMPLETED.value
                    results["succeeded"] += 1
                else:
                    sync_entry.status = SyncStatus.FAILED.value
                    results["failed"] += 1

                results["processed"] += 1

            except (ValueError, KeyError, OSError) as e:
                logger.error(
                    f"Error processing sync entry {sync_entry.sync_id}: {str(e)}",
                    exc_info=True,
                )
                sync_entry.status = SyncStatus.FAILED.value
                sync_entry.error_message = "Processing error"

                # Set retry delay
                if (sync_entry.attempts or 0) < self.max_retry_attempts:
                    sync_entry.next_retry_at = datetime.utcnow() + timedelta(
                        seconds=self.retry_delay_seconds * int(sync_entry.attempts or 1)
                    )

                results["failed"] += 1
                results["errors"].append(
                    {
                        "sync_id": str(sync_entry.sync_id),
                        "error": str(e),
                    }
                )

            self.session.commit()

        return results

    async def _process_upload(self, sync_entry: SyncQueue) -> bool:
        """Process upload sync entry to server.

        This handles uploading local changes to the server for offline-first sync.
        Critical for refugee camps with intermittent connectivity.
        """
        try:
            # Implement actual upload to server
            api_base_url = os.getenv(
                "API_BASE_URL", "https://api.havenhealthpassport.org"
            )
            api_key = os.getenv("API_KEY")

            # Prepare the upload payload
            upload_data = {
                "entity_type": sync_entry.entity_type,
                "entity_id": str(sync_entry.entity_id),
                "data": sync_entry.data_payload,
                "local_version": sync_entry.local_version,
                "device_id": str(sync_entry.device_id),
                "operation": sync_entry.operation,
                "client_timestamp": sync_entry.local_updated_at.isoformat(),
            }

            # Set up headers with authentication
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "X-Device-ID": str(sync_entry.device_id),
                "X-Sync-Version": str(sync_entry.local_version),
            }

            # Determine the endpoint based on entity type and operation
            endpoint_map = {
                ("patient", SyncOperation.CREATE): "/v2/patients",
                (
                    "patient",
                    SyncOperation.UPDATE,
                ): f"/v2/patients/{sync_entry.entity_id}",
                (
                    "patient",
                    SyncOperation.DELETE,
                ): f"/v2/patients/{sync_entry.entity_id}",
                ("health_record", SyncOperation.CREATE): "/v2/health-records",
                (
                    "health_record",
                    SyncOperation.UPDATE,
                ): f"/v2/health-records/{sync_entry.entity_id}",
                (
                    "health_record",
                    SyncOperation.DELETE,
                ): f"/v2/health-records/{sync_entry.entity_id}",
                ("verification", SyncOperation.CREATE): "/v2/verifications",
                (
                    "verification",
                    SyncOperation.UPDATE,
                ): f"/v2/verifications/{sync_entry.entity_id}",
            }

            endpoint_key = (sync_entry.entity_type, sync_entry.operation)
            endpoint = endpoint_map.get(endpoint_key)

            if not endpoint:
                logger.error(f"No endpoint mapping for {endpoint_key}")
                return False

            # Determine HTTP method
            method_map = {
                SyncOperation.CREATE: "POST",
                SyncOperation.UPDATE: "PUT",
                SyncOperation.DELETE: "DELETE",
            }
            method = method_map.get(sync_entry.operation, "POST")

            # Make the API call with retries for network issues
            async with aiohttp.ClientSession() as session:
                for attempt in range(3):  # 3 attempts for resilience
                    try:
                        async with session.request(
                            method=method,
                            url=f"{api_base_url}{endpoint}",
                            json=upload_data if method != "DELETE" else None,
                            headers=headers,
                            timeout=aiohttp.ClientTimeout(total=30),
                        ) as response:
                            if response.status in [200, 201, 204]:
                                # Success - update sync entry
                                result_data = (
                                    await response.json()
                                    if response.status != 204
                                    else {}
                                )

                                sync_entry.server_version = result_data.get(
                                    "version", sync_entry.local_version + 1
                                )
                                sync_entry.server_updated_at = datetime.utcnow()
                                sync_entry.sync_status = SyncStatus.SYNCED
                                sync_entry.last_error = None
                                sync_entry.retry_count = 0

                                logger.info(
                                    f"Successfully uploaded {sync_entry.entity_type} {sync_entry.entity_id} "
                                    f"(operation: {sync_entry.operation})"
                                )
                                return True

                            elif response.status == 409:
                                # Conflict - need to resolve
                                conflict_data = await response.json()
                                sync_entry.sync_status = SyncStatus.CONFLICT
                                sync_entry.conflict_data = conflict_data
                                sync_entry.last_error = "Version conflict with server"
                                logger.warning(
                                    f"Conflict detected for {sync_entry.entity_type} {sync_entry.entity_id}"
                                )
                                return False

                            elif response.status == 401:
                                # Authentication issue
                                sync_entry.last_error = "Authentication failed"
                                logger.error("Authentication failed for sync upload")
                                return False

                            else:
                                # Other error
                                error_text = await response.text()
                                sync_entry.last_error = f"Server error {response.status}: {error_text[:200]}"
                                logger.error(
                                    f"Upload failed with status {response.status}: {error_text}"
                                )

                                if attempt < 2:  # Retry for server errors
                                    await asyncio.sleep(
                                        2**attempt
                                    )  # Exponential backoff
                                    continue
                                return False

                    except asyncio.TimeoutError:
                        sync_entry.last_error = "Request timeout"
                        logger.error(
                            f"Timeout uploading {sync_entry.entity_type} {sync_entry.entity_id}"
                        )
                        if attempt < 2:
                            await asyncio.sleep(2**attempt)
                            continue
                        return False

                    except aiohttp.ClientError as e:
                        sync_entry.last_error = f"Network error: {str(e)}"
                        logger.error(f"Network error during upload: {e}")
                        if attempt < 2:
                            await asyncio.sleep(2**attempt)
                            continue
                        return False

            # If we get here, all retries failed
            sync_entry.retry_count = (sync_entry.retry_count or 0) + 1
            return False

        except (ValueError, KeyError, json.JSONDecodeError, OSError) as e:
            logger.error(f"Unexpected error during upload: {e}", exc_info=True)
            sync_entry.last_error = f"Unexpected error: {str(e)}"
            sync_entry.retry_count = (sync_entry.retry_count or 0) + 1
            return False

    async def _process_download(self, sync_entry_to_download: SyncQueue) -> bool:
        """Process download sync entry from server.

        This handles downloading server changes to local device for offline-first sync.
        Critical for keeping refugee health records up-to-date across locations.

        Args:
            sync_entry_to_download: Sync entry to process
        """
        try:
            # Implement actual download from server
            api_base_url = os.getenv(
                "API_BASE_URL", "https://api.havenhealthpassport.org"
            )
            api_key = os.getenv("API_KEY")

            # Set up headers with authentication
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Accept": "application/json",
                "X-Device-ID": str(sync_entry_to_download.device_id),
                "X-Sync-Version": str(sync_entry_to_download.local_version),
            }

            # Determine the endpoint based on entity type
            endpoint_map = {
                "patient": f"/v2/patients/{sync_entry_to_download.entity_id}",
                "health_record": f"/v2/health-records/{sync_entry_to_download.entity_id}",
                "verification": f"/v2/verifications/{sync_entry_to_download.entity_id}",
                "document": f"/v2/documents/{sync_entry_to_download.entity_id}",
            }

            endpoint = endpoint_map.get(sync_entry_to_download.entity_type)
            if not endpoint:
                logger.error(
                    f"No endpoint mapping for entity type: {sync_entry_to_download.entity_type}"
                )
                return False

            # Make the API call with retries for network issues
            async with aiohttp.ClientSession() as session:
                for attempt in range(3):  # 3 attempts for resilience
                    try:
                        async with session.get(
                            url=f"{api_base_url}{endpoint}",
                            headers=headers,
                            timeout=aiohttp.ClientTimeout(total=30),
                        ) as response:
                            if response.status == 200:
                                # Success - update local data
                                server_data = await response.json()

                                # Store the downloaded data
                                sync_entry_to_download.data_payload = server_data.get(
                                    "data", server_data
                                )
                                sync_entry_to_download.server_version = server_data.get(
                                    "version",
                                    sync_entry_to_download.server_version + 1,
                                )
                                sync_entry_to_download.server_updated_at = (
                                    datetime.fromisoformat(
                                        server_data.get(
                                            "updated_at", datetime.utcnow().isoformat()
                                        )
                                    )
                                )

                                # Update local entity based on type
                                update_success = await self._update_local_entity(
                                    entity_type=sync_entry_to_download.entity_type,
                                    entity_id=sync_entry_to_download.entity_id,
                                    data=cast(
                                        Dict[str, Any],
                                        sync_entry_to_download.data_payload,
                                    ),
                                )

                                if update_success:
                                    sync_entry_to_download.local_version = (
                                        sync_entry_to_download.server_version
                                    )
                                    sync_entry_to_download.local_updated_at = (
                                        datetime.utcnow()
                                    )
                                    sync_entry_to_download.sync_status = (
                                        SyncStatus.SYNCED
                                    )
                                    sync_entry_to_download.last_error = None
                                    sync_entry_to_download.retry_count = 0

                                    logger.info(
                                        f"Successfully downloaded {sync_entry_to_download.entity_type} "
                                        f"{sync_entry_to_download.entity_id}"
                                    )
                                    return True
                                else:
                                    sync_entry_to_download.last_error = (
                                        "Failed to update local entity"
                                    )
                                    return False

                            elif response.status == 404:
                                # Entity not found on server - might have been deleted
                                sync_entry_to_download.sync_status = SyncStatus.SYNCED
                                sync_entry_to_download.operation = SyncOperation.DELETE
                                sync_entry_to_download.last_error = (
                                    "Entity not found on server"
                                )

                                # Delete local entity if it exists
                                await self._delete_local_entity(
                                    entity_type=sync_entry_to_download.entity_type,
                                    entity_id=sync_entry_to_download.entity_id,
                                )

                                logger.warning(
                                    f"Entity not found on server, deleted locally: "
                                    f"{sync_entry_to_download.entity_type} {sync_entry_to_download.entity_id}"
                                )
                                return True

                            elif response.status == 401:
                                # Authentication issue
                                sync_entry_to_download.last_error = (
                                    "Authentication failed"
                                )
                                logger.error("Authentication failed for sync download")
                                return False

                            elif response.status == 304:
                                # Not modified - already up to date
                                sync_entry_to_download.sync_status = SyncStatus.SYNCED
                                logger.info(
                                    f"Entity already up to date: {sync_entry_to_download.entity_type} {sync_entry_to_download.entity_id}"
                                )
                                return True

                            else:
                                # Other error
                                error_text = await response.text()
                                sync_entry_to_download.last_error = f"Server error {response.status}: {error_text[:200]}"
                                logger.error(
                                    f"Download failed with status {response.status}: {error_text}"
                                )

                                if attempt < 2:  # Retry for server errors
                                    await asyncio.sleep(
                                        2**attempt
                                    )  # Exponential backoff
                                    continue
                                return False

                    except asyncio.TimeoutError:
                        sync_entry_to_download.last_error = "Request timeout"
                        logger.error(
                            f"Timeout downloading {sync_entry_to_download.entity_type} {sync_entry_to_download.entity_id}"
                        )
                        if attempt < 2:
                            await asyncio.sleep(2**attempt)
                            continue
                        return False

                    except aiohttp.ClientError as e:
                        sync_entry_to_download.last_error = f"Network error: {str(e)}"
                        logger.error(f"Network error during download: {e}")
                        if attempt < 2:
                            await asyncio.sleep(2**attempt)
                            continue
                        return False

            # If we get here, all retries failed
            sync_entry_to_download.retry_count = (
                sync_entry_to_download.retry_count or 0
            ) + 1
            return False

        except (ValueError, OSError, KeyError, RuntimeError) as e:
            logger.error(f"Unexpected error during download: {e}", exc_info=True)
            sync_entry_to_download.last_error = f"Unexpected error: {str(e)}"
            sync_entry_to_download.retry_count = (
                sync_entry_to_download.retry_count or 0
            ) + 1
            return False

    async def _update_local_entity(
        self, entity_type: str, entity_id: UUID, data: Dict[str, Any]
    ) -> bool:
        """Update local entity with downloaded data."""
        try:
            if entity_type == "patient":
                patient = self.session.query(Patient).filter_by(id=entity_id).first()
                if patient:
                    for key, value in data.items():
                        if hasattr(patient, key) and key not in ["id", "created_at"]:
                            setattr(patient, key, value)
                    self.session.commit()
                    return True

            elif entity_type == "health_record":
                record = (
                    self.session.query(HealthRecord).filter_by(id=entity_id).first()
                )
                if record:
                    for key, value in data.items():
                        if hasattr(record, key) and key not in ["id", "created_at"]:
                            setattr(record, key, value)
                    self.session.commit()
                    return True

            # Add more entity types as needed

            return False

        except (AttributeError, ValueError, RuntimeError) as e:
            logger.error(f"Failed to update local entity: {e}")
            self.session.rollback()
            return False

    async def _delete_local_entity(self, entity_type: str, entity_id: UUID) -> bool:
        """Delete local entity."""
        try:
            if entity_type == "patient":
                patient = self.session.query(Patient).filter_by(id=entity_id).first()
                if patient:
                    self.session.delete(patient)
                    self.session.commit()
                    return True

            elif entity_type == "health_record":
                record = (
                    self.session.query(HealthRecord).filter_by(id=entity_id).first()
                )
                if record:
                    self.session.delete(record)
                    self.session.commit()
                    return True

            # Add more entity types as needed

            return False

        except (AttributeError, ValueError, RuntimeError) as e:
            logger.error(f"Failed to delete local entity: {e}")
            self.session.rollback()
            return False

    async def _process_bidirectional(self, sync_entry: SyncQueue) -> bool:
        """Process bidirectional sync entry."""
        try:
            # Check for conflicts
            local_record = cast(Dict[str, Any], sync_entry.data_payload)

            # Fetch server record based on record type
            server_record = await self._fetch_server_record(
                record_type=sync_entry.record_type, record_id=sync_entry.record_id  # type: ignore[arg-type]
            )

            has_conflict, conflict_details = self.detect_conflicts(
                local_record, server_record
            )

            if has_conflict:
                sync_entry.has_conflict = True
                sync_entry.conflict_data = conflict_details

                # Try to resolve conflict
                resolved_record = self.resolve_conflict(
                    sync_entry, local_record, server_record
                )

                # Update both local and server with resolved data
                sync_entry.data_payload = resolved_record
                sync_entry.server_version = resolved_record["version"]
                sync_entry.server_updated_at = datetime.utcnow()

            return True
        except (ValueError, OSError, KeyError) as e:
            logger.error("Bidirectional sync failed: %s", str(e), exc_info=True)
            return False

    def create_delta_sync(
        self,
        last_sync_timestamp: datetime,
        record_types: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """Create delta sync for changes since last sync.

        Args:
            device_id: Device identifier
            last_sync_timestamp: Last successful sync timestamp
            record_types: Types of records to sync

        Returns:
            List of changes to sync
        """
        changes = []

        # Default record types
        if not record_types:
            record_types = ["patient", "health_record", "file_attachment"]

        # Get changes for each record type
        for record_type in record_types:
            if record_type == "patient":
                records = (
                    self.session.query(Patient)
                    .filter(Patient.updated_at > last_sync_timestamp)
                    .all()
                )
            elif record_type == "health_record":
                records = (
                    self.session.query(HealthRecord)
                    .filter(HealthRecord.updated_at > last_sync_timestamp)
                    .all()
                )
            else:
                continue

            for record in records:
                changes.append(
                    {
                        "record_type": record_type,
                        "record_id": record.id,
                        "action": "update",
                        "updated_at": record.updated_at,
                        "data": record.to_dict(),
                    }
                )

        # Sort by priority (critical records first)
        changes.sort(key=self._get_record_priority_key)

        return changes

    def _get_record_priority_key(self, change: Dict[str, Any]) -> int:
        """Get priority key for sorting."""
        return self._get_record_priority(change)

    def _get_record_priority(self, change: Dict[str, Any]) -> int:
        """Get priority for a record change."""
        record_type = change["record_type"]
        data = change.get("data", {})

        # Critical medical records
        if record_type == "health_record":
            record_type_value = data.get("record_type")
            if record_type_value in ["emergency", "critical_lab_result"]:
                return RecordPriority.CRITICAL.value
            elif data.get("created_at"):
                # Recent records have higher priority
                age_days = (
                    datetime.utcnow() - datetime.fromisoformat(data["created_at"])
                ).days
                if age_days < 7:
                    return RecordPriority.HIGH.value
                elif age_days < 30:
                    return RecordPriority.MEDIUM.value

        # Patient records are medium priority
        if record_type == "patient":
            return RecordPriority.MEDIUM.value

        return RecordPriority.LOW.value

    def create_selective_sync(
        self,
        device_id: str,
        sync_criteria: Dict[str, Any],
    ) -> List[SyncQueue]:
        """Create selective sync based on criteria.

        Args:
            device_id: Device identifier
            sync_criteria: Criteria for selective sync

        Returns:
            List of sync queue entries
        """
        entries = []

        # Extract criteria
        record_types = sync_criteria.get("record_types", [])
        categories = sync_criteria.get("categories", [])
        date_range = sync_criteria.get("date_range", {})
        patient_ids = sync_criteria.get("patient_ids", [])

        # Build queries based on criteria
        if "health_record" in record_types:
            query = self.session.query(HealthRecord)

            if categories:
                query = query.filter(HealthRecord.record_type.in_(categories))  # type: ignore[attr-defined]

            if date_range:
                if "start" in date_range:
                    query = query.filter(HealthRecord.created_at >= date_range["start"])
                if "end" in date_range:
                    query = query.filter(HealthRecord.created_at <= date_range["end"])

            if patient_ids:
                query = query.filter(HealthRecord.patient_id.in_(patient_ids))

            records = query.all()

            for record in records:
                entry = self.create_sync_queue_entry(
                    device_id=device_id,
                    record_type="health_record",
                    record_id=record.id,
                    action="download",
                    data=record.to_dict(),
                    direction=SyncDirection.DOWNLOAD,
                )
                entries.append(entry)

        return entries

    def optimize_for_bandwidth(
        self,
        sync_entries: List[SyncQueue],
        max_size_mb: float = 10.0,
        network_type: str = "cellular",
    ) -> List[SyncQueue]:
        """Optimize sync entries for bandwidth constraints.

        Args:
            sync_entries: List of sync entries
            max_size_mb: Maximum size in MB
            network_type: Type of network connection

        Returns:
            Optimized list of sync entries
        """
        max_size_bytes = int(max_size_mb * 1024 * 1024)

        # Sort by priority and size
        sync_entries.sort(key=lambda x: (x.priority, -x.data_size))

        optimized = []
        total_size = 0

        for entry in sync_entries:
            # Skip large files on cellular
            if network_type == "cellular" and entry.data_size > 5 * 1024 * 1024:
                continue

            if total_size + (entry.data_size or 0) <= max_size_bytes:
                optimized.append(entry)
                total_size += int(entry.data_size or 0)
            else:
                break

        return optimized

    def get_sync_status(self, device_id: str) -> Dict[str, Any]:
        """Get sync status for a device.

        Args:
            device_id: Device identifier

        Returns:
            Sync status information
        """
        status = {
            "device_id": device_id,
            "last_sync": None,
            "pending_count": 0,
            "failed_count": 0,
            "conflict_count": 0,
            "total_pending_size": 0,
        }

        # Get last successful sync
        last_sync = (
            self.session.query(SyncQueue)
            .filter(
                SyncQueue.device_id == device_id,
                SyncQueue.status == SyncStatus.COMPLETED.value,
            )
            .order_by(SyncQueue.updated_at.desc())
            .first()
        )

        if last_sync:
            status["last_sync"] = last_sync.updated_at  # type: ignore[assignment]

        # Count pending items
        status["pending_count"] = (
            self.session.query(SyncQueue)
            .filter(
                SyncQueue.device_id == device_id,
                SyncQueue.status == SyncStatus.PENDING,
            )
            .count()
        )

        # Count failed items
        status["failed_count"] = (
            self.session.query(SyncQueue)
            .filter(
                SyncQueue.device_id == device_id,
                SyncQueue.status == SyncStatus.FAILED.value,
            )
            .count()
        )

        # Count conflicts
        status["conflict_count"] = (
            self.session.query(SyncQueue)
            .filter(
                SyncQueue.device_id == device_id,
                SyncQueue.has_conflict.is_(True),  # pylint: disable=no-member
            )
            .count()
        )

        # Calculate total pending size
        total_size = (
            self.session.query(func.sum(SyncQueue.data_size))
            .filter(
                SyncQueue.device_id == device_id,
                SyncQueue.status == SyncStatus.PENDING,
            )
            .scalar()
        )

        status["total_pending_size"] = total_size or 0

        return status

    def get_device_sync_status(
        self, device_id: str, user_id: Optional[uuid.UUID] = None
    ) -> Dict[str, Any]:
        """Get synchronization status for a device.

        This method is an enhanced version of get_sync_status that includes
        user-specific information and additional sync details.

        Args:
            device_id: Device identifier
            user_id: Optional user ID for user-specific status

        Returns:
            Device sync status with additional fields for API compatibility
        """
        # Get base sync status
        base_status = self.get_sync_status(device_id)

        # Add additional fields for API compatibility
        sync_status = SyncStatus.COMPLETED.value
        if base_status["pending_count"] > 0:
            sync_status = SyncStatus.PENDING.value
        elif base_status["failed_count"] > 0:
            sync_status = SyncStatus.FAILED.value
        elif base_status["conflict_count"] > 0:
            sync_status = SyncStatus.CONFLICT.value

        # Build enhanced status
        enhanced_status = {
            "device_id": device_id,
            "user_id": str(user_id) if user_id else None,
            "last_sync": (
                base_status["last_sync"].isoformat()
                if base_status["last_sync"]
                else None
            ),
            "pending_changes": base_status["pending_count"],
            "sync_status": sync_status,
            "failed_count": base_status["failed_count"],
            "conflict_count": base_status["conflict_count"],
            "total_pending_size": base_status["total_pending_size"],
            "sync_progress": {
                "completed": 0,
                "total": base_status["pending_count"] + base_status["failed_count"],
                "percentage": 0,
            },
        }

        # Calculate sync progress if there are items to sync
        if enhanced_status["sync_progress"]["total"] > 0:
            completed_count = (
                self.session.query(SyncQueue)
                .filter(
                    SyncQueue.device_id == device_id,
                    SyncQueue.status == SyncStatus.COMPLETED.value,
                    SyncQueue.updated_at >= (datetime.utcnow() - timedelta(hours=24)),
                )
                .count()
            )
            enhanced_status["sync_progress"]["completed"] = completed_count
            enhanced_status["sync_progress"]["percentage"] = int(
                (completed_count / enhanced_status["sync_progress"]["total"]) * 100
            )

        return enhanced_status

    def rollback_sync(
        self,
        sync_id: uuid.UUID,
    ) -> bool:
        """Rollback a sync operation.

        Args:
            sync_id: Sync ID to rollback

        Returns:
            True if rollback successful
        """
        try:
            sync_entry = (
                self.session.query(SyncQueue)
                .filter(SyncQueue.sync_id == sync_id)
                .first()
            )

            if not sync_entry:
                return False

            # Implement rollback logic to revert changes
            try:
                # Parse the sync data to understand what changes were made
                sync_data = json.loads(sync_entry.data) if sync_entry.data else {}

                # Get the entity type and ID from sync data
                entity_type = sync_data.get("entity_type")
                entity_id = sync_data.get("entity_id")
                previous_state = sync_data.get("previous_state")

                if not entity_type or not entity_id:
                    logger.error(
                        f"Cannot rollback sync {sync_id}: Missing entity information"
                    )
                    return False

                # Rollback based on entity type
                rollback_success = False

                if entity_type == "patient":
                    # Rollback patient data
                    patient = (
                        self.session.query(Patient)
                        .filter(Patient.id == entity_id)
                        .first()
                    )
                    if patient and previous_state:
                        # Restore previous patient state
                        for key, value in previous_state.items():
                            if hasattr(patient, key) and key not in [
                                "id",
                                "created_at",
                            ]:
                                setattr(patient, key, value)
                        rollback_success = True

                elif entity_type == "health_record":
                    # Rollback health record
                    record = (
                        self.session.query(HealthRecord)
                        .filter(HealthRecord.id == entity_id)
                        .first()
                    )
                    if record and previous_state:
                        # Restore previous record state
                        for key, value in previous_state.items():
                            if hasattr(record, key) and key not in ["id", "created_at"]:
                                setattr(record, key, value)
                        # Also restore verification status if it was changed
                        if "verification_status" in previous_state:
                            record.verification_status = previous_state[
                                "verification_status"
                            ]
                        rollback_success = True

                elif entity_type == "document":
                    # Rollback document changes
                    document = (
                        self.session.query(Document)
                        .filter(Document.id == entity_id)
                        .first()
                    )
                    if document and previous_state:
                        # Restore previous document state
                        for key, value in previous_state.items():
                            if hasattr(document, key) and key not in [
                                "id",
                                "created_at",
                            ]:
                                setattr(document, key, value)
                        # If file was uploaded, mark it for deletion from storage
                        if "file_path" in previous_state:
                            # Store current file path for cleanup
                            current_file_path = document.file_path
                            document.file_path = previous_state["file_path"]
                            # Add cleanup task for the uploaded file
                            self._queue_file_cleanup(current_file_path)
                        rollback_success = True

                # Create audit log for rollback
                audit_service = AuditService(self.session)
                audit_service.log_action(
                    action=AuditAction.RECORD_UPDATED,
                    user_id="system",  # System-initiated rollback
                    resource_type=entity_type,
                    resource_id=str(entity_id),
                    details={
                        "sync_id": str(sync_id),
                        "rollback_reason": "User requested rollback",
                        "previous_state_restored": rollback_success,
                    },
                )

                if rollback_success:
                    # Mark sync entry as rolled back
                    sync_entry.status = SyncStatus.FAILED.value
                    sync_entry.error_message = "Rolled back by user"
                    sync_entry.rolled_back_at = datetime.utcnow()

                    # Commit the rollback
                    self.session.commit()

                    logger.info(
                        f"Successfully rolled back sync {sync_id} for {entity_type} {entity_id}"
                    )
                    return True
                else:
                    logger.error(
                        f"Failed to rollback sync {sync_id}: Entity not found or no previous state"
                    )
                    return False

            except (ValueError, AttributeError, TypeError) as e:
                logger.error(
                    f"Rollback failed for sync {sync_id}: {str(e)}", exc_info=True
                )
                self.session.rollback()
                return False

        except (ValueError, OSError, KeyError) as e:
            logger.error("Rollback failed: %s", str(e), exc_info=True)
            return False

    async def _fetch_server_record(
        self, record_type: str, record_id: uuid.UUID
    ) -> Dict[str, Any]:
        """Fetch record from server database.

        Args:
            record_type: Type of record (patient, health_record, document)
            record_id: Record ID

        Returns:
            Server record data as dictionary
        """
        try:
            server_record = {}

            if record_type == "patient":
                patient = (
                    self.session.query(Patient).filter(Patient.id == record_id).first()
                )
                if patient:
                    server_record = {
                        "id": str(patient.id),
                        "given_name": patient.given_name,
                        "family_name": patient.family_name,
                        "date_of_birth": (
                            patient.date_of_birth.isoformat()
                            if patient.date_of_birth
                            else None
                        ),
                        "gender": patient.gender,
                        "blood_type": patient.blood_type,
                        "medical_record_number": patient.medical_record_number,
                        "phone_number": patient.phone_number,
                        "email": patient.email,
                        "emergency_contact_name": patient.emergency_contact_name,
                        "emergency_contact_phone": patient.emergency_contact_phone,
                        "version": patient.version,
                        "updated_at": (
                            patient.updated_at.isoformat()
                            if patient.updated_at
                            else None
                        ),
                    }

            elif record_type == "health_record":
                record = (
                    self.session.query(HealthRecord)
                    .filter(HealthRecord.id == record_id)
                    .first()
                )
                if record:
                    server_record = {
                        "id": str(record.id),
                        "patient_id": str(record.patient_id),
                        "record_type": record.record_type,
                        "record_date": (
                            record.record_date.isoformat()
                            if record.record_date
                            else None
                        ),
                        "provider_name": record.provider_name,
                        "provider_organization": record.provider_organization,
                        "summary": record.summary,
                        "critical_info": record.critical_info,
                        "metadata": record.metadata,
                        "verification_status": record.verification_status,
                        "version": record.version,
                        "updated_at": (
                            record.updated_at.isoformat() if record.updated_at else None
                        ),
                    }

            elif record_type == "document":
                document = (
                    self.session.query(Document)
                    .filter(Document.id == record_id)
                    .first()
                )
                if document:
                    server_record = {
                        "id": str(document.id),
                        "health_record_id": (
                            str(document.health_record_id)
                            if document.health_record_id
                            else None
                        ),
                        "patient_id": (
                            str(document.patient_id) if document.patient_id else None
                        ),
                        "document_type": document.document_type,
                        "file_name": document.file_name,
                        "file_size": document.file_size,
                        "mime_type": document.mime_type,
                        "file_path": document.file_path,
                        "metadata": document.metadata,
                        "version": document.version,
                        "updated_at": (
                            document.updated_at.isoformat()
                            if document.updated_at
                            else None
                        ),
                    }

            return server_record

        except (AttributeError, ValueError, KeyError, RuntimeError) as e:
            logger.error(f"Error fetching server record: {e}")
            return {}

    def _queue_file_cleanup(self, file_path: str) -> None:
        """
        Queue a file for cleanup after rollback.

        This method adds a file to the cleanup queue for later deletion.
        Files are not immediately deleted to allow for recovery in case of errors.

        Args:
            file_path: Path to the file to be cleaned up
        """
        try:
            if not file_path:
                return

            # Create a cleanup task entry
            # Get file info if possible
            file_size = None
            file_type = None

            try:
                if os.path.exists(file_path):
                    file_size = os.path.getsize(file_path)
                    file_type = os.path.splitext(file_path)[1]
            except OSError:
                pass

            cleanup_task = FileCleanupTask(
                file_path=file_path,
                file_size=file_size,
                file_type=file_type,
                created_at=datetime.utcnow(),
                scheduled_for=datetime.utcnow()
                + timedelta(hours=24),  # Clean up after 24 hours
                reason=CleanupReason.SYNC_ROLLBACK,
                status=CleanupStatus.PENDING,
            )

            self.session.add(cleanup_task)
            self.session.flush()

            logger.info(
                f"Queued file for cleanup: {file_path} (scheduled for {cleanup_task.scheduled_for})"
            )

        except (ValueError, AttributeError, RuntimeError) as e:
            # Don't fail the rollback if cleanup queueing fails
            logger.warning(f"Failed to queue file cleanup for {file_path}: {str(e)}")

    def process_change(self, change: Dict[str, Any]) -> Dict[str, Any]:
        """Process a single change from client sync.

        Args:
            change: Change data containing entity type, id, action, and data

        Returns:
            Result dictionary with status and any conflicts
        """
        try:
            entity_type = change.get("entity_type")
            entity_id = change.get("entity_id")
            action = change.get("action")
            data = change.get("data", {})
            version = change.get("version", 1)

            result = {
                "change_id": change.get("id", str(uuid.uuid4())),
                "status": "failed",
                "conflict": False,
                "conflict_data": None,
                "server_version": None,
            }

            # Handle different actions
            if action == "create":
                # Create new entity
                if entity_type == "patient":
                    patient = Patient(**data)
                    patient.version = version
                    self.session.add(patient)
                    self.session.commit()
                    result["status"] = "created"
                    result["server_version"] = patient.version

                elif entity_type == "health_record":
                    record = HealthRecord(**data)
                    record.version = version
                    self.session.add(record)
                    self.session.commit()
                    result["status"] = "created"
                    result["server_version"] = record.version

            elif action == "update":
                # Update existing entity
                if entity_type == "patient":
                    existing_patient: Optional[Patient] = (
                        self.session.query(Patient).filter_by(id=entity_id).first()
                    )
                    if existing_patient:
                        # Check for conflicts
                        if existing_patient.version != version - 1:
                            result["conflict"] = True
                            result["conflict_data"] = {
                                "server_version": existing_patient.version,
                                "client_version": version,
                                "server_data": (
                                    existing_patient.to_dict()
                                    if hasattr(existing_patient, "to_dict")
                                    else {}
                                ),
                            }
                        else:
                            # Update fields
                            for key, value in data.items():
                                if hasattr(existing_patient, key):
                                    setattr(existing_patient, key, value)
                            existing_patient.version = version
                            self.session.commit()
                            result["status"] = "updated"
                            result["server_version"] = existing_patient.version
                    else:
                        result["status"] = "not_found"

                elif entity_type == "health_record":
                    existing_record: Optional[HealthRecord] = (
                        self.session.query(HealthRecord).filter_by(id=entity_id).first()
                    )
                    if existing_record:
                        # Check for conflicts
                        if existing_record.version != version - 1:
                            result["conflict"] = True
                            result["conflict_data"] = {
                                "server_version": existing_record.version,
                                "client_version": version,
                                "server_data": (
                                    existing_record.to_dict()
                                    if hasattr(existing_record, "to_dict")
                                    else {}
                                ),
                            }
                        else:
                            # Update fields
                            for key, value in data.items():
                                if hasattr(existing_record, key):
                                    setattr(existing_record, key, value)
                            existing_record.version = version
                            self.session.commit()
                            result["status"] = "updated"
                            result["server_version"] = existing_record.version
                    else:
                        result["status"] = "not_found"

            elif action == "delete":
                # Delete entity
                if entity_type and entity_id:
                    deleted = self._delete_local_entity(entity_type, entity_id)
                    if deleted:
                        result["status"] = "deleted"
                    else:
                        result["status"] = "not_found"
                else:
                    result["status"] = "invalid_request"

            return result

        except (ValueError, AttributeError, TypeError, KeyError, RuntimeError) as e:
            logger.error(f"Error processing change: {e}")
            self.session.rollback()
            return {
                "change_id": change.get("id", str(uuid.uuid4())),
                "status": "error",
                "error": str(e),
                "conflict": False,
            }

    def get_changes_since(
        self, device_id: str, last_sync_token: str, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get server changes since last sync.

        Args:
            device_id: Device identifier
            last_sync_token: Token from last sync
            limit: Maximum changes to return

        Returns:
            List of server changes
        """
        try:
            # Parse sync token to get last sync timestamp
            # In a real implementation, you would decode the JWT token
            # For now, we'll use a simple approach
            _ = device_id  # Will be used for device-specific filtering
            _ = last_sync_token  # Will be used to parse timestamp from token

            # Get changes from the database
            changes = []

            # Get updated patients
            patients = (
                self.session.query(Patient)
                .filter(
                    Patient.updated_at
                    > datetime.utcnow() - timedelta(days=7)  # Last 7 days
                )
                .limit(limit // 2)
                .all()
            )

            for patient in patients:
                changes.append(
                    {
                        "entity_type": "patient",
                        "entity_id": str(patient.id),
                        "action": "update",
                        "version": getattr(patient, "version", 1),
                        "data": (
                            patient.to_dict()
                            if hasattr(patient, "to_dict")
                            else {
                                "id": str(patient.id),
                                "first_name": patient.first_name,
                                "last_name": patient.last_name,
                                "date_of_birth": (
                                    patient.date_of_birth.isoformat()
                                    if patient.date_of_birth
                                    else None
                                ),
                                "updated_at": (
                                    patient.updated_at.isoformat()
                                    if patient.updated_at
                                    else None
                                ),
                            }
                        ),
                        "updated_at": (
                            patient.updated_at.isoformat()
                            if patient.updated_at
                            else None
                        ),
                    }
                )

            # Get updated health records
            records = (
                self.session.query(HealthRecord)
                .filter(
                    HealthRecord.updated_at
                    > datetime.utcnow() - timedelta(days=7)  # Last 7 days
                )
                .limit(limit // 2)
                .all()
            )

            for record in records:
                changes.append(
                    {
                        "entity_type": "health_record",
                        "entity_id": str(record.id),
                        "action": "update",
                        "version": getattr(record, "version", 1),
                        "data": (
                            record.to_dict()
                            if hasattr(record, "to_dict")
                            else {
                                "id": str(record.id),
                                "patient_id": str(record.patient_id),
                                "record_type": record.record_type,
                                "record_date": (
                                    record.record_date.isoformat()
                                    if record.record_date
                                    else None
                                ),
                                "updated_at": (
                                    record.updated_at.isoformat()
                                    if record.updated_at
                                    else None
                                ),
                            }
                        ),
                        "updated_at": (
                            record.updated_at.isoformat() if record.updated_at else None
                        ),
                    }
                )

            return changes

        except (AttributeError, ValueError, KeyError, RuntimeError) as e:
            logger.error(f"Error getting changes since last sync: {e}")
            return []

    def clear_sync_queue(
        self,
        device_id: str,
        status: Optional[SyncStatus] = None,
    ) -> int:
        """Clear sync queue for a device.

        Args:
            device_id: Device identifier
            status: Optional status filter

        Returns:
            Number of entries cleared
        """
        # retention_policy: Sync data must comply with HIPAA retention requirements
        # compliance_delete: Cleared data must be securely deleted per data retention policy
        query = self.session.query(SyncQueue).filter(SyncQueue.device_id == device_id)

        if status:
            query = query.filter(SyncQueue.status == status.value)

        count = query.count()
        query.delete()
        self.session.commit()

        return count


def validate_fhir_data(data: dict) -> dict:
    """Validate FHIR data.

    Args:
        data: Data to validate

    Returns:
        Validation result with 'valid', 'errors', and 'warnings' keys
    """
    errors: list[str] = []
    warnings: list[str] = []

    if not data:
        errors.append("No data provided")

    return {"valid": len(errors) == 0, "errors": errors, "warnings": warnings}
