"""Speaker Configuration for Medical Conversations.

This module defines configuration structures for speaker identification
in medical transcription scenarios. All PHI data is encrypted.

IMPORTANT: This module handles PHI (Protected Health Information).
- All PHI data is encrypted at rest and in transit using industry-standard encryption.
- Access control is enforced through role-based permissions and authentication.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union


class SpeakerRole(Enum):
    """Roles for speakers in medical conversations."""

    PATIENT = "patient"
    PHYSICIAN = "physician"
    NURSE = "nurse"
    SPECIALIST = "specialist"
    CAREGIVER = "caregiver"
    INTERPRETER = "interpreter"
    FAMILY_MEMBER = "family_member"
    TECHNICIAN = "technician"
    THERAPIST = "therapist"
    PHARMACIST = "pharmacist"
    ADMINISTRATOR = "administrator"
    UNKNOWN = "unknown"


class ConversationType(Enum):
    """Types of medical conversations."""

    CONSULTATION = "consultation"
    EXAMINATION = "examination"
    THERAPY_SESSION = "therapy_session"
    MEDICATION_REVIEW = "medication_review"
    DISCHARGE_PLANNING = "discharge_planning"
    TELEMEDICINE = "telemedicine"
    EMERGENCY = "emergency"
    ROUTINE_CHECKUP = "routine_checkup"
    PROCEDURE_DISCUSSION = "procedure_discussion"
    TEST_RESULTS = "test_results"


@dataclass
class SpeakerProfile:
    """Profile for a speaker in medical conversations."""

    speaker_id: str
    role: SpeakerRole
    name: Optional[str] = None
    title: Optional[str] = None
    department: Optional[str] = None
    voice_characteristics: Dict[str, Any] = field(default_factory=dict)
    language_preferences: List[str] = field(default_factory=list)
    created_date: Optional[datetime] = None
    last_updated: Optional[datetime] = None

    def __post_init__(self) -> None:
        """Initialize timestamps if not provided."""
        if not self.created_date:
            self.created_date = datetime.utcnow()
        if not self.last_updated:
            self.last_updated = datetime.utcnow()

    def update(self) -> None:
        """Update the last modified timestamp."""
        self.last_updated = datetime.utcnow()


@dataclass
class SpeakerConfig:
    """Configuration for speaker identification."""

    min_speaker_segments: int = 2
    max_speakers: int = 10
    speaker_change_threshold: float = 0.8
    voice_activity_threshold: float = 0.3
    overlap_tolerance_ms: int = 500
    min_segment_duration_ms: int = 1000
    max_segment_duration_ms: int = 30000
    confidence_threshold: float = 0.8
    enable_diarization: bool = True
    enable_voice_profiles: bool = True
    enable_speaker_identification: bool = True
    save_voice_signatures: bool = False
    privacy_mode: bool = True  # Anonymize speaker data

    def __post_init__(self) -> None:
        """Validate and process configuration after initialization."""
        if self.confidence_threshold < 0.0 or self.confidence_threshold > 1.0:
            raise ValueError("Confidence threshold must be between 0.0 and 1.0")

        if self.min_segment_duration_ms <= 0:
            raise ValueError("Minimum segment duration must be positive")

        if self.max_segment_duration_ms <= self.min_segment_duration_ms:
            raise ValueError("Maximum segment duration must be greater than minimum")

    def to_transcribe_params(self) -> Dict[str, Union[int, Dict[str, int]]]:
        """Convert to AWS Transcribe parameters."""
        params: Dict[str, Union[int, Dict[str, int]]] = {
            "MaxSpeakerLabels": self.max_speakers,
        }

        if self.enable_speaker_identification:
            params["Settings"] = {
                "ShowSpeakerLabels": True,
                "MaxSpeakerLabels": self.max_speakers,
            }

        return params


@dataclass
class SpeakerIdentificationConfig:
    """Full configuration for speaker identification system."""

    speaker_config: SpeakerConfig = field(default_factory=SpeakerConfig)
    conversation_type: ConversationType = ConversationType.CONSULTATION
    expected_speakers: List[SpeakerProfile] = field(default_factory=list)
    enable_real_time: bool = True
    enable_analytics: bool = True
    store_conversation_history: bool = True
    retention_days: int = 90
    anonymize_after_days: int = 30

    def add_expected_speaker(self, profile: SpeakerProfile) -> None:
        """Add an expected speaker to the conversation."""
        self.expected_speakers.append(profile)

    def get_speaker_by_role(self, role: SpeakerRole) -> Optional[SpeakerProfile]:
        """Get speaker profile by role."""
        for speaker in self.expected_speakers:
            if speaker.role == role:
                return speaker
        return None

    def validate(self) -> List[str]:
        """Validate the configuration."""
        errors = []

        if self.speaker_config.max_speakers < len(self.expected_speakers):
            errors.append(
                f"Max speakers ({self.speaker_config.max_speakers}) is less than "
                f"expected speakers ({len(self.expected_speakers)})"
            )

        if self.retention_days < self.anonymize_after_days:
            errors.append(
                "Retention days must be greater than or equal to anonymize days"
            )

        if self.speaker_config.min_segment_duration_ms < 100:
            errors.append("Minimum segment duration must be at least 100ms")

        return errors
