"""Comprehensive coverage test for encryption service.

HIPAA COMPLIANCE: Critical healthcare system requiring Comprehensive test coverage.
"""

import base64
import json
import os

import pytest
from cryptography.fernet import Fernet, InvalidToken

from src.models.audit_log import AuditAction

# Import the service at module level to ensure it's loaded
from src.services.encryption_service import EncryptionService, encryption_service


class RealAuditService:
    """Real audit service implementation for testing."""

    def __init__(self):
        """Initialize the audit service."""
        self.logged_actions = []

    def log_action(self, action, resource_type, details, success=True, **kwargs):
        """Log an audit action."""
        self.logged_actions.append(
            {
                "action": action,
                "resource_type": resource_type,
                "details": details,
                "success": success,
                **kwargs,
            }
        )


def test_complete_encryption_service_coverage():
    """Single comprehensive test for comprehensive coverage."""
    # Test 1: Basic initialization with generated keys
    service1 = EncryptionService()
    assert service1.fernet is not None
    assert service1.aes_key is not None
    assert service1.audit_service is None

    # Test 2: Initialization with audit service
    real_audit = RealAuditService()
    service2 = EncryptionService(audit_service=real_audit)
    assert service2.audit_service == real_audit

    # Test 3: Encrypt and decrypt string
    test_data = "sensitive patient data"
    encrypted = service1.encrypt(test_data)
    assert encrypted != test_data
    assert isinstance(encrypted, str)

    decrypted = service1.decrypt(encrypted)
    assert decrypted == test_data

    # Test 4: Encrypt bytes data
    bytes_data = b"sensitive bytes"
    encrypted_bytes = service1.encrypt(bytes_data)
    assert isinstance(encrypted_bytes, str)

    # Test 5: Decrypt with audit logging success
    decrypted_audit = service2.decrypt(encrypted)
    assert decrypted_audit == test_data
    assert len(real_audit.logged_actions) == 1
    logged_action = real_audit.logged_actions[0]
    assert logged_action["action"] == AuditAction.PHI_DECRYPTION
    assert logged_action["resource_type"] == "PHI_DATA"
    assert logged_action["details"] == {
        "data_type": "encrypted_field",
        "operation": "decrypt",
    }
    assert logged_action["success"] is True

    # Test 6: Decrypt with audit logging failure
    real_audit.logged_actions.clear()
    try:
        service2.decrypt(base64.b64encode(b"invalid").decode())
    except Exception:
        pass
    assert len(real_audit.logged_actions) == 1
    assert real_audit.logged_actions[0]["success"] is False

    # Test 7: AES-GCM encryption with associated data
    aes_result = service1.encrypt_aes_gcm("test data", b"associated")
    assert "nonce" in aes_result
    assert "ciphertext" in aes_result
    assert "algorithm" in aes_result
    assert aes_result["algorithm"] == "AES-256-GCM"

    # Test 8: AES-GCM encryption with bytes
    aes_bytes = service1.encrypt_aes_gcm(b"bytes data")
    assert "nonce" in aes_bytes

    # Test 9: AES-GCM decryption
    decrypted_aes = service1.decrypt_aes_gcm(aes_result, b"associated")
    assert decrypted_aes == "test data"

    # Test 10: AES-GCM decryption with audit
    real_audit.logged_actions.clear()
    decrypted_aes2 = service2.decrypt_aes_gcm(aes_result, b"associated")
    assert decrypted_aes2 == "test data"
    assert len(real_audit.logged_actions) == 1

    # Test 11: AES-GCM decryption failure with audit
    real_audit.logged_actions.clear()
    try:
        service2.decrypt_aes_gcm(
            {
                "nonce": base64.b64encode(os.urandom(12)).decode(),
                "ciphertext": base64.b64encode(b"invalid").decode(),
            }
        )
    except Exception:
        pass
    assert len(real_audit.logged_actions) == 1
    assert real_audit.logged_actions[0]["success"] is False

    # Test 12: RSA keypair generation
    private_pem, public_pem = service1.generate_rsa_keypair()
    assert "PRIVATE KEY" in private_pem
    assert "PUBLIC KEY" in public_pem

    # Test 13: RSA keypair with custom size
    private_2048, public_2048 = service1.generate_rsa_keypair(key_size=2048)
    assert isinstance(private_2048, str)

    # Test 14: Encrypt for recipient
    encrypted_package = service1.encrypt_for_recipient("secret data", public_pem)
    assert isinstance(encrypted_package, str)
    package = json.loads(base64.b64decode(encrypted_package))
    assert package["algorithm"] == "RSA-4096/AES-256-GCM"

    # Test 15: Encrypt for recipient with bytes
    encrypted_bytes_pkg = service1.encrypt_for_recipient(b"bytes secret", public_pem)
    assert isinstance(encrypted_bytes_pkg, str)

    # Test 16: Decrypt with private key
    decrypted_pkg = service1.decrypt_with_private_key(encrypted_package, private_pem)
    assert decrypted_pkg == "secret data"

    # Test 17: Field-level encryption
    data = {"name": "John Doe", "ssn": "123-45-6789", "dob": "1990-01-01", "age": None}
    encrypted_fields = service1.encrypt_field_level(data, ["ssn", "dob", "age"])
    assert encrypted_fields["ssn"] != data["ssn"]
    assert encrypted_fields["ssn_encrypted"] is True
    assert encrypted_fields["age"] is None  # None not encrypted

    # Test 18: Field-level decryption
    decrypted_fields = service1.decrypt_field_level(encrypted_fields, ["ssn", "dob"])
    assert decrypted_fields["ssn"] == data["ssn"]
    assert "ssn_encrypted" not in decrypted_fields

    # Test 19: Generate data key
    plaintext_key, encrypted_key = service1.generate_data_key()
    assert len(plaintext_key) == 32
    assert len(encrypted_key) > len(plaintext_key)

    # Test 20: Generate data key with master_key_id
    pk2, ek2 = service1.generate_data_key(_master_key_id="test-key")
    assert isinstance(pk2, bytes)

    # Test singleton
    assert encryption_service is not None
    assert isinstance(encryption_service, EncryptionService)


