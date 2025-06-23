"""Translation Performance Monitoring."""

import json
import statistics
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import psutil

from src.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class PerformanceMetric:
    """A single performance metric measurement."""

    timestamp: datetime
    metric_type: str
    value: float
    language_pair: Optional[str] = None
    model_id: Optional[str] = None
    request_size: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PerformanceAlert:
    """Performance alert when thresholds are exceeded."""

    alert_id: str
    timestamp: datetime
    metric_type: str
    current_value: float
    threshold: float
    severity: str
    message: str
    resolved: bool = False
    resolved_at: Optional[datetime] = None


class TranslationPerformanceMonitor:
    """Monitors translation system performance."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize performance monitor."""
        self.config = config or self._get_default_config()
        self.metrics: Dict[str, deque] = defaultdict(lambda: deque(maxlen=10000))
        self.alerts: List[PerformanceAlert] = []
        self.alert_thresholds = self.config["alert_thresholds"]
        self.monitoring_active = False
        self.monitor_thread: Optional[threading.Thread] = None
        self._load_historical_data()

    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration."""
        return {
            "alert_thresholds": {
                "latency": {"warning": 1000, "critical": 2000},  # ms  # ms
                "error_rate": {"warning": 0.05, "critical": 0.1},  # 5%  # 10%
                "throughput": {
                    "warning": 10,  # requests/sec (low)
                    "critical": 5,  # requests/sec (very low)
                },
                "cpu": {"warning": 80, "critical": 95},  # %  # %
                "memory": {"warning": 80, "critical": 95},  # %  # %
            },
            "monitoring_interval": 60,  # seconds
            "data_retention_days": 30,
            "alert_cooldown_minutes": 15,
        }

    def _load_historical_data(self) -> None:
        """Load historical metrics from storage."""
        # In production, would load from time-series database

    def record_translation_request(
        self,
        start_time: float,
        end_time: float,
        language_pair: str,
        model_id: str,
        request_size: int,
        success: bool,
        error: Optional[str] = None,
    ) -> None:
        """Record metrics for a translation request."""
        timestamp = datetime.now()

        # Record latency
        latency = (end_time - start_time) * 1000  # Convert to ms
        self.metrics["latency"].append(
            PerformanceMetric(
                timestamp=timestamp,
                metric_type="latency",
                value=latency,
                language_pair=language_pair,
                model_id=model_id,
                request_size=request_size,
            )
        )

        # Record success/error
        if not success:
            self.metrics["errors"].append(
                PerformanceMetric(
                    timestamp=timestamp,
                    metric_type="error",
                    value=1,
                    language_pair=language_pair,
                    model_id=model_id,
                    metadata={"error": error},
                )
            )

        # Check thresholds
        self._check_thresholds("latency", latency)

    def _check_thresholds(self, metric_type: str, value: float) -> None:
        """Check if metric exceeds thresholds."""
        if metric_type not in self.alert_thresholds:
            return

        thresholds = self.alert_thresholds[metric_type]
        severity = None
        threshold = None

        if value >= thresholds.get("critical", float("inf")):
            severity = "critical"
            threshold = thresholds["critical"]
        elif value >= thresholds.get("warning", float("inf")):
            severity = "warning"
            threshold = thresholds["warning"]

        if severity and threshold is not None:
            self._create_alert(metric_type, value, threshold, severity)

    def _create_alert(
        self, metric_type: str, value: float, threshold: float, severity: str
    ) -> None:
        """Create a performance alert."""
        # Check for recent similar alerts (cooldown)
        recent_alerts = [
            a
            for a in self.alerts
            if (
                a.metric_type == metric_type
                and not a.resolved
                and (datetime.now() - a.timestamp).total_seconds()
                < self.config["alert_cooldown_minutes"] * 60
            )
        ]

        if recent_alerts:
            return  # Don't create duplicate alerts

        alert = PerformanceAlert(
            alert_id=f"alert_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{metric_type}",
            timestamp=datetime.now(),
            metric_type=metric_type,
            current_value=value,
            threshold=threshold,
            severity=severity,
            message=f"{metric_type} {value:.2f} exceeds {severity} threshold {threshold}",
        )

        self.alerts.append(alert)
        logger.warning(f"Performance alert: {alert.message}")

    def get_metrics_summary(
        self, metric_type: str, minutes: int = 60, language_pair: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get summary statistics for a metric."""
        cutoff_time = datetime.now() - timedelta(minutes=minutes)

        # Filter metrics
        metrics = [
            m for m in self.metrics.get(metric_type, []) if m.timestamp >= cutoff_time
        ]

        if language_pair:
            metrics = [m for m in metrics if m.language_pair == language_pair]

        if not metrics:
            return {"metric_type": metric_type, "period_minutes": minutes, "count": 0}

        values = [m.value for m in metrics]

        return {
            "metric_type": metric_type,
            "period_minutes": minutes,
            "count": len(values),
            "mean": statistics.mean(values),
            "median": statistics.median(values),
            "min": min(values),
            "max": max(values),
            "std_dev": statistics.stdev(values) if len(values) > 1 else 0,
            "p95": self._percentile(values, 95),
            "p99": self._percentile(values, 99),
        }

    def _percentile(self, values: List[float], percentile: float) -> float:
        """Calculate percentile of values."""
        if not values:
            return 0

        sorted_values = sorted(values)
        index = int(len(sorted_values) * percentile / 100)
        return sorted_values[min(index, len(sorted_values) - 1)]

    def get_error_rate(self, minutes: int = 60) -> float:
        """Calculate error rate over time period."""
        cutoff_time = datetime.now() - timedelta(minutes=minutes)

        # Count total requests
        total_requests = len(
            [m for m in self.metrics.get("latency", []) if m.timestamp >= cutoff_time]
        )

        # Count errors
        errors = len(
            [m for m in self.metrics.get("errors", []) if m.timestamp >= cutoff_time]
        )

        return errors / max(total_requests, 1)

    def get_throughput(self, minutes: int = 5) -> float:
        """Calculate throughput (requests per second)."""
        cutoff_time = datetime.now() - timedelta(minutes=minutes)

        requests = [
            m for m in self.metrics.get("latency", []) if m.timestamp >= cutoff_time
        ]

        if not requests:
            return 0

        time_span = (datetime.now() - cutoff_time).total_seconds()
        return len(requests) / max(time_span, 1)

    def start_monitoring(self) -> None:
        """Start background monitoring thread."""
        if self.monitoring_active:
            return

        self.monitoring_active = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop)
        self.monitor_thread.daemon = True
        self.monitor_thread.start()

        logger.info("Performance monitoring started")

    def stop_monitoring(self) -> None:
        """Stop background monitoring."""
        self.monitoring_active = False
        if self.monitor_thread is not None:
            self.monitor_thread.join(timeout=5)

        logger.info("Performance monitoring stopped")

    def _monitor_loop(self) -> None:
        """Background monitoring loop."""
        while self.monitoring_active:
            try:
                # Monitor system resources
                self._monitor_system_resources()

                # Check metrics and alerts
                self._check_metric_health()

                # Sleep until next check
                time.sleep(self.config["monitoring_interval"])

            except (ImportError, RuntimeError, AttributeError) as e:
                logger.error(f"Error in monitoring loop: {e}")

    def _monitor_system_resources(self) -> None:
        """Monitor CPU and memory usage."""
        try:

            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            self.metrics["cpu"].append(
                PerformanceMetric(
                    timestamp=datetime.now(), metric_type="cpu", value=cpu_percent
                )
            )
            self._check_thresholds("cpu", cpu_percent)

            # Memory usage
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            self.metrics["memory"].append(
                PerformanceMetric(
                    timestamp=datetime.now(), metric_type="memory", value=memory_percent
                )
            )
            self._check_thresholds("memory", memory_percent)

        except ImportError:
            pass  # psutil not available

    def _check_metric_health(self) -> None:
        """Check overall metrics health."""
        # Check error rate
        error_rate = self.get_error_rate(minutes=5)
        self._check_thresholds("error_rate", error_rate)

        # Check throughput
        throughput = self.get_throughput(minutes=5)
        if throughput < self.alert_thresholds["throughput"]["critical"]:
            self._create_alert(
                "throughput",
                throughput,
                self.alert_thresholds["throughput"]["critical"],
                "critical",
            )

    def export_metrics(self, output_path: str) -> None:
        """Export metrics to file."""
        data: Dict[str, Any] = {
            "exported_at": datetime.now().isoformat(),
            "metrics": {},
            "alerts": [
                {
                    "alert_id": a.alert_id,
                    "timestamp": a.timestamp.isoformat(),
                    "metric_type": a.metric_type,
                    "current_value": a.current_value,
                    "threshold": a.threshold,
                    "severity": a.severity,
                    "message": a.message,
                    "resolved": a.resolved,
                }
                for a in self.alerts[-100:]  # Last 100 alerts
            ],
        }

        # Export recent metrics
        for metric_type, _metrics in self.metrics.items():
            data["metrics"][metric_type] = self.get_metrics_summary(metric_type)

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

        logger.info(f"Exported metrics to {output_path}")
