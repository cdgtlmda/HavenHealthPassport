"""Cultural context extension implementation.

This module handles FHIR Extension Resource validation for cultural context.
"""

from typing import Any, Dict, List, Optional

from fhirclient.models.codeableconcept import CodeableConcept
from fhirclient.models.coding import Coding
from fhirclient.models.extension import Extension

from ..fhir_profiles import CULTURAL_CONTEXT_EXTENSION

# FHIR resource type for this module
__fhir_resource__ = "Extension"


class CulturalContextExtension:
    """Handler for cultural context FHIR extension."""

    # FHIR resource type
    __fhir_resource__ = "Extension"

    @staticmethod
    def create_extension(
        dietary_restrictions: Optional[List[str]] = None,
        religious_affiliation: Optional[str] = None,
        gender_specific_requirements: Optional[List[str]] = None,
    ) -> Extension:
        """Create cultural context extension.

        Args:
            dietary_restrictions: List of dietary restriction codes
            religious_affiliation: Religious affiliation code
            gender_specific_requirements: List of requirements

        Returns:
            FHIR Extension object
        """
        ext = Extension()
        ext.url = CULTURAL_CONTEXT_EXTENSION
        ext.extension = []

        # Add dietary restrictions
        if dietary_restrictions:
            for restriction in dietary_restrictions:
                diet_ext = Extension()
                diet_ext.url = "dietaryRestrictions"
                diet_concept = CodeableConcept()
                diet_concept.coding = [
                    Coding(
                        {
                            "system": "https://havenhealthpassport.org/fhir/CodeSystem/dietary-restrictions",
                            "code": restriction,
                            "display": CulturalContextExtension._get_dietary_display(
                                restriction
                            ),
                        }
                    )
                ]
                diet_ext.valueCodeableConcept = diet_concept
                ext.extension.append(diet_ext)

        # Add religious affiliation
        if religious_affiliation:
            religion_ext = Extension()
            religion_ext.url = "religiousAffiliation"
            religion_concept = CodeableConcept()
            religion_concept.coding = [
                Coding(
                    {
                        "system": "http://terminology.hl7.org/CodeSystem/v3-ReligiousAffiliation",
                        "code": religious_affiliation,
                    }
                )
            ]
            religion_ext.valueCodeableConcept = religion_concept
            ext.extension.append(religion_ext)

        # Add gender-specific requirements
        if gender_specific_requirements:
            for requirement in gender_specific_requirements:
                gender_ext = Extension()
                gender_ext.url = "genderSpecificRequirements"
                gender_ext.valueString = requirement
                ext.extension.append(gender_ext)

        return ext

    @staticmethod
    def parse_extension(extension: Extension) -> Dict[str, Any]:
        """Parse cultural context extension into dictionary.

        Args:
            extension: FHIR Extension object

        Returns:
            Dictionary with parsed values
        """
        result: Dict[str, Any] = {
            "dietary_restrictions": [],
            "religious_affiliation": None,
            "gender_specific_requirements": [],
        }

        if not extension.extension:
            return result

        for sub_ext in extension.extension:
            if sub_ext.url == "dietaryRestrictions" and sub_ext.valueCodeableConcept:
                if sub_ext.valueCodeableConcept.coding:
                    if result["dietary_restrictions"] is not None:
                        result["dietary_restrictions"].append(
                            sub_ext.valueCodeableConcept.coding[0].code
                        )
            elif sub_ext.url == "religiousAffiliation" and sub_ext.valueCodeableConcept:
                if sub_ext.valueCodeableConcept.coding:
                    result["religious_affiliation"] = (
                        sub_ext.valueCodeableConcept.coding[0].code
                    )
            elif sub_ext.url == "genderSpecificRequirements" and sub_ext.valueString:
                if result["gender_specific_requirements"] is not None:
                    result["gender_specific_requirements"].append(sub_ext.valueString)

        return result

    @staticmethod
    def _get_dietary_display(code: str) -> str:
        """Get display text for dietary restriction code."""
        dietary_map = {
            "halal": "Halal",
            "kosher": "Kosher",
            "vegetarian": "Vegetarian",
            "vegan": "Vegan",
            "gluten-free": "Gluten Free",
            "lactose-free": "Lactose Free",
            "nut-allergy": "Nut Allergy",
            "diabetic": "Diabetic Diet",
        }
        return dietary_map.get(code, code)

    @staticmethod
    def validate_extension(extension_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate cultural context extension data.

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
        elif extension_data["url"] != CULTURAL_CONTEXT_EXTENSION:
            errors.append(f"Invalid extension URL: {extension_data['url']}")

        # Cultural context is optional, but validate sub-extensions if present
        if "extension" in extension_data:
            for sub_ext in extension_data["extension"]:
                url = sub_ext.get("url")
                if url == "dietaryRestrictions":
                    if not sub_ext.get("valueCodeableConcept"):
                        warnings.append(
                            "Dietary restriction should have valueCodeableConcept"
                        )
                elif url == "religiousAffiliation":
                    if not sub_ext.get("valueCodeableConcept"):
                        warnings.append(
                            "Religious affiliation should have valueCodeableConcept"
                        )
                elif url == "genderSpecificRequirements":
                    if not sub_ext.get("valueString"):
                        warnings.append("Gender requirement should have valueString")

        return {"valid": len(errors) == 0, "errors": errors, "warnings": warnings}


def validate_fhir(fhir_data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate FHIR data for cultural context extensions.

    Args:
        fhir_data: FHIR data to validate

    Returns:
        Validation results
    """
    # Use the existing validate_extension method
    return CulturalContextExtension.validate_extension(fhir_data)
