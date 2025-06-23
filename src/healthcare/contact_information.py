"""Patient Contact Information Configuration.

This module defines contact information structures and validation for patients,
including phone numbers, email addresses, and emergency contacts with special
considerations for refugee populations and limited connectivity scenarios.
"""

import logging
import re
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, cast

try:
    import phonenumbers
    from phonenumbers import NumberParseException

    PHONENUMBERS_AVAILABLE = True
except ImportError:
    phonenumbers = None
    NumberParseException = Exception
    PHONENUMBERS_AVAILABLE = False

from src.healthcare.fhir_types import FHIRContactPoint as FHIRContactPointType
from src.healthcare.fhir_types import (
    FHIRTypedResource,
)
from src.healthcare.fhir_validator import FHIRValidator
from src.healthcare.hipaa_access_control import (
    AccessLevel,
    audit_phi_access,
    require_phi_access,
)

# FHIR resource type for this module
__fhir_resource__ = "ContactPoint"
__fhir_type__ = "ContactPoint"

# This module handles encrypted PHI contact information

logger = logging.getLogger(__name__)


class FHIRContactPoint(FHIRContactPointType):
    """FHIR ContactPoint resource type definition."""

    # Additional Haven-specific fields can be added here


class ContactSystem(Enum):
    """Contact point system types."""

    PHONE = "phone"
    FAX = "fax"
    EMAIL = "email"
    PAGER = "pager"
    URL = "url"
    SMS = "sms"
    OTHER = "other"

    # Extended for refugee contexts
    WHATSAPP = "whatsapp"
    TELEGRAM = "telegram"
    SIGNAL = "signal"
    RADIO = "radio"
    SATELLITE = "satellite"
    CAMP_PHONE = "camp-phone"
    NGO_CONTACT = "ngo-contact"


class ContactUse(Enum):
    """Contact point use types."""

    HOME = "home"
    WORK = "work"
    TEMP = "temp"
    OLD = "old"
    MOBILE = "mobile"

    # Extended for refugee contexts
    CAMP = "camp"
    EMERGENCY = "emergency"
    FAMILY = "family"
    NGO = "ngo"
    COMMUNITY = "community"
    TRANSIT = "transit"


class ContactPointPriority(Enum):
    """Contact priority levels."""

    PRIMARY = 1
    SECONDARY = 2
    TERTIARY = 3
    EMERGENCY_ONLY = 4
    LAST_RESORT = 5


class CountryPhoneConfig:
    """Phone number configurations by country/region."""

    CONFIGS = {
        # Major refugee hosting countries
        "KE": {  # Kenya
            "name": "Kenya",
            "code": "+254",
            "format": "XXX XXX XXX",
            "mobile_prefixes": ["7", "1"],
            "emergency": "999",
            "providers": ["Safaricom", "Airtel", "Telkom"],
        },
        "UG": {  # Uganda
            "name": "Uganda",
            "code": "+256",
            "format": "XXX XXX XXX",
            "mobile_prefixes": ["7", "3"],
            "emergency": "999",
            "providers": ["MTN", "Airtel", "Africell"],
        },
        "ET": {  # Ethiopia
            "name": "Ethiopia",
            "code": "+251",
            "format": "XX XXX XXXX",
            "mobile_prefixes": ["9"],
            "emergency": "911",
            "providers": ["Ethio Telecom"],
        },
        "JO": {  # Jordan
            "name": "Jordan",
            "code": "+962",
            "format": "X XXXX XXXX",
            "mobile_prefixes": ["7", "8"],
            "emergency": "911",
            "providers": ["Zain", "Orange", "Umniah"],
        },
        "LB": {  # Lebanon
            "name": "Lebanon",
            "code": "+961",
            "format": "X XXX XXX",
            "mobile_prefixes": ["3", "7", "8"],
            "emergency": "112",
            "providers": ["Alfa", "Touch"],
        },
        "TR": {  # Turkey
            "name": "Turkey",
            "code": "+90",
            "format": "XXX XXX XX XX",
            "mobile_prefixes": ["5"],
            "emergency": "112",
            "providers": ["Turkcell", "Vodafone", "Türk Telekom"],
        },
        "BD": {  # Bangladesh
            "name": "Bangladesh",
            "code": "+880",
            "format": "XXXX XXXXXX",
            "mobile_prefixes": ["1"],
            "emergency": "999",
            "providers": ["Grameenphone", "Robi", "Banglalink"],
        },
        "PK": {  # Pakistan
            "name": "Pakistan",
            "code": "+92",
            "format": "XXX XXXXXXX",
            "mobile_prefixes": ["3"],
            "emergency": "15",
            "providers": ["Jazz", "Telenor", "Zong", "Ufone"],
        },
    }

    @classmethod
    def get_config(cls, country_code: str) -> Optional[Dict]:
        """Get phone configuration for a country."""
        return cls.CONFIGS.get(country_code.upper())

    @classmethod
    def format_number(cls, number: str, country_code: str) -> str:
        """Format phone number according to country standards."""
        config = cls.get_config(country_code)
        if not config:
            return number

        # Remove country code if present
        clean_number = number.replace(config["code"], "").strip()
        clean_number = re.sub(r"[^\d]", "", clean_number)

        # Apply format pattern
        digit_groups = []
        digits = list(clean_number)

        for char in config["format"]:
            if char == "X" and digits:
                digit_groups.append(digits.pop(0))
            elif char == " ":
                digit_groups.append(" ")

        return "".join(digit_groups)


