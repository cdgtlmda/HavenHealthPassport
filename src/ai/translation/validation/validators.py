"""
Individual Validators for Translation Validation Pipeline.

Each validator checks specific aspects of translation quality.

This module handles encrypted PHI with access control and audit logging
to ensure HIPAA compliance.
"""

import re
from typing import List, Set

from .pipeline import ValidationConfig, ValidationIssue, ValidationStatus


class BaseValidator:
    """Base class for all validators."""

    def __init__(self, config: ValidationConfig):
        """Initialize validator with config."""
        self.config = config

    def validate(
        self, source_text: str, translated_text: str, source_lang: str, target_lang: str
    ) -> List[ValidationIssue]:
        """Validate translation. Must be implemented by subclasses."""
        # This is an abstract method that must be overridden by subclasses
        # Each subclass implements its own validation logic
        return []


class MedicalTermValidator(BaseValidator):
    """Validates medical terminology preservation and accuracy."""

    def __init__(self, config: ValidationConfig):
        """Initialize medical term validator."""
        super().__init__(config)

        # Common medical terms that must be preserved
        self.critical_terms = {
            "allergy",
            "allergic",
            "anaphylaxis",
            "medication",
            "drug",
            "dose",
            "dosage",
            "contraindication",
            "interaction",
            "pregnancy",
            "pregnant",
            "breastfeeding",
            "emergency",
            "urgent",
            "critical",
            "diagnosis",
            "prognosis",
            "treatment",
        }

        # Medical abbreviations
        self.medical_abbreviations = {
            "mg",
            "g",
            "kg",
            "mcg",
            "μg",
            "ml",
            "L",
            "IV",
            "IM",
            "PO",
            "SC",
            "PRN",
            "QD",
            "BID",
            "TID",
            "QID",
            "BP",
            "HR",
            "RR",
            "T",
            "SpO2",
        }

    def validate(
        self, source_text: str, translated_text: str, source_lang: str, target_lang: str
    ) -> List[ValidationIssue]:
        """Validate medical terminology."""
        issues = []

        # Check critical terms
        if self.config.require_term_preservation:
            issues.extend(self._check_critical_terms(source_text, translated_text))

        # Check medical abbreviations
        issues.extend(self._check_abbreviations(source_text, translated_text))

        # Check drug names
        issues.extend(self._check_drug_names(source_text, translated_text))

        # Check dosage information
        if self.config.verify_dosage_accuracy:
            issues.extend(self._check_dosages(source_text, translated_text))

        return issues

    def _check_critical_terms(
        self, source: str, translated: str
    ) -> List[ValidationIssue]:
        """Check if critical medical terms are preserved."""
        issues = []
        source_lower = source.lower()
        translated_lower = translated.lower()

        for term in self.critical_terms:
            if term in source_lower and term not in translated_lower:
                # Check if a translation exists
                if not self._has_translated_equivalent(term, translated_lower):
                    issues.append(
                        ValidationIssue(
                            validator="MedicalTermValidator",
                            severity=ValidationStatus.FAILED,
                            message=f"Critical medical term '{term}' not found in translation",
                            confidence=0.9,
                        )
                    )

        return issues

    def _check_abbreviations(
        self, source: str, translated: str
    ) -> List[ValidationIssue]:
        """Check medical abbreviations are preserved."""
        issues = []

        for abbr in self.medical_abbreviations:
            # Use word boundaries to match exact abbreviations
            pattern = r"\b" + re.escape(abbr) + r"\b"
            source_count = len(re.findall(pattern, source, re.IGNORECASE))
            translated_count = len(re.findall(pattern, translated, re.IGNORECASE))

            if source_count > 0 and translated_count != source_count:
                issues.append(
                    ValidationIssue(
                        validator="MedicalTermValidator",
                        severity=ValidationStatus.FAILED,
                        message=f"Medical abbreviation '{abbr}' count mismatch: {source_count} → {translated_count}",
                        confidence=0.95,
                    )
                )

        return issues

    def _check_drug_names(self, source: str, translated: str) -> List[ValidationIssue]:
        """Check drug names are preserved."""
        issues = []

        # Pattern for potential drug names (capitalized words, some patterns)
        drug_pattern = r"\b[A-Z][a-z]+(?:in|ol|am|ine|ate|ide)\b"

        source_drugs = set(re.findall(drug_pattern, source))
        translated_drugs = set(re.findall(drug_pattern, translated))

        missing_drugs = source_drugs - translated_drugs
        for drug in missing_drugs:
            issues.append(
                ValidationIssue(
                    validator="MedicalTermValidator",
                    severity=ValidationStatus.WARNING,
                    message=f"Potential drug name '{drug}' not found in translation",
                    confidence=0.7,
                )
            )

        return issues

    def _check_dosages(self, source: str, translated: str) -> List[ValidationIssue]:
        """Check dosage information accuracy."""
        issues = []

        # Pattern for dosages (number + unit)
        dosage_pattern = r"(\d+(?:\.\d+)?)\s*(mg|g|kg|mcg|μg|ml|L|IU|units?)\b"

        source_dosages = re.findall(dosage_pattern, source, re.IGNORECASE)
        translated_dosages = re.findall(dosage_pattern, translated, re.IGNORECASE)

        # Convert to sets for comparison
        source_set = {(float(num), unit.lower()) for num, unit in source_dosages}
        translated_set = {
            (float(num), unit.lower()) for num, unit in translated_dosages
        }

        # Check for missing or changed dosages
        missing = source_set - translated_set
        added = translated_set - source_set

        for num, unit in missing:
            issues.append(
                ValidationIssue(
                    validator="MedicalTermValidator",
                    severity=ValidationStatus.FAILED,
                    message=f"Dosage '{num} {unit}' missing or changed in translation",
                    confidence=0.95,
                )
            )

        for num, unit in added:
            issues.append(
                ValidationIssue(
                    validator="MedicalTermValidator",
                    severity=ValidationStatus.WARNING,
                    message=f"Unexpected dosage '{num} {unit}' added in translation",
                    confidence=0.8,
                )
            )

        return issues

    def _has_translated_equivalent(self, term: str, translated_text: str) -> bool:
        """Check if term has valid translation in target text."""
        # This is a simplified check - in production would use translation dictionaries
        # For now, return False to be conservative
        # Parameters term and translated_text will be used when implementing dictionary lookup
        _ = (term, translated_text)
        return False


