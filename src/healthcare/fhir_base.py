"""Base FHIR Resource Abstract Class.

This module provides the abstract base class for all FHIR resources
in the Haven Health Passport system, integrating with the fhirclient
library and supporting refugee-specific extensions.
"""

import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Optional, Type

from fhirclient.models.domainresource import DomainResource
from fhirclient.models.extension import Extension
from fhirclient.models.meta import Meta

from ..utils.encryption import EncryptionService
from .fhir_profiles import REFUGEE_STATUS_EXTENSION
from .fhir_validator import FHIRValidator

logger = logging.getLogger(__name__)


class BaseFHIRResource(ABC):
    """Abstract base class for all FHIR resources in Haven Health Passport.

    This class provides common functionality for FHIR resources including:
    - Integration with fhirclient library
    - Validation through FHIRValidator
    - Support for refugee-specific extensions
    - Encryption/decryption of sensitive fields
    - Audit logging
    - Serialization/deserialization
    """

    def __init__(self, resource_type: Type[DomainResource]):
        """Initialize base FHIR resource.

        Args:
            resource_type: The fhirclient model class for this resource type
        """
        self.resource_type = resource_type
        self._validator: Optional[Any] = (
            None  # Lazy initialization to avoid circular imports
        )
        self.encryption_service = EncryptionService()
        self._resource: Optional[DomainResource] = None
        self._encrypted_fields: List[str] = []
        self._audit_log: List[Dict[str, Any]] = []

    @property
    def validator(self) -> Any:
        """Lazy load FHIRValidator to avoid circular imports."""
        if self._validator is None:
            self._validator = FHIRValidator()
        return self._validator

    @abstractmethod
    def create_resource(self, data: Dict[str, Any]) -> DomainResource:
        """Create a new FHIR resource instance.

        Args:
            data: Dictionary containing resource data

        Returns:
            Created FHIR resource instance
        """

    @abstractmethod
    def get_encrypted_fields(self) -> List[str]:
        """Return list of field paths that should be encrypted.

        Returns:
            List of field paths (e.g., ['name[0].family', 'identifier[0].value'])
        """

    def validate(self, resource: Optional[DomainResource] = None) -> bool:
        """Validate the FHIR resource.

        Args:
            resource: Resource to validate (uses internal resource if None)

        Returns:
            True if valid, False otherwise

        Raises:
            ValueError: If validation fails with details
        """
        resource_to_validate = resource or self._resource
        if not resource_to_validate:
            raise ValueError("No resource to validate")

        resource_type_name = resource_to_validate.resource_type

        # Map resource types to validator methods
        validator_methods = {
            "Patient": self.validator.validate_patient,
            "Observation": self.validator.validate_observation,
            "Immunization": self.validator.validate_immunization,
        }

        if resource_type_name in validator_methods:
            is_valid, errors = validator_methods[resource_type_name](
                resource_to_validate.as_json()
            )
            if not is_valid:
                raise ValueError(f"Validation failed: {errors}")
            return True
        else:
            logger.warning("No validator for resource type: %s", resource_type_name)
            return True

    def add_refugee_extensions(self, resource: DomainResource) -> None:
        """Add refugee-specific extensions to the resource.

        Args:
            resource: Resource to add extensions to
        """
        if not hasattr(resource, "extension"):
            resource.extension = []

        # Add refugee status extension if not present
        has_refugee_extension = any(
            ext.url == REFUGEE_STATUS_EXTENSION for ext in resource.extension
        )

        if not has_refugee_extension:
            refugee_ext = Extension()
            refugee_ext.url = REFUGEE_STATUS_EXTENSION
            resource.extension.append(refugee_ext)

    def add_meta_profile(self, resource: DomainResource, profile_url: str) -> None:
        """Add profile URL to resource metadata.

        Args:
            resource: Resource to add profile to
            profile_url: URL of the FHIR profile
        """
        if not resource.meta:
            resource.meta = Meta()

        if not resource.meta.profile:
            resource.meta.profile = []

        if profile_url not in resource.meta.profile:
            resource.meta.profile.append(profile_url)

    def encrypt_sensitive_fields(self, resource: DomainResource) -> None:
        """Encrypt sensitive fields in the resource.

        Args:
            resource: Resource containing fields to encrypt
        """
        encrypted_fields = self.get_encrypted_fields()
        resource_dict = resource.as_json()

        for field_path in encrypted_fields:
            try:
                value = self._get_field_value(resource_dict, field_path)
                if value:
                    encrypted_value = self.encryption_service.encrypt(str(value))
                    self._set_field_value(resource_dict, field_path, encrypted_value)
            except (ValueError, AttributeError) as e:
                logger.error("Failed to encrypt field %s: %s", field_path, e)

        # Update resource with encrypted data
        self._update_resource_from_dict(resource, resource_dict)

    def decrypt_sensitive_fields(self, resource: DomainResource) -> None:
        """Decrypt sensitive fields in the resource.

        Args:
            resource: Resource containing fields to decrypt
        """
        encrypted_fields = self.get_encrypted_fields()
        resource_dict = resource.as_json()

        for field_path in encrypted_fields:
            try:
                value = self._get_field_value(resource_dict, field_path)
                if value:
                    decrypted_value = self.encryption_service.decrypt(str(value))
                    self._set_field_value(resource_dict, field_path, decrypted_value)
            except (ValueError, AttributeError) as e:
                logger.error("Failed to decrypt field %s: %s", field_path, e)

        # Update resource with decrypted data
        self._update_resource_from_dict(resource, resource_dict)

    def to_json(self, include_encrypted: bool = True) -> Dict[str, Any]:
        """Convert resource to JSON dictionary.

        Args:
            include_encrypted: Whether to include encrypted fields

        Returns:
            JSON dictionary representation
        """
        if not self._resource:
            raise ValueError("No resource to serialize")

        resource_dict: Dict[str, Any] = self._resource.as_json()

        if not include_encrypted:
            # Remove encrypted field values
            for field_path in self.get_encrypted_fields():
                self._set_field_value(resource_dict, field_path, "[ENCRYPTED]")

        return resource_dict

    def from_json(self, data: Dict[str, Any]) -> None:
        """Load resource from JSON dictionary.

        Args:
            data: JSON dictionary to load
        """
        self._resource = self.resource_type(data)
        self.validate()

    def add_audit_entry(
        self, action: str, user_id: str, details: Optional[Dict] = None
    ) -> None:
        """Add an audit log entry for this resource.

        Args:
            action: Action performed (e.g., 'create', 'update', 'access')
            user_id: ID of user performing action
            details: Additional details about the action
        """
        audit_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "action": action,
            "user_id": user_id,
            "resource_type": self.resource_type.__name__,
            "resource_id": self._resource.id if self._resource else None,
            "details": details or {},
        }
        self._audit_log.append(audit_entry)
        logger.info(
            "Audit: %s on %s by %s", action, self.resource_type.__name__, user_id
        )

    def get_audit_log(self) -> List[Dict[str, Any]]:
        """Get audit log entries for this resource.

        Returns:
            List of audit log entries
        """
        return self._audit_log.copy()

    def _get_field_value(self, data: Dict, field_path: str) -> Any:
        """Get value from nested dictionary using field path.

        Args:
            data: Dictionary to search
            field_path: Path like 'name[0].family'

        Returns:
            Field value or None
        """
        parts = field_path.replace("[", ".").replace("]", "").split(".")
        current: Any = data

        for part in parts:
            if part.isdigit() and isinstance(current, list):
                index = int(part)
                if index < len(current):
                    current = current[index]
                else:
                    return None
            elif isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return None

        return current

    def _set_field_value(self, data: Dict, field_path: str, value: Any) -> None:
        """Set value in nested dictionary using field path.

        Args:
            data: Dictionary to modify
            field_path: Path like 'name[0].family'
            value: Value to set
        """
        parts = field_path.replace("[", ".").replace("]", "").split(".")
        current: Any = data

        for i, part in enumerate(parts[:-1]):
            if part.isdigit() and isinstance(current, list):
                index = int(part)
                while len(current) <= index:
                    current.append({})
                current = current[index]
            elif isinstance(current, dict):
                if part not in current:
                    # Determine if next part is array index
                    next_part = parts[i + 1]
                    if next_part.isdigit():
                        current[part] = []
                    else:
                        current[part] = {}
                current = current[part]

        # Set final value
        final_part = parts[-1]
        if final_part.isdigit() and isinstance(current, list):
            index = int(final_part)
            while len(current) <= index:
                current.append(None)
            current[index] = value
        elif isinstance(current, dict):
            current[final_part] = value

    def _update_resource_from_dict(
        self, resource: DomainResource, data: Dict[str, Any]
    ) -> None:
        """Update resource object from dictionary.

        Args:
            resource: Resource to update
            data: Dictionary with updated data
        """
        # This is a simplified version - in production would need proper deserialization
        for key, value in data.items():
            if hasattr(resource, key):
                setattr(resource, key, value)

    @property
    def resource(self) -> Optional[DomainResource]:
        """Get the underlying FHIR resource."""
        return self._resource

    @resource.setter
    def resource(self, value: DomainResource) -> None:
        """Set the underlying FHIR resource."""
        self._resource = value
        self.validate()
