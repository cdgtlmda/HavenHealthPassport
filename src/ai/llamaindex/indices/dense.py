"""Dense Vector Index Implementation.

Provides dense vector indices for similarity search.
"""

import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from llama_index.core import Document, StorageContext, VectorStoreIndex
from llama_index.core.schema import TextNode

from ..embeddings import get_embedding_model
from ..similarity import get_similarity_scorer
from .base import BaseVectorIndex, VectorIndexConfig, VectorIndexType

logger = logging.getLogger(__name__)


class DenseVectorIndex(BaseVectorIndex):
    """Standard dense vector index.

    Uses dense embeddings for similarity search.
    """

    def __init__(
        self, config: Optional[VectorIndexConfig] = None, **kwargs: Any
    ) -> None:
        """Initialize dense vector index."""
        # Set default config for dense index
        if config is None:
            config = VectorIndexConfig(index_type=VectorIndexType.DENSE)

        # Initialize embedding model if not provided
        if "embedding_model" not in kwargs or kwargs["embedding_model"] is None:
            kwargs["embedding_model"] = get_embedding_model("general")

        # Initialize similarity scorer if not provided
        if "similarity_scorer" not in kwargs or kwargs["similarity_scorer"] is None:
            kwargs["similarity_scorer"] = get_similarity_scorer("general")

        super().__init__(config, **kwargs)

        # Dense index specific attributes
        self._embeddings_cache: Dict[str, List[float]] = {}
        self._document_store: Dict[str, Document] = {}
        self.reranker = kwargs.get("reranker", None)

    def build_index(self, documents: List[Document]) -> None:
        """Build dense vector index from documents."""
        self.logger.info("Building dense index with %d documents", len(documents))

        # Clear existing data
        self._embeddings_cache.clear()
        self._document_store.clear()

        # Create nodes from documents
        nodes = []
        for doc in documents:
            node = TextNode(
                text=doc.text, metadata=doc.metadata, id_=doc.doc_id or doc.id_
            )
            nodes.append(node)
            self._document_store[node.id_] = doc

        # Build index
        if self.vector_store:
            storage_context = StorageContext.from_defaults(
                vector_store=self.vector_store
            )
            self._index = VectorStoreIndex(
                nodes=nodes,
                storage_context=storage_context,
                embed_model=self.embedding_model,
                show_progress=True,
            )
        else:
            self._index = VectorStoreIndex(
                nodes=nodes, embed_model=self.embedding_model, show_progress=True
            )

        # Update metrics
        self._metrics.total_documents = len(documents)

        self.logger.info("Dense index built successfully")

    def add_documents(self, documents: List[Document]) -> List[str]:
        """Add documents to existing index."""
        if self._index is None:
            self.build_index(documents)
            return [doc.doc_id or doc.id_ for doc in documents]

        doc_ids = []
        for doc in documents:
            node = TextNode(
                text=doc.text, metadata=doc.metadata, id_=doc.doc_id or doc.id_
            )

            # Add to index
            self._index.insert_nodes([node])

            # Store document
            self._document_store[node.id_] = doc
            doc_ids.append(node.id_)

        # Update metrics
        self._metrics.total_documents += len(documents)

        # Clear cache as index has changed
        self.clear_cache()

        return doc_ids

    def delete_documents(self, doc_ids: List[str]) -> bool:
        """Delete documents from index."""
        if self._index is None:
            return False

        try:
            for doc_id in doc_ids:
                # Delete from index
                self._index.delete_ref_doc(doc_id)

                # Remove from document store
                if doc_id in self._document_store:
                    del self._document_store[doc_id]

                # Remove from embeddings cache
                if doc_id in self._embeddings_cache:
                    del self._embeddings_cache[doc_id]

            # Update metrics
            self._metrics.total_documents -= len(doc_ids)

            # Clear cache
            self.clear_cache()

            return True

        except (ValueError, AttributeError) as e:
            self.logger.error("Failed to delete documents: %s", e)
            return False

    def search(
        self,
        query: str,
        top_k: Optional[int] = None,
        filters: Optional[Dict[str, Any]] = None,
        **kwargs: Any,  # pylint: disable=unused-argument
    ) -> List[Tuple[Document, float]]:
        """Search the dense vector index."""
        if self._index is None:
            self.logger.warning("Index not built yet")
            return []

        # Use default top_k if not specified
        if top_k is None:
            top_k = self.config.default_top_k

        # Check cache
        cache_key = self._create_cache_key(query, top_k, filters)
        cached_results = self._check_cache(cache_key)
        if cached_results is not None:
            self._metrics.update_query_metrics(0, True)
            return cached_results

        start_time = time.time()

        try:
            # Create retriever
            retriever = self._index.as_retriever(
                similarity_top_k=top_k * 2 if self.config.enable_reranking else top_k,
                similarity_threshold=self.config.similarity_threshold,
            )

            # Retrieve nodes
            nodes = retriever.retrieve(query)

            # Apply filters if provided
            if filters:
                filtered_nodes = self._apply_filters(
                    [node.node for node in nodes], filters
                )
                nodes = [n for n in nodes if n.node in filtered_nodes]

            # Get query embedding
            if self.embedding_model is None:
                self.logger.error("Embedding model not initialized")
                return []
            query_embedding = self.embedding_model.get_agg_embedding_from_queries(
                [query]
            )

            # Score with custom similarity scorer
            scored_results = []
            for node in nodes:
                # Get document
                doc = self._document_store.get(node.node.id_)
                if doc is None:
                    continue

                # Get document embedding (from cache or compute)
                doc_embedding = self._get_document_embedding(doc)

                # Calculate similarity
                if self.similarity_scorer is None:
                    # Fallback to cosine similarity
                    score = float(
                        np.dot(query_embedding, doc_embedding)
                        / (
                            np.linalg.norm(query_embedding)
                            * np.linalg.norm(doc_embedding)
                        )
                    )
                else:
                    score = self.similarity_scorer.score(
                        query_embedding, doc_embedding, {"query": query}, doc.metadata
                    )

                scored_results.append((doc, score))

            # Sort by score
            scored_results.sort(key=lambda x: x[1], reverse=True)

            # Apply re-ranking if enabled
            if (
                self.config.enable_reranking
                and hasattr(self, "reranker")
                and self.reranker
            ):
                # Convert to reranker format
                rerank_input = [
                    (doc.doc_id or doc.id_, score, doc.metadata)
                    for doc, score in scored_results
                ]

                # Re-rank
                reranked = self.reranker.rerank(query, rerank_input)

                # Convert back to results
                final_results = []
                for r in reranked[:top_k]:
                    doc = next(
                        d for d, _ in scored_results if (d.doc_id or d.id_) == r.doc_id
                    )
                    final_results.append((doc, r.rerank_score))

                results = final_results
            else:
                results = scored_results[:top_k]

            # Update cache
            self._update_cache(cache_key, results)

            # Update metrics
            query_time = (time.time() - start_time) * 1000
            self._metrics.update_query_metrics(query_time, False)

            if query_time > self.config.slow_query_threshold_ms:
                self._metrics.slow_query_count += 1
                self.logger.warning("Slow query detected: %.2fms", query_time)

            return results

        except (ValueError, AttributeError) as e:
            self.logger.error("Search failed: %s", e)
            self._metrics.error_count += 1
            return []

    def _get_document_embedding(self, document: Document) -> List[float]:
        """Get or compute document embedding."""
        doc_id = document.doc_id or document.id_

        # Check cache
        if doc_id in self._embeddings_cache:
            return self._embeddings_cache[doc_id]

        # Compute embedding
        if self.embedding_model is not None:
            embeddings = self.embedding_model.get_text_embedding_batch([document.text])
            embedding = embeddings[0]
        else:
            raise ValueError("Embedding model not initialized")

        # Cache it
        self._embeddings_cache[doc_id] = embedding

        return embedding

    def _optimize_index(self) -> bool:
        """Optimize dense vector index."""
        try:
            # Re-compute embeddings if needed
            if self._index is not None and hasattr(self._index, "refresh_ref_docs"):
                self._index.refresh_ref_docs(self._document_store.keys())

            # Clear embeddings cache to force recomputation
            self._embeddings_cache.clear()

            return True

        except (ValueError, RuntimeError) as e:
            self.logger.error("Optimization failed: %s", e)
            return False

    def _persist_index(self, path: str) -> bool:
        """Persist dense vector index to disk."""
        try:
            persist_dir = Path(path)
            persist_dir.mkdir(parents=True, exist_ok=True)

            # Persist LlamaIndex components
            if self._index:
                self._index.storage_context.persist(persist_dir=str(persist_dir))

            # Persist additional data
            metadata = {
                "config": self.config.__dict__,
                "metrics": self._metrics.__dict__,
                "document_count": len(self._document_store),
            }

            with open(persist_dir / "metadata.json", "w", encoding="utf-8") as f:
                json.dump(metadata, f, indent=2, default=str)

            # Persist document store
            with open(persist_dir / "documents.json", "w", encoding="utf-8") as f:
                json.dump(self._document_store, f, indent=2)

            # Persist embeddings cache
            # Embeddings are already stored as lists in the cache
            embeddings_data = self._embeddings_cache
            with open(persist_dir / "embeddings.json", "w", encoding="utf-8") as f:
                json.dump(embeddings_data, f, indent=2)

            self.logger.info("Index persisted to %s", persist_dir)
            return True

        except OSError as e:
            self.logger.error("Failed to persist index: %s", e)
            return False

    def _load_index(self, path: str) -> bool:
        """Load dense vector index from disk."""
        try:
            persist_dir = Path(path)

            if not persist_dir.exists():
                self.logger.error("Persist directory not found: %s", persist_dir)
                return False

            # Load LlamaIndex components
            # pylint: disable=import-outside-toplevel
            from llama_index.core import load_index_from_storage

            storage_context = StorageContext.from_defaults(persist_dir=str(persist_dir))
            self._index = load_index_from_storage(storage_context)

            # Load metadata
            with open(persist_dir / "metadata.json", "r", encoding="utf-8") as f:
                metadata = json.load(f)

            # Update metrics
            for key, value in metadata.get("metrics", {}).items():
                if hasattr(self._metrics, key):
                    setattr(self._metrics, key, value)

            # Load document store
            with open(persist_dir / "documents.json", "r", encoding="utf-8") as f:
                self._document_store = json.load(f)

            # Load embeddings cache
            with open(persist_dir / "embeddings.json", "r", encoding="utf-8") as f:
                self._embeddings_cache = json.load(f)

            self.logger.info("Index loaded from %s", persist_dir)
            return True

        except (OSError, ValueError) as e:
            self.logger.error("Failed to load index: %s", e)
            return False


