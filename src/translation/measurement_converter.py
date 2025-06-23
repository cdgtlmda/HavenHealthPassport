"""Measurement conversion module for medical data.

This module handles conversion between different measurement systems used
in healthcare contexts, ensuring accuracy for medical applications.
"""

import re
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from enum import Enum
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple, Union

from src.healthcare.hipaa_access_control import (
    AccessLevel,
    audit_phi_access,
    require_phi_access,
)
from src.utils.encryption import EncryptionService
from src.utils.logging import get_logger

# FHIR Resource typing imports
if TYPE_CHECKING:
    pass

logger = get_logger(__name__)


class MeasurementSystem(str, Enum):
    """Measurement systems used globally."""

    METRIC = "metric"
    IMPERIAL = "imperial"
    US_CUSTOMARY = "us_customary"


class MeasurementType(str, Enum):
    """Types of measurements in healthcare."""

    # Vital signs
    TEMPERATURE = "temperature"
    BLOOD_PRESSURE = "blood_pressure"
    HEART_RATE = "heart_rate"
    RESPIRATORY_RATE = "respiratory_rate"
    OXYGEN_SATURATION = "oxygen_saturation"

    # Body measurements
    HEIGHT = "height"
    WEIGHT = "weight"
    BMI = "bmi"
    HEAD_CIRCUMFERENCE = "head_circumference"
    WAIST_CIRCUMFERENCE = "waist_circumference"

    # Medication dosages
    LIQUID_VOLUME = "liquid_volume"
    MASS_DOSAGE = "mass_dosage"
    CONCENTRATION = "concentration"
    INFUSION_RATE = "infusion_rate"

    # Lab values
    GLUCOSE = "glucose"
    HEMOGLOBIN = "hemoglobin"
    CHOLESTEROL = "cholesterol"
    CREATININE = "creatinine"

    # Other
    DISTANCE = "distance"
    TIME = "time"
    FREQUENCY = "frequency"


@dataclass
class MeasurementUnit:
    """Represents a measurement unit."""

    symbol: str
    name: str
    system: MeasurementSystem
    type: MeasurementType
    conversion_factor: Decimal  # To base unit
    base_unit: Optional[str] = None


@dataclass
class ConversionResult:
    """Result of a measurement conversion."""

    value: Decimal
    unit: str
    formatted: str
    precision: int
    warnings: List[str]

    def to_fhir_quantity(self) -> Dict[str, Any]:
        """Convert to FHIR Quantity representation."""
        return {
            "value": float(self.value),
            "unit": self.unit,
            "system": "http://unitsofmeasure.org",
            "code": self.unit,
        }


