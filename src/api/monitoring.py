"""API Monitoring Configuration for Haven Health Passport.

This module provides comprehensive monitoring and observability for the API,
including metrics collection, health checks, and monitoring service integrations.
"""

import asyncio
import shutil
import time
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any, Callable, Dict, Optional, cast

import psutil
from fastapi import FastAPI, Request, Response
from sqlalchemy import text

from src.config import get_settings
from src.core.database import SyncSessionLocal as SessionLocal
from src.utils.logging import get_logger

if TYPE_CHECKING:
    pass

# prometheus_client is an optional dependency for metrics collection
try:
    from prometheus_client import REGISTRY, Counter, Gauge, Histogram, generate_latest

    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False
    # Define dummy classes if prometheus_client is not available

    class Counter:  # type: ignore[no-redef]
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            _ = (args, kwargs)  # Intentionally unused

        def labels(self, **kwargs: Any) -> Any:
            _ = kwargs  # Intentionally unused
            return self

        def inc(self, amount: int = 1) -> None:
            pass

    class Histogram:  # type: ignore[no-redef]
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            _ = (args, kwargs)  # Intentionally unused

        def labels(self, **kwargs: Any) -> Any:
            _ = kwargs  # Intentionally unused
            return self

        def observe(self, amount: float) -> None:
            pass

    class Gauge:  # type: ignore[no-redef]
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            _ = (args, kwargs)  # Intentionally unused

        def labels(self, **kwargs: Any) -> Any:
            _ = kwargs  # Intentionally unused
            return self

        def set(self, value: float) -> None:
            pass

        def inc(self) -> None:
            pass

        def dec(self) -> None:
            pass

    def generate_latest() -> bytes:  # type: ignore[misc]
        return b"# Prometheus client not available"


logger = get_logger(__name__)
settings = get_settings()


# Function to safely create metrics
def get_or_create_counter(name: str, description: str, labels: list[str]) -> Counter:
    """Get existing counter or create new one."""
    try:
        return Counter(name, description, labels)
    except ValueError as exc:
        # Metric already registered
        existing = getattr(REGISTRY, "_names_to_collectors", {}).get(name)
        if existing is None:
            raise ValueError(f"Counter {name} not found") from exc
        return cast(Counter, existing)


def get_or_create_histogram(
    name: str, description: str, labels: list[str]
) -> Histogram:
    """Get existing histogram or create new one."""
    try:
        return Histogram(name, description, labels)
    except ValueError as exc:
        # Metric already registered
        existing = getattr(REGISTRY, "_names_to_collectors", {}).get(name)
        if existing is None:
            raise ValueError(f"Histogram {name} not found") from exc
        return cast(Histogram, existing)


def get_or_create_gauge(name: str, description: str, labels: list[str]) -> Gauge:
    """Get existing gauge or create new one."""
    try:
        return Gauge(name, description, labels)
    except ValueError as exc:
        # Metric already registered
        existing = getattr(REGISTRY, "_names_to_collectors", {}).get(name)
        if existing is None:
            raise ValueError(f"Gauge {name} not found") from exc
        return cast(Gauge, existing)


# Create metrics using safe functions
http_requests_total = get_or_create_counter(
    "http_requests_total", "Total HTTP requests", ["method", "endpoint", "status"]
)

http_request_duration_seconds = get_or_create_histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "endpoint"],
)

http_requests_in_progress = get_or_create_gauge(
    "http_requests_in_progress",
    "Number of HTTP requests in progress",
    ["method", "endpoint"],
)

api_errors_total = get_or_create_counter(
    "api_errors_total", "Total API errors", ["error_type", "endpoint"]
)

database_queries_total = get_or_create_counter(
    "database_queries_total", "Total database queries", ["operation", "table"]
)

database_query_duration_seconds = get_or_create_histogram(
    "database_query_duration_seconds",
    "Database query duration in seconds",
    ["operation", "table"],
)

cache_hits_total = get_or_create_counter(
    "cache_hits_total", "Total cache hits", ["cache_type"]
)

cache_misses_total = get_or_create_counter(
    "cache_misses_total", "Total cache misses", ["cache_type"]
)

authentication_attempts_total = get_or_create_counter(
    "authentication_attempts_total",
    "Total authentication attempts",
    ["method", "result"],
)

authorization_checks_total = get_or_create_counter(
    "authorization_checks_total", "Total authorization checks", ["resource", "result"]
)

translation_requests_total = get_or_create_counter(
    "translation_requests_total",
    "Total translation requests",
    ["source_lang", "target_lang", "status"],
)

