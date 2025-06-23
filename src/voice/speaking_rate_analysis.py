"""Speaking Rate Analysis Module for Medical Voice Processing.

This module implements comprehensive speaking rate analysis including
words per minute, syllables per second, and medical-specific rate patterns.
"""

# pylint: disable=too-many-lines

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from scipy import signal
from scipy.ndimage import gaussian_filter1d

try:
    import librosa
except ImportError:
    librosa = None

logger = logging.getLogger(__name__)


class SpeakingRateCategory(Enum):
    """Categories of speaking rates."""

    VERY_SLOW = "very_slow"  # < 100 WPM
    SLOW = "slow"  # 100-130 WPM
    NORMAL = "normal"  # 130-170 WPM
    FAST = "fast"  # 170-200 WPM
    VERY_FAST = "very_fast"  # > 200 WPM


class RateVariability(Enum):
    """Speaking rate variability levels."""

    CONSISTENT = "consistent"  # Low variability
    MODERATE = "moderate"  # Normal variability
    VARIABLE = "variable"  # High variability
    ERRATIC = "erratic"  # Very high variability


@dataclass
class SpeakingRateFeatures:
    """Features extracted for speaking rate analysis."""

    # Basic rate metrics
    words_per_minute: float = 0.0
    syllables_per_second: float = 0.0
    phonemes_per_second: float = 0.0

    # Pause metrics
    mean_pause_duration: float = 0.0
    pause_frequency: float = 0.0
    pause_ratio: float = 0.0
    filled_pause_count: int = 0  # "um", "uh", etc.

    # Articulation metrics
    articulation_rate: float = 0.0  # Rate excluding pauses
    speech_rate: float = 0.0  # Rate including pauses

    # Variability metrics
    rate_std: float = 0.0
    rate_cv: float = 0.0  # Coefficient of variation
    rate_range: float = 0.0

    # Rhythm metrics
    rhythm_score: float = 0.0
    isochrony_score: float = 0.0  # Regularity of intervals

    # Temporal patterns
    acceleration_events: int = 0
    deceleration_events: int = 0
    rate_changes: List[float] = field(default_factory=list)

    # Segment-wise rates
    segment_rates: List[float] = field(default_factory=list)
    segment_timestamps: List[float] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "words_per_minute": self.words_per_minute,
            "syllables_per_second": self.syllables_per_second,
            "phonemes_per_second": self.phonemes_per_second,
            "mean_pause_duration": self.mean_pause_duration,
            "pause_frequency": self.pause_frequency,
            "pause_ratio": self.pause_ratio,
            "filled_pause_count": self.filled_pause_count,
            "articulation_rate": self.articulation_rate,
            "speech_rate": self.speech_rate,
            "rate_std": self.rate_std,
            "rate_cv": self.rate_cv,
            "rate_range": self.rate_range,
            "rhythm_score": self.rhythm_score,
            "isochrony_score": self.isochrony_score,
            "acceleration_events": self.acceleration_events,
            "deceleration_events": self.deceleration_events,
        }


@dataclass
class SpeakingRateResult:
    """Result of speaking rate analysis."""

    # Primary metrics
    rate_category: SpeakingRateCategory
    variability: RateVariability
    features: SpeakingRateFeatures

    # Medical indicators
    cognitive_load_indicator: float = 0.0  # 0-1 scale
    anxiety_rate_marker: float = 0.0  # 0-1 scale
    fatigue_indicator: float = 0.0  # 0-1 scale
    neurological_concern: float = 0.0  # 0-1 scale

    # Clinical patterns detected
    pressured_speech: bool = False
    bradylalia: bool = False  # Abnormally slow speech
    tachylalia: bool = False  # Abnormally fast speech
    cluttering_detected: bool = False

    # Detailed analysis
    fluency_score: float = 1.0  # 0-1 scale
    consistency_score: float = 1.0
    naturalness_score: float = 1.0

    # Processing metadata
    audio_duration: float = 0.0
    speech_duration: float = 0.0
    processing_time_ms: float = 0.0
    confidence_score: float = 0.0

    # Warnings and notes
    warnings: List[str] = field(default_factory=list)
    clinical_notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "rate_category": self.rate_category.value,
            "variability": self.variability.value,
            "features": self.features.to_dict(),
            "cognitive_load_indicator": self.cognitive_load_indicator,
            "anxiety_rate_marker": self.anxiety_rate_marker,
            "fatigue_indicator": self.fatigue_indicator,
            "neurological_concern": self.neurological_concern,
            "pressured_speech": self.pressured_speech,
            "bradylalia": self.bradylalia,
            "tachylalia": self.tachylalia,
            "cluttering_detected": self.cluttering_detected,
            "fluency_score": self.fluency_score,
            "consistency_score": self.consistency_score,
            "naturalness_score": self.naturalness_score,
            "audio_duration": self.audio_duration,
            "speech_duration": self.speech_duration,
            "processing_time_ms": self.processing_time_ms,
            "confidence_score": self.confidence_score,
            "warnings": self.warnings,
            "clinical_notes": self.clinical_notes,
        }


