"""Dimension Optimization Strategies.

Provides methods to optimize embedding dimensions for specific requirements.
"""

import logging
from enum import Enum
from typing import Any, Dict, Optional, Tuple

from .selector import DimensionConfig, DimensionSelector, SelectionCriteria, UseCase

logger = logging.getLogger(__name__)


class OptimizationStrategy(str, Enum):
    """Optimization strategies for dimensions."""

    QUALITY_MAXIMIZATION = "quality_maximization"
    STORAGE_MINIMIZATION = "storage_minimization"
    LATENCY_MINIMIZATION = "latency_minimization"
    COST_OPTIMIZATION = "cost_optimization"
    BALANCED = "balanced"


class DimensionOptimizer:
    """Optimizes embedding dimensions for specific goals."""

    @staticmethod
    def optimize_dimensions(
        current_config: DimensionConfig,
        strategy: OptimizationStrategy,
        constraints: Optional[Dict[str, Any]] = None,
    ) -> Tuple[DimensionConfig, Dict[str, Any]]:
        """Optimize dimensions based on strategy.

        Args:
            current_config: Current dimension configuration
            strategy: Optimization strategy
            constraints: Optional constraints

        Returns:
            Optimized config and optimization metrics
        """
        if constraints is None:
            constraints = {}

        optimizer_map = {
            OptimizationStrategy.QUALITY_MAXIMIZATION: DimensionOptimizer._optimize_for_quality,
            OptimizationStrategy.STORAGE_MINIMIZATION: DimensionOptimizer._optimize_for_storage,
            OptimizationStrategy.LATENCY_MINIMIZATION: DimensionOptimizer._optimize_for_latency,
            OptimizationStrategy.COST_OPTIMIZATION: DimensionOptimizer._optimize_for_cost,
            OptimizationStrategy.BALANCED: DimensionOptimizer._optimize_balanced,
        }

        optimizer_func = optimizer_map[strategy]
        return optimizer_func(current_config, constraints)

    @staticmethod
    def _optimize_for_quality(
        config: DimensionConfig, constraints: Dict[str, Any]
    ) -> Tuple[DimensionConfig, Dict[str, Any]]:
        """Optimize for maximum quality."""
        # Get all configs sorted by quality
        all_configs = list(DimensionSelector.DIMENSION_CONFIGS.values())
        quality_sorted = sorted(
            all_configs, key=lambda x: x.quality_score, reverse=True
        )

        # Apply constraints
        max_storage = constraints.get("max_storage_per_vector", float("inf"))
        max_latency = constraints.get("max_latency_ms", float("inf"))

        for candidate in quality_sorted:
            if (
                candidate.storage_per_vector <= max_storage
                and candidate.estimated_performance["latency_ms"] <= max_latency
            ):

                metrics = {
                    "quality_gain": candidate.quality_score - config.quality_score,
                    "storage_increase": candidate.storage_per_vector
                    - config.storage_per_vector,
                    "latency_increase": (
                        candidate.estimated_performance["latency_ms"]
                        - config.estimated_performance["latency_ms"]
                    ),
                }

                return candidate, metrics

        # No better option found
        return config, {"status": "no_improvement_possible"}

    @staticmethod
    def _optimize_for_storage(
        config: DimensionConfig, constraints: Dict[str, Any]
    ) -> Tuple[DimensionConfig, Dict[str, Any]]:
        """Optimize for minimum storage."""
        # Get all configs sorted by storage
        all_configs = list(DimensionSelector.DIMENSION_CONFIGS.values())
        storage_sorted = sorted(all_configs, key=lambda x: x.storage_per_vector)

        # Apply constraints
        min_quality = constraints.get("min_quality_score", 0.7)
        max_latency = constraints.get("max_latency_ms", float("inf"))

        for candidate in storage_sorted:
            if (
                candidate.quality_score >= min_quality
                and candidate.estimated_performance["latency_ms"] <= max_latency
            ):

                metrics = {
                    "storage_reduction": config.storage_per_vector
                    - candidate.storage_per_vector,
                    "storage_reduction_pct": (
                        (config.storage_per_vector - candidate.storage_per_vector)
                        / config.storage_per_vector
                        * 100
                    ),
                    "quality_loss": config.quality_score - candidate.quality_score,
                }

                return candidate, metrics

        return config, {"status": "no_improvement_possible"}

    @staticmethod
    def _optimize_for_latency(
        config: DimensionConfig, constraints: Dict[str, Any]
    ) -> Tuple[DimensionConfig, Dict[str, Any]]:
        """Optimize for minimum latency."""
        # Get all configs sorted by latency
        all_configs = list(DimensionSelector.DIMENSION_CONFIGS.values())
        latency_sorted = sorted(
            all_configs, key=lambda x: x.estimated_performance["latency_ms"]
        )

        min_quality = constraints.get("min_quality_score", 0.7)

        for candidate in latency_sorted:
            if candidate.quality_score >= min_quality:
                metrics = {
                    "latency_reduction": (
                        config.estimated_performance["latency_ms"]
                        - candidate.estimated_performance["latency_ms"]
                    ),
                    "latency_reduction_pct": (
                        (
                            config.estimated_performance["latency_ms"]
                            - candidate.estimated_performance["latency_ms"]
                        )
                        / config.estimated_performance["latency_ms"]
                        * 100
                    ),
                    "quality_loss": config.quality_score - candidate.quality_score,
                }

                return candidate, metrics

        return config, {"status": "no_improvement_possible"}

    @staticmethod
    def _optimize_for_cost(
        config: DimensionConfig, constraints: Dict[str, Any]
    ) -> Tuple[DimensionConfig, Dict[str, Any]]:
        """Optimize for minimum cost (storage + compute)."""
        # Get all configs
        all_configs = list(DimensionSelector.DIMENSION_CONFIGS.values())

        # Calculate cost score (lower is better)
        def cost_score(cfg: DimensionConfig) -> float:
            storage_cost = cfg.storage_per_vector / 1024  # Relative storage cost
            compute_cost = (
                1000 / cfg.estimated_performance["throughput_qps"]
            )  # Relative compute cost
            return storage_cost + compute_cost

        cost_sorted = sorted(all_configs, key=cost_score)

        min_quality = constraints.get("min_quality_score", 0.75)

        for candidate in cost_sorted:
            if candidate.quality_score >= min_quality:
                metrics = {
                    "cost_reduction_estimate": f"{(cost_score(config) - cost_score(candidate)) / cost_score(config) * 100:.1f}%",
                    "storage_savings": config.storage_per_vector
                    - candidate.storage_per_vector,
                    "throughput_gain": (
                        candidate.estimated_performance["throughput_qps"]
                        - config.estimated_performance["throughput_qps"]
                    ),
                }

                return candidate, metrics

        return config, {"status": "no_improvement_possible"}

    @staticmethod
    def _optimize_balanced(
        config: DimensionConfig, constraints: Dict[str, Any]
    ) -> Tuple[DimensionConfig, Dict[str, Any]]:
        """Balanced optimization across all factors."""
        # Create balanced criteria
        criteria = SelectionCriteria(
            use_case=UseCase.SEMANTIC_SEARCH,
            expected_documents=constraints.get("expected_documents", 100000),
        )

        # Use selector for balanced recommendation
        recommendation = DimensionSelector.select_dimensions(criteria)

        metrics = {
            "quality_change": recommendation.primary_config.quality_score
            - config.quality_score,
            "storage_change": recommendation.primary_config.storage_per_vector
            - config.storage_per_vector,
            "latency_change": (
                recommendation.primary_config.estimated_performance["latency_ms"]
                - config.estimated_performance["latency_ms"]
            ),
            "reasoning": recommendation.reasoning,
        }

        return recommendation.primary_config, metrics


def optimize_dimensions(
    current_dimension: int, strategy: str = "balanced", **constraints: Any
) -> Tuple[int, Dict[str, Any]]:
    """Optimize dimensions for current use case.

    Args:
        current_dimension: Current embedding dimension
        strategy: Optimization strategy name
        **constraints: Optimization constraints

    Returns:
        Optimized dimension and metrics
    """
    # Find current config
    current_config = None
    for cfg in DimensionSelector.DIMENSION_CONFIGS.values():
        if cfg.dimension == current_dimension:
            current_config = cfg
            break

    if not current_config:
        # Create a generic config
        current_config = DimensionConfig(
            dimension=current_dimension,
            model_name="unknown",
            provider="unknown",
            estimated_performance={"latency_ms": 50, "throughput_qps": 100},
            storage_per_vector=current_dimension * 4,
            quality_score=0.8,
        )

    # Optimize
    strategy_enum = OptimizationStrategy(strategy)
    optimized_config, metrics = DimensionOptimizer.optimize_dimensions(
        current_config, strategy_enum, constraints
    )

    return optimized_config.dimension, metrics
