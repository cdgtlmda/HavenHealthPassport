"""Result Processing Module.

Handles post-processing, filtering, and aggregation of retrieval results.
"""

import logging
from collections import defaultdict
from typing import Any, Callable, Dict, List, Optional, Set

import numpy as np

from .base import PipelineComponent, RetrievalResult

logger = logging.getLogger(__name__)


class ResultProcessor(PipelineComponent):
    """Base result processor.

    Handles post-processing of retrieval results.
    """

    def __init__(self, name: str = "result_processor"):
        """Initialize the result processor."""
        super().__init__(name)

    async def process(self, input_data: List[RetrievalResult]) -> List[RetrievalResult]:
        """Process results."""
        # Default implementation - override in subclasses
        return input_data

    def deduplicate(
        self, results: List[RetrievalResult], similarity_threshold: float = 0.9
    ) -> List[RetrievalResult]:
        """Remove duplicate or near-duplicate results."""
        if len(results) <= 1:
            return results

        unique_results = []
        seen_texts: List[str] = []

        for result in results:
            # Simple text similarity check
            is_duplicate = False

            for seen_text in seen_texts:
                similarity = self._text_similarity(result.document.text, seen_text)
                if similarity > similarity_threshold:
                    is_duplicate = True
                    break

            if not is_duplicate:
                unique_results.append(result)
                seen_texts.append(result.document.text)

        return unique_results

    def _text_similarity(self, text1: str, text2: str) -> float:
        """Calculate simple text similarity."""
        # In production, use proper similarity metrics
        if text1 == text2:
            return 1.0

        # Jaccard similarity on words
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())

        if not words1 or not words2:
            return 0.0

        intersection = len(words1.intersection(words2))
        union = len(words1.union(words2))

        return intersection / union if union > 0 else 0.0


class ResultFilter(ResultProcessor):
    """Result filtering component.

    Applies various filters to results.
    """

    def __init__(
        self,
        name: str = "result_filter",
        min_score: float = 0.0,
        max_results: Optional[int] = None,
        required_metadata: Optional[Dict[str, Any]] = None,
        custom_filters: Optional[List[Callable]] = None,
    ):
        """Initialize the result filter."""
        super().__init__(name)
        self.min_score = min_score
        self.max_results = max_results
        self.required_metadata = required_metadata or {}
        self.custom_filters = custom_filters or []

    async def process(self, input_data: List[RetrievalResult]) -> List[RetrievalResult]:
        """Apply filters to results."""
        filtered = input_data

        # Score filter
        if self.min_score > 0:
            filtered = [r for r in filtered if r.final_score >= self.min_score]

        # Metadata filters
        if self.required_metadata:
            filtered = self._filter_by_metadata(filtered)

        # Custom filters
        for custom_filter in self.custom_filters:
            filtered = [r for r in filtered if custom_filter(r)]

        # Limit results
        if self.max_results and len(filtered) > self.max_results:
            filtered = filtered[: self.max_results]

        return filtered

    def _filter_by_metadata(
        self, results: List[RetrievalResult]
    ) -> List[RetrievalResult]:
        """Filter results by required metadata."""
        filtered = []

        for result in results:
            match = True

            for key, required_value in self.required_metadata.items():
                doc_value = result.document.metadata.get(key)

                if isinstance(required_value, list):
                    # Value should be in list
                    if doc_value not in required_value:
                        match = False
                        break
                elif callable(required_value):
                    # Custom comparison function
                    if not required_value(doc_value):
                        match = False
                        break
                else:
                    # Exact match
                    if doc_value != required_value:
                        match = False
                        break

            if match:
                filtered.append(result)

        return filtered


