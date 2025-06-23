"""Test PHI Protection Module - Medical Compliance.

HIPAA Compliant - Real encryption operations
NO MOCKS for encryption functionality

Tests based on ACTUAL PHIEncryption implementation.
"""

import os

import pytest
from cryptography.fernet import Fernet, InvalidToken

from src.security.phi_protection import PHIEncryption


@pytest.mark.hipaa_required
@pytest.mark.phi_encryption
class TestPHIEncryptionReal:
    """Test PHI encryption with REAL cryptographic operations."""

    def test_phi_encryption_initialization_default(self):
        """Test PHI encryption initialization with default key generation."""
        phi_encryption = PHIEncryption()

        # Verify initialization
        assert hasattr(phi_encryption, "cipher")
        assert phi_encryption.cipher is not None
        assert isinstance(phi_encryption.cipher, Fernet)

    def test_phi_encryption_initialization_with_key(self):
        """Test PHI encryption initialization with provided key."""
        # Generate a test key
        test_key = Fernet.generate_key()
        phi_encryption = PHIEncryption(key=test_key)

        # Verify initialization with provided key
        assert hasattr(phi_encryption, "cipher")
        assert phi_encryption.cipher is not None
        assert isinstance(phi_encryption.cipher, Fernet)

    def test_key_generation_uniqueness(self):
        """Test that generated keys are unique."""
        key1 = PHIEncryption._generate_key()
        key2 = PHIEncryption._generate_key()

        # Keys should be different
        assert key1 != key2
        assert len(key1) == 44  # Fernet key length in base64
        assert len(key2) == 44
        assert isinstance(key1, bytes)
        assert isinstance(key2, bytes)

    def test_key_derivation_from_password(self):
        """Test key derivation from password."""
        password = "test_password_123"

        # Derive key without salt (will generate random salt)
        key1 = PHIEncryption.derive_key_from_password(password)
        key2 = PHIEncryption.derive_key_from_password(password)

        # Keys should be different due to different salts
        assert key1 != key2
        assert len(key1) == 32  # 256-bit key
        assert len(key2) == 32
        assert isinstance(key1, bytes)
        assert isinstance(key2, bytes)

    def test_key_derivation_with_same_salt(self):
        """Test key derivation with same salt produces same key."""
        password = "test_password_123"
        salt = os.urandom(16)

        # Derive keys with same salt
        key1 = PHIEncryption.derive_key_from_password(password, salt)
        key2 = PHIEncryption.derive_key_from_password(password, salt)

        # Keys should be identical with same salt
        assert key1 == key2
        assert len(key1) == 32
        assert isinstance(key1, bytes)

    def test_key_derivation_different_passwords(self):
        """Test key derivation with different passwords."""
        salt = os.urandom(16)

        key1 = PHIEncryption.derive_key_from_password("password1", salt)
        key2 = PHIEncryption.derive_key_from_password("password2", salt)

        # Keys should be different with different passwords
        assert key1 != key2
        assert len(key1) == 32
        assert len(key2) == 32

    def test_encrypt_decrypt_data_string(self):
        """Test encryption and decryption of string data."""
        phi_encryption = PHIEncryption()

        # Test data with PHI (non-real for testing)
        test_data = "Patient Name: John Test, DOB: 1990-01-01, SSN: 000-00-0000"

        # Encrypt the data
        encrypted = phi_encryption.encrypt_data(test_data)
        assert isinstance(encrypted, bytes)
        assert encrypted != test_data.encode()  # Should be encrypted

        # Decrypt the data
        decrypted = phi_encryption.decrypt_data(encrypted)
        assert decrypted == test_data
        assert isinstance(decrypted, str)

    def test_encrypt_decrypt_data_bytes(self):
        """Test encryption and decryption of bytes data."""
        phi_encryption = PHIEncryption()

        test_data = b"Binary PHI data with special chars: \x00\x01\x02"

        encrypted = phi_encryption.encrypt_data(test_data)
        assert isinstance(encrypted, bytes)
        assert encrypted != test_data

        decrypted = phi_encryption.decrypt_data(encrypted)
        # Bytes are decoded to string
        assert decrypted == test_data.decode("utf-8", errors="replace")

    def test_encrypt_decrypt_data_dict(self):
        """Test encryption and decryption of dictionary data."""
        phi_encryption = PHIEncryption()

        test_data = {
            "patient_id": "TEST001",
            "diagnosis": "Test Diagnosis",
            "medications": ["Med1", "Med2"],
        }

        encrypted = phi_encryption.encrypt_data(test_data)
        assert isinstance(encrypted, bytes)

        decrypted = phi_encryption.decrypt_data(encrypted)
        # Dict is converted to string representation
        assert "patient_id" in decrypted
        assert "TEST001" in decrypted
        assert isinstance(decrypted, str)

    def test_encrypt_decrypt_empty_data(self):
        """Test encryption and decryption of empty data."""
        phi_encryption = PHIEncryption()

        test_data = ""

        encrypted = phi_encryption.encrypt_data(test_data)
        decrypted = phi_encryption.decrypt_data(encrypted)

        assert decrypted == test_data

    def test_encrypt_decrypt_unicode_data(self):
        """Test encryption and decryption of unicode data."""
        phi_encryption = PHIEncryption()

        test_data = "Patient notes: Müller, résumé, 北京, 🏥 Medical data"

        encrypted = phi_encryption.encrypt_data(test_data)
        decrypted = phi_encryption.decrypt_data(encrypted)

        assert decrypted == test_data

    def test_encryption_consistency(self):
        """Test that encryption produces different outputs for same input."""
        phi_encryption = PHIEncryption()

        test_data = "Consistent test data for PHI"

        # Multiple encryptions should produce different ciphertexts
        encrypted1 = phi_encryption.encrypt_data(test_data)
        encrypted2 = phi_encryption.encrypt_data(test_data)

        assert encrypted1 != encrypted2  # Different due to randomness

        # But both should decrypt correctly
        assert phi_encryption.decrypt_data(encrypted1) == test_data
        assert phi_encryption.decrypt_data(encrypted2) == test_data

    def test_different_instances_different_keys(self):
        """Test that different PHI encryption instances use different keys."""
        phi1 = PHIEncryption()
        phi2 = PHIEncryption()

        test_data = "Test data for cross-instance verification"

        encrypted1 = phi1.encrypt_data(test_data)
        encrypted2 = phi2.encrypt_data(test_data)

        # Different instances should produce different ciphertexts
        assert encrypted1 != encrypted2

        # Each should decrypt correctly with its own instance
        assert phi1.decrypt_data(encrypted1) == test_data
        assert phi2.decrypt_data(encrypted2) == test_data

        # Cross-decryption should fail (different keys)
        with pytest.raises(InvalidToken):  # Fernet will raise cryptographic error
            phi1.decrypt_data(encrypted2)

        with pytest.raises(InvalidToken):
            phi2.decrypt_data(encrypted1)


