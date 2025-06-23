"""
Background Noise Filtering Module for Medical Voice Processing.

This module implements advanced noise filtering techniques optimized for
medical voice analysis, preserving critical speech characteristics while
removing unwanted background noise.

Note: Audio processed by this module may contain PHI. Ensure all audio data
is encrypted both in transit and at rest. Implement proper access control
to restrict noise filtering operations to authorized healthcare providers.
"""

# pylint: disable=too-many-lines

import logging
import os
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from scipy import signal
from scipy.ndimage import gaussian_filter1d

from src.security import requires_phi_access

try:
    import librosa
except ImportError:
    librosa = None

try:
    import soundfile as sf
except ImportError:
    sf = None

logger = logging.getLogger(__name__)


class NoiseReductionMethod(Enum):
    """Noise reduction algorithms available."""

    SPECTRAL_SUBTRACTION = "spectral_subtraction"
    WIENER_FILTER = "wiener_filter"
    MMSE = "mmse"  # Minimum Mean Square Error
    SPECTRAL_GATING = "spectral_gating"
    ADAPTIVE_FILTER = "adaptive_filter"
    MULTI_BAND = "multi_band"
    MEDICAL_OPTIMIZED = "medical_optimized"
    AI_ENHANCED = "ai_enhanced"


class NoiseProfile(Enum):
    """Types of noise profiles."""

    WHITE = "white"
    PINK = "pink"
    BROWN = "brown"
    HOSPITAL = "hospital"  # Medical equipment, HVAC
    OUTDOOR = "outdoor"  # Traffic, wind
    CROWD = "crowd"  # Multiple voices
    ELECTRONIC = "electronic"  # Hum, buzz
    CUSTOM = "custom"


@dataclass
class NoiseStatistics:
    """Statistics about detected noise."""

    noise_floor_db: float = -60.0
    noise_spectrum: np.ndarray = field(default_factory=lambda: np.array([]))
    noise_profile: NoiseProfile = NoiseProfile.WHITE

    # Frequency-specific noise levels
    low_freq_noise: float = -60.0  # < 250 Hz
    mid_freq_noise: float = -60.0  # 250-2000 Hz
    high_freq_noise: float = -60.0  # > 2000 Hz

    # Temporal characteristics
    is_stationary: bool = True
    noise_variance: float = 0.0
    burst_locations: List[Tuple[float, float]] = field(default_factory=list)

    # Specific noise types detected
    has_hum: bool = False
    hum_frequency: Optional[float] = None
    has_clicks: bool = False
    click_rate: float = 0.0

    # Signal quality metrics
    snr_global: float = 0.0
    snr_speech_band: float = 0.0  # SNR in speech frequencies

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "noise_floor_db": self.noise_floor_db,
            "noise_profile": self.noise_profile.value,
            "low_freq_noise": self.low_freq_noise,
            "mid_freq_noise": self.mid_freq_noise,
            "high_freq_noise": self.high_freq_noise,
            "is_stationary": self.is_stationary,
            "noise_variance": self.noise_variance,
            "has_hum": self.has_hum,
            "hum_frequency": self.hum_frequency,
            "has_clicks": self.has_clicks,
            "click_rate": self.click_rate,
            "snr_global": self.snr_global,
            "snr_speech_band": self.snr_speech_band,
        }


@dataclass
class FilteringResult:
    """Result of noise filtering operation."""

    filtered_audio: np.ndarray

    # Applied processing
    method_used: NoiseReductionMethod
    reduction_amount_db: float

    # Noise analysis
    noise_stats: NoiseStatistics
    removed_noise: Optional[np.ndarray] = None  # For analysis

    # Quality metrics
    speech_preservation: float = 1.0  # 0-1, higher is better
    artifact_score: float = 0.0  # 0-1, lower is better
    intelligibility_score: float = 1.0

    # Processing details
    sample_rate: int = 16000
    processing_time_ms: float = 0.0

    # Frequency response
    frequency_response: Optional[np.ndarray] = None

    # Warnings and recommendations
    warnings: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "method_used": self.method_used.value,
            "reduction_amount_db": self.reduction_amount_db,
            "noise_stats": self.noise_stats.to_dict(),
            "speech_preservation": self.speech_preservation,
            "artifact_score": self.artifact_score,
            "intelligibility_score": self.intelligibility_score,
            "sample_rate": self.sample_rate,
            "processing_time_ms": self.processing_time_ms,
            "warnings": self.warnings,
            "recommendations": self.recommendations,
        }


@dataclass
class NoiseFilterConfig:
    """Configuration for noise filtering."""

    # Method selection
    method: NoiseReductionMethod = NoiseReductionMethod.MEDICAL_OPTIMIZED
    aggressive_mode: bool = False

    # Reduction parameters
    reduction_factor: float = 0.8  # 0-1, amount of noise to remove
    oversubtraction_factor: float = 1.5  # For spectral subtraction

    # Noise estimation
    noise_estimation_duration: float = 0.5  # seconds
    use_voice_activity_detection: bool = True
    update_noise_profile: bool = True  # Adaptive noise tracking

    # Spectral parameters
    fft_size: int = 2048
    hop_length: int = 512
    window_type: str = "hann"

    # Frequency-specific settings
    preserve_low_freq: bool = True  # Preserve < 80 Hz
    low_freq_threshold: float = 80.0  # Hz
    preserve_high_freq: bool = False  # Preserve > 8000 Hz
    high_freq_threshold: float = 8000.0  # Hz

    # Medical voice optimization
    protect_formants: bool = True  # Preserve speech formants
    formant_bands: List[Tuple[float, float]] = field(
        default_factory=lambda: [
            (700, 1220),  # F1 range
            (1220, 2600),  # F2 range
            (2600, 3500),  # F3 range
        ]
    )

    # Quality control
    min_speech_preservation: float = 0.9
    max_artifact_score: float = 0.2

    # Advanced settings
    use_psychoacoustic_model: bool = True
    smoothing_factor: float = 0.95  # Temporal smoothing
    spectral_floor: float = 0.01  # Minimum spectral value

    # Multi-band settings
    band_boundaries: List[float] = field(
        default_factory=lambda: [80, 250, 500, 1000, 2000, 4000, 8000]
    )
    band_specific_reduction: Dict[int, float] = field(default_factory=dict)


