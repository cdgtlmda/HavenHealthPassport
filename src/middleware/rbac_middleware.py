"""RBAC Middleware for API Request Authorization.

This middleware integrates with the RBAC system to enforce
permissions on all API requests.
"""

from functools import wraps
from typing import Any, Callable, Dict, List, Optional, Union

from fastapi import HTTPException, Request, status
from fastapi.security import HTTPBearer
from jose import ExpiredSignatureError, JWTError
from jose.exceptions import JWTError as InvalidTokenError
from requests import HTTPError

from src.auth.permissions import Permission, Role
from src.auth.rbac import (
    AuthorizationContext,
    RoleAssignment,
    rbac_manager,
)
from src.auth.token_decoder import decode_access_token
from src.utils.logging import get_logger

logger = get_logger(__name__)

security = HTTPBearer()


class RBACMiddleware:
    """Middleware for enforcing RBAC on API requests."""

    def __init__(self) -> None:
        """Initialize RBAC middleware."""
        self.rbac_manager = rbac_manager

    async def __call__(self, request: Request, call_next: Any) -> Any:
        """Process request through RBAC checks."""
        # Skip auth for public endpoints
        if self._is_public_endpoint(request.url.path):
            response = await call_next(request)
            return response

        # Extract authorization header
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            logger.warning(
                f"Missing or invalid authorization header for {request.url.path}"
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing or invalid authorization header",
            )

        try:
            # Decode JWT token
            token = auth_header.split(" ")[1]
            payload = decode_access_token(token)

            # Create authorization context
            context = await self._create_auth_context(payload, request)

            # Store context in request state for use in endpoints
            request.state.auth_context = context

            # Process request
            response = await call_next(request)
            return response

        except HTTPException as http_exc:
            # Re-raise HTTP exceptions without modification
            raise http_exc
        except (
            ConnectionError,
            ExpiredSignatureError,
            HTTPError,
            InvalidTokenError,
            JWTError,
            TimeoutError,
            TypeError,
            ValueError,
        ) as e:
            logger.error(
                f"RBAC middleware error: {str(e)}", extra={"path": request.url.path}
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Authorization processing failed",
            ) from e

    async def _create_auth_context(
        self, jwt_payload: Dict[str, Any], request: Request
    ) -> AuthorizationContext:
        """Create authorization context from JWT payload and request."""
        user_id = jwt_payload.get("sub")
        if not user_id:
            raise ValueError("Missing user ID in JWT payload")
        roles_data = jwt_payload.get("roles", [])

        # Convert role strings to RoleAssignment objects
        role_assignments = []
        for role_str in roles_data:
            if isinstance(role_str, str):
                role = Role(role_str)
                assignment = RoleAssignment(
                    user_id=user_id, role=role, assigned_by="system"
                )
                role_assignments.append(assignment)

        # Build context attributes
        attributes = {
            "ip_address": request.client.host if request.client else None,
            "user_agent": request.headers.get("User-Agent"),
            "request_path": request.url.path,
            "request_method": request.method,
            "organization_id": jwt_payload.get("organization_id"),
            "department": jwt_payload.get("department"),
        }

        # Create context
        context = AuthorizationContext(
            user_id=user_id,
            roles=role_assignments,
            attributes=attributes,
            ip_address=request.client.host if request.client else None,
            session_id=jwt_payload.get("session_id"),
        )

        return context

    def _is_public_endpoint(self, path: str) -> bool:
        """Check if endpoint is public and doesn't require authentication."""
        public_paths = [
            "/",
            "/health",
            "/docs",
            "/openapi.json",
            "/auth/login",
            "/auth/register",
            "/auth/refresh",
            "/auth/forgot-password",
        ]

        return any(path.startswith(p) for p in public_paths)


def require_permission(
    permission: Union[Permission, List[Permission]],
    resource_type: Optional[str] = None,
    resource_id_param: Optional[str] = None,
) -> Callable:
    """Require specific permissions for an endpoint.

    Args:
        permission: Required permission(s)
        resource_type: Type of resource being accessed
        resource_id_param: Name of the parameter containing resource ID
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Get request object
            request = None
            for arg in args:
                if isinstance(arg, Request):
                    request = arg
                    break

            if not request:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Request object not found",
                )

            # Get auth context
            context = getattr(request.state, "auth_context", None)
            if not context:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required",
                )

            # Get resource ID if specified
            resource_id = None
            if resource_id_param:
                resource_id = kwargs.get(resource_id_param)

            # Check permissions
            permissions_to_check = (
                [permission] if isinstance(permission, Permission) else permission
            )

            has_permission = False
            for perm in permissions_to_check:
                if rbac_manager.check_permission(
                    context, perm, resource_type, resource_id
                ):
                    has_permission = True
                    break

            if not has_permission:
                logger.warning(
                    f"Permission denied for user {context.user_id}",
                    extra={
                        "permissions": [p.value for p in permissions_to_check],
                        "resource_type": resource_type,
                        "resource_id": resource_id,
                    },
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Insufficient permissions",
                )

            # Call the original function
            return await func(*args, **kwargs)

        return wrapper

    return decorator


def require_role(role: Union[Role, List[Role]]) -> Callable:
    """Require specific role(s) for an endpoint.

    Args:
        role: Required role(s)
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Get request object
            request = None
            for arg in args:
                if isinstance(arg, Request):
                    request = arg
                    break

            if not request:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Request object not found",
                )

            # Get auth context
            context = getattr(request.state, "auth_context", None)
            if not context:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required",
                )

            # Check roles
            roles_to_check = [role] if isinstance(role, Role) else role
            active_roles = context.get_active_roles()

            has_role = any(r in active_roles for r in roles_to_check)

            if not has_role:
                logger.warning(
                    f"Role requirement not met for user {context.user_id}",
                    extra={
                        "required_roles": [r.value for r in roles_to_check],
                        "user_roles": [r.value for r in active_roles],
                    },
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Insufficient role privileges",
                )

            # Call the original function
            return await func(*args, **kwargs)

        return wrapper

    return decorator


def emergency_access() -> Callable:
    """Enable emergency access override for an endpoint."""

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Get request object
            request = None
            for arg in args:
                if isinstance(arg, Request):
                    request = arg
                    break

            if request:
                # Get auth context
                context = getattr(request.state, "auth_context", None)
                if context:
                    # Check for emergency header
                    emergency_header = request.headers.get("X-Emergency-Access")
                    if emergency_header == "true":
                        # Verify user has emergency responder role
                        if Role.EMERGENCY_RESPONDER in context.get_active_roles():
                            context.emergency_override = True
                            logger.warning(
                                f"Emergency access activated by user {context.user_id}",
                                extra={
                                    "path": request.url.path,
                                    "ip_address": context.ip_address,
                                },
                            )

            # Call the original function
            return await func(*args, **kwargs)

        return wrapper

    return decorator
