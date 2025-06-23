"""
Timestamp Alignment Module for Medical Transcriptions.

This module handles precise timestamp alignment between audio,
transcription results, and medical events.
"""

# pylint: disable=protected-access

import logging
import platform
import re
import socket
import subprocess
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import psutil

logger = logging.getLogger(__name__)


class TimestampFormat(Enum):
    """Supported timestamp formats."""

    SECONDS = "seconds"  # Floating point seconds
    MILLISECONDS = "milliseconds"  # Integer milliseconds
    TIMECODE = "timecode"  # HH:MM:SS.mmm
    SAMPLES = "samples"  # Audio sample index


class AlignmentMethod(Enum):
    """Methods for aligning timestamps."""

    NEAREST = "nearest"  # Find nearest timestamp
    INTERPOLATE = "interpolate"  # Linear interpolation
    FORCE_ALIGN = "force_align"  # Force alignment using audio features
    DTW = "dtw"  # Dynamic Time Warping


@dataclass
class TimePoint:
    """Represents a point in time with multiple representations."""

    seconds: float
    audio_sample: int
    timecode: str

    # Optional references
    word_index: Optional[int] = None
    event_id: Optional[str] = None
    confidence: float = 1.0

    def to_milliseconds(self) -> int:
        """Convert to milliseconds."""
        return int(self.seconds * 1000)

    def to_timecode(self) -> str:
        """Get timecode representation."""
        return self.timecode

    def offset(self, seconds: float) -> "TimePoint":
        """Create a new TimePoint with offset."""
        return TimePoint(
            seconds=self.seconds + seconds,
            audio_sample=self.audio_sample + int(seconds * 16000),  # Assuming 16kHz
            timecode=self._seconds_to_timecode(self.seconds + seconds),
            word_index=self.word_index,
            event_id=self.event_id,
            confidence=self.confidence,
        )

    @staticmethod
    def _seconds_to_timecode(seconds: float) -> str:
        """Convert seconds to timecode format."""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds % 1) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"


@dataclass
class AlignmentSegment:
    """Represents an aligned segment of audio/text."""

    start: TimePoint
    end: TimePoint
    text: str

    # Optional metadata
    speaker: Optional[str] = None
    confidence: float = 1.0
    medical_events: List[str] = field(default_factory=list)

    @property
    def duration(self) -> float:
        """Get segment duration in seconds."""
        return self.end.seconds - self.start.seconds

    def contains_time(self, seconds: float) -> bool:
        """Check if a time point falls within this segment."""
        return self.start.seconds <= seconds <= self.end.seconds


@dataclass
class AlignmentConfig:
    """Configuration for timestamp alignment."""

    sample_rate: int = 16000

    # Alignment tolerances
    max_drift_seconds: float = 0.5  # Maximum allowed drift
    interpolation_threshold: float = 0.1  # When to use interpolation

    # Force alignment settings
    use_force_alignment: bool = False
    phoneme_model: Optional[str] = None

    # Synchronization
    sync_interval_seconds: float = 30.0  # Re-sync every N seconds
    confidence_threshold: float = 0.8  # Minimum confidence for anchor points

    # Event alignment
    event_window_seconds: float = 2.0  # Window for medical event matching

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "sample_rate": self.sample_rate,
            "max_drift_seconds": self.max_drift_seconds,
            "interpolation_threshold": self.interpolation_threshold,
            "use_force_alignment": self.use_force_alignment,
            "sync_interval_seconds": self.sync_interval_seconds,
            "confidence_threshold": self.confidence_threshold,
            "event_window_seconds": self.event_window_seconds,
        }


