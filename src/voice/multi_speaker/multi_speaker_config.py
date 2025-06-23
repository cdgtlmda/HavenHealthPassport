"""Multi-Speaker Configuration for Medical Conversations.

This module defines configuration structures for handling multiple speakers
in medical transcription scenarios.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List


class OverlapHandling(Enum):
    """Strategies for handling overlapping speech."""

    PRIORITIZE_PRIMARY = "prioritize_primary"
    MERGE_OVERLAPS = "merge_overlaps"
    SEPARATE_TRACKS = "separate_tracks"
    INTELLIGENT_SWITCHING = "intelligent_switching"
    PRESERVE_ALL = "preserve_all"


class SpeakerGrouping(Enum):
    """Methods for grouping speakers."""

    BY_ROLE = "by_role"
    BY_CHANNEL = "by_channel"
    BY_VOICE_SIMILARITY = "by_voice_similarity"
    BY_INTERACTION_PATTERN = "by_interaction_pattern"
    DYNAMIC = "dynamic"


class AudioChannel(Enum):
    """Audio channel configurations."""

    MONO = "mono"
    STEREO = "stereo"
    MULTI_CHANNEL = "multi_channel"
    TELEPHONE = "telephone"
    CONFERENCE = "conference"


@dataclass
class ChannelConfig:
    """Configuration for audio channel handling."""

    channel_count: int = 1
    channel_layout: AudioChannel = AudioChannel.MONO
    channel_assignments: Dict[int, str] = field(
        default_factory=dict
    )  # channel -> speaker_id
    auto_detect_channels: bool = True
    separate_channel_transcription: bool = False
    channel_quality_threshold: float = 0.7


@dataclass
class MultiSpeakerConfig:
    """Configuration for multi-speaker support."""

    # Basic settings
    max_concurrent_speakers: int = 4
    min_speech_duration_ms: int = 500
    max_speech_gap_ms: int = 1500

    # Overlap handling
    overlap_handling: OverlapHandling = OverlapHandling.INTELLIGENT_SWITCHING
    overlap_threshold_ms: int = 200
    cross_talk_tolerance: float = 0.15  # 15% overlap tolerance

    # Speaker clustering
    enable_speaker_clustering: bool = True
    clustering_threshold: float = 0.85
    min_cluster_size: int = 3
    speaker_grouping: SpeakerGrouping = SpeakerGrouping.DYNAMIC

    # Voice activity detection
    vad_aggressiveness: int = 2  # 0-3, higher = more aggressive
    energy_threshold: float = 0.3
    silence_duration_ms: int = 300

    # Real-time processing
    enable_realtime: bool = True
    buffer_size_ms: int = 2000
    lookahead_ms: int = 500

    # Quality settings
    min_confidence_score: float = 0.7
    require_speaker_consistency: bool = True
    enable_echo_cancellation: bool = True

    # Channel configuration
    channel_config: ChannelConfig = field(default_factory=ChannelConfig)

    def validate(self) -> List[str]:
        """Validate the configuration."""
        errors = []

        if self.max_concurrent_speakers < 2:
            errors.append("Max concurrent speakers must be at least 2")

        if self.min_speech_duration_ms < 100:
            errors.append("Minimum speech duration must be at least 100ms")

        if self.overlap_threshold_ms < 50:
            errors.append("Overlap threshold must be at least 50ms")

        if not 0 <= self.cross_talk_tolerance <= 1:
            errors.append("Cross-talk tolerance must be between 0 and 1")

        return errors
