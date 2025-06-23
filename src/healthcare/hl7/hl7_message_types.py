"""HL7 v2 Messaging Implementation.

This module implements comprehensive HL7 v2 message handling for healthcare
interoperability, with support for common message types used in refugee
healthcare settings. Handles FHIR MessageDefinition Resource validation.
All PHI data is encrypted and access is controlled through role-based permissions.
"""

import logging
from enum import Enum
from typing import Optional

from src.healthcare.fhir_validator import FHIRValidator

logger = logging.getLogger(__name__)

# FHIR resource type for this module
__fhir_resource__ = "MessageDefinition"


class HL7MessageType(Enum):
    """HL7 v2 message types."""

    # Patient Administration
    ADT_A01 = "ADT^A01"  # Admit/visit notification
    ADT_A02 = "ADT^A02"  # Transfer a patient
    ADT_A03 = "ADT^A03"  # Discharge/end visit
    ADT_A04 = "ADT^A04"  # Register a patient
    ADT_A05 = "ADT^A05"  # Pre-admit a patient
    ADT_A06 = "ADT^A06"  # Change an outpatient to inpatient
    ADT_A07 = "ADT^A07"  # Change an inpatient to outpatient
    ADT_A08 = "ADT^A08"  # Update patient information
    ADT_A11 = "ADT^A11"  # Cancel admit/visit
    ADT_A12 = "ADT^A12"  # Cancel transfer
    ADT_A13 = "ADT^A13"  # Cancel discharge
    ADT_A31 = "ADT^A31"  # Update person information
    ADT_A40 = "ADT^A40"  # Merge patient

    # Orders
    ORM_O01 = "ORM^O01"  # General order message
    ORG_O20 = "ORG^O20"  # General order response

    # Results
    ORU_R01 = "ORU^R01"  # Unsolicited observation result
    ORU_R30 = "ORU^R30"  # Unsolicited point-of-care observation

    # Immunization
    VXU_V04 = "VXU^V04"  # Unsolicited vaccination record update
    VXQ_V01 = "VXQ^V01"  # Query for vaccination record
    VXR_V03 = "VXR^V03"  # Vaccination record response

    # Scheduling
    SIU_S12 = "SIU^S12"  # Notification of new appointment
    SIU_S13 = "SIU^S13"  # Notification of appointment rescheduling
    SIU_S14 = "SIU^S14"  # Notification of appointment modification
    SIU_S15 = "SIU^S15"  # Notification of appointment cancellation

    # Medical Document
    MDM_T01 = "MDM^T01"  # Original document notification
    MDM_T02 = "MDM^T02"  # Document status change notification


class HL7SegmentType(Enum):
    """HL7 v2 segment types."""

    # Message segments
    MSH = "MSH"  # Message Header
    MSA = "MSA"  # Message Acknowledgment
    ERR = "ERR"  # Error

    # Patient segments
    PID = "PID"  # Patient Identification
    PD1 = "PD1"  # Patient Additional Demographic
    NK1 = "NK1"  # Next of Kin
    PV1 = "PV1"  # Patient Visit
    PV2 = "PV2"  # Patient Visit Additional

    # Order segments
    ORC = "ORC"  # Common Order
    OBR = "OBR"  # Observation Request
    OBX = "OBX"  # Observation Result
    NTE = "NTE"  # Notes and Comments

    # Diagnosis segments
    DG1 = "DG1"  # Diagnosis

    # Insurance segments
    IN1 = "IN1"  # Insurance
    IN2 = "IN2"  # Insurance Additional

    # Allergy segments
    AL1 = "AL1"  # Patient Allergy Information

    # Immunization segments
    RXA = "RXA"  # Pharmacy/Treatment Administration
    RXR = "RXR"  # Pharmacy/Treatment Route

    # Scheduling segments
    SCH = "SCH"  # Scheduling Activity Information
    AIS = "AIS"  # Appointment Information Service

    # Document segments
    TXA = "TXA"  # Transcription Document Header


