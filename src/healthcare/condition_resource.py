"""Condition FHIR Resource Implementation.

This module implements the Condition FHIR resource for Haven Health Passport,
handling diagnoses, problems, and health concerns with special considerations
for refugee populations including endemic diseases and conflict-related conditions.
All PHI data is encrypted and access is controlled through role-based permissions.
"""

import logging
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from fhirclient.models.age import Age
from fhirclient.models.annotation import Annotation
from fhirclient.models.codeableconcept import CodeableConcept
from fhirclient.models.coding import Coding
from fhirclient.models.condition import Condition, ConditionEvidence, ConditionStage
from fhirclient.models.extension import Extension
from fhirclient.models.fhirdate import FHIRDate
from fhirclient.models.fhirreference import FHIRReference
from fhirclient.models.period import Period
from fhirclient.models.quantity import Quantity
from fhirclient.models.range import Range

from src.healthcare.hipaa_access_control import (
    AccessLevel,
    audit_phi_access,
    require_phi_access,
)

from .fhir_base import BaseFHIRResource
from .fhir_profiles import REFUGEE_CONDITION_PROFILE

logger = logging.getLogger(__name__)

# FHIR resource type for this module
__fhir_resource__ = "Condition"


class ConditionClinicalStatus(Enum):
    """Condition clinical status codes."""

    ACTIVE = "active"  # Active condition
    RECURRENCE = "recurrence"  # Recurrence of past condition
    RELAPSE = "relapse"  # Relapse of remitted condition
    INACTIVE = "inactive"  # Inactive condition
    REMISSION = "remission"  # In remission
    RESOLVED = "resolved"  # Resolved condition


class ConditionVerificationStatus(Enum):
    """Condition verification status codes."""

    UNCONFIRMED = "unconfirmed"  # Unconfirmed condition
    PROVISIONAL = "provisional"  # Provisional diagnosis
    DIFFERENTIAL = "differential"  # Differential diagnosis
    CONFIRMED = "confirmed"  # Confirmed condition
    REFUTED = "refuted"  # Refuted condition
    ENTERED_IN_ERROR = "entered-in-error"  # Entered in error


class ConditionCategory(Enum):
    """Condition category codes."""

    PROBLEM_LIST_ITEM = "problem-list-item"  # Problem list item
    ENCOUNTER_DIAGNOSIS = "encounter-diagnosis"  # Encounter diagnosis

    # Extended categories for refugee care
    CHRONIC_DISEASE = "chronic-disease"  # Chronic disease
    INFECTIOUS_DISEASE = "infectious-disease"  # Infectious disease
    MENTAL_HEALTH = "mental-health"  # Mental health condition
    NUTRITIONAL = "nutritional"  # Nutritional disorder
    TRAUMA_RELATED = "trauma-related"  # Trauma/conflict related
    ENVIRONMENTAL = "environmental"  # Environmental exposure
    MATERNAL_HEALTH = "maternal-health"  # Maternal health condition


class ConditionSeverity(Enum):
    """Condition severity codes."""

    MILD = "24484000"  # Mild severity
    MODERATE = "6736007"  # Moderate severity
    SEVERE = "24484000"  # Severe


class CommonRefugeeConditions(Enum):
    """Common conditions in refugee populations with ICD-10 codes."""

    # Infectious diseases
    TUBERCULOSIS = "A15.9"  # Tuberculosis
    MALARIA = "B54"  # Malaria
    HIV = "B20"  # HIV disease
    HEPATITIS_B = "B16.9"  # Acute hepatitis B
    HEPATITIS_C = "B17.1"  # Acute hepatitis C
    SCHISTOSOMIASIS = "B65.9"  # Schistosomiasis
    INTESTINAL_PARASITES = "B82.9"  # Intestinal parasitosis

    # Nutritional conditions
    SEVERE_ACUTE_MALNUTRITION = "E43"  # Severe malnutrition
    MODERATE_ACUTE_MALNUTRITION = "E44.0"  # Moderate malnutrition
    VITAMIN_A_DEFICIENCY = "E50.9"  # Vitamin A deficiency
    IRON_DEFICIENCY_ANEMIA = "D50.9"  # Iron deficiency anemia

    # Mental health
    PTSD = "F43.1"  # Post-traumatic stress disorder
    DEPRESSION = "F32.9"  # Depression
    ANXIETY = "F41.9"  # Anxiety disorder
    ADJUSTMENT_DISORDER = "F43.2"  # Adjustment disorder

    # Chronic diseases
    DIABETES = "E11.9"  # Type 2 diabetes
    HYPERTENSION = "I10"  # Essential hypertension
    ASTHMA = "J45.9"  # Asthma
    EPILEPSY = "G40.9"  # Epilepsy

    # Maternal health
    PREGNANCY = "Z33"  # Pregnancy state
    POSTPARTUM = "O90.9"  # Postpartum complication

    # Environmental/trauma
    PHYSICAL_TRAUMA = "T14.9"  # Physical trauma
    SEXUAL_VIOLENCE = "T74.2"  # Sexual abuse
    TORTURE_SEQUELAE = "T74.4"  # Torture sequelae


