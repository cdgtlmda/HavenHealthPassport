"""
Translation Validation Pipeline.

Comprehensive validation system for medical translations ensuring accuracy,
completeness, and safety of translated healthcare content.
"""

import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from .metrics import TranslationMetrics


class ValidationLevel(Enum):
    """Validation strictness levels."""

    BASIC = "basic"  # Basic checks only
    STANDARD = "standard"  # Standard medical validation
    STRICT = "strict"  # Strict validation for critical content
    CRITICAL = "critical"  # Maximum validation for life-critical content


class ValidationStatus(Enum):
    """Validation result status."""

    PASSED = "passed"
    WARNING = "warning"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class ValidationIssue:
    """Represents a validation issue found."""

    validator: str
    severity: ValidationStatus
    message: str
    location: Optional[Tuple[int, int]] = None  # Start, end position
    suggestion: Optional[str] = None
    confidence: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "validator": self.validator,
            "severity": self.severity.value,
            "message": self.message,
            "location": self.location,
            "suggestion": self.suggestion,
            "confidence": self.confidence,
        }


@dataclass
class ValidationResult:
    """Complete validation result for a translation."""

    source_text: str
    translated_text: str
    source_lang: str
    target_lang: str
    validation_level: ValidationLevel
    overall_status: ValidationStatus
    issues: List[ValidationIssue] = field(default_factory=list)
    metrics: Optional["TranslationMetrics"] = None
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        """Check if validation passed."""
        return self.overall_status in [
            ValidationStatus.PASSED,
            ValidationStatus.WARNING,
        ]

    @property
    def error_count(self) -> int:
        """Count of failed validations."""
        return sum(
            1 for issue in self.issues if issue.severity == ValidationStatus.FAILED
        )

    @property
    def warning_count(self) -> int:
        """Count of warning validations."""
        return sum(
            1 for issue in self.issues if issue.severity == ValidationStatus.WARNING
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "source_text": self.source_text,
            "translated_text": self.translated_text,
            "source_lang": self.source_lang,
            "target_lang": self.target_lang,
            "validation_level": self.validation_level.value,
            "overall_status": self.overall_status.value,
            "issues": [issue.to_dict() for issue in self.issues],
            "metrics": self.metrics.to_dict() if self.metrics else None,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
            "summary": {
                "passed": self.passed,
                "error_count": self.error_count,
                "warning_count": self.warning_count,
            },
        }


@dataclass
class ValidationConfig:
    """Configuration for validation pipeline."""

    level: ValidationLevel = ValidationLevel.STANDARD

    # Individual validator toggles
    validate_medical_terms: bool = True
    validate_numeric_consistency: bool = True
    validate_format_preservation: bool = True
    validate_context: bool = True
    validate_safety: bool = True
    validate_similarity: bool = True  # New similarity validation
    validate_medical_accuracy: bool = True  # New medical accuracy validation

    # Thresholds
    min_confidence_threshold: float = 0.8
    max_acceptable_errors: int = 0
    max_acceptable_warnings: int = 5

    # Medical-specific settings
    require_term_preservation: bool = True
    check_drug_interactions: bool = True
    verify_dosage_accuracy: bool = True
    check_allergy_info: bool = True

    # Performance settings
    enable_caching: bool = True
    parallel_validation: bool = False
    timeout_seconds: int = 30


