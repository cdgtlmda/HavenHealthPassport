"""Comprehensive test coverage for authentication models - HIPAA compliance required.

This module tests all authentication models with real database operations.
No mocks allowed - we test actual behavior that refugee lives depend on.
"""

import uuid
from datetime import date, datetime, timedelta

import bcrypt
import pytest

from src.models.auth import (
    APIKey,
    BackupCode,
    BiometricAuditLog,
    BiometricTemplate,
    DeviceInfo,
    LoginAttempt,
    MFAConfig,
    PasswordHistory,
    PasswordResetToken,
    SMSVerificationCode,
    UserAuth,
    UserRole,
    UserSession,
    WebAuthnCredential,
)
from src.models.patient import Gender, Patient


@pytest.fixture
def test_patient(db_session):
    """Create a test patient for user authentication."""
    patient = Patient(
        given_name="Test",
        family_name="Patient",
        date_of_birth=date(1990, 1, 1),
        gender=Gender.OTHER,
        origin_country="US",
        created_by=uuid.uuid4(),
    )
    db_session.add(patient)
    db_session.commit()
    return patient


@pytest.fixture
def test_user_auth(db_session, test_patient):
    """Create a test user auth."""
    password = "SecurePass123!"
    password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode(
        "utf-8"
    )

    user = UserAuth(
        patient_id=test_patient.id,
        email="test@example.com",
        phone_number="+1234567890",
        password_hash=password_hash,
        role=UserRole.PATIENT,
        created_by=uuid.uuid4(),
    )
    db_session.add(user)
    db_session.commit()
    return user


