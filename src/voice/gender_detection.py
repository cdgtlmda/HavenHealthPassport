"""
Gender Detection Module for Medical Voice Analysis.

This module implements gender detection from voice recordings to assist
in personalized medical care and accurate clinical assessment.
"""

# pylint: disable=too-many-lines

import json
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, cast

import numpy as np
from scipy import signal, stats
from scipy.ndimage import gaussian_filter1d

from src.security import encrypt_phi, requires_phi_access

try:
    import librosa
except ImportError:
    librosa = None

logger = logging.getLogger(__name__)


class Gender(Enum):
    """Gender classifications."""

    MALE = "male"
    FEMALE = "female"
    UNKNOWN = "unknown"  # When detection is uncertain


class VoiceGenderType(Enum):
    """Voice gender presentation types."""

    MASCULINE = "masculine"
    FEMININE = "feminine"
    ANDROGYNOUS = "androgynous"
    TRANSITIONING = "transitioning"
    UNKNOWN = "unknown"


class GenderIndicator(Enum):
    """Voice indicators of gender."""

    FUNDAMENTAL_FREQUENCY = "fundamental_frequency"
    FORMANT_FREQUENCIES = "formant_frequencies"
    VOCAL_TRACT_LENGTH = "vocal_tract_length"
    BREATHINESS = "breathiness"
    SPECTRAL_TILT = "spectral_tilt"
    F0_VARIABILITY = "f0_variability"
    SPEAKING_RATE = "speaking_rate"
    VOICE_QUALITY = "voice_quality"
    RESONANCE = "resonance"
    INTONATION_PATTERNS = "intonation_patterns"


@dataclass
class GenderFeatures:
    """Acoustic features for gender detection."""

    # Fundamental frequency features
    f0_mean: float = 0.0
    f0_median: float = 0.0
    f0_std: float = 0.0
    f0_min: float = 0.0
    f0_max: float = 0.0
    f0_range: float = 0.0
    f0_percentile_25: float = 0.0
    f0_percentile_75: float = 0.0

    # Formant features
    f1_mean: float = 0.0
    f2_mean: float = 0.0
    f3_mean: float = 0.0
    f4_mean: float = 0.0
    formant_dispersion: float = 0.0
    f1_f2_ratio: float = 0.0
    vocal_tract_length: float = 0.0

    # Voice quality features
    jitter: float = 0.0
    shimmer: float = 0.0
    hnr: float = 0.0
    cpp: float = 0.0
    breathiness_index: float = 0.0
    creakiness_index: float = 0.0

    # Spectral features
    spectral_tilt: float = 0.0
    spectral_centroid: float = 0.0
    spectral_spread: float = 0.0
    spectral_skewness: float = 0.0
    spectral_kurtosis: float = 0.0
    high_freq_energy: float = 0.0

    # Temporal features
    speaking_rate: float = 0.0
    articulation_rate: float = 0.0
    pause_ratio: float = 0.0
    speech_rhythm: float = 0.0

    # Prosodic features
    pitch_contour_range: float = 0.0
    pitch_contour_variability: float = 0.0
    intonation_patterns: List[float] = field(default_factory=list)

    # MFCC features
    mfcc_means: List[float] = field(default_factory=list)
    mfcc_stds: List[float] = field(default_factory=list)
    delta_mfcc_means: List[float] = field(default_factory=list)

    # Resonance features
    formant_bandwidths: List[float] = field(default_factory=list)
    spectral_balance: float = 0.0
    resonance_characteristics: Dict[str, float] = field(default_factory=dict)

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
            "vocal_tract_length": self.vocal_tract_length,
            "jitter": self.jitter,
            "shimmer": self.shimmer,
            "hnr": self.hnr,
            "breathiness_index": self.breathiness_index,
            "spectral_tilt": self.spectral_tilt,
            "speaking_rate": self.speaking_rate,
            "pitch_contour_range": self.pitch_contour_range,
            "mfcc_means": self.mfcc_means,
        }

    def get_gender_score(self) -> Dict[str, float]:
        """Calculate gender likelihood scores."""
        male_score = 0.0
        female_score = 0.0

        # F0-based scoring
        if self.f0_mean > 0:
            if self.f0_mean < 140:  # Typical male range
                male_score += 0.35
            elif self.f0_mean > 180:  # Typical female range
                female_score += 0.35
            else:  # Overlapping range
                male_score += 0.1
                female_score += 0.1

        # Formant-based scoring
        if self.f1_mean > 0 and self.f2_mean > 0:
            if self.f1_mean < 650 and self.f2_mean < 1700:  # Male-like formants
                male_score += 0.25
            elif self.f1_mean > 750 and self.f2_mean > 1900:  # Female-like formants
                female_score += 0.25

        # Voice quality scoring
        if self.breathiness_index > 0.5:  # More common in female voices
            female_score += 0.1
        if self.creakiness_index > 0.3:  # More common in male voices
            male_score += 0.1

        # Spectral tilt scoring
        if self.spectral_tilt < -2.5:  # Steeper tilt in male voices
            male_score += 0.1
        elif self.spectral_tilt > -2.0:  # Less steep in female voices
            female_score += 0.1

        # F0 variability scoring
        if self.f0_std > 30:  # Higher variability in female voices
            female_score += 0.1
        elif self.f0_std < 20:  # Lower variability in male voices
            male_score += 0.1

        # Normalize scores
        total = male_score + female_score
        if total > 0:
            return {"male": male_score / total, "female": female_score / total}
        else:
            return {"male": 0.5, "female": 0.5}


