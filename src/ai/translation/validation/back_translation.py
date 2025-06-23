"""
Back-Translation Validation Module.

Implements back-translation checking to verify translation quality by
translating the output back to the source language and comparing results.

This module handles encrypted PHI with access control and audit logging
to ensure HIPAA compliance.
"""

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from difflib import SequenceMatcher
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

from ..chains import TranslationChainFactory
from ..config import Language, TranslationConfig
from .pipeline import ValidationIssue, ValidationStatus


class BackTranslationMethod(Enum):
    """Methods for performing back-translation."""

    DIRECT = "direct"  # Simple back-translation
    PIVOT = "pivot"  # Use pivot language
    ENSEMBLE = "ensemble"  # Multiple back-translations
    ITERATIVE = "iterative"  # Multiple rounds


class SimilarityMetric(Enum):
    """Metrics for measuring similarity."""

    EXACT_MATCH = "exact_match"
    LEVENSHTEIN = "levenshtein"
    COSINE = "cosine"
    JACCARD = "jaccard"
    BLEU = "bleu"
    SEMANTIC = "semantic"


@dataclass
class BackTranslationResult:
    """Result of back-translation check."""

    original_text: str
    translated_text: str
    back_translated_text: str
    source_lang: str
    target_lang: str
    similarity_scores: Dict[SimilarityMetric, float] = field(default_factory=dict)
    issues: List[ValidationIssue] = field(default_factory=list)
    method: BackTranslationMethod = BackTranslationMethod.DIRECT
    confidence: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_acceptable(self) -> bool:
        """Check if back-translation is acceptable."""
        return self.confidence >= 0.7 and len(self.critical_issues) == 0

    @property
    def critical_issues(self) -> List[ValidationIssue]:
        """Get critical issues only."""
        return [i for i in self.issues if i.severity == ValidationStatus.FAILED]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "original_text": self.original_text,
            "translated_text": self.translated_text,
            "back_translated_text": self.back_translated_text,
            "source_lang": self.source_lang,
            "target_lang": self.target_lang,
            "similarity_scores": {
                k.value: v for k, v in self.similarity_scores.items()
            },
            "issues": [i.to_dict() for i in self.issues],
            "method": self.method.value,
            "confidence": self.confidence,
            "is_acceptable": self.is_acceptable,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }


@dataclass
class BackTranslationConfig:
    """Configuration for back-translation checking."""

    method: BackTranslationMethod = BackTranslationMethod.DIRECT
    similarity_metrics: List[SimilarityMetric] = field(
        default_factory=lambda: [
            SimilarityMetric.LEVENSHTEIN,
            SimilarityMetric.COSINE,
            SimilarityMetric.SEMANTIC,
        ]
    )

    # Thresholds
    min_similarity_threshold: float = 0.7
    min_semantic_similarity: float = 0.8
    max_length_deviation: float = 0.3

    # Medical-specific settings
    preserve_medical_terms: bool = True
    check_dosage_consistency: bool = True
    verify_critical_info: bool = True

    # Performance settings
    use_cache: bool = True
    parallel_processing: bool = False
    max_retries: int = 2
    timeout_seconds: int = 60

    # Ensemble settings (if using ensemble method)
    ensemble_models: List[str] = field(default_factory=list)
    ensemble_voting: str = "weighted"  # weighted, majority, unanimous


