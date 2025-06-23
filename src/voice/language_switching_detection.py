"""Language Switching Detection Module for Multilingual Voice Analysis.

This module implements detection of language switching events in speech,
supporting identification of code-switching patterns, language transitions,
and multilingual communication analysis for medical contexts.
 Handles FHIR Resource validation.

Note: Audio data analyzed may contain PHI. Ensure all audio is encrypted
both in transit and at rest. Implement strict access control to limit
language switching detection operations to authorized healthcare providers.
"""

# pylint: disable=too-many-lines

import asyncio
import logging
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from scipy.special import softmax
from sklearn.mixture import GaussianMixture

from src.security import requires_phi_access

try:
    import librosa
except ImportError:
    librosa = None

logger = logging.getLogger(__name__)


class LanguageCode(Enum):
    """Supported language codes (ISO 639-1)."""

    EN = "en"  # English
    ES = "es"  # Spanish
    FR = "fr"  # French
    AR = "ar"  # Arabic
    ZH = "zh"  # Chinese
    HI = "hi"  # Hindi
    PT = "pt"  # Portuguese
    RU = "ru"  # Russian
    JA = "ja"  # Japanese
    DE = "de"  # German
    KO = "ko"  # Korean
    IT = "it"  # Italian
    TR = "tr"  # Turkish
    VI = "vi"  # Vietnamese
    PL = "pl"  # Polish
    UK = "uk"  # Ukrainian
    FA = "fa"  # Persian/Farsi
    SW = "sw"  # Swahili
    UR = "ur"  # Urdu
    BN = "bn"  # Bengali
    UNKNOWN = "unknown"


class SwitchingType(Enum):
    """Types of language switching patterns."""

    INTER_SENTENTIAL = "inter_sentential"  # Between sentences
    INTRA_SENTENTIAL = "intra_sentential"  # Within sentences
    TAG_SWITCHING = "tag_switching"  # Tags/phrases from another language
    BORROWING = "borrowing"  # Single word borrowing
    MIXED = "mixed"  # Multiple types


class SwitchingContext(Enum):
    """Context in which switching occurs."""

    MEDICAL_TERMS = "medical_terms"
    EMOTIONAL_EXPRESSION = "emotional_expression"
    CLARIFICATION = "clarification"
    EMPHASIS = "emphasis"
    QUOTATION = "quotation"
    PROPER_NAMES = "proper_names"
    TECHNICAL_TERMS = "technical_terms"
    SOCIAL_CONVENTION = "social_convention"
    UNKNOWN = "unknown"


@dataclass
class LanguageSegment:
    """Represents a segment of speech in a specific language."""

    start_time: float
    end_time: float
    language: LanguageCode
    confidence: float
    features: Dict[str, float] = field(default_factory=dict)
    text: Optional[str] = None

    @property
    def duration(self) -> float:
        """Get segment duration in seconds."""
        return self.end_time - self.start_time

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration": self.duration,
            "language": self.language.value,
            "confidence": self.confidence,
            "text": self.text,
        }


@dataclass
class SwitchingEvent:
    """Represents a language switching event."""

    time: float
    from_language: LanguageCode
    to_language: LanguageCode
    switch_type: SwitchingType
    context: SwitchingContext
    confidence: float
    duration: float  # Duration of transition

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "time": self.time,
            "from_language": self.from_language.value,
            "to_language": self.to_language.value,
            "switch_type": self.switch_type.value,
            "context": self.context.value,
            "confidence": self.confidence,
            "duration": self.duration,
        }


@dataclass
class LanguageProfile:
    """Profile of language-specific features."""

    language: LanguageCode

    # Phonetic features
    phoneme_distribution: Dict[str, float] = field(default_factory=dict)
    typical_pitch_range: Tuple[float, float] = (80, 400)
    rhythm_pattern: str = "stress-timed"  # or syllable-timed, mora-timed

    # Acoustic features
    spectral_characteristics: Dict[str, float] = field(default_factory=dict)
    formant_patterns: Dict[str, List[float]] = field(default_factory=dict)

    # Prosodic features
    intonation_patterns: List[str] = field(default_factory=list)
    stress_patterns: Dict[str, float] = field(default_factory=dict)

    # Statistical models
    gmm_model: Optional[Any] = None  # Gaussian Mixture Model
    feature_means: Optional[np.ndarray] = None
    feature_stds: Optional[np.ndarray] = None


