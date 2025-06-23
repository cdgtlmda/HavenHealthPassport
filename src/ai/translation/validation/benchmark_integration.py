"""
Integration script for Performance Benchmarks with Metrics Tracking.

This script demonstrates how to integrate the performance benchmarks system
with the existing metrics tracking infrastructure.
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from src.ai.translation.config import Language, TranslationMode

from .metrics import TranslationMetrics
from .metrics_tracker import MetricAggregationLevel, MetricsTracker
from .performance_benchmarks import PerformanceBenchmarkManager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class BenchmarkIntegration:
    """Integrates performance benchmarks with metrics tracking."""

    def __init__(self) -> None:
        """Initialize the benchmark integration with metrics and benchmark managers."""
        self.metrics_tracker = MetricsTracker()
        self.benchmark_manager = PerformanceBenchmarkManager()

    async def initialize(self) -> None:
        """Initialize both systems."""
        # Initialize default benchmarks
        await self.benchmark_manager.initialize_benchmarks()

        # Start background aggregation for metrics
        await self.metrics_tracker.start_background_aggregation(interval_seconds=300)

        logger.info("Benchmark integration initialized")

    async def track_and_evaluate(
        self,
        source_language: Language,
        target_language: Language,
        mode: TranslationMode,
        metrics: TranslationMetrics,
        model_version: str,
        additional_metrics: Optional[dict] = None,
    ) -> Dict[str, Any]:
        """Track metrics and evaluate against benchmarks."""
        # Track metrics
        await self.metrics_tracker.track_metrics(
            source_language=source_language,
            target_language=target_language,
            mode=mode,
            metrics=metrics,
            model_version=model_version,
        )

        # Evaluate against benchmarks
        benchmark_results = await self.benchmark_manager.evaluate_metrics(
            metrics=metrics,
            language_pair=(source_language.value, target_language.value),
            mode=str(mode.value),
            additional_metrics=additional_metrics,
        )

        # Log results
        passing = sum(1 for r in benchmark_results if r.is_passing)
        total = len(benchmark_results)

        logger.info(
            "Benchmark evaluation complete: %s/%s passing for %s->%s (%s)",
            passing,
            total,
            source_language.value,
            target_language.value,
            mode.value,
        )

        # Check for critical failures
        critical_failures = [
            r
            for r in benchmark_results
            if not r.is_passing
            and r.benchmark_name in ["medical_term_accuracy", "system_availability"]
        ]

        if critical_failures:
            logger.error(
                "Critical benchmark failures detected: %s",
                [f.benchmark_name for f in critical_failures],
            )

        return {
            "benchmark_results": [r.__dict__ for r in benchmark_results],
            "passing_count": passing,
            "total_count": total,
            "pass_rate": passing / total if total > 0 else 0,
            "critical_failures": [f.benchmark_name for f in critical_failures],
            "has_critical_failures": bool(critical_failures),
        }

    async def generate_performance_report(
        self,
        period_days: int = 7,
        language_pair: Optional[tuple] = None,
        mode: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Generate a comprehensive performance report."""
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(days=period_days)

        # Generate benchmark report
        benchmark_report = await self.benchmark_manager.generate_benchmark_report(
            start_time=start_time,
            end_time=end_time,
            language_pair=language_pair,
            mode=mode,
            output_format="markdown",
        )

        # Get aggregated metrics
        aggregated_metrics = await self.metrics_tracker.aggregate_metrics(
            start_time=start_time,
            end_time=end_time,
            aggregation_level=MetricAggregationLevel.DAILY,
            language_pair=language_pair,
            mode=mode,
        )

        logger.info("Performance report generated for %s day period", period_days)

        return {
            "benchmark_report": benchmark_report,
            "aggregated_metrics": aggregated_metrics,
        }

    async def close(self) -> None:
        """Clean up resources."""
        await self.metrics_tracker.close()
        logger.info("Benchmark integration closed")
