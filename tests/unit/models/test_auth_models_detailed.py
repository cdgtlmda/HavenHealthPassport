"""Comprehensive test coverage for auth models.

This test file achieves comprehensive test coverage for src/models/auth.py
using real database operations and no mocks as required for medical compliance.
"""

import uuid
from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

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


@pytest.fixture(scope="function")
def real_database():
    """Create a real test database for auth models testing."""
    # Use SQLite in-memory database for testing
    engine = create_engine("sqlite:///:memory:", echo=False)

    # Create all tables
    Base.metadata.create_all(engine)

    # Create session
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()

    yield session

    # Cleanup
    session.close()
    engine.dispose()


@pytest.fixture
def test_patient(real_database: Session) -> Patient:
    """Create a test patient for user authentication."""
    patient = Patient(
        id=uuid.uuid4(),
        given_name="Test",
        family_name="Patient",
        date_of_birth=datetime(1990, 1, 1).date(),
        gender=Gender.UNKNOWN,
        blood_type="O+",
        created_by_organization="Test Hospital",
        managing_organization="Test Hospital",
        last_updated_by=uuid.uuid4(),
    )
    real_database.add(patient)
    real_database.commit()
    return patient


@pytest.fixture
def test_user_auth(real_database: Session, test_patient: Patient) -> UserAuth:
    """Create a test user auth record."""
    user = UserAuth(
        patient_id=test_patient.id,
        email="test@refugeehealth.org",
        phone_number="+1234567890",
        password_hash="$2b$12$dummy_hash_for_testing",
        password_changed_at=datetime.utcnow(),
        role=UserRole.PATIENT,
        custom_permissions=["custom:permission"],
        created_by=uuid.uuid4(),
        notes="Test user for auth model coverage",
    )
    real_database.add(user)
    real_database.commit()
    return user


class TestUserAuthModel:
    """Test UserAuth model with comprehensive test coverage."""

    def test_user_auth_creation(
        self, real_database: Session, test_patient: Patient
    ) -> None:
        """Test creating a UserAuth record with all fields."""
        # Create user with all fields populated
        user = UserAuth(
            patient_id=test_patient.id,
            email="refugee.patient@example.org",
            phone_number="+9876543210",
            password_hash="$2b$12$secure_password_hash",
            password_changed_at=datetime.utcnow(),
            password_reset_token="reset_token_123",
            password_reset_expires=datetime.utcnow() + timedelta(hours=1),
            password_reset_required=True,
            role=UserRole.HEALTHCARE_PROVIDER,
            custom_permissions=["read:special_records", "write:reports"],
            is_active=True,
            is_locked=True,
            locked_at=datetime.utcnow(),
            locked_reason="Suspicious activity detected",
            email_verified=True,
            email_verified_at=datetime.utcnow(),
            email_verification_token="email_verify_token",
            email_verification_sent_at=datetime.utcnow(),
            phone_verified=True,
            phone_verified_at=datetime.utcnow(),
            phone_verification_code="123456",
            phone_verification_expires=datetime.utcnow() + timedelta(minutes=10),
            last_login_at=datetime.utcnow(),
            last_login_ip="192.168.1.100",
            failed_login_attempts=2,
            last_failed_login_at=datetime.utcnow() - timedelta(minutes=5),
            created_by=uuid.uuid4(),
            notes="Healthcare provider with special access",
        )

        real_database.add(user)
        real_database.commit()

        # Verify all fields
        assert user.id is not None
        assert user.email == "refugee.patient@example.org"
        assert user.phone_number == "+9876543210"
        assert user.password_reset_required is True
        assert user.role == UserRole.HEALTHCARE_PROVIDER
        assert "read:special_records" in user.custom_permissions
        assert user.is_locked is True
        assert user.locked_reason == "Suspicious activity detected"
        assert user.email_verified is True
        assert user.phone_verified is True
        assert user.failed_login_attempts == 2

    def test_user_auth_repr(self, test_user_auth: UserAuth) -> None:
        """Test string representation of UserAuth."""
        repr_str = repr(test_user_auth)
        assert f"UserAuth(id={test_user_auth.id}" in repr_str
        assert "email=test@refugeehealth.org" in repr_str
        assert "role=patient" in repr_str

    def test_is_admin_property(
        self, real_database: Session, test_patient: Patient
    ) -> None:
        """Test is_admin property for different roles."""
        # Test non-admin roles
        patient_user = UserAuth(
            patient_id=test_patient.id,
            email="patient@example.org",
            password_hash="hash",
            role=UserRole.PATIENT,
            created_by=uuid.uuid4(),
        )
        real_database.add(patient_user)
        real_database.commit()
        assert patient_user.is_admin is False

        # Test admin role
        patient_user.role = UserRole.ADMIN
        real_database.commit()
        assert patient_user.is_admin is True

    def test_is_healthcare_provider_property(
        self, test_user_auth: UserAuth, real_database: Session
    ) -> None:
        """Test is_healthcare_provider property."""
        # Test patient role
        assert test_user_auth.is_healthcare_provider is False

        # Change to healthcare provider
        test_user_auth.role = UserRole.HEALTHCARE_PROVIDER
        real_database.commit()
        assert test_user_auth.is_healthcare_provider is True

    def test_has_permission_method(
        self, test_user_auth: UserAuth, real_database: Session
    ) -> None:
        """Test has_permission method with role and custom permissions."""
        # Test role-based permission
        assert test_user_auth.has_permission("read:own_records") is True
        assert test_user_auth.has_permission("system:all") is False

        # Test custom permission
        assert test_user_auth.has_permission("custom:permission") is True
        assert test_user_auth.has_permission("nonexistent:permission") is False

        # Test with empty custom permissions
        test_user_auth.custom_permissions = []  # type: ignore[assignment]
        real_database.commit()
        assert test_user_auth.has_permission("custom:permission") is False

    def test_get_role_permissions(
        self, real_database: Session, test_patient: Patient
    ) -> None:
        """Test _get_role_permissions for all roles."""
        user = UserAuth(
            patient_id=test_patient.id,
            email="role.test@example.org",
            password_hash="hash",
            created_by=uuid.uuid4(),
        )

        # Test each role
        roles_to_test = [
            UserRole.PATIENT,
            UserRole.HEALTHCARE_PROVIDER,
            UserRole.NGO_WORKER,
            UserRole.ADMIN,
            UserRole.SUPER_ADMIN,
        ]

        for role in roles_to_test:
            user.role = role
            permissions = user._get_role_permissions()
            assert isinstance(permissions, list)
            assert len(permissions) > 0

        real_database.add(user)
        real_database.commit()