class ResultAggregator(ResultProcessor):
    """Result aggregation component.

    Aggregates results from multiple sources.
    """

    def __init__(
        self,
        name: str = "result_aggregator",
        aggregation_method: str = "weighted_sum",  # weighted_sum, max, vote
        source_weights: Optional[Dict[str, float]] = None,
    ):
        """Initialize the result aggregator."""
        super().__init__(name)
        self.aggregation_method = aggregation_method
        self.source_weights = source_weights or {}
        self.default_weight = 1.0

    async def process(self, input_data: List[RetrievalResult]) -> List[RetrievalResult]:
        """Aggregate results by document."""
        # Group by document ID
        doc_groups = defaultdict(list)

        for result in input_data:
            doc_id = result.document.doc_id or result.document.id_
            doc_groups[doc_id].append(result)

        # Aggregate each group
        aggregated = []

        for _doc_id, group in doc_groups.items():
            if len(group) == 1:
                aggregated.append(group[0])
            else:
                merged_result = self._aggregate_group(group)
                aggregated.append(merged_result)

        # Sort by aggregated score
        aggregated.sort(key=lambda r: r.final_score, reverse=True)

        return aggregated

    def _aggregate_group(self, group: List[RetrievalResult]) -> RetrievalResult:
        """Aggregate a group of results for the same document."""
        if self.aggregation_method == "weighted_sum":
            return self._weighted_sum_aggregation(group)
        elif self.aggregation_method == "max":
            return self._max_aggregation(group)
        elif self.aggregation_method == "vote":
            return self._vote_aggregation(group)
        else:
            # Default to first result
            return group[0]

    def _weighted_sum_aggregation(
        self, group: List[RetrievalResult]
    ) -> RetrievalResult:
        """Weighted sum aggregation."""
        # Use first result as base
        merged = group[0]

        # Calculate weighted sum
        total_score = 0.0
        total_weight = 0.0

        for result in group:
            source = result.source_index or "unknown"
            weight = self.source_weights.get(source, self.default_weight)

            total_score += result.final_score * weight
            total_weight += weight

        # Update score
        merged.final_score = total_score / total_weight if total_weight > 0 else 0.0

        # Update explanations
        merged.explanations["aggregation"] = {
            "method": "weighted_sum",
            "sources": len(group),
            "weights": {
                r.source_index: self.source_weights.get(
                    r.source_index, self.default_weight
                )
                for r in group
                if r.source_index is not None
            },
        }

        return merged

    def _max_aggregation(self, group: List[RetrievalResult]) -> RetrievalResult:
        """Max score aggregation."""
        # Return result with highest score
        best_result = max(group, key=lambda r: r.final_score)

        # Update explanations
        best_result.explanations["aggregation"] = {
            "method": "max",
            "sources": len(group),
            "scores": [r.final_score for r in group],
        }

        return best_result

    def _vote_aggregation(self, group: List[RetrievalResult]) -> RetrievalResult:
        """Voting-based aggregation."""
        # Use first result as base
        merged = group[0]

        # Count votes (appearances) with weights
        vote_score = 0.0

        for result in group:
            source = result.source_index or "unknown"
            weight = self.source_weights.get(source, self.default_weight)
            vote_score += weight

        # Normalize by maximum possible votes
        max_votes = (
            sum(self.source_weights.values()) if self.source_weights else len(group)
        )
        merged.final_score = vote_score / max_votes

        # Update explanations
        merged.explanations["aggregation"] = {
            "method": "vote",
            "votes": len(group),
            "vote_score": vote_score,
            "max_votes": max_votes,
        }

        return merged


