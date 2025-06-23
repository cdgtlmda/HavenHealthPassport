"""
FHIR Authentication Middleware.

This module provides FastAPI middleware for authenticating requests to FHIR endpoints.
"""

from typing import Any, Callable, Optional, cast

from fastapi import Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from src.healthcare.fhir_auth import FHIRAuthConfig, FHIRAuthenticator
from src.utils.logging import get_logger

logger = get_logger(__name__)

# Security scheme for FastAPI
security = HTTPBearer(auto_error=False)


class FHIRAuthMiddleware(BaseHTTPMiddleware):
    """Middleware for FHIR authentication."""

    def __init__(self, app: Any, config: Optional[FHIRAuthConfig] = None) -> None:
        """Initialize FHIR authentication middleware.

        Args:
            app: The FastAPI application instance.
            config: Optional FHIR authentication configuration.
        """
        super().__init__(app)
        self.authenticator = FHIRAuthenticator(config)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request with authentication.

        Args:
            request: Incoming request
            call_next: Next middleware/handler

        Returns:
            Response from next handler
        """
        # Skip authentication if disabled
        if not self.authenticator.is_enabled():
            response = await call_next(request)
            return cast(Response, response)

        # Check if this is a FHIR endpoint
        if not request.url.path.startswith("/fhir"):
            response = await call_next(request)
            return cast(Response, response)

        # Extract token from Authorization header
        auth_header = request.headers.get("Authorization")
        if not auth_header:
            if (
                self.authenticator.config.allow_anonymous_read
                and request.method == "GET"
            ):
                request.state.auth_claims = {"sub": "anonymous", "scope": "*.read"}
                response = await call_next(request)
                return cast(Response, response)
            else:
                return Response(
                    content="Authorization required",
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    headers={"WWW-Authenticate": "Bearer"},
                )
        # Validate token
        token_claims = self.authenticator.validate_token(auth_header)
        if not token_claims:
            return Response(
                content="Invalid or expired token",
                status_code=status.HTTP_401_UNAUTHORIZED,
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Extract resource type and operation from path
        path_parts = request.url.path.split("/")
        resource_type = None
        resource_id = None
        operation = "read"  # Default operation

        # Parse FHIR path: /fhir/{ResourceType}/{id}
        if len(path_parts) >= 3:
            resource_type = path_parts[2]
            if len(path_parts) >= 4:
                resource_id = path_parts[3]

        # Determine operation based on HTTP method
        if request.method == "GET":
            operation = "read"
        elif request.method in ["POST", "PUT", "PATCH"]:
            operation = "write"
        elif request.method == "DELETE":
            operation = "delete"

        # Check resource access
        if resource_type:
            has_access = self.authenticator.check_resource_access(
                token_claims, resource_type, operation, resource_id
            )

            if not has_access:
                return Response(
                    content=f"Insufficient permissions for {operation} on {resource_type}",
                    status_code=status.HTTP_403_FORBIDDEN,
                )

        # Store auth claims in request state for downstream use
        request.state.auth_claims = token_claims

        # Continue to next handler
        response = await call_next(request)
        return cast(Response, response)


async def get_current_fhir_user(
    credentials: Optional[HTTPAuthorizationCredentials] = None,
) -> Optional[dict]:
    """Dependency for getting current authenticated user in FHIR context.

    Args:
        credentials: HTTP Bearer credentials

    Returns:
        User claims from token or None
    """
    if not credentials:
        return None

    authenticator = FHIRAuthenticator()
    return authenticator.validate_token(credentials.credentials)
