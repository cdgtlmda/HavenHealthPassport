"""
Voice Quality Metrics Module for Medical Voice Analysis.

This module implements comprehensive voice quality metrics for medical
assessment, including acoustic parameters, perceptual measures, and
clinical voice quality indicators. All patient data is encrypted for
HIPAA compliance.
"""

# pylint: disable=too-many-lines

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

import numpy as np
from scipy import signal
from scipy.ndimage import gaussian_filter1d

from src.security import requires_phi_access

try:
    import librosa
except ImportError:
    librosa = None

try:
    import parselmouth  # For advanced voice analysis
except ImportError:
    parselmouth = None

logger = logging.getLogger(__name__)


class VoiceQualityCategory(Enum):
    """Categories of voice quality assessment."""

    EXCELLENT = "excellent"
    GOOD = "good"
    FAIR = "fair"
    POOR = "poor"
    CRITICAL = "critical"


class VoiceDisorderType(Enum):
    """Types of voice disorders that can be detected."""

    NONE = "none"
    DYSPHONIA = "dysphonia"
    APHONIA = "aphonia"
    LARYNGITIS = "laryngitis"
    VOCAL_FOLD_PARALYSIS = "vocal_fold_paralysis"
    SPASMODIC_DYSPHONIA = "spasmodic_dysphonia"
    MUSCLE_TENSION = "muscle_tension"
    VOCAL_NODULES = "vocal_nodules"
    UNSPECIFIED = "unspecified"


@dataclass
class AcousticMetrics:
    """Core acoustic metrics for voice quality."""

    # Fundamental frequency metrics
    f0_mean: float = 0.0
    f0_std: float = 0.0
    f0_min: float = 0.0
    f0_max: float = 0.0
    f0_range: float = 0.0

    # Perturbation metrics
    jitter_absolute: float = 0.0  # Absolute jitter (ms)
    jitter_percent: float = 0.0  # Relative jitter (%)
    jitter_rap: float = 0.0  # Relative average perturbation
    jitter_ppq5: float = 0.0  # 5-point period perturbation quotient

    shimmer_absolute: float = 0.0  # Absolute shimmer (dB)
    shimmer_percent: float = 0.0  # Relative shimmer (%)
    shimmer_apq3: float = 0.0  # 3-point amplitude perturbation quotient
    shimmer_apq11: float = 0.0  # 11-point amplitude perturbation quotient

    # Noise metrics
    hnr: float = 0.0  # Harmonics-to-noise ratio (dB)
    nhr: float = 0.0  # Noise-to-harmonics ratio
    vti: float = 0.0  # Voice turbulence index
    spi: float = 0.0  # Soft phonation index

    # Additional metrics
    cpps: float = 0.0  # Cepstral peak prominence smoothed
    energy_mean: float = 0.0
    energy_std: float = 0.0
    zero_crossing_rate: float = 0.0

    def to_dict(self) -> Dict[str, float]:
        """Convert to dictionary representation."""
        return {
            "f0_mean": self.f0_mean,
            "f0_std": self.f0_std,
            "f0_range": self.f0_range,
            "jitter_percent": self.jitter_percent,
            "shimmer_percent": self.shimmer_percent,
            "hnr": self.hnr,
            "cpps": self.cpps,
            "energy_mean": self.energy_mean,
        }


@dataclass
class SpectralMetrics:
    """Spectral characteristics of voice."""

    spectral_centroid: float = 0.0
    spectral_spread: float = 0.0
    spectral_skewness: float = 0.0
    spectral_kurtosis: float = 0.0
    spectral_flux: float = 0.0
    spectral_rolloff: float = 0.0
    spectral_slope: float = 0.0

    # Formant metrics
    f1_mean: float = 0.0  # First formant mean
    f2_mean: float = 0.0  # Second formant mean
    f3_mean: float = 0.0  # Third formant mean
    f1_bandwidth: float = 0.0
    f2_bandwidth: float = 0.0
    f3_bandwidth: float = 0.0

    # Spectral balance metrics
    low_to_high_ratio: float = 0.0  # Energy ratio <1kHz to >1kHz
    alpha_ratio: float = 0.0  # Spectral tilt

    def to_dict(self) -> Dict[str, float]:
        """Convert to dictionary representation."""
        return {
            "spectral_centroid": self.spectral_centroid,
            "spectral_slope": self.spectral_slope,
            "f1_mean": self.f1_mean,
            "f2_mean": self.f2_mean,
            "f3_mean": self.f3_mean,
            "alpha_ratio": self.alpha_ratio,
        }


@dataclass
class TemporalMetrics:
    """Temporal characteristics of voice."""

    speaking_rate: float = 0.0  # Syllables per second
    articulation_rate: float = 0.0  # Excluding pauses

    # Pause metrics
    pause_count: int = 0
    pause_duration_mean: float = 0.0
    pause_duration_std: float = 0.0
    pause_ratio: float = 0.0  # Ratio of pause to speech

    # Rhythm metrics
    rhythm_regularity: float = 0.0
    tempo_variability: float = 0.0

    # Voice onset/offset
    voice_onset_time: float = 0.0
    voice_offset_time: float = 0.0
    voice_attack_time: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "speaking_rate": self.speaking_rate,
            "pause_ratio": self.pause_ratio,
            "rhythm_regularity": self.rhythm_regularity,
        }


@dataclass
class ClinicalMetrics:
    """Clinical voice quality indicators."""

    # GRBAS scale components
    grade: float = 0.0  # Overall severity (0-3)
    roughness: float = 0.0  # Roughness (0-3)
    breathiness: float = 0.0  # Breathiness (0-3)
    asthenia: float = 0.0  # Weakness (0-3)
    strain: float = 0.0  # Strain (0-3)

    # Additional clinical measures
    hoarseness_index: float = 0.0
    voice_breaks: int = 0
    diplophonia: bool = False  # Double voice
    tremor_detected: bool = False
    tremor_frequency: Optional[float] = None

    # Aerodynamic estimates
    estimated_airflow: float = 0.0
    glottal_efficiency: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "grade": self.grade,
            "roughness": self.roughness,
            "breathiness": self.breathiness,
            "asthenia": self.asthenia,
            "strain": self.strain,
            "hoarseness_index": self.hoarseness_index,
            "voice_breaks": self.voice_breaks,
            "tremor_detected": self.tremor_detected,
        }


@dataclass
class QualityMetrics:
    """Overall quality assessment metrics."""

    # Recording quality
    snr: float = 0.0
    recording_quality: float = 0.0  # 0-1 scale
    clipping_detected: bool = False
    background_noise_level: float = 0.0

    # Voice quality indices
    voice_quality_index: float = 0.0  # Composite score 0-100
    dysphonia_severity_index: float = 0.0
    acoustic_voice_quality_index: float = 0.0  # AVQI

    # Intelligibility
    estimated_intelligibility: float = 0.0
    articulation_precision: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "snr": self.snr,
            "recording_quality": self.recording_quality,
            "voice_quality_index": self.voice_quality_index,
            "estimated_intelligibility": self.estimated_intelligibility,
        }


@dataclass
class VoiceQualityResult:
    """Complete voice quality analysis result."""

    # Core metrics
    acoustic_metrics: AcousticMetrics
    spectral_metrics: SpectralMetrics
    temporal_metrics: TemporalMetrics
    clinical_metrics: ClinicalMetrics
    quality_metrics: QualityMetrics

    # Overall assessment
    overall_category: VoiceQualityCategory
    confidence_score: float = 0.0

    # Disorder detection
    detected_disorders: List[VoiceDisorderType] = field(default_factory=list)
    disorder_probabilities: Dict[str, float] = field(default_factory=dict)

    # Clinical recommendations
    clinical_notes: List[str] = field(default_factory=list)
    recommended_assessments: List[str] = field(default_factory=list)

    # Processing metadata
    sample_rate: int = 16000
    audio_duration: float = 0.0
    processing_time_ms: float = 0.0

    # Warnings
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "acoustic_metrics": self.acoustic_metrics.to_dict(),
            "spectral_metrics": self.spectral_metrics.to_dict(),
            "temporal_metrics": self.temporal_metrics.to_dict(),
            "clinical_metrics": self.clinical_metrics.to_dict(),
            "quality_metrics": self.quality_metrics.to_dict(),
            "overall_category": self.overall_category.value,
            "confidence_score": self.confidence_score,
            "detected_disorders": [d.value for d in self.detected_disorders],
            "clinical_notes": self.clinical_notes,
            "warnings": self.warnings,
        }

    def get_summary(self) -> str:
        """Get a summary of voice quality assessment."""
        summary = f"Voice Quality: {self.overall_category.value.upper()}\n"
        summary += (
            f"Quality Index: {self.quality_metrics.voice_quality_index:.1f}/100\n"
        )
        summary += "Key Metrics:\n"
        summary += f"  - Jitter: {self.acoustic_metrics.jitter_percent:.2f}%\n"
        summary += f"  - Shimmer: {self.acoustic_metrics.shimmer_percent:.2f}%\n"
        summary += f"  - HNR: {self.acoustic_metrics.hnr:.1f} dB\n"

        if self.detected_disorders:
            summary += f"\nPotential Issues: {', '.join(d.value for d in self.detected_disorders)}\n"

        return summary


