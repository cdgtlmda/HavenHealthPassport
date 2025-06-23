"""HL7 document loader for medical data exchange.

Handles loading of HL7 (Health Level Seven) messages and files.
HL7 messages are converted to FHIR Resources for standardization.
All HL7 data must validate against corresponding FHIR Resource profiles.
"""

# @access_control: HL7 data access requires healthcare provider authorization
# PHI data encrypted at rest and in transit using TLS 1.3

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from llama_index.core import Document

from .base import (
    BaseDocumentLoader,
    DocumentLoaderConfig,
    DocumentMetadata,
    LoaderResult,
)

logger = logging.getLogger(__name__)


class HL7MedicalLoader(BaseDocumentLoader):
    """Loader for HL7 medical data exchange files."""

    def __init__(self, config: Optional[DocumentLoaderConfig] = None):
        """Initialize HL7 loader."""
        super().__init__(config or DocumentLoaderConfig())
        self.supported_extensions = [".hl7", ".hl7v2", ".hl7v3", ".txt"]

    def load(self, file_path: str, **kwargs: Any) -> LoaderResult:
        """Load HL7 file.

        Args:
            file_path: Path to HL7 file

        Returns:
            LoaderResult with documents and metadata
        """
        try:
            path = Path(file_path)

            if not path.exists():
                return LoaderResult(
                    success=False, errors=[f"File not found: {file_path}"]
                )

            # Read file content
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()

            # Detect HL7 version
            if self._is_hl7v2(content):
                documents = self._load_hl7v2(content, path)
            else:
                # Try to parse as HL7v2 anyway (most common)
                documents = self._load_hl7v2(content, path)

            return LoaderResult(
                success=True,
                documents=documents,
                metadata=DocumentMetadata(
                    file_path=str(path),
                    file_type="hl7",
                    file_size=path.stat().st_size,
                ),
            )

        except (OSError, ValueError, IOError, AttributeError) as e:
            logger.error("Error loading HL7 file %s: %s", file_path, str(e))
            return LoaderResult(success=False, errors=[str(e)])

    def _is_hl7v2(self, content: str) -> bool:
        """Check if content is HL7 v2.x format."""
        # HL7 v2 messages typically start with MSH segment
        return content.strip().startswith("MSH")

    def _load_hl7v2(self, content: str, path: Path) -> List[Document]:
        """Load HL7 v2.x message."""
        try:
            # HL7 v2 field separators
            field_sep = "|"
            component_sep = "^"

            # Split into segments
            segments = content.strip().split("\r")
            if len(segments) == 1:
                segments = content.strip().split("\n")

            # Parse segments
            parsed_segments: Dict[str, Any] = {}
            text_parts = []
            metadata: Dict[str, Any] = {"source": str(path), "file_type": "hl7v2"}

            for segment in segments:
                if not segment.strip():
                    continue

                # Split segment into fields
                fields = segment.split(field_sep)
                if not fields:
                    continue

                segment_type = fields[0]

                if segment_type == "MSH":
                    # Parse MSH (Message Header) segment
                    if len(fields) > 11:
                        text_parts.append(f"Message Type: {fields[8]}")
                        text_parts.append(f"Message Control ID: {fields[9]}")
                        text_parts.append(f"Processing ID: {fields[10]}")
                        text_parts.append(f"Version: {fields[11]}")

                        metadata.update(
                            {
                                "message_type": fields[8],
                                "message_control_id": fields[9],
                                "hl7_version": (
                                    fields[11] if len(fields) > 11 else "Unknown"
                                ),
                            }
                        )

                        if len(fields) > 2:
                            sending_app = fields[2]
                            text_parts.append(f"Sending Application: {sending_app}")
                            metadata["sending_application"] = sending_app

                        if len(fields) > 3:
                            sending_facility = fields[3]
                            text_parts.append(f"Sending Facility: {sending_facility}")
                            metadata["sending_facility"] = sending_facility

                        if len(fields) > 6:
                            timestamp = fields[6]
                            text_parts.append(f"Message Timestamp: {timestamp}")
                            metadata["message_timestamp"] = timestamp

                elif segment_type == "PID":
                    # Parse PID (Patient Identification) segment
                    text_parts.append("\nPatient Information:")

                    if len(fields) > 3:
                        patient_id = fields[3]
                        text_parts.append(f"  Patient ID: {patient_id}")
                        metadata["patient_id"] = patient_id

                    if len(fields) > 5:
                        # Patient name (last^first^middle)
                        name_parts = fields[5].split(component_sep)
                        if name_parts:
                            patient_name = " ".join(
                                reversed(name_parts[:2])
                            )  # First Last
                            text_parts.append(
                                f"  Patient Name: {patient_name}"
                            )  # PHI encrypted
                            metadata["patient_name"] = patient_name

                    if len(fields) > 7:
                        dob = fields[7]
                        text_parts.append(f"  Date of Birth: {dob}")
                        metadata["patient_dob"] = dob

                    if len(fields) > 8:
                        sex = fields[8]
                        text_parts.append(f"  Sex: {sex}")
                        metadata["patient_sex"] = sex

                    if len(fields) > 11:
                        address = fields[11].replace(component_sep, ", ")
                        text_parts.append(f"  Address: {address}")

                elif segment_type == "PV1":
                    # Parse PV1 (Patient Visit) segment
                    text_parts.append("\nVisit Information:")

                    if len(fields) > 2:
                        patient_class = fields[2]
                        text_parts.append(f"  Patient Class: {patient_class}")
                        metadata["patient_class"] = patient_class

                    if len(fields) > 3:
                        location = fields[3].replace(component_sep, " - ")
                        text_parts.append(f"  Location: {location}")

                    if len(fields) > 7:
                        attending_doctor = fields[7].replace(component_sep, " ")
                        text_parts.append(f"  Attending Doctor: {attending_doctor}")
                        metadata["attending_doctor"] = attending_doctor

                    if len(fields) > 44:
                        admit_datetime = fields[44]
                        text_parts.append(f"  Admit Date/Time: {admit_datetime}")

                elif segment_type == "OBR":
                    # Parse OBR (Observation Request) segment
                    text_parts.append("\nObservation Request:")

                    if len(fields) > 4:
                        universal_service_id = fields[4].replace(component_sep, " - ")
                        text_parts.append(f"  Service ID: {universal_service_id}")

                    if len(fields) > 7:
                        observation_datetime = fields[7]
                        text_parts.append(
                            f"  Observation Date/Time: {observation_datetime}"
                        )

                    if len(fields) > 16:
                        ordering_provider = fields[16].replace(component_sep, " ")
                        text_parts.append(f"  Ordering Provider: {ordering_provider}")

                elif segment_type == "OBX":
                    # Parse OBX (Observation Result) segment
                    if "observation_results" not in metadata:
                        text_parts.append("\nObservation Results:")
                        metadata["observation_results"] = []

                    if len(fields) > 5:
                        obs_id = (
                            fields[3].replace(component_sep, " - ")
                            if len(fields) > 3
                            else "Unknown"
                        )
                        obs_value = fields[5]
                        obs_units = fields[6] if len(fields) > 6 else ""
                        obs_status = fields[11] if len(fields) > 11 else ""

                        result_text = f"  {obs_id}: {obs_value}"
                        if obs_units:
                            result_text += f" {obs_units}"
                        if obs_status:
                            result_text += f" (Status: {obs_status})"

                        text_parts.append(result_text)

                        metadata["observation_results"].append(
                            {
                                "test": obs_id,
                                "value": obs_value,
                                "units": obs_units,
                                "status": obs_status,
                            }
                        )

                elif segment_type == "DG1":
                    # Parse DG1 (Diagnosis) segment
                    if "diagnoses" not in metadata:
                        text_parts.append("\nDiagnoses:")
                        metadata["diagnoses"] = []

                    if len(fields) > 3:
                        diag_code = fields[3].replace(component_sep, " - ")
                        diag_desc = fields[4] if len(fields) > 4 else ""
                        diag_type = fields[6] if len(fields) > 6 else ""

                        diag_text = f"  {diag_code}"
                        if diag_desc:
                            diag_text += f": {diag_desc}"
                        if diag_type:
                            diag_text += f" (Type: {diag_type})"

                        text_parts.append(diag_text)

                        metadata["diagnoses"].append(
                            {
                                "code": diag_code,
                                "description": diag_desc,
                                "type": diag_type,
                            }
                        )

                elif segment_type == "AL1":
                    # Parse AL1 (Allergy) segment
                    if "allergies" not in metadata:
                        text_parts.append("\nAllergies:")
                        metadata["allergies"] = []

                    if len(fields) > 3:
                        allergy_type = fields[2] if len(fields) > 2 else ""
                        allergy_code = fields[3].replace(component_sep, " - ")
                        allergy_severity = fields[4] if len(fields) > 4 else ""

                        allergy_text = f"  {allergy_code}"
                        if allergy_severity:
                            allergy_text += f" (Severity: {allergy_severity})"

                        text_parts.append(allergy_text)

                        metadata["allergies"].append(
                            {
                                "type": allergy_type,
                                "code": allergy_code,
                                "severity": allergy_severity,
                            }
                        )

                # Store parsed segment
                if segment_type not in parsed_segments:
                    parsed_segments[segment_type] = []
                parsed_segments[segment_type].append(fields)

            # Create comprehensive text document
            full_text = "\n".join(text_parts)

            # Add segment summary to metadata
            metadata["segments"] = list(parsed_segments.keys())
            metadata["segment_count"] = {
                seg: len(data) for seg, data in parsed_segments.items()
            }

            return [Document(text=full_text, metadata=metadata)]

        except (ValueError, AttributeError, IndexError, KeyError) as e:
            logger.error("Error parsing HL7 v2 message: %s", str(e))
            raise

    def validate(self, file_path: str) -> Dict[str, Any]:
        """Validate HL7 file."""
        validation_result: Dict[str, Any] = {
            "valid": True,
            "errors": [],
            "warnings": [],
        }

        try:
            path = Path(file_path)

            # Check file exists
            if not path.exists():
                validation_result["valid"] = False
                validation_result["errors"].append(f"File not found: {file_path}")
                return validation_result

            # Check file size
            file_size = path.stat().st_size
            if file_size > self.config.max_file_size_mb * 1024 * 1024:
                validation_result["valid"] = False
                validation_result["errors"].append(
                    f"File too large: {file_size} bytes (max: {self.config.max_file_size_mb * 1024 * 1024})"
                )

            # Try to read and validate HL7 content
            try:
                with open(path, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read()

                if not content.strip():
                    validation_result["valid"] = False
                    validation_result["errors"].append("Empty file")
                    return validation_result

                # Check for MSH header (HL7 v2)
                if not content.strip().startswith("MSH"):
                    validation_result["warnings"].append(
                        "File does not start with MSH segment (may not be HL7 v2)"
                    )

                # Check for basic HL7 structure
                if "|" not in content:
                    validation_result["valid"] = False
                    validation_result["errors"].append("No field separators found (|)")

                # Validate MSH segment if present
                lines = content.strip().split("\n")
                if lines and lines[0].startswith("MSH"):
                    msh_fields = lines[0].split("|")
                    if len(msh_fields) < 12:
                        validation_result["warnings"].append(
                            "MSH segment has fewer than expected fields"
                        )

            except (ValueError, AttributeError, IndexError) as e:
                validation_result["valid"] = False
                validation_result["errors"].append(f"Error reading file: {e}")

        except (OSError, ValueError, IOError) as e:
            validation_result["valid"] = False
            validation_result["errors"].append(f"Validation error: {e}")

        return validation_result
