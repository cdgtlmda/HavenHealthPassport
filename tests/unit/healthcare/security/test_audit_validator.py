"""
Test suite for healthcare security audit validator.

This module provides comprehensive testing for audit validation functionality,
ensuring HIPAA compliance for audit logging, monitoring, and protection.
Tests use real implementations without mocking core functionality.
"""

import pytest

from src.core.security import (
    SecurityControl,
    SecurityControlCategory,
    SecurityControlStatus,
)
from src.healthcare.security.audit_validator import (
    AuditEventType,
    AuditValidator,
)


class TestAuditValidator:
    """Test suite for AuditValidator class."""

    @pytest.fixture
    def audit_validator(self):
        """Create an AuditValidator instance for testing."""
        return AuditValidator()

    @pytest.fixture
    def sample_security_control(self):
        """Create a sample security control for testing."""
        return SecurityControl(
            id="AU-001",
            name="Audit Collection",
            category=SecurityControlCategory.AUDIT_LOGGING,
            description="Audit log collection controls",
            requirement="System must collect audit logs for all security events",
        )

    def test_audit_validator_initialization(self, audit_validator):
        """Test AuditValidator initialization with proper requirements."""
        assert audit_validator is not None
        assert len(audit_validator.audit_requirements) > 0
        assert audit_validator.retention_policy["default_days"] == 2555  # 7 years HIPAA
        assert audit_validator.retention_policy["security_events"] == 3650  # 10 years
        assert "failed_login_attempts" in audit_validator.monitoring_thresholds

    def test_audit_requirements_definition(self, audit_validator):
        """Test that audit requirements are properly defined."""
        requirements = audit_validator.audit_requirements

        # Check that all required event types are covered
        event_types = {req.event_type for req in requirements}
        assert AuditEventType.LOGIN in event_types
        assert AuditEventType.DATA_ACCESS in event_types
        assert AuditEventType.DATA_MODIFICATION in event_types
        assert AuditEventType.PERMISSION_CHANGE in event_types
        assert AuditEventType.SECURITY_EVENT in event_types

        # Verify mandatory requirements
        for req in requirements:
            assert req.mandatory is True
            assert req.retention_days >= 2555  # Minimum HIPAA requirement

            # Verify real-time logging for critical events
            if req.event_type in [
                AuditEventType.LOGIN,
                AuditEventType.DATA_ACCESS,
                AuditEventType.DATA_MODIFICATION,
                AuditEventType.PERMISSION_CHANGE,
                AuditEventType.SECURITY_EVENT,
            ]:
                assert req.real_time is True

    def test_monitoring_thresholds_configuration(self, audit_validator):
        """Test monitoring thresholds are properly configured."""
        thresholds = audit_validator.monitoring_thresholds

        # Verify failed login threshold
        assert thresholds["failed_login_attempts"]["threshold"] == 5
        assert thresholds["failed_login_attempts"]["window_minutes"] == 15
        assert thresholds["failed_login_attempts"]["action"] == "lock_account"

        # Verify unusual access pattern threshold
        assert thresholds["unusual_access_pattern"]["threshold"] == 100
        assert thresholds["unusual_access_pattern"]["window_minutes"] == 60
        assert thresholds["unusual_access_pattern"]["action"] == "alert_security"

        # Verify after-hours access configuration
        assert thresholds["after_hours_access"]["start_hour"] == 22
        assert thresholds["after_hours_access"]["end_hour"] == 6
        assert thresholds["after_hours_access"]["action"] == "log_and_alert"

        # Verify bulk data export threshold
        assert thresholds["bulk_data_export"]["threshold"] == 1000
        assert thresholds["bulk_data_export"]["action"] == "require_approval"

    @pytest.mark.asyncio
    async def test_validate_audit_collection_compliant(self, audit_validator):
        """Test validation of compliant audit collection controls."""
        control = SecurityControl(
            id="AU-001",
            name="Audit Collection",
            category=SecurityControlCategory.AUDIT_LOGGING,
            description="Audit log collection controls",
            requirement="System must collect audit logs for all security events",
        )

        result = await audit_validator.validate_control(control)

        assert result is not None
        assert result.control_id == "AU-001"
        assert result.status == SecurityControlStatus.COMPLIANT
        assert "event_coverage" in result.details
        assert "log_details" in result.details
        assert "realtime_logging" in result.details
        assert "format" in result.details

        # Verify evidence was collected
        assert "evidence" in result.details
        assert len(result.details["evidence"]) > 0

    @pytest.mark.asyncio
    async def test_validate_audit_protection(self, audit_validator):
        """Test validation of audit protection controls."""
        control = SecurityControl(
            id="AU-002",
            name="Audit Protection",
            category=SecurityControlCategory.AUDIT_LOGGING,
            description="Audit log protection controls",
            requirement="System must protect audit logs from tampering",
        )

        result = await audit_validator.validate_control(control)

        assert result is not None
        assert result.control_id == "AU-002"
        assert result.status == SecurityControlStatus.COMPLIANT
        assert "tamper_protection" in result.details
        assert "access_controls" in result.details
        assert "backup" in result.details
        assert "retention" in result.details

        # Verify tamper protection methods
        tamper_details = result.details["tamper_protection"]
        assert tamper_details["methods"]["cryptographic_hashing"] is True
        assert tamper_details["methods"]["digital_signatures"] is True
        assert tamper_details["hash_algorithm"] == "SHA-256"
        assert tamper_details["signature_algorithm"] == "RSA-4096"

    @pytest.mark.asyncio
    async def test_validate_audit_monitoring(self, audit_validator):
        """Test validation of audit monitoring controls."""
        control = SecurityControl(
            id="AU-003",
            name="Audit Monitoring",
            category=SecurityControlCategory.AUDIT_LOGGING,
            description="Audit monitoring and alerting controls",
            requirement="System must monitor audit logs in real-time",
        )

        result = await audit_validator.validate_control(control)

        assert result is not None
        assert result.control_id == "AU-003"
        assert result.status == SecurityControlStatus.COMPLIANT
        assert "monitoring" in result.details
        assert "alerts" in result.details
        assert "anomaly_detection" in result.details
        assert "incident_response" in result.details

        # Verify real-time monitoring coverage
        monitoring = result.details["monitoring"]
        assert monitoring["compliant"] is True
        assert monitoring["coverage"] == 100.0

    @pytest.mark.asyncio
    async def test_check_event_coverage(self, audit_validator):
        """Test event coverage checking."""
        coverage_result = await audit_validator._check_event_coverage()

        assert coverage_result["compliant"] is True
        assert (
            coverage_result["coverage"] >= 100.0
        )  # Can be > 100% if more events logged than required
        assert len(coverage_result["missing"]) == 0
        assert "login" in coverage_result["logged"]
        assert "data_access" in coverage_result["logged"]
        assert "security_event" in coverage_result["logged"]

    @pytest.mark.asyncio
    async def test_check_log_details(self, audit_validator):
        """Test log detail completeness checking."""
        detail_result = await audit_validator._check_log_details()

        assert detail_result["compliant"] is True
        assert detail_result["completeness"] >= 95.0
        assert "user_identification" in detail_result["details"]
        assert detail_result["details"]["user_identification"] == 100
        assert detail_result["details"]["timestamp_precision"] == 100

    @pytest.mark.asyncio
    async def test_check_realtime_logging(self, audit_validator):
        """Test real-time logging capability check."""
        realtime_result = await audit_validator._check_realtime_logging()

        assert realtime_result["compliant"] is True
        assert realtime_result["realtime_events"]["login"] is True
        assert realtime_result["realtime_events"]["security_event"] is True

    @pytest.mark.asyncio
    async def test_check_tamper_protection(self, audit_validator):
        """Test tamper protection checking."""
        tamper_result = await audit_validator._check_tamper_protection()

        assert tamper_result["compliant"] is True
        assert tamper_result["methods"]["cryptographic_hashing"] is True
        assert tamper_result["methods"]["digital_signatures"] is True
        assert tamper_result["hash_algorithm"] == "SHA-256"
        assert tamper_result["signature_algorithm"] == "RSA-4096"
        assert len(tamper_result["issues"]) == 0

    @pytest.mark.asyncio
    async def test_check_audit_access_controls(self, audit_validator):
        """Test audit access control checking."""
        access_result = await audit_validator._check_audit_access_controls()

        assert access_result["compliant"] is True
        assert access_result["restricted"] is True
        assert "security_admin" in access_result["authorized_roles"]
        assert "compliance_officer" in access_result["authorized_roles"]
        assert access_result["config"]["segregation_of_duties"] is True

    @pytest.mark.asyncio
    async def test_check_retention_policy(self, audit_validator):
        """Test retention policy compliance checking."""
        retention_result = await audit_validator._check_retention_policy()

        assert retention_result["compliant"] is True
        assert len(retention_result["issues"]) == 0
        assert retention_result["retention_status"]["login_logs"]["required"] == 2555

    @pytest.mark.asyncio
    async def test_check_anomaly_detection(self, audit_validator):
        """Test anomaly detection configuration checking."""
        anomaly_result = await audit_validator._check_anomaly_detection()

        assert anomaly_result["enabled"] is True
        assert anomaly_result["ml_based"] is True
        assert "access_pattern_anomaly" in anomaly_result["detection_types"]
        assert "geographic_anomaly" in anomaly_result["detection_types"]

    @pytest.mark.asyncio
    async def test_validate_generic_control(self, audit_validator):
        """Test generic control validation for unrecognized control IDs."""
        control = SecurityControl(
            id="AU-999",  # Unknown control ID
            name="Unknown Control",
            category=SecurityControlCategory.AUDIT_LOGGING,
            description="Test unknown control",
            requirement="Test requirement",
        )

        result = await audit_validator.validate_control(control)

        assert result is not None
        assert result.control_id == "AU-999"
        assert result.status == SecurityControlStatus.COMPLIANT
        assert result.details["validation"] == "generic"

    @pytest.mark.asyncio
    async def test_audit_requirement_details(self, audit_validator):
        """Test that all audit requirements have proper details."""
        for requirement in audit_validator.audit_requirements:
            assert len(requirement.details_required) > 0

            # Check specific requirements for each event type
            if requirement.event_type == AuditEventType.LOGIN:
                assert "user_id" in requirement.details_required
                assert "ip_address" in requirement.details_required
                assert "timestamp" in requirement.details_required
                assert "result" in requirement.details_required
            elif requirement.event_type == AuditEventType.DATA_ACCESS:
                assert "user_id" in requirement.details_required
                assert "patient_id" in requirement.details_required
                assert "data_type" in requirement.details_required
                assert "purpose" in requirement.details_required
