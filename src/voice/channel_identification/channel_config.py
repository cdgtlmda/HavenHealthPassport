"""
Channel Configuration for Multi-Channel Audio Processing.

This module defines configuration classes for channel identification
in medical audio transcription scenarios.
 Handles FHIR Resource validation.
"""

import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Union


class ChannelRole(Enum):
    """Predefined roles for audio channels in medical contexts."""

    PATIENT = "patient"
    PHYSICIAN = "physician"
    NURSE = "nurse"
    SPECIALIST = "specialist"
    INTERPRETER = "interpreter"
    FAMILY_MEMBER = "family_member"
    CAREGIVER = "caregiver"
    TECHNICIAN = "technician"
    ASSISTANT = "assistant"
    UNKNOWN = "unknown"
    MIXED = "mixed"  # Multiple speakers on same channel
    AMBIENT = "ambient"  # Background noise channel


class AudioChannelType(Enum):
    """Types of audio channels."""

    MONO = "mono"
    STEREO_LEFT = "stereo_left"
    STEREO_RIGHT = "stereo_right"
    SURROUND_FRONT_LEFT = "surround_fl"
    SURROUND_FRONT_RIGHT = "surround_fr"
    SURROUND_CENTER = "surround_c"
    SURROUND_REAR_LEFT = "surround_rl"
    SURROUND_REAR_RIGHT = "surround_rr"
    TELEPHONE = "telephone"
    RADIO = "radio"
    MICROPHONE_ARRAY = "mic_array"


class ChannelQuality(Enum):
    """Audio quality levels for channels."""

    EXCELLENT = "excellent"
    GOOD = "good"
    FAIR = "fair"
    POOR = "poor"
    UNUSABLE = "unusable"


@dataclass
class ChannelMapping:
    """Maps physical audio channels to logical roles."""

    channel_id: int
    channel_type: AudioChannelType
    role: ChannelRole
    speaker_name: Optional[str] = None
    language_code: Optional[str] = None
    expected_quality: ChannelQuality = ChannelQuality.GOOD
    noise_reduction: bool = True
    gain_adjustment: float = 1.0  # Audio gain multiplier
    priority: int = 1  # Higher priority channels get better processing
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "channel_id": self.channel_id,
            "channel_type": self.channel_type.value,
            "role": self.role.value,
            "speaker_name": self.speaker_name,
            "language_code": self.language_code,
            "expected_quality": self.expected_quality.value,
            "noise_reduction": self.noise_reduction,
            "gain_adjustment": self.gain_adjustment,
            "priority": self.priority,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ChannelMapping":
        """Create from dictionary representation."""
        return cls(
            channel_id=data["channel_id"],
            channel_type=AudioChannelType(data["channel_type"]),
            role=ChannelRole(data["role"]),
            speaker_name=data.get("speaker_name"),
            language_code=data.get("language_code"),
            expected_quality=ChannelQuality(data.get("expected_quality", "good")),
            noise_reduction=data.get("noise_reduction", True),
            gain_adjustment=data.get("gain_adjustment", 1.0),
            priority=data.get("priority", 1),
            metadata=data.get("metadata", {}),
        )


@dataclass
class ChannelConfig:
    """Configuration for a single audio channel."""

    channel_id: int
    enabled: bool = True
    sample_rate: int = 16000  # Hz
    bit_depth: int = 16
    encoding: str = "pcm"
    max_duration: Optional[int] = None  # seconds
    silence_threshold: float = -40.0  # dB
    voice_activity_detection: bool = True
    echo_cancellation: bool = False
    automatic_gain_control: bool = True
    preprocessing_filters: List[str] = field(default_factory=list)

    def validate(self) -> bool:
        """Validate channel configuration."""
        if self.sample_rate not in [8000, 16000, 22050, 44100, 48000]:
            return False
        if self.bit_depth not in [8, 16, 24, 32]:
            return False
        if self.silence_threshold > 0 or self.silence_threshold < -60:
            return False
        return True

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "channel_id": self.channel_id,
            "enabled": self.enabled,
            "sample_rate": self.sample_rate,
            "bit_depth": self.bit_depth,
            "encoding": self.encoding,
            "max_duration": self.max_duration,
            "silence_threshold": self.silence_threshold,
            "voice_activity_detection": self.voice_activity_detection,
            "echo_cancellation": self.echo_cancellation,
            "automatic_gain_control": self.automatic_gain_control,
            "preprocessing_filters": self.preprocessing_filters,
        }


