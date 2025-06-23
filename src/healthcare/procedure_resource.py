"""Procedure FHIR Resource Implementation.

This module implements the Procedure FHIR resource for Haven Health Passport,
handling medical procedures, surgeries, and interventions with considerations
for resource-limited settings and emergency field procedures.
"""

import logging
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from fhirclient.models.age import Age
from fhirclient.models.annotation import Annotation
from fhirclient.models.codeableconcept import CodeableConcept
from fhirclient.models.coding import Coding
from fhirclient.models.fhirreference import FHIRReference
from fhirclient.models.identifier import Identifier
from fhirclient.models.period import Period
from fhirclient.models.procedure import (
    Procedure,
    ProcedureFocalDevice,
    ProcedurePerformer,
)
from fhirclient.models.range import Range

from src.healthcare.hipaa_access_control import (
    AccessLevel,
    audit_phi_access,
    require_phi_access,
)

from .fhir_base import BaseFHIRResource
from .fhir_profiles import REFUGEE_PROCEDURE_PROFILE

logger = logging.getLogger(__name__)

# FHIR resource type for this module
__fhir_resource__ = "Procedure"


class ProcedureStatus(Enum):
    """Procedure status codes."""

    PREPARATION = "preparation"  # Preparation for procedure
    IN_PROGRESS = "in-progress"  # Procedure ongoing
    NOT_DONE = "not-done"  # Procedure not performed
    ON_HOLD = "on-hold"  # Procedure paused
    STOPPED = "stopped"  # Procedure terminated
    COMPLETED = "completed"  # Procedure completed
    ENTERED_IN_ERROR = "entered-in-error"  # Entered in error
    UNKNOWN = "unknown"  # Unknown status


class ProcedureCategory(Enum):
    """Procedure category codes."""

    # Clinical categories
    SURGICAL = "387713003"  # Surgical procedure
    DIAGNOSTIC = "103693007"  # Diagnostic procedure
    THERAPEUTIC = "277132007"  # Therapeutic procedure
    COUNSELING = "409063005"  # Counseling
    EDUCATION = "409073007"  # Education

    # Public health
    SCREENING = "20135006"  # Screening procedure
    IMMUNIZATION = "33879002"  # Immunization

    # Emergency/Field procedures
    EMERGENCY = "EMRG001"  # Emergency procedure
    FIELD_SURGERY = "FIELD001"  # Field surgery
    FIRST_AID = "FIRST001"  # First aid
    STABILIZATION = "STAB001"  # Stabilization procedure

    # Refugee-specific
    REGISTRATION = "REG001"  # Registration procedure
    ASSESSMENT = "ASSESS001"  # Health assessment
    REFERRAL = "REFER001"  # Referral procedure


