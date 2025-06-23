"""
Base Glossary Matcher.

This module provides the core glossary matching functionality for identifying
medical terms in text that need special handling during translation.
"""

import logging
import re
from collections import defaultdict
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional

from ..glossaries import MedicalTerm, TermPriority, glossary_manager

logger = logging.getLogger(__name__)


class MatchType(str, Enum):
    """Types of term matches."""

    EXACT = "exact"
    PARTIAL = "partial"
    FUZZY = "fuzzy"
    CONTEXTUAL = "contextual"
    ABBREVIATION = "abbreviation"
    SYNONYM = "synonym"


class MatchConfidence(str, Enum):
    """Confidence levels for matches."""

    VERY_HIGH = "very_high"  # 0.95-1.0
    HIGH = "high"  # 0.85-0.95
    MEDIUM = "medium"  # 0.70-0.85
    LOW = "low"  # 0.50-0.70
    VERY_LOW = "very_low"  # < 0.50


@dataclass
class TermMatch:
    """Represents a matched term in text."""

    term: MedicalTerm
    matched_text: str
    start_pos: int
    end_pos: int
    match_type: MatchType
    confidence: float
    context: Optional[str] = None
    matched_variant: Optional[str] = None  # Which alias/synonym was matched

    @property
    def confidence_level(self) -> MatchConfidence:
        """Get confidence level category."""
        if self.confidence >= 0.95:
            return MatchConfidence.VERY_HIGH
        elif self.confidence >= 0.85:
            return MatchConfidence.HIGH
        elif self.confidence >= 0.70:
            return MatchConfidence.MEDIUM
        elif self.confidence >= 0.50:
            return MatchConfidence.LOW
        else:
            return MatchConfidence.VERY_LOW

    @property
    def should_preserve(self) -> bool:
        """Determine if this match should be preserved during translation."""
        # Always preserve critical terms
        if self.term.priority == TermPriority.CRITICAL:
            return True

        # Preserve high priority terms with high confidence
        if self.term.priority == TermPriority.HIGH and self.confidence >= 0.85:
            return True

        # Preserve exact matches of medium priority terms
        if (
            self.term.priority == TermPriority.MEDIUM
            and self.match_type == MatchType.EXACT
        ):
            return True

        # Check term-specific preservation flag
        return self.term.preserve_exact


@dataclass
class MatchingOptions:
    """Options for term matching."""

    case_sensitive: bool = False
    match_partial: bool = True
    match_fuzzy: bool = True
    fuzzy_threshold: float = 0.85
    context_window: int = 50  # Characters around match for context
    max_word_distance: int = 3  # For multi-word terms
    include_abbreviations: bool = True
    include_synonyms: bool = True
    confidence_threshold: float = 0.5


