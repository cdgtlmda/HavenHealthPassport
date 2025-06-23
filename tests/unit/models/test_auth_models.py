"""Comprehensive tests for authentication models.

Comprehensive tests for authentication models.
as required for security-critical files handling PHI data.

Uses real database operations without mocks as per medical compliance requirements.
"""

import uuid
from datetime import date, datetime, timedelta

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
def sample_user(db_session):
    """Create a sample user for testing - same as test_user_auth but with different name."""
    # Create patient first
    patient = Patient(
        given_name="Sample",
        family_name="User",
        date_of_birth=date(1995, 5, 15),
        gender=Gender.FEMALE,
    )
    db_session.add(patient)
    db_session.commit()

    # Create user auth
    user_auth = UserAuth(
        patient_id=patient.id,
        email="sample.user@example.com",
        phone_number="+9876543210",
        password_hash="$2b$12$SampleHashForTestingPurposes",
        role=UserRole.PATIENT,
        created_by=str(uuid.uuid4()),
    )
    db_session.add(user_auth)
    db_session.commit()
    yield user_auth
    # Cleanup
    db_session.delete(user_auth)
    db_session.delete(patient)
    db_session.commit()


@pytest.fixture
def test_patient(db_session):
    """Create a test patient for user authentication."""
    patient = Patient(
        given_name="John",
        family_name="Doe",
        date_of_birth=date(1990, 1, 1),
        gender=Gender.MALE,
    )
    db_session.add(patient)
    db_session.commit()
    yield patient
    # Cleanup
    db_session.delete(patient)
    db_session.commit()


@pytest.fixture
def test_user_auth(db_session, test_patient):
    """Create a test user authentication record."""
    user_auth = UserAuth(
        patient_id=test_patient.id,
        email="john.doe@example.com",
        phone_number="+1234567890",
        password_hash="$2b$12$KIXxPfnK6JKG0JKG0JKG0JKG0JKG0JKG0JKG0JKG0JKG0JKG0JKG0",
        role=UserRole.PATIENT,
        created_by=str(uuid.uuid4()),
    )
    db_session.add(user_auth)
    db_session.commit()
    yield user_auth
    # Cleanup
    db_session.delete(user_auth)
    db_session.commit()