class ResultExplainer(ResultProcessor):
    """Result explanation component.

    Generates detailed explanations for results.
    """

    def __init__(
        self,
        name: str = "result_explainer",
        explain_scoring: bool = True,
        explain_matching: bool = True,
        explain_ranking: bool = True,
        include_snippets: bool = True,
        snippet_length: int = 200,
    ):
        """Initialize the result explainer."""
        super().__init__(name)
        self.explain_scoring = explain_scoring
        self.explain_matching = explain_matching
        self.explain_ranking = explain_ranking
        self.include_snippets = include_snippets
        self.snippet_length = snippet_length

    async def process(self, input_data: List[RetrievalResult]) -> List[RetrievalResult]:
        """Add explanations to results."""
        # Add rank-based explanations
        for i, result in enumerate(input_data):
            if self.explain_ranking:
                result.explanations["rank"] = {
                    "position": i + 1,
                    "total_results": len(input_data),
                    "percentile": (len(input_data) - i) / len(input_data) * 100,
                }

            if self.explain_scoring:
                self._explain_scoring(result)

            if self.explain_matching:
                self._explain_matching(result)

            if self.include_snippets:
                self._add_snippet(result)

        return input_data

    def _explain_scoring(self, result: RetrievalResult) -> None:
        """Explain how the score was calculated."""
        explanation: Dict[str, Any] = {
            "base_score": result.retrieval_score,
            "final_score": result.final_score,
            "score_components": [],
        }

        # Add component scores
        if result.retrieval_score != result.final_score:
            if result.rerank_score > 0:
                explanation["score_components"].append(
                    {
                        "component": "reranking",
                        "contribution": result.rerank_score - result.retrieval_score,
                    }
                )

            if "medical_relevance_boost" in result.explanations:
                explanation["score_components"].append(
                    {
                        "component": "medical_relevance",
                        "contribution": result.explanations["medical_relevance_boost"]
                        - 1.0,
                    }
                )

        result.explanations["scoring"] = explanation

    def _explain_matching(self, result: RetrievalResult) -> None:
        """Explain what matched in the document."""
        if not result.matched_terms:
            return

        explanation = {
            "matched_terms": result.matched_terms,
            "match_count": len(result.matched_terms),
            "match_density": len(result.matched_terms)
            / len(result.document.text.split()),
        }

        # Highlight matching sections
        highlights = []
        doc_text = result.document.text.lower()

        for term in result.matched_terms[:5]:  # Top 5 terms
            term_lower = term.lower()
            if term_lower in doc_text:
                # Find context around term
                index = doc_text.find(term_lower)
                start = max(0, index - 50)
                end = min(len(doc_text), index + len(term_lower) + 50)

                highlight = result.document.text[start:end]
                if start > 0:
                    highlight = "..." + highlight
                if end < len(doc_text):
                    highlight = highlight + "..."

                highlights.append({"term": term, "context": highlight})

        explanation["highlights"] = highlights
        result.explanations["matching"] = explanation

    def _add_snippet(self, result: RetrievalResult) -> None:
        """Add relevant snippet from document."""
        text = result.document.text

        if len(text) <= self.snippet_length:
            snippet = text
        else:
            # Try to find most relevant section
            if result.matched_terms:
                # Find section with most matched terms
                words = text.split()
                best_start = 0
                best_score = 0

                for i in range(len(words) - 20):  # 20-word windows
                    window = " ".join(words[i : i + 20]).lower()
                    score = sum(
                        1 for term in result.matched_terms if term.lower() in window
                    )

                    if score > best_score:
                        best_score = score
                        best_start = i

                # Extract snippet around best section
                snippet_words = words[best_start : best_start + 30]
                snippet = " ".join(snippet_words)

                if best_start > 0:
                    snippet = "..." + snippet
                if best_start + 30 < len(words):
                    snippet = snippet + "..."
            else:
                # Use beginning of document
                snippet = text[: self.snippet_length] + "..."

        result.explanations["snippet"] = snippet


class DiversityEnhancer(ResultProcessor):
    """Enhance result diversity.

    Ensures diverse results are returned.
    """

    def __init__(
        self,
        name: str = "diversity_enhancer",
        diversity_weight: float = 0.3,
        aspect_fields: Optional[List[str]] = None,
    ):
        """Initialize the diversity enhancer."""
        super().__init__(name)
        self.diversity_weight = diversity_weight
        self.aspect_fields = aspect_fields or ["source", "type", "specialty", "date"]

    async def process(self, input_data: List[RetrievalResult]) -> List[RetrievalResult]:
        """Enhance diversity of results."""
        if len(input_data) <= 2:
            return input_data

        # Track seen aspects
        seen_aspects: Dict[str, Set[str]] = defaultdict(set)
        diverse_results: List[RetrievalResult] = []
        remaining_results = input_data.copy()

        # Iteratively select diverse results
        while remaining_results and len(diverse_results) < len(input_data):
            best_result = None
            best_diversity_score = -1.0

            for result in remaining_results:
                # Calculate diversity score
                diversity_score = self._calculate_diversity_score(result, seen_aspects)

                # Combine with relevance score
                combined_score = (
                    1 - self.diversity_weight
                ) * result.final_score + self.diversity_weight * diversity_score

                if combined_score > best_diversity_score:
                    best_diversity_score = combined_score
                    best_result = result

            if best_result:
                diverse_results.append(best_result)
                remaining_results.remove(best_result)

                # Update seen aspects
                for field in self.aspect_fields:
                    value = best_result.document.metadata.get(field)
                    if value:
                        seen_aspects[field].add(value)

        return diverse_results

    def _calculate_diversity_score(
        self, result: RetrievalResult, seen_aspects: Dict[str, Set[Any]]
    ) -> float:
        """Calculate diversity score for a result."""
        if not seen_aspects:
            return 1.0

        novelty_scores = []

        for field in self.aspect_fields:
            value = result.document.metadata.get(field)
            if value:
                if value not in seen_aspects[field]:
                    novelty_scores.append(1.0)
                else:
                    novelty_scores.append(0.0)

        if novelty_scores:
            return float(np.mean(novelty_scores))
        else:
            return 0.5  # Neutral score if no aspects
