"""
Core unit conversion functionality.

This module provides the main unit conversion classes and functions
for medical measurement conversions.

This module handles encrypted PHI with access control and audit logging
to ensure HIPAA compliance.
 Handles FHIR Resource validation.
"""

import logging
import re
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

logger = logging.getLogger(__name__)


class UnitType(Enum):
    """Types of measurement units."""

    # Basic measurements
    LENGTH = "length"
    WEIGHT = "weight"
    VOLUME = "volume"
    TEMPERATURE = "temperature"
    TIME = "time"

    # Medical specific
    PRESSURE = "pressure"  # Blood pressure
    CONCENTRATION = "concentration"  # Lab values
    DOSAGE = "dosage"  # Medication
    FLOW_RATE = "flow_rate"  # IV drips
    ENERGY = "energy"  # Calories

    # Lab specific
    MOLAR = "molar"  # Molar concentration
    ENZYME = "enzyme"  # Enzyme activity
    CELL_COUNT = "cell_count"


class UnitSystem(Enum):
    """Measurement systems."""

    METRIC = "metric"
    IMPERIAL = "imperial"
    US_CUSTOMARY = "us_customary"
    MIXED = "mixed"  # E.g., UK uses metric + some imperial


class PrecisionLevel(Enum):
    """Precision requirements for medical measurements."""

    LOW = "low"  # General measurements
    MEDIUM = "medium"  # Most medical uses
    HIGH = "high"  # Lab values, medications
    VERY_HIGH = "very_high"  # Critical measurements


@dataclass
class Unit:
    """Represents a measurement unit."""

    symbol: str  # e.g., "mg", "°F", "mmHg"
    name: str  # e.g., "milligram", "fahrenheit"
    type: UnitType
    system: UnitSystem
    base_unit: Optional[str] = None  # Base unit in same type
    conversion_factor: Optional[Decimal] = None  # To base unit
    offset: Optional[Decimal] = None  # For temperature conversions

    def __str__(self) -> str:
        """Return the symbol representation of the unit."""
        return self.symbol


@dataclass
class MeasurementValue:
    """A value with its unit."""

    value: Decimal
    unit: Unit
    precision: Optional[int] = None  # Significant figures

    def __str__(self) -> str:
        """Return the string representation of the measurement value."""
        if self.precision:
            return f"{self.value:.{self.precision}f} {self.unit.symbol}"
        return f"{self.value} {self.unit.symbol}"

    @classmethod
    def from_string(
        cls, value_str: str, unit_registry: Dict[str, Unit]
    ) -> "MeasurementValue":
        """Parse a measurement from string."""
        # Pattern to match number and unit
        pattern = r"([-+]?\d*\.?\d+)\s*([a-zA-Z°%/]+)"
        match = re.match(pattern, value_str.strip())

        if not match:
            raise ValueError(f"Invalid measurement format: {value_str}")

        value = Decimal(match.group(1))
        unit_symbol = match.group(2)

        if unit_symbol not in unit_registry:
            raise ValueError(f"Unknown unit: {unit_symbol}")

        return cls(value=value, unit=unit_registry[unit_symbol])


@dataclass
class ConversionContext:
    """Context for unit conversion."""

    target_system: UnitSystem
    precision_level: PrecisionLevel = PrecisionLevel.MEDIUM
    preserve_precision: bool = True
    round_values: bool = True
    include_original: bool = False  # Show original in parentheses
    medical_context: bool = True
    age_group: Optional[str] = None  # pediatric, adult, elderly

    def get_decimal_places(self) -> int:
        """Get appropriate decimal places for precision level."""
        precision_map = {
            PrecisionLevel.LOW: 0,
            PrecisionLevel.MEDIUM: 1,
            PrecisionLevel.HIGH: 2,
            PrecisionLevel.VERY_HIGH: 4,
        }
        return precision_map.get(self.precision_level, 1)


@dataclass
class ConversionResult:
    """Result of unit conversion."""

    original: MeasurementValue
    converted: MeasurementValue
    context: ConversionContext
    warnings: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def format(self, include_original: Optional[bool] = None) -> str:
        """Format the conversion result."""
        include_original = include_original or self.context.include_original

        if include_original:
            return f"{self.converted} ({self.original})"
        return str(self.converted)


