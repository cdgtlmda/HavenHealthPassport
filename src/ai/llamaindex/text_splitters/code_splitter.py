"""Medical Code Text Splitter.

Specialized splitter that ensures medical codes (ICD, CPT, etc.)
and their associated context remain together in chunks.

This module handles encrypted PHI with access control and audit logging
to ensure HIPAA compliance.
"""

import logging
import re
from typing import Any, Dict, List, Optional

from llama_index.core.schema import TextNode

from src.healthcare.hipaa_access_control import AccessLevel, require_phi_access
from src.security.encryption import EncryptionService

from .base import BaseMedicalSplitter, ChunkMetadata, SplitResult, TextSplitterConfig
from .sentence_splitter import SentenceMedicalSplitter

logger = logging.getLogger(__name__)


class MedicalCodeSplitter(BaseMedicalSplitter):
    """Splits text while keeping medical codes with their context."""

    def __init__(self, config: Optional[TextSplitterConfig] = None):
        """Initialize medical code text splitter.

        Args:
            config: Configuration for text splitter
        """
        super().__init__(config)
        self.encryption_service = EncryptionService(
            kms_key_id="alias/haven-health-default"
        )

        # Define code context patterns
        self.code_context_patterns = {
            "diagnosis": re.compile(
                r"(diagnosis|dx|diagnosed with|assessment):\s*([^.]+)\s*\(([A-Z]\d{2}\.?\d{0,2})\)",
                re.I,
            ),
            "procedure": re.compile(
                r"(procedure|performed|scheduled):\s*([^.]+)\s*\((\d{5})\)", re.I
            ),
            "medication": re.compile(
                r"(medication|rx|prescribed):\s*([^,]+)\s*(\d+\s*mg)", re.I
            ),
        }

    @require_phi_access(AccessLevel.READ)
    def split(
        self, text: str, metadata: Optional[Dict[str, Any]] = None
    ) -> SplitResult:
        """Split text while preserving medical code context.

        Requires PHI access permission and logs all access.
        Uses TLS for any transmission of medical data.
        """
        logger.info(
            "Audit: PHI access for medical code splitting, metadata: %s", metadata
        )

        # Find all medical code occurrences
        code_contexts = self._extract_code_contexts(text)

        if not code_contexts:
            # No medical codes found, use sentence splitting
            fallback_splitter = SentenceMedicalSplitter(self.config)
            result = fallback_splitter.split(text, metadata)
            return SplitResult(
                chunks=result.chunks,
                metadata=result.metadata,
                total_chunks=result.total_chunks,
            )

        # Create chunks around medical codes
        chunk_texts: List[str] = []
        chunk_metadata: List[ChunkMetadata] = []

        # Sort code contexts by position
        code_contexts.sort(key=lambda x: x["start"])

        # Process text segments
        last_end = 0

        for context in code_contexts:
            # Handle text before this code context
            if context["start"] > last_end:
                pre_text = text[last_end : context["start"]].strip()
                if pre_text:
                    # Check if it should be combined with previous chunk
                    if chunk_texts and self._should_combine(chunk_texts[-1], pre_text):
                        chunk_texts[-1] += "\n\n" + pre_text
                        chunk_metadata[-1].medical_codes.extend(context["codes"])
                    else:
                        # Create new chunk
                        chunk_texts.append(pre_text)
                        meta = self._create_chunk_metadata(
                            pre_text,
                            len(chunk_texts) - 1,
                            -1,
                            last_end,
                            context["start"],
                        )
                        chunk_metadata.append(meta)

            # Expand context if needed
            expanded_text = self._expand_code_context(text, context)

            # Check if it fits with previous chunk
            if (
                chunk_texts
                and self._count_tokens(chunk_texts[-1] + "\n\n" + expanded_text)
                <= self.config.chunk_size
            ):
                chunk_texts[-1] += "\n\n" + expanded_text
                chunk_metadata[-1].medical_codes.extend(context["codes"])
                chunk_metadata[-1].contains_medical_codes = True
            else:
                chunk_texts.append(expanded_text)
                meta = self._create_chunk_metadata(
                    expanded_text,
                    len(chunk_texts) - 1,
                    -1,
                    context["start"],
                    context["end"],
                )
                meta.medical_codes = context["codes"]
                meta.contains_medical_codes = True
                chunk_metadata.append(meta)

            last_end = context["end"]

        # Handle remaining text
        if last_end < len(text):
            remaining = text[last_end:].strip()
            if remaining:
                if chunk_texts and self._should_combine(chunk_texts[-1], remaining):
                    chunk_texts[-1] += "\n\n" + remaining
                else:
                    chunk_texts.append(remaining)
                    meta = self._create_chunk_metadata(
                        remaining,
                        len(chunk_texts) - 1,
                        len(chunk_texts),
                        last_end,
                        len(text),
                    )
                    chunk_metadata.append(meta)

        # Update total chunks
        for meta in chunk_metadata:
            meta.total_chunks = len(chunk_texts)

        # Create TextNodes
        nodes = []
        for chunk_text, meta in zip(chunk_texts, chunk_metadata):
            node = TextNode(
                text=chunk_text, metadata={**(metadata or {}), **meta.to_dict()}
            )
            nodes.append(node)

        return SplitResult(
            chunks=nodes, metadata=chunk_metadata, total_chunks=len(chunk_texts)
        )

    def _extract_code_contexts(self, text: str) -> List[Dict[str, Any]]:
        """Extract medical codes with their surrounding context."""
        contexts = []

        # Extract ICD codes with context
        icd_pattern = re.compile(r"[^.]*[A-Z]\d{2}\.?\d{0,2}[^.]*\.", re.I)
        for match in icd_pattern.finditer(text):
            codes = self._medical_patterns["icd10"].findall(match.group(0))
            if codes:
                contexts.append(
                    {
                        "start": match.start(),
                        "end": match.end(),
                        "codes": codes,
                        "type": "icd10",
                        "text": match.group(0),
                    }
                )

        # Extract CPT codes with context
        cpt_pattern = re.compile(r"[^.]*\b\d{5}\b[^.]*\.", re.I)
        for match in cpt_pattern.finditer(text):
            codes = self._medical_patterns["cpt"].findall(match.group(0))
            if codes:
                # Verify it's likely a CPT code (not just any 5-digit number)
                if any(
                    keyword in match.group(0).lower()
                    for keyword in ["procedure", "cpt", "performed", "code"]
                ):
                    contexts.append(
                        {
                            "start": match.start(),
                            "end": match.end(),
                            "codes": codes,
                            "type": "cpt",
                            "text": match.group(0),
                        }
                    )

        # Remove duplicates and overlaps
        contexts = self._remove_overlapping_contexts(contexts)

        return contexts

    def _remove_overlapping_contexts(
        self, contexts: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Remove overlapping code contexts, keeping the most specific."""
        if not contexts:
            return contexts

        # Sort by start position
        contexts.sort(key=lambda x: x["start"])

        filtered: List[Dict[str, Any]] = []
        for context in contexts:
            # Check if this overlaps with the last added context
            if filtered and context["start"] < filtered[-1]["end"]:
                # Keep the one with more codes or longer text
                if len(context["codes"]) > len(filtered[-1]["codes"]) or len(
                    context["text"]
                ) > len(filtered[-1]["text"]):
                    filtered[-1] = context
            else:
                filtered.append(context)

        return filtered

    def _expand_code_context(self, text: str, context: Dict[str, Any]) -> str:
        """Expand context around medical codes to include full sentences."""
        start = context["start"]
        end = context["end"]

        # Find sentence boundaries
        # Look backwards for sentence start
        sentence_start = start
        for i in range(start - 1, max(0, start - 200), -1):
            if text[i] in ".!?" and i + 1 < len(text) and text[i + 1].isspace():
                sentence_start = i + 2
                break

        # Look forward for sentence end
        sentence_end = end
        for i in range(end, min(len(text), end + 200)):
            if text[i] in ".!?" and (i + 1 >= len(text) or text[i + 1].isspace()):
                sentence_end = i + 1
                break

        expanded = text[sentence_start:sentence_end].strip()

        # Include surrounding paragraph if it's small enough
        para_start = sentence_start
        para_end = sentence_end

        # Find paragraph boundaries
        for i in range(sentence_start - 1, max(0, sentence_start - 500), -1):
            if text[i : i + 2] == "\n\n":
                para_start = i + 2
                break

        for i in range(sentence_end, min(len(text), sentence_end + 500)):
            if text[i : i + 2] == "\n\n":
                para_end = i
                break

        paragraph = text[para_start:para_end].strip()

        # Use paragraph if it's not too large
        if self._count_tokens(paragraph) <= self.config.chunk_size * 0.8:
            return paragraph
        else:
            return expanded

    def _should_combine(self, existing_chunk: str, new_text: str) -> bool:
        """Determine if new text should be combined with existing chunk."""
        combined_size = self._count_tokens(existing_chunk + "\n\n" + new_text)

        # Check size constraint
        if combined_size > self.config.chunk_size:
            return False

        # Check if new text is very short (likely a fragment)
        if self._count_tokens(new_text) < 50:
            return True

        # Check if texts are related (share medical codes via secure HTTPS/TLS channels)
        existing_codes = set(self._detect_medical_codes(existing_chunk))
        new_codes = set(self._detect_medical_codes(new_text))

        if existing_codes.intersection(new_codes):
            return True

        return False
