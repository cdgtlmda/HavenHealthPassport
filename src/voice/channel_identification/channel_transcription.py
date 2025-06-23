"""
Channel-Specific Transcription Management.

This module handles transcription results for individual channels
in multi-channel medical audio processing.

Security Note: This module processes medical transcriptions containing PHI.
All transcription data must be encrypted at rest and in transit. Access to
transcription results should be restricted to authorized healthcare personnel
only through role-based access controls.
"""

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from .channel_config import ChannelIdentificationConfig, ChannelRole
from .channel_processor import ChannelMetadata

logger = logging.getLogger(__name__)


@dataclass
class ChannelSegment:
    """Transcription segment for a specific channel."""

    channel_id: int
    start_time: float
    end_time: float
    text: str
    confidence: float = 0.0
    speaker_label: Optional[str] = None
    alternatives: List[Dict[str, float]] = field(default_factory=list)
    medical_entities: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "channel_id": self.channel_id,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "text": self.text,
            "confidence": self.confidence,
            "speaker_label": self.speaker_label,
            "alternatives": self.alternatives,
            "medical_entities": self.medical_entities,
        }


@dataclass
class ChannelTranscriptionResult:
    """Transcription result for a specific channel."""

    channel_id: int
    role: ChannelRole
    speaker_name: Optional[str] = None
    language_code: str = "en-US"
    segments: List[ChannelSegment] = field(default_factory=list)
    full_transcript: Optional[str] = None
    metadata: Optional[ChannelMetadata] = None
    medical_summary: Dict[str, Any] = field(default_factory=dict)
    confidence_score: float = 0.0
    duration: float = 0.0
    word_count: int = 0
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "channel_id": self.channel_id,
            "role": self.role.value,
            "speaker_name": self.speaker_name,
            "language_code": self.language_code,
            "segments": [seg.to_dict() for seg in self.segments],
            "full_transcript": self.full_transcript,
            "metadata": self.metadata.to_dict() if self.metadata else None,
            "medical_summary": self.medical_summary,
            "confidence_score": self.confidence_score,
            "duration": self.duration,
            "word_count": self.word_count,
            "timestamp": self.timestamp.isoformat(),
        }

    def add_segment(self, segment: ChannelSegment) -> None:
        """Add a transcription segment."""
        self.segments.append(segment)
        self._update_statistics()

    def _update_statistics(self) -> None:
        """Update transcript statistics."""
        if self.segments:
            # Update duration
            self.duration = max(seg.end_time for seg in self.segments)

            # Update word count
            self.word_count = sum(len(seg.text.split()) for seg in self.segments)

            # Update confidence score
            confidences = [
                seg.confidence for seg in self.segments if seg.confidence > 0
            ]
            if confidences:
                self.confidence_score = sum(confidences) / len(confidences)

            # Generate full transcript
            self.full_transcript = " ".join(seg.text for seg in self.segments)

    def merge_consecutive_segments(self, time_threshold: float = 0.5) -> None:
        """Merge consecutive segments from the same speaker."""
        if len(self.segments) < 2:
            return

        merged_segments = [self.segments[0]]

        for segment in self.segments[1:]:
            last_segment = merged_segments[-1]

            # Check if segments should be merged
            if (
                segment.speaker_label == last_segment.speaker_label
                and segment.start_time - last_segment.end_time < time_threshold
            ):
                # Merge segments
                last_segment.end_time = segment.end_time
                last_segment.text += " " + segment.text
                last_segment.confidence = (
                    last_segment.confidence + segment.confidence
                ) / 2
                last_segment.medical_entities.extend(segment.medical_entities)
            else:
                merged_segments.append(segment)

        self.segments = merged_segments
        self._update_statistics()


