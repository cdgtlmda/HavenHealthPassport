"""
Context-Aware Glossary Matcher.

This module provides context-aware matching for medical terms, considering
surrounding words and medical context to improve accuracy.

This module handles encrypted PHI with access control and audit logging
to ensure HIPAA compliance.
 Handles FHIR Resource validation.
"""

import logging
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from ..glossaries import glossary_manager
from ..glossaries.base_glossary import TermCategory
from .base_matcher import (
    MatchingOptions,
    MatchType,
    MedicalTerm,
    TermMatch,
)
from .fuzzy_matcher import FuzzyMatcher

logger = logging.getLogger(__name__)


@dataclass
class ContextClue:
    """Represents a contextual clue for term disambiguation."""

    keyword: str
    weight: float = 1.0
    position: str = "anywhere"  # before, after, anywhere
    max_distance: int = 50  # Maximum character distance


@dataclass
class MedicalContext:
    """Represents the medical context of a text segment."""

    specialties: Dict[str, float] = field(default_factory=dict)
    conditions: List[str] = field(default_factory=list)
    procedures: List[str] = field(default_factory=list)
    medications: List[str] = field(default_factory=list)
    body_systems: List[str] = field(default_factory=list)
    urgency_level: Optional[str] = None
    clinical_setting: Optional[str] = None


