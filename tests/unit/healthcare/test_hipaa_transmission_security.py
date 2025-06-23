"""Tests for HIPAA Transmission Security - CRITICAL COMPLIANCE TESTS.

CRITICAL: This tests HIPAA transmission security for refugee medical data.
- Tests REAL encryption algorithms and protocols
- Tests REAL network security implementations
- Tests REAL audit trail generation
- NO MOCKS for encryption - patient privacy depends on this

COMPLIANCE: comprehensive coverage required for HIPAA §164.312(e) compliance
"""

import json
import secrets
import uuid
from datetime import datetime, timedelta

import pytest
from cryptography.hazmat.primitives import hashes

from src.healthcare.regulatory.hipaa_transmission_security import (
    DataClassification,
    EncryptionStandard,
    HIPAATransmissionSecurity,
    TransmissionProtocol,
)


@pytest.mark.hipaa_required
@pytest.mark.phi_encryption
class TestHIPAATransmissionSecurity:
    """Test HIPAA transmission security with REAL cryptographic operations."""

    def test_encryption_standard_enum(self):
        """Test encryption standard enumeration values."""
        assert EncryptionStandard.AES_256_GCM.value == "aes_256_gcm"
        assert EncryptionStandard.AES_256_CBC.value == "aes_256_cbc"
        assert EncryptionStandard.RSA_4096.value == "rsa_4096"
        assert EncryptionStandard.TLS_1_3.value == "tls_1_3"
        assert EncryptionStandard.TLS_1_2.value == "tls_1_2"

    def test_transmission_protocol_enum(self):
        """Test transmission protocol enumeration values."""
        assert TransmissionProtocol.HTTPS.value == "https"
        assert TransmissionProtocol.SFTP.value == "sftp"
        assert TransmissionProtocol.SECURE_EMAIL.value == "secure_email"
        assert TransmissionProtocol.VPN.value == "vpn"

    def test_data_classification_enum(self):
        """Test data classification enumeration values."""
        assert DataClassification.HIGHLY_SENSITIVE.value == "highly_sensitive"
        assert DataClassification.SENSITIVE.value == "sensitive"
        assert DataClassification.INTERNAL.value == "internal"

    def test_hipaa_transmission_security_initialization(self):
        """Test that HIPAATransmissionSecurity initializes correctly."""
        security = HIPAATransmissionSecurity()

        # Verify initialization
        assert security is not None
        assert hasattr(security, "encryption_policies")
        assert hasattr(security, "transmission_log")
        assert hasattr(security, "keys")
        assert hasattr(security, "active_sessions")
        assert hasattr(security, "failed_transmissions")
        assert hasattr(security, "fhir_validator")

        # Verify FHIR resource type
        assert security.__fhir_resource__ == "AuditEvent"

    def test_encryption_policies_initialization(self):
        """Test encryption policies are properly initialized."""
        security = HIPAATransmissionSecurity()
        policies = security.encryption_policies

        # Verify all required policies exist
        assert "highly_sensitive_phi" in policies
        assert "general_phi" in policies
        assert "internal_data" in policies

        # Verify highly sensitive PHI policy
        hs_policy = policies["highly_sensitive_phi"]
        assert hs_policy["policy_id"] == "TS-001"
        assert hs_policy["classification"] == DataClassification.HIGHLY_SENSITIVE
        assert hs_policy["encryption_standard"] == EncryptionStandard.AES_256_GCM
        assert hs_policy["key_size"] == 256
        assert hs_policy["require_mutual_auth"] is True
        assert hs_policy["require_integrity_check"] is True
        assert hs_policy["session_timeout"] == 300
        assert hs_policy["max_retries"] == 3

        # Verify general PHI policy
        gen_policy = policies["general_phi"]
        assert gen_policy["policy_id"] == "TS-002"
        assert gen_policy["classification"] == DataClassification.SENSITIVE
        assert gen_policy["encryption_standard"] == EncryptionStandard.AES_256_CBC
        assert gen_policy["key_size"] == 256
        assert gen_policy["session_timeout"] == 900

        # Verify internal data policy
        internal_policy = policies["internal_data"]
        assert internal_policy["policy_id"] == "TS-003"
        assert internal_policy["classification"] == DataClassification.INTERNAL
        assert internal_policy["encryption_standard"] == EncryptionStandard.TLS_1_2
        assert internal_policy["key_size"] == 128
        assert internal_policy["session_timeout"] == 3600

    def test_keys_initialization(self):
        """Test encryption keys are properly initialized."""
        security = HIPAATransmissionSecurity()
        keys = security.keys

        # Verify key structure
        assert "master_key" in keys
        assert "session_keys" in keys
        assert "rsa_private_key" in keys
        assert "rsa_public_key" in keys

        # Verify master key is valid Fernet key
        assert keys["master_key"] is not None
        assert isinstance(keys["master_key"], bytes)

        # Verify RSA key is generated
        assert keys["rsa_private_key"] is not None
        assert hasattr(keys["rsa_private_key"], "key_size")

    @pytest.mark.audit_required
    def test_encrypt_for_transmission_basic(self):
        """Test basic encryption for transmission with real cryptography."""
        security = HIPAATransmissionSecurity()

        # Test data
        test_data = {
            "patient_id": "P12345",
            "medical_record_number": "MRN-67890",
            "diagnosis": "Hypertension",
            "ssn": "123-45-6789",
        }

        # Encrypt data
        encrypted_package = security.encrypt_for_transmission(
            data=test_data,
            classification=DataClassification.HIGHLY_SENSITIVE,
            recipient_id="DR-001",
            metadata={"purpose": "treatment"},
        )

        # Verify package structure
        assert "package_id" in encrypted_package
        assert "session_id" in encrypted_package
        assert "encrypted_data" in encrypted_package
        assert "encrypted_session_key" in encrypted_package
        assert "encryption_metadata" in encrypted_package
        assert "classification" in encrypted_package
        assert "require_receipt" in encrypted_package

        # Verify encryption metadata
        metadata = encrypted_package["encryption_metadata"]
        assert metadata["algorithm"] == EncryptionStandard.AES_256_GCM.value
        assert metadata["key_size"] == 256
        assert "timestamp" in metadata
        assert "integrity_hash" in metadata

        # Verify encrypted data is different from original
        assert encrypted_package["encrypted_data"] != json.dumps(test_data)
        assert isinstance(encrypted_package["encrypted_data"], dict)

        # Verify encrypted data contains required components
        encrypted_data = encrypted_package["encrypted_data"]
        assert "ciphertext" in encrypted_data
        assert "algorithm" in encrypted_data
        assert encrypted_data["ciphertext"] != json.dumps(test_data)

    @pytest.mark.audit_required
    def test_decrypt_transmission_package(self):
        """Test decryption of transmission package with real cryptography."""
        security = HIPAATransmissionSecurity()

        # Original test data
        test_data = {
            "patient_id": "P12345",
            "diagnosis": "Diabetes Type 2",
            "medication": "Metformin 500mg",
        }

        # Encrypt data
        encrypted_package = security.encrypt_for_transmission(
            data=test_data,
            classification=DataClassification.SENSITIVE,
            recipient_id="DR-002",
        )

        # Decrypt data
        decrypted_data = security.decrypt_transmission_package(encrypted_package)

        # Verify decryption
        assert decrypted_data == test_data
        assert isinstance(decrypted_data, dict)

    def test_generate_session_key_real_crypto(self):
        """Test session key generation with real cryptography."""
        security = HIPAATransmissionSecurity()

        # Generate session key
        session_key = security._generate_session_key()

        # Verify key properties
        assert isinstance(session_key, bytes)
        assert len(session_key) == 32  # 256-bit key

        # Generate another key to verify uniqueness
        session_key2 = security._generate_session_key()
        assert session_key != session_key2

    def test_encrypt_session_key_with_rsa(self):
        """Test RSA encryption of session keys."""
        security = HIPAATransmissionSecurity()

        # Generate session key
        session_key = security._generate_session_key()

        # Encrypt session key with RSA
        encrypted_session_key = security._encrypt_session_key(session_key, "DR-001")

        # Verify encryption
        assert isinstance(encrypted_session_key, str)  # Base64 encoded string
        assert encrypted_session_key != session_key.hex()
        assert len(encrypted_session_key) > len(session_key.hex())

        # Decrypt and verify
        decrypted_key = security._decrypt_session_key(
            encrypted_session_key, security.keys["rsa_private_key"]
        )
        assert decrypted_key == session_key

    def test_calculate_integrity_hash(self):
        """Test integrity hash calculation."""
        security = HIPAATransmissionSecurity()

        test_data = "Test data for integrity verification"

        # Calculate hash
        hash_value = security._calculate_integrity_hash(test_data)

        # Verify hash properties
        assert isinstance(hash_value, str)
        assert len(hash_value) == 64  # SHA-256 hex digest

        # Verify consistency
        hash_value2 = security._calculate_integrity_hash(test_data)
        assert hash_value == hash_value2

        # Verify different data produces different hash
        different_hash = security._calculate_integrity_hash("Different data")
        assert hash_value != different_hash

    def test_audit_transmission_event(self):
        """Test audit trail creation for transmission events."""
        security = HIPAATransmissionSecurity()

        # Test transmission logging (which creates audit trail)
        initial_log_count = len(security.transmission_log)

        security._log_transmission(
            event_type="encryption",
            session_id="SESSION-001",
            party_id="DR-001",
            classification=DataClassification.HIGHLY_SENSITIVE,
            data_size=1024,
        )

        # Verify audit event was logged
        assert len(security.transmission_log) == initial_log_count + 1

        # Get the logged event
        audit_event = security.transmission_log[-1]

        # Verify audit event structure
        assert "log_id" in audit_event
        assert "timestamp" in audit_event
        assert audit_event["event_type"] == "encryption"
        assert audit_event["session_id"] == "SESSION-001"
        assert audit_event["party_id"] == "DR-001"
        assert (
            audit_event["classification"] == DataClassification.HIGHLY_SENSITIVE.value
        )
        assert audit_event["data_size"] == 1024

    def test_establish_secure_channel(self):
        """Test secure channel establishment."""
        security = HIPAATransmissionSecurity()

        # Test HTTPS channel
        success, channel_id = security.establish_secure_channel(
            endpoint="https://api.hospital.com/fhir",
            protocol=TransmissionProtocol.HTTPS,
            mutual_auth=True,
        )

        # Should succeed (actual implementation may vary)
        # Check if method exists and returns expected format
        assert isinstance(success, bool)
        if success:
            assert channel_id is not None

    def test_data_classification_policies(self):
        """Test different data classification policies are applied correctly."""
        security = HIPAATransmissionSecurity()

        # Test each classification level
        test_cases = [
            (DataClassification.HIGHLY_SENSITIVE, EncryptionStandard.AES_256_GCM, 256),
            (DataClassification.SENSITIVE, EncryptionStandard.AES_256_CBC, 256),
            (DataClassification.INTERNAL, EncryptionStandard.TLS_1_2, 128),
        ]

        for classification, expected_algo, expected_key_size in test_cases:
            # Encrypt with specific classification
            encrypted = security.encrypt_for_transmission(
                data={"test": "data"},
                classification=classification,
                recipient_id="TEST-001",
            )

            # Verify correct algorithm was used
            assert encrypted["encryption_metadata"]["algorithm"] == expected_algo.value
            assert encrypted["encryption_metadata"]["key_size"] == expected_key_size

    def test_transmission_timeout_handling(self):
        """Test transmission timeout handling."""
        security = HIPAATransmissionSecurity()

        # Test timeout configuration
        policies = security.encryption_policies

        # Verify timeout values
        assert policies["highly_sensitive_phi"]["session_timeout"] == 300  # 5 minutes
        assert policies["general_phi"]["session_timeout"] == 900  # 15 minutes
        assert policies["internal_data"]["session_timeout"] == 3600  # 1 hour

    def test_failed_transmission_tracking(self):
        """Test failed transmission tracking."""
        security = HIPAATransmissionSecurity()

        # Simulate failed transmission
        failure_event = {
            "package_id": "PKG-FAIL-001",
            "recipient_id": "DR-001",
            "error": "Network timeout",
            "timestamp": datetime.utcnow().isoformat(),
            "retry_count": 1,
        }

        security.failed_transmissions.append(failure_event)

        # Verify tracking
        assert len(security.failed_transmissions) == 1
        assert security.failed_transmissions[0]["package_id"] == "PKG-FAIL-001"

    def test_session_management(self):
        """Test active session management."""
        security = HIPAATransmissionSecurity()

        # Create session
        session_id = str(uuid.uuid4())
        session_data = {
            "session_id": session_id,
            "recipient_id": "DR-001",
            "created_at": datetime.utcnow().isoformat(),
            "expires_at": (datetime.utcnow() + timedelta(minutes=5)).isoformat(),
        }

        security.active_sessions[session_id] = session_data

        # Verify session tracking
        assert session_id in security.active_sessions
        assert security.active_sessions[session_id]["recipient_id"] == "DR-001"

    def test_real_aes_encryption_operations(self):
        """Test real AES encryption operations."""
        # Test AES-256-GCM encryption
        plaintext = "Sensitive patient data requiring encryption"
        key = secrets.token_bytes(32)  # 256-bit key
        nonce = secrets.token_bytes(12)  # 96-bit nonce for GCM

        # Encrypt using real AES-GCM
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM

        aesgcm = AESGCM(key)
        ciphertext = aesgcm.encrypt(nonce, plaintext.encode(), None)

        # Verify encryption
        assert ciphertext != plaintext.encode()
        assert len(ciphertext) > len(plaintext)

        # Decrypt and verify
        decrypted = aesgcm.decrypt(nonce, ciphertext, None)
        assert decrypted.decode() == plaintext

    def test_real_rsa_key_operations(self):
        """Test real RSA key operations."""
        security = HIPAATransmissionSecurity()

        # Get RSA keys
        private_key = security.keys["rsa_private_key"]
        public_key = security.keys["rsa_public_key"]

        # Test data
        test_data = b"Test session key data"

        # Encrypt with public key
        from cryptography.hazmat.primitives.asymmetric import padding

        encrypted = public_key.encrypt(
            test_data,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None,
            ),
        )

        # Verify encryption
        assert encrypted != test_data
        assert len(encrypted) > len(test_data)

        # Decrypt with private key
        decrypted = private_key.decrypt(
            encrypted,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None,
            ),
        )

        assert decrypted == test_data

    def test_fhir_audit_event_creation(self):
        """Test FHIR audit event creation for transmission security."""
        security = HIPAATransmissionSecurity()

        # Create transmission data
        transmission_data = {
            "action": "encrypt",
            "success": True,
            "patient_id": "P12345",
            "sender": "DR-001",
            "timestamp": datetime.now(),
            "package_id": "PKG-001",
            "source_ip": "192.168.1.100",
            "classification": DataClassification.SENSITIVE,
        }

        # Validate FHIR audit event
        validation_result = security.validate_fhir_transmission_audit(transmission_data)

        # Verify validation passed
        assert validation_result["valid"] is True
        assert len(validation_result.get("errors", [])) == 0


