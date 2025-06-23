"""Main FastAPI application for Haven Health Passport.

This module creates and configures the FastAPI application with all
routers, middleware, and event handlers.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from typing import TYPE_CHECKING, AsyncIterator, Dict, Any

if TYPE_CHECKING:
    from starlette.middleware.sessions import SessionMiddleware
else:
    try:
        from starlette.middleware.sessions import SessionMiddleware
    except ImportError:
        SessionMiddleware = None

from src.api import (
    api_key_endpoints,
    auth_endpoints,
    cache_stats_endpoints,
    device_endpoints,
    documentation_endpoints,
    fhir_auth_endpoints,
    fido2_endpoints,
    file_endpoints,
    health,
    key_management_endpoints,
    live_demo_endpoints,
    medical_glossary_endpoints,
    rate_limit_bypass_endpoints,
    token_blacklist_endpoints,
    translation_endpoints,
    translation_memory_endpoints,
    translation_queue_endpoints,
)
from src.api.biometric import router as biometric_router
from src.api.v2 import (
    patient_endpoints,
    health_record_endpoints,
    analysis_endpoints,
    remediation_endpoints,
    notification_endpoints,
    websocket_health,
    dashboard,
    organization_endpoints,
    bulk_operations_endpoints,
    password_policy_endpoints,
    sync_endpoints,
    report_endpoints,
)
from src.api.openapi_config import configure_openapi
from src.api.versioning import version_middleware
from src.config import get_settings
from src.middleware.ip_allowlist import IPAllowlistMiddleware
from src.middleware.rate_limit import RateLimitMiddleware
from src.middleware.webauthn_middleware import WebAuthnMiddleware
from src.middleware.security_headers import SecurityHeadersMiddleware
from src.middleware.input_sanitization import (
    InputSanitizationMiddleware,
    CSRFProtectionMiddleware,
)
from src.middleware.edge_cache import EdgeCacheMiddleware
from src.utils.logging import setup_logging
from src.api.monitoring import setup_monitoring

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)

# Get settings
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan handler."""
    # Startup
    logger.info(f"Starting {settings.app_name} v{settings.app_version}")

    # Initialize database
    try:
        from src.core.database import init_db

        init_db()
        logger.info("Database initialized")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")

    # Initialize Redis if configured
    if settings.redis_url:
        try:
            import aioredis

            app.state.redis = await aioredis.from_url(settings.redis_url)
            logger.info("Redis connected")
        except Exception as e:
            logger.warning(f"Redis connection failed: {e}")

    yield

    # Shutdown
    logger.info("Shutting down application")

    # Close Redis connection
    if hasattr(app.state, "redis"):
        await app.state.redis.close()

    # Database connections handled by SQLAlchemy session lifecycle


# Create FastAPI application
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Secure, portable health records for refugees and displaced populations",
    docs_url="/api/docs" if settings.debug else None,
    redoc_url="/api/redoc" if settings.debug else None,
    openapi_url="/api/openapi.json" if settings.debug else None,
    lifespan=lifespan,
)

# Add middleware

# Security Headers (should be first)
app.add_middleware(SecurityHeadersMiddleware)

# Input Sanitization
app.add_middleware(InputSanitizationMiddleware)

# CSRF Protection
app.add_middleware(CSRFProtectionMiddleware)

# Edge Cache (before CORS for proper header handling)
app.add_middleware(EdgeCacheMiddleware)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-API-Version", "X-Request-ID"],
    max_age=3600,  # 1 hour cache for preflight requests
)

# Trusted Host
if settings.environment == "production":
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["api.havenhealthpassport.org", "*.havenhealthpassport.org"],
    )

# Session
if SessionMiddleware is not None:
    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.secret_key,
        session_cookie="haven_session",
        max_age=86400,  # 24 hours
        same_site="lax",
        https_only=settings.environment == "production",
    )

# Rate Limiting
app.add_middleware(RateLimitMiddleware)

# IP Allowlist (for admin endpoints)
if settings.environment == "production":
    app.add_middleware(IPAllowlistMiddleware)

# API Versioning
app.middleware("http")(version_middleware)

# WebAuthn middleware for biometric endpoints
app.add_middleware(WebAuthnMiddleware)

# Include routers

# Health check endpoints
app.include_router(health.router, prefix="", tags=["health"])

# Documentation endpoints
app.include_router(
    documentation_endpoints.router, prefix="/api/v2", tags=["documentation"]
)

# Authentication endpoints
app.include_router(auth_endpoints.router, prefix="/api/v2", tags=["authentication"])

# API Key management endpoints
app.include_router(api_key_endpoints.router, prefix="/api/v2", tags=["api-keys"])

# Key management endpoints (admin only)
app.include_router(
    key_management_endpoints.router, prefix="/api/v2", tags=["admin", "key-management"]
)

# Token blacklist endpoints (admin only)
app.include_router(
    token_blacklist_endpoints.router,
    prefix="/api/v2",
    tags=["admin", "token-management"],
)

# Rate limit bypass management endpoints (admin only)
app.include_router(
    rate_limit_bypass_endpoints.router, prefix="/api/v2", tags=["admin", "rate-limit"]
)

# Cache statistics endpoints (admin/monitoring only)
app.include_router(
    cache_stats_endpoints.router,
    prefix="/api/v2",
    tags=["admin", "monitoring", "cache"],
)

