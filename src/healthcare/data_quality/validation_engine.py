"""Healthcare Data Validation Engine.

This module implements the validation engine that applies validation rules
to healthcare data, with support for complex validation scenarios specific
to refugee healthcare. Handles encrypted PHI data with proper access control.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Dict, List, Literal, Optional, Set, TypedDict

from src.config import settings
from src.healthcare.drug_interaction_service import get_drug_interaction_service
from src.healthcare.hipaa_access_control import (
    AccessLevel,
    audit_phi_access,
    require_phi_access,
)

from .validation_rules import (
    DateRule,
    FormatRule,
    RangeRule,
    RequiredFieldRule,
    ValidationCategory,
    ValidationResult,
    ValidationRule,
    ValidationSeverity,
)

logger = logging.getLogger(__name__)

# FHIR resource type for this module - validates multiple resource types
__fhir_resource__ = "OperationOutcome"


@dataclass
class ValidationContext:
    """Context for data validation including patient demographics and medical history."""

    # Patient demographics
    patient_id: Optional[str] = None
    patient_age: Optional[int] = None
    patient_gender: Optional[str] = None
    patient_ethnicity: Optional[str] = None

    # Medical history
    existing_medications: List[Dict[str, Any]] = field(default_factory=list)
    allergies: List[Dict[str, Any]] = field(default_factory=list)
    conditions: List[Dict[str, Any]] = field(default_factory=list)

    # Cultural/religious context
    cultural_background: Optional[str] = None
    religious_affiliation: Optional[str] = None
    dietary_restrictions: List[str] = field(default_factory=list)

    # Clinical context
    clinical_setting: Optional[str] = None  # emergency, primary_care, specialist
    provider_specialty: Optional[str] = None

    # Temporal context
    current_date: datetime = field(default_factory=datetime.now)
    admission_date: Optional[datetime] = None

    # Geographic context
    country_of_origin: Optional[str] = None
    current_location: Optional[str] = None
    camp_location: Optional[str] = None


class FHIRValidationResource(TypedDict):
    """FHIR Validation resource type."""

    resourceType: Literal["OperationOutcome", "Parameters"]
    issue: List[Dict[str, Any]]


class ValidationEngine:
    """Engine for executing validation rules on healthcare data."""

    # FHIR resource types this engine validates
    SUPPORTED_FHIR_RESOURCES: List[
        Literal["Patient", "Observation", "MedicationRequest", "Condition"]
    ] = ["Patient", "Observation", "MedicationRequest", "Condition"]

    def __init__(self) -> None:
        """Initialize validation engine."""
        self.rules: Dict[str, List[ValidationRule]] = {}
        self.rule_sets: Dict[str, Set[str]] = {}
        self.validation_cache: Dict[str, ValidationResult] = {}
        self._initialize_standard_rules()

    def _initialize_standard_rules(self) -> None:
        """Initialize standard healthcare validation rules."""
        # Patient validation rules
        self.add_rule_set(
            "patient",
            [
                RequiredFieldRule("patient_id"),
                RequiredFieldRule("family_name"),
                RequiredFieldRule("given_name"),
                FormatRule(
                    "patient_id",
                    r"^[A-Z0-9\-]+$",
                    "Alphanumeric with hyphens",
                    "PAT-12345",
                ),
                DateRule("birth_date", min_date=date(1900, 1, 1), allow_future=False),
                FormatRule("gender", r"^[MFO]$", "M (Male), F (Female), or O (Other)"),
                FormatRule(
                    "phone",
                    r"^\+?[\d\s\-\(\)]+$",
                    "Valid phone number format",
                    "+1 (555) 123-4567",
                ),
                FormatRule(
                    "email",
                    r"^[^\s@]+@[^\s@]+\.[^\s@]+$",
                    "Valid email format",
                    "patient@example.com",
                ),
            ],
        )

        # Vital signs validation rules
        self.add_rule_set(
            "vital_signs",
            [
                RangeRule("temperature", 35.0, 42.0),  # Celsius
                RangeRule("heart_rate", 30, 250),  # BPM
                RangeRule("blood_pressure_systolic", 60, 250),  # mmHg
                RangeRule("blood_pressure_diastolic", 30, 150),  # mmHg
                RangeRule("respiratory_rate", 8, 60),  # per minute
                RangeRule("oxygen_saturation", 0, 100),  # percentage
                RangeRule("weight", 0.5, 500),  # kg
                RangeRule("height", 30, 250),  # cm
            ],
        )

        # Laboratory results validation
        self.add_rule_set(
            "lab_results",
            [
                RequiredFieldRule("test_code"),
                RequiredFieldRule("value"),
                RequiredFieldRule("unit"),
                DateRule("collection_date", allow_future=False),
                DateRule("result_date", allow_future=False),
            ],
        )

        # Medication validation
        self.add_rule_set(
            "medication",
            [
                RequiredFieldRule("medication_name"),
                RequiredFieldRule("dosage"),
                RequiredFieldRule("frequency"),
                FormatRule(
                    "dosage",
                    r"^\d+(\.\d+)?\s*\w+$",
                    "Number followed by unit",
                    "500 mg",
                ),
            ],
        )

        # Diagnosis validation
        self.add_rule_set(
            "diagnosis",
            [
                RequiredFieldRule("diagnosis_code"),
                RequiredFieldRule("diagnosis_date"),
                DateRule("diagnosis_date", allow_future=False),
                FormatRule(
                    "diagnosis_code",
                    r"^[A-Z]\d{2}(\.\d{1,4})?$",
                    "ICD-10 format",
                    "A15.0",
                ),
            ],
        )

    def add_rule(self, field_name: str, rule: ValidationRule) -> None:
        """Add a validation rule for a field.

        Args:
            field_name: Field to validate
            rule: Validation rule
        """
        if field_name not in self.rules:
            self.rules[field_name] = []
        self.rules[field_name].append(rule)

    def add_rule_set(self, set_name: str, rules: List[ValidationRule]) -> None:
        """Add a named set of validation rules.

        Args:
            set_name: Name of the rule set
            rules: List of validation rules
        """
        if set_name not in self.rule_sets:
            self.rule_sets[set_name] = set()

        for rule in rules:
            field_name = getattr(rule, "field_name", rule.name)
            self.add_rule(field_name, rule)
            self.rule_sets[set_name].add(field_name)

    @require_phi_access(AccessLevel.READ)
    @audit_phi_access("validate_patient_field")
    def validate_field(
        self, field_name: str, value: Any, context: Optional[Dict] = None
    ) -> List[ValidationResult]:
        """Validate a single field.

        Args:
            field_name: Field name
            value: Field value
            context: Optional context data

        Returns:
            List of validation results
        """
        results = []

        if field_name in self.rules:
            for rule in self.rules[field_name]:
                result = rule.validate(value, context)
                results.append(result)

        return results

    @require_phi_access(AccessLevel.READ)
    @audit_phi_access("validate_patient_data")
    def validate_data(
        self,
        data: Dict[str, Any],
        rule_set: Optional[str] = None,
        context: Optional[ValidationContext] = None,
    ) -> Dict[str, List[ValidationResult]]:
        """Validate a data dictionary.

        Args:
            data: Data to validate
            rule_set: Optional rule set to use
            context: Optional context data

        Returns:
            Dictionary of field names to validation results
        """
        results = {}

        # Determine which fields to validate
        if rule_set and rule_set in self.rule_sets:
            fields_to_validate = self.rule_sets[rule_set]
        else:
            fields_to_validate = set(self.rules.keys())

        # Validate each field
        for field_name in fields_to_validate:
            value = data.get(field_name)
            field_results = self.validate_field(field_name, value, context)
            if field_results:
                results[field_name] = field_results

        # Add cross-field validation
        cross_field_results = self._validate_cross_field(data, context)
        if cross_field_results:
            results["_cross_field"] = cross_field_results

        return results

    def _validate_cross_field(
        self, data: Dict[str, Any], context: Optional[ValidationContext] = None
    ) -> List[ValidationResult]:
        """Perform cross-field validation.

        Args:
            data: Data to validate
            context: Optional validation context

        Returns:
            List of validation results
        """
        # Implement context-aware cross-field validation
        results = []

        # Use context for conditional validations if provided
        if context:
            # Pregnancy-related validations
            if context.patient_gender == "male" and (
                data.get("pregnancy_status") or data.get("pregnancy_test_result")
            ):
                results.append(
                    ValidationResult(
                        field="pregnancy_status",
                        rule="gender_pregnancy_consistency",
                        is_valid=False,
                        message="Pregnancy status not applicable for male patients",
                        severity=ValidationSeverity.ERROR,
                        category=ValidationCategory.CONSISTENCY,
                    )
                )

            # Age-related validations
            if context.patient_age is not None:
                # Medicare age validation
                if context.patient_age < 18 and data.get("medicare_number"):
                    results.append(
                        ValidationResult(
                            field="medicare_number",
                            rule="age_medicare_eligibility",
                            is_valid=False,
                            message="Medicare typically not available for patients under 18",
                            severity=ValidationSeverity.WARNING,
                            category=ValidationCategory.DEMOGRAPHIC,
                        )
                    )

                # Pediatric medication warnings
                if context.patient_age < 12 and "medications" in data:
                    results.extend(
                        self._check_pediatric_medication_safety(
                            data.get("medications", []), context.patient_age
                        )
                    )

            # Medication interaction checks
            if "medications" in data and (
                context.existing_medications or context.allergies
            ):
                # TODO: Move _check_medication_interactions to ValidationEngine
                # interaction_results = self._check_medication_interactions(
                #     data.get("medications", []),
                #     context.existing_medications,
                #     context.allergies,
                # )
                # results.extend(interaction_results)
                pass

            # Cultural and religious considerations
            if context.cultural_background or context.religious_affiliation:
                # TODO: Move _check_cultural_compatibility to ValidationEngine
                # cultural_results = self._check_cultural_compatibility(data, context)
                # results.extend(cultural_results)
                pass

            # Temporal validations
            # TODO: Move _validate_temporal_consistency to ValidationEngine
            # temporal_results = self._validate_temporal_consistency(data, context)
            # results.extend(temporal_results)

            # Medication interaction checks
            existing_medications = context.existing_medications if context else []
            allergies = context.allergies if context else []

            if "medications" in data and (existing_medications or allergies):
                new_medications = data.get("medications", [])

                # Check for duplicate medications
                for new_med in new_medications:
                    new_med_name = (
                        new_med.get("name", "").lower()
                        if isinstance(new_med, dict)
                        else str(new_med).lower()
                    )

                    for existing_med in existing_medications:
                        existing_name = existing_med.get("name", "").lower()
                        if new_med_name == existing_name:
                            results.append(
                                ValidationResult(
                                    field="medications",
                                    rule="duplicate_medication",
                                    is_valid=False,
                                    message=f"Patient already taking {new_med_name}",
                                    severity=ValidationSeverity.ERROR,
                                    category=ValidationCategory.CLINICAL,
                                )
                            )

                    # Check allergies
                    for allergy in allergies:
                        allergy_name = allergy.get("name", "").lower()
                        if allergy_name in new_med_name or new_med_name in allergy_name:
                            results.append(
                                ValidationResult(
                                    field="medications",
                                    rule="allergy_contraindication",
                                    is_valid=False,
                                    message=f"Patient has allergy to {allergy_name}",
                                    severity=ValidationSeverity.ERROR,
                                    category=ValidationCategory.CLINICAL,
                                )
                            )

            # Cultural/religious considerations
            if context and context.dietary_restrictions:
                dietary_restrictions = context.dietary_restrictions

                if dietary_restrictions and "medications" in data:
                    medications = data.get("medications", [])

                    for med in medications:
                        if isinstance(med, dict):
                            # Check for animal-derived ingredients
                            if (
                                med.get("contains_gelatin")
                                and "vegetarian" in dietary_restrictions
                            ):
                                results.append(
                                    ValidationResult(
                                        field="medications",
                                        rule="dietary_restriction_conflict",
                                        is_valid=True,  # Info only, not blocking
                                        message=f"{med.get('name', 'Medication')} contains gelatin - may conflict with dietary restrictions",
                                        severity=ValidationSeverity.INFO,
                                        category=ValidationCategory.CULTURAL,
                                    )
                                )

                            if med.get("contains_pork") and (
                                "halal" in dietary_restrictions
                                or "kosher" in dietary_restrictions
                            ):
                                results.append(
                                    ValidationResult(
                                        field="medications",
                                        rule="dietary_restriction_conflict",
                                        is_valid=True,  # Info only, not blocking
                                        message=f"{med.get('name', 'Medication')} contains pork-derived ingredients",
                                        severity=ValidationSeverity.INFO,
                                        category=ValidationCategory.CULTURAL,
                                    )
                                )

        # Blood pressure consistency
        if "blood_pressure_systolic" in data and "blood_pressure_diastolic" in data:
            systolic = data.get("blood_pressure_systolic")
            diastolic = data.get("blood_pressure_diastolic")

            if systolic and diastolic:
                try:
                    if float(systolic) <= float(diastolic):
                        results.append(
                            ValidationResult(
                                field="blood_pressure",
                                rule="bp_consistency",
                                is_valid=False,
                                message="Systolic pressure must be greater than diastolic",
                                severity=ValidationSeverity.ERROR,
                                category=ValidationCategory.CONSISTENCY,
                            )
                        )
                except (TypeError, ValueError):
                    pass

        # Date consistency
        if "collection_date" in data and "result_date" in data:
            collection = data.get("collection_date")
            result_date = data.get("result_date")

            if collection and result_date:
                try:
                    if isinstance(collection, str):
                        collection = datetime.strptime(collection, "%Y-%m-%d").date()
                    if isinstance(result_date, str):
                        result_date = datetime.strptime(result_date, "%Y-%m-%d").date()

                    if result_date < collection:
                        results.append(
                            ValidationResult(
                                field="dates",
                                rule="date_sequence",
                                is_valid=False,
                                message="Result date cannot be before collection date",
                                severity=ValidationSeverity.ERROR,
                                category=ValidationCategory.TEMPORAL,
                            )
                        )
                except (TypeError, ValueError):
                    pass

        # Age calculation consistency
        if "birth_date" in data and "age" in data:
            birth_date = data.get("birth_date")
            stated_age = data.get("age")

            if birth_date and stated_age:
                try:
                    if isinstance(birth_date, str):
                        birth_date = datetime.strptime(birth_date, "%Y-%m-%d").date()

                    calculated_age = (date.today() - birth_date).days // 365

                    if abs(calculated_age - int(stated_age)) > 1:
                        results.append(
                            ValidationResult(
                                field="age",
                                rule="age_consistency",
                                is_valid=False,
                                message=f"Stated age ({stated_age}) doesn't match calculated age ({calculated_age})",
                                severity=ValidationSeverity.WARNING,
                                category=ValidationCategory.CONSISTENCY,
                                suggestion=f"Verify birth date or update age to {calculated_age}",
                            )
                        )
                except (TypeError, ValueError):
                    pass

        return results

    def _check_pediatric_medication_safety(
        self, medications: List[Any], patient_age: int
    ) -> List[ValidationResult]:
        """Check pediatric medication safety concerns.

        Args:
            medications: List of medications
            patient_age: Patient age in years

        Returns:
            List of validation results
        """
        results = []

        # Age-specific medication contraindications
        age_contraindications = {
            0: {  # Under 1 year
                "aspirin": "Contraindicated under 1 year - Reye syndrome risk",
                "honey": "Risk of infant botulism under 1 year",
                "codeine": "Respiratory depression risk in infants",
            },
            2: {  # Under 2 years
                "promethazine": "Black box warning - respiratory depression under 2",
                "diphenhydramine": "Not recommended under 2 years",
            },
            6: {  # Under 6 years
                "decongestants": "Not recommended under 6 years",
                "cough_suppressants": "Limited efficacy and safety concerns under 6",
            },
            12: {  # Under 12 years
                "aspirin": "Reye syndrome risk in children with viral illness",
                "tramadol": "Not recommended for children under 12",
                "codeine": "Respiratory depression risk - contraindicated under 12",
            },
            18: {  # Under 18 years
                "fluoroquinolones": "Risk of tendon damage in pediatric patients",
                "tetracycline": "Tooth discoloration in children under 8",
            },
        }

        if isinstance(medications, list):
            for med in medications:
                med_name = (
                    med.get("name", "").lower()
                    if isinstance(med, dict)
                    else str(med).lower()
                )

                # Check age-specific contraindications
                for age_limit, contraindications in age_contraindications.items():
                    if patient_age < age_limit:
                        for drug, warning in contraindications.items():
                            if drug in med_name:
                                results.append(
                                    ValidationResult(
                                        field="medications",
                                        rule="pediatric_medication_safety",
                                        is_valid=False,
                                        message=f"{med_name}: {warning}",
                                        severity=(
                                            ValidationSeverity.ERROR
                                            if age_limit <= 2
                                            else ValidationSeverity.WARNING
                                        ),
                                        category=ValidationCategory.CLINICAL,
                                    )
                                )

        return results

    def get_validation_summary(
        self, validation_results: Dict[str, List[ValidationResult]]
    ) -> Dict[str, Any]:
        """Get summary of validation results.

        Args:
            validation_results: Validation results by field

        Returns:
            Summary dictionary
        """
        summary: Dict[str, Any] = {
            "total_fields": len(validation_results),
            "valid_fields": 0,
            "invalid_fields": 0,
            "errors": 0,
            "warnings": 0,
            "info": 0,
            "by_category": {},
            "invalid_fields_list": [],
        }

        for field_name, results in validation_results.items():
            has_error = False

            for result in results:
                if not result.is_valid:
                    if result.severity == ValidationSeverity.ERROR:
                        summary["errors"] += 1
                        has_error = True
                    elif result.severity == ValidationSeverity.WARNING:
                        summary["warnings"] += 1
                elif result.severity == ValidationSeverity.INFO:
                    summary["info"] += 1

                # Count by category
                category = result.category.value
                if category not in summary["by_category"]:
                    summary["by_category"][category] = 0
                if not result.is_valid:
                    summary["by_category"][category] += 1

            if has_error:
                summary["invalid_fields"] += 1
                summary["invalid_fields_list"].append(field_name)
            else:
                summary["valid_fields"] += 1

        summary["is_valid"] = summary["errors"] == 0

        return summary


class ClinicalValidator:
    """Specialized validator for clinical data."""

    def __init__(self) -> None:
        """Initialize clinical validator."""
        self.engine = ValidationEngine()
        self._add_clinical_rules()

    def _add_clinical_rules(self) -> None:
        """Add clinical-specific validation rules."""
        # Vital signs with age-specific ranges
        self.engine.add_rule("heart_rate", self._create_age_based_hr_rule())
        self.engine.add_rule("respiratory_rate", self._create_age_based_rr_rule())

        # Lab result ranges
        self.engine.add_rule("hemoglobin", self._create_hemoglobin_rule())
        self.engine.add_rule("glucose", self._create_glucose_rule())

    def _create_age_based_hr_rule(self) -> ValidationRule:
        """Create age-based heart rate validation rule."""

        class AgeBasedHRRule(ValidationRule):
            def __init__(self) -> None:
                super().__init__(
                    name="age_based_hr",
                    description="Age-appropriate heart rate",
                    category=ValidationCategory.CLINICAL,
                )

            def validate(
                self, value: Any, context: Optional[Dict] = None
            ) -> ValidationResult:
                if value is None:
                    return ValidationResult(
                        field="heart_rate",
                        rule=self.name,
                        is_valid=True,
                        category=self.category,
                    )

                try:
                    hr = float(value)
                    age = context.get("age") if context else None

                    if age is None:
                        # Use adult ranges as default
                        min_hr, max_hr = 60, 100
                    elif age < 1:
                        min_hr, max_hr = 100, 160
                    elif age < 3:
                        min_hr, max_hr = 80, 130
                    elif age < 6:
                        min_hr, max_hr = 75, 115
                    elif age < 12:
                        min_hr, max_hr = 70, 110
                    else:
                        min_hr, max_hr = 60, 100

                    if hr < min_hr or hr > max_hr:
                        return ValidationResult(
                            field="heart_rate",
                            rule=self.name,
                            is_valid=False,
                            message=f"Heart rate {hr} outside normal range ({min_hr}-{max_hr}) for age {age}",
                            severity=ValidationSeverity.WARNING,
                            category=self.category,
                        )

                except (TypeError, ValueError):
                    pass

                return ValidationResult(
                    field="heart_rate",
                    rule=self.name,
                    is_valid=True,
                    category=self.category,
                )

        return AgeBasedHRRule()

    def _create_age_based_rr_rule(self) -> ValidationRule:
        """Create age-based respiratory rate validation rule."""

        class AgeBasedRRRule(ValidationRule):
            def __init__(self) -> None:
                super().__init__(
                    name="age_based_rr",
                    description="Age-appropriate respiratory rate",
                    category=ValidationCategory.CLINICAL,
                )

            def validate(
                self, value: Any, context: Optional[Dict] = None
            ) -> ValidationResult:
                if value is None:
                    return ValidationResult(
                        field="respiratory_rate",
                        rule=self.name,
                        is_valid=True,
                        category=self.category,
                    )

                try:
                    rr = float(value)
                    age = context.get("age") if context else None

                    if age is None:
                        # Use adult ranges as default
                        min_rr, max_rr = 12, 20
                    elif age < 1:
                        min_rr, max_rr = 30, 60
                    elif age < 3:
                        min_rr, max_rr = 20, 40
                    elif age < 6:
                        min_rr, max_rr = 20, 30
                    elif age < 12:
                        min_rr, max_rr = 18, 25
                    else:
                        min_rr, max_rr = 12, 20

                    if rr < min_rr or rr > max_rr:
                        return ValidationResult(
                            field="respiratory_rate",
                            rule=self.name,
                            is_valid=False,
                            message=f"Respiratory rate {rr} outside normal range ({min_rr}-{max_rr}) for age {age}",
                            severity=ValidationSeverity.WARNING,
                            category=self.category,
                        )

                except (TypeError, ValueError):
                    pass

                return ValidationResult(
                    field="respiratory_rate",
                    rule=self.name,
                    is_valid=True,
                    category=self.category,
                )

        return AgeBasedRRRule()

    def _create_hemoglobin_rule(self) -> ValidationRule:
        """Create hemoglobin validation rule with gender/age considerations."""

        class HemoglobinRule(ValidationRule):
            def __init__(self) -> None:
                super().__init__(
                    name="hemoglobin_range",
                    description="Gender and age-appropriate hemoglobin",
                    category=ValidationCategory.CLINICAL,
                )

            def validate(
                self, value: Any, context: Optional[Dict] = None
            ) -> ValidationResult:
                if value is None:
                    return ValidationResult(
                        field="hemoglobin",
                        rule=self.name,
                        is_valid=True,
                        category=self.category,
                    )

                try:
                    hgb = float(value)
                    gender = context.get("gender") if context else None
                    age = context.get("age") if context else None

                    # Determine normal range
                    if age and age < 12:
                        min_hgb, max_hgb = 11.0, 14.0
                    elif gender == "M":
                        min_hgb, max_hgb = 13.5, 17.5
                    elif gender == "F":
                        min_hgb, max_hgb = 12.0, 15.5
                    else:
                        min_hgb, max_hgb = 12.0, 17.5

                    if hgb < min_hgb:
                        severity = (
                            ValidationSeverity.ERROR
                            if hgb < 7.0
                            else ValidationSeverity.WARNING
                        )
                        return ValidationResult(
                            field="hemoglobin",
                            rule=self.name,
                            is_valid=False,
                            message=f"Hemoglobin {hgb} g/dL is low (normal: {min_hgb}-{max_hgb})",
                            severity=severity,
                            category=self.category,
                            suggestion="Consider anemia evaluation",
                        )
                    elif hgb > max_hgb:
                        return ValidationResult(
                            field="hemoglobin",
                            rule=self.name,
                            is_valid=False,
                            message=f"Hemoglobin {hgb} g/dL is high (normal: {min_hgb}-{max_hgb})",
                            severity=ValidationSeverity.WARNING,
                            category=self.category,
                        )

                except (TypeError, ValueError):
                    pass

                return ValidationResult(
                    field="hemoglobin",
                    rule=self.name,
                    is_valid=True,
                    category=self.category,
                )

        return HemoglobinRule()

    def _create_glucose_rule(self) -> ValidationRule:
        """Create glucose validation rule."""

        class GlucoseRule(ValidationRule):
            def __init__(self) -> None:
                super().__init__(
                    name="glucose_range",
                    description="Blood glucose range",
                    category=ValidationCategory.CLINICAL,
                )

            def validate(
                self, value: Any, context: Optional[Dict] = None
            ) -> ValidationResult:
                if value is None:
                    return ValidationResult(
                        field="glucose",
                        rule=self.name,
                        is_valid=True,
                        category=self.category,
                    )

                try:
                    glucose = float(value)
                    fasting = context.get("fasting") if context else None

                    if fasting:
                        min_glucose, max_glucose = 70, 100
                        critical_low, critical_high = 50, 126
                    else:
                        min_glucose, max_glucose = 70, 140
                        critical_low, critical_high = 50, 200

                    if glucose < critical_low:
                        return ValidationResult(
                            field="glucose",
                            rule=self.name,
                            is_valid=False,
                            message=f"Critical hypoglycemia: {glucose} mg/dL",
                            severity=ValidationSeverity.ERROR,
                            category=self.category,
                            suggestion="Immediate medical attention required",
                        )
                    elif glucose > critical_high:
                        return ValidationResult(
                            field="glucose",
                            rule=self.name,
                            is_valid=False,
                            message=f"Hyperglycemia: {glucose} mg/dL",
                            severity=ValidationSeverity.WARNING,
                            category=self.category,
                            suggestion="Diabetes evaluation recommended",
                        )
                    elif glucose < min_glucose or glucose > max_glucose:
                        return ValidationResult(
                            field="glucose",
                            rule=self.name,
                            is_valid=False,
                            message=f"Glucose {glucose} mg/dL outside normal range ({min_glucose}-{max_glucose})",
                            severity=ValidationSeverity.WARNING,
                            category=self.category,
                        )

                except (TypeError, ValueError):
                    pass

                return ValidationResult(
                    field="glucose",
                    rule=self.name,
                    is_valid=True,
                    category=self.category,
                )

        return GlucoseRule()

    @require_phi_access(AccessLevel.READ)
    @audit_phi_access("validate_clinical_data")
    def validate_clinical_data(
        self, data: Dict[str, Any], data_type: str
    ) -> Dict[str, Any]:
        """Validate clinical data with type-specific rules.

        Args:
            data: Clinical data to validate
            data_type: Type of clinical data

        Returns:
            Validation results and summary
        """
        # Create context with patient demographics
        context = {
            "age": data.get("age"),
            "gender": data.get("gender"),
            "fasting": data.get("fasting"),
            "pregnant": data.get("pregnant"),
        }

        # Validate with appropriate rule set
        results = self.engine.validate_data(data, data_type, context)
        summary = self.engine.get_validation_summary(results)

        return {
            "results": results,
            "summary": summary,
            "data_type": data_type,
            "timestamp": datetime.now(),
        }

    def _check_medication_interactions(
        self,
        new_medications: List[Any],
        existing_medications: List[Dict[str, Any]],
        allergies: List[Dict[str, Any]],
    ) -> List[ValidationResult]:
        """Check for medication interactions and contraindications.

        Args:
            new_medications: New medications to validate
            existing_medications: Patient's current medications
            allergies: Patient's known allergies

        Returns:
            List of validation results
        """
        results = []
        drug_interactions = {}  # Initialize to empty dict

        # CRITICAL: Use real drug interaction service in production
        if settings.environment.lower() in ["production", "staging"]:
            try:
                service = get_drug_interaction_service()

                # Combine all medications for interaction checking
                all_medications = []

                # Add new medications
                for med in new_medications:
                    if isinstance(med, dict):
                        all_medications.append(
                            {"name": med.get("name", ""), "dose": med.get("dose", "")}
                        )
                    else:
                        all_medications.append({"name": str(med), "dose": ""})

                # Add existing medications
                for med in existing_medications:
                    all_medications.append(
                        {"name": med.get("name", ""), "dose": med.get("dose", "")}
                    )

                # Check interactions
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                interactions = loop.run_until_complete(
                    service.check_interactions(medications=all_medications)
                )

                # Convert to validation results
                for interaction in interactions:
                    severity_map = {
                        "contraindicated": ValidationSeverity.CRITICAL,
                        "major": ValidationSeverity.CRITICAL,
                        "moderate": ValidationSeverity.WARNING,
                        "minor": ValidationSeverity.INFO,
                    }

                    results.append(
                        ValidationResult(
                            field="medication_interaction",
                            rule="drug_interaction",
                            is_valid=False,
                            severity=severity_map.get(
                                interaction["severity"], ValidationSeverity.WARNING
                            ),
                            message=interaction["description"],
                        )
                    )

            except (RuntimeError, ValueError, TypeError) as e:
                logger.error("Failed to use drug interaction service: %s", e)
                # Fall through to simplified checking

        # Development only - simplified drug interactions
        if settings.environment.lower() not in ["production", "staging"]:
            logger.warning(
                "Using simplified drug interactions in development. "
                "Production MUST use DrugInteractionService!"
            )

            # Known drug interactions (simplified - NEVER use in production)
            drug_interactions = {
                "warfarin": {
                    "aspirin": "Increased bleeding risk",
                    "ibuprofen": "Increased bleeding risk",
                    "nsaid": "Increased bleeding risk",
                    "vitamin_k": "Decreased warfarin effectiveness",
                },
                "metformin": {
                    "contrast": "Risk of lactic acidosis with iodinated contrast",
                    "alcohol": "Increased risk of lactic acidosis",
                },
                "digoxin": {
                    "amiodarone": "Increased digoxin levels - toxicity risk",
                    "verapamil": "Increased digoxin levels",
                },
                "ssri": {  # Any SSRI antidepressant
                    "maoi": "Serotonin syndrome risk - contraindicated",
                    "tramadol": "Increased serotonin syndrome risk",
                },
                "ace_inhibitor": {
                    "potassium": "Hyperkalemia risk",
                    "spironolactone": "Hyperkalemia risk",
                },
            }

        # Check each new medication
        for new_med in new_medications:
            new_med_name = (
                new_med.get("name", "").lower()
                if isinstance(new_med, dict)
                else str(new_med).lower()
            )

            # Check for duplicates
            for existing_med in existing_medications:
                existing_name = (
                    existing_med.get("name", "").lower()
                    if isinstance(existing_med, dict)
                    else str(existing_med).lower()
                )

                if new_med_name == existing_name:
                    results.append(
                        ValidationResult(
                            field="medications",
                            rule="duplicate_medication",
                            is_valid=False,
                            message=f"Patient already taking {new_med_name}",
                            severity=ValidationSeverity.ERROR,
                            category=ValidationCategory.CLINICAL,
                        )
                    )

                # Check for interactions
                for drug_class, interactions in drug_interactions.items():
                    if drug_class in existing_name:
                        for interacting_drug, warning in interactions.items():
                            if interacting_drug in new_med_name:
                                results.append(
                                    ValidationResult(
                                        field="medications",
                                        rule="drug_interaction",
                                        is_valid=False,
                                        message=f"Interaction: {existing_name} + {new_med_name} - {warning}",
                                        severity=ValidationSeverity.ERROR,
                                        category=ValidationCategory.CLINICAL,
                                    )
                                )

            # Check allergies
            for allergy in allergies:
                allergy_name = (
                    allergy.get("substance", "").lower()
                    if isinstance(allergy, dict)
                    else str(allergy).lower()
                )

                # Check direct allergy match
                if allergy_name in new_med_name or new_med_name in allergy_name:
                    results.append(
                        ValidationResult(
                            field="medications",
                            rule="allergy_contraindication",
                            is_valid=False,
                            message=f"Patient has allergy to {allergy_name}",
                            severity=ValidationSeverity.ERROR,
                            category=ValidationCategory.CLINICAL,
                        )
                    )

                # Check cross-reactivity
                cross_reactive = {
                    "penicillin": ["amoxicillin", "ampicillin", "cephalosporin"],
                    "sulfa": ["sulfamethoxazole", "furosemide", "hydrochlorothiazide"],
                    "nsaid": ["ibuprofen", "naproxen", "aspirin"],
                }

                for allergy_class, related_drugs in cross_reactive.items():
                    if allergy_class in allergy_name:
                        for related in related_drugs:
                            if related in new_med_name:
                                results.append(
                                    ValidationResult(
                                        field="medications",
                                        rule="cross_reactivity_warning",
                                        is_valid=False,
                                        message=f"Potential cross-reactivity: {allergy_name} allergy with {new_med_name}",
                                        severity=ValidationSeverity.WARNING,
                                        category=ValidationCategory.CLINICAL,
                                    )
                                )

        return results

    def _check_cultural_compatibility(
        self, data: Dict[str, Any], context: ValidationContext
    ) -> List[ValidationResult]:
        """Check for cultural and religious compatibility issues.

        Args:
            data: Data being validated
            context: Validation context with cultural information

        Returns:
            List of validation results
        """
        results = []

        # Cultural and religious dietary restrictions
        dietary_restrictions = {
            "islam": {
                "prohibited": ["pork", "alcohol", "gelatin", "non-halal"],
                "requires": ["halal"],
            },
            "judaism": {
                "prohibited": ["pork", "shellfish", "mixing meat and dairy"],
                "requires": ["kosher"],
            },
            "hinduism": {
                "prohibited": ["beef", "meat"],  # Many Hindus are vegetarian
                "preferred": ["vegetarian"],
            },
            "buddhism": {
                "prohibited": ["meat", "alcohol"],  # Many Buddhists are vegetarian
                "preferred": ["vegetarian"],
            },
            "jainism": {
                "prohibited": ["meat", "eggs", "honey", "root vegetables"],
                "requires": ["strict vegetarian"],
            },
        }

        # Fasting periods that may affect medication timing
        fasting_periods = {
            "islam": "Ramadan - no food/drink/medication during daylight",
            "judaism": "Yom Kippur, other fast days",
            "christianity": "Lent, various fast days",
            "hinduism": "Various festival fasts",
        }

        # Check medications for religious/cultural concerns
        if "medications" in data and context.religious_affiliation:
            religion = context.religious_affiliation.lower()
            restrictions = dietary_restrictions.get(religion, {})

            medications = data.get("medications", [])
            for med in medications:
                med_info = med if isinstance(med, dict) else {"name": str(med)}
                med_name = med_info.get("name", "").lower()
                ingredients = med_info.get("ingredients", "").lower()

                # Check prohibited ingredients
                for prohibited in restrictions.get("prohibited", []):
                    if prohibited in med_name or prohibited in ingredients:
                        results.append(
                            ValidationResult(
                                field="medications",
                                rule="cultural_dietary_restriction",
                                is_valid=False,
                                message=f"Medication may contain {prohibited} - incompatible with {context.religious_affiliation} dietary laws",
                                severity=ValidationSeverity.WARNING,
                                category=ValidationCategory.CULTURAL,
                                suggestion=f"Consider alternative medication or verify ingredients are {restrictions.get('requires', ['acceptable'])[0]}",
                            )
                        )

                # Check medication timing during fasting
                if religion in fasting_periods:
                    schedule = med_info.get("schedule", "")
                    if any(
                        time in schedule.lower()
                        for time in ["daily", "tid", "qid", "morning", "noon"]
                    ):
                        results.append(
                            ValidationResult(
                                field="medications",
                                rule="fasting_medication_timing",
                                is_valid=True,  # Information only
                                message=f"Consider {fasting_periods[religion]} when scheduling medication",
                                severity=ValidationSeverity.INFO,
                                category=ValidationCategory.CULTURAL,
                                suggestion="Discuss alternative dosing schedule during fasting periods",
                            )
                        )

        # Check procedures for cultural sensitivity
        if "procedures" in data and context.cultural_background:
            procedures = data.get("procedures", [])

            # Gender-specific provider preferences
            gender_sensitive_procedures = [
                "gynecological",
                "obstetric",
                "urological",
                "breast",
                "pelvic",
            ]

            for procedure in procedures:
                proc_name = (
                    procedure.get("name", "").lower()
                    if isinstance(procedure, dict)
                    else str(procedure).lower()
                )

                # Check if procedure is gender-sensitive
                if any(
                    sensitive in proc_name for sensitive in gender_sensitive_procedures
                ):
                    if context.cultural_background in [
                        "islam",
                        "orthodox judaism",
                        "some hindu communities",
                    ]:
                        results.append(
                            ValidationResult(
                                field="procedures",
                                rule="gender_provider_preference",
                                is_valid=True,  # Information only
                                message=f"Patient may prefer same-gender provider for {proc_name}",
                                severity=ValidationSeverity.INFO,
                                category=ValidationCategory.CULTURAL,
                                suggestion="Offer same-gender provider option if available",
                            )
                        )

        # Blood transfusion considerations
        if "blood_transfusion" in str(data).lower():
            if context.religious_affiliation == "jehovah's witness":
                results.append(
                    ValidationResult(
                        field="procedures",
                        rule="blood_transfusion_restriction",
                        is_valid=False,
                        message="Jehovah's Witnesses typically refuse blood transfusions",
                        severity=ValidationSeverity.ERROR,
                        category=ValidationCategory.CULTURAL,
                        suggestion="Discuss blood alternatives or obtain specific consent",
                    )
                )

        return results

    def _validate_temporal_consistency(
        self, data: Dict[str, Any], context: ValidationContext
    ) -> List[ValidationResult]:
        """Validate temporal consistency of data.

        Args:
            data: Data to validate
            context: Validation context with temporal information

        Returns:
            List of validation results
        """
        results = []

        current_date = context.current_date or datetime.now()

        # Check dates are not in the future
        date_fields = [
            "date_of_service",
            "procedure_date",
            "diagnosis_date",
            "vaccination_date",
        ]
        for date_field in date_fields:
            if date_field in data:
                try:
                    field_date = data[date_field]
                    if isinstance(field_date, str):
                        field_date = datetime.strptime(field_date, "%Y-%m-%d")
                    elif not isinstance(field_date, datetime):
                        continue

                    if field_date > current_date:
                        results.append(
                            ValidationResult(
                                field=date_field,
                                rule="future_date_check",
                                is_valid=False,
                                message=f"{date_field} cannot be in the future",
                                severity=ValidationSeverity.ERROR,
                                category=ValidationCategory.TEMPORAL,
                            )
                        )
                except (ValueError, TypeError):
                    pass

        # Check admission date consistency
        if context.admission_date and "discharge_date" in data:
            try:
                discharge_date = data["discharge_date"]
                if isinstance(discharge_date, str):
                    discharge_date = datetime.strptime(discharge_date, "%Y-%m-%d")

                if discharge_date < context.admission_date:
                    results.append(
                        ValidationResult(
                            field="discharge_date",
                            rule="discharge_before_admission",
                            is_valid=False,
                            message="Discharge date cannot be before admission date",
                            severity=ValidationSeverity.ERROR,
                            category=ValidationCategory.TEMPORAL,
                        )
                    )
            except (ValueError, TypeError):
                pass

        # Validate pregnancy timeline
        if "pregnancy_status" in data and data.get("pregnancy_status") == "pregnant":
            if "last_menstrual_period" in data:
                try:
                    lmp = data["last_menstrual_period"]
                    if isinstance(lmp, str):
                        lmp = datetime.strptime(lmp, "%Y-%m-%d")

                    weeks_pregnant = (current_date - lmp).days / 7

                    if weeks_pregnant > 42:  # Normal pregnancy is up to 42 weeks
                        results.append(
                            ValidationResult(
                                field="last_menstrual_period",
                                rule="pregnancy_duration_check",
                                is_valid=False,
                                message=f"Pregnancy duration ({int(weeks_pregnant)} weeks) exceeds normal range",
                                severity=ValidationSeverity.WARNING,
                                category=ValidationCategory.TEMPORAL,
                                suggestion="Verify LMP date or pregnancy status",
                            )
                        )

                    if weeks_pregnant < 0:
                        results.append(
                            ValidationResult(
                                field="last_menstrual_period",
                                rule="future_lmp_check",
                                is_valid=False,
                                message="Last menstrual period cannot be in the future",
                                severity=ValidationSeverity.ERROR,
                                category=ValidationCategory.TEMPORAL,
                            )
                        )
                except (ValueError, TypeError):
                    pass

        # Validate vaccination schedules
        if "vaccinations" in data and context.patient_age is not None:
            vaccinations = data.get("vaccinations", [])

            # Standard vaccination age ranges (simplified)
            vaccine_schedules = {
                "bcg": {"min_age_days": 0, "max_age_days": 365},  # Birth to 1 year
                "hepatitis_b": {"min_age_days": 0, "max_age_days": 1},  # At birth
                "mmr": {"min_age_days": 365, "max_age_days": 540},  # 12-18 months
                "dpt": {
                    "min_age_days": 60,
                    "max_age_days": 90,
                },  # 2-3 months for first dose
            }

            for vaccine in vaccinations:
                if isinstance(vaccine, dict):
                    vaccine_name = vaccine.get("name", "").lower()
                    vaccine_date = vaccine.get("date")

                    if vaccine_name in vaccine_schedules and vaccine_date:
                        try:
                            if isinstance(vaccine_date, str):
                                vaccine_date = datetime.strptime(
                                    vaccine_date, "%Y-%m-%d"
                                )

                            # Calculate age at vaccination
                            if context.patient_age and hasattr(vaccine_date, "year"):
                                years_ago = current_date.year - vaccine_date.year
                                age_at_vaccination = context.patient_age - years_ago

                                schedule = vaccine_schedules[vaccine_name]
                                min_age_years = schedule["min_age_days"] / 365
                                max_age_years = schedule["max_age_days"] / 365

                                if age_at_vaccination < min_age_years:
                                    results.append(
                                        ValidationResult(
                                            field="vaccinations",
                                            rule="vaccination_age_early",
                                            is_valid=False,
                                            message=f"{vaccine_name} given too early (age {age_at_vaccination:.1f} years)",
                                            severity=ValidationSeverity.WARNING,
                                            category=ValidationCategory.TEMPORAL,
                                        )
                                    )
                                elif age_at_vaccination > max_age_years:
                                    results.append(
                                        ValidationResult(
                                            field="vaccinations",
                                            rule="vaccination_age_late",
                                            is_valid=False,
                                            message=f"{vaccine_name} given too late (age {age_at_vaccination:.1f} years)",
                                            severity=ValidationSeverity.WARNING,
                                            category=ValidationCategory.TEMPORAL,
                                        )
                                    )
                        except (ValueError, TypeError):
                            pass

        return results
