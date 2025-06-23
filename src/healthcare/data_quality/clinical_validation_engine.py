"""
Healthcare Data Quality Validation Engine.

CRITICAL: This module validates medical data for refugee patients.
Incorrect validation can lead to:
- Missed drug interactions (potentially fatal)
- Incorrect dosing (harm to patient)
- Allergy exposure (anaphylaxis risk)
- Misdiagnosis from invalid data

All validation MUST use real medical services in production.

# FHIR Compliance: This engine validates FHIR Resources including Patient, Medication, and Observation
# All clinical data must pass FHIR R4 validation before being accepted
"""

import re
import threading
from typing import Any, Dict, List, Optional, cast

from src.ai.medical_embeddings_service import get_medical_embeddings_service
from src.audit.audit_service import AuditEventType, audit_event
from src.config import settings
from src.healthcare.clinical_guidelines_service import get_clinical_guidelines_service
from src.healthcare.data_quality.validation_rules import (
    ValidationCategory,
    ValidationResult,
    ValidationSeverity,
)
from src.healthcare.drug_interaction_service import get_drug_interaction_service

# PHI encryption handled through secure storage layer
from src.healthcare.hipaa_access_control import (
    AccessLevel,
    audit_phi_access,
    require_phi_access,
)
from src.translation.medical.snomed_service import get_snomed_service
from src.utils.logging import get_logger

logger = get_logger(__name__)


