"""Voice Data Retention Module.

This module implements comprehensive data retention policies for voice data in the Haven Health Passport system,
including automated cleanup, archival strategies, compliance monitoring, and lifecycle management.
"""

import asyncio
import hashlib
import io
import json
import logging
import tarfile
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from src.audit.audit_logger import AuditEventType, AuditLogger
from src.compliance.regulatory_compliance import RegulatoryCompliance
from src.healthcare.hipaa_access_control import (
    AccessLevel,
    audit_phi_access,
    require_phi_access,
)
from src.monitoring.metrics import MetricsCollector
from src.services.encryption_service import EncryptionService
from src.storage.archive_storage import ArchiveStorage
from src.storage.secure_storage import SecureStorage
from src.voice.interface.voice_privacy_controls import (
    ProcessingPurpose,
    RetentionPeriod,
    VoiceDataRecord,
    VoiceDataType,
)

from .retention_types import (
    ArchiveJob,
    ArchiveStatus,
    DataLifecycleRecord,
    DataLifecycleStage,
    RetentionAction,
    RetentionPolicy,
)

logger = logging.getLogger(__name__)


class RetentionPolicyManager:
    """Manager for retention policies."""

    def __init__(self) -> None:
        """Initialize the retention policy manager."""
        self.policies: Dict[str, RetentionPolicy] = {}
        self._initialize_default_policies()

    def _initialize_default_policies(self) -> None:
        """Initialize default policies."""
        # GDPR standard policy
        gdpr_policy = RetentionPolicy(
            policy_id="gdpr_standard",
            name="GDPR Standard Retention",
            description="Standard GDPR retention policy",
            data_types={
                VoiceDataType.AUDIO_RECORDING,
                VoiceDataType.TRANSCRIPTION,
                VoiceDataType.VOICE_PRINT,
            },
            purposes={
                ProcessingPurpose.HEALTH_MONITORING,
                ProcessingPurpose.TRANSCRIPTION,
                ProcessingPurpose.AUTHENTICATION,
            },
            retention_period=RetentionPeriod.ONE_YEAR,
            action_on_expiry=RetentionAction.DELETE,
            archive_after_days=180,
        )
        self.policies["gdpr_standard"] = gdpr_policy

    def get_policy(self, policy_id: str) -> Optional[RetentionPolicy]:
        """Get a policy by ID."""
        return self.policies.get(policy_id)

    def find_applicable_policy(
        self, data_type: Any, purpose: Any
    ) -> Optional[RetentionPolicy]:
        """Find an applicable policy for the given data type and purpose."""
        for policy in self.policies.values():
            if policy.applies_to(data_type, purpose):
                return policy
        return None


