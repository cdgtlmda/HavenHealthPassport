"""Multi-language name extension implementation.

This module handles FHIR Extension Resource validation for multi-language names.
"""

from typing import Any, Dict, Literal, Optional, TypedDict

from fhirclient.models.extension import Extension
from fhirclient.models.humanname import HumanName

from ..fhir_profiles import MULTI_LANGUAGE_NAME_EXTENSION

# FHIR resource type for this module
__fhir_resource__ = "Extension"


class FHIRExtension(TypedDict, total=False):
    """FHIR Extension resource type definition."""

    url: str
    valueCode: Optional[str]
    valueString: Optional[str]
    extension: Optional[list[Dict[str, Any]]]
    __fhir_resource__: Literal["Extension"]


class MultiLanguageNameExtension:
    """Handler for multi-language name FHIR extension."""

    # FHIR resource type
    __fhir_resource__ = "Extension"

    @staticmethod
    def create_extension(
        language: str,
        script: Optional[str] = None,
        pronunciation_guide: Optional[str] = None,
    ) -> Extension:
        """Create multi-language name extension.

        Args:
            language: BCP 47 language code (e.g., 'ar', 'en', 'fr')
            script: ISO 15924 script code (e.g., 'Arab', 'Latn', 'Cyrl')
            pronunciation_guide: IPA or phonetic pronunciation

        Returns:
            FHIR Extension object
        """
        ext = Extension()
        ext.url = MULTI_LANGUAGE_NAME_EXTENSION
        ext.extension = []

        # Add language
        lang_ext = Extension()
        lang_ext.url = "language"
        lang_ext.valueCode = language
        ext.extension.append(lang_ext)

        # Add script if provided
        if script:
            script_ext = Extension()
            script_ext.url = "script"
            script_ext.valueCode = script
            ext.extension.append(script_ext)

        # Add pronunciation guide if provided
        if pronunciation_guide:
            pronunciation_ext = Extension()
            pronunciation_ext.url = "pronunciationGuide"
            pronunciation_ext.valueString = pronunciation_guide
            ext.extension.append(pronunciation_ext)

        return ext

    @staticmethod
    def parse_extension(extension: Extension) -> Dict[str, Any]:
        """Parse multi-language name extension into dictionary.

        Args:
            extension: FHIR Extension object

        Returns:
            Dictionary with parsed values
        """
        result: Dict[str, Any] = {}

        if not extension.extension:
            return result

        for sub_ext in extension.extension:
            if sub_ext.url == "language" and sub_ext.valueCode:
                result["language"] = sub_ext.valueCode
            elif sub_ext.url == "script" and sub_ext.valueCode:
                result["script"] = sub_ext.valueCode
            elif sub_ext.url == "pronunciationGuide" and sub_ext.valueString:
                result["pronunciation_guide"] = sub_ext.valueString

        return result

    @staticmethod
    def apply_to_name(
        name: HumanName,
        language: str,
        script: Optional[str] = None,
        pronunciation_guide: Optional[str] = None,
    ) -> None:
        """Apply multi-language extension to a HumanName.

        Args:
            name: HumanName object to extend
            language: BCP 47 language code
            script: ISO 15924 script code
            pronunciation_guide: Pronunciation guide
        """
        if not name.extension:
            name.extension = []

        ext = MultiLanguageNameExtension.create_extension(
            language, script, pronunciation_guide
        )
        name.extension.append(ext)

    @staticmethod
    def validate_extension(extension_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate multi-language name extension data.

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
        elif extension_data["url"] != MULTI_LANGUAGE_NAME_EXTENSION:
            errors.append(f"Invalid extension URL: {extension_data['url']}")

        # Check for language sub-extension
        if "extension" in extension_data:
            has_language = False
            for sub_ext in extension_data["extension"]:
                if sub_ext.get("url") == "language" and sub_ext.get("valueCode"):
                    has_language = True
                    # Basic language code validation
                    lang_code = sub_ext["valueCode"]
                    if not 2 <= len(lang_code) <= 3:
                        warnings.append(f"Unusual language code length: {lang_code}")
                    break
            if not has_language:
                errors.append("Multi-language name must have language code")

        return {"valid": len(errors) == 0, "errors": errors, "warnings": warnings}


def validate_fhir(fhir_data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate FHIR data for multi-language name extensions.

    Args:
        fhir_data: FHIR data to validate

    Returns:
        Validation results
    """
    # Use the existing validate_extension method
    return MultiLanguageNameExtension.validate_extension(fhir_data)
