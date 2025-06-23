"""
Healthcare Performance Monitoring.

Continuous monitoring of healthcare standards performance metrics.
Handles FHIR OperationOutcome Resource validation for performance tracking.
"""

import asyncio
import json
import statistics
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from src.healthcare.fhir_validator import FHIRValidator

# FHIR resource type for this module
__fhir_resource__ = "OperationOutcome"


class MetricType(Enum):
    """Types of performance metrics."""

    LATENCY = "latency"
    THROUGHPUT = "throughput"
    ERROR_RATE = "error_rate"
    AVAILABILITY = "availability"
    ACCURACY = "accuracy"


@dataclass
class MetricDataPoint:
    """Single data point for a metric."""

    timestamp: datetime
    value: float
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MetricWindow:
    """Time window for metric aggregation."""

    name: str
    duration: timedelta
    data_points: deque = field(default_factory=lambda: deque(maxlen=10000))

    def add_point(self, point: MetricDataPoint) -> None:
        """Add a data point to the window."""
        self.data_points.append(point)
        self._cleanup_old_points()

    def _cleanup_old_points(self) -> None:
        """Remove data points older than the window duration."""
        cutoff_time = datetime.now() - self.duration
        while self.data_points and self.data_points[0].timestamp < cutoff_time:
            self.data_points.popleft()

    def get_statistics(self) -> Dict[str, float]:
        """Calculate statistics for the current window."""
        if not self.data_points:
            return {
                "count": 0,
                "mean": 0,
                "median": 0,
                "min": 0,
                "max": 0,
                "p95": 0,
                "p99": 0,
            }

        values = [p.value for p in self.data_points]
        sorted_values = sorted(values)

        return {
            "count": len(values),
            "mean": statistics.mean(values),
            "median": statistics.median(values),
            "min": min(values),
            "max": max(values),
            "p95": (
                sorted_values[int(len(sorted_values) * 0.95)]
                if len(sorted_values) > 1
                else sorted_values[0]
            ),
            "p99": (
                sorted_values[int(len(sorted_values) * 0.99)]
                if len(sorted_values) > 1
                else sorted_values[0]
            ),
        }