class ContactValidator(FHIRTypedResource):
    """Validation for contact information."""

    # FHIR resource type
    __fhir_resource__ = "ContactPoint"

    # Email regex pattern
    EMAIL_PATTERN = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")

    # URL pattern
    URL_PATTERN = re.compile(r"^https?://[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}.*$")

    # WhatsApp number pattern (same as phone)
    WHATSAPP_PATTERN = re.compile(r"^\+?[\d\s\-\(\)]+$")

    @property
    def __fhir_resource_type__(self) -> str:
        """Return the FHIR resource type."""
        return "ContactPoint"

    def validate_fhir(self) -> Dict[str, Any]:
        """Validate the FHIR resource (required by FHIRTypedResource)."""
        # This is a validator class, not a resource instance
        return {"valid": True, "errors": [], "warnings": []}

    @classmethod
    def validate_phone_number(
        cls, number: str, country_code: Optional[str] = None
    ) -> Tuple[bool, Optional[str]]:
        """Validate phone number.

        Args:
            number: Phone number to validate
            country_code: Optional ISO country code

        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            # Try to parse with phonenumbers library if available
            if PHONENUMBERS_AVAILABLE:
                if country_code:
                    parsed = phonenumbers.parse(number, country_code)
                else:
                    # Try to parse as international number
                    parsed = phonenumbers.parse(number, None)

                if not phonenumbers.is_valid_number(parsed):
                    return False, "Invalid phone number format"

                return True, None
            else:
                raise ValueError("phonenumbers library not available")

        except (NumberParseException, ValueError):
            # Fallback validation for refugee contexts where numbers might be non-standard
            clean_number = re.sub(r"[^\d+]", "", number)

            # Basic validation: must have at least 5 digits
            if len(re.sub(r"[^\d]", "", clean_number)) < 5:
                return False, "Phone number too short"

            # Check if it looks like a phone number
            if not re.match(r"^\+?[\d\s\-\(\)]+$", number):
                return False, "Invalid characters in phone number"

            # Accept with warning for non-standard numbers
            logger.warning("Non-standard phone number accepted: %s", number)
            return True, None

    @classmethod
    def validate_email(cls, email: str) -> Tuple[bool, Optional[str]]:
        """Validate email address.

        Args:
            email: Email address to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not email:
            return False, "Email address cannot be empty"

        if not cls.EMAIL_PATTERN.match(email.lower()):
            return False, "Invalid email format"

        # Check for common typos
        if email.count("@") != 1:
            return False, "Email must contain exactly one @ symbol"

        local, domain = email.split("@")

        # Check local part
        if len(local) > 64:
            return False, "Email local part too long"

        # Check domain
        if len(domain) > 255:
            return False, "Email domain too long"

        return True, None

    @classmethod
    def validate_url(cls, url: str) -> Tuple[bool, Optional[str]]:
        """Validate URL.

        Args:
            url: URL to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not url:
            return False, "URL cannot be empty"

        if not cls.URL_PATTERN.match(url):
            return False, "Invalid URL format"

        return True, None

    @classmethod
    def validate_contact_point(cls, contact: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """Validate complete contact point.

        Args:
            contact: Contact point dictionary

        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []

        # Required fields
        if "system" not in contact:
            errors.append("Contact system is required")
        if "value" not in contact:
            errors.append("Contact value is required")

        if errors:
            return False, errors

        # Validate based on system
        system = contact["system"]
        value = contact["value"]

        if system in ["phone", "sms", "fax"]:
            is_valid, error = cls.validate_phone_number(value)
            if not is_valid:
                errors.append(f"Phone validation failed: {error}")

        elif system == "email":
            is_valid, error = cls.validate_email(value)
            if not is_valid:
                errors.append(f"Email validation failed: {error}")

        elif system == "url":
            is_valid, error = cls.validate_url(value)
            if not is_valid:
                errors.append(f"URL validation failed: {error}")

        elif system == "whatsapp":
            # WhatsApp uses phone numbers
            is_valid, error = cls.validate_phone_number(value)
            if not is_valid:
                errors.append(f"WhatsApp number validation failed: {error}")

        return len(errors) == 0, errors


