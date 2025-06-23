"""
Generic Encryption Service for Haven Health Passport.

This module provides a generic encryption service interface.
HIPAA: Access control required for PHI encryption/decryption operations.

IMPORTANT: This module uses a thread-safe singleton pattern instead of global
variables to prevent race conditions and data leaks between patients.
"""

import asyncio
import logging
import os
import threading
from typing import Any, Dict, Optional, Union

from ..healthcare.hipaa_access_control import (
    AccessLevel,
    audit_phi_access,
    require_phi_access,
)
from .envelope_encryption import EnvelopeEncryption

logger = logging.getLogger(__name__)


class EncryptionService:
    """Generic encryption service that wraps envelope encryption."""

    def __init__(self, kms_key_id: str, region: str = "us-east-1"):
        """
        Initialize the encryption service.

        Args:
            kms_key_id: The KMS key ID or ARN to use for encryption
            region: AWS region where the KMS key is located
        """
        self.kms_key_id = kms_key_id
        self.region = region
        self.envelope_encryption = EnvelopeEncryption(kms_key_id, region)

    async def encrypt(
        self, data: bytes, context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Encrypt data asynchronously.

        Args:
            data: Data to encrypt
            context: Optional encryption context

        Returns:
            Encrypted data envelope (dict containing ciphertext, encrypted key, etc.)
        """
        # Convert context to string dict for KMS
        encryption_context = None
        if context:
            encryption_context = {k: str(v) for k, v in context.items()}

        # Use envelope encryption
        return self.envelope_encryption.encrypt_data(data, encryption_context)

    async def decrypt(
        self,
        encrypted_data: Union[Dict[str, Any], bytes],
        context: Optional[Dict[str, Any]] = None,
    ) -> bytes:
        """
        Decrypt data asynchronously.

        Args:
            encrypted_data: Encrypted envelope (dict) to decrypt
            context: Optional encryption context for validation

        Returns:
            Decrypted data
        """
        # Ensure we have a proper envelope dictionary
        if not isinstance(encrypted_data, dict):
            raise ValueError("encrypted_data must be an encryption envelope dictionary")

        # If context provided, validate it matches the envelope's encryption context
        if context:
            provided_context = {k: str(v) for k, v in context.items()}
            envelope_context = encrypted_data.get("encryption_context", {})

            # Verify contexts match
            if envelope_context and provided_context != envelope_context:
                raise ValueError(
                    "Provided encryption context does not match envelope context"
                )

        # Use envelope encryption - it will handle context validation with KMS
        return self.envelope_encryption.decrypt_data(encrypted_data)


# Thread-safe singleton implementation
class EncryptionServiceSingleton:
    """Thread-safe singleton for encryption service."""

    _instance = None
    _lock = threading.Lock()
    _service: EncryptionService

    def __new__(cls) -> "EncryptionServiceSingleton":
        """Create or return the singleton instance of EncryptionServiceSingleton."""
        if cls._instance is None:
            with cls._lock:
                # Double-check locking pattern
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    # Initialize the service
                    kms_key_id = os.getenv("KMS_KEY_ID", "alias/haven-health-passport")
                    region = os.getenv("AWS_REGION", "us-east-1")
                    cls._instance._service = EncryptionService(kms_key_id, region)
        return cls._instance

    def get_service(self) -> EncryptionService:
        """Get the encryption service instance."""
        return self._service


def get_encryption_service() -> EncryptionService:
    """Get the thread-safe encryption service instance."""
    singleton = EncryptionServiceSingleton()
    return singleton.get_service()


@require_phi_access(AccessLevel.WRITE)
@audit_phi_access("encrypt_pii")
def encrypt_pii(data: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Encrypt PII data using the thread-safe encryption service.

    Args:
        data: PII data to encrypt (string)
        context: Optional encryption context

    Returns:
        Encrypted data envelope
    """
    service = get_encryption_service()

    # Convert string to bytes
    data_bytes = data.encode("utf-8")

    # Run async encryption in sync context
    # Use get_event_loop() for better compatibility
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        # No event loop in current thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    return loop.run_until_complete(service.encrypt(data_bytes, context))


@require_phi_access(AccessLevel.READ)
@audit_phi_access("decrypt_pii")
def decrypt_pii(
    encrypted_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None
) -> str:
    """
    Decrypt PII data using the thread-safe encryption service.

    Args:
        encrypted_data: Encrypted data envelope
        context: Optional encryption context

    Returns:
        Decrypted PII data (string)
    """
    service = get_encryption_service()

    # Run async decryption in sync context
    # Use get_event_loop() for better compatibility
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        # No event loop in current thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    decrypted_bytes = loop.run_until_complete(service.decrypt(encrypted_data, context))
    return decrypted_bytes.decode("utf-8")
