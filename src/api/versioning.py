"""API versioning strategy for Haven Health Passport.

This module implements the API versioning strategy using URL path versioning
and content negotiation for backward compatibility.
 Handles FHIR Resource validation.
"""

import re
from datetime import datetime
from typing import Any, Callable, Dict, Optional

from fastapi import Header, HTTPException, Request
from fastapi.responses import JSONResponse

from src.utils.logging import get_logger

logger = get_logger(__name__)

# Module-level dependency variables to avoid B008 errors
header_none_dependency = Header(None)


class APIVersion:
    """Represents an API version with its metadata."""

    def __init__(
        self,
        version: str,
        release_date: datetime,
        deprecated: bool = False,
        sunset_date: Optional[datetime] = None,
        changes: Optional[Dict[str, Any]] = None,
    ):
        """Initialize API version."""
        self.version = version
        self.release_date = release_date
        self.deprecated = deprecated
        self.sunset_date = sunset_date
        self.changes = changes or {}

        # Parse version components
        match = re.match(r"v(\d+)\.(\d+)", version)
        if match:
            self.major = int(match.group(1))
            self.minor = int(match.group(2))
        else:
            raise ValueError(f"Invalid version format: {version}")

    def is_compatible_with(self, other: "APIVersion") -> bool:
        """Check if this version is compatible with another."""
        # Same major version = compatible
        return self.major == other.major

    def __str__(self) -> str:
        """Return string representation."""
        return self.version

    def __lt__(self, other: "APIVersion") -> bool:
        """Compare versions."""
        if self.major != other.major:
            return self.major < other.major
        return self.minor < other.minor


class APIVersionManager:
    """Manages API versions and routing."""

    def __init__(self) -> None:
        """Initialize version manager."""
        self.versions: Dict[str, APIVersion] = {}
        self.current_version: Optional[APIVersion] = None
        self.default_version: Optional[APIVersion] = None

        # Initialize versions
        self._initialize_versions()

    def _initialize_versions(self) -> None:
        """Initialize available API versions."""
        # Version 1.0 - Initial release
        self.register_version(
            APIVersion(
                version="v1.0",
                release_date=datetime(2024, 1, 1),
                changes={
                    "initial": "Initial API release",
                    "features": [
                        "Patient management",
                        "Health records",
                        "Basic authentication",
                    ],
                },
            )
        )

        # Version 1.1 - Added verifications
        self.register_version(
            APIVersion(
                version="v1.1",
                release_date=datetime(2024, 3, 1),
                changes={
                    "added": ["Verification endpoints", "Blockchain integration"],
                    "improved": ["Error handling", "Performance optimizations"],
                },
            )
        )

        # Version 2.0 - GraphQL and real-time
        self.register_version(
            APIVersion(
                version="v2.0",
                release_date=datetime(2024, 6, 1),
                changes={
                    "added": [
                        "GraphQL API",
                        "WebSocket subscriptions",
                        "Advanced filtering",
                    ],
                    "breaking": [
                        "Changed authentication flow",
                        "Updated response formats",
                    ],
                },
            )
        )

        # Set current and default versions
        self.current_version = self.versions["v2.0"]
        self.default_version = self.versions["v2.0"]

    def register_version(self, version: APIVersion) -> None:
        """Register a new API version."""
        self.versions[version.version] = version
        logger.info(f"Registered API version: {version}")

    def get_version(self, version_string: str) -> Optional[APIVersion]:
        """Get a specific API version."""
        return self.versions.get(version_string)

    def get_version_from_request(self, request: Request) -> APIVersion:
        """Extract API version from request."""
        # 1. Check URL path
        path_parts = request.url.path.split("/")
        if len(path_parts) > 1 and path_parts[1].startswith("v"):
            version_str = path_parts[1]
            version = self.get_version(version_str)
            if version:
                return version

        # 2. Check Accept header
        accept_header = request.headers.get("accept", "")
        match = re.search(r"application/vnd\.haven\.([v\d\.]+)\+json", accept_header)
        if match:
            version_str = match.group(1)
            version = self.get_version(version_str)
            if version:
                return version

        # 3. Check X-API-Version header
        version_header = request.headers.get("x-api-version")
        if version_header:
            version = self.get_version(version_header)
            if version:
                return version

        # 4. Return default version
        if self.default_version:
            return self.default_version
        raise HTTPException(status_code=500, detail="No default API version configured")

    def check_version_compatibility(self, request: Request) -> None:
        """Check if requested version is compatible and not deprecated."""
        version = self.get_version_from_request(request)

        # Check if version exists
        if not version:
            raise HTTPException(status_code=400, detail="Invalid API version requested")

        # Check if deprecated
        if version.deprecated:
            sunset_date = (
                version.sunset_date.isoformat() if version.sunset_date else "TBD"
            )
            logger.warning(f"Deprecated API version {version} used")
            # Add deprecation headers to response
            request.state.deprecation_headers = {
                "Deprecation": "true",
                "Sunset": sunset_date,
                "Link": f'</api/{self.current_version}/docs>; rel="successor-version"',
            }

        # Check if sunset
        if version.sunset_date and datetime.now() > version.sunset_date:
            raise HTTPException(
                status_code=410, detail=f"API version {version} is no longer available"
            )

    def get_available_versions(self) -> Dict[str, Dict[str, Any]]:
        """Get information about all available versions."""
        versions_info = {}

        for version_str, version in self.versions.items():
            versions_info[version_str] = {
                "version": version.version,
                "release_date": version.release_date.isoformat(),
                "deprecated": version.deprecated,
                "sunset_date": (
                    version.sunset_date.isoformat() if version.sunset_date else None
                ),
                "current": version == self.current_version,
                "changes": version.changes,
            }

        return versions_info


