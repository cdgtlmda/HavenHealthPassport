"""Number Formatting for Multi-Cultural Healthcare.

This module provides number formatting support for different locales
and cultural preferences in healthcare contexts.
"""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from enum import Enum
from typing import Any, Dict, Optional, Tuple

from src.utils.logging import get_logger

logger = get_logger(__name__)


class NumberSystem(str, Enum):
    """Number systems used globally."""

    WESTERN = "western"  # 0-9
    ARABIC_INDIC = "arabic_indic"  # ٠-٩
    DEVANAGARI = "devanagari"  # ०-९
    BENGALI = "bengali"  # ০-৯
    PERSIAN = "persian"  # ۰-۹
    CHINESE = "chinese"  # 〇一二三四五六七八九


@dataclass
class NumberFormat:
    """Number formatting preferences."""

    decimal_separator: str = "."
    thousands_separator: str = ","
    grouping_size: int = 3  # digits between separators
    number_system: NumberSystem = NumberSystem.WESTERN
    negative_pattern: str = "-{n}"  # -{n}, ({n}), {n}-
    percent_pattern: str = "{n}%"
    currency_pattern: str = "{c}{n}"  # {c}=currency, {n}=number


class NumberFormatter:
    """Formats numbers according to locale preferences."""

    # Locale-specific formats
    LOCALE_FORMATS = {
        "en_US": NumberFormat(
            decimal_separator=".",
            thousands_separator=",",
            grouping_size=3,
            number_system=NumberSystem.WESTERN,
            negative_pattern="-{n}",
            currency_pattern="${n}",
        ),
        "en_GB": NumberFormat(
            decimal_separator=".",
            thousands_separator=",",
            grouping_size=3,
            number_system=NumberSystem.WESTERN,
            negative_pattern="-{n}",
            currency_pattern="£{n}",
        ),
        "de_DE": NumberFormat(
            decimal_separator=",",
            thousands_separator=".",
            grouping_size=3,
            number_system=NumberSystem.WESTERN,
            negative_pattern="-{n}",
            currency_pattern="{n} €",
        ),
        "fr_FR": NumberFormat(
            decimal_separator=",",
            thousands_separator=" ",
            grouping_size=3,
            number_system=NumberSystem.WESTERN,
            negative_pattern="-{n}",
            currency_pattern="{n} €",
        ),
        "ar_SA": NumberFormat(
            decimal_separator="٫",
            thousands_separator="٬",
            grouping_size=3,
            number_system=NumberSystem.ARABIC_INDIC,
            negative_pattern="{n}-",
            currency_pattern="{n} ر.س",
        ),
        "hi_IN": NumberFormat(
            decimal_separator=".",
            thousands_separator=",",
            grouping_size=3,
            number_system=NumberSystem.DEVANAGARI,
            negative_pattern="-{n}",
            currency_pattern="₹{n}",
        ),
        "bn_BD": NumberFormat(
            decimal_separator=".",
            thousands_separator=",",
            grouping_size=3,
            number_system=NumberSystem.BENGALI,
            negative_pattern="-{n}",
            currency_pattern="৳{n}",
        ),
        "fa_IR": NumberFormat(
            decimal_separator="٫",
            thousands_separator="٬",
            grouping_size=3,
            number_system=NumberSystem.PERSIAN,
            negative_pattern="{n}-",
            currency_pattern="{n} ﷼",
        ),
    }

    # Number system digit mappings
    DIGIT_MAPPINGS = {
        NumberSystem.ARABIC_INDIC: "٠١٢٣٤٥٦٧٨٩",
        NumberSystem.DEVANAGARI: "०१२३४५६७८९",
        NumberSystem.BENGALI: "০১২৩৪৫৬৭৮৯",
        NumberSystem.PERSIAN: "۰۱۲۳۴۵۶۷۸۹",
    }

    # Medical number contexts
    MEDICAL_CONTEXTS: Dict[str, Dict[str, Dict[str, Any]]] = {
        "temperature": {
            "celsius": {"min": 35.0, "max": 42.0, "decimals": 1},
            "fahrenheit": {"min": 95.0, "max": 107.6, "decimals": 1},
        },
        "blood_pressure": {
            "systolic": {"min": 70, "max": 190, "decimals": 0},
            "diastolic": {"min": 40, "max": 130, "decimals": 0},
        },
        "heart_rate": {"bpm": {"min": 40, "max": 200, "decimals": 0}},
        "weight": {
            "kg": {"min": 0.5, "max": 300, "decimals": 1},
            "lb": {"min": 1, "max": 660, "decimals": 1},
        },
        "dosage": {
            "mg": {"min": 0.01, "max": 5000, "decimals": 2},
            "ml": {"min": 0.1, "max": 1000, "decimals": 1},
        },
    }

    def __init__(self) -> None:
        """Initialize number formatter."""
        self.custom_formats: Dict[str, NumberFormat] = {}

    def format_number(
        self,
        value: float,
        locale: str = "en_US",
        decimals: Optional[int] = None,
        use_grouping: bool = True,
        medical_context: Optional[str] = None,
    ) -> str:
        """Format number according to locale."""
        # Get format for locale
        format_spec = self.LOCALE_FORMATS.get(locale, self.LOCALE_FORMATS["en_US"])

        # Handle decimals
        if decimals is None and medical_context:
            decimals = self._get_medical_decimals(medical_context, value)
        elif decimals is None:
            decimals = 2 if isinstance(value, float) and value != int(value) else 0

        # Convert to Decimal for precise handling
        decimal_value = Decimal(str(value))

        # Round to specified decimals
        if decimals >= 0:
            quantizer = Decimal(10) ** -decimals
            decimal_value = decimal_value.quantize(quantizer, rounding=ROUND_HALF_UP)

        # Handle negative numbers
        is_negative = decimal_value < 0
        if is_negative:
            decimal_value = abs(decimal_value)

        # Split into integer and decimal parts
        str_value = str(decimal_value)
        if "." in str_value:
            integer_part, decimal_part = str_value.split(".")
        else:
            integer_part = str_value
            decimal_part = ""

        # Apply grouping
        if use_grouping and len(integer_part) > format_spec.grouping_size:
            integer_part = self._apply_grouping(
                integer_part, format_spec.thousands_separator, format_spec.grouping_size
            )

        # Combine parts
        if decimal_part:
            formatted = f"{integer_part}{format_spec.decimal_separator}{decimal_part}"
        else:
            formatted = integer_part

        # Convert digits to appropriate number system
        if format_spec.number_system != NumberSystem.WESTERN:
            formatted = self._convert_digits(formatted, format_spec.number_system)

        # Apply negative pattern
        if is_negative:
            formatted = format_spec.negative_pattern.replace("{n}", formatted)

        return formatted

    def _apply_grouping(self, integer_str: str, separator: str, group_size: int) -> str:
        """Apply thousands grouping to integer string."""
        # Reverse the string for easier grouping
        reversed_str = integer_str[::-1]

        # Group digits
        groups = []
        for i in range(0, len(reversed_str), group_size):
            groups.append(reversed_str[i : i + group_size])

        # Join with separator and reverse back
        return separator.join(groups)[::-1]

    def _convert_digits(self, text: str, number_system: NumberSystem) -> str:
        """Convert Western digits to other number systems."""
        if number_system == NumberSystem.WESTERN:
            return text

        digit_mapping = self.DIGIT_MAPPINGS.get(number_system)
        if not digit_mapping:
            return text

        # Replace each Western digit with corresponding digit
        result = text
        for i, local_digit in enumerate(digit_mapping):
            result = result.replace(str(i), local_digit)

        return result

    def _get_medical_decimals(self, context: str, value: float) -> int:
        """Get appropriate decimal places for medical context."""
        # Extract main context (e.g., "temperature" from "temperature_celsius")
        main_context = context.split("_")[0]

        if main_context in self.MEDICAL_CONTEXTS:
            # Find matching sub-context
            for sub_context, specs in self.MEDICAL_CONTEXTS[main_context].items():
                if (
                    sub_context in context
                    or len(self.MEDICAL_CONTEXTS[main_context]) == 1
                ):
                    decimals: int = specs.get("decimals", 2)
                    return decimals

        return 2  # Default

    def format_percentage(
        self, value: float, locale: str = "en_US", decimals: int = 1
    ) -> str:
        """Format percentage value."""
        format_spec = self.LOCALE_FORMATS.get(locale, self.LOCALE_FORMATS["en_US"])

        # Format the number part
        number_str = self.format_number(value, locale, decimals, use_grouping=False)

        # Apply percentage pattern
        return format_spec.percent_pattern.replace("{n}", number_str)

    def format_medical_value(
        self,
        value: float,
        unit: str,
        locale: str = "en_US",
        context: Optional[str] = None,
    ) -> str:
        """Format medical measurement with unit."""
        # Determine decimals based on unit and context
        decimals = self._get_decimals_for_unit(unit, context)

        # Format number
        number_str = self.format_number(
            value, locale, decimals=decimals, medical_context=context
        )

        # Add unit with appropriate spacing
        if locale.startswith("ar") or locale.startswith("fa"):
            # RTL languages might need different spacing
            return f"{number_str} {unit}"
        else:
            return f"{number_str} {unit}"

    def _get_decimals_for_unit(self, unit: str, context: Optional[str]) -> int:
        """Get appropriate decimal places for medical unit."""
        unit_decimals = {
            "mg": 2,
            "g": 1,
            "kg": 1,
            "mcg": 0,
            "ml": 1,
            "L": 2,
            "mmHg": 0,
            "bpm": 0,
            "°C": 1,
            "°F": 1,
            "%": 1,
        }

        return unit_decimals.get(unit, 1)

    def parse_number(self, text: str, locale: str = "en_US") -> Optional[float]:
        """Parse localized number string to float."""
        format_spec = self.LOCALE_FORMATS.get(locale, self.LOCALE_FORMATS["en_US"])

        # Convert non-Western digits to Western
        if format_spec.number_system != NumberSystem.WESTERN:
            text = self._convert_to_western_digits(text, format_spec.number_system)

        # Remove grouping separators
        text = text.replace(format_spec.thousands_separator, "")

        # Replace decimal separator with period
        text = text.replace(format_spec.decimal_separator, ".")

        # Remove currency symbols and other non-numeric characters
        text = "".join(c for c in text if c.isdigit() or c in ".-")

        try:
            return float(text)
        except ValueError:
            logger.error(f"Failed to parse number: {text}")
            return None

    def _convert_to_western_digits(self, text: str, number_system: NumberSystem) -> str:
        """Convert other number systems to Western digits."""
        digit_mapping = self.DIGIT_MAPPINGS.get(number_system)
        if not digit_mapping:
            return text

        result = text
        for i, local_digit in enumerate(digit_mapping):
            result = result.replace(local_digit, str(i))

        return result

    def validate_medical_number(
        self, value: float, context: str, unit: str
    ) -> Tuple[bool, Optional[str]]:
        """Validate if medical number is within reasonable range."""
        # Get context specifications
        main_context = context.split("_")[0]

        if main_context not in self.MEDICAL_CONTEXTS:
            return True, None  # No validation rules

        # Find matching unit specifications
        for sub_context, specs in self.MEDICAL_CONTEXTS[main_context].items():
            if unit.lower() == sub_context or sub_context in context:
                min_val = specs.get("min", float("-inf"))
                max_val = specs.get("max", float("inf"))

                if value < min_val:
                    return (
                        False,
                        f"Value {value} {unit} is below minimum expected ({min_val})",
                    )
                elif value > max_val:
                    return (
                        False,
                        f"Value {value} {unit} is above maximum expected ({max_val})",
                    )

                return True, None

        return True, None

    def format_range(
        self,
        min_value: float,
        max_value: float,
        locale: str = "en_US",
        unit: Optional[str] = None,
        decimals: Optional[int] = None,
    ) -> str:
        """Format a numeric range."""
        min_str = self.format_number(min_value, locale, decimals)
        max_str = self.format_number(max_value, locale, decimals)

        # Language-specific range separators
        range_separators = {"en": "–", "ar": " - ", "zh": "至", "ja": "〜"}  # en dash

        lang = locale.split("_")[0]
        separator = range_separators.get(lang, "–")

        range_str = f"{min_str}{separator}{max_str}"

        if unit:
            range_str += f" {unit}"

        return range_str


# Global number formatter instance
number_formatter = NumberFormatter()
