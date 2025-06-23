"""
Retry Manager for Coordinating Retry Strategies.

Provides centralized management of retry policies across different
agent types and operations.
"""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Dict, Optional

from .circuit_breaker import CircuitBreaker, CircuitBreakerConfig
from .retry_decorator import RetryConfig, retry_with_backoff

logger = logging.getLogger(__name__)


class RetryStrategy(str, Enum):
    """Predefined retry strategies."""

    AGGRESSIVE = "aggressive"  # Many retries, short delays
    STANDARD = "standard"  # Balanced approach
    CONSERVATIVE = "conservative"  # Few retries, long delays
    MEDICAL_CRITICAL = "medical_critical"  # For critical medical ops


@dataclass
class RetryProfile:
    """Profile defining retry behavior."""

    name: str
    config: RetryConfig
    circuit_breaker_config: Optional[CircuitBreakerConfig] = None
    description: str = ""


class RetryManager:
    """
    Centralized retry management for LangChain agents.

    Provides:
    - Predefined retry strategies
    - Circuit breaker integration
    - Metrics collection
    - Dynamic retry adjustment
    """

    def __init__(self) -> None:
        """Initialize retry manager."""
        self._profiles: Dict[str, RetryProfile] = {}
        self._circuit_breakers: Dict[str, CircuitBreaker] = {}
        self._metrics: Dict[str, Dict[str, Any]] = {}
        self._initialize_default_profiles()

    def _initialize_default_profiles(self) -> None:
        """Initialize default retry profiles."""
        # Aggressive strategy - for non-critical operations
        self.register_profile(
            RetryProfile(
                name=RetryStrategy.AGGRESSIVE,
                config=RetryConfig(
                    max_attempts=5,
                    initial_delay=0.5,
                    max_delay=10.0,
                    exponential_base=1.5,
                    jitter=True,
                ),
                circuit_breaker_config=CircuitBreakerConfig(
                    failure_threshold=10, success_threshold=3, timeout=30.0
                ),
                description="Aggressive retry for non-critical operations",
            )
        )

        # Standard strategy - balanced approach
        self.register_profile(
            RetryProfile(
                name=RetryStrategy.STANDARD,
                config=RetryConfig(
                    max_attempts=3,
                    initial_delay=1.0,
                    max_delay=30.0,
                    exponential_base=2.0,
                    jitter=True,
                ),
                circuit_breaker_config=CircuitBreakerConfig(
                    failure_threshold=5, success_threshold=2, timeout=60.0
                ),
                description="Standard retry strategy",
            )
        )

        # Conservative strategy - for expensive operations
        self.register_profile(
            RetryProfile(
                name=RetryStrategy.CONSERVATIVE,
                config=RetryConfig(
                    max_attempts=2,
                    initial_delay=2.0,
                    max_delay=60.0,
                    exponential_base=3.0,
                    jitter=True,
                ),
                circuit_breaker_config=CircuitBreakerConfig(
                    failure_threshold=3, success_threshold=1, timeout=120.0
                ),
                description="Conservative retry for expensive operations",
            )
        )

        # Medical critical - for health-critical operations
        self.register_profile(
            RetryProfile(
                name=RetryStrategy.MEDICAL_CRITICAL,
                config=RetryConfig(
                    max_attempts=4,
                    initial_delay=0.5,
                    max_delay=5.0,
                    exponential_base=1.5,
                    jitter=False,  # No jitter for consistency
                    # Only retry on specific exceptions
                    retry_on=(ConnectionError, TimeoutError),
                    # Callbacks for monitoring
                    on_retry=self._medical_retry_callback,
                    on_failure=self._medical_failure_callback,
                ),
                circuit_breaker_config=CircuitBreakerConfig(
                    failure_threshold=3,
                    success_threshold=1,
                    timeout=30.0,
                    half_open_requests=1,
                ),
                description="Retry strategy for critical medical operations",
            )
        )

    def register_profile(self, profile: RetryProfile) -> None:
        """Register a retry profile."""
        self._profiles[profile.name] = profile

        # Create circuit breaker if configured
        if profile.circuit_breaker_config:
            self._circuit_breakers[profile.name] = CircuitBreaker(
                profile.circuit_breaker_config
            )

    def get_retry_decorator(
        self, strategy: RetryStrategy, operation_name: Optional[str] = None
    ) -> Callable:
        """Get retry decorator for strategy."""
        profile = self._profiles.get(strategy)
        if not profile:
            raise ValueError(f"Unknown retry strategy: {strategy}")

        # Get or create circuit breaker
        circuit_breaker = self._circuit_breakers.get(strategy)

        # Create config with circuit breaker
        config = RetryConfig(**profile.config.__dict__, circuit_breaker=circuit_breaker)

        # Track metrics
        if operation_name:
            self._init_metrics(operation_name)

        return retry_with_backoff(config)

    def _init_metrics(self, operation_name: str) -> None:
        """Initialize metrics for operation."""
        if operation_name not in self._metrics:
            self._metrics[operation_name] = {
                "attempts": 0,
                "successes": 0,
                "failures": 0,
                "total_retry_time": 0.0,
            }

    def _medical_retry_callback(self, exception: Exception, attempt: int) -> None:
        """Execute callback for medical retry attempts."""
        logger.warning(
            "Medical operation retry attempt %d: %s",
            attempt,
            exception,
            extra={"alert_type": "medical_retry", "severity": "high"},
        )

    def _medical_failure_callback(self, exception: Exception) -> None:
        """Execute callback for medical operation failures."""
        logger.error(
            "Medical operation failed after all retries: %s",
            exception,
            extra={"alert_type": "medical_failure", "severity": "critical"},
        )

    def get_circuit_breaker_status(self) -> Dict[str, Dict[str, Any]]:
        """Get status of all circuit breakers."""
        return {name: cb.get_metrics() for name, cb in self._circuit_breakers.items()}

    def reset_circuit_breaker(self, strategy: RetryStrategy) -> None:
        """Manually reset a circuit breaker."""
        if strategy in self._circuit_breakers:
            self._circuit_breakers[strategy].reset()
            logger.info("Circuit breaker reset for %s", strategy)

    def get_metrics(self) -> Dict[str, Any]:
        """Get retry metrics."""
        return {
            "operations": self._metrics,
            "circuit_breakers": self.get_circuit_breaker_status(),
        }


# Global retry manager instance
retry_manager = RetryManager()