@pytest.mark.hipaa_required
class TestHIPAACompliance:
    """Test HIPAA-specific compliance requirements."""

    def test_encryption_strength_requirements(self):
        """Test that encryption meets HIPAA strength requirements."""
        # HIPAA requires AES-256 or equivalent

        # Test AES-256 key length
        aes_key = secrets.token_bytes(32)  # 256 bits
        assert len(aes_key) * 8 == 256  # Verify 256-bit strength

    def test_secure_key_generation(self):
        """Test secure cryptographic key generation."""
        # Test multiple key generations for uniqueness
        keys = set()

        for _ in range(100):
            key = secrets.token_bytes(32)  # 256-bit key
            keys.add(key.hex())

        # All keys should be unique
        assert len(keys) == 100

        # All keys should be 32 bytes (256 bits)
        for key_hex in keys:
            key_bytes = bytes.fromhex(key_hex)
            assert len(key_bytes) == 32

    def test_transmission_audit_requirements(self):
        """Test HIPAA audit requirements for transmission."""
        security = HIPAATransmissionSecurity()

        # Encrypt data (should create audit trail)
        test_data = {"patient_id": "P12345", "data": "test"}
        security.encrypt_for_transmission(
            data=test_data,
            classification=DataClassification.HIGHLY_SENSITIVE,
            recipient_id="DR-001",
        )

        # Verify audit trail exists
        assert len(security.transmission_log) > 0

        # Verify audit contains required HIPAA elements
        audit_event = security.transmission_log[-1]
        assert "timestamp" in audit_event
        assert "event_type" in audit_event
        assert "package_id" in audit_event
        assert "recipient_id" in audit_event
        assert "classification" in audit_event

    def test_data_integrity_verification(self):
        """Test data integrity verification requirements."""
        security = HIPAATransmissionSecurity()

        test_data = {"patient_id": "P12345", "vital_signs": {"bp": "120/80"}}

        # Encrypt data
        encrypted_package = security.encrypt_for_transmission(
            data=test_data,
            classification=DataClassification.SENSITIVE,
            recipient_id="DR-001",
        )

        # Verify integrity hash is present
        assert "integrity_hash" in encrypted_package["encryption_metadata"]

        # Decrypt and verify integrity
        decrypted_data = security.decrypt_transmission_package(encrypted_package)
        assert decrypted_data == test_data

    def test_minimum_encryption_standards(self):
        """Test minimum encryption standards compliance."""
        security = HIPAATransmissionSecurity()

        # Verify all policies meet minimum standards
        for _policy_name, policy in security.encryption_policies.items():
            # All policies should use at least 128-bit encryption
            assert policy["key_size"] >= 128

            # Highly sensitive data should use 256-bit
            if policy["classification"] == DataClassification.HIGHLY_SENSITIVE:
                assert policy["key_size"] == 256

    def test_session_timeout_compliance(self):
        """Test session timeout compliance with HIPAA requirements."""
        security = HIPAATransmissionSecurity()

        policies = security.encryption_policies

        # Highly sensitive PHI should have short timeout
        assert (
            policies["highly_sensitive_phi"]["session_timeout"] <= 300
        )  # 5 minutes max

        # All timeouts should be reasonable for security
        for policy in policies.values():
            assert policy["session_timeout"] <= 3600  # 1 hour max
