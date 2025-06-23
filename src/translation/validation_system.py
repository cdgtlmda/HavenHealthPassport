"""
Medical Translation Validation System.

This module provides validation for medical translations to ensure accuracy,
context appropriateness, and safety in healthcare communications.
"""

import re
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from src.security.access_control import AccessPermission, require_permission
from src.security.audit import audit_phi_access
from src.services.encryption_service import EncryptionService
from src.translation.context_manager import TranslationContextManager
from src.translation.medical_glossary import MedicalGlossaryService
from src.translation.medical_term_verifier import get_medical_term_verifier
from src.translation.medical_terminology_validator import MedicalTerminologyValidator
from src.utils.logging import get_logger

logger = get_logger(__name__)


class ValidationSeverity(str, Enum):
    """Severity levels for validation issues."""

    ERROR = "error"  # Translation is unsafe or incorrect
    WARNING = "warning"  # Translation may be problematic
    INFO = "info"  # Informational issue
    SUGGESTION = "suggestion"  # Improvement suggestion


class ValidationType(str, Enum):
    """Types of validation checks."""

    MEDICAL_ACCURACY = "medical_accuracy"
    TERMINOLOGY_CONSISTENCY = "terminology_consistency"
    CONTEXT_APPROPRIATENESS = "context_appropriateness"
    CULTURAL_SENSITIVITY = "cultural_sensitivity"
    DOSAGE_ACCURACY = "dosage_accuracy"
    UNIT_CONSISTENCY = "unit_consistency"
    ABBREVIATION_CLARITY = "abbreviation_clarity"
    CRITICAL_SAFETY = "critical_safety"


@dataclass
class ValidationIssue:
    """Represents a validation issue found in translation."""

    type: ValidationType
    severity: ValidationSeverity
    message: str
    source_text: str
    translated_text: str
    suggestion: Optional[str] = None
    position: Optional[Tuple[int, int]] = None  # Start, end position


@dataclass
class ValidationResult:
    """Result of translation validation."""

    is_valid: bool
    issues: List[ValidationIssue]
    score: float  # 0-100 quality score
    metadata: Dict[str, Any]