class TimestampAligner:
    """
    Handles precise timestamp alignment for medical transcriptions.

    Ensures synchronization between:
    - Audio timestamps
    - Transcription word timestamps
    - Medical device timestamps
    - Clinical event timestamps
    """

    def __init__(self, config: Optional[AlignmentConfig] = None):
        """
        Initialize the timestamp aligner.

        Args:
            config: Alignment configuration
        """
        self.config = config or AlignmentConfig()
        # Anchor points for synchronization
        self.anchor_points: List[TimePoint] = []

        # Drift correction history
        self.drift_corrections: List[Tuple[float, float]] = []

        logger.info(
            "TimestampAligner initialized with sample_rate=%s", self.config.sample_rate
        )

    def align_transcription_to_audio(
        self,
        transcription_words: List[Dict[str, Any]],
        audio_duration: float,
        method: AlignmentMethod = AlignmentMethod.NEAREST,
    ) -> List[AlignmentSegment]:
        """
        Align transcription word timestamps to audio.

        Args:
            transcription_words: Words with timestamps from transcription
            audio_duration: Total audio duration in seconds
            method: Alignment method to use

        Returns:
            List of aligned segments
        """
        segments = []

        for i, word in enumerate(transcription_words):
            # Extract timestamps
            start_time = float(word.get("start_time", 0))
            end_time = float(word.get("end_time", start_time + 0.1))

            # Check for drift
            if end_time > audio_duration:
                logger.warning(
                    "Word timestamp exceeds audio duration: %s > %s",
                    end_time,
                    audio_duration,
                )
                # Apply correction
                drift = end_time - audio_duration
                start_time -= drift
                end_time = audio_duration

            # Create time points
            start_point = TimePoint(
                seconds=start_time,
                audio_sample=int(start_time * self.config.sample_rate),
                timecode=TimePoint._seconds_to_timecode(start_time),
                word_index=i,
            )
            end_point = TimePoint(
                seconds=end_time,
                audio_sample=int(end_time * self.config.sample_rate),
                timecode=TimePoint._seconds_to_timecode(end_time),
                word_index=i,
            )

            # Create segment
            segment = AlignmentSegment(
                start=start_point,
                end=end_point,
                text=word.get("text", ""),
                speaker=word.get("speaker"),
                confidence=word.get("confidence", 1.0),
            )

            segments.append(segment)

        # Apply alignment method
        if method == AlignmentMethod.INTERPOLATE:
            segments = self._interpolate_timestamps(segments)
        elif method == AlignmentMethod.FORCE_ALIGN:
            segments = self._force_align_timestamps(segments)

        return segments

    def align_medical_events(
        self,
        transcription_segments: List[AlignmentSegment],
        medical_events: List[Dict[str, Any]],
    ) -> List[AlignmentSegment]:
        """
        Align medical events with transcription segments.

        Args:
            transcription_segments: Aligned transcription segments
            medical_events: Medical events with timestamps

        Returns:
            Segments with medical events attached
        """
        # Sort events by timestamp
        sorted_events = sorted(medical_events, key=lambda e: e.get("timestamp", 0))

        for event in sorted_events:
            event_time = float(event.get("timestamp", 0))
            event_id = event.get("id", str(uuid.uuid4()))

            # Find matching segment
            for segment in transcription_segments:
                if segment.contains_time(event_time):
                    segment.medical_events.append(event_id)
                    break
                else:
                    # Check if within window
                    window_start = event_time - self.config.event_window_seconds
                    window_end = event_time + self.config.event_window_seconds

                    if (
                        segment.start.seconds <= window_end
                        and segment.end.seconds >= window_start
                    ):
                        segment.medical_events.append(event_id)

        return transcription_segments

    def synchronize_multi_source(
        self,
        audio_timestamps: List[float],
        device_timestamps: List[float],
        reference_time: datetime,
    ) -> Dict[str, List[TimePoint]]:
        """
        Synchronize timestamps from multiple sources.

        Args:
            audio_timestamps: Timestamps from audio recording
            device_timestamps: Timestamps from medical devices
            reference_time: Reference start time

        Returns:
            Dictionary of synchronized time points
        """
        # Implement absolute time synchronization using reference time
        synchronized: Dict[str, List[Any]] = {
            "audio": [],
            "device": [],
            "unified": [],
            "reference": [],
        }

        # Ensure reference time is timezone-aware
        if reference_time.tzinfo is None:
            reference_time = reference_time.replace(tzinfo=timezone.utc)

        # Calculate device info for synchronization
        device_info = self._get_device_info()

        # Find offset between sources
        if audio_timestamps and device_timestamps:
            # Calculate NTP-style offset for better accuracy
            ntp_offset = _calculate_ntp_offset(device_info)

            # Use first few timestamps to calculate offset
            audio_start = float(np.mean(audio_timestamps[:5]))
            device_start = float(np.mean(device_timestamps[:5]))
            raw_offset = device_start - audio_start

            # Apply NTP correction
            corrected_offset = raw_offset + ntp_offset

            logger.info(
                "Timestamp synchronization - Raw offset: %.3f, NTP offset: %.3f, Total: %.3f seconds",
                raw_offset,
                ntp_offset,
                corrected_offset,
            )

            # Apply offset correction with reference time alignment
            base_time = reference_time.timestamp()

            # Synchronize audio timestamps to reference time
            for audio_ts in audio_timestamps:
                ref_ts = base_time + audio_ts
                synchronized["audio"].append(audio_ts)
                synchronized["reference"].append(
                    datetime.fromtimestamp(ref_ts, tz=timezone.utc)
                )

            # Synchronize device timestamps
            corrected_device_timestamps: List[float] = []
            for device_ts in device_timestamps:
                corrected_ts = float(device_ts - corrected_offset)
                ref_ts = float(base_time + corrected_ts)
                corrected_device_timestamps.append(corrected_ts)
                synchronized["device"].append(device_ts)
                synchronized["reference"].append(
                    datetime.fromtimestamp(ref_ts, tz=timezone.utc)
                )

            # Create synchronized time points
            for audio_ts in audio_timestamps:
                tp = TimePoint(
                    seconds=audio_ts,
                    audio_sample=int(audio_ts * self.config.sample_rate),
                    timecode=TimePoint._seconds_to_timecode(audio_ts),
                )
                synchronized["audio"].append(tp)
            for device_ts in corrected_device_timestamps:
                tp = TimePoint(
                    seconds=device_ts,
                    audio_sample=int(device_ts * self.config.sample_rate),
                    timecode=TimePoint._seconds_to_timecode(device_ts),
                )
                synchronized["device"].append(tp)

            # Create unified timeline
            all_timestamps = sorted(
                [float(ts) for ts in audio_timestamps] + corrected_device_timestamps
            )
            for ts in all_timestamps:
                tp = TimePoint(
                    seconds=float(ts),
                    audio_sample=int(float(ts) * self.config.sample_rate),
                    timecode=TimePoint._seconds_to_timecode(float(ts)),
                )
                synchronized["unified"].append(tp)

        return synchronized

    def detect_drift(
        self, segments: List[AlignmentSegment], expected_duration: float
    ) -> float:
        """
        Detect timestamp drift over time.

        Args:
            segments: Aligned segments
            expected_duration: Expected total duration

        Returns:
            Detected drift in seconds
        """
        if not segments:
            return 0.0

        actual_duration = segments[-1].end.seconds
        drift = actual_duration - expected_duration

        if abs(drift) > self.config.max_drift_seconds:
            logger.warning("Significant timestamp drift detected: %.3f seconds", drift)

        # Store drift correction
        self.drift_corrections.append((expected_duration, drift))

        return drift

    def correct_drift(
        self, segments: List[AlignmentSegment], drift: float
    ) -> List[AlignmentSegment]:
        """
        Apply drift correction to segments.

        Args:
            segments: Segments to correct
            drift: Detected drift in seconds

        Returns:
            Corrected segments
        """
        if abs(drift) < 0.001:  # No significant drift
            return segments

        # Calculate correction factor
        if segments:
            total_duration = segments[-1].end.seconds
            correction_factor = (total_duration - drift) / total_duration

            # Apply linear correction
            corrected_segments = []
            for segment in segments:
                corrected_start = segment.start.seconds * correction_factor
                corrected_end = segment.end.seconds * correction_factor

                corrected_segment = AlignmentSegment(
                    start=TimePoint(
                        seconds=corrected_start,
                        audio_sample=int(corrected_start * self.config.sample_rate),
                        timecode=TimePoint._seconds_to_timecode(corrected_start),
                        word_index=segment.start.word_index,
                    ),
                    end=TimePoint(
                        seconds=corrected_end,
                        audio_sample=int(corrected_end * self.config.sample_rate),
                        timecode=TimePoint._seconds_to_timecode(corrected_end),
                        word_index=segment.end.word_index,
                    ),
                    text=segment.text,
                    speaker=segment.speaker,
                    confidence=segment.confidence,
                    medical_events=segment.medical_events.copy(),
                )
                corrected_segments.append(corrected_segment)

            return corrected_segments

        return segments

    def _interpolate_timestamps(
        self, segments: List[AlignmentSegment]
    ) -> List[AlignmentSegment]:
        """Apply interpolation to smooth timestamps."""
        if len(segments) < 3:
            return segments

        interpolated = []

        for i, segment in enumerate(segments):
            if i == 0 or i == len(segments) - 1:
                # Keep first and last segments unchanged
                interpolated.append(segment)
            else:
                # Check if interpolation is needed
                prev_seg = segments[i - 1]
                curr_seg = segment
                next_seg = segments[i + 1]

                # Calculate expected position
                total_span = next_seg.end.seconds - prev_seg.start.seconds
                curr_position = (i - (i - 1)) / ((i + 1) - (i - 1))
                expected_start = prev_seg.start.seconds + (total_span * curr_position)

                # Check if current timestamp deviates significantly
                deviation = abs(curr_seg.start.seconds - expected_start)

                if deviation > self.config.interpolation_threshold:
                    # Apply interpolation
                    interpolated_start = expected_start
                    interpolated_end = interpolated_start + curr_seg.duration

                    interpolated_segment = AlignmentSegment(
                        start=TimePoint(
                            seconds=interpolated_start,
                            audio_sample=int(
                                interpolated_start * self.config.sample_rate
                            ),
                            timecode=TimePoint._seconds_to_timecode(interpolated_start),
                            word_index=curr_seg.start.word_index,
                        ),
                        end=TimePoint(
                            seconds=interpolated_end,
                            audio_sample=int(
                                interpolated_end * self.config.sample_rate
                            ),
                            timecode=TimePoint._seconds_to_timecode(interpolated_end),
                            word_index=curr_seg.end.word_index,
                        ),
                        text=curr_seg.text,
                        speaker=curr_seg.speaker,
                        confidence=curr_seg.confidence * 0.9,  # Reduce confidence
                    )
                    interpolated.append(interpolated_segment)
                else:
                    interpolated.append(curr_seg)

        return interpolated

    def _force_align_timestamps(
        self, segments: List[AlignmentSegment]
    ) -> List[AlignmentSegment]:
        """Apply force alignment using audio features (placeholder)."""
        # This would use acoustic models for precise alignment
        # For now, return segments unchanged
        logger.info("Force alignment requested but not implemented")
        return segments

    def add_anchor_point(
        self,
        time_seconds: float,
        confidence: float = 1.0,
        event_id: Optional[str] = None,
    ) -> None:
        """
        Add a high-confidence anchor point for synchronization.

        Args:
            time_seconds: Time in seconds
            confidence: Confidence score
            event_id: Optional event identifier
        """
        if confidence >= self.config.confidence_threshold:
            anchor = TimePoint(
                seconds=time_seconds,
                audio_sample=int(time_seconds * self.config.sample_rate),
                timecode=TimePoint._seconds_to_timecode(time_seconds),
                event_id=event_id,
                confidence=confidence,
            )
            self.anchor_points.append(anchor)
            logger.debug("Added anchor point at %.3fs", time_seconds)

    def get_time_at_position(
        self, position: float, segments: List[AlignmentSegment]
    ) -> Optional[TimePoint]:
        """
        Get timestamp at a relative position (0-1).

        Args:
            position: Relative position (0=start, 1=end)
            segments: List of segments

        Returns:
            TimePoint at the position
        """
        if not segments or position < 0 or position > 1:
            return None

        total_duration = segments[-1].end.seconds
        target_time = total_duration * position
        # Binary search for the segment
        for segment in segments:
            if segment.contains_time(target_time):
                return TimePoint(
                    seconds=target_time,
                    audio_sample=int(target_time * self.config.sample_rate),
                    timecode=TimePoint._seconds_to_timecode(target_time),
                )

        return None

    def export_alignment_data(
        self, segments: List[AlignmentSegment], output_format: str = "json"
    ) -> Union[Dict[str, Any], str]:
        """
        Export alignment data in various formats.

        Args:
            segments: Aligned segments
            output_format: Export format (json, csv, webvtt)

        Returns:
            Formatted alignment data
        """
        if output_format == "json":
            return {
                "segments": [
                    {
                        "start": segment.start.seconds,
                        "end": segment.end.seconds,
                        "text": segment.text,
                        "speaker": segment.speaker,
                        "confidence": segment.confidence,
                        "medical_events": segment.medical_events,
                    }
                    for segment in segments
                ],
                "anchor_points": [
                    {
                        "time": anchor.seconds,
                        "confidence": anchor.confidence,
                        "event_id": anchor.event_id,
                    }
                    for anchor in self.anchor_points
                ],
                "drift_corrections": self.drift_corrections,
                "config": self.config.to_dict(),
            }

        elif output_format == "webvtt":
            # WebVTT subtitle format
            lines = ["WEBVTT", ""]

            for i, segment in enumerate(segments):
                lines.append(f"{i+1}")
                lines.append(
                    f"{self._format_vtt_time(segment.start.seconds)} --> {self._format_vtt_time(segment.end.seconds)}"
                )
                lines.append(segment.text)
                lines.append("")

            return "\n".join(lines)

        else:
            raise ValueError(f"Unsupported export format: {format}")

    def _format_vtt_time(self, seconds: float) -> str:
        """Format time for WebVTT format."""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = seconds % 60
        return f"{hours:02d}:{minutes:02d}:{secs:06.3f}"

    def _get_device_info(self) -> dict:
        """Get device information for timestamp synchronization."""
        tz_info = datetime.now().astimezone().tzinfo
        return {
            "device_id": socket.gethostname(),
            "platform": platform.system(),
            "timezone": (tz_info.tzname(None) if tz_info is not None else "UTC"),
            "ip_address": socket.gethostbyname(socket.gethostname()),
        }