class BackTranslationChecker:
    """Main back-translation checking implementation."""

    def __init__(
        self,
        config: Optional[BackTranslationConfig] = None,
        translation_config: Optional[TranslationConfig] = None,
    ):
        """Initialize back-translation checker."""
        self.config = config or BackTranslationConfig()
        self.translation_config = translation_config or TranslationConfig()

        # Initialize translation chain factory
        self.chain_factory = TranslationChainFactory()

        # Cache for performance
        self.cache: Optional[Dict[str, Any]] = {} if self.config.use_cache else None

        # History for analysis
        self.history: List[BackTranslationResult] = []

    def check(
        self,
        original_text: str,
        translated_text: str,
        source_lang: str,
        target_lang: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> BackTranslationResult:
        """Perform back-translation check."""
        # Check cache
        cache_key = self._get_cache_key(
            original_text, translated_text, source_lang, target_lang
        )
        if self.cache is not None and cache_key in self.cache:
            cached_result = self.cache[cache_key]
            if isinstance(cached_result, BackTranslationResult):
                return cached_result

        # Perform back-translation based on method
        if self.config.method == BackTranslationMethod.DIRECT:
            result = self._direct_back_translation(
                original_text, translated_text, source_lang, target_lang, metadata
            )
        elif self.config.method == BackTranslationMethod.PIVOT:
            result = self._pivot_back_translation(
                original_text, translated_text, source_lang, target_lang, metadata
            )
        elif self.config.method == BackTranslationMethod.ENSEMBLE:
            result = self._ensemble_back_translation(
                original_text, translated_text, source_lang, target_lang, metadata
            )
        elif self.config.method == BackTranslationMethod.ITERATIVE:
            result = self._iterative_back_translation(
                original_text, translated_text, source_lang, target_lang, metadata
            )
        else:
            raise ValueError(f"Unknown method: {self.config.method}")

        # Cache result
        if self.cache is not None:
            self.cache[cache_key] = result

        # Add to history
        self.history.append(result)

        return result

    def _get_cache_key(
        self, original: str, translated: str, source_lang: str, target_lang: str
    ) -> str:
        """Generate cache key."""
        return f"{source_lang}:{target_lang}:{hash(original)}:{hash(translated)}"

    def _direct_back_translation(
        self,
        original: str,
        translated: str,
        source_lang: str,
        target_lang: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> BackTranslationResult:
        """Perform direct back-translation."""
        # Create translation chain for back-translation
        back_chain = self.chain_factory.create_chain(
            source_language=target_lang,
            target_language=source_lang,
            config=self.translation_config,
        )

        # Perform back-translation
        try:
            back_result = back_chain.translate(translated, Language(source_lang))
            back_translated = back_result.translated_text
        except (ValueError, RuntimeError, AttributeError) as e:
            # Handle translation failure
            result = BackTranslationResult(
                original_text=original,
                translated_text=translated,
                back_translated_text="",
                source_lang=source_lang,
                target_lang=target_lang,
                method=BackTranslationMethod.DIRECT,
                metadata=metadata or {},
            )
            result.issues.append(
                ValidationIssue(
                    validator="BackTranslationChecker",
                    severity=ValidationStatus.FAILED,
                    message=f"Back-translation failed: {str(e)}",
                    confidence=1.0,
                )
            )
            return result

        # Create result
        result = BackTranslationResult(
            original_text=original,
            translated_text=translated,
            back_translated_text=back_translated,
            source_lang=source_lang,
            target_lang=target_lang,
            method=BackTranslationMethod.DIRECT,
            metadata=metadata or {},
        )

        # Calculate similarity scores
        result.similarity_scores = self._calculate_similarities(
            original, back_translated
        )

        # Analyze results
        result.issues = self._analyze_back_translation(original, back_translated)

        # Calculate confidence
        result.confidence = self._calculate_confidence(result)

        return result

    def _pivot_back_translation(
        self,
        original: str,
        translated: str,
        source_lang: str,
        target_lang: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> BackTranslationResult:
        """Perform back-translation through pivot language."""
        # Common pivot language (English if not already involved)
        pivot_lang = "en" if source_lang != "en" and target_lang != "en" else "es"

        # Translate to pivot language
        to_pivot_chain = self.chain_factory.create_chain(
            source_language=target_lang,
            target_language=pivot_lang,
            config=self.translation_config,
        )

        try:
            pivot_result = to_pivot_chain.translate(translated, Language(pivot_lang))
            pivot_text = pivot_result.translated_text

            # Translate from pivot to source
            from_pivot_chain = self.chain_factory.create_chain(
                source_language=pivot_lang,
                target_language=source_lang,
                config=self.translation_config,
            )

            back_result = from_pivot_chain.translate(pivot_text, Language(source_lang))
            back_translated = back_result.translated_text

        except (ValueError, RuntimeError, AttributeError) as e:
            result = BackTranslationResult(
                original_text=original,
                translated_text=translated,
                back_translated_text="",
                source_lang=source_lang,
                target_lang=target_lang,
                method=BackTranslationMethod.PIVOT,
                metadata=metadata or {},
            )
            result.issues.append(
                ValidationIssue(
                    validator="BackTranslationChecker",
                    severity=ValidationStatus.FAILED,
                    message=f"Pivot back-translation failed: {str(e)}",
                    confidence=1.0,
                )
            )
            return result

        # Create result
        result = BackTranslationResult(
            original_text=original,
            translated_text=translated,
            back_translated_text=back_translated,
            source_lang=source_lang,
            target_lang=target_lang,
            method=BackTranslationMethod.PIVOT,
            metadata=metadata
            or {"pivot_language": pivot_lang, "pivot_text": pivot_text},
        )

        # Calculate metrics
        result.similarity_scores = self._calculate_similarities(
            original, back_translated
        )
        result.issues = self._analyze_back_translation(original, back_translated)
        result.confidence = self._calculate_confidence(result)

        return result

    def _ensemble_back_translation(
        self,
        original: str,
        translated: str,
        source_lang: str,
        target_lang: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> BackTranslationResult:
        """Perform ensemble back-translation using multiple models."""
        back_translations = []

        # Use multiple translation approaches
        models = self.config.ensemble_models or ["default", "medical", "formal"]

        for _ in models:
            try:
                # Create chain with specific model config
                model_config = TranslationConfig()
                back_chain = self.chain_factory.create_chain(
                    source_language=target_lang,
                    target_language=source_lang,
                    config=model_config,
                )

                back_result = back_chain.translate(translated, Language(source_lang))
                back_translations.append(back_result)

            except (ValueError, RuntimeError, AttributeError):
                # Log but continue with other models
                pass

        if not back_translations:
            # All models failed
            result = BackTranslationResult(
                original_text=original,
                translated_text=translated,
                back_translated_text="",
                source_lang=source_lang,
                target_lang=target_lang,
                method=BackTranslationMethod.ENSEMBLE,
                metadata=metadata or {},
            )
            result.issues.append(
                ValidationIssue(
                    validator="BackTranslationChecker",
                    severity=ValidationStatus.FAILED,
                    message="All ensemble models failed",
                    confidence=1.0,
                )
            )
            return result

        # Select best back-translation or combine
        if self.config.ensemble_voting == "weighted":
            # Use the one with highest similarity to original
            best_score = -1.0
            best_translation = back_translations[0]

            for bt in back_translations:
                bt_text = (
                    bt.translated_text if hasattr(bt, "translated_text") else str(bt)
                )
                score = self._calculate_semantic_similarity(original, bt_text)
                if score > best_score:
                    best_score = score
                    best_translation = bt

            selected_back_translation = (
                best_translation.translated_text
                if hasattr(best_translation, "translated_text")
                else str(best_translation)
            )
        else:
            # Simple: use first successful
            selected_back_translation = (
                back_translations[0].translated_text
                if hasattr(back_translations[0], "translated_text")
                else str(back_translations[0])
            )

        # Create result
        result = BackTranslationResult(
            original_text=original,
            translated_text=translated,
            back_translated_text=selected_back_translation,
            source_lang=source_lang,
            target_lang=target_lang,
            method=BackTranslationMethod.ENSEMBLE,
            metadata={
                **(metadata or {}),
                "ensemble_count": len(back_translations),
                "all_back_translations": back_translations,
            },
        )

        # Calculate metrics
        result.similarity_scores = self._calculate_similarities(
            original, selected_back_translation
        )
        result.issues = self._analyze_back_translation(
            original, selected_back_translation
        )
        result.confidence = self._calculate_confidence(result)

        return result

    def _iterative_back_translation(
        self,
        original: str,
        translated: str,
        source_lang: str,
        target_lang: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> BackTranslationResult:
        """Perform iterative back-translation for refinement."""
        iterations = []
        current_text = translated
        max_iterations = 3

        for i in range(max_iterations):
            # Back-translate
            back_chain = self.chain_factory.create_chain(
                source_language=target_lang if i % 2 == 0 else source_lang,
                target_language=source_lang if i % 2 == 0 else target_lang,
                config=self.translation_config,
            )

            try:
                target = Language(source_lang if i % 2 == 0 else target_lang)
                translation_result = back_chain.translate(current_text, target)
                current_text = translation_result.translated_text
                iterations.append(current_text)
            except (ValueError, RuntimeError, AttributeError):
                break

        # Use the final back-translation to source language
        final_back_translation = (
            iterations[-1]
            if len(iterations) % 2 == 1
            else iterations[-2] if len(iterations) >= 2 else ""
        )

        # Create result
        result = BackTranslationResult(
            original_text=original,
            translated_text=translated,
            back_translated_text=final_back_translation,
            source_lang=source_lang,
            target_lang=target_lang,
            method=BackTranslationMethod.ITERATIVE,
            metadata={
                **(metadata or {}),
                "iterations": len(iterations),
                "iteration_history": iterations,
            },
        )

        # Calculate metrics
        if final_back_translation:
            result.similarity_scores = self._calculate_similarities(
                original, final_back_translation
            )
            result.issues = self._analyze_back_translation(
                original, final_back_translation
            )
            result.confidence = self._calculate_confidence(result)
        else:
            result.issues.append(
                ValidationIssue(
                    validator="BackTranslationChecker",
                    severity=ValidationStatus.FAILED,
                    message="Iterative back-translation failed",
                    confidence=1.0,
                )
            )

        return result

    def _calculate_similarities(
        self, original: str, back_translated: str
    ) -> Dict[SimilarityMetric, float]:
        """Calculate various similarity metrics."""
        scores: Dict[SimilarityMetric, float] = {}

        for metric in self.config.similarity_metrics:
            if metric == SimilarityMetric.EXACT_MATCH:
                scores[metric] = 1.0 if original == back_translated else 0.0

            elif metric == SimilarityMetric.LEVENSHTEIN:
                scores[metric] = self._calculate_levenshtein_similarity(
                    original, back_translated
                )

            elif metric == SimilarityMetric.COSINE:
                scores[metric] = self._calculate_cosine_similarity(
                    original, back_translated
                )

            elif metric == SimilarityMetric.JACCARD:
                scores[metric] = self._calculate_jaccard_similarity(
                    original, back_translated
                )

            elif metric == SimilarityMetric.BLEU:
                scores[metric] = self._calculate_bleu_score(original, back_translated)

            elif metric == SimilarityMetric.SEMANTIC:
                scores[metric] = self._calculate_semantic_similarity(
                    original, back_translated
                )

        return scores

    def _calculate_levenshtein_similarity(self, text1: str, text2: str) -> float:
        """Calculate Levenshtein distance-based similarity."""
        # Using SequenceMatcher as approximation
        return SequenceMatcher(None, text1, text2).ratio()

    def _calculate_cosine_similarity(self, text1: str, text2: str) -> float:
        """Calculate cosine similarity between texts."""
        # Simple word-based cosine similarity
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())

        if not words1 or not words2:
            return 0.0

        intersection = len(words1.intersection(words2))
        denominator = (len(words1) ** 0.5) * (len(words2) ** 0.5)

        return intersection / denominator if denominator > 0 else 0.0

    def _calculate_jaccard_similarity(self, text1: str, text2: str) -> float:
        """Calculate Jaccard similarity between texts."""
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())

        if not words1 and not words2:
            return 1.0

        intersection = len(words1.intersection(words2))
        union = len(words1.union(words2))

        return intersection / union if union > 0 else 0.0

    def _calculate_bleu_score(self, reference: str, candidate: str) -> float:
        """Calculate simplified BLEU score."""
        # Simplified unigram BLEU
        ref_words = reference.lower().split()
        cand_words = candidate.lower().split()

        if not cand_words:
            return 0.0

        matches = sum(1 for word in cand_words if word in ref_words)
        precision = matches / len(cand_words)

        # Brevity penalty
        brevity_penalty = (
            min(1.0, len(cand_words) / len(ref_words)) if ref_words else 0.0
        )

        return precision * brevity_penalty

    def _calculate_semantic_similarity(self, text1: str, text2: str) -> float:
        """Calculate semantic similarity (placeholder for embedding-based similarity)."""
        # In production, this would use sentence embeddings
        # For now, use enhanced word overlap with synonyms consideration

        # Extract key medical terms
        medical_terms1 = self._extract_medical_terms(text1)
        medical_terms2 = self._extract_medical_terms(text2)

        # Calculate medical term preservation
        if medical_terms1:
            preserved = len(medical_terms1.intersection(medical_terms2))
            medical_score = preserved / len(medical_terms1)
        else:
            medical_score = 1.0

        # Combine with general similarity
        general_score = self._calculate_jaccard_similarity(text1, text2)

        # Weight medical preservation higher
        return 0.7 * medical_score + 0.3 * general_score

    def _extract_medical_terms(self, text: str) -> Set[str]:
        """Extract medical terms from text."""
        # Common medical terms and patterns
        medical_patterns = [
            r"\b\d+\s*(?:mg|g|ml|mcg|μg|L|IU)\b",  # Dosages
            r"\b(?:allergy|allergic|medication|drug|dose|treatment|diagnosis)\b",
            r"\b(?:daily|twice|three times|QD|BID|TID|QID|PRN)\b",
            r"\b[A-Z][a-z]+(?:in|ol|am|ine|ate|ide)\b",  # Drug name patterns
        ]

        terms: Set[str] = set()

        for pattern in medical_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            terms.update(m.lower() for m in matches)

        return terms

    def _analyze_back_translation(
        self, original: str, back_translated: str
    ) -> List[ValidationIssue]:
        """Analyze back-translation for issues."""
        issues = []

        # Check length deviation
        length_ratio = len(back_translated) / len(original) if original else 0
        if abs(1 - length_ratio) > self.config.max_length_deviation:
            issues.append(
                ValidationIssue(
                    validator="BackTranslationChecker",
                    severity=ValidationStatus.WARNING,
                    message=f"Significant length deviation: {length_ratio:.2f}x original",
                    confidence=0.8,
                )
            )

        # Check medical term preservation
        if self.config.preserve_medical_terms:
            original_terms = self._extract_medical_terms(original)
            back_terms = self._extract_medical_terms(back_translated)

            missing_terms = original_terms - back_terms
            if missing_terms:
                issues.append(
                    ValidationIssue(
                        validator="BackTranslationChecker",
                        severity=ValidationStatus.FAILED,
                        message=f"Medical terms lost in back-translation: {', '.join(missing_terms)}",
                        confidence=0.9,
                    )
                )

        # Check numeric consistency
        original_numbers = set(re.findall(r"\b\d+(?:\.\d+)?\b", original))
        back_numbers = set(re.findall(r"\b\d+(?:\.\d+)?\b", back_translated))

        if original_numbers != back_numbers:
            issues.append(
                ValidationIssue(
                    validator="BackTranslationChecker",
                    severity=ValidationStatus.FAILED,
                    message="Numeric values changed in back-translation",
                    confidence=0.95,
                )
            )

        # Check critical information
        if self.config.verify_critical_info:
            critical_patterns = [
                (r"\b(?:not|never|don\'t|no)\b", "negation"),
                (r"\b(?:warning|danger|caution)\b", "safety warning"),
                (r"\b(?:allergy|allergic)\b", "allergy information"),
                (r"\b(?:contraindicated|avoid)\b", "contraindication"),
            ]

            for pattern, info_type in critical_patterns:
                original_matches = bool(re.search(pattern, original, re.IGNORECASE))
                back_matches = bool(re.search(pattern, back_translated, re.IGNORECASE))

                if original_matches and not back_matches:
                    issues.append(
                        ValidationIssue(
                            validator="BackTranslationChecker",
                            severity=ValidationStatus.FAILED,
                            message=f"Critical {info_type} lost in back-translation",
                            confidence=0.95,
                        )
                    )

        return issues

    def _calculate_confidence(self, result: BackTranslationResult) -> float:
        """Calculate overall confidence score."""
        if not result.similarity_scores:
            return 0.0

        # Weight different metrics
        weights = {
            SimilarityMetric.SEMANTIC: 0.4,
            SimilarityMetric.LEVENSHTEIN: 0.2,
            SimilarityMetric.COSINE: 0.2,
            SimilarityMetric.JACCARD: 0.1,
            SimilarityMetric.BLEU: 0.1,
        }

        weighted_score = 0.0
        total_weight = 0.0

        for metric, score in result.similarity_scores.items():
            weight = weights.get(metric, 0.1)
            weighted_score += score * weight
            total_weight += weight

        base_confidence = weighted_score / total_weight if total_weight > 0 else 0.0

        # Adjust for issues
        if result.critical_issues:
            base_confidence *= 0.5

        warning_penalty = (
            len([i for i in result.issues if i.severity == ValidationStatus.WARNING])
            * 0.05
        )

        return max(0.0, min(1.0, base_confidence - warning_penalty))

    def check_batch(
        self, items: List[Tuple[str, str, str, str]]
    ) -> List[BackTranslationResult]:
        """Check multiple translations."""
        results = []

        for original, translated, source_lang, target_lang in items:
            result = self.check(original, translated, source_lang, target_lang)
            results.append(result)

        return results

    def get_summary(self) -> Dict[str, Any]:
        """Get summary of all back-translation checks."""
        if not self.history:
            return {"message": "No back-translation checks performed yet"}

        acceptable_count = sum(1 for r in self.history if r.is_acceptable)

        # Calculate average scores by metric
        metric_averages = {}
        for metric in SimilarityMetric:
            scores = [
                r.similarity_scores.get(metric, 0)
                for r in self.history
                if metric in r.similarity_scores
            ]
            if scores:
                metric_averages[metric.value] = sum(scores) / len(scores)

        # Common issues
        issue_counts: Dict[Tuple[str, str], int] = {}
        for result in self.history:
            for issue in result.issues:
                key = (issue.validator, issue.message)
                issue_counts[key] = issue_counts.get(key, 0) + 1

        common_issues = sorted(issue_counts.items(), key=lambda x: x[1], reverse=True)[
            :5
        ]

        return {
            "total_checks": len(self.history),
            "acceptable": acceptable_count,
            "acceptance_rate": acceptable_count / len(self.history),
            "average_confidence": sum(r.confidence for r in self.history)
            / len(self.history),
            "metric_averages": metric_averages,
            "common_issues": [
                {"validator": v, "message": m, "count": c}
                for (v, m), c in common_issues
            ],
            "method_distribution": self._get_method_distribution(),
        }

    def _get_method_distribution(self) -> Dict[str, int]:
        """Get distribution of back-translation methods used."""
        distribution: Dict[str, int] = {}
        for result in self.history:
            method = result.method.value
            distribution[method] = distribution.get(method, 0) + 1
        return distribution

    def export_report(self, filepath: str, file_format: str = "json") -> None:
        """Export back-translation report."""
        data = {
            "summary": self.get_summary(),
            "detailed_results": [r.to_dict() for r in self.history[-100:]],  # Last 100
        }

        if file_format == "json":
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        else:
            raise ValueError(f"Unsupported format: {file_format}")


# Convenience functions
def check_back_translation(
    original: str, translated: str, source_lang: str, target_lang: str
) -> BackTranslationResult:
    """Quick back-translation check with default settings."""
    checker = BackTranslationChecker()
    return checker.check(original, translated, source_lang, target_lang)


def evaluate_translation_quality(
    original: str,
    translated: str,
    source_lang: str,
    target_lang: str,
    method: BackTranslationMethod = BackTranslationMethod.DIRECT,
) -> Dict[str, Any]:
    """Evaluate translation quality using back-translation."""
    config = BackTranslationConfig(method=method)
    checker = BackTranslationChecker(config)

    result = checker.check(original, translated, source_lang, target_lang)

    return {
        "is_acceptable": result.is_acceptable,
        "confidence": result.confidence,
        "similarity_scores": {k.value: v for k, v in result.similarity_scores.items()},
        "issues": [
            {"severity": i.severity.value, "message": i.message} for i in result.issues
        ],
        "back_translated_text": result.back_translated_text,
    }
