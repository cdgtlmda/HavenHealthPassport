"""
Healthcare-specific column encryption configurations.

This module defines encryption settings for different types of
healthcare data fields to ensure HIPAA compliance.
"""

import logging
from enum import Enum
from typing import Any, Dict, Set

from src.healthcare.hipaa_access_control import (
    AccessLevel,
    audit_phi_access,
    require_phi_access,
)
from src.security.encryption import EncryptionService

from .column_encryption import ColumnEncryption

logger = logging.getLogger(__name__)


class FieldSensitivity(Enum):
    """Classification of field sensitivity levels."""

    PUBLIC = "public"  # No encryption needed
    PROTECTED = "protected"  # Basic encryption
    SENSITIVE = "sensitive"  # Strong encryption, no searching
    SEARCHABLE_SENSITIVE = "searchable_sensitive"  # Deterministic encryption


class HealthcareFieldEncryption:
    """Manages encryption settings for healthcare data fields."""

    # Define field sensitivity mappings
    FIELD_CLASSIFICATIONS: Dict[str, Dict[str, FieldSensitivity]] = {
        "patients": {
            # Searchable sensitive fields (deterministic encryption)
            "ssn": FieldSensitivity.SEARCHABLE_SENSITIVE,
            "medical_record_number": FieldSensitivity.SEARCHABLE_SENSITIVE,
            "email": FieldSensitivity.SEARCHABLE_SENSITIVE,
            "phone": FieldSensitivity.SEARCHABLE_SENSITIVE,
            # Non-searchable sensitive fields (randomized encryption)
            "first_name": FieldSensitivity.SENSITIVE,
            "last_name": FieldSensitivity.SENSITIVE,
            "date_of_birth": FieldSensitivity.SENSITIVE,
            "address": FieldSensitivity.SENSITIVE,
            "insurance_id": FieldSensitivity.SENSITIVE,
            # Protected fields
            "gender": FieldSensitivity.PROTECTED,
            "blood_type": FieldSensitivity.PROTECTED,
            # Public fields
            "patient_id": FieldSensitivity.PUBLIC,
            "created_at": FieldSensitivity.PUBLIC,
            "updated_at": FieldSensitivity.PUBLIC,
        },
        "medical_records": {
            # Sensitive fields
            "diagnosis": FieldSensitivity.SENSITIVE,
            "treatment": FieldSensitivity.SENSITIVE,
            "notes": FieldSensitivity.SENSITIVE,
            "lab_results": FieldSensitivity.SENSITIVE,
            "medications": FieldSensitivity.SENSITIVE,
            "allergies": FieldSensitivity.SENSITIVE,
            # Searchable sensitive
            "record_number": FieldSensitivity.SEARCHABLE_SENSITIVE,
            "patient_id": FieldSensitivity.SEARCHABLE_SENSITIVE,
            # Protected fields
            "record_type": FieldSensitivity.PROTECTED,
            "department": FieldSensitivity.PROTECTED,
            # Public fields
            "created_at": FieldSensitivity.PUBLIC,
            "updated_at": FieldSensitivity.PUBLIC,
        },
        "test_results": {
            # Sensitive fields
            "result_value": FieldSensitivity.SENSITIVE,
            "result_text": FieldSensitivity.SENSITIVE,
            "abnormal_flags": FieldSensitivity.SENSITIVE,
            "reference_range": FieldSensitivity.SENSITIVE,
            # Searchable sensitive
            "test_code": FieldSensitivity.SEARCHABLE_SENSITIVE,
            "patient_id": FieldSensitivity.SEARCHABLE_SENSITIVE,
            # Protected fields
            "test_name": FieldSensitivity.PROTECTED,
            "unit": FieldSensitivity.PROTECTED,
            # Public fields
            "test_date": FieldSensitivity.PUBLIC,
            "lab_id": FieldSensitivity.PUBLIC,
        },
    }

    def __init__(self, kms_key_id: str, region: str = "us-east-1"):
        """Initialize healthcare field encryption handler."""
        self.kms_key_id = kms_key_id
        self.region = region
        self._encryptors: Dict[str, ColumnEncryption] = {}
        self._encryption_service = EncryptionService(kms_key_id, region)

    @require_phi_access(AccessLevel.READ)
    @audit_phi_access("get_encryptor")
    def get_encryptor(self, table_name: str) -> ColumnEncryption:
        """Get or create an encryptor for a specific table."""
        self._encryption_service = EncryptionService(self.kms_key_id, self.region)
        if table_name not in self._encryptors:
            self._encryptors[table_name] = ColumnEncryption(
                self.kms_key_id, table_name, self.region
            )
        return self._encryptors[table_name]

    @require_phi_access(AccessLevel.READ)
    @audit_phi_access("encrypt_row")
    def encrypt_row(self, table_name: str, row_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Encrypt a row of data based on field classifications.

        Args:
            table_name: Name of the database table
            row_data: Dictionary of field values

        Returns:
            Dictionary with encrypted values
        """
        if table_name not in self.FIELD_CLASSIFICATIONS:
            logger.warning("No encryption config for table: %s", table_name)
            return row_data

        encryptor = self.get_encryptor(table_name)
        encrypted_row = {}
        field_config = self.FIELD_CLASSIFICATIONS[table_name]

        for field_name, value in row_data.items():
            sensitivity = field_config.get(field_name, FieldSensitivity.PUBLIC)

            if sensitivity == FieldSensitivity.PUBLIC:
                encrypted_row[field_name] = value
            elif sensitivity == FieldSensitivity.PROTECTED:
                encrypted_row[field_name] = encryptor.encrypt_value(
                    value, field_name, deterministic=False
                )
            elif sensitivity == FieldSensitivity.SENSITIVE:
                encrypted_row[field_name] = encryptor.encrypt_value(
                    value, field_name, deterministic=False
                )
            elif sensitivity == FieldSensitivity.SEARCHABLE_SENSITIVE:
                encrypted_row[field_name] = encryptor.encrypt_value(
                    value, field_name, deterministic=True
                )

        return encrypted_row

    @require_phi_access(AccessLevel.READ)
    @audit_phi_access("decrypt_row")
    def decrypt_row(
        self, table_name: str, encrypted_row: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Decrypt a row of data based on field classifications.

        Args:
            table_name: Name of the database table
            encrypted_row: Dictionary of encrypted field values

        Returns:
            Dictionary with decrypted values
        """
        if table_name not in self.FIELD_CLASSIFICATIONS:
            logger.warning("No encryption config for table: %s", table_name)
            return encrypted_row

        encryptor = self.get_encryptor(table_name)
        decrypted_row = {}
        field_config = self.FIELD_CLASSIFICATIONS[table_name]

        for field_name, value in encrypted_row.items():
            sensitivity = field_config.get(field_name, FieldSensitivity.PUBLIC)

            if sensitivity == FieldSensitivity.PUBLIC:
                decrypted_row[field_name] = value
            elif sensitivity in [
                FieldSensitivity.PROTECTED,
                FieldSensitivity.SENSITIVE,
            ]:
                decrypted_row[field_name] = encryptor.decrypt_value(
                    value, field_name, deterministic=False
                )
            elif sensitivity == FieldSensitivity.SEARCHABLE_SENSITIVE:
                decrypted_row[field_name] = encryptor.decrypt_value(
                    value, field_name, deterministic=True
                )

        return decrypted_row

    def get_searchable_fields(self, table_name: str) -> Set[str]:
        """Get fields that support searching (deterministic encryption)."""
        if table_name not in self.FIELD_CLASSIFICATIONS:
            return set()

        return {
            field
            for field, sensitivity in self.FIELD_CLASSIFICATIONS[table_name].items()
            if sensitivity == FieldSensitivity.SEARCHABLE_SENSITIVE
        }
