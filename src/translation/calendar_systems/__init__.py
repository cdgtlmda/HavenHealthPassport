"""Calendar Systems Support for Cultural Adaptation.

This module provides support for various calendar systems used across different
cultures, enabling proper date display and conversion for refugee populations.

HIPAA Compliance: Calendar conversions for PHI date fields require:
- Access control for medical appointment dates
- Audit logging of date field access
- Proper authorization for viewing patient birthdays and medical dates
- Encrypted storage of PHI date fields using field-level encryption
- Role-based access control permissions for medical date viewing
"""

from .coptic import CopticCalendarConverter
from .ethiopian import EthiopianCalendarConverter
from .hebrew import HebrewCalendarConverter
from .manager import CalendarManager
from .nepali import NepaliCalendarConverter
from .types import CalendarConfig, CalendarDate, CalendarSystem
from .utils import CalendarUtils

__all__ = [
    "CalendarSystem",
    "CalendarDate",
    "CalendarConfig",
    "EthiopianCalendarConverter",
    "NepaliCalendarConverter",
    "HebrewCalendarConverter",
    "CopticCalendarConverter",
    "CalendarManager",
    "CalendarUtils",
]
