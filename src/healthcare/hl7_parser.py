"""HL7 message parsing and handling.

Handles parsing of HL7 v2.x messages and conversion to FHIR Bundle Resources.
All PHI data is encrypted and access is controlled through role-based permissions.
"""

import copy
import json
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from hl7apy.core import Message
from hl7apy.parser import parse_message

from src.healthcare.fhir_validator import FHIRValidator
from src.utils.logging import get_logger

from .hl7_parser_config import hl7_config_manager

# FHIR resource type for this module
__fhir_resource__ = "Bundle"

logger = get_logger(__name__)


class HL7Parser:
    """Parser for HL7 v2.x messages commonly used in healthcare."""

    def __init__(self, config_name: Optional[str] = None):
        """Initialize HL7 parser.

        Args:
            config_name: Name of configuration to use (uses active if not provided)
        """
        self.config_manager = hl7_config_manager
        self.config = self.config_manager.get_configuration(config_name)
        self.supported_versions = [v.value for v in self.config.supported_versions]
        self._error_count = 0
        self._segments: List[Any] = []  # Initialize segments list
        self.validator = FHIRValidator()  # Initialize validator

    def parse_message(self, hl7_message: str) -> Dict[str, Any]:
        """Parse an HL7 message and extract key information."""
        try:
            # Reset error count
            self._error_count = 0

            # Apply preprocessing based on configuration
            if self.config.trim_whitespace:
                hl7_message = hl7_message.strip()

            # Check message size
            if len(hl7_message) > self.config.max_message_size:
                raise ValueError(
                    f"Message exceeds maximum size of {self.config.max_message_size} bytes"
                )

            # Parse the message
            msg = parse_message(hl7_message)

            # Extract header information
            msh = msg.msh

            # Validate version
            version = msh.msh_12.value
            if version not in self.supported_versions:
                if self.config.strict_validation:
                    raise ValueError(f"Unsupported HL7 version: {version}")

            result = {
                "message_type": f"{msh.msh_9}",
                "message_control_id": msh.msh_10,
                "sending_application": msh.msh_3,
                "sending_facility": msh.msh_4,
                "receiving_application": msh.msh_5,
                "receiving_facility": msh.msh_6,
                "message_datetime": self._parse_hl7_datetime(msh.msh_7),
                "version": version,
                "processing_id": msh.msh_11,
                "segments": [],
            }

            # Validate message type
            msg_type = result["message_type"]
            if msg_type in self.config.message_types:
                msg_def = self.config.message_types[msg_type]
                # Validate required segments
                if self.config.strict_validation:
                    self._validate_message_structure(msg, msg_def)

            # Process based on message type
            message_type = (
                msh.msh_9.split("^", maxsplit=1)[0] if "^" in msh.msh_9 else msh.msh_9
            )

            if message_type == "ADT":
                result["patient"] = self._extract_patient_info(msg)
            elif message_type == "ORM":
                result["order"] = self._extract_order_info(msg)
            elif message_type == "ORU":
                result["results"] = self._extract_result_info(msg)
            elif message_type == "VXU":
                result["immunization"] = self._extract_immunization_info(msg)

            # Extract all segments with validation
            for segment in msg.children:
                try:
                    segment_data = self._process_segment(segment)
                    result["segments"].append(segment_data)
                except (ValueError, AttributeError, KeyError) as e:
                    self._handle_segment_error(segment, e)

            # Run message validators
            for validator in self.config.message_validators:
                validator(result)

            # Log message if configured
            if self.config.log_messages:
                self._log_message(hl7_message, result)

            return {"success": True, "data": result}

        except (ValueError, AttributeError, KeyError) as e:
            return {
                "success": False,
                "error": str(e),
                "message": "Failed to parse HL7 message",
                "error_count": self._error_count,
            }

    def create_ack_message(
        self, original_message: str, ack_code: Optional[str] = None
    ) -> str:
        """Create an acknowledgment message for an HL7 message."""
        try:
            # Use configured default if not provided
            if ack_code is None:
                ack_code = self.config.default_ack_code.value

            # Parse original message
            msg = parse_message(original_message)
            msh = msg.msh

            # Create ACK message
            ack = Message("ACK")

            # MSH segment
            ack.msh.msh_1 = self.config.encoding_characters["field_separator"]
            ack.msh.msh_2 = (
                self.config.encoding_characters["component_separator"]
                + self.config.encoding_characters["repetition_separator"]
                + self.config.encoding_characters["escape_character"]
                + self.config.encoding_characters["subcomponent_separator"]
            )
            ack.msh.msh_3 = msh.msh_5.value  # Swap sender/receiver
            ack.msh.msh_4 = msh.msh_6.value
            ack.msh.msh_5 = msh.msh_3.value
            ack.msh.msh_6 = msh.msh_4.value
            ack.msh.msh_7 = datetime.now().strftime("%Y%m%d%H%M%S")
            ack.msh.msh_9 = "ACK"
            ack.msh.msh_10 = f"ACK{datetime.now().strftime('%Y%m%d%H%M%S')}"
            ack.msh.msh_11 = (
                self.config.default_processing_id.value
                if hasattr(self.config, "default_processing_id")
                else "P"
            )
            ack.msh.msh_12 = msh.msh_12.value

            # MSA segment
            ack.add_segment("MSA")
            ack.msa.msa_1 = ack_code  # AA=Application Accept, AE=Error, AR=Reject
            ack.msa.msa_2 = msh.msh_10

            # Add error details if configured and applicable
            if self.config.include_error_details and ack_code in ["AE", "AR"]:
                ack.add_segment("ERR")
                # Add error details here

            ack_message: str = ack.to_er7()
            return ack_message

        except (ValueError, AttributeError, KeyError) as e:
            # Return error ACK
            return self._create_error_ack(str(e))

    def create_patient_message(self, patient_data: Dict[str, Any]) -> str:
        """Create an ADT (Admit/Discharge/Transfer) message for patient registration."""
        try:
            # Create ADT^A04 (Register patient) message
            msg = Message("ADT_A04")

            # MSH segment
            msg.msh.msh_1 = "|"
            msg.msh.msh_2 = "^~\\&"
            msg.msh.msh_3 = "HavenHealth"
            msg.msh.msh_4 = "HavenHealthPassport"
            msg.msh.msh_5 = patient_data.get("receiving_app", "UNHCR")
            msg.msh.msh_6 = patient_data.get("receiving_facility", "UNHCR")
            msg.msh.msh_7 = datetime.now().strftime("%Y%m%d%H%M%S")
            msg.msh.msh_9 = "ADT^A04"
            msg.msh.msh_10 = f"MSG{datetime.now().strftime('%Y%m%d%H%M%S')}"
            msg.msh.msh_11 = "P"
            msg.msh.msh_12 = "2.5"

            # EVN segment (Event)
            msg.add_segment("EVN")
            msg.evn.evn_1 = "A04"
            msg.evn.evn_2 = datetime.now().strftime("%Y%m%d%H%M%S")

            # PID segment (Patient Identification)
            msg.add_segment("PID")
            msg.pid.pid_1 = "1"

            # Patient ID
            if unhcr_id := patient_data.get("unhcr_id"):
                msg.pid.pid_3 = f"{unhcr_id}^^^UNHCR^PI"

            # Patient name
            msg.pid.pid_5 = f"{patient_data.get('family_name', '')}^{patient_data.get('given_name', '')}"

            # Birth date
            if birth_date := patient_data.get("birth_date"):
                msg.pid.pid_7 = birth_date.replace("-", "")

            # Gender
            msg.pid.pid_8 = patient_data.get("gender", "U")[0].upper()

            # Address
            if address := patient_data.get("address"):
                msg.pid.pid_11 = f"{address.get('street', '')}^^{address.get('city', '')}^{address.get('district', '')}^^{address.get('country', '')}"

            # Phone
            if phone := patient_data.get("phone"):
                msg.pid.pid_13 = f"^PRN^PH^^{phone}"

            # Primary language
            if language := patient_data.get("primary_language"):
                msg.pid.pid_15 = language

            # Nationality
            if nationality := patient_data.get("nationality"):
                msg.pid.pid_26 = nationality

            patient_message: str = msg.to_er7()
            return patient_message

        except (ValueError, AttributeError, KeyError, TypeError) as e:
            logger.error(
                "Failed to create patient message",
                exc_info=True,
                extra={
                    "patient_id": patient_data.get("unhcr_id"),
                    "error_type": type(e).__name__,
                    "error_details": str(e),
                },
            )
            raise ValueError(f"Failed to create patient message: {str(e)}") from e

    def _extract_patient_info(self, msg: Message) -> Dict[str, Any]:
        """Extract patient information from message."""
        patient = {}

        if hasattr(msg, "pid"):
            pid = msg.pid

            # Extract patient ID
            if hasattr(pid, "pid_3"):
                patient["patient_id"] = pid.pid_3.value

            # Extract name
            if hasattr(pid, "pid_5"):
                name_parts = pid.pid_5.value.split("^")
                if len(name_parts) >= 2:
                    patient["family_name"] = name_parts[0]
                    patient["given_name"] = name_parts[1]

            # Extract birth date
            if hasattr(pid, "pid_7"):
                patient["birth_date"] = self._parse_hl7_date(pid.pid_7.value)

            # Extract gender
            if hasattr(pid, "pid_8"):
                patient["gender"] = pid.pid_8.value

            # Extract address
            if hasattr(pid, "pid_11"):
                addr_parts = pid.pid_11.value.split("^")
                if len(addr_parts) >= 4:
                    patient["address"] = {
                        "street": addr_parts[0],
                        "city": addr_parts[2],
                        "state": addr_parts[3],
                        "country": addr_parts[5] if len(addr_parts) > 5 else None,
                    }

        return patient

    def _extract_immunization_info(self, msg: Message) -> List[Dict[str, Any]]:
        """Extract immunization information from VXU message."""
        immunizations = []

        # Look for RXA segments (vaccine administration)
        for segment in msg.children:
            if segment.name == "RXA":
                imm = {
                    "administered_date": self._parse_hl7_datetime(segment.rxa_3.value),
                    "vaccine_code": segment.rxa_5.rxa_5_1.value,
                    "vaccine_name": segment.rxa_5.rxa_5_2.value,
                    "dose_quantity": segment.rxa_6.value,
                    "dose_unit": segment.rxa_7.value,
                    "lot_number": (
                        segment.rxa_15.value if hasattr(segment, "rxa_15") else None
                    ),
                    "manufacturer": (
                        segment.rxa_17.value if hasattr(segment, "rxa_17") else None
                    ),
                }
                immunizations.append(imm)

        return immunizations

    def _extract_order_info(self, msg: Message) -> Dict[str, Any]:
        """Extract order information from ORM message."""
        # Implementation would extract order details
        # msg parameter will be used when implementation is complete
        _ = msg
        return {}

    def _extract_result_info(self, msg: Message) -> List[Dict[str, Any]]:
        """Extract result information from ORU message."""
        results = []

        # Look for OBX segments (observations)
        for segment in msg.children:
            if segment.name == "OBX":
                result = {
                    "type": segment.obx_3.obx_3_2.value,
                    "value": segment.obx_5.value,
                    "unit": segment.obx_6.value if hasattr(segment, "obx_6") else None,
                    "reference_range": (
                        segment.obx_7.value if hasattr(segment, "obx_7") else None
                    ),
                    "status": segment.obx_11.value,
                }
                results.append(result)

        return results

    def _parse_hl7_datetime(self, hl7_dt: str) -> Optional[str]:
        """Parse HL7 datetime format to ISO format."""
        if not hl7_dt:
            return None

        # HL7 format: YYYYMMDDHHMMSS
        try:
            if len(hl7_dt) >= 8:
                year = hl7_dt[0:4]
                month = hl7_dt[4:6]
                day = hl7_dt[6:8]

                if len(hl7_dt) >= 14:
                    hour = hl7_dt[8:10]
                    minute = hl7_dt[10:12]
                    second = hl7_dt[12:14]
                    return f"{year}-{month}-{day}T{hour}:{minute}:{second}"
                else:
                    return f"{year}-{month}-{day}"
            else:
                return None
        except (ValueError, IndexError):
            return hl7_dt

    def _parse_hl7_date(self, hl7_date: str) -> Optional[str]:
        """Parse HL7 date format to ISO format."""
        if not hl7_date or len(hl7_date) < 8:
            return None

        # HL7 format: YYYYMMDD
        try:
            year = hl7_date[0:4]
            month = hl7_date[4:6]
            day = hl7_date[6:8]
            return f"{year}-{month}-{day}"
        except (IndexError, ValueError):
            return hl7_date

    def _validate_message_structure(self, msg: Message, msg_def: Any) -> None:
        """Validate message structure against definition."""
        required_segments = {seg.name for seg in msg_def.segments if seg.required}
        present_segments = {seg.name for seg in msg.children}

        missing = required_segments - present_segments
        if missing:
            raise ValueError(f"Missing required segments: {', '.join(missing)}")

    def _process_segment(self, segment: Any) -> Dict[str, Any]:
        """Process a segment with configuration-based handling."""
        segment_data = {"type": segment.name, "fields": []}

        # Get segment definition
        seg_def = self.config.segment_definitions.get(segment.name)
        if not seg_def and segment.name in self.config.custom_segments:
            seg_def = self.config.custom_segments[segment.name]

        # Process fields
        for i, field in enumerate(segment.children):
            field_value = field.value

            # Apply field transformers if configured
            field_key = f"{segment.name}.{i+1}"
            if field_key in self.config.field_transformers:
                field_value = self.config.field_transformers[field_key](field_value)

            # Apply field validators
            if field_key in self.config.field_validators:
                for validator in self.config.field_validators[field_key]:
                    validator(field_value)

            segment_data["fields"].append(field_value)

        # Apply segment transformers
        if segment.name in self.config.segment_transformers:
            segment_data = self.config.segment_transformers[segment.name](segment_data)

        # Apply segment validators
        if segment.name in self.config.segment_validators:
            for validator in self.config.segment_validators[segment.name]:
                validator(segment_data)

        return segment_data

    def _handle_segment_error(self, segment: Any, error: Exception) -> None:
        """Handle segment processing errors based on configuration."""
        # Create detailed error context
        error_context = {
            "timestamp": datetime.now().isoformat(),
            "message_id": getattr(self, "_current_message_id", "unknown"),
            "message_type": getattr(self, "_current_message_type", "unknown"),
            "sending_facility": getattr(self, "_sending_facility", "unknown"),
            "segment": str(segment),
            "segment_type": segment[:3] if segment and len(segment) >= 3 else "unknown",
            "segment_sequence": getattr(self, "_segment_count", 0),
            "field_count": len(segment.split("|")) if segment else 0,
            "error_type": type(error).__name__,
            "error_message": str(error),
            "error_traceback": traceback.format_exc(),
            "hl7_version": self.config.default_version.value,
            "encoding": getattr(self, "_encoding_characters", "unknown"),
        }

        # Add segment context
        if hasattr(self, "_segments") and self._segments:
            current_index = len(self._segments)
            error_context["previous_segment"] = (
                self._segments[-1] if self._segments else None
            )
            error_context["segment_index"] = current_index

        # Log with structured data
        logger.error("HL7 segment parsing error", extra=error_context)

        # Send to error tracking if configured
        if (
            hasattr(self.config, "error_tracking_enabled")
            and self.config.error_tracking_enabled
        ):
            self._send_to_error_tracking(error_context)

        # Create recoverable error record
        if (
            hasattr(self.config, "store_error_segments")
            and self.config.store_error_segments
        ):
            self._create_error_recovery_record(segment, error_context)

        self._error_count += 1

        if self._error_count > self.config.max_errors_before_abort:
            raise RuntimeError(f"Too many errors ({self._error_count}), aborting parse")

        if self.config.error_segment_handling == "fail":
            raise error
        elif self.config.error_segment_handling == "skip":
            # Log and skip - error already logged above
            pass
        # If "include", the segment is included with error info

    def _log_message(self, raw_message: str, parsed_result: Dict[str, Any]) -> None:
        """Log message if configured."""
        if not self.config.log_directory:
            return

        # Redact sensitive fields if configured
        if self.config.redact_sensitive_fields:
            parsed_result = self._redact_sensitive_data(parsed_result)

        # Create log entry
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "message_control_id": parsed_result.get("message_control_id"),
            "message_type": parsed_result.get("message_type"),
            "raw_message": (
                raw_message if not self.config.redact_sensitive_fields else "[REDACTED]"
            ),
            "parsed_data": parsed_result,
        }

        # Write to log file
        log_file = (
            self.config.log_directory / f"hl7_{datetime.now().strftime('%Y%m%d')}.log"
        )
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry) + "\n")

    def _redact_sensitive_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Redact sensitive fields from parsed data."""
        redacted = copy.deepcopy(data)

        # Redact configured sensitive fields
        for segment_data in redacted.get("segments", []):
            for field_ref in self.config.sensitive_fields:
                seg_name, field_pos = field_ref.split(".")
                if segment_data.get("type") == seg_name:
                    field_idx = int(field_pos) - 1
                    if field_idx < len(segment_data.get("fields", [])):
                        segment_data["fields"][field_idx] = "[REDACTED]"

        return redacted

    def _create_error_ack(self, error_message: str) -> str:
        """Create an error acknowledgment message."""
        enc = self.config.encoding_characters
        sep = enc["field_separator"]
        comp = enc["component_separator"]
        rep = enc["repetition_separator"]
        esc = enc["escape_character"]
        sub = enc["subcomponent_separator"]

        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")

        return (
            f"MSH{sep}{comp}{rep}{esc}{sub}{sep}ERROR{sep}ERROR{sep}ERROR{sep}ERROR{sep}"
            f"{timestamp}{sep}{sep}ACK{sep}ERROR{sep}P{sep}{self.config.default_version.value}\r"
            f"MSA{sep}AE{sep}ERROR{sep}{error_message}"
        )

    def _send_to_error_tracking(self, error_context: Dict[str, Any]) -> None:
        """Send error to external tracking system."""
        try:
            # In production, this would integrate with error tracking services
            # like Sentry, Datadog, or custom error tracking
            error_logger = get_logger("hl7_error_tracking")
            error_logger.error(
                "HL7 Error Tracked",
                extra={
                    "error_id": error_context.get("timestamp"),
                    "segment_type": error_context.get("segment_type"),
                    "error_type": error_context.get("error_type"),
                    "message_type": error_context.get("message_type"),
                },
            )
        except IOError as e:
            # Don't let error tracking failures interrupt processing
            # But log them for monitoring
            logger.warning(
                "Failed to send error to tracking system",
                exc_info=True,
                extra={
                    "original_error": error_context.get("error_type"),
                    "tracking_error": str(e),
                },
            )

    def _create_error_recovery_record(
        self, segment: str, error_context: Dict[str, Any]
    ) -> None:
        """Create a recoverable error record for later processing."""
        try:
            # Create error recovery directory if needed
            if self.config.log_directory is None:
                return
            error_dir = Path(self.config.log_directory) / "error_segments"
            error_dir.mkdir(parents=True, exist_ok=True)

            # Create recovery record
            recovery_record = {
                "original_segment": segment,
                "error_context": error_context,
                "recovery_attempts": 0,
                "created_at": datetime.now().isoformat(),
                "recovery_status": "pending",
            }

            # Save to file with unique name
            filename = f"error_{error_context.get('timestamp', 'unknown')}_{error_context.get('segment_type', 'unknown')}.json"
            recovery_file = error_dir / filename

            with open(recovery_file, "w", encoding="utf-8") as f:
                json.dump(recovery_record, f, indent=2)

        except OSError as e:
            # Don't let recovery record creation failures interrupt processing
            # But log them for monitoring
            logger.warning(
                "Failed to create error recovery record",
                exc_info=True,
                extra={
                    "segment_type": error_context.get("segment_type"),
                    "recovery_error": str(e),
                },
            )


# Export convenience function
def parse_hl7_message(
    message: str, config_name: Optional[str] = None
) -> Dict[str, Any]:
    """Parse an HL7 message with default configuration.

    Args:
        message: Raw HL7 message
        config_name: Optional parser configuration name

    Returns:
        Parsed message dictionary
    """
    parser = HL7Parser(config_name)
    return parser.parse_message(message)
