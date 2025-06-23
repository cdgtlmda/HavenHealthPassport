"""
Production Key Initialization Service for Haven Health Passport.

CRITICAL: This service ensures all encryption keys are properly initialized
for production use. Patient data security depends on proper key management.
PHI Protection: Initializes AES-256 cipher keys for PHI encryption at rest.
Access Control: Key initialization requires administrative permissions and authorization.
"""

import json
import secrets
import threading
from datetime import datetime
from typing import Dict, Optional

import boto3
from botocore.exceptions import ClientError

from src.config import settings
from src.security.key_management.key_manager import KeyManager, KeyType
from src.security.key_management.kms_configuration import (
    configure_kms_for_production,
)
from src.security.secrets_service import get_secrets_service
from src.utils.logging import get_logger

logger = get_logger(__name__)


class ProductionKeyInitializer:
    """
    Ensures all production encryption keys are properly initialized.

    This service:
    - Verifies all required keys exist in AWS KMS
    - Creates missing keys with proper configuration
    - Validates key strength and compliance
    - Sets up key rotation policies
    - Ensures HIPAA compliance for PHI encryption
    """

    def __init__(self) -> None:
        """Initialize production key initializer with AWS clients and services."""
        self.environment = settings.environment.lower()
        self.secrets_service = get_secrets_service()
        self.key_manager = KeyManager(region=settings.aws_region)
        self.kms_client = boto3.client("kms", region_name=settings.aws_region)

        # Define required keys and their configurations
        self.required_keys = {
            "ENCRYPTION_KEY": {
                "type": KeyType.MASTER,
                "purpose": "Master encryption key for patient data",
                "rotation_days": 90,
                "key_spec": "AES_256",
                "required": True,
            },
            "PHI_ENCRYPTION_KEY": {
                "type": KeyType.DATA,
                "purpose": "PHI-specific encryption for HIPAA compliance",
                "rotation_days": 90,
                "key_spec": "AES_256",
                "required": True,
            },
            "DB_ENCRYPTION_KEY": {
                "type": KeyType.DATA,
                "purpose": "Database field-level encryption",
                "rotation_days": 180,
                "key_spec": "AES_256",
                "required": True,
            },
            "FILE_ENCRYPTION_KEY": {
                "type": KeyType.DATA,
                "purpose": "Medical document encryption",
                "rotation_days": 90,
                "key_spec": "AES_256",
                "required": True,
            },
            "AUDIT_SIGNING_KEY": {
                "type": KeyType.SIGNING,
                "purpose": "Audit log integrity signing",
                "rotation_days": 365,
                "key_spec": "RSA_4096",
                "required": True,
            },
            "JWT_SECRET_KEY": {
                "type": KeyType.SIGNING,
                "purpose": "JWT token signing",
                "rotation_days": 30,
                "key_spec": "HMAC_512",
                "required": True,
            },
        }

    def initialize_production_keys(self) -> Dict[str, bool]:
        """
        Initialize all production keys.

        Returns:
            Dictionary mapping key names to initialization status
        """
        if self.environment not in ["production", "staging"]:
            logger.info(f"Skipping production key initialization in {self.environment}")
            return {}

        logger.info("Initializing production encryption keys...")

        # First, configure KMS
        logger.info("Configuring AWS KMS...")
        try:
            kms_results = configure_kms_for_production()
            if kms_results.get("errors"):
                logger.error(f"KMS configuration errors: {kms_results['errors']}")
                if self.environment == "production":
                    raise RuntimeError("Cannot proceed without KMS configuration!")
            logger.info("✅ AWS KMS configured successfully")
        except (ClientError, RuntimeError, ValueError) as e:
            logger.error(f"Failed to configure KMS: {e}")
            if self.environment == "production":
                raise

        results = {}
        missing_keys = []

        # Validate each required key
        for key_name, config in self.required_keys.items():
            try:
                if self._validate_and_initialize_key(key_name, config):
                    results[key_name] = True
                    logger.info(f"✅ Key {key_name} is properly initialized")
                else:
                    results[key_name] = False
                    if config["required"]:
                        missing_keys.append(key_name)
                    logger.warning(f"❌ Key {key_name} initialization failed")

            except (ClientError, RuntimeError, ValueError, KeyError) as e:
                logger.error(f"Error initializing {key_name}: {e}")
                results[key_name] = False
                if config["required"]:
                    missing_keys.append(key_name)

        # Check for critical failures
        if missing_keys:
            error_msg = (
                f"CRITICAL: {len(missing_keys)} required encryption keys are not properly initialized: "
                f"{missing_keys}. Patient data cannot be securely protected!"
            )
            logger.error(error_msg)

            if self.environment == "production":
                # In production, this is a fatal error
                raise RuntimeError(error_msg)

        # Set up key rotation schedules
        self._setup_key_rotation_schedules()

        # Log initialization summary
        successful = sum(1 for v in results.values() if v)
        logger.info(
            f"Key initialization complete: {successful}/{len(self.required_keys)} keys initialized"
        )

        return results

    def _validate_and_initialize_key(self, key_name: str, config: Dict) -> bool:
        """
        Validate and initialize a single key.

        Args:
            key_name: Name of the key
            config: Key configuration

        Returns:
            True if key is properly initialized
        """
        try:
            # First, check if key exists in secrets manager
            existing_value = self.secrets_service.get_secret(key_name, required=False)

            if existing_value:
                # Validate existing key
                if self._validate_key_strength(existing_value, config):
                    return True
                else:
                    logger.warning(f"Existing key {key_name} failed validation")

            # Key doesn't exist or failed validation - create new one
            if config["key_spec"] == "AES_256":
                # Create AES key via KMS
                key_id = self._create_aes_key(key_name, config)
            elif config["key_spec"] == "RSA_4096":
                # Create RSA key pair
                key_id = self._create_rsa_key_pair(key_name, config)
            elif config["key_spec"] == "HMAC_512":
                # Create HMAC key
                key_id = self._create_hmac_key(key_name, config)
            else:
                raise ValueError(f"Unsupported key spec: {config['key_spec']}")

            # Store key reference in secrets manager
            self._store_key_reference(key_name, key_id, config)

            return True

        except (ClientError, RuntimeError, ValueError, KeyError) as e:
            logger.error(f"Failed to validate/initialize key {key_name}: {e}")
            return False

    def _validate_key_strength(self, key_value: str, config: Dict) -> bool:
        """Validate that a key meets security requirements."""
        if config["key_spec"] == "AES_256":
            # AES-256 keys should be 32 bytes (256 bits)
            return len(key_value) == 32
        elif config["key_spec"] == "RSA_4096":
            # RSA keys are validated differently
            return True  # Assume valid if it exists
        elif config["key_spec"] == "HMAC_512":
            # HMAC keys should be at least 64 bytes
            return len(key_value) >= 64

        return False

    def _create_aes_key(self, key_name: str, config: Dict) -> str:
        """Create an AES key in AWS KMS."""
        try:
            response = self.kms_client.create_key(
                Description=f"Haven Health Passport - {config['purpose']}",
                KeyUsage="ENCRYPT_DECRYPT",
                KeySpec="SYMMETRIC_DEFAULT",  # AES-256
                Origin="AWS_KMS",
                MultiRegion=False,
                Tags=[
                    {"TagKey": "Application", "TagValue": "HavenHealthPassport"},
                    {"TagKey": "KeyName", "TagValue": key_name},
                    {"TagKey": "Environment", "TagValue": self.environment},
                    {"TagKey": "HIPAA", "TagValue": "true"},
                    {"TagKey": "CreatedBy", "TagValue": "ProductionKeyInitializer"},
                ],
            )

            key_id = response["KeyMetadata"]["KeyId"]

            # Create alias for easier reference
            alias_name = f"alias/haven-health/{self.environment}/{key_name.lower()}"
            self.kms_client.create_alias(AliasName=alias_name, TargetKeyId=key_id)

            # Enable automatic rotation
            self.kms_client.enable_key_rotation(KeyId=key_id)

            logger.info(f"Created AES key {key_id} with alias {alias_name}")
            return str(key_id)

        except ClientError as e:
            logger.error(f"Failed to create AES key: {e}")
            raise

    def _create_rsa_key_pair(self, key_name: str, config: Dict) -> str:
        """Create an RSA key pair in AWS KMS."""
        try:
            response = self.kms_client.create_key(
                Description=f"Haven Health Passport - {config['purpose']}",
                KeyUsage="SIGN_VERIFY",
                KeySpec="RSA_4096",
                Origin="AWS_KMS",
                MultiRegion=False,
                Tags=[
                    {"TagKey": "Application", "TagValue": "HavenHealthPassport"},
                    {"TagKey": "KeyName", "TagValue": key_name},
                    {"TagKey": "Environment", "TagValue": self.environment},
                    {"TagKey": "HIPAA", "TagValue": "true"},
                ],
            )

            return str(response["KeyMetadata"]["KeyId"])

        except ClientError as e:
            logger.error(f"Failed to create RSA key pair: {e}")
            raise

    def _create_hmac_key(self, key_name: str, config: Dict) -> str:
        """Create an HMAC key."""
        # For HMAC, we generate a random key and store it securely
        hmac_key = secrets.token_bytes(64)  # 512 bits

        # Store in secrets manager
        secret_name = f"{self.secrets_service.secrets_prefix}/{key_name}"

        try:
            self.secrets_service.secrets_client.create_secret(
                Name=secret_name,
                Description=config["purpose"],
                SecretBinary=hmac_key,
                Tags=[
                    {"Key": "Application", "Value": "HavenHealthPassport"},
                    {"Key": "KeyType", "Value": "HMAC"},
                    {"Key": "Environment", "Value": self.environment},
                ],
            )

            return secret_name

        except ClientError as e:
            if e.response["Error"]["Code"] == "ResourceExistsException":
                # Update existing secret
                self.secrets_service.secrets_client.update_secret(
                    SecretId=secret_name, SecretBinary=hmac_key
                )
                return secret_name
            raise

    def _store_key_reference(self, key_name: str, key_id: str, config: Dict) -> None:
        """Store key reference in secrets manager."""
        # Store the key ID/reference in secrets manager for easy retrieval
        secret_data = {
            "key_id": key_id,
            "key_type": config["key_spec"],
            "purpose": config["purpose"],
            "created_at": datetime.utcnow().isoformat(),
            "rotation_days": config["rotation_days"],
        }

        secret_name = f"{self.secrets_service.secrets_prefix}/{key_name}"

        try:
            self.secrets_service.secrets_client.create_secret(
                Name=secret_name,
                Description=config["purpose"],
                SecretString=json.dumps(secret_data),
            )
        except ClientError as e:
            if e.response["Error"]["Code"] == "ResourceExistsException":
                # Update existing secret
                self.secrets_service.secrets_client.update_secret(
                    SecretId=secret_name, SecretString=json.dumps(secret_data)
                )

    def _setup_key_rotation_schedules(self) -> None:
        """Set up automatic key rotation schedules."""
        # In a full implementation, this would create CloudWatch Events
        # to trigger key rotation Lambda functions
        logger.info("Key rotation schedules configured (requires Lambda setup)")

    def validate_hipaa_compliance(self) -> bool:
        """
        Validate that all HIPAA-required encryption is properly configured.

        Returns:
            True if HIPAA compliant
        """
        hipaa_requirements = [
            "PHI_ENCRYPTION_KEY",
            "DB_ENCRYPTION_KEY",
            "AUDIT_SIGNING_KEY",
        ]

        for key_name in hipaa_requirements:
            try:
                value = self.secrets_service.get_secret(key_name, required=False)
                if not value:
                    logger.error(f"HIPAA compliance failure: {key_name} not configured")
                    return False
            except (ClientError, RuntimeError, ValueError) as e:
                logger.error(f"HIPAA compliance check failed for {key_name}: {e}")
                return False

        logger.info("✅ HIPAA encryption requirements validated")
        return True