class TestUserSessionModel:
    """Test UserSession model with comprehensive testing."""

    def test_user_session_creation(
        self, real_database: Session, test_user_auth: UserAuth
    ) -> None:
        """Test creating a UserSession with all fields."""
        session = UserSession(
            user_id=test_user_auth.id,
            token="session_token_123",
            refresh_token="refresh_token_456",
            session_type="mobile",
            timeout_policy="absolute",
            device_fingerprint="device_fingerprint_789",
            ip_address="10.0.0.1",
            user_agent="HavenHealth/1.0 (iOS 16.0)",
            created_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(hours=2),
            absolute_expires_at=datetime.utcnow() + timedelta(days=1),
            last_activity_at=datetime.utcnow(),
            is_active=True,
            session_metadata={"app_version": "1.0.0", "location": "refugee_camp_01"},
        )

        real_database.add(session)
        real_database.commit()

        assert session.id is not None
        assert session.token == "session_token_123"
        assert session.session_type == "mobile"
        assert session.timeout_policy == "absolute"
        assert session.session_metadata["location"] == "refugee_camp_01"

    def test_user_session_repr(
        self, real_database: Session, test_user_auth: UserAuth
    ) -> None:
        """Test string representation of UserSession."""
        session = UserSession(
            user_id=test_user_auth.id,
            token="test_token",
            expires_at=datetime.utcnow() + timedelta(hours=1),
        )
        real_database.add(session)
        real_database.commit()

        repr_str = repr(session)
        assert f"UserSession(id={session.id}" in repr_str
        assert f"user_id={test_user_auth.id}" in repr_str
        assert "active=True" in repr_str

    def test_is_expired_property(
        self, real_database: Session, test_user_auth: UserAuth
    ) -> None:
        """Test is_expired property."""
        # Create non-expired session
        session = UserSession(
            user_id=test_user_auth.id,
            token="active_token",
            expires_at=datetime.utcnow() + timedelta(hours=1),
        )
        real_database.add(session)
        real_database.commit()
        assert session.is_expired is False

        # Create expired session
        expired_session = UserSession(
            user_id=test_user_auth.id,
            token="expired_token",
            expires_at=datetime.utcnow() - timedelta(hours=1),
        )
        real_database.add(expired_session)
        real_database.commit()
        assert expired_session.is_expired is True

    def test_is_valid_property(
        self, real_database: Session, test_user_auth: UserAuth
    ) -> None:
        """Test is_valid property with various conditions."""
        # Valid session
        valid_session = UserSession(
            user_id=test_user_auth.id,
            token="valid_token",
            expires_at=datetime.utcnow() + timedelta(hours=1),
            is_active=True,
        )
        real_database.add(valid_session)
        real_database.commit()
        assert valid_session.is_valid is True

        # Inactive session
        valid_session.is_active = False
        real_database.commit()
        is_valid_result: bool = valid_session.is_valid
        assert is_valid_result is False

        # Expired but active session
        expired_active = UserSession(
            user_id=test_user_auth.id,
            token="expired_active",
            expires_at=datetime.utcnow() - timedelta(hours=1),
            is_active=True,
        )
        real_database.add(expired_active)
        real_database.commit()
        assert expired_active.is_valid is False

    def test_session_invalidation(
        self, real_database: Session, test_user_auth: UserAuth
    ) -> None:
        """Test session invalidation fields."""
        session = UserSession(
            user_id=test_user_auth.id,
            token="invalidated_token",
            expires_at=datetime.utcnow() + timedelta(hours=1),
            is_active=False,
            invalidated_at=datetime.utcnow(),
            invalidation_reason="User logged out",
        )
        real_database.add(session)
        real_database.commit()

        assert session.is_active is False
        assert session.invalidated_at is not None
        assert session.invalidation_reason == "User logged out"


