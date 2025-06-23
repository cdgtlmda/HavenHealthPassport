"""Calendar System Support for Multi-Cultural Healthcare.

This module provides support for various calendar systems used by different
cultures in healthcare contexts.
"""

import calendar
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from dateutil import parser
from hijri_converter import Gregorian, Hijri

from src.utils.logging import get_logger

logger = get_logger(__name__)


class CalendarSystem(str, Enum):
    """Supported calendar systems."""

    GREGORIAN = "gregorian"  # International standard
    HIJRI = "hijri"  # Islamic calendar
    PERSIAN = "persian"  # Solar Hijri (Iran, Afghanistan)
    ETHIOPIAN = "ethiopian"  # Ethiopian calendar
    HEBREW = "hebrew"  # Jewish calendar
    BUDDHIST = "buddhist"  # Buddhist calendar (Thailand)
    JAPANESE = "japanese"  # Japanese imperial calendar
    CHINESE = "chinese"  # Chinese lunar calendar


@dataclass
class CalendarDate:
    """Date in a specific calendar system."""

    year: int
    month: int
    day: int
    calendar_system: CalendarSystem
    gregorian_date: date
    era_name: Optional[str] = None  # For Japanese calendar
    month_name: Optional[str] = None
    day_of_week: Optional[str] = None
    is_holiday: bool = False
    holiday_name: Optional[str] = None


@dataclass
class CalendarPreferences:
    """User's calendar preferences."""

    primary_calendar: CalendarSystem
    secondary_calendar: Optional[CalendarSystem] = None
    show_dual_dates: bool = False
    first_day_of_week: int = 1  # 0=Sunday, 1=Monday
    weekend_days: Optional[List[int]] = None  # [5, 6] for Sat-Sun
    date_format: str = "DD/MM/YYYY"
    time_format: str = "24h"


