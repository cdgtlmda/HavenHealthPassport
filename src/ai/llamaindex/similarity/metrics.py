"""Similarity Metrics Implementation.

Provides various similarity metrics for vector comparison.
"""

import logging
from typing import Any, Dict, List, Optional, Union

import numpy as np
from scipy.spatial.distance import cityblock, cosine, euclidean

from .base import BaseSimilarityScorer, SimilarityConfig, SimilarityMetric

logger = logging.getLogger(__name__)


class CosineSimilarity(BaseSimilarityScorer):
    """Cosine similarity scorer.

    Most commonly used for embedding similarity.
    Range: [-1, 1], where 1 is identical.
    """

    def __init__(self, config: Optional[SimilarityConfig] = None):
        """Initialize the cosine similarity scorer."""
        if config is None:
            config = SimilarityConfig(metric=SimilarityMetric.COSINE)
        super().__init__(config)

    def _initialize(self) -> None:
        """Initialize scorer-specific components."""

    def score(
        self,
        query_embedding: Union[List[float], np.ndarray],
        doc_embedding: Union[List[float], np.ndarray],
        query_metadata: Optional[Dict[str, Any]] = None,
        doc_metadata: Optional[Dict[str, Any]] = None,
    ) -> float:
        """Calculate cosine similarity."""
        # Convert to numpy
        query_vec = self._convert_to_numpy(query_embedding)
        doc_vec = self._convert_to_numpy(doc_embedding)

        # Calculate cosine similarity
        # scipy.spatial.distance.cosine returns distance, so we need 1 - distance
        similarity = 1 - cosine(query_vec, doc_vec)

        # Handle NaN (can occur with zero vectors)
        if np.isnan(similarity):
            similarity = 0.0

        # Apply metadata boost
        similarity = self._apply_metadata_boost(
            similarity, query_metadata, doc_metadata
        )

        # Normalize to [0, 1] range
        normalized = (
            (similarity + 1) / 2 if self.config.normalize_scores else similarity
        )

        # Apply threshold
        return self._apply_threshold(normalized)


class EuclideanDistance(BaseSimilarityScorer):
    """Euclidean distance scorer.

    Measures straight-line distance between vectors.
    Converted to similarity score.
    """

    def __init__(self, config: Optional[SimilarityConfig] = None):
        """Initialize the Euclidean distance scorer."""
        if config is None:
            config = SimilarityConfig(metric=SimilarityMetric.EUCLIDEAN)
        super().__init__(config)

    def _initialize(self) -> None:
        """Initialize scorer-specific components."""

    def score(
        self,
        query_embedding: Union[List[float], np.ndarray],
        doc_embedding: Union[List[float], np.ndarray],
        query_metadata: Optional[Dict[str, Any]] = None,
        doc_metadata: Optional[Dict[str, Any]] = None,
    ) -> float:
        """Calculate Euclidean distance-based similarity."""
        query_vec = self._convert_to_numpy(query_embedding)
        doc_vec = self._convert_to_numpy(doc_embedding)

        # Calculate Euclidean distance
        distance = euclidean(query_vec, doc_vec)

        # Convert distance to similarity
        # Using exponential decay: similarity = exp(-distance)
        similarity = np.exp(-distance)

        # Apply metadata boost
        similarity = self._apply_metadata_boost(
            similarity, query_metadata, doc_metadata
        )

        # Already in [0, 1] range due to exponential
        if not self.config.normalize_scores:
            # Convert back to distance-like score
            similarity = -np.log(similarity) if similarity > 0 else float("inf")

        return self._apply_threshold(similarity)


