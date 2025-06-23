"""
Base Classes for Retrieval Pipelines.

Provides foundation for all retrieval pipeline implementations.
"""

import asyncio
import hashlib
import json
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from llama_index.core import Document

logger = logging.getLogger(__name__)


class PipelineStage(str, Enum):
    """Stages in the retrieval pipeline."""

    QUERY_PROCESSING = "query_processing"
    QUERY_EXPANSION = "query_expansion"
    RETRIEVAL = "retrieval"
    FILTERING = "filtering"
    RERANKING = "reranking"
    POST_PROCESSING = "post_processing"
    AGGREGATION = "aggregation"


@dataclass
class QueryContext:
    """Context information for a query."""

    query: str
    original_query: str
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    language: str = "en"
    metadata: Dict[str, Any] = field(default_factory=dict)

    # Medical context
    urgency_level: int = 1  # 1-5, 5 being most urgent
    medical_specialty: Optional[str] = None
    patient_context: Optional[Dict[str, Any]] = None

    # Search parameters
    top_k: int = 10
    filters: Dict[str, Any] = field(default_factory=dict)
    boost_recent: bool = True
    include_explanations: bool = False

    # Processing flags
    expand_query: bool = True
    use_synonyms: bool = True
    use_medical_terms: bool = True
    cross_lingual: bool = False


@dataclass
class RetrievalResult:
    """Result from retrieval pipeline."""

    document: Document
    score: float
    rank: int

    # Stage scores
    retrieval_score: float = 0.0
    rerank_score: float = 0.0
    final_score: float = 0.0

    # Explanations
    explanations: Dict[str, Any] = field(default_factory=dict)
    matched_terms: List[str] = field(default_factory=list)

    # Metadata
    source_index: Optional[str] = None
    retrieval_time_ms: float = 0.0
    pipeline_stages: List[str] = field(default_factory=list)


@dataclass
class RetrievalConfig:
    """Configuration for retrieval pipeline."""

    # Pipeline settings
    pipeline_name: str = "default_pipeline"
    enable_caching: bool = True
    cache_ttl_seconds: int = 3600

    # Query processing
    enable_query_expansion: bool = True
    enable_spell_correction: bool = True
    enable_synonym_expansion: bool = True
    max_query_terms: int = 50

    # Retrieval settings
    retrieval_top_k: int = 50  # Get more for reranking
    final_top_k: int = 10
    min_score_threshold: float = 0.0

    # Reranking
    enable_reranking: bool = True
    rerank_model: Optional[str] = None
    rerank_top_k: int = 20

    # Filtering
    enable_filtering: bool = True
    filter_duplicates: bool = True
    filter_language: bool = True

    # Performance
    timeout_seconds: float = 30.0
    max_concurrent_retrievals: int = 3
    batch_size: int = 100

    # Monitoring
    enable_metrics: bool = True
    enable_logging: bool = True
    log_slow_queries: bool = True
    slow_query_threshold_ms: float = 1000.0


