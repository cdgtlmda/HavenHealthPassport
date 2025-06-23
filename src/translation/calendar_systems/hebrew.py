"""Hebrew calendar conversion implementation."""


class HebrewCalendarConverter:
    """Hebrew calendar conversion implementation."""

    @staticmethod
    def hebrew_to_jd(year: int, month: int, day: int) -> float:
        """Convert Hebrew date to Julian Day Number."""
        # Hebrew calendar calculations are complex
        # This is a simplified implementation
        # In production, use a library like pyluach

        # Approximate conversion (simplified)
        days_from_epoch = (year - 1) * 365.25 + (month - 1) * 29.5 + day
        return 347998.5 + days_from_epoch

    @staticmethod
    def is_hebrew_leap_year(year: int) -> bool:
        """Check if a Hebrew year is a leap year."""
        return (7 * year + 1) % 19 < 7
