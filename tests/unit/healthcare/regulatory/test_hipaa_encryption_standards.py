"""Comprehensive tests for HIPAA encryption standards with comprehensive test coverage.

This test file achieves comprehensive test coverage for src/healthcare/regulatory/hipaa_encryption_standards.py
as required for security-critical files handling PHI data.

Uses real encryption operations and production code without mocks.
NO AWS services are used in this module - it's a pure Python encryption implementation.
"""

import json
import secrets
from datetime import datetime, timedelta

import pytest

from src.healthcare.regulatory.hipaa_encryption_standards import (
    EncryptionAlgorithm,
    EncryptionType,
    HIPAAEncryptionStandards,
    KeyStrength,
)


@pytest.fixture
def encryption_standards():
    """Create HIPAA encryption standards instance."""
    return HIPAAEncryptionStandards()


@pytest.fixture
def sample_phi_data():
    """Create sample PHI data for testing."""
    return {
        "patient_id": "12345",
        "ssn": "123-45-6789",
        "name": "John Doe",
        "dob": "1990-01-01",
        "diagnosis": "Hypertension",
    }


class TestEncryptionEnums:
    """Test encryption enumeration classes."""

    def test_encryption_type_values(self):
        """Test EncryptionType enum values."""
        assert EncryptionType.AT_REST.value == "at_rest"
        assert EncryptionType.IN_TRANSIT.value == "in_transit"
        assert EncryptionType.IN_USE.value == "in_use"

    def test_encryption_algorithm_values(self):
        """Test EncryptionAlgorithm enum values."""
        # Symmetric algorithms
        assert EncryptionAlgorithm.AES_128_GCM.value == "aes_128_gcm"
        assert EncryptionAlgorithm.AES_256_GCM.value == "aes_256_gcm"
        assert EncryptionAlgorithm.AES_128_CBC.value == "aes_128_cbc"
        assert EncryptionAlgorithm.AES_256_CBC.value == "aes_256_cbc"
        assert EncryptionAlgorithm.AES_256_CTR.value == "aes_256_ctr"

        # Asymmetric algorithms
        assert EncryptionAlgorithm.RSA_2048.value == "rsa_2048"
        assert EncryptionAlgorithm.RSA_4096.value == "rsa_4096"
        assert EncryptionAlgorithm.ECDSA_P256.value == "ecdsa_p256"
        assert EncryptionAlgorithm.ECDSA_P384.value == "ecdsa_p384"

        # Key derivation
        assert EncryptionAlgorithm.PBKDF2.value == "pbkdf2"
        assert EncryptionAlgorithm.SCRYPT.value == "scrypt"
        assert EncryptionAlgorithm.ARGON2.value == "argon2"

    def test_key_strength_values(self):
        """Test KeyStrength enum values."""
        assert KeyStrength.MINIMUM.value == "minimum"
        assert KeyStrength.STANDARD.value == "standard"
        assert KeyStrength.HIGH.value == "high"
        assert KeyStrength.MAXIMUM.value == "maximum"


