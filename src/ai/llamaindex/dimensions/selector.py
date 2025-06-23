"""Dimension Selection Logic for Embeddings.

Intelligently selects appropriate embedding dimensions based on
multiple factors including use case, performance, and storage.
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class UseCase(str, Enum):
    """Embedding use cases."""

    SEMANTIC_SEARCH = "semantic_search"
    DOCUMENT_CLUSTERING = "document_clustering"
    SIMILARITY_MATCHING = "similarity_matching"
    CLASSIFICATION = "classification"
    EMERGENCY_MEDICAL = "emergency_medical"
    RESEARCH_ANALYSIS = "research_analysis"
    REAL_TIME_CHAT = "real_time_chat"
    BATCH_PROCESSING = "batch_processing"


class PerformanceRequirement(str, Enum):
    """Performance requirement levels."""

    ULTRA_LOW_LATENCY = "ultra_low_latency"  # <10ms
    LOW_LATENCY = "low_latency"  # <50ms
    STANDARD = "standard"  # <200ms
    BATCH_OPTIMIZED = "batch_optimized"  # Throughput over latency


class StorageConstraint(str, Enum):
    """Storage constraint levels."""

    MINIMAL = "minimal"  # Optimize for smallest size
    BALANCED = "balanced"  # Balance size and quality
    QUALITY_FIRST = "quality_first"  # Prioritize quality


@dataclass
class SelectionCriteria:
    """Criteria for dimension selection."""

    use_case: UseCase
    performance_requirement: PerformanceRequirement = PerformanceRequirement.STANDARD
    storage_constraint: StorageConstraint = StorageConstraint.BALANCED
    expected_documents: int = 10000
    languages: Optional[List[str]] = None
    medical_accuracy_required: bool = False
    multimodal_support: bool = False

    def __post_init__(self) -> None:
        """Initialize default languages."""
        if self.languages is None:
            self.languages = ["en"]


@dataclass
class DimensionConfig:
    """Configuration for embedding dimensions."""

    dimension: int
    model_name: str
    provider: str
    estimated_performance: Dict[str, float]
    storage_per_vector: float  # in bytes
    quality_score: float  # 0-1 scale
    supports_reduction: bool = False
    reduction_methods: List[str] = field(default_factory=list)


@dataclass
class DimensionRecommendation:
    """Recommendation for embedding dimensions."""

    primary_config: DimensionConfig
    alternative_configs: List[DimensionConfig]
    reasoning: str
    tradeoffs: Dict[str, str]
    estimated_storage_gb: float
    estimated_latency_ms: float


class DimensionSelector:
    """Selects optimal embedding dimensions based on criteria."""

    # Dimension configurations for different models
    DIMENSION_CONFIGS = {
        # AWS Bedrock Titan models
        "titan-embed-v2-1024": DimensionConfig(
            dimension=1024,
            model_name="amazon.titan-embed-text-v2:0",
            provider="bedrock",
            estimated_performance={"latency_ms": 20, "throughput_qps": 100},
            storage_per_vector=4096,  # 1024 * 4 bytes
            quality_score=0.95,
            supports_reduction=False,
        ),
        "titan-embed-g1-384": DimensionConfig(
            dimension=384,
            model_name="amazon.titan-embed-g1-text-02",
            provider="bedrock",
            estimated_performance={"latency_ms": 10, "throughput_qps": 200},
            storage_per_vector=1536,
            quality_score=0.85,
            supports_reduction=False,
        ),
        "titan-embed-v1-1536": DimensionConfig(
            dimension=1536,
            model_name="amazon.titan-embed-text-v1",
            provider="bedrock",
            estimated_performance={"latency_ms": 25, "throughput_qps": 80},
            storage_per_vector=6144,
            quality_score=0.93,
            supports_reduction=False,
        ),
        # OpenAI models
        "openai-3-small-1536": DimensionConfig(
            dimension=1536,
            model_name="text-embedding-3-small",
            provider="openai",
            estimated_performance={"latency_ms": 30, "throughput_qps": 150},
            storage_per_vector=6144,
            quality_score=0.92,
            supports_reduction=True,
            reduction_methods=["truncation", "matryoshka"],
        ),
        "openai-3-large-3072": DimensionConfig(
            dimension=3072,
            model_name="text-embedding-3-large",
            provider="openai",
            estimated_performance={"latency_ms": 40, "throughput_qps": 100},
            storage_per_vector=12288,
            quality_score=0.97,
            supports_reduction=True,
            reduction_methods=["truncation", "matryoshka", "pca"],
        ),
        # Medical models
        "medical-bert-768": DimensionConfig(
            dimension=768,
            model_name="haven-medical-embed",
            provider="medical",
            estimated_performance={"latency_ms": 15, "throughput_qps": 120},
            storage_per_vector=3072,
            quality_score=0.94,
            supports_reduction=True,
            reduction_methods=["pca", "autoencoder"],
        ),
        # Reduced dimensions for performance
        "reduced-512": DimensionConfig(
            dimension=512,
            model_name="custom-reduced",
            provider="custom",
            estimated_performance={"latency_ms": 8, "throughput_qps": 300},
            storage_per_vector=2048,
            quality_score=0.82,
            supports_reduction=False,
        ),
        "minimal-256": DimensionConfig(
            dimension=256,
            model_name="custom-minimal",
            provider="custom",
            estimated_performance={"latency_ms": 5, "throughput_qps": 500},
            storage_per_vector=1024,
            quality_score=0.75,
            supports_reduction=False,
        ),
    }

    @classmethod
    def select_dimensions(cls, criteria: SelectionCriteria) -> DimensionRecommendation:
        """Select optimal dimensions based on criteria.

        Args:
            criteria: Selection criteria

        Returns:
            Dimension recommendation with primary and alternatives
        """
        # Score each configuration
        scored_configs = []
        for _, config in cls.DIMENSION_CONFIGS.items():
            score = cls._score_config(config, criteria)
            scored_configs.append((score, config))

        # Sort by score (highest first)
        scored_configs.sort(key=lambda x: x[0], reverse=True)

        # Get top recommendation
        primary_config = scored_configs[0][1]

        # Get alternatives (next 2 best)
        alternative_configs = [config for _, config in scored_configs[1:3]]

        # Generate reasoning
        reasoning = cls._generate_reasoning(primary_config, criteria)

        # Calculate tradeoffs
        tradeoffs = cls._calculate_tradeoffs(
            primary_config, alternative_configs, criteria
        )

        # Estimate storage and latency
        storage_gb = cls._estimate_storage(primary_config, criteria)
        latency_ms = primary_config.estimated_performance["latency_ms"]

        return DimensionRecommendation(
            primary_config=primary_config,
            alternative_configs=alternative_configs,
            reasoning=reasoning,
            tradeoffs=tradeoffs,
            estimated_storage_gb=storage_gb,
            estimated_latency_ms=latency_ms,
        )

    @classmethod
    def _score_config(
        cls, config: DimensionConfig, criteria: SelectionCriteria
    ) -> float:
        """Score a configuration based on criteria."""
        score = 0.0

        # Quality score weight
        quality_weight = 0.3
        if criteria.use_case in [UseCase.RESEARCH_ANALYSIS, UseCase.CLASSIFICATION]:
            quality_weight = 0.5
        score += config.quality_score * quality_weight

        # Performance score
        perf_score = cls._calculate_performance_score(config, criteria)
        perf_weight = 0.3
        if criteria.performance_requirement == PerformanceRequirement.ULTRA_LOW_LATENCY:
            perf_weight = 0.5
        score += perf_score * perf_weight

        # Storage score
        storage_score = cls._calculate_storage_score(config, criteria)
        storage_weight = 0.2
        if criteria.storage_constraint == StorageConstraint.MINIMAL:
            storage_weight = 0.4
        score += storage_score * storage_weight

        # Use case specific adjustments
        use_case_score = cls._calculate_use_case_score(config, criteria)
        score += use_case_score * 0.2

        return score

    @classmethod
    def _calculate_performance_score(
        cls, config: DimensionConfig, criteria: SelectionCriteria
    ) -> float:
        """Calculate performance score."""
        latency = config.estimated_performance["latency_ms"]

        if criteria.performance_requirement == PerformanceRequirement.ULTRA_LOW_LATENCY:
            if latency <= 10:
                return 1.0
            elif latency <= 20:
                return 0.7
            else:
                return 0.3
        elif criteria.performance_requirement == PerformanceRequirement.LOW_LATENCY:
            if latency <= 20:
                return 1.0
            elif latency <= 50:
                return 0.8
            else:
                return 0.5
        else:  # STANDARD or BATCH_OPTIMIZED
            if latency <= 50:
                return 1.0
            elif latency <= 100:
                return 0.8
            else:
                return 0.6

    @classmethod
    def _calculate_storage_score(
        cls,
        config: DimensionConfig,
        criteria: SelectionCriteria,  # pylint: disable=unused-argument
    ) -> float:
        """Calculate storage efficiency score."""
        bytes_per_vec = config.storage_per_vector

        # Score based on storage per vector
        if bytes_per_vec <= 1024:  # <= 256 dims
            return 1.0
        elif bytes_per_vec <= 2048:  # <= 512 dims
            return 0.9
        elif bytes_per_vec <= 3072:  # <= 768 dims
            return 0.8
        elif bytes_per_vec <= 4096:  # <= 1024 dims
            return 0.7
        elif bytes_per_vec <= 6144:  # <= 1536 dims
            return 0.5
        else:  # > 1536 dims
            return 0.3

    @classmethod
    def _calculate_use_case_score(
        cls, config: DimensionConfig, criteria: SelectionCriteria
    ) -> float:
        """Calculate use case specific score."""
        # Medical use cases prefer medical models
        if criteria.medical_accuracy_required:
            if config.provider == "medical":
                return 1.0
            elif config.dimension >= 768:
                return 0.7
            else:
                return 0.4

        # Emergency cases need fast models
        if criteria.use_case == UseCase.EMERGENCY_MEDICAL:
            if config.estimated_performance["latency_ms"] <= 15:
                return 1.0
            else:
                return 0.5

        # Research needs high quality
        if criteria.use_case == UseCase.RESEARCH_ANALYSIS:
            if config.quality_score >= 0.95:
                return 1.0
            elif config.quality_score >= 0.90:
                return 0.8
            else:
                return 0.5

        # Real-time chat needs balance
        if criteria.use_case == UseCase.REAL_TIME_CHAT:
            if 384 <= config.dimension <= 768:
                return 1.0
            else:
                return 0.7

        return 0.8  # Default score

    @classmethod
    def _generate_reasoning(
        cls, config: DimensionConfig, criteria: SelectionCriteria
    ) -> str:
        """Generate reasoning for the selection."""
        parts = []

        # Base recommendation
        parts.append(
            f"Recommended {config.dimension}-dimensional embeddings "
            f"using {config.model_name}"
        )

        # Use case reasoning
        use_case_reasons = {
            UseCase.SEMANTIC_SEARCH: "optimized for semantic similarity",
            UseCase.EMERGENCY_MEDICAL: "prioritizing low latency",
            UseCase.RESEARCH_ANALYSIS: "maximizing accuracy",
            UseCase.REAL_TIME_CHAT: "balancing quality and speed",
        }
        if criteria.use_case in use_case_reasons:
            parts.append(use_case_reasons[criteria.use_case])

        # Performance reasoning
        if criteria.performance_requirement == PerformanceRequirement.ULTRA_LOW_LATENCY:
            parts.append(
                f"achieving {config.estimated_performance['latency_ms']}ms latency"
            )

        # Storage reasoning
        if criteria.storage_constraint == StorageConstraint.MINIMAL:
            parts.append(
                f"minimizing storage at {config.storage_per_vector} bytes/vector"
            )

        return ". ".join(parts) + "."

    @classmethod
    def _calculate_tradeoffs(
        cls,
        primary: DimensionConfig,
        alternatives: List[DimensionConfig],
        criteria: SelectionCriteria,  # pylint: disable=unused-argument
    ) -> Dict[str, str]:
        """Calculate tradeoffs between options."""
        tradeoffs = {}

        # Use criteria to determine importance of different factors

        for _, alt in enumerate(alternatives):
            key = f"vs_{alt.dimension}d"

            # Quality difference
            quality_diff = primary.quality_score - alt.quality_score

            # Storage difference
            storage_diff = (
                primary.storage_per_vector - alt.storage_per_vector
            ) / alt.storage_per_vector

            # Latency difference
            latency_diff = (
                primary.estimated_performance["latency_ms"]
                - alt.estimated_performance["latency_ms"]
            )

            tradeoffs[key] = (
                f"{quality_diff:+.1%} quality, "
                f"{storage_diff:+.0%} storage, "
                f"{latency_diff:+.0f}ms latency"
            )

        return tradeoffs

    @classmethod
    def _estimate_storage(
        cls, config: DimensionConfig, criteria: SelectionCriteria
    ) -> float:
        """Estimate total storage in GB."""
        bytes_total = config.storage_per_vector * criteria.expected_documents

        # Add overhead for indices (typically 10-20%)
        overhead = 1.15

        # Convert to GB
        gb = (bytes_total * overhead) / (1024**3)

        return round(gb, 2)