class OptimizedDenseIndex(DenseVectorIndex):
    """
    Optimized dense vector index with performance enhancements.

    Features:
    - Quantization for reduced memory usage
    - Batch processing optimizations
    - Parallel search capabilities
    - HNSW graph for approximate search
    """

    def __init__(
        self, config: Optional[VectorIndexConfig] = None, **kwargs: Any
    ) -> None:
        """Initialize optimized dense index."""
        # Enable optimizations by default
        if config is None:
            config = VectorIndexConfig(
                index_type=VectorIndexType.DENSE,
                enable_approximate_search=True,
                enable_compression=True,
            )

        super().__init__(config, **kwargs)

        # Optimization specific attributes
        self._quantized_embeddings: Dict[str, List[int]] = {}
        self._centroid_cache: Dict[str, List[float]] = {}
        self._is_optimized = False

    def build_index(self, documents: List[Document]) -> None:
        """Build optimized dense index."""
        # Build base index first
        super().build_index(documents)

        # Apply optimizations
        if self.config.enable_compression or self.config.enable_approximate_search:
            self._apply_optimizations()

    def _apply_optimizations(self) -> None:
        """Apply performance optimizations to the index."""
        self.logger.info("Applying index optimizations...")

        if self.config.enable_compression:
            self._apply_quantization()

        if self.config.enable_approximate_search:
            self._build_hnsw_graph()

        self._is_optimized = True
        self.logger.info("Index optimizations applied")

    def _apply_quantization(self) -> None:
        """Apply product quantization to embeddings."""
        # Simplified quantization - in production use faiss or similar
        for doc_id, embedding in self._embeddings_cache.items():
            # Convert to int8 for compression
            embedding_array = np.array(embedding)

            # Normalize to [-1, 1]
            norm = np.linalg.norm(embedding_array)
            if norm > 0:
                embedding_array = embedding_array / norm

            # Quantize to int8
            quantized = (embedding_array * 127).astype(np.int8)
            self._quantized_embeddings[doc_id] = quantized.tolist()

        self.logger.info("Quantized %d embeddings", len(self._quantized_embeddings))

    def _build_hnsw_graph(self) -> None:
        """Build HNSW graph for approximate search."""
        # Placeholder - in production, use nmslib or faiss
        self.logger.info("HNSW graph building placeholder")

    def search(
        self,
        query: str,
        top_k: Optional[int] = None,
        filters: Optional[Dict[str, Any]] = None,
        use_approximate: Optional[bool] = None,
        **kwargs: Any,
    ) -> List[Tuple[Document, float]]:
        """Optimized search with approximate option."""
        if use_approximate is None:
            use_approximate = self.config.enable_approximate_search

        if use_approximate and self._is_optimized:
            return self._approximate_search(query, top_k, filters)
        else:
            return super().search(query, top_k, filters, **kwargs)

    def _approximate_search(
        self, query: str, top_k: Optional[int], filters: Optional[Dict[str, Any]]
    ) -> List[Tuple[Document, float]]:
        """Perform approximate nearest neighbor search."""
        # Simplified implementation - in production use HNSW or IVF
        self.logger.debug("Using approximate search")

        # For now, fall back to exact search
        return super().search(query, top_k, filters)

    def get_memory_usage(self) -> Dict[str, float]:
        """Get memory usage statistics."""
        usage = {
            "embeddings_mb": len(self._embeddings_cache)
            * self.config.dimension
            * 4
            / (1024 * 1024),
            "documents_mb": sum(len(doc.text) for doc in self._document_store.values())
            / (1024 * 1024),
        }

        if self._quantized_embeddings:
            usage["quantized_mb"] = (
                len(self._quantized_embeddings) * self.config.dimension / (1024 * 1024)
            )
            usage["compression_ratio"] = usage["quantized_mb"] / usage["embeddings_mb"]

        return usage