class TestDeviceInfoModel:
    """Test DeviceInfo model with comprehensive testing."""

    def test_device_info_creation(
        self, real_database: Session, test_user_auth: UserAuth
    ) -> None:
        """Test creating DeviceInfo with all fields."""
        device = DeviceInfo(
            user_id=test_user_auth.id,
            device_fingerprint="unique_device_id_123",
            device_name="Refugee's Phone",
            device_type="mobile",
            platform="Android",
            platform_version="13",
            browser="Chrome",
            browser_version="119.0",
            ip_address="192.168.1.50",
            user_agent="Mozilla/5.0 (Android 13)",
            is_trusted=True,
            trusted_at=datetime.utcnow(),
            trust_expires_at=datetime.utcnow() + timedelta(days=90),
            first_seen_at=datetime.utcnow() - timedelta(days=30),
            last_seen_at=datetime.utcnow(),
            login_count=15,
        )

        real_database.add(device)
        real_database.commit()

        assert device.id is not None
        assert device.device_name == "Refugee's Phone"
        assert device.platform == "Android"
        assert device.is_trusted is True
        assert device.login_count == 15

    def test_device_info_repr(
        self, real_database: Session, test_user_auth: UserAuth
    ) -> None:
        """Test string representation of DeviceInfo."""
        device = DeviceInfo(
            user_id=test_user_auth.id,
            device_fingerprint="test_device",
            device_name="Test Device",
            is_trusted=False,
        )
        real_database.add(device)
        real_database.commit()

        repr_str = repr(device)
        assert f"DeviceInfo(id={device.id}" in repr_str
        assert "device=Test Device" in repr_str
        assert "trusted=False" in repr_str

    def test_device_unique_constraint(
        self, real_database: Session, test_user_auth: UserAuth
    ) -> None:
        """Test unique constraint on user_id and device_fingerprint."""
        # Create first device
        device1 = DeviceInfo(
            user_id=test_user_auth.id, device_fingerprint="same_fingerprint"
        )
        real_database.add(device1)
        real_database.commit()

        # Try to create duplicate
        device2 = DeviceInfo(
            user_id=test_user_auth.id, device_fingerprint="same_fingerprint"
        )
        real_database.add(device2)

        with pytest.raises(IntegrityError):
            real_database.commit()


class TestMFAConfigModel:
    """Test MFAConfig model with comprehensive testing."""

    def test_mfa_config_creation(
        self, real_database: Session, test_user_auth: UserAuth
    ) -> None:
        """Test creating MFAConfig with all fields."""
        mfa_config = MFAConfig(
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
            backup_codes=["hash1", "hash2", "hash3", "hash4", "hash5"],
            backup_codes_generated_at=datetime.utcnow(),
            backup_codes_used_count=1,
            recovery_email="recovery@example.org",
            recovery_phone="+9876543210",
            security_questions=[
                {"question": "Mother's maiden name?", "answer_hash": "hashed_answer1"},
                {"question": "First school?", "answer_hash": "hashed_answer2"},
            ],
            last_used_at=datetime.utcnow(),
            last_used_method="totp",
        )

        real_database.add(mfa_config)
        real_database.commit()

        assert mfa_config.id is not None
        assert mfa_config.totp_enabled is True
        assert len(mfa_config.backup_codes) == 5
        assert mfa_config.backup_codes_used_count == 1
        assert len(mfa_config.security_questions) == 2

    def test_mfa_config_repr(
        self, real_database: Session, test_user_auth: UserAuth
    ) -> None:
        """Test string representation of MFAConfig."""
        mfa_config = MFAConfig(
            user_id=test_user_auth.id, totp_enabled=True, sms_enabled=False
        )
        real_database.add(mfa_config)
        real_database.commit()

        repr_str = repr(mfa_config)
        assert f"MFAConfig(user_id={test_user_auth.id}" in repr_str
        assert "totp=True" in repr_str
        assert "sms=False" in repr_str

    def test_is_enabled_property(
        self, real_database: Session, test_user_auth: UserAuth
    ) -> None:
        """Test is_enabled property."""
        mfa_config = MFAConfig(user_id=test_user_auth.id)
        real_database.add(mfa_config)
        real_database.commit()

        # All disabled
        assert mfa_config.is_enabled is False

        # Enable TOTP
        mfa_config.totp_enabled = True
        real_database.commit()
        is_enabled_result: bool = mfa_config.is_enabled
        assert is_enabled_result is True

        # Disable TOTP, enable SMS
        mfa_config.totp_enabled = False
        mfa_config.sms_enabled = True
        real_database.commit()
        is_enabled_after_sms: bool = mfa_config.is_enabled
        assert is_enabled_after_sms is True

        # Enable email
        mfa_config.email_enabled = True
        real_database.commit()
        is_enabled_after_email: bool = mfa_config.is_enabled
        assert is_enabled_after_email is True

    def test_enabled_methods_property(
        self, real_database: Session, test_user_auth: UserAuth
    ) -> None:
        """Test enabled_methods property."""
        mfa_config = MFAConfig(user_id=test_user_auth.id)
        real_database.add(mfa_config)
        real_database.commit()

        # No methods enabled
        assert mfa_config.enabled_methods == []

        # Enable all methods
        mfa_config.totp_enabled = True
        mfa_config.sms_enabled = True
        mfa_config.email_enabled = True
        real_database.commit()

        methods = mfa_config.enabled_methods
        assert len(methods) == 3
        assert "totp" in methods
        assert "sms" in methods
        assert "email" in methods


class TestPasswordHistoryModel:
    """Test PasswordHistory model with comprehensive testing."""

    def test_password_history_creation(
        self, real_database: Session, test_user_auth: UserAuth
    ) -> None:
        """Test creating PasswordHistory records."""
        history1 = PasswordHistory(
            user_id=test_user_auth.id,
            password_hash="$2b$12$old_password_hash_1",
            created_at=datetime.utcnow() - timedelta(days=90),
        )
        history2 = PasswordHistory(
            user_id=test_user_auth.id,
            password_hash="$2b$12$old_password_hash_2",
            created_at=datetime.utcnow() - timedelta(days=30),
        )

        real_database.add_all([history1, history2])
        real_database.commit()

        assert history1.id is not None
        assert history2.id is not None
        assert history1.password_hash != history2.password_hash

    def test_password_history_repr(
        self, real_database: Session, test_user_auth: UserAuth
    ) -> None:
        """Test string representation of PasswordHistory."""
        history = PasswordHistory(
            user_id=test_user_auth.id, password_hash="$2b$12$test_hash"
        )
        real_database.add(history)
        real_database.commit()

        repr_str = repr(history)
        assert f"PasswordHistory(user_id={test_user_auth.id}" in repr_str
        assert "created_at=" in repr_str