class VoiceDataRetentionManager:
    """Main manager for voice data retention."""

    def __init__(
        self,
        storage: Optional[SecureStorage] = None,
        archive_storage: Optional[ArchiveStorage] = None,
        encryption_service: Optional[EncryptionService] = None,
        audit_logger: Optional[AuditLogger] = None,
        metrics_collector: Optional[MetricsCollector] = None,
    ):
        """Initialize the voice data retention manager.

        Args:
            storage: Secure storage service for primary data
            archive_storage: Archive storage service for long-term retention
            encryption_service: Service for data encryption
            audit_logger: Logger for audit events
            metrics_collector: Collector for operational metrics
        """
        self.storage = storage
        self.archive_storage = archive_storage
        self.encryption_service = encryption_service
        self.audit_logger = audit_logger
        self.metrics = metrics_collector

        # Managers
        self.policy_manager = RetentionPolicyManager()

        # Lifecycle tracking
        self.lifecycle_records: Dict[str, DataLifecycleRecord] = {}

        # Archive jobs
        self.archive_jobs: Dict[str, ArchiveJob] = {}

        # Configuration
        self.batch_size = 100
        self.archive_compression_level = 6
        self.deletion_grace_period_hours = 24
        self.inactive_threshold_days = 30

    @require_phi_access(AccessLevel.WRITE)
    @audit_phi_access(action="apply_voice_retention_policy")
    async def apply_retention_policy(
        self, data_record: VoiceDataRecord, policy_override: Optional[str] = None
    ) -> DataLifecycleRecord:
        """Apply retention policy to a data record."""
        # Find applicable policy
        if policy_override:
            policy = self.policy_manager.get_policy(policy_override)
        else:
            policy = self.policy_manager.find_applicable_policy(
                data_record.data_type, data_record.purpose
            )

        if not policy:
            logger.warning(
                "No retention policy found for %s/%s",
                data_record.data_type,
                data_record.purpose,
            )
            policy = self.policy_manager.get_policy("gdpr_standard")  # Default
            if not policy:
                raise ValueError("No default retention policy available")

        # Create lifecycle record
        lifecycle_record = DataLifecycleRecord(
            record_id=f"lifecycle_{data_record.record_id}",
            data_record_id=data_record.record_id,
            user_id=data_record.user_id,
            data_type=data_record.data_type,
            current_stage=DataLifecycleStage.ACTIVE,
            created_at=data_record.collected_at,
            last_accessed=data_record.collected_at,
            size_bytes=data_record.data_size_bytes or 0,
            policy_id=policy.policy_id,
        )

        # Store lifecycle record
        self.lifecycle_records[data_record.record_id] = lifecycle_record

        # Set retention period on data record
        data_record.retention_period = policy.retention_period
        data_record.deletion_date = data_record.calculate_deletion_date()

        # Log policy application
        if self.audit_logger:
            await self.audit_logger.log_event(
                AuditEventType.RETENTION_POLICY_APPLIED,
                user_id=data_record.user_id,
                details={
                    "record_id": data_record.record_id,
                    "policy_id": policy.policy_id,
                    "retention_period": policy.retention_period.name,
                    "deletion_date": (
                        data_record.deletion_date.isoformat()
                        if data_record.deletion_date
                        else None
                    ),
                },
            )

        return lifecycle_record

    @require_phi_access(AccessLevel.DELETE)
    @audit_phi_access(action="process_voice_retention_tasks")
    async def process_retention_tasks(self) -> Dict[str, int]:
        """Process all retention tasks (archival, deletion, etc.)."""
        stats = {"archived": 0, "deleted": 0, "reviewed": 0, "extended": 0, "errors": 0}

        # Process in batches
        batch = []

        for _, lifecycle_record in self.lifecycle_records.items():
            batch.append(lifecycle_record)

            if len(batch) >= self.batch_size:
                batch_stats = await self._process_batch(batch)
                for key in stats:
                    stats[key] += batch_stats.get(key, 0)
                batch = []

        # Process remaining
        if batch:
            batch_stats = await self._process_batch(batch)
            for key in stats:
                stats[key] += batch_stats.get(key, 0)

        # Log stats
        logger.info("Retention processing complete: %s", stats)

        # Record metrics
        if self.metrics:
            for action, count in stats.items():
                self.metrics.record_metric(f"voice_retention_{action}", float(count))

        return stats

    async def _process_batch(
        self, records: List[DataLifecycleRecord]
    ) -> Dict[str, int]:
        """Process a batch of lifecycle records."""
        stats = {"archived": 0, "deleted": 0, "reviewed": 0, "extended": 0, "errors": 0}

        for record in records:
            try:
                # Get policy
                if not record.policy_id:
                    continue
                policy = self.policy_manager.get_policy(record.policy_id)
                if not policy:
                    continue

                # Check if action needed
                age_days = (datetime.now() - record.created_at).days

                # Archive if needed
                if (
                    policy.should_archive(age_days)
                    and record.current_stage == DataLifecycleStage.ACTIVE
                ):
                    success = await self._archive_data(record)
                    if success:
                        stats["archived"] += 1

                # Check retention expiry
                if self._should_expire(record, policy):
                    action_taken = await self._handle_expiry(record, policy)
                    if action_taken:
                        stats[action_taken] += 1

                # Check for inactive data
                if self._is_inactive(record):
                    record.transition_to(DataLifecycleStage.INACTIVE)

            except (ValueError, KeyError, AttributeError) as e:
                logger.error(
                    "Error processing lifecycle record %s: %s", record.record_id, str(e)
                )
                stats["errors"] += 1

        return stats

    def _should_expire(
        self, record: DataLifecycleRecord, policy: RetentionPolicy
    ) -> bool:
        """Check if data should expire based on policy."""
        if policy.retention_period == RetentionPeriod.INDEFINITE:
            return False

        if policy.retention_period == RetentionPeriod.IMMEDIATE:
            return True

        age_days = (datetime.now() - record.created_at).days
        return age_days >= int(policy.retention_period.value)

    def _is_inactive(self, record: DataLifecycleRecord) -> bool:
        """Check if data is inactive."""
        if record.current_stage != DataLifecycleStage.ACTIVE:
            return False

        days_since_access = (datetime.now() - record.last_accessed).days
        return days_since_access >= self.inactive_threshold_days

    async def _handle_expiry(
        self, record: DataLifecycleRecord, policy: RetentionPolicy
    ) -> Optional[str]:
        """Handle data expiry based on policy action."""
        if policy.action_on_expiry == RetentionAction.DELETE:
            await self._schedule_deletion(record)
            return "deleted"

        elif policy.action_on_expiry == RetentionAction.ARCHIVE:
            success = await self._archive_data(record)
            return "archived" if success else None

        elif policy.action_on_expiry == RetentionAction.ANONYMIZE:
            success = await self._anonymize_data(record)
            return "anonymized" if success else None

        elif policy.action_on_expiry == RetentionAction.REVIEW:
            await self._mark_for_review(record)
            return "reviewed"

        elif policy.action_on_expiry == RetentionAction.EXTEND:
            await self._extend_retention(record, policy)
            return "extended"

        # This should not happen if all RetentionAction cases are handled
        raise ValueError(f"Unhandled retention action: {policy.action_on_expiry}")

    async def _archive_data(self, record: DataLifecycleRecord) -> bool:
        """Archive voice data."""
        if not self.archive_storage:
            logger.warning("Archive storage not configured")
            return False

        try:
            # Create archive job
            job = ArchiveJob(
                job_id=f"archive_{record.record_id}_{datetime.now().timestamp()}",
                user_id=record.user_id,
                data_records=[record.data_record_id],
                status=ArchiveStatus.PENDING,
                created_at=datetime.now(),
            )

            self.archive_jobs[job.job_id] = job

            # Start archival
            job.status = ArchiveStatus.IN_PROGRESS
            job.started_at = datetime.now()

            # Get data from storage
            if not self.storage:
                job.status = ArchiveStatus.FAILED
                job.error_message = "Storage not configured"
                return False

            data_key = f"voice_data:{record.user_id}:{record.data_record_id}"
            data = self.storage.retrieve(data_key)

            if not data:
                job.status = ArchiveStatus.FAILED
                job.error_message = "Data not found in storage"
                return False

            # Compress data
            compressed_data = await self._compress_data(data, record)

            # Calculate checksum
            checksum = hashlib.sha256(compressed_data).hexdigest()

            # Store in archive
            archive_key = f"archive/{record.user_id}/{record.data_type.value}/{record.data_record_id}.tar.gz"
            await self.archive_storage.archive(archive_key, compressed_data)

            # Update job and record
            job.status = ArchiveStatus.COMPLETED
            job.completed_at = datetime.now()
            job.archive_path = archive_key
            job.checksum = checksum

            record.transition_to(DataLifecycleStage.ARCHIVED)
            record.archive_location = archive_key

            # Delete from primary storage
            # Delete from primary storage
            if self.storage.delete(data_key):
                logger.info("Deleted data from primary storage: %s", data_key)

            # Log archival
            if self.audit_logger:
                await self.audit_logger.log_event(
                    AuditEventType.DATA_ARCHIVED,
                    user_id=record.user_id,
                    details={
                        "record_id": record.data_record_id,
                        "archive_path": archive_key,
                        "checksum": checksum,
                    },
                )

            return True

        except (IOError, ValueError, KeyError) as e:
            logger.error("Archive failed: %s", str(e))
            if job.job_id in self.archive_jobs:
                job = self.archive_jobs[job.job_id]
                job.status = ArchiveStatus.FAILED
                job.error_message = str(e)
                job.retry_count += 1
            return False

    async def _compress_data(self, data: bytes, record: DataLifecycleRecord) -> bytes:
        """Compress data for archival."""
        # Create metadata
        metadata = {
            "record_id": record.data_record_id,
            "user_id": record.user_id,
            "data_type": record.data_type.value,
            "created_at": record.created_at.isoformat(),
            "archived_at": datetime.now().isoformat(),
            "original_size": len(data),
            "access_count": record.access_count,
        }

        # Create tar archive in memory
        tar_buffer = io.BytesIO()

        with tarfile.open(
            fileobj=tar_buffer,
            mode="w:gz",
            compresslevel=self.archive_compression_level,
        ) as tar:
            # Add metadata
            metadata_bytes = json.dumps(metadata).encode()
            metadata_info = tarfile.TarInfo(name="metadata.json")
            metadata_info.size = len(metadata_bytes)
            tar.addfile(metadata_info, io.BytesIO(metadata_bytes))

            # Add data
            data_info = tarfile.TarInfo(name=f"data.{record.data_type.value}")
            data_info.size = len(data)
            tar.addfile(data_info, io.BytesIO(data))

        return tar_buffer.getvalue()

    async def _schedule_deletion(self, record: DataLifecycleRecord) -> None:
        """Schedule data for deletion with grace period."""
        record.transition_to(DataLifecycleStage.SCHEDULED_DELETION)
        record.deletion_scheduled_at = datetime.now() + timedelta(
            hours=self.deletion_grace_period_hours
        )

        # Log scheduled deletion
        if self.audit_logger:
            await self.audit_logger.log_event(
                AuditEventType.DELETION_SCHEDULED,
                user_id=record.user_id,
                details={
                    "record_id": record.data_record_id,
                    "scheduled_for": record.deletion_scheduled_at.isoformat(),
                },
            )

    async def _anonymize_data(self, record: DataLifecycleRecord) -> bool:
        """Anonymize voice data."""
        # Implementation depends on data type
        # This is a placeholder
        logger.info("Anonymizing data record %s", record.data_record_id)
        return True

    async def _mark_for_review(self, record: DataLifecycleRecord) -> None:
        """Mark data for manual review."""
        # Mark for review in audit log
        logger.info("Data record %s marked for review", record.data_record_id)

        # Create review task
        # This would integrate with a task management system
        logger.info("Data record %s marked for review", record.data_record_id)

    async def _extend_retention(
        self, record: DataLifecycleRecord, policy: RetentionPolicy
    ) -> None:
        """Extend retention period based on policy conditions."""
        # Check auto-extend conditions
        if policy.auto_extend_conditions:
            # Example: extend if accessed recently
            if "recent_access_days" in policy.auto_extend_conditions:
                days_since_access = (datetime.now() - record.last_accessed).days
                if (
                    days_since_access
                    <= policy.auto_extend_conditions["recent_access_days"]
                ):
                    # Extend by same period
                    logger.info(
                        "Extended retention for record %s due to recent access",
                        record.data_record_id,
                    )

    async def restore_from_archive(self, user_id: str, record_id: str) -> bool:
        """Restore data from archive."""
        if not self.archive_storage:
            return False

        lifecycle_record = self.lifecycle_records.get(record_id)
        if not lifecycle_record or not lifecycle_record.archive_location:
            return False

        try:
            # Retrieve from archive
            archived_data = await self.archive_storage.retrieve(
                lifecycle_record.archive_location
            )

            if not archived_data:
                return False

            # Decompress
            tar_buffer = io.BytesIO(archived_data)

            with tarfile.open(fileobj=tar_buffer, mode="r:gz") as tar:
                # Extract data
                for member in tar.getmembers():
                    if member.name.startswith("data."):
                        data_file = tar.extractfile(member)
                        if data_file:
                            data = data_file.read()

                            # Restore to primary storage
                            data_key = f"voice_data:{user_id}:{record_id}"
                            if self.storage:
                                self.storage.store(data_key, data)

                            # Update lifecycle record
                            lifecycle_record.transition_to(DataLifecycleStage.RESTORED)

                            # Log restoration
                            if self.audit_logger:
                                await self.audit_logger.log_event(
                                    AuditEventType.DATA_RESTORED,
                                    user_id=user_id,
                                    details={"record_id": record_id},
                                )

                            return True

        except (OSError, ValueError, KeyError) as e:
            logger.error("Restore failed: %s", str(e))

        return False

    @require_phi_access(AccessLevel.READ)
    @audit_phi_access(action="get_voice_retention_summary")
    async def get_retention_summary(self, user_id: str) -> Dict[str, Any]:
        """Get retention summary for a user."""
        summary: Dict[str, Any] = {
            "total_records": 0,
            "by_stage": {},
            "by_data_type": {},
            "scheduled_deletions": [],
            "archived_size_bytes": 0,
            "next_expiry": None,
        }

        user_records = [
            r for r in self.lifecycle_records.values() if r.user_id == user_id
        ]

        summary["total_records"] = len(user_records)

        # Count by stage
        for record in user_records:
            stage = record.current_stage.value
            summary["by_stage"][stage] = summary["by_stage"].get(stage, 0) + 1

            # Count by data type
            data_type = record.data_type.value
            summary["by_data_type"][data_type] = (
                summary["by_data_type"].get(data_type, 0) + 1
            )

            # Track archived size
            if record.current_stage == DataLifecycleStage.ARCHIVED:
                summary["archived_size_bytes"] += record.size_bytes

            # Track scheduled deletions
            if (
                record.deletion_scheduled_at
                and record.deletion_scheduled_at > datetime.now()
            ):
                summary["scheduled_deletions"].append(
                    {
                        "record_id": record.data_record_id,
                        "data_type": record.data_type.value,
                        "scheduled_at": record.deletion_scheduled_at.isoformat(),
                    }
                )

        # Find next expiry
        next_expiry = None
        for record in user_records:
            if (
                record.deletion_scheduled_at
                and record.deletion_scheduled_at > datetime.now()
            ):
                if next_expiry is None or record.deletion_scheduled_at < next_expiry:
                    next_expiry = record.deletion_scheduled_at

        summary["next_expiry"] = next_expiry.isoformat() if next_expiry else None

        return summary

    async def execute_scheduled_deletions(self) -> int:
        """Execute all scheduled deletions that are due."""
        deleted_count = 0

        for record in self.lifecycle_records.values():
            if (
                record.current_stage == DataLifecycleStage.SCHEDULED_DELETION
                and record.deletion_scheduled_at
                and datetime.now() >= record.deletion_scheduled_at
            ):

                # Delete data
                data_key = f"voice_data:{record.user_id}:{record.data_record_id}"
                if self.storage:
                    success = self.storage.delete(data_key)
                else:
                    success = False

                if success:
                    record.transition_to(DataLifecycleStage.DELETED)
                    deleted_count += 1

                    # Log deletion
                    if self.audit_logger:
                        await self.audit_logger.log_event(
                            AuditEventType.DATA_DELETED,
                            user_id=record.user_id,
                            details={"record_id": record.data_record_id},
                        )

        return deleted_count


