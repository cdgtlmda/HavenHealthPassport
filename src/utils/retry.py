"""
Retry Utilities.

Provides retry mechanisms with exponential backoff for network operations.
"""

import asyncio
import functools
import logging
import random
import time
from typing import Any, Awaitable, Callable, Tuple, Type, TypeVar, cast

logger = logging.getLogger(__name__)

T = TypeVar("T")


def retry_with_backoff(
    max_retries: int = 3,
    initial_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    Create decorator for retrying functions with exponential backoff.

    Args:
        max_retries: Maximum number of retry attempts
        initial_delay: Initial delay between retries in seconds
        max_delay: Maximum delay between retries in seconds
        exponential_base: Base for exponential backoff calculation
        jitter: Whether to add random jitter to delays
        exceptions: Tuple of exceptions to catch and retry
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> T:
            delay = initial_delay
            last_exception = None

            for attempt in range(max_retries + 1):
                try:
                    result = cast(Awaitable[T], func(*args, **kwargs))
                    return await result
                except exceptions as e:
                    last_exception = e
                    if attempt == max_retries:
                        logger.error("Failed after %d attempts: %s", max_retries + 1, e)
                        raise

                    if jitter:
                        actual_delay = delay * (0.5 + random.random())
                    else:
                        actual_delay = delay

                    logger.warning(
                        "Attempt %d failed: %s. Retrying in %.2f seconds...",
                        attempt + 1,
                        e,
                        actual_delay,
                    )

                    await asyncio.sleep(actual_delay)

                    # Calculate next delay
                    delay = min(delay * exponential_base, max_delay)

            raise last_exception or Exception("Retry failed")

        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> T:
            delay = initial_delay
            last_exception = None

            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt == max_retries:
                        logger.error("Failed after %d attempts: %s", max_retries + 1, e)
                        raise

                    if jitter:
                        actual_delay = delay * (0.5 + random.random())
                    else:
                        actual_delay = delay

                    logger.warning(
                        "Attempt %d failed: %s. Retrying in %.2f seconds...",
                        attempt + 1,
                        e,
                        actual_delay,
                    )

                    time.sleep(actual_delay)

                    # Calculate next delay
                    delay = min(delay * exponential_base, max_delay)

            raise last_exception or Exception("Retry failed")

        # Return appropriate wrapper based on function type
        if asyncio.iscoroutinefunction(func):
            return cast(Callable[..., T], async_wrapper)
        else:
            return sync_wrapper

    return decorator


__all__ = ["retry_with_backoff"]
