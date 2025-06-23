"""Text Preprocessing Module - utilities for medical document text processing.

Note: This module processes PHI-related medical text data.
- Encryption: All processed medical text data must be encrypted at rest and in transit
- Access Control: Implement role-based access control (RBAC) for medical text processing
"""

import logging
import re
import unicodedata
from typing import Dict, List

logger = logging.getLogger(__name__)


class TextPreprocessor:
    """Preprocesses text extracted from medical documents."""

    def __init__(self) -> None:
        """Initialize text preprocessor with OCR corrections."""
        # Common OCR errors and medical replacements
        self.ocr_corrections = {
            "rng": "mg",
            "rnl": "ml",
            "rnedication": "medication",
            "prescnption": "prescription",
        }
        self.medical_replacements = {
            "mcg": "μg",
            "ug": "μg",
            "degrees": "°",
            "alpha": "α",
            "beta": "β",
            "gamma": "γ",
            "delta": "Δ",
        }

    def preprocess(self, text: str) -> str:
        """Apply all preprocessing steps to text."""
        text = self.normalize_unicode(text)
        text = self.fix_ocr_errors(text)
        text = self.clean_whitespace(text)
        text = self.standardize_medical_notation(text)
        return text

    def normalize_unicode(self, text: str) -> str:
        """Normalize unicode characters."""
        nfd = unicodedata.normalize("NFD", text)
        return "".join(char for char in nfd if unicodedata.category(char) != "Mn")

    def clean_whitespace(self, text: str) -> str:
        """Clean and normalize whitespace."""
        text = re.sub(r"\s+", " ", text)
        text = re.sub(r"\s+([.,;:!?])", r"\1", text)
        text = re.sub(r"([.,;:!?])(\w)", r"\1 \2", text)
        return text.strip()

    def fix_ocr_errors(self, text: str) -> str:
        """Fix common OCR errors in medical text."""
        for old, new in self.ocr_corrections.items():
            text = text.replace(old, new)
        return text

    def standardize_medical_notation(self, text: str) -> str:
        """Standardize medical notation and symbols."""
        for old, new in self.medical_replacements.items():
            text = text.replace(old, new)
        # Standardize dosage formats
        text = re.sub(r"(\d+)\s*(mg|g|ml|l)", r"\1\2", text)
        return text

    def extract_structured_data(self, text: str) -> Dict[str, List[str]]:
        """Extract structured data like dosages, dates, etc."""
        structured = {
            "dosages": re.findall(
                r"\d+\.?\d*\s*(mg|g|ml|l|mcg|μg|units?|iu)", text, re.IGNORECASE
            ),
            "dates": re.findall(r"\d{1,2}[/-]\d{1,2}[/-]\d{2,4}", text),
            "times": re.findall(r"\d{1,2}:\d{2}\s*(am|pm)?", text, re.IGNORECASE),
            "percentages": re.findall(r"\d+\.?\d*\s*%", text),
        }
        return structured
