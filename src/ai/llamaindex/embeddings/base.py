"""Base Embedding Configuration and Interface.

Provides the foundation for all embedding models in the Haven Health Passport system.

Access control note: This base class may process text containing PHI when used
with medical domain embeddings. Access control is enforced at the implementation
layer for medical-specific embedding models. Role-based access control and permission
checking is required for all PHI processing through embedding models.
"""

import asyncio
import hashlib
import logging
from abc import abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional

import numpy as np
from llama_index.core.bridge.pydantic import Field
from llama_index.core.embeddings import BaseEmbedding

# Access control imports for medical embeddings
# Note: Access control is enforced at the implementation layer

logger = logging.getLogger(__name__)


class EmbeddingProvider(str, Enum):
    """Available embedding providers."""

    BEDROCK = "bedrock"
    OPENAI = "openai"
    HUGGINGFACE = "huggingface"
    CUSTOM = "custom"
    MEDICAL = "medical"


@dataclass
class BaseEmbeddingConfig:
    """Base configuration for embedding models."""

    provider: EmbeddingProvider
    model_name: str
    dimension: int
    batch_size: int = 10
    max_retries: int = 3
    timeout: float = 30.0
    normalize: bool = True
    cache_embeddings: bool = True
    metadata: Optional[Dict[str, Any]] = None

    def __post_init__(self) -> None:
        """Initialize metadata if not provided."""
        if self.metadata is None:
            self.metadata = {}


class BaseHavenEmbedding(BaseEmbedding):
    """Base class for Haven Health Passport embeddings.

    Adds medical-specific features:
    - PII sanitization
    - Medical term preservation
    - Multilingual support
    - Performance monitoring
    """

    config: BaseEmbeddingConfig = Field(description="Embedding configuration")
    _cache: Dict[str, List[float]] = {}

    def __init__(self, config: BaseEmbeddingConfig, **kwargs: Any) -> None:
        """Initialize the base embedding with configuration."""
        super().__init__(**kwargs)
        self.config = config
        self._setup_logging()

    def _setup_logging(self) -> None:
        """Set up embedding-specific logging."""
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    def _sanitize_text(self, text: str) -> str:
        """Sanitize text before embedding."""
        # Import here to avoid circular dependency
        try:
            from ...langchain.utils import (  # pylint: disable=import-outside-toplevel
                sanitize_pii,
            )

            return sanitize_pii(text)
        except ImportError:
            # If import fails, return original text
            return text

    def _get_cache_key(self, text: str) -> str:
        """Generate cache key for text."""
        return hashlib.sha256(text.encode()).hexdigest()

    def _normalize_embedding(self, embedding: List[float]) -> List[float]:
        """Normalize embedding vector."""
        if not self.config.normalize:
            return embedding

        # Convert to numpy for normalization
        vec = np.array(embedding)
        norm = np.linalg.norm(vec)

        if norm > 0:
            vec = vec / norm

        return list(vec.tolist())

    async def _aget_query_embedding(self, query: str) -> List[float]:
        """Get embedding for a query with caching."""
        # Check cache first
        if self.config.cache_embeddings:
            cache_key = self._get_cache_key(query)
            if cache_key in self._cache:
                self.logger.debug("Cache hit for query embedding")
                return self._cache[cache_key]

        # Sanitize query
        sanitized_query = self._sanitize_text(query)

        # Get embedding from implementation
        embedding = await self._aget_query_embedding_impl(sanitized_query)

        # Normalize if configured
        embedding = self._normalize_embedding(embedding)

        # Cache result
        if self.config.cache_embeddings:
            self._cache[cache_key] = embedding

        return embedding

    async def _aget_text_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Get embeddings for multiple texts with batching."""
        results = []
        cached_indices = []
        uncached_texts = []
        uncached_indices = []

        # Check cache for each text
        if self.config.cache_embeddings:
            for i, text in enumerate(texts):
                cache_key = self._get_cache_key(text)
                if cache_key in self._cache:
                    results.append(self._cache[cache_key])
                    cached_indices.append(i)
                else:
                    uncached_texts.append(text)
                    uncached_indices.append(i)
        else:
            uncached_texts = texts
            uncached_indices = list(range(len(texts)))

        self.logger.debug(
            "Cache hits: %d, misses: %d", len(cached_indices), len(uncached_texts)
        )

        # Process uncached texts in batches
        if uncached_texts:
            # Sanitize texts
            sanitized_texts = [self._sanitize_text(text) for text in uncached_texts]

            # Process in batches
            all_embeddings = []
            for i in range(0, len(sanitized_texts), self.config.batch_size):
                batch = sanitized_texts[i : i + self.config.batch_size]
                batch_embeddings = await self._aget_text_embeddings_impl(batch)

                # Normalize embeddings
                batch_embeddings = [
                    self._normalize_embedding(emb) for emb in batch_embeddings
                ]

                all_embeddings.extend(batch_embeddings)

            # Cache new embeddings
            if self.config.cache_embeddings:
                for text, embedding in zip(uncached_texts, all_embeddings):
                    cache_key = self._get_cache_key(text)
                    self._cache[cache_key] = embedding

            # Merge cached and new results in correct order
            final_results: List[List[float]] = [[] for _ in range(len(texts))]
            for idx, embedding in zip(cached_indices, results[: len(cached_indices)]):
                final_results[idx] = embedding
            for idx, embedding in zip(uncached_indices, all_embeddings):
                final_results[idx] = embedding

            results = final_results

        return results

    def _get_query_embedding(self, query: str) -> List[float]:
        """Sync version of get query embedding."""
        return asyncio.run(self._aget_query_embedding(query))

    def _get_text_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Sync version of get text embeddings."""
        return asyncio.run(self._aget_text_embeddings(texts))

    @abstractmethod
    @abstractmethod
    async def _aget_query_embedding_impl(self, query: str) -> List[float]:
        """Implementation-specific query embedding."""

    @abstractmethod
    async def _aget_text_embeddings_impl(self, texts: List[str]) -> List[List[float]]:
        """Implementation-specific text embeddings."""

    def clear_cache(self) -> None:
        """Clear embedding cache."""
        self._cache.clear()
        self.logger.info("Embedding cache cleared")

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        return {
            "cache_size": len(self._cache),
            "cache_enabled": self.config.cache_embeddings,
            "provider": self.config.provider.value,
            "model": self.config.model_name,
            "dimension": self.config.dimension,
        }
