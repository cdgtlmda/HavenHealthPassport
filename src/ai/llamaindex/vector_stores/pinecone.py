"""
Pinecone Vector Store Implementation.

Managed vector database option for Haven Health Passport.
"""

import os
from dataclasses import dataclass
from typing import Optional

try:
    import pinecone
except ImportError:
    pinecone = None

try:
    from llama_index.core.vector_stores import VectorStore  # type: ignore[attr-defined]
except ImportError:
    try:
        from llama_index.vector_stores import VectorStore
    except ImportError:
        VectorStore = None

try:
    from llama_index.vector_stores.pinecone import PineconeVectorStore
except ImportError:
    PineconeVectorStore = None

from .base import BaseVectorStoreConfig, BaseVectorStoreFactory


@dataclass
class PineconeConfig(BaseVectorStoreConfig):
    """Configuration for Pinecone vector store."""

    api_key: str = ""
    environment: str = "us-east-1-aws"
    index_name: str = "haven-health-medical"
    namespace: str = "medical-docs"
    metric: str = "cosine"
    pod_type: str = "p1.x1"
    replicas: int = 1


class PineconeFactory(BaseVectorStoreFactory):
    """Factory for creating Pinecone vector stores."""

    def create(self, config: Optional[BaseVectorStoreConfig] = None) -> VectorStore:
        """Create Pinecone vector store instance."""
        if pinecone is None:
            raise ImportError("pinecone-client is required for Pinecone vector store")
        if PineconeVectorStore is None:
            raise ImportError("llama-index pinecone integration is required")

        if config is None:
            config = self.get_default_config()

        # Ensure config is PineconeConfig
        if not isinstance(config, PineconeConfig):
            raise ValueError(f"Expected PineconeConfig, got {type(config)}")

        # Initialize Pinecone
        pinecone.init(
            api_key=config.api_key or os.getenv("PINECONE_API_KEY"),
            environment=config.environment,
        )

        # Create index if it doesn't exist
        if config.index_name not in pinecone.list_indexes():
            pinecone.create_index(
                config.index_name,
                dimension=config.embedding_dimension,
                metric=config.metric,
                pod_type=config.pod_type,
                replicas=config.replicas,
            )

        # Get index
        pinecone_index = pinecone.Index(config.index_name)

        # Create vector store
        return PineconeVectorStore(
            pinecone_index=pinecone_index, namespace=config.namespace
        )

    def validate_config(self, config: BaseVectorStoreConfig) -> bool:
        """Validate Pinecone configuration."""
        if not isinstance(config, PineconeConfig):
            return False
        return bool(config.api_key or os.getenv("PINECONE_API_KEY"))

    def get_default_config(self) -> PineconeConfig:
        """Get default Pinecone configuration."""
        return PineconeConfig()
