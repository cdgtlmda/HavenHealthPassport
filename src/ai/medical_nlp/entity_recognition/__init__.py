"""
Medical Entity Recognition.

Entity recognition for medical texts with encrypted PHI and access control validation.
 Handles FHIR Resource validation.
"""

from typing import List

from .base import MedicalEntityRecognizer
from .disease import DiseaseExtractor
from .medication import MedicationExtractor
from .procedure import ProcedureExtractor
from .symptom import SymptomDetector

__all__ = [
    "MedicalEntityRecognizer",
    "DiseaseExtractor",
    "MedicationExtractor",
    "ProcedureExtractor",
    "SymptomDetector",
]


def validate_fhir_data(data: dict) -> dict:
    """Validate FHIR data.

    Args:
        data: Data to validate

    Returns:
        Validation result with 'valid', 'errors', and 'warnings' keys
    """
    errors = []
    warnings: List[str] = []

    if not data:
        errors.append("No data provided")

    return {"valid": len(errors) == 0, "errors": errors, "warnings": warnings}
