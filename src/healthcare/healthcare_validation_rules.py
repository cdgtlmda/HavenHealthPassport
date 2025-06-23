"""Healthcare-specific Validation Rules.

This module defines validation rules specific to healthcare data
for the Haven Health Passport system. Handles FHIR Resource validation
for healthcare operations and compliance. All PHI data is encrypted
and access is controlled through role-based permissions.
"""

import logging
from datetime import datetime, timedelta
from typing import List

from src.types.validation_types import ValidationSeverity

from .validation_engine import (
    CodeSetRule,
    CrossFieldRule,
    FormatRule,
    RangeRule,
    RequiredFieldRule,
    TemporalRule,
    ValidationContext,
    validation_engine,
)

logger = logging.getLogger(__name__)

# FHIR resource type for this module
__fhir_resource__ = "OperationOutcome"


class HealthcareValidationRules:
    """Healthcare-specific validation rules."""

    @staticmethod
    def validate_fhir_resource(resource_data: dict) -> dict:
        """Validate FHIR resource data.

        Args:
            resource_data: FHIR resource data to validate

        Returns:
            Validation result with 'valid', 'errors', and 'warnings' keys
        """
        errors: List[str] = []
        warnings: List[str] = []

        # Basic FHIR resource structure validation
        if "resourceType" not in resource_data:
            errors.append("Missing required field: resourceType")

        return {"valid": len(errors) == 0, "errors": errors, "warnings": warnings}

    @staticmethod
    def register_patient_rules() -> None:
        """Register validation rules for patient data."""
        # Patient ID rules
        validation_engine.register_rule(
            RequiredFieldRule(
                rule_id="patient.id.required",
                field_path="patient.id",
                description="Patient ID is required",
                severity=ValidationSeverity.ERROR,
                contexts=[ValidationContext.IMPORT, ValidationContext.STORAGE],
            )
        )

        validation_engine.register_rule(
            FormatRule(
                rule_id="patient.id.format",
                field_path="patient.id",
                description="Patient ID format validation",
                format_type="uuid",
                severity=ValidationSeverity.ERROR,
            )
        )

        # UNHCR ID rules
        validation_engine.register_rule(
            FormatRule(
                rule_id="patient.unhcr_id.format",
                field_path="patient.unhcr_id",
                description="UNHCR ID format validation",
                format_type="unhcr_id",
                severity=ValidationSeverity.ERROR,
                error_message="UNHCR ID must be in format XXX-YYCCCCCC",
            )
        )

        # Name rules
        validation_engine.register_rule(
            RequiredFieldRule(
                rule_id="patient.name.given.required",
                field_path="patient.name.given",
                description="Patient given name is required",
                severity=ValidationSeverity.ERROR,
                allow_empty=False,
            )
        )

        validation_engine.register_rule(
            RequiredFieldRule(
                rule_id="patient.name.family.required",
                field_path="patient.name.family",
                description="Patient family name is required",
                severity=ValidationSeverity.WARNING,
                allow_empty=True,  # Some cultures don't use family names
            )
        )

        # Birth date rules
        validation_engine.register_rule(
            RequiredFieldRule(
                rule_id="patient.birth_date.required",
                field_path="patient.birth_date",
                description="Patient birth date is required",
                severity=ValidationSeverity.ERROR,
            )
        )

        validation_engine.register_rule(
            FormatRule(
                rule_id="patient.birth_date.format",
                field_path="patient.birth_date",
                description="Birth date format validation",
                severity=ValidationSeverity.ERROR,
                format_type="date",
            )
        )

        validation_engine.register_rule(
            TemporalRule(
                rule_id="patient.birth_date.past",
                field_path="patient.birth_date",
                description="Birth date must be in the past",
                temporal_type="past",
                severity=ValidationSeverity.ERROR,
            )
        )

        validation_engine.register_rule(
            RangeRule(
                rule_id="patient.birth_date.range",
                field_path="patient.birth_date",
                description="Birth date reasonable range",
                min_value=datetime.now().date()
                - timedelta(days=150 * 365),  # 150 years ago
                max_value=datetime.now().date(),
                severity=ValidationSeverity.WARNING,
                error_message="Birth date seems unreasonable (>150 years ago)",
            )
        )

        # Gender rules
        validation_engine.register_rule(
            RequiredFieldRule(
                rule_id="patient.gender.required",
                field_path="patient.gender",
                description="Patient gender is required",
                severity=ValidationSeverity.ERROR,
            )
        )

        validation_engine.register_rule(
            CodeSetRule(
                rule_id="patient.gender.codeset",
                field_path="patient.gender",
                description="Gender code validation",
                code_system="HL7_AdministrativeGender",
                allowed_codes={"M", "F", "O", "U"},
                severity=ValidationSeverity.ERROR,
            )
        )

        # Contact information rules
        validation_engine.register_rule(
            FormatRule(
                rule_id="patient.telecom.phone.format",
                field_path="patient.telecom.phone",
                description="Phone number format validation",
                format_type="phone",
                severity=ValidationSeverity.WARNING,
            )
        )

        validation_engine.register_rule(
            FormatRule(
                rule_id="patient.telecom.email.format",
                field_path="patient.telecom.email",
                description="Email format validation",
                format_type="email",
                severity=ValidationSeverity.WARNING,
            )
        )

        # Address rules
        validation_engine.register_rule(
            RequiredFieldRule(
                rule_id="patient.address.country.required",
                field_path="patient.address.country",
                description="Country is required for refugee patients",
                severity=ValidationSeverity.ERROR,
                contexts=[ValidationContext.IMPORT, ValidationContext.STORAGE],
            )
        )

        # Language rules
        validation_engine.register_rule(
            RequiredFieldRule(
                rule_id="patient.communication.language.required",
                field_path="patient.communication.language",
                description="Primary language is required",
                severity=ValidationSeverity.WARNING,
            )
        )

        validation_engine.register_rule(
            CodeSetRule(
                rule_id="patient.communication.language.codeset",
                field_path="patient.communication.language",
                description="Language code validation",
                code_system="ISO639",
                severity=ValidationSeverity.WARNING,
            )
        )

    @staticmethod
    def register_immunization_rules() -> None:
        """Register validation rules for immunization data."""
        # Vaccine code rules
        validation_engine.register_rule(
            RequiredFieldRule(
                rule_id="immunization.vaccine_code.required",
                field_path="immunization.vaccine_code",
                description="Vaccine code is required",
                severity=ValidationSeverity.ERROR,
            )
        )

        validation_engine.register_rule(
            CodeSetRule(
                rule_id="immunization.vaccine_code.codeset",
                field_path="immunization.vaccine_code",
                description="Vaccine code validation",
                code_system="CVX",
                severity=ValidationSeverity.ERROR,
            )
        )

        # Administration date rules
        validation_engine.register_rule(
            RequiredFieldRule(
                rule_id="immunization.occurrence_date.required",
                field_path="immunization.occurrence_date",
                description="Immunization date is required",
                severity=ValidationSeverity.ERROR,
            )
        )

        validation_engine.register_rule(
            TemporalRule(
                rule_id="immunization.occurrence_date.past",
                field_path="immunization.occurrence_date",
                description="Immunization date must be in the past",
                temporal_type="past",
                severity=ValidationSeverity.ERROR,
            )
        )

        # Cross-field validation: immunization date after birth date
        validation_engine.register_rule(
            CrossFieldRule(
                rule_id="immunization.date_after_birth",
                field_path="immunization.occurrence_date",
                description="Immunization date must be after birth date",
                related_fields=["patient.birth_date"],
                validation_function=lambda fields, context: (
                    fields.get("immunization.occurrence_date")
                    >= fields.get("patient.birth_date")
                    if all(fields.values())
                    else True
                ),
                severity=ValidationSeverity.ERROR,
                error_message="Immunization date cannot be before patient birth date",
            )
        )

        # Dose number rules
        validation_engine.register_rule(
            RangeRule(
                rule_id="immunization.dose_number.range",
                field_path="immunization.dose_number",
                description="Dose number validation",
                min_value=1,
                max_value=10,
                severity=ValidationSeverity.WARNING,
                error_message="Unusual dose number (expected 1-10)",
            )
        )

        # Lot number rules
        validation_engine.register_rule(
            FormatRule(
                rule_id="immunization.lot_number.format",
                field_path="immunization.lot_number",
                description="Lot number format validation",
                pattern=r"^[A-Z0-9\-]{3,20}$",
                severity=ValidationSeverity.INFO,
                error_message="Lot number should be 3-20 alphanumeric characters",
            )
        )

    @staticmethod
    def register_medication_rules() -> None:
        """Register validation rules for medication data."""
        # Medication code rules
        validation_engine.register_rule(
            RequiredFieldRule(
                rule_id="medication.code.required",
                field_path="medication.code",
                description="Medication code is required",
                severity=ValidationSeverity.ERROR,
            )
        )

        validation_engine.register_rule(
            CodeSetRule(
                rule_id="medication.code.rxnorm",
                field_path="medication.code",
                description="RxNorm code validation",
                code_system="RXNORM",
                severity=ValidationSeverity.WARNING,
            )
        )

        # Dosage rules
        validation_engine.register_rule(
            RequiredFieldRule(
                rule_id="medication.dosage.dose.required",
                field_path="medication.dosage.dose",
                description="Medication dose is required",
                severity=ValidationSeverity.ERROR,
            )
        )

        validation_engine.register_rule(
            RangeRule(
                rule_id="medication.dosage.dose.range",
                field_path="medication.dosage.dose.value",
                description="Dose amount validation",
                min_value=0,
                max_value=10000,
                severity=ValidationSeverity.WARNING,
                error_message="Unusual dose amount",
            )
        )

        # Frequency rules
        validation_engine.register_rule(
            RequiredFieldRule(
                rule_id="medication.dosage.timing.required",
                field_path="medication.dosage.timing",
                description="Medication timing is required",
                severity=ValidationSeverity.WARNING,
            )
        )

        # Duration rules
        validation_engine.register_rule(
            RangeRule(
                rule_id="medication.duration.range",
                field_path="medication.duration.value",
                description="Treatment duration validation",
                min_value=1,
                max_value=365,
                severity=ValidationSeverity.INFO,
                error_message="Unusual treatment duration (expected 1-365 days)",
            )
        )

        # Route rules
        validation_engine.register_rule(
            CodeSetRule(
                rule_id="medication.route.codeset",
                field_path="medication.route",
                description="Route of administration validation",
                code_system="SNOMED",
                allowed_codes={
                    "26643006",  # Oral
                    "78421000",  # Intramuscular
                    "47625008",  # Intravenous
                    "34206005",  # Subcutaneous
                    "45890007",  # Topical
                    "46713006",  # Nasal
                    "16857009",  # Ophthalmic
                },
                severity=ValidationSeverity.WARNING,
            )
        )

    @staticmethod
    def register_observation_rules() -> None:
        """Register validation rules for observation data."""
        # Observation code rules
        validation_engine.register_rule(
            RequiredFieldRule(
                rule_id="observation.code.required",
                field_path="observation.code",
                description="Observation code is required",
                severity=ValidationSeverity.ERROR,
            )
        )

        validation_engine.register_rule(
            CodeSetRule(
                rule_id="observation.code.loinc",
                field_path="observation.code",
                description="LOINC code validation",
                code_system="LOINC",
                severity=ValidationSeverity.WARNING,
            )
        )

        # Value rules
        validation_engine.register_rule(
            RequiredFieldRule(
                rule_id="observation.value.required",
                field_path="observation.value",
                description="Observation value is required",
                severity=ValidationSeverity.ERROR,
            )
        )

        # Vital signs specific rules

        # Blood pressure
        validation_engine.register_rule(
            RangeRule(
                rule_id="observation.bp.systolic.range",
                field_path="observation.component.systolic.value",
                description="Systolic BP range validation",
                min_value=60,
                max_value=300,
                severity=ValidationSeverity.WARNING,
                metadata={"loinc_code": "8480-6"},
            )
        )

        validation_engine.register_rule(
            RangeRule(
                rule_id="observation.bp.diastolic.range",
                field_path="observation.component.diastolic.value",
                description="Diastolic BP range validation",
                min_value=30,
                max_value=200,
                severity=ValidationSeverity.WARNING,
                metadata={"loinc_code": "8462-4"},
            )
        )

        # Temperature
        validation_engine.register_rule(
            RangeRule(
                rule_id="observation.temperature.celsius.range",
                field_path="observation.value",
                description="Body temperature range validation (Celsius)",
                min_value=30,
                max_value=45,
                severity=ValidationSeverity.WARNING,
                metadata={"loinc_code": "8310-5", "unit": "Cel"},
            )
        )

        # Heart rate
        validation_engine.register_rule(
            RangeRule(
                rule_id="observation.heart_rate.range",
                field_path="observation.value",
                description="Heart rate range validation",
                min_value=30,
                max_value=250,
                severity=ValidationSeverity.WARNING,
                metadata={"loinc_code": "8867-4"},
            )
        )

        # Weight
        validation_engine.register_rule(
            RangeRule(
                rule_id="observation.weight.kg.range",
                field_path="observation.value",
                description="Body weight range validation (kg)",
                min_value=0.5,
                max_value=500,
                severity=ValidationSeverity.WARNING,
                metadata={"loinc_code": "29463-7", "unit": "kg"},
            )
        )

        # Height
        validation_engine.register_rule(
            RangeRule(
                rule_id="observation.height.cm.range",
                field_path="observation.value",
                description="Body height range validation (cm)",
                min_value=20,
                max_value=300,
                severity=ValidationSeverity.WARNING,
                metadata={"loinc_code": "8302-2", "unit": "cm"},
            )
        )

        # Observation date rules
        validation_engine.register_rule(
            RequiredFieldRule(
                rule_id="observation.effective_date.required",
                field_path="observation.effective_date",
                description="Observation date is required",
                severity=ValidationSeverity.ERROR,
            )
        )

        validation_engine.register_rule(
            TemporalRule(
                rule_id="observation.effective_date.not_future",
                field_path="observation.effective_date",
                description="Observation date cannot be in the future",
                temporal_type="past",
                severity=ValidationSeverity.ERROR,
            )
        )

    @staticmethod
    def register_condition_rules() -> None:
        """Register validation rules for condition/diagnosis data."""
        # Condition code rules
        validation_engine.register_rule(
            RequiredFieldRule(
                rule_id="condition.code.required",
                field_path="condition.code",
                description="Condition code is required",
                severity=ValidationSeverity.ERROR,
            )
        )

        validation_engine.register_rule(
            CodeSetRule(
                rule_id="condition.code.icd10",
                field_path="condition.code.icd10",
                description="ICD-10 code validation",
                severity=ValidationSeverity.ERROR,
                code_system="ICD10",
            )
        )

        validation_engine.register_rule(
            CodeSetRule(
                rule_id="condition.code.snomed",
                field_path="condition.code.snomed",
                description="SNOMED CT code validation",
                severity=ValidationSeverity.WARNING,
                code_system="SNOMED",
            )
        )

        # Clinical status rules
        validation_engine.register_rule(
            RequiredFieldRule(
                rule_id="condition.clinical_status.required",
                field_path="condition.clinical_status",
                description="Clinical status is required",
                severity=ValidationSeverity.ERROR,
            )
        )

        validation_engine.register_rule(
            CodeSetRule(
                rule_id="condition.clinical_status.codeset",
                field_path="condition.clinical_status",
                description="Clinical status validation",
                severity=ValidationSeverity.ERROR,
                code_system="ConditionClinicalStatus",
                allowed_codes={
                    "active",
                    "recurrence",
                    "relapse",
                    "inactive",
                    "remission",
                    "resolved",
                },
            )
        )

        # Verification status rules
        validation_engine.register_rule(
            CodeSetRule(
                rule_id="condition.verification_status.codeset",
                field_path="condition.verification_status",
                description="Verification status validation",
                severity=ValidationSeverity.WARNING,
                code_system="ConditionVerificationStatus",
                allowed_codes={
                    "unconfirmed",
                    "provisional",
                    "differential",
                    "confirmed",
                    "refuted",
                    "entered-in-error",
                },
            )
        )

        # Onset date rules
        validation_engine.register_rule(
            TemporalRule(
                rule_id="condition.onset_date.past",
                field_path="condition.onset_date",
                description="Onset date must be in the past",
                severity=ValidationSeverity.WARNING,
                temporal_type="past",
            )
        )

        # Cross-field validation: onset after birth
        validation_engine.register_rule(
            CrossFieldRule(
                rule_id="condition.onset_after_birth",
                field_path="condition.onset_date",
                description="Condition onset must be after birth date",
                severity=ValidationSeverity.ERROR,
                error_message="Condition onset cannot be before patient birth date",
                related_fields=["patient.birth_date"],
                validation_function=lambda fields, context: (
                    fields.get("condition.onset_date")
                    >= fields.get("patient.birth_date")
                    if all(fields.values())
                    else True
                ),
            )
        )

        # Severity rules
        validation_engine.register_rule(
            CodeSetRule(
                rule_id="condition.severity.codeset",
                field_path="condition.severity",
                description="Severity code validation",
                severity=ValidationSeverity.INFO,
                code_system="SNOMED",
                allowed_codes={
                    "255604002",  # Mild
                    "6736007",  # Moderate
                    "24484000",  # Severe
                    "442452003",  # Life threatening
                },
            )
        )

    @staticmethod
    def register_allergy_rules() -> None:
        """Register validation rules for allergy data."""
        # Allergen rules
        validation_engine.register_rule(
            RequiredFieldRule(
                rule_id="allergy.code.required",
                field_path="allergy.code",
                description="Allergen code is required",
                severity=ValidationSeverity.ERROR,
            )
        )

        # Reaction rules
        validation_engine.register_rule(
            CodeSetRule(
                rule_id="allergy.reaction.manifestation.codeset",
                field_path="allergy.reaction.manifestation",
                description="Reaction manifestation validation",
                severity=ValidationSeverity.WARNING,
                code_system="SNOMED",
            )
        )

        # Severity rules
        validation_engine.register_rule(
            CodeSetRule(
                rule_id="allergy.reaction.severity.codeset",
                field_path="allergy.reaction.severity",
                description="Reaction severity validation",
                severity=ValidationSeverity.WARNING,
                code_system="AllergyIntoleranceSeverity",
                allowed_codes={"mild", "moderate", "severe"},
            )
        )

        # Clinical status rules
        validation_engine.register_rule(
            RequiredFieldRule(
                rule_id="allergy.clinical_status.required",
                field_path="allergy.clinical_status",
                description="Allergy clinical status is required",
                severity=ValidationSeverity.ERROR,
            )
        )

        validation_engine.register_rule(
            CodeSetRule(
                rule_id="allergy.clinical_status.codeset",
                field_path="allergy.clinical_status",
                description="Allergy clinical status validation",
                severity=ValidationSeverity.ERROR,
                code_system="AllergyIntoleranceClinicalStatus",
                allowed_codes={"active", "inactive", "resolved"},
            )
        )

    @staticmethod
    def register_all_rules() -> None:
        """Register all healthcare validation rules."""
        HealthcareValidationRules.register_patient_rules()
        HealthcareValidationRules.register_immunization_rules()
        HealthcareValidationRules.register_medication_rules()
        HealthcareValidationRules.register_observation_rules()
        HealthcareValidationRules.register_condition_rules()
        HealthcareValidationRules.register_allergy_rules()

        logger.info(
            "Registered %d healthcare validation rules",
            len(validation_engine.rule_registry),
        )


# Initialize healthcare validation rules
HealthcareValidationRules.register_all_rules()
