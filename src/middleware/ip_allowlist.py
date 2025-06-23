"""IP allowlisting middleware for additional security."""

import ipaddress
from typing import Any, Callable, List, Optional, Set

from fastapi import HTTPException, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from src.config import get_settings


class IPAllowlistMiddleware(BaseHTTPMiddleware):
    """Middleware to restrict access to allowed IP addresses."""

    def __init__(self, app: Any, allowed_ips: Optional[List[str]] = None) -> None:
        """
        Initialize IP allowlist middleware.

        Args:
            app: FastAPI application
            allowed_ips: List of allowed IP addresses/ranges
        """
        super().__init__(app)
        self.allowed_ips: Set[str] = set(allowed_ips or [])

        # Add localhost by default in development
        settings = get_settings()
        if settings.environment == "development":
            self.allowed_ips.update(["127.0.0.1", "::1", "localhost"])

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Check if request is from allowed IP."""
        # Skip for health checks
        if request.url.path in ["/health", "/ready", "/docs", "/openapi.json"]:
            response: Response = await call_next(request)
            return response

        # Get client IP
        client_ip = self._get_client_ip(request)

        # Check if IP is allowed
        if self.allowed_ips and client_ip not in self.allowed_ips:
            # Check for IP ranges
            if not self._is_ip_in_range(client_ip):
                raise HTTPException(
                    status_code=403, detail=f"Access denied from IP: {client_ip}"
                )

        response_final: Response = await call_next(request)
        return response_final

    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP from request."""
        # Check for proxy headers
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            # Get the first IP in the chain
            return forwarded.split(",")[0].strip()

        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip

        # Fall back to direct connection
        if request.client:
            return request.client.host

        return "unknown"

    def _is_ip_in_range(self, ip: str) -> bool:
        """Check if IP is in any allowed range with proper CIDR support."""
        try:
            # Parse the client IP address
            client_ip = ipaddress.ip_address(ip)

            for allowed in self.allowed_ips:
                # Check exact match first
                if ip == allowed:
                    return True

                # Handle wildcard patterns
                if allowed.endswith("*"):
                    prefix = allowed[:-1]
                    if ip.startswith(prefix):
                        return True

                # Handle CIDR notation
                elif "/" in allowed:
                    try:
                        network = ipaddress.ip_network(allowed, strict=False)
                        if client_ip in network:
                            return True
                    except (ipaddress.AddressValueError, ipaddress.NetmaskValueError):
                        # Log invalid CIDR notation but continue checking other rules
                        continue

                # Try to parse as a single IP address
                else:
                    try:
                        allowed_ip = ipaddress.ip_address(allowed)
                        if client_ip == allowed_ip:
                            return True
                    except ipaddress.AddressValueError:
                        # Not a valid IP address, skip
                        continue

        except ipaddress.AddressValueError:
            # If client IP is invalid, deny access for security
            return False

        return False

    def add_ip(self, ip: str) -> None:
        """Add an IP to the allowlist."""
        self.allowed_ips.add(ip)

    def remove_ip(self, ip: str) -> None:
        """Remove an IP from the allowlist."""
        self.allowed_ips.discard(ip)

    def get_allowed_ips(self) -> List[str]:
        """Get current list of allowed IPs."""
        return list(self.allowed_ips)