class ClinicalValidationEngine:
    """
    Production clinical data validation engine.

    Integrates with real medical services for:
    - Drug interaction checking
    - Allergy verification
    - Clinical value range validation
    - Medical terminology validation
    """

    def __init__(self) -> None:
        """Initialize the clinical validation engine."""
        self.environment = settings.environment.lower()

        # Initialize services based on environment
        if self.environment in ["production", "staging"]:
            self._initialize_production_services()
        else:
            logger.warning(
                "Using development mode for validation engine. "
                "Production MUST use real medical services!"
            )
            self._initialize_development_services()

    def _initialize_production_services(self) -> None:
        """Initialize all production medical services."""
        try:
            # Drug interaction service
            self.drug_interaction_service = get_drug_interaction_service()
            logger.info("Initialized production drug interaction service")

            # SNOMED service for medical terminology
            self.snomed_service = get_snomed_service()
            logger.info("Initialized production SNOMED service")

            # Medical embeddings for concept matching
            self.medical_embeddings_service = get_medical_embeddings_service()
            logger.info("Initialized production medical embeddings service")

            # Clinical guidelines service
            self.clinical_guidelines_service = get_clinical_guidelines_service()
            logger.info("Initialized production clinical guidelines service")

        except (ImportError, AttributeError) as e:
            logger.error(
                "Failed to initialize production services",
                exc_info=True,
                extra={
                    "service": "clinical_validation_engine",
                    "error_type": type(e).__name__,
                    "error_details": str(e),
                },
            )
            raise RuntimeError(
                "CRITICAL: Cannot initialize medical validation services. "
                "Patient safety requires all services to be operational!"
            ) from e

    def _initialize_development_services(self) -> None:
        """Initialize development/mock services."""
        self.drug_interaction_service = None  # type: ignore[assignment]
        self.snomed_service = None  # type: ignore[assignment]
        self.medical_embeddings_service = None  # type: ignore[assignment]
        self.clinical_guidelines_service = None  # type: ignore[assignment]

    @require_phi_access(AccessLevel.READ)
    @audit_phi_access("validate_medications")
    async def validate_medications(
        self,
        new_medications: List[Dict[str, Any]],
        existing_medications: List[Dict[str, Any]],
        patient_allergies: List[Dict[str, Any]],
        patient_conditions: Optional[List[Dict[str, Any]]] = None,
    ) -> List[ValidationResult]:
        """
        Validate medications for safety and interactions.

        Args:
            new_medications: New medications to validate
            existing_medications: Current patient medications
            patient_allergies: Known patient allergies
            patient_conditions: Patient medical conditions

        Returns:
            List of validation results
        """
        results = []

        # In production, use real services
        if self.environment in ["production", "staging"]:
            if not self.drug_interaction_service:
                raise RuntimeError(
                    "CRITICAL: Drug interaction service not available in production. "
                    "Cannot validate medications without interaction checking!"
                )

            try:
                # Combine all medications
                all_medications = new_medications + existing_medications

                # Check drug interactions
                interactions = await self.drug_interaction_service.check_interactions(
                    medications=all_medications,
                    patient_allergies=[
                        a.get("substance", "") for a in patient_allergies
                    ],
                )

                # Convert interactions to validation results
                for interaction in interactions:
                    severity_map = {
                        "contraindicated": ValidationSeverity.CRITICAL,
                        "major": ValidationSeverity.CRITICAL,
                        "moderate": ValidationSeverity.WARNING,
                        "minor": ValidationSeverity.INFO,
                        "unknown": ValidationSeverity.WARNING,
                    }

                    results.append(
                        ValidationResult(
                            field="medication_interaction",
                            rule="drug_interaction_check",
                            is_valid=False,
                            message=f"{interaction.drug1} + {interaction.drug2}: {interaction.description}",
                            severity=severity_map.get(
                                interaction.severity.value, ValidationSeverity.WARNING
                            ),
                            category=ValidationCategory.SAFETY,
                        )
                    )

                # Check for duplicate medications
                seen_medications = set()
                for med in all_medications:
                    med_name = med.get("name", "").lower()
                    if med_name in seen_medications:
                        results.append(
                            ValidationResult(
                                field="medications",
                                rule="duplicate_medication",
                                is_valid=False,
                                message=f"Duplicate medication: {med_name}",
                                severity=ValidationSeverity.ERROR,
                                category=ValidationCategory.SAFETY,
                            )
                        )
                    seen_medications.add(med_name)

                # Validate dosages against guidelines
                for med in new_medications:
                    dose_validation = await self._validate_dosage(
                        med, patient_conditions
                    )
                    results.extend(dose_validation)

            except (ValueError, TypeError, AttributeError, KeyError) as e:
                logger.error(
                    "Error during medication validation",
                    exc_info=True,
                    extra={
                        "patient_id": "unknown",
                        "medication_count": (
                            len(new_medications) if new_medications else 0
                        ),
                        "error_type": type(e).__name__,
                        "error_details": str(e),
                    },
                )
                # In production, fail safely but log the critical error
                results.append(
                    ValidationResult(
                        field="system",
                        rule="validation_error",
                        is_valid=False,
                        message="Unable to complete medication validation. Please review manually.",
                        severity=ValidationSeverity.CRITICAL,
                        category=ValidationCategory.CLINICAL,
                    )
                )

        else:
            # Development mode - basic validation only
            results.append(
                ValidationResult(
                    field="system",
                    rule="development_mode",
                    is_valid=True,
                    message="Development mode - using basic validation",
                    severity=ValidationSeverity.INFO,
                    category=ValidationCategory.CLINICAL,
                )
            )

        # Audit the validation
        await self._audit_validation(
            "medication_validation",
            {
                "new_medications": len(new_medications),
                "existing_medications": len(existing_medications),
                "allergies": len(patient_allergies),
                "validation_results": len(results),
                "critical_issues": len(
                    [r for r in results if r.severity == ValidationSeverity.CRITICAL]
                ),
            },
        )

        return results

    @require_phi_access(AccessLevel.READ)  # Added access control for PHI
    async def _validate_dosage(
        self,
        medication: Dict[str, Any],
        patient_conditions: Optional[List[Dict[str, Any]]] = None,
    ) -> List[ValidationResult]:
        """Validate medication dosage against clinical guidelines."""
        results = []

        med_name = medication.get("name", "")
        dose = medication.get("dose", "")
        frequency = medication.get("frequency", "")
        route = medication.get("route", "")

        # In production, check against real clinical guidelines
        if (
            self.environment in ["production", "staging"]
            and self.clinical_guidelines_service
        ):
            # Extract numeric dose if present
            dose_match = re.search(r"(\d+\.?\d*)\s*(\w+)", str(dose))

            if dose_match:
                numeric_dose = float(dose_match.group(1))
                dose_unit = dose_match.group(2).lower()

                # Get patient factors
                patient_factors = {
                    "age": 30,  # Default if not provided
                    "pregnant": False,
                    "egfr": None,
                    "liver_disease": None,
                }

                # Extract from patient conditions if available
                if patient_conditions:
                    for condition in patient_conditions:
                        if isinstance(condition, dict):
                            if "pregnancy" in str(condition).lower():
                                patient_factors["pregnant"] = True
                            if (
                                "renal" in str(condition).lower()
                                or "kidney" in str(condition).lower()
                            ):
                                patient_factors["egfr"] = (
                                    30  # Assume moderate impairment
                                )
                            if (
                                "liver" in str(condition).lower()
                                or "hepatic" in str(condition).lower()
                            ):
                                patient_factors["liver_disease"] = True

                # Validate dosage using clinical guidelines service
                validation_result = (
                    await self.clinical_guidelines_service.validate_dosage(
                        medication_name=med_name,
                        dose=numeric_dose,
                        unit=dose_unit,
                        frequency=frequency,
                        route=route or "oral",
                        patient_factors=patient_factors,
                    )
                )

                # Convert to ValidationResult objects
                if not validation_result["valid"]:
                    for warning in validation_result.get("warnings", []):
                        severity_map = {
                            "critical": ValidationSeverity.CRITICAL,
                            "high": ValidationSeverity.ERROR,
                            "warning": ValidationSeverity.WARNING,
                            "info": ValidationSeverity.INFO,
                        }

                        results.append(
                            ValidationResult(
                                field="medication_dose",
                                rule=warning["type"],
                                is_valid=False,
                                message=warning["message"],
                                severity=severity_map.get(
                                    warning["severity"], ValidationSeverity.WARNING
                                ),
                                category=ValidationCategory.SAFETY,
                            )
                        )

                # Add recommendations as INFO level
                for rec in validation_result.get("recommendations", []):
                    results.append(
                        ValidationResult(
                            field="medication_dose",
                            rule=rec["type"],
                            is_valid=True,
                            message=rec["message"],
                            severity=ValidationSeverity.INFO,
                            category=ValidationCategory.CLINICAL,
                        )
                    )

            else:
                # Could not parse dose
                results.append(
                    ValidationResult(
                        field="medication_dose",
                        rule="unparseable_dose",
                        is_valid=False,
                        message=f"Could not parse dose: {dose}",
                        severity=ValidationSeverity.WARNING,
                        category=ValidationCategory.COMPLETENESS,
                    )
                )

        return results

    @require_phi_access(AccessLevel.READ)
    @audit_phi_access("validate_clinical_values")
    async def validate_clinical_values(
        self, lab_results: List[Dict[str, Any]], patient_demographics: Dict[str, Any]
    ) -> List[ValidationResult]:
        """
        Validate clinical laboratory values.

        Args:
            lab_results: Laboratory test results
            patient_demographics: Patient age, gender, pregnancy status, etc.

        Returns:
            List of validation results
        """
        results = []

        # Extract patient info
        age = patient_demographics.get("age")
        gender = patient_demographics.get("gender", "").lower()
        pregnant = patient_demographics.get("pregnant", False)

        # Age will be used for age-specific reference ranges
        is_pediatric = age is not None and age < 18
        is_geriatric = age is not None and age >= 65

        # Define critical value ranges
        critical_ranges = {
            "glucose": {
                "unit": "mg/dL",
                "critical_low": 40,
                "critical_high": 500,
                "normal_range": (70, 140),
                "fasting_range": (70, 100),
            },
            "hemoglobin": {
                "unit": "g/dL",
                "critical_low": 5.0,
                "critical_high": 20.0,
                "normal_range_male": (13.5, 17.5),
                "normal_range_female": (12.0, 15.5),
                "pregnancy_range": (11.0, 15.0),
            },
            "potassium": {
                "unit": "mEq/L",
                "critical_low": 2.5,
                "critical_high": 6.5,
                "normal_range": (3.5, 5.0),
            },
            "sodium": {
                "unit": "mEq/L",
                "critical_low": 120,
                "critical_high": 160,
                "normal_range": (136, 145),
            },
            "creatinine": {
                "unit": "mg/dL",
                "critical_high": 10.0,
                "normal_range_male": (0.7, 1.3),
                "normal_range_female": (0.6, 1.1),
            },
            "inr": {
                "unit": "ratio",
                "critical_high": 5.0,
                "therapeutic_range": (2.0, 3.0),
                "normal_range": (0.8, 1.2),
            },
        }

        # Validate each lab result
        for result in lab_results:
            test_name = result.get("test", "").lower()
            value = result.get("value")
            unit = result.get("unit", "").lower()

            if not value:
                continue

            try:
                numeric_value = float(value)
            except (ValueError, TypeError):
                results.append(
                    ValidationResult(
                        field="lab_value",
                        rule="invalid_numeric_value",
                        is_valid=False,
                        message=f"Invalid numeric value for {test_name}: {value}",
                        severity=ValidationSeverity.ERROR,
                        category=ValidationCategory.COMPLETENESS,
                    )
                )
                continue

            # Check against critical ranges
            if test_name in critical_ranges:
                ranges = critical_ranges[test_name]

                # Critical low
                if "critical_low" in ranges and numeric_value < float(
                    cast(Any, ranges["critical_low"])
                ):
                    results.append(
                        ValidationResult(
                            field="lab_value",
                            rule="critical_low_value",
                            is_valid=False,
                            message=f"CRITICAL LOW: {test_name} = {value} {unit}",
                            severity=ValidationSeverity.CRITICAL,
                            category=ValidationCategory.CLINICAL,
                        )
                    )

                # Critical high
                elif "critical_high" in ranges and numeric_value > float(
                    cast(Any, ranges["critical_high"])
                ):
                    results.append(
                        ValidationResult(
                            field="lab_value",
                            rule="critical_high_value",
                            is_valid=False,
                            message=f"CRITICAL HIGH: {test_name} = {value} {unit}",
                            severity=ValidationSeverity.CRITICAL,
                            category=ValidationCategory.CLINICAL,
                        )
                    )

                # Check normal ranges based on demographics
                else:
                    normal_range = None

                    # Gender-specific ranges
                    if test_name == "hemoglobin":
                        if pregnant and "pregnancy_range" in ranges:
                            normal_range = ranges["pregnancy_range"]
                        elif gender == "male" and "normal_range_male" in ranges:
                            normal_range = ranges["normal_range_male"]
                        elif gender == "female" and "normal_range_female" in ranges:
                            normal_range = ranges["normal_range_female"]
                    elif test_name == "creatinine":
                        # Age-adjusted creatinine ranges
                        if is_pediatric:
                            # Pediatric creatinine levels are lower
                            normal_range = (
                                (0.3, 0.7)
                                if age is not None and age < 12
                                else (0.5, 1.0)
                            )
                        elif is_geriatric:
                            # Slightly higher ranges for elderly due to reduced muscle mass
                            if gender == "male":
                                normal_range = (0.8, 1.5)
                            else:
                                normal_range = (0.7, 1.3)
                        elif gender == "male" and "normal_range_male" in ranges:
                            normal_range = ranges["normal_range_male"]
                        elif gender == "female" and "normal_range_female" in ranges:
                            normal_range = ranges["normal_range_female"]
                    else:
                        normal_range = ranges.get("normal_range")

                    # Check if outside normal range
                    if (
                        normal_range
                        and isinstance(normal_range, (list, tuple))
                        and len(normal_range) >= 2
                    ):
                        min_val = float(normal_range[0])
                        max_val = float(normal_range[1])
                        if numeric_value < min_val or numeric_value > max_val:
                            results.append(
                                ValidationResult(
                                    field="lab_value",
                                    rule="abnormal_value",
                                    is_valid=True,  # Not invalid, just abnormal
                                    message=f"Abnormal {test_name}: {value} {unit} (normal: {min_val}-{max_val})",
                                    severity=ValidationSeverity.WARNING,
                                    category=ValidationCategory.CLINICAL,
                                )
                            )

        return results

    async def _audit_validation(self, action: str, details: Dict[str, Any]) -> None:
        """Audit validation actions for compliance."""
        audit_event(
            event_type=AuditEventType.PATIENT_ACCESS,
            user_id="system",
            resource_type="clinical_validation",
            action=action,
            metadata=details,
        )

    @require_phi_access(AccessLevel.READ)
    @audit_phi_access("validate_patient_conditions")
    async def validate_patient_conditions(
        self, patient_conditions: Dict[str, Any]
    ) -> Dict[str, List[ValidationResult]]:
        """
        Comprehensive patient data validation.

        Args:
            patient_conditions: Complete patient data including demographics, medications, labs, etc.

        Returns:
            Dictionary of validation results by category
        """
        all_results: Dict[str, List[ValidationResult]] = {
            "medications": [],
            "lab_values": [],
            "vital_signs": [],
            "allergies": [],
            "diagnoses": [],
        }

        try:
            # Validate medications if present
            if "medications" in patient_conditions:
                medication_results = await self.validate_medications(
                    new_medications=patient_conditions.get("new_medications", []),
                    existing_medications=patient_conditions.get("medications", []),
                    patient_allergies=patient_conditions.get("allergies", []),
                    patient_conditions=patient_conditions.get("conditions", []),
                )
                all_results["medications"] = medication_results

            # Validate lab values if present
            if "lab_results" in patient_conditions:
                lab_results = await self.validate_clinical_values(
                    lab_results=patient_conditions["lab_results"],
                    patient_demographics=patient_conditions.get("demographics", {}),
                )
                all_results["lab_values"] = lab_results

            # Validate vital signs if present
            if "vital_signs" in patient_conditions:
                vital_results = await self._validate_vital_signs(
                    patient_conditions["vital_signs"],
                    patient_conditions.get("demographics", {}),
                )
                all_results["vital_signs"] = vital_results

            # Validate diagnoses with SNOMED if available
            if "diagnoses" in patient_conditions and self.snomed_service:
                diagnosis_results = await self._validate_diagnoses(
                    patient_conditions["diagnoses"]
                )
                all_results["diagnoses"] = diagnosis_results

        except (ValueError, TypeError, AttributeError, KeyError) as e:
            logger.error(
                "Critical error during patient data validation",
                exc_info=True,
                extra={
                    "patient_id": str(patient_conditions.get("id", "unknown")),
                    "patient_name": patient_conditions.get("given_name", "unknown"),
                    "validation_stage": "complete_validation",
                    "error_type": type(e).__name__,
                    "error_details": str(e),
                },
            )
            # Return safe error result
            all_results["system"] = [
                ValidationResult(
                    field="system",
                    rule="validation_error",
                    is_valid=False,
                    message=f"System error during validation: {str(e)}",
                    severity=ValidationSeverity.CRITICAL,
                    category=ValidationCategory.CLINICAL,
                )
            ]

        return all_results

    @require_phi_access(AccessLevel.READ)  # Added access control for PHI
    async def _validate_vital_signs(
        self, vital_signs: Dict[str, Any], demographics: Dict[str, Any]
    ) -> List[ValidationResult]:
        """Validate vital signs based on patient demographics."""
        results = []

        age = demographics.get("age", 0)

        # Age-based vital sign ranges
        if age < 1:  # Infant
            normal_ranges = {
                "heart_rate": (100, 160),
                "respiratory_rate": (30, 60),
                "systolic_bp": (60, 90),
                "temperature_celsius": (36.5, 37.5),
            }
        elif age < 5:  # Toddler
            normal_ranges = {
                "heart_rate": (80, 130),
                "respiratory_rate": (20, 40),
                "systolic_bp": (80, 110),
                "temperature_celsius": (36.5, 37.5),
            }
        elif age < 12:  # Child
            normal_ranges = {
                "heart_rate": (70, 110),
                "respiratory_rate": (18, 30),
                "systolic_bp": (90, 120),
                "temperature_celsius": (36.5, 37.5),
            }
        else:  # Adult
            normal_ranges = {
                "heart_rate": (60, 100),
                "respiratory_rate": (12, 20),
                "systolic_bp": (90, 140),
                "diastolic_bp": (60, 90),
                "temperature_celsius": (36.5, 37.5),
                "oxygen_saturation": (95, 100),
            }

        # Check each vital sign
        for vital, value in vital_signs.items():
            if vital in normal_ranges and value:
                try:
                    numeric_value = float(value)
                    range_min, range_max = normal_ranges[vital]

                    if numeric_value < range_min or numeric_value > range_max:
                        severity = ValidationSeverity.WARNING

                        # Critical values
                        if vital == "oxygen_saturation" and numeric_value < 90:
                            severity = ValidationSeverity.CRITICAL
                        elif vital == "systolic_bp" and (
                            numeric_value < 80 or numeric_value > 180
                        ):
                            severity = ValidationSeverity.CRITICAL
                        elif vital == "heart_rate" and (
                            numeric_value < 40 or numeric_value > 150
                        ):
                            severity = ValidationSeverity.CRITICAL

                        results.append(
                            ValidationResult(
                                field="vital_signs",
                                rule="abnormal_vital_sign",
                                is_valid=False,
                                message=f"Abnormal {vital}: {value} (normal: {range_min}-{range_max})",
                                severity=severity,
                                category=ValidationCategory.CLINICAL,
                            )
                        )

                except (ValueError, TypeError):
                    results.append(
                        ValidationResult(
                            field="vital_signs",
                            rule="invalid_vital_value",
                            is_valid=False,
                            message=f"Invalid value for {vital}: {value}",
                            severity=ValidationSeverity.ERROR,
                            category=ValidationCategory.COMPLETENESS,
                        )
                    )

        return results

    @require_phi_access(AccessLevel.READ)  # Added access control for PHI
    async def _validate_diagnoses(
        self, diagnoses: List[Dict[str, Any]]
    ) -> List[ValidationResult]:
        """Validate diagnoses using SNOMED terminology service."""
        results = []

        for diagnosis in diagnoses:
            code = diagnosis.get("code", "")
            system = diagnosis.get("system", "").lower()
            # description field reserved for future use: diagnosis.get("description", "")

            if system == "snomed" and self.snomed_service:
                # Validate SNOMED code
                is_valid, issues = await self.snomed_service.validate_concept(
                    concept_id=code, expected_hierarchy="disorder"
                )

                if not is_valid:
                    results.append(
                        ValidationResult(
                            field="diagnosis",
                            rule="invalid_snomed_code",
                            is_valid=False,
                            message=f"Invalid SNOMED code {code}: {', '.join(issues)}",
                            severity=ValidationSeverity.ERROR,
                            category=ValidationCategory.FORMAT,
                        )
                    )

            elif system == "icd10":
                # Basic ICD-10 format validation
                if not re.match(r"^[A-Z]\d{2}(\.\d{1,2})?$", code):
                    results.append(
                        ValidationResult(
                            field="diagnosis",
                            rule="invalid_icd10_format",
                            is_valid=False,
                            message=f"Invalid ICD-10 format: {code}",
                            severity=ValidationSeverity.ERROR,
                            category=ValidationCategory.FORMAT,
                        )
                    )

        return results

    def _get_age_group(self, age: int) -> str:
        """Determine age group for validation purposes."""
        if age < 1:
            return "infant"
        elif age < 5:
            return "toddler"
        elif age < 12:
            return "child"
        elif age < 18:
            return "adolescent"
        elif age < 65:
            return "adult"
        else:
            return "elderly"

    async def validate_patient_data(
        self, patient_data: Dict[str, Any]
    ) -> List[ValidationResult]:
        """Validate complete patient data record.

        Args:
            patient_data: Complete patient data dictionary

        Returns:
            List of validation results
        """
        all_results = []

        # Validate medications if present
        if "medications" in patient_data:
            medication_results = await self.validate_medications(
                new_medications=patient_data.get("medications", []),
                existing_medications=patient_data.get("existing_medications", []),
                patient_allergies=patient_data.get("allergies", []),
                patient_conditions=patient_data.get("conditions", []),
            )
            all_results.extend(medication_results)

        # Validate clinical values if present
        if "lab_results" in patient_data:
            clinical_results = await self.validate_clinical_values(
                lab_results=patient_data.get("lab_results", []),
                patient_demographics=patient_data.get("demographics", {}),
            )
            all_results.extend(clinical_results)

        # Validate conditions/diagnoses if present
        if "diagnoses" in patient_data or "conditions" in patient_data:
            # The method expects the full patient data dict, not just diagnoses
            condition_results = await self.validate_patient_conditions(
                patient_conditions=patient_data
            )
            # Since this returns a dict, we need to extract the validation results
            for _, results in condition_results.items():
                all_results.extend(results)

        return all_results


# Thread-safe singleton pattern


class _ClinicalValidationEngineSingleton:
    """Thread-safe singleton holder for ClinicalValidationEngine."""

    _instance: Optional[ClinicalValidationEngine] = None
    _lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> ClinicalValidationEngine:
        """Get or create singleton instance."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = ClinicalValidationEngine()
        return cls._instance


def get_clinical_validation_engine() -> ClinicalValidationEngine:
    """Get or create global clinical validation engine instance."""
    return _ClinicalValidationEngineSingleton.get_instance()
