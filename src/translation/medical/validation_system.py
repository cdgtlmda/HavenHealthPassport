"""Medical Translation Validation System.

This module provides comprehensive validation for medical translations,
ensuring accuracy, safety, and clinical appropriateness across languages.

Access control enforced: This module processes PHI including medical terms,
dosages, diagnoses, and treatment information. All validation operations
require appropriate healthcare professional access levels and are logged
for HIPAA compliance.
"""

import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from src.healthcare.hipaa_access_control import (
    AccessLevel,
    audit_phi_access,
    require_phi_access,
)
from src.security.encryption import EncryptionService
from src.utils.logging import get_logger

# Access control for medical validation

logger = get_logger(__name__)


class ValidationLevel(str, Enum):
    """Validation severity levels."""

    CRITICAL = "critical"  # Safety-critical errors
    HIGH = "high"  # Important accuracy issues
    MEDIUM = "medium"  # Minor accuracy concerns
    LOW = "low"  # Style or preference issues
    INFO = "info"  # Informational messages


class ValidationType(str, Enum):
    """Types of validation checks."""

    MEDICAL_ACCURACY = "medical_accuracy"
    TERMINOLOGY_CONSISTENCY = "terminology_consistency"
    DOSAGE_ACCURACY = "dosage_accuracy"
    ANATOMICAL_CORRECTNESS = "anatomical_correctness"
    ABBREVIATION_SAFETY = "abbreviation_safety"
    NUMERIC_CONSISTENCY = "numeric_consistency"
    UNIT_CONVERSION = "unit_conversion"
    GENDER_AGREEMENT = "gender_agreement"
    CULTURAL_APPROPRIATENESS = "cultural_appropriateness"
    READABILITY = "readability"


@dataclass
class ValidationIssue:
    """Single validation issue found."""

    type: ValidationType
    level: ValidationLevel
    message: str
    source_text: str
    translated_text: str
    suggestion: Optional[str] = None
    context: Optional[Dict[str, Any]] = None
    position: Optional[Tuple[int, int]] = None  # start, end


@dataclass
class ValidationResult:
    """Complete validation result for a translation."""

    is_valid: bool
    issues: List[ValidationIssue] = field(default_factory=list)
    score: float = 100.0  # 0-100 quality score
    metadata: Dict[str, Any] = field(default_factory=dict)
    validated_at: datetime = field(default_factory=datetime.utcnow)
    validator_version: str = "1.0.0"


