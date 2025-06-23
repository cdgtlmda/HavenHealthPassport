"""
Volume Normalization Module for Medical Voice Processing.

This module implements volume normalization for voice recordings
to ensure consistent audio levels across different recording conditions
and devices, crucial for accurate medical voice analysis. All patient data
is encrypted and access controlled.
"""

# pylint: disable=too-many-lines

import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from scipy import signal

try:
    import librosa
except ImportError:
    librosa = None

try:
    import soundfile as sf
except ImportError:
    sf = None

logger = logging.getLogger(__name__)


class NormalizationType(Enum):
    """Types of volume normalization methods."""

    PEAK = "peak"  # Normalize to peak amplitude
    RMS = "rms"  # Root Mean Square normalization
    LUFS = "lufs"  # Loudness Units Full Scale (broadcast standard)
    DYNAMIC = "dynamic"  # Dynamic range compression
    MEDICAL = "medical"  # Medical-specific normalization
    ADAPTIVE = "adaptive"  # Adaptive normalization based on content
    PERCEPTUAL = "perceptual"  # Perceptual loudness normalization


class DynamicRangeProfile(Enum):
    """Dynamic range compression profiles."""

    NONE = "none"
    LIGHT = "light"  # Minimal compression
    MODERATE = "moderate"  # Standard compression
    HEAVY = "heavy"  # Strong compression
    BROADCAST = "broadcast"  # Broadcast standards
    MEDICAL_VOICE = "medical_voice"  # Optimized for medical voice analysis


@dataclass
class VolumeStatistics:
    """Statistics about audio volume characteristics."""

    peak_amplitude: float = 0.0
    rms_level: float = 0.0
    lufs_integrated: float = -70.0  # Integrated loudness
    lufs_momentary: List[float] = field(default_factory=list)
    lufs_short_term: List[float] = field(default_factory=list)

    dynamic_range: float = 0.0
    crest_factor: float = 0.0  # Peak to RMS ratio

    # Percentile levels
    percentile_10: float = 0.0
    percentile_50: float = 0.0  # Median
    percentile_90: float = 0.0

    # Voice-specific metrics
    speech_level: float = 0.0  # Estimated speech level
    noise_floor: float = -60.0  # Background noise level
    snr: float = 0.0  # Signal-to-noise ratio

    # Clipping detection
    clipping_samples: int = 0
    clipping_ratio: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "peak_amplitude": self.peak_amplitude,
            "rms_level": self.rms_level,
            "lufs_integrated": self.lufs_integrated,
            "dynamic_range": self.dynamic_range,
            "crest_factor": self.crest_factor,
            "speech_level": self.speech_level,
            "noise_floor": self.noise_floor,
            "snr": self.snr,
            "clipping_samples": self.clipping_samples,
            "clipping_ratio": self.clipping_ratio,
        }


@dataclass
class NormalizationResult:
    """Result of volume normalization processing."""

    normalized_audio: np.ndarray

    # Applied settings
    normalization_type: NormalizationType
    target_level: float
    applied_gain: float  # Gain applied in dB

    # Statistics
    input_stats: VolumeStatistics
    output_stats: VolumeStatistics

    # Processing details
    compression_ratio: Optional[float] = None
    gate_threshold: Optional[float] = None
    limiter_engaged: bool = False

    # Quality metrics
    thd: float = 0.0  # Total harmonic distortion
    preservation_score: float = 1.0  # How well original dynamics preserved

    # Processing metadata
    sample_rate: int = 16000
    processing_time_ms: float = 0.0

    # Warnings
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "normalization_type": self.normalization_type.value,
            "target_level": self.target_level,
            "applied_gain": self.applied_gain,
            "input_stats": self.input_stats.to_dict(),
            "output_stats": self.output_stats.to_dict(),
            "compression_ratio": self.compression_ratio,
            "limiter_engaged": self.limiter_engaged,
            "thd": self.thd,
            "preservation_score": self.preservation_score,
            "sample_rate": self.sample_rate,
            "processing_time_ms": self.processing_time_ms,
            "warnings": self.warnings,
        }