class CommonRefugeeProcedures:
    """Common procedures in refugee healthcare settings."""

    PROCEDURES = {
        # Emergency procedures
        "wound_cleaning": {
            "code": "225113003",
            "display": "Wound cleaning",
            "category": ProcedureCategory.THERAPEUTIC,
            "typical_duration": 30,  # minutes
            "setting": ["emergency", "field", "clinic"],
        },
        "wound_suturing": {
            "code": "18557009",
            "display": "Suturing of wound",
            "category": ProcedureCategory.SURGICAL,
            "typical_duration": 45,
            "setting": ["emergency", "field", "clinic"],
        },
        "fracture_reduction": {
            "code": "428683000",
            "display": "Fracture reduction",
            "category": ProcedureCategory.THERAPEUTIC,
            "typical_duration": 60,
            "setting": ["emergency", "hospital"],
        },
        # Maternal/child procedures
        "delivery_normal": {
            "code": "177184002",
            "display": "Normal delivery",
            "category": ProcedureCategory.SURGICAL,
            "typical_duration": 480,  # 8 hours average
            "setting": ["hospital", "clinic", "field"],
        },
        "cesarean_section": {
            "code": "11466000",
            "display": "Cesarean section",
            "category": ProcedureCategory.SURGICAL,
            "typical_duration": 90,
            "setting": ["hospital"],
        },
        "circumcision_male": {
            "code": "30653003",
            "display": "Male circumcision",
            "category": ProcedureCategory.SURGICAL,
            "typical_duration": 30,
            "setting": ["clinic", "hospital"],
        },
        # Screening procedures
        "malnutrition_screening": {
            "code": "SCREEN001",
            "display": "Malnutrition screening",
            "category": ProcedureCategory.SCREENING,
            "typical_duration": 15,
            "setting": ["clinic", "field", "community"],
        },
        "tb_screening": {
            "code": "171126009",
            "display": "Tuberculosis screening",
            "category": ProcedureCategory.SCREENING,
            "typical_duration": 20,
            "setting": ["clinic", "community"],
        },
        "hiv_counseling": {
            "code": "313077009",
            "display": "HIV counseling",
            "category": ProcedureCategory.COUNSELING,
            "typical_duration": 30,
            "setting": ["clinic", "community"],
        },
        # Immunizations
        "measles_vaccination": {
            "code": "429060002",
            "display": "Measles vaccination",
            "category": ProcedureCategory.IMMUNIZATION,
            "typical_duration": 5,
            "setting": ["clinic", "field", "community"],
        },
        "polio_vaccination": {
            "code": "416144004",
            "display": "Polio vaccination",
            "category": ProcedureCategory.IMMUNIZATION,
            "typical_duration": 5,
            "setting": ["clinic", "field", "community"],
        },
        # Assessment procedures
        "health_assessment": {
            "code": "ASSESS002",
            "display": "Comprehensive health assessment",
            "category": ProcedureCategory.ASSESSMENT,
            "typical_duration": 45,
            "setting": ["clinic", "registration"],
        },
        "mental_health_assessment": {
            "code": "225390008",
            "display": "Mental health assessment",
            "category": ProcedureCategory.ASSESSMENT,
            "typical_duration": 60,
            "setting": ["clinic", "community"],
        },
    }

    @classmethod
    def get_procedure_info(cls, procedure_name: str) -> Optional[Dict]:
        """Get information about a common procedure."""
        return cls.PROCEDURES.get(procedure_name.lower().replace(" ", "_"))


