"""
Retrieval Pipeline Implementations.

Various retrieval pipeline implementations for different use cases.
"""

import asyncio
import logging
import time
from collections import defaultdict
from typing import Any, Dict, List, Optional

from ..indices import BaseVectorIndex
from .base import (
    PipelineStage,
    QueryContext,
    RetrievalConfig,
    RetrievalPipeline,
    RetrievalResult,
)
from .query import QueryAnalyzer, QueryExpander, QueryProcessor, SpellCorrector

logger = logging.getLogger(__name__)


class BasicRetrievalPipeline(RetrievalPipeline):
    """
    Basic retrieval pipeline.

    Simple pipeline with query processing and retrieval.
    """

    def __init__(
        self,
        config: Optional[RetrievalConfig] = None,
        indices: Optional[Dict[str, BaseVectorIndex]] = None,
        query_processor: Optional[QueryProcessor] = None,
    ):
        """Initialize the basic retrieval pipeline."""
        super().__init__(config, indices)

        self.query_processor = query_processor or QueryProcessor()

        # Ensure we have at least one index
        if not self.indices:
            raise ValueError("At least one index must be provided")

    async def retrieve(self, query_context: QueryContext) -> List[RetrievalResult]:
        """Execute basic retrieval process."""
        start_time = time.time()

        # Check cache
        cache_key = self._create_cache_key(query_context)
        cached_results = self._check_cache(cache_key)
        if cached_results is not None:
            return cached_results

        try:
            # Stage 1: Query processing
            query_context = await self.query_processor.process(query_context)

            # Stage 2: Retrieval from indices
            results = await self._retrieve_from_indices(query_context)

            # Stage 3: Basic filtering
            results = self._filter_results(results, query_context)

            # Sort by score and limit
            results.sort(key=lambda r: r.score, reverse=True)
            results = results[: query_context.top_k]

            # Update cache
            self._update_cache(cache_key, results)

            # Record metrics
            elapsed_ms = (time.time() - start_time) * 1000
            self._record_metrics(elapsed_ms, len(results))

            return results

        except (ValueError, AttributeError) as e:
            self.logger.error("Retrieval failed: %s", e)
            return []

    async def _retrieve_from_indices(
        self, query_context: QueryContext
    ) -> List[RetrievalResult]:
        """Retrieve from all indices."""
        all_results = []

        for index_name, index in self.indices.items():
            try:
                # Search index
                search_results = index.search(
                    query_context.query,
                    top_k=self.config.retrieval_top_k,
                    filters=query_context.filters,
                )

                # Convert to RetrievalResult
                for rank, (doc, score) in enumerate(search_results):
                    result = RetrievalResult(
                        document=doc,
                        score=score,
                        rank=rank,
                        retrieval_score=score,
                        final_score=score,
                        source_index=index_name,
                        pipeline_stages=[PipelineStage.RETRIEVAL],
                    )
                    all_results.append(result)

            except (ValueError, AttributeError) as e:
                self.logger.error("Failed to search index %s: %s", index_name, e)

        return all_results

    def _filter_results(
        self, results: List[RetrievalResult], query_context: QueryContext
    ) -> List[RetrievalResult]:
        """Filter results based on criteria."""
        if not self.config.enable_filtering:
            return results

        filtered = []
        seen_docs = set()

        for result in results:
            # Skip if below threshold
            if result.score < self.config.min_score_threshold:
                continue

            # Skip duplicates
            if self.config.filter_duplicates:
                doc_id = result.document.doc_id or result.document.id_
                if doc_id in seen_docs:
                    continue
                seen_docs.add(doc_id)

            # Language filtering
            if self.config.filter_language:
                doc_lang = result.document.metadata.get("language", "en")
                if doc_lang != query_context.language:
                    continue

            filtered.append(result)
            result.pipeline_stages.append(PipelineStage.FILTERING)

        return filtered


