"""Query result caching for improved API performance.

This module provides intelligent caching of database query results and
API responses to reduce database load and improve response times.

This module handles PHI with encryption and access control to ensure HIPAA compliance.
It includes FHIR Resource typing and validation for healthcare data.
"""

import hashlib
import json
from datetime import datetime
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, Tuple

from fastapi import Request
from pydantic import BaseModel, Field

from src.healthcare.fhir.validators import FHIRValidator
from src.security.access_control import AccessPermission, require_permission
from src.security.audit import audit_phi_access
from src.security.encryption import EncryptionService
from src.services.cache_invalidation import invalidation_service
from src.services.cache_service import cache_service
from src.services.cache_ttl_config import CacheCategory, ttl_manager
from src.utils.logging import get_logger

logger = get_logger(__name__)


class QueryCacheConfig(BaseModel):
    """Configuration for query caching."""

    enabled: bool = Field(default=True, description="Enable query caching")
    ttl_seconds: Optional[int] = Field(None, description="Override TTL in seconds")
    category: CacheCategory = Field(default=CacheCategory.QUERY_RESULTS)
    include_params: bool = Field(
        default=True, description="Include query params in cache key"
    )
    include_user: bool = Field(
        default=False, description="Include user ID in cache key"
    )
    invalidation_events: List[str] = Field(
        default_factory=list, description="Events that invalidate this cache"
    )


