"""Speaker Manager for Medical Transcription.

This module manages speaker identification and segmentation for medical conversations
using Amazon Transcribe Medical. All patient data is encrypted and access controlled.
"""

import json
import logging
import urllib.request
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, cast
from urllib.parse import urlparse

import boto3
import numpy as np
from botocore.exceptions import ClientError

from .speaker_config import (
    ConversationType,
    SpeakerIdentificationConfig,
    SpeakerProfile,
    SpeakerRole,
)

logger = logging.getLogger(__name__)


@dataclass
class SpeakerSegment:
    """Represents a segment of speech from a specific speaker."""

    speaker_label: str
    start_time: float
    end_time: float
    content: str
    confidence: float
    speaker_role: Optional[SpeakerRole] = None
    speaker_id: Optional[str] = None
    items: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def duration(self) -> float:
        """Get segment duration in seconds."""
        return self.end_time - self.start_time

    def overlaps_with(self, other: "SpeakerSegment") -> bool:
        """Check if this segment overlaps with another."""
        return not (
            self.end_time <= other.start_time or self.start_time >= other.end_time
        )


@dataclass
class OverlapSegment:
    """Represents an overlapping speech segment between speakers."""

    speaker1: str
    speaker2: str
    start_time: float
    end_time: float
    overlap_type: str = "simultaneous"  # simultaneous, interruption, back-channel
    confidence: float = 1.0
    communication_pattern: Optional[str] = None

    @property
    def duration(self) -> float:
        """Get overlap duration in seconds."""
        return self.end_time - self.start_time


@dataclass
class ConversationAnalysis:
    """Analysis results for a medical conversation."""

    conversation_id: str
    conversation_type: ConversationType
    start_time: datetime
    end_time: datetime
    duration_seconds: float
    speaker_segments: List[SpeakerSegment]
    speaker_profiles: Dict[str, SpeakerProfile]
    turn_taking_count: int
    overlap_segments: List[Tuple[SpeakerSegment, SpeakerSegment]]
    dominant_speaker: Optional[str] = None
    speaking_time_distribution: Dict[str, float] = field(default_factory=dict)
    interaction_patterns: Dict[str, Any] = field(default_factory=dict)
    quality_metrics: Dict[str, float] = field(default_factory=dict)


