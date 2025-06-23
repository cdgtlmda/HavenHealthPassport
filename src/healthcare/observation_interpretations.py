"""Observation Interpretation Definitions.

This module defines interpretation codes and logic for clinical observations,
including standard interpretations and refugee-specific considerations for
resource-limited settings.
"""

import logging
from enum import Enum
from typing import Any, Dict, List, Literal, Optional, TypedDict, Union, cast

from src.healthcare.fhir_types import (
    FHIRTypedResource,
    validate_fhir_resource_type,
)
from src.healthcare.fhir_validator import FHIRValidator

# FHIR resource type for this module
__fhir_resource__ = "Observation"
__fhir_type__ = "Observation"

logger = logging.getLogger(__name__)


class FHIRObservationInterpretation(TypedDict, total=False):
    """FHIR Observation.interpretation type definition."""

    coding: List[Dict[str, str]]
    text: str
    __fhir_resource__: Literal["CodeableConcept"]


class FHIRObservationComponent(TypedDict, total=False):
    """FHIR Observation.component type definition."""

    code: Dict[str, Any]
    valueQuantity: Dict[str, Any]
    valueCodeableConcept: Dict[str, Any]
    valueString: str
    valueBoolean: bool
    valueInteger: int
    valueRange: Dict[str, Any]
    valueRatio: Dict[str, Any]
    valueSampledData: Dict[str, Any]
    valueTime: str
    valueDateTime: str
    valuePeriod: Dict[str, Any]
    interpretation: List[FHIRObservationInterpretation]
    referenceRange: List[Dict[str, Any]]
    __fhir_resource__: Literal["ObservationComponent"]


class FHIRObservationExtended(TypedDict, total=False):
    """Extended FHIR Observation resource type definition."""

    resourceType: Literal["Observation"]
    id: str
    identifier: List[Dict[str, Any]]
    basedOn: List[Dict[str, str]]
    partOf: List[Dict[str, str]]
    status: Literal[
        "registered",
        "preliminary",
        "final",
        "amended",
        "corrected",
        "cancelled",
        "entered-in-error",
        "unknown",
    ]
    category: List[Dict[str, Any]]
    code: Dict[str, Any]
    subject: Dict[str, str]
    focus: List[Dict[str, str]]
    encounter: Dict[str, str]
    effectiveDateTime: str
    effectivePeriod: Dict[str, str]
    effectiveTiming: Dict[str, Any]
    effectiveInstant: str
    issued: str
    performer: List[Dict[str, str]]
    valueQuantity: Dict[str, Any]
    valueCodeableConcept: Dict[str, Any]
    valueString: str
    valueBoolean: bool
    valueInteger: int
    valueRange: Dict[str, Any]
    valueRatio: Dict[str, Any]
    valueSampledData: Dict[str, Any]
    valueTime: str
    valueDateTime: str
    valuePeriod: Dict[str, Any]
    dataAbsentReason: Dict[str, Any]
    interpretation: List[FHIRObservationInterpretation]
    note: List[Dict[str, str]]
    bodySite: Dict[str, Any]
    method: Dict[str, Any]
    specimen: Dict[str, str]
    device: Dict[str, str]
    referenceRange: List[Dict[str, Any]]
    hasMember: List[Dict[str, str]]
    derivedFrom: List[Dict[str, str]]
    component: List[FHIRObservationComponent]
    __fhir_resource__: Literal["Observation"]


class ObservationInterpretation(Enum):
    """Standard observation interpretation codes from HL7."""

    # Abnormality codes
    ABNORMAL = "A"  # Abnormal
    ABNORMAL_ALERT = "AA"  # Critically abnormal
    HIGH = "H"  # High
    HIGH_ALERT = "HH"  # Critically high
    LOW = "L"  # Low
    LOW_ALERT = "LL"  # Critically low
    NORMAL = "N"  # Normal

    # Change codes
    BETTER = "B"  # Better
    DECREASED = "D"  # Significant decrease
    INCREASED = "U"  # Significant increase
    WORSE = "W"  # Worse

    # Susceptibility codes
    SUSCEPTIBLE = "S"  # Susceptible
    RESISTANT = "R"  # Resistant
    INTERMEDIATE = "I"  # Intermediate

    # Detection codes
    POSITIVE = "POS"  # Positive
    NEGATIVE = "NEG"  # Negative
    DETECTED = "DET"  # Detected
    NOT_DETECTED = "ND"  # Not detected
    INDETERMINATE = "IND"  # Indeterminate

    # Other codes
    EXPECTED = "E"  # Expected
    UNEXPECTED = "UNE"  # Unexpected
    OUTSIDE_RANGE = "OR"  # Outside reference range
    WITHIN_RANGE = "WR"  # Within reference range


