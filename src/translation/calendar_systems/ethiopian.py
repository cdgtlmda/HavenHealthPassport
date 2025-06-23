"""Ethiopian calendar conversion implementation."""

import math
from datetime import date
from typing import Tuple


class EthiopianCalendarConverter:
    """Proper Ethiopian calendar conversion implementation."""

    # Ethiopian calendar constants
    JD_EPOCH_OFFSET_AMETE_ALEM = 1724220.5
    JD_EPOCH_OFFSET_AMETE_MIHRET = 1724235.5

    @staticmethod
    def ethiopian_to_jd(year: int, month: int, day: int) -> float:
        """Convert Ethiopian date to Julian Day Number."""
        # Ethiopian calendar epoch (Amete Mihret)
        epoch_offset = EthiopianCalendarConverter.JD_EPOCH_OFFSET_AMETE_MIHRET

        # Calculate Julian Day
        jd = (
            epoch_offset
            + 365 * year
            + math.floor(year / 4)
            + 30 * (month - 1)
            + day
            - 1
        )

        if month > 2:
            jd += 1

        return jd

    @staticmethod
    def jd_to_ethiopian(jd: float) -> Tuple[int, int, int]:
        """Convert Julian Day Number to Ethiopian date."""
        epoch_offset = EthiopianCalendarConverter.JD_EPOCH_OFFSET_AMETE_MIHRET

        # Calculate from epoch
        c = math.floor(jd - epoch_offset + 0.5)
        year = math.floor((4 * c + 3) / 1461)
        month = math.floor((c - math.floor((1461 * year) / 4)) / 30) + 1
        day = c - math.floor((1461 * year) / 4) - (month - 1) * 30 + 1

        # Adjust for 13th month
        if month > 13:
            month = 13
            day = c - math.floor((1461 * year) / 4) - 360 + 1

        return int(year), int(month), int(day)

    @staticmethod
    def gregorian_to_jd(date_obj: date) -> float:
        """Convert Gregorian date to Julian Day Number."""
        a = math.floor((14 - date_obj.month) / 12)
        y = date_obj.year + 4800 - a
        m = date_obj.month + 12 * a - 3

        return (
            date_obj.day
            + math.floor((153 * m + 2) / 5)
            + 365 * y
            + math.floor(y / 4)
            - math.floor(y / 100)
            + math.floor(y / 400)
            - 32045
        )

    @staticmethod
    def jd_to_gregorian(jd: float) -> date:
        """Convert Julian Day Number to Gregorian date."""
        a = math.floor(jd + 0.5) + 32044
        b = math.floor((4 * a + 3) / 146097)
        c = a - math.floor((146097 * b) / 4)
        d = math.floor((4 * c + 3) / 1461)
        e = c - math.floor((1461 * d) / 4)
        m = math.floor((5 * e + 2) / 153)

        day = e - math.floor((153 * m + 2) / 5) + 1
        month = m + 3 - 12 * math.floor(m / 10)
        year = 100 * b + d - 4800 + math.floor(m / 10)

        return date(int(year), int(month), int(day))
