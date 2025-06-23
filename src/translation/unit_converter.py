"""
Medical Unit Conversions.

This module handles medical unit conversions between different measurement systems
(metric, imperial) and provides localized unit display for different regions.
"""

import re
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from enum import Enum
from typing import Dict, List, Optional, Tuple

from src.utils.logging import get_logger

logger = get_logger(__name__)


class UnitCategory(str, Enum):
    """Categories of medical units."""

    WEIGHT = "weight"
    HEIGHT = "height"
    TEMPERATURE = "temperature"
    BLOOD_PRESSURE = "blood_pressure"
    VOLUME = "volume"
    CONCENTRATION = "concentration"
    DOSAGE = "dosage"
    TIME = "time"
    GLUCOSE = "glucose"


class UnitSystem(str, Enum):
    """Measurement systems."""

    METRIC = "metric"
    IMPERIAL = "imperial"
    US_CUSTOMARY = "us_customary"


@dataclass
class MedicalUnit:
    """Medical unit with conversion factors."""

    name: str
    symbol: str
    category: UnitCategory
    system: UnitSystem
    base_unit_factor: Optional[
        float
    ]  # Conversion to base unit, None for special conversions
    translations: Dict[str, str]  # Symbol translations


class UnitConverter:
    """Handles medical unit conversions and localization."""

    # Define medical units
    MEDICAL_UNITS = {
        # Weight units
        "kilogram": MedicalUnit(
            name="kilogram",
            symbol="kg",
            category=UnitCategory.WEIGHT,
            system=UnitSystem.METRIC,
            base_unit_factor=1.0,  # Base unit for weight
            translations={
                "ar": "كغ",
                "fr": "kg",
                "es": "kg",
                "sw": "kg",
                "fa": "کیلوگرم",
                "ps": "کیلوګرام",
                "ur": "کلوگرام",
                "bn": "কেজি",
                "hi": "किलो",
            },
        ),
        "gram": MedicalUnit(
            name="gram",
            symbol="g",
            category=UnitCategory.WEIGHT,
            system=UnitSystem.METRIC,
            base_unit_factor=0.001,
            translations={
                "ar": "غ",
                "fr": "g",
                "es": "g",
                "sw": "g",
                "fa": "گرم",
                "ps": "ګرام",
                "ur": "گرام",
                "bn": "গ্রাম",
                "hi": "ग्राम",
            },
        ),
        "pound": MedicalUnit(
            name="pound",
            symbol="lb",
            category=UnitCategory.WEIGHT,
            system=UnitSystem.IMPERIAL,
            base_unit_factor=0.453592,
            translations={
                "ar": "رطل",
                "fr": "lb",
                "es": "lb",
                "sw": "ratili",
                "fa": "پوند",
                "ps": "پاونډ",
                "ur": "پاؤنڈ",
                "bn": "পাউন্ড",
                "hi": "पाउंड",
            },
        ),
        "ounce": MedicalUnit(
            name="ounce",
            symbol="oz",
            category=UnitCategory.WEIGHT,
            system=UnitSystem.IMPERIAL,
            base_unit_factor=0.0283495,
            translations={
                "ar": "أونصة",
                "fr": "oz",
                "es": "oz",
                "sw": "aunsi",
                "fa": "اونس",
                "ps": "اونس",
                "ur": "اونس",
                "bn": "আউন্স",
                "hi": "औंस",
            },
        ),
        # Height/Length units
        "meter": MedicalUnit(
            name="meter",
            symbol="m",
            category=UnitCategory.HEIGHT,
            system=UnitSystem.METRIC,
            base_unit_factor=1.0,  # Base unit for height
            translations={
                "ar": "م",
                "fr": "m",
                "es": "m",
                "sw": "m",
                "fa": "متر",
                "ps": "متر",
                "ur": "میٹر",
                "bn": "মিটার",
                "hi": "मीटर",
            },
        ),
        "centimeter": MedicalUnit(
            name="centimeter",
            symbol="cm",
            category=UnitCategory.HEIGHT,
            system=UnitSystem.METRIC,
            base_unit_factor=0.01,
            translations={
                "ar": "سم",
                "fr": "cm",
                "es": "cm",
                "sw": "cm",
                "fa": "سانتیمتر",
                "ps": "سانتي متر",
                "ur": "سینٹی میٹر",
                "bn": "সেমি",
                "hi": "सेमी",
            },
        ),
        "foot": MedicalUnit(
            name="foot",
            symbol="ft",
            category=UnitCategory.HEIGHT,
            system=UnitSystem.IMPERIAL,
            base_unit_factor=0.3048,
            translations={
                "ar": "قدم",
                "fr": "pi",
                "es": "pie",
                "sw": "futi",
                "fa": "فوت",
                "ps": "فټ",
                "ur": "فٹ",
                "bn": "ফুট",
                "hi": "फुट",
            },
        ),
        "inch": MedicalUnit(
            name="inch",
            symbol="in",
            category=UnitCategory.HEIGHT,
            system=UnitSystem.IMPERIAL,
            base_unit_factor=0.0254,
            translations={
                "ar": "بوصة",
                "fr": "po",
                "es": "pulgada",
                "sw": "inchi",
                "fa": "اینچ",
                "ps": "انچ",
                "ur": "انچ",
                "bn": "ইঞ্চি",
                "hi": "इंच",
            },
        ),
        # Temperature units
        "celsius": MedicalUnit(
            name="celsius",
            symbol="°C",
            category=UnitCategory.TEMPERATURE,
            system=UnitSystem.METRIC,
            base_unit_factor=1.0,  # Base unit for temperature
            translations={
                "ar": "°م",
                "fr": "°C",
                "es": "°C",
                "sw": "°C",
                "fa": "°س",
                "ps": "°س",
                "ur": "°س",
                "bn": "°সে",
                "hi": "°से",
            },
        ),
        "fahrenheit": MedicalUnit(
            name="fahrenheit",
            symbol="°F",
            category=UnitCategory.TEMPERATURE,
            system=UnitSystem.IMPERIAL,
            base_unit_factor=None,  # Special conversion
            translations={
                "ar": "°ف",
                "fr": "°F",
                "es": "°F",
                "sw": "°F",
                "fa": "°ف",
                "ps": "°ف",
                "ur": "°ف",
                "bn": "°ফা",
                "hi": "°फा",
            },
        ),
        # Volume units
        "liter": MedicalUnit(
            name="liter",
            symbol="L",
            category=UnitCategory.VOLUME,
            system=UnitSystem.METRIC,
            base_unit_factor=1.0,  # Base unit for volume
            translations={
                "ar": "ل",
                "fr": "L",
                "es": "L",
                "sw": "L",
                "fa": "لیتر",
                "ps": "لیټر",
                "ur": "لیٹر",
                "bn": "লিটার",
                "hi": "लीटर",
            },
        ),
        "milliliter": MedicalUnit(
            name="milliliter",
            symbol="mL",
            category=UnitCategory.VOLUME,
            system=UnitSystem.METRIC,
            base_unit_factor=0.001,
            translations={
                "ar": "مل",
                "fr": "mL",
                "es": "mL",
                "sw": "mL",
                "fa": "میلی‌لیتر",
                "ps": "ملي لیټر",
                "ur": "ملی لیٹر",
                "bn": "মিলি",
                "hi": "मिली",
            },
        ),
        # Glucose units
        "mg_dl": MedicalUnit(
            name="milligrams per deciliter",
            symbol="mg/dL",
            category=UnitCategory.GLUCOSE,
            system=UnitSystem.US_CUSTOMARY,
            base_unit_factor=1.0,  # Base unit for glucose
            translations={
                "ar": "مغ/دل",
                "fr": "mg/dL",
                "es": "mg/dL",
                "sw": "mg/dL",
                "fa": "mg/dL",
                "ps": "mg/dL",
                "ur": "mg/dL",
                "bn": "mg/dL",
                "hi": "mg/dL",
            },
        ),
        "mmol_l": MedicalUnit(
            name="millimoles per liter",
            symbol="mmol/L",
            category=UnitCategory.GLUCOSE,
            system=UnitSystem.METRIC,
            base_unit_factor=18.0182,  # 1 mmol/L = 18.0182 mg/dL
            translations={
                "ar": "ممول/ل",
                "fr": "mmol/L",
                "es": "mmol/L",
                "sw": "mmol/L",
                "fa": "mmol/L",
                "ps": "mmol/L",
                "ur": "mmol/L",
                "bn": "mmol/L",
                "hi": "mmol/L",
            },
        ),
    }
    # Regional unit preferences
    REGIONAL_PREFERENCES = {
        "US": {
            UnitCategory.WEIGHT: "pound",
            UnitCategory.HEIGHT: "foot",
            UnitCategory.TEMPERATURE: "fahrenheit",
            UnitCategory.GLUCOSE: "mg_dl",
        },
        "UK": {
            UnitCategory.WEIGHT: "kilogram",
            UnitCategory.HEIGHT: "meter",
            UnitCategory.TEMPERATURE: "celsius",
            UnitCategory.GLUCOSE: "mmol_l",
        },
        "EU": {
            UnitCategory.WEIGHT: "kilogram",
            UnitCategory.HEIGHT: "meter",
            UnitCategory.TEMPERATURE: "celsius",
            UnitCategory.GLUCOSE: "mmol_l",
        },
        "MENA": {  # Middle East & North Africa
            UnitCategory.WEIGHT: "kilogram",
            UnitCategory.HEIGHT: "meter",
            UnitCategory.TEMPERATURE: "celsius",
            UnitCategory.GLUCOSE: "mg_dl",
        },
        "AFRICA": {
            UnitCategory.WEIGHT: "kilogram",
            UnitCategory.HEIGHT: "meter",
            UnitCategory.TEMPERATURE: "celsius",
            UnitCategory.GLUCOSE: "mmol_l",
        },
        "ASIA": {
            UnitCategory.WEIGHT: "kilogram",
            UnitCategory.HEIGHT: "meter",
            UnitCategory.TEMPERATURE: "celsius",
            UnitCategory.GLUCOSE: "mg_dl",
        },
    }

    def __init__(self) -> None:
        """Initialize unit converter."""
        self.units = self.MEDICAL_UNITS.copy()
        self._build_conversion_matrix()

    def _build_conversion_matrix(self) -> None:
        """Build conversion lookup tables."""
        self._category_units: Dict[UnitCategory, Dict[str, MedicalUnit]] = {}
        for unit_key, unit in self.units.items():
            if unit.category not in self._category_units:
                self._category_units[unit.category] = {}
            self._category_units[unit.category][unit_key] = unit

    def convert(self, value: float, from_unit: str, to_unit: str) -> float:
        """
        Convert between medical units.

        Args:
            value: Numeric value to convert
            from_unit: Source unit key
            to_unit: Target unit key

        Returns:
            Converted value

        Raises:
            ValueError: If units are incompatible
        """
        if from_unit == to_unit:
            return value

        from_unit_obj = self.units.get(from_unit)
        to_unit_obj = self.units.get(to_unit)

        if not from_unit_obj or not to_unit_obj:
            raise ValueError(f"Unknown unit: {from_unit or to_unit}")

        if from_unit_obj.category != to_unit_obj.category:
            raise ValueError(
                f"Cannot convert between {from_unit_obj.category} and {to_unit_obj.category}"
            )

        # Special handling for temperature
        if from_unit_obj.category == UnitCategory.TEMPERATURE:
            return self._convert_temperature(value, from_unit, to_unit)

        # Convert to base unit first, then to target unit
        if (
            from_unit_obj.base_unit_factor is None
            or to_unit_obj.base_unit_factor is None
        ):
            raise ValueError(f"Cannot convert between {from_unit} and {to_unit}")
        base_value = value * from_unit_obj.base_unit_factor
        converted_value = base_value / to_unit_obj.base_unit_factor

        # Round to appropriate precision
        return float(
            Decimal(str(converted_value)).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
        )

    def _convert_temperature(self, value: float, from_unit: str, to_unit: str) -> float:
        """Convert temperature units."""
        if from_unit == "celsius" and to_unit == "fahrenheit":
            return round((value * 9 / 5) + 32, 1)
        elif from_unit == "fahrenheit" and to_unit == "celsius":
            return round((value - 32) * 5 / 9, 1)
        else:
            return value

    def format_value(
        self,
        value: float,
        unit: str,
        language: str = "en",
        precision: Optional[int] = None,
    ) -> str:
        """
        Format a value with localized unit symbol.

        Args:
            value: Numeric value
            unit: Unit key
            language: Target language
            precision: Decimal places (auto-determined if None)

        Returns:
            Formatted string with localized unit
        """
        unit_obj = self.units.get(unit)
        if not unit_obj:
            return f"{value} {unit}"

        # Get localized symbol
        if language == "en":
            symbol = unit_obj.symbol
        else:
            symbol = unit_obj.translations.get(language, unit_obj.symbol)

        # Determine precision if not specified
        if precision is None:
            if unit_obj.category == UnitCategory.WEIGHT:
                precision = 1 if value >= 1 else 2
            elif unit_obj.category == UnitCategory.HEIGHT:
                precision = 0 if unit in ["foot", "inch"] else 1
            elif unit_obj.category == UnitCategory.TEMPERATURE:
                precision = 1
            else:
                precision = 1

        # Format based on language preferences
        if language in ["ar", "fa", "ur"]:
            # RTL languages may prefer different formatting
            return f"{symbol} {value:.{precision}f}"
        else:
            return f"{value:.{precision}f} {symbol}"

    def convert_height_to_feet_inches(self, height_cm: float) -> Tuple[int, float]:
        """Convert height in cm to feet and inches."""
        total_inches = self.convert(height_cm, "centimeter", "inch")
        feet = int(total_inches // 12)
        inches = total_inches % 12
        return feet, round(inches, 1)

    def format_height_imperial(self, height_cm: float, language: str = "en") -> str:
        """Format height in feet and inches with localization."""
        feet, inches = self.convert_height_to_feet_inches(height_cm)

        foot_unit = self.units["foot"]
        inch_unit = self.units["inch"]

        if language == "en":
            return f"{feet}'{inches}\""
        else:
            foot_symbol = foot_unit.translations.get(language, "ft")
            inch_symbol = inch_unit.translations.get(language, "in")
            return f"{feet} {foot_symbol} {inches} {inch_symbol}"

    def get_preferred_unit(self, category: UnitCategory, region: str = "EU") -> str:
        """Get preferred unit for a category in a region."""
        regional_prefs = self.REGIONAL_PREFERENCES.get(
            region, self.REGIONAL_PREFERENCES["EU"]
        )
        default_unit = list(self._category_units[category].keys())[0]
        return str(regional_prefs.get(category, default_unit))

    def convert_to_preferred(
        self, value: float, current_unit: str, region: str = "EU"
    ) -> Tuple[float, str]:
        """Convert to regionally preferred unit."""
        unit_obj = self.units.get(current_unit)
        if not unit_obj:
            return value, current_unit

        preferred_unit = self.get_preferred_unit(unit_obj.category, region)

        if current_unit == preferred_unit:
            return value, current_unit

        converted_value = self.convert(value, current_unit, preferred_unit)
        return converted_value, preferred_unit

    def get_units_for_category(self, category: UnitCategory) -> List[str]:
        """Get all units available for a category."""
        return list(self._category_units.get(category, {}).keys())

    def parse_value_with_unit(
        self, text: str, expected_category: Optional[UnitCategory] = None
    ) -> Optional[Tuple[float, str]]:
        """
        Parse a value with unit from text.

        Args:
            text: Text containing value and unit
            expected_category: Expected unit category

        Returns:
            Tuple of (value, unit_key) or None
        """
        # Try to extract number and unit
        pattern = r"([\d.]+)\s*([^\s]+)"
        match = re.match(pattern, text.strip())

        if not match:
            return None

        try:
            value = float(match.group(1))
            unit_text = match.group(2).lower()

            # Find matching unit
            for unit_key, unit in self.units.items():
                if expected_category and unit.category != expected_category:
                    continue

                if (
                    unit_text == unit.symbol.lower()
                    or unit_text == unit.name.lower()
                    or unit_text in [t.lower() for t in unit.translations.values()]
                ):
                    return value, unit_key

            return None

        except ValueError:
            return None

    def get_conversion_formula(
        self, from_unit: str, to_unit: str, language: str = "en"
    ) -> str:
        """Get human-readable conversion formula."""
        from_unit_obj = self.units.get(from_unit)
        to_unit_obj = self.units.get(to_unit)

        if not from_unit_obj or not to_unit_obj:
            return ""

        if from_unit_obj.category != to_unit_obj.category:
            return ""

        # Special case for temperature
        if from_unit_obj.category == UnitCategory.TEMPERATURE:
            if from_unit == "celsius" and to_unit == "fahrenheit":
                return "°F = (°C × 9/5) + 32"
            elif from_unit == "fahrenheit" and to_unit == "celsius":
                return "°C = (°F - 32) × 5/9"

        # Calculate conversion factor
        if (
            from_unit_obj.base_unit_factor is None
            or to_unit_obj.base_unit_factor is None
        ):
            raise ValueError(
                f"Cannot get conversion formula for {from_unit} and {to_unit}"
            )
        factor = from_unit_obj.base_unit_factor / to_unit_obj.base_unit_factor

        from_symbol = from_unit_obj.translations.get(language, from_unit_obj.symbol)
        to_symbol = to_unit_obj.translations.get(language, to_unit_obj.symbol)

        return f"1 {from_symbol} = {factor:.4f} {to_symbol}"


# Global instance
unit_converter = UnitConverter()