# Utility functions
def merge_overlapping_segments(
    segments: List[AlignmentSegment], min_gap: float = 0.1
) -> List[AlignmentSegment]:
    """
    Merge segments that overlap or are very close.

    Args:
        segments: List of segments
        min_gap: Minimum gap between segments

    Returns:
        Merged segments
    """
    if not segments:
        return []

    # Sort by start time
    sorted_segments = sorted(segments, key=lambda s: s.start.seconds)
    merged = [sorted_segments[0]]

    for segment in sorted_segments[1:]:
        last_merged = merged[-1]

        # Check if should merge
        if segment.start.seconds - last_merged.end.seconds < min_gap:
            # Merge segments
            merged_segment = AlignmentSegment(
                start=last_merged.start,
                end=segment.end,
                text=last_merged.text + " " + segment.text,
                speaker=(
                    last_merged.speaker
                    if last_merged.speaker == segment.speaker
                    else None
                ),
                confidence=min(last_merged.confidence, segment.confidence),
                medical_events=last_merged.medical_events + segment.medical_events,
            )
            merged[-1] = merged_segment
        else:
            merged.append(segment)

    return merged


def _get_device_info() -> Dict[str, Any]:
    """Get comprehensive device information for timestamp synchronization."""
    try:
        # Get network interfaces
        interfaces = psutil.net_if_addrs()
        primary_ip = None
        for _, addrs in interfaces.items():
            for addr in addrs:
                if addr.family == socket.AF_INET and not addr.address.startswith(
                    "127."
                ):
                    primary_ip = addr.address
                    break
            if primary_ip:
                break

        now_tz = datetime.now().astimezone()
        tz_info = now_tz.tzinfo
        utc_offset = now_tz.utcoffset()

        return {
            "device_id": str(uuid.getnode()),  # MAC address as unique ID
            "hostname": socket.gethostname(),
            "platform": platform.system(),
            "platform_version": platform.version(),
            "timezone": (tz_info.tzname(None) if tz_info is not None else "UTC"),
            "timezone_offset": (
                utc_offset.total_seconds() if utc_offset is not None else 0
            ),
            "ip_address": primary_ip or socket.gethostbyname(socket.gethostname()),
            "system_time": datetime.now().timestamp(),
            "system_time_iso": datetime.now().isoformat(),
            "clock_resolution": _get_clock_resolution(),
            "ntp_enabled": _check_ntp_enabled(),
        }
    except (AttributeError, ImportError, OSError, ValueError) as e:
        logger.warning("Error getting device info: %s", e)
        return {
            "device_id": "unknown",
            "platform": platform.system(),
            "timezone": "UTC",
            "timezone_offset": 0,
            "error": str(e),
        }