@dataclass
class SpeakingRateConfig:
    """Configuration for speaking rate analysis."""

    # Audio processing
    sample_rate: int = 16000
    frame_length_ms: int = 25
    frame_shift_ms: int = 10

    # Rate thresholds (words per minute)
    very_slow_threshold: float = 100
    slow_threshold: float = 130
    normal_min: float = 130
    normal_max: float = 170
    fast_threshold: float = 200

    # Pause detection
    min_pause_duration_ms: float = 200
    max_pause_duration_ms: float = 3000
    pause_energy_threshold: float = 0.02

    # Variability thresholds
    consistent_cv_threshold: float = 0.15
    moderate_cv_threshold: float = 0.30
    variable_cv_threshold: float = 0.45

    # Medical thresholds
    pressured_speech_wpm: float = 200
    bradylalia_wpm: float = 100
    cluttering_acceleration_threshold: float = 1.5

    # Analysis parameters
    segment_duration_s: float = 3.0
    min_speech_duration_s: float = 2.0
    enable_medical_analysis: bool = True
    enable_rhythm_analysis: bool = True

    # Filled pause patterns
    filled_pause_patterns: List[str] = field(
        default_factory=lambda: [
            r"\b(um+|uh+|er+|ah+|hmm+)\b",
            r"\b(like|you know|I mean|sort of|kind of)\b",
        ]
    )