class MeasurementConverter:
    """Handles conversion between different measurement systems."""

    # FHIR LOINC codes for common measurements
    FHIR_LOINC_CODES = {
        MeasurementType.TEMPERATURE: "8310-5",  # Body temperature
        MeasurementType.BLOOD_PRESSURE: "85354-9",  # Blood pressure panel
        MeasurementType.HEART_RATE: "8867-4",  # Heart rate
        MeasurementType.RESPIRATORY_RATE: "9279-1",  # Respiratory rate
        MeasurementType.OXYGEN_SATURATION: "2708-6",  # Oxygen saturation
        MeasurementType.HEIGHT: "8302-2",  # Body height
        MeasurementType.WEIGHT: "29463-7",  # Body weight
        MeasurementType.BMI: "39156-5",  # Body mass index
        MeasurementType.HEAD_CIRCUMFERENCE: "9843-4",  # Head circumference
        MeasurementType.WAIST_CIRCUMFERENCE: "8280-0",  # Waist circumference
        MeasurementType.GLUCOSE: "2339-0",  # Glucose
        MeasurementType.HEMOGLOBIN: "718-7",  # Hemoglobin
        MeasurementType.CHOLESTEROL: "2093-3",  # Cholesterol
        MeasurementType.CREATININE: "2160-0",  # Creatinine
    }

    def __init__(self) -> None:
        """Initialize the measurement converter."""
        self._encryption_service = EncryptionService()
        self._unit_aliases = self._build_unit_aliases()
        self._conversion_cache: Dict[str, Any] = {}

    # Define measurement units
    UNITS = {
        # Temperature
        "celsius": MeasurementUnit(
            symbol="°C",
            name="Celsius",
            system=MeasurementSystem.METRIC,
            type=MeasurementType.TEMPERATURE,
            conversion_factor=Decimal("1.0"),
        ),
        "fahrenheit": MeasurementUnit(
            symbol="°F",
            name="Fahrenheit",
            system=MeasurementSystem.IMPERIAL,
            type=MeasurementType.TEMPERATURE,
            conversion_factor=Decimal("1.0"),
        ),
        # Weight
        "kg": MeasurementUnit(
            symbol="kg",
            name="kilogram",
            system=MeasurementSystem.METRIC,
            type=MeasurementType.WEIGHT,
            conversion_factor=Decimal("1.0"),
        ),
        "g": MeasurementUnit(
            symbol="g",
            name="gram",
            system=MeasurementSystem.METRIC,
            type=MeasurementType.WEIGHT,
            conversion_factor=Decimal("0.001"),
            base_unit="kg",
        ),
        "mg": MeasurementUnit(
            symbol="mg",
            name="milligram",
            system=MeasurementSystem.METRIC,
            type=MeasurementType.WEIGHT,
            conversion_factor=Decimal("0.000001"),
            base_unit="kg",
        ),
        "mcg": MeasurementUnit(
            symbol="μg",
            name="microgram",
            system=MeasurementSystem.METRIC,
            type=MeasurementType.WEIGHT,
            conversion_factor=Decimal("0.000000001"),
            base_unit="kg",
        ),
        "lb": MeasurementUnit(
            symbol="lb",
            name="pound",
            system=MeasurementSystem.IMPERIAL,
            type=MeasurementType.WEIGHT,
            conversion_factor=Decimal("0.453592"),
            base_unit="kg",
        ),
        "oz": MeasurementUnit(
            symbol="oz",
            name="ounce",
            system=MeasurementSystem.IMPERIAL,
            type=MeasurementType.WEIGHT,
            conversion_factor=Decimal("0.0283495"),
            base_unit="kg",
        ),
        # Height/Length
        "m": MeasurementUnit(
            symbol="m",
            name="meter",
            system=MeasurementSystem.METRIC,
            type=MeasurementType.HEIGHT,
            conversion_factor=Decimal("1.0"),
        ),
        "cm": MeasurementUnit(
            symbol="cm",
            name="centimeter",
            system=MeasurementSystem.METRIC,
            type=MeasurementType.HEIGHT,
            conversion_factor=Decimal("0.01"),
            base_unit="m",
        ),
        "mm": MeasurementUnit(
            symbol="mm",
            name="millimeter",
            system=MeasurementSystem.METRIC,
            type=MeasurementType.HEIGHT,
            conversion_factor=Decimal("0.001"),
            base_unit="m",
        ),
        "ft": MeasurementUnit(
            symbol="ft",
            name="feet",
            system=MeasurementSystem.IMPERIAL,
            type=MeasurementType.HEIGHT,
            conversion_factor=Decimal("0.3048"),
            base_unit="m",
        ),
        "in": MeasurementUnit(
            symbol="in",
            name="inches",
            system=MeasurementSystem.IMPERIAL,
            type=MeasurementType.HEIGHT,
            conversion_factor=Decimal("0.0254"),
            base_unit="m",
        ),
        # Volume
        "l": MeasurementUnit(
            symbol="L",
            name="liter",
            system=MeasurementSystem.METRIC,
            type=MeasurementType.LIQUID_VOLUME,
            conversion_factor=Decimal("1.0"),
        ),
        "ml": MeasurementUnit(
            symbol="mL",
            name="milliliter",
            system=MeasurementSystem.METRIC,
            type=MeasurementType.LIQUID_VOLUME,
            conversion_factor=Decimal("0.001"),
            base_unit="l",
        ),
        "dl": MeasurementUnit(
            symbol="dL",
            name="deciliter",
            system=MeasurementSystem.METRIC,
            type=MeasurementType.LIQUID_VOLUME,
            conversion_factor=Decimal("0.1"),
            base_unit="l",
        ),
        "cc": MeasurementUnit(
            symbol="cc",
            name="cubic centimeter",
            system=MeasurementSystem.METRIC,
            type=MeasurementType.LIQUID_VOLUME,
            conversion_factor=Decimal("0.001"),
            base_unit="l",
        ),
        "fl_oz": MeasurementUnit(
            symbol="fl oz",
            name="fluid ounce",
            system=MeasurementSystem.US_CUSTOMARY,
            type=MeasurementType.LIQUID_VOLUME,
            conversion_factor=Decimal("0.0295735"),
            base_unit="l",
        ),
        "tsp": MeasurementUnit(
            symbol="tsp",
            name="teaspoon",
            system=MeasurementSystem.US_CUSTOMARY,
            type=MeasurementType.LIQUID_VOLUME,
            conversion_factor=Decimal("0.00492892"),
            base_unit="l",
        ),
        "tbsp": MeasurementUnit(
            symbol="tbsp",
            name="tablespoon",
            system=MeasurementSystem.US_CUSTOMARY,
            type=MeasurementType.LIQUID_VOLUME,
            conversion_factor=Decimal("0.0147868"),
            base_unit="l",
        ),
        # Blood glucose
        "mmol/l": MeasurementUnit(
            symbol="mmol/L",
            name="millimoles per liter",
            system=MeasurementSystem.METRIC,
            type=MeasurementType.GLUCOSE,
            conversion_factor=Decimal("1.0"),
        ),
        "mg/dl": MeasurementUnit(
            symbol="mg/dL",
            name="milligrams per deciliter",
            system=MeasurementSystem.US_CUSTOMARY,
            type=MeasurementType.GLUCOSE,
            conversion_factor=Decimal("0.0555"),
            base_unit="mmol/l",
        ),
    }

    # Regional preferences
    REGIONAL_PREFERENCES = {
        # Countries using metric system
        "default": MeasurementSystem.METRIC,
        # Countries using imperial/US customary
        "US": MeasurementSystem.US_CUSTOMARY,
        "GB": MeasurementSystem.IMPERIAL,
        "MM": MeasurementSystem.IMPERIAL,  # Myanmar
        "LR": MeasurementSystem.IMPERIAL,  # Liberia
        # Specific regional preferences by country/region
        "SYRIA": MeasurementSystem.METRIC,
        "IRAQ": MeasurementSystem.METRIC,
        "AFGHANISTAN": MeasurementSystem.METRIC,
        "SOMALIA": MeasurementSystem.METRIC,
        "SUDAN": MeasurementSystem.METRIC,
        "CONGO": MeasurementSystem.METRIC,
        "ETHIOPIA": MeasurementSystem.METRIC,
        "ERITREA": MeasurementSystem.METRIC,
        "MYANMAR": MeasurementSystem.IMPERIAL,
        "KENYA": MeasurementSystem.METRIC,
        "TANZANIA": MeasurementSystem.METRIC,
    }

    # Medical precision requirements
    PRECISION_REQUIREMENTS = {
        MeasurementType.TEMPERATURE: 1,
        MeasurementType.WEIGHT: 2,
        MeasurementType.HEIGHT: 1,
        MeasurementType.MASS_DOSAGE: 3,
        MeasurementType.LIQUID_VOLUME: 2,
        MeasurementType.GLUCOSE: 1,
        MeasurementType.BLOOD_PRESSURE: 0,
    }

    def _build_unit_aliases(self) -> Dict[str, str]:
        """Build mapping of unit aliases to standard unit names."""
        aliases = {
            # Weight aliases
            "kilogram": "kg",
            "kilograms": "kg",
            "kilo": "kg",
            "kilos": "kg",
            "gram": "g",
            "grams": "g",
            "gm": "g",
            "milligram": "mg",
            "milligrams": "mg",
            "microgram": "mcg",
            "micrograms": "mcg",
            "ug": "mcg",
            "μg": "mcg",
            "pound": "lb",
            "pounds": "lb",
            "lbs": "lb",
            "ounce": "oz",
            "ounces": "oz",
            # Length aliases
            "meter": "m",
            "meters": "m",
            "metre": "m",
            "metres": "m",
            "centimeter": "cm",
            "centimeters": "cm",
            "centimetre": "cm",
            "centimetres": "cm",
            "millimeter": "mm",
            "millimeters": "mm",
            "millimetre": "mm",
            "millimetres": "mm",
            "foot": "ft",
            "feet": "ft",
            "inch": "in",
            "inches": "in",
            # Volume aliases
            "liter": "l",
            "liters": "l",
            "litre": "l",
            "litres": "l",
            "milliliter": "ml",
            "milliliters": "ml",
            "millilitre": "ml",
            "millilitres": "ml",
            "deciliter": "dl",
            "deciliters": "dl",
            "decilitre": "dl",
            "decilitres": "dl",
            "fluid ounce": "fl_oz",
            "fluid ounces": "fl_oz",
            "teaspoon": "tsp",
            "teaspoons": "tsp",
            "tablespoon": "tbsp",
            "tablespoons": "tbsp",
            # Temperature aliases
            "c": "celsius",
            "°c": "celsius",
            "centigrade": "celsius",
            "f": "fahrenheit",
            "°f": "fahrenheit",
        }

        # Add unit symbols as their own aliases
        for unit_key, unit in self.UNITS.items():
            aliases[unit.symbol.lower()] = unit_key
            aliases[unit_key] = unit_key

        return aliases

    def normalize_unit(self, unit: str) -> Optional[str]:
        """Normalize unit string to standard form."""
        if not unit:
            return None

        # Clean and lowercase
        unit_clean = unit.strip().lower()

        # Remove common prefixes
        unit_clean = unit_clean.replace("per ", "/").replace("sq ", "²")

        # Check aliases
        return self._unit_aliases.get(unit_clean)

    def parse_measurement(self, text: str) -> List[Tuple[Decimal, str]]:
        """
        Parse measurement values and units from text.

        Args:
            text: Text containing measurements

        Returns:
            List of (value, unit) tuples
        """
        measurements = []

        # Patterns for different measurement formats
        patterns = [
            # Standard format: 50 kg, 37.5°C
            r"(\d+\.?\d*)\s*([a-zA-Z°/]+)",
            # With symbols: 98.6°F, 120/80 mmHg
            r"(\d+\.?\d*)\s*°\s*([CF])",
            # Blood pressure: 120/80
            r"(\d+)/(\d+)\s*(mmHg|mm Hg)?",
            # Feet and inches: 5'10", 5 ft 10 in
            r"(\d+)'(\d+)\"?|(\d+)\s*ft\s*(\d+)\s*in",
        ]

        for pattern in patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                groups = match.groups()
                if len(groups) >= 2 and groups[0] and groups[1]:
                    try:
                        value = Decimal(groups[0])
                        unit = self.normalize_unit(groups[1])
                        if unit:
                            measurements.append((value, unit))
                    except (ValueError, TypeError):
                        continue

        return measurements

    @require_phi_access(AccessLevel.READ)
    @audit_phi_access("convert_measurement")
    def convert(
        self,
        value: Union[float, Decimal, str],
        from_unit: str,
        to_unit: str,
        precision: Optional[int] = None,
    ) -> ConversionResult:
        """
        Convert measurement from one unit to another.

        Args:
            value: Numeric value to convert
            from_unit: Source unit
            to_unit: Target unit
            precision: Decimal places (uses medical standards if not specified)

        Returns:
            ConversionResult with converted value and warnings
        """
        warnings = []

        # Convert to Decimal for precision
        if isinstance(value, str):
            try:
                dec_value = Decimal(value)
            except (AttributeError, TypeError, ValueError) as exc:
                raise ValueError(f"Invalid numeric value: {value}") from exc
        else:
            dec_value = Decimal(str(value))

        # Normalize units
        from_unit_norm = self.normalize_unit(from_unit)
        to_unit_norm = self.normalize_unit(to_unit)

        if not from_unit_norm or not to_unit_norm:
            raise ValueError(f"Unknown unit: {from_unit} or {to_unit}")

        # Get unit information
        from_unit_info = self.UNITS.get(from_unit_norm)
        to_unit_info = self.UNITS.get(to_unit_norm)

        if not from_unit_info or not to_unit_info:
            raise ValueError(f"Unit not found: {from_unit_norm} or {to_unit_norm}")

        # Check if units are compatible
        if from_unit_info.type != to_unit_info.type:
            raise ValueError(
                f"Incompatible unit types: {from_unit_info.type} and {to_unit_info.type}"
            )

        # Handle temperature conversion separately
        if from_unit_info.type == MeasurementType.TEMPERATURE:
            converted_value = self._convert_temperature(
                dec_value, from_unit_norm, to_unit_norm
            )
        else:
            # Standard conversion through base unit
            # First convert to base unit
            base_value = dec_value * from_unit_info.conversion_factor

            # Then convert to target unit
            converted_value = base_value / to_unit_info.conversion_factor

        # Apply precision
        if precision is None:
            precision = self.PRECISION_REQUIREMENTS.get(from_unit_info.type, 2)

        # Round to specified precision
        quantizer = Decimal(10) ** -precision
        rounded_value = converted_value.quantize(quantizer, rounding=ROUND_HALF_UP)

        # Check for significant changes due to rounding
        if abs(rounded_value - converted_value) > converted_value * Decimal("0.01"):
            warnings.append("Significant rounding applied")

        # Format the result
        if precision == 0:
            formatted = f"{int(rounded_value)} {to_unit_info.symbol}"
        else:
            formatted = f"{rounded_value} {to_unit_info.symbol}"

        return ConversionResult(
            value=rounded_value,
            unit=to_unit_info.symbol,
            formatted=formatted,
            precision=precision,
            warnings=warnings,
        )

    def _convert_temperature(
        self, value: Decimal, from_unit: str, to_unit: str
    ) -> Decimal:
        """Convert temperature between Celsius and Fahrenheit."""
        if from_unit == "celsius" and to_unit == "fahrenheit":
            return (value * Decimal("9") / Decimal("5")) + Decimal("32")
        elif from_unit == "fahrenheit" and to_unit == "celsius":
            return (value - Decimal("32")) * Decimal("5") / Decimal("9")
        else:
            return value

    def convert_to_system(
        self, value: Union[float, Decimal], unit: str, target_system: MeasurementSystem
    ) -> ConversionResult:
        """
        Convert measurement to preferred unit in target system.

        Args:
            value: Numeric value
            unit: Current unit
            target_system: Target measurement system

        Returns:
            ConversionResult
        """
        # Normalize unit
        unit_norm = self.normalize_unit(unit)
        if not unit_norm:
            raise ValueError(f"Unknown unit: {unit}")

        unit_info = self.UNITS.get(unit_norm)
        if not unit_info:
            raise ValueError(f"Unit not found: {unit_norm}")

        # If already in target system, return as is
        if unit_info.system == target_system:
            result: ConversionResult = self.convert(value, unit, unit)
            return result

        # Find preferred unit in target system
        target_unit = self._get_preferred_unit(unit_info.type, target_system)

        if not target_unit:
            # No conversion available
            warnings = [f"No {target_system} equivalent for {unit}"]
            return ConversionResult(
                value=Decimal(str(value)),
                unit=unit_info.symbol,
                formatted=f"{value} {unit_info.symbol}",
                precision=2,
                warnings=warnings,
            )

        result = self.convert(value, unit, target_unit)
        return result

    def _get_preferred_unit(
        self, measurement_type: MeasurementType, system: MeasurementSystem
    ) -> Optional[str]:
        """Get preferred unit for measurement type in given system."""
        preferences = {
            (MeasurementType.TEMPERATURE, MeasurementSystem.METRIC): "celsius",
            (MeasurementType.TEMPERATURE, MeasurementSystem.IMPERIAL): "fahrenheit",
            (MeasurementType.TEMPERATURE, MeasurementSystem.US_CUSTOMARY): "fahrenheit",
            (MeasurementType.WEIGHT, MeasurementSystem.METRIC): "kg",
            (MeasurementType.WEIGHT, MeasurementSystem.IMPERIAL): "lb",
            (MeasurementType.WEIGHT, MeasurementSystem.US_CUSTOMARY): "lb",
            (MeasurementType.HEIGHT, MeasurementSystem.METRIC): "cm",
            (MeasurementType.HEIGHT, MeasurementSystem.IMPERIAL): "ft",
            (MeasurementType.HEIGHT, MeasurementSystem.US_CUSTOMARY): "ft",
            (MeasurementType.LIQUID_VOLUME, MeasurementSystem.METRIC): "ml",
            (MeasurementType.LIQUID_VOLUME, MeasurementSystem.IMPERIAL): "fl_oz",
            (MeasurementType.LIQUID_VOLUME, MeasurementSystem.US_CUSTOMARY): "fl_oz",
            (MeasurementType.MASS_DOSAGE, MeasurementSystem.METRIC): "mg",
            (
                MeasurementType.MASS_DOSAGE,
                MeasurementSystem.IMPERIAL,
            ): "mg",  # Medical stays metric
            (MeasurementType.MASS_DOSAGE, MeasurementSystem.US_CUSTOMARY): "mg",
            (MeasurementType.GLUCOSE, MeasurementSystem.METRIC): "mmol/l",
            (MeasurementType.GLUCOSE, MeasurementSystem.US_CUSTOMARY): "mg/dl",
        }

        return preferences.get((measurement_type, system))

    def get_regional_system(self, region: str) -> MeasurementSystem:
        """Get preferred measurement system for a region."""
        region_upper = region.upper()

        # Check specific regional preferences
        if region_upper in self.REGIONAL_PREFERENCES:
            return self.REGIONAL_PREFERENCES[region_upper]

        # Check country code (first 2 letters)
        country_code = region_upper[:2]
        if country_code in self.REGIONAL_PREFERENCES:
            return self.REGIONAL_PREFERENCES[country_code]

        # Default to metric
        return self.REGIONAL_PREFERENCES["default"]

    def convert_in_text(
        self,
        text: str,
        target_system: MeasurementSystem,
        preserve_original: bool = False,
    ) -> str:
        """
        Convert all measurements in text to target system.

        Args:
            text: Text containing measurements
            target_system: Target measurement system
            preserve_original: Keep original in parentheses

        Returns:
            Text with converted measurements
        """
        # Parse measurements from text
        measurements = self.parse_measurement(text)

        if not measurements:
            return text

        # Sort by position in text (reverse to maintain positions)
        converted_text = text

        for value, unit in measurements:
            try:
                # Convert to target system
                result = self.convert_to_system(value, unit, target_system)

                # Find original in text
                original_pattern = rf"{value}\s*{re.escape(unit)}"

                # Create replacement
                if preserve_original and result.unit != unit:
                    replacement = f"{result.formatted} ({value} {unit})"
                else:
                    replacement = result.formatted

                # Replace in text
                converted_text = re.sub(
                    original_pattern,
                    replacement,
                    converted_text,
                    count=1,
                    flags=re.IGNORECASE,
                )

            except (KeyError, AttributeError, ValueError) as e:
                logger.warning(f"Failed to convert {value} {unit}: {e}")
                continue

        return converted_text

    def format_height_human_readable(
        self, height_cm: Union[float, Decimal], system: MeasurementSystem
    ) -> str:
        """
        Format height in human-readable form.

        Args:
            height_cm: Height in centimeters
            system: Measurement system for output

        Returns:
            Formatted height string
        """
        if system == MeasurementSystem.METRIC:
            # Use cm for heights under 100cm, otherwise m + cm
            if height_cm < 100:
                return f"{height_cm} cm"
            else:
                meters = int(height_cm // 100)
                cm = int(height_cm % 100)
                if cm > 0:
                    return f"{meters}m {cm}cm"
                else:
                    return f"{meters}m"
        else:
            # Convert to feet and inches
            total_inches = Decimal(str(height_cm)) / Decimal("2.54")
            feet = int(total_inches // 12)
            inches = int(total_inches % 12)

            if inches > 0:
                return f"{feet}'{inches}\""
            else:
                return f"{feet}'"

    def validate_medical_range(
        self, value: Union[float, Decimal], unit: str, measurement_type: MeasurementType
    ) -> List[str]:
        """
        Validate if measurement is within typical medical ranges.

        Args:
            value: Measurement value
            unit: Measurement unit
            measurement_type: Type of measurement

        Returns:
            List of validation warnings
        """
        warnings: List[str] = []

        # Define typical ranges (these are approximate)
        ranges = {
            (MeasurementType.TEMPERATURE, "celsius"): (35.0, 42.0),
            (MeasurementType.TEMPERATURE, "fahrenheit"): (95.0, 107.6),
            (MeasurementType.WEIGHT, "kg"): (0.5, 300.0),
            (MeasurementType.WEIGHT, "lb"): (1.0, 660.0),
            (MeasurementType.HEIGHT, "cm"): (20.0, 250.0),
            (MeasurementType.HEIGHT, "ft"): (0.66, 8.2),
            (MeasurementType.HEART_RATE, "bpm"): (30, 250),
            (MeasurementType.GLUCOSE, "mmol/l"): (1.0, 30.0),
            (MeasurementType.GLUCOSE, "mg/dl"): (18.0, 540.0),
        }

        # Normalize unit
        unit_norm = self.normalize_unit(unit)
        if unit_norm is None:
            return warnings

        range_key = (measurement_type, unit_norm)

        if range_key in ranges:
            min_val, max_val = ranges[range_key]
            dec_value = Decimal(str(value))

            if dec_value < min_val:
                warnings.append(f"Value below typical range (min: {min_val})")
            elif dec_value > max_val:
                warnings.append(f"Value above typical range (max: {max_val})")

        return warnings

    def create_fhir_observation(
        self,
        value: Union[float, Decimal],
        unit: str,
        measurement_type: MeasurementType,
        patient_reference: str,
        effective_datetime: Optional[str] = None,
        status: str = "final",
    ) -> Dict[str, Any]:
        """
        Create a FHIR Observation resource from a measurement.

        Args:
            value: Measurement value
            unit: Measurement unit
            measurement_type: Type of measurement
            patient_reference: Reference to patient resource
            effective_datetime: When the observation was made
            status: Observation status

        Returns:
            FHIR Observation resource as dict
        """
        # Normalize unit
        unit_norm = self.normalize_unit(unit)
        if not unit_norm:
            raise ValueError(f"Unknown unit: {unit}")

        # Get LOINC code
        loinc_code = self.FHIR_LOINC_CODES.get(measurement_type)

        observation: Dict[str, Any] = {
            "resourceType": "Observation",
            "status": status,
            "code": {
                "coding": [
                    {
                        "system": "http://loinc.org",
                        "code": loinc_code,
                        "display": measurement_type.value,
                    }
                ],
                "text": measurement_type.value,
            },
            "subject": {"reference": patient_reference},
            "valueQuantity": {
                "value": float(value),
                "unit": self.UNITS[unit_norm].symbol,
                "system": "http://unitsofmeasure.org",
                "code": unit_norm,
            },
        }

        if effective_datetime:
            observation["effectiveDateTime"] = effective_datetime

        # Add warnings as notes if any
        validation_warnings = self.validate_medical_range(value, unit, measurement_type)
        if validation_warnings:
            observation["note"] = [{"text": warning} for warning in validation_warnings]

        return observation


# Singleton instance
_measurement_converter = MeasurementConverter()


def get_measurement_converter() -> MeasurementConverter:
    """Get the singleton measurement converter instance."""
    return _measurement_converter
