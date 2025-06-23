"""Rate limiter for API endpoints."""

import asyncio
import time
from collections import defaultdict, deque
from functools import wraps
from typing import Any, Callable, Dict

from fastapi import HTTPException

from src.utils.logging import get_logger

logger = get_logger(__name__)


class RateLimiter:
    """Rate limiter for API endpoints to prevent abuse."""

    def __init__(
        self,
        per_minute: int = 60,
        per_hour: int = 1000,
        per_day: int = 10000,
        burst_size: int = 100,
    ):
        """Initialize rate limiter.

        Args:
            per_minute: Max requests per minute
            per_hour: Max requests per hour
            per_day: Max requests per day
            burst_size: Max burst size for token bucket
        """
        self.per_minute = per_minute
        self.per_hour = per_hour
        self.per_day = per_day
        self.burst_size = burst_size

        # Sliding window for rates
        self.request_times: Dict[str, deque] = defaultdict(deque)

        # Token bucket for burst control
        self.tokens: Dict[str, float] = defaultdict(lambda: float(burst_size))
        self.last_refill: Dict[str, float] = defaultdict(time.time)

        # Lock for thread safety
        self._lock = asyncio.Lock()

    def limit(self, rate_string: str) -> Callable:
        """Apply rate limiting to endpoints using a decorator.

        Args:
            rate_string: Rate limit string (e.g., "5/hour", "10/minute")

        Returns:
            Decorator function
        """
        # Parse rate string
        count_str, period = rate_string.split("/")
        count = int(count_str)

        # Convert period to seconds
        period_seconds = {"second": 1, "minute": 60, "hour": 3600, "day": 86400}.get(
            period, 3600
        )  # Default to hour

        def decorator(func: Callable) -> Callable:
            @wraps(func)
            async def wrapper(*args: Any, **kwargs: Any) -> Any:
                # Try to get request object from args/kwargs
                request = None
                for arg in args:
                    if hasattr(arg, "client"):  # FastAPI Request object
                        request = arg
                        break
                if not request and "req" in kwargs:
                    request = kwargs["req"]
                elif not request and "request" in kwargs:
                    request = kwargs["request"]

                # Get identifier (IP address or user ID)
                identifier = "unknown"
                if request:
                    if hasattr(request, "client") and request.client:
                        identifier = request.client.host
                    elif hasattr(request, "headers"):
                        # Try to get from headers (for proxy scenarios)
                        identifier = request.headers.get(
                            "X-Forwarded-For",
                            request.headers.get("X-Real-IP", "unknown"),
                        )

                # Apply rate limit specific to this endpoint
                endpoint_id = f"{identifier}:{func.__name__}:{rate_string}"

                # Check if allowed
                current_time = time.time()
                async with self._lock:
                    if not self._check_endpoint_limit(
                        endpoint_id, count, period_seconds, current_time
                    ):
                        raise HTTPException(
                            status_code=429,
                            detail=f"Rate limit exceeded: {rate_string}",
                        )

                    # Record request
                    if endpoint_id not in self.request_times:
                        self.request_times[endpoint_id] = deque()
                    self.request_times[endpoint_id].append(current_time)

                # Call original function
                return await func(*args, **kwargs)

            return wrapper

        return decorator

    def _check_endpoint_limit(
        self, endpoint_id: str, count: int, period_seconds: float, current_time: float
    ) -> bool:
        """Check if request is allowed for specific endpoint."""
        # Clean old entries
        cutoff_time = current_time - period_seconds

        if endpoint_id in self.request_times:
            # Remove old entries
            while (
                self.request_times[endpoint_id]
                and self.request_times[endpoint_id][0] < cutoff_time
            ):
                self.request_times[endpoint_id].popleft()

            # Check count
            if len(self.request_times[endpoint_id]) >= count:
                return False

        return True

    async def check_rate_limit(self, identifier: str) -> bool:
        """Check if request is allowed under rate limits.

        Args:
            identifier: Unique identifier (e.g., IP address, user ID)

        Returns:
            True if request is allowed, False otherwise
        """
        async with self._lock:
            current_time = time.time()

            # Clean old entries
            self._clean_old_entries(identifier, current_time)

            # Check rate limits
            if not self._check_time_windows(identifier, current_time):
                logger.warning(f"Rate limit exceeded for {identifier}")
                return False

            # Check token bucket
            if not self._check_token_bucket(identifier, current_time):
                logger.warning(f"Burst limit exceeded for {identifier}")
                return False

            # Record request
            self.request_times[identifier].append(current_time)

            return True

    def _clean_old_entries(self, identifier: str, current_time: float) -> None:
        """Remove entries older than 24 hours."""
        day_ago = current_time - 86400  # 24 hours

        while (
            self.request_times[identifier]
            and self.request_times[identifier][0] < day_ago
        ):
            self.request_times[identifier].popleft()

    def _check_time_windows(self, identifier: str, current_time: float) -> bool:
        """Check if request is within time window limits."""
        request_times = self.request_times[identifier]

        # Check per minute
        minute_ago = current_time - 60
        minute_count = sum(1 for t in request_times if t > minute_ago)
        if minute_count >= self.per_minute:
            return False

        # Check per hour
        hour_ago = current_time - 3600
        hour_count = sum(1 for t in request_times if t > hour_ago)
        if hour_count >= self.per_hour:
            return False

        # Check per day
        day_ago = current_time - 86400
        day_count = sum(1 for t in request_times if t > day_ago)
        if day_count >= self.per_day:
            return False

        return True

    def _check_token_bucket(self, identifier: str, current_time: float) -> bool:
        """Check token bucket for burst control."""
        # Refill tokens based on time passed
        time_passed = current_time - self.last_refill[identifier]
        self.last_refill[identifier] = current_time

        # Refill rate: 1 token per second
        tokens_to_add = time_passed
        self.tokens[identifier] = min(
            self.burst_size, self.tokens[identifier] + tokens_to_add
        )

        # Check if we have tokens available
        if self.tokens[identifier] >= 1:
            self.tokens[identifier] -= 1
            return True

        return False

    def reset(self, identifier: str) -> None:
        """Reset rate limits for an identifier."""
        if identifier in self.request_times:
            del self.request_times[identifier]
        if identifier in self.tokens:
            del self.tokens[identifier]
        if identifier in self.last_refill:
            del self.last_refill[identifier]


# For backwards compatibility with email rate limiter
class EmailRateLimiter(RateLimiter):
    """Rate limiter specifically for email sending."""

    def __init__(
        self,
        per_minute: int = 10,
        per_hour: int = 100,
        per_day: int = 1000,
        per_recipient_hour: int = 3,
        burst_size: int = 20,
    ):
        """Initialize email rate limiter with stricter defaults."""
        super().__init__(per_minute, per_hour, per_day, burst_size)
        self.per_recipient_hour = per_recipient_hour
        self.recipient_send_times: Dict[str, deque] = defaultdict(
            lambda: deque(maxlen=per_recipient_hour)
        )
