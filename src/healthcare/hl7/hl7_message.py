"""HL7 Message Implementation.

This module implements HL7 v2 message parsing, creation, and validation
for healthcare interoperability. Handles FHIR MessageHeader Resource conversion
and validation.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING, Dict, List, Optional, Tuple

from .hl7_message_types import HL7EncodingCharacters, HL7Field

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# FHIR resource type for this module
__fhir_resource__ = "MessageHeader"


class HL7Message:
    """Represents a complete HL7 message."""

    def __init__(
        self,
        message_string: Optional[str] = None,
        encoding: Optional[HL7EncodingCharacters] = None,
    ):
        """Initialize HL7 message.

        Args:
            message_string: Raw HL7 message string
            encoding: Encoding characters (will be detected from MSH if not provided)
        """
        self.encoding = encoding or HL7EncodingCharacters()
        self.segments: List[HL7Segment] = []

        if message_string:
            self.parse(message_string)

    def parse(self, message_string: str) -> None:
        """Parse HL7 message string.

        Args:
            message_string: Raw HL7 message
        """
        # Split into segments
        lines = message_string.strip().split("\r\n")
        if not lines:
            lines = message_string.strip().split("\n")

        # Parse MSH first to get encoding
        if lines and lines[0].startswith("MSH"):
            msh_line = lines[0]

            # Extract encoding from MSH-2
            if len(msh_line) >= 8:
                self.encoding.field_separator = msh_line[3]
                self.encoding.component_separator = msh_line[4]
                self.encoding.repetition_separator = msh_line[5]
                self.encoding.escape_character = msh_line[6]
                self.encoding.subcomponent_separator = msh_line[7]

        # Parse all segments
        for line in lines:
            if line.strip():
                segment = HL7Segment(line, self.encoding)
                self.segments.append(segment)

    def get_segment(self, segment_type: str, index: int = 0) -> Optional[HL7Segment]:
        """Get a segment by type and index.

        Args:
            segment_type: Segment type (e.g., "PID")
            index: Segment index (0-based)

        Returns:
            HL7Segment or None
        """
        count = 0
        for segment in self.segments:
            if segment.segment_id == segment_type:
                if count == index:
                    return segment
                count += 1
        return None

    def get_all_segments(self, segment_type: str) -> List[HL7Segment]:
        """Get all segments of a type.

        Args:
            segment_type: Segment type

        Returns:
            List of segments
        """
        return [s for s in self.segments if s.segment_id == segment_type]

    def add_segment(self, segment: HL7Segment) -> None:
        """Add a segment to the message.

        Args:
            segment: Segment to add
        """
        self.segments.append(segment)

    def get_message_type(self) -> Optional[str]:
        """Get the message type from MSH-9."""
        msh = self.get_segment("MSH")
        if msh:
            field = msh.get_field(9)
            if field:
                msg_type = field.get_value(0, 0, 0)
                trigger = field.get_value(0, 1, 0)
                if msg_type and trigger:
                    return f"{msg_type}^{trigger}"
        return None

    def get_message_control_id(self) -> Optional[str]:
        """Get message control ID from MSH-10."""
        msh = self.get_segment("MSH")
        if msh:
            field = msh.get_field(10)
            if field:
                return field.get_first_value()
        return None

    def to_string(self) -> str:
        """Convert message to HL7 string format."""
        segment_strings = []
        for segment in self.segments:
            segment_strings.append(segment.to_string())
        return "\r\n".join(segment_strings)

    def validate(self) -> Tuple[bool, List[str]]:
        """Validate the message structure.

        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []

        # Must have MSH segment
        if not self.segments or self.segments[0].segment_id != "MSH":
            errors.append("Message must start with MSH segment")

        # Check required fields in MSH
        msh = self.get_segment("MSH")
        if msh:
            required_fields = {
                3: "Sending Application",
                4: "Sending Facility",
                9: "Message Type",
                10: "Message Control ID",
                11: "Processing ID",
                12: "Version ID",
            }

            for field_num, field_name in required_fields.items():
                field = msh.get_field(field_num)
                if not field or not field.get_first_value():
                    errors.append(f"MSH-{field_num} ({field_name}) is required")

        # Validate message type specific requirements
        message_type = self.get_message_type()
        if message_type:
            type_errors = self._validate_message_type_requirements(message_type)
            errors.extend(type_errors)

        return len(errors) == 0, errors

    def _validate_message_type_requirements(self, message_type: str) -> List[str]:
        """Validate requirements specific to message type.

        Args:
            message_type: HL7 message type

        Returns:
            List of validation errors
        """
        errors = []

        # ADT messages must have PID
        if message_type.startswith("ADT"):
            if not self.get_segment("PID"):
                errors.append(f"{message_type} requires PID segment")

            # Most ADT messages require PV1
            if message_type not in ["ADT^A31", "ADT^A40"] and not self.get_segment(
                "PV1"
            ):
                errors.append(f"{message_type} requires PV1 segment")

        # ORM messages must have ORC and OBR
        elif message_type.startswith("ORM"):
            if not self.get_segment("ORC"):
                errors.append(f"{message_type} requires ORC segment")
            if not self.get_segment("OBR"):
                errors.append(f"{message_type} requires OBR segment")

        # ORU messages must have OBR and OBX
        elif message_type.startswith("ORU"):
            if not self.get_segment("OBR"):
                errors.append(f"{message_type} requires OBR segment")
            if not self.get_segment("OBX"):
                errors.append(f"{message_type} requires OBX segment")

        return errors


