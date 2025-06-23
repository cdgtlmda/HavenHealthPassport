"""Medical Translation Accuracy Checks.

This module implements comprehensive accuracy checks for medical translations,
including automated scoring, pattern detection, and quality metrics.
"""

import difflib
import re
from collections import Counter
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from src.healthcare.hipaa_access_control import AccessLevel, require_phi_access
from src.services.encryption_service import EncryptionService
from src.translation.drug_name_mapper import drug_mapper
from src.translation.icd10_translations import icd10_manager
from src.translation.medical_glossary import MedicalGlossaryService
from src.translation.snomed_translations import snomed_manager
from src.utils.logging import get_logger

logger = get_logger(__name__)


class AccuracyMetric(str, Enum):
    """Types of accuracy metrics."""

    TERM_ACCURACY = "term_accuracy"
    SEMANTIC_SIMILARITY = "semantic_similarity"
    COMPLETENESS = "completeness"
    CONSISTENCY = "consistency"
    FLUENCY = "fluency"
    CLINICAL_CORRECTNESS = "clinical_correctness"


@dataclass
class AccuracyScore:
    """Detailed accuracy scoring."""

    overall_score: float  # 0-100
    metrics: Dict[AccuracyMetric, float]
    confidence: float  # 0-1
    details: Dict[str, Any]


