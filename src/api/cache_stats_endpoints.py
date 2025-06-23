"""Cache statistics and monitoring endpoints.

This module provides REST API endpoints for monitoring cache performance,
viewing statistics, and managing cache operations.
"""

# flake8: noqa: B008  # FastAPI Depends() is designed to be used in function defaults

import asyncio
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from src.api.auth_endpoints import get_current_user
from src.models.auth import UserAuth, UserRole
from src.services.cache_invalidation import invalidation_service
from src.services.cache_service import cache_service
from src.services.cache_statistics import CacheCategory, cache_stats
from src.services.cache_ttl_config import ttl_manager
from src.services.cache_warming import warming_service
from src.services.query_cache import query_cache
from src.utils.logging import get_logger

router = APIRouter(prefix="/cache", tags=["cache", "monitoring"])
logger = get_logger(__name__)


# Response Models
class CacheStatsResponse(BaseModel):
    """Cache statistics response."""

    overall: Dict[str, Any]
    redis: Dict[str, Any]
    query_cache: Dict[str, Any]
    invalidation: Dict[str, Any]
    warming: Dict[str, Any]
    categories: Dict[str, Any]
    collection_time: str


class CacheHealthResponse(BaseModel):
    """Cache health check response."""

    status: str
    connected: bool
    memory_usage_mb: float
    hit_rate: float
    message: str


class TTLConfigResponse(BaseModel):
    """TTL configuration response."""

    category: str
    ttl_seconds: int
    enabled: bool


class CacheKeyResponse(BaseModel):
    """Cache key information response."""

    key: str
    exists: bool
    ttl_seconds: Optional[int]
    value_preview: Optional[str]


class InvalidationRequest(BaseModel):
    """Request to invalidate cache entries."""

    event: str = Field(..., description="Event type to trigger")
    context: Dict[str, str] = Field(default_factory=dict, description="Event context")
    patterns: Optional[List[str]] = Field(
        None, description="Specific patterns to invalidate"
    )


class WarmingRequest(BaseModel):
    """Request to warm cache."""

    task_names: Optional[List[str]] = Field(None, description="Specific tasks to run")


# Admin check dependency
async def require_admin_or_monitoring(
    current_user: UserAuth = Depends(get_current_user),
) -> UserAuth:
    """Require admin or monitoring role."""

    allowed_roles = [UserRole.ADMIN, UserRole.SUPER_ADMIN]
    if current_user.role not in allowed_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin or monitoring access required",
        )
    return current_user


# Endpoints
@router.get("/stats", response_model=CacheStatsResponse)
async def get_cache_statistics(
    _: UserAuth = Depends(require_admin_or_monitoring),
) -> CacheStatsResponse:
    """Get comprehensive cache statistics."""
    stats = await cache_stats.get_current_stats()

    if not stats:
        # Collect fresh statistics
        stats = await cache_stats.collect_statistics()

    return CacheStatsResponse(
        overall=stats.get("overall", {}),
        redis=stats.get("redis", {}),
        query_cache=stats.get("query_cache", {}),
        invalidation=stats.get("invalidation", {}),
        warming=stats.get("warming", {}),
        categories=stats.get("categories", {}),
        collection_time=(
            stats.get("collection_time", "").isoformat()
            if stats.get("collection_time")
            else ""
        ),
    )


@router.get("/health", response_model=CacheHealthResponse)
async def get_cache_health() -> CacheHealthResponse:
    """Get cache health status (public endpoint)."""
    try:
        # Check Redis connection
        if not cache_service.connected:
            await cache_service.connect()

        connected = cache_service.connected

        if connected:
            # Get basic stats
            stats = await cache_stats.get_current_stats()
            overall = stats.get("overall", {})

            memory_usage = overall.get("memory_usage_mb", 0)
            hit_rate = overall.get("hit_rate", 0)

            # Determine health status
            if hit_rate < 50:
                health_status = "degraded"
                message = "Low cache hit rate"
            elif memory_usage > 2000:  # > 2GB
                health_status = "warning"
                message = "High memory usage"
            else:
                health_status = "healthy"
                message = "Cache operating normally"
        else:
            health_status = "unhealthy"
            message = "Redis connection failed"
            memory_usage = 0
            hit_rate = 0

        return CacheHealthResponse(
            status=health_status,
            connected=connected,
            memory_usage_mb=memory_usage,
            hit_rate=hit_rate,
            message=message,
        )

    except (ConnectionError, TimeoutError, RuntimeError) as e:
        logger.error(f"Cache health check failed: {e}")
        return CacheHealthResponse(
            status="error",
            connected=False,
            memory_usage_mb=0,
            hit_rate=0,
            message=str(e),
        )