class EmergencyContact:
    """Emergency contact information structure."""

    def __init__(self) -> None:
        """Initialize emergency contact."""
        self.name: Optional[str] = None
        self.relationship: Optional[str] = None
        self.contacts: List[Dict] = []
        self.languages: List[str] = []
        self.notes: Optional[str] = None
        self.priority: ContactPointPriority = ContactPointPriority.PRIMARY

    @require_phi_access(AccessLevel.WRITE)
    @audit_phi_access("add_emergency_contact")
    def add_contact(
        self, system: ContactSystem, value: str, use: ContactUse = ContactUse.EMERGENCY
    ) -> "EmergencyContact":
        """Add a contact method."""
        contact = {"system": system.value, "value": value, "use": use.value}

        # Validate before adding
        is_valid, errors = ContactValidator.validate_contact_point(contact)
        if not is_valid:
            raise ValueError(f"Invalid contact: {', '.join(errors)}")

        self.contacts.append(contact)
        return self

    @require_phi_access(AccessLevel.WRITE)
    @audit_phi_access("set_emergency_contact_name")
    def set_name(self, name: str) -> "EmergencyContact":
        """Set contact name."""
        self.name = name
        return self

    def set_relationship(self, relationship: str) -> "EmergencyContact":
        """Set relationship to patient."""
        self.relationship = relationship
        return self

    def add_language(self, language: str) -> "EmergencyContact":
        """Add spoken language."""
        self.languages.append(language)
        return self

    def set_priority(self, priority: ContactPointPriority) -> "EmergencyContact":
        """Set contact priority."""
        self.priority = priority
        return self

    def set_notes(self, notes: str) -> "EmergencyContact":
        """Set additional notes."""
        self.notes = notes
        return self

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "name": self.name,
            "relationship": self.relationship,
            "contacts": self.contacts,
            "languages": self.languages,
            "priority": self.priority.value,
            "notes": self.notes,
        }


