"""
Urgency Detection Module for Medical Voice Analysis.

This module implements urgency level detection from voice recordings
to assist in medical triage and emergency response prioritization.
"""

# pylint: disable=too-many-lines

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, cast

import numpy as np
from scipy import signal
from scipy.ndimage import gaussian_filter1d
from scipy.signal import butter, filtfilt

try:
    import librosa
except ImportError:
    librosa = None

logger = logging.getLogger(__name__)


class UrgencyLevel(Enum):
    """Urgency levels for medical triage."""

    ROUTINE = "routine"  # Non-urgent, scheduled care
    LOW = "low"  # Can wait several hours
    MODERATE = "moderate"  # Should be seen within 1-2 hours
    HIGH = "high"  # Urgent, within 30 minutes
    CRITICAL = "critical"  # Immediate attention required
    EMERGENCY = "emergency"  # Life-threatening, immediate


class UrgencyIndicator(Enum):
    """Voice indicators of urgency."""

    SPEECH_PRESSURE = "speech_pressure"  # Rushed, pressured speech
    VOCAL_STRAIN = "vocal_strain"  # Strained voice quality
    BREATH_DISTRESS = "breath_distress"  # Breathing difficulties
    VOICE_WEAKNESS = "voice_weakness"  # Weak or fading voice
    PANIC_MARKERS = "panic_markers"  # Panic/extreme anxiety
    PAIN_URGENCY = "pain_urgency"  # Acute pain indicators
    CONFUSION_URGENCY = "confusion_urgency"  # Urgent confusion/disorientation
    VOCAL_TREMOR = "vocal_tremor"  # Severe tremor
    SPEECH_FRAGMENTATION = "speech_fragmentation"  # Broken speech patterns


class UrgencyContext(Enum):
    """Context for urgency assessment."""

    TRAUMA = "trauma"
    CARDIAC = "cardiac"
    RESPIRATORY = "respiratory"
    NEUROLOGICAL = "neurological"
    PAIN = "pain"
    PSYCHIATRIC = "psychiatric"
    PEDIATRIC = "pediatric"
    GENERAL = "general"


@dataclass
class UrgencyFeatures:
    """Acoustic features for urgency detection."""

    # Speech tempo and pressure
    speaking_rate: float = 0.0
    speaking_rate_acceleration: float = 0.0
    syllable_rate: float = 0.0
    articulation_rate: float = 0.0

    # Voice strain indicators
    vocal_effort: float = 0.0
    glottal_pressure: float = 0.0
    voice_breaks_frequency: float = 0.0
    hoarseness_index: float = 0.0

    # Breathing patterns
    breath_rate: float = 0.0
    breath_effort: float = 0.0
    inspiratory_time: float = 0.0
    expiratory_time: float = 0.0
    breath_pause_ratio: float = 0.0

    # Voice stability
    pitch_stability: float = 0.0
    amplitude_stability: float = 0.0
    voice_onset_time: float = 0.0
    voice_offset_time: float = 0.0

    # Urgency-specific markers
    f0_maximum: float = 0.0
    f0_excursion: float = 0.0
    spectral_urgency: float = 0.0
    temporal_urgency: float = 0.0

    # Distress indicators
    harmonic_distortion: float = 0.0
    subharmonics_presence: float = 0.0
    voice_irregularity: float = 0.0

    # Energy distribution
    high_frequency_emphasis: float = 0.0
    spectral_slope_steepness: float = 0.0
    energy_concentration: float = 0.0

    def to_dict(self) -> Dict[str, float]:
        """Convert to dictionary representation."""
        return {
            "speaking_rate": self.speaking_rate,
            "speaking_rate_acceleration": self.speaking_rate_acceleration,
            "vocal_effort": self.vocal_effort,
            "breath_rate": self.breath_rate,
            "breath_effort": self.breath_effort,
            "pitch_stability": self.pitch_stability,
            "f0_maximum": self.f0_maximum,
            "spectral_urgency": self.spectral_urgency,
            "temporal_urgency": self.temporal_urgency,
            "voice_irregularity": self.voice_irregularity,
            "high_frequency_emphasis": self.high_frequency_emphasis,
        }

    def calculate_urgency_score(self) -> float:
        """Calculate composite urgency score."""
        # Weight different aspects of urgency
        weights = {
            "temporal": 0.3,  # Speaking rate, acceleration
            "vocal": 0.25,  # Vocal effort, strain
            "respiratory": 0.25,  # Breathing patterns
            "stability": 0.2,  # Voice stability
        }

        # Temporal urgency (normalized)
        temporal_score = min(
            1.0,
            (
                (self.speaking_rate / 300) * 0.4  # Fast speech
                + abs(self.speaking_rate_acceleration) * 0.3
                + self.temporal_urgency * 0.3
            ),
        )

        # Vocal urgency
        vocal_score = min(
            1.0,
            (
                self.vocal_effort * 0.4
                + self.voice_breaks_frequency * 10  # Scaled
                + self.hoarseness_index * 0.3
            ),
        )

        # Respiratory urgency
        respiratory_score = min(
            1.0,
            (
                max(0, (self.breath_rate - 20) / 20) * 0.5  # Elevated breathing
                + self.breath_effort * 0.3
                + (1 - self.breath_pause_ratio) * 0.2  # Less pause = more urgent
            ),
        )

        # Stability (inverted - less stable = more urgent)
        stability_score = min(
            1.0,
            (
                (1 - self.pitch_stability) * 0.5
                + (1 - self.amplitude_stability) * 0.3
                + self.voice_irregularity * 0.2
            ),
        )

        # Weighted combination
        total_score = (
            weights["temporal"] * temporal_score
            + weights["vocal"] * vocal_score
            + weights["respiratory"] * respiratory_score
            + weights["stability"] * stability_score
        )

        return total_score


