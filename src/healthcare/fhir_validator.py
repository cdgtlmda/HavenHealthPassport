"""FHIR resource validation for Haven Health Passport."""

import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from src.healthcare.fhir_profiles import get_profile_definitions
from src.healthcare.hipaa_access_control import AccessLevel, require_phi_access
from src.security.encryption import EncryptionService


class FHIRValidator:
    """Validator for FHIR resources with refugee-specific rules."""

    # FHIR resource type
    __fhir_resource__ = "OperationOutcome"

    def __init__(self) -> None:
        """Initialize validator with profiles."""
        self.profiles = get_profile_definitions()
        # Remove encryption service initialization to avoid circular import
        self._encryption_service: Optional[EncryptionService] = None

    @property
    def encryption_service(self) -> EncryptionService:
        """Lazy load encryption service to avoid circular imports."""
        if self._encryption_service is None:
            self._encryption_service = EncryptionService(
                kms_key_id="alias/haven-health-default"
            )
        return self._encryption_service

    @require_phi_access(AccessLevel.READ)
    def validate_patient(self, patient_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate patient resource against refugee profile."""
        errors = []
        warnings = []

        # Required fields
        if not patient_data.get("name"):
            errors.append("Patient must have at least one name")
        else:
            name = (
                patient_data["name"][0]
                if isinstance(patient_data["name"], list)
                else patient_data["name"]
            )
            if not name.get("family") and not name.get("given"):
                errors.append("Patient name must have family or given name")

        # Validate identifiers
        if not patient_data.get("identifier"):
            warnings.append("Patient should have at least one identifier")
        else:
            # Check for UNHCR ID
            identifiers = patient_data["identifier"]
            if not isinstance(identifiers, list):
                identifiers = [identifiers]

            has_unhcr = any(
                id.get("system") == "https://www.unhcr.org/identifiers"
                for id in identifiers
            )
            if not has_unhcr:
                warnings.append("Refugee patient should have UNHCR identifier")

        # Validate birth date format
        if birth_date := patient_data.get("birthDate"):
            if not self._validate_date_format(birth_date):
                errors.append(f"Invalid birth date format: {birth_date}")

        # Validate gender
        if gender := patient_data.get("gender"):
            valid_genders = ["male", "female", "other", "unknown"]
            if gender not in valid_genders:
                errors.append(f"Invalid gender value: {gender}")

        # Validate contact information
        if telecom := patient_data.get("telecom"):
            for contact in telecom:
                if contact.get("system") == "phone":
                    if not self._validate_phone(contact.get("value")):
                        warnings.append(f"Invalid phone format: {contact.get('value')}")
                elif contact.get("system") == "email":
                    if not self._validate_email(contact.get("value")):
                        errors.append(f"Invalid email format: {contact.get('value')}")

        return {"valid": len(errors) == 0, "errors": errors, "warnings": warnings}

    def validate_observation(self, observation_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate observation resource."""
        errors = []
        warnings = []

        # Required fields
        if not observation_data.get("status"):
            errors.append("Observation must have status")
        elif observation_data["status"] not in [
            "registered",
            "preliminary",
            "final",
            "amended",
            "corrected",
            "cancelled",
            "entered-in-error",
            "unknown",
        ]:
            errors.append(f"Invalid observation status: {observation_data['status']}")

        if not observation_data.get("code"):
            errors.append("Observation must have code")

        if not observation_data.get("subject"):
            errors.append("Observation must have subject (patient reference)")

        # Validate value if present
        if "valueQuantity" in observation_data:
            value = observation_data["valueQuantity"]
            if not isinstance(value.get("value"), (int, float)):
                errors.append("Observation value must be numeric")
            if not value.get("unit"):
                warnings.append("Observation value should have unit")

        # Validate effective date/time
        if effective := observation_data.get("effectiveDateTime"):
            if not self._validate_datetime_format(effective):
                errors.append(f"Invalid effective date/time format: {effective}")

        return {"valid": len(errors) == 0, "errors": errors, "warnings": warnings}

    def validate_immunization(
        self, immunization_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Validate immunization resource."""
        errors = []
        warnings: List[str] = []

        # Required fields
        if not immunization_data.get("status"):
            errors.append("Immunization must have status")
        elif immunization_data["status"] not in [
            "completed",
            "entered-in-error",
            "not-done",
        ]:
            errors.append(f"Invalid immunization status: {immunization_data['status']}")

        if not immunization_data.get("vaccineCode"):
            errors.append("Immunization must have vaccine code")

        if not immunization_data.get("patient"):
            errors.append("Immunization must have patient reference")

        if not immunization_data.get(
            "occurrenceDateTime"
        ) and not immunization_data.get("occurrenceString"):
            errors.append("Immunization must have occurrence date/time or string")

        # Validate occurrence date
        if occurrence := immunization_data.get("occurrenceDateTime"):
            if not self._validate_datetime_format(occurrence):
                errors.append(f"Invalid occurrence date/time format: {occurrence}")

        # Validate primary source
        if "primarySource" in immunization_data:
            if not isinstance(immunization_data["primarySource"], bool):
                errors.append("Primary source must be boolean")

        return {"valid": len(errors) == 0, "errors": errors, "warnings": warnings}

    def validate_bundle(self, bundle_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate bundle resource."""
        errors = []
        warnings = []

        # Required fields
        if not bundle_data.get("resourceType") == "Bundle":
            errors.append("Resource type must be 'Bundle'")

        if not bundle_data.get("type"):
            errors.append("Bundle must have type")
        elif bundle_data["type"] not in [
            "document",
            "message",
            "transaction",
            "transaction-response",
            "batch",
            "batch-response",
            "history",
            "searchset",
            "collection",
        ]:
            errors.append(f"Invalid bundle type: {bundle_data['type']}")

        # Validate entries if present
        if entries := bundle_data.get("entry"):
            if not isinstance(entries, list):
                errors.append("Bundle entries must be a list")
            else:
                for i, entry in enumerate(entries):
                    if not isinstance(entry, dict):
                        errors.append(f"Entry {i} must be a dictionary")
                    elif resource := entry.get("resource"):
                        # Validate each contained resource
                        resource_type = resource.get("resourceType")
                        if resource_type:
                            result = self.validate_resource(resource_type, resource)
                            if not result["valid"]:
                                for error in result["errors"]:
                                    errors.append(
                                        f"Entry {i} ({resource_type}): {error}"
                                    )
                                for warning in result["warnings"]:
                                    warnings.append(
                                        f"Entry {i} ({resource_type}): {warning}"
                                    )

        return {"valid": len(errors) == 0, "errors": errors, "warnings": warnings}

    def validate_resource(
        self, resource_type: str, resource_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Validate any FHIR resource based on type."""
        validators = {
            "Patient": self.validate_patient,
            "Observation": self.validate_observation,
            "Immunization": self.validate_immunization,
            "Bundle": self.validate_bundle,
        }

        if validator := validators.get(resource_type):
            result: Dict[str, Any] = validator(resource_data)
            return result
        else:
            return {
                "valid": False,
                "errors": [
                    f"No validator available for resource type: {resource_type}"
                ],
                "warnings": [],
            }

    def _validate_date_format(self, date_str: str) -> bool:
        """Validate FHIR date format (YYYY-MM-DD)."""
        try:
            datetime.strptime(date_str, "%Y-%m-%d")
            return True
        except ValueError:
            return False

    def _validate_datetime_format(self, datetime_str: str) -> bool:
        """Validate FHIR datetime format."""
        formats = [
            "%Y-%m-%dT%H:%M:%S%z",
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d",
        ]

        for fmt in formats:
            try:
                datetime.strptime(datetime_str.replace("+00:00", "+0000"), fmt)
                return True
            except ValueError:
                continue
        return False

    def _validate_phone(self, phone: str) -> bool:
        """Validate phone number format."""
        # Basic international phone validation
        pattern = r"^\+?[1-9]\d{1,14}$"
        return bool(re.match(pattern, phone.replace(" ", "").replace("-", "")))

    def _validate_email(self, email: str) -> bool:
        """Validate email format."""
        pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        return bool(re.match(pattern, email))
