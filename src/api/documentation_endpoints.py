"""Documentation and developer portal endpoints.

This module provides endpoints for serving API documentation,
developer portal, and interactive API explorer.
"""

from typing import Any, Dict

from fastapi import APIRouter, FastAPI
from fastapi.responses import HTMLResponse

try:
    from src.api.developer_portal import DeveloperPortal, create_developer_portal_html
except ImportError:
    # If there's an import error, create dummy functions
    class DeveloperPortal:  # type: ignore[no-redef]
        def __init__(self, app: Any) -> None:
            self.app = app

        def get_portal_content(self) -> Dict[str, Any]:
            return {}

        def get_getting_started_guide(self) -> Dict[str, Any]:
            return {}

        def get_authentication_guide(self) -> Dict[str, Any]:
            return {}

        def get_code_samples(self) -> Dict[str, Any]:
            return {}

        def get_tutorials(self) -> list:
            return []

        def get_best_practices(self) -> Dict[str, Any]:
            return {}

        def get_troubleshooting_guide(self) -> Dict[str, Any]:
            return {}

        def get_faq(self) -> list:
            return []

        def get_support_info(self) -> Dict[str, Any]:
            return {}

        def get_sdk_info(self) -> Dict[str, Any]:
            return {}

    def create_developer_portal_html() -> str:
        return "<html><body>Developer portal not available</body></html>"


from src.api.openapi_endpoint_docs import (
    get_endpoint_documentation,
    get_error_code_reference,
    get_rate_limit_documentation,
)
from src.config import get_settings

router = APIRouter()
settings = get_settings()


@router.get(
    "/docs/portal",
    response_class=HTMLResponse,
    tags=["documentation"],
    summary="Developer Portal",
    description="Interactive developer portal with tutorials and examples",
)
async def developer_portal() -> HTMLResponse:
    """Serve the developer portal HTML page."""
    return HTMLResponse(content=create_developer_portal_html())


@router.get(
    "/docs/endpoints",
    response_model=Dict[str, Any],
    tags=["documentation"],
    summary="Endpoint Documentation",
    description="Get comprehensive documentation for all endpoints",
)
async def get_endpoints_documentation() -> Dict[str, Any]:
    """Get detailed documentation for all API endpoints."""
    return {
        "endpoints": get_endpoint_documentation(),
        "base_url": "https://api.havenhealthpassport.org",
        "version": settings.app_version,
    }


@router.get(
    "/docs/errors",
    response_model=Dict[str, Any],
    tags=["documentation"],
    summary="Error Code Reference",
    description="Get comprehensive error code documentation",
)
async def get_error_codes() -> Dict[str, Any]:
    """Get documentation for all error codes."""
    return get_error_code_reference()


@router.get(
    "/docs/rate-limits",
    response_model=Dict[str, Any],
    tags=["documentation"],
    summary="Rate Limiting Documentation",
    description="Get rate limiting documentation and current limits",
)
async def get_rate_limits() -> Dict[str, Any]:
    """Get rate limiting documentation."""
    return get_rate_limit_documentation()


@router.get(
    "/docs/portal-content",
    response_model=Dict[str, Any],
    tags=["documentation"],
    summary="Developer Portal Content",
    description="Get all developer portal content as JSON",
)
async def get_portal_content() -> Dict[str, Any]:
    """Get developer portal content as JSON."""
    # Create portal instance with dummy app
    dummy_app = FastAPI()
    portal = DeveloperPortal(dummy_app)

    return portal.get_portal_content()


@router.get(
    "/docs/getting-started",
    response_model=Dict[str, Any],
    tags=["documentation"],
    summary="Getting Started Guide",
    description="Get the getting started guide",
)
async def get_getting_started() -> Dict[str, Any]:
    """Get getting started guide."""
    dummy_app = FastAPI()
    portal = DeveloperPortal(dummy_app)

    return portal.get_getting_started_guide()


@router.get(
    "/docs/authentication",
    response_model=Dict[str, Any],
    tags=["documentation"],
    summary="Authentication Guide",
    description="Get comprehensive authentication documentation",
)
async def get_authentication_guide() -> Dict[str, Any]:
    """Get authentication guide."""
    dummy_app = FastAPI()
    portal = DeveloperPortal(dummy_app)

    return portal.get_authentication_guide()


@router.get(
    "/docs/code-samples",
    response_model=Dict[str, Any],
    tags=["documentation"],
    summary="Code Samples",
    description="Get code samples in multiple languages",
)
async def get_code_samples() -> Dict[str, Any]:
    """Get code samples."""
    dummy_app = FastAPI()
    portal = DeveloperPortal(dummy_app)

    return portal.get_code_samples()


@router.get(
    "/docs/tutorials",
    response_model=Dict[str, Any],
    tags=["documentation"],
    summary="API Tutorials",
    description="Get step-by-step tutorials",
)
async def get_tutorials() -> Dict[str, Any]:
    """Get tutorials."""
    dummy_app = FastAPI()
    portal = DeveloperPortal(dummy_app)

    return {"tutorials": portal.get_tutorials()}


@router.get(
    "/docs/best-practices",
    response_model=Dict[str, Any],
    tags=["documentation"],
    summary="Best Practices",
    description="Get API best practices guide",
)
async def get_best_practices() -> Dict[str, Any]:
    """Get best practices."""
    dummy_app = FastAPI()
    portal = DeveloperPortal(dummy_app)

    return portal.get_best_practices()


@router.get(
    "/docs/troubleshooting",
    response_model=Dict[str, Any],
    tags=["documentation"],
    summary="Troubleshooting Guide",
    description="Get troubleshooting guide for common issues",
)
async def get_troubleshooting() -> Dict[str, Any]:
    """Get troubleshooting guide."""
    dummy_app = FastAPI()
    portal = DeveloperPortal(dummy_app)

    return portal.get_troubleshooting_guide()


@router.get(
    "/docs/faq",
    response_model=Dict[str, Any],
    tags=["documentation"],
    summary="FAQ",
    description="Get frequently asked questions",
)
async def get_faq() -> Dict[str, Any]:
    """Get FAQ."""
    dummy_app = FastAPI()
    portal = DeveloperPortal(dummy_app)

    return {"faq": portal.get_faq()}


@router.get(
    "/docs/support",
    response_model=Dict[str, Any],
    tags=["documentation"],
    summary="Support Information",
    description="Get support contact information",
)
async def get_support() -> Dict[str, Any]:
    """Get support information."""
    dummy_app = FastAPI()
    portal = DeveloperPortal(dummy_app)

    return portal.get_support_info()


@router.get(
    "/docs/sdks",
    response_model=Dict[str, Any],
    tags=["documentation"],
    summary="SDK Information",
    description="Get information about available SDKs",
)
async def get_sdks() -> Dict[str, Any]:
    """Get SDK information."""
    dummy_app = FastAPI()
    portal = DeveloperPortal(dummy_app)

    return portal.get_sdk_info()


# Export router
__all__ = ["router"]
