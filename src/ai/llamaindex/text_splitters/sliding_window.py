"""
Sliding Window Text Splitter.

Splits text using a sliding window approach with configurable
overlap for maximum context preservation.
"""

import logging
from typing import Any, Dict, List, Optional

from llama_index.core.schema import TextNode

from .base import BaseMedicalSplitter, SplitResult, TextSplitterConfig

logger = logging.getLogger(__name__)


class SlidingWindowSplitter(BaseMedicalSplitter):
    """Splits text using sliding window with overlap."""

    def __init__(self, config: Optional[TextSplitterConfig] = None):
        """Initialize the sliding window text splitter."""
        super().__init__(config)

        # Ensure we have overlap for sliding window
        if self.config.chunk_overlap == 0:
            self.config.chunk_overlap = int(self.config.chunk_size * 0.2)  # 20% overlap

    def split(
        self, text: str, metadata: Optional[Dict[str, Any]] = None
    ) -> SplitResult:
        """Split text using sliding window."""
        # Tokenize if using tokenizer, otherwise use characters
        if self.config.use_tokenizer and self.tokenizer:
            tokens = self.tokenizer.encode(text)
            is_token_based = True
        else:
            tokens = list(text)  # Character-based
            is_token_based = False

        if not tokens:
            return SplitResult(chunks=[], metadata=[], total_chunks=0)

        chunks: List[TextNode] = []
        chunk_metadata = []

        # Calculate window parameters
        window_size = self.config.chunk_size
        step_size = window_size - self.config.chunk_overlap

        # Ensure step size is positive
        if step_size <= 0:
            step_size = max(1, window_size // 2)

        # Slide window through text
        start = 0
        while start < len(tokens):
            end = min(start + window_size, len(tokens))

            # Extract chunk
            if is_token_based:
                chunk_tokens = tokens[start:end]
                chunk_text = self.tokenizer.decode(chunk_tokens)
            else:
                chunk_text = "".join(tokens[start:end])

            # Clean chunk boundaries
            chunk_text = self._clean_chunk_boundaries(chunk_text)

            if chunk_text.strip():
                # Create metadata
                char_start = (
                    start
                    if not is_token_based
                    else self._get_char_position(text, start, tokens)
                )
                char_end = (
                    end
                    if not is_token_based
                    else self._get_char_position(text, end, tokens)
                )

                meta = self._create_chunk_metadata(
                    chunk_text,
                    len(chunks),
                    -1,  # Will update later
                    char_start,
                    char_end,
                )

                # Add window-specific metadata
                meta.custom_metadata = {
                    "window_start": start,
                    "window_end": end,
                    "window_size": end - start,
                    "overlap_size": self.config.chunk_overlap if start > 0 else 0,
                }

                # Create TextNode with chunk text and metadata
                node = TextNode(text=chunk_text, metadata=meta.to_dict())
                chunks.append(node)
                chunk_metadata.append(meta)

            # Move to next window
            start += step_size

            # If we're near the end, make sure we capture everything
            if start < len(tokens) and start + window_size >= len(tokens):
                # This will be the last chunk
                start = max(start, len(tokens) - window_size)

        # Update total chunks and relationships
        for i, meta in enumerate(chunk_metadata):
            meta.total_chunks = len(chunks)
            if i > 0:
                meta.previous_chunk_id = f"chunk_{i-1}"
            if i < len(chunks) - 1:
                meta.next_chunk_id = f"chunk_{i+1}"

        # Create TextNodes
        nodes = []
        for i, (chunk, meta) in enumerate(zip(chunks, chunk_metadata)):
            node = TextNode(
                text=chunk,
                id_=f"chunk_{i}",
                metadata={**(metadata or {}), **meta.to_dict()},
            )
            nodes.append(node)

        return SplitResult(
            chunks=nodes, metadata=chunk_metadata, total_chunks=len(chunks)
        )

    def _clean_chunk_boundaries(self, chunk: str) -> str:
        """Clean up chunk boundaries to avoid breaking words or sentences."""
        chunk = chunk.strip()

        if not chunk:
            return chunk

        # If using sentence-aware cleaning
        if self.config.ensure_complete_sentences:
            # Find the last complete sentence
            sentences = self._split_sentences(chunk)
            if sentences:
                # Check if last sentence is complete
                if not chunk.rstrip().endswith((".", "!", "?")):
                    # Remove incomplete last sentence
                    if len(sentences) > 1:
                        complete_sentences = sentences[:-1]
                        chunk = " ".join(complete_sentences)

        # Clean up word boundaries
        if not chunk[-1].isspace() and not chunk[-1] in ".,!?;:":
            # Find last space to avoid breaking words
            last_space = chunk.rfind(" ")
            if last_space > len(chunk) * 0.8:  # Don't trim too much
                chunk = chunk[:last_space]

        # Clean up beginning
        if not chunk[0].isupper() and chunk[0] not in "0123456789":
            # Find first capital letter or number
            for i, char in enumerate(chunk):
                if char.isupper() or char.isdigit():
                    chunk = chunk[i:]
                    break

        return chunk.strip()

    def _get_char_position(
        self, text: str, token_position: int, tokens: List[int]
    ) -> int:
        """Convert token position to character position."""
        if token_position == 0:
            return 0

        if token_position >= len(tokens):
            return len(text)

        # Decode tokens up to position to get character count
        partial_tokens = tokens[:token_position]
        partial_text = self.tokenizer.decode(partial_tokens)

        return len(partial_text)