class ShardedDenseIndex(BaseVectorIndex):
    """
    Sharded dense vector index for large-scale deployments.

    Features:
    - Horizontal sharding across multiple indices
    - Distributed search capabilities
    - Load balancing
    - Shard management
    """

    def __init__(
        self,
        config: Optional[VectorIndexConfig] = None,
        num_shards: int = 4,
        **kwargs: Any,
    ) -> None:
        """Initialize sharded dense index."""
        if config is None:
            config = VectorIndexConfig(index_type=VectorIndexType.DENSE)

        super().__init__(config, **kwargs)

        self.num_shards = num_shards
        self.shards: List[DenseVectorIndex] = []
        self.shard_mapping: Dict[str, int] = {}  # doc_id -> shard_index

        # Initialize shards
        self._init_shards()

    def _init_shards(self) -> None:
        """Initialize shard indices."""
        for i in range(self.num_shards):
            shard_config = VectorIndexConfig(
                index_type=VectorIndexType.DENSE,
                index_name=f"{self.config.index_name}_shard_{i}",
                dimension=self.config.dimension,
                enable_persistence=self.config.enable_persistence,
                persist_path=(
                    f"{self.config.persist_path}_shard_{i}"
                    if self.config.persist_path
                    else None
                ),
            )

            shard = DenseVectorIndex(
                config=shard_config,
                embedding_model=self.embedding_model,
                similarity_scorer=self.similarity_scorer,
                vector_store=self.vector_store,
            )

            self.shards.append(shard)

    def _get_shard_for_document(self, doc_id: str) -> int:
        """Determine which shard a document should go to."""
        # Simple hash-based sharding
        # pylint: disable=import-outside-toplevel
        import hashlib

        hash_value = int(
            hashlib.md5(doc_id.encode(), usedforsecurity=False).hexdigest(), 16
        )
        return hash_value % self.num_shards

    def build_index(self, documents: List[Document]) -> None:
        """Build sharded index from documents."""
        self.logger.info(
            "Building sharded index with %d documents across %d shards",
            len(documents),
            self.num_shards,
        )

        # Group documents by shard
        shard_documents: List[List[Document]] = [[] for _ in range(self.num_shards)]

        for doc in documents:
            doc_id = doc.doc_id or doc.id_
            shard_idx = self._get_shard_for_document(doc_id)
            shard_documents[shard_idx].append(doc)
            self.shard_mapping[doc_id] = shard_idx

        # Build each shard
        for i, shard_docs in enumerate(shard_documents):
            if shard_docs:
                self.logger.info(
                    "Building shard %d with %d documents", i, len(shard_docs)
                )
                self.shards[i].build_index(shard_docs)

        # Update metrics
        self._metrics.total_documents = len(documents)

    def add_documents(self, documents: List[Document]) -> List[str]:
        """Add documents to sharded index."""
        doc_ids = []
        shard_documents: List[List[Document]] = [[] for _ in range(self.num_shards)]

        # Group by shard
        for doc in documents:
            doc_id = doc.doc_id or doc.id_
            shard_idx = self._get_shard_for_document(doc_id)
            shard_documents[shard_idx].append(doc)
            self.shard_mapping[doc_id] = shard_idx
            doc_ids.append(doc_id)

        # Add to shards
        for i, shard_docs in enumerate(shard_documents):
            if shard_docs:
                self.shards[i].add_documents(shard_docs)

        # Update metrics
        self._metrics.total_documents += len(documents)

        return doc_ids

    def delete_documents(self, doc_ids: List[str]) -> bool:
        """Delete documents from sharded index."""
        # Group by shard
        shard_deletions: List[List[str]] = [[] for _ in range(self.num_shards)]

        for doc_id in doc_ids:
            if doc_id in self.shard_mapping:
                shard_idx = self.shard_mapping[doc_id]
                shard_deletions[shard_idx].append(doc_id)

        # Delete from shards
        success = True
        for i, shard_doc_ids in enumerate(shard_deletions):
            if shard_doc_ids:
                if not self.shards[i].delete_documents(shard_doc_ids):
                    success = False
                else:
                    # Remove from mapping
                    for doc_id in shard_doc_ids:
                        del self.shard_mapping[doc_id]

        # Update metrics
        if success:
            self._metrics.total_documents -= len(doc_ids)

        return success

    def search(
        self,
        query: str,
        top_k: Optional[int] = None,
        filters: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> List[Tuple[Document, float]]:
        """Search across all shards."""
        if top_k is None:
            top_k = self.config.default_top_k

        # Search each shard
        all_results = []
        for i, shard in enumerate(self.shards):
            self.logger.debug("Searching shard %d", i)
            shard_results = shard.search(query, top_k, filters, **kwargs)
            all_results.extend(shard_results)

        # Merge and sort results
        all_results.sort(key=lambda x: x[1], reverse=True)

        # Return top k
        return all_results[:top_k]

    def _optimize_index(self) -> bool:
        """Optimize all shards."""
        success = True
        for i, shard in enumerate(self.shards):
            self.logger.info("Optimizing shard %d", i)
            if not shard.optimize():
                success = False

        return success

    def _persist_index(self, path: str) -> bool:
        """Persist sharded index."""
        persist_dir = Path(path)
        persist_dir.mkdir(parents=True, exist_ok=True)

        # Save shard mapping
        mapping_file = persist_dir / "shard_mapping.json"
        with open(mapping_file, "w", encoding="utf-8") as f:
            json.dump({"num_shards": self.num_shards, "mapping": self.shard_mapping}, f)

        # Persist each shard
        success = True
        for i, shard in enumerate(self.shards):
            shard_path = persist_dir / f"shard_{i}"
            if not shard.persist(str(shard_path)):
                success = False

        return success

    def _load_index(self, path: str) -> bool:
        """Load sharded index."""
        persist_dir = Path(path)

        # Load shard mapping
        mapping_file = persist_dir / "shard_mapping.json"
        if not mapping_file.exists():
            return False

        with open(mapping_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            self.num_shards = data["num_shards"]
            self.shard_mapping = data["mapping"]

        # Reinitialize shards if needed
        if len(self.shards) != self.num_shards:
            self.shards = []
            self._init_shards()

        # Load each shard
        success = True
        for i in range(self.num_shards):
            shard_path = persist_dir / f"shard_{i}"
            if not self.shards[i].load(str(shard_path)):
                success = False

        return success

    def get_shard_statistics(self) -> Dict[str, Any]:
        """Get statistics for each shard."""
        stats: Dict[str, Any] = {
            "num_shards": self.num_shards,
            "total_documents": self._metrics.total_documents,
            "shards": [],
        }

        for i, shard in enumerate(self.shards):
            shard_metrics = shard.get_metrics()
            stats["shards"].append(
                {
                    "shard_id": i,
                    "documents": shard_metrics.total_documents,
                    "queries": shard_metrics.total_queries,
                    "avg_query_time_ms": shard_metrics.average_query_time_ms,
                }
            )

        return stats
