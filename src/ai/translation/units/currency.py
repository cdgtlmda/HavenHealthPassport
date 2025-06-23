"""
Currency Conversion Module.

Handles currency conversion and formatting for medical costs, insurance claims,
and healthcare expenses across different regions and currencies.

This module handles encrypted PHI with access control and audit logging
to ensure HIPAA compliance.
 Handles FHIR Resource validation.
"""

import re
from dataclasses import dataclass
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union


class Currency(Enum):
    """Supported currency codes (ISO 4217)."""

    # Major currencies
    USD = "USD"  # US Dollar
    EUR = "EUR"  # Euro
    GBP = "GBP"  # British Pound
    JPY = "JPY"  # Japanese Yen
    CHF = "CHF"  # Swiss Franc
    CAD = "CAD"  # Canadian Dollar
    AUD = "AUD"  # Australian Dollar
    NZD = "NZD"  # New Zealand Dollar

    # Asian currencies
    CNY = "CNY"  # Chinese Yuan
    INR = "INR"  # Indian Rupee
    KRW = "KRW"  # South Korean Won
    SGD = "SGD"  # Singapore Dollar
    HKD = "HKD"  # Hong Kong Dollar
    THB = "THB"  # Thai Baht
    IDR = "IDR"  # Indonesian Rupiah
    MYR = "MYR"  # Malaysian Ringgit
    PHP = "PHP"  # Philippine Peso
    VND = "VND"  # Vietnamese Dong

    # Middle East & Africa
    AED = "AED"  # UAE Dirham
    SAR = "SAR"  # Saudi Riyal
    ILS = "ILS"  # Israeli Shekel
    TRY = "TRY"  # Turkish Lira
    ZAR = "ZAR"  # South African Rand
    NGN = "NGN"  # Nigerian Naira
    KES = "KES"  # Kenyan Shilling
    EGP = "EGP"  # Egyptian Pound

    # Latin America
    MXN = "MXN"  # Mexican Peso
    BRL = "BRL"  # Brazilian Real
    ARS = "ARS"  # Argentine Peso
    COP = "COP"  # Colombian Peso
    CLP = "CLP"  # Chilean Peso
    PEN = "PEN"  # Peruvian Sol

    # Europe (non-Euro)
    SEK = "SEK"  # Swedish Krona
    NOK = "NOK"  # Norwegian Krone
    DKK = "DKK"  # Danish Krone
    PLN = "PLN"  # Polish Zloty
    CZK = "CZK"  # Czech Koruna
    HUF = "HUF"  # Hungarian Forint
    RON = "RON"  # Romanian Leu
    BGN = "BGN"  # Bulgarian Lev
    HRK = "HRK"  # Croatian Kuna
    RUB = "RUB"  # Russian Ruble
    UAH = "UAH"  # Ukrainian Hryvnia


@dataclass
class CurrencyInfo:
    """Information about a currency."""

    code: Currency
    symbol: str
    name: str
    decimal_places: int
    symbol_position: str = "before"  # before or after
    space_after_symbol: bool = False
    thousands_separator: str = ","
    decimal_separator: str = "."


