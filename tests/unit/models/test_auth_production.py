"""Production tests for auth models with comprehensive test coverage.

This module provides comprehensive testing of all authentication models
using real database connections and no mocks, as required for medical compliance.
Tests verify actual behavior and side effects in a real database environment.
"""

import uuid
from datetime import date, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

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
from src.models.base import Base
from src.models.patient import Gender, Patient

# Real database configuration for testing
# Using SQLite in-memory database like other tests in the project
TEST_DATABASE_URL = "sqlite:///:memory:"


@pytest.fixture(scope="function")
def real_db_engine():
    """Create a real database engine for testing."""
    engine = create_engine(TEST_DATABASE_URL, echo=False)
    # Create all tables
    Base.metadata.create_all(engine)
    yield engine
    # Clean up after test
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture(scope="function")
def real_db_session(real_db_engine):
    """Create a real database session for testing."""
    SessionLocal = sessionmaker(bind=real_db_engine)
    session = SessionLocal()
    yield session
    session.rollback()
    session.close()


@pytest.fixture
def test_patient(real_db_session):
    """Create a test patient in the database."""
    patient = Patient(
        id=uuid.uuid4(),
        given_name="Test",
        family_name="Patient",
        date_of_birth=date(1990, 1, 1),
        gender=Gender.UNKNOWN,  # Using enum value
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    real_db_session.add(patient)
    real_db_session.commit()
    real_db_session.refresh(patient)
    return patient


@pytest.fixture
def test_user_auth(real_db_session, test_patient):
    """Create a real UserAuth instance in the database."""
    user = UserAuth(
        id=uuid.uuid4(),
        patient_id=test_patient.id,
        email="test@example.com",
        phone_number="+1234567890",
        password_hash="hashed_password_123",
        password_changed_at=datetime.utcnow(),
        role=UserRole.PATIENT,
        is_active=True,
        created_by=uuid.uuid4(),
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    real_db_session.add(user)
    real_db_session.commit()
    real_db_session.refresh(user)
    return user


class TestUserAuth:
    """Test UserAuth model with real database operations."""

    @pytest.mark.hipaa_required
    def test_user_auth_creation_and_repr(self, real_db_session, test_patient):
        """Test creating a UserAuth instance and its string representation."""
        # Create user with all fields
        user = UserAuth(
            id=uuid.uuid4(),
            patient_id=test_patient.id,
            email="patient@healthcare.com",
            phone_number="+19876543210",
            password_hash="secure_hash_value",
            password_changed_at=datetime.utcnow(),
            password_reset_token="reset_token_123",
            password_reset_expires=datetime.utcnow() + timedelta(hours=1),
            password_reset_required=True,
            role=UserRole.HEALTHCARE_PROVIDER,
            custom_permissions=["special:permission", "extra:access"],
            is_active=True,
            is_locked=False,
            email_verified=True,
            email_verified_at=datetime.utcnow(),
            email_verification_token="verify_token_123",
            email_verification_sent_at=datetime.utcnow(),
            phone_verified=True,
            phone_verified_at=datetime.utcnow(),
            phone_verification_code="123456",
            phone_verification_expires=datetime.utcnow() + timedelta(minutes=10),
            last_login_at=datetime.utcnow(),
            last_login_ip="192.168.1.100",
            failed_login_attempts=2,
            last_failed_login_at=datetime.utcnow() - timedelta(minutes=30),
            created_by=uuid.uuid4(),
            notes="Test user for healthcare provider",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        # Save to real database
        real_db_session.add(user)
        real_db_session.commit()
        real_db_session.refresh(user)

        # Verify saved correctly
        assert user.id is not None
        assert user.email == "patient@healthcare.com"
        assert user.role == UserRole.HEALTHCARE_PROVIDER
        assert user.custom_permissions == ["special:permission", "extra:access"]

        # Test __repr__
        repr_str = repr(user)
        assert f"UserAuth(id={user.id}" in repr_str
        assert "email=patient@healthcare.com" in repr_str
        assert "role=healthcare_provider" in repr_str

    @pytest.mark.hipaa_required
    def test_user_auth_properties(self, real_db_session, test_patient):
        """Test UserAuth properties: is_admin, is_healthcare_provider."""
        # Test patient role
        patient = UserAuth(
            id=uuid.uuid4(),
            patient_id=test_patient.id,
            email="patient@test.com",
            phone_number="+1111111111",
            password_hash="hash1",
            role=UserRole.PATIENT,
            created_by=uuid.uuid4(),
        )
        real_db_session.add(patient)
        real_db_session.commit()

        assert not patient.is_admin
        assert not patient.is_healthcare_provider

        # Test healthcare provider
        provider = UserAuth(
            id=uuid.uuid4(),
            patient_id=uuid.uuid4(),
            email="provider@test.com",
            phone_number="+2222222222",
            password_hash="hash2",
            role=UserRole.HEALTHCARE_PROVIDER,
            created_by=uuid.uuid4(),
        )
        real_db_session.add(provider)
        real_db_session.commit()

        assert not provider.is_admin
        assert provider.is_healthcare_provider

        # Test admin role
        admin = UserAuth(
            id=uuid.uuid4(),
            patient_id=uuid.uuid4(),
            email="admin@test.com",
            phone_number="+3333333333",
            password_hash="hash3",
            role=UserRole.ADMIN,
            created_by=uuid.uuid4(),
        )
        real_db_session.add(admin)
        real_db_session.commit()

        assert admin.is_admin
        assert not admin.is_healthcare_provider

        # Test super admin role
        super_admin = UserAuth(
            id=uuid.uuid4(),
            patient_id=uuid.uuid4(),
            email="superadmin@test.com",
            phone_number="+4444444444",
            password_hash="hash4",
            role=UserRole.SUPER_ADMIN,
            created_by=uuid.uuid4(),
        )
        real_db_session.add(super_admin)
        real_db_session.commit()

        assert super_admin.is_admin
        assert not super_admin.is_healthcare_provider

    @pytest.mark.hipaa_required
    def test_user_auth_permissions(self, real_db_session):
        """Test has_permission and _get_role_permissions methods."""
        # Test PATIENT permissions
        patient = UserAuth(
            id=uuid.uuid4(),
            patient_id=uuid.uuid4(),
            email="patient_perm@test.com",
            phone_number="+5555555555",
            password_hash="hash5",
            role=UserRole.PATIENT,
            created_by=uuid.uuid4(),
        )
        real_db_session.add(patient)
        real_db_session.commit()

        # Test role-based permissions
        assert patient.has_permission("read:own_records")
        assert patient.has_permission("update:own_profile")
        assert patient.has_permission("grant:access")
        assert patient.has_permission("revoke:access")
        assert not patient.has_permission("create:health_records")
        assert not patient.has_permission("system:all")

        # Test custom permissions
        patient.custom_permissions = ["custom:special", "extra:feature"]
        real_db_session.commit()
        assert patient.has_permission("custom:special")
        assert patient.has_permission("extra:feature")
        assert patient.has_permission("read:own_records")  # Still has role permissions

        # Test HEALTHCARE_PROVIDER permissions
        provider = UserAuth(
            id=uuid.uuid4(),
            patient_id=uuid.uuid4(),
            email="provider_perm@test.com",
            phone_number="+6666666666",
            password_hash="hash6",
            role=UserRole.HEALTHCARE_PROVIDER,
            created_by=uuid.uuid4(),
        )
        real_db_session.add(provider)
        real_db_session.commit()

        assert provider.has_permission("read:patient_records")
        assert provider.has_permission("create:health_records")
        assert provider.has_permission("update:health_records")
        assert provider.has_permission("verify:records")
        assert not provider.has_permission("manage:users")
        assert not provider.has_permission("system:all")

        # Test NGO_WORKER permissions
        ngo_worker = UserAuth(
            id=uuid.uuid4(),
            patient_id=uuid.uuid4(),
            email="ngo@test.com",
            phone_number="+7777777777",
            password_hash="hash7",
            role=UserRole.NGO_WORKER,
            created_by=uuid.uuid4(),
        )
        real_db_session.add(ngo_worker)
        real_db_session.commit()

        assert ngo_worker.has_permission("read:patient_records")
        assert ngo_worker.has_permission("create:patients")
        assert ngo_worker.has_permission("update:patients")
        assert ngo_worker.has_permission("create:verifications")
        assert not ngo_worker.has_permission("delete:soft")
        assert not ngo_worker.has_permission("system:all")

        # Test ADMIN permissions
        admin = UserAuth(
            id=uuid.uuid4(),
            patient_id=uuid.uuid4(),
            email="admin_perm@test.com",
            phone_number="+8888888888",
            password_hash="hash8",
            role=UserRole.ADMIN,
            created_by=uuid.uuid4(),
        )
        real_db_session.add(admin)
        real_db_session.commit()

        assert admin.has_permission("read:all")
        assert admin.has_permission("create:all")
        assert admin.has_permission("update:all")
        assert admin.has_permission("delete:soft")
        assert admin.has_permission("manage:users")
        assert admin.has_permission("view:analytics")
        assert not admin.has_permission("system:all")
        assert not admin.has_permission("delete:all")

        # Test SUPER_ADMIN permissions
        super_admin = UserAuth(
            id=uuid.uuid4(),
            patient_id=uuid.uuid4(),
            email="super_perm@test.com",
            phone_number="+9999999999",
            password_hash="hash9",
            role=UserRole.SUPER_ADMIN,
            created_by=uuid.uuid4(),
        )
        real_db_session.add(super_admin)
        real_db_session.commit()

        assert super_admin.has_permission("read:all")
        assert super_admin.has_permission("create:all")
        assert super_admin.has_permission("update:all")
        assert super_admin.has_permission("delete:all")
        assert super_admin.has_permission("manage:all")
        assert super_admin.has_permission("system:all")

        # Test empty custom_permissions (None case)
        super_admin.custom_permissions = None
        real_db_session.commit()
        assert super_admin.has_permission("system:all")  # Still has role permissions
        assert not super_admin.has_permission("custom:nonexistent")

    @pytest.mark.hipaa_required
    def test_user_auth_constraints(self, real_db_session, test_patient):
        """Test database constraints on UserAuth model."""
        # Create first user
        user1 = UserAuth(
            id=uuid.uuid4(),
            patient_id=test_patient.id,
            email="unique@test.com",
            phone_number="+1010101010",
            password_hash="hash10",
            created_by=uuid.uuid4(),
        )
        real_db_session.add(user1)
        real_db_session.commit()

        # Test unique email constraint
        user2 = UserAuth(
            id=uuid.uuid4(),
            patient_id=uuid.uuid4(),
            email="unique@test.com",  # Duplicate email
            phone_number="+2020202020",
            password_hash="hash11",
            created_by=uuid.uuid4(),
        )
        real_db_session.add(user2)
        with pytest.raises(IntegrityError):
            real_db_session.commit()
        real_db_session.rollback()


class TestUserSession:
    """Test UserSession model with real database operations."""

    @pytest.mark.hipaa_required
    def test_user_session_creation_and_repr(self, real_db_session, test_user_auth):
        """Test creating a UserSession instance and its string representation."""
        # Create session with all fields
        session = UserSession(
            id=uuid.uuid4(),
            user_id=test_user_auth.id,
            token="session_token_123456",
            refresh_token="refresh_token_789012",
            session_type="web",
            timeout_policy="sliding",
            device_fingerprint="device_fp_123",
            ip_address="192.168.1.200",
            user_agent="Mozilla/5.0 Test Browser",
            created_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(hours=1),
            absolute_expires_at=datetime.utcnow() + timedelta(days=1),
            last_activity_at=datetime.utcnow(),
            is_active=True,
            session_metadata={"browser": "chrome", "version": "120"},
        )

        real_db_session.add(session)
        real_db_session.commit()
        real_db_session.refresh(session)

        # Verify saved correctly
        assert session.id is not None
        assert session.token == "session_token_123456"
        assert session.session_metadata == {"browser": "chrome", "version": "120"}

        # Test __repr__
        repr_str = repr(session)
        assert f"UserSession(id={session.id}" in repr_str
        assert f"user_id={test_user_auth.id}" in repr_str
        assert "active=True" in repr_str

    @pytest.mark.hipaa_required
    def test_user_session_properties(self, real_db_session, test_user_auth):
        """Test UserSession is_expired and is_valid properties."""
        # Test valid active session
        valid_session = UserSession(
            id=uuid.uuid4(),
            user_id=test_user_auth.id,
            token="valid_token_123",
            expires_at=datetime.utcnow() + timedelta(hours=1),
            is_active=True,
        )
        real_db_session.add(valid_session)
        real_db_session.commit()

        assert not valid_session.is_expired
        assert valid_session.is_valid

        # Test expired session
        expired_session = UserSession(
            id=uuid.uuid4(),
            user_id=test_user_auth.id,
            token="expired_token_456",
            expires_at=datetime.utcnow() - timedelta(hours=1),
            is_active=True,
        )
        real_db_session.add(expired_session)
        real_db_session.commit()

        assert expired_session.is_expired
        assert not expired_session.is_valid

        # Test inactive session
        inactive_session = UserSession(
            id=uuid.uuid4(),
            user_id=test_user_auth.id,
            token="inactive_token_789",
            expires_at=datetime.utcnow() + timedelta(hours=1),
            is_active=False,
            invalidated_at=datetime.utcnow(),
            invalidation_reason="User logged out",
        )
        real_db_session.add(inactive_session)
        real_db_session.commit()

        assert not inactive_session.is_expired
        assert not inactive_session.is_valid  # Not valid because inactive


class TestDeviceInfo:
    """Test DeviceInfo model with real database operations."""

    @pytest.mark.hipaa_required
    def test_device_info_creation_and_repr(self, real_db_session, test_user_auth):
        """Test creating a DeviceInfo instance and its string representation."""
        # Create device with all fields
        device = DeviceInfo(
            id=uuid.uuid4(),
            user_id=test_user_auth.id,
            device_fingerprint="fp_unique_123456",
            device_name="John's iPhone",
            device_type="mobile",
            platform="iOS",
            platform_version="17.0",
            browser="Safari",
            browser_version="17.0",
            ip_address="192.168.1.50",
            user_agent="Mozilla/5.0 iPhone",
            is_trusted=True,
            trusted_at=datetime.utcnow(),
            trust_expires_at=datetime.utcnow() + timedelta(days=30),
            first_seen_at=datetime.utcnow(),
            last_seen_at=datetime.utcnow(),
            login_count=5,
        )

        real_db_session.add(device)
        real_db_session.commit()
        real_db_session.refresh(device)

        # Verify saved correctly
        assert device.id is not None
        assert device.device_name == "John's iPhone"
        assert device.is_trusted is True
        assert device.login_count == 5

        # Test __repr__
        repr_str = repr(device)
        assert f"DeviceInfo(id={device.id}" in repr_str
        assert "device=John's iPhone" in repr_str
        assert "trusted=True" in repr_str


class TestMFAConfig:
    """Test MFAConfig model with real database operations."""

    @pytest.mark.hipaa_required
    def test_mfa_config_creation_and_repr(self, real_db_session, test_user_auth):
        """Test creating a MFAConfig instance and its string representation."""
        # Create MFA config with all fields
        mfa = MFAConfig(
            id=uuid.uuid4(),
            user_id=test_user_auth.id,
            totp_enabled=True,
            totp_secret="JBSWY3DPEHPK3PXP",
            totp_verified=True,
            totp_verified_at=datetime.utcnow(),
            sms_enabled=True,
            sms_phone_number="+1234567890",
            sms_verified=True,
            sms_verified_at=datetime.utcnow(),
            email_enabled=False,
            backup_codes=["hash1", "hash2", "hash3"],
            backup_codes_generated_at=datetime.utcnow(),
            backup_codes_used_count=1,
            recovery_email="recovery@test.com",
            recovery_phone="+9876543210",
            security_questions=[{"q": "Pet name?", "a": "hashed_answer"}],
            last_used_at=datetime.utcnow(),
            last_used_method="totp",
        )

        real_db_session.add(mfa)
        real_db_session.commit()
        real_db_session.refresh(mfa)

        # Verify saved correctly
        assert mfa.id is not None
        assert mfa.totp_enabled is True
        assert mfa.sms_enabled is True
        assert mfa.backup_codes == ["hash1", "hash2", "hash3"]
        assert mfa.security_questions == [{"q": "Pet name?", "a": "hashed_answer"}]

        # Test __repr__
        repr_str = repr(mfa)
        assert f"MFAConfig(user_id={test_user_auth.id}" in repr_str
        assert "totp=True" in repr_str
        assert "sms=True" in repr_str

    @pytest.mark.hipaa_required
    def test_mfa_config_properties(self, real_db_session, test_user_auth):
        """Test MFAConfig is_enabled property and enabled_methods."""
        # Test all disabled
        mfa_disabled = MFAConfig(
            id=uuid.uuid4(),
            user_id=test_user_auth.id,
            totp_enabled=False,
            sms_enabled=False,
            email_enabled=False,
        )
        real_db_session.add(mfa_disabled)
        real_db_session.commit()

        assert not mfa_disabled.is_enabled
        assert mfa_disabled.enabled_methods == []

        # Test only TOTP enabled
        mfa_totp = MFAConfig(
            id=uuid.uuid4(),
            user_id=uuid.uuid4(),  # Different user
            totp_enabled=True,
            sms_enabled=False,
            email_enabled=False,
        )
        real_db_session.add(mfa_totp)
        real_db_session.commit()

        assert mfa_totp.is_enabled
        assert mfa_totp.enabled_methods == ["totp"]

        # Test all enabled
        mfa_all = MFAConfig(
            id=uuid.uuid4(),
            user_id=uuid.uuid4(),  # Different user
            totp_enabled=True,
            sms_enabled=True,
            email_enabled=True,
        )
        real_db_session.add(mfa_all)
        real_db_session.commit()

        assert mfa_all.is_enabled
        assert sorted(mfa_all.enabled_methods) == ["email", "sms", "totp"]


class TestPasswordHistory:
    """Test PasswordHistory model with real database operations."""

    @pytest.mark.hipaa_required
    def test_password_history_creation_and_repr(self, real_db_session, test_user_auth):
        """Test creating a PasswordHistory instance and its string representation."""
        # Create password history entry
        history = PasswordHistory(
            id=uuid.uuid4(),
            user_id=test_user_auth.id,
            password_hash="old_password_hash_123",
            created_at=datetime.utcnow(),
        )

        real_db_session.add(history)
        real_db_session.commit()
        real_db_session.refresh(history)

        # Verify saved correctly
        assert history.id is not None
        assert history.password_hash == "old_password_hash_123"

        # Test __repr__
        repr_str = repr(history)
        assert f"PasswordHistory(user_id={test_user_auth.id}" in repr_str
        assert "created_at=" in repr_str


class TestLoginAttempt:
    """Test LoginAttempt model with real database operations."""

    @pytest.mark.hipaa_required
    def test_login_attempt_creation_and_repr(self, real_db_session, test_user_auth):
        """Test creating a LoginAttempt instance and its string representation."""
        # Create successful login attempt
        success_attempt = LoginAttempt(
            id=uuid.uuid4(),
            user_id=test_user_auth.id,
            username="test@example.com",
            success=True,
            ip_address="192.168.1.100",
            user_agent="Mozilla/5.0",
            device_fingerprint="fp_123",
            attempted_at=datetime.utcnow(),
            session_id=uuid.uuid4(),
            event_metadata={"location": "USA", "browser": "Chrome"},
        )

        real_db_session.add(success_attempt)
        real_db_session.commit()
        real_db_session.refresh(success_attempt)

        # Verify saved correctly
        assert success_attempt.id is not None
        assert success_attempt.success is True
        assert success_attempt.event_metadata == {
            "location": "USA",
            "browser": "Chrome",
        }

        # Test __repr__
        repr_str = repr(success_attempt)
        assert f"LoginAttempt(user_id={test_user_auth.id}" in repr_str
        assert "success=True" in repr_str
        assert "at=" in repr_str

        # Create failed login attempt
        failed_attempt = LoginAttempt(
            id=uuid.uuid4(),
            user_id=test_user_auth.id,
            username="test@example.com",
            success=False,
            failure_reason="Invalid password",
            ip_address="192.168.1.101",
            user_agent="Mozilla/5.0",
            attempted_at=datetime.utcnow(),
        )

        real_db_session.add(failed_attempt)
        real_db_session.commit()

        assert failed_attempt.success is False
        assert failed_attempt.failure_reason == "Invalid password"


class TestBiometricTemplate:
    """Test BiometricTemplate model with real database operations."""

    @pytest.mark.hipaa_required
    def test_biometric_template_creation_and_repr(
        self, real_db_session, test_user_auth
    ):
        """Test creating a BiometricTemplate instance and its string representation."""
        # Create biometric template
        template = BiometricTemplate(
            id=uuid.uuid4(),
            template_id="template_unique_123",
            user_id=test_user_auth.id,
            biometric_type="fingerprint",
            encrypted_template="encrypted_biometric_data_base64",
            quality_score=0.95,
            device_info={"manufacturer": "Apple", "model": "iPhone 15"},
            device_model="iPhone 15 Pro",
            sdk_version="2.1.0",
            is_active=True,
            last_used_at=datetime.utcnow(),
            usage_count=10,
            last_match_score=0.98,
            created_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(days=365),
        )

        real_db_session.add(template)
        real_db_session.commit()
        real_db_session.refresh(template)

        # Verify saved correctly
        assert template.id is not None
        assert template.biometric_type == "fingerprint"
        assert template.quality_score == 0.95
        assert template.device_info == {"manufacturer": "Apple", "model": "iPhone 15"}

        # Test __repr__
        repr_str = repr(template)
        assert f"BiometricTemplate(user_id={test_user_auth.id}" in repr_str
        assert "type=fingerprint" in repr_str
        assert "active=True" in repr_str

        # Test deactivated template
        deactivated = BiometricTemplate(
            id=uuid.uuid4(),
            template_id="template_deact_456",
            user_id=test_user_auth.id,
            biometric_type="face",
            encrypted_template="encrypted_face_data",
            quality_score=0.88,
            is_active=False,
            deactivated_at=datetime.utcnow(),
            deactivation_reason="User requested removal",
        )

        real_db_session.add(deactivated)
        real_db_session.commit()

        assert deactivated.is_active is False
        assert deactivated.deactivation_reason == "User requested removal"


class TestBiometricAuditLog:
    """Test BiometricAuditLog model with real database operations."""

    @pytest.mark.hipaa_required
    def test_biometric_audit_log_creation_and_repr(
        self, real_db_session, test_user_auth
    ):
        """Test creating a BiometricAuditLog instance and its string representation."""
        # Create successful biometric verification log
        success_log = BiometricAuditLog(
            id=uuid.uuid4(),
            user_id=test_user_auth.id,
            template_id="template_123",
            event_type="verified",
            biometric_type="fingerprint",
            success=True,
            match_score=0.97,
            quality_score=0.92,
            device_info={"sdk": "2.1.0", "os": "iOS 17"},
            ip_address="192.168.1.150",
            user_agent="HavenHealth iOS App",
            session_id=uuid.uuid4(),
            event_timestamp=datetime.utcnow(),
        )

        real_db_session.add(success_log)
        real_db_session.commit()
        real_db_session.refresh(success_log)

        # Verify saved correctly
        assert success_log.id is not None
        assert success_log.event_type == "verified"
        assert success_log.success is True
        assert success_log.match_score == 0.97

        # Test __repr__
        repr_str = repr(success_log)
        assert f"BiometricAuditLog(user_id={test_user_auth.id}" in repr_str
        assert "event=verified" in repr_str
        assert "success=True" in repr_str

        # Create failed biometric log
        failed_log = BiometricAuditLog(
            id=uuid.uuid4(),
            user_id=test_user_auth.id,
            template_id="template_123",
            event_type="failed",
            biometric_type="face",
            success=False,
            match_score=0.42,
            failure_reason="Low match score",
            event_timestamp=datetime.utcnow(),
        )

        real_db_session.add(failed_log)
        real_db_session.commit()

        assert failed_log.success is False
        assert failed_log.failure_reason == "Low match score"


class TestWebAuthnCredential:
    """Test WebAuthnCredential model with real database operations."""

    @pytest.mark.hipaa_required
    def test_webauthn_credential_creation_and_repr(
        self, real_db_session, test_user_auth
    ):
        """Test creating a WebAuthnCredential instance and its string representation."""
        # Create WebAuthn credential
        credential = WebAuthnCredential(
            id=uuid.uuid4(),
            user_id=test_user_auth.id,
            credential_id="credential_id_base64_encoded",
            public_key="public_key_base64_encoded",
            aaguid="00000000-0000-0000-0000-000000000000",
            sign_count=42,
            authenticator_attachment="platform",
            credential_type="public-key",
            transports=["internal", "hybrid"],
            device_name="MacBook Pro TouchID",
            last_used_device="MacBook Pro",
            last_used_ip="192.168.1.200",
            is_active=True,
            last_used_at=datetime.utcnow(),
            usage_count=50,
            created_at=datetime.utcnow(),
        )

        real_db_session.add(credential)
        real_db_session.commit()
        real_db_session.refresh(credential)

        # Verify saved correctly
        assert credential.id is not None
        assert credential.credential_type == "public-key"
        assert credential.transports == ["internal", "hybrid"]
        assert credential.sign_count == 42

        # Test __repr__
        repr_str = repr(credential)
        assert f"WebAuthnCredential(user_id={test_user_auth.id}" in repr_str
        assert "device=MacBook Pro TouchID" in repr_str
        assert "active=True" in repr_str

        # Test revoked credential
        revoked = WebAuthnCredential(
            id=uuid.uuid4(),
            user_id=test_user_auth.id,
            credential_id="revoked_credential_id",
            public_key="revoked_public_key",
            device_name="Old Device",
            is_active=False,
            revoked_at=datetime.utcnow(),
            revocation_reason="Device lost",
        )

        real_db_session.add(revoked)
        real_db_session.commit()

        assert revoked.is_active is False
        assert revoked.revocation_reason == "Device lost"


class TestAPIKey:
    """Test APIKey model with real database operations."""

    @pytest.mark.hipaa_required
    def test_api_key_creation_and_repr(self, real_db_session, test_user_auth):
        """Test creating an APIKey instance and its string representation."""
        # Create API key
        api_key = APIKey(
            id=uuid.uuid4(),
            user_id=test_user_auth.id,
            name="Production API Key",
            description="Key for production API access",
            key_prefix="hhp_live_",
            key_hash="hashed_api_key_value",
            last_four="abcd",
            scopes=["read:patients", "write:records", "admin:users"],
            tier="enterprise",
            ip_whitelist=["192.168.1.0/24", "10.0.0.0/8"],
            allowed_origins=["https://app.example.com"],
            is_active=True,
            expires_at=datetime.utcnow() + timedelta(days=365),
            last_used_at=datetime.utcnow(),
            last_used_ip="192.168.1.100",
            last_used_user_agent="Python/3.12 requests/2.31",
            usage_count=1000,
            rate_limit_override=5000,
            rate_limit_window=3600,
            created_at=datetime.utcnow(),
        )

        real_db_session.add(api_key)
        real_db_session.commit()
        real_db_session.refresh(api_key)

        # Verify saved correctly
        assert api_key.id is not None
        assert api_key.tier == "enterprise"
        assert api_key.scopes == ["read:patients", "write:records", "admin:users"]

        # Test __repr__
        repr_str = repr(api_key)
        assert "APIKey(name=Production API Key" in repr_str
        assert f"user_id={test_user_auth.id}" in repr_str
        assert "tier=enterprise" in repr_str
        assert "active=True" in repr_str

    @pytest.mark.hipaa_required
    def test_api_key_is_valid_method(self, real_db_session, test_user_auth):
        """Test APIKey is_valid method with various scenarios."""
        # Test valid active key
        valid_key = APIKey(
            id=uuid.uuid4(),
            user_id=test_user_auth.id,
            name="Valid Key",
            key_prefix="hhp_test_",
            key_hash="hash_valid",
            last_four="1234",
            is_active=True,
            expires_at=datetime.utcnow() + timedelta(days=30),
        )
        real_db_session.add(valid_key)
        real_db_session.commit()

        assert valid_key.is_valid() is True

        # Test inactive key
        inactive_key = APIKey(
            id=uuid.uuid4(),
            user_id=test_user_auth.id,
            name="Inactive Key",
            key_prefix="hhp_test_",
            key_hash="hash_inactive",
            last_four="5678",
            is_active=False,
        )
        real_db_session.add(inactive_key)
        real_db_session.commit()

        assert inactive_key.is_valid() is False

        # Test revoked key
        revoked_key = APIKey(
            id=uuid.uuid4(),
            user_id=test_user_auth.id,
            name="Revoked Key",
            key_prefix="hhp_test_",
            key_hash="hash_revoked",
            last_four="9012",
            is_active=True,
            revoked_at=datetime.utcnow(),
            revocation_reason="Security breach",
        )
        real_db_session.add(revoked_key)
        real_db_session.commit()

        assert revoked_key.is_valid() is False

        # Test expired key
        expired_key = APIKey(
            id=uuid.uuid4(),
            user_id=test_user_auth.id,
            name="Expired Key",
            key_prefix="hhp_test_",
            key_hash="hash_expired",
            last_four="3456",
            is_active=True,
            expires_at=datetime.utcnow() - timedelta(days=1),
        )
        real_db_session.add(expired_key)
        real_db_session.commit()

        assert expired_key.is_valid() is False

    @pytest.mark.hipaa_required
    def test_api_key_has_scope_method(self, real_db_session, test_user_auth):
        """Test APIKey has_scope method."""
        # Test key with scopes
        key_with_scopes = APIKey(
            id=uuid.uuid4(),
            user_id=test_user_auth.id,
            name="Scoped Key",
            key_prefix="hhp_test_",
            key_hash="hash_scoped",
            last_four="7890",
            scopes=["read:patients", "write:records", "admin:users"],
        )
        real_db_session.add(key_with_scopes)
        real_db_session.commit()

        assert key_with_scopes.has_scope("read:patients") is True
        assert key_with_scopes.has_scope("write:records") is True
        assert key_with_scopes.has_scope("admin:users") is True
        assert key_with_scopes.has_scope("delete:all") is False

        # Test key with None scopes
        key_no_scopes = APIKey(
            id=uuid.uuid4(),
            user_id=test_user_auth.id,
            name="No Scopes Key",
            key_prefix="hhp_test_",
            key_hash="hash_noscope",
            last_four="0000",
        )
        real_db_session.add(key_no_scopes)
        real_db_session.commit()

        assert key_no_scopes.has_scope("read:patients") is False


class TestPasswordResetToken:
    """Test PasswordResetToken model with real database operations."""

    @pytest.mark.hipaa_required
    def test_password_reset_token_creation_and_repr(
        self, real_db_session, test_user_auth
    ):
        """Test creating a PasswordResetToken instance and its string representation."""
        # Create password reset token
        token = PasswordResetToken(
            id=uuid.uuid4(),
            user_id=test_user_auth.id,
            token="reset_token_secure_random_string",
            expires_at=datetime.utcnow() + timedelta(hours=24),
            created_at=datetime.utcnow(),
        )

        real_db_session.add(token)
        real_db_session.commit()
        real_db_session.refresh(token)

        # Verify saved correctly
        assert token.id is not None
        assert token.token == "reset_token_secure_random_string"

        # Test __repr__
        repr_str = repr(token)
        assert f"PasswordResetToken(user_id={test_user_auth.id}" in repr_str
        assert "expires_at=" in repr_str

    @pytest.mark.hipaa_required
    def test_password_reset_token_is_valid_method(
        self, real_db_session, test_user_auth
    ):
        """Test PasswordResetToken is_valid method."""
        # Test valid unused token
        valid_token = PasswordResetToken(
            id=uuid.uuid4(),
            user_id=test_user_auth.id,
            token="valid_reset_token",
            expires_at=datetime.utcnow() + timedelta(hours=1),
            created_at=datetime.utcnow(),
        )
        real_db_session.add(valid_token)
        real_db_session.commit()

        assert valid_token.is_valid() is True

        # Test used token
        used_token = PasswordResetToken(
            id=uuid.uuid4(),
            user_id=test_user_auth.id,
            token="used_reset_token",
            expires_at=datetime.utcnow() + timedelta(hours=1),
            used_at=datetime.utcnow(),
            ip_address="192.168.1.100",
            user_agent="Mozilla/5.0",
            created_at=datetime.utcnow(),
        )
        real_db_session.add(used_token)
        real_db_session.commit()

        assert used_token.is_valid() is False

        # Test expired token
        expired_token = PasswordResetToken(
            id=uuid.uuid4(),
            user_id=test_user_auth.id,
            token="expired_reset_token",
            expires_at=datetime.utcnow() - timedelta(hours=1),
            created_at=datetime.utcnow() - timedelta(hours=2),
        )
        real_db_session.add(expired_token)
        real_db_session.commit()

        assert expired_token.is_valid() is False


class TestSMSVerificationCode:
    """Test SMSVerificationCode model with real database operations."""

    @pytest.mark.hipaa_required
    def test_sms_verification_code_creation_and_repr(
        self, real_db_session, test_user_auth
    ):
        """Test creating an SMSVerificationCode instance and its string representation."""
        # Create SMS verification code
        sms_code = SMSVerificationCode(
            id=uuid.uuid4(),
            phone_number="+1234567890",
            code="123456",
            purpose="registration",
            expires_at=datetime.utcnow() + timedelta(minutes=10),
            user_id=test_user_auth.id,
            created_at=datetime.utcnow(),
        )

        real_db_session.add(sms_code)
        real_db_session.commit()
        real_db_session.refresh(sms_code)

        # Verify saved correctly
        assert sms_code.id is not None
        assert sms_code.code == "123456"
        assert sms_code.purpose == "registration"

        # Test __repr__
        repr_str = repr(sms_code)
        assert "SMSVerificationCode(phone=+1234567890" in repr_str
        assert "purpose=registration" in repr_str

    @pytest.mark.hipaa_required
    def test_sms_verification_code_is_valid_method(self, real_db_session):
        """Test SMSVerificationCode is_valid method with various scenarios."""
        # Test valid code
        valid_code = SMSVerificationCode(
            id=uuid.uuid4(),
            phone_number="+1111111111",
            code="111111",
            purpose="login",
            expires_at=datetime.utcnow() + timedelta(minutes=5),
            attempts=0,
        )
        real_db_session.add(valid_code)
        real_db_session.commit()

        assert valid_code.is_valid() is True

        # Test verified code
        verified_code = SMSVerificationCode(
            id=uuid.uuid4(),
            phone_number="+2222222222",
            code="222222",
            purpose="password_reset",
            expires_at=datetime.utcnow() + timedelta(minutes=5),
            verified_at=datetime.utcnow(),
            ip_address="192.168.1.100",
        )
        real_db_session.add(verified_code)
        real_db_session.commit()

        assert verified_code.is_valid() is False

        # Test expired code
        expired_code = SMSVerificationCode(
            id=uuid.uuid4(),
            phone_number="+3333333333",
            code="333333",
            purpose="phone_change",
            expires_at=datetime.utcnow() - timedelta(minutes=1),
            attempts=0,
        )
        real_db_session.add(expired_code)
        real_db_session.commit()

        assert expired_code.is_valid() is False

        # Test code with too many attempts
        failed_code = SMSVerificationCode(
            id=uuid.uuid4(),
            phone_number="+4444444444",
            code="444444",
            purpose="registration",
            expires_at=datetime.utcnow() + timedelta(minutes=5),
            attempts=3,
        )
        real_db_session.add(failed_code)
        real_db_session.commit()

        assert failed_code.is_valid() is False


class TestBackupCode:
    """Test BackupCode model with real database operations."""

    @pytest.mark.hipaa_required
    def test_backup_code_creation_and_repr(self, real_db_session, test_user_auth):
        """Test creating a BackupCode instance and its string representation."""
        # Create backup code
        backup_code = BackupCode(
            id=uuid.uuid4(),
            user_id=test_user_auth.id,
            code_hash="hashed_backup_code_123456",
            created_at=datetime.utcnow(),
        )

        real_db_session.add(backup_code)
        real_db_session.commit()
        real_db_session.refresh(backup_code)

        # Verify saved correctly
        assert backup_code.id is not None
        assert backup_code.code_hash == "hashed_backup_code_123456"

        # Test __repr__
        repr_str = repr(backup_code)
        assert f"BackupCode(user_id={test_user_auth.id}" in repr_str
        assert "used=No" in repr_str

    @pytest.mark.hipaa_required
    def test_backup_code_is_valid_method(self, real_db_session, test_user_auth):
        """Test BackupCode is_valid method."""
        # Test valid unused code
        valid_code = BackupCode(
            id=uuid.uuid4(),
            user_id=test_user_auth.id,
            code_hash="unused_backup_hash",
            created_at=datetime.utcnow(),
        )
        real_db_session.add(valid_code)
        real_db_session.commit()

        assert valid_code.is_valid() is True

        # Test used code
        used_code = BackupCode(
            id=uuid.uuid4(),
            user_id=test_user_auth.id,
            code_hash="used_backup_hash",
            used_at=datetime.utcnow(),
            used_ip="192.168.1.100",
            used_user_agent="Mozilla/5.0",
            created_at=datetime.utcnow(),
        )
        real_db_session.add(used_code)
        real_db_session.commit()

        assert used_code.is_valid() is False

        # Test __repr__ for used code
        repr_str = repr(used_code)
        assert "used=Yes" in repr_str
