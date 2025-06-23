"""Healthcare Validation Module.

This module provides validation capabilities for healthcare data
including FHIR resource validation and healthcare-specific rules.
Handles validation for all FHIR Resource types used in the system.
"""

from .fhir_validators import (
    FHIRValidator,
    ValidationIssue,
    ValidationProfile,
    ValidationSeverity,
    ValidationType,
    create_healthcare_profiles,
)
from .profile_config import ProfileValidationConfig

# FHIR resource type for this module
__fhir_resource__ = "OperationOutcome"

__all__ = [
    "FHIRValidator",
    "ValidationProfile",
    "ValidationIssue",
    "ValidationSeverity",
    "ValidationType",
    "create_healthcare_profiles",
    "ProfileValidationConfig",
]
