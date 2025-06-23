"""HL7 ORU Message Implementation.

This module implements HL7 ORU (Observation Result) messages for
reporting laboratory results, vital signs, and other clinical observations
in refugee healthcare settings. Handles FHIR DiagnosticReport Resource validation.
All PHI data is encrypted and access is controlled through role-based permissions.
"""

import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, cast

from src.healthcare.fhir_validator import FHIRValidator
from src.healthcare.hipaa_access_control import AccessLevel, require_phi_access

from .hl7_message import HL7Message, HL7MessageBuilder, HL7Segment
from .hl7_message_types import HL7EncodingCharacters, HL7Field

logger = logging.getLogger(__name__)

# FHIR resource type for this module
__fhir_resource__ = "DiagnosticReport"


class ORUMessageHandler:
    """Handler for ORU message types."""

    def __init__(self, encoding: Optional[HL7EncodingCharacters] = None):
        """Initialize ORU message handler.

        Args:
            encoding: HL7 encoding characters
        """
        self.encoding = encoding or HL7EncodingCharacters()
        self.validator = FHIRValidator()

    def validate_results(self, results: List[Dict[str, Any]]) -> bool:
        """Validate result observations.

        Args:
            results: List of results to validate

        Returns:
            True if valid
        """
        try:
            if not results:
                return False

            for result in results:
                if not result.get("test_id") or not result.get("value"):
                    return False

            return True
        except (KeyError, TypeError, ValueError) as e:
            logger.warning("Validation error in results: %s", str(e))
            return False

    @require_phi_access(AccessLevel.WRITE)
    def create_oru_r01_result(
        self,
        patient_id: str,
        order_id: str,
        results: List[Dict[str, Any]],
        result_meta: Dict[str, Any],
    ) -> HL7Message:
        """Create ORU^R01 unsolicited observation result message.

        Args:
            patient_id: Patient identifier
            order_id: Order identifier
            results: List of result observations
            result_meta: Result metadata

        Returns:
            HL7Message for results
        """
        builder = HL7MessageBuilder(self.encoding)

        # Add MSH segment
        builder.add_msh(
            sending_application="HavenHealthPassport",
            sending_facility=result_meta.get("facility", "RefugeeLab"),
            receiving_application=result_meta.get("receiving_app", "EMR"),
            receiving_facility=result_meta.get("receiving_facility", "Clinic"),
            message_type="ORU^R01",
            message_control_id=self._generate_control_id(),
            processing_id="P",
            version_id="2.5",
        )

        # Add PID segment
        builder.add_pid(
            patient_id=patient_id,
            patient_name=result_meta.get("patient_name", {}),
            birth_date=result_meta.get("birth_date"),
            gender=result_meta.get("gender"),
        )

        # Add PV1 segment if available
        if result_meta.get("patient_location"):
            builder.add_pv1(
                patient_class=result_meta.get("patient_class", "O"),
                location=result_meta.get("patient_location"),
            )

        # Add ORC segment
        self._add_orc_segment(builder, order_id, result_meta)

        # Add OBR segment
        self._add_obr_segment(builder, order_id, result_meta)

        # Add OBX segments for each result
        for i, result in enumerate(results):
            self._add_obx_segment(builder, result, i + 1)

            # Add NTE for result comments
            if result.get("comments"):
                self._add_nte_segment(builder, result["comments"], i + 1)

        return builder.build()

    def create_vital_signs_result(
        self, patient_id: str, vital_signs: Dict[str, Any]
    ) -> HL7Message:
        """Create ORU message for vital signs.

        Args:
            patient_id: Patient identifier
            vital_signs: Vital signs data

        Returns:
            HL7Message for vital signs
        """
        # Convert vital signs to result format
        results = []

        # Map vital signs to LOINC codes
        vital_mappings = {
            "temperature": {
                "code": "8310-5",
                "name": "Body temperature",
                "unit": "Cel",
            },
            "heart_rate": {"code": "8867-4", "name": "Heart rate", "unit": "/min"},
            "blood_pressure_systolic": {
                "code": "8480-6",
                "name": "Systolic blood pressure",
                "unit": "mm[Hg]",
            },
            "blood_pressure_diastolic": {
                "code": "8462-4",
                "name": "Diastolic blood pressure",
                "unit": "mm[Hg]",
            },
            "respiratory_rate": {
                "code": "9279-1",
                "name": "Respiratory rate",
                "unit": "/min",
            },
            "oxygen_saturation": {
                "code": "59408-5",
                "name": "Oxygen saturation",
                "unit": "%",
            },
        }

        for vital_type, value in vital_signs.items():
            if vital_type in vital_mappings and value is not None:
                mapping = vital_mappings[vital_type]
                results.append(
                    {
                        "test_code": mapping["code"],
                        "test_name": mapping["name"],
                        "value": str(value),
                        "unit": mapping["unit"],
                        "value_type": "NM",  # Numeric
                        "result_status": "F",  # Final
                        "observation_datetime": vital_signs.get(
                            "datetime", datetime.now()
                        ),
                    }
                )

        result_meta = {
            "facility": vital_signs.get("facility", "RefugeeCamp"),
            "test_name": "Vital Signs Panel",
            "test_code": "35094-2",  # LOINC for vital signs panel
            "result_status": "F",
            "observation_datetime": vital_signs.get("datetime", datetime.now()),
        }

        result = self.create_oru_r01_result(
            patient_id=patient_id,
            order_id=self._generate_order_id(),
            results=results,
            result_meta=result_meta,
        )
        return cast(HL7Message, result)

    def create_lab_result(
        self, patient_id: str, order_id: str, lab_results: List[Dict[str, Any]]
    ) -> HL7Message:
        """Create ORU message for laboratory results.

        Args:
            patient_id: Patient identifier
            order_id: Lab order ID
            lab_results: Laboratory results

        Returns:
            HL7Message for lab results
        """
        # Process lab results
        results = []
        for lab_result in lab_results:
            result = {
                "test_code": lab_result.get("loinc_code"),
                "test_name": lab_result.get("test_name"),
                "value": lab_result.get("value"),
                "unit": lab_result.get("unit"),
                "reference_range": lab_result.get("reference_range"),
                "abnormal_flag": lab_result.get("abnormal_flag"),
                "result_status": lab_result.get("status", "F"),
                "observation_datetime": lab_result.get("datetime", datetime.now()),
                "value_type": self._determine_value_type(lab_result.get("value")),
            }

            # Add interpretation if abnormal
            if lab_result.get("abnormal_flag"):
                result["interpretation"] = self._get_interpretation(lab_result)

            results.append(result)

        result_meta = {
            "facility": "RefugeeLab",
            "test_name": "Laboratory Panel",
            "result_status": "F",
            "observation_datetime": datetime.now(),
        }

        result = self.create_oru_r01_result(
            patient_id=patient_id,
            order_id=order_id,
            results=results,
            result_meta=result_meta,
        )
        return cast(HL7Message, result)

    def _add_orc_segment(
        self, builder: HL7MessageBuilder, order_id: str, result_meta: Dict[str, Any]
    ) -> None:
        """Add ORC segment for result message.

        Args:
            builder: Message builder
            order_id: Order identifier
            result_meta: Result metadata
        """
        orc = HL7Segment(f"ORC{self.encoding.field_separator}", self.encoding)

        # ORC-1: Order control (RE=Observations to follow)
        orc.set_field(1, "RE")

        # ORC-2: Placer order number
        orc.set_field(2, order_id)

        # ORC-3: Filler order number
        if result_meta.get("filler_order_id"):
            orc.set_field(3, result_meta["filler_order_id"])

        # ORC-5: Order status (CM=Complete)
        orc.set_field(5, "CM")

        # ORC-9: Date/time of transaction
        orc.set_field(9, datetime.now().strftime("%Y%m%d%H%M%S"))

        # ORC-12: Ordering provider
        if result_meta.get("ordering_provider"):
            provider_field = HL7Field("", self.encoding)
            provider = result_meta["ordering_provider"]
            provider_field.set_value(provider.get("id", ""), 0, 0, 0)
            provider_field.set_value(provider.get("family", ""), 0, 1, 0)
            provider_field.set_value(provider.get("given", ""), 0, 2, 0)
            orc.fields[11] = provider_field

        builder.message.add_segment(orc)

    def _add_obr_segment(
        self, builder: HL7MessageBuilder, order_id: str, result_meta: Dict[str, Any]
    ) -> None:
        """Add OBR segment for result message.

        Args:
            builder: Message builder
            order_id: Order identifier
            result_meta: Result metadata
        """
        obr = HL7Segment(f"OBR{self.encoding.field_separator}", self.encoding)

        # OBR-1: Set ID
        obr.set_field(1, "1")

        # OBR-2: Placer order number
        obr.set_field(2, order_id)

        # OBR-3: Filler order number
        if result_meta.get("filler_order_id"):
            obr.set_field(3, result_meta["filler_order_id"])

        # OBR-4: Universal service identifier
        service_field = HL7Field("", self.encoding)
        service_field.set_value(result_meta.get("test_code", ""), 0, 0, 0)
        service_field.set_value(result_meta.get("test_name", ""), 0, 1, 0)
        service_field.set_value("LN", 0, 2, 0)  # LOINC
        obr.fields[3] = service_field

        # OBR-7: Observation date/time
        obs_datetime = result_meta.get("observation_datetime", datetime.now())
        if isinstance(obs_datetime, datetime):
            obs_datetime = obs_datetime.strftime("%Y%m%d%H%M%S")
        obr.set_field(7, obs_datetime)

        # OBR-14: Specimen received date/time
        if result_meta.get("specimen_received"):
            obr.set_field(14, result_meta["specimen_received"])

        # OBR-15: Specimen source
        if result_meta.get("specimen_source"):
            specimen_field = HL7Field("", self.encoding)
            specimen = result_meta["specimen_source"]
            specimen_field.set_value(specimen.get("code", ""), 0, 0, 0)
            specimen_field.set_value(specimen.get("name", ""), 0, 1, 0)
            obr.fields[14] = specimen_field

        # OBR-22: Results report date/time
        obr.set_field(22, datetime.now().strftime("%Y%m%d%H%M%S"))

        # OBR-25: Result status (F=Final, P=Preliminary, C=Correction)
        obr.set_field(25, result_meta.get("result_status", "F"))

        # OBR-32: Principal result interpreter
        if result_meta.get("result_interpreter"):
            interpreter_field = HL7Field("", self.encoding)
            interpreter = result_meta["result_interpreter"]
            interpreter_field.set_value(interpreter.get("id", ""), 0, 0, 0)
            interpreter_field.set_value(interpreter.get("family", ""), 0, 1, 0)
            interpreter_field.set_value(interpreter.get("given", ""), 0, 2, 0)
            obr.fields[31] = interpreter_field

        builder.message.add_segment(obr)

    def _add_obx_segment(
        self, builder: HL7MessageBuilder, result: Dict[str, Any], sequence: int
    ) -> None:
        """Add OBX segment for individual result.

        Args:
            builder: Message builder
            result: Individual result data
            sequence: Sequence number
        """
        obx = HL7Segment(f"OBX{self.encoding.field_separator}", self.encoding)

        # OBX-1: Set ID
        obx.set_field(1, str(sequence))

        # OBX-2: Value type
        obx.set_field(2, result.get("value_type", "ST"))

        # OBX-3: Observation identifier
        obs_field = HL7Field("", self.encoding)
        obs_field.set_value(result.get("test_code", ""), 0, 0, 0)
        obs_field.set_value(result.get("test_name", ""), 0, 1, 0)
        obs_field.set_value("LN", 0, 2, 0)  # LOINC
        obx.fields[2] = obs_field

        # OBX-4: Observation sub-ID (for multiple values)
        if result.get("sub_id"):
            obx.set_field(4, result["sub_id"])

        # OBX-5: Observation value
        value = result.get("value", "")
        if result.get("value_type") == "ST":  # String
            obx.set_field(5, str(value))
        elif result.get("value_type") == "NM":  # Numeric
            obx.set_field(5, str(value))
        elif result.get("value_type") == "CE":  # Coded element
            value_field = HL7Field("", self.encoding)
            if isinstance(value, dict):
                value_field.set_value(value.get("code", ""), 0, 0, 0)
                value_field.set_value(value.get("text", ""), 0, 1, 0)
                value_field.set_value(value.get("system", ""), 0, 2, 0)
            obx.fields[4] = value_field
        else:
            obx.set_field(5, str(value))

        # OBX-6: Units
        if result.get("unit"):
            obx.set_field(6, result["unit"])

        # OBX-7: Reference range
        if result.get("reference_range"):
            obx.set_field(7, result["reference_range"])

        # OBX-8: Abnormal flags
        if result.get("abnormal_flag"):
            obx.set_field(8, result["abnormal_flag"])

        # OBX-11: Observation result status
        obx.set_field(11, result.get("result_status", "F"))

        # OBX-14: Date/time of observation
        obs_datetime = result.get("observation_datetime", datetime.now())
        if isinstance(obs_datetime, datetime):
            obs_datetime = obs_datetime.strftime("%Y%m%d%H%M%S")
        obx.set_field(14, obs_datetime)

        # OBX-15: Producer's reference
        if result.get("producer_reference"):
            obx.set_field(15, result["producer_reference"])

        # OBX-16: Responsible observer
        if result.get("responsible_observer"):
            observer_field = HL7Field("", self.encoding)
            observer = result["responsible_observer"]
            observer_field.set_value(observer.get("id", ""), 0, 0, 0)
            observer_field.set_value(observer.get("family", ""), 0, 1, 0)
            observer_field.set_value(observer.get("given", ""), 0, 2, 0)
            obx.fields[15] = observer_field

        # OBX-19: Date/time of analysis
        if result.get("analysis_datetime"):
            obx.set_field(19, result["analysis_datetime"])

        builder.message.add_segment(obx)

    def _add_nte_segment(
        self, builder: HL7MessageBuilder, comment: str, sequence: int
    ) -> None:
        """Add NTE segment for result comments.

        Args:
            builder: Message builder
            comment: Comment text
            sequence: Sequence number
        """
        nte = HL7Segment(f"NTE{self.encoding.field_separator}", self.encoding)

        # NTE-1: Set ID
        nte.set_field(1, str(sequence))

        # NTE-2: Source of comment (L=Laboratory)
        nte.set_field(2, "L")

        # NTE-3: Comment
        nte.set_field(3, comment)

        builder.message.add_segment(nte)

    def _determine_value_type(self, value: Any) -> str:
        """Determine HL7 value type from Python value.

        Args:
            value: Value to check

        Returns:
            HL7 value type code
        """
        if isinstance(value, (int, float)):
            return "NM"  # Numeric
        elif isinstance(value, dict):
            return "CE"  # Coded element
        elif isinstance(value, bool):
            return "ST"  # String (Yes/No)
        else:
            return "ST"  # String (default)

    def _get_interpretation(self, result: Dict[str, Any]) -> str:
        """Get interpretation text for abnormal result.

        Args:
            result: Result data

        Returns:
            Interpretation text
        """
        flag = result.get("abnormal_flag", "")
        value = result.get("value")
        reference = result.get("reference_range", "")

        interpretations = {
            "H": f"High - Value {value} exceeds normal range {reference}",
            "L": f"Low - Value {value} below normal range {reference}",
            "HH": f"Critical High - Value {value} critically exceeds normal range {reference}",
            "LL": f"Critical Low - Value {value} critically below normal range {reference}",
            "A": f"Abnormal - Value {value} outside normal range {reference}",
        }

        return interpretations.get(flag, f"Abnormal result: {value}")

    def _generate_control_id(self) -> str:
        """Generate unique message control ID.

        Returns:
            Unique control ID
        """
        return str(uuid.uuid4())[:20]

    def _generate_order_id(self) -> str:
        """Generate unique order ID.

        Returns:
            Unique order ID
        """
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        return f"VS{timestamp}{str(uuid.uuid4())[:6].upper()}"

    def parse_oru_message(self, message: HL7Message) -> Dict[str, Any]:
        """Parse ORU message into structured data.

        Args:
            message: HL7Message to parse

        Returns:
            Parsed data dictionary
        """
        result: Dict[str, Any] = {
            "message_type": message.get_message_type(),
            "control_id": message.get_message_control_id(),
            "patient_id": None,
            "orders": [],
        }

        # Parse PID
        pid = message.get_segment("PID")
        if pid:
            id_field = pid.get_field(3)
            if id_field:
                result["patient_id"] = id_field.get_value(0, 0, 0)

        # Parse OBR/OBX groups
        obr_segments = message.get_all_segments("OBR")

        for obr in obr_segments:
            order = self._parse_obr_segment(obr)
            order["results"] = []

            # Find OBX segments that follow this OBR
            obx_segments = message.get_all_segments("OBX")
            for obx in obx_segments:
                result_data = self._parse_obx_segment(obx)
                order["results"].append(result_data)

            result["orders"].append(order)

        return result

    def _parse_obr_segment(self, obr: HL7Segment) -> Dict[str, Any]:
        """Parse OBR segment from result message.

        Args:
            obr: OBR segment

        Returns:
            Order data dictionary
        """
        order_data: Dict[str, Any] = {}

        # OBR-2: Placer order number
        order_field = obr.get_field(2)
        if order_field:
            order_data["order_id"] = order_field.get_first_value()

        # OBR-3: Filler order number
        filler_field = obr.get_field(3)
        if filler_field:
            order_data["filler_order_id"] = filler_field.get_first_value()

        # OBR-4: Universal service identifier
        service_field = obr.get_field(4)
        if service_field:
            order_data["test"] = {
                "code": service_field.get_value(0, 0, 0),
                "name": service_field.get_value(0, 1, 0),
                "system": service_field.get_value(0, 2, 0),
            }

        # OBR-7: Observation date/time
        obs_field = obr.get_field(7)
        if obs_field:
            order_data["observation_datetime"] = obs_field.get_first_value()

        # OBR-25: Result status
        status_field = obr.get_field(25)
        if status_field:
            order_data["result_status"] = status_field.get_first_value()

        return order_data

    def _parse_obx_segment(self, obx: HL7Segment) -> Dict[str, Any]:
        """Parse OBX segment.

        Args:
            obx: OBX segment

        Returns:
            Result data dictionary
        """
        result_data: Dict[str, Any] = {}

        # OBX-2: Value type
        type_field = obx.get_field(2)
        if type_field:
            result_data["value_type"] = type_field.get_first_value()

        # OBX-3: Observation identifier
        obs_field = obx.get_field(3)
        if obs_field:
            result_data["test"] = {
                "code": obs_field.get_value(0, 0, 0),
                "name": obs_field.get_value(0, 1, 0),
                "system": obs_field.get_value(0, 2, 0),
            }

        # OBX-5: Observation value
        value_field = obx.get_field(5)
        if value_field:
            if result_data.get("value_type") == "CE":
                result_data["value"] = {
                    "code": value_field.get_value(0, 0, 0),
                    "text": value_field.get_value(0, 1, 0),
                    "system": value_field.get_value(0, 2, 0),
                }
            else:
                result_data["value"] = value_field.get_first_value()

        # OBX-6: Units
        unit_field = obx.get_field(6)
        if unit_field:
            result_data["unit"] = unit_field.get_first_value()

        # OBX-7: Reference range
        range_field = obx.get_field(7)
        if range_field:
            result_data["reference_range"] = range_field.get_first_value()

        # OBX-8: Abnormal flags
        flag_field = obx.get_field(8)
        if flag_field:
            result_data["abnormal_flag"] = flag_field.get_first_value()

        # OBX-11: Result status
        status_field = obx.get_field(11)
        if status_field:
            result_data["result_status"] = status_field.get_first_value()

        # OBX-14: Observation date/time
        datetime_field = obx.get_field(14)
        if datetime_field:
            result_data["observation_datetime"] = datetime_field.get_first_value()

        return result_data
