"""Monitoring and observability utilities."""

import logging
import time
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Dict, Optional

try:
    from opentelemetry import trace
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.trace import Status, StatusCode

    OPENTELEMETRY_AVAILABLE = True
except ImportError:
    OPENTELEMETRY_AVAILABLE = False
    trace = None
    OTLPSpanExporter = None
    Resource = None
    TracerProvider = None
    BatchSpanProcessor = None
    Status = None
    StatusCode = None

try:
    from prometheus_client import REGISTRY, Counter, Gauge, Histogram, Info

    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False
    Counter = None  # type: ignore[assignment,misc]
    Gauge = None  # type: ignore[assignment,misc]
    Histogram = None  # type: ignore[assignment,misc]
    Info = None  # type: ignore[assignment,misc]
    REGISTRY = None  # type: ignore[assignment]

from src.config import get_settings
from src.utils.logging import get_logger

logger = logging.getLogger(__name__)

# Prometheus metrics
if PROMETHEUS_AVAILABLE:
    try:
        http_requests_total = Counter(
            "http_requests_total",
            "Total number of HTTP requests",
            ["method", "endpoint", "status"],
        )

        http_request_duration_seconds = Histogram(
            "http_request_duration_seconds",
            "HTTP request latency",
            ["method", "endpoint"],
        )

        active_connections = Gauge("active_connections", "Number of active connections")

        database_connections = Gauge(
            "database_connections_active",
            "Number of active database connections",
            ["database"],
        )

        cache_hits = Counter(
            "cache_hits_total", "Total number of cache hits", ["cache_type"]
        )

        cache_misses = Counter(
            "cache_misses_total", "Total number of cache misses", ["cache_type"]
        )

        authentication_attempts = Counter(
            "authentication_attempts_total",
            "Total number of authentication attempts",
            ["method", "success"],
        )

        api_calls_total = Counter(
            "api_calls_total",
            "Total number of API calls",
            ["api_name", "operation", "status"],
        )

        blockchain_transactions = Counter(
            "blockchain_transactions_total",
            "Total number of blockchain transactions",
            ["type", "status"],
        )

        app_info = Info("app", "Application information")
    except ValueError:
        # Metrics already registered, retrieve them from the registry

        def get_collector(name: str) -> Optional[Any]:
            """Get collector from registry by name."""
            # Access internal registry structure - pylint: disable=protected-access
            return REGISTRY._names_to_collectors.get(name)

        http_requests_total = get_collector("http_requests_total")  # type: ignore[assignment]
        http_request_duration_seconds = get_collector("http_request_duration_seconds")  # type: ignore[assignment]
        active_connections = get_collector("active_connections")  # type: ignore[assignment]
        database_connections = get_collector("database_connections_active")  # type: ignore[assignment]
        cache_hits = get_collector("cache_hits_total")  # type: ignore[assignment]
        cache_misses = get_collector("cache_misses_total")  # type: ignore[assignment]
        authentication_attempts = get_collector("authentication_attempts_total")  # type: ignore[assignment]
        api_calls_total = get_collector("api_calls_total")  # type: ignore[assignment]
        blockchain_transactions = get_collector("blockchain_transactions_total")  # type: ignore[assignment]
        app_info = get_collector("app")  # type: ignore[assignment]
else:
    # Create dummy metrics when Prometheus is not available
    http_requests_total = None  # type: ignore[assignment]
    http_request_duration_seconds = None  # type: ignore[assignment]
    active_connections = None  # type: ignore[assignment]
    database_connections = None  # type: ignore[assignment]
    cache_hits = None  # type: ignore[assignment]
    cache_misses = None  # type: ignore[assignment]
    authentication_attempts = None  # type: ignore[assignment]
    api_calls_total = None  # type: ignore[assignment]
    blockchain_transactions = None  # type: ignore[assignment]
    app_info = None  # type: ignore[assignment]


