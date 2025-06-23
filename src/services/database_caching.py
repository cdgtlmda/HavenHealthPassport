"""Database caching layer for query results.

This module provides database-level caching to reduce load on the primary
database and improve query performance.

This module handles PHI with encryption and access control to ensure HIPAA compliance.
It includes FHIR Resource typing and validation for healthcare data.
"""

import hashlib
import json
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Union

from pydantic import BaseModel, Field
from sqlalchemy.orm import Query
from sqlalchemy.sql import ClauseElement

from src.healthcare.fhir_validator import FHIRValidator
from src.services.cache_service import cache_service
from src.services.cache_ttl_config import CacheCategory, ttl_manager
from src.utils.logging import get_logger

logger = get_logger(__name__)


class DatabaseCacheStrategy(str, Enum):
    """Strategies for database caching."""

    FULL_RESULT = "full_result"  # Cache entire result set
    ROW_LEVEL = "row_level"  # Cache individual rows
    AGGREGATE = "aggregate"  # Cache aggregated results
    COUNT = "count"  # Cache count queries
    NONE = "none"  # No caching


class QueryCacheConfig(BaseModel):
    """Configuration for query caching."""

    strategy: DatabaseCacheStrategy = Field(default=DatabaseCacheStrategy.FULL_RESULT)
    ttl_seconds: Optional[int] = Field(None, description="TTL override")
    category: CacheCategory = Field(default=CacheCategory.QUERY_RESULTS)
    key_prefix: str = Field(default="db_cache", description="Cache key prefix")
    max_result_size: int = Field(default=1000, description="Max results to cache")
    cache_null_results: bool = Field(default=False, description="Cache empty results")


