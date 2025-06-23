"""
Application Startup Initialization for Haven Health Passport.

CRITICAL: This module ensures all production security configurations
are properly initialized before the application handles any patient data.
PHI Protection: Validates all encryption systems are operational before PHI access.
Access Control: Verifies authorization systems and permissions are properly configured.
"""

from typing import Any, List, Optional

import boto3
from botocore.exceptions import BotoCoreError as BotoCore
from botocore.exceptions import ClientError
from pydantic import ValidationError

from src.config import settings
from src.config.production_environment import configure_production_environment
from src.security.key_management import initialize_production_keys
from src.security.secrets_service import validate_production_secrets
from src.utils.logging import get_logger


# Define CryptographyError as a general exception for cryptography-related errors
class CryptographyError(Exception):
    """Raised when encryption/decryption operations fail."""


logger = get_logger(__name__)


class StartupInitializer:
    """
    Handles all critical startup initialization for production.

    This ensures:
    - All encryption keys are properly configured
    - AWS services are connected
    - Security policies are enforced
    - HIPAA compliance is validated
    """

    def __init__(self) -> None:
        """Initialize startup security configuration and validation."""
        self.environment = settings.environment.lower()
        self.initialization_complete = False
        self.initialization_errors: List[str] = []

    def _configure_environment(self) -> bool:
        """Configure and validate environment variables."""
        try:
            logger.info("Configuring environment variables...")

            if self.environment in ["production", "staging"]:
                # Validate production environment
                if not configure_production_environment():
                    error_msg = "Environment configuration validation failed"
                    self.initialization_errors.append(error_msg)
                    logger.error(error_msg)
                    return False

            logger.info("✅ Environment variables configured successfully")
            return True

        except (TypeError, ValidationError, ValueError) as e:
            error_msg = f"Environment configuration failed: {e}"
            self.initialization_errors.append(error_msg)
            logger.error(error_msg)
            return False

    def initialize(self, app: Optional[Any] = None) -> bool:
        """
        Run all startup initialization tasks.

        Args:
            app: Optional Flask/FastAPI app instance

        Returns:
            True if initialization successful, False otherwise
        """
        logger.info(
            f"Starting Haven Health Passport initialization for {self.environment}"
        )

        # Step 1: Configure and validate environment variables
        if not self._configure_environment():
            return False

        # Step 2: Initialize production encryption keys
        if not self._initialize_encryption():
            return False

        # Step 3: Validate all secrets are configured
        if not self._validate_secrets():
            return False

        # Step 4: Validate AWS services
        if not self._validate_aws_services():
            return False

        # Step 5: Initialize security policies
        if not self._initialize_security_policies():
            return False

        # Step 6: Validate HIPAA compliance
        if not self._validate_hipaa_compliance():
            return False

        # Step 7: Initialize app-specific configurations
        if app:
            self._configure_app(app)

        self.initialization_complete = True
        logger.info("✅ Haven Health Passport initialization complete")

        return True

    def _initialize_encryption(self) -> bool:
        """Initialize all encryption keys."""
        try:
            logger.info("Initializing encryption keys...")

            if self.environment in ["production", "staging"]:
                # Initialize production keys from AWS KMS
                results = initialize_production_keys()

                # Check if all required keys initialized
                failed_keys = [k for k, v in results.items() if not v]
                if failed_keys:
                    error_msg = f"Failed to initialize encryption keys: {failed_keys}"
                    self.initialization_errors.append(error_msg)
                    logger.error(error_msg)
                    return False

            logger.info("✅ Encryption keys initialized successfully")
            return True

        except (
            BotoCore,
            ClientError,
            ConnectionError,
            CryptographyError,
            ValueError,
        ) as e:
            error_msg = f"Encryption initialization failed: {e}"
            self.initialization_errors.append(error_msg)
            logger.error(error_msg)
            return False

    def _validate_secrets(self) -> bool:
        """Validate all required secrets are configured."""
        try:
            logger.info("Validating secrets configuration...")

            if self.environment in ["production", "staging"]:
                if not validate_production_secrets():
                    error_msg = "Secret validation failed - missing required secrets"
                    self.initialization_errors.append(error_msg)
                    logger.error(error_msg)
                    return False

            logger.info("✅ Secrets validated successfully")
            return True

        except (CryptographyError, TypeError, ValidationError, ValueError) as e:
            error_msg = f"Secret validation failed: {e}"
            self.initialization_errors.append(error_msg)
            logger.error(error_msg)
            return False

    def _validate_aws_services(self) -> bool:
        """Validate AWS service connections."""
        if self.environment not in ["production", "staging"]:
            return True

        try:
            logger.info("Validating AWS service connections...")

            # Validate HealthLake
            if not settings.healthlake_datastore_id:
                logger.warning("HealthLake datastore ID not configured")

            # Validate Managed Blockchain
            if not settings.managed_blockchain_network_id:
                logger.warning("Managed Blockchain network ID not configured")

            # Validate S3

            s3_client = boto3.client("s3", region_name=settings.aws_region)
            s3_client.list_buckets()  # Test connection

            logger.info("✅ AWS services validated")
            return True

        except (
            BotoCore,
            ClientError,
            ConnectionError,
            TypeError,
            ValidationError,
            ValueError,
        ) as e:
            error_msg = f"AWS service validation failed: {e}"
            self.initialization_errors.append(error_msg)
            logger.error(error_msg)

            # This is critical in production
            if self.environment == "production":
                return False

            return True  # Allow startup in staging with warnings

    def _initialize_security_policies(self) -> bool:
        """Initialize security policies."""
        try:
            logger.info("Initializing security policies...")

            # Ensure PHI encryption is enabled
            if not settings.phi_encryption_enabled:
                error_msg = "PHI encryption is disabled!"
                self.initialization_errors.append(error_msg)
                logger.error(error_msg)

                if self.environment == "production":
                    return False

            # Ensure audit logging is enabled
            if not settings.phi_access_audit_enabled:
                error_msg = "PHI access auditing is disabled!"
                self.initialization_errors.append(error_msg)
                logger.error(error_msg)

                if self.environment == "production":
                    return False

            # Check MFA requirement
            if not settings.require_mfa_for_phi_access:
                logger.warning("MFA for PHI access is not required - security risk!")

            logger.info("✅ Security policies initialized")
            return True

        except (RuntimeError, TypeError, ValueError) as e:
            error_msg = f"Security policy initialization failed: {e}"
            self.initialization_errors.append(error_msg)
            logger.error(error_msg)
            return False

    def _validate_hipaa_compliance(self) -> bool:
        """Validate HIPAA compliance requirements."""
        try:
            logger.info("Validating HIPAA compliance...")

            compliance_checks = {
                "Encryption at rest": settings.phi_encryption_enabled,
                "Access auditing": settings.phi_access_audit_enabled,
                "PHI encryption key": (
                    bool(settings.phi_encryption_key)
                    if hasattr(settings, "phi_encryption_key")
                    else False
                ),
                "Audit signing key": (
                    bool(settings.audit_signing_key)
                    if hasattr(settings, "audit_signing_key")
                    else False
                ),
            }

            failed_checks = [k for k, v in compliance_checks.items() if not v]

            if failed_checks:
                error_msg = f"HIPAA compliance failures: {failed_checks}"
                self.initialization_errors.append(error_msg)
                logger.error(error_msg)

                if self.environment == "production":
                    return False

            logger.info("✅ HIPAA compliance validated")
            return True

        except (TypeError, ValidationError, ValueError) as e:
            error_msg = f"HIPAA compliance validation failed: {e}"
            self.initialization_errors.append(error_msg)
            logger.error(error_msg)
            return False

    def _configure_app(self, app: Any) -> None:
        """Configure app-specific settings."""
        try:
            # Flask configuration
            if hasattr(app, "config"):
                app.config["PHI_ENCRYPTION_ENABLED"] = settings.phi_encryption_enabled
                app.config["AUDIT_ENABLED"] = settings.phi_access_audit_enabled
                app.config["ENVIRONMENT"] = self.environment

                # Add initialization status to app
                app.initialization_complete = self.initialization_complete
                app.initialization_errors = self.initialization_errors

            # FastAPI configuration
            elif hasattr(app, "state"):
                app.state.phi_encryption_enabled = settings.phi_encryption_enabled
                app.state.audit_enabled = settings.phi_access_audit_enabled
                app.state.environment = self.environment
                app.state.initialization_complete = self.initialization_complete
                app.state.initialization_errors = self.initialization_errors

            logger.info("✅ App configuration complete")

        except (CryptographyError, ValueError) as e:
            logger.error(f"App configuration failed: {e}")
            # Non-fatal, continue

    def get_status(self) -> dict:
        """Get initialization status."""
        return {
            "complete": self.initialization_complete,
            "environment": self.environment,
            "errors": self.initialization_errors,
            "encryption_enabled": settings.phi_encryption_enabled,
            "audit_enabled": settings.phi_access_audit_enabled,
        }