class ContactBuilder:
    """Builder for patient contact information."""

    def __init__(self) -> None:
        """Initialize contact builder."""
        self.contacts: List[Dict] = []
        self.emergency_contacts: List[EmergencyContact] = []

    @require_phi_access(AccessLevel.WRITE)
    @audit_phi_access("add_patient_phone")
    def add_phone(
        self,
        number: str,
        use: ContactUse = ContactUse.MOBILE,
        country_code: Optional[str] = None,
    ) -> "ContactBuilder":
        """Add phone number."""
        # Validate and format
        is_valid, error = ContactValidator.validate_phone_number(number, country_code)
        if not is_valid:
            raise ValueError(f"Invalid phone number: {error}")

        # Format if country code provided
        if country_code:
            formatted = CountryPhoneConfig.format_number(number, country_code)
        else:
            formatted = number

        contact = {
            "system": ContactSystem.PHONE.value,
            "value": formatted,
            "use": use.value,
        }

        self.contacts.append(contact)
        return self

    @require_phi_access(AccessLevel.WRITE)
    @audit_phi_access("add_patient_email")
    def add_email(
        self, email: str, use: ContactUse = ContactUse.HOME
    ) -> "ContactBuilder":
        """Add email address."""
        is_valid, error = ContactValidator.validate_email(email)
        if not is_valid:
            raise ValueError(f"Invalid email: {error}")

        contact = {
            "system": ContactSystem.EMAIL.value,
            "value": email.lower(),
            "use": use.value,
        }

        self.contacts.append(contact)
        return self

    @require_phi_access(AccessLevel.WRITE)
    @audit_phi_access("add_patient_whatsapp")
    def add_whatsapp(
        self, number: str, country_code: Optional[str] = None
    ) -> "ContactBuilder":
        """Add WhatsApp number."""
        is_valid, error = ContactValidator.validate_phone_number(number, country_code)
        if not is_valid:
            raise ValueError(f"Invalid WhatsApp number: {error}")

        contact = {
            "system": ContactSystem.WHATSAPP.value,
            "value": number,
            "use": ContactUse.MOBILE.value,
        }

        self.contacts.append(contact)
        return self

    def add_camp_phone(self, number: str, camp_name: str) -> "ContactBuilder":
        """Add camp phone number."""
        contact = {
            "system": ContactSystem.CAMP_PHONE.value,
            "value": number,
            "use": ContactUse.CAMP.value,
            "extension": [
                {
                    "url": "http://havenhealthpassport.org/fhir/extension/camp-name",
                    "valueString": camp_name,
                }
            ],
        }

        self.contacts.append(contact)
        return self

    def add_emergency_contact(
        self, emergency_contact: EmergencyContact
    ) -> "ContactBuilder":
        """Add emergency contact."""
        self.emergency_contacts.append(emergency_contact)
        return self

    def build(self) -> Dict[str, Any]:
        """Build contact information structure."""
        result = {"telecom": self.contacts}

        if self.emergency_contacts:
            result["emergency_contacts"] = [
                contact.to_dict() for contact in self.emergency_contacts
            ]

        return result