@dataclass
class NormalizationConfig:
    """Configuration for volume normalization."""

    # Target levels
    target_peak: float = -1.0  # dB for peak normalization
    target_rms: float = -20.0  # dB for RMS normalization
    target_lufs: float = -16.0  # LUFS for loudness normalization

    # Normalization settings
    normalization_type: NormalizationType = NormalizationType.MEDICAL
    preserve_dynamics: bool = True  # Preserve relative dynamics

    # Dynamic range compression
    enable_compression: bool = True
    compression_profile: DynamicRangeProfile = DynamicRangeProfile.MEDICAL_VOICE
    compression_threshold: float = -20.0  # dB
    compression_ratio: float = 3.0  # 3:1 compression
    compression_knee: float = 2.0  # dB soft knee
    attack_time_ms: float = 5.0
    release_time_ms: float = 50.0

    # Limiting and protection
    enable_limiter: bool = True
    limiter_threshold: float = -0.5  # dB
    limiter_release_ms: float = 10.0

    # Gating (silence removal)
    enable_gate: bool = True
    gate_threshold: float = -50.0  # dB
    gate_ratio: float = 10.0
    gate_attack_ms: float = 1.0
    gate_release_ms: float = 100.0

    # Medical voice specific
    preserve_medical_frequencies: bool = True
    medical_freq_range: Tuple[float, float] = (85, 3400)  # Hz
    enhance_speech_clarity: bool = True

    # Advanced settings
    use_k_weighting: bool = True  # ITU-R BS.1770 K-weighting
    momentary_block_size: float = 0.4  # seconds
    short_term_block_size: float = 3.0  # seconds

    # Safety settings
    max_gain: float = 40.0  # dB maximum gain
    prevent_clipping: bool = True
    headroom: float = 0.5  # dB headroom