class GlossaryMatcher:
    """Base glossary matching engine."""

    def __init__(self, options: Optional[MatchingOptions] = None):
        """Initialize the base matcher with optional configuration."""
        self.options = options or MatchingOptions()
        self._compiled_patterns: Dict[str, re.Pattern] = {}
        self._term_index: Dict[str, List[MedicalTerm]] = defaultdict(list)
        self._build_indices()

    def _build_indices(self) -> None:
        """Build search indices for efficient matching."""
        # Index all terms from glossary manager
        all_glossaries = [glossary_manager.base_glossary] + list(
            glossary_manager.domain_glossaries.values()
        )

        for glossary in all_glossaries:
            for _, term in glossary.terms.items():
                # Index by main term
                self._add_to_index(term.term.lower(), term)

                # Index by aliases
                for alias in term.aliases:
                    self._add_to_index(alias.lower(), term)

        logger.info("Built index with %d unique keys", len(self._term_index))

    def _add_to_index(self, key: str, term: MedicalTerm) -> None:
        """Add term to search index."""
        if term not in self._term_index[key]:
            self._term_index[key].append(term)

    def find_matches(self, text: str) -> List[TermMatch]:
        """Find all glossary term matches in text."""
        matches = []

        # Exact matching
        matches.extend(self._find_exact_matches(text))

        # Partial matching
        if self.options.match_partial:
            matches.extend(self._find_partial_matches(text))

        # Multi-word matching
        matches.extend(self._find_multiword_matches(text))

        # Abbreviation matching
        if self.options.include_abbreviations:
            matches.extend(self._find_abbreviation_matches(text))

        # Remove duplicates and overlaps
        matches = self._resolve_overlaps(matches)

        # Filter by confidence threshold
        matches = [
            m for m in matches if m.confidence >= self.options.confidence_threshold
        ]

        # Sort by position
        matches.sort(key=lambda m: (m.start_pos, -m.confidence))

        return matches

    def _find_exact_matches(self, text: str) -> List[TermMatch]:
        """Find exact term matches."""
        matches = []

        # Use word boundaries for matching
        words = re.finditer(r"\b[\w\-\.]+\b", text)

        for word_match in words:
            word = word_match.group()
            word_key = word.lower() if not self.options.case_sensitive else word

            if word_key in self._term_index:
                for term in self._term_index[word_key]:
                    # Check case sensitivity requirements
                    if term.case_sensitive and word != term.term:
                        continue

                    match = TermMatch(
                        term=term,
                        matched_text=word,
                        start_pos=word_match.start(),
                        end_pos=word_match.end(),
                        match_type=MatchType.EXACT,
                        confidence=1.0,
                        context=self._extract_context(
                            text, word_match.start(), word_match.end()
                        ),
                    )
                    matches.append(match)

        return matches

    def _find_partial_matches(self, text: str) -> List[TermMatch]:
        """Find partial term matches (e.g., 'cardiac' in 'cardiovascular')."""
        matches = []

        # Look for terms that might be part of larger words
        for term_key, terms in self._term_index.items():
            if len(term_key) < 4:  # Skip very short terms for partial matching
                continue

            # Find all occurrences
            pattern = re.compile(
                rf"\b\w*{re.escape(term_key)}\w*\b",
                re.IGNORECASE if not self.options.case_sensitive else 0,
            )

            for match in pattern.finditer(text):
                matched_text = match.group()

                # Skip if it's an exact match (already handled)
                if matched_text.lower() == term_key:
                    continue

                for term in terms:
                    if term.case_sensitive:
                        continue  # Skip case-sensitive terms for partial matching

                    # Calculate confidence based on how much of the word is the term
                    confidence = len(term_key) / len(matched_text)

                    if confidence >= 0.6:  # At least 60% of the word should be the term
                        match_obj = TermMatch(
                            term=term,
                            matched_text=matched_text,
                            start_pos=match.start(),
                            end_pos=match.end(),
                            match_type=MatchType.PARTIAL,
                            confidence=confidence
                            * 0.9,  # Slightly reduce confidence for partial
                            context=self._extract_context(
                                text, match.start(), match.end()
                            ),
                        )
                        matches.append(match_obj)

        return matches

    def _find_multiword_matches(self, text: str) -> List[TermMatch]:
        """Find multi-word term matches (e.g., 'heart attack', 'blood pressure')."""
        matches = []

        # Get all multi-word terms
        multiword_terms = []
        for terms_list in self._term_index.values():
            for term in terms_list:
                if " " in term.term:
                    multiword_terms.append(term)

        # Remove duplicates
        multiword_terms = list({t.term: t for t in multiword_terms}.values())

        # Sort by length (longest first) to match longer phrases first
        multiword_terms.sort(key=lambda t: len(t.term), reverse=True)

        for term in multiword_terms:
            # Create pattern for the multi-word term
            term_pattern = term.term
            if not term.case_sensitive:
                term_pattern = term_pattern.lower()

            # Allow some flexibility in spacing and word boundaries
            pattern_parts = term_pattern.split()
            pattern_regex = (
                r"\b" + r"\s+".join(re.escape(part) for part in pattern_parts) + r"\b"
            )

            flags = 0 if term.case_sensitive else re.IGNORECASE
            pattern = re.compile(pattern_regex, flags)

            for match in pattern.finditer(text):
                match_obj = TermMatch(
                    term=term,
                    matched_text=match.group(),
                    start_pos=match.start(),
                    end_pos=match.end(),
                    match_type=MatchType.EXACT,
                    confidence=1.0,
                    context=self._extract_context(text, match.start(), match.end()),
                )
                matches.append(match_obj)

        return matches

    def _find_abbreviation_matches(self, text: str) -> List[TermMatch]:
        """Find abbreviation matches (e.g., 'MI' for 'myocardial infarction')."""
        matches = []

        # Look for uppercase abbreviations
        abbrev_pattern = re.compile(r"\b[A-Z]{2,}\b")

        for match in abbrev_pattern.finditer(text):
            abbrev = match.group()
            abbrev_lower = abbrev.lower()

            # Check if this abbreviation is in our index
            if abbrev_lower in self._term_index or abbrev in self._term_index:
                terms = self._term_index.get(abbrev_lower, []) + self._term_index.get(
                    abbrev, []
                )

                for term in terms:
                    # Check if this is actually an abbreviation (in aliases)
                    if abbrev in term.aliases or abbrev_lower in [
                        a.lower() for a in term.aliases
                    ]:
                        match_obj = TermMatch(
                            term=term,
                            matched_text=abbrev,
                            start_pos=match.start(),
                            end_pos=match.end(),
                            match_type=MatchType.ABBREVIATION,
                            confidence=0.95,  # High confidence for exact abbreviation match
                            context=self._extract_context(
                                text, match.start(), match.end()
                            ),
                            matched_variant=abbrev,
                        )
                        matches.append(match_obj)

        return matches

    def _extract_context(self, text: str, start: int, end: int) -> str:
        """Extract context around a match."""
        window = self.options.context_window
        context_start = max(0, start - window)
        context_end = min(len(text), end + window)

        context = text[context_start:context_end]

        # Mark the matched portion
        match_offset = start - context_start
        match_length = end - start

        marked_context = (
            context[:match_offset]
            + f"**{context[match_offset:match_offset + match_length]}**"
            + context[match_offset + match_length :]
        )

        return marked_context

    def _resolve_overlaps(self, matches: List[TermMatch]) -> List[TermMatch]:
        """Resolve overlapping matches by keeping the best ones."""
        if not matches:
            return matches

        # Sort by start position and confidence
        sorted_matches = sorted(matches, key=lambda m: (m.start_pos, -m.confidence))

        resolved = []
        last_end = -1

        for match in sorted_matches:
            # No overlap
            if match.start_pos >= last_end:
                resolved.append(match)
                last_end = match.end_pos
            else:
                # Overlap - check if this match is better
                if resolved and match.confidence > resolved[-1].confidence * 1.2:
                    # Replace with better match
                    resolved[-1] = match
                    last_end = match.end_pos

        return resolved

    def get_unmatched_terms(self, text: str) -> List[MedicalTerm]:
        """Get important terms that should be in the text but weren't found."""
        matches = self.find_matches(text)
        matched_terms = {m.term for m in matches}

        # Get all critical and high priority terms
        important_terms = []
        all_glossaries = [glossary_manager.base_glossary] + list(
            glossary_manager.domain_glossaries.values()
        )

        for glossary in all_glossaries:
            for term in glossary.terms.values():
                if term.priority in [TermPriority.CRITICAL, TermPriority.HIGH]:
                    if term not in matched_terms:
                        important_terms.append(term)

        return important_terms
