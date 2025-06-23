"""Medical Temporal Reasoning - Extract temporal expressions from medical text.

HIPAA Compliance Notes:
- All PHI data processed by this module must be encrypted at rest and in transit
- Access to this module should be restricted to authorized healthcare personnel only
- Implement role-based access control (RBAC) for all temporal reasoning functions
- Audit logs must be maintained for all PHI access and processing operations
"""

import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional


class TemporalType(Enum):
    """Types of temporal expressions."""

    DATE = "date"
    DURATION = "duration"
    FREQUENCY = "frequency"
    RELATIVE = "relative"


@dataclass
class TemporalExpression:
    """Represents a temporal expression in medical text."""

    text: str
    start_pos: int
    end_pos: int
    temporal_type: TemporalType
    normalized_value: Optional[Any] = None
    confidence: float = 1.0


def find_medical_temporal_patterns(
    text: str, reference_date: Optional[datetime] = None
) -> List[TemporalExpression]:
    """Find temporal patterns in medical text."""
    reasoner = MedicalTemporalReasoner(reference_date)
    return reasoner.extract_temporal_expressions(text)


class MedicalTemporalReasoner:
    """Extract temporal expressions from medical text."""

    def __init__(self, reference_date: Optional[datetime] = None):
        """Initialize the temporal extractor with optional reference date."""
        self.reference_date = reference_date or datetime.now()

        # Combined patterns
        self.patterns = {
            TemporalType.DATE: [
                (r"\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\b", "date"),
                (r"\b(today|yesterday|tomorrow)\b", "relative"),
            ],
            TemporalType.DURATION: [
                (r"\b(\d+)\s*(days?|weeks?|months?|years?)\b", "duration"),
                (r"\b(\d+)\s*(days?|weeks?|months?|years?)\s+ago\b", "ago"),
            ],
            TemporalType.FREQUENCY: [
                (r"\b(daily|BID|TID|QID|PRN)\b", "medical_freq"),
                (r"\bevery\s+(\d+)\s*(hours?|days?)\b", "interval"),
            ],
        }

    def extract_temporal_expressions(self, text: str) -> List[TemporalExpression]:
        """Extract all temporal expressions from text."""
        expressions = []

        for temp_type, patterns in self.patterns.items():
            for pattern, pattern_name in patterns:
                for match in re.finditer(pattern, text, re.IGNORECASE):
                    expr = TemporalExpression(
                        text=match.group(0),
                        start_pos=match.start(),
                        end_pos=match.end(),
                        temporal_type=temp_type,
                    )
                    # Normalize
                    self._normalize(expr, pattern_name)
                    expressions.append(expr)

        # Sort by position
        expressions.sort(key=lambda x: x.start_pos)
        return expressions

    def _normalize(self, expr: TemporalExpression, pattern_name: str) -> None:
        """Normalize temporal expression."""
        text = expr.text.lower()

        if expr.temporal_type == TemporalType.DATE:
            if pattern_name == "relative":
                if text == "today":
                    expr.normalized_value = self.reference_date.date()
                elif text == "yesterday":
                    expr.normalized_value = (
                        self.reference_date - timedelta(days=1)
                    ).date()
                elif text == "tomorrow":
                    expr.normalized_value = (
                        self.reference_date + timedelta(days=1)
                    ).date()

        elif expr.temporal_type == TemporalType.DURATION:
            # Extract number and unit
            match = re.search(r"(\d+)\s*(days?|weeks?|months?|years?)", text)
            if match:
                num = int(match.group(1))
                unit = match.group(2).rstrip("s")

                if unit == "day":
                    expr.normalized_value = timedelta(days=num)
                elif unit == "week":
                    expr.normalized_value = timedelta(weeks=num)
                # Approximate for months/years
                elif unit == "month":
                    expr.normalized_value = timedelta(days=num * 30)
                elif unit == "year":
                    expr.normalized_value = timedelta(days=num * 365)
                # Handle ago pattern
                if "ago" in text and expr.normalized_value:
                    expr.normalized_value = self.reference_date - expr.normalized_value

        elif expr.temporal_type == TemporalType.FREQUENCY:
            if pattern_name == "medical_freq":
                freq_map = {
                    "daily": {"times": 1, "period": "day"},
                    "bid": {"times": 2, "period": "day"},
                    "tid": {"times": 3, "period": "day"},
                    "qid": {"times": 4, "period": "day"},
                    "prn": {"times": 0, "period": "as_needed"},
                }
                expr.normalized_value = freq_map.get(text, {})

    def find_temporal_relations(self, text: str) -> List[Dict[str, Any]]:
        """Find temporal relationships in text."""
        expressions = self.extract_temporal_expressions(text)

        # Look for medical events with temporal info
        event_patterns = [
            (r"(diagnosed|dx)", "diagnosis"),
            (r"(started|began)", "onset"),
            (r"(admitted|admission)", "admission"),
            (r"(surgery|operation)", "surgery"),
        ]

        events = []
        for pattern, event_type in event_patterns:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                # Find nearby temporal expressions
                nearby_temporal = []
                for expr in expressions:
                    if abs(expr.start_pos - match.start()) < 50:
                        nearby_temporal.append(expr)

                if nearby_temporal:
                    events.append(
                        {
                            "event": event_type,
                            "text": match.group(0),
                            "position": match.start(),
                            "temporal": nearby_temporal[0] if nearby_temporal else None,
                        }
                    )

        return events


# Convenience functions
def extract_temporal_info(text: str) -> List[TemporalExpression]:
    """Extract temporal expressions from text."""
    reasoner = MedicalTemporalReasoner()
    return reasoner.extract_temporal_expressions(text)


def find_medical_timeline(text: str) -> List[Dict[str, Any]]:
    """Build medical timeline from text."""
    reasoner = MedicalTemporalReasoner()
    return reasoner.find_temporal_relations(text)