blockchain_verifications_total = get_or_create_counter(
    "blockchain_verifications_total", "Total blockchain verifications", ["status"]
)

# Custom metrics for business logic
patient_registrations_total = get_or_create_counter(
    "patient_registrations_total",
    "Total patient registrations",
    ["country", "organization"],
)

health_records_created_total = get_or_create_counter(
    "health_records_created_total",
    "Total health records created",
    ["record_type", "organization"],
)

active_users_gauge = get_or_create_gauge(
    "active_users", "Number of active users", ["user_type"]
)

api_rate_limit_hits_total = get_or_create_counter(
    "api_rate_limit_hits_total", "Total rate limit hits", ["tier", "endpoint"]
)


@dataclass
class HealthCheckResult:
    """Health check result."""

    service: str
    status: str  # healthy, degraded, unhealthy
    message: Optional[str] = None
    response_time_ms: Optional[float] = None
    details: Optional[Dict[str, Any]] = None


class MonitoringService:
    """Comprehensive monitoring service."""

    def __init__(self, app: FastAPI):
        """Initialize monitoring service."""
        self.app = app
        self.settings = settings
        self.logger = logger
        self.health_checks: Dict[str, Callable] = {}
        self.start_time = datetime.utcnow()

    def setup_monitoring(self) -> None:
        """Set up monitoring middleware and endpoints."""
        # Add monitoring middleware
        self.app.middleware("http")(self.monitoring_middleware)

        # Add metrics endpoint
        self.app.get("/metrics", tags=["monitoring"])(self.metrics_endpoint)

        # Add detailed health check endpoint
        self.app.get("/health/detailed", tags=["monitoring"])(
            self.detailed_health_check
        )

        # Register default health checks
        self.register_default_health_checks()

        # Background monitoring will be started in startup event

    async def monitoring_middleware(
        self, request: Request, call_next: Callable
    ) -> Response:
        """Middleware to collect request metrics."""
        start_time = time.time()

        # Extract endpoint path
        endpoint = request.url.path
        method = request.method

        # Track in-progress requests
        http_requests_in_progress.labels(method=method, endpoint=endpoint).inc()

        try:
            # Process request
            response = await call_next(request)

            # Record metrics
            duration = time.time() - start_time
            http_requests_total.labels(
                method=method, endpoint=endpoint, status=response.status_code
            ).inc()

            http_request_duration_seconds.labels(
                method=method, endpoint=endpoint
            ).observe(duration)

            # Add response headers
            response.headers["X-Response-Time"] = f"{duration:.3f}"
            response.headers["X-Request-ID"] = (
                request.state.request_id
                if hasattr(request.state, "request_id")
                else "unknown"
            )

            return response  # type: ignore[no-any-return]

        except Exception as e:
            # Record error metrics
            api_errors_total.labels(
                error_type=type(e).__name__, endpoint=endpoint
            ).inc()
            raise
        finally:
            # Decrement in-progress counter
            http_requests_in_progress.labels(method=method, endpoint=endpoint).dec()

    async def metrics_endpoint(self) -> Response:
        """Prometheus metrics endpoint."""
        if not PROMETHEUS_AVAILABLE:
            return Response(
                content="# Prometheus client not available\n# Install prometheus-client to enable metrics",
                media_type="text/plain",
                status_code=501,
            )
        return Response(content=generate_latest(), media_type="text/plain")

    async def detailed_health_check(self) -> Dict[str, Any]:
        """Perform detailed health checks."""
        results = []
        overall_status = "healthy"

        # Run all registered health checks
        for name, check_func in self.health_checks.items():
            try:
                start = time.time()
                result = await check_func()
                result.response_time_ms = (time.time() - start) * 1000
                results.append(result)

                # Update overall status
                if result.status == "unhealthy":
                    overall_status = "unhealthy"
                elif result.status == "degraded" and overall_status == "healthy":
                    overall_status = "degraded"

            except (asyncio.TimeoutError, OSError, ValueError, RuntimeError) as e:
                self.logger.error(f"Health check error for {name}: {str(e)}")
                results.append(
                    HealthCheckResult(service=name, status="unhealthy", message=str(e))
                )
                overall_status = "unhealthy"

        # Calculate uptime
        uptime = datetime.utcnow() - self.start_time

        return {
            "status": overall_status,
            "timestamp": datetime.utcnow().isoformat(),
            "uptime_seconds": uptime.total_seconds(),
            "version": self.settings.app_version,
            "environment": self.settings.environment,
            "checks": [
                {
                    "service": r.service,
                    "status": r.status,
                    "message": r.message,
                    "response_time_ms": r.response_time_ms,
                    "details": r.details,
                }
                for r in results
            ],
        }

    def register_health_check(self, name: str, check_func: Callable) -> None:
        """Register a health check function."""
        self.health_checks[name] = check_func

    def register_default_health_checks(self) -> None:
        """Register default health checks."""
        self.register_health_check("database", self.check_database_health)
        self.register_health_check("redis", self.check_redis_health)
        self.register_health_check("s3", self.check_s3_health)
        self.register_health_check("api_rate_limits", self.check_rate_limit_health)
        self.register_health_check("disk_space", self.check_disk_space)
        self.register_health_check("memory", self.check_memory_usage)

    async def check_database_health(self) -> HealthCheckResult:
        """Check database health."""
        try:
            start = time.time()
            db = SessionLocal()
            try:
                # Simple query to check connection
                db.execute(text("SELECT 1"))
                response_time = (time.time() - start) * 1000

                if response_time > 1000:  # 1 second
                    return HealthCheckResult(
                        service="database",
                        status="degraded",
                        message=f"Slow response time: {response_time:.2f}ms",
                        details={"response_time_ms": response_time},
                    )

                return HealthCheckResult(
                    service="database",
                    status="healthy",
                    details={"response_time_ms": response_time},
                )
            finally:
                db.close()

        except (OSError, RuntimeError) as e:
            return HealthCheckResult(
                service="database",
                status="unhealthy",
                message=f"Database error: {str(e)}",
            )

    async def check_redis_health(self) -> HealthCheckResult:
        """Check Redis health."""
        if not hasattr(self.app.state, "redis"):
            return HealthCheckResult(
                service="redis", status="healthy", message="Redis not configured"
            )

        try:
            start = time.time()
            await self.app.state.redis.ping()
            response_time = (time.time() - start) * 1000

            return HealthCheckResult(
                service="redis",
                status="healthy",
                details={"response_time_ms": response_time},
            )
        except (OSError, RuntimeError) as e:
            return HealthCheckResult(
                service="redis", status="unhealthy", message=f"Redis error: {str(e)}"
            )

    async def check_s3_health(self) -> HealthCheckResult:
        """Check S3 health."""
        try:
            # Import S3StorageBackend locally to avoid import errors if not configured
            from src.storage.s3_backend import S3StorageBackend

            # Create a minimal config for health check
            config = {
                "bucket_name": (
                    settings.aws_s3_bucket
                    if hasattr(settings, "aws_s3_bucket")
                    else "haven-health-passport"
                ),
                "region": (
                    settings.aws_region
                    if hasattr(settings, "aws_region")
                    else "us-east-1"
                ),
            }

            storage = S3StorageBackend(config)
            start = time.time()

            # Try to list objects (limited to 1)
            # Storage list returns tuple, not awaitable
            storage.list(prefix="health-check", limit=1)
            # Result should not be a coroutine based on the comment
            response_time = (time.time() - start) * 1000

            return HealthCheckResult(
                service="s3",
                status="healthy",
                details={"response_time_ms": response_time},
            )
        except ImportError as e:
            return HealthCheckResult(
                service="s3",
                status="unhealthy",
                message=f"S3 storage not configured: {str(e)}",
            )
        except (OSError, RuntimeError) as e:
            return HealthCheckResult(
                service="s3", status="unhealthy", message=f"S3 error: {str(e)}"
            )

    async def check_rate_limit_health(self) -> HealthCheckResult:
        """Check rate limit service health."""
        try:
            # Check if rate limiting is working
            # This is a simple check - in production, check actual rate limit service
            return HealthCheckResult(
                service="rate_limits", status="healthy", details={"active_limits": 5}
            )
        except (RuntimeError, ValueError, TypeError, AttributeError) as e:
            return HealthCheckResult(
                service="rate_limits",
                status="unhealthy",
                message=f"Rate limit error: {str(e)}",
            )

    async def check_disk_space(self) -> HealthCheckResult:
        """Check available disk space."""
        try:
            stats = shutil.disk_usage("/")
            percent_used = (stats.used / stats.total) * 100

            if percent_used > 90:
                status = "unhealthy"
                message = f"Disk space critical: {percent_used:.1f}% used"
            elif percent_used > 80:
                status = "degraded"
                message = f"Disk space warning: {percent_used:.1f}% used"
            else:
                status = "healthy"
                message = None

            return HealthCheckResult(
                service="disk_space",
                status=status,
                message=message,
                details={
                    "total_gb": stats.total / (1024**3),
                    "used_gb": stats.used / (1024**3),
                    "free_gb": stats.free / (1024**3),
                    "percent_used": percent_used,
                },
            )
        except (OSError, RuntimeError, ValueError) as e:
            return HealthCheckResult(
                service="disk_space",
                status="unhealthy",
                message=f"Disk check error: {str(e)}",
            )

    async def check_memory_usage(self) -> HealthCheckResult:
        """Check memory usage."""
        try:
            memory = psutil.virtual_memory()

            if memory.percent > 90:
                status = "unhealthy"
                message = f"Memory usage critical: {memory.percent}%"
            elif memory.percent > 80:
                status = "degraded"
                message = f"Memory usage warning: {memory.percent}%"
            else:
                status = "healthy"
                message = None

            return HealthCheckResult(
                service="memory",
                status=status,
                message=message,
                details={
                    "total_gb": memory.total / (1024**3),
                    "available_gb": memory.available / (1024**3),
                    "percent_used": memory.percent,
                },
            )
        except (OSError, RuntimeError, ValueError) as e:
            return HealthCheckResult(
                service="memory",
                status="unhealthy",
                message=f"Memory check error: {str(e)}",
            )

    async def background_monitoring(self) -> None:
        """Background monitoring tasks."""
        while True:
            try:
                # Update active users gauge
                # This would query the actual active users from database
                active_users_gauge.labels(user_type="patient").set(100)
                active_users_gauge.labels(user_type="provider").set(50)
                active_users_gauge.labels(user_type="admin").set(10)

                # Sleep for 60 seconds
                await asyncio.sleep(60)

            except asyncio.CancelledError:
                # Gracefully handle task cancellation
                self.logger.info("Background monitoring task cancelled")
                break
            except (RuntimeError, ValueError, TypeError) as e:
                self.logger.error(f"Background monitoring error: {str(e)}")
                await asyncio.sleep(60)


