"""
Translation Quality Dashboards System.

This module provides comprehensive dashboard functionality for visualizing
translation quality metrics, performance benchmarks, and trends over time.
"""

import json
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from .metrics_tracker import MetricAggregationLevel, MetricsTracker
from .performance_benchmarks import PerformanceBenchmarkManager

logger = logging.getLogger(__name__)


class DashboardType(Enum):
    """Types of quality dashboards."""

    OVERVIEW = "overview"
    PERFORMANCE = "performance"
    BENCHMARKS = "benchmarks"
    LANGUAGE_PAIR = "language_pair"
    TRENDS = "trends"
    ALERTS = "alerts"


class MetricStatus(Enum):
    """Status indicators for metrics."""

    EXCELLENT = "excellent"
    GOOD = "good"
    WARNING = "warning"
    CRITICAL = "critical"


class TimeRange(Enum):
    """Predefined time ranges for dashboards."""

    LAST_HOUR = "last_hour"
    LAST_24_HOURS = "last_24_hours"
    LAST_7_DAYS = "last_7_days"
    LAST_30_DAYS = "last_30_days"
    CUSTOM = "custom"


@dataclass
class DashboardWidget:
    """Individual dashboard widget configuration."""

    widget_id: str
    widget_type: str
    title: str
    data_source: str
    config: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "widget_id": self.widget_id,
            "widget_type": self.widget_type,
            "title": self.title,
            "data_source": self.data_source,
            "config": self.config,
        }


@dataclass
class DashboardData:
    """Dashboard data container."""

    dashboard_id: str
    dashboard_type: DashboardType
    time_range: TimeRange
    data: Dict[str, Any]
    generated_at: datetime

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "dashboard_id": self.dashboard_id,
            "dashboard_type": self.dashboard_type.value,
            "time_range": self.time_range.value,
            "data": self.data,
            "generated_at": self.generated_at.isoformat(),
        }


