"""
Confidence Threshold Configuration Module.

This module manages confidence scoring and thresholds for
medical transcription results to ensure accuracy and reliability.

Security Note: This module processes PHI data. Ensure all transcription
results are encrypted at rest and in transit. Access to confidence scores
containing medical terms should be restricted to authorized healthcare
personnel only through role-based access controls.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

import numpy as np

logger = logging.getLogger(__name__)


class ConfidenceLevel(Enum):
    """Confidence levels for transcription results."""

    VERY_HIGH = "very_high"  # > 0.95
    HIGH = "high"  # 0.85 - 0.95
    MEDIUM = "medium"  # 0.70 - 0.85
    LOW = "low"  # 0.50 - 0.70
    VERY_LOW = "very_low"  # < 0.50


class MedicalTermType(Enum):
    """Types of medical terms for specialized thresholds."""

    MEDICATION = "medication"
    DOSAGE = "dosage"
    DIAGNOSIS = "diagnosis"
    PROCEDURE = "procedure"
    ANATOMY = "anatomy"
    SYMPTOM = "symptom"
    ALLERGY = "allergy"
    LAB_VALUE = "lab_value"
    VITAL_SIGN = "vital_sign"


@dataclass
class ConfidenceThreshold:
    """Configuration for confidence thresholds."""

    # General thresholds
    default_threshold: float = 0.70
    accept_threshold: float = 0.85
    review_threshold: float = 0.70
    reject_threshold: float = 0.50
    # Medical term-specific thresholds
    medical_term_thresholds: Dict[MedicalTermType, float] = field(
        default_factory=lambda: {
            MedicalTermType.MEDICATION: 0.95,
            MedicalTermType.DOSAGE: 0.98,
            MedicalTermType.DIAGNOSIS: 0.90,
            MedicalTermType.PROCEDURE: 0.90,
            MedicalTermType.ANATOMY: 0.85,
            MedicalTermType.SYMPTOM: 0.80,
            MedicalTermType.ALLERGY: 0.95,
            MedicalTermType.LAB_VALUE: 0.98,
            MedicalTermType.VITAL_SIGN: 0.95,
        }
    )

    # Context-based adjustments
    enable_context_adjustment: bool = True
    context_boost_factor: float = 0.05  # Boost confidence based on context

    # Acoustic condition adjustments
    noise_penalty_factor: float = 0.10  # Reduce confidence in noisy conditions
    accent_penalty_factor: float = 0.05  # Reduce confidence for strong accents

    # Alternative suggestion settings
    suggest_alternatives: bool = True
    min_alternative_confidence: float = 0.60
    max_alternatives: int = 3

    def get_threshold(self, term_type: Optional[MedicalTermType] = None) -> float:
        """Get the appropriate threshold for a given term type."""
        if term_type and term_type in self.medical_term_thresholds:
            return self.medical_term_thresholds[term_type]
        return self.default_threshold

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "default_threshold": self.default_threshold,
            "accept_threshold": self.accept_threshold,
            "review_threshold": self.review_threshold,
            "reject_threshold": self.reject_threshold,
            "medical_term_thresholds": {
                k.value: v for k, v in self.medical_term_thresholds.items()
            },
            "enable_context_adjustment": self.enable_context_adjustment,
            "context_boost_factor": self.context_boost_factor,
            "noise_penalty_factor": self.noise_penalty_factor,
            "accent_penalty_factor": self.accent_penalty_factor,
            "suggest_alternatives": self.suggest_alternatives,
            "min_alternative_confidence": self.min_alternative_confidence,
            "max_alternatives": self.max_alternatives,
        }


@dataclass
class TranscriptionWord:
    """Represents a single word in the transcription with confidence."""

    text: str
    confidence: float
    start_time: float
    end_time: float
    speaker: Optional[str] = None
    term_type: Optional[MedicalTermType] = None
    alternatives: List[Dict[str, float]] = field(default_factory=list)

    @property
    def confidence_level(self) -> ConfidenceLevel:
        """Get the confidence level category."""
        if self.confidence > 0.95:
            return ConfidenceLevel.VERY_HIGH
        elif self.confidence > 0.85:
            return ConfidenceLevel.HIGH
        elif self.confidence > 0.70:
            return ConfidenceLevel.MEDIUM
        elif self.confidence > 0.50:
            return ConfidenceLevel.LOW
        else:
            return ConfidenceLevel.VERY_LOW

    def needs_review(self, threshold: float) -> bool:
        """Check if this word needs review based on threshold."""
        return self.confidence < threshold


@dataclass
class TranscriptionResult:
    """Complete transcription result with confidence analysis."""

    transcript: str
    words: List[TranscriptionWord]
    overall_confidence: float
    language_code: str

    # Confidence metrics
    average_confidence: float = 0.0
    min_confidence: float = 0.0
    max_confidence: float = 0.0
    confidence_distribution: Dict[ConfidenceLevel, int] = field(default_factory=dict)

    # Review requirements
    words_needing_review: List[TranscriptionWord] = field(default_factory=list)
    critical_terms_flagged: List[TranscriptionWord] = field(default_factory=list)

    # Metadata
    processing_time_ms: float = 0.0
    audio_duration_seconds: float = 0.0
    word_error_rate_estimate: float = 0.0


class ConfidenceManager:
    """Manage confidence scoring and threshold application.

    Handles confidence scoring and threshold application for
    medical transcriptions.
    """

    def __init__(self, config: Optional[ConfidenceThreshold] = None):
        """
        Initialize the confidence manager.

        Args:
            config: Confidence threshold configuration
        """
        self.config = config or ConfidenceThreshold()

        # Medical term patterns for identification
        self.medical_patterns = {
            MedicalTermType.MEDICATION: ["mg", "ml", "tablet", "capsule", "injection"],
            MedicalTermType.DOSAGE: [
                "milligram",
                "milliliter",
                "twice",
                "daily",
                "qid",
                "bid",
            ],
            MedicalTermType.DIAGNOSIS: [
                "diagnosed",
                "diagnosis",
                "condition",
                "syndrome",
            ],
            MedicalTermType.PROCEDURE: ["surgery", "procedure", "operation", "biopsy"],
            MedicalTermType.ANATOMY: ["heart", "lung", "liver", "kidney", "brain"],
            MedicalTermType.SYMPTOM: ["pain", "fever", "cough", "fatigue", "nausea"],
            MedicalTermType.ALLERGY: ["allergy", "allergic", "reaction", "sensitivity"],
            MedicalTermType.LAB_VALUE: [
                "glucose",
                "hemoglobin",
                "cholesterol",
                "creatinine",
            ],
            MedicalTermType.VITAL_SIGN: [
                "blood pressure",
                "temperature",
                "pulse",
                "respiration",
            ],
        }

        logger.info(
            "ConfidenceManager initialized with default threshold=%s",
            self.config.default_threshold,
        )

    def analyze_transcription(
        self,
        raw_transcription: Dict[str, Any],
        noise_metrics: Optional[Dict[str, Any]] = None,
        accent_detected: bool = False,
    ) -> TranscriptionResult:
        """
        Analyze transcription results and apply confidence thresholds.

        Args:
            raw_transcription: Raw transcription from Transcribe
            noise_metrics: Optional noise analysis metrics
            accent_detected: Whether accent was detected

        Returns:
            Analyzed transcription result
        """
        # Extract words from raw transcription
        words = self._extract_words(raw_transcription)

        # Apply confidence adjustments
        adjusted_words = self._apply_confidence_adjustments(
            words, noise_metrics, accent_detected
        )
        # Identify medical terms
        for word in adjusted_words:
            word.term_type = self._identify_medical_term_type(word.text)

        # Flag words needing review
        words_needing_review = []
        critical_terms_flagged = []

        for word in adjusted_words:
            threshold = self.config.get_threshold(word.term_type)

            if word.confidence < threshold:
                words_needing_review.append(word)

                # Check if it's a critical term
                if word.term_type in [
                    MedicalTermType.MEDICATION,
                    MedicalTermType.DOSAGE,
                    MedicalTermType.ALLERGY,
                    MedicalTermType.LAB_VALUE,
                ]:
                    critical_terms_flagged.append(word)

        # Calculate confidence metrics
        confidences = [w.confidence for w in adjusted_words]
        avg_confidence = float(np.mean(confidences)) if confidences else 0.0
        min_confidence = float(np.min(confidences)) if confidences else 0.0
        max_confidence = float(np.max(confidences)) if confidences else 0.0

        # Calculate confidence distribution
        confidence_distribution = self._calculate_confidence_distribution(
            adjusted_words
        )

        # Build transcript text
        transcript = " ".join(w.text for w in adjusted_words)

        # Estimate word error rate
        wer_estimate = self._estimate_word_error_rate(avg_confidence)

        return TranscriptionResult(
            transcript=transcript,
            words=adjusted_words,
            overall_confidence=avg_confidence,
            language_code=raw_transcription.get("language_code", "en-US"),
            average_confidence=avg_confidence,
            min_confidence=min_confidence,
            max_confidence=max_confidence,
            confidence_distribution=confidence_distribution,
            words_needing_review=words_needing_review,
            critical_terms_flagged=critical_terms_flagged,
            word_error_rate_estimate=wer_estimate,
        )

    def _extract_words(
        self, raw_transcription: Dict[str, Any]
    ) -> List[TranscriptionWord]:
        """Extract words from raw transcription data."""
        words = []

        # Handle different transcription formats
        if "results" in raw_transcription:
            for result in raw_transcription["results"]:
                if "alternatives" in result:
                    alt = result["alternatives"][0]
                    if "items" in alt:
                        for item in alt["items"]:
                            if item["type"] == "pronunciation":
                                word = TranscriptionWord(
                                    text=item["content"],
                                    confidence=float(item.get("confidence", 0.0)),
                                    start_time=float(item.get("start_time", 0.0)),
                                    end_time=float(item.get("end_time", 0.0)),
                                    speaker=item.get("speaker_label"),
                                    alternatives=self._extract_alternatives(item),
                                )
                                words.append(word)

        return words

    def _extract_alternatives(self, item: Dict[str, Any]) -> List[Dict[str, float]]:
        """Extract alternative words with confidence scores."""
        alternatives = []

        if "alternatives" in item and len(item["alternatives"]) > 1:
            for alt in item["alternatives"][1 : self.config.max_alternatives + 1]:
                if (
                    float(alt.get("confidence", 0))
                    >= self.config.min_alternative_confidence
                ):
                    alternatives.append(
                        {"text": alt["content"], "confidence": float(alt["confidence"])}
                    )

        return alternatives

    def _apply_confidence_adjustments(
        self,
        words: List[TranscriptionWord],
        noise_metrics: Optional[Dict[str, Any]],
        accent_detected: bool,
    ) -> List[TranscriptionWord]:
        """Apply confidence adjustments based on conditions."""
        adjusted_words = []

        for word in words:
            adjusted_confidence = word.confidence
            # Apply noise penalty
            if noise_metrics and self.config.noise_penalty_factor > 0:
                noise_level = noise_metrics.get("processed_noise_level", "low")
                if noise_level in ["high", "severe"]:
                    adjusted_confidence *= 1 - self.config.noise_penalty_factor

            # Apply accent penalty
            if accent_detected and self.config.accent_penalty_factor > 0:
                adjusted_confidence *= 1 - self.config.accent_penalty_factor

            # Apply context boost (would use more sophisticated NLP in production)
            if self.config.enable_context_adjustment:
                # Simple context check - boost if surrounded by high confidence words
                context_boost = self._calculate_context_boost(words, words.index(word))
                adjusted_confidence = min(1.0, adjusted_confidence + context_boost)

            # Create adjusted word
            adjusted_word = TranscriptionWord(
                text=word.text,
                confidence=adjusted_confidence,
                start_time=word.start_time,
                end_time=word.end_time,
                speaker=word.speaker,
                term_type=word.term_type,
                alternatives=word.alternatives,
            )
            adjusted_words.append(adjusted_word)

        return adjusted_words

    def _calculate_context_boost(
        self, words: List[TranscriptionWord], index: int, window: int = 2
    ) -> float:
        """Calculate confidence boost based on surrounding context."""
        if not self.config.enable_context_adjustment:
            return 0.0

        # Get surrounding words
        start_idx = max(0, index - window)
        end_idx = min(len(words), index + window + 1)

        context_words = words[start_idx:index] + words[index + 1 : end_idx]

        if not context_words:
            return 0.0
        # Calculate average confidence of context
        context_confidence = np.mean([w.confidence for w in context_words])

        # If context is high confidence, provide a boost
        if context_confidence > 0.85:
            return self.config.context_boost_factor

        return 0.0

    def _identify_medical_term_type(self, word: str) -> Optional[MedicalTermType]:
        """Identify if a word is a medical term and its type."""
        word_lower = word.lower()

        # Check each medical pattern
        for term_type, patterns in self.medical_patterns.items():
            for pattern in patterns:
                if pattern in word_lower:
                    return term_type

        # Additional checks could include medical dictionaries, ML models, etc.
        return None

    def _calculate_confidence_distribution(
        self, words: List[TranscriptionWord]
    ) -> Dict[ConfidenceLevel, int]:
        """Calculate distribution of confidence levels."""
        distribution = {level: 0 for level in ConfidenceLevel}

        for word in words:
            distribution[word.confidence_level] += 1

        return distribution

    def _estimate_word_error_rate(self, avg_confidence: float) -> float:
        """Estimate word error rate based on average confidence."""
        # Simple linear approximation
        # In production, this would use validated models
        if avg_confidence > 0.95:
            return 0.02  # 2% WER
        elif avg_confidence > 0.90:
            return 0.05  # 5% WER
        elif avg_confidence > 0.85:
            return 0.08  # 8% WER
        elif avg_confidence > 0.80:
            return 0.12  # 12% WER
        elif avg_confidence > 0.70:
            return 0.20  # 20% WER
        else:
            return 0.30  # 30% WER

    def generate_review_report(self, result: TranscriptionResult) -> Dict[str, Any]:
        """Generate a review report for the transcription."""
        report = {
            "timestamp": datetime.now().isoformat(),
            "overall_quality": self._assess_overall_quality(result),
            "confidence_metrics": {
                "average": result.average_confidence,
                "minimum": result.min_confidence,
                "maximum": result.max_confidence,
                "distribution": {
                    k.value: v for k, v in result.confidence_distribution.items()
                },
            },
            "review_required": {
                "total_words": len(result.words),
                "words_needing_review": len(result.words_needing_review),
                "critical_terms_flagged": len(result.critical_terms_flagged),
                "review_percentage": (
                    len(result.words_needing_review) / len(result.words) * 100
                    if result.words
                    else 0
                ),
            },
            "critical_terms": [
                {
                    "text": word.text,
                    "confidence": word.confidence,
                    "type": word.term_type.value if word.term_type else None,
                    "alternatives": word.alternatives,
                }
                for word in result.critical_terms_flagged
            ],
            "recommendations": self._generate_recommendations(result),
        }

        return report

    def _assess_overall_quality(self, result: TranscriptionResult) -> str:
        """Assess overall transcription quality."""
        if result.average_confidence > 0.90:
            return "excellent"
        elif result.average_confidence > 0.80:
            return "good"
        elif result.average_confidence > 0.70:
            return "fair"
        elif result.average_confidence > 0.60:
            return "poor"
        else:
            return "very_poor"

    def _generate_recommendations(self, result: TranscriptionResult) -> List[str]:
        """Generate recommendations based on transcription analysis."""
        recommendations = []

        # Check overall confidence
        if result.average_confidence < 0.70:
            recommendations.append("Consider re-recording in a quieter environment")

        # Check critical terms
        if len(result.critical_terms_flagged) > 0:
            recommendations.append(
                f"Manual review required for {len(result.critical_terms_flagged)} critical medical terms"
            )

        # Check confidence distribution
        low_conf_percentage = (
            (
                result.confidence_distribution.get(ConfidenceLevel.LOW, 0)
                + result.confidence_distribution.get(ConfidenceLevel.VERY_LOW, 0)
            )
            / len(result.words)
            * 100
            if result.words
            else 0
        )

        if low_conf_percentage > 20:
            recommendations.append("High percentage of low-confidence words detected")

        # Check for specific term types
        med_terms = [
            w
            for w in result.critical_terms_flagged
            if w.term_type == MedicalTermType.MEDICATION
        ]
        if med_terms:
            recommendations.append("Verify all medication names and dosages")

        return recommendations

    def update_thresholds(self, performance_data: Dict[str, Any]) -> None:
        """Update thresholds based on performance data."""
        # This would implement adaptive threshold adjustment
        # based on actual transcription accuracy data

    def export_config(self) -> Dict[str, Any]:
        """Export current configuration."""
        return self.config.to_dict()

    def import_config(self, config_data: Dict[str, Any]) -> None:
        """Import configuration from dictionary."""
        self.config = ConfidenceThreshold(**config_data)