class TestUserAuthModel:
    """Test UserAuth model functionality."""

    @pytest.mark.hipaa_required
    def test_user_auth_creation(self, db_session, test_patient):
        """Test creating a UserAuth instance."""
        user = UserAuth(
            patient_id=test_patient.id,
            email="user@example.com",
            phone_number="+1234567890",
            password_hash="hashed_password",
            role=UserRole.HEALTHCARE_PROVIDER,
            created_by=uuid.uuid4(),
        )

        db_session.add(user)
        db_session.commit()

        assert user.id is not None
        assert user.email == "user@example.com"
        assert user.role == UserRole.HEALTHCARE_PROVIDER
        assert user.is_active is True
        assert user.is_locked is False
        assert user.email_verified is False
        assert user.phone_verified is False
        assert user.failed_login_attempts == 0

    @pytest.mark.hipaa_required
    def test_user_auth_repr(self, test_user_auth):
        """Test UserAuth string representation."""
        expected = (
            f"<UserAuth(id={test_user_auth.id}, email=test@example.com, role=patient)>"
        )
        assert repr(test_user_auth) == expected

    @pytest.mark.hipaa_required
    def test_is_admin_property(self, db_session, test_patient):
        """Test is_admin property for different roles."""
        # Test non-admin user
        regular_user = UserAuth(
            patient_id=test_patient.id,
            email="regular@example.com",
            phone_number="+1111111111",
            password_hash="hash",
            role=UserRole.PATIENT,
            created_by=uuid.uuid4(),
        )
        db_session.add(regular_user)
        db_session.commit()
        assert regular_user.is_admin is False

        # Test admin user
        admin_user = UserAuth(
            patient_id=test_patient.id,
            email="admin@example.com",
            phone_number="+2222222222",
            password_hash="hash",
            role=UserRole.ADMIN,
            created_by=uuid.uuid4(),
        )
        db_session.add(admin_user)
        db_session.commit()
        assert admin_user.is_admin is True

        # Test super admin
        super_admin = UserAuth(
            patient_id=test_patient.id,
            email="super@example.com",
            phone_number="+3333333333",
            password_hash="hash",
            role=UserRole.SUPER_ADMIN,
            created_by=uuid.uuid4(),
        )
        db_session.add(super_admin)
        db_session.commit()
        assert super_admin.is_admin is True

    @pytest.mark.hipaa_required
    def test_is_healthcare_provider_property(self, db_session, test_patient):
        """Test is_healthcare_provider property."""
        provider = UserAuth(
            patient_id=test_patient.id,
            email="provider@example.com",
            phone_number="+4444444444",
            password_hash="hash",
            role=UserRole.HEALTHCARE_PROVIDER,
            created_by=uuid.uuid4(),
        )
        db_session.add(provider)
        db_session.commit()

        assert provider.is_healthcare_provider is True
        assert test_patient.auth.is_healthcare_provider is False

    @pytest.mark.hipaa_required
    def test_has_permission_method(self, db_session, test_patient):
        """Test permission checking for all roles."""
        # Test patient permissions
        patient_user = UserAuth(
            patient_id=test_patient.id,
            email="patient@example.com",
            phone_number="+5555555555",
            password_hash="hash",
            role=UserRole.PATIENT,
            created_by=uuid.uuid4(),
        )
        db_session.add(patient_user)
        db_session.commit()

        assert patient_user.has_permission("read:own_records") is True
        assert patient_user.has_permission("update:own_profile") is True
        assert patient_user.has_permission("grant:access") is True
        assert patient_user.has_permission("revoke:access") is True
        assert patient_user.has_permission("read:all") is False

        # Test NGO worker permissions
        ngo_user = UserAuth(
            patient_id=test_patient.id,
            email="ngo@example.com",
            phone_number="+6666666666",
            password_hash="hash",
            role=UserRole.NGO_WORKER,
            created_by=uuid.uuid4(),
        )
        db_session.add(ngo_user)
        db_session.commit()

        assert ngo_user.has_permission("read:patient_records") is True
        assert ngo_user.has_permission("create:patients") is True
        assert ngo_user.has_permission("update:patients") is True
        assert ngo_user.has_permission("create:verifications") is True
        assert ngo_user.has_permission("delete:all") is False

        # Test custom permissions
        patient_user.custom_permissions = ["special:permission"]
        db_session.commit()
        assert patient_user.has_permission("special:permission") is True

        # Test empty custom permissions
        patient_user.custom_permissions = None
        db_session.commit()
        assert patient_user.has_permission("special:permission") is False

    @pytest.mark.hipaa_required
    def test_user_auth_relationships(self, db_session, test_user_auth):
        """Test UserAuth relationships."""
        # Create related objects
        session = UserSession(
            user_id=test_user_auth.id,
            token="test_token",
            expires_at=datetime.utcnow() + timedelta(hours=1),
        )

        device = DeviceInfo(
            user_id=test_user_auth.id,
            device_fingerprint="test_fingerprint",
            device_name="Test Device",
        )

        mfa = MFAConfig(user_id=test_user_auth.id, totp_enabled=True)

        db_session.add_all([session, device, mfa])
        db_session.commit()

        # Test relationships
        assert len(test_user_auth.sessions) == 1
        assert test_user_auth.sessions[0].token == "test_token"
        assert len(test_user_auth.devices) == 1
        assert test_user_auth.devices[0].device_name == "Test Device"
        assert test_user_auth.mfa_config.totp_enabled is True


