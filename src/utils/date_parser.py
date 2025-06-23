"""
Multilingual Date Parser Module.

This module provides comprehensive date parsing capabilities for multiple languages
and date formats commonly used in medical documents worldwide.
"""

import logging
import re
from datetime import date, datetime
from enum import Enum
from typing import List, Optional, cast

from dateutil import parser as dateutil_parser

logger = logging.getLogger(__name__)


class DateFormat(Enum):
    """Common date formats across different regions."""

    US_MDY = "MM/DD/YYYY"
    EU_DMY = "DD/MM/YYYY"
    ISO_YMD = "YYYY-MM-DD"
    JAPANESE = "YYYY年MM月DD日"
    GERMAN = "DD.MM.YYYY"
    FRENCH = "DD/MM/YYYY"
    SPANISH = "DD/MM/YYYY"
    ARABIC = "DD/MM/YYYY"  # Often uses Western numerals


class MultilingualDateParser:
    """Parser for dates in multiple languages and formats."""

    def __init__(self) -> None:
        """Initialize multilingual date parser with month names."""
        # Month names in different languages
        self.month_names = {
            "en": {
                "january": 1,
                "february": 2,
                "march": 3,
                "april": 4,
                "may": 5,
                "june": 6,
                "july": 7,
                "august": 8,
                "september": 9,
                "october": 10,
                "november": 11,
                "december": 12,
                "jan": 1,
                "feb": 2,
                "mar": 3,
                "apr": 4,
                "jun": 6,
                "jul": 7,
                "aug": 8,
                "sep": 9,
                "sept": 9,
                "oct": 10,
                "nov": 11,
                "dec": 12,
            },
            "es": {
                "enero": 1,
                "febrero": 2,
                "marzo": 3,
                "abril": 4,
                "mayo": 5,
                "junio": 6,
                "julio": 7,
                "agosto": 8,
                "septiembre": 9,
                "octubre": 10,
                "noviembre": 11,
                "diciembre": 12,
                "ene": 1,
                "feb": 2,
                "mar": 3,
                "abr": 4,
                "may": 5,
                "jun": 6,
                "jul": 7,
                "ago": 8,
                "sep": 9,
                "oct": 10,
                "nov": 11,
                "dic": 12,
            },
            "fr": {
                "janvier": 1,
                "février": 2,
                "mars": 3,
                "avril": 4,
                "mai": 5,
                "juin": 6,
                "juillet": 7,
                "août": 8,
                "septembre": 9,
                "octobre": 10,
                "novembre": 11,
                "décembre": 12,
                "janv": 1,
                "févr": 2,
                # "mars": 3,  # Same as full name
                "avr": 4,
                # "mai": 5,  # Same as full name
                # "juin": 6,  # Same as full name
                "juil": 7,
                # "août": 8,  # Same as full name
                "sept": 9,
                "oct": 10,
                "nov": 11,
                "déc": 12,
            },
            "de": {
                "januar": 1,
                "februar": 2,
                "märz": 3,
                "april": 4,
                "mai": 5,
                "juni": 6,
                "juli": 7,
                "august": 8,
                "september": 9,
                "oktober": 10,
                "november": 11,
                "dezember": 12,
                "jan": 1,
                "feb": 2,
                "mär": 3,
                "apr": 4,
                # "mai": 5,  # Same as full name
                "jun": 6,
                "jul": 7,
                "aug": 8,
                "sep": 9,
                "okt": 10,
                "nov": 11,
                "dez": 12,
            },
            "pt": {
                "janeiro": 1,
                "fevereiro": 2,
                "março": 3,
                "abril": 4,
                "maio": 5,
                "junho": 6,
                "julho": 7,
                "agosto": 8,
                "setembro": 9,
                "outubro": 10,
                "novembro": 11,
                "dezembro": 12,
                "jan": 1,
                "fev": 2,
                "mar": 3,
                "abr": 4,
                "mai": 5,
                "jun": 6,
                "jul": 7,
                "ago": 8,
                "set": 9,
                "out": 10,
                "nov": 11,
                "dez": 12,
            },
            "ar": {
                "يناير": 1,
                "فبراير": 2,
                "مارس": 3,
                "أبريل": 4,
                "مايو": 5,
                "يونيو": 6,
                "يوليو": 7,
                "أغسطس": 8,
                "سبتمبر": 9,
                "أكتوبر": 10,
                "نوفمبر": 11,
                "ديسمبر": 12,
            },
        }

        # Common date patterns
        self.patterns = [
            # US format MM/DD/YYYY or MM-DD-YYYY
            (r"(\d{1,2})[/-](\d{1,2})[/-](\d{4})", "MDY"),
            # EU format DD/MM/YYYY or DD-MM-YYYY
            (r"(\d{1,2})[/-](\d{1,2})[/-](\d{4})", "DMY"),
            # ISO format YYYY-MM-DD
            (r"(\d{4})[/-](\d{1,2})[/-](\d{1,2})", "YMD"),
            # German format DD.MM.YYYY
            (r"(\d{1,2})\.(\d{1,2})\.(\d{4})", "DMY"),
            # Japanese format YYYY年MM月DD日
            (r"(\d{4})年(\d{1,2})月(\d{1,2})日", "YMD"),
            # Written format: January 1, 2024 or 1 January 2024
            (r"(\w+)\s+(\d{1,2}),?\s+(\d{4})", "MDY_TEXT"),
            (r"(\d{1,2})\s+(\w+)\s+(\d{4})", "DMY_TEXT"),
            # Short year format
            (r"(\d{1,2})[/-](\d{1,2})[/-](\d{2})", "MDY_SHORT"),
            (r"(\d{1,2})\.(\d{1,2})\.(\d{2})", "DMY_SHORT"),
        ]

    def parse(
        self,
        date_string: str,
        language: str = "auto",
        hint_format: Optional[DateFormat] = None,
    ) -> Optional[date]:
        """
        Parse a date string in the specified language.

        Args:
            date_string: The date string to parse
            language: Language code (en, es, fr, de, pt, ar)
            hint_format: Optional hint about expected format

        Returns:
            Parsed date object

        Raises:
            ValueError: If date cannot be parsed
        """
        if not date_string:
            raise ValueError("Empty date string")

        # Clean the input
        date_string = date_string.strip()

        # Try hint format first if provided
        if hint_format:
            try:
                return self._parse_with_format(date_string, hint_format)
            except (ValueError, TypeError) as e:
                logger.debug("Failed to parse with hint format: %s", e)

        # Try pattern matching
        parsed_date = self._parse_with_patterns(date_string, language)
        if parsed_date:
            return parsed_date

        # Try dateutil parser as fallback
        try:
            parsed_datetime = cast(
                datetime, dateutil_parser.parse(date_string, fuzzy=True)
            )
            return parsed_datetime.date()
        except (ValueError, TypeError, AttributeError) as e:
            logger.debug("dateutil parser failed: %s", e)

        # Last resort: try to extract numbers and guess
        numbers = re.findall(r"\d+", date_string)
        if len(numbers) >= 3:
            return self._guess_from_numbers(numbers, language)

        raise ValueError(f"Could not parse date: {date_string}")

    def _parse_with_format(self, date_string: str, date_format: DateFormat) -> date:
        """Parse using a specific format."""
        if date_format == DateFormat.US_MDY:
            return datetime.strptime(date_string, "%m/%d/%Y").date()
        elif date_format == DateFormat.EU_DMY:
            return datetime.strptime(date_string, "%d/%m/%Y").date()
        elif date_format == DateFormat.ISO_YMD:
            return datetime.strptime(date_string, "%Y-%m-%d").date()
        elif date_format == DateFormat.GERMAN:
            return datetime.strptime(date_string, "%d.%m.%Y").date()
        else:
            raise ValueError(f"Unsupported format: {date_format}")

    def _parse_with_patterns(self, date_string: str, language: str) -> Optional[date]:
        """Parse using regex patterns."""
        for pattern, format_type in self.patterns:
            match = re.search(pattern, date_string, re.IGNORECASE)
            if match:
                groups = match.groups()

                try:
                    if format_type == "MDY":
                        month, day, year = map(int, groups)
                        # Ambiguous - try to determine based on values
                        if month > 12:  # Must be DMY
                            day, month = month, day
                    elif format_type == "DMY":
                        day, month, year = map(int, groups)
                        # Ambiguous - try to determine based on values
                        if day > 12:  # Must be MDY
                            day, month = month, day
                    elif format_type == "YMD":
                        year, month, day = map(int, groups)
                    elif format_type == "MDY_TEXT":
                        month_str, day_str, year_str = groups
                        month = self._parse_month(str(month_str), language)
                        day = int(str(day_str))
                        year = int(str(year_str))
                    elif format_type == "DMY_TEXT":
                        day_str, month_str, year_str = groups
                        day = int(str(day_str))
                        month = self._parse_month(str(month_str), language)
                        year = int(str(year_str))
                    elif format_type in ["MDY_SHORT", "DMY_SHORT"]:
                        # Handle 2-digit years
                        if format_type == "MDY_SHORT":
                            month, day, year = map(int, groups)
                        else:
                            day, month, year = map(int, groups)

                        # Convert 2-digit year
                        if year < 100:
                            if year > 50:
                                year += 1900
                            else:
                                year += 2000
                    else:
                        continue

                    # Validate and create date
                    if 1 <= month <= 12 and 1 <= day <= 31:
                        return date(year, month, day)

                except (ValueError, KeyError):
                    continue

        return None

    def _parse_month(self, month_str: str, language: str) -> int:
        """Parse month name in specified language."""
        month_str_lower = month_str.lower()

        # Try specified language first
        if language in self.month_names:
            if month_str_lower in self.month_names[language]:
                return self.month_names[language][month_str_lower]

        # Try all languages
        for lang_months in self.month_names.values():
            if month_str_lower in lang_months:
                return lang_months[month_str_lower]

        # Try numeric
        try:
            month_num = int(month_str)
            if 1 <= month_num <= 12:
                return month_num
        except (ValueError, TypeError) as e:
            logger.debug("Failed to parse month as number: %s", e)

        raise ValueError(f"Unknown month: {month_str}")

    def _guess_from_numbers(self, numbers: List[str], language: str) -> date:
        """Guess date from extracted numbers based on language/region."""
        nums = [int(n) for n in numbers[:3]]

        # Find the year (usually the largest number or 4-digit number)
        year_idx = None
        for i, num in enumerate(nums):
            if num > 1900 and num < 2100:
                year_idx = i
                break

        if year_idx is None:
            # No clear year, assume last number
            year_idx = 2
            if nums[year_idx] < 100:
                nums[year_idx] = (
                    2000 + nums[year_idx]
                    if nums[year_idx] < 50
                    else 1900 + nums[year_idx]
                )

        year = nums[year_idx]
        remaining = [nums[i] for i in range(3) if i != year_idx]

        # Guess month and day based on language
        if language in ["en", "ja"]:  # US/Japan typically use MDY/YMD
            if year_idx == 0:  # YMD
                month, day = remaining[0], remaining[1]
            else:  # MDY
                month, day = remaining[0], remaining[1]
        else:  # Most others use DMY
            day, month = remaining[0], remaining[1]

        # Swap if obviously wrong
        if month > 12 and day <= 12:
            month, day = day, month

        return date(year, month, day)

    def parse_fuzzy(self, text: str, language: str = "en") -> List[date]:
        """
        Extract all possible dates from a text.

        Args:
            text: Text containing dates
            language: Language code

        Returns:
            List of parsed dates
        """
        dates = []

        # Try to find date patterns in the text
        for pattern, _ in self.patterns:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                try:
                    date_str = match.group(0)
                    parsed = self.parse(date_str, language)
                    if parsed is not None and parsed not in dates:
                        dates.append(parsed)
                except (ValueError, TypeError, AttributeError) as e:
                    logger.debug("Failed to parse date from match: %s", e)
                    continue

        return dates

    def format_date(
        self,
        date_obj: date,
        language: str = "en",
        format_type: Optional[DateFormat] = None,
    ) -> str:
        """
        Format a date according to language/region conventions.

        Args:
            date_obj: Date to format
            language: Language code
            format_type: Optional specific format

        Returns:
            Formatted date string
        """
        if format_type:
            if format_type == DateFormat.US_MDY:
                return date_obj.strftime("%m/%d/%Y")
            elif format_type == DateFormat.EU_DMY:
                return date_obj.strftime("%d/%m/%Y")
            elif format_type == DateFormat.ISO_YMD:
                return date_obj.strftime("%Y-%m-%d")
            elif format_type == DateFormat.GERMAN:
                return date_obj.strftime("%d.%m.%Y")
            elif format_type == DateFormat.JAPANESE:
                return f"{date_obj.year}年{date_obj.month}月{date_obj.day}日"

        # Default formats by language
        if language == "en":
            return date_obj.strftime("%m/%d/%Y")
        elif language == "de":
            return date_obj.strftime("%d.%m.%Y")
        elif language == "ja":
            return f"{date_obj.year}年{date_obj.month}月{date_obj.day}日"
        else:
            return date_obj.strftime("%d/%m/%Y")
