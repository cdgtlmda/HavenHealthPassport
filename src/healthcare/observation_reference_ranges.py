"""Observation Reference Ranges.

This module defines reference ranges for clinical observations with support
for age, gender, pregnancy, and population-specific adjustments relevant
to refugee healthcare contexts.
Handles FHIR Observation Resource validation.

COMPLIANCE NOTE: This module processes PHI including clinical observations,
lab results, and patient-specific reference ranges. All PHI data must be
encrypted at rest and in transit. Access control must be enforced - only
authorized healthcare providers should access patient observation data.
Reference ranges may contain sensitive health information.
"""

import logging
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

# FHIR resource type for this module
__fhir_resource__ = "ObservationDefinition"

logger = logging.getLogger(__name__)


class ReferenceRangeType(Enum):
    """Types of reference ranges."""

    NORMAL = "normal"  # Normal/healthy range
    THERAPEUTIC = "therapeutic"  # Therapeutic target range
    CRITICAL = "critical"  # Critical value thresholds
    TREATMENT = "treatment"  # Treatment decision thresholds
    POPULATION = "population"  # Population-specific range
    CONDITIONAL = "conditional"  # Conditional range (e.g., fasting)


class PopulationCategory(Enum):
    """Population categories for reference ranges."""

    # Age groups
    NEONATE = "neonate"  # 0-28 days
    INFANT = "infant"  # 1-12 months
    TODDLER = "toddler"  # 1-3 years
    PRESCHOOL = "preschool"  # 3-5 years
    SCHOOL_AGE = "school-age"  # 5-12 years
    ADOLESCENT = "adolescent"  # 12-18 years
    ADULT = "adult"  # 18-65 years
    ELDERLY = "elderly"  # 65+ years

    # Gender
    MALE = "male"
    FEMALE = "female"

    # Physiological states
    PREGNANT = "pregnant"
    LACTATING = "lactating"

    # Nutritional states
    MALNOURISHED = "malnourished"
    WELL_NOURISHED = "well-nourished"

    # Geographic/ethnic
    SUB_SAHARAN_AFRICAN = "sub-saharan-african"
    MIDDLE_EASTERN = "middle-eastern"
    SOUTH_ASIAN = "south-asian"
    EAST_ASIAN = "east-asian"

    # Environmental
    HIGH_ALTITUDE = "high-altitude"
    TROPICAL = "tropical"
    DESERT = "desert"


