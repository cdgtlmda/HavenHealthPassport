"""
Channel Processing Module for Multi-Channel Audio.

This module provides audio channel processing capabilities including
separation, analysis, and enhancement for medical transcription.

Security Note: This module processes multi-channel audio that may contain PHI.
All audio data must be encrypted at rest and in transit. Access to channel
processing functionality should be restricted to authorized healthcare personnel
only through role-based access controls.
"""

import asyncio
import json
import logging
import threading
import wave
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, AsyncIterator, Dict, List, Optional, Tuple, Union

import numpy as np

from .channel_config import (
    ChannelConfig,
    ChannelIdentificationConfig,
    ChannelMapping,
)

logger = logging.getLogger(__name__)


class ChannelStatus(Enum):
    """Status of audio channel processing."""

    IDLE = "idle"
    ACTIVE = "active"
    PROCESSING = "processing"
    MUTED = "muted"
    ERROR = "error"


@dataclass
class ChannelMetadata:
    """Metadata for an audio channel."""

    channel_id: int
    status: ChannelStatus = ChannelStatus.IDLE
    duration: float = 0.0  # seconds
    sample_count: int = 0
    peak_amplitude: float = 0.0
    rms_level: float = 0.0
    silence_ratio: float = 0.0
    activity_periods: List[Tuple[float, float]] = field(default_factory=list)
    quality_score: float = 0.0
    detected_language: Optional[str] = None
    cross_talk_events: int = 0
    noise_level: float = 0.0
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "channel_id": self.channel_id,
            "status": self.status.value,
            "duration": self.duration,
            "sample_count": self.sample_count,
            "peak_amplitude": self.peak_amplitude,
            "rms_level": self.rms_level,
            "silence_ratio": self.silence_ratio,
            "activity_periods": self.activity_periods,
            "quality_score": self.quality_score,
            "detected_language": self.detected_language,
            "cross_talk_events": self.cross_talk_events,
            "noise_level": self.noise_level,
            "timestamp": self.timestamp.isoformat(),
        }


class ChannelAnalyzer:
    """Analyzes audio channels for quality and characteristics."""

    def __init__(self, config: ChannelConfig):
        """Initialize channel analyzer."""
        self.config = config
        self.metadata = ChannelMetadata(channel_id=config.channel_id)
        self._buffer: List[np.ndarray] = []
        self._lock = threading.Lock()

    def analyze_samples(self, samples: np.ndarray) -> ChannelMetadata:
        """
        Analyze audio samples and update channel metadata.

        Args:
            samples: Audio samples as numpy array

        Returns:
            Updated channel metadata
        """
        with self._lock:
            # Update sample count and duration
            self.metadata.sample_count += len(samples)
            self.metadata.duration = (
                self.metadata.sample_count / self.config.sample_rate
            )

            # Calculate audio metrics
            if len(samples) > 0:
                # Peak amplitude
                self.metadata.peak_amplitude = float(np.max(np.abs(samples)))

                # RMS level
                self.metadata.rms_level = float(np.sqrt(np.mean(samples**2)))

                # Silence detection
                silence_threshold = 10 ** (self.config.silence_threshold / 20)
                silent_samples = np.sum(np.abs(samples) < silence_threshold)
                self.metadata.silence_ratio = silent_samples / len(samples)

                # Voice activity detection
                if self.config.voice_activity_detection:
                    self._detect_voice_activity(samples)

                # Quality assessment
                self._assess_quality(samples)

            self.metadata.timestamp = datetime.utcnow()

        return self.metadata

    def _detect_voice_activity(self, samples: np.ndarray) -> None:
        """Detect voice activity in audio samples."""
        # Simple energy-based VAD
        energy = np.sum(samples**2) / len(samples)
        voice_threshold = 10 ** (self.config.silence_threshold / 10)

        if energy > voice_threshold:
            # Update metadata to indicate voice activity
            self.metadata.status = ChannelStatus.ACTIVE

    def _assess_quality(self, samples: np.ndarray) -> None:
        """Assess audio quality based on various metrics."""
        # Simple quality assessment based on SNR and clipping
        if len(samples) > 0:
            # Check for clipping
            clipping_ratio = np.sum(np.abs(samples) > 0.95) / len(samples)

            # Estimate SNR (simplified)
            signal_power = np.mean(samples**2)
            noise_floor = np.percentile(np.abs(samples), 10) ** 2

            if noise_floor > 0:
                snr_db = 10 * np.log10(signal_power / noise_floor)
            else:
                snr_db = 40  # Good quality default

            # Calculate quality score (0-1)
            quality_factors = []

            # SNR factor
            quality_factors.append(min(1.0, max(0.0, snr_db / 40)))

            # Clipping factor
            quality_factors.append(1.0 - clipping_ratio * 10)

            # Activity factor
            quality_factors.append(1.0 - self.metadata.silence_ratio)

            # RMS level factor (not too quiet, not too loud)
            ideal_rms = 0.1
            rms_factor = 1.0 - abs(self.metadata.rms_level - ideal_rms) / ideal_rms
            quality_factors.append(max(0.0, rms_factor))

            # Average quality score
            self.metadata.quality_score = sum(quality_factors) / len(quality_factors)

            # Update noise level
            self.metadata.noise_level = float(np.sqrt(noise_floor))

    def reset(self) -> None:
        """Reset analyzer state."""
        with self._lock:
            self.metadata = ChannelMetadata(channel_id=self.config.channel_id)
            self._buffer.clear()


