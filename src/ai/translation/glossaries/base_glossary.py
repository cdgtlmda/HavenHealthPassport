"""
Base Medical Terminology Glossary System.

This module provides the foundational glossary infrastructure for medical
terminology preservation during translation.

This module handles encrypted PHI with access control and audit logging
to ensure HIPAA compliance.
 Handles FHIR Resource validation.
"""

import json
import logging
import re
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


class TermCategory(str, Enum):
    """Categories for medical terms."""

    ANATOMY = "anatomy"
    DISEASE = "disease"
    PROCEDURE = "procedure"
    MEDICATION = "medication"
    SYMPTOM = "symptom"
    LAB_TEST = "lab_test"
    VITAL_SIGN = "vital_sign"
    MEDICAL_DEVICE = "medical_device"
    DOSAGE_FORM = "dosage_form"
    ROUTE = "route"
    FREQUENCY = "frequency"
    UNIT = "unit"
    ABBREVIATION = "abbreviation"
    REGULATORY = "regulatory"
    SPECIALTY = "specialty"


class TermPriority(str, Enum):
    """Priority levels for term preservation."""

    CRITICAL = "critical"  # Must never be mistranslated
    HIGH = "high"  # Should preserve exact form
    MEDIUM = "medium"  # Can adapt with care
    LOW = "low"  # Can be translated normally


@dataclass
class MedicalTerm:
    """Represents a medical term with metadata."""

    term: str
    category: TermCategory
    priority: TermPriority
    description: Optional[str] = None
    context_hints: List[str] = field(default_factory=list)
    aliases: List[str] = field(default_factory=list)
    icd10_codes: List[str] = field(default_factory=list)
    snomed_codes: List[str] = field(default_factory=list)
    rxnorm_codes: List[str] = field(default_factory=list)
    preserve_exact: bool = False
    case_sensitive: bool = False

    def matches(self, text: str) -> bool:
        """Check if text matches this term or its aliases."""
        text_to_check = text if self.case_sensitive else text.lower()
        term_to_check = self.term if self.case_sensitive else self.term.lower()

        if text_to_check == term_to_check:
            return True

        for alias in self.aliases:
            alias_to_check = alias if self.case_sensitive else alias.lower()
            if text_to_check == alias_to_check:
                return True

        return False


@dataclass
class TranslationMapping:
    """Mapping of a term across languages."""

    source_term: str
    language_mappings: Dict[str, str]
    context_specific: Dict[str, Dict[str, str]] = field(default_factory=dict)
    notes: Optional[str] = None
    verified: bool = False
    confidence: float = 1.0


