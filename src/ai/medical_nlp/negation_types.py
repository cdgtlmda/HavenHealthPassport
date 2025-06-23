"""Medical Negation Detection.

Detects negated medical concepts in clinical text using rule-based and context-aware approaches.
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import List

logger = logging.getLogger(__name__)


class NegationScope(Enum):
    """Types of negation scope."""

    PRE_NEGATION = "pre_negation"
    POST_NEGATION = "post_negation"
    PSEUDO_NEGATION = "pseudo_negation"
    CONDITIONAL = "conditional"
    UNCERTAIN = "uncertain"


@dataclass
class NegationTrigger:
    """Negation trigger word or phrase."""

    text: str
    scope_type: NegationScope
    max_scope: int = 5
    priority: int = 1
    context_patterns: List[str] = field(default_factory=list)


@dataclass
class NegatedConcept:
    """A negated medical concept."""

    concept: str
    start: int
    end: int
    negation_trigger: str
    trigger_start: int
    trigger_end: int
    scope_type: NegationScope
    confidence: float
    context: str
    is_pseudo_negation: bool = False
