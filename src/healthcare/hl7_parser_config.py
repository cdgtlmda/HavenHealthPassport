"""HL7 Parser Configuration Module.

This module provides comprehensive configuration for HL7 v2.x message parsing,
including segment handlers, field mappings, encoding rules, and error processing.
Handles FHIR Resource conversion and validation.

COMPLIANCE NOTE: This module processes PHI data including patient identifiers
(PID segments), visit information (PV1), and clinical data (OBR/OBX). All PHI
must be encrypted at rest and in transit. Access control is enforced through
the HIPAA compliance framework. Sensitive fields are automatically redacted
in logs as configured in the sensitive_fields set.
"""

import copy
import json
import logging
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set

# Import access control for PHI protection
# Note: Access control is enforced at the API layer

# FHIR resource type for this module
__fhir_resource__ = "MessageHeader"

logger = logging.getLogger(__name__)


class HL7Version(Enum):
    """Supported HL7 versions."""

    V2_1 = "2.1"
    V2_2 = "2.2"
    V2_3 = "2.3"
    V2_3_1 = "2.3.1"
    V2_4 = "2.4"
    V2_5 = "2.5"
    V2_5_1 = "2.5.1"
    V2_6 = "2.6"
    V2_7 = "2.7"
    V2_7_1 = "2.7.1"
    V2_8 = "2.8"
    V2_8_1 = "2.8.1"
    V2_8_2 = "2.8.2"


class EncodingCharacters(Enum):
    """HL7 encoding characters."""

    FIELD_SEPARATOR = "|"
    COMPONENT_SEPARATOR = "^"
    REPETITION_SEPARATOR = "~"
    ESCAPE_CHARACTER = "\\"
    SUBCOMPONENT_SEPARATOR = "&"


class AcknowledgmentCode(Enum):
    """HL7 acknowledgment codes."""

    AA = "AA"  # Application Accept
    AE = "AE"  # Application Error
    AR = "AR"  # Application Reject
    CA = "CA"  # Commit Accept
    CE = "CE"  # Commit Error
    CR = "CR"  # Commit Reject


class ProcessingID(Enum):
    """HL7 processing ID values."""

    P = "P"  # Production
    T = "T"  # Training
    D = "D"  # Debugging


@dataclass
class SegmentDefinition:
    """Definition of an HL7 segment."""

    name: str
    description: str
    required: bool = True
    repeatable: bool = False
    fields: List[Dict[str, Any]] = field(default_factory=list)
    validation_rules: List[Callable] = field(default_factory=list)


@dataclass
class MessageTypeDefinition:
    """Definition of an HL7 message type."""

    message_type: str
    trigger_event: str
    description: str
    segments: List[SegmentDefinition]
    acknowledgment_required: bool = True
    response_message_type: Optional[str] = None


@dataclass
class FieldMapping:
    """Mapping configuration for HL7 fields."""

    segment: str
    field_position: int
    field_name: str
    target_property: str
    data_type: str
    required: bool = False
    default_value: Optional[Any] = None
    transform_function: Optional[Callable] = None
    validation_function: Optional[Callable] = None


