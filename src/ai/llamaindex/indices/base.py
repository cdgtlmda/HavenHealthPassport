"""Base Classes for Vector Indices.

Provides foundation for all vector index implementations.
"""

import hashlib
import json
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Protocol, Tuple

try:
    from llama_index.core import Document
    from llama_index.core.schema import BaseNode
    from llama_index.core.vector_stores.base import VectorStore
except (ImportError, AttributeError):
    try:
        from llama_index.core.schema import BaseNode, Document
        from llama_index.core.vector_stores import SimpleVectorStore as VectorStore
    except (ImportError, AttributeError):
        # Create placeholder types for when imports fail
        _DocumentType = type("Document", (), {})
        _BaseNodeType = type("BaseNode", (), {})
        _VectorStoreType = type("VectorStore", (), {})
        Document = _DocumentType  # type: ignore[misc,assignment]
        BaseNode = _BaseNodeType  # type: ignore[misc,assignment]
        VectorStore = _VectorStoreType

from ..embeddings import BaseHavenEmbedding
from ..similarity import BaseSimilarityScorer

logger = logging.getLogger(__name__)


class VectorIndexType(str, Enum):
    """Types of vector indices."""

    DENSE = "dense"
    SPARSE = "sparse"
    HYBRID = "hybrid"
    MEDICAL = "medical"
    MULTIMODAL = "multimodal"
    GRAPH = "graph"
    HIERARCHICAL = "hierarchical"


@dataclass
class VectorIndexConfig:
    """Configuration for vector indices."""

    # Basic settings
    index_type: VectorIndexType = VectorIndexType.DENSE
    index_name: str = "haven_medical_index"
    dimension: int = 768

    # Storage settings
    vector_store_type: str = "simple"  # simple, opensearch, pinecone, etc.
    persist_path: Optional[str] = None
    enable_persistence: bool = True

    # Indexing settings
    batch_size: int = 100
    max_docs_per_index: Optional[int] = None
    enable_deduplication: bool = True

    # Search settings
    default_top_k: int = 10
    similarity_threshold: float = 0.7
    enable_reranking: bool = True
    rerank_top_k: int = 20

    # Medical settings
    enable_medical_expansion: bool = True
    enable_multilingual: bool = True
    supported_languages: List[str] = field(
        default_factory=lambda: ["en", "es", "fr", "ar", "zh"]
    )
    medical_ontologies: List[str] = field(
        default_factory=lambda: ["icd10", "snomed", "rxnorm"]
    )

    # Performance settings
    enable_caching: bool = True
    cache_size: int = 1000
    enable_approximate_search: bool = False
    nprobe: int = 10  # For approximate search

    # Monitoring
    enable_metrics: bool = True
    enable_query_logging: bool = True
    slow_query_threshold_ms: int = 1000

    # Advanced settings
    enable_auto_optimization: bool = True
    optimization_schedule: str = "daily"  # daily, weekly, on_demand
    enable_compression: bool = False
    compression_ratio: float = 0.5


@dataclass
class IndexMetrics:
    """Metrics for monitoring index performance."""

    total_documents: int = 0
    total_queries: int = 0
    average_query_time_ms: float = 0.0
    cache_hit_rate: float = 0.0
    index_size_mb: float = 0.0
    last_optimization: Optional[datetime] = None
    error_count: int = 0
    slow_query_count: int = 0

    def update_query_metrics(self, query_time_ms: float, cache_hit: bool) -> None:
        """Update metrics after a query."""
        self.total_queries += 1

        # Update average query time
        self.average_query_time_ms = (
            self.average_query_time_ms * (self.total_queries - 1) + query_time_ms
        ) / self.total_queries

        # Update cache hit rate
        if cache_hit:
            cache_hits = self.cache_hit_rate * (self.total_queries - 1)
            self.cache_hit_rate = (cache_hits + 1) / self.total_queries