@dataclass
class UrgencyDetectionResult:
    """Result of urgency detection analysis."""

    urgency_level: UrgencyLevel
    urgency_score: float  # 0-1 normalized score

    # Detailed indicators
    active_indicators: List[UrgencyIndicator] = field(default_factory=list)
    features: Optional[UrgencyFeatures] = None

    # Context and classification
    likely_context: Optional[UrgencyContext] = None
    secondary_contexts: List[UrgencyContext] = field(default_factory=list)

    # Temporal analysis
    urgency_progression: List[Tuple[float, float]] = field(
        default_factory=list
    )  # (time, score)
    peak_urgency_time: Optional[float] = None
    urgency_trend: str = "stable"  # "increasing", "decreasing", "stable"

    # Clinical recommendations
    triage_category: str = ""
    recommended_response_time: str = ""
    priority_symptoms: List[str] = field(default_factory=list)

    # Confidence and quality
    confidence_score: float = 0.0
    audio_quality_score: float = 0.0
    analysis_warnings: List[str] = field(default_factory=list)

    # Processing metadata
    audio_duration: float = 0.0
    processing_time_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "urgency_level": self.urgency_level.value,
            "urgency_score": self.urgency_score,
            "active_indicators": [i.value for i in self.active_indicators],
            "features": self.features.to_dict() if self.features else None,
            "likely_context": (
                self.likely_context.value if self.likely_context else None
            ),
            "secondary_contexts": [c.value for c in self.secondary_contexts],
            "urgency_progression": self.urgency_progression,
            "peak_urgency_time": self.peak_urgency_time,
            "urgency_trend": self.urgency_trend,
            "triage_category": self.triage_category,
            "recommended_response_time": self.recommended_response_time,
            "priority_symptoms": self.priority_symptoms,
            "confidence_score": self.confidence_score,
            "audio_quality_score": self.audio_quality_score,
            "analysis_warnings": self.analysis_warnings,
            "audio_duration": self.audio_duration,
            "processing_time_ms": self.processing_time_ms,
        }

    def get_triage_summary(self) -> str:
        """Get human-readable triage summary."""
        summary = (
            f"URGENCY: {self.urgency_level.value.upper()} ({self.urgency_score:.1%})\n"
        )
        summary += f"TRIAGE: {self.triage_category}\n"
        summary += f"RESPONSE TIME: {self.recommended_response_time}\n"

        if self.priority_symptoms:
            summary += f"PRIORITY SYMPTOMS: {', '.join(self.priority_symptoms)}\n"

        if self.urgency_trend != "stable":
            summary += f"TREND: Urgency {self.urgency_trend}\n"

        return summary


@dataclass
class UrgencyDetectionConfig:
    """Configuration for urgency detection."""

    # Audio parameters
    sample_rate: int = 16000
    frame_length_ms: int = 25
    frame_shift_ms: int = 10

    # Analysis settings
    enable_temporal_analysis: bool = True
    temporal_window_size: float = 1.5  # seconds
    enable_breathing_analysis: bool = True
    enable_context_detection: bool = True

    # Urgency thresholds
    urgency_thresholds: Dict[str, float] = field(
        default_factory=lambda: {
            "routine": 0.2,
            "low": 0.35,
            "moderate": 0.5,
            "high": 0.7,
            "critical": 0.85,
            "emergency": 0.95,
        }
    )

    # Response time mapping (in minutes)
    response_times: Dict[str, str] = field(
        default_factory=lambda: {
            "routine": "Within 24 hours",
            "low": "Within 4 hours",
            "moderate": "Within 1-2 hours",
            "high": "Within 30 minutes",
            "critical": "Within 10 minutes",
            "emergency": "Immediate (< 5 minutes)",
        }
    )

    # Feature sensitivity
    breathing_sensitivity: float = 0.8
    pain_sensitivity: float = 0.9
    panic_sensitivity: float = 0.85

    # Quality thresholds
    min_audio_quality: float = 0.3
    min_confidence_threshold: float = 0.5