@dataclass
class ParserConfiguration:
    """Main HL7 parser configuration."""

    # Version settings
    default_version: HL7Version = HL7Version.V2_5_1
    supported_versions: List[HL7Version] = field(
        default_factory=lambda: [
            HL7Version.V2_3,
            HL7Version.V2_3_1,
            HL7Version.V2_4,
            HL7Version.V2_5,
            HL7Version.V2_5_1,
            HL7Version.V2_6,
            HL7Version.V2_7,
            HL7Version.V2_7_1,
        ]
    )

    # Encoding settings
    encoding_characters: Dict[str, str] = field(
        default_factory=lambda: {
            "field_separator": "|",
            "component_separator": "^",
            "repetition_separator": "~",
            "escape_character": "\\",
            "subcomponent_separator": "&",
        }
    )

    # Character encoding
    input_encoding: str = "utf-8"
    output_encoding: str = "utf-8"

    # Message handling
    strict_validation: bool = True
    allow_unknown_segments: bool = False
    ignore_empty_fields: bool = True
    trim_whitespace: bool = True

    # Error handling
    continue_on_error: bool = False
    max_errors_before_abort: int = 10
    error_segment_handling: str = "skip"  # skip, include, fail

    # Performance settings
    batch_size: int = 100
    max_message_size: int = 1048576  # 1MB
    parse_timeout_seconds: int = 30

    # Acknowledgment settings
    auto_acknowledge: bool = True
    default_ack_code: AcknowledgmentCode = AcknowledgmentCode.AA
    include_error_details: bool = True

    # Segment settings
    segment_definitions: Dict[str, SegmentDefinition] = field(default_factory=dict)
    custom_segments: Dict[str, SegmentDefinition] = field(default_factory=dict)

    # Message type settings
    message_types: Dict[str, MessageTypeDefinition] = field(default_factory=dict)

    # Field mappings
    field_mappings: Dict[str, List[FieldMapping]] = field(default_factory=dict)

    # Transformations
    field_transformers: Dict[str, Callable] = field(default_factory=dict)
    segment_transformers: Dict[str, Callable] = field(default_factory=dict)

    # Validation rules
    field_validators: Dict[str, List[Callable]] = field(default_factory=dict)
    segment_validators: Dict[str, List[Callable]] = field(default_factory=dict)
    message_validators: List[Callable] = field(default_factory=list)

    # Routing rules
    routing_rules: List[Dict[str, Any]] = field(default_factory=list)

    # Logging
    log_messages: bool = True
    log_directory: Optional[Path] = None
    redact_sensitive_fields: bool = True
    sensitive_fields: Set[str] = field(
        default_factory=lambda: {
            "PID.3",
            "PID.4",
            "PID.5",
            "PID.19",  # Patient identifiers
            "PV1.19",
            "IN1.2",
            "IN1.36",  # Insurance/visit info
        }
    )


