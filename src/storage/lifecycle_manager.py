"""Storage lifecycle management for file retention policies.

Note: This module handles PHI-related file lifecycle management.
- Access Control: Implement role-based access control (RBAC) for lifecycle management operations
"""

from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List

from sqlalchemy import or_
from sqlalchemy.orm import Session

from src.models.file_attachment import FileAttachment, FileStatus
from src.storage.base import FileCategory
from src.utils.logging import get_logger

logger = get_logger(__name__)


class RetentionPolicy(Enum):
    """File retention policies."""

    PERMANENT = "permanent"  # Never delete
    SEVEN_YEARS = "seven_years"  # Standard medical record retention
    THREE_YEARS = "three_years"  # Administrative documents
    ONE_YEAR = "one_year"  # Temporary files
    SIX_MONTHS = "six_months"  # Short-term files
    THIRTY_DAYS = "thirty_days"  # Very temporary files


class LifecycleStatus(Enum):
    """File lifecycle status."""

    ACTIVE = "active"  # Frequently accessed
    ARCHIVED = "archived"  # Moved to cheaper storage
    PENDING_DELETION = "pending_deletion"  # Marked for deletion
    DELETED = "deleted"  # Soft deleted


class StorageLifecycleManager:
    """Manages file lifecycle and retention policies.

    All medical records and PHI data must be encrypted at rest
    and during transitions between storage tiers.
    """

    # Default retention policies by category
    DEFAULT_RETENTION_POLICIES = {
        FileCategory.MEDICAL_RECORD: RetentionPolicy.SEVEN_YEARS,
        FileCategory.LAB_RESULT: RetentionPolicy.SEVEN_YEARS,
        FileCategory.IMAGING: RetentionPolicy.SEVEN_YEARS,
        FileCategory.PRESCRIPTION: RetentionPolicy.SEVEN_YEARS,
        FileCategory.VACCINATION: RetentionPolicy.PERMANENT,
        FileCategory.INSURANCE: RetentionPolicy.THREE_YEARS,
        FileCategory.IDENTIFICATION: RetentionPolicy.PERMANENT,
        FileCategory.CONSENT_FORM: RetentionPolicy.SEVEN_YEARS,
        FileCategory.CLINICAL_NOTE: RetentionPolicy.SEVEN_YEARS,
        FileCategory.VOICE_RECORDING: RetentionPolicy.THREE_YEARS,
        FileCategory.OTHER: RetentionPolicy.THREE_YEARS,
    }

    # Days to keep files before archiving (by category)
    ARCHIVE_AFTER_DAYS = {
        FileCategory.MEDICAL_RECORD: 365,  # 1 year
        FileCategory.LAB_RESULT: 180,  # 6 months
        FileCategory.IMAGING: 90,  # 3 months
        FileCategory.PRESCRIPTION: 365,  # 1 year
        FileCategory.VACCINATION: 730,  # 2 years
        FileCategory.INSURANCE: 365,  # 1 year
        FileCategory.IDENTIFICATION: 730,  # 2 years
        FileCategory.CONSENT_FORM: 365,  # 1 year
        FileCategory.CLINICAL_NOTE: 180,  # 6 months
        FileCategory.VOICE_RECORDING: 90,  # 3 months
        FileCategory.OTHER: 180,  # 6 months
    }

    def __init__(self, session: Session):
        """Initialize lifecycle manager.

        Args:
            session: Database session
        """
        self.session = session

    def get_retention_policy(self, category: FileCategory) -> RetentionPolicy:
        """Get retention policy for a file category.

        Args:
            category: File category

        Returns:
            Retention policy
        """
        return self.DEFAULT_RETENTION_POLICIES.get(
            category, RetentionPolicy.THREE_YEARS
        )

    def get_retention_date(
        self, category: FileCategory, created_at: datetime
    ) -> datetime:
        """Calculate retention date for a file.

        Args:
            category: File category
            created_at: File creation date

        Returns:
            Date when file can be deleted
        """
        policy = self.get_retention_policy(category)

        if policy == RetentionPolicy.PERMANENT:
            # Far future date for permanent files
            return created_at + timedelta(days=36500)  # 100 years
        elif policy == RetentionPolicy.SEVEN_YEARS:
            return created_at + timedelta(days=2555)  # 7 years
        elif policy == RetentionPolicy.THREE_YEARS:
            return created_at + timedelta(days=1095)  # 3 years
        elif policy == RetentionPolicy.ONE_YEAR:
            return created_at + timedelta(days=365)
        elif policy == RetentionPolicy.SIX_MONTHS:
            return created_at + timedelta(days=180)
        elif policy == RetentionPolicy.THIRTY_DAYS:
            return created_at + timedelta(days=30)

        # All retention policies are covered above
        raise ValueError(f"Unknown retention policy: {policy}")

    def should_archive(self, file: FileAttachment) -> bool:
        """Check if file should be archived.

        Args:
            file: File attachment

        Returns:
            True if file should be archived
        """
        if file.lifecycle_status == LifecycleStatus.ARCHIVED.value:
            return False

        archive_days = self.ARCHIVE_AFTER_DAYS.get(FileCategory(file.category), 180)
        archive_date = file.created_at + timedelta(days=archive_days)

        # Archive if past archive date and not accessed recently
        if datetime.utcnow() > archive_date:
            # Check last access (30 days)
            if file.last_accessed_at:
                days_since_access = (datetime.utcnow() - file.last_accessed_at).days
                return bool(days_since_access > 30)
            return True

        return False

    def should_delete(self, file: FileAttachment) -> bool:
        """Check if file should be deleted based on retention policy.

        Args:
            file: File attachment

        Returns:
            True if file should be deleted
        """
        # Use file's created_at timestamp
        created_at = file.created_at or datetime.utcnow()
        # Ensure created_at is a datetime instance
        if not isinstance(created_at, datetime):
            created_at = datetime.utcnow()
        retention_date = self.get_retention_date(
            FileCategory(file.category), created_at
        )
        return datetime.utcnow() > retention_date

    def process_lifecycle_policies(self, batch_size: int = 100) -> Dict[str, List[str]]:
        """Process files according to lifecycle policies.

        Args:
            batch_size: Number of files to process at once

        Returns:
            Dictionary with lists of file IDs by action taken
        """
        results: Dict[str, List[str]] = {
            "archived": [],
            "marked_for_deletion": [],
            "errors": [],
        }

        try:
            # Get active files to check
            active_files = (
                self.session.query(FileAttachment)
                .filter(
                    FileAttachment.status == FileStatus.AVAILABLE,
                    or_(
                        FileAttachment.lifecycle_status.is_(None),
                        FileAttachment.lifecycle_status == LifecycleStatus.ACTIVE.value,
                    ),
                )
                .limit(batch_size)
                .all()
            )

            for file in active_files:
                try:
                    # Check if should archive
                    if self.should_archive(file):
                        file.lifecycle_status = LifecycleStatus.ARCHIVED.value
                        file.lifecycle_metadata = file.lifecycle_metadata or {}
                        file.lifecycle_metadata["archived_at"] = (
                            datetime.utcnow().isoformat()
                        )
                        results["archived"].append(str(file.id))
                        logger.info(f"Archived file {file.id}")

                    # Check if should delete
                    elif self.should_delete(file):
                        file.lifecycle_status = LifecycleStatus.PENDING_DELETION.value
                        file.lifecycle_metadata = file.lifecycle_metadata or {}
                        file.lifecycle_metadata["marked_for_deletion_at"] = (
                            datetime.utcnow().isoformat()
                        )
                        results["marked_for_deletion"].append(str(file.id))
                        logger.info(f"Marked file {file.id} for deletion")

                except (ValueError, AttributeError) as e:
                    logger.error(f"Error processing file {file.id}: {e}")
                    results["errors"].append(str(file.id))

            self.session.commit()

        except (ValueError, RuntimeError) as e:
            logger.error(f"Error in lifecycle processing: {e}")
            self.session.rollback()

        return results

    def archive_files(self, file_ids: List[str]) -> int:
        """Archive specific files to cheaper storage.

        Args:
            file_ids: List of file IDs to archive

        Returns:
            Number of files archived
        """
        count = 0
        for file_id in file_ids:
            file = (
                self.session.query(FileAttachment)
                .filter(FileAttachment.id == file_id)
                .first()
            )

            if file and file.lifecycle_status != LifecycleStatus.ARCHIVED.value:
                file.lifecycle_status = LifecycleStatus.ARCHIVED.value
                file.lifecycle_metadata = file.lifecycle_metadata or {}
                file.lifecycle_metadata["archived_at"] = datetime.utcnow().isoformat()
                count += 1

        self.session.commit()
        return count

    def restore_from_archive(self, file_id: str) -> bool:
        """Restore a file from archive to active storage.

        Args:
            file_id: File ID to restore

        Returns:
            True if restored successfully
        """
        file = (
            self.session.query(FileAttachment)
            .filter(FileAttachment.id == file_id)
            .first()
        )

        if file and file.lifecycle_status == LifecycleStatus.ARCHIVED.value:
            file.lifecycle_status = LifecycleStatus.ACTIVE.value
            file.lifecycle_metadata = file.lifecycle_metadata or {}
            file.lifecycle_metadata["restored_at"] = datetime.utcnow().isoformat()
            file.last_accessed_at = datetime.utcnow()
            self.session.commit()
            return True

        return False

    def get_lifecycle_statistics(self) -> Dict[str, Any]:
        """Get statistics about file lifecycle states.

        Returns:
            Dictionary with lifecycle statistics
        """
        stats: Dict[str, Any] = {
            "total_files": self.session.query(FileAttachment).count(),
            "by_status": {},
            "by_category": {},
            "pending_actions": {
                "to_archive": 0,
                "to_delete": 0,
            },
        }

        # Count by lifecycle status
        for status in LifecycleStatus:
            count = (
                self.session.query(FileAttachment)
                .filter(FileAttachment.lifecycle_status == status.value)
                .count()
            )
            stats["by_status"][status.value] = count

        # Count by category
        for category in FileCategory:
            count = (
                self.session.query(FileAttachment)
                .filter(FileAttachment.category == category.value)
                .count()
            )
            stats["by_category"][category.value] = count

        return stats
