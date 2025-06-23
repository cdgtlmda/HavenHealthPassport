"""
Channel Identification Module for Amazon Transcribe Medical.

This module provides comprehensive channel identification capabilities
for multi-channel medical audio processing and transcription.
"""

from .channel_config import (
    AudioChannelType,
    ChannelConfig,
    ChannelIdentificationConfig,
    ChannelMapping,
    ChannelRole,
    PredefinedConfigs,
)
from .channel_processor import (
    ChannelAnalyzer,
    ChannelMetadata,
    ChannelProcessor,
    ChannelSeparator,
)
from .channel_transcription import (
    ChannelSegment,
    ChannelTranscriptionManager,
    ChannelTranscriptionResult,
)

__all__ = [
    "AudioChannelType",
    "ChannelConfig",
    "ChannelRole",
    "ChannelMapping",
    "ChannelIdentificationConfig",
    "PredefinedConfigs",
    "ChannelProcessor",
    "ChannelSeparator",
    "ChannelAnalyzer",
    "ChannelMetadata",
    "ChannelTranscriptionManager",
    "ChannelTranscriptionResult",
    "ChannelSegment",
]
