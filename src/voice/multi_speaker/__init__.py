"""Multi-Speaker Support Module for Medical Conversations.

This module provides advanced multi-speaker capabilities for handling
complex medical conversations with multiple participants.
"""

from .channel_manager import (
    AudioChannelInfo,
    ChannelAssignment,
    ChannelManager,
    ChannelSeparator,
)
from .multi_speaker_config import (
    AudioChannel,
    ChannelConfig,
    MultiSpeakerConfig,
    OverlapHandling,
    SpeakerGrouping,
)
from .multi_speaker_processor import (
    ConversationFlow,
    MultiSpeakerProcessor,
    OverlapSegment,
    SpeakerCluster,
)
from .overlap_detector import (
    CrossTalkMetrics,
    OverlapAnalysis,
    OverlapDetector,
    SpeechOverlap,
)
from .realtime_tracker import (
    ActiveSpeaker,
    RealtimeMultiSpeakerTracker,
    SpeakerState,
    SpeakerTransition,
)

__all__ = [
    # Configuration
    "MultiSpeakerConfig",
    "ChannelConfig",
    "OverlapHandling",
    "SpeakerGrouping",
    "AudioChannel",
    # Processing
    "MultiSpeakerProcessor",
    "SpeakerCluster",
    "OverlapSegment",
    "ConversationFlow",
    # Channel Management
    "ChannelManager",
    "ChannelAssignment",
    "AudioChannelInfo",
    "ChannelSeparator",
    # Overlap Detection
    "OverlapDetector",
    "OverlapAnalysis",
    "CrossTalkMetrics",
    "SpeechOverlap",
    # Real-time Tracking
    "RealtimeMultiSpeakerTracker",
    "SpeakerState",
    "ActiveSpeaker",
    "SpeakerTransition",
]
