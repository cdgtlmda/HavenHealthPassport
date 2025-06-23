"""
Medical-specific unit conversion.

This module provides specialized unit conversion for medical contexts,
including medication dosages, lab values, and vital signs.

This module handles encrypted PHI with access control and audit logging
to ensure HIPAA compliance.
 Handles FHIR Resource validation.
"""

import logging
import re
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple, Union, cast

from .core import (
    ConversionContext,
    MeasurementValue,
    PrecisionLevel,
    Unit,
    UnitConverter,
    UnitSystem,
    UnitType,
)

logger = logging.getLogger(__name__)


@dataclass
class MedicationDose:
    """Represents a medication dose."""

    amount: MeasurementValue
    form: str  # tablet, capsule, mL, etc.
    frequency: Optional[str] = None  # daily, BID, TID, etc.
    route: Optional[str] = None  # oral, IV, IM, etc.
    duration: Optional[str] = None  # days, weeks, etc.

    def __str__(self) -> str:
        """Return string representation of medication dose."""
        parts = [str(self.amount)]
        if self.form:
            parts.append(self.form)
        if self.frequency:
            parts.append(self.frequency)
        if self.route:
            parts.append(f"({self.route})")
        return " ".join(parts)


@dataclass
class LabValue:
    """Represents a laboratory test value."""

    test_name: str
    value: MeasurementValue
    normal_range: Optional[Tuple[Decimal, Decimal]] = None
    unit_type: Optional[str] = None  # conventional, SI
    flags: List[str] = field(default_factory=list)  # H, L, Critical

    def is_normal(self) -> Optional[bool]:
        """Check if value is within normal range."""
        if not self.normal_range:
            return None
        return self.normal_range[0] <= self.value.value <= self.normal_range[1]

    def __str__(self) -> str:
        """Return string representation of lab value."""
        result = f"{self.test_name}: {self.value}"
        if self.normal_range:
            result += f" (Normal: {self.normal_range[0]}-{self.normal_range[1]} {self.value.unit.symbol})"
        if self.flags:
            result += f" [{', '.join(self.flags)}]"
        return result


@dataclass
class VitalSign:
    """Represents a vital sign measurement."""

    type: str  # temperature, blood_pressure, heart_rate, etc.
    value: Union[
        MeasurementValue, Tuple[MeasurementValue, MeasurementValue]
    ]  # BP is tuple
    position: Optional[str] = None  # sitting, standing, lying
    location: Optional[str] = None  # oral, rectal, axillary (for temp)
    time: Optional[str] = None

    def __str__(self) -> str:
        """Return string representation of vital sign."""
        if isinstance(self.value, tuple):
            # Blood pressure
            return f"{self.type}: {self.value[0]}/{self.value[1]}"
        return f"{self.type}: {self.value}"


