"""
Date Format Localization Module.

Handles conversion between different date formats used across regions,
with special support for medical contexts and cultural variations.
"""

import re
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Dict, List, Optional, Pattern, Tuple, Union

from .core import ConversionContext


class DateFormat(Enum):
    """Standard date format patterns."""

    # US formats
    US_SLASH = "MM/DD/YYYY"
    US_DASH = "MM-DD-YYYY"
    US_SHORT = "MM/DD/YY"

    # European formats
    EU_SLASH = "DD/MM/YYYY"
    EU_DASH = "DD-MM-YYYY"
    EU_DOT = "DD.MM.YYYY"
    EU_SHORT = "DD/MM/YY"

    # ISO formats
    ISO_FULL = "YYYY-MM-DD"
    ISO_BASIC = "YYYYMMDD"
    ISO_TIME = "YYYY-MM-DDTHH:mm:ss"
    ISO_TIME_Z = "YYYY-MM-DDTHH:mm:ssZ"

    # Asian formats
    ASIA_DOT = "YYYY.MM.DD"
    ASIA_SLASH = "YYYY/MM/DD"
    ASIA_HANZI = "YYYY年MM月DD日"

    # Medical/Clinical formats
    MEDICAL_ABBREV = "DD-MMM-YYYY"  # e.g., 15-JAN-2024
    MEDICAL_FULL = "DD MMMM YYYY"  # e.g., 15 January 2024

    # Human-readable formats
    LONG_US = "MMMM DD, YYYY"  # e.g., January 15, 2024
    LONG_EU = "DD MMMM YYYY"  # e.g., 15 January 2024
    SHORT_MONTH = "MMM DD, YYYY"  # e.g., Jan 15, 2024


class TimeFormat(Enum):
    """Standard time format patterns."""

    HOUR_24 = "HH:mm"
    HOUR_24_SEC = "HH:mm:ss"
    HOUR_12 = "hh:mm AM/PM"
    HOUR_12_SEC = "hh:mm:ss AM/PM"
    MILITARY = "HHmm"


@dataclass
class DateTimeFormat:
    """Complete datetime formatting specification."""

    date_format: DateFormat
    time_format: TimeFormat
    separator: str = " "
    include_timezone: bool = False
    timezone_format: str = "Z"  # Z, +HH:MM, PST, etc.


@dataclass
class LocalePreferences:
    """Date/time preferences for a specific locale."""

    primary_date_format: DateFormat
    alternative_date_formats: List[DateFormat]
    time_format: TimeFormat
    week_starts_on: str  # "Monday" or "Sunday"
    month_names: Dict[int, str]
    month_abbrev: Dict[int, str]
    weekday_names: Dict[int, str]
    weekday_abbrev: Dict[int, str]
    am_pm_indicators: Tuple[str, str] = ("AM", "PM")
    decimal_separator: str = "."
    ordinal_indicators: Dict[int, str] = field(default_factory=dict)