class MedicalTranslationValidator:
    """Validates medical translations for accuracy and safety."""

    # Critical medical terms that require exact translation
    CRITICAL_TERMS = {
        "emergency",
        "urgent",
        "critical",
        "severe",
        "acute",
        "allergic",
        "anaphylaxis",
        "overdose",
        "contraindication",
        "do not",
        "must not",
        "warning",
        "danger",
        "caution",
    }

    # Common mistranslation patterns
    MISTRANSLATION_PATTERNS = [
        # Dosage confusions
        (r"\b(\d+)\s*mg\b", r"\b(\d+)\s*g\b", "Potential mg/g confusion"),
        (r"\bonce\s+daily\b", r"\bonce\b", "Missing frequency information"),
        (r"\btake\s+(\d+)\b", r"\bgive\s+(\d+)\b", "Action verb confusion"),
        # Negation errors
        (r"\bnot\s+safe\b", r"\bsafe\b", "Critical negation missing"),
        (r"\bdo\s+not\b", r"\bdo\b", "Critical negation missing"),
        # Time/frequency errors
        (
            r"\bevery\s+(\d+)\s+hours?\b",
            r"\b(\d+)\s+times?\b",
            "Frequency mistranslation",
        ),
    ]

    # Medical abbreviations that should be expanded
    AMBIGUOUS_ABBREVIATIONS = {
        "q.d.": ["once daily", "every day"],
        "b.i.d.": ["twice daily", "two times a day"],
        "t.i.d.": ["three times daily", "three times a day"],
        "q.i.d.": ["four times daily", "four times a day"],
        "p.r.n.": ["as needed", "when necessary"],
        "p.o.": ["by mouth", "orally"],
        "i.m.": ["intramuscular", "into muscle"],
        "i.v.": ["intravenous", "into vein"],
    }

    def __init__(
        self,
        glossary_service: MedicalGlossaryService,
        terminology_validator: MedicalTerminologyValidator,
        context_manager: TranslationContextManager,
    ):
        """Initialize the validator."""
        self.glossary = glossary_service
        self.terminology = terminology_validator
        self.context = context_manager
        self.encryption_service = EncryptionService()

    async def validate_translation(
        self,
        source_text: str,
        translated_text: str,
        source_lang: str,
        target_lang: str,
        context_type: Optional[str] = None,
    ) -> ValidationResult:
        """
        Validate a medical translation.

        Args:
            source_text: Original text
            translated_text: Translated text
            source_lang: Source language code
            target_lang: Target language code
            context_type: Medical context (e.g., prescription, diagnosis)

        Returns:
            Validation result with issues and score
        """
        issues = []

        # Run all validation checks
        issues.extend(
            self._check_medical_accuracy(
                source_text, translated_text, source_lang, target_lang
            )
        )
        issues.extend(
            self._check_terminology_consistency(
                source_text, translated_text, source_lang, target_lang
            )
        )
        issues.extend(
            await self._check_critical_safety(
                source_text, translated_text, source_lang, target_lang
            )
        )
        issues.extend(self._check_dosage_accuracy(source_text, translated_text))
        issues.extend(self._check_unit_consistency(source_text, translated_text))
        issues.extend(self._check_abbreviations(translated_text, target_lang))

        if context_type:
            issues.extend(
                self._check_context_appropriateness(
                    translated_text, context_type, target_lang
                )
            )

        # Calculate quality score
        score = self._calculate_quality_score(issues)

        # Determine if translation is valid
        has_errors = any(issue.severity == ValidationSeverity.ERROR for issue in issues)
        is_valid = not has_errors and score >= 70

        return ValidationResult(
            is_valid=is_valid,
            issues=issues,
            score=score,
            metadata={
                "source_lang": source_lang,
                "target_lang": target_lang,
                "context_type": context_type,
                "checked_at": datetime.utcnow().isoformat(),
            },
        )

    def _check_medical_accuracy(
        self, source: str, translated: str, source_lang: str, target_lang: str
    ) -> List[ValidationIssue]:
        """Check medical term accuracy."""
        issues = []

        # Extract medical terms from source
        source_terms = self._extract_medical_terms(source, source_lang)

        for term in source_terms:
            # Get expected translation
            expected_translation = self.glossary.get_term_translation(
                term, target_lang, source_lang
            )

            if (
                expected_translation
                and expected_translation.lower() not in translated.lower()
            ):
                issues.append(
                    ValidationIssue(
                        type=ValidationType.MEDICAL_ACCURACY,
                        severity=ValidationSeverity.WARNING,
                        message=f"Medical term '{term}' may be mistranslated",
                        source_text=term,
                        translated_text=translated,
                        suggestion=expected_translation,
                    )
                )

        return issues

    def _check_terminology_consistency(
        self, source: str, translated: str, source_lang: str, target_lang: str
    ) -> List[ValidationIssue]:
        """Check for consistent terminology usage."""
        issues = []

        # Check if standardized terminology is used
        is_valid, _ = self.terminology.validate_medical_terms(translated, target_lang)
        if not is_valid:
            issues.append(
                ValidationIssue(
                    type=ValidationType.TERMINOLOGY_CONSISTENCY,
                    severity=ValidationSeverity.WARNING,
                    message=f"Non-standard medical terminology detected when translating from {source_lang}",
                    source_text=source,
                    translated_text=translated,
                )
            )

        return issues

    async def _check_critical_safety(
        self, source: str, translated: str, source_lang: str, target_lang: str
    ) -> List[ValidationIssue]:
        """Check critical safety terms."""
        issues = []

        # Check for critical terms in source
        source_lower = source.lower()
        for critical_term in self.CRITICAL_TERMS:
            if critical_term in source_lower:
                # CRITICAL: Verify medical terms are properly translated
                # Must check for language-appropriate medical equivalents
                if not await self._verify_medical_term_translation(
                    critical_term, source, translated, source_lang, target_lang
                ):
                    issues.append(
                        ValidationIssue(
                            type=ValidationType.CRITICAL_SAFETY,
                            severity=ValidationSeverity.ERROR,
                            message=f"Critical safety term '{critical_term}' not properly translated",
                            source_text=source,
                            translated_text=translated,
                        )
                    )

        # Check for mistranslation patterns with context awareness
        for source_pattern, target_pattern, message in self.MISTRANSLATION_PATTERNS:
            if re.search(source_pattern, source):
                # Verify the translation doesn't contain dangerous patterns
                if re.search(target_pattern, translated):
                    # Additional context check to reduce false positives
                    if await self._confirm_mistranslation(
                        source, translated, source_pattern, target_pattern
                    ):
                        issues.append(
                            ValidationIssue(
                                type=ValidationType.CRITICAL_SAFETY,
                                severity=ValidationSeverity.ERROR,
                                message=message,
                                source_text=source,
                                translated_text=translated,
                            )
                        )

        return issues

    def _check_dosage_accuracy(
        self, source: str, translated: str
    ) -> List[ValidationIssue]:
        """Check dosage information accuracy."""
        issues = []

        # Extract dosage information
        source_dosages = self._extract_dosages(source)
        translated_dosages = self._extract_dosages(translated)

        # Check if all dosages are preserved
        if len(source_dosages) != len(translated_dosages):
            issues.append(
                ValidationIssue(
                    type=ValidationType.DOSAGE_ACCURACY,
                    severity=ValidationSeverity.ERROR,
                    message="Dosage information count mismatch",
                    source_text=source,
                    translated_text=translated,
                )
            )

        # Check individual dosages
        for src_dosage in source_dosages:
            if not any(
                self._dosages_match(src_dosage, trans_dosage)
                for trans_dosage in translated_dosages
            ):
                issues.append(
                    ValidationIssue(
                        type=ValidationType.DOSAGE_ACCURACY,
                        severity=ValidationSeverity.ERROR,
                        message=f"Dosage '{src_dosage}' not correctly translated",
                        source_text=source,
                        translated_text=translated,
                    )
                )

        return issues

    def _check_unit_consistency(
        self, source: str, translated: str
    ) -> List[ValidationIssue]:
        """Check unit consistency."""
        issues = []

        # Extract units
        source_units = self._extract_units(source)
        translated_units = self._extract_units(translated)

        # Simplified check - in production would be more sophisticated
        if len(source_units) != len(translated_units):
            issues.append(
                ValidationIssue(
                    type=ValidationType.UNIT_CONSISTENCY,
                    severity=ValidationSeverity.WARNING,
                    message="Unit count mismatch between source and translation",
                    source_text=source,
                    translated_text=translated,
                )
            )

        return issues

    def _check_abbreviations(
        self, translated: str, target_lang: str
    ) -> List[ValidationIssue]:
        """Check for ambiguous abbreviations."""
        issues = []

        # Language-specific abbreviation checks
        lang_specific_abbr = self._get_language_specific_abbreviations(target_lang)

        for abbr, expansions in self.AMBIGUOUS_ABBREVIATIONS.items():
            if abbr in translated.lower():
                # Get language-appropriate expansion
                suggestion = lang_specific_abbr.get(abbr, expansions[0])
                issues.append(
                    ValidationIssue(
                        type=ValidationType.ABBREVIATION_CLARITY,
                        severity=ValidationSeverity.WARNING,
                        message=f"Ambiguous abbreviation '{abbr}' should be expanded in {target_lang}",
                        source_text=abbr,
                        translated_text=translated,
                        suggestion=suggestion,
                    )
                )

        return issues

    def _check_context_appropriateness(
        self, translated: str, _context_type: str, target_lang: str
    ) -> List[ValidationIssue]:
        """Check if translation is appropriate for context."""
        issues = []

        # Get context requirements
        # TODO: Implement get_context_requirements method in TranslationContextManager
        context_requirements: Dict[str, Any] = {}  # Default empty requirements

        # Check formality level
        if context_requirements.get("formality") == "high":
            # Get language-specific informal markers
            informal_markers = self._get_informal_markers(target_lang)

            if any(informal in translated.lower() for informal in informal_markers):
                issues.append(
                    ValidationIssue(
                        type=ValidationType.CONTEXT_APPROPRIATENESS,
                        severity=ValidationSeverity.WARNING,
                        message=f"Informal language detected in formal medical context for {target_lang}",
                        source_text="",
                        translated_text=translated,
                    )
                )

        return issues

    @audit_phi_access("phi_access__extract_medical_terms")
    @require_permission(AccessPermission.READ_PHI)
    def _extract_medical_terms(self, text: str, language: str) -> List[str]:
        """Extract medical terms from text."""
        # Simplified extraction - would use NLP in production
        terms = []
        words = text.lower().split()

        for word in words:
            # Check if word is in medical glossary
            if self.glossary.search_terms(word, language, limit=1):
                terms.append(word)

        return terms

    @audit_phi_access("phi_access__extract_dosages")
    @require_permission(AccessPermission.READ_PHI)
    def _extract_dosages(self, text: str) -> List[str]:
        """Extract dosage information from text."""
        # Pattern for dosages (simplified)
        pattern = r"\b(\d+(?:\.\d+)?)\s*(mg|g|ml|mcg|unit|tablet|capsule)s?\b"
        return re.findall(pattern, text, re.IGNORECASE)

    @audit_phi_access("phi_access__extract_units")
    @require_permission(AccessPermission.READ_PHI)
    def _extract_units(self, text: str) -> List[str]:
        """Extract measurement units from text."""
        # Pattern for units (simplified)
        pattern = r"\b(mg|g|kg|ml|l|cm|m|°C|°F)\b"
        return re.findall(pattern, text, re.IGNORECASE)

    def _dosages_match(
        self, dosage1: Tuple[str, str], dosage2: Tuple[str, str]
    ) -> bool:
        """Check if two dosages match."""
        # Compare numeric value and unit
        return dosage1[0] == dosage2[0] and dosage1[1].lower() == dosage2[1].lower()

    def _calculate_quality_score(self, issues: List[ValidationIssue]) -> float:
        """Calculate quality score based on issues."""
        if not issues:
            return 100.0

        # Weight by severity
        weights = {
            ValidationSeverity.ERROR: 25,
            ValidationSeverity.WARNING: 10,
            ValidationSeverity.INFO: 2,
            ValidationSeverity.SUGGESTION: 1,
        }

        total_penalty = sum(weights.get(issue.severity, 0) for issue in issues)
        score = max(0, 100 - total_penalty)

        return round(score, 1)

    async def _verify_medical_term_translation(
        self,
        term: str,
        source_text: str,
        translated_text: str,
        source_lang: str,
        target_lang: str,
    ) -> bool:
        """
        Verify if a medical term is properly translated.

        Uses medical terminology databases to ensure critical terms
        are accurately translated for patient safety.
        """
        try:
            verifier = get_medical_term_verifier()
            return await verifier.verify_term_translation(
                term, source_text, translated_text, source_lang, target_lang
            )
        except (RuntimeError, TypeError, ValueError) as e:
            logger.error(f"Failed to verify medical term translation: {e}")
            # In case of error, be conservative and flag as issue
            return False

    async def _get_medical_translations(
        self, term: str, source_lang: str, target_lang: str
    ) -> List[str]:
        """Get expected medical translations for a term."""
        try:
            verifier = get_medical_term_verifier()
            return await verifier.get_medical_translations(
                term, source_lang, target_lang
            )
        except (RuntimeError, TypeError, ValueError) as e:
            logger.error(f"Failed to get medical translations: {e}")
            return []

    async def _confirm_mistranslation(
        self, source: str, translated: str, source_pattern: str, target_pattern: str
    ) -> bool:
        """
        Confirm if a potential mistranslation is actually problematic.

        Uses context analysis to reduce false positives.
        """
        # Extract context around the pattern
        source_match = re.search(source_pattern, source)
        target_match = re.search(target_pattern, translated)

        if not source_match or not target_match:
            return False

        # Check if the context indicates this is actually correct
        # For example, "no allergies" translated to "sin alergias" is correct
        # even though both contain negation

        # Get surrounding words
        source_context = source[
            max(0, source_match.start() - 50) : min(
                len(source), source_match.end() + 50
            )
        ]
        target_context = translated[
            max(0, target_match.start() - 50) : min(
                len(translated), target_match.end() + 50
            )
        ]

        # Common false positive patterns
        false_positive_patterns = [
            # Correct double negatives in some languages
            (r"no\s+\w+\s+no", r"no\s+\w+\s+no"),  # Spanish double negative
            # Correct negative concordance
            (r"not\s+any", r"ningún|ninguna|aucun|aucune"),
        ]

        for fp_source, fp_target in false_positive_patterns:
            if re.search(fp_source, source_context) and re.search(
                fp_target, target_context
            ):
                return False  # This is actually correct

        # If we can't determine it's a false positive, flag it
        return True

    def _get_language_specific_abbreviations(self, target_lang: str) -> Dict[str, str]:
        """Get language-specific abbreviation expansions."""
        lang_abbr = {
            "es": {
                "q.d.": "una vez al día",
                "b.i.d.": "dos veces al día",
                "t.i.d.": "tres veces al día",
                "q.i.d.": "cuatro veces al día",
            },
            "fr": {
                "q.d.": "une fois par jour",
                "b.i.d.": "deux fois par jour",
                "t.i.d.": "trois fois par jour",
                "q.i.d.": "quatre fois par jour",
            },
            "ar": {
                "q.d.": "مرة واحدة يومياً",
                "b.i.d.": "مرتين يومياً",
                "t.i.d.": "ثلاث مرات يومياً",
                "q.i.d.": "أربع مرات يومياً",
            },
        }
        return lang_abbr.get(target_lang, {})

    def _get_informal_markers(self, target_lang: str) -> List[str]:
        """Get language-specific informal language markers."""
        informal_markers = {
            "en": ["gonna", "wanna", "yeah", "yep", "nope", "kinda", "sorta"],
            "es": ["pa'", "tá", "pos", "tons", "ahi"],
            "fr": ["ouais", "bof", "truc", "machin"],
            "de": ["halt", "mal", "eh", "ne"],
        }
        return informal_markers.get(target_lang, informal_markers.get("en", []))


