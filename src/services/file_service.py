"""File management service for handling file uploads, downloads, and metadata.

This service provides methods for managing file attachments including
upload, download, virus scanning integration, and access control.
"""

import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import and_
from sqlalchemy.orm import Session

from src.models.access_log import AccessContext, AccessLog, AccessType
from src.models.file_attachment import FileAccessLevel, FileAttachment, FileStatus
from src.services.base import BaseService
from src.utils.logging import get_logger

logger = get_logger(__name__)


class FileService(BaseService[FileAttachment]):
    """Service for managing file attachments."""

    def __init__(self, db: Session):
        """Initialize file service."""
        super().__init__(db)
        self.db = db
        self.access_context = AccessContext.API

    def create_file_attachment(
        self,
        filename: str,
        content_type: str,
        size: int,
        storage_key: str,
        file_hash: str,
        patient_id: Optional[uuid.UUID] = None,
        record_id: Optional[uuid.UUID] = None,
        access_level: str = "private",
        title: Optional[str] = None,
        description: Optional[str] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> FileAttachment:
        """Create a new file attachment record."""
        try:
            # Create file attachment
            file_attachment = FileAttachment(
                filename=filename,
                original_filename=filename,
                content_type=content_type,
                size=size,
                file_hash=file_hash,
                storage_key=storage_key,
                status=FileStatus.PROCESSING,
                access_level=FileAccessLevel[access_level.upper()],
                patient_id=patient_id,
                record_id=record_id,
                uploaded_by=self.current_user_id,
                title=title,
                description=description,
                tags=tags or [],
                metadata=metadata or {},
                upload_ip=metadata.get("ip_address") if metadata else None,
                user_agent=metadata.get("user_agent") if metadata else None,
            )

            self.db.add(file_attachment)
            self.db.flush()

            # Log file creation
            self.log_access(
                resource_type="file_attachment",
                resource_id=file_attachment.id,
                access_type=AccessType.CREATE,
                purpose=f"Uploaded file: {filename}",
            )

            logger.info(
                f"Created file attachment {file_attachment.id} for patient {patient_id}"
            )
            return file_attachment

        except Exception as e:
            logger.error(f"Error creating file attachment: {e}")
            raise

    def get_by_hash(self, file_hash: str) -> Optional[FileAttachment]:
        """Get file attachment by hash."""
        return (
            self.db.query(FileAttachment)
            .filter(
                and_(
                    FileAttachment.file_hash == file_hash,
                    FileAttachment.deleted_at.is_(None),
                    FileAttachment.status != FileStatus.DELETED,
                )
            )
            .first()
        )

    def get_patient_files(
        self,
        patient_id: uuid.UUID,
        include_deleted: bool = False,
        file_types: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
    ) -> List[FileAttachment]:
        """Get all files for a patient."""
        query = self.db.query(FileAttachment).filter(
            FileAttachment.patient_id == patient_id
        )

        if not include_deleted:
            query = query.filter(
                and_(
                    FileAttachment.deleted_at.is_(None),
                    FileAttachment.status != FileStatus.DELETED,
                )
            )

        if file_types:
            query = query.filter(FileAttachment.content_type.in_(file_types))

        if tags:
            # Filter by tags (assuming PostgreSQL array operations)
            for tag in tags:
                query = query.filter(FileAttachment.tags.contains([tag]))

        return query.order_by(FileAttachment.created_at.desc()).all()

    def get_record_files(
        self, record_id: uuid.UUID, include_deleted: bool = False
    ) -> List[FileAttachment]:
        """Get all files attached to a health record."""
        query = self.db.query(FileAttachment).filter(
            FileAttachment.record_id == record_id
        )

        if not include_deleted:
            query = query.filter(
                and_(
                    FileAttachment.deleted_at.is_(None),
                    FileAttachment.status != FileStatus.DELETED,
                )
            )

        return query.order_by(FileAttachment.created_at.desc()).all()

    def can_access_file(self, file_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        """Check if user can access a file."""
        file_attachment = self.get_by_id(file_id)
        if not file_attachment:
            return False

        # Check if user uploaded the file
        if file_attachment.uploaded_by == user_id:
            return True

        # Check if user has admin role
        if self.current_user_role in ["admin", "super_admin"]:
            return True

        # Check if user has access to the patient
        if file_attachment.patient_id:
            # In production, would check patient access permissions
            return True

        # Check if file is public
        if file_attachment.access_level == FileAccessLevel.PUBLIC:
            return True

        return False

    def can_delete_file(self, file_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        """Check if user can delete a file."""
        file_attachment = self.get_by_id(file_id)
        if not file_attachment:
            return False

        # Only uploader or admin can delete
        return file_attachment.uploaded_by == user_id or self.current_user_role in [
            "admin",
            "super_admin",
        ]

    def update_scan_status(
        self, file_id: uuid.UUID, scan_status: str, scan_result: Dict[str, Any]
    ) -> bool:
        """Update virus scan status for a file."""
        try:
            file_attachment = self.get_by_id(file_id)
            if not file_attachment:
                return False

            file_attachment.virus_scan_status = scan_status
            file_attachment.virus_scan_result = scan_result
            file_attachment.virus_scan_date = datetime.utcnow()

            if scan_status == "clean":
                file_attachment.status = FileStatus.AVAILABLE
            elif scan_status == "infected":
                file_attachment.status = FileStatus.QUARANTINED

            self.db.flush()
            return True

        except (ValueError, AttributeError) as e:
            logger.error(f"Error updating scan status: {e}")
            return False

    def quarantine_file(self, file_id: uuid.UUID, reason: str) -> bool:
        """Quarantine a file."""
        try:
            file_attachment = self.get_by_id(file_id)
            if not file_attachment:
                return False

            file_attachment.mark_as_quarantined(reason)

            # Log quarantine action
            self.log_access(
                resource_type="file_attachment",
                resource_id=file_id,
                access_type=AccessType.UPDATE,
                purpose=f"File quarantined: {reason}",
            )

            self.db.flush()
            return True

        except (ValueError, AttributeError) as e:
            logger.error(f"Error quarantining file: {e}")
            return False

    def log_file_access(
        self,
        file_id: uuid.UUID,
        accessed_by: uuid.UUID,
        purpose: str,
        download: bool = False,
    ) -> None:
        """Log file access."""
        try:
            file_attachment = self.get_by_id(file_id)
            if not file_attachment:
                return

            # Update file access metrics
            if download:
                file_attachment.increment_download_count()
            else:
                file_attachment.increment_access_count()

            # Create access log entry
            access_log = AccessLog(
                user_id=accessed_by,
                resource_type="file_attachment",
                resource_id=file_id,
                access_type=AccessType.VIEW,
                access_context=self.access_context,
                purpose=purpose,
                ip_address=None,  # Would be set from request context
                user_agent=None,  # Would be set from request context
                session_id=None,
                granted=True,
            )

            self.db.add(access_log)
            self.db.flush()

        except (ValueError, KeyError) as e:
            logger.error(f"Error logging file access: {e}")

    def add_tags(self, file_id: uuid.UUID, tags: List[str]) -> bool:
        """Add tags to a file."""
        try:
            file_attachment = self.get_by_id(file_id)
            if not file_attachment:
                return False

            # Merge new tags with existing
            existing_tags = set(file_attachment.tags or [])
            new_tags = existing_tags.union(set(tags))
            file_attachment.tags = list(new_tags)

            self.db.flush()
            return True

        except (ValueError, KeyError) as e:
            logger.error(f"Error adding tags: {e}")
            return False

    def remove_tags(self, file_id: uuid.UUID, tags: List[str]) -> bool:
        """Remove tags from a file."""
        try:
            file_attachment = self.get_by_id(file_id)
            if not file_attachment:
                return False

            # Remove specified tags
            existing_tags = set(file_attachment.tags or [])
            tags_to_remove = set(tags)
            file_attachment.tags = list(existing_tags - tags_to_remove)

            self.db.flush()
            return True

        except (ValueError, KeyError) as e:
            logger.error(f"Error removing tags: {e}")
            return False

    def update_metadata(
        self, file_id: uuid.UUID, metadata: Dict[str, Any], merge: bool = True
    ) -> bool:
        """Update file metadata."""
        try:
            file_attachment = self.get_by_id(file_id)
            if not file_attachment:
                return False

            if merge:
                # Merge with existing metadata
                existing_metadata = file_attachment.metadata or {}
                existing_metadata.update(metadata)
                file_attachment.metadata = existing_metadata
            else:
                # Replace metadata
                file_attachment.metadata = metadata

            self.db.flush()
            return True

        except (ValueError, KeyError) as e:
            logger.error(f"Error updating metadata: {e}")
            return False

    def set_retention_date(self, file_id: uuid.UUID, retention_days: int) -> bool:
        """Set retention date for a file."""
        try:
            file_attachment = self.get_by_id(file_id)
            if not file_attachment:
                return False

            file_attachment.retention_date = datetime.utcnow() + timedelta(
                days=retention_days
            )

            self.db.flush()
            return True

        except (ValueError, KeyError) as e:
            logger.error(f"Error setting retention date: {e}")
            return False

    def archive_file(self, file_id: uuid.UUID) -> bool:
        """Archive a file."""
        try:
            file_attachment = self.get_by_id(file_id)
            if not file_attachment:
                return False

            file_attachment.archived = True
            file_attachment.archive_date = datetime.utcnow()

            # Log archive action
            self.log_access(
                resource_type="file_attachment",
                resource_id=file_id,
                access_type=AccessType.UPDATE,
                purpose="File archived",
            )

            self.db.flush()
            return True

        except (ValueError, KeyError) as e:
            logger.error(f"Error archiving file: {e}")
            return False

    def get_expired_files(self, limit: int = 100) -> List[FileAttachment]:
        """Get files that have expired."""
        return (
            self.db.query(FileAttachment)
            .filter(
                and_(
                    FileAttachment.expires_at <= datetime.utcnow(),
                    FileAttachment.deleted_at.is_(None),
                    FileAttachment.status != FileStatus.DELETED,
                )
            )
            .limit(limit)
            .all()
        )

    def get_files_for_deletion(self, limit: int = 100) -> List[FileAttachment]:
        """Get files that have passed their retention date."""
        return (
            self.db.query(FileAttachment)
            .filter(
                and_(
                    FileAttachment.retention_date <= datetime.utcnow(),
                    FileAttachment.deleted_at.is_(None),
                    FileAttachment.status != FileStatus.DELETED,
                )
            )
            .limit(limit)
            .all()
        )

    def cleanup_expired_files(self) -> int:
        """Clean up expired files."""
        try:
            expired_files = self.get_expired_files()
            count = 0

            for file_attachment in expired_files:
                if self.delete(file_attachment.id, hard=False):
                    count += 1
                    logger.info(f"Cleaned up expired file: {file_attachment.id}")

            return count

        except (ValueError, OSError) as e:
            logger.error(f"Error cleaning up expired files: {e}")
            return 0
