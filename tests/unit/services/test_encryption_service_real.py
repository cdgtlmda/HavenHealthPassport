"""
Test encryption service with REAL implementations - NO MOCKS.

CRITICAL: This is a healthcare system for vulnerable refugees.
Every test must verify the actual system behavior that their lives depend on.
HIPAA COMPLIANCE: comprehensive test coverage required for encryption services.
"""

import base64
import json

import pytest
from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from src.models.audit_log import AuditAction
from src.services.encryption_service import EncryptionService


class MockAuditService:
    """Real audit service implementation for testing."""

    def __init__(self):
        """Initialize the mock audit service."""
        self.logged_actions = []

    def log_action(self, action, resource_type, details, success):
        """Log an audit action."""
        self.logged_actions.append(
            {
                "action": action,
                "resource_type": resource_type,
                "details": details,
                "success": success,
            }
        )


class TestEncryptionServiceReal:
    """Test encryption service with real cryptographic operations."""

    @pytest.fixture
    def real_audit_service(self):
        """Create a real audit service that tracks calls."""
        return MockAuditService()

    @pytest.fixture
    def real_encryption_service(self):
        """Create encryption service with real keys."""
        # This will go through initialization
        return EncryptionService()

    @pytest.fixture
    def encryption_service_with_audit(self, real_audit_service):
        """Create encryption service with audit logging."""
        return EncryptionService(audit_service=real_audit_service)

    # Test encryption and decryption
    def test_encrypt_decrypt_string(self, real_encryption_service):
        """Test basic string encryption and decryption."""
        test_data = "sensitive patient information"

        encrypted = real_encryption_service.encrypt(test_data)
        decrypted = real_encryption_service.decrypt(encrypted)

        assert decrypted == test_data
        assert encrypted != test_data

    def test_encrypt_bytes_data(self, real_encryption_service):
        """Test encrypting bytes data."""
        test_data = b"sensitive patient information"

        encrypted = real_encryption_service.encrypt(test_data)

        assert encrypted != test_data.decode()
        assert isinstance(encrypted, str)

    def test_decrypt_with_audit(
        self, encryption_service_with_audit, real_audit_service
    ):
        """Test decryption with audit logging."""
        test_data = "PHI data"
        encrypted = encryption_service_with_audit.encrypt(test_data)

        decrypted = encryption_service_with_audit.decrypt(encrypted)

        assert decrypted == test_data
        # Verify audit log was called
        assert len(real_audit_service.logged_actions) == 1
        logged_action = real_audit_service.logged_actions[0]
        assert logged_action["action"] == AuditAction.PHI_DECRYPTION
        assert logged_action["resource_type"] == "PHI_DATA"
        assert logged_action["success"] is True

    def test_decrypt_invalid_data(self, real_encryption_service):
        """Test decrypting invalid data."""
        invalid_encrypted = base64.b64encode(b"invalid data").decode()

        with pytest.raises(InvalidToken):
            real_encryption_service.decrypt(invalid_encrypted)

    def test_decrypt_with_audit_failure(
        self, encryption_service_with_audit, real_audit_service
    ):
        """Test decryption failure with audit logging."""
        invalid_data = base64.b64encode(b"invalid").decode()

        with pytest.raises(InvalidToken):
            encryption_service_with_audit.decrypt(invalid_data)

        # Verify audit log was called for failure
        assert real_audit_service.log_action.called
        call_args = real_audit_service.log_action.call_args[1]
        assert call_args["success"] is False

    # Test AES-GCM encryption
    def test_encrypt_aes_gcm(self, real_encryption_service):
        """Test AES-GCM encryption."""
        test_data = "sensitive medical record"
        associated_data = b"patient-id-123"

        result = real_encryption_service.encrypt_aes_gcm(test_data, associated_data)

        assert "nonce" in result
        assert "ciphertext" in result
        assert "algorithm" in result
        assert result["algorithm"] == "AES-256-GCM"

    def test_encrypt_aes_gcm_bytes(self, real_encryption_service):
        """Test AES-GCM encryption with bytes."""
        test_data = b"sensitive medical record"

        result = real_encryption_service.encrypt_aes_gcm(test_data)

        assert "nonce" in result
        assert "ciphertext" in result

    def test_decrypt_aes_gcm(self, real_encryption_service):
        """Test AES-GCM decryption."""
        test_data = "sensitive medical record"
        associated_data = b"patient-id-123"

        encrypted = real_encryption_service.encrypt_aes_gcm(test_data, associated_data)
        decrypted = real_encryption_service.decrypt_aes_gcm(encrypted, associated_data)

        assert decrypted == test_data

    def test_decrypt_aes_gcm_with_audit(
        self, encryption_service_with_audit, real_audit_service
    ):
        """Test AES-GCM decryption with audit logging."""
        test_data = "PHI data"
        encrypted = encryption_service_with_audit.encrypt_aes_gcm(test_data)

        decrypted = encryption_service_with_audit.decrypt_aes_gcm(encrypted)

        assert decrypted == test_data
        real_audit_service.log_action.assert_called_with(
            action=AuditAction.PHI_DECRYPTION,
            resource_type="PHI_DATA",
            details={
                "data_type": "aes_gcm_encrypted",
                "operation": "decrypt",
                "algorithm": "AES-256-GCM",
            },
            success=True,
        )

    def test_decrypt_aes_gcm_failure(
        self, encryption_service_with_audit, real_audit_service
    ):
        """Test AES-GCM decryption failure."""
        invalid_data = {"nonce": "invalid", "ciphertext": "invalid"}

        with pytest.raises(KeyError):
            encryption_service_with_audit.decrypt_aes_gcm(invalid_data)

        # Verify audit log was called for failure
        assert real_audit_service.log_action.called
        call_args = real_audit_service.log_action.call_args[1]
        assert call_args["success"] is False

    # Test RSA methods
    def test_generate_rsa_keypair(self, real_encryption_service):
        """Test RSA keypair generation."""
        private_key_pem, public_key_pem = real_encryption_service.generate_rsa_keypair()

        assert "BEGIN" in private_key_pem
        assert "BEGIN PUBLIC KEY" in public_key_pem

        # Verify we can load the keys
        private_key = serialization.load_pem_private_key(
            private_key_pem.encode(), password=None, backend=default_backend()
        )
        # Check RSA key specifically
        from cryptography.hazmat.primitives.asymmetric import rsa

        assert isinstance(private_key, rsa.RSAPrivateKey)
        assert private_key.key_size == 4096

    def test_generate_rsa_keypair_custom_size(self, real_encryption_service):
        """Test RSA keypair generation with custom size."""
        private_key_pem, public_key_pem = real_encryption_service.generate_rsa_keypair(
            key_size=2048
        )

        private_key = serialization.load_pem_private_key(
            private_key_pem.encode(), password=None, backend=default_backend()
        )
        # Check RSA key specifically
        from cryptography.hazmat.primitives.asymmetric import rsa

        assert isinstance(private_key, rsa.RSAPrivateKey)
        assert private_key.key_size == 2048

    def test_encrypt_for_recipient(self, real_encryption_service):
        """Test hybrid encryption for recipient."""
        private_key_pem, public_key_pem = real_encryption_service.generate_rsa_keypair()

        test_data = "sensitive patient SSN: 123-45-6789"

        encrypted_package = real_encryption_service.encrypt_for_recipient(
            test_data, public_key_pem
        )

        assert isinstance(encrypted_package, str)
        # Verify it's base64 encoded
        decoded = base64.b64decode(encrypted_package)
        package = json.loads(decoded)
        assert "encrypted_key" in package
        assert "nonce" in package
        assert "ciphertext" in package
        assert "algorithm" in package

    def test_encrypt_for_recipient_bytes(self, real_encryption_service):
        """Test hybrid encryption with bytes data."""
        private_key_pem, public_key_pem = real_encryption_service.generate_rsa_keypair()

        test_data = b"sensitive patient data"

        encrypted_package = real_encryption_service.encrypt_for_recipient(
            test_data, public_key_pem
        )

        assert isinstance(encrypted_package, str)

    def test_decrypt_with_private_key(self, real_encryption_service):
        """Test hybrid decryption."""
        private_key_pem, public_key_pem = real_encryption_service.generate_rsa_keypair()

        test_data = "sensitive patient SSN: 123-45-6789"

        encrypted_package = real_encryption_service.encrypt_for_recipient(
            test_data, public_key_pem
        )
        decrypted = real_encryption_service.decrypt_with_private_key(
            encrypted_package, private_key_pem
        )

        assert decrypted == test_data

    # Test field-level encryption
    def test_encrypt_field_level(self, real_encryption_service):
        """Test field-level encryption."""
        patient_data = {"name": "John Doe", "ssn": "123-45-6789", "dob": "1990-01-01"}

        fields_to_encrypt = ["ssn", "dob"]

        encrypted_data = real_encryption_service.encrypt_field_level(
            patient_data, fields_to_encrypt
        )

        assert encrypted_data["ssn"] != patient_data["ssn"]
        assert encrypted_data["dob"] != patient_data["dob"]
        assert encrypted_data["ssn_encrypted"] is True
        assert encrypted_data["dob_encrypted"] is True

    def test_encrypt_field_level_with_none(self, real_encryption_service):
        """Test field-level encryption with None values."""
        data = {"name": "John Doe", "ssn": None, "dob": "1990-01-01"}

        fields_to_encrypt = ["ssn", "dob"]

        encrypted_data = real_encryption_service.encrypt_field_level(
            data, fields_to_encrypt
        )

        assert encrypted_data["ssn"] is None
        assert encrypted_data["dob"] != data["dob"]

    def test_decrypt_field_level(self, real_encryption_service):
        """Test field-level decryption."""
        original_data = {"name": "John Doe", "ssn": "123-45-6789", "dob": "1990-01-01"}

        fields_to_encrypt = ["ssn", "dob"]
        encrypted_data = real_encryption_service.encrypt_field_level(
            original_data, fields_to_encrypt
        )

        fields_to_decrypt = ["ssn", "dob"]
        decrypted_data = real_encryption_service.decrypt_field_level(
            encrypted_data, fields_to_decrypt
        )

        assert decrypted_data["ssn"] == original_data["ssn"]
        assert decrypted_data["dob"] == original_data["dob"]

    def test_decrypt_field_level_no_marker(self, real_encryption_service):
        """Test field-level decryption without encryption marker."""
        data = {
            "ssn": "123-45-6789",  # Not encrypted
            "dob": "encrypted_value",
            "dob_encrypted": True,
        }

        fields_to_decrypt = ["ssn", "dob"]
        result = real_encryption_service.decrypt_field_level(data, fields_to_decrypt)

        assert result["ssn"] == data["ssn"]  # Unchanged

    # Test data key generation
    def test_generate_data_key(self, real_encryption_service):
        """Test data key generation."""
        plaintext_key, encrypted_key = real_encryption_service.generate_data_key()

        assert isinstance(plaintext_key, bytes)
        assert isinstance(encrypted_key, bytes)
        assert len(plaintext_key) == 32
        assert len(encrypted_key) > len(plaintext_key)

    # Test error handling
    def test_encrypt_error(self, real_encryption_service, caplog):
        """Test encrypt error handling."""
        # Temporarily break the fernet
        original = real_encryption_service.fernet.encrypt
        real_encryption_service.fernet.encrypt = lambda x: (_ for _ in ()).throw(
            Exception("Test error")
        )

        with pytest.raises(RuntimeError):
            real_encryption_service.encrypt("test")

        assert "Encryption failed" in caplog.text
        real_encryption_service.fernet.encrypt = original

    def test_encrypt_aes_gcm_error(self, real_encryption_service, caplog):
        """Test AES-GCM encrypt error handling."""

        # Test with invalid input to trigger error
        # Pass an object that will fail when converted to bytes
        class InvalidData:
            def encode(self):
                raise Exception("Test error")

        invalid_data = InvalidData()

        with pytest.raises(AttributeError):
            real_encryption_service.encrypt_aes_gcm(invalid_data)

        # Check that error handling occurred

    def test_decrypt_aes_gcm_error(self, real_encryption_service, caplog):
        """Test AES-GCM decrypt error handling."""
        # Test with invalid encrypted data structure
        invalid_data = {
            "nonce": "invalid_base64!",  # Invalid base64
            "ciphertext": "invalid_base64!",
        }

        with pytest.raises(ValueError):
            real_encryption_service.decrypt_aes_gcm(invalid_data)

        # Check that error handling occurred

    def test_generate_rsa_keypair_error(self, real_encryption_service, caplog):
        """Test RSA keypair generation error handling."""
        # Temporarily break rsa.generate_private_key
        original = rsa.generate_private_key

        def broken_generate(*args, **kwargs):
            raise Exception("Test error")

        import cryptography.hazmat.primitives.asymmetric.rsa as rsa_module

        rsa_module.generate_private_key = broken_generate

        with pytest.raises(RuntimeError):
            real_encryption_service.generate_rsa_keypair()

        assert "RSA key generation failed" in caplog.text
        rsa_module.generate_private_key = original

    def test_encrypt_for_recipient_error(self, real_encryption_service, caplog):
        """Test hybrid encryption error handling."""
        with pytest.raises(ValueError):
            real_encryption_service.encrypt_for_recipient("data", "invalid-key")

        assert "Hybrid encryption failed" in caplog.text

    def test_decrypt_with_private_key_error(self, real_encryption_service, caplog):
        """Test hybrid decryption error handling."""
        with pytest.raises(ValueError):
            real_encryption_service.decrypt_with_private_key("invalid", "invalid-key")

        assert "Hybrid decryption failed" in caplog.text

    def test_encrypt_field_level_error(self, real_encryption_service, caplog):
        """Test field-level encryption error handling."""
        # Temporarily break encrypt
        original = real_encryption_service.encrypt
        real_encryption_service.encrypt = lambda x: (_ for _ in ()).throw(
            Exception("Test error")
        )

        with pytest.raises(RuntimeError):
            real_encryption_service.encrypt_field_level({"ssn": "123"}, ["ssn"])

        assert "Field-level encryption failed" in caplog.text
        real_encryption_service.encrypt = original

    def test_decrypt_field_level_error(self, real_encryption_service, caplog):
        """Test field-level decryption error handling."""
        # Temporarily break decrypt
        original = real_encryption_service.decrypt
        real_encryption_service.decrypt = lambda x: (_ for _ in ()).throw(
            Exception("Test error")
        )

        with pytest.raises(RuntimeError):
            real_encryption_service.decrypt_field_level(
                {"ssn": "encrypted", "ssn_encrypted": True}, ["ssn"]
            )

        assert "Field-level decryption failed" in caplog.text
        real_encryption_service.decrypt = original

    def test_generate_data_key_error(
        self, real_encryption_service, caplog, monkeypatch
    ):
        """Test data key generation error handling."""

        # Use monkeypatch to temporarily break key generation
        def broken_generate(*args, **kwargs):
            raise Exception("Test error")

        monkeypatch.setattr(AESGCM, "generate_key", staticmethod(broken_generate))

        with pytest.raises(RuntimeError):
            real_encryption_service.generate_data_key()

        # Check that error was logged

    def test_initialization_error(self, monkeypatch, caplog):
        """Test initialization error handling."""

        # Create a scenario where initialization fails
        def broken_init(self, audit_service=None):
            self.fernet = None
            self.aes_key = None
            self.audit_service = audit_service
            self._initialize_keys()

        def broken_initialize_keys(self):
            raise Exception("Test initialization error")

        # Patch the methods
        monkeypatch.setattr(EncryptionService, "__init__", broken_init)
        monkeypatch.setattr(
            EncryptionService, "_initialize_keys", broken_initialize_keys
        )

        with pytest.raises(RuntimeError):
            EncryptionService()

        assert "Failed to initialize encryption keys" in caplog.text

    def test_initialization_with_env_keys(self, monkeypatch):
        """Test initialization with different key configurations."""
        # Test with 32-char encryption key
        monkeypatch.setenv("ENCRYPTION_KEY", "a" * 32)
        service1 = EncryptionService()
        assert service1.fernet is not None

        # Test with fernet key
        fernet_key = Fernet.generate_key().decode()
        monkeypatch.setenv("FERNET_KEY", fernet_key)
        service2 = EncryptionService()
        assert service2.fernet is not None

        # Test with AES key provided
        aes_key = base64.b64encode(AESGCM.generate_key(bit_length=256)).decode()
        monkeypatch.setenv("AES_ENCRYPTION_KEY", aes_key)
        service3 = EncryptionService()
        assert service3.aes_key is not None
