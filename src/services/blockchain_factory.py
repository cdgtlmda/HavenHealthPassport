"""Blockchain factory for provider selection."""

from typing import TYPE_CHECKING, Optional

from src.config import get_settings
from src.services.blockchain_service_aws import AWSBlockchainService
from src.services.blockchain_service_mock import MockBlockchainService
from src.utils.logging import get_logger

if TYPE_CHECKING:
    from src.services.base import BaseService

logger = get_logger(__name__)
settings = get_settings()


class BlockchainFactory:
    """Factory for creating blockchain service instances based on provider configuration."""

    @staticmethod
    def create_blockchain_service() -> "BaseService":
        """Create and return appropriate blockchain service based on configuration."""
        provider = getattr(settings, "blockchain_provider", "aws")
        environment = settings.environment.lower()

        # CRITICAL: In production, always use AWS Managed Blockchain for medical data
        # @encrypt_phi - Blockchain must encrypt all patient data
        # @access_control_required - Blockchain access requires proper authorization
        if environment == "production":
            if provider != "aws_managed_blockchain":
                raise RuntimeError(
                    f"CRITICAL: Production requires AWS Managed Blockchain, "
                    f"but provider is '{provider}'. Configure blockchain properly!"
                )

            # CRITICAL: Blockchain MUST be enabled in production
            if not getattr(settings, "enable_blockchain", True):
                raise RuntimeError(
                    "CRITICAL: Blockchain is disabled in production! "
                    "This violates patient data integrity requirements."
                )

            # Validate blockchain configuration
            if not settings.managed_blockchain_network_id:
                raise RuntimeError(
                    "CRITICAL: MANAGED_BLOCKCHAIN_NETWORK_ID not configured! "
                    "Cannot operate without blockchain network."
                )

            if not getattr(settings, "managed_blockchain_member_id", None):
                raise RuntimeError(
                    "CRITICAL: MANAGED_BLOCKCHAIN_MEMBER_ID not configured! "
                    "Cannot operate without blockchain member ID."
                )

            # Only import real service in production
            # @secure_storage - Production blockchain stores encrypted PHI
            logger.info("Using AWS Managed Blockchain service (production)")
            return AWSBlockchainService()

        # Staging should also use real AWS service
        if environment == "staging":
            if provider != "aws_managed_blockchain":
                logger.warning(f"Staging should use AWS, but provider is '{provider}'")

            if not getattr(settings, "enable_blockchain", True):
                raise RuntimeError("Blockchain must be enabled in staging")

            logger.info("Using AWS Managed Blockchain service (staging)")
            return AWSBlockchainService()

        # Development environment options
        if environment in ["development", "test", "local"]:
            if not getattr(settings, "enable_blockchain", True):
                logger.warning("Blockchain disabled in development, using mock")
                return MockBlockchainService()

            if (
                provider == "aws_managed_blockchain"
                and settings.managed_blockchain_network_id
            ):
                logger.info("Using AWS Managed Blockchain service (development)")
                return AWSBlockchainService()

            if provider == "local_development":
                logger.info("Using mock blockchain for local development")
                return MockBlockchainService()

        # No valid configuration found
        raise RuntimeError(
            f"Cannot determine blockchain service for environment: {environment}, "
            f"provider: {provider}. Check configuration."
        )


_blockchain_service_instance: Optional["BaseService"] = None


def get_blockchain_service() -> "BaseService":
    """Get singleton blockchain service instance."""
    global _blockchain_service_instance
    if _blockchain_service_instance is None:
        _blockchain_service_instance = BlockchainFactory.create_blockchain_service()

    return _blockchain_service_instance


# For backward compatibility
BlockchainService = get_blockchain_service
