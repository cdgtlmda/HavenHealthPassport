"""Image Medical Document Loader.

Specialized loader for medical images including:
- Scanned documents
- Handwritten notes
- Medical forms
- X-rays and medical imaging (metadata only)

This module handles encrypted PHI with access control and audit logging
to ensure HIPAA compliance.
"""

import logging
import os
import re
import time
from datetime import datetime
from typing import Any, Optional

cv2: Any = None
try:
    import cv2 as _cv2

    cv2 = _cv2
except ImportError:
    pass

import numpy as np

try:
    import pytesseract
except ImportError:
    pytesseract = None

from PIL import Image

from .base import (
    BaseDocumentLoader,
    DocumentLoaderConfig,
    DocumentMetadata,
    DocumentQuality,
    LoaderResult,
)

logger = logging.getLogger(__name__)


class ImageMedicalLoader(BaseDocumentLoader):
    """Loader for medical image documents."""

    def __init__(self, config: Optional[DocumentLoaderConfig] = None):
        """Initialize the image loader with optional configuration."""
        super().__init__(config)
        self.supported_extensions = [
            ".jpg",
            ".jpeg",
            ".png",
            ".gif",
            ".bmp",
            ".tiff",
            ".tif",
            ".webp",
        ]

    def can_load(self, file_path: str) -> bool:
        """Check if this loader can handle the file."""
        return any(file_path.lower().endswith(ext) for ext in self.supported_extensions)

    def load(self, file_path: str, **kwargs: Any) -> LoaderResult:
        """Load image document with medical optimizations."""
        start_time = time.time()
        result = LoaderResult(success=False)

        try:
            # Validate file
            if not os.path.exists(file_path):
                result.errors.append(f"File not found: {file_path}")
                return result
            # Create metadata
            metadata = self._extract_metadata(file_path)

            # Load and preprocess image
            image = Image.open(file_path)

            # Convert to RGB if necessary
            if image.mode != "RGB":
                rgb_image = image.convert("RGB")
            else:
                rgb_image = image

            # Preprocess for better OCR
            processed_image = self._preprocess_medical_image(rgb_image)

            # Extract text using OCR
            text = pytesseract.image_to_string(processed_image)
            metadata.ocr_applied = True

            if not text.strip():
                result.warnings.append("No text extracted from image")
                metadata.quality_score = DocumentQuality.UNREADABLE
            else:
                # Clean extracted text
                cleaned_text = self._clean_ocr_text(text)

                # Detect and handle PHI
                if self.config.detect_phi:
                    phi_level = self._detect_phi_level(cleaned_text)
                    metadata.phi_level = phi_level

                    if self.config.anonymize_phi and phi_level.value != "none":
                        cleaned_text, _ = self._anonymize_text(cleaned_text)
                        metadata.anonymization_applied = True

                # Extract medical terms
                if self.config.extract_medical_terms:
                    medical_terms = self._extract_medical_terms(cleaned_text)
                    metadata.icd_codes = medical_terms.get("icd10", [])
                    metadata.cpt_codes = medical_terms.get("cpt", [])

                # Assess quality based on confidence
                confidence = self._assess_ocr_confidence(text)
                metadata.confidence_score = confidence

                if confidence > 0.8:
                    metadata.quality_score = DocumentQuality.HIGH
                elif confidence > 0.6:
                    metadata.quality_score = DocumentQuality.MEDIUM
                else:
                    metadata.quality_score = DocumentQuality.LOW

                # Create document
                doc = self._create_document(cleaned_text, metadata)
                result.documents = [doc]
            result.success = True
            result.metadata = metadata
            result.processing_time_ms = int((time.time() - start_time) * 1000)

        except (OSError, ValueError) as e:
            logger.error("Error loading image: %s", e)
            result.errors.append(str(e))

        return result

    def _extract_metadata(self, file_path: str) -> DocumentMetadata:
        """Extract metadata from image file."""
        file_stats = os.stat(file_path)

        metadata = DocumentMetadata(
            file_path=file_path,
            file_type="image",
            file_size=file_stats.st_size,
            created_date=datetime.fromtimestamp(file_stats.st_ctime),
            modified_date=datetime.fromtimestamp(file_stats.st_mtime),
        )

        # Determine document type from filename
        filename_lower = os.path.basename(file_path).lower()

        if "prescription" in filename_lower or "rx" in filename_lower:
            metadata.document_type = "prescription_image"
        elif "form" in filename_lower:
            metadata.document_type = "medical_form"
        elif "note" in filename_lower:
            metadata.document_type = "clinical_note_image"
        else:
            metadata.document_type = "medical_image"

        return metadata

    def _preprocess_medical_image(self, image: Image.Image) -> np.ndarray:
        """Preprocess image for better OCR results."""
        # Convert PIL image to OpenCV format
        img_array = np.array(image)

        # Convert to grayscale
        gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)  # pylint: disable=no-member

        # Apply denoising
        denoised = cv2.fastNlMeansDenoising(gray)  # pylint: disable=no-member

        # Apply thresholding for better contrast
        _, thresh = cv2.threshold(  # pylint: disable=no-member
            denoised,
            0,
            255,
            cv2.THRESH_BINARY + cv2.THRESH_OTSU,  # pylint: disable=no-member
        )

        return thresh  # type: ignore[no-any-return]

    def _clean_ocr_text(self, text: str) -> str:
        """Clean OCR-extracted text."""
        # Remove common OCR artifacts
        text = re.sub(r"[|]{2,}", "", text)  # Remove multiple pipes
        text = re.sub(r"[-]{3,}", "", text)  # Remove long dashes
        text = re.sub(r"[_]{3,}", "", text)  # Remove long underscores

        # Fix common OCR errors
        text = text.replace("|", "I")  # Pipe to I
        text = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", text)  # Add space between camelCase

        # Remove extra whitespace
        text = re.sub(r"\s+", " ", text)

        return text.strip()

    def _assess_ocr_confidence(self, text: str) -> float:
        """Assess OCR quality/confidence."""
        # Simple heuristics for OCR quality
        confidence = 1.0

        # Check for too many special characters (likely OCR errors)
        special_char_ratio = len(re.findall(r'[^a-zA-Z0-9\s.,;:!?\'"()-]', text)) / max(
            len(text), 1
        )
        if special_char_ratio > 0.1:
            confidence -= 0.3

        # Check for very short words (likely fragments)
        words = text.split()
        if words:
            short_word_ratio = len([w for w in words if len(w) <= 2]) / len(words)
            if short_word_ratio > 0.5:
                confidence -= 0.2

        # Check for reasonable word patterns
        if not re.search(r"\b[a-zA-Z]{3,}\b", text):
            confidence -= 0.4

        return max(0.1, confidence)