class DotProductSimilarity(BaseSimilarityScorer):
    """Dot product similarity scorer.

    Simple inner product of vectors.
    """

    def __init__(self, config: Optional[SimilarityConfig] = None):
        """Initialize the dot product similarity scorer."""
        if config is None:
            config = SimilarityConfig(metric=SimilarityMetric.DOT_PRODUCT)
        super().__init__(config)

    def _initialize(self) -> None:
        """Initialize scorer-specific components."""

    def score(
        self,
        query_embedding: Union[List[float], np.ndarray],
        doc_embedding: Union[List[float], np.ndarray],
        query_metadata: Optional[Dict[str, Any]] = None,
        doc_metadata: Optional[Dict[str, Any]] = None,
    ) -> float:
        """Calculate dot product similarity."""
        query_vec = self._convert_to_numpy(query_embedding)
        doc_vec = self._convert_to_numpy(doc_embedding)

        # Calculate dot product
        similarity = np.dot(query_vec, doc_vec)

        # Apply metadata boost
        similarity = self._apply_metadata_boost(
            similarity, query_metadata, doc_metadata
        )

        # Normalize if requested
        if self.config.normalize_scores:
            # Normalize by vector magnitudes
            query_norm = np.linalg.norm(query_vec)
            doc_norm = np.linalg.norm(doc_vec)
            if query_norm > 0 and doc_norm > 0:
                similarity = similarity / (query_norm * doc_norm)
                similarity = (similarity + 1) / 2  # Map to [0, 1]
            else:
                similarity = 0.0

        return self._apply_threshold(similarity)


class ManhattanDistance(BaseSimilarityScorer):
    """Manhattan distance scorer.

    Also known as L1 distance or city block distance.
    """

    def __init__(self, config: Optional[SimilarityConfig] = None):
        """Initialize the Manhattan distance scorer."""
        if config is None:
            config = SimilarityConfig(metric=SimilarityMetric.MANHATTAN)
        super().__init__(config)

    def _initialize(self) -> None:
        """Initialize scorer-specific components."""

    def score(
        self,
        query_embedding: Union[List[float], np.ndarray],
        doc_embedding: Union[List[float], np.ndarray],
        query_metadata: Optional[Dict[str, Any]] = None,
        doc_metadata: Optional[Dict[str, Any]] = None,
    ) -> float:
        """Calculate Manhattan distance-based similarity."""
        query_vec = self._convert_to_numpy(query_embedding)
        doc_vec = self._convert_to_numpy(doc_embedding)

        # Calculate Manhattan distance
        distance = cityblock(query_vec, doc_vec)

        # Convert distance to similarity
        # Using inverse distance with offset
        similarity = 1 / (1 + distance)

        # Apply metadata boost
        similarity = self._apply_metadata_boost(
            similarity, query_metadata, doc_metadata
        )

        # Already in [0, 1] range
        if not self.config.normalize_scores:
            # Convert back to distance
            similarity = (1 / similarity) - 1 if similarity > 0 else float("inf")

        return self._apply_threshold(similarity)


class JaccardSimilarity(BaseSimilarityScorer):
    """Jaccard similarity scorer.

    Useful for sparse vectors or binary features.
    """

    def __init__(self, config: Optional[SimilarityConfig] = None):
        """Initialize the Jaccard similarity scorer."""
        if config is None:
            config = SimilarityConfig(metric=SimilarityMetric.JACCARD)
        super().__init__(config)

    def _initialize(self) -> None:
        """Initialize scorer-specific components."""

    def score(
        self,
        query_embedding: Union[List[float], np.ndarray],
        doc_embedding: Union[List[float], np.ndarray],
        query_metadata: Optional[Dict[str, Any]] = None,
        doc_metadata: Optional[Dict[str, Any]] = None,
    ) -> float:
        """Calculate Jaccard similarity."""
        query_vec = self._convert_to_numpy(query_embedding)
        doc_vec = self._convert_to_numpy(doc_embedding)

        # For continuous vectors, use threshold to create binary vectors
        threshold = 0.5
        query_binary = query_vec > threshold
        doc_binary = doc_vec > threshold

        # Calculate Jaccard similarity
        intersection = np.sum(query_binary & doc_binary)
        union = np.sum(query_binary | doc_binary)

        if union == 0:
            similarity = 0.0
        else:
            similarity = intersection / union

        # Apply metadata boost
        similarity = self._apply_metadata_boost(
            similarity, query_metadata, doc_metadata
        )

        # Already in [0, 1] range
        return self._apply_threshold(similarity)
