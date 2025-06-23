"""Pain Level Assessment Module for Medical Voice Analysis.

This module implements pain level detection and assessment from voice
recordings for medical evaluation and pain management.

Note: Pain assessment data constitutes PHI. All audio recordings and assessment
results must be encrypted both in transit and at rest. Implement strict access
control to ensure only authorized healthcare providers can access pain data.
"""

# pylint: disable=too-many-lines

import json
import logging
from collections import deque
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

logger = logging.getLogger(__name__)


class PainLevel(Enum):
    """Pain levels based on clinical pain scales."""

    NO_PAIN = "no_pain"  # 0/10 - No pain
    MILD = "mild"  # 1-3/10 - Mild, annoying pain
    MODERATE = "moderate"  # 4-6/10 - Interferes with tasks
    SEVERE = "severe"  # 7-8/10 - Interferes with concentration
    VERY_SEVERE = "very_severe"  # 9/10 - Cannot do most activities
    WORST_POSSIBLE = "worst_possible"  # 10/10 - Emergency level pain


class PainType(Enum):
    """Types of pain that can be detected from voice."""

    ACUTE = "acute"  # Sudden onset, sharp
    CHRONIC = "chronic"  # Long-term, persistent
    NEUROPATHIC = "neuropathic"  # Nerve pain (burning, tingling)
    NOCICEPTIVE = "nociceptive"  # Tissue damage (aching, throbbing)
    VISCERAL = "visceral"  # Internal organ pain
    SOMATIC = "somatic"  # Musculoskeletal pain
    REFERRED = "referred"  # Pain felt away from source
    BREAKTHROUGH = "breakthrough"  # Sudden pain spike


class PainIndicator(Enum):
    """Voice indicators of pain."""

    VOCAL_FRY = "vocal_fry"  # Creaky voice
    VOICE_STRAIN = "voice_strain"  # Strained vocal quality
    PITCH_BREAKS = "pitch_breaks"  # Sudden pitch changes
    BREATHINESS = "breathiness"  # Breathy voice quality
    TENSION = "tension"  # Muscular tension in voice
    TREMOR = "tremor"  # Voice tremor from pain
    GRUNT_SOUNDS = "grunt_sounds"  # Pain vocalizations
    SPEECH_PAUSES = "speech_pauses"  # Frequent pausing
    VOLUME_REDUCTION = "volume_reduction"  # Reduced voice volume
    ARTICULATION_CHANGES = "articulation_changes"  # Impaired articulation


class PainDescriptor(Enum):
    """Common pain descriptors that affect voice."""

    SHARP = "sharp"
    DULL = "dull"
    BURNING = "burning"
    THROBBING = "throbbing"
    STABBING = "stabbing"
    ACHING = "aching"
    CRAMPING = "cramping"
    SHOOTING = "shooting"
    TENDER = "tender"
    GNAWING = "gnawing"


@dataclass
class PainFeatures:
    """Acoustic features for pain assessment."""

    # Fundamental frequency features
    f0_mean: float = 0.0
    f0_std: float = 0.0
    f0_range: float = 0.0
    f0_tremor_rate: float = 0.0
    f0_tremor_amplitude: float = 0.0

    # Voice quality features specific to pain
    vocal_fry_ratio: float = 0.0  # Percentage of vocal fry
    strain_index: float = 0.0  # Overall strain measure
    breathiness_index: float = 0.0  # H1-H2 ratio
    roughness_index: float = 0.0  # Perturbation measures

    # Tension indicators
    laryngeal_tension: float = 0.0  # Estimated from spectral tilt
    pharyngeal_tension: float = 0.0  # Formant shifts
    global_tension: float = 0.0  # Overall tension score

    # Temporal pain features
    pause_frequency: float = 0.0  # Pauses per minute
    pause_duration_mean: float = 0.0  # Average pause length
    speech_rate_variability: float = 0.0  # Inconsistent speaking rate

    # Spectral pain markers
    spectral_centroid_elevation: float = 0.0  # Higher with pain
    harmonic_structure_deviation: float = 0.0  # Harmonic irregularity
    spectral_flux_instability: float = 0.0  # Spectral instability

    # Pain-specific vocalizations
    grunt_detection: float = 0.0  # Presence of grunts/moans
    gasp_detection: float = 0.0  # Sharp intakes of breath
    vocalization_intensity: float = 0.0  # Non-speech sounds

    # Prosodic features
    pitch_contour_flatness: float = 0.0  # Reduced prosody
    amplitude_modulation: float = 0.0  # Volume variations
    rhythm_disruption: float = 0.0  # Speech rhythm changes

    # Articulation features
    vowel_centralization: float = 0.0  # Reduced vowel space
    consonant_precision: float = 0.0  # Articulation clarity
    coarticulation_index: float = 0.0  # Speech motor control

    def to_dict(self) -> Dict[str, float]:
        """Convert features to dictionary."""
        return {
            "f0_mean": self.f0_mean,
            "f0_std": self.f0_std,
            "f0_tremor_amplitude": self.f0_tremor_amplitude,
            "vocal_fry_ratio": self.vocal_fry_ratio,
            "strain_index": self.strain_index,
            "breathiness_index": self.breathiness_index,
            "laryngeal_tension": self.laryngeal_tension,
            "pause_frequency": self.pause_frequency,
            "spectral_centroid_elevation": self.spectral_centroid_elevation,
            "grunt_detection": self.grunt_detection,
            "pitch_contour_flatness": self.pitch_contour_flatness,
            "vowel_centralization": self.vowel_centralization,
        }

    def calculate_pain_score(self) -> float:
        """Calculate composite pain score from features."""
        # Weight different aspects of pain
        weights = {
            "voice_quality": 0.3,
            "tension": 0.25,
            "temporal": 0.2,
            "spectral": 0.15,
            "vocalizations": 0.1,
        }

        # Voice quality score
        voice_quality_score = min(
            1.0,
            (
                self.vocal_fry_ratio * 2
                + self.strain_index
                + self.breathiness_index
                + self.roughness_index
            )
            / 4,
        )

        # Tension score
        tension_score = min(
            1.0,
            (self.laryngeal_tension + self.pharyngeal_tension + self.global_tension)
            / 3,
        )

        # Temporal score
        temporal_score = min(
            1.0,
            (
                min(1.0, self.pause_frequency / 20)
                + self.speech_rate_variability
                + self.rhythm_disruption
            )
            / 3,
        )

        # Spectral score
        spectral_score = min(
            1.0,
            (
                self.spectral_centroid_elevation
                + self.harmonic_structure_deviation
                + self.spectral_flux_instability
            )
            / 3,
        )

        # Vocalization score
        vocalization_score = min(
            1.0,
            (
                self.grunt_detection * 2  # Heavily weighted
                + self.gasp_detection
                + self.vocalization_intensity
            )
            / 3,
        )

        # Weighted combination
        total_score = (
            weights["voice_quality"] * voice_quality_score
            + weights["tension"] * tension_score
            + weights["temporal"] * temporal_score
            + weights["spectral"] * spectral_score
            + weights["vocalizations"] * vocalization_score
        )

        return total_score


