"""Encryption utilities for sensitive data using AES-256.

Note: This module handles PHI-related encryption operations.
- Access Control: Implement strict access control for encryption/decryption operations and key management
"""

import base64
import hashlib
import os
from typing import Any, Dict, Optional

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from src.config import get_settings
from src.utils.logging import get_logger


class EncryptionService:
    """Service for encrypting and decrypting sensitive data using AES-256."""

    def __init__(self) -> None:
        """Initialize encryption service."""
        settings = get_settings()
        self.encryption_key = settings.encryption_key.encode()
        self._key: Optional[bytes] = None
        self._key_rotation_manager = KeyRotationManager()
        # Generate a unique salt for this instance
        self._salt = os.urandom(16)  # 128-bit salt

    @property
    def key(self) -> bytes:
        """Get or derive the encryption key."""
        if not self._key:
            # Derive a 256-bit key from the configured key
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,  # 256 bits
                salt=self._salt,  # Use instance-specific salt
                iterations=100000,
                backend=default_backend(),
            )
            self._key = kdf.derive(self.encryption_key)
        return self._key

    def encrypt(self, data: str) -> str:
        """Encrypt a string using AES-256-GCM."""
        if not data:
            return data

        # Generate a random 96-bit IV for GCM
        iv = os.urandom(12)

        # Create cipher
        cipher = Cipher(
            algorithms.AES(self.key), modes.GCM(iv), backend=default_backend()
        )
        encryptor = cipher.encryptor()

        # Encrypt the data
        ciphertext = encryptor.update(data.encode()) + encryptor.finalize()

        # Combine IV + tag + ciphertext
        result = iv + encryptor.tag + ciphertext

        # Return base64 encoded
        return base64.urlsafe_b64encode(result).decode()

    def decrypt(self, encrypted_data: str) -> str:
        """Decrypt a string encrypted with AES-256-GCM."""
        if not encrypted_data:
            return encrypted_data

        # Decode from base64
        data = base64.urlsafe_b64decode(encrypted_data.encode())

        # Extract components
        iv = data[:12]
        tag = data[12:28]
        ciphertext = data[28:]

        # Create cipher
        cipher = Cipher(
            algorithms.AES(self.key), modes.GCM(iv, tag), backend=default_backend()
        )
        decryptor = cipher.decryptor()

        # Decrypt
        plaintext = decryptor.update(ciphertext) + decryptor.finalize()

        return plaintext.decode()

    def encrypt_dict(self, data: Dict[str, Any], fields: list[str]) -> Dict[str, Any]:
        """Encrypt specific fields in a dictionary."""
        result = data.copy()
        for field in fields:
            if field in result and result[field]:
                result[field] = self.encrypt(str(result[field]))
        return result

    def decrypt_dict(self, data: Dict[str, Any], fields: list[str]) -> Dict[str, Any]:
        """Decrypt specific fields in a dictionary."""
        result = data.copy()
        for field in fields:
            if field in result and result[field]:
                try:
                    result[field] = self.decrypt(result[field])
                except (ValueError, TypeError):
                    # If decryption fails, leave the field as is
                    pass
        return result

    def generate_key(self) -> str:
        """Generate a new AES-256 encryption key."""
        return base64.urlsafe_b64encode(os.urandom(32)).decode()

    def hash_value(self, value: str) -> str:
        """Create a one-way hash of a value."""
        return hashlib.sha256(value.encode()).hexdigest()

    def rotate_key(self, old_key: bytes, new_key: bytes, data: str) -> str:
        """Rotate encryption key for existing data."""
        # Store old key temporarily
        old_service_key = self._key

        # Decrypt with old key
        self._key = old_key
        decrypted = self.decrypt(data)

        # Encrypt with new key
        self._key = new_key
        encrypted = self.encrypt(decrypted)

        # Restore current key
        self._key = old_service_key

        # Log key rotation
        self._audit_key_usage("key_rotation", {"data_size": len(data)})

        return encrypted

    def _audit_key_usage(self, operation: str, metadata: Dict[str, Any]) -> None:
        """Audit log for key usage."""
        logger = get_logger(__name__)
        logger.info(f"Encryption operation: {operation}", extra=metadata)


class KeyRotationManager:
    """Manages encryption key rotation."""

    def __init__(self) -> None:
        """Initialize key rotation manager."""
        self.backup_keys: Dict[str, bytes] = {}
        self.emergency_keys: Dict[str, bytes] = {}

    def add_backup_key(self, key_id: str, key: bytes) -> None:
        """Add a backup key."""
        self.backup_keys[key_id] = key

    def add_emergency_key(self, key_id: str, key: bytes) -> None:
        """Add an emergency access key."""
        self.emergency_keys[key_id] = key

    def get_backup_key(self, key_id: str) -> Optional[bytes]:
        """Get a backup key by ID."""
        return self.backup_keys.get(key_id)

    def get_emergency_key(self, key_id: str) -> Optional[bytes]:
        """Get an emergency key by ID."""
        return self.emergency_keys.get(key_id)


class FieldEncryption:
    """Field-level encryption for sensitive data."""

    # Fields that should always be encrypted
    SENSITIVE_FIELDS = [
        "ssn",
        "social_security_number",
        "passport_number",
        "driver_license",
        "credit_card",
        "bank_account",
        "medical_record_number",
        "unhcr_case_number",
        "biometric_data",
        "genetic_data",
    ]

    def __init__(self) -> None:
        """Initialize field encryption."""
        self.encryption_service = EncryptionService()

    def should_encrypt_field(self, field_name: str) -> bool:
        """Check if a field should be encrypted."""
        field_lower = field_name.lower()
        return any(sensitive in field_lower for sensitive in self.SENSITIVE_FIELDS)

    def encrypt_document(self, document: Dict[str, Any]) -> Dict[str, Any]:
        """Encrypt sensitive fields in a document."""
        result = document.copy()

        for field, value in document.items():
            if self.should_encrypt_field(field) and value:
                result[field] = self.encryption_service.encrypt(str(value))
                result[f"{field}_encrypted"] = True

        return result

    def decrypt_document(self, document: Dict[str, Any]) -> Dict[str, Any]:
        """Decrypt sensitive fields in a document."""
        result = document.copy()

        for field, value in document.items():
            if field.endswith("_encrypted"):
                continue

            if document.get(f"{field}_encrypted") and value:
                try:
                    result[field] = self.encryption_service.decrypt(value)
                    # Remove the encryption flag
                    result.pop(f"{field}_encrypted", None)
                except (ValueError, TypeError):
                    # If decryption fails, leave as is
                    pass

        return result