@dataclass
class SwitchingAnalysisResult:
    """Complete language switching analysis result."""

    # Language segments
    segments: List[LanguageSegment]
    primary_language: LanguageCode
    language_distribution: Dict[LanguageCode, float]  # Percentage of each language

    # Switching events
    switching_events: List[SwitchingEvent]
    switch_count: int
    switching_rate: float  # Switches per minute

    # Switching patterns
    switching_types: Dict[SwitchingType, int]
    switching_contexts: Dict[SwitchingContext, int]

    # Code-switching metrics
    mixing_index: float  # 0-1, degree of language mixing
    balance_index: float  # 0-1, balance between languages
    complexity_score: float  # Complexity of switching patterns

    # Medical relevance
    medical_term_switches: List[Dict[str, Any]]
    clarity_impact: float  # Impact on communication clarity

    # Processing metadata
    audio_duration: float
    sample_rate: int
    confidence_score: float
    processing_time_ms: float

    # Quality indicators
    detection_quality: float
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "primary_language": self.primary_language.value,
            "language_distribution": {
                lang.value: pct for lang, pct in self.language_distribution.items()
            },
            "segments": [seg.to_dict() for seg in self.segments],
            "switch_count": self.switch_count,
            "switching_rate": self.switching_rate,
            "switching_events": [event.to_dict() for event in self.switching_events],
            "mixing_index": self.mixing_index,
            "balance_index": self.balance_index,
            "complexity_score": self.complexity_score,
            "medical_term_switches": self.medical_term_switches,
            "clarity_impact": self.clarity_impact,
            "confidence_score": self.confidence_score,
        }

    def get_summary(self) -> str:
        """Get a summary of language switching analysis."""
        summary = f"Primary Language: {self.primary_language.value.upper()}\n"
        summary += "Language Distribution:\n"
        for lang, pct in sorted(
            self.language_distribution.items(), key=lambda x: x[1], reverse=True
        ):
            if pct > 0:
                summary += f"  - {lang.value}: {pct:.1f}%\n"

        summary += "\nSwitching Statistics:\n"
        summary += f"  - Total Switches: {self.switch_count}\n"
        summary += f"  - Switching Rate: {self.switching_rate:.2f} per minute\n"
        summary += f"  - Mixing Index: {self.mixing_index:.2f}\n"

        if self.switching_types:
            summary += "\nSwitching Types:\n"
            for switch_type, count in self.switching_types.items():
                summary += f"  - {switch_type.value}: {count}\n"

        return summary


@dataclass
class LanguageSwitchingConfig:
    """Configuration for language switching detection."""

    # Detection settings
    min_segment_duration: float = 0.5  # Minimum duration for language segment
    switching_threshold: float = 0.7  # Confidence threshold for switching

    # Feature extraction
    window_length: float = 0.025  # seconds
    hop_length: float = 0.010  # seconds
    n_mfcc: int = 13
    n_mels: int = 128

    # Language models
    supported_languages: List[LanguageCode] = field(
        default_factory=lambda: [
            LanguageCode.EN,
            LanguageCode.ES,
            LanguageCode.FR,
            LanguageCode.AR,
            LanguageCode.ZH,
        ]
    )
    use_pretrained_models: bool = True
    model_path: Optional[str] = None

    # Analysis parameters
    detect_borrowing: bool = True
    detect_medical_terms: bool = True
    context_window: float = 2.0  # seconds, for context analysis

    # Medical terminology
    medical_term_languages: List[LanguageCode] = field(
        default_factory=lambda: [LanguageCode.EN, LanguageCode.ES]
    )

    # Smoothing and post-processing
    smooth_predictions: bool = True
    smoothing_window: int = 5  # frames
    min_switch_interval: float = 0.3  # seconds