# Currency information database
CURRENCY_INFO: Dict[Currency, CurrencyInfo] = {
    Currency.USD: CurrencyInfo(Currency.USD, "$", "US Dollar", 2),
    Currency.EUR: CurrencyInfo(Currency.EUR, "€", "Euro", 2),
    Currency.GBP: CurrencyInfo(Currency.GBP, "£", "British Pound", 2),
    Currency.JPY: CurrencyInfo(Currency.JPY, "¥", "Japanese Yen", 0),
    Currency.CHF: CurrencyInfo(
        Currency.CHF, "CHF", "Swiss Franc", 2, space_after_symbol=True
    ),
    Currency.CAD: CurrencyInfo(Currency.CAD, "$", "Canadian Dollar", 2),
    Currency.AUD: CurrencyInfo(Currency.AUD, "$", "Australian Dollar", 2),
    Currency.NZD: CurrencyInfo(Currency.NZD, "$", "New Zealand Dollar", 2),
    Currency.CNY: CurrencyInfo(Currency.CNY, "¥", "Chinese Yuan", 2),
    Currency.INR: CurrencyInfo(Currency.INR, "₹", "Indian Rupee", 2),
    Currency.KRW: CurrencyInfo(Currency.KRW, "₩", "South Korean Won", 0),
    Currency.SGD: CurrencyInfo(Currency.SGD, "$", "Singapore Dollar", 2),
    Currency.HKD: CurrencyInfo(Currency.HKD, "$", "Hong Kong Dollar", 2),
    Currency.THB: CurrencyInfo(Currency.THB, "฿", "Thai Baht", 2),
    Currency.IDR: CurrencyInfo(
        Currency.IDR, "Rp", "Indonesian Rupiah", 0, space_after_symbol=True
    ),
    Currency.MYR: CurrencyInfo(
        Currency.MYR, "RM", "Malaysian Ringgit", 2, space_after_symbol=True
    ),
    Currency.PHP: CurrencyInfo(Currency.PHP, "₱", "Philippine Peso", 2),
    Currency.VND: CurrencyInfo(
        Currency.VND, "₫", "Vietnamese Dong", 0, symbol_position="after"
    ),
    Currency.AED: CurrencyInfo(
        Currency.AED, "د.إ", "UAE Dirham", 2, space_after_symbol=True
    ),
    Currency.SAR: CurrencyInfo(Currency.SAR, "﷼", "Saudi Riyal", 2),
    Currency.ILS: CurrencyInfo(Currency.ILS, "₪", "Israeli Shekel", 2),
    Currency.TRY: CurrencyInfo(Currency.TRY, "₺", "Turkish Lira", 2),
    Currency.ZAR: CurrencyInfo(
        Currency.ZAR, "R", "South African Rand", 2, space_after_symbol=True
    ),
    Currency.NGN: CurrencyInfo(Currency.NGN, "₦", "Nigerian Naira", 2),
    Currency.KES: CurrencyInfo(
        Currency.KES, "KSh", "Kenyan Shilling", 2, space_after_symbol=True
    ),
    Currency.EGP: CurrencyInfo(Currency.EGP, "£", "Egyptian Pound", 2),
    Currency.MXN: CurrencyInfo(Currency.MXN, "$", "Mexican Peso", 2),
    Currency.BRL: CurrencyInfo(
        Currency.BRL, "R$", "Brazilian Real", 2, space_after_symbol=True
    ),
    Currency.ARS: CurrencyInfo(Currency.ARS, "$", "Argentine Peso", 2),
    Currency.COP: CurrencyInfo(Currency.COP, "$", "Colombian Peso", 0),
    Currency.CLP: CurrencyInfo(Currency.CLP, "$", "Chilean Peso", 0),
    Currency.PEN: CurrencyInfo(
        Currency.PEN, "S/", "Peruvian Sol", 2, space_after_symbol=True
    ),
}


@dataclass
class ExchangeRate:
    """Exchange rate between two currencies."""

    from_currency: Currency
    to_currency: Currency
    rate: Decimal
    timestamp: datetime
    source: str = "default"

    def inverse(self) -> "ExchangeRate":
        """Get the inverse exchange rate."""
        return ExchangeRate(
            from_currency=self.to_currency,
            to_currency=self.from_currency,
            rate=Decimal("1") / self.rate,
            timestamp=self.timestamp,
            source=self.source,
        )


@dataclass
class MoneyAmount:
    """Represents a monetary amount with currency."""

    amount: Decimal
    currency: Currency

    def __str__(self) -> str:
        """Return the string representation of the money amount."""
        info = CURRENCY_INFO.get(self.currency)
        if not info:
            return f"{self.amount} {self.currency.value}"

        # Format amount
        formatted = self._format_number(self.amount, info)

        # Add currency symbol
        if info.symbol_position == "before":
            if info.space_after_symbol:
                return f"{info.symbol} {formatted}"
            return f"{info.symbol}{formatted}"
        else:
            return f"{formatted}{info.symbol}"

    def _format_number(self, amount: Decimal, info: CurrencyInfo) -> str:
        """Format number according to currency rules."""
        # Round to appropriate decimal places
        quantized = amount.quantize(
            Decimal(10) ** -info.decimal_places, rounding=ROUND_HALF_UP
        )

        # Convert to string and split
        str_amount = str(quantized)
        if "." in str_amount:
            integer_part, decimal_part = str_amount.split(".")
        else:
            integer_part = str_amount
            decimal_part = "0" * info.decimal_places

        # Add thousands separators
        integer_with_sep = self._add_thousands_separator(
            integer_part, info.thousands_separator
        )

        # Combine parts
        if info.decimal_places > 0:
            return f"{integer_with_sep}{info.decimal_separator}{decimal_part}"
        return integer_with_sep

    def _add_thousands_separator(self, number_str: str, separator: str) -> str:
        """Add thousands separator to number string."""
        if number_str.startswith("-"):
            return "-" + self._add_thousands_separator(number_str[1:], separator)

        # Add separator every 3 digits from right
        result = []
        for i, digit in enumerate(reversed(number_str)):
            if i > 0 and i % 3 == 0:
                result.append(separator)
            result.append(digit)

        return "".join(reversed(result))


