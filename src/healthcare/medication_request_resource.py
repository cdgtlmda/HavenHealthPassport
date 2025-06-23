"""MedicationRequest FHIR Resource Implementation.

This module implements the MedicationRequest FHIR resource for Haven Health Passport,
handling medication prescriptions and orders with special considerations for
refugee healthcare settings including limited formularies and cross-border care.
"""

import logging
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from fhirclient.models.annotation import Annotation
from fhirclient.models.codeableconcept import CodeableConcept
from fhirclient.models.coding import Coding
from fhirclient.models.dosage import Dosage, DosageDoseAndRate
from fhirclient.models.duration import Duration
from fhirclient.models.extension import Extension
from fhirclient.models.fhirdate import FHIRDate
from fhirclient.models.fhirreference import FHIRReference
from fhirclient.models.identifier import Identifier
from fhirclient.models.medicationrequest import (
    MedicationRequest,
    MedicationRequestDispenseRequest,
    MedicationRequestSubstitution,
)
from fhirclient.models.period import Period
from fhirclient.models.quantity import Quantity
from fhirclient.models.range import Range
from fhirclient.models.ratio import Ratio
from fhirclient.models.timing import Timing, TimingRepeat

from src.healthcare.hipaa_access_control import (
    AccessLevel,
    audit_phi_access,
    require_phi_access,
)

from .fhir_base import BaseFHIRResource
from .fhir_profiles import REFUGEE_MEDICATION_REQUEST_PROFILE

logger = logging.getLogger(__name__)

# FHIR resource type for this module
__fhir_resource__ = "MedicationRequest"


class MedicationRequestStatus(Enum):
    """MedicationRequest status codes."""

    ACTIVE = "active"  # Active prescription
    ON_HOLD = "on-hold"  # On hold
    CANCELLED = "cancelled"  # Cancelled
    COMPLETED = "completed"  # Completed
    ENTERED_IN_ERROR = "entered-in-error"  # Entered in error
    STOPPED = "stopped"  # Stopped
    DRAFT = "draft"  # Draft
    UNKNOWN = "unknown"  # Unknown


class MedicationRequestIntent(Enum):
    """MedicationRequest intent codes."""

    PROPOSAL = "proposal"  # Proposal
    PLAN = "plan"  # Plan
    ORDER = "order"  # Order
    ORIGINAL_ORDER = "original-order"  # Original order
    REFLEX_ORDER = "reflex-order"  # Reflex order
    FILLER_ORDER = "filler-order"  # Filler order
    INSTANCE_ORDER = "instance-order"  # Instance order
    OPTION = "option"  # Option


class MedicationRequestPriority(Enum):
    """Request priority codes."""

    ROUTINE = "routine"  # Routine priority
    URGENT = "urgent"  # Urgent priority
    ASAP = "asap"  # As soon as possible
    STAT = "stat"  # Emergency/immediate


class MedicationRequestCategory(Enum):
    """Medication request categories."""

    INPATIENT = "inpatient"  # Inpatient medication
    OUTPATIENT = "outpatient"  # Outpatient prescription
    COMMUNITY = "community"  # Community prescription
    DISCHARGE = "discharge"  # Discharge medication

    # Refugee-specific categories
    EMERGENCY = "emergency"  # Emergency supply
    HUMANITARIAN = "humanitarian"  # Humanitarian aid
    CHRONIC = "chronic"  # Chronic disease management
    PREVENTIVE = "preventive"  # Preventive medication
    DONATION = "donation"  # Donated medication


class RouteOfAdministration(Enum):
    """Common routes of administration."""

    # Oral routes
    ORAL = "26643006"  # Oral route
    SUBLINGUAL = "37839007"  # Sublingual route
    BUCCAL = "54471007"  # Buccal route

    # Parenteral routes
    INTRAVENOUS = "47625008"  # Intravenous route
    INTRAMUSCULAR = "78421000"  # Intramuscular route
    SUBCUTANEOUS = "34206005"  # Subcutaneous route
    INTRADERMAL = "372464004"  # Intradermal route

    # Topical routes
    TOPICAL = "45890006"  # Topical route
    TRANSDERMAL = "45890006"  # Transdermal route

    # Other routes
    INHALATION = "18679011"  # Inhalation route
    NASAL = "46713006"  # Nasal route
    OPHTHALMIC = "54485002"  # Ophthalmic route
    OTIC = "10547007"  # Otic route
    RECTAL = "37161004"  # Rectal route
    VAGINAL = "16857009"  # Vaginal route


