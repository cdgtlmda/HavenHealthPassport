"""
Circuit Breaker Pattern Implementation.

Provides circuit breaker functionality to prevent cascading failures
in distributed systems.
"""

import logging
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class CircuitBreakerState(str, Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failures exceeded threshold
    HALF_OPEN = "half_open"  # Testing if service recovered


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker."""

    failure_threshold: int = 5
    success_threshold: int = 2
    timeout: float = 60.0  # seconds
    half_open_requests: int = 1


class CircuitBreaker:
    """
    Circuit breaker implementation.

    States:
    - CLOSED: Normal operation, requests pass through
    - OPEN: Too many failures, requests blocked
    - HALF_OPEN: Testing recovery, limited requests allowed
    """

    def __init__(self, config: Optional[CircuitBreakerConfig] = None):
        """Initialize circuit breaker."""
        self.config = config or CircuitBreakerConfig()
        self._state = CircuitBreakerState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: Optional[float] = None
        self._half_open_requests = 0
        self._lock = threading.Lock()
        self._metrics: Dict[str, Any] = {
            "total_requests": 0,
            "failed_requests": 0,
            "successful_requests": 0,
            "rejected_requests": 0,
            "state_changes": [],
        }

    @property
    def state(self) -> CircuitBreakerState:
        """Get current circuit breaker state."""
        with self._lock:
            self._check_timeout()
            return self._state

    def can_execute(self) -> bool:
        """Check if request can be executed."""
        with self._lock:
            self._check_timeout()
            self._metrics["total_requests"] += 1

            if self._state == CircuitBreakerState.CLOSED:
                return True

            elif self._state == CircuitBreakerState.OPEN:
                self._metrics["rejected_requests"] += 1
                logger.warning("Circuit breaker is OPEN - request rejected")
                return False

            else:  # HALF_OPEN
                if self._half_open_requests < self.config.half_open_requests:
                    self._half_open_requests += 1
                    return True
                else:
                    self._metrics["rejected_requests"] += 1
                    logger.warning("Circuit breaker is HALF_OPEN - limit reached")
                    return False

    def record_success(self) -> None:
        """Record successful request."""
        with self._lock:
            self._metrics["successful_requests"] += 1

            if self._state == CircuitBreakerState.HALF_OPEN:
                self._success_count += 1
                logger.info(
                    "Half-open success: %d/%d",
                    self._success_count,
                    self.config.success_threshold,
                )

                if self._success_count >= self.config.success_threshold:
                    self._transition_to(CircuitBreakerState.CLOSED)

            elif self._state == CircuitBreakerState.CLOSED:
                # Reset failure count on success
                self._failure_count = 0

    def record_failure(self) -> None:
        """Record failed request."""
        with self._lock:
            self._metrics["failed_requests"] += 1
            self._last_failure_time = time.time()

            if self._state == CircuitBreakerState.CLOSED:
                self._failure_count += 1
                logger.warning(
                    "Failure recorded: %d/%d",
                    self._failure_count,
                    self.config.failure_threshold,
                )

                if self._failure_count >= self.config.failure_threshold:
                    self._transition_to(CircuitBreakerState.OPEN)

            elif self._state == CircuitBreakerState.HALF_OPEN:
                # Single failure in half-open state reopens circuit
                self._transition_to(CircuitBreakerState.OPEN)

    def _check_timeout(self) -> None:
        """Check if timeout has expired for open circuit."""
        if self._state == CircuitBreakerState.OPEN and self._last_failure_time:
            if time.time() - self._last_failure_time >= self.config.timeout:
                logger.info(
                    "Circuit breaker timeout expired - transitioning to HALF_OPEN"
                )
                self._transition_to(CircuitBreakerState.HALF_OPEN)

    def _transition_to(self, new_state: CircuitBreakerState) -> None:
        """Transition to new state."""
        old_state = self._state
        self._state = new_state

        # Record state change
        self._metrics["state_changes"].append(
            {
                "from": old_state,
                "to": new_state,
                "timestamp": datetime.utcnow().isoformat(),
            }
        )

        # Reset counters based on new state
        if new_state == CircuitBreakerState.CLOSED:
            self._failure_count = 0
            self._success_count = 0
            self._half_open_requests = 0
            logger.info("Circuit breaker CLOSED - normal operation resumed")

        elif new_state == CircuitBreakerState.OPEN:
            self._success_count = 0
            self._half_open_requests = 0
            logger.error(
                "Circuit breaker OPEN - will retry after %ds", self.config.timeout
            )

        elif new_state == CircuitBreakerState.HALF_OPEN:
            self._success_count = 0
            self._failure_count = 0
            self._half_open_requests = 0
            logger.info("Circuit breaker HALF_OPEN - testing recovery")

    def get_metrics(self) -> Dict[str, Any]:
        """Get circuit breaker metrics."""
        with self._lock:
            return {
                **self._metrics,
                "current_state": self._state,
                "failure_count": self._failure_count,
                "success_count": self._success_count,
            }

    def reset(self) -> None:
        """Manually reset circuit breaker."""
        with self._lock:
            logger.info("Circuit breaker manually reset")
            self._transition_to(CircuitBreakerState.CLOSED)
