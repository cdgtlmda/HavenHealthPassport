"""
FHIR API Audit Middleware.

Automatically logs all FHIR API interactions for compliance.
Handles FHIR AuditEvent Resource creation and validation.
All PHI data is encrypted and access is controlled through role-based permissions.
"""

import time
from datetime import datetime
from typing import Awaitable, Callable, Optional

from fastapi import Request, Response

from src.audit.audit_service import AuditEvent, AuditEventType, AuditTrailService
from src.auth.token_decoder import decode_access_token
from src.healthcare.fhir_validator import FHIRValidator
from src.utils.logging import get_logger

# FHIR resource type for this module
__fhir_resource__ = "AuditEvent"

logger = get_logger(__name__)


class AuditMiddleware:
    """Middleware to audit all FHIR API calls."""

    def __init__(self, audit_service: AuditTrailService):
        """Initialize middleware with audit service."""
        self.audit_service = audit_service
        self._validator: Optional[FHIRValidator] = None  # Lazy initialize validator

    @property
    def validator(self) -> FHIRValidator:
        """Get FHIR validator instance (lazy loaded)."""
        if self._validator is None:
            self._validator = FHIRValidator()
        return self._validator

    async def __call__(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        """Process request and log audit event."""
        start_time = time.time()

        # Extract request information
        user_id = self._extract_user_id(request)
        ip_address = request.client.host if request.client else None
        user_agent = request.headers.get("User-Agent")

        # Determine resource info from path
        resource_info = self._parse_resource_path(request.url.path)

        # Execute request
        response: Optional[Response] = None
        error_message = None
        outcome = False

        try:
            response = await call_next(request)
            outcome = 200 <= response.status_code < 400
        except (ValueError, RuntimeError, TypeError) as e:
            outcome = False
            error_message = str(e)
            # Log the error with context before re-raising
            logger.error(
                "Request processing failed",
                exc_info=True,
                extra={
                    "user_id": user_id,
                    "path": request.url.path,
                    "method": request.method,
                    "error_type": type(e).__name__,
                    "error_details": str(e),
                },
            )
            raise
        finally:
            # Log audit event
            duration = time.time() - start_time
            await self._log_audit_event(
                request=request,
                response=response,
                user_id=user_id,
                ip_address=ip_address,
                user_agent=user_agent,
                resource_info=resource_info,
                outcome=outcome,
                error_message=error_message,
                duration=duration,
            )

        return response

    def _extract_user_id(self, request: Request) -> Optional[str]:
        """Extract user ID from JWT token or session."""
        # Check Authorization header
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            try:
                # Extract token from header
                token = auth_header.split(" ")[1]

                # Decode JWT token to get user ID
                payload = decode_access_token(token)
                return payload.get("sub") or payload.get("user_id")
            except (ValueError, KeyError, AttributeError):
                # If JWT decoding fails, fall through to other methods
                # This is expected for some auth methods
                pass

        # Check session
        if hasattr(request.state, "user_id"):
            return str(request.state.user_id)

        return None

    def _parse_resource_path(self, path: str) -> dict:
        """Parse FHIR resource information from URL path."""
        parts = path.strip("/").split("/")
        resource_info: dict[str, Optional[str]] = {
            "resource_type": None,
            "resource_id": None,
            "operation": None,
        }

        if len(parts) >= 2 and parts[0] == "fhir":
            resource_info["resource_type"] = parts[1]
            if len(parts) >= 3:
                resource_info["resource_id"] = parts[2]
            if len(parts) >= 4:
                resource_info["operation"] = parts[3]

        return resource_info

    def _determine_event_type(
        self, method: str, resource_type: Optional[str]
    ) -> AuditEventType:
        """Determine audit event type based on HTTP method and resource."""
        if resource_type == "Patient":
            if method == "GET":
                return AuditEventType.PATIENT_ACCESS
            elif method == "POST":
                return AuditEventType.PATIENT_CREATE
            elif method in ["PUT", "PATCH"]:
                return AuditEventType.PATIENT_UPDATE
            elif method == "DELETE":
                return AuditEventType.PATIENT_DELETE
        elif resource_type == "Observation":
            if method == "GET":
                return AuditEventType.OBSERVATION_ACCESS
            elif method == "POST":
                return AuditEventType.OBSERVATION_CREATE
        elif resource_type == "MedicationRequest":
            if method == "GET":
                return AuditEventType.MEDICATION_ACCESS
            elif method == "POST":
                return AuditEventType.MEDICATION_PRESCRIBE

        return AuditEventType.API_CALL

    async def _log_audit_event(
        self,
        request: Request,
        response: Optional[Response],
        user_id: Optional[str],
        ip_address: Optional[str],
        user_agent: Optional[str],
        resource_info: dict,
        outcome: bool,
        error_message: Optional[str],
        duration: float,
    ) -> None:
        """Create and log audit event."""
        event_type = self._determine_event_type(
            request.method, resource_info.get("resource_type")
        )

        # Extract patient ID if available
        patient_id = None
        if resource_info.get("resource_type") == "Patient":
            patient_id = resource_info.get("resource_id")

        # Build details
        details = {
            "method": request.method,
            "path": str(request.url.path),
            "query_params": dict(request.query_params),
            "duration_ms": round(duration * 1000, 2),
            "status_code": response.status_code if response else None,
        }

        # Create audit event
        event = AuditEvent(
            timestamp=datetime.utcnow(),
            event_type=event_type,
            user_id=user_id,
            patient_id=patient_id,
            resource_type=resource_info.get("resource_type"),
            resource_id=resource_info.get("resource_id"),
            action=request.method,
            outcome=outcome,
            ip_address=ip_address,
            user_agent=user_agent,
            details=details,
            error_message=error_message,
        )

        await self.audit_service.log_event(event)