@dataclass
class PainAssessmentResult:
    """Result of pain assessment analysis."""

    pain_level: PainLevel
    pain_score: float  # 0-10 scale matching clinical scales

    # Pain characteristics
    pain_types: List[PainType] = field(default_factory=list)
    pain_descriptors: List[PainDescriptor] = field(default_factory=list)
    active_indicators: List[PainIndicator] = field(default_factory=list)

    # Detailed features
    features: Optional[PainFeatures] = None

    # Temporal analysis
    pain_timeline: List[Tuple[float, float]] = field(
        default_factory=list
    )  # (time, pain_score)
    pain_variability: float = 0.0
    pain_peaks: List[Tuple[float, float]] = field(
        default_factory=list
    )  # (time, intensity)
    breakthrough_events: List[float] = field(default_factory=list)  # Timestamps

    # Clinical information
    functional_impact: str = ""  # How pain affects function
    pain_behavior_score: float = 0.0  # Observable pain behaviors
    suffering_index: float = 0.0  # Emotional component

    # Pain location hints (from voice characteristics)
    likely_locations: List[str] = field(default_factory=list)

    # Recommendations
    assessment_notes: List[str] = field(default_factory=list)
    intervention_suggestions: List[str] = field(default_factory=list)

    # Quality metrics
    confidence_score: float = 0.0
    assessment_reliability: float = 0.0

    # Processing metadata
    audio_duration: float = 0.0
    processing_time_ms: float = 0.0
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "pain_level": self.pain_level.value,
            "pain_score": self.pain_score,
            "pain_types": [t.value for t in self.pain_types],
            "pain_descriptors": [d.value for d in self.pain_descriptors],
            "active_indicators": [i.value for i in self.active_indicators],
            "features": self.features.to_dict() if self.features else None,
            "pain_timeline": self.pain_timeline,
            "pain_variability": self.pain_variability,
            "pain_peaks": self.pain_peaks,
            "breakthrough_events": self.breakthrough_events,
            "functional_impact": self.functional_impact,
            "pain_behavior_score": self.pain_behavior_score,
            "suffering_index": self.suffering_index,
            "likely_locations": self.likely_locations,
            "assessment_notes": self.assessment_notes,
            "intervention_suggestions": self.intervention_suggestions,
            "confidence_score": self.confidence_score,
            "assessment_reliability": self.assessment_reliability,
            "audio_duration": self.audio_duration,
            "processing_time_ms": self.processing_time_ms,
            "warnings": self.warnings,
        }

    def get_clinical_summary(self) -> str:
        """Generate clinical summary of pain assessment."""
        summary = f"Pain Level: {self.pain_level.value.replace('_', ' ').title()} "
        summary += f"({self.pain_score:.1f}/10)\n"

        if self.pain_types:
            summary += f"Pain Types: {', '.join(t.value for t in self.pain_types)}\n"

        if self.pain_descriptors:
            summary += f"Characteristics: {', '.join(d.value for d in self.pain_descriptors)}\n"

        if self.functional_impact:
            summary += f"Functional Impact: {self.functional_impact}\n"

        if self.breakthrough_events:
            summary += f"Breakthrough Pain Events: {len(self.breakthrough_events)}\n"

        return summary


@dataclass
class PainAssessmentConfig:
    """Configuration for pain assessment."""

    # Audio parameters
    sample_rate: int = 16000
    frame_length_ms: int = 30
    frame_shift_ms: int = 10

    # Analysis settings
    enable_temporal_analysis: bool = True
    temporal_window_size: float = 2.0  # seconds
    enable_vocalization_detection: bool = True
    enable_breakthrough_detection: bool = True

    # Pain scale mapping (0-10)
    pain_thresholds: Dict[str, float] = field(
        default_factory=lambda: {
            "no_pain": 0.5,
            "mild": 3.0,
            "moderate": 6.0,
            "severe": 8.0,
            "very_severe": 9.0,
            "worst_possible": 9.5,
        }
    )

    # Detection sensitivity
    vocal_fry_sensitivity: float = 0.8
    tension_sensitivity: float = 0.85
    vocalization_sensitivity: float = 0.9

    # Clinical settings
    use_behavioral_indicators: bool = True
    include_suffering_assessment: bool = True
    breakthrough_threshold: float = 2.0  # Point increase for breakthrough

    # Model settings
    use_ml_model: bool = False
    model_path: Optional[str] = None