class RetrievalPipeline(ABC):
    """
    Abstract base class for retrieval pipelines.

    Provides common functionality for all pipeline implementations.
    """

    def __init__(
        self,
        config: Optional[RetrievalConfig] = None,
        indices: Optional[Dict[str, Any]] = None,
    ):
        """Initialize retrieval pipeline."""
        self.config = config or RetrievalConfig()
        self.indices = indices or {}

        # Components
        self._query_processor = None
        self._result_processor = None
        self._cache: Optional[Dict[str, Any]] = (
            {} if self.config.enable_caching else None
        )

        # Metrics
        self._total_queries = 0
        self._total_time_ms = 0.0
        self._cache_hits = 0

        # Setup logging
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

        # Initialize pipeline
        self._initialize_pipeline()

    def _initialize_pipeline(self) -> None:
        """Initialize pipeline components."""
        self.logger.info("Initializing pipeline: %s", self.config.pipeline_name)

    @abstractmethod
    async def retrieve(self, query_context: QueryContext) -> List[RetrievalResult]:
        """
        Retrieve relevant documents for a query.

        Args:
            query_context: Context containing query and metadata

        Returns:
            List of retrieval results
        """

    def retrieve_sync(self, query: str, **kwargs: Any) -> List[RetrievalResult]:
        """Retrieve documents synchronously."""
        # Create query context
        context = QueryContext(query=query, original_query=query, **kwargs)

        # Run async retrieval
        return asyncio.run(self.retrieve(context))

    async def batch_retrieve(
        self, queries: List[Union[str, QueryContext]]
    ) -> List[List[RetrievalResult]]:
        """Batch retrieval for multiple queries."""
        results = []

        for query in queries:
            if isinstance(query, str):
                context = QueryContext(query=query, original_query=query)
            else:
                context = query

            result = await self.retrieve(context)
            results.append(result)

        return results

    def _create_cache_key(self, query_context: QueryContext) -> str:
        """Create cache key for query."""
        cache_data = {
            "query": query_context.query,
            "top_k": query_context.top_k,
            "filters": query_context.filters,
            "language": query_context.language,
        }

        cache_str = json.dumps(cache_data, sort_keys=True)
        return hashlib.sha256(cache_str.encode()).hexdigest()

    def _check_cache(self, cache_key: str) -> Optional[List[RetrievalResult]]:
        """Check cache for results."""
        if self._cache is None:
            return None

        if cache_key in self._cache:
            entry = self._cache[cache_key]

            # Check TTL
            if time.time() - entry["timestamp"] < self.config.cache_ttl_seconds:
                self._cache_hits += 1
                self.logger.debug("Cache hit")
                return list(entry["results"])
            else:
                # Expired
                del self._cache[cache_key]

        return None

    def _update_cache(self, cache_key: str, results: List[RetrievalResult]) -> None:
        """Update cache with results."""
        if self._cache is None:
            return

        self._cache[cache_key] = {"results": results, "timestamp": time.time()}

        # Limit cache size (simple FIFO)
        max_cache_size = 1000
        if self._cache and len(self._cache) > max_cache_size:
            # Remove oldest entry
            cache = self._cache  # Type narrowing for mypy
            oldest_key = min(cache.keys(), key=lambda k: cache[k]["timestamp"])
            del self._cache[oldest_key]

    def _record_metrics(self, query_time_ms: float, num_results: int) -> None:
        """Record pipeline metrics."""
        self._total_queries += 1
        self._total_time_ms += query_time_ms

        if (
            self.config.log_slow_queries
            and query_time_ms > self.config.slow_query_threshold_ms
        ):
            self.logger.warning(
                "Slow query detected: %.2fms for %d results", query_time_ms, num_results
            )

    def get_metrics(self) -> Dict[str, Any]:
        """Get pipeline metrics."""
        avg_time_ms = self._total_time_ms / max(self._total_queries, 1)
        cache_hit_rate = (
            self._cache_hits / max(self._total_queries, 1) if self._cache else 0.0
        )

        return {
            "pipeline_name": self.config.pipeline_name,
            "total_queries": self._total_queries,
            "average_time_ms": avg_time_ms,
            "cache_hit_rate": cache_hit_rate,
            "cache_enabled": self.config.enable_caching,
            "indices_count": len(self.indices),
        }

    def clear_cache(self) -> None:
        """Clear the cache."""
        if self._cache is not None:
            self._cache.clear()
            self.logger.info("Cache cleared")

    def add_index(self, name: str, index: Any) -> None:
        """Add an index to the pipeline."""
        self.indices[name] = index
        self.logger.info("Added index: %s", name)

    def remove_index(self, name: str) -> None:
        """Remove an index from the pipeline."""
        if name in self.indices:
            del self.indices[name]
            self.logger.info("Removed index: %s", name)


class PipelineComponent(ABC):
    """Base class for pipeline components."""

    def __init__(self, name: str):
        """Initialize pipeline component."""
        self.name = name
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    @abstractmethod
    async def process(self, input_data: Any) -> Any:
        """Process input data."""

    def process_sync(self, input_data: Any) -> Any:
        """Process input data synchronously."""
        return asyncio.run(self.process(input_data))
