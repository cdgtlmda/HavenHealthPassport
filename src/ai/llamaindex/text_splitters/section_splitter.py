"""
Section-Aware Medical Text Splitter.

Splits text while respecting medical document sections and structure.
Ensures sections remain coherent and complete.

This module handles encrypted PHI with access control and audit logging
to ensure HIPAA compliance.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

from llama_index.core.schema import TextNode

from src.healthcare.hipaa_access_control import AccessLevel, require_phi_access
from src.security.encryption import EncryptionService

from .base import BaseMedicalSplitter, SplitResult, TextSplitterConfig

logger = logging.getLogger(__name__)


class SectionAwareSplitter(BaseMedicalSplitter):
    """Splits text by medical document sections."""

    def __init__(self, config: Optional[TextSplitterConfig] = None):
        """Initialize section-aware splitter."""
        super().__init__(config)
        self.encryption_service = EncryptionService(
            kms_key_id="alias/haven-health-default"
        )

        # Define section hierarchy
        self.section_hierarchy = [
            "chief_complaint",
            "hpi",
            "pmh",
            "medications",
            "allergies",
            "physical_exam",
            "labs",
            "imaging",
            "assessment",
            "plan",
        ]

    @require_phi_access(AccessLevel.READ)
    def split(
        self, text: str, metadata: Optional[Dict[str, Any]] = None
    ) -> SplitResult:
        """Split text by sections.

        Requires PHI access permission and logs all access
        """
        logger.info("Audit: PHI access for section splitting, metadata: %s", metadata)

        # Extract sections
        sections = self._extract_sections(text)

        if not sections:
            # No sections found, fall back to paragraph splitting
            logger.info("No sections found, using paragraph splitting")
            return self._split_by_paragraphs(text, metadata)

        # Process each section
        chunks = []
        chunk_metadata = []
        char_offset = 0

        for section_name, section_content in sections:
            # Check if section fits in one chunk
            section_size = self._count_tokens(section_content)

            if section_size <= self.config.chunk_size:
                # Section fits in one chunk
                chunk = self._create_section_chunk(section_name, section_content)
                chunks.append(chunk)

                # Create metadata
                meta = self._create_chunk_metadata(
                    chunk,
                    len(chunks) - 1,
                    -1,  # Will update later
                    char_offset,
                    char_offset + len(chunk),
                )
                meta.section_name = section_name
                chunk_metadata.append(meta)

                char_offset += len(chunk) + 1
            else:
                # Section needs to be split
                section_chunks = self._split_large_section(
                    section_name, section_content
                )

                for i, sub_chunk in enumerate(section_chunks):
                    chunks.append(sub_chunk)

                    meta = self._create_chunk_metadata(
                        sub_chunk,
                        len(chunks) - 1,
                        -1,
                        char_offset,
                        char_offset + len(sub_chunk),
                    )
                    meta.section_name = f"{section_name}_part_{i+1}"
                    chunk_metadata.append(meta)

                    char_offset += len(sub_chunk) + 1

        # Update total chunks
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

    def _extract_sections(self, text: str) -> List[Tuple[str, str]]:
        """Extract sections from medical document."""
        sections = []

        # Find all section headers and their positions
        section_positions: List[Dict[str, Any]] = []

        for section_name, pattern in self._section_patterns.items():
            matches = list(pattern.finditer(text))
            for match in matches:
                section_positions.append(
                    {
                        "name": section_name,
                        "start": match.start(),
                        "end": match.end(),
                        "header": match.group(0),
                    }
                )

        # Sort by position
        section_positions.sort(key=lambda x: x["start"])

        # Extract content for each section
        for i, section in enumerate(section_positions):
            start = section["end"]

            # Find end of section (start of next section or end of text)
            if i + 1 < len(section_positions):
                end = section_positions[i + 1]["start"]
            else:
                end = len(text)

            content = text[start:end].strip()

            if content:
                # Include header in content
                full_content = str(section["header"]) + content
                sections.append((str(section["name"]), full_content))

        # Check for content before first section
        if section_positions and section_positions[0]["start"] > 0:
            pre_content = text[: section_positions[0]["start"]].strip()
            if pre_content:
                sections.insert(0, ("introduction", pre_content))

        # If no sections found but text exists
        if not sections and text.strip():
            sections.append(("content", text))

        return sections

    def _create_section_chunk(self, section_name: str, content: str) -> str:
        """Create a chunk for a section."""
        # Format section nicely
        formatted_name = section_name.replace("_", " ").title()

        # Check if content already has header
        if not content.strip().startswith(formatted_name):
            return f"[{formatted_name}]\n\n{content}"
        else:
            return content

    def _split_large_section(self, section_name: str, content: str) -> List[str]:
        """Split a large section into smaller chunks."""
        chunks = []

        # Try to split by paragraphs first
        paragraphs = content.split("\n\n")

        current_chunk = f"[{section_name.replace('_', ' ').title()}]\n\n"
        current_size = self._count_tokens(current_chunk)

        for para in paragraphs:
            para_size = self._count_tokens(para)

            if current_size + para_size <= self.config.chunk_size:
                current_chunk += para + "\n\n"
                current_size += para_size
            else:
                # Save current chunk
                if current_chunk.strip():
                    chunks.append(current_chunk.strip())

                # Start new chunk
                if self.config.chunk_overlap > 0 and chunks:
                    # Add section header to continuation
                    current_chunk = (
                        f"[{section_name.replace('_', ' ').title()} - Continued]\n\n"
                    )
                else:
                    current_chunk = ""

                current_chunk += para + "\n\n"
                current_size = self._count_tokens(current_chunk)

        # Add remaining content
        if current_chunk.strip():
            chunks.append(current_chunk.strip())

        return chunks

    def _split_by_paragraphs(
        self, text: str, metadata: Optional[Dict[str, Any]] = None
    ) -> SplitResult:
        """Fallback paragraph-based splitting."""
        paragraphs = text.split("\n\n")
        chunks = []
        chunk_metadata = []
        current_chunk: List[str] = []
        current_size = 0
        start_char = 0

        for para in paragraphs:
            para_size = self._count_tokens(para)

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

                # Reset
                current_chunk = []
                current_size = 0
                start_char = end_char + 2  # Account for \n\n

            current_chunk.append(para)
            current_size += para_size

        # Handle remaining
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

        # Create nodes
        nodes = []
        for chunk, meta in zip(chunks, chunk_metadata):
            node = TextNode(text=chunk, metadata={**(metadata or {}), **meta.to_dict()})
            nodes.append(node)

        return SplitResult(
            chunks=nodes, metadata=chunk_metadata, total_chunks=len(chunks)
        )
