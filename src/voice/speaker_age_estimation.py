"""Speaker Age Estimation Module for Medical Voice Analysis.

This module implements age estimation from voice recordings to assist
in age-appropriate medical care and demographic analysis.

HIPAA Compliance Notes:
- All PHI data processed by this module must be encrypted at rest and in transit
- Access to this module should be restricted to authorized healthcare personnel only
- Implement role-based access control (RBAC) for all age estimation functions
- Audit logs must be maintained for all PHI access and processing operations
"""

# pylint: disable=too-many-lines

import json
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

try:
    import librosa

    LIBROSA_AVAILABLE = True
except ImportError:
    librosa = None
    LIBROSA_AVAILABLE = False

import numpy as np
from scipy import signal
from scipy.ndimage import gaussian_filter1d

logger = logging.getLogger(__name__)


class AgeGroup(Enum):
    """Age groups for classification."""

    CHILD = "child"  # 3-12 years
    ADOLESCENT = "adolescent"  # 13-17 years
    YOUNG_ADULT = "young_adult"  # 18-30 years
    MIDDLE_AGED = "middle_aged"  # 31-50 years
    OLDER_ADULT = "older_adult"  # 51-70 years
    ELDERLY = "elderly"  # 71+ years


class VoiceMaturity(Enum):
    """Voice maturity stages."""

    PRE_PUBERTAL = "pre_pubertal"
    PUBERTAL = "pubertal"
    POST_PUBERTAL = "post_pubertal"
    MATURE = "mature"
    AGING = "aging"
    ADVANCED_AGING = "advanced_aging"


class AgeIndicator(Enum):
    """Voice indicators of age."""

    F0_RANGE = "f0_range"  # Fundamental frequency range
    FORMANT_FREQUENCIES = "formant_frequencies"  # Formant positions
    VOICE_TREMOR = "voice_tremor"  # Age-related tremor
    BREATHINESS = "breathiness"  # Increased with age
    HOARSENESS = "hoarseness"  # Voice roughness
    SPEECH_RATE = "speech_rate"  # Speaking speed
    PAUSE_PATTERNS = "pause_patterns"  # Pause frequency/duration
    ARTICULATION_PRECISION = "articulation_precision"  # Clarity of speech
    VOCAL_STABILITY = "vocal_stability"  # Voice steadiness
    HARMONIC_STRUCTURE = "harmonic_structure"  # Harmonic richness
    HIGH_F0 = "high_f0"  # High fundamental frequency


