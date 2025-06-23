"""Integration module for external services."""

from typing import Any, Dict

from src.healthcare.fhir_validator import FHIRValidator

from .fhir_mapping import FHIRResourceMapper
from .fhir_server import FHIRServerClient

__all__ = [
    "FHIRServerClient",
    "FHIRResourceMapper",
    "FHIRValidator",
    "validate_fhir_resource",
]

# Initialize FHIR validator for integration module
fhir_validator = FHIRValidator()


def validate_fhir_resource(
    resource_type: str, resource_data: Dict[str, Any]
) -> Dict[str, Any]:
    """Validate FHIR resource for integration operations.

    Args:
        resource_type: FHIR resource type (e.g., 'Patient', 'Observation')
        resource_data: Resource data to validate

    Returns:
        Validation result with 'valid', 'errors', and 'warnings' keys
    """
    return fhir_validator.validate_resource(resource_type, resource_data)
