"""Displacement date extension implementation."""

from datetime import date
from typing import Any, Dict, List, Literal, Optional, TypedDict

from fhirclient.models.extension import Extension
from fhirclient.models.fhirdate import FHIRDate

from ..fhir_profiles import DISPLACEMENT_DATE_EXTENSION

# FHIR resource type for this module
__fhir_resource__ = "Extension"


class FHIRExtension(TypedDict, total=False):
    """FHIR Extension resource type definition."""

    url: str
    valueBoolean: Optional[bool]
    valueInteger: Optional[int]
    valueDecimal: Optional[float]
    valueBase64Binary: Optional[str]
    valueInstant: Optional[str]
    valueString: Optional[str]
    valueUri: Optional[str]
    valueDate: Optional[str]
    valueDateTime: Optional[str]
    valueTime: Optional[str]
    valueCode: Optional[str]
    valueOid: Optional[str]
    valueUuid: Optional[str]
    valueId: Optional[str]
    valueUnsignedInt: Optional[int]
    valuePositiveInt: Optional[int]
    valueMarkdown: Optional[str]
    valueElement: Optional[Dict[str, Any]]
    valueExtension: Optional[Dict[str, Any]]
    valueCoding: Optional[Dict[str, Any]]
    valueCodeableConcept: Optional[Dict[str, Any]]
    valueAttachment: Optional[Dict[str, Any]]
    valueIdentifier: Optional[Dict[str, Any]]
    valueQuantity: Optional[Dict[str, Any]]
    valueSampledData: Optional[Dict[str, Any]]
    valueRange: Optional[Dict[str, Any]]
    valuePeriod: Optional[Dict[str, Any]]
    valueRatio: Optional[Dict[str, Any]]
    valueReference: Optional[Dict[str, Any]]
    valueSignature: Optional[Dict[str, Any]]
    valueHumanName: Optional[Dict[str, Any]]
    valueAddress: Optional[Dict[str, Any]]
    valueContactPoint: Optional[Dict[str, Any]]
    valueTiming: Optional[Dict[str, Any]]
    valueMeta: Optional[Dict[str, Any]]
    valueDuration: Optional[Dict[str, Any]]
    __fhir_resource__: Literal["Extension"]


class DisplacementDateExtension:
    """Handler for displacement date FHIR extension."""

    # FHIR resource type
    __fhir_resource__ = "Extension"

    @staticmethod
    def create_extension(displacement_date: date) -> Extension:
        """Create displacement date extension.

        Args:
            displacement_date: Date when person was displaced

        Returns:
            FHIR Extension object
        """
        ext = Extension()
        ext.url = DISPLACEMENT_DATE_EXTENSION
        ext.valueDate = FHIRDate(displacement_date.isoformat())
        return ext

    @staticmethod
    def parse_extension(extension: Extension) -> Dict[str, Any]:
        """Parse displacement date extension into dictionary.

        Args:
            extension: FHIR Extension object

        Returns:
            Dictionary with parsed values
        """
        result = {}

        if extension.valueDate:
            result["displacement_date"] = extension.valueDate.as_json()

        return result

    @staticmethod
    def validate_extension(extension_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate displacement date extension data.

        Args:
            extension_data: Extension data to validate

        Returns:
            Validation result with 'valid', 'errors', and 'warnings' keys
        """
        errors = []
        warnings: List[str] = []

        # Check required fields
        if not extension_data.get("url"):
            errors.append("Extension must have url")
        elif extension_data["url"] != DISPLACEMENT_DATE_EXTENSION:
            errors.append(f"Invalid extension URL: {extension_data['url']}")

        if not extension_data.get("valueDate"):
            errors.append("Displacement date extension must have valueDate")

        return {"valid": len(errors) == 0, "errors": errors, "warnings": warnings}

    @staticmethod
    def validate_fhir_extension(extension_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate extension as FHIR Extension resource.

        Args:
            extension_data: Extension data to validate

        Returns:
            Validation result with 'valid', 'errors', and 'warnings' keys
        """
        # Use existing validation method
        validation_result = DisplacementDateExtension.validate_extension(extension_data)

        # Additional FHIR validation if needed
        if validation_result["valid"]:
            # Ensure it's marked as Extension resource
            if (
                "resourceType" in extension_data
                and extension_data["resourceType"] != "Extension"
            ):
                validation_result["errors"].append(
                    "ResourceType must be 'Extension' if specified"
                )
                validation_result["valid"] = False

        return validation_result

    @staticmethod
    def create_fhir_extension(displacement_date: date) -> FHIRExtension:
        """Create FHIR Extension structure for displacement date.

        Args:
            displacement_date: Date when person was displaced

        Returns:
            FHIR Extension structure
        """
        extension: FHIRExtension = {
            "url": DISPLACEMENT_DATE_EXTENSION,
            "valueDate": displacement_date.isoformat(),
            "__fhir_resource__": "Extension",
        }

        return extension
