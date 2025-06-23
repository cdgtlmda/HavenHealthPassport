"""Real-time Multi-Speaker Tracker for Medical Conversations.

This module provides real-time tracking of multiple speakers in
ongoing medical conversations.
"""

import asyncio
import logging
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

from .multi_speaker_config import MultiSpeakerConfig

logger = logging.getLogger(__name__)


@dataclass
class SpeakerState:
    """Current state of a speaker."""

    speaker_id: str
    is_active: bool = False
    last_active_time: Optional[float] = None
    total_speaking_time: float = 0.0
    segment_count: int = 0
    average_segment_duration: float = 0.0
    current_confidence: float = 0.0

    def update_activity(self, timestamp: float, is_speaking: bool) -> None:
        """Update speaker activity state."""
        if is_speaking:
            self.is_active = True
            self.last_active_time = timestamp
        else:
            self.is_active = False


@dataclass
class ActiveSpeaker:
    """Information about currently active speaker."""

    speaker_id: str
    start_time: float
    confidence: float
    predicted_end_time: Optional[float] = None

    @property
    def duration(self) -> float:
        """Get current speaking duration."""
        return datetime.utcnow().timestamp() - self.start_time


@dataclass
class SpeakerTransition:
    """Represents a transition between speakers."""

    from_speaker: str
    to_speaker: str
    transition_time: float
    gap_duration: float  # Silence between speakers
    overlap_duration: float  # Overlap if any
    transition_type: str  # smooth, interrupted, overlapped


