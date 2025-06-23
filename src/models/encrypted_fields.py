"""Encrypted field types for SQLAlchemy models.

This module provides encrypted field types for storing PHI data securely.
Handles encryption for FHIR Resource data stored in the database.
All PHI data is encrypted and access is controlled through role-based permissions.
"""

import base64
import hashlib
import json
from datetime import datetime
from typing import Any, Optional, Type

from cryptography.fernet import InvalidToken
from sqlalchemy import Text, TypeDecorator
from sqlalchemy.ext.mutable import MutableDict, MutableList

from src.healthcare.fhir_validator import FHIRValidator
from src.services.encryption_service import EncryptionService
from src.utils.logging import get_logger

# FHIR resource type for this module
__fhir_resource__ = "Binary"  # Encrypted data is stored as Binary resources

logger = get_logger(__name__)

# Initialize validator for encrypted FHIR data
validator = FHIRValidator()


class EncryptedType(TypeDecorator):
    """Base type for encrypted database fields."""

    impl = Text
    cache_ok = True

    def __init__(
        self,
        *args: Any,
        encryption_service: Optional[EncryptionService] = None,
        **kwargs: Any,
    ) -> None:
        """Initialize encrypted type."""
        super().__init__(*args, **kwargs)
        self.encryption_service = encryption_service or EncryptionService()
        self._key_id = None

    @property
    def python_type(self) -> Type[Any]:
        """Return the Python type for this custom type."""
        return str

    def process_literal_param(self, value: Any, dialect: Any) -> Any:
        """Process literal parameter values."""
        return self.process_bind_param(value, dialect)

    def process_bind_param(self, value: Any, dialect: Any) -> Optional[str]:
        """Encrypt value before storing in database."""
        if value is None:
            return None

        try:
            # Convert value to bytes
            if isinstance(value, str):
                data = value.encode("utf-8")
            elif isinstance(value, (dict, list)):
                data = json.dumps(value).encode("utf-8")
            elif isinstance(value, bytes):
                data = value
            else:
                data = str(value).encode("utf-8")

            # Encrypt data
            encrypted_data = self.encryption_service.encrypt(data).encode("utf-8")
            metadata = {"version": "1.0", "algorithm": "Fernet"}

            # Store as base64-encoded JSON
            storage_format = {
                "data": base64.b64encode(encrypted_data).decode(),
                "metadata": metadata,
            }

            return json.dumps(storage_format)

        except (
            InvalidToken,
            OSError,
            TypeError,
            ValueError,
        ) as e:
            logger.error(f"Encryption error: {e}")
            raise

    def process_result_value(self, value: Optional[str], dialect: Any) -> Any:
        """Decrypt value after loading from database."""
        if value is None:
            return None

        try:
            # Parse stored format
            storage_format = json.loads(value)
            encrypted_data = base64.b64decode(storage_format["data"])
            # metadata = storage_format["metadata"]  # Reserved for future use

            # Decrypt data
            decrypted_string = self.encryption_service.decrypt(
                encrypted_data.decode("utf-8")
            )
            decrypted_data = decrypted_string.encode("utf-8")

            # Convert back to original type
            return self._deserialize(decrypted_data)

        except (ValueError, TypeError, AttributeError) as e:
            logger.error(f"Decryption error: {e}")
            # Return None or raise based on policy
            return None

    def _deserialize(self, data: bytes) -> Any:
        """Deserialize decrypted data to original type."""
        return data.decode("utf-8")


class EncryptedString(EncryptedType):
    """Encrypted string field."""

    impl = Text

    @property
    def python_type(self) -> Type[str]:
        """Return the Python type for this custom type."""
        return str

    def process_literal_param(self, value: Any, dialect: Any) -> Any:
        """Process literal parameter values."""
        return self.process_bind_param(value, dialect)

    def _deserialize(self, data: bytes) -> str:
        """Deserialize to string."""
        return data.decode("utf-8")


class EncryptedText(EncryptedType):
    """Encrypted text field for large strings."""

    impl = Text

    @property
    def python_type(self) -> Type[str]:
        """Return the Python type for this custom type."""
        return str

    def process_literal_param(self, value: Any, dialect: Any) -> Any:
        """Process literal parameter values."""
        return self.process_bind_param(value, dialect)

    def _deserialize(self, data: bytes) -> str:
        """Deserialize to string."""
        return data.decode("utf-8")


class EncryptedJSON(EncryptedType):
    """Encrypted JSON field."""

    impl = Text

    @property
    def python_type(self) -> Type[dict]:
        """Return the Python type for this custom type."""
        return dict

    def process_literal_param(self, value: Any, dialect: Any) -> Any:
        """Process literal parameter values."""
        return self.process_bind_param(value, dialect)

    def _deserialize(self, data: bytes) -> Any:
        """Deserialize to JSON object."""
        return json.loads(data.decode("utf-8"))


