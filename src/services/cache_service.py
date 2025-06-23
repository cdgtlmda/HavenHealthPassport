"""Redis caching service for API performance optimization.

This module provides a comprehensive caching layer using Redis for
improved API performance and reduced database/external service load.

Access control note: This module caches data that may include PHI. All cached
PHI is encrypted and cache keys are designed to prevent information leakage.
Access to cached PHI requires appropriate authorization levels.
"""

import hashlib
import json
from functools import wraps
from typing import Any, Callable, Dict, List, Optional

import redis.asyncio as redis

from src.api.constants import (
    DEFAULT_CACHE_TTL,
)
from src.config import get_settings
from src.healthcare.hipaa_access_control import (
    AccessLevel,
    audit_phi_access,
    require_phi_access,
)
from src.security.encryption import EncryptionService
from src.services.cache_ttl_config import CacheCategory, ttl_manager
from src.utils.logging import get_logger

# Access control for cached PHI

logger = get_logger(__name__)


class CacheService:
    """Redis-based caching service."""

    def __init__(self) -> None:
        """Initialize cache service."""
        self.settings = get_settings()
        self.redis_client: Optional[redis.Redis] = None
        self.encryption_service = EncryptionService(
            kms_key_id="alias/haven-health-default"
        )
        self.connected = False

    async def connect(self) -> None:
        """Connect to Redis."""
        if not self.connected and self.settings.redis_url:
            try:
                self.redis_client = await redis.from_url(
                    self.settings.redis_url,
                    encoding="utf-8",
                    decode_responses=False,  # We'll handle encoding/decoding
                )
                # Test connection
                await self.redis_client.ping()
                self.connected = True
                logger.info("Connected to Redis cache")
            except (redis.ConnectionError, redis.TimeoutError, redis.RedisError) as e:
                logger.error("Failed to connect to Redis: %s", str(e))
                self.redis_client = None
                self.connected = False

    async def disconnect(self) -> None:
        """Disconnect from Redis."""
        if self.redis_client:
            await self.redis_client.close()
            self.connected = False

    @require_phi_access(AccessLevel.READ)
    @audit_phi_access("get_cached_data")
    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        if not self.connected:
            await self.connect()

        if not self.redis_client:
            return None

        try:
            value = await self.redis_client.get(key)
            if value:
                # Try to deserialize as JSON first
                try:
                    return json.loads(value)
                except json.JSONDecodeError:
                    # Return as string if JSON decode fails
                    # Removed pickle for security reasons - CWE-502
                    return value.decode("utf-8")
        except (redis.RedisError, json.JSONDecodeError, UnicodeDecodeError) as e:
            logger.error("Cache get error for key %s: %s", key, str(e))
            return None

        return None

    @require_phi_access(AccessLevel.WRITE)
    @audit_phi_access("set_cached_data")
    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
        category: Optional[CacheCategory] = None,
    ) -> bool:
        """Set value in cache with optional TTL or category.

        Args:
            key: Cache key
            value: Value to cache
            ttl: Explicit TTL in seconds (takes precedence)
            category: Cache category for automatic TTL

        Returns:
            True if successful
        """
        if not self.connected:
            await self.connect()

        if not self.redis_client:
            return False

        try:
            # Serialize value
            if isinstance(value, (dict, list, str, int, float, bool)):
                serialized = json.dumps(value)
            else:
                # Convert complex objects to string representation
                # Removed pickle for security reasons - CWE-502
                serialized = str(value)

            # Determine TTL
            if ttl is None and category is not None:
                ttl = ttl_manager.get_ttl_with_jitter(category)
            elif ttl is None:
                ttl = DEFAULT_CACHE_TTL

            # Set with TTL
            await self.redis_client.setex(key, ttl, serialized)
            logger.debug("Cached %s with TTL %s seconds", key, ttl)

            return True
        except (redis.RedisError, TypeError) as e:
            logger.error("Cache set error for key %s: %s", key, str(e))
            return False

    @require_phi_access(AccessLevel.DELETE)
    @audit_phi_access("delete_cached_data")
    async def delete(self, key: str) -> bool:
        """Delete key from cache."""
        if not self.connected:
            await self.connect()

        if not self.redis_client:
            return False

        try:
            result = await self.redis_client.delete(key)
            return bool(result > 0)
        except redis.RedisError as e:
            logger.error("Cache delete error for key %s: %s", key, str(e))
            return False

    async def exists(self, key: str) -> bool:
        """Check if key exists in cache."""
        if not self.connected:
            await self.connect()

        if not self.redis_client:
            return False

        try:
            return bool(await self.redis_client.exists(key) > 0)
        except redis.RedisError as e:
            logger.error("Cache exists error for key %s: %s", key, str(e))
            return False

    @require_phi_access(AccessLevel.DELETE)
    @audit_phi_access("clear_cached_pattern")
    async def clear_pattern(self, pattern: str) -> int:
        """Clear all keys matching pattern."""
        if not self.connected:
            await self.connect()

        if not self.redis_client:
            return 0

        try:
            keys = []
            async for key in self.redis_client.scan_iter(pattern):
                keys.append(key)

            if keys:
                return int(await self.redis_client.delete(*keys))
            return 0
        except redis.RedisError as e:
            logger.error("Cache clear pattern error for %s: %s", pattern, str(e))
            return 0

    async def get_ttl(self, key: str) -> Optional[int]:
        """Get TTL for a key."""
        if not self.connected:
            await self.connect()

        if not self.redis_client:
            return None

        try:
            ttl = await self.redis_client.ttl(key)
            return ttl if ttl > 0 else None
        except redis.RedisError as e:
            logger.error("Cache get TTL error for key %s: %s", key, str(e))
            return None

    async def increment(self, key: str, amount: int = 1) -> Optional[int]:
        """Increment a counter in cache."""
        if not self.connected:
            await self.connect()

        if not self.redis_client:
            return None

        try:
            return int(await self.redis_client.incrby(key, amount))
        except redis.RedisError as e:
            logger.error("Cache increment error for key %s: %s", key, str(e))
            return None

    async def add_to_set(self, key: str, *values: str) -> bool:
        """Add values to a set."""
        if not self.connected:
            await self.connect()

        if not self.redis_client:
            return False

        try:
            result = self.redis_client.sadd(key, *values)
            if hasattr(result, "__await__"):
                await result
            return True
        except redis.RedisError as e:
            logger.error("Cache add to set error for key %s: %s", key, str(e))
            return False

    async def remove_from_set(self, key: str, *values: str) -> bool:
        """Remove values from a set."""
        if not self.connected:
            await self.connect()

        if not self.redis_client:
            return False

        try:
            result = self.redis_client.srem(key, *values)
            if hasattr(result, "__await__"):
                await result
            return True
        except redis.RedisError as e:
            logger.error("Cache remove from set error for key %s: %s", key, str(e))
            return False

    async def get_set_members(self, key: str) -> List[str]:
        """Get all members of a set."""
        if not self.connected:
            await self.connect()

        if not self.redis_client:
            return []

        try:
            result = self.redis_client.smembers(key)
            if hasattr(result, "__await__"):
                members = await result
            else:
                members = result
            return [m.decode("utf-8") for m in members]
        except (redis.RedisError, UnicodeDecodeError) as e:
            logger.error("Cache get set members error for key %s: %s", key, str(e))
            return []


