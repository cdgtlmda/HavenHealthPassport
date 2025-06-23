"""
Intelligibility Scoring Module for Medical Voice Analysis.

This module implements comprehensive speech intelligibility assessment
for medical applications, including articulation clarity, phoneme
recognition accuracy, and communication effectiveness metrics.
"""

# pylint: disable=too-many-lines

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, cast

try:
    import librosa

    LIBROSA_AVAILABLE = True
except ImportError:
    librosa = None
    LIBROSA_AVAILABLE = False

import numpy as np

try:
    import parselmouth

    PARSELMOUTH_AVAILABLE = True
except ImportError:
    parselmouth = None
    PARSELMOUTH_AVAILABLE = False

from scipy import signal
from scipy.ndimage import gaussian_filter1d
from scipy.signal import butter, filtfilt

logger = logging.getLogger(__name__)


class IntelligibilityLevel(Enum):
    """Levels of speech intelligibility."""

    EXCELLENT = "excellent"  # 95-100% intelligible
    GOOD = "good"  # 85-94% intelligible
    FAIR = "fair"  # 70-84% intelligible
    POOR = "poor"  # 50-69% intelligible
    VERY_POOR = "very_poor"  # Below 50% intelligible


class CommunicationContext(Enum):
    """Context for intelligibility assessment."""

    QUIET_ENVIRONMENT = "quiet_environment"
    NOISY_ENVIRONMENT = "noisy_environment"
    TELEPHONE = "telephone"
    PUBLIC_ADDRESS = "public_address"
    MEDICAL_CONSULTATION = "medical_consultation"
    EMERGENCY = "emergency"


class SpeechDisorderType(Enum):
    """Types of speech disorders affecting intelligibility."""

    NONE = "none"
    DYSARTHRIA = "dysarthria"
    APRAXIA = "apraxia"
    APHASIA = "aphasia"
    STUTTERING = "stuttering"
    CLUTTERING = "cluttering"
    VOICE_DISORDER = "voice_disorder"
    HEARING_IMPAIRMENT = "hearing_impairment"
    DEVELOPMENTAL = "developmental"
    NEUROLOGICAL = "neurological"


@dataclass
class ArticulationMetrics:
    """Metrics for articulation assessment."""

    # Consonant precision
    consonant_precision: float = 0.0  # 0-1 scale
    consonant_distortion: float = 0.0  # Amount of distortion
    voiced_voiceless_contrast: float = 0.0  # Distinction clarity

    # Vowel clarity
    vowel_space_area: float = 0.0  # Acoustic vowel space
    vowel_centralization: float = 0.0  # Degree of centralization
    vowel_consistency: float = 0.0  # Production consistency

    # Coarticulation
    coarticulation_smoothness: float = 0.0
    transition_clarity: float = 0.0

    # Place of articulation
    bilabial_accuracy: float = 0.0  # p, b, m
    alveolar_accuracy: float = 0.0  # t, d, n, s, z
    velar_accuracy: float = 0.0  # k, g

    # Manner of articulation
    stop_accuracy: float = 0.0  # p, t, k, b, d, g
    fricative_accuracy: float = 0.0  # f, s, sh, v, z
    nasal_accuracy: float = 0.0  # m, n, ng
    liquid_accuracy: float = 0.0  # l, r

    def to_dict(self) -> Dict[str, float]:
        """Convert to dictionary representation."""
        return {
            "consonant_precision": self.consonant_precision,
            "vowel_space_area": self.vowel_space_area,
            "coarticulation_smoothness": self.coarticulation_smoothness,
            "stop_accuracy": self.stop_accuracy,
            "fricative_accuracy": self.fricative_accuracy,
        }


@dataclass
class PhonemeMetrics:
    """Metrics for phoneme-level analysis."""

    # Phoneme recognition
    phoneme_accuracy: float = 0.0  # Overall accuracy
    phoneme_substitutions: int = 0  # Count of substitutions
    phoneme_omissions: int = 0  # Count of omissions
    phoneme_additions: int = 0  # Count of additions

    # Phoneme-specific scores
    phoneme_scores: Dict[str, float] = field(default_factory=dict)

    # Distinctive features
    voicing_accuracy: float = 0.0
    place_accuracy: float = 0.0
    manner_accuracy: float = 0.0

    # Phonological processes
    final_consonant_deletion: float = 0.0
    cluster_reduction: float = 0.0
    stopping: float = 0.0
    fronting: float = 0.0
    gliding: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "phoneme_accuracy": self.phoneme_accuracy,
            "substitutions": self.phoneme_substitutions,
            "omissions": self.phoneme_omissions,
            "distinctive_features": {
                "voicing": self.voicing_accuracy,
                "place": self.place_accuracy,
                "manner": self.manner_accuracy,
            },
        }


@dataclass
class ProsodyMetrics:
    """Metrics for prosodic features affecting intelligibility."""

    # Rhythm and timing
    speaking_rate_appropriateness: float = 0.0
    rhythm_consistency: float = 0.0
    syllable_duration_variance: float = 0.0

    # Stress patterns
    lexical_stress_accuracy: float = 0.0
    sentence_stress_appropriateness: float = 0.0

    # Intonation
    pitch_range_adequacy: float = 0.0
    intonation_naturalness: float = 0.0
    boundary_marking_clarity: float = 0.0

    # Pausing
    pause_placement_appropriateness: float = 0.0
    pause_duration_appropriateness: float = 0.0

    def to_dict(self) -> Dict[str, float]:
        """Convert to dictionary representation."""
        return {
            "speaking_rate_appropriateness": self.speaking_rate_appropriateness,
            "rhythm_consistency": self.rhythm_consistency,
            "intonation_naturalness": self.intonation_naturalness,
            "pause_placement_appropriateness": self.pause_placement_appropriateness,
        }


@dataclass
class AcousticClarityMetrics:
    """Metrics for acoustic clarity."""

    # Spectral clarity
    spectral_tilt: float = 0.0
    high_frequency_energy: float = 0.0
    formant_clarity: float = 0.0
    spectral_moments_clarity: float = 0.0

    # Temporal clarity
    envelope_modulation_depth: float = 0.0
    temporal_fine_structure: float = 0.0

    # Signal quality
    signal_to_noise_ratio: float = 0.0
    harmonic_to_noise_ratio: float = 0.0

    # Dynamic range
    dynamic_range: float = 0.0
    peak_to_average_ratio: float = 0.0

    def to_dict(self) -> Dict[str, float]:
        """Convert to dictionary representation."""
        return {
            "spectral_tilt": self.spectral_tilt,
            "formant_clarity": self.formant_clarity,
            "envelope_modulation_depth": self.envelope_modulation_depth,
            "signal_to_noise_ratio": self.signal_to_noise_ratio,
        }


@dataclass
class ContextualFactors:
    """Contextual factors affecting intelligibility."""

    # Environmental factors
    background_noise_level: float = 0.0
    reverberation_estimate: float = 0.0

    # Speaker factors
    vocal_effort: float = 0.0
    speaking_style_clarity: float = 0.0

    # Listener factors (estimated)
    estimated_listening_effort: float = 0.0
    predicted_comprehension: float = 0.0

    # Communication factors
    redundancy_level: float = 0.0
    context_availability: float = 0.0

    def to_dict(self) -> Dict[str, float]:
        """Convert to dictionary representation."""
        return {
            "background_noise_level": self.background_noise_level,
            "vocal_effort": self.vocal_effort,
            "estimated_listening_effort": self.estimated_listening_effort,
            "context_availability": self.context_availability,
        }


@dataclass
class IntelligibilityResult:
    """Complete intelligibility assessment result."""

    # Core metrics
    articulation_metrics: ArticulationMetrics
    phoneme_metrics: PhonemeMetrics
    prosody_metrics: ProsodyMetrics
    acoustic_clarity_metrics: AcousticClarityMetrics
    contextual_factors: ContextualFactors

    # Overall scores
    overall_intelligibility_score: float = 0.0  # 0-100 scale
    intelligibility_level: IntelligibilityLevel = IntelligibilityLevel.GOOD
    confidence_score: float = 0.0

    # Context-specific scores
    quiet_environment_score: float = 0.0
    noisy_environment_score: float = 0.0
    telephone_score: float = 0.0

    # Disorder detection
    detected_disorders: List[SpeechDisorderType] = field(default_factory=list)
    disorder_severity: Dict[str, float] = field(default_factory=dict)

    # Problem areas
    primary_issues: List[str] = field(default_factory=list)
    secondary_issues: List[str] = field(default_factory=list)

    # Recommendations
    therapy_recommendations: List[str] = field(default_factory=list)
    compensatory_strategies: List[str] = field(default_factory=list)

    # Processing metadata
    sample_rate: int = 16000
    audio_duration: float = 0.0
    speech_duration: float = 0.0
    processing_time_ms: float = 0.0

    # Quality indicators
    recording_quality: float = 0.0
    analysis_warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "overall_intelligibility_score": self.overall_intelligibility_score,
            "intelligibility_level": self.intelligibility_level.value,
            "confidence_score": self.confidence_score,
            "articulation_metrics": self.articulation_metrics.to_dict(),
            "phoneme_metrics": self.phoneme_metrics.to_dict(),
            "prosody_metrics": self.prosody_metrics.to_dict(),
            "acoustic_clarity_metrics": self.acoustic_clarity_metrics.to_dict(),
            "contextual_factors": self.contextual_factors.to_dict(),
            "context_scores": {
                "quiet": self.quiet_environment_score,
                "noisy": self.noisy_environment_score,
                "telephone": self.telephone_score,
            },
            "detected_disorders": [d.value for d in self.detected_disorders],
            "primary_issues": self.primary_issues,
            "therapy_recommendations": self.therapy_recommendations,
        }

    def get_summary(self) -> str:
        """Get a summary of intelligibility assessment."""
        summary = (
            f"Intelligibility Score: {self.overall_intelligibility_score:.1f}/100 "
        )
        summary += f"({self.intelligibility_level.value.upper()})\n"

        summary += "\nKey Metrics:\n"
        summary += f"  - Consonant Precision: {self.articulation_metrics.consonant_precision:.2f}\n"
        summary += (
            f"  - Vowel Clarity: {self.articulation_metrics.vowel_space_area:.2f}\n"
        )
        summary += f"  - Prosody: {self.prosody_metrics.intonation_naturalness:.2f}\n"

        if self.primary_issues:
            summary += f"\nPrimary Issues: {', '.join(self.primary_issues)}\n"

        if self.detected_disorders:
            summary += f"\nDetected Patterns: {', '.join(d.value for d in self.detected_disorders)}\n"

        return summary


