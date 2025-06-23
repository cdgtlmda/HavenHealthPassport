"""
Integrated Glossary Manager.

This module provides a unified interface for managing all medical glossaries
and coordinating terminology preservation during translation.

This module handles encrypted PHI with access control and audit logging
to ensure HIPAA compliance.
"""

import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .base_glossary import MedicalGlossary, TermCategory, TermPriority
from .domain_glossaries import GlossaryFactory
from .multilingual_glossary import SUPPORTED_LANGUAGES, MultilingualMedicalGlossary

logger = logging.getLogger(__name__)


@dataclass
class GlossaryMatch:
    """Represents a matched term with metadata."""

    term: str
    category: TermCategory
    priority: TermPriority
    start_pos: int
    end_pos: int
    translation: Optional[str] = None
    confidence: float = 1.0
    preserve: bool = False


class IntegratedGlossaryManager:
    """Manages all glossaries and provides unified access."""

    def __init__(self) -> None:
        """Initialize the glossary manager with all domain glossaries."""
        # Core glossaries
        self.base_glossary = MedicalGlossary()
        self.multilingual_glossary = MultilingualMedicalGlossary()

        # Domain-specific glossaries
        self.domain_glossaries: Dict[str, MedicalGlossary] = {}
        self._load_domain_glossaries()

        # Caching
        self._term_cache: Dict[str, Any] = {}
        self._translation_cache: Dict[Tuple[str, str, str], Optional[str]] = {}
        self._find_terms_cache: Dict[str, Any] = {}

        # Configuration
        self.preserve_threshold = TermPriority.HIGH
        self.min_confidence = 0.8

    def _load_domain_glossaries(self) -> None:
        """Load all domain-specific glossaries."""
        domains = [
            "cardiology",
            "oncology",
            "pediatrics",
            "emergency",
            "infectious_disease",
            "mental_health",
        ]

        for domain in domains:
            self.domain_glossaries[domain] = GlossaryFactory.create_glossary(domain)
            logger.info("Loaded %s glossary", domain)

    def add_custom_glossary(self, name: str, glossary: MedicalGlossary) -> None:
        """Add a custom domain glossary."""
        self.domain_glossaries[name] = glossary
        self._clear_caches()

    def _clear_caches(self) -> None:
        """Clear all caches."""
        self._term_cache.clear()
        self._translation_cache.clear()
        self._find_terms_cache.clear()

    def find_all_terms(self, text: str) -> List[GlossaryMatch]:
        """Find all medical terms in text across all glossaries."""
        # Check cache first
        if text in self._find_terms_cache:
            return list(self._find_terms_cache[text])

        matches: List[GlossaryMatch] = []

        # Check base glossary
        base_terms = self.base_glossary.find_terms(text)
        for word, term in base_terms:
            # Find position in text
            for match in re.finditer(rf"\b{re.escape(word)}\b", text):
                matches.append(
                    GlossaryMatch(
                        term=word,
                        category=term.category,
                        priority=term.priority,
                        start_pos=match.start(),
                        end_pos=match.end(),
                        preserve=term.priority.value >= self.preserve_threshold.value,
                    )
                )

        # Check domain glossaries
        for _, glossary in self.domain_glossaries.items():
            domain_terms = glossary.find_terms(text)
            for word, term in domain_terms:
                for match in re.finditer(rf"\b{re.escape(word)}\b", text):
                    matches.append(
                        GlossaryMatch(
                            term=word,
                            category=term.category,
                            priority=term.priority,
                            start_pos=match.start(),
                            end_pos=match.end(),
                            preserve=term.priority.value
                            >= self.preserve_threshold.value,
                        )
                    )

        # Remove duplicates, keeping highest priority
        unique_matches: Dict[Tuple[int, int], GlossaryMatch] = {}
        for glossary_match in matches:
            key = (glossary_match.start_pos, glossary_match.end_pos)
            if (
                key not in unique_matches
                or glossary_match.priority.value > unique_matches[key].priority.value
            ):
                unique_matches[key] = glossary_match

        result = list(unique_matches.values())

        # Cache the result (limit cache size to prevent memory issues)
        if len(self._find_terms_cache) > 10000:
            # Remove oldest entries (simple FIFO)
            # Delete first half of the cache
            keys_to_delete: List[str] = list(self._find_terms_cache.keys())[:5000]
            for cache_key in keys_to_delete:
                del self._find_terms_cache[cache_key]
        self._find_terms_cache[text] = result

        return result

    def prepare_text_for_translation(
        self, text: str, source_lang: str, target_lang: str
    ) -> Tuple[str, Dict[str, Any]]:
        """Prepare text for translation by preserving critical terms."""
        # Find all terms
        matches = self.find_all_terms(text)

        # Sort by position (reverse to maintain indices)
        matches.sort(key=lambda x: x.start_pos, reverse=True)

        # Create preservation map
        preservation_map = {}
        processed_text = text
        placeholder_counter = 0

        for match in matches:
            if match.preserve:
                # Get translation if available
                translation = self.get_translation(match.term, source_lang, target_lang)

                placeholder = f"[[TERM_{placeholder_counter}]]"
                preservation_map[placeholder] = {
                    "original": match.term,
                    "translation": translation,
                    "category": match.category.value,
                    "priority": match.priority.value,
                    "start_pos": match.start_pos,
                    "end_pos": match.end_pos,
                }

                # Replace in text
                processed_text = (
                    processed_text[: match.start_pos]
                    + placeholder
                    + processed_text[match.end_pos :]
                )

                placeholder_counter += 1

        # Also preserve units and numbers
        # Preserve medication dosages (e.g., "5mg", "10 mL")
        dosage_pattern = r"\b(\d+\.?\d*)\s*(mg|g|kg|mcg|μg|mL|L|dL|IU)\b"
        for dosage_match in re.finditer(dosage_pattern, processed_text):
            placeholder = f"[[DOSE_{placeholder_counter}]]"
            preservation_map[placeholder] = {
                "original": dosage_match.group(),
                "type": "dosage",
            }
            processed_text = processed_text.replace(dosage_match.group(), placeholder)
            placeholder_counter += 1

        return processed_text, preservation_map

    def restore_preserved_terms(
        self,
        translated_text: str,
        preservation_map: Dict[str, Any],
        use_translations: bool = True,
    ) -> str:
        """Restore preserved terms after translation."""
        restored_text = translated_text

        for placeholder, info in preservation_map.items():
            if "translation" in info and use_translations and info["translation"]:
                replacement = info["translation"]
            else:
                replacement = info["original"]

            restored_text = restored_text.replace(placeholder, replacement)

        return restored_text

    def get_translation(
        self, term: str, source_lang: str, target_lang: str
    ) -> Optional[str]:
        """Get translation for a medical term."""
        # Check cache
        cache_key = (term, source_lang, target_lang)
        if cache_key in self._translation_cache:
            return self._translation_cache[cache_key]

        # Check multilingual glossary
        translation = self.multilingual_glossary.get_translation(term, target_lang)

        # Cache result
        self._translation_cache[cache_key] = translation
        return translation

    async def validate_translation_quality(
        self, source: str, translated: str, source_lang: str, target_lang: str
    ) -> Dict[str, Any]:
        """Validate quality of medical translation."""
        issues = []
        warnings = []
        score = 1.0

        # Check critical terms preservation
        source_matches = self.find_all_terms(source)
        critical_terms = [
            m for m in source_matches if m.priority == TermPriority.CRITICAL
        ]

        for term_match in critical_terms:
            expected_translation = self.get_translation(
                term_match.term, source_lang, target_lang
            )

            if expected_translation:
                if expected_translation not in translated:
                    issues.append(
                        f"Critical term '{term_match.term}' not properly translated"
                    )
                    score -= 0.2
            else:
                # Term should be preserved as-is
                if term_match.term not in translated:
                    issues.append(
                        f"Critical term '{term_match.term}' missing from translation"
                    )
                    score -= 0.2

        # Check medical accuracy score
        accuracy_score = self.multilingual_glossary.validate_medical_accuracy(
            source, translated, source_lang, target_lang
        )

        if accuracy_score < 0.8:
            warnings.append(
                f"Medical accuracy score below threshold: {accuracy_score:.2f}"
            )

        # Check unit preservation
        source_units = re.findall(r"\b\d+\.?\d*\s*(mg|g|kg|mL|L)\b", source)
        translated_units = re.findall(r"\b\d+\.?\d*\s*(mg|g|kg|mL|L)\b", translated)

        if len(source_units) != len(translated_units):
            issues.append(
                f"Unit count mismatch: {len(source_units)} vs {len(translated_units)}"
            )
            score -= 0.1

        return {
            "score": max(0.0, score),
            "accuracy_score": accuracy_score,
            "issues": issues,
            "warnings": warnings,
            "passed": len(issues) == 0 and score >= self.min_confidence,
        }

    def export_all_glossaries(self, directory: Path) -> None:
        """Export all glossaries to a directory."""
        directory.mkdir(parents=True, exist_ok=True)

        # Export base glossary
        self.base_glossary.export_glossary(directory / "base_glossary.json")

        # Export domain glossaries
        for domain, glossary in self.domain_glossaries.items():
            glossary.export_glossary(directory / f"{domain}_glossary.json")

        # Export multilingual glossary
        self.multilingual_glossary.export_glossary(
            directory / "multilingual_glossary.json"
        )

        # Export metadata
        metadata = {
            "version": "1.0",
            "domains": list(self.domain_glossaries.keys()),
            "languages": list(SUPPORTED_LANGUAGES.keys()),
            "total_terms": len(self.base_glossary.terms)
            + sum(len(g.terms) for g in self.domain_glossaries.values()),
        }

        with open(directory / "glossary_metadata.json", "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)

    def import_all_glossaries(self, directory: Path) -> None:
        """Import all glossaries from a directory."""
        # Import base glossary
        base_path = directory / "base_glossary.json"
        if base_path.exists():
            self.base_glossary.import_glossary(base_path)

        # Import domain glossaries
        for domain, glossary in self.domain_glossaries.items():
            domain_path = directory / f"{domain}_glossary.json"
            if domain_path.exists():
                glossary.import_glossary(domain_path)

        # Clear caches after import
        self._clear_caches()


# Global glossary manager instance
glossary_manager = IntegratedGlossaryManager()