class TestLoginAttemptModel:
    """Test LoginAttempt model with comprehensive testing."""

    def test_login_attempt_success(
        self, real_database: Session, test_user_auth: UserAuth
    ) -> None:
        """Test recording successful login attempt."""
        session_id = uuid.uuid4()
        attempt = LoginAttempt(
            user_id=test_user_auth.id,
            username=test_user_auth.email,
            success=True,
            ip_address="192.168.1.100",
            user_agent="Mozilla/5.0 (Windows NT 10.0)",
            device_fingerprint="windows_device_123",
            attempted_at=datetime.utcnow(),
            session_id=session_id,
            event_metadata={"location": "refugee_camp_01", "auth_method": "password"},
        )

        real_database.add(attempt)
        real_database.commit()

        assert attempt.id is not None
        assert attempt.success is True
        assert attempt.failure_reason is None
        assert attempt.session_id == session_id

    def test_login_attempt_failure(
        self, real_database: Session, test_user_auth: UserAuth
    ) -> None:
        """Test recording failed login attempt."""
        attempt = LoginAttempt(
            user_id=test_user_auth.id,
            username="wrong@email.org",
            success=False,
            failure_reason="Invalid credentials",
            ip_address="10.0.0.50",
            user_agent="HavenHealth/1.0",
            device_fingerprint="mobile_device_456",
            event_metadata={"attempts_today": 3},
        )

        real_database.add(attempt)
        real_database.commit()

        assert attempt.success is False
        assert attempt.failure_reason == "Invalid credentials"
        assert attempt.session_id is None

    def test_login_attempt_repr(
        self, real_database: Session, test_user_auth: UserAuth
    ) -> None:
        """Test string representation of LoginAttempt."""
        attempt = LoginAttempt(
            user_id=test_user_auth.id, username=test_user_auth.email, success=True
        )
        real_database.add(attempt)
        real_database.commit()

        repr_str = repr(attempt)
        assert f"LoginAttempt(user_id={test_user_auth.id}" in repr_str
        assert "success=True" in repr_str
        assert "at=" in repr_str


class TestBiometricTemplateModel:
    """Test BiometricTemplate model with comprehensive testing."""

    def test_biometric_template_creation(
        self, real_database: Session, test_user_auth: UserAuth
    ) -> None:
        """Test creating BiometricTemplate with all fields."""
        template = BiometricTemplate(
            template_id="TEMPLATE_FINGERPRINT_001",
            user_id=test_user_auth.id,
            biometric_type="fingerprint",
            encrypted_template="encrypted_biometric_data_base64...",
            quality_score=0.95,
            device_info={"manufacturer": "Samsung", "model": "Galaxy S21"},
            device_model="SM-G991B",
            sdk_version="2.1.0",
            is_active=True,
            last_used_at=datetime.utcnow(),
            usage_count=10,
            last_match_score=0.98,
            created_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(days=365),
        )

        real_database.add(template)
        real_database.commit()

        assert template.id is not None
        assert template.quality_score == 0.95
        assert template.usage_count == 10
        assert template.device_info["manufacturer"] == "Samsung"

    def test_biometric_template_deactivation(
        self, real_database: Session, test_user_auth: UserAuth
    ) -> None:
        """Test biometric template deactivation."""
        template = BiometricTemplate(
            template_id="TEMPLATE_FACE_001",
            user_id=test_user_auth.id,
            biometric_type="face",
            encrypted_template="encrypted_face_data...",
            quality_score=0.88,
            is_active=False,
            deactivated_at=datetime.utcnow(),
            deactivation_reason="User requested removal",
        )

        real_database.add(template)
        real_database.commit()

        assert template.is_active is False
        assert template.deactivated_at is not None
        assert template.deactivation_reason == "User requested removal"

    def test_biometric_template_repr(
        self, real_database: Session, test_user_auth: UserAuth
    ) -> None:
        """Test string representation of BiometricTemplate."""
        template = BiometricTemplate(
            template_id="TEST_001",
            user_id=test_user_auth.id,
            biometric_type="voice",
            encrypted_template="data",
            quality_score=0.9,
        )
        real_database.add(template)
        real_database.commit()

        repr_str = repr(template)
        assert f"BiometricTemplate(user_id={test_user_auth.id}" in repr_str
        assert "type=voice" in repr_str
        assert "active=True" in repr_str