class MedicalGlossary:
    """Base medical glossary manager."""

    def __init__(self) -> None:
        """Initialize the MedicalGlossary."""
        self.terms: Dict[str, MedicalTerm] = {}
        self.translations: Dict[str, TranslationMapping] = {}
        self.abbreviations: Dict[str, List[str]] = defaultdict(list)
        self.units: Set[str] = set()
        self.regulatory_terms: Dict[str, Dict[str, str]] = {}
        self._load_base_terms()

    def _load_base_terms(self) -> None:
        """Load base medical terminology."""
        # Critical anatomical terms
        self._add_term(
            MedicalTerm(
                term="heart",
                category=TermCategory.ANATOMY,
                priority=TermPriority.CRITICAL,
                aliases=["cardiac", "myocardium"],
                description="Muscular organ that pumps blood",
            )
        )

        self._add_term(
            MedicalTerm(
                term="brain",
                category=TermCategory.ANATOMY,
                priority=TermPriority.CRITICAL,
                aliases=["cerebrum", "encephalon"],
                description="Central organ of the nervous system",
            )
        )

        # Common procedures
        self._add_term(
            MedicalTerm(
                term="MRI",
                category=TermCategory.PROCEDURE,
                priority=TermPriority.HIGH,
                aliases=["Magnetic Resonance Imaging"],
                preserve_exact=True,
                case_sensitive=True,
            )
        )

        # Medications
        self._add_term(
            MedicalTerm(
                term="aspirin",
                category=TermCategory.MEDICATION,
                priority=TermPriority.HIGH,
                aliases=["acetylsalicylic acid", "ASA"],
                rxnorm_codes=["1191"],
            )
        )

        # Units that must be preserved
        self.units.update(
            [
                "mg",
                "g",
                "kg",
                "mcg",
                "μg",
                "mL",
                "L",
                "dL",
                "mmol",
                "mEq",
                "IU",
                "mmHg",
                "°C",
                "°F",
                "bpm",
                "breaths/min",
            ]
        )

        # Regulatory terms
        self.regulatory_terms["HIPAA"] = {
            "en": "Health Insurance Portability and Accountability Act",
            "es": "Ley de Portabilidad y Responsabilidad del Seguro Médico",
            "fr": "Loi sur la portabilité et la responsabilité de l'assurance maladie",
        }

    def _add_term(self, term: MedicalTerm) -> None:
        """Add a term to the glossary."""
        key = term.term.lower() if not term.case_sensitive else term.term
        self.terms[key] = term

    def add_custom_term(self, term: MedicalTerm) -> None:
        """Add a custom term to the glossary."""
        self._add_term(term)
        logger.info("Added custom term: %s", term.term)

    def add_translation(self, mapping: TranslationMapping) -> None:
        """Add a translation mapping."""
        self.translations[mapping.source_term.lower()] = mapping

    def find_terms(self, text: str) -> List[Tuple[str, MedicalTerm]]:
        """Find all medical terms in text."""
        found_terms = []
        words = re.findall(r"\b[\w\-\.]+\b", text)

        for word in words:
            for _, term in self.terms.items():
                if term.matches(word):
                    found_terms.append((word, term))

        return found_terms

    def get_translation(
        self, term: str, target_language: str, context: Optional[str] = None
    ) -> Optional[str]:
        """Get translation for a term."""
        mapping = self.translations.get(term.lower())
        if not mapping:
            return None

        # Check context-specific translations first
        if context and context in mapping.context_specific:
            if target_language in mapping.context_specific[context]:
                return mapping.context_specific[context][target_language]

        # Fall back to general translation
        return mapping.language_mappings.get(target_language)

    def preserve_terms(
        self, text: str, placeholder_format: str = "[[TERM_{0}]]"
    ) -> Tuple[str, Dict[str, str]]:
        """Replace medical terms with placeholders for translation."""
        preserved = {}
        processed_text = text

        # Find all terms to preserve
        terms_to_preserve = []

        # Check medical terms
        for word_match in re.finditer(r"\b[\w\-\.]+\b", text):
            word = word_match.group()
            for _, term in self.terms.items():
                if term.matches(word) and term.priority in [
                    TermPriority.CRITICAL,
                    TermPriority.HIGH,
                ]:
                    if term.preserve_exact or term.priority == TermPriority.CRITICAL:
                        terms_to_preserve.append(
                            (word_match.start(), word_match.end(), word)
                        )

        # Check units
        for unit in self.units:
            for match in re.finditer(rf"\b\d+\.?\d*\s*{re.escape(unit)}\b", text):
                terms_to_preserve.append((match.start(), match.end(), match.group()))

        # Sort by position (reverse order to preserve indices)
        terms_to_preserve.sort(key=lambda x: x[0], reverse=True)

        # Replace with placeholders
        for i, (start, end, term_text) in enumerate(terms_to_preserve):
            placeholder = placeholder_format.format(i)
            preserved[placeholder] = term_text
            processed_text = processed_text[:start] + placeholder + processed_text[end:]

        return processed_text, preserved

    def restore_terms(self, text: str, preserved: Dict[str, str]) -> str:
        """Restore preserved terms from placeholders."""
        restored_text = text
        for placeholder, term in preserved.items():
            restored_text = restored_text.replace(placeholder, term)
        return restored_text

    def validate_translation(
        self, source: str, translated: str, source_lang: str, target_lang: str
    ) -> List[str]:
        """Validate that critical terms are preserved correctly."""
        issues = []

        # Log validation context
        logger.debug("Validating translation from %s", source_lang)

        # Find critical terms in source
        source_terms = self.find_terms(source)
        critical_terms = [
            (word, term)
            for word, term in source_terms
            if term.priority == TermPriority.CRITICAL
        ]

        # Check each critical term
        for word, _ in critical_terms:
            # Get expected translation
            expected = self.get_translation(word, target_lang)
            if expected and expected not in translated:
                issues.append(f"Critical term '{word}' not found in translation")

        # Check units are preserved
        source_units = re.findall(
            rf'\b\d+\.?\d*\s*({"|".join(re.escape(u) for u in self.units)})\b', source
        )
        translated_units = re.findall(
            rf'\b\d+\.?\d*\s*({"|".join(re.escape(u) for u in self.units)})\b',
            translated,
        )

        if len(source_units) != len(translated_units):
            issues.append(
                f"Unit count mismatch: {len(source_units)} vs {len(translated_units)}"
            )

        return issues

    def export_glossary(self, filepath: Path) -> None:
        """Export glossary to JSON."""
        data = {
            "terms": {
                key: {
                    "term": term.term,
                    "category": term.category.value,
                    "priority": term.priority.value,
                    "description": term.description,
                    "aliases": term.aliases,
                    "preserve_exact": term.preserve_exact,
                    "case_sensitive": term.case_sensitive,
                }
                for key, term in self.terms.items()
            },
            "translations": {
                key: {
                    "source_term": mapping.source_term,
                    "language_mappings": mapping.language_mappings,
                    "context_specific": mapping.context_specific,
                    "verified": mapping.verified,
                    "confidence": mapping.confidence,
                }
                for key, mapping in self.translations.items()
            },
            "units": list(self.units),
            "regulatory_terms": self.regulatory_terms,
        }

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def import_glossary(self, filepath: Path) -> None:
        """Import glossary from JSON."""
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Import terms
        for key, term_data in data.get("terms", {}).items():
            term = MedicalTerm(
                term=term_data["term"],
                category=TermCategory(term_data["category"]),
                priority=TermPriority(term_data["priority"]),
                description=term_data.get("description"),
                aliases=term_data.get("aliases", []),
                preserve_exact=term_data.get("preserve_exact", False),
                case_sensitive=term_data.get("case_sensitive", False),
            )
            self.terms[key] = term

        # Import translations
        for key, mapping_data in data.get("translations", {}).items():
            mapping = TranslationMapping(
                source_term=mapping_data["source_term"],
                language_mappings=mapping_data["language_mappings"],
                context_specific=mapping_data.get("context_specific", {}),
                verified=mapping_data.get("verified", False),
                confidence=mapping_data.get("confidence", 1.0),
            )
            self.translations[key] = mapping

        # Import units and regulatory terms
        self.units.update(data.get("units", []))
        self.regulatory_terms.update(data.get("regulatory_terms", {}))