# Module-level singleton instance holder
class _InitializerHolder:
    """Holds the singleton startup initializer instance."""

    instance: Optional[StartupInitializer] = None


def get_startup_initializer() -> StartupInitializer:
    """Get or create the startup initializer."""
    if _InitializerHolder.instance is None:
        _InitializerHolder.instance = StartupInitializer()
    return _InitializerHolder.instance


def initialize_application(app: Optional[Any] = None) -> bool:
    """
    Initialize the Haven Health Passport application.

    This MUST be called during application startup before handling
    any requests that might involve patient data.

    Args:
        app: Optional Flask/FastAPI app instance

    Returns:
        True if initialization successful

    Raises:
        RuntimeError: If initialization fails in production
    """
    initializer = get_startup_initializer()

    success = initializer.initialize(app)

    if not success:
        error_msg = (
            f"CRITICAL: Application initialization failed with {len(initializer.initialization_errors)} errors:\n"
            + "\n".join(f"  - {error}" for error in initializer.initialization_errors)
        )

        logger.error(error_msg)

        if initializer.environment == "production":
            # Fatal error in production
            raise RuntimeError(error_msg)
        else:
            # Warning in development/staging
            logger.warning(
                "Continuing with initialization errors in non-production environment"
            )

    return success


# Example usage in Flask app:
# from src.security.startup_initializer import initialize_application
# app = Flask(__name__)
# initialize_application(app)

# Example usage in FastAPI app:
# from src.security.startup_initializer import initialize_application
# app = FastAPI()
# @app.on_event("startup")
# async def startup_event():
#     initialize_application(app)
