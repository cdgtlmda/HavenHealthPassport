"""Test PHI Protection Module - comprehensive coverage Required.

HIPAA Compliant - Real encryption operations.
NO MOCKS for encryption functionality per medical compliance requirements.

This tests critical PHI encryption and access control for refugee healthcare data.
MUST achieve comprehensive test coverage for medical compliance.
"""

from datetime import datetime

import pytest
from cryptography.fernet import Fernet, InvalidToken

from src.security.phi_protection import (
    PHIAccessControl,
    PHIEncryption,
    decrypt_phi,
    encrypt_phi,
    get_phi_protection,
    protect_phi_field,
    requires_phi_access,
)


@pytest.mark.hipaa_required
@pytest.mark.phi_encryption
class TestPHIEncryption:
    """Test PHI encryption with REAL cryptographic operations - comprehensive coverage Required."""

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

    def test_generate_key_static_method(self):
        """Test static key generation method."""
        key1 = PHIEncryption._generate_key()
        key2 = PHIEncryption._generate_key()

        # Keys should be different
        assert key1 != key2
        assert len(key1) == 44  # Fernet key length in base64
        assert len(key2) == 44
        assert isinstance(key1, bytes)
        assert isinstance(key2, bytes)

        # Verify keys are valid Fernet keys
        cipher1 = Fernet(key1)
        cipher2 = Fernet(key2)
        assert cipher1 is not None
        assert cipher2 is not None

    def test_derive_key_from_password_with_salt(self):
        """Test key derivation from password with provided salt."""
        password = "test_password_123"
        salt = b"test_salt_16byte"

        key = PHIEncryption.derive_key_from_password(password, salt)

        # Verify key properties
        assert isinstance(key, bytes)
        assert len(key) == 44  # Base64 encoded 32-byte key

        # Same password and salt should produce same key
        key2 = PHIEncryption.derive_key_from_password(password, salt)
        assert key == key2

        # Different password should produce different key
        key3 = PHIEncryption.derive_key_from_password("different_password", salt)
        assert key != key3

    def test_derive_key_from_password_without_salt(self):
        """Test key derivation from password without provided salt - uses real os.urandom."""
        password = "test_password_123"

        # Call multiple times to verify different salts produce different keys
        key1 = PHIEncryption.derive_key_from_password(password)
        key2 = PHIEncryption.derive_key_from_password(password)

        # Verify key properties
        assert isinstance(key1, bytes)
        assert isinstance(key2, bytes)
        assert len(key1) == 44  # Base64 encoded 32-byte key
        assert len(key2) == 44

        # Different salts should produce different keys
        assert key1 != key2

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

        test_data = b"Binary PHI data with special chars: \\x00\\x01\\x02"

        encrypted = phi_encryption.encrypt_data(test_data)
        assert isinstance(encrypted, bytes)
        assert encrypted != test_data

        decrypted = phi_encryption.decrypt_data(encrypted)
        # Bytes are decoded to string
        assert decrypted == test_data.decode("utf-8")

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

    def test_encrypt_decrypt_empty_string(self):
        """Test encryption and decryption of empty string."""
        phi_encryption = PHIEncryption()

        test_data = ""
        encrypted = phi_encryption.encrypt_data(test_data)
        assert isinstance(encrypted, bytes)
        assert len(encrypted) > 0  # Even empty data produces encrypted output

        decrypted = phi_encryption.decrypt_data(encrypted)
        assert decrypted == test_data

    def test_encrypt_decrypt_unicode_data(self):
        """Test encryption and decryption of unicode data."""
        phi_encryption = PHIEncryption()

        test_data = "Patient: José María, Diagnosis: Niño con fiebre 🌡️"
        encrypted = phi_encryption.encrypt_data(test_data)
        assert isinstance(encrypted, bytes)

        decrypted = phi_encryption.decrypt_data(encrypted)
        assert decrypted == test_data

    def test_decrypt_invalid_data_raises_error(self):
        """Test that decrypting invalid data raises appropriate error."""
        phi_encryption = PHIEncryption()

        # Try to decrypt invalid data
        with pytest.raises(InvalidToken):
            phi_encryption.decrypt_data(b"invalid_encrypted_data")

    def test_encrypt_data_none_value_coverage(self):
        """Test encryption of None value to ensure line 57 coverage."""
        phi_encryption = PHIEncryption()

        encrypted = phi_encryption.encrypt_data(None)
        assert isinstance(encrypted, bytes)

        # Decrypt and verify it becomes empty string
        decrypted = phi_encryption.decrypt_data(encrypted)
        assert decrypted == ""


