"""Flask middleware for security headers."""

try:
    from flask import Flask, Response, g, request

    FLASK_AVAILABLE = True
except ImportError:
    FLASK_AVAILABLE = False
    Flask = None
    Response = None
    g = None
    request = None

from .security_headers import SecurityHeaders


def init_security_headers(app: "Flask", environment: str = "production") -> None:
    """
    Initialize security headers middleware for Flask app.

    Args:
        app: Flask application instance
        environment: Deployment environment
    """
    security_headers = SecurityHeaders(environment)

    @app.before_request  # type: ignore[misc]
    def before_request() -> None:
        """Generate nonce for CSP before each request."""
        g.csp_nonce = security_headers.generate_nonce()

    @app.after_request  # type: ignore[misc]
    def after_request(response: Response) -> Response:
        """Add security headers to all responses."""
        # Get nonce from request context
        nonce = getattr(g, "csp_nonce", None)

        # Add security headers
        headers = security_headers.get_security_headers(nonce)
        for header, value in headers.items():
            response.headers[header] = value

        # Add CORS headers for API endpoints
        if request.path.startswith("/api/"):
            allowed_origins = app.config.get(
                "CORS_ORIGINS", ["https://havenhealthpassport.org"]
            )
            cors_headers = security_headers.get_cors_headers(allowed_origins)
            for header, value in cors_headers.items():
                response.headers[header] = value

        return response

    # Store security headers instance on app
    app.security_headers = security_headers
