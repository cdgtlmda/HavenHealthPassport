"""GraphQL Schema Versioning System.

This module implements a comprehensive versioning strategy for GraphQL types,
fields, and operations to ensure backward compatibility and smooth migrations.

This module handles PHI with encryption and access control to ensure HIPAA compliance.
It includes FHIR Resource typing and validation for healthcare data.
"""

from datetime import datetime
from enum import Enum
from functools import wraps
from typing import Any, Callable, Dict, List, Optional

try:
    import strawberry
    from strawberry.extensions import Extension
    from strawberry.types import Info
except ImportError as e:
    raise ImportError(
        "Failed to import strawberry modules. Please install strawberry-graphql: pip install strawberry-graphql"
    ) from e

# FHIR resources - removed unused imports

from src.healthcare.fhir.validators import FHIRValidator
from src.security.access_control import AccessPermission, require_permission
from src.security.audit import audit_phi_access
from src.security.encryption import EncryptionService

# Version tracking
CURRENT_VERSION = "2.0"
SUPPORTED_VERSIONS = ["1.0", "1.1", "2.0"]
DEPRECATED_VERSIONS = ["0.9"]


@strawberry.enum
class SchemaVersion(Enum):
    """Available schema versions."""

    V1_0 = "1.0"
    V1_1 = "1.1"
    V2_0 = "2.0"


@strawberry.type
class VersionInfo:
    """Version information for the GraphQL schema."""

    current: str
    supported: List[str]
    deprecated: List[str]
    changes: List["VersionChange"]


@strawberry.type
class VersionChange:
    """Represents a change between versions."""

    version: str
    date: datetime
    breaking: bool
    description: str
    affected_types: List[str]
    migration_guide: Optional[str] = None


@strawberry.type
class DeprecationInfo:
    """Deprecation information for fields and types."""

    deprecated_in: str
    removed_in: Optional[str]
    reason: str
    replacement: Optional[str]


class VersionedField:
    """Decorator for versioned GraphQL fields."""

    def __init__(
        self,
        added_in: str,
        deprecated_in: Optional[str] = None,
        removed_in: Optional[str] = None,
        replacement: Optional[str] = None,
    ):
        """Initialize versioned field decorator."""
        self.added_in = added_in
        self.deprecated_in = deprecated_in
        self.removed_in = removed_in
        self.replacement = replacement

    def __call__(self, func: Callable) -> Callable:
        """Apply versioning to field resolver."""

        @wraps(func)
        async def wrapper(self: Any, info: Info, *args: Any, **kwargs: Any) -> Any:
            # Get requested version from context
            version = get_requested_version(info)

            # Check if field is available in requested version
            if not self._is_available_in_version(version):
                raise ValueError(
                    f"Field not available in version {version}. "
                    f"Added in {self.added_in}"
                )

            # Add deprecation warning if applicable
            if self._is_deprecated_in_version(version):
                add_deprecation_warning(
                    info,
                    (
                        f"Field deprecated in {self.deprecated_in}. "
                        f"Use {self.replacement} instead."
                        if self.replacement
                        else ""
                    ),
                )

            # Call original resolver
            return await func(self, info, *args, **kwargs)

        # Add metadata for introspection
        wrapper._version_info = {  # type: ignore[attr-defined]
            "added_in": self.added_in,
            "deprecated_in": self.deprecated_in,
            "removed_in": self.removed_in,
            "replacement": self.replacement,
        }

        return wrapper

    def _is_available_in_version(self, version: str) -> bool:
        """Check if field is available in given version."""
        if self.removed_in and version >= self.removed_in:
            return False
        return version >= self.added_in

    def _is_deprecated_in_version(self, version: str) -> bool:
        """Check if field is deprecated in given version."""
        if not self.deprecated_in:
            return False
        return version >= self.deprecated_in


class VersionedType:
    """Decorator for versioned GraphQL types."""

    def __init__(
        self,
        added_in: str,
        deprecated_in: Optional[str] = None,
        removed_in: Optional[str] = None,
    ):
        """Initialize versioned type decorator."""
        self.added_in = added_in
        self.deprecated_in = deprecated_in
        self.removed_in = removed_in

    def __call__(self, cls: Any) -> Any:
        """Apply versioning to type."""
        # Store version info on class
        cls._version_info = {
            "added_in": self.added_in,
            "deprecated_in": self.deprecated_in,
            "removed_in": self.removed_in,
        }

        # Add version check to constructor
        original_init = cls.__init__

        def versioned_init(self: Any, *args: Any, **kwargs: Any) -> None:
            original_init(self, *args, **kwargs)
            # Version checking would happen here if needed

        cls.__init__ = versioned_init

        return cls