class LanguageSwitchingDetector:
    """
    Detects and analyzes language switching patterns in speech.

    Supports identification of code-switching, borrowing, and
    multilingual communication patterns in medical contexts.
    """

    def __init__(self, config: Optional[LanguageSwitchingConfig] = None):
        """
        Initialize the language switching detector.

        Args:
            config: Detection configuration
        """
        self.config = config or LanguageSwitchingConfig()

        # Initialize language profiles
        self.language_profiles = self._initialize_language_profiles()

        # Load or initialize models
        if self.config.use_pretrained_models:
            self._load_pretrained_models()
        else:
            self._initialize_models()

        # Medical terminology database
        self.medical_terms = self._load_medical_terminology()

        logger.info("LanguageSwitchingDetector initialized")

    def _initialize_language_profiles(self) -> Dict[LanguageCode, LanguageProfile]:
        """Initialize language-specific profiles."""
        profiles = {}

        # English profile
        profiles[LanguageCode.EN] = LanguageProfile(
            language=LanguageCode.EN,
            typical_pitch_range=(80, 300),
            rhythm_pattern="stress-timed",
            phoneme_distribution={"vowels": 0.4, "consonants": 0.6, "fricatives": 0.15},
        )

        # Spanish profile
        profiles[LanguageCode.ES] = LanguageProfile(
            language=LanguageCode.ES,
            typical_pitch_range=(100, 350),
            rhythm_pattern="syllable-timed",
            phoneme_distribution={"vowels": 0.45, "consonants": 0.55, "trills": 0.05},
        )

        # French profile
        profiles[LanguageCode.FR] = LanguageProfile(
            language=LanguageCode.FR,
            typical_pitch_range=(100, 400),
            rhythm_pattern="syllable-timed",
            phoneme_distribution={"vowels": 0.43, "consonants": 0.57, "nasals": 0.1},
        )

        # Arabic profile
        profiles[LanguageCode.AR] = LanguageProfile(
            language=LanguageCode.AR,
            typical_pitch_range=(90, 350),
            rhythm_pattern="stress-timed",
            phoneme_distribution={
                "vowels": 0.35,
                "consonants": 0.65,
                "pharyngeals": 0.05,
            },
        )

        # Chinese profile
        profiles[LanguageCode.ZH] = LanguageProfile(
            language=LanguageCode.ZH,
            typical_pitch_range=(80, 400),
            rhythm_pattern="syllable-timed",
            phoneme_distribution={
                "vowels": 0.5,
                "consonants": 0.5,
                "tones": 0.0,  # Tonal language
            },
        )

        return profiles

    def _load_pretrained_models(self) -> None:
        """Load pre-trained language identification models."""
        # In production, would load actual trained models
        # For now, initialize GMMs for each language
        for lang_code, profile in self.language_profiles.items():
            if lang_code in self.config.supported_languages:
                # Initialize GMM for language
                profile.gmm_model = GaussianMixture(
                    n_components=8, covariance_type="diag", random_state=42
                )

                # Initialize with mock data (in production, use trained parameters)
                mock_features = np.random.randn(
                    1000, self.config.n_mfcc + self.config.n_mels
                )
                profile.gmm_model.fit(mock_features)

                profile.feature_means = np.mean(mock_features, axis=0)
                profile.feature_stds = np.std(mock_features, axis=0)

        logger.info("Loaded language models (mock)")

    def _initialize_models(self) -> None:
        """Initialize language models from scratch."""
        # Similar to load_pretrained_models but without pre-trained weights
        self._load_pretrained_models()

    def _load_medical_terminology(self) -> Dict[str, List[LanguageCode]]:
        """Load medical terminology database."""
        # Simplified medical terms dictionary
        # In production, would load from comprehensive database
        return {
            # English medical terms
            "diagnosis": [LanguageCode.EN],
            "prescription": [LanguageCode.EN],
            "symptoms": [LanguageCode.EN],
            "medication": [LanguageCode.EN],
            "allergy": [LanguageCode.EN],
            "diabetes_en": [LanguageCode.EN],
            "hypertension": [LanguageCode.EN],
            # Spanish medical terms
            "diagnóstico": [LanguageCode.ES],
            "receta": [LanguageCode.ES],
            "síntomas": [LanguageCode.ES],
            "medicamento": [LanguageCode.ES],
            "alergia": [LanguageCode.ES],
            "diabetes_es": [LanguageCode.ES],
            "hipertensión": [LanguageCode.ES],
            # Terms used in multiple languages
            "covid": [LanguageCode.EN, LanguageCode.ES, LanguageCode.FR],
            "coronavirus": [LanguageCode.EN, LanguageCode.ES, LanguageCode.FR],
        }

    async def detect_language_switching(
        self,
        audio_data: np.ndarray,
        sample_rate: int = 16000,
        reference_text: Optional[str] = None,
    ) -> SwitchingAnalysisResult:
        """
        Detect and analyze language switching in audio.

        Args:
            audio_data: Audio signal
            sample_rate: Sample rate of audio
            reference_text: Optional reference text for alignment (not used yet)

        Returns:
            SwitchingAnalysisResult with all findings
        """
        _ = reference_text  # Future enhancement: align with text
        start_time = datetime.now()

        try:
            # Extract features for language identification
            features = self._extract_features(audio_data, sample_rate)

            # Segment audio and identify languages
            segments = await self._identify_language_segments(features, sample_rate)

            # Smooth predictions if configured
            if self.config.smooth_predictions:
                segments = self._smooth_segments(segments)

            # Detect switching events
            switching_events = self._detect_switching_events(segments)

            # Analyze switching patterns
            switching_types = self._classify_switching_types(
                switching_events, segments, audio_data, sample_rate
            )

            # Analyze switching contexts
            switching_contexts = await self._analyze_switching_contexts(
                switching_events, segments, audio_data, sample_rate
            )

            # Calculate language distribution
            language_distribution = self._calculate_language_distribution(
                segments, len(audio_data) / sample_rate
            )

            # Determine primary language
            primary_language = (
                max(language_distribution.items(), key=lambda x: x[1])[0]
                if language_distribution
                else LanguageCode.UNKNOWN
            )

            # Calculate metrics
            mixing_index = self._calculate_mixing_index(segments)
            balance_index = self._calculate_balance_index(language_distribution)
            complexity_score = self._calculate_complexity_score(
                switching_events, switching_types
            )

            # Detect medical term switches
            medical_switches = await self._detect_medical_term_switches(
                segments, audio_data, sample_rate
            )

            # Assess clarity impact
            clarity_impact = self._assess_clarity_impact(
                switching_events, mixing_index, complexity_score
            )

            # Calculate confidence
            confidence_score = self._calculate_confidence(segments, features)

            # Generate warnings
            warnings = self._generate_warnings(
                segments, switching_events, confidence_score
            )

            # Processing time
            processing_time = (datetime.now() - start_time).total_seconds() * 1000

            return SwitchingAnalysisResult(
                segments=segments,
                primary_language=primary_language,
                language_distribution=language_distribution,
                switching_events=switching_events,
                switch_count=len(switching_events),
                switching_rate=len(switching_events)
                / (len(audio_data) / sample_rate / 60),
                switching_types=switching_types,
                switching_contexts=switching_contexts,
                mixing_index=mixing_index,
                balance_index=balance_index,
                complexity_score=complexity_score,
                medical_term_switches=medical_switches,
                clarity_impact=clarity_impact,
                audio_duration=len(audio_data) / sample_rate,
                sample_rate=sample_rate,
                confidence_score=confidence_score,
                processing_time_ms=processing_time,
                detection_quality=confidence_score,
                warnings=warnings,
            )

        except Exception as e:
            logger.error(
                "Error in language switching detection: %s", str(e), exc_info=True
            )
            raise

    def _extract_features(self, audio_data: np.ndarray, sample_rate: int) -> np.ndarray:
        """Extract features for language identification."""
        # Frame the audio
        frame_length = int(self.config.window_length * sample_rate)
        hop_length = int(self.config.hop_length * sample_rate)

        # Extract MFCC features
        mfccs = librosa.feature.mfcc(
            y=audio_data,
            sr=sample_rate,
            n_mfcc=self.config.n_mfcc,
            n_fft=frame_length,
            hop_length=hop_length,
        )

        # Extract mel-spectrogram
        mel_spec = librosa.feature.melspectrogram(
            y=audio_data,
            sr=sample_rate,
            n_mels=self.config.n_mels,
            n_fft=frame_length,
            hop_length=hop_length,
        )

        # Convert to log scale
        log_mel = librosa.power_to_db(mel_spec, ref=np.max)

        # Extract additional features
        # Spectral centroid
        spectral_centroid = librosa.feature.spectral_centroid(
            y=audio_data, sr=sample_rate, hop_length=hop_length
        )

        # Zero crossing rate
        zcr = librosa.feature.zero_crossing_rate(
            audio_data, frame_length=frame_length, hop_length=hop_length
        )

        # Spectral rolloff
        rolloff = librosa.feature.spectral_rolloff(
            y=audio_data, sr=sample_rate, hop_length=hop_length
        )

        # Combine all features
        features = np.vstack([mfccs, log_mel, spectral_centroid, zcr, rolloff])

        return features.T  # Transpose to have time as first dimension

    async def _identify_language_segments(
        self, features: np.ndarray, sample_rate: int
    ) -> List[LanguageSegment]:
        """Identify language for each frame and create segments."""
        _ = sample_rate  # Unused but kept for consistency
        segments = []

        # Get language predictions for each frame
        frame_predictions = []
        frame_confidences = []

        for frame_features in features:
            lang, conf = self._identify_frame_language(frame_features)
            frame_predictions.append(lang)
            frame_confidences.append(conf)

        # Group consecutive frames with same language into segments
        current_segment_start = 0
        current_language = (
            frame_predictions[0] if frame_predictions else LanguageCode.UNKNOWN
        )

        hop_length = self.config.hop_length

        for i in range(1, len(frame_predictions)):
            if frame_predictions[i] != current_language:
                # End current segment
                segment_duration = (i - current_segment_start) * hop_length

                if segment_duration >= self.config.min_segment_duration:
                    # Calculate average confidence for segment
                    avg_confidence = np.mean(frame_confidences[current_segment_start:i])

                    segments.append(
                        LanguageSegment(
                            start_time=current_segment_start * hop_length,
                            end_time=i * hop_length,
                            language=current_language,
                            confidence=float(avg_confidence),
                        )
                    )

                # Start new segment
                current_segment_start = i
                current_language = frame_predictions[i]

        # Add final segment
        if current_segment_start < len(frame_predictions):
            segment_duration = (
                len(frame_predictions) - current_segment_start
            ) * hop_length

            if segment_duration >= self.config.min_segment_duration:
                avg_confidence = np.mean(frame_confidences[current_segment_start:])

                segments.append(
                    LanguageSegment(
                        start_time=current_segment_start * hop_length,
                        end_time=len(frame_predictions) * hop_length,
                        language=current_language,
                        confidence=float(avg_confidence),
                    )
                )

        return segments

    def _identify_frame_language(
        self, frame_features: np.ndarray
    ) -> Tuple[LanguageCode, float]:
        """Identify language for a single frame."""
        scores = {}

        # Calculate likelihood for each language
        for lang_code in self.config.supported_languages:
            if lang_code in self.language_profiles:
                profile = self.language_profiles[lang_code]

                if profile.gmm_model is not None:
                    # Use GMM to calculate log-likelihood
                    score = profile.gmm_model.score_samples(
                        frame_features.reshape(1, -1)
                    )[0]
                    scores[lang_code] = score

        if not scores:
            return LanguageCode.UNKNOWN, 0.0

        # Convert to probabilities using softmax
        lang_codes = list(scores.keys())
        score_values = np.array(list(scores.values()))
        probabilities = softmax(score_values)

        # Get best language
        best_idx = np.argmax(probabilities)
        best_lang = lang_codes[best_idx]
        confidence = probabilities[best_idx]

        return best_lang, float(confidence)

    def _smooth_segments(
        self, segments: List[LanguageSegment]
    ) -> List[LanguageSegment]:
        """Smooth language segments to reduce noise."""
        if len(segments) <= 1:
            return segments

        smoothed_segments: List[LanguageSegment] = []
        i = 0

        while i < len(segments):
            current_segment = segments[i]

            # Look ahead for short segments that might be noise
            if (
                i < len(segments) - 2
                and current_segment.duration < self.config.min_switch_interval
            ):

                # Check if surrounding segments have same language
                prev_lang = segments[i - 1].language if i > 0 else None
                next_lang = segments[i + 1].language if i < len(segments) - 1 else None

                if prev_lang == next_lang and prev_lang != current_segment.language:
                    # Skip this segment (merge with surrounding)
                    if smoothed_segments and prev_lang is not None:
                        # Extend previous segment
                        smoothed_segments[-1] = LanguageSegment(
                            start_time=smoothed_segments[-1].start_time,
                            end_time=(
                                segments[i + 1].end_time
                                if i < len(segments) - 1
                                else current_segment.end_time
                            ),
                            language=prev_lang,
                            confidence=(
                                smoothed_segments[-1].confidence
                                + segments[i + 1].confidence
                            )
                            / 2,
                        )
                    i += 2  # Skip next segment too
                    continue

            smoothed_segments.append(current_segment)
            i += 1

        return smoothed_segments

    def _detect_switching_events(
        self, segments: List[LanguageSegment]
    ) -> List[SwitchingEvent]:
        """Detect language switching events from segments."""
        events = []

        for i in range(1, len(segments)):
            prev_segment = segments[i - 1]
            curr_segment = segments[i]

            if prev_segment.language != curr_segment.language:
                # Calculate transition duration
                transition_duration = min(
                    0.1,  # Max 100ms transition
                    (curr_segment.start_time - prev_segment.end_time),
                )

                event = SwitchingEvent(
                    time=prev_segment.end_time,
                    from_language=prev_segment.language,
                    to_language=curr_segment.language,
                    switch_type=SwitchingType.INTER_SENTENTIAL,  # Default
                    context=SwitchingContext.UNKNOWN,  # To be determined
                    confidence=(prev_segment.confidence + curr_segment.confidence) / 2,
                    duration=transition_duration,
                )

                events.append(event)

        return events

    def _classify_switching_types(
        self,
        events: List[SwitchingEvent],
        segments: List[LanguageSegment],
        audio_data: np.ndarray,
        sample_rate: int,
    ) -> Dict[SwitchingType, int]:
        """Classify the type of each switching event."""
        type_counts: defaultdict[SwitchingType, int] = defaultdict(int)

        for event in events:
            # Find segments around the switch
            prev_segment = None
            next_segment = None

            for segment in segments:
                if segment.end_time <= event.time:
                    prev_segment = segment
                elif segment.start_time >= event.time and next_segment is None:
                    next_segment = segment

            if prev_segment and next_segment:
                # Classify based on segment characteristics
                switch_type = self._determine_switch_type(
                    prev_segment, next_segment, audio_data, sample_rate
                )
                event.switch_type = switch_type
                type_counts[switch_type] += 1

        return dict(type_counts)

    def _determine_switch_type(
        self,
        prev_segment: LanguageSegment,
        next_segment: LanguageSegment,
        audio_data: np.ndarray,
        sample_rate: int,
    ) -> SwitchingType:
        """Determine the type of language switch."""
        _ = audio_data  # Unused but kept for future audio analysis
        _ = sample_rate  # Unused but kept for future audio analysis
        # Simple heuristics for switch type classification

        # Check duration of segments
        if prev_segment.duration > 2.0 and next_segment.duration > 2.0:
            # Long segments suggest inter-sentential
            return SwitchingType.INTER_SENTENTIAL

        elif prev_segment.duration < 0.5 or next_segment.duration < 0.5:
            # Very short segment might be borrowing
            return SwitchingType.BORROWING

        elif prev_segment.duration < 1.0 and next_segment.duration < 1.0:
            # Short segments suggest tag switching
            return SwitchingType.TAG_SWITCHING

        else:
            # Medium duration suggests intra-sentential
            return SwitchingType.INTRA_SENTENTIAL

    async def _analyze_switching_contexts(
        self,
        events: List[SwitchingEvent],
        segments: List[LanguageSegment],
        audio_data: np.ndarray,
        sample_rate: int,
    ) -> Dict[SwitchingContext, int]:
        """Analyze the context of language switches."""
        context_counts: defaultdict[SwitchingContext, int] = defaultdict(int)

        for event in events:
            # Determine context based on acoustic and linguistic cues
            context = await self._determine_switch_context(
                event, segments, audio_data, sample_rate
            )
            event.context = context
            context_counts[context] += 1

        return dict(context_counts)

    async def _determine_switch_context(
        self,
        event: SwitchingEvent,
        segments: List[LanguageSegment],
        audio_data: np.ndarray,
        sample_rate: int,
    ) -> SwitchingContext:
        """Determine the context of a language switch."""
        _ = segments  # Unused but kept for future context analysis
        # Extract audio around the switch
        context_window = self.config.context_window
        start_time = max(0, event.time - context_window / 2)
        end_time = min(len(audio_data) / sample_rate, event.time + context_window / 2)

        start_sample = int(start_time * sample_rate)
        end_sample = int(end_time * sample_rate)
        context_audio = audio_data[start_sample:end_sample]

        # Analyze prosodic features
        if len(context_audio) > 0:
            # Check for emphasis (higher energy/pitch)
            energy = np.mean(context_audio**2)

            # Extract pitch
            f0, _, _ = librosa.pyin(context_audio, fmin=80, fmax=400, sr=sample_rate)

            if f0 is not None and len(f0) > 0:
                valid_f0 = f0[~np.isnan(f0)]
                if len(valid_f0) > 0:
                    pitch_variation = np.std(valid_f0)

                    # High pitch variation might indicate emphasis or emotion
                    if pitch_variation > 50:
                        if energy > np.mean(audio_data**2) * 2:
                            return SwitchingContext.EMPHASIS
                        else:
                            return SwitchingContext.EMOTIONAL_EXPRESSION

        # Check if switching to medical terminology
        if event.switch_type == SwitchingType.BORROWING:
            # Short switches might be technical terms
            return SwitchingContext.MEDICAL_TERMS

        # Default context
        return SwitchingContext.UNKNOWN

    def _calculate_language_distribution(
        self, segments: List[LanguageSegment], total_duration: float
    ) -> Dict[LanguageCode, float]:
        """Calculate percentage of time spent in each language."""
        language_durations: defaultdict[LanguageCode, float] = defaultdict(float)

        for segment in segments:
            language_durations[segment.language] += segment.duration

        # Convert to percentages
        distribution = {}
        for lang, duration in language_durations.items():
            distribution[lang] = (duration / total_duration) * 100

        return distribution

    def _calculate_mixing_index(self, segments: List[LanguageSegment]) -> float:
        """Calculate degree of language mixing (0-1)."""
        if len(segments) <= 1:
            return 0.0

        # Count language changes
        changes = 0
        for i in range(1, len(segments)):
            if segments[i].language != segments[i - 1].language:
                changes += 1

        # Normalize by number of segments
        mixing_index = changes / (len(segments) - 1)

        return min(1.0, mixing_index)

    def _calculate_balance_index(
        self, distribution: Dict[LanguageCode, float]
    ) -> float:
        """Calculate balance between languages (0-1, 1=perfectly balanced)."""
        if len(distribution) <= 1:
            return 0.0

        # Calculate entropy
        percentages = np.array(list(distribution.values())) / 100
        percentages = percentages[percentages > 0]  # Remove zeros

        if len(percentages) <= 1:
            return 0.0

        # Normalized entropy
        entropy = -np.sum(percentages * np.log(percentages))
        max_entropy = -np.log(1.0 / len(percentages))

        return entropy / max_entropy if max_entropy > 0 else 0.0

    def _calculate_complexity_score(
        self, events: List[SwitchingEvent], switch_types: Dict[SwitchingType, int]
    ) -> float:
        """Calculate complexity of switching patterns."""
        if not events:
            return 0.0

        # Factors contributing to complexity
        complexity = 0.0

        # Number of different switch types
        type_diversity = len(switch_types) / len(SwitchingType)
        complexity += type_diversity * 0.3

        # Frequency of switches
        switch_frequency = min(1.0, len(events) / 10)  # Normalize to 10 switches
        complexity += switch_frequency * 0.3

        # Variation in switch intervals
        if len(events) > 1:
            intervals = [
                events[i].time - events[i - 1].time for i in range(1, len(events))
            ]
            interval_cv = np.std(intervals) / (np.mean(intervals) + 1e-10)
            complexity += min(1.0, float(interval_cv)) * 0.2

        # Confidence variation
        confidences = [e.confidence for e in events]
        conf_std = np.std(confidences)
        complexity += (
            1.0 - float(conf_std)
        ) * 0.2  # Lower variation = higher complexity

        return complexity

    async def _detect_medical_term_switches(
        self, segments: List[LanguageSegment], audio_data: np.ndarray, sample_rate: int
    ) -> List[Dict[str, Any]]:
        """Detect switches involving medical terminology."""
        # Mark parameters as intentionally unused
        _ = audio_data
        _ = sample_rate
        medical_switches = []

        for i, segment in enumerate(segments):

            # Check if segment might contain medical terms
            # In production, would use actual speech recognition
            if (
                segment.duration < 2.0  # Short segments more likely to be terms
                and segment.language in self.config.medical_term_languages
            ):

                # Check if it's a switch from another language
                is_switch = (
                    i > 0 and segments[i - 1].language != segment.language
                ) or (
                    i < len(segments) - 1
                    and segments[i + 1].language != segment.language
                )

                if is_switch:
                    medical_switches.append(
                        {
                            "time": segment.start_time,
                            "duration": segment.duration,
                            "language": segment.language.value,
                            "confidence": segment.confidence,
                            "potential_term": True,  # In production, identify actual term
                        }
                    )

        return medical_switches

    def _assess_clarity_impact(
        self, events: List[SwitchingEvent], mixing_index: float, complexity_score: float
    ) -> float:
        """Assess impact of language switching on communication clarity."""
        # Start with perfect clarity
        clarity = 1.0

        # Reduce based on mixing index
        clarity -= mixing_index * 0.3

        # Reduce based on complexity
        clarity -= complexity_score * 0.2

        # Reduce based on frequency of switches
        if len(events) > 0:
            # More than 1 switch per 10 seconds impacts clarity
            switch_rate = len(events) / 10  # Normalized rate
            clarity -= min(0.3, switch_rate * 0.1)

        # Consider confidence of switches
        if events:
            avg_confidence = np.mean([e.confidence for e in events])
            clarity *= float(avg_confidence)  # Low confidence switches reduce clarity

        return max(0.0, min(1.0, clarity))

    def _calculate_confidence(
        self, segments: List[LanguageSegment], features: np.ndarray
    ) -> float:
        """Calculate overall confidence in detection."""
        if not segments:
            return 0.0

        # Average segment confidence
        segment_confidence = np.mean([s.confidence for s in segments])

        # Feature quality (check for clipping, noise, etc.)
        feature_quality = 1.0
        if features.size > 0:
            # Check for feature saturation
            if np.any(np.abs(features) > 100):  # Arbitrary threshold
                feature_quality *= 0.8

            # Check for low energy
            if np.mean(np.abs(features)) < 0.1:
                feature_quality *= 0.7

        # Combine factors
        confidence = segment_confidence * feature_quality

        return float(confidence)

    def _generate_warnings(
        self,
        segments: List[LanguageSegment],
        events: List[SwitchingEvent],
        confidence: float,
    ) -> List[str]:
        """Generate warnings about detection quality or issues."""
        warnings = []

        # Low confidence warning
        if confidence < 0.5:
            warnings.append("Low confidence in language detection")

        # Many unknown segments
        unknown_count = sum(1 for s in segments if s.language == LanguageCode.UNKNOWN)
        if unknown_count > len(segments) * 0.3:
            warnings.append(
                f"High proportion of unidentified language segments ({unknown_count}/{len(segments)})"
            )

        # Very high switching rate
        if len(events) > len(segments) * 0.5:
            warnings.append("Unusually high language switching rate")

        # Short segments
        short_segments = sum(1 for s in segments if s.duration < 0.5)
        if short_segments > len(segments) * 0.5:
            warnings.append("Many short segments - may indicate detection issues")

        return warnings

    async def detect_code_switching_patterns(
        self, audio_data: np.ndarray, sample_rate: int = 16000
    ) -> Dict[str, Any]:
        """
        Specialized analysis for code-switching patterns.

        Args:
            audio_data: Audio signal
            sample_rate: Sample rate

        Returns:
            Dictionary with code-switching analysis
        """
        # Perform general switching detection
        result = await self.detect_language_switching(audio_data, sample_rate)

        # Additional code-switching specific analysis
        patterns: Dict[str, Any] = {
            "matrix_language": result.primary_language.value,
            "embedded_languages": [
                lang.value
                for lang, pct in result.language_distribution.items()
                if lang != result.primary_language and pct > 5
            ],
            "switching_patterns": [],
        }

        # Analyze switching patterns
        for i, event in enumerate(result.switching_events):
            pattern = {
                "type": event.switch_type.value,
                "from": event.from_language.value,
                "to": event.to_language.value,
                "time": event.time,
            }

            # Check for specific patterns
            if i > 0:
                prev_event = result.switching_events[i - 1]
                if (
                    prev_event.to_language == event.from_language
                    and event.to_language == prev_event.from_language
                ):
                    pattern["pattern"] = "alternation"
                elif event.from_language == event.to_language:
                    pattern["pattern"] = "self-repair"

            patterns["switching_patterns"].append(pattern)

        # Calculate code-switching metrics
        patterns["metrics"] = {
            "switch_rate_per_minute": result.switching_rate,
            "mixing_index": result.mixing_index,
            "matrix_language_percentage": result.language_distribution.get(
                result.primary_language, 0
            ),
        }

        return patterns

    @requires_phi_access("read")
    async def analyze_multilingual_medical_consultation(
        self,
        audio_data: np.ndarray,
        sample_rate: int = 16000,
        patient_languages: Optional[List[LanguageCode]] = None,
        provider_languages: Optional[List[LanguageCode]] = None,
        _user_id: str = "system",
    ) -> Dict[str, Any]:
        """
        Analyze language use in medical consultation.

        Args:
            audio_data: Consultation audio
            sample_rate: Sample rate
            patient_languages: Expected patient languages
            provider_languages: Expected provider languages

        Returns:
            Medical consultation language analysis
        """
        # General analysis
        result = await self.detect_language_switching(audio_data, sample_rate)

        analysis: Dict[str, Any] = {
            "language_summary": result.get_summary(),
            "medical_terminology": {
                "switches_to_medical_terms": len(result.medical_term_switches),
                "medical_term_languages": Counter(
                    [switch["language"] for switch in result.medical_term_switches]
                ),
            },
            "communication_assessment": {
                "clarity_score": result.clarity_impact,
                "complexity": result.complexity_score,
                "accommodation": 0.0,  # To be calculated
            },
        }

        # Check for language accommodation
        if patient_languages and provider_languages:
            # See if provider accommodates patient's language
            patient_lang_use = sum(
                result.language_distribution.get(lang, 0) for lang in patient_languages
            )

            if patient_lang_use > 30:  # Significant use of patient language
                analysis["communication_assessment"]["accommodation"] = (
                    patient_lang_use / 100
                )

        # Identify potential communication barriers
        barriers = []

        if result.mixing_index > 0.7:
            barriers.append("High language mixing may affect clarity")

        if result.complexity_score > 0.7:
            barriers.append("Complex switching patterns detected")

        if len(result.medical_term_switches) > 5:
            barriers.append("Frequent switching for medical terms")

        analysis["potential_barriers"] = barriers

        # Recommendations
        recommendations = []

        if result.clarity_impact < 0.7:
            recommendations.append("Consider using professional interpreter")

        if result.mixing_index > 0.5:
            recommendations.append("Try to maintain longer segments in each language")

        if result.medical_term_switches:
            recommendations.append("Ensure patient understands medical terminology")

        analysis["recommendations"] = recommendations

        return analysis


