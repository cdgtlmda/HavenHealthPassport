"""HL7 Parser Module.

Simple parser for HL7 messages
"""

from typing import Any, Dict, List, Optional

# FHIR resource type for this module
__fhir_resource__ = "Bundle"


class HL7Parser:
    """Basic HL7 message parser."""

    def __init__(self) -> None:
        """Initialize HL7 parser."""
        self.segments: List[Dict[str, Any]] = []

    def validate_message(self, message: str) -> Dict[str, Any]:
        """Validate HL7 message format.

        Args:
            message: HL7 message to validate

        Returns:
            Validation result with 'valid', 'errors', and 'warnings' keys
        """
        errors = []
        warnings: List[str] = []

        if not message:
            errors.append("Empty message")
            return {"valid": False, "errors": errors, "warnings": warnings}

        # Check for MSH segment
        if not message.startswith("MSH"):
            errors.append("Message must start with MSH segment")

        # Check field separator
        if len(message) > 3 and message[3] != "|":
            errors.append("Invalid field separator")

        return {"valid": len(errors) == 0, "errors": errors, "warnings": warnings}

    def parse(self, message: str) -> Optional["ParsedMessage"]:
        """Parse an HL7 message."""
        if not message:
            return None

        lines = message.strip().split("\r")
        segments = []

        for line in lines:
            if line:
                fields = line.split("|")
                segments.append({"type": fields[0] if fields else "", "fields": fields})

        result = ParsedMessage()
        result.segments = segments
        return result

    def get_field(self, segment_type: str, field_index: int) -> Optional[str]:
        """Get a specific field from a segment."""
        for segment in self.segments:
            if (
                segment.get("type") == segment_type
                and len(segment.get("fields", [])) > field_index
            ):
                field_value = segment["fields"][field_index]
                return str(field_value) if field_value is not None else None
        return None

    async def transform_to_fhir(
        self, parsed_message: "ParsedMessage"
    ) -> Optional[Dict[str, Any]]:
        """Transform parsed HL7 message to FHIR Bundle."""
        if not parsed_message or not parsed_message.segments:
            return None

        bundle: Dict[str, Any] = {
            "resourceType": "Bundle",
            "type": "collection",
            "entry": [],
        }

        # Simple transformation logic
        for segment in parsed_message.segments:
            if segment.get("type") == "PID":
                # Create a Patient resource
                fields = segment.get("fields", [])
                if len(fields) > 5:
                    patient = {
                        "resourceType": "Patient",
                        "id": fields[2] if len(fields) > 2 else "unknown",
                        "name": [
                            {
                                "family": (
                                    fields[5].split("^")[0]
                                    if "^" in fields[5]
                                    else fields[5]
                                ),
                                "given": (
                                    [fields[5].split("^")[1]]
                                    if "^" in fields[5]
                                    and len(fields[5].split("^")) > 1
                                    else []
                                ),
                            }
                        ],
                    }
                    bundle["entry"].append({"resource": patient})

        return bundle


class ParsedMessage:
    """Represents a parsed HL7 message."""

    def __init__(self) -> None:
        """Initialize parsed message."""
        self.segments: List[Dict[str, Any]] = []

    def get_field(self, segment_type: str, field_index: int) -> Optional[str]:
        """Get a field from the parsed message."""
        for segment in self.segments:
            if segment.get("type") == segment_type:
                fields = segment.get("fields", [])
                if len(fields) > field_index:
                    field_value = fields[field_index]
                    return str(field_value) if field_value is not None else None
        return None