@pytest.mark.hipaa_required
@pytest.mark.phi_protection
class TestPHIAccessControl:
    """Test PHI access control functionality - comprehensive coverage Required."""

    def test_phi_access_control_initialization(self):
        """Test PHI access control initialization."""
        access_control = PHIAccessControl()

        # Verify initialization
        assert hasattr(access_control, "authorized_users")
        assert hasattr(access_control, "access_log")
        assert isinstance(access_control.authorized_users, set)
        assert isinstance(access_control.access_log, list)
        assert len(access_control.authorized_users) == 0
        assert len(access_control.access_log) == 0

    def test_add_authorized_user_with_role(self):
        """Test adding authorized user with specific role."""
        access_control = PHIAccessControl()

        user_id = "test_user_001"
        role = "physician"

        access_control.add_authorized_user(user_id, role)

        # Verify user was added
        assert (user_id, role) in access_control.authorized_users
        assert len(access_control.authorized_users) == 1

    def test_add_authorized_user_default_role(self):
        """Test adding authorized user with default role."""
        access_control = PHIAccessControl()

        user_id = "test_user_002"

        access_control.add_authorized_user(user_id)

        # Verify user was added with default role
        assert (user_id, "viewer") in access_control.authorized_users
        assert len(access_control.authorized_users) == 1

    def test_add_multiple_authorized_users(self):
        """Test adding multiple authorized users."""
        access_control = PHIAccessControl()

        users = [
            ("user1", "admin"),
            ("user2", "physician"),
            ("user3", "nurse"),
            ("user4", "viewer"),
        ]

        for user_id, role in users:
            access_control.add_authorized_user(user_id, role)

        # Verify all users were added
        assert len(access_control.authorized_users) == 4
        for user_tuple in users:
            assert user_tuple in access_control.authorized_users

    def test_check_access_authorized_user_read(self):
        """Test access check for authorized user with read operation."""
        access_control = PHIAccessControl()
        user_id = "authorized_user"
        access_control.add_authorized_user(user_id, "physician")

        # Check access
        has_access = access_control.check_access(user_id, "read")

        # Verify access granted
        assert has_access is True

        # Verify access log entry
        assert len(access_control.access_log) == 1
        log_entry = access_control.access_log[0]
        assert log_entry["user_id"] == user_id
        assert log_entry["operation"] == "read"
        assert log_entry["granted"] is True
        assert "timestamp" in log_entry

    def test_check_access_authorized_user_default_operation(self):
        """Test access check for authorized user with default operation."""
        access_control = PHIAccessControl()
        user_id = "authorized_user"
        access_control.add_authorized_user(user_id, "nurse")

        # Check access without specifying operation (defaults to "read")
        has_access = access_control.check_access(user_id)

        # Verify access granted
        assert has_access is True

        # Verify access log entry
        assert len(access_control.access_log) == 1
        log_entry = access_control.access_log[0]
        assert log_entry["operation"] == "read"

    def test_check_access_unauthorized_user(self):
        """Test access check for unauthorized user."""
        access_control = PHIAccessControl()
        access_control.add_authorized_user("authorized_user", "physician")

        unauthorized_user = "unauthorized_user"

        # Check access for unauthorized user
        has_access = access_control.check_access(unauthorized_user, "read")

        # Verify access denied
        assert has_access is False

        # Verify access log entry
        assert len(access_control.access_log) == 1
        log_entry = access_control.access_log[0]
        assert log_entry["user_id"] == unauthorized_user
        assert log_entry["operation"] == "read"
        assert log_entry["granted"] is False

    def test_check_access_multiple_operations(self):
        """Test multiple access checks create separate log entries."""
        access_control = PHIAccessControl()
        user_id = "test_user"
        access_control.add_authorized_user(user_id, "admin")

        operations = ["read", "write", "delete", "update"]

        for operation in operations:
            access_control.check_access(user_id, operation)

        # Verify all operations logged
        assert len(access_control.access_log) == 4
        for i, operation in enumerate(operations):
            assert access_control.access_log[i]["operation"] == operation
            assert access_control.access_log[i]["granted"] is True

    def test_get_access_log_returns_copy(self):
        """Test that get_access_log returns a copy of the log."""
        access_control = PHIAccessControl()
        user_id = "test_user"
        access_control.add_authorized_user(user_id)
        access_control.check_access(user_id, "read")

        # Get access log
        log_copy = access_control.get_access_log()

        # Verify it's a copy
        assert log_copy == access_control.access_log
        assert log_copy is not access_control.access_log

        # Modify copy shouldn't affect original
        log_copy.append({"test": "entry"})
        assert len(access_control.access_log) == 1
        assert len(log_copy) == 2

    def test_access_log_timestamp_format_real(self):
        """Test that access log timestamps are in correct ISO format using real datetime."""
        access_control = PHIAccessControl()
        user_id = "test_user"
        access_control.add_authorized_user(user_id)

        # Record time before access check
        before_time = datetime.utcnow()
        access_control.check_access(user_id, "read")
        after_time = datetime.utcnow()

        # Verify timestamp format and timing
        log_entry = access_control.access_log[0]
        timestamp_str = log_entry["timestamp"]

        # Parse timestamp to verify format
        timestamp = datetime.fromisoformat(timestamp_str)

        # Verify timestamp is within expected range
        assert before_time <= timestamp <= after_time


