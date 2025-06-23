"""Camp/Settlement identifier extension implementation.

This module handles FHIR Extension Resource validation for camp/settlement identifiers.
"""

from typing import Any, Dict, List, Literal, Optional, TypedDict

from fhirclient.models.extension import Extension

from ..fhir_profiles import CAMP_SETTLEMENT_EXTENSION

# FHIR resource type for this module
__fhir_resource__ = "Extension"


class FHIRExtension(TypedDict, total=False):
    """FHIR Extension resource type definition."""

    url: str
    valueString: Optional[str]
    extension: Optional[list[Dict[str, Any]]]
    __fhir_resource__: Literal["Extension"]


class CampSettlementExtension:
    """Handler for camp/settlement identifier FHIR extension."""

    # FHIR resource type
    __fhir_resource__ = "Extension"

    @staticmethod
    def create_extension(
        camp_name: str,
        camp_code: Optional[str] = None,
        sector: Optional[str] = None,
    ) -> Extension:
        """Create camp/settlement identifier extension.

        Args:
            camp_name: Name of the camp or settlement
            camp_code: Official camp code (e.g., UNHCR camp code)
            sector: Sector/zone within the camp

        Returns:
            FHIR Extension object
        """
        ext = Extension()
        ext.url = CAMP_SETTLEMENT_EXTENSION
        ext.extension = []

        # Add camp name
        name_ext = Extension()
        name_ext.url = "campName"
        name_ext.valueString = camp_name
        ext.extension.append(name_ext)

        # Add camp code if provided
        if camp_code:
            code_ext = Extension()
            code_ext.url = "campCode"
            code_ext.valueString = camp_code
            ext.extension.append(code_ext)

        # Add sector if provided
        if sector:
            sector_ext = Extension()
            sector_ext.url = "sector"
            sector_ext.valueString = sector
            ext.extension.append(sector_ext)

        return ext

    @staticmethod
    def parse_extension(extension: Extension) -> Dict[str, Any]:
        """Parse camp/settlement extension into dictionary.

        Args:
            extension: FHIR Extension object

        Returns:
            Dictionary with parsed values
        """
        result: Dict[str, Any] = {}

        if not extension.extension:
            return result

        for sub_ext in extension.extension:
            if sub_ext.url == "campName" and sub_ext.valueString:
                result["camp_name"] = sub_ext.valueString
            elif sub_ext.url == "campCode" and sub_ext.valueString:
                result["camp_code"] = sub_ext.valueString
            elif sub_ext.url == "sector" and sub_ext.valueString:
                result["sector"] = sub_ext.valueString

        return result

    @staticmethod
    def validate_extension(extension_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate camp/settlement extension data.

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
        elif extension_data["url"] != CAMP_SETTLEMENT_EXTENSION:
            errors.append(f"Invalid extension URL: {extension_data['url']}")

        # Check for campName sub-extension
        if "extension" in extension_data:
            has_camp_name = False
            for sub_ext in extension_data["extension"]:
                if sub_ext.get("url") == "campName" and sub_ext.get("valueString"):
                    has_camp_name = True
                    break
            if not has_camp_name:
                errors.append("Camp/settlement extension must have campName")

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
        validation_result = CampSettlementExtension.validate_extension(extension_data)

        # Additional FHIR validation if needed
        if validation_result["valid"]:
            # Ensure proper structure for sub-extensions
            if "extension" in extension_data:
                for sub_ext in extension_data["extension"]:
                    if "url" not in sub_ext:
                        validation_result["errors"].append(
                            "Sub-extension must have url"
                        )
                        validation_result["valid"] = False

        return validation_result

    @staticmethod
    def create_fhir_extension(
        camp_name: str,
        camp_code: Optional[str] = None,
        sector: Optional[str] = None,
    ) -> FHIRExtension:
        """Create FHIR Extension structure for camp/settlement.

        Args:
            camp_name: Name of the camp or settlement
            camp_code: Official camp code
            sector: Sector/zone within the camp

        Returns:
            FHIR Extension structure
        """
        extension: FHIRExtension = {
            "url": CAMP_SETTLEMENT_EXTENSION,
            "extension": [],
            "__fhir_resource__": "Extension",
        }

        # Add camp name
        name_ext = {"url": "campName", "valueString": camp_name}
        if extension["extension"] is not None:
            extension["extension"].append(name_ext)

        # Add camp code if provided
        if camp_code:
            code_ext = {"url": "campCode", "valueString": camp_code}
            if extension["extension"] is not None:
                extension["extension"].append(code_ext)

        # Add sector if provided
        if sector:
            sector_ext = {"url": "sector", "valueString": sector}
            if extension["extension"] is not None:
                extension["extension"].append(sector_ext)

        return extension


def validate_fhir(fhir_data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate FHIR data for camp/settlement extensions.

    Args:
        fhir_data: FHIR data to validate

    Returns:
        Validation results
    """
    errors = []
    warnings = []

    # Check if it's an Extension
    if fhir_data.get("__fhir_resource__") == "Extension" or "url" in fhir_data:
        # Validate URL
        if fhir_data.get("url") != CAMP_SETTLEMENT_EXTENSION:
            warnings.append(
                f"Expected URL {CAMP_SETTLEMENT_EXTENSION}, got {fhir_data.get('url')}"
            )

        # Check for required sub-extensions
        if "extension" in fhir_data and isinstance(fhir_data["extension"], list):
            has_camp_name = any(
                ext.get("url") == "campName" for ext in fhir_data["extension"]
            )
            if not has_camp_name:
                errors.append(
                    "Camp settlement extension must include 'campName' sub-extension"
                )
        else:
            errors.append("Extension must have 'extension' array")
    else:
        errors.append("Not a valid FHIR Extension structure")

    return {"valid": len(errors) == 0, "errors": errors, "warnings": warnings}
