"""File versioning service for managing document versions."""

import hashlib
import json
import mimetypes
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, BinaryIO, Dict, List, Optional, cast
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, Integer, String, desc
from sqlalchemy.orm import Mapped, Session, mapped_column

from src.models.base import BaseModel
from src.models.db_types import UUID as SQLAlchemyUUID
from src.services.base import BaseService
from src.storage.base import FileCategory

# Import moved to break circular dependency
from src.utils.logging import get_logger

logger = get_logger(__name__)


class VersionStatus(str, Enum):
    """Version status states."""

    CURRENT = "current"
    ARCHIVED = "archived"
    DELETED = "deleted"
    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"
    SUPERSEDED = "superseded"


class VersionChangeType(str, Enum):
    """Types of changes between versions."""

    MINOR = "minor"  # Small updates, corrections
    MAJOR = "major"  # Significant content changes
    CRITICAL = "critical"  # Medical information updates
    FORMAT = "format"  # File format changes only
    METADATA = "metadata"  # Metadata updates only


@dataclass
class VersionDiff:
    """Differences between two versions."""

    version_a: int
    version_b: int
    size_change: int
    hash_changed: bool
    metadata_changes: Dict[str, Any]
    change_summary: str


class FileVersion(BaseModel):
    """Model for file versions."""

    __tablename__ = "file_versions"

    # Version identification
    file_id: Mapped[str] = mapped_column(String(255))  # Base file ID
    version_id: Mapped[str] = mapped_column(String(255))  # Unique version ID
    version_number: Mapped[int] = mapped_column(Integer)  # Sequential version number

    # Version metadata
    filename: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(100))
    size: Mapped[int] = mapped_column(Integer)
    checksum: Mapped[str] = mapped_column(String(64))
    storage_path: Mapped[str] = mapped_column(String(500))

    # Version status
    status: Mapped[str] = mapped_column(String(50))
    change_type: Mapped[str] = mapped_column(String(50))
    change_description: Mapped[Optional[str]] = mapped_column(
        String(500), nullable=True
    )

    # Relationships
    parent_version_id: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True
    )  # Previous version
    created_by: Mapped[UUID] = mapped_column(SQLAlchemyUUID(as_uuid=True))
    approved_by: Mapped[Optional[UUID]] = mapped_column(
        SQLAlchemyUUID(as_uuid=True), nullable=True
    )

    # Timestamps (created_at comes from BaseModel)
    approved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    archived_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Additional metadata - SQLAlchemy doesn't support Dict directly, use JSON
    _metadata: Mapped[Optional[str]] = mapped_column(
        String, nullable=True, name="metadata"
    )  # Store as JSON string
    _tags: Mapped[Optional[str]] = mapped_column(
        String, nullable=True, name="tags"
    )  # Store as JSON string

    # Security
    is_locked: Mapped[bool] = mapped_column(
        Boolean, default=False
    )  # Prevent modifications
    requires_approval: Mapped[bool] = mapped_column(Boolean, default=False)

    @property
    def meta_data(self) -> Dict[str, Any]:
        """Get metadata as dictionary."""
        if self._metadata:
            try:
                return cast(Dict[str, Any], json.loads(self._metadata))
            except (json.JSONDecodeError, TypeError):
                return {}
        return {}

    @meta_data.setter
    def meta_data(self, value: Optional[Dict[str, Any]]) -> None:
        """Set metadata from dictionary."""
        if value is None:
            self._metadata = None
        else:
            self._metadata = json.dumps(value)

    @property
    def tags(self) -> List[str]:
        """Get tags as list."""
        if self._tags:
            try:
                return cast(List[str], json.loads(self._tags))
            except (json.JSONDecodeError, TypeError):
                return []
        return []

    @tags.setter
    def tags(self, value: Optional[List[str]]) -> None:
        """Set tags from list."""
        if value is None:
            self._tags = None
        else:
            self._tags = json.dumps(value)

    @property
    def is_current(self) -> bool:
        """Check if this is the current version."""
        return self.status == VersionStatus.CURRENT