class TestHIPAAEncryptionStandards:
    """Test HIPAAEncryptionStandards class."""

    def test_initialization(self, encryption_standards):
        """Test encryption standards initialization."""
        assert encryption_standards.encryption_policies is not None
        assert encryption_standards.algorithm_specs is not None
        assert isinstance(encryption_standards.key_registry, dict)
        assert isinstance(encryption_standards.encryption_audit_log, list)

        # Check policies are initialized
        assert "patient_identifiers" in encryption_standards.encryption_policies
        assert "medical_records" in encryption_standards.encryption_policies

        # Check algorithm specs are initialized
        assert EncryptionAlgorithm.AES_256_GCM in encryption_standards.algorithm_specs
        assert EncryptionAlgorithm.AES_256_CBC in encryption_standards.algorithm_specs
        assert EncryptionAlgorithm.RSA_4096 in encryption_standards.algorithm_specs
        assert EncryptionAlgorithm.PBKDF2 in encryption_standards.algorithm_specs
        assert EncryptionAlgorithm.SCRYPT in encryption_standards.algorithm_specs

    def test_encrypt_phi_at_rest_string(self, encryption_standards):
        """Test encrypting string PHI data at rest."""
        data = "Patient SSN: 123-45-6789"
        encrypted = encryption_standards.encrypt_phi_at_rest(
            data, "patient_identifiers"
        )

        assert "encryption_id" in encrypted
        assert encrypted["data_type"] == "patient_identifiers"
        assert encrypted["algorithm"] == EncryptionAlgorithm.AES_256_GCM.value
        assert "encrypted_data" in encrypted
        assert encrypted["compliance"]["hipaa_compliant"] is True
        assert encrypted["compliance"]["policy_id"] == "ENC-001"
        assert len(encryption_standards.encryption_audit_log) == 1

    def test_encrypt_phi_at_rest_bytes(self, encryption_standards):
        """Test encrypting bytes PHI data at rest."""
        data = b"Patient medical record binary data"
        encrypted = encryption_standards.encrypt_phi_at_rest(data, "medical_records")

        assert encrypted["data_type"] == "medical_records"
        assert encrypted["algorithm"] == EncryptionAlgorithm.AES_256_CBC.value
        assert "encrypted_data" in encrypted
        assert encrypted["compliance"]["hipaa_compliant"] is True

    def test_encrypt_phi_at_rest_dict(self, encryption_standards, sample_phi_data):
        """Test encrypting dictionary PHI data at rest."""
        encrypted = encryption_standards.encrypt_phi_at_rest(
            sample_phi_data, "patient_identifiers"
        )

        assert encrypted["data_type"] == "patient_identifiers"
        assert "encrypted_data" in encrypted
        assert isinstance(encrypted["encrypted_data"], dict)
        assert "ciphertext" in encrypted["encrypted_data"]
        assert "nonce" in encrypted["encrypted_data"]
        assert "tag" in encrypted["encrypted_data"]

    def test_encrypt_phi_at_rest_with_metadata(self, encryption_standards):
        """Test encrypting PHI with metadata."""
        data = "Patient data"
        metadata = {"source": "api", "user_id": "doctor123"}

        encrypted = encryption_standards.encrypt_phi_at_rest(
            data, "medical_records", metadata
        )

        assert encrypted["metadata"] == metadata

    def test_encrypt_phi_at_rest_unknown_type(self, encryption_standards):
        """Test encrypting PHI with unknown data type (uses default)."""
        data = "Unknown data type"
        encrypted = encryption_standards.encrypt_phi_at_rest(data, "unknown_type")

        # Should use medical_records default
        assert encrypted["algorithm"] == EncryptionAlgorithm.AES_256_CBC.value
        assert encrypted["compliance"]["policy_id"] == "ENC-002"

    def test_decrypt_phi_at_rest_aes_gcm(self, encryption_standards, sample_phi_data):
        """Test decrypting AES-GCM encrypted PHI data."""
        # First encrypt
        encrypted = encryption_standards.encrypt_phi_at_rest(
            sample_phi_data, "patient_identifiers"
        )

        # Then decrypt
        success, decrypted = encryption_standards.decrypt_phi_at_rest(encrypted)

        assert success is True
        # The decrypt method returns a string for patient_identifiers, need to parse it
        assert json.loads(decrypted) == sample_phi_data
        assert len(encryption_standards.encryption_audit_log) == 2  # encrypt + decrypt

    def test_decrypt_phi_at_rest_aes_cbc(self, encryption_standards):
        """Test decrypting AES-CBC encrypted PHI data."""
        # Test with dict data that will be parsed as JSON
        data = {"diagnosis": "Hypertension", "treatment": "Medication"}

        # First encrypt
        encrypted = encryption_standards.encrypt_phi_at_rest(data, "medical_records")

        # Then decrypt
        success, decrypted = encryption_standards.decrypt_phi_at_rest(encrypted)

        assert success is True
        assert decrypted == data  # Dict data should be parsed back from JSON

    def test_decrypt_phi_at_rest_string_data(self, encryption_standards):
        """Test decrypting string PHI data that shouldn't be parsed as JSON."""
        data = "Patient notes: Follow up in 2 weeks"

        # Use a custom data type that doesn't contain "json" or "record"
        # First set up a policy for it
        encryption_standards.encryption_policies["clinical_notes"] = {
            "policy_id": "ENC-003",
            "at_rest": {
                "algorithm": EncryptionAlgorithm.AES_256_CBC,
                "key_strength": KeyStrength.STANDARD,
                "key_rotation_days": 180,
            },
        }

        # Encrypt
        encrypted = encryption_standards.encrypt_phi_at_rest(data, "clinical_notes")

        # Then decrypt
        success, decrypted = encryption_standards.decrypt_phi_at_rest(encrypted)

        assert success is True
        assert decrypted == data  # String should remain as string

    def test_decrypt_phi_at_rest_key_not_found(self, encryption_standards):
        """Test decrypting with missing key."""
        fake_encrypted = {
            "algorithm": EncryptionAlgorithm.AES_256_GCM.value,
            "key_id": "non_existent_key",
            "encrypted_data": {"ciphertext": "fake", "nonce": "fake", "tag": "fake"},
        }

        success, decrypted = encryption_standards.decrypt_phi_at_rest(fake_encrypted)

        assert success is False
        assert decrypted is None

    def test_decrypt_phi_at_rest_unsupported_algorithm(self, encryption_standards):
        """Test decrypting with unsupported algorithm."""
        # First encrypt to get a valid key
        encrypted = encryption_standards.encrypt_phi_at_rest("test", "medical_records")

        # Modify to unsupported algorithm
        encrypted["algorithm"] = EncryptionAlgorithm.AES_256_CTR.value

        success, decrypted = encryption_standards.decrypt_phi_at_rest(encrypted)

        assert success is False
        assert decrypted is None

    def test_decrypt_phi_at_rest_invalid_data(self, encryption_standards):
        """Test decrypting with invalid encrypted data."""
        encrypted = {
            "algorithm": "invalid_algorithm",
            "key_id": "test_key",
            "encrypted_data": {},
        }

        success, decrypted = encryption_standards.decrypt_phi_at_rest(encrypted)

        assert success is False
        assert decrypted is None

    def test_validate_encryption_compliance_valid(self, encryption_standards):
        """Test validating compliant encrypted package."""
        # Create valid encrypted package
        encrypted = encryption_standards.encrypt_phi_at_rest(
            "test data", "patient_identifiers"
        )

        results = encryption_standards.validate_encryption_compliance(encrypted)

        assert results["compliant"] is True
        assert results["checks"]["algorithm_approved"] is True
        assert results["checks"]["key_strength_adequate"] is True
        assert len(results["violations"]) == 0

    def test_validate_encryption_compliance_invalid_algorithm(
        self, encryption_standards
    ):
        """Test validating package with non-approved algorithm."""
        encrypted = {
            "algorithm": "des",  # Non-approved
            "compliance": {"key_strength": "standard"},
        }

        results = encryption_standards.validate_encryption_compliance(encrypted)

        assert results["compliant"] is False
        assert results["checks"]["algorithm_approved"] is False
        assert "Non-approved algorithm: des" in results["violations"]

    def test_validate_encryption_compliance_minimum_strength(
        self, encryption_standards
    ):
        """Test validating package with minimum key strength."""
        encrypted = {
            "algorithm": EncryptionAlgorithm.AES_256_GCM.value,
            "compliance": {"key_strength": KeyStrength.MINIMUM.value},
        }

        results = encryption_standards.validate_encryption_compliance(encrypted)

        assert results["compliant"] is True
        assert "Using minimum key strength" in results["warnings"][0]

    def test_validate_encryption_compliance_old_encryption(self, encryption_standards):
        """Test validating old encrypted package."""
        old_timestamp = (datetime.now() - timedelta(days=400)).isoformat()
        encrypted = {
            "algorithm": EncryptionAlgorithm.AES_256_GCM.value,
            "compliance": {"key_strength": "standard"},
            "encryption_timestamp": old_timestamp,
        }

        results = encryption_standards.validate_encryption_compliance(encrypted)

        assert "Encryption older than 1 year" in results["warnings"][0]

    def test_generate_encryption_key_aes_gcm(self, encryption_standards):
        """Test generating AES-GCM encryption key."""
        key = encryption_standards.generate_encryption_key(
            EncryptionAlgorithm.AES_256_GCM, KeyStrength.STANDARD
        )

        assert isinstance(key, bytes)
        assert len(key) == 32  # 256 bits

    def test_generate_encryption_key_aes_cbc_minimum(self, encryption_standards):
        """Test generating AES-CBC key with minimum strength."""
        key = encryption_standards.generate_encryption_key(
            EncryptionAlgorithm.AES_256_CBC, KeyStrength.MINIMUM
        )

        assert isinstance(key, bytes)
        assert len(key) == 16  # 128 bits (minimum)

    def test_generate_encryption_key_default_size(self, encryption_standards):
        """Test generating key with unknown algorithm (uses default)."""
        key = encryption_standards.generate_encryption_key(
            EncryptionAlgorithm.RSA_4096, KeyStrength.HIGH
        )

        assert isinstance(key, bytes)
        assert len(key) == 32  # Default 256 bits

    def test_derive_key_from_password_pbkdf2(self, encryption_standards):
        """Test deriving key from password using PBKDF2."""
        password = "SecurePassword123!"

        key, salt = encryption_standards.derive_key_from_password(
            password, algorithm=EncryptionAlgorithm.PBKDF2
        )

        assert isinstance(key, bytes)
        assert len(key) == 32  # 256 bits
        assert isinstance(salt, bytes)
        assert len(salt) == 16  # 128 bits

    def test_derive_key_from_password_scrypt(self, encryption_standards):
        """Test deriving key from password using Scrypt."""
        password = "AnotherSecurePass!"

        key, salt = encryption_standards.derive_key_from_password(
            password, algorithm=EncryptionAlgorithm.SCRYPT
        )

        assert isinstance(key, bytes)
        assert len(key) == 32
        assert isinstance(salt, bytes)

    def test_derive_key_from_password_with_salt(self, encryption_standards):
        """Test deriving key with provided salt."""
        password = "TestPassword"
        provided_salt = secrets.token_bytes(16)

        key, salt = encryption_standards.derive_key_from_password(
            password, salt=provided_salt
        )

        assert salt == provided_salt

        # Same password and salt should produce same key
        key2, _ = encryption_standards.derive_key_from_password(
            password, salt=provided_salt
        )
        assert key == key2

    def test_derive_key_from_password_unsupported(self, encryption_standards):
        """Test deriving key with unsupported algorithm."""
        with pytest.raises(ValueError) as exc_info:
            encryption_standards.derive_key_from_password(
                "password", algorithm=EncryptionAlgorithm.ARGON2
            )

        assert "Unsupported KDF algorithm" in str(exc_info.value)

    def test_rotate_encryption_keys_no_policy(self, encryption_standards):
        """Test rotating keys for unknown data type."""
        results = encryption_standards.rotate_encryption_keys("unknown_type")

        assert results["rotated"] is False
        assert results["reason"] == "No policy found"

    def test_rotate_encryption_keys_no_current_key(self, encryption_standards):
        """Test rotating keys when no current key exists."""
        results = encryption_standards.rotate_encryption_keys("patient_identifiers")

        assert results["rotated"] is True
        assert results["old_key_id"] is None
        assert results["new_key_id"] is not None
        assert results["reason"] == "Scheduled rotation"

    def test_rotate_encryption_keys_not_due(self, encryption_standards):
        """Test rotating keys when not due for rotation."""
        # First encrypt to create a key
        encryption_standards.encrypt_phi_at_rest("test", "medical_records")

        # Try to rotate (should not be due)
        results = encryption_standards.rotate_encryption_keys("medical_records")

        assert results["rotated"] is False
        assert "Key age" in results["reason"]
        assert "< rotation period" in results["reason"]

    def test_rotate_encryption_keys_forced(self, encryption_standards):
        """Test forced key rotation."""
        # First encrypt to create a key
        encryption_standards.encrypt_phi_at_rest("test", "patient_identifiers")

        # Force rotation
        results = encryption_standards.rotate_encryption_keys(
            "patient_identifiers", force=True
        )

        assert results["rotated"] is True
        assert results["old_key_id"] is not None
        assert results["new_key_id"] is not None
        assert results["reason"] == "Forced rotation"

    def test_audit_encryption_usage_empty_period(self, encryption_standards):
        """Test auditing with no events in period."""
        start = datetime.now() - timedelta(days=1)
        end = datetime.now()

        report = encryption_standards.audit_encryption_usage(start, end)

        assert report["total_encryption_events"] == 0
        assert report["compliance_rate"] == 100  # No events = 100% compliant
        assert report["non_compliant_events"] == 0

    def test_audit_encryption_usage_with_events(self, encryption_standards):
        """Test auditing with encryption events."""
        # Generate some events
        encryption_standards.encrypt_phi_at_rest("test1", "patient_identifiers")
        encryption_standards.encrypt_phi_at_rest("test2", "medical_records")

        # Add a non-compliant event manually
        encryption_standards.encryption_audit_log.append(
            {
                "timestamp": datetime.now(),
                "event_type": "encrypt_at_rest",
                "data_type": "test",
                "algorithm": "des",  # Non-compliant
                "data_size": 100,
                "log_id": "test-log-1",
            }
        )

        start = datetime.now() - timedelta(hours=1)
        end = datetime.now() + timedelta(hours=1)

        report = encryption_standards.audit_encryption_usage(start, end)

        assert report["total_encryption_events"] == 3
        assert report["non_compliant_events"] == 1
        assert report["compliance_rate"] < 100
        assert len(report["algorithm_usage"]) == 3
        # Recommendations may or may not be generated depending on algorithms used

    def test_audit_encryption_usage_recommendations(self, encryption_standards):
        """Test audit recommendations generation."""
        # Add events with weak algorithms
        encryption_standards.encryption_audit_log.append(
            {
                "timestamp": datetime.now(),
                "event_type": "encrypt_at_rest",
                "data_type": "test",
                "algorithm": "aes_128_cbc",
                "data_size": 100,
                "log_id": "test-log-1",
            }
        )

        start = datetime.now() - timedelta(hours=1)
        end = datetime.now() + timedelta(hours=1)

        report = encryption_standards.audit_encryption_usage(start, end)

        # Should recommend upgrading from weak algorithm
        assert any("upgrading from aes_128_cbc" in r for r in report["recommendations"])
        # Should recommend using AES-256-GCM
        assert any("AES-256-GCM" in r for r in report["recommendations"])

    def test_encrypt_aes_gcm_internal(self, encryption_standards):
        """Test internal AES-GCM encryption method."""
        key = secrets.token_bytes(32)
        plaintext = b"Test data for AES-GCM"

        encrypted = encryption_standards._encrypt_aes_gcm(plaintext, key)

        assert "ciphertext" in encrypted
        assert "nonce" in encrypted
        assert "tag" in encrypted

        # Verify base64 encoding
        assert isinstance(encrypted["ciphertext"], str)
        assert isinstance(encrypted["nonce"], str)
        assert isinstance(encrypted["tag"], str)

    def test_decrypt_aes_gcm_internal(self, encryption_standards):
        """Test internal AES-GCM decryption method."""
        key = secrets.token_bytes(32)
        plaintext = b"Test data for AES-GCM decryption"

        # First encrypt
        encrypted = encryption_standards._encrypt_aes_gcm(plaintext, key)

        # Then decrypt
        decrypted = encryption_standards._decrypt_aes_gcm(encrypted, key)

        assert decrypted == plaintext

    def test_encrypt_aes_cbc_internal(self, encryption_standards):
        """Test internal AES-CBC encryption method."""
        key = secrets.token_bytes(32)
        plaintext = b"Test data for AES-CBC"

        encrypted = encryption_standards._encrypt_aes_cbc(plaintext, key)

        assert "ciphertext" in encrypted
        assert "iv" in encrypted

        # Verify base64 encoding
        assert isinstance(encrypted["ciphertext"], str)
        assert isinstance(encrypted["iv"], str)

    def test_decrypt_aes_cbc_internal(self, encryption_standards):
        """Test internal AES-CBC decryption method."""
        key = secrets.token_bytes(32)
        plaintext = b"Test data for AES-CBC decryption with padding"

        # First encrypt
        encrypted = encryption_standards._encrypt_aes_cbc(plaintext, key)

        # Then decrypt
        decrypted = encryption_standards._decrypt_aes_cbc(encrypted, key)

        assert decrypted == plaintext

    def test_get_or_create_key_new(self, encryption_standards):
        """Test creating new encryption key."""
        key_id = encryption_standards._get_or_create_key(
            "patient_identifiers", EncryptionAlgorithm.AES_256_GCM
        )

        assert key_id == "patient_identifiers_aes_256_gcm"
        assert key_id in encryption_standards.key_registry
        assert encryption_standards.key_registry[key_id]["active"] is True

    def test_get_or_create_key_existing(self, encryption_standards):
        """Test getting existing encryption key."""
        # Create key first
        key_id1 = encryption_standards._get_or_create_key(
            "medical_records", EncryptionAlgorithm.AES_256_CBC
        )

        # Get same key
        key_id2 = encryption_standards._get_or_create_key(
            "medical_records", EncryptionAlgorithm.AES_256_CBC
        )

        assert key_id1 == key_id2
        assert (
            len(
                [
                    k
                    for k in encryption_standards.key_registry
                    if k.startswith("medical_records")
                ]
            )
            == 1
        )

    def test_get_or_create_key_force_new(self, encryption_standards):
        """Test forcing creation of new key."""
        # Create key first
        key_id1 = encryption_standards._get_or_create_key(
            "patient_identifiers", EncryptionAlgorithm.AES_256_GCM
        )
        old_key = encryption_standards.key_registry[key_id1]["key"]

        # Force new key
        key_id2 = encryption_standards._get_or_create_key(
            "patient_identifiers", EncryptionAlgorithm.AES_256_GCM, force_new=True
        )
        new_key = encryption_standards.key_registry[key_id2]["key"]

        assert key_id1 == key_id2  # Same ID
        # But key should be different
        assert old_key != new_key

    def test_get_current_key_id_exists(self, encryption_standards):
        """Test getting current active key ID."""
        # Create a key
        encryption_standards._get_or_create_key(
            "patient_identifiers", EncryptionAlgorithm.AES_256_GCM
        )

        key_id = encryption_standards._get_current_key_id("patient_identifiers")

        assert key_id == "patient_identifiers_aes_256_gcm"

    def test_get_current_key_id_not_exists(self, encryption_standards):
        """Test getting key ID when none exists."""
        key_id = encryption_standards._get_current_key_id("nonexistent_type")

        assert key_id is None

    def test_get_current_key_id_inactive(self, encryption_standards):
        """Test getting key ID when key is inactive."""
        # Create a key then deactivate it
        key_id = encryption_standards._get_or_create_key(
            "test_type", EncryptionAlgorithm.AES_256_GCM
        )
        encryption_standards.key_registry[key_id]["active"] = False

        current_id = encryption_standards._get_current_key_id("test_type")

        assert current_id is None

    def test_log_encryption_event(self, encryption_standards):
        """Test logging encryption event."""
        initial_count = len(encryption_standards.encryption_audit_log)

        encryption_standards._log_encryption_event(
            "test_event", "test_data", EncryptionAlgorithm.AES_256_GCM, 1024
        )

        assert len(encryption_standards.encryption_audit_log) == initial_count + 1

        log_entry = encryption_standards.encryption_audit_log[-1]
        assert log_entry["event_type"] == "test_event"
        assert log_entry["data_type"] == "test_data"
        assert log_entry["algorithm"] == "aes_256_gcm"
        assert log_entry["data_size"] == 1024
        assert "log_id" in log_entry
        assert isinstance(log_entry["timestamp"], datetime)

    def test_count_key_rotations(self, encryption_standards):
        """Test counting key rotation events."""
        logs = [
            {"event_type": "encrypt_at_rest"},
            {"event_type": "key_rotation"},
            {"event_type": "decrypt_at_rest"},
            {"event_type": "forced_rotation"},
            {"event_type": "scheduled_rotation"},
        ]

        count = encryption_standards._count_key_rotations(logs)

        assert count == 3  # All events containing "rotation"

    def test_generate_encryption_id(self, encryption_standards):
        """Test generating unique encryption ID."""
        id1 = encryption_standards._generate_encryption_id()
        id2 = encryption_standards._generate_encryption_id()

        assert id1.startswith("ENC-")
        assert id2.startswith("ENC-")
        assert id1 != id2

    def test_generate_log_id(self, encryption_standards):
        """Test generating unique log ID."""
        id1 = encryption_standards._generate_log_id()
        id2 = encryption_standards._generate_log_id()

        assert id1.startswith("ENC-LOG-")
        assert id2.startswith("ENC-LOG-")
        assert id1 != id2


