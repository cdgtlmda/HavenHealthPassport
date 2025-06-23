"""Embedding Store implementation for vector storage."""

import json
from datetime import datetime
from json import JSONDecodeError
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from src.utils.logging import get_logger

from .base import BaseVectorStore, VectorSearchResult

logger = get_logger(__name__)


class EmbeddingStore(BaseVectorStore):
    """In-memory embedding store with persistence support."""

    def __init__(self, persist_path: Optional[Path] = None):
        """Initialize the embedding store.

        Args:
            persist_path: Optional path for persistence
        """
        self.persist_path = persist_path
        self._vectors: Dict[str, np.ndarray] = {}
        self._metadata: Dict[str, Dict[str, Any]] = {}
        self._timestamps: Dict[str, datetime] = {}

        # Load from disk if persist path exists
        if self.persist_path and self.persist_path.exists():
            self._load_from_disk()

    def add(
        self,
        vector_id: str,
        vector: np.ndarray,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Add a vector to the store.

        Args:
            vector_id: Unique identifier
            vector: Embedding vector
            metadata: Optional metadata

        Returns:
            Success status
        """
        try:
            self._vectors[vector_id] = vector.copy()
            self._metadata[vector_id] = metadata or {}
            self._timestamps[vector_id] = datetime.now()

            # Persist if enabled
            if self.persist_path:
                self._save_to_disk()

            logger.debug(f"Added vector {vector_id} to store")
            return True

        except (TypeError, ValueError) as e:
            # Catch all exceptions to prevent crashes during vector operations
            logger.error(f"Failed to add vector {vector_id}: {e}")
            return False

    def add_batch(
        self, items: List[Tuple[str, np.ndarray, Optional[Dict[str, Any]]]]
    ) -> List[bool]:
        """Add multiple vectors to the store.

        Args:
            items: List of (id, vector, metadata) tuples

        Returns:
            List of success statuses
        """
        results = []

        for vector_id, vector, metadata in items:
            success = self.add(vector_id, vector, metadata)
            results.append(success)

        return results

    def search(
        self,
        query_vector: np.ndarray,
        k: int = 10,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[VectorSearchResult]:
        """Search for similar vectors using cosine similarity.

        Args:
            query_vector: Query embedding
            k: Number of results
            filters: Optional metadata filters

        Returns:
            Sorted search results
        """
        results = []

        # Normalize query vector
        query_norm = query_vector / np.linalg.norm(query_vector)
        # Calculate similarities
        for vector_id, vector in self._vectors.items():
            # Apply filters if provided
            if filters:
                metadata = self._metadata.get(vector_id, {})
                if not self._matches_filters(metadata, filters):
                    continue

            # Calculate cosine similarity
            vector_norm = vector / np.linalg.norm(vector)
            similarity = np.dot(query_norm, vector_norm)

            result = VectorSearchResult(
                id=vector_id,
                score=float(similarity),
                vector=vector,
                metadata=self._metadata.get(vector_id, {}),
                timestamp=self._timestamps.get(vector_id, datetime.now()),
            )
            results.append(result)

        # Sort by score descending and limit to k
        results.sort(key=lambda x: x.score, reverse=True)
        return results[:k]

    def _matches_filters(
        self, metadata: Dict[str, Any], filters: Dict[str, Any]
    ) -> bool:
        """Check if metadata matches filters.

        Args:
            metadata: Vector metadata
            filters: Filter criteria

        Returns:
            True if matches all filters
        """
        for key, value in filters.items():
            if key not in metadata:
                return False
            if metadata[key] != value:
                return False
        return True

    def get(self, vector_id: str) -> Optional[VectorSearchResult]:
        """Get a vector by ID.

        Args:
            vector_id: Vector ID

        Returns:
            Vector result or None
        """
        if vector_id not in self._vectors:
            return None

        return VectorSearchResult(
            id=vector_id,
            score=1.0,
            vector=self._vectors[vector_id],
            metadata=self._metadata.get(vector_id, {}),
            timestamp=self._timestamps.get(vector_id, datetime.now()),
        )

    def delete(self, vector_id: str) -> bool:
        """Delete a vector by ID.

        Args:
            vector_id: Vector ID

        Returns:
            Success status
        """
        if vector_id not in self._vectors:
            return False

        del self._vectors[vector_id]
        self._metadata.pop(vector_id, None)
        self._timestamps.pop(vector_id, None)

        # Persist if enabled
        if self.persist_path:
            self._save_to_disk()

        return True

    def update_metadata(self, vector_id: str, metadata: Dict[str, Any]) -> bool:
        """Update metadata for a vector.

        Args:
            vector_id: Vector ID
            metadata: New metadata

        Returns:
            Success status
        """
        if vector_id not in self._vectors:
            return False

        self._metadata[vector_id] = metadata
        self._timestamps[vector_id] = datetime.now()

        # Persist if enabled
        if self.persist_path:
            self._save_to_disk()

        return True

    def _save_to_disk(self) -> None:
        """Save store to disk."""
        if not self.persist_path:
            return

        try:
            data = {
                "vectors": {k: v.tolist() for k, v in self._vectors.items()},
                "metadata": self._metadata,
                "timestamps": {k: v.isoformat() for k, v in self._timestamps.items()},
            }

            with open(self.persist_path, "w", encoding="utf-8") as f:
                json.dump(data, f)

            logger.debug(f"Saved {len(self._vectors)} vectors to disk")

        except (OSError, TypeError, ValueError) as e:
            # Catch all exceptions to prevent crashes during persistence operations
            logger.error(f"Failed to save to disk: {e}")

    def _load_from_disk(self) -> None:
        """Load store from disk."""
        if not self.persist_path:
            return

        try:
            with open(self.persist_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            self._vectors = {k: np.array(v) for k, v in data["vectors"].items()}
            self._metadata = data["metadata"]
            self._timestamps = {
                k: datetime.fromisoformat(v) for k, v in data["timestamps"].items()
            }

            logger.info(f"Loaded {len(self._vectors)} vectors from disk")

        except (
            JSONDecodeError,
            OSError,
            TypeError,
            ValueError,
        ) as e:
            # Catch all exceptions to prevent crashes during persistence operations
            logger.error(f"Failed to load from disk: {e}")

    def size(self) -> int:
        """Get the number of vectors in the store."""
        return len(self._vectors)
