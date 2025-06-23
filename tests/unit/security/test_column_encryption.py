"""Test Column Encryption Module - comprehensive coverage Required.

HIPAA Compliant - Real AWS KMS encryption operations.
NO MOCKS for AWS KMS functionality per medical compliance requirements.

This tests critical PHI column-level encryption for refugee healthcare data.
MUST achieve comprehensive test coverage for medical compliance.
"""

import os
from datetime import date, datetime
from decimal import Decimal

import pytest
from botocore.exceptions import ClientError, NoCredentialsError
from cryptography.fernet import InvalidToken

from src.security.column_encryption import ColumnEncryption


def check_aws_credentials():
    """Check if AWS credentials are available for real KMS testing."""
    try:
        import boto3

        sts = boto3.client("sts")
        sts.get_caller_identity()
        return True
    except (ClientError, NoCredentialsError):
        return False


@pytest.fixture(scope="session")
def real_kms_key_id():
    """Get real KMS key ID for testing."""
    return os.environ.get("TEST_KMS_KEY_ID", "alias/haven-health-test-key")


@pytest.fixture
def column_encryption(real_kms_key_id):
    """Create ColumnEncryption instance with real AWS KMS."""
    if not check_aws_credentials():
        pytest.skip("AWS credentials not available for real KMS testing")

    return ColumnEncryption(kms_key_id=real_kms_key_id, table_name="test_table")


