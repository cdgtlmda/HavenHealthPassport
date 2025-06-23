"""Speaker Identification Module for Medical Conversations.

This module provides speaker identification capabilities for Amazon Transcribe Medical,
enabling the system to differentiate between multiple speakers in medical conversations.
"""

from .speaker_analytics import (
    ConversationMetrics,
    SpeakerAnalytics,
    SpeakerTurnAnalysis,
)
from .speaker_config import (
    ConversationType,
    SpeakerConfig,
    SpeakerIdentificationConfig,
    SpeakerProfile,
    SpeakerRole,
)
from .speaker_manager import ConversationAnalysis, SpeakerManager, SpeakerSegment

__all__ = [
    # Configuration
    "ConversationType",
    "SpeakerRole",
    "SpeakerProfile",
    "SpeakerConfig",
    "SpeakerIdentificationConfig",
    # Management
    "SpeakerManager",
    "SpeakerSegment",
    "ConversationAnalysis",
    # Analytics
    "SpeakerAnalytics",
    "ConversationMetrics",
    "SpeakerTurnAnalysis",
]