class CriticalValueThreshold:
    """Critical value thresholds for common observations."""

    CRITICAL_VALUES = {
        # Vital signs
        "8310-5": {  # Body temperature
            "unit": "Cel",
            "critical_low": 35.0,
            "low": 36.0,
            "high": 38.0,
            "critical_high": 40.0,
            "pediatric_adjustments": {
                "infant": {"high": 37.5}  # Infants have lower fever threshold
            },
        },
        "8867-4": {  # Heart rate
            "unit": "/min",
            "critical_low": 40,
            "low": 60,
            "high": 100,
            "critical_high": 130,
            "age_adjustments": {
                "newborn": {"low": 100, "high": 160},
                "infant": {"low": 80, "high": 140},
                "child": {"low": 70, "high": 120},
            },
        },
        "9279-1": {  # Respiratory rate
            "unit": "/min",
            "critical_low": 8,
            "low": 12,
            "high": 20,
            "critical_high": 30,
            "age_adjustments": {
                "newborn": {"low": 30, "high": 60},
                "infant": {"low": 20, "high": 40},
                "child": {"low": 15, "high": 30},
            },
        },
        "8480-6": {  # Systolic blood pressure
            "unit": "mm[Hg]",
            "critical_low": 80,
            "low": 90,
            "high": 140,
            "critical_high": 180,
        },
        "8462-4": {  # Diastolic blood pressure
            "unit": "mm[Hg]",
            "critical_low": 50,
            "low": 60,
            "high": 90,
            "critical_high": 110,
        },
        "59408-5": {  # Oxygen saturation
            "unit": "%",
            "critical_low": 88,
            "low": 92,
            "high": 100,
            "critical_high": 100,
            "altitude_adjustment": True,  # Needs adjustment for high altitude
        },
        # Lab values
        "718-7": {  # Hemoglobin
            "unit": "g/dL",
            "critical_low": 7.0,
            "low": 12.0,
            "high": 16.0,
            "critical_high": 20.0,
            "gender_adjustments": {
                "male": {"low": 13.5, "high": 17.5},
                "female": {"low": 12.0, "high": 15.5},
            },
            "pregnancy_adjustments": {
                "pregnant": {"low": 11.0}  # Lower threshold in pregnancy
            },
        },
        "2345-7": {  # Glucose
            "unit": "mg/dL",
            "critical_low": 40,
            "low": 70,
            "high": 110,
            "critical_high": 300,
            "fasting_adjustments": {
                "fasting": {"high": 100},
                "post_meal": {"high": 140},
            },
        },
        # Nutrition indicators
        "56072-2": {  # MUAC (Mid-upper arm circumference)
            "unit": "cm",
            "critical_low": 11.0,  # Severe acute malnutrition
            "low": 12.5,  # Moderate acute malnutrition
            "high": 50.0,  # No upper concern
            "critical_high": None,
            "age_adjustments": {
                "child_6_59_months": {"critical_low": 11.5, "low": 12.5}
            },
        },
    }

    @classmethod
    def get_thresholds(
        cls, loinc_code: str, context: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict]:
        """Get threshold values for a specific observation.

        Args:
            loinc_code: LOINC code for the observation
            context: Optional context (age, gender, pregnancy status, etc.)

        Returns:
            Dictionary of threshold values or None
        """
        base_thresholds = cls.CRITICAL_VALUES.get(loinc_code)
        if not base_thresholds:
            return None

        # Make a copy to avoid modifying the original
        thresholds = cast(Dict[str, Any], base_thresholds.copy())

        if context:
            # Apply age adjustments
            if "age" in context and "age_adjustments" in base_thresholds:
                age_group = cls._determine_age_group(context["age"])
                age_adjustments = cast(
                    Dict[str, Any], base_thresholds["age_adjustments"]
                )
                if age_group in age_adjustments:
                    thresholds.update(age_adjustments[age_group])

            # Apply gender adjustments
            if "gender" in context and "gender_adjustments" in base_thresholds:
                gender_adjustments = cast(
                    Dict[str, Any], base_thresholds["gender_adjustments"]
                )
                if context["gender"] in gender_adjustments:
                    thresholds.update(gender_adjustments[context["gender"]])

            # Apply pregnancy adjustments
            if context.get("pregnant") and "pregnancy_adjustments" in base_thresholds:
                thresholds.update(
                    cast(Dict[str, Any], base_thresholds)["pregnancy_adjustments"][
                        "pregnant"
                    ]
                )

            # Apply altitude adjustments for oxygen saturation
            if context.get("altitude") and base_thresholds.get("altitude_adjustment"):
                # For every 1000m altitude, normal O2 sat drops by ~1-2%
                altitude_m = context["altitude"]
                adjustment = int(altitude_m / 1000) * 1.5
                thresholds["low"] = max(85, float(thresholds["low"]) - adjustment)
                thresholds["critical_low"] = max(
                    80, float(thresholds["critical_low"]) - adjustment
                )

        return thresholds

    @classmethod
    def _determine_age_group(cls, age: Union[int, float]) -> str:
        """Determine age group for threshold adjustments."""
        if age < 0.08:  # Less than 1 month
            return "newborn"
        elif age < 1:
            return "infant"
        elif age < 12:
            return "child"
        elif age < 18:
            return "adolescent"
        else:
            return "adult"


