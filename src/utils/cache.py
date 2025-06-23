"""Cache utilities for Redis connections."""

from typing import Optional

import redis.asyncio as redis

from src.config.loader import get_settings


class RedisClientManager:
    """Manages Redis client singleton."""

    _instance: Optional["RedisClientManager"] = None
    _redis_client: Optional[redis.Redis] = None

    def __new__(cls) -> "RedisClientManager":
        """Create singleton instance of Redis client manager."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    async def get_client(self) -> redis.Redis:
        """Get or create Redis client instance."""
        if self._redis_client is None:
            settings = get_settings()
            # Create new client and store at instance level
            self._redis_client = redis.from_url(
                settings.redis_url,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
            )
        return self._redis_client


_manager = RedisClientManager()


async def get_redis_client() -> redis.Redis:
    """Get or create Redis client instance."""
    return await _manager.get_client()


# Export redis_client for compatibility
redis_client = get_redis_client()