@dataclass
class ChannelIdentificationConfig:
    """
    Main configuration for channel identification system.

    This configuration manages how multi-channel audio is processed
    and transcribed in medical contexts.
    """

    max_channels: int = 8
    auto_detect_channels: bool = True
    channel_mappings: List[ChannelMapping] = field(default_factory=list)
    channel_configs: List[ChannelConfig] = field(default_factory=list)
    enable_cross_talk_detection: bool = True
    cross_talk_threshold: float = 0.3  # 0-1 scale
    enable_speaker_diarization: bool = True
    merge_similar_channels: bool = False
    similarity_threshold: float = 0.8  # 0-1 scale
    output_format: str = "separate"  # "separate", "merged", "annotated"
    preserve_channel_audio: bool = True
    channel_visualization: bool = False
    real_time_processing: bool = False
    buffer_size: int = 4096  # samples

    def add_channel_mapping(self, mapping: ChannelMapping) -> None:
        """Add a channel mapping."""
        if mapping.channel_id in [m.channel_id for m in self.channel_mappings]:
            raise ValueError(f"Channel {mapping.channel_id} already mapped")

        self.channel_mappings.append(mapping)

        # Update total channels if needed
        if mapping.channel_id >= self.max_channels:
            self.max_channels = mapping.channel_id + 1

    def add_channel_config(self, config: ChannelConfig) -> None:
        """Add a channel configuration."""
        if not config.validate():
            raise ValueError(
                f"Invalid channel configuration for channel {config.channel_id}"
            )

        if config.channel_id in [c.channel_id for c in self.channel_configs]:
            raise ValueError(f"Channel {config.channel_id} already configured")

        self.channel_configs.append(config)

    def get_channel_mapping(self, channel_id: int) -> Optional[ChannelMapping]:
        """Get mapping for specific channel."""
        for mapping in self.channel_mappings:
            if mapping.channel_id == channel_id:
                return mapping
        return None

    def get_channel_config(self, channel_id: int) -> Optional[ChannelConfig]:
        """Get configuration for specific channel."""
        for config in self.channel_configs:
            if config.channel_id == channel_id:
                return config
        return None

    def get_channels_by_role(self, role: ChannelRole) -> List[ChannelMapping]:
        """Get all channels assigned to a specific role."""
        return [m for m in self.channel_mappings if m.role == role]

    def validate(self) -> bool:
        """Validate the complete configuration."""
        if self.max_channels < 1 or self.max_channels > 32:
            return False

        if self.cross_talk_threshold < 0 or self.cross_talk_threshold > 1:
            return False

        if self.similarity_threshold < 0 or self.similarity_threshold > 1:
            return False

        if self.output_format not in ["separate", "merged", "annotated"]:
            return False

        # Validate all channel configs
        for config in self.channel_configs:
            if not config.validate():
                return False

        # Check for channel ID consistency
        mapping_ids = set(m.channel_id for m in self.channel_mappings)
        config_ids = set(c.channel_id for c in self.channel_configs)

        # All mapped channels should have configs
        if mapping_ids - config_ids:
            return False

        return True

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "max_channels": self.max_channels,
            "auto_detect_channels": self.auto_detect_channels,
            "channel_mappings": [m.to_dict() for m in self.channel_mappings],
            "channel_configs": [c.to_dict() for c in self.channel_configs],
            "enable_cross_talk_detection": self.enable_cross_talk_detection,
            "cross_talk_threshold": self.cross_talk_threshold,
            "enable_speaker_diarization": self.enable_speaker_diarization,
            "merge_similar_channels": self.merge_similar_channels,
            "similarity_threshold": self.similarity_threshold,
            "output_format": self.output_format,
            "preserve_channel_audio": self.preserve_channel_audio,
            "channel_visualization": self.channel_visualization,
            "real_time_processing": self.real_time_processing,
            "buffer_size": self.buffer_size,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ChannelIdentificationConfig":
        """Create from dictionary representation."""
        config = cls(
            max_channels=data.get("max_channels", 8),
            auto_detect_channels=data.get("auto_detect_channels", True),
            enable_cross_talk_detection=data.get("enable_cross_talk_detection", True),
            cross_talk_threshold=data.get("cross_talk_threshold", 0.3),
            enable_speaker_diarization=data.get("enable_speaker_diarization", True),
            merge_similar_channels=data.get("merge_similar_channels", False),
            similarity_threshold=data.get("similarity_threshold", 0.8),
            output_format=data.get("output_format", "separate"),
            preserve_channel_audio=data.get("preserve_channel_audio", True),
            channel_visualization=data.get("channel_visualization", False),
            real_time_processing=data.get("real_time_processing", False),
            buffer_size=data.get("buffer_size", 4096),
        )

        # Load channel mappings
        for mapping_data in data.get("channel_mappings", []):
            config.channel_mappings.append(ChannelMapping.from_dict(mapping_data))

        # Load channel configs
        for config_data in data.get("channel_configs", []):
            channel_config = ChannelConfig(**config_data)
            config.channel_configs.append(channel_config)

        return config

    def save_to_file(self, file_path: Union[str, Path]) -> None:
        """Save configuration to JSON file."""
        file_path = Path(file_path)
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def load_from_file(
        cls, file_path: Union[str, Path]
    ) -> "ChannelIdentificationConfig":
        """Load configuration from JSON file."""
        file_path = Path(file_path)
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls.from_dict(data)


