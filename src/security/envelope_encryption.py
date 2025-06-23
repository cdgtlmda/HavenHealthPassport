"""
Envelope Encryption Implementation for Haven Health Passport.

This module provides envelope encryption functionality using AWS KMS.
Envelope encryption uses a data encryption key (DEK) to encrypt data,
and then encrypts the DEK with a KMS key (KEK).
"""

import base64
import logging
from typing import Any, Dict, Optional, Tuple

import boto3
from botocore.exceptions import ClientError
from cryptography.exceptions import InvalidTag as InvalidToken
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

logger = logging.getLogger(__name__)


class EnvelopeEncryption:
    """
    Implements envelope encryption using AWS KMS.

    This class provides methods to encrypt and decrypt data using
    envelope encryption pattern with AWS KMS.
    """

    def __init__(self, kms_key_id: str, region: str = "us-east-1"):
        """
        Initialize the envelope encryption handler.

        Args:
            kms_key_id: The KMS key ID or ARN to use for encryption
            region: AWS region where the KMS key is located
        """
        self.kms_key_id = kms_key_id
        self.kms_client = boto3.client("kms", region_name=region)
        self.backend = default_backend()

    def generate_data_key(
        self, encryption_context: Optional[Dict[str, str]] = None
    ) -> Tuple[bytes, bytes]:
        """
        Generate a data encryption key (DEK) using KMS.

        Args:
            encryption_context: Optional encryption context for additional security

        Returns:
            Tuple of (plaintext_key, encrypted_key)
        """
        try:
            params: Dict[str, Any] = {"KeyId": self.kms_key_id, "KeySpec": "AES_256"}

            if encryption_context:
                params["EncryptionContext"] = encryption_context

            response = self.kms_client.generate_data_key(**params)

            return response["Plaintext"], response["CiphertextBlob"]

        except ClientError as e:
            logger.error("Error generating data key: %s", e)
            raise

    def encrypt_data(
        self, plaintext: bytes, encryption_context: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Encrypt data using envelope encryption.

        Args:
            plaintext: The data to encrypt
            encryption_context: Optional encryption context

        Returns:
            Dictionary containing encrypted data and metadata
        """
        # Generate a new data encryption key
        dek_plaintext, dek_encrypted = self.generate_data_key(encryption_context)

        # Generate a random IV for AES-GCM (96 bits for GCM)
        iv = self.kms_client.generate_random(NumberOfBytes=12)["Plaintext"]

        # GCM mode doesn't require padding
        # Encrypt the data with AES-256-GCM
        cipher = Cipher(
            algorithms.AES(dek_plaintext), modes.GCM(iv), backend=self.backend
        )
        encryptor = cipher.encryptor()
        ciphertext = encryptor.update(plaintext) + encryptor.finalize()

        # Get the authentication tag
        tag = encryptor.tag

        # Note: In production, use secure memory clearing techniques
        # to clear the plaintext DEK from memory

        # Return the encrypted envelope
        return {
            "ciphertext": base64.b64encode(ciphertext).decode("utf-8"),
            "encrypted_data_key": base64.b64encode(dek_encrypted).decode("utf-8"),
            "iv": base64.b64encode(iv).decode("utf-8"),
            "tag": base64.b64encode(tag).decode("utf-8"),
            "encryption_context": encryption_context,
            "algorithm": "AES-256-GCM",
        }

    def decrypt_data(self, encrypted_envelope: Dict[str, Any]) -> bytes:
        """
        Decrypt data that was encrypted using envelope encryption.

        Args:
            encrypted_envelope: The encrypted data envelope

        Returns:
            The decrypted plaintext
        """
        try:
            # Decode the components
            ciphertext = base64.b64decode(encrypted_envelope["ciphertext"])
            encrypted_data_key = base64.b64decode(
                encrypted_envelope["encrypted_data_key"]
            )
            iv = base64.b64decode(encrypted_envelope["iv"])
            tag = base64.b64decode(encrypted_envelope["tag"])
            encryption_context = encrypted_envelope.get("encryption_context")

            # Decrypt the data encryption key
            params = {"CiphertextBlob": encrypted_data_key}

            if encryption_context:
                params["EncryptionContext"] = encryption_context

            response = self.kms_client.decrypt(**params)
            dek_plaintext = response["Plaintext"]

            # Decrypt the data with AES-256-GCM
            cipher = Cipher(
                algorithms.AES(dek_plaintext), modes.GCM(iv, tag), backend=self.backend
            )
            decryptor = cipher.decryptor()
            plaintext = decryptor.update(ciphertext) + decryptor.finalize()

            # Clear the plaintext DEK from memory
            dek_plaintext = None

            return plaintext

        except ClientError as e:
            logger.error("Error decrypting data: %s", e)
            raise
        except (InvalidToken, TypeError, ValueError) as e:
            logger.error("Unexpected error during decryption: %s", e)
            raise

    def encrypt_string(
        self, plaintext: str, encryption_context: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Encrypt a string using envelope encryption.

        Args:
            plaintext: String to encrypt
            encryption_context: Optional encryption context

        Returns:
            Encrypted envelope
        """
        return self.encrypt_data(plaintext.encode("utf-8"), encryption_context)

    def decrypt_string(self, encrypted_envelope: Dict[str, Any]) -> str:
        """
        Decrypt a string from an encrypted envelope.

        Args:
            encrypted_envelope: The encrypted data envelope

        Returns:
            Decrypted string
        """
        return self.decrypt_data(encrypted_envelope).decode("utf-8")