class TestPHIAccessControlReal:
    """Test PHI access control with REAL operations."""

    def test_access_control_initialization(self):
        """Test access control initialization."""
        from src.security.phi_protection import PHIAccessControl

        access_control = PHIAccessControl()

        assert hasattr(access_control, "authorized_users")
        assert hasattr(access_control, "access_log")
        assert isinstance(access_control.authorized_users, set)
        assert isinstance(access_control.access_log, list)
        assert len(access_control.authorized_users) == 0
        assert len(access_control.access_log) == 0

    def test_add_authorized_user(self):
        """Test adding authorized users."""
        from src.security.phi_protection import PHIAccessControl

        access_control = PHIAccessControl()

        # Add user with default role
        access_control.add_authorized_user("user1")
        assert ("user1", "viewer") in access_control.authorized_users

        # Add user with specific role
        access_control.add_authorized_user("user2", "admin")
        assert ("user2", "admin") in access_control.authorized_users

        # Check total count
        assert len(access_control.authorized_users) == 2

    def test_check_access_authorized_user(self):
        """Test access check for authorized user."""
        from src.security.phi_protection import PHIAccessControl

        access_control = PHIAccessControl()
        access_control.add_authorized_user("authorized_user", "admin")

        # Check access for authorized user
        has_access = access_control.check_access("authorized_user", "read")
        assert has_access is True

        # Verify access log
        access_log = access_control.get_access_log()
        assert len(access_log) == 1
        assert access_log[0]["user_id"] == "authorized_user"
        assert access_log[0]["operation"] == "read"
        assert access_log[0]["granted"] is True
        assert "timestamp" in access_log[0]

    def test_check_access_unauthorized_user(self):
        """Test access check for unauthorized user."""
        from src.security.phi_protection import PHIAccessControl

        access_control = PHIAccessControl()

        # Check access for unauthorized user
        has_access = access_control.check_access("unauthorized_user", "write")
        assert has_access is False

        # Verify access log
        access_log = access_control.get_access_log()
        assert len(access_log) == 1
        assert access_log[0]["user_id"] == "unauthorized_user"
        assert access_log[0]["operation"] == "write"
        assert access_log[0]["granted"] is False

    def test_access_log_multiple_operations(self):
        """Test access log with multiple operations."""
        from src.security.phi_protection import PHIAccessControl

        access_control = PHIAccessControl()
        access_control.add_authorized_user("user1", "admin")

        # Perform multiple operations
        access_control.check_access("user1", "read")
        access_control.check_access("user1", "write")
        access_control.check_access("user2", "read")  # Unauthorized

        access_log = access_control.get_access_log()
        assert len(access_log) == 3

        # Check first operation
        assert access_log[0]["user_id"] == "user1"
        assert access_log[0]["operation"] == "read"
        assert access_log[0]["granted"] is True

        # Check second operation
        assert access_log[1]["user_id"] == "user1"
        assert access_log[1]["operation"] == "write"
        assert access_log[1]["granted"] is True

        # Check third operation (unauthorized)
        assert access_log[2]["user_id"] == "user2"
        assert access_log[2]["operation"] == "read"
        assert access_log[2]["granted"] is False

    def test_global_encryption_functions(self):
        """Test global PHI encryption functions."""
        from src.security.phi_protection import decrypt_phi, encrypt_phi

        test_data = "Global encryption test data"

        # Test global encryption functions
        encrypted = encrypt_phi(test_data)
        assert isinstance(encrypted, bytes)

        decrypted = decrypt_phi(encrypted)
        assert decrypted == test_data
        assert isinstance(decrypted, str)

    def test_requires_phi_access_decorator_authorized(self):
        """Test PHI access decorator with authorized user."""
        from src.security.phi_protection import get_phi_protection, requires_phi_access

        # Add authorized user
        protection = get_phi_protection()
        protection.get_access_control().add_authorized_user("test_user", "admin")

        @requires_phi_access("read")
        def test_function(data, user_id=None):
            return f"Processed: {data}"

        # Should work with authorized user
        result = test_function("test data", user_id="test_user")
        assert result == "Processed: test data"

    def test_requires_phi_access_decorator_unauthorized(self):
        """Test PHI access decorator with unauthorized user."""
        from src.security.phi_protection import requires_phi_access

        @requires_phi_access("read")
        def test_function(data, user_id=None):
            return f"Processed: {data}"

        # Should raise PermissionError with unauthorized user
        with pytest.raises(PermissionError) as exc_info:
            test_function("test data", user_id="unauthorized_user")

        assert "not authorized for read operation" in str(exc_info.value)

    def test_error_handling_invalid_encrypted_data(self):
        """Test error handling with invalid encrypted data."""
        phi_encryption = PHIEncryption()

        # Try to decrypt invalid data
        with pytest.raises(InvalidToken):  # Fernet will raise appropriate error
            phi_encryption.decrypt_data(b"invalid_encrypted_data")
