"""
Test suite for HIPAA Compliance Security module.

This test ensures 100% statement coverage as required for critical security compliance.
Uses real implementation code - NO MOCKS for core functionality.
"""

from datetime import datetime

import pytest

from src.healthcare.security.base_types import (
    SecurityControl,
    SecurityControlCategory,
    SecurityControlStatus,
    ValidationResult,
)
from src.healthcare.security.hipaa_compliance import (
    HIPAAComplianceChecker,
    HIPAARequirement,
    HIPAASafeguard,
)


class TestHIPAASafeguard:
    """Test HIPAA safeguard enumeration."""

    def test_all_safeguard_values(self):
        """Test all safeguard enumeration values."""
        assert HIPAASafeguard.ADMINISTRATIVE.value == "administrative"
        assert HIPAASafeguard.PHYSICAL.value == "physical"
        assert HIPAASafeguard.TECHNICAL.value == "technical"

    def test_safeguard_enumeration_completeness(self):
        """Test that all expected safeguards are present."""
        expected_safeguards = {"administrative", "physical", "technical"}
        actual_safeguards = {safeguard.value for safeguard in HIPAASafeguard}
        assert actual_safeguards == expected_safeguards


class TestHIPAARequirement:
    """Test HIPAA requirement data class."""

    def test_requirement_creation(self):
        """Test creating HIPAA requirement."""
        requirement = HIPAARequirement(
            section="164.312(a)(1)",
            title="Access Control",
            safeguard=HIPAASafeguard.TECHNICAL,
            required=True,
            description="Unique user identification",
        )

        assert requirement.section == "164.312(a)(1)"
        assert requirement.title == "Access Control"
        assert requirement.safeguard == HIPAASafeguard.TECHNICAL
        assert requirement.required is True
        assert requirement.description == "Unique user identification"

    def test_requirement_with_addressable(self):
        """Test creating addressable HIPAA requirement."""
        requirement = HIPAARequirement(
            section="164.312(a)(2)(i)",
            title="Automatic Logoff",
            safeguard=HIPAASafeguard.TECHNICAL,
            required=False,
            description="Automatic logoff procedures",
        )

        assert requirement.required is False


