"""Mock Services Package for Haven Health Passport.

This package contains REAL mock implementations for external services only.
Internal services use actual implementations - NO MOCKS for critical functionality.
"""

from .external_services import (
    ExternalServiceContractTests,
    ExternalServiceMocks,
    RealExternalServiceMocks,
)

__all__ = [
    "RealExternalServiceMocks",
    "ExternalServiceMocks",
    "ExternalServiceContractTests",
]

# Module-level singleton instance
_external_mocks_instance = None


def get_external_mocks():
    """Get or create initialized external service mocks."""
    global _external_mocks_instance
    if _external_mocks_instance is None:
        _external_mocks_instance = RealExternalServiceMocks.initialize_all_mocks()
    return _external_mocks_instance