class TestUserAuth:
    """Test UserAuth model with comprehensive coverage."""

    @pytest.mark.hipaa_required
    def test_user_auth_creation(self, db_session, test_patient):
        """Test creating a new user authentication record."""
        user_auth = UserAuth(
            patient_id=test_patient.id,
            email="test@example.com",
            phone_number="+1234567890",
            password_hash="hashed_password",
            role=UserRole.PATIENT,
            created_by=str(uuid.uuid4()),
        )

        db_session.add(user_auth)
        db_session.commit()

        # Verify record in database
        saved_user = (
            db_session.query(UserAuth).filter_by(email="test@example.com").first()
        )
        assert saved_user is not None
        assert saved_user.email == "test@example.com"
        assert saved_user.role == UserRole.PATIENT
        assert saved_user.is_active is True
        assert saved_user.is_locked is False
        assert saved_user.failed_login_attempts == 0

    def test_user_auth_repr(self, test_user_auth):
        """Test string representation."""
        expected = f"<UserAuth(id={test_user_auth.id}, email=john.doe@example.com, role=patient)>"
        assert repr(test_user_auth) == expected

    def test_is_admin_property(self, db_session, test_patient):
        """Test is_admin property for different roles."""
        # Test regular patient
        patient_user = UserAuth(
            patient_id=test_patient.id,
            email="patient@example.com",
            phone_number="+1111111111",
            password_hash="hash",
            role=UserRole.PATIENT,
            created_by=str(uuid.uuid4()),
        )
        assert patient_user.is_admin is False

        # Test admin user
        admin_user = UserAuth(
            patient_id=test_patient.id,
            email="admin@example.com",
            phone_number="+2222222222",
            password_hash="hash",
            role=UserRole.ADMIN,
            created_by=str(uuid.uuid4()),
        )
        assert admin_user.is_admin is True

        # Test super admin
        super_admin = UserAuth(
            patient_id=test_patient.id,
            email="super@example.com",
            phone_number="+3333333333",
            password_hash="hash",
            role=UserRole.SUPER_ADMIN,
            created_by=str(uuid.uuid4()),
        )
        assert super_admin.is_admin is True

    def test_is_healthcare_provider_property(self, db_session, test_patient):
        """Test is_healthcare_provider property."""
        # Test healthcare provider
        provider = UserAuth(
            patient_id=test_patient.id,
            email="provider@example.com",
            phone_number="+4444444444",
            password_hash="hash",
            role=UserRole.HEALTHCARE_PROVIDER,
            created_by=str(uuid.uuid4()),
        )
        assert provider.is_healthcare_provider is True

        # Test non-provider
        patient = UserAuth(
            patient_id=test_patient.id,
            email="patient2@example.com",
            phone_number="+5555555555",
            password_hash="hash",
            role=UserRole.PATIENT,
            created_by=str(uuid.uuid4()),
        )
        assert patient.is_healthcare_provider is False

    def test_has_permission_role_based(self, db_session, test_patient):
        """Test has_permission method with role-based permissions."""
        # Test patient permissions
        patient = UserAuth(
            patient_id=test_patient.id,
            email="patient3@example.com",
            phone_number="+6666666666",
            password_hash="hash",
            role=UserRole.PATIENT,
            created_by=str(uuid.uuid4()),
        )
        assert patient.has_permission("read:own_records") is True
        assert patient.has_permission("update:own_profile") is True
        assert patient.has_permission("grant:access") is True
        assert patient.has_permission("revoke:access") is True
        assert patient.has_permission("create:health_records") is False

    def test_has_permission_all_roles(self, db_session, test_patient):
        """Test permissions for all user roles."""
        # Healthcare Provider
        provider = UserAuth(
            patient_id=test_patient.id,
            email="provider2@example.com",
            phone_number="+7777777777",
            password_hash="hash",
            role=UserRole.HEALTHCARE_PROVIDER,
            created_by=str(uuid.uuid4()),
        )
        assert provider.has_permission("read:patient_records") is True
        assert provider.has_permission("create:health_records") is True
        assert provider.has_permission("update:health_records") is True
        assert provider.has_permission("verify:records") is True
        assert provider.has_permission("system:all") is False

        # NGO Worker
        ngo_worker = UserAuth(
            patient_id=test_patient.id,
            email="ngo@example.com",
            phone_number="+8888888888",
            password_hash="hash",
            role=UserRole.NGO_WORKER,
            created_by=str(uuid.uuid4()),
        )
        assert ngo_worker.has_permission("read:patient_records") is True
        assert ngo_worker.has_permission("create:patients") is True
        assert ngo_worker.has_permission("update:patients") is True
        assert ngo_worker.has_permission("create:verifications") is True
        assert ngo_worker.has_permission("delete:all") is False
        # Admin
        admin = UserAuth(
            patient_id=test_patient.id,
            email="admin2@example.com",
            phone_number="+9999999999",
            password_hash="hash",
            role=UserRole.ADMIN,
            created_by=str(uuid.uuid4()),
        )
        assert admin.has_permission("read:all") is True
        assert admin.has_permission("create:all") is True
        assert admin.has_permission("update:all") is True
        assert admin.has_permission("delete:soft") is True
        assert admin.has_permission("manage:users") is True
        assert admin.has_permission("view:analytics") is True
        assert admin.has_permission("system:all") is False

        # Super Admin
        super_admin = UserAuth(
            patient_id=test_patient.id,
            email="super2@example.com",
            phone_number="+1010101010",
            password_hash="hash",
            role=UserRole.SUPER_ADMIN,
            created_by=str(uuid.uuid4()),
        )
        assert super_admin.has_permission("read:all") is True
        assert super_admin.has_permission("create:all") is True
        assert super_admin.has_permission("update:all") is True
        assert super_admin.has_permission("delete:all") is True
        assert super_admin.has_permission("manage:all") is True
        assert super_admin.has_permission("system:all") is True

    def test_has_permission_custom(self, db_session, test_patient):
        """Test custom permissions."""
        user = UserAuth(
            patient_id=test_patient.id,
            email="custom@example.com",
            phone_number="+1212121212",
            password_hash="hash",
            role=UserRole.PATIENT,
            custom_permissions=["special:access", "custom:feature"],
            created_by=str(uuid.uuid4()),
        )

        # Test custom permissions
        assert user.has_permission("special:access") is True
        assert user.has_permission("custom:feature") is True
        assert user.has_permission("nonexistent:permission") is False

        # Test combination of role and custom permissions
        assert user.has_permission("read:own_records") is True  # Role permission
        assert user.has_permission("special:access") is True  # Custom permission

    def test_user_auth_all_fields(self, db_session, test_patient):
        """Test UserAuth with all fields populated."""
        now = datetime.utcnow()
        user = UserAuth(
            patient_id=test_patient.id,
            email="complete@example.com",
            phone_number="+1313131313",
            password_hash="hash",
            password_changed_at=now,
            password_reset_token="reset_token_123",
            password_reset_expires=now + timedelta(hours=1),
            password_reset_required=True,
            role=UserRole.PATIENT,
            custom_permissions=["test:permission"],
            is_active=True,
            is_locked=True,
            locked_at=now,
            locked_reason="Security review",
            email_verified=True,
            email_verified_at=now,
            email_verification_token="verify_token_123",
            email_verification_sent_at=now,
            phone_verified=True,
            phone_verified_at=now,
            phone_verification_code="123456",
            phone_verification_expires=now + timedelta(minutes=10),
            last_login_at=now,
            last_login_ip="192.168.1.1",
            failed_login_attempts=2,
            last_failed_login_at=now,
            created_by=str(uuid.uuid4()),
            notes="Test user with all fields",
        )

        db_session.add(user)
        db_session.commit()

        # Verify all fields saved correctly
        saved = (
            db_session.query(UserAuth).filter_by(email="complete@example.com").first()
        )
        assert saved.password_reset_token == "reset_token_123"
        assert saved.password_reset_required is True
        assert saved.is_locked is True
        assert saved.locked_reason == "Security review"
        assert saved.email_verified is True
        assert saved.phone_verified is True
        assert saved.failed_login_attempts == 2
        assert saved.notes == "Test user with all fields"


class TestUserSession:
    """Test UserSession model with comprehensive testing."""

    def test_user_session_creation(self, db_session, test_user_auth):
        """Test creating a user session."""
        expires = datetime.utcnow() + timedelta(hours=1)
        session = UserSession(
            user_id=test_user_auth.id,
            token="session_token_123",
            refresh_token="refresh_token_123",
            session_type="web",
            timeout_policy="sliding",
            ip_address="192.168.1.100",
            user_agent="Mozilla/5.0",
            expires_at=expires,
            absolute_expires_at=expires + timedelta(hours=23),
            device_fingerprint="fingerprint_123",
            session_metadata={"browser": "Chrome", "version": "120"},
        )

        db_session.add(session)
        db_session.commit()

        # Verify in database
        saved = (
            db_session.query(UserSession).filter_by(token="session_token_123").first()
        )
        assert saved is not None
        assert saved.user_id == test_user_auth.id
        assert saved.session_type == "web"
        assert saved.is_active is True
        assert saved.session_metadata["browser"] == "Chrome"

    def test_user_session_repr(self, db_session, test_user_auth):
        """Test string representation of UserSession."""
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

    def test_user_session_is_expired(self, db_session, test_user_auth):
        """Test is_expired property."""
        # Test active session
        active_session = UserSession(
            user_id=test_user_auth.id,
            token="active_token",
            expires_at=datetime.utcnow() + timedelta(hours=1),
        )
        assert active_session.is_expired is False

        # Test expired session
        expired_session = UserSession(
            user_id=test_user_auth.id,
            token="expired_token",
            expires_at=datetime.utcnow() - timedelta(hours=1),
        )
        assert expired_session.is_expired is True

    def test_user_session_is_valid(self, db_session, test_user_auth):
        """Test is_valid property."""
        # Test valid session
        valid_session = UserSession(
            user_id=test_user_auth.id,
            token="valid_token",
            expires_at=datetime.utcnow() + timedelta(hours=1),
            is_active=True,
        )
        assert valid_session.is_valid is True

        # Test inactive session
        inactive_session = UserSession(
            user_id=test_user_auth.id,
            token="inactive_token",
            expires_at=datetime.utcnow() + timedelta(hours=1),
            is_active=False,
        )
        assert inactive_session.is_valid is False

        # Test expired but active session
        expired_active = UserSession(
            user_id=test_user_auth.id,
            token="expired_active",
            expires_at=datetime.utcnow() - timedelta(hours=1),
            is_active=True,
        )
        assert expired_active.is_valid is False


