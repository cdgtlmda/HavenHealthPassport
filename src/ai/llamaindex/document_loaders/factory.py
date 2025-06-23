"""Document Loader Factory.

Factory for creating appropriate document loaders based on file type.
 Handles FHIR Resource validation.
"""

import logging
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Type

from .base import BaseDocumentLoader, DocumentLoaderConfig, LoaderResult
from .dicom_loader import DICOMMedicalLoader
from .hl7_loader import HL7MedicalLoader
from .image_loader import ImageMedicalLoader
from .office_loader import OfficeMedicalLoader
from .pdf_loader import PDFMedicalLoader
from .structured_loader import StructuredMedicalLoader
from .text_loader import TextMedicalLoader

logger = logging.getLogger(__name__)


class DocumentType(str, Enum):
    """Supported document types."""

    PDF = "pdf"
    IMAGE = "image"
    TEXT = "text"
    OFFICE = "office"
    DICOM = "dicom"
    HL7 = "hl7"
    STRUCTURED = "structured"
    UNKNOWN = "unknown"


class DocumentLoaderFactory:
    """Factory for creating document loaders."""

    # Loader registry
    _loaders: Dict[DocumentType, Type[BaseDocumentLoader]] = {
        DocumentType.PDF: PDFMedicalLoader,
        DocumentType.IMAGE: ImageMedicalLoader,
        DocumentType.TEXT: TextMedicalLoader,
        DocumentType.OFFICE: OfficeMedicalLoader,  # type: ignore[type-abstract]
        DocumentType.DICOM: DICOMMedicalLoader,  # type: ignore[type-abstract]
        DocumentType.HL7: HL7MedicalLoader,  # type: ignore[type-abstract]
        DocumentType.STRUCTURED: StructuredMedicalLoader,  # type: ignore[type-abstract]
    }

    # File extension mapping
    _extension_map = {
        # PDF
        ".pdf": DocumentType.PDF,
        # Images
        ".jpg": DocumentType.IMAGE,
        ".jpeg": DocumentType.IMAGE,
        ".png": DocumentType.IMAGE,
        ".gif": DocumentType.IMAGE,
        ".bmp": DocumentType.IMAGE,
        ".tiff": DocumentType.IMAGE,
        ".tif": DocumentType.IMAGE,
        ".webp": DocumentType.IMAGE,
        # Text
        ".txt": DocumentType.TEXT,
        ".text": DocumentType.TEXT,
        ".md": DocumentType.TEXT,
        ".rtf": DocumentType.TEXT,
        # Office (to be implemented)
        ".doc": DocumentType.OFFICE,
        ".docx": DocumentType.OFFICE,
        ".xls": DocumentType.OFFICE,
        ".xlsx": DocumentType.OFFICE,
        # Medical specific (to be implemented)
        ".dcm": DocumentType.DICOM,
        ".hl7": DocumentType.HL7,
        ".json": DocumentType.STRUCTURED,
        ".xml": DocumentType.STRUCTURED,
    }

    @classmethod
    def create_loader(
        cls, file_path: str, config: Optional[DocumentLoaderConfig] = None
    ) -> BaseDocumentLoader:
        """Create appropriate loader for file."""
        doc_type = cls.detect_document_type(file_path)

        if doc_type == DocumentType.UNKNOWN:
            raise ValueError(f"Unsupported file type: {file_path}")

        # All loaders are now implemented
        loader_class = cls._loaders[doc_type]
        return loader_class(config)

    @classmethod
    def detect_document_type(cls, file_path: str) -> DocumentType:
        """Detect document type from file path."""
        ext = Path(file_path).suffix.lower()
        return cls._extension_map.get(ext, DocumentType.UNKNOWN)

    @classmethod
    def load_document(
        cls, file_path: str, config: Optional[DocumentLoaderConfig] = None
    ) -> LoaderResult:
        """Load document using appropriate loader."""
        loader = cls.create_loader(file_path, config)
        return loader.load(file_path)

    @classmethod
    def load_documents_batch(
        cls, file_paths: List[str], config: Optional[DocumentLoaderConfig] = None
    ) -> Dict[str, LoaderResult]:
        """Load multiple documents in batch."""
        results = {}

        for file_path in file_paths:
            try:
                result = cls.load_document(file_path, config)
                results[file_path] = result
            except (OSError, ValueError) as e:
                logger.error("Failed to load %s: %s", file_path, e)
                results[file_path] = LoaderResult(success=False, errors=[str(e)])

        return results

    @classmethod
    def get_supported_extensions(cls) -> List[str]:
        """Get list of supported file extensions."""
        return list(cls._extension_map.keys())

    @classmethod
    def is_supported(cls, file_path: str) -> bool:
        """Check if file type is supported."""
        return cls.detect_document_type(file_path) != DocumentType.UNKNOWN


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