class CalendarManager:
    """Manages multiple calendar systems for healthcare applications."""

    # Month names by calendar system and language
    MONTH_NAMES = {
        CalendarSystem.HIJRI: {
            "ar": [
                "محرم",
                "صفر",
                "ربيع الأول",
                "ربيع الثاني",
                "جمادى الأولى",
                "جمادى الآخرة",
                "رجب",
                "شعبان",
                "رمضان",
                "شوال",
                "ذو القعدة",
                "ذو الحجة",
            ],
            "en": [
                "Muharram",
                "Safar",
                "Rabi' al-awwal",
                "Rabi' al-thani",
                "Jumada al-awwal",
                "Jumada al-thani",
                "Rajab",
                "Sha'ban",
                "Ramadan",
                "Shawwal",
                "Dhu al-Qi'dah",
                "Dhu al-Hijjah",
            ],
        },
        CalendarSystem.PERSIAN: {
            "fa": [
                "فروردین",
                "اردیبهشت",
                "خرداد",
                "تیر",
                "مرداد",
                "شهریور",
                "مهر",
                "آبان",
                "آذر",
                "دی",
                "بهمن",
                "اسفند",
            ],
            "en": [
                "Farvardin",
                "Ordibehesht",
                "Khordad",
                "Tir",
                "Mordad",
                "Shahrivar",
                "Mehr",
                "Aban",
                "Azar",
                "Dey",
                "Bahman",
                "Esfand",
            ],
        },
        CalendarSystem.ETHIOPIAN: {
            "am": [
                "መስከረም",
                "ጥቅምት",
                "ኅዳር",
                "ታኅሣሥ",
                "ጥር",
                "የካቲት",
                "መጋቢት",
                "ሚያዝያ",
                "ግንቦት",
                "ሰኔ",
                "ሐምሌ",
                "ነሐሴ",
                "ጳጉሜን",
            ],
            "en": [
                "Meskerem",
                "Tikmt",
                "Hidar",
                "Tahsas",
                "Tir",
                "Yakatit",
                "Maggabit",
                "Miazya",
                "Genbot",
                "Sene",
                "Hamle",
                "Nehasse",
                "Pagume",
            ],
        },
    }

    # Weekend days by region/culture
    WEEKEND_PATTERNS = {
        "standard": [6, 0],  # Saturday-Sunday (most countries)
        "middle_east": [5, 6],  # Friday-Saturday (many Muslim countries)
        "iran": [5],  # Friday only
        "israel": [5, 6],  # Friday-Saturday
        "nepal": [6],  # Saturday only
    }

    # Date formats by locale
    DATE_FORMATS = {
        "US": "MM/DD/YYYY",
        "EU": "DD/MM/YYYY",
        "ISO": "YYYY-MM-DD",
        "ar": "DD/MM/YYYY",
        "fa": "YYYY/MM/DD",
        "zh": "YYYY年MM月DD日",
        "ja": "YYYY年MM月DD日",
        "medical": "YYYY-MM-DD",  # Standard medical format
    }

    def __init__(self) -> None:
        """Initialize calendar manager."""
        self.user_preferences: Dict[str, CalendarPreferences] = {}
        self._initialize_converters()

    def _initialize_converters(self) -> None:
        """Initialize calendar conversion systems."""
        # Converters would be initialized here
        pass

    def convert_date(
        self,
        date_value: date,
        from_calendar: CalendarSystem,
        to_calendar: CalendarSystem,
        language: str = "en",
    ) -> CalendarDate:
        """Convert date between calendar systems."""
        # Ensure we have Gregorian as intermediate
        if from_calendar != CalendarSystem.GREGORIAN:
            gregorian_date = self._to_gregorian(
                (date_value.year, date_value.month, date_value.day), from_calendar
            )
        else:
            gregorian_date = date_value

        # Convert to target calendar
        if to_calendar == CalendarSystem.GREGORIAN:
            target_date = gregorian_date
            year, month, day = target_date.year, target_date.month, target_date.day
        else:
            year, month, day = self._from_gregorian(gregorian_date, to_calendar)

        # Get month name
        month_name = self._get_month_name(to_calendar, month, language)

        # Get day of week
        day_of_week = self._get_day_of_week(gregorian_date, language)

        return CalendarDate(
            year=year,
            month=month,
            day=day,
            calendar_system=to_calendar,
            gregorian_date=gregorian_date,
            month_name=month_name,
            day_of_week=day_of_week,
        )

    def _to_gregorian(
        self, date_value: Tuple[int, int, int], from_calendar: CalendarSystem
    ) -> date:
        """Convert any calendar date to Gregorian."""
        year, month, day = date_value

        if from_calendar == CalendarSystem.HIJRI:
            # Convert Hijri to Gregorian
            hijri = Hijri(year, month, day)
            greg = hijri.to_gregorian()
            return date(greg.year, greg.month, greg.day)

        elif from_calendar == CalendarSystem.PERSIAN:
            # Persian calendar conversion (simplified)
            # In production, would use proper Persian calendar library
            # This is approximate
            return self._persian_to_gregorian(year, month, day)

        elif from_calendar == CalendarSystem.ETHIOPIAN:
            # Ethiopian calendar conversion
            return self._ethiopian_to_gregorian(year, month, day)

        # Add other calendar conversions as needed

        return date(year, month, day)  # Default

    def _from_gregorian(
        self, gregorian_date: date, to_calendar: CalendarSystem
    ) -> Tuple[int, int, int]:
        """Convert Gregorian date to other calendar."""
        if to_calendar == CalendarSystem.HIJRI:
            # Convert to Hijri
            greg = Gregorian(
                gregorian_date.year, gregorian_date.month, gregorian_date.day
            )
            hijri = greg.to_hijri()
            return hijri.year, hijri.month, hijri.day

        elif to_calendar == CalendarSystem.PERSIAN:
            # Convert to Persian
            return self._gregorian_to_persian(gregorian_date)

        elif to_calendar == CalendarSystem.ETHIOPIAN:
            # Convert to Ethiopian
            return self._gregorian_to_ethiopian(gregorian_date)

        elif to_calendar == CalendarSystem.BUDDHIST:
            # Buddhist calendar (Thai) - simply add 543 years
            return gregorian_date.year + 543, gregorian_date.month, gregorian_date.day

        # Default
        return gregorian_date.year, gregorian_date.month, gregorian_date.day

    def _persian_to_gregorian(self, year: int, month: int, day: int) -> date:
        """Convert Persian date to Gregorian (simplified)."""
        # This is a simplified conversion
        # In production, use a proper Persian calendar library

        # Persian year 1 = 622 CE (approximately)
        # Persian calendar is solar
        gregorian_year = year + 621

        # Approximate day of year
        days_before_month = [0, 31, 62, 93, 124, 155, 186, 216, 246, 276, 306, 336]

        if month <= 12:
            day_of_year = days_before_month[month - 1] + day
        else:
            day_of_year = 365  # Handle 13th month

        # Approximate conversion
        base_date = date(gregorian_year, 3, 21)  # Persian New Year
        return base_date + timedelta(days=day_of_year - 1)

    def _gregorian_to_persian(self, gregorian_date: date) -> Tuple[int, int, int]:
        """Convert Gregorian to Persian date (simplified)."""
        # Simplified conversion
        year = gregorian_date.year - 621

        # Calculate day of Persian year
        persian_new_year = date(gregorian_date.year, 3, 21)
        if gregorian_date < persian_new_year:
            year -= 1
            persian_new_year = date(gregorian_date.year - 1, 3, 21)

        days_since_new_year = (gregorian_date - persian_new_year).days + 1

        # Determine month and day
        if days_since_new_year <= 186:  # First 6 months have 31 days
            month = (days_since_new_year - 1) // 31 + 1
            day = (days_since_new_year - 1) % 31 + 1
        else:  # Next 5 months have 30 days
            days_in_second_half = days_since_new_year - 186
            month = 6 + (days_in_second_half - 1) // 30 + 1
            day = (days_in_second_half - 1) % 30 + 1

        return year, month, day

    def _ethiopian_to_gregorian(self, year: int, month: int, day: int) -> date:
        """Convert Ethiopian date to Gregorian."""
        # Ethiopian calendar is 7-8 years behind Gregorian
        # New Year is September 11 (or 12 in leap years)

        gregorian_year = year + 7  # Approximate

        # Ethiopian months: 12 months of 30 days + 1 month of 5-6 days
        day_of_year = (month - 1) * 30 + day

        # Ethiopian New Year is around September 11
        base_date = date(gregorian_year, 9, 11)

        return base_date + timedelta(days=day_of_year - 1)

    def _gregorian_to_ethiopian(self, gregorian_date: date) -> Tuple[int, int, int]:
        """Convert Gregorian to Ethiopian date."""
        # Approximate conversion
        year = gregorian_date.year - 7

        # Ethiopian New Year
        ethiopian_new_year = date(gregorian_date.year, 9, 11)
        if gregorian_date < ethiopian_new_year:
            year -= 1
            ethiopian_new_year = date(gregorian_date.year - 1, 9, 11)

        days_since_new_year = (gregorian_date - ethiopian_new_year).days + 1

        # Calculate month and day
        month = (days_since_new_year - 1) // 30 + 1
        day = (days_since_new_year - 1) % 30 + 1

        # Handle 13th month
        if month > 12:
            month = 13
            day = days_since_new_year - 360

        return year, month, day

    def _get_month_name(
        self, calendar_system: CalendarSystem, month: int, language: str
    ) -> str:
        """Get localized month name."""
        month_names = self.MONTH_NAMES.get(calendar_system, {}).get(language, [])

        if month_names and 1 <= month <= len(month_names):
            return month_names[month - 1]

        # Default to Gregorian month names
        if calendar_system == CalendarSystem.GREGORIAN:
            return calendar.month_name[month]

        return f"Month {month}"

    def _get_day_of_week(self, date_value: date, language: str) -> str:
        """Get localized day of week name."""
        day_names = {
            "en": [
                "Monday",
                "Tuesday",
                "Wednesday",
                "Thursday",
                "Friday",
                "Saturday",
                "Sunday",
            ],
            "ar": [
                "الإثنين",
                "الثلاثاء",
                "الأربعاء",
                "الخميس",
                "الجمعة",
                "السبت",
                "الأحد",
            ],
            "fa": ["دوشنبه", "سه‌شنبه", "چهارشنبه", "پنج‌شنبه", "جمعه", "شنبه", "یکشنبه"],
            "es": [
                "Lunes",
                "Martes",
                "Miércoles",
                "Jueves",
                "Viernes",
                "Sábado",
                "Domingo",
            ],
        }

        weekday = date_value.weekday()  # 0 = Monday
        return day_names.get(language, day_names["en"])[weekday]

    def format_date(
        self,
        calendar_date: CalendarDate,
        format_pattern: Optional[str] = None,
        language: str = "en",
        include_era: bool = False,
    ) -> str:
        """Format date according to locale and preferences."""
        if not format_pattern:
            format_pattern = self.DATE_FORMATS.get(language, "DD/MM/YYYY")

        # Replace format tokens
        formatted = format_pattern
        formatted = formatted.replace("YYYY", str(calendar_date.year).zfill(4))
        formatted = formatted.replace("YY", str(calendar_date.year)[-2:])
        formatted = formatted.replace("MM", str(calendar_date.month).zfill(2))
        formatted = formatted.replace("M", str(calendar_date.month))
        formatted = formatted.replace("DD", str(calendar_date.day).zfill(2))
        formatted = formatted.replace("D", str(calendar_date.day))

        # Add month name if requested
        if "MMM" in formatted:
            formatted = formatted.replace("MMM", calendar_date.month_name or "")

        # Add era for Japanese calendar
        if include_era and calendar_date.era_name:
            formatted = f"{calendar_date.era_name} {formatted}"

        return formatted

    def get_date_range_for_medical_history(
        self,
        start_gregorian: date,
        end_gregorian: date,
        calendar_system: CalendarSystem,
        language: str = "en",
    ) -> Dict[str, Any]:
        """Get date range formatted for medical history display."""
        start_converted = self.convert_date(
            start_gregorian, CalendarSystem.GREGORIAN, calendar_system, language
        )

        end_converted = self.convert_date(
            end_gregorian, CalendarSystem.GREGORIAN, calendar_system, language
        )

        # Calculate duration
        duration_days = (end_gregorian - start_gregorian).days

        return {
            "start": {
                "formatted": self.format_date(start_converted, language=language),
                "calendar_date": start_converted,
            },
            "end": {
                "formatted": self.format_date(end_converted, language=language),
                "calendar_date": end_converted,
            },
            "duration": {
                "days": duration_days,
                "weeks": duration_days // 7,
                "months": duration_days // 30,  # Approximate
                "formatted": self._format_duration(duration_days, language),
            },
        }

    def _format_duration(self, days: int, language: str) -> str:
        """Format duration in appropriate units."""
        if days < 7:
            return f"{days} days"
        elif days < 30:
            weeks = days // 7
            return f"{weeks} week{'s' if weeks > 1 else ''}"
        elif days < 365:
            months = days // 30
            return f"{months} month{'s' if months > 1 else ''}"
        else:
            years = days // 365
            return f"{years} year{'s' if years > 1 else ''}"

    def get_age_in_calendar_system(
        self,
        birth_date: date,
        calendar_system: CalendarSystem,
        as_of_date: Optional[date] = None,
    ) -> Dict[str, Any]:
        """Calculate age in specific calendar system."""
        if not as_of_date:
            as_of_date = date.today()

        # Convert dates to target calendar
        birth_converted = self.convert_date(
            birth_date, CalendarSystem.GREGORIAN, calendar_system
        )

        current_converted = self.convert_date(
            as_of_date, CalendarSystem.GREGORIAN, calendar_system
        )

        # Calculate age
        age_years = current_converted.year - birth_converted.year

        # Adjust if birthday hasn't occurred this year
        if current_converted.month < birth_converted.month or (
            current_converted.month == birth_converted.month
            and current_converted.day < birth_converted.day
        ):
            age_years -= 1

        # Calculate months
        if current_converted.month >= birth_converted.month:
            age_months = current_converted.month - birth_converted.month
        else:
            age_months = 12 + current_converted.month - birth_converted.month

        return {
            "years": age_years,
            "months": age_months,
            "total_days": (as_of_date - birth_date).days,
            "formatted": f"{age_years} years, {age_months} months",
        }

    def get_appointment_dates(
        self,
        appointment_date: datetime,
        user_preferences: CalendarPreferences,
        show_both_calendars: bool = True,
    ) -> Dict[str, Any]:
        """Format appointment date according to user preferences."""
        result: Dict[str, Any] = {}

        # Primary calendar
        primary_cal_date = self.convert_date(
            appointment_date.date(),
            CalendarSystem.GREGORIAN,
            user_preferences.primary_calendar,
        )

        result["primary"] = {
            "date": self.format_date(primary_cal_date),
            "time": self._format_time(appointment_date, user_preferences.time_format),
            "day_of_week": primary_cal_date.day_of_week,
            "calendar": user_preferences.primary_calendar.value,
        }

        # Secondary calendar if requested
        if show_both_calendars and user_preferences.secondary_calendar:
            secondary_cal_date = self.convert_date(
                appointment_date.date(),
                CalendarSystem.GREGORIAN,
                user_preferences.secondary_calendar,
            )

            result["secondary"] = {
                "date": self.format_date(secondary_cal_date),
                "calendar": user_preferences.secondary_calendar.value,
            }

        # Check if it's a weekend
        weekday = appointment_date.weekday()
        is_weekend = weekday in (user_preferences.weekend_days or [5, 6])
        result["is_weekend"] = is_weekend

        return result

    def _format_time(self, dt: datetime, time_format: str) -> str:
        """Format time according to user preference."""
        if time_format == "24h":
            return dt.strftime("%H:%M")
        else:  # 12h
            return dt.strftime("%I:%M %p")

    def validate_date_input(
        self,
        date_string: str,
        calendar_system: CalendarSystem,
        format_hint: Optional[str] = None,
    ) -> Tuple[bool, Optional[CalendarDate], Optional[str]]:
        """Validate and parse date input in specific calendar system."""
        try:
            # Try to parse the date
            parsed_date = parser.parse(date_string, dayfirst=True)

            # Convert to calendar system
            cal_date = self.convert_date(
                parsed_date.date(), CalendarSystem.GREGORIAN, calendar_system
            )

            return True, cal_date, None

        except Exception as e:
            error_message = f"Invalid date format: {str(e)}"
            return False, None, error_message

    def get_calendar_widget_data(
        self,
        year: int,
        month: int,
        calendar_system: CalendarSystem,
        language: str = "en",
    ) -> Dict[str, Any]:
        """Get data for rendering a calendar widget."""
        # Get month information
        if calendar_system == CalendarSystem.GREGORIAN:
            first_day = date(year, month, 1)
            if month == 12:
                last_day = date(year + 1, 1, 1) - timedelta(days=1)
            else:
                last_day = date(year, month + 1, 1) - timedelta(days=1)
        else:
            # Convert from other calendar
            first_day_tuple = (year, month, 1)
            first_day = self._to_gregorian(first_day_tuple, calendar_system)

            # Get last day of month (varies by calendar)
            days_in_month = self._get_days_in_month(year, month, calendar_system)
            last_day_tuple = (year, month, days_in_month)
            last_day = self._to_gregorian(last_day_tuple, calendar_system)

        # Build calendar grid
        first_weekday = first_day.weekday()
        days: List[Any] = []

        # Add empty cells for days before month starts
        for _ in range(first_weekday):
            days.append(None)

        # Add days of month
        current = first_day
        while current <= last_day:
            cal_date = self.convert_date(
                current, CalendarSystem.GREGORIAN, calendar_system, language
            )
            days.append(
                {
                    "day": cal_date.day,
                    "date": current,
                    "is_today": current == date.today(),
                    "is_holiday": cal_date.is_holiday,
                    "holiday_name": cal_date.holiday_name,
                }
            )
            current += timedelta(days=1)

        return {
            "year": year,
            "month": month,
            "month_name": self._get_month_name(calendar_system, month, language),
            "days": days,
            "weeks": [days[i : i + 7] for i in range(0, len(days), 7)],
        }

    def _get_days_in_month(
        self, year: int, month: int, calendar_system: CalendarSystem
    ) -> int:
        """Get number of days in a month for a calendar system."""
        if calendar_system == CalendarSystem.GREGORIAN:
            return calendar.monthrange(year, month)[1]
        elif calendar_system == CalendarSystem.HIJRI:
            # Hijri months alternate between 29 and 30 days (approximately)
            return 29 if month % 2 == 0 else 30
        elif calendar_system == CalendarSystem.PERSIAN:
            # First 6 months: 31 days, next 5: 30 days, last: 29/30
            if month <= 6:
                return 31
            elif month <= 11:
                return 30
            else:
                # Check for leap year
                return 30 if self._is_persian_leap_year(year) else 29
        elif calendar_system == CalendarSystem.ETHIOPIAN:
            # 12 months of 30 days, 13th month has 5/6 days
            if month <= 12:
                return 30
            else:
                return 6 if self._is_ethiopian_leap_year(year) else 5

        return 30  # Default

    def _is_persian_leap_year(self, year: int) -> bool:
        """Check if Persian year is leap year."""
        # 33-year cycle with specific leap years
        # Simplified check
        return year % 33 in [1, 5, 9, 13, 17, 22, 26, 30]

    def _is_ethiopian_leap_year(self, year: int) -> bool:
        """Check if Ethiopian year is leap year."""
        # Every 4 years, similar to Gregorian
        return year % 4 == 3


# Global calendar manager instance
calendar_manager = CalendarManager()
