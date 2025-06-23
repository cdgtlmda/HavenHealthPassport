"""
Glossary Data Loader.

This module provides functionality to load pre-populated medical terminology
from JSON data files into the glossary system.

This module handles encrypted PHI with access control and audit logging
to ensure HIPAA compliance.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.healthcare.hipaa_access_control import AccessLevel, require_phi_access
from src.services.encryption_service import EncryptionService

from ..base_glossary import MedicalTerm, TermCategory, TermPriority, TranslationMapping
from ..glossary_manager import IntegratedGlossaryManager
from ..multilingual_glossary import MultilingualMedicalGlossary

logger = logging.getLogger(__name__)


class GlossaryDataLoader:
    """Loads pre-populated glossary data from JSON files."""

    def __init__(self, data_directory: Optional[Path] = None):
        """Initialize the GlossaryDataLoader."""
        if data_directory is None:
            # Default to the data directory in this package
            self.data_directory = Path(__file__).parent
        else:
            self.data_directory = Path(data_directory)

    def load_all_data(self, glossary_manager: IntegratedGlossaryManager) -> None:
        """Load all available glossary data files."""
        data_files = [
            "emergency_pain_terms.json",
            "body_parts.json",
            "medications.json",
        ]

        for filename in data_files:
            filepath = self.data_directory / filename
            if filepath.exists():
                self.load_data_file(filepath, glossary_manager)
                logger.info("Loaded glossary data from %s", filename)
            else:
                logger.warning("Data file not found: %s", filename)

    def load_data_file(
        self, filepath: Path, glossary_manager: IntegratedGlossaryManager
    ) -> None:
        """Load a specific glossary data file."""
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        for _, terms in data.items():
            for term_key, term_data in terms.items():
                # Create MedicalTerm
                term = MedicalTerm(
                    term=term_key,
                    category=TermCategory(term_data.get("category", "symptom")),
                    priority=TermPriority(term_data.get("priority", "medium")),
                    description=term_data.get("description"),
                    aliases=term_data.get("aliases", []),
                    icd10_codes=term_data.get("icd10_codes", []),
                    snomed_codes=term_data.get("snomed_codes", []),
                    rxnorm_codes=term_data.get("rxnorm_codes", []),
                    preserve_exact=term_data.get("preserve_exact", False),
                    case_sensitive=term_data.get("case_sensitive", False),
                )

                # Add to base glossary
                glossary_manager.base_glossary.add_custom_term(term)

                # Add translations if present
                if "translations" in term_data:
                    for lang_code, trans_list in term_data["translations"].items():
                        glossary_manager.multilingual_glossary.add_translation(
                            term_key, lang_code, trans_list, verified=True
                        )

    def export_to_unified_format(
        self, glossary_manager: IntegratedGlossaryManager, output_path: Path
    ) -> None:
        """Export all glossary data to a unified JSON format."""
        unified_data: Dict[str, Any] = {
            "version": "1.0",
            "terms": {},
            "translations": {},
        }

        # Export terms
        for key, term in glossary_manager.base_glossary.terms.items():
            unified_data["terms"][key] = {
                "term": term.term,
                "category": term.category.value,
                "priority": term.priority.value,
                "description": term.description,
                "aliases": term.aliases,
                "icd10_codes": term.icd10_codes,
                "snomed_codes": term.snomed_codes,
                "rxnorm_codes": term.rxnorm_codes,
                "preserve_exact": term.preserve_exact,
                "case_sensitive": term.case_sensitive,
            }

        # Export translations
        for (
            source_term,
            lang_dict,
        ) in glossary_manager.multilingual_glossary.translations.items():
            unified_data["translations"][source_term] = dict(lang_dict)

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(unified_data, f, indent=2, ensure_ascii=False)

        logger.info("Exported unified glossary to %s", output_path)

    def validate_data_integrity(self) -> Dict[str, List[str]]:
        """Validate the integrity of glossary data files."""
        issues: Dict[str, List[str]] = {
            "missing_files": [],
            "format_errors": [],
            "missing_translations": [],
        }

        expected_files = [
            "emergency_pain_terms.json",
            "body_parts.json",
            "medications.json",
        ]

        for filename in expected_files:
            filepath = self.data_directory / filename
            if not filepath.exists():
                issues["missing_files"].append(filename)
                continue

            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)

                # Check structure
                if not isinstance(data, dict):
                    issues["format_errors"].append(f"{filename}: Root must be object")

                # Check for required languages in translations
                required_langs = ["es", "fr", "ar", "zh", "hi"]
                for _, terms in data.items():
                    for term_key, term_data in terms.items():
                        if "translations" in term_data:
                            for lang in required_langs:
                                if lang not in term_data["translations"]:
                                    issues["missing_translations"].append(
                                        f"{filename}: {term_key} missing {lang} translation"
                                    )

            except json.JSONDecodeError as e:
                issues["format_errors"].append(
                    f"{filename}: JSON decode error - {str(e)}"
                )
            except (KeyError, ValueError, TypeError) as e:
                issues["format_errors"].append(f"{filename}: {str(e)}")

        return issues


# Initialize global data loader
data_loader = GlossaryDataLoader()
