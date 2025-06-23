"""Verification status extension implementation.

This module handles FHIR Extension Resource validation for verification status.
"""

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional, TypedDict

from fhirclient.models.extension import Extension
from fhirclient.models.fhirdate import FHIRDate
from fhirclient.models.fhirreference import FHIRReference

from ..fhir_profiles import VERIFICATION_STATUS_EXTENSION

# FHIR resource type for this module
__fhir_resource__ = "Extension"


class FHIRExtension(TypedDict, total=False):
    """FHIR Extension resource type definition."""

    url: str
    valueCode: Optional[str]
    valueDateTime: Optional[str]
    valueReference: Optional[Dict[str, str]]
    extension: Optional[list[Dict[str, Any]]]
    __fhir_resource__: Literal["Extension"]


class VerificationStatusExtension:
    """Handler for verification status FHIR extension."""

    # FHIR resource type
    __fhir_resource__ = "Extension"

    @staticmethod
    def create_extension(
        level: str,
        timestamp: datetime,
        verifier_reference: Optional[str] = None,
    ) -> Extension:
        """Create verification status extension.

        Args:
            level: Verification level (unverified, basic, standard, enhanced, full)
            timestamp: When verification was performed
            verifier_reference: Reference to verifying Practitioner or Organization

        Returns:
            FHIR Extension object
        """
        ext = Extension()
        ext.url = VERIFICATION_STATUS_EXTENSION
        ext.extension = []

        # Add verification level
        level_ext = Extension()
        level_ext.url = "level"
        level_ext.valueCode = level
        ext.extension.append(level_ext)

        # Add timestamp
        timestamp_ext = Extension()
        timestamp_ext.url = "timestamp"
        timestamp_ext.valueDateTime = FHIRDate(timestamp.isoformat())
        ext.extension.append(timestamp_ext)

        # Add verifier reference if provided
        if verifier_reference:
            verifier_ext = Extension()
            verifier_ext.url = "verifier"
            verifier_ext.valueReference = FHIRReference(
                {"reference": verifier_reference}
            )
            ext.extension.append(verifier_ext)

        return ext

    @staticmethod
    def parse_extension(extension: Extension) -> Dict[str, Any]:
        """Parse verification status extension into dictionary.

        Args:
            extension: FHIR Extension object

        Returns:
            Dictionary with parsed values
        """
        result: Dict[str, Any] = {}

        if not extension.extension:
            return result

        for sub_ext in extension.extension:
            if sub_ext.url == "level" and sub_ext.valueCode:
                result["level"] = sub_ext.valueCode
            elif sub_ext.url == "timestamp" and sub_ext.valueDateTime:
                result["timestamp"] = sub_ext.valueDateTime.as_json()
            elif sub_ext.url == "verifier" and sub_ext.valueReference:
                result["verifier_reference"] = sub_ext.valueReference.reference

        return result

    @staticmethod
    def get_level_display(level: str) -> str:
        """Get display text for verification level."""
        level_map = {
            "unverified": "Unverified",
            "basic": "Basic Verification",
            "standard": "Standard Verification",
            "enhanced": "Enhanced Verification",
            "full": "Full Verification",
        }
        return level_map.get(level, level)

    @staticmethod
    def validate_extension(extension_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate verification status extension data.

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
        elif extension_data["url"] != VERIFICATION_STATUS_EXTENSION:
            errors.append(f"Invalid extension URL: {extension_data['url']}")

        # Check for required sub-extensions
        if "extension" in extension_data:
            has_level = False
            has_timestamp = False

            for sub_ext in extension_data["extension"]:
                if sub_ext.get("url") == "level":
                    has_level = True
                    # Validate level value
                    level = sub_ext.get("valueCode")
                    valid_levels = [
                        "unverified",
                        "basic",
                        "standard",
                        "enhanced",
                        "full",
                    ]
                    if level and level not in valid_levels:
                        errors.append(f"Invalid verification level: {level}")
                elif sub_ext.get("url") == "timestamp":
                    has_timestamp = True

            if not has_level:
                errors.append("Verification status must have level")
            if not has_timestamp:
                errors.append("Verification status must have timestamp")

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
        validation_result = VerificationStatusExtension.validate_extension(
            extension_data
        )

        # Additional FHIR validation if needed
        if validation_result["valid"]:
            # Validate timestamp format if present
            if "extension" in extension_data:
                for sub_ext in extension_data["extension"]:
                    if sub_ext.get("url") == "timestamp" and "valueDateTime" in sub_ext:
                        # Basic datetime format check
                        try:
                            datetime.fromisoformat(
                                sub_ext["valueDateTime"].replace("Z", "+00:00")
                            )
                        except (ValueError, AttributeError):
                            validation_result["errors"].append(
                                "Invalid timestamp format"
                            )
                            validation_result["valid"] = False

        return validation_result

    @staticmethod
    def create_fhir_extension(
        level: str,
        timestamp: datetime,
        verifier_reference: Optional[str] = None,
    ) -> FHIRExtension:
        """Create FHIR Extension structure for verification status.

        Args:
            level: Verification level
            timestamp: When verification was performed
            verifier_reference: Reference to verifier

        Returns:
            FHIR Extension structure
        """
        extension: FHIRExtension = {
            "url": VERIFICATION_STATUS_EXTENSION,
            "extension": [],
            "__fhir_resource__": "Extension",
        }

        # Add verification level
        level_ext = {"url": "level", "valueCode": level}
        if extension["extension"] is not None:
            extension["extension"].append(level_ext)

        # Add timestamp
        timestamp_ext = {
            "url": "timestamp",
            "valueDateTime": timestamp.isoformat() + "Z",
        }
        if extension["extension"] is not None:
            extension["extension"].append(timestamp_ext)

        # Add verifier reference if provided
        if verifier_reference:
            verifier_ext = {
                "url": "verifier",
                "valueReference": {"reference": verifier_reference},
            }
            if extension["extension"] is not None:
                extension["extension"].append(verifier_ext)

        return extension


def validate_fhir(fhir_data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate FHIR data for verification status extensions.

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
        if fhir_data.get("url") != VERIFICATION_STATUS_EXTENSION:
            warnings.append(
                f"Expected URL {VERIFICATION_STATUS_EXTENSION}, got {fhir_data.get('url')}"
            )

        # Check for required sub-extensions
        if "extension" in fhir_data and isinstance(fhir_data["extension"], list):
            required_extensions = ["level", "timestamp"]
            for req in required_extensions:
                has_extension = any(
                    ext.get("url") == req for ext in fhir_data["extension"]
                )
                if not has_extension:
                    errors.append(
                        f"Verification status extension must include '{req}' sub-extension"
                    )

            # Validate verification level
            level_ext = next(
                (ext for ext in fhir_data["extension"] if ext.get("url") == "level"),
                None,
            )
            if level_ext and "valueCode" in level_ext:
                valid_levels = ["unverified", "basic", "standard", "enhanced", "full"]
                if level_ext["valueCode"] not in valid_levels:
                    errors.append(
                        f"Invalid verification level: {level_ext['valueCode']}"
                    )
        else:
            errors.append("Extension must have 'extension' array")
    else:
        errors.append("Not a valid FHIR Extension structure")

    return {"valid": len(errors) == 0, "errors": errors, "warnings": warnings}