class HL7ConfigurationBuilder:
    """Builder for creating HL7 parser configurations."""

    def __init__(self) -> None:
        """Initialize configuration builder."""
        self.config = ParserConfiguration()
        self._initialize_standard_segments()
        self._initialize_standard_message_types()
        self._initialize_standard_field_mappings()

    def _initialize_standard_segments(self) -> None:
        """Initialize standard HL7 segment definitions."""
        # MSH - Message Header
        self.config.segment_definitions["MSH"] = SegmentDefinition(
            name="MSH",
            description="Message Header",
            required=True,
            repeatable=False,
            fields=[
                {"position": 1, "name": "field_separator", "required": True},
                {"position": 2, "name": "encoding_characters", "required": True},
                {"position": 3, "name": "sending_application", "required": True},
                {"position": 4, "name": "sending_facility", "required": True},
                {"position": 5, "name": "receiving_application", "required": True},
                {"position": 6, "name": "receiving_facility", "required": True},
                {"position": 7, "name": "message_datetime", "required": True},
                {"position": 8, "name": "security", "required": False},
                {"position": 9, "name": "message_type", "required": True},
                {"position": 10, "name": "message_control_id", "required": True},
                {"position": 11, "name": "processing_id", "required": True},
                {"position": 12, "name": "version_id", "required": True},
            ],
        )

        # PID - Patient Identification
        self.config.segment_definitions["PID"] = SegmentDefinition(
            name="PID",
            description="Patient Identification",
            required=False,
            repeatable=False,
            fields=[
                {"position": 1, "name": "set_id", "required": False},
                {"position": 2, "name": "patient_id", "required": False},
                {"position": 3, "name": "patient_identifier_list", "required": True},
                {"position": 4, "name": "alternate_patient_id", "required": False},
                {"position": 5, "name": "patient_name", "required": True},
                {"position": 6, "name": "mother_maiden_name", "required": False},
                {"position": 7, "name": "date_of_birth", "required": False},
                {"position": 8, "name": "sex", "required": False},
                {"position": 9, "name": "patient_alias", "required": False},
                {"position": 10, "name": "race", "required": False},
                {"position": 11, "name": "patient_address", "required": False},
                {"position": 12, "name": "country_code", "required": False},
                {"position": 13, "name": "phone_home", "required": False},
                {"position": 14, "name": "phone_business", "required": False},
                {"position": 15, "name": "primary_language", "required": False},
                {"position": 16, "name": "marital_status", "required": False},
                {"position": 17, "name": "religion", "required": False},
                {"position": 18, "name": "patient_account_number", "required": False},
                {"position": 19, "name": "ssn", "required": False},
            ],
        )

        # PV1 - Patient Visit
        self.config.segment_definitions["PV1"] = SegmentDefinition(
            name="PV1",
            description="Patient Visit",
            required=False,
            repeatable=False,
            fields=[
                {"position": 1, "name": "set_id", "required": False},
                {"position": 2, "name": "patient_class", "required": True},
                {"position": 3, "name": "assigned_patient_location", "required": False},
                {"position": 4, "name": "admission_type", "required": False},
                {"position": 5, "name": "preadmit_number", "required": False},
                {"position": 6, "name": "prior_patient_location", "required": False},
                {"position": 7, "name": "attending_doctor", "required": False},
                {"position": 8, "name": "referring_doctor", "required": False},
                {"position": 9, "name": "consulting_doctor", "required": False},
                {"position": 10, "name": "hospital_service", "required": False},
            ],
        )

        # OBR - Observation Request
        self.config.segment_definitions["OBR"] = SegmentDefinition(
            name="OBR",
            description="Observation Request",
            required=False,
            repeatable=True,
            fields=[
                {"position": 1, "name": "set_id", "required": False},
                {"position": 2, "name": "placer_order_number", "required": False},
                {"position": 3, "name": "filler_order_number", "required": False},
                {"position": 4, "name": "universal_service_id", "required": True},
                {"position": 5, "name": "priority", "required": False},
                {"position": 6, "name": "requested_datetime", "required": False},
                {"position": 7, "name": "observation_datetime", "required": False},
            ],
        )

        # OBX - Observation Result
        self.config.segment_definitions["OBX"] = SegmentDefinition(
            name="OBX",
            description="Observation Result",
            required=False,
            repeatable=True,
            fields=[
                {"position": 1, "name": "set_id", "required": False},
                {"position": 2, "name": "value_type", "required": True},
                {"position": 3, "name": "observation_identifier", "required": True},
                {"position": 4, "name": "observation_sub_id", "required": False},
                {"position": 5, "name": "observation_value", "required": False},
                {"position": 6, "name": "units", "required": False},
                {"position": 7, "name": "reference_range", "required": False},
                {"position": 8, "name": "abnormal_flags", "required": False},
                {"position": 9, "name": "probability", "required": False},
                {"position": 10, "name": "nature_of_abnormal_test", "required": False},
                {"position": 11, "name": "observation_result_status", "required": True},
            ],
        )

    def _initialize_standard_message_types(self) -> None:
        """Initialize standard HL7 message type definitions."""
        # ADT^A01 - Admit/Visit Notification
        self.config.message_types["ADT^A01"] = MessageTypeDefinition(
            message_type="ADT",
            trigger_event="A01",
            description="Admit/Visit Notification",
            segments=[
                self.config.segment_definitions["MSH"],
                SegmentDefinition(name="EVN", description="Event Type", required=True),
                self.config.segment_definitions["PID"],
                self.config.segment_definitions["PV1"],
            ],
        )

        # ADT^A04 - Register a Patient
        self.config.message_types["ADT^A04"] = MessageTypeDefinition(
            message_type="ADT",
            trigger_event="A04",
            description="Register a Patient",
            segments=[
                self.config.segment_definitions["MSH"],
                SegmentDefinition(name="EVN", description="Event Type", required=True),
                self.config.segment_definitions["PID"],
                self.config.segment_definitions["PV1"],
            ],
        )

        # ORM^O01 - Order Message
        self.config.message_types["ORM^O01"] = MessageTypeDefinition(
            message_type="ORM",
            trigger_event="O01",
            description="Order Message",
            segments=[
                self.config.segment_definitions["MSH"],
                self.config.segment_definitions["PID"],
                self.config.segment_definitions["PV1"],
                self.config.segment_definitions["OBR"],
            ],
        )

        # ORU^R01 - Observation Result
        self.config.message_types["ORU^R01"] = MessageTypeDefinition(
            message_type="ORU",
            trigger_event="R01",
            description="Observation Result",
            segments=[
                self.config.segment_definitions["MSH"],
                self.config.segment_definitions["PID"],
                self.config.segment_definitions["PV1"],
                self.config.segment_definitions["OBR"],
                self.config.segment_definitions["OBX"],
            ],
        )

    def _initialize_standard_field_mappings(self) -> None:
        """Initialize standard field mappings."""
        # Patient mappings
        self.config.field_mappings["patient"] = [
            FieldMapping(
                segment="PID",
                field_position=3,
                field_name="patient_identifier_list",
                target_property="patient_id",
                data_type="CX",
                required=True,
            ),
            FieldMapping(
                segment="PID",
                field_position=5,
                field_name="patient_name",
                target_property="patient_name",
                data_type="XPN",
                required=True,
            ),
            FieldMapping(
                segment="PID",
                field_position=7,
                field_name="date_of_birth",
                target_property="birth_date",
                data_type="TS",
                required=False,
            ),
            FieldMapping(
                segment="PID",
                field_position=8,
                field_name="sex",
                target_property="gender",
                data_type="IS",
                required=False,
            ),
        ]

        # Visit mappings
        self.config.field_mappings["visit"] = [
            FieldMapping(
                segment="PV1",
                field_position=2,
                field_name="patient_class",
                target_property="patient_class",
                data_type="IS",
                required=True,
            ),
            FieldMapping(
                segment="PV1",
                field_position=3,
                field_name="assigned_patient_location",
                target_property="location",
                data_type="PL",
                required=False,
            ),
        ]

    def with_version(self, version: HL7Version) -> "HL7ConfigurationBuilder":
        """Set the default HL7 version."""
        self.config.default_version = version
        return self

    def with_strict_validation(self, strict: bool = True) -> "HL7ConfigurationBuilder":
        """Enable or disable strict validation."""
        self.config.strict_validation = strict
        return self

    def with_custom_segment(
        self, segment: SegmentDefinition
    ) -> "HL7ConfigurationBuilder":
        """Add a custom segment definition."""
        self.config.custom_segments[segment.name] = segment
        return self

    def with_field_mapping(self, mapping: FieldMapping) -> "HL7ConfigurationBuilder":
        """Add a field mapping."""
        category = mapping.target_property.split(".")[0]
        if category not in self.config.field_mappings:
            self.config.field_mappings[category] = []
        self.config.field_mappings[category].append(mapping)
        return self

    def with_routing_rule(self, rule: Dict[str, Any]) -> "HL7ConfigurationBuilder":
        """Add a routing rule."""
        self.config.routing_rules.append(rule)
        return self

    def build(self) -> ParserConfiguration:
        """Build the configuration."""
        return self.config