class ChannelSeparator:
    """Separates multi-channel audio into individual channels."""

    def __init__(self, config: ChannelIdentificationConfig):
        """Initialize channel separator."""
        self.config = config
        self._analyzers = {}
        # Create analyzers for each configured channel
        for channel_id in range(config.max_channels):
            channel_config = config.get_channel_config(channel_id)
            if channel_config and channel_config.enabled:
                self._analyzers[channel_id] = ChannelAnalyzer(channel_config)

    def separate_channels(
        self, audio_data: np.ndarray, num_channels: Optional[int] = None
    ) -> Dict[int, np.ndarray]:
        """
        Separate multi-channel audio data.

        Args:
            audio_data: Multi-channel audio data
            num_channels: Number of channels (auto-detect if None)

        Returns:
            Dictionary mapping channel IDs to audio data
        """
        if num_channels is None:
            # Auto-detect number of channels
            if len(audio_data.shape) == 1:
                num_channels = 1
            else:
                num_channels = audio_data.shape[1]

        separated_channels = {}

        if num_channels == 1:
            # Mono audio
            separated_channels[0] = audio_data
        else:
            # Multi-channel audio
            for i in range(min(num_channels, self.config.max_channels)):
                if len(audio_data.shape) == 1:
                    # Already separated
                    separated_channels[i] = audio_data
                else:
                    # Extract channel
                    separated_channels[i] = audio_data[:, i]

        return separated_channels

    def process_audio_file(
        self, file_path: Union[str, Path]
    ) -> Dict[int, Tuple[np.ndarray, ChannelMetadata]]:
        """
        Process audio file and separate channels.

        Args:
            file_path: Path to audio file

        Returns:
            Dictionary mapping channel IDs to (audio_data, metadata) tuples
        """
        file_path = Path(file_path)

        try:
            # Read audio file
            with wave.open(str(file_path), "rb") as wav_file:
                num_channels = wav_file.getnchannels()
                num_frames = wav_file.getnframes()

                # Read all frames
                frames = wav_file.readframes(num_frames)

                # Convert to numpy array
                if wav_file.getsampwidth() == 2:
                    audio_data = np.frombuffer(frames, dtype=np.int16)
                elif wav_file.getsampwidth() == 4:
                    audio_data = np.frombuffer(frames, dtype=np.int32)
                else:
                    raise ValueError(
                        f"Unsupported sample width: {wav_file.getsampwidth()}"
                    )

                # Normalize to float32 [-1, 1]
                normalized_audio = (
                    audio_data.astype(np.float32) / np.iinfo(audio_data.dtype).max
                )

                # Reshape for multi-channel
                if num_channels > 1:
                    normalized_audio = normalized_audio.reshape(-1, num_channels)

                # Separate channels
                separated = self.separate_channels(normalized_audio, num_channels)

                # Process each channel
                results = {}
                for channel_id, channel_data in separated.items():
                    if channel_id in self._analyzers:
                        metadata = self._analyzers[channel_id].analyze_samples(
                            channel_data
                        )
                        results[channel_id] = (channel_data, metadata)
                    else:
                        # Create default metadata for unconfigured channels
                        metadata = ChannelMetadata(channel_id=channel_id)
                        results[channel_id] = (channel_data, metadata)

                return results

        except Exception as e:
            logger.error("Error processing audio file %s: %s", file_path, e)
            raise

    def detect_cross_talk(
        self, channels: Dict[int, np.ndarray], threshold: Optional[float] = None
    ) -> List[Tuple[int, int, float]]:
        """
        Detect cross-talk between channels.

        Args:
            channels: Dictionary of channel audio data
            threshold: Cross-talk detection threshold

        Returns:
            List of (channel1, channel2, correlation) tuples
        """
        if threshold is None:
            threshold = self.config.cross_talk_threshold

        cross_talk_events = []

        # Compare all channel pairs
        channel_ids = list(channels.keys())
        for i, _ in enumerate(channel_ids):
            for j in range(i + 1, len(channel_ids)):
                ch1_id, ch2_id = channel_ids[i], channel_ids[j]
                ch1_data, ch2_data = channels[ch1_id], channels[ch2_id]

                # Ensure same length
                min_len = min(len(ch1_data), len(ch2_data))
                if min_len > 0:
                    # Calculate correlation
                    correlation = np.corrcoef(ch1_data[:min_len], ch2_data[:min_len])[
                        0, 1
                    ]

                    if abs(correlation) > threshold:
                        cross_talk_events.append((ch1_id, ch2_id, float(correlation)))

                        # Update metadata
                        if ch1_id in self._analyzers:
                            self._analyzers[ch1_id].metadata.cross_talk_events += 1
                        if ch2_id in self._analyzers:
                            self._analyzers[ch2_id].metadata.cross_talk_events += 1

        return cross_talk_events

    def get_channel_metadata(self, channel_id: int) -> Optional[ChannelMetadata]:
        """Get metadata for specific channel."""
        if channel_id in self._analyzers:
            return self._analyzers[channel_id].metadata
        return None

    def get_all_metadata(self) -> Dict[int, ChannelMetadata]:
        """Get metadata for all channels."""
        return {
            channel_id: analyzer.metadata
            for channel_id, analyzer in self._analyzers.items()
        }