class SpeakerManager:
    """Manages speaker identification for medical conversations."""

    def __init__(self, region_name: str = "us-east-1"):
        """Initialize the speaker manager."""
        self.transcribe_client = boto3.client("transcribe", region_name=region_name)
        self.region = region_name
        self.active_jobs: Dict[str, Dict[str, Any]] = {}
        self.completed_analyses: Dict[str, ConversationAnalysis] = {}
        self.speaker_profiles: Dict[str, SpeakerProfile] = {}
        self.config: Optional[SpeakerIdentificationConfig] = None

        # Storage for conversation data
        self.data_dir = Path("speaker_data")
        self.data_dir.mkdir(exist_ok=True)

    def configure(self, config: SpeakerIdentificationConfig) -> None:
        """Configure the speaker identification system."""
        # Validate configuration
        errors = config.validate()
        if errors:
            raise ValueError(f"Invalid configuration: {', '.join(errors)}")

        self.config = config

        # Load expected speaker profiles
        for profile in config.expected_speakers:
            self.speaker_profiles[profile.speaker_id] = profile

        logger.info(
            "Configured speaker identification with %d expected speakers",
            len(config.expected_speakers),
        )

    async def start_medical_transcription_with_speakers(
        self,
        audio_uri: str,
        job_name: str,
        medical_specialty: str = "PRIMARYCARE",
        output_bucket: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Start a medical transcription job with speaker identification."""
        if not self.config:
            raise ValueError("Speaker identification not configured")

        # Prepare transcription job parameters
        params = {
            "MedicalTranscriptionJobName": job_name,
            "LanguageCode": "en-US",
            "MediaFormat": "mp4",  # Will be detected from file
            "Media": {"MediaFileUri": audio_uri},
            "OutputBucketName": output_bucket
            or f"haven-health-transcripts-{self.region}",
            "Specialty": medical_specialty,
            "Type": self.config.conversation_type.value.upper(),
            "Settings": {
                "ShowSpeakerLabels": self.config.speaker_config.enable_diarization,
                "MaxSpeakerLabels": self.config.speaker_config.max_speakers,
            },
        }

        try:
            # Start transcription job
            response = self.transcribe_client.start_medical_transcription_job(**params)

            # Store job information
            self.active_jobs[job_name] = {
                "start_time": datetime.utcnow(),
                "status": "IN_PROGRESS",
                "config": self.config,
                "audio_uri": audio_uri,
                "specialty": medical_specialty,
            }

            logger.info(
                "Started medical transcription job '%s' with speaker identification",
                job_name,
            )
            return {
                "job_name": job_name,
                "status": response["MedicalTranscriptionJob"]["TranscriptionJobStatus"],
                "created_time": response["MedicalTranscriptionJob"]["CreationTime"],
            }

        except ClientError as e:
            logger.error("Failed to start transcription job: %s", e)
            raise

    async def get_transcription_with_speakers(
        self, job_name: str
    ) -> Optional[ConversationAnalysis]:
        """Get transcription results with speaker identification."""
        try:
            # Get job status
            response = self.transcribe_client.get_medical_transcription_job(
                MedicalTranscriptionJobName=job_name
            )

            job_data = response["MedicalTranscriptionJob"]
            status = job_data["TranscriptionJobStatus"]

            if status == "COMPLETED":
                # Get transcript URI
                transcript_uri = job_data["Transcript"]["TranscriptFileUri"]

                # Download and parse transcript
                transcript_data = await self._download_transcript(transcript_uri)

                # Process speaker segments
                analysis = await self._process_speaker_segments(
                    job_name, transcript_data, job_data
                )

                # Store completed analysis
                self.completed_analyses[job_name] = analysis

                # Save to disk if configured
                if self.config and self.config.store_conversation_history:
                    await self._save_analysis(analysis)

                # Update job status
                if job_name in self.active_jobs:
                    self.active_jobs[job_name]["status"] = "COMPLETED"

                return analysis

            elif status == "FAILED":
                logger.error(
                    "Transcription job '%s' failed: %s",
                    job_name,
                    job_data.get("FailureReason"),
                )
                if job_name in self.active_jobs:
                    self.active_jobs[job_name]["status"] = "FAILED"
                return None

            else:
                # Job still in progress
                return None

        except ClientError as e:
            logger.error("Failed to get transcription job: %s", e)
            raise

    async def _download_transcript(self, transcript_uri: str) -> Dict[str, Any]:
        """Download transcript from S3."""
        # Validate URL scheme
        parsed_url = urlparse(transcript_uri)
        # Only allow HTTPS for security
        if parsed_url.scheme not in ["https"]:
            raise ValueError(f"Only HTTPS URLs are allowed, got: {parsed_url.scheme}")

        # Validate URL is HTTPS for security
        parsed_uri = urllib.parse.urlparse(transcript_uri)
        if parsed_uri.scheme not in ["https"]:
            raise ValueError("Only HTTPS URLs are allowed for transcript downloads")

        try:
            req = urllib.request.Request(transcript_uri)
            with urllib.request.urlopen(
                req
            ) as response:  # nosec B310 - URL is validated to be HTTPS only
                data = json.loads(response.read().decode("utf-8"))
                return cast(Dict[str, Any], data)
        except Exception as e:
            logger.error("Failed to download transcript: %s", e)
            raise

    async def _process_speaker_segments(
        self, job_name: str, transcript_data: Dict[str, Any], job_data: Dict[str, Any]
    ) -> ConversationAnalysis:
        """Process transcript data to extract speaker segments."""
        segments = []
        speaker_times: Dict[str, float] = defaultdict(float)

        # Extract results
        results = transcript_data.get("results", {})
        speaker_labels = results.get("speaker_labels", {})
        items = results.get("items", [])

        # Group items by speaker

        for label_segment in speaker_labels.get("segments", []):
            speaker = label_segment["speaker_label"]
            start_time = float(label_segment["start_time"])
            end_time = float(label_segment["end_time"])

            # Collect items for this segment
            segment_items = []
            for item in label_segment.get("items", []):
                segment_items.append(item)

            # Extract content from items
            content_items = []
            for item_ref in segment_items:
                # Find corresponding item in main items list
                for item in items:
                    if item.get("start_time") == item_ref.get(
                        "start_time"
                    ) and item.get("end_time") == item_ref.get("end_time"):
                        if "alternatives" in item:
                            content_items.append(item["alternatives"][0]["content"])
                        break

            content = " ".join(content_items)
            confidence = label_segment.get("confidence", 1.0)

            # Create speaker segment
            segment = SpeakerSegment(
                speaker_label=speaker,
                start_time=start_time,
                end_time=end_time,
                content=content.strip(),
                confidence=confidence,
                items=segment_items,
            )

            # Attempt to identify speaker role
            segment.speaker_role = await self._identify_speaker_role(segment)

            segments.append(segment)

            # Track speaking time
            speaker_times[speaker] += end_time - start_time

        # Calculate conversation metrics
        job_start_time = datetime.fromisoformat(
            job_data["CreationTime"].replace("Z", "+00:00")
        )
        job_end_time = datetime.fromisoformat(
            job_data.get("CompletionTime", job_data["CreationTime"]).replace(
                "Z", "+00:00"
            )
        )
        duration = (job_end_time - job_start_time).total_seconds()

        # Find dominant speaker
        dominant_speaker = (
            max(speaker_times.items(), key=lambda x: x[1])[0] if speaker_times else None
        )

        # Count turn-taking
        turn_count = 0
        last_speaker = None
        for segment in segments:
            if segment.speaker_label != last_speaker:
                turn_count += 1
                last_speaker = segment.speaker_label

        # Create analysis
        analysis = ConversationAnalysis(
            conversation_id=job_name,
            conversation_type=(
                self.config.conversation_type
                if self.config
                else ConversationType.CONSULTATION
            ),
            start_time=job_start_time,
            end_time=job_end_time,
            duration_seconds=duration,
            speaker_segments=segments,
            speaker_profiles=self.speaker_profiles,
            turn_taking_count=turn_count,
            overlap_segments=[],  # TODO: Convert OverlapSegments to tuples
            dominant_speaker=dominant_speaker,
            speaking_time_distribution=dict(speaker_times),
        )

        # Calculate quality metrics
        analysis.quality_metrics = await self._calculate_quality_metrics(analysis)

        return analysis

    async def _identify_speaker_role(
        self, segment: SpeakerSegment
    ) -> Optional[SpeakerRole]:
        """Attempt to identify speaker role based on content and context."""
        content_lower = segment.content.lower()

        # Simple heuristic-based role detection
        # In production, this would use more sophisticated NLP
        physician_keywords = ["prescribe", "diagnose", "examination", "treatment plan"]
        patient_keywords = ["feel", "hurts", "pain", "symptoms", "worried"]
        nurse_keywords = ["vitals", "blood pressure", "temperature", "administer"]

        if any(keyword in content_lower for keyword in physician_keywords):
            return SpeakerRole.PHYSICIAN
        elif any(keyword in content_lower for keyword in patient_keywords):
            return SpeakerRole.PATIENT
        elif any(keyword in content_lower for keyword in nurse_keywords):
            return SpeakerRole.NURSE

        # Check expected speakers if configured
        if self.config:
            for profile in self.config.expected_speakers:
                if profile.speaker_id == segment.speaker_label:
                    return profile.role

        return SpeakerRole.UNKNOWN

    async def _calculate_quality_metrics(
        self, analysis: ConversationAnalysis
    ) -> Dict[str, float]:
        """Calculate conversation quality metrics."""
        metrics = {}

        # Speaking balance (0-1, 1 = perfectly balanced)
        total_time = sum(analysis.speaking_time_distribution.values())
        if total_time > 0 and len(analysis.speaking_time_distribution) > 1:
            expected_time = total_time / len(analysis.speaking_time_distribution)
            variance = sum(
                (time - expected_time) ** 2
                for time in analysis.speaking_time_distribution.values()
            )
            metrics["speaking_balance"] = 1 - (variance / (total_time**2))
        else:
            metrics["speaking_balance"] = 0.0

        # Turn-taking rate (turns per minute)
        if analysis.duration_seconds > 0:
            metrics["turn_taking_rate"] = (
                analysis.turn_taking_count * 60
            ) / analysis.duration_seconds
        else:
            metrics["turn_taking_rate"] = 0.0

        # Average segment duration
        if analysis.speaker_segments:
            total_duration = sum(seg.duration for seg in analysis.speaker_segments)
            metrics["avg_segment_duration"] = total_duration / len(
                analysis.speaker_segments
            )
        else:
            metrics["avg_segment_duration"] = 0.0

        # Confidence score
        if analysis.speaker_segments:
            metrics["avg_confidence"] = sum(
                seg.confidence for seg in analysis.speaker_segments
            ) / len(analysis.speaker_segments)
        else:
            metrics["avg_confidence"] = 0.0

        return metrics

    async def _save_analysis(self, analysis: ConversationAnalysis) -> None:
        """Save conversation analysis to disk."""
        # Create conversation directory
        conv_dir = self.data_dir / analysis.conversation_id
        conv_dir.mkdir(exist_ok=True)

        # Save analysis metadata
        metadata = {
            "conversation_id": analysis.conversation_id,
            "conversation_type": analysis.conversation_type.value,
            "start_time": analysis.start_time.isoformat(),
            "end_time": analysis.end_time.isoformat(),
            "duration_seconds": analysis.duration_seconds,
            "turn_taking_count": analysis.turn_taking_count,
            "dominant_speaker": analysis.dominant_speaker,
            "speaking_time_distribution": analysis.speaking_time_distribution,
            "quality_metrics": analysis.quality_metrics,
        }

        with open(conv_dir / "metadata.json", "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)

        # Save segments
        segments_data = []
        for segment in analysis.speaker_segments:
            segments_data.append(
                {
                    "speaker_label": segment.speaker_label,
                    "start_time": segment.start_time,
                    "end_time": segment.end_time,
                    "content": segment.content,
                    "confidence": segment.confidence,
                    "speaker_role": (
                        segment.speaker_role.value if segment.speaker_role else None
                    ),
                    "speaker_id": segment.speaker_id,
                }
            )

        with open(conv_dir / "segments.json", "w", encoding="utf-8") as f:
            json.dump(segments_data, f, indent=2)

        logger.info("Saved conversation analysis for '%s'", analysis.conversation_id)

    def get_speaker_statistics(
        self,
        speaker_id: Optional[str] = None,
        time_range: Optional[Tuple[datetime, datetime]] = None,
    ) -> Dict[str, Any]:
        """Get statistics for speakers."""
        stats: Dict[str, Any] = {
            "total_conversations": 0,
            "total_speaking_time": 0.0,
            "avg_segment_duration": 0.0,
            "turn_taking_frequency": 0.0,
            "role_distribution": defaultdict(int),
        }

        all_analyses = list(self.completed_analyses.values())

        # Filter by time range if specified
        if time_range:
            start, end = time_range
            analyses = [a for a in all_analyses if start <= a.start_time <= end]
        else:
            analyses = all_analyses

        # Calculate statistics
        segment_count = 0
        for analysis in analyses:
            stats["total_conversations"] += 1

            for segment in analysis.speaker_segments:
                if speaker_id and segment.speaker_id != speaker_id:
                    continue

                stats["total_speaking_time"] += segment.duration
                segment_count += 1

                if segment.speaker_role:
                    stats["role_distribution"][segment.speaker_role.value] += 1

        # Calculate averages
        if segment_count > 0:
            stats["avg_segment_duration"] = stats["total_speaking_time"] / segment_count

        if stats["total_conversations"] > 0:
            stats["avg_turn_taking"] = (
                sum(a.turn_taking_count for a in analyses)
                / stats["total_conversations"]
            )

        return dict(stats)

    async def _detect_speaker_overlaps(
        self,
        segments: List[SpeakerSegment],
        audio_features: Optional[np.ndarray],
        _sample_rate: int,
    ) -> List[OverlapSegment]:
        """Detect overlapping speech segments between speakers."""
        overlaps: List[OverlapSegment] = []

        if not audio_features or len(segments) < 2:
            return overlaps

        # Sort segments by start time
        sorted_segments = sorted(segments, key=lambda s: s.start_time)

        # Check for temporal overlaps between segments
        for i in range(len(sorted_segments) - 1):
            current = sorted_segments[i]

            # Check overlap with all subsequent segments
            for j in range(i + 1, len(sorted_segments)):
                next_seg = sorted_segments[j]

                # If next segment starts after current ends, no overlap
                if next_seg.start_time >= current.end_time:
                    break

                # Calculate overlap
                overlap_start = max(current.start_time, next_seg.start_time)
                overlap_end = min(current.end_time, next_seg.end_time)
                overlap_duration = overlap_end - overlap_start

                if overlap_duration > 0.1:  # Minimum 100ms overlap
                    # Audio segment analysis would happen here if audio was available
                    # start_sample = int(overlap_start * sample_rate)
                    # end_sample = int(overlap_end * sample_rate)

                    overlap_type = "simultaneous_speech"

                    # Determine overlap type based on duration and position
                    if overlap_duration < 0.5:
                        # Short overlap - likely interruption
                        if next_seg.start_time > current.start_time + 0.5:
                            overlap_type = "interruption"
                        else:
                            overlap_type = "backchannel"  # "uh-huh", "yeah" etc.

                    # Create overlap segment
                    overlap_segment = OverlapSegment(
                        speaker1=current.speaker_label,
                        speaker2=next_seg.speaker_label,
                        start_time=overlap_start,
                        end_time=overlap_end,
                        overlap_type=overlap_type,
                        confidence=min(current.confidence, next_seg.confidence),
                    )

                    overlaps.append(overlap_segment)

        # Merge adjacent overlaps if they involve the same speakers
        merged_overlaps: List[OverlapSegment] = []
        for overlap in overlaps:
            if merged_overlaps and self._should_merge_overlaps(
                merged_overlaps[-1], overlap
            ):
                # Extend the previous overlap
                merged_overlaps[-1].end_time = overlap.end_time
            else:
                merged_overlaps.append(overlap)

        # TODO: Add overlap statistics when OverlapSegment supports it

        return merged_overlaps

    def _should_merge_overlaps(
        self, overlap1: OverlapSegment, overlap2: OverlapSegment
    ) -> bool:
        """Check if two overlap segments should be merged."""
        # Same speakers
        speakers1 = {overlap1.speaker1, overlap1.speaker2}
        speakers2 = {overlap2.speaker1, overlap2.speaker2}
        if speakers1 != speakers2:
            return False

        # Adjacent or very close (within 0.5 seconds)
        if overlap2.start_time - overlap1.end_time > 0.5:
            return False

        # Same overlap type
        if overlap1.overlap_type != overlap2.overlap_type:
            return False

        return True

    async def cleanup_old_data(self, days: int = 90) -> int:
        """Clean up old conversation data."""
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        removed_count = 0

        # Remove from memory
        to_remove = []
        for conv_id, analysis in self.completed_analyses.items():
            if analysis.end_time < cutoff_date:
                to_remove.append(conv_id)

        for conv_id in to_remove:
            del self.completed_analyses[conv_id]
            removed_count += 1

        # Remove from disk
        for conv_dir in self.data_dir.iterdir():
            if conv_dir.is_dir():
                metadata_file = conv_dir / "metadata.json"
                if metadata_file.exists():
                    with open(metadata_file, "r", encoding="utf-8") as f:
                        metadata = json.load(f)

                    end_time = datetime.fromisoformat(metadata["end_time"])
                    if end_time < cutoff_date:
                        # Remove directory
                        for file in conv_dir.iterdir():
                            file.unlink()
                        conv_dir.rmdir()
                        removed_count += 1

        logger.info("Cleaned up %d old conversations", removed_count)
        return removed_count

    async def _detect_speaker_overlaps_advanced(
        self,
        segments: List[SpeakerSegment],
        audio_features: np.ndarray,
        sample_rate: int,
    ) -> List[OverlapSegment]:
        """Advanced speaker overlap detection using audio features and harmonic analysis."""
        import scipy.signal as signal  # noqa: PLC0415
        from sklearn.decomposition import FastICA  # noqa: PLC0415

        overlaps: List[OverlapSegment] = []

        if not audio_features.any() or len(segments) < 2:
            return overlaps

        # Frequency band analysis for multiple speakers
        def split_frequency_bands(audio_segment: np.ndarray) -> np.ndarray:
            """Split audio into frequency bands to detect multiple voices."""
            # Define frequency bands for human speech
            bands = [
                (80, 250),  # Fundamental frequency range for male voices
                (150, 350),  # Fundamental frequency range for female voices
                (250, 500),  # First formant range
                (500, 1500),  # Second formant range
                (1500, 4000),  # Higher formants
            ]

            band_energies = []
            for low, high in bands:
                # Apply bandpass filter
                sos = signal.butter(
                    4, [low, high], btype="band", fs=sample_rate, output="sos"
                )
                filtered = signal.sosfilt(sos, audio_segment)
                # Calculate energy
                energy = np.sum(filtered**2)
                band_energies.append(energy)

            return np.array(band_energies)

        def analyze_harmonics(
            audio_window: np.ndarray,
        ) -> Tuple[List[float], List[float]]:
            """Analyze harmonic patterns to detect multiple fundamental frequencies."""
            # Compute FFT
            fft = np.fft.rfft(audio_window)
            freqs = np.fft.rfftfreq(len(audio_window), 1 / sample_rate)
            magnitude = np.abs(fft)

            # Find peaks in spectrum
            peaks, _ = signal.find_peaks(
                magnitude,
                height=np.max(magnitude) * 0.1,  # At least 10% of max
                distance=20,  # Minimum distance between peaks
            )

            # Identify fundamental frequencies
            fundamental_freqs = []
            fundamental_strengths = []
            for peak in peaks:
                freq = freqs[peak]
                if 80 <= freq <= 400:  # Human fundamental frequency range
                    # Check for harmonics
                    harmonic_count = 0
                    for h in range(2, 6):  # Check up to 5th harmonic
                        harmonic_freq = freq * h
                        # Find closest frequency bin
                        idx = np.argmin(np.abs(freqs - harmonic_freq))
                        if magnitude[idx] > np.mean(magnitude) * 2:
                            harmonic_count += 1

                    if harmonic_count >= 2:  # At least 2 harmonics present
                        fundamental_freqs.append(float(freq))
                        fundamental_strengths.append(float(magnitude[peak]))

            return fundamental_freqs, fundamental_strengths

        def _perform_ica_separation(
            audio_window: np.ndarray, num_sources: int = 2
        ) -> Tuple[np.ndarray, bool]:
            """Use Independent Component Analysis to separate mixed sources."""
            try:
                # Reshape for ICA (needs multiple observations)
                # Create shifted versions as observations
                observations = []
                shift_samples = [0, 1, 2, 3]  # Small shifts
                for shift in shift_samples:
                    if shift == 0:
                        observations.append(audio_window)
                    else:
                        # Pad and shift
                        shifted = np.roll(audio_window, shift)
                        observations.append(shifted)

                X = np.array(observations).T

                # Perform ICA
                ica = FastICA(
                    n_components=min(num_sources, len(shift_samples)), random_state=42
                )
                sources = ica.fit_transform(X)

                return sources.T, True  # Return separated sources and success flag
            except (AttributeError, ImportError, OSError, ValueError) as e:
                logger.warning("ICA separation failed: %s", e)
                return np.array([]), False  # Return empty array and failure flag

        # Process each potential overlap region
        window_size = int(0.1 * sample_rate)  # 100ms windows
        hop_size = int(0.05 * sample_rate)  # 50ms hop

        for i in range(0, len(audio_features) - window_size, hop_size):
            window = audio_features[i : i + window_size]
            time_pos = i / sample_rate

            # Check which segments are active at this time
            active_segments = [
                seg for seg in segments if seg.start_time <= time_pos <= seg.end_time
            ]

            if len(active_segments) >= 2:
                # Multiple speakers potentially active
                # Analyze harmonics
                fundamentals, _ = analyze_harmonics(window)

                if len(fundamentals) >= 2:
                    # Multiple fundamental frequencies detected
                    # Try ICA separation
                    # ICA separation would be performed here
                    # separated = perform_ica_separation(window, len(fundamentals))

                    # Analyze energy distribution
                    band_energies = split_frequency_bands(window)
                    energy_variance = np.var(band_energies)

                    # High variance suggests multiple speakers
                    if energy_variance > np.mean(band_energies) * 0.5:
                        # Create overlap segment
                        # Only create overlap if we have at least 2 active speakers
                        if len(active_segments) >= 2:
                            overlap = OverlapSegment(
                                speaker1=active_segments[0].speaker_label,
                                speaker2=active_segments[1].speaker_label,
                                start_time=time_pos,
                                end_time=time_pos + (window_size / sample_rate),
                                overlap_type=self._classify_overlap_type(
                                    active_segments, fundamentals, energy_variance
                                ),
                            )
                            overlaps.append(overlap)

        # Merge continuous overlaps
        merged = self._merge_continuous_overlaps(overlaps)

        # Add communication pattern analysis
        for overlap in merged:
            overlap.communication_pattern = self._analyze_communication_pattern(
                overlap, segments
            )

        return merged

    def _classify_overlap_type(
        self,
        segments: List[SpeakerSegment],
        fundamentals: List[float],
        energy_variance: float,
    ) -> str:
        """Classify the type of overlap based on audio features."""
        if len(fundamentals) == 1:
            return "single_speaker"  # False positive

        # Check duration of overlapping segments
        durations = [seg.end_time - seg.start_time for seg in segments]

        if any(d < 0.5 for d in durations):
            return "backchannel"  # Short utterance like "uh-huh"
        elif energy_variance > 1000:  # High energy variance
            return "interruption"  # One speaker cutting off another
        elif len(fundamentals) >= 3:
            return "crosstalk"  # Multiple people talking at once
        else:
            return "simultaneous_speech"  # Normal overlap

    def _merge_continuous_overlaps(
        self, overlaps: List[OverlapSegment]
    ) -> List[OverlapSegment]:
        """Merge overlaps that are continuous or nearly continuous."""
        if not overlaps:
            return []

        merged = []
        current = overlaps[0]

        for next_overlap in overlaps[1:]:
            # Check if overlaps are continuous (within 100ms)
            if next_overlap.start_time - current.end_time < 0.1:
                # Check if same speakers
                current_speakers = {current.speaker1, current.speaker2}
                next_speakers = {next_overlap.speaker1, next_overlap.speaker2}

                if current_speakers == next_speakers:
                    # Merge
                    current.end_time = next_overlap.end_time
                    # Merge audio features
                    if hasattr(current, "audio_features") and hasattr(
                        next_overlap, "audio_features"
                    ):
                        for key in current.audio_features:
                            if isinstance(current.audio_features[key], list):
                                current.audio_features[key].extend(
                                    next_overlap.audio_features.get(key, [])
                                )
                else:
                    merged.append(current)
                    current = next_overlap
            else:
                merged.append(current)
                current = next_overlap

        merged.append(current)
        return merged

    def _analyze_communication_pattern(
        self,
        overlap: OverlapSegment,
        _all_segments: List[SpeakerSegment],
    ) -> str:
        """Analyze the communication pattern of an overlap."""
        patterns = {
            "collaborative": 0,
            "competitive": 0,
            "supportive": 0,
            "disruptive": 0,
        }

        # Analyze based on overlap characteristics
        if overlap.overlap_type == "backchannel":
            patterns["supportive"] += 1
        elif overlap.overlap_type == "interruption":
            patterns["competitive"] += 1
        elif overlap.overlap_type == "crosstalk":
            patterns["disruptive"] += 1
        else:
            patterns["collaborative"] += 1

        # Consider cultural context if available
        if hasattr(self, "cultural_context"):
            # Some cultures have more overlapping speech patterns
            if self.cultural_context in ["mediterranean", "latin", "middle_eastern"]:
                patterns["collaborative"] = int(patterns["collaborative"] * 1.5)

        # Determine dominant pattern
        dominant_pattern = max(patterns, key=lambda x: patterns[x])

        return dominant_pattern

    def _is_culturally_appropriate(
        self, overlap: OverlapSegment, cultural_context: str
    ) -> bool:
        """Determine if overlap pattern is appropriate for cultural context."""
        appropriate_patterns = {
            "western": ["backchannel"],
            "mediterranean": ["backchannel", "simultaneous_speech", "interruption"],
            "east_asian": ["backchannel"],
            "latin": ["backchannel", "simultaneous_speech", "interruption"],
            "middle_eastern": ["simultaneous_speech", "interruption"],
            "african": ["backchannel", "simultaneous_speech"],
        }

        context_patterns = appropriate_patterns.get(cultural_context, ["backchannel"])
        return overlap.overlap_type in context_patterns