class TestDeviceInfo:
    """Test DeviceInfo model with comprehensive testing."""

    def test_device_info_creation(self, db_session, test_user_auth):
        """Test creating device info record."""
        device = DeviceInfo(
            user_id=test_user_auth.id,
            device_fingerprint="device_fp_123",
            device_name="iPhone 15 Pro",
            device_type="mobile",
            platform="iOS",
            platform_version="17.0",
            browser="Safari",
            browser_version="17.0",
            ip_address="192.168.1.50",
            user_agent="Mozilla/5.0 (iPhone)",
            is_trusted=True,
            trusted_at=datetime.utcnow(),
            trust_expires_at=datetime.utcnow() + timedelta(days=30),
            login_count=5,
        )

        db_session.add(device)
        db_session.commit()

        # Verify in database
        saved = (
            db_session.query(DeviceInfo)
            .filter_by(device_fingerprint="device_fp_123")
            .first()
        )
        assert saved is not None
        assert saved.device_name == "iPhone 15 Pro"
        assert saved.is_trusted is True
        assert saved.login_count == 5

    def test_device_info_repr(self, db_session, test_user_auth):
        """Test string representation of DeviceInfo."""
        device = DeviceInfo(
            user_id=test_user_auth.id,
            device_fingerprint="test_fp",
            device_name="Test Device",
            is_trusted=True,
        )
        db_session.add(device)
        db_session.commit()

        expected = f"<DeviceInfo(id={device.id}, device=Test Device, trusted=True)>"
        assert repr(device) == expected


class TestMFAConfig:
    """Test MFAConfig model with comprehensive testing."""

    def test_mfa_config_creation(self, db_session, test_user_auth):
        """Test creating MFA configuration."""
        mfa = MFAConfig(
            user_id=test_user_auth.id,
            totp_enabled=True,
            totp_secret="JBSWY3DPEHPK3PXP",
            totp_verified=True,
            totp_verified_at=datetime.utcnow(),
            sms_enabled=True,
            sms_phone_number="+1234567890",
            sms_verified=True,
            sms_verified_at=datetime.utcnow(),
            email_enabled=True,
            email_verified=True,
            email_verified_at=datetime.utcnow(),
            backup_codes=["hash1", "hash2", "hash3"],
            backup_codes_generated_at=datetime.utcnow(),
            backup_codes_used_count=1,
            recovery_email="recovery@example.com",
            recovery_phone="+0987654321",
            security_questions=[
                {"question": "First pet?", "answer_hash": "hash_pet"},
                {"question": "Birth city?", "answer_hash": "hash_city"},
            ],
            last_used_at=datetime.utcnow(),
            last_used_method="totp",
        )

        db_session.add(mfa)
        db_session.commit()

        # Verify in database
        saved = db_session.query(MFAConfig).filter_by(user_id=test_user_auth.id).first()
        assert saved is not None
        assert saved.totp_enabled is True
        assert saved.sms_enabled is True
        assert saved.email_enabled is True
        assert len(saved.backup_codes) == 3
        assert saved.backup_codes_used_count == 1
        assert saved.last_used_method == "totp"

    def test_mfa_config_repr(self, db_session, test_user_auth):
        """Test string representation of MFAConfig."""
        mfa = MFAConfig(user_id=test_user_auth.id, totp_enabled=True, sms_enabled=False)
        expected = f"<MFAConfig(user_id={test_user_auth.id}, totp=True, sms=False)>"
        assert repr(mfa) == expected

    def test_mfa_is_enabled_property(self, db_session, test_user_auth):
        """Test is_enabled property."""
        # Test with no methods enabled
        mfa_disabled = MFAConfig(
            user_id=test_user_auth.id,
            totp_enabled=False,
            sms_enabled=False,
            email_enabled=False,
        )
        assert mfa_disabled.is_enabled is False

        # Test with TOTP enabled
        mfa_totp = MFAConfig(user_id=test_user_auth.id, totp_enabled=True)
        assert mfa_totp.is_enabled is True

        # Test with SMS enabled
        mfa_sms = MFAConfig(user_id=test_user_auth.id, sms_enabled=True)
        assert mfa_sms.is_enabled is True

        # Test with email enabled
        mfa_email = MFAConfig(user_id=test_user_auth.id, email_enabled=True)
        assert mfa_email.is_enabled is True

    def test_mfa_enabled_methods_property(self, db_session, test_user_auth):
        """Test enabled_methods property."""
        # Test with no methods
        mfa_none = MFAConfig(user_id=test_user_auth.id)
        assert mfa_none.enabled_methods == []

        # Test with all methods
        mfa_all = MFAConfig(
            user_id=test_user_auth.id,
            totp_enabled=True,
            sms_enabled=True,
            email_enabled=True,
        )
        assert set(mfa_all.enabled_methods) == {"totp", "sms", "email"}

        # Test with some methods
        mfa_some = MFAConfig(
            user_id=test_user_auth.id,
            totp_enabled=True,
            sms_enabled=False,
            email_enabled=True,
        )
        assert set(mfa_some.enabled_methods) == {"totp", "email"}


