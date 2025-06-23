"""
Retry Decorator with Exponential Backoff.

Provides a decorator for retrying failed operations with configurable
backoff strategies and error handling.
"""

import asyncio
import logging
import random
import time
from dataclasses import dataclass
from enum import Enum
from functools import wraps
from typing import Any, Callable, Optional, Tuple, Type

logger = logging.getLogger(__name__)


class RetryException(Exception):
    """Exception raised when all retry attempts fail."""


class CircuitBreakerOpenException(Exception):
    """Exception raised when circuit breaker is open."""


class BackoffStrategy(str, Enum):
    """Backoff strategies for retry logic."""

    EXPONENTIAL = "exponential"
    LINEAR = "linear"
    FIXED = "fixed"


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""

    max_attempts: int = 3
    initial_delay: float = 1.0  # seconds
    max_delay: float = 60.0  # seconds
    exponential_base: float = 2.0
    jitter: bool = True
    jitter_range: float = 0.1  # ±10% jitter
    backoff_strategy: BackoffStrategy = BackoffStrategy.EXPONENTIAL
    retry_on: Tuple[Type[Exception], ...] = (Exception,)
    exclude: Tuple[Type[Exception], ...] = ()
    on_retry: Optional[Callable[[Exception, int], None]] = None
    on_failure: Optional[Callable[[Exception], None]] = None
    circuit_breaker: Optional[Any] = None


def calculate_delay(attempt: int, config: RetryConfig) -> float:
    """Calculate delay for current attempt."""
    if config.backoff_strategy == BackoffStrategy.FIXED:
        delay = config.initial_delay
    elif config.backoff_strategy == BackoffStrategy.LINEAR:
        delay = config.initial_delay * attempt
    else:  # EXPONENTIAL
        delay = config.initial_delay * (config.exponential_base ** (attempt - 1))

    # Apply max delay cap
    delay = min(delay, config.max_delay)

    # Apply jitter if enabled
    if config.jitter:
        jitter_amount = delay * config.jitter_range
        delay += random.uniform(-jitter_amount, jitter_amount)

    return max(0, delay)  # Ensure non-negative


def should_retry(exception: Exception, config: RetryConfig) -> bool:
    """Determine if exception should trigger retry."""
    # Check if exception is in exclude list
    if isinstance(exception, config.exclude):
        return False

    # Check if exception is in retry list
    return isinstance(exception, config.retry_on)


def retry_with_backoff(config: Optional[RetryConfig] = None, **kwargs: Any) -> Callable:
    """
    Return decorator for retrying functions with exponential backoff.

    Args:
        config: RetryConfig instance or None
        **kwargs: Individual config parameters

    Returns:
        Decorated function
    """
    # Create config from kwargs if not provided
    if config is None:
        config = RetryConfig(**kwargs)

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            """Async version of retry wrapper."""
            # Check circuit breaker if configured
            if config.circuit_breaker and not config.circuit_breaker.can_execute():
                raise CircuitBreakerOpenException(
                    f"Circuit breaker is open for {func.__name__}"
                )

            last_exception = None

            for attempt in range(1, config.max_attempts + 1):
                try:
                    # Record attempt with circuit breaker
                    if config.circuit_breaker:
                        result = await func(*args, **kwargs)
                        config.circuit_breaker.record_success()
                        return result
                    else:
                        return await func(*args, **kwargs)

                except (ValueError, KeyError, AttributeError, RuntimeError) as e:
                    last_exception = e

                    # Record failure with circuit breaker
                    if config.circuit_breaker:
                        config.circuit_breaker.record_failure()

                    # Check if we should retry
                    if not should_retry(e, config):
                        raise

                    # Check if we have attempts left
                    if attempt >= config.max_attempts:
                        break

                    # Calculate delay
                    delay = calculate_delay(attempt, config)

                    # Log retry attempt
                    logger.warning(
                        "Retry attempt %d/%d for %s after %s: %s. Waiting %.2fs before retry.",
                        attempt,
                        config.max_attempts,
                        func.__name__,
                        e.__class__.__name__,
                        str(e),
                        delay,
                    )

                    # Call on_retry callback if provided
                    if config.on_retry:
                        config.on_retry(e, attempt)

                    # Wait before retry
                    await asyncio.sleep(delay)

            # All attempts failed
            if config.on_failure and last_exception is not None:
                config.on_failure(last_exception)

            raise RetryException(
                f"Failed after {config.max_attempts} attempts: {last_exception}"
            ) from last_exception

        @wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            """Sync version of retry wrapper."""
            # Check circuit breaker if configured
            if config.circuit_breaker and not config.circuit_breaker.can_execute():
                raise CircuitBreakerOpenException(
                    f"Circuit breaker is open for {func.__name__}"
                )

            last_exception = None

            for attempt in range(1, config.max_attempts + 1):
                try:
                    # Record attempt with circuit breaker
                    if config.circuit_breaker:
                        result = func(*args, **kwargs)
                        config.circuit_breaker.record_success()
                        return result
                    else:
                        return func(*args, **kwargs)

                except (ValueError, KeyError, AttributeError, RuntimeError) as e:
                    last_exception = e

                    # Record failure with circuit breaker
                    if config.circuit_breaker:
                        config.circuit_breaker.record_failure()

                    # Check if we should retry
                    if not should_retry(e, config):
                        raise

                    # Check if we have attempts left
                    if attempt >= config.max_attempts:
                        break

                    # Calculate delay
                    delay = calculate_delay(attempt, config)

                    # Log retry attempt
                    logger.warning(
                        "Retry attempt %d/%d for %s after %s: %s. Waiting %.2fs before retry.",
                        attempt,
                        config.max_attempts,
                        func.__name__,
                        e.__class__.__name__,
                        str(e),
                        delay,
                    )

                    # Call on_retry callback if provided
                    if config.on_retry:
                        config.on_retry(e, attempt)

                    # Wait before retry
                    time.sleep(delay)

            # All attempts failed
            if config.on_failure and last_exception is not None:
                config.on_failure(last_exception)

            raise RetryException(
                f"Failed after {config.max_attempts} attempts: {last_exception}"
            ) from last_exception

        # Return appropriate wrapper based on function type
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator
