"""
Dialect Identification Module for Medical Voice Analysis.

This module implements dialect and accent identification from voice recordings
to assist in culturally-aware medical care and accurate communication.

Security Note: This module processes voice data that may contain PHI.
All audio analysis must be performed with encryption at rest and in transit.
Access to dialect identification results should be restricted to authorized
healthcare personnel only through role-based access controls.
"""

# pylint: disable=too-many-lines

import json
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, cast

try:
    import librosa

    LIBROSA_AVAILABLE = True
except ImportError:
    LIBROSA_AVAILABLE = False

import numpy as np
from scipy import signal
from scipy.ndimage import gaussian_filter1d

try:
    from scipy.spatial import ConvexHull
except ImportError:
    ConvexHull = None
from scipy.stats import kurtosis, skew

logger = logging.getLogger(__name__)


class DialectRegion(Enum):
    """Major dialect regions."""

    # English dialects
    AMERICAN_ENGLISH = "american_english"
    BRITISH_ENGLISH = "british_english"
    AUSTRALIAN_ENGLISH = "australian_english"
    CANADIAN_ENGLISH = "canadian_english"
    INDIAN_ENGLISH = "indian_english"
    SOUTH_AFRICAN_ENGLISH = "south_african_english"

    # Spanish dialects
    MEXICAN_SPANISH = "mexican_spanish"
    SPAIN_SPANISH = "spain_spanish"
    ARGENTINE_SPANISH = "argentine_spanish"
    CARIBBEAN_SPANISH = "caribbean_spanish"

    # Arabic dialects
    LEVANTINE_ARABIC = "levantine_arabic"
    GULF_ARABIC = "gulf_arabic"
    EGYPTIAN_ARABIC = "egyptian_arabic"
    MAGHREBI_ARABIC = "maghrebi_arabic"

    # Other
    UNKNOWN = "unknown"


class DialectFeatureType(Enum):
    """Types of dialect features."""

    PHONETIC = "phonetic"
    PROSODIC = "prosodic"
    LEXICAL = "lexical"
    PHONOLOGICAL = "phonological"
    SUPRASEGMENTAL = "suprasegmental"


class DialectIndicator(Enum):
    """Specific dialect indicators."""

    VOWEL_SYSTEM = "vowel_system"
    CONSONANT_INVENTORY = "consonant_inventory"
    RHOTICITY = "rhoticity"
    INTONATION_PATTERN = "intonation_pattern"
    STRESS_PATTERN = "stress_pattern"
    RHYTHM_TYPE = "rhythm_type"
    VOWEL_SHIFT = "vowel_shift"
    VOICE_ONSET_TIME = "voice_onset_time"
    FINAL_CONSONANT_DELETION = "final_consonant_deletion"
    TONAL_PATTERNS = "tonal_patterns"