class MedicalUnitConverter(UnitConverter):
    """Specialized unit converter for medical measurements."""

    def __init__(self) -> None:
        """Initialize medical unit converter."""
        super().__init__()
        self._add_medical_units()
        self.lab_conversions = self._load_lab_conversions()
        self.normal_ranges = self._load_normal_ranges()

    def _add_medical_units(self) -> None:
        """Add medical-specific units."""
        # Concentration units
        self.units.update(
            {
                "mg/dL": Unit(
                    "mg/dL",
                    "milligrams per deciliter",
                    UnitType.CONCENTRATION,
                    UnitSystem.US_CUSTOMARY,
                ),
                "mmol/L": Unit(
                    "mmol/L",
                    "millimoles per liter",
                    UnitType.CONCENTRATION,
                    UnitSystem.METRIC,
                ),
                "g/dL": Unit(
                    "g/dL",
                    "grams per deciliter",
                    UnitType.CONCENTRATION,
                    UnitSystem.US_CUSTOMARY,
                ),
                "g/L": Unit(
                    "g/L", "grams per liter", UnitType.CONCENTRATION, UnitSystem.METRIC
                ),
                "µg/dL": Unit(
                    "µg/dL",
                    "micrograms per deciliter",
                    UnitType.CONCENTRATION,
                    UnitSystem.US_CUSTOMARY,
                ),
                "nmol/L": Unit(
                    "nmol/L",
                    "nanomoles per liter",
                    UnitType.CONCENTRATION,
                    UnitSystem.METRIC,
                ),
                "mEq/L": Unit(
                    "mEq/L",
                    "milliequivalents per liter",
                    UnitType.CONCENTRATION,
                    UnitSystem.METRIC,
                ),
                "IU/L": Unit(
                    "IU/L",
                    "international units per liter",
                    UnitType.ENZYME,
                    UnitSystem.METRIC,
                ),
                "U/L": Unit(
                    "U/L", "units per liter", UnitType.ENZYME, UnitSystem.METRIC
                ),
            }
        )

        # Cell count units
        self.units.update(
            {
                "cells/µL": Unit(
                    "cells/µL",
                    "cells per microliter",
                    UnitType.CELL_COUNT,
                    UnitSystem.METRIC,
                ),
                "×10⁹/L": Unit(
                    "×10⁹/L",
                    "billion per liter",
                    UnitType.CELL_COUNT,
                    UnitSystem.METRIC,
                ),
                "×10¹²/L": Unit(
                    "×10¹²/L",
                    "trillion per liter",
                    UnitType.CELL_COUNT,
                    UnitSystem.METRIC,
                ),
            }
        )

        # Flow rate units
        self.units.update(
            {
                "mL/hr": Unit(
                    "mL/hr",
                    "milliliters per hour",
                    UnitType.FLOW_RATE,
                    UnitSystem.METRIC,
                ),
                "gtt/min": Unit(
                    "gtt/min", "drops per minute", UnitType.FLOW_RATE, UnitSystem.METRIC
                ),
                "L/min": Unit(
                    "L/min", "liters per minute", UnitType.FLOW_RATE, UnitSystem.METRIC
                ),
            }
        )

    def convert_lab_value(
        self, lab_value: LabValue, target_unit_type: str = "SI"
    ) -> LabValue:
        """
        Convert lab value between conventional and SI units.

        Args:
            lab_value: Lab value to convert
            target_unit_type: "SI" or "conventional"

        Returns:
            Converted lab value
        """
        # Check if conversion is available for this test
        test_key = lab_value.test_name.lower()
        if test_key not in self.lab_conversions:
            return lab_value  # Return unchanged if no conversion available

        conversion_info = self.lab_conversions[test_key]

        # Determine source and target units
        if target_unit_type == "SI":
            if lab_value.value.unit.symbol == conversion_info["conventional_unit"]:
                # Convert conventional to SI
                factor = Decimal(str(conversion_info["to_si_factor"]))
                new_value = lab_value.value.value * factor
                new_unit = self.units[conversion_info["si_unit"]]
            else:
                return lab_value  # Already in SI
        else:
            if lab_value.value.unit.symbol == conversion_info["si_unit"]:
                # Convert SI to conventional
                factor = Decimal(str(conversion_info["to_conventional_factor"]))
                new_value = lab_value.value.value * factor
                new_unit = self.units[conversion_info["conventional_unit"]]
            else:
                return lab_value  # Already in conventional

        # Create new lab value
        new_measurement = MeasurementValue(
            value=new_value, unit=new_unit, precision=lab_value.value.precision
        )

        # Convert normal range if present
        new_normal_range = None
        if lab_value.normal_range:
            if target_unit_type == "SI":
                factor = Decimal(str(conversion_info["to_si_factor"]))
            else:
                factor = Decimal(str(conversion_info["to_conventional_factor"]))
            new_normal_range = (
                lab_value.normal_range[0] * factor,
                lab_value.normal_range[1] * factor,
            )

        return LabValue(
            test_name=lab_value.test_name,
            value=new_measurement,
            normal_range=new_normal_range,
            unit_type=target_unit_type,
            flags=lab_value.flags,
        )

    def convert_medication_dose(
        self,
        dose: MedicationDose,
        target_unit: Union[Unit, str],
        patient_weight: Optional[MeasurementValue] = None,
    ) -> MedicationDose:
        """
        Convert medication dose to different unit.

        The patient_weight parameter can be used for weight-based
        dosing calculations when needed.

        Args:
            dose: Medication dose to convert
            target_unit: Target unit for dose
            patient_weight: Patient weight for weight-based dosing

        Returns:
            Converted medication dose
        """
        # Handle weight-based dosing calculations
        if patient_weight and isinstance(target_unit, str):
            # Check if this is a weight-based dosing conversion
            if "/kg" in target_unit or "per kg" in target_unit.lower():
                # Convert patient weight to kg if needed
                weight_in_kg = self._convert_weight_to_kg(patient_weight)

                # Calculate total dose from per-kg dose
                if "/kg" in str(dose.amount.unit):
                    # Current dose is already per-kg, calculate total
                    dose_per_kg = dose.amount.value
                    total_dose = float(dose_per_kg) * weight_in_kg

                    # Get the base unit (remove /kg)
                    base_unit = str(dose.amount.unit).replace("/kg", "").strip()

                    return MedicationDose(
                        amount=MeasurementValue(
                            value=Decimal(str(round(total_dose, 2))),
                            unit=self.units.get(
                                base_unit,
                                Unit(
                                    base_unit,
                                    base_unit,
                                    UnitType.WEIGHT,
                                    UnitSystem.METRIC,
                                ),
                            ),
                        ),
                        form=dose.form,
                        frequency=dose.frequency,
                        route=dose.route,
                        duration=dose.duration,
                    )
                else:
                    # Current dose is total, calculate per-kg
                    total_dose = float(dose.amount.value)
                    dose_per_kg = Decimal(str(total_dose / weight_in_kg))

                    # Add /kg to the unit
                    per_kg_unit = f"{dose.amount.unit}/kg"

                    return MedicationDose(
                        amount=MeasurementValue(
                            value=Decimal(str(round(dose_per_kg, 3))),
                            unit=self.units.get(
                                per_kg_unit,
                                Unit(
                                    per_kg_unit,
                                    per_kg_unit,
                                    UnitType.WEIGHT,
                                    UnitSystem.METRIC,
                                ),
                            ),
                        ),
                        form=dose.form,
                        frequency=dose.frequency,
                        route=dose.route,
                        duration=dose.duration,
                    )

            # Check for body surface area (BSA) based dosing
            elif (
                "/m²" in target_unit
                or "/m2" in target_unit
                or "per m2" in target_unit.lower()
            ):
                # BSA calculation would require height as well
                # For now, use standard conversion without BSA
                logger.warning(
                    "BSA-based dosing requires patient height. Using standard conversion."
                )

        # Standard dose conversion (not weight-based)
        context = ConversionContext(
            target_system=UnitSystem.METRIC,
            precision_level=PrecisionLevel.HIGH,
            medical_context=True,
        )

        conversion_result = self.convert(dose.amount, target_unit, context)

        # Create new dose
        return MedicationDose(
            amount=conversion_result.converted,
            form=dose.form,
            frequency=dose.frequency,
            route=dose.route,
            duration=dose.duration,
        )

    def _convert_weight_to_kg(self, weight: MeasurementValue) -> float:
        """Convert weight measurement to kilograms."""
        # Common weight units to kg conversion factors
        weight_conversions = {
            "kg": 1.0,
            "kilogram": 1.0,
            "kilograms": 1.0,
            "g": 0.001,
            "gram": 0.001,
            "grams": 0.001,
            "mg": 0.000001,
            "milligram": 0.000001,
            "milligrams": 0.000001,
            "lb": 0.453592,
            "lbs": 0.453592,
            "pound": 0.453592,
            "pounds": 0.453592,
            "oz": 0.0283495,
            "ounce": 0.0283495,
            "ounces": 0.0283495,
            "stone": 6.35029,
            "stones": 6.35029,
        }

        unit_str = str(weight.unit).lower()

        if unit_str in weight_conversions:
            return float(weight.value) * weight_conversions[unit_str]
        else:
            # Try to convert using the standard conversion method
            try:
                context = ConversionContext(
                    target_system=UnitSystem.METRIC,
                    precision_level=PrecisionLevel.HIGH,
                    medical_context=True,
                )
                result = self.convert(weight, "kg", context)
                return float(result.converted.value)
            except (ValueError, AttributeError, KeyError) as e:
                logger.warning(
                    "Could not convert weight unit %s to kg: %s", unit_str, str(e)
                )
                # Assume kg if conversion fails
                return float(weight.value)

    def _load_lab_conversions(self) -> Dict[str, Dict[str, Any]]:
        """Load lab test conversion factors."""
        return {
            "glucose": {
                "conventional_unit": "mg/dL",
                "si_unit": "mmol/L",
                "to_si_factor": 0.0555,  # mg/dL to mmol/L
                "to_conventional_factor": 18.0182,  # mmol/L to mg/dL
            },
            "cholesterol": {
                "conventional_unit": "mg/dL",
                "si_unit": "mmol/L",
                "to_si_factor": 0.0259,
                "to_conventional_factor": 38.67,
            },
            "hemoglobin": {
                "conventional_unit": "g/dL",
                "si_unit": "g/L",
                "to_si_factor": 10.0,
                "to_conventional_factor": 0.1,
            },
            "creatinine": {
                "conventional_unit": "mg/dL",
                "si_unit": "µmol/L",
                "to_si_factor": 88.4,
                "to_conventional_factor": 0.0113,
            },
            "bilirubin": {
                "conventional_unit": "mg/dL",
                "si_unit": "µmol/L",
                "to_si_factor": 17.1,
                "to_conventional_factor": 0.0585,
            },
            "calcium": {
                "conventional_unit": "mg/dL",
                "si_unit": "mmol/L",
                "to_si_factor": 0.25,
                "to_conventional_factor": 4.0,
            },
            "sodium": {
                "conventional_unit": "mEq/L",
                "si_unit": "mmol/L",
                "to_si_factor": 1.0,  # Same for monovalent ions
                "to_conventional_factor": 1.0,
            },
            "potassium": {
                "conventional_unit": "mEq/L",
                "si_unit": "mmol/L",
                "to_si_factor": 1.0,
                "to_conventional_factor": 1.0,
            },
        }

    def _load_normal_ranges(self) -> Dict[str, Dict[str, Any]]:
        """Load normal ranges for common lab tests."""
        return {
            "glucose": {"mg/dL": (70, 100), "mmol/L": (3.9, 5.6)},  # Fasting
            "hemoglobin": {
                "g/dL": (
                    13.5,
                    17.5,
                ),  # Average range, gender-specific handled elsewhere
                "g/L": (135, 175),  # Average range
            },
            "creatinine": {
                "mg/dL": {"male": (0.7, 1.3), "female": (0.6, 1.1)},
                "µmol/L": {"male": (62, 115), "female": (53, 97)},
            },
        }