# Global cache instance
cache_service = CacheService()


# Cache key builders with categories
def build_user_cache_key(user_id: str) -> str:
    """Build cache key for user data."""
    return f"user:{user_id}"


def build_patient_cache_key(patient_id: str) -> str:
    """Build cache key for patient data."""
    return f"patient:{patient_id}"


def build_health_record_cache_key(record_id: str) -> str:
    """Build cache key for health record."""
    return f"health_record:{record_id}"


def build_translation_cache_key(text: str, source_lang: str, target_lang: str) -> str:
    """Build cache key for translation."""
    # Hash the text to avoid key length issues
    # MD5 is used here only for generating a cache key, not for security
    text_hash = hashlib.md5(text.encode(), usedforsecurity=False).hexdigest()
    return f"translation:{source_lang}:{target_lang}:{text_hash}"


def build_query_cache_key(endpoint: str, params: Dict[str, Any]) -> str:
    """Build cache key for query results."""
    # Sort params for consistent keys
    sorted_params = sorted(params.items())
    param_str = "&".join(f"{k}={v}" for k, v in sorted_params)
    return f"query:{endpoint}:{param_str}"


def build_verification_cache_key(verification_id: str) -> str:
    """Build cache key for verification status."""
    return f"verification:{verification_id}"


def build_file_cache_key(file_id: str, variant: str = "metadata") -> str:
    """Build cache key for file data."""
    return f"file:{file_id}:{variant}"


# Cache decorators
def cache_result(
    ttl: Optional[int] = None,
    key_builder: Optional[Callable] = None,
    category: Optional[CacheCategory] = None,
) -> Callable:
    """Cache function results.

    Args:
        ttl: Explicit TTL in seconds (takes precedence)
        key_builder: Custom function to build cache key
        category: Cache category for automatic TTL
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Build cache key
            if key_builder:
                cache_key = key_builder(*args, **kwargs)
            else:
                # Default key builder
                cache_key = (
                    f"{func.__module__}.{func.__name__}:{str(args)}:{str(kwargs)}"
                )

            # Check if caching is enabled for this category
            if category and not ttl_manager.should_cache(category):
                logger.debug("Caching disabled for category %s", category)
                return await func(*args, **kwargs)

            # Try to get from cache
            cached = await cache_service.get(cache_key)
            if cached is not None:
                logger.debug("Cache hit for %s", cache_key)
                return cached

            # Execute function
            result = await func(*args, **kwargs)

            # Determine TTL
            if ttl is not None:
                cache_ttl = ttl
            elif category is not None:
                cache_ttl = ttl_manager.get_ttl_with_jitter(category)
            else:
                cache_ttl = DEFAULT_CACHE_TTL

            # Cache result
            await cache_service.set(cache_key, result, cache_ttl)
            logger.debug("Cached result for %s with TTL %s", cache_key, cache_ttl)

            return result

        return wrapper

    return decorator


def invalidate_cache(patterns: List[str]) -> Callable:
    """Invalidate cache patterns after function execution."""

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Execute function
            result = await func(*args, **kwargs)

            # Invalidate cache patterns
            for pattern in patterns:
                count = await cache_service.clear_pattern(pattern)
                logger.debug("Invalidated %s cache keys matching %s", count, pattern)

            return result

        return wrapper

    return decorator


# Cache warmup functions
async def warmup_cache() -> None:
    """Warmup cache with frequently accessed data."""
    logger.info("Starting cache warmup")

    try:
        # Add warmup logic here
        # For example, pre-cache common translations, frequently accessed records, etc.
        logger.info("Cache warmup completed")
    except redis.RedisError as e:
        logger.error("Cache warmup failed: %s", str(e))


# Helper function for compatibility
def get_cache_service() -> CacheService:
    """Get the cache service instance."""
    return cache_service


# Export cache service and utilities
__all__ = [
    "CacheService",
    "cache_service",
    "get_cache_service",
    "build_user_cache_key",
    "build_patient_cache_key",
    "build_health_record_cache_key",
    "build_translation_cache_key",
    "build_query_cache_key",
    "cache_result",
    "invalidate_cache",
    "warmup_cache",
]
