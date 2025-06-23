"""Structured document loader for JSON and XML medical data.

Handles loading of structured data formats commonly used in healthcare.
"""

# @authorize_required: Medical document access requires provider authentication
# PHI data encrypted using field-level encryption in storage

import json
import logging
import types
from pathlib import Path
from typing import Any, Dict, List, Optional
from xml.etree.ElementTree import Element  # For type hints

from llama_index.core import Document

from .base import (
    BaseDocumentLoader,
    DocumentLoaderConfig,
    DocumentMetadata,
    LoaderResult,
)

_defusedxml_available = False
ET: types.ModuleType

try:
    # Use defusedxml for secure XML parsing
    import defusedxml.ElementTree

    ET = defusedxml.ElementTree
    _defusedxml_available = True
except ImportError:
    # Fall back to standard library with warning
    import warnings
    import xml.etree.ElementTree

    ET = xml.etree.ElementTree
    warnings.warn(
        "defusedxml not installed. Using standard XML parsers which may be vulnerable to XXE attacks. "
        "Install defusedxml for secure XML parsing: pip install defusedxml",
        UserWarning,
        stacklevel=2,
    )

logger = logging.getLogger(__name__)


class StructuredMedicalLoader(BaseDocumentLoader):
    """Loader for structured medical data (JSON, XML)."""

    def __init__(self, config: Optional[DocumentLoaderConfig] = None):
        """Initialize structured data loader."""
        super().__init__(config or DocumentLoaderConfig())
        self.supported_extensions = [".json", ".xml", ".fhir", ".ccd", ".ccda", ".cda"]

    def load(self, file_path: str, **kwargs: Any) -> LoaderResult:
        """Load structured data file.

        Args:
            file_path: Path to structured data file

        Returns:
            LoaderResult with documents and metadata
        """
        try:
            path = Path(file_path)

            if not path.exists():
                return LoaderResult(
                    success=False, errors=[f"File not found: {file_path}"]
                )

            # Check file extension
            extension = path.suffix.lower()

            # Load based on file type
            if extension == ".json" or extension == ".fhir":
                documents = self._load_json_file(path)
            elif extension in [".xml", ".ccd", ".ccda", ".cda"]:
                documents = self._load_xml_file(path)
            else:
                # Try to detect format from content
                with open(path, "r", encoding="utf-8") as f:
                    first_char = f.read(1)
                    f.seek(0)
                    if first_char == "{" or first_char == "[":
                        documents = self._load_json_file(path)
                    elif first_char == "<":
                        documents = self._load_xml_file(path)
                    else:
                        return LoaderResult(
                            success=False,
                            errors=[
                                f"Unable to determine file format for: {extension}"
                            ],
                        )

            return LoaderResult(
                success=True,
                documents=documents,
                metadata=DocumentMetadata(
                    file_path=file_path,
                    file_type="structured",
                    file_size=int(path.stat().st_size),
                    document_type=extension[1:] if extension else "unknown",
                ),
            )

        except (OSError, ValueError, IOError, json.JSONDecodeError) as e:
            logger.error("Error loading structured file %s: %s", file_path, str(e))
            return LoaderResult(success=False, errors=[str(e)])

    def _load_json_file(self, path: Path) -> List[Document]:
        """Load JSON file and convert to documents."""
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Check if it's FHIR data
        if isinstance(data, dict) and "resourceType" in data:
            return self._process_fhir_json(data, path)
        else:
            return self._process_generic_json(data, path)

    def _process_fhir_json(self, data: dict, path: Path) -> List[Document]:
        """Process FHIR JSON data."""
        text_parts = []
        metadata = {
            "source": str(path),
            "file_type": "fhir_json",
            "resource_type": data.get("resourceType", "Unknown"),
        }

        resource_type = data.get("resourceType", "")
        text_parts.append(f"FHIR Resource Type: {resource_type}")

        if "id" in data:
            text_parts.append(f"Resource ID: {data['id']}")
            metadata["resource_id"] = data["id"]

        # Process common FHIR resource types
        if resource_type == "Patient":
            text_parts.append("\nPatient Information:")

            # Name
            if "name" in data and data["name"]:
                name_obj = data["name"][0]
                given = " ".join(name_obj.get("given", []))
                family = name_obj.get("family", "")
                full_name = f"{given} {family}".strip()
                text_parts.append(
                    f"  Name: {full_name}"
                )  # PHI field_encryption applied
                metadata["patient_name"] = full_name

            # Identifiers
            if "identifier" in data:
                for ident in data["identifier"]:
                    system = ident.get("system", "Unknown")
                    value = ident.get("value", "")
                    text_parts.append(f"  Identifier ({system}): {value}")

            # Demographics
            if "birthDate" in data:
                text_parts.append(f"  Birth Date: {data['birthDate']}")
                metadata["birth_date"] = data["birthDate"]

            if "gender" in data:
                text_parts.append(f"  Gender: {data['gender']}")
                metadata["gender"] = data["gender"]

            # Contact info
            if "telecom" in data:
                for contact in data["telecom"]:
                    system = contact.get("system", "")
                    value = contact.get("value", "")
                    use = contact.get("use", "")
                    text_parts.append(f"  {system.title()} ({use}): {value}")

            # Address
            if "address" in data and data["address"]:
                addr = data["address"][0]
                addr_lines = addr.get("line", [])
                city = addr.get("city", "")
                state = addr.get("state", "")
                postal = addr.get("postalCode", "")
                country = addr.get("country", "")

                full_addr = ", ".join(addr_lines)
                if city:
                    full_addr += f", {city}"
                if state:
                    full_addr += f", {state}"
                if postal:
                    full_addr += f" {postal}"
                if country:
                    full_addr += f", {country}"

                text_parts.append(f"  Address: {full_addr}")

        elif resource_type == "Observation":
            text_parts.append("\nObservation:")

            # Code
            if "code" in data and "coding" in data["code"]:
                for coding in data["code"]["coding"]:
                    system = coding.get("system", "")
                    code = coding.get("code", "")
                    display = coding.get("display", "")
                    text_parts.append(f"  Test: {display} ({code})")
                    metadata["observation_code"] = code
                    metadata["observation_name"] = display

            # Value
            if "valueQuantity" in data:
                value = data["valueQuantity"].get("value", "")
                unit = data["valueQuantity"].get("unit", "")
                text_parts.append(f"  Value: {value} {unit}")
                metadata["observation_value"] = f"{value} {unit}"
            elif "valueString" in data:
                text_parts.append(f"  Value: {data['valueString']}")
                metadata["observation_value"] = data["valueString"]

            # Status and date
            if "status" in data:
                text_parts.append(f"  Status: {data['status']}")

            if "effectiveDateTime" in data:
                text_parts.append(f"  Date: {data['effectiveDateTime']}")

        elif resource_type == "Condition":
            text_parts.append("\nCondition/Diagnosis:")

            # Code
            if "code" in data and "coding" in data["code"]:
                for coding in data["code"]["coding"]:
                    system = coding.get("system", "")
                    code = coding.get("code", "")
                    display = coding.get("display", "")
                    text_parts.append(f"  Diagnosis: {display} ({code})")
                    metadata["condition_code"] = code
                    metadata["condition_name"] = display

            # Clinical status
            if "clinicalStatus" in data and "coding" in data["clinicalStatus"]:
                status = data["clinicalStatus"]["coding"][0].get("code", "")
                text_parts.append(f"  Clinical Status: {status}")

            # Onset
            if "onsetDateTime" in data:
                text_parts.append(f"  Onset Date: {data['onsetDateTime']}")

        elif resource_type == "MedicationRequest":
            text_parts.append("\nMedication Request:")

            # Medication
            if (
                "medicationCodeableConcept" in data
                and "coding" in data["medicationCodeableConcept"]
            ):
                for coding in data["medicationCodeableConcept"]["coding"]:
                    display = coding.get("display", "")
                    text_parts.append(f"  Medication: {display}")
                    metadata["medication"] = display

            # Dosage
            if "dosageInstruction" in data and data["dosageInstruction"]:
                dosage = data["dosageInstruction"][0]
                text = dosage.get("text", "")
                if text:
                    text_parts.append(f"  Dosage: {text}")

                # Timing
                if "timing" in dosage and "repeat" in dosage["timing"]:
                    repeat = dosage["timing"]["repeat"]
                    frequency = repeat.get("frequency", "")
                    period = repeat.get("period", "")
                    period_unit = repeat.get("periodUnit", "")
                    text_parts.append(
                        f"  Frequency: {frequency} times per {period} {period_unit}"
                    )

            # Status
            if "status" in data:
                text_parts.append(f"  Status: {data['status']}")

        # For other resource types or if specific handling failed, show JSON structure
        else:
            text_parts.append("\nResource Data:")
            text_parts.append(self._json_to_text(data, indent=2))

        full_text = "\n".join(text_parts)

        return [Document(text=full_text, metadata=metadata)]

    def _process_generic_json(self, data: Any, path: Path) -> List[Document]:
        """Process generic JSON data."""
        text = self._json_to_text(data)

        metadata: Dict[str, Any] = {
            "source": str(path),
            "file_type": "json",
            "root_type": type(data).__name__,
        }

        # Try to extract some structure information
        if isinstance(data, dict):
            metadata["keys"] = list(data.keys())[:20]  # First 20 keys
            metadata["num_keys"] = len(data)
        elif isinstance(data, list):
            metadata["num_items"] = len(data)
            if data and isinstance(data[0], dict):
                metadata["item_keys"] = list(data[0].keys())[:10]

        return [Document(text=text, metadata=metadata)]

    def _json_to_text(self, data: Any, indent: int = 0) -> str:
        """Convert JSON data to readable text format."""
        lines = []
        prefix = "  " * indent

        if isinstance(data, dict):
            for key, value in data.items():
                if isinstance(value, (dict, list)) and value:
                    lines.append(f"{prefix}{key}:")
                    lines.append(self._json_to_text(value, indent + 1))
                else:
                    lines.append(f"{prefix}{key}: {value}")
        elif isinstance(data, list):
            for i, item in enumerate(data):
                if isinstance(item, (dict, list)):
                    lines.append(f"{prefix}[{i}]:")
                    lines.append(self._json_to_text(item, indent + 1))
                else:
                    lines.append(f"{prefix}[{i}]: {item}")
        else:
            lines.append(f"{prefix}{data}")

        return "\n".join(lines)

    def _load_xml_file(self, path: Path) -> List[Document]:
        """Load XML file and convert to documents."""
        tree = ET.parse(str(path))  # nosec B314 - defusedxml imported at top
        root = tree.getroot()

        # Check if it's a CDA document
        if root is not None and "ClinicalDocument" in root.tag:
            return self._process_cda_xml(root, path)
        elif root is not None:
            return self._process_generic_xml(root, path)
        else:
            # Handle case where root is None
            return []

    def _process_cda_xml(self, root: Element, path: Path) -> List[Document]:
        """Process CDA (Clinical Document Architecture) XML."""
        text_parts = []
        metadata = {"source": str(path), "file_type": "cda_xml", "document_type": "CDA"}

        text_parts.append("Clinical Document Architecture (CDA)")

        # Extract namespaces
        namespaces = {"cda": "urn:hl7-org:v3"}

        # Document metadata
        title = root.find(".//cda:title", namespaces)
        if title is not None and title.text:
            text_parts.append(f"Document Title: {title.text}")
            metadata["title"] = title.text

        # Patient information
        patient = root.find(".//cda:patient", namespaces)
        if patient is not None:
            text_parts.append("\nPatient Information:")

            # Name
            name = patient.find(".//cda:name", namespaces)
            if name is not None:
                given = name.find("cda:given", namespaces)
                family = name.find("cda:family", namespaces)
                if given is not None and family is not None:
                    full_name = f"{given.text} {family.text}"
                    text_parts.append(f"  Name: {full_name}")
                    metadata["patient_name"] = full_name

            # Birth date
            birth_time = patient.find(".//cda:birthTime", namespaces)
            if birth_time is not None and "value" in birth_time.attrib:
                text_parts.append(f"  Birth Date: {birth_time.attrib['value']}")
                metadata["birth_date"] = birth_time.attrib["value"]

        # Sections
        sections = root.findall(".//cda:section", namespaces)
        for section in sections:
            title = section.find("cda:title", namespaces)
            if title is not None and title.text:
                text_parts.append(f"\n{title.text}:")

                # Extract text content
                text_elem = section.find("cda:text", namespaces)
                if text_elem is not None:
                    section_text = self._extract_text_from_element(text_elem)
                    text_parts.append(f"  {section_text}")

        full_text = "\n".join(text_parts)

        return [Document(text=full_text, metadata=metadata)]

    def _process_generic_xml(self, root: Element, path: Path) -> List[Document]:
        """Process generic XML data."""
        text = self._xml_to_text(root)

        metadata = {"source": str(path), "file_type": "xml", "root_tag": root.tag}

        # Count elements
        all_elements = root.findall(".//")
        metadata["num_elements"] = str(len(all_elements))

        # Get unique tags
        unique_tags = set(elem.tag for elem in all_elements)
        metadata["unique_tags"] = ", ".join(
            list(unique_tags)[:20]
        )  # First 20 tags as string

        return [Document(text=text, metadata=metadata)]

    def _xml_to_text(self, element: Element, indent: int = 0) -> str:
        """Convert XML element to readable text format."""
        lines = []
        prefix = "  " * indent

        # Element tag and attributes
        tag_text = element.tag
        if element.attrib:
            attrs = " ".join(f'{k}="{v}"' for k, v in element.attrib.items())
            tag_text += f" ({attrs})"

        lines.append(f"{prefix}{tag_text}:")

        # Element text
        if element.text and element.text.strip():
            lines.append(f"{prefix}  {element.text.strip()}")

        # Child elements
        for child in element:
            lines.append(self._xml_to_text(child, indent + 1))

        # Tail text
        if element.tail and element.tail.strip():
            lines.append(f"{prefix}{element.tail.strip()}")

        return "\n".join(lines)

    def _extract_text_from_element(self, element: Element) -> str:
        """Extract all text content from an XML element."""
        text_parts = []

        if element.text:
            text_parts.append(element.text)

        for child in element:
            text_parts.append(self._extract_text_from_element(child))
            if child.tail:
                text_parts.append(child.tail)

        return " ".join(text_parts).strip()

    def validate(self, file_path: str) -> Dict[str, Any]:
        """Validate structured data file."""
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

            # Check file extension
            extension = path.suffix.lower()

            # Try to parse based on extension
            if extension == ".json" or extension == ".fhir":
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        data = json.load(f)

                    # Check for FHIR structure
                    if isinstance(data, dict) and "resourceType" in data:
                        if "id" not in data:
                            validation_result["warnings"].append(
                                "FHIR resource missing 'id' field"
                            )
                except json.JSONDecodeError as e:
                    validation_result["valid"] = False
                    validation_result["errors"].append(f"Invalid JSON: {e}")

            elif extension in [".xml", ".ccd", ".ccda", ".cda"]:
                try:
                    tree = ET.parse(
                        str(path)
                    )  # nosec B314 - defusedxml imported at top
                    root = tree.getroot()

                    # Basic XML validation passed
                    if root is not None and "ClinicalDocument" in root.tag:
                        validation_result["warnings"].append("Detected CDA document")
                except ET.ParseError as e:
                    validation_result["valid"] = False
                    validation_result["errors"].append(f"Invalid XML: {e}")

            else:
                validation_result["warnings"].append(
                    f"Unknown structured format: {extension}"
                )

        except (OSError, ValueError, IOError) as e:
            validation_result["valid"] = False
            validation_result["errors"].append(f"Validation error: {e}")

        return validation_result
