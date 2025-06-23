"""Edge caching middleware for API responses.

This middleware handles edge caching logic, including cache headers,
conditional requests, and integration with CDN services.
"""

import hashlib
import json
from datetime import datetime
from typing import Any, Callable, Optional, Set

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from src.services.cache_ttl_config import CacheCategory, ttl_manager
from src.services.cdn_service import CDNContentType, cdn_service
from src.utils.logging import get_logger

logger = get_logger(__name__)


class EdgeCacheMiddleware(BaseHTTPMiddleware):
    """Middleware for handling edge caching."""

    def __init__(
        self,
        app: Any,
        cacheable_paths: Optional[Set[str]] = None,
        cache_methods: Optional[Set[str]] = None,
        enable_etag: bool = True,
        enable_conditional: bool = True,
    ) -> None:
        """Initialize edge cache middleware.

        Args:
            app: FastAPI application
            cacheable_paths: Set of path prefixes to cache
            cache_methods: HTTP methods to cache
            enable_etag: Enable ETag generation
            enable_conditional: Enable conditional requests
        """
        super().__init__(app)
        self.cacheable_paths = cacheable_paths or {
            "/api/v2/public",
            "/api/v2/translations",
            "/api/v2/glossary",
            "/static",
            "/assets",
            "/media",
        }
        self.cache_methods = cache_methods or {"GET", "HEAD"}
        self.enable_etag = enable_etag
        self.enable_conditional = enable_conditional

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request with edge caching logic."""
        # Check if request should be cached
        if not self._should_cache(request):
            return await call_next(request)  # type: ignore[no-any-return]

        # Handle conditional requests
        if self.enable_conditional:
            cached_response = await self._handle_conditional_request(request)
            if cached_response:
                return cached_response

        # Process request
        response = await call_next(request)

        # Only cache successful responses
        if response.status_code not in {200, 203, 204, 206, 300, 301, 304}:
            return response  # type: ignore[no-any-return]

        # Add cache headers
        await self._add_cache_headers(request, response)

        # Generate ETag if enabled
        if self.enable_etag and response.status_code == 200:
            await self._add_etag(response)

        # Add timing header
        response.headers["X-Cache"] = "MISS"
        response.headers["X-Cache-Lookup"] = "MISS"

        return response  # type: ignore[no-any-return]

    def _should_cache(self, request: Request) -> bool:
        """Check if request should be cached."""
        # Check method
        if request.method not in self.cache_methods:
            return False

        # Check path
        path = request.url.path
        if not any(path.startswith(prefix) for prefix in self.cacheable_paths):
            return False

        # Don't cache authenticated requests by default
        if "Authorization" in request.headers:
            # Unless it's a public endpoint
            if not path.startswith("/api/v2/public"):
                return False

        # Check Cache-Control header
        cache_control = request.headers.get("Cache-Control", "")
        if "no-cache" in cache_control or "no-store" in cache_control:
            return False

        return True

    async def _handle_conditional_request(self, request: Request) -> Optional[Response]:
        """Handle conditional GET requests (If-None-Match, If-Modified-Since)."""
        # Check If-None-Match (ETag)
        if_none_match = request.headers.get("If-None-Match")
        if if_none_match:
            # In a real implementation, we would check against stored ETags
            # For now, return None to continue processing
            return None

        # Check If-Modified-Since
        if_modified_since = request.headers.get("If-Modified-Since")
        if if_modified_since:
            # In a real implementation, we would check against last modified time
            # For now, return None to continue processing
            return None

        return None

    async def _add_cache_headers(self, request: Request, response: Response) -> None:
        """Add appropriate cache headers to response."""
        path = request.url.path

        # Determine content type
        content_type = self._determine_content_type(path, response)

        # Check if CDN should be used
        if cdn_service.should_use_cdn(request, content_type):
            # Get CDN cache headers
            category = self._determine_cache_category(path)
            private = "Authorization" in request.headers

            headers = cdn_service.get_cache_headers(
                content_type=content_type,
                category=category,
                private=private,
            )

            # Add headers to response
            for key, value in headers.items():
                response.headers[key] = value
        else:
            # Add basic cache headers
            category = self._determine_cache_category(path)
            headers = ttl_manager.get_cache_headers(category)

            for key, value in headers.items():
                response.headers[key] = value

        # Add additional headers
        response.headers["X-Content-Type-Options"] = "nosniff"

        # Add Last-Modified if not present
        if "Last-Modified" not in response.headers:
            response.headers["Last-Modified"] = datetime.utcnow().strftime(
                "%a, %d %b %Y %H:%M:%S GMT"
            )

    async def _add_etag(self, response: Response) -> None:
        """Generate and add ETag header."""
        # Read response body
        body = b""
        async for chunk in response.body_iterator:  # type: ignore[attr-defined]
            body += chunk

        # Generate ETag from content
        etag = self._generate_etag(body)
        response.headers["ETag"] = etag

        # Recreate response with body
        response = Response(
            content=body,
            status_code=response.status_code,
            headers=dict(response.headers),
            media_type=response.media_type,
        )

    def _generate_etag(self, content: bytes) -> str:
        """Generate ETag from content."""
        # Use weak ETag for dynamic content
        # MD5 is used here only for checksum, not for security
        content_hash = hashlib.md5(content, usedforsecurity=False).hexdigest()
        return f'W/"{content_hash}"'

    def _determine_content_type(self, path: str, _response: Response) -> CDNContentType:
        """Determine CDN content type from path and response."""
        # Check file extensions
        if path.endswith((".js", ".css", ".woff", ".woff2", ".ttf", ".eot")):
            return CDNContentType.STATIC_ASSETS

        if path.endswith((".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg")):
            return CDNContentType.IMAGES

        if path.endswith((".pdf", ".doc", ".docx")):
            return CDNContentType.DOCUMENTS

        # Check API paths
        if path.startswith("/api/v2/translations"):
            return CDNContentType.TRANSLATIONS

        if path.startswith("/api/v2/public"):
            return CDNContentType.PUBLIC_DATA

        # Default to API responses
        return CDNContentType.API_RESPONSES

    def _determine_cache_category(self, path: str) -> CacheCategory:
        """Determine cache category from path."""
        if "/patients" in path:
            return CacheCategory.PATIENT_BASIC

        if "/health-records" in path:
            return CacheCategory.HEALTH_RECORD

        if "/translations" in path:
            return CacheCategory.TRANSLATION

        if "/search" in path:
            return CacheCategory.SEARCH_RESULTS

        if "/files" in path or "/media" in path:
            return CacheCategory.FILE_METADATA

        # Default
        return CacheCategory.QUERY_RESULTS


class EdgeCacheHeaderMiddleware:
    """Simplified middleware for just adding cache headers."""

    def __init__(self, default_cache_control: str = "public, max-age=300"):
        """Initialize cache header middleware.

        Args:
            default_cache_control: Default Cache-Control header value
        """
        self.default_cache_control = default_cache_control

    async def __call__(self, request: Request, call_next: Callable) -> Response:
        """Add cache headers to response."""
        response = await call_next(request)

        # Only add headers if not already present
        if "Cache-Control" not in response.headers:
            # Determine appropriate cache control
            cache_control = self._get_cache_control(request, response)
            response.headers["Cache-Control"] = cache_control

        return response  # type: ignore[no-any-return]

    def _get_cache_control(self, request: Request, response: Response) -> str:
        """Determine appropriate Cache-Control header."""
        # Don't cache errors
        if response.status_code >= 400:
            return "no-cache, no-store, must-revalidate"

        # Private for authenticated requests
        if "Authorization" in request.headers:
            return "private, max-age=0, must-revalidate"

        # Use default for public content
        return self.default_cache_control


# Decorator for adding cache headers to specific endpoints
def cache_response(
    max_age: int = 300,
    s_maxage: Optional[int] = None,
    public: bool = True,
    must_revalidate: bool = False,
    category: Optional[CacheCategory] = None,
) -> Callable[..., Any]:
    """Add cache headers to endpoint responses.

    Args:
        max_age: Browser cache time in seconds
        s_maxage: CDN cache time in seconds (defaults to max_age)
        public: Whether response can be cached publicly
        must_revalidate: Whether cache must revalidate
        category: Cache category for automatic TTL
    """

    def decorator(func: Callable) -> Callable:
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Get response from endpoint
            response = await func(*args, **kwargs)

            # If response is not a Response object, wrap it
            if not isinstance(response, Response):
                response = Response(
                    content=json.dumps(response),
                    media_type="application/json",
                )

            # Determine cache values
            if category:
                ttl = ttl_manager.get_ttl(category)
                cache_max_age = min(max_age, ttl)
                cache_s_maxage = s_maxage or ttl
            else:
                cache_max_age = max_age
                cache_s_maxage = s_maxage or max_age

            # Build Cache-Control header
            cache_parts = []

            if public:
                cache_parts.append("public")
            else:
                cache_parts.append("private")

            cache_parts.append(f"max-age={cache_max_age}")
            cache_parts.append(f"s-maxage={cache_s_maxage}")

            if must_revalidate:
                cache_parts.append("must-revalidate")

            # Add stale-while-revalidate for better performance
            if cache_max_age > 60:
                cache_parts.append(
                    f"stale-while-revalidate={min(cache_max_age // 2, 3600)}"
                )

            response.headers["Cache-Control"] = ", ".join(cache_parts)

            # Add other cache-related headers
            response.headers["X-Cache-TTL"] = str(cache_s_maxage)

            return response

        return wrapper

    return decorator


# Export components
__all__ = [
    "EdgeCacheMiddleware",
    "EdgeCacheHeaderMiddleware",
    "cache_response",
]
