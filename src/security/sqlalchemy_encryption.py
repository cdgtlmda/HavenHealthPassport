"""
SQLAlchemy integration for automatic column encryption.

This module provides SQLAlchemy types and mixins for transparent
column-level encryption in database models.

FHIR Compliance: Encrypted data must be validated for FHIR Resource storage.
PHI Protection: Uses field_encryption for PHI data with AES-256 cipher algorithms.
Access Control: Database access requires proper authorization for PHI field decryption.
"""

import logging
import os
from typing import Any, Optional, cast

from sqlalchemy import String, TypeDecorator

from .healthcare_encryption import FieldSensitivity, HealthcareFieldEncryption

logger = logging.getLogger(__name__)


class EncryptedType(TypeDecorator):
    """SQLAlchemy type for encrypted columns."""

    impl = String
    cache_ok = True

    def __init__(
        self,
        encryptor: HealthcareFieldEncryption,
        table_name: str,
        column_name: str,
        sensitivity: FieldSensitivity,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """
        Initialize encrypted type.

        Args:
            encryptor: Healthcare field encryption instance
            table_name: Name of the database table
            column_name: Name of the column
            sensitivity: Field sensitivity level
        """
        super().__init__(*args, **kwargs)
        self.encryptor = encryptor
        self.table_name = table_name
        self.column_name = column_name
        self.sensitivity = sensitivity
        self.deterministic = sensitivity == FieldSensitivity.SEARCHABLE_SENSITIVE

    @property
    def python_type(self) -> type:
        """Return the Python type object expected to be returned by instances of this type."""
        return str

    def process_literal_param(self, value: Any, dialect: Any) -> str:
        """Receive a literal parameter value to be rendered inline within a statement."""
        if value is None:
            return "NULL"
        result = self.process_bind_param(value, dialect)
        return result if result is not None else ""

    def process_bind_param(self, value: Any, dialect: Any) -> Optional[str]:
        """Encrypt value before storing in database.

        Note: Access control is enforced at the application layer through
        @require_phi_access decorators on methods that use encrypted fields.
        Permission checks ensure only authorized users can write PHI data.
        """
        if value is None:
            return None

        if self.sensitivity == FieldSensitivity.PUBLIC:
            return str(value)

        # Access control validation: PHI encryption requires proper authorization
        # This is enforced by the calling code which must have @require_phi_access
        column_encryptor = self.encryptor.get_encryptor(self.table_name)
        encrypted = column_encryptor.encrypt_value(
            value, self.column_name, self.deterministic
        )
        return str(encrypted) if encrypted is not None else None

    def process_result_value(self, value: Optional[str], dialect: Any) -> Any:
        """Decrypt value when loading from database.

        Note: Access control is enforced at the application layer through
        @require_phi_access decorators on methods that use encrypted fields.
        Role-based access control ensures only authorized users can read PHI data.
        """
        if value is None:
            return None

        if self.sensitivity == FieldSensitivity.PUBLIC:
            return value

        # Access control validation: PHI decryption requires proper authorization
        # This is enforced by the calling code which must have @require_phi_access
        column_encryptor = self.encryptor.get_encryptor(self.table_name)
        return column_encryptor.decrypt_value(
            value, self.column_name, self.deterministic
        )


class EncryptedColumnMixin:
    """Mixin for SQLAlchemy models with encrypted columns.

    Usage:
        class Patient(Base, EncryptedColumnMixin):
            __tablename__ = 'patients'
            __encryptor__ = healthcare_encryptor  # Your HealthcareFieldEncryption instance

            id = Column(Integer, primary_key=True)
            name = encrypted_column('name', FieldSensitivity.PII)
            ssn = encrypted_column('ssn', FieldSensitivity.HIGHLY_SENSITIVE)
    """

    # Class-level encryptor that can be set by applications
    _default_encryptor: Optional[HealthcareFieldEncryption] = None

    @classmethod
    def set_default_encryptor(cls, encryptor: HealthcareFieldEncryption) -> None:
        """Set the default encryptor for all models using this mixin.

        Args:
            encryptor: The HealthcareFieldEncryption instance to use
        """
        cls._default_encryptor = encryptor

    @property
    def __encryptor__(self) -> HealthcareFieldEncryption:
        """Get the encryptor instance.

        This can be overridden in the model class, or a default can be set
        using set_default_encryptor().
        """
        # First check if the class has its own encryptor
        if hasattr(self.__class__, "_encryptor"):
            return cast(
                HealthcareFieldEncryption,
                self.__class__._encryptor,  # pylint: disable=protected-access
            )  # noqa: SLF001

        # Then check for a default encryptor
        if self._default_encryptor:
            return self._default_encryptor

        # If neither is set, raise an informative error
        raise RuntimeError(
            f"No encryptor configured for {self.__class__.__name__}. "
            "Either set __encryptor__ on the class or call "
            "EncryptedColumnMixin.set_default_encryptor() with a "
            "HealthcareFieldEncryption instance."
        )

    @classmethod
    def encrypted_column(
        cls, column_name: str, sensitivity: FieldSensitivity, **kwargs: Any
    ) -> EncryptedType:
        """
        Create an encrypted column.

        Args:
            column_name: Name of the column
            sensitivity: Field sensitivity level
            **kwargs: Additional column arguments

        Returns:
            Encrypted column type
        """
        # Get the encryptor - this will use the class's encryptor if available,
        # otherwise the default encryptor
        if hasattr(cls, "_encryptor"):
            encryptor = cls._encryptor
        elif cls._default_encryptor:
            encryptor = cls._default_encryptor
        else:
            # Create a placeholder that will be resolved when the model is used
            # Get KMS key ID from environment or use a placeholder
            kms_key_id = os.environ.get("KMS_KEY_ID", "placeholder-key-id")
            hfe = HealthcareFieldEncryption(kms_key_id)
            # Use the table name from the model's __tablename__ attribute
            table_name = getattr(cls, "__tablename__", "default")
            encryptor = hfe.get_encryptor(table_name)
            logger.warning(
                "Creating temporary encryptor for %s.%s. "
                "Consider setting a proper encryptor for production use.",
                cls.__name__,
                column_name,
            )

        return EncryptedType(
            encryptor,
            getattr(cls, "__tablename__", cls.__name__.lower()),
            column_name,
            sensitivity,
            **kwargs,
        )
