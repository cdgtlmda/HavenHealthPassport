"""Cache statistics and monitoring service.

This module provides comprehensive cache statistics collection, monitoring,
and reporting for the Haven Health Passport caching infrastructure.
Includes validation for FHIR Resource cache performance monitoring.
"""

import asyncio
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Tuple

from pydantic import BaseModel, Field

from src.services.cache_invalidation import invalidation_service
from src.services.cache_service import cache_service
from src.services.cache_ttl_config import CacheCategory, ttl_manager
from src.services.cache_warming import warming_service
from src.services.query_cache import query_cache
from src.utils.logging import get_logger

logger = get_logger(__name__)


class CacheMetricType(str, Enum):
    """Types of cache metrics."""

    HIT_RATE = "hit_rate"
    MISS_RATE = "miss_rate"
    EVICTION_RATE = "eviction_rate"
    FILL_RATE = "fill_rate"
    LATENCY = "latency"
    SIZE = "size"
    TTL_DISTRIBUTION = "ttl_distribution"


class CacheStatistics(BaseModel):
    """Cache statistics model."""

    # Basic metrics
    total_hits: int = Field(default=0, description="Total cache hits")
    total_misses: int = Field(default=0, description="Total cache misses")
    total_evictions: int = Field(default=0, description="Total evictions")
    total_invalidations: int = Field(default=0, description="Total invalidations")

    # Calculated metrics
    hit_rate: float = Field(default=0.0, description="Cache hit rate percentage")
    miss_rate: float = Field(default=0.0, description="Cache miss rate percentage")

    # Size metrics
    total_keys: int = Field(default=0, description="Total number of keys")
    memory_usage_mb: float = Field(default=0.0, description="Memory usage in MB")

    # Performance metrics
    avg_latency_ms: float = Field(default=0.0, description="Average latency in ms")
    p95_latency_ms: float = Field(default=0.0, description="95th percentile latency")
    p99_latency_ms: float = Field(default=0.0, description="99th percentile latency")

    # Time period
    period_start: datetime = Field(..., description="Start of measurement period")
    period_end: datetime = Field(..., description="End of measurement period")

    @property
    def total_requests(self) -> int:
        """Total number of cache requests."""
        return self.total_hits + self.total_misses


class CategoryStatistics(BaseModel):
    """Statistics for a specific cache category."""

    category: CacheCategory
    statistics: CacheStatistics
    top_keys: List[Tuple[str, int]] = Field(
        default_factory=list, description="Top accessed keys"
    )
    ttl_distribution: Dict[str, int] = Field(
        default_factory=dict, description="TTL distribution"
    )


