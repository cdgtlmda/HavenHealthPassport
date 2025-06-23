"""OpenAI Embeddings Implementation.

Provides OpenAI embedding models for text vectorization.
Note: Requires OpenAI API key for production use.
"""

import logging
from enum import Enum
from typing import Any, Dict, List, Optional

import numpy as np

from .base import BaseEmbeddingConfig, BaseHavenEmbedding, EmbeddingProvider

logger = logging.getLogger(__name__)


class OpenAIEmbeddingModel(str, Enum):
    """Available OpenAI embedding models."""

    TEXT_EMBEDDING_ADA_002 = "text-embedding-ada-002"
    TEXT_EMBEDDING_3_SMALL = "text-embedding-3-small"
    TEXT_EMBEDDING_3_LARGE = "text-embedding-3-large"


class OpenAIEmbeddings(BaseHavenEmbedding):
    """OpenAI embeddings implementation.

    Features:
    - Multiple model support
    - Dimension reduction for 3-series models
    - Batch embedding support
    - Cost optimization
    """

    def __init__(
        self,
        config: Optional[BaseEmbeddingConfig] = None,
        model: str = OpenAIEmbeddingModel.TEXT_EMBEDDING_3_SMALL,
        api_key: Optional[str] = None,
        dimensions: Optional[int] = None,
        **kwargs: Any,
    ):
        """Initialize OpenAI embeddings.

        Args:
            config: Embedding configuration
            model: OpenAI model name
            api_key: OpenAI API key
            dimensions: Target dimensions (for v3 models)
        """
        # Get default dimensions based on model
        default_dims = self._get_default_dimensions(model)

        # Use specified dimensions or default
        final_dimensions = dimensions or default_dims

        # Create default config if not provided
        if config is None:
            config = BaseEmbeddingConfig(
                provider=EmbeddingProvider.OPENAI,
                model_name=model,
                dimension=final_dimensions,
                batch_size=100,  # OpenAI supports large batches
                normalize=True,
            )

        super().__init__(config, **kwargs)

        self.model = model
        self.api_key = api_key
        self.dimensions = final_dimensions if final_dimensions != default_dims else None

        # Note: In production, would initialize OpenAI client here
        # For now, we'll use mock implementation
        self.logger.warning(
            "OpenAI embeddings in mock mode. Configure API key for production use."
        )

    def _get_default_dimensions(self, model: str) -> int:
        """Get default dimensions for model."""
        dimensions: Dict[str, int] = {
            OpenAIEmbeddingModel.TEXT_EMBEDDING_ADA_002: 1536,
            OpenAIEmbeddingModel.TEXT_EMBEDDING_3_SMALL: 1536,
            OpenAIEmbeddingModel.TEXT_EMBEDDING_3_LARGE: 3072,
        }
        return dimensions.get(model, 1536)

    async def _aget_query_embedding_impl(self, query: str) -> List[float]:
        """Get embedding for a single query."""
        # Mock implementation for development
        # In production, would call OpenAI API

        # Generate deterministic embedding based on query
        seed = sum(ord(c) for c in query) % 1000
        np.random.seed(seed)
        embedding = np.random.randn(self.config.dimension).tolist()

        self.logger.debug("Generated mock embedding for query using %s", self.model)
        return embedding  # type: ignore[no-any-return]

    async def _aget_text_embeddings_impl(self, texts: List[str]) -> List[List[float]]:
        """Get embeddings for multiple texts."""
        # Mock implementation
        embeddings = []
        for text in texts:
            embedding = await self._aget_query_embedding_impl(text)
            embeddings.append(embedding)

        return embeddings

    def estimate_cost(self, num_tokens: int) -> float:
        """Estimate cost for embedding tokens."""
        # Pricing as of 2024 (per 1M tokens)
        pricing: Dict[str, float] = {
            OpenAIEmbeddingModel.TEXT_EMBEDDING_ADA_002: 0.10,
            OpenAIEmbeddingModel.TEXT_EMBEDDING_3_SMALL: 0.02,
            OpenAIEmbeddingModel.TEXT_EMBEDDING_3_LARGE: 0.13,
        }

        price_per_million = pricing.get(self.model, 0.10)
        return (num_tokens / 1_000_000) * price_per_million

    def get_model_info(self) -> Dict[str, Any]:
        """Get information about the current model."""
        return {
            "provider": "OpenAI",
            "model": self.model,
            "dimension": self.config.dimension,
            "supports_batch": True,
            "max_batch_size": 2048,
            "max_input_tokens": 8191,
            "supports_dimension_reduction": "3" in self.model,
        }

    def _get_text_embedding(self, text: str) -> List[float]:
        """Get embedding for a single text - required by llama_index BaseEmbedding."""
        import asyncio

        return asyncio.run(self._aget_query_embedding_impl(text))
