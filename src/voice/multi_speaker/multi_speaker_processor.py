"""Multi-Speaker Processor for Medical Conversations.

This module handles the processing of multi-speaker audio in medical settings,
including overlap detection, speaker clustering, and conversation flow analysis.
"""

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

from ..speaker_identification import SpeakerRole, SpeakerSegment
from .multi_speaker_config import MultiSpeakerConfig, OverlapHandling, SpeakerGrouping

logger = logging.getLogger(__name__)


@dataclass
class OverlapSegment:
    """Represents overlapping speech from multiple speakers."""

    start_time: float
    end_time: float
    speakers: List[str]  # Speaker labels involved
    primary_speaker: Optional[str] = None
    overlap_type: str = "cross_talk"  # cross_talk, interruption, back_channel
    confidence: float = 0.0

    @property
    def duration(self) -> float:
        """Get overlap duration in seconds."""
        return self.end_time - self.start_time

    @property
    def speaker_count(self) -> int:
        """Get number of overlapping speakers."""
        return len(self.speakers)


@dataclass
class SpeakerCluster:
    """Represents a cluster of related speakers."""

    cluster_id: str
    speakers: Set[str]
    primary_role: Optional[SpeakerRole] = None
    interaction_count: int = 0
    total_duration: float = 0.0
    characteristics: Dict[str, Any] = field(default_factory=dict)

    def add_speaker(self, speaker_id: str) -> None:
        """Add a speaker to the cluster."""
        self.speakers.add(speaker_id)

    def merge_with(self, other: "SpeakerCluster") -> None:
        """Merge another cluster into this one."""
        self.speakers.update(other.speakers)
        self.interaction_count += other.interaction_count
        self.total_duration += other.total_duration


@dataclass
class ConversationFlow:
    """Represents the flow of a multi-speaker conversation."""

    segments: List[SpeakerSegment]
    overlaps: List[OverlapSegment]
    speaker_clusters: List[SpeakerCluster]
    transition_matrix: Dict[Tuple[str, str], int]  # (from_speaker, to_speaker) -> count
    speaking_order: List[str]  # Chronological order of speakers

    @property
    def unique_speakers(self) -> Set[str]:
        """Get unique speaker labels."""
        return {seg.speaker_id for seg in self.segments if seg.speaker_id is not None}

    @property
    def total_overlap_duration(self) -> float:
        """Get total duration of overlapping speech."""
        return sum(overlap.duration for overlap in self.overlaps)


