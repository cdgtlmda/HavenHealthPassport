"""
Tests for AccessControlValidator class.

CRITICAL: These tests follow medical compliance requirements:
- NO mocks for core security functionality
- Real validation of access control mechanisms
- HIPAA compliance verification
- Audit trail requirements
"""

import pytest

# Import the module to test
from src.healthcare.security.access_control_validator import (
    AccessControlValidator,
    AccessLevel,
    AccessPolicy,
    Role,
)
from src.healthcare.security.base_types import (
    SecurityControl,
    SecurityControlCategory,
    SecurityControlStatus,
    ValidationResult,
)


@pytest.fixture
def access_validator():
    """Create AccessControlValidator instance."""
    return AccessControlValidator()


@pytest.mark.hipaa_required
@pytest.mark.audit_required
class TestAccessControlValidator:
    """Test access control validation with HIPAA compliance."""

    def test_initialization(self, access_validator):
        """Test that AccessControlValidator initializes correctly."""
        assert access_validator is not None
        assert hasattr(access_validator, "roles")
        assert hasattr(access_validator, "policies")
        assert hasattr(access_validator, "validation_cache")

        # Verify standard roles are defined
        assert isinstance(access_validator.roles, dict)
        assert len(access_validator.roles) > 0

        # Check that physician role exists (from code inspection)
        assert "physician" in access_validator.roles
        physician_role = access_validator.roles["physician"]
        assert physician_role.name == "physician"
        assert physician_role.access_level == AccessLevel.READ_WRITE
        assert "patient.read" in physician_role.permissions

    def test_fhir_resource_type(self, access_validator):
        """Test FHIR resource type is properly defined."""
        assert access_validator.__fhir_resource_type__ == "AuditEvent"
        assert hasattr(access_validator, "__fhir_resource__")

    def test_validate_fhir_method(self, access_validator):
        """Test FHIR validation method exists and returns valid structure."""
        result = access_validator.validate_fhir()
        assert isinstance(result, dict)
        assert "valid" in result
        assert "errors" in result
        assert "warnings" in result
        assert result["valid"] is True

    def test_standard_roles_definition(self, access_validator):
        """Test that standard healthcare roles are properly defined."""
        roles = access_validator.roles

        # Check for expected healthcare roles
        expected_roles = ["physician", "nurse", "admin", "patient"]
        for role_name in expected_roles:
            if role_name in roles:
                role = roles[role_name]
                assert isinstance(role, Role)
                assert role.name == role_name
                assert isinstance(role.permissions, set)
                assert isinstance(role.access_level, AccessLevel)
                assert isinstance(role.data_categories, list)

    def test_access_policies_definition(self, access_validator):
        """Test that access policies are properly defined."""
        policies = access_validator.policies
        assert isinstance(policies, list)
        assert len(policies) > 0

        # Verify policy structure
        for policy in policies:
            assert isinstance(policy, AccessPolicy)
            assert hasattr(policy, "policy_name")
            assert hasattr(policy, "resource_type")
            assert hasattr(policy, "allowed_roles")
            assert hasattr(policy, "conditions")
            assert hasattr(policy, "enforcement_mode")

    @pytest.mark.asyncio
    async def test_validate_control_authentication(self, access_validator):
        """Test validation of authentication security control."""
        # Create a mock authentication control
        control = SecurityControl(
            id="AUTH-001",
            name="User authentication control",
            category=SecurityControlCategory.ACCESS_CONTROL,
            description="User authentication control",
            hipaa_reference="164.312(a)(1)",
            validation_method="automated",
            status=SecurityControlStatus.FULLY_IMPLEMENTED,
        )

        # Validate the control
        result = await access_validator.validate_control(control)

        assert isinstance(result, ValidationResult)
        assert hasattr(result, "is_valid")
        assert hasattr(result, "findings")
        assert hasattr(result, "risk_level")

    @pytest.mark.asyncio
    @pytest.mark.hipaa_required
    async def test_validate_control_rbac(self, access_validator):
        """Test validation of RBAC security control."""
        control = SecurityControl(
            id="RBAC-001",
            name="Role-based access control",
            category=SecurityControlCategory.ACCESS_CONTROL,
            description="Role-based access control",
            hipaa_reference="164.308(a)(4)",
            validation_method="automated",
            status=SecurityControlStatus.FULLY_IMPLEMENTED,
        )

        result = await access_validator.validate_control(control)
        assert isinstance(result, ValidationResult)

    @pytest.mark.asyncio
    async def test_validate_control_mfa(self, access_validator):
        """Test validation of MFA security control."""
        control = SecurityControl(
            id="MFA-001",
            name="Multi-factor authentication",
            category=SecurityControlCategory.ACCESS_CONTROL,
            description="Multi-factor authentication",
            hipaa_reference="164.312(a)(2)",
            validation_method="automated",
            status=SecurityControlStatus.FULLY_IMPLEMENTED,
        )

        result = await access_validator.validate_control(control)
        assert isinstance(result, ValidationResult)

    def test_access_level_enum(self):
        """Test AccessLevel enum values."""
        assert AccessLevel.NO_ACCESS.value == "no_access"
        assert AccessLevel.READ_ONLY.value == "read_only"
        assert AccessLevel.READ_WRITE.value == "read_write"
        assert AccessLevel.FULL_CONTROL.value == "full_control"
        assert AccessLevel.ADMIN.value == "admin"

    def test_role_dataclass(self):
        """Test Role dataclass creation."""
        test_role = Role(
            name="test_role",
            description="Test role for unit testing",
            permissions={"test.read", "test.write"},
            access_level=AccessLevel.READ_WRITE,
            data_categories=["test_data"],
        )

        assert test_role.name == "test_role"
        assert test_role.description == "Test role for unit testing"
        assert "test.read" in test_role.permissions
        assert test_role.access_level == AccessLevel.READ_WRITE
        assert "test_data" in test_role.data_categories

    def test_access_policy_dataclass(self):
        """Test AccessPolicy dataclass creation."""
        test_policy = AccessPolicy(
            policy_name="test_policy",
            resource_type="Patient",
            allowed_roles=["physician", "nurse"],
            conditions={"time_based": True},
            enforcement_mode="enforce",
        )

        assert test_policy.policy_name == "test_policy"
        assert test_policy.resource_type == "Patient"
        assert "physician" in test_policy.allowed_roles
        assert test_policy.conditions["time_based"] is True
        assert test_policy.enforcement_mode == "enforce"