@router.get("/performance-report")
async def get_performance_report(
    _: UserAuth = Depends(require_admin_or_monitoring),
) -> Dict[str, Any]:
    """Get cache performance report with recommendations."""
    return await cache_stats.get_performance_report()


@router.get("/ttl-config", response_model=List[TTLConfigResponse])
async def get_ttl_configuration(
    _: UserAuth = Depends(require_admin_or_monitoring),
) -> List[TTLConfigResponse]:
    """Get TTL configuration for all categories."""
    configs = []

    for category in CacheCategory:
        ttl = ttl_manager.get_ttl(category)
        enabled = ttl_manager.should_cache(category)

        configs.append(
            TTLConfigResponse(
                category=category.value,
                ttl_seconds=ttl,
                enabled=enabled,
            )
        )

    return configs


@router.get("/key/{key:path}", response_model=CacheKeyResponse)
async def get_cache_key_info(
    key: str,
    _: UserAuth = Depends(require_admin_or_monitoring),
) -> CacheKeyResponse:
    """Get information about a specific cache key."""
    exists = await cache_service.exists(key)
    ttl = await cache_service.get_ttl(key) if exists else None

    # Get value preview (first 100 chars)
    value_preview = None
    if exists:
        value = await cache_service.get(key)
        if value:
            value_str = str(value)
            value_preview = (
                value_str[:100] + "..." if len(value_str) > 100 else value_str
            )

    return CacheKeyResponse(
        key=key,
        exists=exists,
        ttl_seconds=ttl,
        value_preview=value_preview,
    )


@router.post("/invalidate", status_code=status.HTTP_204_NO_CONTENT)
async def invalidate_cache(
    request: InvalidationRequest,
    _: UserAuth = Depends(require_admin_or_monitoring),
) -> None:
    """Trigger cache invalidation."""
    try:
        if request.patterns:
            # Invalidate specific patterns
            for pattern in request.patterns:
                count = await cache_service.clear_pattern(pattern)
                logger.info(f"Invalidated {count} keys matching pattern: {pattern}")
        else:
            # Trigger event-based invalidation
            await invalidation_service.trigger_invalidation(
                event=request.event,
                context=request.context,
            )

    except Exception as e:
        logger.error(f"Cache invalidation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Cache invalidation failed",
        ) from e


@router.post("/warm", status_code=status.HTTP_202_ACCEPTED)
async def warm_cache(
    request: WarmingRequest,
    _: UserAuth = Depends(require_admin_or_monitoring),
) -> Dict[str, str]:
    """Trigger cache warming."""
    try:
        # Start warming in background
        asyncio.create_task(warming_service.warm_cache(task_names=request.task_names))

        return {
            "message": "Cache warming started",
            "tasks": str(request.task_names) if request.task_names else "all",
        }

    except Exception as e:
        logger.error(f"Cache warming failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Cache warming failed",
        ) from e


@router.delete("/clear", status_code=status.HTTP_204_NO_CONTENT)
async def clear_cache(
    pattern: str = Query(..., description="Pattern to clear (use * for all)"),
    confirm: bool = Query(False, description="Confirm dangerous operation"),
    current_user: UserAuth = Depends(require_admin_or_monitoring),
) -> None:
    """Clear cache entries matching pattern (dangerous operation)."""
    # Extra check for admin role for this dangerous operation

    if current_user.role not in [UserRole.ADMIN, UserRole.SUPER_ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admin can clear cache",
        )

    if not confirm:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Must confirm cache clear operation",
        )

    try:
        count = await cache_service.clear_pattern(pattern)
        logger.warning(
            f"Admin {current_user.id} cleared {count} cache keys matching: {pattern}"
        )

    except Exception as e:
        logger.error(f"Cache clear failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Cache clear failed",
        ) from e


@router.get("/query-stats")
async def get_query_cache_stats(
    query_name: Optional[str] = None,
    _: UserAuth = Depends(require_admin_or_monitoring),
) -> Dict[str, Any]:
    """Get query cache statistics."""
    return await query_cache.get_cache_stats(query_name)
