"""Medical Negation Detection System.

Detects negated medical concepts in clinical text.
"""

import re
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Tuple


class NegationType(Enum):
    """Types of negation in medical text."""

    NEGATED = "negated"
    AFFIRMED = "affirmed"
    UNCERTAIN = "uncertain"
    CONDITIONAL = "conditional"


@dataclass
class NegationResult:
    """Result of negation detection."""

    text: str
    concept: str
    negation_type: NegationType
    trigger: Optional[str] = None
    confidence: float = 1.0
    start_pos: int = 0
    end_pos: int = 0


class MedicalNegationDetector:
    """Medical negation detector for clinical text."""

    def __init__(self) -> None:
        """Initialize the medical negation detector."""
        # Negation patterns with scope
        self.negation_patterns = {
            # Definite negations
            "no": (5, NegationType.NEGATED),
            "not": (5, NegationType.NEGATED),
            "without": (5, NegationType.NEGATED),
            "denies": (5, NegationType.NEGATED),
            "denied": (5, NegationType.NEGATED),
            "negative for": (7, NegationType.NEGATED),
            "no evidence of": (7, NegationType.NEGATED),
            "absence of": (5, NegationType.NEGATED),
            "ruled out": (5, NegationType.NEGATED),
            "r/o": (5, NegationType.NEGATED),
        }

        # Uncertainty patterns
        self.uncertainty_patterns = {
            "possible": (3, NegationType.UNCERTAIN),
            "probable": (3, NegationType.UNCERTAIN),
            "may": (3, NegationType.UNCERTAIN),
            "might": (3, NegationType.UNCERTAIN),
            "uncertain": (3, NegationType.UNCERTAIN),
            "questionable": (3, NegationType.UNCERTAIN),
            "cannot rule out": (5, NegationType.UNCERTAIN),
        }

        # Conditional patterns
        self.conditional_patterns = {
            "if": (3, NegationType.CONDITIONAL),
            "unless": (3, NegationType.CONDITIONAL),
            "monitor for": (5, NegationType.CONDITIONAL),
            "watch for": (5, NegationType.CONDITIONAL),
        }

        # Combine all patterns
        self.all_patterns = {
            **self.negation_patterns,
            **self.uncertainty_patterns,
            **self.conditional_patterns,
        }

        # Compile regex
        self._compile_patterns()

    def _compile_patterns(self) -> None:
        """Compile regex patterns."""
        # Sort patterns by length (longer patterns first) to match multi-word triggers
        sorted_triggers = sorted(self.all_patterns.keys(), key=len, reverse=True)
        escaped_triggers = [re.escape(t) for t in sorted_triggers]
        self.trigger_pattern = re.compile(
            r"\b(" + "|".join(escaped_triggers) + r")\b", re.IGNORECASE
        )

    def detect_negations(self, text: str) -> List[NegationResult]:
        """Detect negated concepts in text.

        Args:
            text: Clinical text to analyze

        Returns:
            List of negation results
        """
        results = []

        # Find all triggers
        for match in self.trigger_pattern.finditer(text):
            trigger = match.group(0).lower()
            scope, neg_type = self.all_patterns.get(trigger, (5, NegationType.NEGATED))

            # Get words after trigger
            start = match.end()
            remaining_text = text[start:]
            words = remaining_text.split()[:scope]

            if words:
                # Extract concept (up to 3 words)
                concept_words = []
                for word in words[:3]:
                    # Stop at punctuation
                    if word.strip(".,;:") != word:
                        break
                    concept_words.append(word)

                if concept_words:
                    concept = " ".join(concept_words)

                    results.append(
                        NegationResult(
                            text=text[match.start() : start + len(" ".join(words))],
                            concept=concept,
                            negation_type=neg_type,
                            trigger=trigger,
                            confidence=0.8 if neg_type == NegationType.NEGATED else 0.6,
                            start_pos=match.start(),
                            end_pos=start + len(concept),
                        )
                    )

        return results

    def is_negated(self, text: str, concept: str) -> Tuple[bool, float, str]:
        """Check if a specific concept is negated.

        Args:
            text: Text to analyze
            concept: Concept to check

        Returns:
            Tuple of (is_negated, confidence, negation_type)
        """
        results = self.detect_negations(text)
        for result in results:
            if concept.lower() in result.concept.lower():
                is_neg = result.negation_type == NegationType.NEGATED
                return (is_neg, result.confidence, result.negation_type.value)

        return (False, 1.0, NegationType.AFFIRMED.value)

    def annotate_text(self, text: str) -> str:
        """Annotate text with negation markers.

        Args:
            text: Text to annotate

        Returns:
            Annotated text
        """
        results = self.detect_negations(text)

        # Sort by position (reverse)
        results.sort(key=lambda x: x.start_pos, reverse=True)

        annotated = text
        for result in results:
            if result.negation_type == NegationType.NEGATED:
                # Insert markers
                annotated = (
                    annotated[: result.start_pos]
                    + f"[NEG:{result.trigger}]"
                    + annotated[result.start_pos :]
                )

        return annotated


# Convenience functions
def detect_negations(text: str) -> List[NegationResult]:
    """Detect negations in text."""
    detector = MedicalNegationDetector()
    return detector.detect_negations(text)


def is_negated(text: str, concept: str) -> bool:
    """Check if concept is negated."""
    detector = MedicalNegationDetector()
    negated, _, _ = detector.is_negated(text, concept)
    return negated
