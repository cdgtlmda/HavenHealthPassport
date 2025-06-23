"""FastAPI middleware for security headers."""

from typing import Any, Callable, List, Optional

from fastapi import FastAPI, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from .security_headers import SecurityHeaders


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """FastAPI middleware for adding security headers to responses."""

    def __init__(
        self,
        app: Any,
        environment: str = "production",
        cors_origins: Optional[List[str]] = None,
    ):
        """
        Initialize security headers middleware.

        Args:
            app: FastAPI application
            environment: Deployment environment
            cors_origins: List of allowed CORS origins
        """
        super().__init__(app)
        self.security_headers = SecurityHeaders(environment)
        self.cors_origins = cors_origins or ["https://havenhealthpassport.org"]

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process request and add security headers to response.

        Args:
            request: Incoming request
            call_next: Next middleware in chain

        Returns:
            Response with security headers
        """
        # Generate nonce for this request
        nonce = self.security_headers.generate_nonce()

        # Store nonce in request state
        request.state.csp_nonce = nonce

        # Process request
        response: Response = await call_next(request)
        # Add security headers
        headers = self.security_headers.get_security_headers(nonce)
        for header, value in headers.items():
            response.headers[header] = value

        # Add CORS headers for API endpoints
        if request.url.path.startswith("/api/"):
            cors_headers = self.security_headers.get_cors_headers(self.cors_origins)
            for header, value in cors_headers.items():
                response.headers[header] = value

        return response


def init_security_headers(
    app: FastAPI,
    environment: str = "production",
    cors_origins: Optional[List[str]] = None,
) -> None:
    """
    Initialize security headers middleware for FastAPI app.

    Args:
        app: FastAPI application instance
        environment: Deployment environment
        cors_origins: List of allowed CORS origins
    """
    app.add_middleware(
        SecurityHeadersMiddleware, environment=environment, cors_origins=cors_origins
    )
