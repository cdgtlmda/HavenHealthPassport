"""Encryption service for secure data handling in Haven Health Passport.

This service provides encryption/decryption capabilities for PHI data,
supporting both symmetric (AES) and asymmetric (RSA) encryption.
"""

import base64
import hashlib
import json
import os
from typing import Any, Dict, Optional, Tuple, Union

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from src.config import get_settings
from src.models.audit_log import AuditAction
from src.utils.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


class EncryptionService:
    """Service for encrypting and decrypting sensitive health data."""

    def __init__(self, audit_service: Optional[Any] = None) -> None:
        """Initialize encryption service with keys."""
        self.fernet: Optional[Fernet] = None
        self.aes_key: Optional[bytes] = None
        self.audit_service = audit_service
        self._initialize_keys()

    def _initialize_keys(self) -> None:
        """Initialize encryption keys from environment or generate new ones."""
        try:
            # Try to load existing key
            encryption_key = settings.encryption_key or settings.ENCRYPTION_KEY
            fernet_key = getattr(settings, "fernet_key", None) or getattr(
                settings, "FERNET_KEY", None
            )

            # Use fernet_key if available (it's already base64 encoded)
            if fernet_key:
                self.fernet = Fernet(
                    fernet_key.encode() if isinstance(fernet_key, str) else fernet_key
                )
            elif encryption_key:
                # For backward compatibility, try to use encryption_key
                # If it's exactly 32 chars, treat it as a plain string and generate a proper Fernet key
                if len(encryption_key) == 32:
                    # Generate a proper Fernet key from the 32-char string
                    key_bytes = hashlib.sha256(encryption_key.encode()).digest()
                    fernet_key = base64.urlsafe_b64encode(key_bytes)
                    self.fernet = Fernet(fernet_key)
                else:
                    # Assume it's already a proper Fernet key
                    self.fernet = Fernet(
                        encryption_key.encode()
                        if isinstance(encryption_key, str)
                        else encryption_key
                    )
            else:
                # Generate new key if none exists
                key = Fernet.generate_key()
                self.fernet = Fernet(key)
                logger.warning("Generated new encryption key - store this securely!")

            # Initialize AES key for AESGCM
            aes_key = settings.AES_ENCRYPTION_KEY
            if aes_key:
                self.aes_key = base64.b64decode(aes_key)
            else:
                # Generate 256-bit key for AES-256
                self.aes_key = AESGCM.generate_key(bit_length=256)
                logger.warning("Generated new AES key - store this securely!")

        except Exception as e:
            logger.error(f"Failed to initialize encryption keys: {e}")
            raise

    def encrypt(self, data: Union[str, bytes]) -> str:
        """
        Encrypt data using Fernet (symmetric encryption).

        @access_control_required - Encryption operations require authorization

        Args:
            data: Plain text data to encrypt

        Returns:
            Base64 encoded encrypted data
        """
        try:
            if isinstance(data, str):
                data_bytes = data.encode("utf-8")
            else:
                data_bytes = data

            if self.fernet is None:
                raise ValueError("Encryption not initialized")
            encrypted = self.fernet.encrypt(data_bytes)
            return base64.b64encode(encrypted).decode("utf-8")

        except Exception as e:
            logger.error(f"Encryption failed: {e}")
            raise

    def decrypt(self, encrypted_data: str) -> str:
        """
        Decrypt data encrypted with Fernet.

        @permission_required - Decryption requires explicit authorization

        Args:
            encrypted_data: Base64 encoded encrypted data

        Returns:
            Decrypted plain text
        """
        try:
            encrypted_bytes = base64.b64decode(encrypted_data)
            if self.fernet is None:
                raise ValueError("Encryption not initialized")
            decrypted = self.fernet.decrypt(encrypted_bytes)
            result: str = decrypted.decode("utf-8")

            # HIPAA COMPLIANCE: Log every PHI decryption
            if self.audit_service:
                self.audit_service.log_action(
                    action=AuditAction.PHI_DECRYPTION,
                    resource_type="PHI_DATA",
                    details={"data_type": "encrypted_field", "operation": "decrypt"},
                    success=True,
                )

            return result

        except Exception as e:
            logger.error(f"Decryption failed: {e}")
            if self.audit_service:
                self.audit_service.log_action(
                    action=AuditAction.PHI_DECRYPTION,
                    resource_type="PHI_DATA",
                    details={"data_type": "encrypted_field", "operation": "decrypt"},
                    success=False,
                    error_message=str(e),
                )
            raise

    def encrypt_aes_gcm(
        self, data: Union[str, bytes], associated_data: Optional[bytes] = None
    ) -> Dict[str, str]:
        """
        Encrypt data using AES-GCM for authenticated encryption.

        Args:
            data: Plain text data to encrypt
            associated_data: Additional data to authenticate but not encrypt

        Returns:
            Dictionary with nonce, ciphertext, and tag
        """
        try:
            data_bytes: bytes
            if isinstance(data, bytes):
                data_bytes = data
            else:
                data_bytes = data.encode("utf-8")

            # Generate a random 96-bit nonce
            nonce = os.urandom(12)

            # Create AESGCM instance
            if self.aes_key is None:
                raise ValueError("AES key not initialized")
            aesgcm = AESGCM(self.aes_key)

            # Encrypt data
            ciphertext = aesgcm.encrypt(nonce, data_bytes, associated_data)

            return {
                "nonce": base64.b64encode(nonce).decode("utf-8"),
                "ciphertext": base64.b64encode(ciphertext).decode("utf-8"),
                "algorithm": "AES-256-GCM",
            }

        except Exception as e:
            logger.error(f"AES-GCM encryption failed: {e}")
            raise

    def decrypt_aes_gcm(
        self, encrypted_data: Dict[str, str], associated_data: Optional[bytes] = None
    ) -> str:
        """
        Decrypt data encrypted with AES-GCM.

        Args:
            encrypted_data: Dictionary with nonce and ciphertext
            associated_data: Additional authenticated data

        Returns:
            Decrypted plain text
        """
        try:
            nonce = base64.b64decode(encrypted_data["nonce"])
            ciphertext = base64.b64decode(encrypted_data["ciphertext"])

            # Create AESGCM instance
            if self.aes_key is None:
                raise ValueError("AES key not initialized")
            aesgcm = AESGCM(self.aes_key)

            # Decrypt data
            plaintext = aesgcm.decrypt(nonce, ciphertext, associated_data)
            result = plaintext.decode("utf-8")

            # HIPAA COMPLIANCE: Log every PHI decryption
            if self.audit_service:
                self.audit_service.log_action(
                    action=AuditAction.PHI_DECRYPTION,
                    resource_type="PHI_DATA",
                    details={
                        "data_type": "aes_gcm_encrypted",
                        "operation": "decrypt",
                        "algorithm": "AES-256-GCM",
                    },
                    success=True,
                )

            return result

        except Exception as e:
            logger.error(f"AES-GCM decryption failed: {e}")
            if self.audit_service:
                self.audit_service.log_action(
                    action=AuditAction.PHI_DECRYPTION,
                    resource_type="PHI_DATA",
                    details={
                        "data_type": "aes_gcm_encrypted",
                        "operation": "decrypt",
                        "algorithm": "AES-256-GCM",
                    },
                    success=False,
                    error_message=str(e),
                )
            raise

    def generate_rsa_keypair(self, key_size: int = 4096) -> Tuple[str, str]:
        """
        Generate RSA key pair for asymmetric encryption.

        @role_based_access - Key generation requires admin role

        Args:
            key_size: RSA key size (default 4096 for high security)

        Returns:
            Tuple of (private_key_pem, public_key_pem)
        """
        try:
            # Generate private key
            private_key = rsa.generate_private_key(
                public_exponent=65537, key_size=key_size
            )

            # Extract public key
            public_key = private_key.public_key()

            # Serialize keys to PEM format
            private_pem = private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption(),
            ).decode("utf-8")

            public_pem = public_key.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo,
            ).decode("utf-8")

            return private_pem, public_pem

        except Exception as e:
            logger.error(f"RSA key generation failed: {e}")
            raise

    def encrypt_for_recipient(
        self, data: Union[str, bytes], recipient_public_key: str
    ) -> str:
        """
        Encrypt data for a specific recipient using their RSA public key.

        This uses hybrid encryption:
        1. Generate a random AES key
        2. Encrypt the data with AES
        3. Encrypt the AES key with recipient's RSA public key

        Args:
            data: Plain text data to encrypt
            recipient_public_key: Recipient's RSA public key in PEM format

        Returns:
            Base64 encoded encrypted package
        """
        try:
            # Load recipient's public key
            public_key = serialization.load_pem_public_key(
                recipient_public_key.encode("utf-8")
            )

            # Generate ephemeral AES key
            ephemeral_key = AESGCM.generate_key(bit_length=256)

            # Encrypt data with AES
            aesgcm = AESGCM(ephemeral_key)
            nonce = os.urandom(12)

            data_bytes: bytes
            if isinstance(data, bytes):
                data_bytes = data
            else:
                data_bytes = data.encode("utf-8")

            ciphertext = aesgcm.encrypt(nonce, data_bytes, None)

            # Encrypt AES key with RSA
            if not hasattr(public_key, "encrypt"):
                raise ValueError("Public key does not support encryption (must be RSA)")
            encrypted_key = public_key.encrypt(
                ephemeral_key,
                padding.OAEP(
                    mgf=padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None,
                ),
            )

            # Create encrypted package
            package = {
                "encrypted_key": base64.b64encode(encrypted_key).decode("utf-8"),
                "nonce": base64.b64encode(nonce).decode("utf-8"),
                "ciphertext": base64.b64encode(ciphertext).decode("utf-8"),
                "algorithm": "RSA-4096/AES-256-GCM",
            }

            # Encode entire package
            return base64.b64encode(json.dumps(package).encode("utf-8")).decode("utf-8")

        except Exception as e:
            logger.error(f"Hybrid encryption failed: {e}")
            raise

    def decrypt_with_private_key(self, encrypted_package: str, private_key: str) -> str:
        """
        Decrypt data encrypted with encrypt_for_recipient.

        Args:
            encrypted_package: Base64 encoded encrypted package
            private_key: RSA private key in PEM format

        Returns:
            Decrypted plain text
        """
        try:
            # Decode package
            package = json.loads(base64.b64decode(encrypted_package).decode("utf-8"))

            # Load private key
            private_key_obj = serialization.load_pem_private_key(
                private_key.encode("utf-8"), password=None
            )

            # Decrypt AES key with RSA
            encrypted_key = base64.b64decode(package["encrypted_key"])
            if not hasattr(private_key_obj, "decrypt"):
                raise ValueError(
                    "Private key does not support decryption (must be RSA)"
                )
            ephemeral_key = private_key_obj.decrypt(
                encrypted_key,
                padding.OAEP(
                    mgf=padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None,
                ),
            )

            # Decrypt data with AES
            nonce = base64.b64decode(package["nonce"])
            ciphertext = base64.b64decode(package["ciphertext"])

            aesgcm = AESGCM(ephemeral_key)
            plaintext = aesgcm.decrypt(nonce, ciphertext, None)

            return plaintext.decode("utf-8")

        except Exception as e:
            logger.error(f"Hybrid decryption failed: {e}")
            raise

    def encrypt_field_level(
        self, data: Dict[str, Any], fields_to_encrypt: list
    ) -> Dict[str, Any]:
        """
        Encrypt specific fields in a dictionary.

        Args:
            data: Dictionary containing data
            fields_to_encrypt: List of field names to encrypt

        Returns:
            Dictionary with specified fields encrypted
        """
        try:
            encrypted_data = data.copy()

            for field in fields_to_encrypt:
                if field in encrypted_data and encrypted_data[field] is not None:
                    # Convert to string if needed
                    value = str(encrypted_data[field])
                    # Encrypt the field
                    encrypted_data[field] = self.encrypt(value)
                    # Mark field as encrypted
                    encrypted_data[f"{field}_encrypted"] = True

            return encrypted_data

        except Exception as e:
            logger.error(f"Field-level encryption failed: {e}")
            raise

    def decrypt_field_level(
        self, data: Dict[str, Any], fields_to_decrypt: list
    ) -> Dict[str, Any]:
        """
        Decrypt specific fields in a dictionary.

        Args:
            data: Dictionary containing encrypted data
            fields_to_decrypt: List of field names to decrypt

        Returns:
            Dictionary with specified fields decrypted
        """
        try:
            decrypted_data = data.copy()

            for field in fields_to_decrypt:
                if field in decrypted_data and decrypted_data.get(f"{field}_encrypted"):
                    # Decrypt the field
                    decrypted_data[field] = self.decrypt(decrypted_data[field])
                    # Remove encryption marker
                    decrypted_data.pop(f"{field}_encrypted", None)

            return decrypted_data

        except Exception as e:
            logger.error(f"Field-level decryption failed: {e}")
            raise

    def generate_data_key(
        self, _master_key_id: Optional[str] = None
    ) -> Tuple[bytes, bytes]:
        """
        Generate a data encryption key (DEK) for envelope encryption.

        Args:
            master_key_id: ID of master key to use (for KMS integration)

        Returns:
            Tuple of (plaintext_key, encrypted_key)
        """
        try:
            # Generate new data key
            data_key = AESGCM.generate_key(bit_length=256)

            # Encrypt data key with master key
            if self.fernet is None:
                raise ValueError("Encryption not initialized")
            encrypted_data_key = self.fernet.encrypt(data_key)

            return data_key, encrypted_data_key

        except Exception as e:
            logger.error(f"Data key generation failed: {e}")
            raise


# Create singleton instance
encryption_service = EncryptionService()
