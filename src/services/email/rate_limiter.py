"""Rate limiter for email sending."""

import asyncio
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta
from typing import Any, Dict

from src.utils.logging import get_logger

logger = get_logger(__name__)


class EmailRateLimiter:
    """Rate limiter for email sending to prevent abuse and comply with provider limits."""

    def __init__(
        self,
        per_minute: int = 10,
        per_hour: int = 100,
        per_day: int = 1000,
        per_recipient_hour: int = 3,
        burst_size: int = 20,
    ):
        """Initialize rate limiter.

        Args:
            per_minute: Max emails per minute (global)
            per_hour: Max emails per hour (global)
            per_day: Max emails per day (global)
            per_recipient_hour: Max emails per recipient per hour
            burst_size: Max burst size for token bucket
        """
        self.per_minute = per_minute
        self.per_hour = per_hour
        self.per_day = per_day
        self.per_recipient_hour = per_recipient_hour
        self.burst_size = burst_size

        # Sliding window for global rates
        self.send_times: deque = deque(maxlen=per_day)

        # Per-recipient tracking
        self.recipient_send_times: Dict[str, deque] = defaultdict(
            lambda: deque(maxlen=per_recipient_hour)
        )

        # Token bucket for burst control
        self.tokens = burst_size
        self.last_refill = time.time()
        self.refill_rate = per_minute / 60.0  # tokens per second

        # Lock for thread safety
        self.lock = asyncio.Lock()

    def _refill_tokens(self) -> None:
        """Refill tokens based on elapsed time."""
        now = time.time()
        elapsed = now - self.last_refill

        # Add tokens based on elapsed time
        tokens_to_add = elapsed * self.refill_rate
        self.tokens = int(min(self.burst_size, self.tokens + tokens_to_add))
        self.last_refill = now

    def _clean_old_sends(self) -> None:
        """Remove old send times outside the tracking windows."""
        now = datetime.utcnow()

        # Clean global sends older than 24 hours
        day_ago = now - timedelta(days=1)
        while self.send_times and self.send_times[0] < day_ago:
            self.send_times.popleft()

        # Clean per-recipient sends older than 1 hour
        hour_ago = now - timedelta(hours=1)
        for email, times in list(self.recipient_send_times.items()):
            while times and times[0] < hour_ago:
                times.popleft()

            # Remove empty entries
            if not times:
                del self.recipient_send_times[email]

    async def check_rate_limit(self, recipient_email: str) -> tuple[bool, str]:
        """Check if sending to recipient is allowed.

        Args:
            recipient_email: Email address to check

        Returns:
            Tuple of (allowed, reason_if_denied)
        """
        async with self.lock:
            now = datetime.utcnow()

            # Clean old data
            self._clean_old_sends()

            # Refill tokens
            self._refill_tokens()

            # Check token bucket
            if self.tokens < 1:
                wait_time = (1 - self.tokens) / self.refill_rate
                return (
                    False,
                    f"Rate limit exceeded. Try again in {wait_time:.1f} seconds",
                )

            # Count recent sends
            minute_ago = now - timedelta(minutes=1)
            hour_ago = now - timedelta(hours=1)

            minute_count = sum(1 for t in self.send_times if t > minute_ago)
            hour_count = sum(1 for t in self.send_times if t > hour_ago)
            day_count = len(self.send_times)

            # Check global limits
            if minute_count >= self.per_minute:
                return False, f"Per-minute limit ({self.per_minute}) exceeded"

            if hour_count >= self.per_hour:
                return False, f"Per-hour limit ({self.per_hour}) exceeded"

            if day_count >= self.per_day:
                return False, f"Per-day limit ({self.per_day}) exceeded"

            # Check per-recipient limit
            recipient_times = self.recipient_send_times[recipient_email]
            recipient_hour_count = len(recipient_times)

            if recipient_hour_count >= self.per_recipient_hour:
                return (
                    False,
                    f"Per-recipient hourly limit ({self.per_recipient_hour}) exceeded for {recipient_email}",
                )

            return True, ""

    async def record_send(self, recipient_email: str) -> None:
        """Record a successful send for rate limiting.

        Args:
            recipient_email: Email address that was sent to
        """
        async with self.lock:
            now = datetime.utcnow()

            # Record global send
            self.send_times.append(now)

            # Record per-recipient send
            self.recipient_send_times[recipient_email].append(now)

            # Consume a token
            self.tokens = max(0, self.tokens - 1)

    async def wait_if_needed(self, recipient_email: str) -> bool:
        """Wait if rate limited, return True if can proceed.

        Args:
            recipient_email: Email address to check

        Returns:
            True if can proceed after waiting, False if denied
        """
        for _ in range(60):  # Max 1 minute wait
            allowed, reason = await self.check_rate_limit(recipient_email)

            if allowed:
                return True

            # If it's a token bucket issue, wait a bit
            if "Try again in" in reason:
                await asyncio.sleep(1)
                continue
            else:
                # Hard limit reached
                logger.warning(f"Rate limit denied: {reason}")
                return False

        return False

    def get_current_usage(self) -> Dict[str, Any]:
        """Get current rate limit usage statistics."""
        now = datetime.utcnow()
        minute_ago = now - timedelta(minutes=1)
        hour_ago = now - timedelta(hours=1)

        minute_count = sum(1 for t in self.send_times if t > minute_ago)
        hour_count = sum(1 for t in self.send_times if t > hour_ago)
        day_count = len(self.send_times)

        return {
            "tokens_available": self.tokens,
            "minute_count": minute_count,
            "minute_limit": self.per_minute,
            "hour_count": hour_count,
            "hour_limit": self.per_hour,
            "day_count": day_count,
            "day_limit": self.per_day,
            "tracked_recipients": len(self.recipient_send_times),
        }