class TestUserSessionModel:
    """Test UserSession model to achieve comprehensive coverage."""

    @pytest.mark.hipaa_required
    def test_user_session_creation(self, db_session, test_user_auth):
        """Test creating a UserSession instance."""
        expires = datetime.utcnow() + timedelta(hours=2)
        session = UserSession(
            user_id=test_user_auth.id,
            token="session_token_123",
            refresh_token="refresh_token_123",
            session_type="mobile",
            timeout_policy="absolute",
            expires_at=expires,
            ip_address="192.168.1.1",
            user_agent="TestApp/1.0",
        )

        db_session.add(session)
        db_session.commit()

        assert session.id is not None
        assert session.is_active is True
        assert session.is_expired is False
        assert session.is_valid is True

    @pytest.mark.hipaa_required
    def test_user_session_repr(self, db_session, test_user_auth):
        """Test UserSession string representation."""
        session = UserSession(
            user_id=test_user_auth.id,
            token="test_token",
            expires_at=datetime.utcnow() + timedelta(hours=1),
        )
        db_session.add(session)
        db_session.commit()

        expected = (
            f"<UserSession(id={session.id}, user_id={test_user_auth.id}, active=True)>"
        )
        assert repr(session) == expected

    @pytest.mark.hipaa_required
    def test_session_expiration(self, db_session, test_user_auth):
        """Test session expiration logic."""
        # Create expired session
        past_time = datetime.utcnow() - timedelta(hours=1)
        expired_session = UserSession(
            user_id=test_user_auth.id, token="expired_token", expires_at=past_time
        )
        db_session.add(expired_session)
        db_session.commit()

        assert expired_session.is_expired is True
        assert expired_session.is_valid is False

        # Test inactive session
        active_session = UserSession(
            user_id=test_user_auth.id,
            token="inactive_token",
            expires_at=datetime.utcnow() + timedelta(hours=1),
            is_active=False,
        )
        db_session.add(active_session)
        db_session.commit()

        assert active_session.is_expired is False
        assert active_session.is_valid is False


class TestDeviceInfoModel:
    """Test DeviceInfo model to achieve comprehensive coverage."""

    @pytest.mark.hipaa_required
    def test_device_info_creation(self, db_session, test_user_auth):
        """Test creating a DeviceInfo instance."""
        device = DeviceInfo(
            user_id=test_user_auth.id,
            device_fingerprint="unique_fingerprint_123",
            device_name="iPhone 12",
            device_type="mobile",
            platform="iOS",
            platform_version="15.0",
            browser="Safari",
            browser_version="15.0",
            ip_address="192.168.1.100",
            user_agent="Mozilla/5.0 iPhone",
            is_trusted=True,
            trusted_at=datetime.utcnow(),
        )

        db_session.add(device)
        db_session.commit()

        assert device.id is not None
        assert device.device_name == "iPhone 12"
        assert device.is_trusted is True
        assert device.login_count == 0

    @pytest.mark.hipaa_required
    def test_device_info_repr(self, db_session, test_user_auth):
        """Test DeviceInfo string representation."""
        device = DeviceInfo(
            user_id=test_user_auth.id,
            device_fingerprint="test_fp",
            device_name="Test Device",
            is_trusted=False,
        )
        db_session.add(device)
        db_session.commit()

        expected = f"<DeviceInfo(id={device.id}, device=Test Device, trusted=False)>"
        assert repr(device) == expected


class TestMFAConfigModel:
    """Test MFAConfig model to achieve comprehensive coverage."""

    @pytest.mark.hipaa_required
    def test_mfa_config_creation(self, db_session, test_user_auth):
        """Test creating an MFAConfig instance."""
        mfa = MFAConfig(
            user_id=test_user_auth.id,
            totp_enabled=True,
            totp_secret="secret123",
            totp_verified=True,
            totp_verified_at=datetime.utcnow(),
            sms_enabled=True,
            sms_phone_number="+1234567890",
            email_enabled=False,
            backup_codes=["hash1", "hash2", "hash3"],
            recovery_email="recovery@example.com",
        )

        db_session.add(mfa)
        db_session.commit()

        assert mfa.id is not None
        assert mfa.is_enabled is True
        assert len(mfa.enabled_methods) == 2
        assert "totp" in mfa.enabled_methods
        assert "sms" in mfa.enabled_methods
        assert "email" not in mfa.enabled_methods

    @pytest.mark.hipaa_required
    def test_mfa_config_repr(self, db_session, test_user_auth):
        """Test MFAConfig string representation."""
        mfa = MFAConfig(user_id=test_user_auth.id, totp_enabled=True, sms_enabled=False)
        db_session.add(mfa)
        db_session.commit()

        expected = f"<MFAConfig(user_id={test_user_auth.id}, totp=True, sms=False)>"
        assert repr(mfa) == expected

    @pytest.mark.hipaa_required
    def test_mfa_no_methods_enabled(self, db_session, test_user_auth):
        """Test MFA with no methods enabled."""
        mfa = MFAConfig(
            user_id=test_user_auth.id,
            totp_enabled=False,
            sms_enabled=False,
            email_enabled=False,
        )
        db_session.add(mfa)
        db_session.commit()

        assert mfa.is_enabled is False
        assert len(mfa.enabled_methods) == 0