class EncryptedBinary(EncryptedType):
    """Encrypted binary data field."""

    impl = Text  # Store as Text to maintain compatibility with parent

    @property
    def python_type(self) -> Type[bytes]:
        """Return the Python type for this custom type."""
        return bytes

    def process_literal_param(self, value: Any, dialect: Any) -> Any:
        """Process literal parameter values."""
        return self.process_bind_param(value, dialect)

    def process_bind_param(self, value: Any, dialect: Any) -> Optional[str]:
        """Encrypt binary value before storing."""
        if value is None:
            return None

        try:
            # Ensure we have bytes
            if isinstance(value, str):
                data = value.encode("utf-8")
            else:
                data = bytes(value)

            # Encrypt data
            encrypted_data = self.encryption_service.encrypt(data).encode("utf-8")
            metadata = {"version": "1.0", "algorithm": "Fernet"}

            # Store as base64-encoded JSON like parent class
            storage_format = {
                "data": base64.b64encode(encrypted_data).decode(),
                "metadata": metadata,
            }

            return json.dumps(storage_format)

        except (
            InvalidToken,
            OSError,
            TypeError,
            ValueError,
        ) as e:
            logger.error(f"Binary encryption error: {e}")
            raise

    def process_result_value(
        self, value: Optional[str], dialect: Any
    ) -> Optional[bytes]:
        """Decrypt binary value after loading."""
        if value is None:
            return None

        try:
            # Parse stored format (same as parent class)
            storage_format = json.loads(value)
            encrypted_data = base64.b64decode(storage_format["data"])
            # metadata = storage_format["metadata"]  # Reserved for future use

            # Decrypt data
            decrypted_string = self.encryption_service.decrypt(
                encrypted_data.decode("utf-8")
            )
            # Return as bytes
            return decrypted_string.encode("utf-8")

        except (ValueError, TypeError, KeyError) as e:
            logger.error(f"Binary decryption error: {e}")
            return None

    def _deserialize(self, data: bytes) -> bytes:
        """Return bytes as-is."""
        return data


class EncryptedDateTime(EncryptedType):
    """Encrypted datetime field."""

    impl = Text

    @property
    def python_type(self) -> Type[datetime]:
        """Return the Python type for this custom type."""
        return datetime

    def process_literal_param(self, value: Any, dialect: Any) -> Any:
        """Process literal parameter values."""
        return self.process_bind_param(value, dialect)

    def _deserialize(self, data: bytes) -> Any:
        """Deserialize to datetime."""
        iso_string = data.decode("utf-8")
        return datetime.fromisoformat(iso_string)

    def process_bind_param(self, value: Any, dialect: Any) -> Optional[str]:
        """Convert datetime to ISO format before encryption."""
        if value is None:
            return None

        # Convert datetime to ISO format string
        if isinstance(value, datetime):
            value = value.isoformat()

        return super().process_bind_param(value, dialect)