@dataclass
class AgeFeatures:
    """Acoustic features for age estimation."""

    # Fundamental frequency features
    f0_mean: float = 0.0
    f0_median: float = 0.0
    f0_std: float = 0.0
    f0_95th_percentile: float = 0.0
    f0_5th_percentile: float = 0.0
    f0_range: float = 0.0

    # Formant features (vocal tract length indicators)
    f1_mean: float = 0.0  # First formant
    f2_mean: float = 0.0  # Second formant
    f3_mean: float = 0.0  # Third formant
    f4_mean: float = 0.0  # Fourth formant
    formant_dispersion: float = 0.0  # Average formant spacing
    vocal_tract_length_estimate: float = 0.0

    # Voice quality features
    jitter: float = 0.0  # Pitch perturbation
    shimmer: float = 0.0  # Amplitude perturbation
    hnr: float = 0.0  # Harmonics-to-noise ratio
    cpp: float = 0.0  # Cepstral peak prominence

    # Age-related tremor
    tremor_frequency: float = 0.0
    tremor_amplitude: float = 0.0
    tremor_regularity: float = 0.0

    # Spectral features
    spectral_slope: float = 0.0
    spectral_centroid_mean: float = 0.0
    spectral_rolloff_mean: float = 0.0
    high_frequency_energy_ratio: float = 0.0

    # Temporal features
    speaking_rate: float = 0.0  # Syllables per second
    articulation_rate: float = 0.0  # Excluding pauses
    pause_frequency: float = 0.0
    pause_duration_mean: float = 0.0
    speech_rhythm_regularity: float = 0.0

    # Voice onset/offset
    voice_onset_time: float = 0.0
    voice_offset_time: float = 0.0

    # MFCC statistics
    mfcc_means: List[float] = field(default_factory=list)
    mfcc_stds: List[float] = field(default_factory=list)

    # Breathiness and hoarseness
    breathiness_index: float = 0.0
    hoarseness_index: float = 0.0
    roughness_index: float = 0.0

    # Glottal features
    glottal_closure_quotient: float = 0.0
    glottal_opening_quotient: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert features to dictionary."""
        return {
            "f0_mean": self.f0_mean,
            "f0_median": self.f0_median,
            "f0_std": self.f0_std,
            "f0_range": self.f0_range,
            "f1_mean": self.f1_mean,
            "f2_mean": self.f2_mean,
            "f3_mean": self.f3_mean,
            "formant_dispersion": self.formant_dispersion,
            "vocal_tract_length_estimate": self.vocal_tract_length_estimate,
            "jitter": self.jitter,
            "shimmer": self.shimmer,
            "hnr": self.hnr,
            "tremor_amplitude": self.tremor_amplitude,
            "speaking_rate": self.speaking_rate,
            "pause_frequency": self.pause_frequency,
            "breathiness_index": self.breathiness_index,
            "spectral_slope": self.spectral_slope,
        }


@dataclass
class AgeEstimationResult:
    """Result of age estimation analysis."""

    estimated_age: float  # Estimated age in years
    age_range: Tuple[float, float]  # Confidence interval
    age_group: AgeGroup

    # Voice maturity assessment
    voice_maturity: VoiceMaturity
    maturity_indicators: List[str] = field(default_factory=list)

    # Detailed features
    features: Optional[AgeFeatures] = None
    active_indicators: List[AgeIndicator] = field(default_factory=list)

    # Age-specific observations
    child_likelihood: float = 0.0
    adolescent_likelihood: float = 0.0
    adult_likelihood: float = 0.0
    elderly_likelihood: float = 0.0

    # Medical relevance
    developmental_stage: str = ""
    age_related_changes: List[str] = field(default_factory=list)
    clinical_considerations: List[str] = field(default_factory=list)

    # Gender estimation (affects age estimation)
    likely_gender: Optional[str] = None  # "male", "female", None
    gender_confidence: float = 0.0

    # Quality and confidence
    confidence_score: float = 0.0
    estimation_uncertainty: float = 0.0
    quality_warnings: List[str] = field(default_factory=list)

    # Processing metadata
    audio_duration: float = 0.0
    processing_time_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "estimated_age": self.estimated_age,
            "age_range": self.age_range,
            "age_group": self.age_group.value,
            "voice_maturity": self.voice_maturity.value,
            "maturity_indicators": self.maturity_indicators,
            "features": self.features.to_dict() if self.features else None,
            "active_indicators": [i.value for i in self.active_indicators],
            "child_likelihood": self.child_likelihood,
            "adolescent_likelihood": self.adolescent_likelihood,
            "adult_likelihood": self.adult_likelihood,
            "elderly_likelihood": self.elderly_likelihood,
            "developmental_stage": self.developmental_stage,
            "age_related_changes": self.age_related_changes,
            "clinical_considerations": self.clinical_considerations,
            "likely_gender": self.likely_gender,
            "gender_confidence": self.gender_confidence,
            "confidence_score": self.confidence_score,
            "estimation_uncertainty": self.estimation_uncertainty,
            "quality_warnings": self.quality_warnings,
            "audio_duration": self.audio_duration,
            "processing_time_ms": self.processing_time_ms,
        }

    def get_summary(self) -> str:
        """Get human-readable summary."""
        summary = f"Estimated Age: {self.estimated_age:.0f} years "
        summary += f"({self.age_range[0]:.0f}-{self.age_range[1]:.0f})\n"
        summary += f"Age Group: {self.age_group.value.replace('_', ' ').title()}\n"
        summary += (
            f"Voice Maturity: {self.voice_maturity.value.replace('_', ' ').title()}\n"
        )

        if self.likely_gender:
            summary += f"Likely Gender: {self.likely_gender.title()} "
            summary += f"({self.gender_confidence:.1%} confidence)\n"

        summary += f"Confidence: {self.confidence_score:.1%}"

        return summary


@dataclass
class AgeEstimationConfig:
    """Configuration for age estimation."""

    # Audio parameters
    sample_rate: int = 16000
    frame_length_ms: int = 25
    frame_shift_ms: int = 10

    # Analysis settings
    enable_gender_estimation: bool = True
    enable_developmental_analysis: bool = True
    use_formant_analysis: bool = True

    # Age boundaries
    age_boundaries: Dict[str, Tuple[int, int]] = field(
        default_factory=lambda: {
            "child": (3, 12),
            "adolescent": (13, 17),
            "young_adult": (18, 30),
            "middle_aged": (31, 50),
            "older_adult": (51, 70),
            "elderly": (71, 120),
        }
    )

    # Feature thresholds
    min_voiced_duration: float = 1.0  # Minimum seconds of voiced speech
    formant_tracking_threshold: float = 0.7

    # Model settings
    use_ml_model: bool = False
    model_path: Optional[str] = None

    # Clinical settings
    include_developmental_milestones: bool = True
    include_pathology_screening: bool = False


class SpeakerAgeEstimator:
    """
    Estimates speaker age from voice recordings using acoustic analysis.

    Uses evidence-based acoustic correlates of age including fundamental
    frequency, formants, voice quality, and temporal characteristics.
    """

    def __init__(self, config: Optional[AgeEstimationConfig] = None):
        """
        Initialize the age estimator.

        Args:
            config: Estimation configuration
        """
        self.config = config or AgeEstimationConfig()

        # Frame parameters
        self.frame_length = int(
            self.config.sample_rate * self.config.frame_length_ms / 1000
        )
        self.frame_shift = int(
            self.config.sample_rate * self.config.frame_shift_ms / 1000
        )

        # Initialize age-related patterns
        self._init_age_patterns()

        # Initialize developmental milestones
        self._init_developmental_milestones()

        logger.info(
            "SpeakerAgeEstimator initialized with sample_rate=%dHz",
            self.config.sample_rate,
        )

    def _init_age_patterns(self) -> None:
        """Initialize age-related acoustic patterns."""
        # F0 ranges by age and gender (in Hz)
        self.f0_patterns = {
            "child": {"male": (200, 300), "female": (200, 300), "neutral": (200, 300)},
            "adolescent": {
                "male": (100, 200),  # Voice change period
                "female": (180, 250),
                "neutral": (140, 225),
            },
            "young_adult": {
                "male": (85, 155),
                "female": (165, 255),
                "neutral": (125, 205),
            },
            "middle_aged": {
                "male": (85, 145),
                "female": (165, 245),
                "neutral": (125, 195),
            },
            "older_adult": {
                "male": (90, 150),
                "female": (170, 240),
                "neutral": (130, 195),
            },
            "elderly": {
                "male": (95, 155),  # F0 increases with age in elderly
                "female": (175, 230),  # F0 decreases with age in elderly
                "neutral": (135, 192),
            },
        }

        # Formant patterns (vocal tract length indicators)
        self.formant_patterns = {
            "child": {
                "f1": (700, 1000),
                "f2": (1800, 2800),
                "f3": (3000, 4000),
                "vtl": (12, 14),  # cm
            },
            "adolescent": {
                "f1": (650, 850),
                "f2": (1500, 2400),
                "f3": (2700, 3500),
                "vtl": (14, 16),
            },
            "adult_male": {
                "f1": (500, 700),
                "f2": (1200, 1800),
                "f3": (2300, 3000),
                "vtl": (16, 18),
            },
            "adult_female": {
                "f1": (600, 800),
                "f2": (1400, 2200),
                "f3": (2600, 3300),
                "vtl": (14, 16),
            },
        }

        # Voice quality patterns by age
        self.voice_quality_patterns = {
            "child": {
                "jitter": (0.002, 0.01),
                "shimmer": (0.02, 0.05),
                "hnr": (15, 25),
            },
            "young_adult": {
                "jitter": (0.001, 0.005),
                "shimmer": (0.015, 0.03),
                "hnr": (20, 30),
            },
            "elderly": {
                "jitter": (0.005, 0.02),
                "shimmer": (0.03, 0.08),
                "hnr": (10, 20),
            },
        }

        # Speaking rate patterns (syllables per second)
        self.speaking_rate_patterns = {
            "child": (3.5, 5.0),
            "adolescent": (4.0, 5.5),
            "young_adult": (4.5, 6.0),
            "middle_aged": (4.0, 5.5),
            "older_adult": (3.5, 5.0),
            "elderly": (3.0, 4.5),
        }

    def _init_developmental_milestones(self) -> None:
        """Initialize developmental milestones for age estimation."""
        self.developmental_milestones = {
            3: "Basic phoneme production established",
            5: "Most speech sounds correctly produced",
            7: "Adult-like speech rhythm emerging",
            10: "Pre-pubertal voice characteristics stable",
            13: "Voice change beginning (males)",
            15: "Voice change ongoing",
            18: "Adult voice characteristics established",
            25: "Peak vocal performance",
            50: "Age-related voice changes beginning",
            65: "Presbyphonia risk increasing",
            75: "Advanced age-related voice changes common",
        }

    async def estimate_age(
        self, audio_data: np.ndarray, known_gender: Optional[str] = None
    ) -> AgeEstimationResult:
        """
        Estimate speaker age from audio data.

        Args:
            audio_data: Audio signal as numpy array
            known_gender: Optional known gender ("male" or "female")

        Returns:
            AgeEstimationResult with age estimation and analysis
        """
        start_time = datetime.now()

        try:
            # Normalize audio
            audio_data = self._normalize_audio(audio_data)

            # Extract age-related features
            features = await self._extract_age_features(audio_data)

            # Estimate gender if not provided and enabled
            likely_gender = known_gender
            gender_confidence = 1.0 if known_gender else 0.0

            if not known_gender and self.config.enable_gender_estimation:
                likely_gender, gender_confidence = await self._estimate_gender(features)

            # Calculate age likelihoods for each group
            age_likelihoods = self._calculate_age_likelihoods(features, likely_gender)

            # Estimate age and confidence interval
            estimated_age, age_range = self._estimate_age_value(
                features, age_likelihoods, likely_gender
            )

            # Determine age group
            age_group = self._determine_age_group(estimated_age)

            # Assess voice maturity
            voice_maturity, maturity_indicators = self._assess_voice_maturity(
                features, estimated_age, likely_gender
            )

            # Identify active age indicators
            active_indicators = self._identify_active_indicators(
                features, estimated_age
            )

            # Determine developmental stage
            developmental_stage = ""
            if self.config.enable_developmental_analysis:
                developmental_stage = self._determine_developmental_stage(
                    estimated_age, features
                )

            # Identify age-related changes
            age_related_changes = self._identify_age_related_changes(
                features, estimated_age
            )

            # Generate clinical considerations
            clinical_considerations = self._generate_clinical_considerations(
                estimated_age, age_group, voice_maturity, features
            )

            # Calculate confidence and uncertainty
            confidence = self._calculate_confidence(features, age_likelihoods)
            uncertainty = self._calculate_uncertainty(features, age_range)

            # Generate quality warnings
            warnings = self._generate_quality_warnings(features, confidence)

            # Processing time
            processing_time = (datetime.now() - start_time).total_seconds() * 1000

            return AgeEstimationResult(
                estimated_age=estimated_age,
                age_range=age_range,
                age_group=age_group,
                voice_maturity=voice_maturity,
                maturity_indicators=maturity_indicators,
                features=features,
                active_indicators=active_indicators,
                child_likelihood=age_likelihoods.get("child", 0.0),
                adolescent_likelihood=age_likelihoods.get("adolescent", 0.0),
                adult_likelihood=age_likelihoods.get("adult", 0.0),
                elderly_likelihood=age_likelihoods.get("elderly", 0.0),
                developmental_stage=developmental_stage,
                age_related_changes=age_related_changes,
                clinical_considerations=clinical_considerations,
                likely_gender=likely_gender,
                gender_confidence=gender_confidence,
                confidence_score=confidence,
                estimation_uncertainty=uncertainty,
                quality_warnings=warnings,
                audio_duration=len(audio_data) / self.config.sample_rate,
                processing_time_ms=processing_time,
            )

        except Exception as e:
            logger.error("Error in age estimation: %s", str(e), exc_info=True)
            raise

    def _normalize_audio(self, audio_data: np.ndarray) -> np.ndarray:
        """Normalize audio to [-1, 1] range."""
        max_val = np.max(np.abs(audio_data))
        if max_val > 0:
            normalized: np.ndarray = (audio_data / max_val).astype(audio_data.dtype)
            return normalized
        return audio_data

    async def _extract_age_features(self, audio_data: np.ndarray) -> AgeFeatures:
        """Extract comprehensive age-related features."""
        features = AgeFeatures()

        # Extract F0 features
        f0_features = self._extract_f0_features(audio_data)
        features.f0_mean = f0_features["mean"]
        features.f0_median = f0_features["median"]
        features.f0_std = f0_features["std"]
        features.f0_95th_percentile = f0_features["95th"]
        features.f0_5th_percentile = f0_features["5th"]
        features.f0_range = f0_features["range"]

        # Extract formant features
        if self.config.use_formant_analysis:
            formant_features = await self._extract_formant_features(audio_data)
            features.f1_mean = formant_features["f1"]
            features.f2_mean = formant_features["f2"]
            features.f3_mean = formant_features["f3"]
            features.f4_mean = formant_features["f4"]
            features.formant_dispersion = formant_features["dispersion"]
            features.vocal_tract_length_estimate = formant_features["vtl_estimate"]

        # Extract voice quality features
        quality_features = self._extract_voice_quality_features(audio_data)
        features.jitter = quality_features["jitter"]
        features.shimmer = quality_features["shimmer"]
        features.hnr = quality_features["hnr"]
        features.cpp = quality_features["cpp"]

        # Extract tremor features
        tremor_features = self._extract_tremor_features(audio_data)
        features.tremor_frequency = tremor_features["frequency"]
        features.tremor_amplitude = tremor_features["amplitude"]
        features.tremor_regularity = tremor_features["regularity"]

        # Extract spectral features
        spectral_features = self._extract_spectral_features(audio_data)
        features.spectral_slope = spectral_features["slope"]
        features.spectral_centroid_mean = spectral_features["centroid"]
        features.spectral_rolloff_mean = spectral_features["rolloff"]
        features.high_frequency_energy_ratio = spectral_features["hf_ratio"]

        # Extract temporal features
        temporal_features = self._extract_temporal_features(audio_data)
        features.speaking_rate = temporal_features["speaking_rate"]
        features.articulation_rate = temporal_features["articulation_rate"]
        features.pause_frequency = temporal_features["pause_frequency"]
        features.pause_duration_mean = temporal_features["pause_duration"]
        features.speech_rhythm_regularity = temporal_features["rhythm_regularity"]

        # Extract MFCC features
        mfcc_features = self._extract_mfcc_features(audio_data)
        features.mfcc_means = mfcc_features["means"]
        features.mfcc_stds = mfcc_features["stds"]

        # Extract breathiness and hoarseness
        breath_hoarse_features = self._extract_breathiness_hoarseness(audio_data)
        features.breathiness_index = breath_hoarse_features["breathiness"]
        features.hoarseness_index = breath_hoarse_features["hoarseness"]
        features.roughness_index = breath_hoarse_features["roughness"]

        # Extract glottal features
        glottal_features = self._extract_glottal_features(audio_data)
        features.glottal_closure_quotient = glottal_features["closure_quotient"]
        features.glottal_opening_quotient = glottal_features["opening_quotient"]

        return features

    def _extract_f0_features(self, audio_data: np.ndarray) -> Dict[str, float]:
        """Extract fundamental frequency features."""
        if not LIBROSA_AVAILABLE:
            logger.warning("librosa not available, returning default F0 features")
            return {
                "mean": 0.0,
                "median": 0.0,
                "std": 0.0,
                "95th": 0.0,
                "5th": 0.0,
                "range": 0.0,
            }

        # Extract F0 using YIN algorithm
        f0 = librosa.yin(
            audio_data,
            fmin=50,
            fmax=500,
            sr=self.config.sample_rate,
            frame_length=self.frame_length * 4,
            hop_length=self.frame_shift,
        )

        # Remove unvoiced segments
        voiced_f0 = f0[f0 > 0]

        features = {
            "mean": 0.0,
            "median": 0.0,
            "std": 0.0,
            "95th": 0.0,
            "5th": 0.0,
            "range": 0.0,
        }

        if len(voiced_f0) > 10:
            features["mean"] = np.mean(voiced_f0)
            features["median"] = np.median(voiced_f0)
            features["std"] = np.std(voiced_f0)
            features["95th"] = np.percentile(voiced_f0, 95)
            features["5th"] = np.percentile(voiced_f0, 5)
            features["range"] = features["95th"] - features["5th"]

        return features

    async def _extract_formant_features(
        self, audio_data: np.ndarray
    ) -> Dict[str, float]:
        """Extract formant frequencies using LPC analysis."""
        features = {
            "f1": 0.0,
            "f2": 0.0,
            "f3": 0.0,
            "f4": 0.0,
            "dispersion": 0.0,
            "vtl_estimate": 17.0,  # Default adult VTL in cm
        }

        # Process in frames
        formant_tracks: Dict[str, List[float]] = {f"f{i}": [] for i in range(1, 5)}

        # Window for analysis
        window_size = self.frame_length * 2
        hop_size = self.frame_shift

        for i in range(0, len(audio_data) - window_size, hop_size):
            frame = audio_data[i : i + window_size]

            # Pre-emphasis
            pre_emphasis = 0.97
            emphasized = np.append(frame[0], frame[1:] - pre_emphasis * frame[:-1])

            # Apply window
            windowed = emphasized * np.hamming(len(emphasized))

            # Skip if energy too low
            if np.sum(windowed**2) < 0.01:
                continue

            # LPC analysis
            try:
                # LPC order based on sampling rate
                lpc_order = min(
                    int(self.config.sample_rate / 1000) + 4, len(windowed) - 1
                )

                # Get LPC coefficients
                a = librosa.lpc(windowed, order=lpc_order)

                # Find roots
                roots = np.roots(a)

                # Convert to frequencies
                angles = []
                for root in roots:
                    if np.imag(root) >= 0:  # Keep only positive frequencies
                        angle = np.angle(root)
                        freq = angle * self.config.sample_rate / (2 * np.pi)
                        if 200 < freq < 5000:  # Formant range
                            angles.append(freq)

                # Sort and assign to formants
                angles.sort()
                for j, freq in enumerate(angles[:4]):
                    if j < 4:
                        formant_tracks[f"f{j+1}"].append(freq)

            except (ValueError, IndexError, KeyError) as e:
                logger.debug("Error extracting formants for frame: %s", e)
                continue

        # Calculate mean formants
        for i in range(1, 5):
            track = formant_tracks[f"f{i}"]
            if track:
                features[f"f{i}"] = float(np.median(track))  # Use median for robustness

        # Calculate formant dispersion
        formants = [features[f"f{i}"] for i in range(1, 5) if features[f"f{i}"] > 0]
        if len(formants) >= 3:
            # Average spacing between consecutive formants
            spacings = np.diff(formants)
            features["dispersion"] = np.mean(spacings)

            # Estimate vocal tract length using formant dispersion
            # VTL ≈ c / (2 * formant_dispersion), where c is speed of sound
            c = 35000  # cm/s
            if features["dispersion"] > 0:
                features["vtl_estimate"] = c / (2 * features["dispersion"])

        return features

    def _extract_voice_quality_features(
        self, audio_data: np.ndarray
    ) -> Dict[str, float]:
        """Extract voice quality features (jitter, shimmer, HNR, CPP)."""
        features = {"jitter": 0.0, "shimmer": 0.0, "hnr": 0.0, "cpp": 0.0}

        # Extract F0 for jitter calculation
        f0 = librosa.yin(
            audio_data,
            fmin=50,
            fmax=500,
            sr=self.config.sample_rate,
            frame_length=self.frame_length * 4,
            hop_length=self.frame_shift,
        )

        voiced_f0 = f0[f0 > 0]

        # Jitter (pitch perturbation)
        if len(voiced_f0) > 2:
            periods = 1.0 / voiced_f0
            period_diffs = np.abs(np.diff(periods))
            features["jitter"] = (
                np.mean(period_diffs) / np.mean(periods) if np.mean(periods) > 0 else 0
            )

        # Shimmer (amplitude perturbation)
        # Find peaks in the signal
        frame_length = int(0.03 * self.config.sample_rate)  # 30ms frames
        peak_amplitudes = []

        for i in range(0, len(audio_data) - frame_length, frame_length // 2):
            frame = audio_data[i : i + frame_length]
            peaks, _ = signal.find_peaks(
                np.abs(frame), height=np.max(np.abs(frame)) * 0.7
            )
            if len(peaks) > 0:
                peak_amplitudes.extend(np.abs(frame[peaks]))

        if len(peak_amplitudes) > 2:
            peak_amplitudes_array = np.array(peak_amplitudes)
            amp_diffs = np.abs(np.diff(peak_amplitudes_array))
            features["shimmer"] = (
                np.mean(amp_diffs) / np.mean(peak_amplitudes_array)
                if np.mean(peak_amplitudes_array) > 0
                else 0
            )

        # HNR (Harmonics-to-Noise Ratio)
        features["hnr"] = self._calculate_hnr(audio_data)

        # CPP (Cepstral Peak Prominence)
        features["cpp"] = self._calculate_cpp(audio_data)

        return features

    def _calculate_hnr(self, audio_data: np.ndarray) -> float:
        """Calculate Harmonics-to-Noise Ratio."""
        # Frame-based HNR calculation
        frame_length = int(0.04 * self.config.sample_rate)  # 40ms frames
        hop_length = frame_length // 2
        hnr_values = []

        for i in range(0, len(audio_data) - frame_length, hop_length):
            frame = audio_data[i : i + frame_length]

            # Skip low energy frames
            if np.max(np.abs(frame)) < 0.01:
                continue

            # Autocorrelation
            autocorr = np.correlate(frame, frame, mode="full")
            autocorr = autocorr[len(autocorr) // 2 :]

            # Find first peak (fundamental period)
            min_lag = int(self.config.sample_rate / 500)  # 500 Hz max
            max_lag = int(self.config.sample_rate / 50)  # 50 Hz min

            if max_lag < len(autocorr):
                search_region = autocorr[min_lag:max_lag]
                if len(search_region) > 0:
                    peak_idx = np.argmax(search_region) + min_lag

                    # HNR calculation
                    if autocorr[0] > 0:
                        r0 = autocorr[0]
                        r1 = autocorr[peak_idx]

                        if r1 > 0 and r1 < r0:
                            hnr = 10 * np.log10(r1 / (r0 - r1))
                            hnr_values.append(hnr)

        return np.mean(hnr_values) if hnr_values else 0.0

    def _calculate_cpp(self, audio_data: np.ndarray) -> float:
        """Calculate Cepstral Peak Prominence."""
        # Frame-based CPP calculation
        frame_length = int(0.04 * self.config.sample_rate)
        hop_length = frame_length // 2
        cpp_values = []

        for i in range(0, len(audio_data) - frame_length, hop_length):
            frame = audio_data[i : i + frame_length]

            # Skip low energy frames
            if np.max(np.abs(frame)) < 0.01:
                continue

            # Window the frame
            windowed = frame * np.hamming(len(frame))

            # Compute cepstrum
            spectrum = np.fft.fft(windowed, n=4096)
            log_spectrum = np.log(np.abs(spectrum) + 1e-10)
            cepstrum = np.real(np.fft.ifft(log_spectrum))

            # Focus on speech quefrency range
            min_quefrency = int(self.config.sample_rate / 300)  # 300 Hz max
            max_quefrency = int(self.config.sample_rate / 60)  # 60 Hz min

            if max_quefrency < len(cepstrum) // 2:
                speech_cepstrum = cepstrum[min_quefrency:max_quefrency]

                if len(speech_cepstrum) > 0:
                    # Find peak
                    peak_idx = np.argmax(speech_cepstrum)
                    peak_val = speech_cepstrum[peak_idx]

                    # Calculate prominence (peak relative to regression line)
                    quefrencies = np.arange(len(speech_cepstrum))

                    # Fit regression line
                    if len(quefrencies) > 10:
                        slope, intercept = np.polyfit(quefrencies, speech_cepstrum, 1)
                        regression_val = slope * peak_idx + intercept

                        cpp = peak_val - regression_val
                        cpp_values.append(cpp)

        return np.mean(cpp_values) if cpp_values else 0.0

    def _extract_tremor_features(self, audio_data: np.ndarray) -> Dict[str, float]:
        """Extract age-related tremor features."""
        features = {"frequency": 0.0, "amplitude": 0.0, "regularity": 0.0}

        # Extract F0 contour
        f0 = librosa.yin(
            audio_data,
            fmin=50,
            fmax=500,
            sr=self.config.sample_rate,
            frame_length=self.frame_length * 4,
            hop_length=self.frame_shift,
        )

        # Remove unvoiced segments
        voiced_indices = np.where(f0 > 0)[0]

        if len(voiced_indices) > 30:  # Need sufficient data
            voiced_f0 = f0[voiced_indices]

            # Detrend to focus on tremor
            detrended_f0 = signal.detrend(voiced_f0)

            # Compute power spectrum
            fs = self.config.sample_rate / self.frame_shift  # F0 sampling rate

            # Look for tremor in 3-15 Hz range
            nperseg = min(256, len(detrended_f0) // 4)
            if nperseg > 16:
                freqs, psd = signal.welch(detrended_f0, fs=fs, nperseg=nperseg)

                # Find tremor frequency range
                tremor_mask = (freqs >= 3) & (freqs <= 15)

                if np.any(tremor_mask):
                    tremor_psd = psd[tremor_mask]
                    tremor_freqs = freqs[tremor_mask]

                    # Find peak in tremor range
                    peak_idx = np.argmax(tremor_psd)
                    features["frequency"] = tremor_freqs[peak_idx]

                    # Tremor amplitude (std of detrended F0)
                    features["amplitude"] = np.std(detrended_f0)

                    # Regularity (peak prominence in spectrum)
                    if np.sum(psd) > 0:
                        features["regularity"] = tremor_psd[peak_idx] / np.sum(psd)

        return features

    def _extract_spectral_features(self, audio_data: np.ndarray) -> Dict[str, float]:
        """Extract spectral features relevant to age."""
        features = {"slope": 0.0, "centroid": 0.0, "rolloff": 0.0, "hf_ratio": 0.0}

        # STFT
        stft = librosa.stft(
            audio_data, n_fft=self.frame_length * 2, hop_length=self.frame_shift
        )
        magnitude = np.abs(stft)
        freqs = librosa.fft_frequencies(
            sr=self.config.sample_rate, n_fft=self.frame_length * 2
        )

        # Spectral slope (overall tilt)
        slopes = []
        for frame_idx in range(magnitude.shape[1]):
            frame_mag = magnitude[:, frame_idx]
            if np.sum(frame_mag) > 0:
                # Linear regression of log magnitude vs log frequency
                valid_idx = (freqs > 100) & (frame_mag > 0)
                if np.sum(valid_idx) > 10:
                    log_freq = np.log(freqs[valid_idx])
                    log_mag = np.log(frame_mag[valid_idx] + 1e-10)
                    slope, _ = np.polyfit(log_freq, log_mag, 1)
                    slopes.append(slope)

        if slopes:
            features["slope"] = np.mean(slopes)

        # Spectral centroid
        centroid = librosa.feature.spectral_centroid(
            y=audio_data, sr=self.config.sample_rate, hop_length=self.frame_shift
        )[0]
        if len(centroid) > 0:
            features["centroid"] = np.mean(centroid)

        # Spectral rolloff
        rolloff = librosa.feature.spectral_rolloff(
            y=audio_data,
            sr=self.config.sample_rate,
            hop_length=self.frame_shift,
            roll_percent=0.85,
        )[0]
        if len(rolloff) > 0:
            features["rolloff"] = np.mean(rolloff)

        # High frequency energy ratio
        # Elderly voices often have reduced high frequency energy
        total_energy = np.sum(magnitude**2, axis=0)
        high_freq_idx = freqs > 4000
        high_energy = np.sum(magnitude[high_freq_idx, :] ** 2, axis=0)

        valid_frames = total_energy > 0
        if np.any(valid_frames):
            hf_ratios = high_energy[valid_frames] / total_energy[valid_frames]
            features["hf_ratio"] = np.mean(hf_ratios)

        return features

    def _extract_temporal_features(self, audio_data: np.ndarray) -> Dict[str, float]:
        """Extract temporal features (speaking rate, pauses, rhythm)."""
        features = {
            "speaking_rate": 0.0,
            "articulation_rate": 0.0,
            "pause_frequency": 0.0,
            "pause_duration": 0.0,
            "rhythm_regularity": 0.0,
        }

        # Energy envelope for syllable detection
        energy = librosa.feature.rms(
            y=audio_data, frame_length=self.frame_length, hop_length=self.frame_shift
        )[0]

        # Smooth energy
        smooth_energy = gaussian_filter1d(energy, sigma=2)

        # Find peaks (syllable nuclei)
        mean_energy = np.mean(smooth_energy)
        peaks, _ = signal.find_peaks(
            smooth_energy, height=mean_energy * 1.2, distance=5
        )  # Min distance between syllables

        duration = len(audio_data) / self.config.sample_rate

        if duration > 0:
            # Speaking rate (syllables per second)
            features["speaking_rate"] = len(peaks) / duration

            # Detect pauses
            pause_threshold = mean_energy * 0.1
            is_pause = smooth_energy < pause_threshold

            # Find pause segments
            pause_durations = []
            pause_count = 0
            in_pause = False
            pause_start = 0

            for i, frame_is_pause in enumerate(is_pause):
                if frame_is_pause and not in_pause:
                    pause_start = i
                    in_pause = True
                elif not frame_is_pause and in_pause:
                    pause_duration = (
                        (i - pause_start) * self.frame_shift / self.config.sample_rate
                    )
                    if pause_duration > 0.2:  # Minimum pause duration
                        pause_durations.append(pause_duration)
                        pause_count += 1
                    in_pause = False

            # Pause frequency (pauses per minute)
            features["pause_frequency"] = pause_count * 60 / duration

            # Average pause duration
            if pause_durations:
                features["pause_duration"] = float(np.mean(pause_durations))

            # Articulation rate (syllables per second excluding pauses)
            total_pause_time = sum(pause_durations)
            speech_time = duration - total_pause_time
            if speech_time > 0:
                features["articulation_rate"] = len(peaks) / speech_time
            else:
                features["articulation_rate"] = features["speaking_rate"]

            # Rhythm regularity (based on inter-syllable intervals)
            if len(peaks) > 2:
                intervals = np.diff(peaks) * self.frame_shift / self.config.sample_rate
                # Coefficient of variation of intervals
                if np.mean(intervals) > 0:
                    cv = np.std(intervals) / np.mean(intervals)
                    features["rhythm_regularity"] = float(
                        1 / (1 + cv)
                    )  # Higher value = more regular

        return features

    def _extract_mfcc_features(self, audio_data: np.ndarray) -> Dict[str, List[float]]:
        """Extract MFCC features for age modeling."""
        # Extract MFCCs
        mfcc = librosa.feature.mfcc(
            y=audio_data,
            sr=self.config.sample_rate,
            n_mfcc=13,
            hop_length=self.frame_shift,
        )

        features = {
            "means": mfcc.mean(axis=1).tolist(),
            "stds": mfcc.std(axis=1).tolist(),
        }

        return features

    def _extract_breathiness_hoarseness(
        self, audio_data: np.ndarray
    ) -> Dict[str, float]:
        """Extract breathiness and hoarseness indices."""
        features = {"breathiness": 0.0, "hoarseness": 0.0, "roughness": 0.0}

        # STFT for spectral analysis
        stft = librosa.stft(
            audio_data, n_fft=self.frame_length * 2, hop_length=self.frame_shift
        )
        magnitude = np.abs(stft)

        # Breathiness (H1-H2 and spectral tilt)
        breathiness_scores = []

        for frame_idx in range(magnitude.shape[1]):
            frame_mag = magnitude[:, frame_idx]

            # Find harmonic peaks
            peaks, _ = signal.find_peaks(frame_mag, height=np.max(frame_mag) * 0.1)

            if len(peaks) >= 2:
                # H1-H2 difference
                h1_h2 = frame_mag[peaks[0]] - frame_mag[peaks[1]]
                if frame_mag[peaks[0]] > 0:
                    breathiness_scores.append(h1_h2 / frame_mag[peaks[0]])

        if breathiness_scores:
            features["breathiness"] = min(1.0, np.mean(breathiness_scores))

        # Hoarseness (spectral noise)
        # Using cepstral peak prominence as inverse indicator
        cpp = self._calculate_cpp(audio_data)
        features["hoarseness"] = max(0, 1 - cpp / 20)  # Normalize CPP to hoarseness

        # Roughness (amplitude perturbation and subharmonics)
        # Extract amplitude envelope
        amplitude = librosa.feature.rms(
            y=audio_data, frame_length=self.frame_length, hop_length=self.frame_shift
        )[0]

        if len(amplitude) > 2:
            # Short-term amplitude variation
            amp_diff = np.abs(np.diff(amplitude))
            features["roughness"] = min(
                1.0, np.mean(amp_diff) / (np.mean(amplitude) + 1e-10) * 10
            )

        return features

    def _extract_glottal_features(self, audio_data: np.ndarray) -> Dict[str, float]:
        """Extract glottal source features (simplified)."""
        features = {
            "closure_quotient": 0.5,  # Default
            "opening_quotient": 0.5,  # Default
        }

        # Simplified glottal feature extraction using zero crossing rate
        # and energy patterns

        # Frame-based analysis
        frame_length = int(0.02 * self.config.sample_rate)  # 20ms
        hop_length = frame_length // 2

        closure_quotients = []

        for i in range(0, len(audio_data) - frame_length, hop_length):
            frame = audio_data[i : i + frame_length]

            # Find glottal cycles using zero crossings
            zero_crossings = np.where(np.diff(np.sign(frame)))[0]

            if len(zero_crossings) > 2:
                # Estimate closure phase (simplified)
                # Higher energy portion typically corresponds to closed phase
                energy_profile = frame**2
                threshold = np.mean(energy_profile)

                closed_samples = np.sum(energy_profile > threshold)
                closure_quotient = closed_samples / len(frame)
                closure_quotients.append(closure_quotient)

        if closure_quotients:
            features["closure_quotient"] = np.mean(closure_quotients)
            features["opening_quotient"] = 1 - features["closure_quotient"]

        return features

    async def _estimate_gender(
        self, features: AgeFeatures
    ) -> Tuple[Optional[str], float]:
        """Estimate gender from voice features."""
        # Simple gender estimation based on F0 and formants
        male_score = 0.0
        female_score = 0.0

        # F0-based estimation
        if features.f0_mean > 0:
            if features.f0_mean < 160:
                male_score += 0.4
            elif features.f0_mean > 180:
                female_score += 0.4
            else:
                # Ambiguous range
                male_score += 0.2
                female_score += 0.2

        # Formant-based estimation
        if features.f1_mean > 0 and features.f2_mean > 0:
            # Lower formants indicate longer vocal tract (typically male)
            if features.f1_mean < 600 and features.f2_mean < 1600:
                male_score += 0.3
            elif features.f1_mean > 700 and features.f2_mean > 1800:
                female_score += 0.3
            else:
                male_score += 0.15
                female_score += 0.15

        # Voice quality can also differ
        if features.breathiness_index > 0.5:
            female_score += 0.1  # Females tend to have breathier voices

        # Normalize scores
        total_score = male_score + female_score
        if total_score > 0:
            male_score /= total_score
            female_score /= total_score

        # Determine gender and confidence
        if male_score > female_score:
            return "male", male_score
        elif female_score > male_score:
            return "female", female_score
        else:
            return None, 0.5

    def _calculate_age_likelihoods(
        self, features: AgeFeatures, gender: Optional[str]
    ) -> Dict[str, float]:
        """Calculate likelihood scores for each age group."""
        likelihoods = {}

        # Use gender-specific patterns if available
        gender_key = gender if gender in ["male", "female"] else "neutral"

        # Child likelihood
        child_score = 0.0
        if features.f0_mean > 0:
            child_f0_range = self.f0_patterns["child"][gender_key]
            if child_f0_range[0] <= features.f0_mean <= child_f0_range[1]:
                child_score += 0.3

            # High F0 variance common in children
            if features.f0_std > 30:
                child_score += 0.1

        # High formants indicate short vocal tract
        if features.f1_mean > 800 and features.f2_mean > 2000:
            child_score += 0.2

        # Fast speaking rate
        if features.speaking_rate > 4.5:
            child_score += 0.1

        # Good voice quality
        if features.jitter < 0.005 and features.shimmer < 0.03:
            child_score += 0.1

        # Low breathiness
        if features.breathiness_index < 0.3:
            child_score += 0.1

        likelihoods["child"] = min(1.0, child_score)

        # Adolescent likelihood
        adolescent_score = 0.0
        if gender == "male":
            # Voice change indicators
            if 100 <= features.f0_mean <= 200:
                adolescent_score += 0.3
            if features.f0_std > 40:  # Voice instability
                adolescent_score += 0.2
            if features.jitter > 0.005:
                adolescent_score += 0.1
        else:
            adolescent_f0_range = self.f0_patterns["adolescent"]["female"]
            if adolescent_f0_range[0] <= features.f0_mean <= adolescent_f0_range[1]:
                adolescent_score += 0.3

        # Moderate speaking rate
        if 4.0 <= features.speaking_rate <= 5.5:
            adolescent_score += 0.1

        # Some voice quality issues during change
        if 0.003 <= features.jitter <= 0.01:
            adolescent_score += 0.1

        likelihoods["adolescent"] = min(1.0, adolescent_score)

        # Adult likelihood (combining young and middle-aged)
        adult_score = 0.0

        # Check F0 for adult range
        for age_group in ["young_adult", "middle_aged"]:
            f0_range = self.f0_patterns[age_group][gender_key]
            if f0_range[0] <= features.f0_mean <= f0_range[1]:
                adult_score += 0.2
                break

        # Stable voice
        if features.f0_std < 25:
            adult_score += 0.1

        # Good voice quality
        if features.hnr > 20:
            adult_score += 0.15
        if features.cpp > 10:
            adult_score += 0.15

        # Moderate formants
        if 500 <= features.f1_mean <= 800:
            adult_score += 0.1

        # Regular speech rhythm
        if features.speech_rhythm_regularity > 0.7:
            adult_score += 0.1

        # Low tremor
        if features.tremor_amplitude < 5:
            adult_score += 0.1

        likelihoods["adult"] = min(1.0, adult_score)

        # Elderly likelihood
        elderly_score = 0.0

        # F0 changes in elderly
        elderly_f0_range = self.f0_patterns["elderly"][gender_key]
        if elderly_f0_range[0] <= features.f0_mean <= elderly_f0_range[1]:
            elderly_score += 0.2

        # Voice quality deterioration
        if features.jitter > 0.008:
            elderly_score += 0.15
        if features.shimmer > 0.05:
            elderly_score += 0.15
        if features.hnr < 15:
            elderly_score += 0.1

        # Tremor presence
        if features.tremor_frequency > 0 and 4 <= features.tremor_frequency <= 8:
            elderly_score += 0.1

        # Slower speaking rate
        if features.speaking_rate < 4.0:
            elderly_score += 0.1

        # More pauses
        if features.pause_frequency > 15:
            elderly_score += 0.05

        # Reduced high frequency energy
        if features.high_frequency_energy_ratio < 0.1:
            elderly_score += 0.1

        # Increased breathiness
        if features.breathiness_index > 0.5:
            elderly_score += 0.05

        likelihoods["elderly"] = min(1.0, elderly_score)

        # Normalize likelihoods
        total = sum(likelihoods.values())
        if total > 0:
            for key in likelihoods:
                likelihoods[key] /= total

        return likelihoods

    def _estimate_age_value(
        self,
        features: AgeFeatures,
        likelihoods: Dict[str, float],
        gender: Optional[str],
    ) -> Tuple[float, Tuple[float, float]]:
        """Estimate specific age value and confidence interval."""
        # Age range centers for each group
        age_centers = {"child": 8, "adolescent": 15, "adult": 35, "elderly": 75}

        # Initial estimate based on weighted average
        weighted_age = sum(
            likelihoods.get(group, 0) * center for group, center in age_centers.items()
        )

        # Refine based on specific features
        age_adjustment = 0.0

        # F0-based refinement
        if gender == "male" and features.f0_mean > 0:
            if features.f0_mean > 120:  # Higher than typical adult male
                age_adjustment -= 5
            elif features.f0_mean < 100:  # Lower than typical
                age_adjustment += 5
        elif gender == "female" and features.f0_mean > 0:
            if features.f0_mean > 220:  # Higher than typical adult female
                age_adjustment -= 5
            elif features.f0_mean < 180:  # Lower than typical
                age_adjustment += 5

        # Voice quality refinement
        quality_score = (features.jitter * 1000 + features.shimmer * 100) / 2
        if quality_score > 10:  # Poor voice quality
            age_adjustment += 10
        elif quality_score < 3:  # Excellent voice quality
            age_adjustment -= 5

        # Speaking rate refinement
        if features.speaking_rate > 5.5:
            age_adjustment -= 3
        elif features.speaking_rate < 3.5:
            age_adjustment += 5

        # Apply adjustment
        estimated_age = weighted_age + age_adjustment
        estimated_age = max(3, min(100, estimated_age))  # Clamp to reasonable range

        # Calculate confidence interval
        # Higher uncertainty for ambiguous cases
        max_likelihood = max(likelihoods.values()) if likelihoods else 0.5
        base_uncertainty = 10 * (1 - max_likelihood)

        # Additional uncertainty factors
        if features.f0_mean == 0:  # Missing F0
            base_uncertainty += 5
        if features.f1_mean == 0:  # Missing formants
            base_uncertainty += 3

        # Age-specific uncertainty
        if estimated_age < 18:
            base_uncertainty *= 0.8  # More precise for children/adolescents
        elif estimated_age > 60:
            base_uncertainty *= 1.2  # Less precise for elderly

        # Calculate interval
        lower_bound = max(3, estimated_age - base_uncertainty)
        upper_bound = min(100, estimated_age + base_uncertainty)

        return estimated_age, (lower_bound, upper_bound)

    def _determine_age_group(self, age: float) -> AgeGroup:
        """Determine age group from estimated age."""
        boundaries = self.config.age_boundaries

        if age <= boundaries["child"][1]:
            return AgeGroup.CHILD
        elif age <= boundaries["adolescent"][1]:
            return AgeGroup.ADOLESCENT
        elif age <= boundaries["young_adult"][1]:
            return AgeGroup.YOUNG_ADULT
        elif age <= boundaries["middle_aged"][1]:
            return AgeGroup.MIDDLE_AGED
        elif age <= boundaries["older_adult"][1]:
            return AgeGroup.OLDER_ADULT
        else:
            return AgeGroup.ELDERLY

    def _assess_voice_maturity(
        self, features: AgeFeatures, age: float, gender: Optional[str]
    ) -> Tuple[VoiceMaturity, List[str]]:
        """Assess voice maturity stage."""
        maturity_indicators = []

        # Pre-pubertal characteristics
        if age < 12 or (features.f0_mean > 250):
            if features.f0_mean > 250:
                maturity_indicators.append("High fundamental frequency")
            if features.formant_dispersion > 1200:
                maturity_indicators.append("Wide formant spacing")
            return VoiceMaturity.PRE_PUBERTAL, maturity_indicators

        # Pubertal (mainly for males)
        if gender == "male" and 12 <= age <= 17:
            if 100 <= features.f0_mean <= 200:
                maturity_indicators.append("F0 in transition range")
            if features.f0_std > 40:
                maturity_indicators.append("Voice instability")
            if features.jitter > 0.008:
                maturity_indicators.append("Increased perturbation")
            return VoiceMaturity.PUBERTAL, maturity_indicators

        # Post-pubertal
        if 16 <= age <= 25:
            if gender == "male" and features.f0_mean < 150:
                maturity_indicators.append("Adult male F0 range")
            elif gender == "female" and 165 <= features.f0_mean <= 255:
                maturity_indicators.append("Adult female F0 range")
            return VoiceMaturity.POST_PUBERTAL, maturity_indicators

        # Mature voice
        if 25 <= age <= 50:
            if features.hnr > 20:
                maturity_indicators.append("Good harmonic structure")
            if features.cpp > 10:
                maturity_indicators.append("Strong cepstral peak")
            return VoiceMaturity.MATURE, maturity_indicators

        # Aging voice
        if 50 <= age <= 70:
            if features.tremor_amplitude > 5:
                maturity_indicators.append("Emerging tremor")
            if features.breathiness_index > 0.4:
                maturity_indicators.append("Increased breathiness")
            return VoiceMaturity.AGING, maturity_indicators

        # Advanced aging
        if features.jitter > 0.01:
            maturity_indicators.append("High jitter")
        if features.shimmer > 0.06:
            maturity_indicators.append("High shimmer")
        if features.tremor_frequency > 0:
            maturity_indicators.append("Voice tremor present")
        return VoiceMaturity.ADVANCED_AGING, maturity_indicators

    def _identify_active_indicators(
        self, features: AgeFeatures, age: float
    ) -> List[AgeIndicator]:
        """Identify which age indicators are active."""
        indicators = []

        # Use age parameter to determine relevant indicators
        if age < 18:
            # Check for child/adolescent indicators
            if features.f0_mean > 250:
                indicators.append(AgeIndicator.HIGH_F0)

        # Age parameter may influence indicator thresholds

        # F0 range indicator
        if features.f0_range > 0:
            indicators.append(AgeIndicator.F0_RANGE)

        # Formant indicator
        if features.f1_mean > 0 and features.f2_mean > 0:
            indicators.append(AgeIndicator.FORMANT_FREQUENCIES)

        # Voice tremor
        if features.tremor_amplitude > 3:
            indicators.append(AgeIndicator.VOICE_TREMOR)

        # Breathiness
        if features.breathiness_index > 0.4:
            indicators.append(AgeIndicator.BREATHINESS)

        # Hoarseness
        if features.hoarseness_index > 0.5:
            indicators.append(AgeIndicator.HOARSENESS)

        # Speech rate
        if features.speaking_rate > 0:
            indicators.append(AgeIndicator.SPEECH_RATE)

        # Pause patterns
        if features.pause_frequency > 10:
            indicators.append(AgeIndicator.PAUSE_PATTERNS)

        # Vocal stability
        if features.f0_std < 20 or features.f0_std > 40:
            indicators.append(AgeIndicator.VOCAL_STABILITY)

        # Harmonic structure
        if features.hnr > 0:
            indicators.append(AgeIndicator.HARMONIC_STRUCTURE)

        return indicators

    def _determine_developmental_stage(self, age: float, features: AgeFeatures) -> str:
        """Determine developmental stage based on age and features."""
        # Use features to refine stage determination
        if features.f0_mean > 300 and age < 10:
            # High pitch suggests younger child
            age = min(age, 8)
        elif features.f0_mean < 150 and age > 12:
            # Low pitch suggests older adolescent or adult
            age = max(age, 15)

        # Find closest milestone
        milestones = sorted(self.developmental_milestones.keys())

        for milestone_age in milestones:
            if age <= milestone_age:
                return self.developmental_milestones[milestone_age]

        # Default to last milestone
        return self.developmental_milestones[milestones[-1]]

    def _identify_age_related_changes(
        self, features: AgeFeatures, age: float
    ) -> List[str]:
        """Identify age-related voice changes."""
        changes = []

        # Presbyphonia indicators (age-related voice changes)
        if age > 60:
            if features.jitter > 0.008:
                changes.append("Increased pitch perturbation (presbyphonia)")
            if features.shimmer > 0.05:
                changes.append("Increased amplitude perturbation")
            if features.breathiness_index > 0.5:
                changes.append("Vocal fold bowing (increased breathiness)")
            if features.tremor_frequency > 0:
                changes.append("Age-related voice tremor")
            if features.high_frequency_energy_ratio < 0.1:
                changes.append("Reduced high-frequency energy")

        # Voice maturation indicators
        if age < 18:
            if features.f0_std > 35:
                changes.append("Voice instability (maturation process)")
            if features.formant_dispersion > 1200:
                changes.append("Short vocal tract (pediatric)")

        # Peak performance indicators
        if 20 <= age <= 40:
            if features.hnr > 25:
                changes.append("Optimal voice quality")
            if features.speech_rhythm_regularity > 0.8:
                changes.append("Peak motor control")

        return changes

    def _generate_clinical_considerations(
        self,
        age: float,
        age_group: AgeGroup,
        maturity: VoiceMaturity,
        features: AgeFeatures,
    ) -> List[str]:
        """Generate clinical considerations based on age estimation."""
        considerations = []

        # Age is used throughout the method for clinical thresholds

        # Pediatric considerations
        if age_group in [AgeGroup.CHILD, AgeGroup.ADOLESCENT]:
            considerations.append(
                f"Age-appropriate communication strategies recommended for estimated age {age:.0f}"
            )
            if features.f0_std > 50:
                considerations.append("Monitor for voice disorders during development")

        # Adolescent voice change
        if maturity == VoiceMaturity.PUBERTAL:
            considerations.append("Voice change in progress - avoid vocal strain")
            considerations.append(
                "Voice therapy contraindicated during active mutation"
            )

        # Adult considerations
        if age_group in [AgeGroup.YOUNG_ADULT, AgeGroup.MIDDLE_AGED]:
            if features.jitter > 0.01 or features.shimmer > 0.06:
                considerations.append("Voice quality suggests possible pathology")

        # Geriatric considerations
        if age_group in [AgeGroup.OLDER_ADULT, AgeGroup.ELDERLY]:
            considerations.append("Screen for presbyphonia")
            considerations.append("Consider age-related comorbidities affecting voice")
            if features.tremor_frequency > 0:
                considerations.append("Evaluate for neurological conditions")
            if features.breathiness_index > 0.6:
                considerations.append("Assess for vocal fold atrophy")

        # General quality concerns
        if features.hnr < 10:
            considerations.append(
                "Poor voice quality - comprehensive evaluation recommended"
            )

        return considerations

    def _calculate_confidence(
        self, features: AgeFeatures, likelihoods: Dict[str, float]
    ) -> float:
        """Calculate confidence in age estimation."""
        confidence_factors = []

        # Feature availability
        feature_availability = 0.0
        if features.f0_mean > 0:
            feature_availability += 0.3
        if features.f1_mean > 0:
            feature_availability += 0.2
        if features.speaking_rate > 0:
            feature_availability += 0.1
        if features.jitter > 0:
            feature_availability += 0.1
        if len(features.mfcc_means) > 0:
            feature_availability += 0.1

        confidence_factors.append(feature_availability)

        # Likelihood concentration
        if likelihoods:
            max_likelihood = max(likelihoods.values())
            confidence_factors.append(max_likelihood)

        # Feature quality
        quality_score = 1.0
        if features.f0_std > 100:  # Excessive F0 variation
            quality_score *= 0.7
        if features.hnr < 5:  # Very poor voice quality
            quality_score *= 0.8

        confidence_factors.append(quality_score)

        return float(np.mean(confidence_factors))

    def _calculate_uncertainty(
        self, features: AgeFeatures, age_range: Tuple[float, float]
    ) -> float:
        """Calculate uncertainty in age estimation."""
        # Base uncertainty from range
        range_uncertainty = (age_range[1] - age_range[0]) / 100  # Normalize to 0-1

        # Additional uncertainty from missing features
        missing_features = 0.0
        if features.f0_mean == 0:
            missing_features += 0.1
        if features.f1_mean == 0:
            missing_features += 0.1
        if features.speaking_rate == 0:
            missing_features += 0.05

        total_uncertainty = min(1.0, range_uncertainty + missing_features)

        return total_uncertainty

    def _generate_quality_warnings(
        self, features: AgeFeatures, confidence: float
    ) -> List[str]:
        """Generate warnings about estimation quality."""
        warnings = []

        if confidence < 0.5:
            warnings.append("Low confidence in age estimation")

        if features.f0_mean == 0:
            warnings.append("Unable to extract pitch information")

        if features.f1_mean == 0:
            warnings.append("Formant analysis failed - reduced accuracy")

        if features.hnr < 10:
            warnings.append("Poor voice quality may affect accuracy")

        if features.f0_std > 80:
            warnings.append("High pitch variability may indicate pathology")

        if features.speaking_rate < 2 or features.speaking_rate > 8:
            warnings.append("Unusual speaking rate detected")

        return warnings

    async def process_audio_file(
        self,
        file_path: str,
        known_gender: Optional[str] = None,
        save_results: bool = True,
    ) -> AgeEstimationResult:
        """Process an audio file for age estimation."""
        try:
            # Load audio file
            audio_data, _ = librosa.load(file_path, sr=self.config.sample_rate)

            # Estimate age
            result = await self.estimate_age(audio_data, known_gender)

            # Save results if requested
            if save_results:
                output_path = file_path.replace(".wav", "_age_estimation.json")
                with open(output_path, "w", encoding="utf-8") as f:
                    json.dump(result.to_dict(), f, indent=2)
                logger.info("Age estimation saved to %s", output_path)

            return result

        except Exception as e:
            logger.error("Error processing audio file: %s", str(e), exc_info=True)
            raise

    def get_age_statistics(self, results: List[AgeEstimationResult]) -> Dict[str, Any]:
        """Calculate statistics from multiple age estimations."""
        if not results:
            return {}

        ages = [r.estimated_age for r in results]
        age_groups = [r.age_group.value for r in results]

        # Gender distribution
        gender_counts: Dict[str, int] = defaultdict(int)
        for r in results:
            if r.likely_gender:
                gender_counts[r.likely_gender] += 1

        # Voice maturity distribution
        maturity_counts: Dict[str, int] = defaultdict(int)
        for r in results:
            maturity_counts[r.voice_maturity.value] += 1

        stats = {
            "mean_age": np.mean(ages),
            "median_age": np.median(ages),
            "age_std": np.std(ages),
            "age_range": (min(ages), max(ages)),
            "age_group_distribution": {
                group: age_groups.count(group) for group in set(age_groups)
            },
            "gender_distribution": dict(gender_counts),
            "voice_maturity_distribution": dict(maturity_counts),
            "mean_confidence": np.mean([r.confidence_score for r in results]),
            "samples_analyzed": len(results),
        }

        return stats
