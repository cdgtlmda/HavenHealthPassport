"""
Enhanced FHIR Authentication and Authorization Middleware.

This module provides FastAPI middleware that integrates both authentication and
authorization for FHIR endpoints using the comprehensive authorization handler.
"""

import hashlib
import json
import time
from typing import Any, Callable, Dict, List, Optional, cast

from fastapi import Request, status
from fastapi.security import HTTPBearer
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response

from src.healthcare.fhir_auth import FHIRAuthConfig, FHIRAuthenticator
from src.healthcare.fhir_authorization import (
    AuthorizationContext,
    AuthorizationRequest,
    FHIRRole,
    ResourcePermission,
    get_authorization_handler,
)
from src.healthcare.fhir_authorization_config import get_authorization_configurator
from src.utils.logging import get_logger

logger = get_logger(__name__)

# Security scheme for FastAPI
security = HTTPBearer(auto_error=False)


class EnhancedFHIRAuthMiddleware(BaseHTTPMiddleware):
    """Enhanced middleware for FHIR authentication and authorization."""

    def __init__(self, app: Any, auth_config: Optional[FHIRAuthConfig] = None) -> None:
        """Initialize the enhanced FHIR authentication middleware.

        Args:
            app: The FastAPI application instance
            auth_config: Optional FHIR authentication configuration
        """
        super().__init__(app)
        self.authenticator = FHIRAuthenticator(auth_config)
        self.authorization_handler = get_authorization_handler()
        self.auth_configurator = get_authorization_configurator()
        self._cache: Dict[str, Any] = {}  # Simple in-memory cache for auth decisions

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request with authentication and authorization.

        Args:
            request: Incoming request
            call_next: Next middleware/handler

        Returns:
            Response from next handler or error response
        """
        # Skip auth for non-FHIR endpoints
        if not request.url.path.startswith("/fhir"):
            response = await call_next(request)
            return cast(Response, response)

        # Skip auth for metadata endpoints
        if request.url.path in [
            "/fhir/metadata",
            "/fhir/.well-known/smart-configuration",
        ]:
            response = await call_next(request)
            return cast(Response, response)

        try:
            # Perform authentication
            auth_result = await self._authenticate(request)
            if not auth_result["authenticated"]:
                return self._unauthorized_response(
                    auth_result.get("message", "Unauthorized")
                )

            # Extract resource information from request
            resource_info = self._extract_resource_info(request)

            # Perform authorization
            auth_decision = await self._authorize(
                request, auth_result["claims"], resource_info
            )

            if not auth_decision["allowed"]:
                return self._forbidden_response(
                    auth_decision.get("message", "Forbidden")
                )

            # Add authorization context to request
            request.state.auth_claims = auth_result["claims"]
            request.state.auth_context = auth_decision.get("context")
            request.state.resource_filters = auth_decision.get("filters", [])

            # Process request
            response = cast(Response, await call_next(request))

            # Apply response filtering if needed
            if request.state.resource_filters and response.status_code == 200:
                response = await self._apply_response_filters(
                    response, request.state.resource_filters
                )

            return response

        except (ValueError, KeyError, AttributeError) as e:
            logger.error(f"Auth middleware error: {str(e)}", exc_info=True)
            return self._internal_error_response()

    async def _authenticate(self, request: Request) -> Dict[str, Any]:
        """Perform authentication.

        Args:
            request: Incoming request

        Returns:
            Authentication result with claims
        """
        # Check if authentication is enabled
        if not self.authenticator.is_enabled():
            return {
                "authenticated": True,
                "claims": {
                    "sub": "anonymous",
                    "scope": "*.read",
                    "roles": ["anonymous"],
                },
            }

        # Extract token
        auth_header = request.headers.get("Authorization")
        if not auth_header:
            # Check if anonymous read is allowed
            if (
                self.authenticator.config.allow_anonymous_read
                and request.method == "GET"
            ):
                return {
                    "authenticated": True,
                    "claims": {
                        "sub": "anonymous",
                        "scope": "*.read",
                        "roles": ["anonymous"],
                    },
                }
            return {"authenticated": False, "message": "Authorization header required"}

        # Validate token
        token_claims = self.authenticator.validate_token(auth_header)
        if not token_claims:
            return {"authenticated": False, "message": "Invalid or expired token"}

        # Extract roles from token
        roles = self._extract_roles_from_claims(token_claims)
        token_claims["roles"] = roles

        return {"authenticated": True, "claims": token_claims}

    def _extract_roles_from_claims(self, claims: Dict[str, Any]) -> List[str]:
        """Extract user roles from token claims.

        Args:
            claims: JWT claims

        Returns:
            List of role identifiers
        """
        roles = []

        # Check for explicit roles claim
        if "roles" in claims:
            roles.extend(claims["roles"])

        # Derive roles from scopes
        scopes = claims.get("scope", "").split()
        if "patient/*.read" in scopes or "patient/*.write" in scopes:
            roles.append(FHIRRole.PATIENT.value)
        if "system/*.*" in scopes:
            roles.append(FHIRRole.ADMIN.value)
        if "practitioner/*.read" in scopes or "practitioner/*.write" in scopes:
            roles.append(FHIRRole.PRACTITIONER.value)

        # Check for patient claim
        if claims.get("patient") and FHIRRole.PATIENT.value not in roles:
            roles.append(FHIRRole.PATIENT.value)

        return roles

    def _extract_resource_info(self, request: Request) -> Dict[str, Any]:
        """Extract FHIR resource information from request.

        Args:
            request: Incoming request

        Returns:
            Resource information dictionary
        """
        path_parts = request.url.path.strip("/").split("/")
        info: Dict[str, Any] = {
            "resource_type": None,
            "resource_id": None,
            "operation": None,
            "compartment": None,
        }

        # Parse FHIR URL patterns
        if len(path_parts) >= 2:
            info["resource_type"] = path_parts[1]

        if len(path_parts) >= 3:
            # Check for special operations
            if path_parts[2].startswith("$"):
                info["operation"] = path_parts[2]
            else:
                info["resource_id"] = path_parts[2]

        if len(path_parts) >= 4:
            if path_parts[3].startswith("$"):
                info["operation"] = path_parts[3]

        # Determine action from HTTP method
        if request.method == "GET":
            info["action"] = ResourcePermission.READ
        elif request.method == "POST":
            info["action"] = ResourcePermission.CREATE
        elif request.method == "PUT":
            info["action"] = ResourcePermission.UPDATE
        elif request.method == "PATCH":
            info["action"] = ResourcePermission.PATCH
        elif request.method == "DELETE":
            info["action"] = ResourcePermission.DELETE
        else:
            info["action"] = ResourcePermission.READ

        return info

    async def _authorize(
        self, request: Request, claims: Dict[str, Any], resource_info: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Perform authorization check.

        Args:
            request: Incoming request
            claims: Authenticated user claims
            resource_info: Extracted resource information

        Returns:
            Authorization decision
        """
        # Build authorization context
        auth_context = AuthorizationContext(
            user_id=claims.get("sub", "unknown"),
            roles=[FHIRRole(role) for role in claims.get("roles", [])],
            organization_id=claims.get("organization"),
            session_id=request.headers.get("X-Session-ID"),
            ip_address=request.client.host if request.client else None,
            emergency_access=claims.get("emergency_access", False),
            attributes=claims,
        )

        # Get resource data for condition evaluation
        resource_data = None
        if request.method in ["PUT", "POST", "PATCH"]:
            try:
                body = await request.body()
                resource_data = json.loads(body) if body else None
            except (json.JSONDecodeError, ValueError):
                pass

        # Build authorization request
        auth_request = AuthorizationRequest(
            context=auth_context,
            resource_type=resource_info["resource_type"],
            action=resource_info["action"],
            resource_id=resource_info["resource_id"],
            resource_data=resource_data,
            compartment=resource_info["compartment"],
        )

        # Check cache if enabled
        cache_key = self._get_cache_key(auth_request)
        if self.auth_configurator.auth_config.cache_authorization_decisions:
            cached = self._cache.get(cache_key)
            if cached and cached["expires"] > time.time():
                return cached["decision"]  # type: ignore[no-any-return]

        # Perform authorization check
        decision = self.authorization_handler.check_authorization(auth_request)

        # Cache decision if enabled
        if self.auth_configurator.auth_config.cache_authorization_decisions:
            self._cache[cache_key] = {
                "decision": {
                    "allowed": decision.allowed,
                    "message": decision.reasons[0] if decision.reasons else None,
                    "context": auth_context,
                    "filters": [],
                },
                "expires": time.time()
                + self.auth_configurator.auth_config.cache_ttl_seconds,
            }

        # Get resource filters if allowed
        filters = []
        if decision.allowed and resource_info["action"] == ResourcePermission.READ:
            filters = self.authorization_handler.get_resource_filters(
                auth_context, resource_info["resource_type"]
            )

        return {
            "allowed": decision.allowed,
            "message": decision.reasons[0] if decision.reasons else None,
            "context": auth_context,
            "filters": filters,
        }

    def _get_cache_key(self, auth_request: AuthorizationRequest) -> str:
        """Generate cache key for authorization request."""
        key_parts = [
            auth_request.context.user_id,
            auth_request.resource_type,
            auth_request.action.value,
            auth_request.resource_id or "none",
            str(sorted(auth_request.context.roles)),
        ]
        key_string = "|".join(key_parts)
        return hashlib.md5(key_string.encode(), usedforsecurity=False).hexdigest()

    async def _apply_response_filters(
        self, response: Response, filters: List[Any]
    ) -> Response:
        """Apply authorization filters to response data.

        Args:
            response: Original response
            filters: List of filters to apply

        Returns:
            Filtered response
        """
        # For now, just return the original response
        # In a real implementation, this would filter the response data
        # filters parameter will be used in future implementation
        _ = filters  # Acknowledge unused parameter
        return response

    def _unauthorized_response(self, message: str = "Unauthorized") -> Response:
        """Create unauthorized response."""
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={
                "resourceType": "OperationOutcome",
                "issue": [
                    {
                        "severity": "error",
                        "code": "security",
                        "details": {"text": message},
                    }
                ],
            },
            headers={"WWW-Authenticate": "Bearer"},
        )

    def _forbidden_response(self, message: str = "Forbidden") -> Response:
        """Create forbidden response."""
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={
                "resourceType": "OperationOutcome",
                "issue": [
                    {
                        "severity": "error",
                        "code": "forbidden",
                        "details": {"text": message},
                    }
                ],
            },
        )

    def _internal_error_response(self) -> Response:
        """Create internal error response."""
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "resourceType": "OperationOutcome",
                "issue": [
                    {
                        "severity": "error",
                        "code": "exception",
                        "details": {"text": "Internal server error"},
                    }
                ],
            },
        )