class SearchableEncrypted(EncryptedType):
    """Encrypted field with deterministic encryption for searching."""

    impl = Text

    @property
    def python_type(self) -> Type[str]:
        """Return the Python type for this custom type."""
        return str

    def process_literal_param(self, value: Any, dialect: Any) -> Any:
        """Process literal parameter values."""
        return self.process_bind_param(value, dialect)

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize with deterministic encryption."""
        super().__init__(*args, **kwargs)
        # Use a deterministic algorithm for searchability
        self.search_algorithm = "FERNET"

    def process_bind_param(self, value: Any, dialect: Any) -> Optional[str]:
        """Encrypt with deterministic algorithm."""
        if value is None:
            return None

        try:
            # For searching, we need deterministic encryption
            # This means same plaintext always produces same ciphertext
            # WARNING: This is less secure than random encryption

            # Convert to string
            search_value = str(value).lower().strip()

            # Create deterministic key based on value
            # In production, use a proper searchable encryption scheme
            value_hash = hashlib.sha256(search_value.encode()).hexdigest()[:32]

            # Store both searchable hash and encrypted value
            storage_format = {
                "search_hash": value_hash,
                "encrypted": super().process_bind_param(value, dialect),
            }

            return json.dumps(storage_format)

        except (
            AttributeError,
            InvalidToken,
            OSError,
            TypeError,
            ValueError,
        ) as e:
            logger.error(f"Searchable encryption error: {e}")
            raise

    def process_result_value(self, value: Optional[str], dialect: Any) -> Any:
        """Decrypt searchable value."""
        if value is None:
            return None

        try:
            storage_format = json.loads(value)
            # Decrypt the actual value, ignore search hash
            return super().process_result_value(storage_format["encrypted"], dialect)
        except (KeyError, json.JSONDecodeError, TypeError) as e:
            logger.error(f"Searchable decryption error: {e}")
            return None


# Mutable encrypted types for JSON fields
class MutableEncryptedDict(MutableDict, EncryptedJSON):
    """Mutable encrypted dictionary field."""

    @property
    def python_type(self) -> Type[dict]:
        """Return the Python type for this custom type."""
        return dict

    def process_literal_param(self, value: Any, dialect: Any) -> Any:
        """Process literal parameter values."""
        return self.process_bind_param(value, dialect)

    def copy(
        self, **kw: Any  # pylint: disable=unused-argument
    ) -> "MutableEncryptedDict":
        """Create a copy of this type."""
        return self.__class__(encryption_service=self.encryption_service)


class MutableEncryptedList(MutableList, EncryptedType):
    """Mutable encrypted list field."""

    impl = Text

    @property
    def python_type(self) -> Type[list]:
        """Return the Python type for this custom type."""
        return list

    def _deserialize(self, data: bytes) -> Any:
        """Deserialize to list."""
        return json.loads(data.decode("utf-8"))

    def process_literal_param(self, value: Any, dialect: Any) -> Any:
        """Process literal parameter values."""
        return self.process_bind_param(value, dialect)

    def copy(self, **kw: Any) -> "MutableEncryptedList":
        """Create a copy of this type."""
        # Create a new instance with all kwargs including encryption_service
        kw["encryption_service"] = self.encryption_service
        return type(self)(**kw)


# Factory functions for creating encrypted fields
def create_encrypted_field(
    field_type: Type[TypeDecorator],
    encryption_service: Optional[EncryptionService] = None,
    **kwargs: Any,
) -> TypeDecorator:
    """
    Create an encrypted field with custom encryption service.

    Args:
        field_type: Type of encrypted field
        encryption_service: Custom encryption service
        **kwargs: Additional field arguments

    Returns:
        Configured encrypted field
    """
    return field_type(encryption_service=encryption_service, **kwargs)


# Commonly used encrypted field configurations
def EncryptedEmail() -> TypeDecorator:
    """Create an encrypted email field with searchable capabilities."""
    return create_encrypted_field(SearchableEncrypted)


def EncryptedPhone() -> TypeDecorator:
    """Create an encrypted phone number field."""
    return create_encrypted_field(EncryptedString)


def EncryptedSSN() -> TypeDecorator:
    """Create an encrypted SSN field."""
    return create_encrypted_field(EncryptedString)


def EncryptedAddress() -> TypeDecorator:
    """Create an encrypted address field."""
    return create_encrypted_field(EncryptedJSON)


def EncryptedMedicalNotes() -> TypeDecorator:
    """Create an encrypted medical notes field."""
    return create_encrypted_field(EncryptedText)


def EncryptedDiagnosis() -> TypeDecorator:
    """Create an encrypted diagnosis field."""
    return create_encrypted_field(EncryptedJSON)


def EncryptedMedication() -> TypeDecorator:
    """Create an encrypted medication field."""
    return create_encrypted_field(EncryptedJSON)


# Utility functions for bulk encryption operations
def encrypt_existing_field(
    model_class: Any,
    field_name: str,
    encryption_service: EncryptionService,
    session: Any,
    batch_size: int = 100,
) -> int:
    """
    Encrypt existing unencrypted field data.

    Args:
        model_class: SQLAlchemy model class
        field_name: Field to encrypt
        encryption_service: Encryption service
        session: Database session
        batch_size: Batch size for processing

    Returns:
        Number of records encrypted
    """
    # Note: encryption_service parameter is kept for API compatibility
    # but the actual encryption is handled by the field's setter
    _ = encryption_service  # Mark as intentionally unused
    encrypted_count = 0

    try:
        # Get records in batches
        offset = 0
        while True:
            records = session.query(model_class).limit(batch_size).offset(offset).all()
            if not records:
                break

            for record in records:
                # Get current value
                current_value = getattr(record, field_name)
                if current_value is not None:
                    # Encrypt and update
                    # The field's setter will handle encryption
                    setattr(record, field_name, current_value)
                    encrypted_count += 1

            session.commit()
            offset += batch_size

            logger.info(f"Encrypted {encrypted_count} records")

        return encrypted_count

    except (InvalidToken, ValueError) as e:
        logger.error(f"Bulk encryption error: {e}")
        session.rollback()
        raise


def rotate_field_encryption(
    model_class: Any,
    field_name: str,
    old_service: EncryptionService,
    new_service: EncryptionService,
    session: Any,
    batch_size: int = 100,
) -> int:
    """
    Rotate encryption keys for a field.

    Args:
        model_class: SQLAlchemy model class
        field_name: Field to rotate
        old_service: Old encryption service
        new_service: New encryption service
        session: Database session
        batch_size: Batch size for processing

    Returns:
        Number of records rotated
    """
    rotated_count = 0

    try:
        # Temporarily set the field to use old service for decryption
        field = getattr(model_class, field_name).property.columns[0].type
        original_service = field.encryption_service
        field.encryption_service = old_service

        offset = 0
        while True:
            records = session.query(model_class).limit(batch_size).offset(offset).all()
            if not records:
                break

            # Switch to new service for encryption
            field.encryption_service = new_service

            for record in records:
                # Get decrypted value (using old service)
                field.encryption_service = old_service
                current_value = getattr(record, field_name)

                if current_value is not None:
                    # Re-encrypt with new service
                    field.encryption_service = new_service
                    setattr(record, field_name, current_value)
                    rotated_count += 1

            session.commit()
            offset += batch_size

            logger.info(f"Rotated encryption for {rotated_count} records")

        # Restore original service
        field.encryption_service = original_service

        return rotated_count

    except (InvalidToken, ValueError) as e:
        logger.error(f"Key rotation error: {e}")
        session.rollback()
        raise
