"""
Translation Performance Benchmarks System.

This module defines and manages performance benchmarks for translation quality,
providing targets, thresholds, and comparison capabilities for continuous monitoring
and improvement of the translation system.
"""

import json
import logging
import statistics
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import boto3
import numpy as np
import pandas as pd

from ..exceptions import TranslationError
from .metrics import TranslationMetrics

logger = logging.getLogger(__name__)


class BenchmarkError(TranslationError):
    """Exception raised for benchmark-related errors."""


class BenchmarkLevel(Enum):
    """Performance benchmark levels."""

    MINIMUM = "minimum"  # Absolute minimum acceptable performance
    TARGET = "target"  # Target performance level
    EXCELLENT = "excellent"  # Excellent performance level
    WORLD_CLASS = "world_class"  # World-class performance level


class BenchmarkCategory(Enum):
    """Categories of benchmarks."""

    ACCURACY = "accuracy"
    SPEED = "speed"
    RELIABILITY = "reliability"
    EFFICIENCY = "efficiency"
    USER_SATISFACTION = "user_satisfaction"


@dataclass
class PerformanceBenchmark:
    """Definition of a performance benchmark."""

    name: str
    category: BenchmarkCategory
    metric_name: str
    levels: Dict[BenchmarkLevel, float]
    unit: str
    description: str
    higher_is_better: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)

    def evaluate(self, value: float) -> Tuple[BenchmarkLevel, float]:
        """
        Evaluate a metric value against benchmark levels.

        Returns:
            Tuple of (achieved level, percentage of target)
        """
        # Sort levels by value
        sorted_levels = sorted(
            self.levels.items(), key=lambda x: x[1], reverse=self.higher_is_better
        )

        # Find achieved level
        achieved_level = BenchmarkLevel.MINIMUM
        for level, threshold in sorted_levels:
            if self.higher_is_better:
                if value >= threshold:
                    achieved_level = level
                    break
            else:
                if value <= threshold:
                    achieved_level = level
                    break

        # Calculate percentage of target
        target_value = self.levels[BenchmarkLevel.TARGET]
        if target_value != 0:
            if self.higher_is_better:
                percentage = (value / target_value) * 100
            else:
                percentage = (target_value / value) * 100
        else:
            percentage = 100.0 if value == 0 else 0.0

        return achieved_level, percentage


@dataclass
class BenchmarkResult:
    """Result of benchmark evaluation."""

    benchmark_name: str
    actual_value: float
    achieved_level: BenchmarkLevel
    target_percentage: float
    timestamp: datetime
    language_pair: Optional[Tuple[str, str]] = None
    mode: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_passing(self) -> bool:
        """Check if benchmark meets minimum requirements."""
        return self.achieved_level != BenchmarkLevel.MINIMUM

    @property
    def exceeds_target(self) -> bool:
        """Check if benchmark exceeds target level."""
        return self.achieved_level in [
            BenchmarkLevel.EXCELLENT,
            BenchmarkLevel.WORLD_CLASS,
        ]


