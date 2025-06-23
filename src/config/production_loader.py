"""
Production-ready configuration loader for Haven Health Passport.

This module integrates with AWS Secrets Manager to load sensitive
configuration in production environments while maintaining backward
compatibility with environment variables for development.

FHIR Compliance: Configuration must be validated for FHIR Resource requirements.
PHI Protection: All PHI configuration uses encryption keys loaded from secure storage.
Access Control: Configuration loading requires proper authorization and permissions.
"""

import logging
from functools import lru_cache
from typing import Any, Optional

from botocore.exceptions import BotoCoreError, ClientError

from src.config.base import Settings
from src.security.secrets_service import SecretsService, get_secrets_service

logger = logging.getLogger(__name__)


class ProductionSettings(Settings):
    """
    Enhanced settings class that integrates with AWS Secrets Manager.

    CRITICAL: This ensures all sensitive configuration is loaded from
    secure sources in production to protect patient data.
    """

    def __init__(self, **kwargs: Any) -> None:
        """Initialize production loader with secure secrets handling.

        Args:
            **kwargs: Additional configuration parameters
        """
        # First, load from environment and defaults
        super().__init__(**kwargs)

        # Then override with secrets from AWS Secrets Manager if in production
        if self.environment.lower() in ["production", "staging"]:
            self._load_production_secrets()

    def _load_production_secrets(self) -> None:
        """Load sensitive configuration from AWS Secrets Manager."""
        try:
            secrets_service = get_secrets_service()

            # Critical encryption keys - MUST come from Secrets Manager in production
            self._load_secret(
                "secret_key", "SECRET_KEY", secrets_service, required=True
            )
            self._load_secret(
                "encryption_key", "ENCRYPTION_KEY", secrets_service, required=True
            )
            self._load_secret(
                "jwt_secret_key", "JWT_SECRET_KEY", secrets_service, required=True
            )
            self._load_secret(
                "jwt_refresh_secret_key",
                "JWT_REFRESH_SECRET_KEY",
                secrets_service,
                required=True,
            )

            # PHI encryption keys for HIPAA compliance
            self._load_secret(
                "phi_encryption_key",
                "PHI_ENCRYPTION_KEY",
                secrets_service,
                required=True,
            )
            self._load_secret(
                "db_encryption_key", "DB_ENCRYPTION_KEY", secrets_service, required=True
            )
            self._load_secret(
                "file_encryption_key",
                "FILE_ENCRYPTION_KEY",
                secrets_service,
                required=True,
            )

            # Signing keys
            self._load_secret(
                "audit_signing_key", "AUDIT_SIGNING_KEY", secrets_service, required=True
            )
            self._load_secret(
                "document_signing_key",
                "DOCUMENT_SIGNING_KEY",
                secrets_service,
                required=True,
            )

            # AWS service configurations
            self._load_secret(
                "healthlake_datastore_id",
                "HEALTHLAKE_DATASTORE_ID",
                secrets_service,
                required=True,
            )
            self._load_secret(
                "managed_blockchain_network_id",
                "MANAGED_BLOCKCHAIN_NETWORK_ID",
                secrets_service,
                required=True,
            )
            self._load_secret(
                "managed_blockchain_member_id",
                "MANAGED_BLOCKCHAIN_MEMBER_ID",
                secrets_service,
                required=True,
            )

            # External API keys
            self._load_secret(
                "resend_api_key", "RESEND_API_KEY", secrets_service, required=False
            )
            self._load_secret(
                "twilio_auth_token",
                "TWILIO_AUTH_TOKEN",
                secrets_service,
                required=False,
            )
            self._load_secret(
                "virus_scan_api_key",
                "VIRUS_SCAN_API_KEY",
                secrets_service,
                required=False,
            )

            # Database credentials
            self._load_secret(
                "database_url", "DATABASE_URL", secrets_service, required=True
            )
            self._load_secret("redis_url", "REDIS_URL", secrets_service, required=False)

            # Validate critical secrets are loaded
            self._validate_production_config()

            logger.info(
                "Successfully loaded production secrets from AWS Secrets Manager"
            )

        except (
            BotoCoreError,
            ClientError,
            ConnectionError,
            TypeError,
            ValueError,
        ) as e:
            logger.error("Failed to load production secrets: %s", e)
            raise RuntimeError(
                "CRITICAL: Cannot load production secrets. "
                "Patient data security requires proper configuration! "
                f"Error: {e}"
            ) from e

    def _load_secret(
        self,
        attr_name: str,
        secret_name: str,
        secrets_service: SecretsService,
        required: bool = True,
    ) -> None:
        """Load a single secret and set it as an attribute."""
        try:
            value = secrets_service.get_secret(secret_name, required=required)
            if value:
                setattr(self, attr_name, value)
        except (ConnectionError, TimeoutError) as e:
            if required and self.environment == "production":
                raise RuntimeError(
                    f"Failed to load required secret {secret_name}: {e}"
                ) from e
            logger.warning("Could not load secret %s: %s", secret_name, e)

    def _validate_production_config(self) -> None:
        """Validate all critical configuration is properly set for production."""
        if self.environment == "production":
            # Validate core encryption keys
            if not self.secret_key or len(self.secret_key) < 64:
                raise ValueError(
                    "SECRET_KEY must be at least 64 characters in production"
                )

            if not self.encryption_key or len(self.encryption_key) != 32:
                raise ValueError(
                    "ENCRYPTION_KEY must be exactly 32 characters for AES-256"
                )

            if not self.jwt_secret_key or len(self.jwt_secret_key) < 64:
                raise ValueError(
                    "JWT_SECRET_KEY must be at least 64 characters in production"
                )

            if (
                not hasattr(self, "jwt_refresh_secret_key")
                or not getattr(self, "jwt_refresh_secret_key", None)
                or len(getattr(self, "jwt_refresh_secret_key", "")) < 64
            ):
                raise ValueError(
                    "JWT_REFRESH_SECRET_KEY must be at least 64 characters in production"
                )

            # Validate PHI encryption keys
            if not hasattr(self, "phi_encryption_key") or not self.phi_encryption_key:
                raise ValueError("PHI_ENCRYPTION_KEY is required for HIPAA compliance")

            if not hasattr(self, "db_encryption_key") or not self.db_encryption_key:
                raise ValueError(
                    "DB_ENCRYPTION_KEY is required for database encryption"
                )

            if not hasattr(self, "audit_signing_key") or not self.audit_signing_key:
                raise ValueError("AUDIT_SIGNING_KEY is required for audit integrity")

            # Validate healthcare service configuration
            if not self.healthlake_datastore_id:
                raise ValueError("HEALTHLAKE_DATASTORE_ID is required in production")

            if not self.managed_blockchain_network_id:
                raise ValueError(
                    "MANAGED_BLOCKCHAIN_NETWORK_ID is required in production"
                )

            # Ensure HIPAA compliance settings
            if not self.phi_encryption_enabled:
                raise ValueError("PHI encryption must be enabled in production")

            if not self.phi_access_audit_enabled:
                raise ValueError("PHI access auditing must be enabled in production")

            if not self.require_mfa_for_phi_access:
                logger.warning("MFA for PHI access is not required - security risk!")

            # Validate database connection
            if not hasattr(self, "database_url") or not self.database_url:
                raise ValueError("DATABASE_URL is required in production")

            logger.info("Production configuration validated successfully")


# Module-level singleton holder
class _SettingsHolder:
    """Holds the singleton settings instance."""

    instance: Optional[ProductionSettings] = None


@lru_cache()
def get_settings() -> ProductionSettings:
    """
    Get cached settings instance with production enhancements.

    This function ensures that sensitive configuration is loaded from
    AWS Secrets Manager in production environments.
    """
    if _SettingsHolder.instance is None:
        _SettingsHolder.instance = ProductionSettings()

        # Log configuration status
        env = _SettingsHolder.instance.environment
        logger.info("Loaded configuration for environment: %s", env)

        if env == "production":
            logger.info(
                "Production configuration loaded with AWS Secrets Manager integration"
            )
        elif env == "development":
            logger.info("Development configuration loaded from environment variables")

    return _SettingsHolder.instance


def reload_settings() -> None:
    """
    Force reload of settings - useful for testing or after rotation.

    WARNING: This clears the cache and creates a new settings instance.
    Use with caution in production.
    """
    _SettingsHolder.instance = None
    get_settings.cache_clear()
    logger.info("Settings cache cleared and will be reloaded on next access")


# For backward compatibility
settings = get_settings()