# Validation presets for different contexts
class ValidationPresets:
    """Predefined validation configurations for different medical contexts."""

    PRESCRIPTION = {
        "required_checks": [
            ValidationType.DOSAGE_ACCURACY,
            ValidationType.UNIT_CONSISTENCY,
            ValidationType.CRITICAL_SAFETY,
            ValidationType.ABBREVIATION_CLARITY,
        ],
        "min_score": 95,
        "allow_warnings": False,
    }

    DIAGNOSIS = {
        "required_checks": [
            ValidationType.MEDICAL_ACCURACY,
            ValidationType.TERMINOLOGY_CONSISTENCY,
            ValidationType.CONTEXT_APPROPRIATENESS,
        ],
        "min_score": 90,
        "allow_warnings": True,
    }

    PATIENT_INSTRUCTIONS = {
        "required_checks": [
            ValidationType.CRITICAL_SAFETY,
            ValidationType.ABBREVIATION_CLARITY,
            ValidationType.CONTEXT_APPROPRIATENESS,
            ValidationType.CULTURAL_SENSITIVITY,
        ],
        "min_score": 85,
        "allow_warnings": True,
    }

    LAB_RESULTS = {
        "required_checks": [
            ValidationType.MEDICAL_ACCURACY,
            ValidationType.UNIT_CONSISTENCY,
            ValidationType.TERMINOLOGY_CONSISTENCY,
        ],
        "min_score": 95,
        "allow_warnings": False,
    }
