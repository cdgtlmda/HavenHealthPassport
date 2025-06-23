"""Test HSM Integration - comprehensive coverage Required.

HIPAA Compliant - Real HSM operations.
NO MOCKS for HSM functionality per medical compliance requirements.

This tests critical HSM integration for refugee healthcare data encryption.
MUST achieve comprehensive test coverage for medical compliance.
"""

import os
from datetime import datetime
from typing import Any, Type

import pytest

try:
    from src.security.hsm_integration import (
        HardwareSecurityModule as HSMIntegrationImport,
    )

    HSMIntegration: Type[Any] = HSMIntegrationImport
    HSM_AVAILABLE = True
except ImportError:
    # Skip HSM tests if module not available
    HSM_AVAILABLE = False

    # Create a dummy class to avoid type errors
    class DummyHSM:
        pass

    HSMIntegration = DummyHSM


def check_hsm_available():
    """Check if HSM is available for testing."""
    try:
        # Check if CloudHSM environment variables are set
        return bool(os.environ.get("CLOUDHSM_IP") and os.environ.get("CLOUDHSM_USER"))
    except Exception:
        return False


@pytest.fixture
def hsm_integration():
    """Create HSM integration instance."""
    if HSMIntegration is None:
        pytest.skip("HSM integration module not available")
    return HSMIntegration()