class TestBiometricAuditLogModel:
    """Test BiometricAuditLog model with comprehensive testing."""

    def test_biometric_audit_log_success(
        self, real_database: Session, test_user_auth: UserAuth
    ) -> None:
        """Test logging successful biometric authentication."""
        audit_log = BiometricAuditLog(
            user_id=test_user_auth.id,
            template_id="TEMPLATE_001",
            event_type="verified",
            biometric_type="fingerprint",
            success=True,
            match_score=0.96,
            quality_score=0.92,
            device_info={"os": "iOS", "version": "16.0"},
            ip_address="192.168.1.20",
            user_agent="HavenHealth/1.0 (iOS)",
            session_id=uuid.uuid4(),
        )

        real_database.add(audit_log)
        real_database.commit()

        assert audit_log.id is not None
        assert audit_log.success is True
        assert audit_log.match_score == 0.96
        assert audit_log.failure_reason is None

    def test_biometric_audit_log_failure(
        self, real_database: Session, test_user_auth: UserAuth
    ) -> None:
        """Test logging failed biometric authentication."""
        audit_log = BiometricAuditLog(
            user_id=test_user_auth.id,
            template_id="TEMPLATE_002",
            event_type="failed",
            biometric_type="face",
            success=False,
            match_score=0.45,
            quality_score=0.80,
            failure_reason="Match score below threshold",
            device_info={"camera": "front", "lighting": "poor"},
            ip_address="10.0.0.100",
            user_agent="HavenHealth/1.0 (Android)",
        )

        real_database.add(audit_log)
        real_database.commit()

        assert audit_log.success is False
        assert audit_log.failure_reason == "Match score below threshold"
        assert audit_log.session_id is None

    def test_biometric_audit_log_repr(
        self, real_database: Session, test_user_auth: UserAuth
    ) -> None:
        """Test string representation of BiometricAuditLog."""
        audit_log = BiometricAuditLog(
            user_id=test_user_auth.id,
            event_type="enrolled",
            biometric_type="fingerprint",
            success=True,
        )
        real_database.add(audit_log)
        real_database.commit()

        repr_str = repr(audit_log)
        assert f"BiometricAuditLog(user_id={test_user_auth.id}" in repr_str
        assert "event=enrolled" in repr_str
        assert "success=True" in repr_str


class TestWebAuthnCredentialModel:
    """Test WebAuthnCredential model with comprehensive testing."""

    def test_webauthn_credential_creation(
        self, real_database: Session, test_user_auth: UserAuth
    ) -> None:
        """Test creating WebAuthnCredential with all fields."""
        credential = WebAuthnCredential(
            user_id=test_user_auth.id,
            credential_id="base64_credential_id_string",
            public_key="base64_public_key_string",
            aaguid="f8a011f3-8c0a-4d15-8006-000000000000",
            sign_count=5,
            authenticator_attachment="platform",
            credential_type="public-key",
            transports=["internal", "hybrid"],
            device_name="iPhone 14 Pro",
            last_used_device="iPhone 14 Pro",
            last_used_ip="192.168.1.30",
            is_active=True,
            last_used_at=datetime.utcnow(),
            usage_count=25,
        )

        real_database.add(credential)
        real_database.commit()

        assert credential.id is not None
        assert credential.sign_count == 5
        assert "internal" in credential.transports
        assert credential.device_name == "iPhone 14 Pro"

    def test_webauthn_credential_revocation(
        self, real_database: Session, test_user_auth: UserAuth
    ) -> None:
        """Test WebAuthn credential revocation."""
        credential = WebAuthnCredential(
            user_id=test_user_auth.id,
            credential_id="revoked_credential_id",
            public_key="public_key_data",
            is_active=False,
            revoked_at=datetime.utcnow(),
            revocation_reason="Device lost",
        )

        real_database.add(credential)
        real_database.commit()

        assert credential.is_active is False
        assert credential.revoked_at is not None
        assert credential.revocation_reason == "Device lost"

    def test_webauthn_credential_repr(
        self, real_database: Session, test_user_auth: UserAuth
    ) -> None:
        """Test string representation of WebAuthnCredential."""
        credential = WebAuthnCredential(
            user_id=test_user_auth.id,
            credential_id="test_cred_id",
            public_key="test_key",
            device_name="Test Device",
        )
        real_database.add(credential)
        real_database.commit()

        repr_str = repr(credential)
        assert f"WebAuthnCredential(user_id={test_user_auth.id}" in repr_str
        assert "device=Test Device" in repr_str
        assert "active=True" in repr_str