class TestPasswordHistoryModel:
    """Test PasswordHistory model to achieve comprehensive coverage."""

    @pytest.mark.hipaa_required
    def test_password_history_creation(self, db_session, test_user_auth):
        """Test creating a PasswordHistory instance."""
        history = PasswordHistory(
            user_id=test_user_auth.id, password_hash="old_password_hash"
        )

        db_session.add(history)
        db_session.commit()

        assert history.id is not None
        assert history.password_hash == "old_password_hash"
        assert history.created_at is not None

    @pytest.mark.hipaa_required
    def test_password_history_repr(self, db_session, test_user_auth):
        """Test PasswordHistory string representation."""
        history = PasswordHistory(user_id=test_user_auth.id, password_hash="hash123")
        db_session.add(history)
        db_session.commit()

        expected = f"<PasswordHistory(user_id={test_user_auth.id}, created_at={history.created_at})>"
        assert repr(history) == expected


class TestLoginAttemptModel:
    """Test LoginAttempt model to achieve comprehensive coverage."""

    @pytest.mark.hipaa_required
    def test_login_attempt_success(self, db_session, test_user_auth):
        """Test successful login attempt."""
        attempt = LoginAttempt(
            user_id=test_user_auth.id,
            username="test@example.com",
            success=True,
            ip_address="192.168.1.1",
            user_agent="Mozilla/5.0",
            device_fingerprint="device123",
            session_id=uuid.uuid4(),
        )

        db_session.add(attempt)
        db_session.commit()

        assert attempt.id is not None
        assert attempt.success is True
        assert attempt.failure_reason is None

    @pytest.mark.hipaa_required
    def test_login_attempt_failure(self, db_session):
        """Test failed login attempt."""
        attempt = LoginAttempt(
            username="invalid@example.com",
            success=False,
            failure_reason="Invalid credentials",
            ip_address="192.168.1.2",
            user_agent="TestBrowser/1.0",
        )

        db_session.add(attempt)
        db_session.commit()

        assert attempt.success is False
        assert attempt.failure_reason == "Invalid credentials"
        assert attempt.user_id is None

    @pytest.mark.hipaa_required
    def test_login_attempt_repr(self, db_session, test_user_auth):
        """Test LoginAttempt string representation."""
        attempt = LoginAttempt(
            user_id=test_user_auth.id, username="test@example.com", success=True
        )
        db_session.add(attempt)
        db_session.commit()

        expected = f"<LoginAttempt(user_id={test_user_auth.id}, success=True, at={attempt.attempted_at})>"
        assert repr(attempt) == expected


class TestBiometricTemplateModel:
    """Test BiometricTemplate model to achieve comprehensive coverage."""

    @pytest.mark.hipaa_required
    def test_biometric_template_creation(self, db_session, test_user_auth):
        """Test creating a BiometricTemplate instance."""
        template = BiometricTemplate(
            template_id="template_123",
            user_id=test_user_auth.id,
            biometric_type="fingerprint",
            encrypted_template="encrypted_data_here",
            quality_score=0.95,
            device_info={"model": "iPhone 12", "sdk": "1.0"},
            device_model="iPhone 12",
            sdk_version="1.0",
        )

        db_session.add(template)
        db_session.commit()

        assert template.id is not None
        assert template.is_active is True
        assert template.quality_score == 0.95
        assert template.usage_count == 0

    @pytest.mark.hipaa_required
    def test_biometric_template_repr(self, db_session, test_user_auth):
        """Test BiometricTemplate string representation."""
        template = BiometricTemplate(
            template_id="test_template",
            user_id=test_user_auth.id,
            biometric_type="face",
            encrypted_template="encrypted",
            quality_score=0.9,
            is_active=False,
        )
        db_session.add(template)
        db_session.commit()

        expected = (
            f"<BiometricTemplate(user_id={test_user_auth.id}, type=face, active=False)>"
        )
        assert repr(template) == expected