class AdvancedRetrievalPipeline(BasicRetrievalPipeline):
    """
    Advanced retrieval pipeline.

    Includes query expansion, reranking, and explanation.
    """

    def __init__(
        self,
        config: Optional[RetrievalConfig] = None,
        indices: Optional[Dict[str, BaseVectorIndex]] = None,
        query_processor: Optional[QueryProcessor] = None,
        query_expander: Optional[QueryExpander] = None,
        query_analyzer: Optional[QueryAnalyzer] = None,
        spell_corrector: Optional[SpellCorrector] = None,
        reranker: Optional[Any] = None,
    ):
        """Initialize the advanced retrieval pipeline."""
        super().__init__(config, indices, query_processor)

        self.query_expander = query_expander or QueryExpander()
        self.query_analyzer = query_analyzer or QueryAnalyzer()
        self.spell_corrector = spell_corrector or SpellCorrector()
        self.reranker = reranker

    async def retrieve(self, query_context: QueryContext) -> List[RetrievalResult]:
        """Advanced retrieval process."""
        start_time = time.time()

        # Check cache
        cache_key = self._create_cache_key(query_context)
        cached_results = self._check_cache(cache_key)
        if cached_results is not None:
            return cached_results

        try:
            # Stage 1: Query analysis
            query_context = await self.query_analyzer.process(query_context)

            # Stage 2: Spell correction
            if self.config.enable_spell_correction:
                query_context = await self.spell_corrector.process(query_context)

            # Stage 3: Query processing
            query_context = await self.query_processor.process(query_context)

            # Stage 4: Query expansion
            if self.config.enable_query_expansion:
                query_context = await self.query_expander.process(query_context)

            # Stage 5: Retrieval
            results = await self._retrieve_from_indices(query_context)

            # Stage 6: Filtering
            results = self._filter_results(results, query_context)

            # Stage 7: Reranking
            if self.config.enable_reranking and self.reranker and len(results) > 0:
                results = await self._rerank_results(results, query_context)

            # Stage 8: Explanation generation
            if query_context.include_explanations:
                results = self._generate_explanations(results, query_context)

            # Final sorting and limiting
            results.sort(key=lambda r: r.final_score, reverse=True)
            results = results[: query_context.top_k]

            # Update cache
            self._update_cache(cache_key, results)

            # Record metrics
            elapsed_ms = (time.time() - start_time) * 1000
            self._record_metrics(elapsed_ms, len(results))

            return results

        except (ValueError, AttributeError) as e:
            self.logger.error("Advanced retrieval failed: %s", e)
            return []

    async def _rerank_results(
        self, results: List[RetrievalResult], query_context: QueryContext
    ) -> List[RetrievalResult]:
        """Rerank results."""
        if self.reranker is None:
            return results

        # Prepare for reranking
        rerank_input = [
            (r.document.doc_id or r.document.id_, r.score, r.document.metadata)
            for r in results[: self.config.rerank_top_k]
        ]

        # Rerank
        reranked = self.reranker.rerank(query_context.query, rerank_input)

        # Update results
        reranked_results = []
        for rerank_result in reranked:
            # Find original result
            original = next(
                r
                for r in results
                if (r.document.doc_id or r.document.id_) == rerank_result.doc_id
            )

            # Update scores
            original.rerank_score = rerank_result.rerank_score
            original.final_score = rerank_result.rerank_score
            original.pipeline_stages.append(PipelineStage.RERANKING)

            reranked_results.append(original)

        # Add non-reranked results
        reranked_ids = {r.doc_id for r in reranked}
        for result in results[self.config.rerank_top_k :]:
            doc_id = result.document.doc_id or result.document.id_
            if doc_id not in reranked_ids:
                reranked_results.append(result)

        return reranked_results

    def _generate_explanations(
        self, results: List[RetrievalResult], query_context: QueryContext
    ) -> List[RetrievalResult]:
        """Generate explanations for results."""
        expanded_terms = query_context.metadata.get("expanded_terms", [])

        for result in results:
            explanations = {}

            # Match analysis
            doc_text = result.document.text.lower()
            query_terms = query_context.query.lower().split()

            matched_terms = []
            for term in query_terms:
                if term in doc_text:
                    matched_terms.append(term)

            result.matched_terms = matched_terms

            # Scoring explanation
            explanations["retrieval_score"] = (
                f"Base similarity: {result.retrieval_score:.3f}"
            )

            if result.rerank_score > 0:
                explanations["rerank_score"] = (
                    f"Reranked score: {result.rerank_score:.3f}"
                )

            # Expansion explanation
            if expanded_terms:
                matched_expansions = [
                    term for term in expanded_terms if term.lower() in doc_text
                ]
                if matched_expansions:
                    explanations["expansions"] = (
                        f"Matched expansions: {', '.join(matched_expansions)}"
                    )

            # Intent matching
            if "intent" in query_context.metadata:
                explanations["intent"] = (
                    f"Query intent: {query_context.metadata['intent']}"
                )

            result.explanations = explanations

        return results


