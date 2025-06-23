"""UNHCR registration extension implementation."""

from datetime import date
from typing import Any, Dict, Optional

from fhirclient.models.extension import Extension
from fhirclient.models.fhirdate import FHIRDate

from ..fhir_profiles import UNHCR_REGISTRATION_EXTENSION

# FHIR resource type for this module
__fhir_resource__ = "Extension"


class UNHCRRegistrationExtension:
    """Handler for UNHCR registration FHIR extension."""

    # FHIR resource type
    __fhir_resource__ = "Extension"

    @staticmethod
    def create_extension(
        registration_number: str,
        registration_date: Optional[date] = None,
        registration_office: Optional[str] = None,
    ) -> Extension:
        """Create UNHCR registration extension.

        Args:
            registration_number: UNHCR registration number
            registration_date: Date of registration
            registration_office: Office where registered

        Returns:
            FHIR Extension object
        """
        ext = Extension()
        ext.url = UNHCR_REGISTRATION_EXTENSION
        ext.extension = []

        # Add registration number
        number_ext = Extension()
        number_ext.url = "registrationNumber"
        number_ext.valueString = registration_number
        ext.extension.append(number_ext)

        # Add registration date if provided
        if registration_date:
            date_ext = Extension()
            date_ext.url = "registrationDate"
            date_ext.valueDate = FHIRDate(registration_date.isoformat())
            ext.extension.append(date_ext)

        # Add registration office if provided
        if registration_office:
            office_ext = Extension()
            office_ext.url = "registrationOffice"
            office_ext.valueString = registration_office
            ext.extension.append(office_ext)

        return ext

    @staticmethod
    def parse_extension(extension: Extension) -> Dict[str, Any]:
        """Parse UNHCR registration extension into dictionary.

        Args:
            extension: FHIR Extension object

        Returns:
            Dictionary with parsed values
        """
        result: Dict[str, Any] = {}

        if not extension.extension:
            return result

        for sub_ext in extension.extension:
            if sub_ext.url == "registrationNumber" and sub_ext.valueString:
                result["registration_number"] = sub_ext.valueString
            elif sub_ext.url == "registrationDate" and sub_ext.valueDate:
                result["registration_date"] = sub_ext.valueDate.as_json()
            elif sub_ext.url == "registrationOffice" and sub_ext.valueString:
                result["registration_office"] = sub_ext.valueString

        return result


def validate_fhir(fhir_data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate FHIR data for UNHCR registration extensions.

    Args:
        fhir_data: FHIR data to validate

    Returns:
        Validation results
    """
    errors = []
    warnings = []

    # Check if it's an Extension
    if (
        "__fhir_resource__" in fhir_data
        and fhir_data["__fhir_resource__"] != "Extension"
    ):
        errors.append("Resource must be Extension type")

    # Validate URL
    if "url" in fhir_data:
        if fhir_data["url"] != UNHCR_REGISTRATION_EXTENSION:
            warnings.append(
                f"Expected URL {UNHCR_REGISTRATION_EXTENSION}, got {fhir_data['url']}"
            )
    else:
        errors.append("Extension must have 'url' field")

    # Check for required sub-extensions
    if "extension" in fhir_data and isinstance(fhir_data["extension"], list):
        has_registration_number = any(
            ext.get("url") == "registrationNumber" for ext in fhir_data["extension"]
        )
        if not has_registration_number:
            errors.append(
                "UNHCR registration extension must include 'registrationNumber' sub-extension"
            )
    else:
        errors.append("Extension must have 'extension' array")

    return {"valid": len(errors) == 0, "errors": errors, "warnings": warnings}
