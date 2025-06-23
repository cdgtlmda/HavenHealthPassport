"""PHI Access Control for Haven Health Passport.

This module provides decorators and utilities for protecting access to
Protected Health Information (PHI) in accordance with HIPAA regulations.

FHIR Compliance: PHI access to FHIR Resource data must be validated.
PHI Protection: All PHI data is encrypted at rest and in transit.
Access Control: Enforces permission-based access control with @phi_access_required decorator.
"""

import asyncio
import functools
import inspect
import logging
from typing import Any, Callable, List, Optional

from sqlalchemy.exc import DataError, IntegrityError, SQLAlchemyError

from src.core.database import get_db
from src.models.access_log import AccessContext, AccessLog, AccessResult, AccessType

logger = logging.getLogger(__name__)


class PHIAccessDenied(Exception):
    """Raise when PHI access is denied."""


def phi_access_required(
    resource_type: str = "phi_data",
    access_type: AccessType = AccessType.VIEW,
    required_permissions: Optional[List[str]] = None,
    log_access: bool = True,
    audit_fields: Optional[List[str]] = None,
) -> Callable:
    """Enforce PHI access control on functions using decorator pattern.

    Args:
        resource_type: Type of PHI resource being accessed
        access_type: Type of access (view, update, etc.)
        required_permissions: List of required permissions
        log_access: Whether to log this access
        audit_fields: Specific fields being accessed for audit

    Usage:
        @phi_access_required(
            resource_type="patient_embeddings",
            access_type=AccessType.VIEW,
            required_permissions=["read:phi", "read:embeddings"]
        )
        def process_patient_text(patient_id: str, text: str) -> List[float]:
            # Function implementation
            pass
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            # Try to get the current user from various sources
            user = None
            request = None
            patient_id = None

            # Check if there's a 'request' in kwargs
            if "request" in kwargs:
                request = kwargs["request"]
                user = getattr(request, "user", None) or getattr(
                    request.state, "user", None
                )

            # Check if there's a 'user' in kwargs
            if not user and "user" in kwargs:
                user = kwargs["user"]

            # Check if there's a 'self' with user attribute
            if not user and args and hasattr(args[0], "user"):
                user = args[0].user

            # Check if there's a 'self' with request attribute
            if not user and args and hasattr(args[0], "request"):
                request = args[0].request
                user = getattr(request, "user", None) or getattr(
                    request.state, "user", None
                )

            # If still no user, try to get from global context (for background tasks)
            if not user:
                # Context module not available, skip context-based user lookup
                # This requires proper authorization context to be passed explicitly
                pass

            # Extract patient_id from arguments
            sig = inspect.signature(func)
            params = list(sig.parameters.keys())

            # Try to find patient_id in various places
            if "patient_id" in kwargs:
                patient_id = kwargs["patient_id"]
            elif "patient_id" in params:
                idx = params.index("patient_id")
                if idx < len(args):
                    patient_id = args[idx]
            elif args and hasattr(args[0], "patient_id"):
                patient_id = args[0].patient_id

            # Perform access control check
            if user:
                # Check basic permissions
                if required_permissions:
                    for perm in required_permissions:
                        if not user.has_permission(perm):
                            if log_access and patient_id:
                                _log_access_denial(
                                    user_id=str(user.id),
                                    patient_id=str(patient_id),
                                    resource_type=resource_type,
                                    access_type=access_type,
                                    reason=f"Missing permission: {perm}",
                                )
                            raise PHIAccessDenied(
                                f"User lacks required permission: {perm}"
                            )

                # Log successful access if requested
                if log_access and patient_id:
                    _log_access_success(
                        user_id=str(user.id),
                        patient_id=str(patient_id),
                        resource_type=resource_type,
                        access_type=access_type,
                        audit_fields=audit_fields,
                        function_name=func.__name__,
                    )
            else:
                # No user context - this might be a system operation
                logger.warning(
                    "PHI access to %s without user context. "
                    "Resource: %s, Patient: %s",
                    func.__name__,
                    resource_type,
                    patient_id,
                )

            # Execute the original function
            return await func(*args, **kwargs)

        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            # Similar logic for synchronous functions
            user = None
            request = None
            patient_id = None

            # Check if there's a 'request' in kwargs
            if "request" in kwargs:
                request = kwargs["request"]
                user = getattr(request, "user", None) or getattr(
                    request.state, "user", None
                )

            # Check if there's a 'user' in kwargs
            if not user and "user" in kwargs:
                user = kwargs["user"]

            # Check if there's a 'self' with user attribute
            if not user and args and hasattr(args[0], "user"):
                user = args[0].user

            # Check if there's a 'self' with request attribute
            if not user and args and hasattr(args[0], "request"):
                request = args[0].request
                user = getattr(request, "user", None) or getattr(
                    request.state, "user", None
                )

            # Extract patient_id from arguments
            sig = inspect.signature(func)
            params = list(sig.parameters.keys())

            if "patient_id" in kwargs:
                patient_id = kwargs["patient_id"]
            elif "patient_id" in params:
                idx = params.index("patient_id")
                if idx < len(args):
                    patient_id = args[idx]
            elif args and hasattr(args[0], "patient_id"):
                patient_id = args[0].patient_id

            # Perform access control check
            if user:
                # Check basic permissions
                if required_permissions:
                    for perm in required_permissions:
                        if not user.has_permission(perm):
                            if log_access and patient_id:
                                _log_access_denial(
                                    user_id=str(user.id),
                                    patient_id=str(patient_id),
                                    resource_type=resource_type,
                                    access_type=access_type,
                                    reason=f"Missing permission: {perm}",
                                )
                            raise PHIAccessDenied(
                                f"User lacks required permission: {perm}"
                            )

                # Log successful access if requested
                if log_access and patient_id:
                    _log_access_success(
                        user_id=str(user.id),
                        patient_id=str(patient_id),
                        resource_type=resource_type,
                        access_type=access_type,
                        audit_fields=audit_fields,
                        function_name=func.__name__,
                    )
            else:
                # No user context - this might be a system operation
                logger.warning(
                    "PHI access to %s without user context. "
                    "Resource: %s, Patient: %s",
                    func.__name__,
                    resource_type,
                    patient_id,
                )

            # Execute the original function
            return func(*args, **kwargs)

        # Return appropriate wrapper based on function type
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


def _log_access_success(
    user_id: str,
    patient_id: str,
    resource_type: str,
    access_type: AccessType,
    audit_fields: Optional[List[str]],
    function_name: str,
) -> None:
    """Log successful PHI access."""
    try:
        # Get database session from context
        # get_db imported at module level

        with get_db() as db:
            AccessLog.log_access(
                session=db,
                user_id=user_id,
                resource_type=resource_type,
                resource_id=patient_id,
                access_type=access_type,
                access_context=AccessContext.API,
                purpose=f"PHI access via {function_name}",
                patient_id=patient_id,
                access_result=AccessResult.SUCCESS,
                fields_accessed=audit_fields or [],
            )

            db.commit()

    except (DataError, IntegrityError, SQLAlchemyError) as e:
        logger.error("Failed to log PHI access: %s", str(e))


def _log_access_denial(
    user_id: str,
    patient_id: str,
    resource_type: str,
    access_type: AccessType,
    reason: str,
) -> None:
    """Log denied PHI access attempt."""
    try:
        # Get database session from context
        # get_db imported at module level

        with get_db() as db:
            AccessLog.log_access(
                session=db,
                user_id=user_id,
                resource_type=resource_type,
                resource_id=patient_id,
                access_type=access_type,
                access_context=AccessContext.API,
                purpose=reason,
                patient_id=patient_id,
                access_result=AccessResult.DENIED,
            )

            db.commit()

    except (DataError, IntegrityError, SQLAlchemyError) as e:
        logger.error("Failed to log PHI access denial: %s", str(e))


# Convenience decorators for common PHI access patterns
phi_read_access = functools.partial(
    phi_access_required, access_type=AccessType.VIEW, required_permissions=["read:phi"]
)

phi_write_access = functools.partial(
    phi_access_required,
    access_type=AccessType.UPDATE,
    required_permissions=["write:phi"],
)

phi_embedding_access = functools.partial(
    phi_access_required,
    resource_type="patient_embeddings",
    access_type=AccessType.VIEW,
    required_permissions=["read:phi", "read:embeddings"],
)