class InterpretationEngine(FHIRTypedResource):
    """Engine for interpreting observation values."""

    def __init__(self) -> None:
        """Initialize the interpretation engine."""
        self.fhir_validator = FHIRValidator()

    @property
    def __fhir_resource_type__(self) -> str:
        """Return the FHIR resource type."""
        return "Observation"

    @classmethod
    def interpret_value(
        cls,
        loinc_code: str,
        value: Union[float, int, str],
        _unit: Optional[str] = None,
        reference_range: Optional[Dict] = None,
        context: Optional[Dict] = None,
    ) -> List[ObservationInterpretation]:
        """Interpret an observation value.

        Args:
            loinc_code: LOINC code for the observation
            value: The observation value
            unit: Unit of measurement
            reference_range: Optional reference range
            context: Optional context (age, gender, etc.)

        Returns:
            List of applicable interpretation codes
        """
        interpretations = []

        # Handle string values (like positive/negative)
        if isinstance(value, str):
            return cls._interpret_string_value(value)

        # Get thresholds
        thresholds = CriticalValueThreshold.get_thresholds(loinc_code, context)

        # Use reference range if no standard thresholds
        if not thresholds and reference_range:
            thresholds = cls._convert_reference_range(reference_range)

        if not thresholds:
            return []  # Cannot interpret without thresholds

        # Interpret numeric value
        value_float = float(value)

        # Check critical values first
        if (
            thresholds.get("critical_low") is not None
            and value_float <= thresholds["critical_low"]
        ):
            interpretations.append(ObservationInterpretation.LOW_ALERT)
            interpretations.append(ObservationInterpretation.ABNORMAL_ALERT)
        elif (
            thresholds.get("critical_high") is not None
            and value_float >= thresholds["critical_high"]
        ):
            interpretations.append(ObservationInterpretation.HIGH_ALERT)
            interpretations.append(ObservationInterpretation.ABNORMAL_ALERT)
        # Check normal abnormal values
        elif thresholds.get("low") is not None and value_float < thresholds["low"]:
            interpretations.append(ObservationInterpretation.LOW)
            interpretations.append(ObservationInterpretation.ABNORMAL)
        elif thresholds.get("high") is not None and value_float > thresholds["high"]:
            interpretations.append(ObservationInterpretation.HIGH)
            interpretations.append(ObservationInterpretation.ABNORMAL)
        else:
            interpretations.append(ObservationInterpretation.NORMAL)

        return interpretations

    @classmethod
    def _interpret_string_value(cls, value: str) -> List[ObservationInterpretation]:
        """Interpret string observation values."""
        value_lower = value.lower()

        if value_lower in ["positive", "pos", "detected", "present"]:
            return [
                ObservationInterpretation.POSITIVE,
                ObservationInterpretation.DETECTED,
            ]
        elif value_lower in ["negative", "neg", "not detected", "absent"]:
            return [
                ObservationInterpretation.NEGATIVE,
                ObservationInterpretation.NOT_DETECTED,
            ]
        elif value_lower in ["indeterminate", "equivocal", "inconclusive"]:
            return [ObservationInterpretation.INDETERMINATE]
        else:
            return []

    @classmethod
    def _convert_reference_range(cls, reference_range: Dict) -> Dict:
        """Convert FHIR reference range to threshold format."""
        thresholds = {}

        if "low" in reference_range:
            thresholds["low"] = reference_range["low"].get("value")

        if "high" in reference_range:
            thresholds["high"] = reference_range["high"].get("value")

        return thresholds

    def validate_fhir(self) -> Dict[str, Any]:
        """Validate the FHIR resource (required by FHIRTypedResource)."""
        # This is a validator class, not a resource instance
        return {"valid": True, "errors": [], "warnings": []}

    def validate_fhir_observation(
        self, observation_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Validate FHIR Observation resource with interpretation.

        Args:
            observation_data: FHIR Observation resource data

        Returns:
            Validation result with 'valid', 'errors', and 'warnings' keys
        """
        # Ensure resource type
        if "resourceType" not in observation_data:
            observation_data["resourceType"] = "Observation"

        # Validate resource type
        if not validate_fhir_resource_type(observation_data):
            return {
                "valid": False,
                "errors": ["Invalid FHIR resource type"],
                "warnings": [],
            }

        # First validate using base FHIR validator
        validation_result = self.fhir_validator.validate_observation(observation_data)

        # Add interpretation-specific validation
        if "interpretation" in observation_data:
            interpretations = observation_data["interpretation"]
            if not isinstance(interpretations, list):
                interpretations = [interpretations]

            for interpretation in interpretations:
                if "coding" in interpretation:
                    for coding in interpretation["coding"]:
                        code = coding.get("code")
                        # Validate interpretation codes
                        try:
                            ObservationInterpretation(code)
                        except ValueError:
                            validation_result["warnings"].append(
                                f"Non-standard interpretation code: {code}"
                            )

        return validation_result

    @classmethod
    def interpret_trend(
        cls,
        current_value: float,
        previous_value: float,
        significant_change_percent: float = 20.0,
    ) -> List[ObservationInterpretation]:
        """Interpret trend between two values.

        Args:
            current_value: Current observation value
            previous_value: Previous observation value
            significant_change_percent: Percentage change considered significant

        Returns:
            List of trend interpretation codes
        """
        interpretations = []

        if previous_value == 0:
            return []  # Cannot calculate percentage change

        percent_change = ((current_value - previous_value) / previous_value) * 100

        if percent_change >= significant_change_percent:
            interpretations.append(ObservationInterpretation.INCREASED)
            if current_value > previous_value:
                interpretations.append(ObservationInterpretation.WORSE)
        elif percent_change <= -significant_change_percent:
            interpretations.append(ObservationInterpretation.DECREASED)
            if current_value < previous_value:
                interpretations.append(ObservationInterpretation.BETTER)

        return interpretations


class RefugeeContextInterpretation:
    """Interpretation adjustments for refugee contexts."""

    @staticmethod
    def adjust_for_malnutrition(
        loinc_code: str,
        interpretations: List[ObservationInterpretation],
        nutritional_status: Optional[str] = None,
    ) -> List[str]:
        """Add context notes for malnourished patients.

        Args:
            loinc_code: LOINC code for the observation
            interpretations: Base interpretations
            nutritional_status: Patient's nutritional status

        Returns:
            List of contextual notes
        """
        notes = []

        if nutritional_status in [
            "severe_acute_malnutrition",
            "moderate_acute_malnutrition",
        ]:
            # Certain values may be expected to be abnormal in malnutrition
            if loinc_code == "718-7":  # Hemoglobin
                if ObservationInterpretation.LOW in interpretations:
                    notes.append(
                        "Low hemoglobin common in malnutrition; consider iron supplementation"
                    )

            elif loinc_code == "777-3":  # Platelet count
                if ObservationInterpretation.LOW in interpretations:
                    notes.append(
                        "Thrombocytopenia may be related to nutritional deficiency"
                    )

        return notes

    @staticmethod
    def adjust_for_endemic_diseases(
        loinc_code: str,
        interpretations: List[ObservationInterpretation],
        endemic_diseases: List[str],
    ) -> List[str]:
        """Add context notes for endemic disease areas.

        Args:
            loinc_code: LOINC code for the observation
            interpretations: Base interpretations
            endemic_diseases: List of endemic diseases in the area

        Returns:
            List of contextual notes
        """
        notes = []

        if "malaria" in endemic_diseases:
            if (
                loinc_code == "777-3"
                and ObservationInterpretation.LOW in interpretations
            ):
                notes.append(
                    "Consider malaria testing given low platelet count in endemic area"
                )
            elif (
                loinc_code == "8310-5"
                and ObservationInterpretation.HIGH in interpretations
            ):
                notes.append(
                    "Fever in malaria-endemic area; consider rapid diagnostic test"
                )

        if "tuberculosis" in endemic_diseases:
            if (
                loinc_code == "9279-1"
                and ObservationInterpretation.HIGH in interpretations
            ):
                notes.append("Elevated respiratory rate; screen for TB in endemic area")

        return notes

    @staticmethod
    def flag_critical_for_camp_setting(
        interpretations: List[ObservationInterpretation],
    ) -> bool:
        """Determine if finding requires urgent action in camp setting.

        Args:
            interpretations: Observation interpretations

        Returns:
            True if requires urgent referral/action
        """
        critical_interpretations = [
            ObservationInterpretation.ABNORMAL_ALERT,
            ObservationInterpretation.HIGH_ALERT,
            ObservationInterpretation.LOW_ALERT,
        ]

        return any(interp in critical_interpretations for interp in interpretations)


def format_interpretation_display(
    interpretations: List[ObservationInterpretation],
) -> str:
    """Format interpretations for human-readable display.

    Args:
        interpretations: List of interpretation codes

    Returns:
        Formatted string
    """
    if not interpretations:
        return "No interpretation available"

    # Priority order for display
    priority_order = [
        ObservationInterpretation.ABNORMAL_ALERT,
        ObservationInterpretation.HIGH_ALERT,
        ObservationInterpretation.LOW_ALERT,
        ObservationInterpretation.ABNORMAL,
        ObservationInterpretation.HIGH,
        ObservationInterpretation.LOW,
        ObservationInterpretation.POSITIVE,
        ObservationInterpretation.NEGATIVE,
        ObservationInterpretation.NORMAL,
    ]

    # Find highest priority interpretation
    for interp in priority_order:
        if interp in interpretations:
            display_map = {
                ObservationInterpretation.ABNORMAL_ALERT: "⚠️ CRITICAL",
                ObservationInterpretation.HIGH_ALERT: "⚠️ CRITICALLY HIGH",
                ObservationInterpretation.LOW_ALERT: "⚠️ CRITICALLY LOW",
                ObservationInterpretation.ABNORMAL: "Abnormal",
                ObservationInterpretation.HIGH: "High",
                ObservationInterpretation.LOW: "Low",
                ObservationInterpretation.POSITIVE: "Positive",
                ObservationInterpretation.NEGATIVE: "Negative",
                ObservationInterpretation.NORMAL: "Normal",
            }
            return display_map.get(interp, interp.value)

    # Default to first interpretation
    return interpretations[0].value