@pytest.mark.hipaa_required
@pytest.mark.phi_protection
class TestGlobalPHIFunctions:
    """Test global PHI encryption functions - comprehensive coverage Required."""

    def test_encrypt_phi_global_function(self):
        """Test global encrypt_phi function."""
        test_data = "Test PHI data for global encryption"

        encrypted = encrypt_phi(test_data)

        # Verify encryption
        assert isinstance(encrypted, bytes)
        assert encrypted != test_data.encode()

        # Verify it uses the global encryption instance
        protection = get_phi_protection()
        expected_encrypted = protection.get_encryption().encrypt_data(test_data)
        # Note: Fernet includes timestamp, so we can't compare directly
        # Instead, verify both can be decrypted to same value
        decrypted1 = protection.get_encryption().decrypt_data(encrypted)
        decrypted2 = protection.get_encryption().decrypt_data(expected_encrypted)
        assert decrypted1 == decrypted2 == test_data

    def test_decrypt_phi_global_function(self):
        """Test global decrypt_phi function."""
        test_data = "Test PHI data for global decryption"

        # First encrypt using global function
        encrypted = encrypt_phi(test_data)

        # Then decrypt using global function
        decrypted = decrypt_phi(encrypted)

        # Verify decryption
        assert decrypted == test_data
        assert isinstance(decrypted, str)

    def test_global_functions_use_same_instance(self):
        """Test that global functions use the same encryption instance."""
        test_data = "Test data for instance consistency"

        # Encrypt with global function
        encrypted_global = encrypt_phi(test_data)

        # Decrypt with instance method
        protection = get_phi_protection()
        decrypted_instance = protection.get_encryption().decrypt_data(encrypted_global)

        # Should work because they use the same instance
        assert decrypted_instance == test_data


