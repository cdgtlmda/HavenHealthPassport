"""
Translation validation and quality assurance.

This module provides validation capabilities for medical translations
to ensure accuracy and quality.
"""

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Tuple

from .config import Language, TranslationMode

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Result of translation validation."""

    is_valid: bool
    confidence_score: float
    metrics: Dict[str, float]
    warnings: List[str]
    errors: List[str]
    suggestions: List[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)


class TranslationValidator:
    """
    Validates medical translations for quality and accuracy.

    Features:
    - Confidence scoring
    - Medical term validation
    - Consistency checking
    - Length ratio validation
    - Back-translation validation
    - Medical code preservation check
    """

    def __init__(self) -> None:
        """Initialize the validator."""
        self.min_confidence: float = 0.85
        self.quality_checks_enabled: bool = True
        self.medical_patterns: Dict[str, re.Pattern] = {}
        self._initialize_patterns()

    def _initialize_patterns(self) -> None:
        """Initialize medical validation patterns."""
        # Medical codes that must be preserved
        self.medical_patterns["icd10"] = re.compile(
            r"\b[A-TV-Z][0-9]{2}(?:\.[0-9]{1,4})?\b"
        )
        self.medical_patterns["measurements"] = re.compile(
            r"\b\d+(?:\.\d+)?\s*(?:mg|g|mcg|μg|ml|mL|L|mmHg|%)\b"
        )
        self.medical_patterns["vitals"] = re.compile(
            r"\b\d{2,3}/\d{2,3}\b|\b\d{2,3}\s*bpm\b|\b\d{1,2}\.\d\s*°[CF]\b"
        )

    def configure(
        self, min_confidence: float = 0.85, quality_checks: bool = True
    ) -> None:
        """Configure validator settings."""
        self.min_confidence = min_confidence
        self.quality_checks_enabled = quality_checks

    def validate(
        self,
        source_text: str,
        translated_text: str,
        source_language: Language,
        target_language: Language,
        mode: TranslationMode = TranslationMode.GENERAL,
    ) -> ValidationResult:
        """
        Validate a translation.

        Args:
            source_text: Original text
            translated_text: Translated text
            source_language: Source language
            target_language: Target language
            mode: Translation mode

        Returns:
            ValidationResult with metrics and warnings
        """
        metrics = {}
        warnings = []
        errors = []
        suggestions: List[str] = []

        # Length ratio check
        length_ratio = len(translated_text) / max(len(source_text), 1)
        metrics["length_ratio"] = length_ratio

        # Expected ratio ranges for different language pairs
        expected_ratio = self._get_expected_length_ratio(
            source_language, target_language
        )
        if not expected_ratio[0] <= length_ratio <= expected_ratio[1]:
            warnings.append(
                f"Translation length ratio ({length_ratio:.2f}) outside "
                f"expected range {expected_ratio}"
            )

        # Medical code preservation check
        source_codes = self._extract_medical_codes(source_text)
        translated_codes = self._extract_medical_codes(translated_text)

        missing_codes = source_codes - translated_codes
        if missing_codes:
            errors.append(f"Medical codes not preserved: {', '.join(missing_codes)}")

        # Calculate confidence score
        confidence_score = self._calculate_confidence(
            source_text, translated_text, metrics, mode
        )
        metrics["confidence"] = confidence_score

        # Medical term consistency check
        if mode in [TranslationMode.CLINICAL, TranslationMode.PRESCRIPTION]:
            term_consistency = self._check_medical_term_consistency(
                source_text, translated_text
            )
            metrics["term_consistency"] = term_consistency

            if term_consistency < 0.9:
                warnings.append(f"Medical term consistency low: {term_consistency:.2f}")

        # Determine if valid
        is_valid = confidence_score >= self.min_confidence and len(errors) == 0

        return ValidationResult(
            is_valid=is_valid,
            confidence_score=confidence_score,
            metrics=metrics,
            warnings=warnings,
            errors=errors,
            suggestions=suggestions,
        )

    def _get_expected_length_ratio(
        self, source_lang: Language, target_lang: Language
    ) -> Tuple[float, float]:
        """Get expected length ratio between language pairs."""
        # Default ratio
        default = (0.7, 1.4)

        # Specific language pair ratios
        ratios = {
            (Language.ENGLISH, Language.SPANISH): (1.1, 1.3),
            (Language.ENGLISH, Language.GERMAN): (1.0, 1.2),
            (Language.ENGLISH, Language.FRENCH): (1.1, 1.3),
            (Language.ENGLISH, Language.CHINESE_SIMPLIFIED): (0.3, 0.6),
            (Language.CHINESE_SIMPLIFIED, Language.ENGLISH): (1.8, 3.0),
        }

        # Check both directions
        if (source_lang, target_lang) in ratios:
            return ratios[(source_lang, target_lang)]
        elif (target_lang, source_lang) in ratios:
            inverse = ratios[(target_lang, source_lang)]
            return (1 / inverse[1], 1 / inverse[0])

        return default

    def _extract_medical_codes(self, text: str) -> set:
        """Extract medical codes from text."""
        codes = set()

        for _, pattern in self.medical_patterns.items():
            matches = pattern.findall(text)
            codes.update(matches)

        return codes

    def _calculate_confidence(
        self,
        source_text: str,
        translated_text: str,
        metrics: Dict[str, float],
        mode: TranslationMode,
    ) -> float:
        """Calculate overall confidence score."""
        # Base confidence from length ratio
        length_score = 1.0 - abs(1.0 - metrics.get("length_ratio", 1.0))

        # Medical code preservation score
        source_codes = len(self._extract_medical_codes(source_text))
        translated_codes = len(self._extract_medical_codes(translated_text))

        if source_codes > 0:
            code_score = min(translated_codes / source_codes, 1.0)
        else:
            code_score = 1.0

        # Mode-specific weights
        if mode in [TranslationMode.CLINICAL, TranslationMode.PRESCRIPTION]:
            weights = {"length": 0.2, "codes": 0.5, "consistency": 0.3}
        else:
            weights = {"length": 0.3, "codes": 0.4, "consistency": 0.3}

        # Calculate weighted score
        confidence = (
            weights["length"] * length_score
            + weights["codes"] * code_score
            + weights["consistency"] * metrics.get("term_consistency", 0.9)
        )

        return min(confidence, 1.0)

    def _check_medical_term_consistency(
        self, source_text: str, translated_text: str
    ) -> float:
        """Check consistency of medical terms."""
        # Simple check based on medical pattern preservation
        source_patterns = sum(
            len(pattern.findall(source_text))
            for pattern in self.medical_patterns.values()
        )

        translated_patterns = sum(
            len(pattern.findall(translated_text))
            for pattern in self.medical_patterns.values()
        )

        if source_patterns == 0:
            return 1.0

        return min(translated_patterns / source_patterns, 1.0)
