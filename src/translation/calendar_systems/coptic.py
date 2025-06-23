"""Coptic calendar conversion implementation."""

import math
from typing import Tuple


class CopticCalendarConverter:
    """Coptic calendar conversion implementation."""

    JD_EPOCH = 1825029.5

    @staticmethod
    def coptic_to_jd(year: int, month: int, day: int) -> float:
        """Convert Coptic date to Julian Day Number."""
        return (
            CopticCalendarConverter.JD_EPOCH
            + (year - 1) * 365
            + math.floor(year / 4)
            + (month - 1) * 30
            + day
            - 1
        )

    @staticmethod
    def jd_to_coptic(jd: float) -> Tuple[int, int, int]:
        """Convert Julian Day Number to Coptic date."""
        days_from_epoch = jd - CopticCalendarConverter.JD_EPOCH
        year = math.floor((days_from_epoch + 366) / 365.25)
        remaining = days_from_epoch - (year - 1) * 365 - math.floor((year - 1) / 4)
        month = min(13, math.floor(remaining / 30) + 1)
        day = remaining - (month - 1) * 30 + 1
        return int(year), int(month), int(day)