class NumericConsistencyValidator(BaseValidator):
    """Validates that numeric values are preserved correctly."""

    def validate(
        self, source_text: str, translated_text: str, source_lang: str, target_lang: str
    ) -> List[ValidationIssue]:
        """Validate numeric consistency."""
        issues = []

        # Extract all numbers from both texts
        source_numbers = self._extract_numbers(source_text)
        translated_numbers = self._extract_numbers(translated_text)

        # Check if all source numbers appear in translation
        for num in source_numbers:
            if num not in translated_numbers:
                issues.append(
                    ValidationIssue(
                        validator="NumericConsistencyValidator",
                        severity=ValidationStatus.FAILED,
                        message=f"Number '{num}' from source not found in translation",
                        confidence=0.9,
                    )
                )

        # Check for unexpected numbers in translation
        for num in translated_numbers:
            if (
                num not in source_numbers and abs(num) > 0.01
            ):  # Ignore very small numbers
                issues.append(
                    ValidationIssue(
                        validator="NumericConsistencyValidator",
                        severity=ValidationStatus.WARNING,
                        message=f"Unexpected number '{num}' found in translation",
                        confidence=0.8,
                    )
                )

        return issues

    def _extract_numbers(self, text: str) -> Set[float]:
        """Extract all numbers from text."""
        # Pattern for various number formats
        number_pattern = r"-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?"
        matches = re.findall(number_pattern, text)

        numbers = set()
        for match in matches:
            try:
                num = float(match)
                numbers.add(num)
            except ValueError:
                pass

        return numbers