class SpeakingRateAnalyzer:
    """
    Analyzes speaking rate and related temporal features from voice recordings.

    Provides comprehensive analysis including medical indicators and clinical patterns
    relevant for healthcare assessment.
    """

    def __init__(self, config: Optional[SpeakingRateConfig] = None):
        """
        Initialize the speaking rate analyzer.

        Args:
            config: Analysis configuration
        """
        self.config = config or SpeakingRateConfig()

        # Frame parameters
        self.frame_length = int(
            self.config.sample_rate * self.config.frame_length_ms / 1000
        )
        self.frame_shift = int(
            self.config.sample_rate * self.config.frame_shift_ms / 1000
        )

        # Compile filled pause patterns
        self.filled_pause_regex = [
            re.compile(pattern, re.IGNORECASE)
            for pattern in self.config.filled_pause_patterns
        ]

        logger.info(
            "SpeakingRateAnalyzer initialized with sample_rate=%dHz",
            self.config.sample_rate,
        )

    async def analyze_speaking_rate(
        self, audio_data: np.ndarray, transcript: Optional[str] = None
    ) -> SpeakingRateResult:
        """
        Analyze speaking rate from audio data.

        Args:
            audio_data: Audio signal as numpy array
            transcript: Optional transcript for more accurate word counting

        Returns:
            SpeakingRateResult with comprehensive rate analysis
        """
        start_time = datetime.now()

        try:
            # Normalize audio
            audio_data = self._normalize_audio(audio_data)

            # Extract speaking rate features
            features = await self._extract_rate_features(audio_data, transcript)

            # Categorize speaking rate
            rate_category = self._categorize_rate(features.words_per_minute)

            # Analyze variability
            variability = self._analyze_variability(features)

            # Medical analysis
            medical_indicators = await self._analyze_medical_indicators(
                features, variability
            )

            # Detect clinical patterns
            clinical_patterns = self._detect_clinical_patterns(
                features, medical_indicators
            )

            # Calculate quality scores
            quality_scores = self._calculate_quality_scores(features, variability)

            # Generate clinical notes
            clinical_notes = self._generate_clinical_notes(
                features, rate_category, variability, clinical_patterns
            )

            # Calculate confidence
            confidence = self._calculate_confidence(features, transcript is not None)

            # Processing time
            processing_time = (datetime.now() - start_time).total_seconds() * 1000

            return SpeakingRateResult(
                rate_category=rate_category,
                variability=variability,
                features=features,
                cognitive_load_indicator=medical_indicators.get("cognitive_load", 0.0),
                anxiety_rate_marker=medical_indicators.get("anxiety", 0.0),
                fatigue_indicator=medical_indicators.get("fatigue", 0.0),
                neurological_concern=medical_indicators.get("neurological", 0.0),
                pressured_speech=clinical_patterns.get("pressured_speech", False),
                bradylalia=clinical_patterns.get("bradylalia", False),
                tachylalia=clinical_patterns.get("tachylalia", False),
                cluttering_detected=clinical_patterns.get("cluttering", False),
                fluency_score=quality_scores.get("fluency", 1.0),
                consistency_score=quality_scores.get("consistency", 1.0),
                naturalness_score=quality_scores.get("naturalness", 1.0),
                audio_duration=len(audio_data) / self.config.sample_rate,
                speech_duration=features.speech_rate
                * len(audio_data)
                / self.config.sample_rate,
                processing_time_ms=processing_time,
                confidence_score=confidence,
                clinical_notes=clinical_notes,
            )

        except Exception as e:
            logger.error("Error in speaking rate analysis: %s", str(e), exc_info=True)
            raise

    def _normalize_audio(self, audio_data: np.ndarray) -> np.ndarray:
        """Normalize audio to [-1, 1] range."""
        max_val = np.max(np.abs(audio_data))
        if max_val > 0:
            normalized: np.ndarray = (audio_data / max_val).astype(audio_data.dtype)
            return normalized
        return audio_data

    async def _extract_rate_features(
        self, audio_data: np.ndarray, transcript: Optional[str] = None
    ) -> SpeakingRateFeatures:
        """Extract speaking rate features from audio."""
        features = SpeakingRateFeatures()

        # Detect speech segments and pauses
        speech_segments, pause_segments = self._detect_speech_pauses(audio_data)

        # Calculate basic timing
        total_duration = len(audio_data) / self.config.sample_rate
        speech_duration = sum(seg[1] - seg[0] for seg in speech_segments)
        pause_duration = sum(seg[1] - seg[0] for seg in pause_segments)

        # Pause metrics
        if len(pause_segments) > 0:
            pause_durations = [(seg[1] - seg[0]) for seg in pause_segments]
            features.mean_pause_duration = float(np.mean(pause_durations))
            features.pause_frequency = len(pause_segments) / total_duration

        features.pause_ratio = (
            pause_duration / total_duration if total_duration > 0 else 0
        )

        # Estimate speech units
        if transcript:
            # Use transcript for accurate word count
            words = self._count_words(transcript)
            features.filled_pause_count = self._count_filled_pauses(transcript)
        else:
            # Estimate from audio features
            words = self._estimate_word_count(audio_data, speech_segments)
            features.filled_pause_count = 0

        # Calculate rates
        if speech_duration > 0:
            features.words_per_minute = (words / speech_duration) * 60
            features.articulation_rate = features.words_per_minute

        if total_duration > 0:
            features.speech_rate = (words / total_duration) * 60

        # Estimate syllables and phonemes
        syllables = self._estimate_syllable_count(audio_data, speech_segments)
        features.syllables_per_second = (
            syllables / speech_duration if speech_duration > 0 else 0
        )
        features.phonemes_per_second = (
            features.syllables_per_second * 2.5
        )  # Rough estimate

        # Analyze rate variability across segments
        segment_rates = await self._analyze_segment_rates(audio_data, speech_segments)
        features.segment_rates = segment_rates

        if len(segment_rates) > 1:
            features.rate_std = float(np.std(segment_rates))
            features.rate_cv = (
                features.rate_std / float(np.mean(segment_rates))
                if float(np.mean(segment_rates)) > 0
                else 0
            )
            features.rate_range = max(segment_rates) - min(segment_rates)

            # Detect rate changes
            rate_changes = np.diff(segment_rates)
            features.rate_changes = rate_changes.tolist()
            features.acceleration_events = sum(
                1 for r in rate_changes if r > 0.2 * np.mean(segment_rates)
            )
            features.deceleration_events = sum(
                1 for r in rate_changes if r < -0.2 * np.mean(segment_rates)
            )

        # Rhythm analysis
        if self.config.enable_rhythm_analysis:
            features.rhythm_score = self._calculate_rhythm_score(speech_segments)
            features.isochrony_score = self._calculate_isochrony(speech_segments)

        return features

    def _detect_speech_pauses(
        self, audio_data: np.ndarray
    ) -> Tuple[List[Tuple[float, float]], List[Tuple[float, float]]]:
        """Detect speech and pause segments in audio."""
        # Calculate energy
        energy = librosa.feature.rms(
            y=audio_data, frame_length=self.frame_length, hop_length=self.frame_shift
        )[0]

        # Dynamic threshold
        energy_threshold = np.mean(energy) * self.config.pause_energy_threshold

        # Find speech/pause boundaries
        is_speech = energy > energy_threshold

        # Convert to time segments
        speech_segments = []
        pause_segments = []

        in_speech = False
        segment_start = 0.0

        for i, frame_is_speech in enumerate(is_speech):
            time = i * self.frame_shift / self.config.sample_rate

            if frame_is_speech and not in_speech:
                # Start of speech
                if in_speech is False and i > 0:
                    # End previous pause
                    pause_segments.append((segment_start, time))
                segment_start = time
                in_speech = True
            elif not frame_is_speech and in_speech:
                # Start of pause
                speech_segments.append((segment_start, time))
                segment_start = time
                in_speech = False

        # Handle final segment
        final_time = len(audio_data) / self.config.sample_rate
        if in_speech:
            speech_segments.append((segment_start, final_time))
        else:
            pause_segments.append((segment_start, final_time))

        # Filter out very short segments
        min_duration = self.config.min_pause_duration_ms / 1000
        pause_segments = [
            (start, end) for start, end in pause_segments if end - start >= min_duration
        ]

        return speech_segments, pause_segments

    def _count_words(self, transcript: str) -> int:
        """Count words in transcript."""
        # Remove punctuation and split
        words = re.findall(r"\b\w+\b", transcript.lower())
        return len(words)

    def _count_filled_pauses(self, transcript: str) -> int:
        """Count filled pauses in transcript."""
        count = 0
        for pattern in self.filled_pause_regex:
            matches = pattern.findall(transcript)
            count += len(matches)
        return count

    def _estimate_word_count(
        self, audio_data: np.ndarray, speech_segments: List[Tuple[float, float]]
    ) -> int:
        """Estimate word count from audio features."""
        # Use syllable detection as proxy
        total_syllables = 0

        for start, end in speech_segments:
            start_sample = int(start * self.config.sample_rate)
            end_sample = int(end * self.config.sample_rate)
            segment = audio_data[start_sample:end_sample]

            # Detect syllables using energy peaks
            energy = librosa.feature.rms(y=segment, hop_length=self.frame_shift)[0]
            peaks, _ = signal.find_peaks(energy, height=np.mean(energy))
            total_syllables += len(peaks)

        # Approximate words (average 1.5 syllables per word in English)
        return int(total_syllables / 1.5)

    def _estimate_syllable_count(
        self, audio_data: np.ndarray, speech_segments: List[Tuple[float, float]]
    ) -> int:
        """Estimate syllable count from audio."""
        total_syllables = 0

        for start, end in speech_segments:
            start_sample = int(start * self.config.sample_rate)
            end_sample = int(end * self.config.sample_rate)
            segment = audio_data[start_sample:end_sample]

            # Use intensity peaks as syllable nuclei
            intensity = librosa.feature.rms(y=segment, hop_length=self.frame_shift)[0]

            # Smooth to reduce noise
            intensity_smooth = gaussian_filter1d(intensity, sigma=2)

            # Find peaks
            peaks, _ = signal.find_peaks(
                intensity_smooth,
                height=np.mean(intensity_smooth) * 0.7,
                distance=int(
                    0.08 * self.config.sample_rate / self.frame_shift
                ),  # Min 80ms between syllables
            )

            total_syllables += len(peaks)

        return total_syllables

    async def _analyze_segment_rates(
        self, audio_data: np.ndarray, speech_segments: List[Tuple[float, float]]
    ) -> List[float]:
        """Analyze speaking rate for each segment."""
        segment_rates = []
        segment_duration = self.config.segment_duration_s

        for start, end in speech_segments:
            if end - start < segment_duration / 2:
                continue  # Skip very short segments

            start_sample = int(start * self.config.sample_rate)
            end_sample = int(end * self.config.sample_rate)
            segment = audio_data[start_sample:end_sample]

            # Estimate syllables in segment
            syllables = self._estimate_syllable_count(segment, [(0, end - start)])
            duration = end - start

            if duration > 0:
                # Convert to words per minute
                syllable_rate = syllables / duration
                word_rate = (syllable_rate / 1.5) * 60  # Approximate conversion
                segment_rates.append(word_rate)

        return segment_rates

    def _calculate_rhythm_score(
        self, speech_segments: List[Tuple[float, float]]
    ) -> float:
        """Calculate rhythm regularity score."""
        if len(speech_segments) < 2:
            return 1.0

        # Calculate inter-segment intervals
        intervals = []
        for i in range(1, len(speech_segments)):
            interval = speech_segments[i][0] - speech_segments[i - 1][1]
            intervals.append(interval)

        if not intervals:
            return 1.0

        # Calculate regularity (lower CV = more regular)
        mean_interval = np.mean(intervals)
        std_interval = np.std(intervals)

        if mean_interval > 0:
            cv = std_interval / mean_interval
            # Convert to 0-1 score (1 = perfectly regular)
            rhythm_score = max(0, 1 - float(cv))
            return float(rhythm_score)

        return 1.0

    def _calculate_isochrony(self, speech_segments: List[Tuple[float, float]]) -> float:
        """Calculate isochrony (temporal regularity) score."""
        if len(speech_segments) < 3:
            return 1.0

        # Calculate durations
        durations = [end - start for start, end in speech_segments]

        # Pairwise variability index
        pvi_values = []
        for i in range(len(durations) - 1):
            if durations[i] + durations[i + 1] > 0:
                pvi = (
                    200
                    * abs(durations[i] - durations[i + 1])
                    / (durations[i] + durations[i + 1])
                )
                pvi_values.append(pvi)

        if pvi_values:
            mean_pvi = np.mean(pvi_values)
            # Convert to 0-1 score (lower PVI = more isochronous)
            isochrony_score = max(0, 1 - float(mean_pvi) / 100)
            return float(isochrony_score)

        return 1.0

    def _categorize_rate(self, wpm: float) -> SpeakingRateCategory:
        """Categorize speaking rate based on words per minute."""
        if wpm < self.config.very_slow_threshold:
            return SpeakingRateCategory.VERY_SLOW
        elif wpm < self.config.slow_threshold:
            return SpeakingRateCategory.SLOW
        elif wpm <= self.config.normal_max:
            return SpeakingRateCategory.NORMAL
        elif wpm <= self.config.fast_threshold:
            return SpeakingRateCategory.FAST
        else:
            return SpeakingRateCategory.VERY_FAST

    def _analyze_variability(self, features: SpeakingRateFeatures) -> RateVariability:
        """Analyze speaking rate variability."""
        if features.rate_cv < self.config.consistent_cv_threshold:
            return RateVariability.CONSISTENT
        elif features.rate_cv < self.config.moderate_cv_threshold:
            return RateVariability.MODERATE
        elif features.rate_cv < self.config.variable_cv_threshold:
            return RateVariability.VARIABLE
        else:
            return RateVariability.ERRATIC

    async def _analyze_medical_indicators(
        self, features: SpeakingRateFeatures, variability: RateVariability
    ) -> Dict[str, float]:
        """Analyze medical indicators from speaking rate patterns."""
        indicators = {}

        # Cognitive load indicator
        cognitive_features = [
            features.pause_frequency / 10 if features.pause_frequency > 5 else 0,
            features.filled_pause_count / 20 if features.filled_pause_count > 0 else 0,
            features.rate_cv if variability == RateVariability.VARIABLE else 0,
            1 - features.fluency_score if hasattr(features, "fluency_score") else 0,
        ]
        indicators["cognitive_load"] = np.clip(np.mean(cognitive_features), 0, 1)

        # Anxiety rate marker
        anxiety_features = []
        if features.words_per_minute > self.config.fast_threshold:
            anxiety_features.append(
                (features.words_per_minute - self.config.fast_threshold) / 50
            )
        if features.acceleration_events > 3:
            anxiety_features.append(features.acceleration_events / 10)
        if features.pause_ratio < 0.1:
            anxiety_features.append(1 - features.pause_ratio * 10)

        indicators["anxiety"] = np.clip(
            np.mean(anxiety_features) if anxiety_features else 0, 0, 1
        )

        # Fatigue indicator
        fatigue_features = []
        if features.words_per_minute < self.config.slow_threshold:
            fatigue_features.append(
                (self.config.slow_threshold - features.words_per_minute) / 30
            )
        if features.mean_pause_duration > 1.0:
            fatigue_features.append(features.mean_pause_duration / 3)
        if features.deceleration_events > features.acceleration_events * 2:
            fatigue_features.append(0.5)

        indicators["fatigue"] = np.clip(
            np.mean(fatigue_features) if fatigue_features else 0, 0, 1
        )

        # Neurological concern indicator
        neuro_features = []
        if variability == RateVariability.ERRATIC:
            neuro_features.append(0.7)
        if features.rhythm_score < 0.3:
            neuro_features.append(1 - features.rhythm_score)
        if abs(features.words_per_minute - 150) > 100:  # Very far from normal
            neuro_features.append(0.5)

        indicators["neurological"] = np.clip(
            np.mean(neuro_features) if neuro_features else 0, 0, 1
        )

        return indicators

    def _detect_clinical_patterns(
        self, features: SpeakingRateFeatures, medical_indicators: Dict[str, float]
    ) -> Dict[str, bool]:
        """Detect specific clinical speech patterns."""
        patterns = {}

        # Pressured speech
        patterns["pressured_speech"] = (
            features.words_per_minute > self.config.pressured_speech_wpm
            and features.pause_ratio < 0.15
            and medical_indicators.get("anxiety", 0) > 0.6
        )

        # Bradylalia (pathologically slow speech)
        patterns["bradylalia"] = (
            features.words_per_minute < self.config.bradylalia_wpm
            and features.mean_pause_duration > 1.5
            and medical_indicators.get("neurological", 0) > 0.5
        )

        # Tachylalia (pathologically fast speech)
        patterns["tachylalia"] = (
            features.words_per_minute > self.config.pressured_speech_wpm
            and features.articulation_rate > features.speech_rate * 1.3
        )

        # Cluttering detection
        cluttering_indicators = [
            features.rate_cv > 0.4,
            features.acceleration_events > 5,
            features.rhythm_score < 0.4,
            features.filled_pause_count > 10,
        ]
        patterns["cluttering"] = sum(cluttering_indicators) >= 3

        return patterns

    def _calculate_quality_scores(
        self, features: SpeakingRateFeatures, variability: RateVariability
    ) -> Dict[str, float]:
        """Calculate speech quality scores."""
        scores = {}

        # Fluency score
        fluency_factors = []

        # Pause pattern contribution
        if features.pause_ratio > 0.05 and features.pause_ratio < 0.4:
            fluency_factors.append(1.0)
        else:
            fluency_factors.append(0.5)

        # Filled pause contribution
        if features.filled_pause_count < 5:
            fluency_factors.append(1.0)
        elif features.filled_pause_count < 10:
            fluency_factors.append(0.7)
        else:
            fluency_factors.append(0.4)

        # Rate consistency contribution
        if variability in [RateVariability.CONSISTENT, RateVariability.MODERATE]:
            fluency_factors.append(0.9)
        else:
            fluency_factors.append(0.6)

        scores["fluency"] = float(np.mean(fluency_factors))

        # Consistency score
        if variability == RateVariability.CONSISTENT:
            scores["consistency"] = 1.0
        elif variability == RateVariability.MODERATE:
            scores["consistency"] = 0.8
        elif variability == RateVariability.VARIABLE:
            scores["consistency"] = 0.5
        else:
            scores["consistency"] = 0.3

        # Naturalness score
        naturalness_factors = []

        # Rate appropriateness
        if (
            features.words_per_minute >= self.config.normal_min
            and features.words_per_minute <= self.config.normal_max
        ):
            naturalness_factors.append(1.0)
        else:
            deviation = min(
                abs(features.words_per_minute - self.config.normal_min),
                abs(features.words_per_minute - self.config.normal_max),
            )
            naturalness_factors.append(max(0.3, 1 - deviation / 100))

        # Rhythm contribution
        naturalness_factors.append(features.rhythm_score)

        # Isochrony contribution
        naturalness_factors.append(features.isochrony_score)

        scores["naturalness"] = float(np.mean(naturalness_factors))

        return scores

    def _generate_clinical_notes(
        self,
        features: SpeakingRateFeatures,
        rate_category: SpeakingRateCategory,
        variability: RateVariability,
        clinical_patterns: Dict[str, bool],
    ) -> List[str]:
        """Generate clinical notes based on speaking rate analysis."""
        notes = []

        # Rate category notes
        if rate_category == SpeakingRateCategory.VERY_SLOW:
            notes.append(
                f"Very slow speaking rate detected ({features.words_per_minute:.0f} WPM)"
            )
        elif rate_category == SpeakingRateCategory.VERY_FAST:
            notes.append(
                f"Very fast speaking rate detected ({features.words_per_minute:.0f} WPM)"
            )

        # Variability notes
        if variability == RateVariability.ERRATIC:
            notes.append("Highly erratic speaking rate variability observed")
        elif variability == RateVariability.VARIABLE:
            notes.append("Significant speaking rate variability detected")

        # Clinical pattern notes
        if clinical_patterns.get("pressured_speech"):
            notes.append(
                "Pressured speech pattern detected - may indicate anxiety or manic state"
            )

        if clinical_patterns.get("bradylalia"):
            notes.append(
                "Bradylalia detected - abnormally slow speech requiring clinical attention"
            )

        if clinical_patterns.get("tachylalia"):
            notes.append("Tachylalia detected - abnormally rapid speech pattern")

        if clinical_patterns.get("cluttering"):
            notes.append(
                "Speech cluttering pattern detected - irregular rate and rhythm"
            )

        # Pause pattern notes
        if features.pause_ratio > 0.5:
            notes.append("Excessive pausing detected in speech")
        elif features.pause_ratio < 0.05:
            notes.append("Minimal pausing - continuous speech pattern")

        # Filled pause notes
        if features.filled_pause_count > 15:
            notes.append(
                f"High frequency of filled pauses ({features.filled_pause_count} detected)"
            )

        # Rhythm disturbances
        if features.rhythm_score < 0.3:
            notes.append("Poor speech rhythm detected")

        # Rate changes
        if features.acceleration_events > 5:
            notes.append(
                f"Frequent speech accelerations ({features.acceleration_events} events)"
            )

        if features.deceleration_events > 5:
            notes.append(
                f"Frequent speech decelerations ({features.deceleration_events} events)"
            )

        return notes

    def _calculate_confidence(
        self, features: SpeakingRateFeatures, has_transcript: bool
    ) -> float:
        """Calculate confidence in the analysis results."""
        confidence_factors = []

        # Transcript availability
        confidence_factors.append(1.0 if has_transcript else 0.7)

        # Speech duration adequacy
        if features.speech_rate > 0:
            speech_duration = features.words_per_minute / features.speech_rate * 60
            if speech_duration >= self.config.min_speech_duration_s:
                confidence_factors.append(1.0)
            else:
                confidence_factors.append(
                    speech_duration / self.config.min_speech_duration_s
                )

        # Feature reliability
        if len(features.segment_rates) >= 3:
            confidence_factors.append(1.0)
        elif len(features.segment_rates) >= 1:
            confidence_factors.append(0.7)
        else:
            confidence_factors.append(0.4)

        # Consistency of measurements
        if features.rate_cv < 0.5:
            confidence_factors.append(0.9)
        else:
            confidence_factors.append(0.6)

        return float(np.mean(confidence_factors))

    def get_rate_summary(self, result: SpeakingRateResult) -> Dict[str, Any]:
        """Create a summary of speaking rate analysis."""
        summary: Dict[str, Any] = {
            "rate_category": result.rate_category.value,
            "words_per_minute": round(result.features.words_per_minute, 1),
            "variability": result.variability.value,
            "key_findings": [],
            "recommendations": [],
        }

        # Key findings
        if result.rate_category in [
            SpeakingRateCategory.VERY_SLOW,
            SpeakingRateCategory.VERY_FAST,
        ]:
            summary["key_findings"].append(
                f"Abnormal speaking rate: {result.rate_category.value}"
            )

        if result.variability == RateVariability.ERRATIC:
            summary["key_findings"].append("Highly variable speaking rate")

        if any(
            [
                result.pressured_speech,
                result.bradylalia,
                result.tachylalia,
                result.cluttering_detected,
            ]
        ):
            summary["key_findings"].append("Clinical speech pattern detected")

        # Recommendations
        if result.cognitive_load_indicator > 0.7:
            summary["recommendations"].append("Consider cognitive load assessment")

        if result.anxiety_rate_marker > 0.7:
            summary["recommendations"].append(
                "Evaluate for anxiety-related speech patterns"
            )

        if result.neurological_concern > 0.6:
            summary["recommendations"].append(
                "Neurological evaluation may be warranted"
            )

        return summary

    async def analyze_multiple_samples(
        self, audio_samples: List[np.ndarray], transcripts: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Analyze multiple audio samples to create a comprehensive profile."""
        results = []

        if transcripts and len(transcripts) != len(audio_samples):
            logger.warning("Transcript count doesn't match audio sample count")
            transcripts = None

        for i, audio in enumerate(audio_samples):
            transcript = transcripts[i] if transcripts else None
            result = await self.analyze_speaking_rate(audio, transcript)
            results.append(result)

        # Aggregate results
        avg_wpm = np.mean([r.features.words_per_minute for r in results])
        wpm_std = np.std([r.features.words_per_minute for r in results])

        # Consistency across samples
        rate_categories = [r.rate_category for r in results]
        category_consistency = len(set(rate_categories)) == 1

        # Medical indicators
        avg_cognitive_load = np.mean([r.cognitive_load_indicator for r in results])
        avg_anxiety = np.mean([r.anxiety_rate_marker for r in results])
        avg_fatigue = np.mean([r.fatigue_indicator for r in results])
        avg_neurological = np.mean([r.neurological_concern for r in results])

        # Clinical patterns
        clinical_pattern_counts = {
            "pressured_speech": sum(1 for r in results if r.pressured_speech),
            "bradylalia": sum(1 for r in results if r.bradylalia),
            "tachylalia": sum(1 for r in results if r.tachylalia),
            "cluttering": sum(1 for r in results if r.cluttering_detected),
        }

        profile = {
            "sample_count": len(results),
            "average_wpm": round(avg_wpm, 1),
            "wpm_standard_deviation": round(wpm_std, 1),
            "category_consistency": category_consistency,
            "dominant_category": max(
                set(rate_categories), key=rate_categories.count
            ).value,
            "medical_indicators": {
                "cognitive_load": round(avg_cognitive_load, 2),
                "anxiety": round(avg_anxiety, 2),
                "fatigue": round(avg_fatigue, 2),
                "neurological": round(avg_neurological, 2),
            },
            "clinical_patterns": clinical_pattern_counts,
            "confidence": round(np.mean([r.confidence_score for r in results]), 2),
        }

        return profile