# Predefined configurations for common scenarios
class PredefinedConfigs:
    """Common channel identification configurations."""

    @staticmethod
    def doctor_patient_consultation() -> ChannelIdentificationConfig:
        """Create configuration for typical doctor-patient consultation."""
        config = ChannelIdentificationConfig(
            max_channels=2, enable_speaker_diarization=True, output_format="annotated"
        )

        # Doctor channel
        config.add_channel_mapping(
            ChannelMapping(
                channel_id=0,
                channel_type=AudioChannelType.STEREO_LEFT,
                role=ChannelRole.PHYSICIAN,
                priority=1,
            )
        )
        config.add_channel_config(
            ChannelConfig(channel_id=0, sample_rate=16000, automatic_gain_control=True)
        )

        # Patient channel
        config.add_channel_mapping(
            ChannelMapping(
                channel_id=1,
                channel_type=AudioChannelType.STEREO_RIGHT,
                role=ChannelRole.PATIENT,
                priority=2,
            )
        )
        config.add_channel_config(
            ChannelConfig(
                channel_id=1,
                sample_rate=16000,
                automatic_gain_control=True,
            )
        )

        return config

    @staticmethod
    def doctor_patient_consultation_advanced() -> ChannelIdentificationConfig:
        """Create configuration for typical doctor-patient consultation."""
        config = ChannelIdentificationConfig(
            max_channels=2, enable_speaker_diarization=True, output_format="annotated"
        )

        # Doctor channel
        config.add_channel_mapping(
            ChannelMapping(
                channel_id=0,
                channel_type=AudioChannelType.STEREO_LEFT,
                role=ChannelRole.PHYSICIAN,
                priority=1,
            )
        )
        config.add_channel_config(
            ChannelConfig(channel_id=0, sample_rate=16000, automatic_gain_control=True)
        )

        # Patient channel
        config.add_channel_mapping(
            ChannelMapping(
                channel_id=1,
                channel_type=AudioChannelType.STEREO_RIGHT,
                role=ChannelRole.PATIENT,
                priority=2,
            )
        )
        config.add_channel_config(
            ChannelConfig(
                channel_id=1,
                sample_rate=16000,
                automatic_gain_control=True,
            )
        )

        return config

    @staticmethod
    def telemedicine_session() -> ChannelIdentificationConfig:
        """Create configuration for telemedicine with potential interpreter."""
        config = ChannelIdentificationConfig(
            max_channels=3,
            enable_cross_talk_detection=True,
            enable_speaker_diarization=True,
            output_format="separate",
        )

        # Remote physician channel
        config.add_channel_mapping(
            ChannelMapping(
                channel_id=0,
                channel_type=AudioChannelType.TELEPHONE,
                role=ChannelRole.PHYSICIAN,
                expected_quality=ChannelQuality.FAIR,
                priority=1,
            )
        )
        config.add_channel_config(
            ChannelConfig(
                channel_id=0,
                sample_rate=8000,  # Telephone quality
                echo_cancellation=True,
                automatic_gain_control=True,
            )
        )

        # Patient channel
        config.add_channel_mapping(
            ChannelMapping(
                channel_id=1,
                channel_type=AudioChannelType.MICROPHONE_ARRAY,
                role=ChannelRole.PATIENT,
                priority=2,
            )
        )
        config.add_channel_config(ChannelConfig(channel_id=1, sample_rate=16000))

        # Interpreter channel (optional)
        config.add_channel_mapping(
            ChannelMapping(
                channel_id=2,
                channel_type=AudioChannelType.MICROPHONE_ARRAY,
                role=ChannelRole.INTERPRETER,
                priority=3,
            )
        )
        config.add_channel_config(
            ChannelConfig(
                channel_id=2,
                sample_rate=16000,
                enabled=False,  # Enable when interpreter joins
            )
        )

        return config

    @staticmethod
    def emergency_room_recording() -> ChannelIdentificationConfig:
        """Create configuration for busy emergency room environment."""
        config = ChannelIdentificationConfig(
            max_channels=8,
            auto_detect_channels=True,
            enable_cross_talk_detection=True,
            merge_similar_channels=True,
            similarity_threshold=0.7,
            output_format="merged",
        )

        # Configure multiple microphone arrays
        roles = [
            ChannelRole.PHYSICIAN,
            ChannelRole.NURSE,
            ChannelRole.PATIENT,
            ChannelRole.TECHNICIAN,
        ]

        for i in range(4):
            config.add_channel_mapping(
                ChannelMapping(
                    channel_id=i,
                    channel_type=AudioChannelType.MICROPHONE_ARRAY,
                    role=roles[i % len(roles)],
                    priority=1 if i < 2 else 2,
                )
            )
            config.add_channel_config(
                ChannelConfig(
                    channel_id=i,
                    sample_rate=16000,
                    voice_activity_detection=True,
                    automatic_gain_control=True,
                    preprocessing_filters=["bandpass", "compressor"],
                )
            )

        return config
