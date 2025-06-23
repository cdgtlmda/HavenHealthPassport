"""Vector Store Module - Base classes and interfaces.

This module provides vector storage capabilities for medical embeddings,
translation memory, and semantic search functionality.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import numpy as np


@dataclass
class VectorSearchResult:
    """Result from a vector search operation."""

    id: str
    score: float
    vector: np.ndarray
    metadata: Dict[str, Any]
    timestamp: datetime


class BaseEmbeddingService(ABC):
    """Abstract base class for embedding services."""

    @abstractmethod
    def embed(self, text: str) -> np.ndarray:
        """Generate embedding for input text.

        Args:
            text: Text to embed

        Returns:
            Embedding vector
        """

    @abstractmethod
    def embed_batch(self, texts: List[str]) -> List[np.ndarray]:
        """Generate embeddings for multiple texts.

        Args:
            texts: List of texts to embed

        Returns:
            List of embedding vectors
        """

    @abstractmethod
    def get_dimension(self) -> int:
        """Get the dimension of embeddings produced.

        Returns:
            Embedding dimension
        """


class BaseVectorStore(ABC):
    """Abstract base class for vector storage implementations."""

    @abstractmethod
    def add(
        self,
        vector_id: str,
        vector: np.ndarray,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Add a vector to the store.

        Args:
            vector_id: Unique identifier for the vector
            vector: The vector to store
            metadata: Optional metadata to associate with the vector

        Returns:
            Success status
        """

    @abstractmethod
    def add_batch(
        self, items: List[Tuple[str, np.ndarray, Optional[Dict[str, Any]]]]
    ) -> List[bool]:
        """Add multiple vectors to the store.

        Args:
            items: List of (id, vector, metadata) tuples

        Returns:
            List of success statuses
        """

    @abstractmethod
    def search(
        self,
        query_vector: np.ndarray,
        k: int = 10,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[VectorSearchResult]:
        """Search for similar vectors.

        Args:
            query_vector: Query vector
            k: Number of results to return
            filters: Optional metadata filters

        Returns:
            List of search results
        """

    @abstractmethod
    def get(self, vector_id: str) -> Optional[VectorSearchResult]:
        """Get a vector by ID.

        Args:
            vector_id: Vector ID
        Returns:
            Vector result or None if not found
        """

    @abstractmethod
    def delete(self, vector_id: str) -> bool:
        """Delete a vector by ID.

        Args:
            vector_id: Vector ID

        Returns:
            Success status
        """

    @abstractmethod
    def update_metadata(self, vector_id: str, metadata: Dict[str, Any]) -> bool:
        """Update metadata for a vector.

        Args:
            vector_id: Vector ID
            metadata: New metadata

        Returns:
            Success status
        """
