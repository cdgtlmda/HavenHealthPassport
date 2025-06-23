"""Types for voice data retention functionality."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Set


class RetentionAction(Enum):
    """Actions to take when retention period expires."""

    DELETE = "delete"
    ARCHIVE = "archive"
    ANONYMIZE = "anonymize"
    REVIEW = "review"
    EXTEND = "extend"


class ArchiveStatus(Enum):
    """Status of archived data."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    VERIFIED = "verified"
    RESTORED = "restored"


class DataLifecycleStage(Enum):
    """Stages in voice data lifecycle."""

    ACTIVE = "active"  # Currently in use
    INACTIVE = "inactive"  # Not accessed recently
    ARCHIVED = "archived"  # Moved to archive storage
    SCHEDULED_DELETION = "scheduled_deletion"  # Marked for deletion
    DELETED = "deleted"  # Permanently deleted
    RESTORED = "restored"  # Restored from archive


@dataclass
class RetentionPolicy:
    """Defines retention policy for voice data."""

    policy_id: str
    name: str
    description: str
    data_types: Set[Any]  # VoiceDataType from voice_privacy_controls
    purposes: Set[Any]  # ProcessingPurpose from voice_privacy_controls
    retention_period: Any  # RetentionPeriod from voice_privacy_controls
    action_on_expiry: RetentionAction
    archive_after_days: Optional[int] = None
    legal_hold: bool = False
    review_required: bool = False
    auto_extend_conditions: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def applies_to(self, data_type: Any, purpose: Any) -> bool:
        """Check if policy applies to given data type and purpose."""
        return data_type in self.data_types and purpose in self.purposes

    def should_archive(self, age_days: int) -> bool:
        """Check if data should be archived based on age."""
        if self.archive_after_days is None:
            return False
        return age_days >= self.archive_after_days


@dataclass
class DataLifecycleRecord:
    """Tracks lifecycle of voice data."""

    record_id: str
    data_record_id: str
    user_id: str
    data_type: Any  # VoiceDataType from voice_privacy_controls
    current_stage: DataLifecycleStage
    created_at: datetime
    last_accessed: datetime
    archived_at: Optional[datetime] = None
    deletion_scheduled_at: Optional[datetime] = None
    deleted_at: Optional[datetime] = None
    archive_location: Optional[str] = None
    size_bytes: int = 0
    access_count: int = 0
    policy_id: Optional[str] = None

    def update_access(self) -> None:
        """Update last access time and count."""
        self.last_accessed = datetime.now()
        self.access_count += 1

    def transition_to(self, new_stage: DataLifecycleStage) -> None:
        """Transition to new lifecycle stage."""
        self.current_stage = new_stage

        if new_stage == DataLifecycleStage.ARCHIVED:
            self.archived_at = datetime.now()
        elif new_stage == DataLifecycleStage.SCHEDULED_DELETION:
            self.deletion_scheduled_at = datetime.now()
        elif new_stage == DataLifecycleStage.DELETED:
            self.deleted_at = datetime.now()


@dataclass
class ArchiveJob:
    """Represents an archival job."""

    job_id: str
    user_id: str
    data_records: List[str]  # Record IDs
    status: ArchiveStatus
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    archive_path: Optional[str] = None
    checksum: Optional[str] = None
    error_message: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
