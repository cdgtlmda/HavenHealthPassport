"""
Test encryption validator implementation.

CRITICAL: NO MOCKS for core functionality - test real behavior only.
This is a healthcare system for vulnerable refugees.
"""

import ssl
from datetime import datetime

import pytest

from src.healthcare.security.base_types import (
    SecurityControl,
    SecurityControlCategory,
    SecurityControlStatus,
    ValidationResult,
)
from src.healthcare.security.encryption_validator import (
    EncryptionAlgorithm,
    EncryptionConfig,
    EncryptionValidator,
    KeyManagementSystem,
)


@pytest.mark.asyncio
@pytest.mark.hipaa_required
class TestEncryptionValidator:
    """Test encryption validator with real implementations."""

    def test_initialization(self):
        """Test validator initialization."""
        validator = EncryptionValidator()

        # Verify initialization values
        assert validator is not None
        assert validator.minimum_key_sizes == {"AES": 256, "RSA": 4096, "ECDSA": 384}
        assert len(validator.approved_algorithms) == 4
        assert EncryptionAlgorithm.AES_256_GCM in validator.approved_algorithms
        assert EncryptionAlgorithm.AES_256_CBC in validator.approved_algorithms
        assert EncryptionAlgorithm.RSA_4096 in validator.approved_algorithms
        assert EncryptionAlgorithm.ECDSA_P384 in validator.approved_algorithms
        assert validator.tls_minimum_version == ssl.TLSVersion.TLSv1_3

    async def test_validate_control_data_at_rest(self):
        """Test data at rest encryption validation."""
        validator = EncryptionValidator()

        # Create a test control for data at rest
        control = SecurityControl(
            id="EN-001",
            name="Data at Rest Encryption",
            category=SecurityControlCategory.ENCRYPTION,
            description="All PHI data at rest must be encrypted",
            hipaa_reference="164.312(a)(2)(iv)",
            validation_method="validate_data_at_rest",
            critical=True,
        )

        # Perform validation
        result = await validator.validate_control(control)

        # Verify result structure
        assert isinstance(result, ValidationResult)
        assert result.control == control
        assert result.status in [
            SecurityControlStatus.COMPLIANT,
            SecurityControlStatus.NON_COMPLIANT,
            SecurityControlStatus.PARTIALLY_COMPLIANT,
        ]
        assert isinstance(result.timestamp, datetime)
        assert isinstance(result.details, dict)
        assert isinstance(result.evidence, list)
        assert isinstance(result.remediation_required, bool)
        assert isinstance(result.remediation_steps, list)

        # Verify expected keys in details
        assert "database" in result.details
        assert "filesystem" in result.details
        assert "backup" in result.details
        assert "temp_files" in result.details

    async def test_validate_control_data_in_transit(self):
        """Test data in transit encryption validation."""
        validator = EncryptionValidator()

        # Create a test control for data in transit
        control = SecurityControl(
            id="EN-002",
            name="Data in Transit Encryption",
            category=SecurityControlCategory.ENCRYPTION,
            description="All PHI data in transit must be encrypted",
            hipaa_reference="164.312(e)(1)",
            validation_method="validate_data_in_transit",
            critical=True,
        )

        # Perform validation
        result = await validator.validate_control(control)

        # Verify result structure
        assert isinstance(result, ValidationResult)
        assert result.control == control
        assert result.status in [
            SecurityControlStatus.COMPLIANT,
            SecurityControlStatus.NON_COMPLIANT,
            SecurityControlStatus.PARTIALLY_COMPLIANT,
        ]
        assert isinstance(result.timestamp, datetime)
        assert isinstance(result.details, dict)
        assert isinstance(result.evidence, list)

        # Verify expected keys in details
        assert "tls" in result.details
        assert "api" in result.details
        assert "internal_comm" in result.details
        assert "certificates" in result.details

    async def test_validate_control_key_management(self):
        """Test key management validation."""
        validator = EncryptionValidator()

        # Create a test control for key management
        control = SecurityControl(
            id="EN-003",
            name="Key Management",
            category=SecurityControlCategory.ENCRYPTION,
            description="Proper key management procedures",
            hipaa_reference="164.312(a)(2)(iv)",
            validation_method="validate_key_management",
            critical=True,
        )

        # Perform validation
        result = await validator.validate_control(control)

        # Verify result returns properly
        assert isinstance(result, ValidationResult)
        assert result.control == control
        assert isinstance(result.timestamp, datetime)

    def test_encryption_config_dataclass(self):
        """Test EncryptionConfig dataclass."""
        config = EncryptionConfig(
            algorithm=EncryptionAlgorithm.AES_256_GCM,
            key_size=256,
            mode="GCM",
            key_rotation_days=90,
            key_management=KeyManagementSystem.HSM,
        )

        assert config.algorithm == EncryptionAlgorithm.AES_256_GCM
        assert config.key_size == 256
        assert config.mode == "GCM"
        assert config.key_rotation_days == 90
        assert config.key_management == KeyManagementSystem.HSM

    def test_encryption_algorithm_enum(self):
        """Test EncryptionAlgorithm enum values."""
        assert EncryptionAlgorithm.AES_256_GCM.value == "AES-256-GCM"
        assert EncryptionAlgorithm.AES_256_CBC.value == "AES-256-CBC"
        assert EncryptionAlgorithm.RSA_4096.value == "RSA-4096"
        assert EncryptionAlgorithm.ECDSA_P384.value == "ECDSA-P384"
        assert EncryptionAlgorithm.CHACHA20_POLY1305.value == "ChaCha20-Poly1305"

    def test_key_management_system_enum(self):
        """Test KeyManagementSystem enum values."""
        assert KeyManagementSystem.HSM.value == "Hardware Security Module"
        assert KeyManagementSystem.KMS.value == "Key Management Service"
        assert KeyManagementSystem.LOCAL_VAULT.value == "Local Secure Vault"
        assert KeyManagementSystem.CLOUD_KMS.value == "Cloud KMS"

    async def test_validate_control_generic_fallback(self):
        """Test generic encryption validation fallback for unknown control IDs."""
        validator = EncryptionValidator()

        # Create a test control with unknown ID
        control = SecurityControl(
            id="EN-999",  # Unknown ID
            name="Generic Encryption Control",
            category=SecurityControlCategory.ENCRYPTION,
            description="Generic encryption validation",
            hipaa_reference="164.312(a)(2)(iv)",
            validation_method="validate_generic",
            critical=True,
        )

        # Should use generic validation method
        result = await validator.validate_control(control)

        # Verify it returns a valid result
        assert isinstance(result, ValidationResult)
        assert result.control == control
        assert isinstance(result.timestamp, datetime)

    async def test_validation_result_is_compliant_property(self):
        """Test ValidationResult.is_compliant property."""
        validator = EncryptionValidator()

        control = SecurityControl(
            id="EN-001",
            name="Test Control",
            category=SecurityControlCategory.ENCRYPTION,
            description="Test",
            hipaa_reference="164.312(a)(2)(iv)",
            validation_method="test",
            critical=True,
        )

        result = await validator.validate_control(control)

        # Test is_compliant property
        if result.status == SecurityControlStatus.COMPLIANT:
            assert result.is_compliant is True
        else:
            assert result.is_compliant is False


# Run a quick verification when this file is executed directly
if __name__ == "__main__":
    import asyncio

    async def verify_basic_functionality():
        """Quick verification that basic functionality works."""
        validator = EncryptionValidator()
        print(f"✓ Created validator: {validator}")
        print(f"✓ Minimum key sizes: {validator.minimum_key_sizes}")
        print(f"✓ Approved algorithms: {len(validator.approved_algorithms)}")
        print(f"✓ TLS minimum version: {validator.tls_minimum_version}")

        # Test a simple validation
        control = SecurityControl(
            id="EN-001",
            name="Test",
            category=SecurityControlCategory.ENCRYPTION,
            description="Test control",
            hipaa_reference="164.312(a)(2)(iv)",
            validation_method="test",
            critical=True,
        )

        result = await validator.validate_control(control)
        print(f"✓ Validation completed: {result.status}")

    asyncio.run(verify_basic_functionality())