class DosageTimingCode(Enum):
    """Common dosage timing codes."""

    QD = "QD"  # Once daily
    BID = "BID"  # Twice daily
    TID = "TID"  # Three times daily
    QID = "QID"  # Four times daily
    Q4H = "Q4H"  # Every 4 hours
    Q6H = "Q6H"  # Every 6 hours
    Q8H = "Q8H"  # Every 8 hours
    Q12H = "Q12H"  # Every 12 hours
    PRN = "PRN"  # As needed
    STAT = "STAT"  # Immediately
    AC = "AC"  # Before meals
    PC = "PC"  # After meals
    HS = "HS"  # At bedtime
    AM = "AM"  # Morning
    PM = "PM"  # Evening


class MedicationRequestResource(BaseFHIRResource):
    """MedicationRequest FHIR resource implementation for Haven Health Passport."""

    def __init__(self) -> None:
        """Initialize MedicationRequest resource handler."""
        super().__init__(MedicationRequest)
        self._encrypted_fields = [
            "identifier[0].value",  # Prescription ID
            "subject.reference",  # Patient reference
            "requester.reference",  # Prescriber reference
        ]

    @require_phi_access(AccessLevel.WRITE)
    @require_phi_access(AccessLevel.WRITE)
    @audit_phi_access("create_medication_request")
    def create_resource(self, data: Dict[str, Any]) -> MedicationRequest:
        """Create a new MedicationRequest resource.

        Args:
            data: Dictionary containing medication request data

        Returns:
            Created MedicationRequest resource
        """
        med_request = MedicationRequest()

        # Set required fields
        med_request.status = data.get("status", MedicationRequestStatus.ACTIVE.value)
        med_request.intent = data.get("intent", MedicationRequestIntent.ORDER.value)

        # Set medication reference or codeable concept
        if "medication_reference" in data:
            med_request.medicationReference = FHIRReference(
                {"reference": data["medication_reference"]}
            )
        elif "medication_code" in data:
            med_request.medicationCodeableConcept = self._create_codeable_concept(
                data["medication_code"]
            )

        # Set subject (patient)
        med_request.subject = FHIRReference({"reference": data["subject"]})

        # Set encounter if provided
        if "encounter" in data:
            med_request.encounter = FHIRReference({"reference": data["encounter"]})

        # Set requester
        if "requester" in data:
            med_request.requester = FHIRReference({"reference": data["requester"]})

        # Set priority
        if "priority" in data:
            med_request.priority = data["priority"]

        # Set category
        if "category" in data:
            med_request.category = [
                self._create_codeable_concept(cat) for cat in data["category"]
            ]

        # Set identifiers
        if "identifier" in data:
            med_request.identifier = self._create_identifiers(data["identifier"])
        # Set authored on date
        if "authored_on" in data:
            med_request.authoredOn = self._create_fhir_datetime(data["authored_on"])

        # Set reason codes and references
        if "reason_code" in data:
            med_request.reasonCode = [
                self._create_codeable_concept(code) for code in data["reason_code"]
            ]

        if "reason_reference" in data:
            med_request.reasonReference = [
                FHIRReference({"reference": ref}) for ref in data["reason_reference"]
            ]

        # Set notes
        if "note" in data:
            med_request.note = [self._create_annotation(note) for note in data["note"]]

        # Set dosage instructions
        if "dosage_instruction" in data:
            med_request.dosageInstruction = self._create_dosage_instructions(
                data["dosage_instruction"]
            )

        # Set dispense request
        if "dispense_request" in data:
            med_request.dispenseRequest = self._create_dispense_request(
                data["dispense_request"]
            )

        # Set substitution
        if "substitution" in data:
            med_request.substitution = self._create_substitution(data["substitution"])

        # Set prior prescription
        if "prior_prescription" in data:
            med_request.priorPrescription = FHIRReference(
                {"reference": data["prior_prescription"]}
            )

        # Add refugee-specific extensions
        if "refugee_context" in data:
            self._add_refugee_context(med_request, data["refugee_context"])

        # Add profile and validate
        self.add_meta_profile(med_request, REFUGEE_MEDICATION_REQUEST_PROFILE)

        # Store and validate
        self._resource = med_request
        self.validate()

        # Add audit entry
        self.add_audit_entry("create", data.get("created_by", "system"))

        return med_request

    def get_encrypted_fields(self) -> List[str]:
        """Return list of fields that should be encrypted."""
        return self._encrypted_fields

    def _create_identifiers(
        self, identifiers: List[Dict[str, Any]]
    ) -> List[Identifier]:
        """Create Identifier objects from data."""
        result = []
        for id_data in identifiers:
            identifier = Identifier()

            if "use" in id_data:
                identifier.use = id_data["use"]

            if "type" in id_data:
                identifier.type = self._create_codeable_concept(id_data["type"])

            if "system" in id_data:
                identifier.system = id_data["system"]

            if "value" in id_data:
                identifier.value = id_data["value"]

            result.append(identifier)
        return result

    def _create_dosage_instructions(
        self, dosage_data: List[Dict[str, Any]]
    ) -> List[Dosage]:
        """Create dosage instruction objects."""
        result = []

        for dosage_info in dosage_data:
            dosage = Dosage()

            # Set sequence
            if "sequence" in dosage_info:
                dosage.sequence = dosage_info["sequence"]

            # Set text instructions
            if "text" in dosage_info:
                dosage.text = dosage_info["text"]

            # Set additional instructions
            if "additional_instruction" in dosage_info:
                dosage.additionalInstruction = [
                    self._create_codeable_concept(inst)
                    for inst in dosage_info["additional_instruction"]
                ]

            # Set patient instructions
            if "patient_instruction" in dosage_info:
                dosage.patientInstruction = dosage_info["patient_instruction"]

            # Set timing
            if "timing" in dosage_info:
                dosage.timing = self._create_timing(dosage_info["timing"])

            # Set as needed
            if "as_needed_boolean" in dosage_info:
                dosage.asNeededBoolean = dosage_info["as_needed_boolean"]
            elif "as_needed_codeable_concept" in dosage_info:
                dosage.asNeededCodeableConcept = self._create_codeable_concept(
                    dosage_info["as_needed_codeable_concept"]
                )

            # Set site
            if "site" in dosage_info:
                dosage.site = self._create_codeable_concept(dosage_info["site"])

            # Set route
            if "route" in dosage_info:
                dosage.route = self._create_codeable_concept(dosage_info["route"])

            # Set method
            if "method" in dosage_info:
                dosage.method = self._create_codeable_concept(dosage_info["method"])

            # Set dose and rate
            if "dose_and_rate" in dosage_info:
                dosage.doseAndRate = self._create_dose_and_rate(
                    dosage_info["dose_and_rate"]
                )

            # Set max dose per period
            if "max_dose_per_period" in dosage_info:
                dosage.maxDosePerPeriod = self._create_ratio(
                    dosage_info["max_dose_per_period"]
                )

            # Set max dose per administration
            if "max_dose_per_administration" in dosage_info:
                dosage.maxDosePerAdministration = self._create_quantity(
                    dosage_info["max_dose_per_administration"]
                )

            # Set max dose per lifetime
            if "max_dose_per_lifetime" in dosage_info:
                dosage.maxDosePerLifetime = self._create_quantity(
                    dosage_info["max_dose_per_lifetime"]
                )

            result.append(dosage)

        return result

    def _create_timing(self, timing_data: Dict[str, Any]) -> Timing:
        """Create Timing object."""
        timing = Timing()

        # Set event times
        if "event" in timing_data:
            timing.event = [
                self._create_fhir_datetime(event) for event in timing_data["event"]
            ]

        # Set repeat
        if "repeat" in timing_data:
            repeat = TimingRepeat()
            repeat_data = timing_data["repeat"]

            if "bounds_duration" in repeat_data:
                repeat.boundsDuration = self._create_duration(
                    repeat_data["bounds_duration"]
                )
            elif "bounds_range" in repeat_data:
                repeat.boundsRange = self._create_range(repeat_data["bounds_range"])
            elif "bounds_period" in repeat_data:
                repeat.boundsPeriod = self._create_period(repeat_data["bounds_period"])

            if "count" in repeat_data:
                repeat.count = repeat_data["count"]

            if "count_max" in repeat_data:
                repeat.countMax = repeat_data["count_max"]

            if "duration" in repeat_data:
                repeat.duration = repeat_data["duration"]

            if "duration_max" in repeat_data:
                repeat.durationMax = repeat_data["duration_max"]

            if "duration_unit" in repeat_data:
                repeat.durationUnit = repeat_data["duration_unit"]

            if "frequency" in repeat_data:
                repeat.frequency = repeat_data["frequency"]

            if "frequency_max" in repeat_data:
                repeat.frequencyMax = repeat_data["frequency_max"]

            if "period" in repeat_data:
                repeat.period = repeat_data["period"]

            if "period_max" in repeat_data:
                repeat.periodMax = repeat_data["period_max"]

            if "period_unit" in repeat_data:
                repeat.periodUnit = repeat_data["period_unit"]

            if "day_of_week" in repeat_data:
                repeat.dayOfWeek = repeat_data["day_of_week"]

            if "time_of_day" in repeat_data:
                repeat.timeOfDay = repeat_data["time_of_day"]

            if "when" in repeat_data:
                repeat.when = repeat_data["when"]

            if "offset" in repeat_data:
                repeat.offset = repeat_data["offset"]

            timing.repeat = repeat

        # Set code
        if "code" in timing_data:
            timing.code = self._create_codeable_concept(timing_data["code"])

        return timing

    def _create_dose_and_rate(
        self, dose_rate_data: List[Dict[str, Any]]
    ) -> List[DosageDoseAndRate]:
        """Create dose and rate objects."""
        result = []

        for dr_data in dose_rate_data:
            dose_rate = DosageDoseAndRate()

            if "type" in dr_data:
                dose_rate.type = self._create_codeable_concept(dr_data["type"])

            # Set dose
            if "dose_range" in dr_data:
                dose_rate.doseRange = self._create_range(dr_data["dose_range"])
            elif "dose_quantity" in dr_data:
                dose_rate.doseQuantity = self._create_quantity(dr_data["dose_quantity"])

            # Set rate
            if "rate_ratio" in dr_data:
                dose_rate.rateRatio = self._create_ratio(dr_data["rate_ratio"])
            elif "rate_range" in dr_data:
                dose_rate.rateRange = self._create_range(dr_data["rate_range"])
            elif "rate_quantity" in dr_data:
                dose_rate.rateQuantity = self._create_quantity(dr_data["rate_quantity"])

            result.append(dose_rate)

        return result

    def _create_dispense_request(
        self, dispense_data: Dict[str, Any]
    ) -> MedicationRequestDispenseRequest:
        """Create dispense request object."""
        dispense = MedicationRequestDispenseRequest()

        # Set initial fill
        if "initial_fill" in dispense_data:
            initial_fill = dispense_data["initial_fill"]
            if "quantity" in initial_fill:
                dispense.initialFill = MedicationRequestDispenseRequest()
                dispense.initialFill.quantity = self._create_quantity(
                    initial_fill["quantity"]
                )
            if "duration" in initial_fill:
                dispense.initialFill.duration = self._create_duration(
                    initial_fill["duration"]
                )

        # Set dispense interval
        if "dispense_interval" in dispense_data:
            dispense.dispenseInterval = self._create_duration(
                dispense_data["dispense_interval"]
            )

        # Set validity period
        if "validity_period" in dispense_data:
            dispense.validityPeriod = self._create_period(
                dispense_data["validity_period"]
            )

        # Set number of repeats allowed
        if "number_of_repeats_allowed" in dispense_data:
            dispense.numberOfRepeatsAllowed = dispense_data["number_of_repeats_allowed"]

        # Set quantity
        if "quantity" in dispense_data:
            dispense.quantity = self._create_quantity(dispense_data["quantity"])

        # Set expected supply duration
        if "expected_supply_duration" in dispense_data:
            dispense.expectedSupplyDuration = self._create_duration(
                dispense_data["expected_supply_duration"]
            )

        # Set performer
        if "performer" in dispense_data:
            dispense.performer = FHIRReference(
                {"reference": dispense_data["performer"]}
            )

        return dispense

    def _create_substitution(
        self, substitution_data: Dict[str, Any]
    ) -> MedicationRequestSubstitution:
        """Create substitution object."""
        substitution = MedicationRequestSubstitution()

        # Set allowed boolean or codeable concept
        if "allowed_boolean" in substitution_data:
            substitution.allowedBoolean = substitution_data["allowed_boolean"]
        elif "allowed_codeable_concept" in substitution_data:
            substitution.allowedCodeableConcept = self._create_codeable_concept(
                substitution_data["allowed_codeable_concept"]
            )

        # Set reason
        if "reason" in substitution_data:
            substitution.reason = self._create_codeable_concept(
                substitution_data["reason"]
            )

        return substitution

    def _add_refugee_context(
        self, med_request: MedicationRequest, context_data: Dict[str, Any]
    ) -> None:
        """Add refugee-specific context extensions."""
        if not med_request.extension:
            med_request.extension = []

        # Add humanitarian aid marker
        if context_data.get("is_humanitarian_aid"):
            aid_ext = Extension()
            aid_ext.url = "http://havenhealthpassport.org/fhir/StructureDefinition/humanitarian-aid"
            aid_ext.valueBoolean = True
            med_request.extension.append(aid_ext)

        # Add cross-border validity
        if "cross_border_validity" in context_data:
            border_ext = Extension()
            border_ext.url = "http://havenhealthpassport.org/fhir/StructureDefinition/cross-border-validity"
            border_ext.valueString = context_data["cross_border_validity"]
            med_request.extension.append(border_ext)

        # Add generic substitution allowed
        if "generic_allowed" in context_data:
            generic_ext = Extension()
            generic_ext.url = "http://havenhealthpassport.org/fhir/StructureDefinition/generic-substitution-allowed"
            generic_ext.valueBoolean = context_data["generic_allowed"]
            med_request.extension.append(generic_ext)

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

    def _create_quantity(self, quantity_data: Dict[str, Any]) -> Quantity:
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

    def _create_duration(self, duration_data: Dict[str, Any]) -> Duration:
        """Create Duration object."""
        duration = Duration()

        if "value" in duration_data:
            duration.value = duration_data["value"]

        if "unit" in duration_data:
            duration.unit = duration_data["unit"]

        if "system" in duration_data:
            duration.system = duration_data["system"]

        if "code" in duration_data:
            duration.code = duration_data["code"]

        return duration

    def _create_range(self, range_data: Dict[str, Any]) -> Range:
        """Create Range object."""
        range_obj = Range()

        if "low" in range_data:
            range_obj.low = self._create_quantity(range_data["low"])

        if "high" in range_data:
            range_obj.high = self._create_quantity(range_data["high"])

        return range_obj

    def _create_ratio(self, ratio_data: Dict[str, Any]) -> Ratio:
        """Create Ratio object."""
        ratio = Ratio()

        if "numerator" in ratio_data:
            ratio.numerator = self._create_quantity(ratio_data["numerator"])

        if "denominator" in ratio_data:
            ratio.denominator = self._create_quantity(ratio_data["denominator"])

        return ratio

    def _create_period(self, period_data: Dict[str, Any]) -> Period:
        """Create Period object."""
        period = Period()

        if "start" in period_data:
            period.start = self._create_fhir_datetime(period_data["start"])

        if "end" in period_data:
            period.end = self._create_fhir_datetime(period_data["end"])

        return period

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


