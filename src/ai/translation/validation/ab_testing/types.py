"""Types for A/B testing framework."""

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple


class TestStatus(Enum):
    """Status of an A/B test."""

    DRAFT = "draft"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class TestType(Enum):
    """Types of A/B tests."""

    PROMPT_VARIANT = "prompt_variant"
    MODEL_COMPARISON = "model_comparison"
    PARAMETER_TUNING = "parameter_tuning"
    GLOSSARY_TEST = "glossary_test"
    FEATURE_FLAG = "feature_flag"
    MULTI_VARIANT = "multi_variant"


class AllocationStrategy(Enum):
    """Traffic allocation strategies."""

    RANDOM = "random"
    DETERMINISTIC = "deterministic"
    WEIGHTED = "weighted"
    ADAPTIVE = "adaptive"  # Thompson sampling


class StatisticalTest(Enum):
    """Statistical tests for significance."""

    T_TEST = "t_test"
    CHI_SQUARE = "chi_square"
    MANN_WHITNEY = "mann_whitney"
    BAYESIAN = "bayesian"


@dataclass
class TestVariant:
    """A variant in an A/B test."""

    variant_id: str
    name: str
    description: str
    configuration: Dict[str, Any]

    # Allocation
    allocation_percentage: float = 50.0
    is_control: bool = False

    # Metrics
    sample_count: int = 0
    success_count: int = 0
    metrics: Dict[str, List[float]] = field(default_factory=lambda: defaultdict(list))

    def add_result(self, success: bool, metrics_data: Dict[str, float]) -> None:
        """Add a test result to this variant."""
        self.sample_count += 1
        if success:
            self.success_count += 1

        for metric_name, value in metrics_data.items():
            self.metrics[metric_name].append(value)

    def get_success_rate(self) -> float:
        """Calculate success rate."""
        if self.sample_count == 0:
            return 0.0
        return self.success_count / self.sample_count


@dataclass
class TestMetrics:
    """Metrics for a test."""

    start_time: datetime
    end_time: Optional[datetime] = None
    total_participants: int = 0

    # Per-variant metrics
    variant_metrics: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    # Statistical results
    p_value: Optional[float] = None
    confidence_level: float = 0.95
    statistical_power: Optional[float] = None
    effect_size: Optional[float] = None

    # Early stopping
    should_stop_early: bool = False
    early_stop_reason: Optional[str] = None


@dataclass
class ABTest:
    """An A/B test configuration."""

    test_id: str
    name: str
    description: str
    test_type: TestType
    status: TestStatus

    # Variants
    variants: List[TestVariant]
    control_variant_id: str

    # Configuration
    allocation_strategy: AllocationStrategy
    min_sample_size: int
    max_duration_days: int
    confidence_level: float = 0.95

    # Targeting
    target_languages: Optional[List[str]] = None
    target_domains: Optional[List[str]] = None
    target_user_segments: Optional[List[str]] = None

    # Metrics
    primary_metric: str = "accuracy"
    secondary_metrics: List[str] = field(default_factory=list)
    guardrail_metrics: List[str] = field(default_factory=list)

    # Timestamps
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    # Results
    metrics: Optional[TestMetrics] = None
    winner_variant_id: Optional[str] = None

    # Metadata
    created_by: str = "system"
    tags: Set[str] = field(default_factory=set)
    notes: str = ""


@dataclass
class TestResult:
    """Result of a single test execution."""

    test_id: str
    variant_id: str
    participant_id: str
    timestamp: datetime

    # Context
    language_pair: str
    text_domain: str
    text_length: int

    # Metrics
    success: bool
    metrics: Dict[str, float]

    # Optional metadata
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SignificanceResult:
    """Statistical significance test result."""

    is_significant: bool
    p_value: float
    confidence_interval: Tuple[float, float]
    effect_size: float
    sample_size_a: int
    sample_size_b: int
    test_type: StatisticalTest
    notes: str = ""