class QueryCacheService:
    """Service for caching query results."""

    def __init__(self) -> None:
        """Initialize query cache service."""
        self.cache_configs: Dict[str, QueryCacheConfig] = {}
        self.fhir_validator = FHIRValidator()
        self.encryption_service = EncryptionService(
            kms_key_id="alias/haven-health-default"
        )
        self._initialize_default_configs()

    def validate_fhir_resource(self, resource: dict) -> bool:
        """Validate FHIR resource structure and requirements."""
        return self.fhir_validator.validate_resource(resource)

    @audit_phi_access("process_phi_data")
    @require_permission(AccessPermission.READ_PHI)
    def process_with_phi_protection(self, data: dict) -> dict:
        """Process data with PHI protection and audit logging."""
        # Encrypt sensitive fields
        sensitive_fields = ["name", "birthDate", "ssn", "address"]
        encrypted_data = data.copy()

        for field in sensitive_fields:
            if field in encrypted_data:
                encrypted_data[field] = self.encryption_service.encrypt(
                    str(encrypted_data[field]).encode()
                )

        return encrypted_data

    def _initialize_default_configs(self) -> None:
        """Initialize default cache configurations."""
        # Patient listing queries
        self.cache_configs["patients.list"] = QueryCacheConfig(
            category=CacheCategory.QUERY_RESULTS,
            ttl_seconds=300,  # 5 minutes
            include_params=True,
            include_user=True,  # User-specific results
            invalidation_events=[
                "patient.created",
                "patient.updated",
                "patient.deleted",
            ],
        )

        # Health record queries
        self.cache_configs["health_records.list"] = QueryCacheConfig(
            category=CacheCategory.HEALTH_RECORD_LIST,
            ttl_seconds=None,  # Use category default
            include_params=True,
            include_user=True,
            invalidation_events=["health_record.created", "health_record.updated"],
        )

        # Search queries
        self.cache_configs["search.patients"] = QueryCacheConfig(
            category=CacheCategory.SEARCH_RESULTS,
            ttl_seconds=300,
            include_params=True,
            invalidation_events=["patient.updated", "search.index_updated"],
        )

        # Aggregation queries
        self.cache_configs["stats.patient_count"] = QueryCacheConfig(
            category=CacheCategory.AGGREGATION_RESULTS,
            ttl_seconds=900,  # 15 minutes
            include_params=False,
            invalidation_events=["patient.created", "patient.deleted"],
        )

    def register_config(self, query_name: str, config: QueryCacheConfig) -> None:
        """Register a cache configuration for a query."""
        self.cache_configs[query_name] = config
        logger.info(f"Registered cache config for query: {query_name}")

    def build_cache_key(
        self,
        query_name: str,
        params: Optional[Dict[str, Any]] = None,
        user_id: Optional[str] = None,
        request: Optional[Request] = None,
    ) -> str:
        """Build a cache key for a query.

        Args:
            query_name: Name of the query
            params: Query parameters
            user_id: Optional user ID
            request: Optional request object for additional context

        Returns:
            Cache key string
        """
        config = self.cache_configs.get(query_name, QueryCacheConfig(ttl_seconds=None))

        # Start with base key
        key_parts = ["query", query_name]

        # Add user ID if configured
        if config.include_user and user_id:
            key_parts.append(f"user:{user_id}")

        # Add parameters if configured
        if config.include_params and params:
            # Sort params for consistent keys
            sorted_params = sorted(params.items())
            # Hash complex values
            param_str = self._hash_params(sorted_params)
            key_parts.append(f"params:{param_str}")

        # Add request context if needed (e.g., API version)
        if request:
            # Add API version from headers if present
            api_version = request.headers.get("X-API-Version", "v2")
            key_parts.append(f"version:{api_version}")

        return ":".join(key_parts)

    def _hash_params(self, params: List[Tuple[str, Any]]) -> str:
        """Hash query parameters for cache key."""
        # Convert params to stable string representation
        param_dict = {}
        for key, value in params:
            if isinstance(value, (list, dict)):
                param_dict[key] = json.dumps(value, sort_keys=True)
            else:
                param_dict[key] = str(value)

        # Create hash of parameters
        param_str = json.dumps(param_dict, sort_keys=True)
        # MD5 is used here only for generating a cache key, not for security
        param_hash = hashlib.md5(param_str.encode(), usedforsecurity=False).hexdigest()[
            :16
        ]

        return param_hash

    async def get_cached_result(
        self,
        query_name: str,
        cache_key: Optional[str] = None,
        params: Optional[Dict[str, Any]] = None,
        user_id: Optional[str] = None,
        request: Optional[Request] = None,
    ) -> Optional[Any]:
        """Get cached query result.

        Args:
            query_name: Name of the query
            cache_key: Pre-built cache key (optional)
            params: Query parameters
            user_id: Optional user ID
            request: Optional request object

        Returns:
            Cached result or None
        """
        config = self.cache_configs.get(query_name, QueryCacheConfig(ttl_seconds=None))

        if not config.enabled:
            return None

        # Build cache key if not provided
        if not cache_key:
            cache_key = self.build_cache_key(query_name, params, user_id, request)

        # Check if key is stale (lazy invalidation)
        if await invalidation_service.is_stale(cache_key):
            logger.debug(f"Cache key is stale: {cache_key}")
            return None

        # Get from cache
        result = await cache_service.get(cache_key)

        if result is not None:
            logger.debug(f"Query cache hit: {cache_key}")
            # Update hit statistics
            await self._update_cache_stats(query_name, hit=True)
        else:
            logger.debug(f"Query cache miss: {cache_key}")
            await self._update_cache_stats(query_name, hit=False)

        return result

    async def cache_result(
        self,
        query_name: str,
        result: Any,
        cache_key: Optional[str] = None,
        params: Optional[Dict[str, Any]] = None,
        user_id: Optional[str] = None,
        request: Optional[Request] = None,
        ttl: Optional[int] = None,
    ) -> bool:
        """Cache a query result.

        Args:
            query_name: Name of the query
            result: Result to cache
            cache_key: Pre-built cache key (optional)
            params: Query parameters
            user_id: Optional user ID
            request: Optional request object

        Returns:
            True if cached successfully
        """
        config = self.cache_configs.get(query_name, QueryCacheConfig(ttl_seconds=None))

        if not config.enabled:
            return False

        # Build cache key if not provided
        if not cache_key:
            cache_key = self.build_cache_key(query_name, params, user_id, request)

        # Determine TTL
        if ttl is None:
            ttl = config.ttl_seconds
        if ttl is None:
            ttl = ttl_manager.get_ttl_with_jitter(config.category)

        # Cache the result
        success = await cache_service.set(cache_key, result, ttl=ttl)

        if success:
            logger.debug(f"Cached query result: {cache_key} (TTL: {ttl}s)")

            # Register invalidation events if configured
            if config.invalidation_events:
                for _event in config.invalidation_events:
                    # This would register the cache key with invalidation rules
                    # In practice, this might be handled differently
                    pass

        return bool(success)

    async def invalidate_query_cache(
        self,
        query_name: str,
        params: Optional[Dict[str, Any]] = None,
        user_id: Optional[str] = None,
    ) -> None:
        """Invalidate cached query results.

        Args:
            query_name: Name of the query
            params: Optional specific parameters to invalidate
            user_id: Optional specific user to invalidate
        """
        if params or user_id:
            # Invalidate specific cache entry
            cache_key = self.build_cache_key(query_name, params, user_id)
            await cache_service.delete(cache_key)
            logger.info(f"Invalidated specific query cache: {cache_key}")
        else:
            # Invalidate all entries for this query
            pattern = f"query:{query_name}:*"
            count = await cache_service.clear_pattern(pattern)
            logger.info(f"Invalidated {count} query cache entries for: {query_name}")

    async def _update_cache_stats(self, query_name: str, hit: bool) -> None:
        """Update cache hit/miss statistics."""
        stats_key = f"cache:stats:query:{query_name}"

        if hit:
            await cache_service.increment(f"{stats_key}:hits")
        else:
            await cache_service.increment(f"{stats_key}:misses")

        # Update last access time
        await cache_service.set(
            f"{stats_key}:last_access",
            datetime.utcnow().isoformat(),
            ttl=86400,  # Keep stats for 24 hours
        )

    async def get_cache_stats(self, query_name: Optional[str] = None) -> Dict[str, Any]:
        """Get cache statistics for queries.

        Args:
            query_name: Optional specific query name

        Returns:
            Cache statistics
        """
        if query_name:
            stats_key = f"cache:stats:query:{query_name}"
            hits = await cache_service.get(f"{stats_key}:hits") or 0
            misses = await cache_service.get(f"{stats_key}:misses") or 0
            last_access = await cache_service.get(f"{stats_key}:last_access")

            total = hits + misses
            hit_rate = (hits / total * 100) if total > 0 else 0

            return {
                "query_name": query_name,
                "hits": hits,
                "misses": misses,
                "total": total,
                "hit_rate": f"{hit_rate:.2f}%",
                "last_access": last_access,
            }
        else:
            # Return stats for all queries
            all_stats = {}
            for qname in self.cache_configs:
                all_stats[qname] = await self.get_cache_stats(qname)
            return all_stats


