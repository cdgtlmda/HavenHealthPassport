"""Glossary Update Manager - Manages automatic glossary updates."""

import json
import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.security.access_control import AccessPermission, require_permission
from src.security.audit import audit_phi_access
from src.services.encryption_service import EncryptionService
from src.translation.management.terminology_manager import Term, TerminologyManager
from src.translation.management.translation_memory import TranslationMemory
from src.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class GlossaryUpdateCandidate:
    """A candidate term for glossary inclusion."""

    term: str
    frequency: int
    contexts: List[str]
    translations: Dict[str, List[str]]
    consistency_score: float
    first_seen: datetime
    last_seen: datetime
    suggested_domain: str
    confidence: float


@dataclass
class GlossaryUpdateReport:
    """Report of glossary update analysis."""

    analyzed_translations: int
    new_term_candidates: List[GlossaryUpdateCandidate]
    inconsistent_terms: List[Dict[str, Any]]
    updated_terms: List[str]
    deprecated_terms: List[str]
    analysis_time: float


class GlossaryUpdateManager:
    """Manages automatic glossary updates."""

    def __init__(
        self, glossary_path: str, translation_memory: Optional[TranslationMemory] = None
    ):
        """Initialize glossary update manager."""
        self.terminology_manager = TerminologyManager(glossary_path)
        self.translation_memory = translation_memory
        self.update_config = self._load_config()
        self.term_patterns = self._compile_term_patterns()
        self.candidate_terms: Dict[str, GlossaryUpdateCandidate] = {}
        self.encryption_service = EncryptionService()

    def _load_config(self) -> Dict[str, Any]:
        """Load update configuration."""
        return {
            "min_frequency": 5,  # Minimum occurrences to consider
            "min_consistency_score": 0.7,  # Minimum consistency for auto-add
            "confidence_threshold": 0.8,  # Minimum confidence for auto-add
            "analysis_window_days": 30,  # Days to look back for analysis
            "medical_term_patterns": [
                r"\b(blood|pressure|heart|rate|temperature|glucose)\b",
                r"\b(mg|ml|mmHg|bpm|°[CF])\b",
                r"\b(diagnosis|symptom|treatment|medication)\b",
            ],
        }

    def _compile_term_patterns(self) -> List[re.Pattern]:
        """Compile regex patterns for term detection."""
        patterns = []
        for pattern_str in self.update_config["medical_term_patterns"]:
            patterns.append(re.compile(pattern_str, re.IGNORECASE))
        return patterns

    def analyze_for_updates(
        self,
        translations_path: Optional[str] = None,
        languages: Optional[List[str]] = None,
    ) -> GlossaryUpdateReport:
        """Analyze translations for glossary updates."""
        start_time = datetime.now()

        # Load recent translations
        translations = self._load_recent_translations(translations_path, languages)

        # Extract term candidates
        self._extract_term_candidates(translations)

        # Analyze consistency
        inconsistent_terms = self._find_inconsistent_terms(translations)

        # Find deprecated terms
        deprecated_terms = self._find_deprecated_terms()

        # Apply updates
        updated_terms = self._apply_automatic_updates()

        analysis_time = (datetime.now() - start_time).total_seconds()

        return GlossaryUpdateReport(
            analyzed_translations=len(translations),
            new_term_candidates=list(self.candidate_terms.values()),
            inconsistent_terms=inconsistent_terms,
            updated_terms=updated_terms,
            deprecated_terms=deprecated_terms,
            analysis_time=analysis_time,
        )

    def _load_recent_translations(
        self, _translations_path: Optional[str], _languages: Optional[List[str]]
    ) -> List[Dict[str, Any]]:
        """Load recent translations for analysis."""
        translations: List[Dict[str, Any]] = []

        # Load from translation memory if available
        if self.translation_memory:
            # Get recent translations from TM
            # This would query the translation memory database
            pass

        # Load from files if path provided
        if _translations_path:
            path = Path(_translations_path)
            if path.exists():
                # Load translation files
                # Implementation would parse translation files
                pass

        return translations

    @audit_phi_access("phi_access__extract_term_candidates")
    @require_permission(AccessPermission.READ_PHI)
    def _extract_term_candidates(self, translations: List[Dict[str, Any]]) -> Any:
        """Extract potential terms from translations."""
        term_occurrences: Any = defaultdict(
            lambda: {
                "frequency": 0,
                "contexts": [],
                "translations": defaultdict(list),
                "first_seen": datetime.now(),
                "last_seen": datetime.now(),
            }
        )

        for translation in translations:
            # Extract terms using patterns
            text = translation.get("source_text", "")

            for pattern in self.term_patterns:
                matches = pattern.findall(text)
                for match in matches:
                    term = match.lower()
                    occurrence = term_occurrences[term]

                    occurrence["frequency"] += 1
                    occurrence["contexts"].append(translation.get("context", ""))

                    target_lang = translation.get("target_language", "")
                    target_text = translation.get("target_text", "")
                    if target_lang and target_text:
                        occurrence["translations"][target_lang].append(target_text)

        # Convert to candidates
        for term, data in term_occurrences.items():
            if data["frequency"] >= self.update_config["min_frequency"]:
                # Calculate consistency score
                consistency_score = self._calculate_consistency_score(
                    data["translations"]
                )

                # Determine domain
                suggested_domain = self._suggest_domain(term, data["contexts"])

                # Calculate confidence
                confidence = self._calculate_confidence(
                    data["frequency"], consistency_score, len(data["translations"])
                )

                contexts_set = (
                    set(data["contexts"])
                    if isinstance(data["contexts"], list)
                    else set()
                )
                translations_dict = (
                    dict(data["translations"])
                    if hasattr(data["translations"], "__iter__")
                    else {}
                )

                candidate = GlossaryUpdateCandidate(
                    term=term,
                    frequency=data["frequency"],
                    contexts=list(contexts_set),
                    translations=translations_dict,
                    consistency_score=consistency_score,
                    first_seen=(
                        datetime.fromisoformat(str(data["first_seen"]))
                        if isinstance(data["first_seen"], str)
                        else data["first_seen"]
                    ),
                    last_seen=(
                        datetime.fromisoformat(str(data["last_seen"]))
                        if isinstance(data["last_seen"], str)
                        else data["last_seen"]
                    ),
                    suggested_domain=suggested_domain,
                    confidence=confidence,
                )

                self.candidate_terms[term] = candidate

    def _calculate_consistency_score(self, translations: Dict[str, List[str]]) -> float:
        """Calculate how consistent translations are for a term."""
        if not translations:
            return 0.0

        total_score = 0.0
        language_count = 0

        for _lang, trans_list in translations.items():
            if not trans_list:
                continue

            # Count unique translations
            unique_trans = set(trans_list)

            # Score based on how many unique translations exist
            # 1.0 if all are the same, lower if there's variation
            score = 1.0 / len(unique_trans)
            total_score = total_score + score
            language_count += 1

        return total_score / language_count if language_count > 0 else 0.0

    def _suggest_domain(self, _term: str, contexts: List[str]) -> str:
        """Suggest domain for a term based on context."""
        # Check medical patterns
        medical_keywords = ["patient", "medical", "health", "clinical", "diagnosis"]
        medical_count = sum(
            1
            for context in contexts
            if any(keyword in context.lower() for keyword in medical_keywords)
        )

        if medical_count > len(contexts) / 2:
            return "medical"

        # Check UI patterns
        ui_keywords = ["button", "form", "menu", "dialog", "screen"]
        ui_count = sum(
            1
            for context in contexts
            if any(keyword in context.lower() for keyword in ui_keywords)
        )

        if ui_count > len(contexts) / 2:
            return "ui"

        return "general"

    def _calculate_confidence(
        self, frequency: int, consistency_score: float, language_coverage: int
    ) -> float:
        """Calculate confidence score for a term candidate."""
        # Normalize frequency (cap at 20)
        freq_score = min(frequency / 20, 1.0)

        # Normalize language coverage (assuming 10 languages max)
        coverage_score = min(language_coverage / 10, 1.0)

        # Weighted average
        confidence = freq_score * 0.3 + consistency_score * 0.5 + coverage_score * 0.2

        return confidence

    def _find_inconsistent_terms(
        self, translations: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Find terms with inconsistent translations."""
        inconsistent = []

        # Check existing glossary terms
        for term_key, term in self.terminology_manager.terms.items():
            if term.term != term_key:
                continue  # Skip synonyms

            # Look for usage in translations
            variations: Dict[str, int] = defaultdict(int)

            for translation in translations:
                if term.term.lower() in translation.get("source_text", "").lower():
                    target_text = translation.get("target_text", "")
                    target_lang = translation.get("target_language", "")

                    if target_lang in term.translations:
                        expected = term.translations[target_lang]
                        if expected.lower() not in target_text.lower():
                            variations[target_text] += 1

            if variations:
                inconsistent.append(
                    {
                        "term": term.term,
                        "expected_translations": term.translations,
                        "found_variations": dict(variations),
                        "severity": "high" if term.domain == "medical" else "medium",
                    }
                )

        return inconsistent

    def _find_deprecated_terms(self) -> List[str]:
        """Find terms that haven't been used recently."""
        deprecated: List[str] = []

        # Check term usage in translation memory
        # This is a simplified implementation
        # In production, would check actual usage data

        return deprecated

    @audit_phi_access("phi_access__apply_automatic_updates")
    @require_permission(AccessPermission.READ_PHI)
    def _apply_automatic_updates(self) -> List[str]:
        """Apply automatic updates to glossary."""
        updated = []

        for term, candidate in self.candidate_terms.items():
            # Check if term should be auto-added
            if (
                candidate.confidence >= self.update_config["confidence_threshold"]
                and candidate.consistency_score
                >= self.update_config["min_consistency_score"]
            ):

                # Check if term already exists
                existing_term = self.terminology_manager.get_term(term)

                if not existing_term:
                    # Create new term
                    new_term = Term(
                        term=candidate.term,
                        definition="Auto-detected term from translations",
                        domain=candidate.suggested_domain,
                        translations={
                            lang: trans[0] if len(set(trans)) == 1 else trans[0]
                            for lang, trans in candidate.translations.items()
                            if trans
                        },
                        approved=False,  # Require manual approval
                    )

                    self.terminology_manager.add_term(new_term)
                    updated.append(term)

                    logger.info(f"Auto-added term '{term}' to glossary")

        return updated

    def review_candidates(
        self, min_confidence: float = 0.5
    ) -> List[GlossaryUpdateCandidate]:
        """Get candidates for manual review."""
        return [
            candidate
            for candidate in self.candidate_terms.values()
            if (
                candidate.confidence >= min_confidence
                and candidate.confidence < self.update_config["confidence_threshold"]
            )
        ]

    def approve_candidate(
        self, term: str, definition: str, translations: Optional[Dict[str, str]] = None
    ) -> bool:
        """Manually approve a candidate term."""
        candidate = self.candidate_terms.get(term)
        if not candidate:
            return False

        # Use provided translations or candidate's translations
        final_translations = translations or {
            lang: trans[0] for lang, trans in candidate.translations.items() if trans
        }

        new_term = Term(
            term=term,
            definition=definition,
            domain=candidate.suggested_domain,
            translations=final_translations,
            approved=True,
        )

        self.terminology_manager.add_term(new_term)

        # Remove from candidates
        del self.candidate_terms[term]

        logger.info(f"Manually approved term '{term}'")

        return True

    @audit_phi_access("phi_access_export_update_report")
    @require_permission(AccessPermission.READ_PHI)
    def export_update_report(
        self, report: GlossaryUpdateReport, output_path: str
    ) -> None:
        """Export update report to file."""
        report_data = {
            "generated_at": datetime.now().isoformat(),
            "summary": {
                "analyzed_translations": report.analyzed_translations,
                "new_candidates": len(report.new_term_candidates),
                "inconsistent_terms": len(report.inconsistent_terms),
                "updated_terms": len(report.updated_terms),
                "deprecated_terms": len(report.deprecated_terms),
                "analysis_time_seconds": report.analysis_time,
            },
            "candidates": [
                {
                    "term": c.term,
                    "frequency": c.frequency,
                    "confidence": c.confidence,
                    "consistency_score": c.consistency_score,
                    "suggested_domain": c.suggested_domain,
                    "translations": c.translations,
                }
                for c in report.new_term_candidates
            ],
            "inconsistencies": report.inconsistent_terms,
        }

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(report_data, f, indent=2, ensure_ascii=False)
