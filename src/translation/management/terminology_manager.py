"""Terminology Management.

This module manages medical and general terminology glossaries
for consistent translations across the system.
"""

import csv
import json
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from src.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class Term:
    """Represents a term in the glossary."""

    term: str
    definition: str
    domain: str  # 'medical', 'general', 'ui', 'legal'
    translations: Dict[str, str] = field(default_factory=dict)
    synonyms: List[str] = field(default_factory=list)
    notes: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    approved: bool = False
    medical_code: Optional[str] = None  # ICD-10, SNOMED, etc.

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "term": self.term,
            "definition": self.definition,
            "domain": self.domain,
            "translations": self.translations,
            "synonyms": self.synonyms,
            "notes": self.notes,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "approved": self.approved,
            "medical_code": self.medical_code,
        }


class TerminologyManager:
    """Manages terminology glossaries."""

    def __init__(self, glossary_path: str):
        """Initialize terminology manager."""
        self.glossary_path = Path(glossary_path)
        self.glossary_path.parent.mkdir(parents=True, exist_ok=True)

        self.terms: Dict[str, Term] = {}
        self.domain_index: Dict[str, Set[str]] = defaultdict(set)
        self.language_index: Dict[str, Dict[str, str]] = defaultdict(dict)

        self._load_glossary()

    def _load_glossary(self) -> None:
        """Load glossary from file."""
        if self.glossary_path.exists():
            try:
                with open(self.glossary_path, "r", encoding="utf-8") as f:
                    data = json.load(f)

                for term_data in data.get("terms", []):
                    term = Term(
                        term=term_data["term"],
                        definition=term_data["definition"],
                        domain=term_data["domain"],
                        translations=term_data.get("translations", {}),
                        synonyms=term_data.get("synonyms", []),
                        notes=term_data.get("notes"),
                        created_at=datetime.fromisoformat(
                            term_data.get("created_at", datetime.now().isoformat())
                        ),
                        updated_at=datetime.fromisoformat(
                            term_data.get("updated_at", datetime.now().isoformat())
                        ),
                        approved=term_data.get("approved", False),
                        medical_code=term_data.get("medical_code"),
                    )
                    self.add_term(term)

                logger.info(f"Loaded {len(self.terms)} terms from glossary")
            except (json.JSONDecodeError, OSError, ValueError) as e:
                logger.error(f"Error loading glossary: {e}")

    def _save_glossary(self) -> None:
        """Save glossary to file."""
        data = {
            "version": "1.0",
            "updated_at": datetime.now().isoformat(),
            "terms": [term.to_dict() for term in self.terms.values()],
        }

        with open(self.glossary_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def add_term(self, term: Term) -> bool:
        """Add a term to the glossary."""
        if term.term in self.terms:
            logger.warning(f"Term '{term.term}' already exists, updating")

        self.terms[term.term] = term

        # Update indexes
        self.domain_index[term.domain].add(term.term)

        for lang, translation in term.translations.items():
            self.language_index[lang][term.term] = translation

        # Add synonyms to index
        for synonym in term.synonyms:
            self.terms[synonym] = term  # Point synonyms to same term

        self._save_glossary()
        return True

    def get_term(self, term: str) -> Optional[Term]:
        """Get a term from the glossary."""
        return self.terms.get(term)

    def get_translation(self, term: str, language: str) -> Optional[str]:
        """Get translation for a term in specific language."""
        term_obj = self.get_term(term)
        if term_obj:
            return term_obj.translations.get(language)
        return None

    def search_terms(
        self, query: str, domain: Optional[str] = None, _language: Optional[str] = None
    ) -> List[Term]:
        """Search for terms matching query."""
        results = []
        query_lower = query.lower()

        for term_key, term in self.terms.items():
            # Skip synonym entries
            if term.term != term_key:
                continue

            # Check domain filter
            if domain and term.domain != domain:
                continue

            # Search in term, definition, and translations
            if (
                query_lower in term.term.lower()
                or query_lower in term.definition.lower()
                or any(
                    query_lower in trans.lower() for trans in term.translations.values()
                )
            ):
                results.append(term)

        return results

    def update_translation(self, term: str, language: str, translation: str) -> bool:
        """Update translation for a term."""
        term_obj = self.get_term(term)
        if not term_obj:
            return False

        term_obj.translations[language] = translation
        term_obj.updated_at = datetime.now()

        # Update language index
        self.language_index[language][term] = translation

        self._save_glossary()
        return True

    def approve_term(self, term: str) -> bool:
        """Mark a term as approved."""
        term_obj = self.get_term(term)
        if not term_obj:
            return False

        term_obj.approved = True
        term_obj.updated_at = datetime.now()

        self._save_glossary()
        return True

    def get_terms_by_domain(self, domain: str) -> List[Term]:
        """Get all terms in a specific domain."""
        return [
            self.terms[term_key]
            for term_key in self.domain_index.get(domain, [])
            if self.terms[term_key].term == term_key  # Skip synonyms
        ]

    def export_csv(self, output_path: str, languages: List[str]) -> None:
        """Export glossary to CSV format."""
        with open(output_path, "w", newline="", encoding="utf-8") as f:
            headers = (
                ["Term", "Definition", "Domain"] + languages + ["Notes", "Medical Code"]
            )
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writeheader()

            for term in self.terms.values():
                if (
                    term.term
                    != list(self.terms.keys())[list(self.terms.values()).index(term)]
                ):
                    continue  # Skip synonym entries

                row = {
                    "Term": term.term,
                    "Definition": term.definition,
                    "Domain": term.domain,
                    "Notes": term.notes or "",
                    "Medical Code": term.medical_code or "",
                }

                for lang in languages:
                    row[lang] = term.translations.get(lang, "")

                writer.writerow(row)

    def import_csv(self, csv_path: str, languages: List[str]) -> None:
        """Import terms from CSV format."""
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)

            for row in reader:
                translations = {}
                for lang in languages:
                    if lang in row and row[lang]:
                        translations[lang] = row[lang]

                term = Term(
                    term=row["Term"],
                    definition=row["Definition"],
                    domain=row["Domain"],
                    translations=translations,
                    notes=row.get("Notes") if row.get("Notes") else None,
                    medical_code=(
                        row.get("Medical Code") if row.get("Medical Code") else None
                    ),
                )

                self.add_term(term)

    def get_stats(self) -> Dict[str, Any]:
        """Get glossary statistics."""
        unique_terms = [
            t
            for t in self.terms.values()
            if t.term == list(self.terms.keys())[list(self.terms.values()).index(t)]
        ]

        stats: Dict[str, Any] = {
            "total_terms": len(unique_terms),
            "by_domain": {},
            "by_language": {},
            "approved_terms": sum(1 for t in unique_terms if t.approved),
            "terms_with_medical_codes": sum(1 for t in unique_terms if t.medical_code),
        }

        # Count by domain
        for term in unique_terms:
            stats["by_domain"][term.domain] = stats["by_domain"].get(term.domain, 0) + 1

        # Count by language coverage
        for lang in self.language_index:
            stats["by_language"][lang] = len(self.language_index[lang])

        return stats
