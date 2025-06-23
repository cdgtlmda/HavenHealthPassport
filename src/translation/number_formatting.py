"""Number and Currency Formatting for Cultural Adaptation.

This module provides culturally appropriate number and currency formatting
for different locales and regions.
"""

import decimal
import re
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from src.utils.logging import get_logger

logger = get_logger(__name__)


class NumberSystem(str, Enum):
    """Number systems used in different cultures."""

    WESTERN = "western"  # 0-9
    ARABIC_INDIC = "arabic-indic"  # ٠-٩
    EASTERN_ARABIC = "eastern-arabic"  # ۰-۹ (Persian)
    DEVANAGARI = "devanagari"  # ०-९
    BENGALI = "bengali"  # ০-৯
    THAI = "thai"  # ๐-๙
    BURMESE = "burmese"  # ၀-၉


@dataclass
class NumberFormat:
    """Number formatting configuration."""

    decimal_separator: str
    thousands_separator: str
    grouping_pattern: List[int]  # e.g., [3, 2] for Indian numbering
    negative_pattern: str  # e.g., "-{n}", "({n})"
    percent_pattern: str
    number_system: NumberSystem


@dataclass
class CurrencyFormat:
    """Currency formatting configuration."""

    currency_code: str
    symbol: str
    symbol_position: str  # "before" or "after"
    decimal_places: int
    symbol_spacing: bool  # Space between symbol and number
    negative_pattern: str  # e.g., "-$n", "($n)"