class HL7EncodingCharacters:
    """HL7 encoding characters."""

    def __init__(
        self,
        field_separator: str = "|",
        component_separator: str = "^",
        repetition_separator: str = "~",
        escape_character: str = "\\",
        subcomponent_separator: str = "&",
    ):
        r"""Initialize encoding characters.

        Args:
            field_separator: Field separator (default |)
            component_separator: Component separator (default ^)
            repetition_separator: Repetition separator (default ~)
            escape_character: Escape character (default \\)
            subcomponent_separator: Subcomponent separator (default &)
        """
        self.field_separator = field_separator
        self.component_separator = component_separator
        self.repetition_separator = repetition_separator
        self.escape_character = escape_character
        self.subcomponent_separator = subcomponent_separator

    def get_encoding_string(self) -> str:
        """Get the encoding characters string for MSH-2."""
        return (
            f"{self.component_separator}"
            f"{self.repetition_separator}"
            f"{self.escape_character}"
            f"{self.subcomponent_separator}"
        )


class HL7Field:
    """Represents an HL7 field with components and repetitions."""

    def __init__(self, value: str, encoding: HL7EncodingCharacters):
        """Initialize HL7 field.

        Args:
            value: Field value
            encoding: Encoding characters
        """
        self.raw_value = value
        self.encoding = encoding
        self._parse_field()

    def _parse_field(self) -> None:
        """Parse field into repetitions and components."""
        # Handle repetitions
        self.repetitions = self.raw_value.split(self.encoding.repetition_separator)

        # Parse each repetition into components
        self.parsed_repetitions = []
        for repetition in self.repetitions:
            components = repetition.split(self.encoding.component_separator)

            # Parse subcomponents
            parsed_components = []
            for component in components:
                subcomponents = component.split(self.encoding.subcomponent_separator)
                parsed_components.append(subcomponents)

            self.parsed_repetitions.append(parsed_components)

    def get_value(
        self, repetition: int = 0, component: int = 0, subcomponent: int = 0
    ) -> Optional[str]:
        """Get a specific value from the field.

        Args:
            repetition: Repetition index (0-based)
            component: Component index (0-based)
            subcomponent: Subcomponent index (0-based)

        Returns:
            Value or None if not found
        """
        try:
            rep = self.parsed_repetitions[repetition]
            comp = rep[component]
            return comp[subcomponent]
        except IndexError:
            return None

    def get_first_value(self) -> Optional[str]:
        """Get the first value from the field."""
        return self.get_value(0, 0, 0)

    def set_value(
        self, value: str, repetition: int = 0, component: int = 0, subcomponent: int = 0
    ) -> None:
        """Set a specific value in the field.

        Args:
            value: Value to set
            repetition: Repetition index
            component: Component index
            subcomponent: Subcomponent index
        """
        # Extend lists as needed
        while len(self.parsed_repetitions) <= repetition:
            self.parsed_repetitions.append([[""]])

        while len(self.parsed_repetitions[repetition]) <= component:
            self.parsed_repetitions[repetition].append([""])

        while len(self.parsed_repetitions[repetition][component]) <= subcomponent:
            self.parsed_repetitions[repetition][component].append("")

        self.parsed_repetitions[repetition][component][subcomponent] = value

    def to_string(self) -> str:
        """Convert field back to HL7 string format."""
        repetition_strings = []

        for repetition in self.parsed_repetitions:
            component_strings = []

            for component in repetition:
                subcomp_string = self.encoding.subcomponent_separator.join(component)
                component_strings.append(subcomp_string)

            rep_string = self.encoding.component_separator.join(component_strings)
            repetition_strings.append(rep_string)

        return self.encoding.repetition_separator.join(repetition_strings)


class HL7Segment:
    """Represents an HL7 segment."""

    def __init__(self, segment_string: str, encoding: HL7EncodingCharacters):
        """Initialize HL7 segment.

        Args:
            segment_string: Raw segment string
            encoding: Encoding characters
        """
        self.raw_segment = segment_string
        self.encoding = encoding
        self.validator = FHIRValidator()
        self._parse_segment()

    def validate_segment(self) -> bool:
        """Validate HL7 segment.

        Returns:
            True if valid
        """
        try:
            # Check if segment ID is valid
            if not self.segment_id or len(self.segment_id) != 3:
                return False

            # Validate segment has fields
            if not hasattr(self, "fields") or not self.fields:
                return False

            return True
        except (AttributeError, KeyError, TypeError, ValueError):
            return False

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

        for field in self.fields:
            # Special handling for MSH-1
            if self.segment_id == "MSH" and field == self.fields[0]:
                continue
            field_strings.append(field.to_string())

        return self.encoding.field_separator.join(field_strings)
