"""
Similarity-based Validator.

Validates translations using various similarity metrics to ensure
semantic and structural accuracy.
"""

import logging
from typing import Any, Dict, List, Optional

from .pipeline import ValidationConfig, ValidationIssue, ValidationStatus
from .similarity import SimilarityConfig, SimilarityMetric, SimilarityScorer
from .validators import BaseValidator

logger = logging.getLogger(__name__)


class SimilarityValidator(BaseValidator):
    """
    Validates translations using similarity scoring.

    Checks:
    - Semantic similarity using embeddings
    - Medical terminology preservation
    - Structural similarity (BLEU, ROUGE)
    - Overall translation quality
    """

    def __init__(self, config: ValidationConfig):
        """Initialize similarity validator."""
        super().__init__(config)

        # Configure similarity scorer
        similarity_config = SimilarityConfig(
            min_semantic_similarity=0.85,
            min_medical_similarity=0.9,
            metric_weights={
                SimilarityMetric.SEMANTIC: 0.3,
                SimilarityMetric.MEDICAL: 0.4,
                SimilarityMetric.BLEU: 0.15,
                SimilarityMetric.ROUGE: 0.15,
            },
        )

        self.scorer = SimilarityScorer(similarity_config)
        self.name = "SimilarityValidator"

    def validate(
        self,
        source_text: str,
        translated_text: str,
        source_lang: str,
        target_lang: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> List[ValidationIssue]:
        """Validate translation using similarity metrics."""
        issues = []

        try:
            # Calculate similarity scores
            scores = self.scorer.calculate_similarity(
                source_text,
                translated_text,
                metrics=[
                    SimilarityMetric.SEMANTIC,
                    SimilarityMetric.MEDICAL,
                    SimilarityMetric.BLEU,
                    SimilarityMetric.ROUGE,
                ],
                source_lang=source_lang,
                target_lang=target_lang,
            )

            # Validate semantic similarity
            semantic_score = scores.get(SimilarityMetric.SEMANTIC)
            if (
                semantic_score
                and semantic_score.score < self.scorer.config.min_semantic_similarity
            ):
                issues.append(
                    ValidationIssue(
                        validator=self.name,
                        severity=ValidationStatus.FAILED,
                        message=f"Semantic similarity too low: {semantic_score.score:.2f} "
                        f"(minimum: {self.scorer.config.min_semantic_similarity})",
                        confidence=semantic_score.confidence,
                        suggestion="Review translation for meaning preservation",
                    )
                )

            # Validate medical similarity
            medical_score = scores.get(SimilarityMetric.MEDICAL)
            if medical_score:
                if medical_score.score < self.scorer.config.min_medical_similarity:
                    issues.append(
                        ValidationIssue(
                            validator=self.name,
                            severity=ValidationStatus.FAILED,
                            message=f"Medical terminology similarity too low: {medical_score.score:.2f} "
                            f"(minimum: {self.scorer.config.min_medical_similarity})",
                            confidence=medical_score.confidence,
                            suggestion="Ensure medical terms are accurately translated",
                        )
                    )

                # Check medical term preservation
                details = medical_score.details
                preservation_ratio = details.get("term_preservation_ratio", 1.0)
                if preservation_ratio < 0.9:
                    issues.append(
                        ValidationIssue(
                            validator=self.name,
                            severity=ValidationStatus.WARNING,
                            message=f"Medical terms not fully preserved: "
                            f"{details.get('medical_terms_translated', 0)}/{details.get('medical_terms_source', 0)}",
                            confidence=0.9,
                        )
                    )

            # Check BLEU score for structural similarity
            bleu_score = scores.get(SimilarityMetric.BLEU)
            if bleu_score and bleu_score.score < self.scorer.config.min_bleu_score:
                issues.append(
                    ValidationIssue(
                        validator=self.name,
                        severity=ValidationStatus.WARNING,
                        message=f"Low structural similarity (BLEU): {bleu_score.score:.2f}",
                        confidence=0.8,
                        suggestion="Translation structure differs significantly from source",
                    )
                )

            # Calculate composite score
            composite_score = self.scorer.calculate_composite_score(scores)

            # Add to metadata for metrics
            if metadata is not None:
                metadata["similarity_scores"] = {
                    metric.value: score.score for metric, score in scores.items()
                }
                metadata["composite_similarity_score"] = composite_score

            # Overall quality check
            if composite_score < 0.8:
                issues.append(
                    ValidationIssue(
                        validator=self.name,
                        severity=ValidationStatus.WARNING,
                        message=f"Overall translation quality score: {composite_score:.2f}",
                        confidence=0.9,
                        suggestion="Consider reviewing translation for overall quality",
                    )
                )

        except (ValueError, AttributeError, KeyError) as e:
            logger.error("Error in similarity validation: %s", e)
            issues.append(
                ValidationIssue(
                    validator=self.name,
                    severity=ValidationStatus.WARNING,
                    message=f"Similarity validation error: {str(e)}",
                    confidence=0.5,
                )
            )

        return issues