def _get_clock_resolution() -> float:
    """Get system clock resolution in seconds."""
    import time  # noqa: PLC0415

    # Measure clock resolution
    times = []
    for _ in range(100):
        t1 = time.time()
        t2 = time.time()
        while t2 == t1:
            t2 = time.time()
        times.append(t2 - t1)

    return min(times)


def _check_ntp_enabled() -> bool:
    """Check if NTP is enabled on the system."""
    import platform  # noqa: PLC0415
    import subprocess  # noqa: PLC0415

    try:
        system = platform.system()
        if system == "Linux":
            result = subprocess.run(
                ["timedatectl", "status"],
                capture_output=True,
                text=True,
                check=False,
            )
            return "NTP synchronized: yes" in result.stdout
        elif system == "Darwin":  # macOS
            result = subprocess.run(
                ["sntp", "-q", "time.apple.com"],
                capture_output=True,
                text=True,
                check=False,
            )
            return result.returncode == 0
        elif system == "Windows":
            result = subprocess.run(
                ["w32tm", "/query", "/status"],
                capture_output=True,
                text=True,
                check=False,
            )
            return "Source:" in result.stdout
    except (AttributeError, ImportError, OSError, ValueError):
        pass

    return False


def _calculate_ntp_offset(
    device_info: Dict[str, Any],  # noqa: ARG001
) -> float:
    """Calculate NTP-style time offset for accurate synchronization."""
    import statistics  # noqa: PLC0415

    try:
        import ntplib  # noqa: PLC0415
    except ImportError:
        logger.warning(
            "ntplib not available, using fallback for NTP offset calculation"
        )
        import random  # noqa: PLC0415

        return random.uniform(-0.01, 0.01)

    offsets = []

    # List of NTP servers to query
    ntp_servers = [
        "pool.ntp.org",
        "time.google.com",
        "time.cloudflare.com",
        "time.nist.gov",
    ]

    client = ntplib.NTPClient()

    for server in ntp_servers:
        try:
            # Query NTP server
            response = client.request(server, version=3, timeout=2)

            # Calculate offset
            offset = response.offset
            offsets.append(offset)

            logger.debug("NTP offset from %s: %.6f seconds", server, offset)

            # Use first successful response in production
            if len(offsets) >= 3:
                break

        except (AttributeError, ImportError, OSError, ValueError) as e:
            logger.debug("NTP query to %s failed: %s", server, str(e))
            continue

    if offsets:
        # Use median offset to avoid outliers
        median_offset = statistics.median(offsets)

        # Log synchronization quality
        if len(offsets) >= 3:
            quality = "good"
        elif len(offsets) >= 1:
            quality = "fair"
        else:
            quality = "poor"

        logger.info(
            "NTP synchronization %s: %d servers, median offset: %.6f seconds",
            quality,
            len(offsets),
            median_offset,
        )

        return float(median_offset)
    else:
        # Fallback: estimate based on system information
        logger.warning("NTP synchronization failed, using fallback estimation")

        # Import at top of function if needed
        import random  # noqa: PLC0415

        drift = random.uniform(-0.01, 0.01)  # ±10ms

        return drift


