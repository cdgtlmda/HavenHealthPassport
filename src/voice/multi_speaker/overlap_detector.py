"""Overlap Detector for Multi-Speaker Conversations.

This module provides advanced overlap detection and analysis for
multi-speaker medical conversations.
"""

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

from ..speaker_identification import SpeakerSegment

logger = logging.getLogger(__name__)


@dataclass
class SpeechOverlap:
    """Detailed information about speech overlap."""

    start_time: float
    end_time: float
    speakers: Set[str]
    overlap_ratio: float  # Percentage of overlap
    dominant_speaker: Optional[str] = None
    overlap_pattern: str = "unknown"  # simultaneous, interruption, back-channel

    @property
    def duration(self) -> float:
        """Get overlap duration."""
        return self.end_time - self.start_time

    @property
    def speaker_count(self) -> int:
        """Get number of overlapping speakers."""
        return len(self.speakers)


@dataclass
class CrossTalkMetrics:
    """Metrics for cross-talk analysis."""

    total_overlaps: int = 0
    total_overlap_duration: float = 0.0
    overlap_percentage: float = 0.0
    interruption_count: int = 0
    back_channel_count: int = 0
    simultaneous_speech_count: int = 0
    max_concurrent_speakers: int = 0
    problematic_overlaps: List[SpeechOverlap] = field(default_factory=list)


@dataclass
class OverlapAnalysis:
    """Complete analysis of overlaps in a conversation."""

    overlaps: List[SpeechOverlap]
    metrics: CrossTalkMetrics
    speaker_overlap_matrix: Dict[Tuple[str, str], int]  # Speaker pair -> overlap count
    temporal_distribution: List[Tuple[float, int]]  # (timestamp, concurrent_speakers)
    recommendations: List[str] = field(default_factory=list)