class HybridRetrievalPipeline(AdvancedRetrievalPipeline):
    """
    Hybrid retrieval pipeline.

    Combines multiple retrieval strategies.
    """

    def __init__(
        self,
        config: Optional[RetrievalConfig] = None,
        dense_indices: Optional[Dict[str, BaseVectorIndex]] = None,
        sparse_indices: Optional[Dict[str, BaseVectorIndex]] = None,
        fusion_weights: Optional[Dict[str, float]] = None,
        **kwargs: Any,
    ):
        """Initialize the hybrid retrieval pipeline."""
        # Combine all indices
        all_indices = {}
        if dense_indices:
            all_indices.update({f"dense_{k}": v for k, v in dense_indices.items()})
        if sparse_indices:
            all_indices.update({f"sparse_{k}": v for k, v in sparse_indices.items()})

        super().__init__(config, all_indices, **kwargs)

        self.dense_indices = dense_indices or {}
        self.sparse_indices = sparse_indices or {}

        # Default fusion weights
        self.fusion_weights = fusion_weights or {"dense": 0.7, "sparse": 0.3}

    async def _retrieve_from_indices(
        self, query_context: QueryContext
    ) -> List[RetrievalResult]:
        """Retrieve from dense and sparse indices separately."""
        dense_results = []
        sparse_results = []

        # Dense retrieval
        for index_name, index in self.dense_indices.items():
            try:
                search_results = index.search(
                    query_context.query,
                    top_k=self.config.retrieval_top_k,
                    filters=query_context.filters,
                )

                for rank, (doc, score) in enumerate(search_results):
                    result = RetrievalResult(
                        document=doc,
                        score=score * self.fusion_weights.get("dense", 0.7),
                        rank=rank,
                        retrieval_score=score,
                        final_score=score * self.fusion_weights.get("dense", 0.7),
                        source_index=f"dense_{index_name}",
                        pipeline_stages=[PipelineStage.RETRIEVAL],
                    )
                    result.explanations["retrieval_type"] = "dense"
                    dense_results.append(result)

            except (ValueError, AttributeError) as e:
                self.logger.error("Dense retrieval failed for %s: %s", index_name, e)

        # Sparse retrieval (typically with less expanded query)
        sparse_query = query_context.original_query
        for index_name, index in self.sparse_indices.items():
            try:
                search_results = index.search(
                    sparse_query,
                    top_k=self.config.retrieval_top_k,
                    filters=query_context.filters,
                )

                for rank, (doc, score) in enumerate(search_results):
                    result = RetrievalResult(
                        document=doc,
                        score=score * self.fusion_weights.get("sparse", 0.3),
                        rank=rank,
                        retrieval_score=score,
                        final_score=score * self.fusion_weights.get("sparse", 0.3),
                        source_index=f"sparse_{index_name}",
                        pipeline_stages=[PipelineStage.RETRIEVAL],
                    )
                    result.explanations["retrieval_type"] = "sparse"
                    sparse_results.append(result)

            except (ValueError, AttributeError) as e:
                self.logger.error("Sparse retrieval failed for %s: %s", index_name, e)

        # Merge results
        merged_results = self._merge_results(dense_results, sparse_results)

        return merged_results

    def _merge_results(
        self,
        dense_results: List[RetrievalResult],
        sparse_results: List[RetrievalResult],
    ) -> List[RetrievalResult]:
        """Merge dense and sparse results."""
        # Group by document ID
        doc_results = defaultdict(list)

        for result in dense_results + sparse_results:
            doc_id = result.document.doc_id or result.document.id_
            doc_results[doc_id].append(result)

        # Combine scores for same documents
        merged = []
        for _, results in doc_results.items():
            if len(results) == 1:
                merged.append(results[0])
            else:
                # Combine scores
                combined_score = sum(r.score for r in results)

                # Use the first result as base
                merged_result = results[0]
                merged_result.score = combined_score
                merged_result.final_score = combined_score

                # Note fusion in explanations
                merged_result.explanations["fusion"] = (
                    f"Combined {len(results)} results"
                )
                merged_result.explanations["fusion_scores"] = [r.score for r in results]

                merged.append(merged_result)

        return merged


