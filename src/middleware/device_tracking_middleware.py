"""Device tracking middleware for FastAPI.

This middleware handles automatic device fingerprint extraction and tracking
for authenticated requests.
"""

from typing import Awaitable, Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from src.utils.logging import get_logger

logger = get_logger(__name__)


class DeviceTrackingMiddleware(BaseHTTPMiddleware):
    """Middleware for device tracking on authenticated endpoints."""

    def __init__(self, app: ASGIApp):
        """Initialize device tracking middleware."""
        super().__init__(app)

        # Endpoints that require device tracking
        self.tracked_endpoints = [
            "/api/v2/auth/login",
            "/api/v2/auth/refresh",
            "/api/v2/patient",
            "/api/v2/health-records",
        ]

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        """Process request for device tracking."""
        # Check if endpoint needs device tracking
        needs_tracking = any(
            request.url.path.startswith(endpoint) for endpoint in self.tracked_endpoints
        )

        if needs_tracking and request.headers.get("Authorization"):
            # Check for device fingerprint
            device_fingerprint = request.headers.get("X-Device-Fingerprint")

            if not device_fingerprint:
                logger.warning(
                    f"Missing device fingerprint for authenticated request: {request.url.path}"
                )

        response = await call_next(request)
        return response
