"""Input sanitization middleware for API security.

This middleware provides input sanitization to prevent XSS, SQL injection,
and other injection attacks.
"""

import html
import json
import re
from typing import Any, Awaitable, Callable, Dict

from fastapi import Request, Response
from starlette.applications import ASGIApp
from starlette.middleware.base import BaseHTTPMiddleware

from src.utils.logging import get_logger

logger = get_logger(__name__)


class InputSanitizationMiddleware(BaseHTTPMiddleware):
    """Middleware to sanitize user inputs."""

    def __init__(self, app: ASGIApp) -> None:
        """Initialize input sanitization middleware."""
        super().__init__(app)

        # Dangerous patterns to detect
        self.sql_patterns = [
            r"(\b(SELECT|INSERT|UPDATE|DELETE|DROP|UNION|ALTER|CREATE)\b)",
            r"(-{2}|\/\*|\*\/)",  # SQL comments
            r"(;|\||&&)",  # Command separators
            r"(xp_|sp_)",  # SQL Server extended procedures
        ]

        self.xss_patterns = [
            r"<script[^>]*>.*?</script>",
            r"javascript:",
            r"on\w+\s*=",  # Event handlers
            r"<iframe[^>]*>",
            r"<object[^>]*>",
            r"<embed[^>]*>",
            r"<link[^>]*>",
        ]

        self.path_traversal_patterns = [
            r"\.\./",  # Directory traversal
            r"\.\.\%2[fF]",  # URL encoded traversal
            r"\.\.\%5[cC]",  # URL encoded backslash
        ]

        # Compile patterns for efficiency
        self.sql_regex = re.compile("|".join(self.sql_patterns), re.IGNORECASE)
        self.xss_regex = re.compile(
            "|".join(self.xss_patterns), re.IGNORECASE | re.DOTALL
        )
        self.path_regex = re.compile("|".join(self.path_traversal_patterns))

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        """Sanitize request inputs before processing."""
        # Skip sanitization for certain paths
        skip_paths = ["/health", "/ready", "/metrics"]
        if request.url.path in skip_paths:
            return await call_next(request)

        try:
            # Sanitize query parameters
            if request.query_params:
                sanitized_params = self._sanitize_params(dict(request.query_params))
                if self._contains_dangerous_content(str(sanitized_params)):
                    logger.warning(
                        f"Blocked potentially malicious query params: {request.url}"
                    )
                    return Response(
                        content=json.dumps({"error": "Invalid input detected"}),
                        status_code=400,
                        media_type="application/json",
                    )

            # Sanitize request body for POST/PUT/PATCH
            if request.method in ["POST", "PUT", "PATCH"]:
                # Store original body for later use
                body = await request.body()

                if body:
                    try:
                        # Try to parse as JSON
                        data = json.loads(body)
                        sanitized_data = self._sanitize_data(data)

                        if self._contains_dangerous_content(json.dumps(sanitized_data)):
                            logger.warning(
                                f"Blocked potentially malicious body content: {request.url}"
                            )
                            return Response(
                                content=json.dumps({"error": "Invalid input detected"}),
                                status_code=400,
                                media_type="application/json",
                            )

                        # Create new request with sanitized body
                        async def receive() -> Dict[str, Any]:
                            return {
                                "type": "http.request",
                                "body": json.dumps(sanitized_data).encode(),
                            }

                        request._receive = receive  # pylint: disable=protected-access

                    except json.JSONDecodeError:
                        # Not JSON, check for dangerous patterns in raw body
                        if self._contains_dangerous_content(
                            body.decode("utf-8", errors="ignore")
                        ):
                            logger.warning(
                                f"Blocked potentially malicious non-JSON body: {request.url}"
                            )
                            return Response(
                                content=json.dumps({"error": "Invalid input detected"}),
                                status_code=400,
                                media_type="application/json",
                            )

                        # Restore original body
                        async def receive() -> Dict[str, Any]:
                            return {"type": "http.request", "body": body}

                        request._receive = receive  # pylint: disable=protected-access

            # Process request
            response = await call_next(request)
            return response

        except (AttributeError, ValueError, RuntimeError) as e:
            logger.error(f"Error in input sanitization: {e}")
            # On error, pass through to avoid breaking the application
            return await call_next(request)

    def _sanitize_data(self, data: Any) -> Any:
        """Recursively sanitize data structure."""
        if isinstance(data, str):
            return self._sanitize_string(data)
        elif isinstance(data, dict):
            return {k: self._sanitize_data(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [self._sanitize_data(item) for item in data]
        else:
            return data

    def _sanitize_params(self, params: Dict[str, str]) -> Dict[str, str]:
        """Sanitize query parameters."""
        return {k: self._sanitize_string(v) for k, v in params.items()}

    def _sanitize_string(self, value: str) -> str:
        """Sanitize a string value."""
        # HTML encode special characters
        sanitized = html.escape(value)

        # Remove null bytes
        sanitized = sanitized.replace("\x00", "")

        # Remove non-printable characters (except newlines and tabs)
        sanitized = "".join(
            char
            for char in sanitized
            if char.isprintable() or char in ["\n", "\t", "\r"]
        )

        return sanitized.strip()

    def _contains_dangerous_content(self, content: str) -> bool:
        """Check if content contains dangerous patterns."""
        # Check for SQL injection patterns
        if self.sql_regex.search(content):
            return True

        # Check for XSS patterns
        if self.xss_regex.search(content):
            return True

        # Check for path traversal
        if self.path_regex.search(content):
            return True

        # Check for LDAP injection
        if any(char in content for char in ["(", ")", "*", "\\", "\0"]):
            if re.search(r"\(\w+=[^)]+\)", content):  # LDAP filter pattern
                return True

        # Check for command injection
        dangerous_chars = ["|", ";", "&", "$", "`", "\n", "\r"]
        if any(char in content for char in dangerous_chars):
            # More specific check for command patterns
            if re.search(
                r"[|;&$`].*?(cat|ls|rm|wget|curl|bash|sh|cmd)", content, re.IGNORECASE
            ):
                return True

        return False


class CSRFProtectionMiddleware(BaseHTTPMiddleware):
    """CSRF protection middleware."""

    def __init__(self, app: ASGIApp) -> None:
        """Initialize CSRF protection middleware."""
        super().__init__(app)
        self.safe_methods = ["GET", "HEAD", "OPTIONS", "TRACE"]
        self.csrf_header = "X-CSRF-Token"
        self.csrf_cookie = "csrf_token"

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        """Validate CSRF token for state-changing requests."""
        # Skip CSRF check for safe methods
        if request.method in self.safe_methods:
            return await call_next(request)

        # Skip for API endpoints that use JWT authentication
        if request.url.path.startswith("/api/"):
            # Check for Authorization header (JWT)
            if request.headers.get("Authorization"):
                return await call_next(request)

        # Get CSRF token from header and cookie
        header_token = request.headers.get(self.csrf_header)
        cookie_token = request.cookies.get(self.csrf_cookie)

        # Validate CSRF token
        if not header_token or not cookie_token or header_token != cookie_token:
            logger.warning(f"CSRF validation failed for {request.url.path}")
            return Response(
                content=json.dumps({"error": "CSRF validation failed"}),
                status_code=403,
                media_type="application/json",
            )

        return await call_next(request)


# Export middleware classes
__all__ = [
    "InputSanitizationMiddleware",
    "CSRFProtectionMiddleware",
]