def test_error_handling_paths():
    """Test all error handling paths using real implementations."""
    service = EncryptionService()

    # Test decrypt invalid base64
    with pytest.raises(ValueError):
        service.decrypt("invalid-base64!@#")

    # Test decrypt invalid token
    with pytest.raises(InvalidToken):
        service.decrypt(base64.b64encode(b"invalid").decode())

    # Test encrypt for recipient with invalid key
    with pytest.raises(ValueError):
        service.encrypt_for_recipient("test", "invalid-key")

    # Test decrypt with invalid private key
    with pytest.raises(ValueError):
        service.decrypt_with_private_key("invalid", "invalid")

    # Test field decrypt with invalid encrypted data
    invalid_encrypted = {"ssn": "invalid_encrypted_data", "ssn_encrypted": True}
    with pytest.raises(ValueError):
        service.decrypt_field_level(invalid_encrypted, ["ssn"])


def test_all_initialization_paths():
    """Test all initialization paths with real environment variables."""
    # Test with no environment variables
    original_fernet_key = os.environ.get("FERNET_KEY")
    original_aes_key = os.environ.get("AES_KEY")

    try:
        # Remove environment variables if they exist
        if "FERNET_KEY" in os.environ:
            del os.environ["FERNET_KEY"]
        if "AES_KEY" in os.environ:
            del os.environ["AES_KEY"]

        # Should generate new keys
        service = EncryptionService()
        assert service.fernet is not None
        assert service.aes_key is not None

        # Test with environment variables set
        os.environ["FERNET_KEY"] = Fernet.generate_key().decode()
        os.environ["AES_KEY"] = base64.b64encode(os.urandom(32)).decode()

        service2 = EncryptionService()
        assert service2.fernet is not None
        assert service2.aes_key is not None

    finally:
        # Restore original environment
        if original_fernet_key:
            os.environ["FERNET_KEY"] = original_fernet_key
        elif "FERNET_KEY" in os.environ:
            del os.environ["FERNET_KEY"]
        if original_aes_key:
            os.environ["AES_KEY"] = original_aes_key
        elif "AES_KEY" in os.environ:
            del os.environ["AES_KEY"]


def test_edge_cases():
    """Test edge cases with real implementations."""
    service = EncryptionService()

    # Test empty string encryption/decryption
    empty_encrypted = service.encrypt("")
    assert service.decrypt(empty_encrypted) == ""

    # Test field-level encryption with empty fields list
    data = {"name": "John", "ssn": "123-45-6789"}
    result = service.encrypt_field_level(data, [])
    assert result == data  # No fields encrypted

    # Test field-level decryption with no encrypted fields
    result = service.decrypt_field_level(data, ["name"])
    assert result == data  # No changes since no encrypted fields

    # Test AES-GCM with empty associated data
    aes_result = service.encrypt_aes_gcm("test", b"")
    decrypted = service.decrypt_aes_gcm(aes_result, b"")
    assert decrypted == "test"