class RealtimeMultiSpeakerTracker:
    """Tracks multiple speakers in real-time during medical conversations."""

    def __init__(self, config: MultiSpeakerConfig):
        """Initialize the real-time tracker."""
        self.config = config
        self.speaker_states: Dict[str, SpeakerState] = {}
        self.active_speakers: List[ActiveSpeaker] = []
        self.transition_history: deque = deque(maxlen=100)
        self.buffer_window = config.buffer_size_ms / 1000.0

        # Real-time metrics
        self.current_overlap_count = 0
        self.total_transitions = 0
        self.last_update_time = datetime.utcnow().timestamp()

        # Prediction model (simplified)
        self.avg_segment_durations: Dict[str, float] = {}

    async def start_tracking(self) -> None:
        """Start real-time tracking."""
        logger.info("Starting real-time multi-speaker tracking")

        # Start background tasks
        asyncio.create_task(self._monitor_speakers())
        asyncio.create_task(self._update_predictions())

    def update_speaker_activity(
        self,
        speaker_id: str,
        timestamp: float,
        is_speaking: bool,
        confidence: float = 1.0,
    ) -> None:
        """Update speaker activity in real-time."""
        # Create or update speaker state
        if speaker_id not in self.speaker_states:
            self.speaker_states[speaker_id] = SpeakerState(speaker_id=speaker_id)

        state = self.speaker_states[speaker_id]
        previous_state = state.is_active

        # Update state
        state.update_activity(timestamp, is_speaking)
        state.current_confidence = confidence

        # Handle state transitions
        if is_speaking and not previous_state:
            # Speaker started
            self._handle_speaker_start(speaker_id, timestamp, confidence)
        elif not is_speaking and previous_state:
            # Speaker stopped
            self._handle_speaker_stop(speaker_id, timestamp)

        self.last_update_time = timestamp

    def _handle_speaker_start(
        self, speaker_id: str, timestamp: float, confidence: float
    ) -> None:
        """Handle speaker starting to speak."""
        # Check for transitions
        if self.active_speakers:
            last_active = self.active_speakers[-1]
            gap = timestamp - (
                last_active.start_time + (last_active.predicted_end_time or 0)
            )

            transition = SpeakerTransition(
                from_speaker=last_active.speaker_id,
                to_speaker=speaker_id,
                transition_time=timestamp,
                gap_duration=max(0, gap),
                overlap_duration=max(0, -gap),
                transition_type=self._classify_transition(gap),
            )
            self.transition_history.append(transition)
            self.total_transitions += 1

        # Add to active speakers
        active = ActiveSpeaker(
            speaker_id=speaker_id,
            start_time=timestamp,
            confidence=confidence,
            predicted_end_time=self._predict_end_time(speaker_id, timestamp),
        )
        self.active_speakers.append(active)

        # Update overlap count
        concurrent = sum(1 for s in self.active_speakers if s.speaker_id != speaker_id)
        if concurrent > 0:
            self.current_overlap_count += 1

    def _handle_speaker_stop(self, speaker_id: str, timestamp: float) -> None:
        """Handle speaker stopping."""
        # Remove from active speakers
        self.active_speakers = [
            s for s in self.active_speakers if s.speaker_id != speaker_id
        ]

        # Update speaker statistics
        state = self.speaker_states[speaker_id]
        if state.last_active_time:
            duration = timestamp - state.last_active_time
            state.total_speaking_time += duration
            state.segment_count += 1

            # Update average
            state.average_segment_duration = (
                state.total_speaking_time / state.segment_count
            )

            # Update prediction model
            self.avg_segment_durations[speaker_id] = state.average_segment_duration

    def _classify_transition(self, gap: float) -> str:
        """Classify the type of transition."""
        if gap < -0.2:  # Significant overlap
            return "overlapped"
        elif gap < 0.5:  # Smooth transition
            return "smooth"
        else:  # Interrupted with pause
            return "interrupted"

    def _predict_end_time(self, speaker_id: str, start_time: float) -> float:
        """Predict when speaker will stop speaking."""
        # Use historical average if available
        if speaker_id in self.avg_segment_durations:
            return start_time + self.avg_segment_durations[speaker_id]

        # Use default estimate
        return start_time + 5.0  # 5 second default

    async def _monitor_speakers(self) -> None:
        """Monitor speaker activity in background."""
        while True:
            await asyncio.sleep(1.0)  # Check every second

            current_time = datetime.utcnow().timestamp()

            # Check for stale active speakers
            for active in self.active_speakers[:]:
                if (
                    active.predicted_end_time
                    and current_time > active.predicted_end_time
                ):
                    # Speaker likely stopped
                    logger.debug(
                        "Speaker %s likely stopped (timeout)", active.speaker_id
                    )
                    self._handle_speaker_stop(active.speaker_id, current_time)

    async def _update_predictions(self) -> None:
        """Update predictions periodically."""
        while True:
            await asyncio.sleep(5.0)  # Update every 5 seconds

            # Update predictions for active speakers
            for active in self.active_speakers:
                active.predicted_end_time = self._predict_end_time(
                    active.speaker_id, active.start_time
                )

    def get_current_state(self) -> Dict[str, Any]:
        """Get current state of all speakers."""
        return {
            "active_speakers": [
                {
                    "speaker_id": s.speaker_id,
                    "duration": s.duration,
                    "confidence": s.confidence,
                }
                for s in self.active_speakers
            ],
            "total_speakers": len(self.speaker_states),
            "current_overlaps": self.current_overlap_count,
            "total_transitions": self.total_transitions,
            "speaker_states": {
                id: {
                    "is_active": state.is_active,
                    "total_time": state.total_speaking_time,
                    "segment_count": state.segment_count,
                    "avg_duration": state.average_segment_duration,
                }
                for id, state in self.speaker_states.items()
            },
        }

    def get_transition_analytics(self) -> Dict[str, Any]:
        """Get analytics about speaker transitions."""
        if not self.transition_history:
            return {"total_transitions": 0}

        transitions = list(self.transition_history)

        # Calculate metrics
        smooth_count = sum(1 for t in transitions if t.transition_type == "smooth")
        overlap_count = sum(1 for t in transitions if t.transition_type == "overlapped")
        interrupted_count = sum(
            1 for t in transitions if t.transition_type == "interrupted"
        )

        avg_gap = sum(t.gap_duration for t in transitions) / len(transitions)
        avg_overlap = sum(t.overlap_duration for t in transitions) / len(transitions)

        # Build transition matrix
        transition_pairs: defaultdict[tuple[str, str], int] = defaultdict(int)
        for t in transitions:
            pair = (t.from_speaker, t.to_speaker)
            transition_pairs[pair] += 1

        return {
            "total_transitions": len(transitions),
            "smooth_transitions": smooth_count,
            "overlapped_transitions": overlap_count,
            "interrupted_transitions": interrupted_count,
            "average_gap_duration": avg_gap,
            "average_overlap_duration": avg_overlap,
            "transition_pairs": dict(transition_pairs),
            "transition_rate_per_minute": (
                len(transitions) / (self.last_update_time / 60)
                if self.last_update_time > 0
                else 0
            ),
        }

    def predict_next_speaker(self) -> Optional[str]:
        """Predict the next likely speaker based on patterns."""
        if not self.transition_history or not self.active_speakers:
            return None

        current_speaker = self.active_speakers[-1].speaker_id

        # Find most common transition from current speaker
        transitions_from_current = [
            t for t in self.transition_history if t.from_speaker == current_speaker
        ]

        if not transitions_from_current:
            return None

        # Count transitions to each speaker
        next_speaker_counts: defaultdict[str, int] = defaultdict(int)
        for t in transitions_from_current:
            next_speaker_counts[t.to_speaker] += 1

        # Return most likely next speaker
        if next_speaker_counts:
            return max(next_speaker_counts.items(), key=lambda x: x[1])[0]
        return None
