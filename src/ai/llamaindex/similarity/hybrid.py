"""Hybrid Similarity Scoring.

Combines multiple similarity metrics for improved performance.
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Union

import numpy as np

from .base import BaseSimilarityScorer, SimilarityConfig
from .metrics import CosineSimilarity, DotProductSimilarity, EuclideanDistance

logger = logging.getLogger(__name__)


@dataclass
class HybridSimilarityConfig(SimilarityConfig):
    """Configuration for hybrid similarity scoring."""

    base_scorers: List[str] = field(default_factory=lambda: ["cosine", "euclidean"])
    scorer_weights: List[float] = field(default_factory=lambda: [0.7, 0.3])
    aggregation_method: str = "weighted_mean"  # weighted_mean, max, min, harmonic_mean
    normalize_before_aggregation: bool = True
    use_adaptive_weights: bool = False


class HybridSimilarityScorer(BaseSimilarityScorer):
    """Combines multiple similarity metrics.

    Allows flexible combination of different similarity measures.
    """

    def __init__(
        self,
        config: Optional[HybridSimilarityConfig] = None,
        scorers: Optional[List[BaseSimilarityScorer]] = None,
    ):
        """Initialize the hybrid similarity scorer."""
        if config is None:
            config = HybridSimilarityConfig()
        super().__init__(config)

        self.hybrid_config = config
        self.scorers = scorers or self._create_default_scorers()
        self._validate_configuration()

    def _initialize(self) -> None:
        """Initialize scorer-specific components."""

    def _create_default_scorers(self) -> List[BaseSimilarityScorer]:
        """Create default scorers based on configuration."""
        scorer_map = {
            "cosine": CosineSimilarity,
            "euclidean": EuclideanDistance,
            "dot_product": DotProductSimilarity,
        }

        scorers = []
        for scorer_name in self.hybrid_config.base_scorers:
            if scorer_name in scorer_map:
                scorer_class = scorer_map[scorer_name]
                scorer = scorer_class(self.config)  # type: ignore[abstract]
                scorers.append(scorer)
            else:
                logger.warning("Unknown scorer: %s", scorer_name)

        return scorers

    def _validate_configuration(self) -> None:
        """Validate hybrid configuration."""
        if len(self.scorers) != len(self.hybrid_config.scorer_weights):
            # Adjust weights to match number of scorers
            num_scorers = len(self.scorers)
            self.hybrid_config.scorer_weights = [1.0 / num_scorers] * num_scorers
            logger.warning("Adjusted weights to match %d scorers", num_scorers)

    def score(
        self,
        query_embedding: Union[List[float], np.ndarray],
        doc_embedding: Union[List[float], np.ndarray],
        query_metadata: Optional[Dict[str, Any]] = None,
        doc_metadata: Optional[Dict[str, Any]] = None,
    ) -> float:
        """Calculate hybrid similarity score."""
        # Get scores from all base scorers
        scores = []
        for scorer in self.scorers:
            score = scorer.score(
                query_embedding, doc_embedding, query_metadata, doc_metadata
            )
            scores.append(score)

        # Apply adaptive weights if enabled
        if self.hybrid_config.use_adaptive_weights:
            weights = self._calculate_adaptive_weights(
                scores, query_metadata, doc_metadata
            )
        else:
            weights = self.hybrid_config.scorer_weights

        # Aggregate scores
        final_score = self._aggregate_scores(scores, weights)

        return self._apply_threshold(final_score)

    def _aggregate_scores(self, scores: List[float], weights: List[float]) -> float:
        """Aggregate multiple scores based on method."""
        scores_array = np.array(scores)
        weights_array = np.array(weights)

        if self.hybrid_config.aggregation_method == "weighted_mean":
            return float(np.average(scores_array, weights=weights_array))

        elif self.hybrid_config.aggregation_method == "max":
            return float(np.max(scores_array))

        elif self.hybrid_config.aggregation_method == "min":
            return float(np.min(scores_array))

        elif self.hybrid_config.aggregation_method == "harmonic_mean":
            # Weighted harmonic mean
            denominator = np.sum(weights_array / (scores_array + 1e-10))
            return float(np.sum(weights_array) / denominator)

        else:
            logger.warning(
                "Unknown aggregation method: %s", self.hybrid_config.aggregation_method
            )
            return float(np.average(scores_array, weights=weights_array))

    def _calculate_adaptive_weights(
        self,
        scores: List[float],
        _query_metadata: Optional[
            Dict[str, Any]
        ] = None,  # pylint: disable=unused-argument # Reserved for future use
        _doc_metadata: Optional[
            Dict[str, Any]
        ] = None,  # pylint: disable=unused-argument # Reserved for future use
    ) -> List[float]:
        """Calculate adaptive weights based on score distribution."""
        scores_array = np.array(scores)

        # Use score variance to adjust weights
        # Higher variance = more weight to best scorer
        variance = np.var(scores_array)

        if variance > 0.1:  # High variance
            # Give more weight to best performing scorer
            weights = np.exp(scores_array * 2)  # Exponential weighting
        else:  # Low variance
            # Use default weights
            weights = np.array(self.hybrid_config.scorer_weights)

        # Normalize weights
        weights = weights / np.sum(weights)

        return list(weights.tolist())


class WeightedSimilarityScorer(HybridSimilarityScorer):
    """Weighted combination of similarity scorers.

    Allows dynamic weight adjustment based on context.
    """

    def __init__(
        self,
        config: Optional[HybridSimilarityConfig] = None,
        scorers: Optional[List[BaseSimilarityScorer]] = None,
        weight_function: Optional[Callable] = None,
    ):
        """Initialize the weighted similarity scorer."""
        super().__init__(config, scorers)
        self.weight_function = weight_function

    def score(
        self,
        query_embedding: Union[List[float], np.ndarray],
        doc_embedding: Union[List[float], np.ndarray],
        query_metadata: Optional[Dict[str, Any]] = None,
        doc_metadata: Optional[Dict[str, Any]] = None,
    ) -> float:
        """Calculate weighted similarity score."""
        # Calculate weights using custom function if provided
        if self.weight_function:
            weights = self.weight_function(query_metadata, doc_metadata, self.scorers)
        else:
            weights = self._calculate_context_weights(query_metadata, doc_metadata)

        # Get scores from all scorers
        scores = []
        for scorer in self.scorers:
            score = scorer.score(
                query_embedding, doc_embedding, query_metadata, doc_metadata
            )
            scores.append(score)

        # Aggregate with calculated weights
        final_score = self._aggregate_scores(scores, weights)

        return self._apply_threshold(final_score)

    def _calculate_context_weights(
        self,
        query_metadata: Optional[Dict[str, Any]],
        doc_metadata: Optional[Dict[str, Any]],
    ) -> List[float]:
        """Calculate weights based on context."""
        # Default weights
        weights = list(self.hybrid_config.scorer_weights)

        if query_metadata and doc_metadata:
            # Adjust weights based on content type
            content_type = query_metadata.get("content_type", "general")

            if content_type == "medical":
                # Prefer cosine for medical content
                if "cosine" in self.hybrid_config.base_scorers:
                    idx = self.hybrid_config.base_scorers.index("cosine")
                    weights[idx] *= 1.5

            elif content_type == "technical":
                # Prefer dot product for technical content
                if "dot_product" in self.hybrid_config.base_scorers:
                    idx = self.hybrid_config.base_scorers.index("dot_product")
                    weights[idx] *= 1.5

        # Normalize weights
        total = sum(weights)
        return [w / total for w in weights]


class EnsembleSimilarityScorer(HybridSimilarityScorer):
    """Ensemble approach to similarity scoring.

    Uses voting or stacking to combine multiple scorers.
    """

    def __init__(
        self,
        config: Optional[HybridSimilarityConfig] = None,
        scorers: Optional[List[BaseSimilarityScorer]] = None,
        ensemble_method: str = "voting",  # voting, stacking
    ):
        """Initialize the ensemble similarity scorer."""
        super().__init__(config, scorers)
        self.ensemble_method = ensemble_method
        self.threshold_percentile = 75  # For voting

    def score(
        self,
        query_embedding: Union[List[float], np.ndarray],
        doc_embedding: Union[List[float], np.ndarray],
        query_metadata: Optional[Dict[str, Any]] = None,
        doc_metadata: Optional[Dict[str, Any]] = None,
    ) -> float:
        """Calculate ensemble similarity score."""
        # Get scores from all scorers
        scores = []
        for scorer in self.scorers:
            score = scorer.score(
                query_embedding, doc_embedding, query_metadata, doc_metadata
            )
            scores.append(score)

        if self.ensemble_method == "voting":
            return self._voting_ensemble(scores)
        elif self.ensemble_method == "stacking":
            return self._stacking_ensemble(scores, query_metadata, doc_metadata)
        else:
            # Fallback to weighted mean
            return super().score(
                query_embedding, doc_embedding, query_metadata, doc_metadata
            )

    def _voting_ensemble(self, scores: List[float]) -> float:
        """Ensemble by voting on high scores."""
        scores_array = np.array(scores)

        # Calculate threshold
        threshold = np.percentile(scores_array, self.threshold_percentile)

        # Count votes (scores above threshold)
        votes = np.sum(scores_array >= threshold)
        vote_ratio = votes / len(scores_array)

        # Weight by average of high scores
        high_scores = scores_array[scores_array >= threshold]
        if high_scores.size > 0:
            avg_high = np.mean(high_scores)
        else:
            avg_high = np.mean(scores_array)

        # Combine vote ratio and average
        return float(vote_ratio * avg_high)

    def _stacking_ensemble(
        self,
        scores: List[float],
        query_metadata: Optional[Dict[str, Any]],
        doc_metadata: Optional[Dict[str, Any]],
    ) -> float:
        """Ensemble by stacking (meta-learning)."""
        # Create feature vector from scores and metadata
        features = list(scores)

        # Add statistical features
        features.extend(
            [
                float(np.mean(scores)),
                float(np.std(scores)),
                float(np.max(scores)),
                float(np.min(scores)),
                float(np.max(scores) - np.min(scores)),  # Range
            ]
        )

        # Add metadata features
        if query_metadata and doc_metadata:
            # Language match
            lang_match = float(
                query_metadata.get("language") == doc_metadata.get("language")
            )
            features.append(lang_match)

            # Content type match
            type_match = float(
                query_metadata.get("content_type") == doc_metadata.get("content_type")
            )
            features.append(type_match)

        # Simple linear combination (in production, use trained model)
        weights = np.ones(len(features)) / len(features)
        return float(np.dot(features, weights))