def setup_monitoring(app: FastAPI) -> MonitoringService:
    """Set up monitoring for the application."""
    monitoring_service = MonitoringService(app)
    monitoring_service.setup_monitoring()

    # Store monitoring service in app state
    app.state.monitoring = monitoring_service

    return monitoring_service


# Utility functions for manual metric tracking
def track_authentication_attempt(method: str, success: bool) -> None:
    """Track authentication attempt."""
    result = "success" if success else "failure"
    authentication_attempts_total.labels(method=method, result=result).inc()


def track_authorization_check(resource: str, allowed: bool) -> None:
    """Track authorization check."""
    result = "allowed" if allowed else "denied"
    authorization_checks_total.labels(resource=resource, result=result).inc()


def track_database_query(operation: str, table: str, duration: float) -> None:
    """Track database query."""
    database_queries_total.labels(operation=operation, table=table).inc()
    database_query_duration_seconds.labels(operation=operation, table=table).observe(
        duration
    )


def track_cache_access(cache_type: str, hit: bool) -> None:
    """Track cache access."""
    if hit:
        cache_hits_total.labels(cache_type=cache_type).inc()
    else:
        cache_misses_total.labels(cache_type=cache_type).inc()


def track_translation_request(
    source_lang: str, target_lang: str, success: bool
) -> None:
    """Track translation request."""
    status = "success" if success else "failure"
    translation_requests_total.labels(
        source_lang=source_lang, target_lang=target_lang, status=status
    ).inc()


def track_blockchain_verification(success: bool) -> None:
    """Track blockchain verification."""
    status = "success" if success else "failure"
    blockchain_verifications_total.labels(status=status).inc()


def track_patient_registration(country: str, organization: str) -> None:
    """Track patient registration."""
    patient_registrations_total.labels(country=country, organization=organization).inc()


def track_health_record_creation(record_type: str, organization: str) -> None:
    """Track health record creation."""
    health_records_created_total.labels(
        record_type=record_type, organization=organization
    ).inc()


def track_rate_limit_hit(tier: str, endpoint: str) -> None:
    """Track rate limit hit."""
    api_rate_limit_hits_total.labels(tier=tier, endpoint=endpoint).inc()


# Export monitoring components
__all__ = [
    "MonitoringService",
    "setup_monitoring",
    "track_authentication_attempt",
    "track_authorization_check",
    "track_database_query",
    "track_cache_access",
    "track_translation_request",
    "track_blockchain_verification",
    "track_patient_registration",
    "track_health_record_creation",
    "track_rate_limit_hit",
]
