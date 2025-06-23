"""
Column-level Encryption for Haven Health Passport.

This module provides column-level encryption for sensitive database fields
using AWS KMS and field-level encryption techniques.
"""

import base64
import json
import logging
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Optional

import boto3
from botocore.exceptions import ClientError
from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

logger = logging.getLogger(__name__)


class ColumnEncryption:
    """
    Provides column-level encryption for database fields.

    This class implements deterministic and randomized encryption
    for different use cases (searchable vs non-searchable fields).
    """

    def __init__(self, kms_key_id: str, table_name: str, region: str = "us-east-1"):
        """
        Initialize column encryption handler.

        Args:
            kms_key_id: KMS key ID for data key generation
            table_name: Database table name (used for context)
            region: AWS region
        """
        self.kms_key_id = kms_key_id
        self.table_name = table_name
        self.kms_client = boto3.client("kms", region_name=region)
        self._data_key_cache: dict[str, bytes] = {}

    def _get_or_create_data_key(
        self, column_name: str, deterministic: bool = False
    ) -> bytes:
        """
        Get or create a data key for a specific column.

        Args:
            column_name: Name of the column
            deterministic: Whether to use deterministic encryption

        Returns:
            Data encryption key
        """
        cache_key = f"{self.table_name}:{column_name}:{deterministic}"

        if cache_key in self._data_key_cache:
            return self._data_key_cache[cache_key]

        # Generate encryption context
        encryption_context = {
            "table": self.table_name,
            "column": column_name,
            "type": "deterministic" if deterministic else "randomized",
        }

        try:
            # For deterministic encryption, derive key from a master key
            if deterministic:
                # Get a consistent data key for this column
                response = self.kms_client.generate_data_key_without_plaintext(
                    KeyId=self.kms_key_id,
                    EncryptionContext=encryption_context,
                    KeySpec="AES_256",
                )

                # Derive a deterministic key using PBKDF2
                kdf = PBKDF2HMAC(
                    algorithm=hashes.SHA256(),
                    length=32,
                    salt=f"{self.table_name}:{column_name}".encode(),
                    iterations=100000,
                )
                key = base64.urlsafe_b64encode(
                    kdf.derive(response["CiphertextBlob"][:32])
                )
            else:
                # For randomized encryption, generate a new key each time
                response = self.kms_client.generate_data_key(
                    KeyId=self.kms_key_id,
                    EncryptionContext=encryption_context,
                    KeySpec="AES_256",
                )
                key = base64.urlsafe_b64encode(response["Plaintext"])

            self._data_key_cache[cache_key] = key
            return key

        except ClientError as e:
            logger.error("Error generating data key: %s", e)
            raise

    def encrypt_value(
        self, value: Any, column_name: str, deterministic: bool = False
    ) -> Optional[str]:
        """
        Encrypt a value for storage in database.

        Args:
            value: Value to encrypt
            column_name: Name of the column
            deterministic: Use deterministic encryption (for searchable fields)

        Returns:
            Base64-encoded encrypted value
        """
        if value is None:
            return None

        # Serialize the value
        serialized = self._serialize_value(value)

        # Get encryption key
        key = self._get_or_create_data_key(column_name, deterministic)

        # Create Fernet instance
        fernet = Fernet(key)

        # Encrypt the value
        encrypted = fernet.encrypt(serialized.encode("utf-8"))

        # Return base64-encoded result
        return base64.b64encode(encrypted).decode("utf-8")

    def decrypt_value(
        self,
        encrypted_value: Optional[str],
        column_name: str,
        deterministic: bool = False,
    ) -> Any:
        """
        Decrypt a value from database storage.

        Args:
            encrypted_value: Base64-encoded encrypted value
            column_name: Name of the column
            deterministic: Whether deterministic encryption was used

        Returns:
            Decrypted value
        """
        if encrypted_value is None:
            return None

        try:
            # Decode from base64
            encrypted_bytes = base64.b64decode(encrypted_value)

            # Get decryption key
            key = self._get_or_create_data_key(column_name, deterministic)

            # Create Fernet instance
            fernet = Fernet(key)

            # Decrypt the value
            decrypted = fernet.decrypt(encrypted_bytes)

            # Deserialize and return
            return self._deserialize_value(decrypted.decode("utf-8"))

        except (
            InvalidToken,
            ValueError,
        ) as e:
            logger.error("Error decrypting value: %s", e)
            raise

    def _serialize_value(self, value: Any) -> str:
        """Serialize a value to JSON string."""
        if isinstance(value, (datetime, date)):
            return json.dumps({"_type": "datetime", "value": value.isoformat()})
        elif isinstance(value, Decimal):
            return json.dumps({"_type": "decimal", "value": str(value)})
        else:
            return json.dumps(value)

    def _deserialize_value(self, serialized: str) -> Any:
        """Deserialize a value from JSON string."""
        data = json.loads(serialized)

        if isinstance(data, dict) and "_type" in data:
            if data["_type"] == "datetime":
                return datetime.fromisoformat(data["value"])
            elif data["_type"] == "decimal":
                return Decimal(data["value"])

        return data
