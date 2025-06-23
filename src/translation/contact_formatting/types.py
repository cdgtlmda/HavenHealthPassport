"""Contact formatting types and data classes."""

from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional


class AddressFormat(str, Enum):
    """Address formatting styles."""

    WESTERN = "western"  # Street, City, State, Country
    EASTERN = "eastern"  # Country, State, City, Street
    JAPANESE = "japanese"  # Postal code first
    MIDDLE_EASTERN = "middle_eastern"  # Various formats


@dataclass
class CountryPhoneFormat:
    """Phone number format for a country."""

    country_code: str
    international_prefix: str
    national_prefix: Optional[str]
    number_length: List[int]  # Valid lengths
    area_code_length: Optional[int]
    format_pattern: str  # e.g., "XXX-XXX-XXXX"
    mobile_prefixes: List[str]
    emergency_numbers: Dict[str, str]
    regex_patterns: List[str]  # Additional validation patterns


@dataclass
class CountryAddressFormat:
    """Address format for a country."""

    country_code: str
    format_order: List[str]  # Order of address components
    required_fields: List[str]
    postal_code_format: Optional[str]  # Regex pattern
    state_provinces: Optional[Dict[str, str]]  # Code -> Name
    address_format: AddressFormat
    local_terms: Dict[str, str]  # e.g., "state" -> "province"
    common_prefixes: List[str]  # Common street prefixes
    common_suffixes: List[str]  # Common street suffixes
