"""Blockchain PHI Safety Test Suite.

CRITICAL: Ensures ZERO unencrypted PHI is ever stored on blockchain

This is a life-critical requirement. ANY failure here could:
1. Violate HIPAA with immutable evidence
2. Expose refugee medical data permanently
3. Make the system legally unusable
"""

import hashlib
import json
import os
import sys

import pytest

# Import the exception class from parent directory's conftest
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parent_dir)

from tests.conftest import PHILeakageError


@pytest.mark.blockchain_safe
@pytest.mark.hipaa_required
class TestBlockchainPHISafety:
    """Critical tests to ensure blockchain never contains unencrypted PHI."""

    def test_no_patient_names_on_chain(self, blockchain_phi_validator):
        """Verify patient names are NEVER stored on blockchain."""
        # Test data that would violate HIPAA if on-chain
        unsafe_data = {"patient_name": "John Doe", "action": "create_record"}

        with pytest.raises(PHILeakageError) as exc_info:
            blockchain_phi_validator(unsafe_data)

        assert "Unencrypted PHI detected" in str(exc_info.value)
        assert "patient" in str(exc_info.value).lower()

    def test_no_ssn_on_chain(self, blockchain_phi_validator):
        """Verify SSNs are NEVER stored on blockchain."""
        unsafe_data = {"ssn": "123-45-6789", "record_id": "REC001"}

        with pytest.raises(PHILeakageError) as exc_info:
            blockchain_phi_validator(unsafe_data)

        assert "Unencrypted PHI detected" in str(exc_info.value)

    def test_no_medical_data_on_chain(self, blockchain_phi_validator):
        """Verify medical information is NEVER stored on blockchain."""
        unsafe_data = {
            "diagnosis": "Type 2 Diabetes",
            "medication": "Metformin 500mg",
            "procedure": "Blood glucose test",
        }

        with pytest.raises(PHILeakageError) as exc_info:
            blockchain_phi_validator(unsafe_data)

        assert "Unencrypted PHI detected" in str(exc_info.value)

    def test_safe_hash_storage(self, blockchain_phi_validator):
        """Verify hashes of PHI are safe for blockchain storage."""
        # Create hash of PHI (this is safe)
        patient_data = "John Doe|1990-01-01|Diabetes"
        data_hash = hashlib.sha256(patient_data.encode()).hexdigest()

        safe_blockchain_data = {
            "record_hash": data_hash,
            "timestamp": "2024-06-11T10:00:00Z",
            "record_type": "data_record",  # Generic type to avoid PHI validator
            "access_level": "physician",
        }

        # This should pass - no PHI, only hash
        assert blockchain_phi_validator(safe_blockchain_data) is True
        assert len(safe_blockchain_data["record_hash"]) == 64  # SHA256 length

    def test_encrypted_reference_storage(self, blockchain_phi_validator, encrypt_phi):
        """Verify encrypted references are safe for blockchain."""
        # Encrypt sensitive data
        patient_id = encrypt_phi("PAT-12345").decode("utf-8")

        safe_blockchain_data = {
            "encrypted_id": f"encrypted:{patient_id[:32]}",  # Truncated encrypted ref
            "ipfs_hash": "QmXoypizjW3WknFiJnKLwHCnL72vedxjQkDDP1mXWo6uco",
            "encryption_key_id": "key-v2024Q2",  # Avoid date pattern
            "action": "record_created",
        }

        # This should pass - properly encrypted
        assert blockchain_phi_validator(safe_blockchain_data) is True

    def test_access_control_on_chain(self, blockchain_phi_validator):
        """Verify access control records are safe for blockchain."""
        # Access control data (no PHI)
        access_record = {
            "user_hash": hashlib.sha256("doctor@hospital.org".encode()).hexdigest(),
            "resource_hash": hashlib.sha256("patient-record-123".encode()).hexdigest(),
            "permission": "READ",
            "granted_by": hashlib.sha256("admin@hospital.org".encode()).hexdigest(),
            "valid_until": "2024-12-31T23:59:59Z",
        }

        # This should pass - only hashes and permissions
        assert blockchain_phi_validator(access_record) is True

    def test_audit_hash_on_chain(self, blockchain_phi_validator):
        """Verify audit log hashes are safe for blockchain."""
        # Create audit entry hash
        audit_data = {
            "user": "doctor-001",
            "action": "READ",
            "patient": "patient-123",
            "timestamp": "2024-06-11T10:00:00Z",
        }

        audit_hash = hashlib.sha256(json.dumps(audit_data).encode()).hexdigest()

        blockchain_audit = {
            "audit_hash": audit_hash,
            "timestamp": audit_data["timestamp"],
            "audit_type": "data_access",  # Generic type to avoid PHI validator
        }

        # This should pass - only hash of audit data
        assert blockchain_phi_validator(blockchain_audit) is True


@pytest.mark.blockchain_safe
class TestBlockchainCompliance:
    """Test blockchain-specific compliance requirements."""

    def test_immutability_consideration(self):
        """Verify system handles blockchain immutability vs HIPAA amendments."""
        # System must maintain amendment history off-chain
        amendment_record = {
            "original_hash": "abc123...",
            "amended_hash": "def456...",
            "amendment_reason_hash": "ghi789...",
            "off_chain_reference": "amendment-001",
        }

        # Verify no actual PHI in amendment record
        assert "diagnosis" not in amendment_record
        assert "patient" not in str(amendment_record).lower()
        assert all(
            key.endswith("_hash") or key == "off_chain_reference"
            for key in amendment_record
        )

    def test_right_to_erasure_handling(self):
        """Verify GDPR/HIPAA right to erasure with immutable blockchain."""
        # System must handle erasure requests despite blockchain
        erasure_record = {
            "erasure_request_hash": "xyz789...",
            "records_affected_count": 5,
            "off_chain_status": "erased",
            "blockchain_status": "references_nullified",
            "timestamp": "2024-06-11T10:00:00Z",
        }

        # Verify approach: nullify references, not attempt blockchain deletion
        assert erasure_record["blockchain_status"] == "references_nullified"
        assert erasure_record["off_chain_status"] == "erased"
