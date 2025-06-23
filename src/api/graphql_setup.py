"""Strawberry GraphQL Configuration and Setup.

This module configures Strawberry GraphQL for Haven Health Passport,
including type system setup, extensions, and directives.

This module implements PHI encryption and access control to ensure HIPAA compliance.
"""

import logging
import time
import uuid
from datetime import date, datetime
from typing import Any, Dict, Optional
from uuid import UUID

try:
    import strawberry
    from strawberry.extensions import Extension
    from strawberry.fastapi import GraphQLRouter
    from strawberry.permission import BasePermission
    from strawberry.scalars import JSON
    from strawberry.types import Info
except ImportError as e:
    logger = logging.getLogger(__name__)
    logger.error("Failed to import strawberry modules: %s", str(e))
    raise

# Import GraphQL components
from src.api.graphql_audit import AuditExtension
from src.api.graphql_versioning import VersioningExtension
from src.api.mutations import Mutation
from src.api.queries import Query
from src.api.subscriptions import Subscription
from src.config import get_settings

# Import access control for HIPAA compliance
from src.security.access_control import AccessPermission
from src.security.audit import audit_phi_access
from src.security.encryption import EncryptionService

logger = logging.getLogger(__name__)


def check_user_permission(user: Any, permission: AccessPermission) -> bool:
    """Check if user has specified permission."""
    if not user or not hasattr(user, "role"):
        return False

    # Admin has all permissions
    if user.role == "admin":
        return True

    # Check specific permissions based on role
    if permission == AccessPermission.READ_PHI:
        return user.role in ["doctor", "nurse", "admin"]

    return False


# Custom Scalars
DateTime = strawberry.scalar(
    datetime,
    serialize=lambda v: v.isoformat() if v else None,
    parse_value=lambda v: datetime.fromisoformat(v) if v else None,
)

Date = strawberry.scalar(
    date,
    serialize=lambda v: v.isoformat() if v else None,
    parse_value=lambda v: datetime.strptime(v, "%Y-%m-%d").date() if v else None,
)

UUIDScalar = strawberry.scalar(
    uuid.UUID,
    serialize=lambda v: str(v) if v else None,
    parse_value=lambda v: uuid.UUID(v) if v else None,
)

# Custom Extensions for monitoring and logging


class LoggingExtension(Extension):
    """Extension for logging GraphQL operations."""

    def on_request_start(self) -> None:
        """Log request start."""
        request = self.execution_context.context["request"]
        logger.info("GraphQL request started: %s %s", request.method, request.url)

    def on_request_end(self) -> None:
        """Log request completion."""
        result = self.execution_context.result
        if result and result.errors:
            logger.error("GraphQL errors: %s", result.errors)

    def on_parse_start(self) -> None:
        """Log query parsing start."""
        logger.debug("Parsing GraphQL query")

    def on_validate_start(self) -> None:
        """Log validation start."""
        logger.debug("Validating GraphQL query")

    def on_execute_start(self) -> None:
        """Log execution start."""
        operation_name = self.execution_context.operation_name
        logger.info("Executing GraphQL operation: %s", operation_name)


class PerformanceExtension(Extension):
    """Extension for tracking GraphQL performance."""

    def __init__(self) -> None:
        self.start_time: Optional[float] = None
        self.parse_time: Optional[float] = None
        self.validate_time: Optional[float] = None

    def on_request_start(self) -> None:
        """Track request start time."""
        self.start_time = time.time()

    def on_parse_end(self) -> None:
        """Track parsing duration."""
        if self.start_time:
            self.parse_time = time.time() - self.start_time

    def on_validate_end(self) -> None:
        """Track validation duration."""
        if self.start_time and self.parse_time:
            self.validate_time = time.time() - self.start_time - self.parse_time

    def on_request_end(self) -> None:
        """Log performance metrics."""
        if self.start_time:
            total_time = time.time() - self.start_time
            logger.info(
                "GraphQL performance - Total: %.3fs, Parse: %.3fs, Validate: %.3fs",
                total_time,
                self.parse_time,
                self.validate_time,
            )