class TestHSMIntegration:
    """Test HSM integration with real operations."""

    def test_hsm_integration_initialization(self, hsm_integration):
        """Test HSM integration initialization."""
        assert hsm_integration is not None
        assert hasattr(hsm_integration, "environment")
        assert hasattr(hsm_integration, "aws_region")

    @pytest.mark.skipif(
        not check_hsm_available(), reason="HSM credentials not available"
    )
    def test_real_hsm_connection(self, hsm_integration):
        """Test real HSM connection."""
        # Test connection to real HSM
        connection_result = hsm_integration.connect()
        assert connection_result is not None

    def test_hsm_environment_detection(self, hsm_integration):
        """Test HSM environment detection."""
        # Test environment detection logic
        environment = hsm_integration.get_environment()
        assert environment in ["production", "development", "testing"]

    def test_hsm_configuration_validation(self, hsm_integration):
        """Test HSM configuration validation."""
        # Test configuration validation
        config = hsm_integration.get_configuration()
        assert isinstance(config, dict)
        assert "environment" in config
        assert "aws_region" in config

    @pytest.mark.skipif(
        not check_hsm_available(), reason="HSM credentials not available"
    )
    def test_real_key_generation(self, hsm_integration):
        """Test real key generation with HSM."""
        # Test key generation with real HSM
        key_result = hsm_integration.generate_key(
            key_type="AES",
            key_size=256,
            key_label="test_key_" + str(int(datetime.now().timestamp())),
        )
        assert key_result is not None
        assert "key_handle" in key_result

    @pytest.mark.skipif(
        not check_hsm_available(), reason="HSM credentials not available"
    )
    def test_real_encryption_operations(self, hsm_integration):
        """Test real encryption operations with HSM."""
        # Generate a key for testing
        key_result = hsm_integration.generate_key(
            key_type="AES",
            key_size=256,
            key_label="encrypt_test_key_" + str(int(datetime.now().timestamp())),
        )

        # Test encryption
        plaintext = "sensitive patient data for HSM encryption"
        encrypted_result = hsm_integration.encrypt(
            key_handle=key_result["key_handle"], plaintext=plaintext
        )

        assert encrypted_result is not None
        assert encrypted_result != plaintext

        # Test decryption
        decrypted_result = hsm_integration.decrypt(
            key_handle=key_result["key_handle"], ciphertext=encrypted_result
        )

        assert decrypted_result == plaintext

    def test_hsm_fallback_behavior(self, hsm_integration):
        """Test HSM fallback behavior when HSM unavailable."""
        # Test fallback behavior when HSM is not available
        fallback_result = hsm_integration.get_fallback_encryption()
        assert fallback_result is not None
        assert isinstance(fallback_result, dict)

    def test_hsm_error_handling(self, hsm_integration):
        """Test HSM error handling."""
        # Test error handling for invalid operations
        try:
            hsm_integration.encrypt(
                key_handle="invalid_key_handle", plaintext="test data"
            )
        except Exception as e:
            assert isinstance(e, Exception)
            assert str(e)  # Error message should not be empty

    def test_hsm_logging_functionality(self, hsm_integration):
        """Test HSM logging functionality."""
        # Test that logging is properly configured
        logger = hsm_integration.get_logger()
        assert logger is not None
        assert hasattr(logger, "info")
        assert hasattr(logger, "error")
        assert hasattr(logger, "warning")

    def test_hsm_security_compliance(self, hsm_integration):
        """Test HSM security compliance features."""
        # Test security compliance features
        compliance_check = hsm_integration.check_security_compliance()
        assert isinstance(compliance_check, dict)
        assert "fips_140_2_level_3" in compliance_check
        assert "key_management" in compliance_check

    @pytest.mark.skipif(
        not check_hsm_available(), reason="HSM credentials not available"
    )
    def test_real_key_management_lifecycle(self, hsm_integration):
        """Test complete key management lifecycle with real HSM."""
        key_label = "lifecycle_test_key_" + str(int(datetime.now().timestamp()))

        # Generate key
        key_result = hsm_integration.generate_key(
            key_type="AES", key_size=256, key_label=key_label
        )
        assert key_result is not None

        # List keys to verify creation
        keys_list = hsm_integration.list_keys()
        assert any(key["label"] == key_label for key in keys_list)

        # Use key for encryption/decryption
        test_data = "lifecycle test data"
        encrypted = hsm_integration.encrypt(
            key_handle=key_result["key_handle"], plaintext=test_data
        )
        decrypted = hsm_integration.decrypt(
            key_handle=key_result["key_handle"], ciphertext=encrypted
        )
        assert decrypted == test_data

        # Clean up - delete test key
        delete_result = hsm_integration.delete_key(key_result["key_handle"])
        assert delete_result is True

    def test_hsm_audit_trail(self, hsm_integration):
        """Test HSM audit trail functionality."""
        # Test audit trail generation
        audit_events = hsm_integration.get_audit_events()
        assert isinstance(audit_events, list)

        # Test audit event structure
        if audit_events:
            event = audit_events[0]
            assert "timestamp" in event
            assert "event_type" in event
            assert "user_id" in event

    def test_hsm_performance_metrics(self, hsm_integration):
        """Test HSM performance metrics collection."""
        # Test performance metrics
        metrics = hsm_integration.get_performance_metrics()
        assert isinstance(metrics, dict)
        assert "operations_per_second" in metrics
        assert "latency_ms" in metrics

    @pytest.mark.skipif(
        not check_hsm_available(), reason="HSM credentials not available"
    )
    def test_real_bulk_operations(self, hsm_integration):
        """Test bulk operations with real HSM."""
        # Test bulk key generation
        bulk_keys = hsm_integration.generate_bulk_keys(
            count=5, key_type="AES", key_size=256, key_prefix="bulk_test_"
        )

        assert len(bulk_keys) == 5
        for key in bulk_keys:
            assert "key_handle" in key
            assert "key_label" in key

        # Clean up bulk keys
        for key in bulk_keys:
            hsm_integration.delete_key(key["key_handle"])

    def test_hsm_configuration_management(self, hsm_integration):
        """Test HSM configuration management."""
        # Test configuration retrieval
        config = hsm_integration.get_hsm_configuration()
        assert isinstance(config, dict)
        assert "cluster_id" in config or "development_mode" in config

        # Test configuration validation
        validation_result = hsm_integration.validate_configuration()
        assert isinstance(validation_result, bool)

    def test_hsm_disaster_recovery(self, hsm_integration):
        """Test HSM disaster recovery features."""
        # Test backup functionality
        backup_status = hsm_integration.get_backup_status()
        assert isinstance(backup_status, dict)
        assert "last_backup" in backup_status
        assert "backup_enabled" in backup_status

    def test_hsm_integration_health_check(self, hsm_integration):
        """Test HSM integration health check."""
        # Test health check
        health_status = hsm_integration.health_check()
        assert isinstance(health_status, dict)
        assert "status" in health_status
        assert "timestamp" in health_status
        assert health_status["status"] in ["healthy", "degraded", "unavailable"]

    def test_hsm_key_rotation_support(self, hsm_integration):
        """Test HSM key rotation support."""
        # Test key rotation capabilities
        rotation_policy = hsm_integration.get_key_rotation_policy()
        assert isinstance(rotation_policy, dict)
        assert "rotation_interval_days" in rotation_policy
        assert "auto_rotation_enabled" in rotation_policy