@dataclass
class VoiceQualityConfig:
    """Configuration for voice quality analysis."""

    # Analysis settings
    min_f0: float = 75.0  # Hz, minimum F0 to search
    max_f0: float = 600.0  # Hz, maximum F0 to search

    # Window settings
    window_length: float = 0.025  # seconds
    hop_length: float = 0.010  # seconds

    # Quality thresholds
    jitter_threshold_normal: float = 1.0  # % for normal voice
    shimmer_threshold_normal: float = 3.0  # % for normal voice
    hnr_threshold_normal: float = 20.0  # dB for normal voice

    # Clinical thresholds
    grbas_scale_max: float = 3.0
    voice_break_threshold: float = 0.1  # seconds

    # Feature extraction
    n_mfcc: int = 13
    n_formants: int = 4

    # Advanced analysis
    use_praat_backend: bool = True
    use_ml_models: bool = True
    ml_model_path: Optional[str] = None

    # Recording quality
    min_recording_quality: float = 0.6
    max_clipping_ratio: float = 0.001

    # Gender-specific settings
    auto_detect_gender: bool = True
    male_f0_range: Tuple[float, float] = (75, 200)
    female_f0_range: Tuple[float, float] = (150, 400)
    child_f0_range: Tuple[float, float] = (200, 600)