@dataclass
class GenderDetectionResult:
    """Result of gender detection analysis."""

    detected_gender: Gender
    confidence_score: float
    gender_probabilities: Dict[str, float] = field(default_factory=dict)

    # Voice gender type
    voice_gender_type: VoiceGenderType = VoiceGenderType.UNKNOWN
    voice_characteristics: List[str] = field(default_factory=list)

    # Detailed features
    features: Optional[GenderFeatures] = None
    active_indicators: List[GenderIndicator] = field(default_factory=list)

    # Additional analysis
    ambiguity_score: float = 0.0  # How ambiguous the gender markers are
    consistency_score: float = 0.0  # How consistent the indicators are

    # Clinical relevance
    clinical_notes: List[str] = field(default_factory=list)
    medication_considerations: List[str] = field(default_factory=list)

    # Quality metrics
    audio_quality_score: float = 0.0
    feature_reliability: float = 0.0
    warnings: List[str] = field(default_factory=list)

    # Processing metadata
    audio_duration: float = 0.0
    processing_time_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "detected_gender": self.detected_gender.value,
            "confidence_score": self.confidence_score,
            "gender_probabilities": self.gender_probabilities,
            "voice_gender_type": self.voice_gender_type.value,
            "voice_characteristics": self.voice_characteristics,
            "features": self.features.to_dict() if self.features else None,
            "active_indicators": [i.value for i in self.active_indicators],
            "ambiguity_score": self.ambiguity_score,
            "consistency_score": self.consistency_score,
            "clinical_notes": self.clinical_notes,
            "medication_considerations": self.medication_considerations,
            "audio_quality_score": self.audio_quality_score,
            "feature_reliability": self.feature_reliability,
            "warnings": self.warnings,
            "audio_duration": self.audio_duration,
            "processing_time_ms": self.processing_time_ms,
        }

    def get_summary(self) -> str:
        """Get human-readable summary."""
        summary = f"Detected Gender: {self.detected_gender.value.title()}\n"
        summary += f"Confidence: {self.confidence_score:.1%}\n"
        summary += (
            f"Voice Type: {self.voice_gender_type.value.replace('_', ' ').title()}\n"
        )

        if self.gender_probabilities:
            summary += "Probabilities:\n"
            for gender, prob in self.gender_probabilities.items():
                summary += f"  {gender.title()}: {prob:.1%}\n"

        if self.ambiguity_score > 0.3:
            summary += (
                f"Note: Ambiguous gender markers (score: {self.ambiguity_score:.2f})\n"
            )

        return summary


@dataclass
class GenderDetectionConfig:
    """Configuration for gender detection."""

    # Audio parameters
    sample_rate: int = 16000
    frame_length_ms: int = 25
    frame_shift_ms: int = 10

    # Analysis settings
    use_advanced_features: bool = True
    enable_voice_type_analysis: bool = True
    enable_clinical_notes: bool = True

    # Detection thresholds
    confidence_threshold: float = 0.7
    ambiguity_threshold: float = 0.3

    # Feature thresholds
    male_f0_threshold: float = 160
    female_f0_threshold: float = 180

    # Clinical settings
    include_medication_considerations: bool = True
    include_hormonal_effects: bool = True

    # Model settings
    use_ml_model: bool = False
    model_path: Optional[str] = None


