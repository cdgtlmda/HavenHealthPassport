"""
Translation Metrics Module.

Defines metrics for evaluating translation quality and validation results.
"""

from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class TranslationMetrics:
    """Metrics for translation validation."""

    total_validations: int
    passed_validations: int
    failed_validations: int
    warnings: int
    confidence_score: float
    validation_time: float  # seconds

    # Additional quality metrics
    semantic_similarity: Optional[float] = None
    terminology_accuracy: Optional[float] = None
    format_preservation: Optional[float] = None
    fluency_score: Optional[float] = None

    @property
    def pass_rate(self) -> float:
        """Calculate validation pass rate."""
        if self.total_validations == 0:
            return 0.0
        return self.passed_validations / self.total_validations

    @property
    def quality_score(self) -> float:
        """Calculate overall quality score."""
        scores = [self.confidence_score]

        if self.semantic_similarity is not None:
            scores.append(self.semantic_similarity)
        if self.terminology_accuracy is not None:
            scores.append(self.terminology_accuracy)
        if self.format_preservation is not None:
            scores.append(self.format_preservation)
        if self.fluency_score is not None:
            scores.append(self.fluency_score)

        return sum(scores) / len(scores)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "total_validations": self.total_validations,
            "passed_validations": self.passed_validations,
            "failed_validations": self.failed_validations,
            "warnings": self.warnings,
            "confidence_score": self.confidence_score,
            "validation_time": self.validation_time,
            "pass_rate": self.pass_rate,
            "quality_score": self.quality_score,
            "semantic_similarity": self.semantic_similarity,
            "terminology_accuracy": self.terminology_accuracy,
            "format_preservation": self.format_preservation,
            "fluency_score": self.fluency_score,
        }