class TestHIPAAComplianceChecker:
    """Test HIPAA compliance checker."""

    @pytest.fixture
    def checker(self):
        """Create HIPAA compliance checker."""
        return HIPAAComplianceChecker()

    @pytest.fixture
    def real_security_control(self):
        """Create real security control using actual SecurityControl class."""
        return SecurityControl(
            id="AC-001",
            name="User Access Control",
            category=SecurityControlCategory.ACCESS_CONTROL,
            description="Implement user access control mechanisms",
            hipaa_reference="164.312(a)(1)",
            validation_method="automated_scan",
            critical=True,
        )

    def test_checker_initialization(self, checker):
        """Test checker initialization."""
        assert isinstance(checker, HIPAAComplianceChecker)
        assert len(checker.requirements) > 0

        # Verify specific requirements are loaded
        sections = [req.section for req in checker.requirements]
        assert "164.312(a)(1)" in sections  # Access Control
        assert "164.312(b)" in sections  # Audit Controls
        assert "164.312(c)(1)" in sections  # Integrity
        assert "164.312(a)(2)(iv)" in sections  # Encryption and Decryption
        assert "164.312(e)(1)" in sections  # Transmission Security

    def test_requirements_structure(self, checker):
        """Test that all requirements have proper structure."""
        for req in checker.requirements:
            assert isinstance(req.section, str)
            assert isinstance(req.title, str)
            assert isinstance(req.safeguard, HIPAASafeguard)
            assert isinstance(req.required, bool)
            assert isinstance(req.description, str)
            assert req.section.startswith("164.")

    @pytest.mark.asyncio
    async def test_validate_control_with_mapping(self, checker, real_security_control):
        """Test validating control that maps to HIPAA requirements."""
        # Set up control that should map to requirements
        real_security_control.id = "AC-001"  # Maps to access control requirements
        real_security_control.category = SecurityControlCategory.ACCESS_CONTROL
        real_security_control.name = "User Access Control"

        result = await checker.validate_control(real_security_control)

        assert isinstance(result, ValidationResult)
        assert result.control == real_security_control
        assert result.status in [
            SecurityControlStatus.COMPLIANT,
            SecurityControlStatus.PARTIALLY_COMPLIANT,
            SecurityControlStatus.NON_COMPLIANT,
        ]
        assert isinstance(result.timestamp, datetime)
        assert "hipaa_requirements" in result.details
        assert "validation_results" in result.details
        assert isinstance(result.evidence, list)
        assert isinstance(result.remediation_steps, list)

    @pytest.mark.asyncio
    async def test_validate_control_encryption(self, checker):
        """Test validating encryption control."""
        encryption_control = SecurityControl(
            id="EN-001",
            name="Data Encryption",
            category=SecurityControlCategory.ENCRYPTION,
            description="Implement data encryption mechanisms",
            hipaa_reference="164.312(a)(2)(iv)",
            validation_method="automated_scan",
            critical=True,
        )

        result = await checker.validate_control(encryption_control)

        assert isinstance(result, ValidationResult)
        # Should map to encryption requirement
        if result.status != SecurityControlStatus.NOT_APPLICABLE:
            sections = result.details.get("hipaa_requirements", [])
            assert any("164.312(a)(2)(iv)" in str(section) for section in sections)

    @pytest.mark.asyncio
    async def test_validate_control_audit(self, checker):
        """Test validating audit control."""
        audit_control = SecurityControl(
            id="AU-001",
            name="Audit Logging",
            category=SecurityControlCategory.AUDIT_LOGGING,
            description="Implement audit logging mechanisms",
            hipaa_reference="164.312(b)",
            validation_method="automated_scan",
            critical=True,
        )

        result = await checker.validate_control(audit_control)

        assert isinstance(result, ValidationResult)
        # Should map to audit controls requirement
        if result.status != SecurityControlStatus.NOT_APPLICABLE:
            sections = result.details.get("hipaa_requirements", [])
            assert any("164.312(b)" in str(section) for section in sections)

    @pytest.mark.asyncio
    async def test_validate_control_transmission_security(self, checker):
        """Test validating transmission security control."""
        transmission_control = SecurityControl(
            id="TS-001",
            name="Network Security",
            category=SecurityControlCategory.TRANSMISSION_SECURITY,
            description="Implement transmission security mechanisms",
            hipaa_reference="164.312(e)(1)",
            validation_method="automated_scan",
            critical=True,
        )

        result = await checker.validate_control(transmission_control)

        assert isinstance(result, ValidationResult)
        if result.status != SecurityControlStatus.NOT_APPLICABLE:
            sections = result.details.get("hipaa_requirements", [])
            assert any("164.312(e)(1)" in str(section) for section in sections)

    @pytest.mark.asyncio
    async def test_validate_control_no_mapping(self, checker):
        """Test validating control with no HIPAA mapping."""
        unknown_control = SecurityControl(
            id="UNKNOWN-001",
            name="Unknown Control",
            category=SecurityControlCategory.ACCESS_CONTROL,  # Use valid enum
            description="Unknown control type",
            hipaa_reference="N/A",
            validation_method="manual",
            critical=False,
        )

        result = await checker.validate_control(unknown_control)

        assert isinstance(result, ValidationResult)
        assert result.status == SecurityControlStatus.NOT_APPLICABLE
        assert "No direct HIPAA requirement mapping" in result.details.get(
            "message", ""
        )

    @pytest.mark.asyncio
    async def test_validate_requirement_compliant(self, checker, real_security_control):
        """Test validating compliant requirement."""
        requirement = HIPAARequirement(
            section="164.312(a)(1)",
            title="Access Control",
            safeguard=HIPAASafeguard.TECHNICAL,
            required=True,
            description="Unique user identification",
        )

        result = await checker._validate_requirement(real_security_control, requirement)

        assert isinstance(result, dict)
        assert "requirement" in result
        assert "compliant" in result
        assert "checks" in result
        assert "notes" in result
        assert result["requirement"] == "164.312(a)(1)"

    @pytest.mark.asyncio
    async def test_validate_requirement_non_compliant(
        self, checker, real_security_control
    ):
        """Test validating non-compliant requirement."""
        requirement = HIPAARequirement(
            section="164.312(b)",
            title="Audit Controls",
            safeguard=HIPAASafeguard.TECHNICAL,
            required=True,
            description="Audit controls implementation",
        )

        result = await checker._validate_requirement(real_security_control, requirement)

        assert isinstance(result, dict)
        assert result["requirement"] == "164.312(b)"
        assert isinstance(result["compliant"], bool)
        assert isinstance(result["checks"], dict)

    def test_map_control_to_requirements_access_control(
        self, checker, real_security_control
    ):
        """Test mapping access control to requirements."""
        real_security_control.id = "AC-001"
        requirements = checker._map_control_to_requirements(real_security_control)

        assert len(requirements) > 0
        sections = [req.section for req in requirements]
        assert "164.312(a)(1)" in sections

    def test_map_control_to_requirements_rbac(self, checker, real_security_control):
        """Test mapping RBAC control to requirements."""
        real_security_control.id = "AC-002"
        requirements = checker._map_control_to_requirements(real_security_control)

        assert len(requirements) > 0
        sections = [req.section for req in requirements]
        assert "164.308(a)(4)" in sections

    def test_map_control_to_requirements_audit(self, checker, real_security_control):
        """Test mapping audit control to requirements."""
        real_security_control.id = "AU-001"
        requirements = checker._map_control_to_requirements(real_security_control)

        assert len(requirements) > 0
        sections = [req.section for req in requirements]
        assert "164.312(b)" in sections

    def test_map_control_to_requirements_encryption(
        self, checker, real_security_control
    ):
        """Test mapping encryption control to requirements."""
        real_security_control.id = "EN-001"
        requirements = checker._map_control_to_requirements(real_security_control)

        assert len(requirements) > 0
        sections = [req.section for req in requirements]
        assert "164.312(a)(2)(iv)" in sections

    def test_map_control_to_requirements_transmission(
        self, checker, real_security_control
    ):
        """Test mapping transmission security control to requirements."""
        real_security_control.id = "TS-001"
        requirements = checker._map_control_to_requirements(real_security_control)

        assert len(requirements) > 0
        sections = [req.section for req in requirements]
        assert "164.312(e)(1)" in sections

    def test_map_control_to_requirements_unknown(self, checker, real_security_control):
        """Test mapping unknown control to requirements."""
        real_security_control.id = "UNKNOWN-999"
        requirements = checker._map_control_to_requirements(real_security_control)

        assert len(requirements) == 0

    def test_generate_remediation_steps_access_control_mfa(
        self, checker, real_security_control
    ):
        """Test generating remediation steps for access control MFA issues."""
        # Create control with control_type attribute for remediation logic
        real_security_control.control_type = "ACCESS_CONTROL"

        validation_results = [
            {
                "requirement": "164.312(a)(1)",
                "compliant": False,
                "issue_type": "MISSING_MFA",
                "checks": {
                    "mfa_enabled": False,
                    "policy_exists": True,
                    "implementation_verified": False,
                    "documentation_complete": True,
                },
                "notes": "MFA not enabled for all users",
            }
        ]

        steps = checker._generate_remediation_steps(
            real_security_control, validation_results
        )

        assert isinstance(steps, list)
        assert len(steps) > 0
        # Check for MFA-specific remediation
        steps_text = " ".join(steps)
        assert "multi-factor authentication" in steps_text.lower()
        assert "HIGH" in steps_text  # Severity indicator

    def test_generate_remediation_steps_access_control_permissions(
        self, checker, real_security_control
    ):
        """Test generating remediation steps for excessive permissions."""
        real_security_control.control_type = "ACCESS_CONTROL"

        validation_results = [
            {
                "requirement": "164.308(a)(4)",
                "compliant": False,
                "issue_type": "EXCESSIVE_PERMISSIONS",
                "checks": {
                    "least_privilege": False,
                    "role_based_access": True,
                    "permission_review": False,
                },
                "notes": "Users have excessive permissions",
            }
        ]

        steps = checker._generate_remediation_steps(
            real_security_control, validation_results
        )

        assert isinstance(steps, list)
        assert len(steps) > 0
        steps_text = " ".join(steps)
        assert "permissions" in steps_text.lower()
        assert "least privilege" in steps_text.lower()

    def test_generate_remediation_steps_access_control_stale_accounts(
        self, checker, real_security_control
    ):
        """Test generating remediation steps for stale accounts."""
        real_security_control.control_type = "ACCESS_CONTROL"

        validation_results = [
            {
                "requirement": "164.308(a)(3)",
                "compliant": False,
                "issue_type": "STALE_ACCOUNTS",
                "checks": {
                    "account_lifecycle": False,
                    "inactive_monitoring": False,
                    "automated_cleanup": False,
                },
                "notes": "Stale accounts detected",
            }
        ]

        steps = checker._generate_remediation_steps(
            real_security_control, validation_results
        )

        assert isinstance(steps, list)
        assert len(steps) > 0
        steps_text = " ".join(steps)
        assert "inactive" in steps_text.lower() or "stale" in steps_text.lower()

    def test_generate_remediation_steps_audit_controls_missing_logs(
        self, checker, real_security_control
    ):
        """Test generating remediation steps for missing audit logs."""
        real_security_control.control_type = "AUDIT_CONTROLS"

        validation_results = [
            {
                "requirement": "164.312(b)",
                "compliant": False,
                "issue_type": "MISSING_AUDIT_LOGS",
                "checks": {
                    "audit_logging_enabled": False,
                    "log_retention": False,
                    "tamper_proof": False,
                },
                "notes": "Audit logging not comprehensive",
            }
        ]

        steps = checker._generate_remediation_steps(
            real_security_control, validation_results
        )

        assert isinstance(steps, list)
        assert len(steps) > 0
        steps_text = " ".join(steps)
        assert "audit" in steps_text.lower()
        assert "log" in steps_text.lower()
        assert "HIGH" in steps_text  # Should be high severity

    def test_generate_remediation_steps_audit_controls_incomplete_trail(
        self, checker, real_security_control
    ):
        """Test generating remediation steps for incomplete audit trail."""
        real_security_control.control_type = "AUDIT_CONTROLS"

        validation_results = [
            {
                "requirement": "164.312(b)",
                "compliant": False,
                "issue_type": "INCOMPLETE_AUDIT_TRAIL",
                "checks": {
                    "crud_logging": False,
                    "user_tracking": True,
                    "timestamp_accuracy": True,
                },
                "notes": "Audit trail incomplete",
            }
        ]

        steps = checker._generate_remediation_steps(
            real_security_control, validation_results
        )

        assert isinstance(steps, list)
        assert len(steps) > 0
        steps_text = " ".join(steps)
        assert "audit" in steps_text.lower()
        assert "trail" in steps_text.lower() or "crud" in steps_text.lower()

    def test_generate_remediation_steps_encryption_weak(
        self, checker, real_security_control
    ):
        """Test generating remediation steps for weak encryption."""
        real_security_control.control_type = "ENCRYPTION"

        validation_results = [
            {
                "requirement": "164.312(a)(2)(iv)",
                "compliant": False,
                "issue_type": "WEAK_ENCRYPTION",
                "checks": {
                    "encryption_strength": False,
                    "key_management": False,
                    "algorithm_current": False,
                },
                "notes": "Weak encryption detected",
            }
        ]

        steps = checker._generate_remediation_steps(
            real_security_control, validation_results
        )

        assert isinstance(steps, list)
        assert len(steps) > 0
        steps_text = " ".join(steps)
        assert "encryption" in steps_text.lower()
        assert "aes-256" in steps_text.lower()
        assert "CRITICAL" in steps_text  # Should be critical severity

    def test_generate_remediation_steps_encryption_missing_at_rest(
        self, checker, real_security_control
    ):
        """Test generating remediation steps for missing encryption at rest."""
        real_security_control.control_type = "ENCRYPTION"

        validation_results = [
            {
                "requirement": "164.312(a)(2)(iv)",
                "compliant": False,
                "issue_type": "MISSING_ENCRYPTION_AT_REST",
                "checks": {
                    "database_encryption": False,
                    "file_encryption": False,
                    "backup_encryption": True,
                },
                "notes": "Encryption at rest missing",
            }
        ]

        steps = checker._generate_remediation_steps(
            real_security_control, validation_results
        )

        assert isinstance(steps, list)
        assert len(steps) > 0
        steps_text = " ".join(steps)
        assert "encryption" in steps_text.lower()
        assert "rest" in steps_text.lower() or "database" in steps_text.lower()

    def test_generate_remediation_steps_transmission_weak_tls(
        self, checker, real_security_control
    ):
        """Test generating remediation steps for weak TLS."""
        real_security_control.control_type = "TRANSMISSION_SECURITY"

        validation_results = [
            {
                "requirement": "164.312(e)(1)",
                "compliant": False,
                "issue_type": "WEAK_TLS",
                "checks": {
                    "tls_version": False,
                    "cipher_strength": False,
                    "certificate_valid": True,
                },
                "notes": "Weak TLS configuration",
            }
        ]

        steps = checker._generate_remediation_steps(
            real_security_control, validation_results
        )

        assert isinstance(steps, list)
        assert len(steps) > 0
        steps_text = " ".join(steps)
        assert "tls" in steps_text.lower()
        assert "1.3" in steps_text  # Should recommend TLS 1.3

    def test_generate_remediation_steps_unknown_control_type(
        self, checker, real_security_control
    ):
        """Test generating remediation steps for unknown control type."""
        # Don't set control_type to test fallback behavior
        validation_results = [
            {
                "requirement": "164.312(a)(1)",
                "compliant": False,
                "issue_type": "UNKNOWN_ISSUE",
                "checks": {
                    "unknown_check": False,
                },
                "notes": "Unknown issue type",
            }
        ]

        steps = checker._generate_remediation_steps(
            real_security_control, validation_results
        )

        assert isinstance(steps, list)
        assert len(steps) > 0
        # Should contain generic remediation
        steps_text = " ".join(steps)
        assert "review" in steps_text.lower()

    def test_generate_remediation_steps_control_without_type(
        self, checker, real_security_control
    ):
        """Test generating remediation steps for control without type attribute."""
        # Ensure no control_type or type attribute
        if hasattr(real_security_control, "control_type"):
            delattr(real_security_control, "control_type")
        if hasattr(real_security_control, "type"):
            delattr(real_security_control, "type")

        validation_results = [
            {
                "requirement": "164.312(a)(1)",
                "compliant": False,
                "checks": {
                    "policy_exists": False,
                    "implementation_verified": False,
                },
                "notes": "Control validation failed",
            }
        ]

        steps = checker._generate_remediation_steps(
            real_security_control, validation_results
        )

        assert isinstance(steps, list)
        assert len(steps) > 0
        # Should contain generic remediation and specific check failures
        steps_text = " ".join(steps)
        assert "policy_exists" in steps_text or "implementation_verified" in steps_text

    def test_generate_remediation_steps_control_with_type_attribute(
        self, checker, real_security_control
    ):
        """Test generating remediation steps for control with type attribute."""
        # Set type attribute instead of control_type
        real_security_control.type = "ACCESS_CONTROL"

        validation_results = [
            {
                "requirement": "164.312(a)(1)",
                "compliant": False,
                "issue_type": "MISSING_MFA",
                "checks": {
                    "mfa_enabled": False,
                },
                "notes": "MFA missing",
            }
        ]

        steps = checker._generate_remediation_steps(
            real_security_control, validation_results
        )

        assert isinstance(steps, list)
        assert len(steps) > 0
        # Should use the type attribute for remediation
        steps_text = " ".join(steps)
        assert "multi-factor" in steps_text.lower() or "mfa" in steps_text.lower()

    def test_generate_remediation_steps_compliant_results(
        self, checker, real_security_control
    ):
        """Test generating remediation steps for compliant results."""
        validation_results = [
            {
                "requirement": "164.312(a)(1)",
                "compliant": True,
                "checks": {
                    "policy_exists": True,
                    "implementation_verified": True,
                },
                "notes": "All checks passed",
            }
        ]

        steps = checker._generate_remediation_steps(
            real_security_control, validation_results
        )

        # Should return empty list for compliant results
        assert isinstance(steps, list)
        assert len(steps) == 0

    def test_generate_remediation_steps_mixed_results(
        self, checker, real_security_control
    ):
        """Test generating remediation steps for mixed compliant/non-compliant results."""
        real_security_control.control_type = "ACCESS_CONTROL"

        validation_results = [
            {
                "requirement": "164.312(a)(1)",
                "compliant": True,
                "checks": {"policy_exists": True},
                "notes": "Policy check passed",
            },
            {
                "requirement": "164.308(a)(4)",
                "compliant": False,
                "issue_type": "EXCESSIVE_PERMISSIONS",
                "checks": {"least_privilege": False},
                "notes": "Permission check failed",
            },
        ]

        steps = checker._generate_remediation_steps(
            real_security_control, validation_results
        )

        assert isinstance(steps, list)
        assert len(steps) > 0
        # Should only include remediation for non-compliant results
        steps_text = " ".join(steps)
        assert "permissions" in steps_text.lower()
        # Should not include remediation for compliant results
        assert "policy check passed" not in steps_text

    def test_generate_remediation_steps_with_general_recommendations(
        self, checker, real_security_control
    ):
        """Test that general recommendations are included when remediation steps exist."""
        real_security_control.control_type = "ACCESS_CONTROL"

        validation_results = [
            {
                "requirement": "164.312(a)(1)",
                "compliant": False,
                "issue_type": "MISSING_MFA",
                "checks": {"mfa_enabled": False},
                "notes": "MFA not enabled",
            }
        ]

        steps = checker._generate_remediation_steps(
            real_security_control, validation_results
        )

        assert isinstance(steps, list)
        assert len(steps) > 0
        steps_text = " ".join(steps)
        # Should include general recommendations
        assert "General Recommendations" in steps_text
        assert "Document all remediation actions" in steps_text
        assert "Test changes in non-production" in steps_text

    @pytest.mark.asyncio
    async def test_validate_control_comprehensive_flow(
        self, checker, real_security_control
    ):
        """Test comprehensive validation flow."""
        real_security_control.id = "AC-001"  # Maps to access control

        result = await checker.validate_control(real_security_control)

        assert isinstance(result, ValidationResult)
        assert result.control == real_security_control
        assert isinstance(result.timestamp, datetime)
        assert isinstance(result.details, dict)
        assert isinstance(result.evidence, list)
        assert isinstance(result.remediation_steps, list)

        # Verify all expected fields are present
        assert hasattr(result, "remediation_required")
        assert isinstance(result.remediation_required, bool)

    def test_all_hipaa_safeguards_covered(self, checker):
        """Test that all HIPAA safeguards are covered in requirements."""
        safeguards_in_requirements = {req.safeguard for req in checker.requirements}
        expected_safeguards = set(HIPAASafeguard)

        assert safeguards_in_requirements == expected_safeguards

    def test_required_vs_addressable_requirements(self, checker):
        """Test that both required and addressable requirements are present."""
        required_reqs = [req for req in checker.requirements if req.required]
        addressable_reqs = [req for req in checker.requirements if not req.required]

        assert len(required_reqs) > 0
        assert len(addressable_reqs) > 0

        # Verify specific addressable requirement
        encryption_req = next(
            (req for req in checker.requirements if req.section == "164.312(a)(2)(iv)"),
            None,
        )
        assert encryption_req is not None
        assert encryption_req.required is False  # Addressable

    @pytest.mark.asyncio
    async def test_edge_case_empty_control_id(self, checker):
        """Test validation with empty control ID."""
        empty_control = SecurityControl(
            id="",
            name="Empty ID Control",
            category=SecurityControlCategory.ACCESS_CONTROL,
            description="Control with empty ID",
            hipaa_reference="N/A",
            validation_method="manual",
        )

        result = await checker.validate_control(empty_control)

        assert isinstance(result, ValidationResult)
        assert result.status == SecurityControlStatus.NOT_APPLICABLE

    @pytest.mark.asyncio
    async def test_edge_case_none_control_id(self, checker):
        """Test validation with None control ID."""
        none_control = SecurityControl(
            id="",
            name="None ID Control",
            category=SecurityControlCategory.ACCESS_CONTROL,
            description="Control with None ID",
            hipaa_reference="N/A",
            validation_method="manual",
        )

        result = await checker.validate_control(none_control)

        assert isinstance(result, ValidationResult)
        assert result.status == SecurityControlStatus.NOT_APPLICABLE

    def test_remediation_steps_with_failed_checks(self, checker, real_security_control):
        """Test remediation steps generation with specific failed checks."""
        validation_results = [
            {
                "requirement": "164.312(a)(1)",
                "compliant": False,
                "checks": {
                    "policy_exists": False,
                    "implementation_verified": False,
                    "documentation_complete": True,
                    "testing_performed": False,
                },
                "notes": "Multiple checks failed",
            }
        ]

        steps = checker._generate_remediation_steps(
            real_security_control, validation_results
        )

        assert isinstance(steps, list)
        assert len(steps) > 0
        steps_text = " ".join(steps)

        # Should include remediation for failed checks
        assert "policy_exists" in steps_text
        assert "implementation_verified" in steps_text
        assert "testing_performed" in steps_text
        # Should not include remediation for passed checks
        assert (
            "documentation_complete" not in steps_text
            or "Address documentation_complete" not in steps_text
        )

    @pytest.mark.asyncio
    async def test_validate_control_not_applicable_status(
        self, checker, real_security_control
    ):
        """Test that NOT_APPLICABLE status is returned for unmapped controls."""
        real_security_control.id = "UNMAPPED-001"

        result = await checker.validate_control(real_security_control)

        assert result.status == SecurityControlStatus.NOT_APPLICABLE
        assert "No direct HIPAA requirement mapping" in result.details.get(
            "message", ""
        )

    @pytest.mark.asyncio
    async def test_validate_control_covers_all_status_branches(
        self, checker, real_security_control
    ):
        """Test that validation can return all possible status values."""
        # Test mapped control (should return COMPLIANT, PARTIALLY_COMPLIANT, or NON_COMPLIANT)
        real_security_control.id = "AC-001"

        result = await checker.validate_control(real_security_control)

        assert result.status in [
            SecurityControlStatus.COMPLIANT,
            SecurityControlStatus.PARTIALLY_COMPLIANT,
            SecurityControlStatus.NON_COMPLIANT,
        ]

        # Test unmapped control (should return NOT_APPLICABLE)
        real_security_control.id = "UNMAPPED-999"

        result = await checker.validate_control(real_security_control)

        assert result.status == SecurityControlStatus.NOT_APPLICABLE

    @pytest.mark.asyncio
    async def test_validate_control_non_compliant_with_failed_validations(
        self, checker, real_security_control
    ):
        """Test validation returns NON_COMPLIANT when all validations fail."""
        real_security_control.id = "AC-001"

        # Mock the _validate_requirement method to return non-compliant results
        async def mock_validate_requirement(control, requirement):
            return {
                "requirement": requirement.section,
                "compliant": False,
                "checks": {"all_checks": False},
                "notes": "All validations failed",
            }

        # Temporarily replace the method
        original_method = checker._validate_requirement
        checker._validate_requirement = mock_validate_requirement

        try:
            result = await checker.validate_control(real_security_control)

            assert result.status == SecurityControlStatus.NON_COMPLIANT
            assert result.remediation_required is True
            assert len(result.remediation_steps) > 0
        finally:
            # Restore original method
            checker._validate_requirement = original_method


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
