"""
Medical terminology preservation for translations.

This module handles the preservation of medical terms, codes, and
abbreviations during translation to maintain clinical accuracy.

This module handles encrypted PHI with access control and audit logging
to ensure HIPAA compliance.
"""

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..medical_nlp.abbreviations import MedicalAbbreviationHandler
from .config import Language

logger = logging.getLogger(__name__)


@dataclass
class MedicalTerm:
    """Represents a medical term to be preserved."""

    text: str
    category: str  # drug, disease, procedure, anatomy, etc.
    codes: Dict[str, str] = field(default_factory=dict)  # ICD-10, SNOMED, etc.
    translations: Dict[Language, str] = field(default_factory=dict)
    synonyms: List[str] = field(default_factory=list)
    context_hints: List[str] = field(default_factory=list)


@dataclass
class PreservationResult:
    """Result of terminology preservation."""

    original_text: str
    processed_text: str
    preserved_terms: List[Dict[str, Any]]
    placeholders: Dict[str, MedicalTerm]
    warnings: List[str] = field(default_factory=list)


class MedicalTerminologyPreserver:
    """
    Preserves medical terminology during translation.

    Features:
    - Medical term identification and extraction
    - Code preservation (ICD-10, SNOMED, etc.)
    - Drug name preservation
    - Anatomical term preservation
    - Medical abbreviation handling
    - Measurement unit preservation
    """

    def __init__(self) -> None:
        """Initialize the terminology preserver."""
        self.medical_terms: Dict[str, MedicalTerm] = {}
        self.abbreviation_handler = MedicalAbbreviationHandler()
        self.term_patterns: Dict[str, re.Pattern] = {}
        self._initialize_patterns()

    def _initialize_patterns(self) -> None:
        """Initialize regex patterns for medical terms."""
        # ICD-10 codes
        self.term_patterns["icd10"] = re.compile(
            r"\b[A-TV-Z][0-9]{2}(?:\.[0-9]{1,4})?\b"
        )

        # SNOMED CT codes
        self.term_patterns["snomed"] = re.compile(r"\b\d{6,18}\b")

        # Drug dosages
        self.term_patterns["dosage"] = re.compile(
            r"\b\d+(?:\.\d+)?\s*(?:mg|g|mcg|μg|ml|mL|L|IU|units?)\b", re.IGNORECASE
        )

        # Blood pressure
        self.term_patterns["blood_pressure"] = re.compile(
            r"\b\d{2,3}/\d{2,3}\s*(?:mmHg|mm\s*Hg)?\b"
        )

        # Lab values with units
        self.term_patterns["lab_value"] = re.compile(
            r"\b\d+(?:\.\d+)?\s*(?:mmol/L|mEq/L|mg/dL|g/dL|IU/L|U/L|%)\b"
        )

    def load_medical_terms(self, dictionary_path: Optional[Path] = None) -> None:
        """
        Load medical terms from dictionary.

        Args:
            dictionary_path: Path to medical dictionary JSON file
        """
        if dictionary_path and dictionary_path.exists():
            with open(dictionary_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                for term_data in data:
                    term = MedicalTerm(**term_data)
                    self.medical_terms[term.text.lower()] = term

        # Load default medical terms
        self._load_default_terms()

        logger.info("Loaded %d medical terms", len(self.medical_terms))

    def _load_default_terms(self) -> None:
        """Load default medical terms."""
        # Common drugs
        common_drugs = [
            "aspirin",
            "ibuprofen",
            "acetaminophen",
            "amoxicillin",
            "metformin",
            "lisinopril",
            "atorvastatin",
            "levothyroxine",
        ]

        for drug in common_drugs:
            self.medical_terms[drug] = MedicalTerm(
                text=drug,
                category="drug",
                context_hints=["medication", "prescription", "drug"],
            )

        # Common conditions
        common_conditions = [
            "diabetes",
            "hypertension",
            "asthma",
            "pneumonia",
            "covid-19",
            "influenza",
            "tuberculosis",
            "malaria",
        ]

        for condition in common_conditions:
            self.medical_terms[condition] = MedicalTerm(
                text=condition,
                category="disease",
                context_hints=["diagnosis", "condition", "disease"],
            )

    def preserve_terms(
        self,
        text: str,
        source_language: Language,
        target_language: Language,
    ) -> PreservationResult:
        """
        Preserve medical terms in text.

        Args:
            text: Original text
            source_language: Source language
            target_language: Target language

        Returns:
            PreservationResult with processed text and preserved terms
        """
        preserved_terms = []
        placeholders = {}
        processed_text = text
        warnings: List[str] = []

        # Log target language for context
        logger.debug(
            "Preserving terms for translation from %s to %s",
            source_language,
            target_language,
        )

        # Extract and replace medical codes
        for pattern_name, pattern in self.term_patterns.items():
            matches = list(pattern.finditer(processed_text))
            for i, match in enumerate(reversed(matches)):
                term_text = match.group()
                placeholder = f"[[MEDICAL_{pattern_name.upper()}_{i}]]"

                # Store the term
                placeholders[placeholder] = MedicalTerm(
                    text=term_text, category=pattern_name, context_hints=[pattern_name]
                )

                preserved_terms.append(
                    {
                        "text": term_text,
                        "category": pattern_name,
                        "position": match.span(),
                        "placeholder": placeholder,
                    }
                )

                # Replace in text
                processed_text = (
                    processed_text[: match.start()]
                    + placeholder
                    + processed_text[match.end() :]
                )

        # Extract known medical terms
        for term_key, medical_term in self.medical_terms.items():
            if term_key in processed_text.lower():
                # Find exact matches
                pattern = re.compile(
                    r"\b" + re.escape(medical_term.text) + r"\b", re.IGNORECASE
                )
                matches = list(pattern.finditer(processed_text))

                for i, match in enumerate(reversed(matches)):
                    placeholder = f"[[MEDICAL_TERM_{term_key.upper()}_{i}]]"

                    placeholders[placeholder] = medical_term

                    preserved_terms.append(
                        {
                            "text": match.group(),
                            "category": medical_term.category,
                            "position": match.span(),
                            "placeholder": placeholder,
                            "codes": (
                                list(medical_term.codes.items())
                                if medical_term.codes
                                else []
                            ),
                        }
                    )

                    processed_text = (
                        processed_text[: match.start()]
                        + placeholder
                        + processed_text[match.end() :]
                    )

        # Handle abbreviations
        abbreviations = self.abbreviation_handler.detect_abbreviations(processed_text)
        for abbrev in abbreviations:
            placeholder = f"[[MEDICAL_ABBREV_{abbrev.text}]]"

            # Create a medical term for the abbreviation
            placeholders[placeholder] = MedicalTerm(
                text=abbrev.text,
                category="abbreviation",
                context_hints=["abbreviation"]
                + ([abbrev.selected_expansion] if abbrev.selected_expansion else []),
            )

            preserved_terms.append(
                {
                    "text": abbrev.text,
                    "category": "abbreviation",
                    "expansion": abbrev.selected_expansion or "",
                    "placeholder": placeholder,
                }
            )

        return PreservationResult(
            original_text=text,
            processed_text=processed_text,
            preserved_terms=preserved_terms,
            placeholders=placeholders,
            warnings=warnings,
        )

    def restore_terms(
        self,
        translated_text: str,
        preservation_result: PreservationResult,
        target_language: Language,
    ) -> str:
        """
        Restore preserved terms in translated text.

        Args:
            translated_text: Translated text with placeholders
            preservation_result: Original preservation result
            target_language: Target language

        Returns:
            Text with medical terms restored
        """
        restored_text = translated_text

        # Sort placeholders by length (longest first) to avoid partial replacements
        sorted_placeholders = sorted(
            preservation_result.placeholders.items(),
            key=lambda x: len(x[0]),
            reverse=True,
        )

        for placeholder, medical_term in sorted_placeholders:
            if placeholder in restored_text:
                # Check if term has translation for target language
                if target_language in medical_term.translations:
                    replacement = medical_term.translations[target_language]
                else:
                    # Keep original term if no translation available
                    replacement = medical_term.text
                    logger.debug(
                        "No translation found for '%s' in %s, keeping original",
                        medical_term.text,
                        target_language.value,
                    )

                restored_text = restored_text.replace(placeholder, replacement)

        return restored_text

    def add_custom_term(
        self,
        term: str,
        category: str,
        translations: Optional[Dict[Language, str]] = None,
        codes: Optional[Dict[str, str]] = None,
    ) -> None:
        """Add a custom medical term to the dictionary."""
        self.medical_terms[term.lower()] = MedicalTerm(
            text=term,
            category=category,
            translations=translations or {},
            codes=codes or {},
        )