class CacheStatisticsService:
    """Service for collecting and analyzing cache statistics."""

    def __init__(self) -> None:
        """Initialize cache statistics service."""
        self.current_stats: Dict[str, Any] = {}
        self.category_stats: Dict[CacheCategory, CategoryStatistics] = {}
        self.collection_interval = 60  # seconds
        self.is_collecting = False
        self._initialize_stats()

    def validate_cache_stats(self, stats: Dict[str, Any]) -> bool:
        """Validate cache statistics for completeness and accuracy.

        Args:
            stats: Dictionary containing cache statistics

        Returns:
            bool: True if statistics are valid, False otherwise
        """
        if not stats:
            return False

        # Validate required metrics are present
        required_metrics = ["hit_rate", "miss_rate", "total_requests"]
        for metric in required_metrics:
            if metric not in stats.get("overall", {}):
                logger.error(f"Missing required metric in cache stats: {metric}")
                return False

        # Validate hit rate + miss rate = 100%
        overall = stats.get("overall", {})
        if "hit_rate" in overall and "miss_rate" in overall:
            total_rate = overall["hit_rate"] + overall["miss_rate"]
            if abs(total_rate - 100.0) > 0.01:  # Allow small floating point error
                logger.error(
                    f"Invalid cache stats: hit_rate + miss_rate != 100% (got {total_rate}%)"
                )
                return False

        return True

    def _initialize_stats(self) -> None:
        """Initialize statistics for all categories."""
        for category in CacheCategory:
            self.category_stats[category] = CategoryStatistics(
                category=category,
                statistics=CacheStatistics(
                    period_start=datetime.utcnow(),
                    period_end=datetime.utcnow(),
                ),
            )

    async def start_collection(self) -> None:
        """Start automatic statistics collection."""
        if self.is_collecting:
            logger.warning("Statistics collection already running")
            return

        self.is_collecting = True
        asyncio.create_task(self._collection_loop())
        logger.info("Started cache statistics collection")

    async def stop_collection(self) -> None:
        """Stop automatic statistics collection."""
        self.is_collecting = False
        logger.info("Stopped cache statistics collection")

    async def _collection_loop(self) -> None:
        """Run the main collection loop."""
        while self.is_collecting:
            try:
                await self.collect_statistics()
                await asyncio.sleep(self.collection_interval)
            except (ValueError, RuntimeError, AttributeError) as e:
                logger.error(f"Error in statistics collection: {e}")
                await asyncio.sleep(self.collection_interval)

    async def collect_statistics(self) -> Dict[str, Any]:
        """Collect current cache statistics."""
        start_time = datetime.utcnow()

        try:
            # Collect Redis statistics
            redis_stats = await self._collect_redis_stats()

            # Collect query cache statistics
            query_stats = await query_cache.get_cache_stats()

            # Collect invalidation statistics
            invalidation_stats = invalidation_service.get_invalidation_stats()

            # Collect warming statistics
            warming_stats = warming_service.get_warming_stats()

            # Collect category-specific statistics
            category_stats = await self._collect_category_stats()

            # Calculate overall statistics
            overall_stats = self._calculate_overall_stats(
                redis_stats,
                query_stats,
                category_stats,
            )

            # Store current statistics
            self.current_stats = {
                "overall": overall_stats,
                "redis": redis_stats,
                "query_cache": query_stats,
                "invalidation": invalidation_stats,
                "warming": warming_stats,
                "categories": category_stats,
                "collection_time": datetime.utcnow(),
                "collection_duration_ms": (
                    datetime.utcnow() - start_time
                ).total_seconds()
                * 1000,
            }

            return self.current_stats

        except (ValueError, RuntimeError, AttributeError) as e:
            logger.error(f"Failed to collect statistics: {e}")
            return {}

    async def _collect_redis_stats(self) -> Dict[str, Any]:
        """Collect Redis-specific statistics."""
        if not cache_service.connected:
            await cache_service.connect()

        if not cache_service.redis_client:
            return {}

        try:
            # Get Redis INFO
            info = await cache_service.redis_client.info()

            # Extract relevant statistics
            stats = {
                "connected_clients": info.get("connected_clients", 0),
                "used_memory_mb": info.get("used_memory", 0) / (1024 * 1024),
                "used_memory_peak_mb": info.get("used_memory_peak", 0) / (1024 * 1024),
                "total_commands_processed": info.get("total_commands_processed", 0),
                "instantaneous_ops_per_sec": info.get("instantaneous_ops_per_sec", 0),
                "keyspace_hits": info.get("keyspace_hits", 0),
                "keyspace_misses": info.get("keyspace_misses", 0),
                "evicted_keys": info.get("evicted_keys", 0),
                "expired_keys": info.get("expired_keys", 0),
            }

            # Calculate hit rate
            total_ops = stats["keyspace_hits"] + stats["keyspace_misses"]
            if total_ops > 0:
                stats["hit_rate"] = (stats["keyspace_hits"] / total_ops) * 100
            else:
                stats["hit_rate"] = 0.0

            # Get key count by pattern
            stats["key_counts"] = await self._get_key_counts()

            return stats

        except (ValueError, RuntimeError, AttributeError) as e:
            logger.error(f"Failed to collect Redis stats: {e}")
            return {}

    async def _get_key_counts(self) -> Dict[str, int]:
        """Get count of keys by pattern."""
        patterns = {
            "user": "user:*",
            "patient": "patient:*",
            "health_record": "health_record:*",
            "translation": "translation:*",
            "query": "query:*",
            "file": "file:*",
            "cache_stats": "cache:stats:*",
        }

        counts = {}
        for name, pattern in patterns.items():
            try:
                count = 0
                if cache_service.redis_client is not None:
                    async for _ in cache_service.redis_client.scan_iter(pattern):
                        count += 1
                counts[name] = count
            except (ValueError, RuntimeError, AttributeError) as e:
                logger.error(f"Failed to count keys for pattern {pattern}: {e}")
                counts[name] = 0

        return counts

    async def _collect_category_stats(self) -> Dict[CacheCategory, Dict[str, Any]]:
        """Collect statistics for each cache category."""
        category_stats = {}

        for category in CacheCategory:
            try:
                # Get hit/miss stats for category
                # @encrypt_phi - Cache stats may contain PHI identifiers
                # @access_control_required - Statistics access requires monitoring role
                stats_key = f"cache:stats:category:{category.value}"
                hits = await cache_service.get(f"{stats_key}:hits") or 0
                misses = await cache_service.get(f"{stats_key}:misses") or 0

                total = hits + misses
                hit_rate = (hits / total * 100) if total > 0 else 0

                # Get TTL statistics
                ttl = ttl_manager.get_ttl(category)

                category_stats[category] = {
                    "hits": hits,
                    "misses": misses,
                    "total_requests": total,
                    "hit_rate": hit_rate,
                    "configured_ttl": ttl,
                    "ttl_enabled": ttl_manager.should_cache(category),
                }

            except (ValueError, RuntimeError, AttributeError) as e:
                logger.error(f"Failed to collect stats for category {category}: {e}")
                category_stats[category] = {}

        return category_stats

    def _calculate_overall_stats(
        self,
        redis_stats: Dict[str, Any],
        query_stats: Dict[str, Any],
        category_stats: Dict[CacheCategory, Dict[str, Any]],
    ) -> CacheStatistics:
        """Calculate overall statistics from component stats."""
        # Aggregate hits and misses from all sources
        total_hits = redis_stats.get("keyspace_hits", 0)
        total_misses = redis_stats.get("keyspace_misses", 0)
        total_evictions = redis_stats.get("evicted_keys", 0)

        # Add query cache stats
        for _, stats in query_stats.items():
            if isinstance(stats, dict):
                total_hits += stats.get("hits", 0)
                total_misses += stats.get("misses", 0)

        # Aggregate category statistics
        category_hits = 0
        category_misses = 0
        category_evictions = 0
        total_invalidations = 0
        latency_samples = []

        for category, stats in category_stats.items():
            if isinstance(stats, dict):
                # Add category-specific metrics
                category_hits += stats.get("hits", 0)
                category_misses += stats.get("misses", 0)
                category_evictions += stats.get("evictions", 0)
                total_invalidations += stats.get("invalidations", 0)

                # Collect latency data if available
                if "avg_latency_ms" in stats and stats["avg_latency_ms"] > 0:
                    # Weight by number of requests for accurate average
                    requests = stats.get("hits", 0) + stats.get("misses", 0)
                    if requests > 0:
                        latency_samples.extend(
                            [stats["avg_latency_ms"]] * min(requests, 100)
                        )

                # Log critical category performance
                # @secure_storage - Patient data metrics must be protected
                if category == CacheCategory.PATIENT_BASIC:
                    if stats.get("hit_rate", 100) < 80:
                        logger.warning(
                            f"Low cache hit rate for patient data: {stats.get('hit_rate', 0):.1f}%"
                        )
                elif category == CacheCategory.HEALTH_RECORD:
                    if stats.get("avg_latency_ms", 0) > 100:
                        logger.warning(
                            f"High latency for medical records cache: {stats.get('avg_latency_ms', 0):.1f}ms"
                        )

        # Add category stats to totals
        total_hits += category_hits
        total_misses += category_misses
        total_evictions += category_evictions

        # Calculate rates
        total_requests = total_hits + total_misses
        hit_rate = (total_hits / total_requests * 100) if total_requests > 0 else 0
        miss_rate = 100 - hit_rate

        # Calculate latency percentiles
        avg_latency_ms = 0.0
        p95_latency_ms = 0.0
        p99_latency_ms = 0.0

        if latency_samples:
            latency_samples.sort()
            avg_latency_ms = sum(latency_samples) / len(latency_samples)
            p95_index = int(len(latency_samples) * 0.95)
            p99_index = int(len(latency_samples) * 0.99)
            p95_latency_ms = latency_samples[min(p95_index, len(latency_samples) - 1)]
            p99_latency_ms = latency_samples[min(p99_index, len(latency_samples) - 1)]

        # Get memory and key stats
        memory_usage_mb = redis_stats.get("used_memory_mb", 0)
        total_keys = sum(redis_stats.get("key_counts", {}).values())

        # Add category key counts
        for stats in category_stats.values():
            if isinstance(stats, dict):
                total_keys += stats.get("key_count", 0)

        return CacheStatistics(
            total_hits=total_hits,
            total_misses=total_misses,
            total_evictions=total_evictions,
            total_invalidations=total_invalidations,
            hit_rate=hit_rate,
            miss_rate=miss_rate,
            total_keys=total_keys,
            memory_usage_mb=memory_usage_mb,
            avg_latency_ms=avg_latency_ms,
            p95_latency_ms=p95_latency_ms,
            p99_latency_ms=p99_latency_ms,
            period_start=datetime.utcnow()
            - timedelta(seconds=self.collection_interval),
            period_end=datetime.utcnow(),
        )

    async def get_current_stats(self) -> Dict[str, Any]:
        """Get current statistics."""
        if not self.current_stats:
            return await self.collect_statistics()
        return self.current_stats

    async def get_category_stats(self, category: CacheCategory) -> CategoryStatistics:
        """Get statistics for a specific category."""
        if category not in self.category_stats:
            return CategoryStatistics(
                category=category,
                statistics=CacheStatistics(
                    period_start=datetime.utcnow(),
                    period_end=datetime.utcnow(),
                ),
            )
        return self.category_stats[category]

    async def get_performance_report(self) -> Dict[str, Any]:
        """Generate a performance report."""
        stats = await self.get_current_stats()

        if not stats:
            return {"error": "No statistics available"}

        overall = stats.get("overall", {})
        redis = stats.get("redis", {})

        report = {
            "summary": {
                "hit_rate": f"{overall.hit_rate:.2f}%",
                "total_requests": overall.total_requests,
                "memory_usage_mb": f"{overall.memory_usage_mb:.2f}",
                "total_keys": overall.total_keys,
            },
            "performance": {
                "ops_per_second": redis.get("instantaneous_ops_per_sec", 0),
                "connected_clients": redis.get("connected_clients", 0),
            },
            "recommendations": self._generate_recommendations(stats),
            "timestamp": datetime.utcnow().isoformat(),
        }

        return report

    def _generate_recommendations(self, stats: Dict[str, Any]) -> List[str]:
        """Generate performance recommendations based on statistics."""
        recommendations = []

        overall = stats.get("overall", {})
        redis = stats.get("redis", {})

        # Check hit rate
        if overall.hit_rate < 80:
            recommendations.append(
                f"Cache hit rate is {overall.hit_rate:.2f}%. "
                "Consider adjusting TTL values or warming more data."
            )

        # Check memory usage
        memory_mb = overall.memory_usage_mb
        if memory_mb > 1000:  # > 1GB
            recommendations.append(
                f"High memory usage ({memory_mb:.2f}MB). "
                "Consider reducing TTL values or evicting stale data."
            )

        # Check evictions
        if redis.get("evicted_keys", 0) > 100:
            recommendations.append(
                "High number of evictions detected. "
                "Consider increasing Redis memory limit."
            )

        return recommendations


# Global statistics service instance
cache_stats = CacheStatisticsService()


# Export components
__all__ = [
    "CacheMetricType",
    "CacheStatistics",
    "CategoryStatistics",
    "CacheStatisticsService",
    "cache_stats",
]
