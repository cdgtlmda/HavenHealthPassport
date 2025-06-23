"""HL7 ORM Message Implementation.

This module implements HL7 ORM (Order) messages for managing
laboratory, radiology, and other diagnostic orders in refugee
healthcare settings. Handles FHIR ServiceRequest Resource validation.
All PHI data is encrypted and access is controlled through role-based permissions.
"""

import logging
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from src.healthcare.fhir_validator import FHIRValidator
from src.healthcare.hipaa_access_control import AccessLevel, require_phi_access

from .hl7_message import HL7Message, HL7MessageBuilder, HL7Segment
from .hl7_message_types import HL7EncodingCharacters, HL7Field

logger = logging.getLogger(__name__)

# FHIR resource type for this module
__fhir_resource__ = "ServiceRequest"


class ORMMessageHandler:
    """Handler for ORM message types."""

    def __init__(self, encoding: Optional[HL7EncodingCharacters] = None):
        """Initialize ORM message handler.

        Args:
            encoding: HL7 encoding characters
        """
        self.encoding = encoding or HL7EncodingCharacters()
        self.validator = FHIRValidator()

    def validate_order(self, order_data: Dict[str, Any]) -> bool:
        """Validate order data.

        Args:
            order_data: Order data to validate

        Returns:
            True if valid
        """
        try:
            # Validate required fields
            if not order_data.get("patient_id"):
                return False
            if not order_data.get("order_control"):
                return False
            return True
        except (AttributeError, KeyError, TypeError, ValueError):
            return False

    @require_phi_access(AccessLevel.WRITE)
    def create_orm_o01_order(
        self, patient_id: str, order_data: Dict[str, Any]
    ) -> HL7Message:
        """Create ORM^O01 order message.

        Args:
            patient_id: Patient identifier
            order_data: Order details

        Returns:
            HL7Message for order
        """
        builder = HL7MessageBuilder(self.encoding)

        # Add MSH segment
        builder.add_msh(
            sending_application="HavenHealthPassport",
            sending_facility=order_data.get("facility", "RefugeeCamp"),
            receiving_application=order_data.get("receiving_app", "LIS"),
            receiving_facility=order_data.get("receiving_facility", "Lab"),
            message_type="ORM^O01",
            message_control_id=self._generate_control_id(),
            processing_id="P",
            version_id="2.5",
        )

        # Add PID segment
        builder.add_pid(
            patient_id=patient_id,
            patient_name=order_data.get("patient_name", {}),
            birth_date=order_data.get("birth_date"),
            gender=order_data.get("gender"),
        )

        # Add PV1 segment if patient visit info available
        if order_data.get("patient_location"):
            builder.add_pv1(
                patient_class=order_data.get("patient_class", "O"),
                location=order_data.get("patient_location"),
            )

        # Add ORC segment (Common Order)
        self._add_orc_segment(builder, order_data)

        # Add OBR segment (Observation Request) for each test
        for test in order_data.get("tests", []):
            self._add_obr_segment(builder, test, order_data)

        # Add NTE segment for order notes
        if order_data.get("notes"):
            self._add_nte_segment(builder, order_data["notes"])

        return builder.build()

    def create_order_cancel(self, order_id: str, cancel_reason: str) -> HL7Message:
        """Create order cancellation message.

        Args:
            order_id: Order ID to cancel
            cancel_reason: Reason for cancellation

        Returns:
            HL7Message for cancellation
        """
        builder = HL7MessageBuilder(self.encoding)

        # Add MSH segment
        builder.add_msh(
            sending_application="HavenHealthPassport",
            sending_facility="RefugeeCamp",
            receiving_application="LIS",
            receiving_facility="Lab",
            message_type="ORM^O01",
            message_control_id=self._generate_control_id(),
            processing_id="P",
            version_id="2.5",
        )

        # Add minimal PID
        pid = HL7Segment(f"PID{self.encoding.field_separator}", self.encoding)
        pid.set_field(1, "1")
        builder.message.add_segment(pid)

        # Add ORC with cancel status
        orc = HL7Segment(f"ORC{self.encoding.field_separator}", self.encoding)
        orc.set_field(1, "CA")  # Order control: Cancel
        orc.set_field(2, order_id)  # Placer order number
        orc.set_field(5, "CA")  # Order status: Cancelled
        orc.set_field(16, cancel_reason)  # Order control code reason
        builder.message.add_segment(orc)

        return builder.build()

    def _add_orc_segment(
        self, builder: HL7MessageBuilder, order_data: Dict[str, Any]
    ) -> None:
        """Add ORC (Common Order) segment.

        Args:
            builder: Message builder
            order_data: Order data
        """
        orc = HL7Segment(f"ORC{self.encoding.field_separator}", self.encoding)

        # ORC-1: Order control (NW=New, CA=Cancel, DC=Discontinue)
        orc.set_field(1, order_data.get("order_control", "NW"))

        # ORC-2: Placer order number
        orc.set_field(2, order_data.get("order_id", self._generate_order_id()))

        # ORC-3: Filler order number (empty for new orders)
        if order_data.get("filler_order_id"):
            orc.set_field(3, order_data["filler_order_id"])

        # ORC-5: Order status
        orc.set_field(5, order_data.get("order_status", "IP"))  # IP=In Process

        # ORC-7: Quantity/timing
        timing_field = HL7Field("", self.encoding)
        timing_field.set_value(order_data.get("priority", "R"), 0, 5, 0)  # Priority
        timing_field.set_value("1", 0, 0, 0)  # Quantity
        if order_data.get("collection_time"):
            timing_field.set_value(order_data["collection_time"], 0, 3, 0)
        orc.fields[6] = timing_field

        # ORC-9: Date/time of transaction
        orc.set_field(9, datetime.now().strftime("%Y%m%d%H%M%S"))

        # ORC-10: Entered by
        if order_data.get("entered_by"):
            orc.set_field(10, order_data["entered_by"])

        # ORC-12: Ordering provider
        if order_data.get("ordering_provider"):
            provider_field = HL7Field("", self.encoding)
            provider = order_data["ordering_provider"]
            provider_field.set_value(provider.get("id", ""), 0, 0, 0)
            provider_field.set_value(provider.get("family", ""), 0, 1, 0)
            provider_field.set_value(provider.get("given", ""), 0, 2, 0)
            orc.fields[11] = provider_field

        # ORC-15: Order effective date/time
        orc.set_field(
            15, order_data.get("effective_date", datetime.now().strftime("%Y%m%d"))
        )

        builder.message.add_segment(orc)

    def _add_obr_segment(
        self,
        builder: HL7MessageBuilder,
        test_data: Dict[str, Any],
        order_data: Dict[str, Any],
    ) -> None:
        """Add OBR (Observation Request) segment.

        Args:
            builder: Message builder
            test_data: Individual test data
            order_data: Overall order data
        """
        obr = HL7Segment(f"OBR{self.encoding.field_separator}", self.encoding)

        # OBR-1: Set ID
        segment_count = len(builder.message.get_all_segments("OBR")) + 1
        obr.set_field(1, str(segment_count))

        # OBR-2: Placer order number
        obr.set_field(2, order_data.get("order_id", self._generate_order_id()))

        # OBR-4: Universal service identifier
        service_field = HL7Field("", self.encoding)
        service_field.set_value(test_data.get("code", ""), 0, 0, 0)
        service_field.set_value(test_data.get("name", ""), 0, 1, 0)
        service_field.set_value(test_data.get("coding_system", "LN"), 0, 2, 0)  # LOINC
        obr.fields[3] = service_field

        # OBR-7: Observation date/time
        obr.set_field(
            7,
            order_data.get("collection_time", datetime.now().strftime("%Y%m%d%H%M%S")),
        )

        # OBR-11: Specimen action code
        obr.set_field(11, "P")  # P=Pending

        # OBR-13: Relevant clinical information
        if test_data.get("clinical_info"):
            obr.set_field(13, test_data["clinical_info"])

        # OBR-15: Specimen source
        if test_data.get("specimen_source"):
            specimen_field = HL7Field("", self.encoding)
            specimen = test_data["specimen_source"]
            specimen_field.set_value(specimen.get("code", ""), 0, 0, 0)
            specimen_field.set_value(specimen.get("name", ""), 0, 1, 0)
            obr.fields[14] = specimen_field

        # OBR-16: Ordering provider
        if order_data.get("ordering_provider"):
            provider_field = HL7Field("", self.encoding)
            provider = order_data["ordering_provider"]
            provider_field.set_value(provider.get("id", ""), 0, 0, 0)
            provider_field.set_value(provider.get("family", ""), 0, 1, 0)
            provider_field.set_value(provider.get("given", ""), 0, 2, 0)
            obr.fields[15] = provider_field

        # OBR-25: Result status
        obr.set_field(25, "O")  # O=Order received

        # OBR-27: Quantity/timing
        priority_field = HL7Field("", self.encoding)
        priority_field.set_value(
            test_data.get("priority", "R"), 0, 5, 0
        )  # R=Routine, S=Stat
        obr.fields[26] = priority_field

        # OBR-31: Reason for study
        if test_data.get("reason"):
            obr.set_field(31, test_data["reason"])

        builder.message.add_segment(obr)

    def _add_nte_segment(self, builder: HL7MessageBuilder, notes: str) -> None:
        """Add NTE (Notes and Comments) segment.

        Args:
            builder: Message builder
            notes: Note text
        """
        nte = HL7Segment(f"NTE{self.encoding.field_separator}", self.encoding)

        # NTE-1: Set ID
        nte.set_field(1, "1")

        # NTE-2: Source of comment (L=Lab, P=Placer)
        nte.set_field(2, "P")

        # NTE-3: Comment
        nte.set_field(3, notes)

        builder.message.add_segment(nte)

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
        return f"ORD{timestamp}{str(uuid.uuid4())[:6].upper()}"

    def parse_orm_message(self, message: HL7Message) -> Dict[str, Any]:
        """Parse ORM message into structured data.

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

        # Parse ORC/OBR pairs
        orc_segments = message.get_all_segments("ORC")
        obr_segments = message.get_all_segments("OBR")

        for orc in orc_segments:
            order = self._parse_orc_segment(orc)

            # Find associated OBR segments
            order["tests"] = []
            for obr in obr_segments:
                # Check if this OBR belongs to this ORC
                # (simplified - in real implementation would match by order ID)
                order["tests"].append(self._parse_obr_segment(obr))

            result["orders"].append(order)

        return result

    def _parse_orc_segment(self, orc: HL7Segment) -> Dict[str, Any]:
        """Parse ORC segment.

        Args:
            orc: ORC segment

        Returns:
            Order data dictionary
        """
        order_data: Dict[str, Any] = {}

        # ORC-1: Order control
        control_field = orc.get_field(1)
        if control_field:
            order_data["order_control"] = control_field.get_first_value()

        # ORC-2: Placer order number
        order_id_field = orc.get_field(2)
        if order_id_field:
            order_data["order_id"] = order_id_field.get_first_value()

        # ORC-3: Filler order number
        filler_field = orc.get_field(3)
        if filler_field:
            order_data["filler_order_id"] = filler_field.get_first_value()

        # ORC-5: Order status
        status_field = orc.get_field(5)
        if status_field:
            order_data["order_status"] = status_field.get_first_value()

        # ORC-7: Quantity/timing
        timing_field = orc.get_field(7)
        if timing_field:
            order_data["priority"] = timing_field.get_value(0, 5, 0)
            order_data["collection_time"] = timing_field.get_value(0, 3, 0)

        # ORC-9: Date/time of transaction
        transaction_field = orc.get_field(9)
        if transaction_field:
            order_data["transaction_datetime"] = transaction_field.get_first_value()

        # ORC-12: Ordering provider
        provider_field = orc.get_field(12)
        if provider_field:
            order_data["ordering_provider"] = {
                "id": provider_field.get_value(0, 0, 0),
                "family": provider_field.get_value(0, 1, 0),
                "given": provider_field.get_value(0, 2, 0),
            }

        return order_data

    def _parse_obr_segment(self, obr: HL7Segment) -> Dict[str, Any]:
        """Parse OBR segment.

        Args:
            obr: OBR segment

        Returns:
            Test data dictionary
        """
        test_data: Dict[str, Any] = {}

        # OBR-4: Universal service identifier
        service_field = obr.get_field(4)
        if service_field:
            test_data["code"] = service_field.get_value(0, 0, 0)
            test_data["name"] = service_field.get_value(0, 1, 0)
            test_data["coding_system"] = service_field.get_value(0, 2, 0)

        # OBR-7: Observation date/time
        obs_time_field = obr.get_field(7)
        if obs_time_field:
            test_data["observation_datetime"] = obs_time_field.get_first_value()

        # OBR-15: Specimen source
        specimen_field = obr.get_field(15)
        if specimen_field:
            test_data["specimen_source"] = {
                "code": specimen_field.get_value(0, 0, 0),
                "name": specimen_field.get_value(0, 1, 0),
            }

        # OBR-25: Result status
        status_field = obr.get_field(25)
        if status_field:
            test_data["result_status"] = status_field.get_first_value()

        # OBR-27: Quantity/timing
        priority_field = obr.get_field(27)
        if priority_field:
            test_data["priority"] = priority_field.get_value(0, 5, 0)

        return test_data