class MedicalAccuracyChecker:
    """Performs accuracy checks on medical translations."""

    # Weights for different metrics
    METRIC_WEIGHTS = {
        AccuracyMetric.TERM_ACCURACY: 0.30,
        AccuracyMetric.SEMANTIC_SIMILARITY: 0.20,
        AccuracyMetric.COMPLETENESS: 0.20,
        AccuracyMetric.CONSISTENCY: 0.15,
        AccuracyMetric.FLUENCY: 0.10,
        AccuracyMetric.CLINICAL_CORRECTNESS: 0.05,
    }

    # Critical information patterns
    CRITICAL_PATTERNS = {
        "dosage": [
            r"\b(\d+(?:\.\d+)?)\s*(mg|g|ml|mcg|unit)s?\b",
            r"\b(once|twice|three times|four times)\s+(daily|a day|per day)\b",
            r"\bevery\s+(\d+)\s+hours?\b",
        ],
        "duration": [
            r"\bfor\s+(\d+)\s+(days?|weeks?|months?)\b",
            r"\b(\d+)\s+(days?|weeks?|months?)\s+course\b",
        ],
        "warnings": [
            r"\b(do not|must not|should not|avoid)\b",
            r"\b(allergic|allergy|reaction)\b",
            r"\b(overdose|toxic|dangerous)\b",
        ],
        "instructions": [
            r"\b(before|after|with|without)\s+meals?\b",
            r"\b(morning|evening|night|bedtime)\b",
            r"\b(empty stomach|with food)\b",
        ],
    }

    def __init__(
        self, glossary_service: MedicalGlossaryService, enable_ml_scoring: bool = False
    ):
        """Initialize accuracy checker."""
        self.glossary = glossary_service
        self.enable_ml = enable_ml_scoring
        self.encryption_service = EncryptionService()
        self._init_reference_data()

    def _init_reference_data(self) -> None:
        """Initialize reference data for accuracy checking."""
        # Build term frequency maps
        self.term_frequencies: Dict[str, Dict[str, int]] = {}

        # Common medical phrase patterns
        self.medical_phrases = {
            "en": {
                "take medication": ["take", "medication"],
                "side effects": ["side", "effects"],
                "allergic reaction": ["allergic", "reaction"],
                "blood pressure": ["blood", "pressure"],
                "heart rate": ["heart", "rate"],
            }
        }

    @require_phi_access(AccessLevel.READ)
    def check_accuracy(
        self,
        source_text: str,
        translated_text: str,
        source_lang: str,
        target_lang: str,
        reference_translation: Optional[str] = None,
    ) -> AccuracyScore:
        """
        Perform comprehensive accuracy check.

        Args:
            source_text: Original text
            translated_text: Translation to check
            source_lang: Source language code
            target_lang: Target language code
            reference_translation: Optional reference translation

        Returns:
            Detailed accuracy score
        """
        metrics: Dict[AccuracyMetric, float] = {}
        details: Dict[str, Any] = {}

        # Check term accuracy
        term_score, term_details = self._check_term_accuracy(
            source_text, translated_text, source_lang, target_lang
        )
        metrics[AccuracyMetric.TERM_ACCURACY] = term_score
        details["term_accuracy"] = term_details

        # Check semantic similarity
        if reference_translation:
            semantic_score = self._check_semantic_similarity(
                translated_text, reference_translation
            )
        else:
            semantic_score = self._estimate_semantic_similarity(
                source_text, translated_text, source_lang, target_lang
            )
        metrics[AccuracyMetric.SEMANTIC_SIMILARITY] = semantic_score

        # Check completeness
        completeness_score, missing_info = self._check_completeness(
            source_text, translated_text
        )
        metrics[AccuracyMetric.COMPLETENESS] = completeness_score
        if missing_info:
            details["missing_information"] = missing_info

        # Check consistency
        consistency_score = self._check_consistency(translated_text, target_lang)
        metrics[AccuracyMetric.CONSISTENCY] = consistency_score

        # Check fluency
        fluency_score = self._check_fluency(translated_text, target_lang)
        metrics[AccuracyMetric.FLUENCY] = fluency_score

        # Check clinical correctness
        clinical_score, clinical_issues = self._check_clinical_correctness(
            source_text, translated_text, source_lang, target_lang
        )
        metrics[AccuracyMetric.CLINICAL_CORRECTNESS] = clinical_score
        if clinical_issues:
            details["clinical_issues"] = clinical_issues

        # Calculate overall score
        overall_score = self._calculate_overall_score(metrics)

        # Calculate confidence
        confidence = self._calculate_confidence(metrics, details)

        return AccuracyScore(
            overall_score=overall_score,
            metrics=metrics,
            confidence=confidence,
            details=details,
        )

    def _check_term_accuracy(
        self, source: str, translated: str, source_lang: str, target_lang: str
    ) -> Tuple[float, Dict[str, Any]]:
        """Check accuracy of medical term translations."""
        details: Dict[str, Any] = {
            "total_terms": 0,
            "correctly_translated": 0,
            "missing_terms": [],
            "incorrect_terms": [],
        }

        # Extract medical terms from source
        source_terms = self._extract_all_medical_terms(source, source_lang)
        details["total_terms"] = len(source_terms)

        if not source_terms:
            return 100.0, details

        correctly_translated = 0

        for term_info in source_terms:
            term = term_info["term"]
            term_type = term_info["type"]

            # Get expected translation based on term type
            expected_translation = None

            if term_type == "glossary":
                expected_translation = self.glossary.get_term_translation(
                    term, target_lang, source_lang
                )
            elif term_type == "icd10":
                expected_translation = icd10_manager.get_translation(term, target_lang)
            elif term_type == "snomed":
                expected_translation = snomed_manager.get_translation(term, target_lang)
            elif term_type == "drug":
                expected_translation = drug_mapper.get_translation(term, target_lang)

            if expected_translation:
                if self._term_present_in_translation(expected_translation, translated):
                    correctly_translated += 1
                else:
                    incorrect_terms = details["incorrect_terms"]
                    if isinstance(incorrect_terms, list):
                        incorrect_terms.append(
                            {
                                "term": term,
                                "expected": expected_translation,
                                "type": term_type,
                            }
                        )
            else:
                # Check if term appears untranslated (which might be correct)
                if term.lower() in translated.lower():
                    correctly_translated += 1
                else:
                    missing_terms = details["missing_terms"]
                    if isinstance(missing_terms, list):
                        missing_terms.append(term)

        details["correctly_translated"] = correctly_translated

        # Calculate score
        total_terms = details["total_terms"]
        if isinstance(total_terms, int) and total_terms > 0:
            score = (correctly_translated / total_terms) * 100
        else:
            score = 100.0

        return score, details

    def _check_semantic_similarity(self, translated: str, reference: str) -> float:
        """Check semantic similarity with reference translation."""
        # Use difflib for basic similarity
        # In production, would use advanced NLP models
        similarity = difflib.SequenceMatcher(
            None, translated.lower(), reference.lower()
        ).ratio()

        return similarity * 100

    def _estimate_semantic_similarity(
        self, source: str, translated: str, _source_lang: str, _target_lang: str
    ) -> float:
        """Estimate semantic similarity without reference."""
        # Check if key information is preserved
        score = 100.0

        # Extract key information from source
        source_numbers = re.findall(r"\b\d+(?:\.\d+)?\b", source)
        translated_numbers = re.findall(r"\b\d+(?:\.\d+)?\b", translated)

        # Numbers should be preserved
        if len(source_numbers) != len(translated_numbers):
            score -= 20
        elif set(source_numbers) != set(translated_numbers):
            score -= 10

        # Check critical patterns
        for _pattern_type, patterns in self.CRITICAL_PATTERNS.items():
            source_matches = 0
            translated_matches = 0

            for pattern in patterns:
                if re.search(pattern, source, re.IGNORECASE):
                    source_matches += 1
                if re.search(pattern, translated, re.IGNORECASE):
                    translated_matches += 1

            if source_matches > 0 and translated_matches == 0:
                score -= 15

        return max(0, score)

    def _check_completeness(
        self, source: str, translated: str
    ) -> Tuple[float, List[str]]:
        """Check if translation is complete."""
        missing_info = []

        # Check length ratio
        source_words = source.split()
        translated_words = translated.split()

        # Allow for language differences in word count
        min_ratio = 0.5
        max_ratio = 2.0

        word_ratio = len(translated_words) / max(len(source_words), 1)

        if word_ratio < min_ratio:
            missing_info.append("Translation appears incomplete (too short)")
            completeness_score = word_ratio * 100
        elif word_ratio > max_ratio:
            missing_info.append("Translation appears to have extra content")
            completeness_score = 100 - (word_ratio - max_ratio) * 20
        else:
            completeness_score = 100

        # Check for critical information
        critical_info_preserved = self._check_critical_info_preserved(
            source, translated
        )

        if not critical_info_preserved["all_preserved"]:
            missing_info.extend(critical_info_preserved["missing"])
            completeness_score *= 0.8

        return max(0, min(100, completeness_score)), missing_info

    def _check_consistency(self, translated: str, _target_lang: str) -> float:
        """Check internal consistency of translation."""
        score = 100.0

        # Check for repeated terms translated differently
        words = translated.lower().split()
        word_freq = Counter(words)

        # In medical text, repeated terms should be translated consistently
        repeated_words = [w for w, count in word_freq.items() if count > 1]

        # Simple consistency check - would be more sophisticated in production
        if len(repeated_words) > 0:
            # Check if medical terms are used consistently
            medical_terms_consistent = True  # Simplified
            if not medical_terms_consistent:
                score -= 10

        return score

    def _check_fluency(self, translated: str, _target_lang: str) -> float:
        """Check translation fluency."""
        # Simplified fluency check
        # In production, would use language models

        score = 100.0

        # Check for basic fluency issues
        # Multiple spaces
        if "  " in translated:
            score -= 5

        # Unclosed parentheses
        if translated.count("(") != translated.count(")"):
            score -= 10

        # Check sentence structure (simplified)
        sentences = re.split(r"[.!?]+", translated)
        for sentence in sentences:
            if len(sentence.strip()) > 0:
                # Very long sentences may indicate fluency issues
                if len(sentence.split()) > 50:
                    score -= 5
                # Very short sentences (except last) may indicate issues
                elif len(sentence.split()) < 3:
                    score -= 3

        return max(0, score)

    def _check_clinical_correctness(
        self, source: str, translated: str, _source_lang: str, _target_lang: str
    ) -> Tuple[float, List[str]]:
        """Check clinical correctness of translation."""
        issues = []
        score = 100.0

        # Check for dangerous mistranslations
        dangerous_patterns = [
            # Negation reversals
            (r"\bnot\s+safe\b", r"\bsafe\b(?!\s+not)"),
            (r"\bdo\s+not\b", r"\bdo\b(?!\s+not)"),
            # Dosage errors
            (r"\b(\d+)\s*mg\b", r"\b\1\s*g\b"),
            # Frequency errors
            (r"\bonce\s+daily\b", r"\bonce\b(?!\s+daily)"),
        ]

        for source_pattern, danger_pattern in dangerous_patterns:
            if re.search(source_pattern, source, re.IGNORECASE):
                if re.search(danger_pattern, translated, re.IGNORECASE):
                    issues.append("Potential dangerous mistranslation detected")
                    score -= 30

        # Check for missing critical warnings
        if any(word in source.lower() for word in ["warning", "danger", "caution"]):
            if not any(
                word in translated.lower() for word in ["warning", "danger", "caution"]
            ):
                # Would check for proper translation in target language
                issues.append("Critical warning may be missing")
                score -= 20

        return max(0, score), issues

    def _extract_all_medical_terms(
        self, text: str, language: str
    ) -> List[Dict[str, str]]:
        """Extract all types of medical terms from text."""
        terms = []

        # Extract from medical glossary
        glossary_terms = self.glossary.search_terms(text, language, limit=50)
        for term in glossary_terms:
            terms.append({"term": term.term_display, "type": "glossary"})

        # Extract ICD-10 codes
        icd_pattern = r"\b[A-Z]\d{2}(?:\.\d+)?\b"
        for match in re.finditer(icd_pattern, text):
            code = match.group()
            if icd10_manager.get_translation(code, language):
                terms.append({"term": code, "type": "icd10"})

        # Extract drug names
        words = text.split()
        for word in words:
            if drug_mapper.get_generic_name(word):
                terms.append({"term": word, "type": "drug"})

        return terms

    def _term_present_in_translation(self, term: str, translation: str) -> bool:
        """Check if term is present in translation."""
        # Simple check - would be more sophisticated in production
        return term.lower() in translation.lower()

    def _check_critical_info_preserved(
        self, source: str, translated: str
    ) -> Dict[str, Any]:
        """Check if critical information is preserved."""
        result: Dict[str, Any] = {"all_preserved": True, "missing": []}

        # Check numbers
        source_numbers = set(re.findall(r"\b\d+(?:\.\d+)?\b", source))
        translated_numbers = set(re.findall(r"\b\d+(?:\.\d+)?\b", translated))

        missing_numbers = source_numbers - translated_numbers
        if missing_numbers:
            result["all_preserved"] = False
            missing_list = result["missing"]
            if isinstance(missing_list, list):
                missing_list.extend([f"Number: {n}" for n in missing_numbers])

        # Check critical patterns
        for pattern_type, patterns in self.CRITICAL_PATTERNS.items():
            for pattern in patterns:
                source_matches = re.findall(pattern, source, re.IGNORECASE)
                if source_matches and not re.search(pattern, translated, re.IGNORECASE):
                    result["all_preserved"] = False
                    missing_list = result["missing"]
                    if isinstance(missing_list, list):
                        missing_list.append(f"{pattern_type}: {source_matches[0]}")

        return result

    def _calculate_overall_score(self, metrics: Dict[AccuracyMetric, float]) -> float:
        """Calculate weighted overall score."""
        total_score = 0.0
        total_weight = 0.0

        for metric, score in metrics.items():
            weight = self.METRIC_WEIGHTS.get(metric, 0)
            total_score += score * weight
            total_weight += weight

        if total_weight > 0:
            return round(total_score / total_weight, 1)
        return 0.0

    def _calculate_confidence(
        self, metrics: Dict[AccuracyMetric, float], details: Dict[str, Any]
    ) -> float:
        """Calculate confidence in accuracy assessment."""
        confidence = 1.0

        # Lower confidence if too few terms analyzed
        term_details = details.get("term_accuracy", {})
        if isinstance(term_details, dict) and term_details.get("total_terms", 0) < 3:
            confidence *= 0.7

        # Lower confidence if scores vary widely
        scores = list(metrics.values())
        if scores:
            score_variance = max(scores) - min(scores)
            if score_variance > 30:
                confidence *= 0.8

        # Lower confidence for very short texts
        source_text = details.get("source_text", "")
        if isinstance(source_text, str) and len(source_text.split()) < 10:
            confidence *= 0.9

        return round(confidence, 2)


# Global instance (would be initialized with dependencies in production)
accuracy_checker = None