class ProcedureResource(BaseFHIRResource):
    """Procedure FHIR resource implementation."""

    def __init__(self) -> None:
        """Initialize Procedure resource handler."""
        super().__init__(Procedure)
        self._encrypted_fields = []  # Procedures typically not encrypted

    @require_phi_access(AccessLevel.WRITE)
    @require_phi_access(AccessLevel.WRITE)
    @audit_phi_access("create_procedure_resource")
    def create_resource(self, data: Dict[str, Any]) -> Procedure:
        """Create a new Procedure resource.

        Args:
            data: Dictionary containing procedure data with fields:
                - status: Procedure status (required)
                - code: Procedure code (required)
                - subject: Reference to patient (required)
                - performed: When procedure was performed
                - performer: Who performed the procedure
                - location: Where procedure was performed
                - reasonCode: Why procedure was performed
                - outcome: Procedure outcome
                - complication: Any complications

        Returns:
            Created Procedure resource
        """
        procedure = Procedure()

        # Set required fields
        procedure.status = data.get("status", ProcedureStatus.COMPLETED.value)
        procedure.code = self._create_procedure_code(data["code"])
        procedure.subject = FHIRReference({"reference": data["subject"]})

        # Set ID if provided
        if "id" in data:
            procedure.id = data["id"]

        # Set identifiers
        if "identifier" in data:
            procedure.identifier = [
                self._create_identifier(ident) for ident in data["identifier"]
            ]

        # Set based on
        if "basedOn" in data:
            procedure.basedOn = [
                FHIRReference({"reference": ref}) for ref in data["basedOn"]
            ]

        # Set part of
        if "partOf" in data:
            procedure.partOf = [
                FHIRReference({"reference": ref}) for ref in data["partOf"]
            ]

        # Set category
        if "category" in data:
            procedure.category = self._create_codeable_concept(data["category"])

        # Set performed time/period
        if "performed" in data:
            procedure.performedDateTime = self._create_performed(data["performed"])

        # Set performer
        if "performer" in data:
            procedure.performer = [
                self._create_performer(perf) for perf in data["performer"]
            ]

        # Set location
        if "location" in data:
            procedure.location = FHIRReference({"reference": data["location"]})

        # Set reason codes
        if "reasonCode" in data:
            procedure.reasonCode = [
                self._create_codeable_concept(reason) for reason in data["reasonCode"]
            ]

        # Set reason references
        if "reasonReference" in data:
            procedure.reasonReference = [
                FHIRReference({"reference": ref}) for ref in data["reasonReference"]
            ]

        # Set body site
        if "bodySite" in data:
            procedure.bodySite = [
                self._create_codeable_concept(site) for site in data["bodySite"]
            ]

        # Set outcome
        if "outcome" in data:
            procedure.outcome = self._create_codeable_concept(data["outcome"])

        # Set report
        if "report" in data:
            procedure.report = [
                FHIRReference({"reference": ref}) for ref in data["report"]
            ]

        # Set complications
        if "complication" in data:
            procedure.complication = [
                self._create_codeable_concept(comp) for comp in data["complication"]
            ]

        # Set follow up
        if "followUp" in data:
            procedure.followUp = [
                self._create_codeable_concept(fu) for fu in data["followUp"]
            ]

        # Set notes
        if "note" in data:
            procedure.note = [self._create_annotation(note) for note in data["note"]]

        # Set focal device
        if "focalDevice" in data:
            procedure.focalDevice = [
                self._create_focal_device(device) for device in data["focalDevice"]
            ]

        # Set used reference (devices, medications, etc.)
        if "usedReference" in data:
            procedure.usedReference = [
                FHIRReference({"reference": ref}) for ref in data["usedReference"]
            ]

        # Set used code
        if "usedCode" in data:
            procedure.usedCode = [
                self._create_codeable_concept(code) for code in data["usedCode"]
            ]

        # Add refugee-specific extensions
        if "refugee_context" in data:
            self._add_refugee_context(procedure, data["refugee_context"])

        # Add profile and validate
        self.add_meta_profile(procedure, REFUGEE_PROCEDURE_PROFILE)

        # Store and validate
        self._resource = procedure
        self.validate()

        # Add audit entry
        self.add_audit_entry("create", data.get("created_by", "system"))

        return procedure

    def get_encrypted_fields(self) -> List[str]:
        """Return list of fields that should be encrypted."""
        return self._encrypted_fields

    @require_phi_access(AccessLevel.WRITE)
    @audit_phi_access("create_emergency_procedure")
    def create_emergency_procedure(
        self,
        procedure_type: str,
        patient_id: str,
        performed_by: str,
        location: Optional[str] = None,
        **kwargs: Any,
    ) -> Procedure:
        """Create an emergency procedure record.

        Args:
            procedure_type: Type of emergency procedure
            patient_id: Patient reference
            performed_by: Performer reference
            location: Location reference
            **kwargs: Additional procedure fields

        Returns:
            Created emergency procedure
        """
        # Look up procedure info
        proc_info = CommonRefugeeProcedures.get_procedure_info(procedure_type)
        if not proc_info:
            # Create generic emergency procedure
            proc_code = {
                "text": procedure_type,
                "coding": [
                    {
                        "system": "http://havenhealthpassport.org/fhir/CodeSystem/emergency-procedures",
                        "code": f'EMRG-{procedure_type.upper().replace(" ", "-")}',
                        "display": procedure_type,
                    }
                ],
            }
            category = ProcedureCategory.EMERGENCY
        else:
            proc_code = {
                "coding": [
                    {
                        "system": "http://snomed.info/sct",
                        "code": proc_info["code"],
                        "display": proc_info["display"],
                    }
                ]
            }
            category = proc_info["category"]

        data = {
            "status": kwargs.get("status", ProcedureStatus.COMPLETED.value),
            "code": proc_code,
            "category": category.value,
            "subject": f"Patient/{patient_id}",
            "performed": kwargs.get("performed", datetime.now()),
            "performer": [
                {
                    "actor": performed_by,
                    "function": {
                        "coding": [
                            {
                                "system": "http://snomed.info/sct",
                                "code": "224561008",
                                "display": "Emergency treatment provider",
                            }
                        ]
                    },
                }
            ],
        }

        if location:
            data["location"] = location

        # Add emergency context
        data["refugee_context"] = {
            "emergency": True,
            "field_conditions": kwargs.get("field_conditions", "emergency"),
        }

        # Add any additional fields
        data.update(kwargs)

        return self.create_resource(data)

    @require_phi_access(AccessLevel.WRITE)
    @audit_phi_access("create_screening_procedure")
    def create_screening_procedure(
        self,
        screening_type: str,
        patient_id: str,
        result: Optional[str] = None,
        **kwargs: Any,
    ) -> Procedure:
        """Create a screening procedure record.

        Args:
            screening_type: Type of screening
            patient_id: Patient reference
            result: Screening result
            **kwargs: Additional procedure fields

        Returns:
            Created screening procedure
        """
        # Look up screening info
        proc_info = CommonRefugeeProcedures.get_procedure_info(screening_type)
        proc_code: Dict[str, Any]

        if proc_info:
            proc_code = {
                "coding": [
                    {
                        "system": (
                            "http://snomed.info/sct"
                            if not proc_info["code"].startswith("SCREEN")
                            else "http://havenhealthpassport.org/fhir/CodeSystem/screening-procedures"
                        ),
                        "code": proc_info["code"],
                        "display": proc_info["display"],
                    }
                ]
            }
        else:
            proc_code = {
                "coding": [{"display": screening_type}],
            }
            # Add text separately to avoid type conflict
            if screening_type:
                proc_code["text"] = screening_type

        data = {
            "status": ProcedureStatus.COMPLETED.value,
            "code": proc_code,
            "category": ProcedureCategory.SCREENING.value,
            "subject": f"Patient/{patient_id}",
            "performed": kwargs.get("performed", datetime.now()),
        }

        # Add result as outcome if provided
        if result:
            data["outcome"] = {"text": result}

        # Add any additional fields
        data.update(kwargs)

        return self.create_resource(data)

    def _create_procedure_code(self, code_data: Union[str, Dict]) -> CodeableConcept:
        """Create procedure code."""
        if isinstance(code_data, str):
            # Try to look up in common procedures
            proc_info = CommonRefugeeProcedures.get_procedure_info(code_data)
            if proc_info:
                system = "http://snomed.info/sct"
                if proc_info["code"].startswith(("SCREEN", "ASSESS", "EMRG", "FIELD")):
                    system = "http://havenhealthpassport.org/fhir/CodeSystem/refugee-procedures"

                return CodeableConcept(
                    {
                        "coding": [
                            {
                                "system": system,
                                "code": proc_info["code"],
                                "display": proc_info["display"],
                            }
                        ],
                        "text": proc_info["display"],
                    }
                )
            else:
                # Create as text-only
                return CodeableConcept({"text": code_data})
        else:
            return self._create_codeable_concept(code_data)

    def _create_performed(
        self, performed_data: Union[str, datetime, Dict]
    ) -> Union[str, Dict]:
        """Create performed time/period."""
        if isinstance(performed_data, (str, datetime)):
            # Single datetime
            if isinstance(performed_data, datetime):
                return performed_data.isoformat()
            return performed_data
        elif isinstance(performed_data, dict) and (
            "start" in performed_data or "end" in performed_data
        ):
            # Period
            period = Period()
            if "start" in performed_data:
                period.start = self._create_fhir_datetime(performed_data["start"])
            if "end" in performed_data:
                period.end = self._create_fhir_datetime(performed_data["end"])
            return dict(period.as_json())
        else:
            # Age or Range
            if "age" in performed_data:
                age = Age()
                age.value = performed_data["age"]["value"]
                age.unit = performed_data["age"]["unit"]
                age.system = "http://unitsofmeasure.org"
                return {"age": age.as_json()}
            elif "range" in performed_data:
                range_obj = Range()
                if "low" in performed_data["range"]:
                    range_obj.low = self._create_quantity(
                        performed_data["range"]["low"]
                    )
                if "high" in performed_data["range"]:
                    range_obj.high = self._create_quantity(
                        performed_data["range"]["high"]
                    )
                return {"range": range_obj.as_json()}

        # Default return for any other case
        return str(performed_data)

    def _create_performer(self, performer_data: Dict) -> ProcedurePerformer:
        """Create procedure performer."""
        performer = ProcedurePerformer()

        # Actor is required
        performer.actor = FHIRReference({"reference": performer_data["actor"]})

        # Function is optional
        if "function" in performer_data:
            performer.function = self._create_codeable_concept(
                performer_data["function"]
            )

        # On behalf of is optional
        if "onBehalfOf" in performer_data:
            performer.onBehalfOf = FHIRReference(
                {"reference": performer_data["onBehalfOf"]}
            )

        return performer

    def _create_focal_device(self, device_data: Dict) -> ProcedureFocalDevice:
        """Create focal device reference."""
        focal_device = ProcedureFocalDevice()

        # Action is optional
        if "action" in device_data:
            focal_device.action = self._create_codeable_concept(device_data["action"])

        # Manipulated is required
        focal_device.manipulated = FHIRReference(
            {"reference": device_data["manipulated"]}
        )

        return focal_device

    def _create_annotation(self, note_data: Union[str, Dict]) -> Annotation:
        """Create annotation/note."""
        if isinstance(note_data, str):
            annotation = Annotation()
            annotation.text = note_data
            annotation.time = datetime.now().isoformat()
            return annotation
        else:
            annotation = Annotation()
            annotation.text = note_data.get("text")
            if "author" in note_data:
                annotation.authorReference = FHIRReference(
                    {"reference": note_data["author"]}
                )
            if "time" in note_data:
                annotation.time = note_data["time"]
            return annotation

    def _create_identifier(self, identifier_data: Dict) -> Identifier:
        """Create procedure identifier."""
        identifier = Identifier()

        if "system" in identifier_data:
            identifier.system = identifier_data["system"]

        if "value" in identifier_data:
            identifier.value = identifier_data["value"]

        if "use" in identifier_data:
            identifier.use = identifier_data["use"]

        return identifier

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

    def _create_quantity(self, quantity_data: Union[float, Dict]) -> Dict:
        """Create quantity value."""
        if isinstance(quantity_data, (int, float)):
            return {"value": float(quantity_data)}
        else:
            return {
                "value": quantity_data.get("value"),
                "unit": quantity_data.get("unit"),
                "system": quantity_data.get("system", "http://unitsofmeasure.org"),
                "code": quantity_data.get("code"),
            }

    def _create_fhir_datetime(self, datetime_value: Union[str, datetime]) -> str:
        """Create FHIR datetime string."""
        if isinstance(datetime_value, str):
            return datetime_value
        elif isinstance(datetime_value, datetime):
            return datetime_value.isoformat()
        else:
            raise ValueError(f"Invalid datetime format: {type(datetime_value)}")

    def _add_refugee_context(
        self, procedure: Procedure, context_data: Dict[str, Any]
    ) -> None:
        """Add refugee-specific context extensions."""
        if not procedure.extension:
            procedure.extension = []

        # Add field conditions
        if "field_conditions" in context_data:
            ext = {
                "url": "http://havenhealthpassport.org/fhir/extension/field-conditions",
                "valueString": context_data["field_conditions"],
            }
            procedure.extension.append(ext)

        # Add resource limitations
        if "resource_limitations" in context_data:
            ext = {
                "url": "http://havenhealthpassport.org/fhir/extension/resource-limitations",
                "valueString": context_data["resource_limitations"],
            }
            procedure.extension.append(ext)

        # Add emergency flag
        if context_data.get("emergency"):
            ext = {
                "url": "http://havenhealthpassport.org/fhir/extension/emergency-procedure",
                "valueBoolean": True,
            }
            procedure.extension.append(ext)

        # Add training level of performer
        if "performer_training" in context_data:
            ext = {
                "url": "http://havenhealthpassport.org/fhir/extension/performer-training",
                "valueString": context_data["performer_training"],
            }
            procedure.extension.append(ext)
