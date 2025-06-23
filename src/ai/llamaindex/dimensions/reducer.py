"""Dimension Reduction Methods.

Provides various methods to reduce embedding dimensions while
preserving semantic information.
"""

import logging
from enum import Enum
from typing import Any, List, Optional, Union

import numpy as np

logger = logging.getLogger(__name__)


class ReductionMethod(str, Enum):
    """Available dimension reduction methods."""

    TRUNCATION = "truncation"
    PCA = "pca"
    AUTOENCODER = "autoencoder"
    AVERAGE_POOLING = "average_pooling"
    MAX_POOLING = "max_pooling"
    MATRYOSHKA = "matryoshka"  # For compatible models


class DimensionReducer:
    """Reduces embedding dimensions using various methods."""

    @staticmethod
    def reduce_dimension(
        embedding: Union[List[float], np.ndarray],
        target_dimension: int,
        method: ReductionMethod = ReductionMethod.TRUNCATION,
        reduction_model: Optional[Any] = None,
    ) -> List[float]:
        """Reduce embedding dimension.

        Args:
            embedding: Original embedding
            target_dimension: Target dimension size
            method: Reduction method
            reduction_model: Pre-trained reduction model

        Returns:
            Reduced embedding
        """
        # Convert to numpy if needed
        if isinstance(embedding, list):
            embedding = np.array(embedding)
        current_dim = len(embedding)

        if current_dim <= target_dimension:
            logger.warning(
                "Current dimension %d already <= target %d",
                current_dim,
                target_dimension,
            )
            return list(embedding.tolist())

        # Apply reduction method
        if method == ReductionMethod.TRUNCATION:
            reduced = DimensionReducer._truncate(embedding, target_dimension)

        elif method == ReductionMethod.AVERAGE_POOLING:
            reduced = DimensionReducer._average_pool(embedding, target_dimension)

        elif method == ReductionMethod.MAX_POOLING:
            reduced = DimensionReducer._max_pool(embedding, target_dimension)

        elif method == ReductionMethod.PCA:
            reduced = DimensionReducer._pca_reduce(
                embedding, target_dimension, reduction_model
            )

        elif method == ReductionMethod.MATRYOSHKA:
            reduced = DimensionReducer._matryoshka_reduce(embedding, target_dimension)

        else:
            raise ValueError(f"Unknown reduction method: {method}")

        return list(reduced.tolist())

    @staticmethod
    def _truncate(embedding: np.ndarray, target_dim: int) -> np.ndarray:
        """Truncate to target dimension."""
        return embedding[:target_dim]

    @staticmethod
    def _average_pool(embedding: np.ndarray, target_dim: int) -> np.ndarray:
        """Average pooling reduction."""
        current_dim = len(embedding)
        pool_size = current_dim // target_dim

        if current_dim % target_dim != 0:
            # Pad embedding
            pad_size = pool_size * target_dim - current_dim
            embedding = np.pad(embedding, (0, pad_size), mode="constant")

        # Reshape and average
        reshaped = embedding.reshape(target_dim, -1)
        reduced = np.mean(reshaped, axis=1)

        return np.array(reduced)

    @staticmethod
    def _max_pool(embedding: np.ndarray, target_dim: int) -> np.ndarray:
        """Max pooling reduction."""
        current_dim = len(embedding)
        pool_size = current_dim // target_dim

        if current_dim % target_dim != 0:
            # Pad embedding
            pad_size = pool_size * target_dim - current_dim
            embedding = np.pad(embedding, (0, pad_size), mode="constant")

        # Reshape and take max
        reshaped = embedding.reshape(target_dim, -1)
        reduced = np.max(reshaped, axis=1)

        return np.array(reduced)

    @staticmethod
    def _pca_reduce(
        embedding: np.ndarray, target_dim: int, pca_model: Optional[Any] = None
    ) -> np.ndarray:
        """PCA-based reduction (requires pre-trained PCA model)."""
        if pca_model is None:
            logger.warning("PCA reduction requires pre-trained model, using truncation")
            return DimensionReducer._truncate(embedding, target_dim)

        # Apply PCA transformation
        # In production, would use sklearn PCA or similar
        # For now, simulate with random projection
        projection_matrix = np.random.randn(target_dim, len(embedding))
        projection_matrix = projection_matrix / np.linalg.norm(
            projection_matrix, axis=1, keepdims=True
        )

        reduced = projection_matrix @ embedding
        return np.array(reduced)

    @staticmethod
    def _matryoshka_reduce(embedding: np.ndarray, target_dim: int) -> np.ndarray:
        """Matryoshka reduction for compatible models.

        This method assumes the model was trained with Matryoshka representations
        where earlier dimensions contain more important information.
        """
        # For Matryoshka-compatible models, we can simply truncate
        # as the model is trained to pack information hierarchically
        return DimensionReducer._truncate(embedding, target_dim)

    @staticmethod
    def batch_reduce(
        embeddings: List[Union[List[float], np.ndarray]],
        target_dimension: int,
        method: ReductionMethod = ReductionMethod.TRUNCATION,
        reduction_model: Optional[Any] = None,
    ) -> List[List[float]]:
        """Reduce dimensions for batch of embeddings."""
        reduced_embeddings = []

        for embedding in embeddings:
            reduced = DimensionReducer.reduce_dimension(
                embedding, target_dimension, method, reduction_model
            )
            reduced_embeddings.append(reduced)

        return reduced_embeddings


def reduce_embedding_dimension(
    embedding: Union[List[float], np.ndarray],
    target_dimension: int,
    method: str = "truncation",
) -> List[float]:
    """Reduce embedding dimension.

    Args:
        embedding: Original embedding
        target_dimension: Target dimension
        method: Reduction method name

    Returns:
        Reduced embedding
    """
    method_enum = ReductionMethod(method)
    return DimensionReducer.reduce_dimension(embedding, target_dimension, method_enum)
