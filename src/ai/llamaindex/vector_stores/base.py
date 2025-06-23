"""Base Classes for Vector Store Integration.

Provides abstract base classes and common functionality
for all vector store implementations.

Security Note: This module processes PHI data. All vector data must be:
- Subject to role-based access control (RBAC) for PHI protection
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Protocol

try:
    from llama_index.core import StorageContext, VectorStoreIndex
    from llama_index.core.schema import BaseNode
    from llama_index.core.vector_stores import VectorStore  # type: ignore[attr-defined]
except ImportError:
    try:
        from llama_index import (  # type: ignore[attr-defined,no-redef]
            StorageContext,
            VectorStoreIndex,
        )
        from llama_index.schema import BaseNode  # type: ignore[no-redef]
        from llama_index.vector_stores import VectorStore
    except ImportError:
        StorageContext = None  # type: ignore[assignment,misc]
        VectorStoreIndex = None  # type: ignore[assignment,misc]
        BaseNode = None  # type: ignore[assignment,misc]
        VectorStore = None
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class IndexingMode(str, Enum):
    """Vector indexing modes."""

    BATCH = "batch"  # Process documents in batches
    STREAMING = "streaming"  # Stream documents one by one
    HYBRID = "hybrid"  # Combine vector and keyword search


class SimilarityMetric(str, Enum):
    """Similarity metrics for vector search."""

    COSINE = "cosine"
    EUCLIDEAN = "euclidean"
    DOT_PRODUCT = "dot_product"


@dataclass
class BaseVectorStoreConfig:
    """Base configuration for vector stores."""

    # Basic settings
    collection_name: str = "haven_health_medical_docs"
    embedding_dimension: int = 1536  # Default for OpenAI embeddings

    # Indexing settings
    indexing_mode: IndexingMode = IndexingMode.BATCH
    batch_size: int = 100

    # Search settings
    similarity_metric: SimilarityMetric = SimilarityMetric.COSINE
    top_k: int = 10

    # Medical-specific settings
    enable_phi_filtering: bool = True  # Filter PHI from vectors
    enable_medical_synonyms: bool = True  # Expand medical terms
    enable_cross_lingual: bool = True  # Support multi-language search

    # Performance settings
    enable_caching: bool = True
    cache_ttl_seconds: int = 3600  # 1 hour
    max_connections: int = 10
    connection_timeout: int = 30

    # Security settings
    enable_encryption: bool = True
    enable_audit_logging: bool = True

    # Additional metadata
    metadata: Dict[str, Any] = field(default_factory=dict)


class VectorStoreProtocol(Protocol):
    """Protocol defining vector store interface."""

    def add(self, nodes: List[BaseNode], **kwargs: Any) -> List[str]:
        """Add nodes to the vector store."""

    def delete(self, ref_doc_id: str, **kwargs: Any) -> None:
        """Delete nodes by document ID."""

    def query(self, query: Any, **kwargs: Any) -> Any:
        """Query the vector store."""


class BaseVectorStoreFactory(ABC):
    """Abstract factory for creating vector stores."""

    @abstractmethod
    def create(self, config: Optional[BaseVectorStoreConfig] = None) -> VectorStore:
        """Create and configure a vector store instance."""

    @abstractmethod
    def validate_config(self, config: BaseVectorStoreConfig) -> bool:
        """Validate the configuration."""

    @abstractmethod
    def get_default_config(self) -> BaseVectorStoreConfig:
        """Get default configuration for this vector store."""

    def create_with_index(
        self, documents: List[Any], config: Optional[BaseVectorStoreConfig] = None
    ) -> VectorStoreIndex:
        """Create vector store and build index from documents."""
        vector_store = self.create(config)
        storage_context = StorageContext.from_defaults(vector_store=vector_store)

        index = VectorStoreIndex.from_documents(
            documents, storage_context=storage_context, show_progress=True
        )

        return index

    def _apply_medical_filters(
        self, nodes: List[BaseNode], config: Optional[BaseVectorStoreConfig] = None
    ) -> List[BaseNode]:
        """Apply medical-specific filters to nodes."""
        filtered_nodes = []

        for node in nodes:
            # Apply PHI filtering if enabled
            if (
                config is not None
                and hasattr(config, "enable_phi_filtering")
                and config.enable_phi_filtering
            ):
                # This would integrate with PHI detection service
                node = self._filter_phi(node)

            filtered_nodes.append(node)

        return filtered_nodes

    def _filter_phi(self, node: BaseNode) -> BaseNode:
        """Filter Protected Health Information from node."""
        # Placeholder for PHI filtering logic
        # Would integrate with healthcare standards module
        return node

    def _expand_medical_terms(self, query: str) -> str:
        """Expand medical terms with synonyms."""
        # Placeholder for medical synonym expansion
        # Would integrate with medical NLP module
        return query


class MedicalMetadata(BaseModel):
    """Medical-specific metadata for documents."""

    document_type: str = Field(..., description="Type of medical document")
    specialty: Optional[str] = Field(None, description="Medical specialty")
    icd_codes: List[str] = Field(default_factory=list, description="ICD-10 codes")
    language: str = Field("en", description="Document language")
    patient_id: Optional[str] = Field(None, description="Anonymized patient ID")
    date_created: Optional[str] = Field(None, description="Creation date")
    is_encrypted: bool = Field(False, description="Whether content is encrypted")
    compliance_level: str = Field("hipaa", description="Compliance standard")