class GenderDetector:
    """
    Detects gender from voice recordings using acoustic analysis.

    Implements evidence-based acoustic correlates of gender including
    fundamental frequency, formants, voice quality, and spectral characteristics.
    """

    def __init__(self, config: Optional[GenderDetectionConfig] = None):
        """
        Initialize the gender detector.

        Args:
            config: Detection configuration
        """
        self.config = config or GenderDetectionConfig()

        # Frame parameters
        self.frame_length = int(
            self.config.sample_rate * self.config.frame_length_ms / 1000
        )
        self.frame_shift = int(
            self.config.sample_rate * self.config.frame_shift_ms / 1000
        )

        # Initialize gender patterns
        self._init_gender_patterns()

        # Initialize voice type patterns
        self._init_voice_type_patterns()

        logger.info(
            "GenderDetector initialized with sample_rate=%sHz", self.config.sample_rate
        )

    def _init_gender_patterns(self) -> None:
        """Initialize gender-specific acoustic patterns."""
        self.gender_patterns = {
            Gender.MALE: {
                "f0_range": (80, 160),
                "f0_mean": 120,
                "f1_range": (500, 700),
                "f2_range": (1200, 1800),
                "formant_dispersion": (900, 1100),
                "spectral_tilt": (-3.5, -2.5),
                "breathiness": (0.0, 0.3),
                "speaking_rate": (3.5, 5.5),
            },
            Gender.FEMALE: {
                "f0_range": (160, 300),
                "f0_mean": 210,
                "f1_range": (650, 900),
                "f2_range": (1600, 2400),
                "formant_dispersion": (1100, 1400),
                "spectral_tilt": (-2.5, -1.5),
                "breathiness": (0.2, 0.6),
                "speaking_rate": (3.8, 5.8),
            },
        }

        # Overlapping ranges (ambiguous zone)
        self.ambiguous_ranges = {"f0": (140, 180), "f1": (650, 750), "f2": (1600, 1900)}

    def _init_voice_type_patterns(self) -> None:
        """Initialize voice type patterns."""
        self.voice_type_patterns = {
            VoiceGenderType.MASCULINE: {
                "low_f0": True,
                "low_formants": True,
                "steep_spectral_tilt": True,
                "low_breathiness": True,
                "high_creakiness": True,
            },
            VoiceGenderType.FEMININE: {
                "high_f0": True,
                "high_formants": True,
                "shallow_spectral_tilt": True,
                "high_breathiness": True,
                "low_creakiness": True,
            },
            VoiceGenderType.ANDROGYNOUS: {
                "mid_f0": True,
                "mixed_features": True,
                "balanced_quality": True,
            },
            VoiceGenderType.TRANSITIONING: {
                "changing_f0": True,
                "unstable_features": True,
                "mixed_indicators": True,
            },
        }

    @requires_phi_access("read")
    async def detect_gender(
        self,
        audio_data: np.ndarray,
        speaker_age: Optional[float] = None,
        user_id: str = "system",
    ) -> GenderDetectionResult:
        """
        Detect gender from audio data.

        Args:
            audio_data: Audio signal as numpy array
            speaker_age: Optional speaker age for age-adjusted detection
            user_id: User ID for access control

        Returns:
            GenderDetectionResult with gender analysis
        """
        logger.info("Gender detection requested by user: %s", user_id)
        start_time = datetime.now()

        try:
            # Normalize audio
            audio_data = self._normalize_audio(audio_data)

            # Check audio quality
            audio_quality = self._assess_audio_quality(audio_data)

            # Extract gender-related features
            features = await self._extract_gender_features(audio_data)

            # Calculate gender scores
            gender_scores = features.get_gender_score()

            # Apply age adjustments if provided
            if speaker_age is not None:
                gender_scores = self._apply_age_adjustments(
                    gender_scores, features, speaker_age
                )

            # Determine gender and confidence
            detected_gender, confidence = self._determine_gender(gender_scores)

            # Assess voice gender type
            voice_type = self._assess_voice_type(features)

            # Identify voice characteristics
            voice_characteristics = self._identify_voice_characteristics(features)

            # Identify active indicators
            active_indicators = self._identify_active_indicators(features)

            # Calculate ambiguity score
            ambiguity_score = self._calculate_ambiguity(features)

            # Calculate consistency score
            consistency_score = self._calculate_consistency(features, detected_gender)

            # Generate clinical notes
            clinical_notes = []
            medication_considerations = []

            if self.config.enable_clinical_notes:
                clinical_notes = self._generate_clinical_notes(
                    detected_gender, features, voice_type, speaker_age
                )

                if self.config.include_medication_considerations:
                    medication_considerations = (
                        self._generate_medication_considerations(
                            detected_gender, features, speaker_age
                        )
                    )

            # Calculate feature reliability
            feature_reliability = self._calculate_feature_reliability(
                features, audio_quality
            )

            # Generate warnings
            warnings = self._generate_warnings(
                features, confidence, ambiguity_score, audio_quality
            )

            # Processing time
            processing_time = (datetime.now() - start_time).total_seconds() * 1000

            return GenderDetectionResult(
                detected_gender=detected_gender,
                confidence_score=confidence,
                gender_probabilities=gender_scores,
                voice_gender_type=voice_type,
                voice_characteristics=voice_characteristics,
                features=features,
                active_indicators=active_indicators,
                ambiguity_score=ambiguity_score,
                consistency_score=consistency_score,
                clinical_notes=clinical_notes,
                medication_considerations=medication_considerations,
                audio_quality_score=audio_quality,
                feature_reliability=feature_reliability,
                warnings=warnings,
                audio_duration=len(audio_data) / self.config.sample_rate,
                processing_time_ms=processing_time,
            )

        except Exception as e:
            logger.error("Error in gender detection: %s", str(e), exc_info=True)
            raise

    def _normalize_audio(self, audio_data: np.ndarray) -> np.ndarray:
        """Normalize audio to [-1, 1] range."""
        max_val = np.max(np.abs(audio_data))
        if max_val > 0:
            return np.array(audio_data / max_val)
        return audio_data

    def _assess_audio_quality(self, audio_data: np.ndarray) -> float:
        """Assess audio quality for reliability."""
        # Check for clipping
        clipping_ratio = np.sum(np.abs(audio_data) > 0.95) / len(audio_data)

        # Check SNR
        signal_power = np.mean(audio_data**2)
        noise_floor = np.percentile(np.abs(audio_data), 10) ** 2

        if noise_floor > 0:
            snr = 10 * np.log10(signal_power / noise_floor)
        else:
            snr = 40

        # Check voice activity
        energy = librosa.feature.rms(
            y=audio_data, frame_length=self.frame_length, hop_length=self.frame_shift
        )[0]
        voice_activity_ratio = np.sum(energy > np.mean(energy) * 0.1) / len(energy)

        # Combine quality metrics
        quality_score = min(
            1.0,
            (
                (1 - clipping_ratio) * 0.3
                + min(1.0, snr / 40) * 0.4
                + voice_activity_ratio * 0.3
            ),
        )

        return float(quality_score)

    async def _extract_gender_features(self, audio_data: np.ndarray) -> GenderFeatures:
        """Extract comprehensive gender-related features."""
        features = GenderFeatures()

        # Extract F0 features
        f0_features = self._extract_f0_features(audio_data)
        features.f0_mean = f0_features["mean"]
        features.f0_median = f0_features["median"]
        features.f0_std = f0_features["std"]
        features.f0_min = f0_features["min"]
        features.f0_max = f0_features["max"]
        features.f0_range = f0_features["range"]
        features.f0_percentile_25 = f0_features["p25"]
        features.f0_percentile_75 = f0_features["p75"]

        # Extract formant features
        formant_features = await self._extract_formant_features(audio_data)
        features.f1_mean = formant_features["f1"]
        features.f2_mean = formant_features["f2"]
        features.f3_mean = formant_features["f3"]
        features.f4_mean = formant_features["f4"]
        features.formant_dispersion = formant_features["dispersion"]
        features.f1_f2_ratio = formant_features["f1_f2_ratio"]
        features.vocal_tract_length = formant_features["vtl"]

        # Extract voice quality features
        quality_features = self._extract_voice_quality_features(audio_data)
        features.jitter = quality_features["jitter"]
        features.shimmer = quality_features["shimmer"]
        features.hnr = quality_features["hnr"]
        features.cpp = quality_features["cpp"]
        features.breathiness_index = quality_features["breathiness"]
        features.creakiness_index = quality_features["creakiness"]

        # Extract spectral features
        spectral_features = self._extract_spectral_features(audio_data)
        features.spectral_tilt = spectral_features["tilt"]
        features.spectral_centroid = spectral_features["centroid"]
        features.spectral_spread = spectral_features["spread"]
        features.spectral_skewness = spectral_features["skewness"]
        features.spectral_kurtosis = spectral_features["kurtosis"]
        features.high_freq_energy = spectral_features["hf_energy"]

        # Extract temporal features
        temporal_features = self._extract_temporal_features(audio_data)
        features.speaking_rate = temporal_features["speaking_rate"]
        features.articulation_rate = temporal_features["articulation_rate"]
        features.pause_ratio = temporal_features["pause_ratio"]
        features.speech_rhythm = temporal_features["rhythm"]

        # Extract prosodic features
        if self.config.use_advanced_features:
            prosodic_features = self._extract_prosodic_features(audio_data)
            features.pitch_contour_range = prosodic_features["contour_range"]
            features.pitch_contour_variability = prosodic_features["contour_var"]
            features.intonation_patterns = prosodic_features["patterns"]

        # Extract MFCC features
        mfcc_features = self._extract_mfcc_features(audio_data)
        features.mfcc_means = mfcc_features["means"]
        features.mfcc_stds = mfcc_features["stds"]
        features.delta_mfcc_means = mfcc_features["delta_means"]

        # Extract resonance features
        if self.config.use_advanced_features:
            resonance_features = self._extract_resonance_features(audio_data)
            features.formant_bandwidths = resonance_features["bandwidths"]
            features.spectral_balance = resonance_features["balance"]
            features.resonance_characteristics = resonance_features["characteristics"]

        return features

    def _extract_f0_features(self, audio_data: np.ndarray) -> Dict[str, float]:
        """Extract fundamental frequency features."""
        # Extract F0 using YIN
        f0 = librosa.yin(
            audio_data,
            fmin=50,
            fmax=400,
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
            "min": 0.0,
            "max": 0.0,
            "range": 0.0,
            "p25": 0.0,
            "p75": 0.0,
        }

        if len(voiced_f0) > 10:
            features["mean"] = np.mean(voiced_f0)
            features["median"] = np.median(voiced_f0)
            features["std"] = np.std(voiced_f0)
            features["min"] = np.min(voiced_f0)
            features["max"] = np.max(voiced_f0)
            features["range"] = features["max"] - features["min"]
            features["p25"] = np.percentile(voiced_f0, 25)
            features["p75"] = np.percentile(voiced_f0, 75)

        return features

    async def _extract_formant_features(
        self, audio_data: np.ndarray
    ) -> Dict[str, float]:
        """Extract formant frequencies."""
        features = {
            "f1": 0.0,
            "f2": 0.0,
            "f3": 0.0,
            "f4": 0.0,
            "dispersion": 0.0,
            "f1_f2_ratio": 0.0,
            "vtl": 17.0,  # Default VTL in cm
        }

        # Process in frames
        formant_tracks: Dict[str, List[float]] = {f"f{i}": [] for i in range(1, 5)}

        window_size = self.frame_length * 2
        hop_size = self.frame_shift

        for i in range(0, len(audio_data) - window_size, hop_size):
            frame = audio_data[i : i + window_size]

            # Pre-emphasis
            pre_emphasis = 0.97
            emphasized = np.append(frame[0], frame[1:] - pre_emphasis * frame[:-1])

            # Window
            windowed = emphasized * np.hamming(len(emphasized))

            # Skip low energy frames
            if np.sum(windowed**2) < 0.01:
                continue

            try:
                # LPC analysis
                lpc_order = min(
                    int(self.config.sample_rate / 1000) + 4, len(windowed) - 1
                )
                a = librosa.lpc(windowed, order=lpc_order)

                # Find formants from roots
                roots = np.roots(a)

                # Convert to frequencies
                formants = []
                for root in roots:
                    if np.imag(root) >= 0:
                        angle = np.angle(root)
                        freq = angle * self.config.sample_rate / (2 * np.pi)
                        if 200 < freq < 5000:
                            formants.append(freq)

                # Sort and assign
                formants.sort()
                for j, freq in enumerate(formants[:4]):
                    if j < 4:
                        formant_tracks[f"f{j+1}"].append(freq)

            except (ValueError, RuntimeError, AttributeError):
                continue

        # Calculate mean formants
        for i in range(1, 5):
            track = formant_tracks[f"f{i}"]
            if track:
                features[f"f{i}"] = float(np.median(track))

        # Calculate additional features
        if features["f1"] > 0 and features["f2"] > 0:
            features["f1_f2_ratio"] = features["f1"] / features["f2"]

        # Formant dispersion
        formants = [features[f"f{i}"] for i in range(1, 5) if features[f"f{i}"] > 0]
        if len(formants) >= 3:
            spacings = np.diff(formants)
            features["dispersion"] = np.mean(spacings)

            # Estimate VTL
            c = 35000  # Speed of sound in cm/s
            if features["dispersion"] > 0:
                features["vtl"] = c / (2 * features["dispersion"])

        return features

    def _extract_voice_quality_features(
        self, audio_data: np.ndarray
    ) -> Dict[str, float]:
        """Extract voice quality features."""
        features = {
            "jitter": 0.0,
            "shimmer": 0.0,
            "hnr": 0.0,
            "cpp": 0.0,
            "breathiness": 0.0,
            "creakiness": 0.0,
        }

        # Extract F0 for jitter
        f0 = librosa.yin(
            audio_data,
            fmin=50,
            fmax=400,
            sr=self.config.sample_rate,
            frame_length=self.frame_length * 4,
            hop_length=self.frame_shift,
        )

        voiced_f0 = f0[f0 > 0]

        # Jitter calculation
        if len(voiced_f0) > 2:
            periods = 1.0 / voiced_f0
            period_diffs = np.abs(np.diff(periods))
            features["jitter"] = (
                np.mean(period_diffs) / np.mean(periods) if np.mean(periods) > 0 else 0
            )

        # Shimmer calculation
        frame_length = int(0.03 * self.config.sample_rate)
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

        # HNR calculation
        features["hnr"] = self._calculate_hnr(audio_data)

        # CPP calculation
        features["cpp"] = self._calculate_cpp(audio_data)

        # Breathiness (H1-H2 based)
        features["breathiness"] = self._calculate_breathiness(audio_data)

        # Creakiness (low F0 and irregular periods)
        if len(voiced_f0) > 0:
            low_f0_ratio = np.sum(voiced_f0 < 100) / len(voiced_f0)
            features["creakiness"] = low_f0_ratio

        return features

    def _calculate_hnr(self, audio_data: np.ndarray) -> float:
        """Calculate Harmonics-to-Noise Ratio."""
        frame_length = int(0.04 * self.config.sample_rate)
        hop_length = frame_length // 2
        hnr_values = []

        for i in range(0, len(audio_data) - frame_length, hop_length):
            frame = audio_data[i : i + frame_length]

            if np.max(np.abs(frame)) < 0.01:
                continue

            # Autocorrelation
            autocorr = np.correlate(frame, frame, mode="full")
            autocorr = autocorr[len(autocorr) // 2 :]

            # Find peak
            min_lag = int(self.config.sample_rate / 400)
            max_lag = int(self.config.sample_rate / 50)

            if max_lag < len(autocorr):
                search_region = autocorr[min_lag:max_lag]
                if len(search_region) > 0:
                    peak_idx = np.argmax(search_region) + min_lag

                    if autocorr[0] > 0:
                        r0 = autocorr[0]
                        r1 = autocorr[peak_idx]

                        if r1 > 0 and r1 < r0:
                            hnr = 10 * np.log10(r1 / (r0 - r1))
                            hnr_values.append(hnr)

        return np.mean(hnr_values) if hnr_values else 0.0

    def _calculate_cpp(self, audio_data: np.ndarray) -> float:
        """Calculate Cepstral Peak Prominence."""
        frame_length = int(0.04 * self.config.sample_rate)
        hop_length = frame_length // 2
        cpp_values = []

        for i in range(0, len(audio_data) - frame_length, hop_length):
            frame = audio_data[i : i + frame_length]

            if np.max(np.abs(frame)) < 0.01:
                continue

            # Window
            windowed = frame * np.hamming(len(frame))

            # Cepstrum
            spectrum = np.fft.fft(windowed, n=4096)
            log_spectrum = np.log(np.abs(spectrum) + 1e-10)
            cepstrum = np.real(np.fft.ifft(log_spectrum))

            # Find peak in speech range
            min_quefrency = int(self.config.sample_rate / 300)
            max_quefrency = int(self.config.sample_rate / 60)

            if max_quefrency < len(cepstrum) // 2:
                speech_cepstrum = cepstrum[min_quefrency:max_quefrency]

                if len(speech_cepstrum) > 10:
                    peak_idx = np.argmax(speech_cepstrum)
                    peak_val = speech_cepstrum[peak_idx]

                    # Regression line
                    quefrencies = np.arange(len(speech_cepstrum))
                    slope, intercept = np.polyfit(quefrencies, speech_cepstrum, 1)
                    regression_val = slope * peak_idx + intercept

                    cpp = peak_val - regression_val
                    cpp_values.append(cpp)

        return np.mean(cpp_values) if cpp_values else 0.0

    def _calculate_breathiness(self, audio_data: np.ndarray) -> float:
        """Calculate breathiness index."""
        # STFT
        stft = librosa.stft(
            audio_data, n_fft=self.frame_length * 2, hop_length=self.frame_shift
        )
        magnitude = np.abs(stft)

        breathiness_scores = []

        for frame_idx in range(magnitude.shape[1]):
            frame_mag = magnitude[:, frame_idx]

            # Find harmonics
            peaks, _ = signal.find_peaks(frame_mag, height=np.max(frame_mag) * 0.1)

            if len(peaks) >= 2:
                # H1-H2 difference
                h1 = frame_mag[peaks[0]]
                h2 = frame_mag[peaks[1]]

                if h1 > 0:
                    breathiness_scores.append((h1 - h2) / h1)

        return np.mean(breathiness_scores) if breathiness_scores else 0.0

    def _extract_spectral_features(self, audio_data: np.ndarray) -> Dict[str, float]:
        """Extract spectral features."""
        features = {
            "tilt": 0.0,
            "centroid": 0.0,
            "spread": 0.0,
            "skewness": 0.0,
            "kurtosis": 0.0,
            "hf_energy": 0.0,
        }

        # STFT
        stft = librosa.stft(
            audio_data, n_fft=self.frame_length * 2, hop_length=self.frame_shift
        )
        magnitude = np.abs(stft)
        freqs = librosa.fft_frequencies(
            sr=self.config.sample_rate, n_fft=self.frame_length * 2
        )

        # Spectral tilt
        tilts = []
        for frame_idx in range(magnitude.shape[1]):
            frame_mag = magnitude[:, frame_idx]
            if np.sum(frame_mag) > 0:
                valid_idx = (freqs > 100) & (frame_mag > 0)
                if np.sum(valid_idx) > 10:
                    log_freq = np.log(freqs[valid_idx])
                    log_mag = np.log(frame_mag[valid_idx] + 1e-10)
                    slope, _ = np.polyfit(log_freq, log_mag, 1)
                    tilts.append(slope)

        if tilts:
            features["tilt"] = np.mean(tilts)

        # Spectral centroid
        centroid = librosa.feature.spectral_centroid(
            y=audio_data, sr=self.config.sample_rate, hop_length=self.frame_shift
        )[0]
        if len(centroid) > 0:
            features["centroid"] = np.mean(centroid)
            features["spread"] = np.std(centroid)

        # Spectral shape statistics
        spectral_values = []
        for frame_idx in range(magnitude.shape[1]):
            frame_mag = magnitude[:, frame_idx]
            if np.sum(frame_mag) > 0:
                normalized = frame_mag / np.sum(frame_mag)
                spectral_values.append(normalized)

        if spectral_values:
            spectral_values_array = np.array(spectral_values)
            features["skewness"] = np.mean(
                [stats.skew(frame) for frame in spectral_values_array]
            )
            features["kurtosis"] = np.mean(
                [stats.kurtosis(frame) for frame in spectral_values_array]
            )

        # High frequency energy ratio
        total_energy = np.sum(magnitude**2, axis=0)
        high_freq_idx = freqs > 3000
        high_energy = np.sum(magnitude[high_freq_idx, :] ** 2, axis=0)

        valid_frames = total_energy > 0
        if np.any(valid_frames):
            hf_ratios = high_energy[valid_frames] / total_energy[valid_frames]
            features["hf_energy"] = np.mean(hf_ratios)

        return features

    def _extract_temporal_features(self, audio_data: np.ndarray) -> Dict[str, float]:
        """Extract temporal features."""
        features = {
            "speaking_rate": 0.0,
            "articulation_rate": 0.0,
            "pause_ratio": 0.0,
            "rhythm": 0.0,
        }

        # Energy envelope
        energy = librosa.feature.rms(
            y=audio_data, frame_length=self.frame_length, hop_length=self.frame_shift
        )[0]

        # Smooth energy
        smooth_energy = gaussian_filter1d(energy, sigma=2)

        # Find syllable peaks
        mean_energy = np.mean(smooth_energy)
        peaks, _ = signal.find_peaks(
            smooth_energy, height=mean_energy * 1.2, distance=5
        )

        duration = len(audio_data) / self.config.sample_rate

        if duration > 0:
            # Speaking rate
            features["speaking_rate"] = len(peaks) / duration

            # Pause detection
            pause_threshold = mean_energy * 0.1
            is_pause = smooth_energy < pause_threshold
            pause_frames = np.sum(is_pause)
            features["pause_ratio"] = pause_frames / len(energy)

            # Articulation rate (excluding pauses)
            speech_duration = duration * (1 - features["pause_ratio"])
            if speech_duration > 0:
                features["articulation_rate"] = len(peaks) / speech_duration

            # Rhythm regularity
            if len(peaks) > 2:
                intervals = np.diff(peaks) * self.frame_shift / self.config.sample_rate
                if np.mean(intervals) > 0:
                    cv = np.std(intervals) / np.mean(intervals)
                    features["rhythm"] = float(1 / (1 + cv))

        return features

    def _extract_prosodic_features(self, audio_data: np.ndarray) -> Dict[str, Any]:
        """Extract prosodic features."""
        features = {"contour_range": 0.0, "contour_var": 0.0, "patterns": []}

        # Extract F0 contour
        f0 = librosa.yin(
            audio_data,
            fmin=50,
            fmax=400,
            sr=self.config.sample_rate,
            frame_length=self.frame_length * 4,
            hop_length=self.frame_shift,
        )

        # Analyze voiced segments
        voiced_segments = []
        in_voiced = False
        start_idx = 0

        for i, f0_val in enumerate(f0):
            if f0_val > 0 and not in_voiced:
                start_idx = i
                in_voiced = True
            elif f0_val == 0 and in_voiced:
                if i - start_idx > 5:  # Minimum segment length
                    voiced_segments.append(f0[start_idx:i])
                in_voiced = False

        if voiced_segments:
            # Analyze each segment
            contour_ranges = []
            for segment in voiced_segments:
                if len(segment) > 0:
                    contour_ranges.append(np.ptp(segment))

            if contour_ranges:
                features["contour_range"] = np.mean(contour_ranges)
                features["contour_var"] = np.std(contour_ranges)

            # Extract intonation patterns (simplified)
            patterns = []
            for segment in voiced_segments[:5]:  # First 5 segments
                if len(segment) > 2:
                    # Fit linear trend
                    x = np.arange(len(segment))
                    slope, _ = np.polyfit(x, segment, 1)
                    patterns.append(slope)

            features["patterns"] = patterns

        return features

    def _extract_mfcc_features(self, audio_data: np.ndarray) -> Dict[str, List[float]]:
        """Extract MFCC features."""
        # Extract MFCCs
        mfcc = librosa.feature.mfcc(
            y=audio_data,
            sr=self.config.sample_rate,
            n_mfcc=13,
            hop_length=self.frame_shift,
        )

        # Delta MFCCs
        delta_mfcc = librosa.feature.delta(mfcc)

        features = {
            "means": mfcc.mean(axis=1).tolist(),
            "stds": mfcc.std(axis=1).tolist(),
            "delta_means": delta_mfcc.mean(axis=1).tolist(),
        }

        return features

    def _extract_resonance_features(self, audio_data: np.ndarray) -> Dict[str, Any]:
        """Extract resonance characteristics."""
        features: Dict[str, Any] = {
            "bandwidths": [],
            "balance": 0.0,
            "characteristics": {},
        }

        # Estimate formant bandwidths (simplified)
        # Would require more sophisticated analysis in production

        # Spectral balance (low vs high frequency energy)
        stft = librosa.stft(
            audio_data, n_fft=self.frame_length * 2, hop_length=self.frame_shift
        )
        magnitude = np.abs(stft)
        freqs = librosa.fft_frequencies(
            sr=self.config.sample_rate, n_fft=self.frame_length * 2
        )

        # Low frequency energy (below 1kHz)
        low_freq_idx = freqs < 1000
        low_energy = np.sum(magnitude[low_freq_idx, :] ** 2)

        # High frequency energy (above 1kHz)
        high_freq_idx = freqs >= 1000
        high_energy = np.sum(magnitude[high_freq_idx, :] ** 2)

        if low_energy + high_energy > 0:
            features["balance"] = low_energy / (low_energy + high_energy)

        # Resonance characteristics
        balance_value = features["balance"]
        features["characteristics"]["chest_resonance"] = float(balance_value)
        features["characteristics"]["head_resonance"] = 1.0 - float(balance_value)

        return features

    def _determine_gender(
        self, gender_scores: Dict[str, float]
    ) -> Tuple[Gender, float]:
        """Determine gender and confidence from scores."""
        if not gender_scores:
            return Gender.UNKNOWN, 0.0

        # Get maximum score
        max_gender = max(gender_scores.items(), key=lambda x: x[1])
        gender_str, confidence = max_gender

        # Map to Gender enum
        if gender_str == "male":
            gender = Gender.MALE
        elif gender_str == "female":
            gender = Gender.FEMALE
        else:
            gender = Gender.UNKNOWN

        # Adjust confidence based on score difference
        if len(gender_scores) == 2:
            scores = list(gender_scores.values())
            score_diff = abs(scores[0] - scores[1])
            if score_diff < 0.2:  # Close scores indicate uncertainty
                confidence *= 0.7

        return gender, confidence

    def _apply_age_adjustments(
        self, gender_scores: Dict[str, float], features: GenderFeatures, age: float
    ) -> Dict[str, float]:
        """Apply age-based adjustments to gender scores."""
        adjusted_scores = gender_scores.copy()

        # Pre-pubertal children have similar voice characteristics
        if age < 12:
            # Reduce confidence difference
            diff = abs(
                adjusted_scores.get("male", 0.5) - adjusted_scores.get("female", 0.5)
            )
            adjusted_scores["male"] = 0.5 + diff * 0.2
            adjusted_scores["female"] = 0.5 - diff * 0.2

        # Elderly females may have lower F0
        elif age > 70 and features.f0_mean < 180:
            if "female" in adjusted_scores:
                adjusted_scores["female"] *= 1.2  # Boost female score

        # Normalize
        total = sum(adjusted_scores.values())
        if total > 0:
            for key in adjusted_scores:
                adjusted_scores[key] /= total

        return adjusted_scores

    def _assess_voice_type(self, features: GenderFeatures) -> VoiceGenderType:
        """Assess voice gender presentation type."""
        masculine_score = 0.0
        feminine_score = 0.0

        # F0-based scoring
        if features.f0_mean < 140:
            masculine_score += 0.3
        elif features.f0_mean > 200:
            feminine_score += 0.3
        else:
            # Androgynous range
            masculine_score += 0.1
            feminine_score += 0.1

        # Formant-based scoring
        if features.f1_mean < 650:
            masculine_score += 0.2
        elif features.f1_mean > 800:
            feminine_score += 0.2

        # Voice quality scoring
        if features.breathiness_index > 0.4:
            feminine_score += 0.1
        if features.creakiness_index > 0.3:
            masculine_score += 0.1

        # Spectral tilt
        if features.spectral_tilt < -2.5:
            masculine_score += 0.1
        elif features.spectral_tilt > -2.0:
            feminine_score += 0.1

        # Determine type
        if masculine_score > feminine_score * 1.5:
            return VoiceGenderType.MASCULINE
        elif feminine_score > masculine_score * 1.5:
            return VoiceGenderType.FEMININE
        elif abs(masculine_score - feminine_score) < 0.2:
            return VoiceGenderType.ANDROGYNOUS
        else:
            # Mixed features might indicate transitioning
            if features.f0_std > 40 or features.jitter > 0.01:
                return VoiceGenderType.TRANSITIONING
            else:
                return VoiceGenderType.ANDROGYNOUS

    def _identify_voice_characteristics(self, features: GenderFeatures) -> List[str]:
        """Identify specific voice characteristics."""
        characteristics = []

        # Pitch characteristics
        if features.f0_mean < 120:
            characteristics.append("Very low pitch")
        elif features.f0_mean < 160:
            characteristics.append("Low pitch")
        elif features.f0_mean > 250:
            characteristics.append("Very high pitch")
        elif features.f0_mean > 200:
            characteristics.append("High pitch")
        else:
            characteristics.append("Medium pitch")

        # Voice quality
        if features.breathiness_index > 0.6:
            characteristics.append("Breathy voice")
        if features.creakiness_index > 0.4:
            characteristics.append("Creaky voice")
        if features.hnr > 25:
            characteristics.append("Clear voice quality")
        elif features.hnr < 15:
            characteristics.append("Rough voice quality")

        # Resonance
        if features.spectral_balance > 0.7:
            characteristics.append("Chest-dominant resonance")
        elif features.spectral_balance < 0.3:
            characteristics.append("Head-dominant resonance")

        # Speaking style
        if features.f0_std > 35:
            characteristics.append("Expressive intonation")
        elif features.f0_std < 15:
            characteristics.append("Monotone delivery")

        if features.speaking_rate > 5.5:
            characteristics.append("Fast speaker")
        elif features.speaking_rate < 3.5:
            characteristics.append("Slow speaker")

        return characteristics

    def _identify_active_indicators(
        self, features: GenderFeatures
    ) -> List[GenderIndicator]:
        """Identify which gender indicators are active."""
        indicators = []

        if features.f0_mean > 0:
            indicators.append(GenderIndicator.FUNDAMENTAL_FREQUENCY)

        if features.f1_mean > 0 and features.f2_mean > 0:
            indicators.append(GenderIndicator.FORMANT_FREQUENCIES)

        if features.vocal_tract_length > 0:
            indicators.append(GenderIndicator.VOCAL_TRACT_LENGTH)

        if features.breathiness_index > 0.3:
            indicators.append(GenderIndicator.BREATHINESS)

        if features.spectral_tilt != 0:
            indicators.append(GenderIndicator.SPECTRAL_TILT)

        if features.f0_std > 20:
            indicators.append(GenderIndicator.F0_VARIABILITY)

        if features.speaking_rate > 0:
            indicators.append(GenderIndicator.SPEAKING_RATE)

        if features.hnr > 0:
            indicators.append(GenderIndicator.VOICE_QUALITY)

        if features.spectral_balance != 0:
            indicators.append(GenderIndicator.RESONANCE)

        if len(features.intonation_patterns) > 0:
            indicators.append(GenderIndicator.INTONATION_PATTERNS)

        return indicators

    def _calculate_ambiguity(self, features: GenderFeatures) -> float:
        """Calculate ambiguity score based on overlapping features."""
        ambiguity_score = 0.0
        ambiguity_factors = 0

        # Check F0 ambiguity
        if (
            self.ambiguous_ranges["f0"][0]
            <= features.f0_mean
            <= self.ambiguous_ranges["f0"][1]
        ):
            ambiguity_score += 0.3
            ambiguity_factors += 1

        # Check formant ambiguity
        if (
            self.ambiguous_ranges["f1"][0]
            <= features.f1_mean
            <= self.ambiguous_ranges["f1"][1]
        ):
            ambiguity_score += 0.2
            ambiguity_factors += 1

        if (
            self.ambiguous_ranges["f2"][0]
            <= features.f2_mean
            <= self.ambiguous_ranges["f2"][1]
        ):
            ambiguity_score += 0.2
            ambiguity_factors += 1

        # Voice quality ambiguity
        if 0.3 <= features.breathiness_index <= 0.5:
            ambiguity_score += 0.1
            ambiguity_factors += 1

        # Spectral tilt ambiguity
        if -2.5 <= features.spectral_tilt <= -2.0:
            ambiguity_score += 0.1
            ambiguity_factors += 1

        # High variability indicates ambiguity
        if features.f0_std > 40:
            ambiguity_score += 0.1
            ambiguity_factors += 1

        # Normalize by number of factors
        if ambiguity_factors > 0:
            ambiguity_score /= ambiguity_factors

        return min(1.0, ambiguity_score * 1.5)  # Scale up slightly

    def _calculate_consistency(self, features: GenderFeatures, gender: Gender) -> float:
        """Calculate how consistent features are with detected gender."""
        consistency_scores: List[float] = []

        if gender == Gender.MALE:
            pattern = self.gender_patterns[Gender.MALE]

            # Check F0 consistency
            f0_range = cast(Tuple[float, float], pattern["f0_range"])
            if f0_range[0] <= features.f0_mean <= f0_range[1]:
                consistency_scores.append(1.0)
            else:
                # Calculate distance from range
                if features.f0_mean < f0_range[0]:
                    distance = f0_range[0] - features.f0_mean
                else:
                    distance = features.f0_mean - f0_range[1]
                consistency_scores.append(max(0, 1 - distance / 100))

            # Check formant consistency
            f1_range = cast(Tuple[float, float], pattern["f1_range"])
            if f1_range[0] <= features.f1_mean <= f1_range[1]:
                consistency_scores.append(1.0)
            else:
                consistency_scores.append(0.5)

            # Check voice quality
            breathiness_range = cast(Tuple[float, float], pattern["breathiness"])
            if features.breathiness_index <= breathiness_range[1]:
                consistency_scores.append(1.0)
            else:
                consistency_scores.append(0.7)

        elif gender == Gender.FEMALE:
            pattern = self.gender_patterns[Gender.FEMALE]

            # Similar checks for female pattern
            f0_range = cast(Tuple[float, float], pattern["f0_range"])
            if f0_range[0] <= features.f0_mean <= f0_range[1]:
                consistency_scores.append(1.0)
            else:
                if features.f0_mean < f0_range[0]:
                    distance = f0_range[0] - features.f0_mean
                else:
                    distance = features.f0_mean - f0_range[1]
                consistency_scores.append(max(0, 1 - distance / 100))

            f1_range = cast(Tuple[float, float], pattern["f1_range"])
            if f1_range[0] <= features.f1_mean <= f1_range[1]:
                consistency_scores.append(1.0)
            else:
                consistency_scores.append(0.5)

            breathiness_range = cast(Tuple[float, float], pattern["breathiness"])
            if (
                breathiness_range[0]
                <= features.breathiness_index
                <= breathiness_range[1]
            ):
                consistency_scores.append(1.0)
            else:
                consistency_scores.append(0.7)

        return float(np.mean(consistency_scores)) if consistency_scores else 0.5

    def _generate_clinical_notes(
        self,
        gender: Gender,
        features: GenderFeatures,
        voice_type: VoiceGenderType,
        age: Optional[float],
    ) -> List[str]:
        """Generate clinical notes based on gender detection."""
        notes: List[str] = []

        # Voice-gender mismatch - encrypt clinical notes
        if gender == Gender.MALE and voice_type == VoiceGenderType.FEMININE:
            # Store encrypted note as base64 string for type consistency
            note = encrypt_phi("Feminine voice characteristics in male speaker")
            notes.append(note.decode("utf-8") if isinstance(note, bytes) else str(note))
        elif gender == Gender.FEMALE and voice_type == VoiceGenderType.MASCULINE:
            note = encrypt_phi("Masculine voice characteristics in female speaker")
            notes.append(note.decode("utf-8") if isinstance(note, bytes) else str(note))

        # Transitioning voice - encrypt clinical notes
        if voice_type == VoiceGenderType.TRANSITIONING:
            note1 = encrypt_phi(
                "Voice characteristics suggest possible gender transition"
            )
            note2 = encrypt_phi("Consider hormone therapy effects on voice")
            notes.extend(
                [
                    note1.decode("utf-8") if isinstance(note1, bytes) else str(note1),
                    note2.decode("utf-8") if isinstance(note2, bytes) else str(note2),
                ]
            )

        # Age-related notes
        if age and age > 50:
            if gender == Gender.FEMALE and features.f0_mean < 170:
                notes.append("Lower F0 may be age-related in female speaker")
            elif gender == Gender.MALE and features.f0_mean > 140:
                notes.append("Elevated F0 may be age-related in male speaker")

        # Voice quality concerns
        if features.jitter > 0.01 or features.shimmer > 0.06:
            notes.append("Voice quality parameters suggest possible pathology")

        # Ambiguous characteristics
        if features.f0_mean > 0 and 140 <= features.f0_mean <= 180:
            notes.append("F0 in gender-ambiguous range")

        return notes

    def _generate_medication_considerations(
        self, gender: Gender, features: GenderFeatures, age: Optional[float]
    ) -> List[str]:
        """Generate medication-related considerations."""
        considerations = []

        # Hormone therapy effects
        if features.f0_std > 40 or features.jitter > 0.01:
            considerations.append(
                "Voice instability may indicate hormone therapy effects"
            )

        # Gender-specific medication metabolism
        if gender == Gender.MALE:
            considerations.append("Consider male-typical drug metabolism rates")
        elif gender == Gender.FEMALE:
            considerations.append("Consider female-typical drug metabolism rates")
            if age and 15 <= age <= 50:
                considerations.append("Consider potential pregnancy when prescribing")

        # Voice-affecting medications
        if features.breathiness_index > 0.7:
            considerations.append(
                "High breathiness - check for medications causing vocal fold edema"
            )

        # Check for hoarseness using creakiness as a proxy
        if features.creakiness_index > 0.7:
            considerations.append(
                "Voice irregularity present - review medications with voice side effects"
            )

        return considerations

    def _calculate_feature_reliability(
        self, features: GenderFeatures, audio_quality: float
    ) -> float:
        """Calculate reliability of extracted features."""
        reliability_factors = []

        # Audio quality factor
        reliability_factors.append(audio_quality)

        # Feature completeness
        feature_completeness = 0.0
        if features.f0_mean > 0:
            feature_completeness += 0.3
        if features.f1_mean > 0:
            feature_completeness += 0.2
        if features.speaking_rate > 0:
            feature_completeness += 0.1
        if features.hnr > 0:
            feature_completeness += 0.1
        if len(features.mfcc_means) > 0:
            feature_completeness += 0.1

        reliability_factors.append(feature_completeness)

        # Feature quality
        quality_score = 1.0
        if features.hnr < 10:  # Poor voice quality
            quality_score *= 0.8
        if features.f0_std > 100:  # Excessive variability
            quality_score *= 0.7

        reliability_factors.append(quality_score)

        return float(np.mean(reliability_factors))

    def _generate_warnings(
        self,
        features: GenderFeatures,
        confidence: float,
        ambiguity: float,
        audio_quality: float,
    ) -> List[str]:
        """Generate warnings about detection quality."""
        warnings = []

        if confidence < self.config.confidence_threshold:
            warnings.append(f"Low confidence in gender detection ({confidence:.1%})")

        if ambiguity > self.config.ambiguity_threshold:
            warnings.append(f"High ambiguity in gender markers ({ambiguity:.2f})")

        if audio_quality < 0.5:
            warnings.append("Poor audio quality may affect accuracy")

        if features.f0_mean == 0:
            warnings.append("Unable to extract pitch information")

        if features.f1_mean == 0:
            warnings.append("Formant analysis failed")

        if features.jitter > 0.02 or features.shimmer > 0.1:
            warnings.append("Voice quality issues may affect gender detection")

        if features.f0_std > 80:
            warnings.append("High pitch variability detected")

        return warnings

    async def process_audio_file(
        self,
        file_path: str,
        speaker_age: Optional[float] = None,
        save_results: bool = True,
    ) -> GenderDetectionResult:
        """Process an audio file for gender detection."""
        try:
            # Load audio file
            audio_data, _ = librosa.load(file_path, sr=self.config.sample_rate)

            # Detect gender
            result: GenderDetectionResult = await self.detect_gender(
                audio_data, speaker_age
            )

            # Save results if requested
            if save_results:
                output_path = file_path.replace(".wav", "_gender_detection.json")
                with open(output_path, "w", encoding="utf-8") as f:
                    json.dump(result.to_dict(), f, indent=2)
                logger.info("Gender detection saved to %s", output_path)

            return result

        except Exception as e:
            logger.error("Error processing audio file: %s", str(e), exc_info=True)
            raise

    def get_gender_statistics(
        self, results: List[GenderDetectionResult]
    ) -> Dict[str, Any]:
        """Calculate statistics from multiple gender detections."""
        if not results:
            return {}

        gender_counts: Dict[str, int] = defaultdict(int)
        voice_type_counts: Dict[str, int] = defaultdict(int)

        for r in results:
            gender_counts[r.detected_gender.value] += 1
            voice_type_counts[r.voice_gender_type.value] += 1

        # Confidence statistics
        confidences = [r.confidence_score for r in results]
        ambiguities = [r.ambiguity_score for r in results]

        # Feature averages
        f0_means = [
            r.features.f0_mean for r in results if r.features and r.features.f0_mean > 0
        ]

        analysis_stats = {
            "gender_distribution": dict(gender_counts),
            "voice_type_distribution": dict(voice_type_counts),
            "mean_confidence": np.mean(confidences),
            "mean_ambiguity": np.mean(ambiguities),
            "confidence_range": (min(confidences), max(confidences)),
            "mean_f0": np.mean(f0_means) if f0_means else 0,
            "f0_range": (min(f0_means), max(f0_means)) if f0_means else (0, 0),
            "samples_analyzed": len(results),
            "high_confidence_rate": sum(1 for r in results if r.confidence_score > 0.8)
            / len(results),
        }

        return analysis_stats