class MultiStageRetrievalPipeline(RetrievalPipeline):
    """
    Multi-stage retrieval pipeline.

    Uses different strategies for each stage.
    """

    def __init__(
        self,
        config: Optional[RetrievalConfig] = None,
        first_stage_indices: Optional[Dict[str, BaseVectorIndex]] = None,
        second_stage_indices: Optional[Dict[str, BaseVectorIndex]] = None,
        first_stage_k: int = 100,
        query_processor: Optional[QueryProcessor] = None,
    ):
        """Initialize multi-stage retrieval pipeline."""
        all_indices = {}
        if first_stage_indices:
            all_indices.update(first_stage_indices)
        if second_stage_indices:
            all_indices.update(second_stage_indices)

        super().__init__(config, all_indices)

        self.first_stage_indices = first_stage_indices or {}
        self.second_stage_indices = second_stage_indices or {}
        self.first_stage_k = first_stage_k
        self.query_processor = query_processor or QueryProcessor()

    async def retrieve(self, query_context: QueryContext) -> List[RetrievalResult]:
        """Multi-stage retrieval."""
        start_time = time.time()

        try:
            # Process query
            query_context = await self.query_processor.process(query_context)

            # Stage 1: Fast retrieval of candidates
            candidates = await self._first_stage_retrieval(query_context)

            if not candidates:
                return []

            # Stage 2: Detailed reranking of candidates
            results = await self._second_stage_retrieval(query_context, candidates)

            # Sort and limit
            results.sort(key=lambda r: r.final_score, reverse=True)
            results = results[: query_context.top_k]

            # Record metrics
            elapsed_ms = (time.time() - start_time) * 1000
            self._record_metrics(elapsed_ms, len(results))

            return results

        except (ValueError, AttributeError) as e:
            self.logger.error("Multi-stage retrieval failed: %s", e)
            return []

    async def _first_stage_retrieval(
        self, query_context: QueryContext
    ) -> List[RetrievalResult]:
        """Fast first-stage retrieval."""
        candidates = []

        for index_name, index in self.first_stage_indices.items():
            try:
                # Use simpler query for speed
                search_results = index.search(
                    query_context.original_query,
                    top_k=self.first_stage_k,
                    filters=query_context.filters,
                )

                for rank, (doc, score) in enumerate(search_results):
                    result = RetrievalResult(
                        document=doc,
                        score=score,
                        rank=rank,
                        retrieval_score=score,
                        source_index=index_name,
                        pipeline_stages=[PipelineStage.RETRIEVAL],
                    )
                    result.explanations["stage"] = "first_stage"
                    candidates.append(result)

            except (ValueError, AttributeError) as e:
                self.logger.error("First stage retrieval failed: %s", e)

        return candidates

    async def _second_stage_retrieval(
        self, query_context: QueryContext, candidates: List[RetrievalResult]
    ) -> List[RetrievalResult]:
        """Detailed second-stage reranking."""
        # Extract candidate documents
        _ = [
            r.document for r in candidates
        ]  # candidate_docs - placeholder for future use

        # Create mini-index or use existing second stage indices
        results = []

        # Use query_context to determine reranking parameters
        boost_factor = 1.2 if query_context.urgency_level > 3 else 1.1

        for _, _ in self.second_stage_indices.items():
            try:
                # In practice, you might create a temporary index
                # or use a reranking model here

                # For now, re-score candidates with expanded query
                for candidate in candidates:
                    # This is simplified - in production, use proper reranking
                    new_score = (
                        candidate.score * boost_factor
                    )  # Use dynamic boost factor

                    result = RetrievalResult(
                        document=candidate.document,
                        score=new_score,
                        rank=candidate.rank,
                        retrieval_score=candidate.retrieval_score,
                        rerank_score=new_score,
                        final_score=new_score,
                        source_index=candidate.source_index,
                        pipeline_stages=candidate.pipeline_stages
                        + [PipelineStage.RERANKING],
                    )
                    result.explanations["stage"] = "second_stage"
                    results.append(result)

            except (ValueError, AttributeError) as e:
                self.logger.error("Second stage retrieval failed: %s", e)

        return results if results else candidates


