"""Phone and Address Format Management.

This module handles phone number and address formatting for different
countries and regions in healthcare contexts.
"""

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from src.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class PhoneFormat:
    """Phone number format specification."""

    country_code: str
    country_name: str
    international_prefix: str
    national_prefix: str
    number_pattern: str
    display_format: str
    example: str
    mobile_prefixes: List[str]
    emergency_numbers: List[str]


@dataclass
class AddressFormat:
    """Address format specification."""

    country_code: str
    format_lines: List[str]  # Template lines
    required_fields: List[str]
    optional_fields: List[str]
    postal_code_pattern: str
    state_required: bool
    city_before_state: bool


class PhoneFormatter:
    """Formats phone numbers for different countries."""

    # Phone formats by country
    PHONE_FORMATS = {
        "US": PhoneFormat(
            country_code="1",
            country_name="United States",
            international_prefix="+1",
            national_prefix="1",
            number_pattern=r"^\d{10}$",
            display_format="(###) ###-####",
            example="(555) 123-4567",
            mobile_prefixes=[],  # No specific mobile prefixes
            emergency_numbers=["911"],
        ),
        "KE": PhoneFormat(
            country_code="254",
            country_name="Kenya",
            international_prefix="+254",
            national_prefix="0",
            number_pattern=r"^\d{9}$",
            display_format="### ### ###",
            example="712 345 678",
            mobile_prefixes=["7", "1"],
            emergency_numbers=["999", "911", "112"],
        ),
        "JO": PhoneFormat(
            country_code="962",
            country_name="Jordan",
            international_prefix="+962",
            national_prefix="0",
            number_pattern=r"^\d{8,9}$",
            display_format="# #### ####",
            example="7 9123 4567",
            mobile_prefixes=["7"],
            emergency_numbers=["911"],
        ),
        "BD": PhoneFormat(
            country_code="880",
            country_name="Bangladesh",
            international_prefix="+880",
            national_prefix="0",
            number_pattern=r"^\d{10}$",
            display_format="#### ######",
            example="1712 345678",
            mobile_prefixes=["1"],
            emergency_numbers=["999"],
        ),
        "PK": PhoneFormat(
            country_code="92",
            country_name="Pakistan",
            international_prefix="+92",
            national_prefix="0",
            number_pattern=r"^\d{10}$",
            display_format="### #######",
            example="300 1234567",
            mobile_prefixes=["3"],
            emergency_numbers=["15", "115", "1122"],
        ),
        "SY": PhoneFormat(
            country_code="963",
            country_name="Syria",
            international_prefix="+963",
            national_prefix="0",
            number_pattern=r"^\d{8,9}$",
            display_format="## ### ####",
            example="93 312 3456",
            mobile_prefixes=["9"],
            emergency_numbers=["110", "113"],
        ),
        "AF": PhoneFormat(
            country_code="93",
            country_name="Afghanistan",
            international_prefix="+93",
            national_prefix="0",
            number_pattern=r"^\d{9}$",
            display_format="## ### ####",
            example="70 123 4567",
            mobile_prefixes=["7"],
            emergency_numbers=["119", "102"],
        ),
    }

    def format_phone_number(
        self, number: str, country_code: str, international: bool = False
    ) -> Optional[str]:
        """Format phone number according to country standards."""
        format_spec = self.PHONE_FORMATS.get(country_code)
        if not format_spec:
            return number

        # Clean number
        clean_number = re.sub(r"\D", "", number)

        # Remove country code if present
        if clean_number.startswith(format_spec.country_code):
            clean_number = clean_number[len(format_spec.country_code) :]

        # Remove national prefix if present
        if clean_number.startswith(format_spec.national_prefix):
            clean_number = clean_number[len(format_spec.national_prefix) :]

        # Validate length
        if not re.match(format_spec.number_pattern, clean_number):
            logger.warning(f"Invalid phone number format for {country_code}: {number}")
            return None

        # Format number
        if international:
            formatted = format_spec.international_prefix + " "
            # Apply display format without country code
            formatted += self._apply_format(clean_number, format_spec.display_format)
        else:
            # Apply national format
            if format_spec.national_prefix and format_spec.national_prefix != "0":
                formatted = format_spec.national_prefix + " "
            else:
                formatted = ""
            formatted += self._apply_format(clean_number, format_spec.display_format)

        return formatted

    def _apply_format(self, number: str, format_template: str) -> str:
        """Apply format template to number."""
        result = ""
        num_idx = 0

        for char in format_template:
            if char == "#":
                if num_idx < len(number):
                    result += number[num_idx]
                    num_idx += 1
            else:
                result += char

        return result

    def validate_phone_number(
        self, number: str, country_code: str
    ) -> Tuple[bool, Optional[str]]:
        """Validate phone number format."""
        format_spec = self.PHONE_FORMATS.get(country_code)
        if not format_spec:
            return False, "Unknown country code"

        # Clean number
        clean_number = re.sub(r"\D", "", number)

        # Remove country code if present
        if clean_number.startswith(format_spec.country_code):
            clean_number = clean_number[len(format_spec.country_code) :]

        # Remove national prefix
        if clean_number.startswith(format_spec.national_prefix):
            clean_number = clean_number[len(format_spec.national_prefix) :]

        # Check pattern
        if not re.match(format_spec.number_pattern, clean_number):
            return False, f"Invalid format. Example: {format_spec.example}"

        # Check mobile prefix if applicable
        if format_spec.mobile_prefixes:
            if not any(
                clean_number.startswith(prefix)
                for prefix in format_spec.mobile_prefixes
            ):
                return (
                    False,
                    f"Number should start with: {', '.join(format_spec.mobile_prefixes)}",
                )

        return True, None

    def get_emergency_numbers(self, country_code: str) -> List[str]:
        """Get emergency numbers for a country."""
        format_spec = self.PHONE_FORMATS.get(country_code)
        if format_spec:
            return format_spec.emergency_numbers
        return ["112"]  # International emergency number