class ConditionResource(BaseFHIRResource):
    """Condition FHIR resource implementation for Haven Health Passport."""

    def __init__(self) -> None:
        """Initialize Condition resource handler."""
        super().__init__(Condition)
        self._encrypted_fields = [
            "identifier[0].value",  # Condition ID
            "subject.reference",  # Patient reference
        ]

    @require_phi_access(AccessLevel.WRITE)
    @audit_phi_access("create_condition_resource")
    def create_resource(self, data: Dict[str, Any]) -> Condition:
        """Create a new Condition resource.

        Args:
            data: Dictionary containing condition data

        Returns:
            Created Condition resource
        """
        condition = Condition()

        # Set clinical status (required)
        condition.clinicalStatus = self._create_codeable_concept(
            {
                "coding": [
                    {
                        "system": "http://terminology.hl7.org/CodeSystem/condition-clinical",
                        "code": data.get(
                            "clinical_status", ConditionClinicalStatus.ACTIVE.value
                        ),
                    }
                ]
            }
        )

        # Set verification status
        if "verification_status" in data:
            condition.verificationStatus = self._create_codeable_concept(
                {
                    "coding": [
                        {
                            "system": "http://terminology.hl7.org/CodeSystem/condition-ver-status",
                            "code": data["verification_status"],
                        }
                    ]
                }
            )

        # Set category
        if "category" in data:
            condition.category = [
                self._create_codeable_concept(cat) for cat in data["category"]
            ]

        # Set severity
        if "severity" in data:
            condition.severity = self._create_codeable_concept(data["severity"])

        # Set code (required)
        condition.code = self._create_codeable_concept(data["code"])

        # Set body site
        if "body_site" in data:
            condition.bodySite = [
                self._create_codeable_concept(site) for site in data["body_site"]
            ]

        # Set subject (required)
        condition.subject = FHIRReference({"reference": data["subject"]})
        # Set encounter
        if "encounter" in data:
            condition.encounter = FHIRReference({"reference": data["encounter"]})

        # Set onset
        if "onset_datetime" in data:
            condition.onsetDateTime = self._create_fhir_datetime(data["onset_datetime"])
        elif "onset_age" in data:
            condition.onsetAge = self._create_age(data["onset_age"])
        elif "onset_period" in data:
            condition.onsetPeriod = self._create_period(data["onset_period"])
        elif "onset_range" in data:
            condition.onsetRange = self._create_range(data["onset_range"])
        elif "onset_string" in data:
            condition.onsetString = data["onset_string"]

        # Set abatement
        if "abatement_datetime" in data:
            condition.abatementDateTime = self._create_fhir_datetime(
                data["abatement_datetime"]
            )
        elif "abatement_age" in data:
            condition.abatementAge = self._create_age(data["abatement_age"])
        elif "abatement_period" in data:
            condition.abatementPeriod = self._create_period(data["abatement_period"])
        elif "abatement_range" in data:
            condition.abatementRange = self._create_range(data["abatement_range"])
        elif "abatement_string" in data:
            condition.abatementString = data["abatement_string"]

        # Set recorded date
        if "recorded_date" in data:
            condition.recordedDate = self._create_fhir_datetime(data["recorded_date"])

        # Set recorder
        if "recorder" in data:
            condition.recorder = FHIRReference({"reference": data["recorder"]})

        # Set asserter
        if "asserter" in data:
            condition.asserter = FHIRReference({"reference": data["asserter"]})

        # Set stage
        if "stage" in data:
            condition.stage = [self._create_stage(s) for s in data["stage"]]

        # Set evidence
        if "evidence" in data:
            condition.evidence = [self._create_evidence(e) for e in data["evidence"]]

        # Set notes
        if "note" in data:
            condition.note = [self._create_annotation(note) for note in data["note"]]

        # Add refugee-specific extensions
        if "refugee_context" in data:
            self._add_refugee_context(condition, data["refugee_context"])

        # Add profile and validate
        self.add_meta_profile(condition, REFUGEE_CONDITION_PROFILE)

        # Store and validate
        self._resource = condition
        self.validate()

        # Add audit entry
        self.add_audit_entry("create", data.get("created_by", "system"))

        return condition

    def get_encrypted_fields(self) -> List[str]:
        """Return list of fields that should be encrypted."""
        return self._encrypted_fields

    def _create_stage(self, stage_data: Dict[str, Any]) -> ConditionStage:
        """Create ConditionStage object."""
        stage = ConditionStage()

        if "summary" in stage_data:
            stage.summary = self._create_codeable_concept(stage_data["summary"])

        if "assessment" in stage_data:
            stage.assessment = [
                FHIRReference({"reference": ref}) for ref in stage_data["assessment"]
            ]

        if "type" in stage_data:
            stage.type = self._create_codeable_concept(stage_data["type"])

        return stage

    def _create_evidence(self, evidence_data: Dict[str, Any]) -> ConditionEvidence:
        """Create ConditionEvidence object."""
        evidence = ConditionEvidence()

        if "code" in evidence_data:
            evidence.code = [
                self._create_codeable_concept(code) for code in evidence_data["code"]
            ]

        if "detail" in evidence_data:
            evidence.detail = [
                FHIRReference({"reference": ref}) for ref in evidence_data["detail"]
            ]

        return evidence

    def _add_refugee_context(
        self, condition: Condition, context_data: Dict[str, Any]
    ) -> None:
        """Add refugee-specific context extensions."""
        if not condition.extension:
            condition.extension = []

        # Add conflict-related marker
        if context_data.get("is_conflict_related"):
            conflict_ext = Extension()
            conflict_ext.url = "http://havenhealthpassport.org/fhir/StructureDefinition/conflict-related-condition"
            conflict_ext.valueBoolean = True
            condition.extension.append(conflict_ext)

        # Add endemic disease marker
        if "endemic_region" in context_data:
            endemic_ext = Extension()
            endemic_ext.url = "http://havenhealthpassport.org/fhir/StructureDefinition/endemic-disease-region"
            endemic_ext.valueString = context_data["endemic_region"]
            condition.extension.append(endemic_ext)

        # Add displacement-related marker
        if context_data.get("displacement_related"):
            displacement_ext = Extension()
            displacement_ext.url = "http://havenhealthpassport.org/fhir/StructureDefinition/displacement-related-condition"
            displacement_ext.valueBoolean = True
            condition.extension.append(displacement_ext)

    def _create_age(self, age_data: Union[int, Dict[str, Any]]) -> Age:
        """Create Age object."""
        age = Age()

        if isinstance(age_data, int):
            age.value = age_data
            age.unit = "a"
            age.system = "http://unitsofmeasure.org"
            age.code = "a"
        else:
            if "value" in age_data:
                age.value = age_data["value"]
            if "unit" in age_data:
                age.unit = age_data["unit"]
            if "system" in age_data:
                age.system = age_data["system"]
            if "code" in age_data:
                age.code = age_data["code"]

        return age

    def _create_range(self, range_data: Dict[str, Any]) -> Range:
        """Create Range object."""
        range_obj = Range()

        if "low" in range_data:
            range_obj.low = self._create_quantity(range_data["low"])

        if "high" in range_data:
            range_obj.high = self._create_quantity(range_data["high"])

        return range_obj

    def _create_period(self, period_data: Dict[str, Any]) -> Period:
        """Create Period object."""
        period = Period()

        if "start" in period_data:
            period.start = self._create_fhir_datetime(period_data["start"])

        if "end" in period_data:
            period.end = self._create_fhir_datetime(period_data["end"])

        return period

    def _create_codeable_concept(
        self, data: Union[str, Dict[str, Any]]
    ) -> CodeableConcept:
        """Create CodeableConcept from data."""
        concept = CodeableConcept()

        if isinstance(data, str):
            concept.text = data
        else:
            if "coding" in data:
                concept.coding = []
                for coding_data in data["coding"]:
                    coding = Coding()
                    if "system" in coding_data:
                        coding.system = coding_data["system"]
                    if "code" in coding_data:
                        coding.code = coding_data["code"]
                    if "display" in coding_data:
                        coding.display = coding_data["display"]
                    concept.coding.append(coding)

            if "text" in data:
                concept.text = data["text"]

        return concept

    def _create_annotation(self, note_data: Union[str, Dict[str, Any]]) -> Annotation:
        """Create Annotation object."""
        annotation = Annotation()

        if isinstance(note_data, str):
            annotation.text = note_data
        else:
            if "author_reference" in note_data:
                annotation.authorReference = FHIRReference(
                    {"reference": note_data["author_reference"]}
                )
            elif "author_string" in note_data:
                annotation.authorString = note_data["author_string"]

            if "time" in note_data:
                annotation.time = self._create_fhir_datetime(note_data["time"])

            if "text" in note_data:
                annotation.text = note_data["text"]

        return annotation

    def _create_fhir_datetime(self, datetime_value: Union[str, datetime]) -> FHIRDate:
        """Create FHIRDate from various datetime formats."""
        if isinstance(datetime_value, str):
            return FHIRDate(datetime_value)
        elif isinstance(datetime_value, datetime):
            return FHIRDate(datetime_value.isoformat())
        else:
            raise ValueError(f"Invalid datetime format: {type(datetime_value)}")

    def _create_quantity(self, quantity_data: Dict[str, Any]) -> Any:
        """Create Quantity object."""
        quantity = Quantity()

        if "value" in quantity_data:
            quantity.value = quantity_data["value"]

        if "unit" in quantity_data:
            quantity.unit = quantity_data["unit"]

        if "system" in quantity_data:
            quantity.system = quantity_data["system"]

        if "code" in quantity_data:
            quantity.code = quantity_data["code"]

        return quantity


