"""Patient Identifier System Definitions.

This module defines the identifier systems used for patient identification
in the Haven Health Passport system, including refugee-specific identifiers
and cross-border identification schemes.
"""

import logging
import random
import re
import string
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, cast

from src.healthcare.fhir_types import FHIRIdentifier as FHIRIdentifierType
from src.healthcare.fhir_types import (
    FHIRTypedResource,
)
from src.healthcare.fhir_validator import FHIRValidator
from src.healthcare.hipaa_access_control import AccessLevel, require_phi_access

# FHIR resource type for this module
__fhir_resource__ = "Identifier"
__fhir_type__ = "Identifier"

logger = logging.getLogger(__name__)


class FHIRIdentifier(FHIRIdentifierType):
    """FHIR Identifier resource type definition."""

    # Additional Haven-specific fields can be added here


class IdentifierSystem(Enum):
    """Enumeration of supported identifier systems."""

    # Haven Health Passport specific
    HHP_ID = "http://havenhealthpassport.org/fhir/sid/hhp-id"
    HHP_BIOMETRIC = "http://havenhealthpassport.org/fhir/sid/biometric-id"

    # UNHCR systems
    UNHCR_CASE = "http://unhcr.org/fhir/sid/case-number"
    UNHCR_REGISTRATION = "http://unhcr.org/fhir/sid/registration"
    UNHCR_PROGRES = "http://unhcr.org/fhir/sid/progres-id"

    # National identification
    NATIONAL_ID = "http://hl7.org/fhir/sid/national-id"
    PASSPORT = "http://hl7.org/fhir/sid/passport"
    DRIVER_LICENSE = "http://hl7.org/fhir/sid/driver-license"

    # Healthcare identifiers
    MEDICAL_RECORD = "http://hl7.org/fhir/sid/medical-record-number"
    HEALTH_CARD = "http://hl7.org/fhir/sid/health-card-number"
    INSURANCE_ID = "http://hl7.org/fhir/sid/insurance-id"

    # Humanitarian organization IDs
    ICRC_ID = "http://icrc.org/fhir/sid/beneficiary-id"
    MSF_ID = "http://msf.org/fhir/sid/patient-id"
    WHO_ID = "http://who.int/fhir/sid/patient-id"
    IOM_ID = "http://iom.int/fhir/sid/migrant-id"

    # Regional systems
    EACS_ID = "http://eac.int/fhir/sid/eacs-id"  # East African Community
    ECOWAS_ID = "http://ecowas.int/fhir/sid/ecowas-id"  # West Africa
    AU_ID = "http://au.int/fhir/sid/au-id"  # African Union

    # Temporary/Camp identifiers
    CAMP_REGISTRATION = "http://havenhealthpassport.org/fhir/sid/camp-registration"
    BRACELET_ID = "http://havenhealthpassport.org/fhir/sid/bracelet-id"
    FAMILY_ID = "http://havenhealthpassport.org/fhir/sid/family-id"