class AddressFormatter:
    """Formats addresses for different countries."""

    # Address formats by country
    ADDRESS_FORMATS = {
        "US": AddressFormat(
            country_code="US",
            format_lines=[
                "{name}",
                "{street_address}",
                "{city}, {state} {postal_code}",
                "{country}",
            ],
            required_fields=["street_address", "city", "state", "postal_code"],
            optional_fields=["name", "apartment", "country"],
            postal_code_pattern=r"^\d{5}(-\d{4})?$",
            state_required=True,
            city_before_state=True,
        ),
        "GB": AddressFormat(
            country_code="GB",
            format_lines=[
                "{name}",
                "{street_address}",
                "{city}",
                "{postal_code}",
                "{country}",
            ],
            required_fields=["street_address", "city", "postal_code"],
            optional_fields=["name", "county", "country"],
            postal_code_pattern=r"^[A-Z]{1,2}\d[A-Z\d]? ?\d[A-Z]{2}$",
            state_required=False,
            city_before_state=True,
        ),
        "KE": AddressFormat(
            country_code="KE",
            format_lines=[
                "{name}",
                "{street_address}",
                "{city}",
                "{postal_code}",
                "{country}",
            ],
            required_fields=["street_address", "city"],
            optional_fields=["name", "postal_code", "country"],
            postal_code_pattern=r"^\d{5}$",
            state_required=False,
            city_before_state=True,
        ),
        "JO": AddressFormat(
            country_code="JO",
            format_lines=[
                "{name}",
                "{street_address}",
                "{city} {postal_code}",
                "{country}",
            ],
            required_fields=["street_address", "city"],
            optional_fields=["name", "postal_code", "country"],
            postal_code_pattern=r"^\d{5}$",
            state_required=False,
            city_before_state=True,
        ),
    }

    def format_address(
        self,
        address_data: Dict[str, str],
        country_code: str,
        include_country: bool = True,
    ) -> List[str]:
        """Format address according to country standards."""
        format_spec = self.ADDRESS_FORMATS.get(country_code)
        if not format_spec:
            # Default format
            return self._format_default(address_data)

        formatted_lines = []

        for line_template in format_spec.format_lines:
            # Skip country line if not needed
            if "{country}" in line_template and not include_country:
                continue

            # Replace placeholders
            line = line_template
            for field, value in address_data.items():
                placeholder = f"{{{field}}}"
                if placeholder in line:
                    line = line.replace(placeholder, value or "")

            # Remove empty placeholders
            line = re.sub(r"\{[^}]+\}", "", line)

            # Clean up extra spaces and punctuation
            line = re.sub(r"\s+", " ", line).strip()
            line = re.sub(r",\s*,", ",", line)
            line = re.sub(r",\s*$", "", line)

            if line:
                formatted_lines.append(line)

        return formatted_lines

    def _format_default(self, address_data: Dict[str, str]) -> List[str]:
        """Format address using default layout."""
        lines = []

        if address_data.get("name"):
            lines.append(address_data["name"])

        if address_data.get("street_address"):
            lines.append(address_data["street_address"])

        city_line = ""
        if address_data.get("city"):
            city_line = address_data["city"]

        if address_data.get("state"):
            if city_line:
                city_line += f", {address_data['state']}"
            else:
                city_line = address_data["state"]

        if address_data.get("postal_code"):
            if city_line:
                city_line += f" {address_data['postal_code']}"
            else:
                city_line = address_data["postal_code"]

        if city_line:
            lines.append(city_line)

        if address_data.get("country"):
            lines.append(address_data["country"])

        return lines

    def validate_postal_code(
        self, postal_code: str, country_code: str
    ) -> Tuple[bool, Optional[str]]:
        """Validate postal code format."""
        format_spec = self.ADDRESS_FORMATS.get(country_code)
        if not format_spec:
            return True, None  # No validation for unknown countries

        if not format_spec.postal_code_pattern:
            return True, None

        if not re.match(format_spec.postal_code_pattern, postal_code):
            return False, f"Invalid postal code format for {country_code}"

        return True, None

    def get_address_fields(self, country_code: str) -> Dict[str, Any]:
        """Get address field requirements for a country."""
        format_spec = self.ADDRESS_FORMATS.get(country_code)
        if not format_spec:
            # Default fields
            return {
                "required": ["street_address", "city"],
                "optional": ["name", "state", "postal_code", "country"],
                "state_required": False,
            }

        return {
            "required": format_spec.required_fields,
            "optional": format_spec.optional_fields,
            "state_required": format_spec.state_required,
            "postal_code_pattern": format_spec.postal_code_pattern,
        }


# Global instances
phone_formatter = PhoneFormatter()
address_formatter = AddressFormatter()
