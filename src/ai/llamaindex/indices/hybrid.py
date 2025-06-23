"""
Hybrid Vector Index Implementation.

Combines dense and sparse indices for improved retrieval.
"""

import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from llama_index.core import Document

from .base import BaseVectorIndex, VectorIndexConfig, VectorIndexType
from .dense import DenseVectorIndex
from .sparse import BM25Index

logger = logging.getLogger(__name__)


@dataclass
class HybridSearchResult:
    """Result from hybrid search."""

    document: Document
    dense_score: float
    sparse_score: float
    combined_score: float
    metadata: Dict[str, Any]


class HybridVectorIndex(BaseVectorIndex):
    """
    Hybrid vector index combining dense and sparse search.

    Provides the benefits of both semantic and keyword search.
    """

    def __init__(
        self,
        config: Optional[VectorIndexConfig] = None,
        dense_weight: float = 0.7,
        sparse_weight: float = 0.3,
        **kwargs: Any,
    ) -> None:
        """Initialize hybrid vector index."""
        if config is None:
            config = VectorIndexConfig(index_type=VectorIndexType.HYBRID)

        super().__init__(config, **kwargs)

        # Hybrid parameters
        self.dense_weight = dense_weight
        self.sparse_weight = sparse_weight

        # Initialize sub-indices
        self.dense_index = DenseVectorIndex(
            config=config,
            embedding_model=self.embedding_model,
            similarity_scorer=self.similarity_scorer,
            vector_store=self.vector_store,
        )

        self.sparse_index = BM25Index(config=config)

        # Normalization parameters
        self._dense_score_stats = {"min": 0.0, "max": 1.0}
        self._sparse_score_stats = {"min": 0.0, "max": 1.0}

        # Document store
        self._document_store: Dict[str, Document] = {}

    def build_index(self, documents: List[Document]) -> None:
        """Build both dense and sparse indices."""
        self.logger.info("Building hybrid index with %d documents", len(documents))

        # Build dense index
        self.logger.info("Building dense component...")
        self.dense_index.build_index(documents)

        # Build sparse index
        self.logger.info("Building sparse component...")
        self.sparse_index.build_index(documents)

        # Store documents
        self._document_store = {(doc.doc_id or doc.id_): doc for doc in documents}

        # Update metrics
        self._metrics.total_documents = len(documents)

        self.logger.info("Hybrid index built successfully")

    def add_documents(self, documents: List[Document]) -> List[str]:
        """Add documents to both indices."""
        # Add to dense
        dense_ids = self.dense_index.add_documents(documents)

        # Add to sparse
        self.sparse_index.add_documents(documents)

        # Update document store
        for doc in documents:
            doc_id = doc.doc_id or doc.id_
            self._document_store[doc_id] = doc

        # Update metrics
        self._metrics.total_documents += len(documents)

        return dense_ids

    def delete_documents(self, doc_ids: List[str]) -> bool:
        """Delete documents from both indices."""
        dense_success = self.dense_index.delete_documents(doc_ids)
        sparse_success = self.sparse_index.delete_documents(doc_ids)

        if dense_success and sparse_success:
            # Remove from document store
            for doc_id in doc_ids:
                if doc_id in self._document_store:
                    del self._document_store[doc_id]

            # Update metrics
            self._metrics.total_documents -= len(doc_ids)

            return True

        return False

    def search(
        self,
        query: str,
        top_k: Optional[int] = None,
        filters: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> List[Tuple[Document, float]]:
        """Search using both dense and sparse indices."""
        if top_k is None:
            top_k = self.config.default_top_k

        start_time = time.time()

        # Get results from both indices
        # Request more results for better fusion
        k_multiplier = 2

        # Dense search
        dense_results = self.dense_index.search(
            query, top_k * k_multiplier, filters, **kwargs
        )

        # Sparse search
        sparse_results = self.sparse_index.search(
            query, top_k * k_multiplier, filters, **kwargs
        )

        # Combine results
        combined_results = self._combine_results(dense_results, sparse_results, top_k)

        # Update metrics
        query_time = (time.time() - start_time) * 1000
        self._metrics.update_query_metrics(query_time, False)

        # Check if caller wants hybrid results from kwargs
        if kwargs.get("return_hybrid_results", False):
            return combined_results  # type: ignore[return-value]
        else:
            # Convert to standard format
            return [(r.document, r.combined_score) for r in combined_results]

    def _combine_results(
        self,
        dense_results: List[Tuple[Document, float]],
        sparse_results: List[Tuple[Document, float]],
        top_k: int,
    ) -> List[HybridSearchResult]:
        """Combine dense and sparse results."""
        start_time = time.time()

        # Create result mapping
        result_map = {}

        # Process dense results
        for doc, score in dense_results:
            doc_id = doc.doc_id or doc.id_
            result_map[doc_id] = HybridSearchResult(
                document=doc,
                dense_score=score,
                sparse_score=0.0,
                combined_score=0.0,
                metadata={"source": "dense"},
            )

        # Process sparse results
        for doc, score in sparse_results:
            doc_id = doc.doc_id or doc.id_
            if doc_id in result_map:
                result_map[doc_id].sparse_score = score
                result_map[doc_id].metadata["source"] = "both"
            else:
                result_map[doc_id] = HybridSearchResult(
                    document=doc,
                    dense_score=0.0,
                    sparse_score=score,
                    combined_score=0.0,
                    metadata={"source": "sparse"},
                )

        # Normalize and combine scores
        self._normalize_scores(list(result_map.values()))

        # Calculate combined scores
        for result in result_map.values():
            result.combined_score = (
                self.dense_weight * result.dense_score
                + self.sparse_weight * result.sparse_score
            )

        # Sort by combined score
        sorted_results = sorted(
            result_map.values(), key=lambda x: x.combined_score, reverse=True
        )

        # Update metrics
        elapsed_time = (time.time() - start_time) * 1000  # Convert to milliseconds
        self._metrics.update_query_metrics(elapsed_time, cache_hit=False)

        # Return the sorted results (already in HybridSearchResult format)
        return sorted_results[:top_k]

    def _normalize_scores(self, results: List[HybridSearchResult]) -> None:
        """Normalize scores using min-max normalization."""
        # Get score ranges
        dense_scores = [r.dense_score for r in results if r.dense_score > 0]
        sparse_scores = [r.sparse_score for r in results if r.sparse_score > 0]

        if dense_scores:
            dense_min = min(dense_scores)
            dense_max = max(dense_scores)

            # Update stats for future use
            self._dense_score_stats["min"] = dense_min
            self._dense_score_stats["max"] = dense_max

            # Normalize
            for result in results:
                if result.dense_score > 0:
                    if dense_max > dense_min:
                        result.dense_score = (result.dense_score - dense_min) / (
                            dense_max - dense_min
                        )
                    else:
                        result.dense_score = 1.0

        if sparse_scores:
            sparse_min = min(sparse_scores)
            sparse_max = max(sparse_scores)

            # Update stats
            self._sparse_score_stats["min"] = sparse_min
            self._sparse_score_stats["max"] = sparse_max

            # Normalize
            for result in results:
                if result.sparse_score > 0:
                    if sparse_max > sparse_min:
                        result.sparse_score = (result.sparse_score - sparse_min) / (
                            sparse_max - sparse_min
                        )
                    else:
                        result.sparse_score = 1.0

    def set_weights(self, dense_weight: float, sparse_weight: float) -> None:
        """Update combination weights."""
        # Normalize weights
        total = dense_weight + sparse_weight
        self.dense_weight = dense_weight / total
        self.sparse_weight = sparse_weight / total

        self.logger.info(
            "Updated weights - Dense: %.2f, Sparse: %.2f",
            self.dense_weight,
            self.sparse_weight,
        )

    def _optimize_index(self) -> bool:
        """Optimize both indices."""
        dense_success = self.dense_index.optimize()
        sparse_success = self.sparse_index.optimize()

        return dense_success and sparse_success

    def _persist_index(self, path: str) -> bool:
        """Persist hybrid index."""
        # pylint: disable=import-outside-toplevel
        import json
        from pathlib import Path

        persist_dir = Path(path)
        persist_dir.mkdir(parents=True, exist_ok=True)

        # Save configuration
        config_data = {
            "dense_weight": self.dense_weight,
            "sparse_weight": self.sparse_weight,
            "dense_score_stats": self._dense_score_stats,
            "sparse_score_stats": self._sparse_score_stats,
        }

        with open(persist_dir / "hybrid_config.json", "w", encoding="utf-8") as f:
            json.dump(config_data, f, indent=2)

        # Persist sub-indices
        dense_success = self.dense_index.persist(str(persist_dir / "dense"))
        sparse_success = self.sparse_index.persist(str(persist_dir / "sparse"))

        return dense_success and sparse_success

    def _load_index(self, path: str) -> bool:
        """Load hybrid index."""
        # pylint: disable=import-outside-toplevel
        import json
        from pathlib import Path

        persist_dir = Path(path)

        # Load configuration
        config_file = persist_dir / "hybrid_config.json"
        if config_file.exists():
            with open(config_file, "r", encoding="utf-8") as f:
                config_data = json.load(f)
                self.dense_weight = config_data["dense_weight"]
                self.sparse_weight = config_data["sparse_weight"]
                self._dense_score_stats = config_data["dense_score_stats"]
                self._sparse_score_stats = config_data["sparse_score_stats"]

        # Load sub-indices
        dense_success = self.dense_index.load(str(persist_dir / "dense"))
        sparse_success = self.sparse_index.load(str(persist_dir / "sparse"))

        return dense_success and sparse_success


class DenseSparseFusionIndex(HybridVectorIndex):
    """Advanced fusion techniques for dense and sparse results."""

    def __init__(
        self,
        config: Optional[VectorIndexConfig] = None,
        fusion_method: str = "rrf",  # rrf, linear, learned
        **kwargs: Any,
    ):
        """Initialize dense sparse fusion index."""
        super().__init__(config, **kwargs)
        self.fusion_method = fusion_method

        # RRF parameter
        self.rrf_k = 60

    def _combine_results(
        self,
        dense_results: List[Tuple[Document, float]],
        sparse_results: List[Tuple[Document, float]],
        top_k: int,
    ) -> List[HybridSearchResult]:
        """Combine using specified fusion method."""
        if self.fusion_method == "rrf":
            return self._reciprocal_rank_fusion(dense_results, sparse_results, top_k)
        elif self.fusion_method == "linear":
            return super()._combine_results(dense_results, sparse_results, top_k)
        else:
            # Default to linear combination
            return super()._combine_results(dense_results, sparse_results, top_k)

    def _reciprocal_rank_fusion(
        self,
        dense_results: List[Tuple[Document, float]],
        sparse_results: List[Tuple[Document, float]],
        top_k: int,
    ) -> List[HybridSearchResult]:
        """Reciprocal Rank Fusion (RRF) combination."""
        # Create document rankings
        dense_rankings = {
            (doc.doc_id or doc.id_): rank
            for rank, (doc, _) in enumerate(dense_results, 1)
        }

        sparse_rankings = {
            (doc.doc_id or doc.id_): rank
            for rank, (doc, _) in enumerate(sparse_results, 1)
        }

        # Calculate RRF scores
        rrf_scores = {}
        all_doc_ids = set(dense_rankings.keys()) | set(sparse_rankings.keys())

        for doc_id in all_doc_ids:
            dense_rank = dense_rankings.get(doc_id, float("inf"))
            sparse_rank = sparse_rankings.get(doc_id, float("inf"))

            # RRF formula
            rrf_score = 1 / (self.rrf_k + dense_rank) + 1 / (self.rrf_k + sparse_rank)

            rrf_scores[doc_id] = rrf_score

        # Create results
        results = []
        for doc_id, rrf_score in rrf_scores.items():
            # Find document
            doc = None
            dense_score = 0.0
            sparse_score = 0.0

            for d, s in dense_results:
                if (d.doc_id or d.id_) == doc_id:
                    doc = d
                    dense_score = s
                    break

            if doc is None:
                for d, s in sparse_results:
                    if (d.doc_id or d.id_) == doc_id:
                        doc = d
                        sparse_score = s
                        break

            if doc:
                results.append(
                    HybridSearchResult(
                        document=doc,
                        dense_score=dense_score,
                        sparse_score=sparse_score,
                        combined_score=rrf_score,
                        metadata={
                            "fusion_method": "rrf",
                            "dense_rank": dense_rankings.get(doc_id, -1),
                            "sparse_rank": sparse_rankings.get(doc_id, -1),
                        },
                    )
                )

        # Sort by RRF score
        results.sort(key=lambda x: x.combined_score, reverse=True)

        return results[:top_k]


class MultiStageIndex(BaseVectorIndex):
    """
    Multi-stage retrieval index.

    Uses sparse search for initial retrieval, then dense for re-ranking.
    """

    def __init__(
        self,
        config: Optional[VectorIndexConfig] = None,
        first_stage_k: int = 100,
        **kwargs: Any,
    ):
        """Initialize multi-stage index."""
        if config is None:
            config = VectorIndexConfig(index_type=VectorIndexType.HYBRID)

        super().__init__(config, **kwargs)

        self.first_stage_k = first_stage_k

        # Initialize stages
        self.sparse_index = BM25Index(config=config)
        self.dense_index = DenseVectorIndex(
            config=config,
            embedding_model=self.embedding_model,
            similarity_scorer=self.similarity_scorer,
            vector_store=self.vector_store,
        )

        # Document store
        self._document_store: Dict[str, Document] = {}

    def build_index(self, documents: List[Document]) -> None:
        """Build multi-stage index."""
        self.logger.info("Building multi-stage index with %d documents", len(documents))

        # Build both indices
        self.sparse_index.build_index(documents)
        self.dense_index.build_index(documents)

        # Store documents
        self._document_store = {(doc.doc_id or doc.id_): doc for doc in documents}

        # Update metrics
        self._metrics.total_documents = len(documents)

    def add_documents(self, documents: List[Document]) -> List[str]:
        """Add documents to both stages."""
        self.sparse_index.add_documents(documents)
        self.dense_index.add_documents(documents)

        # Update document store
        doc_ids = []
        for doc in documents:
            doc_id = doc.doc_id or doc.id_
            self._document_store[doc_id] = doc
            doc_ids.append(doc_id)

        # Update metrics
        self._metrics.total_documents += len(documents)

        return doc_ids

    def delete_documents(self, doc_ids: List[str]) -> bool:
        """Delete from both stages."""
        sparse_success = self.sparse_index.delete_documents(doc_ids)
        dense_success = self.dense_index.delete_documents(doc_ids)

        if sparse_success and dense_success:
            for doc_id in doc_ids:
                if doc_id in self._document_store:
                    del self._document_store[doc_id]

            self._metrics.total_documents -= len(doc_ids)
            return True

        return False

    def search(
        self,
        query: str,
        top_k: Optional[int] = None,
        filters: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> List[Tuple[Document, float]]:
        """Multi-stage search."""
        if top_k is None:
            top_k = self.config.default_top_k

        start_time = time.time()

        # Stage 1: Sparse retrieval
        self.logger.debug("Stage 1: Sparse retrieval for top %d", self.first_stage_k)
        sparse_results = self.sparse_index.search(
            query, self.first_stage_k, filters, **kwargs
        )

        if not sparse_results:
            return []

        # Extract documents for re-ranking
        candidate_docs = [doc for doc, _ in sparse_results]

        # Stage 2: Dense re-ranking
        self.logger.debug(
            "Stage 2: Dense re-ranking of %d candidates", len(candidate_docs)
        )

        # Create a temporary index with just the candidates
        # In production, use more efficient re-ranking
        rerank_results = []

        # Get query embedding
        if self.dense_index.embedding_model is None:
            self.logger.error("Dense index embedding model not initialized")
            return sparse_results[:top_k]

        query_embedding = (
            self.dense_index.embedding_model.get_agg_embedding_from_queries([query])
        )

        for doc in candidate_docs:
            doc_embeddings = self.dense_index.embedding_model.get_text_embedding_batch(
                [doc.text]
            )
            doc_embedding = doc_embeddings[0]

            if self.dense_index.similarity_scorer is None:
                # Fallback to cosine similarity
                score = float(
                    np.dot(query_embedding, doc_embedding)
                    / (np.linalg.norm(query_embedding) * np.linalg.norm(doc_embedding))
                )
            else:
                score = self.dense_index.similarity_scorer.score(
                    query_embedding, doc_embedding, {"query": query}, doc.metadata
                )
            rerank_results.append((doc, score))

        # Sort by dense score
        rerank_results.sort(key=lambda x: x[1], reverse=True)

        # Update metrics
        query_time = (time.time() - start_time) * 1000
        self._metrics.update_query_metrics(query_time, False)

        return rerank_results[:top_k]

    def _optimize_index(self) -> bool:
        """Optimize both stages."""
        sparse_success = self.sparse_index.optimize()
        dense_success = self.dense_index.optimize()
        return sparse_success and dense_success

    def _persist_index(self, path: str) -> bool:
        """Persist multi-stage index."""
        # pylint: disable=import-outside-toplevel
        import json
        from pathlib import Path

        persist_dir = Path(path)
        persist_dir.mkdir(parents=True, exist_ok=True)

        # Save configuration
        config_data = {"first_stage_k": self.first_stage_k}

        with open(persist_dir / "multistage_config.json", "w", encoding="utf-8") as f:
            json.dump(config_data, f)

        # Persist stages
        sparse_success = self.sparse_index.persist(str(persist_dir / "sparse"))
        dense_success = self.dense_index.persist(str(persist_dir / "dense"))

        return sparse_success and dense_success

    def _load_index(self, path: str) -> bool:
        """Load multi-stage index."""
        # pylint: disable=import-outside-toplevel
        import json
        from pathlib import Path

        persist_dir = Path(path)

        # Load configuration
        config_file = persist_dir / "multistage_config.json"
        if config_file.exists():
            with open(config_file, "r", encoding="utf-8") as f:
                config_data = json.load(f)
                self.first_stage_k = config_data["first_stage_k"]

        # Load stages
        sparse_success = self.sparse_index.load(str(persist_dir / "sparse"))
        dense_success = self.dense_index.load(str(persist_dir / "dense"))

        return sparse_success and dense_success