@dataclass
class DialectFeatures:
    """Acoustic features for dialect identification."""

    # Vowel features
    vowel_formants: Dict[str, List[float]] = field(default_factory=dict)
    vowel_space_area: float = 0.0
    vowel_dispersion: float = 0.0
    vowel_centralization: float = 0.0
    f1_f2_ratios: List[float] = field(default_factory=list)

    # Consonant features
    voice_onset_times: List[float] = field(default_factory=list)
    closure_durations: List[float] = field(default_factory=list)
    fricative_centroids: List[float] = field(default_factory=list)
    stop_bursts: List[float] = field(default_factory=list)

    # Prosodic features
    pitch_range: float = 0.0
    pitch_variance: float = 0.0
    pitch_contour_types: Dict[str, int] = field(default_factory=dict)
    intonation_patterns: List[str] = field(default_factory=list)

    # Rhythm features
    syllable_duration_variance: float = 0.0
    vowel_percentage: float = 0.0
    consonant_percentage: float = 0.0
    pvi_raw: float = 0.0  # Pairwise Variability Index
    pvi_normalized: float = 0.0

    # Stress patterns
    stress_interval_variance: float = 0.0
    strong_weak_ratio: float = 0.0
    stress_timing_index: float = 0.0

    # Spectral features
    spectral_moments: Dict[str, float] = field(default_factory=dict)
    formant_trajectories: Dict[str, List[float]] = field(default_factory=dict)
    spectral_tilt_patterns: List[float] = field(default_factory=list)

    # Phonological processes
    rhoticity_index: float = 0.0
    nasality_index: float = 0.0
    glottalization_index: float = 0.0
    palatalization_index: float = 0.0

    # Language-specific features
    tone_patterns: List[Tuple[float, float]] = field(default_factory=list)
    creaky_voice_ratio: float = 0.0
    breathy_voice_ratio: float = 0.0

    # MFCC and spectral statistics
    mfcc_statistics: Dict[str, List[float]] = field(default_factory=dict)
    delta_mfcc_statistics: Dict[str, List[float]] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert features to dictionary."""
        return {
            "vowel_space_area": self.vowel_space_area,
            "vowel_dispersion": self.vowel_dispersion,
            "pitch_range": self.pitch_range,
            "pitch_variance": self.pitch_variance,
            "syllable_duration_variance": self.syllable_duration_variance,
            "pvi_raw": self.pvi_raw,
            "rhoticity_index": self.rhoticity_index,
            "stress_timing_index": self.stress_timing_index,
            "vowel_formants": self.vowel_formants,
            "intonation_patterns": self.intonation_patterns,
            "spectral_moments": self.spectral_moments,
        }


@dataclass
class DialectIdentificationResult:
    """Result of dialect identification analysis."""

    primary_dialect: DialectRegion
    dialect_scores: Dict[str, float] = field(default_factory=dict)
    confidence_score: float = 0.0

    # Secondary dialects (for mixed accents)
    secondary_dialects: List[DialectRegion] = field(default_factory=list)
    dialect_mixture_ratio: Dict[str, float] = field(default_factory=dict)

    # Detailed features
    features: Optional[DialectFeatures] = None
    active_indicators: List[DialectIndicator] = field(default_factory=list)

    # Linguistic analysis
    phonetic_characteristics: List[str] = field(default_factory=list)
    prosodic_characteristics: List[str] = field(default_factory=list)
    distinctive_features: List[str] = field(default_factory=list)

    # Medical relevance
    communication_considerations: List[str] = field(default_factory=list)
    cultural_considerations: List[str] = field(default_factory=list)
    interpretation_risks: List[str] = field(default_factory=list)

    # Language background
    estimated_native_language: Optional[str] = None
    multilingual_indicators: List[str] = field(default_factory=list)
    acquisition_stage: Optional[str] = None  # Native, early learner, late learner

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
            "primary_dialect": self.primary_dialect.value,
            "dialect_scores": self.dialect_scores,
            "confidence_score": self.confidence_score,
            "secondary_dialects": [d.value for d in self.secondary_dialects],
            "dialect_mixture_ratio": self.dialect_mixture_ratio,
            "features": self.features.to_dict() if self.features else None,
            "active_indicators": [i.value for i in self.active_indicators],
            "phonetic_characteristics": self.phonetic_characteristics,
            "prosodic_characteristics": self.prosodic_characteristics,
            "distinctive_features": self.distinctive_features,
            "communication_considerations": self.communication_considerations,
            "cultural_considerations": self.cultural_considerations,
            "interpretation_risks": self.interpretation_risks,
            "estimated_native_language": self.estimated_native_language,
            "multilingual_indicators": self.multilingual_indicators,
            "acquisition_stage": self.acquisition_stage,
            "audio_quality_score": self.audio_quality_score,
            "feature_reliability": self.feature_reliability,
            "warnings": self.warnings,
            "audio_duration": self.audio_duration,
            "processing_time_ms": self.processing_time_ms,
        }

    def get_summary(self) -> str:
        """Get human-readable summary."""
        summary = (
            f"Primary Dialect: {self.primary_dialect.value.replace('_', ' ').title()}\n"
        )
        summary += f"Confidence: {self.confidence_score:.1%}\n"

        if self.secondary_dialects:
            summary += "Secondary Dialects: "
            summary += ", ".join(
                d.value.replace("_", " ").title() for d in self.secondary_dialects[:2]
            )
            summary += "\n"

        if self.estimated_native_language:
            summary += f"Estimated Native Language: {self.estimated_native_language}\n"

        if self.distinctive_features:
            summary += f"Key Features: {', '.join(self.distinctive_features[:3])}\n"

        return summary


@dataclass
class DialectIdentificationConfig:
    """Configuration for dialect identification."""

    # Audio parameters
    sample_rate: int = 16000
    frame_length_ms: int = 25
    frame_shift_ms: int = 10

    # Analysis settings
    enable_prosodic_analysis: bool = True
    enable_phonetic_analysis: bool = True
    enable_rhythm_analysis: bool = True
    enable_multilingual_detection: bool = True

    # Feature extraction
    min_vowel_duration: float = 0.05  # seconds
    min_consonant_duration: float = 0.02  # seconds
    formant_ceiling: float = 5500  # Hz

    # Dialect detection
    confidence_threshold: float = 0.6
    secondary_dialect_threshold: float = 0.3
    mixture_detection_threshold: float = 0.2

    # Medical settings
    include_communication_risks: bool = True
    include_cultural_notes: bool = True

    # Model settings
    use_ml_model: bool = False
    model_path: Optional[str] = None


class DialectIdentifier:
    """
    Identifies dialects and accents from voice recordings using acoustic analysis.

    Implements evidence-based acoustic correlates of dialectal variation including
    vowel systems, prosodic patterns, rhythm, and phonological processes.
    """

    def __init__(self, config: Optional[DialectIdentificationConfig] = None):
        """
        Initialize the dialect identifier.

        Args:
            config: Identification configuration
        """
        self.config = config or DialectIdentificationConfig()

        # Frame parameters
        self.frame_length = int(
            self.config.sample_rate * self.config.frame_length_ms / 1000
        )
        self.frame_shift = int(
            self.config.sample_rate * self.config.frame_shift_ms / 1000
        )

        # Initialize dialect patterns
        self._init_dialect_patterns()

        # Initialize phonetic inventories
        self._init_phonetic_inventories()

        logger.info(
            "DialectIdentifier initialized with sample_rate=%dHz",
            self.config.sample_rate,
        )

    def _init_dialect_patterns(self) -> None:
        """Initialize dialect-specific acoustic patterns."""
        self.dialect_patterns = {
            DialectRegion.AMERICAN_ENGLISH: {
                "vowels": {
                    "ae": {"f1": (650, 850), "f2": (1700, 2000)},  # 'cat'
                    "ɑ": {"f1": (700, 900), "f2": (1100, 1300)},  # 'cot'
                    "ɔ": {"f1": (550, 750), "f2": (850, 1050)},  # 'caught'
                },
                "rhoticity": 0.8,  # High rhoticity
                "rhythm": "stress-timed",
                "intonation": "falling_declarative",
                "distinctive": ["rhotic", "flapping", "vowel_reduction"],
            },
            DialectRegion.BRITISH_ENGLISH: {
                "vowels": {
                    "ɑː": {"f1": (650, 850), "f2": (1000, 1200)},  # 'bath'
                    "ɒ": {"f1": (550, 750), "f2": (700, 900)},  # 'lot'
                    "əʊ": {"f1": (450, 650), "f2": (1000, 1800)},  # 'goat'
                },
                "rhoticity": 0.1,  # Non-rhotic (except some regions)
                "rhythm": "stress-timed",
                "intonation": "rising_declarative",
                "distinctive": ["non-rhotic", "glottal_stop", "monophthongs"],
            },
            DialectRegion.AUSTRALIAN_ENGLISH: {
                "vowels": {
                    "æɪ": {"f1": (600, 800), "f2": (1800, 2200)},  # 'face'
                    "ɑɪ": {"f1": (700, 900), "f2": (1200, 1600)},  # 'price'
                    "əʉ": {"f1": (400, 600), "f2": (1200, 1600)},  # 'goose'
                },
                "rhoticity": 0.0,  # Non-rhotic
                "rhythm": "stress-timed",
                "intonation": "high_rising_terminal",
                "distinctive": ["vowel_shifts", "flapping", "yod_dropping"],
            },
            DialectRegion.INDIAN_ENGLISH: {
                "vowels": {
                    "ʌ": {"f1": (600, 800), "f2": (1200, 1400)},  # 'strut'
                    "ɛ": {"f1": (500, 700), "f2": (1700, 1900)},  # 'dress'
                },
                "rhoticity": 0.5,  # Variable rhoticity
                "rhythm": "syllable-timed",
                "intonation": "retroflex_influence",
                "distinctive": ["retroflexion", "aspiration", "clear_l"],
            },
            DialectRegion.MEXICAN_SPANISH: {
                "vowels": {
                    "e": {"f1": (400, 600), "f2": (2000, 2400)},
                    "o": {"f1": (400, 600), "f2": (800, 1200)},
                },
                "rhythm": "syllable-timed",
                "intonation": "circumflex_pattern",
                "distinctive": ["seseo", "weakened_consonants", "vowel_reduction"],
            },
            DialectRegion.SPAIN_SPANISH: {
                "vowels": {
                    "e": {"f1": (400, 550), "f2": (2100, 2500)},
                    "o": {"f1": (400, 550), "f2": (700, 1100)},
                },
                "rhythm": "syllable-timed",
                "intonation": "peninsular_pattern",
                "distinctive": ["distincion", "stronger_consonants", "apical_s"],
            },
        }

    def _init_phonetic_inventories(self) -> None:
        """Initialize phonetic inventories for different dialects."""
        self.phonetic_inventories = {
            "vowel_systems": {
                "general_american": [
                    "i",
                    "ɪ",
                    "e",
                    "ɛ",
                    "æ",
                    "ʌ",
                    "ɑ",
                    "ɔ",
                    "o",
                    "ʊ",
                    "u",
                ],
                "received_pronunciation": [
                    "iː",
                    "ɪ",
                    "e",
                    "ɛ",
                    "æ",
                    "ɑː",
                    "ɒ",
                    "ɔː",
                    "ʊ",
                    "uː",
                ],
                "australian": [
                    "iː",
                    "ɪ",
                    "e",
                    "ɛ",
                    "æ",
                    "ɐː",
                    "ɐ",
                    "ɔ",
                    "oː",
                    "ʊ",
                    "ʉː",
                ],
                "spanish": ["i", "e", "a", "o", "u"],
            },
            "consonant_processes": {
                "flapping": ["american", "australian"],
                "glottalization": ["british", "cockney"],
                "retroflexion": ["indian", "american_southern"],
                "seseo": ["latin_american_spanish"],
                "distincion": ["spain_spanish"],
            },
        }

    async def identify_dialect(
        self, audio_data: np.ndarray, reference_text: Optional[str] = None
    ) -> DialectIdentificationResult:
        """
        Identify dialect from audio data.

        Args:
            audio_data: Audio signal as numpy array
            reference_text: Optional reference text for phonetic alignment

        Returns:
            DialectIdentificationResult with dialect analysis
        """
        # reference_text will be used for phonetic alignment in future enhancement
        _ = reference_text

        start_time = datetime.now()

        try:
            # Normalize audio
            audio_data = self._normalize_audio(audio_data)

            # Check audio quality
            audio_quality = self._assess_audio_quality(audio_data)

            # Extract dialect features
            features = await self._extract_dialect_features(audio_data)

            # Calculate dialect scores
            dialect_scores = self._calculate_dialect_scores(features)

            # Determine primary dialect
            primary_dialect, confidence = self._determine_primary_dialect(
                dialect_scores
            )

            # Identify secondary dialects (for mixed accents)
            secondary_dialects = self._identify_secondary_dialects(
                dialect_scores, primary_dialect, confidence
            )

            # Calculate dialect mixture ratios
            mixture_ratio = self._calculate_mixture_ratio(dialect_scores)

            # Identify active indicators
            active_indicators = self._identify_active_indicators(features)

            # Extract characteristics
            phonetic_chars = self._extract_phonetic_characteristics(
                features, primary_dialect
            )
            prosodic_chars = self._extract_prosodic_characteristics(
                features, primary_dialect
            )
            distinctive_features = self._identify_distinctive_features(
                features, primary_dialect
            )

            # Language background estimation
            native_language = self._estimate_native_language(features, primary_dialect)
            multilingual_indicators = self._identify_multilingual_indicators(features)
            acquisition_stage = self._estimate_acquisition_stage(features)

            # Medical relevance
            communication_considerations = []
            cultural_considerations = []
            interpretation_risks = []

            if self.config.include_communication_risks:
                communication_considerations = (
                    self._generate_communication_considerations(
                        primary_dialect, secondary_dialects, features
                    )
                )
                interpretation_risks = self._identify_interpretation_risks(
                    primary_dialect, features
                )

            if self.config.include_cultural_notes:
                cultural_considerations = self._generate_cultural_considerations(
                    primary_dialect, native_language
                )

            # Calculate feature reliability
            feature_reliability = self._calculate_feature_reliability(
                features, audio_quality
            )

            # Generate warnings
            warnings = self._generate_warnings(
                features, confidence, audio_quality, mixture_ratio
            )

            # Processing time
            processing_time = (datetime.now() - start_time).total_seconds() * 1000

            return DialectIdentificationResult(
                primary_dialect=primary_dialect,
                dialect_scores=dialect_scores,
                confidence_score=confidence,
                secondary_dialects=secondary_dialects,
                dialect_mixture_ratio=mixture_ratio,
                features=features,
                active_indicators=active_indicators,
                phonetic_characteristics=phonetic_chars,
                prosodic_characteristics=prosodic_chars,
                distinctive_features=distinctive_features,
                communication_considerations=communication_considerations,
                cultural_considerations=cultural_considerations,
                interpretation_risks=interpretation_risks,
                estimated_native_language=native_language,
                multilingual_indicators=multilingual_indicators,
                acquisition_stage=acquisition_stage,
                audio_quality_score=audio_quality,
                feature_reliability=feature_reliability,
                warnings=warnings,
                audio_duration=len(audio_data) / self.config.sample_rate,
                processing_time_ms=processing_time,
            )

        except Exception as e:
            logger.error("Error in dialect identification: %s", str(e), exc_info=True)
            raise

    def _normalize_audio(self, audio_data: np.ndarray) -> np.ndarray:
        """Normalize audio to [-1, 1] range."""
        max_val = np.max(np.abs(audio_data))
        if max_val > 0:
            normalized: np.ndarray = (audio_data / max_val).astype(audio_data.dtype)
            return normalized
        return audio_data

    def _assess_audio_quality(self, audio_data: np.ndarray) -> float:
        """Assess audio quality for dialect analysis."""
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

        # Check spectral clarity
        stft = librosa.stft(
            audio_data, n_fft=self.frame_length * 2, hop_length=self.frame_shift
        )
        spectral_clarity = float(np.mean(np.abs(stft)) / (np.std(np.abs(stft)) + 1e-10))

        # Combine quality metrics
        quality_score = min(
            1.0,
            (
                (1 - clipping_ratio) * 0.2
                + min(1.0, snr / 40) * 0.3
                + voice_activity_ratio * 0.3
                + min(1.0, spectral_clarity / 10) * 0.2
            ),
        )

        return float(quality_score)

    async def _extract_dialect_features(
        self, audio_data: np.ndarray
    ) -> DialectFeatures:
        """Extract comprehensive dialect-related features."""
        features = DialectFeatures()

        # Extract vowel features
        if self.config.enable_phonetic_analysis:
            vowel_features = await self._extract_vowel_features(audio_data)
            features.vowel_formants = vowel_features["formants"]
            features.vowel_space_area = vowel_features["space_area"]
            features.vowel_dispersion = vowel_features["dispersion"]
            features.vowel_centralization = vowel_features["centralization"]
            features.f1_f2_ratios = vowel_features["f1_f2_ratios"]

        # Extract consonant features
        consonant_features = self._extract_consonant_features(audio_data)
        features.voice_onset_times = consonant_features["vot"]
        features.closure_durations = consonant_features["closures"]
        features.fricative_centroids = consonant_features["fricatives"]
        features.stop_bursts = consonant_features["bursts"]

        # Extract prosodic features
        if self.config.enable_prosodic_analysis:
            prosodic_features = self._extract_prosodic_features(audio_data)
            features.pitch_range = prosodic_features["range"]
            features.pitch_variance = prosodic_features["variance"]
            features.pitch_contour_types = prosodic_features["contour_types"]
            features.intonation_patterns = prosodic_features["patterns"]

        # Extract rhythm features
        if self.config.enable_rhythm_analysis:
            rhythm_features = await self._extract_rhythm_features(audio_data)
            features.syllable_duration_variance = rhythm_features["syllable_variance"]
            features.vowel_percentage = rhythm_features["vowel_percentage"]
            features.consonant_percentage = rhythm_features["consonant_percentage"]
            features.pvi_raw = rhythm_features["pvi_raw"]
            features.pvi_normalized = rhythm_features["pvi_norm"]

        # Extract stress patterns
        stress_features = self._extract_stress_patterns(audio_data)
        features.stress_interval_variance = stress_features["interval_variance"]
        features.strong_weak_ratio = stress_features["strong_weak_ratio"]
        features.stress_timing_index = stress_features["timing_index"]

        # Extract spectral features
        spectral_features = self._extract_spectral_dialect_features(audio_data)
        features.spectral_moments = spectral_features["moments"]
        features.formant_trajectories = spectral_features["trajectories"]
        features.spectral_tilt_patterns = spectral_features["tilt_patterns"]

        # Extract phonological process features
        phonological_features = self._extract_phonological_features(audio_data)
        features.rhoticity_index = phonological_features["rhoticity"]
        features.nasality_index = phonological_features["nasality"]
        features.glottalization_index = phonological_features["glottalization"]
        features.palatalization_index = phonological_features["palatalization"]

        # Extract voice quality features
        voice_quality = self._extract_voice_quality_dialect(audio_data)
        features.creaky_voice_ratio = voice_quality["creaky"]
        features.breathy_voice_ratio = voice_quality["breathy"]

        # Extract MFCC statistics
        mfcc_stats = self._extract_mfcc_statistics(audio_data)
        features.mfcc_statistics = mfcc_stats["static"]
        features.delta_mfcc_statistics = mfcc_stats["delta"]

        return features

    async def _extract_vowel_features(self, audio_data: np.ndarray) -> Dict[str, Any]:
        """Extract vowel-related features for dialect identification."""
        features: Dict[str, Any] = {
            "formants": {},
            "space_area": 0.0,
            "dispersion": 0.0,
            "centralization": 0.0,
            "f1_f2_ratios": [],
        }

        # Segment potential vowels using energy and spectral features
        vowel_segments = self._segment_vowels(audio_data)

        if not vowel_segments:
            return features

        # Extract formants for each vowel segment
        all_f1 = []
        all_f2 = []

        for segment in vowel_segments[:50]:  # Limit to first 50 segments
            formants = self._extract_formants_from_segment(segment)
            if formants and formants["f1"] > 0 and formants["f2"] > 0:
                all_f1.append(formants["f1"])
                all_f2.append(formants["f2"])

                # Calculate F1/F2 ratio
                features["f1_f2_ratios"].append(formants["f1"] / formants["f2"])

        if all_f1 and all_f2:
            # Calculate vowel space area (convex hull area of F1-F2 plot)
            if len(all_f1) >= 3:
                points = np.column_stack((all_f2, all_f1))  # F2 on x-axis, F1 on y-axis
                try:
                    hull = ConvexHull(points)
                    features["space_area"] = hull.area
                except (ValueError, RuntimeError):
                    features["space_area"] = 0.0

            # Calculate dispersion
            features["dispersion"] = np.std(all_f1) + np.std(all_f2)

            # Calculate centralization (distance from center)
            center_f1 = np.mean(all_f1)
            center_f2 = np.mean(all_f2)
            distances = [
                np.sqrt((f1 - center_f1) ** 2 + (f2 - center_f2) ** 2)
                for f1, f2 in zip(all_f1, all_f2)
            ]
            features["centralization"] = np.mean(distances)

            # Store mean formants for common vowels (simplified)
            features["formants"]["mean_f1"] = np.mean(all_f1)
            features["formants"]["mean_f2"] = np.mean(all_f2)
            features["formants"]["f1_range"] = (np.min(all_f1), np.max(all_f1))
            features["formants"]["f2_range"] = (np.min(all_f2), np.max(all_f2))

        return features

    def _segment_vowels(self, audio_data: np.ndarray) -> List[np.ndarray]:
        """Segment potential vowel regions from audio."""
        segments = []

        # Use energy and spectral features to find vowel-like regions
        energy = librosa.feature.rms(
            y=audio_data, frame_length=self.frame_length, hop_length=self.frame_shift
        )[0]

        # Zero crossing rate (lower for vowels)
        zcr = librosa.feature.zero_crossing_rate(
            audio_data, frame_length=self.frame_length, hop_length=self.frame_shift
        )[0]

        # Find voiced regions with low ZCR (potential vowels)
        energy_threshold = np.percentile(energy, 30)
        zcr_threshold = np.percentile(zcr, 50)

        vowel_frames = (energy > energy_threshold) & (zcr < zcr_threshold)

        # Group consecutive frames into segments
        in_vowel = False
        start_frame = 0

        for i, is_vowel in enumerate(vowel_frames):
            if is_vowel and not in_vowel:
                start_frame = i
                in_vowel = True
            elif not is_vowel and in_vowel:
                # Convert frames to samples
                start_sample = start_frame * self.frame_shift
                end_sample = i * self.frame_shift
                duration = (end_sample - start_sample) / self.config.sample_rate

                # Keep segments of appropriate duration
                if duration >= self.config.min_vowel_duration:
                    segments.append(audio_data[start_sample:end_sample])

                in_vowel = False

        return segments

    def _extract_formants_from_segment(self, segment: np.ndarray) -> Dict[str, float]:
        """Extract formant frequencies from a segment."""
        formants = {"f1": 0.0, "f2": 0.0, "f3": 0.0}

        if len(segment) < self.frame_length * 2:
            return formants

        # Pre-emphasis
        pre_emphasis = 0.97
        emphasized = np.append(segment[0], segment[1:] - pre_emphasis * segment[:-1])

        # Window
        window = np.hamming(len(emphasized))
        windowed = emphasized * window

        try:
            # LPC analysis
            lpc_order = min(int(self.config.sample_rate / 1000) + 4, len(windowed) - 1)
            a = librosa.lpc(windowed, order=lpc_order)

            # Find formants from LPC roots
            roots = np.roots(a)

            # Convert to frequencies
            formant_freqs = []
            for root in roots:
                if np.imag(root) >= 0:
                    angle = np.angle(root)
                    freq = angle * self.config.sample_rate / (2 * np.pi)
                    if 200 < freq < self.config.formant_ceiling:
                        formant_freqs.append(freq)

            # Sort and assign first three formants
            formant_freqs.sort()
            for i, freq in enumerate(formant_freqs[:3]):
                formants[f"f{i+1}"] = freq

        except (ValueError, IndexError):
            pass

        return formants

    def _extract_consonant_features(self, audio_data: np.ndarray) -> Dict[str, Any]:
        """Extract consonant-related features."""
        features: Dict[str, Any] = {
            "vot": [],  # Voice onset times
            "closures": [],  # Closure durations
            "fricatives": [],  # Fricative spectral centroids
            "bursts": [],  # Stop burst characteristics
        }

        # Simplified consonant detection using spectral features
        # In production, would use more sophisticated phoneme segmentation

        # High-frequency energy for fricatives
        stft = librosa.stft(
            audio_data, n_fft=self.frame_length * 2, hop_length=self.frame_shift
        )
        magnitude = np.abs(stft)
        freqs = librosa.fft_frequencies(
            sr=self.config.sample_rate, n_fft=self.frame_length * 2
        )

        # Detect fricative-like frames (high HF energy)
        high_freq_idx = freqs > 2000
        high_energy = np.sum(magnitude[high_freq_idx, :], axis=0)
        total_energy = np.sum(magnitude, axis=0)

        hf_ratio = high_energy / (total_energy + 1e-10)
        fricative_frames = hf_ratio > 0.6

        # Calculate spectral centroids for fricative frames
        for i, is_fricative in enumerate(fricative_frames):
            if is_fricative and total_energy[i] > 0:
                frame_mag = magnitude[:, i]
                centroid = np.sum(freqs * frame_mag) / np.sum(frame_mag)
                features["fricatives"].append(centroid)

        # Simplified VOT detection (would need aligned transcription in practice)
        # Look for silence-to-voicing transitions
        energy = librosa.feature.rms(
            y=audio_data, frame_length=self.frame_length, hop_length=self.frame_shift
        )[0]

        silence_threshold = np.percentile(energy, 20)
        voice_threshold = np.percentile(energy, 50)

        for i in range(1, len(energy) - 1):
            if energy[i - 1] < silence_threshold and energy[i + 1] > voice_threshold:
                # Potential VOT region
                vot_duration = 2 * self.frame_shift / self.config.sample_rate
                features["vot"].append(vot_duration * 1000)  # Convert to ms

        return features

    def _extract_prosodic_features(self, audio_data: np.ndarray) -> Dict[str, Any]:
        """Extract prosodic features for dialect identification."""
        features: Dict[str, Any] = {
            "range": 0.0,
            "variance": 0.0,
            "contour_types": {},
            "patterns": [],
        }

        # Extract F0 contour
        f0 = librosa.yin(
            audio_data,
            fmin=50,
            fmax=500,
            sr=self.config.sample_rate,
            frame_length=self.frame_length * 4,
            hop_length=self.frame_shift,
        )

        voiced_f0 = f0[f0 > 0]

        if len(voiced_f0) > 10:
            features["range"] = np.ptp(voiced_f0)
            features["variance"] = np.var(voiced_f0)

            # Analyze pitch contours
            # Segment into phrases
            phrase_segments = self._segment_phrases(f0)

            for segment in phrase_segments[:20]:  # Analyze first 20 phrases
                contour_type = self._classify_pitch_contour(segment)
                features["contour_types"][contour_type] = (
                    features["contour_types"].get(contour_type, 0) + 1
                )
                features["patterns"].append(contour_type)

        return features

    def _segment_phrases(self, f0: np.ndarray) -> List[np.ndarray]:
        """Segment F0 into phrases based on pauses."""
        segments = []

        # Find unvoiced regions (potential phrase boundaries)
        voiced = f0 > 0

        in_phrase = False
        start_idx = 0

        for i, is_voiced in enumerate(voiced):
            if is_voiced and not in_phrase:
                start_idx = i
                in_phrase = True
            elif not is_voiced and in_phrase:
                # Check if pause is long enough
                pause_start = i
                pause_end = i
                while pause_end < len(voiced) and not voiced[pause_end]:
                    pause_end += 1

                pause_duration = (
                    (pause_end - pause_start)
                    * self.frame_shift
                    / self.config.sample_rate
                )

                if pause_duration > 0.2:  # 200ms pause = phrase boundary
                    if i - start_idx > 10:  # Minimum phrase length
                        segments.append(f0[start_idx:i])
                    in_phrase = False

        return segments

    def _classify_pitch_contour(self, contour: np.ndarray) -> str:
        """Classify pitch contour type."""
        if len(contour) < 3:
            return "short"

        # Remove zeros
        voiced_contour = contour[contour > 0]

        if len(voiced_contour) < 3:
            return "short"

        # Fit linear trend
        x = np.arange(len(voiced_contour))
        slope, _ = np.polyfit(x, voiced_contour, 1)

        # Calculate relative slope
        mean_f0 = np.mean(voiced_contour)
        relative_slope = slope / mean_f0 * len(voiced_contour)

        # Classify based on slope and shape
        if relative_slope > 0.3:
            return "rising"
        elif relative_slope < -0.3:
            return "falling"
        else:
            # Check for complex patterns
            mid_point = len(voiced_contour) // 2
            first_half_mean = np.mean(voiced_contour[:mid_point])
            second_half_mean = np.mean(voiced_contour[mid_point:])

            if first_half_mean < second_half_mean - 10:
                return "rise_late"
            elif first_half_mean > second_half_mean + 10:
                return "fall_late"
            else:
                return "level"

    async def _extract_rhythm_features(
        self, audio_data: np.ndarray
    ) -> Dict[str, float]:
        """Extract rhythm features for dialect identification."""
        features = {
            "syllable_variance": 0.0,
            "vowel_percentage": 0.0,
            "consonant_percentage": 0.0,
            "pvi_raw": 0.0,
            "pvi_norm": 0.0,
        }

        # Segment into syllables using energy peaks
        energy = librosa.feature.rms(
            y=audio_data, frame_length=self.frame_length, hop_length=self.frame_shift
        )[0]

        # Smooth energy
        smooth_energy = gaussian_filter1d(energy, sigma=3)

        # Find syllable nuclei (energy peaks)
        peaks, _ = signal.find_peaks(
            smooth_energy,
            height=np.mean(smooth_energy) * 1.2,
            distance=int(0.08 * self.config.sample_rate / self.frame_shift),
        )

        if len(peaks) > 2:
            # Calculate syllable durations
            syllable_durations = (
                np.diff(peaks) * self.frame_shift / self.config.sample_rate
            )
            features["syllable_variance"] = float(np.var(syllable_durations))

            # Calculate Pairwise Variability Index (PVI)
            # Raw PVI
            if len(syllable_durations) > 1:
                pvi_raw_values = []
                for i in range(len(syllable_durations) - 1):
                    diff = abs(syllable_durations[i + 1] - syllable_durations[i])
                    pvi_raw_values.append(diff)
                features["pvi_raw"] = np.mean(pvi_raw_values) * 100

                # Normalized PVI
                pvi_norm_values = []
                for i in range(len(syllable_durations) - 1):
                    diff = abs(syllable_durations[i + 1] - syllable_durations[i])
                    avg = (syllable_durations[i + 1] + syllable_durations[i]) / 2
                    if avg > 0:
                        pvi_norm_values.append(diff / avg)
                features["pvi_norm"] = np.mean(pvi_norm_values) * 100

        # Calculate vowel/consonant percentages
        # Use spectral features to distinguish
        zcr = librosa.feature.zero_crossing_rate(
            audio_data, frame_length=self.frame_length, hop_length=self.frame_shift
        )[0]

        # Low ZCR = vowel-like, High ZCR = consonant-like
        zcr_threshold = np.median(zcr)
        vowel_frames = np.sum(zcr < zcr_threshold)
        consonant_frames = np.sum(zcr >= zcr_threshold)
        total_frames = len(zcr)

        if total_frames > 0:
            features["vowel_percentage"] = vowel_frames / total_frames
            features["consonant_percentage"] = consonant_frames / total_frames

        return features

    def _extract_stress_patterns(self, audio_data: np.ndarray) -> Dict[str, float]:
        """Extract stress pattern features."""
        features = {
            "interval_variance": 0.0,
            "strong_weak_ratio": 0.0,
            "timing_index": 0.0,
        }

        # Extract intensity and F0 for stress detection
        energy = librosa.feature.rms(
            y=audio_data, frame_length=self.frame_length, hop_length=self.frame_shift
        )[0]

        f0 = librosa.yin(
            audio_data,
            fmin=50,
            fmax=500,
            sr=self.config.sample_rate,
            frame_length=self.frame_length * 4,
            hop_length=self.frame_shift,
        )

        # Combine energy and F0 for stress detection
        stress_signal = energy.copy()

        # Add F0 contribution where voiced
        for i in range(min(len(stress_signal), len(f0))):
            if f0[i] > 0:
                stress_signal[i] *= 1 + f0[i] / 200  # Boost by relative F0

        # Find stress peaks
        stress_peaks, properties = signal.find_peaks(
            stress_signal,
            height=np.mean(stress_signal) * 1.5,
            distance=int(0.2 * self.config.sample_rate / self.frame_shift),
        )

        if len(stress_peaks) > 2:
            # Calculate inter-stress intervals
            stress_intervals = (
                np.diff(stress_peaks) * self.frame_shift / self.config.sample_rate
            )
            features["interval_variance"] = float(np.var(stress_intervals))

            # Calculate strong/weak ratio
            peak_heights = properties["peak_heights"]
            threshold = np.median(peak_heights)
            strong_stresses = np.sum(peak_heights > threshold)
            weak_stresses = np.sum(peak_heights <= threshold)

            if weak_stresses > 0:
                features["strong_weak_ratio"] = strong_stresses / weak_stresses

            # Stress timing index (regularity)
            if len(stress_intervals) > 1:
                cv = np.std(stress_intervals) / np.mean(stress_intervals)
                features["timing_index"] = float(1 / (1 + cv))  # Higher = more regular

        return features

    def _extract_spectral_dialect_features(
        self, audio_data: np.ndarray
    ) -> Dict[str, Any]:
        """Extract spectral features for dialect identification."""
        features: Dict[str, Any] = {
            "moments": {},
            "trajectories": {},
            "tilt_patterns": [],
        }

        # STFT
        stft = librosa.stft(
            audio_data, n_fft=self.frame_length * 2, hop_length=self.frame_shift
        )
        magnitude = np.abs(stft)
        freqs = librosa.fft_frequencies(
            sr=self.config.sample_rate, n_fft=self.frame_length * 2
        )

        # Calculate spectral moments for each frame
        centroids = []
        spreads = []
        skewnesses = []
        kurtoses = []

        for frame_idx in range(magnitude.shape[1]):
            frame_mag = magnitude[:, frame_idx]
            if np.sum(frame_mag) > 0:
                # Normalize as probability distribution
                prob = frame_mag / np.sum(frame_mag)

                # Centroid (1st moment)
                centroid = np.sum(freqs * prob)
                centroids.append(centroid)

                # Spread (2nd moment)
                spread = np.sqrt(np.sum(((freqs - centroid) ** 2) * prob))
                spreads.append(spread)

                # Skewness (3rd moment)
                if spread > 0:
                    skewness = np.sum(((freqs - centroid) ** 3) * prob) / (spread**3)
                    skewnesses.append(skewness)

                # Kurtosis (4th moment)
                if spread > 0:
                    kurt = np.sum(((freqs - centroid) ** 4) * prob) / (spread**4) - 3
                    kurtoses.append(kurt)

        # Store moment statistics
        if centroids:
            features["moments"]["centroid_mean"] = np.mean(centroids)
            features["moments"]["centroid_std"] = np.std(centroids)
        if spreads:
            features["moments"]["spread_mean"] = np.mean(spreads)
        if skewnesses:
            features["moments"]["skewness_mean"] = np.mean(skewnesses)
        if kurtoses:
            features["moments"]["kurtosis_mean"] = np.mean(kurtoses)

        # Extract spectral tilt patterns
        for frame_idx in range(0, magnitude.shape[1], 10):  # Sample every 10th frame
            frame_mag = magnitude[:, frame_idx]
            if np.sum(frame_mag) > 0:
                # Fit line to log spectrum
                valid_idx = (freqs > 100) & (frame_mag > 0)
                if np.sum(valid_idx) > 10:
                    log_freq = np.log(freqs[valid_idx])
                    log_mag = np.log(frame_mag[valid_idx] + 1e-10)
                    slope, _ = np.polyfit(log_freq, log_mag, 1)
                    features["tilt_patterns"].append(slope)

        return features

    def _extract_phonological_features(
        self, audio_data: np.ndarray
    ) -> Dict[str, float]:
        """Extract features related to phonological processes."""
        features = {
            "rhoticity": 0.0,
            "nasality": 0.0,
            "glottalization": 0.0,
            "palatalization": 0.0,
        }

        # Rhoticity detection (F3 lowering)
        # Extract F3 values from potential rhotic contexts
        f3_values = []

        # Would need phonetic alignment in practice
        # For now, extract F3 from all voiced segments
        segments = self._segment_vowels(audio_data)

        for segment in segments[:30]:
            formants = self._extract_formants_from_segment(segment)
            if formants["f3"] > 0:
                f3_values.append(formants["f3"])

        if f3_values:
            # Low F3 indicates rhoticity
            mean_f3 = np.mean(f3_values)
            features["rhoticity"] = max(0, 1 - float(mean_f3) / 3000)  # Normalize

        # Nasality detection (using spectral features)
        # Nasal sounds have anti-formants and specific spectral characteristics
        stft = librosa.stft(
            audio_data, n_fft=self.frame_length * 2, hop_length=self.frame_shift
        )
        magnitude = np.abs(stft)

        # Look for nasal murmur characteristics
        nasal_band = (250, 350)  # Hz - nasal murmur frequency
        freqs = librosa.fft_frequencies(
            sr=self.config.sample_rate, n_fft=self.frame_length * 2
        )

        nasal_idx = (freqs >= nasal_band[0]) & (freqs <= nasal_band[1])
        if np.any(nasal_idx):
            nasal_energy = np.mean(magnitude[nasal_idx, :])
            total_energy = np.mean(magnitude)
            features["nasality"] = nasal_energy / (total_energy + 1e-10)

        # Glottalization detection (irregular F0, creaky voice)
        f0 = librosa.yin(
            audio_data,
            fmin=50,
            fmax=500,
            sr=self.config.sample_rate,
            frame_length=self.frame_length * 4,
            hop_length=self.frame_shift,
        )

        # Look for F0 irregularities
        voiced_f0 = f0[f0 > 0]
        if len(voiced_f0) > 10:
            # Check for sudden F0 drops (glottal stops)
            f0_diffs = np.abs(np.diff(voiced_f0))
            glottal_drops = np.sum(f0_diffs > 50)  # Sudden drops > 50 Hz
            features["glottalization"] = min(1.0, glottal_drops / len(voiced_f0) * 10)

        # Palatalization detection (spectral shift)
        # Palatalized consonants have higher spectral energy
        # Simplified: look at spectral centroid variations
        centroids = librosa.feature.spectral_centroid(
            y=audio_data, sr=self.config.sample_rate, hop_length=self.frame_shift
        )[0]

        if len(centroids) > 10:
            # High variability in centroid might indicate palatalization
            centroid_var = np.var(centroids)
            features["palatalization"] = min(1.0, centroid_var / 1000000)

        return features

    def _extract_voice_quality_dialect(
        self, audio_data: np.ndarray
    ) -> Dict[str, float]:
        """Extract voice quality features relevant to dialect."""
        features = {"creaky": 0.0, "breathy": 0.0}

        # Creaky voice detection
        f0 = librosa.yin(
            audio_data,
            fmin=30,
            fmax=500,
            sr=self.config.sample_rate,
            frame_length=self.frame_length * 4,
            hop_length=self.frame_shift,
        )

        # Count very low F0 frames (potential creak)
        total_voiced = np.sum(f0 > 0)
        if total_voiced > 0:
            creaky_frames = np.sum((f0 > 30) & (f0 < 80))
            features["creaky"] = creaky_frames / total_voiced

        # Breathy voice detection (H1-H2)
        # Already implemented in other modules, simplified here
        stft = librosa.stft(
            audio_data, n_fft=self.frame_length * 2, hop_length=self.frame_shift
        )
        magnitude = np.abs(stft)

        breathiness_scores = []

        for frame_idx in range(magnitude.shape[1]):
            frame_mag = magnitude[:, frame_idx]
            peaks, _ = signal.find_peaks(frame_mag, height=np.max(frame_mag) * 0.1)

            if len(peaks) >= 2:
                h1_h2_ratio = frame_mag[peaks[0]] / frame_mag[peaks[1]]
                if h1_h2_ratio > 1:
                    breathiness_scores.append(h1_h2_ratio - 1)

        if breathiness_scores:
            features["breathy"] = min(1.0, np.mean(breathiness_scores))

        return features

    def _extract_mfcc_statistics(
        self, audio_data: np.ndarray
    ) -> Dict[str, Dict[str, List[float]]]:
        """Extract MFCC statistics for dialect modeling."""
        # Extract MFCCs
        mfcc = librosa.feature.mfcc(
            y=audio_data,
            sr=self.config.sample_rate,
            n_mfcc=13,
            hop_length=self.frame_shift,
        )

        # Delta MFCCs
        delta_mfcc = librosa.feature.delta(mfcc)

        # Calculate statistics
        mfcc_stats = {
            "static": {
                "means": mfcc.mean(axis=1).tolist(),
                "stds": mfcc.std(axis=1).tolist(),
                "skew": [skew(mfcc[i, :]) for i in range(mfcc.shape[0])],
                "kurtosis": [kurtosis(mfcc[i, :]) for i in range(mfcc.shape[0])],
            },
            "delta": {
                "means": delta_mfcc.mean(axis=1).tolist(),
                "stds": delta_mfcc.std(axis=1).tolist(),
            },
        }

        return mfcc_stats

    def _calculate_dialect_scores(self, features: DialectFeatures) -> Dict[str, float]:
        """Calculate scores for each dialect based on features."""
        scores = {}

        for dialect, pattern_obj in self.dialect_patterns.items():
            pattern = cast(Dict[str, Any], pattern_obj)
            score = 0.0
            weight_sum = 0.0

            # Vowel system matching
            if "vowels" in pattern and features.vowel_formants:
                vowel_score = self._match_vowel_system(features, pattern["vowels"])
                score += vowel_score * 0.3
                weight_sum += 0.3

            # Rhoticity matching
            if "rhoticity" in pattern:
                rhotic_diff = abs(features.rhoticity_index - pattern["rhoticity"])
                rhotic_score = 1 - rhotic_diff
                score += rhotic_score * 0.2
                weight_sum += 0.2

            # Rhythm matching
            if "rhythm" in pattern:
                rhythm_score = self._match_rhythm_type(features, pattern["rhythm"])
                score += rhythm_score * 0.2
                weight_sum += 0.2

            # Intonation matching
            if "intonation" in pattern and features.intonation_patterns:
                intonation_score = self._match_intonation(
                    features, pattern["intonation"]
                )
                score += intonation_score * 0.15
                weight_sum += 0.15

            # Distinctive features
            if "distinctive" in pattern:
                distinctive_score = self._match_distinctive_features(
                    features, pattern["distinctive"]
                )
                score += distinctive_score * 0.15
                weight_sum += 0.15

            # Normalize score
            if weight_sum > 0:
                scores[dialect.value] = score / weight_sum
            else:
                scores[dialect.value] = 0.0

        return scores

    def _match_vowel_system(
        self, features: DialectFeatures, vowel_pattern: Dict
    ) -> float:
        """Match vowel system to dialect pattern."""
        if not features.vowel_formants:
            return 0.5

        # Simplified: check if formant ranges match
        score = 0.0

        # Check general formant ranges
        if (
            "mean_f1" in features.vowel_formants
            and "mean_f2" in features.vowel_formants
        ):
            f1 = features.vowel_formants["mean_f1"]
            f2 = features.vowel_formants["mean_f2"]

            # Check against each vowel in pattern
            matches = 0.0
            for _, ranges in vowel_pattern.items():
                if ranges["f1"][0] <= f1 <= ranges["f1"][1]:
                    matches += 0.5
                if ranges["f2"][0] <= f2 <= ranges["f2"][1]:
                    matches += 0.5

            score = matches / len(vowel_pattern) if vowel_pattern else 0.5

        return min(1.0, score)

    def _match_rhythm_type(self, features: DialectFeatures, rhythm_type: str) -> float:
        """Match rhythm features to expected type."""
        if rhythm_type == "stress-timed":
            # Stress-timed languages have higher PVI values
            if features.pvi_normalized > 50:
                return 0.8
            elif features.pvi_normalized > 40:
                return 0.6
            else:
                return 0.3

        elif rhythm_type == "syllable-timed":
            # Syllable-timed languages have lower PVI values
            if features.pvi_normalized < 40:
                return 0.8
            elif features.pvi_normalized < 50:
                return 0.6
            else:
                return 0.3

        else:
            return 0.5

    def _match_intonation(
        self, features: DialectFeatures, intonation_type: str
    ) -> float:
        """Match intonation patterns."""
        if not features.intonation_patterns:
            return 0.5

        # Check predominant patterns
        pattern_counts: Dict[str, int] = {}
        for pattern in features.intonation_patterns:
            pattern_counts[pattern] = pattern_counts.get(pattern, 0) + 1

        # Simple matching based on expected patterns
        score = 0.5

        if (
            intonation_type == "falling_declarative"
            and pattern_counts.get("falling", 0)
            > len(features.intonation_patterns) * 0.4
        ):
            score = 0.8
        elif (
            intonation_type == "rising_declarative"
            and pattern_counts.get("rising", 0)
            > len(features.intonation_patterns) * 0.3
        ):
            score = 0.8
        elif (
            intonation_type == "high_rising_terminal"
            and pattern_counts.get("rise_late", 0)
            > len(features.intonation_patterns) * 0.2
        ):
            score = 0.8

        return score

    def _match_distinctive_features(
        self, features: DialectFeatures, distinctive: List[str]
    ) -> float:
        """Match distinctive phonological features."""
        matches = 0

        for feature in distinctive:
            if feature == "rhotic" and features.rhoticity_index > 0.6:
                matches += 1
            elif feature == "non-rhotic" and features.rhoticity_index < 0.3:
                matches += 1
            elif feature == "flapping" and features.voice_onset_times:
                # Flapping produces short VOT
                mean_vot = np.mean(features.voice_onset_times)
                if mean_vot < 30:  # ms
                    matches += 1
            elif feature == "glottal_stop" and features.glottalization_index > 0.3:
                matches += 1
            elif feature == "retroflexion" and features.fricative_centroids:
                # Retroflex sounds have lower spectral centroids
                mean_centroid = np.mean(features.fricative_centroids)
                if mean_centroid < 3000:
                    matches += 1

        return matches / len(distinctive) if distinctive else 0.5

    def _determine_primary_dialect(
        self, scores: Dict[str, float]
    ) -> Tuple[DialectRegion, float]:
        """Determine primary dialect and confidence."""
        if not scores:
            return DialectRegion.UNKNOWN, 0.0

        # Sort by score
        sorted_dialects = sorted(scores.items(), key=lambda x: x[1], reverse=True)

        # Get top dialect
        top_dialect_str, top_score = sorted_dialects[0]

        # Map string to enum
        try:
            primary_dialect = DialectRegion(top_dialect_str)
        except ValueError:
            primary_dialect = DialectRegion.UNKNOWN

        # Calculate confidence based on score and separation
        confidence = top_score

        # Adjust confidence based on separation from second best
        if len(sorted_dialects) > 1:
            second_score = sorted_dialects[1][1]
            separation = top_score - second_score

            if separation < 0.1:  # Very close scores
                confidence *= 0.7
            elif separation < 0.2:
                confidence *= 0.85

        return primary_dialect, confidence

    def _identify_secondary_dialects(
        self,
        scores: Dict[str, float],
        primary: DialectRegion,
        primary_confidence: float,
    ) -> List[DialectRegion]:
        """Identify secondary dialects for mixed accents."""
        # primary_confidence will be used for threshold adjustment in future
        _ = primary_confidence

        secondary = []

        for dialect_str, score in scores.items():
            if (
                dialect_str != primary.value
                and score > self.config.secondary_dialect_threshold
            ):
                try:
                    dialect = DialectRegion(dialect_str)
                    secondary.append(dialect)
                except ValueError:
                    pass

        # Sort by score
        secondary.sort(key=lambda d: scores.get(d.value, 0), reverse=True)

        return secondary[:2]  # Return top 2 secondary dialects

    def _calculate_mixture_ratio(self, scores: Dict[str, float]) -> Dict[str, float]:
        """Calculate dialect mixture ratios."""
        mixture: Dict[str, float] = {}

        # Filter significant scores
        significant_scores = {
            d: s
            for d, s in scores.items()
            if s > self.config.mixture_detection_threshold
        }

        if not significant_scores:
            return mixture

        # Normalize to sum to 1
        total = sum(significant_scores.values())

        for dialect, score in significant_scores.items():
            mixture[dialect] = score / total

        return mixture

    def _identify_active_indicators(
        self, features: DialectFeatures
    ) -> List[DialectIndicator]:
        """Identify which dialect indicators are active."""
        indicators = []

        if features.vowel_formants:
            indicators.append(DialectIndicator.VOWEL_SYSTEM)

        if features.voice_onset_times or features.fricative_centroids:
            indicators.append(DialectIndicator.CONSONANT_INVENTORY)

        if features.rhoticity_index > 0.1:
            indicators.append(DialectIndicator.RHOTICITY)

        if features.intonation_patterns:
            indicators.append(DialectIndicator.INTONATION_PATTERN)

        if features.stress_timing_index > 0:
            indicators.append(DialectIndicator.STRESS_PATTERN)

        if features.pvi_raw > 0 or features.pvi_normalized > 0:
            indicators.append(DialectIndicator.RHYTHM_TYPE)

        if features.vowel_dispersion > 0:
            indicators.append(DialectIndicator.VOWEL_SHIFT)

        if features.voice_onset_times:
            indicators.append(DialectIndicator.VOICE_ONSET_TIME)

        return indicators

    def _extract_phonetic_characteristics(
        self, features: DialectFeatures, dialect: DialectRegion
    ) -> List[str]:
        """Extract phonetic characteristics."""
        # dialect parameter will be used for dialect-specific features in future
        _ = dialect

        characteristics = []

        # Vowel characteristics
        if features.vowel_space_area > 0:
            if features.vowel_space_area > 500000:
                characteristics.append("Large vowel space")
            elif features.vowel_space_area < 200000:
                characteristics.append("Reduced vowel space")

        if features.vowel_centralization > 300:
            characteristics.append("Centralized vowels")

        # Consonant characteristics
        if features.voice_onset_times:
            mean_vot = np.mean(features.voice_onset_times)
            if mean_vot < 25:
                characteristics.append("Short VOT (possibly flapped)")
            elif mean_vot > 60:
                characteristics.append("Long VOT (aspirated stops)")

        # Voice quality
        if features.creaky_voice_ratio > 0.3:
            characteristics.append("Frequent creaky voice")

        if features.breathy_voice_ratio > 0.4:
            characteristics.append("Breathy voice quality")

        # Phonological processes
        if features.rhoticity_index > 0.7:
            characteristics.append("Strongly rhotic")
        elif features.rhoticity_index < 0.2:
            characteristics.append("Non-rhotic")

        if features.glottalization_index > 0.4:
            characteristics.append("Frequent glottalization")

        return characteristics

    def _extract_prosodic_characteristics(
        self, features: DialectFeatures, dialect: DialectRegion
    ) -> List[str]:
        """Extract prosodic characteristics."""
        # dialect parameter will be used for dialect-specific features in future
        _ = dialect

        characteristics = []

        # Pitch range
        if features.pitch_range > 200:
            characteristics.append("Wide pitch range")
        elif features.pitch_range < 100:
            characteristics.append("Narrow pitch range")

        # Intonation patterns
        if features.pitch_contour_types:
            dominant = max(features.pitch_contour_types.items(), key=lambda x: x[1])
            characteristics.append(f"Predominantly {dominant[0]} intonation")

        # Rhythm type
        if features.pvi_normalized > 50:
            characteristics.append("Stress-timed rhythm")
        elif features.pvi_normalized < 40:
            characteristics.append("Syllable-timed rhythm")
        else:
            characteristics.append("Mixed rhythm type")

        # Stress patterns
        if features.stress_timing_index > 0.7:
            characteristics.append("Regular stress intervals")
        elif features.stress_timing_index < 0.3:
            characteristics.append("Irregular stress patterns")

        return characteristics

    def _identify_distinctive_features(
        self, features: DialectFeatures, dialect: DialectRegion
    ) -> List[str]:
        """Identify distinctive features for the dialect."""
        distinctive = []

        # Get expected features for dialect
        if dialect in self.dialect_patterns:
            pattern_obj = self.dialect_patterns[dialect]
            pattern = cast(Dict[str, Any], pattern_obj)
            expected_features = pattern.get("distinctive", [])

            # Check which expected features are present
            for feature in expected_features:
                if feature == "rhotic" and features.rhoticity_index > 0.6:
                    distinctive.append("Rhotic accent")
                elif feature == "non-rhotic" and features.rhoticity_index < 0.3:
                    distinctive.append("Non-rhotic accent")
                elif feature == "flapping" and features.voice_onset_times:
                    if np.mean(features.voice_onset_times) < 30:
                        distinctive.append("T/D flapping")
                elif (
                    feature == "vowel_reduction" and features.vowel_centralization > 250
                ):
                    distinctive.append("Vowel reduction in unstressed syllables")

        # Add unexpected but present features
        if features.nasality_index > 0.5:
            distinctive.append("Nasalized vowels")

        if features.palatalization_index > 0.4:
            distinctive.append("Palatalized consonants")

        return distinctive[:5]  # Limit to top 5

    def _estimate_native_language(
        self, features: DialectFeatures, dialect: DialectRegion
    ) -> Optional[str]:
        """Estimate likely native language."""
        # Simplified estimation based on dialect and features

        if dialect in [
            DialectRegion.AMERICAN_ENGLISH,
            DialectRegion.BRITISH_ENGLISH,
            DialectRegion.AUSTRALIAN_ENGLISH,
            DialectRegion.CANADIAN_ENGLISH,
        ]:
            # Check for L2 features
            if features.syllable_duration_variance < 0.05:  # Very regular syllables
                return "Possibly L2 speaker"
            else:
                return "English"

        elif dialect == DialectRegion.INDIAN_ENGLISH:
            # Could be L1 or L2
            if features.palatalization_index > 0.5:
                return "Likely Hindi/Indian language L1"
            else:
                return "Indian English"

        elif dialect in [DialectRegion.MEXICAN_SPANISH, DialectRegion.SPAIN_SPANISH]:
            return "Spanish"

        elif dialect in [
            DialectRegion.LEVANTINE_ARABIC,
            DialectRegion.GULF_ARABIC,
            DialectRegion.EGYPTIAN_ARABIC,
            DialectRegion.MAGHREBI_ARABIC,
        ]:
            return "Arabic"

        return None

    def _identify_multilingual_indicators(self, features: DialectFeatures) -> List[str]:
        """Identify indicators of multilingualism."""
        indicators = []

        # Mixed rhythm patterns
        if features.pvi_normalized > 40 and features.pvi_normalized < 50:
            indicators.append("Mixed rhythm patterns (possible L1 interference)")

        # Unusual VOT patterns
        if features.voice_onset_times:
            vot_std = np.std(features.voice_onset_times)
            if vot_std > 30:
                indicators.append("Variable VOT (possible L1 influence)")

        # Mixed phonological processes
        if features.rhoticity_index > 0.3 and features.rhoticity_index < 0.6:
            indicators.append("Variable rhoticity (possible dialect mixing)")

        # Unusual formant patterns
        if features.vowel_dispersion > 400:
            indicators.append("Extended vowel space (possible L1 vowels)")

        return indicators

    def _estimate_acquisition_stage(self, features: DialectFeatures) -> Optional[str]:
        """Estimate language acquisition stage."""
        # Based on various phonetic accuracy measures

        accuracy_score = 0.0

        # Vowel accuracy (centralization)
        if features.vowel_centralization < 200:
            accuracy_score += 0.25
        elif features.vowel_centralization < 300:
            accuracy_score += 0.15

        # Consonant accuracy (VOT consistency)
        if features.voice_onset_times:
            vot_cv = np.std(features.voice_onset_times) / (
                np.mean(features.voice_onset_times) + 1e-10
            )
            if vot_cv < 0.3:
                accuracy_score += 0.25

        # Prosodic accuracy
        if features.stress_timing_index > 0.6:
            accuracy_score += 0.25

        # Voice quality
        if features.creaky_voice_ratio < 0.2 and features.breathy_voice_ratio < 0.3:
            accuracy_score += 0.25

        # Determine stage
        if accuracy_score > 0.8:
            return "Native speaker"
        elif accuracy_score > 0.6:
            return "Early acquisition/High proficiency"
        elif accuracy_score > 0.4:
            return "Intermediate acquisition"
        else:
            return "Late acquisition/Developing proficiency"

    def _generate_communication_considerations(
        self,
        dialect: DialectRegion,
        secondary: List[DialectRegion],
        features: DialectFeatures,
    ) -> List[str]:
        """Generate communication considerations for medical settings."""
        considerations = []

        # Dialect-specific considerations
        if dialect == DialectRegion.INDIAN_ENGLISH:
            considerations.append(
                "May use different stress patterns than American English"
            )
            considerations.append("Retroflex consonants may affect intelligibility")

        elif dialect in [DialectRegion.MEXICAN_SPANISH, DialectRegion.SPAIN_SPANISH]:
            if features.vowel_formants:  # Detected Spanish accent in English
                considerations.append(
                    "Spanish-accented English - may merge vowel contrasts"
                )
                considerations.append(
                    "May have difficulty with English consonant clusters"
                )

        # Mixed dialect considerations
        if secondary:
            considerations.append("Mixed dialect features detected")
            considerations.append("May switch between dialect features")

        # Intelligibility factors
        if features.vowel_centralization > 350:
            considerations.append("Reduced vowel distinctions may affect clarity")

        # Speaking rate analysis would go here if available
        # if features.speaking_rate > 6:
        #     considerations.append("Fast speech rate - may need to ask for repetition")

        return considerations

    def _identify_interpretation_risks(
        self, dialect: DialectRegion, features: DialectFeatures
    ) -> List[str]:
        """Identify potential interpretation risks."""
        risks = []

        # Phonetic ambiguities
        if features.vowel_centralization > 300:
            risks.append("Vowel mergers may cause word ambiguities")

        # Prosodic differences
        if dialect in [DialectRegion.INDIAN_ENGLISH, DialectRegion.LEVANTINE_ARABIC]:
            risks.append(
                "Different intonation patterns may be misinterpreted as attitude"
            )

        # Rhythm differences
        if features.pvi_normalized < 40:  # Syllable-timed
            risks.append(
                "Syllable-timed rhythm may sound 'robotic' to stress-timed listeners"
            )

        # Voice quality
        if features.creaky_voice_ratio > 0.4:
            risks.append("Creaky voice may be misinterpreted as disinterest or illness")

        return risks

    def _generate_cultural_considerations(
        self, dialect: DialectRegion, native_language: Optional[str]
    ) -> List[str]:
        """Generate cultural considerations."""
        considerations = []

        # Dialect-specific cultural notes
        if dialect in [DialectRegion.LEVANTINE_ARABIC, DialectRegion.GULF_ARABIC]:
            considerations.append("May prefer formal address in medical settings")
            considerations.append("Gender preferences for medical providers may apply")

        elif dialect in [DialectRegion.MEXICAN_SPANISH, DialectRegion.SPAIN_SPANISH]:
            considerations.append("Family involvement in medical decisions common")
            considerations.append("May use formal/informal address distinctions")

        elif dialect == DialectRegion.INDIAN_ENGLISH:
            considerations.append("Hierarchical communication style common")
            considerations.append("May not directly contradict medical authority")

        # Language-specific notes
        if native_language and "L2" in native_language:
            considerations.append(
                "May need extra time to process complex medical terms"
            )
            considerations.append("Written materials in native language may be helpful")

        return considerations

    def _calculate_feature_reliability(
        self, features: DialectFeatures, audio_quality: float
    ) -> float:
        """Calculate reliability of extracted features."""
        reliability_factors = []

        # Audio quality
        reliability_factors.append(audio_quality)

        # Feature completeness
        completeness = 0.0

        if features.vowel_formants:
            completeness += 0.2
        if features.pitch_range > 0:
            completeness += 0.1
        if features.pvi_raw > 0:
            completeness += 0.15
        if features.rhoticity_index >= 0:
            completeness += 0.1
        if len(features.intonation_patterns) > 0:
            completeness += 0.1
        if len(features.mfcc_statistics) > 0:
            completeness += 0.1

        reliability_factors.append(completeness)

        # Feature quality
        quality_score = 1.0

        # Check for reasonable values
        if features.pitch_variance > 10000:  # Excessive variance
            quality_score *= 0.8
        if features.vowel_space_area == 0:  # No vowel space
            quality_score *= 0.7

        reliability_factors.append(quality_score)

        return float(np.mean(reliability_factors))

    def _generate_warnings(
        self,
        features: DialectFeatures,
        confidence: float,
        audio_quality: float,
        mixture_ratio: Dict[str, float],
    ) -> List[str]:
        """Generate warnings about identification quality."""
        warnings = []

        if confidence < self.config.confidence_threshold:
            warnings.append(
                f"Low confidence in dialect identification ({confidence:.1%})"
            )

        if audio_quality < 0.5:
            warnings.append("Poor audio quality may affect accuracy")

        if not features.vowel_formants:
            warnings.append("Unable to extract vowel formants")

        if not features.intonation_patterns:
            warnings.append("Insufficient data for intonation analysis")

        if len(mixture_ratio) > 2:
            warnings.append("Multiple dialect influences detected")

        if features.vowel_space_area == 0:
            warnings.append("Unable to calculate vowel space")

        return warnings

    async def process_audio_file(
        self,
        file_path: str,
        reference_text: Optional[str] = None,
        save_results: bool = True,
    ) -> DialectIdentificationResult:
        """Process an audio file for dialect identification."""
        try:
            # Load audio file
            audio_data, _ = librosa.load(file_path, sr=self.config.sample_rate)

            # Identify dialect
            result = await self.identify_dialect(audio_data, reference_text)

            # Save results if requested
            if save_results:
                output_path = file_path.replace(".wav", "_dialect_identification.json")
                with open(output_path, "w", encoding="utf-8") as f:
                    json.dump(result.to_dict(), f, indent=2)
                logger.info("Dialect identification saved to %s", output_path)

            return result

        except Exception as e:
            logger.error("Error processing audio file: %s", str(e), exc_info=True)
            raise

    def get_dialect_statistics(
        self, results: List[DialectIdentificationResult]
    ) -> Dict[str, Any]:
        """Calculate statistics from multiple dialect identifications."""
        if not results:
            return {}

        dialect_counts: Dict[str, int] = defaultdict(int)
        confidence_scores = []

        for r in results:
            dialect_counts[r.primary_dialect.value] += 1
            confidence_scores.append(r.confidence_score)

        # Feature statistics
        rhoticity_values = [
            r.features.rhoticity_index
            for r in results
            if r.features and r.features.rhoticity_index >= 0
        ]

        pvi_values = [
            r.features.pvi_normalized
            for r in results
            if r.features and r.features.pvi_normalized > 0
        ]

        stats = {
            "dialect_distribution": dict(dialect_counts),
            "mean_confidence": np.mean(confidence_scores),
            "confidence_std": np.std(confidence_scores),
            "mean_rhoticity": np.mean(rhoticity_values) if rhoticity_values else 0,
            "mean_pvi": np.mean(pvi_values) if pvi_values else 0,
            "samples_analyzed": len(results),
            "high_confidence_rate": sum(1 for r in results if r.confidence_score > 0.7)
            / len(results),
        }

        return stats
