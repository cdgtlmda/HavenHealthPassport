"""Currency and Measurement Unit Management.

This module provides currency display and measurement unit conversion
for global healthcare applications.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional

from src.healthcare.hipaa_access_control import require_phi_access  # noqa: F401
from src.services.encryption_service import EncryptionService  # noqa: F401
from src.utils.logging import get_logger

logger = get_logger(__name__)


class MeasurementSystem(str, Enum):
    """Measurement systems."""

    METRIC = "metric"
    IMPERIAL = "imperial"
    US_CUSTOMARY = "us_customary"


@dataclass
class CurrencyInfo:
    """Currency information."""

    code: str  # ISO 4217 code
    symbol: str
    name: str
    decimal_places: int
    symbol_position: str  # prefix/suffix
    space_between: bool


@dataclass
class UnitConversion:
    """Unit conversion information."""

    from_unit: str
    to_unit: str
    factor: float
    offset: float = 0.0  # For temperature conversions


class CurrencyManager:
    """Manages currency display for healthcare costs."""

    # Common currencies in refugee regions
    CURRENCIES = {
        "USD": CurrencyInfo("USD", "$", "US Dollar", 2, "prefix", False),
        "EUR": CurrencyInfo("EUR", "€", "Euro", 2, "suffix", True),
        "GBP": CurrencyInfo("GBP", "£", "British Pound", 2, "prefix", False),
        "KES": CurrencyInfo("KES", "KSh", "Kenyan Shilling", 2, "prefix", True),
        "JOD": CurrencyInfo("JOD", "د.أ", "Jordanian Dinar", 3, "prefix", True),
        "BDT": CurrencyInfo("BDT", "৳", "Bangladeshi Taka", 2, "prefix", False),
        "PKR": CurrencyInfo("PKR", "₨", "Pakistani Rupee", 2, "prefix", False),
        "INR": CurrencyInfo("INR", "₹", "Indian Rupee", 2, "prefix", False),
        "AFN": CurrencyInfo("AFN", "؋", "Afghan Afghani", 2, "prefix", True),
        "SYP": CurrencyInfo("SYP", "£S", "Syrian Pound", 2, "prefix", True),
        "IQD": CurrencyInfo("IQD", "ع.د", "Iraqi Dinar", 3, "prefix", True),
        "TRY": CurrencyInfo("TRY", "₺", "Turkish Lira", 2, "suffix", True),
        "NGN": CurrencyInfo("NGN", "₦", "Nigerian Naira", 2, "prefix", False),
        "ETB": CurrencyInfo("ETB", "Br", "Ethiopian Birr", 2, "prefix", True),
        "UGX": CurrencyInfo("UGX", "USh", "Ugandan Shilling", 0, "prefix", True),
    }

    def format_currency(
        self,
        amount: float,
        currency_code: str,
        locale: Optional[str] = None,
        show_code: bool = False,
    ) -> str:
        """Format currency amount."""
        currency = self.CURRENCIES.get(currency_code)
        if not currency:
            return f"{amount:.2f} {currency_code}"

        # Format number with appropriate decimals
        from src.localization.number_formatter import number_formatter

        formatted_number = number_formatter.format_number(
            amount, locale or "en_US", decimals=currency.decimal_places
        )

        # Apply currency formatting
        if currency.symbol_position == "prefix":
            if currency.space_between:
                result = f"{currency.symbol} {formatted_number}"
            else:
                result = f"{currency.symbol}{formatted_number}"
        else:
            if currency.space_between:
                result = f"{formatted_number} {currency.symbol}"
            else:
                result = f"{formatted_number}{currency.symbol}"

        # Add currency code if requested
        if show_code:
            result += f" {currency_code}"

        return result

    def get_healthcare_cost_estimate(
        self, service: str, country: str, currency_code: str
    ) -> Dict[str, Any]:
        """Get estimated healthcare costs by country."""
        # Simplified cost estimates for common services
        cost_estimates = {
            "consultation": {
                "KE": 500,  # Kenya - KES
                "JO": 20,  # Jordan - JOD
                "BD": 500,  # Bangladesh - BDT
                "PK": 1000,  # Pakistan - PKR
                "US": 150,  # USA - USD
            },
            "medication_monthly": {
                "KE": 2000,
                "JO": 50,
                "BD": 1500,
                "PK": 3000,
                "US": 300,
            },
            "lab_test": {
                "KE": 1000,
                "JO": 30,
                "BD": 800,
                "PK": 1500,
                "US": 200,
            },
        }

        base_cost = cost_estimates.get(service, {}).get(country, 0)

        return {
            "service": service,
            "country": country,
            "estimated_cost": base_cost,
            "formatted_cost": self.format_currency(base_cost, currency_code),
            "currency": currency_code,
            "note": "Costs are estimates and may vary",
        }


class MeasurementUnitManager:
    """Manages measurement unit conversions for healthcare."""

    # Unit conversions for healthcare
    CONVERSIONS = {
        # Weight
        ("kg", "lb"): UnitConversion("kg", "lb", 2.20462),
        ("lb", "kg"): UnitConversion("lb", "kg", 0.453592),
        ("g", "oz"): UnitConversion("g", "oz", 0.035274),
        ("oz", "g"): UnitConversion("oz", "g", 28.3495),
        # Height/Length
        ("cm", "in"): UnitConversion("cm", "in", 0.393701),
        ("in", "cm"): UnitConversion("in", "cm", 2.54),
        ("m", "ft"): UnitConversion("m", "ft", 3.28084),
        ("ft", "m"): UnitConversion("ft", "m", 0.3048),
        # Temperature
        ("C", "F"): UnitConversion("C", "F", 1.8, 32),  # F = C * 1.8 + 32
        ("F", "C"): UnitConversion("F", "C", 0.555556, -17.7778),  # C = (F - 32) / 1.8
        # Volume
        ("ml", "fl oz"): UnitConversion("ml", "fl oz", 0.033814),
        ("fl oz", "ml"): UnitConversion("fl oz", "ml", 29.5735),
        ("L", "gal"): UnitConversion("L", "gal", 0.264172),
        ("gal", "L"): UnitConversion("gal", "L", 3.78541),
    }

    # Measurement preferences by region
    REGIONAL_PREFERENCES = {
        "US": MeasurementSystem.US_CUSTOMARY,
        "GB": MeasurementSystem.IMPERIAL,
        "CA": MeasurementSystem.METRIC,
        "AU": MeasurementSystem.METRIC,
        "IN": MeasurementSystem.METRIC,
        "PK": MeasurementSystem.METRIC,
        "BD": MeasurementSystem.METRIC,
        "KE": MeasurementSystem.METRIC,
        "JO": MeasurementSystem.METRIC,
        "SY": MeasurementSystem.METRIC,
        "AF": MeasurementSystem.METRIC,
        "IQ": MeasurementSystem.METRIC,
    }

    def convert_unit(
        self, value: float, from_unit: str, to_unit: str
    ) -> Optional[float]:
        """Convert between measurement units."""
        if from_unit == to_unit:
            return value

        conversion = self.CONVERSIONS.get((from_unit, to_unit))
        if not conversion:
            logger.warning(f"No conversion found from {from_unit} to {to_unit}")
            return None

        # Apply conversion
        result = value * conversion.factor + conversion.offset

        # Round appropriately
        if to_unit in ["kg", "lb"]:
            return round(result, 1)
        elif to_unit in ["C", "F"]:
            return round(result, 1)
        elif to_unit in ["cm", "in"]:
            return round(result, 1)
        else:
            return round(result, 2)

    def format_measurement(
        self,
        value: float,
        unit: str,
        locale: str = "en_US",
        include_conversion: bool = False,
        target_system: Optional[MeasurementSystem] = None,
    ) -> str:
        """Format measurement with optional conversion."""
        from src.localization.number_formatter import number_formatter

        # Format primary value
        formatted = number_formatter.format_medical_value(value, unit, locale)

        if include_conversion:
            # Determine target unit
            target_unit = self._get_target_unit(unit, target_system)
            if target_unit and target_unit != unit:
                converted_value = self.convert_unit(value, unit, target_unit)
                if converted_value is not None:
                    converted_formatted = number_formatter.format_medical_value(
                        converted_value, target_unit, locale
                    )
                    formatted += f" ({converted_formatted})"

        return formatted

    def _get_target_unit(
        self, source_unit: str, target_system: Optional[MeasurementSystem]
    ) -> Optional[str]:
        """Get target unit for conversion based on measurement system."""
        if not target_system:
            return None

        # Unit mappings
        metric_to_imperial = {
            "kg": "lb",
            "cm": "in",
            "m": "ft",
            "C": "F",
            "ml": "fl oz",
            "L": "gal",
        }

        imperial_to_metric = {v: k for k, v in metric_to_imperial.items()}

        if target_system == MeasurementSystem.METRIC:
            return imperial_to_metric.get(source_unit)
        elif target_system in [
            MeasurementSystem.IMPERIAL,
            MeasurementSystem.US_CUSTOMARY,
        ]:
            return metric_to_imperial.get(source_unit)

        return None

    def get_vital_signs_display(
        self,
        temperature: float,
        weight: float,
        height: float,
        locale: str = "en_US",
        measurement_system: Optional[MeasurementSystem] = None,
    ) -> Dict[str, str]:
        """Format vital signs for display."""
        # Determine measurement system
        if not measurement_system:
            country = locale.split("_")[1] if "_" in locale else "US"
            measurement_system = self.REGIONAL_PREFERENCES.get(
                country, MeasurementSystem.METRIC
            )

        # Temperature
        if measurement_system == MeasurementSystem.METRIC:
            temp_display = self.format_measurement(temperature, "C", locale, True)
        else:
            temp_f = self.convert_unit(temperature, "C", "F")
            if temp_f is not None:
                temp_display = self.format_measurement(temp_f, "F", locale, True)
            else:
                temp_display = f"{temperature} °C"

        # Weight
        if measurement_system == MeasurementSystem.METRIC:
            weight_display = self.format_measurement(weight, "kg", locale, True)
        else:
            weight_lb = self.convert_unit(weight, "kg", "lb")
            if weight_lb is not None:
                weight_display = self.format_measurement(weight_lb, "lb", locale, True)
            else:
                weight_display = f"{weight} kg"

        # Height
        if measurement_system == MeasurementSystem.METRIC:
            height_display = self.format_measurement(height, "cm", locale, True)
        else:
            height_in = self.convert_unit(height, "cm", "in")
            if height_in is not None:
                # Convert to feet and inches
                feet = int(height_in // 12)
                inches = height_in % 12
                height_display = f"{feet}' {inches:.0f}\" ({height} cm)"
            else:
                height_display = f"{height} cm"

        return {
            "temperature": temp_display,
            "weight": weight_display,
            "height": height_display,
            "measurement_system": measurement_system.value,
        }


# Global instances
currency_manager = CurrencyManager()
unit_manager = MeasurementUnitManager()