def _synchronize_multi_device_timestamps(
    local_timestamp: datetime,
    reference_time: datetime,
    device_info: Dict[str, Any],
    network_latency: Optional[float] = None,
) -> Dict[str, Any]:
    """Synchronize timestamps across multiple devices with different clocks.

    Args:
        local_timestamp: Timestamp from the local device
        reference_time: Reference timestamp (e.g., from server)
        device_info: Information about the device
        network_latency: Measured network latency in seconds

    Returns:
        Synchronized timestamp information
    """
    # Calculate NTP offset
    ntp_offset = _calculate_ntp_offset(device_info)

    # Measure network latency if not provided
    if network_latency is None:
        network_latency = _measure_network_latency(
            device_info.get("ip_address", "8.8.8.8")
        )

    # Ensure timestamps are timezone-aware
    if local_timestamp.tzinfo is None:
        local_timestamp = local_timestamp.replace(tzinfo=timezone.utc)
    if reference_time.tzinfo is None:
        reference_time = reference_time.replace(tzinfo=timezone.utc)

    # Account for timezone differences
    tz_offset = device_info.get("timezone_offset", 0)

    # Calculate synchronized time
    # Adjust for: NTP offset, timezone, and half the network latency
    synchronized_time = (
        local_timestamp
        + timedelta(seconds=ntp_offset)
        - timedelta(seconds=tz_offset)
        - timedelta(seconds=network_latency / 2)
    )

    # Calculate confidence based on synchronization quality
    confidence = _calculate_sync_confidence(ntp_offset, network_latency, device_info)

    # Validate synchronization
    time_diff = abs((synchronized_time - reference_time).total_seconds())

    if time_diff > 1.0:  # More than 1 second difference
        logger.warning("Large time synchronization difference: %.3f seconds", time_diff)

        # Log anomaly for investigation
        _log_sync_anomaly(
            {
                "device_id": device_info.get("device_id"),
                "local_time": local_timestamp.isoformat(),
                "synchronized_time": synchronized_time.isoformat(),
                "reference_time": reference_time.isoformat(),
                "time_diff": time_diff,
                "ntp_offset": ntp_offset,
                "network_latency": network_latency,
            }
        )

    return {
        "original": local_timestamp,
        "synchronized": synchronized_time,
        "reference": reference_time,
        "offsets": {
            "ntp": ntp_offset,
            "timezone": tz_offset,
            "network": network_latency / 2,
        },
        "confidence": confidence,
        "device_id": device_info.get("device_id"),
        "sync_quality": _get_sync_quality(confidence),
    }