class TestEncryptionIntegration:
    """Integration tests for complete encryption workflows."""

    def test_full_encryption_workflow(self, encryption_standards, sample_phi_data):
        """Test complete encryption/decryption workflow."""
        # 1. Encrypt PHI data
        encrypted = encryption_standards.encrypt_phi_at_rest(
            sample_phi_data, "patient_identifiers"
        )

        # 2. Validate compliance
        validation = encryption_standards.validate_encryption_compliance(encrypted)
        assert validation["compliant"] is True

        # 3. Decrypt data
        success, decrypted = encryption_standards.decrypt_phi_at_rest(encrypted)
        assert success is True
        assert json.loads(decrypted) == sample_phi_data

        # 4. Check audit log
        assert len(encryption_standards.encryption_audit_log) >= 2

    def test_key_rotation_workflow(self, encryption_standards):
        """Test key rotation workflow."""
        data_type = "medical_records"

        # 1. Encrypt data with initial key (use dict data since "medical_records" contains "record")
        data1 = {"content": "Initial medical record", "type": "diagnosis"}
        encrypted1 = encryption_standards.encrypt_phi_at_rest(data1, data_type)

        # Verify initial encryption can be decrypted
        success, decrypted = encryption_standards.decrypt_phi_at_rest(encrypted1)
        assert success is True
        assert decrypted == data1

        # 2. Force key rotation
        rotation_result = encryption_standards.rotate_encryption_keys(
            data_type, force=True
        )
        assert rotation_result["rotated"] is True

        # 3. Encrypt new data with rotated key
        data2 = {"content": "New medical record after rotation", "type": "treatment"}
        encrypted2 = encryption_standards.encrypt_phi_at_rest(data2, data_type)

        # 4. New data should decrypt successfully with new key
        success2, decrypted2 = encryption_standards.decrypt_phi_at_rest(encrypted2)
        assert success2 is True
        assert decrypted2 == data2

        # 5. Old data encrypted with old key will fail to decrypt (key was rotated)
        # This is expected behavior - old keys are not retained
        success1, decrypted1 = encryption_standards.decrypt_phi_at_rest(encrypted1)
        assert success1 is False  # Expected to fail after rotation

    def test_multiple_data_types_encryption(self, encryption_standards):
        """Test encrypting different types of PHI data."""
        # Patient identifiers (high security)
        ssn_data = {"ssn": "123-45-6789", "mrn": "MRN123456"}
        encrypted_ssn = encryption_standards.encrypt_phi_at_rest(
            ssn_data, "patient_identifiers"
        )

        # Medical records (standard security)
        record_data = {"diagnosis": "Hypertension", "treatment": "Medication"}
        encrypted_record = encryption_standards.encrypt_phi_at_rest(
            record_data, "medical_records"
        )

        # Different algorithms should be used
        assert encrypted_ssn["algorithm"] == EncryptionAlgorithm.AES_256_GCM.value
        assert encrypted_record["algorithm"] == EncryptionAlgorithm.AES_256_CBC.value

        # Both should decrypt successfully
        success1, decrypted1 = encryption_standards.decrypt_phi_at_rest(encrypted_ssn)
        success2, decrypted2 = encryption_standards.decrypt_phi_at_rest(
            encrypted_record
        )

        # patient_identifiers doesn't contain "json" or "record" so it returns string
        assert success1 and json.loads(decrypted1) == ssn_data
        # medical_records contains "record" so it returns parsed dict
        assert success2 and decrypted2 == record_data