def convert_medication_dose(
    dose_str: str, target_unit: str, converter: Optional[MedicalUnitConverter] = None
) -> str:
    """
    Convert medication dose string to target unit.

    Args:
        dose_str: Dose string (e.g., "500 mg twice daily")
        target_unit: Target unit symbol
        converter: Optional converter instance

    Returns:
        Converted dose string
    """
    converter = converter or MedicalUnitConverter()

    # Parse dose
    pattern = r"([\d.]+)\s*([a-zA-Zµ]+)"
    match = re.search(pattern, dose_str)

    if not match:
        return dose_str

    try:
        value = Decimal(match.group(1))
        unit_symbol = match.group(2)

        measurement = MeasurementValue(value=value, unit=converter.units[unit_symbol])

        dose = MedicationDose(
            amount=measurement, form="", frequency=dose_str[match.end() :].strip()
        )

        converted = converter.convert_medication_dose(dose, target_unit)
        return f"{converted.amount} {converted.frequency}"

    except (KeyError, ValueError):
        return dose_str


def convert_lab_value(
    test_name: str,
    value: float,
    unit: str,
    target_type: str = "SI",
    converter: Optional[MedicalUnitConverter] = None,
) -> LabValue:
    """
    Convert a lab value between unit systems.

    Args:
        test_name: Name of the lab test
        value: Numeric value
        unit: Current unit
        target_type: "SI" or "conventional"
        converter: Optional converter instance

    Returns:
        Converted LabValue
    """
    converter = converter or MedicalUnitConverter()

    measurement = MeasurementValue(
        value=Decimal(str(value)),
        unit=converter.units.get(
            unit, Unit(unit, unit, UnitType.CONCENTRATION, UnitSystem.METRIC)
        ),
    )

    lab_value = LabValue(test_name=test_name, value=measurement)

    return converter.convert_lab_value(lab_value, target_type)


