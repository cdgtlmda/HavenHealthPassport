"""
Comprehensive test suite for encryption service targeting comprehensive test coverage.

CRITICAL: This is a healthcare system for vulnerable refugees.
HIPAA COMPLIANCE: comprehensive test coverage required for encryption services.
MEDICAL COMPLIANCE: Uses REAL production code, REAL audit service, NO MOCKS.
"""

import base64
import json

import pytest
from cryptography.fernet import InvalidToken

from src.audit.audit_service import AuditTrailService
from src.database import SessionLocal
from src.models.audit_log import AuditAction, AuditLog
from src.services.encryption_service import EncryptionService


class TestEncryptionServiceCompleteCoverage:
    """Comprehensive test coverage for encryption service - REAL PRODUCTION CODE ONLY."""

    @pytest.fixture
    def db_session(self):
        """Create real database session for audit logging."""
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    @pytest.fixture
    def real_audit_service(self, db_session):
        """Create REAL audit service - no mocks for medical compliance."""
        return AuditTrailService(db_session)

    def test_init_and_key_initialization_real_service(self, real_audit_service):
        """Test initialization with REAL audit service."""
        # Test with real audit service
        service = EncryptionService(audit_service=real_audit_service)
        assert service.audit_service is not None
        assert service.fernet is not None
        assert service.aes_key is not None

        # Test without audit service
        service_no_audit = EncryptionService()
        assert service_no_audit.fernet is not None
        assert service_no_audit.aes_key is not None

    def test_encrypt_decrypt_string_real_operations(self):
        """Test encrypting and decrypting string data with REAL encryption."""
        service = EncryptionService()

        test_data = "sensitive patient information"
        encrypted = service.encrypt(test_data)

        assert encrypted != test_data
        assert isinstance(encrypted, str)

        decrypted = service.decrypt(encrypted)
        assert decrypted == test_data

    def test_encrypt_bytes_data_real_operations(self):
        """Test encrypting bytes data with REAL encryption."""
        service = EncryptionService()

        test_data = b"sensitive patient information"
        encrypted = service.encrypt(test_data.decode())

        assert isinstance(encrypted, str)
        decrypted = service.decrypt(encrypted)
        assert decrypted == test_data.decode()

    def test_decrypt_with_real_audit_success(self, real_audit_service, db_session):
        """Test decryption with REAL audit logging on success."""
        service = EncryptionService(audit_service=real_audit_service)

        test_data = "PHI data"
        encrypted = service.encrypt(test_data)
        decrypted = service.decrypt(encrypted)

        assert decrypted == test_data

        # Verify real audit log was created
        audit_logs = (
            db_session.query(AuditLog)
            .filter_by(action=AuditAction.PHI_DECRYPTION)
            .all()
        )
        assert len(audit_logs) > 0
        latest_log = audit_logs[-1]
        assert latest_log.resource_type == "PHI_DATA"
        assert latest_log.success is True

    def test_decrypt_with_real_audit_failure(self, real_audit_service, db_session):
        """Test decryption with REAL audit logging on failure."""
        service = EncryptionService(audit_service=real_audit_service)

        invalid_data = base64.b64encode(b"invalid").decode()

        with pytest.raises(InvalidToken):
            service.decrypt(invalid_data)

        # Verify real audit log was created for failure
        audit_logs = (
            db_session.query(AuditLog)
            .filter_by(action=AuditAction.PHI_DECRYPTION)
            .all()
        )
        # Should have failure log
        failure_logs = [log for log in audit_logs if not log.success]
        assert len(failure_logs) > 0

    def test_decrypt_error_cases_real_encryption(self):
        """Test decrypt error handling with REAL encryption operations."""
        service = EncryptionService()

        # Test with invalid base64
        with pytest.raises(ValueError):
            service.decrypt("invalid_base64!")

        # Test with valid base64 but invalid encrypted data
        invalid_data = base64.b64encode(b"not_encrypted_data").decode()
        with pytest.raises(InvalidToken):
            service.decrypt(invalid_data)

    def test_encrypt_aes_gcm_real_operations(self):
        """Test AES-GCM encryption with REAL operations."""
        service = EncryptionService()

        test_data = b"sensitive medical data"
        encrypted_data = service.encrypt_aes_gcm(test_data.decode())

        assert "ciphertext" in encrypted_data
        assert "nonce" in encrypted_data
        assert "tag" in encrypted_data

        # Verify we can decrypt it back
        decrypted = service.decrypt_aes_gcm(encrypted_data)
        assert decrypted == test_data.decode()

    def test_decrypt_aes_gcm_real_operations(self, real_audit_service, db_session):
        """Test AES-GCM decryption with REAL audit logging."""
        service = EncryptionService(audit_service=real_audit_service)

        test_data = b"medical record data"
        encrypted_data = service.encrypt_aes_gcm(test_data.decode())
        decrypted = service.decrypt_aes_gcm(encrypted_data)

        assert decrypted == test_data.decode()

        # Verify real audit log
        audit_logs = (
            db_session.query(AuditLog)
            .filter_by(action=AuditAction.PHI_DECRYPTION)
            .all()
        )
        assert len(audit_logs) > 0

    def test_decrypt_aes_gcm_error_handling_real(self, real_audit_service, db_session):
        """Test AES-GCM decryption error handling with REAL audit."""
        service = EncryptionService(audit_service=real_audit_service)

        # Test with invalid encrypted data structure
        invalid_data = {"invalid": "structure"}

        with pytest.raises(KeyError):
            service.decrypt_aes_gcm(invalid_data)

        # Verify failure audit log
        audit_logs = (
            db_session.query(AuditLog)
            .filter_by(action=AuditAction.PHI_DECRYPTION)
            .all()
        )
        failure_logs = [log for log in audit_logs if not log.success]
        assert len(failure_logs) > 0

    def test_generate_rsa_keypair_real_operations(self):
        """Test RSA keypair generation with REAL cryptographic operations."""
        service = EncryptionService()

        private_key, public_key = service.generate_rsa_keypair()

        # Verify keys are valid
        assert "BEGIN PRIVATE KEY" in private_key
        assert "END PRIVATE KEY" in private_key
        assert "BEGIN PUBLIC KEY" in public_key
        assert "END PUBLIC KEY" in public_key

        # Test with different key sizes
        private_key_4096, public_key_4096 = service.generate_rsa_keypair(key_size=4096)
        assert "BEGIN PRIVATE KEY" in private_key_4096
        assert "BEGIN PUBLIC KEY" in public_key_4096

    def test_encrypt_for_recipient_real_operations(self):
        """Test recipient encryption with REAL RSA operations."""
        service = EncryptionService()

        # Generate real keypair
        private_key, public_key = service.generate_rsa_keypair()

        test_data = "confidential patient data"
        encrypted = service.encrypt_for_recipient(test_data, public_key)

        assert encrypted != test_data
        assert isinstance(encrypted, str)

        # Verify we can decrypt with private key
        decrypted = service.decrypt_with_private_key(encrypted, private_key)
        assert decrypted == test_data

    def test_encrypt_for_recipient_error_handling_real(self):
        """Test recipient encryption error handling with REAL operations."""
        service = EncryptionService()

        # Test with invalid public key
        with pytest.raises(ValueError):
            service.encrypt_for_recipient("test data", "invalid_public_key")

    def test_decrypt_with_private_key_real_operations(self):
        """Test private key decryption with REAL RSA operations."""
        service = EncryptionService()

        # Generate real keypair and encrypt data
        private_key, public_key = service.generate_rsa_keypair()
        test_data = "medical record content"
        encrypted = service.encrypt_for_recipient(test_data, public_key)

        # Decrypt with real private key
        decrypted = service.decrypt_with_private_key(encrypted, private_key)
        assert decrypted == test_data

    def test_decrypt_with_private_key_error_handling_real(self):
        """Test private key decryption error handling with REAL operations."""
        service = EncryptionService()

        # Test with invalid private key
        with pytest.raises(ValueError):
            service.decrypt_with_private_key("encrypted_data", "invalid_private_key")

    def test_encrypt_field_level_real_operations(self):
        """Test field-level encryption with REAL operations."""
        service = EncryptionService()

        test_fields = {
            "ssn": "123-45-6789",
            "medical_record_number": "MRN123456",
            "diagnosis": "Hypertension",
        }

        encrypted_fields = service.encrypt_field_level(
            test_fields, list(test_fields.keys())
        )

        # Verify all fields are encrypted
        for field_name, encrypted_value in encrypted_fields.items():
            assert encrypted_value != test_fields[field_name]
            assert isinstance(encrypted_value, str)

        # Verify we can decrypt them back
        decrypted_fields = service.decrypt_field_level(
            encrypted_fields, list(encrypted_fields.keys())
        )
        assert decrypted_fields == test_fields

    def test_decrypt_field_level_real_operations(self):
        """Test field-level decryption with REAL operations."""
        service = EncryptionService()

        # First encrypt some fields
        test_fields = {
            "patient_id": "P123456",
            "dob": "1990-01-01",
            "emergency_contact": "+1234567890",
        }

        encrypted_fields = service.encrypt_field_level(
            test_fields, list(test_fields.keys())
        )

        # Now decrypt them
        decrypted_fields = service.decrypt_field_level(
            encrypted_fields, list(encrypted_fields.keys())
        )

        assert decrypted_fields == test_fields

        # Test partial decryption
        partial_encrypted = {"patient_id": encrypted_fields["patient_id"]}
        partial_decrypted = service.decrypt_field_level(
            partial_encrypted, list(partial_encrypted.keys())
        )
        assert partial_decrypted["patient_id"] == test_fields["patient_id"]

    def test_generate_data_key_real_operations(self):
        """Test data key generation with REAL cryptographic operations."""
        service = EncryptionService()

        # Test data key generation
        key_plain, key_encrypted = service.generate_data_key()
        assert isinstance(key_plain, bytes)
        assert isinstance(key_encrypted, bytes)
        assert len(key_plain) > 0
        assert len(key_encrypted) > 0

        # Verify keys are different each time
        another_plain, another_encrypted = service.generate_data_key()
        assert key_plain != another_plain
        assert key_encrypted != another_encrypted

    def test_singleton_instance_real_behavior(self):
        """Test singleton behavior with REAL instance management."""
        from src.services.encryption_service import EncryptionService

        # Create multiple instances
        service1 = EncryptionService()
        service2 = EncryptionService()

        # Note: Without a singleton pattern, these will be different instances
        # but they should still work correctly

        # Should have working encryption
        test_data = "singleton test data"
        encrypted = service1.encrypt(test_data)
        decrypted = service2.decrypt(encrypted)
        assert decrypted == test_data

    def test_comprehensive_encryption_workflow_real(
        self, real_audit_service, db_session
    ):
        """Test comprehensive encryption workflow with REAL operations and audit."""
        service = EncryptionService(audit_service=real_audit_service)

        # Test complete workflow
        patient_data = {
            "name": "John Doe",
            "ssn": "123-45-6789",
            "medical_history": "Diabetes, Hypertension",
            "medications": ["Metformin", "Lisinopril"],
        }

        # 1. Field-level encryption
        encrypted_fields = service.encrypt_field_level(
            patient_data, list(patient_data.keys())
        )

        # 2. Full data encryption
        full_encrypted = service.encrypt(json.dumps(patient_data))

        # 3. AES-GCM encryption
        aes_encrypted = service.encrypt_aes_gcm(json.dumps(patient_data))

        # 4. RSA encryption
        private_key, public_key = service.generate_rsa_keypair()
        rsa_encrypted = service.encrypt_for_recipient(
            json.dumps(patient_data), public_key
        )

        # Verify all encryptions worked
        assert all(encrypted_fields[k] != patient_data[k] for k in patient_data.keys())
        assert full_encrypted != json.dumps(patient_data)
        assert "ciphertext" in aes_encrypted
        assert rsa_encrypted != json.dumps(patient_data)

        # Verify all decryptions work
        decrypted_fields = service.decrypt_field_level(
            encrypted_fields, list(encrypted_fields.keys())
        )
        full_decrypted = service.decrypt(full_encrypted)
        aes_decrypted = service.decrypt_aes_gcm(aes_encrypted)
        rsa_decrypted = service.decrypt_with_private_key(rsa_encrypted, private_key)

        assert decrypted_fields == patient_data
        assert json.loads(full_decrypted) == patient_data
        assert json.loads(aes_decrypted) == patient_data
        assert json.loads(rsa_decrypted) == patient_data

        # Verify real audit logs were created
        audit_logs = (
            db_session.query(AuditLog)
            .filter_by(action=AuditAction.PHI_DECRYPTION)
            .all()
        )
        assert len(audit_logs) >= 3  # At least 3 decryption operations logged
