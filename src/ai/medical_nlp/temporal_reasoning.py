"""Medical Temporal Reasoning.

Extracts and normalizes temporal information from medical text.
Handles dates, durations, frequencies, and temporal relationships.

HIPAA Compliance Notes:
- All PHI data processed by this module must be encrypted at rest and in transit
- Implement encryption for any PHI data before storage or transmission
"""

import logging
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, cast

import dateutil.parser
from dateutil.relativedelta import relativedelta

from src.healthcare.hipaa_access_control import (
    AccessLevel,
    require_phi_access,
)

logger = logging.getLogger(__name__)


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


class MedicalTemporalReasoner:
    """Medical temporal reasoning system.

    Features:
    - Extract temporal expressions from clinical text
    - Normalize dates, times, durations, and frequencies
    - Resolve relative temporal references
    - Build clinical timelines
    - Handle medical-specific temporal patterns
    """

    def __init__(
        self,
        reference_date: Optional[datetime] = None,
        enable_fuzzy: bool = True,
        language: str = "en",
    ):
        """Initialize temporal reasoner.

        Args:
            reference_date: Reference date for relative expressions
            enable_fuzzy: Enable fuzzy date parsing
            language: Language for temporal patterns
        """
        self.reference_date = reference_date or datetime.now()
        self.enable_fuzzy = enable_fuzzy
        self.language = language

        # Initialize patterns
        self._init_temporal_patterns()
        self._init_medical_patterns()

        # Compile all patterns after initialization
        self._compile_patterns()

        logger.info(
            "Initialized MedicalTemporalReasoner with reference date: %s",
            self.reference_date,
        )

    def _init_temporal_patterns(self) -> None:
        """Initialize temporal expression patterns."""
        # Date patterns
        self.date_patterns = [
            # Standard formats
            (r"\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\b", "standard_date"),
            (r"\b(\d{4}[/-]\d{1,2}[/-]\d{1,2})\b", "iso_date"),
            # Written dates
            (
                r"\b((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2},?\s+\d{2,4})\b",
                "written_date",
            ),
            (
                r"\b(\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{2,4})\b",
                "written_date",
            ),
            # Special dates
            (r"\b(today|yesterday|tomorrow)\b", "relative_date"),
            (r"\b(now|currently|present)\b", "current_time"),
        ]

        # Duration patterns
        self.duration_patterns = [
            # X days/weeks/months/years
            (r"\b(\d+)\s*(day|week|month|year)s?\b", "numeric_duration"),
            (r"\b(a|an|one)\s+(day|week|month|year)\b", "single_duration"),
            (
                r"\b(few|several|couple\s+of)\s+(days|weeks|months|years)\b",
                "fuzzy_duration",
            ),
            # Medical durations
            (
                r"\bfor\s+the\s+past\s+(\d+)\s*(day|week|month|year)s?\b",
                "past_duration",
            ),
            (r"\b(since)\s+(\d+)\s*(day|week|month|year)s?\s+ago\b", "since_duration"),
            (r"\bx\s*(\d+)\s*(d|day|wk|week|mo|month|yr|year)s?\b", "medical_duration"),
            # Ongoing
            (r"\b(ongoing|continuous|chronic|persistent)\b", "ongoing_duration"),
        ]

        # Relative time patterns
        self.relative_patterns = [
            # X ago
            (r"\b(\d+)\s*(day|week|month|year)s?\s+ago\b", "time_ago"),
            (
                r"\b(last)\s+(night|week|month|year|Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\b",
                "last_time",
            ),
            (r"\b(this)\s+(morning|afternoon|evening|week|month|year)\b", "this_time"),
            # Medical relative
            (r"\b(prior\s+to|before)\s+admission\b", "before_admission"),
            (r"\b(on\s+admission|at\s+presentation)\b", "on_admission"),
            (r"\b(post[\s-]?op|postoperative)\s+day\s+(\d+)\b", "postop_day"),
        ]

        # Frequency patterns
        self.frequency_patterns = [
            # Medical frequencies
            (r"\b(QD|qd|daily|once\s+daily|every\s+day)\b", "daily"),
            (r"\b(BID|bid|twice\s+daily|two\s+times\s+daily)\b", "twice_daily"),
            (r"\b(TID|tid|three\s+times\s+daily)\b", "three_times_daily"),
            (r"\b(QID|qid|four\s+times\s+daily)\b", "four_times_daily"),
            (r"\b(PRN|prn|as\s+needed)\b", "as_needed"),
            # Standard frequencies
            (r"\bevery\s+(\d+)\s*(hour|day|week|month)s?\b", "every_n"),
            (r"\b(\d+)\s*times?\s+per\s+(day|week|month)\b", "times_per"),
            (r"\b(weekly|monthly|yearly|annually)\b", "periodic"),
        ]

        # Age patterns
        self.age_patterns = [
            (r"\b(\d+)\s*y/?o\b", "age_yo"),
            (r"\b(\d+)\s*years?\s*old\b", "age_years_old"),
            (r"\b(\d+)\s*months?\s*old\b", "age_months_old"),
            (r"\b(\d+)\s*weeks?\s*old\b", "age_weeks_old"),
            (r"\bage\s*:?\s*(\d+)\b", "age_number"),
        ]

    def _init_medical_patterns(self) -> None:
        """Initialize medical-specific temporal patterns."""
        # Medical event patterns
        self.medical_events = {
            "onset": r"\b(onset|started|began|developed|first\s+noticed)\b",
            "diagnosis": r"\b(diagnosed|diagnosis|dx|found\s+to\s+have)\b",
            "treatment": r"\b(treated|started\s+on|initiated|given)\b",
            "resolution": r"\b(resolved|improved|better|cleared)\b",
            "admission": r"\b(admitted|admission|hospitalized)\b",
            "discharge": r"\b(discharged|discharge|sent\s+home)\b",
            "surgery": r"\b(surgery|operation|procedure|s/p)\b",
            "followup": r"\b(follow[\s-]?up|f/u|return\s+visit)\b",
        }

        # Time-sensitive conditions
        self.time_critical = {
            "acute": ["acute", "sudden", "abrupt", "rapid"],
            "subacute": ["subacute", "gradual", "progressive"],
            "chronic": ["chronic", "longstanding", "persistent", "ongoing"],
            "recurrent": ["recurrent", "recurring", "intermittent", "episodic"],
        }

    def _compile_patterns(self) -> None:
        """Compile regex patterns."""
        self.compiled_patterns = {
            "date": [(re.compile(p, re.IGNORECASE), t) for p, t in self.date_patterns],
            "duration": [
                (re.compile(p, re.IGNORECASE), t) for p, t in self.duration_patterns
            ],
            "relative": [
                (re.compile(p, re.IGNORECASE), t) for p, t in self.relative_patterns
            ],
            "frequency": [
                (re.compile(p, re.IGNORECASE), t) for p, t in self.frequency_patterns
            ],
            "age": [(re.compile(p, re.IGNORECASE), t) for p, t in self.age_patterns],
        }

        self.compiled_medical = {
            k: re.compile(v, re.IGNORECASE) for k, v in self.medical_events.items()
        }

    @require_phi_access(AccessLevel.READ)
    def extract_temporal_expressions(self, text: str) -> List[TemporalExpression]:
        """Extract all temporal expressions from text.

        Args:
            text: Medical text to analyze

        Returns:
            List of temporal expressions found
        """
        expressions = []

        # Extract different types of temporal expressions
        for temp_type, patterns in self.compiled_patterns.items():
            for pattern, pattern_type in patterns:
                for match in pattern.finditer(text):
                    # Map pattern type to TemporalType
                    if temp_type == "date":
                        temporal_type = TemporalType.DATE
                    elif temp_type == "duration":
                        temporal_type = TemporalType.DURATION
                    elif temp_type == "relative":
                        temporal_type = TemporalType.RELATIVE
                    elif temp_type == "frequency":
                        temporal_type = TemporalType.FREQUENCY
                    elif temp_type == "age":
                        temporal_type = TemporalType.AGE
                    else:
                        temporal_type = TemporalType.FUZZY

                    expr = TemporalExpression(
                        text=match.group(0),
                        start_pos=match.start(),
                        end_pos=match.end(),
                        temporal_type=temporal_type,
                        context=text[
                            max(0, match.start() - 20) : min(
                                len(text), match.end() + 20
                            )
                        ],
                        attributes={"pattern_type": pattern_type},
                    )

                    # Normalize the expression
                    self._normalize_expression(expr)

                    expressions.append(expr)

        # Remove duplicates and sort by position
        expressions = self._deduplicate_expressions(expressions)
        expressions.sort(key=lambda x: x.start_pos)

        return expressions

    def _normalize_expression(self, expr: TemporalExpression) -> None:
        """Normalize a temporal expression."""
        try:
            if expr.temporal_type == TemporalType.DATE:
                expr.normalized_value = self._normalize_date(expr)
            elif expr.temporal_type == TemporalType.DURATION:
                expr.normalized_value = self._normalize_duration(expr)
            elif expr.temporal_type == TemporalType.RELATIVE:
                expr.normalized_value = self._normalize_relative(expr)
            elif expr.temporal_type == TemporalType.FREQUENCY:
                expr.normalized_value = self._normalize_frequency(expr)
            elif expr.temporal_type == TemporalType.AGE:
                expr.normalized_value = self._normalize_age(expr)
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.debug("Failed to normalize expression '%s': %s", expr.text, e)
            expr.confidence *= 0.5

    def _normalize_date(self, expr: TemporalExpression) -> Optional[datetime]:
        """Normalize date expression."""
        text = expr.text.lower()
        pattern_type = expr.attributes.get("pattern_type")

        # Handle relative dates
        if pattern_type == "relative_date":
            if text == "today":
                return self.reference_date.replace(
                    hour=0, minute=0, second=0, microsecond=0
                )
            elif text == "yesterday":
                return (self.reference_date - timedelta(days=1)).replace(
                    hour=0, minute=0, second=0, microsecond=0
                )
            elif text == "tomorrow":
                return (self.reference_date + timedelta(days=1)).replace(
                    hour=0, minute=0, second=0, microsecond=0
                )

        # Try parsing with dateutil
        if self.enable_fuzzy:
            try:
                parsed = dateutil.parser.parse(
                    expr.text, fuzzy=True, default=self.reference_date
                )
                return cast(datetime, parsed)
            except (ValueError, OverflowError):
                pass

        return None

    def _normalize_duration(self, expr: TemporalExpression) -> Optional[timedelta]:
        """Normalize duration expression."""
        text = expr.text.lower()
        pattern_type = expr.attributes.get("pattern_type")

        # Extract number and unit
        if pattern_type in ["numeric_duration", "medical_duration", "past_duration"]:
            match = re.search(r"(\d+)\s*(d|day|wk|week|mo|month|yr|year)", text)
            if match:
                num = int(match.group(1))
                unit = match.group(2)

                # Convert to timedelta
                if unit in ["d", "day", "days"]:
                    return timedelta(days=num)
                elif unit in ["wk", "week", "weeks"]:
                    return timedelta(weeks=num)
                elif unit in ["mo", "month", "months"]:
                    return timedelta(days=num * 30)  # Approximate
                elif unit in ["yr", "year", "years"]:
                    return timedelta(days=num * 365)  # Approximate

        # Handle fuzzy durations
        elif pattern_type == "fuzzy_duration":
            if "few" in text:
                return timedelta(days=3)  # Approximate
            elif "several" in text:
                return timedelta(days=5)  # Approximate
            elif "couple" in text:
                return timedelta(days=2)

        # Handle ongoing
        elif pattern_type == "ongoing_duration":
            expr.attributes["ongoing"] = True
            return None

        return None

    def _normalize_relative(self, expr: TemporalExpression) -> Optional[datetime]:
        """Normalize relative time expression."""
        text = expr.text.lower()
        pattern_type = expr.attributes.get("pattern_type")

        if pattern_type == "time_ago":
            # Extract number and unit
            match = re.search(r"(\d+)\s*(day|week|month|year)s?\s+ago", text)
            if match:
                num = int(match.group(1))
                unit = match.group(2)

                if unit == "day":
                    return self.reference_date - timedelta(days=num)
                elif unit == "week":
                    return self.reference_date - timedelta(weeks=num)
                elif unit == "month":
                    return cast(
                        datetime, self.reference_date - relativedelta(months=num)
                    )
                elif unit == "year":
                    return cast(
                        datetime, self.reference_date - relativedelta(years=num)
                    )

        elif pattern_type == "last_time":
            # Handle "last week", "last month", etc.
            if "last week" in text:
                return self.reference_date - timedelta(weeks=1)
            elif "last month" in text:
                return cast(datetime, self.reference_date - relativedelta(months=1))
            elif "last year" in text:
                return cast(datetime, self.reference_date - relativedelta(years=1))

        return None

    def _normalize_frequency(
        self, expr: TemporalExpression
    ) -> Optional[Dict[str, Any]]:
        """Normalize frequency expression."""
        text = expr.text.lower()
        pattern_type = expr.attributes.get("pattern_type")

        # Medical frequencies
        freq_map: Dict[str, Dict[str, Any]] = {
            "daily": {"times": 1, "period": "day"},
            "twice_daily": {"times": 2, "period": "day"},
            "three_times_daily": {"times": 3, "period": "day"},
            "four_times_daily": {"times": 4, "period": "day"},
            "as_needed": {"times": None, "period": "as_needed"},
            "weekly": {"times": 1, "period": "week"},
            "monthly": {"times": 1, "period": "month"},
            "yearly": {"times": 1, "period": "year"},
        }

        if pattern_type in freq_map:
            return freq_map[pattern_type]

        # Extract custom frequency
        if pattern_type == "every_n":
            match = re.search(r"every\s+(\d+)\s*(hour|day|week|month)", text)
            if match:
                return {"every": int(match.group(1)), "period": match.group(2)}

        elif pattern_type == "times_per":
            match = re.search(r"(\d+)\s*times?\s+per\s+(day|week|month)", text)
            if match:
                return {"times": int(match.group(1)), "period": match.group(2)}

        return None

    def _normalize_age(self, expr: TemporalExpression) -> Optional[int]:
        """Normalize age expression to years."""
        text = expr.text
        pattern_type = expr.attributes.get("pattern_type")

        # Extract number
        match = re.search(r"(\d+)", text)
        if match:
            num = int(match.group(1))

            if pattern_type in ["age_yo", "age_years_old", "age_number"]:
                return num
            elif pattern_type == "age_months_old":
                return int(num / 12.0)
            elif pattern_type == "age_weeks_old":
                return int(num / 52.0)

        return None

    def _deduplicate_expressions(
        self, expressions: List[TemporalExpression]
    ) -> List[TemporalExpression]:
        """Remove duplicate/overlapping expressions."""
        if not expressions:
            return []

        # Sort by start position
        expressions.sort(key=lambda x: (x.start_pos, -x.end_pos))

        deduped = []
        last_end = -1

        for expr in expressions:
            # Skip if overlapping with previous
            if expr.start_pos < last_end:
                continue

            deduped.append(expr)
            last_end = expr.end_pos

        return deduped

    def extract_medical_timeline(self, text: str) -> List[MedicalEvent]:
        """Extract medical events and build timeline.

        Args:
            text: Medical narrative

        Returns:
            List of medical events with temporal information
        """
        events = []

        # Find medical events
        for event_type, pattern in self.compiled_medical.items():
            for match in pattern.finditer(text):
                # Extract event and surrounding context
                start = max(0, match.start() - 50)
                end = min(len(text), match.end() + 100)
                context = text[start:end]

                # Find temporal expressions near the event
                temporal_exprs = self.extract_temporal_expressions(context)

                # Create medical event
                event = MedicalEvent(
                    event_text=context.strip(),
                    event_type=event_type,
                    temporal_expressions=temporal_exprs,
                )

                # Try to resolve absolute time
                self._resolve_event_time(event)

                events.append(event)

        # Sort events by time
        events.sort(key=lambda e: e.absolute_time or datetime.min)

        return events

    def _resolve_event_time(self, event: MedicalEvent) -> None:
        """Resolve absolute time for a medical event."""
        # Look for date expressions first
        date_exprs = [
            e
            for e in event.temporal_expressions
            if e.temporal_type in [TemporalType.DATE, TemporalType.RELATIVE]
        ]

        if date_exprs and date_exprs[0].normalized_value:
            if isinstance(date_exprs[0].normalized_value, datetime):
                event.absolute_time = date_exprs[0].normalized_value
            elif isinstance(date_exprs[0].normalized_value, date):
                # Convert date to datetime
                event.absolute_time = datetime.combine(
                    date_exprs[0].normalized_value, datetime.min.time()
                )
            return

        # Look for relative expressions
        relative_exprs = [
            e
            for e in event.temporal_expressions
            if e.temporal_type == TemporalType.RELATIVE
        ]

        if relative_exprs and relative_exprs[0].normalized_value:
            event.absolute_time = relative_exprs[0].normalized_value
            return

        # Look for duration from reference
        duration_exprs = [
            e
            for e in event.temporal_expressions
            if e.temporal_type == TemporalType.DURATION
        ]

        if duration_exprs and duration_exprs[0].normalized_value:
            # Check if it's a "past duration" pattern
            if "past" in duration_exprs[0].text.lower():
                event.absolute_time = (
                    self.reference_date - duration_exprs[0].normalized_value
                )

    def calculate_temporal_relations(
        self, event1: MedicalEvent, event2: MedicalEvent
    ) -> Optional[TemporalRelation]:
        """Calculate temporal relationship between two events.

        Args:
            event1: First medical event
            event2: Second medical event

        Returns:
            Temporal relationship or None
        """
        if not event1.absolute_time or not event2.absolute_time:
            return None

        # Compare times
        if event1.absolute_time < event2.absolute_time:
            return TemporalRelation.BEFORE
        elif event1.absolute_time > event2.absolute_time:
            return TemporalRelation.AFTER
        else:
            return TemporalRelation.SIMULTANEOUS

    def format_timeline(self, events: List[MedicalEvent]) -> str:
        """Format medical timeline as readable text."""
        if not events:
            return "No temporal events found."

        timeline = []
        for event in events:
            time_str = "Unknown time"
            if event.absolute_time:
                time_str = event.absolute_time.strftime("%Y-%m-%d")

            timeline.append(
                f"{time_str}: {event.event_type.upper()} - {event.event_text[:50]}..."
            )

        return "\n".join(timeline)


# Convenience functions
@require_phi_access(AccessLevel.READ)
def extract_temporal_info(text: str) -> List[TemporalExpression]:
    """Extract temporal expressions from text."""
    reasoner = MedicalTemporalReasoner()
    return cast(List[TemporalExpression], reasoner.extract_temporal_expressions(text))


def build_medical_timeline(text: str) -> List[MedicalEvent]:
    """Build medical timeline from text."""
    reasoner = MedicalTemporalReasoner()
    return reasoner.extract_medical_timeline(text)