def create_refugee_condition(
    condition_code: CommonRefugeeConditions,
    patient_id: str,
    clinical_status: ConditionClinicalStatus = ConditionClinicalStatus.ACTIVE,
    verification_status: ConditionVerificationStatus = ConditionVerificationStatus.CONFIRMED,
    onset_date: Optional[datetime] = None,
    severity: Optional[ConditionSeverity] = None,
    is_conflict_related: bool = False,
    endemic_region: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a condition data structure for common refugee conditions.

    Args:
        condition_code: Common refugee condition code
        patient_id: Patient reference
        clinical_status: Clinical status
        verification_status: Verification status
        onset_date: Onset date
        severity: Condition severity
        is_conflict_related: Whether condition is conflict-related
        endemic_region: Endemic region if applicable

    Returns:
        Condition data dictionary
    """
    condition_data: Dict[str, Any] = {
        "clinical_status": clinical_status.value,
        "verification_status": verification_status.value,
        "code": {
            "coding": [
                {
                    "system": "http://hl7.org/fhir/sid/icd-10",
                    "code": condition_code.value,
                    "display": condition_code.name.replace("_", " ").title(),
                }
            ]
        },
        "subject": f"Patient/{patient_id}",
        "recorded_date": datetime.now(),
    }

    # Add onset if provided
    if onset_date:
        condition_data["onset_datetime"] = onset_date

    # Add severity if provided
    if severity:
        condition_data["severity"] = {
            "coding": [
                {
                    "system": "http://snomed.info/sct",
                    "code": severity.value,
                    "display": severity.name.title(),
                }
            ]
        }

    # Add refugee context
    refugee_context: Dict[str, Any] = {}
    if is_conflict_related:
        refugee_context["is_conflict_related"] = True
    if endemic_region:
        refugee_context["endemic_region"] = endemic_region

    if refugee_context:
        # Store as extension or additional data
        condition_data["_refugee_context"] = refugee_context

    # Add appropriate category based on condition
    category_list: List[Dict[str, str]] = []
    if condition_code in [
        CommonRefugeeConditions.TUBERCULOSIS,
        CommonRefugeeConditions.MALARIA,
        CommonRefugeeConditions.HIV,
        CommonRefugeeConditions.HEPATITIS_B,
        CommonRefugeeConditions.HEPATITIS_C,
    ]:
        category_list = [{"text": ConditionCategory.INFECTIOUS_DISEASE.value}]
    elif condition_code in [
        CommonRefugeeConditions.PTSD,
        CommonRefugeeConditions.DEPRESSION,
        CommonRefugeeConditions.ANXIETY,
    ]:
        category_list = [{"text": ConditionCategory.MENTAL_HEALTH.value}]
    elif condition_code in [
        CommonRefugeeConditions.SEVERE_ACUTE_MALNUTRITION,
        CommonRefugeeConditions.MODERATE_ACUTE_MALNUTRITION,
    ]:
        category_list = [{"text": ConditionCategory.NUTRITIONAL.value}]

    if category_list:
        condition_data["category"] = category_list

    return condition_data