class ConnectivityAssessment:
    """Assess connectivity options for a location."""

    CONNECTIVITY_LEVELS = {
        "excellent": {
            "description": "Reliable internet and phone",
            "options": ["phone", "sms", "email", "whatsapp", "video_call"],
        },
        "good": {
            "description": "Regular phone and intermittent internet",
            "options": ["phone", "sms", "whatsapp", "email"],
        },
        "limited": {
            "description": "Basic phone service only",
            "options": ["phone", "sms"],
        },
        "poor": {
            "description": "Intermittent phone service",
            "options": ["sms", "camp_phone"],
        },
        "none": {
            "description": "No regular connectivity",
            "options": ["radio", "satellite", "physical_visit"],
        },
    }

    @classmethod
    def assess_location(
        cls, location: str, camp_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """Assess connectivity options for a location.

        Args:
            location: Country or region code
            camp_name: Optional camp name

        Returns:
            Connectivity assessment
        """
        # Simplified assessment - in production would use detailed location data
        camp_connectivity = {
            "Dadaab": "limited",
            "Kakuma": "good",
            "Zaatari": "good",
            "Cox's Bazar": "limited",
            "Bidi Bidi": "limited",
        }

        if camp_name and camp_name in camp_connectivity:
            level = camp_connectivity[camp_name]
        else:
            # Default by country
            country_levels = {
                "KE": "good",
                "UG": "good",
                "ET": "limited",
                "JO": "excellent",
                "LB": "excellent",
                "TR": "excellent",
                "BD": "good",
                "PK": "good",
            }
            level = country_levels.get(location, "limited")

        return {
            "level": level,
            "details": cls.CONNECTIVITY_LEVELS[level],
            "recommended_contact_methods": cls.CONNECTIVITY_LEVELS[level]["options"],
        }


def format_contact_for_display(contact: Dict[str, Any]) -> str:
    """Format contact information for display.

    Args:
        contact: Contact dictionary

    Returns:
        Formatted string
    """
    system = contact.get("system", "")
    value = contact.get("value", "")
    use = contact.get("use", "")

    # Format based on system
    if system == "phone":
        display = f"📱 {value}"
    elif system == "email":
        display = f"✉️ {value}"
    elif system == "whatsapp":
        display = f"💬 WhatsApp: {value}"
    elif system == "camp_phone":
        display = f"🏕️ Camp Phone: {value}"
    else:
        display = f"{system}: {value}"

    # Add use if not default
    if use and use not in ["home", "mobile"]:
        display += f" ({use})"

    return display


class ContactInformationValidator(FHIRTypedResource):
    """FHIR ContactPoint validation for Haven Health Passport."""

    def __init__(self) -> None:
        """Initialize validator."""
        self.fhir_validator = FHIRValidator()

    @property
    def __fhir_resource_type__(self) -> str:
        """Return the FHIR resource type."""
        return "ContactPoint"

    def validate_fhir(self) -> Dict[str, Any]:
        """Validate the FHIR resource (required by FHIRTypedResource)."""
        # This is a validator class, not a resource instance
        return {"valid": True, "errors": [], "warnings": []}

    def validate_fhir_contact_point(
        self, contact_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Validate FHIR ContactPoint resource.

        Args:
            contact_data: FHIR ContactPoint resource data

        Returns:
            Validation result with 'valid', 'errors', and 'warnings' keys
        """
        errors: List[str] = []
        warnings: List[str] = []

        # Check required fields
        if not contact_data.get("system"):
            errors.append("ContactPoint must have system")
        elif contact_data["system"] not in [
            "phone",
            "fax",
            "email",
            "pager",
            "url",
            "sms",
            "other",
        ]:
            errors.append(f"Invalid contact system: {contact_data['system']}")

        if not contact_data.get("value"):
            errors.append("ContactPoint must have value")

        # Validate use code
        if use := contact_data.get("use"):
            valid_uses = ["home", "work", "temp", "old", "mobile"]
            if use not in valid_uses:
                errors.append(f"Invalid contact use: {use}")

        # Validate rank
        if rank := contact_data.get("rank"):
            if not isinstance(rank, int) or rank < 1:
                errors.append("ContactPoint rank must be a positive integer")

        # Validate based on system
        if system := contact_data.get("system"):
            value = contact_data.get("value", "")

            if system == "email":
                is_valid, error = ContactValidator.validate_email(value)
                if not is_valid:
                    errors.append(f"Invalid email format: {error}")
            elif system in ["phone", "sms"]:
                is_valid, error = ContactValidator.validate_phone_number(value)
                if not is_valid:
                    errors.append(f"Invalid phone number: {error}")
                elif error:
                    warnings.append(error)

        return {"valid": len(errors) == 0, "errors": errors, "warnings": warnings}

    def create_fhir_contact_point(
        self,
        system: str,
        value: str,
        use: Optional[str] = None,
        rank: Optional[int] = None,
    ) -> FHIRContactPoint:
        """Create a valid FHIR ContactPoint resource.

        Args:
            system: The contact system type
            value: The contact value
            use: The contact use code
            rank: Priority ranking

        Returns:
            FHIR ContactPoint resource
        """
        # Create contact point with all fields
        contact = {
            "__fhir_type__": "ContactPoint",
            "system": (
                system
                if system
                and system in ["phone", "fax", "email", "pager", "url", "sms", "other"]
                else "phone"
            ),
            "value": value or "",
            "use": (
                use
                if use and use in ["home", "work", "temp", "old", "mobile"]
                else None
            ),
            "rank": rank,
            "period": None,
        }

        return cast(FHIRContactPoint, contact)
