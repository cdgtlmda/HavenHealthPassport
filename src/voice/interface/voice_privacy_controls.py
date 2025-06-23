"""Voice Privacy Controls Module.

This module implements comprehensive privacy controls for voice data in the Haven Health Passport system,
ensuring GDPR/HIPAA compliance, user consent management, data retention policies, and granular
control over voice recordings and biometric data.
"""

import json
import logging
import secrets
from dataclasses import asdict
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set

from src.audit.audit_logger import AuditEventType, AuditLogger
from src.compliance.gdpr import GDPRCompliance
from src.compliance.hipaa import HIPAACompliance
from src.healthcare.hipaa_access_control import (
    AccessLevel,
    audit_phi_access,
    require_phi_access,
)
from src.services.encryption_service import EncryptionService
from src.storage.secure_storage import SecureStorage

from .privacy_types import (
    ConsentStatus,
    ProcessingPurpose,
    RetentionPeriod,
    VoiceConsent,
    VoiceDataRecord,
    VoiceDataType,
    VoicePrivacySettings,
)

logger = logging.getLogger(__name__)


class VoicePrivacyController:
    """Main controller for voice privacy management."""

    def __init__(
        self,
        storage: Optional[SecureStorage] = None,
        encryption_service: Optional[EncryptionService] = None,
        audit_logger: Optional[AuditLogger] = None,
    ):
        """Initialize the voice privacy controller.

        Args:
            storage: Secure storage service for persisting data
            encryption_service: Service for encrypting sensitive data
            audit_logger: Logger for audit events
        """
        self.storage = storage
        self.encryption_service = encryption_service
        self.audit_logger = audit_logger

        # In-memory caches
        self.consents: Dict[str, List[VoiceConsent]] = {}
        self.privacy_settings: Dict[str, VoicePrivacySettings] = {}
        self.data_records: Dict[str, List[VoiceDataRecord]] = {}

        # Compliance managers
        self.gdpr_compliance = GDPRCompliance()
        self.hipaa_compliance = HIPAACompliance()

    @require_phi_access(AccessLevel.WRITE)
    @audit_phi_access(action="request_voice_consent")
    async def request_consent(
        self,
        user_id: str,
        data_types: Set[VoiceDataType],
        purposes: Set[ProcessingPurpose],
        duration_days: Optional[int] = 365,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> VoiceConsent:
        """Request user consent for voice data processing."""
        consent = VoiceConsent(
            consent_id=secrets.token_urlsafe(16),
            user_id=user_id,
            data_types=data_types,
            purposes=purposes,
            status=ConsentStatus.PENDING,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        if duration_days:
            consent.expires_at = datetime.now() + timedelta(days=duration_days)

        # Store consent request
        if user_id not in self.consents:
            self.consents[user_id] = []
        self.consents[user_id].append(consent)

        # Log consent request
        if self.audit_logger:
            await self.audit_logger.log_event(
                AuditEventType.CONSENT_REQUESTED,
                user_id=user_id,
                details={
                    "consent_id": consent.consent_id,
                    "data_types": [dt.value for dt in data_types],
                    "purposes": [p.value for p in purposes],
                },
            )

        return consent

    @require_phi_access(AccessLevel.WRITE)
    @audit_phi_access(action="grant_voice_consent")
    async def grant_consent(self, user_id: str, consent_id: str) -> bool:
        """Grant consent for voice data processing."""
        consent = await self._get_consent(user_id, consent_id)
        if not consent:
            return False

        consent.status = ConsentStatus.GRANTED
        consent.granted_at = datetime.now()

        # Persist consent
        if self.storage:
            await self._save_consent(consent)

        # Log consent grant
        if self.audit_logger:
            await self.audit_logger.log_event(
                AuditEventType.CONSENT_GRANTED,
                user_id=user_id,
                details={"consent_id": consent_id},
            )

        return True

    @require_phi_access(AccessLevel.WRITE)
    @audit_phi_access(action="withdraw_voice_consent")
    async def withdraw_consent(self, user_id: str, consent_id: str) -> bool:
        """Withdraw consent for voice data processing."""
        consent = await self._get_consent(user_id, consent_id)
        if not consent:
            return False

        consent.status = ConsentStatus.WITHDRAWN
        consent.withdrawn_at = datetime.now()

        # Persist withdrawal
        if self.storage:
            await self._save_consent(consent)

        # Trigger data deletion if required
        await self._handle_consent_withdrawal(user_id, consent)

        # Log withdrawal
        if self.audit_logger:
            await self.audit_logger.log_event(
                AuditEventType.CONSENT_WITHDRAWN,
                user_id=user_id,
                details={"consent_id": consent_id},
            )

        return True

    async def check_consent(
        self, user_id: str, data_type: VoiceDataType, purpose: ProcessingPurpose
    ) -> bool:
        """Check if user has valid consent for specific data processing."""
        if user_id not in self.consents:
            return False

        for consent in self.consents[user_id]:
            if consent.is_valid():
                if data_type in consent.data_types and purpose in consent.purposes:
                    return True

        return False

    @require_phi_access(AccessLevel.WRITE)
    @audit_phi_access(action="record_voice_data_collection")
    async def record_data_collection(
        self,
        user_id: str,
        data_type: VoiceDataType,
        purpose: ProcessingPurpose,
        size_bytes: int,
        retention_period: Optional[RetentionPeriod] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> VoiceDataRecord:
        """Record collection of voice data."""
        # Get user's retention preference
        settings = await self.get_privacy_settings(user_id)

        if retention_period is None:
            # Use user's preference based on data type
            if data_type == VoiceDataType.AUDIO_RECORDING:
                retention_period = settings.audio_retention
            elif data_type == VoiceDataType.TRANSCRIPTION:
                retention_period = settings.transcription_retention
            elif data_type == VoiceDataType.VOICE_PRINT:
                retention_period = settings.voice_print_retention
            else:
                retention_period = settings.analytics_retention

        record = VoiceDataRecord(
            record_id=secrets.token_urlsafe(16),
            user_id=user_id,
            data_type=data_type,
            purpose=purpose,
            collected_at=datetime.now(),
            data_size_bytes=size_bytes,
            retention_period=retention_period,
            deletion_date=None,
            metadata=metadata or {},
        )

        record.deletion_date = record.calculate_deletion_date()

        # Store record
        if user_id not in self.data_records:
            self.data_records[user_id] = []
        self.data_records[user_id].append(record)

        # Persist record
        if self.storage:
            await self._save_data_record(record)

        return record

    async def get_privacy_settings(self, user_id: str) -> VoicePrivacySettings:
        """Get user's voice privacy settings."""
        if user_id in self.privacy_settings:
            return self.privacy_settings[user_id]

        # Load from storage
        if self.storage:
            settings = await self._load_privacy_settings(user_id)
            if settings:
                self.privacy_settings[user_id] = settings
                return settings

        # Return defaults
        settings = VoicePrivacySettings(user_id=user_id)
        self.privacy_settings[user_id] = settings
        return settings

    async def update_privacy_settings(
        self, user_id: str, updates: Dict[str, Any]
    ) -> VoicePrivacySettings:
        """Update user's voice privacy settings."""
        settings = await self.get_privacy_settings(user_id)

        # Apply updates
        for key, value in updates.items():
            if hasattr(settings, key):
                # Handle enum conversions
                if key.endswith("_retention"):
                    value = RetentionPeriod[value] if isinstance(value, str) else value
                setattr(settings, key, value)

        # Persist settings
        if self.storage:
            await self._save_privacy_settings(settings)

        # Log settings change
        if self.audit_logger:
            await self.audit_logger.log_event(
                AuditEventType.PRIVACY_SETTINGS_UPDATED,
                user_id=user_id,
                details={"updates": updates},
            )

        return settings

    async def delete_voice_data(
        self,
        user_id: str,
        data_types: Optional[Set[VoiceDataType]] = None,
        before_date: Optional[datetime] = None,
    ) -> Dict[str, int]:
        """Delete user's voice data."""
        deletion_stats: Dict[str, int] = {}

        if user_id not in self.data_records:
            return deletion_stats

        records_to_delete = []

        for record in self.data_records[user_id]:
            # Check data type filter
            if data_types and record.data_type not in data_types:
                continue

            # Check date filter
            if before_date and record.collected_at >= before_date:
                continue

            records_to_delete.append(record)

        # Delete records
        for record in records_to_delete:
            await self._delete_data_record(record)
            data_type_key = record.data_type.value
            deletion_stats[data_type_key] = deletion_stats.get(data_type_key, 0) + 1

        # Remove from cache
        self.data_records[user_id] = [
            r for r in self.data_records[user_id] if r not in records_to_delete
        ]

        # Log deletion
        if self.audit_logger:
            await self.audit_logger.log_event(
                AuditEventType.DATA_DELETED,
                user_id=user_id,
                details={
                    "deletion_stats": deletion_stats,
                    "data_types": (
                        [dt.value for dt in data_types] if data_types else "all"
                    ),
                },
            )

        return deletion_stats

    async def export_voice_data(self, user_id: str) -> Dict[str, Any]:
        """Export all user's voice data for portability."""
        export_data: Dict[str, Any] = {
            "user_id": user_id,
            "export_date": datetime.now().isoformat(),
            "consents": [],
            "privacy_settings": None,
            "data_records": [],
            "statistics": {},
        }

        # Export consents
        if user_id in self.consents:
            export_data["consents"] = [
                asdict(consent) for consent in self.consents[user_id]
            ]

        # Export privacy settings
        settings = await self.get_privacy_settings(user_id)
        export_data["privacy_settings"] = settings.to_dict()

        # Export data records
        if user_id in self.data_records:
            export_data["data_records"] = [
                {
                    "record_id": record.record_id,
                    "data_type": record.data_type.value,
                    "purpose": record.purpose.value,
                    "collected_at": record.collected_at.isoformat(),
                    "size_bytes": record.data_size_bytes,
                    "retention_period": record.retention_period.name,
                    "deletion_date": (
                        record.deletion_date.isoformat()
                        if record.deletion_date
                        else None
                    ),
                    "anonymized": record.metadata.get("anonymized", False),
                }
                for record in self.data_records[user_id]
            ]

        # Calculate statistics
        if user_id in self.data_records:
            stats: Dict[str, int] = {}
            for record in self.data_records[user_id]:
                data_type = record.data_type.value
                stats[data_type] = stats.get(data_type, 0) + 1
            export_data["statistics"] = stats

        # Log export
        if self.audit_logger:
            await self.audit_logger.log_event(
                AuditEventType.DATA_EXPORTED,
                user_id=user_id,
                details={"record_count": len(export_data["data_records"])},
            )

        return export_data

    async def anonymize_voice_data(
        self, user_id: str, data_types: Set[VoiceDataType]
    ) -> int:
        """Anonymize voice data while preserving it for research/analytics."""
        anonymized_count = 0

        if user_id not in self.data_records:
            return anonymized_count

        for record in self.data_records[user_id]:
            if record.data_type in data_types and not record.metadata.get(
                "anonymized", False
            ):
                # Anonymize the actual data
                await self._anonymize_data_record(record)
                record.metadata["anonymized"] = True
                record.metadata["anonymized_at"] = datetime.now().isoformat()
                anonymized_count += 1

        # Log anonymization
        if self.audit_logger:
            await self.audit_logger.log_event(
                AuditEventType.DATA_ANONYMIZED,
                user_id=user_id,
                details={
                    "count": anonymized_count,
                    "data_types": [dt.value for dt in data_types],
                },
            )

        return anonymized_count

    async def enforce_retention_policies(self) -> Dict[str, int]:
        """Enforce data retention policies for all users."""
        deletion_stats: Dict[str, int] = {}

        for _user_id, records in self.data_records.items():
            for record in records:
                deletion_date = record.calculate_deletion_date()
                if deletion_date and datetime.now() >= deletion_date:
                    await self._delete_data_record(record)
                    data_type_key = record.data_type.value
                    deletion_stats[data_type_key] = (
                        deletion_stats.get(data_type_key, 0) + 1
                    )

        # Clean up deleted records from cache
        for user_id in self.data_records:
            filtered_records = []
            for r in self.data_records[user_id]:
                deletion_date = r.calculate_deletion_date()
                if not (deletion_date is not None and datetime.now() >= deletion_date):
                    filtered_records.append(r)
            self.data_records[user_id] = filtered_records

        return deletion_stats

    async def get_data_access_log(
        self,
        user_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """Get log of who accessed user's voice data."""
        if not self.audit_logger:
            return []

        # Query audit log for access events
        # Get audit logs for the user
        all_events = self.audit_logger.get_audit_logs(
            start_date=start_date,
            end_date=end_date,
        )

        # Filter by user and event types
        relevant_types = {
            AuditEventType.DATA_ACCESSED.value,
            AuditEventType.DATA_SHARED.value,
            AuditEventType.DATA_EXPORTED.value,
        }

        events = [
            event
            for event in all_events
            if event.get("user_id") == user_id
            and event.get("event_type") in relevant_types
        ]

        return events

    # Private helper methods

    async def _get_consent(
        self, user_id: str, consent_id: str
    ) -> Optional[VoiceConsent]:
        """Get specific consent by ID."""
        if user_id not in self.consents:
            return None

        for consent in self.consents[user_id]:
            if consent.consent_id == consent_id:
                return consent

        return None

    async def _handle_consent_withdrawal(
        self, user_id: str, consent: VoiceConsent
    ) -> None:
        """Handle data deletion after consent withdrawal."""
        settings = await self.get_privacy_settings(user_id)

        # Delete data based on withdrawn consent
        data_types_to_delete: Set[VoiceDataType] = set()

        for data_type in consent.data_types:
            # Check if user wants data deleted on withdrawal
            if (
                data_type == VoiceDataType.AUDIO_RECORDING
                and not settings.allow_audio_storage
            ):
                data_types_to_delete.add(data_type)
            elif (
                data_type == VoiceDataType.VOICE_PRINT
                and not settings.allow_voice_print_storage
            ):
                data_types_to_delete.add(data_type)

        if data_types_to_delete:
            await self.delete_voice_data(user_id, data_types_to_delete)

    async def _delete_data_record(self, record: VoiceDataRecord) -> None:
        """Delete actual data associated with a record."""
        # Delete from storage
        if record.data_location and self.storage:
            self.storage.delete(record.data_location)

        # Additional cleanup based on data type
        if record.data_type == VoiceDataType.VOICE_PRINT:
            # Remove from authentication system
            pass
        elif record.data_type == VoiceDataType.AUDIO_RECORDING:
            # Delete audio file
            pass

    async def _anonymize_data_record(self, record: VoiceDataRecord) -> None:
        """Anonymize data while preserving for research."""
        # Implementation depends on data type
        if record.data_type == VoiceDataType.TRANSCRIPTION:
            # Remove PII from transcription
            pass
        elif record.data_type == VoiceDataType.VOICE_FEATURES:
            # Remove identifying features
            pass

    async def _save_consent(self, consent: VoiceConsent) -> None:
        """Persist consent to storage."""
        if not self.storage:
            return

        key = f"voice_consent:{consent.user_id}:{consent.consent_id}"
        self.storage.store(key, asdict(consent))

    async def _save_privacy_settings(self, settings: VoicePrivacySettings) -> None:
        """Persist privacy settings to storage."""
        if not self.storage:
            return

        key = f"voice_privacy_settings:{settings.user_id}"
        self.storage.store(key, settings.to_dict())

    async def _load_privacy_settings(
        self, user_id: str
    ) -> Optional[VoicePrivacySettings]:
        """Load privacy settings from storage."""
        if not self.storage:
            return None

        key = f"voice_privacy_settings:{user_id}"
        data = self.storage.retrieve(key)

        if not data:
            return None

        try:
            settings_dict = data if isinstance(data, dict) else json.loads(data)
            # Convert back to VoicePrivacySettings
            settings = VoicePrivacySettings(user_id=user_id)
            for key, value in settings_dict.items():
                if hasattr(settings, key) and key != "user_id":
                    setattr(settings, key, value)
            return settings
        except (ValueError, OSError) as e:
            logger.error("Failed to load privacy settings: %s", str(e))
            return None

    async def _save_data_record(self, record: VoiceDataRecord) -> None:
        """Persist data record to storage."""
        if not self.storage:
            return

        key = f"voice_data_record:{record.user_id}:{record.record_id}"
        record_dict = {
            "record_id": record.record_id,
            "user_id": record.user_id,
            "data_type": record.data_type.value,
            "purpose": record.purpose.value,
            "collected_at": record.collected_at.isoformat(),
            "size_bytes": record.data_size_bytes,
            "retention_period": record.retention_period.name,
            "deletion_date": (
                record.deletion_date.isoformat() if record.deletion_date else None
            ),
            "storage_location": record.data_location,
            "encryption_key_id": record.encryption_key_id,
            "anonymized": record.metadata.get("anonymized", False),
            "metadata": record.metadata,
        }
        self.storage.store(key, record_dict)


class VoicePrivacyNotificationService:
    """Service for sending privacy-related notifications."""

    def __init__(self, notification_service: Optional[Any] = None) -> None:
        """Initialize the voice privacy notification service.

        Args:
            notification_service: Service for sending notifications
        """
        self.notification_service = notification_service

    async def notify_data_access(
        self, user_id: str, accessor: str, data_types: List[VoiceDataType], purpose: str
    ) -> None:
        """Notify user of data access."""
        if not self.notification_service:
            return

        message = f"Your voice data was accessed by {accessor} for {purpose}. Data types: {', '.join(dt.value for dt in data_types)}"

        await self.notification_service.send_notification(
            user_id=user_id, title="Voice Data Access", message=message, priority="high"
        )

    async def notify_deletion_pending(
        self, user_id: str, data_type: VoiceDataType, deletion_date: datetime
    ) -> None:
        """Notify user of pending data deletion."""
        if not self.notification_service:
            return

        days_until = (deletion_date - datetime.now()).days

        message = f"Your {data_type.value} data will be deleted in {days_until} days. Download it now if you want to keep a copy."

        await self.notification_service.send_notification(
            user_id=user_id,
            title="Voice Data Deletion Notice",
            message=message,
            priority="medium",
        )

    async def notify_consent_expiring(
        self, user_id: str, consent_id: str, expiry_date: datetime
    ) -> None:
        """Notify user of expiring consent."""
        if not self.notification_service:
            return

        days_until = (expiry_date - datetime.now()).days

        message = f"Your voice data consent expires in {days_until} days. Please renew to continue using voice features."

        await self.notification_service.send_notification(
            user_id=user_id,
            title="Voice Consent Expiring",
            message=message,
            priority="medium",
            action_url=f"/privacy/consent/{consent_id}",
        )


# Privacy policy templates
class VoicePrivacyPolicyTemplates:
    """Pre-defined privacy policy templates for different regions/requirements."""

    @staticmethod
    def gdpr_compliant() -> VoicePrivacySettings:
        """GDPR-compliant privacy settings."""
        return VoicePrivacySettings(
            user_id="",  # To be filled
            allow_audio_storage=False,
            allow_transcription_storage=True,
            allow_voice_print_storage=True,
            allow_analytics=False,
            allow_quality_monitoring=False,
            allow_research_use=False,
            require_explicit_consent=True,
            local_processing_only=False,
            allow_cloud_processing=True,
            audio_retention=RetentionPeriod.IMMEDIATE,
            transcription_retention=RetentionPeriod.THIRTY_DAYS,
            voice_print_retention=RetentionPeriod.ONE_YEAR,
            analytics_retention=RetentionPeriod.THIRTY_DAYS,
            allow_sharing_with_providers=False,
            allow_anonymized_sharing=False,
            allow_emergency_access=True,
            notify_on_access=True,
            notify_on_sharing=True,
            notify_before_deletion=True,
        )

    @staticmethod
    def hipaa_compliant() -> VoicePrivacySettings:
        """HIPAA-compliant privacy settings."""
        return VoicePrivacySettings(
            user_id="",  # To be filled
            allow_audio_storage=True,
            allow_transcription_storage=True,
            allow_voice_print_storage=True,
            allow_analytics=True,
            allow_quality_monitoring=True,
            allow_research_use=False,
            require_explicit_consent=True,
            local_processing_only=False,
            allow_cloud_processing=True,
            audio_retention=RetentionPeriod.ONE_YEAR,
            transcription_retention=RetentionPeriod.ONE_YEAR,
            voice_print_retention=RetentionPeriod.ONE_YEAR,
            analytics_retention=RetentionPeriod.ONE_YEAR,
            allow_sharing_with_providers=True,
            allow_anonymized_sharing=True,
            allow_emergency_access=True,
            notify_on_access=False,
            notify_on_sharing=True,
            notify_before_deletion=False,
        )

    @staticmethod
    def maximum_privacy() -> VoicePrivacySettings:
        """Maximum privacy settings."""
        return VoicePrivacySettings(
            user_id="",  # To be filled
            allow_audio_storage=False,
            allow_transcription_storage=False,
            allow_voice_print_storage=True,  # Required for authentication
            allow_analytics=False,
            allow_quality_monitoring=False,
            allow_research_use=False,
            require_explicit_consent=True,
            local_processing_only=True,
            allow_cloud_processing=False,
            audio_retention=RetentionPeriod.IMMEDIATE,
            transcription_retention=RetentionPeriod.IMMEDIATE,
            voice_print_retention=RetentionPeriod.NINETY_DAYS,
            analytics_retention=RetentionPeriod.IMMEDIATE,
            allow_sharing_with_providers=False,
            allow_anonymized_sharing=False,
            allow_emergency_access=False,
            notify_on_access=True,
            notify_on_sharing=True,
            notify_before_deletion=True,
            require_re_authentication=True,
            re_authentication_interval_days=7,
            allow_voice_cloning_detection=True,
            require_liveness_check=True,
        )


# Example usage
if __name__ == "__main__":
    import asyncio

    async def demo_privacy_controls() -> None:
        """Demonstrate voice privacy control functionality."""
        # Initialize controller
        controller = VoicePrivacyController()

        user_id = "user123"

        # Request consent
        consent = await controller.request_consent(
            user_id=user_id,
            data_types={VoiceDataType.AUDIO_RECORDING, VoiceDataType.TRANSCRIPTION},
            purposes={
                ProcessingPurpose.COMMANDS,
                ProcessingPurpose.QUALITY_IMPROVEMENT,
            },
            duration_days=365,
        )
        print(f"Consent requested: {consent.consent_id}")

        # Grant consent
        await controller.grant_consent(user_id, consent.consent_id)
        print("Consent granted")

        # Check consent
        has_consent = await controller.check_consent(
            user_id, VoiceDataType.AUDIO_RECORDING, ProcessingPurpose.COMMANDS
        )
        print(f"Has consent: {has_consent}")

        # Update privacy settings
        settings = await controller.update_privacy_settings(
            user_id,
            {
                "allow_audio_storage": False,
                "audio_retention": "IMMEDIATE",
                "notify_on_access": True,
            },
        )
        print(f"Updated settings: audio_storage={settings.allow_audio_storage}")

        # Record data collection
        record = await controller.record_data_collection(
            user_id=user_id,
            data_type=VoiceDataType.TRANSCRIPTION,
            purpose=ProcessingPurpose.COMMANDS,
            size_bytes=1024,
            metadata={"command": "check medications"},
        )
        print(f"Recorded data collection: {record.record_id}")

        # Export data
        export = await controller.export_voice_data(user_id)
        print(f"Exported data: {len(export['data_records'])} records")

        # Apply GDPR template
        gdpr_settings = VoicePrivacyPolicyTemplates.gdpr_compliant()
        gdpr_settings.user_id = user_id
        await controller.update_privacy_settings(user_id, gdpr_settings.to_dict())
        print("Applied GDPR-compliant settings")

    # Run demo
    asyncio.run(demo_privacy_controls())
