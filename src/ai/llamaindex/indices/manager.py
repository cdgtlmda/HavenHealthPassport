"""
Index Management Module.

Provides tools for managing, monitoring, and optimizing indices.
"""

import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from .base import BaseVectorIndex, VectorIndexConfig

logger = logging.getLogger(__name__)


@dataclass
class IndexHealth:
    """Health status of an index."""

    index_name: str
    status: str  # healthy, degraded, unhealthy
    total_documents: int
    index_size_mb: float
    avg_query_time_ms: float
    error_rate: float
    last_optimization: Optional[datetime]
    issues: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)


class IndexManager:
    """
    Manages multiple vector indices.

    Features:
    - Index lifecycle management
    - Health monitoring
    - Automatic optimization
    - Load balancing
    """

    def __init__(self) -> None:
        """Initialize index manager."""
        self.indices: Dict[str, BaseVectorIndex] = {}
        self.index_configs: Dict[str, VectorIndexConfig] = {}
        self.health_status: Dict[str, IndexHealth] = {}
        self._lock = threading.Lock()
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    def register_index(
        self,
        name: str,
        index: BaseVectorIndex,
        config: Optional[VectorIndexConfig] = None,
    ) -> None:
        """Register an index with the manager."""
        with self._lock:
            self.indices[name] = index
            self.index_configs[name] = config or index.config
            self.logger.info("Registered index: %s", name)

    def unregister_index(self, name: str) -> None:
        """Unregister an index."""
        with self._lock:
            if name in self.indices:
                del self.indices[name]
                del self.index_configs[name]
                if name in self.health_status:
                    del self.health_status[name]
                self.logger.info("Unregistered index: %s", name)

    def get_index(self, name: str) -> Optional[BaseVectorIndex]:
        """Get a registered index."""
        return self.indices.get(name)

    def list_indices(self) -> List[str]:
        """List all registered indices."""
        return list(self.indices.keys())

    def get_health_status(
        self, index_name: Optional[str] = None
    ) -> Dict[str, IndexHealth]:
        """Get health status of indices."""
        if index_name:
            if index_name in self.indices:
                return {index_name: self._check_index_health(index_name)}
            return {}

        # Check all indices
        health_status = {}
        for name in self.indices:
            health_status[name] = self._check_index_health(name)

        return health_status

    def _check_index_health(self, name: str) -> IndexHealth:
        """Check health of a specific index."""
        index = self.indices[name]
        metrics = index.get_metrics()

        # Determine health status
        issues = []
        recommendations = []
        status = "healthy"

        # Check query performance
        if metrics.average_query_time_ms > 1000:
            status = "degraded"
            issues.append("High average query time")
            recommendations.append("Consider optimizing the index")

        # Check error rate
        total_operations = metrics.total_queries + metrics.total_documents
        if total_operations > 0:
            error_rate = metrics.error_count / total_operations
            if error_rate > 0.05:  # 5% error rate
                status = "unhealthy"
                issues.append(f"High error rate: {error_rate:.2%}")
                recommendations.append("Investigate error logs")
        else:
            error_rate = 0.0

        # Check optimization schedule
        if metrics.last_optimization:
            days_since_optimization = (datetime.now() - metrics.last_optimization).days
            if days_since_optimization > 7:
                if status == "healthy":
                    status = "degraded"
                issues.append(f"No optimization in {days_since_optimization} days")
                recommendations.append("Schedule index optimization")

        # Check index size
        if metrics.index_size_mb > 1000:  # 1GB
            recommendations.append("Consider sharding for large index")

        return IndexHealth(
            index_name=name,
            status=status,
            total_documents=metrics.total_documents,
            index_size_mb=metrics.index_size_mb,
            avg_query_time_ms=metrics.average_query_time_ms,
            error_rate=error_rate,
            last_optimization=metrics.last_optimization,
            issues=issues,
            recommendations=recommendations,
        )

    def optimize_index(self, name: str) -> bool:
        """Optimize a specific index."""
        if name not in self.indices:
            self.logger.error("Index not found: %s", name)
            return False

        index = self.indices[name]
        self.logger.info("Optimizing index: %s", name)

        return index.optimize()

    def optimize_all(self) -> Dict[str, bool]:
        """Optimize all indices."""
        results = {}

        for name in self.indices:
            results[name] = self.optimize_index(name)

        return results

    def backup_index(self, name: str, backup_path: str) -> bool:
        """Backup an index."""
        if name not in self.indices:
            return False

        index = self.indices[name]
        backup_dir = Path(backup_path) / name / datetime.now().strftime("%Y%m%d_%H%M%S")

        return index.persist(str(backup_dir))

    def restore_index(self, name: str, backup_path: str) -> bool:
        """Restore an index from backup."""
        if name not in self.indices:
            return False

        index = self.indices[name]
        return index.load(backup_path)

    def get_statistics(self) -> Dict[str, Any]:
        """Get overall statistics."""
        stats: Dict[str, Any] = {
            "total_indices": len(self.indices),
            "total_documents": 0,
            "total_queries": 0,
            "avg_query_time_ms": 0.0,
            "indices": {},
        }

        total_query_time = 0.0
        total_queries = 0

        for name, index in self.indices.items():
            metrics = index.get_metrics()

            stats["total_documents"] += metrics.total_documents
            stats["total_queries"] += metrics.total_queries

            total_query_time += metrics.average_query_time_ms * metrics.total_queries
            total_queries += metrics.total_queries

            stats["indices"][name] = {
                "documents": metrics.total_documents,
                "queries": metrics.total_queries,
                "avg_query_time_ms": metrics.average_query_time_ms,
                "cache_hit_rate": metrics.cache_hit_rate,
            }

        if total_queries > 0:
            stats["avg_query_time_ms"] = total_query_time / total_queries

        return stats


