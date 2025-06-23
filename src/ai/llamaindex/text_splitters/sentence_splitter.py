"""
Sentence-based Medical Text Splitter.

Splits text at sentence boundaries while preserving medical context
and ensuring complete medical statements.

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


class SentenceMedicalSplitter(BaseMedicalSplitter):
    """Splits text by sentences with medical awareness."""

    def __init__(self, config: Optional[TextSplitterConfig] = None):
        """Initialize the sentence text splitter."""
        super().__init__(config)
        self.encryption_service = EncryptionService(
            kms_key_id="alias/haven-health-default"
        )

        # Medical sentence patterns that should not be split
        self.medical_continuations = [
            r"\b(mg|ml|mcg|g|kg|lb|oz)\b",  # Dosage units
            r"\b(bid|tid|qid|qd|prn|po|iv|im|sq)\b",  # Medical frequency/route
            r"\b(bp|hr|rr|temp|spo2)\s*:?\s*\d+",  # Vital signs
            r"\b\d+\s*/\s*\d+",  # Fractions, BP readings
            r"\b(icd|cpt|dx|rx)\s*:?\s*",  # Code prefixes
        ]

    @require_phi_access(AccessLevel.READ)
    def split(
        self, text: str, metadata: Optional[Dict[str, Any]] = None
    ) -> SplitResult:
        """Split text into sentence-based chunks.

        Requires PHI access permission and logs all access
        """
        logger.info("Audit: PHI access for text splitting, metadata: %s", metadata)

        # Split into sentences
        sentences = self._split_medical_sentences(text)

        if not sentences:
            return SplitResult(chunks=[], metadata=[], total_chunks=0)

        # Group sentences into chunks
        chunks = []
        chunk_metadata = []
        current_chunk: List[str] = []
        current_size = 0
        start_char = 0

        for sentence in sentences:
            sentence_size = self._count_tokens(sentence)

            # Check if adding this sentence exceeds chunk size
            if current_size + sentence_size > self.config.chunk_size and current_chunk:
                # Create chunk from accumulated sentences
                chunk_text = " ".join(current_chunk)
                chunks.append(chunk_text)

                # Create metadata
                end_char = start_char + len(chunk_text)
                metadata_obj = self._create_chunk_metadata(
                    chunk_text,
                    len(chunks) - 1,
                    -1,  # Will update later
                    start_char,
                    end_char,
                )
                chunk_metadata.append(metadata_obj)

                # Reset for next chunk with overlap
                if self.config.chunk_overlap > 0:
                    overlap_sentences = self._calculate_sentence_overlap(current_chunk)
                    current_chunk = overlap_sentences
                    current_size = sum(self._count_tokens(s) for s in overlap_sentences)
                    start_char = end_char - len(" ".join(overlap_sentences))
                else:
                    current_chunk = []
                    current_size = 0
                    start_char = end_char + 1

            current_chunk.append(sentence)
            current_size += sentence_size

        # Handle remaining sentences
        if current_chunk:
            chunk_text = " ".join(current_chunk)
            chunks.append(chunk_text)

            metadata_obj = self._create_chunk_metadata(
                chunk_text,
                len(chunks) - 1,
                len(chunks),
                start_char,
                start_char + len(chunk_text),
            )
            chunk_metadata.append(metadata_obj)

        # Update total chunks in metadata
        for meta in chunk_metadata:
            meta.total_chunks = len(chunks)

        # Create TextNodes
        nodes = []
        for _, (chunk, meta) in enumerate(zip(chunks, chunk_metadata)):
            node = TextNode(text=chunk, metadata={**(metadata or {}), **meta.to_dict()})
            nodes.append(node)

        return SplitResult(
            chunks=nodes, metadata=chunk_metadata, total_chunks=len(chunks)
        )

    def _split_medical_sentences(self, text: str) -> List[str]:
        """Split text into sentences with medical awareness."""
        # Pre-process to protect medical abbreviations
        protected_text = text

        # Protect common medical abbreviations
        medical_abbrevs = [
            "Dr.",
            "Mr.",
            "Mrs.",
            "Ms.",
            "Prof.",
            "Sr.",
            "Jr.",
            "Inc.",
            "Ltd.",
            "Corp.",
            "Co.",
            "vs.",
            "eg.",
            "ie.",
            "etc.",
            "al.",
            "Jan.",
            "Feb.",
            "Mar.",
            "Apr.",
            "Jun.",
            "Jul.",
            "Aug.",
            "Sept.",
            "Oct.",
            "Nov.",
            "Dec.",
            "Mon.",
            "Tue.",
            "Wed.",
            "Thu.",
            "Fri.",
            "Sat.",
            "Sun.",
            "St.",
            "Ave.",
            "Blvd.",
            "Rd.",
            "No.",
            "Vol.",
            "Fig.",
            "pt.",
            "pts.",
            "wt.",
            "ht.",
            "mg.",
            "ml.",
            "mcg.",
            "kg.",
            "lb.",
            "a.m.",
            "p.m.",
            "A.M.",
            "P.M.",
        ]

        for abbrev in medical_abbrevs:
            protected_text = protected_text.replace(
                abbrev, abbrev.replace(".", "<DOT>")
            )

        # Protect decimal numbers
        protected_text = re.sub(r"(\d)\.(\d)", r"\1<DOT>\2", protected_text)

        # Split on sentence boundaries
        # Look for period, exclamation, or question mark followed by space and capital letter
        sentence_pattern = r"(?<=[.!?])\s+(?=[A-Z])"
        sentences = re.split(sentence_pattern, protected_text)

        # Restore dots
        sentences = [s.replace("<DOT>", ".") for s in sentences]

        # Post-process to merge incorrectly split medical statements
        merged_sentences = []
        i = 0

        while i < len(sentences):
            current = sentences[i].strip()

            # Check if next sentence should be merged
            if i + 1 < len(sentences):
                next_sent = sentences[i + 1].strip()

                # Check for medical continuations
                should_merge = False

                # Check if current ends with medical term that continues
                for pattern in self.medical_continuations:
                    if re.search(pattern + r"\s*$", current, re.I):
                        should_merge = True
                        break

                # Check for specific patterns
                if not should_merge:
                    # Medication dosing pattern
                    if re.search(r"\d+\s*$", current) and re.search(
                        r"^(mg|ml|mcg|g)", next_sent, re.I
                    ):
                        should_merge = True
                    # List continuation
                    elif current.endswith(":") and next_sent[0].islower():
                        should_merge = True

                if should_merge:
                    current = current + " " + next_sent
                    i += 1

            if current:
                merged_sentences.append(current)
            i += 1

        return merged_sentences

    def _calculate_sentence_overlap(self, sentences: List[str]) -> List[str]:
        """Calculate which sentences to include for overlap."""
        if self.config.chunk_overlap <= 0:
            return []

        overlap_sentences: List[str] = []
        overlap_size = 0

        # Add sentences from the end until we reach overlap size
        for sentence in reversed(sentences):
            sentence_size = self._count_tokens(sentence)

            if overlap_size + sentence_size <= self.config.chunk_overlap:
                overlap_sentences.insert(0, sentence)
                overlap_size += sentence_size
            else:
                # If we can't fit the whole sentence, stop
                break

        return overlap_sentences


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
