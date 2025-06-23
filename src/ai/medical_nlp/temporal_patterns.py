"""Temporal Patterns for Medical Text.

Defines regex patterns for temporal expression extraction.
"""

from typing import List, Tuple


class TemporalPatterns:
    """Collection of temporal patterns for medical text."""

    @staticmethod
    def get_date_patterns() -> List[Tuple[str, str]]:
        """Get date patterns."""
        return [
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

    @staticmethod
    def get_duration_patterns() -> List[Tuple[str, str]]:
        """Get duration patterns."""
        return [
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

    @staticmethod
    def get_relative_patterns() -> List[Tuple[str, str]]:
        """Get relative time patterns."""
        return [
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
