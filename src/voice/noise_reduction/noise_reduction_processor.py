"""Noise Reduction Processor Module.

This module implements the main noise reduction functionality
for medical audio recordings.

Security Note: This module processes audio that may contain PHI data.
All audio data must be encrypted at rest and in transit. Access to
audio processing functionality should be restricted to authorized
healthcare personnel only through role-based access controls.
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

from .noise_detector import NoiseDetectionResult, NoiseDetector
from .noise_profile import NoiseLevel

logger = logging.getLogger(__name__)


class NoiseReductionMethod(Enum):
    """Available noise reduction methods."""

    SPECTRAL_SUBTRACTION = "spectral_subtraction"
    WIENER_FILTER = "wiener_filter"
    WAVELET_DENOISING = "wavelet_denoising"
    ADAPTIVE_FILTER = "adaptive_filter"
    DEEP_LEARNING = "deep_learning"
    MULTI_BAND = "multi_band"


@dataclass
class NoiseReductionConfig:
    """Configuration for noise reduction processing."""

    method: NoiseReductionMethod = NoiseReductionMethod.SPECTRAL_SUBTRACTION
    aggressiveness: float = 1.0  # 0.0 (gentle) to 2.0 (aggressive)
    preserve_voice: bool = True
    frequency_smoothing: bool = True
    temporal_smoothing: bool = True

    # Method-specific parameters
    spectral_floor: float = 0.1
    wiener_noise_power: float = 0.01
    wavelet_level: int = 4
    adaptive_filter_order: int = 32
    # Voice preservation parameters
    voice_freq_min: float = 80.0  # Hz
    voice_freq_max: float = 4000.0  # Hz
    formant_protection: bool = True

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "method": self.method.value,
            "aggressiveness": self.aggressiveness,
            "preserve_voice": self.preserve_voice,
            "frequency_smoothing": self.frequency_smoothing,
            "temporal_smoothing": self.temporal_smoothing,
            "spectral_floor": self.spectral_floor,
            "wiener_noise_power": self.wiener_noise_power,
            "wavelet_level": self.wavelet_level,
            "adaptive_filter_order": self.adaptive_filter_order,
            "voice_freq_min": self.voice_freq_min,
            "voice_freq_max": self.voice_freq_max,
            "formant_protection": self.formant_protection,
        }


@dataclass
class NoiseReductionResult:
    """Results of noise reduction processing."""

    processed_audio: np.ndarray = field(default_factory=lambda: np.array([]))
    noise_removed: np.ndarray = field(default_factory=lambda: np.array([]))

    original_snr: float = 0.0
    processed_snr: float = 0.0
    snr_improvement: float = 0.0

    original_noise_level: NoiseLevel = NoiseLevel.LOW
    processed_noise_level: NoiseLevel = NoiseLevel.LOW

    processing_time_ms: float = 0.0
    method_used: NoiseReductionMethod = NoiseReductionMethod.SPECTRAL_SUBTRACTION

    quality_metrics: Dict[str, float] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "original_snr": self.original_snr,
            "processed_snr": self.processed_snr,
            "snr_improvement": self.snr_improvement,
            "original_noise_level": self.original_noise_level.value,
            "processed_noise_level": self.processed_noise_level.value,
            "processing_time_ms": self.processing_time_ms,
            "method_used": self.method_used.value,
            "quality_metrics": self.quality_metrics,
            "warnings": self.warnings,
        }


class NoiseReductionProcessor:
    """
    Main processor for noise reduction in medical audio recordings.

    Implements multiple noise reduction algorithms optimized for
    preserving medical speech quality while removing various types
    of environmental and technical noise.
    """

    def __init__(
        self,
        sample_rate: int = 16000,
        frame_size: int = 512,
        hop_length: int = 256,
        n_fft: int = 1024,
        config: Optional[NoiseReductionConfig] = None,
    ):
        """
        Initialize the noise reduction processor.

        Args:
            sample_rate: Audio sample rate in Hz
            frame_size: Size of processing frames
            hop_length: Number of samples between frames
            n_fft: FFT size for spectral processing
            config: Noise reduction configuration
        """
        self.sample_rate = sample_rate
        self.frame_size = frame_size
        self.hop_length = hop_length
        self.n_fft = n_fft
        self.config = config or NoiseReductionConfig()

        # Initialize noise detector
        self.noise_detector = NoiseDetector(
            sample_rate=sample_rate,
            frame_size=frame_size,
            hop_length=hop_length,
            n_fft=n_fft,
        )
        # Frequency bins
        self.frequency_bins = np.fft.fftfreq(n_fft, 1.0 / sample_rate)[: n_fft // 2]

        # Pre-compute windows
        self.window = np.hanning(frame_size)

        # Initialize method-specific components
        self._init_method_components()

        logger.info(
            "NoiseReductionProcessor initialized with method=%s, sample_rate=%dHz",
            self.config.method.value,
            sample_rate,
        )

    def _init_method_components(self) -> None:
        """Initialize components specific to the selected method."""
        if self.config.method == NoiseReductionMethod.ADAPTIVE_FILTER:
            # Initialize adaptive filter coefficients
            self.adaptive_coeffs = np.zeros(self.config.adaptive_filter_order)
            self.adaptive_mu = 0.01  # Learning rate

    async def process_audio(
        self,
        audio_data: np.ndarray,
        noise_profile: Optional[Dict[str, Any]] = None,
        detect_noise: bool = True,
    ) -> NoiseReductionResult:
        """
        Process audio to reduce noise.

        Args:
            audio_data: Input audio signal
            noise_profile: Optional pre-computed noise profile
            detect_noise: Whether to run noise detection first

        Returns:
            NoiseReductionResult with processed audio and metrics
        """
        start_time = datetime.now()

        try:
            # Store original for comparison
            original_audio = audio_data.copy()

            # Detect noise if requested
            detection_result = None
            if detect_noise:
                detection_result = await self.noise_detector.detect_noise(audio_data)
                logger.info(
                    "Detected noise level: %s",
                    detection_result.overall_noise_level.value,
                )

            # Select and apply appropriate method
            if self.config.method == NoiseReductionMethod.SPECTRAL_SUBTRACTION:
                processed_audio = await self._spectral_subtraction(
                    audio_data, noise_profile, detection_result
                )
            elif self.config.method == NoiseReductionMethod.WIENER_FILTER:
                processed_audio = await self._wiener_filter(
                    audio_data, noise_profile, detection_result
                )
            elif self.config.method == NoiseReductionMethod.MULTI_BAND:
                processed_audio = await self._multi_band_reduction(
                    audio_data, noise_profile, detection_result
                )
            else:
                # Default to spectral subtraction
                processed_audio = await self._spectral_subtraction(
                    audio_data, noise_profile, detection_result
                )

            # Apply post-processing
            processed_audio = await self._post_process(processed_audio, original_audio)

            # Calculate quality metrics
            quality_metrics = await self._calculate_quality_metrics(
                original_audio, processed_audio
            )

            # Detect noise in processed audio for comparison
            processed_detection = None
            if detect_noise:
                processed_detection = await self.noise_detector.detect_noise(
                    processed_audio
                )

            # Calculate processing time
            processing_time = (datetime.now() - start_time).total_seconds() * 1000

            # Create result
            result = NoiseReductionResult(
                processed_audio=processed_audio,
                noise_removed=original_audio - processed_audio,
                original_snr=(
                    detection_result.signal_to_noise_ratio if detection_result else 0.0
                ),
                processed_snr=(
                    processed_detection.signal_to_noise_ratio
                    if processed_detection
                    else 0.0
                ),
                snr_improvement=(
                    (
                        processed_detection.signal_to_noise_ratio
                        - detection_result.signal_to_noise_ratio
                    )
                    if detection_result and processed_detection
                    else 0.0
                ),
                original_noise_level=(
                    detection_result.overall_noise_level
                    if detection_result
                    else NoiseLevel.LOW
                ),
                processed_noise_level=(
                    processed_detection.overall_noise_level
                    if processed_detection
                    else NoiseLevel.LOW
                ),
                processing_time_ms=processing_time,
                method_used=self.config.method,
                quality_metrics=quality_metrics,
                warnings=self._generate_warnings(quality_metrics),
            )
            return result

        except Exception as e:
            logger.error("Error in noise reduction: %s", str(e), exc_info=True)
            raise

    async def _spectral_subtraction(
        self,
        audio_data: np.ndarray,
        noise_profile: Optional[Dict[str, Any]],
        _detection_result: Optional[NoiseDetectionResult],
    ) -> np.ndarray:
        """Implement spectral subtraction noise reduction."""
        # Frame the audio
        frames = self._frame_audio(audio_data)
        processed_frames = []

        # Get noise spectrum
        if noise_profile and "average_spectrum" in noise_profile:
            noise_spectrum = np.array(noise_profile["average_spectrum"])
        else:
            # Estimate noise from first few frames
            noise_frames = frames[:10] if len(frames) > 10 else frames
            noise_spectra = []
            for frame in noise_frames:
                windowed = frame * self.window[: len(frame)]
                spectrum = np.abs(np.fft.rfft(windowed, n=self.n_fft))
                noise_spectra.append(spectrum**2)
            noise_spectrum = np.mean(noise_spectra, axis=0)

        # Process each frame
        for frame in frames:
            # Apply window
            windowed = frame * self.window[: len(frame)]

            # FFT
            spectrum = np.fft.rfft(windowed, n=self.n_fft)
            magnitude = np.abs(spectrum)
            phase = np.angle(spectrum)

            # Power spectrum
            power = magnitude**2

            # Spectral subtraction
            alpha = self.config.aggressiveness
            reduced_power = power - alpha * noise_spectrum[: len(power)]

            # Apply spectral floor
            floor = self.config.spectral_floor * noise_spectrum[: len(power)]
            reduced_power = np.maximum(reduced_power, floor)
            # Voice preservation
            if self.config.preserve_voice:
                reduced_power = self._preserve_voice_frequencies(reduced_power)

            # Reconstruct spectrum
            reduced_magnitude = np.sqrt(reduced_power)
            reduced_spectrum = reduced_magnitude * np.exp(1j * phase)

            # IFFT
            reduced_frame = np.fft.irfft(reduced_spectrum, n=self.n_fft)[: len(frame)]
            processed_frames.append(reduced_frame)

        # Overlap-add synthesis
        return self._overlap_add(processed_frames)

    async def _wiener_filter(
        self,
        audio_data: np.ndarray,
        noise_profile: Optional[Dict[str, Any]],
        _detection_result: Optional[NoiseDetectionResult],
    ) -> np.ndarray:
        """Implement Wiener filter noise reduction."""
        frames = self._frame_audio(audio_data)
        processed_frames = []

        # Estimate noise power
        noise_power = self.config.wiener_noise_power
        if noise_profile and "statistics" in noise_profile:
            noise_power = noise_profile["statistics"]["mean_power"]

        for frame in frames:
            # Apply window
            windowed = frame * self.window[: len(frame)]

            # FFT
            spectrum = np.fft.rfft(windowed, n=self.n_fft)
            power = np.abs(spectrum) ** 2

            # Wiener gain
            gain = power / (power + noise_power)

            # Apply gain
            filtered_spectrum = spectrum * gain

            # IFFT
            filtered_frame = np.fft.irfft(filtered_spectrum, n=self.n_fft)[: len(frame)]
            processed_frames.append(filtered_frame)

        return self._overlap_add(processed_frames)

    async def _multi_band_reduction(
        self,
        audio_data: np.ndarray,
        _noise_profile: Optional[Dict[str, Any]],
        _detection_result: Optional[NoiseDetectionResult],
    ) -> np.ndarray:
        """Implement multi-band noise reduction."""
        # Define frequency bands
        bands = [
            (0, 250),  # Low frequencies
            (250, 1000),  # Low-mid
            (1000, 3000),  # Mid
            (3000, 6000),  # High-mid
            (6000, self.sample_rate // 2),  # High
        ]

        frames = self._frame_audio(audio_data)
        processed_frames = []

        for frame in frames:
            # Apply window
            windowed = frame * self.window[: len(frame)]

            # FFT
            spectrum = np.fft.rfft(windowed, n=self.n_fft)
            processed_spectrum = spectrum.copy()

            # Process each band separately
            for low_freq, high_freq in bands:
                # Get band indices
                low_idx = int(low_freq * self.n_fft / self.sample_rate)
                high_idx = int(high_freq * self.n_fft / self.sample_rate)

                # Apply band-specific reduction
                # band_power = np.abs(spectrum[low_idx:high_idx]) ** 2  # For future use

                # Different aggressiveness for different bands
                if low_freq < 250:
                    # More aggressive on low frequencies
                    reduction = 0.1
                elif low_freq < 1000:
                    # Moderate on speech range
                    reduction = 0.5
                else:
                    # Gentle on high frequencies
                    reduction = 0.8

                processed_spectrum[low_idx:high_idx] *= reduction
            # IFFT
            processed_frame = np.fft.irfft(processed_spectrum, n=self.n_fft)[
                : len(frame)
            ]
            processed_frames.append(processed_frame)

        return self._overlap_add(processed_frames)

    def _frame_audio(self, audio_data: np.ndarray) -> List[np.ndarray]:
        """Split audio into overlapping frames."""
        frames = []
        n_frames = (len(audio_data) - self.frame_size) // self.hop_length + 1

        for i in range(n_frames):
            start = i * self.hop_length
            end = start + self.frame_size

            if end <= len(audio_data):
                frames.append(audio_data[start:end])

        return frames

    def _overlap_add(self, frames: List[np.ndarray]) -> np.ndarray:
        """Reconstruct audio from overlapping frames."""
        if not frames:
            return np.array([])

        # Calculate output length
        n_frames = len(frames)
        output_length = (n_frames - 1) * self.hop_length + len(frames[0])

        # Initialize output
        output = np.zeros(output_length)

        # Overlap-add
        for i, frame in enumerate(frames):
            start = i * self.hop_length
            end = start + len(frame)
            output[start:end] += frame

        return output

    def _preserve_voice_frequencies(self, power_spectrum: np.ndarray) -> np.ndarray:
        """Preserve frequencies in the voice range."""
        # Get frequency indices for voice range
        voice_min_idx = int(
            self.config.voice_freq_min * len(power_spectrum) * 2 / self.sample_rate
        )
        voice_max_idx = int(
            self.config.voice_freq_max * len(power_spectrum) * 2 / self.sample_rate
        )
        # Apply protection
        if self.config.formant_protection:
            # Boost formant regions slightly
            formant_boost = 1.2
            power_spectrum[voice_min_idx:voice_max_idx] *= formant_boost

        return power_spectrum

    async def _post_process(
        self, processed_audio: np.ndarray, original_audio: np.ndarray
    ) -> np.ndarray:
        """Apply post-processing to the noise-reduced audio."""
        # Temporal smoothing
        if self.config.temporal_smoothing:
            # Simple moving average
            window_size = 3
            kernel = np.ones(window_size) / window_size
            processed_audio = np.convolve(processed_audio, kernel, mode="same")

        # Normalize to original level
        original_rms = np.sqrt(np.mean(original_audio**2))
        processed_rms = np.sqrt(np.mean(processed_audio**2))

        if processed_rms > 0:
            processed_audio *= original_rms / processed_rms

        # Clip to prevent overflow
        processed_audio = np.clip(processed_audio, -1.0, 1.0)

        return processed_audio

    async def _calculate_quality_metrics(
        self, original_audio: np.ndarray, processed_audio: np.ndarray
    ) -> Dict[str, float]:
        """Calculate quality metrics for the processed audio."""
        metrics = {}

        # Signal-to-Distortion Ratio (SDR)
        distortion = original_audio - processed_audio
        signal_power = np.mean(original_audio**2)
        distortion_power = np.mean(distortion**2)

        if distortion_power > 0:
            metrics["sdr_db"] = 10 * np.log10(signal_power / distortion_power)
        else:
            metrics["sdr_db"] = float("inf")
        # Perceptual Evaluation of Speech Quality (PESQ) approximation
        # This is a simplified metric, not true PESQ
        correlation = np.corrcoef(original_audio, processed_audio)[0, 1]
        metrics["correlation"] = correlation

        # Spectral distortion
        orig_spectrum = np.abs(np.fft.rfft(original_audio))
        proc_spectrum = np.abs(np.fft.rfft(processed_audio))

        spectral_dist = np.mean(np.abs(orig_spectrum - proc_spectrum))
        metrics["spectral_distortion"] = float(spectral_dist)

        # Energy preservation ratio
        orig_energy = np.sum(original_audio**2)
        proc_energy = np.sum(processed_audio**2)

        if orig_energy > 0:
            metrics["energy_ratio"] = proc_energy / orig_energy
        else:
            metrics["energy_ratio"] = 1.0

        return metrics

    def _generate_warnings(self, quality_metrics: Dict[str, float]) -> List[str]:
        """Generate warnings based on quality metrics."""
        warnings = []

        # Check for over-processing
        if quality_metrics.get("sdr_db", 0) < 10:
            warnings.append(
                "High distortion detected. Consider reducing aggressiveness."
            )

        # Check for energy loss
        energy_ratio = quality_metrics.get("energy_ratio", 1.0)
        if energy_ratio < 0.5:
            warnings.append("Significant energy loss. Voice may sound muffled.")
        elif energy_ratio > 1.5:
            warnings.append("Energy amplification detected. Check for artifacts.")

        # Check correlation
        if quality_metrics.get("correlation", 1.0) < 0.7:
            warnings.append(
                "Low correlation with original. Voice characteristics may be altered."
            )

        return warnings

    async def create_noise_profile_from_samples(
        self, noise_samples: List[np.ndarray], profile_name: str = "custom"
    ) -> Dict[str, Any]:
        """
        Create a noise profile from multiple noise-only samples.

        Args:
            noise_samples: List of audio samples containing only noise
            profile_name: Name for the profile

        Returns:
            Noise profile dictionary
        """
        return await self.noise_detector.create_noise_profile(
            noise_samples, profile_name
        )

    def save_noise_profile(self, profile: Dict[str, Any], filepath: Path) -> None:
        """Save a noise profile to disk."""
        filepath.parent.mkdir(parents=True, exist_ok=True)

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(profile, f, indent=2)

        logger.info("Saved noise profile to %s", filepath)

    def load_noise_profile(self, filepath: Path) -> Dict[str, Any]:
        """Load a noise profile from disk."""
        with open(filepath, "r", encoding="utf-8") as f:
            profile: Dict[str, Any] = json.load(f)

        logger.info("Loaded noise profile from %s", filepath)
        return profile

    async def batch_process(
        self,
        audio_files: List[Path],
        output_dir: Path,
        noise_profile: Optional[Dict[str, Any]] = None,
        progress_callback: Optional[Any] = None,
    ) -> List[Optional[NoiseReductionResult]]:
        """
        Process multiple audio files in batch.

        Args:
            audio_files: List of input audio file paths
            output_dir: Directory for processed files
            noise_profile: Optional shared noise profile
            progress_callback: Optional callback for progress updates

        Returns:
            List of processing results
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        results: List[Optional[NoiseReductionResult]] = []
        for i, audio_file in enumerate(audio_files):
            try:
                # Load audio (would need audio loading library in real implementation)
                # For now, we'll assume audio_data is loaded
                audio_data = np.array([])  # Placeholder

                # Process
                result = await self.process_audio(audio_data, noise_profile)
                results.append(result)

                # Save processed audio
                # output_path = output_dir / f"processed_{audio_file.name}"
                # Would save audio here in real implementation

                # Progress callback
                if progress_callback:
                    progress_callback(i + 1, len(audio_files))

            except (IOError, ValueError, RuntimeError) as e:
                logger.error("Error processing %s: %s", audio_file, str(e))
                results.append(None)

        return results

    def get_recommended_config(self, noise_level: NoiseLevel) -> NoiseReductionConfig:
        """Get recommended configuration based on noise level."""
        if noise_level == NoiseLevel.LOW:
            return NoiseReductionConfig(
                method=NoiseReductionMethod.SPECTRAL_SUBTRACTION,
                aggressiveness=0.5,
                preserve_voice=True,
            )
        elif noise_level == NoiseLevel.MODERATE:
            return NoiseReductionConfig(
                method=NoiseReductionMethod.WIENER_FILTER,
                aggressiveness=1.0,
                preserve_voice=True,
            )
        elif noise_level == NoiseLevel.HIGH:
            return NoiseReductionConfig(
                method=NoiseReductionMethod.MULTI_BAND,
                aggressiveness=1.5,
                preserve_voice=True,
                formant_protection=True,
            )
        else:  # SEVERE
            return NoiseReductionConfig(
                method=NoiseReductionMethod.MULTI_BAND,
                aggressiveness=2.0,
                preserve_voice=True,
                formant_protection=True,
                temporal_smoothing=True,
            )