class RetentionPolicyValidator:
    """Validates retention policies against regulatory requirements."""

    def __init__(self, regulatory_compliance: Optional[RegulatoryCompliance] = None):
        """Initialize the retention policy validator.

        Args:
            regulatory_compliance: Service for checking regulatory compliance
        """
        self.regulatory_compliance = regulatory_compliance

    def validate_policy(
        self, policy: RetentionPolicy, region: str
    ) -> Tuple[bool, List[str]]:
        """Validate policy against regional regulations."""
        errors = []

        # GDPR validation (EU)
        if region.startswith("EU") or region in ["GB", "UK"]:
            if policy.retention_period == RetentionPeriod.INDEFINITE:
                if ProcessingPurpose.RESEARCH not in policy.purposes:
                    errors.append(
                        "GDPR: Indefinite retention only allowed for research purposes"
                    )

            if policy.action_on_expiry != RetentionAction.DELETE:
                if not policy.review_required:
                    errors.append("GDPR: Non-deletion actions require review")

        # HIPAA validation (US)
        if region == "US":
            medical_purposes = {
                ProcessingPurpose.HEALTH_MONITORING,
                ProcessingPurpose.TRANSCRIPTION,
            }
            if any(p in medical_purposes for p in policy.purposes):
                if policy.retention_period.value < 365:  # Less than 1 year
                    errors.append(
                        "HIPAA: Medical records must be retained for at least 1 year"
                    )

        # PIPEDA validation (Canada)
        if region == "CA":
            if policy.retention_period == RetentionPeriod.INDEFINITE:
                errors.append("PIPEDA: Indefinite retention not permitted")

        return len(errors) == 0, errors


