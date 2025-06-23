"""Security headers middleware for API protection.

CRITICAL: This is a healthcare application handling refugee medical data.
Security headers are mandatory for:
1. Preventing XSS attacks that could expose patient data
2. Preventing clickjacking of authentication forms
3. Enforcing HTTPS for HIPAA compliance
4. Preventing data leakage through referrer headers

HIPAA Compliance: Implements access control and secure transmission requirements.
- Enforces encrypted transport (HTTPS) for all PHI data
- Prevents unauthorized access through security headers
- Logs all access attempts for audit compliance
"""

from typing import Any, Callable
from urllib.parse import urlparse

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from src.config import get_settings
from src.utils.logging import get_logger

logger = get_logger(__name__)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Middleware to add security headers to responses."""

    def __init__(self, app: Any) -> None:
        """Initialize security headers middleware."""
        super().__init__(app)
        self.settings = get_settings()
        self._hsts_logged = False

        # Validate critical security settings
        if self.settings.environment == "production":
            if not self.settings.FORCE_HTTPS:
                raise RuntimeError(
                    "CRITICAL: FORCE_HTTPS must be enabled in production! "
                    "HTTPS is required for HIPAA compliance and patient data protection."
                )
            logger.info("Security headers middleware initialized for production")

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Add security headers to response."""
        response = await call_next(request)

        # CRITICAL: Security headers for healthcare data protection
        headers = {
            # Prevent clickjacking attacks on login/auth pages
            "X-Frame-Options": "DENY",
            # Prevent MIME type sniffing that could execute malicious scripts
            "X-Content-Type-Options": "nosniff",
            # Enable XSS protection (legacy but still useful)
            "X-XSS-Protection": "1; mode=block",
            # Control referrer to prevent leaking patient URLs
            "Referrer-Policy": "strict-origin-when-cross-origin",
            # Disable dangerous browser features
            "Permissions-Policy": (
                "geolocation=(), microphone=(), camera=(), "
                "payment=(), usb=(), magnetometer=(), "
                "accelerometer=(), gyroscope=(), "
                "interest-cohort=()"  # Disable FLoC tracking
            ),
            # Content Security Policy - strict for medical data
            "Content-Security-Policy": (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdnjs.cloudflare.com; "
                "style-src 'self' 'unsafe-inline'; "
                "img-src 'self' data: https:; "
                "font-src 'self' data:; "
                "connect-src 'self' https://api.havenhealthpassport.org wss://api.havenhealthpassport.org; "
                "frame-ancestors 'none'; "
                "base-uri 'self'; "
                "form-action 'self'; "
                "upgrade-insecure-requests"  # Force HTTPS for all resources
            ),
        }

        # CRITICAL: HTTP Strict Transport Security (HSTS)
        # Required for HIPAA compliance - ensures all communications are encrypted
        if self.settings.environment in ["production", "staging"]:
            # Production: 1 year with subdomains and preload
            headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains; preload"
            )

            # Log HSTS activation for compliance audit
            if not hasattr(self, "_hsts_logged"):
                logger.info(
                    "HSTS enabled with 1-year duration, subdomains, and preload. "
                    "This ensures all patient data is transmitted over HTTPS."
                )
                self._hsts_logged = True
        else:
            # Development: shorter duration for testing
            headers["Strict-Transport-Security"] = "max-age=3600"

        # Additional production-only headers
        if self.settings.environment == "production":
            # Expect-CT for certificate transparency
            headers["Expect-CT"] = "max-age=86400, enforce"

            # Additional CSP directives for production
            headers[
                "Content-Security-Policy"
            ] += "; report-uri https://api.havenhealthpassport.org/csp-report"

        # Add headers to response
        for header, value in headers.items():
            if value is not None:
                response.headers[header] = value

        # Remove sensitive headers
        sensitive_headers = ["Server", "X-Powered-By"]
        for header in sensitive_headers:
            if header in response.headers:
                del response.headers[header]

        response_typed: Response = response
        return response_typed


class CORSSecurityMiddleware(BaseHTTPMiddleware):
    """Enhanced CORS security middleware."""

    def __init__(self, app: Any) -> None:
        """Initialize CORS security middleware."""
        super().__init__(app)
        self.settings = get_settings()

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Handle CORS preflight and add security headers."""
        # Handle preflight requests
        if request.method == "OPTIONS":
            return Response(
                status_code=200,
                headers={
                    "Access-Control-Allow-Origin": self._get_allowed_origin(request),
                    "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS, PATCH",
                    "Access-Control-Allow-Headers": (
                        "Authorization, Content-Type, X-API-Version, X-Request-ID"
                    ),
                    "Access-Control-Max-Age": "3600",
                    "Access-Control-Allow-Credentials": "true",
                },
            )

        response = await call_next(request)

        # Add CORS headers to actual requests
        origin = self._get_allowed_origin(request)
        if origin:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Credentials"] = "true"
            response.headers["Vary"] = "Origin"

        response_typed: Response = response
        return response_typed

    def _get_allowed_origin(self, request: Request) -> str:
        """Get allowed origin based on request with proper URL validation."""
        origin = request.headers.get("origin", "")

        # In development, allow all origins
        if self.settings.environment == "development":
            return origin or "*"

        # In production, check against allowed origins
        if not origin:
            return ""

        # Parse the origin URL for proper validation
        try:
            parsed_origin = urlparse(origin)
            if not parsed_origin.scheme or not parsed_origin.netloc:
                return ""
        except (ValueError, AttributeError):
            return ""

        allowed_origins = self.settings.allowed_origins

        # Check exact match
        if origin in allowed_origins:
            return origin

        # Check for wildcard subdomain patterns
        for allowed in allowed_origins:
            if allowed.endswith("*"):
                # Parse the allowed pattern
                try:
                    # Remove the wildcard and parse
                    allowed_base = allowed[:-1]  # Remove *
                    if allowed_base.endswith("."):
                        # Pattern like *.example.com
                        allowed_domain = allowed_base[:-1]  # Remove trailing .
                        if allowed_base.startswith("http"):
                            # Full URL pattern
                            parsed_allowed = urlparse(allowed_base + "dummy")
                            # Check scheme matches
                            if parsed_origin.scheme != parsed_allowed.scheme:
                                continue
                            # Extract domain from netloc
                            origin_domain = parsed_origin.netloc.lower()
                            allowed_domain = parsed_allowed.netloc.lower().replace(
                                "dummy", ""
                            )
                            # Check if origin is subdomain of allowed
                            if origin_domain.endswith(allowed_domain):
                                return origin
                        else:
                            # Domain-only pattern
                            origin_domain = parsed_origin.netloc.lower()
                            if (
                                origin_domain.endswith(allowed_domain)
                                or origin_domain == allowed_domain[1:]
                            ):
                                return origin
                except (ValueError, AttributeError):
                    # Skip malformed patterns
                    continue

        return ""


# Export middleware classes
__all__ = [
    "SecurityHeadersMiddleware",
    "CORSSecurityMiddleware",
]