class TestAPIKeyModel:
    """Test APIKey model with comprehensive testing."""

    def test_api_key_creation(
        self, real_database: Session, test_user_auth: UserAuth
    ) -> None:
        """Test creating APIKey with all fields."""
        api_key = APIKey(
            id=uuid.uuid4(),
            user_id=test_user_auth.id,
            name="Mobile App Integration",
            description="API key for refugee mobile health app",
            key_prefix="hhp_live_",
            key_hash="$2b$12$hashed_api_key_value",
            last_four="a1b2",
            scopes=["read:records", "write:vitals", "read:appointments"],
            tier="premium",
            ip_whitelist=["192.168.1.0/24", "10.0.0.0/8"],
            allowed_origins=[
                "https://refugeehealth.org",
                "https://app.refugeehealth.org",
            ],
            is_active=True,
            expires_at=datetime.utcnow() + timedelta(days=90),
            last_used_at=datetime.utcnow(),
            last_used_ip="192.168.1.50",
            last_used_user_agent="RefugeeHealthApp/2.0",
            usage_count=150,
            rate_limit_override=1000,
            rate_limit_window=3600,
        )

        real_database.add(api_key)
        real_database.commit()

        assert api_key.name == "Mobile App Integration"
        assert "read:records" in api_key.scopes
        assert api_key.tier == "premium"
        assert len(api_key.ip_whitelist) == 2
        assert api_key.usage_count == 150

    def test_api_key_revocation(
        self, real_database: Session, test_user_auth: UserAuth
    ) -> None:
        """Test API key revocation."""
        api_key = APIKey(
            id=uuid.uuid4(),
            user_id=test_user_auth.id,
            name="Revoked Key",
            key_prefix="hhp_test_",
            key_hash="hash",
            last_four="test",
            scopes=[],
            is_active=False,
            revoked_at=datetime.utcnow(),
            revocation_reason="Security breach detected",
        )

        real_database.add(api_key)
        real_database.commit()

        assert api_key.is_active is False
        assert api_key.revoked_at is not None
        assert api_key.revocation_reason == "Security breach detected"

    def test_api_key_repr(
        self, real_database: Session, test_user_auth: UserAuth
    ) -> None:
        """Test string representation of APIKey."""
        api_key = APIKey(
            id=uuid.uuid4(),
            user_id=test_user_auth.id,
            name="Test API Key",
            key_prefix="hhp_",
            key_hash="hash",
            last_four="1234",
            scopes=["read"],
            tier="basic",
        )
        real_database.add(api_key)
        real_database.commit()

        repr_str = repr(api_key)
        assert "APIKey(name=Test API Key" in repr_str
        assert f"user_id={test_user_auth.id}" in repr_str
        assert "tier=basic" in repr_str
        assert "active=True" in repr_str

    def test_api_key_is_valid(
        self, real_database: Session, test_user_auth: UserAuth
    ) -> None:
        """Test is_valid method for APIKey."""
        # Valid key
        valid_key = APIKey(
            id=uuid.uuid4(),
            user_id=test_user_auth.id,
            name="Valid Key",
            key_prefix="hhp_",
            key_hash="hash",
            last_four="1234",
            scopes=["read"],
            is_active=True,
        )
        real_database.add(valid_key)
        real_database.commit()
        assert valid_key.is_valid() is True

        # Inactive key
        valid_key.is_active = False
        real_database.commit()
        assert valid_key.is_valid() is False

        # Revoked key
        revoked_key = APIKey(
            id=uuid.uuid4(),
            user_id=test_user_auth.id,
            name="Revoked Key",
            key_prefix="hhp_",
            key_hash="hash",
            last_four="5678",
            scopes=["read"],
            is_active=True,
            revoked_at=datetime.utcnow(),
        )
        real_database.add(revoked_key)
        real_database.commit()
        assert revoked_key.is_valid() is False

        # Expired key
        expired_key = APIKey(
            id=uuid.uuid4(),
            user_id=test_user_auth.id,
            name="Expired Key",
            key_prefix="hhp_",
            key_hash="hash",
            last_four="9012",
            scopes=["read"],
            is_active=True,
            expires_at=datetime.utcnow() - timedelta(days=1),
        )
        real_database.add(expired_key)
        real_database.commit()
        assert expired_key.is_valid() is False

    def test_api_key_has_scope(
        self, real_database: Session, test_user_auth: UserAuth
    ) -> None:
        """Test has_scope method for APIKey."""
        api_key = APIKey(
            id=uuid.uuid4(),
            user_id=test_user_auth.id,
            name="Scoped Key",
            key_prefix="hhp_",
            key_hash="hash",
            last_four="3456",
            scopes=["read:records", "write:vitals"],
        )
        real_database.add(api_key)
        real_database.commit()

        assert api_key.has_scope("read:records") is True
        assert api_key.has_scope("write:vitals") is True
        assert api_key.has_scope("delete:all") is False

        # Test with None scopes
        api_key.scopes = None
        real_database.commit()
        assert api_key.has_scope("read:records") is False


class TestPasswordResetTokenModel:
    """Test PasswordResetToken model with comprehensive testing."""

    def test_password_reset_token_creation(
        self, real_database: Session, test_user_auth: UserAuth
    ) -> None:
        """Test creating PasswordResetToken."""
        token = PasswordResetToken(
            user_id=test_user_auth.id,
            token="secure_reset_token_123456",
            expires_at=datetime.utcnow() + timedelta(hours=1),
        )

        real_database.add(token)
        real_database.commit()

        assert token.id is not None
        assert token.token == "secure_reset_token_123456"
        assert token.used_at is None

    def test_password_reset_token_usage(
        self, real_database: Session, test_user_auth: UserAuth
    ) -> None:
        """Test using a password reset token."""
        token = PasswordResetToken(
            user_id=test_user_auth.id,
            token="used_token_789",
            expires_at=datetime.utcnow() + timedelta(hours=1),
            used_at=datetime.utcnow(),
            ip_address="192.168.1.75",
            user_agent="Mozilla/5.0 (X11; Linux x86_64)",
        )

        real_database.add(token)
        real_database.commit()

        assert token.used_at is not None
        assert token.ip_address == "192.168.1.75"

    def test_password_reset_token_repr(
        self, real_database: Session, test_user_auth: UserAuth
    ) -> None:
        """Test string representation of PasswordResetToken."""
        expires = datetime.utcnow() + timedelta(hours=1)
        token = PasswordResetToken(
            user_id=test_user_auth.id, token="test_token", expires_at=expires
        )
        real_database.add(token)
        real_database.commit()

        repr_str = repr(token)
        assert f"PasswordResetToken(user_id={test_user_auth.id}" in repr_str
        assert f"expires_at={expires}" in repr_str

    def test_password_reset_token_is_valid(
        self, real_database: Session, test_user_auth: UserAuth
    ) -> None:
        """Test is_valid method for PasswordResetToken."""
        # Valid token
        valid_token = PasswordResetToken(
            user_id=test_user_auth.id,
            token="valid_token",
            expires_at=datetime.utcnow() + timedelta(hours=1),
        )
        real_database.add(valid_token)
        real_database.commit()
        assert valid_token.is_valid() is True

        # Used token
        used_token = PasswordResetToken(
            user_id=test_user_auth.id,
            token="used_token",
            expires_at=datetime.utcnow() + timedelta(hours=1),
            used_at=datetime.utcnow(),
        )
        real_database.add(used_token)
        real_database.commit()
        assert used_token.is_valid() is False

        # Expired token
        expired_token = PasswordResetToken(
            user_id=test_user_auth.id,
            token="expired_token",
            expires_at=datetime.utcnow() - timedelta(hours=1),
        )
        real_database.add(expired_token)
        real_database.commit()
        assert expired_token.is_valid() is False