@pytest.mark.hipaa_required
@pytest.mark.phi_protection
class TestPHIDecorators:
    """Test PHI protection decorators - comprehensive coverage Required."""

    def test_requires_phi_access_decorator_authorized(self):
        """Test requires_phi_access decorator with authorized user."""
        # Add user to global access control
        protection = get_phi_protection()
        protection.get_access_control().add_authorized_user("test_user", "physician")

        @requires_phi_access("read")
        def test_function(data, user_id=None):
            return f"Processed: {data}"

        # Call function with authorized user
        result = test_function("test data", user_id="test_user")

        # Verify function executed
        assert result == "Processed: test data"

        # Verify access was logged
        protection = get_phi_protection()
        access_log = protection.get_access_control().get_access_log()
        assert len(access_log) >= 1
        # Find the relevant log entry
        relevant_logs = [log for log in access_log if log["user_id"] == "test_user"]
        assert len(relevant_logs) >= 1
        assert relevant_logs[-1]["granted"] is True

    def test_requires_phi_access_decorator_unauthorized(self):
        """Test requires_phi_access decorator with unauthorized user."""

        @requires_phi_access("write")
        def test_function(data, user_id=None):
            return f"Processed: {data}"

        # Call function with unauthorized user
        with pytest.raises(PermissionError) as exc_info:
            test_function("test data", user_id="unauthorized_user")

        # Verify error message
        assert "unauthorized_user not authorized for write operation" in str(
            exc_info.value
        )

        # Verify access was logged as denied
        protection = get_phi_protection()
        access_log = protection.get_access_control().get_access_log()
        relevant_logs = [
            log for log in access_log if log["user_id"] == "unauthorized_user"
        ]
        assert len(relevant_logs) >= 1
        assert relevant_logs[-1]["granted"] is False

    def test_requires_phi_access_decorator_default_operation(self):
        """Test requires_phi_access decorator with default operation."""
        protection = get_phi_protection()
        protection.get_access_control().add_authorized_user(
            "test_user_default", "viewer"
        )

        @requires_phi_access()  # Default operation is "read"
        def test_function(data, user_id=None):
            return f"Read: {data}"

        # Call function
        result = test_function("test data", user_id="test_user_default")

        # Verify function executed
        assert result == "Read: test data"

        # Verify access log shows "read" operation
        protection = get_phi_protection()
        access_log = protection.get_access_control().get_access_log()
        relevant_logs = [
            log for log in access_log if log["user_id"] == "test_user_default"
        ]
        assert len(relevant_logs) >= 1
        assert relevant_logs[-1]["operation"] == "read"

    def test_requires_phi_access_decorator_system_user(self):
        """Test requires_phi_access decorator with system user (default)."""

        @requires_phi_access("admin")
        def test_function(data):
            return f"Admin: {data}"

        # Call function without user_id (defaults to "system")
        result = test_function("test data")

        # Verify function executed (system user is pre-authorized)
        assert result == "Admin: test data"

    def test_requires_phi_access_decorator_preserves_function_metadata(self):
        """Test that decorator preserves original function metadata."""

        @requires_phi_access("read")
        def test_function_with_metadata(data, user_id=None):
            """Test function docstring."""
            return data

        # Verify metadata preserved
        assert test_function_with_metadata.__name__ == "test_function_with_metadata"
        assert test_function_with_metadata.__doc__ == "Test function docstring."

    def test_protect_phi_field_decorator_basic(self):
        """Test protect_phi_field decorator basic functionality."""

        @protect_phi_field("ssn")
        class TestPatient:
            def __init__(self, name, ssn):
                self.name = name
                self.ssn = ssn

        # Create instance
        patient = TestPatient("John Doe", "123-45-6789")

        # Verify name is not encrypted
        assert patient.name == "John Doe"

        # Verify SSN is encrypted (accessing it should decrypt)
        assert patient.ssn == "123-45-6789"

        # Verify encrypted field exists
        assert hasattr(patient, "_encrypted_ssn")
        assert patient._encrypted_ssn is not None
        assert isinstance(patient._encrypted_ssn, bytes)

    def test_protect_phi_field_decorator_setter(self):
        """Test protect_phi_field decorator with setter."""

        @protect_phi_field("medical_record")
        class TestRecord:
            def __init__(self, record_id):
                self.record_id = record_id
                self.medical_record = None

        # Create instance
        record = TestRecord("REC001")

        # Set protected field
        record.medical_record = "Confidential medical information"

        # Verify field is encrypted
        assert record.medical_record == "Confidential medical information"
        assert hasattr(record, "_encrypted_medical_record")
        assert record._encrypted_medical_record is not None

        # Update the field
        record.medical_record = "Updated medical information"
        assert record.medical_record == "Updated medical information"

    def test_protect_phi_field_decorator_multiple_fields(self):
        """Test protect_phi_field decorator with multiple protected fields."""

        @protect_phi_field("ssn")
        @protect_phi_field("diagnosis")
        class TestPatientRecord:
            def __init__(self, name, ssn, diagnosis):
                self.name = name
                self.ssn = ssn
                self.diagnosis = diagnosis

        # Create instance
        patient = TestPatientRecord("Jane Doe", "987-65-4321", "Hypertension")

        # Verify both fields are protected
        assert patient.ssn == "987-65-4321"
        assert patient.diagnosis == "Hypertension"
        assert patient.name == "Jane Doe"  # Not protected

        # Verify encrypted fields exist
        assert hasattr(patient, "_encrypted_ssn")
        assert hasattr(patient, "_encrypted_diagnosis")
        assert patient._encrypted_ssn is not None
        assert patient._encrypted_diagnosis is not None

    def test_protect_phi_field_decorator_field_not_set(self):
        """Test protect_phi_field decorator when field is not initially set."""

        @protect_phi_field("optional_field")
        class TestClass:
            def __init__(self, required_field):
                self.required_field = required_field
                # optional_field not set initially

        # Create instance
        instance = TestClass("required_value")

        # Verify required field works normally
        assert instance.required_field == "required_value"

        # Set the protected field later
        instance.optional_field = "protected_value"  # type: ignore[attr-defined]
        assert instance.optional_field == "protected_value"  # type: ignore[attr-defined]
        assert hasattr(instance, "_encrypted_optional_field")