class FileVersionHistory(BaseModel):
    """Model for tracking version history and relationships."""

    __tablename__ = "file_version_history"

    file_id: Mapped[str] = mapped_column(String(255))
    from_version: Mapped[int] = mapped_column(Integer)
    to_version: Mapped[int] = mapped_column(Integer)
    change_type: Mapped[str] = mapped_column(String(50))
    changed_by: Mapped[UUID] = mapped_column(SQLAlchemyUUID(as_uuid=True))
    change_reason: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    rollback_of: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True
    )  # If this is a rollback operation
    _metadata: Mapped[Optional[str]] = mapped_column(
        String, nullable=True, name="metadata"
    )  # Store as JSON string

    @property
    def meta_data(self) -> Dict[str, Any]:
        """Get metadata as dictionary."""
        if self._metadata:
            try:
                return cast(Dict[str, Any], json.loads(self._metadata))
            except (json.JSONDecodeError, TypeError):
                return {}
        return {}

    @meta_data.setter
    def meta_data(self, value: Optional[Dict[str, Any]]) -> None:
        """Set metadata from dictionary."""
        if value is None:
            self._metadata = None
        else:
            self._metadata = json.dumps(value)


class FileVersioningService(BaseService[FileVersion]):
    """Service for managing file versions."""

    model_class = FileVersion

    # Configuration
    MAX_VERSIONS_PER_FILE = 100
    AUTO_ARCHIVE_AFTER_DAYS = 90
    REQUIRE_APPROVAL_FOR_CRITICAL = True

    def __init__(self, session: Session, storage_manager: Optional[Any] = None):
        """Initialize file versioning service.

        Args:
            session: Database session
            storage_manager: Optional storage manager instance. If not provided,
                           the service will create one when needed.
        """
        super().__init__(session)
        self._storage_manager = storage_manager

    @property
    def storage_manager(self) -> Any:
        """Get storage manager instance, creating if needed.

        This lazy initialization breaks the circular dependency.
        """
        if self._storage_manager is None:
            from src.storage.manager import StorageManager

            self._storage_manager = StorageManager(self.session)
        return self._storage_manager

    def create_version(
        self,
        file_id: str,
        file_data: BinaryIO,
        filename: str,
        created_by: UUID,
        change_type: VersionChangeType = VersionChangeType.MINOR,
        change_description: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None,
        requires_approval: bool = False,
        category: Optional[FileCategory] = None,
    ) -> FileVersion:
        """
        Create a new version of a file.

        Args:
            file_id: Base file identifier
            file_data: New version data
            filename: Filename for this version
            created_by: User creating the version
            change_type: Type of change
            change_description: Description of changes
            metadata: Additional metadata
            tags: Version tags
            requires_approval: Whether version needs approval
            category: File category

        Returns:
            Created file version
        """
        try:
            # Get current version number
            current_version = self._get_current_version(file_id)
            version_number = (
                (current_version.version_number + 1) if current_version else 1
            )

            # Generate version ID
            version_id = f"{file_id}_v{version_number}_{uuid4().hex[:8]}"

            # Calculate checksum
            file_data.seek(0)
            checksum = self._calculate_checksum(file_data)

            # Get file size
            file_data.seek(0, 2)
            size = file_data.tell()
            file_data.seek(0)

            # Determine content type
            content_type, _ = mimetypes.guess_type(filename)
            content_type = content_type or "application/octet-stream"

            # Store file with version path
            storage_result = self.storage_manager.store_file(
                file_data=file_data,
                filename=filename,
                category=category or FileCategory.OTHER,
                uploaded_by=created_by,
                metadata={
                    "version_id": version_id,
                    "version_number": version_number,
                    "original_file_id": file_id,
                },
            )

            # Create version record
            version = FileVersion(
                file_id=file_id,
                version_id=version_id,
                version_number=version_number,
                filename=filename,
                content_type=content_type,
                size=size,
                checksum=checksum,
                storage_path=storage_result.file_id,
                status=(
                    VersionStatus.DRAFT if requires_approval else VersionStatus.CURRENT
                ),
                change_type=change_type.value,
                change_description=change_description,
                parent_version_id=(
                    current_version.version_id if current_version else None
                ),
                created_by=created_by,
                requires_approval=requires_approval,
                metadata=metadata or {},
                tags=tags or [],
                created_at=datetime.utcnow(),
            )

            self.session.add(version)

            # Update current version status if not requiring approval
            if not requires_approval and current_version:
                current_version.status = VersionStatus.SUPERSEDED
                current_version.archived_at = datetime.utcnow()

            # Create history entry
            if current_version:
                history = FileVersionHistory(
                    file_id=file_id,
                    from_version=current_version.version_number,
                    to_version=version_number,
                    change_type=change_type.value,
                    changed_by=created_by,
                    change_reason=change_description,
                    metadata={
                        "size_change": size - current_version.size,
                        "checksum_changed": checksum != current_version.checksum,
                    },
                )
                self.session.add(history)

            self.session.commit()

            # Send alert for critical changes
            if change_type == VersionChangeType.CRITICAL:
                self._send_critical_change_alert(version, current_version)

            logger.info(
                f"Created version {version_number} for file {file_id} - "
                f"Type: {change_type.value}, Size: {size}"
            )

            return version

        except Exception as e:
            logger.error(f"Error creating file version: {e}")
            self.session.rollback()
            raise

    def get_version(
        self,
        file_id: str,
        version_number: Optional[int] = None,
        version_id: Optional[str] = None,
    ) -> Optional[FileVersion]:
        """
        Get a specific file version.

        Args:
            file_id: Base file ID
            version_number: Version number to retrieve
            version_id: Specific version ID

        Returns:
            File version if found
        """
        query = self.session.query(FileVersion).filter(FileVersion.file_id == file_id)

        if version_id:
            query = query.filter(FileVersion.version_id == version_id)
        elif version_number:
            query = query.filter(FileVersion.version_number == version_number)
        else:
            # Get current version
            query = query.filter(FileVersion.status == VersionStatus.CURRENT)

        return query.first()

    def get_version_history(
        self, file_id: str, include_deleted: bool = False, limit: int = 50
    ) -> List[FileVersion]:
        """
        Get version history for a file.

        Args:
            file_id: Base file ID
            include_deleted: Include deleted versions
            limit: Maximum versions to return

        Returns:
            List of file versions
        """
        query = self.session.query(FileVersion).filter(FileVersion.file_id == file_id)

        if not include_deleted:
            query = query.filter(FileVersion.status != VersionStatus.DELETED)

        versions = query.order_by(desc(FileVersion.version_number)).limit(limit).all()

        return versions

    def compare_versions(
        self, file_id: str, version_a: int, version_b: int
    ) -> VersionDiff:
        """
        Compare two versions of a file.

        Args:
            file_id: Base file ID
            version_a: First version number
            version_b: Second version number

        Returns:
            Version differences
        """
        # Get both versions
        v_a = self.get_version(file_id, version_number=version_a)
        v_b = self.get_version(file_id, version_number=version_b)

        if not v_a or not v_b:
            raise ValueError("One or both versions not found")

        # Calculate differences
        size_change = v_b.size - v_a.size
        hash_changed = v_a.checksum != v_b.checksum

        # Find metadata changes
        metadata_changes = {}
        for key in set(v_a.meta_data.keys()) | set(v_b.meta_data.keys()):
            val_a = v_a.meta_data.get(key)
            val_b = v_b.meta_data.get(key)
            if val_a != val_b:
                metadata_changes[key] = {"old": val_a, "new": val_b}

        # Generate summary
        summary_parts = []
        if hash_changed:
            summary_parts.append("Content changed")
        if size_change > 0:
            summary_parts.append(f"Size increased by {size_change} bytes")
        elif size_change < 0:
            summary_parts.append(f"Size decreased by {abs(size_change)} bytes")
        if metadata_changes:
            summary_parts.append(f"{len(metadata_changes)} metadata changes")

        return VersionDiff(
            version_a=version_a,
            version_b=version_b,
            size_change=size_change,
            hash_changed=hash_changed,
            metadata_changes=metadata_changes,
            change_summary=" | ".join(summary_parts) or "No changes",
        )

    def rollback_version(
        self, file_id: str, target_version: int, rolled_back_by: UUID, reason: str
    ) -> FileVersion:
        """
        Rollback to a previous version.

        Args:
            file_id: Base file ID
            target_version: Version to rollback to
            rolled_back_by: User performing rollback
            reason: Reason for rollback

        Returns:
            New version created from rollback
        """
        try:
            # Get target version
            target = self.get_version(file_id, version_number=target_version)
            if not target:
                raise ValueError(f"Version {target_version} not found")

            # Get file data from storage
            file_data, _ = self.storage_manager.retrieve_file(target.storage_path)

            # Get current version before creating new one
            current_version = self._get_current_version(file_id)

            # Create new version as rollback
            new_version = self.create_version(
                file_id=file_id,
                file_data=file_data,
                filename=target.filename,
                created_by=rolled_back_by,
                change_type=VersionChangeType.MAJOR,
                change_description=f"Rollback to version {target_version}: {reason}",
                metadata={
                    **target.meta_data,
                    "rollback_from_version": (
                        current_version.version_number if current_version else 0
                    ),
                    "rollback_to_version": target_version,
                    "rollback_reason": reason,
                },
            )

            # Update history
            current_ver = self._get_current_version(file_id)
            history = FileVersionHistory(
                file_id=file_id,
                from_version=(current_ver.version_number if current_ver else 0),
                to_version=new_version.version_number,
                change_type=VersionChangeType.MAJOR.value,
                changed_by=rolled_back_by,
                change_reason=f"Rollback: {reason}",
                rollback_of=target.version_id,
                metadata={"rollback_target": target_version},
            )
            self.session.add(history)
            self.session.commit()

            logger.info(f"Rolled back file {file_id} to version {target_version}")

            return new_version

        except Exception as e:
            logger.error(f"Error rolling back version: {e}")
            self.session.rollback()
            raise

    def approve_version(
        self, version_id: str, approved_by: UUID, approval_notes: Optional[str] = None
    ) -> FileVersion:
        """
        Approve a pending version.

        Args:
            version_id: Version to approve
            approved_by: User approving
            approval_notes: Approval notes

        Returns:
            Approved version
        """
        try:
            # Get version
            version = (
                self.session.query(FileVersion)
                .filter(FileVersion.version_id == version_id)
                .first()
            )

            if not version:
                raise ValueError(f"Version {version_id} not found")

            if not version.requires_approval:
                raise ValueError("Version does not require approval")

            if version.status != VersionStatus.PENDING_REVIEW:
                raise ValueError(
                    f"Version status is {version.status}, not pending review"
                )

            # Get current version to supersede
            current = self._get_current_version(version.file_id)
            if current:
                current.status = VersionStatus.SUPERSEDED
                current.archived_at = datetime.utcnow()

            # Approve version
            version.status = VersionStatus.CURRENT
            version.approved_by = approved_by
            version.approved_at = datetime.utcnow()
            version.requires_approval = False

            if approval_notes:
                version.meta_data["approval_notes"] = approval_notes

            self.session.commit()

            logger.info(f"Approved version {version_id}")

            return version

        except Exception as e:
            logger.error(f"Error approving version: {e}")
            self.session.rollback()
            raise

    def delete_version(
        self, version_id: str, deleted_by: UUID, reason: str, permanent: bool = False
    ) -> bool:
        """
        Delete a file version.

        Args:
            version_id: Version to delete
            deleted_by: User deleting
            reason: Deletion reason
            permanent: Permanently delete from storage

        Returns:
            Success status
        """
        try:
            version = (
                self.session.query(FileVersion)
                .filter(FileVersion.version_id == version_id)
                .first()
            )

            if not version:
                return False

            if version.is_locked:
                raise ValueError("Cannot delete locked version")

            if version.status == VersionStatus.CURRENT:
                raise ValueError("Cannot delete current version")

            if permanent:
                # Delete from storage
                self.storage_manager.delete_file(
                    version.storage_path, permanent=True, deleted_by=deleted_by
                )

                # Delete record
                self.session.delete(version)
            else:
                # Soft delete
                version.status = VersionStatus.DELETED
                version.meta_data["deleted_by"] = str(deleted_by)
                version.meta_data["deleted_reason"] = reason
                version.meta_data["deleted_at"] = datetime.utcnow().isoformat()

            self.session.commit()

            logger.info(f"Deleted version {version_id} - Permanent: {permanent}")

            return True

        except (ValueError, AttributeError, KeyError) as e:
            logger.error(f"Error deleting version: {e}")
            self.session.rollback()
            return False

    def lock_version(self, version_id: str, locked_by: UUID, reason: str) -> bool:
        """
        Lock a version to prevent modifications.

        Args:
            version_id: Version to lock
            locked_by: User locking
            reason: Lock reason

        Returns:
            Success status
        """
        try:
            version = (
                self.session.query(FileVersion)
                .filter(FileVersion.version_id == version_id)
                .first()
            )

            if not version:
                return False

            version.is_locked = True
            version.meta_data["locked_by"] = str(locked_by)
            version.meta_data["locked_reason"] = reason
            version.meta_data["locked_at"] = datetime.utcnow().isoformat()

            self.session.commit()

            logger.info(f"Locked version {version_id}")

            return True

        except (ValueError, AttributeError, KeyError) as e:
            logger.error(f"Error locking version: {e}")
            self.session.rollback()
            return False

    def archive_old_versions(
        self, file_id: Optional[str] = None, older_than_days: Optional[int] = None
    ) -> int:
        """
        Archive old versions.

        Args:
            file_id: Specific file to archive versions for
            older_than_days: Archive versions older than X days

        Returns:
            Number of versions archived
        """
        try:
            older_than_days = older_than_days or self.AUTO_ARCHIVE_AFTER_DAYS
            cutoff_date = datetime.utcnow() - timedelta(days=older_than_days)

            query = self.session.query(FileVersion).filter(
                FileVersion.status == VersionStatus.SUPERSEDED,
                FileVersion.created_at < cutoff_date,
                FileVersion.archived_at.is_(None),
            )

            if file_id:
                query = query.filter(FileVersion.file_id == file_id)

            versions = query.all()

            archived_count = 0
            for version in versions:
                # Don't archive if it's the only old version
                history = self.get_version_history(version.file_id, limit=2)
                if len(history) > 1:
                    version.status = VersionStatus.ARCHIVED
                    version.archived_at = datetime.utcnow()
                    archived_count += 1

            self.session.commit()

            logger.info(f"Archived {archived_count} old versions")

            return archived_count

        except (ValueError, AttributeError, KeyError) as e:
            logger.error(f"Error archiving versions: {e}")
            self.session.rollback()
            return 0

    def _get_current_version(self, file_id: str) -> Optional[FileVersion]:
        """Get current version of a file."""
        return (
            self.session.query(FileVersion)
            .filter(
                FileVersion.file_id == file_id,
                FileVersion.status == VersionStatus.CURRENT,
            )
            .first()
        )

    def _calculate_checksum(self, file_data: BinaryIO) -> str:
        """Calculate SHA-256 checksum of file data."""
        file_data.seek(0)
        sha256_hash = hashlib.sha256()

        for chunk in iter(lambda: file_data.read(8192), b""):
            sha256_hash.update(chunk)

        file_data.seek(0)
        return sha256_hash.hexdigest()

    def _send_critical_change_alert(
        self, new_version: FileVersion, old_version: Optional[FileVersion]
    ) -> None:
        """Send alert for critical file changes."""
        try:
            message = (
                f"Critical file change detected:\n"
                f"File ID: {new_version.file_id}\n"
                f"Version: {new_version.version_number}\n"
                f"Changed by: {new_version.created_by}\n"
                f"Description: {new_version.change_description or 'No description'}"
            )

            if old_version:
                message += f"\nPrevious version: {old_version.version_number}"

            # Log significant change alert
            logger.warning(
                f"Significant change alert: {message}",
                extra={
                    "file_id": new_version.file_id,
                    "version_id": new_version.version_id,
                    "change_type": new_version.change_type,
                },
            )

        except (KeyError, ValueError, AttributeError) as e:
            logger.error(f"Error sending critical change alert: {e}")

    def get_storage_usage(self, file_id: str) -> Dict[str, Any]:
        """
        Get storage usage for all versions of a file.

        Args:
            file_id: Base file ID

        Returns:
            Storage usage statistics
        """
        versions = (
            self.session.query(FileVersion).filter(FileVersion.file_id == file_id).all()
        )

        total_size = sum(v.size for v in versions)
        active_size = sum(
            v.size
            for v in versions
            if v.status not in [VersionStatus.DELETED, VersionStatus.ARCHIVED]
        )

        return {
            "total_versions": len(versions),
            "total_size_bytes": total_size,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "active_size_bytes": active_size,
            "active_size_mb": round(active_size / (1024 * 1024), 2),
            "archived_versions": sum(
                1 for v in versions if v.status == VersionStatus.ARCHIVED
            ),
            "deleted_versions": sum(
                1 for v in versions if v.status == VersionStatus.DELETED
            ),
        }

    def cleanup_versions(
        self, file_id: str, keep_versions: int = 10, force: bool = False
    ) -> int:
        """
        Clean up old versions keeping only recent ones.

        Args:
            file_id: Base file ID
            keep_versions: Number of versions to keep
            force: Force cleanup even for locked versions

        Returns:
            Number of versions cleaned up
        """
        try:
            # Get all versions sorted by version number
            versions = (
                self.session.query(FileVersion)
                .filter(FileVersion.file_id == file_id)
                .order_by(desc(FileVersion.version_number))
                .all()
            )

            if len(versions) <= keep_versions:
                return 0

            # Keep the specified number of recent versions
            versions_to_delete = versions[keep_versions:]

            deleted_count = 0
            for version in versions_to_delete:
                if version.is_locked and not force:
                    continue

                if version.status == VersionStatus.CURRENT:
                    continue

                # Delete from storage and database
                if self.delete_version(
                    version.version_id,
                    deleted_by=UUID(
                        "00000000-0000-0000-0000-000000000000"
                    ),  # System user
                    reason="Automatic cleanup",
                    permanent=True,
                ):
                    deleted_count += 1

            logger.info(f"Cleaned up {deleted_count} versions for file {file_id}")

            return deleted_count

        except (ValueError, AttributeError, TypeError) as e:
            logger.error(f"Error cleaning up versions: {e}")
            return 0
