"""LlamaIndex Dimension Selection Module.

Provides intelligent dimension selection for embeddings based on
use case, performance requirements, and storage constraints.
"""

from .optimizer import DimensionOptimizer, OptimizationStrategy, optimize_dimensions
from .profiler import (
    DimensionProfiler,
    estimate_storage_requirements,
    profile_dimension_performance,
)
from .reducer import DimensionReducer, ReductionMethod, reduce_embedding_dimension
from .selector import (
    DimensionConfig,
    DimensionRecommendation,
    DimensionSelector,
    SelectionCriteria,
)
from .validator import (
    DimensionValidator,
    check_vector_store_compatibility,
    validate_dimension_compatibility,
)

__all__ = [
    "DimensionSelector",
    "DimensionConfig",
    "SelectionCriteria",
    "DimensionRecommendation",
    "DimensionOptimizer",
    "OptimizationStrategy",
    "optimize_dimensions",
    "DimensionValidator",
    "validate_dimension_compatibility",
    "check_vector_store_compatibility",
    "DimensionReducer",
    "ReductionMethod",
    "reduce_embedding_dimension",
    "DimensionProfiler",
    "profile_dimension_performance",
    "estimate_storage_requirements",
]
