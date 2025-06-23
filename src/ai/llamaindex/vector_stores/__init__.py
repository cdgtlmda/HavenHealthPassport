"""Vector Store Integrations for LlamaIndex.

This module provides HIPAA-compliant vector store implementations
for medical document indexing and retrieval.

Supported Vector Stores:
- OpenSearch (Primary - AWS managed)
- Pinecone (Managed cloud option)
- Qdrant (High-performance option)
- Chroma (Local development)
- PostgreSQL + pgvector (Hybrid storage)
- FAISS (Efficient similarity search)
- Redis (Caching and simple operations)
"""

import logging
from typing import Dict, Optional, Type

from llama_index.core import VectorStoreIndex

try:
    from llama_index.core.vector_stores.base import VectorStore
except (ImportError, AttributeError):
    # Fallback if VectorStore is not available in expected location
    try:
        from llama_index.core.vector_stores import SimpleVectorStore as VectorStore
    except (ImportError, AttributeError):
        # Final fallback - define a placeholder
        from typing import Any

        VectorStore = Any

from .base import BaseVectorStoreConfig, BaseVectorStoreFactory
from .chroma import ChromaConfig, ChromaFactory
from .faiss import FAISSConfig, FAISSFactory
from .opensearch import OpenSearchConfig, OpenSearchFactory
from .pinecone import PineconeConfig, PineconeFactory
from .postgres import PostgresConfig, PostgresFactory
from .qdrant import QdrantConfig, QdrantFactory
from .redis import RedisConfig, RedisFactory

logger = logging.getLogger(__name__)

# Registry of available vector stores
VECTOR_STORE_REGISTRY: Dict[str, Type[BaseVectorStoreFactory]] = {
    "opensearch": OpenSearchFactory,
    "pinecone": PineconeFactory,
    "qdrant": QdrantFactory,
    "chroma": ChromaFactory,
    "postgres": PostgresFactory,
    "faiss": FAISSFactory,
    "redis": RedisFactory,
}

__all__ = [
    "BaseVectorStoreConfig",
    "BaseVectorStoreFactory",
    "OpenSearchConfig",
    "OpenSearchFactory",
    "PineconeConfig",
    "PineconeFactory",
    "QdrantConfig",
    "QdrantFactory",
    "ChromaConfig",
    "ChromaFactory",
    "PostgresConfig",
    "PostgresFactory",
    "FAISSConfig",
    "FAISSFactory",
    "RedisConfig",
    "RedisFactory",
    "VECTOR_STORE_REGISTRY",
    "create_vector_store",
    "get_available_stores",
]


def create_vector_store(
    store_type: str, config: Optional[BaseVectorStoreConfig] = None
) -> VectorStore:
    """
    Create a vector store instance.

    Args:
        store_type: Type of vector store (e.g., 'opensearch', 'pinecone')
        config: Configuration for the vector store

    Returns:
        Vector store instance

    Raises:
        ValueError: If store_type is not supported
    """
    if store_type not in VECTOR_STORE_REGISTRY:
        raise ValueError(
            f"Unknown vector store type: {store_type}. "
            f"Available types: {list(VECTOR_STORE_REGISTRY.keys())}"
        )

    factory_class = VECTOR_STORE_REGISTRY[store_type]
    factory = factory_class()

    logger.info("Creating vector store of type: %s", store_type)
    return factory.create(config)


def get_available_stores() -> Dict[str, str]:
    """Get list of available vector stores with descriptions."""
    return {
        "opensearch": "AWS OpenSearch - Managed search and analytics",
        "pinecone": "Pinecone - Managed vector database",
        "qdrant": "Qdrant - High-performance vector search",
        "chroma": "Chroma - Embedded vector database",
        "postgres": "PostgreSQL + pgvector - Hybrid SQL/vector storage",
        "faiss": "FAISS - Efficient similarity search",
        "redis": "Redis - In-memory vector operations",
    }
