"""Development environment configuration."""

from typing import TYPE_CHECKING, Any, Dict, List, Optional

from src.config.base import Settings
from src.healthcare.hipaa_access_control import (
    AccessLevel,
    audit_phi_access,
    require_phi_access,
)
from src.utils.encryption import EncryptionService

# FHIR Resource type imports
if TYPE_CHECKING:
    pass


class DevelopmentSettings(Settings):
    """Development-specific settings."""

    environment: str = "development"
    debug: bool = True

    # Relaxed CORS for development
    allowed_origins: list[str] = ["http://localhost:3000", "http://localhost:8080"]

    # Local services
    database_url: str = (
        "postgresql+asyncpg://postgres:postgres@localhost/havenhealth_dev"
    )
    redis_url: str = "redis://localhost:6379/0"
    fhir_server_url: str = "http://localhost:8080/fhir"

    # Development logging
    log_level: str = "DEBUG"

    # PHI Protection Settings
    encrypt_phi_at_rest: bool = True
    encrypt_phi_in_transit: bool = True
    phi_access_audit_enabled: bool = True
    phi_access_level_default: str = "READ"

    # FHIR Validation Settings
    fhir_validation_enabled: bool = True
    fhir_strict_validation: bool = False  # Relaxed for development
    fhir_profile_validation: bool = True
    fhir_terminology_validation: bool = True
    fhir_reference_validation: bool = True

    # FHIR Validation Rules
    fhir_validation_rules: Dict[str, Dict[str, bool]] = {
        "Patient": {
            "require_identifier": True,
            "require_name": True,
            "validate_telecom": True,
            "validate_address": True,
        },
        "Observation": {
            "require_status": True,
            "require_code": True,
            "require_subject": True,
            "validate_value": True,
        },
        "MedicationRequest": {
            "require_status": True,
            "require_intent": True,
            "require_medication": True,
            "require_subject": True,
        },
    }

    # FHIR Profiles to validate against
    fhir_profiles: List[str] = [
        "http://hl7.org/fhir/StructureDefinition/Patient",
        "http://hl7.org/fhir/StructureDefinition/Observation",
        "http://hl7.org/fhir/StructureDefinition/MedicationRequest",
        "http://hl7.org/fhir/StructureDefinition/Condition",
    ]

    # FHIR Terminology Server
    fhir_terminology_server_url: Optional[str] = "http://localhost:8080/terminology"
    fhir_validate_code_systems: bool = True
    fhir_validate_value_sets: bool = True

    def __init__(self, **kwargs: Any) -> None:
        """Initialize development settings with encryption service."""
        super().__init__(**kwargs)
        self._encryption_service = EncryptionService()

    @require_phi_access(AccessLevel.READ)
    @audit_phi_access("get_encrypted_setting")
    def get_encrypted_setting(self, key: str) -> str:
        """Get a setting value with encryption if it contains PHI."""
        value = getattr(self, key, None)
        if value and self._contains_phi(key):
            return self._encryption_service.encrypt(str(value))
        return str(value) if value is not None else ""

    def _contains_phi(self, key: str) -> bool:
        """Check if a setting key might contain PHI."""
        phi_indicators = ["patient", "medical", "health", "diagnosis", "treatment"]
        return any(indicator in key.lower() for indicator in phi_indicators)