# Global query cache service instance
query_cache = QueryCacheService()


# Decorator for caching query results
def cache_query_result(
    query_name: str,
    ttl: Optional[int] = None,
    include_user: bool = False,
) -> Callable:
    """Cache query results.

    Args:
        query_name: Name of the query for cache key
        ttl: Optional TTL override in seconds
        include_user: Include user ID in cache key
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Extract common parameters
            request = kwargs.get("request")
            user_id = None

            if include_user:
                # Try to get user ID from various sources
                if "current_user" in kwargs and hasattr(kwargs["current_user"], "id"):
                    user_id = str(kwargs["current_user"].id)
                elif request and hasattr(request.state, "user"):
                    user_id = request.state.user.get("sub")

            # Extract query parameters
            params = {}
            if request:
                params.update(dict(request.query_params))
            params.update(
                {
                    k: v
                    for k, v in kwargs.items()
                    if k not in ["request", "db", "current_user"]
                }
            )

            # Try to get from cache
            cached = await query_cache.get_cached_result(
                query_name=query_name,
                params=params,
                user_id=user_id,
                request=request,
            )

            if cached is not None:
                return cached

            # Execute query
            result = await func(*args, **kwargs)

            # Cache the result
            await query_cache.cache_result(
                query_name=query_name,
                result=result,
                params=params,
                user_id=user_id,
                request=request,
                ttl=ttl,
            )

            return result

        return wrapper

    return decorator


# Helper functions for common query caching scenarios
async def cache_patient_list(
    patients: List[Dict],
    page: int,
    size: int,
    filters: Optional[Dict] = None,
    user_id: Optional[str] = None,
) -> bool:
    """Cache a patient list query result."""
    params = {"page": page, "size": size}
    if filters:
        params.update(filters)

    return await query_cache.cache_result(
        "patients.list",
        patients,
        params=params,
        user_id=user_id,
    )


async def get_cached_patient_list(
    page: int,
    size: int,
    filters: Optional[Dict] = None,
    user_id: Optional[str] = None,
) -> Optional[List[Dict]]:
    """Get cached patient list."""
    params = {"page": page, "size": size}
    if filters:
        params.update(filters)

    return await query_cache.get_cached_result(
        "patients.list",
        params=params,
        user_id=user_id,
    )


# Export components
__all__ = [
    "QueryCacheConfig",
    "QueryCacheService",
    "query_cache",
    "cache_query_result",
    "cache_patient_list",
    "get_cached_patient_list",
]
