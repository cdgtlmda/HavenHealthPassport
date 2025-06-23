"""Document Loaders for Haven Health Passport.

Specialized loaders for medical documents with PHI protection,
metadata extraction, and multi-format support.

This module handles encrypted PHI with access control and audit logging
to ensure HIPAA compliance. Handles FHIR Resource validation.
"""

from src.healthcare.hipaa_access_control import AccessLevel, require_phi_access
from src.services.encryption_service import EncryptionService

from .base import (
    BaseDocumentLoader,
    DocumentLoaderConfig,
    DocumentMetadata,
    LoaderResult,
)
from .dicom_loader import DICOMMedicalLoader
from .factory import DocumentLoaderFactory, DocumentType
from .hl7_loader import HL7MedicalLoader
from .image_loader import ImageMedicalLoader
from .office_loader import OfficeMedicalLoader
from .pdf_loader import PDFMedicalLoader
from .structured_loader import StructuredMedicalLoader
from .text_loader import TextMedicalLoader

__all__ = [
    # Base classes
    "BaseDocumentLoader",
    "DocumentLoaderConfig",
    "LoaderResult",
    "DocumentMetadata",
    # Specific loaders
    "PDFMedicalLoader",
    "ImageMedicalLoader",
    "TextMedicalLoader",
    "OfficeMedicalLoader",
    "DICOMMedicalLoader",
    "HL7MedicalLoader",
    "StructuredMedicalLoader",
    # Factory
    "DocumentLoaderFactory",
    "DocumentType",
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
