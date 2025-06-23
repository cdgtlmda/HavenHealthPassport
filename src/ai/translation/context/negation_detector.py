"""Negation Detection for Medical Context.

This module provides negation detection capabilities for medical text,
identifying when medical conditions, symptoms, or treatments are negated.
"""

import re
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Tuple


class NegationScope(Enum):
    """Scope of negation in text."""

    PRE_NEGATION = "pre_negation"  # Negation before the term
    POST_NEGATION = "post_negation"  # Negation after the term
    PSEUDO_NEGATION = "pseudo_negation"  # Appears negative but isn't


@dataclass
class NegationSpan:
    """Represents a negated span in text."""

    start: int
    end: int
    negation_word: str
    scope: NegationScope
    confidence: float


class NegationDetector:
    """Detects negation in medical text."""

    def __init__(self) -> None:
        """Initialize the NegationDetector with medical-specific patterns."""
        # Pre-negation triggers (appear before negated term)
        self.pre_negation_triggers = {
            "no": 1.0,
            "not": 1.0,
            "without": 1.0,
            "denies": 0.9,
            "denied": 0.9,
            "denying": 0.9,
            "negative for": 1.0,
            "no evidence of": 1.0,
            "no sign of": 1.0,
            "no history of": 1.0,
            "absence of": 1.0,
            "absent": 0.9,
            "rather than": 0.8,
            "ruled out": 0.9,
            "rule out": 0.8,
            "free of": 1.0,
            "failed to reveal": 1.0,
        }

        # Post-negation triggers (appear after negated term)
        self.post_negation_triggers = {
            "absent": 0.9,
            "denied": 0.9,
            "not detected": 1.0,
            "not found": 1.0,
            "not present": 1.0,
            "negative": 0.8,
            "unremarkable": 0.7,
        }

        # Pseudo-negation triggers (look like negation but aren't)
        self.pseudo_negation_triggers = {
            "no increase",
            "no change",
            "not only",
            "not necessarily",
            "no further",
            "not certain whether",
        }

        # Termination words (end negation scope)
        self.termination_words = {
            "but",
            "however",
            "although",
            "though",
            "except",
            "aside from",
            "apart from",
            "other than",
            ".",
            ",",
            ";",
            ":",
            "?",
        }

        # Common medical terms that are often negated
        self.medical_terms_pattern = re.compile(
            r"\b(pain|fever|cough|nausea|vomiting|diarrhea|rash|bleeding|"
            r"swelling|tenderness|discharge|symptoms?|signs?|history|"
            r"evidence|findings?|abnormalit(?:y|ies)|disease|disorder|"
            r"condition|infection|inflammation|injury|trauma)\b",
            re.IGNORECASE,
        )

    def detect_negations(self, text: str) -> List[NegationSpan]:
        """Detect all negations in the text.

        Args:
            text: Input medical text

        Returns:
            List of NegationSpan objects
        """
        negations = []
        text_lower = text.lower()

        # Check for pre-negations
        for trigger, confidence in self.pre_negation_triggers.items():
            pattern = rf"\b{re.escape(trigger)}\b"
            for match in re.finditer(pattern, text_lower):
                span = self._find_negation_scope(
                    text,
                    match.start(),
                    match.end(),
                    trigger,
                    NegationScope.PRE_NEGATION,
                    confidence,
                )
                if span:
                    negations.append(span)

        # Check for post-negations
        for trigger, confidence in self.post_negation_triggers.items():
            pattern = rf"\b{re.escape(trigger)}\b"
            for match in re.finditer(pattern, text_lower):
                span = self._find_negation_scope(
                    text,
                    match.start(),
                    match.end(),
                    trigger,
                    NegationScope.POST_NEGATION,
                    confidence,
                )
                if span:
                    negations.append(span)

        # Filter out pseudo-negations
        negations = self._filter_pseudo_negations(text, negations)

        # Merge overlapping spans
        negations = self._merge_overlapping_spans(negations)

        return negations

    def is_negated(self, text: str, term: str) -> Tuple[bool, float]:
        """Check if a specific term is negated in the text.

        Args:
            text: Input medical text
            term: Term to check for negation

        Returns:
            Tuple of (is_negated, confidence)
        """
        negations = self.detect_negations(text)
        term_lower = term.lower()

        # Find term position in text
        text_lower = text.lower()
        term_start = text_lower.find(term_lower)

        if term_start == -1:
            return False, 0.0

        term_end = term_start + len(term)

        # Check if term falls within any negation span
        for negation in negations:
            if term_start >= negation.start and term_end <= negation.end:
                return True, negation.confidence

        return False, 0.0

    def _find_negation_scope(
        self,
        text: str,
        trigger_start: int,
        trigger_end: int,
        trigger: str,
        scope_type: NegationScope,
        confidence: float,
    ) -> Optional[NegationSpan]:
        """Find the scope of a negation trigger.

        Args:
            text: Original text
            trigger_start: Start position of trigger
            trigger_end: End position of trigger
            trigger: The negation trigger word
            scope_type: Type of negation scope
            confidence: Confidence score for this trigger

        Returns:
            NegationSpan or None
        """
        if scope_type == NegationScope.PRE_NEGATION:
            # Look forward for the scope
            scope_start = trigger_start
            scope_end = self._find_forward_boundary(text, trigger_end)

            # Check if there's a medical term in the scope
            scope_text = text[trigger_end:scope_end]
            if not self.medical_terms_pattern.search(scope_text):
                return None

        else:  # POST_NEGATION
            # Look backward for the scope
            scope_start = self._find_backward_boundary(text, trigger_start)
            scope_end = trigger_end

            # Check if there's a medical term in the scope
            scope_text = text[scope_start:trigger_start]
            if not self.medical_terms_pattern.search(scope_text):
                return None

        return NegationSpan(
            start=scope_start,
            end=scope_end,
            negation_word=trigger,
            scope=scope_type,
            confidence=confidence,
        )

    def _find_forward_boundary(self, text: str, start_pos: int) -> int:
        """Find forward boundary of negation scope."""
        # Look for termination words or punctuation
        remaining_text = text[start_pos:]
        min_pos = len(text)

        for term in self.termination_words:
            pos = remaining_text.find(term)
            if pos != -1 and pos < min_pos:
                min_pos = pos

        # Also check for line breaks
        newline_pos = remaining_text.find("\n")
        if newline_pos != -1 and newline_pos < min_pos:
            min_pos = newline_pos

        # Default to next 5 words if no terminator found
        if min_pos == len(text):
            words = remaining_text.split()[:5]
            min_pos = len(" ".join(words))

        return start_pos + min_pos

    def _find_backward_boundary(self, text: str, end_pos: int) -> int:
        """Find backward boundary of negation scope."""
        # Look backward for termination words or punctuation
        preceding_text = text[:end_pos]
        max_pos = 0

        for term in self.termination_words:
            pos = preceding_text.rfind(term)
            if pos != -1 and pos > max_pos:
                max_pos = pos + len(term)

        # Also check for line breaks
        newline_pos = preceding_text.rfind("\n")
        if newline_pos != -1 and newline_pos > max_pos:
            max_pos = newline_pos + 1

        # Default to previous 3 words if no terminator found
        if max_pos == 0:
            words = preceding_text.split()[-3:]
            if words:
                first_word_start = preceding_text.rfind(words[0])
                max_pos = first_word_start if first_word_start != -1 else 0

        return max_pos

    def _filter_pseudo_negations(
        self, text: str, negations: List[NegationSpan]
    ) -> List[NegationSpan]:
        """Filter out pseudo-negations."""
        filtered = []

        for negation in negations:
            # Check if this matches a pseudo-negation pattern
            negation_context = text[
                max(0, negation.start - 20) : min(len(text), negation.end + 20)
            ].lower()

            is_pseudo = False
            for pseudo_trigger in self.pseudo_negation_triggers:
                if pseudo_trigger in negation_context:
                    is_pseudo = True
                    break

            if not is_pseudo:
                filtered.append(negation)

        return filtered

    def _merge_overlapping_spans(
        self, negations: List[NegationSpan]
    ) -> List[NegationSpan]:
        """Merge overlapping negation spans."""
        if not negations:
            return negations

        # Sort by start position
        sorted_negations = sorted(negations, key=lambda x: x.start)
        merged = [sorted_negations[0]]

        for current in sorted_negations[1:]:
            last = merged[-1]

            # Check for overlap
            if current.start <= last.end:
                # Merge spans
                merged[-1] = NegationSpan(
                    start=min(last.start, current.start),
                    end=max(last.end, current.end),
                    negation_word=f"{last.negation_word}+{current.negation_word}",
                    scope=last.scope,  # Keep first scope type
                    confidence=max(last.confidence, current.confidence),
                )
            else:
                merged.append(current)

        return merged

    def annotate_text(self, text: str) -> str:
        """Annotate text with negation markers for visualization.

        Args:
            text: Input medical text

        Returns:
            Annotated text with negation markers
        """
        negations = self.detect_negations(text)

        # Sort negations by position (reverse order for correct insertion)
        negations.sort(key=lambda x: x.start, reverse=True)

        annotated = text
        for negation in negations:
            # Insert markers
            negated_text = annotated[negation.start : negation.end]
            marked_text = f"[NEGATED: {negated_text}]"
            annotated = (
                annotated[: negation.start] + marked_text + annotated[negation.end :]
            )

        return annotated
