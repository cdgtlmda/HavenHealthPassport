"""HL7 ADT Message Implementation.

This module implements HL7 ADT (Admit, Discharge, Transfer) messages
for patient administration in refugee healthcare settings.
Handles FHIR Encounter Resource validation and conversion.
All PHI data is encrypted and access is controlled through role-based permissions.
"""

import logging
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from src.healthcare.fhir_validator import FHIRValidator
from src.healthcare.hipaa_access_control import (
    AccessLevel,
    audit_phi_access,
    require_phi_access,
)

from .hl7_message import HL7Message, HL7MessageBuilder, HL7Segment
from .hl7_message_types import HL7EncodingCharacters, HL7Field

logger = logging.getLogger(__name__)

# FHIR resource type for this module
__fhir_resource__ = "Encounter"


class ADTMessageHandler:
    """Handler for ADT message types."""

    def __init__(self, encoding: Optional[HL7EncodingCharacters] = None):
        """Initialize ADT message handler.

        Args:
            encoding: HL7 encoding characters
        """
        self.encoding = encoding or HL7EncodingCharacters()
        self.validator = FHIRValidator()

    def validate_admission(self, admission_data: Dict[str, Any]) -> bool:
        """Validate admission data.

        Args:
            admission_data: Admission data to validate

        Returns:
            True if valid
        """
        try:
            # Validate required fields
            if not admission_data.get("facility"):
                return False
            if not admission_data.get("admission_date"):
                return False
            return True
        except (KeyError, TypeError, ValueError) as e:
            logger.warning("Validation error in admission data: %s", str(e))
            return False

    @require_phi_access(AccessLevel.WRITE)
    @require_phi_access(AccessLevel.WRITE)
    @audit_phi_access("create_adt_admission_message")
    def create_a01_admission(
        self,
        patient_id: str,
        patient_name: Dict[str, str],
        admission_data: Dict[str, Any],
    ) -> HL7Message:
        """Create ADT^A01 admission message.

        Args:
            patient_id: Patient identifier
            patient_name: Patient name components
            admission_data: Admission details

        Returns:
            HL7Message for admission
        """
        builder = HL7MessageBuilder(self.encoding)

        # Add MSH segment
        builder.add_msh(
            sending_application="HavenHealthPassport",
            sending_facility=admission_data.get("facility", "RefugeeCamp"),
            receiving_application=admission_data.get("receiving_app", "HIS"),
            receiving_facility=admission_data.get("receiving_facility", "Hospital"),
            message_type="ADT^A01",
            message_control_id=self._generate_control_id(),
            processing_id="P",
            version_id="2.5",
        )

        # Add EVN segment (event type)
        evn = HL7Segment(f"EVN{self.encoding.field_separator}", self.encoding)
        evn.set_field(1, "A01")  # Event type code
        evn.set_field(2, datetime.now().strftime("%Y%m%d%H%M%S"))  # Event occurred
        evn.set_field(6, datetime.now().strftime("%Y%m%d%H%M%S"))  # Event entered
        builder.message.add_segment(evn)

        # Add PID segment
        builder.add_pid(
            patient_id=patient_id,
            patient_name=patient_name,
            birth_date=admission_data.get("birth_date"),
            gender=admission_data.get("gender"),
            address=admission_data.get("address"),
            phone=admission_data.get("phone"),
        )

        # Add refugee-specific PID fields
        pid = builder.message.get_segment("PID")
        if pid and admission_data.get("refugee_id"):
            # PID-3 repetition for refugee ID
            pid_field = pid.get_field(3)
            if pid_field:
                pid_field.set_value(admission_data["refugee_id"], 1, 0, 0)
                pid_field.set_value("UNHCR", 1, 4, 0)

        # Add NK1 (next of kin) if available
        if admission_data.get("next_of_kin"):
            self._add_nk1_segment(builder, admission_data["next_of_kin"])

        # Add PV1 segment
        builder.add_pv1(
            patient_class=admission_data.get("patient_class", "I"),
            location=admission_data.get("location"),
            admission_type=admission_data.get("admission_type", "E"),
            attending_doctor=admission_data.get("attending_doctor"),
        )

        # Add DG1 (diagnosis) if available
        if admission_data.get("diagnosis"):
            self._add_dg1_segment(builder, admission_data["diagnosis"])

        # Add AL1 (allergy) if available
        if admission_data.get("allergies"):
            for allergy in admission_data["allergies"]:
                self._add_al1_segment(builder, allergy)

        return builder.build()

    @require_phi_access(AccessLevel.WRITE)
    @audit_phi_access("create_adt_discharge_message")
    def create_a03_discharge(
        self, patient_id: str, discharge_data: Dict[str, Any]
    ) -> HL7Message:
        """Create ADT^A03 discharge message.

        Args:
            patient_id: Patient identifier
            discharge_data: Discharge details

        Returns:
            HL7Message for discharge
        """
        builder = HL7MessageBuilder(self.encoding)

        # Add MSH segment
        builder.add_msh(
            sending_application="HavenHealthPassport",
            sending_facility=discharge_data.get("facility", "RefugeeCamp"),
            receiving_application=discharge_data.get("receiving_app", "HIS"),
            receiving_facility=discharge_data.get("receiving_facility", "Hospital"),
            message_type="ADT^A03",
            message_control_id=self._generate_control_id(),
            processing_id="P",
            version_id="2.5",
        )

        # Add EVN segment
        evn = HL7Segment(f"EVN{self.encoding.field_separator}", self.encoding)
        evn.set_field(1, "A03")
        evn.set_field(2, datetime.now().strftime("%Y%m%d%H%M%S"))
        builder.message.add_segment(evn)

        # Add PID segment (minimal for discharge)
        pid = HL7Segment(f"PID{self.encoding.field_separator}", self.encoding)
        pid.set_field(1, "1")
        pid.set_field(3, patient_id)
        builder.message.add_segment(pid)

        # Add PV1 segment with discharge info
        pv1 = HL7Segment(f"PV1{self.encoding.field_separator}", self.encoding)
        pv1.set_field(1, "1")
        pv1.set_field(2, discharge_data.get("patient_class", "I"))
        location = discharge_data.get("location")
        if location:
            pv1.set_field(3, location)
        pv1.set_field(
            36, discharge_data.get("discharge_disposition", "01")
        )  # Discharge disposition
        discharged_to = discharge_data.get("discharged_to_location")
        if discharged_to:
            pv1.set_field(37, discharged_to)  # Discharged to location
        pv1.set_field(
            45,
            discharge_data.get(
                "discharge_date", datetime.now().strftime("%Y%m%d%H%M%S")
            ),
        )
        builder.message.add_segment(pv1)

        return builder.build()

    @require_phi_access(AccessLevel.WRITE)
    @audit_phi_access("create_adt_update_message")
    def create_a08_update(
        self, patient_id: str, updated_data: Dict[str, Any]
    ) -> HL7Message:
        """Create ADT^A08 patient information update message.

        Args:
            patient_id: Patient identifier
            updated_data: Updated patient information

        Returns:
            HL7Message for update
        """
        builder = HL7MessageBuilder(self.encoding)

        # Add MSH segment
        builder.add_msh(
            sending_application="HavenHealthPassport",
            sending_facility=updated_data.get("facility", "RefugeeCamp"),
            receiving_application=updated_data.get("receiving_app", "HIS"),
            receiving_facility=updated_data.get("receiving_facility", "Hospital"),
            message_type="ADT^A08",
            message_control_id=self._generate_control_id(),
            processing_id="P",
            version_id="2.5",
        )

        # Add EVN segment
        evn = HL7Segment(f"EVN{self.encoding.field_separator}", self.encoding)
        evn.set_field(1, "A08")
        evn.set_field(2, datetime.now().strftime("%Y%m%d%H%M%S"))
        builder.message.add_segment(evn)

        # Add PID with updated information
        builder.add_pid(
            patient_id=patient_id,
            patient_name=updated_data.get("name", {}),
            birth_date=updated_data.get("birth_date"),
            gender=updated_data.get("gender"),
            address=updated_data.get("address"),
            phone=updated_data.get("phone"),
        )

        # Add PV1 if patient is currently admitted
        if updated_data.get("current_location"):
            builder.add_pv1(
                patient_class=updated_data.get("patient_class", "I"),
                location=updated_data.get("current_location"),
            )

        return builder.build()

    def _add_nk1_segment(
        self, builder: HL7MessageBuilder, nk_data: Dict[str, str]
    ) -> None:
        """Add NK1 (next of kin) segment.

        Args:
            builder: Message builder
            nk_data: Next of kin data
        """
        nk1 = HL7Segment(f"NK1{self.encoding.field_separator}", self.encoding)

        # NK1-1: Set ID
        nk1.set_field(1, "1")

        # NK1-2: Name
        name_field = nk1.get_field(2) or HL7Field("", self.encoding)
        name_field.set_value(nk_data.get("family", ""), 0, 0, 0)
        name_field.set_value(nk_data.get("given", ""), 0, 1, 0)
        nk1.fields[1] = name_field

        # NK1-3: Relationship
        nk1.set_field(3, nk_data.get("relationship", ""))

        # NK1-5: Phone number
        if nk_data.get("phone"):
            nk1.set_field(5, nk_data["phone"])

        builder.message.add_segment(nk1)

    def _add_dg1_segment(
        self, builder: HL7MessageBuilder, diagnosis_data: Dict[str, str]
    ) -> None:
        """Add DG1 (diagnosis) segment.

        Args:
            builder: Message builder
            diagnosis_data: Diagnosis data
        """
        dg1 = HL7Segment(f"DG1{self.encoding.field_separator}", self.encoding)

        # DG1-1: Set ID
        dg1.set_field(1, "1")

        # DG1-2: Diagnosis coding method (ICD10)
        dg1.set_field(2, "I10")

        # DG1-3: Diagnosis code
        diag_field = dg1.get_field(3) or HL7Field("", self.encoding)
        diag_field.set_value(diagnosis_data.get("code", ""), 0, 0, 0)
        diag_field.set_value(diagnosis_data.get("description", ""), 0, 1, 0)
        diag_field.set_value("ICD10", 0, 2, 0)
        dg1.fields[2] = diag_field

        # DG1-5: Diagnosis date/time
        dg1.set_field(5, diagnosis_data.get("date", datetime.now().strftime("%Y%m%d")))

        # DG1-6: Diagnosis type (A=Admitting, W=Working, F=Final)
        dg1.set_field(6, diagnosis_data.get("type", "W"))

        builder.message.add_segment(dg1)

    def _add_al1_segment(
        self, builder: HL7MessageBuilder, allergy_data: Dict[str, str]
    ) -> None:
        """Add AL1 (allergy) segment.

        Args:
            builder: Message builder
            allergy_data: Allergy data
        """
        al1 = HL7Segment(f"AL1{self.encoding.field_separator}", self.encoding)

        # AL1-1: Set ID
        al1.set_field(1, str(len(builder.message.get_all_segments("AL1")) + 1))

        # AL1-2: Allergen type (DA=Drug allergy, FA=Food allergy, EA=Environmental)
        al1.set_field(2, allergy_data.get("type", "DA"))

        # AL1-3: Allergen code/description
        allergen_field = al1.get_field(3) or HL7Field("", self.encoding)
        allergen_field.set_value(allergy_data.get("code", ""), 0, 0, 0)
        allergen_field.set_value(allergy_data.get("description", ""), 0, 1, 0)
        al1.fields[2] = allergen_field

        # AL1-4: Allergy severity (SV=Severe, MO=Moderate, MI=Mild)
        al1.set_field(4, allergy_data.get("severity", "MO"))

        # AL1-5: Allergy reaction
        if allergy_data.get("reaction"):
            al1.set_field(5, allergy_data["reaction"])

        builder.message.add_segment(al1)

    def _generate_control_id(self) -> str:
        """Generate unique message control ID.

        Returns:
            Unique control ID
        """
        return str(uuid.uuid4())[:20]

    def parse_adt_message(self, message: HL7Message) -> Dict[str, Any]:
        """Parse ADT message into structured data.

        Args:
            message: HL7Message to parse

        Returns:
            Parsed data dictionary
        """
        result: Dict[str, Any] = {
            "message_type": message.get_message_type(),
            "control_id": message.get_message_control_id(),
            "timestamp": None,
            "patient": {},
            "visit": {},
            "diagnoses": [],
            "allergies": [],
        }

        # Parse MSH
        msh = message.get_segment("MSH")
        if msh:
            timestamp_field = msh.get_field(7)
            if timestamp_field:
                result["timestamp"] = timestamp_field.get_first_value()

        # Parse PID
        pid = message.get_segment("PID")
        if pid:
            result["patient"] = self._parse_pid_segment(pid)

        # Parse PV1
        pv1 = message.get_segment("PV1")
        if pv1:
            result["visit"] = self._parse_pv1_segment(pv1)

        # Parse all DG1 segments
        for dg1 in message.get_all_segments("DG1"):
            result["diagnoses"].append(self._parse_dg1_segment(dg1))

        # Parse all AL1 segments
        for al1 in message.get_all_segments("AL1"):
            result["allergies"].append(self._parse_al1_segment(al1))

        return result

    def _parse_pid_segment(self, pid: HL7Segment) -> Dict[str, Any]:
        """Parse PID segment.

        Args:
            pid: PID segment

        Returns:
            Patient data dictionary
        """
        patient_data: Dict[str, Any] = {}

        # PID-3: Patient identifier
        id_field = pid.get_field(3)
        if id_field:
            patient_data["id"] = id_field.get_value(0, 0, 0)
            patient_data["id_type"] = id_field.get_value(0, 4, 0)

            # Check for additional identifiers
            refugee_id = id_field.get_value(1, 0, 0)
            if refugee_id:
                patient_data["refugee_id"] = refugee_id

        # PID-5: Patient name
        name_field = pid.get_field(5)
        if name_field:
            patient_data["name"] = {
                "family": name_field.get_value(0, 0, 0),
                "given": name_field.get_value(0, 1, 0),
                "middle": name_field.get_value(0, 2, 0),
                "suffix": name_field.get_value(0, 3, 0),
                "prefix": name_field.get_value(0, 4, 0),
            }

        # PID-7: Date of birth
        dob_field = pid.get_field(7)
        if dob_field:
            patient_data["birth_date"] = dob_field.get_first_value()

        # PID-8: Gender
        gender_field = pid.get_field(8)
        if gender_field:
            patient_data["gender"] = gender_field.get_first_value()

        # PID-11: Address
        addr_field = pid.get_field(11)
        if addr_field:
            patient_data["address"] = {
                "street": addr_field.get_value(0, 0, 0),
                "city": addr_field.get_value(0, 2, 0),
                "state": addr_field.get_value(0, 3, 0),
                "zip": addr_field.get_value(0, 4, 0),
                "country": addr_field.get_value(0, 5, 0),
            }

        # PID-13: Phone
        phone_field = pid.get_field(13)
        if phone_field:
            patient_data["phone"] = phone_field.get_first_value()

        return patient_data

    def _parse_pv1_segment(self, pv1: HL7Segment) -> Dict[str, Any]:
        """Parse PV1 segment.

        Args:
            pv1: PV1 segment

        Returns:
            Visit data dictionary
        """
        visit_data: Dict[str, Any] = {}

        # PV1-2: Patient class
        class_field = pv1.get_field(2)
        if class_field:
            visit_data["patient_class"] = class_field.get_first_value()

        # PV1-3: Patient location
        location_field = pv1.get_field(3)
        if location_field:
            visit_data["location"] = location_field.get_first_value()

        # PV1-4: Admission type
        admission_field = pv1.get_field(4)
        if admission_field:
            visit_data["admission_type"] = admission_field.get_first_value()

        # PV1-7: Attending doctor
        doctor_field = pv1.get_field(7)
        if doctor_field:
            visit_data["attending_doctor"] = doctor_field.get_first_value()

        # PV1-44: Admit date/time
        admit_field = pv1.get_field(44)
        if admit_field:
            visit_data["admit_datetime"] = admit_field.get_first_value()

        # PV1-45: Discharge date/time
        discharge_field = pv1.get_field(45)
        if discharge_field:
            visit_data["discharge_datetime"] = discharge_field.get_first_value()

        return visit_data

    def _parse_dg1_segment(self, dg1: HL7Segment) -> Dict[str, Any]:
        """Parse DG1 segment.

        Args:
            dg1: DG1 segment

        Returns:
            Diagnosis data dictionary
        """
        diagnosis_data = {}

        # DG1-3: Diagnosis code
        diag_field = dg1.get_field(3)
        if diag_field:
            diagnosis_data["code"] = diag_field.get_value(0, 0, 0)
            diagnosis_data["description"] = diag_field.get_value(0, 1, 0)
            diagnosis_data["coding_system"] = diag_field.get_value(0, 2, 0)

        # DG1-5: Diagnosis date
        date_field = dg1.get_field(5)
        if date_field:
            diagnosis_data["date"] = date_field.get_first_value()

        # DG1-6: Diagnosis type
        type_field = dg1.get_field(6)
        if type_field:
            diagnosis_data["type"] = type_field.get_first_value()

        return diagnosis_data

    def _parse_al1_segment(self, al1: HL7Segment) -> Dict[str, Any]:
        """Parse AL1 segment.

        Args:
            al1: AL1 segment

        Returns:
            Allergy data dictionary
        """
        allergy_data = {}

        # AL1-2: Allergen type
        type_field = al1.get_field(2)
        if type_field:
            allergy_data["type"] = type_field.get_first_value()

        # AL1-3: Allergen
        allergen_field = al1.get_field(3)
        if allergen_field:
            allergy_data["code"] = allergen_field.get_value(0, 0, 0)
            allergy_data["description"] = allergen_field.get_value(0, 1, 0)

        # AL1-4: Severity
        severity_field = al1.get_field(4)
        if severity_field:
            allergy_data["severity"] = severity_field.get_first_value()

        # AL1-5: Reaction
        reaction_field = al1.get_field(5)
        if reaction_field:
            allergy_data["reaction"] = reaction_field.get_first_value()

        return allergy_data
