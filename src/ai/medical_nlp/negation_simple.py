"""Medical Negation Detection System.

Simple but effective negation detection for medical text.
"""

import re
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Tuple


# Negation types
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
    """Simple medical negation detector."""

    def __init__(self) -> None:
        """Initialize the simple negation detector."""
        # Common negation triggers
        self.negation_triggers = {
            # Definite negations
            "no": 5,
            "not": 5,
            "without": 5,
            "denies": 5,
            "negative for": 7,
            "no evidence of": 7,
            "absence of": 5,
            "ruled out": 5,
            "free of": 5,
            "r/o": 5,
            # Uncertainty markers
            "possible": 3,
            "probable": 3,
            "may": 3,
            "might": 3,
            "uncertain": 3,
            "questionable": 3,
            # Conditional
            "if": 3,
            "unless": 3,
            "monitor for": 5,
        }

        # Compile patterns
        self._compile_patterns()

    def _compile_patterns(self) -> None:
        """Compile regex patterns."""
        triggers = [re.escape(t) for t in self.negation_triggers]
        self.trigger_pattern = re.compile(
            r"\b(" + "|".join(triggers) + r")\b", re.IGNORECASE
        )

    def detect_negations(self, text: str) -> List[NegationResult]:
        """Detect negations in text."""
        results = []

        # Find negation triggers
        for match in self.trigger_pattern.finditer(text):
            trigger = match.group(0).lower()
            scope = self.negation_triggers.get(trigger, 5)

            # Get context after trigger
            start = match.end()
            words_after = text[start:].split()[:scope]

            # Extract concepts (simplified)
            if words_after:
                concept = " ".join(words_after[:3])  # Up to 3 words

                # Determine negation type
                if trigger in ["possible", "probable", "may", "might", "uncertain"]:
                    neg_type = NegationType.UNCERTAIN
                elif trigger in ["if", "unless", "monitor for"]:
                    neg_type = NegationType.CONDITIONAL
                else:
                    neg_type = NegationType.NEGATED

                results.append(
                    NegationResult(
                        text=text[match.start() : start + len(" ".join(words_after))],
                        concept=concept.strip(),
                        negation_type=neg_type,
                        trigger=trigger,
                        confidence=0.8,
                        start_pos=match.start(),
                        end_pos=start + len(" ".join(words_after)),
                    )
                )

        return results

    def is_negated(self, text: str, concept: str) -> Tuple[bool, float]:
        """Check if a concept is negated."""
        results = self.detect_negations(text)

        for result in results:
            if concept.lower() in result.concept.lower():
                is_neg = result.negation_type == NegationType.NEGATED
                return (is_neg, result.confidence)

        return (False, 1.0)