class OverlapDetector:
    """Detects and analyzes speech overlaps in multi-speaker conversations."""

    def __init__(
        self, min_overlap_duration: float = 0.1, overlap_threshold: float = 0.8
    ):
        """Initialize the overlap detector."""
        self.min_overlap_duration = min_overlap_duration
        self.overlap_threshold = overlap_threshold

    def analyze_overlaps(
        self, segments: List[SpeakerSegment], conversation_duration: float
    ) -> OverlapAnalysis:
        """Perform comprehensive overlap analysis."""
        # Detect all overlaps
        overlaps = self._detect_all_overlaps(segments)

        # Calculate metrics
        metrics = self._calculate_metrics(overlaps, conversation_duration)

        # Build speaker overlap matrix
        overlap_matrix = self._build_overlap_matrix(overlaps)

        # Analyze temporal distribution
        temporal_dist = self._analyze_temporal_distribution(segments)

        # Generate recommendations
        recommendations = self._generate_recommendations(metrics)

        return OverlapAnalysis(
            overlaps=overlaps,
            metrics=metrics,
            speaker_overlap_matrix=overlap_matrix,
            temporal_distribution=temporal_dist,
            recommendations=recommendations,
        )

    def _detect_all_overlaps(
        self, segments: List[SpeakerSegment]
    ) -> List[SpeechOverlap]:
        """Detect all speech overlaps between segments."""
        overlaps = []

        # Sort segments by start time
        sorted_segments = sorted(segments, key=lambda s: s.start_time)

        # Use sweep line algorithm for efficient overlap detection
        active_segments: List[SpeakerSegment] = []

        for current_segment in sorted_segments:
            # Remove segments that have ended
            active_segments = [
                seg
                for seg in active_segments
                if seg.end_time > current_segment.start_time
            ]

            # Check for overlaps with active segments
            for active_seg in active_segments:
                if active_seg.speaker_id != current_segment.speaker_id:
                    overlap_start = max(
                        active_seg.start_time, current_segment.start_time
                    )
                    overlap_end = min(active_seg.end_time, current_segment.end_time)

                    if overlap_end - overlap_start >= self.min_overlap_duration:
                        # Calculate overlap characteristics
                        overlap_ratio = (overlap_end - overlap_start) / min(
                            active_seg.duration, current_segment.duration
                        )

                        # Determine overlap pattern
                        pattern = self._classify_overlap_pattern(
                            active_seg, current_segment, overlap_start, overlap_end
                        )

                        overlap = SpeechOverlap(
                            start_time=overlap_start,
                            end_time=overlap_end,
                            speakers={
                                active_seg.speaker_id or "",
                                current_segment.speaker_id or "",
                            },
                            overlap_ratio=overlap_ratio,
                            dominant_speaker=self._determine_dominant(
                                active_seg, current_segment
                            ),
                            overlap_pattern=pattern,
                        )
                        overlaps.append(overlap)

            active_segments.append(current_segment)

        return overlaps

    def _classify_overlap_pattern(
        self,
        seg1: SpeakerSegment,
        seg2: SpeakerSegment,
        overlap_start: float,
        overlap_end: float,
    ) -> str:
        """Classify the pattern of overlap."""
        overlap_duration = overlap_end - overlap_start

        # Back-channel: short overlap, usually acknowledgment
        if overlap_duration < 0.5:
            return "back-channel"

        # Interruption: one speaker starts while other is speaking
        seg1_before = seg1.start_time < seg2.start_time - 0.5
        seg2_before = seg2.start_time < seg1.start_time - 0.5

        if seg1_before or seg2_before:
            return "interruption"

        # Simultaneous speech: both start around same time
        return "simultaneous"

    def _determine_dominant(self, seg1: SpeakerSegment, seg2: SpeakerSegment) -> str:
        """Determine dominant speaker in overlap."""
        # Based on confidence and duration
        score1 = seg1.confidence * seg1.duration
        score2 = seg2.confidence * seg2.duration

        return (seg1.speaker_id or "") if score1 >= score2 else (seg2.speaker_id or "")

    def _calculate_metrics(
        self, overlaps: List[SpeechOverlap], conversation_duration: float
    ) -> CrossTalkMetrics:
        """Calculate cross-talk metrics."""
        metrics = CrossTalkMetrics()

        metrics.total_overlaps = len(overlaps)
        metrics.total_overlap_duration = sum(o.duration for o in overlaps)

        if conversation_duration > 0:
            metrics.overlap_percentage = (
                metrics.total_overlap_duration / conversation_duration
            ) * 100

        # Count overlap types
        for overlap in overlaps:
            if overlap.overlap_pattern == "interruption":
                metrics.interruption_count += 1
            elif overlap.overlap_pattern == "back-channel":
                metrics.back_channel_count += 1
            elif overlap.overlap_pattern == "simultaneous":
                metrics.simultaneous_speech_count += 1

        # Find problematic overlaps (long duration or many speakers)
        metrics.problematic_overlaps = [
            o for o in overlaps if o.duration > 2.0 or o.speaker_count > 2
        ]

        # Max concurrent speakers
        if overlaps:
            metrics.max_concurrent_speakers = max(o.speaker_count for o in overlaps)

        return metrics

    def _build_overlap_matrix(
        self, overlaps: List[SpeechOverlap]
    ) -> Dict[Tuple[str, str], int]:
        """Build matrix of speaker overlap counts."""
        matrix: Dict[Tuple[str, str], int] = defaultdict(int)

        for overlap in overlaps:
            speakers = sorted(list(overlap.speakers))
            if len(speakers) >= 2:
                # Count overlaps between each pair
                for i, speaker_i in enumerate(speakers):
                    for j in range(i + 1, len(speakers)):
                        pair = (speaker_i, speakers[j])
                        matrix[pair] += 1

        return dict(matrix)

    def _analyze_temporal_distribution(
        self, segments: List[SpeakerSegment]
    ) -> List[Tuple[float, int]]:
        """Analyze temporal distribution of concurrent speakers."""
        events = []

        # Create events for segment starts and ends
        for segment in segments:
            events.append((segment.start_time, 1, segment.speaker_label))  # Start
            events.append((segment.end_time, -1, segment.speaker_label))  # End

        # Sort events by time
        events.sort(key=lambda x: x[0])

        # Track concurrent speakers
        active_speakers = set()
        distribution = []

        for time, event_type, speaker in events:
            if event_type == 1:
                active_speakers.add(speaker)
            else:
                active_speakers.discard(speaker)

            distribution.append((time, len(active_speakers)))

        return distribution

    def _generate_recommendations(self, metrics: CrossTalkMetrics) -> List[str]:
        """Generate recommendations based on overlap analysis."""
        recommendations = []

        # High overlap percentage
        if metrics.overlap_percentage > 20:
            recommendations.append(
                f"High overlap rate ({metrics.overlap_percentage:.1f}%) - "
                "Consider implementing turn-taking protocols"
            )

        # Many interruptions
        if metrics.interruption_count > 10:
            recommendations.append(
                f"Frequent interruptions ({metrics.interruption_count}) detected - "
                "May impact communication quality"
            )

        # Problematic overlaps
        if metrics.problematic_overlaps:
            recommendations.append(
                f"{len(metrics.problematic_overlaps)} problematic overlaps found - "
                "Review audio quality and speaker positioning"
            )

        # Too many concurrent speakers
        if metrics.max_concurrent_speakers > 3:
            recommendations.append(
                "Multiple concurrent speakers detected - "
                "Consider using separate microphones or channels"
            )

        # Positive feedback for good patterns
        if metrics.back_channel_count > metrics.interruption_count:
            recommendations.append(
                "Good use of back-channel communication indicates active listening"
            )

        return recommendations
