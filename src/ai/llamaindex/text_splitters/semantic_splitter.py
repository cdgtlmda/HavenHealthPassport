"""
Semantic Medical Text Splitter.

Splits text based on semantic similarity to maintain coherent chunks.
Uses embeddings to ensure related medical concepts stay together.
"""

import logging
from typing import Any, Dict, List, Optional

import numpy as np
from llama_index.core.schema import TextNode
from sentence_transformers import SentenceTransformer

from .base import BaseMedicalSplitter, ChunkMetadata, SplitResult, TextSplitterConfig

logger = logging.getLogger(__name__)


class SemanticMedicalSplitter(BaseMedicalSplitter):
    """Splits text based on semantic similarity."""

    def __init__(self, config: Optional[TextSplitterConfig] = None):
        """Initialize the semantic text splitter."""
        super().__init__(config)

        # Load embedding model
        # Using a medical-optimized model if available
        self.embed_model = SentenceTransformer("all-MiniLM-L6-v2")

        # Semantic threshold for splitting
        self.semantic_threshold = config.semantic_coherence_threshold if config else 0.7

    def split(
        self, text: str, metadata: Optional[Dict[str, Any]] = None
    ) -> SplitResult:
        """Split text based on semantic similarity."""
        # Split into sentences first
        sentences = self._split_sentences(text)

        if not sentences:
            return SplitResult(chunks=[], metadata=[], total_chunks=0)

        # Get embeddings for all sentences
        embeddings = self.embed_model.encode(sentences)

        # Group sentences by semantic similarity
        chunks = []
        chunk_metadata = []
        current_group = [0]  # Start with first sentence
        current_size = self._count_tokens(sentences[0])

        for i in range(1, len(sentences)):
            # Calculate similarity with current group
            group_embedding = np.mean([embeddings[j] for j in current_group], axis=0)
            similarity = self._cosine_similarity(embeddings[i], group_embedding)

            sentence_size = self._count_tokens(sentences[i])

            # Decide whether to add to current group or start new one
            if (
                similarity >= self.semantic_threshold
                and current_size + sentence_size <= self.config.chunk_size
            ):
                # Add to current group
                current_group.append(i)
                current_size += sentence_size
            else:
                # Create chunk from current group
                chunk_text = " ".join([sentences[j] for j in current_group])
                chunks.append(chunk_text)

                # Create metadata
                start_idx = current_group[0]
                end_idx = current_group[-1]
                meta = self._create_semantic_metadata(
                    chunk_text, len(chunks) - 1, sentences[start_idx : end_idx + 1]
                )
                chunk_metadata.append(meta)

                # Start new group with overlap if configured
                if self.config.chunk_overlap > 0:
                    # Include semantically similar sentences from previous chunk
                    overlap_indices = self._calculate_semantic_overlap(
                        current_group, embeddings, sentences
                    )
                    current_group = overlap_indices + [i]
                    current_size = sum(
                        self._count_tokens(sentences[j]) for j in current_group
                    )
                else:
                    current_group = [i]
                    current_size = sentence_size

        # Handle remaining sentences
        if current_group:
            chunk_text = " ".join([sentences[j] for j in current_group])
            chunks.append(chunk_text)

            start_idx = current_group[0]
            end_idx = current_group[-1]
            meta = self._create_semantic_metadata(
                chunk_text, len(chunks) - 1, sentences[start_idx : end_idx + 1]
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

    def _cosine_similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        """Calculate cosine similarity between two vectors."""
        dot_product = np.dot(vec1, vec2)
        norm_product = np.linalg.norm(vec1) * np.linalg.norm(vec2)

        if norm_product == 0:
            return 0.0

        return float(dot_product / norm_product)

    def _calculate_semantic_overlap(
        self, group_indices: List[int], embeddings: np.ndarray, sentences: List[str]
    ) -> List[int]:
        """Calculate which sentences to include for semantic overlap."""
        if self.config.chunk_overlap <= 0:
            return []

        # Get embedding for the group
        group_embedding = np.mean([embeddings[i] for i in group_indices], axis=0)

        # Calculate similarities for all sentences in the group
        similarities = []
        for i in reversed(group_indices):
            sim = self._cosine_similarity(embeddings[i], group_embedding)
            similarities.append((i, sim))

        # Sort by similarity (highest first)
        similarities.sort(key=lambda x: x[1], reverse=True)

        # Select sentences for overlap based on similarity and size
        overlap_indices = []
        overlap_size = 0

        for idx, _sim in similarities:
            sentence_size = self._count_tokens(sentences[idx])

            if overlap_size + sentence_size <= self.config.chunk_overlap:
                overlap_indices.append(idx)
                overlap_size += sentence_size
            else:
                break

        # Return in original order
        return sorted(overlap_indices)

    def _create_semantic_metadata(
        self, chunk_text: str, chunk_index: int, sentences: List[str]
    ) -> ChunkMetadata:
        """Create metadata with semantic information."""
        # Get base metadata
        meta = self._create_chunk_metadata(
            chunk_text,
            chunk_index,
            -1,  # Will be updated
            0,  # Will be updated
            len(chunk_text),
        )

        # Calculate semantic coherence score
        if len(sentences) > 1:
            embeddings = self.embed_model.encode(sentences)

            # Calculate average pairwise similarity
            similarities = []
            for i, emb1 in enumerate(embeddings):
                for j in range(i + 1, len(embeddings)):
                    sim = self._cosine_similarity(emb1, embeddings[j])
                    similarities.append(sim)

            meta.coherence_score = float(np.mean(similarities)) if similarities else 1.0
        else:
            meta.coherence_score = 1.0

        return meta