@pytest.mark.hipaa_required
@pytest.mark.phi_encryption
class TestColumnEncryption:
    """Test column encryption with REAL AWS KMS operations - comprehensive coverage Required."""

    def test_column_encryption_initialization(self, real_kms_key_id):
        """Test ColumnEncryption initialization with real KMS key."""
        if not check_aws_credentials():
            pytest.skip("AWS credentials not available")

        encryption = ColumnEncryption(
            kms_key_id=real_kms_key_id, table_name="test_table"
        )

        assert encryption.kms_key_id == real_kms_key_id
        assert encryption.kms_client is not None
        assert encryption.kms_client.meta.region_name == "us-east-1"  # Default region

    def test_column_encryption_initialization_custom_region(self, real_kms_key_id):
        """Test ColumnEncryption initialization with custom region."""
        if not check_aws_credentials():
            pytest.skip("AWS credentials not available")

        custom_region = "us-west-2"
        encryption = ColumnEncryption(
            kms_key_id=real_kms_key_id, table_name="test_table", region=custom_region
        )

        assert encryption.kms_client.meta.region_name == custom_region
        assert encryption.kms_client.meta.region_name == custom_region

    def test_encrypt_value_string(self, column_encryption):
        """Test encryption of string values."""
        test_value = "John Doe"
        column_name = "patient_name"

        encrypted = column_encryption.encrypt_value(test_value, column_name)

        # Verify encryption
        assert isinstance(encrypted, str)
        assert encrypted != test_value
        assert len(encrypted) > len(test_value)

        # Verify it's base64 encoded
        import base64

        try:
            base64.b64decode(encrypted)
        except Exception:
            pytest.fail("Encrypted value is not valid base64")

    def test_encrypt_value_integer(self, column_encryption):
        """Test encryption of integer values."""
        test_value = 12345
        column_name = "patient_id"

        encrypted = column_encryption.encrypt_value(test_value, column_name)

        # Verify encryption
        assert isinstance(encrypted, str)
        assert encrypted != str(test_value)

    def test_encrypt_value_float(self, column_encryption):
        """Test encryption of float values."""
        test_value = 98.6
        column_name = "temperature"

        encrypted = column_encryption.encrypt_value(test_value, column_name)

        # Verify encryption
        assert isinstance(encrypted, str)
        assert encrypted != str(test_value)

    def test_encrypt_value_decimal(self, column_encryption):
        """Test encryption of Decimal values."""
        test_value = Decimal("123.45")
        column_name = "cost"

        encrypted = column_encryption.encrypt_value(test_value, column_name)

        # Verify encryption
        assert isinstance(encrypted, str)
        assert encrypted != str(test_value)

    def test_encrypt_value_date(self, column_encryption):
        """Test encryption of date values."""
        test_value = date(2024, 1, 15)
        column_name = "birth_date"

        encrypted = column_encryption.encrypt_value(test_value, column_name)

        # Verify encryption
        assert isinstance(encrypted, str)
        assert encrypted != str(test_value)

    def test_encrypt_value_datetime(self, column_encryption):
        """Test encryption of datetime values."""
        test_value = datetime(2024, 1, 15, 10, 30, 0)
        column_name = "appointment_time"

        encrypted = column_encryption.encrypt_value(test_value, column_name)

        # Verify encryption
        assert isinstance(encrypted, str)
        assert encrypted != str(test_value)

    def test_encrypt_value_boolean(self, column_encryption):
        """Test encryption of boolean values."""
        test_value = True
        column_name = "is_active"

        encrypted = column_encryption.encrypt_value(test_value, column_name)

        # Verify encryption
        assert isinstance(encrypted, str)
        assert encrypted != str(test_value)

    def test_encrypt_value_none(self, column_encryption):
        """Test encryption of None values."""
        test_value = None
        column_name = "optional_field"

        encrypted = column_encryption.encrypt_value(test_value, column_name)

        # Verify encryption
        assert isinstance(encrypted, str)
        assert encrypted != str(test_value)

    def test_decrypt_value_string(self, column_encryption):
        """Test decryption of string values."""
        test_value = "Jane Smith"
        column_name = "patient_name"

        # Encrypt then decrypt
        encrypted = column_encryption.encrypt_value(test_value, column_name)
        decrypted = column_encryption.decrypt_value(encrypted, column_name)

        # Verify decryption
        assert decrypted == test_value
        assert isinstance(decrypted, str)

    def test_decrypt_value_integer(self, column_encryption):
        """Test decryption of integer values."""
        test_value = 67890
        column_name = "patient_id"

        # Encrypt then decrypt
        encrypted = column_encryption.encrypt_value(test_value, column_name)
        decrypted = column_encryption.decrypt_value(encrypted, column_name)

        # Verify decryption
        assert decrypted == test_value
        assert isinstance(decrypted, int)

    def test_decrypt_value_float(self, column_encryption):
        """Test decryption of float values."""
        test_value = 99.2
        column_name = "temperature"

        # Encrypt then decrypt
        encrypted = column_encryption.encrypt_value(test_value, column_name)
        decrypted = column_encryption.decrypt_value(encrypted, column_name)

        # Verify decryption
        assert decrypted == test_value
        assert isinstance(decrypted, float)

    def test_decrypt_value_decimal(self, column_encryption):
        """Test decryption of Decimal values."""
        test_value = Decimal("456.78")
        column_name = "cost"

        # Encrypt then decrypt
        encrypted = column_encryption.encrypt_value(test_value, column_name)
        decrypted = column_encryption.decrypt_value(encrypted, column_name)

        # Verify decryption
        assert decrypted == test_value
        assert isinstance(decrypted, Decimal)

    def test_decrypt_value_date(self, column_encryption):
        """Test decryption of date values."""
        test_value = date(2024, 2, 20)
        column_name = "birth_date"

        # Encrypt then decrypt
        encrypted = column_encryption.encrypt_value(test_value, column_name)
        decrypted = column_encryption.decrypt_value(encrypted, column_name)

        # Verify decryption
        assert decrypted == test_value
        assert isinstance(decrypted, date)

    def test_decrypt_value_datetime(self, column_encryption):
        """Test decryption of datetime values."""
        test_value = datetime(2024, 2, 20, 14, 45, 30)
        column_name = "appointment_time"

        # Encrypt then decrypt
        encrypted = column_encryption.encrypt_value(test_value, column_name)
        decrypted = column_encryption.decrypt_value(encrypted, column_name)

        # Verify decryption
        assert decrypted == test_value
        assert isinstance(decrypted, datetime)

    def test_decrypt_value_boolean(self, column_encryption):
        """Test decryption of boolean values."""
        test_value = False
        column_name = "is_active"

        # Encrypt then decrypt
        encrypted = column_encryption.encrypt_value(test_value, column_name)
        decrypted = column_encryption.decrypt_value(encrypted, column_name)

        # Verify decryption
        assert decrypted == test_value
        assert isinstance(decrypted, bool)

    def test_decrypt_value_none(self, column_encryption):
        """Test decryption of None values."""
        test_value = None
        column_name = "optional_field"

        # Encrypt then decrypt
        encrypted = column_encryption.encrypt_value(test_value, column_name)
        decrypted = column_encryption.decrypt_value(encrypted, column_name)

        # Verify decryption
        assert decrypted == test_value

    def test_decrypt_value_invalid_data(self, column_encryption):
        """Test decryption error handling for invalid data."""
        with pytest.raises((ValueError, InvalidToken)):
            column_encryption.decrypt_value("invalid_encrypted_data", "test_column")

    def test_deterministic_encryption_same_value(self, column_encryption):
        """Test that deterministic encryption produces same result for same value."""
        test_value = "deterministic_test"
        column_name = "ssn"  # SSN should use deterministic encryption

        # Encrypt same value multiple times
        encrypted1 = column_encryption.encrypt_value(
            test_value, column_name, deterministic=True
        )
        encrypted2 = column_encryption.encrypt_value(
            test_value, column_name, deterministic=True
        )

        # Should produce same encrypted value
        assert encrypted1 == encrypted2

    def test_deterministic_encryption_different_values(self, column_encryption):
        """Test that deterministic encryption produces different results for different values."""
        column_name = "ssn"

        # Encrypt different values
        encrypted1 = column_encryption.encrypt_value(
            "123-45-6789", column_name, deterministic=True
        )
        encrypted2 = column_encryption.encrypt_value(
            "987-65-4321", column_name, deterministic=True
        )

        # Should produce different encrypted values
        assert encrypted1 != encrypted2

    def test_non_deterministic_encryption_different_results(self, column_encryption):
        """Test that non-deterministic encryption produces different results each time."""
        test_value = "non_deterministic_test"
        column_name = "notes"

        # Encrypt same value multiple times
        encrypted1 = column_encryption.encrypt_value(
            test_value, column_name, deterministic=False
        )
        encrypted2 = column_encryption.encrypt_value(
            test_value, column_name, deterministic=False
        )

        # Should produce different encrypted values each time
        assert encrypted1 != encrypted2

        # But both should decrypt to same original value
        decrypted1 = column_encryption.decrypt_value(encrypted1, column_name)
        decrypted2 = column_encryption.decrypt_value(encrypted2, column_name)
        assert decrypted1 == decrypted2 == test_value

    def test_encryption_context_usage(self, column_encryption):
        """Test that encryption context is properly used."""
        test_value = "context_test"
        column_name = "test_column"

        # Encrypt with context
        encrypted = column_encryption.encrypt_value(test_value, column_name)

        # Decrypt should work with same context
        decrypted = column_encryption.decrypt_value(encrypted, column_name)
        assert decrypted == test_value

    @pytest.mark.skipif(
        not check_aws_credentials(), reason="AWS credentials not available"
    )
    def test_real_aws_integration_end_to_end(self, real_kms_key_id):
        """Test complete end-to-end encryption with real AWS KMS."""
        encryption = ColumnEncryption(
            kms_key_id=real_kms_key_id, table_name="test_table"
        )

        # Test various data types
        test_cases = [
            ("John Doe", "patient_name", str),
            (12345, "patient_id", int),
            (98.6, "temperature", float),
            (Decimal("123.45"), "cost", Decimal),
            (date(2024, 1, 15), "birth_date", date),
            (datetime(2024, 1, 15, 10, 30), "appointment_time", datetime),
            (True, "is_active", bool),
            (None, "optional_field", type(None)),
        ]

        for test_value, column_name, expected_type in test_cases:
            # Encrypt
            encrypted = encryption.encrypt_value(test_value, column_name)
            assert isinstance(encrypted, str)
            assert encrypted != str(test_value)

            # Decrypt
            decrypted = encryption.decrypt_value(encrypted, column_name)
            assert decrypted == test_value
            if test_value is not None:
                assert isinstance(decrypted, expected_type)

    @pytest.mark.skipif(
        not check_aws_credentials(), reason="AWS credentials not available"
    )
    def test_kms_error_handling(self, real_kms_key_id):
        """Test KMS error handling with real AWS operations."""
        # Test with invalid KMS key
        invalid_key = "arn:aws:kms:us-east-1:123456789012:key/invalid-key-id"

        with pytest.raises(ClientError):
            encryption = ColumnEncryption(
                kms_key_id=invalid_key, table_name="test_table"
            )
            encryption.encrypt_value("test", "test_column")

    def test_concurrent_encryption_operations(self, column_encryption):
        """Test that concurrent encryption operations work correctly."""
        import threading

        results = {}
        errors = []

        def encrypt_worker(worker_id):
            try:
                test_value = f"worker_{worker_id}_data"
                column_name = f"worker_{worker_id}_column"

                encrypted = column_encryption.encrypt_value(test_value, column_name)
                decrypted = column_encryption.decrypt_value(encrypted, column_name)

                results[worker_id] = (test_value, encrypted, decrypted)
            except Exception as e:
                errors.append(f"Worker {worker_id}: {str(e)}")

        # Create multiple threads
        threads = []
        for i in range(5):
            thread = threading.Thread(target=encrypt_worker, args=(i,))
            threads.append(thread)
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        # Verify results
        assert len(errors) == 0, f"Errors occurred: {errors}"
        assert len(results) == 5

        for _worker_id, (original, encrypted, decrypted) in results.items():
            assert decrypted == original
            assert encrypted != original