class TestSMSVerificationCodeModel:
    """Test SMSVerificationCode model with comprehensive testing."""

    def test_sms_verification_code_creation(
        self, real_database: Session, test_user_auth: UserAuth
    ) -> None:
        """Test creating SMSVerificationCode with all fields."""
        code = SMSVerificationCode(
            phone_number="+1234567890",
            code="123456",
            purpose="registration",
            expires_at=datetime.utcnow() + timedelta(minutes=10),
            attempts=0,
            ip_address="192.168.1.90",
            user_id=test_user_auth.id,
        )

        real_database.add(code)
        real_database.commit()

        assert code.id is not None
        assert code.code == "123456"
        assert code.purpose == "registration"
        assert code.attempts == 0

    def test_sms_verification_code_purposes(
        self, real_database: Session, test_user_auth: UserAuth
    ) -> None:
        """Test different SMS verification purposes."""
        purposes = ["registration", "login", "password_reset", "phone_change"]

        for purpose in purposes:
            code = SMSVerificationCode(
                phone_number=f"+1234567{purposes.index(purpose)}",
                code=f"{100000 + purposes.index(purpose)}",
                purpose=purpose,
                expires_at=datetime.utcnow() + timedelta(minutes=5),
                user_id=test_user_auth.id if purpose != "registration" else None,
            )
            real_database.add(code)

        real_database.commit()

        # Verify all purposes were created
        codes = (
            real_database.query(SMSVerificationCode)
            .filter(SMSVerificationCode.phone_number.like("+1234567%"))
            .all()
        )
        assert len(codes) == 4

    def test_sms_verification_code_verification(self, real_database: Session) -> None:
        """Test SMS code verification."""
        code = SMSVerificationCode(
            phone_number="+9876543210",
            code="654321",
            purpose="login",
            expires_at=datetime.utcnow() + timedelta(minutes=10),
            attempts=2,
            verified_at=datetime.utcnow(),
            ip_address="10.0.0.200",
        )

        real_database.add(code)
        real_database.commit()

        assert code.verified_at is not None
        assert code.attempts == 2

    def test_sms_verification_code_repr(self, real_database: Session) -> None:
        """Test string representation of SMSVerificationCode."""
        code = SMSVerificationCode(
            phone_number="+1111111111",
            code="111111",
            purpose="password_reset",
            expires_at=datetime.utcnow() + timedelta(minutes=10),
        )
        real_database.add(code)
        real_database.commit()

        repr_str = repr(code)
        assert "SMSVerificationCode(phone=+1111111111" in repr_str
        assert "purpose=password_reset)" in repr_str

    def test_sms_verification_code_is_valid(self, real_database: Session) -> None:
        """Test is_valid method for SMSVerificationCode."""
        # Valid code
        valid_code = SMSVerificationCode(
            phone_number="+2222222222",
            code="222222",
            purpose="login",
            expires_at=datetime.utcnow() + timedelta(minutes=10),
            attempts=1,
        )
        real_database.add(valid_code)
        real_database.commit()
        assert valid_code.is_valid() is True

        # Already verified code
        verified_code = SMSVerificationCode(
            phone_number="+3333333333",
            code="333333",
            purpose="login",
            expires_at=datetime.utcnow() + timedelta(minutes=10),
            attempts=0,
            verified_at=datetime.utcnow(),
        )
        real_database.add(verified_code)
        real_database.commit()
        assert verified_code.is_valid() is False

        # Expired code
        expired_code = SMSVerificationCode(
            phone_number="+4444444444",
            code="444444",
            purpose="login",
            expires_at=datetime.utcnow() - timedelta(minutes=10),
            attempts=0,
        )
        real_database.add(expired_code)
        real_database.commit()
        assert expired_code.is_valid() is False

        # Too many attempts
        failed_code = SMSVerificationCode(
            phone_number="+5555555555",
            code="555555",
            purpose="login",
            expires_at=datetime.utcnow() + timedelta(minutes=10),
            attempts=3,
        )
        real_database.add(failed_code)
        real_database.commit()
        assert failed_code.is_valid() is False


