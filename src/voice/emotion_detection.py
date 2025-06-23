"""
Emotion Detection Module for Medical Voice Analysis.

This module implements emotion detection from voice recordings
to assist in medical assessments and patient care.
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from scipy import signal

try:
    import librosa

    LIBROSA_AVAILABLE = True
except ImportError:
    LIBROSA_AVAILABLE = False
    import warnings

    warnings.warn(
        "librosa not available. Audio feature extraction will be limited.", stacklevel=2
    )

logger = logging.getLogger(__name__)


class EmotionType(Enum):
    """Types of emotions detected in voice."""

    NEUTRAL = "neutral"
    HAPPY = "happy"
    SAD = "sad"
    ANGRY = "angry"
    FEAR = "fear"
    ANXIOUS = "anxious"
    STRESSED = "stressed"
    PAIN = "pain"  # Medical-specific
    CONFUSED = "confused"
    CALM = "calm"


class EmotionIntensity(Enum):
    """Intensity levels of detected emotions."""

    VERY_LOW = 1
    LOW = 2
    MODERATE = 3
    HIGH = 4
    VERY_HIGH = 5


@dataclass
class EmotionFeatures:
    """Acoustic features used for emotion detection."""

    # Prosodic features
    pitch_mean: float = 0.0
    pitch_std: float = 0.0
    pitch_range: float = 0.0
    pitch_contour: List[float] = field(default_factory=list)

    # Energy features
    energy_mean: float = 0.0
    energy_std: float = 0.0
    energy_range: float = 0.0

    # Speaking rate features
    speaking_rate: float = 0.0
    pause_ratio: float = 0.0
    voiced_ratio: float = 0.0

    # Spectral features
    spectral_centroid_mean: float = 0.0
    spectral_rolloff_mean: float = 0.0
    spectral_flux_mean: float = 0.0

    # MFCC features (Mel-frequency cepstral coefficients)
    mfcc_means: List[float] = field(default_factory=list)
    mfcc_stds: List[float] = field(default_factory=list)

    # Voice quality features
    jitter: float = 0.0  # Pitch variation
    shimmer: float = 0.0  # Amplitude variation
    hnr: float = 0.0  # Harmonics-to-noise ratio

    # Formant features
    formant_frequencies: List[float] = field(default_factory=list)
    formant_bandwidths: List[float] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "pitch_mean": self.pitch_mean,
            "pitch_std": self.pitch_std,
            "pitch_range": self.pitch_range,
            "energy_mean": self.energy_mean,
            "energy_std": self.energy_std,
            "speaking_rate": self.speaking_rate,
            "pause_ratio": self.pause_ratio,
            "voiced_ratio": self.voiced_ratio,
            "spectral_centroid_mean": self.spectral_centroid_mean,
            "spectral_rolloff_mean": self.spectral_rolloff_mean,
            "spectral_flux_mean": self.spectral_flux_mean,
            "jitter": self.jitter,
            "shimmer": self.shimmer,
            "hnr": self.hnr,
        }


@dataclass
class EmotionScore:
    """Score for a detected emotion."""

    emotion: EmotionType
    confidence: float
    intensity: EmotionIntensity

    @property
    def intensity_value(self) -> int:
        """Get numeric intensity value."""
        return self.intensity.value

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "emotion": self.emotion.value,
            "confidence": self.confidence,
            "intensity": self.intensity.value,
            "intensity_label": self.intensity.name,
        }


@dataclass
class EmotionDetectionResult:
    """Result of emotion detection analysis."""

    primary_emotion: EmotionType
    emotion_scores: List[EmotionScore] = field(default_factory=list)

    # Acoustic features
    features: Optional[EmotionFeatures] = None

    # Medical indicators
    distress_level: float = 0.0  # 0-1 scale
    pain_indicators: float = 0.0  # 0-1 scale
    anxiety_markers: float = 0.0  # 0-1 scale

    # Temporal analysis
    emotion_timeline: List[Tuple[float, EmotionType]] = field(default_factory=list)
    emotion_stability: float = 1.0  # How stable emotions are

    # Processing metadata
    audio_duration: float = 0.0
    processing_time_ms: float = 0.0
    confidence_score: float = 0.0

    # Warnings and notes
    warnings: List[str] = field(default_factory=list)
    clinical_notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "primary_emotion": self.primary_emotion.value,
            "emotion_scores": [score.to_dict() for score in self.emotion_scores],
            "features": self.features.to_dict() if self.features else None,
            "distress_level": self.distress_level,
            "pain_indicators": self.pain_indicators,
            "anxiety_markers": self.anxiety_markers,
            "emotion_stability": self.emotion_stability,
            "audio_duration": self.audio_duration,
            "processing_time_ms": self.processing_time_ms,
            "confidence_score": self.confidence_score,
            "warnings": self.warnings,
            "clinical_notes": self.clinical_notes,
        }


@dataclass
class EmotionDetectionConfig:
    """Configuration for emotion detection."""

    # Feature extraction
    sample_rate: int = 16000
    frame_length_ms: int = 25
    frame_shift_ms: int = 10

    # Analysis parameters
    enable_medical_emotions: bool = True
    enable_temporal_analysis: bool = True
    min_segment_duration: float = 1.0  # Minimum duration for analysis

    # Model settings
    use_ml_model: bool = True
    model_path: Optional[str] = None
    model_type: str = "ensemble"  # "svm", "neural", "ensemble"

    # Thresholds
    confidence_threshold: float = 0.6
    intensity_thresholds: Dict[str, float] = field(
        default_factory=lambda: {
            "very_low": 0.2,
            "low": 0.4,
            "moderate": 0.6,
            "high": 0.8,
            "very_high": 0.9,
        }
    )
    # Medical-specific settings
    pain_detection_sensitivity: float = 0.7
    distress_detection_sensitivity: float = 0.8

    # Feature weights
    feature_weights: Dict[str, float] = field(
        default_factory=lambda: {
            "prosodic": 0.3,
            "spectral": 0.25,
            "voice_quality": 0.25,
            "temporal": 0.2,
        }
    )


class EmotionDetector:
    """
    Detects emotions from voice recordings with medical context awareness.

    Uses acoustic features and machine learning to identify emotional states
    that may be relevant for medical assessment and patient care.
    """

    def __init__(self, config: Optional[EmotionDetectionConfig] = None):
        """
        Initialize the emotion detector.

        Args:
            config: Detection configuration
        """
        self.config = config or EmotionDetectionConfig()

        # Feature extraction parameters
        self.frame_length = int(
            self.config.sample_rate * self.config.frame_length_ms / 1000
        )
        self.frame_shift = int(
            self.config.sample_rate * self.config.frame_shift_ms / 1000
        )

        # Emotion patterns (simplified - would use ML model in production)
        self.emotion_patterns = {
            EmotionType.NEUTRAL: {
                "pitch_range": (80, 250),
                "energy_std_ratio": 0.3,
                "speaking_rate": (3, 5),
            },
            EmotionType.ANXIOUS: {
                "pitch_mean_elevated": 1.2,  # Relative to neutral
                "speaking_rate_elevated": 1.3,
                "pause_ratio_reduced": 0.7,
            },
            EmotionType.SAD: {
                "pitch_mean_reduced": 0.8,
                "energy_reduced": 0.7,
                "speaking_rate_reduced": 0.8,
            },
            EmotionType.ANGRY: {
                "pitch_mean_elevated": 1.4,
                "energy_elevated": 1.5,
                "spectral_centroid_elevated": 1.3,
            },
            EmotionType.PAIN: {
                "pitch_variability_high": 1.5,
                "voice_breaks": True,
                "hnr_reduced": 0.6,
            },
            EmotionType.STRESSED: {
                "jitter_elevated": 1.4,
                "shimmer_elevated": 1.3,
                "speaking_rate_variable": True,
            },
        }

        # Medical emotion indicators
        self.medical_indicators = {
            "distress": ["pitch_variability", "voice_tremor", "breath_patterns"],
            "pain": ["vocal_fry", "voice_breaks", "tension"],
            "anxiety": ["speaking_rate", "pause_patterns", "pitch_elevation"],
        }

        logger.info(
            "EmotionDetector initialized with sample_rate=%dHz", self.config.sample_rate
        )

    async def detect_emotions(
        self, audio_data: np.ndarray, segment_emotions: bool = True
    ) -> EmotionDetectionResult:
        """
        Detect emotions from audio data.

        Args:
            audio_data: Audio signal as numpy array
            segment_emotions: Whether to analyze emotions over time segments

        Returns:
            EmotionDetectionResult with detected emotions and features
        """
        start_time = datetime.now()

        try:
            # Normalize audio
            audio_data = self._normalize_audio(audio_data)

            # Extract acoustic features
            features = await self._extract_features(audio_data)

            # Detect emotions
            emotion_scores = await self._classify_emotions(features)
            # Sort by confidence
            emotion_scores.sort(key=lambda x: x.confidence, reverse=True)
            primary_emotion = (
                emotion_scores[0].emotion if emotion_scores else EmotionType.NEUTRAL
            )

            # Medical-specific analysis
            medical_metrics = await self._analyze_medical_indicators(
                features, emotion_scores
            )

            # Temporal analysis if requested
            emotion_timeline: List[Any] = []
            emotion_stability = 1.0

            if segment_emotions and self.config.enable_temporal_analysis:
                emotion_timeline, emotion_stability = (
                    await self._analyze_temporal_emotions(audio_data, features)
                )

            # Calculate confidence
            confidence = self._calculate_confidence(emotion_scores, features)

            # Generate clinical notes
            clinical_notes = self._generate_clinical_notes(
                emotion_scores, medical_metrics, features
            )

            # Processing time
            processing_time = (datetime.now() - start_time).total_seconds() * 1000

            return EmotionDetectionResult(
                primary_emotion=primary_emotion,
                emotion_scores=emotion_scores,
                features=features,
                distress_level=medical_metrics.get("distress", 0.0),
                pain_indicators=medical_metrics.get("pain", 0.0),
                anxiety_markers=medical_metrics.get("anxiety", 0.0),
                emotion_timeline=emotion_timeline,
                emotion_stability=emotion_stability,
                audio_duration=len(audio_data) / self.config.sample_rate,
                processing_time_ms=processing_time,
                confidence_score=confidence,
                clinical_notes=clinical_notes,
            )

        except Exception as e:
            logger.error("Error in emotion detection: %s", str(e), exc_info=True)
            raise

    def _normalize_audio(self, audio_data: np.ndarray) -> np.ndarray:
        """Normalize audio to [-1, 1] range."""
        max_val = np.max(np.abs(audio_data))
        if max_val > 0:
            normalized: np.ndarray = (audio_data / max_val).astype(audio_data.dtype)
            return normalized
        return audio_data

    async def _extract_features(self, audio_data: np.ndarray) -> EmotionFeatures:
        """Extract acoustic features from audio."""
        features = EmotionFeatures()

        # Extract pitch features
        pitch_values = self._extract_pitch(audio_data)
        if len(pitch_values) > 0:
            features.pitch_mean = np.mean(pitch_values)
            features.pitch_std = np.std(pitch_values)
            features.pitch_range = np.max(pitch_values) - np.min(pitch_values)
            features.pitch_contour = pitch_values.tolist()[:100]  # First 100 values

        # Extract energy features
        energy = self._calculate_energy(audio_data)
        features.energy_mean = np.mean(energy)
        features.energy_std = np.std(energy)
        features.energy_range = np.max(energy) - np.min(energy)

        # Extract speaking rate features
        features.speaking_rate = self._calculate_speaking_rate(audio_data)
        features.pause_ratio = self._calculate_pause_ratio(audio_data)
        features.voiced_ratio = self._calculate_voiced_ratio(audio_data)

        # Extract spectral features
        spectral_features = self._extract_spectral_features(audio_data)
        features.spectral_centroid_mean = spectral_features["centroid"]
        features.spectral_rolloff_mean = spectral_features["rolloff"]
        features.spectral_flux_mean = spectral_features["flux"]

        # Extract MFCC features
        mfcc = self._extract_mfcc(audio_data)
        features.mfcc_means = np.mean(mfcc, axis=1).tolist()
        features.mfcc_stds = np.std(mfcc, axis=1).tolist()

        # Extract voice quality features
        features.jitter = self._calculate_jitter(pitch_values)
        features.shimmer = self._calculate_shimmer(audio_data)
        features.hnr = self._calculate_hnr(audio_data)

        return features

    def _extract_pitch(self, audio_data: np.ndarray) -> np.ndarray:
        """Extract pitch (F0) values from audio."""
        try:
            # Using librosa pitch tracking
            pitches, magnitudes = librosa.piptrack(
                y=audio_data,
                sr=self.config.sample_rate,
                hop_length=self.frame_shift,
                fmin=50,
                fmax=400,
            )

            # Get pitch values where magnitude is significant
            pitch_values = []
            for t in range(pitches.shape[1]):
                index = magnitudes[:, t].argmax()
                pitch = pitches[index, t]
                if pitch > 0:
                    pitch_values.append(pitch)

            return np.array(pitch_values)
        except (ValueError, AttributeError, RuntimeError) as e:
            logger.warning("Pitch extraction failed: %s", str(e))
            return np.array([])

    def _calculate_energy(self, audio_data: np.ndarray) -> np.ndarray:
        """Calculate frame-wise energy."""
        frames = librosa.util.frame(
            audio_data, frame_length=self.frame_length, hop_length=self.frame_shift
        )
        energy: np.ndarray = np.sqrt(np.mean(frames**2, axis=0)).astype(frames.dtype)
        return energy

    def _calculate_speaking_rate(self, audio_data: np.ndarray) -> float:
        """Estimate speaking rate (syllables per second)."""
        # Simplified: use energy peaks as syllable markers
        energy = self._calculate_energy(audio_data)

        # Find peaks in energy
        peaks, _ = signal.find_peaks(energy, height=np.mean(energy))

        # Estimate syllables per second
        duration = len(audio_data) / self.config.sample_rate
        if duration > 0:
            return len(peaks) / duration
        return 0.0

    def _calculate_pause_ratio(self, audio_data: np.ndarray) -> float:
        """Calculate ratio of pause duration to total duration."""
        energy = self._calculate_energy(audio_data)
        threshold = np.mean(energy) * 0.1

        # Count frames below threshold as pauses
        pause_frames = np.sum(energy < threshold)
        total_frames = len(energy)

        if total_frames > 0:
            return float(pause_frames / total_frames)
        return 0.0

    def _calculate_voiced_ratio(self, audio_data: np.ndarray) -> float:
        """Calculate ratio of voiced segments."""
        # Zero crossing rate for voiced/unvoiced detection
        zcr = librosa.feature.zero_crossing_rate(
            audio_data, frame_length=self.frame_length, hop_length=self.frame_shift
        )[0]

        # Low ZCR indicates voiced segments
        voiced_threshold = 0.1
        voiced_frames = np.sum(zcr < voiced_threshold)

        if len(zcr) > 0:
            return float(voiced_frames / len(zcr))
        return 0.0

    def _extract_spectral_features(self, audio_data: np.ndarray) -> Dict[str, float]:
        """Extract spectral features."""
        # Spectral centroid
        centroid = librosa.feature.spectral_centroid(
            y=audio_data, sr=self.config.sample_rate, hop_length=self.frame_shift
        )

        # Spectral rolloff
        rolloff = librosa.feature.spectral_rolloff(
            y=audio_data, sr=self.config.sample_rate, hop_length=self.frame_shift
        )
        # Spectral flux
        stft = librosa.stft(audio_data, hop_length=self.frame_shift)
        magnitude = np.abs(stft)
        flux = np.sum(np.diff(magnitude, axis=1) ** 2, axis=0)

        return {
            "centroid": float(np.mean(centroid)),
            "rolloff": float(np.mean(rolloff)),
            "flux": float(np.mean(flux)) if len(flux) > 0 else 0.0,
        }

    def _extract_mfcc(self, audio_data: np.ndarray) -> np.ndarray:
        """Extract MFCC features."""
        mfcc = librosa.feature.mfcc(
            y=audio_data,
            sr=self.config.sample_rate,
            n_mfcc=13,
            hop_length=self.frame_shift,
        )
        mfcc_typed: np.ndarray = mfcc.astype(audio_data.dtype)
        return mfcc_typed

    def _calculate_jitter(self, pitch_values: np.ndarray) -> float:
        """Calculate jitter (pitch period variation)."""
        if len(pitch_values) < 2:
            return 0.0

        # Convert pitch to period
        periods = 1.0 / (pitch_values + 1e-10)

        # Calculate jitter as average absolute difference
        period_diffs = np.abs(np.diff(periods))
        mean_period = np.mean(periods)

        if mean_period > 0:
            return float(np.mean(period_diffs) / mean_period)
        return 0.0

    def _calculate_shimmer(self, audio_data: np.ndarray) -> float:
        """Calculate shimmer (amplitude variation)."""
        # Get amplitude envelope
        amplitude = np.abs(audio_data)

        # Find local maxima (peaks)
        peaks, _ = signal.find_peaks(amplitude)

        if len(peaks) < 2:
            return 0.0
        peak_amplitudes = amplitude[peaks]

        # Calculate shimmer as relative amplitude variation
        amp_diffs = np.abs(np.diff(peak_amplitudes))
        mean_amp = np.mean(peak_amplitudes)

        if mean_amp > 0:
            return float(np.mean(amp_diffs) / mean_amp)
        return 0.0

    def _calculate_hnr(self, audio_data: np.ndarray) -> float:
        """Calculate harmonics-to-noise ratio."""
        # Simplified HNR calculation
        # Autocorrelation method
        autocorr = np.correlate(audio_data, audio_data, mode="full")
        autocorr = autocorr[len(autocorr) // 2 :]

        # Find first peak after zero lag
        peaks, _ = signal.find_peaks(autocorr)

        if len(peaks) > 0 and autocorr[0] > 0:
            # HNR as ratio of peak to noise floor
            harmonic_peak = autocorr[peaks[0]]
            noise_floor = np.mean(autocorr[peaks[0] * 2 :])

            if noise_floor > 0:
                hnr_linear = harmonic_peak / noise_floor
                return float(10 * np.log10(hnr_linear))  # Convert to dB

        return 0.0

    async def _classify_emotions(self, features: EmotionFeatures) -> List[EmotionScore]:
        """Classify emotions based on features."""
        emotion_scores = []

        if self.config.use_ml_model and self.config.model_path:
            # Use ML model (placeholder)
            emotion_scores = await self._ml_classify(features)
        else:
            # Rule-based classification
            emotion_scores = self._rule_based_classify(features)

        return emotion_scores

    def _rule_based_classify(self, features: EmotionFeatures) -> List[EmotionScore]:
        """Rule-based emotion classification."""
        scores = []

        # Neutral baseline
        neutral_score = 0.5

        # Check for anxiety indicators
        if (
            features.pitch_mean > 200
            and features.speaking_rate > 4.5
            and features.pause_ratio < 0.2
        ):
            anxiety_score = min(0.9, 0.3 + features.pitch_std / 100)
            scores.append(
                EmotionScore(
                    emotion=EmotionType.ANXIOUS,
                    confidence=anxiety_score,
                    intensity=self._score_to_intensity(anxiety_score),
                )
            )
            neutral_score -= 0.2

        # Check for sadness indicators
        if (
            features.pitch_mean < 150
            and features.energy_mean < 0.3
            and features.speaking_rate < 3.0
        ):
            sadness_score = min(0.85, 0.3 + (1 - features.energy_mean))
            scores.append(
                EmotionScore(
                    emotion=EmotionType.SAD,
                    confidence=sadness_score,
                    intensity=self._score_to_intensity(sadness_score),
                )
            )
            neutral_score -= 0.2

        # Check for anger indicators
        if features.energy_mean > 0.7 and features.spectral_centroid_mean > 2000:
            anger_score = min(0.8, features.energy_mean * 0.8)
            scores.append(
                EmotionScore(
                    emotion=EmotionType.ANGRY,
                    confidence=anger_score,
                    intensity=self._score_to_intensity(anger_score),
                )
            )
            neutral_score -= 0.15

        # Check for pain indicators (medical-specific)
        if features.jitter > 0.05 and features.hnr < 15 and features.pitch_std > 50:
            pain_score = min(0.9, features.jitter * 10)
            scores.append(
                EmotionScore(
                    emotion=EmotionType.PAIN,
                    confidence=pain_score,
                    intensity=self._score_to_intensity(
                        pain_score * 1.2
                    ),  # Pain tends to be intense
                )
            )
            neutral_score -= 0.3

        # Add neutral score if significant
        if neutral_score > 0.3:
            scores.append(
                EmotionScore(
                    emotion=EmotionType.NEUTRAL,
                    confidence=max(0.3, neutral_score),
                    intensity=EmotionIntensity.LOW,
                )
            )

        # Normalize scores
        total_confidence = sum(s.confidence for s in scores)
        if total_confidence > 0:
            for score in scores:
                score.confidence /= total_confidence

        return scores

    def _score_to_intensity(self, score: float) -> EmotionIntensity:
        """Convert confidence score to intensity level."""
        thresholds = self.config.intensity_thresholds

        if score >= thresholds["very_high"]:
            return EmotionIntensity.VERY_HIGH
        elif score >= thresholds["high"]:
            return EmotionIntensity.HIGH
        elif score >= thresholds["moderate"]:
            return EmotionIntensity.MODERATE
        elif score >= thresholds["low"]:
            return EmotionIntensity.LOW
        else:
            return EmotionIntensity.VERY_LOW

    async def _ml_classify(self, features: EmotionFeatures) -> List[EmotionScore]:
        """Machine learning based classification (placeholder)."""
        # This would load and use a trained model
        logger.warning("ML classification not implemented, using rule-based")
        return self._rule_based_classify(features)

    async def _analyze_medical_indicators(
        self, features: EmotionFeatures, emotion_scores: List[EmotionScore]
    ) -> Dict[str, float]:
        """Analyze medical-specific emotional indicators."""
        indicators: Dict[str, float] = {}

        # Distress level calculation
        distress_features = [
            features.pitch_std / 100,  # Normalized pitch variability
            features.jitter * 10,  # Normalized jitter
            1 - features.hnr / 30,  # Inverted and normalized HNR
            features.speaking_rate / 10 if features.speaking_rate > 5 else 0,
        ]
        indicators["distress"] = float(
            np.mean(distress_features) * self.config.distress_detection_sensitivity
        )

        # Pain indicators
        pain_features = [
            features.jitter * 15,
            features.shimmer * 10,
            1 - features.voiced_ratio,
            features.pitch_std / 80,
        ]

        # Check for pain emotion score
        pain_emotion_score = next(
            (s.confidence for s in emotion_scores if s.emotion == EmotionType.PAIN), 0
        )
        pain_features.append(pain_emotion_score)

        indicators["pain"] = float(
            np.mean(pain_features) * self.config.pain_detection_sensitivity
        )

        # Anxiety markers
        anxiety_features = [
            features.speaking_rate / 8 if features.speaking_rate > 4 else 0,
            features.pitch_mean / 300 if features.pitch_mean > 200 else 0,
            1 - features.pause_ratio * 2,
            (
                features.energy_std / features.energy_mean
                if features.energy_mean > 0
                else 0
            ),
        ]

        # Check for anxiety emotion score
        anxiety_emotion_score = next(
            (s.confidence for s in emotion_scores if s.emotion == EmotionType.ANXIOUS),
            0,
        )
        anxiety_features.append(anxiety_emotion_score)

        indicators["anxiety"] = float(np.mean(anxiety_features))

        # Clamp all indicators to [0, 1]
        for key in indicators:
            indicators[key] = float(np.clip(indicators[key], 0, 1))

        return indicators

    async def _analyze_temporal_emotions(
        self, audio_data: np.ndarray, global_features: EmotionFeatures
    ) -> Tuple[List[Tuple[float, EmotionType]], float]:
        """Analyze emotions over time segments."""
        # Use global features for context
        _ = global_features  # Will be used for temporal analysis context

        segment_duration = self.config.min_segment_duration
        segment_samples = int(segment_duration * self.config.sample_rate)

        timeline = []
        emotions_sequence = []

        # Process audio in segments
        for i in range(0, len(audio_data) - segment_samples, segment_samples):
            segment = audio_data[i : i + segment_samples]
            timestamp = i / self.config.sample_rate

            # Extract features for segment
            segment_features = await self._extract_features(segment)

            # Classify emotion for segment
            segment_scores = await self._classify_emotions(segment_features)

            if segment_scores:
                primary_emotion = max(
                    segment_scores, key=lambda x: x.confidence
                ).emotion
                timeline.append((timestamp, primary_emotion))
                emotions_sequence.append(primary_emotion)

        # Calculate stability (how often emotion changes)
        if len(emotions_sequence) > 1:
            changes = sum(
                1
                for i in range(1, len(emotions_sequence))
                if emotions_sequence[i] != emotions_sequence[i - 1]
            )
            stability = 1 - (changes / (len(emotions_sequence) - 1))
        else:
            stability = 1.0

        return timeline, stability

    def _calculate_confidence(
        self, emotion_scores: List[EmotionScore], features: EmotionFeatures
    ) -> float:
        """Calculate overall confidence in emotion detection."""
        if not emotion_scores:
            return 0.0

        # Factors affecting confidence
        confidence_factors = []

        # 1. Top emotion score
        top_score = emotion_scores[0].confidence if emotion_scores else 0
        confidence_factors.append(top_score)

        # 2. Separation between top emotions
        if len(emotion_scores) > 1:
            separation = emotion_scores[0].confidence - emotion_scores[1].confidence
            confidence_factors.append(min(1.0, separation * 2))

        # 3. Feature quality
        feature_quality = 1.0
        if features.pitch_mean == 0 or features.energy_mean == 0:
            feature_quality *= 0.5
        if features.hnr < 5:  # Poor voice quality
            feature_quality *= 0.8
        confidence_factors.append(feature_quality)

        # 4. Voice activity
        if features.voiced_ratio < 0.2:  # Too little voiced content
            confidence_factors.append(0.5)
        else:
            confidence_factors.append(1.0)

        return float(np.mean(confidence_factors))

    def _generate_clinical_notes(
        self,
        emotion_scores: List[EmotionScore],
        medical_metrics: Dict[str, float],
        features: EmotionFeatures,
    ) -> List[str]:
        """Generate clinical notes based on emotion analysis."""
        notes = []

        # High distress level
        if medical_metrics.get("distress", 0) > 0.7:
            notes.append("High distress level detected in voice patterns")
        # Pain indicators
        if medical_metrics.get("pain", 0) > 0.6:
            notes.append("Voice characteristics suggest possible pain or discomfort")
            if features.jitter > 0.05:
                notes.append("Elevated voice tremor detected")

        # Anxiety markers
        if medical_metrics.get("anxiety", 0) > 0.7:
            notes.append("Voice patterns indicate elevated anxiety")
            if features.speaking_rate > 5:
                notes.append("Rapid speech rate observed")

        # Voice quality issues
        if features.hnr < 10:
            notes.append("Poor voice quality may affect assessment accuracy")

        # Emotional instability
        emotion_types = [
            score.emotion for score in emotion_scores if score.confidence > 0.3
        ]
        if len(emotion_types) > 2:
            notes.append("Multiple emotional states detected")

        # Specific emotion notes
        for score in emotion_scores:
            if (
                score.confidence > 0.6
                and score.intensity.value >= EmotionIntensity.HIGH.value
            ):
                notes.append(f"Strong {score.emotion.value} emotion detected")

        return notes

    def get_emotion_profile(
        self, results: List[EmotionDetectionResult]
    ) -> Dict[str, Any]:
        """Create an emotion profile from multiple detection results."""
        if not results:
            return {}

        # Aggregate emotions
        emotion_counts: Dict[str, int] = {}
        total_distress = 0.0
        total_pain = 0.0
        total_anxiety = 0.0

        for result in results:
            emotion_counts[result.primary_emotion.value] = (
                emotion_counts.get(result.primary_emotion.value, 0) + 1
            )
            total_distress += result.distress_level
            total_pain += result.pain_indicators
            total_anxiety += result.anxiety_markers
        # Calculate averages
        n_results = len(results)

        profile = {
            "dominant_emotion": max(emotion_counts.items(), key=lambda x: x[1])[0],
            "emotion_distribution": emotion_counts,
            "average_distress": total_distress / n_results,
            "average_pain_indicators": total_pain / n_results,
            "average_anxiety": total_anxiety / n_results,
            "emotional_stability": np.mean([r.emotion_stability for r in results]),
            "sample_count": n_results,
            "confidence_mean": np.mean([r.confidence_score for r in results]),
            "clinical_notes": list(
                set(note for r in results for note in r.clinical_notes)
            ),
        }

        return profile

    async def process_audio_file(
        self, file_path: str, save_results: bool = True
    ) -> EmotionDetectionResult:
        """Process an audio file for emotion detection."""
        # Load audio file (placeholder - would use librosa.load in production)
        audio_data = np.random.randn(16000 * 5)  # 5 seconds placeholder

        # Detect emotions
        result = await self.detect_emotions(audio_data)

        # Save results if requested
        if save_results:
            output_path = file_path.replace(".wav", "_emotions.json")
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(result.to_dict(), f, indent=2)
            logger.info("Emotion analysis saved to %s", output_path)

        return result