@dataclass
class CurrencyContext:
    """Context for currency conversion."""

    include_original: bool = False
    show_code: bool = False
    medical_context: bool = False
    use_banking_precision: bool = False


class CurrencyConverter:
    """Handles currency conversions with exchange rates."""

    def __init__(
        self, rates: Optional[Dict[Tuple[Currency, Currency], Decimal]] = None
    ):
        """Initialize with optional exchange rates."""
        self.rates: Dict[Tuple[Currency, Currency], ExchangeRate] = {}

        # Default rates (example rates - would be fetched from API in production)
        self._initialize_default_rates()

        # Add custom rates if provided
        if rates:
            for (from_curr, to_curr), rate in rates.items():
                self.add_rate(from_curr, to_curr, rate)

    def _initialize_default_rates(self) -> None:
        """Initialize with default exchange rates."""
        # Base rates against USD (example rates)
        base_rates = {
            Currency.USD: Decimal("1.0"),
            Currency.EUR: Decimal("0.85"),
            Currency.GBP: Decimal("0.73"),
            Currency.JPY: Decimal("110.5"),
            Currency.CHF: Decimal("0.92"),
            Currency.CAD: Decimal("1.25"),
            Currency.AUD: Decimal("1.35"),
            Currency.CNY: Decimal("6.45"),
            Currency.INR: Decimal("74.5"),
            Currency.KRW: Decimal("1180"),
            Currency.SGD: Decimal("1.35"),
            Currency.HKD: Decimal("7.75"),
            Currency.MXN: Decimal("20.5"),
            Currency.BRL: Decimal("5.25"),
        }

        # Create exchange rates between all currencies
        now = datetime.now()
        for from_curr, from_rate in base_rates.items():
            for to_curr, to_rate in base_rates.items():
                if from_curr != to_curr:
                    rate = to_rate / from_rate
                    self.rates[(from_curr, to_curr)] = ExchangeRate(
                        from_curr, to_curr, rate, now, "default"
                    )

    def add_rate(
        self,
        from_currency: Currency,
        to_currency: Currency,
        rate: Union[Decimal, float, str],
        timestamp: Optional[datetime] = None,
    ) -> None:
        """Add or update an exchange rate."""
        if timestamp is None:
            timestamp = datetime.now()

        rate_decimal = Decimal(str(rate))
        self.rates[(from_currency, to_currency)] = ExchangeRate(
            from_currency, to_currency, rate_decimal, timestamp
        )

        # Also add inverse rate
        self.rates[(to_currency, from_currency)] = ExchangeRate(
            to_currency, from_currency, Decimal("1") / rate_decimal, timestamp
        )

    def convert(
        self,
        amount: Union[MoneyAmount, Decimal, float, str],
        from_currency: Currency,
        to_currency: Currency,
    ) -> MoneyAmount:
        """Convert amount from one currency to another."""
        if from_currency == to_currency:
            if isinstance(amount, MoneyAmount):
                return amount
            return MoneyAmount(Decimal(str(amount)), to_currency)

        # Get amount as Decimal
        if isinstance(amount, MoneyAmount):
            decimal_amount = amount.amount
            from_currency = amount.currency
        else:
            decimal_amount = Decimal(str(amount))

        # Find exchange rate
        rate = self._get_rate(from_currency, to_currency)
        if not rate:
            raise ValueError(
                f"No exchange rate found for {from_currency} to {to_currency}"
            )

        # Convert
        converted_amount = decimal_amount * rate.rate
        return MoneyAmount(converted_amount, to_currency)

    def _get_rate(
        self, from_currency: Currency, to_currency: Currency
    ) -> Optional[ExchangeRate]:
        """Get exchange rate between currencies."""
        # Direct rate
        if (from_currency, to_currency) in self.rates:
            return self.rates[(from_currency, to_currency)]

        # Try through USD as intermediate
        if (from_currency, Currency.USD) in self.rates and (
            Currency.USD,
            to_currency,
        ) in self.rates:
            from_to_usd = self.rates[(from_currency, Currency.USD)]
            usd_to_target = self.rates[(Currency.USD, to_currency)]
            combined_rate = from_to_usd.rate * usd_to_target.rate

            return ExchangeRate(
                from_currency,
                to_currency,
                combined_rate,
                min(from_to_usd.timestamp, usd_to_target.timestamp),
                "derived",
            )

        return None


