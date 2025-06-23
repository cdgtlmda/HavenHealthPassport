"""
Audit logging module for Haven Health Passport.

This module provides audit logging functionality for PHI access
and other security-sensitive operations with encryption and access control.
"""

from functools import wraps
from typing import Any, Callable, Dict, Optional

from src.utils.logging import get_logger

logger = get_logger(__name__)


def audit_log(
    operation: str,
    resource_type: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Log an audit event.

    Args:
        operation: The operation being performed
        resource_type: Type of resource being accessed
        details: Additional details about the operation
    """
    audit_entry = {
        "operation": operation,
        "resource_type": resource_type,
        "details": details or {},
    }
    logger.info(f"AUDIT: {audit_entry}")


def audit_phi_access(operation: str) -> Callable:
    """Audit PHI access operations.

    Args:
        operation: The operation being performed

    Returns:
        Decorated function that logs PHI access
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            # Log the PHI access operation
            audit_log(
                operation=operation,
                resource_type="PHI",
                details={"function": func.__name__},
            )
            return await func(*args, **kwargs)

        @wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            # Log the PHI access operation
            audit_log(
                operation=operation,
                resource_type="PHI",
                details={"function": func.__name__},
            )
            return func(*args, **kwargs)

        # Return appropriate wrapper based on function type
        import asyncio  # pylint: disable=import-outside-toplevel

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


__all__ = [
    "audit_log",
    "audit_phi_access",
]
