"""
OpenSearch Health Check Module.

Provides health monitoring and diagnostics for OpenSearch cluster.
"""

import logging
from datetime import datetime
from typing import Any, Dict

from .connector import OpenSearchConnector

logger = logging.getLogger(__name__)


class OpenSearchHealthCheck:
    """Health monitoring for OpenSearch."""

    def __init__(self, connector: OpenSearchConnector):
        """Initialize health monitor."""
        self.connector = connector
        self.health_thresholds = {
            "cpu_usage_percent": 80,
            "memory_usage_percent": 85,
            "disk_usage_percent": 90,
            "query_latency_ms": 1000,
            "indexing_latency_ms": 500,
        }

    def check_cluster_health(self) -> Dict[str, Any]:
        """Check overall cluster health."""
        if not self.connector.client:
            return {"status": "disconnected", "error": "Not connected to OpenSearch"}

        try:
            health = self.connector.client.cluster.health()
            return {
                "status": health["status"],
                "cluster_name": health["cluster_name"],
                "number_of_nodes": health["number_of_nodes"],
                "active_shards": health["active_shards"],
                "relocating_shards": health["relocating_shards"],
                "initializing_shards": health["initializing_shards"],
                "unassigned_shards": health["unassigned_shards"],
                "timestamp": datetime.utcnow().isoformat(),
            }
        except (KeyError, ConnectionError) as e:
            logger.error("Cluster health check failed: %s", e)
            return {"status": "error", "error": str(e)}

    def check_node_stats(self) -> Dict[str, Any]:
        """Check node-level statistics."""
        if not self.connector.client:
            return {"error": "Not connected to OpenSearch"}

        try:
            stats = self.connector.client.nodes.stats()
            node_info = {}

            for _, node_data in stats["nodes"].items():
                node_info[node_data["name"]] = {
                    "cpu_percent": node_data["os"]["cpu"]["percent"],
                    "memory_used_percent": node_data["os"]["mem"]["used_percent"],
                    "disk_used_percent": self._calculate_disk_usage(node_data),
                    "heap_used_percent": node_data["jvm"]["mem"]["heap_used_percent"],
                    "thread_pool_queue": node_data["thread_pool"]["search"].get(
                        "queue", 0
                    ),
                    "thread_pool_rejected": node_data["thread_pool"]["search"].get(
                        "rejected", 0
                    ),
                }

            return node_info
        except (KeyError, ConnectionError) as e:
            logger.error("Node stats check failed: %s", e)
            return {"error": str(e)}

    def _calculate_disk_usage(self, node_data: Dict) -> float:
        """Calculate disk usage percentage."""
        try:
            total = node_data["fs"]["total"]["total_in_bytes"]
            available = node_data["fs"]["total"]["available_in_bytes"]
            used = total - available
            return float(round((used / total) * 100, 2))
        except (KeyError, ZeroDivisionError):
            return 0.0

    def check_index_performance(self, index_name: str) -> Dict[str, Any]:
        """Check performance metrics for specific index."""
        if not self.connector.client:
            return {"error": "Not connected to OpenSearch"}

        try:
            stats = self.connector.client.indices.stats(index=index_name)
            index_stats = stats["indices"][index_name]["primaries"]

            return {
                "index_name": index_name,
                "docs_count": index_stats["docs"]["count"],
                "size_mb": index_stats["store"]["size_in_bytes"] / (1024 * 1024),
                "query_total": index_stats["search"]["query_total"],
                "query_time_ms": index_stats["search"]["query_time_in_millis"],
                "avg_query_time_ms": (
                    (
                        index_stats["search"]["query_time_in_millis"]
                        / index_stats["search"]["query_total"]
                    )
                    if index_stats["search"]["query_total"] > 0
                    else 0
                ),
                "indexing_total": index_stats["indexing"]["index_total"],
                "indexing_time_ms": index_stats["indexing"]["index_time_in_millis"],
                "refresh_total": index_stats["refresh"]["total"],
                "refresh_time_ms": index_stats["refresh"]["total_time_in_millis"],
            }
        except (KeyError, ConnectionError) as e:
            logger.error("Index performance check failed: %s", e)
            return {"error": str(e)}

    def run_comprehensive_health_check(self) -> Dict[str, Any]:
        """Run comprehensive health check on cluster."""
        report: Dict[str, Any] = {
            "timestamp": datetime.utcnow().isoformat(),
            "cluster_health": self.check_cluster_health(),
            "node_stats": self.check_node_stats(),
            "alerts": [],
        }

        # Check for issues
        cluster_status = report["cluster_health"].get("status", "unknown")
        if cluster_status == "red":
            report["alerts"].append(
                {
                    "severity": "critical",
                    "message": "Cluster status is RED - immediate attention required",
                }
            )
        elif cluster_status == "yellow":
            report["alerts"].append(
                {
                    "severity": "warning",
                    "message": "Cluster status is YELLOW - some shards are not allocated",
                }
            )

        # Check node resources
        for node_name, node_data in report["node_stats"].items():
            if isinstance(node_data, dict):
                for metric_key, threshold in self.health_thresholds.items():
                    if (
                        metric_key in node_data
                        and isinstance(node_data.get(metric_key), (int, float))
                        and node_data.get(metric_key, 0) > threshold
                    ):
                        report["alerts"].append(
                            {
                                "severity": "warning",
                                "node": node_name,
                                "message": f"{metric_key} is {node_data.get(metric_key)}% (threshold: {threshold}%)",
                            }
                        )

        return report
