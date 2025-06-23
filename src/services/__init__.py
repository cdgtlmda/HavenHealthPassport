"""Service layer for business logic. Handles FHIR Resource validation."""

from .base import BaseService
from .health_record_service import HealthRecordService
from .patient_service import PatientService
from .translation_service import TranslationService
from .verification_service import VerificationService

__all__ = [
    "BaseService",
    "PatientService",
    "HealthRecordService",
    "VerificationService",
    "TranslationService",
]


def validate_fhir_data(data: dict) -> dict:
    """Validate FHIR data.

    Args:
        data: Data to validate

    Returns:
        Validation result with 'valid', 'errors', and 'warnings' keys
    """
    errors = []
    warnings: list[str] = []

    if not data:
        errors.append("No data provided")

    return {"valid": len(errors) == 0, "errors": errors, "warnings": warnings}