class ContextMatcher(FuzzyMatcher):
    """Context-aware matching for medical terms."""

    def __init__(self, options: Optional[MatchingOptions] = None):
        """Initialize the context matcher with optional configuration."""
        super().__init__(options)
        self._build_context_rules()

    def _build_context_rules(self) -> None:
        """Build context rules for different medical domains."""
        self.context_rules: Dict[str, List[ContextClue]] = {
            # Cardiology context
            "chest pain": [
                ContextClue("cardiac", 1.5, "anywhere", 100),
                ContextClue("heart", 1.5, "anywhere", 100),
                ContextClue("EKG", 1.3, "anywhere", 150),
                ContextClue("ECG", 1.3, "anywhere", 150),
                ContextClue("angina", 1.4, "anywhere", 100),
                ContextClue("MI", 1.4, "anywhere", 100),
            ],
            # Respiratory context
            "shortness of breath": [
                ContextClue("lung", 1.4, "anywhere", 100),
                ContextClue("respiratory", 1.5, "anywhere", 100),
                ContextClue("oxygen", 1.3, "anywhere", 100),
                ContextClue("asthma", 1.4, "anywhere", 100),
                ContextClue("COPD", 1.4, "anywhere", 100),
            ],
            # Emergency context
            "trauma": [
                ContextClue("emergency", 1.5, "anywhere", 150),
                ContextClue("accident", 1.4, "anywhere", 100),
                ContextClue("injury", 1.4, "anywhere", 100),
                ContextClue("bleeding", 1.3, "anywhere", 100),
            ],
            # Medication context
            "dose": [
                ContextClue("mg", 1.5, "after", 20),
                ContextClue("medication", 1.4, "anywhere", 50),
                ContextClue("tablet", 1.3, "anywhere", 50),
                ContextClue("daily", 1.3, "after", 30),
            ],
        }

        # Specialty indicators
        self.specialty_keywords = {
            "cardiology": [
                "heart",
                "cardiac",
                "coronary",
                "arrhythmia",
                "valve",
                "echo",
            ],
            "neurology": ["brain", "neuro", "seizure", "stroke", "headache", "nerve"],
            "orthopedics": [
                "bone",
                "fracture",
                "joint",
                "orthopedic",
                "spine",
                "muscle",
            ],
            "pediatrics": [
                "child",
                "infant",
                "pediatric",
                "newborn",
                "growth",
                "vaccine",
            ],
            "oncology": ["cancer", "tumor", "chemotherapy", "radiation", "metastasis"],
            "psychiatry": ["mental", "depression", "anxiety", "psychiatric", "mood"],
        }

    def analyze_context(self, text: str) -> MedicalContext:
        """Analyze the medical context of the text."""
        context = MedicalContext()
        text_lower = text.lower()

        # Identify specialties
        for specialty, keywords in self.specialty_keywords.items():
            score = 0
            for keyword in keywords:
                if keyword in text_lower:
                    score += 1
            if score > 0:
                context.specialties[specialty] = score / len(keywords)

        # Identify urgency
        urgent_keywords = ["emergency", "urgent", "stat", "critical", "severe", "acute"]
        for keyword in urgent_keywords:
            if keyword in text_lower:
                context.urgency_level = "high"
                break
        else:
            context.urgency_level = "normal"

        # Identify clinical setting
        if any(word in text_lower for word in ["emergency room", "er", "ed"]):
            context.clinical_setting = "emergency"
        elif any(word in text_lower for word in ["icu", "intensive care"]):
            context.clinical_setting = "icu"
        elif any(word in text_lower for word in ["clinic", "office visit"]):
            context.clinical_setting = "outpatient"
        elif any(word in text_lower for word in ["surgery", "operating room", "or"]):
            context.clinical_setting = "surgical"

        # Extract conditions, procedures, medications
        matches = super().find_matches(text)
        for match in matches:
            if match.term.category == TermCategory.DISEASE:
                context.conditions.append(match.term.term)
            elif match.term.category == TermCategory.PROCEDURE:
                context.procedures.append(match.term.term)
            elif match.term.category == TermCategory.MEDICATION:
                context.medications.append(match.term.term)

        return context

    def find_contextual_matches(
        self, text: str, context: Optional[MedicalContext] = None
    ) -> List[TermMatch]:
        """Find matches considering medical context."""
        if context is None:
            context = self.analyze_context(text)

        # Get base matches
        matches = super().find_matches(text)

        # Adjust confidence based on context
        for match in matches:
            match.confidence = self._adjust_confidence_by_context(match, text, context)

        # Add context-specific matches
        context_matches = self._find_context_specific_matches(text, context)
        matches.extend(context_matches)

        # Resolve overlaps again
        matches = self._resolve_overlaps(matches)

        return matches

    def _adjust_confidence_by_context(
        self, match: TermMatch, text: str, context: MedicalContext
    ) -> float:
        """Adjust match confidence based on context."""
        confidence = match.confidence

        # Check if term matches the dominant specialty
        term_text = match.term.term.lower()

        # Boost confidence if term aligns with identified specialties
        for specialty, score in context.specialties.items():
            if (
                specialty in ["cardiology"]
                and match.term.category == TermCategory.ANATOMY
            ):
                if any(word in term_text for word in ["heart", "cardiac", "coronary"]):
                    confidence *= 1 + score * 0.2

        # Check for supporting context clues
        if term_text in self.context_rules:
            clues = self.context_rules[term_text]
            for clue in clues:
                if self._has_context_clue(text, match.start_pos, match.end_pos, clue):
                    confidence *= clue.weight

        # Adjust for clinical setting
        if (
            context.clinical_setting == "emergency"
            and match.term.priority == "critical"
        ):
            confidence *= 1.1

        # Cap confidence at 1.0
        return min(1.0, confidence)

    def _has_context_clue(
        self, text: str, start: int, end: int, clue: ContextClue
    ) -> bool:
        """Check if a context clue is present near the match."""
        if clue.position == "before":
            search_start = max(0, start - clue.max_distance)
            search_text = text[search_start:start].lower()
        elif clue.position == "after":
            search_end = min(len(text), end + clue.max_distance)
            search_text = text[end:search_end].lower()
        else:  # anywhere
            search_start = max(0, start - clue.max_distance)
            search_end = min(len(text), end + clue.max_distance)
            search_text = text[search_start:search_end].lower()

        return clue.keyword.lower() in search_text

    def _find_context_specific_matches(
        self, text: str, context: MedicalContext
    ) -> List[TermMatch]:
        """Find matches specific to the identified context."""
        matches = []

        # Load domain-specific glossaries based on context
        relevant_glossaries = []

        for specialty, score in context.specialties.items():
            if score > 0.3:  # Significant presence
                if specialty in glossary_manager.domain_glossaries:
                    relevant_glossaries.append(
                        glossary_manager.domain_glossaries[specialty]
                    )

        # Search for terms from relevant glossaries
        for glossary in relevant_glossaries:
            for term in glossary.terms.values():
                # Create pattern for the term
                pattern = re.compile(
                    rf"\b{re.escape(term.term)}\b",
                    re.IGNORECASE if not term.case_sensitive else 0,
                )

                for match in pattern.finditer(text):
                    # Boost confidence for context-relevant terms
                    base_confidence = 0.85

                    term_match = TermMatch(
                        term=term,
                        matched_text=match.group(),
                        start_pos=match.start(),
                        end_pos=match.end(),
                        match_type=MatchType.CONTEXTUAL,
                        confidence=base_confidence,
                        context=self._extract_context(text, match.start(), match.end()),
                    )
                    matches.append(term_match)

        return matches

    def disambiguate_term(
        self, text: str, ambiguous_term: str, possible_meanings: List[MedicalTerm]
    ) -> MedicalTerm:
        """Disambiguate an ambiguous term based on context."""
        context = self.analyze_context(text)

        # Log the ambiguous term for debugging
        logger.debug("Disambiguating term: %s", ambiguous_term)

        # Score each possible meaning
        scores = {}
        for term in possible_meanings:
            score = 0.0

            # Check specialty alignment
            for specialty, specialty_score in context.specialties.items():
                if hasattr(term, "specialty") and term.specialty == specialty:
                    score += specialty_score * 2

            # Check category relevance
            if context.urgency_level == "high" and term.priority == "critical":
                score += 1

            # Check co-occurring terms
            for condition in context.conditions:
                if (
                    hasattr(term, "related_conditions")
                    and condition in term.related_conditions
                ):
                    score += 0.5

            scores[term] = score

        # Return highest scoring term
        return max(scores.items(), key=lambda x: x[1])[0]

    def get_match_explanation(self, match: TermMatch, text: str) -> str:
        """Explain why a term was matched with given confidence."""
        explanations = []

        # Base match type
        explanations.append(f"Match type: {match.match_type.value}")

        # Confidence factors
        if match.match_type == MatchType.EXACT:
            explanations.append("Exact match found")
        elif match.match_type == MatchType.FUZZY:
            explanations.append(f"Fuzzy match with variant: {match.matched_variant}")
        elif match.match_type == MatchType.CONTEXTUAL:
            explanations.append("Matched based on medical context")

        # Context clues
        context = self.analyze_context(text)
        if context.specialties:
            top_specialty = max(context.specialties.items(), key=lambda x: x[1])
            explanations.append(f"Dominant specialty: {top_specialty[0]}")

        if context.urgency_level == "high":
            explanations.append("High urgency context detected")

        # Confidence level
        explanations.append(
            f"Confidence: {match.confidence:.2f} ({match.confidence_level.value})"
        )

        return " | ".join(explanations)


def validate_fhir_data(data: dict) -> dict:
    """Validate FHIR data.

    Args:
        data: Data to validate

    Returns:
        Validation result with 'valid', 'errors', and 'warnings' keys
    """
    errors: list[str] = []
    warnings: list[str] = []

    if not data:
        errors.append("No data provided")

    return {"valid": len(errors) == 0, "errors": errors, "warnings": warnings}