class HL7MessageBuilder:
    """Builder for creating HL7 messages."""

    def __init__(self, encoding: Optional[HL7EncodingCharacters] = None):
        """Initialize message builder.

        Args:
            encoding: Encoding characters to use
        """
        self.encoding = encoding or HL7EncodingCharacters()
        self.message = HL7Message(encoding=self.encoding)

    def add_msh(
        self,
        sending_application: str,
        sending_facility: str,
        receiving_application: str,
        receiving_facility: str,
        message_type: str,
        message_control_id: str,
        processing_id: str = "P",
        version_id: str = "2.5",
    ) -> "HL7MessageBuilder":
        """Add MSH segment.

        Args:
            sending_application: Sending application
            sending_facility: Sending facility
            receiving_application: Receiving application
            receiving_facility: Receiving facility
            message_type: Message type (e.g., "ADT^A01")
            message_control_id: Unique message ID
            processing_id: Processing ID (P=Production, T=Test)
            version_id: HL7 version

        Returns:
            Self for chaining
        """
        msh = HL7Segment(f"MSH{self.encoding.field_separator}", self.encoding)

        # MSH-2: Encoding characters
        msh.set_field(2, self.encoding.get_encoding_string())

        # MSH-3: Sending application
        msh.set_field(3, sending_application)

        # MSH-4: Sending facility
        msh.set_field(4, sending_facility)

        # MSH-5: Receiving application
        msh.set_field(5, receiving_application)

        # MSH-6: Receiving facility
        msh.set_field(6, receiving_facility)

        # MSH-7: Message date/time
        msh.set_field(7, datetime.now().strftime("%Y%m%d%H%M%S"))

        # MSH-9: Message type
        msh.set_field(9, message_type)

        # MSH-10: Message control ID
        msh.set_field(10, message_control_id)

        # MSH-11: Processing ID
        msh.set_field(11, processing_id)

        # MSH-12: Version ID
        msh.set_field(12, version_id)

        self.message.add_segment(msh)
        return self

    def add_pid(
        self,
        patient_id: str,
        patient_name: Dict[str, str],
        birth_date: Optional[str] = None,
        gender: Optional[str] = None,
        address: Optional[Dict[str, str]] = None,
        phone: Optional[str] = None,
    ) -> "HL7MessageBuilder":
        """Add PID segment.

        Args:
            patient_id: Patient identifier
            patient_name: Name components (family, given, middle, etc.)
            birth_date: Birth date (YYYYMMDD)
            gender: Gender (M/F/O/U)
            address: Address components
            phone: Phone number

        Returns:
            Self for chaining
        """
        pid = HL7Segment(f"PID{self.encoding.field_separator}", self.encoding)

        # PID-1: Set ID (sequence number)
        pid.set_field(1, "1")

        # PID-3: Patient identifier list
        pid_field = HL7Field(patient_id, self.encoding)
        pid_field.set_value(patient_id, 0, 0, 0)  # ID
        pid_field.set_value("MRN", 0, 4, 0)  # Identifier type
        pid.fields[2] = pid_field  # PID-3 is index 2

        # PID-5: Patient name
        name_field = HL7Field("", self.encoding)
        name_field.set_value(patient_name.get("family", ""), 0, 0, 0)
        name_field.set_value(patient_name.get("given", ""), 0, 1, 0)
        name_field.set_value(patient_name.get("middle", ""), 0, 2, 0)
        name_field.set_value(patient_name.get("suffix", ""), 0, 3, 0)
        name_field.set_value(patient_name.get("prefix", ""), 0, 4, 0)
        pid.fields[4] = name_field  # PID-5 is index 4

        # PID-7: Date of birth
        if birth_date:
            pid.set_field(7, birth_date)

        # PID-8: Gender
        if gender:
            pid.set_field(8, gender)

        # PID-11: Patient address
        if address:
            addr_field = HL7Field("", self.encoding)
            addr_field.set_value(address.get("street", ""), 0, 0, 0)
            addr_field.set_value(address.get("city", ""), 0, 2, 0)
            addr_field.set_value(address.get("state", ""), 0, 3, 0)
            addr_field.set_value(address.get("zip", ""), 0, 4, 0)
            addr_field.set_value(address.get("country", ""), 0, 5, 0)
            pid.fields[10] = addr_field  # PID-11 is index 10

        # PID-13: Phone number - home
        if phone:
            pid.set_field(13, phone)

        self.message.add_segment(pid)
        return self

    def add_pv1(
        self,
        patient_class: str,
        location: Optional[str] = None,
        admission_type: Optional[str] = None,
        attending_doctor: Optional[str] = None,
    ) -> "HL7MessageBuilder":
        """Add PV1 segment.

        Args:
            patient_class: Patient class (I=Inpatient, O=Outpatient, E=Emergency)
            location: Patient location
            admission_type: Admission type
            attending_doctor: Attending doctor ID

        Returns:
            Self for chaining
        """
        pv1 = HL7Segment(f"PV1{self.encoding.field_separator}", self.encoding)

        # PV1-1: Set ID
        pv1.set_field(1, "1")

        # PV1-2: Patient class
        pv1.set_field(2, patient_class)

        # PV1-3: Assigned patient location
        if location:
            pv1.set_field(3, location)

        # PV1-4: Admission type
        if admission_type:
            pv1.set_field(4, admission_type)

        # PV1-7: Attending doctor
        if attending_doctor:
            pv1.set_field(7, attending_doctor)

        # PV1-44: Admit date/time
        pv1.set_field(44, datetime.now().strftime("%Y%m%d%H%M%S"))

        self.message.add_segment(pv1)
        return self

    def build(self) -> HL7Message:
        """Build and return the message.

        Returns:
            Completed HL7Message
        """
        return self.message