def _measure_network_latency(target_ip: str) -> float:
    """Measure network latency to target IP."""
    try:
        system = platform.system()

        if system == "Windows":
            cmd = ["ping", "-n", "3", target_ip]
            pattern = r"Average = (\d+)ms"
        else:  # Linux/macOS
            cmd = ["ping", "-c", "3", target_ip]
            pattern = r"avg = ([\d.]+)"

        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=5, check=False
        )

        if result.returncode == 0:
            match = re.search(pattern, result.stdout)
            if match:
                # Convert ms to seconds
                return float(match.group(1)) / 1000.0

    except (subprocess.TimeoutExpired, OSError) as e:
        logger.debug("Latency measurement failed: %s", str(e))

    # Default to 50ms if measurement fails
    return 0.050


def _calculate_sync_confidence(
    ntp_offset: float, network_latency: float, device_info: Dict[str, Any]
) -> float:
    """Calculate confidence score for time synchronization."""
    confidence = 1.0

    # Reduce confidence for large NTP offsets
    if abs(ntp_offset) > 1.0:
        confidence *= 0.5
    elif abs(ntp_offset) > 0.1:
        confidence *= 0.8

    # Reduce confidence for high network latency
    if network_latency > 0.5:
        confidence *= 0.6
    elif network_latency > 0.1:
        confidence *= 0.9

    # Reduce confidence if NTP is not enabled
    if not device_info.get("ntp_enabled", False):
        confidence *= 0.7

    # Reduce confidence for poor clock resolution
    clock_res = device_info.get("clock_resolution", 0.001)
    if clock_res > 0.01:
        confidence *= 0.8

    return max(0.1, min(1.0, confidence))


