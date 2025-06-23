"""
Qdrant Vector Store Implementation.

High-performance vector search for Haven Health Passport.
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
    from llama_index.vector_stores.qdrant import QdrantVectorStore
except ImportError:
    QdrantVectorStore = None

try:
    from qdrant_client import QdrantClient
except ImportError:
    QdrantClient = None

from .base import BaseVectorStoreConfig, BaseVectorStoreFactory


@dataclass
class QdrantConfig(BaseVectorStoreConfig):
    """Configuration for Qdrant vector store."""

    url: str = "http://localhost:6333"
    api_key: Optional[str] = None
    collection_name: str = "haven_health_medical"
    enable_https: bool = False


class QdrantFactory(BaseVectorStoreFactory):
    """Factory for creating Qdrant vector stores."""

    def create(self, config: Optional[BaseVectorStoreConfig] = None) -> VectorStore:
        """Create Qdrant vector store instance."""
        if config is None:
            config = self.get_default_config()

        # Ensure config is QdrantConfig
        if not isinstance(config, QdrantConfig):
            raise ValueError(f"Expected QdrantConfig, got {type(config)}")

        client = QdrantClient(
            url=config.url, api_key=config.api_key, https=config.enable_https
        )

        return QdrantVectorStore(
            client=client,
            collection_name=config.collection_name,
            dimension=config.embedding_dimension,
        )

    def validate_config(self, config: BaseVectorStoreConfig) -> bool:
        """Validate Qdrant configuration."""
        if not isinstance(config, QdrantConfig):
            return False
        return bool(config.url)

    def get_default_config(self) -> QdrantConfig:
        """Get default Qdrant configuration."""
        return QdrantConfig()