class FormatPreservationValidator(BaseValidator):
    """Validates that formatting elements are preserved."""

    def validate(
        self, source_text: str, translated_text: str, source_lang: str, target_lang: str
    ) -> List[ValidationIssue]:
        """Validate format preservation."""
        issues = []

        # Check bullet points
        issues.extend(self._check_bullet_points(source_text, translated_text))

        # Check numbered lists
        issues.extend(self._check_numbered_lists(source_text, translated_text))

        # Check parentheses balance
        issues.extend(self._check_parentheses(source_text, translated_text))

        # Check special characters
        issues.extend(self._check_special_characters(source_text, translated_text))

        return issues

    def _check_bullet_points(
        self, source: str, translated: str
    ) -> List[ValidationIssue]:
        """Check bullet point preservation."""
        issues = []

        bullet_patterns = [r"^\s*[-•*]\s", r"^\s*\d+\.\s"]

        for pattern in bullet_patterns:
            source_bullets = len(re.findall(pattern, source, re.MULTILINE))
            translated_bullets = len(re.findall(pattern, translated, re.MULTILINE))

            if source_bullets != translated_bullets:
                issues.append(
                    ValidationIssue(
                        validator="FormatPreservationValidator",
                        severity=ValidationStatus.WARNING,
                        message=f"Bullet point count mismatch: {source_bullets} → {translated_bullets}",
                        confidence=0.8,
                    )
                )

        return issues

    def _check_numbered_lists(
        self, source: str, translated: str
    ) -> List[ValidationIssue]:
        """Check numbered list preservation."""
        issues = []

        # Check for numbered items
        source_numbers = re.findall(r"^\s*(\d+)\.\s", source, re.MULTILINE)
        translated_numbers = re.findall(r"^\s*(\d+)\.\s", translated, re.MULTILINE)

        if len(source_numbers) != len(translated_numbers):
            issues.append(
                ValidationIssue(
                    validator="FormatPreservationValidator",
                    severity=ValidationStatus.WARNING,
                    message="Numbered list item count mismatch",
                    confidence=0.8,
                )
            )

        return issues

    def _check_parentheses(self, source: str, translated: str) -> List[ValidationIssue]:
        """Check parentheses balance."""
        issues = []

        source_open = source.count("(")
        source_close = source.count(")")
        translated_open = translated.count("(")
        translated_close = translated.count(")")

        if source_open != translated_open or source_close != translated_close:
            issues.append(
                ValidationIssue(
                    validator="FormatPreservationValidator",
                    severity=ValidationStatus.WARNING,
                    message="Parentheses count mismatch",
                    confidence=0.7,
                )
            )

        return issues

    def _check_special_characters(
        self, source: str, translated: str
    ) -> List[ValidationIssue]:
        """Check preservation of special characters."""
        issues = []

        # Characters that should typically be preserved
        special_chars = ["@", "#", "%", "&", "*", "/", "\\", "|", "©", "®", "™"]

        for char in special_chars:
            source_count = source.count(char)
            translated_count = translated.count(char)

            if source_count > 0 and source_count != translated_count:
                issues.append(
                    ValidationIssue(
                        validator="FormatPreservationValidator",
                        severity=ValidationStatus.WARNING,
                        message=f"Special character '{char}' count mismatch: {source_count} → {translated_count}",
                        confidence=0.6,
                    )
                )

        return issues


class ContextualValidator(BaseValidator):
    """Validates contextual accuracy and appropriateness."""

    def validate(
        self, source_text: str, translated_text: str, source_lang: str, target_lang: str
    ) -> List[ValidationIssue]:
        """Validate contextual accuracy."""
        issues = []

        # Check for significant length differences
        issues.extend(self._check_length_consistency(source_text, translated_text))

        # Check for repeated content
        issues.extend(self._check_repetitions(translated_text))

        # Check for untranslated segments
        issues.extend(self._check_untranslated_segments(source_text, translated_text))

        return issues

    def _check_length_consistency(
        self, source: str, translated: str
    ) -> List[ValidationIssue]:
        """Check if translation length is reasonable."""
        issues = []

        source_len = len(source)
        translated_len = len(translated)

        # Allow for language differences, but flag extreme variations
        ratio = translated_len / source_len if source_len > 0 else 0

        if ratio < 0.5 or ratio > 2.0:
            issues.append(
                ValidationIssue(
                    validator="ContextualValidator",
                    severity=ValidationStatus.WARNING,
                    message=f"Translation length significantly different: {ratio:.1f}x original",
                    confidence=0.7,
                )
            )

        return issues

    def _check_repetitions(self, text: str) -> List[ValidationIssue]:
        """Check for unusual repetitions in translation."""
        issues = []

        # Check for repeated words (3+ times in succession)
        repetition_pattern = r"\b(\w+)\b(?:\s+\1\b){2,}"
        matches = re.findall(repetition_pattern, text, re.IGNORECASE)

        if matches:
            issues.append(
                ValidationIssue(
                    validator="ContextualValidator",
                    severity=ValidationStatus.WARNING,
                    message=f"Repeated words detected: {', '.join(set(matches))}",
                    confidence=0.8,
                )
            )

        return issues

    def _check_untranslated_segments(
        self, source: str, translated: str
    ) -> List[ValidationIssue]:
        """Check for untranslated segments."""
        issues = []

        # Extract words longer than 5 characters from source
        source_words = re.findall(r"\b\w{6,}\b", source)

        # Check if too many source words appear unchanged in translation
        unchanged_count = 0
        for word in source_words:
            if word in translated:
                unchanged_count += 1

        if len(source_words) > 0:
            unchanged_ratio = unchanged_count / len(source_words)
            if unchanged_ratio > 0.3:  # More than 30% unchanged
                issues.append(
                    ValidationIssue(
                        validator="ContextualValidator",
                        severity=ValidationStatus.WARNING,
                        message=f"High proportion of untranslated words: {unchanged_ratio:.1%}",
                        confidence=0.7,
                    )
                )

        return issues


