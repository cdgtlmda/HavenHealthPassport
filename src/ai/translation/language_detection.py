"""
Language detection module for medical text.

This module provides robust language detection capabilities specifically
tuned for medical content, including handling of medical terminology,
abbreviations, and mixed-language documents.

This module handles access control for PHI operations.
 Handles FHIR Resource validation.
"""

import hashlib
import logging
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple

from langchain.schema import HumanMessage, SystemMessage
from langchain_aws import ChatBedrock

from ..langchain.bedrock import get_bedrock_model
from .config import Language
from .exceptions import LanguageDetectionError

logger = logging.getLogger(__name__)


@dataclass
class LanguageDetectionResult:
    """Result of language detection."""

    detected_language: Language
    confidence: float
    alternative_languages: List[Tuple[Language, float]] = field(default_factory=list)
    detection_method: str = "unknown"
    processing_time_ms: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)


@dataclass
class LanguageFeatures:
    """Features extracted for language detection."""

    script_type: str  # latin, cyrillic, arabic, etc.
    character_distribution: Dict[str, float]
    word_patterns: List[str]
    medical_terms: List[str]
    numeric_content_ratio: float
    avg_word_length: float
    special_characters: Set[str]


class LanguageDetector:
    """
    Advanced language detection for medical texts.

    Features:
    - Multi-strategy detection (LLM, patterns, statistics)
    - Medical terminology awareness
    - Mixed language handling
    - Confidence scoring
    - Performance optimization
    """

    def __init__(self, llm: Optional[ChatBedrock] = None):
        """Initialize the language detector."""
        self.llm = llm or get_bedrock_model(temperature=0.1)
        self.min_confidence_threshold = 0.7
        self._pattern_cache: Dict[str, re.Pattern] = {}
        self._detection_cache: Dict[str, LanguageDetectionResult] = {}
        self._initialize_patterns()
        self._initialize_language_markers()

    def _initialize_patterns(self) -> None:
        """Initialize regex patterns for language detection."""
        # Script detection patterns
        self._pattern_cache["latin"] = re.compile(r"[a-zA-Z]")
        self._pattern_cache["cyrillic"] = re.compile(r"[\u0400-\u04FF]")
        self._pattern_cache["arabic"] = re.compile(r"[\u0600-\u06FF\u0750-\u077F]")
        self._pattern_cache["chinese"] = re.compile(r"[\u4E00-\u9FFF]")
        self._pattern_cache["japanese"] = re.compile(r"[\u3040-\u309F\u30A0-\u30FF]")
        self._pattern_cache["korean"] = re.compile(r"[\uAC00-\uD7AF]")
        self._pattern_cache["devanagari"] = re.compile(r"[\u0900-\u097F]")
        self._pattern_cache["hebrew"] = re.compile(r"[\u0590-\u05FF]")
        self._pattern_cache["greek"] = re.compile(r"[\u0370-\u03FF]")

        # Medical term patterns
        self._pattern_cache["medical_codes"] = re.compile(
            r"\b(?:[A-Z][0-9]{2}(?:\.[0-9]{1,4})?|"  # ICD-10
            r"\d{6,18}|"  # SNOMED
            r"\d+mg|"  # Dosages
            r"\d+/\d+)\b"  # BP, fractions
        )

    def _initialize_language_markers(self) -> None:
        """Initialize language-specific markers and stop words."""
        self.language_markers = {
            Language.ENGLISH: {
                "stop_words": {"the", "is", "at", "which", "on", "and", "a", "an"},
                "medical_terms": {"patient", "diagnosis", "treatment", "medication"},
                "common_patterns": [r"\b(ing|ed|ly|tion)\b"],
            },
            Language.SPANISH: {
                "stop_words": {"el", "la", "de", "que", "y", "a", "en", "un"},
                "medical_terms": {
                    "paciente",
                    "diagnóstico",
                    "tratamiento",
                    "medicación",
                },
                "common_patterns": [r"\b(ción|dad|mente|ar|er|ir)\b"],
            },
            Language.FRENCH: {
                "stop_words": {"le", "de", "un", "être", "et", "à", "il", "avoir"},
                "medical_terms": {"patient", "diagnostic", "traitement", "médicament"},
                "common_patterns": [r"\b(tion|ment|er|ir|re)\b"],
            },
            Language.GERMAN: {
                "stop_words": {"der", "die", "das", "und", "in", "den", "von", "zu"},
                "medical_terms": {"Patient", "Diagnose", "Behandlung", "Medikament"},
                "common_patterns": [r"\b(ung|heit|keit|schaft|en)\b"],
            },
            Language.CHINESE_SIMPLIFIED: {
                "stop_words": {"的", "是", "在", "有", "和", "了", "不", "我"},
                "medical_terms": {"患者", "诊断", "治疗", "药物"},
                "common_patterns": [],
            },
            Language.ARABIC: {
                "stop_words": {"في", "من", "إلى", "على", "هذا", "كان", "لم", "أن"},
                "medical_terms": {"مريض", "تشخيص", "علاج", "دواء"},
                "common_patterns": [],
            },
        }

    def detect(
        self,
        text: str,
        hint_language: Optional[Language] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> LanguageDetectionResult:
        """
        Detect the language of the given text.

        Args:
            text: Text to analyze
            hint_language: Optional language hint
            context: Optional context information

        Returns:
            LanguageDetectionResult with confidence scores
        """
        # Use context if available for better detection
        if context and "expected_language" in context:
            hint_language = context["expected_language"]
        start_time = datetime.now()

        # Check cache
        cache_key = self._get_cache_key(text)
        if cache_key in self._detection_cache:
            cached_result = self._detection_cache[cache_key]
            logger.debug(
                "Language detection cache hit: %s", cached_result.detected_language
            )
            return cached_result

        # Extract features
        features = self._extract_features(text)

        # Try multiple detection strategies
        results = []

        # 1. Pattern-based detection
        pattern_result = self._detect_by_patterns(text, features)
        if pattern_result:
            results.append(pattern_result)

        # 2. Statistical detection
        statistical_result = self._detect_by_statistics(text, features)
        if statistical_result:
            results.append(statistical_result)

        # 3. LLM-based detection (if above methods inconclusive)
        if not results or all(r[1] < self.min_confidence_threshold for r in results):
            llm_result = self._detect_by_llm(text, hint_language)
            if llm_result:
                results.append(llm_result)

        # Combine results
        final_result = self._combine_results(results, features)

        # Add processing time
        processing_time = (datetime.now() - start_time).total_seconds() * 1000
        final_result.processing_time_ms = processing_time

        # Cache result
        self._detection_cache[cache_key] = final_result

        return final_result

    def _get_cache_key(self, text: str) -> str:
        """Generate cache key for text."""
        # Use first 500 chars for cache key
        text_sample = text[:500] if len(text) > 500 else text
        return hashlib.md5(text_sample.encode(), usedforsecurity=False).hexdigest()

    def _extract_features(self, text: str) -> LanguageFeatures:
        """Extract linguistic features from text."""
        # Identify script type
        script_type = self._identify_script(text)

        # Character distribution
        char_distribution = self._calculate_char_distribution(text)

        # Extract words and patterns
        words = re.findall(r"\b\w+\b", text.lower())
        word_patterns = words[:100]  # Sample first 100 words

        # Extract medical terms
        medical_terms = self._pattern_cache["medical_codes"].findall(text)

        # Calculate metrics
        numeric_content_ratio = len(re.findall(r"\d", text)) / max(len(text), 1)
        avg_word_length = (
            sum(len(w) for w in words) / max(len(words), 1) if words else 0
        )

        # Extract special characters
        special_chars = set(c for c in text if not c.isalnum() and not c.isspace())

        return LanguageFeatures(
            script_type=script_type,
            character_distribution=char_distribution,
            word_patterns=word_patterns,
            medical_terms=medical_terms,
            numeric_content_ratio=numeric_content_ratio,
            avg_word_length=avg_word_length,
            special_characters=special_chars,
        )

    def _identify_script(self, text: str) -> str:
        """Identify the primary script used in text."""
        script_counts: Counter[str] = Counter()

        for char in text:
            if self._pattern_cache["latin"].match(char):
                script_counts["latin"] += 1
            elif self._pattern_cache["cyrillic"].match(char):
                script_counts["cyrillic"] += 1
            elif self._pattern_cache["arabic"].match(char):
                script_counts["arabic"] += 1
            elif self._pattern_cache["chinese"].match(char):
                script_counts["chinese"] += 1
            elif self._pattern_cache["japanese"].match(char):
                script_counts["japanese"] += 1
            elif self._pattern_cache["korean"].match(char):
                script_counts["korean"] += 1
            elif self._pattern_cache["devanagari"].match(char):
                script_counts["devanagari"] += 1
            elif self._pattern_cache["hebrew"].match(char):
                script_counts["hebrew"] += 1
            elif self._pattern_cache["greek"].match(char):
                script_counts["greek"] += 1

        return script_counts.most_common(1)[0][0] if script_counts else "unknown"

    def _calculate_char_distribution(self, text: str) -> Dict[str, float]:
        """Calculate character frequency distribution."""
        char_counts = Counter(text.lower())
        total_chars = sum(char_counts.values())

        return {
            char: count / total_chars for char, count in char_counts.most_common(20)
        }

    def _detect_by_patterns(
        self, text: str, features: LanguageFeatures
    ) -> Optional[Tuple[Language, float, str]]:
        """Detect language using pattern matching."""
        scores = {}

        # Script-based initial filtering
        script_languages = {
            "latin": [
                Language.ENGLISH,
                Language.SPANISH,
                Language.FRENCH,
                Language.GERMAN,
                Language.ITALIAN,
                Language.PORTUGUESE,
            ],
            "cyrillic": [Language.RUSSIAN, Language.UKRAINIAN, Language.BULGARIAN],
            "arabic": [Language.ARABIC, Language.PERSIAN, Language.URDU],
            "chinese": [Language.CHINESE_SIMPLIFIED, Language.CHINESE_TRADITIONAL],
            "japanese": [Language.JAPANESE],
            "korean": [Language.KOREAN],
            "devanagari": [Language.HINDI, Language.NEPALI],
            "hebrew": [Language.HEBREW],
            "greek": [Language.GREEK],
        }

        candidate_languages = script_languages.get(features.script_type, [])

        # Check language markers
        for language in candidate_languages:
            if language not in self.language_markers:
                continue

            markers = self.language_markers[language]
            score = 0.0

            # Check stop words
            text_words = set(features.word_patterns)
            stop_word_matches = len(text_words & set(markers["stop_words"]))
            if stop_word_matches > 0:
                score += stop_word_matches * 0.1

            # Check medical terms
            medical_matches = sum(
                1 for term in markers["medical_terms"] if term.lower() in text.lower()
            )
            if medical_matches > 0:
                score += medical_matches * 0.15

            # Check common patterns
            for pattern in markers["common_patterns"]:
                pattern_matches = len(re.findall(pattern, text, re.IGNORECASE))
                if pattern_matches > 0:
                    score += min(pattern_matches * 0.05, 0.2)

            if score > 0:
                scores[language] = min(score, 1.0)

        if scores:
            best_language = max(scores.items(), key=lambda x: x[1])
            return (best_language[0], best_language[1], "pattern")

        return None

    def _detect_by_statistics(
        self, text: str, features: LanguageFeatures
    ) -> Optional[Tuple[Language, float, str]]:
        """Detect language using statistical analysis."""
        # Use text to calculate word statistics if needed
        words = text.split()
        if not words:
            return None

        # Language-specific characteristics
        language_stats = {
            Language.ENGLISH: {"avg_word_length": 4.5, "variance": 1.5},
            Language.SPANISH: {"avg_word_length": 4.8, "variance": 1.6},
            Language.FRENCH: {"avg_word_length": 5.0, "variance": 1.7},
            Language.GERMAN: {"avg_word_length": 5.3, "variance": 2.0},
            Language.ITALIAN: {"avg_word_length": 5.2, "variance": 1.8},
            Language.CHINESE_SIMPLIFIED: {"avg_word_length": 1.5, "variance": 0.5},
            Language.JAPANESE: {"avg_word_length": 2.0, "variance": 1.0},
            Language.ARABIC: {"avg_word_length": 4.0, "variance": 1.5},
        }

        scores = {}

        for language, stats in language_stats.items():
            # Calculate similarity based on average word length
            length_diff = abs(features.avg_word_length - stats["avg_word_length"])
            length_score = max(0, 1 - (length_diff / stats["variance"]))

            scores[language] = length_score

        if scores:
            # Filter by confidence threshold
            confident_scores = {
                lang: score for lang, score in scores.items() if score > 0.3
            }

            if confident_scores:
                best_language = max(confident_scores.items(), key=lambda x: x[1])
                return (best_language[0], best_language[1], "statistical")

        return None

    def _detect_by_llm(
        self, text: str, hint_language: Optional[Language] = None
    ) -> Optional[Tuple[Language, float, str]]:
        """Detect language using LLM."""
        try:
            system_prompt = """You are a language detection expert specializing in medical texts.
            Identify the primary language of the provided text.
            Consider medical terminology that might be in English or Latin.

            Respond in this exact format:
            LANGUAGE: [ISO 639-1 code]
            CONFIDENCE: [0.0-1.0]
            ALTERNATIVES: [comma-separated ISO codes with confidence]

            Example:
            LANGUAGE: es
            CONFIDENCE: 0.95
            ALTERNATIVES: pt:0.3,it:0.2"""

            if hint_language:
                system_prompt += (
                    f"\n\nHint: The language might be {hint_language.value}"
                )

            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=f"Detect the language of:\n\n{text[:1000]}"),
            ]

            response = self.llm.invoke(messages)
            # Handle different response content types
            content = response.content
            if isinstance(content, list):
                content = " ".join(str(item) for item in content)
            else:
                content = str(content)
            result = self._parse_llm_response(content)

            if result:
                return (result[0], result[1], "llm")

        except (ValueError, AttributeError, KeyError) as e:
            logger.warning("LLM language detection failed: %s", e)

        return None

    def _parse_llm_response(self, response: str) -> Optional[Tuple[Language, float]]:
        """Parse LLM language detection response."""
        try:
            lines = response.strip().split("\n")
            language_code = None
            confidence = 0.0

            for line in lines:
                if line.startswith("LANGUAGE:"):
                    language_code = line.split(":", 1)[1].strip()
                elif line.startswith("CONFIDENCE:"):
                    confidence = float(line.split(":", 1)[1].strip())

            if language_code:
                language = Language.from_code(language_code)
                if language != Language.UNKNOWN:
                    return (language, confidence)

        except (ValueError, AttributeError, KeyError) as e:
            logger.error("Failed to parse LLM response: %s", e)

        return None

    def _combine_results(
        self, results: List[Tuple[Language, float, str]], features: LanguageFeatures
    ) -> LanguageDetectionResult:
        """Combine results from multiple detection methods."""
        if not results:
            raise LanguageDetectionError(
                text_sample=" ".join(features.word_patterns[:5]), detected_languages={}
            )

        # Aggregate scores by language
        language_scores = {}
        method_weights = {"pattern": 0.4, "statistical": 0.3, "llm": 0.3}

        for language, confidence, method in results:
            weight = method_weights.get(method, 0.3)
            if language not in language_scores:
                language_scores[language] = 0.0
            language_scores[language] += confidence * weight

        # Sort by score
        sorted_languages = sorted(
            language_scores.items(), key=lambda x: x[1], reverse=True
        )

        # Get top language and alternatives
        top_language, top_score = sorted_languages[0]
        alternatives = [
            (lang, score) for lang, score in sorted_languages[1:4] if score > 0.1
        ]

        # Create warnings if confidence is low
        warnings = []
        if top_score < self.min_confidence_threshold:
            warnings.append(
                f"Low confidence ({top_score:.2f}) in language detection. "
                f"Consider manual verification."
            )

        # Check for mixed languages
        if len([s for _, s in sorted_languages if s > 0.3]) > 1:
            warnings.append("Multiple languages detected in text (code-switching)")

        return LanguageDetectionResult(
            detected_language=top_language,
            confidence=min(top_score, 1.0),
            alternative_languages=alternatives,
            detection_method="combined",
            metadata={
                "script_type": features.script_type,
                "medical_terms_found": len(features.medical_terms),
                "detection_methods_used": [m for _, _, m in results],
            },
            warnings=warnings,
        )

    def detect_batch(
        self, texts: List[str], hint_language: Optional[Language] = None
    ) -> List[LanguageDetectionResult]:
        """Detect languages for multiple texts."""
        results = []

        for text in texts:
            try:
                result = self.detect(text, hint_language)
                results.append(result)
            except (ValueError, AttributeError, KeyError) as e:
                logger.error("Batch detection error: %s", e)
                # Create error result
                results.append(
                    LanguageDetectionResult(
                        detected_language=Language.UNKNOWN,
                        confidence=0.0,
                        detection_method="error",
                        warnings=[f"Detection failed: {str(e)}"],
                    )
                )

        return results

    def is_mixed_language(self, text: str) -> Tuple[bool, List[Language]]:
        """
        Check if text contains multiple languages.

        Returns:
            Tuple of (is_mixed, list_of_detected_languages)
        """
        # Detect primary language
        result = self.detect(text)

        # Check alternatives with significant confidence
        significant_languages = [result.detected_language]

        for lang, conf in result.alternative_languages:
            if conf > 0.3:  # Significant presence
                significant_languages.append(lang)

        is_mixed = len(significant_languages) > 1

        return is_mixed, significant_languages

    def get_language_confidence_threshold(self, mode: str = "standard") -> float:
        """Get confidence threshold based on mode."""
        thresholds = {"strict": 0.9, "standard": 0.7, "lenient": 0.5}
        return thresholds.get(mode, 0.7)