class TestBiometricAuditLogModel:
    """Test BiometricAuditLog model to achieve comprehensive coverage."""

    @pytest.mark.hipaa_required
    def test_biometric_audit_log_creation(self, db_session, test_user_auth):
        """Test creating a BiometricAuditLog instance."""
        audit = BiometricAuditLog(
            user_id=test_user_auth.id,
            template_id="template_123",
            event_type="verified",
            biometric_type="fingerprint",
            success=True,
            match_score=0.98,
            quality_score=0.95,
            device_info={"device": "iPhone"},
            ip_address="192.168.1.1",
            user_agent="TestApp/1.0",
            session_id=uuid.uuid4(),
        )

        db_session.add(audit)
        db_session.commit()

        assert audit.id is not None
        assert audit.success is True
        assert audit.match_score == 0.98

    @pytest.mark.hipaa_required
    def test_biometric_audit_log_failure(self, db_session, test_user_auth):
        """Test biometric audit log for failed attempt."""
        audit = BiometricAuditLog(
            user_id=test_user_auth.id,
            event_type="failed",
            biometric_type="face",
            success=False,
            failure_reason="Poor quality image",
            quality_score=0.3,
        )

        db_session.add(audit)
        db_session.commit()

        assert audit.success is False
        assert audit.failure_reason == "Poor quality image"

    @pytest.mark.hipaa_required
    def test_biometric_audit_log_repr(self, db_session, test_user_auth):
        """Test BiometricAuditLog string representation."""
        audit = BiometricAuditLog(
            user_id=test_user_auth.id,
            event_type="enrolled",
            biometric_type="voice",
            success=True,
        )
        db_session.add(audit)
        db_session.commit()

        expected = f"<BiometricAuditLog(user_id={test_user_auth.id}, event=enrolled, success=True)>"
        assert repr(audit) == expected


class TestWebAuthnCredentialModel:
    """Test WebAuthnCredential model to achieve comprehensive coverage."""

    @pytest.mark.hipaa_required
    def test_webauthn_credential_creation(self, db_session, test_user_auth):
        """Test creating a WebAuthnCredential instance."""
        credential = WebAuthnCredential(
            user_id=test_user_auth.id,
            credential_id="cred_id_123",
            public_key="public_key_data",
            aaguid="aaguid_123",
            sign_count=0,
            authenticator_attachment="platform",
            transports=["internal"],
            device_name="MacBook Pro",
        )

        db_session.add(credential)
        db_session.commit()

        assert credential.id is not None
        assert credential.is_active is True
        assert credential.sign_count == 0
        assert credential.usage_count == 0

    @pytest.mark.hipaa_required
    def test_webauthn_credential_repr(self, db_session, test_user_auth):
        """Test WebAuthnCredential string representation."""
        credential = WebAuthnCredential(
            user_id=test_user_auth.id,
            credential_id="test_cred",
            public_key="test_key",
            device_name="Test Device",
            is_active=False,
        )
        db_session.add(credential)
        db_session.commit()

        expected = f"<WebAuthnCredential(user_id={test_user_auth.id}, device=Test Device, active=False)>"
        assert repr(credential) == expected