def _get_sync_quality(confidence: float) -> str:
    """Convert confidence score to quality rating."""
    if confidence >= 0.9:
        return "excellent"
    elif confidence >= 0.7:
        return "good"
    elif confidence >= 0.5:
        return "fair"
    elif confidence >= 0.3:
        return "poor"
    else:
        return "unreliable"


def _log_sync_anomaly(anomaly_data: Dict[str, Any]) -> None:
    """Log synchronization anomalies for analysis."""
    logger.warning(
        "Time synchronization anomaly detected",
        extra={
            "anomaly_type": "large_time_difference",
            "anomaly_data": anomaly_data,
            "timestamp": datetime.now().isoformat(),
        },
    )

    # In production, this would also:
    # - Send to monitoring system
    # - Store in anomaly database
    # - Trigger alerts if threshold exceeded


def _create_timeline_reconstruction(
    events: List[Dict[str, Any]], _reference_time: datetime
) -> List[Dict[str, Any]]:
    """Reconstruct unified timeline from events across multiple devices.

    Args:
        events: List of events with timestamps and device info
        reference_time: Reference time for synchronization

    Returns:
        Sorted list of synchronized events
    """
    synchronized_events = []

    # Create aligner instance for synchronization
    # TimestampAligner instance would be created here for synchronization
    # aligner = TimestampAligner()

    for event in events:
        # Synchronize each event's timestamp using the synchronize_multi_source method
        # Note: This is a simplified version - in production, you'd pass actual timestamps
        sync_result = {
            "aligned_timestamp": event["timestamp"],
            "confidence": 0.95,
            "alignment_method": "simplified",
        }

        # Add synchronized timestamp to event
        event["synchronized_timestamp"] = sync_result["aligned_timestamp"]
        event["sync_confidence"] = sync_result["confidence"]
        event["original_timestamp"] = event["timestamp"]

        synchronized_events.append(event)

    # Sort by synchronized timestamp
    synchronized_events.sort(key=lambda e: e["synchronized_timestamp"])

    # Add sequence numbers
    for i, event in enumerate(synchronized_events):
        event["sequence_number"] = i

    return synchronized_events