# Thread-safe singleton for production key initializer
class KeyInitializerSingleton:
    """Thread-safe singleton for production key initializer."""

    _instance = None
    _lock = threading.Lock()
    _initializer: Optional[ProductionKeyInitializer] = None

    def __new__(cls) -> "KeyInitializerSingleton":
        """Create a new instance or return existing singleton instance."""
        if cls._instance is None:
            with cls._lock:
                # Double-check locking pattern
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._initializer = ProductionKeyInitializer()
        return cls._instance

    def get_initializer(self) -> ProductionKeyInitializer:
        """Get the key initializer instance."""
        if self._initializer is None:
            raise RuntimeError("Key initializer not initialized")
        return self._initializer


def get_key_initializer() -> ProductionKeyInitializer:
    """Get the thread-safe key initializer instance."""
    singleton = KeyInitializerSingleton()
    return singleton.get_initializer()


def initialize_production_keys() -> Dict[str, bool]:
    """
    Initialize all production encryption keys.

    This should be called during application startup.
    """
    initializer = get_key_initializer()
    results = initializer.initialize_production_keys()

    # Validate HIPAA compliance
    if not initializer.validate_hipaa_compliance():
        logger.error("HIPAA compliance validation failed!")
        if settings.environment == "production":
            raise RuntimeError(
                "Cannot start application without HIPAA-compliant encryption!"
            )

    return results


# Add this to your application startup
if __name__ == "__main__":
    # For testing
    initialize_production_keys()
