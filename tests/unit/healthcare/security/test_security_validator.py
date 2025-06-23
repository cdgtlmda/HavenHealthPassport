"""
Test suite for Healthcare Security Controls Validator.

Tests actual security validation functionality without mocks.
HIPAA compliance testing for security controls.
"""

from datetime import datetime
from pathlib import Path

import pytest

from src.healthcare.security.base_types import (
    SecurityControl,
    SecurityControlCategory,
    SecurityControlStatus,
    ValidationResult,
)
from src.healthcare.security.security_validator import SecurityValidator


class TestSecurityValidator:
    """Test SecurityValidator class - basic functionality."""

    def test_security_validator_initialization(self):
        """Test that SecurityValidator can be created successfully."""
        # Create validator - no parameters needed based on __init__
        validator = SecurityValidator()

        # Verify basic initialization
        assert validator is not None
        assert hasattr(validator, "controls")
        assert hasattr(validator, "validation_results")
        assert hasattr(validator, "report_dir")

        # Check controls are defined
        assert len(validator.controls) > 0
        assert all(isinstance(c, SecurityControl) for c in validator.controls)

        # Check sub-validators exist
        assert hasattr(validator, "hipaa_checker")
        assert hasattr(validator, "access_validator")
        assert hasattr(validator, "encryption_validator")
        assert hasattr(validator, "audit_validator")

    def test_report_directory_creation(self):
        """Test that report directory is created on initialization."""
        validator = SecurityValidator()

        # Check report directory exists
        assert validator.report_dir.exists()
        assert validator.report_dir.is_dir()
        assert validator.report_dir == Path("compliance_reports/security")

    def test_security_controls_defined(self):
        """Test that all required security controls are defined."""
        validator = SecurityValidator()

        # Check we have controls for all categories
        categories_present = set(control.category for control in validator.controls)

        # Verify critical categories are present
        assert SecurityControlCategory.ACCESS_CONTROL in categories_present
        assert SecurityControlCategory.ENCRYPTION in categories_present
        assert SecurityControlCategory.AUDIT_LOGGING in categories_present

        # Check critical controls exist
        control_ids = [c.id for c in validator.controls]
        assert "AC-001" in control_ids  # User Authentication
        assert "EN-001" in control_ids  # Data at Rest Encryption
        assert "AU-001" in control_ids  # Audit Log Collection

    def test_critical_controls_marked(self):
        """Test that critical controls are properly marked."""
        validator = SecurityValidator()

        # Find critical encryption control
        encryption_control = next(
            (c for c in validator.controls if c.id == "EN-001"), None
        )
        assert encryption_control is not None
        assert encryption_control.critical is True
        assert encryption_control.hipaa_reference == "164.312(a)(2)(iv)"

    def test_validation_result_structure(self):
        """Test ValidationResult can be created with required fields."""
        # Create a test control
        control = SecurityControl(
            id="TEST-001",
            name="Test Control",
            category=SecurityControlCategory.ACCESS_CONTROL,
            description="Test control for unit testing",
            hipaa_reference="164.312(test)",
            validation_method="test_method",
            critical=True,
        )

        # Create validation result
        result = ValidationResult(
            control=control,
            status=SecurityControlStatus.COMPLIANT,
            timestamp=datetime.now(),
            details={"test": "details"},
            evidence=[{"type": "test", "description": "Test evidence"}],
            remediation_required=False,
        )

        # Verify result
        assert result.control == control
        assert result.status == SecurityControlStatus.COMPLIANT
        assert result.is_compliant is True
        assert result.remediation_required is False
        assert len(result.evidence) == 1

    @pytest.mark.asyncio
    async def test_validate_authentication_basic(self):
        """Test authentication validation method with real logic."""
        validator = SecurityValidator()

        # Find authentication control
        auth_control = next((c for c in validator.controls if c.id == "AC-001"), None)
        assert auth_control is not None

        # Run validation
        result = await validator._validate_authentication(auth_control)

        # Check result structure
        assert isinstance(result, ValidationResult)
        assert result.control == auth_control
        assert result.status in SecurityControlStatus
        assert "password_policy" in result.details
        assert "lockout_policy" in result.details
        assert len(result.evidence) > 0

    @pytest.mark.asyncio
    async def test_validate_data_at_rest_encryption(self):
        """Test data at rest encryption validation."""
        validator = SecurityValidator()

        # Find encryption control
        encryption_control = next(
            (c for c in validator.controls if c.id == "EN-001"), None
        )
        assert encryption_control is not None

        # Run validation
        result = await validator._validate_data_at_rest_encryption(encryption_control)

        # Check result
        assert isinstance(result, ValidationResult)
        assert result.control == encryption_control
        assert "database_encryption" in result.details
        assert "filesystem_encryption" in result.details
        assert "backup_encryption" in result.details
        assert len(result.evidence) >= 3  # Should have evidence for each type

    def test_generate_security_report_structure(self):
        """Test security report generation structure."""
        validator = SecurityValidator()

        # Add a test result
        test_control = validator.controls[0]
        test_result = ValidationResult(
            control=test_control,
            status=SecurityControlStatus.COMPLIANT,
            timestamp=datetime.now(),
            details={"test": "data"},
            evidence=[{"type": "test"}],
        )
        validator.validation_results = [test_result]

        # Generate report
        report = validator._generate_security_report()

        # Verify report structure
        assert "report_metadata" in report
        assert "executive_summary" in report
        assert "category_summary" in report
        assert "detailed_results" in report
        assert "remediation_plan" in report
        assert "risk_assessment" in report

        # Check executive summary
        assert report["executive_summary"]["total_controls"] == 1
        assert report["executive_summary"]["compliant"] == 1
        assert report["executive_summary"]["compliance_rate"] == 100.0

    def test_hipaa_references_present(self):
        """Test that all controls have valid HIPAA references."""
        validator = SecurityValidator()

        for control in validator.controls:
            # Check HIPAA reference format
            assert control.hipaa_reference.startswith("164.")
            assert len(control.hipaa_reference) > 7  # e.g., "164.312(a)"

            # Verify it's not a placeholder
            assert "test" not in control.hipaa_reference.lower()
            assert "todo" not in control.hipaa_reference.lower()

    @pytest.mark.hipaa_required
    def test_phi_handling_controls_exist(self):
        """Test that PHI handling controls are properly defined."""
        validator = SecurityValidator()

        # Check for encryption controls
        encryption_controls = [
            c
            for c in validator.controls
            if c.category == SecurityControlCategory.ENCRYPTION
        ]
        assert len(encryption_controls) >= 3  # At rest, in transit, key management

        # Check for audit controls
        audit_controls = [
            c
            for c in validator.controls
            if c.category == SecurityControlCategory.AUDIT_LOGGING
        ]
        assert len(audit_controls) >= 3  # Collection, protection, monitoring

        # All should be marked as critical or have high priority
        critical_categories = [
            SecurityControlCategory.ENCRYPTION,
            SecurityControlCategory.AUDIT_LOGGING,
            SecurityControlCategory.ACCESS_CONTROL,
        ]

        for control in validator.controls:
            if control.category in critical_categories:
                # Most should be critical
                if control.id in [
                    "AC-001",
                    "AC-002",
                    "EN-001",
                    "EN-002",
                    "AU-001",
                    "AU-002",
                ]:
                    assert control.critical is True
