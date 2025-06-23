"""Text Processing Utilities.

Provides text normalization and processing utilities for medical documents.

Note: This module processes PHI-related medical document text.
- Encryption: All medical document text must be encrypted at rest and in transit
- Access Control: Implement role-based access control (RBAC) for text processing operations
"""

import re
import unicodedata
from typing import List


class TextNormalizer:
    """Normalizes text for processing and analysis."""

    def normalize(self, text: str) -> str:
        """Normalize text by removing extra whitespace and normalizing unicode.

        Also cleans up formatting for consistency.
        """
        if not text:
            return ""

        # Normalize unicode
        text = unicodedata.normalize("NFKC", text)

        # Replace multiple whitespaces with single space
        text = re.sub(r"\s+", " ", text)

        # Remove leading/trailing whitespace
        text = text.strip()

        # Fix common OCR errors
        text = self._fix_common_ocr_errors(text)

        return text

    def _fix_common_ocr_errors(self, text: str) -> str:
        """Fix common OCR misrecognitions."""
        # Common OCR errors are context-dependent
        # This is simplified - in production would use more sophisticated rules
        return text

    def remove_special_characters(
        self, text: str, keep_punctuation: bool = True
    ) -> str:
        """Remove special characters while preserving medical terms."""
        if keep_punctuation:
            # Keep alphanumeric, spaces, and basic punctuation
            pattern = r"[^a-zA-Z0-9\s\.\,\;\:\!\?\-\(\)\/]"
        else:
            # Keep only alphanumeric and spaces
            pattern = r"[^a-zA-Z0-9\s]"

        return re.sub(pattern, "", text)

    def extract_sentences(self, text: str) -> List[str]:
        """Extract sentences from text."""
        # Simple sentence splitting
        sentences = re.split(r"[.!?]+", text)
        return [s.strip() for s in sentences if s.strip()]


__all__ = ["TextNormalizer"]