def create_standard_dosage_instruction(
    timing_code: DosageTimingCode,
    dose_quantity: float,
    dose_unit: str,
    route: RouteOfAdministration,
    duration_days: Optional[int] = None,
    instructions: Optional[str] = None,
) -> Dict[str, Any]:
    """Create standard dosage instruction data.

    Args:
        timing_code: Timing code (e.g., BID, TID)
        dose_quantity: Dose amount
        dose_unit: Unit of dose (e.g., "mg", "tablet")
        route: Route of administration
        duration_days: Duration in days (optional)
        instructions: Additional instructions (optional)

    Returns:
        Dosage instruction data dictionary
    """
    dosage: Dict[str, Any] = {
        "text": f"{dose_quantity} {dose_unit} {timing_code.value}",
        "timing": {
            "code": {
                "coding": [
                    {
                        "system": "http://terminology.hl7.org/CodeSystem/v3-GTSAbbreviation",
                        "code": timing_code.value,
                        "display": timing_code.name,
                    }
                ]
            }
        },
        "route": {
            "coding": [
                {
                    "system": "http://snomed.info/sct",
                    "code": route.value,
                    "display": route.name.replace("_", " ").title(),
                }
            ]
        },
        "dose_and_rate": [
            {
                "dose_quantity": {
                    "value": dose_quantity,
                    "unit": dose_unit,
                    "system": "http://unitsofmeasure.org",
                }
            }
        ],
    }

    # Add duration if specified
    if duration_days:
        dosage["timing"]["repeat"] = {
            "bounds_duration": {
                "value": duration_days,
                "unit": "d",
                "system": "http://unitsofmeasure.org",
                "code": "d",
            }
        }

    # Add patient instructions if provided
    if instructions:
        dosage["patient_instruction"] = instructions

    return dosage
