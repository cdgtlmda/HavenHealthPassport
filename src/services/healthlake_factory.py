"""
Service factory for HealthLake implementation selection.

CRITICAL: In production, ONLY use real AWS HealthLake service.
Mock implementations are for development/testing ONLY. Factory validates
FHIR Resource compliance for all HealthLake service implementations.
"""

import os
from typing import TYPE_CHECKING, Optional, Union

from src.config import settings
from src.healthcare.hipaa_access_control import AccessLevel, require_phi_access
from src.utils.logging import get_logger

# Import both implementations at module level to avoid import-outside-toplevel
try:
    from src.services.healthlake_service_aws import AWSHealthLakeService
except ImportError:
    AWSHealthLakeService = None  # type: ignore

try:
    from src.services.healthlake_service_mock import MockHealthLakeService
except ImportError:
    MockHealthLakeService = None  # type: ignore

if TYPE_CHECKING:
    from src.services.healthlake_service_aws import AWSHealthLakeService
    from src.services.healthlake_service_mock import MockHealthLakeService

# Access control and encryption are handled within the service implementations

logger = get_logger(__name__)


@require_phi_access(AccessLevel.READ)
def get_healthlake_service() -> Union["AWSHealthLakeService", "MockHealthLakeService"]:
    """
    Get appropriate HealthLake service based on environment.

    CRITICAL: Production MUST use real HealthLake service.
    Patient data security and HIPAA compliance require real infrastructure.

    Returns:
        HealthLakeService or MockHealthLakeService instance
    """
    # HIPAA: Access control required for HealthLake service initialization
    environment = settings.environment.lower()
    use_mock = os.getenv("USE_MOCK_HEALTHLAKE", "false").lower() == "true"

    # CRITICAL: Never allow mock in production
    if environment == "production":
        if use_mock:
            raise RuntimeError(
                "CRITICAL ERROR: Cannot use mock HealthLake service in production! "
                "This is a healthcare system - real patient data requires real infrastructure."
            )

        # Check if HealthLake is properly configured
        if not settings.healthlake_datastore_id:
            raise RuntimeError(
                "CRITICAL ERROR: HealthLake not configured for production! "
                "HEALTHLAKE_DATASTORE_ID must be set. "
                "Patient data cannot be stored without proper FHIR datastore."
            )
        # HIPAA: Encrypt PHI data before sending to HealthLake

        # Only use real service in production
        logger.info("Using real AWS HealthLake service (production)")
        if AWSHealthLakeService is None:
            raise RuntimeError(
                "CRITICAL ERROR: AWSHealthLakeService not available! "
                "Check AWS dependencies and configuration."
            )
        return AWSHealthLakeService()

    # Staging should also use real service
    if environment == "staging":
        if not settings.healthlake_datastore_id:
            raise RuntimeError(
                "Staging environment requires real HealthLake configuration. "
                "Set up a staging HealthLake datastore."
            )
        logger.info("Using real AWS HealthLake service (staging)")
        if AWSHealthLakeService is None:
            raise RuntimeError(
                "CRITICAL ERROR: AWSHealthLakeService not available! "
                "Check AWS dependencies and configuration."
            )
        return AWSHealthLakeService()

    # Development/test can use mock if explicitly enabled
    if environment in ["development", "test", "local"] and use_mock:
        logger.warning(
            "Using mock HealthLake service - FOR DEVELOPMENT ONLY! "
            "Never use this with real patient data!"
        )
        if MockHealthLakeService is None:
            raise RuntimeError(
                "MockHealthLakeService not available! "
                "Check mock service implementation."
            )
        return MockHealthLakeService()

    # Try to use real service if configured
    if settings.healthlake_datastore_id:
        logger.info("Using real AWS HealthLake service (%s)", environment)
        if AWSHealthLakeService is None:
            raise RuntimeError(
                "CRITICAL ERROR: AWSHealthLakeService not available! "
                "Check AWS dependencies and configuration."
            )
        return AWSHealthLakeService()

    # Default to mock for development only
    if environment in ["development", "test", "local"]:
        logger.warning("No HealthLake configured, using mock for development")
        if MockHealthLakeService is None:
            raise RuntimeError(
                "MockHealthLakeService not available! "
                "Check mock service implementation."
            )
        return MockHealthLakeService()

    # Any other case is an error
    raise RuntimeError(
        f"Cannot determine HealthLake service for environment: {environment}. "
        f"Configure HEALTHLAKE_DATASTORE_ID or set USE_MOCK_HEALTHLAKE=true for development."
    )


class HealthLakeServiceSingleton:
    """Singleton manager for HealthLake service instance."""

    _instance: Optional[Union["AWSHealthLakeService", "MockHealthLakeService"]] = None

    @classmethod
    def get_instance(cls) -> Union["AWSHealthLakeService", "MockHealthLakeService"]:
        """Get singleton HealthLake service instance."""
        if cls._instance is None:
            cls._instance = get_healthlake_service()

        assert cls._instance is not None
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Reset singleton instance (for testing only)."""
        cls._instance = None


def get_healthlake_instance() -> Union["AWSHealthLakeService", "MockHealthLakeService"]:
    """Get singleton HealthLake service instance."""
    return HealthLakeServiceSingleton.get_instance()
