"""Observation FHIR Resource Implementation.

This module implements the Observation FHIR resource for Haven Health Passport,
handling vital signs, lab results, social observations, and other clinical
measurements with refugee-specific extensions.
"""

import logging
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from fhirclient.models.annotation import Annotation
from fhirclient.models.codeableconcept import CodeableConcept
from fhirclient.models.coding import Coding
from fhirclient.models.fhirdate import FHIRDate
from fhirclient.models.fhirreference import FHIRReference
from fhirclient.models.observation import Observation
from fhirclient.models.period import Period
from fhirclient.models.quantity import Quantity
from fhirclient.models.range import Range
from fhirclient.models.ratio import Ratio

from src.healthcare.hipaa_access_control import (
    AccessLevel,
    audit_phi_access,
    require_phi_access,
)

from .fhir_base import BaseFHIRResource
from .fhir_profiles import REFUGEE_OBSERVATION_PROFILE

logger = logging.getLogger(__name__)

# FHIR resource type for this module
__fhir_resource__ = "Observation"


class ObservationStatus(Enum):
    """Observation status codes."""

    REGISTERED = "registered"  # Observation to be done
    PRELIMINARY = "preliminary"  # Initial result
    FINAL = "final"  # Final result
    AMENDED = "amended"  # Amended result
    CORRECTED = "corrected"  # Corrected result
    CANCELLED = "cancelled"  # Cancelled/aborted
    ENTERED_IN_ERROR = "entered-in-error"  # Entered in error
    UNKNOWN = "unknown"  # Unknown status


class ObservationCategory(Enum):
    """Observation category codes."""

    # Standard categories
    VITAL_SIGNS = "vital-signs"
    LABORATORY = "laboratory"
    IMAGING = "imaging"
    PROCEDURE = "procedure"
    SURVEY = "survey"
    EXAM = "exam"
    THERAPY = "therapy"
    ACTIVITY = "activity"

    # Extended for refugee care
    NUTRITION = "nutrition"
    MENTAL_HEALTH = "mental-health"
    SOCIAL = "social"
    ENVIRONMENTAL = "environmental"
    SCREENING = "screening"
    PUBLIC_HEALTH = "public-health"


class VitalSignCode(Enum):
    """Common vital sign LOINC codes."""

    # Basic vital signs
    BODY_TEMPERATURE = "8310-5"  # Body temperature
    HEART_RATE = "8867-4"  # Heart rate
    RESPIRATORY_RATE = "9279-1"  # Respiratory rate
    BLOOD_PRESSURE = "85354-9"  # Blood pressure panel
    SYSTOLIC_BP = "8480-6"  # Systolic blood pressure
    DIASTOLIC_BP = "8462-4"  # Diastolic blood pressure
    OXYGEN_SATURATION = "59408-5"  # Oxygen saturation

    # Anthropometric measurements
    BODY_HEIGHT = "8302-2"  # Body height
    BODY_WEIGHT = "29463-7"  # Body weight
    BMI = "39156-5"  # Body mass index
    HEAD_CIRCUMFERENCE = "9843-4"  # Head circumference
    MUAC = "56072-2"  # Mid-upper arm circumference

    # Pediatric specific
    WEIGHT_FOR_HEIGHT = "77606-2"  # Weight-for-height percentile
    HEIGHT_FOR_AGE = "77605-4"  # Height-for-age percentile
    WEIGHT_FOR_AGE = "77604-7"  # Weight-for-age percentile


class LabResultCode(Enum):
    """Common laboratory result LOINC codes."""

    # Hematology
    HEMOGLOBIN = "718-7"  # Hemoglobin
    HEMATOCRIT = "4544-3"  # Hematocrit
    WBC_COUNT = "6690-2"  # White blood cell count
    PLATELET_COUNT = "777-3"  # Platelet count

    # Chemistry
    GLUCOSE = "2345-7"  # Glucose
    CREATININE = "2160-0"  # Creatinine
    UREA_NITROGEN = "3094-0"  # Blood urea nitrogen

    # Infectious disease
    HIV_TEST = "75622-1"  # HIV test
    TB_TEST = "48576-6"  # TB test result
    MALARIA_TEST = "32700-7"  # Malaria test
    COVID_TEST = "94500-6"  # COVID-19 test

    # Nutritional
    VITAMIN_D = "1989-3"  # Vitamin D
    IRON = "2498-4"  # Iron
    FOLATE = "2284-8"  # Folate