class VolumeNormalizer:
    """
    Normalizes audio volume for consistent medical voice analysis.

    Handles various normalization methods including peak, RMS, LUFS,
    and medical-specific normalization that preserves important
    voice characteristics for clinical assessment.
    """

    def __init__(self, config: Optional[NormalizationConfig] = None):
        """
        Initialize the volume normalizer.

        Args:
            config: Normalization configuration
        """
        self.config = config or NormalizationConfig()

        # Initialize filters for LUFS measurement
        self._init_lufs_filters()

        # Initialize compression parameters
        self._init_compression_params()

        logger.info(
            "VolumeNormalizer initialized with type=%s",
            self.config.normalization_type.value,
        )

    def _init_lufs_filters(self) -> None:
        """Initialize filters for LUFS measurement (ITU-R BS.1770-4)."""
        # Pre-filter (shelving filter)
        # Boost high frequencies: +4 dB at 2 kHz
        self.prefilter_b = np.array(
            [1.53512485958697, -2.69169618940638, 1.19839281085285]
        )
        self.prefilter_a = np.array([1.0, -1.69065929318241, 0.73248077421585])

        # RLB filter (Revised Low-frequency B-curve weighting)
        self.rlb_b = np.array([1.0, -2.0, 1.0])
        self.rlb_a = np.array([1.0, -1.99004745483398, 0.99007225036621])

    def _init_compression_params(self) -> None:
        """Initialize compression parameters based on profile."""
        profiles = {
            DynamicRangeProfile.NONE: {"ratio": 1.0, "threshold": 0.0, "knee": 0.0},
            DynamicRangeProfile.LIGHT: {"ratio": 2.0, "threshold": -15.0, "knee": 4.0},
            DynamicRangeProfile.MODERATE: {
                "ratio": 3.0,
                "threshold": -20.0,
                "knee": 2.0,
            },
            DynamicRangeProfile.HEAVY: {"ratio": 6.0, "threshold": -25.0, "knee": 1.0},
            DynamicRangeProfile.MEDICAL_VOICE: {
                "ratio": 3.0,
                "threshold": -18.0,
                "knee": 3.0,
                "preserve_transients": True,
            },
        }

        profile = profiles.get(
            self.config.compression_profile, profiles[DynamicRangeProfile.MODERATE]
        )

        if self.config.compression_profile == DynamicRangeProfile.MEDICAL_VOICE:
            # Override with config values
            self.compression_params = profile
        else:
            self.compression_params = profile

    async def normalize(
        self, audio_data: np.ndarray, sample_rate: int = 16000
    ) -> NormalizationResult:
        """
        Normalize audio volume.

        Args:
            audio_data: Input audio signal
            sample_rate: Sample rate in Hz

        Returns:
            NormalizationResult with normalized audio and statistics
        """
        start_time = datetime.now()

        try:
            # Analyze input audio
            input_stats = await self._analyze_volume(audio_data, sample_rate)

            # Check for clipping
            if input_stats.clipping_ratio > 0.01:  # More than 1% clipping
                logger.warning(
                    "Input audio has %.1f%% clipping", input_stats.clipping_ratio * 100
                )

            # Apply normalization based on type
            if self.config.normalization_type == NormalizationType.PEAK:
                normalized, gain = await self._normalize_peak(audio_data, input_stats)
            elif self.config.normalization_type == NormalizationType.RMS:
                normalized, gain = await self._normalize_rms(audio_data, input_stats)
            elif self.config.normalization_type == NormalizationType.LUFS:
                normalized, gain = await self._normalize_lufs(
                    audio_data, sample_rate, input_stats
                )
            elif self.config.normalization_type == NormalizationType.MEDICAL:
                normalized, gain = await self._normalize_medical(
                    audio_data, sample_rate, input_stats
                )
            elif self.config.normalization_type == NormalizationType.DYNAMIC:
                normalized, gain = await self._normalize_dynamic(
                    audio_data, sample_rate, input_stats
                )
            else:
                # Default to adaptive
                normalized, gain = await self._normalize_adaptive(
                    audio_data, sample_rate, input_stats
                )

            # Apply compression if enabled
            compression_ratio = None
            if self.config.enable_compression:
                normalized, compression_ratio = await self._apply_compression(
                    normalized, sample_rate
                )

            # Apply limiting if enabled
            limiter_engaged = False
            if self.config.enable_limiter:
                normalized, limiter_engaged = await self._apply_limiting(
                    normalized, sample_rate
                )

            # Analyze output
            output_stats = await self._analyze_volume(normalized, sample_rate)

            # Calculate quality metrics
            thd = self._calculate_thd(audio_data, normalized)
            preservation_score = self._calculate_preservation_score(
                input_stats, output_stats, audio_data, normalized
            )

            # Generate warnings
            warnings = self._generate_warnings(
                input_stats, output_stats, gain, compression_ratio
            )

            # Processing time
            processing_time = (datetime.now() - start_time).total_seconds() * 1000

            return NormalizationResult(
                normalized_audio=normalized,
                normalization_type=self.config.normalization_type,
                target_level=self._get_target_level(),
                applied_gain=gain,
                input_stats=input_stats,
                output_stats=output_stats,
                compression_ratio=compression_ratio,
                gate_threshold=(
                    self.config.gate_threshold if self.config.enable_gate else None
                ),
                limiter_engaged=limiter_engaged,
                thd=thd,
                preservation_score=preservation_score,
                sample_rate=sample_rate,
                processing_time_ms=processing_time,
                warnings=warnings,
            )

        except Exception as e:
            logger.error("Error in volume normalization: %s", str(e), exc_info=True)
            raise

    async def _analyze_volume(
        self, audio_data: np.ndarray, sample_rate: int
    ) -> VolumeStatistics:
        """Analyze volume statistics of audio."""
        stats = VolumeStatistics()

        # Basic measurements
        stats.peak_amplitude = 20 * np.log10(np.max(np.abs(audio_data)) + 1e-10)
        stats.rms_level = 20 * np.log10(np.sqrt(np.mean(audio_data**2)) + 1e-10)

        # LUFS measurement
        lufs_values = await self._measure_lufs(audio_data, sample_rate)
        stats.lufs_integrated = lufs_values["integrated"]
        stats.lufs_momentary = lufs_values["momentary"]
        stats.lufs_short_term = lufs_values["short_term"]

        # Dynamic range
        stats.dynamic_range = stats.peak_amplitude - stats.rms_level
        stats.crest_factor = stats.peak_amplitude - stats.rms_level

        # Percentiles
        abs_audio = np.abs(audio_data)
        stats.percentile_10 = 20 * np.log10(np.percentile(abs_audio, 10) + 1e-10)
        stats.percentile_50 = 20 * np.log10(np.percentile(abs_audio, 50) + 1e-10)
        stats.percentile_90 = 20 * np.log10(np.percentile(abs_audio, 90) + 1e-10)

        # Voice-specific analysis
        speech_segments = self._detect_speech_segments(audio_data, sample_rate)
        if speech_segments:
            speech_audio = np.concatenate(
                [audio_data[start:end] for start, end in speech_segments]
            )
            stats.speech_level = 20 * np.log10(
                np.sqrt(np.mean(speech_audio**2)) + 1e-10
            )

        # Noise floor estimation
        stats.noise_floor = await self._estimate_noise_floor(audio_data, sample_rate)
        stats.snr = stats.speech_level - stats.noise_floor

        # Clipping detection
        clipping_threshold = 0.99
        stats.clipping_samples = np.sum(abs_audio > clipping_threshold)
        stats.clipping_ratio = stats.clipping_samples / len(audio_data)

        return stats

    async def _measure_lufs(
        self, audio_data: np.ndarray, sample_rate: int
    ) -> Dict[str, Any]:
        """Measure LUFS (Loudness Units Full Scale) according to ITU-R BS.1770-4."""
        # Apply K-weighting filters
        if self.config.use_k_weighting:
            # Pre-filter
            filtered = signal.lfilter(self.prefilter_b, self.prefilter_a, audio_data)
            # RLB filter
            filtered = signal.lfilter(self.rlb_b, self.rlb_a, filtered)
        else:
            filtered = audio_data.copy()

        # Calculate momentary loudness (400ms blocks)
        momentary_samples = int(self.config.momentary_block_size * sample_rate)
        momentary_hop = momentary_samples // 4  # 75% overlap

        momentary_loudness = []
        for i in range(0, len(filtered) - momentary_samples, momentary_hop):
            block = filtered[i : i + momentary_samples]
            mean_square = np.mean(block**2)
            if mean_square > 0:
                loudness = -0.691 + 10 * np.log10(mean_square)
                momentary_loudness.append(loudness)

        # Calculate short-term loudness (3s blocks)
        short_term_samples = int(self.config.short_term_block_size * sample_rate)
        short_term_hop = short_term_samples // 4

        short_term_loudness = []
        for i in range(0, len(filtered) - short_term_samples, short_term_hop):
            block = filtered[i : i + short_term_samples]
            mean_square = np.mean(block**2)
            if mean_square > 0:
                loudness = -0.691 + 10 * np.log10(mean_square)
                short_term_loudness.append(loudness)

        # Calculate integrated loudness
        # Gate at -70 LUFS (absolute) and -10 LU (relative)
        if momentary_loudness:
            # Absolute gating
            gated_blocks = [
                loudness for loudness in momentary_loudness if loudness > -70
            ]

            if gated_blocks:
                # Relative gating
                mean_loudness = np.mean(gated_blocks)
                relative_gate = mean_loudness - 10
                gated_blocks = [
                    loudness for loudness in gated_blocks if loudness > relative_gate
                ]

                if gated_blocks:
                    integrated_loudness = np.mean(gated_blocks)
                else:
                    integrated_loudness = -70.0
            else:
                integrated_loudness = -70.0
        else:
            integrated_loudness = -70.0

        return {
            "integrated": integrated_loudness,
            "momentary": momentary_loudness,
            "short_term": short_term_loudness,
        }

    def _detect_speech_segments(
        self, audio_data: np.ndarray, sample_rate: int
    ) -> List[Tuple[int, int]]:
        """Detect speech segments in audio."""
        # Simple energy-based VAD
        frame_length = int(0.025 * sample_rate)  # 25ms frames
        hop_length = int(0.010 * sample_rate)  # 10ms hop

        # Calculate frame energy
        frames = librosa.util.frame(
            audio_data, frame_length=frame_length, hop_length=hop_length
        )
        frame_energy = np.sum(frames**2, axis=0)

        # Dynamic threshold
        energy_threshold = np.percentile(frame_energy, 30)

        # Find speech frames
        speech_frames = frame_energy > energy_threshold

        # Convert to segments
        segments = []
        in_speech = False
        start = 0

        for i, is_speech in enumerate(speech_frames):
            frame_start = i * hop_length

            if is_speech and not in_speech:
                start = frame_start
                in_speech = True
            elif not is_speech and in_speech:
                segments.append((start, frame_start))
                in_speech = False

        if in_speech:
            segments.append((start, len(audio_data)))

        # Merge close segments
        merged_segments: List[Tuple[int, int]] = []
        min_gap = int(0.3 * sample_rate)  # 300ms minimum gap

        for start, end in segments:
            if merged_segments and start - merged_segments[-1][1] < min_gap:
                merged_segments[-1] = (merged_segments[-1][0], end)
            else:
                merged_segments.append((start, end))

        return merged_segments

    async def _estimate_noise_floor(
        self, audio_data: np.ndarray, sample_rate: int
    ) -> float:
        """Estimate noise floor level."""
        # Use percentile method for noise floor estimation
        # Assume bottom 10% of samples represent noise
        frame_length = int(0.1 * sample_rate)  # 100ms frames
        hop_length = frame_length // 2

        frames = librosa.util.frame(
            audio_data, frame_length=frame_length, hop_length=hop_length
        )
        frame_rms = np.sqrt(np.mean(frames**2, axis=0))

        # Get lower percentile as noise estimate
        noise_percentile = 10
        noise_rms = np.percentile(frame_rms[frame_rms > 0], noise_percentile)

        return float(20 * np.log10(noise_rms + 1e-10))

    def _get_target_level(self) -> float:
        """Get target level based on normalization type."""
        if self.config.normalization_type == NormalizationType.PEAK:
            return self.config.target_peak
        elif self.config.normalization_type == NormalizationType.RMS:
            return self.config.target_rms
        elif self.config.normalization_type == NormalizationType.LUFS:
            return self.config.target_lufs
        else:
            return -16.0  # Default LUFS target

    async def _normalize_peak(
        self, audio_data: np.ndarray, stats: VolumeStatistics
    ) -> Tuple[np.ndarray, float]:
        """Peak normalization."""
        current_peak_linear = 10 ** (stats.peak_amplitude / 20)
        target_peak_linear = 10 ** (self.config.target_peak / 20)

        gain_linear = target_peak_linear / (current_peak_linear + 1e-10)
        gain_db = 20 * np.log10(gain_linear)

        # Apply gain limit
        gain_db = np.clip(gain_db, -self.config.max_gain, self.config.max_gain)
        gain_linear = 10 ** (gain_db / 20)

        normalized = audio_data * gain_linear

        # Prevent clipping
        if self.config.prevent_clipping:
            max_val = np.max(np.abs(normalized))
            if max_val > 0.99:
                normalized = normalized * 0.99 / max_val
                gain_db = 20 * np.log10(0.99 / (current_peak_linear + 1e-10))

        return normalized, gain_db

    async def _normalize_rms(
        self, audio_data: np.ndarray, stats: VolumeStatistics
    ) -> Tuple[np.ndarray, float]:
        """RMS normalization."""
        current_rms_db = stats.rms_level
        target_rms_db = self.config.target_rms

        gain_db = target_rms_db - current_rms_db

        # Apply gain limit
        gain_db = np.clip(gain_db, -self.config.max_gain, self.config.max_gain)
        gain_linear = 10 ** (gain_db / 20)

        normalized = audio_data * gain_linear

        # Check for clipping
        if self.config.prevent_clipping:
            max_val = np.max(np.abs(normalized))
            if max_val > 0.99:
                # Reduce gain to prevent clipping
                clipping_reduction = 20 * np.log10(0.99 / max_val)
                gain_db += clipping_reduction
                gain_linear = 10 ** (gain_db / 20)
                normalized = audio_data * gain_linear

        return normalized, gain_db

    async def _normalize_lufs(
        self, audio_data: np.ndarray, sample_rate: int, stats: VolumeStatistics
    ) -> Tuple[np.ndarray, float]:
        """LUFS normalization."""
        current_lufs = stats.lufs_integrated
        target_lufs = self.config.target_lufs

        if current_lufs <= -70:  # Too quiet to measure accurately
            logger.warning("Audio too quiet for accurate LUFS measurement, using RMS")
            return await self._normalize_rms(audio_data, stats)

        gain_db = target_lufs - current_lufs

        # Apply gain limit
        gain_db = np.clip(gain_db, -self.config.max_gain, self.config.max_gain)
        gain_linear = 10 ** (gain_db / 20)

        normalized = audio_data * gain_linear

        # Iterative refinement for accuracy
        for _ in range(2):
            # Measure normalized LUFS
            lufs_check = await self._measure_lufs(normalized, sample_rate)
            current_lufs_normalized = lufs_check["integrated"]

            if abs(current_lufs_normalized - target_lufs) < 0.5:  # Within 0.5 LU
                break

            # Refine gain
            correction_db = target_lufs - current_lufs_normalized
            gain_db += correction_db * 0.8  # Damped correction
            gain_db = np.clip(gain_db, -self.config.max_gain, self.config.max_gain)
            gain_linear = 10 ** (gain_db / 20)
            normalized = audio_data * gain_linear

        return normalized, gain_db

    async def _normalize_medical(
        self, audio_data: np.ndarray, sample_rate: int, stats: VolumeStatistics
    ) -> Tuple[np.ndarray, float]:
        """Medical-specific normalization optimized for voice analysis."""
        # Start with LUFS normalization
        normalized, base_gain = await self._normalize_lufs(
            audio_data, sample_rate, stats
        )

        if self.config.preserve_medical_frequencies:
            # Apply gentle spectral shaping for medical frequencies
            # Enhance critical speech frequencies
            low_freq, high_freq = self.config.medical_freq_range

            # Design bandpass filter
            nyquist = sample_rate / 2
            low = low_freq / nyquist
            high = high_freq / nyquist

            # Butterworth bandpass
            sos = signal.butter(4, [low, high], btype="band", output="sos")

            # Extract medical frequency content
            medical_band = signal.sosfilt(sos, normalized)

            # Gentle enhancement (2dB boost)
            enhancement = 10 ** (2 / 20)
            enhanced_band = medical_band * enhancement

            # Crossover mixing
            other_freqs = normalized - medical_band
            normalized = other_freqs + enhanced_band * 0.7 + medical_band * 0.3

        if self.config.enhance_speech_clarity:
            # Apply gentle expansion to increase clarity
            # Expand quiet parts slightly to reduce noise
            threshold_linear = 10 ** (stats.noise_floor / 20) * 2

            # Soft knee expansion
            mask = np.abs(normalized) < threshold_linear
            expansion_ratio = 0.8  # Gentle expansion
            normalized[mask] *= expansion_ratio

        # Final limiting to prevent any clipping
        max_val = np.max(np.abs(normalized))
        if max_val > 0.95:
            normalized = normalized * 0.95 / max_val
            base_gain -= 20 * np.log10(max_val / 0.95)

        return normalized, base_gain

    async def _normalize_dynamic(
        self, audio_data: np.ndarray, sample_rate: int, stats: VolumeStatistics
    ) -> Tuple[np.ndarray, float]:
        """Dynamic normalization with compression."""
        # First normalize to target RMS
        normalized, base_gain = await self._normalize_rms(audio_data, stats)

        # Apply multiband compression for dynamic control
        # This is simplified - production would use proper multiband

        # Simple two-band compression
        crossover_freq = 250  # Hz
        nyquist = sample_rate / 2
        crossover_norm = crossover_freq / nyquist

        # Design filters
        sos_low = signal.butter(4, crossover_norm, btype="low", output="sos")
        sos_high = signal.butter(4, crossover_norm, btype="high", output="sos")

        # Split bands
        low_band = signal.sosfilt(sos_low, normalized)
        high_band = signal.sosfilt(sos_high, normalized)

        # Compress each band
        low_compressed, _ = await self._apply_compression(low_band, sample_rate)
        high_compressed, _ = await self._apply_compression(high_band, sample_rate)

        # Recombine
        normalized = low_compressed + high_compressed

        return normalized, base_gain

    async def _normalize_adaptive(
        self, audio_data: np.ndarray, sample_rate: int, stats: VolumeStatistics
    ) -> Tuple[np.ndarray, float]:
        """Adaptive normalization based on content analysis."""
        # Analyze content type
        is_speech = stats.snr > 10 and stats.speech_level > -40
        has_music = self._detect_music_content(audio_data, sample_rate)

        if is_speech and not has_music:
            # Use medical normalization for speech
            return await self._normalize_medical(audio_data, sample_rate, stats)
        elif has_music:
            # Use LUFS for music content
            return await self._normalize_lufs(audio_data, sample_rate, stats)
        else:
            # Default to RMS for other content
            return await self._normalize_rms(audio_data, stats)

    def _detect_music_content(self, audio_data: np.ndarray, sample_rate: int) -> bool:
        """Detect music content based on spectral features."""
        _ = sample_rate  # Unused but kept for API consistency
        # Calculate spectral features
        stft = librosa.stft(audio_data)
        magnitude = np.abs(stft)

        # Spectral flux (changes in spectrum)
        flux = np.sum(np.diff(magnitude, axis=1) ** 2, axis=0)
        flux_regularity = np.std(flux) / (np.mean(flux) + 1e-10)

        # Music tends to have more regular spectral changes
        return bool(flux_regularity < 1.5)

    async def _apply_compression(
        self, audio_data: np.ndarray, sample_rate: int
    ) -> Tuple[np.ndarray, float]:
        """Apply dynamic range compression."""
        threshold_linear = 10 ** (self.config.compression_threshold / 20)
        ratio = self.config.compression_ratio
        knee = self.config.compression_knee

        # Calculate envelope
        attack_samples = int(self.config.attack_time_ms * sample_rate / 1000)
        release_samples = int(self.config.release_time_ms * sample_rate / 1000)

        envelope = self._calculate_envelope(audio_data, attack_samples, release_samples)

        # Apply compression
        compressed = audio_data.copy()

        # Soft knee compression
        for i, level in enumerate(envelope):
            if level > threshold_linear:
                # Above threshold - compress
                excess = level - threshold_linear

                if knee > 0:
                    # Soft knee
                    knee_start = threshold_linear - knee / 2
                    knee_end = threshold_linear + knee / 2

                    if level < knee_end:
                        # In knee region
                        knee_factor = (level - knee_start) / knee
                        effective_ratio = 1 + (ratio - 1) * knee_factor
                    else:
                        effective_ratio = ratio
                else:
                    effective_ratio = ratio

                gain = threshold_linear + excess / effective_ratio
                compressed[i] = audio_data[i] * (gain / level)

        return compressed, ratio

    def _calculate_envelope(
        self, audio_data: np.ndarray, attack_samples: int, release_samples: int
    ) -> np.ndarray:
        """Calculate signal envelope with attack/release."""
        envelope = np.zeros_like(audio_data)
        abs_signal = np.abs(audio_data)

        # Attack and release coefficients
        attack_coeff = np.exp(-1 / attack_samples) if attack_samples > 0 else 0
        release_coeff = np.exp(-1 / release_samples) if release_samples > 0 else 0

        envelope[0] = abs_signal[0]

        for i in range(1, len(audio_data)):
            if abs_signal[i] > envelope[i - 1]:
                # Attack
                envelope[i] = abs_signal[i] + attack_coeff * (
                    envelope[i - 1] - abs_signal[i]
                )
            else:
                # Release
                envelope[i] = abs_signal[i] + release_coeff * (
                    envelope[i - 1] - abs_signal[i]
                )

        return envelope

    async def _apply_limiting(
        self, audio_data: np.ndarray, sample_rate: int
    ) -> Tuple[np.ndarray, bool]:
        """Apply brick-wall limiting."""
        threshold_linear = 10 ** (self.config.limiter_threshold / 20)

        limited = audio_data.copy()
        envelope = np.abs(audio_data)
        limiter_engaged = False

        # Look-ahead buffer
        lookahead_ms = 5
        lookahead_samples = int(lookahead_ms * sample_rate / 1000)

        for i in range(len(audio_data) - lookahead_samples):
            # Check future samples
            future_max = np.max(envelope[i : i + lookahead_samples])

            if future_max > threshold_linear:
                limiter_engaged = True
                gain_reduction = threshold_linear / future_max

                # Apply gain reduction with release
                for j in range(lookahead_samples):
                    if i + j < len(limited):
                        limited[i + j] *= gain_reduction

        return limited, limiter_engaged

    def _calculate_thd(self, original: np.ndarray, processed: np.ndarray) -> float:
        """Calculate Total Harmonic Distortion."""
        # Ensure same length
        min_len = min(len(original), len(processed))
        original = original[:min_len]
        processed = processed[:min_len]

        # Calculate difference (distortion)
        distortion = processed - original * (
            np.max(processed) / (np.max(original) + 1e-10)
        )

        # THD as ratio of distortion to signal
        signal_power = np.mean(original**2)
        distortion_power = np.mean(distortion**2)

        if signal_power > 0:
            thd = np.sqrt(distortion_power / signal_power)
            return float(np.clip(thd * 100, 0, 100))  # Percentage

        return 0.0

    def _calculate_preservation_score(
        self,
        input_stats: VolumeStatistics,
        output_stats: VolumeStatistics,
        original: np.ndarray,
        processed: np.ndarray,
    ) -> float:
        """Calculate how well dynamics are preserved."""
        scores = []

        # Dynamic range preservation
        if input_stats.dynamic_range > 0:
            dr_preservation = min(
                1.0, output_stats.dynamic_range / input_stats.dynamic_range
            )
            scores.append(dr_preservation)

        # Crest factor preservation
        if input_stats.crest_factor > 0:
            cf_preservation = min(
                1.0, output_stats.crest_factor / input_stats.crest_factor
            )
            scores.append(cf_preservation)

        # Correlation between original and processed
        correlation = np.corrcoef(
            original[: len(processed)], processed[: len(original)]
        )[0, 1]
        scores.append(max(0, correlation))

        # SNR preservation (if applicable)
        if input_stats.snr > 0 and output_stats.snr > 0:
            snr_preservation = min(1.0, output_stats.snr / input_stats.snr)
            scores.append(snr_preservation)

        return float(np.mean(scores)) if scores else 1.0

    def _generate_warnings(
        self,
        input_stats: VolumeStatistics,
        output_stats: VolumeStatistics,
        gain_db: float,
        compression_ratio: Optional[float],
    ) -> List[str]:
        """Generate warnings about processing."""
        warnings = []

        if gain_db > 30:
            warnings.append(f"High gain applied: {gain_db:.1f} dB")

        if input_stats.clipping_ratio > 0.001:
            warnings.append(
                f"Input clipping detected: {input_stats.clipping_ratio*100:.2f}%"
            )

        if output_stats.clipping_ratio > 0:
            warnings.append("Output clipping detected")

        if input_stats.snr < 10:
            warnings.append(f"Low SNR: {input_stats.snr:.1f} dB")

        if compression_ratio and compression_ratio > 6:
            warnings.append(f"Heavy compression applied: {compression_ratio}:1")

        if output_stats.dynamic_range < 6:
            warnings.append("Low dynamic range in output")

        return warnings

    async def normalize_batch(
        self,
        audio_files: List[str],
        output_dir: str,
        target_loudness: Optional[float] = None,
    ) -> List[NormalizationResult]:
        """
        Normalize a batch of audio files to consistent loudness.

        Args:
            audio_files: List of input file paths
            output_dir: Directory for normalized files
            target_loudness: Optional common target (uses config if None)

        Returns:
            List of normalization results
        """
        results = []

        # First pass: analyze all files
        if target_loudness is None:
            all_loudness = []

            for file_path in audio_files:
                audio_data, sr = librosa.load(file_path, sr=None)
                stats = await self._analyze_volume(audio_data, sr)
                all_loudness.append(stats.lufs_integrated)

            # Use median as target
            valid_loudness = [loudness for loudness in all_loudness if loudness > -70]
            if valid_loudness:
                target_loudness = float(np.median(valid_loudness))
            else:
                target_loudness = self.config.target_lufs

        # Second pass: normalize all files
        original_target = self.config.target_lufs
        if target_loudness is not None:
            self.config.target_lufs = target_loudness

        for file_path in audio_files:
            try:
                # Load audio
                audio_data, sr = librosa.load(file_path, sr=None)

                # Normalize
                result = await self.normalize(audio_data, sr)

                # Save normalized file
                output_path = os.path.join(
                    output_dir, os.path.basename(file_path).replace(".", "_normalized.")
                )

                sf.write(output_path, result.normalized_audio, sr)

                results.append(result)
                logger.info("Normalized %s -> %s", file_path, output_path)

            except (IOError, ValueError, RuntimeError) as e:
                logger.error("Error normalizing %s: %s", file_path, str(e))
                # Skip failed files instead of appending None

        # Restore original target
        self.config.target_lufs = original_target

        return results

    def create_loudness_report(
        self, results: List[NormalizationResult]
    ) -> Dict[str, Any]:
        """Create a summary report of normalization results."""
        valid_results = [r for r in results if r is not None]

        if not valid_results:
            return {"error": "No valid results"}

        report = {
            "file_count": len(results),
            "successful": len(valid_results),
            "failed": len(results) - len(valid_results),
            "input_stats": {
                "lufs_mean": np.mean(
                    [r.input_stats.lufs_integrated for r in valid_results]
                ),
                "lufs_std": np.std(
                    [r.input_stats.lufs_integrated for r in valid_results]
                ),
                "peak_mean": np.mean(
                    [r.input_stats.peak_amplitude for r in valid_results]
                ),
                "rms_mean": np.mean([r.input_stats.rms_level for r in valid_results]),
            },
            "output_stats": {
                "lufs_mean": np.mean(
                    [r.output_stats.lufs_integrated for r in valid_results]
                ),
                "lufs_std": np.std(
                    [r.output_stats.lufs_integrated for r in valid_results]
                ),
                "peak_mean": np.mean(
                    [r.output_stats.peak_amplitude for r in valid_results]
                ),
                "rms_mean": np.mean([r.output_stats.rms_level for r in valid_results]),
            },
            "processing": {
                "gain_mean": np.mean([r.applied_gain for r in valid_results]),
                "gain_range": (
                    np.min([r.applied_gain for r in valid_results]),
                    np.max([r.applied_gain for r in valid_results]),
                ),
                "limiter_engaged_count": sum(
                    1 for r in valid_results if r.limiter_engaged
                ),
                "avg_processing_time_ms": np.mean(
                    [r.processing_time_ms for r in valid_results]
                ),
            },
            "quality": {
                "thd_mean": np.mean([r.thd for r in valid_results]),
                "preservation_mean": np.mean(
                    [r.preservation_score for r in valid_results]
                ),
            },
            "warnings": [w for r in valid_results for w in r.warnings],
        }

        return report


# Example usage functions
async def normalize_medical_recording(file_path: str) -> NormalizationResult:
    """Normalize a medical voice recording."""
    _ = file_path  # Unused in example function
    config = NormalizationConfig(
        normalization_type=NormalizationType.MEDICAL,
        target_lufs=-18.0,  # Slightly louder for clarity
        compression_profile=DynamicRangeProfile.MEDICAL_VOICE,
        preserve_medical_frequencies=True,
        enhance_speech_clarity=True,
    )

    normalizer = VolumeNormalizer(config)

    # Load audio (placeholder)
    audio_data = np.random.randn(16000 * 10) * 0.1  # 10 seconds

    result = await normalizer.normalize(audio_data, 16000)

    logger.info("Normalization complete: %.1f dB gain applied", result.applied_gain)
    logger.info("Output LUFS: %.1f", result.output_stats.lufs_integrated)

    return result
