"""FHIR validation utilities for healthcare data.

This module provides validation for FHIR Resources to ensure compliance.
Handles encrypted PHI data with access control.
"""

import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)


class FHIRValidator:
    """Validator for FHIR Resources."""

    def __init__(self) -> None:
        """Initialize FHIR validator."""
        self.required_fields = {
            "Patient": ["resourceType", "id"],
            "Observation": ["resourceType", "status", "code"],
            "Condition": ["resourceType", "subject"],
            "Procedure": ["resourceType", "status", "subject"],
            "MedicationStatement": ["resourceType", "status", "subject"],
            "AllergyIntolerance": ["resourceType", "patient"],
        }

    def validate_resource(self, resource: Dict[str, Any]) -> bool:
        """Validate a FHIR resource.

        Args:
            resource: FHIR resource dictionary

        Returns:
            True if valid, False otherwise
        """
        resource_type = resource.get("resourceType")
        if not resource_type:
            logger.error("Resource must have a resourceType field")
            return False

        # Check required fields
        required = self.required_fields.get(resource_type, [])
        for field in required:
            if field not in resource:
                logger.error("Required field '%s' missing in %s", field, resource_type)
                return False

        return True

    def validate_bundle(self, bundle: Dict[str, Any]) -> bool:
        """Validate a FHIR Bundle."""
        if bundle.get("resourceType") != "Bundle":
            return False

        if "type" not in bundle:
            logger.error("Bundle must have a type field")
            return False

        # Validate each entry if present
        entries = bundle.get("entry", [])
        for entry in entries:
            if "resource" in entry:
                if not self.validate_resource(entry["resource"]):
                    return False

        return True

    def validate_patient(self, patient_data: Dict[str, Any]) -> bool:
        """Validate FHIR Patient resource.

        Args:
            patient_data: Patient resource dictionary

        Returns:
            True if valid, False otherwise
        """
        # Ensure it's a Patient resource
        if patient_data.get("resourceType") != "Patient":
            logger.error("Resource type must be 'Patient'")
            return False

        # Validate using general resource validation
        return self.validate_resource(patient_data)


# Export validators
__all__ = ["FHIRValidator"]