class TestBackupCodeModel:
    """Test BackupCode model with comprehensive testing."""

    def test_backup_code_creation(
        self, real_database: Session, test_user_auth: UserAuth
    ) -> None:
        """Test creating BackupCode records."""
        # Create multiple backup codes
        codes = []
        for i in range(5):
            code = BackupCode(
                user_id=test_user_auth.id, code_hash=f"$2b$12$backup_code_hash_{i}"
            )
            codes.append(code)

        real_database.add_all(codes)
        real_database.commit()

        assert len(codes) == 5
        for code in codes:
            assert code.id is not None
            assert code.user_id == test_user_auth.id

    def test_backup_code_usage(
        self, real_database: Session, test_user_auth: UserAuth
    ) -> None:
        """Test using a backup code."""
        code = BackupCode(
            user_id=test_user_auth.id,
            code_hash="$2b$12$used_backup_code_hash",
            used_at=datetime.utcnow(),
            used_ip="192.168.1.150",
            used_user_agent="HavenHealth/1.0 Emergency Access",
        )

        real_database.add(code)
        real_database.commit()

        assert code.used_at is not None
        assert code.used_ip == "192.168.1.150"
        assert "Emergency Access" in code.used_user_agent

    def test_backup_code_repr(
        self, real_database: Session, test_user_auth: UserAuth
    ) -> None:
        """Test string representation of BackupCode."""
        # Unused code
        unused_code = BackupCode(
            user_id=test_user_auth.id, code_hash="$2b$12$unused_hash"
        )
        real_database.add(unused_code)
        real_database.commit()

        repr_str = repr(unused_code)
        assert f"BackupCode(user_id={test_user_auth.id}" in repr_str
        assert "used=No)" in repr_str

        # Used code
        used_code = BackupCode(
            user_id=test_user_auth.id,
            code_hash="$2b$12$used_hash",
            used_at=datetime.utcnow(),
        )
        real_database.add(used_code)
        real_database.commit()

        repr_str = repr(used_code)
        assert "used=Yes)" in repr_str

    def test_backup_code_is_valid(
        self, real_database: Session, test_user_auth: UserAuth
    ) -> None:
        """Test is_valid method for BackupCode."""
        # Valid (unused) code
        valid_code = BackupCode(
            user_id=test_user_auth.id, code_hash="$2b$12$valid_unused_code"
        )
        real_database.add(valid_code)
        real_database.commit()
        assert valid_code.is_valid() is True

        # Invalid (used) code
        used_code = BackupCode(
            user_id=test_user_auth.id,
            code_hash="$2b$12$used_code",
            used_at=datetime.utcnow(),
        )
        real_database.add(used_code)
        real_database.commit()
        assert used_code.is_valid() is False

    def test_backup_code_unique_constraint(
        self, real_database: Session, test_user_auth: UserAuth
    ) -> None:
        """Test unique constraint on user_id and code_hash."""
        # Create first code
        code1 = BackupCode(user_id=test_user_auth.id, code_hash="$2b$12$duplicate_hash")
        real_database.add(code1)
        real_database.commit()

        # Try to create duplicate
        code2 = BackupCode(user_id=test_user_auth.id, code_hash="$2b$12$duplicate_hash")
        real_database.add(code2)

        with pytest.raises(IntegrityError):
            real_database.commit()


class TestAuthModelRelationships:
    """Test relationships between auth models."""

    def test_user_auth_relationships(
        self, real_database: Session, test_user_auth: UserAuth
    ) -> None:
        """Test all UserAuth relationships."""
        # Create related records
        session = UserSession(
            user_id=test_user_auth.id,
            token="test_token",
            expires_at=datetime.utcnow() + timedelta(hours=1),
        )

        device = DeviceInfo(user_id=test_user_auth.id, device_fingerprint="test_device")

        mfa_config = MFAConfig(user_id=test_user_auth.id, totp_enabled=True)

        password_history = PasswordHistory(
            user_id=test_user_auth.id, password_hash="old_hash"
        )

        login_attempt = LoginAttempt(
            user_id=test_user_auth.id, username=test_user_auth.email, success=True
        )

        biometric = BiometricTemplate(
            template_id="BIO_001",
            user_id=test_user_auth.id,
            biometric_type="fingerprint",
            encrypted_template="data",
            quality_score=0.9,
        )

        webauthn = WebAuthnCredential(
            user_id=test_user_auth.id, credential_id="CRED_001", public_key="key_data"
        )

        api_key = APIKey(
            id=uuid.uuid4(),
            user_id=test_user_auth.id,
            name="Test Key",
            key_prefix="hhp_",
            key_hash="hash",
            last_four="1234",
            scopes=[],
        )

        real_database.add_all(
            [
                session,
                device,
                mfa_config,
                password_history,
                login_attempt,
                biometric,
                webauthn,
                api_key,
            ]
        )
        real_database.commit()

        # Verify relationships
        assert len(test_user_auth.sessions) >= 1
        assert len(test_user_auth.devices) >= 1
        assert test_user_auth.mfa_config is not None
        assert len(test_user_auth.password_history) >= 1
        assert len(test_user_auth.login_attempts) >= 1
        assert len(test_user_auth.biometric_templates) >= 1
        assert len(test_user_auth.webauthn_credentials) >= 1
        assert len(test_user_auth.api_keys) >= 1

    def test_cascade_deletion(
        self, real_database: Session, test_patient: Patient
    ) -> None:
        """Test cascade deletion of related records."""
        # Create user with related records
        user = UserAuth(
            patient_id=test_patient.id,
            email="cascade.test@example.org",
            password_hash="hash",
            created_by=uuid.uuid4(),
        )
        real_database.add(user)
        real_database.commit()

        # Add related records
        session = UserSession(
            user_id=user.id,
            token="cascade_token",
            expires_at=datetime.utcnow() + timedelta(hours=1),
        )

        device = DeviceInfo(user_id=user.id, device_fingerprint="cascade_device")

        real_database.add_all([session, device])
        real_database.commit()

        # Delete user
        real_database.delete(user)
        real_database.commit()

        # Verify cascade deletion
        assert real_database.query(UserSession).filter_by(user_id=user.id).count() == 0
        assert real_database.query(DeviceInfo).filter_by(user_id=user.id).count() == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