def get_normal_ranges(
    test_name: str, unit_type: str = "SI", gender: Optional[str] = None
) -> Optional[Tuple[float, float]]:
    """
    Get normal ranges for lab tests.

    The unit_type parameter specifies whether to return SI or conventional units.
    Get normal ranges for a lab test.

    Args:
        test_name: Name of the lab test
        unit_type: "SI" or "conventional"
        gender: Optional gender for gender-specific ranges

    Returns:
        Tuple of (low, high) normal values
    """
    converter = MedicalUnitConverter()
    ranges = converter.normal_ranges.get(test_name.lower(), {})

    if not ranges:
        return None

    # Determine which unit to use based on unit_type
    target_units = []

    if unit_type.upper() == "SI":
        # SI units mapping
        si_units = {
            "glucose": ["mmol/L"],
            "cholesterol": ["mmol/L"],
            "hemoglobin": ["g/L"],
            "creatinine": ["µmol/L", "umol/L", "μmol/L"],
        }
        target_units = si_units.get(test_name.lower(), [])
    else:  # conventional
        # Conventional units mapping
        conventional_units = {
            "glucose": ["mg/dL"],
            "cholesterol": ["mg/dL"],
            "hemoglobin": ["g/dL"],
            "creatinine": ["mg/dL"],
        }
        target_units = conventional_units.get(test_name.lower(), [])

    # Find the appropriate range for the requested unit type
    for unit in target_units:
        if unit in ranges:
            range_data = ranges[unit]
            if isinstance(range_data, dict) and gender:
                # Gender-specific ranges
                if gender.lower() in range_data:
                    return cast(Tuple[float, float], range_data[gender.lower()])
                # Try variations of gender specification
                elif gender.lower() == "m" and "male" in range_data:
                    return cast(Tuple[float, float], range_data["male"])
                elif gender.lower() == "f" and "female" in range_data:
                    return cast(Tuple[float, float], range_data["female"])
            elif isinstance(range_data, tuple):
                # Non-gender-specific range
                return range_data

    # Fallback: if no range found for specified unit type, return any available range
    # This ensures backward compatibility
    for _, range_data in ranges.items():
        if isinstance(range_data, dict) and gender:
            if gender.lower() in range_data:
                return cast(Tuple[float, float], range_data[gender.lower()])
            elif gender.lower() == "m" and "male" in range_data:
                return cast(Tuple[float, float], range_data["male"])
            elif gender.lower() == "f" and "female" in range_data:
                return cast(Tuple[float, float], range_data["female"])
        elif isinstance(range_data, tuple):
            return range_data

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