# Retention policy templates for different use cases
class RetentionPolicyTemplates:
    """Pre-defined retention policy templates."""

    @staticmethod
    def healthcare_provider() -> List[RetentionPolicy]:
        """Policies for healthcare providers."""
        return [
            RetentionPolicy(
                policy_id="healthcare_clinical",
                name="Clinical Voice Records",
                description="Voice records from clinical consultations",
                data_types={VoiceDataType.AUDIO_RECORDING, VoiceDataType.TRANSCRIPTION},
                purposes={
                    ProcessingPurpose.HEALTH_MONITORING,
                    ProcessingPurpose.TRANSCRIPTION,
                },
                retention_period=RetentionPeriod.ONE_YEAR,
                action_on_expiry=RetentionAction.ARCHIVE,
                archive_after_days=90,
                legal_hold=True,
            ),
            RetentionPolicy(
                policy_id="healthcare_commands",
                name="Voice Commands",
                description="Voice commands for system interaction",
                data_types={VoiceDataType.COMMAND_HISTORY},
                purposes={ProcessingPurpose.COMMANDS},
                retention_period=RetentionPeriod.NINETY_DAYS,
                action_on_expiry=RetentionAction.DELETE,
            ),
        ]

    @staticmethod
    def research_institution() -> List[RetentionPolicy]:
        """Policies for research institutions."""
        return [
            RetentionPolicy(
                policy_id="research_consented",
                name="Consented Research Data",
                description="Voice data with research consent",
                data_types=set(VoiceDataType),
                purposes={ProcessingPurpose.RESEARCH},
                retention_period=RetentionPeriod.INDEFINITE,
                action_on_expiry=RetentionAction.REVIEW,
                review_required=True,
                auto_extend_conditions={"active_study": True},
            ),
            RetentionPolicy(
                policy_id="research_anonymous",
                name="Anonymous Research Data",
                description="Anonymized voice data for research",
                data_types=set(VoiceDataType),
                purposes={ProcessingPurpose.RESEARCH, ProcessingPurpose.TRAINING},
                retention_period=RetentionPeriod.INDEFINITE,
                action_on_expiry=RetentionAction.ANONYMIZE,
            ),
        ]

    @staticmethod
    def emergency_services() -> List[RetentionPolicy]:
        """Policies for emergency services."""
        return [
            RetentionPolicy(
                policy_id="emergency_calls",
                name="Emergency Voice Calls",
                description="Voice data from emergency situations",
                data_types={VoiceDataType.AUDIO_RECORDING, VoiceDataType.TRANSCRIPTION},
                purposes={ProcessingPurpose.LEGAL_COMPLIANCE},
                retention_period=RetentionPeriod.ONE_YEAR,
                action_on_expiry=RetentionAction.ARCHIVE,
                archive_after_days=30,
                legal_hold=True,
            )
        ]