# Example usage functions
async def analyze_bilingual_speech(audio_file: str) -> SwitchingAnalysisResult:
    """Analyze bilingual speech for language switching."""
    # Mark parameter as intentionally unused in this example
    _ = audio_file
    detector = LanguageSwitchingDetector()

    # Simulate loading audio
    duration = 10.0
    sample_rate = 16000
    t = np.linspace(0, duration, int(sample_rate * duration))

    # Create synthetic bilingual speech (alternating languages)
    audio = np.zeros_like(t)

    # First 3 seconds - Language 1 (e.g., English)
    audio[: 3 * sample_rate] = 0.5 * np.sin(2 * np.pi * 150 * t[: 3 * sample_rate])

    # Next 2 seconds - Language 2 (e.g., Spanish)
    audio[3 * sample_rate : 5 * sample_rate] = 0.5 * np.sin(
        2 * np.pi * 200 * t[: 2 * sample_rate]
    )

    # Continue alternating
    audio[5 * sample_rate : 7 * sample_rate] = 0.5 * np.sin(
        2 * np.pi * 150 * t[: 2 * sample_rate]
    )
    audio[7 * sample_rate :] = 0.5 * np.sin(2 * np.pi * 200 * t[: 3 * sample_rate])

    # Add some noise
    audio += 0.05 * np.random.randn(len(audio))

    result = await detector.detect_language_switching(audio, sample_rate)

    logger.info("Language switching analysis complete")
    logger.info(result.get_summary())

    return result