class HL7ParserConfigManager:
    """Manager for HL7 parser configurations."""

    def __init__(self, config_path: Optional[Path] = None):
        """Initialize configuration manager.

        Args:
            config_path: Path to configuration file
        """
        self.config_path = config_path
        self.configurations: Dict[str, ParserConfiguration] = {}
        self.active_config: Optional[str] = None

        # Load default configuration
        self.configurations["default"] = HL7ConfigurationBuilder().build()
        self.active_config = "default"

        # Load from file if provided
        if config_path and config_path.exists():
            self.load_configuration(config_path)

    def load_configuration(self, path: Path) -> None:
        """Load configuration from file.

        Args:
            path: Path to configuration file
        """
        try:
            with open(path, "r", encoding="utf-8") as f:
                config_data = json.load(f)

            for name, config_dict in config_data.items():
                builder = HL7ConfigurationBuilder()

                # Apply configuration settings
                if "version" in config_dict:
                    builder.with_version(HL7Version(config_dict["version"]))

                if "strict_validation" in config_dict:
                    builder.with_strict_validation(config_dict["strict_validation"])

                # Add custom segments
                for segment_data in config_dict.get("custom_segments", []):
                    segment = SegmentDefinition(**segment_data)
                    builder.with_custom_segment(segment)

                # Add field mappings
                for mapping_data in config_dict.get("field_mappings", []):
                    mapping = FieldMapping(**mapping_data)
                    builder.with_field_mapping(mapping)

                # Add routing rules
                for rule in config_dict.get("routing_rules", []):
                    builder.with_routing_rule(rule)

                self.configurations[name] = builder.build()

            logger.info("Loaded %d configurations from %s", len(config_data), path)

        except OSError as e:
            logger.error("Failed to load configuration from %s: %s", path, e)
            raise

    def save_configuration(self, path: Path) -> None:
        """Save configurations to file.

        Args:
            path: Path to save configuration file
        """
        config_data = {}

        for name, config in self.configurations.items():
            config_data[name] = {
                "version": config.default_version.value,
                "strict_validation": config.strict_validation,
                "encoding_characters": config.encoding_characters,
                "custom_segments": [
                    {
                        "name": seg.name,
                        "description": seg.description,
                        "required": seg.required,
                        "repeatable": seg.repeatable,
                        "fields": seg.fields,
                    }
                    for seg in config.custom_segments.values()
                ],
                "routing_rules": config.routing_rules,
            }

        with open(path, "w", encoding="utf-8") as f:
            json.dump(config_data, f, indent=2)

        logger.info("Saved %d configurations to %s", len(config_data), path)

    def get_configuration(self, name: Optional[str] = None) -> ParserConfiguration:
        """Get a configuration by name.

        Args:
            name: Configuration name (uses active if not provided)

        Returns:
            Parser configuration
        """
        config_name = name or self.active_config

        if config_name not in self.configurations:
            raise ValueError(f"Configuration '{config_name}' not found")

        return self.configurations[config_name]

    def set_active_configuration(self, name: str) -> None:
        """Set the active configuration.

        Args:
            name: Configuration name
        """
        if name not in self.configurations:
            raise ValueError(f"Configuration '{name}' not found")

        self.active_config = name
        logger.info("Active configuration set to '%s'", name)

    def create_configuration(
        self, name: str, base: Optional[str] = None
    ) -> HL7ConfigurationBuilder:
        """Create a new configuration.

        Args:
            name: Configuration name
            base: Base configuration to copy from

        Returns:
            Configuration builder
        """
        _ = name  # Name parameter used for documentation, actual registration happens later
        if base:
            if base not in self.configurations:
                raise ValueError(f"Base configuration '{base}' not found")

            # Copy base configuration
            builder = HL7ConfigurationBuilder()
            builder.config = copy.deepcopy(self.configurations[base])
        else:
            builder = HL7ConfigurationBuilder()

        return builder

    def register_configuration(self, name: str, config: ParserConfiguration) -> None:
        """Register a configuration.

        Args:
            name: Configuration name
            config: Parser configuration
        """
        self.configurations[name] = config
        logger.info("Registered configuration '%s'", name)


# Create global configuration manager
hl7_config_manager = HL7ParserConfigManager()