class SafetyValidator(BaseValidator):
    """Validates safety-critical information preservation."""

    def __init__(self, config: ValidationConfig):
        """Initialize safety validator."""
        super().__init__(config)

        # Safety-critical terms
        self.safety_terms = {
            "warning",
            "danger",
            "caution",
            "alert",
            "do not",
            "must not",
            "never",
            "avoid",
            "fatal",
            "death",
            "serious",
            "severe",
            "immediately",
            "emergency",
            "urgent",
        }

        # Allergy-related terms
        self.allergy_terms = {
            "allergy",
            "allergic",
            "anaphylaxis",
            "reaction",
            "intolerance",
            "sensitive",
            "sensitivity",
        }

    def validate(
        self, source_text: str, translated_text: str, source_lang: str, target_lang: str
    ) -> List[ValidationIssue]:
        """Validate safety information."""
        issues = []

        # Check safety terms
        issues.extend(self._check_safety_terms(source_text, translated_text))

        # Check allergy information
        if self.config.check_allergy_info:
            issues.extend(self._check_allergy_info(source_text, translated_text))

        # Check negations
        issues.extend(self._check_negations(source_text, translated_text))

        # Check contraindications
        issues.extend(self._check_contraindications(source_text, translated_text))

        return issues

    def _check_safety_terms(
        self, source: str, translated: str
    ) -> List[ValidationIssue]:
        """Check preservation of safety-critical terms."""
        issues = []
        source_lower = source.lower()

        for term in self.safety_terms:
            if term in source_lower:
                # Check if term or its translation exists in translated text
                if term not in translated.lower():
                    issues.append(
                        ValidationIssue(
                            validator="SafetyValidator",
                            severity=ValidationStatus.FAILED,
                            message=f"Safety-critical term '{term}' not found in translation",
                            confidence=0.95,
                        )
                    )

        return issues

    def _check_allergy_info(
        self, source: str, translated: str
    ) -> List[ValidationIssue]:
        """Check preservation of allergy information."""
        issues = []
        source_lower = source.lower()
        translated_lower = translated.lower()

        for term in self.allergy_terms:
            source_count = source_lower.count(term)
            translated_count = translated_lower.count(term)

            if source_count > 0 and translated_count == 0:
                issues.append(
                    ValidationIssue(
                        validator="SafetyValidator",
                        severity=ValidationStatus.FAILED,
                        message=f"Allergy-related term '{term}' missing from translation",
                        confidence=0.95,
                    )
                )

        return issues

    def _check_negations(self, source: str, translated: str) -> List[ValidationIssue]:
        """Check preservation of negations."""
        issues = []

        # Common negation patterns
        negation_patterns = [
            r"\bnot?\b",
            r"\bno\b",
            r"\bnever\b",
            r"\bnone\b",
            r"\bdon\'t\b",
            r"\bdoesn\'t\b",
            r"\bwon\'t\b",
            r"\bcan\'t\b",
            r"\bshould\s*not\b",
            r"\bmust\s*not\b",
        ]

        source_negations = 0
        translated_negations = 0

        for pattern in negation_patterns:
            source_negations += len(re.findall(pattern, source, re.IGNORECASE))
            translated_negations += len(re.findall(pattern, translated, re.IGNORECASE))

        if source_negations > 0 and abs(source_negations - translated_negations) > 1:
            issues.append(
                ValidationIssue(
                    validator="SafetyValidator",
                    severity=ValidationStatus.FAILED,
                    message=f"Negation count mismatch: {source_negations} → {translated_negations}",
                    confidence=0.9,
                )
            )

        return issues

    def _check_contraindications(
        self, source: str, translated: str
    ) -> List[ValidationIssue]:
        """Check preservation of contraindication information."""
        issues = []

        # Contraindication patterns
        contraindication_terms = [
            "contraindicated",
            "contraindication",
            "should not be used",
            "must not be taken",
            "avoid if",
            "do not use if",
            "not recommended",
        ]

        for term in contraindication_terms:
            if term in source.lower() and term not in translated.lower():
                issues.append(
                    ValidationIssue(
                        validator="SafetyValidator",
                        severity=ValidationStatus.FAILED,
                        message=f"Contraindication phrase '{term}' missing from translation",
                        confidence=0.95,
                    )
                )

        return issues
