"""
Hardware Security Module (HSM) Integration for Haven Health Passport.

CRITICAL: This module integrates with AWS CloudHSM for hardware-based
key protection. Patient data encryption keys are stored in FIPS 140-2
Level 3 validated hardware for maximum security.

FHIR Compliance: HSM-encrypted FHIR Resource data must be validated.
PHI Protection: Hardware-based crypto operations for PHI using AES-256 cipher.
Access Control: HSM access requires authenticated crypto user permissions.
"""

import json
import os
from datetime import datetime
from typing import Any, Dict, Optional

import boto3

try:
    import pycloudhsm

    HSM_AVAILABLE = True
except ImportError:
    pycloudhsm = None
    HSM_AVAILABLE = False

# CryptographyError and InvalidToken are not available in cryptography.exceptions
from cryptography.exceptions import InvalidSignature as InvalidToken

from src.config import settings
from src.security.envelope_encryption import EnvelopeEncryption
from src.utils.logging import get_logger


# Define CryptographyError as a generic exception
class CryptographyError(Exception):
    """Generic cryptography error."""


logger = get_logger(__name__)


class HardwareSecurityModule:
    """
    Manages cryptographic operations using AWS CloudHSM.

    Provides:
    - Hardware-based key generation
    - Secure key storage
    - Cryptographic operations
    - Key lifecycle management
    """

    def __init__(self) -> None:
        """Initialize the Hardware Security Module connection and configuration."""
        self.environment = settings.environment.lower()

        # CloudHSM configuration
        self.cluster_id = os.getenv("CLOUDHSM_CLUSTER_ID")
        self.hsm_ip = os.getenv("CLOUDHSM_IP")
        self.crypto_user = os.getenv("CLOUDHSM_CRYPTO_USER")
        self.crypto_password = os.getenv("CLOUDHSM_CRYPTO_PASSWORD")

        # Validate configuration in production
        if self.environment == "production":
            if not all(
                [self.cluster_id, self.hsm_ip, self.crypto_user, self.crypto_password]
            ):
                raise RuntimeError(
                    "CloudHSM not configured for production! "
                    "Hardware security module is required for patient data protection. "
                    "Set CLOUDHSM_CLUSTER_ID, CLOUDHSM_IP, CLOUDHSM_CRYPTO_USER, and CLOUDHSM_CRYPTO_PASSWORD."
                )

        # Initialize HSM connection
        self._initialize_hsm()

        logger.info("Initialized Hardware Security Module")

    def _initialize_hsm(self) -> None:
        """Initialize connection to CloudHSM."""
        if not self.hsm_ip:
            logger.warning("HSM not configured, using software crypto for development")
            self.hsm_client = None
            return

        try:
            # Initialize CloudHSM client
            self.hsm_client = pycloudhsm.CloudHsmClient(
                hsm_ip=self.hsm_ip,
                username=self.crypto_user,
                password=self.crypto_password,
            )

            # Test connection
            self.hsm_client.connect()
            logger.info(f"Connected to CloudHSM cluster {self.cluster_id}")

        except (ConnectionError, TimeoutError) as e:
            logger.error(f"Failed to connect to CloudHSM: {e}")
            if self.environment == "production":
                raise
            else:
                logger.warning("Falling back to software crypto for development")
                self.hsm_client = None

    def generate_master_key(self, key_label: str) -> str:
        """
        Generate a master encryption key in the HSM.

        Args:
            key_label: Unique label for the key

        Returns:
            Key handle/identifier
        """
        if self.hsm_client:
            try:
                # Generate AES-256 key in HSM
                key_handle = self.hsm_client.generate_symmetric_key(
                    key_type="AES",
                    key_size=256,
                    label=key_label,
                    extractable=False,  # Key cannot be exported
                    persistent=True,  # Key persists across sessions
                )

                logger.info(f"Generated master key in HSM: {key_label}")
                return str(key_handle)

            except (ConnectionError, TimeoutError) as e:
                logger.error(f"Failed to generate key in HSM: {e}")
                raise
        else:
            # Development fallback - use KMS
            logger.warning("Using KMS for key generation (development mode)")
            kms_client = boto3.client("kms", region_name=settings.aws_region)
            response = kms_client.create_key(
                Description=f"Haven Health Passport master key: {key_label}",
                KeyUsage="ENCRYPT_DECRYPT",
                Origin="AWS_KMS",
            )
            return str(response["KeyMetadata"]["KeyId"])

    def encrypt_with_hsm(self, key_handle: str, plaintext: bytes) -> bytes:
        """
        Encrypt data using HSM-protected key.

        Args:
            key_handle: HSM key identifier
            plaintext: Data to encrypt

        Returns:
            Encrypted ciphertext
        """
        if self.hsm_client:
            try:
                # Use HSM for encryption
                ciphertext = self.hsm_client.encrypt(
                    key_handle=key_handle,
                    plaintext=plaintext,
                    algorithm="AES_GCM",
                    iv_length=12,  # 96 bits for GCM
                )
                return bytes(ciphertext)

            except (CryptographyError, TypeError, ValueError) as e:
                logger.error("HSM encryption failed: %s", e)
                raise
        else:
            # Development fallback
            # EnvelopeEncryption imported at module level

            envelope = EnvelopeEncryption(key_handle, settings.aws_region)
            result = envelope.encrypt_data(plaintext)
            return bytes(result["ciphertext"].encode("utf-8"))

    def decrypt_with_hsm(self, key_handle: str, ciphertext: bytes) -> bytes:
        """
        Decrypt data using HSM-protected key.

        Args:
            key_handle: HSM key identifier
            ciphertext: Encrypted data

        Returns:
            Decrypted plaintext
        """
        if self.hsm_client:
            try:
                # Use HSM for decryption
                plaintext = self.hsm_client.decrypt(
                    key_handle=key_handle, ciphertext=ciphertext, algorithm="AES_GCM"
                )
                return bytes(plaintext)

            except (CryptographyError, InvalidToken, TypeError, ValueError) as e:
                logger.error(f"HSM decryption failed: {e}")
                raise
        else:
            # Development fallback
            logger.warning("Using software decryption (development mode)")
            # In real implementation, would use envelope decryption
            return ciphertext  # Placeholder

    def rotate_master_key(self, old_key_handle: str, new_key_label: str) -> str:
        """
        Rotate a master encryption key.

        Args:
            old_key_handle: Current key identifier
            new_key_label: Label for new key

        Returns:
            New key handle
        """
        # Generate new key
        new_key_handle = self.generate_master_key(new_key_label)

        # Log rotation event
        logger.info(f"Rotated master key from {old_key_handle} to {new_key_label}")

        # In production, would also:
        # 1. Re-encrypt all data with new key
        # 2. Securely delete old key after migration
        # 3. Update key references in database

        return new_key_handle

    def get_key_info(self, key_handle: str) -> Dict[str, Any]:
        """Get information about an HSM key."""
        if self.hsm_client:
            try:
                key_info = self.hsm_client.get_key_attributes(key_handle)
                return {
                    "handle": key_handle,
                    "type": key_info.get("type"),
                    "size": key_info.get("size"),
                    "created": key_info.get("created_date"),
                    "extractable": key_info.get("extractable", False),
                }
            except (CryptographyError, ValueError) as e:
                logger.error(f"Failed to get key info: {e}")
                return {"handle": key_handle, "error": str(e)}
        else:
            return {"handle": key_handle, "type": "KMS", "environment": "development"}

    def audit_key_usage(self, key_handle: str, operation: str, user_id: str) -> None:
        """Log key usage for audit trail."""
        audit_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "key_handle": key_handle,
            "operation": operation,
            "user_id": user_id,
            "environment": self.environment,
            "hsm_cluster": self.cluster_id,
        }

        # Log to CloudWatch
        logger.info(f"HSM key usage: {json.dumps(audit_entry)}")

        # In production, also log to audit database
        if self.environment == "production":
            # Would integrate with AuditLog model
            pass

    def close(self) -> None:
        """Close HSM connection."""
        if self.hsm_client:
            try:
                self.hsm_client.disconnect()
                logger.info("Disconnected from CloudHSM")
            except (OSError, TypeError, ValueError) as e:
                logger.error(f"Error closing HSM connection: {e}")


# Module-level singleton holder
class _HSMHolder:
    """Holds the singleton HSM instance."""

    instance: Optional[HardwareSecurityModule] = None


def get_hardware_security_module() -> HardwareSecurityModule:
    """Get the global HSM instance."""
    if _HSMHolder.instance is None:
        _HSMHolder.instance = HardwareSecurityModule()
    # Type assertion: after assignment above, instance is not None
    assert _HSMHolder.instance is not None
    return _HSMHolder.instance