class MetricsCollector:
    """Collect and export application metrics."""

    def __init__(self) -> None:
        """Initialize metrics collector."""
        self.logger = get_logger(__name__)
        settings = get_settings()

        # Set application info
        if PROMETHEUS_AVAILABLE and app_info:
            app_info.info(
                {
                    "version": settings.app_version,
                    "environment": settings.environment,
                    "region": settings.aws_region,
                }
            )

    def record_request(
        self, method: str, endpoint: str, status: int, duration: float
    ) -> None:
        """Record HTTP request metrics."""
        if (
            PROMETHEUS_AVAILABLE
            and http_requests_total
            and http_request_duration_seconds
        ):
            http_requests_total.labels(
                method=method, endpoint=endpoint, status=str(status)
            ).inc()
            http_request_duration_seconds.labels(
                method=method, endpoint=endpoint
            ).observe(duration)

    def record_cache_access(self, cache_type: str, hit: bool) -> None:
        """Record cache access metrics."""
        if PROMETHEUS_AVAILABLE and cache_hits and cache_misses:
            if hit:
                cache_hits.labels(cache_type=cache_type).inc()
            else:
                cache_misses.labels(cache_type=cache_type).inc()

    def record_auth_attempt(self, method: str, success: bool) -> None:
        """Record authentication attempt."""
        if PROMETHEUS_AVAILABLE and authentication_attempts:
            authentication_attempts.labels(method=method, success=str(success)).inc()

    def record_api_call(self, api_name: str, operation: str, status: str) -> None:
        """Record external API call."""
        if PROMETHEUS_AVAILABLE and api_calls_total:
            api_calls_total.labels(
                api_name=api_name, operation=operation, status=status
            ).inc()

    def record_blockchain_transaction(self, tx_type: str, status: str) -> None:
        """Record blockchain transaction."""
        if PROMETHEUS_AVAILABLE and blockchain_transactions:
            blockchain_transactions.labels(type=tx_type, status=status).inc()

    def record_bedrock_request(
        self,
        model_id: str,
        latency: float,
        success: bool,
        error_code: Optional[str] = None,
    ) -> None:
        """Record Bedrock API request metrics."""
        if PROMETHEUS_AVAILABLE and api_calls_total and http_request_duration_seconds:
            status = "success" if success else "failure"
            api_calls_total.labels(
                api_name="bedrock", operation=f"invoke_{model_id}", status=status
            ).inc()

            # Log error code if provided
            if error_code:
                logger.warning("Bedrock request failed with error code: %s", error_code)

            # Record latency for successful requests
            if success:
                http_request_duration_seconds.labels(
                    method="POST", endpoint=f"/bedrock/{model_id}"
                ).observe(latency)

    def update_connection_count(self, delta: int) -> None:
        """Update active connection count."""
        if PROMETHEUS_AVAILABLE and active_connections:
            if delta > 0:
                active_connections.inc(delta)
            else:
                active_connections.dec(abs(delta))

    def update_db_connections(self, database: str, count: int) -> None:
        """Update database connection count."""
        if PROMETHEUS_AVAILABLE and database_connections:
            database_connections.labels(database=database).set(count)


class TracingService:
    """OpenTelemetry tracing service."""

    def __init__(self) -> None:
        """Initialize tracing service."""
        settings = get_settings()
        self.logger = get_logger(__name__)

        if not settings.tracing_enabled or not OPENTELEMETRY_AVAILABLE:
            self.tracer = None
            return

        # Configure OpenTelemetry
        resource = Resource.create(
            {
                "service.name": "haven-health-passport",
                "service.version": settings.app_version,
                "deployment.environment": settings.environment,
            }
        )

        provider = TracerProvider(resource=resource)

        # Configure OTLP exporter if endpoint is provided
        if hasattr(settings, "otlp_endpoint") and settings.otlp_endpoint:
            otlp_exporter = OTLPSpanExporter(
                endpoint=settings.otlp_endpoint,
                insecure=True,  # Use secure=False for local development
            )
            provider.add_span_processor(BatchSpanProcessor(otlp_exporter))

        trace.set_tracer_provider(provider)
        self.tracer = trace.get_tracer(__name__)

    @asynccontextmanager
    async def trace_operation(
        self, name: str, attributes: Optional[Dict[str, Any]] = None
    ) -> AsyncIterator[None]:
        """Context manager for tracing operations."""
        if not self.tracer:
            yield
            return

        with self.tracer.start_as_current_span(name) as span:
            if attributes:
                span.set_attributes(attributes)

            try:
                yield span
            except (RuntimeError, TypeError, ValueError) as e:
                span.set_status(Status(StatusCode.ERROR, str(e)))
                span.record_exception(e)
                raise
            else:
                span.set_status(Status(StatusCode.OK))


class HealthChecker:
    """Service health checking."""

    def __init__(self) -> None:
        """Initialize health checker."""
        self.logger = get_logger(__name__)
        self.checks: Dict[str, Any] = {}

    def register_check(self, name: str, check_func: Any) -> None:
        """Register a health check."""
        self.checks[name] = check_func

    async def check_health(self) -> Dict[str, Any]:
        """Run all health checks."""
        results: Dict[str, Any] = {
            "status": "healthy",
            "timestamp": time.time(),
            "checks": {},
        }

        for name, check_func in self.checks.items():
            try:
                start = time.time()
                result = await check_func()
                duration = time.time() - start

                results["checks"][name] = {
                    "status": "healthy" if result else "unhealthy",
                    "duration_ms": round(duration * 1000, 2),
                }

                if not result:
                    results["status"] = "unhealthy"

            except (OSError, RuntimeError) as e:
                self.logger.error(f"Health check failed: {name}", error=str(e))
                results["checks"][name] = {"status": "unhealthy", "error": str(e)}
                results["status"] = "unhealthy"

        return results


# Global instances
metrics_collector = MetricsCollector()
tracing_service = TracingService()
health_checker = HealthChecker()