@pytest.mark.hipaa_required
@pytest.mark.phi_protection
class TestGlobalPHIState:
    """Test global PHI protection state - comprehensive coverage Required."""

    def test_global_encryption_instance_exists(self):
        """Test that global encryption instance exists and is properly initialized."""
        protection = get_phi_protection()
        encryption = protection.get_encryption()
        assert encryption is not None
        assert isinstance(encryption, PHIEncryption)
        assert hasattr(encryption, "cipher")
        assert encryption.cipher is not None

    def test_global_access_control_instance_exists(self):
        """Test that global access control instance exists and is properly initialized."""
        protection = get_phi_protection()
        access_control = protection.get_access_control()
        assert access_control is not None
        assert isinstance(access_control, PHIAccessControl)
        assert hasattr(access_control, "authorized_users")
        assert hasattr(access_control, "access_log")

    def test_global_access_control_default_users(self):
        """Test that global access control has default authorized users."""
        # The module initializes with default users
        protection = get_phi_protection()
        authorized_users = protection.get_access_control().authorized_users

        # Check for default users (system and demo_user)
        user_ids = {user[0] for user in authorized_users}
        assert "system" in user_ids
        assert "demo_user" in user_ids

        # Check roles
        user_roles = {user[0]: user[1] for user in authorized_users}
        assert user_roles["system"] == "admin"
        assert user_roles["demo_user"] == "viewer"

    def test_global_access_control_demo_user_line_coverage(self):
        """Test that covers the demo user addition line 183."""
        # The line adds demo_user with viewer role
        phi_protection = get_phi_protection()
        access_control = phi_protection.get_access_control()
        assert ("demo_user", "viewer") in access_control.authorized_users

        # Verify the demo user can access PHI with viewer permissions
        phi_protection = get_phi_protection()
        access_control = phi_protection.get_access_control()
        assert access_control.check_access("demo_user", "read") is True

    def test_global_instances_consistency(self):
        """Test that global instances are consistent across imports."""
        # Get instances through singleton
        phi_protection1 = get_phi_protection()
        phi_protection2 = get_phi_protection()

        # Should be the same instance
        assert phi_protection1 is phi_protection2
        assert phi_protection1.get_encryption() is phi_protection2.get_encryption()
        assert (
            phi_protection1.get_access_control() is phi_protection2.get_access_control()
        )

    def test_global_functions_integration(self):
        """Test integration between global functions and instances."""
        test_data = "Integration test data"

        # Encrypt with global function
        encrypted = encrypt_phi(test_data)

        # Decrypt with global function
        decrypted = decrypt_phi(encrypted)

        # Verify round-trip
        assert decrypted == test_data

        # Verify same result with direct instance usage
        protection = get_phi_protection()
        encrypted_direct = protection.get_encryption().encrypt_data(test_data)
        decrypted_direct = protection.get_encryption().decrypt_data(encrypted_direct)
        assert decrypted_direct == test_data