class BaseVectorIndex(ABC):
    """Abstract base class for vector indices.

    Provides common functionality for all index types.
    """

    def __init__(
        self,
        config: Optional[VectorIndexConfig] = None,
        embedding_model: Optional[BaseHavenEmbedding] = None,
        similarity_scorer: Optional[BaseSimilarityScorer] = None,
        vector_store: Optional[VectorStore] = None,
    ):
        """Initialize vector index."""
        self.config = config or VectorIndexConfig()
        self.embedding_model = embedding_model
        self.similarity_scorer = similarity_scorer
        self.vector_store = vector_store

        # Initialize components
        self._index: Optional[Any] = None
        self._retriever: Optional[Any] = None
        self._cache: Optional[Dict[str, List[Tuple[Document, float]]]] = (
            {} if self.config.enable_caching else None
        )
        self._metrics = IndexMetrics()

        # Setup logging
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

        # Initialize index
        self._initialize()

    def _initialize(self) -> None:
        """Initialize index components."""
        self.logger.info(
            "Initializing %s index: %s", self.config.index_type, self.config.index_name
        )

    @abstractmethod
    def build_index(self, documents: List[Document]) -> None:
        """Build index from documents."""

    @abstractmethod
    def add_documents(self, documents: List[Document]) -> List[str]:
        """Add documents to existing index."""

    @abstractmethod
    def delete_documents(self, doc_ids: List[str]) -> bool:
        """Delete documents from index."""

    @abstractmethod
    def search(
        self,
        query: str,
        top_k: Optional[int] = None,
        filters: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> List[Tuple[Document, float]]:
        """Search the index."""

    def batch_search(
        self,
        queries: List[str],
        top_k: Optional[int] = None,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[List[Tuple[Document, float]]]:
        """Batch search multiple queries."""
        results = []
        for query in queries:
            result = self.search(query, top_k, filters)
            results.append(result)
        return results

    def update_document(self, doc_id: str, document: Document) -> bool:
        """Update a document in the index."""
        # Default implementation: delete and re-add
        if self.delete_documents([doc_id]):
            doc_ids = self.add_documents([document])
            return len(doc_ids) > 0
        return False

    def clear_cache(self) -> None:
        """Clear the query cache."""
        if self._cache is not None:
            self._cache.clear()
            self.logger.info("Query cache cleared")

    def get_metrics(self) -> IndexMetrics:
        """Get current index metrics."""
        return self._metrics

    def optimize(self) -> bool:
        """Optimize the index for better performance."""
        self.logger.info("Starting index optimization...")
        start_time = time.time()

        try:
            # Clear cache
            self.clear_cache()

            # Index-specific optimization
            success = self._optimize_index()

            if success:
                self._metrics.last_optimization = datetime.now()
                elapsed_time = time.time() - start_time
                self.logger.info("Index optimization completed in %.2fs", elapsed_time)

            return success

        except OSError as e:
            self.logger.error("Index optimization failed: %s", e)
            return False

    @abstractmethod
    def _optimize_index(self) -> bool:
        """Index-specific optimization logic."""

    def persist(self, path: Optional[str] = None) -> bool:
        """Persist index to disk."""
        if not self.config.enable_persistence:
            return False

        persist_path = path or self.config.persist_path
        if not persist_path:
            self.logger.warning("No persist path specified")
            return False

        try:
            return self._persist_index(persist_path)
        except OSError as e:
            self.logger.error("Failed to persist index: %s", e)
            return False

    @abstractmethod
    def _persist_index(self, path: str) -> bool:
        """Index-specific persistence logic."""

    def load(self, path: Optional[str] = None) -> bool:
        """Load index from disk."""
        load_path = path or self.config.persist_path
        if not load_path:
            self.logger.warning("No load path specified")
            return False

        try:
            return self._load_index(load_path)
        except OSError as e:
            self.logger.error("Failed to load index: %s", e)
            return False

    @abstractmethod
    def _load_index(self, path: str) -> bool:
        """Index-specific loading logic."""

    def _create_cache_key(
        self, query: str, top_k: int, filters: Optional[Dict[str, Any]]
    ) -> str:
        """Create cache key for query."""
        cache_data = {"query": query, "top_k": top_k, "filters": filters or {}}
        cache_str = json.dumps(cache_data, sort_keys=True)
        return hashlib.sha256(cache_str.encode()).hexdigest()

    def _check_cache(self, cache_key: str) -> Optional[List[Tuple[Document, float]]]:
        """Check cache for query results."""
        if self._cache is None:
            return None

        if cache_key in self._cache:
            self.logger.debug("Cache hit for query")
            cached_result = self._cache[cache_key]
            return cached_result

        return None

    def _update_cache(
        self, cache_key: str, results: List[Tuple[Document, float]]
    ) -> None:
        """Update cache with query results."""
        if self._cache is None:
            return

        # Limit cache size
        if len(self._cache) >= self.config.cache_size:
            # Remove oldest entry (simple FIFO)
            first_key = next(iter(self._cache))
            del self._cache[first_key]

        self._cache[cache_key] = results

    def _apply_filters(
        self, nodes: List[BaseNode], filters: Dict[str, Any]
    ) -> List[BaseNode]:
        """Apply metadata filters to nodes."""
        if not filters:
            return nodes

        filtered_nodes = []
        for node in nodes:
            match = True
            for key, value in filters.items():
                if key not in node.metadata:
                    match = False
                    break

                node_value = node.metadata[key]
                if isinstance(value, list):
                    # Value in list
                    if node_value not in value:
                        match = False
                        break
                elif isinstance(value, dict):
                    # Range query
                    if "gte" in value and node_value < value["gte"]:
                        match = False
                        break
                    if "lte" in value and node_value > value["lte"]:
                        match = False
                        break
                else:
                    # Exact match
                    if node_value != value:
                        match = False
                        break

            if match:
                filtered_nodes.append(node)

        return filtered_nodes


class IndexProtocol(Protocol):
    """Protocol defining vector index interface."""

    def search(
        self, query: str, top_k: Optional[int] = None, **kwargs: Any
    ) -> List[Tuple[Document, float]]:
        """Search the index."""

    def add_documents(self, documents: List[Document]) -> List[str]:
        """Add documents to index."""

    def delete_documents(self, doc_ids: List[str]) -> bool:
        """Delete documents from index."""