class TestAPIKeyModel:
    """Test APIKey model to achieve comprehensive coverage."""

    @pytest.mark.hipaa_required
    def test_api_key_creation(self, db_session, test_user_auth):
        """Test creating an APIKey instance."""
        api_key = APIKey(
            id=uuid.uuid4(),
            user_id=test_user_auth.id,
            name="Production API Key",
            description="Key for production app",
            key_prefix="hhp_live_",
            key_hash="hashed_key_value",
            last_four="abcd",
            scopes=["read:patients", "write:patients"],
            tier="premium",
            ip_whitelist=["192.168.1.0/24"],
            allowed_origins=["https://example.com"],
        )

        db_session.add(api_key)
        db_session.commit()

        assert api_key.id is not None
        assert api_key.is_active is True
        assert api_key.is_valid() is True
        assert api_key.has_scope("read:patients") is True
        assert api_key.has_scope("delete:all") is False

    @pytest.mark.hipaa_required
    def test_api_key_expiration(self, db_session, test_user_auth):
        """Test API key expiration logic."""
        # Test expired key
        expired_key = APIKey(
            id=uuid.uuid4(),
            user_id=test_user_auth.id,
            name="Expired Key",
            key_prefix="hhp_test_",
            key_hash="expired_hash",
            last_four="1234",
            expires_at=datetime.utcnow() - timedelta(days=1),
        )
        db_session.add(expired_key)
        db_session.commit()

        assert expired_key.is_valid() is False

        # Test revoked key
        revoked_key = APIKey(
            id=uuid.uuid4(),
            user_id=test_user_auth.id,
            name="Revoked Key",
            key_prefix="hhp_test_",
            key_hash="revoked_hash",
            last_four="5678",
            revoked_at=datetime.utcnow(),
            revocation_reason="Security breach",
        )
        db_session.add(revoked_key)
        db_session.commit()

        assert revoked_key.is_valid() is False

        # Test inactive key
        inactive_key = APIKey(
            id=uuid.uuid4(),
            user_id=test_user_auth.id,
            name="Inactive Key",
            key_prefix="hhp_test_",
            key_hash="inactive_hash",
            last_four="9012",
            is_active=False,
        )
        db_session.add(inactive_key)
        db_session.commit()

        assert inactive_key.is_valid() is False

    @pytest.mark.hipaa_required
    def test_api_key_repr(self, db_session, test_user_auth):
        """Test APIKey string representation."""
        api_key = APIKey(
            id=uuid.uuid4(),
            user_id=test_user_auth.id,
            name="Test Key",
            key_prefix="hhp_test_",
            key_hash="test_hash",
            last_four="test",
            tier="basic",
            is_active=True,
        )
        db_session.add(api_key)
        db_session.commit()

        expected = f"<APIKey(name=Test Key, user_id={test_user_auth.id}, tier=basic, active=True)>"
        assert repr(api_key) == expected

    @pytest.mark.hipaa_required
    def test_api_key_scope_check_with_none(self, db_session, test_user_auth):
        """Test has_scope with None scopes."""
        api_key = APIKey(
            id=uuid.uuid4(),
            user_id=test_user_auth.id,
            name="No Scope Key",
            key_prefix="hhp_test_",
            key_hash="no_scope_hash",
            last_four="none",
            scopes=None,
        )
        db_session.add(api_key)
        db_session.commit()

        assert api_key.has_scope("any:scope") is False


class TestPasswordResetTokenModel:
    """Test PasswordResetToken model to achieve comprehensive coverage."""

    @pytest.mark.hipaa_required
    def test_password_reset_token_creation(self, db_session, test_user_auth):
        """Test creating a PasswordResetToken instance."""
        token = PasswordResetToken(
            user_id=test_user_auth.id,
            token="reset_token_123",
            expires_at=datetime.utcnow() + timedelta(hours=1),
        )

        db_session.add(token)
        db_session.commit()

        assert token.id is not None
        assert token.is_valid() is True
        assert token.used_at is None

    @pytest.mark.hipaa_required
    def test_password_reset_token_used(self, db_session, test_user_auth):
        """Test used password reset token."""
        token = PasswordResetToken(
            user_id=test_user_auth.id,
            token="used_token",
            expires_at=datetime.utcnow() + timedelta(hours=1),
            used_at=datetime.utcnow(),
            ip_address="192.168.1.1",
            user_agent="TestBrowser",
        )

        db_session.add(token)
        db_session.commit()

        assert token.is_valid() is False

    @pytest.mark.hipaa_required
    def test_password_reset_token_expired(self, db_session, test_user_auth):
        """Test expired password reset token."""
        token = PasswordResetToken(
            user_id=test_user_auth.id,
            token="expired_token",
            expires_at=datetime.utcnow() - timedelta(hours=1),
        )

        db_session.add(token)
        db_session.commit()

        assert token.is_valid() is False

    @pytest.mark.hipaa_required
    def test_password_reset_token_repr(self, db_session, test_user_auth):
        """Test PasswordResetToken string representation."""
        token = PasswordResetToken(
            user_id=test_user_auth.id,
            token="test_token",
            expires_at=datetime.utcnow() + timedelta(hours=1),
        )
        db_session.add(token)
        db_session.commit()

        expected = f"<PasswordResetToken(user_id={test_user_auth.id}, expires_at={token.expires_at})>"
        assert repr(token) == expected


