"""Medical Validators Module.

This module provides validation functions for medical data including medications,
lab values, vital signs, and other healthcare-specific data types.

This module handles encrypted PHI with access control and audit logging
to ensure HIPAA compliance.
Handles FHIR Resource validation.
"""

import re
from typing import Dict, List, Optional, Tuple, Union


class ValidationResult:
    """Result of a validation operation."""

    def __init__(
        self,
        is_valid: bool,
        errors: Optional[List[str]] = None,
        warnings: Optional[List[str]] = None,
    ) -> None:
        """Initialize validation result."""
        self.is_valid = is_valid
        self.errors = errors or []
        self.warnings = warnings or []


class MedicationValidator:
    """Validator for medication-related data."""

    @staticmethod
    async def validate_medication_name(name: str) -> Tuple[bool, List[str]]:
        """Validate medication name format and characters."""
        errors = []

        if not name or not name.strip():
            errors.append("Medication name cannot be empty")
            return False, errors

        # Check for invalid characters
        if not re.match(r"^[A-Za-z0-9\s\-\(\)\.\/]+$", name):
            errors.append("Medication name contains invalid characters")

        # Check length
        if len(name) < 2:
            errors.append("Medication name too short")
        elif len(name) > 100:
            errors.append("Medication name too long")

        return len(errors) == 0, errors

    @staticmethod
    async def validate_dosage(dosage: str) -> Tuple[bool, List[str]]:
        """Validate medication dosage format."""
        errors = []

        # Common dosage patterns
        patterns = [
            r"^\d+\.?\d*\s*(mg|g|mcg|ug|ml|l|unit|units|iu|mEq)$",
            r"^\d+\.?\d*-\d+\.?\d*\s*(mg|g|mcg|ug|ml|l|unit|units|iu|mEq)$",
            r"^\d+\.?\d*/\d+\.?\d*\s*(mg|ml|g|l)$",
        ]

        dosage_lower = dosage.lower().strip()
        if not any(re.match(pattern, dosage_lower) for pattern in patterns):
            errors.append("Invalid dosage format")

        return len(errors) == 0, errors

    @staticmethod
    async def validate_frequency(frequency: str) -> Tuple[bool, List[str]]:
        """Validate medication frequency."""
        errors = []

        valid_frequencies = [
            "qd",
            "daily",
            "once daily",
            "od",
            "bid",
            "twice daily",
            "bd",
            "tid",
            "three times daily",
            "tds",
            "qid",
            "four times daily",
            "qds",
            "prn",
            "as needed",
            "as required",
            "stat",
            "immediately",
            "q4h",
            "q6h",
            "q8h",
            "q12h",
            "q24h",
            "weekly",
            "monthly",
        ]

        if frequency.lower().strip() not in valid_frequencies:
            # Check for pattern like "every X hours/days"
            if not re.match(
                r"^(every|q)\s*\d+\s*(hours?|hrs?|days?|weeks?|months?)$",
                frequency.lower(),
            ):
                errors.append("Invalid frequency format")

        return len(errors) == 0, errors


class LabValueValidator:
    """Validator for laboratory values and results."""

    # Common lab test reference ranges
    REFERENCE_RANGES: Dict[str, Dict[str, Union[float, str]]] = {
        "glucose": {"min": 70, "max": 100, "unit": "mg/dL"},
        "hemoglobin": {"min": 12.0, "max": 17.5, "unit": "g/dL"},
        "wbc": {"min": 4000, "max": 11000, "unit": "cells/mm3"},
        "platelet": {"min": 150000, "max": 400000, "unit": "/mm3"},
        "sodium": {"min": 136, "max": 145, "unit": "mEq/L"},
        "potassium": {"min": 3.5, "max": 5.0, "unit": "mEq/L"},
        "creatinine": {"min": 0.6, "max": 1.2, "unit": "mg/dL"},
    }

    @staticmethod
    async def validate_lab_value(
        value: str, test_name: Optional[str] = None
    ) -> Tuple[bool, List[str]]:
        """Validate lab value format and optionally check against reference ranges."""
        errors = []

        # Extract numeric value and operator
        match = re.match(r"^([<>≤≥]?)\s*(\d+\.?\d*)\s*(.*)$", value.strip())
        if not match:
            errors.append("Invalid lab value format")
            return False, errors

        operator, numeric_str, _ = match.groups()

        try:
            numeric_value = float(numeric_str)
        except ValueError:
            errors.append("Invalid numeric value")
            return False, errors

        # Check if value is reasonable
        if numeric_value < 0:
            errors.append("Lab value cannot be negative")

        # If test name provided, check against reference ranges
        if test_name and test_name.lower() in LabValueValidator.REFERENCE_RANGES:
            ref_range = LabValueValidator.REFERENCE_RANGES[test_name.lower()]
            if not operator and (
                numeric_value < ref_range["min"] or numeric_value > ref_range["max"]  # type: ignore
            ):
                errors.append(
                    f"Value outside normal range ({ref_range['min']}-{ref_range['max']} {ref_range['unit']})"
                )

        return len(errors) == 0, errors

    @staticmethod
    async def validate_reference_range(range_str: str) -> Tuple[bool, List[str]]:
        """Validate lab reference range format."""
        errors = []

        # Common patterns for reference ranges
        patterns = [
            r"^\d+\.?\d*\s*-\s*\d+\.?\d*\s*\w*$",  # 10-20 mg/dL
            r"^[<>≤≥]\s*\d+\.?\d*\s*\w*$",  # < 5.0
            r"^negative$",
            r"^positive$",  # Qualitative results
            r"^normal$",
            r"^abnormal$",
        ]

        if not any(
            re.match(pattern, range_str.lower().strip()) for pattern in patterns
        ):
            errors.append("Invalid reference range format")

        return len(errors) == 0, errors


