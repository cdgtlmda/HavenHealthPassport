"""HL7 Module.

This module provides comprehensive HL7 v2 message handling for healthcare
interoperability in refugee settings. Handles FHIR MessageHeader Resource
validation and conversion.
"""

from src.healthcare.fhir_validator import FHIRValidator

from .adt_messages import ADTMessageHandler
from .hl7_message import HL7Message, HL7MessageBuilder, HL7Segment
from .hl7_message_types import HL7EncodingCharacters, HL7Field, HL7MessageType
from .hl7_message_types import HL7Segment as HL7SegmentType
from .orm_messages import ORMMessageHandler
from .oru_messages import ORUMessageHandler

# FHIR resource type for this module
__fhir_resource__ = "MessageHeader"

__all__ = [
    # Message handlers
    "ADTMessageHandler",
    "ORMMessageHandler",
    "ORUMessageHandler",
    # Core classes
    "HL7Message",
    "HL7MessageBuilder",
    "HL7Segment",
    "HL7Field",
    # Types and enums
    "HL7EncodingCharacters",
    "HL7MessageType",
    "HL7SegmentType",
]


def validate_hl7_message(message: str) -> bool:
    """Validate HL7 message format.

    Args:
        message: HL7 message string

    Returns:
        True if valid HL7 message
    """
    try:
        # Check basic HL7 structure
        if not message or not message.startswith("MSH"):
            return False

        # Check for field separator
        if len(message) < 4 or message[3] != "|":
            return False

        return True
    except (AttributeError, IndexError, TypeError, ValueError):
        return False