class TestSMSVerificationCodeModel:
    """Test SMSVerificationCode model to achieve comprehensive coverage."""

    @pytest.mark.hipaa_required
    def test_sms_verification_code_creation(self, db_session, test_user_auth):
        """Test creating an SMSVerificationCode instance."""
        code = SMSVerificationCode(
            phone_number="+1234567890",
            code="123456",
            purpose="registration",
            expires_at=datetime.utcnow() + timedelta(minutes=10),
            user_id=test_user_auth.id,
        )

        db_session.add(code)
        db_session.commit()

        assert code.id is not None
        assert code.is_valid() is True
        assert code.attempts == 0

    @pytest.mark.hipaa_required
    def test_sms_verification_code_invalid_states(self, db_session):
        """Test invalid SMS verification code states."""
        # Test verified code
        verified_code = SMSVerificationCode(
            phone_number="+1111111111",
            code="111111",
            purpose="login",
            expires_at=datetime.utcnow() + timedelta(minutes=10),
            verified_at=datetime.utcnow(),
        )
        db_session.add(verified_code)
        db_session.commit()
        assert verified_code.is_valid() is False

        # Test expired code
        expired_code = SMSVerificationCode(
            phone_number="+2222222222",
            code="222222",
            purpose="password_reset",
            expires_at=datetime.utcnow() - timedelta(minutes=1),
        )
        db_session.add(expired_code)
        db_session.commit()
        assert expired_code.is_valid() is False

        # Test max attempts
        max_attempts_code = SMSVerificationCode(
            phone_number="+3333333333",
            code="333333",
            purpose="phone_change",
            expires_at=datetime.utcnow() + timedelta(minutes=10),
            attempts=3,
        )
        db_session.add(max_attempts_code)
        db_session.commit()
        assert max_attempts_code.is_valid() is False

    @pytest.mark.hipaa_required
    def test_sms_verification_code_repr(self, db_session):
        """Test SMSVerificationCode string representation."""
        code = SMSVerificationCode(
            phone_number="+1234567890",
            code="123456",
            purpose="registration",
            expires_at=datetime.utcnow() + timedelta(minutes=10),
        )
        db_session.add(code)
        db_session.commit()

        expected = "<SMSVerificationCode(phone=+1234567890, purpose=registration)>"
        assert repr(code) == expected


