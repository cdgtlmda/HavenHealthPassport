"""Convenience functions for medical record formatting.

This module handles FHIR Resource formatting validation for patient contact information.
"""

from typing import Dict

from .address_formatter import AddressFormatter
from .name_formatter import NameFormatter
from .phone_formatter import PhoneNumberFormatter

# FHIR Resource validation for Patient contact data
# Validates DomainResource compliance for contact information


# Global formatter instances
phone_formatter = PhoneNumberFormatter()
address_formatter = AddressFormatter()
name_formatter = NameFormatter()


# Convenience functions for medical record formatting
def format_patient_name(
    name_parts: Dict[str, str], country_code: str, for_medical_record: bool = True
) -> str:
    """
    Format patient name for medical records.

    Args:
        name_parts: Name components
        country_code: Patient's country
        for_medical_record: If True, uses formal medical formatting

    Returns:
        Formatted name suitable for medical records
    """
    if for_medical_record:
        # Medical records often use FAMILY, Given format
        return name_formatter.format_name(
            name_parts, country_code, format_type="legal", formality="medical"
        )
    else:
        return name_formatter.format_name(
            name_parts, country_code, format_type="full", formality="formal"
        )


def format_patient_address(
    address_components: Dict[str, str], country_code: str, include_country: bool = True
) -> str:
    """
    Format patient address for medical records.

    Args:
        address_components: Address parts
        country_code: Country code
        include_country: Whether to include country name

    Returns:
        Formatted address suitable for medical records
    """
    formatted = address_formatter.format_address(
        address_components, country_code, format_type="postal"
    )

    if include_country and "country" not in address_components:
        # Add country name
        country_names = {
            "US": "United States",
            "GB": "United Kingdom",
            "IN": "India",
            "PK": "Pakistan",
            "BD": "Bangladesh",
            "AF": "Afghanistan",
            "SA": "Saudi Arabia",
            "AE": "United Arab Emirates",
            "EG": "Egypt",
            "IQ": "Iraq",
            "SY": "Syria",
            "IR": "Iran",
            "KE": "Kenya",
            "ET": "Ethiopia",
            "FR": "France",
            "DE": "Germany",
        }

        if country_code in country_names:
            formatted += f"\n{country_names[country_code]}"

    return formatted


def format_patient_phone(
    phone_number: str, country_code: str, include_country_code: bool = True
) -> str:
    """
    Format patient phone number for medical records.

    Args:
        phone_number: Phone number
        country_code: Country code
        include_country_code: Whether to include country code

    Returns:
        Formatted phone number suitable for medical records
    """
    if include_country_code:
        return phone_formatter.format_phone_number(
            phone_number, country_code, format_type="international"
        )
    else:
        return phone_formatter.format_phone_number(
            phone_number, country_code, format_type="national"
        )


def validate_patient_contact_info(contact_data: Dict[str, str]) -> bool:
    """
    Validate patient contact information for FHIR compliance.

    Args:
        contact_data: Dictionary containing patient contact information

    Returns:
        True if valid, False otherwise
    """
    # Basic validation for required fields
    required_fields = ["name", "phone", "address"]
    return all(field in contact_data for field in required_fields)
