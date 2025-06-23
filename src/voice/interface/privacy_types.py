"""Types for voice privacy controls."""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, Optional, Set


class VoiceDataType(Enum):
    """Types of voice data collected."""

    AUDIO_RECORDING = "audio_recording"
    VOICE_PRINT = "voice_print"
    TRANSCRIPTION = "transcription"
    VOICE_FEATURES = "voice_features"
    SPEAKER_PROFILE = "speaker_profile"
    EMOTION_DATA = "emotion_data"
    HEALTH_INDICATORS = "health_indicators"
    COMMAND_HISTORY = "command_history"
    ERROR_RECORDINGS = "error_recordings"
    TRAINING_DATA = "training_data"


class ConsentStatus(Enum):
    """Voice data consent status."""

    NOT_REQUESTED = "not_requested"
    PENDING = "pending"
    GRANTED = "granted"
    DENIED = "denied"
    WITHDRAWN = "withdrawn"
    EXPIRED = "expired"


class RetentionPeriod(Enum):
    """Data retention periods for voice data."""

    IMMEDIATE = "immediate"  # Delete immediately after processing
    SESSION = "session"  # Delete when session ends
    TWENTY_FOUR_HOURS = "24_hours"
    SEVEN_DAYS = "7_days"
    THIRTY_DAYS = "30_days"
    NINETY_DAYS = "90_days"
    ONE_YEAR = "1_year"
    LEGAL_REQUIREMENT = "legal_requirement"  # As required by law
    INDEFINITE = "indefinite"  # Until explicitly deleted


class ProcessingPurpose(Enum):
    """Purposes for processing voice data."""

    TRANSCRIPTION = "transcription"
    AUTHENTICATION = "authentication"
    DICTATION = "dictation"
    COMMANDS = "commands"
    HEALTH_MONITORING = "health_monitoring"
    QUALITY_IMPROVEMENT = "quality_improvement"
    TRAINING = "training"
    RESEARCH = "research"
    EMERGENCY_RESPONSE = "emergency_response"
    LEGAL_COMPLIANCE = "legal_compliance"


@dataclass
class VoiceConsent:
    """Voice data consent record."""

    user_id: str
    consent_id: str
    data_types: Set[VoiceDataType]
    purposes: Set[ProcessingPurpose]
    status: ConsentStatus
    granted_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    withdrawn_at: Optional[datetime] = None
    retention_period: RetentionPeriod = RetentionPeriod.LEGAL_REQUIREMENT
    special_conditions: Dict[str, Any] = field(default_factory=dict)
    version: str = "1.0"
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def is_valid(self) -> bool:
        """Check if consent is currently valid."""
        if self.status != ConsentStatus.GRANTED:
            return False
        if self.expires_at and datetime.now() > self.expires_at:
            return False
        return True

    def covers_data_type(self, data_type: VoiceDataType) -> bool:
        """Check if consent covers a specific data type."""
        return data_type in self.data_types and self.is_valid()

    def covers_purpose(self, purpose: ProcessingPurpose) -> bool:
        """Check if consent covers a specific processing purpose."""
        return purpose in self.purposes and self.is_valid()


@dataclass
class VoiceDataRecord:
    """Record of voice data collection."""

    record_id: str
    user_id: str
    data_type: VoiceDataType
    purpose: ProcessingPurpose
    collected_at: datetime
    retention_period: RetentionPeriod
    deletion_date: Optional[datetime] = None
    data_location: Optional[str] = None
    data_size_bytes: Optional[int] = None
    encryption_key_id: Optional[str] = None
    consent_id: Optional[str] = None
    access_count: int = 0
    last_accessed: Optional[datetime] = None
    processing_status: str = "collected"
    hash_value: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def calculate_deletion_date(self) -> Optional[datetime]:
        """Calculate when this data should be deleted."""
        if self.retention_period == RetentionPeriod.IMMEDIATE:
            return self.collected_at
        elif self.retention_period == RetentionPeriod.SESSION:
            # Session-based deletion handled elsewhere
            return None
        elif self.retention_period == RetentionPeriod.TWENTY_FOUR_HOURS:
            return self.collected_at + timedelta(hours=24)
        elif self.retention_period == RetentionPeriod.SEVEN_DAYS:
            return self.collected_at + timedelta(days=7)
        elif self.retention_period == RetentionPeriod.THIRTY_DAYS:
            return self.collected_at + timedelta(days=30)
        elif self.retention_period == RetentionPeriod.NINETY_DAYS:
            return self.collected_at + timedelta(days=90)
        elif self.retention_period == RetentionPeriod.ONE_YEAR:
            return self.collected_at + timedelta(days=365)
        else:
            return None


@dataclass
class VoicePrivacySettings:
    """User's voice privacy settings."""

    user_id: str
    # Data collection settings
    allow_audio_storage: bool = False
    allow_transcription_storage: bool = True
    allow_voice_print_storage: bool = True
    allow_analytics: bool = True
    allow_quality_monitoring: bool = True
    allow_research_use: bool = False

    # Processing settings
    require_explicit_consent: bool = True
    local_processing_only: bool = False
    allow_cloud_processing: bool = True

    # Retention settings
    audio_retention: RetentionPeriod = RetentionPeriod.IMMEDIATE
    transcription_retention: RetentionPeriod = RetentionPeriod.THIRTY_DAYS
    voice_print_retention: RetentionPeriod = RetentionPeriod.ONE_YEAR
    analytics_retention: RetentionPeriod = RetentionPeriod.NINETY_DAYS

    # Sharing settings
    allow_sharing_with_providers: bool = False
    allow_anonymized_sharing: bool = False
    allow_emergency_access: bool = True

    # Notification settings
    notify_on_access: bool = False
    notify_on_sharing: bool = True
    notify_before_deletion: bool = True

    # Advanced settings
    require_re_authentication: bool = True
    re_authentication_interval_days: int = 30
    allow_voice_cloning_detection: bool = True
    require_liveness_check: bool = True

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "user_id": self.user_id,
            "allow_audio_storage": self.allow_audio_storage,
            "allow_transcription_storage": self.allow_transcription_storage,
            "allow_voice_print_storage": self.allow_voice_print_storage,
            "allow_analytics": self.allow_analytics,
            "allow_quality_monitoring": self.allow_quality_monitoring,
            "allow_research_use": self.allow_research_use,
            "require_explicit_consent": self.require_explicit_consent,
            "local_processing_only": self.local_processing_only,
            "allow_cloud_processing": self.allow_cloud_processing,
            "audio_retention": self.audio_retention.value,
            "transcription_retention": self.transcription_retention.value,
            "voice_print_retention": self.voice_print_retention.value,
            "analytics_retention": self.analytics_retention.value,
            "allow_sharing_with_providers": self.allow_sharing_with_providers,
            "allow_anonymized_sharing": self.allow_anonymized_sharing,
            "allow_emergency_access": self.allow_emergency_access,
            "notify_on_access": self.notify_on_access,
            "notify_on_sharing": self.notify_on_sharing,
            "notify_before_deletion": self.notify_before_deletion,
            "require_re_authentication": self.require_re_authentication,
            "re_authentication_interval_days": self.re_authentication_interval_days,
            "allow_voice_cloning_detection": self.allow_voice_cloning_detection,
            "require_liveness_check": self.require_liveness_check,
        }
