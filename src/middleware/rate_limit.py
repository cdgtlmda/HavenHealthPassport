"""Rate limiting middleware for API protection."""

import time
from typing import Any, Callable, Dict, Optional, cast

import redis.asyncio as redis
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from src.config import get_settings
from src.middleware.rate_limit_bypass import bypass_config


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limiting middleware using Redis."""

    def __init__(self, app: ASGIApp, calls: int = 100, period: int = 60) -> None:
        """
        Initialize rate limiter.

        Args:
            app: FastAPI application
            calls: Number of allowed calls
            period: Time period in seconds
        """
        super().__init__(app)
        self.calls = calls
        self.period = period
        self.redis_client: Optional[redis.Redis] = None
        settings = get_settings()
        self.redis_url = settings.redis_url

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request with rate limiting."""
        # Check bypass rules first
        if bypass_config.should_bypass(request):
            return cast(Response, await call_next(request))

        # Skip rate limiting for health checks (legacy check, now handled by bypass rules)
        if request.url.path in ["/health", "/ready"]:
            return cast(Response, await call_next(request))

        # Get client identifier (IP or authenticated user)
        client_id = self._get_client_id(request)

        # Check rate limit
        if not await self._check_rate_limit(client_id):
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded", "retry_after": self.period},
                headers={
                    "Retry-After": str(self.period),
                    "X-RateLimit-Limit": str(self.calls),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(int(time.time()) + self.period),
                },
            )

        # Process request
        response = await call_next(request)

        # Add rate limit headers
        remaining = await self._get_remaining_calls(client_id)
        response.headers["X-RateLimit-Limit"] = str(self.calls)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(int(time.time()) + self.period)

        return cast(Response, response)

    def _get_client_id(self, request: Request) -> str:
        """Get client identifier from request."""
        # Try to get authenticated user ID
        if hasattr(request.state, "user") and request.state.user:
            return f"user:{request.state.user.get('sub', 'unknown')}"

        # Fall back to IP address
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            client_ip = forwarded.split(",")[0]
        else:
            client_ip = request.client.host if request.client else "unknown"

        return f"ip:{client_ip}"

    async def _connect_redis(self) -> None:
        """Connect to Redis if not connected."""
        if not self.redis_client:
            self.redis_client = await redis.from_url(
                self.redis_url, encoding="utf-8", decode_responses=True
            )

    async def _check_rate_limit(self, client_id: str) -> bool:
        """Check if client has exceeded rate limit."""
        await self._connect_redis()

        key = f"rate_limit:{client_id}"

        try:
            # Increment counter
            if self.redis_client is None:
                return True
            current = await self.redis_client.incr(key)

            # Set expiration on first request
            if current == 1:
                if self.redis_client:
                    await self.redis_client.expire(key, self.period)

            return bool(current <= self.calls)

        except (redis.RedisError, redis.ConnectionError):
            # If Redis fails, allow request (fail open)
            return True

    async def _get_remaining_calls(self, client_id: str) -> int:
        """Get remaining calls for client."""
        await self._connect_redis()

        key = f"rate_limit:{client_id}"

        try:
            if self.redis_client is None:
                return self.calls
            current = await self.redis_client.get(key)
            if current:
                remaining = self.calls - int(current)
                return max(0, remaining)
            return self.calls

        except (redis.RedisError, redis.ConnectionError):
            return self.calls


class APIKeyRateLimiter:
    """Rate limiter for API key-based access."""

    # Different limits for different API key tiers
    TIER_LIMITS = {
        "basic": {"calls": 1000, "period": 3600},  # 1000 calls/hour
        "standard": {"calls": 5000, "period": 3600},  # 5000 calls/hour
        "premium": {"calls": 20000, "period": 3600},  # 20000 calls/hour
        "enterprise": {"calls": 100000, "period": 3600},  # 100000 calls/hour
    }

    def __init__(self) -> None:
        """Initialize API key rate limiter."""
        settings = get_settings()
        self.redis_url = settings.redis_url
        self.redis_client: Optional[redis.Redis] = None

    async def check_api_key_limit(
        self, api_key: str, tier: str = "basic"
    ) -> Dict[str, Any]:
        """Check API key rate limit."""
        limits = self.TIER_LIMITS.get(tier, self.TIER_LIMITS["basic"])

        # Connect to Redis
        if not self.redis_client:
            self.redis_client = await redis.from_url(self.redis_url)

        key = f"api_rate_limit:{api_key}"

        # Check current usage
        current = await self.redis_client.incr(key)

        if current == 1:
            await self.redis_client.expire(key, limits["period"])

        remaining = max(0, limits["calls"] - current)
        exceeded = current > limits["calls"]

        return {
            "limit": limits["calls"],
            "remaining": remaining,
            "reset": int(time.time()) + limits["period"],
            "exceeded": exceeded,
        }