class QualityDashboardManager:
    """
    Manages quality dashboards for translation monitoring.

    Features:
    - Multiple dashboard types
    - Real-time data updates
    - Customizable widgets
    - Export capabilities
    - Alert integration
    - Trend visualization
    """

    def __init__(self) -> None:
        """Initialize the dashboard manager."""
        self.metrics_tracker = MetricsTracker()
        self.benchmark_manager = PerformanceBenchmarkManager()
        self._dashboard_configs = self._initialize_dashboard_configs()
        self._data_cache: Dict[str, Any] = {}

    def _initialize_dashboard_configs(
        self,
    ) -> Dict[DashboardType, List[DashboardWidget]]:
        """Initialize default dashboard configurations."""
        return {
            DashboardType.OVERVIEW: [
                DashboardWidget(
                    widget_id="current_metrics",
                    widget_type="metric_cards",
                    title="Current Performance",
                    data_source="real_time_metrics",
                ),
                DashboardWidget(
                    widget_id="quality_trend",
                    widget_type="line_chart",
                    title="Quality Score Trend",
                    data_source="quality_trend_data",
                ),
                DashboardWidget(
                    widget_id="benchmark_summary",
                    widget_type="gauge_chart",
                    title="Benchmark Achievement",
                    data_source="benchmark_summary",
                ),
                DashboardWidget(
                    widget_id="language_heatmap",
                    widget_type="heatmap",
                    title="Language Pair Performance",
                    data_source="language_pair_metrics",
                ),
            ],
            DashboardType.PERFORMANCE: [
                DashboardWidget(
                    widget_id="response_times",
                    widget_type="line_chart",
                    title="Response Times",
                    data_source="response_time_metrics",
                ),
                DashboardWidget(
                    widget_id="throughput",
                    widget_type="bar_chart",
                    title="Translation Throughput",
                    data_source="throughput_metrics",
                ),
            ],
            DashboardType.BENCHMARKS: [
                DashboardWidget(
                    widget_id="benchmark_grid",
                    widget_type="table",
                    title="Benchmark Status",
                    data_source="benchmark_status",
                ),
                DashboardWidget(
                    widget_id="benchmark_trends",
                    widget_type="multi_line_chart",
                    title="Benchmark Trends",
                    data_source="benchmark_trends",
                ),
            ],
        }

    async def get_dashboard_data(
        self,
        dashboard_type: DashboardType,
        time_range: TimeRange = TimeRange.LAST_24_HOURS,
        language_pair: Optional[Tuple[str, str]] = None,
        mode: Optional[str] = None,
    ) -> DashboardData:
        """
        Get data for a specific dashboard.

        Args:
            dashboard_type: Type of dashboard
            time_range: Time range for data
            language_pair: Optional language pair filter
            mode: Optional mode filter

        Returns:
            Dashboard data
        """
        # Calculate time boundaries
        end_time = datetime.utcnow()
        start_time = self._calculate_start_time(time_range, end_time)

        # Get widgets for this dashboard type
        widgets: List[DashboardWidget] = self._dashboard_configs.get(dashboard_type, [])

        # Collect data for each widget
        widget_data = {}
        for widget in widgets:
            widget_data[widget.widget_id] = await self._get_widget_data(
                widget, start_time, end_time, language_pair, mode
            )

        return DashboardData(
            dashboard_id=f"{dashboard_type.value}_{datetime.utcnow().timestamp()}",
            dashboard_type=dashboard_type,
            time_range=time_range,
            data=widget_data,
            generated_at=datetime.utcnow(),
        )

    async def _get_widget_data(
        self,
        widget: DashboardWidget,
        start_time: datetime,
        end_time: datetime,
        language_pair: Optional[Tuple[str, str]],
        mode: Optional[str],
    ) -> Dict[str, Any]:
        """Get data for a specific widget."""
        data_source = widget.data_source

        if data_source == "real_time_metrics":
            return await self._get_real_time_metrics(language_pair, mode)
        elif data_source == "quality_trend_data":
            return await self._get_quality_trend_data(
                start_time, end_time, language_pair, mode
            )
        elif data_source == "benchmark_summary":
            return await self._get_benchmark_summary(language_pair, mode)
        elif data_source == "language_pair_metrics":
            return await self._get_language_pair_metrics(start_time, end_time)
        elif data_source == "benchmark_status":
            return await self._get_benchmark_status(language_pair, mode)
        elif data_source == "benchmark_trends":
            return await self._get_benchmark_trends(
                start_time, end_time, language_pair, mode
            )
        elif data_source == "response_time_metrics":
            return await self._get_performance_metrics(
                start_time, end_time, "validation_time", language_pair, mode
            )
        elif data_source == "throughput_metrics":
            return await self._get_throughput_metrics(
                start_time, end_time, language_pair, mode
            )
        else:
            logger.warning("Unknown data source: %s", data_source)
            return {"error": f"Unknown data source: {data_source}"}

    async def _get_real_time_metrics(
        self, language_pair: Optional[Tuple[str, str]], mode: Optional[str]
    ) -> Dict[str, Any]:
        """Get real-time metric values."""
        recent_metrics = await self.metrics_tracker.get_recent_metrics(
            limit=10, language_pair=language_pair, mode=mode
        )

        if not recent_metrics:
            return {"status": "no_data", "metrics": {}}

        latest = recent_metrics[0].metrics

        return {
            "metrics": {
                "quality_score": {
                    "value": latest.quality_score,
                    "status": self._get_metric_status(latest.quality_score, 0.8, 0.9),
                    "trend": self._calculate_trend(recent_metrics, "quality_score"),
                },
                "pass_rate": {
                    "value": latest.pass_rate,
                    "status": self._get_metric_status(latest.pass_rate, 0.9, 0.95),
                    "trend": self._calculate_trend(recent_metrics, "pass_rate"),
                },
                "confidence_score": {
                    "value": latest.confidence_score,
                    "status": self._get_metric_status(
                        latest.confidence_score, 0.85, 0.92
                    ),
                    "trend": self._calculate_trend(recent_metrics, "confidence_score"),
                },
                "validation_time": {
                    "value": latest.validation_time,
                    "status": self._get_metric_status(
                        latest.validation_time, 2.0, 1.0, lower_is_better=True
                    ),
                    "trend": self._calculate_trend(
                        recent_metrics, "validation_time", lower_is_better=True
                    ),
                },
            },
            "last_updated": recent_metrics[0].timestamp.isoformat(),
        }

    async def _get_quality_trend_data(
        self,
        start_time: datetime,
        end_time: datetime,
        language_pair: Optional[Tuple[str, str]],
        mode: Optional[str],
    ) -> Dict[str, Any]:
        """Get quality trend data for charting."""
        aggregations = []
        current_time = start_time

        # Hourly aggregations
        while current_time < end_time:
            next_time = min(current_time + timedelta(hours=1), end_time)

            agg = await self.metrics_tracker.aggregate_metrics(
                start_time=current_time,
                end_time=next_time,
                aggregation_level=MetricAggregationLevel.HOURLY,
                language_pair=language_pair,
                mode=mode,
            )

            aggregations.append(
                {
                    "timestamp": current_time.isoformat(),
                    "quality_score": agg.avg_quality_score,
                    "confidence_score": agg.avg_confidence_score,
                    "pass_rate": agg.avg_pass_rate,
                }
            )

            current_time = next_time

        return {
            "data": aggregations,
            "series": [
                {"name": "Quality Score", "key": "quality_score"},
                {"name": "Confidence", "key": "confidence_score"},
                {"name": "Pass Rate", "key": "pass_rate"},
            ],
        }

    async def _get_benchmark_summary(
        self, language_pair: Optional[Tuple[str, str]], mode: Optional[str]
    ) -> Dict[str, Any]:
        """Get benchmark achievement summary."""
        recent_metrics = await self.metrics_tracker.get_recent_metrics(
            limit=1, language_pair=language_pair, mode=mode
        )

        if not recent_metrics:
            return {"achievement": 0, "status": "no_data"}

        # Evaluate against benchmarks
        results = await self.benchmark_manager.evaluate_metrics(
            metrics=recent_metrics[0].metrics, language_pair=language_pair, mode=mode
        )

        if results:
            passing = sum(1 for r in results if r.is_passing)
            achievement = (passing / len(results)) * 100
        else:
            achievement = 0

        return {
            "achievement": achievement,
            "total_benchmarks": len(results),
            "passing": sum(1 for r in results if r.is_passing),
            "exceeding": sum(1 for r in results if r.exceeds_target),
            "status": self._get_metric_status(achievement, 80, 90),
        }

    async def _get_language_pair_metrics(
        self, start_time: datetime, end_time: datetime
    ) -> Dict[str, Any]:
        """Get metrics heatmap for language pairs."""
        # Query snapshots using public method
        all_metrics = await self.metrics_tracker.get_recent_metrics(limit=1000)

        # Filter by time range
        filtered_metrics = [
            m for m in all_metrics if start_time <= m.timestamp <= end_time
        ]

        language_data: Dict[str, Dict[str, float]] = defaultdict(
            lambda: {"count": 0, "quality_sum": 0.0}
        )

        for snapshot in filtered_metrics:
            key = f"{snapshot.language_pair[0]}-{snapshot.language_pair[1]}"
            language_data[key]["count"] += 1
            language_data[key]["quality_sum"] += snapshot.metrics.quality_score

        heatmap_data = []
        for lang_pair, data in language_data.items():
            if data["count"] > 0:
                avg_quality = data["quality_sum"] / data["count"]
                source, target = lang_pair.split("-")

                heatmap_data.append(
                    {
                        "source": source,
                        "target": target,
                        "value": avg_quality,
                        "count": data["count"],
                    }
                )

        return {"data": heatmap_data}

    async def _get_benchmark_status(
        self, language_pair: Optional[Tuple[str, str]], mode: Optional[str]
    ) -> Dict[str, Any]:
        """Get detailed benchmark status."""
        recent_metrics = await self.metrics_tracker.get_recent_metrics(
            limit=1, language_pair=language_pair, mode=mode
        )

        if not recent_metrics:
            return {"benchmarks": [], "status": "no_data"}

        results = await self.benchmark_manager.evaluate_metrics(
            metrics=recent_metrics[0].metrics, language_pair=language_pair, mode=mode
        )

        benchmark_data = []
        for result in results:
            benchmark_data.append(
                {
                    "name": result.benchmark_name,
                    "value": result.actual_value,
                    "level": result.achieved_level.value,
                    "target_percentage": result.target_percentage,
                    "is_passing": result.is_passing,
                }
            )

        return {"benchmarks": benchmark_data}

    async def _get_benchmark_trends(
        self,
        start_time: datetime,
        end_time: datetime,
        language_pair: Optional[Tuple[str, str]],
        mode: Optional[str],
    ) -> Dict[str, Any]:
        """Get benchmark trend data."""
        trend_data = []
        benchmark_names = ["medical_term_accuracy", "overall_quality_score"]

        for benchmark_name in benchmark_names:
            history = await self.benchmark_manager.get_benchmark_history(
                benchmark_name=benchmark_name,
                start_time=start_time,
                end_time=end_time,
                language_pair=language_pair,
                mode=mode,
            )

            for result in history:
                trend_data.append(
                    {
                        "benchmark": benchmark_name,
                        "timestamp": result.timestamp.isoformat(),
                        "value": result.target_percentage,
                    }
                )

        return {"data": trend_data}

    async def _get_performance_metrics(
        self,
        start_time: datetime,
        end_time: datetime,
        metric_name: str,
        language_pair: Optional[Tuple[str, str]],
        mode: Optional[str],
    ) -> Dict[str, Any]:
        """Get performance metric data."""
        agg = await self.metrics_tracker.aggregate_metrics(
            start_time=start_time,
            end_time=end_time,
            aggregation_level=MetricAggregationLevel.DAILY,
            language_pair=language_pair,
            mode=mode,
        )

        return {
            "metric": metric_name,
            "value": agg.avg_validation_time,
            "trend": agg.trend_direction.value if agg.trend_direction else "stable",
        }

    async def _get_throughput_metrics(
        self,
        start_time: datetime,
        end_time: datetime,
        language_pair: Optional[Tuple[str, str]],
        mode: Optional[str],
    ) -> Dict[str, Any]:
        """Get throughput metrics."""
        agg = await self.metrics_tracker.aggregate_metrics(
            start_time=start_time,
            end_time=end_time,
            aggregation_level=MetricAggregationLevel.DAILY,
            language_pair=language_pair,
            mode=mode,
        )

        return {
            "total_translations": agg.total_translations,
            "period": f"{start_time.date()} to {end_time.date()}",
        }

    def _get_metric_status(
        self,
        value: float,
        warning_threshold: float,
        good_threshold: float,
        lower_is_better: bool = False,
    ) -> str:
        """Determine metric status based on thresholds."""
        if lower_is_better:
            if value <= good_threshold:
                return MetricStatus.EXCELLENT.value
            elif value <= warning_threshold:
                return MetricStatus.GOOD.value
            else:
                return MetricStatus.WARNING.value
        else:
            if value >= good_threshold:
                return MetricStatus.EXCELLENT.value
            elif value >= warning_threshold:
                return MetricStatus.GOOD.value
            else:
                return MetricStatus.WARNING.value

    def _calculate_trend(
        self, metrics: List[Any], metric_name: str, lower_is_better: bool = False
    ) -> str:
        """Calculate trend direction for a metric."""
        if len(metrics) < 2:
            return "stable"

        values = []
        for m in metrics:
            value = getattr(m.metrics, metric_name, None)
            if value is not None:
                values.append(value)

        if len(values) < 2:
            return "stable"

        trend = values[0] - values[-1]

        if abs(trend) < 0.01:
            return "stable"
        elif trend > 0:
            return "improving" if not lower_is_better else "declining"
        else:
            return "declining" if not lower_is_better else "improving"

    def _calculate_start_time(
        self, time_range: TimeRange, end_time: datetime
    ) -> datetime:
        """Calculate start time based on time range."""
        if time_range == TimeRange.LAST_HOUR:
            return end_time - timedelta(hours=1)
        elif time_range == TimeRange.LAST_24_HOURS:
            return end_time - timedelta(hours=24)
        elif time_range == TimeRange.LAST_7_DAYS:
            return end_time - timedelta(days=7)
        elif time_range == TimeRange.LAST_30_DAYS:
            return end_time - timedelta(days=30)
        else:
            return end_time - timedelta(hours=24)

    async def export_dashboard_data(
        self,
        dashboard_type: DashboardType,
        export_format: str = "json",
        output_path: Optional[Path] = None,
        time_range: TimeRange = TimeRange.LAST_24_HOURS,
        language_pair: Optional[Tuple[str, str]] = None,
        mode: Optional[str] = None,
    ) -> Path:
        """
        Export dashboard data to file.

        Args:
            dashboard_type: Type of dashboard
            format: Export format (json, csv)
            output_path: Output file path
            time_range: Time range for data
            language_pair: Optional language pair filter
            mode: Optional mode filter

        Returns:
            Path to exported file
        """
        # Get dashboard data
        dashboard_data = await self.get_dashboard_data(
            dashboard_type, time_range, language_pair, mode
        )

        # Set default output path
        if not output_path:
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            output_path = Path(
                f"dashboard_{dashboard_type.value}_{timestamp}.{export_format}"
            )

        # Export based on format
        if export_format == "json":
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(dashboard_data.to_dict(), f, indent=2, default=str)

        elif export_format == "csv":
            # Flatten data for CSV export
            rows = []
            for widget_id, widget_data in dashboard_data.data.items():
                if isinstance(widget_data, dict) and "data" in widget_data:
                    for item in widget_data["data"]:
                        row = {"widget_id": widget_id}
                        row.update(item)
                        rows.append(row)

            df = pd.DataFrame(rows)
            df.to_csv(output_path, index=False)

        else:
            raise ValueError(f"Unsupported export format: {export_format}")

        logger.info("Exported dashboard data to %s", output_path)
        return output_path