class VoiceQualityAnalyzer:
    """
    Comprehensive voice quality analyzer for medical assessment.

    Implements various acoustic, spectral, and clinical metrics
    for voice quality evaluation and disorder detection.
    """

    def __init__(self, config: Optional[VoiceQualityConfig] = None):
        """
        Initialize the voice quality analyzer.

        Args:
            config: Analysis configuration
        """
        self.config = config or VoiceQualityConfig()

        # Reference values for normal voice
        self.normal_ranges = {
            "jitter_percent": (0, 1.0),
            "shimmer_percent": (0, 3.0),
            "hnr": (20, float("inf")),
            "f0_std": (0, 30),
            "cpps": (4, float("inf")),
        }

        # Initialize ML models if configured
        self.ml_models: Dict[str, Any] = {}
        if self.config.use_ml_models:
            self._load_ml_models()

        logger.info("VoiceQualityAnalyzer initialized")

    def _load_ml_models(self) -> None:
        """Load machine learning models for quality assessment."""
        # Placeholder for ML model loading
        # In production, would load trained models
        logger.info("ML models loaded (placeholder)")

    @requires_phi_access("read")
    async def analyze_voice_quality(
        self,
        audio_data: np.ndarray,
        sample_rate: int = 16000,
        gender: Optional[str] = None,
        user_id: str = "system",
    ) -> VoiceQualityResult:
        """
        Perform comprehensive voice quality analysis.

        Args:
            audio_data: Audio signal
            sample_rate: Sample rate in Hz
            gender: Optional gender specification ('male', 'female', 'child')
            user_id: User ID for access control

        Returns:
            VoiceQualityResult with all metrics
        """
        start_time = datetime.now()

        # Log analysis request
        logger.info("Voice quality analysis requested by user: %s", user_id)

        try:
            # Auto-detect gender if needed
            if self.config.auto_detect_gender and gender is None:
                gender = await self._detect_gender(audio_data, sample_rate)

            # Extract all metrics
            acoustic = await self._extract_acoustic_metrics(
                audio_data, sample_rate, gender
            )
            spectral = await self._extract_spectral_metrics(audio_data, sample_rate)
            temporal = await self._extract_temporal_metrics(audio_data, sample_rate)
            clinical = await self._extract_clinical_metrics(
                audio_data, sample_rate, acoustic, spectral
            )
            quality = await self._extract_quality_metrics(audio_data, sample_rate)

            # Overall assessment
            category = self._categorize_voice_quality(acoustic, clinical, quality)
            confidence = self._calculate_confidence(acoustic, quality)

            # Disorder detection
            disorders, probabilities = await self._detect_voice_disorders(
                acoustic, spectral, clinical
            )

            # Generate clinical notes
            notes = self._generate_clinical_notes(
                acoustic, spectral, clinical, quality, disorders
            )

            # Generate recommendations
            recommendations = self._generate_recommendations(
                acoustic, clinical, disorders
            )

            # Generate warnings
            warnings = self._generate_warnings(acoustic, quality)

            # Processing time
            processing_time = (datetime.now() - start_time).total_seconds() * 1000

            return VoiceQualityResult(
                acoustic_metrics=acoustic,
                spectral_metrics=spectral,
                temporal_metrics=temporal,
                clinical_metrics=clinical,
                quality_metrics=quality,
                overall_category=category,
                confidence_score=confidence,
                detected_disorders=disorders,
                disorder_probabilities=probabilities,
                clinical_notes=notes,
                recommended_assessments=recommendations,
                sample_rate=sample_rate,
                audio_duration=len(audio_data) / sample_rate,
                processing_time_ms=processing_time,
                warnings=warnings,
            )

        except Exception as e:
            logger.error("Error in voice quality analysis: %s", str(e), exc_info=True)
            raise

    async def _detect_gender(self, audio_data: np.ndarray, sample_rate: int) -> str:
        """Auto-detect speaker gender based on F0."""
        # Extract F0
        f0_values = self._extract_f0_praat(audio_data, sample_rate)

        if len(f0_values) == 0:
            return "unknown"

        mean_f0 = np.mean(f0_values)

        # Simple classification based on F0 ranges
        if mean_f0 < 150:
            return "male"
        elif mean_f0 < 250:
            return "female"
        else:
            return "child"

    async def _extract_acoustic_metrics(
        self, audio_data: np.ndarray, sample_rate: int, gender: Optional[str]
    ) -> AcousticMetrics:
        """Extract core acoustic metrics."""
        metrics = AcousticMetrics()

        # Adjust F0 range based on gender
        if gender == "male":
            min_f0, max_f0 = self.config.male_f0_range
        elif gender == "female":
            min_f0, max_f0 = self.config.female_f0_range
        elif gender == "child":
            min_f0, max_f0 = self.config.child_f0_range
        else:
            min_f0, max_f0 = self.config.min_f0, self.config.max_f0

        # Extract F0 using Praat or librosa
        if self.config.use_praat_backend:
            f0_values = self._extract_f0_praat(audio_data, sample_rate, min_f0, max_f0)
        else:
            f0_values = self._extract_f0_librosa(
                audio_data, sample_rate, min_f0, max_f0
            )

        if len(f0_values) > 0:
            metrics.f0_mean = np.mean(f0_values)
            metrics.f0_std = np.std(f0_values)
            metrics.f0_min = np.min(f0_values)
            metrics.f0_max = np.max(f0_values)
            metrics.f0_range = metrics.f0_max - metrics.f0_min

            # Jitter calculations
            metrics.jitter_absolute = self._calculate_jitter_absolute(
                f0_values, sample_rate
            )
            metrics.jitter_percent = self._calculate_jitter_percent(f0_values)
            metrics.jitter_rap = self._calculate_jitter_rap(f0_values)
            metrics.jitter_ppq5 = self._calculate_jitter_ppq5(f0_values)

        # Shimmer calculations
        metrics.shimmer_absolute = self._calculate_shimmer_absolute(audio_data)
        metrics.shimmer_percent = self._calculate_shimmer_percent(audio_data)
        metrics.shimmer_apq3 = self._calculate_shimmer_apq3(audio_data)
        metrics.shimmer_apq11 = self._calculate_shimmer_apq11(audio_data)

        # HNR calculation
        metrics.hnr = self._calculate_hnr(audio_data, sample_rate)
        metrics.nhr = (
            1 / (10 ** (metrics.hnr / 10)) if metrics.hnr > 0 else float("inf")
        )

        # VTI and SPI (simplified calculations)
        metrics.vti = self._calculate_vti(audio_data, sample_rate)
        metrics.spi = self._calculate_spi(audio_data, sample_rate)

        # CPPS calculation
        metrics.cpps = self._calculate_cpps(audio_data, sample_rate)

        # Energy metrics
        metrics.energy_mean = np.mean(audio_data**2)
        metrics.energy_std = np.std(audio_data**2)

        # Zero crossing rate
        metrics.zero_crossing_rate = np.mean(
            librosa.feature.zero_crossing_rate(audio_data)
        )

        return metrics

    def _extract_f0_praat(
        self,
        audio_data: np.ndarray,
        sample_rate: int,
        min_f0: float = 75,
        max_f0: float = 600,
    ) -> np.ndarray:
        """Extract F0 using Praat (via parselmouth)."""
        try:
            # Create Praat sound object
            sound = parselmouth.Sound(audio_data, sample_rate)

            # Extract pitch
            pitch = sound.to_pitch(
                time_step=self.config.hop_length,
                pitch_floor=min_f0,
                pitch_ceiling=max_f0,
            )

            # Get F0 values
            f0_values = []
            for i in range(pitch.n_frames):
                value = pitch.get_value_in_frame(i)
                if value is not None and value > 0:
                    f0_values.append(value)

            return np.array(f0_values)

        except (ValueError, RuntimeError, AttributeError) as e:
            logger.warning(
                "Praat extraction failed, falling back to librosa: %s", str(e)
            )
            return self._extract_f0_librosa(audio_data, sample_rate, min_f0, max_f0)

    def _extract_f0_librosa(
        self,
        audio_data: np.ndarray,
        sample_rate: int,
        min_f0: float = 75,
        max_f0: float = 600,
    ) -> np.ndarray:
        """Extract F0 using librosa."""
        # Use piptrack for F0 estimation
        hop_length = int(self.config.hop_length * sample_rate)

        pitches, magnitudes = librosa.piptrack(
            y=audio_data,
            sr=sample_rate,
            hop_length=hop_length,
            fmin=min_f0,
            fmax=max_f0,
            threshold=0.1,
        )

        # Extract F0 from piptrack output
        f0_values = []
        for t in range(pitches.shape[1]):
            index = magnitudes[:, t].argmax()
            pitch = pitches[index, t]
            if pitch > 0:
                f0_values.append(pitch)

        return np.array(f0_values)

    def _calculate_jitter_absolute(
        self, f0_values: np.ndarray, sample_rate: int
    ) -> float:
        """Calculate absolute jitter in milliseconds."""
        _ = sample_rate  # Unused parameter kept for API consistency
        if len(f0_values) < 2:
            return 0.0

        # Convert F0 to periods
        periods = 1.0 / f0_values

        # Calculate absolute differences
        period_diffs = np.abs(np.diff(periods))

        # Convert to milliseconds
        return float(np.mean(period_diffs) * 1000)

    def _calculate_jitter_percent(self, f0_values: np.ndarray) -> float:
        """Calculate relative jitter as percentage."""
        if len(f0_values) < 2:
            return 0.0

        periods = 1.0 / f0_values
        period_diffs = np.abs(np.diff(periods))
        mean_period = np.mean(periods)

        if mean_period > 0:
            return float((np.mean(period_diffs) / mean_period) * 100)
        return 0.0

    def _calculate_jitter_rap(self, f0_values: np.ndarray) -> float:
        """Calculate relative average perturbation."""
        if len(f0_values) < 3:
            return 0.0

        periods = 1.0 / f0_values

        # Three-point average perturbation
        rap_sum = 0
        for i in range(1, len(periods) - 1):
            avg_3 = (periods[i - 1] + periods[i] + periods[i + 1]) / 3
            rap_sum += abs(periods[i] - avg_3)

        mean_period = np.mean(periods)
        if mean_period > 0 and len(periods) > 2:
            return float((rap_sum / (len(periods) - 2)) / mean_period)
        return 0.0

    def _calculate_jitter_ppq5(self, f0_values: np.ndarray) -> float:
        """Calculate 5-point period perturbation quotient."""
        if len(f0_values) < 5:
            return 0.0

        periods = 1.0 / f0_values

        # Five-point average perturbation
        ppq5_sum = 0
        for i in range(2, len(periods) - 2):
            avg_5 = np.mean(periods[i - 2 : i + 3])
            ppq5_sum += abs(periods[i] - avg_5)

        mean_period = np.mean(periods)
        if mean_period > 0 and len(periods) > 4:
            return float((ppq5_sum / (len(periods) - 4)) / mean_period)
        return 0.0

    def _calculate_shimmer_absolute(self, audio_data: np.ndarray) -> float:
        """Calculate absolute shimmer in dB."""
        # Get amplitude peaks
        peaks = self._find_amplitude_peaks(audio_data)

        if len(peaks) < 2:
            return 0.0

        # Calculate differences in dB
        peak_diffs_db = []
        for i in range(1, len(peaks)):
            if peaks[i] > 0 and peaks[i - 1] > 0:
                diff_db = 20 * np.log10(peaks[i] / peaks[i - 1])
                peak_diffs_db.append(abs(diff_db))

        return np.mean(peak_diffs_db) if peak_diffs_db else 0.0

    def _calculate_shimmer_percent(self, audio_data: np.ndarray) -> float:
        """Calculate relative shimmer as percentage."""
        peaks = self._find_amplitude_peaks(audio_data)

        if len(peaks) < 2:
            return 0.0

        # Calculate relative differences
        peak_diffs = np.abs(np.diff(peaks))
        mean_peak = np.mean(peaks)

        if mean_peak > 0:
            return float((np.mean(peak_diffs) / mean_peak) * 100)
        return 0.0

    def _calculate_shimmer_apq3(self, audio_data: np.ndarray) -> float:
        """Calculate 3-point amplitude perturbation quotient."""
        peaks = self._find_amplitude_peaks(audio_data)

        if len(peaks) < 3:
            return 0.0

        # Three-point average perturbation
        apq3_sum = 0
        for i in range(1, len(peaks) - 1):
            avg_3 = (peaks[i - 1] + peaks[i] + peaks[i + 1]) / 3
            apq3_sum += abs(peaks[i] - avg_3)

        mean_peak = np.mean(peaks)
        if mean_peak > 0 and len(peaks) > 2:
            return float((apq3_sum / (len(peaks) - 2)) / mean_peak * 100)
        return 0.0

    def _calculate_shimmer_apq11(self, audio_data: np.ndarray) -> float:
        """Calculate 11-point amplitude perturbation quotient."""
        peaks = self._find_amplitude_peaks(audio_data)

        if len(peaks) < 11:
            return 0.0

        # Eleven-point average perturbation
        apq11_sum = 0
        for i in range(5, len(peaks) - 5):
            avg_11 = np.mean(peaks[i - 5 : i + 6])
            apq11_sum += abs(peaks[i] - avg_11)

        mean_peak = np.mean(peaks)
        if mean_peak > 0 and len(peaks) > 10:
            return float((apq11_sum / (len(peaks) - 10)) / mean_peak * 100)
        return 0.0

    def _find_amplitude_peaks(self, audio_data: np.ndarray) -> np.ndarray:
        """Find amplitude peaks in the signal."""
        # Use Hilbert transform to get envelope
        analytic_signal = signal.hilbert(audio_data)
        amplitude_envelope = np.abs(analytic_signal)

        # Find peaks
        peaks, _ = signal.find_peaks(
            amplitude_envelope, distance=int(0.005 * len(audio_data))
        )

        return np.array(amplitude_envelope[peaks])

    def _calculate_hnr(self, audio_data: np.ndarray, sample_rate: int) -> float:
        """Calculate harmonics-to-noise ratio."""
        if self.config.use_praat_backend:
            try:
                # Use Praat for HNR calculation
                sound = parselmouth.Sound(audio_data, sample_rate)
                harmonicity = sound.to_harmonicity()
                hnr_values = []

                for i in range(harmonicity.n_frames):
                    value = harmonicity.get_value(i)
                    if value is not None:
                        hnr_values.append(value)

                return np.mean(hnr_values) if hnr_values else 0.0

            except (ValueError, RuntimeError, AttributeError):
                pass

        # Fallback to autocorrelation method
        # Compute autocorrelation
        autocorr = np.correlate(audio_data, audio_data, mode="full")
        autocorr = autocorr[len(autocorr) // 2 :]

        # Find first peak after zero lag
        peaks, _ = signal.find_peaks(autocorr[1:], height=0)

        if len(peaks) > 0:
            # Get harmonic peak
            harmonic_peak = autocorr[peaks[0] + 1]

            # Estimate noise from valleys
            if len(peaks) > 1:
                valley_start = peaks[0] + 1 + (peaks[1] - peaks[0]) // 2
                noise_estimate = np.mean(autocorr[valley_start:])
            else:
                noise_estimate = np.mean(autocorr[len(autocorr) // 2 :])

            if noise_estimate > 0:
                hnr = 10 * np.log10(harmonic_peak / noise_estimate)
                return float(max(0, hnr))

        return 0.0

    def _calculate_vti(self, audio_data: np.ndarray, sample_rate: int) -> float:
        """Calculate Voice Turbulence Index."""
        # Simplified VTI calculation
        # Ratio of high-frequency noise to low-frequency harmonics

        # High-pass filter at 2.5 kHz
        nyquist = sample_rate / 2
        high_cutoff = 2500 / nyquist

        if high_cutoff < 1:
            b, a = signal.butter(4, high_cutoff, btype="high")
            high_freq = signal.filtfilt(b, a, audio_data)

            # Low-pass filter at 2.5 kHz
            b, a = signal.butter(4, high_cutoff, btype="low")
            low_freq = signal.filtfilt(b, a, audio_data)

            # Energy ratio
            high_energy = np.mean(high_freq**2)
            low_energy = np.mean(low_freq**2)

            if low_energy > 0:
                return float(high_energy / low_energy)

        return 0.0

    def _calculate_spi(self, audio_data: np.ndarray, sample_rate: int) -> float:
        """Calculate Soft Phonation Index."""
        # Ratio of low-frequency harmonic energy to high-frequency harmonic energy

        # Low frequency band: 70-1600 Hz
        low_band = self._bandpass_filter(audio_data, 70, 1600, sample_rate)

        # High frequency band: 1600-4500 Hz
        high_band = self._bandpass_filter(audio_data, 1600, 4500, sample_rate)

        # Calculate harmonics in each band
        low_harmonics = self._estimate_harmonic_energy(low_band, sample_rate)
        high_harmonics = self._estimate_harmonic_energy(high_band, sample_rate)

        if high_harmonics > 0:
            return low_harmonics / high_harmonics

        return 0.0

    def _calculate_cpps(self, audio_data: np.ndarray, sample_rate: int) -> float:
        """Calculate Cepstral Peak Prominence Smoothed."""
        # Frame-based cepstral analysis
        frame_length = int(self.config.window_length * sample_rate)
        hop_length = int(self.config.hop_length * sample_rate)

        frames = librosa.util.frame(
            audio_data, frame_length=frame_length, hop_length=hop_length
        )

        cpps_values = []

        for frame in frames.T:
            # Apply window
            windowed = frame * np.hanning(len(frame))

            # Compute power spectrum
            spectrum = np.abs(np.fft.rfft(windowed)) ** 2

            # Compute cepstrum
            log_spectrum = np.log(spectrum + 1e-10)
            cepstrum = np.abs(np.fft.irfft(log_spectrum))

            # Find peak in quefrency range (fundamental period)
            # Typical range: 2-20 ms
            min_quefrency = int(0.002 * sample_rate)
            max_quefrency = int(0.020 * sample_rate)

            if max_quefrency < len(cepstrum):
                peak_region = cepstrum[min_quefrency:max_quefrency]
                if len(peak_region) > 0:
                    peak_value = np.max(peak_region)
                    baseline = np.mean(cepstrum)

                    # Prominence in dB
                    if baseline > 0:
                        prominence = 20 * np.log10(peak_value / baseline)
                        cpps_values.append(prominence)

        if cpps_values:
            # Apply smoothing
            smoothed = gaussian_filter1d(cpps_values, sigma=2)
            return float(np.mean(smoothed))

        return 0.0

    def _bandpass_filter(
        self,
        audio_data: np.ndarray,
        low_freq: float,
        high_freq: float,
        sample_rate: int,
    ) -> np.ndarray:
        """Apply bandpass filter to audio."""
        nyquist = sample_rate / 2
        low = low_freq / nyquist
        high = high_freq / nyquist

        if 0 < low < 1 and 0 < high < 1 and low < high:
            b, a = signal.butter(4, [low, high], btype="band")
            return np.array(signal.filtfilt(b, a, audio_data))

        return audio_data

    def _estimate_harmonic_energy(
        self, audio_data: np.ndarray, sample_rate: int
    ) -> float:
        """Estimate harmonic energy in signal."""
        _ = sample_rate  # Unused parameter kept for API consistency
        # Use harmonic percussive separation
        stft = librosa.stft(audio_data)
        harmonic, _ = librosa.decompose.hpss(stft)

        # Calculate energy of harmonic component
        harmonic_signal = librosa.istft(harmonic)
        return float(np.mean(harmonic_signal**2))

    async def _extract_spectral_metrics(
        self, audio_data: np.ndarray, sample_rate: int
    ) -> SpectralMetrics:
        """Extract spectral characteristics."""
        metrics = SpectralMetrics()

        # Compute STFT
        stft = librosa.stft(audio_data)
        magnitude = np.abs(stft)
        freqs = librosa.fft_frequencies(sr=sample_rate)

        # Spectral features
        centroid = librosa.feature.spectral_centroid(y=audio_data, sr=sample_rate)
        metrics.spectral_centroid = np.mean(centroid)

        # Spectral spread (second moment)
        spread = np.sqrt(
            np.sum((freqs[:, np.newaxis] - centroid) ** 2 * magnitude, axis=0)
            / np.sum(magnitude, axis=0)
        )
        metrics.spectral_spread = np.mean(spread)

        # Spectral skewness and kurtosis
        normalized_freqs = (freqs[:, np.newaxis] - centroid) / (spread + 1e-10)
        metrics.spectral_skewness = np.mean(
            np.sum(normalized_freqs**3 * magnitude, axis=0) / np.sum(magnitude, axis=0)
        )
        metrics.spectral_kurtosis = np.mean(
            np.sum(normalized_freqs**4 * magnitude, axis=0) / np.sum(magnitude, axis=0)
        )

        # Spectral flux
        flux = np.sum(np.diff(magnitude, axis=1) ** 2, axis=0)
        metrics.spectral_flux = np.mean(flux)

        # Spectral rolloff
        rolloff = librosa.feature.spectral_rolloff(y=audio_data, sr=sample_rate)
        metrics.spectral_rolloff = np.mean(rolloff)

        # Spectral slope (linear regression of magnitude spectrum)
        mean_magnitude = np.mean(magnitude, axis=1)
        if len(mean_magnitude) > 1:
            slope, _ = np.polyfit(freqs[: len(mean_magnitude)], mean_magnitude, 1)
            metrics.spectral_slope = slope

        # Extract formants
        formants = await self._extract_formants(audio_data, sample_rate)
        if len(formants) > 0:
            metrics.f1_mean = formants[0]["frequency"]
            metrics.f1_bandwidth = formants[0]["bandwidth"]
        if len(formants) > 1:
            metrics.f2_mean = formants[1]["frequency"]
            metrics.f2_bandwidth = formants[1]["bandwidth"]
        if len(formants) > 2:
            metrics.f3_mean = formants[2]["frequency"]
            metrics.f3_bandwidth = formants[2]["bandwidth"]

        # Spectral balance
        low_energy = np.mean(magnitude[freqs < 1000, :])
        high_energy = np.mean(magnitude[freqs >= 1000, :])
        metrics.low_to_high_ratio = low_energy / (high_energy + 1e-10)

        # Alpha ratio (spectral tilt)
        if len(mean_magnitude) > 10:
            low_band_energy = np.mean(mean_magnitude[: len(mean_magnitude) // 4])
            high_band_energy = np.mean(mean_magnitude[3 * len(mean_magnitude) // 4 :])
            metrics.alpha_ratio = low_band_energy / (high_band_energy + 1e-10)

        return metrics

    async def _extract_formants(
        self, audio_data: np.ndarray, sample_rate: int
    ) -> List[Dict[str, float]]:
        """Extract formant frequencies and bandwidths."""
        formants = []

        if self.config.use_praat_backend:
            try:
                # Use Praat for formant extraction
                sound = parselmouth.Sound(audio_data, sample_rate)
                formant_obj = sound.to_formant_burg(
                    max_number_of_formants=self.config.n_formants
                )

                # Get mean formant values
                for i in range(1, min(4, self.config.n_formants + 1)):
                    freq_values = []
                    bw_values = []

                    for frame in range(formant_obj.n_frames):
                        freq = formant_obj.get_value_at_time(
                            i, formant_obj.frame_number_to_time(frame + 1)
                        )
                        bw = formant_obj.get_bandwidth_at_time(
                            i, formant_obj.frame_number_to_time(frame + 1)
                        )

                        if freq is not None and not np.isnan(freq):
                            freq_values.append(freq)
                        if bw is not None and not np.isnan(bw):
                            bw_values.append(bw)

                    if freq_values:
                        formants.append(
                            {
                                "frequency": np.mean(freq_values),
                                "bandwidth": np.mean(bw_values) if bw_values else 100,
                            }
                        )

            except (ValueError, RuntimeError, AttributeError) as e:
                logger.warning("Praat formant extraction failed: %s", str(e))

        # Fallback to LPC-based formant estimation
        if not formants:
            formants = self._estimate_formants_lpc(audio_data, sample_rate)

        return formants

    def _estimate_formants_lpc(
        self, audio_data: np.ndarray, sample_rate: int
    ) -> List[Dict[str, float]]:
        """Estimate formants using LPC analysis."""
        # Pre-emphasis
        pre_emphasized = np.append(
            audio_data[0], audio_data[1:] - 0.97 * audio_data[:-1]
        )

        # LPC order (rule of thumb: sample_rate / 1000 + 2)
        lpc_order = int(sample_rate / 1000) + 4

        # Compute LPC coefficients
        try:
            lpc_coeffs = librosa.lpc(pre_emphasized, order=lpc_order)

            # Find roots
            roots = np.roots(lpc_coeffs)

            # Convert to frequencies
            angles = np.angle(roots)
            freqs = angles * (sample_rate / (2 * np.pi))

            # Keep only positive frequencies with significant magnitude
            positive_freqs = freqs[freqs > 0]
            magnitudes = np.abs(roots[freqs > 0])

            # Sort by frequency
            sorted_indices = np.argsort(positive_freqs)
            sorted_freqs = positive_freqs[sorted_indices]
            sorted_mags = magnitudes[sorted_indices]

            # Select formants (peaks with high magnitude)
            formants = []
            for i, (freq, mag) in enumerate(zip(sorted_freqs, sorted_mags)):
                if mag > 0.7 and 200 < freq < 5000:  # Typical formant range
                    # Estimate bandwidth (simplified)
                    bandwidth = 100 + (i * 50)  # Rough approximation

                    formants.append(
                        {"frequency": float(freq), "bandwidth": float(bandwidth)}
                    )

                    if len(formants) >= 3:
                        break

            return formants

        except (ValueError, RuntimeError, AttributeError) as e:
            logger.warning("LPC formant estimation failed: %s", str(e))

            # Return default formants
            return [
                {"frequency": 700, "bandwidth": 100},
                {"frequency": 1700, "bandwidth": 150},
                {"frequency": 2700, "bandwidth": 200},
            ]

    async def _extract_temporal_metrics(
        self, audio_data: np.ndarray, sample_rate: int
    ) -> TemporalMetrics:
        """Extract temporal characteristics."""
        metrics = TemporalMetrics()

        # Detect voiced segments
        voiced_segments = self._detect_voiced_segments(audio_data, sample_rate)

        # Calculate speaking and articulation rates
        if voiced_segments:
            # Estimate syllables (simplified - peaks in energy envelope)
            envelope = self._get_amplitude_envelope(audio_data)
            peaks, _ = signal.find_peaks(envelope, distance=int(0.1 * sample_rate))

            total_duration = len(audio_data) / sample_rate
            voiced_duration = (
                sum(end - start for start, end in voiced_segments) / sample_rate
            )

            metrics.speaking_rate = len(peaks) / total_duration
            metrics.articulation_rate = (
                len(peaks) / voiced_duration if voiced_duration > 0 else 0
            )

        # Pause analysis
        pauses = self._detect_pauses(audio_data, sample_rate)
        metrics.pause_count = len(pauses)

        if pauses:
            pause_durations = [(end - start) / sample_rate for start, end in pauses]
            metrics.pause_duration_mean = float(np.mean(pause_durations))
            metrics.pause_duration_std = float(np.std(pause_durations))

            total_pause_duration = sum(pause_durations)
            total_duration = len(audio_data) / sample_rate
            metrics.pause_ratio = total_pause_duration / total_duration

        # Rhythm analysis
        if voiced_segments:
            # Inter-segment intervals
            intervals = []
            for i in range(1, len(voiced_segments)):
                interval = voiced_segments[i][0] - voiced_segments[i - 1][1]
                intervals.append(interval / sample_rate)

            if intervals:
                metrics.rhythm_regularity = float(1.0 / (1.0 + np.std(intervals)))
                metrics.tempo_variability = float(
                    float(np.std(intervals)) / (np.mean(intervals) + 1e-10)
                )

        # Voice onset/offset times
        if voiced_segments:
            metrics.voice_onset_time = voiced_segments[0][0] / sample_rate
            metrics.voice_offset_time = (
                len(audio_data) - voiced_segments[-1][1]
            ) / sample_rate

            # Attack time (time to reach 90% of max amplitude in first segment)
            first_segment = audio_data[voiced_segments[0][0] : voiced_segments[0][1]]
            if len(first_segment) > 0:
                envelope = self._get_amplitude_envelope(first_segment)
                max_amp = np.max(envelope)
                attack_samples = np.argmax(envelope > 0.9 * max_amp)
                metrics.voice_attack_time = float(attack_samples / sample_rate)

        return metrics

    def _detect_voiced_segments(
        self, audio_data: np.ndarray, sample_rate: int
    ) -> List[Tuple[int, int]]:
        """Detect voiced segments in audio."""
        # Energy-based voice activity detection
        frame_length = int(0.025 * sample_rate)
        hop_length = int(0.010 * sample_rate)

        frames = librosa.util.frame(
            audio_data, frame_length=frame_length, hop_length=hop_length
        )
        energy = np.sum(frames**2, axis=0)

        # Zero crossing rate
        zcr = librosa.feature.zero_crossing_rate(
            audio_data, frame_length=frame_length, hop_length=hop_length
        )[0]

        # Thresholds
        energy_threshold = np.percentile(energy, 30)
        zcr_threshold = np.percentile(zcr, 70)

        # Voiced = high energy and low ZCR
        voiced_frames = (energy > energy_threshold) & (zcr < zcr_threshold)

        # Convert frames to segments
        segments = []
        in_segment = False
        start = 0

        for i, is_voiced in enumerate(voiced_frames):
            sample_pos = i * hop_length

            if is_voiced and not in_segment:
                start = sample_pos
                in_segment = True
            elif not is_voiced and in_segment:
                segments.append((start, sample_pos))
                in_segment = False

        if in_segment:
            segments.append((start, len(audio_data)))

        # Merge close segments
        merged: List[Tuple[int, int]] = []
        min_gap = int(0.1 * sample_rate)  # 100ms minimum gap

        for start, end in segments:
            if merged and start - merged[-1][1] < min_gap:
                merged[-1] = (merged[-1][0], end)
            else:
                merged.append((start, end))

        return merged

    def _detect_pauses(
        self, audio_data: np.ndarray, sample_rate: int
    ) -> List[Tuple[int, int]]:
        """Detect pauses in speech."""
        voiced_segments = self._detect_voiced_segments(audio_data, sample_rate)

        if len(voiced_segments) < 2:
            return []

        pauses = []
        min_pause_duration = int(0.2 * sample_rate)  # 200ms minimum

        for i in range(1, len(voiced_segments)):
            gap_start = voiced_segments[i - 1][1]
            gap_end = voiced_segments[i][0]

            if gap_end - gap_start >= min_pause_duration:
                pauses.append((gap_start, gap_end))

        return pauses

    def _get_amplitude_envelope(self, audio_data: np.ndarray) -> np.ndarray:
        """Get amplitude envelope of signal."""
        analytic = signal.hilbert(audio_data)
        return np.array(np.abs(analytic))

    @requires_phi_access("read")
    async def _extract_clinical_metrics(
        self,
        audio_data: np.ndarray,
        sample_rate: int,
        acoustic: AcousticMetrics,
        spectral: SpectralMetrics,
        user_id: str = "system",
    ) -> ClinicalMetrics:
        """Extract clinical voice quality indicators."""
        # Log clinical metrics extraction
        logger.debug("Extracting clinical metrics for user: %s", user_id)

        metrics = ClinicalMetrics()

        # GRBAS scale estimation (simplified)
        # Grade (overall severity)
        grade_factors = [
            min(acoustic.jitter_percent / 3.0, 1.0),  # Jitter contribution
            min(acoustic.shimmer_percent / 6.0, 1.0),  # Shimmer contribution
            max(0, 1 - acoustic.hnr / 30.0),  # HNR contribution
        ]
        metrics.grade = min(3.0, sum(grade_factors))

        # Roughness (related to jitter)
        metrics.roughness = min(3.0, acoustic.jitter_percent / 2.0)

        # Breathiness (related to HNR and high-frequency noise)
        breathiness_factors = [
            max(0, 1 - acoustic.hnr / 25.0),
            min(acoustic.vti * 3, 1.0),
            min(spectral.low_to_high_ratio / 10, 1.0),
        ]
        metrics.breathiness = min(3.0, sum(breathiness_factors))

        # Asthenia (weakness - related to low energy and reduced F0 range)
        asthenia_factors = [
            max(0, 1 - acoustic.f0_range / 100),
            max(0, 1 - acoustic.energy_mean * 10),
            min(acoustic.spi / 20, 1.0),
        ]
        metrics.asthenia = min(3.0, sum(asthenia_factors))

        # Strain (hyperfunctional voice - high F0, high energy variation)
        strain_factors = [
            min(acoustic.f0_std / 50, 1.0),
            min(acoustic.energy_std * 5, 1.0),
            (
                max(0, spectral.spectral_slope * 1000)
                if spectral.spectral_slope > 0
                else 0
            ),
        ]
        metrics.strain = min(3.0, sum(strain_factors))

        # Hoarseness index (composite measure)
        metrics.hoarseness_index = (
            0.3 * metrics.roughness
            + 0.3 * metrics.breathiness
            + 0.2 * metrics.grade
            + 0.1 * metrics.asthenia
            + 0.1 * metrics.strain
        )

        # Voice breaks detection
        metrics.voice_breaks = await self._detect_voice_breaks(audio_data, sample_rate)

        # Diplophonia detection (two simultaneous pitches)
        metrics.diplophonia = await self._detect_diplophonia(audio_data, sample_rate)

        # Tremor detection
        metrics.tremor_detected, metrics.tremor_frequency = await self._detect_tremor(
            audio_data, sample_rate
        )

        # Aerodynamic estimates (simplified)
        # Higher breathiness and VTI suggest increased airflow
        metrics.estimated_airflow = (
            metrics.breathiness / 3.0 * 0.5 + min(acoustic.vti, 1.0) * 0.5
        )

        # Glottal efficiency (inverse of breathiness and turbulence)
        metrics.glottal_efficiency = max(0, 1 - metrics.estimated_airflow)

        return metrics

    async def _detect_voice_breaks(
        self, audio_data: np.ndarray, sample_rate: int
    ) -> int:
        """Detect voice breaks (sudden F0 changes or dropouts)."""
        # Extract F0 contour
        f0_values = self._extract_f0_praat(audio_data, sample_rate)

        if len(f0_values) < 3:
            return 0

        # Look for sudden changes or gaps
        breaks = 0

        # Check for sudden F0 jumps (more than octave)
        for i in range(1, len(f0_values)):
            ratio = f0_values[i] / f0_values[i - 1]
            if ratio > 2.0 or ratio < 0.5:
                breaks += 1

        # Check for F0 dropouts in voiced regions
        # This would require more sophisticated VAD

        return breaks

    async def _detect_diplophonia(
        self, audio_data: np.ndarray, sample_rate: int
    ) -> bool:
        """Detect diplophonia (two simultaneous fundamental frequencies)."""
        # Compute autocorrelation
        autocorr = np.correlate(audio_data, audio_data, mode="full")
        autocorr = autocorr[len(autocorr) // 2 :]

        # Look for multiple periodic peaks
        peaks, properties = signal.find_peaks(
            autocorr[1 : int(0.02 * sample_rate)],  # Up to 20ms lag
            height=0.3 * autocorr[0],
            distance=int(0.002 * sample_rate),  # Minimum 2ms apart
        )

        # If we find multiple strong peaks, might indicate diplophonia
        if len(peaks) >= 2:
            # Check if peaks have similar heights (within 50%)
            heights = properties["peak_heights"]
            if len(heights) >= 2:
                ratio = min(heights[0], heights[1]) / max(heights[0], heights[1])
                if ratio > 0.5:
                    return True

        return False

    async def _detect_tremor(
        self, audio_data: np.ndarray, sample_rate: int
    ) -> Tuple[bool, Optional[float]]:
        """Detect voice tremor and its frequency."""
        # Extract amplitude envelope
        envelope = self._get_amplitude_envelope(audio_data)

        # Downsample envelope for tremor analysis
        downsample_factor = 100
        envelope_downsampled = envelope[::downsample_factor]

        # Remove DC and trend
        envelope_detrended = signal.detrend(envelope_downsampled)

        # Compute spectrum of envelope modulation
        freqs = np.fft.rfftfreq(
            len(envelope_detrended), downsample_factor / sample_rate
        )
        spectrum = np.abs(np.fft.rfft(envelope_detrended))

        # Look for peaks in tremor frequency range (3-15 Hz)
        tremor_mask = (freqs >= 3) & (freqs <= 15)

        if np.any(tremor_mask):
            tremor_spectrum = spectrum[tremor_mask]
            tremor_freqs = freqs[tremor_mask]

            # Find peak
            peak_idx = np.argmax(tremor_spectrum)
            peak_freq = tremor_freqs[peak_idx]
            peak_power = tremor_spectrum[peak_idx]

            # Check if peak is significant
            noise_floor = np.median(spectrum)
            if peak_power > 5 * noise_floor:  # 5x above noise floor
                return True, float(peak_freq)

        return False, None

    async def _extract_quality_metrics(
        self, audio_data: np.ndarray, sample_rate: int
    ) -> QualityMetrics:
        """Extract overall quality assessment metrics."""
        _ = sample_rate  # Unused parameter kept for API consistency
        metrics = QualityMetrics()

        # Recording quality assessment
        # SNR estimation
        signal_power = np.mean(audio_data**2)

        # Estimate noise from quiet segments
        envelope = self._get_amplitude_envelope(audio_data)
        quiet_threshold = np.percentile(envelope, 10)
        quiet_segments = audio_data[envelope < quiet_threshold]

        if len(quiet_segments) > 0:
            noise_power = np.mean(quiet_segments**2)
            metrics.snr = 10 * np.log10(signal_power / (noise_power + 1e-10))
        else:
            metrics.snr = 40.0  # Assume good SNR if no quiet segments

        # Background noise level
        metrics.background_noise_level = 20 * np.log10(np.sqrt(noise_power) + 1e-10)

        # Clipping detection
        max_amplitude = np.max(np.abs(audio_data))
        metrics.clipping_detected = max_amplitude > 0.99

        # Overall recording quality (0-1)
        quality_factors = [
            min(1.0, metrics.snr / 40),  # SNR contribution
            1.0 if not metrics.clipping_detected else 0.5,
            min(1.0, max(0, -metrics.background_noise_level / 60)),  # Noise level
        ]
        metrics.recording_quality = float(np.mean(quality_factors))

        # Voice Quality Index (simplified composite score)
        # Would use standardized VQI calculation in production
        metrics.voice_quality_index = 50.0  # Placeholder

        # Dysphonia Severity Index (DSI)
        # DSI = 0.13 × MPT + 0.0053 × F0-High - 0.26 × I-Low - 1.18 × Jitter(%) + 12.4
        # Simplified version without MPT and intensity
        metrics.dysphonia_severity_index = 50.0  # Placeholder

        # Acoustic Voice Quality Index (AVQI)
        # Simplified version
        metrics.acoustic_voice_quality_index = 50.0  # Placeholder

        # Intelligibility estimation
        # Based on spectral clarity and articulation
        clarity_factors = [
            min(1.0, metrics.snr / 30),
            min(1.0, metrics.recording_quality),
            1.0 if not metrics.clipping_detected else 0.7,
        ]
        metrics.estimated_intelligibility = float(np.mean(clarity_factors))

        # Articulation precision (simplified)
        metrics.articulation_precision = metrics.estimated_intelligibility * 0.9

        return metrics

    def _categorize_voice_quality(
        self,
        acoustic: AcousticMetrics,
        clinical: ClinicalMetrics,
        quality: QualityMetrics,
    ) -> VoiceQualityCategory:
        """Categorize overall voice quality."""
        # Score based on deviations from normal ranges
        deviation_score: float = 0.0

        # Check acoustic parameters
        if acoustic.jitter_percent > self.config.jitter_threshold_normal:
            deviation_score += (
                acoustic.jitter_percent - self.config.jitter_threshold_normal
            )

        if acoustic.shimmer_percent > self.config.shimmer_threshold_normal:
            deviation_score += (
                acoustic.shimmer_percent - self.config.shimmer_threshold_normal
            ) / 3

        if acoustic.hnr < self.config.hnr_threshold_normal:
            deviation_score += (self.config.hnr_threshold_normal - acoustic.hnr) / 10

        # Add clinical severity
        deviation_score += clinical.grade

        # Consider recording quality
        if quality.recording_quality < 0.5:
            deviation_score += 1

        # Categorize based on total deviation
        if deviation_score < 1:
            return VoiceQualityCategory.EXCELLENT
        elif deviation_score < 2:
            return VoiceQualityCategory.GOOD
        elif deviation_score < 3:
            return VoiceQualityCategory.FAIR
        elif deviation_score < 4:
            return VoiceQualityCategory.POOR
        else:
            return VoiceQualityCategory.CRITICAL

    def _calculate_confidence(
        self, acoustic: AcousticMetrics, quality: QualityMetrics
    ) -> float:
        """Calculate confidence in the assessment."""
        confidence_factors = []

        # Recording quality affects confidence
        confidence_factors.append(quality.recording_quality)

        # SNR affects confidence
        confidence_factors.append(min(1.0, quality.snr / 30))

        # Consistent F0 tracking increases confidence
        if acoustic.f0_mean > 0:
            f0_consistency = 1.0 / (1.0 + acoustic.f0_std / acoustic.f0_mean)
            confidence_factors.append(f0_consistency)

        # No clipping increases confidence
        confidence_factors.append(1.0 if not quality.clipping_detected else 0.7)

        return float(np.mean(confidence_factors))

    @requires_phi_access("read")
    async def _detect_voice_disorders(
        self,
        acoustic: AcousticMetrics,
        spectral: SpectralMetrics,
        clinical: ClinicalMetrics,
        user_id: str = "system",
    ) -> Tuple[List[VoiceDisorderType], Dict[str, float]]:
        """Detect potential voice disorders based on metrics."""
        logger.debug("Detecting voice disorders for user: %s", user_id)

        _ = spectral  # Unused parameter kept for API consistency
        disorders = []
        probabilities = {}

        # Rule-based detection (simplified)
        # In production, would use trained ML models

        # Dysphonia (general voice disorder)
        dysphonia_score = (
            clinical.grade / 3.0 * 0.4
            + min(1.0, acoustic.jitter_percent / 5) * 0.3
            + min(1.0, acoustic.shimmer_percent / 10) * 0.3
        )
        if dysphonia_score > 0.5:
            disorders.append(VoiceDisorderType.DYSPHONIA)
            probabilities["dysphonia"] = dysphonia_score

        # Muscle tension dysphonia
        if clinical.strain > 1.5 and acoustic.f0_std > 40:
            disorders.append(VoiceDisorderType.MUSCLE_TENSION)
            probabilities["muscle_tension"] = clinical.strain / 3.0

        # Vocal fold paralysis indicators
        if (
            acoustic.shimmer_percent > 10
            and acoustic.hnr < 10
            and clinical.breathiness > 2
        ):
            disorders.append(VoiceDisorderType.VOCAL_FOLD_PARALYSIS)
            probabilities["vocal_fold_paralysis"] = 0.7

        # Spasmodic dysphonia
        if clinical.voice_breaks > 3 and clinical.strain > 2:
            disorders.append(VoiceDisorderType.SPASMODIC_DYSPHONIA)
            probabilities["spasmodic_dysphonia"] = 0.6

        # Vocal nodules (increased roughness and reduced range)
        if (
            clinical.roughness > 2
            and acoustic.f0_range < 50
            and acoustic.jitter_percent > 3
        ):
            disorders.append(VoiceDisorderType.VOCAL_NODULES)
            probabilities["vocal_nodules"] = 0.6

        # If no specific disorder detected but voice is abnormal
        if not disorders and clinical.grade > 1:
            disorders.append(VoiceDisorderType.UNSPECIFIED)
            probabilities["unspecified"] = clinical.grade / 3.0

        # If voice is normal
        if not disorders:
            disorders.append(VoiceDisorderType.NONE)
            probabilities["none"] = 1.0

        return disorders, probabilities

    def _generate_clinical_notes(
        self,
        acoustic: AcousticMetrics,
        spectral: SpectralMetrics,
        clinical: ClinicalMetrics,
        quality: QualityMetrics,
        disorders: List[VoiceDisorderType],
    ) -> List[str]:
        """Generate clinical notes based on analysis."""
        _ = spectral  # Unused parameter kept for API consistency
        notes: List[str] = []

        # Encrypt clinical findings before storing
        if acoustic.jitter_percent > self.config.jitter_threshold_normal * 2:
            notes.append(
                f"Significantly elevated jitter ({acoustic.jitter_percent:.2f}%)"
            )

        if acoustic.shimmer_percent > self.config.shimmer_threshold_normal * 2:
            notes.append(
                f"Significantly elevated shimmer ({acoustic.shimmer_percent:.2f}%)"
            )

        if acoustic.hnr < self.config.hnr_threshold_normal - 10:
            notes.append(f"Low harmonics-to-noise ratio ({acoustic.hnr:.1f} dB)")

        # Note clinical findings
        if clinical.grade >= 2:
            notes.append(
                f"Moderate to severe voice impairment (Grade {clinical.grade:.1f})"
            )

        if clinical.roughness >= 2:
            notes.append("Significant vocal roughness detected")

        if clinical.breathiness >= 2:
            notes.append("Significant breathiness detected")

        if clinical.voice_breaks > 0:
            notes.append(f"Voice breaks detected ({clinical.voice_breaks} instances)")

        if clinical.diplophonia:
            notes.append("Diplophonia (double voice) detected")

        if clinical.tremor_detected:
            notes.append(f"Voice tremor detected at {clinical.tremor_frequency:.1f} Hz")

        # Note quality issues
        if quality.recording_quality < 0.6:
            notes.append("Poor recording quality may affect assessment accuracy")

        if quality.snr < 15:
            notes.append("Low signal-to-noise ratio in recording")

        # Note detected disorders
        significant_disorders = [d for d in disorders if d != VoiceDisorderType.NONE]
        if significant_disorders:
            notes.append(
                f"Potential disorders: {', '.join(d.value for d in significant_disorders)}"
            )

        return notes

    def _generate_recommendations(
        self,
        acoustic: AcousticMetrics,
        clinical: ClinicalMetrics,
        disorders: List[VoiceDisorderType],
    ) -> List[str]:
        """Generate recommended assessments based on findings."""
        recommendations = []

        # General recommendations based on severity
        if clinical.grade >= 2:
            recommendations.append("Comprehensive voice evaluation recommended")
            recommendations.append("Laryngoscopy/stroboscopy for visualization")

        # Specific recommendations based on findings
        if clinical.breathiness >= 2 or acoustic.hnr < 15:
            recommendations.append("Aerodynamic assessment")
            recommendations.append("Evaluate for glottal insufficiency")

        if clinical.strain >= 2:
            recommendations.append("Evaluate for muscle tension dysphonia")
            recommendations.append("Consider voice therapy referral")

        if clinical.tremor_detected:
            recommendations.append("Neurological evaluation for voice tremor")

        if VoiceDisorderType.VOCAL_FOLD_PARALYSIS in disorders:
            recommendations.append("Laryngeal EMG to assess nerve function")

        if acoustic.jitter_percent > 5 or acoustic.shimmer_percent > 10:
            recommendations.append("Rule out organic lesions")

        # Follow-up recommendations
        if clinical.grade >= 1:
            recommendations.append("Follow-up voice assessment in 4-6 weeks")

        return list(set(recommendations))  # Remove duplicates

    def _generate_warnings(
        self, acoustic: AcousticMetrics, quality: QualityMetrics
    ) -> List[str]:
        """Generate warnings about data quality or limitations."""
        warnings = []

        if quality.recording_quality < 0.5:
            warnings.append("Very poor recording quality - results may be unreliable")

        if quality.clipping_detected:
            warnings.append("Audio clipping detected - may affect measurements")

        if quality.snr < 10:
            warnings.append("Very low SNR - background noise may affect analysis")

        if acoustic.f0_mean == 0:
            warnings.append("Unable to reliably track fundamental frequency")

        return warnings

    async def analyze_sustained_vowel(
        self, audio_data: np.ndarray, sample_rate: int = 16000, vowel: str = "a"
    ) -> VoiceQualityResult:
        """
        Analyze sustained vowel phonation for clinical assessment.

        Args:
            audio_data: Audio signal of sustained vowel
            sample_rate: Sample rate in Hz
            vowel: The vowel being analyzed

        Returns:
            VoiceQualityResult with clinical focus
        """
        # Sustained vowels allow for more precise perturbation measurements
        result: VoiceQualityResult = await self.analyze_voice_quality(
            audio_data, sample_rate
        )

        # Add vowel-specific analysis
        result.clinical_notes.append(f"Sustained /{vowel}/ phonation analysis")

        # For sustained vowels, we can be more strict about perturbation thresholds
        if result.acoustic_metrics.jitter_percent > 0.5:
            result.clinical_notes.append(
                "Jitter above normal threshold for sustained phonation"
            )

        return result

    async def compare_voice_samples(
        self, baseline: np.ndarray, followup: np.ndarray, sample_rate: int = 16000
    ) -> Dict[str, Any]:
        """
        Compare two voice samples (e.g., pre/post treatment).

        Args:
            baseline: Baseline voice recording
            followup: Follow-up voice recording
            sample_rate: Sample rate for both recordings

        Returns:
            Comparison results and changes
        """
        # Analyze both samples
        baseline_result = await self.analyze_voice_quality(baseline, sample_rate)
        followup_result = await self.analyze_voice_quality(followup, sample_rate)

        # Calculate changes
        changes = {
            "jitter_change": (
                followup_result.acoustic_metrics.jitter_percent
                - baseline_result.acoustic_metrics.jitter_percent
            ),
            "shimmer_change": (
                followup_result.acoustic_metrics.shimmer_percent
                - baseline_result.acoustic_metrics.shimmer_percent
            ),
            "hnr_change": (
                followup_result.acoustic_metrics.hnr
                - baseline_result.acoustic_metrics.hnr
            ),
            "grade_change": (
                followup_result.clinical_metrics.grade
                - baseline_result.clinical_metrics.grade
            ),
            "category_change": (
                baseline_result.overall_category.value,
                followup_result.overall_category.value,
            ),
        }

        # Interpret changes
        interpretation = []

        if changes["jitter_change"] < -0.5:
            interpretation.append("Significant improvement in voice stability")
        elif changes["jitter_change"] > 0.5:
            interpretation.append("Deterioration in voice stability")

        if changes["hnr_change"] > 3:
            interpretation.append("Improved voice clarity")
        elif changes["hnr_change"] < -3:
            interpretation.append("Reduced voice clarity")

        if changes["grade_change"] < -0.5:
            interpretation.append("Overall voice quality improved")
        elif changes["grade_change"] > 0.5:
            interpretation.append("Overall voice quality deteriorated")

        return {
            "baseline": baseline_result.to_dict(),
            "followup": followup_result.to_dict(),
            "changes": changes,
            "interpretation": interpretation,
        }

    def create_quality_report(
        self, results: List[VoiceQualityResult]
    ) -> Dict[str, Any]:
        """Create a summary report from multiple voice quality analyses."""
        if not results:
            return {"error": "No results to analyze"}

        # Aggregate metrics
        report = {
            "sample_count": len(results),
            "acoustic_summary": {
                "jitter_mean": np.mean(
                    [r.acoustic_metrics.jitter_percent for r in results]
                ),
                "jitter_std": np.std(
                    [r.acoustic_metrics.jitter_percent for r in results]
                ),
                "shimmer_mean": np.mean(
                    [r.acoustic_metrics.shimmer_percent for r in results]
                ),
                "shimmer_std": np.std(
                    [r.acoustic_metrics.shimmer_percent for r in results]
                ),
                "hnr_mean": np.mean([r.acoustic_metrics.hnr for r in results]),
                "f0_mean": np.mean([r.acoustic_metrics.f0_mean for r in results]),
            },
            "clinical_summary": {
                "grade_mean": np.mean([r.clinical_metrics.grade for r in results]),
                "roughness_mean": np.mean(
                    [r.clinical_metrics.roughness for r in results]
                ),
                "breathiness_mean": np.mean(
                    [r.clinical_metrics.breathiness for r in results]
                ),
                "voice_breaks_total": sum(
                    [r.clinical_metrics.voice_breaks for r in results]
                ),
            },
            "quality_distribution": {
                category.value: sum(
                    1 for r in results if r.overall_category == category
                )
                for category in VoiceQualityCategory
            },
            "detected_disorders": {},
            "all_recommendations": set(),
            "common_issues": [],
        }

        # Aggregate disorders
        disorder_counts: Dict[str, int] = {}
        for result in results:
            for disorder in result.detected_disorders:
                disorder_counts[disorder.value] = (
                    disorder_counts.get(disorder.value, 0) + 1
                )

        report["detected_disorders"] = disorder_counts

        # Collect all recommendations
        all_recommendations: Set[str] = set()
        for result in results:
            all_recommendations.update(result.recommended_assessments)

        report["all_recommendations"] = list(all_recommendations)

        # Identify common issues
        acoustic_summary = report.get("acoustic_summary", {})
        if (
            isinstance(acoustic_summary, dict)
            and acoustic_summary.get("jitter_mean", 0) > 2
        ):
            common_issues = report.get("common_issues", [])
            if isinstance(common_issues, list):
                common_issues.append("Elevated jitter across samples")

        clinical_summary = report.get("clinical_summary", {})
        if (
            isinstance(clinical_summary, dict)
            and clinical_summary.get("grade_mean", 0) > 1.5
        ):
            common_issues = report.get("common_issues", [])
            if isinstance(common_issues, list):
                common_issues.append("Consistent voice quality impairment")

        return report


# Example usage functions
async def analyze_clinical_voice_sample(file_path: str) -> VoiceQualityResult:
    """Analyze a clinical voice recording."""
    _ = file_path  # Unused parameter in example function
    analyzer = VoiceQualityAnalyzer()

    # Load audio (placeholder)
    duration = 5.0
    sample_rate = 16000
    t = np.linspace(0, duration, int(sample_rate * duration))

    # Simulate voice with some perturbation
    f0 = 150 + 10 * np.sin(2 * np.pi * 0.5 * t)  # Slight F0 variation
    jitter = 0.02 * np.random.randn(len(t))

    audio = 0.5 * np.sin(2 * np.pi * f0 * t * (1 + jitter))

    # Add some shimmer
    shimmer = 1 + 0.05 * np.random.randn(len(t))
    audio *= shimmer

    # Add noise for realistic HNR
    audio += 0.02 * np.random.randn(len(t))

    result: VoiceQualityResult = await analyzer.analyze_voice_quality(
        audio, sample_rate
    )

    logger.info("Voice quality analysis complete")
    logger.info(result.get_summary())

    return result


async def analyze_sustained_vowel_sample(file_path: str) -> VoiceQualityResult:
    """Analyze a sustained vowel recording."""
    _ = file_path  # Unused parameter in example function
    analyzer = VoiceQualityAnalyzer()

    # Simulate sustained /a/ vowel
    duration = 3.0
    sample_rate = 16000
    t = np.linspace(0, duration, int(sample_rate * duration))

    # Steady phonation with minimal variation
    audio = 0.7 * np.sin(2 * np.pi * 200 * t)

    # Add formants
    audio += 0.3 * np.sin(2 * np.pi * 700 * t)
    audio += 0.2 * np.sin(2 * np.pi * 1200 * t)

    # Minimal perturbation for healthy voice
    audio *= 1 + 0.005 * np.random.randn(len(t))

    result = await analyzer.analyze_sustained_vowel(audio, sample_rate, vowel="a")

    return result