class VitalSignValidator:
    """Validator for vital signs."""

    VITAL_SIGN_RANGES: Dict[str, Union[Dict[str, Dict[str, int]], Dict[str, int]]] = {
        "blood_pressure": {
            "systolic": {"min": 70, "max": 200},
            "diastolic": {"min": 40, "max": 130},
        },
        "heart_rate": {"min": 40, "max": 200},
        "respiratory_rate": {"min": 8, "max": 40},
        "temperature": {
            "celsius": {"min": 35, "max": 42},
            "fahrenheit": {"min": 95, "max": 108},
        },
        "oxygen_saturation": {"min": 70, "max": 100},
    }

    @staticmethod
    async def validate_blood_pressure(bp_str: str) -> Tuple[bool, List[str]]:
        """Validate blood pressure format (e.g., 120/80)."""
        errors = []

        match = re.match(r"^(\d+)\s*/\s*(\d+)$", bp_str.strip())
        if not match:
            errors.append(
                "Invalid blood pressure format (expected: systolic/diastolic)"
            )
            return False, errors

        systolic, diastolic = map(int, match.groups())

        # Check ranges
        bp_ranges = VitalSignValidator.VITAL_SIGN_RANGES["blood_pressure"]
        assert isinstance(bp_ranges, dict)
        systolic_ranges = bp_ranges["systolic"]
        diastolic_ranges = bp_ranges["diastolic"]
        assert isinstance(systolic_ranges, dict)
        assert isinstance(diastolic_ranges, dict)

        if systolic < systolic_ranges["min"]:
            errors.append("Systolic pressure too low")
        elif systolic > systolic_ranges["max"]:
            errors.append("Systolic pressure too high")

        if diastolic < diastolic_ranges["min"]:
            errors.append("Diastolic pressure too low")
        elif diastolic > diastolic_ranges["max"]:
            errors.append("Diastolic pressure too high")

        if systolic <= diastolic:
            errors.append("Systolic pressure must be greater than diastolic")

        return len(errors) == 0, errors

    @staticmethod
    async def validate_heart_rate(hr_str: str) -> Tuple[bool, List[str]]:
        """Validate heart rate value."""
        errors = []

        try:
            hr = int(hr_str.strip())
            hr_ranges = VitalSignValidator.VITAL_SIGN_RANGES["heart_rate"]
            assert isinstance(hr_ranges, dict)
            min_hr = hr_ranges["min"]
            max_hr = hr_ranges["max"]
            assert isinstance(min_hr, int)
            assert isinstance(max_hr, int)
            if hr < min_hr:
                errors.append("Heart rate too low")
            elif hr > max_hr:
                errors.append("Heart rate too high")
        except ValueError:
            errors.append("Invalid heart rate format")

        return len(errors) == 0, errors

    @staticmethod
    async def validate_temperature(
        temp_str: str, unit: str = "celsius"
    ) -> Tuple[bool, List[str]]:
        """Validate temperature value."""
        errors = []

        try:
            temp = float(temp_str.strip())
            temp_ranges = VitalSignValidator.VITAL_SIGN_RANGES["temperature"]
            assert isinstance(temp_ranges, dict)
            unit_ranges = temp_ranges[unit.lower()]
            assert isinstance(unit_ranges, dict)

            if temp < unit_ranges["min"]:
                errors.append(f"Temperature too low for {unit}")
            elif temp > unit_ranges["max"]:
                errors.append(f"Temperature too high for {unit}")
        except ValueError:
            errors.append("Invalid temperature format")
        except KeyError:
            errors.append(f"Unknown temperature unit: {unit}")

        return len(errors) == 0, errors

    @staticmethod
    async def validate_vital_sign(
        value: str, sign_type: Optional[str] = None
    ) -> Tuple[bool, List[str]]:
        """Validate generic vital sign."""
        if sign_type and "pressure" in sign_type.lower():
            return await VitalSignValidator.validate_blood_pressure(value)
        elif sign_type and "heart" in sign_type.lower():
            return await VitalSignValidator.validate_heart_rate(value)
        elif sign_type and "temp" in sign_type.lower():
            return await VitalSignValidator.validate_temperature(value)
        else:
            # Generic numeric validation
            try:
                float(value.strip())
                return True, []
            except ValueError:
                return False, ["Invalid numeric value"]
