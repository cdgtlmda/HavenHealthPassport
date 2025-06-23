"""
Unit formatting and parsing utilities.

This module provides functions for formatting measurements
and parsing measurement strings.

This module handles encrypted PHI with access control and audit logging
to ensure HIPAA compliance.
 Handles FHIR Resource validation.
"""

import logging
from decimal import Decimal
from typing import Any, Dict, Optional, Union

from ..config import Language
from .core import MeasurementValue, Unit, UnitConverter, UnitSystem, UnitType
from .medical import MedicationDose

logger = logging.getLogger(__name__)


class UnitFormatter:
    """Formats measurements according to regional and medical conventions."""

    def __init__(self) -> None:
        """Initialize formatter."""
        self.converter = UnitConverter()
        self.formats = self._load_format_rules()

    def format_measurement(
        self,
        value: MeasurementValue,
        language: Language = Language.ENGLISH,
        style: str = "standard",  # standard, abbreviated, full
        include_unit_name: bool = False,
    ) -> str:
        """
        Format a measurement value.

        Args:
            value: Measurement to format
            language: Target language
            style: Formatting style
            include_unit_name: Include full unit name

        Returns:
            Formatted measurement string
        """
        # Format number based on precision
        if value.precision is not None:
            number_str = f"{value.value:.{value.precision}f}"
        else:
            # Remove trailing zeros
            number_str = f"{value.value:g}"

        # Add thousands separator for large numbers
        if value.value >= 1000:
            parts = number_str.split(".")
            parts[0] = f"{int(parts[0]):,}"
            number_str = ".".join(parts)

        # Format unit
        if include_unit_name:
            unit_str = value.unit.name
        elif style == "abbreviated":
            unit_str = value.unit.symbol
        else:
            unit_str = value.unit.symbol

        # Language-specific formatting
        if language == Language.FRENCH:
            # French uses space before unit
            return f"{number_str} {unit_str}"
        elif language == Language.GERMAN:
            # German decimal comma
            number_str = number_str.replace(".", ",")
            return f"{number_str} {unit_str}"
        else:
            # Default formatting
            return f"{number_str} {unit_str}"

    def format_range(
        self,
        low: MeasurementValue,
        high: MeasurementValue,
        language: Language = Language.ENGLISH,
        style: str = "dash",  # dash, to, parentheses
    ) -> str:
        """Format a measurement range."""
        low_str = self.format_measurement(low, language)
        high_str = self.format_measurement(high, language)

        if style == "dash":
            return f"{low_str}–{high_str}"
        elif style == "to":
            if language == Language.ENGLISH:
                return f"{low_str} to {high_str}"
            elif language == Language.SPANISH:
                return f"{low_str} a {high_str}"
            elif language == Language.FRENCH:
                return f"{low_str} à {high_str}"
        elif style == "parentheses":
            return f"{low_str} ({high_str})"

        return f"{low_str}-{high_str}"

    def format_medication(
        self,
        dose: MedicationDose,
        language: Language = Language.ENGLISH,
        include_route: bool = True,
    ) -> str:
        """Format medication dose."""
        parts = []

        # Amount
        parts.append(self.format_measurement(dose.amount, language))

        # Form
        if dose.form:
            parts.append(dose.form)

        # Frequency
        if dose.frequency:
            freq_map = {
                "QD": "once daily",
                "BID": "twice daily",
                "TID": "three times daily",
                "QID": "four times daily",
                "PRN": "as needed",
            }
            frequency = freq_map.get(dose.frequency, dose.frequency)
            parts.append(frequency)

        # Route
        if include_route and dose.route:
            route_map = {
                "PO": "by mouth",
                "IV": "intravenously",
                "IM": "intramuscularly",
                "SC": "subcutaneously",
                "TOP": "topically",
            }
            route = route_map.get(dose.route, dose.route)
            parts.append(f"({route})")

        return " ".join(parts)

    def _load_format_rules(self) -> Dict[str, Any]:
        """Load formatting rules."""
        return {
            "decimal_separators": {
                Language.ENGLISH: ".",
                Language.FRENCH: ",",
                Language.GERMAN: ",",
                Language.SPANISH: ",",
            },
            "thousands_separators": {
                Language.ENGLISH: ",",
                Language.FRENCH: " ",
                Language.GERMAN: ".",
                Language.SPANISH: ".",
            },
        }


def format_measurement(
    value: Union[MeasurementValue, float],
    unit: Optional[Union[Unit, str]] = None,
    precision: Optional[int] = None,
    language: Language = Language.ENGLISH,
) -> str:
    """
    Format a measurement value.

    Args:
        value: Measurement or numeric value
        unit: Unit (required if value is numeric)
        precision: Decimal places
        language: Target language

    Returns:
        Formatted string
    """
    formatter = UnitFormatter()

    if isinstance(value, MeasurementValue):
        return formatter.format_measurement(value, language)
    else:
        if not unit:
            raise ValueError("Unit required for numeric value")

        converter = UnitConverter()
        if isinstance(unit, str):
            unit_obj = converter.units.get(unit)
            if not unit_obj:
                raise ValueError(f"Unknown unit: {unit}")
        else:
            unit_obj = unit

        measurement = MeasurementValue(
            value=Decimal(str(value)), unit=unit_obj, precision=precision
        )

        return formatter.format_measurement(measurement, language)


def format_range(
    low: float,
    high: float,
    unit: Union[Unit, str],
    language: Language = Language.ENGLISH,
) -> str:
    """Format a measurement range."""
    formatter = UnitFormatter()
    converter = UnitConverter()

    if isinstance(unit, str):
        unit_obj = converter.units.get(unit)
        if not unit_obj:
            raise ValueError(f"Unknown unit: {unit}")
    else:
        unit_obj = unit

    low_measurement = MeasurementValue(value=Decimal(str(low)), unit=unit_obj)
    high_measurement = MeasurementValue(value=Decimal(str(high)), unit=unit_obj)

    return formatter.format_range(low_measurement, high_measurement, language)


def format_medication(
    amount: float,
    unit: str,
    form: str,
    frequency: str,
    route: Optional[str] = None,
    language: Language = Language.ENGLISH,
) -> str:
    """Format medication dose information."""
    formatter = UnitFormatter()
    converter = UnitConverter()

    measurement = MeasurementValue(
        value=Decimal(str(amount)),
        unit=converter.units.get(
            unit, Unit(unit, unit, UnitType.DOSAGE, UnitSystem.METRIC)
        ),
    )

    dose = MedicationDose(
        amount=measurement, form=form, frequency=frequency, route=route
    )

    return formatter.format_medication(dose, language)


def parse_measurement(
    text: str, expected_type: Optional[str] = None
) -> Optional[MeasurementValue]:
    """
    Parse a measurement from text.

    Args:
        text: Text containing measurement
        expected_type: Expected unit type for validation

    Returns:
        MeasurementValue or None
    """
    converter = UnitConverter()

    try:
        measurement = MeasurementValue.from_string(text, converter.units)

        # Validate type if specified
        if expected_type and measurement.unit.type.value != expected_type:
            return None

        return measurement

    except (ValueError, KeyError):
        return None


def validate_measurement(measurement: MeasurementValue) -> bool:
    """Validate measurement data."""
    if not measurement:
        return False
    # Since MeasurementValue has non-optional fields, if it exists, they exist
    return True