class ReferenceRange:
    """Represents a reference range for an observation."""

    # FHIR resource type
    __fhir_resource__ = "ObservationDefinition"

    def __init__(
        self,
        low: Optional[float] = None,
        high: Optional[float] = None,
        text: Optional[str] = None,
    ):
        """Initialize reference range.

        Args:
            low: Lower bound (inclusive)
            high: Upper bound (inclusive)
            text: Text description of range
        """
        self.low = low
        self.high = high
        self.text = text
        self.type = ReferenceRangeType.NORMAL
        self.unit: Optional[str] = None
        self.applies_to: List[PopulationCategory] = []
        self.age_range: Optional[Tuple[float, float]] = None  # Age in years
        self.conditions: List[str] = []  # e.g., "fasting", "post-meal"

    def set_type(self, range_type: ReferenceRangeType) -> "ReferenceRange":
        """Set reference range type."""
        self.type = range_type
        return self

    def set_unit(self, unit: str) -> "ReferenceRange":
        """Set unit of measurement."""
        self.unit = unit
        return self

    def add_population(self, population: PopulationCategory) -> "ReferenceRange":
        """Add applicable population category."""
        if population not in self.applies_to:
            self.applies_to.append(population)
        return self

    def set_age_range(self, min_age: float, max_age: float) -> "ReferenceRange":
        """Set age range in years."""
        self.age_range = (min_age, max_age)
        return self

    def add_condition(self, condition: str) -> "ReferenceRange":
        """Add condition for this range (e.g., fasting)."""
        if condition not in self.conditions:
            self.conditions.append(condition)
        return self

    def contains(self, value: float) -> bool:
        """Check if value is within range."""
        if self.low is not None and value < self.low:
            return False
        if self.high is not None and value > self.high:
            return False
        return True

    def to_fhir(self) -> Dict[str, Any]:
        """Convert to FHIR reference range structure."""
        fhir_range: Dict[str, Any] = {}

        if self.low is not None:
            fhir_range["low"] = {
                "value": self.low,
                "unit": self.unit,
                "system": "http://unitsofmeasure.org",
                "code": self.unit,
            }

        if self.high is not None:
            fhir_range["high"] = {
                "value": self.high,
                "unit": self.unit,
                "system": "http://unitsofmeasure.org",
                "code": self.unit,
            }

        if self.text:
            fhir_range["text"] = self.text

        # Add type
        fhir_range["type"] = {
            "coding": [
                {
                    "system": "http://terminology.hl7.org/CodeSystem/referencerange-meaning",
                    "code": self.type.value,
                }
            ]
        }

        # Add applicable populations
        if self.applies_to:
            fhir_range["appliesTo"] = []
            for pop in self.applies_to:
                fhir_range["appliesTo"].append(
                    {
                        "coding": [
                            {
                                "system": "http://havenhealthpassport.org/fhir/CodeSystem/population-category",
                                "code": pop.value,
                                "display": pop.value.replace("-", " ").title(),
                            }
                        ]
                    }
                )

        # Add age range
        if self.age_range:
            fhir_range["age"] = {
                "low": {
                    "value": self.age_range[0],
                    "unit": "a",  # years
                    "system": "http://unitsofmeasure.org",
                    "code": "a",
                },
                "high": {
                    "value": self.age_range[1],
                    "unit": "a",
                    "system": "http://unitsofmeasure.org",
                    "code": "a",
                },
            }

        return fhir_range

    def validate_fhir(self, reference_range_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate FHIR reference range data.

        Args:
            reference_range_data: FHIR reference range data

        Returns:
            Validation result with 'valid', 'errors', and 'warnings' keys
        """
        errors = []
        warnings = []

        # Check for at least one bound
        if not reference_range_data.get("low") and not reference_range_data.get("high"):
            warnings.append("Reference range should have at least low or high bound")

        # Validate low bound if present
        if "low" in reference_range_data:
            low = reference_range_data["low"]
            if not isinstance(low, dict) or "value" not in low:
                errors.append("Low bound must have value")
            elif not isinstance(low["value"], (int, float)):
                errors.append("Low bound value must be numeric")

        # Validate high bound if present
        if "high" in reference_range_data:
            high = reference_range_data["high"]
            if not isinstance(high, dict) or "value" not in high:
                errors.append("High bound must have value")
            elif not isinstance(high["value"], (int, float)):
                errors.append("High bound value must be numeric")

        # Check logical consistency
        if (
            "low" in reference_range_data
            and "high" in reference_range_data
            and isinstance(reference_range_data["low"], dict)
            and isinstance(reference_range_data["high"], dict)
        ):
            low_val = reference_range_data["low"].get("value")
            high_val = reference_range_data["high"].get("value")
            if (
                isinstance(low_val, (int, float))
                and isinstance(high_val, (int, float))
                and low_val > high_val
            ):
                errors.append("Low bound cannot be greater than high bound")

        return {"valid": len(errors) == 0, "errors": errors, "warnings": warnings}


class ReferenceRangeRepository:
    """Repository of reference ranges for common observations."""

    # Reference ranges organized by LOINC code
    REFERENCE_RANGES = {
        # Vital Signs
        "8310-5": [  # Body temperature
            ReferenceRange(36.1, 37.2, "Normal body temperature")
            .set_unit("Cel")
            .add_population(PopulationCategory.ADULT),
            ReferenceRange(36.4, 37.5, "Normal body temperature - infant")
            .set_unit("Cel")
            .add_population(PopulationCategory.INFANT)
            .set_age_range(0, 1),
        ],
        "8867-4": [  # Heart rate
            ReferenceRange(60, 100, "Normal resting heart rate")
            .set_unit("/min")
            .add_population(PopulationCategory.ADULT),
            ReferenceRange(100, 160, "Normal heart rate - newborn")
            .set_unit("/min")
            .add_population(PopulationCategory.NEONATE)
            .set_age_range(0, 0.08),
            ReferenceRange(80, 140, "Normal heart rate - infant")
            .set_unit("/min")
            .add_population(PopulationCategory.INFANT)
            .set_age_range(0.08, 1),
            ReferenceRange(70, 120, "Normal heart rate - child")
            .set_unit("/min")
            .add_population(PopulationCategory.SCHOOL_AGE)
            .set_age_range(5, 12),
        ],
        "9279-1": [  # Respiratory rate
            ReferenceRange(12, 20, "Normal respiratory rate")
            .set_unit("/min")
            .add_population(PopulationCategory.ADULT),
            ReferenceRange(30, 60, "Normal respiratory rate - newborn")
            .set_unit("/min")
            .add_population(PopulationCategory.NEONATE),
            ReferenceRange(20, 40, "Normal respiratory rate - infant")
            .set_unit("/min")
            .add_population(PopulationCategory.INFANT),
        ],
        "8480-6": [  # Systolic blood pressure
            ReferenceRange(90, 120, "Normal systolic BP")
            .set_unit("mm[Hg]")
            .add_population(PopulationCategory.ADULT),
            ReferenceRange(120, 139, "Elevated systolic BP")
            .set_unit("mm[Hg]")
            .set_type(ReferenceRangeType.TREATMENT)
            .add_population(PopulationCategory.ADULT),
            ReferenceRange(140, 180, "Hypertensive systolic BP")
            .set_unit("mm[Hg]")
            .set_type(ReferenceRangeType.TREATMENT)
            .add_population(PopulationCategory.ADULT),
        ],
        "59408-5": [  # Oxygen saturation
            ReferenceRange(95, 100, "Normal oxygen saturation")
            .set_unit("%")
            .add_population(PopulationCategory.ADULT),
            ReferenceRange(92, 100, "Normal O2 sat at altitude")
            .set_unit("%")
            .add_population(PopulationCategory.HIGH_ALTITUDE)
            .add_condition("altitude>2500m"),
        ],
        # Anthropometry
        "56072-2": [  # Mid-upper arm circumference (MUAC)
            ReferenceRange(12.5, 50, "Normal MUAC")
            .set_unit("cm")
            .add_population(PopulationCategory.SCHOOL_AGE)
            .set_age_range(5, 18),
            ReferenceRange(11.5, 12.5, "Moderate acute malnutrition")
            .set_unit("cm")
            .set_type(ReferenceRangeType.TREATMENT)
            .add_population(PopulationCategory.SCHOOL_AGE)
            .set_age_range(0.5, 5),
            ReferenceRange(0, 11.5, "Severe acute malnutrition")
            .set_unit("cm")
            .set_type(ReferenceRangeType.CRITICAL)
            .add_population(PopulationCategory.SCHOOL_AGE)
            .set_age_range(0.5, 5),
        ],
        # Laboratory - Hematology
        "718-7": [  # Hemoglobin
            ReferenceRange(13.5, 17.5, "Normal hemoglobin - male")
            .set_unit("g/dL")
            .add_population(PopulationCategory.ADULT)
            .add_population(PopulationCategory.MALE),
            ReferenceRange(12.0, 15.5, "Normal hemoglobin - female")
            .set_unit("g/dL")
            .add_population(PopulationCategory.ADULT)
            .add_population(PopulationCategory.FEMALE),
            ReferenceRange(11.0, 15.5, "Normal hemoglobin - pregnancy")
            .set_unit("g/dL")
            .add_population(PopulationCategory.PREGNANT),
            ReferenceRange(9.5, 13.5, "Normal hemoglobin - infant")
            .set_unit("g/dL")
            .add_population(PopulationCategory.INFANT)
            .set_age_range(0.5, 2),
            # Population-specific ranges
            ReferenceRange(11.5, 16.5, "Normal hemoglobin - Sub-Saharan African")
            .set_unit("g/dL")
            .add_population(PopulationCategory.SUB_SAHARAN_AFRICAN)
            .set_type(ReferenceRangeType.POPULATION),
        ],
        "777-3": [  # Platelet count
            ReferenceRange(150, 400, "Normal platelet count")
            .set_unit("10*3/uL")
            .add_population(PopulationCategory.ADULT),
            ReferenceRange(100, 400, "Normal platelets - tropical regions")
            .set_unit("10*3/uL")
            .add_population(PopulationCategory.TROPICAL)
            .set_type(ReferenceRangeType.POPULATION),
        ],
        # Laboratory - Chemistry
        "2345-7": [  # Glucose
            ReferenceRange(70, 100, "Normal fasting glucose")
            .set_unit("mg/dL")
            .add_condition("fasting")
            .add_population(PopulationCategory.ADULT),
            ReferenceRange(70, 140, "Normal random glucose")
            .set_unit("mg/dL")
            .add_condition("random")
            .add_population(PopulationCategory.ADULT),
            ReferenceRange(100, 125, "Prediabetic fasting glucose")
            .set_unit("mg/dL")
            .set_type(ReferenceRangeType.TREATMENT)
            .add_condition("fasting")
            .add_population(PopulationCategory.ADULT),
        ],
        "2160-0": [  # Creatinine
            ReferenceRange(0.7, 1.3, "Normal creatinine - male")
            .set_unit("mg/dL")
            .add_population(PopulationCategory.ADULT)
            .add_population(PopulationCategory.MALE),
            ReferenceRange(0.6, 1.1, "Normal creatinine - female")
            .set_unit("mg/dL")
            .add_population(PopulationCategory.ADULT)
            .add_population(PopulationCategory.FEMALE),
            ReferenceRange(0.3, 0.7, "Normal creatinine - child")
            .set_unit("mg/dL")
            .add_population(PopulationCategory.SCHOOL_AGE)
            .set_age_range(5, 12),
        ],
        # Nutritional markers
        "1989-3": [  # Vitamin D
            ReferenceRange(30, 100, "Normal vitamin D")
            .set_unit("ng/mL")
            .add_population(PopulationCategory.ADULT),
            ReferenceRange(20, 30, "Vitamin D insufficiency")
            .set_unit("ng/mL")
            .set_type(ReferenceRangeType.TREATMENT),
            ReferenceRange(0, 20, "Vitamin D deficiency")
            .set_unit("ng/mL")
            .set_type(ReferenceRangeType.TREATMENT),
        ],
    }

    @classmethod
    def get_ranges(
        cls, loinc_code: str, context: Optional[Dict[str, Any]] = None
    ) -> List[ReferenceRange]:
        """Get applicable reference ranges for an observation.

        Args:
            loinc_code: LOINC code for the observation
            context: Optional context (age, gender, conditions, etc.)

        Returns:
            List of applicable reference ranges
        """
        all_ranges = cls.REFERENCE_RANGES.get(loinc_code, [])

        if not context:
            # Return default adult ranges
            return [
                r
                for r in all_ranges
                if PopulationCategory.ADULT in r.applies_to or not r.applies_to
            ]

        applicable_ranges = []

        for range_obj in all_ranges:
            if cls._is_range_applicable(range_obj, context):
                applicable_ranges.append(range_obj)

        # If no specific ranges found, return general ones
        if not applicable_ranges:
            applicable_ranges = [r for r in all_ranges if not r.applies_to]

        return applicable_ranges

    @classmethod
    def _is_range_applicable(
        cls, range_obj: ReferenceRange, context: Dict[str, Any]
    ) -> bool:
        """Check if a reference range applies to the given context."""
        # Check age
        if range_obj.age_range and "age" in context:
            age = context["age"]
            if not range_obj.age_range[0] <= age <= range_obj.age_range[1]:
                return False

        # Check population categories
        if range_obj.applies_to:
            # Map context to population categories
            context_populations = cls._get_context_populations(context)

            # Check if any required population matches
            if not any(pop in context_populations for pop in range_obj.applies_to):
                return False

        # Check conditions
        if range_obj.conditions:
            context_conditions = context.get("conditions", [])
            if not any(cond in context_conditions for cond in range_obj.conditions):
                return False

        return True

    @classmethod
    def _get_context_populations(
        cls, context: Dict[str, Any]
    ) -> List[PopulationCategory]:
        """Convert context to population categories."""
        populations = []

        # Age-based populations
        if "age" in context:
            age = context["age"]
            if age < 0.08:
                populations.append(PopulationCategory.NEONATE)
            elif age < 1:
                populations.append(PopulationCategory.INFANT)
            elif age < 3:
                populations.append(PopulationCategory.TODDLER)
            elif age < 5:
                populations.append(PopulationCategory.PRESCHOOL)
            elif age < 12:
                populations.append(PopulationCategory.SCHOOL_AGE)
            elif age < 18:
                populations.append(PopulationCategory.ADOLESCENT)
            elif age < 65:
                populations.append(PopulationCategory.ADULT)
            else:
                populations.append(PopulationCategory.ELDERLY)

        # Gender
        if "gender" in context:
            if context["gender"] == "male":
                populations.append(PopulationCategory.MALE)
            elif context["gender"] == "female":
                populations.append(PopulationCategory.FEMALE)

        # Physiological states
        if context.get("pregnant"):
            populations.append(PopulationCategory.PREGNANT)
        if context.get("lactating"):
            populations.append(PopulationCategory.LACTATING)

        # Nutritional status
        if "nutritional_status" in context:
            if context["nutritional_status"] == "malnourished":
                populations.append(PopulationCategory.MALNOURISHED)
            elif context["nutritional_status"] == "well_nourished":
                populations.append(PopulationCategory.WELL_NOURISHED)

        # Geographic/ethnic
        if "ethnicity" in context:
            ethnicity_map = {
                "sub_saharan_african": PopulationCategory.SUB_SAHARAN_AFRICAN,
                "middle_eastern": PopulationCategory.MIDDLE_EASTERN,
                "south_asian": PopulationCategory.SOUTH_ASIAN,
                "east_asian": PopulationCategory.EAST_ASIAN,
            }
            if context["ethnicity"] in ethnicity_map:
                populations.append(ethnicity_map[context["ethnicity"]])

        # Environmental
        if context.get("altitude", 0) > 2500:
            populations.append(PopulationCategory.HIGH_ALTITUDE)
        if context.get("climate") == "tropical":
            populations.append(PopulationCategory.TROPICAL)
        if context.get("climate") == "desert":
            populations.append(PopulationCategory.DESERT)

        return populations


class ReferenceRangeBuilder:
    """Builder for creating custom reference ranges."""

    def __init__(self) -> None:
        """Initialize builder."""
        self.ranges: List[ReferenceRange] = []

    def add_range(
        self,
        low: Optional[float] = None,
        high: Optional[float] = None,
        text: Optional[str] = None,
    ) -> ReferenceRange:
        """Add a new reference range."""
        range_obj = ReferenceRange(low, high, text)
        self.ranges.append(range_obj)
        return range_obj

    def add_percentile_ranges(
        self, percentiles: Dict[int, float], unit: str
    ) -> "ReferenceRangeBuilder":
        """Add percentile-based ranges (e.g., growth charts).

        Args:
            percentiles: Dictionary mapping percentile to value
            unit: Unit of measurement
        """
        # Add ranges for standard percentile brackets
        if 3 in percentiles and 97 in percentiles:
            self.add_range(
                percentiles[3], percentiles[97], "3rd-97th percentile"
            ).set_unit(unit).set_type(ReferenceRangeType.POPULATION)

        if 10 in percentiles and 90 in percentiles:
            self.add_range(
                percentiles[10], percentiles[90], "10th-90th percentile"
            ).set_unit(unit).set_type(ReferenceRangeType.NORMAL)

        return self

    def add_z_score_ranges(
        self, mean: float, sd: float, unit: str
    ) -> "ReferenceRangeBuilder":
        """Add z-score based ranges.

        Args:
            mean: Population mean
            sd: Standard deviation
            unit: Unit of measurement
        """
        # Normal range: -2 to +2 SD
        self.add_range(mean - 2 * sd, mean + 2 * sd, "Normal (-2 to +2 SD)").set_unit(
            unit
        ).set_type(ReferenceRangeType.NORMAL)

        # Moderate abnormal: -3 to -2 SD or +2 to +3 SD
        self.add_range(
            mean - 3 * sd, mean - 2 * sd, "Moderately low (-3 to -2 SD)"
        ).set_unit(unit).set_type(ReferenceRangeType.TREATMENT)

        self.add_range(
            mean + 2 * sd, mean + 3 * sd, "Moderately high (+2 to +3 SD)"
        ).set_unit(unit).set_type(ReferenceRangeType.TREATMENT)

        # Severe abnormal: < -3 SD or > +3 SD
        self.add_range(None, mean - 3 * sd, "Severely low (< -3 SD)").set_unit(
            unit
        ).set_type(ReferenceRangeType.CRITICAL)

        self.add_range(mean + 3 * sd, None, "Severely high (> +3 SD)").set_unit(
            unit
        ).set_type(ReferenceRangeType.CRITICAL)

        return self

    def build(self) -> List[ReferenceRange]:
        """Build and return the reference ranges."""
        return self.ranges


def select_best_range(
    ranges: List[ReferenceRange], value: float
) -> Optional[ReferenceRange]:
    """Select the most specific applicable range for a value.

    Args:
        ranges: List of reference ranges
        value: The observation value

    Returns:
        Most specific range containing the value, or None
    """
    # Filter to ranges containing the value
    containing_ranges = [r for r in ranges if r.contains(value)]

    if not containing_ranges:
        return None

    # Prioritize by type
    type_priority = [
        ReferenceRangeType.CRITICAL,
        ReferenceRangeType.TREATMENT,
        ReferenceRangeType.THERAPEUTIC,
        ReferenceRangeType.POPULATION,
        ReferenceRangeType.CONDITIONAL,
        ReferenceRangeType.NORMAL,
    ]

    for range_type in type_priority:
        typed_ranges = [r for r in containing_ranges if r.type == range_type]
        if typed_ranges:
            # Return the most specific (narrowest) range
            return min(
                typed_ranges,
                key=lambda r: (r.high or float("inf")) - (r.low or float("-inf")),
            )

    return containing_ranges[0]