class PHIEncryptionExtension(Extension):
    """Extension for encrypting PHI in GraphQL responses."""

    def __init__(self) -> None:
        self.encryption_service = EncryptionService(
            kms_key_id="alias/haven-health-default"
        )

    @audit_phi_access("graphql_phi_access")
    def on_request_end(self) -> None:
        """Encrypt PHI in response data before sending."""
        result = self.execution_context.result

        if result and result.data:
            # Recursively encrypt sensitive fields
            self._encrypt_sensitive_fields(result.data)

    def _encrypt_sensitive_fields(self, data: Any, path: str = "") -> None:
        """Recursively encrypt sensitive fields in response data."""
        sensitive_fields = {
            "ssn",
            "socialSecurityNumber",
            "dateOfBirth",
            "dob",
            "address",
            "phoneNumber",
            "email",
            "medicalRecordNumber",
            "insuranceId",
            "patientName",
            "name",
        }

        if isinstance(data, dict):
            for key, value in data.items():
                if key in sensitive_fields and isinstance(value, str):
                    # Only encrypt if user doesn't have explicit PHI access
                    request = self.execution_context.context.get("request")
                    if request and not check_user_permission(
                        request.user, AccessPermission.READ_PHI
                    ):
                        data[key] = self.encryption_service.encrypt(
                            value.encode("utf-8")
                        )
                elif isinstance(value, (dict, list)):
                    self._encrypt_sensitive_fields(value, f"{path}.{key}")
        elif isinstance(data, list):
            for item in data:
                self._encrypt_sensitive_fields(item, f"{path}[]")


class HasPHIAccess(BasePermission):
    """Permission class to check PHI access."""

    message = "User does not have PHI access permission"

    def has_permission(self, source: Any, info: Info, **kwargs: Any) -> bool:
        """Check if user has PHI access permission."""
        _ = source  # Unused but required by base class
        _ = kwargs  # Unused but required by base class
        request = info.context["request"]
        if not hasattr(request, "user") or not request.user.is_authenticated:
            return False

        # Check for PHI access permission
        return check_user_permission(request.user, AccessPermission.READ_PHI)


# Custom Permissions
class IsAuthenticated(BasePermission):
    """Permission class to check if user is authenticated."""

    message = "User is not authenticated"

    def has_permission(self, source: Any, info: Info, **kwargs: Any) -> bool:
        """Check if request has valid authentication."""
        _ = source  # Unused but required by base class
        _ = kwargs  # Unused but required by base class
        request = info.context["request"]
        return hasattr(request, "user") and request.user.is_authenticated


class HasRole(BasePermission):
    """Permission class to check user roles."""

    message = "User does not have required role"

    def __init__(self, required_role: str):
        """Initialize with required role."""
        self.required_role = required_role

    def has_permission(self, source: Any, info: Info, **kwargs: Any) -> bool:
        """Check if user has required role."""
        _ = source  # Unused but required by base class
        _ = kwargs  # Unused but required by base class
        request = info.context["request"]
        if not hasattr(request, "user") or not request.user.is_authenticated:
            return False
        return self.required_role in request.user.roles


# Federation setup
@strawberry.federation.type(keys=["id"])
class FederatedUser:
    """Federated user type for cross-service queries."""

    id: UUID

    @strawberry.federation.field
    def resolve_reference(self, user_id: UUID) -> Optional["FederatedUser"]:
        """Resolve federated user reference."""
        _ = user_id  # To be implemented when federation is needed
        # Implementation would fetch user from database
        return None


# Schema configuration function
def create_graphql_schema() -> strawberry.Schema:
    """Create and configure the Strawberry GraphQL schema."""
    schema = strawberry.Schema(
        query=Query,
        mutation=Mutation,
        subscription=Subscription,
        extensions=[
            LoggingExtension,
            PerformanceExtension,
            PHIEncryptionExtension,  # Add PHI encryption
            VersioningExtension,  # Add versioning support
            AuditExtension,  # Add audit logging
        ],
        scalar_overrides={
            datetime: DateTime,
            uuid.UUID: UUID,
        },
    )

    return schema


# GraphQL Router factory
def create_graphql_router(schema: strawberry.Schema) -> GraphQLRouter:
    """Create FastAPI GraphQL router with configured schema."""
    try:
        settings = get_settings()

        return GraphQLRouter(
            schema,
            path="/graphql",
            graphiql=settings.debug,  # Enable GraphiQL in debug mode
            allow_queries_via_get=True,
            context_getter=get_context,
        )
    except (AttributeError, ImportError, ValueError) as e:
        logger.error("Failed to create GraphQL router: %s", str(e))
        # Return with default settings
        return GraphQLRouter(
            schema,
            path="/graphql",
            graphiql=False,
            allow_queries_via_get=True,
            context_getter=get_context,
        )


async def get_context(request: Any) -> Dict[str, Any]:
    """Get context for GraphQL execution."""
    return {
        "request": request,
        "user": getattr(request, "user", None),
        "db": getattr(request.app.state, "db", None),
        "redis": getattr(request.app.state, "redis", None),
    }


# Export main components
__all__ = [
    "create_graphql_schema",
    "create_graphql_router",
    "DateTime",
    "Date",
    "UUID",
    "JSON",
    "IsAuthenticated",
    "HasRole",
]