class FederatedRetrievalPipeline(RetrievalPipeline):
    """Federated retrieval across multiple independent pipelines."""

    def __init__(
        self,
        config: Optional[RetrievalConfig] = None,
        sub_pipelines: Optional[Dict[str, RetrievalPipeline]] = None,
    ):
        """Initialize federated retrieval pipeline."""
        super().__init__(config)
        self.sub_pipelines = sub_pipelines or {}

    async def retrieve(self, query_context: QueryContext) -> List[RetrievalResult]:
        """Federated retrieval from all sub-pipelines."""
        start_time = time.time()

        try:
            # Run all sub-pipelines in parallel
            tasks = []
            pipeline_names = []

            for name, pipeline in self.sub_pipelines.items():
                task = pipeline.retrieve(query_context)
                tasks.append(task)
                pipeline_names.append(name)

            # Wait for all results
            all_results = await asyncio.gather(*tasks, return_exceptions=True)

            # Merge results
            merged_results = []
            for name, results in zip(pipeline_names, all_results):
                if isinstance(results, Exception):
                    self.logger.error("Pipeline %s failed: %s", name, results)
                    continue

                # Add source pipeline to results
                # Type narrowing - results is List[RetrievalResult] here
                if isinstance(results, list):
                    for result in results:
                        result.explanations["source_pipeline"] = name
                        merged_results.append(result)

            # Sort by score
            merged_results.sort(key=lambda r: r.final_score, reverse=True)

            # Deduplicate if needed
            if self.config.filter_duplicates:
                merged_results = self._deduplicate_results(merged_results)

            # Limit results
            merged_results = merged_results[: query_context.top_k]

            # Record metrics
            elapsed_ms = (time.time() - start_time) * 1000
            self._record_metrics(elapsed_ms, len(merged_results))

            return merged_results

        except (ValueError, AttributeError) as e:
            self.logger.error("Federated retrieval failed: %s", e)
            return []

    def _deduplicate_results(
        self, results: List[RetrievalResult]
    ) -> List[RetrievalResult]:
        """Remove duplicate documents, keeping highest score."""
        seen_docs = {}
        deduplicated = []

        for result in results:
            doc_id = result.document.doc_id or result.document.id_

            if doc_id not in seen_docs:
                seen_docs[doc_id] = result
                deduplicated.append(result)
            else:
                # Keep the one with higher score
                if result.final_score > seen_docs[doc_id].final_score:
                    # Remove old one and add new one
                    deduplicated.remove(seen_docs[doc_id])
                    deduplicated.append(result)
                    seen_docs[doc_id] = result

        return deduplicated

    def add_pipeline(self, name: str, pipeline: RetrievalPipeline) -> None:
        """Add a sub-pipeline."""
        self.sub_pipelines[name] = pipeline
        self.logger.info("Added sub-pipeline: %s", name)

    def remove_pipeline(self, name: str) -> None:
        """Remove a sub-pipeline."""
        if name in self.sub_pipelines:
            del self.sub_pipelines[name]
            self.logger.info("Removed sub-pipeline: %s", name)