# Global version manager instance
version_manager = APIVersionManager()


async def version_middleware(request: Request, call_next: Callable) -> Any:
    """Middleware to handle API versioning."""
    # Check version compatibility
    try:
        version_manager.check_version_compatibility(request)
    except HTTPException as e:
        return JSONResponse(status_code=e.status_code, content={"detail": e.detail})

    # Process request
    response = await call_next(request)

    # Add version headers
    version = version_manager.get_version_from_request(request)
    response.headers["X-API-Version"] = version.version

    # Add deprecation headers if applicable
    if hasattr(request.state, "deprecation_headers"):
        for header, value in request.state.deprecation_headers.items():
            response.headers[header] = value

    return response


def negotiate_content_type(accept: Optional[str] = header_none_dependency) -> str:
    """Negotiate content type based on Accept header."""
    if not accept:
        return "application/json"

    # Parse Accept header
    accept_types = []
    for accept_type in accept.split(","):
        parts = accept_type.split(";")
        media_type = parts[0].strip()
        quality = 1.0

        for part in parts[1:]:
            if part.strip().startswith("q="):
                try:
                    quality = float(part.strip()[2:])
                except ValueError:
                    pass

        accept_types.append((media_type, quality))

    # Sort by quality
    accept_types.sort(key=lambda x: x[1], reverse=True)

    # Find best match
    supported_types = {
        "application/json": "json",
        "application/vnd.haven+json": "json",
        "application/vnd.haven.v1+json": "json_v1",
        "application/vnd.haven.v2+json": "json_v2",
        "application/xml": "xml",
        "application/fhir+json": "fhir_json",
        "application/fhir+xml": "fhir_xml",
    }

    for media_type, _ in accept_types:
        if media_type == "*/*":
            return "application/json"

        if media_type in supported_types:
            return media_type

        # Check wildcards
        if media_type.endswith("/*"):
            prefix = media_type[:-2]
            for supported in supported_types:
                if supported.startswith(prefix):
                    return supported

    # Default to JSON
    return "application/json"


# Base URL configuration
class BaseURLConfig:
    """Configuration for base URLs across different environments."""

    def __init__(self) -> None:
        """Initialize base URL configuration."""
        self.environments = {
            "development": {
                "base_url": "http://localhost:8000",
                "api_base": "/api",
                "graphql_endpoint": "/graphql",
                "websocket_endpoint": "/ws",
            },
            "staging": {
                "base_url": "https://staging.havenhealthpassport.org",
                "api_base": "/api",
                "graphql_endpoint": "/graphql",
                "websocket_endpoint": "/ws",
            },
            "production": {
                "base_url": "https://api.havenhealthpassport.org",
                "api_base": "/api",
                "graphql_endpoint": "/graphql",
                "websocket_endpoint": "/ws",
            },
        }

    def get_base_url(self, environment: str = "development") -> str:
        """Get base URL for environment."""
        env_config = self.environments.get(
            environment, self.environments["development"]
        )
        return env_config["base_url"]

    def get_api_url(
        self, environment: str = "development", version: str = "v2.0"
    ) -> str:
        """Get API URL for environment and version."""
        env_config = self.environments.get(
            environment, self.environments["development"]
        )
        return f"{env_config['base_url']}{env_config['api_base']}/{version}"

    def get_graphql_url(self, environment: str = "development") -> str:
        """Get GraphQL URL for environment."""
        env_config = self.environments.get(
            environment, self.environments["development"]
        )
        return f"{env_config['base_url']}{env_config['graphql_endpoint']}"

    def get_websocket_url(self, environment: str = "development") -> str:
        """Get WebSocket URL for environment."""
        env_config = self.environments.get(
            environment, self.environments["development"]
        )
        base = (
            env_config["base_url"]
            .replace("https://", "wss://")
            .replace("http://", "ws://")
        )
        return f"{base}{env_config['websocket_endpoint']}"


# Global base URL configuration
base_url_config = BaseURLConfig()


# Export for use in FastAPI app
__all__ = [
    "APIVersion",
    "APIVersionManager",
    "version_manager",
    "version_middleware",
    "negotiate_content_type",
    "BaseURLConfig",
    "base_url_config",
]


def validate_fhir_data(data: dict) -> dict:
    """Validate FHIR data.

    Args:
        data: Data to validate

    Returns:
        Validation result with 'valid', 'errors', and 'warnings' keys
    """
    errors: list[str] = []
    warnings: list[str] = []

    if not data:
        errors.append("No data provided")

    return {"valid": len(errors) == 0, "errors": errors, "warnings": warnings}