class IndexOptimizer:
    """
    Automatic index optimization.

    Features:
    - Performance analysis
    - Automatic tuning
    - Resource optimization
    """

    def __init__(self, manager: IndexManager):
        """Initialize index optimizer."""
        self.manager = manager
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self.optimization_history: Dict[str, List[Dict[str, Any]]] = {}

    def analyze_index(self, index_name: str) -> Dict[str, Any]:
        """Analyze index performance."""
        if index_name not in self.manager.indices:
            return {}

        index = self.manager.indices[index_name]
        metrics = index.get_metrics()
        config = self.manager.index_configs[index_name]

        analysis: Dict[str, Any] = {
            "index_name": index_name,
            "performance": {
                "avg_query_time_ms": metrics.average_query_time_ms,
                "cache_hit_rate": metrics.cache_hit_rate,
                "slow_query_ratio": metrics.slow_query_count
                / max(metrics.total_queries, 1),
            },
            "resource_usage": {
                "index_size_mb": metrics.index_size_mb,
                "documents_per_mb": metrics.total_documents
                / max(metrics.index_size_mb, 1),
            },
            "recommendations": [],
        }

        # Generate recommendations
        if metrics.average_query_time_ms > 500:
            if metrics.cache_hit_rate < 0.5:
                analysis["recommendations"].append(
                    {
                        "type": "cache",
                        "action": "increase_cache_size",
                        "reason": "Low cache hit rate with high query time",
                    }
                )

            if config.enable_approximate_search is False:
                analysis["recommendations"].append(
                    {
                        "type": "search",
                        "action": "enable_approximate_search",
                        "reason": "High query time, consider approximate search",
                    }
                )

        if metrics.index_size_mb > 500 and config.enable_compression is False:
            analysis["recommendations"].append(
                {
                    "type": "storage",
                    "action": "enable_compression",
                    "reason": "Large index size, compression recommended",
                }
            )

        return analysis

    def auto_optimize(self, index_name: str) -> bool:
        """Automatically optimize based on analysis."""
        analysis = self.analyze_index(index_name)

        if not analysis or not analysis.get("recommendations"):
            self.logger.info("No optimizations needed for %s", index_name)
            return True

        index = self.manager.indices[index_name]
        config = self.manager.index_configs[index_name]

        # Apply recommendations
        applied = []
        for rec in analysis["recommendations"]:
            if rec["action"] == "increase_cache_size":
                config.cache_size = min(config.cache_size * 2, 10000)
                applied.append("increased_cache_size")

            elif rec["action"] == "enable_approximate_search":
                config.enable_approximate_search = True
                applied.append("enabled_approximate_search")

            elif rec["action"] == "enable_compression":
                config.enable_compression = True
                applied.append("enabled_compression")

        # Record optimization
        if index_name not in self.optimization_history:
            self.optimization_history[index_name] = []

        self.optimization_history[index_name].append(
            {"timestamp": datetime.now(), "analysis": analysis, "applied": applied}
        )

        # Trigger index optimization
        return index.optimize()