class BackgroundNoiseFilter:
    """
    Advanced background noise filtering for medical voice recordings.

    Implements multiple noise reduction algorithms optimized for preserving
    speech intelligibility and medical-relevant acoustic features.
    """

    def __init__(self, config: Optional[NoiseFilterConfig] = None):
        """
        Initialize the noise filter.

        Args:
            config: Filter configuration
        """
        self.config = config or NoiseFilterConfig()

        # Pre-compute window
        self.window = signal.get_window(self.config.window_type, self.config.fft_size)

        # Initialize noise profile
        self.noise_profile: Optional[np.ndarray] = None
        self.noise_stats: Optional[NoiseStatistics] = None

        # Psychoacoustic model parameters
        self.bark_bands = self._compute_bark_bands()
        self.absolute_threshold = self._compute_absolute_threshold()

        # Thread pool for parallel processing
        self.executor = ThreadPoolExecutor(max_workers=4)

        logger.info(
            "BackgroundNoiseFilter initialized with method=%s", self.config.method.value
        )

    def _compute_bark_bands(self) -> List[Tuple[float, float]]:
        """Compute Bark scale frequency bands."""
        # Bark scale critical bands
        bark_frequencies = [
            0,
            100,
            200,
            300,
            400,
            510,
            630,
            770,
            920,
            1080,
            1270,
            1480,
            1720,
            2000,
            2320,
            2700,
            3150,
            3700,
            4400,
            5300,
            6400,
            7700,
            9500,
            12000,
            15500,
        ]

        bands: List[Tuple[float, float]] = []
        for i in range(len(bark_frequencies) - 1):
            bands.append((float(bark_frequencies[i]), float(bark_frequencies[i + 1])))

        return bands

    def _compute_absolute_threshold(self) -> np.ndarray:
        """Compute absolute threshold of hearing."""
        # Simplified ATH curve
        freqs = np.linspace(0, self.config.fft_size // 2, self.config.fft_size // 2)

        # Convert to kHz
        f_khz = freqs * (16000 / self.config.fft_size) / 1000

        # ATH approximation (in dB SPL)
        ath = (
            3.64 * (f_khz**-0.8)
            - 6.5 * np.exp(-0.6 * (f_khz - 3.3) ** 2)
            + 0.001 * (f_khz**4)
        )

        # Convert to linear scale and normalize
        ath_linear = 10 ** (ath / 20)
        ath_linear = ath_linear / np.max(ath_linear) * 0.1

        return ath_linear

    @requires_phi_access("read")
    async def filter_noise(
        self,
        audio_data: np.ndarray,
        sample_rate: int = 16000,
        noise_sample: Optional[np.ndarray] = None,
        _user_id: str = "system",
    ) -> FilteringResult:
        """
        Filter background noise from audio.

        Args:
            audio_data: Input audio signal
            sample_rate: Sample rate in Hz
            noise_sample: Optional noise-only sample for profiling

        Returns:
            FilteringResult with filtered audio and analysis
        """
        start_time = datetime.now()

        try:
            # Estimate or update noise profile
            if noise_sample is not None:
                await self._estimate_noise_profile(noise_sample, sample_rate)
            elif self.noise_profile is None:
                # Estimate from beginning of audio
                noise_duration = int(
                    self.config.noise_estimation_duration * sample_rate
                )
                noise_segment = audio_data[:noise_duration]
                await self._estimate_noise_profile(noise_segment, sample_rate)

            # Analyze input noise
            self.noise_stats = await self._analyze_noise(audio_data, sample_rate)

            # Apply selected noise reduction method
            if self.config.method == NoiseReductionMethod.SPECTRAL_SUBTRACTION:
                filtered, reduction = await self._spectral_subtraction(
                    audio_data, sample_rate
                )
            elif self.config.method == NoiseReductionMethod.WIENER_FILTER:
                filtered, reduction = await self._wiener_filter(audio_data, sample_rate)
            elif self.config.method == NoiseReductionMethod.MMSE:
                filtered, reduction = await self._mmse_filter(audio_data, sample_rate)
            elif self.config.method == NoiseReductionMethod.SPECTRAL_GATING:
                filtered, reduction = await self._spectral_gating(
                    audio_data, sample_rate
                )
            elif self.config.method == NoiseReductionMethod.ADAPTIVE_FILTER:
                filtered, reduction = await self._adaptive_filter(
                    audio_data, sample_rate
                )
            elif self.config.method == NoiseReductionMethod.MULTI_BAND:
                filtered, reduction = await self._multi_band_filter(
                    audio_data, sample_rate
                )
            elif self.config.method == NoiseReductionMethod.MEDICAL_OPTIMIZED:
                filtered, reduction = await self._medical_optimized_filter(
                    audio_data, sample_rate
                )
            else:
                # AI-enhanced (placeholder)
                filtered, reduction = await self._ai_enhanced_filter(
                    audio_data, sample_rate
                )

            # Post-processing
            if self.config.protect_formants:
                filtered = await self._protect_formants(
                    filtered, audio_data, sample_rate
                )

            # Calculate quality metrics
            speech_preservation = await self._calculate_speech_preservation(
                audio_data, filtered, sample_rate
            )
            artifact_score = await self._calculate_artifact_score(filtered, sample_rate)
            intelligibility = await self._estimate_intelligibility(
                filtered, sample_rate
            )

            # Extract removed noise for analysis
            removed_noise = audio_data - filtered

            # Calculate frequency response
            freq_response = await self._calculate_frequency_response(
                audio_data, filtered, sample_rate
            )

            # Generate warnings and recommendations
            warnings = self._generate_warnings(
                self.noise_stats, reduction, speech_preservation, artifact_score
            )
            recommendations = self._generate_recommendations(
                self.noise_stats, speech_preservation, artifact_score
            )

            # Processing time
            processing_time = (datetime.now() - start_time).total_seconds() * 1000

            return FilteringResult(
                filtered_audio=filtered,
                method_used=self.config.method,
                reduction_amount_db=reduction,
                noise_stats=self.noise_stats,
                removed_noise=removed_noise,
                speech_preservation=speech_preservation,
                artifact_score=artifact_score,
                intelligibility_score=intelligibility,
                sample_rate=sample_rate,
                processing_time_ms=processing_time,
                frequency_response=freq_response,
                warnings=warnings,
                recommendations=recommendations,
            )

        except Exception as e:
            logger.error("Error in noise filtering: %s", str(e), exc_info=True)
            raise

    async def _estimate_noise_profile(
        self, noise_sample: np.ndarray, sample_rate: int
    ) -> None:
        """Estimate noise profile from noise-only sample."""
        # Compute STFT of noise
        _, _, noise_stft = signal.stft(
            noise_sample,
            fs=sample_rate,
            window=self.window,
            nperseg=self.config.fft_size,
            noverlap=self.config.fft_size - self.config.hop_length,
        )

        # Average magnitude spectrum
        self.noise_profile = np.mean(np.abs(noise_stft), axis=1)

        # Add small epsilon to avoid division by zero
        self.noise_profile += 1e-10

        logger.info("Noise profile estimated")

    async def _analyze_noise(
        self, audio_data: np.ndarray, sample_rate: int
    ) -> NoiseStatistics:
        """Analyze noise characteristics in audio."""
        stats = NoiseStatistics()

        # Estimate noise floor using percentile method
        frame_length = int(0.05 * sample_rate)  # 50ms frames
        hop_length = frame_length // 2

        frames = librosa.util.frame(
            audio_data, frame_length=frame_length, hop_length=hop_length
        )
        frame_energy = np.sqrt(np.mean(frames**2, axis=0))

        # Noise floor as lower percentile
        stats.noise_floor_db = 20 * np.log10(np.percentile(frame_energy, 10) + 1e-10)

        # Frequency-specific noise analysis
        freqs, _, stft = signal.stft(
            audio_data,
            fs=sample_rate,
            window=self.window,
            nperseg=self.config.fft_size,
            noverlap=self.config.fft_size - self.config.hop_length,
        )

        magnitude = np.abs(stft)

        # Analyze different frequency bands
        low_mask = freqs < 250
        mid_mask = (freqs >= 250) & (freqs < 2000)
        high_mask = freqs >= 2000

        stats.low_freq_noise = 20 * np.log10(np.mean(magnitude[low_mask, :]) + 1e-10)
        stats.mid_freq_noise = 20 * np.log10(np.mean(magnitude[mid_mask, :]) + 1e-10)
        stats.high_freq_noise = 20 * np.log10(np.mean(magnitude[high_mask, :]) + 1e-10)

        # Check for stationarity
        frame_std = np.std(frame_energy)
        frame_mean = np.mean(frame_energy)
        stats.noise_variance = frame_std / (frame_mean + 1e-10)
        stats.is_stationary = stats.noise_variance < 0.5

        # Detect hum (power line interference)
        stats.has_hum, stats.hum_frequency = await self._detect_hum(
            audio_data, sample_rate
        )

        # Detect clicks/pops
        stats.has_clicks, stats.click_rate = await self._detect_clicks(
            audio_data, sample_rate
        )

        # Calculate SNR
        signal_power = np.mean(audio_data**2)
        noise_power = 10 ** (stats.noise_floor_db / 10)
        stats.snr_global = 10 * np.log10(signal_power / (noise_power + 1e-10))

        # SNR in speech band (300-3400 Hz)
        speech_mask = (freqs >= 300) & (freqs <= 3400)
        speech_signal = np.mean(magnitude[speech_mask, :] ** 2)
        speech_noise = np.mean(magnitude[speech_mask, :10] ** 2)  # First 10 frames
        stats.snr_speech_band = 10 * np.log10(speech_signal / (speech_noise + 1e-10))

        # Classify noise profile
        stats.noise_profile = await self._classify_noise_profile(magnitude, freqs)

        return stats

    async def _detect_hum(
        self, audio_data: np.ndarray, sample_rate: int
    ) -> Tuple[bool, Optional[float]]:
        """Detect power line hum."""
        # Look for 50/60 Hz and harmonics
        fft = np.fft.rfft(audio_data)
        freqs = np.fft.rfftfreq(len(audio_data), 1 / sample_rate)

        magnitude = np.abs(fft)

        # Check for peaks at 50/60 Hz and harmonics
        hum_freqs = [50, 60, 100, 120, 150, 180]
        tolerance = 2  # Hz

        for hum_freq in hum_freqs:
            freq_mask = np.abs(freqs - hum_freq) < tolerance
            if np.any(freq_mask):
                peak_magnitude = np.max(magnitude[freq_mask])
                avg_magnitude = np.mean(magnitude)

                if peak_magnitude > avg_magnitude * 10:  # 20 dB above average
                    return True, float(hum_freq)

        return False, None

    async def _detect_clicks(
        self, audio_data: np.ndarray, sample_rate: int
    ) -> Tuple[bool, float]:
        """Detect clicks and pops in audio."""
        # Use derivative to find sudden changes
        diff = np.diff(audio_data)
        threshold = np.std(diff) * 4  # 4 sigma threshold

        clicks = np.abs(diff) > threshold
        num_clicks = np.sum(clicks)

        duration = len(audio_data) / sample_rate
        click_rate = num_clicks / duration if duration > 0 else 0

        has_clicks = click_rate > 10  # More than 10 clicks per second

        return has_clicks, click_rate

    async def _classify_noise_profile(
        self, magnitude_spectrum: np.ndarray, frequencies: np.ndarray
    ) -> NoiseProfile:
        """Classify the type of noise based on spectral characteristics."""
        # Calculate spectral slope
        log_freq = np.log10(frequencies[1:] + 1)  # Avoid log(0)
        log_mag = np.log10(np.mean(magnitude_spectrum[1:, :], axis=1) + 1e-10)

        # Linear regression for spectral slope
        slope, _ = np.polyfit(log_freq, log_mag, 1)

        # Classify based on slope
        if -0.5 < slope < 0.5:
            return NoiseProfile.WHITE
        elif -1.5 < slope <= -0.5:
            return NoiseProfile.PINK
        elif slope <= -1.5:
            return NoiseProfile.BROWN
        else:
            # Check for specific patterns
            if self.noise_stats and self.noise_stats.has_hum:
                return NoiseProfile.ELECTRONIC
            else:
                return NoiseProfile.CUSTOM

    async def _spectral_subtraction(
        self, audio_data: np.ndarray, sample_rate: int
    ) -> Tuple[np.ndarray, float]:
        """Apply spectral subtraction noise reduction."""
        # STFT
        _, _, stft = signal.stft(
            audio_data,
            fs=sample_rate,
            window=self.window,
            nperseg=self.config.fft_size,
            noverlap=self.config.fft_size - self.config.hop_length,
        )

        magnitude = np.abs(stft)
        phase = np.angle(stft)

        # Expand noise profile to match STFT dimensions
        if self.noise_profile is not None:
            noise_profile_expanded = self.noise_profile[:, np.newaxis]
        else:
            # Estimate from first few frames
            noise_profile_expanded = np.mean(magnitude[:, :10], axis=1, keepdims=True)

        # Apply oversubtraction
        noise_scaled = noise_profile_expanded * self.config.oversubtraction_factor

        # Subtract noise
        magnitude_filtered = magnitude - noise_scaled * self.config.reduction_factor

        # Apply spectral floor
        magnitude_filtered = np.maximum(
            magnitude_filtered, self.config.spectral_floor * magnitude
        )

        # Smooth over time
        if self.config.smoothing_factor > 0:
            for i in range(1, magnitude_filtered.shape[1]):
                magnitude_filtered[:, i] = (
                    self.config.smoothing_factor * magnitude_filtered[:, i - 1]
                    + (1 - self.config.smoothing_factor) * magnitude_filtered[:, i]
                )

        # Reconstruct STFT
        stft_filtered = magnitude_filtered * np.exp(1j * phase)

        # Inverse STFT
        _, filtered_audio = signal.istft(
            stft_filtered,
            fs=sample_rate,
            window=self.window,
            nperseg=self.config.fft_size,
            noverlap=self.config.fft_size - self.config.hop_length,
        )

        # Ensure same length as input
        if len(filtered_audio) > len(audio_data):
            filtered_audio = filtered_audio[: len(audio_data)]
        elif len(filtered_audio) < len(audio_data):
            filtered_audio = np.pad(
                filtered_audio, (0, len(audio_data) - len(filtered_audio))
            )

        # Calculate reduction amount
        reduction_db = 20 * np.log10(
            np.sqrt(np.mean(audio_data**2))
            / (np.sqrt(np.mean(filtered_audio**2)) + 1e-10)
        )

        return filtered_audio, reduction_db

    async def _wiener_filter(
        self, audio_data: np.ndarray, sample_rate: int
    ) -> Tuple[np.ndarray, float]:
        """Apply Wiener filtering."""
        # STFT
        _, _, stft = signal.stft(
            audio_data,
            fs=sample_rate,
            window=self.window,
            nperseg=self.config.fft_size,
            noverlap=self.config.fft_size - self.config.hop_length,
        )

        power_spectrum = np.abs(stft) ** 2

        # Estimate noise power
        if self.noise_profile is not None:
            noise_power = self.noise_profile[:, np.newaxis] ** 2
        else:
            noise_power = np.mean(power_spectrum[:, :10], axis=1, keepdims=True)

        # Wiener gain
        wiener_gain = power_spectrum / (power_spectrum + noise_power + 1e-10)

        # Apply gain with reduction factor
        wiener_gain = wiener_gain**self.config.reduction_factor

        # Apply to STFT
        stft_filtered = stft * wiener_gain

        # Inverse STFT
        _, filtered_audio = signal.istft(
            stft_filtered,
            fs=sample_rate,
            window=self.window,
            nperseg=self.config.fft_size,
            noverlap=self.config.fft_size - self.config.hop_length,
        )

        # Ensure same length
        if len(filtered_audio) != len(audio_data):
            filtered_audio = self._match_length(filtered_audio, len(audio_data))

        # Calculate reduction
        reduction_db = 20 * np.log10(
            np.sqrt(np.mean(audio_data**2))
            / (np.sqrt(np.mean(filtered_audio**2)) + 1e-10)
        )

        return filtered_audio, reduction_db

    async def _mmse_filter(
        self, audio_data: np.ndarray, sample_rate: int
    ) -> Tuple[np.ndarray, float]:
        """Apply Minimum Mean Square Error filtering."""
        # STFT
        _, _, stft = signal.stft(
            audio_data,
            fs=sample_rate,
            window=self.window,
            nperseg=self.config.fft_size,
            noverlap=self.config.fft_size - self.config.hop_length,
        )

        magnitude = np.abs(stft)
        phase = np.angle(stft)

        # Estimate noise
        if self.noise_profile is not None:
            noise_estimate = self.noise_profile[:, np.newaxis]
        else:
            noise_estimate = np.mean(magnitude[:, :10], axis=1, keepdims=True)

        # A priori SNR estimation (decision-directed approach)
        snr_post = magnitude**2 / (noise_estimate**2 + 1e-10)

        # Initialize a priori SNR
        snr_prior = snr_post.copy()
        alpha = 0.98  # Smoothing parameter

        # MMSE gain function
        for i in range(1, magnitude.shape[1]):
            # Decision-directed estimation
            snr_prior[:, i] = alpha * (
                magnitude[:, i - 1] / (noise_estimate[:, 0] + 1e-10)
            ) ** 2 + (1 - alpha) * np.maximum(snr_post[:, i] - 1, 0)

            # MMSE gain
            gain = snr_prior[:, i] / (1 + snr_prior[:, i])

            # Apply gain
            magnitude[:, i] = gain * magnitude[:, i]

        # Reconstruct
        stft_filtered = magnitude * np.exp(1j * phase)

        # Inverse STFT
        _, filtered_audio = signal.istft(
            stft_filtered,
            fs=sample_rate,
            window=self.window,
            nperseg=self.config.fft_size,
            noverlap=self.config.fft_size - self.config.hop_length,
        )

        # Match length
        filtered_audio = self._match_length(filtered_audio, len(audio_data))

        # Calculate reduction
        reduction_db = 20 * np.log10(
            np.sqrt(np.mean(audio_data**2))
            / (np.sqrt(np.mean(filtered_audio**2)) + 1e-10)
        )

        return filtered_audio, reduction_db

    async def _spectral_gating(
        self, audio_data: np.ndarray, sample_rate: int
    ) -> Tuple[np.ndarray, float]:
        """Apply spectral gating noise reduction."""
        # STFT
        _, _, stft = signal.stft(
            audio_data,
            fs=sample_rate,
            window=self.window,
            nperseg=self.config.fft_size,
            noverlap=self.config.fft_size - self.config.hop_length,
        )

        magnitude = np.abs(stft)
        phase = np.angle(stft)

        # Create gate threshold based on noise profile
        if self.noise_profile is not None:
            gate_threshold = self.noise_profile[:, np.newaxis] * 2  # 6 dB above noise
        else:
            gate_threshold = np.mean(magnitude[:, :10], axis=1, keepdims=True) * 2

        # Apply gating
        gate_mask = magnitude > gate_threshold

        # Smooth gate transitions
        for i in range(1, gate_mask.shape[1]):
            gate_mask[:, i] = 0.7 * gate_mask[:, i - 1] + 0.3 * gate_mask[:, i]

        # Apply gate with soft knee
        soft_gate = np.zeros_like(magnitude)
        above_threshold = magnitude > gate_threshold

        # Linear fade in knee region
        knee_width = gate_threshold * 0.5
        knee_region = (magnitude > gate_threshold - knee_width) & (~above_threshold)

        soft_gate[above_threshold] = 1.0
        soft_gate[knee_region] = (
            magnitude[knee_region] - (gate_threshold[knee_region] - knee_width)
        ) / knee_width

        # Apply gate
        magnitude_gated = magnitude * soft_gate * self.config.reduction_factor

        # Reconstruct
        stft_filtered = magnitude_gated * np.exp(1j * phase)

        # Inverse STFT
        _, filtered_audio = signal.istft(
            stft_filtered,
            fs=sample_rate,
            window=self.window,
            nperseg=self.config.fft_size,
            noverlap=self.config.fft_size - self.config.hop_length,
        )

        # Match length
        filtered_audio = self._match_length(filtered_audio, len(audio_data))

        # Calculate reduction
        reduction_db = 20 * np.log10(
            np.sqrt(np.mean(audio_data**2))
            / (np.sqrt(np.mean(filtered_audio**2)) + 1e-10)
        )

        return filtered_audio, reduction_db

    async def _adaptive_filter(
        self, audio_data: np.ndarray, sample_rate: int
    ) -> Tuple[np.ndarray, float]:
        """Apply adaptive filtering using LMS algorithm."""
        _ = sample_rate  # Unused but kept for API consistency
        # Simple LMS adaptive filter
        filter_length = 256
        mu = 0.01  # Learning rate

        # Initialize filter
        w = np.zeros(filter_length)

        # Pad input
        padded = np.pad(audio_data, (filter_length - 1, 0), mode="constant")
        filtered = np.zeros_like(audio_data)

        # Adaptive filtering
        for n, _ in enumerate(audio_data):
            # Get input vector
            x = padded[n : n + filter_length][::-1]

            # Filter output
            y = np.dot(w, x)

            # Error (assuming desired signal is estimated)
            if n < int(0.1 * len(audio_data)):
                # Learning phase - assume mostly noise
                e = audio_data[n] - y
                # Update weights
                w += mu * e * x / (np.dot(x, x) + 1e-10)
            else:
                # Filtering phase
                filtered[n] = audio_data[n] - y * self.config.reduction_factor

        # Calculate reduction
        reduction_db = 20 * np.log10(
            np.sqrt(np.mean(audio_data**2)) / (np.sqrt(np.mean(filtered**2)) + 1e-10)
        )

        return filtered, reduction_db

    async def _multi_band_filter(
        self, audio_data: np.ndarray, sample_rate: int
    ) -> Tuple[np.ndarray, float]:
        """Apply multi-band noise filtering."""
        filtered_total = np.zeros_like(audio_data)

        # Process each band separately
        for i, (low_freq, high_freq) in enumerate(
            zip(self.config.band_boundaries[:-1], self.config.band_boundaries[1:])
        ):
            # Design bandpass filter
            nyquist = sample_rate / 2
            low = low_freq / nyquist
            high = high_freq / nyquist

            if low > 0 and high < 1:
                # Bandpass filter
                sos = signal.butter(4, [low, high], btype="band", output="sos")
            elif low == 0:
                # Lowpass filter
                sos = signal.butter(4, high, btype="low", output="sos")
            else:
                # Highpass filter
                sos = signal.butter(4, low, btype="high", output="sos")

            # Extract band
            band_signal = signal.sosfilt(sos, audio_data)

            # Get band-specific reduction
            if i in self.config.band_specific_reduction:
                reduction = self.config.band_specific_reduction[i]
            else:
                reduction = self.config.reduction_factor

            # Apply spectral subtraction to this band
            band_filtered, _ = await self._spectral_subtraction(
                band_signal, sample_rate
            )

            # Scale by band-specific reduction
            band_filtered *= reduction

            # Add to total
            filtered_total += band_filtered

        # Calculate overall reduction
        reduction_db = 20 * np.log10(
            np.sqrt(np.mean(audio_data**2))
            / (np.sqrt(np.mean(filtered_total**2)) + 1e-10)
        )

        return filtered_total, reduction_db

    async def _medical_optimized_filter(
        self, audio_data: np.ndarray, sample_rate: int
    ) -> Tuple[np.ndarray, float]:
        """Medical-optimized noise filtering preserving diagnostic features."""
        # Start with MMSE as base
        filtered, _ = await self._mmse_filter(audio_data, sample_rate)

        # Protect critical medical frequencies
        if self.config.protect_formants:
            # STFT for formant protection
            freqs, _, stft_original = signal.stft(
                audio_data,
                fs=sample_rate,
                window=self.window,
                nperseg=self.config.fft_size,
                noverlap=self.config.fft_size - self.config.hop_length,
            )

            _, _, stft_filtered = signal.stft(
                filtered,
                fs=sample_rate,
                window=self.window,
                nperseg=self.config.fft_size,
                noverlap=self.config.fft_size - self.config.hop_length,
            )

            # Protect formant regions
            for f_low, f_high in self.config.formant_bands:
                freq_mask = (freqs >= f_low) & (freqs <= f_high)

                # Blend original and filtered in formant regions
                blend_factor = 0.7  # More original in formant regions
                stft_filtered[freq_mask, :] = (
                    blend_factor * stft_original[freq_mask, :]
                    + (1 - blend_factor) * stft_filtered[freq_mask, :]
                )

            # Reconstruct
            _, filtered = signal.istft(
                stft_filtered,
                fs=sample_rate,
                window=self.window,
                nperseg=self.config.fft_size,
                noverlap=self.config.fft_size - self.config.hop_length,
            )

            filtered = self._match_length(filtered, len(audio_data))

        # Apply psychoacoustic model if enabled
        if self.config.use_psychoacoustic_model:
            filtered = await self._apply_psychoacoustic_model(
                filtered, audio_data, sample_rate
            )

        # Preserve very low frequencies if configured
        if self.config.preserve_low_freq:
            # Extract and preserve low frequencies
            sos_low = signal.butter(
                4,
                self.config.low_freq_threshold / (sample_rate / 2),
                btype="low",
                output="sos",
            )
            low_freq_original = signal.sosfilt(sos_low, audio_data)

            # Replace low frequencies with original
            high_pass = signal.butter(
                4,
                self.config.low_freq_threshold / (sample_rate / 2),
                btype="high",
                output="sos",
            )
            filtered_high = signal.sosfilt(high_pass, filtered)
            filtered = filtered_high + low_freq_original

        # Final gain adjustment to match target preservation
        current_preservation = await self._calculate_speech_preservation(
            audio_data, filtered, sample_rate
        )

        if current_preservation < self.config.min_speech_preservation:
            # Blend back some original to improve preservation
            blend = (self.config.min_speech_preservation - current_preservation) / (
                1 - current_preservation + 1e-10
            )
            blend = np.clip(blend, 0, 0.5)
            filtered = (1 - blend) * filtered + blend * audio_data

        # Recalculate reduction
        reduction_db = 20 * np.log10(
            np.sqrt(np.mean(audio_data**2)) / (np.sqrt(np.mean(filtered**2)) + 1e-10)
        )

        return filtered, reduction_db

    async def _ai_enhanced_filter(
        self, audio_data: np.ndarray, sample_rate: int
    ) -> Tuple[np.ndarray, float]:
        """AI-enhanced filtering (placeholder for future ML model)."""
        # For now, use medical-optimized as fallback
        logger.info(
            "AI-enhanced filtering not yet implemented, using medical-optimized"
        )
        return await self._medical_optimized_filter(audio_data, sample_rate)

    async def _protect_formants(
        self, filtered: np.ndarray, original: np.ndarray, sample_rate: int
    ) -> np.ndarray:
        """Protect formant frequencies in filtered audio."""
        _ = original  # Unused but kept for future implementation
        _ = sample_rate  # Unused but kept for future implementation
        # This is handled within medical_optimized_filter
        # Provided as separate method for other filtering methods
        return filtered

    async def _apply_psychoacoustic_model(
        self, filtered: np.ndarray, original: np.ndarray, sample_rate: int
    ) -> np.ndarray:
        """Apply psychoacoustic model to improve perceptual quality."""
        _ = original  # Unused but kept for future implementation
        # STFT
        freqs, _, stft_filtered = signal.stft(
            filtered,
            fs=sample_rate,
            window=self.window,
            nperseg=self.config.fft_size,
            noverlap=self.config.fft_size - self.config.hop_length,
        )

        magnitude = np.abs(stft_filtered)
        phase = np.angle(stft_filtered)

        # Apply masking threshold
        for _, (low, high) in enumerate(self.bark_bands):
            if high > sample_rate / 2:
                break

            # Find frequency bins for this Bark band
            freq_mask = (freqs >= low) & (freqs < high)

            if np.any(freq_mask):
                # Calculate masking threshold for this band
                band_energy = np.mean(magnitude[freq_mask, :], axis=0)

                # Simplified masking calculation
                masking_threshold = band_energy * 0.1  # 20 dB below band energy

                # Apply masking
                magnitude[freq_mask, :] = np.maximum(
                    magnitude[freq_mask, :], masking_threshold
                )

        # Apply absolute threshold of hearing
        ath_expanded = self.absolute_threshold[: len(freqs), np.newaxis]
        magnitude = np.maximum(magnitude, ath_expanded)

        # Reconstruct
        stft_masked = magnitude * np.exp(1j * phase)
        _, audio_masked = signal.istft(
            stft_masked,
            fs=sample_rate,
            window=self.window,
            nperseg=self.config.fft_size,
            noverlap=self.config.fft_size - self.config.hop_length,
        )

        return self._match_length(audio_masked, len(filtered))

    async def _calculate_speech_preservation(
        self, original: np.ndarray, filtered: np.ndarray, sample_rate: int
    ) -> float:
        """Calculate how well speech is preserved."""
        # Focus on speech frequency range
        sos = signal.butter(
            4,
            [300 / (sample_rate / 2), 3400 / (sample_rate / 2)],
            btype="band",
            output="sos",
        )

        speech_original = signal.sosfilt(sos, original)
        speech_filtered = signal.sosfilt(sos, filtered)

        # Correlation in speech band
        correlation = np.corrcoef(speech_original, speech_filtered)[0, 1]

        # Energy preservation
        energy_ratio = np.sum(speech_filtered**2) / (np.sum(speech_original**2) + 1e-10)
        energy_preservation = min(1.0, energy_ratio)

        # Spectral similarity
        stft_original = librosa.stft(speech_original, n_fft=1024, hop_length=256)
        stft_filtered = librosa.stft(speech_filtered, n_fft=1024, hop_length=256)

        mag_original = np.abs(stft_original)
        mag_filtered = np.abs(stft_filtered)

        # Cosine similarity of magnitude spectra
        spectral_similarity = np.mean(
            [
                np.dot(mag_original[:, i], mag_filtered[:, i])
                / (
                    np.linalg.norm(mag_original[:, i])
                    * np.linalg.norm(mag_filtered[:, i])
                    + 1e-10
                )
                for i in range(min(mag_original.shape[1], mag_filtered.shape[1]))
            ]
        )

        # Combined score
        preservation_score = (
            0.4 * max(0, correlation)
            + 0.3 * energy_preservation
            + 0.3 * spectral_similarity
        )

        return float(np.clip(preservation_score, 0, 1))

    async def _calculate_artifact_score(
        self, filtered: np.ndarray, sample_rate: int
    ) -> float:
        """Calculate artifact/distortion score."""
        _ = sample_rate  # Unused but kept for API consistency
        # Check for musical noise (tonal artifacts)
        stft = librosa.stft(filtered, n_fft=1024, hop_length=256)
        magnitude = np.abs(stft)

        # Temporal variance of spectral bins
        temporal_variance = np.var(magnitude, axis=1)
        mean_magnitude = np.mean(magnitude, axis=1) + 1e-10

        # High variance relative to mean indicates musical noise
        musical_noise_score = np.mean(temporal_variance / mean_magnitude)

        # Check for discontinuities
        diff = np.diff(filtered)
        discontinuity_score = np.sum(np.abs(diff) > 3 * np.std(diff)) / len(diff)

        # Check for excessive zeros (over-gating)
        zero_score = np.sum(np.abs(filtered) < 1e-6) / len(filtered)

        # Combined artifact score
        artifact_score = (
            0.5 * min(1.0, musical_noise_score)
            + 0.3 * discontinuity_score
            + 0.2 * zero_score
        )

        return float(np.clip(artifact_score, 0, 1))

    async def _estimate_intelligibility(
        self, filtered: np.ndarray, sample_rate: int
    ) -> float:
        """Estimate speech intelligibility (simplified)."""
        # Extract speech-relevant features
        # This is a simplified version - real implementation would use
        # standardized metrics like STOI or PESQ

        # Check presence of key frequency bands
        band_energies = []
        key_bands = [(200, 500), (500, 1000), (1000, 2000), (2000, 4000)]

        for low, high in key_bands:
            sos = signal.butter(
                4,
                [low / (sample_rate / 2), high / (sample_rate / 2)],
                btype="band",
                output="sos",
            )
            band_signal = signal.sosfilt(sos, filtered)
            band_energy = np.sqrt(np.mean(band_signal**2))
            band_energies.append(band_energy)

        # Normalize energies
        total_energy = sum(band_energies) + 1e-10
        band_ratios = [e / total_energy for e in band_energies]

        # Expected ratios for good intelligibility
        expected_ratios = [0.2, 0.3, 0.3, 0.2]

        # Calculate deviation from expected
        deviation = sum(abs(a - b) for a, b in zip(band_ratios, expected_ratios))

        # Convert to intelligibility score
        intelligibility = max(0, 1 - deviation)

        return float(intelligibility)

    async def _calculate_frequency_response(
        self, original: np.ndarray, filtered: np.ndarray, sample_rate: int
    ) -> np.ndarray:
        """Calculate frequency response of the filter."""
        _ = sample_rate  # Unused but kept for API consistency
        # Use shorter FFT for smoother response
        n_fft = 512

        # Calculate average spectra
        orig_fft = np.fft.rfft(original[: n_fft * 10])
        filt_fft = np.fft.rfft(filtered[: n_fft * 10])

        # Magnitude response
        response = np.abs(filt_fft) / (np.abs(orig_fft) + 1e-10)

        # Convert to dB
        response_db = 20 * np.log10(response + 1e-10)

        # Smooth response
        response_db_smooth: np.ndarray = gaussian_filter1d(response_db, sigma=2)

        return response_db_smooth

    def _match_length(self, audio: np.ndarray, target_length: int) -> np.ndarray:
        """Match audio length to target."""
        if len(audio) > target_length:
            return audio[:target_length]
        elif len(audio) < target_length:
            return np.pad(audio, (0, target_length - len(audio)))
        return audio

    def _generate_warnings(
        self,
        noise_stats: NoiseStatistics,
        reduction_db: float,
        speech_preservation: float,
        artifact_score: float,
    ) -> List[str]:
        """Generate warnings based on analysis."""
        warnings = []

        if noise_stats.snr_global < 6:
            warnings.append(f"Very low SNR: {noise_stats.snr_global:.1f} dB")

        if reduction_db > 20:
            warnings.append(f"Heavy noise reduction applied: {reduction_db:.1f} dB")

        if speech_preservation < 0.7:
            warnings.append(f"Low speech preservation: {speech_preservation:.2f}")

        if artifact_score > 0.5:
            warnings.append(f"High artifact score: {artifact_score:.2f}")

        if noise_stats.has_hum:
            warnings.append(
                f"Power line hum detected at {noise_stats.hum_frequency} Hz"
            )

        if noise_stats.has_clicks:
            warnings.append(
                f"Clicks/pops detected: {noise_stats.click_rate:.1f} per second"
            )

        if not noise_stats.is_stationary:
            warnings.append("Non-stationary noise detected")

        return warnings

    def _generate_recommendations(
        self,
        noise_stats: NoiseStatistics,
        speech_preservation: float,
        artifact_score: float,
    ) -> List[str]:
        """Generate recommendations for better results."""
        recommendations = []

        if noise_stats.snr_global < 10:
            recommendations.append("Consider re-recording in quieter environment")

        if noise_stats.has_hum:
            recommendations.append(
                "Use notch filter for power line hum removal before general denoising"
            )

        if speech_preservation < 0.8 and artifact_score > 0.3:
            recommendations.append("Try less aggressive noise reduction settings")

        if noise_stats.low_freq_noise > -30:
            recommendations.append(
                "High low-frequency noise - check for wind or vibration"
            )

        if not noise_stats.is_stationary:
            recommendations.append(
                "Non-stationary noise - adaptive filtering may work better"
            )

        return recommendations

    async def process_batch(
        self,
        audio_files: List[str],
        output_dir: str,
        use_consistent_profile: bool = True,
    ) -> List[FilteringResult]:
        """
        Process multiple audio files with noise filtering.

        Args:
            audio_files: List of input file paths
            output_dir: Directory for filtered outputs
            use_consistent_profile: Use same noise profile for all files

        Returns:
            List of filtering results
        """
        results = []

        # Estimate common noise profile if requested
        if use_consistent_profile and len(audio_files) > 0:
            # Use first file's beginning for noise estimation
            first_audio, sr = librosa.load(audio_files[0], sr=None)
            noise_duration = int(self.config.noise_estimation_duration * sr)
            noise_sample = first_audio[:noise_duration]
            await self._estimate_noise_profile(noise_sample, sr)

        # Process each file
        for file_path in audio_files:
            try:
                # Load audio
                audio_data, sr = librosa.load(file_path, sr=None)

                # Filter noise
                result = await self.filter_noise(audio_data, sr)

                # Save filtered audio
                output_path = os.path.join(
                    output_dir, os.path.basename(file_path).replace(".", "_denoised.")
                )

                sf.write(output_path, result.filtered_audio, sr)

                results.append(result)
                logger.info("Filtered %s -> %s", file_path, output_path)

            except (IOError, ValueError, RuntimeError) as e:
                logger.error("Error filtering %s: %s", file_path, str(e))
                results.append(None)

        return results

    def create_noise_report(self, results: List[FilteringResult]) -> Dict[str, Any]:
        """Create summary report of noise filtering results."""
        valid_results = [r for r in results if r is not None]

        if not valid_results:
            return {"error": "No valid results"}

        report = {
            "file_count": len(results),
            "successful": len(valid_results),
            "failed": len(results) - len(valid_results),
            "noise_analysis": {
                "avg_noise_floor": np.mean(
                    [r.noise_stats.noise_floor_db for r in valid_results]
                ),
                "avg_snr_global": np.mean(
                    [r.noise_stats.snr_global for r in valid_results]
                ),
                "avg_snr_speech": np.mean(
                    [r.noise_stats.snr_speech_band for r in valid_results]
                ),
                "files_with_hum": sum(
                    1 for r in valid_results if r.noise_stats.has_hum
                ),
                "files_with_clicks": sum(
                    1 for r in valid_results if r.noise_stats.has_clicks
                ),
            },
            "reduction_applied": {
                "avg_reduction_db": np.mean(
                    [r.reduction_amount_db for r in valid_results]
                ),
                "min_reduction_db": np.min(
                    [r.reduction_amount_db for r in valid_results]
                ),
                "max_reduction_db": np.max(
                    [r.reduction_amount_db for r in valid_results]
                ),
            },
            "quality_metrics": {
                "avg_speech_preservation": np.mean(
                    [r.speech_preservation for r in valid_results]
                ),
                "avg_artifact_score": np.mean(
                    [r.artifact_score for r in valid_results]
                ),
                "avg_intelligibility": np.mean(
                    [r.intelligibility_score for r in valid_results]
                ),
            },
            "methods_used": {
                method.value: sum(1 for r in valid_results if r.method_used == method)
                for method in NoiseReductionMethod
            },
            "all_warnings": list(set(w for r in valid_results for w in r.warnings)),
            "all_recommendations": list(
                set(rec for r in valid_results for rec in r.recommendations)
            ),
        }

        return report


# Example usage functions
@requires_phi_access("read")
async def denoise_medical_recording(
    file_path: str, user_id: str = "system"
) -> FilteringResult:
    """Denoise a medical voice recording."""
    _ = file_path  # Unused in example function
    config = NoiseFilterConfig(
        method=NoiseReductionMethod.MEDICAL_OPTIMIZED,
        reduction_factor=0.7,  # Moderate reduction
        protect_formants=True,
        use_psychoacoustic_model=True,
        min_speech_preservation=0.85,
    )

    noise_filter = BackgroundNoiseFilter(config)

    # Load audio (placeholder)
    audio_data = np.random.randn(16000 * 5) * 0.1  # 5 seconds with noise

    # Add simulated speech
    t = np.linspace(0, 5, 16000 * 5)
    speech = 0.5 * np.sin(2 * np.pi * 200 * t) * (1 + 0.5 * np.sin(2 * np.pi * 4 * t))
    audio_data += speech

    result: FilteringResult = await noise_filter.filter_noise(
        audio_data, 16000, _user_id=user_id
    )

    logger.info("Denoising complete: %.1f dB reduction", result.reduction_amount_db)
    logger.info("Speech preservation: %.2f", result.speech_preservation)
    logger.info("Artifact score: %.2f", result.artifact_score)

    return result


async def analyze_noise_profile(file_path: str) -> NoiseStatistics:
    """Analyze noise characteristics in audio."""
    _ = file_path  # Unused in example function
    noise_filter = BackgroundNoiseFilter()

    # Load audio (placeholder)
    audio_data = np.random.randn(16000 * 2) * 0.05  # 2 seconds of noise

    # Add some specific noise types
    # Power line hum
    t = np.linspace(0, 2, 16000 * 2)
    audio_data += 0.02 * np.sin(2 * np.pi * 60 * t)  # 60 Hz hum

    # Analyze using public method
    result: FilteringResult = await noise_filter.filter_noise(audio_data, 16000)

    # The result contains noise statistics
    logger.info("Denoising complete: %.1f dB reduction", result.reduction_amount_db)
    logger.info("Speech preservation: %.2f", result.speech_preservation)

    if result.noise_stats is None:
        raise ValueError("Noise statistics not available")

    return result.noise_stats
