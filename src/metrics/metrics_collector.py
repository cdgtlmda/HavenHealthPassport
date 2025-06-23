"""Metrics Collection Module.

This module provides metrics collection functionality for the Haven Health Passport system.
"""

import logging
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class MetricType(Enum):
    """Types of metrics collected in the system."""

    DOCUMENT_ENHANCEMENT = "document_enhancement"
    DOCUMENT_CLASSIFICATION = "document_classification"
    TRANSLATION = "translation"
    VOICE_PROCESSING = "voice_processing"
    API_REQUEST = "api_request"
    ERROR = "error"
    PERFORMANCE = "performance"
    SECURITY = "security"
    BLOCKCHAIN = "blockchain"


class MetricsCollector:
    """Collects and manages system metrics."""

    def __init__(self) -> None:
        """Initialize the metrics collector."""
        self.metrics: List[Dict[str, Any]] = []

    def record_metric(
        self,
        metric_type: MetricType,
        data: Dict[str, Any],
        timestamp: Optional[datetime] = None,
    ) -> None:
        """
        Record a metric.

        Args:
            metric_type: Type of metric being recorded
            data: Metric data as a dictionary
            timestamp: Optional timestamp (uses current time if not provided)
        """
        if timestamp is None:
            timestamp = datetime.utcnow()

        metric = {
            "type": metric_type.value,
            "data": data,
            "timestamp": timestamp.isoformat(),
        }

        self.metrics.append(metric)
        logger.debug("Recorded %s metric: %s", metric_type.value, data)

    def get_metrics(self, metric_type: Optional[MetricType] = None) -> list:
        """
        Get recorded metrics.

        Args:
            metric_type: Optional filter by metric type

        Returns:
            List of metrics
        """
        if metric_type:
            return [m for m in self.metrics if m["type"] == metric_type.value]
        return self.metrics