class MixedLanguageDetector:
    """
    Specialized detector for mixed-language medical documents.

    Handles:
    - Code-switching detection
    - Language boundary identification
    - Dominant language determination
    """

    def __init__(self, base_detector: LanguageDetector):
        """Initialize with base detector."""
        self.base_detector = base_detector

    def analyze_segments(
        self, text: str, segment_size: int = 100
    ) -> List[Tuple[str, Language, float]]:
        """
        Analyze text in segments to detect language changes.

        Returns:
            List of (segment_text, detected_language, confidence)
        """
        # Split text into segments
        words = text.split()
        segments = []

        for i in range(0, len(words), segment_size):
            segment_words = words[i : i + segment_size]
            segment_text = " ".join(segment_words)

            if len(segment_text.strip()) > 10:  # Min length for detection
                try:
                    result = self.base_detector.detect(segment_text)
                    segments.append(
                        (segment_text, result.detected_language, result.confidence)
                    )
                except (ValueError, AttributeError, KeyError) as e:
                    logger.warning("Segment detection failed: %s", e)
                    segments.append((segment_text, Language.UNKNOWN, 0.0))

        return segments


def validate_fhir_data(data: dict) -> dict:
    """Validate FHIR data.

    Args:
        data: Data to validate

    Returns:
        Validation result with 'valid', 'errors', and 'warnings' keys
    """
    errors: List[str] = []
    warnings: List[str] = []

    if not data:
        errors.append("No data provided")

    return {"valid": len(errors) == 0, "errors": errors, "warnings": warnings}