class NumberFormatter:
    """Formats numbers according to cultural preferences."""

    # Number format configurations by locale
    LOCALE_FORMATS = {
        "en-US": NumberFormat(
            decimal_separator=".",
            thousands_separator=",",
            grouping_pattern=[3],
            negative_pattern="-{n}",
            percent_pattern="{n}%",
            number_system=NumberSystem.WESTERN,
        ),
        "en-GB": NumberFormat(
            decimal_separator=".",
            thousands_separator=",",
            grouping_pattern=[3],
            negative_pattern="-{n}",
            percent_pattern="{n}%",
            number_system=NumberSystem.WESTERN,
        ),
        "ar": NumberFormat(
            decimal_separator="٫",
            thousands_separator="٬",
            grouping_pattern=[3],
            negative_pattern="-{n}",
            percent_pattern="{n}٪",
            number_system=NumberSystem.ARABIC_INDIC,
        ),
        "fa": NumberFormat(
            decimal_separator="٫",
            thousands_separator="٬",
            grouping_pattern=[3],
            negative_pattern="-{n}",
            percent_pattern="٪{n}",
            number_system=NumberSystem.EASTERN_ARABIC,
        ),
        "ur": NumberFormat(
            decimal_separator=".",
            thousands_separator=",",
            grouping_pattern=[3],
            negative_pattern="-{n}",
            percent_pattern="{n}%",
            number_system=NumberSystem.ARABIC_INDIC,
        ),
        "hi": NumberFormat(
            decimal_separator=".",
            thousands_separator=",",
            grouping_pattern=[3, 2],  # Indian numbering: 1,00,000
            negative_pattern="-{n}",
            percent_pattern="{n}%",
            number_system=NumberSystem.DEVANAGARI,
        ),
        "bn": NumberFormat(
            decimal_separator=".",
            thousands_separator=",",
            grouping_pattern=[3, 2],  # Indian numbering
            negative_pattern="-{n}",
            percent_pattern="{n}%",
            number_system=NumberSystem.BENGALI,
        ),
        "th": NumberFormat(
            decimal_separator=".",
            thousands_separator=",",
            grouping_pattern=[3],
            negative_pattern="-{n}",
            percent_pattern="{n}%",
            number_system=NumberSystem.THAI,
        ),
        "fr": NumberFormat(
            decimal_separator=",",
            thousands_separator=" ",
            grouping_pattern=[3],
            negative_pattern="-{n}",
            percent_pattern="{n} %",
            number_system=NumberSystem.WESTERN,
        ),
        "es": NumberFormat(
            decimal_separator=",",
            thousands_separator=".",
            grouping_pattern=[3],
            negative_pattern="-{n}",
            percent_pattern="{n} %",
            number_system=NumberSystem.WESTERN,
        ),
        "sw": NumberFormat(
            decimal_separator=".",
            thousands_separator=",",
            grouping_pattern=[3],
            negative_pattern="-{n}",
            percent_pattern="{n}%",
            number_system=NumberSystem.WESTERN,
        ),
    }

    # Digit mappings for different number systems
    DIGIT_MAPPINGS = {
        NumberSystem.ARABIC_INDIC: {
            "0": "٠",
            "1": "١",
            "2": "٢",
            "3": "٣",
            "4": "٤",
            "5": "٥",
            "6": "٦",
            "7": "٧",
            "8": "٨",
            "9": "٩",
        },
        NumberSystem.EASTERN_ARABIC: {
            "0": "۰",
            "1": "۱",
            "2": "۲",
            "3": "۳",
            "4": "۴",
            "5": "۵",
            "6": "۶",
            "7": "۷",
            "8": "۸",
            "9": "۹",
        },
        NumberSystem.DEVANAGARI: {
            "0": "०",
            "1": "१",
            "2": "२",
            "3": "३",
            "4": "४",
            "5": "५",
            "6": "६",
            "7": "७",
            "8": "८",
            "9": "९",
        },
        NumberSystem.BENGALI: {
            "0": "০",
            "1": "১",
            "2": "২",
            "3": "৩",
            "4": "৪",
            "5": "৫",
            "6": "৬",
            "7": "৭",
            "8": "৮",
            "9": "৯",
        },
        NumberSystem.THAI: {
            "0": "๐",
            "1": "๑",
            "2": "๒",
            "3": "๓",
            "4": "๔",
            "5": "๕",
            "6": "๖",
            "7": "๗",
            "8": "๘",
            "9": "๙",
        },
    }

    def __init__(self) -> None:
        """Initialize number formatter."""
        self.locale_cache: Dict[str, Any] = {}

    def format_number(
        self,
        value: Union[int, float, Decimal],
        locale: str,
        decimal_places: Optional[int] = None,
        use_grouping: bool = True,
        force_sign: bool = False,
    ) -> str:
        """
        Format a number according to locale.

        Args:
            value: Number to format
            locale: Locale code (e.g., "en-US", "ar")
            decimal_places: Number of decimal places
            use_grouping: Whether to use thousands separators
            force_sign: Always show sign (+ or -)

        Returns:
            Formatted number string
        """
        # Get format configuration
        format_config = self._get_format_config(locale)

        # Convert to Decimal for precision
        decimal_value = Decimal(str(value))

        # Round if decimal places specified
        if decimal_places is not None:
            quantizer = Decimal(10) ** -decimal_places
            decimal_value = decimal_value.quantize(quantizer, rounding=ROUND_HALF_UP)

        # Check if negative
        is_negative = decimal_value < 0
        if is_negative:
            decimal_value = abs(decimal_value)

        # Split into integer and decimal parts
        str_value = str(decimal_value)
        if "." in str_value:
            integer_part, decimal_part = str_value.split(".")
        else:
            integer_part, decimal_part = str_value, ""

        # Apply grouping
        if use_grouping:
            integer_part = self._apply_grouping(
                integer_part, format_config.grouping_pattern
            )
            integer_part = integer_part.replace(",", format_config.thousands_separator)

        # Convert digits to locale's number system
        integer_part = self._convert_digits(integer_part, format_config.number_system)
        decimal_part = self._convert_digits(decimal_part, format_config.number_system)

        # Combine parts
        if decimal_part:
            formatted = f"{integer_part}{format_config.decimal_separator}{decimal_part}"
        else:
            formatted = integer_part

        # Apply negative pattern
        if is_negative:
            formatted = format_config.negative_pattern.replace("{n}", formatted)
        elif force_sign:
            formatted = f"+{formatted}"

        return formatted

    def format_percent(
        self, value: Union[int, float, Decimal], locale: str, decimal_places: int = 0
    ) -> str:
        """
        Format a number as percentage.

        Args:
            value: Number to format (0.15 = 15%)
            locale: Locale code
            decimal_places: Number of decimal places

        Returns:
            Formatted percentage string
        """
        format_config = self._get_format_config(locale)

        # Convert to percentage
        percent_value = Decimal(str(value)) * 100

        # Format the number part
        number_str = self.format_number(
            percent_value, locale, decimal_places=decimal_places, use_grouping=True
        )

        # Apply percent pattern
        return format_config.percent_pattern.replace("{n}", number_str)

    def format_ordinal(
        self, value: int, locale: str, gender: Optional[str] = None
    ) -> str:
        """
        Format ordinal numbers (1st, 2nd, etc.).

        Args:
            value: Number to format
            locale: Locale code
            gender: Gender for gendered languages

        Returns:
            Formatted ordinal string
        """
        # English ordinals
        if locale.startswith("en"):
            if value % 100 in [11, 12, 13]:
                suffix = "th"
            else:
                suffix = {1: "st", 2: "nd", 3: "rd"}.get(value % 10, "th")
            return f"{value}{suffix}"

        # Arabic ordinals
        elif locale == "ar":
            # Arabic uses different forms for ordinals
            ordinal_forms = {
                1: "الأول",
                2: "الثاني",
                3: "الثالث",
                4: "الرابع",
                5: "الخامس",
                6: "السادس",
                7: "السابع",
                8: "الثامن",
                9: "التاسع",
                10: "العاشر",
            }
            return ordinal_forms.get(value, f"ال{self.format_number(value, locale)}")

        # French ordinals
        elif locale == "fr":
            if value == 1:
                return "1er" if gender != "feminine" else "1ère"
            else:
                return f"{value}e"

        # Spanish ordinals
        elif locale == "es":
            ordinal_forms = {
                1: "1º" if gender != "feminine" else "1ª",
                2: "2º" if gender != "feminine" else "2ª",
                3: "3º" if gender != "feminine" else "3ª",
            }
            return ordinal_forms.get(value, f"{value}º")

        # Default: just return the number
        return self.format_number(value, locale)

    def _get_format_config(self, locale: str) -> NumberFormat:
        """Get format configuration for locale."""
        # Try exact match
        if locale in self.LOCALE_FORMATS:
            return self.LOCALE_FORMATS[locale]

        # Try language only (e.g., "en" from "en-US")
        language = locale.split("-")[0]
        if language in self.LOCALE_FORMATS:
            return self.LOCALE_FORMATS[language]

        # Default to en-US
        return self.LOCALE_FORMATS["en-US"]

    def _apply_grouping(self, number_str: str, pattern: List[int]) -> str:
        """Apply grouping pattern to number string."""
        if not pattern or len(number_str) <= pattern[0]:
            return number_str

        # Reverse for easier processing
        reversed_str = number_str[::-1]
        grouped = []
        position = 0

        for _, digit in enumerate(reversed_str):
            if position > 0 and position in self._get_grouping_positions(
                len(number_str), pattern
            ):
                grouped.append(",")
            grouped.append(digit)
            position += 1

        return "".join(grouped[::-1])

    def _get_grouping_positions(self, length: int, pattern: List[int]) -> List[int]:
        """Get positions where grouping separators should be placed."""
        positions = []
        pos = 0

        # Apply pattern
        for i, group_size in enumerate(pattern):
            pos += group_size
            if pos < length:
                positions.append(pos)

                # Repeat last pattern
                if i == len(pattern) - 1:
                    while pos < length:
                        pos += group_size
                        if pos < length:
                            positions.append(pos)

        return positions

    def _convert_digits(self, text: str, number_system: NumberSystem) -> str:
        """Convert Western digits to locale's number system."""
        if number_system == NumberSystem.WESTERN:
            return text

        mapping = self.DIGIT_MAPPINGS.get(number_system, {})
        if not mapping:
            return text

        result = text
        for western, local in mapping.items():
            result = result.replace(western, local)

        return result

    def parse_number(self, text: str, locale: str) -> Optional[Decimal]:
        """
        Parse a localized number string.

        Args:
            text: Localized number string
            locale: Locale code

        Returns:
            Parsed number or None
        """
        format_config = self._get_format_config(locale)

        # Convert locale digits to Western
        normalized = text
        if format_config.number_system != NumberSystem.WESTERN:
            mapping = self.DIGIT_MAPPINGS.get(format_config.number_system, {})
            for western, local in mapping.items():
                normalized = normalized.replace(local, western)

        # Remove thousands separators
        normalized = normalized.replace(format_config.thousands_separator, "")

        # Replace decimal separator
        normalized = normalized.replace(format_config.decimal_separator, ".")

        # Remove negative pattern
        is_negative = False
        if format_config.negative_pattern:
            negative_pattern = format_config.negative_pattern.replace("{n}", "(.*)")
            match = re.match(negative_pattern, normalized)
            if match:
                normalized = match.group(1)
                is_negative = True

        # Try to parse
        try:
            value = Decimal(normalized)
            return -value if is_negative else value
        except (ValueError, decimal.InvalidOperation):
            return None