class UrgencyDetector:
    """
    Detects urgency levels from voice recordings for medical triage.

    Uses acoustic analysis to identify urgent medical situations and
    provide appropriate triage recommendations.
    """

    def __init__(self, config: Optional[UrgencyDetectionConfig] = None):
        """
        Initialize the urgency detector.

        Args:
            config: Detection configuration
        """
        self.config = config or UrgencyDetectionConfig()

        # Frame parameters
        self.frame_length = int(
            self.config.sample_rate * self.config.frame_length_ms / 1000
        )
        self.frame_shift = int(
            self.config.sample_rate * self.config.frame_shift_ms / 1000
        )

        # Initialize urgency patterns
        self._init_urgency_patterns()

        # Initialize context patterns
        self._init_context_patterns()

        logger.info(
            "UrgencyDetector initialized with sample_rate=%dHz", self.config.sample_rate
        )

    def _init_urgency_patterns(self) -> None:
        """Initialize urgency detection patterns."""
        self.urgency_patterns: Dict[UrgencyIndicator, Dict[str, Any]] = {
            UrgencyIndicator.SPEECH_PRESSURE: {
                "features": [
                    "speaking_rate",
                    "syllable_rate",
                    "speaking_rate_acceleration",
                ],
                "thresholds": {
                    "speaking_rate": 250,  # words per minute
                    "acceleration": 5.0,
                    "syllable_rate": 6.0,
                },
            },
            UrgencyIndicator.VOCAL_STRAIN: {
                "features": ["vocal_effort", "glottal_pressure", "hoarseness_index"],
                "thresholds": {"effort": 0.7, "pressure": 0.6, "hoarseness": 0.5},
            },
            UrgencyIndicator.BREATH_DISTRESS: {
                "features": ["breath_rate", "breath_effort", "breath_pause_ratio"],
                "thresholds": {
                    "rate": 25,  # breaths per minute
                    "effort": 0.7,
                    "pause_ratio": 0.2,
                },
            },
            UrgencyIndicator.PANIC_MARKERS: {
                "features": ["f0_maximum", "spectral_urgency", "voice_irregularity"],
                "thresholds": {
                    "f0_max": 400,  # Hz
                    "spectral": 0.8,
                    "irregularity": 0.6,
                },
            },
        }

    def _init_context_patterns(self) -> None:
        """Initialize medical context patterns."""
        self.context_patterns: Dict[UrgencyContext, Dict[str, Any]] = {
            UrgencyContext.CARDIAC: {
                "indicators": [
                    UrgencyIndicator.BREATH_DISTRESS,
                    UrgencyIndicator.VOICE_WEAKNESS,
                ],
                "features": {
                    "breath_rate": (20, 40),
                    "voice_weakness": 0.6,
                    "speech_fragmentation": 0.5,
                },
            },
            UrgencyContext.RESPIRATORY: {
                "indicators": [
                    UrgencyIndicator.BREATH_DISTRESS,
                    UrgencyIndicator.VOCAL_STRAIN,
                ],
                "features": {
                    "breath_effort": 0.7,
                    "inspiratory_time": 0.4,
                    "speaking_rate": (100, 200),
                },
            },
            UrgencyContext.NEUROLOGICAL: {
                "indicators": [
                    UrgencyIndicator.CONFUSION_URGENCY,
                    UrgencyIndicator.SPEECH_FRAGMENTATION,
                ],
                "features": {
                    "voice_irregularity": 0.6,
                    "speech_fragmentation": 0.7,
                    "articulation_rate": (1, 3),
                },
            },
            UrgencyContext.PAIN: {
                "indicators": [
                    UrgencyIndicator.PAIN_URGENCY,
                    UrgencyIndicator.VOCAL_STRAIN,
                ],
                "features": {
                    "vocal_effort": 0.8,
                    "f0_excursion": 150,
                    "voice_breaks_frequency": 0.1,
                },
            },
        }

    async def detect_urgency(
        self, audio_data: np.ndarray, context_hint: Optional[str] = None
    ) -> UrgencyDetectionResult:
        """
        Detect urgency level from audio data.

        Args:
            audio_data: Audio signal as numpy array
            context_hint: Optional hint about medical context

        Returns:
            UrgencyDetectionResult with comprehensive urgency analysis
        """
        start_time = datetime.now()

        try:
            # Normalize audio
            audio_data = self._normalize_audio(audio_data)

            # Check audio quality
            audio_quality = self._assess_audio_quality(audio_data)

            # Extract urgency features
            features = await self._extract_urgency_features(audio_data)

            # Calculate urgency score
            urgency_score = features.calculate_urgency_score()

            # Determine urgency level
            urgency_level = self._score_to_urgency_level(urgency_score)

            # Identify active indicators
            active_indicators = self._identify_active_indicators(features)

            # Detect medical context
            likely_context = None
            secondary_contexts: List[UrgencyContext] = []
            if self.config.enable_context_detection:
                likely_context, secondary_contexts = await self._detect_medical_context(
                    features, active_indicators, context_hint
                )

            # Temporal analysis
            urgency_progression = []
            peak_urgency_time = None
            urgency_trend = "stable"

            if self.config.enable_temporal_analysis:
                temporal_result = await self._analyze_temporal_urgency(audio_data)
                urgency_progression = temporal_result["progression"]
                peak_urgency_time = temporal_result["peak_time"]
                urgency_trend = temporal_result["trend"]

            # Generate triage information
            triage_category = self._determine_triage_category(
                urgency_level, likely_context, active_indicators
            )

            # Get response time recommendation
            recommended_response_time = self.config.response_times.get(
                urgency_level.value, "Immediate assessment needed"
            )

            # Identify priority symptoms
            priority_symptoms = self._identify_priority_symptoms(
                features, active_indicators, likely_context
            )

            # Calculate confidence
            confidence = self._calculate_confidence(
                features, audio_quality, len(active_indicators)
            )

            # Generate warnings
            warnings = self._generate_warnings(audio_quality, confidence, features)

            # Processing time
            processing_time = (datetime.now() - start_time).total_seconds() * 1000

            return UrgencyDetectionResult(
                urgency_level=urgency_level,
                urgency_score=urgency_score,
                active_indicators=active_indicators,
                features=features,
                likely_context=likely_context,
                secondary_contexts=secondary_contexts,
                urgency_progression=urgency_progression,
                peak_urgency_time=peak_urgency_time,
                urgency_trend=urgency_trend,
                triage_category=triage_category,
                recommended_response_time=recommended_response_time,
                priority_symptoms=priority_symptoms,
                confidence_score=confidence,
                audio_quality_score=audio_quality,
                analysis_warnings=warnings,
                audio_duration=len(audio_data) / self.config.sample_rate,
                processing_time_ms=processing_time,
            )

        except Exception as e:
            logger.error("Error in urgency detection: %s", str(e), exc_info=True)
            raise

    def _normalize_audio(self, audio_data: np.ndarray) -> np.ndarray:
        """Normalize audio to [-1, 1] range."""
        max_val = np.max(np.abs(audio_data))
        if max_val > 0:
            return cast(np.ndarray, audio_data / max_val)
        return audio_data

    def _assess_audio_quality(self, audio_data: np.ndarray) -> float:
        """Assess audio quality for reliability of analysis."""
        # Check for clipping
        clipping_ratio = np.sum(np.abs(audio_data) > 0.95) / len(audio_data)

        # Check signal-to-noise ratio (simplified)
        signal_power = np.mean(audio_data**2)
        noise_floor = np.percentile(np.abs(audio_data), 10) ** 2

        if noise_floor > 0:
            snr = 10 * np.log10(signal_power / noise_floor)
        else:
            snr = 40  # Good SNR

        # Check for sufficient voice activity
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

    async def _extract_urgency_features(
        self, audio_data: np.ndarray
    ) -> UrgencyFeatures:
        """Extract comprehensive urgency-related features."""
        features = UrgencyFeatures()

        # Extract speaking rate features
        rate_features = self._extract_rate_features(audio_data)
        features.speaking_rate = rate_features["speaking_rate"]
        features.speaking_rate_acceleration = rate_features["acceleration"]
        features.syllable_rate = rate_features["syllable_rate"]
        features.articulation_rate = rate_features["articulation_rate"]

        # Extract vocal effort features
        effort_features = self._extract_vocal_effort(audio_data)
        features.vocal_effort = effort_features["effort"]
        features.glottal_pressure = effort_features["glottal_pressure"]
        features.voice_breaks_frequency = effort_features["breaks_frequency"]
        features.hoarseness_index = effort_features["hoarseness"]

        # Extract breathing features
        if self.config.enable_breathing_analysis:
            breathing_features = await self._analyze_breathing_urgency(audio_data)
            features.breath_rate = breathing_features["rate"]
            features.breath_effort = breathing_features["effort"]
            features.inspiratory_time = breathing_features["inspiratory_time"]
            features.expiratory_time = breathing_features["expiratory_time"]
            features.breath_pause_ratio = breathing_features["pause_ratio"]

        # Extract voice stability features
        stability_features = self._extract_voice_stability(audio_data)
        features.pitch_stability = stability_features["pitch_stability"]
        features.amplitude_stability = stability_features["amplitude_stability"]
        features.voice_onset_time = stability_features["onset_time"]
        features.voice_offset_time = stability_features["offset_time"]

        # Extract pitch urgency markers
        pitch_features = self._extract_pitch_urgency(audio_data)
        features.f0_maximum = pitch_features["f0_max"]
        features.f0_excursion = pitch_features["f0_excursion"]

        # Extract spectral urgency features
        spectral_features = self._extract_spectral_urgency(audio_data)
        features.spectral_urgency = spectral_features["urgency_score"]
        features.high_frequency_emphasis = spectral_features["high_freq_emphasis"]
        features.spectral_slope_steepness = spectral_features["slope_steepness"]
        features.energy_concentration = spectral_features["energy_concentration"]

        # Extract temporal urgency
        features.temporal_urgency = self._calculate_temporal_urgency(audio_data)

        # Extract voice irregularity
        features.voice_irregularity = self._calculate_voice_irregularity(audio_data)

        # Extract harmonic distortion
        distortion_features = self._extract_harmonic_distortion(audio_data)
        features.harmonic_distortion = distortion_features["distortion"]
        features.subharmonics_presence = distortion_features["subharmonics"]

        return features

    def _extract_rate_features(self, audio_data: np.ndarray) -> Dict[str, float]:
        """Extract speaking rate and related features."""
        # Energy-based syllable detection
        energy = librosa.feature.rms(
            y=audio_data, frame_length=self.frame_length, hop_length=self.frame_shift
        )[0]

        # Smooth energy
        smoothed_energy = gaussian_filter1d(energy, sigma=2)

        # Find peaks (syllables)
        peaks, _ = signal.find_peaks(
            smoothed_energy, height=np.mean(smoothed_energy), distance=5
        )  # Minimum distance between syllables

        duration = len(audio_data) / self.config.sample_rate
        syllable_count = len(peaks)

        # Calculate rates
        syllable_rate = syllable_count / duration if duration > 0 else 0
        speaking_rate = syllable_rate * 60  # Convert to per minute

        # Calculate acceleration (rate of change)
        if len(peaks) > 2:
            # Inter-syllable intervals
            intervals = np.diff(peaks) / (self.config.sample_rate / self.frame_shift)
            # Rate of change of intervals
            interval_changes = np.diff(intervals)
            acceleration = (
                np.mean(np.abs(interval_changes)) if len(interval_changes) > 0 else 0
            )
        else:
            acceleration = 0

        # Articulation rate (excluding pauses)
        speech_frames = smoothed_energy > np.mean(smoothed_energy) * 0.1
        speech_duration = (
            np.sum(speech_frames) * self.frame_shift / self.config.sample_rate
        )
        articulation_rate = (
            syllable_count / speech_duration if speech_duration > 0 else syllable_rate
        )

        return {
            "speaking_rate": speaking_rate,
            "acceleration": acceleration,
            "syllable_rate": syllable_rate,
            "articulation_rate": articulation_rate,
        }

    def _extract_vocal_effort(self, audio_data: np.ndarray) -> Dict[str, float]:
        """Extract vocal effort and strain indicators."""
        # Spectral features for effort estimation
        stft = librosa.stft(
            audio_data, n_fft=self.frame_length * 2, hop_length=self.frame_shift
        )
        magnitude = np.abs(stft)
        freqs = librosa.fft_frequencies(
            sr=self.config.sample_rate, n_fft=self.frame_length * 2
        )

        # High-frequency energy ratio (effort indicator)
        high_freq_idx = freqs > 2000
        low_freq_idx = (freqs > 100) & (freqs < 1000)

        high_energy = np.mean(magnitude[high_freq_idx, :])
        low_energy = np.mean(magnitude[low_freq_idx, :])

        effort_ratio = high_energy / (low_energy + 1e-10)
        effort_score = min(1.0, effort_ratio / 2)  # Normalize

        # Glottal pressure estimation (spectral tilt)
        spectral_tilt = []
        for frame_idx in range(magnitude.shape[1]):
            frame_mag = magnitude[:, frame_idx]
            if np.sum(frame_mag) > 0:
                # Linear regression of log magnitude vs log frequency
                valid_idx = (freqs > 100) & (frame_mag > 0)
                if np.sum(valid_idx) > 10:
                    log_freq = np.log(freqs[valid_idx])
                    log_mag = np.log(frame_mag[valid_idx] + 1e-10)
                    slope, _ = np.polyfit(log_freq, log_mag, 1)
                    spectral_tilt.append(abs(slope))

        glottal_pressure = np.mean(spectral_tilt) / 10 if spectral_tilt else 0.5

        # Voice breaks detection
        f0 = librosa.yin(
            audio_data,
            fmin=50,
            fmax=500,
            sr=self.config.sample_rate,
            frame_length=self.frame_length * 4,
        )

        # Count voice breaks (sudden F0 drops)
        voice_breaks = 0
        for i in range(1, len(f0)):
            if f0[i - 1] > 0 and f0[i] == 0:  # Voice to unvoiced transition
                voice_breaks += 1

        duration = len(audio_data) / self.config.sample_rate
        breaks_frequency = voice_breaks / duration if duration > 0 else 0

        # Hoarseness index (spectral irregularity)
        spectral_centroid = librosa.feature.spectral_centroid(
            y=audio_data, sr=self.config.sample_rate, hop_length=self.frame_shift
        )[0]
        hoarseness = np.std(spectral_centroid) / (np.mean(spectral_centroid) + 1e-10)

        return {
            "effort": effort_score,
            "glottal_pressure": min(1.0, glottal_pressure),
            "breaks_frequency": min(1.0, breaks_frequency),
            "hoarseness": min(1.0, hoarseness),
        }

    async def _analyze_breathing_urgency(
        self, audio_data: np.ndarray
    ) -> Dict[str, float]:
        """Analyze breathing patterns for urgency indicators."""
        # Extract envelope for breathing detection
        envelope = np.abs(signal.hilbert(audio_data))

        # Smooth envelope
        smooth_envelope = gaussian_filter1d(
            envelope, sigma=int(0.05 * self.config.sample_rate)
        )

        # Downsample for breathing rate analysis
        downsample_factor = 100
        downsampled = smooth_envelope[::downsample_factor]
        downsample_rate = self.config.sample_rate / downsample_factor

        # Find breathing cycles
        # Bandpass filter for breathing frequencies (0.2-0.8 Hz)
        nyquist = downsample_rate / 2
        low_freq = 0.2 / nyquist
        high_freq = min(0.8 / nyquist, 0.99)

        if low_freq < high_freq:
            b, a = butter(2, [low_freq, high_freq], btype="band")
            breathing_signal = filtfilt(b, a, downsampled)
        else:
            breathing_signal = downsampled

        # Find peaks (inhalations)
        peaks, _ = signal.find_peaks(
            breathing_signal,
            distance=int(1.5 * downsample_rate),  # Min 1.5s between breaths
            prominence=np.std(breathing_signal) * 0.3,
        )

        # Calculate breathing rate
        if len(peaks) > 1:
            intervals = np.diff(peaks) / downsample_rate
            breath_rate = float(60 / np.mean(intervals))  # Breaths per minute
        else:
            breath_rate = 15.0  # Default normal rate

        # Calculate breathing effort (amplitude variation)
        if len(peaks) > 0:
            peak_amplitudes = breathing_signal[peaks]
            effort = np.std(peak_amplitudes) / (np.mean(peak_amplitudes) + 1e-10)
        else:
            effort = 0.5

        # Estimate inspiratory/expiratory times
        inspiratory_time = 0.4  # Default
        expiratory_time = 0.6  # Default

        if len(peaks) > 1:
            # Find valleys between peaks
            for i in range(len(peaks) - 1):
                valley_region = breathing_signal[peaks[i] : peaks[i + 1]]
                if len(valley_region) > 0:
                    valley_idx = np.argmin(valley_region) + peaks[i]
                    insp_time = (valley_idx - peaks[i]) / downsample_rate
                    exp_time = (peaks[i + 1] - valley_idx) / downsample_rate
                    total_time = insp_time + exp_time
                    if total_time > 0:
                        inspiratory_time = insp_time / total_time
                        expiratory_time = exp_time / total_time

        # Calculate pause ratio
        energy_threshold = np.percentile(envelope, 20)
        breathing_active = envelope > energy_threshold
        pause_ratio = 1 - (np.sum(breathing_active) / len(breathing_active))

        return {
            "rate": breath_rate,
            "effort": min(1.0, effort),
            "inspiratory_time": inspiratory_time,
            "expiratory_time": expiratory_time,
            "pause_ratio": pause_ratio,
        }

    def _extract_voice_stability(self, audio_data: np.ndarray) -> Dict[str, float]:
        """Extract voice stability features."""
        # Pitch stability
        f0 = librosa.yin(
            audio_data,
            fmin=50,
            fmax=500,
            sr=self.config.sample_rate,
            frame_length=self.frame_length * 4,
        )

        # Remove unvoiced segments
        voiced_f0 = f0[f0 > 0]

        if len(voiced_f0) > 1:
            # Coefficient of variation
            pitch_cv = np.std(voiced_f0) / (np.mean(voiced_f0) + 1e-10)
            pitch_stability = 1 / (1 + pitch_cv)  # Convert to stability score
        else:
            pitch_stability = 0.5

        # Amplitude stability
        amplitude = librosa.feature.rms(
            y=audio_data, frame_length=self.frame_length, hop_length=self.frame_shift
        )[0]

        # Remove silent segments
        voiced_amplitude = amplitude[amplitude > np.max(amplitude) * 0.1]

        if len(voiced_amplitude) > 1:
            amp_cv = np.std(voiced_amplitude) / (np.mean(voiced_amplitude) + 1e-10)
            amplitude_stability = 1 / (1 + amp_cv)
        else:
            amplitude_stability = 0.5

        # Voice onset/offset times
        energy_threshold = np.max(amplitude) * 0.1
        voice_active = amplitude > energy_threshold

        # Find first voice onset
        onset_frame = np.argmax(voice_active) if np.any(voice_active) else 0
        onset_time = float(onset_frame * self.frame_shift / self.config.sample_rate)

        # Find last voice offset
        if np.any(voice_active):
            offset_frame = len(voice_active) - np.argmax(voice_active[::-1]) - 1
            offset_time = float(
                offset_frame * self.frame_shift / self.config.sample_rate
            )
        else:
            offset_time = float(len(audio_data) / self.config.sample_rate)

        return {
            "pitch_stability": pitch_stability,
            "amplitude_stability": amplitude_stability,
            "onset_time": onset_time,
            "offset_time": offset_time,
        }

    def _extract_pitch_urgency(self, audio_data: np.ndarray) -> Dict[str, float]:
        """Extract pitch-related urgency markers."""
        # Extract F0 contour
        f0 = librosa.yin(
            audio_data,
            fmin=50,
            fmax=600,
            sr=self.config.sample_rate,
            frame_length=self.frame_length * 4,
        )

        # Get voiced F0 values
        voiced_f0 = f0[f0 > 0]

        if len(voiced_f0) > 0:
            f0_max = np.max(voiced_f0)
            f0_min = np.min(voiced_f0)
            f0_excursion = f0_max - f0_min
        else:
            f0_max = 150  # Default
            f0_excursion = 50

        return {"f0_max": f0_max, "f0_excursion": f0_excursion}

    def _extract_spectral_urgency(self, audio_data: np.ndarray) -> Dict[str, float]:
        """Extract spectral features indicating urgency."""
        # STFT
        stft = librosa.stft(
            audio_data, n_fft=self.frame_length * 2, hop_length=self.frame_shift
        )
        magnitude = np.abs(stft)
        freqs = librosa.fft_frequencies(
            sr=self.config.sample_rate, n_fft=self.frame_length * 2
        )

        # High frequency emphasis
        high_freq_idx = freqs > 3000
        mid_freq_idx = (freqs > 1000) & (freqs <= 3000)

        if np.sum(mid_freq_idx) > 0:
            high_energy = np.mean(magnitude[high_freq_idx, :])
            mid_energy = np.mean(magnitude[mid_freq_idx, :])
            high_freq_emphasis = high_energy / (mid_energy + 1e-10)
        else:
            high_freq_emphasis = 0.5

        # Spectral slope steepness
        slopes = []
        for frame_idx in range(magnitude.shape[1]):
            frame_mag = magnitude[:, frame_idx]
            if np.sum(frame_mag) > 0:
                # Fit line to spectrum
                valid_idx = frame_mag > 0
                if np.sum(valid_idx) > 10:
                    slope, _ = np.polyfit(freqs[valid_idx], frame_mag[valid_idx], 1)
                    slopes.append(abs(slope))

        slope_steepness = np.mean(slopes) if slopes else 0.5

        # Energy concentration (how focused the energy is)
        energy_per_frame = np.sum(magnitude**2, axis=0)
        if len(energy_per_frame) > 0 and np.sum(energy_per_frame) > 0:
            energy_distribution = energy_per_frame / np.sum(energy_per_frame)
            # Entropy of energy distribution
            entropy = -np.sum(
                energy_distribution * np.log2(energy_distribution + 1e-10)
            )
            max_entropy = np.log2(len(energy_distribution))
            energy_concentration = (
                1 - (entropy / max_entropy) if max_entropy > 0 else 0.5
            )
        else:
            energy_concentration = 0.5

        # Composite spectral urgency score
        urgency_score = min(
            1.0,
            (
                high_freq_emphasis * 0.4
                + slope_steepness * 0.3
                + energy_concentration * 0.3
            ),
        )

        return {
            "urgency_score": urgency_score,
            "high_freq_emphasis": min(1.0, high_freq_emphasis),
            "slope_steepness": min(1.0, slope_steepness / 1000),
            "energy_concentration": energy_concentration,
        }

    def _calculate_temporal_urgency(self, audio_data: np.ndarray) -> float:
        """Calculate temporal urgency from rhythm and timing."""
        # Energy envelope
        energy = librosa.feature.rms(
            y=audio_data, frame_length=self.frame_length, hop_length=self.frame_shift
        )[0]

        # Detect rapid changes
        energy_diff = np.diff(energy)
        rapid_changes = np.sum(np.abs(energy_diff) > np.std(energy_diff) * 2)

        # Calculate urgency based on rapid changes
        change_rate = rapid_changes / len(energy_diff) if len(energy_diff) > 0 else 0

        return min(1.0, change_rate * 5)  # Scale to 0-1

    def _calculate_voice_irregularity(self, audio_data: np.ndarray) -> float:
        """Calculate overall voice irregularity."""
        # Multiple measures of irregularity

        # 1. Pitch irregularity
        f0 = librosa.yin(
            audio_data,
            fmin=50,
            fmax=500,
            sr=self.config.sample_rate,
            frame_length=self.frame_length * 4,
        )
        voiced_f0 = f0[f0 > 0]

        if len(voiced_f0) > 2:
            # Jitter (short-term pitch variation)
            f0_diff = np.abs(np.diff(voiced_f0))
            jitter = np.mean(f0_diff) / (np.mean(voiced_f0) + 1e-10)
        else:
            jitter = 0.1

        # 2. Amplitude irregularity
        amplitude = librosa.feature.rms(
            y=audio_data, frame_length=self.frame_length, hop_length=self.frame_shift
        )[0]

        if len(amplitude) > 2:
            # Shimmer (short-term amplitude variation)
            amp_diff = np.abs(np.diff(amplitude))
            shimmer = np.mean(amp_diff) / (np.mean(amplitude) + 1e-10)
        else:
            shimmer = 0.1

        # 3. Spectral irregularity
        spectral_centroid = librosa.feature.spectral_centroid(
            y=audio_data, sr=self.config.sample_rate, hop_length=self.frame_shift
        )[0]
        spectral_var = np.std(spectral_centroid) / (np.mean(spectral_centroid) + 1e-10)

        # Combine irregularity measures
        irregularity = min(1.0, (jitter * 5 + shimmer * 3 + spectral_var) / 3)

        return float(irregularity)

    def _extract_harmonic_distortion(self, audio_data: np.ndarray) -> Dict[str, float]:
        """Extract harmonic distortion and subharmonics."""
        # Perform FFT on windows
        windows = self._create_analysis_windows(audio_data)

        distortion_values = []
        subharmonic_values = []

        for window in windows:
            if np.max(np.abs(window)) < 0.01:  # Skip silent windows
                continue

            # Apply window function
            windowed = window * np.hanning(len(window))

            # FFT
            spectrum = np.abs(np.fft.rfft(windowed))
            freqs = np.fft.rfftfreq(len(windowed), 1 / self.config.sample_rate)

            # Find fundamental frequency
            f0_idx = self._find_fundamental(spectrum, freqs)

            if f0_idx is not None and f0_idx > 0:
                f0 = freqs[f0_idx]

                # Check for subharmonics (f0/2, f0/3)
                subharmonic_energy = 0
                for divisor in [2, 3]:
                    sub_f0 = f0 / divisor
                    sub_idx = np.argmin(np.abs(freqs - sub_f0))
                    if 0 < sub_idx < len(spectrum):
                        subharmonic_energy += spectrum[sub_idx]

                # Normalize by fundamental energy
                if spectrum[f0_idx] > 0:
                    subharmonic_ratio = subharmonic_energy / spectrum[f0_idx]
                    subharmonic_values.append(subharmonic_ratio)

                # Calculate harmonic distortion
                # Expected vs actual harmonic amplitudes
                harmonic_distortion = self._calculate_harmonic_distortion(
                    spectrum, freqs, f0
                )
                distortion_values.append(harmonic_distortion)

        return {
            "distortion": (
                float(np.mean(distortion_values)) if distortion_values else 0.5
            ),
            "subharmonics": (
                float(np.mean(subharmonic_values)) if subharmonic_values else 0.0
            ),
        }

    def _create_analysis_windows(self, audio_data: np.ndarray) -> List[np.ndarray]:
        """Create analysis windows for detailed processing."""
        window_size = int(0.05 * self.config.sample_rate)  # 50ms windows
        hop_size = window_size // 2

        windows = []
        for i in range(0, len(audio_data) - window_size, hop_size):
            windows.append(audio_data[i : i + window_size])

        return windows

    def _find_fundamental(
        self, spectrum: np.ndarray, freqs: np.ndarray
    ) -> Optional[int]:
        """Find fundamental frequency index in spectrum."""
        # Simple peak detection in expected F0 range
        f0_range = (freqs > 80) & (freqs < 400)

        if np.any(f0_range):
            f0_spectrum = spectrum[f0_range]

            if len(f0_spectrum) > 0:
                peak_idx = np.argmax(f0_spectrum)
                # Convert back to full spectrum index
                full_idx = np.where(f0_range)[0][peak_idx]
                return int(full_idx)

        return None

    def _calculate_harmonic_distortion(
        self, spectrum: np.ndarray, freqs: np.ndarray, f0: float
    ) -> float:
        """Calculate harmonic distortion based on harmonic series."""
        harmonic_energies = []
        expected_decay = 1.0  # Exponential decay factor

        for harmonic_num in range(2, 6):  # Check harmonics 2-5
            harmonic_freq = f0 * harmonic_num
            harmonic_idx = np.argmin(np.abs(freqs - harmonic_freq))

            if 0 < harmonic_idx < len(spectrum):
                actual_energy = spectrum[harmonic_idx]
                expected_energy = spectrum[np.argmin(np.abs(freqs - f0))] * (
                    expected_decay ** (harmonic_num - 1)
                )

                if expected_energy > 0:
                    distortion = abs(actual_energy - expected_energy) / expected_energy
                    harmonic_energies.append(distortion)

        return np.mean(harmonic_energies) if harmonic_energies else 0.5

    def _score_to_urgency_level(self, score: float) -> UrgencyLevel:
        """Convert urgency score to urgency level."""
        thresholds = self.config.urgency_thresholds

        if score >= thresholds["emergency"]:
            return UrgencyLevel.EMERGENCY
        elif score >= thresholds["critical"]:
            return UrgencyLevel.CRITICAL
        elif score >= thresholds["high"]:
            return UrgencyLevel.HIGH
        elif score >= thresholds["moderate"]:
            return UrgencyLevel.MODERATE
        elif score >= thresholds["low"]:
            return UrgencyLevel.LOW
        else:
            return UrgencyLevel.ROUTINE

    def _identify_active_indicators(
        self, features: UrgencyFeatures
    ) -> List[UrgencyIndicator]:
        """Identify which urgency indicators are active."""
        active = []

        # Check each indicator against its patterns
        for indicator, pattern in self.urgency_patterns.items():
            is_active = False

            if indicator == UrgencyIndicator.SPEECH_PRESSURE:
                if (
                    features.speaking_rate > pattern["thresholds"]["speaking_rate"]
                    or features.speaking_rate_acceleration
                    > pattern["thresholds"]["acceleration"]
                ):
                    is_active = True

            elif indicator == UrgencyIndicator.VOCAL_STRAIN:
                if (
                    features.vocal_effort > pattern["thresholds"]["effort"]
                    or features.glottal_pressure > pattern["thresholds"]["pressure"]
                ):
                    is_active = True

            elif indicator == UrgencyIndicator.BREATH_DISTRESS:
                if (
                    features.breath_rate > pattern["thresholds"]["rate"]
                    or features.breath_effort > pattern["thresholds"]["effort"]
                ):
                    is_active = True

            elif indicator == UrgencyIndicator.PANIC_MARKERS:
                if (
                    features.f0_maximum > pattern["thresholds"]["f0_max"]
                    or features.spectral_urgency > pattern["thresholds"]["spectral"]
                ):
                    is_active = True

            # Additional indicators
            elif indicator == UrgencyIndicator.VOICE_WEAKNESS:
                if features.amplitude_stability < 0.3 or features.vocal_effort < 0.2:
                    is_active = True

            elif indicator == UrgencyIndicator.PAIN_URGENCY:
                if features.vocal_effort > 0.8 and features.f0_excursion > 150:
                    is_active = True

            elif indicator == UrgencyIndicator.CONFUSION_URGENCY:
                if features.voice_irregularity > 0.7 or features.articulation_rate < 2:
                    is_active = True

            elif indicator == UrgencyIndicator.VOCAL_TREMOR:
                if features.voice_irregularity > 0.6 and features.pitch_stability < 0.4:
                    is_active = True

            elif indicator == UrgencyIndicator.SPEECH_FRAGMENTATION:
                if features.voice_breaks_frequency > 0.1:
                    is_active = True

            if is_active:
                active.append(indicator)

        return active

    async def _detect_medical_context(
        self,
        features: UrgencyFeatures,
        indicators: List[UrgencyIndicator],
        hint: Optional[str],
    ) -> Tuple[Optional[UrgencyContext], List[UrgencyContext]]:
        """Detect likely medical context from voice features."""
        context_scores = {}

        # Check each context pattern
        for context, pattern in self.context_patterns.items():
            score = 0.0
            matches = 0

            # Check if required indicators are present
            required_indicators = pattern.get("indicators", [])
            indicator_match = sum(1 for ind in required_indicators if ind in indicators)
            score += (
                indicator_match / len(required_indicators) if required_indicators else 0
            )
            matches += 1

            # Check feature ranges
            for feature_name, expected_value in pattern.get("features", {}).items():
                actual_value = getattr(features, feature_name, None)

                if actual_value is not None:
                    if isinstance(expected_value, tuple):  # Range
                        if expected_value[0] <= actual_value <= expected_value[1]:
                            score += 1
                    elif isinstance(expected_value, (int, float)):  # Threshold
                        if actual_value >= expected_value:
                            score += 1
                    matches += 1

            if matches > 0:
                context_scores[context] = score / matches

        # Apply hint if provided
        if hint and hint.lower() in [c.value for c in UrgencyContext]:
            hint_context = UrgencyContext(hint.lower())
            if hint_context in context_scores:
                context_scores[hint_context] *= 1.5  # Boost score

        # Sort by score
        sorted_contexts = sorted(
            context_scores.items(), key=lambda x: x[1], reverse=True
        )

        # Determine likely and secondary contexts
        likely_context = None
        secondary_contexts = []

        if sorted_contexts:
            if sorted_contexts[0][1] > 0.5:  # Threshold for primary context
                likely_context = sorted_contexts[0][0]

            # Add secondary contexts with reasonable scores
            for context, ctx_score in sorted_contexts[1:]:
                if ctx_score > 0.3:  # Threshold for secondary context
                    secondary_contexts.append(context)

        return likely_context, secondary_contexts

    async def _analyze_temporal_urgency(self, audio_data: np.ndarray) -> Dict[str, Any]:
        """Analyze how urgency changes over time."""
        window_size = int(self.config.temporal_window_size * self.config.sample_rate)
        hop_size = window_size // 2

        progression = []
        urgency_scores = []

        # Analyze windows
        for i in range(0, len(audio_data) - window_size, hop_size):
            window = audio_data[i : i + window_size]
            timestamp = i / self.config.sample_rate

            # Quick feature extraction for window
            window_features = await self._extract_urgency_features(window)
            window_score = window_features.calculate_urgency_score()

            progression.append((timestamp, window_score))
            urgency_scores.append(window_score)

        # Find peak urgency
        peak_time = None
        if urgency_scores:
            peak_idx = np.argmax(urgency_scores)
            peak_time = progression[peak_idx][0]

        # Determine trend
        trend = "stable"
        if len(urgency_scores) > 2:
            # Linear regression to find trend
            times = np.array([p[0] for p in progression])
            scores = np.array(urgency_scores)

            slope, _ = np.polyfit(times, scores, 1)

            if slope > 0.1:
                trend = "increasing"
            elif slope < -0.1:
                trend = "decreasing"

        return {"progression": progression, "peak_time": peak_time, "trend": trend}

    def _determine_triage_category(
        self,
        level: UrgencyLevel,
        context: Optional[UrgencyContext],
        indicators: List[UrgencyIndicator],
    ) -> str:
        """Determine triage category based on analysis."""
        # Emergency categories
        if level == UrgencyLevel.EMERGENCY:
            if context == UrgencyContext.CARDIAC:
                return "Emergency - Possible cardiac event"
            elif context == UrgencyContext.RESPIRATORY:
                return "Emergency - Severe respiratory distress"
            elif context == UrgencyContext.NEUROLOGICAL:
                return "Emergency - Possible stroke/neurological emergency"
            else:
                return "Emergency - Immediate medical attention required"

        # Critical categories
        elif level == UrgencyLevel.CRITICAL:
            if UrgencyIndicator.BREATH_DISTRESS in indicators:
                return "Critical - Significant breathing difficulty"
            elif UrgencyIndicator.PANIC_MARKERS in indicators:
                return "Critical - Severe panic/anxiety attack"
            else:
                return "Critical - Urgent medical evaluation needed"

        # High urgency
        elif level == UrgencyLevel.HIGH:
            if context == UrgencyContext.PAIN:
                return "High Priority - Severe pain requiring prompt attention"
            elif context == UrgencyContext.PSYCHIATRIC:
                return "High Priority - Mental health crisis"
            else:
                return "High Priority - Prompt medical assessment recommended"

        # Moderate urgency
        elif level == UrgencyLevel.MODERATE:
            return "Moderate Priority - Medical evaluation within 1-2 hours"

        # Low urgency
        elif level == UrgencyLevel.LOW:
            return "Low Priority - Can be seen when convenient"

        # Routine
        else:
            return "Routine - Schedule regular appointment"

    def _identify_priority_symptoms(
        self,
        features: UrgencyFeatures,
        indicators: List[UrgencyIndicator],
        context: Optional[UrgencyContext],
    ) -> List[str]:
        """Identify priority symptoms for triage."""
        symptoms = []

        # Breathing issues
        if features.breath_rate > 25:
            symptoms.append("Rapid breathing")
        if features.breath_effort > 0.7:
            symptoms.append("Labored breathing")
        if UrgencyIndicator.BREATH_DISTRESS in indicators:
            symptoms.append("Respiratory distress")

        # Voice/speech issues
        if features.voice_breaks_frequency > 0.1:
            symptoms.append("Voice breaking/weakness")
        if features.speaking_rate > 250:
            symptoms.append("Rapid/pressured speech")
        if features.hoarseness_index > 0.7:
            symptoms.append("Severe hoarseness")

        # Pain indicators
        if features.vocal_effort > 0.8 and features.f0_excursion > 150:
            symptoms.append("Severe pain indicated by voice")

        # Neurological signs
        if features.voice_irregularity > 0.7:
            symptoms.append("Significant voice irregularity")
        if features.articulation_rate < 2:
            symptoms.append("Slowed/impaired speech")

        # Panic/anxiety
        if UrgencyIndicator.PANIC_MARKERS in indicators:
            symptoms.append("Panic/extreme anxiety")

        # Context-specific symptoms
        if context == UrgencyContext.CARDIAC:
            symptoms.append("Possible cardiac symptoms")
        elif context == UrgencyContext.NEUROLOGICAL:
            symptoms.append("Possible neurological symptoms")

        return symptoms[:5]  # Limit to top 5 symptoms

    def _calculate_confidence(
        self, features: UrgencyFeatures, audio_quality: float, num_indicators: int
    ) -> float:
        """Calculate confidence in urgency assessment."""
        confidence_factors = []

        # Audio quality factor
        confidence_factors.append(audio_quality)

        # Feature reliability
        feature_confidence = 1.0

        # Check if key features are within expected ranges
        if features.speaking_rate == 0 or features.speaking_rate > 500:
            feature_confidence *= 0.7
        if features.breath_rate < 5 or features.breath_rate > 60:
            feature_confidence *= 0.8

        confidence_factors.append(feature_confidence)

        # Indicator consistency
        if num_indicators > 0:
            # More indicators = higher confidence (up to a point)
            indicator_confidence = min(1.0, num_indicators / 5)
            confidence_factors.append(indicator_confidence)
        else:
            confidence_factors.append(0.5)

        # Feature consistency
        # Check if features align (e.g., high speaking rate with high temporal urgency)
        consistency = 1.0
        if features.speaking_rate > 200 and features.temporal_urgency < 0.3:
            consistency *= 0.7
        if features.breath_rate > 25 and features.breath_effort < 0.3:
            consistency *= 0.8

        confidence_factors.append(consistency)

        return float(np.mean(confidence_factors))

    def _generate_warnings(
        self, audio_quality: float, confidence: float, features: UrgencyFeatures
    ) -> List[str]:
        """Generate warnings about analysis limitations."""
        warnings = []

        if audio_quality < self.config.min_audio_quality:
            warnings.append("Low audio quality may affect accuracy")

        if confidence < self.config.min_confidence_threshold:
            warnings.append("Low confidence in analysis results")

        if features.voice_breaks_frequency > 0.3:
            warnings.append(
                "Frequent voice breaks detected - may affect feature extraction"
            )

        if features.breath_rate > 40:
            warnings.append(
                "Extremely high breathing rate detected - verify sensor/recording"
            )

        if features.speaking_rate == 0:
            warnings.append("No clear speech detected in recording")

        return warnings

    async def process_audio_file(
        self,
        file_path: str,
        context_hint: Optional[str] = None,
        save_results: bool = True,
    ) -> UrgencyDetectionResult:
        """Process an audio file for urgency detection."""
        try:
            # Load audio file
            audio_data, _ = librosa.load(file_path, sr=self.config.sample_rate)

            # Detect urgency
            result = await self.detect_urgency(audio_data, context_hint)

            # Save results if requested
            if save_results:
                output_path = file_path.replace(".wav", "_urgency.json")
                with open(output_path, "w", encoding="utf-8") as f:
                    json.dump(result.to_dict(), f, indent=2)
                logger.info("Urgency analysis saved to %s", output_path)

            return result

        except Exception as e:
            logger.error("Error processing audio file: %s", str(e), exc_info=True)
            raise

    def get_urgency_statistics(
        self, results: List[UrgencyDetectionResult]
    ) -> Dict[str, Any]:
        """Calculate statistics from multiple urgency detection results."""
        if not results:
            return {}

        # Aggregate statistics
        urgency_scores = [r.urgency_score for r in results]
        urgency_levels = [r.urgency_level.value for r in results]

        # Count indicators
        all_indicators = []
        for r in results:
            all_indicators.extend(r.active_indicators)

        indicator_counts: Dict[str, int] = {}
        for indicator in all_indicators:
            indicator_counts[indicator.value] = (
                indicator_counts.get(indicator.value, 0) + 1
            )

        # Context statistics
        context_counts: Dict[str, int] = {}
        for r in results:
            if r.likely_context:
                context_counts[r.likely_context.value] = (
                    context_counts.get(r.likely_context.value, 0) + 1
                )

        stats = {
            "mean_urgency_score": np.mean(urgency_scores),
            "max_urgency_score": np.max(urgency_scores),
            "urgency_level_distribution": {
                level: urgency_levels.count(level) for level in set(urgency_levels)
            },
            "most_common_indicators": sorted(
                indicator_counts.items(), key=lambda x: x[1], reverse=True
            )[:5],
            "context_distribution": context_counts,
            "mean_confidence": np.mean([r.confidence_score for r in results]),
            "samples_analyzed": len(results),
        }

        return stats