class PerformanceMonitor:
    """Continuous performance monitoring for healthcare standards."""

    def __init__(self) -> None:
        """Initialize performance monitor with metrics and alert configuration."""
        self.metrics: Dict[str, Dict[str, MetricWindow]] = {}
        self.alerts: List[Dict[str, Any]] = []
        self.monitoring_active = False
        self.alert_callbacks: List[Callable] = []
        self.validator = FHIRValidator()  # Initialize FHIR validator

        # Define monitoring windows
        self.window_definitions = [
            ("1min", timedelta(minutes=1)),
            ("5min", timedelta(minutes=5)),
            ("1hour", timedelta(hours=1)),
            ("24hour", timedelta(hours=24)),
        ]

        # Alert thresholds
        self.alert_thresholds = self._define_alert_thresholds()

        # Monitoring data directory
        self.monitoring_dir = Path("monitoring/performance")
        self.monitoring_dir.mkdir(parents=True, exist_ok=True)

    def _define_alert_thresholds(self) -> Dict[str, Dict[str, Any]]:
        """Define alert thresholds for different metrics."""
        return {
            "api_latency": {
                "metric_type": MetricType.LATENCY,
                "warning": 400,  # ms
                "critical": 500,  # ms
                "window": "5min",
                "aggregation": "p95",
            },
            "fhir_validation_latency": {
                "metric_type": MetricType.LATENCY,
                "warning": 40,
                "critical": 50,
                "window": "5min",
                "aggregation": "mean",
            },
            "translation_accuracy": {
                "metric_type": MetricType.ACCURACY,
                "warning": 99.5,
                "critical": 99.0,
                "window": "1hour",
                "aggregation": "mean",
                "comparison": "less_than",
            },
            "error_rate": {
                "metric_type": MetricType.ERROR_RATE,
                "warning": 0.5,  # 0.5%
                "critical": 1.0,  # 1%
                "window": "5min",
                "aggregation": "mean",
            },
            "system_availability": {
                "metric_type": MetricType.AVAILABILITY,
                "warning": 99.95,
                "critical": 99.9,
                "window": "24hour",
                "aggregation": "mean",
                "comparison": "less_than",
            },
        }

    def register_metric(self, metric_name: str, metric_type: MetricType) -> None:
        """Register a new metric for monitoring."""
        # metric_type would be used for metric-specific processing
        _ = metric_type
        if metric_name not in self.metrics:
            self.metrics[metric_name] = {}
            for window_name, duration in self.window_definitions:
                self.metrics[metric_name][window_name] = MetricWindow(
                    name=window_name, duration=duration
                )

    def record_metric(
        self, metric_name: str, value: float, metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Record a metric data point."""
        if metric_name not in self.metrics:
            raise ValueError(f"Metric '{metric_name}' not registered")

        data_point = MetricDataPoint(
            timestamp=datetime.now(), value=value, metadata=metadata or {}
        )

        # Add to all windows
        for window in self.metrics[metric_name].values():
            window.add_point(data_point)

        # Check for alerts
        self._check_alerts(metric_name)

    def _check_alerts(self, metric_name: str) -> None:
        """Check if metric triggers any alerts."""
        if metric_name not in self.alert_thresholds:
            return

        threshold_config = self.alert_thresholds[metric_name]
        window_name = threshold_config["window"]

        if metric_name in self.metrics and window_name in self.metrics[metric_name]:
            window = self.metrics[metric_name][window_name]
            stats = window.get_statistics()

            if stats["count"] == 0:
                return

            aggregation = threshold_config["aggregation"]
            current_value = stats[aggregation]
            comparison = threshold_config.get("comparison", "greater_than")

            alert_level = None
            threshold_value = None

            if comparison == "greater_than":
                if current_value > threshold_config["critical"]:
                    alert_level = "critical"
                    threshold_value = threshold_config["critical"]
                elif current_value > threshold_config["warning"]:
                    alert_level = "warning"
                    threshold_value = threshold_config["warning"]
            else:  # less_than
                if current_value < threshold_config["critical"]:
                    alert_level = "critical"
                    threshold_value = threshold_config["critical"]
                elif current_value < threshold_config["warning"]:
                    alert_level = "warning"
                    threshold_value = threshold_config["warning"]

            if alert_level:
                alert = {
                    "timestamp": datetime.now(),
                    "metric": metric_name,
                    "level": alert_level,
                    "current_value": current_value,
                    "threshold": threshold_value,
                    "window": window_name,
                    "aggregation": aggregation,
                    "message": f"{metric_name} {aggregation} is {current_value:.2f} ({alert_level} threshold: {threshold_value})",
                }

                self.alerts.append(alert)
                self._trigger_alert_callbacks(alert)

    def _trigger_alert_callbacks(self, alert: Dict[str, Any]) -> None:
        """Trigger registered alert callbacks."""
        for callback in self.alert_callbacks:
            try:
                callback(alert)
            except (ValueError, RuntimeError, AttributeError):
                print("Error in alert callback")

    def add_alert_callback(self, callback: Callable) -> None:
        """Add a callback function for alerts."""
        self.alert_callbacks.append(callback)

    def get_metric_statistics(
        self, metric_name: str, window: str = "5min"
    ) -> Dict[str, float]:
        """Get current statistics for a metric."""
        if metric_name not in self.metrics or window not in self.metrics[metric_name]:
            return {}

        return self.metrics[metric_name][window].get_statistics()

    def get_all_metrics_summary(self) -> Dict[str, Dict[str, Any]]:
        """Get summary of all monitored metrics."""
        summary: Dict[str, Any] = {}

        for metric_name, windows in self.metrics.items():
            summary[metric_name] = {}
            for window_name, window in windows.items():
                summary[metric_name][window_name] = window.get_statistics()

        return summary

    def save_metrics_snapshot(self) -> None:
        """Save current metrics snapshot to file."""
        timestamp = datetime.now()
        snapshot = {
            "timestamp": timestamp.isoformat(),
            "metrics": self.get_all_metrics_summary(),
            "active_alerts": [
                {
                    "timestamp": alert["timestamp"].isoformat(),
                    "metric": alert["metric"],
                    "level": alert["level"],
                    "message": alert["message"],
                }
                for alert in self.alerts
                if timestamp - alert["timestamp"]
                < timedelta(minutes=30)  # Recent alerts only
            ],
        }

        # Save daily snapshots
        snapshot_file = (
            self.monitoring_dir
            / f"metrics_snapshot_{timestamp.strftime('%Y%m%d')}.json"
        )

        # Load existing snapshots for the day
        existing_snapshots = []
        if snapshot_file.exists():
            with open(snapshot_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                existing_snapshots = data.get("snapshots", [])

        # Append new snapshot
        existing_snapshots.append(snapshot)

        # Save updated file
        with open(snapshot_file, "w", encoding="utf-8") as f:
            json.dump({"snapshots": existing_snapshots}, f, indent=2, default=str)

    async def start_monitoring(self, interval_seconds: int = 60) -> None:
        """Start continuous monitoring."""
        self.monitoring_active = True

        # Register all standard metrics
        self._register_standard_metrics()

        print("Performance monitoring started...")

        while self.monitoring_active:
            try:
                # Collect metrics from various sources
                await self._collect_metrics()

                # Save snapshot periodically
                self.save_metrics_snapshot()

                # Wait for next collection interval
                await asyncio.sleep(interval_seconds)

            except (ValueError, TypeError, KeyError) as e:
                print(f"Error in monitoring loop: {e}")
                await asyncio.sleep(interval_seconds)

    def stop_monitoring(self) -> None:
        """Stop continuous monitoring."""
        self.monitoring_active = False
        print("Performance monitoring stopped.")

    def _register_standard_metrics(self) -> None:
        """Register standard healthcare metrics."""
        standard_metrics = [
            ("api_latency", MetricType.LATENCY),
            ("fhir_validation_latency", MetricType.LATENCY),
            ("hl7_parsing_latency", MetricType.LATENCY),
            ("terminology_lookup_latency", MetricType.LATENCY),
            ("translation_accuracy", MetricType.ACCURACY),
            ("error_rate", MetricType.ERROR_RATE),
            ("system_availability", MetricType.AVAILABILITY),
            ("blockchain_transaction_time", MetricType.LATENCY),
            ("document_retrieval_time", MetricType.LATENCY),
            ("offline_sync_time", MetricType.LATENCY),
        ]

        for metric_name, metric_type in standard_metrics:
            self.register_metric(metric_name, metric_type)

    async def _collect_metrics(self) -> None:
        """Collect metrics from various sources."""
        # This would integrate with actual system components
        # For now, we'll simulate metric collection

        # Simulate API latency
        self.record_metric("api_latency", 250 + (time.time() % 100))

        # Simulate validation latency
        self.record_metric("fhir_validation_latency", 30 + (time.time() % 20))

        # Simulate translation accuracy
        self.record_metric("translation_accuracy", 99.5 + (time.time() % 0.5))

        # Simulate error rate
        self.record_metric("error_rate", 0.1 + (time.time() % 0.5))

        # Simulate availability
        self.record_metric("system_availability", 99.95 + (time.time() % 0.05))

    def generate_performance_dashboard(self) -> Dict[str, Any]:
        """Generate data for performance dashboard."""
        current_time = datetime.now()

        dashboard: Dict[str, Any] = {
            "generated_at": current_time.isoformat(),
            "metrics": {},
            "alerts": {"active": [], "recent": []},
            "trends": {},
            "health_score": self._calculate_health_score(),
        }

        # Add current metrics
        for metric_name, windows in self.metrics.items():
            dashboard["metrics"][metric_name] = {
                "current": (
                    windows["1min"].get_statistics() if "1min" in windows else {}
                ),
                "5min": windows["5min"].get_statistics() if "5min" in windows else {},
                "1hour": (
                    windows["1hour"].get_statistics() if "1hour" in windows else {}
                ),
            }

        # Add alerts
        for alert in self.alerts:
            alert_age = current_time - alert["timestamp"]
            alert_data = {
                "timestamp": alert["timestamp"].isoformat(),
                "metric": alert["metric"],
                "level": alert["level"],
                "message": alert["message"],
            }

            if alert_age < timedelta(minutes=5):
                dashboard["alerts"]["active"].append(alert_data)
            elif alert_age < timedelta(hours=1):
                dashboard["alerts"]["recent"].append(alert_data)

        return dashboard

    def _calculate_health_score(self) -> float:
        """Calculate overall system health score (0-100)."""
        score = 100.0

        # Deduct points for active alerts
        recent_alerts = [
            alert
            for alert in self.alerts
            if datetime.now() - alert["timestamp"] < timedelta(minutes=30)
        ]

        for alert in recent_alerts:
            if alert["level"] == "critical":
                score -= 10
            elif alert["level"] == "warning":
                score -= 5

        # Ensure score doesn't go below 0
        return max(0, score)


# Example usage and monitoring setup
if __name__ == "__main__":

    async def example_monitoring() -> None:
        """Run example performance monitoring demonstration."""
        monitor = PerformanceMonitor()

        # Add alert callback
        def alert_handler(alert: Dict[str, Any]) -> None:
            print(f"ALERT: {alert['level'].upper()} - {alert['message']}")

        monitor.add_alert_callback(alert_handler)

        # Start monitoring
        monitoring_task = asyncio.create_task(
            monitor.start_monitoring(interval_seconds=5)
        )

        # Run for a while
        await asyncio.sleep(30)

        # Generate dashboard
        dashboard = monitor.generate_performance_dashboard()
        print(f"\nDashboard Health Score: {dashboard['health_score']}")

        # Stop monitoring
        monitor.stop_monitoring()
        await monitoring_task

    asyncio.run(example_monitoring())