class TranslationValidationPipeline:
    """Main translation validation pipeline."""

    def __init__(self, config: Optional[ValidationConfig] = None):
        """Initialize validation pipeline."""
        self.config = config or ValidationConfig()

        # Initialize validators
        self._init_validators()

        # Cache for repeated validations
        self.cache: Optional[Dict[str, Any]] = (
            {} if self.config.enable_caching else None
        )

        # Validation history for learning
        self.history: List[ValidationResult] = []

    def _init_validators(self) -> None:
        """Initialize all validators based on config."""
        from . import validators  # pylint: disable=import-outside-toplevel
        from .medical_accuracy_validator import (  # pylint: disable=import-outside-toplevel
            MedicalAccuracyValidatorIntegration,
        )
        from .similarity_validator import (  # pylint: disable=import-outside-toplevel
            SimilarityValidator,
        )

        self.validators: List[Any] = []

        if self.config.validate_medical_terms:
            self.validators.append(validators.MedicalTermValidator(self.config))

        if self.config.validate_numeric_consistency:
            self.validators.append(validators.NumericConsistencyValidator(self.config))

        if self.config.validate_format_preservation:
            self.validators.append(validators.FormatPreservationValidator(self.config))

        if self.config.validate_context:
            self.validators.append(validators.ContextualValidator(self.config))

        if self.config.validate_safety:
            self.validators.append(validators.SafetyValidator(self.config))

        if self.config.validate_similarity:
            self.validators.append(SimilarityValidator(self.config))

        if self.config.validate_medical_accuracy:
            self.validators.append(MedicalAccuracyValidatorIntegration(self.config))

    def validate(
        self,
        source_text: str,
        translated_text: str,
        source_lang: str,
        target_lang: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ValidationResult:
        """Validate a translation."""
        # Check cache
        cache_key = self._get_cache_key(
            source_text, translated_text, source_lang, target_lang
        )
        if self.cache is not None and cache_key in self.cache:
            cached_result = self.cache[cache_key]
            if isinstance(cached_result, ValidationResult):
                return cached_result

        # Create result object
        result = ValidationResult(
            source_text=source_text,
            translated_text=translated_text,
            source_lang=source_lang,
            target_lang=target_lang,
            validation_level=self.config.level,
            overall_status=ValidationStatus.PASSED,
            metadata=metadata or {},
        )

        # Run each validator
        for validator in self.validators:
            try:
                validator_issues = validator.validate(
                    source_text, translated_text, source_lang, target_lang
                )
                result.issues.extend(validator_issues)
            except (ValueError, AttributeError, TypeError) as e:
                # Log validator error but continue
                result.issues.append(
                    ValidationIssue(
                        validator=validator.__class__.__name__,
                        severity=ValidationStatus.WARNING,
                        message=f"Validator error: {str(e)}",
                        confidence=0.5,
                    )
                )

        # Calculate metrics
        result.metrics = self._calculate_metrics(result)

        # Determine overall status
        result.overall_status = self._determine_overall_status(result)

        # Cache result
        if self.cache is not None:
            self.cache[cache_key] = result

        # Add to history
        self.history.append(result)

        return result

    def _get_cache_key(
        self, source_text: str, translated_text: str, source_lang: str, target_lang: str
    ) -> str:
        """Generate cache key for validation result."""
        return (
            f"{source_lang}:{target_lang}:{hash(source_text)}:{hash(translated_text)}"
        )

    def _calculate_metrics(self, result: ValidationResult) -> TranslationMetrics:
        """Calculate validation metrics."""
        # Extract similarity scores from metadata if available
        similarity_scores = result.metadata.get("similarity_scores", {})
        semantic_similarity = similarity_scores.get("semantic")

        metrics = TranslationMetrics(
            total_validations=len(self.validators),
            passed_validations=len(self.validators) - len(result.issues),
            failed_validations=result.error_count,
            warnings=result.warning_count,
            confidence_score=self._calculate_confidence(result),
            validation_time=(datetime.now() - result.timestamp).total_seconds(),
            semantic_similarity=semantic_similarity,
        )

        # Add other similarity metrics if available
        if "medical" in similarity_scores:
            metrics.terminology_accuracy = similarity_scores["medical"]
        if "composite_similarity_score" in result.metadata:
            # Store composite score in fluency_score as a proxy
            metrics.fluency_score = result.metadata["composite_similarity_score"]

        return metrics

    def _calculate_confidence(self, result: ValidationResult) -> float:
        """Calculate overall confidence score."""
        if not result.issues:
            return 1.0

        # Weight by severity
        severity_weights = {ValidationStatus.WARNING: 0.9, ValidationStatus.FAILED: 0.5}

        confidence = 1.0
        for issue in result.issues:
            weight = severity_weights.get(issue.severity, 1.0)
            confidence *= weight * issue.confidence

        return max(0.0, min(1.0, confidence))

    def _determine_overall_status(self, result: ValidationResult) -> ValidationStatus:
        """Determine overall validation status."""
        if result.error_count > self.config.max_acceptable_errors:
            return ValidationStatus.FAILED
        elif result.warning_count > self.config.max_acceptable_warnings:
            return ValidationStatus.WARNING
        elif (
            result.metrics
            and result.metrics.confidence_score < self.config.min_confidence_threshold
        ):
            return ValidationStatus.WARNING
        else:
            return ValidationStatus.PASSED

    def validate_batch(
        self, translations: List[Tuple[str, str, str, str]]
    ) -> List[ValidationResult]:
        """Validate multiple translations."""
        results = []

        for source_text, translated_text, source_lang, target_lang in translations:
            result = self.validate(
                source_text, translated_text, source_lang, target_lang
            )
            results.append(result)

        return results

    def get_validation_summary(self) -> Dict[str, Any]:
        """Get summary of all validations performed."""
        if not self.history:
            return {"message": "No validations performed yet"}

        return {
            "total_validations": len(self.history),
            "passed": sum(1 for r in self.history if r.passed),
            "failed": sum(1 for r in self.history if not r.passed),
            "average_confidence": sum(
                r.metrics.confidence_score for r in self.history if r.metrics
            )
            / len(self.history),
            "common_issues": self._get_common_issues(),
            "language_pairs": self._get_language_pair_stats(),
        }

    def _get_common_issues(self) -> List[Dict[str, Any]]:
        """Analyze common validation issues."""
        issue_counts = {}

        for result in self.history:
            for issue in result.issues:
                key = (issue.validator, issue.message)
                if key not in issue_counts:
                    issue_counts[key] = 0
                issue_counts[key] += 1

        # Sort by frequency
        sorted_issues = sorted(issue_counts.items(), key=lambda x: x[1], reverse=True)

        return [
            {"validator": validator, "message": message, "count": count}
            for (validator, message), count in sorted_issues[:10]
        ]

    def _get_language_pair_stats(self) -> Dict[str, Dict[str, int]]:
        """Get statistics by language pair."""
        stats = {}

        for result in self.history:
            pair = f"{result.source_lang}->{result.target_lang}"
            if pair not in stats:
                stats[pair] = {"total": 0, "passed": 0, "failed": 0}

            stats[pair]["total"] += 1
            if result.passed:
                stats[pair]["passed"] += 1
            else:
                stats[pair]["failed"] += 1

        return stats

    def export_report(self, filepath: str, format_type: str = "json") -> None:
        """Export validation report."""
        summary = self.get_validation_summary()

        if format_type == "json":
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(summary, f, indent=2)
        else:
            raise ValueError(f"Unsupported format: {format_type}")