# Regional date/time preferences
REGIONAL_PREFERENCES: Dict[str, LocalePreferences] = {
    "US": LocalePreferences(
        primary_date_format=DateFormat.US_SLASH,
        alternative_date_formats=[
            DateFormat.US_DASH,
            DateFormat.US_SHORT,
            DateFormat.LONG_US,
            DateFormat.SHORT_MONTH,
        ],
        time_format=TimeFormat.HOUR_12,
        week_starts_on="Sunday",
        month_names={
            1: "January",
            2: "February",
            3: "March",
            4: "April",
            5: "May",
            6: "June",
            7: "July",
            8: "August",
            9: "September",
            10: "October",
            11: "November",
            12: "December",
        },
        month_abbrev={
            1: "Jan",
            2: "Feb",
            3: "Mar",
            4: "Apr",
            5: "May",
            6: "Jun",
            7: "Jul",
            8: "Aug",
            9: "Sep",
            10: "Oct",
            11: "Nov",
            12: "Dec",
        },
        weekday_names={
            0: "Monday",
            1: "Tuesday",
            2: "Wednesday",
            3: "Thursday",
            4: "Friday",
            5: "Saturday",
            6: "Sunday",
        },
        weekday_abbrev={
            0: "Mon",
            1: "Tue",
            2: "Wed",
            3: "Thu",
            4: "Fri",
            5: "Sat",
            6: "Sun",
        },
        ordinal_indicators={
            1: "st",
            2: "nd",
            3: "rd",
            21: "st",
            22: "nd",
            23: "rd",
            31: "st",
        },
    ),
    "GB": LocalePreferences(
        primary_date_format=DateFormat.EU_SLASH,
        alternative_date_formats=[
            DateFormat.EU_DASH,
            DateFormat.LONG_EU,
            DateFormat.MEDICAL_ABBREV,
        ],
        time_format=TimeFormat.HOUR_24,
        week_starts_on="Monday",
        month_names={
            1: "January",
            2: "February",
            3: "March",
            4: "April",
            5: "May",
            6: "June",
            7: "July",
            8: "August",
            9: "September",
            10: "October",
            11: "November",
            12: "December",
        },
        month_abbrev={
            1: "Jan",
            2: "Feb",
            3: "Mar",
            4: "Apr",
            5: "May",
            6: "Jun",
            7: "Jul",
            8: "Aug",
            9: "Sep",
            10: "Oct",
            11: "Nov",
            12: "Dec",
        },
        weekday_names={
            0: "Monday",
            1: "Tuesday",
            2: "Wednesday",
            3: "Thursday",
            4: "Friday",
            5: "Saturday",
            6: "Sunday",
        },
        weekday_abbrev={
            0: "Mon",
            1: "Tue",
            2: "Wed",
            3: "Thu",
            4: "Fri",
            5: "Sat",
            6: "Sun",
        },
        ordinal_indicators={
            1: "st",
            2: "nd",
            3: "rd",
            21: "st",
            22: "nd",
            23: "rd",
            31: "st",
        },
    ),
    "EU": LocalePreferences(
        primary_date_format=DateFormat.EU_DOT,
        alternative_date_formats=[
            DateFormat.EU_SLASH,
            DateFormat.EU_DASH,
            DateFormat.ISO_FULL,
        ],
        time_format=TimeFormat.HOUR_24,
        week_starts_on="Monday",
        month_names={
            1: "January",
            2: "February",
            3: "March",
            4: "April",
            5: "May",
            6: "June",
            7: "July",
            8: "August",
            9: "September",
            10: "October",
            11: "November",
            12: "December",
        },
        month_abbrev={
            1: "Jan",
            2: "Feb",
            3: "Mar",
            4: "Apr",
            5: "May",
            6: "Jun",
            7: "Jul",
            8: "Aug",
            9: "Sep",
            10: "Oct",
            11: "Nov",
            12: "Dec",
        },
        weekday_names={
            0: "Monday",
            1: "Tuesday",
            2: "Wednesday",
            3: "Thursday",
            4: "Friday",
            5: "Saturday",
            6: "Sunday",
        },
        weekday_abbrev={
            0: "Mon",
            1: "Tue",
            2: "Wed",
            3: "Thu",
            4: "Fri",
            5: "Sat",
            6: "Sun",
        },
    ),
    "ISO": LocalePreferences(
        primary_date_format=DateFormat.ISO_FULL,
        alternative_date_formats=[
            DateFormat.ISO_BASIC,
            DateFormat.ISO_TIME,
            DateFormat.ISO_TIME_Z,
        ],
        time_format=TimeFormat.HOUR_24_SEC,
        week_starts_on="Monday",
        month_names={
            1: "January",
            2: "February",
            3: "March",
            4: "April",
            5: "May",
            6: "June",
            7: "July",
            8: "August",
            9: "September",
            10: "October",
            11: "November",
            12: "December",
        },
        month_abbrev={
            1: "Jan",
            2: "Feb",
            3: "Mar",
            4: "Apr",
            5: "May",
            6: "Jun",
            7: "Jul",
            8: "Aug",
            9: "Sep",
            10: "Oct",
            11: "Nov",
            12: "Dec",
        },
        weekday_names={
            0: "Monday",
            1: "Tuesday",
            2: "Wednesday",
            3: "Thursday",
            4: "Friday",
            5: "Saturday",
            6: "Sunday",
        },
        weekday_abbrev={
            0: "Mon",
            1: "Tue",
            2: "Wed",
            3: "Thu",
            4: "Fri",
            5: "Sat",
            6: "Sun",
        },
    ),
    "JP": LocalePreferences(
        primary_date_format=DateFormat.ASIA_SLASH,
        alternative_date_formats=[
            DateFormat.ASIA_DOT,
            DateFormat.ASIA_HANZI,
            DateFormat.ISO_FULL,
        ],
        time_format=TimeFormat.HOUR_24,
        week_starts_on="Sunday",
        month_names={
            1: "1月",
            2: "2月",
            3: "3月",
            4: "4月",
            5: "5月",
            6: "6月",
            7: "7月",
            8: "8月",
            9: "9月",
            10: "10月",
            11: "11月",
            12: "12月",
        },
        month_abbrev={
            1: "1月",
            2: "2月",
            3: "3月",
            4: "4月",
            5: "5月",
            6: "6月",
            7: "7月",
            8: "8月",
            9: "9月",
            10: "10月",
            11: "11月",
            12: "12月",
        },
        weekday_names={
            0: "月曜日",
            1: "火曜日",
            2: "水曜日",
            3: "木曜日",
            4: "金曜日",
            5: "土曜日",
            6: "日曜日",
        },
        weekday_abbrev={0: "月", 1: "火", 2: "水", 3: "木", 4: "金", 5: "土", 6: "日"},
    ),
}


