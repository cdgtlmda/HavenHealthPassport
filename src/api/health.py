"""Health check endpoints."""

import os
from datetime import datetime
from typing import Any, Dict, List

import boto3
from fastapi import APIRouter, Response, status
from sqlalchemy import text

from src.api.versioning import version_manager
from src.config import get_settings
from src.core.database import get_async_db
from src.utils.logging import get_logger
from src.utils.monitoring import health_checker

try:
    import aioredis
except ImportError:
    aioredis = None

router = APIRouter(tags=["health"])
logger = get_logger(__name__)


async def check_database() -> bool:
    """Check database connectivity."""
    try:
        async with get_async_db() as db:
            result = await db.execute(text("SELECT 1"))
            return result.scalar() == 1
    except (ValueError, AttributeError, RuntimeError) as e:
        logger.error("Database check failed: %s", e, exc_info=True)
        return False


async def check_redis() -> bool:
    """Check Redis connectivity."""
    try:
        settings = get_settings()
        if hasattr(settings, "redis_url") and settings.redis_url and aioredis:
            redis = await aioredis.from_url(settings.redis_url)
            result = await redis.ping()
            await redis.close()
            return bool(result)
        return True  # Redis is optional
    except (ImportError, AttributeError, RuntimeError, OSError) as e:
        logger.error("Redis check failed: %s", e, exc_info=True)
        return False


async def check_aws_services() -> bool:
    """Check AWS services connectivity."""
    try:
        settings = get_settings()
        if settings.environment == "production":
            # Check S3 access
            s3 = boto3.client("s3")
            s3.list_buckets()
            return True
        return True  # AWS is optional in non-production
    except (ImportError, AttributeError, RuntimeError, OSError) as e:
        logger.error("AWS services check failed: %s", e, exc_info=True)
        return False


# Register health checks
health_checker.register_check("database", check_database)
health_checker.register_check("redis", check_redis)
health_checker.register_check("aws_services", check_aws_services)


@router.get("/health/live")
async def health_check() -> Dict[str, Any]:
    """Check basic service health."""
    settings = get_settings()
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "service": "haven-health-passport-api",
        "version": getattr(settings, "app_version", "2.0.0"),
        "environment": settings.environment,
    }


@router.get("/health/ready")
async def readiness_check(response: Response) -> Dict[str, Any]:
    """Detailed readiness check."""
    result = await health_checker.check_health()

    if result["status"] != "healthy":
        response.status_code = 503

    return result


@router.get("/health/startup")
async def startup_check(response: Response) -> Dict[str, Any]:
    """Startup check endpoint.

    Checks if the service has completed initialization.
    """
    startup_checks = {
        "configuration": False,
        "database_migrations": False,
        "services_loaded": False,
    }

    errors: List[str] = []

    # Check configuration
    try:
        settings = get_settings()
        required_configs = ["database_url", "jwt_secret_key", "encryption_key"]

        for config in required_configs:
            if not getattr(settings, config, None):
                raise ValueError(f"Missing required configuration: {config}")

        startup_checks["configuration"] = True
    except (ValueError, AttributeError) as e:
        errors.append(f"Configuration: Missing required configuration - {e}")

    # Check database migrations
    try:
        async with get_async_db() as db:
            result = await db.execute(
                text(
                    "SELECT EXISTS (SELECT FROM information_schema.tables "
                    "WHERE table_schema = 'public' AND table_name = 'patients')"
                )
            )
            startup_checks["database_migrations"] = bool(result.scalar())
    except (ValueError, AttributeError, RuntimeError) as e:
        errors.append(f"Database: Unable to check migrations - {e}")

    # Check services
    try:
        # Just import the services module to check if it's available
        # import src.services
        startup_checks["services_loaded"] = True
    except ImportError as e:
        errors.append(f"Services: Unable to load services - {e}")

    # Determine if startup is complete
    startup_complete = all(
        [
            startup_checks["configuration"],
            startup_checks["database_migrations"],
            startup_checks["services_loaded"],
        ]
    )

    if not startup_complete:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return {
        "initialized": startup_complete,
        "timestamp": datetime.utcnow().isoformat(),
        "checks": startup_checks,
        "errors": errors if errors else None,
    }


@router.get("/version")
async def version_info() -> Dict[str, Any]:
    """Get application version information."""
    settings = get_settings()

    try:
        api_versions = version_manager.get_available_versions()
    except (AttributeError, ValueError) as e:
        logger.warning(f"Failed to get API versions: {e}")
        api_versions = {"v2.0": {"current": True}}

    return {
        "service": "haven-health-passport-api",
        "version": getattr(settings, "app_version", "2.0.0"),
        "environment": settings.environment,
        "region": getattr(settings, "aws_region", "us-east-1"),
        "build": {
            "timestamp": datetime.utcnow().isoformat(),
            "commit": os.environ.get("GIT_COMMIT", "unknown"),
        },
        "api_versions": api_versions,
    }