class ChannelProcessor:
    """
    Main processor for channel identification and processing.

    This class coordinates channel separation, analysis, and enhancement
    for multi-channel medical audio transcription.
    """

    def __init__(self, config: ChannelIdentificationConfig):
        """Initialize channel processor."""
        self.config = config
        self.separator = ChannelSeparator(config)
        self._processed_files: Dict[
            str, Dict[int, Tuple[np.ndarray, ChannelMetadata]]
        ] = {}
        self._processing_lock = threading.Lock()

    async def process_audio_stream(
        self,
        audio_stream: asyncio.StreamReader,
        sample_rate: int = 16000,  # pylint: disable=unused-argument
        channels: int = 2,
    ) -> AsyncIterator[Dict[int, Tuple[np.ndarray, ChannelMetadata]]]:
        """
        Process audio stream in real-time.

        Args:
            audio_stream: Async audio stream
            sample_rate: Sample rate in Hz
            channels: Number of channels

        Yields:
            Channel data and metadata for each buffer
        """
        buffer_size = self.config.buffer_size * channels * 2  # 16-bit samples

        while True:
            try:
                # Read buffer from stream
                data = await audio_stream.read(buffer_size)
                if not data:
                    break

                # Convert to numpy array
                audio_data = (
                    np.frombuffer(data, dtype=np.int16).astype(np.float32) / 32768.0
                )

                if channels > 1:
                    audio_data = audio_data.reshape(-1, channels)

                # Separate and analyze channels
                separated = self.separator.separate_channels(audio_data, channels)

                # Process each channel
                results = {}
                for channel_id, channel_data in separated.items():
                    # Get analyzer without accessing protected member
                    analyzer = getattr(self.separator, "_analyzers", {}).get(channel_id)
                    if analyzer:
                        metadata = analyzer.analyze_samples(channel_data)
                        results[channel_id] = (channel_data, metadata)

                # Detect cross-talk if enabled
                if self.config.enable_cross_talk_detection:
                    self.separator.detect_cross_talk(separated)

                yield results

            except Exception as e:  # pylint: disable=broad-exception-caught
                # Catch all exceptions to ensure stream processing continues gracefully
                logger.error("Error processing audio stream: %s", e)
                break

    def process_file(
        self, file_path: Union[str, Path], cache_results: bool = True
    ) -> Dict[int, Tuple[np.ndarray, ChannelMetadata]]:
        """
        Process audio file with channel separation.

        Args:
            file_path: Path to audio file
            cache_results: Whether to cache processing results

        Returns:
            Dictionary mapping channel IDs to (audio_data, metadata) tuples
        """
        file_path = str(Path(file_path).absolute())

        # Check cache
        if cache_results and file_path in self._processed_files:
            logger.info("Using cached results for %s", file_path)
            return self._processed_files[file_path]

        with self._processing_lock:
            # Process file
            results = self.separator.process_audio_file(file_path)

            # Apply channel-specific processing
            processed_results = {}
            for channel_id, (audio_data, metadata) in results.items():
                # Get channel config and mapping
                channel_config = self.config.get_channel_config(channel_id)
                channel_mapping = self.config.get_channel_mapping(channel_id)

                if channel_config and channel_config.enabled:
                    # Apply preprocessing
                    processed_audio = self._apply_preprocessing(
                        audio_data, channel_config, channel_mapping
                    )
                    processed_results[channel_id] = (processed_audio, metadata)

            # Cache results if requested
            if cache_results:
                self._processed_files[file_path] = processed_results

            return processed_results

    def _apply_preprocessing(
        self,
        audio_data: np.ndarray,
        config: ChannelConfig,
        mapping: Optional[ChannelMapping] = None,
    ) -> np.ndarray:
        """Apply preprocessing to channel audio."""
        processed = audio_data.copy()

        # Apply gain adjustment from mapping
        if mapping and mapping.gain_adjustment != 1.0:
            processed *= mapping.gain_adjustment

        # Apply automatic gain control
        if config.automatic_gain_control:
            # Simple AGC implementation
            target_level = 0.1
            current_level = np.sqrt(np.mean(processed**2))
            if current_level > 0:
                gain = target_level / current_level
                gain = np.clip(gain, 0.1, 10.0)  # Limit gain range
                processed *= gain

        # Apply noise reduction if configured
        if mapping and mapping.noise_reduction:
            # Simple spectral subtraction (placeholder)
            # In production, use more sophisticated noise reduction
            pass

        # Apply echo cancellation if configured
        if config.echo_cancellation:
            # Placeholder for echo cancellation
            # In production, use acoustic echo cancellation algorithms
            pass

        # Apply preprocessing filters
        for filter_name in config.preprocessing_filters:
            if filter_name == "bandpass":
                # Simple bandpass filter for voice frequencies
                # In production, use scipy.signal filters
                pass
            elif filter_name == "compressor":
                # Dynamic range compression
                threshold = 0.7
                ratio = 4.0
                mask = np.abs(processed) > threshold
                processed[mask] = np.sign(processed[mask]) * (
                    threshold + (np.abs(processed[mask]) - threshold) / ratio
                )

        return processed

    def _preprocess_channel_audio(
        self,
        audio_data: np.ndarray,
        mapping: Optional[ChannelMapping],
        config: ChannelConfig,
    ) -> np.ndarray:
        """Apply preprocessing to channel audio."""
        processed = audio_data.copy()

        # Apply gain adjustment from mapping
        if mapping and mapping.gain_adjustment != 1.0:
            processed *= mapping.gain_adjustment

        # Apply automatic gain control
        if config.automatic_gain_control:
            # Simple AGC implementation
            target_level = 0.1
            current_level = np.sqrt(np.mean(processed**2))
            if current_level > 0:
                gain = target_level / current_level
                gain = np.clip(gain, 0.1, 10.0)  # Limit gain range
                processed *= gain

        # Apply noise reduction if configured
        if mapping and mapping.noise_reduction:
            # Simple spectral subtraction (placeholder)
            # In production, use more sophisticated noise reduction
            pass

        # Apply echo cancellation if configured
        if config.echo_cancellation:
            # Placeholder for echo cancellation
            # In production, use acoustic echo cancellation algorithms
            pass

        # Apply preprocessing filters
        for filter_name in config.preprocessing_filters:
            if filter_name == "bandpass":
                # Simple bandpass filter for voice frequencies
                # In production, use scipy.signal filters
                pass
            elif filter_name == "compressor":
                # Dynamic range compression
                threshold = 0.7
                ratio = 4.0
                mask = np.abs(processed) > threshold
                processed[mask] = np.sign(processed[mask]) * (
                    threshold + (np.abs(processed[mask]) - threshold) / ratio
                )

        return processed

    def export_channels(
        self,
        results: Dict[int, Tuple[np.ndarray, ChannelMetadata]],
        output_dir: Union[str, Path],
        export_format: str = "wav",
    ) -> Dict[int, Path]:
        """
        Export processed channels to individual files.

        Args:
            results: Channel processing results
            output_dir: Output directory
            export_format: Audio format (wav, mp3, etc.)

        Returns:
            Dictionary mapping channel IDs to output file paths
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        output_files = {}

        for channel_id, (audio_data, _metadata) in results.items():
            # Get channel info
            mapping = self.config.get_channel_mapping(channel_id)

            # Generate filename
            if mapping and mapping.speaker_name:
                filename = f"channel_{channel_id}_{mapping.role.value}_{mapping.speaker_name}.{export_format}"
            elif mapping:
                filename = f"channel_{channel_id}_{mapping.role.value}.{export_format}"
            else:
                filename = f"channel_{channel_id}.{export_format}"

            output_path = output_dir / filename

            # Export audio (WAV only for now)
            if export_format == "wav":
                # Convert float32 to int16
                audio_int16 = (audio_data * 32767).astype(np.int16)

                # Get sample rate from config
                channel_config = self.config.get_channel_config(channel_id)
                sample_rate = channel_config.sample_rate if channel_config else 16000

                # Write WAV file
                with wave.open(str(output_path), "w") as wav_file:
                    # pylint: disable=no-member
                    # Wave_write object has these methods
                    wav_file.setnchannels(1)
                    wav_file.setsampwidth(2)  # 16-bit
                    wav_file.setframerate(sample_rate)
                    wav_file.writeframes(audio_int16.tobytes())
                    # pylint: enable=no-member

                output_files[channel_id] = output_path
                logger.info("Exported channel %s to %s", channel_id, output_path)
            else:
                logger.warning("Format %s not yet supported", export_format)

        # Export metadata
        metadata_path = output_dir / "channel_metadata.json"
        metadata_dict = {
            str(ch_id): metadata.to_dict() for ch_id, (_, metadata) in results.items()
        }

        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(metadata_dict, f, indent=2)

        return output_files

    def get_channel_summary(
        self, results: Dict[int, Tuple[np.ndarray, ChannelMetadata]]
    ) -> Dict[str, Any]:
        """
        Generate summary report of channel processing.

        Args:
            results: Channel processing results

        Returns:
            Summary dictionary with statistics and quality metrics
        """
        summary = {
            "total_channels": len(results),
            "active_channels": 0,
            "total_duration": 0.0,
            "average_quality": 0.0,
            "cross_talk_detected": False,
            "channels": [],
        }

        quality_scores = []

        for channel_id, (_, metadata) in results.items():
            mapping = self.config.get_channel_mapping(channel_id)

            channel_info = {
                "channel_id": channel_id,
                "role": mapping.role.value if mapping else "unknown",
                "speaker": mapping.speaker_name if mapping else None,
                "duration": metadata.duration,
                "quality_score": metadata.quality_score,
                "activity_ratio": 1.0 - metadata.silence_ratio,
                "cross_talk_events": metadata.cross_talk_events,
            }

            summary["channels"].append(channel_info)  # type: ignore

            # Update summary stats
            if metadata.status == ChannelStatus.ACTIVE:
                summary["active_channels"] += 1  # type: ignore

            summary["total_duration"] = max(  # type: ignore
                summary["total_duration"], metadata.duration
            )
            quality_scores.append(metadata.quality_score)

            if metadata.cross_talk_events > 0:
                summary["cross_talk_detected"] = True

        # Calculate average quality
        if quality_scores:
            summary["average_quality"] = sum(quality_scores) / len(quality_scores)

        return summary