class MultiSpeakerProcessor:
    """Processes multi-speaker conversations in medical settings."""

    def __init__(self, config: MultiSpeakerConfig):
        """Initialize the multi-speaker processor."""
        self.config = config
        self._validate_config()

        # Processing state
        self.active_speakers: Set[str] = set()
        self.speaker_clusters: Dict[str, SpeakerCluster] = {}
        self.overlap_buffer: List[OverlapSegment] = []

    def _validate_config(self) -> None:
        """Validate configuration."""
        errors = self.config.validate()
        if errors:
            raise ValueError(f"Invalid configuration: {', '.join(errors)}")

    def process_conversation(self, segments: List[SpeakerSegment]) -> ConversationFlow:
        """Process a multi-speaker conversation."""
        # Sort segments by start time
        sorted_segments = sorted(segments, key=lambda s: s.start_time)

        # Detect overlaps
        overlaps = self._detect_overlaps(sorted_segments)

        # Handle overlaps based on strategy
        processed_segments = self._handle_overlaps(sorted_segments, overlaps)

        # Cluster speakers
        clusters = self._cluster_speakers(processed_segments)

        # Analyze conversation flow
        transition_matrix = self._build_transition_matrix(processed_segments)
        speaking_order = self._extract_speaking_order(processed_segments)

        return ConversationFlow(
            segments=processed_segments,
            overlaps=overlaps,
            speaker_clusters=clusters,
            transition_matrix=transition_matrix,
            speaking_order=speaking_order,
        )

    def _detect_overlaps(self, segments: List[SpeakerSegment]) -> List[OverlapSegment]:
        """Detect overlapping speech segments."""
        overlaps = []

        for i, seg1 in enumerate(segments):
            for seg2 in segments[i + 1 :]:
                # Check if segments overlap
                if seg1.speaker_id != seg2.speaker_id:
                    overlap_start = max(seg1.start_time, seg2.start_time)
                    overlap_end = min(seg1.end_time, seg2.end_time)

                    if overlap_start < overlap_end:
                        # Calculate overlap duration
                        overlap_duration = overlap_end - overlap_start

                        # Only consider significant overlaps
                        if overlap_duration * 1000 >= self.config.overlap_threshold_ms:
                            # Determine overlap type
                            overlap_type = self._classify_overlap(
                                seg1, seg2, overlap_duration
                            )

                            overlap = OverlapSegment(
                                start_time=overlap_start,
                                end_time=overlap_end,
                                speakers=[
                                    s
                                    for s in [seg1.speaker_id, seg2.speaker_id]
                                    if s is not None
                                ],
                                primary_speaker=self._determine_primary_speaker(
                                    seg1, seg2
                                ),
                                overlap_type=overlap_type,
                                confidence=min(seg1.confidence, seg2.confidence),
                            )
                            overlaps.append(overlap)

        return overlaps

    def _classify_overlap(
        self, seg1: SpeakerSegment, seg2: SpeakerSegment, overlap_duration: float
    ) -> str:
        """Classify the type of overlap."""
        # Short overlaps are usually back-channels
        if overlap_duration < 0.5:
            return "back_channel"

        # Check if one segment starts significantly before the other
        if seg1.start_time < seg2.start_time - 0.5:
            return "interruption"
        elif seg2.start_time < seg1.start_time - 0.5:
            return "interruption"

        return "cross_talk"

    def _determine_primary_speaker(
        self, seg1: SpeakerSegment, seg2: SpeakerSegment
    ) -> Optional[str]:
        """Determine the primary speaker in an overlap."""
        # Priority based on role
        role_priority = {
            SpeakerRole.DOCTOR: 3,  # type: ignore[attr-defined]
            SpeakerRole.NURSE: 2,
            SpeakerRole.PATIENT: 1,
            SpeakerRole.UNKNOWN: 0,
        }

        role1_priority = 0
        role2_priority = 0

        if hasattr(seg1, "role") and seg1.role:
            role1_priority = role_priority.get(seg1.role, 0)
        if hasattr(seg2, "role") and seg2.role:
            role2_priority = role_priority.get(seg2.role, 0)

        if role1_priority > role2_priority:
            return seg1.speaker_id
        elif role2_priority > role1_priority:
            return seg2.speaker_id

        # If same priority, use confidence
        if seg1.confidence > seg2.confidence:
            return seg1.speaker_id
        else:
            return seg2.speaker_id

    def _handle_overlaps(
        self, segments: List[SpeakerSegment], overlaps: List[OverlapSegment]
    ) -> List[SpeakerSegment]:
        """Handle overlapping segments based on configured strategy."""
        if self.config.overlap_handling == OverlapHandling.PRESERVE_ALL:
            return segments

        if self.config.overlap_handling == OverlapHandling.PRIORITIZE_PRIMARY:
            return self._prioritize_primary_speaker(segments, overlaps)

        if self.config.overlap_handling == OverlapHandling.MERGE_OVERLAPS:
            return self._merge_overlapping_segments(segments, overlaps)

        if self.config.overlap_handling == OverlapHandling.INTELLIGENT_SWITCHING:
            return self._intelligent_speaker_switching(segments, overlaps)

        return segments

    def _prioritize_primary_speaker(
        self, segments: List[SpeakerSegment], overlaps: List[OverlapSegment]
    ) -> List[SpeakerSegment]:
        """Prioritize primary speaker in overlaps."""
        # Create a copy of segments
        result_segments = []

        for segment in segments:
            # Check if this segment is involved in any overlap
            involved_overlaps = [
                o for o in overlaps if segment.speaker_id in o.speakers
            ]

            if not involved_overlaps:
                result_segments.append(segment)
            else:
                # Check if this speaker is primary in all overlaps
                is_primary = all(
                    o.primary_speaker == segment.speaker_id for o in involved_overlaps
                )
                if is_primary:
                    result_segments.append(segment)

        return sorted(result_segments, key=lambda s: s.start_time)

    def _intelligent_speaker_switching(
        self, segments: List[SpeakerSegment], overlaps: List[OverlapSegment]
    ) -> List[SpeakerSegment]:
        """Intelligently handle speaker switching in overlaps."""
        result_segments = []
        processed_times = set()

        for segment in segments:
            segment_key = (segment.start_time, segment.end_time, segment.speaker_id)

            if segment_key in processed_times:
                continue

            # Find overlaps involving this segment
            segment_overlaps = [
                o
                for o in overlaps
                if segment.speaker_id in o.speakers
                and o.start_time < segment.end_time
                and o.end_time > segment.start_time
            ]

            if not segment_overlaps:
                result_segments.append(segment)
            else:
                # For interruptions, keep the interruptor
                # For back-channels, keep the main speaker
                for overlap in segment_overlaps:
                    if overlap.overlap_type == "interruption":
                        if segment.start_time > overlap.start_time:
                            result_segments.append(segment)
                    elif overlap.overlap_type == "back_channel":
                        if segment.speaker_id == overlap.primary_speaker:
                            result_segments.append(segment)
                    else:  # cross_talk
                        if segment.speaker_id == overlap.primary_speaker:
                            result_segments.append(segment)

            processed_times.add(segment_key)

        return sorted(result_segments, key=lambda s: s.start_time)

    def _merge_overlapping_segments(
        self, segments: List[SpeakerSegment], _overlaps: List[OverlapSegment]
    ) -> List[SpeakerSegment]:
        """Merge overlapping segments into combined segments."""
        # Implementation would merge overlapping segments
        # For now, return segments as-is
        return segments

    def _cluster_speakers(self, segments: List[SpeakerSegment]) -> List[SpeakerCluster]:
        """Cluster speakers based on interaction patterns."""
        clusters = []

        if not self.config.enable_speaker_clustering:
            # Create one cluster per speaker
            for speaker in {s.speaker_id for s in segments if s.speaker_id is not None}:
                if speaker is not None:
                    cluster = SpeakerCluster(
                        cluster_id=f"cluster_{speaker}", speakers={speaker}
                    )
                    clusters.append(cluster)
            return clusters

        # Group speakers based on configured method
        if self.config.speaker_grouping == SpeakerGrouping.BY_ROLE:
            return self._cluster_by_role(segments)
        elif self.config.speaker_grouping == SpeakerGrouping.BY_INTERACTION_PATTERN:
            return self._cluster_by_interaction(segments)
        else:  # DYNAMIC
            return self._dynamic_clustering(segments)

    def _cluster_by_role(self, segments: List[SpeakerSegment]) -> List[SpeakerCluster]:
        """Cluster speakers by their roles."""
        role_clusters = defaultdict(set)

        for segment in segments:
            if hasattr(segment, "role") and segment.role:
                role_clusters[segment.role].add(segment.speaker_id)

        clusters = []
        for role, speakers in role_clusters.items():
            cluster = SpeakerCluster(
                cluster_id=f"cluster_{role.value}",
                speakers={s for s in speakers if s is not None},
                primary_role=role,
            )
            clusters.append(cluster)

        return clusters

    def _cluster_by_interaction(
        self, segments: List[SpeakerSegment]
    ) -> List[SpeakerCluster]:
        """Cluster speakers by interaction patterns."""
        # Build interaction graph
        interactions: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))

        for i in range(len(segments) - 1):
            speaker1 = segments[i].speaker_id
            speaker2 = segments[i + 1].speaker_id

            if speaker1 and speaker2 and speaker1 != speaker2:
                interactions[speaker1][speaker2] += 1
                interactions[speaker2][speaker1] += 1

        # Find strongly connected speakers
        clusters: List[SpeakerCluster] = []
        processed = set()

        for speaker in interactions:
            if speaker in processed:
                continue

            # Find speakers with strong interactions
            cluster_speakers = {speaker} if speaker else set()
            for other_speaker, count in interactions[speaker].items():
                if count >= self.config.min_cluster_size:
                    cluster_speakers.add(other_speaker)

            cluster = SpeakerCluster(
                cluster_id=f"cluster_interact_{len(clusters)}",
                speakers=cluster_speakers,
                interaction_count=sum(interactions[speaker].values()),
            )
            clusters.append(cluster)
            processed.update(cluster_speakers)

        return clusters

    def _dynamic_clustering(
        self, segments: List[SpeakerSegment]
    ) -> List[SpeakerCluster]:
        """Dynamically cluster speakers using multiple factors."""
        # Combine role and interaction clustering
        role_clusters = self._cluster_by_role(segments)
        interaction_clusters = self._cluster_by_interaction(segments)

        # Merge clusters with significant overlap
        merged_clusters = self._merge_clusters(role_clusters, interaction_clusters)
        return merged_clusters

    def _merge_clusters(
        self,
        role_clusters: List[SpeakerCluster],
        interaction_clusters: List[SpeakerCluster],
    ) -> List[SpeakerCluster]:
        """Merge role and interaction clusters intelligently."""
        merged: List[SpeakerCluster] = []
        used_speakers = set()

        # Prioritize role clusters
        for role_cluster in role_clusters:
            # Find overlapping interaction clusters
            overlapping_interaction = []
            for int_cluster in interaction_clusters:
                overlap = set(role_cluster.speakers) & set(int_cluster.speakers)
                if overlap:
                    overlapping_interaction.append((int_cluster, len(overlap)))

            if overlapping_interaction:
                # Merge with highest overlap
                best_match, _ = max(overlapping_interaction, key=lambda x: x[1])
                merged_speakers = role_cluster.speakers | best_match.speakers
                merged_cluster = SpeakerCluster(
                    cluster_id=f"merged_{len(merged)}", speakers=merged_speakers
                )
                merged.append(merged_cluster)
                used_speakers.update(merged_speakers)
            else:
                merged.append(role_cluster)
                used_speakers.update(role_cluster.speakers)

        # Add remaining interaction clusters
        for int_cluster in interaction_clusters:
            if not any(spk in used_speakers for spk in int_cluster.speakers):
                merged.append(int_cluster)

        return merged

    def _build_transition_matrix(
        self, segments: List[SpeakerSegment]
    ) -> Dict[Tuple[str, str], int]:
        """Build speaker transition matrix."""
        transitions: Dict[Tuple[str, str], int] = defaultdict(int)

        for i in range(len(segments) - 1):
            from_speaker = segments[i].speaker_id
            to_speaker = segments[i + 1].speaker_id

            if from_speaker and to_speaker and from_speaker != to_speaker:
                transitions[(from_speaker, to_speaker)] += 1

        # Build result with only valid transitions
        result: Dict[Tuple[str, str], int] = {}
        for key, value in transitions.items():
            if key[0] is not None and key[1] is not None:
                result[(key[0], key[1])] = value
        return result

    def _extract_speaking_order(self, segments: List[SpeakerSegment]) -> List[str]:
        """Extract chronological speaking order."""
        order: List[str] = []
        last_speaker: Optional[str] = None

        for segment in segments:
            if segment.speaker_id and segment.speaker_id != last_speaker:
                order.append(segment.speaker_id)
                last_speaker = segment.speaker_id

        return order

    def analyze_concurrent_speakers(
        self, segments: List[SpeakerSegment], time_window: float = 1.0
    ) -> Dict[float, Set[str]]:
        """Analyze concurrent speakers within time windows."""
        concurrent_map = {}

        # Create time windows
        if segments:
            start_time = segments[0].start_time
            end_time = segments[-1].end_time

            current_time = start_time
            while current_time < end_time:
                # Find active speakers in this window
                active = {
                    seg.speaker_id
                    for seg in segments
                    if seg.start_time <= current_time < seg.end_time
                    and seg.speaker_id is not None
                }

                if active:
                    concurrent_map[current_time] = active

                current_time += time_window

        return concurrent_map
