"""Cross-border access extension implementation.

This module handles FHIR Extension Resource validation for cross-border access.
"""

from datetime import date
from typing import Any, Dict, List, Optional, Tuple, cast

from fhirclient.models.codeableconcept import CodeableConcept
from fhirclient.models.coding import Coding
from fhirclient.models.extension import Extension
from fhirclient.models.fhirdate import FHIRDate
from fhirclient.models.period import Period

from ..fhir_profiles import CROSS_BORDER_ACCESS_EXTENSION

# FHIR resource type for this module
__fhir_resource__ = "Extension"


class CrossBorderAccessExtension:
    """Handler for cross-border access FHIR extension."""

    # FHIR resource type
    __fhir_resource__ = "Extension"

    @staticmethod
    def create_extension(
        countries: List[str],
        duration: Optional[Tuple[date, date]] = None,
        emergency_access: bool = False,
    ) -> Extension:
        """Create cross-border access extension.

        Args:
            countries: List of ISO 3166-1 alpha-2 country codes
            duration: Tuple of (start_date, end_date) for access period
            emergency_access: Whether emergency access is granted

        Returns:
            FHIR Extension object
        """
        ext = Extension()
        ext.url = CROSS_BORDER_ACCESS_EXTENSION
        ext.extension = []

        # Add countries
        for country_code in countries:
            country_ext = Extension()
            country_ext.url = "countries"
            country_concept = CodeableConcept()
            country_concept.coding = [
                Coding(
                    {
                        "system": "urn:iso:std:iso:3166",
                        "code": country_code,
                    }
                )
            ]
            country_ext.valueCodeableConcept = country_concept
            ext.extension.append(country_ext)

        # Add duration if provided
        if duration:
            duration_ext = Extension()
            duration_ext.url = "duration"
            period = Period()
            period.start = FHIRDate(duration[0].isoformat())
            period.end = FHIRDate(duration[1].isoformat())
            duration_ext.valuePeriod = period
            ext.extension.append(duration_ext)

        # Add emergency access flag
        emergency_ext = Extension()
        emergency_ext.url = "emergencyAccess"
        emergency_ext.valueBoolean = emergency_access
        ext.extension.append(emergency_ext)

        return ext

    @staticmethod
    def parse_extension(extension: Extension) -> Dict[str, Any]:
        """Parse cross-border access extension into dictionary.

        Args:
            extension: FHIR Extension object

        Returns:
            Dictionary with parsed values
        """
        result: Dict[str, Any] = {
            "countries": [],
            "emergency_access": False,
        }

        if not extension.extension:
            return result

        for sub_ext in extension.extension:
            if sub_ext.url == "countries" and sub_ext.valueCodeableConcept:
                if sub_ext.valueCodeableConcept.coding:
                    cast(list, result["countries"]).append(
                        sub_ext.valueCodeableConcept.coding[0].code
                    )
            elif sub_ext.url == "duration" and sub_ext.valuePeriod:
                result["duration"] = {
                    "start": (
                        sub_ext.valuePeriod.start.as_json()
                        if sub_ext.valuePeriod.start
                        else None
                    ),
                    "end": (
                        sub_ext.valuePeriod.end.as_json()
                        if sub_ext.valuePeriod.end
                        else None
                    ),
                }
            elif sub_ext.url == "emergencyAccess":
                result["emergency_access"] = sub_ext.valueBoolean

        return result

    @staticmethod
    def validate_extension(extension_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate cross-border access extension data.

        Args:
            extension_data: Extension data to validate

        Returns:
            Validation result with 'valid', 'errors', and 'warnings' keys
        """
        errors = []
        warnings = []

        # Check required fields
        if not extension_data.get("url"):
            errors.append("Extension must have url")
        elif extension_data["url"] != CROSS_BORDER_ACCESS_EXTENSION:
            errors.append(f"Invalid extension URL: {extension_data['url']}")

        # Check for countries sub-extension
        if "extension" in extension_data:
            has_countries = False
            for sub_ext in extension_data["extension"]:
                if sub_ext.get("url") == "countries":
                    has_countries = True
                    # Validate country code format
                    if "valueCodeableConcept" in sub_ext:
                        concept = sub_ext["valueCodeableConcept"]
                        if "coding" in concept and len(concept["coding"]) > 0:
                            code = concept["coding"][0].get("code", "")
                            if len(code) != 2:
                                warnings.append(
                                    f"Country code should be ISO 3166-1 alpha-2: {code}"
                                )
                    break

            if not has_countries:
                warnings.append("Cross-border access should specify countries")

        return {"valid": len(errors) == 0, "errors": errors, "warnings": warnings}


def validate_fhir(fhir_data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate FHIR data for cross-border access extensions.

    Args:
        fhir_data: FHIR data to validate

    Returns:
        Validation results
    """
    # Use the existing validate_extension method
    return CrossBorderAccessExtension.validate_extension(fhir_data)