class TestPasswordHistory:
    """Test PasswordHistory model with comprehensive testing."""

    def test_password_history_creation(self, db_session, test_user_auth):
        """Test creating password history record."""
        history = PasswordHistory(
            user_id=test_user_auth.id, password_hash="$2b$12$OldPasswordHashHere"
        )

        db_session.add(history)
        db_session.commit()

        # Verify in database
        saved = (
            db_session.query(PasswordHistory)
            .filter_by(user_id=test_user_auth.id)
            .first()
        )
        assert saved is not None
        assert saved.password_hash == "$2b$12$OldPasswordHashHere"
        assert saved.created_at is not None

    def test_password_history_repr(self, db_session, test_user_auth):
        """Test string representation of PasswordHistory."""
        history = PasswordHistory(user_id=test_user_auth.id, password_hash="hash")
        db_session.add(history)
        db_session.commit()

        expected = f"<PasswordHistory(user_id={test_user_auth.id}, created_at={history.created_at})>"
        assert repr(history) == expected


class TestLoginAttempt:
    """Test LoginAttempt model with comprehensive testing."""

    def test_login_attempt_creation(self, db_session, test_user_auth):
        """Test creating login attempt record."""
        attempt = LoginAttempt(
            user_id=test_user_auth.id,
            username="john.doe@example.com",
            success=True,
            failure_reason=None,
            ip_address="192.168.1.100",
            user_agent="Mozilla/5.0",
            device_fingerprint="device_123",
            session_id=str(uuid.uuid4()),
            event_metadata={"location": "USA", "login_method": "password"},
        )

        db_session.add(attempt)
        db_session.commit()

        # Verify in database
        saved = (
            db_session.query(LoginAttempt).filter_by(user_id=test_user_auth.id).first()
        )
        assert saved is not None
        assert saved.username == "john.doe@example.com"
        assert saved.success is True
        assert saved.event_metadata["login_method"] == "password"

    def test_login_attempt_repr(self, db_session, test_user_auth):
        """Test string representation of LoginAttempt."""
        attempt = LoginAttempt(user_id=test_user_auth.id, success=False)
        db_session.add(attempt)
        db_session.commit()

        expected = f"<LoginAttempt(user_id={test_user_auth.id}, success=False, at={attempt.attempted_at})>"
        assert repr(attempt) == expected


class TestBiometricTemplate:
    """Test BiometricTemplate model with comprehensive testing."""

    def test_biometric_template_creation(self, db_session, test_user_auth):
        """Test creating biometric template record."""
        template = BiometricTemplate(
            template_id="bio_template_123",
            user_id=test_user_auth.id,
            biometric_type="fingerprint",
            encrypted_template="encrypted_biometric_data_here",
            quality_score=0.95,
            device_info={"model": "iPhone 15", "os": "iOS 17"},
            device_model="iPhone 15 Pro",
            sdk_version="2.0.1",
            is_active=True,
            usage_count=10,
            last_match_score=0.98,
        )

        db_session.add(template)
        db_session.commit()

        # Verify in database
        saved = (
            db_session.query(BiometricTemplate)
            .filter_by(template_id="bio_template_123")
            .first()
        )
        assert saved is not None
        assert saved.biometric_type == "fingerprint"
        assert saved.quality_score == 0.95
        assert saved.is_active is True
        assert saved.usage_count == 10

    def test_biometric_template_repr(self, db_session, test_user_auth):
        """Test string representation of BiometricTemplate."""
        template = BiometricTemplate(
            template_id="test_template",
            user_id=test_user_auth.id,
            biometric_type="face",
            encrypted_template="encrypted_data",
            quality_score=0.9,
            is_active=False,
        )
        db_session.add(template)
        db_session.commit()

        expected = (
            f"<BiometricTemplate(user_id={test_user_auth.id}, type=face, active=False)>"
        )
        assert repr(template) == expected

    def test_biometric_template_all_fields(self, db_session, test_user_auth):
        """Test BiometricTemplate with all fields including optional ones."""
        now = datetime.utcnow()
        template = BiometricTemplate(
            template_id="complete_template",
            user_id=test_user_auth.id,
            biometric_type="voice",
            encrypted_template="encrypted_voice_data",
            quality_score=0.88,
            device_info={"manufacturer": "Apple", "model": "iPhone 14"},
            device_model="iPhone 14 Pro Max",
            sdk_version="1.9.5",
            is_active=False,
            deactivated_at=now,
            deactivation_reason="User requested removal",
            last_used_at=now,
            usage_count=25,
            last_match_score=0.92,
            expires_at=now + timedelta(days=365),
        )

        db_session.add(template)
        db_session.commit()

        # Verify all fields
        saved = (
            db_session.query(BiometricTemplate)
            .filter_by(template_id="complete_template")
            .first()
        )
        assert saved.deactivation_reason == "User requested removal"
        assert saved.expires_at is not None


class TestBiometricAuditLog:
    """Test BiometricAuditLog model with comprehensive testing."""

    def test_biometric_audit_log_creation(self, db_session, test_user_auth):
        """Test creating biometric audit log record."""
        audit = BiometricAuditLog(
            user_id=test_user_auth.id,
            template_id="template_123",
            event_type="enrolled",
            biometric_type="fingerprint",
            success=True,
            match_score=0.95,
            quality_score=0.90,
            device_info={"platform": "iOS"},
            ip_address="192.168.1.100",
            user_agent="Haven Health App/1.0",
            session_id=str(uuid.uuid4()),
        )

        db_session.add(audit)
        db_session.commit()

        # Verify in database
        saved = (
            db_session.query(BiometricAuditLog)
            .filter_by(user_id=test_user_auth.id)
            .first()
        )
        assert saved is not None
        assert saved.event_type == "enrolled"
        assert saved.success is True
        assert saved.match_score == 0.95

    def test_biometric_audit_log_repr(self, db_session, test_user_auth):
        """Test string representation of BiometricAuditLog."""
        audit = BiometricAuditLog(
            user_id=test_user_auth.id,
            event_type="verified",
            biometric_type="face",
            success=False,
        )

        expected = f"<BiometricAuditLog(user_id={test_user_auth.id}, event=verified, success=False)>"
        assert repr(audit) == expected

    def test_biometric_audit_failed_attempt(self, db_session, test_user_auth):
        """Test biometric audit log for failed attempt."""
        audit = BiometricAuditLog(
            user_id=test_user_auth.id,
            template_id="template_456",
            event_type="failed",
            biometric_type="fingerprint",
            success=False,
            failure_reason="Low quality scan - please try again",
            match_score=0.45,
            quality_score=0.30,
            device_info={"error": "sensor_dirty"},
            ip_address="10.0.0.50",
            user_agent="Mobile App",
            session_id=None,
        )

        db_session.add(audit)
        db_session.commit()

        # Verify failure details
        saved = (
            db_session.query(BiometricAuditLog)
            .filter_by(template_id="template_456")
            .first()
        )
        assert saved.success is False
        assert saved.failure_reason == "Low quality scan - please try again"
        assert saved.match_score == 0.45


