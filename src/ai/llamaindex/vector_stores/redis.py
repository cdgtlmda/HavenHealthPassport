"""
Redis Vector Store Implementation.

In-memory vector operations for Haven Health Passport.
"""

from dataclasses import dataclass
from typing import Optional

try:
    from llama_index.core.vector_stores import VectorStore  # type: ignore[attr-defined]
except ImportError:
    try:
        from llama_index.vector_stores import VectorStore
    except ImportError:
        VectorStore = None

try:
    from llama_index.vector_stores.redis import RedisVectorStore
except ImportError:
    RedisVectorStore = None

from .base import BaseVectorStoreConfig, BaseVectorStoreFactory


@dataclass
class RedisConfig(BaseVectorStoreConfig):
    """Configuration for Redis vector store."""

    redis_url: str = "redis://localhost:6379"
    index_name: str = "haven_health_idx"
    index_prefix: str = "doc"
    index_args: Optional[dict] = None


class RedisFactory(BaseVectorStoreFactory):
    """Factory for creating Redis vector stores."""

    def create(self, config: Optional[BaseVectorStoreConfig] = None) -> VectorStore:
        """Create Redis vector store instance."""
        if config is None:
            config = self.get_default_config()

        # Ensure config is RedisConfig
        if not isinstance(config, RedisConfig):
            raise ValueError(f"Expected RedisConfig, got {type(config)}")

        return RedisVectorStore(
            redis_url=config.redis_url,
            index_name=config.index_name,
            index_prefix=config.index_prefix,
            index_args=config.index_args
            or {
                "algorithm": "HNSW",
                "m": 16,
                "ef_construction": 200,
                "distance_metric": "COSINE",
            },
        )

    def validate_config(self, config: BaseVectorStoreConfig) -> bool:
        """Validate Redis configuration."""
        if isinstance(config, RedisConfig):
            return bool(config.redis_url)
        return False

    def get_default_config(self) -> RedisConfig:
        """Get default Redis configuration."""
        return RedisConfig()
