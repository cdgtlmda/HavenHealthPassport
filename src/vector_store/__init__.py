"""Vector Store Module for Haven Health Passport.

This module provides vector storage and similarity search capabilities
for medical embeddings, translation memory, and document retrieval.
"""

from .base import BaseEmbeddingService, BaseVectorStore, VectorSearchResult
from .config import VectorStoreConfig
from .embedding_store import EmbeddingStore
from .medical_embeddings import MedicalEmbeddingService

__all__ = [
    "BaseEmbeddingService",
    "BaseVectorStore",
    "VectorSearchResult",
    "MedicalEmbeddingService",
    "EmbeddingStore",
    "VectorStoreConfig",
]

__version__ = "1.0.0"
