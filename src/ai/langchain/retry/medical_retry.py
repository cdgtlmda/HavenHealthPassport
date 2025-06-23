"""
Medical-Specific Retry Logic.

Provides retry mechanisms tailored for medical AI operations with
special handling for critical scenarios.
"""

import logging
from typing import Any, Callable, Tuple, Type, cast

from .retry_decorator import BackoffStrategy, RetryConfig, retry_with_backoff

logger = logging.getLogger(__name__)


# Medical-specific exceptions that should trigger retry
MEDICAL_RETRY_EXCEPTIONS: Tuple[Type[Exception], ...] = (
    ConnectionError,
    TimeoutError,
    # Add medical-specific exceptions as needed
)

# Exceptions that should NOT trigger retry in medical context
MEDICAL_NO_RETRY_EXCEPTIONS: Tuple[Type[Exception], ...] = (
    ValueError,  # Bad medical data
    PermissionError,  # HIPAA violations
    # Add other non-retryable exceptions
)


class MedicalRetryPolicy:
    """
    Medical-specific retry policy.

    Handles:
    - Emergency vs routine operations
    - Critical medical data operations
    - HIPAA compliance during retries
    - Audit requirements
    """

    @staticmethod
    def get_retry_config(
        urgency_level: int, operation_type: str = "standard"
    ) -> RetryConfig:
        """
        Get appropriate retry config based on medical context.

        Args:
            urgency_level: 1-5 scale (5 = emergency)
            operation_type: Type of medical operation

        Returns:
            RetryConfig: Configuration for retry behavior
        """
        # Use urgency level to determine retry parameters
        _ = operation_type  # Mark as intentionally unused
        # Emergency operations - fast retries, low tolerance
        if urgency_level >= 4:
            return RetryConfig(
                max_attempts=5,
                initial_delay=0.1,
                max_delay=2.0,
                exponential_base=1.2,
                jitter=False,  # Predictable timing for emergencies
                backoff_strategy=BackoffStrategy.EXPONENTIAL,
                retry_on=MEDICAL_RETRY_EXCEPTIONS,
                exclude=MEDICAL_NO_RETRY_EXCEPTIONS,
            )

        # Critical operations - balanced approach
        elif urgency_level >= 3:
            return RetryConfig(
                max_attempts=4,
                initial_delay=0.5,
                max_delay=10.0,
                exponential_base=1.5,
                jitter=True,
                backoff_strategy=BackoffStrategy.EXPONENTIAL,
                retry_on=MEDICAL_RETRY_EXCEPTIONS,
                exclude=MEDICAL_NO_RETRY_EXCEPTIONS,
            )

        # Routine operations - conservative approach
        else:
            return RetryConfig(
                max_attempts=3,
                initial_delay=1.0,
                max_delay=30.0,
                exponential_base=2.0,
                jitter=True,
                backoff_strategy=BackoffStrategy.EXPONENTIAL,
                retry_on=MEDICAL_RETRY_EXCEPTIONS,
                exclude=MEDICAL_NO_RETRY_EXCEPTIONS,
            )


def medical_retry(
    urgency_level: int = 2, operation_type: str = "standard", audit: bool = True
) -> Callable:
    """
    Return decorator for medical operations with appropriate retry logic.

    Args:
        urgency_level: 1-5 scale (5 = emergency)
        operation_type: Type of medical operation
        audit: Whether to enable audit logging

    Returns:
        Decorated function
    """

    def decorator(func: Callable) -> Callable:
        # Get appropriate retry config
        config = MedicalRetryPolicy.get_retry_config(urgency_level, operation_type)

        # Add medical-specific callbacks
        if audit:
            original_on_retry = config.on_retry
            original_on_failure = config.on_failure

            def medical_on_retry(exception: Exception, attempt: int) -> None:
                logger.warning(
                    "Medical operation %s retry %d: %s",
                    func.__name__,
                    attempt,
                    exception,
                    extra={
                        "operation": func.__name__,
                        "urgency": urgency_level,
                        "type": operation_type,
                        "attempt": attempt,
                        "exception": str(exception),
                    },
                )
                if original_on_retry:
                    original_on_retry(exception, attempt)

            def medical_on_failure(exception: Exception) -> None:
                logger.error(
                    "Medical operation %s failed: %s",
                    func.__name__,
                    exception,
                    extra={
                        "operation": func.__name__,
                        "urgency": urgency_level,
                        "type": operation_type,
                        "exception": str(exception),
                        "alert": "medical_failure",
                    },
                )
                if original_on_failure:
                    original_on_failure(exception)

            config.on_retry = medical_on_retry
            config.on_failure = medical_on_failure

        # Apply retry decorator
        return cast(Callable, retry_with_backoff(config)(func))

    return decorator


def get_medical_retry_decorator(
    context: Any, operation_type: str = "standard"
) -> Callable:
    """
    Get retry decorator based on medical context.

    Args:
        context: Medical context with urgency level
        operation_type: Type of operation

    Returns:
        Retry decorator
    """
    return medical_retry(
        urgency_level=context.urgency_level, operation_type=operation_type, audit=True
    )