class TestWebAuthnCredential:
    """Test WebAuthnCredential model with comprehensive testing."""

    def test_webauthn_credential_creation(self, db_session, test_user_auth):
        """Test creating WebAuthn credential record."""
        credential = WebAuthnCredential(
            user_id=test_user_auth.id,
            credential_id="credential_id_base64_encoded",
            public_key="public_key_base64_encoded",
            aaguid="00000000-0000-0000-0000-000000000000",
            sign_count=0,
            authenticator_attachment="platform",
            credential_type="public-key",
            transports=["internal"],
            device_name="MacBook Pro",
            last_used_device="MacBook Pro",
            last_used_ip="192.168.1.100",
            is_active=True,
            usage_count=0,
        )

        db_session.add(credential)
        db_session.commit()

        # Verify in database
        saved = (
            db_session.query(WebAuthnCredential)
            .filter_by(credential_id="credential_id_base64_encoded")
            .first()
        )
        assert saved is not None
        assert saved.authenticator_attachment == "platform"
        assert saved.is_active is True

    def test_webauthn_credential_repr(self, db_session, test_user_auth):
        """Test string representation of WebAuthnCredential."""
        credential = WebAuthnCredential(
            user_id=test_user_auth.id,
            credential_id="test_cred",
            public_key="test_key",
            device_name="iPhone",
            is_active=True,
        )

        expected = f"<WebAuthnCredential(user_id={test_user_auth.id}, device=iPhone, active=True)>"
        assert repr(credential) == expected

    def test_webauthn_credential_revoked(self, db_session, test_user_auth):
        """Test WebAuthn credential with revocation."""
        now = datetime.utcnow()
        credential = WebAuthnCredential(
            user_id=test_user_auth.id,
            credential_id="revoked_cred",
            public_key="revoked_key",
            aaguid="11111111-1111-1111-1111-111111111111",
            sign_count=50,
            authenticator_attachment="cross-platform",
            transports=["usb", "nfc"],
            device_name="YubiKey 5",
            is_active=False,
            revoked_at=now,
            revocation_reason="Lost device",
            last_used_at=now - timedelta(days=7),
            usage_count=50,
        )

        db_session.add(credential)
        db_session.commit()

        # Verify revocation details
        saved = (
            db_session.query(WebAuthnCredential)
            .filter_by(credential_id="revoked_cred")
            .first()
        )
        assert saved.is_active is False
        assert saved.revocation_reason == "Lost device"
        assert saved.usage_count == 50


class TestAPIKey:
    """Test APIKey model with comprehensive testing."""

    def test_api_key_creation(self, db_session, test_user_auth):
        """Test creating API key record."""
        api_key = APIKey(
            id=uuid.uuid4(),
            user_id=test_user_auth.id,
            name="Production API Key",
            description="Key for production integration",
            key_prefix="hhp_live_",
            key_hash="hashed_api_key_value",
            last_four="abcd",
            scopes=["read:patients", "write:records"],
            tier="premium",
            ip_whitelist=["192.168.1.0/24"],
            allowed_origins=["https://app.example.com"],
            is_active=True,
            usage_count=100,
            rate_limit_override=1000,
            rate_limit_window=3600,
        )

        db_session.add(api_key)
        db_session.commit()

        # Verify in database
        saved = db_session.query(APIKey).filter_by(name="Production API Key").first()
        assert saved is not None
        assert saved.tier == "premium"
        assert "read:patients" in saved.scopes
        assert saved.is_active is True

    def test_api_key_repr(self, db_session, test_user_auth):
        """Test string representation of APIKey."""
        api_key = APIKey(
            id=uuid.uuid4(),
            user_id=test_user_auth.id,
            name="Test Key",
            key_prefix="hhp_test_",
            key_hash="test_hash",
            last_four="1234",
            tier="basic",
            is_active=True,
        )

        expected = f"<APIKey(name=Test Key, user_id={test_user_auth.id}, tier=basic, active=True)>"
        assert repr(api_key) == expected

    def test_api_key_is_valid(self, db_session, test_user_auth):
        """Test is_valid method of APIKey."""
        # Test valid key
        valid_key = APIKey(
            id=uuid.uuid4(),
            user_id=test_user_auth.id,
            name="Valid Key",
            key_prefix="hhp_",
            key_hash="hash1",
            last_four="5678",
            is_active=True,
        )
        assert valid_key.is_valid() is True

        # Test inactive key
        inactive_key = APIKey(
            id=uuid.uuid4(),
            user_id=test_user_auth.id,
            name="Inactive Key",
            key_prefix="hhp_",
            key_hash="hash2",
            last_four="9012",
            is_active=False,
        )
        assert inactive_key.is_valid() is False

        # Test revoked key
        revoked_key = APIKey(
            id=uuid.uuid4(),
            user_id=test_user_auth.id,
            name="Revoked Key",
            key_prefix="hhp_",
            key_hash="hash3",
            last_four="3456",
            is_active=True,
            revoked_at=datetime.utcnow(),
        )
        assert revoked_key.is_valid() is False

        # Test expired key
        expired_key = APIKey(
            id=uuid.uuid4(),
            user_id=test_user_auth.id,
            name="Expired Key",
            key_prefix="hhp_",
            key_hash="hash4",
            last_four="7890",
            is_active=True,
            expires_at=datetime.utcnow() - timedelta(days=1),
        )
        assert expired_key.is_valid() is False

    def test_api_key_has_scope(self, db_session, test_user_auth):
        """Test has_scope method of APIKey."""
        api_key = APIKey(
            id=uuid.uuid4(),
            user_id=test_user_auth.id,
            name="Scoped Key",
            key_prefix="hhp_",
            key_hash="hash5",
            last_four="1111",
            scopes=["read:patients", "write:records", "admin:users"],
        )

        # Test existing scopes
        assert api_key.has_scope("read:patients") is True
        assert api_key.has_scope("write:records") is True
        assert api_key.has_scope("admin:users") is True

        # Test non-existing scope
        assert api_key.has_scope("delete:all") is False

        # Test with empty scopes
        empty_key = APIKey(
            id=uuid.uuid4(),
            user_id=test_user_auth.id,
            name="Empty Key",
            key_prefix="hhp_",
            key_hash="hash6",
            last_four="2222",
            scopes=[],
        )
        assert empty_key.has_scope("read:patients") is False