# FIDO2 authentication endpoints
app.include_router(fido2_endpoints.router, prefix="/api/v2", tags=["fido2"])

# Device management endpoints
app.include_router(device_endpoints.router, prefix="/api/v2", tags=["devices"])

# Biometric authentication endpoints
app.include_router(biometric_router, prefix="/api/v2", tags=["biometric-auth"])

# File management endpoints
app.include_router(file_endpoints.router, prefix="/api/v2", tags=["files"])

# Translation endpoints
app.include_router(
    translation_endpoints.router, prefix="/api/v2", tags=["translations"]
)

# Translation memory endpoints
app.include_router(
    translation_memory_endpoints.router, prefix="/api/v2", tags=["translation-memory"]
)

# Medical glossary endpoints
app.include_router(
    medical_glossary_endpoints.router, prefix="/api/v2", tags=["medical-glossary"]
)

# Translation queue endpoints
app.include_router(
    translation_queue_endpoints.router, prefix="/api/v2", tags=["translation-queue"]
)

# Live Demo AWS Services endpoints
app.include_router(live_demo_endpoints.router, tags=["live-demo", "aws-services"])

# FHIR authentication endpoints
app.include_router(fhir_auth_endpoints.router, prefix="/api/v1", tags=["fhir-auth"])

# Core v2 API endpoints
# Patient management endpoints
app.include_router(patient_endpoints, prefix="/api/v2", tags=["patients"])

# Health records management endpoints
app.include_router(health_record_endpoints, prefix="/api/v2", tags=["health-records"])

# AI-powered analysis endpoints
app.include_router(analysis_endpoints, prefix="/api/v2", tags=["analysis"])

# Remediation and treatment plan endpoints
app.include_router(remediation_endpoints, prefix="/api/v2", tags=["remediation"])

# Notification management endpoints
app.include_router(notification_endpoints, prefix="/api/v2", tags=["notifications"])

# Dashboard and analytics endpoints
app.include_router(dashboard, prefix="/api/v2", tags=["dashboard", "analytics"])

# Report endpoints
app.include_router(report_endpoints, prefix="/api/v2", tags=["reports"])

# Organization management endpoints
app.include_router(organization_endpoints, prefix="/api/v2", tags=["organizations"])

# Bulk operations endpoints
app.include_router(
    bulk_operations_endpoints, prefix="/api/v2", tags=["bulk-operations"]
)

# Password policy endpoints
app.include_router(password_policy_endpoints)

# Sync endpoints for offline functionality
app.include_router(sync_endpoints, prefix="/api/v2", tags=["sync", "offline"])

# GraphQL endpoint - temporarily disabled for testing
# try:
#     from src.api.graphql_setup import create_graphql_router, create_graphql_schema
#     from src.api.strawberry_schema import schema
#
#     # Create GraphQL router with Strawberry
#     graphql_router = create_graphql_router(schema)
#     app.include_router(graphql_router)
#     logger.info("GraphQL endpoint mounted at /graphql using Strawberry")
# except ImportError as e:
#     logger.warning(f"GraphQL dependencies not installed: {e}")
logger.info("GraphQL temporarily disabled for testing")

# WebSocket endpoint for subscriptions
try:
    from src.api.websocket import handle_websocket_connection

    app.add_api_websocket_route("/ws", handle_websocket_connection)
    logger.info("WebSocket endpoint mounted at /ws")
except ImportError:
    logger.warning("WebSocket support not available")

# Health WebSocket endpoint for real-time updates
app.include_router(websocket_health, prefix="/api/v2")

# Configure OpenAPI documentation
from src.api.openapi_config import configure_openapi

configure_openapi(app)

# Set up monitoring
setup_monitoring(app)


# Startup and shutdown events
@app.on_event("startup")
async def startup_event() -> None:
    """Initialize services on startup."""
    # Start background monitoring if not in test environment
    if hasattr(app.state, "monitoring") and settings.environment != "test":
        import asyncio

        monitoring_service = app.state.monitoring
        asyncio.create_task(monitoring_service.background_monitoring())


@app.on_event("shutdown")
async def shutdown_event() -> None:
    """Cleanup on shutdown."""
    # Cleanup tasks if needed
    pass


# Root endpoint
@app.get("/")
async def root() -> Dict[str, Any]:
    """Root endpoint."""
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "status": "running",
        "docs": "/api/docs" if settings.debug else None,
    }


# API info endpoint
@app.get("/api")
async def api_info() -> Dict[str, Any]:
    """API information endpoint."""
    return {
        "name": f"{settings.app_name} API",
        "version": settings.app_version,
        "endpoints": {
            "rest": "/api/v2",
            "graphql": "/graphql",
            "websocket": "/ws",
            "health": "/health",
            "docs": "/api/docs" if settings.debug else None,
        },
    }


# Error handlers
@app.exception_handler(404)
async def not_found_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle 404 errors."""
    return JSONResponse(
        status_code=404,
        content={
            "error": "Not Found",
            "message": f"The requested URL {request.url.path} was not found",
            "status_code": 404,
        },
    )


@app.exception_handler(500)
async def internal_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle 500 errors."""
    logger.error(f"Internal server error: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal Server Error",
            "message": "An unexpected error occurred",
            "status_code": 500,
        },
    )


# Export app for uvicorn
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.debug,
        log_level=settings.log_level.lower(),
    )
