"""Stress Analyzer implementation for medical voice processing."""

import logging
from collections import deque
from typing import Optional

from .models import StressAnalysisConfig

logger = logging.getLogger(__name__)


class StressAnalyzer:
    """
    Analyzes stress levels from voice recordings with medical context awareness.

    Implements multi-modal stress detection using acoustic, prosodic, and
    physiological voice markers relevant to medical assessment.
    """

    def __init__(self, config: Optional[StressAnalysisConfig] = None):
        """
        Initialize the stress analyzer.

        Args:
            config: Configuration for stress analysis
        """
        self.config = config or StressAnalysisConfig()
        self._init_analysis_buffers()

    def _init_analysis_buffers(self) -> None:
        """Initialize buffers for temporal analysis."""
        from typing import Deque  # noqa: PLC0415

        buffer_size = int(self.config.temporal_window_seconds * self.config.sample_rate)
        self.pitch_buffer: Deque[float] = deque(maxlen=buffer_size)
        self.amplitude_buffer: Deque[float] = deque(maxlen=buffer_size)