class TestMedicalCompliancePermissions:
    """SURGICAL TESTS for 100% auth model coverage - MEDICAL COMPLIANCE CRITICAL."""

    def test_admin_privilege_checking_lines_137_142(self, db_session, sample_patient):
        """Test admin privilege properties (missing lines 137, 142)."""
        # Test ADMIN role
        admin_user = UserAuth(
            patient_id=sample_patient.id,
            email="admin@havenhealthpassport.com",
            password_hash="hashed_password",
            role=UserRole.ADMIN,
            created_by=uuid.uuid4(),
        )
        db_session.add(admin_user)
        db_session.commit()

        # Missing line 137: return self.role in [UserRole.ADMIN, UserRole.SUPER_ADMIN]
        assert admin_user.is_admin is True

        # Test SUPER_ADMIN role
        super_admin_user = UserAuth(
            patient_id=sample_patient.id,
            email="superadmin@havenhealthpassport.com",
            password_hash="hashed_password",
            role=UserRole.SUPER_ADMIN,
            created_by=uuid.uuid4(),
        )
        db_session.add(super_admin_user)
        db_session.commit()

        assert super_admin_user.is_admin is True

        # Test SUPER_ADMIN role
        healthcare_user = UserAuth(
            patient_id=sample_patient.id,
            email="doctor@havenhealthpassport.com",
            password_hash="hashed_password",
            role=UserRole.HEALTHCARE_PROVIDER,
            created_by=uuid.uuid4(),
        )
        db_session.add(healthcare_user)
        db_session.commit()

        assert healthcare_user.is_healthcare_provider is True
        assert healthcare_user.is_admin is False

    def test_permission_checking_logic_lines_147_199(self, db_session, sample_patient):
        """Test permission checking methods (missing lines 147-199)."""
        # Test custom permissions path (line 157)
        user_with_custom_perms = UserAuth(
            patient_id=sample_patient.id,
            email="custom@havenhealthpassport.com",
            password_hash="hashed_password",
            role=UserRole.PATIENT,
            custom_permissions=["special:permission", "admin:override"],
            created_by=uuid.uuid4(),
        )
        db_session.add(user_with_custom_perms)
        db_session.commit()

        # Missing line 157: return permission in (self.custom_permissions or [])
        assert user_with_custom_perms.has_permission("special:permission") is True
        assert user_with_custom_perms.has_permission("admin:override") is True
        assert user_with_custom_perms.has_permission("nonexistent:permission") is False

        # Test all role permission mappings (lines 162-199)
        # PATIENT permissions (lines 164-168)
        patient_user = UserAuth(
            patient_id=sample_patient.id,
            email="patient@havenhealthpassport.com",
            password_hash="hashed_password",
            role=UserRole.PATIENT,
            created_by=uuid.uuid4(),
        )
        db_session.add(patient_user)
        db_session.commit()

        assert patient_user.has_permission("read:own_records") is True
        assert patient_user.has_permission("update:own_profile") is True
        assert patient_user.has_permission("grant:access") is True
        assert patient_user.has_permission("revoke:access") is True

        # HEALTHCARE_PROVIDER permissions (lines 169-174)
        provider_user = UserAuth(
            patient_id=sample_patient.id,
            email="provider@havenhealthpassport.com",
            password_hash="hashed_password",
            role=UserRole.HEALTHCARE_PROVIDER,
            created_by=uuid.uuid4(),
        )
        db_session.add(provider_user)
        db_session.commit()

        assert provider_user.has_permission("read:patient_records") is True
        assert provider_user.has_permission("create:health_records") is True
        assert provider_user.has_permission("update:health_records") is True
        assert provider_user.has_permission("verify:records") is True

        # NGO_WORKER permissions (lines 175-180)
        ngo_user = UserAuth(
            patient_id=sample_patient.id,
            email="ngo@havenhealthpassport.com",
            password_hash="hashed_password",
            role=UserRole.NGO_WORKER,
            created_by=uuid.uuid4(),
        )
        db_session.add(ngo_user)
        db_session.commit()

        assert ngo_user.has_permission("read:patient_records") is True
        assert ngo_user.has_permission("create:patients") is True
        assert ngo_user.has_permission("update:patients") is True
        assert ngo_user.has_permission("create:verifications") is True

        # ADMIN permissions (lines 181-188)
        admin_user = UserAuth(
            patient_id=sample_patient.id,
            email="admin2@havenhealthpassport.com",
            password_hash="hashed_password",
            role=UserRole.ADMIN,
            created_by=uuid.uuid4(),
        )
        db_session.add(admin_user)
        db_session.commit()

        assert admin_user.has_permission("read:all") is True
        assert admin_user.has_permission("create:all") is True
        assert admin_user.has_permission("update:all") is True
        assert admin_user.has_permission("delete:soft") is True
        assert admin_user.has_permission("manage:users") is True
        assert admin_user.has_permission("view:analytics") is True

        # SUPER_ADMIN permissions (lines 189-197)
        super_admin = UserAuth(
            patient_id=sample_patient.id,
            email="superadmin2@havenhealthpassport.com",
            password_hash="hashed_password",
            role=UserRole.SUPER_ADMIN,
            created_by=uuid.uuid4(),
        )
        db_session.add(super_admin)
        db_session.commit()

        assert super_admin.has_permission("read:all") is True
        assert super_admin.has_permission("create:all") is True
        assert super_admin.has_permission("update:all") is True
        assert super_admin.has_permission("delete:all") is True
        assert super_admin.has_permission("manage:all") is True
        assert super_admin.has_permission("system:all") is True

    def test_session_validation_methods_lines_247_257(self, db_session, sample_user):
        """Test session validation properties (missing lines 247, 252, 257)."""
        from datetime import datetime, timedelta

        # Test expired session (line 247)
        expired_session = UserSession(
            user_id=sample_user.id,
            token="expired_token",
            expires_at=datetime.utcnow() - timedelta(hours=1),  # Expired 1 hour ago
            created_at=datetime.utcnow() - timedelta(hours=2),
        )
        db_session.add(expired_session)
        db_session.commit()

        # Missing line 247: return datetime.utcnow() > self.expires_at
        assert expired_session.is_expired is True

        # Test valid active session (lines 252, 257)
        valid_session = UserSession(
            user_id=sample_user.id,
            token="valid_token",
            expires_at=datetime.utcnow() + timedelta(hours=1),  # Expires in 1 hour
            is_active=True,
            created_at=datetime.utcnow(),
        )
        db_session.add(valid_session)
        db_session.commit()

        # Missing line 252: return self.is_active and not self.is_expired
        assert valid_session.is_valid is True
        assert valid_session.is_expired is False

        # Test inactive session
        inactive_session = UserSession(
            user_id=sample_user.id,
            token="inactive_token",
            expires_at=datetime.utcnow() + timedelta(hours=1),
            is_active=False,  # Inactive
            created_at=datetime.utcnow(),
        )
        db_session.add(inactive_session)
        db_session.commit()

        assert inactive_session.is_valid is False

    def test_repr_methods_all_models(self, db_session, sample_user, sample_patient):
        """Test __repr__ methods for all auth models (missing lines 395, 433, 484, 528, 579)."""
        # Test PasswordHistory __repr__ (line 395)
        password_history = PasswordHistory(
            user_id=sample_user.id, password_hash="old_hashed_password"
        )
        db_session.add(password_history)
        db_session.commit()

        repr_str = repr(password_history)
        assert "PasswordHistory" in repr_str
        assert str(password_history.id) in repr_str

        # Test LoginAttempt __repr__ (line 433)
        login_attempt = LoginAttempt(
            user_id=sample_user.id,
            username="test@example.com",
            success=True,
            ip_address="192.168.1.1",
        )
        db_session.add(login_attempt)
        db_session.commit()

        repr_str = repr(login_attempt)
        assert "LoginAttempt" in repr_str
        assert str(login_attempt.id) in repr_str

        # Test BiometricTemplate __repr__ (line 484)
        biometric_template = BiometricTemplate(
            template_id="bio_template_123",
            user_id=sample_user.id,
            biometric_type="fingerprint",
            encrypted_template="encrypted_biometric_data",
            quality_score=0.95,
        )
        db_session.add(biometric_template)
        db_session.commit()

        repr_str = repr(biometric_template)
        assert "BiometricTemplate" in repr_str
        assert "bio_template_123" in repr_str

        # Test BiometricAuditLog __repr__ (line 528)
        audit_log = BiometricAuditLog(
            user_id=sample_user.id,
            template_id="bio_template_123",
            event_type="verified",
            biometric_type="fingerprint",
            success=True,
        )
        db_session.add(audit_log)
        db_session.commit()

        repr_str = repr(audit_log)
        assert "BiometricAuditLog" in repr_str
        assert str(audit_log.id) in repr_str

        # Test WebAuthnCredential __repr__ (line 579)
        webauthn_cred = WebAuthnCredential(
            user_id=sample_user.id,
            credential_id="webauthn_cred_123",
            public_key="public_key_data",
        )
        db_session.add(webauthn_cred)
        db_session.commit()

        repr_str = repr(webauthn_cred)
        assert "WebAuthnCredential" in repr_str
        assert str(webauthn_cred.id) in repr_str

    def test_api_key_validation_lines_648_662(self, db_session, sample_user):
        """Test API key validation methods (missing lines 648, 652-658, 662)."""
        from datetime import datetime, timedelta

        # Test valid API key (lines 650-660)
        valid_api_key = APIKey(
            user_id=sample_user.id,
            name="Test API Key",
            key_prefix="hhp_test_",
            key_hash="hashed_api_key_value",
            last_four="1234",
            scopes=["read:records", "write:records"],
            is_active=True,
            expires_at=datetime.utcnow() + timedelta(days=30),
        )
        db_session.add(valid_api_key)
        db_session.commit()

        # Missing line 650-658: API key validation logic
        assert valid_api_key.is_valid() is True

        # Test expired API key
        expired_api_key = APIKey(
            user_id=sample_user.id,
            name="Expired API Key",
            key_prefix="hhp_exp_",
            key_hash="expired_hashed_key",
            last_four="9999",
            scopes=["read:records"],
            is_active=True,
            expires_at=datetime.utcnow() - timedelta(days=1),  # Expired
        )
        db_session.add(expired_api_key)
        db_session.commit()

        assert expired_api_key.is_valid() is False

        # Test revoked API key
        revoked_api_key = APIKey(
            user_id=sample_user.id,
            name="Revoked API Key",
            key_prefix="hhp_rev_",
            key_hash="revoked_hashed_key",
            last_four="0000",
            scopes=["read:records"],
            is_active=False,  # Revoked
            expires_at=datetime.utcnow() + timedelta(days=30),
        )
        db_session.add(revoked_api_key)
        db_session.commit()

        assert revoked_api_key.is_valid() is False

        # Missing line 662: has_scope method
        assert valid_api_key.has_scope("read:records") is True
        assert valid_api_key.has_scope("write:records") is True
        assert valid_api_key.has_scope("admin:all") is False

    def test_password_reset_token_validation_lines_698_702(
        self, db_session, sample_user
    ):
        """Test password reset token validation (missing lines 698, 702)."""
        # Test valid password reset token (line 700)
        valid_reset_token = PasswordResetToken(
            user_id=sample_user.id,
            token="valid_reset_token_123",
            expires_at=datetime.utcnow() + timedelta(hours=1),
            used_at=None,  # Not used yet
        )
        db_session.add(valid_reset_token)
        db_session.commit()

        # Missing line 700-704: token validation logic
        assert valid_reset_token.is_valid() is True

        # Test expired reset token
        expired_reset_token = PasswordResetToken(
            user_id=sample_user.id,
            token="expired_reset_token_456",
            expires_at=datetime.utcnow() - timedelta(hours=1),  # Expired
            used_at=None,
        )
        db_session.add(expired_reset_token)
        db_session.commit()

        assert expired_reset_token.is_valid() is False

        # Test used reset token
        used_reset_token = PasswordResetToken(
            user_id=sample_user.id,
            token="used_reset_token_789",
            expires_at=datetime.utcnow() + timedelta(hours=1),
            used_at=datetime.utcnow() - timedelta(minutes=30),  # Already used
        )
        db_session.add(used_reset_token)
        db_session.commit()

        assert used_reset_token.is_valid() is False

    def test_sms_verification_validation_lines_744_750(self, db_session, sample_user):
        """Test SMS verification code validation (missing lines 744, 750)."""
        # Test valid SMS verification code (line 748)
        valid_sms_code = SMSVerificationCode(
            phone_number="+1234567890",
            code="123456",
            purpose="registration",
            expires_at=datetime.utcnow() + timedelta(minutes=15),
            attempts=0,
            verified_at=None,
            user_id=sample_user.id,
        )
        db_session.add(valid_sms_code)
        db_session.commit()

        # Missing line 748-756: SMS code validation logic
        assert valid_sms_code.is_valid() is True

        # Test expired SMS code
        expired_sms_code = SMSVerificationCode(
            phone_number="+1234567891",
            code="654321",
            purpose="login",
            expires_at=datetime.utcnow() - timedelta(minutes=5),  # Expired
            attempts=0,
            verified_at=None,
            user_id=sample_user.id,
        )
        db_session.add(expired_sms_code)
        db_session.commit()

        assert expired_sms_code.is_valid() is False

    def test_backup_code_validation_lines_785_789(self, db_session, sample_user):
        """Test backup code validation (missing lines 785, 789)."""
        # Test valid (unused) backup code (line 787)
        valid_backup_code = BackupCode(
            user_id=sample_user.id,
            code_hash="hashed_backup_code_123",
            used_at=None,  # Not used yet
        )
        db_session.add(valid_backup_code)
        db_session.commit()

        # Missing line 787-791: backup code validation logic
        assert valid_backup_code.is_valid() is True

        # Test used backup code
        used_backup_code = BackupCode(
            user_id=sample_user.id,
            code_hash="hashed_backup_code_456",
            used_at=datetime.utcnow() - timedelta(hours=1),  # Already used
        )
        db_session.add(used_backup_code)
        db_session.commit()

        assert used_backup_code.is_valid() is False

    def test_device_info_repr_line_304(self, db_session, sample_user):
        """Test DeviceInfo __repr__ method (missing line 304)."""
        device_info = DeviceInfo(
            user_id=sample_user.id,
            device_fingerprint="device_fingerprint_123",
            device_name="iPhone 15 Pro",
            device_type="mobile",
            platform="iOS",
            is_trusted=True,
        )
        db_session.add(device_info)
        db_session.commit()

        # Missing line 304: __repr__ method
        repr_str = repr(device_info)
        assert "DeviceInfo" in repr_str
        assert "iPhone 15 Pro" in repr_str
        assert "trusted=True" in repr_str

    def test_mfa_config_methods_lines_353_370(self, db_session, sample_user):
        """Test MFA configuration methods (missing lines 353, 358, 363-370)."""
        # Test MFA config __repr__ (line 353)
        mfa_config = MFAConfig(
            user_id=sample_user.id,
            totp_enabled=True,
            totp_verified=True,
            sms_enabled=False,
            email_enabled=True,
        )
        db_session.add(mfa_config)
        db_session.commit()

        repr_str = repr(mfa_config)
        assert "MFAConfig" in repr_str
        assert str(mfa_config.id) in repr_str

        # Missing line 358: is_enabled property
        assert mfa_config.is_enabled is True

        # Test disabled MFA config
        disabled_mfa = MFAConfig(
            user_id=sample_user.id,
            totp_enabled=False,
            sms_enabled=False,
            email_enabled=False,
        )
        db_session.add(disabled_mfa)
        db_session.commit()

        assert disabled_mfa.is_enabled is False

        # Missing lines 363-370: enabled_methods property
        enabled_methods = mfa_config.enabled_methods
        assert "totp" in enabled_methods
        assert "email" in enabled_methods
        assert "sms" not in enabled_methods

        # Test all methods enabled
        all_enabled_mfa = MFAConfig(
            user_id=sample_user.id,
            totp_enabled=True,
            sms_enabled=True,
            email_enabled=True,
        )
        db_session.add(all_enabled_mfa)
        db_session.commit()

        all_methods = all_enabled_mfa.enabled_methods
        assert "totp" in all_methods
        assert "sms" in all_methods
        assert "email" in all_methods
        assert len(all_methods) == 3
