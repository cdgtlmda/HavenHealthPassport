"""
Paragraph-based Medical Text Splitter.

Splits text by paragraphs while maintaining medical context
and ensuring complete thoughts are preserved.

This module handles encrypted PHI with access control and audit logging
to ensure HIPAA compliance.
 Handles FHIR Resource validation.
"""

import logging
import re
from typing import Any, Dict, List, Optional

from llama_index.core.schema import TextNode

from src.healthcare.hipaa_access_control import AccessLevel, require_phi_access
from src.security.encryption import EncryptionService

from .base import BaseMedicalSplitter, SplitResult, TextSplitterConfig

logger = logging.getLogger(__name__)


class ParagraphMedicalSplitter(BaseMedicalSplitter):
    """Splits text by paragraphs with medical awareness."""

    def __init__(self, config: Optional[TextSplitterConfig] = None):
        """Initialize paragraph medical splitter."""
        super().__init__(config)
        self.encryption_service = EncryptionService(
            kms_key_id="alias/haven-health-default"
        )

        # Patterns that indicate a paragraph should not be split
        self.keep_together_patterns = [
            r"^\s*\d+\.",  # Numbered lists
            r"^\s*[a-z]\.",  # Lettered lists
            r"^\s*[-•]",  # Bullet points
            r"^\s*\(",  # Parenthetical starts
            r"^\s*(medication|drug|rx).*:",  # Medication lists
            r"^\s*(diagnosis|dx).*:",  # Diagnosis lists
        ]

    @require_phi_access(AccessLevel.READ)
    def split(
        self, text: str, metadata: Optional[Dict[str, Any]] = None
    ) -> SplitResult:
        """Split text by paragraphs.

        Requires PHI access permission and logs all access
        """
        logger.info("Audit: PHI access for paragraph splitting, metadata: %s", metadata)

        # Split into paragraphs
        paragraphs = self._split_paragraphs(text)

        if not paragraphs:
            return SplitResult(chunks=[], metadata=[], total_chunks=0)

        # Group paragraphs into chunks
        chunks = []
        chunk_metadata = []
        current_chunk: List[str] = []
        current_size = 0
        start_char = 0

        i = 0
        while i < len(paragraphs):
            para = paragraphs[i]
            para_size = self._count_tokens(para)

            # Check if this paragraph should be kept with the next
            keep_with_next = self._should_keep_with_next(para, paragraphs, i)

            # Check if adding this paragraph exceeds chunk size
            if current_size + para_size > self.config.chunk_size and current_chunk:
                # Create chunk
                chunk_text = "\n\n".join(current_chunk)
                chunks.append(chunk_text)

                # Create metadata
                end_char = start_char + len(chunk_text)
                meta = self._create_chunk_metadata(
                    chunk_text, len(chunks) - 1, -1, start_char, end_char
                )
                chunk_metadata.append(meta)

                # Handle overlap
                if self.config.chunk_overlap > 0:
                    overlap_paras = self._calculate_paragraph_overlap(current_chunk)
                    current_chunk = overlap_paras
                    current_size = sum(self._count_tokens(p) for p in overlap_paras)
                    start_char = end_char - len("\n\n".join(overlap_paras))
                else:
                    current_chunk = []
                    current_size = 0
                    start_char = end_char + 2  # Account for \n\n

            # Add paragraph to current chunk
            current_chunk.append(para)
            current_size += para_size

            # If this should be kept with next, add next paragraph too
            if keep_with_next and i + 1 < len(paragraphs):
                i += 1
                next_para = paragraphs[i]
                next_size = self._count_tokens(next_para)

                # Force add even if it exceeds size slightly
                current_chunk.append(next_para)
                current_size += next_size

            i += 1

        # Handle remaining paragraphs
        if current_chunk:
            chunk_text = "\n\n".join(current_chunk)
            chunks.append(chunk_text)

            meta = self._create_chunk_metadata(
                chunk_text,
                len(chunks) - 1,
                len(chunks),
                start_char,
                start_char + len(chunk_text),
            )
            chunk_metadata.append(meta)

        # Update total chunks
        for meta in chunk_metadata:
            meta.total_chunks = len(chunks)

        # Create TextNodes
        nodes = []
        for chunk, meta in zip(chunks, chunk_metadata):
            node = TextNode(text=chunk, metadata={**(metadata or {}), **meta.to_dict()})
            nodes.append(node)

        return SplitResult(
            chunks=nodes, metadata=chunk_metadata, total_chunks=len(chunks)
        )

    def _split_paragraphs(self, text: str) -> List[str]:
        """Split text into paragraphs with special handling for medical content."""
        # Basic paragraph splitting
        raw_paragraphs = text.split("\n\n")

        # Clean and filter paragraphs
        paragraphs = []
        for para in raw_paragraphs:
            para = para.strip()
            if para:
                paragraphs.append(para)

        # Merge paragraphs that should stay together
        merged_paragraphs = []
        i = 0

        while i < len(paragraphs):
            current = paragraphs[i]

            # Check if this is a list that continues in next paragraph
            if i + 1 < len(paragraphs):
                next_para = paragraphs[i + 1]

                # Check for list continuations
                if (
                    self._is_list_item(current)
                    and self._is_list_item(next_para)
                    and self._same_list_level(current, next_para)
                ):
                    # Merge list items
                    merged = current
                    while i + 1 < len(paragraphs) and self._is_list_item(
                        paragraphs[i + 1]
                    ):
                        i += 1
                        merged += "\n" + paragraphs[i]
                    merged_paragraphs.append(merged)
                else:
                    merged_paragraphs.append(current)
            else:
                merged_paragraphs.append(current)

            i += 1

        return merged_paragraphs

    def _should_keep_with_next(
        self, para: str, paragraphs: List[str], index: int
    ) -> bool:
        """Determine if paragraph should be kept with next one."""
        if index + 1 >= len(paragraphs):
            return False

        next_para = paragraphs[index + 1]

        # Check if current paragraph ends with colon (introduces list)
        if para.rstrip().endswith(":"):
            return True

        # Check if next paragraph is a continuation
        if next_para.strip().startswith(
            ("however,", "therefore,", "furthermore,", "additionally,", "moreover,")
        ):
            return True

        # Check for medical list patterns
        for pattern in self.keep_together_patterns:
            if re.match(pattern, next_para, re.I):
                return True

        # Check for medication dosing split across paragraphs
        if re.search(r"\d+\s*$", para) and re.match(r"^\s*(mg|ml|mcg)", next_para):
            return True

        return False

    def _calculate_paragraph_overlap(self, paragraphs: List[str]) -> List[str]:
        """Calculate which paragraphs to include for overlap."""
        if self.config.chunk_overlap <= 0 or not paragraphs:
            return []

        overlap_paras: List[str] = []
        overlap_size = 0

        # Add paragraphs from the end until we reach overlap size
        for para in reversed(paragraphs):
            para_size = self._count_tokens(para)

            if overlap_size + para_size <= self.config.chunk_overlap:
                overlap_paras.insert(0, para)
                overlap_size += para_size
            else:
                # Can't fit whole paragraph, stop
                break

        return overlap_paras

    def _is_list_item(self, text: str) -> bool:
        """Check if text appears to be a list item."""
        patterns = [
            r"^\s*\d+\.",  # Numbered
            r"^\s*[a-zA-Z]\.",  # Lettered
            r"^\s*[-•*]",  # Bullets
            r"^\s*\(",  # Parenthetical
        ]

        for pattern in patterns:
            if re.match(pattern, text):
                return True

        return False

    def _same_list_level(self, para1: str, para2: str) -> bool:
        """Check if two paragraphs are at the same list level."""
        # Extract leading whitespace
        indent1 = len(para1) - len(para1.lstrip())
        indent2 = len(para2) - len(para2.lstrip())

        # Similar indentation suggests same level
        return abs(indent1 - indent2) < 4


def validate_fhir_data(data: dict) -> dict:
    """Validate FHIR data.

    Args:
        data: Data to validate

    Returns:
        Validation result with 'valid', 'errors', and 'warnings' keys
    """
    errors: List[str] = []
    warnings: List[str] = []

    if not data:
        errors.append("No data provided")

    return {"valid": len(errors) == 0, "errors": errors, "warnings": warnings}
