"""Logging configuration for Haven Health Passport."""

import logging
import sys
from typing import Any, Dict, Optional

import structlog
from structlog.stdlib import BoundLogger, LoggerFactory

from src.config import get_settings


def setup_logging() -> None:
    """Configure structured logging for the application."""
    settings = get_settings()

    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, settings.log_level.upper()),
    )

    # Configure structlog
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.dict_tracebacks,
            render_processor(),
        ],
        context_class=dict,
        logger_factory=LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def render_processor() -> Any:
    """Choose renderer based on environment."""
    settings = get_settings()

    if settings.log_format == "json":
        return structlog.processors.JSONRenderer()
    else:
        return structlog.dev.ConsoleRenderer()


def get_logger(name: str) -> BoundLogger:
    """Get a configured logger instance."""
    bound_logger: BoundLogger = structlog.get_logger(name)
    return bound_logger


class RequestLogger:
    """Middleware for logging HTTP requests."""

    def __init__(self) -> None:
        """Initialize request logger."""
        self.logger = get_logger(__name__)

    async def log_request(self, request: Any) -> Dict[str, Any]:
        """Log incoming request details."""
        request_data = {
            "method": request.method,
            "path": request.url.path,
            "query_params": dict(request.query_params),
            "headers": dict(request.headers),
            "client_host": request.client.host if request.client else None,
        }

        self.logger.info("request_received", **request_data)
        return request_data

    async def log_response(
        self, request_data: Dict[str, Any], response: Any, duration: float
    ) -> None:
        """Log response details."""
        response_data = {
            **request_data,
            "status_code": response.status_code,
            "duration_ms": round(duration * 1000, 2),
        }

        if response.status_code >= 400:
            self.logger.error("request_failed", **response_data)
        else:
            self.logger.info("request_completed", **response_data)


class AuditLogger:
    """Logger for HIPAA-compliant audit trails."""

    def __init__(self) -> None:
        """Initialize audit logger."""
        self.logger = get_logger("audit")

    def log_access(
        self, user_id: str, resource_type: str, resource_id: str, action: str
    ) -> None:
        """Log resource access for audit trail."""
        self.logger.info(
            "resource_accessed",
            user_id=user_id,
            resource_type=resource_type,
            resource_id=resource_id,
            action=action,
            compliance="HIPAA",
        )

    def log_data_change(
        self,
        user_id: str,
        resource_type: str,
        resource_id: str,
        action: str,
        old_value: Any = None,
        new_value: Any = None,
    ) -> None:
        """Log data modifications for audit trail."""
        self.logger.info(
            "data_modified",
            user_id=user_id,
            resource_type=resource_type,
            resource_id=resource_id,
            action=action,
            old_value=old_value,
            new_value=new_value,
            compliance="HIPAA",
        )

    def log_authentication(
        self,
        user_id: str,
        action: str,
        success: bool,
        ip_address: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Log authentication events."""
        self.logger.info(
            "authentication_event",
            user_id=user_id,
            action=action,
            success=success,
            ip_address=ip_address,
            details=details or {},
            compliance="HIPAA",
        )


# Global logger instances
logger = get_logger(__name__)
audit_logger = AuditLogger()
request_logger = RequestLogger()