class IndexMonitor:
    """
    Real-time index monitoring.

    Features:
    - Performance tracking
    - Alert generation
    - Trend analysis
    """

    def __init__(self, manager: IndexManager):
        """Initialize index monitor."""
        self.manager = manager
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self.alerts: List[Dict[str, Any]] = []
        self.metrics_history: Dict[str, List[Dict[str, Any]]] = {}
        self._monitoring = False
        self._monitor_thread: Optional[threading.Thread] = None

    def start_monitoring(self, interval_seconds: int = 60) -> None:
        """Start monitoring indices."""
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
        """Run the main monitoring loop."""
        while self._monitoring:
            self._collect_metrics()
            self._check_alerts()
            time.sleep(interval)

    def _collect_metrics(self) -> None:
        """Collect metrics from all indices."""
        timestamp = datetime.now()

        for name, index in self.manager.indices.items():
            metrics = index.get_metrics()

            if name not in self.metrics_history:
                self.metrics_history[name] = []

            # Keep last 24 hours of metrics
            cutoff = timestamp - timedelta(hours=24)
            self.metrics_history[name] = [
                m for m in self.metrics_history[name] if m["timestamp"] > cutoff
            ]

            self.metrics_history[name].append(
                {
                    "timestamp": timestamp,
                    "total_queries": metrics.total_queries,
                    "avg_query_time_ms": metrics.average_query_time_ms,
                    "error_count": metrics.error_count,
                    "cache_hit_rate": metrics.cache_hit_rate,
                }
            )

    def _check_alerts(self) -> None:
        """Check for alert conditions."""
        for name, history in self.metrics_history.items():
            if len(history) < 2:
                continue

            latest = history[-1]
            previous = history[-2]

            # Check for sudden performance degradation
            if latest["avg_query_time_ms"] > previous["avg_query_time_ms"] * 2:
                self._create_alert(
                    name,
                    "performance_degradation",
                    f"Query time doubled: {latest['avg_query_time_ms']:.2f}ms",
                    "high",
                )

            # Check for error spike
            error_increase = latest["error_count"] - previous["error_count"]
            if error_increase > 10:
                self._create_alert(
                    name,
                    "error_spike",
                    f"Error count increased by {error_increase}",
                    "critical",
                )

    def _create_alert(
        self, index_name: str, alert_type: str, message: str, severity: str
    ) -> None:
        """Create an alert."""
        alert = {
            "timestamp": datetime.now(),
            "index_name": index_name,
            "type": alert_type,
            "message": message,
            "severity": severity,
            "resolved": False,
        }

        self.alerts.append(alert)
        self.logger.warning("Alert: %s - %s", index_name, message)

    def get_alerts(
        self, index_name: Optional[str] = None, unresolved_only: bool = True
    ) -> List[Dict[str, Any]]:
        """Get alerts."""
        alerts = self.alerts

        if index_name:
            alerts = [a for a in alerts if a["index_name"] == index_name]

        if unresolved_only:
            alerts = [a for a in alerts if not a["resolved"]]

        return alerts

    def resolve_alert(self, alert_index: int) -> None:
        """Mark an alert as resolved."""
        if 0 <= alert_index < len(self.alerts):
            self.alerts[alert_index]["resolved"] = True

    def get_metrics_summary(self, index_name: str, hours: int = 1) -> Dict[str, Any]:
        """Get metrics summary for an index."""
        if index_name not in self.metrics_history:
            return {}

        cutoff = datetime.now() - timedelta(hours=hours)
        recent_metrics = [
            m for m in self.metrics_history[index_name] if m["timestamp"] > cutoff
        ]

        if not recent_metrics:
            return {}

        # Calculate summary statistics
        query_times = [m["avg_query_time_ms"] for m in recent_metrics]
        cache_rates = [m["cache_hit_rate"] for m in recent_metrics]

        return {
            "index_name": index_name,
            "time_range_hours": hours,
            "metrics_count": len(recent_metrics),
            "avg_query_time_ms": {
                "mean": sum(query_times) / len(query_times),
                "min": min(query_times),
                "max": max(query_times),
            },
            "cache_hit_rate": {
                "mean": sum(cache_rates) / len(cache_rates),
                "min": min(cache_rates),
                "max": max(cache_rates),
            },
            "total_errors": sum(m["error_count"] for m in recent_metrics),
        }