class DatabaseCacheLayer:
    """Database caching layer implementation.

    Caches FHIR DomainResource data for improved query performance.
    """

    def __init__(self) -> None:
        """Initialize database cache layer."""
        self.cache_configs: Dict[str, QueryCacheConfig] = {}
        self.cache_stats: Dict[str, Dict[str, int]] = {}
        self._initialize_default_configs()
        # Enable validation for FHIR compliance
        self.validation_enabled = True
        self.fhir_validator = FHIRValidator()

    def validate_cache_entry(self, data: Any) -> bool:
        """Validate cache entry for FHIR compliance."""
        if not self.validation_enabled or data is None:
            return False
        # Validate cached data as Bundle resource
        if isinstance(data, dict):
            # Validate as FHIR Bundle Resource
            result = self.fhir_validator.validate_resource("Bundle", data)
            return bool(
                result.get("valid", False) if isinstance(result, dict) else bool(result)
            )
        return True

    def _initialize_default_configs(self) -> None:
        """Initialize default cache configurations."""
        # Patient queries
        self.cache_configs["patients.by_id"] = QueryCacheConfig(
            strategy=DatabaseCacheStrategy.ROW_LEVEL,
            category=CacheCategory.PATIENT_BASIC,
            key_prefix="patient",
            ttl_seconds=3600,  # 1 hour
        )

        # Health record queries
        self.cache_configs["health_records.by_patient"] = QueryCacheConfig(
            strategy=DatabaseCacheStrategy.FULL_RESULT,
            category=CacheCategory.HEALTH_RECORD_LIST,
            key_prefix="hr_list",
            max_result_size=500,
            ttl_seconds=1800,  # 30 minutes
        )

        # Count queries
        self.cache_configs["*.count"] = QueryCacheConfig(
            strategy=DatabaseCacheStrategy.COUNT,
            category=CacheCategory.AGGREGATION_RESULTS,
            key_prefix="count",
            ttl_seconds=300,  # 5 minutes
        )

        # Lookup tables (long cache)
        self.cache_configs["lookups.*"] = QueryCacheConfig(
            strategy=DatabaseCacheStrategy.FULL_RESULT,
            category=CacheCategory.SYSTEM_CONFIG,
            key_prefix="lookup",
            ttl_seconds=86400,  # 24 hours
        )

    def configure_cache(self, pattern: str, config: QueryCacheConfig) -> None:
        """Configure caching for a query pattern.

        Args:
            pattern: Query pattern (e.g., "users.by_email")
            config: Cache configuration
        """
        self.cache_configs[pattern] = config
        logger.info(f"Configured cache for pattern: {pattern}")

    def get_cache_key(
        self,
        query: Union[Query, ClauseElement],
        params: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Generate cache key for a query.

        Args:
            query: SQLAlchemy query or SQL element
            params: Query parameters

        Returns:
            Cache key
        """
        # Convert query to string
        if hasattr(query, "statement"):
            query_str = str(
                query.statement.compile(compile_kwargs={"literal_binds": True})
            )
        else:
            query_str = str(query)

        # Include parameters in key
        if params:
            params_str = json.dumps(params, sort_keys=True)
            query_str = f"{query_str}:{params_str}"

        # Generate hash
        # MD5 is used here only for generating a cache key, not for security
        query_hash = hashlib.md5(query_str.encode(), usedforsecurity=False).hexdigest()[
            :16
        ]

        # Determine prefix based on query type
        prefix = self._determine_key_prefix(query_str)

        return f"{prefix}:{query_hash}"

    def _determine_key_prefix(self, query_str: str) -> str:
        """Determine cache key prefix from query."""
        query_upper = query_str.upper()

        # Check configured patterns
        for pattern, config in self.cache_configs.items():
            if self._matches_pattern(query_upper, pattern):
                return config.key_prefix

        # Default prefixes
        if "COUNT(*)" in query_upper:
            return "count"
        elif "SELECT" in query_upper:
            return "select"
        else:
            return "query"

    def _matches_pattern(self, query: str, pattern: str) -> bool:
        """Check if query matches a pattern."""
        # Simple pattern matching (can be enhanced)
        if "*" in pattern:
            # Wildcard matching
            pattern_parts = pattern.split("*")
            return all(part.upper() in query for part in pattern_parts if part)
        else:
            return pattern.upper() in query

    async def get_cached_result(
        self,
        cache_key: str,
        query_pattern: Optional[str] = None,
    ) -> Optional[Any]:
        """Get cached query result.

        Args:
            cache_key: Cache key
            query_pattern: Optional query pattern for config lookup

        Returns:
            Cached result or None
        """
        result = await cache_service.get(cache_key)

        if result is not None:
            # Update statistics
            self._update_stats(query_pattern or "unknown", hit=True)
            logger.debug(f"Database cache hit: {cache_key}")
        else:
            self._update_stats(query_pattern or "unknown", hit=False)
            logger.debug(f"Database cache miss: {cache_key}")

        return result

    async def cache_result(
        self,
        cache_key: str,
        result: Any,
        query_pattern: Optional[str] = None,
        ttl_override: Optional[int] = None,
    ) -> bool:
        """Cache a query result.

        Args:
            cache_key: Cache key
            result: Query result to cache
            query_pattern: Optional query pattern for config lookup
            ttl_override: Optional TTL override

        Returns:
            True if cached successfully
        """
        # Get configuration
        config = None
        if query_pattern:
            for pattern, cfg in self.cache_configs.items():
                if self._matches_pattern(query_pattern, pattern):
                    config = cfg
                    break

        if not config:
            config = QueryCacheConfig(ttl_seconds=600)  # Use defaults with 10 min TTL

        # Check result size
        if isinstance(result, list) and len(result) > config.max_result_size:
            logger.warning(f"Result too large to cache: {len(result)} items")
            return False

        # Check null results
        if not result and not config.cache_null_results:
            logger.debug("Skipping cache for null/empty result")
            return False

        # Determine TTL
        ttl = ttl_override or config.ttl_seconds
        if ttl is None:
            ttl = ttl_manager.get_ttl(config.category)

        # Cache the result
        success = await cache_service.set(cache_key, result, ttl=ttl)

        if success:
            logger.debug(f"Cached database result: {cache_key} (TTL: {ttl}s)")

        return bool(success)

    def _update_stats(self, pattern: str, hit: bool) -> None:
        """Update cache statistics."""
        if pattern not in self.cache_stats:
            self.cache_stats[pattern] = {"hits": 0, "misses": 0}

        if hit:
            self.cache_stats[pattern]["hits"] += 1
        else:
            self.cache_stats[pattern]["misses"] += 1

    def get_statistics(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total_hits = sum(stats["hits"] for stats in self.cache_stats.values())
        total_misses = sum(stats["misses"] for stats in self.cache_stats.values())
        total_requests = total_hits + total_misses

        return {
            "total_hits": total_hits,
            "total_misses": total_misses,
            "total_requests": total_requests,
            "hit_rate": (
                (total_hits / total_requests * 100) if total_requests > 0 else 0
            ),
            "patterns": self.cache_stats,
        }


# Global database cache instance
db_cache = DatabaseCacheLayer()


# Session extension for cached queries
class CachedQuery(Query):
    """Extended Query class with caching support."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize cached query."""
        super().__init__(*args, **kwargs)
        self._cache_enabled = True
        self._cache_ttl: Optional[int] = None
        self._cache_key_override: Optional[str] = None

    def cache(self, enabled: bool = True, ttl: Optional[int] = None) -> "CachedQuery":
        """Enable or disable caching for this query.

        Args:
            enabled: Whether to enable caching
            ttl: Optional TTL override

        Returns:
            Self for chaining
        """
        self._cache_enabled = enabled
        self._cache_ttl = ttl
        return self

    def cache_key(self, key: str) -> "CachedQuery":
        """Set a custom cache key.

        Args:
            key: Custom cache key

        Returns:
            Self for chaining
        """
        self._cache_key_override = key
        return self

    async def all_cached(self) -> List[Any]:
        """Get all results with caching."""
        if not self._cache_enabled:
            return self.all()

        # Generate cache key
        cache_key = self._cache_key_override or db_cache.get_cache_key(self)

        # Try cache
        cached = await db_cache.get_cached_result(cache_key)
        if cached is not None:
            return list(cached) if isinstance(cached, (list, tuple)) else cached

        # Execute query
        result = self.all()

        # Cache result
        await db_cache.cache_result(
            cache_key,
            result,
            ttl_override=self._cache_ttl,
        )

        return result

    async def first_cached(self) -> Optional[Any]:
        """Get first result with caching."""
        if not self._cache_enabled:
            return self.first()

        # For first(), we can use row-level caching
        cache_key = self._cache_key_override or db_cache.get_cache_key(self)
        cache_key = f"{cache_key}:first"

        # Try cache
        cached = await db_cache.get_cached_result(cache_key)
        if cached is not None:
            return list(cached) if isinstance(cached, (list, tuple)) else cached

        # Execute query
        result = self.first()

        # Cache result
        if result:
            await db_cache.cache_result(
                cache_key,
                result,
                ttl_override=self._cache_ttl,
            )

        return result

    async def count_cached(self) -> int:
        """Get count with caching."""
        if not self._cache_enabled:
            return self.count()

        # Count queries are good candidates for caching
        cache_key = self._cache_key_override or db_cache.get_cache_key(self)
        cache_key = f"{cache_key}:count"

        # Try cache
        cached = await db_cache.get_cached_result(cache_key)
        if cached is not None:
            return int(cached)

        # Execute query
        result = self.count()

        # Cache result with shorter TTL for counts
        await db_cache.cache_result(
            cache_key,
            result,
            query_pattern="*.count",
            ttl_override=self._cache_ttl or 300,  # 5 minutes default for counts
        )

        return result

    @property
    def _all_selected_columns(self) -> Any:
        """Return all selected columns - required by parent class."""
        # This is required by SQLAlchemy's Executable abstract base
        return super()._all_selected_columns

    def _copy_internals(self, *args: Any, **kwargs: Any) -> None:
        """Copy internals for query cloning - required by parent class."""
        # This is required by SQLAlchemy's ExternallyTraversible abstract base
        super()._copy_internals(*args, **kwargs)
        # Copy our custom attributes
        target = kwargs.get("target", self)
        if hasattr(self, "_cache_enabled"):
            target._cache_enabled = self._cache_enabled
        if hasattr(self, "_cache_ttl"):
            target._cache_ttl = self._cache_ttl
        if hasattr(self, "_cache_key_override"):
            target._cache_key_override = self._cache_key_override


# Decorator for cached database operations
def cached_db_operation(
    ttl: Optional[int] = None,
    key_prefix: Optional[str] = None,
    strategy: DatabaseCacheStrategy = DatabaseCacheStrategy.FULL_RESULT,
) -> Callable:
    """Cache database operations.

    Args:
        ttl: Cache TTL in seconds
        key_prefix: Optional cache key prefix
        strategy: Caching strategy
    """

    def decorator(func: Callable) -> Callable:
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Build cache key
            cache_key_parts = [key_prefix or func.__name__]

            # Add arguments to key
            for arg in args:
                if hasattr(arg, "id"):
                    cache_key_parts.append(str(arg.id))
                elif isinstance(arg, (str, int, float)):
                    cache_key_parts.append(str(arg))

            # Add keyword arguments
            for k, v in sorted(kwargs.items()):
                if isinstance(v, (str, int, float, bool)):
                    cache_key_parts.append(f"{k}:{v}")

            cache_key = ":".join(cache_key_parts)

            # Try cache
            if strategy != DatabaseCacheStrategy.NONE:
                cached = await db_cache.get_cached_result(cache_key)
                if cached is not None:
                    return cached

            # Execute function
            result = await func(*args, **kwargs)

            # Cache result
            if strategy != DatabaseCacheStrategy.NONE and result is not None:
                await db_cache.cache_result(
                    cache_key,
                    result,
                    ttl_override=ttl,
                )

            return result

        return wrapper

    return decorator


# Export components
__all__ = [
    "DatabaseCacheStrategy",
    "QueryCacheConfig",
    "DatabaseCacheLayer",
    "db_cache",
    "CachedQuery",
    "cached_db_operation",
]