class TestBackupCodeModel:
    """Test BackupCode model to achieve comprehensive coverage."""

    @pytest.mark.hipaa_required
    def test_backup_code_creation(self, db_session, test_user_auth):
        """Test creating a BackupCode instance."""
        code = BackupCode(user_id=test_user_auth.id, code_hash="hashed_backup_code")

        db_session.add(code)
        db_session.commit()

        assert code.id is not None
        assert code.is_valid() is True
        assert code.used_at is None

    @pytest.mark.hipaa_required
    def test_backup_code_used(self, db_session, test_user_auth):
        """Test used backup code."""
        code = BackupCode(
            user_id=test_user_auth.id,
            code_hash="used_code_hash",
            used_at=datetime.utcnow(),
            used_ip="192.168.1.1",
            used_user_agent="TestBrowser/1.0",
        )

        db_session.add(code)
        db_session.commit()

        assert code.is_valid() is False

    @pytest.mark.hipaa_required
    def test_backup_code_repr(self, db_session, test_user_auth):
        """Test BackupCode string representation."""
        # Test unused code
        unused_code = BackupCode(user_id=test_user_auth.id, code_hash="unused_hash")
        db_session.add(unused_code)
        db_session.commit()

        expected = f"<BackupCode(user_id={test_user_auth.id}, used=No)>"
        assert repr(unused_code) == expected

        # Test used code
        used_code = BackupCode(
            user_id=test_user_auth.id, code_hash="used_hash", used_at=datetime.utcnow()
        )
        db_session.add(used_code)
        db_session.commit()

        expected = f"<BackupCode(user_id={test_user_auth.id}, used=Yes)>"
        assert repr(used_code) == expected


# Additional edge case tests for comprehensive testing
class TestAuthModelsEdgeCases:
    """Test edge cases and special scenarios for comprehensive coverage."""

    @pytest.mark.hipaa_required
    def test_user_auth_with_all_fields(self, db_session, test_patient):
        """Test UserAuth with all optional fields populated."""
        user = UserAuth(
            patient_id=test_patient.id,
            email="complete@example.com",
            phone_number="+9999999999",
            password_hash="hash",
            password_reset_token="reset_token",
            password_reset_expires=datetime.utcnow() + timedelta(hours=1),
            password_reset_required=True,
            role=UserRole.ADMIN,
            custom_permissions=["custom:permission"],
            is_locked=True,
            locked_at=datetime.utcnow(),
            locked_reason="Security violation",
            email_verified=True,
            email_verified_at=datetime.utcnow(),
            email_verification_token="verify_token",
            email_verification_sent_at=datetime.utcnow(),
            phone_verified=True,
            phone_verified_at=datetime.utcnow(),
            phone_verification_code="123456",
            phone_verification_expires=datetime.utcnow() + timedelta(minutes=10),
            last_login_at=datetime.utcnow(),
            last_login_ip="192.168.1.1",
            failed_login_attempts=2,
            last_failed_login_at=datetime.utcnow(),
            created_by=uuid.uuid4(),
            notes="Test user with all fields",
        )

        db_session.add(user)
        db_session.commit()

        assert user.password_reset_required is True
        assert user.is_locked is True
        assert user.email_verified is True
        assert user.phone_verified is True
        assert user.failed_login_attempts == 2

    @pytest.mark.hipaa_required
    def test_session_with_absolute_expiration(self, db_session, test_user_auth):
        """Test session with absolute expiration policy."""
        session = UserSession(
            user_id=test_user_auth.id,
            token="absolute_token",
            expires_at=datetime.utcnow() + timedelta(hours=1),
            absolute_expires_at=datetime.utcnow() + timedelta(hours=24),
            session_metadata={"client": "mobile", "version": "1.0"},
        )

        db_session.add(session)
        db_session.commit()

        assert session.absolute_expires_at is not None
        assert session.session_metadata["client"] == "mobile"

    @pytest.mark.hipaa_required
    def test_mfa_with_security_questions(self, db_session, test_user_auth):
        """Test MFA configuration with security questions."""
        mfa = MFAConfig(
            user_id=test_user_auth.id,
            email_enabled=True,
            email_verified=True,
            email_verified_at=datetime.utcnow(),
            recovery_email="recovery@example.com",
            recovery_phone="+1234567890",
            security_questions=[
                {"question": "First pet?", "answer_hash": "hash1"},
                {"question": "Birth city?", "answer_hash": "hash2"},
            ],
            last_used_at=datetime.utcnow(),
            last_used_method="email",
        )

        db_session.add(mfa)
        db_session.commit()

        assert len(mfa.security_questions) == 2
        assert mfa.last_used_method == "email"
        assert "email" in mfa.enabled_methods