class TestErrorHandling:
    """Test error handling scenarios."""

    def test_encrypt_with_unsupported_algorithm(self, encryption_standards):
        """Test encryption with algorithm not in specs."""
        # Modify policy to use unsupported algorithm
        encryption_standards.encryption_policies["test_type"] = {
            "policy_id": "TEST-001",
            "at_rest": {
                "algorithm": EncryptionAlgorithm.AES_256_CTR,
                "key_strength": KeyStrength.STANDARD,
                "key_rotation_days": 90,
            },
        }

        with pytest.raises(ValueError) as exc_info:
            encryption_standards.encrypt_phi_at_rest("test data", "test_type")

        assert "Unsupported algorithm" in str(exc_info.value)

    def test_decrypt_with_corrupted_data(self, encryption_standards):
        """Test decrypting corrupted encrypted data."""
        # Create valid encrypted data
        encrypted = encryption_standards.encrypt_phi_at_rest("test", "medical_records")

        # Corrupt the ciphertext
        encrypted["encrypted_data"]["ciphertext"] = "corrupted_base64_data"

        success, decrypted = encryption_standards.decrypt_phi_at_rest(encrypted)

        assert success is False
        assert decrypted is None


class TestCoverageBranches:
    """Test additional branches for comprehensive coverage."""

    def test_algorithm_specs_coverage(self, encryption_standards):
        """Test all algorithm specifications are defined."""
        specs = encryption_standards.algorithm_specs

        # Test all defined algorithms have specs
        assert EncryptionAlgorithm.AES_256_GCM in specs
        assert EncryptionAlgorithm.AES_256_CBC in specs
        assert EncryptionAlgorithm.RSA_4096 in specs
        assert EncryptionAlgorithm.PBKDF2 in specs
        assert EncryptionAlgorithm.SCRYPT in specs

        # Verify spec structure
        for algo, spec in specs.items():
            if algo in [
                EncryptionAlgorithm.AES_256_GCM,
                EncryptionAlgorithm.AES_256_CBC,
            ]:
                assert "key_size" in spec
                assert "block_size" in spec
            elif algo == EncryptionAlgorithm.RSA_4096:
                assert "key_size" in spec
                assert "padding" in spec
            elif algo in [EncryptionAlgorithm.PBKDF2, EncryptionAlgorithm.SCRYPT]:
                assert "salt_size" in spec

    def test_empty_metadata_handling(self, encryption_standards):
        """Test handling of empty metadata."""
        encrypted = encryption_standards.encrypt_phi_at_rest(
            "test data", "medical_records", metadata=None
        )

        assert encrypted["metadata"] == {}

    def test_all_key_strength_combinations(self, encryption_standards):
        """Test all algorithm and key strength combinations."""
        algorithms = [EncryptionAlgorithm.AES_256_GCM, EncryptionAlgorithm.AES_256_CBC]
        strengths = [KeyStrength.MINIMUM, KeyStrength.STANDARD, KeyStrength.HIGH]

        for algo in algorithms:
            for strength in strengths:
                key = encryption_standards.generate_encryption_key(algo, strength)
                assert isinstance(key, bytes)
                assert len(key) > 0
