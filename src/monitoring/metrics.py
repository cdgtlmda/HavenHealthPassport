"""Metrics collection module for monitoring."""

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional


@dataclass
class Metric:
    """Represents a single metric."""

    name: str
    value: float
    timestamp: datetime
    tags: Optional[Dict[str, str]] = None

    def __post_init__(self) -> None:
        """Initialize default values for mutable attributes."""
        if self.tags is None:
            self.tags = {}


class MetricsCollector:
    """Collects and manages system metrics."""

    def __init__(self) -> None:
        """Initialize metrics collector."""
        self.metrics: List[Metric] = []

    def record_metric(
        self, name: str, value: float, tags: Optional[Dict[str, str]] = None
    ) -> None:
        """Record a metric value."""
        metric = Metric(
            name=name, value=value, timestamp=datetime.now(), tags=tags or {}
        )
        self.metrics.append(metric)

    def get_metrics(self, name: Optional[str] = None) -> List[Metric]:
        """Get metrics by name."""
        if name:
            return [m for m in self.metrics if m.name == name]
        return self.metrics

    def clear_metrics(self) -> None:
        """Clear all collected metrics."""
        self.metrics.clear()
