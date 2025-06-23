"""Noise Detection Module.

This module provides functionality for detecting and analyzing
noise in medical audio recordings.

Security Note: This module processes audio data that may contain PHI.
All audio analysis and noise detection must be performed with encryption
at rest and in transit. Access to audio processing functionality should
be restricted to authorized healthcare personnel only through role-based
access controls.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, cast

import numpy as np

from .noise_profile import NoiseCharacteristics, NoiseLevel, NoiseProfile, NoiseType

logger = logging.getLogger(__name__)


@dataclass
class SpectralAnalysis:
    """Results of spectral analysis for noise detection."""

    frequency_bins: np.ndarray = field(default_factory=lambda: np.array([]))
    power_spectrum: np.ndarray = field(default_factory=lambda: np.array([]))
    spectral_centroid: float = 0.0
    spectral_rolloff: float = 0.0
    spectral_flux: float = 0.0
    zero_crossing_rate: float = 0.0

    # Frequency band energies
    low_freq_energy: float = 0.0  # 0-250 Hz
    mid_freq_energy: float = 0.0  # 250-2000 Hz
    high_freq_energy: float = 0.0  # 2000-8000 Hz

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "spectral_centroid": self.spectral_centroid,
            "spectral_rolloff": self.spectral_rolloff,
            "spectral_flux": self.spectral_flux,
            "zero_crossing_rate": self.zero_crossing_rate,
            "low_freq_energy": self.low_freq_energy,
            "mid_freq_energy": self.mid_freq_energy,
            "high_freq_energy": self.high_freq_energy,
        }


@dataclass
class NoiseDetectionResult:
    """Results of noise detection analysis."""

    noise_profiles: List[NoiseProfile] = field(default_factory=list)
    overall_noise_level: NoiseLevel = NoiseLevel.LOW
    signal_to_noise_ratio: float = 0.0
    spectral_analysis: Optional[SpectralAnalysis] = None
    confidence_score: float = 0.0
    processing_time_ms: float = 0.0
    recommendations: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "noise_profiles": [p.to_dict() for p in self.noise_profiles],
            "overall_noise_level": self.overall_noise_level.value,
            "signal_to_noise_ratio": self.signal_to_noise_ratio,
            "spectral_analysis": (
                self.spectral_analysis.to_dict() if self.spectral_analysis else None
            ),
            "confidence_score": self.confidence_score,
            "processing_time_ms": self.processing_time_ms,
            "recommendations": self.recommendations,
        }


class NoiseDetector:
    """
    Detects and analyzes various types of noise in medical audio recordings.

    This class implements advanced noise detection algorithms specifically
    tuned for medical environments and voice recordings.
    """

    def __init__(
        self,
        sample_rate: int = 16000,
        frame_size: int = 512,
        hop_length: int = 256,
        n_fft: int = 1024,
        enable_gpu: bool = False,
    ):
        """
        Initialize the noise detector.

        Args:
            sample_rate: Audio sample rate in Hz
            frame_size: Size of analysis frames
            hop_length: Number of samples between frames
            n_fft: FFT size for spectral analysis
            enable_gpu: Whether to use GPU acceleration if available
        """
        self.sample_rate = sample_rate
        self.frame_size = frame_size
        self.hop_length = hop_length
        self.n_fft = n_fft
        self.enable_gpu = enable_gpu

        # Frequency bins for analysis
        self.frequency_bins = np.fft.fftfreq(n_fft, 1.0 / sample_rate)[: n_fft // 2]

        # Noise thresholds (in dB)
        self.noise_thresholds = {
            NoiseLevel.LOW: -40,
            NoiseLevel.MODERATE: -30,
            NoiseLevel.HIGH: -20,
            NoiseLevel.VERY_HIGH: -10,
        }

        # Frequency band definitions (Hz)
        self.frequency_bands = {
            "low": (0, 250),  # Environmental noise, HVAC
            "mid": (250, 2000),  # Speech range
            "high": (2000, 8000),  # High frequency noise
            "ultrasonic": (8000, sample_rate // 2),  # Electronic interference
        }

        logger.info(
            "NoiseDetector initialized with sample_rate=%dHz, n_fft=%d, GPU=%s",
            sample_rate,
            n_fft,
            "enabled" if enable_gpu else "disabled",
        )

    async def detect_noise(
        self, audio_data: np.ndarray, reference_noise: Optional[np.ndarray] = None
    ) -> NoiseDetectionResult:
        """
        Detect and analyze noise in audio data.

        Args:
            audio_data: Audio signal as numpy array
            reference_noise: Optional reference noise profile for comparison

        Returns:
            NoiseDetectionResult with detailed noise analysis
        """
        start_time = datetime.now()

        try:
            # Normalize audio data
            audio_data = self._normalize_audio(audio_data)

            # Perform spectral analysis
            spectral_analysis = await self._analyze_spectrum(audio_data)

            # Detect specific noise types
            noise_profiles = await self._detect_noise_types(
                audio_data, spectral_analysis
            )

            # Calculate overall metrics
            snr = self._calculate_snr(audio_data, reference_noise)
            overall_level = self._determine_overall_level(noise_profiles, snr)

            # Generate recommendations
            recommendations = self._generate_recommendations(
                noise_profiles, overall_level
            )

            # Calculate confidence score
            confidence = self._calculate_confidence(spectral_analysis, noise_profiles)

            # Calculate processing time
            processing_time = (datetime.now() - start_time).total_seconds() * 1000

            return NoiseDetectionResult(
                noise_profiles=noise_profiles,
                overall_noise_level=overall_level,
                signal_to_noise_ratio=snr,
                spectral_analysis=spectral_analysis,
                confidence_score=confidence,
                processing_time_ms=processing_time,
                recommendations=recommendations,
            )

        except Exception as e:
            logger.error("Error in noise detection: %s", str(e), exc_info=True)
            raise

    def _normalize_audio(self, audio_data: np.ndarray) -> np.ndarray:
        """Normalize audio data to [-1, 1] range."""
        max_val = np.max(np.abs(audio_data))
        if max_val > 0:
            normalized: np.ndarray = audio_data / max_val
            return normalized
        return audio_data

    async def _analyze_spectrum(self, audio_data: np.ndarray) -> SpectralAnalysis:
        """Perform spectral analysis on audio data."""
        # Compute FFT
        fft_result = np.fft.rfft(audio_data, n=self.n_fft)
        power_spectrum = np.abs(fft_result) ** 2

        # Calculate spectral features
        spectral_centroid = self._calculate_spectral_centroid(power_spectrum)
        spectral_rolloff = self._calculate_spectral_rolloff(power_spectrum)
        spectral_flux = self._calculate_spectral_flux(audio_data)
        zcr = self._calculate_zero_crossing_rate(audio_data)

        # Calculate band energies
        low_energy = self._calculate_band_energy(
            power_spectrum, *self.frequency_bands["low"]
        )
        mid_energy = self._calculate_band_energy(
            power_spectrum, *self.frequency_bands["mid"]
        )
        high_energy = self._calculate_band_energy(
            power_spectrum, *self.frequency_bands["high"]
        )

        return SpectralAnalysis(
            frequency_bins=self.frequency_bins,
            power_spectrum=power_spectrum,
            spectral_centroid=spectral_centroid,
            spectral_rolloff=spectral_rolloff,
            spectral_flux=spectral_flux,
            zero_crossing_rate=zcr,
            low_freq_energy=low_energy,
            mid_freq_energy=mid_energy,
            high_freq_energy=high_energy,
        )

    async def _detect_noise_types(
        self, audio_data: np.ndarray, spectral_analysis: SpectralAnalysis
    ) -> List[NoiseProfile]:
        """Detect specific types of noise in the audio."""
        noise_profiles = []

        # Detect background noise
        if spectral_analysis.low_freq_energy > 0.3:
            noise_profiles.append(
                NoiseProfile(
                    noise_type=NoiseType.AMBIENT,
                    noise_level=self._energy_to_level(
                        spectral_analysis.low_freq_energy
                    ),
                    characteristics=NoiseCharacteristics(
                        frequency_range=(0, 250),
                        typical_duration=(0, len(audio_data) / self.sample_rate),
                        is_continuous=True,
                    ),
                )
            )

        # Detect electrical interference
        if self._detect_electrical_noise(spectral_analysis.power_spectrum):
            noise_profiles.append(
                NoiseProfile(
                    noise_type=NoiseType.INTERFERENCE,
                    noise_level=NoiseLevel.MODERATE,
                    characteristics=NoiseCharacteristics(
                        frequency_range=(50, 60),  # Power line frequency
                        is_periodic=True,
                        spectral_shape="narrowband",
                    ),
                )
            )

        # Detect white noise
        if self._is_white_noise(spectral_analysis):
            noise_profiles.append(
                NoiseProfile(
                    noise_type=NoiseType.WHITE_NOISE,
                    noise_level=self._energy_to_level(
                        np.mean(spectral_analysis.power_spectrum)
                    ),
                    characteristics=NoiseCharacteristics(
                        frequency_range=(0, self.sample_rate // 2),
                        is_continuous=True,
                        spectral_shape="broadband",
                    ),
                )
            )

        # Detect impulse noise
        impulse_locations = self._detect_impulse_noise(audio_data)
        if impulse_locations:
            noise_profiles.append(
                NoiseProfile(
                    noise_type=NoiseType.MONITOR_BEEPS,
                    noise_level=NoiseLevel.HIGH,
                    characteristics=NoiseCharacteristics(
                        is_impulsive=True, is_continuous=False
                    ),
                )
            )

        return noise_profiles

    def _calculate_spectral_centroid(self, power_spectrum: np.ndarray) -> float:
        """Calculate the spectral centroid (center of mass of spectrum)."""
        magnitudes = np.abs(power_spectrum)
        freqs = self.frequency_bins[: len(power_spectrum)]

        if np.sum(magnitudes) == 0:
            return 0.0

        return float(np.sum(freqs * magnitudes) / np.sum(magnitudes))

    def _calculate_spectral_rolloff(
        self, power_spectrum: np.ndarray, threshold: float = 0.85
    ) -> float:
        """Calculate frequency below which threshold% of energy is contained."""
        total_energy = np.sum(power_spectrum)
        cumulative_energy = np.cumsum(power_spectrum)

        rolloff_idx = np.where(cumulative_energy >= threshold * total_energy)[0]

        if len(rolloff_idx) > 0:
            return float(self.frequency_bins[rolloff_idx[0]])
        return 0.0

    def _calculate_spectral_flux(self, audio_data: np.ndarray) -> float:
        """Calculate spectral flux (measure of spectral change)."""
        frames = self._frame_audio(audio_data)
        flux_values = []

        prev_spectrum = None
        for frame in frames:
            spectrum = np.abs(np.fft.rfft(frame, n=self.n_fft))

            if prev_spectrum is not None:
                flux = np.sum((spectrum - prev_spectrum) ** 2)
                flux_values.append(flux)

            prev_spectrum = spectrum

        return np.mean(flux_values) if flux_values else 0.0

    def _calculate_zero_crossing_rate(self, audio_data: np.ndarray) -> float:
        """Calculate zero crossing rate of the signal."""
        signs = np.sign(audio_data)
        signs[signs == 0] = 1

        zero_crossings = np.sum(np.abs(np.diff(signs))) / 2
        return float(zero_crossings / len(audio_data))

    def _calculate_band_energy(
        self, power_spectrum: np.ndarray, low_freq: float, high_freq: float
    ) -> float:
        """Calculate energy in a specific frequency band."""
        freq_mask = (self.frequency_bins[: len(power_spectrum)] >= low_freq) & (
            self.frequency_bins[: len(power_spectrum)] <= high_freq
        )

        band_energy = np.sum(power_spectrum[freq_mask])
        total_energy = np.sum(power_spectrum)

        return band_energy / total_energy if total_energy > 0 else 0.0

    def _detect_electrical_noise(self, power_spectrum: np.ndarray) -> bool:
        """Detect electrical interference (50/60 Hz and harmonics)."""
        power_line_freqs = [50, 60, 100, 120, 150, 180]  # Fundamental and harmonics

        for freq in power_line_freqs:
            freq_idx = int(freq * len(power_spectrum) / (self.sample_rate / 2))
            if freq_idx < len(power_spectrum):
                # Check for peaks at power line frequencies
                if power_spectrum[freq_idx] > np.mean(power_spectrum) * 5:
                    return True

        return False

    def _is_white_noise(self, spectral_analysis: SpectralAnalysis) -> bool:
        """Detect if the signal contains white noise."""
        # White noise has relatively uniform power across frequencies
        uniformity = self._calculate_spectral_uniformity(spectral_analysis)
        return uniformity > 0.8

    def _calculate_spectral_uniformity(
        self, spectral_analysis: SpectralAnalysis
    ) -> float:
        """Calculate how uniform the power spectrum is (0-1)."""
        power = spectral_analysis.power_spectrum
        if len(power) == 0:
            return 0.0

        mean_power = np.mean(power)
        std_power = np.std(power)

        # Coefficient of variation (lower means more uniform)
        cv = std_power / mean_power if mean_power > 0 else 1.0

        # Convert to uniformity score (0-1)
        uniformity = 1.0 / (1.0 + cv)
        return uniformity

    def _detect_impulse_noise(
        self, audio_data: np.ndarray, threshold: float = 3.0
    ) -> List[int]:
        """Detect impulse noise (clicks, pops) in the signal."""
        # Calculate local energy
        frames = self._frame_audio(audio_data)
        energies = np.array([np.sum(frame**2) for frame in frames])

        # Find outliers (potential impulses)
        mean_energy = np.mean(energies)
        std_energy = np.std(energies)

        impulse_indices = np.where(energies > mean_energy + threshold * std_energy)[0]

        return cast(List[int], impulse_indices.tolist())

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

    def _calculate_snr(
        self, audio_data: np.ndarray, reference_noise: Optional[np.ndarray]
    ) -> float:
        """Calculate signal-to-noise ratio in dB."""
        signal_power = np.mean(audio_data**2)

        if reference_noise is not None:
            noise_power = np.mean(reference_noise**2)
        else:
            # Estimate noise from quietest 10% of frames
            frames = self._frame_audio(audio_data)
            frame_powers = [np.mean(frame**2) for frame in frames]
            sorted_powers = sorted(frame_powers)

            # Use bottom 10% as noise estimate
            noise_frames_count = max(1, len(sorted_powers) // 10)
            noise_power = np.mean(sorted_powers[:noise_frames_count])

        if noise_power > 0:
            snr = 10 * np.log10(signal_power / noise_power)
            return float(snr)

        return float("inf")  # No noise detected

    def _energy_to_level(self, energy: float) -> NoiseLevel:
        """Convert energy value to noise level."""
        if energy < 0.1:
            return NoiseLevel.LOW
        elif energy < 0.3:
            return NoiseLevel.MODERATE
        elif energy < 0.6:
            return NoiseLevel.HIGH
        else:
            return NoiseLevel.VERY_HIGH

    def _determine_overall_level(
        self, noise_profiles: List[NoiseProfile], snr: float
    ) -> NoiseLevel:
        """Determine overall noise level from individual profiles and SNR."""
        if not noise_profiles:
            return NoiseLevel.LOW

        # Get maximum noise level from profiles
        # Note: Assuming NoiseProfile has a noise_type attribute
        # If it has level, use profile.level instead
        max_level = NoiseLevel.LOW
        for profile in noise_profiles:
            # TODO: Update when NoiseProfile structure is defined
            if hasattr(profile, "level"):
                if profile.level.value > max_level.value:
                    max_level = profile.level

        # Adjust based on SNR
        if snr < 10:  # Poor SNR
            return NoiseLevel.VERY_HIGH
        elif snr < 20:  # Fair SNR
            return (
                NoiseLevel.HIGH
                if NoiseLevel.HIGH.value > max_level.value
                else max_level
            )
        elif snr < 30:  # Good SNR
            return (
                NoiseLevel.MODERATE
                if NoiseLevel.MODERATE.value > max_level.value
                else max_level
            )
        else:  # Excellent SNR
            return max_level

    def _generate_recommendations(
        self, noise_profiles: List[NoiseProfile], overall_level: NoiseLevel
    ) -> List[str]:
        """Generate recommendations based on detected noise."""
        recommendations = []

        # Overall level recommendations
        if overall_level == NoiseLevel.VERY_HIGH:
            recommendations.append(
                "Recording environment has severe noise. Consider finding a quieter location."
            )
        elif overall_level == NoiseLevel.HIGH:
            recommendations.append(
                "High noise levels detected. Audio enhancement recommended."
            )

        # Specific noise type recommendations
        noise_types = {profile.noise_type for profile in noise_profiles}

        if NoiseType.BACKGROUND in noise_types:
            recommendations.append(
                "Background noise detected. Use directional microphone or noise-canceling headset."
            )

        if NoiseType.ELECTRICAL in noise_types:
            recommendations.append(
                "Electrical interference detected. Check microphone shielding and grounding."
            )

        if NoiseType.WIND in noise_types:
            recommendations.append(
                "Wind noise detected. Use windscreen or record in sheltered location."
            )

        if NoiseType.ECHO in noise_types:
            recommendations.append(
                "Echo/reverb detected. Add sound absorption materials or move to smaller room."
            )

        if NoiseType.IMPULSE in noise_types:
            recommendations.append(
                "Clicking/popping detected. Check microphone connection and handling."
            )

        return recommendations

    def _calculate_confidence(
        self, spectral_analysis: SpectralAnalysis, noise_profiles: List[NoiseProfile]
    ) -> float:
        """Calculate confidence score for the noise detection results."""
        confidence_factors = []

        # Factor 1: Spectral clarity (how well-defined the spectrum is)
        if len(spectral_analysis.power_spectrum) > 0:
            spectral_entropy = self._calculate_spectral_entropy(
                spectral_analysis.power_spectrum
            )
            clarity_score = 1.0 - spectral_entropy
            confidence_factors.append(clarity_score)

        # Factor 2: Consistency of detected noise types
        if noise_profiles:
            # More consistent detections = higher confidence
            consistency_score = 1.0 / (
                1.0 + len(set(p.noise_type for p in noise_profiles))
            )
            confidence_factors.append(consistency_score)

        # Factor 3: Signal strength
        signal_strength = np.mean(np.abs(spectral_analysis.power_spectrum))
        strength_score = min(1.0, signal_strength / 0.1)  # Normalize to 0-1
        confidence_factors.append(strength_score)

        # Calculate overall confidence
        if confidence_factors:
            return float(np.mean(confidence_factors))

        return 0.5  # Default medium confidence

    def _calculate_spectral_entropy(self, power_spectrum: np.ndarray) -> float:
        """Calculate spectral entropy (measure of spectral complexity)."""
        # Normalize power spectrum to probability distribution
        power_sum = np.sum(power_spectrum)
        if power_sum == 0:
            return 1.0

        prob_dist = power_spectrum / power_sum

        # Calculate entropy
        entropy = -np.sum(prob_dist * np.log2(prob_dist + 1e-10))

        # Normalize to 0-1 range
        max_entropy = np.log2(len(power_spectrum))
        normalized_entropy = entropy / max_entropy if max_entropy > 0 else 0

        return normalized_entropy

    async def create_noise_profile(
        self, audio_samples: List[np.ndarray], profile_name: str = "custom"
    ) -> Dict[str, Any]:
        """
        Create a noise profile from multiple audio samples.

        Args:
            audio_samples: List of audio samples containing noise
            profile_name: Name for the noise profile

        Returns:
            Dictionary containing the noise profile data
        """
        logger.info(
            "Creating noise profile '%s' from %d samples",
            profile_name,
            len(audio_samples),
        )

        # Analyze each sample
        all_spectra = []
        all_features = []

        for sample in audio_samples:
            spectral_analysis = await self._analyze_spectrum(sample)
            all_spectra.append(spectral_analysis.power_spectrum)
            all_features.append(spectral_analysis.to_dict())

        # Average the spectra
        avg_spectrum = np.mean(all_spectra, axis=0)

        # Calculate average features
        avg_features = {}
        for key in all_features[0].keys():
            values = [f[key] for f in all_features]
            avg_features[key] = np.mean(values)

        # Create profile
        profile = {
            "name": profile_name,
            "created_at": datetime.now().isoformat(),
            "sample_count": len(audio_samples),
            "sample_rate": self.sample_rate,
            "average_spectrum": avg_spectrum.tolist(),
            "frequency_bins": self.frequency_bins.tolist(),
            "features": avg_features,
            "statistics": {
                "mean_power": float(np.mean(avg_spectrum)),
                "std_power": float(np.std(avg_spectrum)),
                "peak_frequency": float(self.frequency_bins[np.argmax(avg_spectrum)]),
            },
        }

        return profile

    def apply_noise_profile(
        self, current_spectrum: np.ndarray, noise_profile: Dict[str, Any]
    ) -> np.ndarray:
        """
        Apply a noise profile for spectral subtraction.

        Args:
            current_spectrum: Current power spectrum
            noise_profile: Noise profile to subtract

        Returns:
            Noise-reduced spectrum
        """
        # Get noise spectrum from profile
        noise_spectrum = np.array(noise_profile["average_spectrum"])

        # Ensure matching dimensions
        min_len = min(len(current_spectrum), len(noise_spectrum))
        current_spectrum = current_spectrum[:min_len]
        noise_spectrum = noise_spectrum[:min_len]

        # Spectral subtraction with over-subtraction factor
        alpha = 2.0  # Over-subtraction factor
        reduced_spectrum = current_spectrum - alpha * noise_spectrum

        # Apply spectral floor to prevent over-subtraction
        spectral_floor = 0.1 * noise_spectrum
        reduced_spectrum = np.maximum(reduced_spectrum, spectral_floor)

        return reduced_spectrum
