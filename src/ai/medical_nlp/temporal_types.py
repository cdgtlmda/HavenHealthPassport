"""Temporal Types and Data Structures.

Defines types and structures for temporal reasoning.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional


class TemporalType(Enum):
    """Types of temporal expressions."""

    DATE = "date"  # Specific date
    TIME = "time"  # Specific time
    DATETIME = "datetime"  # Date and time
    DURATION = "duration"  # Time span
    FREQUENCY = "frequency"  # Recurring pattern
    AGE = "age"  # Age expression
    RELATIVE = "relative"  # Relative to reference
    FUZZY = "fuzzy"  # Approximate time
    SET = "set"  # Recurring set


class TemporalRelation(Enum):
    """Temporal relationships between events."""

    BEFORE = "before"
    AFTER = "after"
    DURING = "during"
    OVERLAP = "overlap"
    SIMULTANEOUS = "simultaneous"
    STARTED_BY = "started_by"
    FINISHED_BY = "finished_by"
    INCLUDES = "includes"


@dataclass
class TemporalExpression:
    """A temporal expression found in text."""

    text: str  # Original text
    start_pos: int  # Start position in text
    end_pos: int  # End position in text
    temporal_type: TemporalType  # Type of expression
    normalized_value: Optional[Any] = None  # Normalized representation
    confidence: float = 1.0  # Confidence score
    context: str = ""  # Surrounding context
    attributes: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MedicalEvent:
    """A medical event with temporal information."""

    event_text: str  # Event description
    event_type: str  # Type of event
    temporal_expressions: List[TemporalExpression] = field(default_factory=list)
    absolute_time: Optional[datetime] = None  # Resolved absolute time
    duration: Optional[timedelta] = None  # Event duration
    attributes: Dict[str, Any] = field(default_factory=dict)