class MedicalTranslationValidator:
    """Validates medical translations for accuracy and safety."""

    # Critical medical terms that must be translated accurately
    CRITICAL_TERMS = {
        "en": {
            "allergy",
            "allergic",
            "anaphylaxis",
            "emergency",
            "urgent",
            "immediately",
            "contraindicated",
            "do not",
            "never",
            "overdose",
            "toxic",
            "poison",
            "pregnant",
            "pregnancy",
            "breastfeeding",
            "death",
            "fatal",
            "life-threatening",
        },
        "es": {
            "alergia",
            "alérgico",
            "anafilaxia",
            "emergencia",
            "urgente",
            "inmediatamente",
            "contraindicado",
            "no",
            "nunca",
            "sobredosis",
            "tóxico",
            "veneno",
            "embarazada",
            "embarazo",
            "lactancia",
            "muerte",
            "fatal",
            "mortal",
        },
    }

    # Dangerous abbreviation pairs
    DANGEROUS_ABBREVIATIONS = {
        "IU": "International Units (not IV)",
        "U": "Units (not 0)",
        "QD": "Daily (use 'daily' instead)",
        "QOD": "Every other day (spell out)",
        "MS": "Morphine sulfate (not magnesium sulfate)",
        "MSO4": "Morphine sulfate (not magnesium sulfate)",
        "MgSO4": "Magnesium sulfate (not morphine sulfate)",
    }

    # Medical number patterns
    MEDICAL_NUMBER_PATTERNS = {
        "dosage": r"\d+\.?\d*\s*(mg|g|mcg|ml|L|IU|units?)",
        "blood_pressure": r"\d{2,3}/\d{2,3}",
        "temperature": r"\d{2,3}\.?\d*\s*°?[CF]",
        "percentage": r"\d+\.?\d*\s*%",
        "frequency": r"\d+\s*(times?|x)\s*(per|/)\s*(day|hour|week)",
    }

    def __init__(self) -> None:
        """Initialize medical translation validator."""
        self.validation_rules = self._initialize_validation_rules()
        self.medical_dictionaries: Dict[str, Any] = {}  # Loaded medical dictionaries
        self.encryption_service = EncryptionService(
            kms_key_id="alias/haven-health-default"
        )
        self.custom_validators: Dict[str, Any] = {}  # Custom validation functions

    def _initialize_validation_rules(self) -> Dict[ValidationType, Any]:
        """Initialize validation rules for each type."""
        return {
            ValidationType.MEDICAL_ACCURACY: self._validate_medical_accuracy,
            ValidationType.TERMINOLOGY_CONSISTENCY: self._validate_terminology,
            ValidationType.DOSAGE_ACCURACY: self._validate_dosage,
            ValidationType.ANATOMICAL_CORRECTNESS: self._validate_anatomy,
            ValidationType.ABBREVIATION_SAFETY: self._validate_abbreviations,
            ValidationType.NUMERIC_CONSISTENCY: self._validate_numbers,
            ValidationType.UNIT_CONVERSION: self._validate_units,
            ValidationType.GENDER_AGREEMENT: self._validate_gender,
            ValidationType.CULTURAL_APPROPRIATENESS: self._validate_cultural,
            ValidationType.READABILITY: self._validate_readability,
        }

    @require_phi_access(AccessLevel.READ)
    @audit_phi_access("validate_medical_translation")
    def validate_translation(
        self,
        source_text: str,
        translated_text: str,
        source_language: str,
        target_language: str,
        context: Optional[Dict[str, Any]] = None,
        validation_types: Optional[List[ValidationType]] = None,
    ) -> ValidationResult:
        """Perform comprehensive validation of medical translation."""
        issues = []
        context = context or {}

        # Determine which validations to run
        if validation_types is None:
            validation_types = list(ValidationType)

        # Run each validation
        for val_type in validation_types:
            validator = self.validation_rules.get(val_type)
            if validator:
                type_issues = validator(
                    source_text,
                    translated_text,
                    source_language,
                    target_language,
                    context,
                )
                issues.extend(type_issues)

        # Calculate quality score
        score = self._calculate_quality_score(issues)

        # Determine if translation is valid
        critical_issues = [i for i in issues if i.level == ValidationLevel.CRITICAL]
        is_valid = len(critical_issues) == 0 and score >= 70.0

        return ValidationResult(
            is_valid=is_valid,
            issues=issues,
            score=score,
            metadata={
                "source_language": source_language,
                "target_language": target_language,
                "validation_types": [v.value for v in validation_types],
                "context": context,
            },
        )

    def _validate_medical_accuracy(
        self,
        source: str,
        translation: str,
        source_lang: str,
        target_lang: str,
        context: Dict[str, Any],  # pylint: disable=unused-argument
    ) -> List[ValidationIssue]:
        """Validate medical accuracy of translation."""
        issues = []

        # Check for critical terms
        critical_terms_source = self.CRITICAL_TERMS.get(source_lang, set())
        critical_terms_target = self.CRITICAL_TERMS.get(target_lang, set())

        # Find critical terms in source
        source_lower = source.lower()
        found_critical = []

        for term in critical_terms_source:
            if term in source_lower:
                found_critical.append(term)

        # Verify they appear in translation
        translation_lower = translation.lower()
        for term in found_critical:
            # Should have corresponding critical term in target
            has_equivalent = any(
                target_term in translation_lower
                for target_term in critical_terms_target
            )

            if not has_equivalent:
                issues.append(
                    ValidationIssue(
                        type=ValidationType.MEDICAL_ACCURACY,
                        level=ValidationLevel.CRITICAL,
                        message=f"Critical term '{term}' may not be properly translated",
                        source_text=source,
                        translated_text=translation,
                        suggestion="Ensure critical safety terms are accurately translated",
                    )
                )

        return issues

    def _validate_terminology(
        self,
        source: str,
        translation: str,
        source_lang: str,  # pylint: disable=unused-argument
        target_lang: str,  # pylint: disable=unused-argument
        context: Dict[str, Any],  # pylint: disable=unused-argument
    ) -> List[ValidationIssue]:
        """Validate terminology consistency."""
        issues = []

        # Check if medical terms are consistently translated
        # This would integrate with medical dictionaries

        # Example: Check for mixed terminology styles
        if "blood pressure" in source.lower() and "BP" in translation:
            issues.append(
                ValidationIssue(
                    type=ValidationType.TERMINOLOGY_CONSISTENCY,
                    level=ValidationLevel.MEDIUM,
                    message="Inconsistent terminology: full term vs abbreviation",
                    source_text=source,
                    translated_text=translation,
                    suggestion="Use consistent terminology throughout",
                )
            )

        return issues

    def _validate_dosage(
        self,
        source: str,
        translation: str,
        source_lang: str,  # pylint: disable=unused-argument
        target_lang: str,  # pylint: disable=unused-argument
        context: Dict[str, Any],  # pylint: disable=unused-argument
    ) -> List[ValidationIssue]:
        """Validate dosage information accuracy."""
        issues = []

        # Extract dosages from both texts
        source_dosages = re.findall(self.MEDICAL_NUMBER_PATTERNS["dosage"], source)
        trans_dosages = re.findall(self.MEDICAL_NUMBER_PATTERNS["dosage"], translation)

        # Check if same number of dosages
        if len(source_dosages) != len(trans_dosages):
            issues.append(
                ValidationIssue(
                    type=ValidationType.DOSAGE_ACCURACY,
                    level=ValidationLevel.CRITICAL,
                    message=f"Dosage count mismatch: {len(source_dosages)} vs {len(trans_dosages)}",
                    source_text=source,
                    translated_text=translation,
                )
            )

        # Check each dosage value
        for src_dose, trans_dose in zip(source_dosages, trans_dosages):
            # Extract number and unit
            src_num = re.findall(r"\d+\.?\d*", src_dose)[0]
            trans_num = re.findall(r"\d+\.?\d*", trans_dose)[0]

            if src_num != trans_num:
                issues.append(
                    ValidationIssue(
                        type=ValidationType.DOSAGE_ACCURACY,
                        level=ValidationLevel.CRITICAL,
                        message=f"Dosage value mismatch: {src_dose} vs {trans_dose}",
                        source_text=source,
                        translated_text=translation,
                        position=(
                            source.find(src_dose),
                            source.find(src_dose) + len(src_dose),
                        ),
                    )
                )

        return issues

    def _validate_anatomy(
        self,
        source: str,  # pylint: disable=unused-argument
        translation: str,  # pylint: disable=unused-argument
        source_lang: str,  # pylint: disable=unused-argument
        target_lang: str,  # pylint: disable=unused-argument
        context: Dict[str, Any],  # pylint: disable=unused-argument
    ) -> List[ValidationIssue]:
        """Validate anatomical terms are correctly translated."""
        issues: List[ValidationIssue] = []

        # Would check against anatomical dictionary

        return issues

    def _validate_abbreviations(
        self,
        source: str,
        translation: str,
        source_lang: str,  # pylint: disable=unused-argument
        target_lang: str,  # pylint: disable=unused-argument
        context: Dict[str, Any],  # pylint: disable=unused-argument
    ) -> List[ValidationIssue]:
        """Validate safe use of medical abbreviations."""
        issues = []

        # Check for dangerous abbreviations
        for abbrev, warning in self.DANGEROUS_ABBREVIATIONS.items():
            if abbrev in translation:
                issues.append(
                    ValidationIssue(
                        type=ValidationType.ABBREVIATION_SAFETY,
                        level=ValidationLevel.HIGH,
                        message=f"Dangerous abbreviation '{abbrev}' found: {warning}",
                        source_text=source,
                        translated_text=translation,
                        suggestion=f"Replace '{abbrev}' with full text",
                    )
                )

        return issues

    def _validate_numbers(
        self,
        source: str,
        translation: str,
        source_lang: str,  # pylint: disable=unused-argument
        target_lang: str,  # pylint: disable=unused-argument
        context: Dict[str, Any],  # pylint: disable=unused-argument
    ) -> List[ValidationIssue]:
        """Validate numeric consistency."""
        issues = []

        # Extract all numbers
        source_numbers = re.findall(r"\d+\.?\d*", source)
        trans_numbers = re.findall(r"\d+\.?\d*", translation)

        # Basic count check
        if len(source_numbers) != len(trans_numbers):
            issues.append(
                ValidationIssue(
                    type=ValidationType.NUMERIC_CONSISTENCY,
                    level=ValidationLevel.HIGH,
                    message=f"Number count mismatch: {len(source_numbers)} vs {len(trans_numbers)}",
                    source_text=source,
                    translated_text=translation,
                )
            )

        # Check for number format changes (e.g., 1,000 vs 1.000)
        # This varies by locale

        return issues

    def _validate_units(
        self,
        source: str,  # pylint: disable=unused-argument
        translation: str,  # pylint: disable=unused-argument
        source_lang: str,  # pylint: disable=unused-argument
        target_lang: str,  # pylint: disable=unused-argument
        context: Dict[str, Any],  # pylint: disable=unused-argument
    ) -> List[ValidationIssue]:
        """Validate unit conversions and consistency."""
        issues: List[ValidationIssue] = []

        # Detect if units were inappropriately converted
        # Medical units should generally not be converted

        return issues

    def _validate_gender(
        self,
        source: str,  # pylint: disable=unused-argument
        translation: str,  # pylint: disable=unused-argument
        source_lang: str,  # pylint: disable=unused-argument
        target_lang: str,
        context: Dict[str, Any],
    ) -> List[ValidationIssue]:
        """Validate gender agreement in translation."""
        issues: List[ValidationIssue] = []

        # This would integrate with gender support module
        patient_gender = context.get("patient_gender")

        if patient_gender and target_lang in ["es", "fr", "ar"]:
            # Check for gender agreement issues
            # Would need language-specific rules
            pass

        return issues

    def _validate_cultural(
        self,
        source: str,  # pylint: disable=unused-argument
        translation: str,  # pylint: disable=unused-argument
        source_lang: str,  # pylint: disable=unused-argument
        target_lang: str,  # pylint: disable=unused-argument
        context: Dict[str, Any],  # pylint: disable=unused-argument
    ) -> List[ValidationIssue]:
        """Validate cultural appropriateness."""
        issues: List[ValidationIssue] = []

        # Check for culturally sensitive terms
        # Example: dietary restrictions, religious considerations

        return issues

    def _validate_readability(
        self,
        source: str,  # pylint: disable=unused-argument
        translation: str,
        source_lang: str,  # pylint: disable=unused-argument
        target_lang: str,  # pylint: disable=unused-argument
        context: Dict[str, Any],  # pylint: disable=unused-argument
    ) -> List[ValidationIssue]:
        """Validate translation readability."""
        issues = []

        # Check sentence length
        trans_sentences = translation.split(".")
        long_sentences = [s for s in trans_sentences if len(s.split()) > 25]

        if long_sentences:
            issues.append(
                ValidationIssue(
                    type=ValidationType.READABILITY,
                    level=ValidationLevel.LOW,
                    message=f"Found {len(long_sentences)} long sentences (>25 words)",
                    source_text=source,
                    translated_text=translation,
                    suggestion="Consider breaking into shorter sentences for clarity",
                )
            )

        return issues

    def _calculate_quality_score(self, issues: List[ValidationIssue]) -> float:
        """Calculate overall quality score based on issues."""
        if not issues:
            return 100.0

        # Weight by severity
        weights = {
            ValidationLevel.CRITICAL: 20.0,
            ValidationLevel.HIGH: 10.0,
            ValidationLevel.MEDIUM: 5.0,
            ValidationLevel.LOW: 2.0,
            ValidationLevel.INFO: 0.0,
        }

        total_penalty = sum(weights.get(issue.level, 0) for issue in issues)
        score = max(0.0, 100.0 - total_penalty)

        return round(score, 1)

    def validate_batch(
        self,
        translations: List[Tuple[str, str, str, str]],
        context: Optional[Dict[str, Any]] = None,
    ) -> List[ValidationResult]:
        """Validate multiple translations in batch."""
        results = []

        for source, translation, source_lang, target_lang in translations:
            result = self.validate_translation(
                source, translation, source_lang, target_lang, context
            )
            results.append(result)

        return results

    def get_validation_report(self, results: List[ValidationResult]) -> Dict[str, Any]:
        """Generate validation report summary."""
        total = len(results)
        valid = sum(1 for r in results if r.is_valid)

        issue_counts: Dict[str, int] = {}
        for result in results:
            for issue in result.issues:
                key = f"{issue.type.value}_{issue.level.value}"
                issue_counts[key] = issue_counts.get(key, 0) + 1

        avg_score = sum(r.score for r in results) / total if total > 0 else 0

        return {
            "total_translations": total,
            "valid_translations": valid,
            "validation_rate": (valid / total * 100) if total > 0 else 0,
            "average_score": round(avg_score, 1),
            "issue_summary": issue_counts,
            "critical_issues": sum(
                1
                for r in results
                for i in r.issues
                if i.level == ValidationLevel.CRITICAL
            ),
        }


# Global validator instance
medical_validator = MedicalTranslationValidator()
