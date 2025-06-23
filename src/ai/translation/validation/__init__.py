"""
Translation Validation Module.

Comprehensive validation system for medical translations.
"""

from .ab_testing import (
    ABTest,
    ABTestingFramework,
    AllocationStrategy,
    StatisticalTest,
    TestMetrics,
    TestResult,
    TestStatus,
    TestType,
    TestVariant,
)
from .alert_mechanisms import (
    AlertChannel,
    AlertMechanismManager,
    AlertPriority,
    AlertRule,
    ChannelConfiguration,
    CloudWatchChannelConfig,
    EmailChannelConfig,
    SlackChannelConfig,
    SNSChannelConfig,
)
from .automated_reporting import (
    AutomatedReportingSystem,
    ReportConfiguration,
    ReportData,
    ReportFormat,
    ReportSchedule,
    ReportType,
)
from .back_translation import (
    BackTranslationChecker,
    BackTranslationConfig,
    BackTranslationMethod,
    BackTranslationResult,
    SimilarityMetric,
    check_back_translation,
    evaluate_translation_quality,
)
from .confidence_scorer import (
    ConfidenceFactor,
    ConfidenceFactorType,
    ConfidenceScorer,
    ConfidenceScoringConfig,
    DetailedConfidenceScore,
    integrate_confidence_scorer,
)
from .continuous_improvement import (
    ContinuousImprovementEngine,
    ImprovementPattern,
    ImprovementProposal,
    ImprovementStatus,
    ImprovementType,
    PromptOptimization,
)
from .dashboard_renderer import DashboardRenderer
from .feedback_collector import (
    FeedbackAnalysis,
    FeedbackCollector,
    FeedbackItem,
    FeedbackPriority,
    FeedbackRating,
    FeedbackStatus,
    FeedbackType,
    TranslationContext,
)
from .human_in_loop import (
    HumanInLoopConfig,
    HumanInLoopSystem,
    HumanInLoopValidationPipeline,
    ReviewDecision,
    ReviewerProfile,
    ReviewerRole,
    ReviewPriority,
    ReviewRequest,
    ReviewStatus,
)
from .metrics import TranslationMetrics
from .metrics_tracker import (
    AggregatedMetrics,
    MetricAggregationLevel,
    MetricSnapshot,
    MetricsTracker,
    TrendDirection,
)
from .performance_benchmarks import (
    BenchmarkCategory,
    BenchmarkLevel,
    BenchmarkResult,
    PerformanceBenchmark,
    PerformanceBenchmarkManager,
)
from .pipeline import (
    TranslationValidationPipeline,
    ValidationConfig,
    ValidationIssue,
    ValidationLevel,
    ValidationResult,
    ValidationStatus,
)
from .quality_dashboards import (
    DashboardData,
    DashboardType,
    DashboardWidget,
    MetricStatus,
    QualityDashboardManager,
    TimeRange,
)
from .similarity import SimilarityConfig
from .similarity import SimilarityMetric as SimilarityMetricType
from .similarity import SimilarityScore, SimilarityScorer
from .threshold_alerts import (
    Alert,
    AlertConfiguration,
    AlertSeverity,
    AlertStatus,
    AlertType,
    EmailNotificationChannel,
    LogNotificationChannel,
    MetricsNotificationChannel,
    NotificationChannel,
    SlackNotificationChannel,
    ThresholdAlertManager,
    ThresholdDefinition,
    create_medical_translation_alerts,
    integrate_alert_manager,
)
from .validators import (
    BaseValidator,
    ContextualValidator,
    FormatPreservationValidator,
    MedicalTermValidator,
    NumericConsistencyValidator,
    SafetyValidator,
)

__all__ = [
    # Pipeline
    "ValidationLevel",
    "ValidationStatus",
    "ValidationIssue",
    "ValidationResult",
    "ValidationConfig",
    "TranslationValidationPipeline",
    # Metrics
    "TranslationMetrics",
    "MetricAggregationLevel",
    "TrendDirection",
    "MetricSnapshot",
    "AggregatedMetrics",
    "MetricsTracker",
    # Feedback
    "FeedbackType",
    "FeedbackRating",
    "FeedbackStatus",
    "FeedbackPriority",
    "TranslationContext",
    "FeedbackItem",
    "FeedbackAnalysis",
    "FeedbackCollector",
    # Continuous Improvement
    "ImprovementType",
    "ImprovementStatus",
    "ImprovementPattern",
    "ImprovementProposal",
    "PromptOptimization",
    "ContinuousImprovementEngine",
    # A/B Testing
    "TestStatus",
    "TestType",
    "AllocationStrategy",
    "StatisticalTest",
    "TestVariant",
    "TestMetrics",
    "TestResult",
    "ABTest",
    "ABTestingFramework",
    # Validators
    "BaseValidator",
    "MedicalTermValidator",
    "NumericConsistencyValidator",
    "FormatPreservationValidator",
    "ContextualValidator",
    "SafetyValidator",
    # Back-translation
    "BackTranslationChecker",
    "BackTranslationConfig",
    "BackTranslationResult",
    "BackTranslationMethod",
    "SimilarityMetric",
    "check_back_translation",
    "evaluate_translation_quality",
    # Similarity scoring
    "SimilarityScorer",
    "SimilarityConfig",
    "SimilarityScore",
    "SimilarityMetricType",
    # Human-in-the-loop
    "ReviewPriority",
    "ReviewStatus",
    "ReviewerRole",
    "ReviewerProfile",
    "ReviewRequest",
    "ReviewDecision",
    "HumanInLoopConfig",
    "HumanInLoopSystem",
    "HumanInLoopValidationPipeline",
    # Confidence scoring
    "ConfidenceFactorType",
    "ConfidenceFactor",
    "DetailedConfidenceScore",
    "ConfidenceScoringConfig",
    "ConfidenceScorer",
    "integrate_confidence_scorer",
    # Threshold alerts
    "AlertType",
    "AlertSeverity",
    "AlertStatus",
    "ThresholdDefinition",
    "Alert",
    "AlertConfiguration",
    "ThresholdAlertManager",
    "NotificationChannel",
    "LogNotificationChannel",
    "MetricsNotificationChannel",
    "EmailNotificationChannel",
    "SlackNotificationChannel",
    "create_medical_translation_alerts",
    "integrate_alert_manager",
    # Performance benchmarks
    "BenchmarkLevel",
    "BenchmarkCategory",
    "PerformanceBenchmark",
    "BenchmarkResult",
    "PerformanceBenchmarkManager",
    # Quality dashboards
    "DashboardType",
    "MetricStatus",
    "TimeRange",
    "DashboardWidget",
    "DashboardData",
    "QualityDashboardManager",
    "DashboardRenderer",
    # Automated reporting
    "ReportType",
    "ReportFormat",
    "ReportSchedule",
    "ReportConfiguration",
    "ReportData",
    "AutomatedReportingSystem",
    # Alert mechanisms
    "AlertChannel",
    "AlertPriority",
    "AlertRule",
    "ChannelConfiguration",
    "EmailChannelConfig",
    "SlackChannelConfig",
    "SNSChannelConfig",
    "CloudWatchChannelConfig",
    "AlertMechanismManager",
]