class PainAssessor:
    """
    Assesses pain levels from voice recordings using acoustic analysis.

    Implements evidence-based voice biomarkers for pain detection and
    quantification for clinical assessment.
    """

    def __init__(self, config: Optional[PainAssessmentConfig] = None):
        """
        Initialize the pain assessor.

        Args:
            config: Assessment configuration
        """
        self.config = config or PainAssessmentConfig()

        # Frame parameters
        self.frame_length = int(
            self.config.sample_rate * self.config.frame_length_ms / 1000
        )
        self.frame_shift = int(
            self.config.sample_rate * self.config.frame_shift_ms / 1000
        )

        # Initialize pain patterns
        self._init_pain_patterns()

        # Initialize pain descriptors mapping
        self._init_descriptor_patterns()

        # Pain history for tracking
        self.pain_history: deque[PainAssessmentResult] = deque(maxlen=100)

        logger.info(
            "PainAssessor initialized with sample_rate=%dHz",
            config.sample_rate if config else self.config.sample_rate,
        )

    def _init_pain_patterns(self) -> None:
        """Initialize pain detection patterns."""
        self.pain_patterns = {
            PainType.ACUTE: {
                "indicators": [
                    PainIndicator.PITCH_BREAKS,
                    PainIndicator.GRUNT_SOUNDS,
                    PainIndicator.VOICE_STRAIN,
                ],
                "features": {
                    "f0_range": (50, 150),  # Wide pitch range
                    "strain_index": 0.7,
                    "vocalization_intensity": 0.6,
                },
            },
            PainType.CHRONIC: {
                "indicators": [
                    PainIndicator.VOCAL_FRY,
                    PainIndicator.BREATHINESS,
                    PainIndicator.VOLUME_REDUCTION,
                ],
                "features": {
                    "vocal_fry_ratio": 0.3,
                    "breathiness_index": 0.5,
                    "pitch_contour_flatness": 0.7,
                },
            },
            PainType.NEUROPATHIC: {
                "indicators": [
                    PainIndicator.TREMOR,
                    PainIndicator.TENSION,
                    PainIndicator.ARTICULATION_CHANGES,
                ],
                "features": {
                    "f0_tremor_amplitude": 5,
                    "global_tension": 0.7,
                    "vowel_centralization": 0.6,
                },
            },
        }

    def _init_descriptor_patterns(self) -> None:
        """Initialize pain descriptor patterns."""
        self.descriptor_patterns = {
            PainDescriptor.SHARP: {
                "f0_acceleration": 10,
                "spectral_flux": 0.8,
                "vocal_onset": "abrupt",
            },
            PainDescriptor.BURNING: {
                "breathiness": 0.7,
                "spectral_slope": -2.5,
                "sustained_tension": 0.8,
            },
            PainDescriptor.THROBBING: {
                "amplitude_modulation": 0.7,
                "rhythm_periodicity": 0.8,
                "f0_oscillation": 5,
            },
        }

    @requires_phi_access("read")
    async def assess_pain(
        self,
        audio_data: np.ndarray,
        baseline: Optional[PainFeatures] = None,
        _user_id: str = "system",
    ) -> PainAssessmentResult:
        """
        Assess pain levels from audio data.

        Args:
            audio_data: Audio signal as numpy array
            baseline: Optional baseline features for comparison

        Returns:
            PainAssessmentResult with comprehensive pain analysis
        """
        start_time = datetime.now()

        try:
            # Normalize audio
            audio_data = self._normalize_audio(audio_data)

            # Extract pain-related features
            features = await self._extract_pain_features(audio_data)

            # Calculate pain score
            raw_score = features.calculate_pain_score()

            # Adjust for baseline if provided
            if baseline:
                raw_score = self._adjust_for_baseline(features, baseline, raw_score)

            # Convert to 0-10 scale
            pain_score = raw_score * 10

            # Determine pain level
            pain_level = self._score_to_pain_level(pain_score)

            # Identify pain types
            pain_types = await self._identify_pain_types(features)

            # Identify pain descriptors
            pain_descriptors = self._identify_pain_descriptors(features)

            # Identify active indicators
            active_indicators = self._identify_active_indicators(features)

            # Temporal analysis
            pain_timeline = []
            pain_variability = 0.0
            pain_peaks = []
            breakthrough_events = []

            if self.config.enable_temporal_analysis:
                temporal_result = await self._analyze_temporal_pain(audio_data)
                pain_timeline = temporal_result["timeline"]
                pain_variability = temporal_result["variability"]
                pain_peaks = temporal_result["peaks"]

                if self.config.enable_breakthrough_detection:
                    breakthrough_events = self._detect_breakthrough_pain(pain_timeline)

            # Assess functional impact
            functional_impact = self._assess_functional_impact(pain_level, features)

            # Calculate pain behavior score
            pain_behavior_score = self._calculate_pain_behavior_score(
                features, active_indicators
            )

            # Assess suffering component
            suffering_index = 0.0
            if self.config.include_suffering_assessment:
                suffering_index = self._assess_suffering_component(features, pain_score)

            # Estimate pain location
            likely_locations = self._estimate_pain_locations(features, pain_types)

            # Generate assessment notes
            assessment_notes = self._generate_assessment_notes(
                pain_level, pain_types, features, active_indicators
            )

            # Generate intervention suggestions
            intervention_suggestions = self._generate_intervention_suggestions(
                pain_level, pain_types, breakthrough_events
            )

            # Calculate confidence and reliability
            confidence = self._calculate_confidence(features, len(active_indicators))
            reliability = self._assess_reliability(features, pain_variability)

            # Generate warnings
            warnings = self._generate_warnings(features, pain_score)

            # Processing time
            processing_time = (datetime.now() - start_time).total_seconds() * 1000

            # Create result object first
            result = PainAssessmentResult(
                pain_level=pain_level,
                pain_score=pain_score,
                pain_types=pain_types,
                pain_descriptors=pain_descriptors,
                active_indicators=active_indicators,
                features=features,
                pain_timeline=pain_timeline,
                pain_variability=pain_variability,
                pain_peaks=pain_peaks,
                breakthrough_events=breakthrough_events,
                functional_impact=functional_impact,
                pain_behavior_score=pain_behavior_score,
                suffering_index=suffering_index,
                likely_locations=likely_locations,
                assessment_notes=assessment_notes,
                intervention_suggestions=intervention_suggestions,
                confidence_score=confidence,
                assessment_reliability=reliability,
                audio_duration=len(audio_data) / self.config.sample_rate,
                processing_time_ms=processing_time,
                warnings=warnings,
            )

            # Store in history
            self.pain_history.append(result)

            return result

        except Exception as e:
            logger.error("Error in pain assessment: %s", str(e), exc_info=True)
            raise

    def _normalize_audio(self, audio_data: np.ndarray) -> np.ndarray:
        """Normalize audio to [-1, 1] range."""
        max_val = np.max(np.abs(audio_data))
        if max_val > 0:
            return np.array(audio_data / max_val)
        return audio_data

    async def _extract_pain_features(self, audio_data: np.ndarray) -> PainFeatures:
        """Extract comprehensive pain-related features."""
        features = PainFeatures()

        # Extract F0 features
        f0_features = self._extract_f0_features(audio_data)
        features.f0_mean = f0_features["mean"]
        features.f0_std = f0_features["std"]
        features.f0_range = f0_features["range"]
        features.f0_tremor_rate = f0_features["tremor_rate"]
        features.f0_tremor_amplitude = f0_features["tremor_amplitude"]

        # Extract voice quality features
        quality_features = self._extract_voice_quality_features(audio_data)
        features.vocal_fry_ratio = quality_features["vocal_fry"]
        features.strain_index = quality_features["strain"]
        features.breathiness_index = quality_features["breathiness"]
        features.roughness_index = quality_features["roughness"]

        # Extract tension features
        tension_features = self._extract_tension_features(audio_data)
        features.laryngeal_tension = tension_features["laryngeal"]
        features.pharyngeal_tension = tension_features["pharyngeal"]
        features.global_tension = tension_features["global"]

        # Extract temporal features
        temporal_features = self._extract_temporal_features(audio_data)
        features.pause_frequency = temporal_features["pause_frequency"]
        features.pause_duration_mean = temporal_features["pause_duration"]
        features.speech_rate_variability = temporal_features["rate_variability"]

        # Extract spectral pain markers
        spectral_features = self._extract_spectral_pain_markers(audio_data)
        features.spectral_centroid_elevation = spectral_features["centroid_elevation"]
        features.harmonic_structure_deviation = spectral_features["harmonic_deviation"]
        features.spectral_flux_instability = spectral_features["flux_instability"]

        # Detect pain vocalizations
        if self.config.enable_vocalization_detection:
            vocalization_features = await self._detect_pain_vocalizations(audio_data)
            features.grunt_detection = vocalization_features["grunts"]
            features.gasp_detection = vocalization_features["gasps"]
            features.vocalization_intensity = vocalization_features["intensity"]

        # Extract prosodic features
        prosodic_features = self._extract_prosodic_features(audio_data)
        features.pitch_contour_flatness = prosodic_features["flatness"]
        features.amplitude_modulation = prosodic_features["amp_modulation"]
        features.rhythm_disruption = prosodic_features["rhythm_disruption"]

        # Extract articulation features
        articulation_features = self._extract_articulation_features(audio_data)
        features.vowel_centralization = articulation_features["vowel_centralization"]
        features.consonant_precision = articulation_features["consonant_precision"]
        features.coarticulation_index = articulation_features["coarticulation"]

        return features

    def _extract_f0_features(self, audio_data: np.ndarray) -> Dict[str, float]:
        """Extract fundamental frequency features related to pain."""
        # Extract F0 using YIN algorithm
        f0 = librosa.yin(
            audio_data,
            fmin=50,
            fmax=500,
            sr=self.config.sample_rate,
            frame_length=self.frame_length * 4,
        )

        # Remove unvoiced segments
        voiced_f0 = f0[f0 > 0]

        features = {
            "mean": 0.0,
            "std": 0.0,
            "range": 0.0,
            "tremor_rate": 0.0,
            "tremor_amplitude": 0.0,
        }

        if len(voiced_f0) > 10:
            features["mean"] = np.mean(voiced_f0)
            features["std"] = np.std(voiced_f0)
            features["range"] = np.ptp(voiced_f0)

            # Tremor analysis
            # Detrend F0
            detrended_f0 = signal.detrend(voiced_f0)

            # Compute autocorrelation for tremor
            autocorr = np.correlate(detrended_f0, detrended_f0, mode="full")
            autocorr = autocorr[len(autocorr) // 2 :]
            autocorr = autocorr / autocorr[0]

            # Find tremor frequency (3-15 Hz range)
            frame_rate = self.config.sample_rate / self.frame_shift
            min_lag = int(frame_rate / 15)  # 15 Hz max
            max_lag = int(frame_rate / 3)  # 3 Hz min

            if max_lag < len(autocorr):
                tremor_region = autocorr[min_lag:max_lag]
                if len(tremor_region) > 0:
                    peaks, _ = signal.find_peaks(tremor_region, height=0.3)
                    if len(peaks) > 0:
                        tremor_lag = peaks[0] + min_lag
                        features["tremor_rate"] = frame_rate / tremor_lag
                        features["tremor_amplitude"] = np.std(detrended_f0)

        return features

    def _extract_voice_quality_features(
        self, audio_data: np.ndarray
    ) -> Dict[str, float]:
        """Extract voice quality features indicative of pain."""
        features = {
            "vocal_fry": 0.0,
            "strain": 0.0,
            "breathiness": 0.0,
            "roughness": 0.0,
        }

        # Vocal fry detection (very low F0)
        f0 = librosa.yin(
            audio_data,
            fmin=30,
            fmax=500,
            sr=self.config.sample_rate,
            frame_length=self.frame_length * 4,
        )

        total_voiced = np.sum(f0 > 0)
        if total_voiced > 0:
            vocal_fry_frames = np.sum((f0 > 30) & (f0 < 80))
            features["vocal_fry"] = vocal_fry_frames / total_voiced

        # Strain index (high-frequency energy)
        stft = librosa.stft(
            audio_data, n_fft=self.frame_length * 2, hop_length=self.frame_shift
        )
        magnitude = np.abs(stft)
        freqs = librosa.fft_frequencies(
            sr=self.config.sample_rate, n_fft=self.frame_length * 2
        )

        # High frequency ratio as strain indicator
        high_freq_idx = freqs > 3000
        mid_freq_idx = (freqs > 1000) & (freqs <= 3000)

        if np.sum(mid_freq_idx) > 0:
            high_energy = np.mean(magnitude[high_freq_idx, :])
            mid_energy = np.mean(magnitude[mid_freq_idx, :])
            features["strain"] = min(1.0, high_energy / (mid_energy + 1e-10))

        # Breathiness (H1-H2 measure)
        breathiness_values = []
        for frame_idx in range(magnitude.shape[1]):
            frame_mag = magnitude[:, frame_idx]

            # Find first two harmonics
            peaks, _ = signal.find_peaks(frame_mag, height=np.max(frame_mag) * 0.1)
            if len(peaks) >= 2:
                h1 = frame_mag[peaks[0]]
                h2 = frame_mag[peaks[1]]
                if h2 > 0:
                    breathiness_values.append(h1 / h2)

        if breathiness_values:
            features["breathiness"] = min(1.0, np.mean(breathiness_values) / 10)

        # Roughness (perturbation measures)
        # Simplified: using spectral flux variation
        spectral_flux = np.sum(np.diff(magnitude, axis=1) ** 2, axis=0)
        if len(spectral_flux) > 0:
            features["roughness"] = min(
                1.0, np.std(spectral_flux) / (np.mean(spectral_flux) + 1e-10)
            )

        return features

    def _extract_tension_features(self, audio_data: np.ndarray) -> Dict[str, float]:
        """Extract muscular tension features from voice."""
        features = {"laryngeal": 0.0, "pharyngeal": 0.0, "global": 0.0}

        # STFT for spectral analysis
        stft = librosa.stft(
            audio_data, n_fft=self.frame_length * 2, hop_length=self.frame_shift
        )
        magnitude = np.abs(stft)
        freqs = librosa.fft_frequencies(
            sr=self.config.sample_rate, n_fft=self.frame_length * 2
        )

        # Laryngeal tension (spectral tilt)
        tilt_values = []
        for frame_idx in range(magnitude.shape[1]):
            frame_mag = magnitude[:, frame_idx]
            if np.sum(frame_mag) > 0:
                # Linear regression of log magnitude vs log frequency
                valid_idx = (freqs > 100) & (frame_mag > 0)
                if np.sum(valid_idx) > 10:
                    log_freq = np.log(freqs[valid_idx])
                    log_mag = np.log(frame_mag[valid_idx] + 1e-10)
                    slope, _ = np.polyfit(log_freq, log_mag, 1)
                    tilt_values.append(abs(slope))

        if tilt_values:
            # Steeper negative slope indicates more tension
            features["laryngeal"] = min(1.0, np.mean(tilt_values) / 5)

        # Pharyngeal tension (formant analysis)
        # Simplified: using spectral centroid shift
        centroid = librosa.feature.spectral_centroid(
            y=audio_data, sr=self.config.sample_rate, hop_length=self.frame_shift
        )[0]

        if len(centroid) > 0:
            # Higher centroid indicates pharyngeal tension
            mean_centroid = np.mean(centroid)
            features["pharyngeal"] = min(1.0, mean_centroid / 3000)

        # Global tension (combination)
        features["global"] = (features["laryngeal"] + features["pharyngeal"]) / 2

        return features

    def _extract_temporal_features(self, audio_data: np.ndarray) -> Dict[str, float]:
        """Extract temporal features related to pain."""
        # Energy for speech/pause detection
        energy = librosa.feature.rms(
            y=audio_data, frame_length=self.frame_length, hop_length=self.frame_shift
        )[0]

        # Detect pauses
        energy_threshold = np.percentile(energy, 20)
        is_pause = energy < energy_threshold

        # Find pause segments
        pause_starts = []
        pause_durations = []
        in_pause = False
        pause_start = 0

        for i, frame_is_pause in enumerate(is_pause):
            if frame_is_pause and not in_pause:
                pause_start = i
                in_pause = True
            elif not frame_is_pause and in_pause:
                duration = (
                    (i - pause_start) * self.frame_shift / self.config.sample_rate
                )
                if duration > 0.1:  # Minimum pause duration
                    pause_starts.append(pause_start)
                    pause_durations.append(duration)
                in_pause = False

        # Calculate features
        audio_duration = len(audio_data) / self.config.sample_rate

        features = {
            "pause_frequency": float(
                len(pause_durations) * 60 / audio_duration if audio_duration > 0 else 0
            ),
            "pause_duration": (
                float(np.mean(pause_durations)) if pause_durations else 0.0
            ),
            "rate_variability": 0.0,
        }

        # Speech rate variability
        # Detect syllable nuclei (simplified)
        if len(energy) > 10:
            # Smooth energy
            smooth_energy = gaussian_filter1d(energy, sigma=2)

            # Find peaks (syllables)
            peaks, _ = signal.find_peaks(smooth_energy, height=np.mean(smooth_energy))

            if len(peaks) > 2:
                # Inter-syllable intervals
                intervals = np.diff(peaks) * self.frame_shift / self.config.sample_rate
                features["rate_variability"] = float(
                    np.std(intervals) / (np.mean(intervals) + 1e-10)
                )

        return features

    def _extract_spectral_pain_markers(
        self, audio_data: np.ndarray
    ) -> Dict[str, float]:
        """Extract spectral features that indicate pain."""
        features = {
            "centroid_elevation": 0.0,
            "harmonic_deviation": 0.0,
            "flux_instability": 0.0,
        }

        # Spectral centroid
        centroid = librosa.feature.spectral_centroid(
            y=audio_data, sr=self.config.sample_rate, hop_length=self.frame_shift
        )[0]

        if len(centroid) > 0:
            # Pain often causes centroid elevation
            mean_centroid = np.mean(centroid)
            # Normalize (normal speech ~1500-2000 Hz)
            features["centroid_elevation"] = min(
                1.0, max(0, (mean_centroid - 1500) / 2000)
            )

        # Harmonic structure analysis
        stft = librosa.stft(
            audio_data, n_fft=self.frame_length * 2, hop_length=self.frame_shift
        )
        magnitude = np.abs(stft)

        # Analyze harmonic regularity
        harmonic_scores = []
        for frame_idx in range(0, magnitude.shape[1], 10):  # Sample frames
            frame_mag = magnitude[:, frame_idx]

            # Autocorrelation of magnitude spectrum
            if np.sum(frame_mag) > 0:
                autocorr = np.correlate(frame_mag, frame_mag, mode="full")
                autocorr = autocorr[len(autocorr) // 2 :]

                # Find periodicity (harmonicity)
                if len(autocorr) > 100:
                    autocorr_norm = autocorr / (autocorr[0] + 1e-10)
                    # Look for regular peaks
                    peaks, _ = signal.find_peaks(autocorr_norm[20:100], height=0.3)
                    if len(peaks) > 1:
                        # Regular spacing indicates good harmonic structure
                        peak_intervals = np.diff(peaks)
                        regularity = 1 - np.std(peak_intervals) / (
                            np.mean(peak_intervals) + 1e-10
                        )
                        harmonic_scores.append(regularity)

        if harmonic_scores:
            # Low score indicates disrupted harmonics (pain)
            features["harmonic_deviation"] = 1 - np.mean(harmonic_scores)

        # Spectral flux instability
        spectral_flux = np.sqrt(np.sum(np.diff(magnitude, axis=1) ** 2, axis=0))
        if len(spectral_flux) > 1:
            # High variability in flux indicates instability
            features["flux_instability"] = min(
                1.0, np.std(spectral_flux) / (np.mean(spectral_flux) + 1e-10)
            )

        return features

    async def _detect_pain_vocalizations(
        self, audio_data: np.ndarray
    ) -> Dict[str, float]:
        """Detect non-speech pain vocalizations."""
        features = {"grunts": 0.0, "gasps": 0.0, "intensity": 0.0}

        # Energy envelope
        energy = librosa.feature.rms(
            y=audio_data, frame_length=self.frame_length, hop_length=self.frame_shift
        )[0]

        # Zero crossing rate (for detecting fricative sounds)
        zcr = librosa.feature.zero_crossing_rate(
            audio_data, frame_length=self.frame_length, hop_length=self.frame_shift
        )[0]

        # Spectral features
        spectral_rolloff = librosa.feature.spectral_rolloff(
            y=audio_data, sr=self.config.sample_rate, hop_length=self.frame_shift
        )[0]

        # Detect grunts (low frequency, high energy bursts)
        grunt_frames = 0
        for i, frame_energy in enumerate(energy):
            if (
                frame_energy > np.percentile(energy, 80)  # High energy
                and zcr[i] < np.percentile(zcr, 30)  # Low ZCR (voiced)
                and spectral_rolloff[i] < 2000
            ):  # Low frequency content
                grunt_frames += 1

        features["grunts"] = grunt_frames / len(energy) if len(energy) > 0 else 0

        # Detect gasps (sudden high-frequency bursts)
        gasp_frames = 0
        energy_diff = np.diff(energy)

        for i in range(1, len(energy_diff)):
            if energy_diff[i] > np.std(energy_diff) * 2 and zcr[  # Sudden increase
                i
            ] > np.percentile(
                zcr, 70
            ):  # High ZCR (fricative)
                gasp_frames += 1

        features["gasps"] = gasp_frames / len(energy) if len(energy) > 0 else 0

        # Overall vocalization intensity
        # Combination of non-speech vocal sounds
        features["intensity"] = min(
            1.0, (features["grunts"] * 2 + features["gasps"]) / 3
        )

        return features

    def _extract_prosodic_features(self, audio_data: np.ndarray) -> Dict[str, float]:
        """Extract prosodic features affected by pain."""
        features = {"flatness": 0.0, "amp_modulation": 0.0, "rhythm_disruption": 0.0}

        # Extract F0 contour
        f0 = librosa.yin(
            audio_data,
            fmin=50,
            fmax=500,
            sr=self.config.sample_rate,
            frame_length=self.frame_length * 4,
        )

        # Pitch contour flatness
        voiced_f0 = f0[f0 > 0]
        if len(voiced_f0) > 10:
            # Measure variation
            f0_variation = np.std(voiced_f0) / (np.mean(voiced_f0) + 1e-10)
            # Low variation = flat contour
            features["flatness"] = 1 / (1 + f0_variation * 5)

        # Amplitude modulation
        amplitude = librosa.feature.rms(
            y=audio_data, frame_length=self.frame_length, hop_length=self.frame_shift
        )[0]

        if len(amplitude) > 10:
            # Analyze amplitude envelope modulation
            # Smooth amplitude
            smooth_amplitude = gaussian_filter1d(amplitude, sigma=3)

            # Calculate modulation depth
            if np.mean(smooth_amplitude) > 0:
                modulation = np.std(smooth_amplitude) / np.mean(smooth_amplitude)
                features["amp_modulation"] = min(1.0, modulation)

        # Rhythm disruption
        # Detect rhythm from energy peaks
        energy = librosa.feature.rms(
            y=audio_data, frame_length=self.frame_length, hop_length=self.frame_shift
        )[0]

        # Find peaks (stressed syllables)
        peaks, _ = signal.find_peaks(energy, height=np.mean(energy) * 1.2)

        if len(peaks) > 3:
            # Inter-peak intervals
            intervals = np.diff(peaks) * self.frame_shift / self.config.sample_rate

            # Check for regularity
            interval_var = np.std(intervals) / (np.mean(intervals) + 1e-10)
            features["rhythm_disruption"] = min(1.0, float(interval_var))

        return features

    def _extract_articulation_features(
        self, audio_data: np.ndarray
    ) -> Dict[str, float]:
        """Extract articulation features affected by pain."""
        features = {
            "vowel_centralization": 0.0,
            "consonant_precision": 0.0,
            "coarticulation": 0.0,
        }

        # Simplified vowel space analysis
        # Extract formants using LPC
        # Note: Full implementation would segment vowels first

        # Use spectral centroid as proxy for vowel space
        centroid = librosa.feature.spectral_centroid(
            y=audio_data, sr=self.config.sample_rate, hop_length=self.frame_shift
        )[0]

        if len(centroid) > 0:
            # Reduced variation indicates centralization
            centroid_var = np.std(centroid) / (np.mean(centroid) + 1e-10)
            features["vowel_centralization"] = 1 / (1 + centroid_var * 2)

        # Consonant precision (using spectral flux at transitions)
        stft = librosa.stft(
            audio_data, n_fft=self.frame_length * 2, hop_length=self.frame_shift
        )
        magnitude = np.abs(stft)

        # Spectral flux
        spectral_flux = np.sqrt(np.sum(np.diff(magnitude, axis=1) ** 2, axis=0))

        if len(spectral_flux) > 0:
            # Sharp transitions indicate precise consonants
            flux_peaks, _ = signal.find_peaks(
                spectral_flux, height=np.mean(spectral_flux) * 2
            )

            if len(flux_peaks) > 0:
                # Sharpness of peaks
                peak_sharpness = []
                for peak in flux_peaks:
                    if 1 < peak < len(spectral_flux) - 1:
                        sharpness = spectral_flux[peak] / np.mean(
                            [spectral_flux[peak - 1], spectral_flux[peak + 1]]
                        )
                        peak_sharpness.append(sharpness)

                if peak_sharpness:
                    # Low sharpness indicates imprecise articulation
                    features["consonant_precision"] = 1 / (1 + np.mean(peak_sharpness))

        # Coarticulation index (transition smoothness)
        # Using MFCC delta features
        mfcc = librosa.feature.mfcc(
            y=audio_data,
            sr=self.config.sample_rate,
            n_mfcc=13,
            hop_length=self.frame_shift,
        )

        if mfcc.shape[1] > 2:
            # Calculate delta MFCCs
            mfcc_delta = librosa.feature.delta(mfcc)

            # Average change rate
            change_rate = np.mean(np.abs(mfcc_delta))
            # High change rate indicates less coarticulation (more effortful)
            features["coarticulation"] = 1 / (1 + change_rate)

        return features

    def _score_to_pain_level(self, score: float) -> PainLevel:
        """Convert pain score (0-10) to pain level."""
        thresholds = self.config.pain_thresholds

        if score >= thresholds["worst_possible"]:
            return PainLevel.WORST_POSSIBLE
        elif score >= thresholds["very_severe"]:
            return PainLevel.VERY_SEVERE
        elif score >= thresholds["severe"]:
            return PainLevel.SEVERE
        elif score >= thresholds["moderate"]:
            return PainLevel.MODERATE
        elif score >= thresholds["mild"]:
            return PainLevel.MILD
        else:
            return PainLevel.NO_PAIN

    def _adjust_for_baseline(
        self, features: PainFeatures, baseline: PainFeatures, raw_score: float
    ) -> float:
        """Adjust pain score based on baseline comparison."""
        # Calculate relative changes from baseline
        adjustments = []

        # F0 changes
        if baseline.f0_mean > 0:
            f0_change = abs(features.f0_mean - baseline.f0_mean) / baseline.f0_mean
            adjustments.append(f0_change * 0.2)

        # Tension increase
        tension_change = features.global_tension - baseline.global_tension
        if tension_change > 0:
            adjustments.append(tension_change * 0.3)

        # Voice quality degradation
        quality_change = features.strain_index - baseline.strain_index
        if quality_change > 0:
            adjustments.append(quality_change * 0.2)

        # Apply adjustments
        adjustment = sum(adjustments)
        return min(1.0, raw_score + adjustment)

    async def _identify_pain_types(self, features: PainFeatures) -> List[PainType]:
        """Identify types of pain from voice features."""
        pain_types = []

        for pain_type, pattern in self.pain_patterns.items():
            matches = 0
            total_checks = 0

            # Check feature thresholds
            features_dict = pattern.get("features", {})
            if isinstance(features_dict, dict):
                for feature_name, threshold in features_dict.items():
                    total_checks += 1

                    if hasattr(features, feature_name):
                        feature_value = getattr(features, feature_name)

                        if isinstance(threshold, tuple):  # Range
                            if threshold[0] <= feature_value <= threshold[1]:
                                matches += 1
                        elif isinstance(threshold, (int, float)):  # Minimum threshold
                            if feature_value >= threshold:
                                matches += 1

            # Check if enough features match
            if total_checks > 0 and matches / total_checks > 0.6:
                pain_types.append(pain_type)

        # Special case: chronic pain detection
        if len(self.pain_history) > 10:
            recent_scores = [h.pain_score for h in list(self.pain_history)[-10:]]
            if np.mean(recent_scores) > 4 and PainType.CHRONIC not in pain_types:
                pain_types.append(PainType.CHRONIC)

        return pain_types

    def _identify_pain_descriptors(
        self, features: PainFeatures
    ) -> List[PainDescriptor]:
        """Identify pain descriptors from voice characteristics."""
        descriptors = []

        # Sharp pain
        if features.f0_range > 100 and features.spectral_flux_instability > 0.7:
            descriptors.append(PainDescriptor.SHARP)

        # Burning pain
        if features.breathiness_index > 0.6 and features.global_tension > 0.7:
            descriptors.append(PainDescriptor.BURNING)

        # Throbbing pain
        if features.amplitude_modulation > 0.6 and features.rhythm_disruption < 0.3:
            descriptors.append(PainDescriptor.THROBBING)

        # Aching pain
        if features.vocal_fry_ratio > 0.3 and features.pitch_contour_flatness > 0.6:
            descriptors.append(PainDescriptor.ACHING)

        # Stabbing pain
        if features.grunt_detection > 0.1 and features.f0_tremor_amplitude > 10:
            descriptors.append(PainDescriptor.STABBING)

        return descriptors

    def _identify_active_indicators(
        self, features: PainFeatures
    ) -> List[PainIndicator]:
        """Identify which pain indicators are active."""
        indicators = []

        if features.vocal_fry_ratio > 0.2:
            indicators.append(PainIndicator.VOCAL_FRY)

        if features.strain_index > 0.6:
            indicators.append(PainIndicator.VOICE_STRAIN)

        if features.f0_range > 100:
            indicators.append(PainIndicator.PITCH_BREAKS)

        if features.breathiness_index > 0.5:
            indicators.append(PainIndicator.BREATHINESS)

        if features.global_tension > 0.6:
            indicators.append(PainIndicator.TENSION)

        if features.f0_tremor_amplitude > 5:
            indicators.append(PainIndicator.TREMOR)

        if features.grunt_detection > 0.05:
            indicators.append(PainIndicator.GRUNT_SOUNDS)

        if features.pause_frequency > 20:
            indicators.append(PainIndicator.SPEECH_PAUSES)

        if features.amplitude_modulation < 0.3:
            indicators.append(PainIndicator.VOLUME_REDUCTION)

        if features.vowel_centralization > 0.6:
            indicators.append(PainIndicator.ARTICULATION_CHANGES)

        return indicators

    async def _analyze_temporal_pain(self, audio_data: np.ndarray) -> Dict[str, Any]:
        """Analyze pain variations over time."""
        window_size = int(self.config.temporal_window_size * self.config.sample_rate)
        hop_size = window_size // 2

        timeline = []
        pain_scores = []

        # Analyze windows
        for i in range(0, len(audio_data) - window_size, hop_size):
            window = audio_data[i : i + window_size]
            timestamp = i / self.config.sample_rate

            # Quick feature extraction
            window_features = await self._extract_pain_features(window)
            window_score = window_features.calculate_pain_score() * 10

            timeline.append((timestamp, window_score))
            pain_scores.append(window_score)

        # Find peaks
        peaks = []
        if len(pain_scores) > 2:
            peak_indices, _ = signal.find_peaks(
                pain_scores,
                height=np.mean(pain_scores) + np.std(pain_scores),
                prominence=1.0,
            )

            for idx in peak_indices:
                peaks.append((timeline[idx][0], pain_scores[idx]))

        # Calculate variability
        variability = np.std(pain_scores) if pain_scores else 0.0

        return {"timeline": timeline, "variability": variability, "peaks": peaks}

    def _detect_breakthrough_pain(
        self, pain_timeline: List[Tuple[float, float]]
    ) -> List[float]:
        """Detect breakthrough pain events."""
        if len(pain_timeline) < 3:
            return []

        breakthrough_events = []
        scores = [score for _, score in pain_timeline]

        # Calculate baseline (median of lower 75% of scores)
        baseline = np.percentile(scores, 75)

        # Detect sudden increases
        for i in range(1, len(scores)):
            if scores[i] - scores[i - 1] > self.config.breakthrough_threshold:
                if scores[i] > baseline + self.config.breakthrough_threshold:
                    breakthrough_events.append(pain_timeline[i][0])

        return breakthrough_events

    def _assess_functional_impact(
        self, pain_level: PainLevel, features: PainFeatures
    ) -> str:
        """Assess how pain affects functional ability."""
        # Use features for detailed functional assessment
        impact_details = []

        # Analyze voice indicators for functional impact
        if features.speech_rate_variability > 0.8:  # Highly variable speech
            impact_details.append("severely disrupted speech rhythm")
        elif features.speech_rate_variability > 0.5:  # Moderately variable
            impact_details.append("noticeably disrupted speech rhythm")

        if features.pause_frequency > 40:  # Excessive pausing
            impact_details.append("frequent pausing indicating difficulty")
        elif features.pause_frequency > 25:
            impact_details.append("increased pause frequency")

        if features.strain_index > 0.8:  # High vocal strain
            impact_details.append("severe vocal strain")
        elif features.strain_index > 0.5:
            impact_details.append("moderate vocal strain")

        if features.breathiness_index > 0.6:  # Breathiness indicates exertion
            impact_details.append(
                "significant breathiness suggesting physical distress"
            )
        elif features.breathiness_index > 0.4:
            impact_details.append("noticeable breathiness")

        # Combine feature analysis with pain level assessment
        base_assessment = self._get_base_functional_assessment(pain_level)

        if impact_details:
            feature_assessment = (
                f" Voice analysis indicates: {', '.join(impact_details)}."
            )
            return base_assessment + feature_assessment
        else:
            return base_assessment

    def _get_base_functional_assessment(self, pain_level: PainLevel) -> str:
        """Get base functional assessment based on pain level."""
        if pain_level == PainLevel.WORST_POSSIBLE:
            return "Unable to perform any activities, requires immediate intervention."
        elif pain_level == PainLevel.VERY_SEVERE:
            return "Severely limited function, unable to concentrate or perform most tasks."
        elif pain_level == PainLevel.SEVERE:
            return "Significantly interferes with daily activities and concentration."
        elif pain_level == PainLevel.MODERATE:
            return "Interferes with some tasks, can manage with effort."
        elif pain_level == PainLevel.MILD:
            return "Noticeable but does not significantly interfere with activities."
        else:
            return "No functional limitations."

    def _calculate_pain_behavior_score(
        self, features: PainFeatures, indicators: List[PainIndicator]
    ) -> float:
        """Calculate observable pain behavior score."""
        behavior_score = 0.0

        # Vocal behaviors
        if PainIndicator.GRUNT_SOUNDS in indicators:
            behavior_score += 0.2
        if PainIndicator.VOCAL_FRY in indicators:
            behavior_score += 0.1

        # Speech changes
        if features.pause_frequency > 20:
            behavior_score += 0.15
        if features.speech_rate_variability > 0.5:
            behavior_score += 0.1

        # Voice quality changes
        if features.strain_index > 0.7:
            behavior_score += 0.15
        if features.breathiness_index > 0.6:
            behavior_score += 0.1

        # Non-verbal vocalizations
        behavior_score += features.vocalization_intensity * 0.2

        return min(1.0, behavior_score)

    def _assess_suffering_component(
        self, features: PainFeatures, pain_score: float
    ) -> float:
        """Assess emotional suffering component of pain."""
        suffering_score = 0.0

        # Voice quality indicators of distress
        if features.breathiness_index > 0.6:
            suffering_score += 0.2

        # Prosodic indicators
        if features.pitch_contour_flatness > 0.7:  # Emotional blunting
            suffering_score += 0.15

        # Tension indicators
        suffering_score += features.global_tension * 0.3

        # Tremor (emotional component)
        if features.f0_tremor_amplitude > 5:
            suffering_score += 0.2

        # Scale by pain intensity
        suffering_score *= pain_score / 10

        return min(1.0, suffering_score)

    def _estimate_pain_locations(
        self, features: PainFeatures, pain_types: List[PainType]
    ) -> List[str]:
        """Estimate possible pain locations from voice characteristics."""
        locations = []

        # Chest/cardiac pain often causes breathiness
        if features.breathiness_index > 0.7 and features.pause_frequency > 25:
            locations.append("chest/cardiac region")

        # Abdominal pain often causes grunting
        if features.grunt_detection > 0.1 and PainType.VISCERAL in pain_types:
            locations.append("abdominal region")

        # Head/neck pain affects voice tension
        if features.laryngeal_tension > 0.8 and features.pharyngeal_tension > 0.7:
            locations.append("head/neck region")

        # Back pain affects posture and breathing
        if features.roughness_index > 0.5 and features.amplitude_modulation < 0.3:
            locations.append("back/spine region")

        # Neuropathic pain patterns
        if PainType.NEUROPATHIC in pain_types and features.f0_tremor_amplitude > 8:
            locations.append("peripheral nerves")

        return locations[:3]  # Limit to top 3 locations

    def _generate_assessment_notes(
        self,
        pain_level: PainLevel,
        pain_types: List[PainType],
        features: PainFeatures,
        indicators: List[PainIndicator],
    ) -> List[str]:
        """Generate clinical assessment notes."""
        # Use indicators for detailed clinical notes
        notes = []

        # Pain level note
        notes.append(
            f"Voice analysis indicates {pain_level.value.replace('_', ' ')} pain"
        )

        # Indicator-specific observations
        indicator_messages = {
            PainIndicator.VOCAL_FRY: "Vocal fry pattern detected, suggesting chronic pain or fatigue",
            PainIndicator.VOICE_STRAIN: "Voice strain present, indicating physical discomfort",
            PainIndicator.PITCH_BREAKS: "Pitch instability observed, consistent with pain response",
            PainIndicator.BREATHINESS: "Increased breathiness detected, suggesting respiratory compensation",
            PainIndicator.TENSION: "Muscular tension evident in voice production",
            PainIndicator.TREMOR: "Voice tremor present, indicating pain-related instability",
            PainIndicator.GRUNT_SOUNDS: "Pain vocalizations detected during speech",
            PainIndicator.SPEECH_PAUSES: "Frequent speech pauses suggesting difficulty with continuous speech",
            PainIndicator.VOLUME_REDUCTION: "Reduced voice volume indicating energy conservation",
            PainIndicator.ARTICULATION_CHANGES: "Articulation changes detected, suggesting pain interference",
        }

        for indicator in indicators:
            if indicator in indicator_messages:
                notes.append(indicator_messages[indicator])

        # Voice quality observations
        if features.vocal_fry_ratio > 0.3:
            notes.append(
                "Significant vocal fry detected, suggesting chronic pain or fatigue"
            )

        if features.strain_index > 0.7:
            notes.append("High vocal strain indicating significant discomfort")

        # Breathing observations
        if features.pause_frequency > 30:
            notes.append("Frequent pausing suggests pain interferes with breathing")

        # Pain behavior observations
        if features.grunt_detection > 0.1:
            notes.append("Pain vocalizations detected")

        # Tremor observations
        if features.f0_tremor_amplitude > 10:
            notes.append("Significant voice tremor indicating severe pain or distress")

        # Chronic pain indicators
        if PainType.CHRONIC in pain_types:
            notes.append("Voice patterns consistent with chronic pain")

        return notes

    def _generate_intervention_suggestions(
        self,
        pain_level: PainLevel,
        pain_types: List[PainType],
        breakthrough_events: List[float],
    ) -> List[str]:
        """Generate intervention suggestions based on pain assessment."""
        suggestions = []

        # Immediate interventions for severe pain
        if pain_level in [PainLevel.VERY_SEVERE, PainLevel.WORST_POSSIBLE]:
            suggestions.append("Immediate pain intervention required")
            suggestions.append("Consider rescue medication")
            suggestions.append("Assess for emergency medical needs")

        # Breakthrough pain management
        if len(breakthrough_events) > 0:
            suggestions.append(
                f"Breakthrough pain detected ({len(breakthrough_events)} events)"
            )
            suggestions.append("Review current pain management plan")
            suggestions.append("Consider adjusting baseline pain medication")

        # Type-specific interventions
        if PainType.NEUROPATHIC in pain_types:
            suggestions.append("Consider neuropathic pain medications")

        if PainType.CHRONIC in pain_types:
            suggestions.append("Comprehensive pain management approach recommended")
            suggestions.append("Consider psychological support for chronic pain")

        # Moderate pain suggestions
        if pain_level == PainLevel.MODERATE:
            suggestions.append("Monitor pain progression")
            suggestions.append("Consider non-pharmacological interventions")

        return suggestions

    def _calculate_confidence(
        self, features: PainFeatures, num_indicators: int
    ) -> float:
        """Calculate confidence in pain assessment."""
        confidence_factors = []

        # Feature quality
        if features.f0_mean > 0:
            confidence_factors.append(0.9)
        else:
            confidence_factors.append(0.3)

        # Number of indicators
        indicator_confidence = min(1.0, num_indicators / 5)
        confidence_factors.append(indicator_confidence)

        # Feature consistency
        # Check if features align
        consistency = 1.0
        if features.vocal_fry_ratio > 0.5 and features.f0_mean > 300:
            consistency *= 0.7  # Inconsistent

        confidence_factors.append(consistency)

        return float(np.mean(confidence_factors))

    def _assess_reliability(self, features: PainFeatures, variability: float) -> float:
        """Assess reliability of pain assessment."""
        reliability_factors = []

        # Temporal consistency
        if variability < 3.0:  # Consistent pain levels
            reliability_factors.append(0.9)
        else:
            reliability_factors.append(0.6)

        # Feature reliability
        if features.pause_frequency < 100:  # Reasonable pause frequency
            reliability_factors.append(0.9)
        else:
            reliability_factors.append(0.5)

        # Voice quality
        if features.strain_index < 0.95:  # Not completely strained
            reliability_factors.append(0.9)
        else:
            reliability_factors.append(0.6)

        return float(np.mean(reliability_factors))

    def _generate_warnings(
        self, features: PainFeatures, pain_score: float
    ) -> List[str]:
        """Generate warnings about assessment limitations."""
        warnings = []

        if pain_score > 9.5:
            warnings.append(
                "Extreme pain levels detected - verify with clinical assessment"
            )

        if features.vocal_fry_ratio > 0.8:
            warnings.append("Very high vocal fry may affect feature accuracy")

        if features.pause_frequency > 50:
            warnings.append("Excessive pausing may indicate other conditions")

        if features.grunt_detection > 0.3:
            warnings.append("High level of non-speech vocalizations")

        return warnings

    @requires_phi_access("read")
    async def process_audio_file(
        self,
        file_path: str,
        baseline_file: Optional[str] = None,
        save_results: bool = True,
        _user_id: str = "system",
    ) -> PainAssessmentResult:
        """Process an audio file for pain assessment."""
        try:
            # Load audio file
            audio_data, _ = librosa.load(file_path, sr=self.config.sample_rate)

            # Load baseline if provided
            baseline = None
            if baseline_file:
                baseline_audio, _ = librosa.load(
                    baseline_file, sr=self.config.sample_rate
                )
                baseline = await self._extract_pain_features(baseline_audio)

            # Assess pain
            result: PainAssessmentResult = await self.assess_pain(audio_data, baseline)

            # Save results if requested
            if save_results:
                output_path = file_path.replace(".wav", "_pain_assessment.json")
                with open(output_path, "w", encoding="utf-8") as f:
                    json.dump(result.to_dict(), f, indent=2)
                logger.info("Pain assessment saved to %s", output_path)

            return result

        except Exception as e:
            logger.error("Error processing audio file: %s", str(e), exc_info=True)
            raise

    def get_pain_statistics(
        self, results: List[PainAssessmentResult]
    ) -> Dict[str, Any]:
        """Calculate statistics from multiple pain assessments."""
        if not results:
            return {}

        pain_scores = [r.pain_score for r in results]
        pain_levels = [r.pain_level.value for r in results]

        # Pain type frequency
        all_pain_types = []
        for r in results:
            all_pain_types.extend(r.pain_types)

        pain_type_counts: Dict[str, int] = {}
        for pt in all_pain_types:
            pain_type_counts[pt.value] = pain_type_counts.get(pt.value, 0) + 1

        # Breakthrough pain statistics
        total_breakthrough = sum(len(r.breakthrough_events) for r in results)

        stats = {
            "mean_pain_score": np.mean(pain_scores),
            "max_pain_score": np.max(pain_scores),
            "min_pain_score": np.min(pain_scores),
            "pain_level_distribution": {
                level: pain_levels.count(level) for level in set(pain_levels)
            },
            "pain_type_frequency": pain_type_counts,
            "total_breakthrough_events": total_breakthrough,
            "mean_variability": np.mean([r.pain_variability for r in results]),
            "samples_analyzed": len(results),
            "mean_confidence": np.mean([r.confidence_score for r in results]),
        }

        return stats
