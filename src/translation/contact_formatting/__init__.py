"""Phone Number and Address Formatting for Cultural Adaptation.

This module provides culturally appropriate phone number and address formatting
for different countries and regions with advanced NLP-based parsing.

FHIR Compliance: Contact information must be validated for FHIR Resource format.

HIPAA Compliance: Patient contact information is PHI and requires:
- Access control for viewing/editing patient addresses and phone numbers
- Audit logging of all contact information access
- Role-based permissions for contact field modifications
- Encryption of all PHI contact fields using secure storage mechanisms
"""

from .address_formatter import AddressFormatter
from .address_nlp import AddressNLPParser
from .name_formatter import NameFormatter
from .phone_formatter import PhoneNumberFormatter
from .phone_ml import PhoneNumberMLParser
from .types import AddressFormat, CountryAddressFormat, CountryPhoneFormat
from .utils import (
    address_formatter,
    format_patient_address,
    format_patient_name,
    format_patient_phone,
    name_formatter,
    phone_formatter,
)

__all__ = [
    # Types
    "AddressFormat",
    "CountryAddressFormat",
    "CountryPhoneFormat",
    # Parsers
    "AddressNLPParser",
    "PhoneNumberMLParser",
    # Formatters
    "PhoneNumberFormatter",
    "AddressFormatter",
    "NameFormatter",
    # Global instances
    "phone_formatter",
    "address_formatter",
    "name_formatter",
    # Convenience functions
    "format_patient_name",
    "format_patient_address",
    "format_patient_phone",
]