@dataclass
class IntelligibilityConfig:
    """Configuration for intelligibility analysis."""

    # Analysis settings
    use_ml_models: bool = True
    ml_model_path: Optional[str] = None

    # Acoustic analysis
    window_length: float = 0.025  # seconds
    hop_length: float = 0.010  # seconds
    n_mfcc: int = 13
    n_formants: int = 4

    # Phoneme analysis
    use_forced_alignment: bool = True
    phoneme_model: str = "english"
    min_phoneme_duration: float = 0.030  # seconds

    # Prosody analysis
    pitch_range: Tuple[float, float] = (75, 500)  # Hz
    normal_speaking_rate: Tuple[float, float] = (3.0, 5.0)  # syllables/sec

    # Quality thresholds
    min_snr_threshold: float = 10.0  # dB
    min_recording_quality: float = 0.5

    # Context simulation
    simulate_noise: bool = True
    noise_levels_db: List[float] = [0, 10, 20]  # SNR levels

    # Scoring weights
    articulation_weight: float = 0.35
    phoneme_weight: float = 0.25
    prosody_weight: float = 0.20
    clarity_weight: float = 0.20


class IntelligibilityAnalyzer:
    """
    Comprehensive speech intelligibility analyzer for medical assessment.

    Implements various metrics for assessing speech clarity, articulation
    precision, and communication effectiveness in clinical contexts.
    """

    def __init__(self, config: Optional[IntelligibilityConfig] = None):
        """
        Initialize the intelligibility analyzer.

        Args:
            config: Analysis configuration
        """
        self.config = config or IntelligibilityConfig()

        # Reference values for normal speech
        self.normal_values = {
            "vowel_space_area": 300000,  # Hz²
            "consonant_precision": 0.95,
            "speaking_rate": 4.0,  # syllables/sec
            "f0_range": 100,  # Hz
        }

        # Initialize components
        self._init_phoneme_models()
        self._init_reference_data()

        if self.config.use_ml_models:
            self._load_ml_models()

        logger.info("IntelligibilityAnalyzer initialized")

    def _init_phoneme_models(self) -> None:
        """Initialize phoneme recognition models."""
        # Placeholder for phoneme model initialization
        self.phoneme_set = {
            "vowels": ["i", "ɪ", "e", "ɛ", "æ", "ɑ", "ɔ", "o", "ʊ", "u", "ʌ", "ə"],
            "consonants": {
                "stops": ["p", "b", "t", "d", "k", "g"],
                "fricatives": ["f", "v", "θ", "ð", "s", "z", "ʃ", "ʒ", "h"],
                "nasals": ["m", "n", "ŋ"],
                "liquids": ["l", "r"],
                "glides": ["w", "j"],
            },
        }
        logger.info("Phoneme models initialized")

    def _init_reference_data(self) -> None:
        """Initialize reference data for comparison."""
        # Reference formant frequencies for vowels
        self.reference_formants = {
            "i": {"F1": 280, "F2": 2250},
            "e": {"F1": 400, "F2": 2100},
            "æ": {"F1": 660, "F2": 1700},
            "ɑ": {"F1": 710, "F2": 1100},
            "o": {"F1": 450, "F2": 850},
            "u": {"F1": 310, "F2": 870},
        }

        # Expected durations for different phoneme types
        self.reference_durations = {
            "vowels": 0.120,  # seconds
            "stops": 0.080,
            "fricatives": 0.100,
            "nasals": 0.090,
            "liquids": 0.085,
        }

    def _load_ml_models(self) -> None:
        """Load machine learning models for intelligibility prediction."""
        # Placeholder for ML model loading
        self.ml_models: Dict[str, Any] = {}
        logger.info("ML models loaded (placeholder)")

    async def analyze_intelligibility(
        self,
        audio_data: np.ndarray,
        sample_rate: int = 16000,
        transcription: Optional[str] = None,
        context: CommunicationContext = CommunicationContext.QUIET_ENVIRONMENT,
    ) -> IntelligibilityResult:
        """
        Perform comprehensive intelligibility analysis.

        Args:
            audio_data: Audio signal
            sample_rate: Sample rate in Hz
            transcription: Optional reference transcription
            context: Communication context for analysis

        Returns:
            IntelligibilityResult with all metrics
        """
        start_time = datetime.now()

        try:
            # Extract all component metrics
            articulation = await self._analyze_articulation(audio_data, sample_rate)
            phonemes = await self._analyze_phonemes(
                audio_data, sample_rate, transcription
            )
            prosody = await self._analyze_prosody(audio_data, sample_rate)
            clarity = await self._analyze_acoustic_clarity(audio_data, sample_rate)
            contextual = await self._analyze_contextual_factors(audio_data, sample_rate)

            # Calculate overall intelligibility score
            overall_score = self._calculate_overall_score(
                articulation, phonemes, prosody, clarity
            )

            # Determine intelligibility level
            level = self._determine_intelligibility_level(overall_score)

            # Calculate context-specific scores
            quiet_score = overall_score
            noisy_score = self._estimate_noisy_environment_score(overall_score, clarity)
            telephone_score = self._estimate_telephone_score(overall_score, clarity)

            # Detect speech disorders
            disorders, severities = await self._detect_speech_disorders(
                articulation, phonemes, prosody, clarity
            )

            # Identify issues
            primary_issues, secondary_issues = self._identify_issues(
                articulation, phonemes, prosody, clarity
            )

            # Generate recommendations
            therapy_recs = self._generate_therapy_recommendations(
                primary_issues, disorders
            )
            strategies = self._generate_compensatory_strategies(primary_issues, context)

            # Calculate confidence
            confidence = self._calculate_confidence(audio_data, sample_rate)

            # Get recording quality and warnings
            recording_quality, quality_warnings = self._assess_recording_quality(
                audio_data, sample_rate
            )

            # Calculate durations
            speech_duration = self._calculate_speech_duration(audio_data, sample_rate)

            # Processing time
            processing_time = (datetime.now() - start_time).total_seconds() * 1000

            return IntelligibilityResult(
                articulation_metrics=articulation,
                phoneme_metrics=phonemes,
                prosody_metrics=prosody,
                acoustic_clarity_metrics=clarity,
                contextual_factors=contextual,
                overall_intelligibility_score=overall_score,
                intelligibility_level=level,
                confidence_score=confidence,
                quiet_environment_score=quiet_score,
                noisy_environment_score=noisy_score,
                telephone_score=telephone_score,
                detected_disorders=disorders,
                disorder_severity=severities,
                primary_issues=primary_issues,
                secondary_issues=secondary_issues,
                therapy_recommendations=therapy_recs,
                compensatory_strategies=strategies,
                sample_rate=sample_rate,
                audio_duration=len(audio_data) / sample_rate,
                speech_duration=speech_duration,
                processing_time_ms=processing_time,
                recording_quality=recording_quality,
                analysis_warnings=quality_warnings,
            )

        except Exception as e:
            logger.error("Error in intelligibility analysis: %s", str(e), exc_info=True)
            raise

    async def _analyze_articulation(
        self, audio_data: np.ndarray, sample_rate: int
    ) -> ArticulationMetrics:
        """Analyze articulation precision and clarity."""
        metrics = ArticulationMetrics()

        # Extract spectral features for articulation analysis
        stft = librosa.stft(audio_data, n_fft=2048, hop_length=512)
        magnitude = np.abs(stft)

        # Analyze consonant precision
        # High-frequency energy indicates fricative/stop clarity
        high_freq_energy = np.mean(magnitude[1000:, :])  # Above ~8kHz
        total_energy = np.mean(magnitude)
        metrics.consonant_precision = min(
            1.0, high_freq_energy / (total_energy + 1e-10) * 10
        )

        # Voiced/voiceless contrast
        # Analyze zero crossing rate differences
        zcr = librosa.feature.zero_crossing_rate(audio_data, hop_length=512)[0]
        zcr_variance = np.var(zcr)
        metrics.voiced_voiceless_contrast = min(1.0, zcr_variance * 100)

        # Vowel space analysis
        formants = await self._extract_vowel_formants(audio_data, sample_rate)
        if formants:
            metrics.vowel_space_area = self._calculate_vowel_space_area(formants)
            metrics.vowel_centralization = self._calculate_centralization(formants)
            metrics.vowel_consistency = self._calculate_vowel_consistency(formants)

        # Coarticulation smoothness
        # Analyze spectral flux for smooth transitions
        spectral_flux = np.sum(np.diff(magnitude, axis=1) ** 2, axis=0)
        metrics.coarticulation_smoothness = 1.0 / (1.0 + np.mean(spectral_flux))

        # Formant transitions
        if len(formants) > 1:
            transitions = self._analyze_formant_transitions(formants)
            metrics.transition_clarity = transitions

        # Place of articulation accuracy (simplified estimation)
        # Would use forced alignment in production
        spectral_moments = self._calculate_spectral_moments(magnitude)

        # Estimate place accuracy based on spectral characteristics
        metrics.bilabial_accuracy = self._estimate_place_accuracy(
            spectral_moments, "bilabial"
        )
        metrics.alveolar_accuracy = self._estimate_place_accuracy(
            spectral_moments, "alveolar"
        )
        metrics.velar_accuracy = self._estimate_place_accuracy(
            spectral_moments, "velar"
        )

        # Manner of articulation accuracy
        metrics.stop_accuracy = self._estimate_manner_accuracy(
            audio_data, sample_rate, "stop"
        )
        metrics.fricative_accuracy = self._estimate_manner_accuracy(
            audio_data, sample_rate, "fricative"
        )
        metrics.nasal_accuracy = self._estimate_manner_accuracy(
            audio_data, sample_rate, "nasal"
        )
        metrics.liquid_accuracy = self._estimate_manner_accuracy(
            audio_data, sample_rate, "liquid"
        )

        # Consonant distortion
        metrics.consonant_distortion = 1.0 - metrics.consonant_precision

        return metrics

    async def _extract_vowel_formants(
        self, audio_data: np.ndarray, sample_rate: int
    ) -> List[Dict[str, Any]]:
        """Extract formant frequencies for vowel segments."""
        formants = []

        # Segment audio into potential vowel regions
        # Using energy and spectral characteristics
        frames = librosa.util.frame(
            audio_data,
            frame_length=int(0.025 * sample_rate),
            hop_length=int(0.010 * sample_rate),
        )

        for i, frame in enumerate(frames.T):
            # Check if frame is likely a vowel (high energy, periodic)
            if self._is_vowel_frame(frame, sample_rate):
                # Extract formants using LPC or Praat
                frame_formants = self._extract_frame_formants(frame, sample_rate)
                if frame_formants:
                    formants.append(
                        {
                            "time": i * 0.010,
                            "F1": frame_formants[0],
                            "F2": frame_formants[1],
                            "F3": (
                                frame_formants[2] if len(frame_formants) > 2 else None
                            ),
                        }
                    )

        return formants

    def _is_vowel_frame(self, frame: np.ndarray, sample_rate: int) -> bool:
        """Determine if a frame likely contains a vowel."""
        # sample_rate will be used for spectral analysis in future
        _ = sample_rate

        # Energy threshold
        energy = np.mean(frame**2)
        if energy < 0.001:
            return False

        # Check periodicity using autocorrelation
        autocorr = np.correlate(frame, frame, mode="full")
        autocorr = autocorr[len(autocorr) // 2 :]

        # Look for strong periodicity
        peaks, _ = signal.find_peaks(autocorr[20:200], height=0.3 * autocorr[0])

        return len(peaks) > 0

    def _extract_frame_formants(
        self, frame: np.ndarray, sample_rate: int
    ) -> List[float]:
        """Extract formant frequencies from a single frame."""
        # Pre-emphasis
        pre_emphasized = np.append(frame[0], frame[1:] - 0.97 * frame[:-1])

        # LPC analysis
        lpc_order = int(sample_rate / 1000) + 2

        try:
            # Get LPC coefficients
            lpc_coeffs = librosa.lpc(pre_emphasized, order=lpc_order)

            # Find roots
            roots = np.roots(lpc_coeffs)

            # Convert to frequencies
            angles = np.angle(roots)
            freqs = angles * (sample_rate / (2 * np.pi))

            # Select positive frequencies with significant magnitude
            positive_freqs = freqs[freqs > 0]
            magnitudes = np.abs(roots[freqs > 0])

            # Sort by frequency
            sorted_indices = np.argsort(positive_freqs)
            sorted_freqs = positive_freqs[sorted_indices]
            sorted_mags = magnitudes[sorted_indices]

            # Select formants
            formants = []
            for freq, mag in zip(sorted_freqs, sorted_mags):
                if mag > 0.7 and 200 < freq < 4000:
                    formants.append(freq)
                    if len(formants) >= 3:
                        break

            return [float(f) for f in formants]

        except (ValueError, AttributeError, RuntimeError):
            return []

    def _calculate_vowel_space_area(self, formants: List[Dict[str, Any]]) -> float:
        """Calculate the area of the vowel space in F1-F2 plane."""
        if len(formants) < 3:
            return 0.0

        # Extract F1 and F2 values
        f1_values = [f["F1"] for f in formants if f.get("F1")]
        f2_values = [f["F2"] for f in formants if f.get("F2")]

        if len(f1_values) < 3 or len(f2_values) < 3:
            return 0.0

        # Find corner vowels (simplified - using extremes)
        # In production, would identify specific vowels
        points = []

        # High-front (like /i/)
        high_front_idx = np.argmax(f2_values)
        points.append((f1_values[high_front_idx], f2_values[high_front_idx]))

        # Low-front (like /æ/)
        low_front_mask = np.array(f1_values) > np.percentile(f1_values, 70)
        if np.any(low_front_mask):
            low_front_f2 = np.array(f2_values)[low_front_mask]
            low_front_f1 = np.array(f1_values)[low_front_mask]
            idx = np.argmax(low_front_f2)
            points.append((low_front_f1[idx], low_front_f2[idx]))

        # Low-back (like /ɑ/)
        low_back_idx = np.argmax(f1_values)
        points.append((f1_values[low_back_idx], f2_values[low_back_idx]))

        # High-back (like /u/)
        high_back_mask = np.array(f2_values) < np.percentile(f2_values, 30)
        if np.any(high_back_mask):
            high_back_f1 = np.array(f1_values)[high_back_mask]
            high_back_f2 = np.array(f2_values)[high_back_mask]
            idx = np.argmin(high_back_f1)
            points.append((high_back_f1[idx], high_back_f2[idx]))

        # Calculate area using shoelace formula
        if len(points) >= 3:
            area = 0.0
            n = len(points)
            for i in range(n):
                j = (i + 1) % n
                area += points[i][0] * points[j][1]
                area -= points[j][0] * points[i][1]

            return abs(area) / 2.0

        return 100000.0  # Default value

    def _calculate_centralization(self, formants: List[Dict[str, Any]]) -> float:
        """Calculate degree of vowel centralization."""
        if not formants:
            return 0.0

        # Calculate centroid
        f1_values = [f["F1"] for f in formants if f.get("F1")]
        f2_values = [f["F2"] for f in formants if f.get("F2")]

        if not f1_values or not f2_values:
            return 0.0

        centroid_f1 = np.mean(f1_values)
        centroid_f2 = np.mean(f2_values)

        # Calculate average distance from centroid
        distances = []
        for f1, f2 in zip(f1_values, f2_values):
            dist = np.sqrt((f1 - centroid_f1) ** 2 + (f2 - centroid_f2) ** 2)
            distances.append(dist)

        avg_distance = np.mean(distances)

        # Normalize (lower distance = more centralized)
        # Expected distance for clear speech is ~400 Hz
        centralization = max(0, 1.0 - avg_distance / 400.0)

        return float(centralization)

    def _calculate_vowel_consistency(self, formants: List[Dict[str, Any]]) -> float:
        """Calculate consistency of vowel production."""
        if len(formants) < 2:
            return 1.0

        # Group formants by similar F1/F2 values (likely same vowel)
        # Simplified clustering
        f1_values = np.array([f["F1"] for f in formants if f.get("F1")])
        f2_values = np.array([f["F2"] for f in formants if f.get("F2")])

        if len(f1_values) < 2:
            return 1.0

        # Calculate within-cluster variance
        # Using simplified approach - variance of all values
        f1_variance = np.var(f1_values)
        f2_variance = np.var(f2_values)

        # Lower variance = higher consistency
        consistency = 1.0 / (1.0 + (f1_variance + f2_variance) / 10000)

        return float(consistency)

    def _analyze_formant_transitions(self, formants: List[Dict[str, Any]]) -> float:
        """Analyze smoothness of formant transitions."""
        if len(formants) < 3:
            return 1.0

        # Calculate rate of change in formants
        f1_values = [f["F1"] for f in formants if f.get("F1")]
        f2_values = [f["F2"] for f in formants if f.get("F2")]
        times = [f["time"] for f in formants if f.get("F1")]

        if len(f1_values) < 3:
            return 1.0

        # Calculate derivatives
        f1_velocity = np.diff(f1_values) / np.diff(times)
        f2_velocity = np.diff(f2_values) / np.diff(times)

        # Smooth transitions have consistent velocity
        f1_smoothness = 1.0 / (1.0 + np.std(f1_velocity) / 1000)
        f2_smoothness = 1.0 / (1.0 + np.std(f2_velocity) / 1000)

        return float((f1_smoothness + f2_smoothness) / 2.0)

    def _calculate_spectral_moments(self, magnitude: np.ndarray) -> Dict[str, float]:
        """Calculate spectral moments for place of articulation analysis."""
        # Calculate moments for each frame
        freqs = librosa.fft_frequencies(sr=16000, n_fft=magnitude.shape[0] * 2 - 1)

        moments: Dict[str, List[float]] = {
            "centroid": [],
            "spread": [],
            "skewness": [],
            "kurtosis": [],
        }

        for frame in magnitude.T:
            if np.sum(frame) > 0:
                # Centroid
                centroid = np.sum(freqs * frame) / np.sum(frame)
                moments["centroid"].append(centroid)

                # Spread
                spread = np.sqrt(
                    np.sum((freqs - centroid) ** 2 * frame) / np.sum(frame)
                )
                moments["spread"].append(spread)

                # Skewness
                if spread > 0:
                    skewness = np.sum((freqs - centroid) ** 3 * frame) / (
                        np.sum(frame) * spread**3
                    )
                    moments["skewness"].append(skewness)

                # Kurtosis
                if spread > 0:
                    kurtosis = np.sum((freqs - centroid) ** 4 * frame) / (
                        np.sum(frame) * spread**4
                    )
                    moments["kurtosis"].append(kurtosis)

        # Return averages
        return {
            "centroid": (
                float(np.mean(moments["centroid"])) if moments["centroid"] else 0.0
            ),
            "spread": float(np.mean(moments["spread"])) if moments["spread"] else 0.0,
            "skewness": (
                float(np.mean(moments["skewness"])) if moments["skewness"] else 0.0
            ),
            "kurtosis": (
                float(np.mean(moments["kurtosis"])) if moments["kurtosis"] else 0.0
            ),
        }

    def _estimate_place_accuracy(
        self, spectral_moments: Dict[str, float], place: str
    ) -> float:
        """Estimate accuracy for a place of articulation."""
        # Simplified estimation based on spectral characteristics
        # In production, would use trained models

        centroid = spectral_moments["centroid"]

        if place == "bilabial":
            # Bilabials have lower spectral centroid
            return min(1.0, max(0, 1.0 - centroid / 2000))
        elif place == "alveolar":
            # Alveolars have mid-range centroid
            return min(1.0, 1.0 - abs(centroid - 3000) / 3000)
        elif place == "velar":
            # Velars have specific F2-F3 patterns
            return min(1.0, max(0, 1.0 - abs(centroid - 2000) / 2000))

        return 0.5

    def _estimate_manner_accuracy(
        self, audio_data: np.ndarray, sample_rate: int, manner: str
    ) -> float:
        """Estimate accuracy for a manner of articulation."""
        # Simplified estimation

        if manner == "stop":
            # Stops have silence followed by burst
            return self._detect_stop_accuracy(audio_data, sample_rate)
        elif manner == "fricative":
            # Fricatives have high-frequency noise
            return self._detect_fricative_accuracy(audio_data, sample_rate)
        elif manner == "nasal":
            # Nasals have low F1 and nasal formants
            return self._detect_nasal_accuracy(audio_data, sample_rate)
        elif manner == "liquid":
            # Liquids have specific formant patterns
            return self._detect_liquid_accuracy(audio_data, sample_rate)

        return 0.5

    def _detect_stop_accuracy(self, audio_data: np.ndarray, sample_rate: int) -> float:
        """Detect accuracy of stop consonant production."""
        # Look for silence-burst patterns
        envelope = np.abs(signal.hilbert(audio_data))

        # Smooth envelope
        envelope_smooth = gaussian_filter1d(envelope, sigma=int(0.005 * sample_rate))

        # Find rapid increases (bursts)
        derivative = np.diff(envelope_smooth)
        bursts = signal.find_peaks(derivative, height=np.std(derivative) * 2)[0]

        if len(bursts) > 0:
            # Check if bursts are preceded by silence
            accuracy_scores = []
            for burst_idx in bursts:
                if burst_idx > int(0.02 * sample_rate):
                    pre_burst = envelope_smooth[
                        burst_idx - int(0.02 * sample_rate) : burst_idx
                    ]
                    if np.mean(pre_burst) < 0.1 * envelope_smooth[burst_idx]:
                        accuracy_scores.append(1.0)
                    else:
                        accuracy_scores.append(0.5)

            return float(np.mean(accuracy_scores)) if accuracy_scores else 0.5

        return 0.3

    def _detect_fricative_accuracy(
        self, audio_data: np.ndarray, sample_rate: int
    ) -> float:
        """Detect accuracy of fricative production."""
        # sample_rate will be used for frequency band analysis in future
        _ = sample_rate

        # Fricatives have high-frequency energy
        stft = librosa.stft(audio_data)
        magnitude = np.abs(stft)

        # High frequency energy ratio
        high_freq_bins = magnitude[magnitude.shape[0] // 2 :, :]
        low_freq_bins = magnitude[: magnitude.shape[0] // 2, :]

        high_energy = np.mean(high_freq_bins)
        low_energy = np.mean(low_freq_bins)

        if low_energy > 0:
            hf_ratio = high_energy / low_energy
            # Good fricatives have high HF ratio
            return float(min(1.0, hf_ratio / 0.5))

        return 0.5

    def _detect_nasal_accuracy(self, audio_data: np.ndarray, sample_rate: int) -> float:
        """Detect accuracy of nasal consonant production."""
        # Nasals have low F1 and anti-formants
        # Simplified detection based on spectral characteristics

        # Use sample_rate for frequency calculations
        stft = librosa.stft(audio_data, sr=sample_rate)
        magnitude = np.abs(stft)

        # Look for low-frequency dominance
        low_freq_energy = np.mean(magnitude[: magnitude.shape[0] // 4, :])
        total_energy = np.mean(magnitude)

        if total_energy > 0:
            lf_ratio = low_freq_energy / total_energy
            # Nasals have high LF ratio
            return float(min(1.0, lf_ratio * 2))

        return 0.5

    def _detect_liquid_accuracy(
        self, audio_data: np.ndarray, sample_rate: int
    ) -> float:
        """Detect accuracy of liquid consonant production."""
        # Liquids have specific F3 patterns
        # Simplified detection

        # Extract formants
        formants = self._extract_frame_formants(audio_data, sample_rate)

        if len(formants) >= 3:
            f3 = formants[2]
            # /r/ has low F3, /l/ has high F3
            # Check for clear F3
            if 1500 < f3 < 3500:
                return 0.8

        return 0.5

    async def _analyze_phonemes(
        self, audio_data: np.ndarray, sample_rate: int, transcription: Optional[str]
    ) -> PhonemeMetrics:
        """Analyze phoneme-level accuracy and patterns."""
        metrics = PhonemeMetrics()

        if self.config.use_forced_alignment and transcription:
            # Use forced alignment to get phoneme boundaries
            phoneme_segments = await self._get_forced_alignment(
                audio_data, sample_rate, transcription
            )
        else:
            # Use acoustic segmentation
            phoneme_segments = await self._acoustic_segmentation(
                audio_data, sample_rate
            )

        if not phoneme_segments:
            return metrics

        # Analyze each phoneme segment
        correct_phonemes = 0
        total_phonemes = len(phoneme_segments)

        for segment in phoneme_segments:
            phoneme = segment["phoneme"]
            start_time = segment["start"]
            end_time = segment["end"]

            # Extract segment audio
            start_sample = int(start_time * sample_rate)
            end_sample = int(end_time * sample_rate)
            segment_audio = audio_data[start_sample:end_sample]

            if len(segment_audio) > 0:
                # Analyze phoneme realization
                accuracy = await self._analyze_phoneme_realization(
                    segment_audio, sample_rate, phoneme
                )

                metrics.phoneme_scores[phoneme] = accuracy

                if accuracy > 0.7:
                    correct_phonemes += 1
                elif accuracy < 0.3:
                    metrics.phoneme_omissions += 1
                else:
                    metrics.phoneme_substitutions += 1

        # Calculate overall accuracy
        metrics.phoneme_accuracy = (
            correct_phonemes / total_phonemes if total_phonemes > 0 else 0
        )

        # Analyze distinctive features
        metrics.voicing_accuracy = await self._analyze_voicing_accuracy(
            phoneme_segments, audio_data, sample_rate
        )
        metrics.place_accuracy = self._analyze_place_accuracy(phoneme_segments)
        metrics.manner_accuracy = self._analyze_manner_accuracy(phoneme_segments)

        # Detect phonological processes
        metrics.final_consonant_deletion = self._detect_final_consonant_deletion(
            phoneme_segments
        )
        metrics.cluster_reduction = self._detect_cluster_reduction(phoneme_segments)
        metrics.stopping = self._detect_stopping(phoneme_segments)
        metrics.fronting = self._detect_fronting(phoneme_segments)
        metrics.gliding = self._detect_gliding(phoneme_segments)

        return metrics

    async def _get_forced_alignment(
        self, audio_data: np.ndarray, sample_rate: int, transcription: str
    ) -> List[Dict[str, Any]]:
        """Get forced alignment using production service."""
        from src.voice.forced_alignment_service import (  # noqa: PLC0415
            forced_alignment_service,
        )

        # Use the production forced alignment service
        segments = await forced_alignment_service.perform_forced_alignment(
            audio_data=audio_data,
            sample_rate=sample_rate,
            transcription=transcription,
            language="en-US",  # Default language
        )

        return segments

    async def _acoustic_segmentation(
        self, audio_data: np.ndarray, sample_rate: int
    ) -> List[Dict[str, Any]]:
        """Segment audio into phoneme-like units using acoustic cues."""
        segments = []

        # Use spectral change detection
        stft = librosa.stft(audio_data, hop_length=int(0.005 * sample_rate))
        magnitude = np.abs(stft)

        # Calculate spectral flux
        flux = np.sum(np.diff(magnitude, axis=1) ** 2, axis=0)

        # Find peaks in flux (segment boundaries)
        peaks, _ = signal.find_peaks(
            flux, distance=int(0.03 * sample_rate / (0.005 * sample_rate))
        )

        # Create segments
        boundaries = [0] + list(peaks * int(0.005 * sample_rate)) + [len(audio_data)]

        for i in range(len(boundaries) - 1):
            if boundaries[i + 1] - boundaries[i] > int(0.02 * sample_rate):
                segments.append(
                    {
                        "phoneme": "UNK",  # Unknown
                        "start": boundaries[i] / sample_rate,
                        "end": boundaries[i + 1] / sample_rate,
                    }
                )

        return segments

    async def _analyze_phoneme_realization(
        self, segment_audio: np.ndarray, sample_rate: int, target_phoneme: str
    ) -> float:
        """Analyze how well a phoneme was realized."""
        # target_phoneme will be used for comparison with reference patterns in future
        _ = target_phoneme

        # Extract features from segment
        if len(segment_audio) < 100:
            return 0.0

        # MFCC features
        mfccs = librosa.feature.mfcc(y=segment_audio, sr=sample_rate, n_mfcc=13)

        # Compare with reference patterns
        # Simplified - in production would use trained models
        feature_quality = 1.0 - np.mean(np.abs(mfccs)) / 100

        return float(max(0, min(1, feature_quality)))

    async def _analyze_voicing_accuracy(
        self, segments: List[Dict[str, Any]], audio_data: np.ndarray, sample_rate: int
    ) -> float:
        """Analyze accuracy of voicing distinctions."""
        if not segments:
            return 0.0

        voicing_scores = []

        for segment in segments:
            start_sample = int(segment["start"] * sample_rate)
            end_sample = int(segment["end"] * sample_rate)
            segment_audio = audio_data[start_sample:end_sample]

            if len(segment_audio) > 100:
                # Check voicing using zero crossing rate and energy
                zcr = np.mean(librosa.feature.zero_crossing_rate(segment_audio))
                energy = np.mean(segment_audio**2)

                # Voiced sounds have low ZCR and high energy
                voicing_clarity = (1.0 - zcr) * min(1.0, energy * 100)
                voicing_scores.append(voicing_clarity)

        return np.mean(voicing_scores) if voicing_scores else 0.0

    def _analyze_place_accuracy(self, segments: List[Dict[str, Any]]) -> float:
        """Analyze accuracy of place of articulation."""
        # segments parameter will be used for detailed analysis in future
        _ = segments

        # Simplified analysis based on phoneme scores
        if not segments:
            return 0.0

        # In production, would analyze actual place features
        return 0.75  # Placeholder

    def _analyze_manner_accuracy(self, segments: List[Dict[str, Any]]) -> float:
        """Analyze accuracy of manner of articulation."""
        # segments parameter will be used for detailed analysis in future
        _ = segments

        # Simplified analysis
        if not segments:
            return 0.0

        return 0.75  # Placeholder

    def _detect_final_consonant_deletion(self, segments: List[Dict[str, Any]]) -> float:
        """Detect final consonant deletion pattern."""
        # segments parameter will be used for pattern analysis in future
        _ = segments

        # Check if final consonants are missing
        # Simplified detection
        return 0.1  # Placeholder - low value indicates minimal deletion

    def _detect_cluster_reduction(self, segments: List[Dict[str, Any]]) -> float:
        """Detect consonant cluster reduction."""
        # segments parameter will be used for cluster analysis in future
        _ = segments

        # Check for simplified consonant clusters
        return 0.1  # Placeholder

    def _detect_stopping(self, segments: List[Dict[str, Any]]) -> float:
        """Detect stopping of fricatives."""
        # segments parameter will be used for fricative analysis in future
        _ = segments  # noqa: F841
        # Check if fricatives are replaced with stops
        return 0.1  # Placeholder

    def _detect_fronting(self, segments: List[Dict[str, Any]]) -> float:
        """Detect fronting of back sounds."""
        # Fronting is when back sounds (like /k/, /g/) are produced more forward (like /t/, /d/)
        back_sounds = {"k", "g", "ŋ", "ɡ"}  # Back consonants
        front_replacements = {"t", "d", "n"}  # Common front replacements

        fronting_count = 0
        back_sound_count = 0

        for segment in segments:
            phoneme = segment.get("phoneme", "").lower()
            if phoneme in back_sounds:
                back_sound_count += 1
                # Check if followed by a front sound replacement
                segment_index = segments.index(segment)
                if segment_index < len(segments) - 1:
                    next_phoneme = (
                        segments[segment_index + 1].get("phoneme", "").lower()
                    )
                    if next_phoneme in front_replacements:
                        fronting_count += 1

        # Calculate fronting score (0-1, where 1 is maximum fronting)
        if back_sound_count > 0:
            return fronting_count / back_sound_count
        return 0.0

    def _detect_gliding(self, segments: List[Dict[str, Any]]) -> float:
        """Detect gliding of liquids."""
        # Gliding is when liquid sounds (/r/, /l/) are replaced with glides (/w/, /j/)
        liquids = {"r", "l", "ɹ", "ɾ", "ɭ", "ʎ"}  # Liquid consonants
        glides = {"w", "j", "ɥ", "ɰ"}  # Glide sounds

        gliding_count = 0.0
        liquid_count = 0

        for i, segment in enumerate(segments):
            phoneme = segment.get("phoneme", "").lower()
            if phoneme in liquids:
                liquid_count += 1

                # Check context for gliding patterns
                # Look at surrounding segments for evidence of gliding
                confidence = segment.get("confidence", 1.0)

                # Low confidence on liquids might indicate gliding
                if confidence < 0.7:
                    gliding_count += 0.5

                # Check if there's a glide nearby that might be a substitution
                if i > 0:
                    prev_phoneme = segments[i - 1].get("phoneme", "").lower()
                    if prev_phoneme in glides:
                        gliding_count += 0.5

                if i < len(segments) - 1:
                    next_phoneme = segments[i + 1].get("phoneme", "").lower()
                    if next_phoneme in glides:
                        gliding_count += 0.5

        # Calculate gliding score (0-1, where 1 is maximum gliding)
        if liquid_count > 0:
            return min(1.0, gliding_count / liquid_count)
        return 0.0

    async def _analyze_prosody(
        self, audio_data: np.ndarray, sample_rate: int
    ) -> ProsodyMetrics:
        """Analyze prosodic features affecting intelligibility."""
        metrics = ProsodyMetrics()

        # Extract pitch contour
        f0_values = self._extract_pitch_contour(audio_data, sample_rate)

        # Analyze speaking rate
        syllable_count = self._estimate_syllable_count(audio_data, sample_rate)
        duration = len(audio_data) / sample_rate
        speaking_rate = syllable_count / duration if duration > 0 else 0

        # Check if rate is appropriate
        if (
            self.config.normal_speaking_rate[0]
            <= speaking_rate
            <= self.config.normal_speaking_rate[1]
        ):
            metrics.speaking_rate_appropriateness = 1.0
        else:
            # Calculate how far from normal
            if speaking_rate < self.config.normal_speaking_rate[0]:
                metrics.speaking_rate_appropriateness = (
                    speaking_rate / self.config.normal_speaking_rate[0]
                )
            else:
                metrics.speaking_rate_appropriateness = (
                    self.config.normal_speaking_rate[1] / speaking_rate
                )

        # Rhythm consistency
        metrics.rhythm_consistency = self._analyze_rhythm_consistency(
            audio_data, sample_rate
        )

        # Syllable duration variance
        syllable_durations = self._get_syllable_durations(audio_data, sample_rate)
        if syllable_durations:
            metrics.syllable_duration_variance = float(
                np.std(syllable_durations) / np.mean(syllable_durations)
            )

        # Stress patterns
        metrics.lexical_stress_accuracy = self._analyze_lexical_stress(
            audio_data, sample_rate, f0_values
        )
        metrics.sentence_stress_appropriateness = self._analyze_sentence_stress(
            f0_values
        )

        # Intonation
        if f0_values is not None and len(f0_values) > 0:
            # Pitch range
            pitch_range = np.max(f0_values) - np.min(f0_values)
            expected_range = 100  # Hz
            metrics.pitch_range_adequacy = min(1.0, pitch_range / expected_range)

            # Intonation naturalness
            metrics.intonation_naturalness = self._analyze_intonation_naturalness(
                f0_values
            )

            # Boundary marking
            metrics.boundary_marking_clarity = self._analyze_boundary_marking(
                f0_values, audio_data, sample_rate
            )

        # Pausing
        pause_analysis = self._analyze_pauses(audio_data, sample_rate)
        metrics.pause_placement_appropriateness = pause_analysis["placement_score"]
        metrics.pause_duration_appropriateness = pause_analysis["duration_score"]

        return metrics

    def _extract_pitch_contour(
        self, audio_data: np.ndarray, sample_rate: int
    ) -> Optional[np.ndarray]:
        """Extract fundamental frequency contour."""
        try:
            # Using parselmouth for robust pitch extraction
            sound = parselmouth.Sound(audio_data, sample_rate)
            pitch = sound.to_pitch(
                time_step=0.01,
                pitch_floor=self.config.pitch_range[0],
                pitch_ceiling=self.config.pitch_range[1],
            )

            # Extract F0 values
            f0_values = []
            for i in range(pitch.n_frames):
                value = pitch.get_value_in_frame(i)
                if value is not None and value > 0:
                    f0_values.append(value)
                else:
                    f0_values.append(np.nan)

            return np.array(f0_values)

        except (ValueError, AttributeError, RuntimeError):
            # Fallback to librosa
            f0, _, _ = librosa.pyin(
                audio_data,
                fmin=self.config.pitch_range[0],
                fmax=self.config.pitch_range[1],
                sr=sample_rate,
            )
            return cast(Optional[np.ndarray], f0)

    def _estimate_syllable_count(self, audio_data: np.ndarray, sample_rate: int) -> int:
        """Estimate number of syllables in speech."""
        # Use amplitude envelope peaks as syllable nuclei
        envelope = np.abs(signal.hilbert(audio_data))

        # Smooth envelope
        envelope_smooth = gaussian_filter1d(envelope, sigma=int(0.02 * sample_rate))

        # Find peaks (syllable nuclei)
        peaks, _ = signal.find_peaks(
            envelope_smooth,
            distance=int(0.1 * sample_rate),  # Min 100ms between syllables
            height=np.max(envelope_smooth) * 0.3,
        )

        return len(peaks)

    def _analyze_rhythm_consistency(
        self, audio_data: np.ndarray, sample_rate: int
    ) -> float:
        """Analyze consistency of speech rhythm."""
        # Get syllable intervals
        envelope = np.abs(signal.hilbert(audio_data))
        envelope_smooth = gaussian_filter1d(envelope, sigma=int(0.02 * sample_rate))

        peaks, _ = signal.find_peaks(
            envelope_smooth,
            distance=int(0.1 * sample_rate),
            height=np.max(envelope_smooth) * 0.3,
        )

        if len(peaks) < 2:
            return 1.0

        # Calculate inter-syllable intervals
        intervals = np.diff(peaks) / sample_rate

        # Consistency is inverse of normalized standard deviation
        if np.mean(intervals) > 0:
            consistency = float(1.0 / (1.0 + np.std(intervals) / np.mean(intervals)))
        else:
            consistency = 0.5

        return consistency

    def _get_syllable_durations(
        self, audio_data: np.ndarray, sample_rate: int
    ) -> List[float]:
        """Extract syllable durations."""
        # Simplified approach using energy envelope
        envelope = np.abs(signal.hilbert(audio_data))
        envelope_smooth = gaussian_filter1d(envelope, sigma=int(0.01 * sample_rate))

        # Threshold for syllable boundaries
        threshold = np.max(envelope_smooth) * 0.2

        # Find syllable boundaries
        above_threshold = envelope_smooth > threshold
        boundaries = np.where(np.diff(above_threshold.astype(int)))[0]

        durations = []
        for i in range(0, len(boundaries) - 1, 2):
            if i + 1 < len(boundaries):
                duration = (boundaries[i + 1] - boundaries[i]) / sample_rate
                if 0.05 < duration < 0.5:  # Reasonable syllable duration
                    durations.append(duration)

        return durations

    def _analyze_lexical_stress(
        self, audio_data: np.ndarray, sample_rate: int, f0_values: Optional[np.ndarray]
    ) -> float:
        """Analyze accuracy of lexical stress patterns."""
        # Simplified analysis - check for appropriate stress contrasts
        if f0_values is None or len(f0_values) < 10:
            return 0.5

        # Remove NaN values
        valid_f0 = f0_values[~np.isnan(f0_values)]
        if len(valid_f0) < 10:
            return 0.5

        # Look for pitch accents (local maxima)
        smoothed_f0 = gaussian_filter1d(valid_f0, sigma=3)

        # Find peaks (stressed syllables)
        peaks, _ = signal.find_peaks(smoothed_f0, prominence=10)

        if len(peaks) > 0:
            # Check if stress pattern is reasonable
            # Expect 1 stress per 2-4 syllables
            syllable_count = self._estimate_syllable_count(audio_data, sample_rate)
            expected_stresses = syllable_count / 3

            ratio = len(peaks) / expected_stresses if expected_stresses > 0 else 0

            # Score based on how close to expected
            if 0.5 <= ratio <= 2.0:
                return 1.0
            else:
                return max(0, 1.0 - abs(ratio - 1.0) / 2.0)

        return 0.3

    def _analyze_sentence_stress(self, f0_values: Optional[np.ndarray]) -> float:
        """Analyze appropriateness of sentence-level stress."""
        if f0_values is None or len(f0_values) < 20:
            return 0.5

        # Check for appropriate declination and final lowering
        valid_f0 = f0_values[~np.isnan(f0_values)]
        if len(valid_f0) < 20:
            return 0.5

        # Fit linear trend
        x = np.arange(len(valid_f0))
        slope, _ = np.polyfit(x, valid_f0, 1)

        # Expect slight declination
        if -5 < slope < -0.1:
            declination_score = 1.0
        else:
            declination_score = 0.5

        # Check for final lowering
        final_portion = valid_f0[-len(valid_f0) // 5 :]
        initial_portion = valid_f0[: len(valid_f0) // 5]

        if np.mean(final_portion) < np.mean(initial_portion):
            final_lowering_score = 1.0
        else:
            final_lowering_score = 0.5

        return (declination_score + final_lowering_score) / 2.0

    def _analyze_intonation_naturalness(self, f0_values: np.ndarray) -> float:
        """Analyze naturalness of intonation patterns."""
        if len(f0_values) < 10:
            return 0.5

        valid_f0 = f0_values[~np.isnan(f0_values)]
        if len(valid_f0) < 10:
            return 0.5

        # Check for appropriate variation
        f0_std = np.std(valid_f0)
        f0_mean = np.mean(valid_f0)

        if f0_mean > 0:
            cv = f0_std / f0_mean  # Coefficient of variation

            # Natural speech has CV around 0.2-0.3
            if 0.15 <= cv <= 0.35:
                variation_score = 1.0
            else:
                variation_score = max(0, 1.0 - abs(cv - 0.25) * 4)
        else:
            variation_score = 0.0

        # Check for smooth contours (not too jumpy)
        f0_diff = np.diff(valid_f0)
        smoothness = 1.0 / (1.0 + np.mean(np.abs(f0_diff)) / 10)

        return float((variation_score + smoothness) / 2.0)

    def _analyze_boundary_marking(
        self, f0_values: np.ndarray, audio_data: np.ndarray, sample_rate: int
    ) -> float:
        """Analyze clarity of prosodic boundary marking."""
        # Look for pitch resets and pauses at boundaries
        if len(f0_values) < 20:
            return 0.5

        # Detect potential boundary locations
        # Using energy dips and pitch resets
        envelope = np.abs(signal.hilbert(audio_data))
        envelope_smooth = gaussian_filter1d(envelope, sigma=int(0.05 * sample_rate))

        # Find significant dips
        inverted = -envelope_smooth
        boundaries, _ = signal.find_peaks(inverted, prominence=np.std(envelope_smooth))

        if len(boundaries) > 0:
            # Check if boundaries have pitch resets
            boundary_scores = []

            for boundary_idx in boundaries:
                # Convert to F0 index
                f0_idx = int(boundary_idx / len(audio_data) * len(f0_values))

                if 10 < f0_idx < len(f0_values) - 10:
                    # Check for pitch reset
                    pre_boundary = f0_values[f0_idx - 10 : f0_idx]
                    post_boundary = f0_values[f0_idx : f0_idx + 10]

                    pre_mean = np.nanmean(pre_boundary)
                    post_mean = np.nanmean(post_boundary)

                    if not np.isnan(pre_mean) and not np.isnan(post_mean):
                        # Look for pitch reset (rise after boundary)
                        if post_mean > pre_mean:
                            boundary_scores.append(1.0)
                        else:
                            boundary_scores.append(0.5)

            return float(np.mean(boundary_scores)) if boundary_scores else 0.5

        return 0.5

    def _analyze_pauses(
        self, audio_data: np.ndarray, sample_rate: int
    ) -> Dict[str, Any]:
        """Analyze pause placement and duration."""
        # Detect pauses using energy
        envelope = np.abs(signal.hilbert(audio_data))
        envelope_smooth = gaussian_filter1d(envelope, sigma=int(0.01 * sample_rate))

        # Threshold for pause detection
        threshold = np.max(envelope_smooth) * 0.1

        # Find pause regions
        below_threshold = envelope_smooth < threshold

        # Get pause boundaries
        boundaries = np.where(np.diff(below_threshold.astype(int)))[0]

        pauses = []
        for i in range(0, len(boundaries) - 1, 2):
            if i + 1 < len(boundaries):
                pause_start = boundaries[i]
                pause_end = boundaries[i + 1]
                pause_duration = (pause_end - pause_start) / sample_rate

                if pause_duration > 0.1:  # Min pause duration
                    pauses.append(
                        {
                            "start": pause_start / sample_rate,
                            "end": pause_end / sample_rate,
                            "duration": pause_duration,
                        }
                    )

        # Analyze pause placement
        placement_score = 1.0
        if pauses:
            # Check if pauses occur at reasonable intervals
            inter_pause_intervals = []
            for i in range(1, len(pauses)):
                interval = pauses[i]["start"] - pauses[i - 1]["end"]
                inter_pause_intervals.append(interval)

            if inter_pause_intervals:
                # Expect pauses every 2-5 seconds
                mean_interval = np.mean(inter_pause_intervals)
                if 2.0 <= mean_interval <= 5.0:
                    placement_score = 1.0
                else:
                    placement_score = max(0, 1.0 - abs(mean_interval - 3.5) / 3.5)

        # Analyze pause duration
        duration_score = 1.0
        if pauses:
            pause_durations = [p["duration"] for p in pauses]
            mean_duration = np.mean(pause_durations)

            # Normal pause duration 0.2-0.8 seconds
            if 0.2 <= mean_duration <= 0.8:
                duration_score = 1.0
            else:
                duration_score = max(0, 1.0 - abs(mean_duration - 0.5) / 0.5)

        return {
            "placement_score": placement_score,
            "duration_score": duration_score,
            "pause_count": len(pauses),
            "pauses": pauses,
        }

    async def _analyze_acoustic_clarity(
        self, audio_data: np.ndarray, sample_rate: int
    ) -> AcousticClarityMetrics:
        """Analyze acoustic clarity factors."""
        metrics = AcousticClarityMetrics()

        # Compute STFT for spectral analysis
        stft = librosa.stft(audio_data)
        magnitude = np.abs(stft)
        freqs = librosa.fft_frequencies(sr=sample_rate)

        # Spectral tilt
        mean_spectrum = np.mean(magnitude, axis=1)
        if len(mean_spectrum) > 1 and len(freqs) > 1:
            # Fit line to log spectrum
            log_freqs = np.log10(freqs[1:] + 1)  # Avoid log(0)
            log_magnitude = np.log10(mean_spectrum[1:] + 1e-10)

            slope, _ = np.polyfit(log_freqs, log_magnitude, 1)
            metrics.spectral_tilt = -slope  # Positive tilt = more HF energy

        # High frequency energy
        hf_boundary = 3000  # Hz
        hf_bins = freqs > hf_boundary
        if np.any(hf_bins):
            metrics.high_frequency_energy = np.mean(magnitude[hf_bins, :]) / np.mean(
                magnitude
            )

        # Formant clarity
        metrics.formant_clarity = await self._analyze_formant_clarity(
            audio_data, sample_rate
        )

        # Spectral moments clarity
        moments = self._calculate_spectral_moments(magnitude)
        # Clear speech has moderate centroid and low spread
        centroid_score = 1.0 - abs(moments["centroid"] - 2000) / 2000
        spread_score = 1.0 / (1.0 + moments["spread"] / 1000)
        metrics.spectral_moments_clarity = (centroid_score + spread_score) / 2

        # Envelope modulation depth
        metrics.envelope_modulation_depth = self._calculate_modulation_depth(
            audio_data, sample_rate
        )

        # Temporal fine structure
        metrics.temporal_fine_structure = self._analyze_temporal_fine_structure(
            audio_data, sample_rate
        )

        # SNR estimation
        metrics.signal_to_noise_ratio = self._estimate_snr(audio_data, sample_rate)

        # HNR (reuse from voice quality)
        metrics.harmonic_to_noise_ratio = self._calculate_hnr_simple(
            audio_data, sample_rate
        )

        # Dynamic range
        envelope = np.abs(signal.hilbert(audio_data))
        if len(envelope) > 0:
            metrics.dynamic_range = 20 * np.log10(
                np.max(envelope) / (np.mean(envelope) + 1e-10)
            )
            metrics.peak_to_average_ratio = np.max(envelope) / np.mean(envelope)

        return metrics

    async def _analyze_formant_clarity(
        self, audio_data: np.ndarray, sample_rate: int
    ) -> float:
        """Analyze clarity of formant structure."""
        # Extract formants
        formants = await self._extract_vowel_formants(audio_data, sample_rate)

        if not formants:
            return 0.5

        clarity_scores = []

        for formant_data in formants:
            if "F1" in formant_data and "F2" in formant_data:
                # Check if formants are in expected ranges
                f1 = formant_data["F1"]
                f2 = formant_data["F2"]

                # Clear formants are well-separated and in normal ranges
                if 200 < f1 < 1000 and 800 < f2 < 3000:
                    separation = abs(f2 - f1)
                    if separation > 500:
                        clarity_scores.append(1.0)
                    else:
                        clarity_scores.append(separation / 500)
                else:
                    clarity_scores.append(0.5)

        return float(np.mean(clarity_scores)) if clarity_scores else 0.5

    def _calculate_modulation_depth(
        self, audio_data: np.ndarray, sample_rate: int
    ) -> float:
        """Calculate amplitude modulation depth."""
        # sample_rate will be used for modulation frequency analysis in future
        _ = sample_rate

        # Get envelope
        envelope = np.abs(signal.hilbert(audio_data))

        # Low-pass filter to get slow modulations
        b, a = butter(4, 30 / (sample_rate / 2), btype="low")
        envelope_smooth = filtfilt(b, a, envelope)

        # Calculate modulation depth
        if np.mean(envelope_smooth) > 0:
            modulation_depth = np.std(envelope_smooth) / np.mean(envelope_smooth)
            # Normalize to 0-1 range (good speech has depth around 0.3-0.5)
            return float(min(1.0, modulation_depth * 2))

        return 0.0

    def _analyze_temporal_fine_structure(
        self, audio_data: np.ndarray, sample_rate: int
    ) -> float:
        """Analyze preservation of temporal fine structure."""
        # sample_rate will be used for frequency analysis in future
        _ = sample_rate

        # Use zero-crossing patterns
        zcr = librosa.feature.zero_crossing_rate(audio_data, hop_length=64)[0]

        # Clear speech has consistent ZCR patterns
        zcr_consistency = 1.0 / (1.0 + np.std(zcr))

        # Also check for phase coherence using autocorrelation
        autocorr = np.correlate(audio_data[:1000], audio_data[:1000], mode="full")
        autocorr = autocorr[len(autocorr) // 2 :]

        # Find first peak after zero lag
        peaks, _ = signal.find_peaks(autocorr[1:], height=0.3 * autocorr[0])

        if len(peaks) > 0:
            # Strong periodicity indicates good temporal structure
            periodicity_score = min(1.0, autocorr[peaks[0] + 1] / autocorr[0])
        else:
            periodicity_score = 0.5

        return float((zcr_consistency + periodicity_score) / 2)

    def _estimate_snr(self, audio_data: np.ndarray, sample_rate: int) -> float:
        """Estimate signal-to-noise ratio."""
        # Find quiet portions using frame-based energy calculation
        frame_length = int(0.025 * sample_rate)  # 25ms frames
        if len(audio_data) < frame_length:
            frame_length = len(audio_data)

        envelope = np.abs(signal.hilbert(audio_data))
        threshold = np.percentile(envelope, 20)

        noise_segments = audio_data[envelope < threshold]
        signal_segments = audio_data[envelope >= threshold]

        if len(noise_segments) > 0 and len(signal_segments) > 0:
            noise_power = np.mean(noise_segments**2)
            signal_power = np.mean(signal_segments**2)

            if noise_power > 0:
                snr = 10 * np.log10(signal_power / noise_power)
                return float(max(0, snr))

        return 20.0  # Default reasonable SNR

    def _calculate_hnr_simple(self, audio_data: np.ndarray, sample_rate: int) -> float:
        """Calculate simple harmonics-to-noise ratio."""
        # Compute autocorrelation
        autocorr = np.correlate(audio_data, audio_data, mode="full")
        autocorr = autocorr[len(autocorr) // 2 :]

        # Find harmonic peak
        search_region = autocorr[int(0.002 * sample_rate) : int(0.02 * sample_rate)]
        if len(search_region) > 0:
            harmonic_peak = np.max(search_region)
            noise_floor = np.mean(autocorr[int(0.02 * sample_rate) :])

            if noise_floor > 0:
                hnr = 10 * np.log10(harmonic_peak / noise_floor)
                return float(max(0, hnr))

        return 15.0  # Default

    async def _analyze_contextual_factors(
        self, audio_data: np.ndarray, sample_rate: int
    ) -> ContextualFactors:
        """Analyze contextual factors affecting intelligibility."""
        factors = ContextualFactors()

        # Estimate background noise level
        envelope = np.abs(signal.hilbert(audio_data))
        quiet_threshold = np.percentile(envelope, 10)
        quiet_segments = audio_data[envelope < quiet_threshold]

        if len(quiet_segments) > 0:
            noise_level = 20 * np.log10(np.sqrt(np.mean(quiet_segments**2)) + 1e-10)
            factors.background_noise_level = noise_level

        # Estimate reverberation (simplified)
        factors.reverberation_estimate = self._estimate_reverberation(
            audio_data, sample_rate
        )

        # Estimate vocal effort
        factors.vocal_effort = self._estimate_vocal_effort(audio_data, sample_rate)

        # Speaking style clarity
        # Based on articulation and prosody features
        factors.speaking_style_clarity = 0.75  # Placeholder

        # Estimated listening effort (inverse of clarity)
        clarity_score = self._estimate_overall_clarity(audio_data, sample_rate)
        factors.estimated_listening_effort = 1.0 - clarity_score

        # Predicted comprehension
        factors.predicted_comprehension = (
            clarity_score * 0.9
        )  # Slightly lower than clarity

        # Redundancy level (simplified)
        factors.redundancy_level = 0.5  # Placeholder

        # Context availability
        factors.context_availability = 0.5  # Placeholder

        return factors

    def _estimate_reverberation(
        self, audio_data: np.ndarray, sample_rate: int
    ) -> float:
        """Estimate amount of reverberation."""
        # Simplified estimation using decay rate
        envelope = np.abs(signal.hilbert(audio_data))

        # Find peaks
        peaks, _ = signal.find_peaks(envelope, distance=int(0.1 * sample_rate))

        if len(peaks) > 1:
            # Check decay after peaks
            decay_rates = []

            for peak in peaks[:-1]:
                if peak + int(0.1 * sample_rate) < len(envelope):
                    peak_val = envelope[peak]
                    decay_val = envelope[peak + int(0.05 * sample_rate)]

                    if peak_val > 0:
                        decay_rate = decay_val / peak_val
                        decay_rates.append(decay_rate)

            if decay_rates:
                # High decay rate indicates reverb
                avg_decay = np.mean(decay_rates)
                reverb_estimate = max(0, avg_decay - 0.3) / 0.7
                return float(reverb_estimate)

        return 0.1  # Low reverb default

    def _estimate_vocal_effort(self, audio_data: np.ndarray, sample_rate: int) -> float:
        """Estimate vocal effort level."""
        # Based on intensity and high-frequency emphasis

        # Overall intensity
        intensity = 20 * np.log10(np.sqrt(np.mean(audio_data**2)) + 1e-10)

        # High-frequency emphasis (effort often increases HF)
        stft = librosa.stft(audio_data)
        magnitude = np.abs(stft)
        freqs = librosa.fft_frequencies(sr=sample_rate)

        hf_energy = np.mean(magnitude[freqs > 2000, :])
        lf_energy = np.mean(magnitude[freqs <= 2000, :])

        if lf_energy > 0:
            hf_emphasis = hf_energy / lf_energy
        else:
            hf_emphasis = 0

        # Combine factors
        # Normal speech around -20 dB, high effort > -15 dB
        intensity_factor = min(1.0, max(0, (intensity + 15) / 10))
        emphasis_factor = min(1.0, hf_emphasis * 2)

        return float((intensity_factor + emphasis_factor) / 2)

    def _estimate_overall_clarity(
        self, audio_data: np.ndarray, sample_rate: int
    ) -> float:
        """Quick estimate of overall clarity."""
        # Combine multiple factors

        # SNR factor
        snr = self._estimate_snr(audio_data, sample_rate)
        snr_factor = min(1.0, snr / 30)

        # Modulation factor
        mod_depth = self._calculate_modulation_depth(audio_data, sample_rate)

        # Spectral clarity
        stft = librosa.stft(audio_data)
        magnitude = np.abs(stft)
        spectral_contrast = np.std(np.mean(magnitude, axis=1))
        contrast_factor = min(1.0, float(spectral_contrast / 10))

        return float((snr_factor + mod_depth + contrast_factor) / 3)

    def _calculate_overall_score(
        self,
        articulation: ArticulationMetrics,
        phonemes: PhonemeMetrics,
        prosody: ProsodyMetrics,
        clarity: AcousticClarityMetrics,
    ) -> float:
        """Calculate overall intelligibility score."""
        # Weighted combination of all factors

        # Articulation score
        articulation_score = np.mean(
            [
                articulation.consonant_precision,
                articulation.vowel_space_area / 300000,  # Normalize
                articulation.coarticulation_smoothness,
                articulation.transition_clarity,
            ]
        )

        # Phoneme score
        phoneme_score = phonemes.phoneme_accuracy

        # Prosody score
        prosody_score = np.mean(
            [
                prosody.speaking_rate_appropriateness,
                prosody.intonation_naturalness,
                prosody.pause_placement_appropriateness,
            ]
        )

        # Clarity score
        clarity_score = np.mean(
            [
                min(1.0, clarity.signal_to_noise_ratio / 30),
                clarity.formant_clarity,
                clarity.envelope_modulation_depth,
            ]
        )

        # Weighted combination
        overall = (
            self.config.articulation_weight * articulation_score
            + self.config.phoneme_weight * phoneme_score
            + self.config.prosody_weight * prosody_score
            + self.config.clarity_weight * clarity_score
        )

        # Convert to 0-100 scale
        return float(overall * 100)

    def _determine_intelligibility_level(self, score: float) -> IntelligibilityLevel:
        """Determine intelligibility level from score."""
        if score >= 95:
            return IntelligibilityLevel.EXCELLENT
        elif score >= 85:
            return IntelligibilityLevel.GOOD
        elif score >= 70:
            return IntelligibilityLevel.FAIR
        elif score >= 50:
            return IntelligibilityLevel.POOR
        else:
            return IntelligibilityLevel.VERY_POOR

    def _estimate_noisy_environment_score(
        self, quiet_score: float, clarity: AcousticClarityMetrics
    ) -> float:
        """Estimate intelligibility in noisy environment."""
        # Degradation based on acoustic clarity metrics

        # SNR impact
        snr_factor = min(1.0, clarity.signal_to_noise_ratio / 20)

        # High frequency content helps in noise
        hf_factor = clarity.high_frequency_energy

        # Modulation depth crucial in noise
        mod_factor = clarity.envelope_modulation_depth

        # Apply degradation
        noise_resistance = (snr_factor + hf_factor + mod_factor) / 3
        noisy_score = quiet_score * (0.5 + 0.5 * noise_resistance)

        return noisy_score

    def _estimate_telephone_score(
        self, quiet_score: float, clarity: AcousticClarityMetrics
    ) -> float:
        """Estimate intelligibility over telephone."""
        # Telephone bandwidth: 300-3400 Hz

        # Factors that help with telephone
        # - Good formant structure in mid frequencies
        # - Clear consonants
        # - Appropriate speaking rate

        # Formant clarity is crucial
        formant_factor = clarity.formant_clarity

        # Mid-frequency energy
        # Spectral tilt shouldn't be too steep
        tilt_factor = 1.0 / (1.0 + abs(clarity.spectral_tilt))

        # Apply telephone degradation
        telephone_factor = (formant_factor + tilt_factor) / 2
        telephone_score = quiet_score * (0.7 + 0.3 * telephone_factor)

        return telephone_score

    async def _detect_speech_disorders(
        self,
        articulation: ArticulationMetrics,
        phonemes: PhonemeMetrics,
        prosody: ProsodyMetrics,
        clarity: AcousticClarityMetrics,
    ) -> Tuple[List[SpeechDisorderType], Dict[str, float]]:
        """Detect potential speech disorders affecting intelligibility."""
        disorders = []
        severities = {}

        # Dysarthria detection
        dysarthria_indicators = [
            articulation.consonant_precision < 0.7,
            articulation.coarticulation_smoothness < 0.5,
            prosody.speaking_rate_appropriateness < 0.7,
            clarity.envelope_modulation_depth < 0.3,
        ]

        if sum(dysarthria_indicators) >= 3:
            disorders.append(SpeechDisorderType.DYSARTHRIA)
            severities["dysarthria"] = sum(dysarthria_indicators) / 4

        # Apraxia detection
        if (
            articulation.consonant_distortion > 0.4
            and phonemes.phoneme_substitutions > phonemes.phoneme_omissions
            and prosody.syllable_duration_variance > 0.5
        ):
            disorders.append(SpeechDisorderType.APRAXIA)
            severities["apraxia"] = articulation.consonant_distortion

        # Stuttering detection
        if (
            prosody.rhythm_consistency < 0.5
            and prosody.pause_placement_appropriateness < 0.6
        ):
            disorders.append(SpeechDisorderType.STUTTERING)
            severities["stuttering"] = 1.0 - prosody.rhythm_consistency

        # Voice disorder impact on intelligibility
        if clarity.harmonic_to_noise_ratio < 10:
            disorders.append(SpeechDisorderType.VOICE_DISORDER)
            severities["voice_disorder"] = 1.0 - clarity.harmonic_to_noise_ratio / 20

        # Developmental patterns
        if (
            phonemes.fronting > 0.3
            or phonemes.stopping > 0.3
            or phonemes.final_consonant_deletion > 0.3
        ):
            disorders.append(SpeechDisorderType.DEVELOPMENTAL)
            severities["developmental"] = max(
                phonemes.fronting, phonemes.stopping, phonemes.final_consonant_deletion
            )

        if not disorders:
            disorders.append(SpeechDisorderType.NONE)

        return disorders, severities

    def _identify_issues(
        self,
        articulation: ArticulationMetrics,
        phonemes: PhonemeMetrics,
        prosody: ProsodyMetrics,
        clarity: AcousticClarityMetrics,
    ) -> Tuple[List[str], List[str]]:
        """Identify primary and secondary issues affecting intelligibility."""
        issues = []

        # Check articulation issues
        if articulation.consonant_precision < 0.7:
            issues.append(
                ("Imprecise consonant production", articulation.consonant_precision)
            )

        if articulation.vowel_space_area < 200000:
            issues.append(
                ("Reduced vowel space", articulation.vowel_space_area / 300000)
            )

        if articulation.coarticulation_smoothness < 0.6:
            issues.append(
                ("Poor coarticulation", articulation.coarticulation_smoothness)
            )

        # Check phoneme issues
        if phonemes.phoneme_accuracy < 0.8:
            issues.append(("Low phoneme accuracy", phonemes.phoneme_accuracy))

        if phonemes.phoneme_substitutions > 5:
            issues.append(("Frequent sound substitutions", 0.5))

        # Check prosody issues
        if prosody.speaking_rate_appropriateness < 0.7:
            issues.append(
                ("Inappropriate speaking rate", prosody.speaking_rate_appropriateness)
            )

        if prosody.intonation_naturalness < 0.6:
            issues.append(("Unnatural intonation", prosody.intonation_naturalness))

        # Check clarity issues
        if clarity.signal_to_noise_ratio < 15:
            issues.append(
                ("Poor signal-to-noise ratio", clarity.signal_to_noise_ratio / 30)
            )

        if clarity.formant_clarity < 0.6:
            issues.append(("Unclear formant structure", clarity.formant_clarity))

        # Sort by severity
        issues.sort(key=lambda x: x[1])

        # Split into primary and secondary
        primary = [issue[0] for issue in issues[:3]]
        secondary = [issue[0] for issue in issues[3:6]]

        return primary, secondary

    def _generate_therapy_recommendations(
        self, primary_issues: List[str], disorders: List[SpeechDisorderType]
    ) -> List[str]:
        """Generate therapy recommendations based on identified issues."""
        recommendations = []

        # Issue-specific recommendations
        for issue in primary_issues:
            if "consonant" in issue.lower():
                recommendations.append(
                    "Articulation therapy focusing on consonant precision"
                )
                recommendations.append(
                    "Minimal pairs practice for consonant distinctions"
                )

            elif "vowel" in issue.lower():
                recommendations.append("Vowel differentiation exercises")
                recommendations.append("Visual feedback for vowel production")

            elif "rate" in issue.lower():
                recommendations.append("Rate control exercises")
                recommendations.append("Paced speaking practice with metronome")

            elif "intonation" in issue.lower():
                recommendations.append("Prosody training with pitch contours")
                recommendations.append("Emotional expression exercises")

            elif "coarticulation" in issue.lower():
                recommendations.append("Connected speech exercises")
                recommendations.append("Phrase-level practice")

        # Disorder-specific recommendations
        if SpeechDisorderType.DYSARTHRIA in disorders:
            recommendations.append("Oro-motor strengthening exercises")
            recommendations.append("Respiratory support training")

        if SpeechDisorderType.APRAXIA in disorders:
            recommendations.append("Motor planning exercises")
            recommendations.append("PROMPT therapy consideration")

        if SpeechDisorderType.STUTTERING in disorders:
            recommendations.append("Fluency shaping techniques")
            recommendations.append("Stuttering modification approach")

        # Remove duplicates
        return list(set(recommendations))

    def _generate_compensatory_strategies(
        self, primary_issues: List[str], context: CommunicationContext
    ) -> List[str]:
        """Generate compensatory strategies for immediate use."""
        strategies = []

        # General strategies
        strategies.append("Face the listener directly")
        strategies.append("Reduce background noise when possible")

        # Issue-specific strategies
        for issue in primary_issues:
            if "consonant" in issue.lower():
                strategies.append("Slightly exaggerate consonant sounds")
                strategies.append("Use clear word boundaries")

            elif "rate" in issue.lower():
                strategies.append("Consciously slow down speech")
                strategies.append("Pause between phrases")

            elif "vowel" in issue.lower():
                strategies.append("Open mouth wider for clearer vowels")

            elif "noise" in issue.lower():
                strategies.append("Increase vocal effort slightly")
                strategies.append("Use repetition for important words")

        # Context-specific strategies
        if context == CommunicationContext.NOISY_ENVIRONMENT:
            strategies.append("Get closer to listener")
            strategies.append("Use gestures to support speech")

        elif context == CommunicationContext.TELEPHONE:
            strategies.append("Spell out important words")
            strategies.append("Confirm understanding frequently")

        elif context == CommunicationContext.MEDICAL_CONSULTATION:
            strategies.append("Prepare key points in advance")
            strategies.append("Bring written notes as backup")

        # Remove duplicates
        return list(set(strategies))

    def _calculate_confidence(self, audio_data: np.ndarray, sample_rate: int) -> float:
        """Calculate confidence in the analysis results."""
        confidence_factors = []

        # Audio duration
        duration = len(audio_data) / sample_rate
        if duration > 2.0:
            confidence_factors.append(1.0)
        else:
            confidence_factors.append(duration / 2.0)

        # Signal quality
        snr = self._estimate_snr(audio_data, sample_rate)
        confidence_factors.append(min(1.0, snr / 20))

        # Clipping check
        max_amplitude = np.max(np.abs(audio_data))
        if max_amplitude < 0.99:
            confidence_factors.append(1.0)
        else:
            confidence_factors.append(0.7)

        return float(np.mean(confidence_factors))

    def _assess_recording_quality(
        self, audio_data: np.ndarray, sample_rate: int
    ) -> Tuple[float, List[str]]:
        """Assess recording quality and generate warnings."""
        quality_warnings = []
        quality_factors = []

        # Check duration
        duration = len(audio_data) / sample_rate
        if duration < 1.0:
            quality_warnings.append("Recording too short for comprehensive analysis")
            quality_factors.append(0.5)
        else:
            quality_factors.append(1.0)

        # Check for clipping
        max_amplitude = np.max(np.abs(audio_data))
        if max_amplitude > 0.99:
            quality_warnings.append("Audio clipping detected")
            quality_factors.append(0.5)
        else:
            quality_factors.append(1.0)

        # Check SNR
        snr = self._estimate_snr(audio_data, sample_rate)
        if snr < 10:
            quality_warnings.append("Low signal-to-noise ratio")
            quality_factors.append(snr / 20)
        else:
            quality_factors.append(1.0)

        # Check for DC offset
        dc_offset = np.mean(audio_data)
        if abs(dc_offset) > 0.1:
            quality_warnings.append("DC offset detected in audio")
            quality_factors.append(0.8)
        else:
            quality_factors.append(1.0)

        recording_quality = float(np.mean(quality_factors))

        return recording_quality, quality_warnings

    def _calculate_speech_duration(
        self, audio_data: np.ndarray, sample_rate: int
    ) -> float:
        """Calculate duration of actual speech (excluding silence)."""
        # Energy-based voice activity detection
        frame_length = int(0.025 * sample_rate)
        hop_length = int(0.010 * sample_rate)

        frames = librosa.util.frame(
            audio_data, frame_length=frame_length, hop_length=hop_length
        )
        energy = np.sum(frames**2, axis=0)

        # Threshold
        threshold = np.percentile(energy, 30)
        speech_frames = energy > threshold

        speech_duration = np.sum(speech_frames) * (hop_length / sample_rate)

        return float(speech_duration)

    async def analyze_word_list(
        self,
        audio_segments: List[np.ndarray],
        word_list: List[str],
        sample_rate: int = 16000,
    ) -> Dict[str, Any]:
        """
        Analyze intelligibility using word list test.

        Args:
            audio_segments: List of audio arrays, one per word
            word_list: List of target words
            sample_rate: Sample rate for all audio

        Returns:
            Dictionary with word-level and overall scores
        """
        if len(audio_segments) != len(word_list):
            raise ValueError("Number of audio segments must match word list length")

        word_scores = []
        word_results = {}

        for audio, word in zip(audio_segments, word_list):
            # Analyze each word
            result = await self.analyze_intelligibility(
                audio, sample_rate, transcription=word
            )

            word_scores.append(result.overall_intelligibility_score)
            word_results[word] = {
                "score": result.overall_intelligibility_score,
                "primary_issues": result.primary_issues,
                "confidence": result.confidence_score,
            }

        # Calculate overall statistics
        overall_score = np.mean(word_scores)
        consistency = 1.0 - np.std(word_scores) / 100  # Normalized std

        return {
            "overall_score": overall_score,
            "consistency": consistency,
            "word_results": word_results,
            "difficult_words": [
                word
                for word, data in word_results.items()
                if float(str(data["score"])) < overall_score - 10
            ],
        }

    async def analyze_conversation(
        self,
        audio_data: np.ndarray,
        sample_rate: int = 16000,
        speaker_segments: Optional[List[Tuple[float, float]]] = None,
    ) -> Dict[str, Any]:
        """
        Analyze intelligibility in conversational speech.

        Args:
            audio_data: Conversation audio
            sample_rate: Sample rate
            speaker_segments: Optional list of (start, end) times for speaker turns

        Returns:
            Conversation-level intelligibility analysis
        """
        # Overall analysis
        overall_result = await self.analyze_intelligibility(
            audio_data, sample_rate, context=CommunicationContext.MEDICAL_CONSULTATION
        )

        results: Dict[str, Any] = {
            "overall": overall_result.to_dict(),
            "turn_analysis": [],
        }

        if speaker_segments:
            # Analyze each speaker turn
            for start, end in speaker_segments:
                start_sample = int(start * sample_rate)
                end_sample = int(end * sample_rate)
                segment = audio_data[start_sample:end_sample]

                if len(segment) > sample_rate * 0.5:  # Min 0.5s
                    turn_result = await self.analyze_intelligibility(
                        segment, sample_rate
                    )
                    results["turn_analysis"].append(
                        {
                            "start": start,
                            "end": end,
                            "duration": end - start,
                            "score": turn_result.overall_intelligibility_score,
                            "level": turn_result.intelligibility_level.value,
                        }
                    )

        # Calculate conversation flow metrics
        if results["turn_analysis"]:
            scores = [float(turn["score"]) for turn in results["turn_analysis"]]
            results["conversation_metrics"] = {
                "mean_turn_score": np.mean(scores),
                "score_variance": np.var(scores),
                "improving_trend": scores[-1] > scores[0] if len(scores) > 1 else None,
            }

        return results


# Example usage functions
async def analyze_speech_sample(file_path: str) -> IntelligibilityResult:
    """Analyze a speech recording for intelligibility."""
    # file_path would be used to load actual audio file in production
    _ = file_path

    analyzer = IntelligibilityAnalyzer()

    # Simulate loading audio
    duration = 5.0
    sample_rate = 16000
    t = np.linspace(0, duration, int(sample_rate * duration))

    # Create synthetic speech with varying clarity
    # Clear vowel
    audio = 0.5 * np.sin(2 * np.pi * 200 * t[:sample_rate])
    audio += 0.3 * np.sin(2 * np.pi * 700 * t[:sample_rate])

    # Less clear consonant
    noise = 0.2 * np.random.randn(sample_rate // 2)
    audio = np.concatenate([audio, noise])

    # Another vowel
    audio2 = 0.5 * np.sin(2 * np.pi * 250 * t[:sample_rate])
    audio2 += 0.3 * np.sin(2 * np.pi * 2000 * t[:sample_rate])
    audio = np.concatenate([audio, audio2])

    # Add some background noise
    audio += 0.05 * np.random.randn(len(audio))

    # Truncate to match duration
    audio = audio[: int(sample_rate * duration)]

    result = await analyzer.analyze_intelligibility(audio, sample_rate)

    logger.info("Intelligibility analysis complete")
    logger.info(result.get_summary())

    return result


async def compare_speaking_conditions(file_path: str) -> Dict[str, Any]:
    """Compare intelligibility across different speaking conditions."""
    # file_path would be used to load actual audio file in production
    _ = file_path

    analyzer = IntelligibilityAnalyzer()

    # Simulate different conditions
    duration = 3.0
    sample_rate = 16000

    conditions = {}

    # Clear speech
    t = np.linspace(0, duration, int(sample_rate * duration))
    clear_audio = 0.7 * np.sin(2 * np.pi * 200 * t)
    clear_audio += 0.05 * np.random.randn(len(t))

    result = await analyzer.analyze_intelligibility(
        clear_audio, sample_rate, context=CommunicationContext.QUIET_ENVIRONMENT
    )
    conditions["clear"] = result

    # Noisy environment
    noisy_audio = clear_audio + 0.2 * np.random.randn(len(t))
    result = await analyzer.analyze_intelligibility(
        noisy_audio, sample_rate, context=CommunicationContext.NOISY_ENVIRONMENT
    )
    conditions["noisy"] = result

    # Compare results
    comparison = {
        "clear_score": conditions["clear"].overall_intelligibility_score,
        "noisy_score": conditions["noisy"].overall_intelligibility_score,
        "degradation": conditions["clear"].overall_intelligibility_score
        - conditions["noisy"].overall_intelligibility_score,
        "recommendations": conditions["noisy"].compensatory_strategies,
    }

    return comparison


if __name__ == "__main__":
    # Run example analysis
    async def main() -> None:
        """Run example intelligibility analysis."""
        # Test basic analysis
        result = await analyze_speech_sample("sample.wav")
        print(f"Intelligibility Score: {result.overall_intelligibility_score:.1f}")
        print(f"Level: {result.intelligibility_level.value}")

        # Test condition comparison
        comparison = await compare_speaking_conditions("sample.wav")
        print("\nCondition Comparison:")
        print(f"Clear: {comparison['clear_score']:.1f}")
        print(f"Noisy: {comparison['noisy_score']:.1f}")

    asyncio.run(main())