class PerformanceBenchmarkManager:
    """
    Manages performance benchmarks for translation quality.

    Features:
    - Define and store performance benchmarks
    - Evaluate metrics against benchmarks
    - Track benchmark achievement over time
    - Generate benchmark reports
    - Support for language-specific benchmarks
    """

    def __init__(self, table_name: str = "translation_benchmarks"):
        """Initialize the benchmark manager."""
        self.table_name = table_name
        self.dynamodb = boto3.resource("dynamodb")
        self.table = self._initialize_table()

        # Default benchmarks
        self.default_benchmarks = self._create_default_benchmarks()

        # Cache for loaded benchmarks
        self._benchmark_cache: Dict[str, PerformanceBenchmark] = {}

    def _initialize_table(self) -> Any:
        """Initialize DynamoDB table for benchmark storage."""
        try:
            table = self.dynamodb.Table(self.table_name)
            table.load()
            return table
        except (
            boto3.client("dynamodb").exceptions.ResourceNotFoundException,
            AttributeError,
        ):
            return self._create_benchmark_table()

    def _create_benchmark_table(self) -> Any:
        """Create DynamoDB table for benchmarks."""
        table = self.dynamodb.create_table(
            TableName=self.table_name,
            KeySchema=[
                {
                    "AttributeName": "pk",  # "BENCHMARK#{category}#{name}"
                    "KeyType": "HASH",
                },
                {
                    "AttributeName": "sk",  # "CONFIG" or "RESULT#{timestamp}"
                    "KeyType": "RANGE",
                },
            ],
            AttributeDefinitions=[
                {"AttributeName": "pk", "AttributeType": "S"},
                {"AttributeName": "sk", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )

        table.wait_until_exists()
        return table

    def _create_default_benchmarks(self) -> List[PerformanceBenchmark]:
        """Create default performance benchmarks."""
        return [
            # Accuracy benchmarks
            PerformanceBenchmark(
                name="medical_term_accuracy",
                category=BenchmarkCategory.ACCURACY,
                metric_name="terminology_accuracy",
                levels={
                    BenchmarkLevel.MINIMUM: 0.95,  # 95% minimum
                    BenchmarkLevel.TARGET: 0.99,  # 99% target (per requirements)
                    BenchmarkLevel.EXCELLENT: 0.995,  # 99.5% excellent
                    BenchmarkLevel.WORLD_CLASS: 0.999,  # 99.9% world-class
                },
                unit="percentage",
                description="Accuracy of medical terminology translation",
                higher_is_better=True,
            ),
            PerformanceBenchmark(
                name="semantic_similarity",
                category=BenchmarkCategory.ACCURACY,
                metric_name="semantic_similarity",
                levels={
                    BenchmarkLevel.MINIMUM: 0.85,
                    BenchmarkLevel.TARGET: 0.92,
                    BenchmarkLevel.EXCELLENT: 0.95,
                    BenchmarkLevel.WORLD_CLASS: 0.98,
                },
                unit="score",
                description="Semantic similarity between source and translated text",
                higher_is_better=True,
            ),
            PerformanceBenchmark(
                name="overall_quality_score",
                category=BenchmarkCategory.ACCURACY,
                metric_name="quality_score",
                levels={
                    BenchmarkLevel.MINIMUM: 0.80,
                    BenchmarkLevel.TARGET: 0.90,
                    BenchmarkLevel.EXCELLENT: 0.95,
                    BenchmarkLevel.WORLD_CLASS: 0.98,
                },
                unit="score",
                description="Overall translation quality score",
                higher_is_better=True,
            ),
            # Speed benchmarks
            PerformanceBenchmark(
                name="validation_time",
                category=BenchmarkCategory.SPEED,
                metric_name="validation_time",
                levels={
                    BenchmarkLevel.MINIMUM: 5.0,  # 5 seconds max
                    BenchmarkLevel.TARGET: 2.0,  # 2 seconds target
                    BenchmarkLevel.EXCELLENT: 1.0,  # 1 second excellent
                    BenchmarkLevel.WORLD_CLASS: 0.5,  # 0.5 seconds world-class
                },
                unit="seconds",
                description="Time to validate translation",
                higher_is_better=False,
            ),
            PerformanceBenchmark(
                name="api_response_time",
                category=BenchmarkCategory.SPEED,
                metric_name="api_response_time",
                levels={
                    BenchmarkLevel.MINIMUM: 2.0,  # 2 seconds max
                    BenchmarkLevel.TARGET: 0.5,  # 500ms target (per requirements)
                    BenchmarkLevel.EXCELLENT: 0.3,  # 300ms excellent
                    BenchmarkLevel.WORLD_CLASS: 0.1,  # 100ms world-class
                },
                unit="seconds",
                description="API response time for translation requests",
                higher_is_better=False,
            ),
            # Reliability benchmarks
            PerformanceBenchmark(
                name="validation_pass_rate",
                category=BenchmarkCategory.RELIABILITY,
                metric_name="pass_rate",
                levels={
                    BenchmarkLevel.MINIMUM: 0.90,
                    BenchmarkLevel.TARGET: 0.95,
                    BenchmarkLevel.EXCELLENT: 0.98,
                    BenchmarkLevel.WORLD_CLASS: 0.995,
                },
                unit="percentage",
                description="Percentage of translations passing validation",
                higher_is_better=True,
            ),
            PerformanceBenchmark(
                name="system_availability",
                category=BenchmarkCategory.RELIABILITY,
                metric_name="uptime",
                levels={
                    BenchmarkLevel.MINIMUM: 0.99,  # 99% minimum
                    BenchmarkLevel.TARGET: 0.999,  # 99.9% target (per requirements)
                    BenchmarkLevel.EXCELLENT: 0.9995,  # 99.95% excellent
                    BenchmarkLevel.WORLD_CLASS: 0.9999,  # 99.99% world-class
                },
                unit="percentage",
                description="System availability and uptime",
                higher_is_better=True,
            ),
            # Efficiency benchmarks
            PerformanceBenchmark(
                name="confidence_score",
                category=BenchmarkCategory.EFFICIENCY,
                metric_name="confidence_score",
                levels={
                    BenchmarkLevel.MINIMUM: 0.85,
                    BenchmarkLevel.TARGET: 0.92,
                    BenchmarkLevel.EXCELLENT: 0.95,
                    BenchmarkLevel.WORLD_CLASS: 0.98,
                },
                unit="score",
                description="Model confidence in translation quality",
                higher_is_better=True,
            ),
            PerformanceBenchmark(
                name="format_preservation",
                category=BenchmarkCategory.EFFICIENCY,
                metric_name="format_preservation",
                levels={
                    BenchmarkLevel.MINIMUM: 0.95,
                    BenchmarkLevel.TARGET: 0.98,
                    BenchmarkLevel.EXCELLENT: 0.995,
                    BenchmarkLevel.WORLD_CLASS: 1.0,
                },
                unit="score",
                description="Preservation of document formatting",
                higher_is_better=True,
            ),
            # User satisfaction benchmarks
            PerformanceBenchmark(
                name="fluency_score",
                category=BenchmarkCategory.USER_SATISFACTION,
                metric_name="fluency_score",
                levels={
                    BenchmarkLevel.MINIMUM: 0.80,
                    BenchmarkLevel.TARGET: 0.90,
                    BenchmarkLevel.EXCELLENT: 0.95,
                    BenchmarkLevel.WORLD_CLASS: 0.98,
                },
                unit="score",
                description="Fluency and naturalness of translated text",
                higher_is_better=True,
            ),
        ]

    async def initialize_benchmarks(self) -> None:
        """Initialize default benchmarks in the system."""
        for benchmark in self.default_benchmarks:
            await self.create_benchmark(benchmark)

        logger.info("Initialized %s default benchmarks", len(self.default_benchmarks))

    async def create_benchmark(
        self,
        benchmark: PerformanceBenchmark,
        language_pair: Optional[Tuple[str, str]] = None,
        mode: Optional[str] = None,
    ) -> None:
        """
        Create or update a performance benchmark.

        Args:
            benchmark: Benchmark definition
            language_pair: Optional language pair for specific benchmark
            mode: Optional mode for specific benchmark
        """
        # Create cache key
        cache_key = self._get_cache_key(benchmark.name, language_pair, mode)

        # Store in cache
        self._benchmark_cache[cache_key] = benchmark

        # Store in DynamoDB
        pk = f"BENCHMARK#{benchmark.category.value}#{benchmark.name}"
        if language_pair:
            pk += f"#{language_pair[0]}-{language_pair[1]}"
        if mode:
            pk += f"#{mode}"

        item = {
            "pk": pk,
            "sk": "CONFIG",
            "name": benchmark.name,
            "category": benchmark.category.value,
            "metric_name": benchmark.metric_name,
            "levels": {k.value: v for k, v in benchmark.levels.items()},
            "unit": benchmark.unit,
            "description": benchmark.description,
            "higher_is_better": benchmark.higher_is_better,
            "metadata": benchmark.metadata,
            "language_pair": (
                f"{language_pair[0]}-{language_pair[1]}" if language_pair else None
            ),
            "mode": mode,
            "created_at": datetime.utcnow().isoformat(),
        }

        try:
            self.table.put_item(Item=item)
            logger.info("Created benchmark: %s", benchmark.name)
        except Exception as e:
            logger.error("Failed to create benchmark: %s", str(e))
            raise TranslationError(f"Failed to create benchmark: {e}") from e

    async def get_benchmark(
        self,
        name: str,
        language_pair: Optional[Tuple[str, str]] = None,
        mode: Optional[str] = None,
    ) -> Optional[PerformanceBenchmark]:
        """
        Get a specific benchmark.

        Args:
            name: Benchmark name
            language_pair: Optional language pair
            mode: Optional mode

        Returns:
            Benchmark if found, None otherwise
        """
        # Check cache first
        cache_key = self._get_cache_key(name, language_pair, mode)
        if cache_key in self._benchmark_cache:
            return self._benchmark_cache[cache_key]

        # Try to load from DynamoDB
        # First try specific benchmark
        if language_pair or mode:
            benchmark = await self._load_specific_benchmark(name, language_pair, mode)
            if benchmark:
                self._benchmark_cache[cache_key] = benchmark
                return benchmark

        # Fall back to default benchmark
        benchmark = await self._load_default_benchmark(name)
        if benchmark:
            self._benchmark_cache[cache_key] = benchmark
            return benchmark

        return None

    async def _load_specific_benchmark(
        self, name: str, language_pair: Optional[Tuple[str, str]], mode: Optional[str]
    ) -> Optional[PerformanceBenchmark]:
        """Load a specific benchmark from DynamoDB."""
        # Try different combinations
        for category in BenchmarkCategory:
            pk = f"BENCHMARK#{category.value}#{name}"
            if language_pair:
                pk += f"#{language_pair[0]}-{language_pair[1]}"
            if mode:
                pk += f"#{mode}"

            try:
                response = self.table.get_item(Key={"pk": pk, "sk": "CONFIG"})

                if (
                    response
                    and hasattr(response, "__contains__")
                    and "Item" in response
                ):
                    return self._deserialize_benchmark(response["Item"])
            except (ValueError, KeyError):
                continue

        return None

    async def _load_default_benchmark(
        self, name: str
    ) -> Optional[PerformanceBenchmark]:
        """Load default benchmark from DynamoDB."""
        for category in BenchmarkCategory:
            pk = f"BENCHMARK#{category.value}#{name}"

            try:
                response = self.table.get_item(Key={"pk": pk, "sk": "CONFIG"})

                if (
                    response
                    and hasattr(response, "__contains__")
                    and "Item" in response
                ):
                    return self._deserialize_benchmark(response["Item"])
            except (KeyError, AttributeError, ValueError):
                continue

        # Check in-memory defaults
        for benchmark in self.default_benchmarks:
            if benchmark.name == name:
                return benchmark

        return None

    def _deserialize_benchmark(self, item: Dict[str, Any]) -> PerformanceBenchmark:
        """Deserialize benchmark from DynamoDB item."""
        return PerformanceBenchmark(
            name=item["name"],
            category=BenchmarkCategory(item["category"]),
            metric_name=item["metric_name"],
            levels={BenchmarkLevel(k): v for k, v in item["levels"].items()},
            unit=item["unit"],
            description=item["description"],
            higher_is_better=item.get("higher_is_better", True),
            metadata=item.get("metadata", {}),
        )

    async def evaluate_metrics(
        self,
        metrics: TranslationMetrics,
        language_pair: Optional[Tuple[str, str]] = None,
        mode: Optional[str] = None,
        additional_metrics: Optional[Dict[str, float]] = None,
    ) -> List[BenchmarkResult]:
        """
        Evaluate metrics against all applicable benchmarks.

        Args:
            metrics: Translation metrics to evaluate
            language_pair: Optional language pair
            mode: Optional mode
            additional_metrics: Additional metrics not in TranslationMetrics

        Returns:
            List of benchmark results
        """
        results = []

        # Get all metrics values
        metrics_dict = metrics.to_dict()
        if additional_metrics:
            metrics_dict.update(additional_metrics)

        # Evaluate each benchmark
        for benchmark in self.default_benchmarks:
            # Get specific benchmark if available
            specific_benchmark = await self.get_benchmark(
                benchmark.name, language_pair, mode
            )
            benchmark_to_use = specific_benchmark or benchmark

            # Check if metric exists
            if benchmark_to_use.metric_name in metrics_dict:
                value = metrics_dict[benchmark_to_use.metric_name]
                if value is not None:
                    level, percentage = benchmark_to_use.evaluate(value)

                    result = BenchmarkResult(
                        benchmark_name=benchmark_to_use.name,
                        actual_value=value,
                        achieved_level=level,
                        target_percentage=percentage,
                        timestamp=datetime.utcnow(),
                        language_pair=language_pair,
                        mode=mode,
                    )

                    results.append(result)

                    # Store result
                    await self._store_result(result)

        return results

    async def _store_result(self, result: BenchmarkResult) -> None:
        """Store benchmark result in DynamoDB."""
        pk = f"BENCHMARK#RESULT#{result.benchmark_name}"
        if result.language_pair:
            pk += f"#{result.language_pair[0]}-{result.language_pair[1]}"
        if result.mode:
            pk += f"#{result.mode}"

        item = {
            "pk": pk,
            "sk": f"RESULT#{result.timestamp.isoformat()}",
            "benchmark_name": result.benchmark_name,
            "actual_value": result.actual_value,
            "achieved_level": result.achieved_level.value,
            "target_percentage": result.target_percentage,
            "timestamp": result.timestamp.isoformat(),
            "language_pair": (
                f"{result.language_pair[0]}-{result.language_pair[1]}"
                if result.language_pair
                else None
            ),
            "mode": result.mode,
            "metadata": result.metadata,
        }

        try:
            self.table.put_item(Item=item)
        except (AttributeError, ValueError, KeyError) as e:
            logger.error("Failed to store benchmark result: %s", str(e))

    async def get_benchmark_history(
        self,
        benchmark_name: str,
        start_time: datetime,
        end_time: datetime,
        language_pair: Optional[Tuple[str, str]] = None,
        mode: Optional[str] = None,
    ) -> List[BenchmarkResult]:
        """Get historical benchmark results."""
        pk = f"BENCHMARK#RESULT#{benchmark_name}"
        if language_pair:
            pk += f"#{language_pair[0]}-{language_pair[1]}"
        if mode:
            pk += f"#{mode}"

        results = []

        try:
            response = self.table.query(
                KeyConditionExpression="pk = :pk AND sk BETWEEN :start AND :end",
                ExpressionAttributeValues={
                    ":pk": pk,
                    ":start": f"RESULT#{start_time.isoformat()}",
                    ":end": f"RESULT#{end_time.isoformat()}",
                },
            )

            for item in response.get("Items", []):
                results.append(self._deserialize_result(item))

        except (AttributeError, ValueError, KeyError) as e:
            logger.error("Failed to get benchmark history: %s", str(e))

        return results

    def _deserialize_result(self, item: Dict[str, Any]) -> BenchmarkResult:
        """Deserialize benchmark result from DynamoDB item."""
        language_pair = None
        if item.get("language_pair"):
            parts = item["language_pair"].split("-")
            language_pair = (parts[0], parts[1])

        return BenchmarkResult(
            benchmark_name=item["benchmark_name"],
            actual_value=item["actual_value"],
            achieved_level=BenchmarkLevel(item["achieved_level"]),
            target_percentage=item["target_percentage"],
            timestamp=datetime.fromisoformat(item["timestamp"]),
            language_pair=language_pair,
            mode=item.get("mode"),
            metadata=item.get("metadata", {}),
        )

    async def generate_benchmark_report(
        self,
        start_time: datetime,
        end_time: datetime,
        language_pair: Optional[Tuple[str, str]] = None,
        mode: Optional[str] = None,
        output_format: str = "json",
    ) -> Union[Dict[str, Any], str]:
        """
        Generate a benchmark performance report.

        Args:
            start_time: Report start time
            end_time: Report end time
            language_pair: Optional language pair filter
            mode: Optional mode filter
            output_format: Output format (json, html, markdown)

        Returns:
            Report in requested format
        """
        report_data = {
            "period": {"start": start_time.isoformat(), "end": end_time.isoformat()},
            "filters": {
                "language_pair": (
                    f"{language_pair[0]}-{language_pair[1]}" if language_pair else None
                ),
                "mode": mode,
            },
            "benchmarks": {},
            "summary": {
                "total_benchmarks": 0,
                "passing_benchmarks": 0,
                "failing_benchmarks": 0,
                "average_target_percentage": 0.0,
            },
        }

        # Collect results for each benchmark
        total_percentage = 0.0

        for benchmark in self.default_benchmarks:
            history = await self.get_benchmark_history(
                benchmark.name, start_time, end_time, language_pair, mode
            )

            if history:
                # Calculate statistics
                values = [r.actual_value for r in history]
                percentages = [r.target_percentage for r in history]
                levels = [r.achieved_level for r in history]

                benchmark_stats = {
                    "name": benchmark.name,
                    "category": benchmark.category.value,
                    "description": benchmark.description,
                    "unit": benchmark.unit,
                    "evaluations": len(history),
                    "current_value": values[-1] if values else None,
                    "current_level": levels[-1].value if levels else None,
                    "average_value": statistics.mean(values) if values else None,
                    "min_value": min(values) if values else None,
                    "max_value": max(values) if values else None,
                    "average_target_percentage": (
                        statistics.mean(percentages) if percentages else 0.0
                    ),
                    "pass_rate": sum(1 for r in history if r.is_passing)
                    / len(history)
                    * 100,
                    "trend": (
                        self._calculate_trend(values) if len(values) > 1 else "stable"
                    ),
                }

                report_data["benchmarks"][benchmark.name] = benchmark_stats  # type: ignore
                report_data["summary"]["total_benchmarks"] += 1  # type: ignore

                if (
                    benchmark_stats["pass_rate"] is not None
                    and isinstance(benchmark_stats["pass_rate"], (int, float))
                    and benchmark_stats["pass_rate"] >= 100
                ):
                    report_data["summary"]["passing_benchmarks"] += 1  # type: ignore
                else:
                    report_data["summary"]["failing_benchmarks"] += 1  # type: ignore

                if benchmark_stats["average_target_percentage"] is not None:
                    total_percentage += float(
                        benchmark_stats["average_target_percentage"]
                    )

        # Calculate summary statistics
        if report_data["summary"]["total_benchmarks"] > 0:  # type: ignore
            report_data["summary"]["average_target_percentage"] = (  # type: ignore
                total_percentage / report_data["summary"]["total_benchmarks"]  # type: ignore
            )

        # Format output
        if output_format == "json":
            return report_data
        elif output_format == "html":
            return self._format_report_html(report_data)
        elif output_format == "markdown":
            return self._format_report_markdown(report_data)
        else:
            raise ValueError(f"Unsupported output format: {output_format}")

    def _calculate_trend(self, values: List[float]) -> str:
        """Calculate trend from values."""
        if len(values) < 2:
            return "stable"

        # Simple linear regression
        x = np.arange(len(values))
        slope, _ = np.polyfit(x, values, 1)

        if abs(slope) < 0.001:
            return "stable"
        elif slope > 0:
            return "improving"
        else:
            return "declining"

    def _format_report_markdown(self, report_data: Dict[str, Any]) -> str:
        """Format report as Markdown."""
        md = []
        md.append("# Translation Performance Benchmark Report\n")

        # Period and filters
        md.append(
            f"**Period**: {report_data['period']['start']} to {report_data['period']['end']}\n"
        )

        if report_data["filters"]["language_pair"]:
            md.append(f"**Language Pair**: {report_data['filters']['language_pair']}\n")

        if report_data["filters"]["mode"]:
            md.append(f"**Mode**: {report_data['filters']['mode']}\n")

        # Summary
        md.append("\n## Summary\n")
        summary = report_data["summary"]
        md.append(f"- **Total Benchmarks**: {summary['total_benchmarks']}")
        md.append(f"- **Passing**: {summary['passing_benchmarks']}")
        md.append(f"- **Failing**: {summary['failing_benchmarks']}")
        md.append(
            f"- **Average Target Achievement**: {summary['average_target_percentage']:.1f}%\n"
        )

        # Benchmark details
        md.append("\n## Benchmark Details\n")

        for _, stats in report_data["benchmarks"].items():
            md.append(f"\n### {stats['name']}\n")
            md.append(f"*{stats['description']}*\n")
            md.append(f"- **Category**: {stats['category']}")
            md.append(
                f"- **Current Value**: {stats['current_value']:.3f} {stats['unit']}"
            )
            md.append(f"- **Current Level**: {stats['current_level']}")
            md.append(f"- **Average**: {stats['average_value']:.3f} {stats['unit']}")
            md.append(
                f"- **Range**: {stats['min_value']:.3f} - {stats['max_value']:.3f}"
            )
            md.append(
                f"- **Target Achievement**: {stats['average_target_percentage']:.1f}%"
            )
            md.append(f"- **Pass Rate**: {stats['pass_rate']:.1f}%")
            md.append(f"- **Trend**: {stats['trend']}\n")

        return "\n".join(md)

    def _format_report_html(self, report_data: Dict[str, Any]) -> str:
        """Format report as HTML."""
        # Simple HTML template
        html = []
        html.append("<html><head><title>Benchmark Report</title>")
        html.append("<style>")
        html.append("body { font-family: Arial, sans-serif; margin: 20px; }")
        html.append("table { border-collapse: collapse; width: 100%; }")
        html.append(
            "th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }"
        )
        html.append("th { background-color: #f2f2f2; }")
        html.append(".passing { color: green; }")
        html.append(".failing { color: red; }")
        html.append("</style></head><body>")

        html.append("<h1>Translation Performance Benchmark Report</h1>")

        # Period and filters
        html.append(
            f"<p><strong>Period:</strong> {report_data['period']['start']} to {report_data['period']['end']}</p>"
        )

        # Summary
        summary = report_data["summary"]
        html.append("<h2>Summary</h2>")
        html.append("<ul>")
        html.append(f"<li>Total Benchmarks: {summary['total_benchmarks']}</li>")
        html.append(
            f"<li class='passing'>Passing: {summary['passing_benchmarks']}</li>"
        )
        html.append(
            f"<li class='failing'>Failing: {summary['failing_benchmarks']}</li>"
        )
        html.append(
            f"<li>Average Target Achievement: {summary['average_target_percentage']:.1f}%</li>"
        )
        html.append("</ul>")

        # Benchmark table
        html.append("<h2>Benchmark Details</h2>")
        html.append("<table>")
        html.append("<tr>")
        html.append("<th>Benchmark</th>")
        html.append("<th>Category</th>")
        html.append("<th>Current Value</th>")
        html.append("<th>Level</th>")
        html.append("<th>Target %</th>")
        html.append("<th>Pass Rate</th>")
        html.append("<th>Trend</th>")
        html.append("</tr>")

        for _, stats in report_data["benchmarks"].items():
            pass_class = "passing" if stats["pass_rate"] >= 100 else "failing"
            html.append("<tr>")
            html.append(f"<td>{stats['name']}</td>")
            html.append(f"<td>{stats['category']}</td>")
            html.append(f"<td>{stats['current_value']:.3f} {stats['unit']}</td>")
            html.append(f"<td>{stats['current_level']}</td>")
            html.append(f"<td>{stats['average_target_percentage']:.1f}%</td>")
            html.append(f"<td class='{pass_class}'>{stats['pass_rate']:.1f}%</td>")
            html.append(f"<td>{stats['trend']}</td>")
            html.append("</tr>")

        html.append("</table>")
        html.append("</body></html>")

        return "\n".join(html)

    def _get_cache_key(
        self, name: str, language_pair: Optional[Tuple[str, str]], mode: Optional[str]
    ) -> str:
        """Generate cache key for benchmark."""
        key = name
        if language_pair:
            key += f"#{language_pair[0]}-{language_pair[1]}"
        if mode:
            key += f"#{mode}"
        return key

    async def export_benchmarks(
        self, output_path: Path, export_format: str = "json"
    ) -> Path:
        """Export all benchmarks to file."""
        benchmarks = []

        # Export all benchmarks
        for benchmark in self.default_benchmarks:
            benchmarks.append(
                {
                    "name": benchmark.name,
                    "category": benchmark.category.value,
                    "metric_name": benchmark.metric_name,
                    "levels": {k.value: v for k, v in benchmark.levels.items()},
                    "unit": benchmark.unit,
                    "description": benchmark.description,
                    "higher_is_better": benchmark.higher_is_better,
                }
            )

        if export_format == "json":
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(benchmarks, f, indent=2)
        elif export_format == "csv":
            df = pd.DataFrame(benchmarks)
            df.to_csv(output_path, index=False)
        else:
            raise ValueError(f"Unsupported export format: {export_format}")

        return output_path

    async def import_benchmarks(
        self, input_path: Path, import_format: str = "json"
    ) -> int:
        """Import benchmarks from file."""
        if import_format == "json":
            with open(input_path, "r", encoding="utf-8") as f:
                benchmarks_data = json.load(f)
        elif import_format == "csv":
            df = pd.read_csv(input_path)
            benchmarks_data = df.to_dict("records")
        else:
            raise ValueError(f"Unsupported import format: {import_format}")

        count = 0
        for data in benchmarks_data:
            benchmark = PerformanceBenchmark(
                name=data["name"],
                category=BenchmarkCategory(data["category"]),
                metric_name=data["metric_name"],
                levels={BenchmarkLevel(k): v for k, v in data["levels"].items()},
                unit=data["unit"],
                description=data["description"],
                higher_is_better=data.get("higher_is_better", True),
            )

            await self.create_benchmark(benchmark)
            count += 1

        return count