# Background task for automated retention management
class RetentionBackgroundTask:
    """Background task for automated retention management."""

    def __init__(self, retention_manager: VoiceDataRetentionManager):
        """Initialize the retention background task.

        Args:
            retention_manager: The retention manager to run tasks for
        """
        self.retention_manager = retention_manager
        self.running = False
        self.task: Optional[asyncio.Task[None]] = None

    async def start(self) -> None:
        """Start the background task."""
        self.running = True
        self.task = asyncio.create_task(self._run())
        logger.info("Retention background task started")

    async def stop(self) -> None:
        """Stop the background task."""
        self.running = False
        if self.task:
            await self.task
        logger.info("Retention background task stopped")

    async def _run(self) -> None:
        """Run the background task."""
        while self.running:
            try:
                # Process retention tasks
                stats = await self.retention_manager.process_retention_tasks()
                logger.info("Retention task completed: %s", stats)

                # Execute scheduled deletions
                deleted = await self.retention_manager.execute_scheduled_deletions()
                if deleted > 0:
                    logger.info("Executed %d scheduled deletions", deleted)

                # Sleep for 1 hour
                await asyncio.sleep(3600)

            except (asyncio.CancelledError, KeyError, ValueError, IOError) as e:
                logger.error("Retention task error: %s", str(e))
                await asyncio.sleep(300)  # Sleep 5 minutes on error


