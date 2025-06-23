"""Similarity search module for medical images."""

import logging
from dataclasses import dataclass
from typing import Any, Dict, List

import numpy as np
from scipy.spatial.distance import cosine

logger = logging.getLogger(__name__)


@dataclass
class SimilarityResult:
    """Result of similarity search."""

    image_id: str
    similarity_score: float
    metadata: Dict[str, Any]


class SimilaritySearchEngine:
    """Search for similar medical images."""

    def __init__(self, index: Dict[str, Any]):
        """Initialize similarity search engine."""
        self.index = index

    def search_similar(
        self, query_features: np.ndarray, top_k: int = 10
    ) -> List[SimilarityResult]:
        """Search for similar images based on features."""
        results = []

        for image_id, entry in self.index.items():
            # Calculate similarity
            similarity = self._calculate_similarity(query_features, entry.features)

            results.append(
                SimilarityResult(
                    image_id=image_id,
                    similarity_score=similarity,
                    metadata=entry.metadata,
                )
            )

        # Sort by similarity and return top k
        results.sort(key=lambda x: x.similarity_score, reverse=True)
        return results[:top_k]

    def _calculate_similarity(
        self, features1: np.ndarray, features2: np.ndarray
    ) -> float:
        """Calculate similarity between two feature vectors."""
        # Use cosine similarity
        return float(1 - cosine(features1, features2))
