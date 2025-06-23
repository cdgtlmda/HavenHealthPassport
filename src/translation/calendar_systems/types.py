"""Calendar system types and data classes."""

from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional


class CalendarSystem(str, Enum):
    """Supported calendar systems."""

    GREGORIAN = "gregorian"
    HIJRI = "hijri"  # Islamic calendar
    PERSIAN = "persian"  # Solar Hijri / Jalali
    ETHIOPIAN = "ethiopian"
    COPTIC = "coptic"
    HEBREW = "hebrew"
    BUDDHIST = "buddhist"  # Thai Buddhist calendar
    NEPALI = "nepali"  # Bikram Sambat


@dataclass
class CalendarDate:
    """Represents a date in a specific calendar system."""

    year: int
    month: int
    day: int
    calendar_system: CalendarSystem
    era: Optional[str] = None  # BCE/CE, AH, etc.

    def __str__(self) -> str:
        """Return string representation of the date."""
        return f"{self.day:02d}/{self.month:02d}/{self.year}"


@dataclass
class CalendarConfig:
    """Configuration for a calendar system."""

    system: CalendarSystem
    month_names: Dict[str, List[str]]  # Language -> month names
    day_names: Dict[str, List[str]]  # Language -> day names
    era_names: Dict[str, Dict[str, str]]  # Language -> era abbreviations
    first_day_of_week: int  # 0=Monday, 6=Sunday
    weekend_days: List[int]  # Day indices
    date_format: str  # Default format string