class ChannelTranscriptionManager:
    """
    Manages transcription results across multiple channels.

    This class coordinates channel-specific transcriptions and provides
    methods for merging, formatting, and exporting results.
    """

    def __init__(self, config: ChannelIdentificationConfig):
        """Initialize transcription manager."""
        self.config = config
        self.channel_results: Dict[int, ChannelTranscriptionResult] = {}
        self._lock = asyncio.Lock()

        # Initialize results for configured channels
        for mapping in config.channel_mappings:
            self.channel_results[mapping.channel_id] = ChannelTranscriptionResult(
                channel_id=mapping.channel_id,
                role=mapping.role,
                speaker_name=mapping.speaker_name,
                language_code=mapping.language_code or "en-US",
            )

    async def add_transcription_segment(
        self, channel_id: int, segment: ChannelSegment
    ) -> None:
        """Add transcription segment to specific channel."""
        async with self._lock:
            if channel_id in self.channel_results:
                self.channel_results[channel_id].add_segment(segment)
            else:
                # Create new result for unconfigured channel
                mapping = self.config.get_channel_mapping(channel_id)
                result = ChannelTranscriptionResult(
                    channel_id=channel_id,
                    role=mapping.role if mapping else ChannelRole.UNKNOWN,
                    speaker_name=mapping.speaker_name if mapping else None,
                )
                result.add_segment(segment)
                self.channel_results[channel_id] = result

    def update_channel_metadata(
        self, channel_id: int, metadata: ChannelMetadata
    ) -> None:
        """Update metadata for specific channel."""
        if channel_id in self.channel_results:
            self.channel_results[channel_id].metadata = metadata

    def get_channel_result(
        self, channel_id: int
    ) -> Optional[ChannelTranscriptionResult]:
        """Get transcription result for specific channel."""
        return self.channel_results.get(channel_id)

    def get_all_results(self) -> Dict[int, ChannelTranscriptionResult]:
        """Get all channel transcription results."""
        return self.channel_results.copy()

    def merge_channels(self, output_format: Optional[str] = None) -> Dict[str, Any]:
        """
        Merge transcriptions from all channels.

        Args:
            output_format: Format for merged output (from config if None)

        Returns:
            Merged transcription with channel annotations
        """
        if output_format is None:
            output_format = self.config.output_format

        merged_segments = []

        # Collect all segments from all channels
        for channel_id, result in self.channel_results.items():
            for segment in result.segments:
                merged_segments.append(
                    {
                        "channel_id": channel_id,
                        "role": result.role.value,
                        "speaker": result.speaker_name or f"Speaker {channel_id}",
                        "start_time": segment.start_time,
                        "end_time": segment.end_time,
                        "text": segment.text,
                        "confidence": segment.confidence,
                    }
                )

        # Sort by start time
        merged_segments.sort(key=lambda x: x["start_time"])

        if output_format == "separate":
            # Keep channels separate
            return {
                "format": "separate",
                "channels": {
                    str(ch_id): result.to_dict()
                    for ch_id, result in self.channel_results.items()
                },
            }

        elif output_format == "merged":
            # Create single transcript
            merged_text: List[str] = []
            for seg in merged_segments:
                merged_text.append(str(seg["text"]))

            return {
                "format": "merged",
                "transcript": " ".join(merged_text),
                "segments": merged_segments,
            }

        elif output_format == "annotated":
            # Create annotated transcript
            annotated_text: List[str] = []
            current_speaker = None

            for seg in merged_segments:
                speaker = f"{seg['role']}:{seg['speaker']}"
                if speaker != current_speaker:
                    annotated_text.append(f"\n[{speaker}]")
                    current_speaker = speaker
                annotated_text.append(str(seg["text"]))

            return {
                "format": "annotated",
                "transcript": " ".join(annotated_text),
                "segments": merged_segments,
            }

        else:
            raise ValueError(f"Unknown output format: {output_format}")

    def export_transcriptions(
        self, output_dir: Union[str, Path], include_metadata: bool = True
    ) -> Dict[str, Path]:
        """
        Export transcriptions to files.

        Args:
            output_dir: Output directory
            include_metadata: Whether to include metadata files

        Returns:
            Dictionary mapping output types to file paths
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        output_files = {}

        # Export individual channel transcripts
        for channel_id, result in self.channel_results.items():
            # Generate filename
            mapping = self.config.get_channel_mapping(channel_id)
            if mapping and mapping.speaker_name:
                filename = f"transcript_ch{channel_id}_{mapping.role.value}_{mapping.speaker_name}.json"
            else:
                filename = f"transcript_ch{channel_id}.json"

            file_path = output_dir / filename

            # Write transcript
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(result.to_dict(), f, indent=2)

            output_files[f"channel_{channel_id}"] = file_path

        # Export merged transcript
        merged = self.merge_channels()
        merged_path = output_dir / "merged_transcript.json"

        with open(merged_path, "w", encoding="utf-8") as f:
            json.dump(merged, f, indent=2)

        output_files["merged"] = merged_path

        # Export plain text versions
        for format_type in ["separate", "merged", "annotated"]:
            formatted = self.merge_channels(format_type)

            if format_type == "annotated":
                text_path = output_dir / f"transcript_{format_type}.txt"
                with open(text_path, "w", encoding="utf-8") as f:
                    f.write(formatted["transcript"])
                output_files[f"{format_type}_text"] = text_path

        # Export metadata if requested
        if include_metadata:
            metadata_path = output_dir / "transcription_metadata.json"
            metadata = {
                "config": self.config.to_dict(),
                "channel_count": len(self.channel_results),
                "total_segments": sum(
                    len(r.segments) for r in self.channel_results.values()
                ),
                "channel_summaries": {
                    str(ch_id): {
                        "role": result.role.value,
                        "speaker": result.speaker_name,
                        "duration": result.duration,
                        "word_count": result.word_count,
                        "confidence": result.confidence_score,
                        "segment_count": len(result.segments),
                    }
                    for ch_id, result in self.channel_results.items()
                },
            }

            with open(metadata_path, "w", encoding="utf-8") as f:
                json.dump(metadata, f, indent=2)

            output_files["metadata"] = metadata_path

        logger.info("Exported transcriptions to %s", output_dir)
        return output_files

    def generate_medical_summary(self) -> Dict[str, Any]:
        """
        Generate medical summary from all channels.

        Returns:
            Summary with medical entities, medications, conditions, etc.
        """
        summary: Dict[str, Any] = {
            "medications": [],
            "conditions": [],
            "procedures": [],
            "symptoms": [],
            "vitals": [],
            "allergies": [],
            "by_channel": {},
        }

        # Process each channel's transcription for medical entities
        for channel_id, result in self.channel_results.items():
            channel_summary: Dict[str, Any] = {
                "role": result.role.value,
                "speaker": result.speaker_name,
                "entities": {
                    "medications": [],
                    "conditions": [],
                    "procedures": [],
                    "symptoms": [],
                },
            }

            # Extract entities from segments
            for segment in result.segments:
                for entity in segment.medical_entities:
                    entity_type = entity.get("type", "").lower()
                    entity_text = entity.get("text", "")

                    if entity_type == "medication":
                        channel_summary["entities"]["medications"].append(entity_text)
                        if entity_text not in summary["medications"]:
                            summary["medications"].append(entity_text)
                    elif entity_type == "condition":
                        channel_summary["entities"]["conditions"].append(entity_text)
                        if entity_text not in summary["conditions"]:
                            summary["conditions"].append(entity_text)
                    elif entity_type == "procedure":
                        channel_summary["entities"]["procedures"].append(entity_text)
                        if entity_text not in summary["procedures"]:
                            summary["procedures"].append(entity_text)
                    elif entity_type == "symptom":
                        channel_summary["entities"]["symptoms"].append(entity_text)
                        if entity_text not in summary["symptoms"]:
                            summary["symptoms"].append(entity_text)

            summary["by_channel"][str(channel_id)] = channel_summary

        return summary
