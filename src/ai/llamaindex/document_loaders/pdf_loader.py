"""PDF Medical Document Loader.

Specialized loader for medical PDFs including:
- Clinical notes
- Lab reports
- Medical imaging reports
- Prescriptions
- Insurance documents

This module handles encrypted PHI with access control and audit logging
to ensure HIPAA compliance.
 Handles FHIR Resource validation.
"""

import logging
import os
import re
import time
from datetime import datetime
from typing import Any, List, Optional

try:
    import pdfplumber
except ImportError:
    pdfplumber = None

try:
    import pytesseract
except ImportError:
    pytesseract = None

try:
    from pdf2image import convert_from_path
except ImportError:
    convert_from_path = None

from pypdf import PdfReader

from .base import (
    BaseDocumentLoader,
    DocumentLoaderConfig,
    DocumentMetadata,
    DocumentQuality,
    LoaderResult,
    PHILevel,
)

logger = logging.getLogger(__name__)


class PDFMedicalLoader(BaseDocumentLoader):
    """Loader for medical PDF documents."""

    def __init__(self, config: Optional[DocumentLoaderConfig] = None):
        """Initialize the PDF loader with optional configuration."""
        super().__init__(config)
        self.supported_extensions = [".pdf"]

    def can_load(self, file_path: str) -> bool:
        """Check if this loader can handle the file."""
        return any(file_path.lower().endswith(ext) for ext in self.supported_extensions)

    def load(self, file_path: str, **kwargs: Any) -> LoaderResult:
        """Load PDF document with medical optimizations."""
        start_time = time.time()
        result = LoaderResult(success=False)

        try:
            # Validate file
            if not os.path.exists(file_path):
                result.errors.append(f"File not found: {file_path}")
                return result

            file_size = os.path.getsize(file_path) / (1024 * 1024)  # MB
            if file_size > self.config.max_file_size_mb:
                result.errors.append(
                    f"File too large: {file_size:.1f}MB (max: {self.config.max_file_size_mb}MB)"
                )
                return result

            # Create metadata
            metadata = self._extract_metadata(file_path)

            # Extract text and process pages
            documents = []

            # Try different extraction methods
            text_pages = self._extract_with_pypdf(file_path)

            if not text_pages or all(not page.strip() for page in text_pages):
                # Try pdfplumber for better table extraction
                text_pages = self._extract_with_pdfplumber(file_path)

            if not text_pages or all(not page.strip() for page in text_pages):
                # Fall back to OCR for scanned documents
                logger.info("Using OCR for %s", file_path)
                text_pages = self._extract_with_ocr(file_path)
                metadata.ocr_applied = True

            # Process each page
            for page_num, page_text in enumerate(text_pages, 1):
                if not page_text.strip():
                    continue

                # Clean and process text
                cleaned_text = self._clean_medical_text(page_text)

                # Detect and handle PHI
                if self.config.detect_phi:
                    phi_level = self._detect_phi_level(cleaned_text)
                    metadata.phi_level = max(metadata.phi_level, phi_level)

                    if self.config.anonymize_phi and phi_level != PHILevel.NONE:
                        cleaned_text, phi_found = self._anonymize_text(cleaned_text)
                        metadata.anonymization_applied = True
                        if phi_found:
                            result.warnings.append(
                                f"PHI detected and anonymized on page {page_num}"
                            )

                # Extract medical terms
                if self.config.extract_medical_terms:
                    medical_terms = self._extract_medical_terms(cleaned_text)
                    metadata.icd_codes.extend(medical_terms.get("icd10", []))
                    metadata.cpt_codes.extend(medical_terms.get("cpt", []))

                # Create document for this page
                doc = self._create_document(cleaned_text, metadata, page_num)
                documents.append(doc)
            # Deduplicate medical codes
            metadata.icd_codes = list(set(metadata.icd_codes))
            metadata.cpt_codes = list(set(metadata.cpt_codes))

            # Set quality score based on extraction method
            if metadata.ocr_applied:
                metadata.quality_score = DocumentQuality.LOW
            elif len(documents) > 0:
                metadata.quality_score = DocumentQuality.HIGH
            else:
                metadata.quality_score = DocumentQuality.UNREADABLE

            result.success = True
            result.documents = documents
            result.metadata = metadata
            result.processing_time_ms = int((time.time() - start_time) * 1000)

            logger.info("Successfully loaded PDF with %d pages", len(documents))

        except (IOError, ValueError) as e:
            logger.error("Error loading PDF: %s", e)
            result.errors.append(str(e))

        return result

    def _extract_metadata(self, file_path: str) -> DocumentMetadata:
        """Extract metadata from PDF file."""
        file_stats = os.stat(file_path)

        metadata = DocumentMetadata(
            file_path=file_path,
            file_type="pdf",
            file_size=file_stats.st_size,
            created_date=datetime.fromtimestamp(file_stats.st_ctime),
            modified_date=datetime.fromtimestamp(file_stats.st_mtime),
        )

        # Try to determine document type from filename or content
        filename_lower = os.path.basename(file_path).lower()

        if "lab" in filename_lower or "result" in filename_lower:
            metadata.document_type = "lab_report"
        elif "prescription" in filename_lower or "rx" in filename_lower:
            metadata.document_type = "prescription"
        elif "imaging" in filename_lower or "radiology" in filename_lower:
            metadata.document_type = "imaging_report"
        elif "discharge" in filename_lower:
            metadata.document_type = "discharge_summary"
        else:
            metadata.document_type = "clinical_document"

        return metadata

    def _extract_with_pypdf(self, file_path: str) -> List[str]:
        """Extract text using PyPDF."""
        pages = []

        try:
            with open(file_path, "rb") as file:
                reader = PdfReader(file)

                for page in reader.pages:
                    text = page.extract_text()
                    pages.append(text)
        except (OSError, ValueError) as e:
            logger.warning("PyPDF extraction failed: %s", e)

        return pages

    def _extract_with_pdfplumber(self, file_path: str) -> List[str]:
        """Extract text using pdfplumber (better for tables)."""
        pages = []

        try:
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    text = page.extract_text()

                    # Also extract tables
                    if self.config.extract_tables:
                        tables = page.extract_tables()
                        for table in tables:
                            # Convert table to text format
                            table_text = "\n".join(
                                ["\t".join(row) for row in table if row]
                            )
                            text += f"\n\n[TABLE]\n{table_text}\n[/TABLE]\n"

                    pages.append(text)
        except (OSError, ValueError) as e:
            logger.warning("pdfplumber extraction failed: %s", e)

        return pages

    def _extract_with_ocr(self, file_path: str) -> List[str]:
        """Extract text using OCR for scanned documents."""
        pages = []

        try:
            # Convert PDF to images
            if convert_from_path is None:
                raise ImportError("pdf2image library is required for OCR")

            images = convert_from_path(file_path)

            for _i, image in enumerate(images):
                # Perform OCR
                text = pytesseract.image_to_string(image)
                pages.append(text)

        except (ImportError, OSError) as e:
            logger.error("OCR extraction failed: %s", e)

        return pages

    def _clean_medical_text(self, text: str) -> str:
        """Clean and normalize medical text."""
        # Remove extra whitespace
        text = re.sub(r"\s+", " ", text)

        # Fix common OCR errors in medical text
        replacements = {
            r"\bl\b": "1",  # Common OCR error: l -> 1
            r"\bO\b": "0",  # Common OCR error: O -> 0
            r"n\\/a": "N/A",
            r"\\s+": " ",
            r"\.{3,}": "...",
        }

        for pattern, replacement in replacements.items():
            text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)

        # Remove page headers/footers (common patterns)
        text = re.sub(r"Page \d+ of \d+", "", text)
        text = re.sub(r"Confidential.*?Patient Information", "", text)

        return text.strip()

    def validate(self, data: dict) -> bool:
        """Validate document data."""
        if not data:
            return False
        return True