class IdentifierType:
    """Identifier type definitions with validation rules."""

    # FHIR resource type
    __fhir_resource__ = "Identifier"

    IDENTIFIER_TYPES: Dict[IdentifierSystem, Dict[str, Any]] = {
        IdentifierSystem.HHP_ID: {
            "display": "Haven Health Passport ID",
            "pattern": r"^HHP-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}$",
            "example": "HHP-A1B2-C3D4-E5F6",
            "description": "Unique Haven Health Passport identifier",
            "permanent": True,
            "unique": True,
        },
        IdentifierSystem.HHP_BIOMETRIC: {
            "display": "Biometric Identifier",
            "pattern": r"^BIO-[A-Z0-9]{16}$",
            "example": "BIO-1234567890ABCDEF",
            "description": "Biometric-based unique identifier",
            "permanent": True,
            "unique": True,
        },
        IdentifierSystem.UNHCR_CASE: {
            "display": "UNHCR Case Number",
            "pattern": r"^[A-Z]{3}-\d{2}-C\d{6}$",
            "example": "KEN-21-C123456",
            "description": "UNHCR case number for refugee families",
            "permanent": False,
            "unique": False,  # Family members share case numbers
        },
        IdentifierSystem.UNHCR_REGISTRATION: {
            "display": "UNHCR Individual Registration",
            "pattern": r"^\d{3}-\d{2}C\d{6}/\d{2}$",
            "example": "123-21C123456/01",
            "description": "UNHCR individual registration number",
            "permanent": False,
            "unique": True,
        },
        IdentifierSystem.UNHCR_PROGRES: {
            "display": "UNHCR proGres ID",
            "pattern": r"^[A-Z0-9]{8,12}$",
            "example": "ABC12345678",
            "description": "UNHCR proGres database identifier",
            "permanent": False,
            "unique": True,
        },
        IdentifierSystem.NATIONAL_ID: {
            "display": "National ID Number",
            "pattern": r"^[A-Z0-9-]+$",
            "example": "12345678-A",
            "description": "National identification number",
            "permanent": True,
            "unique": True,
            "country_specific": True,
        },
        IdentifierSystem.PASSPORT: {
            "display": "Passport Number",
            "pattern": r"^[A-Z0-9]+$",
            "example": "A12345678",
            "description": "Passport number",
            "permanent": False,
            "unique": True,
            "country_specific": True,
        },
        IdentifierSystem.MEDICAL_RECORD: {
            "display": "Medical Record Number",
            "pattern": r"^MRN-[A-Z0-9]{8,}$",
            "example": "MRN-12345678",
            "description": "Healthcare facility medical record number",
            "permanent": False,
            "unique": True,
            "facility_specific": True,
        },
        IdentifierSystem.CAMP_REGISTRATION: {
            "display": "Camp Registration Number",
            "pattern": r"^[A-Z]{3}-[A-Z0-9]{6,}$",
            "example": "DAD-123456",
            "description": "Refugee camp registration number",
            "permanent": False,
            "unique": True,
            "location_specific": True,
        },
        IdentifierSystem.BRACELET_ID: {
            "display": "Medical Bracelet ID",
            "pattern": r"^MB-\d{12}$",
            "example": "MB-123456789012",
            "description": "Temporary medical bracelet identifier",
            "permanent": False,
            "unique": True,
            "temporary": True,
        },
        IdentifierSystem.FAMILY_ID: {
            "display": "Family Group ID",
            "pattern": r"^FAM-[A-Z0-9]{8}$",
            "example": "FAM-A1B2C3D4",
            "description": "Family group identifier",
            "permanent": False,
            "unique": False,  # Shared by family members
        },
    }

    @classmethod
    def validate_identifier(
        cls, system: IdentifierSystem, value: str
    ) -> Tuple[bool, Optional[str]]:
        """Validate an identifier value against its system rules.

        Args:
            system: The identifier system
            value: The identifier value to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        if system not in cls.IDENTIFIER_TYPES:
            return False, f"Unknown identifier system: {system.value}"

        type_info = cls.IDENTIFIER_TYPES[system]
        pattern = type_info.get("pattern")

        if pattern and not re.match(pattern, value):
            return (
                False,
                f"Invalid format for {type_info['display']}. Expected format: {type_info['example']}",
            )

        return True, None

    @classmethod
    def get_display_name(cls, system: IdentifierSystem) -> str:
        """Get display name for an identifier system."""
        type_info = cls.IDENTIFIER_TYPES.get(system, {})
        if isinstance(type_info, dict):
            display = type_info.get("display")
            if display:
                return str(display)
        return system.value

    @classmethod
    def is_permanent(cls, system: IdentifierSystem) -> bool:
        """Check if an identifier system represents permanent IDs."""
        type_info = cls.IDENTIFIER_TYPES.get(system)
        if type_info:
            return bool(type_info.get("permanent", False))
        return False

    @classmethod
    def is_unique(cls, system: IdentifierSystem) -> bool:
        """Check if an identifier system guarantees uniqueness."""
        type_info = cls.IDENTIFIER_TYPES.get(system)
        if type_info:
            return bool(type_info.get("unique", True))
        return True


class IdentifierPriority:
    """Priority ordering for identifier systems when multiple are available."""

    # Priority order (highest to lowest)
    PRIORITY_ORDER = [
        IdentifierSystem.HHP_ID,
        IdentifierSystem.HHP_BIOMETRIC,
        IdentifierSystem.UNHCR_PROGRES,
        IdentifierSystem.UNHCR_REGISTRATION,
        IdentifierSystem.UNHCR_CASE,
        IdentifierSystem.NATIONAL_ID,
        IdentifierSystem.PASSPORT,
        IdentifierSystem.MEDICAL_RECORD,
        IdentifierSystem.HEALTH_CARD,
        IdentifierSystem.INSURANCE_ID,
        IdentifierSystem.ICRC_ID,
        IdentifierSystem.MSF_ID,
        IdentifierSystem.WHO_ID,
        IdentifierSystem.IOM_ID,
        IdentifierSystem.EACS_ID,
        IdentifierSystem.ECOWAS_ID,
        IdentifierSystem.AU_ID,
        IdentifierSystem.CAMP_REGISTRATION,
        IdentifierSystem.FAMILY_ID,
        IdentifierSystem.BRACELET_ID,
    ]

    @classmethod
    def get_priority(cls, system: IdentifierSystem) -> int:
        """Get priority score for an identifier system (lower is higher priority)."""
        try:
            return cls.PRIORITY_ORDER.index(system)
        except ValueError:
            return len(cls.PRIORITY_ORDER)  # Unknown systems get lowest priority

    @classmethod
    @require_phi_access(AccessLevel.READ)
    def select_primary_identifier(
        cls, identifiers: List[Dict[str, str]]
    ) -> Optional[Dict[str, str]]:
        """Select the primary identifier from a list based on priority.

        Args:
            identifiers: List of identifier dictionaries with 'system' and 'value' keys

        Returns:
            The highest priority identifier or None
        """
        if not identifiers:
            return None

        valid_identifiers: List[Dict[str, Any]] = []

        for identifier in identifiers:
            try:
                system = IdentifierSystem(identifier.get("system"))
                value = identifier.get("value")

                if value:
                    is_valid, _ = IdentifierType.validate_identifier(system, value)
                    if is_valid:
                        valid_identifiers.append(
                            {
                                "system": system,
                                "value": value,
                                "priority": cls.get_priority(system),
                            }
                        )
            except ValueError:
                # Unknown system, skip
                continue

        if not valid_identifiers:
            return None

        # Sort by priority and return the highest
        valid_identifiers.sort(key=lambda x: x["priority"])
        best = valid_identifiers[0]

        return {"system": best["system"].value, "value": best["value"]}


class IdentifierGenerator:
    """Generator for Haven Health Passport identifiers."""

    @staticmethod
    def generate_hhp_id() -> str:
        """Generate a new Haven Health Passport ID.

        Returns:
            New HHP ID in format HHP-XXXX-XXXX-XXXX
        """
        chars = string.ascii_uppercase + string.digits
        segments = []

        for _ in range(3):
            segment = "".join(random.choices(chars, k=4))
            segments.append(segment)

        return f"HHP-{'-'.join(segments)}"

    @staticmethod
    def generate_biometric_id(biometric_hash: str) -> str:
        """Generate a biometric-based identifier.

        Args:
            biometric_hash: Hash of biometric data

        Returns:
            Biometric ID in format BIO-XXXXXXXXXXXXXXXX
        """
        # Take first 16 characters of hash and convert to uppercase
        clean_hash = re.sub(r"[^A-Z0-9]", "", biometric_hash.upper())[:16]
        clean_hash = clean_hash.ljust(16, "0")  # Pad if needed

        return f"BIO-{clean_hash}"

    @staticmethod
    def generate_family_id() -> str:
        """Generate a new family group ID.

        Returns:
            Family ID in format FAM-XXXXXXXX
        """
        chars = string.ascii_uppercase + string.digits
        id_part = "".join(random.choices(chars, k=8))

        return f"FAM-{id_part}"

    @staticmethod
    def generate_bracelet_id() -> str:
        """Generate a temporary medical bracelet ID.

        Returns:
            Bracelet ID in format MB-XXXXXXXXXXXX (12 digits)
        """
        digits = "".join([str(random.randint(0, 9)) for _ in range(12)])
        return f"MB-{digits}"


@require_phi_access(AccessLevel.READ)
def format_identifier_for_display(system: str, value: str) -> str:
    """Format an identifier for human-readable display.

    Args:
        system: The identifier system URI
        value: The identifier value

    Returns:
        Formatted string for display
    """
    try:
        id_system = IdentifierSystem(system)
        display_name = IdentifierType.get_display_name(id_system)
        return f"{display_name}: {value}"
    except ValueError:
        # Unknown system
        return f"{system}: {value}"


class IdentifierValidator(FHIRTypedResource):
    """FHIR Identifier validation for Haven Health Passport."""

    def __init__(self) -> None:
        """Initialize validator."""
        self.fhir_validator = FHIRValidator()

    @property
    def __fhir_resource_type__(self) -> str:
        """Return the FHIR resource type."""
        return "Identifier"

    def validate_fhir(self) -> Dict[str, Any]:
        """Validate the FHIR resource (required by FHIRTypedResource)."""
        # This is a validator class, not a resource instance
        return {"valid": True, "errors": [], "warnings": []}

    def validate_fhir_identifier(
        self, identifier_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Validate FHIR Identifier resource.

        Args:
            identifier_data: FHIR Identifier resource data

        Returns:
            Validation result with 'valid', 'errors', and 'warnings' keys
        """
        errors = []
        warnings = []

        # Check required fields
        if not identifier_data.get("system"):
            errors.append("Identifier must have system")
        if not identifier_data.get("value"):
            errors.append("Identifier must have value")

        # Validate against known systems
        if system := identifier_data.get("system"):
            try:
                id_system = IdentifierSystem(system)
                # Validate format
                if value := identifier_data.get("value"):
                    is_valid, error_msg = IdentifierType.validate_identifier(
                        id_system, value
                    )
                    if not is_valid:
                        if error_msg:
                            errors.append(error_msg)
            except ValueError:
                warnings.append(f"Unknown identifier system: {system}")

        # Validate use code
        if use := identifier_data.get("use"):
            valid_uses = ["official", "temp", "secondary", "old"]
            if use not in valid_uses:
                errors.append(f"Invalid identifier use: {use}")

        return {"valid": len(errors) == 0, "errors": errors, "warnings": warnings}

    def create_fhir_identifier(
        self, system: IdentifierSystem, value: str, use: Optional[str] = "official"
    ) -> FHIRIdentifier:
        """Create a valid FHIR Identifier resource.

        Args:
            system: The identifier system
            value: The identifier value
            use: The identifier use code

        Returns:
            FHIR Identifier resource
        """
        # Create identifier with all required fields
        identifier: Dict[str, Any] = {
            "__fhir_type__": "Identifier",
            "system": system.value,
            "value": value,
            "use": (
                use
                if use and use in ["usual", "official", "temp", "secondary", "old"]
                else "official"
            ),
            "type": None,
            "period": None,
            "assigner": None,
        }

        # Add display if available
        if display := IdentifierType.get_display_name(system):
            identifier["type"] = {
                "coding": [
                    {
                        "system": "http://terminology.hl7.org/CodeSystem/v2-0203",
                        "code": system.name,
                        "display": display,
                    }
                ]
            }

        return cast(FHIRIdentifier, identifier)