# Date pattern regexes for parsing
DATE_PATTERNS: Dict[DateFormat, Pattern] = {
    DateFormat.US_SLASH: re.compile(r"\b(\d{1,2})/(\d{1,2})/(\d{4}|\d{2})\b"),
    DateFormat.US_DASH: re.compile(r"\b(\d{1,2})-(\d{1,2})-(\d{4}|\d{2})\b"),
    DateFormat.EU_SLASH: re.compile(r"\b(\d{1,2})/(\d{1,2})/(\d{4}|\d{2})\b"),
    DateFormat.EU_DASH: re.compile(r"\b(\d{1,2})-(\d{1,2})-(\d{4}|\d{2})\b"),
    DateFormat.EU_DOT: re.compile(r"\b(\d{1,2})\.(\d{1,2})\.(\d{4}|\d{2})\b"),
    DateFormat.ISO_FULL: re.compile(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b"),
    DateFormat.ISO_BASIC: re.compile(r"\b(\d{4})(\d{2})(\d{2})\b"),
    DateFormat.ASIA_DOT: re.compile(r"\b(\d{4})\.(\d{1,2})\.(\d{1,2})\b"),
    DateFormat.ASIA_SLASH: re.compile(r"\b(\d{4})/(\d{1,2})/(\d{1,2})\b"),
    DateFormat.ASIA_HANZI: re.compile(r"\b(\d{4})年(\d{1,2})月(\d{1,2})日\b"),
    DateFormat.MEDICAL_ABBREV: re.compile(
        r"\b(\d{1,2})-(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)-(\d{4})\b", re.I
    ),
}


class DateParser:
    """Parses dates from various formats."""

    def __init__(self) -> None:
        """Initialize the date parser with month name mappings."""
        self.month_names_to_num = {
            "january": 1,
            "jan": 1,
            "february": 2,
            "feb": 2,
            "march": 3,
            "mar": 3,
            "april": 4,
            "apr": 4,
            "may": 5,
            "june": 6,
            "jun": 6,
            "july": 7,
            "jul": 7,
            "august": 8,
            "aug": 8,
            "september": 9,
            "sep": 9,
            "sept": 9,
            "october": 10,
            "oct": 10,
            "november": 11,
            "nov": 11,
            "december": 12,
            "dec": 12,
        }

    def parse(
        self, date_str: str, format_hint: Optional[DateFormat] = None
    ) -> Optional[date]:
        """Parse a date string into a date object."""
        if format_hint:
            return self._parse_with_format(date_str, format_hint)

        # Try to auto-detect format
        return self._auto_parse(date_str)

    def _parse_with_format(
        self, date_str: str, date_format: DateFormat
    ) -> Optional[date]:
        """Parse using a specific format."""
        pattern = DATE_PATTERNS.get(date_format)
        if not pattern:
            return None

        match = pattern.match(date_str.strip())
        if not match:
            return None

        groups = match.groups()

        try:
            if date_format in [
                DateFormat.US_SLASH,
                DateFormat.US_DASH,
                DateFormat.US_SHORT,
            ]:
                month, day, year = int(groups[0]), int(groups[1]), int(groups[2])
                if year < 100:
                    year += 2000 if year < 50 else 1900
                return date(year, month, day)

            elif date_format in [
                DateFormat.EU_SLASH,
                DateFormat.EU_DASH,
                DateFormat.EU_DOT,
                DateFormat.EU_SHORT,
            ]:
                day, month, year = int(groups[0]), int(groups[1]), int(groups[2])
                if year < 100:
                    year += 2000 if year < 50 else 1900
                return date(year, month, day)

            elif date_format in [
                DateFormat.ISO_FULL,
                DateFormat.ISO_BASIC,
                DateFormat.ASIA_DOT,
                DateFormat.ASIA_SLASH,
                DateFormat.ASIA_HANZI,
            ]:
                year, month, day = int(groups[0]), int(groups[1]), int(groups[2])
                return date(year, month, day)

            elif date_format == DateFormat.MEDICAL_ABBREV:
                day = int(groups[0])
                month = self.month_names_to_num.get(groups[1].lower(), 0)
                year = int(groups[2])
                if month:
                    return date(year, month, day)

        except ValueError:
            return None

        return None

    def _auto_parse(self, date_str: str) -> Optional[date]:
        """Try to automatically detect and parse date format."""
        # Try each pattern
        for date_format, _ in DATE_PATTERNS.items():
            result = self._parse_with_format(date_str, date_format)
            if result:
                return result

        # Try datetime parsing
        try:
            dt = datetime.strptime(date_str, "%Y-%m-%d")
            return dt.date()
        except ValueError:
            pass

        return None


class DateFormatter:
    """Formats dates according to regional preferences."""

    def __init__(self, locale: str = "US") -> None:
        """Initialize the date formatter with a specific locale."""
        self.locale = locale
        self.preferences = REGIONAL_PREFERENCES.get(locale, REGIONAL_PREFERENCES["US"])

    def format(
        self,
        date_obj: Union[date, datetime],
        format_type: Optional[DateFormat] = None,
        include_weekday: bool = False,
    ) -> str:
        """Format a date according to locale preferences."""
        if format_type is None:
            format_type = self.preferences.primary_date_format

        # Handle datetime vs date
        if isinstance(date_obj, datetime):
            date_part = date_obj.date()
        else:
            date_part = date_obj

        # Get components
        year = date_part.year
        month = date_part.month
        day = date_part.day
        weekday = date_part.weekday()

        # Format based on type
        result = self._format_date_part(year, month, day, format_type)

        # Add weekday if requested
        if include_weekday:
            weekday_name = self.preferences.weekday_names[weekday]
            result = f"{weekday_name}, {result}"

        return result

    def _format_date_part(
        self, year: int, month: int, day: int, format_type: DateFormat
    ) -> str:
        """Format the date components according to the specified format."""
        if format_type == DateFormat.US_SLASH:
            return f"{month:02d}/{day:02d}/{year}"
        elif format_type == DateFormat.US_DASH:
            return f"{month:02d}-{day:02d}-{year}"
        elif format_type == DateFormat.US_SHORT:
            return f"{month:02d}/{day:02d}/{year % 100:02d}"
        elif format_type == DateFormat.EU_SLASH:
            return f"{day:02d}/{month:02d}/{year}"
        elif format_type == DateFormat.EU_DASH:
            return f"{day:02d}-{month:02d}-{year}"
        elif format_type == DateFormat.EU_DOT:
            return f"{day:02d}.{month:02d}.{year}"
        elif format_type == DateFormat.EU_SHORT:
            return f"{day:02d}/{month:02d}/{year % 100:02d}"
        elif format_type == DateFormat.ISO_FULL:
            return f"{year}-{month:02d}-{day:02d}"
        elif format_type == DateFormat.ISO_BASIC:
            return f"{year}{month:02d}{day:02d}"
        elif format_type == DateFormat.ASIA_DOT:
            return f"{year}.{month:02d}.{day:02d}"
        elif format_type == DateFormat.ASIA_SLASH:
            return f"{year}/{month:02d}/{day:02d}"
        elif format_type == DateFormat.ASIA_HANZI:
            return f"{year}年{month}月{day}日"
        elif format_type == DateFormat.MEDICAL_ABBREV:
            month_abbrev = self.preferences.month_abbrev[month].upper()
            return f"{day:02d}-{month_abbrev}-{year}"
        elif format_type == DateFormat.MEDICAL_FULL:
            month_name = self.preferences.month_names[month]
            return f"{day} {month_name} {year}"
        elif format_type == DateFormat.LONG_US:
            month_name = self.preferences.month_names[month]
            return f"{month_name} {day}, {year}"
        elif format_type == DateFormat.LONG_EU:
            month_name = self.preferences.month_names[month]
            return f"{day} {month_name} {year}"
        elif format_type == DateFormat.SHORT_MONTH:
            month_abbrev = self.preferences.month_abbrev[month]
            return f"{month_abbrev} {day}, {year}"
        else:
            # Default to ISO
            return f"{year}-{month:02d}-{day:02d}"

    def format_time(
        self, time_obj: Union[datetime, str], format_type: Optional[TimeFormat] = None
    ) -> str:
        """Format time according to locale preferences."""
        if format_type is None:
            format_type = self.preferences.time_format

        # Parse time if string
        if isinstance(time_obj, str):
            # Simple parse for HH:MM or HH:MM:SS
            parts = time_obj.split(":")
            hour = int(parts[0])
            minute = int(parts[1]) if len(parts) > 1 else 0
            second = int(parts[2]) if len(parts) > 2 else 0
        else:
            hour = time_obj.hour
            minute = time_obj.minute
            second = time_obj.second

        # Format based on type
        if format_type == TimeFormat.HOUR_24:
            return f"{hour:02d}:{minute:02d}"
        elif format_type == TimeFormat.HOUR_24_SEC:
            return f"{hour:02d}:{minute:02d}:{second:02d}"
        elif format_type == TimeFormat.HOUR_12:
            am_pm = self.preferences.am_pm_indicators[0 if hour < 12 else 1]
            hour_12 = hour % 12 or 12
            return f"{hour_12}:{minute:02d} {am_pm}"
        elif format_type == TimeFormat.HOUR_12_SEC:
            am_pm = self.preferences.am_pm_indicators[0 if hour < 12 else 1]
            hour_12 = hour % 12 or 12
            return f"{hour_12}:{minute:02d}:{second:02d} {am_pm}"
        else:  # TimeFormat.MILITARY
            return f"{hour:02d}{minute:02d}"


class DateLocalizer:
    """Main class for date localization in translations."""

    def __init__(self) -> None:
        """Initialize the date localizer with parsers and formatters."""
        self.parser = DateParser()
        self.formatters = {
            locale: DateFormatter(locale) for locale in REGIONAL_PREFERENCES
        }

    def localize(
        self, text: str, target_locale: str, context: Optional[ConversionContext] = None
    ) -> str:
        """Localize all dates in text to target locale format."""
        if target_locale not in self.formatters:
            target_locale = "US"

        formatter = self.formatters[target_locale]
        result = text

        # Find and replace all dates
        for date_format, pattern in DATE_PATTERNS.items():
            matches = list(pattern.finditer(result))

            # Process matches in reverse to maintain positions
            for match in reversed(matches):
                date_str = match.group(0)
                parsed_date = self.parser.parse(date_str, date_format)

                if parsed_date:
                    # Format according to target locale
                    if context and context.medical_context:
                        # Use medical format for medical contexts
                        formatted = formatter.format(
                            parsed_date, DateFormat.MEDICAL_ABBREV
                        )
                    else:
                        formatted = formatter.format(parsed_date)

                    # Replace in text
                    start, end = match.span()
                    result = result[:start] + formatted + result[end:]

        return result

    def convert_date(
        self,
        date_str: str,
        target_locale: str,
        format_hint: Optional[DateFormat] = None,
    ) -> str:
        """Convert a single date to target locale format."""
        parsed = self.parser.parse(date_str, format_hint)
        if not parsed:
            return date_str

        formatter = self.formatters.get(target_locale, self.formatters["US"])
        return formatter.format(parsed)

    def extract_dates(self, text: str) -> List[Tuple[str, date, Tuple[int, int]]]:
        """Extract all dates from text with their positions."""
        dates = []

        for date_format, pattern in DATE_PATTERNS.items():
            for match in pattern.finditer(text):
                date_str = match.group(0)
                parsed_date = self.parser.parse(date_str, date_format)

                if parsed_date:
                    dates.append((date_str, parsed_date, match.span()))

        # Sort by position
        dates.sort(key=lambda x: x[2][0])
        return dates


# Convenience functions
def localize_dates(text: str, target_locale: str) -> str:
    """Localize all dates in text to target locale format."""
    localizer = DateLocalizer()
    return localizer.localize(text, target_locale)


def format_date(
    date_obj: Union[date, datetime, str],
    locale: str = "US",
    format_type: Optional[DateFormat] = None,
) -> str:
    """Format a date according to locale preferences."""
    formatter = DateFormatter(locale)

    if isinstance(date_obj, str):
        parser = DateParser()
        parsed = parser.parse(date_obj)
        if not parsed:
            return date_obj
        date_obj = parsed

    return formatter.format(date_obj, format_type)


def parse_date(
    date_str: str, format_hint: Optional[DateFormat] = None
) -> Optional[date]:
    """Parse a date string into a date object."""
    parser = DateParser()
    return parser.parse(date_str, format_hint)
