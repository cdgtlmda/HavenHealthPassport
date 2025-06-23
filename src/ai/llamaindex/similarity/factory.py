"""Similarity Factory.

Provides factory methods for creating similarity scorers.
"""

import logging
from typing import Any, Dict, List, Optional, Type, Union

from .base import BaseSimilarityScorer, SimilarityConfig, SimilarityMetric
from .hybrid import (
    EnsembleSimilarityScorer,
    HybridSimilarityConfig,
    HybridSimilarityScorer,
)
from .medical import (
    ClinicalRelevanceScorer,
    MedicalSimilarityConfig,
    MedicalSimilarityScorer,
    SemanticMedicalSimilarity,
)
from .metrics import (
    CosineSimilarity,
    DotProductSimilarity,
    EuclideanDistance,
    JaccardSimilarity,
    ManhattanDistance,
)
from .reranking import ReRanker

logger = logging.getLogger(__name__)


class SimilarityFactory:
    """Factory for creating similarity scorers."""

    # Metric to scorer mapping
    METRIC_SCORERS: Dict[SimilarityMetric, Type[BaseSimilarityScorer]] = {
        SimilarityMetric.COSINE: CosineSimilarity,
        SimilarityMetric.EUCLIDEAN: EuclideanDistance,
        SimilarityMetric.DOT_PRODUCT: DotProductSimilarity,
        SimilarityMetric.MANHATTAN: ManhattanDistance,
        SimilarityMetric.JACCARD: JaccardSimilarity,
        SimilarityMetric.MEDICAL: MedicalSimilarityScorer,
        SimilarityMetric.HYBRID: HybridSimilarityScorer,
    }

    @staticmethod
    def create_scorer(
        metric: Union[str, SimilarityMetric],
        config: Optional[SimilarityConfig] = None,
        **kwargs: Any,
    ) -> BaseSimilarityScorer:
        """Create a similarity scorer.

        Args:
            metric: Similarity metric to use
            config: Optional configuration
            **kwargs: Additional scorer-specific arguments

        Returns:
            Configured similarity scorer
        """
        # Convert string to enum if needed
        if isinstance(metric, str):
            metric = SimilarityMetric(metric)

        # Get scorer class
        if metric not in SimilarityFactory.METRIC_SCORERS:
            raise ValueError(f"Unknown similarity metric: {metric}")

        scorer_class = SimilarityFactory.METRIC_SCORERS[metric]

        # Create appropriate config if not provided
        if config is None:
            if metric == SimilarityMetric.MEDICAL:
                config = MedicalSimilarityConfig()
            elif metric == SimilarityMetric.HYBRID:
                config = HybridSimilarityConfig()
            else:
                config = SimilarityConfig(metric=metric)

        # Create scorer
        return scorer_class(config=config, **kwargs)

    @staticmethod
    def create_medical_scorer(
        scorer_type: str = "general",
        config: Optional[MedicalSimilarityConfig] = None,
        **kwargs: Any,
    ) -> BaseSimilarityScorer:
        """Create a medical similarity scorer.

        Args:
            scorer_type: Type of medical scorer (general, clinical, semantic)
            config: Optional configuration
            **kwargs: Additional arguments

        Returns:
            Medical similarity scorer
        """
        medical_scorers = {
            "general": MedicalSimilarityScorer,
            "clinical": ClinicalRelevanceScorer,
            "semantic": SemanticMedicalSimilarity,
        }

        if scorer_type not in medical_scorers:
            raise ValueError(f"Unknown medical scorer type: {scorer_type}")

        scorer_class = medical_scorers[scorer_type]

        if config is None:
            config = MedicalSimilarityConfig()

        return scorer_class(config=config, **kwargs)

    @staticmethod
    def create_hybrid_scorer(
        base_metrics: Optional[List[str]] = None,
        weights: Optional[List[float]] = None,
        config: Optional[HybridSimilarityConfig] = None,
        **kwargs: Any,
    ) -> HybridSimilarityScorer:
        """Create a hybrid similarity scorer.

        Args:
            base_metrics: List of base metrics to combine
            weights: Weights for each metric
            config: Optional configuration
            **kwargs: Additional arguments

        Returns:
            Hybrid similarity scorer
        """
        if base_metrics is None:
            base_metrics = ["cosine", "euclidean"]

        if weights is None:
            weights = [1.0 / len(base_metrics)] * len(base_metrics)

        if config is None:
            config = HybridSimilarityConfig(
                base_scorers=base_metrics, scorer_weights=weights
            )

        # Create base scorers
        scorers = []
        for metric in base_metrics:
            scorer = SimilarityFactory.create_scorer(metric)
            scorers.append(scorer)

        return HybridSimilarityScorer(config=config, scorers=scorers, **kwargs)

    @staticmethod
    def create_ensemble_scorer(
        base_metrics: Optional[List[str]] = None,
        ensemble_method: str = "voting",
        config: Optional[HybridSimilarityConfig] = None,
        **kwargs: Any,
    ) -> EnsembleSimilarityScorer:
        """Create an ensemble similarity scorer.

        Args:
            base_metrics: List of base metrics
            ensemble_method: Ensemble method (voting, stacking)
            config: Optional configuration
            **kwargs: Additional arguments

        Returns:
            Ensemble similarity scorer
        """
        if base_metrics is None:
            base_metrics = ["cosine", "medical", "dot_product"]

        if config is None:
            config = HybridSimilarityConfig(
                base_scorers=base_metrics, aggregation_method=ensemble_method
            )

        # Create base scorers
        scorers = []
        for metric in base_metrics:
            if metric == "medical":
                scorer = SimilarityFactory.create_medical_scorer()
            else:
                scorer = SimilarityFactory.create_scorer(metric)
            scorers.append(scorer)

        return EnsembleSimilarityScorer(
            config=config, scorers=scorers, ensemble_method=ensemble_method, **kwargs
        )