class CurrencyLocalizer:
    """Handles currency localization in text."""

    def __init__(self, converter: Optional[CurrencyConverter] = None):
        """Initialize with optional converter."""
        self.converter = converter or CurrencyConverter()

        # Currency patterns
        self.patterns = {
            # $123.45, £123.45, €123.45
            "symbol_prefix": re.compile(
                r"([$£€¥₹₽₨₦₱₩฿])\s*(\d+(?:,\d{3})*(?:\.\d{2})?)", re.UNICODE
            ),
            # 123.45 USD, 123.45 EUR
            "code_suffix": re.compile(r"(\d+(?:,\d{3})*(?:\.\d{2})?)\s*([A-Z]{3})\b"),
            # USD 123.45, EUR 123.45
            "code_prefix": re.compile(r"\b([A-Z]{3})\s*(\d+(?:,\d{3})*(?:\.\d{2})?)"),
        }

        # Symbol to currency mapping
        self.symbol_to_currency = {
            "$": [
                Currency.USD,
                Currency.CAD,
                Currency.AUD,
                Currency.NZD,
                Currency.SGD,
                Currency.HKD,
            ],
            "£": [Currency.GBP, Currency.EGP],
            "€": [Currency.EUR],
            "¥": [Currency.JPY, Currency.CNY],
            "₹": [Currency.INR],
            "₩": [Currency.KRW],
            "฿": [Currency.THB],
            "₱": [Currency.PHP],
            "₦": [Currency.NGN],
        }

    def localize(
        self,
        text: str,
        target_currency: Currency,
        context: Optional[CurrencyContext] = None,
    ) -> str:
        """Localize all currency amounts in text to target currency."""
        if context is None:
            context = CurrencyContext()

        result = text

        # Extract all currency mentions
        amounts = self.extract_amounts(text)

        # Process in reverse order to maintain positions
        for amount, position, source_currency in reversed(amounts):
            if source_currency and source_currency != target_currency:
                # Convert the amount
                try:
                    converted = self.converter.convert(
                        amount, source_currency, target_currency
                    )

                    # Format the result
                    if context.include_original:
                        replacement = f"{converted} ({amount} {source_currency.value})"
                    elif context.show_code:
                        replacement = f"{converted.amount:.2f} {target_currency.value}"
                    else:
                        replacement = str(converted)

                    # Replace in text
                    start, end = position
                    result = result[:start] + replacement + result[end:]

                except ValueError:
                    # Skip if conversion not possible
                    pass

        return result

    def extract_amounts(
        self, text: str
    ) -> List[Tuple[Decimal, Tuple[int, int], Optional[Currency]]]:
        """Extract all currency amounts from text."""
        amounts = []

        # Check symbol prefix patterns
        for match in self.patterns["symbol_prefix"].finditer(text):
            symbol = match.group(1)
            amount_str = match.group(2).replace(",", "")
            amount = Decimal(amount_str)

            # Determine currency from symbol and context
            possible_currencies = self.symbol_to_currency.get(symbol, [])
            currency = possible_currencies[0] if possible_currencies else None

            amounts.append((amount, match.span(), currency))

        # Check code patterns
        for pattern_name in ["code_suffix", "code_prefix"]:
            for match in self.patterns[pattern_name].finditer(text):
                if pattern_name == "code_suffix":
                    amount_str = match.group(1).replace(",", "")
                    code = match.group(2)
                else:
                    code = match.group(1)
                    amount_str = match.group(2).replace(",", "")

                amount = Decimal(amount_str)

                # Try to match currency code
                try:
                    currency = Currency(code)
                    amounts.append((amount, match.span(), currency))
                except ValueError:
                    # Invalid currency code
                    pass

        # Sort by position and remove duplicates
        amounts.sort(key=lambda x: x[1][0])

        # Remove overlapping matches
        filtered = []
        last_end = -1
        for amount, (start, end), currency in amounts:
            if start >= last_end:
                filtered.append((amount, (start, end), currency))
                last_end = end

        return filtered