class SocialObservationCode(Enum):
    """Social determinant observation codes."""

    # Housing
    HOUSING_STATUS = "71802-3"  # Housing status
    HOMELESS_STATUS = "69911-0"  # Homeless status

    # Food security
    FOOD_INSECURITY = "88124-3"  # Food insecurity

    # Education
    EDUCATION_LEVEL = "82589-3"  # Highest education level

    # Employment
    EMPLOYMENT_STATUS = "67875-5"  # Employment status

    # Social support
    SOCIAL_SUPPORT = "52490-8"  # Social support

    # Refugee specific
    REFUGEE_STATUS = "REFUGEE-001"  # Refugee status
    DISPLACEMENT_DURATION = "REFUGEE-002"  # Time since displacement
    CAMP_CONDITIONS = "REFUGEE-003"  # Living conditions in camp


class ObservationResource(BaseFHIRResource):
    """Observation FHIR resource implementation."""

    def __init__(self) -> None:
        """Initialize Observation resource handler."""
        super().__init__(Observation)
        self._encrypted_fields = []  # Observations typically not encrypted

    @require_phi_access(AccessLevel.WRITE)
    @audit_phi_access("create_observation_resource")
    def create_resource(self, data: Dict[str, Any]) -> Observation:
        """Create a new Observation resource.

        Args:
            data: Dictionary containing observation data with fields:
                - status: Observation status
                - category: Observation category
                - code: What was observed (required)
                - subject: Reference to patient (required)
                - effective: When observation was made
                - value: The observation value
                - interpretation: Clinical interpretation
                - reference_range: Reference ranges

        Returns:
            Created Observation resource
        """
        observation = Observation()

        # Required fields
        observation.status = data.get("status", ObservationStatus.FINAL.value)
        observation.code = self._create_codeable_concept(data["code"])
        observation.subject = FHIRReference({"reference": data["subject"]})

        # Set ID if provided
        if "id" in data:
            observation.id = data["id"]

        # Set category
        if "category" in data:
            observation.category = [
                self._create_category(cat) for cat in data["category"]
            ]

        # Set effective time
        if "effective" in data:
            observation.effectiveDateTime = self._create_fhir_datetime(
                data["effective"]
            )

        # Set performer
        if "performer" in data:
            observation.performer = [
                FHIRReference({"reference": ref}) for ref in data["performer"]
            ]

        # Set value based on type
        if "value" in data:
            self._set_observation_value(observation, data["value"])

        # Set interpretation
        if "interpretation" in data:
            observation.interpretation = [
                self._create_codeable_concept(interp)
                for interp in data["interpretation"]
            ]

        # Set reference range
        if "reference_range" in data:
            observation.referenceRange = [
                self._create_reference_range(rr) for rr in data["reference_range"]
            ]

        # Set notes
        if "note" in data:
            observation.note = [self._create_annotation(note) for note in data["note"]]

        # Set body site
        if "body_site" in data:
            observation.bodySite = self._create_codeable_concept(data["body_site"])

        # Set method
        if "method" in data:
            observation.method = self._create_codeable_concept(data["method"])

        # Set specimen
        if "specimen" in data:
            observation.specimen = FHIRReference({"reference": data["specimen"]})

        # Set device
        if "device" in data:
            observation.device = FHIRReference({"reference": data["device"]})

        # Add refugee-specific extensions
        if "refugee_context" in data:
            self._add_refugee_context(observation, data["refugee_context"])

        # Add profile and validate
        self.add_meta_profile(observation, REFUGEE_OBSERVATION_PROFILE)

        # Store and validate
        self._resource = observation
        self.validate()

        # Add audit entry
        self.add_audit_entry("create", data.get("created_by", "system"))

        return observation

    def get_encrypted_fields(self) -> List[str]:
        """Return list of fields that should be encrypted."""
        return self._encrypted_fields

    @require_phi_access(AccessLevel.WRITE)
    @audit_phi_access("create_vital_sign_observation")
    def create_vital_sign(
        self,
        vital_type: VitalSignCode,
        value: Union[float, Dict],
        patient_id: str,
        performed_by: Optional[str] = None,
        **kwargs: Any,
    ) -> Observation:
        """Create a vital sign observation.

        Args:
            vital_type: Type of vital sign
            value: Vital sign value (number or complex)
            patient_id: Patient reference
            performed_by: Performer reference
            **kwargs: Additional observation fields

        Returns:
            Created vital sign observation
        """
        data = {
            "status": ObservationStatus.FINAL.value,
            "category": [ObservationCategory.VITAL_SIGNS.value],
            "code": {
                "coding": [
                    {
                        "system": "http://loinc.org",
                        "code": vital_type.value,
                        "display": vital_type.name.replace("_", " ").title(),
                    }
                ]
            },
            "subject": f"Patient/{patient_id}",
            "effective": kwargs.get("effective", datetime.now()),
            "value": value,
        }

        if performed_by:
            data["performer"] = [performed_by]

        # Add any additional fields
        data.update(kwargs)

        return self.create_resource(data)

    @require_phi_access(AccessLevel.WRITE)
    @audit_phi_access("create_lab_result_observation")
    def create_lab_result(
        self,
        test_code: LabResultCode,
        value: Union[float, str, Dict],
        patient_id: str,
        specimen_id: Optional[str] = None,
        **kwargs: Any,
    ) -> Observation:
        """Create a laboratory result observation.

        Args:
            test_code: Type of lab test
            value: Test result value
            patient_id: Patient reference
            specimen_id: Specimen reference
            **kwargs: Additional observation fields

        Returns:
            Created lab result observation
        """
        data = {
            "status": kwargs.get("status", ObservationStatus.FINAL.value),
            "category": [ObservationCategory.LABORATORY.value],
            "code": {
                "coding": [
                    {
                        "system": "http://loinc.org",
                        "code": test_code.value,
                        "display": test_code.name.replace("_", " ").title(),
                    }
                ]
            },
            "subject": f"Patient/{patient_id}",
            "effective": kwargs.get("effective", datetime.now()),
            "value": value,
        }

        if specimen_id:
            data["specimen"] = f"Specimen/{specimen_id}"

        # Add any additional fields
        data.update(kwargs)

        return self.create_resource(data)

    @require_phi_access(AccessLevel.WRITE)
    @audit_phi_access("create_social_observation")
    def create_social_observation(
        self,
        observation_type: SocialObservationCode,
        value: Union[str, Dict],
        patient_id: str,
        **kwargs: Any,
    ) -> Observation:
        """Create a social determinant observation.

        Args:
            observation_type: Type of social observation
            value: Observation value
            patient_id: Patient reference
            **kwargs: Additional observation fields

        Returns:
            Created social observation
        """
        # Determine system based on code
        if observation_type.value.startswith("REFUGEE-"):
            system = (
                "http://havenhealthpassport.org/fhir/CodeSystem/refugee-observations"
            )
        else:
            system = "http://loinc.org"

        data = {
            "status": ObservationStatus.FINAL.value,
            "category": [ObservationCategory.SOCIAL.value],
            "code": {
                "coding": [
                    {
                        "system": system,
                        "code": observation_type.value,
                        "display": observation_type.name.replace("_", " ").title(),
                    }
                ]
            },
            "subject": f"Patient/{patient_id}",
            "effective": kwargs.get("effective", datetime.now()),
            "value": value,
        }

        # Add any additional fields
        data.update(kwargs)

        return self.create_resource(data)

    def _set_observation_value(
        self, observation: Observation, value_data: Union[float, str, Dict]
    ) -> None:
        """Set observation value based on data type."""
        if isinstance(value_data, (int, float)):
            # Simple numeric value
            observation.valueQuantity = Quantity()
            observation.valueQuantity.value = float(value_data)

            # Try to infer unit from code
            if observation.code and observation.code.coding:
                code = observation.code.coding[0].code
                observation.valueQuantity.unit = self._infer_unit(code)

        elif isinstance(value_data, str):
            # String value
            observation.valueString = value_data

        elif isinstance(value_data, dict):
            # Complex value
            if "quantity" in value_data:
                observation.valueQuantity = self._create_quantity(
                    value_data["quantity"]
                )
            elif "codeable_concept" in value_data:
                observation.valueCodeableConcept = self._create_codeable_concept(
                    value_data["codeable_concept"]
                )
            elif "boolean" in value_data:
                observation.valueBoolean = value_data["boolean"]
            elif "range" in value_data:
                observation.valueRange = self._create_range(value_data["range"])
            elif "ratio" in value_data:
                observation.valueRatio = self._create_ratio(value_data["ratio"])
            elif "period" in value_data:
                observation.valuePeriod = self._create_period(value_data["period"])
            elif "components" in value_data:
                # Multi-component observation (e.g., blood pressure)
                observation.component = [
                    self._create_component(comp) for comp in value_data["components"]
                ]

    def _create_category(self, category: Union[str, Dict]) -> CodeableConcept:
        """Create observation category."""
        if isinstance(category, str):
            return CodeableConcept(
                {
                    "coding": [
                        {
                            "system": "http://terminology.hl7.org/CodeSystem/observation-category",
                            "code": category,
                        }
                    ]
                }
            )
        else:
            return self._create_codeable_concept(category)

    def _create_reference_range(self, range_data: Dict) -> Dict:
        """Create reference range structure."""
        ref_range = {}

        if "low" in range_data:
            ref_range["low"] = self._create_quantity(range_data["low"])

        if "high" in range_data:
            ref_range["high"] = self._create_quantity(range_data["high"])

        if "type" in range_data:
            ref_range["type"] = self._create_codeable_concept(range_data["type"])

        if "applies_to" in range_data:
            ref_range["appliesTo"] = [
                self._create_codeable_concept(code) for code in range_data["applies_to"]
            ]

        if "age" in range_data:
            ref_range["age"] = self._create_range(range_data["age"])

        if "text" in range_data:
            ref_range["text"] = range_data["text"]

        return ref_range

    def _create_component(self, component_data: Dict) -> Dict:
        """Create observation component."""
        component = {"code": self._create_codeable_concept(component_data["code"])}

        # Set component value
        if "value" in component_data:
            self._set_observation_value(component, component_data["value"])

        # Set interpretation
        if "interpretation" in component_data:
            component["interpretation"] = [
                self._create_codeable_concept(interp)
                for interp in component_data["interpretation"]
            ]

        # Set reference range
        if "reference_range" in component_data:
            component["referenceRange"] = [
                self._create_reference_range(rr)
                for rr in component_data["reference_range"]
            ]

        return component

    def _create_annotation(self, note_data: Union[str, Dict]) -> Annotation:
        """Create annotation/note."""
        if isinstance(note_data, str):
            annotation = Annotation()
            annotation.text = note_data
            annotation.time = FHIRDate(datetime.now().isoformat())
            return annotation
        else:
            annotation = Annotation()
            annotation.text = note_data.get("text")
            if "author" in note_data:
                annotation.authorReference = FHIRReference(
                    {"reference": note_data["author"]}
                )
            if "time" in note_data:
                annotation.time = FHIRDate(note_data["time"])
            return annotation

    def _create_quantity(self, quantity_data: Union[float, Dict]) -> Quantity:
        """Create quantity value."""
        quantity = Quantity()

        if isinstance(quantity_data, (int, float)):
            quantity.value = float(quantity_data)
        else:
            quantity.value = quantity_data.get("value")
            quantity.unit = quantity_data.get("unit")
            quantity.system = quantity_data.get("system", "http://unitsofmeasure.org")
            quantity.code = quantity_data.get("code")

        return quantity

    def _create_range(self, range_data: Dict) -> Range:
        """Create range value."""
        range_obj = Range()

        if "low" in range_data:
            range_obj.low = self._create_quantity(range_data["low"])

        if "high" in range_data:
            range_obj.high = self._create_quantity(range_data["high"])

        return range_obj

    def _create_ratio(self, ratio_data: Dict) -> Ratio:
        """Create ratio value."""
        ratio = Ratio()

        if "numerator" in ratio_data:
            ratio.numerator = self._create_quantity(ratio_data["numerator"])

        if "denominator" in ratio_data:
            ratio.denominator = self._create_quantity(ratio_data["denominator"])

        return ratio

    def _create_period(self, period_data: Dict) -> Period:
        """Create period value."""
        period = Period()

        if "start" in period_data:
            period.start = FHIRDate(period_data["start"])

        if "end" in period_data:
            period.end = FHIRDate(period_data["end"])

        return period

    def _create_codeable_concept(self, data: Union[str, Dict]) -> CodeableConcept:
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

    def _create_fhir_datetime(self, datetime_value: Union[str, datetime]) -> FHIRDate:
        """Create FHIRDate from various datetime formats."""
        if isinstance(datetime_value, str):
            return FHIRDate(datetime_value)
        elif isinstance(datetime_value, datetime):
            return FHIRDate(datetime_value.isoformat())
        else:
            raise ValueError(f"Invalid datetime format: {type(datetime_value)}")

    def _add_refugee_context(
        self, observation: Observation, context_data: Dict[str, Any]
    ) -> None:
        """Add refugee-specific context extensions."""
        if not observation.extension:
            observation.extension = []

        # Add camp conditions
        if "camp_conditions" in context_data:
            ext = {
                "url": "http://havenhealthpassport.org/fhir/extension/camp-conditions",
                "valueCodeableConcept": self._create_codeable_concept(
                    context_data["camp_conditions"]
                ),
            }
            observation.extension.append(ext)

        # Add resource limitations
        if "resource_limitations" in context_data:
            ext = {
                "url": "http://havenhealthpassport.org/fhir/extension/resource-limitations",
                "valueString": context_data["resource_limitations"],
            }
            observation.extension.append(ext)

        # Add measurement conditions
        if "measurement_conditions" in context_data:
            ext = {
                "url": "http://havenhealthpassport.org/fhir/extension/measurement-conditions",
                "valueString": context_data["measurement_conditions"],
            }
            observation.extension.append(ext)

    def _infer_unit(self, loinc_code: str) -> str:
        """Infer unit from LOINC code."""
        unit_map = {
            # Vital signs
            VitalSignCode.BODY_TEMPERATURE.value: "Cel",
            VitalSignCode.HEART_RATE.value: "/min",
            VitalSignCode.RESPIRATORY_RATE.value: "/min",
            VitalSignCode.SYSTOLIC_BP.value: "mm[Hg]",
            VitalSignCode.DIASTOLIC_BP.value: "mm[Hg]",
            VitalSignCode.OXYGEN_SATURATION.value: "%",
            VitalSignCode.BODY_HEIGHT.value: "cm",
            VitalSignCode.BODY_WEIGHT.value: "kg",
            VitalSignCode.BMI.value: "kg/m2",
            VitalSignCode.HEAD_CIRCUMFERENCE.value: "cm",
            VitalSignCode.MUAC.value: "cm",
            # Lab results
            LabResultCode.HEMOGLOBIN.value: "g/dL",
            LabResultCode.HEMATOCRIT.value: "%",
            LabResultCode.WBC_COUNT.value: "10*3/uL",
            LabResultCode.PLATELET_COUNT.value: "10*3/uL",
            LabResultCode.GLUCOSE.value: "mg/dL",
            LabResultCode.CREATININE.value: "mg/dL",
            LabResultCode.UREA_NITROGEN.value: "mg/dL",
        }

        return unit_map.get(loinc_code, "")