# Example usage
if __name__ == "__main__":

    async def demo_retention() -> None:
        """Demonstrate voice data retention functionality."""
        # Initialize manager
        manager = VoiceDataRetentionManager()
        # Create sample data record
        data_record = VoiceDataRecord(
            record_id="rec123",
            user_id="user456",
            data_type=VoiceDataType.TRANSCRIPTION,
            purpose=ProcessingPurpose.HEALTH_MONITORING,
            collected_at=datetime.now() - timedelta(days=100),
            data_size_bytes=1024,
            retention_period=RetentionPeriod.ONE_YEAR,
        )

        # Apply retention policy
        lifecycle_record = await manager.apply_retention_policy(data_record)
        print(f"Applied policy: {lifecycle_record.policy_id}")

        # Get retention summary
        summary = await manager.get_retention_summary("user456")
        print(f"Retention summary: {summary}")

        # Process retention tasks
        stats = await manager.process_retention_tasks()
        print(f"Processing stats: {stats}")

        # Validate policy
        validator = RetentionPolicyValidator()
        policy = manager.policy_manager.get_policy("gdpr_standard")
        if policy:
            valid, errors = validator.validate_policy(policy, "EU")
        else:
            valid, errors = False, ["Policy not found"]
        print(f"Policy valid for EU: {valid}, errors: {errors}")

    # Run demo
    asyncio.run(demo_retention())