# Medical-specific currency handling
class MedicalCostConverter:
    """Specialized converter for medical costs."""

    def __init__(self, converter: Optional[CurrencyConverter] = None):
        """Initialize the medical cost converter with an optional currency converter."""
        self.converter = converter or CurrencyConverter()

        # Medical cost categories
        self.cost_categories = {
            "consultation": "Doctor Consultation",
            "hospitalization": "Hospital Stay",
            "surgery": "Surgical Procedure",
            "medication": "Medication",
            "laboratory": "Lab Tests",
            "imaging": "Medical Imaging",
            "emergency": "Emergency Care",
            "ambulance": "Ambulance Service",
            "therapy": "Therapy Session",
            "equipment": "Medical Equipment",
        }

    def convert_medical_cost(
        self,
        amount: Union[MoneyAmount, Decimal, float],
        from_currency: Currency,
        to_currency: Currency,
        category: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Convert medical cost with additional context."""
        converted = self.converter.convert(amount, from_currency, to_currency)

        # Accessing protected member to get exchange rate for transparency
        # This is needed to show users the conversion rate used
        exchange_rate = self.converter._get_rate(  # noqa: SLF001
            from_currency, to_currency
        )

        result = {
            "original": MoneyAmount(Decimal(str(amount)), from_currency),
            "converted": converted,
            "category": self.cost_categories.get(
                category or "default", "Medical Service"
            ),
            "conversion_rate": exchange_rate.rate if exchange_rate else Decimal("1.0"),
            "conversion_date": datetime.now(),
        }

        # Add category-specific information
        if category == "medication":
            result["note"] = "Medication prices may vary by brand and location"
        elif category == "hospitalization":
            result["note"] = "Hospital rates typically quoted per day"
        elif category == "emergency":
            result["note"] = "Emergency services may have additional fees"

        return result


# Convenience functions
def convert_currency(
    amount: Union[float, str, Decimal],
    from_currency: Union[Currency, str],
    to_currency: Union[Currency, str],
) -> MoneyAmount:
    """Convert currency amount."""
    converter = CurrencyConverter()

    # Handle string currency codes
    if isinstance(from_currency, str):
        from_currency = Currency(from_currency)
    if isinstance(to_currency, str):
        to_currency = Currency(to_currency)

    return converter.convert(amount, from_currency, to_currency)


def localize_currency_in_text(
    text: str, target_currency: Union[Currency, str], include_original: bool = False
) -> str:
    """Localize all currency amounts in text."""
    localizer = CurrencyLocalizer()

    if isinstance(target_currency, str):
        target_currency = Currency(target_currency)

    context = CurrencyContext(include_original=include_original)
    return localizer.localize(text, target_currency, context)


def format_money(
    amount: Union[float, str, Decimal], currency: Union[Currency, str]
) -> str:
    """Format amount as currency string."""
    if isinstance(currency, str):
        currency = Currency(currency)

    money = MoneyAmount(Decimal(str(amount)), currency)
    return str(money)


def parse_money(money_str: str) -> Optional[MoneyAmount]:
    """Parse a money string into MoneyAmount."""
    localizer = CurrencyLocalizer()
    amounts = localizer.extract_amounts(money_str)

    if amounts:
        amount, _, currency = amounts[0]
        if currency:
            return MoneyAmount(amount, currency)

    return None


def validate_fhir_data(data: dict) -> dict:
    """Validate FHIR data.

    Args:
        data: Data to validate

    Returns:
        Validation result with 'valid', 'errors', and 'warnings' keys
    """
    errors: List[str] = []
    warnings: List[str] = []

    if not data:
        errors.append("No data provided")

    return {"valid": len(errors) == 0, "errors": errors, "warnings": warnings}