# Segment class needs to be renamed to avoid conflict
class HL7Segment:
    """Represents an HL7 segment (renamed from HL7Segment in message_types)."""

    def __init__(self, segment_string: str, encoding: HL7EncodingCharacters):
        """Initialize HL7 segment.

        Args:
            segment_string: Raw segment string
            encoding: Encoding characters
        """
        self.raw_segment = segment_string
        self.encoding = encoding
        self._parse_segment()

    def _parse_segment(self) -> None:
        """Parse segment into fields."""
        # Split by field separator
        field_strings = self.raw_segment.split(self.encoding.field_separator)

        # First field is segment ID
        self.segment_id = field_strings[0]

        # Parse remaining fields
        self.fields = []
        for i, field_string in enumerate(field_strings[1:]):
            # MSH-1 is the field separator itself
            if self.segment_id == "MSH" and i == 0:
                self.fields.append(
                    HL7Field(self.encoding.field_separator, self.encoding)
                )
            else:
                self.fields.append(HL7Field(field_string, self.encoding))

    def get_field(self, field_number: int) -> Optional[HL7Field]:
        """Get a field by number (1-based).

        Args:
            field_number: Field number (1-based)

        Returns:
            HL7Field or None
        """
        index = field_number - 1
        if 0 <= index < len(self.fields):
            return self.fields[index]
        return None

    def set_field(self, field_number: int, value: str) -> None:
        """Set a field value.

        Args:
            field_number: Field number (1-based)
            value: Field value
        """
        # Extend fields list if needed
        while len(self.fields) < field_number:
            self.fields.append(HL7Field("", self.encoding))

        self.fields[field_number - 1] = HL7Field(value, self.encoding)

    def to_string(self) -> str:
        """Convert segment back to HL7 string format."""
        field_strings = [self.segment_id]

        for i, field in enumerate(self.fields):
            # Special handling for MSH-1
            if self.segment_id == "MSH" and i == 0:
                continue
            field_strings.append(field.to_string())

        return self.encoding.field_separator.join(field_strings)