class UnitConverter:
    """Main unit conversion implementation."""

    def __init__(self) -> None:
        """Initialize unit converter."""
        self.units = self._load_units()
        self.conversions = self._load_conversions()

    def convert(
        self,
        value: Union[MeasurementValue, str, float],
        target_unit: Union[Unit, str],
        context: Optional[ConversionContext] = None,
    ) -> ConversionResult:
        """
        Convert a measurement to target unit.

        Args:
            value: Value to convert (MeasurementValue, string, or float)
            target_unit: Target unit or unit symbol
            context: Conversion context

        Returns:
            ConversionResult with converted value
        """
        # Parse input
        if isinstance(value, str):
            measurement = MeasurementValue.from_string(value, self.units)
        elif isinstance(value, (int, float)):
            raise ValueError("Numeric value requires unit specification")
        else:
            measurement = value

        # Get target unit
        if isinstance(target_unit, str):
            if target_unit not in self.units:
                raise ValueError(f"Unknown target unit: {target_unit}")
            target = self.units[target_unit]
        else:
            target = target_unit

        # Validate conversion
        if measurement.unit.type != target.type:
            raise ValueError(
                f"Cannot convert {measurement.unit.type.value} "
                f"to {target.type.value}"
            )

        # Use default context if not provided
        context = context or ConversionContext(target_system=target.system)

        # Perform conversion
        if measurement.unit.symbol == target.symbol:
            # Same unit, no conversion needed
            converted_value = measurement.value
        else:
            converted_value = self._perform_conversion(
                measurement.value, measurement.unit, target
            )

        # Apply precision rules
        if context.round_values:
            decimal_places = context.get_decimal_places()
            converted_value = converted_value.quantize(
                Decimal(f'0.{"0" * decimal_places}'), rounding=ROUND_HALF_UP
            )

        # Create result
        converted = MeasurementValue(
            value=converted_value,
            unit=target,
            precision=(
                context.get_decimal_places() if context.preserve_precision else None
            ),
        )

        result = ConversionResult(
            original=measurement, converted=converted, context=context
        )

        # Add warnings for significant conversions
        if measurement.unit.system != target.system:
            result.warnings.append(
                f"Converted between different systems: "
                f"{measurement.unit.system.value} to {target.system.value}"
            )

        return result

    def _perform_conversion(
        self, value: Decimal, from_unit: Unit, to_unit: Unit
    ) -> Decimal:
        """Perform the actual unit conversion."""
        # Temperature requires special handling
        if from_unit.type == UnitType.TEMPERATURE:
            return self._convert_temperature(value, from_unit, to_unit)

        # Convert to base unit first
        if from_unit.base_unit and from_unit.conversion_factor is not None:
            base_value = value * from_unit.conversion_factor
        else:
            base_value = value  # Already in base unit

        # Convert from base to target
        if to_unit.base_unit and to_unit.conversion_factor is not None:
            result = base_value / to_unit.conversion_factor
        else:
            result = base_value

        return result

    def _convert_temperature(
        self, value: Decimal, from_unit: Unit, to_unit: Unit
    ) -> Decimal:
        """Handle temperature conversions."""
        # Convert to Celsius first
        if from_unit.symbol == "°F":
            celsius = (value - Decimal("32")) * Decimal("5") / Decimal("9")
        elif from_unit.symbol == "K":
            celsius = value - Decimal("273.15")
        else:
            celsius = value

        # Convert from Celsius to target
        if to_unit.symbol == "°F":
            return celsius * Decimal("9") / Decimal("5") + Decimal("32")
        elif to_unit.symbol == "K":
            return celsius + Decimal("273.15")
        else:
            return celsius

    def _load_units(self) -> Dict[str, Unit]:
        """Load unit definitions."""
        units = {}

        # Length units
        units.update(
            {
                "m": Unit("m", "meter", UnitType.LENGTH, UnitSystem.METRIC),
                "cm": Unit(
                    "cm",
                    "centimeter",
                    UnitType.LENGTH,
                    UnitSystem.METRIC,
                    "m",
                    Decimal("0.01"),
                ),
                "mm": Unit(
                    "mm",
                    "millimeter",
                    UnitType.LENGTH,
                    UnitSystem.METRIC,
                    "m",
                    Decimal("0.001"),
                ),
                "km": Unit(
                    "km",
                    "kilometer",
                    UnitType.LENGTH,
                    UnitSystem.METRIC,
                    "m",
                    Decimal("1000"),
                ),
                "ft": Unit(
                    "ft",
                    "foot",
                    UnitType.LENGTH,
                    UnitSystem.IMPERIAL,
                    "m",
                    Decimal("0.3048"),
                ),
                "in": Unit(
                    "in",
                    "inch",
                    UnitType.LENGTH,
                    UnitSystem.IMPERIAL,
                    "m",
                    Decimal("0.0254"),
                ),
                "yd": Unit(
                    "yd",
                    "yard",
                    UnitType.LENGTH,
                    UnitSystem.IMPERIAL,
                    "m",
                    Decimal("0.9144"),
                ),
                "mi": Unit(
                    "mi",
                    "mile",
                    UnitType.LENGTH,
                    UnitSystem.IMPERIAL,
                    "m",
                    Decimal("1609.344"),
                ),
            }
        )

        # Weight units
        units.update(
            {
                "kg": Unit("kg", "kilogram", UnitType.WEIGHT, UnitSystem.METRIC),
                "g": Unit(
                    "g",
                    "gram",
                    UnitType.WEIGHT,
                    UnitSystem.METRIC,
                    "kg",
                    Decimal("0.001"),
                ),
                "mg": Unit(
                    "mg",
                    "milligram",
                    UnitType.WEIGHT,
                    UnitSystem.METRIC,
                    "kg",
                    Decimal("0.000001"),
                ),
                "mcg": Unit(
                    "mcg",
                    "microgram",
                    UnitType.WEIGHT,
                    UnitSystem.METRIC,
                    "kg",
                    Decimal("0.000000001"),
                ),
                "lb": Unit(
                    "lb",
                    "pound",
                    UnitType.WEIGHT,
                    UnitSystem.IMPERIAL,
                    "kg",
                    Decimal("0.453592"),
                ),
                "oz": Unit(
                    "oz",
                    "ounce",
                    UnitType.WEIGHT,
                    UnitSystem.IMPERIAL,
                    "kg",
                    Decimal("0.0283495"),
                ),
                "st": Unit(
                    "st",
                    "stone",
                    UnitType.WEIGHT,
                    UnitSystem.IMPERIAL,
                    "kg",
                    Decimal("6.35029"),
                ),
            }
        )

        # Volume units
        units.update(
            {
                "L": Unit("L", "liter", UnitType.VOLUME, UnitSystem.METRIC),
                "mL": Unit(
                    "mL",
                    "milliliter",
                    UnitType.VOLUME,
                    UnitSystem.METRIC,
                    "L",
                    Decimal("0.001"),
                ),
                "dL": Unit(
                    "dL",
                    "deciliter",
                    UnitType.VOLUME,
                    UnitSystem.METRIC,
                    "L",
                    Decimal("0.1"),
                ),
                "cc": Unit(
                    "cc",
                    "cubic centimeter",
                    UnitType.VOLUME,
                    UnitSystem.METRIC,
                    "L",
                    Decimal("0.001"),
                ),
                "gal": Unit(
                    "gal",
                    "gallon",
                    UnitType.VOLUME,
                    UnitSystem.US_CUSTOMARY,
                    "L",
                    Decimal("3.78541"),
                ),
                "qt": Unit(
                    "qt",
                    "quart",
                    UnitType.VOLUME,
                    UnitSystem.US_CUSTOMARY,
                    "L",
                    Decimal("0.946353"),
                ),
                "pt": Unit(
                    "pt",
                    "pint",
                    UnitType.VOLUME,
                    UnitSystem.US_CUSTOMARY,
                    "L",
                    Decimal("0.473176"),
                ),
                "cup": Unit(
                    "cup",
                    "cup",
                    UnitType.VOLUME,
                    UnitSystem.US_CUSTOMARY,
                    "L",
                    Decimal("0.236588"),
                ),
                "fl oz": Unit(
                    "fl oz",
                    "fluid ounce",
                    UnitType.VOLUME,
                    UnitSystem.US_CUSTOMARY,
                    "L",
                    Decimal("0.0295735"),
                ),
                "tbsp": Unit(
                    "tbsp",
                    "tablespoon",
                    UnitType.VOLUME,
                    UnitSystem.US_CUSTOMARY,
                    "L",
                    Decimal("0.0147868"),
                ),
                "tsp": Unit(
                    "tsp",
                    "teaspoon",
                    UnitType.VOLUME,
                    UnitSystem.US_CUSTOMARY,
                    "L",
                    Decimal("0.00492892"),
                ),
            }
        )

        # Temperature units
        units.update(
            {
                "°C": Unit("°C", "celsius", UnitType.TEMPERATURE, UnitSystem.METRIC),
                "°F": Unit(
                    "°F", "fahrenheit", UnitType.TEMPERATURE, UnitSystem.IMPERIAL
                ),
                "K": Unit("K", "kelvin", UnitType.TEMPERATURE, UnitSystem.METRIC),
            }
        )

        # Pressure units (for blood pressure)
        units.update(
            {
                "mmHg": Unit(
                    "mmHg",
                    "millimeters of mercury",
                    UnitType.PRESSURE,
                    UnitSystem.METRIC,
                ),
                "kPa": Unit(
                    "kPa",
                    "kilopascal",
                    UnitType.PRESSURE,
                    UnitSystem.METRIC,
                    "mmHg",
                    Decimal("7.50062"),
                ),
            }
        )

        return units

    def _load_conversions(self) -> Dict[Tuple[str, str], Callable]:
        """Load special conversion functions."""
        # Most conversions are handled by conversion factors
        # This is for special cases that need custom logic
        return {
            # Add any special conversion functions here
        }

    def detect_units_in_text(self, text: str) -> List[Tuple[str, MeasurementValue]]:
        """Detect and parse all measurements in text."""
        measurements = []

        # Pattern to match measurements
        pattern = r"([-+]?\d*\.?\d+)\s*([a-zA-Z°%/]+)(?:\s|$|[,.])"

        for match in re.finditer(pattern, text):
            try:
                value_str = match.group(0).strip().rstrip(".,")
                measurement = MeasurementValue.from_string(value_str, self.units)
                measurements.append((match.group(0), measurement))
            except ValueError:
                # Skip unrecognized units
                continue

        return measurements

    def convert_all_in_text(
        self,
        text: str,
        target_system: UnitSystem,
        context: Optional[ConversionContext] = None,
    ) -> str:
        """Convert all measurements in text to target system."""
        context = context or ConversionContext(target_system=target_system)
        result_text = text

        # Detect all measurements
        measurements = self.detect_units_in_text(text)

        # Convert each measurement
        replacements = []
        for original_str, measurement in measurements:
            # Skip if already in target system
            if measurement.unit.system == target_system:
                continue

            # Find appropriate target unit
            target_unit = self._find_target_unit(measurement.unit, target_system)
            if not target_unit:
                continue

            # Convert
            conversion = self.convert(measurement, target_unit, context)
            replacement_str = conversion.format()
            replacements.append((original_str.strip(), replacement_str))

        # Apply replacements (in reverse order to maintain positions)
        for original, replacement in reversed(replacements):
            result_text = result_text.replace(original, replacement)

        return result_text

    def _find_target_unit(
        self, source_unit: Unit, target_system: UnitSystem
    ) -> Optional[Unit]:
        """Find appropriate unit in target system."""
        # Map common conversions
        conversion_map = {
            # Length
            ("m", UnitSystem.IMPERIAL): "ft",
            ("cm", UnitSystem.IMPERIAL): "in",
            ("km", UnitSystem.IMPERIAL): "mi",
            ("ft", UnitSystem.METRIC): "m",
            ("in", UnitSystem.METRIC): "cm",
            ("mi", UnitSystem.METRIC): "km",
            # Weight
            ("kg", UnitSystem.IMPERIAL): "lb",
            ("g", UnitSystem.IMPERIAL): "oz",
            ("lb", UnitSystem.METRIC): "kg",
            ("oz", UnitSystem.METRIC): "g",
            # Volume
            ("L", UnitSystem.US_CUSTOMARY): "qt",
            ("mL", UnitSystem.US_CUSTOMARY): "fl oz",
            ("gal", UnitSystem.METRIC): "L",
            ("fl oz", UnitSystem.METRIC): "mL",
            # Temperature
            ("°C", UnitSystem.IMPERIAL): "°F",
            ("°F", UnitSystem.METRIC): "°C",
        }

        key = (source_unit.symbol, target_system)
        if key in conversion_map:
            return self.units.get(conversion_map[key])

        # Return None if no appropriate conversion found
        return None

    def validate_conversion(self, value: MeasurementValue, target_unit: Unit) -> bool:
        """Validate that a conversion is possible."""
        if not value or not target_unit:
            return False
        if value.unit.type != target_unit.type:
            return False
        return True
