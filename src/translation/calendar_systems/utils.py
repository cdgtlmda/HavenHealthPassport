"""Calendar utility functions."""

import calendar

from .nepali import NepaliCalendarConverter
from .types import CalendarSystem


class CalendarUtils:
    """Utility functions for calendar operations - critical for medical date calculations."""

    @staticmethod
    def is_leap_year(year: int, calendar_system: CalendarSystem) -> bool:
        """Check if a year is a leap year in the given calendar."""
        if calendar_system == CalendarSystem.GREGORIAN:
            return calendar.isleap(year)

        elif calendar_system == CalendarSystem.PERSIAN:
            # Persian calendar leap year calculation (33-year cycle)
            cycle = year % 128
            if cycle <= 29:
                return cycle % 33 in [1, 5, 9, 13, 17, 22, 26, 30]
            else:
                return (cycle - 29) % 33 in [1, 5, 9, 13, 17, 22, 26, 30]

        elif calendar_system == CalendarSystem.HIJRI:
            # Hijri leap years in 30-year cycle
            return year % 30 in [2, 5, 7, 10, 13, 16, 18, 21, 24, 26, 29]

        elif calendar_system == CalendarSystem.ETHIOPIAN:
            # Ethiopian leap year every 4 years
            return year % 4 == 3

        elif calendar_system == CalendarSystem.NEPALI:
            # Nepali calendar leap years are irregular, check data
            if year in NepaliCalendarConverter.BS_CALENDAR_DATA:
                days_in_year = sum(NepaliCalendarConverter.BS_CALENDAR_DATA[year])
                return days_in_year > 365
            return False

        elif calendar_system == CalendarSystem.BUDDHIST:
            # Buddhist calendar follows Gregorian leap years
            return calendar.isleap(year - 543)

        elif calendar_system == CalendarSystem.COPTIC:
            # Coptic leap year every 4 years
            return year % 4 == 3

        elif calendar_system == CalendarSystem.HEBREW:
            # Hebrew leap year calculation
            return (7 * year + 1) % 19 < 7

        # All calendar systems are covered above
        raise ValueError(f"Unknown calendar system: {calendar_system}")

    @staticmethod
    def get_days_in_month(
        year: int, month: int, calendar_system: CalendarSystem
    ) -> int:
        """Get number of days in a month - critical for appointment scheduling."""
        if calendar_system == CalendarSystem.GREGORIAN:
            return calendar.monthrange(year, month)[1]

        elif calendar_system == CalendarSystem.PERSIAN:
            if month <= 6:
                return 31
            elif month <= 11:
                return 30
            else:  # Month 12
                return 30 if CalendarUtils.is_leap_year(year, calendar_system) else 29

        elif calendar_system == CalendarSystem.HIJRI:
            # Hijri months alternate between 29 and 30 days with adjustments
            if month in [1, 3, 5, 7, 9, 11]:
                return 30
            elif month == 12:  # Dhu al-Hijjah
                return 30 if CalendarUtils.is_leap_year(year, calendar_system) else 29
            else:
                return 29

        elif calendar_system == CalendarSystem.ETHIOPIAN:
            if month <= 12:
                return 30
            else:  # 13th month (Pagume)
                return 6 if CalendarUtils.is_leap_year(year, calendar_system) else 5

        elif calendar_system == CalendarSystem.NEPALI:
            # Use lookup table for Nepali calendar
            if year in NepaliCalendarConverter.BS_CALENDAR_DATA:
                return NepaliCalendarConverter.BS_CALENDAR_DATA[year][month - 1]
            return 30  # Default

        elif calendar_system == CalendarSystem.BUDDHIST:
            # Buddhist calendar follows Gregorian month lengths
            return calendar.monthrange(year - 543, month)[1]

        elif calendar_system == CalendarSystem.COPTIC:
            if month <= 12:
                return 30
            else:  # 13th month
                return 6 if CalendarUtils.is_leap_year(year, calendar_system) else 5

        elif calendar_system == CalendarSystem.HEBREW:
            # Hebrew months have variable lengths
            # This is simplified - use proper library in production
            if month in [1, 3, 5, 7, 10]:  # Tishrei, Kislev, Shevat, Nisan, Tammuz
                return 30
            elif month == 2:  # Cheshvan
                return 29  # Can be 29 or 30
            elif month == 9:  # Adar (in non-leap years)
                return 29
            else:
                return 29

        # All calendar systems are covered above
        raise ValueError(f"Unknown calendar system: {calendar_system}")