class CurrencyFormatter:
    """Formats currency values according to cultural preferences."""

    # Currency configurations
    CURRENCY_CONFIGS = {
        "USD": CurrencyFormat(
            currency_code="USD",
            symbol="$",
            symbol_position="before",
            decimal_places=2,
            symbol_spacing=False,
            negative_pattern="-$n",
        ),
        "EUR": CurrencyFormat(
            currency_code="EUR",
            symbol="€",
            symbol_position="before",
            decimal_places=2,
            symbol_spacing=False,
            negative_pattern="-€n",
        ),
        "GBP": CurrencyFormat(
            currency_code="GBP",
            symbol="£",
            symbol_position="before",
            decimal_places=2,
            symbol_spacing=False,
            negative_pattern="-£n",
        ),
        "JPY": CurrencyFormat(
            currency_code="JPY",
            symbol="¥",
            symbol_position="before",
            decimal_places=0,
            symbol_spacing=False,
            negative_pattern="-¥n",
        ),
        "CNY": CurrencyFormat(
            currency_code="CNY",
            symbol="¥",
            symbol_position="before",
            decimal_places=2,
            symbol_spacing=False,
            negative_pattern="-¥n",
        ),
        "INR": CurrencyFormat(
            currency_code="INR",
            symbol="₹",
            symbol_position="before",
            decimal_places=2,
            symbol_spacing=False,
            negative_pattern="-₹n",
        ),
        "PKR": CurrencyFormat(
            currency_code="PKR",
            symbol="₨",
            symbol_position="before",
            decimal_places=2,
            symbol_spacing=False,
            negative_pattern="-₨n",
        ),
        "BDT": CurrencyFormat(
            currency_code="BDT",
            symbol="৳",
            symbol_position="before",
            decimal_places=2,
            symbol_spacing=False,
            negative_pattern="-৳n",
        ),
        "AFN": CurrencyFormat(
            currency_code="AFN",
            symbol="؋",
            symbol_position="after",
            decimal_places=2,
            symbol_spacing=True,
            negative_pattern="-n ؋",
        ),
        "IRR": CurrencyFormat(
            currency_code="IRR",
            symbol="﷼",
            symbol_position="after",
            decimal_places=0,
            symbol_spacing=True,
            negative_pattern="-n ﷼",
        ),
        "IQD": CurrencyFormat(
            currency_code="IQD",
            symbol="ع.د",
            symbol_position="after",
            decimal_places=3,
            symbol_spacing=True,
            negative_pattern="-n ع.د",
        ),
        "SYP": CurrencyFormat(
            currency_code="SYP",
            symbol="ل.س",
            symbol_position="after",
            decimal_places=2,
            symbol_spacing=True,
            negative_pattern="-n ل.س",
        ),
        "TRY": CurrencyFormat(
            currency_code="TRY",
            symbol="₺",
            symbol_position="after",
            decimal_places=2,
            symbol_spacing=True,
            negative_pattern="-n ₺",
        ),
        "KES": CurrencyFormat(
            currency_code="KES",
            symbol="KSh",
            symbol_position="before",
            decimal_places=2,
            symbol_spacing=True,
            negative_pattern="-KSh n",
        ),
        "ETB": CurrencyFormat(
            currency_code="ETB",
            symbol="Br",
            symbol_position="before",
            decimal_places=2,
            symbol_spacing=True,
            negative_pattern="-Br n",
        ),
        "NGN": CurrencyFormat(
            currency_code="NGN",
            symbol="₦",
            symbol_position="before",
            decimal_places=2,
            symbol_spacing=False,
            negative_pattern="-₦n",
        ),
        "ZAR": CurrencyFormat(
            currency_code="ZAR",
            symbol="R",
            symbol_position="before",
            decimal_places=2,
            symbol_spacing=True,
            negative_pattern="-R n",
        ),
    }

    # Locale to preferred currency mapping
    LOCALE_CURRENCIES = {
        "en-US": "USD",
        "en-GB": "GBP",
        "en-CA": "CAD",
        "en-AU": "AUD",
        "ar-SA": "SAR",
        "ar-AE": "AED",
        "ar-EG": "EGP",
        "ar-IQ": "IQD",
        "ar-SY": "SYP",
        "fa-IR": "IRR",
        "fa-AF": "AFN",
        "ur-PK": "PKR",
        "bn-BD": "BDT",
        "hi-IN": "INR",
        "sw-KE": "KES",
        "am-ET": "ETB",
        "fr-FR": "EUR",
        "es-ES": "EUR",
        "pt-BR": "BRL",
        "zh-CN": "CNY",
        "ja-JP": "JPY",
        "ko-KR": "KRW",
        "th-TH": "THB",
        "vi-VN": "VND",
        "id-ID": "IDR",
        "tr-TR": "TRY",
    }

    def __init__(self, formatter: NumberFormatter):
        """Initialize currency formatter."""
        self.number_formatter = formatter

    def format_currency(
        self,
        amount: Union[int, float, Decimal],
        currency_code: str,
        locale: str,
        show_symbol: bool = True,
        show_code: bool = False,
    ) -> str:
        """
        Format currency amount.

        Args:
            amount: Amount to format
            currency_code: ISO 4217 currency code
            locale: Locale code
            show_symbol: Show currency symbol
            show_code: Show currency code

        Returns:
            Formatted currency string
        """
        # Get currency configuration
        currency_config = self.CURRENCY_CONFIGS.get(
            currency_code,
            CurrencyFormat(
                currency_code=currency_code,
                symbol=currency_code,
                symbol_position="before",
                decimal_places=2,
                symbol_spacing=True,
                negative_pattern=f"-{currency_code} n",
            ),
        )

        # Check if negative
        is_negative = amount < 0
        if is_negative:
            amount = abs(float(amount))

        # Format number part
        formatted_number = self.number_formatter.format_number(
            amount,
            locale,
            decimal_places=currency_config.decimal_places,
            use_grouping=True,
        )

        # Build currency string
        if show_symbol and not show_code:
            symbol = currency_config.symbol
        elif show_code:
            symbol = currency_config.currency_code
        else:
            return formatted_number

        # Apply symbol position
        spacing = " " if currency_config.symbol_spacing else ""

        if currency_config.symbol_position == "before":
            formatted = f"{symbol}{spacing}{formatted_number}"
        else:
            formatted = f"{formatted_number}{spacing}{symbol}"

        # Apply negative pattern
        if is_negative:
            formatted = currency_config.negative_pattern.replace("n", formatted_number)
            if "$" in currency_config.negative_pattern:
                formatted = formatted.replace("$", symbol)

        return formatted

    def get_preferred_currency(self, locale: str) -> str:
        """Get preferred currency for a locale."""
        return self.LOCALE_CURRENCIES.get(locale, "USD")

    def convert_currency(
        self,
        amount: Decimal,
        from_currency: str,
        to_currency: str,
        exchange_rates: Dict[str, float],
    ) -> Decimal:
        """
        Convert between currencies.

        Args:
            amount: Amount to convert
            from_currency: Source currency code
            to_currency: Target currency code
            exchange_rates: Exchange rates relative to base currency

        Returns:
            Converted amount
        """
        if from_currency == to_currency:
            return amount

        # Convert to base currency (usually USD)
        from_rate = exchange_rates.get(from_currency, 1.0)
        to_rate = exchange_rates.get(to_currency, 1.0)

        # Convert
        base_amount = amount / Decimal(str(from_rate))
        converted = base_amount * Decimal(str(to_rate))

        # Round to target currency decimal places
        to_config = self.CURRENCY_CONFIGS.get(to_currency)
        if to_config:
            quantizer = Decimal(10) ** -to_config.decimal_places
            converted = converted.quantize(quantizer, rounding=ROUND_HALF_UP)

        return converted


# Global formatter instances
number_formatter = NumberFormatter()
currency_formatter = CurrencyFormatter(number_formatter)