def get_similarity_scorer(
    use_case: str = "general", **kwargs: Any
) -> BaseSimilarityScorer:
    """Get similarity scorer for specific use case.

    Args:
        use_case: Use case identifier
        **kwargs: Additional arguments

    Returns:
        Configured similarity scorer
    """
    use_case_configs = {
        "general": {
            "metric": SimilarityMetric.COSINE,
            "normalize_scores": True,
        },
        "medical": {
            "metric": SimilarityMetric.MEDICAL,
            "boost_medical_terms": True,
            "use_cui_matching": True,
        },
        "clinical": {
            "scorer_type": "clinical",
            "consider_clinical_context": True,
            "urgency_boost_factor": 3.0,
        },
        "multilingual": {
            "metric": SimilarityMetric.COSINE,
            "consider_metadata": True,
            "use_multilingual_medical": True,
        },
        "high_precision": {
            "base_metrics": ["cosine", "dot_product", "medical"],
            "weights": [0.4, 0.3, 0.3],
            "enable_reranking": True,
        },
        "fast": {
            "metric": SimilarityMetric.DOT_PRODUCT,
            "normalize_scores": False,
            "use_approximate_search": True,
        },
        "research": {
            "base_metrics": ["cosine", "euclidean", "manhattan"],
            "ensemble_method": "stacking",
            "normalize_before_aggregation": True,
        },
    }

    if use_case not in use_case_configs:
        raise ValueError(
            f"Unknown use case: {use_case}. Choose from: {list(use_case_configs.keys())}"
        )

    # Get use case configuration
    use_case_config = use_case_configs[use_case]

    # Merge with provided kwargs
    merged_config = {**use_case_config, **kwargs}

    # Determine scorer type
    if "base_metrics" in merged_config:
        # Hybrid or ensemble scorer
        if "ensemble_method" in merged_config:
            return SimilarityFactory.create_ensemble_scorer(**merged_config)
        else:
            return SimilarityFactory.create_hybrid_scorer(**merged_config)

    elif "scorer_type" in merged_config:
        # Medical scorer variant
        return SimilarityFactory.create_medical_scorer(**merged_config)

    else:
        # Single metric scorer
        metric = merged_config.pop("metric", SimilarityMetric.COSINE)
        config = SimilarityConfig(**merged_config)
        return SimilarityFactory.create_scorer(metric, config)


def create_similarity_pipeline(
    scorer: BaseSimilarityScorer,
    reranker: Optional[ReRanker] = None,
    min_score_threshold: float = 0.0,
) -> Dict[str, Any]:
    """Create a complete similarity scoring pipeline.

    Args:
        scorer: Primary similarity scorer
        reranker: Optional re-ranker
        min_score_threshold: Minimum score threshold

    Returns:
        Pipeline configuration
    """
    pipeline = {
        "scorer": scorer,
        "reranker": reranker,
        "min_score_threshold": min_score_threshold,
        "stats": {
            "scorer_type": type(scorer).__name__,
            "reranker_type": type(reranker).__name__ if reranker else None,
            "config": scorer.get_stats(),
        },
    }

    return pipeline