class VersioningExtension(Extension):
    """GraphQL extension for handling versioning."""

    def on_request_start(self) -> None:
        """Set up version context for request."""
        request = self.execution_context.context.get("request")
        if request:
            # Get version from header or query param
            version = (
                request.headers.get("X-API-Version")
                or request.query_params.get("version")
                or CURRENT_VERSION
            )

            # Validate version
            if version not in SUPPORTED_VERSIONS:
                if version in DEPRECATED_VERSIONS:
                    # Log deprecation warning
                    self.execution_context.context["deprecation_warnings"] = [
                        f"API version {version} is deprecated. "
                        f"Please upgrade to {CURRENT_VERSION}"
                    ]
                else:
                    raise ValueError(
                        f"Unsupported API version: {version}. "
                        f"Supported versions: {', '.join(SUPPORTED_VERSIONS)}"
                    )

            # Store version in context
            self.execution_context.context["api_version"] = version

    def on_request_end(self) -> None:
        """Add version headers to response."""
        response = self.execution_context.response
        if response:
            response.headers["X-API-Version"] = self.execution_context.context.get(
                "api_version", CURRENT_VERSION
            )

            # Add deprecation warnings to response
            warnings = self.execution_context.context.get("deprecation_warnings", [])
            if warnings:
                response.headers["X-API-Deprecation"] = "; ".join(warnings)


# Helper functions
def get_requested_version(info: Info) -> str:
    """Get the API version requested by the client."""
    return str(info.context.get("api_version", CURRENT_VERSION))


def add_deprecation_warning(info: Info, warning: str) -> None:
    """Add a deprecation warning to the response."""
    if "deprecation_warnings" not in info.context:
        info.context["deprecation_warnings"] = []
    info.context["deprecation_warnings"].append(warning)


def version_field_resolver(field_name: str, version_map: Dict[str, Any]) -> Callable:
    """Create a field resolver that returns different values based on version."""
    # Note: field_name parameter is used for documentation purposes
    _ = field_name  # Acknowledge unused parameter

    def resolver(self: Any, info: Info) -> Any:
        # Note: self parameter is required for Strawberry field resolvers
        _ = self  # Acknowledge unused parameter
        version = get_requested_version(info)

        # Find the appropriate value for the version
        for v in sorted(version_map.keys(), reverse=True):
            if version >= v:
                return version_map[v]

        # Default to None if no version matches
        return None

    return resolver


# Version-specific type transformers
class TypeVersionManager:
    """Manages type transformations across versions."""

    def __init__(self) -> None:
        """Initialize type version manager."""
        self.transformers: Dict[str, Dict[str, Callable]] = {}
        self.fhir_validator = FHIRValidator()
        self.encryption_service = EncryptionService(
            kms_key_id="alias/haven-health-default"
        )

    def validate_fhir_resource(self, resource: dict) -> bool:
        """Validate FHIR resource structure and requirements."""
        return self.fhir_validator.validate_resource(resource)

    @audit_phi_access("process_phi_data")
    @require_permission(AccessPermission.READ_PHI)
    def process_with_phi_protection(self, data: dict) -> dict:
        """Process data with PHI protection and audit logging."""
        # Encrypt sensitive fields
        sensitive_fields = ["name", "birthDate", "ssn", "address"]
        encrypted_data = data.copy()

        for field in sensitive_fields:
            if field in encrypted_data:
                encrypted_data[field] = self.encryption_service.encrypt(
                    str(encrypted_data[field]).encode()
                )

        return encrypted_data

    def register_transformer(
        self, type_name: str, from_version: str, to_version: str, transformer: Callable
    ) -> None:
        """Register a type transformer between versions."""
        key = f"{from_version}->{to_version}"
        if type_name not in self.transformers:
            self.transformers[type_name] = {}
        self.transformers[type_name][key] = transformer

    def transform(
        self, obj: Any, type_name: str, from_version: str, to_version: str
    ) -> Any:
        """Transform an object between versions."""
        if from_version == to_version:
            return obj

        key = f"{from_version}->{to_version}"
        if type_name in self.transformers and key in self.transformers[type_name]:
            return self.transformers[type_name][key](obj)

        # No transformer found, return as-is
        return obj


# Global version manager instance
version_manager = TypeVersionManager()


# Schema evolution tracking
version_changes = [
    VersionChange(
        version="1.1",
        date=datetime(2024, 6, 1),
        breaking=False,
        description="Added support for family linking and refugee status",
        affected_types=["Patient"],
        migration_guide=None,
    ),
    VersionChange(
        version="2.0",
        date=datetime(2024, 12, 1),
        breaking=True,
        description="Restructured health records with FHIR compliance",
        affected_types=["HealthRecord", "Patient", "Observation"],
        migration_guide="See migration guide at /docs/migrations/v2.0",
    ),
]


# Query for version information
@strawberry.type
class VersionQuery:
    """Queries for schema version information."""

    @strawberry.field
    def version_info(self) -> VersionInfo:
        """Get current version information."""
        return VersionInfo(
            current=CURRENT_VERSION,
            supported=SUPPORTED_VERSIONS,
            deprecated=DEPRECATED_VERSIONS,
            changes=version_changes,
        )

    @strawberry.field
    def check_compatibility(self, version: str) -> bool:
        """Check if a version is compatible."""
        return version in SUPPORTED_VERSIONS


# Export versioning components
__all__ = [
    "SchemaVersion",
    "VersionInfo",
    "VersionChange",
    "DeprecationInfo",
    "VersionedField",
    "VersionedType",
    "VersioningExtension",
    "get_requested_version",
    "add_deprecation_warning",
    "version_field_resolver",
    "TypeVersionManager",
    "version_manager",
    "VersionQuery",
    "CURRENT_VERSION",
    "SUPPORTED_VERSIONS",
]
