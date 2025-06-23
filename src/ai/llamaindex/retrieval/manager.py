"""
Pipeline Management Module.

Provides tools for managing, routing, and monitoring retrieval pipelines.
"""

import logging
import random
import threading
import time
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional, Tuple

from .base import QueryContext, RetrievalPipeline, RetrievalResult

logger = logging.getLogger(__name__)


class PipelineManager:
    """
    Manages multiple retrieval pipelines.

    Features:
    - Pipeline registration and lifecycle
    - Performance monitoring
    - Health checks
    - Configuration management
    """

    def __init__(self) -> None:
        """Initialize the pipeline manager."""
        self.pipelines: Dict[str, RetrievalPipeline] = {}
        self.pipeline_configs: Dict[str, Any] = {}
        self.pipeline_stats: Dict[str, Dict[str, Any]] = defaultdict(dict)
        self._lock = threading.Lock()
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    def register_pipeline(
        self,
        name: str,
        pipeline: RetrievalPipeline,
        config: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Register a pipeline."""
        with self._lock:
            self.pipelines[name] = pipeline
            self.pipeline_configs[name] = config or {}
            self.pipeline_stats[name] = {
                "registered_at": datetime.now(),
                "total_queries": 0,
                "total_time_ms": 0.0,
                "error_count": 0,
                "last_used": None,
            }
            self.logger.info("Registered pipeline: %s", name)

    def unregister_pipeline(self, name: str) -> None:
        """Unregister a pipeline."""
        with self._lock:
            if name in self.pipelines:
                del self.pipelines[name]
                del self.pipeline_configs[name]
                del self.pipeline_stats[name]
                self.logger.info("Unregistered pipeline: %s", name)

    def get_pipeline(self, name: str) -> Optional[RetrievalPipeline]:
        """Get a registered pipeline."""
        return self.pipelines.get(name)

    def list_pipelines(self) -> List[str]:
        """List all registered pipelines."""
        return list(self.pipelines.keys())

    async def retrieve(
        self, pipeline_name: str, query_context: QueryContext
    ) -> List[RetrievalResult]:
        """Retrieve using specified pipeline."""
        pipeline = self.get_pipeline(pipeline_name)
        if not pipeline:
            raise ValueError(f"Pipeline not found: {pipeline_name}")

        start_time = time.time()

        try:
            # Execute retrieval
            results = await pipeline.retrieve(query_context)

            # Update stats
            elapsed_ms = (time.time() - start_time) * 1000
            self._update_stats(pipeline_name, elapsed_ms, len(results), success=True)

            return results

        except Exception as e:
            self.logger.error("Pipeline %s failed: %s", pipeline_name, e)
            self._update_stats(pipeline_name, 0, 0, success=False)
            raise

    def _update_stats(
        self, pipeline_name: str, elapsed_ms: float, num_results: int, success: bool
    ) -> None:
        """Update pipeline statistics."""
        with self._lock:
            stats = self.pipeline_stats[pipeline_name]
            stats["total_queries"] += 1
            stats["last_used"] = datetime.now()

            if success:
                stats["total_time_ms"] += elapsed_ms
                stats["last_query_time_ms"] = elapsed_ms
                stats["last_num_results"] = num_results
            else:
                stats["error_count"] += 1
                stats["last_error"] = datetime.now()

    def get_statistics(self) -> Dict[str, Any]:
        """Get statistics for all pipelines."""
        with self._lock:
            stats = {}

            for name, pipeline_stats in self.pipeline_stats.items():
                avg_time = (
                    pipeline_stats["total_time_ms"] / pipeline_stats["total_queries"]
                    if pipeline_stats["total_queries"] > 0
                    else 0
                )

                stats[name] = {
                    "total_queries": pipeline_stats["total_queries"],
                    "average_time_ms": avg_time,
                    "error_rate": (
                        pipeline_stats["error_count"] / pipeline_stats["total_queries"]
                        if pipeline_stats["total_queries"] > 0
                        else 0
                    ),
                    "last_used": pipeline_stats["last_used"],
                    "status": self._get_pipeline_status(name),
                }

            return stats

    def _get_pipeline_status(self, name: str) -> str:
        """Get current status of a pipeline."""
        stats = self.pipeline_stats[name]

        # Check if recently used
        if stats["last_used"]:
            time_since_use = datetime.now() - stats["last_used"]
            if time_since_use < timedelta(minutes=5):
                return "active"
            elif time_since_use < timedelta(hours=1):
                return "idle"

        # Check error rate
        if stats["total_queries"] > 0:
            error_rate = stats["error_count"] / stats["total_queries"]
            if error_rate > 0.1:  # 10% error rate
                return "degraded"

        return "healthy"

    def health_check(self) -> Dict[str, Dict[str, Any]]:
        """Perform health check on all pipelines."""
        health_status = {}

        for name, pipeline in self.pipelines.items():
            try:
                # Get pipeline metrics
                metrics = pipeline.get_metrics()

                # Check health indicators
                status = "healthy"
                issues = []

                # Check average query time
                if metrics.get("average_time_ms", 0) > 2000:
                    status = "degraded"
                    issues.append("High average query time")

                # Check cache hit rate
                if (
                    metrics.get("cache_hit_rate", 0) < 0.1
                    and metrics.get("total_queries", 0) > 100
                ):
                    issues.append("Low cache hit rate")

                # Check pipeline-specific health
                pipeline_status = self._get_pipeline_status(name)
                if pipeline_status != "healthy":
                    status = pipeline_status

                health_status[name] = {
                    "status": status,
                    "metrics": metrics,
                    "issues": issues,
                    "last_checked": datetime.now(),
                }

            except (AttributeError, ValueError) as e:
                health_status[name] = {
                    "status": "error",
                    "error": str(e),
                    "last_checked": datetime.now(),
                }

        return health_status


class PipelineRouter:
    """
    Routes queries to appropriate pipelines.

    Features:
    - Content-based routing
    - Load balancing
    - Fallback handling
    """

    def __init__(
        self,
        manager: PipelineManager,
        routing_strategy: str = "content_based",  # content_based, round_robin, weighted
    ):
        """Initialize the pipeline router."""
        self.manager = manager
        self.routing_strategy = routing_strategy
        self.routing_rules: List[Dict[str, Any]] = []
        self._round_robin_index = 0
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    def add_routing_rule(
        self,
        condition: Callable[[QueryContext], bool],
        pipeline_name: str,
        priority: int = 0,
    ) -> None:
        """Add a routing rule."""
        self.routing_rules.append(
            {"condition": condition, "pipeline": pipeline_name, "priority": priority}
        )

        # Sort by priority (higher first)
        self.routing_rules.sort(key=lambda r: r["priority"], reverse=True)

    async def route_query(self, query_context: QueryContext) -> List[RetrievalResult]:
        """Route query to appropriate pipeline."""
        pipeline_name = self._select_pipeline(query_context)

        if not pipeline_name:
            raise ValueError("No suitable pipeline found for query")

        self.logger.info("Routing query to pipeline: %s", pipeline_name)

        try:
            return await self.manager.retrieve(pipeline_name, query_context)
        except Exception:  # pylint: disable=broad-except
            # Try fallback if available
            fallback = self._get_fallback_pipeline(pipeline_name)
            if fallback:
                self.logger.warning(
                    "Falling back from %s to %s", pipeline_name, fallback
                )
                return await self.manager.retrieve(fallback, query_context)
            raise

    def _select_pipeline(self, query_context: QueryContext) -> Optional[str]:
        """Select pipeline based on routing strategy."""
        if self.routing_strategy == "content_based":
            return self._content_based_routing(query_context)
        elif self.routing_strategy == "round_robin":
            return self._round_robin_routing()
        elif self.routing_strategy == "weighted":
            return self._weighted_routing()
        else:
            # Default to first available
            pipelines = self.manager.list_pipelines()
            return pipelines[0] if pipelines else None

    def _content_based_routing(self, query_context: QueryContext) -> Optional[str]:
        """Route based on query content."""
        # Check routing rules
        for rule in self.routing_rules:
            if rule["condition"](query_context):
                return str(rule["pipeline"])

        # Default routing based on query metadata
        if query_context.urgency_level >= 4:
            # High urgency - route to emergency pipeline if available
            if "emergency" in self.manager.pipelines:
                return "emergency"

        if query_context.medical_specialty:
            # Route to specialty-specific pipeline
            specialty_pipeline = f"{query_context.medical_specialty}_pipeline"
            if specialty_pipeline in self.manager.pipelines:
                return specialty_pipeline

        # Default pipeline
        if "default" in self.manager.pipelines:
            return "default"

        # Any available pipeline
        pipelines = self.manager.list_pipelines()
        return pipelines[0] if pipelines else None

    def _round_robin_routing(self) -> Optional[str]:
        """Round-robin routing."""
        pipelines = self.manager.list_pipelines()
        if not pipelines:
            return None

        pipeline = pipelines[self._round_robin_index % len(pipelines)]
        self._round_robin_index += 1

        return pipeline

    def _weighted_routing(self) -> Optional[str]:
        """Weighted routing based on performance."""
        stats = self.manager.get_statistics()
        if not stats:
            return None

        # Calculate weights based on performance
        weights = {}
        for name, pipeline_stats in stats.items():
            # Lower average time = higher weight
            avg_time = pipeline_stats.get("average_time_ms", 1000)
            error_rate = pipeline_stats.get("error_rate", 0)

            # Penalize high error rates
            weight = 1000 / (avg_time + 1) * (1 - error_rate)
            weights[name] = weight

        total_weight = sum(weights.values())
        if total_weight == 0:
            return None

        rand = random.uniform(0, total_weight)
        cumulative = 0

        for name, weight in weights.items():
            cumulative += weight
            if rand <= cumulative:
                return name

        return list(weights.keys())[0]

    def _get_fallback_pipeline(self, failed_pipeline: str) -> Optional[str]:
        """Get fallback pipeline for a failed one."""
        # Simple fallback logic
        fallback_map = {
            "advanced": "basic",
            "medical": "general",
            "emergency": "medical",
        }

        if failed_pipeline in fallback_map:
            fallback = fallback_map[failed_pipeline]
            if fallback in self.manager.pipelines:
                return fallback

        # Any other available pipeline
        for name in self.manager.list_pipelines():
            if name != failed_pipeline:
                return name

        return None


class PipelineMonitor:
    """
    Monitors pipeline performance and health.

    Features:
    - Real-time monitoring
    - Performance alerts
    - Trend analysis
    """

    def __init__(
        self,
        manager: PipelineManager,
        alert_thresholds: Optional[Dict[str, float]] = None,
    ):
        """Initialize the pipeline monitor."""
        self.manager = manager
        self.alert_thresholds = alert_thresholds or {
            "avg_query_time_ms": 2000,
            "error_rate": 0.1,
            "cache_hit_rate_min": 0.2,
        }

        self.alerts: List[Dict[str, Any]] = []
        self.metrics_history: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        self._monitoring = False
        self._monitor_thread: Optional[threading.Thread] = None

        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    def start_monitoring(self, interval_seconds: int = 60) -> None:
        """Start monitoring pipelines."""
        if self._monitoring:
            return

        self._monitoring = True
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop, args=(interval_seconds,), daemon=True
        )
        self._monitor_thread.start()
        self.logger.info("Started monitoring with %ds interval", interval_seconds)

    def stop_monitoring(self) -> None:
        """Stop monitoring."""
        self._monitoring = False
        if self._monitor_thread:
            self._monitor_thread.join()
        self.logger.info("Stopped monitoring")

    def _monitor_loop(self, interval: int) -> None:
        """Run monitoring loop."""
        while self._monitoring:
            try:
                self._collect_metrics()
                self._check_alerts()
                time.sleep(interval)
            except (RuntimeError, ValueError) as e:
                self.logger.error("Monitoring error: %s", e)

    def _collect_metrics(self) -> None:
        """Collect metrics from all pipelines."""
        timestamp = datetime.now()
        stats = self.manager.get_statistics()

        for pipeline_name, pipeline_stats in stats.items():
            # Add to history
            self.metrics_history[pipeline_name].append(
                {"timestamp": timestamp, "stats": pipeline_stats}
            )

            # Keep only last 24 hours
            cutoff = timestamp - timedelta(hours=24)
            self.metrics_history[pipeline_name] = [
                m
                for m in self.metrics_history[pipeline_name]
                if m["timestamp"] > cutoff
            ]

    def _check_alerts(self) -> None:
        """Check for alert conditions."""
        current_stats = self.manager.get_statistics()

        for pipeline_name, stats in current_stats.items():
            # Check average query time
            avg_time = stats.get("average_time_ms", 0)
            if avg_time > self.alert_thresholds["avg_query_time_ms"]:
                self._create_alert(
                    pipeline_name,
                    "high_query_time",
                    f"Average query time {avg_time:.0f}ms exceeds threshold",
                    "warning",
                )

            # Check error rate
            error_rate = stats.get("error_rate", 0)
            if error_rate > self.alert_thresholds["error_rate"]:
                self._create_alert(
                    pipeline_name,
                    "high_error_rate",
                    f"Error rate {error_rate:.1%} exceeds threshold",
                    "critical",
                )

            # Check degraded status
            if stats.get("status") == "degraded":
                self._create_alert(
                    pipeline_name,
                    "degraded_status",
                    "Pipeline status is degraded",
                    "warning",
                )

    def _create_alert(
        self, pipeline_name: str, alert_type: str, message: str, severity: str
    ) -> None:
        """Create an alert."""
        alert = {
            "timestamp": datetime.now(),
            "pipeline": pipeline_name,
            "type": alert_type,
            "message": message,
            "severity": severity,
            "resolved": False,
        }

        # Check if similar alert already exists
        for existing in self.alerts:
            if (
                not existing["resolved"]
                and existing["pipeline"] == pipeline_name
                and existing["type"] == alert_type
            ):
                # Update existing alert
                existing["timestamp"] = alert["timestamp"]
                existing["message"] = alert["message"]
                return

        # Add new alert
        self.alerts.append(alert)
        self.logger.warning("Alert: %s - %s", pipeline_name, message)

    def get_alerts(
        self,
        pipeline_name: Optional[str] = None,
        unresolved_only: bool = True,
        severity: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Get alerts."""
        alerts = self.alerts

        if pipeline_name:
            alerts = [a for a in alerts if a["pipeline"] == pipeline_name]

        if unresolved_only:
            alerts = [a for a in alerts if not a["resolved"]]

        if severity:
            alerts = [a for a in alerts if a["severity"] == severity]

        return alerts

    def resolve_alert(self, alert_index: int) -> None:
        """Resolve an alert."""
        if 0 <= alert_index < len(self.alerts):
            self.alerts[alert_index]["resolved"] = True
            self.alerts[alert_index]["resolved_at"] = datetime.now()

    def get_performance_trends(
        self, pipeline_name: str, metric: str = "average_time_ms", hours: int = 24
    ) -> List[Tuple[datetime, float]]:
        """Get performance trends for a pipeline."""
        if pipeline_name not in self.metrics_history:
            return []

        cutoff = datetime.now() - timedelta(hours=hours)
        trends = []

        for entry in self.metrics_history[pipeline_name]:
            if entry["timestamp"] > cutoff:
                value = entry["stats"].get(metric, 0)
                trends.append((entry["timestamp"], value))

        return trends

    def generate_report(self) -> Dict[str, Any]:
        """Generate monitoring report."""
        report: Dict[str, Any] = {
            "timestamp": datetime.now(),
            "pipelines": {},
            "alerts": {
                "total": len(self.alerts),
                "unresolved": len([a for a in self.alerts if not a["resolved"]]),
                "critical": len(
                    [
                        a
                        for a in self.alerts
                        if a["severity"] == "critical" and not a["resolved"]
                    ]
                ),
            },
            "recommendations": [],
        }

        # Analyze each pipeline
        for name in self.manager.list_pipelines():
            stats = self.manager.get_statistics().get(name, {})
            health = self.manager.health_check().get(name, {})

            report["pipelines"][name] = {
                "status": health.get("status", "unknown"),
                "total_queries": stats.get("total_queries", 0),
                "average_time_ms": stats.get("average_time_ms", 0),
                "error_rate": stats.get("error_rate", 0),
                "issues": health.get("issues", []),
            }

            # Generate recommendations
            if stats.get("average_time_ms", 0) > 1500:
                report["recommendations"].append(
                    f"Consider optimizing {name} pipeline - high average query time"
                )

            if stats.get("error_rate", 0) > 0.05:
                report["recommendations"].append(
                    f"Investigate errors in {name} pipeline - {stats['error_rate']:.1%} error rate"
                )

        return report
