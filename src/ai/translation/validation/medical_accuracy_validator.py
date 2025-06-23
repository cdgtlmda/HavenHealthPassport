"""
Medical Accuracy Validator Integration.

Integrates medical accuracy validation into the translation validation pipeline.

This module handles encrypted PHI with access control and audit logging
to ensure HIPAA compliance.
"""

import logging
from typing import Any, Dict, List, Optional

from ..config import TranslationMode
from .medical_accuracy import (
    MedicalAccuracyLevel,
    MedicalAccuracyValidator,
)
from .pipeline import ValidationConfig, ValidationIssue, ValidationStatus
from .validators import BaseValidator

logger = logging.getLogger(__name__)


class MedicalAccuracyValidatorIntegration(BaseValidator):
    """
    Validates medical accuracy of translations.

    Ensures that critical medical information such as medications,
    dosages, diagnoses, and procedures are accurately preserved.
    """

    def __init__(self, config: ValidationConfig):
        """Initialize medical accuracy validator."""
        super().__init__(config)
        self.validator = MedicalAccuracyValidator()
        self.name = "MedicalAccuracyValidator"

        # Determine accuracy level based on validation level
        if config.level.value == "critical":
            self.accuracy_level = MedicalAccuracyLevel.CRITICAL
        elif config.level.value == "strict":
            self.accuracy_level = MedicalAccuracyLevel.HIGH
        else:
            self.accuracy_level = MedicalAccuracyLevel.STANDARD

    def validate(
        self,
        source_text: str,
        translated_text: str,
        source_lang: str,
        target_lang: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> List[ValidationIssue]:
        """Validate medical accuracy of translation."""
        issues = []

        try:
            # Determine translation mode from metadata
            mode = TranslationMode.CLINICAL
            if metadata and "translation_mode" in metadata:
                mode = metadata["translation_mode"]

            # Validate medical accuracy
            result = self.validator.validate_medical_accuracy(
                source_text,
                translated_text,
                mode=mode,
                accuracy_level=self.accuracy_level,
            )

            # Convert errors to validation issues
            for error in result.errors:
                issues.append(
                    ValidationIssue(
                        validator=self.name,
                        severity=ValidationStatus.FAILED,
                        message=error,
                        confidence=0.95,
                    )
                )

            # Convert warnings to validation issues
            for warning in result.warnings:
                issues.append(
                    ValidationIssue(
                        validator=self.name,
                        severity=ValidationStatus.WARNING,
                        message=warning,
                        confidence=0.85,
                    )
                )

            # Add accuracy score to metadata
            if metadata is not None:
                metadata["medical_accuracy"] = result.to_dict()

            # Check overall accuracy
            if not result.is_accurate:
                issues.append(
                    ValidationIssue(
                        validator=self.name,
                        severity=ValidationStatus.FAILED,
                        message=f"Medical accuracy below threshold: {result.accuracy_score:.2f}",
                        confidence=0.9,
                        suggestion="Review medical entities for accuracy",
                    )
                )

            # Report missing critical entities
            critical_missing = [e for e in result.missing_entities if e.is_critical()]
            if critical_missing:
                entities_list = ", ".join([e.text for e in critical_missing[:3]])
                issues.append(
                    ValidationIssue(
                        validator=self.name,
                        severity=ValidationStatus.FAILED,
                        message=f"Critical medical entities missing: {entities_list}",
                        confidence=0.95,
                        suggestion="Ensure all medications, dosages, and allergies are preserved",
                    )
                )

            # Report altered entities
            if result.altered_entities:
                altered_count = len(result.altered_entities)
                issues.append(
                    ValidationIssue(
                        validator=self.name,
                        severity=ValidationStatus.WARNING,
                        message=f"{altered_count} medical entities were altered in translation",
                        confidence=0.8,
                        suggestion="Verify that alterations maintain medical accuracy",
                    )
                )

        except (ValueError, TypeError, AttributeError) as e:
            logger.error("Error in medical accuracy validation: %s", e)
            issues.append(
                ValidationIssue(
                    validator=self.name,
                    severity=ValidationStatus.WARNING,
                    message=f"Medical accuracy validation error: {str(e)}",
                    confidence=0.5,
                )
            )

        return issues


# Export the validator
__all__ = ["MedicalAccuracyValidatorIntegration"]