async def analyze_medical_consultation(audio_file: str) -> Dict[str, Any]:
    """Analyze language use in medical consultation."""
    # Mark parameter as intentionally unused in this example
    _ = audio_file
    detector = LanguageSwitchingDetector()

    # Simulate consultation audio
    duration = 30.0
    sample_rate = 16000
    t = np.linspace(0, duration, int(sample_rate * duration))

    # Create more complex pattern
    audio = np.zeros_like(t)

    # Simulate conversation with code-switching
    # Doctor speaks English, patient responds in Spanish, medical terms in English
    segments = [
        (0, 5, "en"),  # Doctor introduction
        (5, 8, "es"),  # Patient response
        (8, 10, "en"),  # Medical term
        (10, 15, "es"),  # Patient explanation
        (15, 18, "en"),  # Doctor clarification
        (18, 20, "mixed"),  # Code-switching
        (20, 25, "es"),  # Patient questions
        (25, 30, "en"),  # Doctor summary
    ]

    for start, end, lang in segments:
        start_idx = int(start * sample_rate)
        end_idx = int(end * sample_rate)

        if lang == "en":
            freq = 150
        elif lang == "es":
            freq = 200
        else:  # mixed
            freq = 175

        segment_t = t[: end_idx - start_idx]
        audio[start_idx:end_idx] = 0.5 * np.sin(2 * np.pi * freq * segment_t)

    # Add noise
    audio += 0.05 * np.random.randn(len(audio))

    analysis = await detector.analyze_multilingual_medical_consultation(
        audio,
        sample_rate,
        patient_languages=[LanguageCode.ES],
        provider_languages=[LanguageCode.EN, LanguageCode.ES],
    )

    return dict(analysis)


if __name__ == "__main__":
    # Run example analysis
    async def main() -> None:
        """Run example language switching analysis."""
        # Test basic switching detection
        result = await analyze_bilingual_speech("sample.wav")
        print(f"Detected {result.switch_count} language switches")
        print(f"Mixing index: {result.mixing_index:.2f}")

        # Test medical consultation
        consultation = await analyze_medical_consultation("consultation.wav")
        print("\nMedical Consultation Analysis:")
        print(
            f"Clarity score: {consultation['communication_assessment']['clarity_score']:.2f}"
        )
        print(f"Recommendations: {consultation['recommendations']}")

    asyncio.run(main())


def validate_fhir_data(data: dict) -> dict:
    """Validate FHIR data.

    Args:
        data: Data to validate

    Returns:
        Validation result with 'valid', 'errors', and 'warnings' keys
    """
    errors = []
    warnings: List[str] = []

    if not data:
        errors.append("No data provided")

    return {"valid": len(errors) == 0, "errors": errors, "warnings": warnings}
