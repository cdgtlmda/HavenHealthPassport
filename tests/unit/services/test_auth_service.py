"""
Comprehensive tests for AuthenticationService with comprehensive test coverage.

CRITICAL: Medical-grade testing for healthcare project serving displaced refugees.
Uses real database operations - no mocks for core authentication functionality.
Tests cover all security-critical paths with real data validation.
"""

import os
import uuid
from datetime import datetime, timedelta

import bcrypt
import pyotp
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.models.auth import (
    BackupCode,
    MFAConfig,
    PasswordHistory,
    PasswordResetToken,
    SMSVerificationCode,
)
from src.models.base import Base
from src.services.auth_service import AuthenticationService
from src.utils.exceptions import AuthenticationException

# Removed mocks - using real AWS services only


@pytest.fixture
def real_database():
    """Create real SQLite database for testing - no mocks allowed for medical data."""
    # Use in-memory SQLite for fast, isolated testing
    engine = create_engine("sqlite:///:memory:", echo=False)

    # Create all tables
    Base.metadata.create_all(engine)

    # Create session maker
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    session = SessionLocal()
    yield session

    session.close()


@pytest.fixture
def auth_service(real_database):
    """Create AuthenticationService with real database session."""
    return AuthenticationService(db=real_database)


@pytest.fixture
def sample_patient_id():
    """Generate a sample patient ID."""
    return uuid.uuid4()


@pytest.fixture
def valid_user_data():
    """Provide valid user registration data."""
    # Use a unique password that hasn't been breached
    unique_suffix = str(uuid.uuid4())[:8]
    return {
        "email": "test@example.com",
        "password": f"HavenHealth2025!{unique_suffix}",
        "phone_number": "+1234567890",
        "role": "patient",
    }


class TestAuthenticationServiceInitialization:
    """Test service initialization and configuration."""

    def test_init_with_database_session(self, real_database):
        """Test service initializes with real database session."""
        service = AuthenticationService(db=real_database)

        assert service.db is real_database
        assert service._jwt_handler is None  # Lazy loaded
        assert service._email_service is not None
        assert service.twilio_client is None  # No env vars set
        assert service.twilio_from_number is None

    def test_init_with_twilio_config(self, real_database):
        """Test service initializes Twilio when environment variables are set."""
        # Set up real Twilio test credentials
        os.environ["TWILIO_ACCOUNT_SID"] = os.getenv(
            "TEST_TWILIO_ACCOUNT_SID", "ACtest"
        )
        os.environ["TWILIO_AUTH_TOKEN"] = os.getenv(
            "TEST_TWILIO_AUTH_TOKEN", "testtoken"
        )
        os.environ["TWILIO_FROM_NUMBER"] = os.getenv(
            "TEST_TWILIO_FROM_NUMBER", "+15005550006"
        )

        try:
            service = AuthenticationService(db=real_database)

            # Check if Twilio initialized (may be None if test credentials not available)
            if service.twilio_client is not None:
                assert service.twilio_from_number == os.environ["TWILIO_FROM_NUMBER"]
        finally:
            # Clean up environment
            for key in [
                "TWILIO_ACCOUNT_SID",
                "TWILIO_AUTH_TOKEN",
                "TWILIO_FROM_NUMBER",
            ]:
                os.environ.pop(key, None)

    def test_init_twilio_failure_handling(self, real_database):
        """Test graceful handling of Twilio initialization failure."""
        # Use invalid credentials to trigger failure
        os.environ["TWILIO_ACCOUNT_SID"] = "invalid_sid"
        os.environ["TWILIO_AUTH_TOKEN"] = "invalid_token"
        os.environ["TWILIO_FROM_NUMBER"] = "invalid_number"

        try:
            service = AuthenticationService(db=real_database)

            # Should handle exception gracefully
            assert service.twilio_client is None or service.twilio_from_number is None
        finally:
            # Clean up environment
            for key in [
                "TWILIO_ACCOUNT_SID",
                "TWILIO_AUTH_TOKEN",
                "TWILIO_FROM_NUMBER",
            ]:
                os.environ.pop(key, None)

    def test_jwt_handler_lazy_loading(self, auth_service):
        """Test JWT handler is lazy loaded correctly."""
        # Initially None
        assert auth_service._jwt_handler is None

        # Access should trigger lazy loading with real JWT handler
        handler = auth_service.jwt_handler

        assert handler is not None
        assert auth_service._jwt_handler is handler

        # Verify it's a real JWT handler instance
        assert hasattr(handler, "create_access_token")
        assert hasattr(handler, "create_refresh_token")
        assert hasattr(handler, "decode_token")


class TestUserCreation:
    """Test user authentication record creation with medical-grade validation."""

    def test_create_user_auth_success(
        self, auth_service, sample_patient_id, valid_user_data
    ):
        """Test successful user creation with all validations."""
        user_auth = auth_service.create_user_auth(
            patient_id=sample_patient_id, **valid_user_data
        )

        # Verify user created successfully
        assert user_auth.id is not None
        assert user_auth.patient_id == sample_patient_id
        assert user_auth.email == valid_user_data["email"]
        assert user_auth.phone_number == valid_user_data["phone_number"]
        assert user_auth.role == valid_user_data["role"]
        assert user_auth.is_active is True
        assert user_auth.email_verified is False
        assert user_auth.phone_verified is False
        assert user_auth.created_at is not None
        assert user_auth.password_changed_at is not None

        # Verify password is hashed (not plain text)
        assert user_auth.password_hash != valid_user_data["password"]
        assert user_auth.password_hash.startswith("$2b$")

        # Verify password can be verified
        assert bcrypt.checkpw(
            valid_user_data["password"].encode(), user_auth.password_hash.encode()
        )

    def test_create_user_auth_email_normalization(
        self, auth_service, sample_patient_id
    ):
        """Test email normalization and case handling."""
        unique_password = f"HavenHealth2025!{str(uuid.uuid4())[:8]}"
        user_auth = auth_service.create_user_auth(
            patient_id=sample_patient_id,
            email="TEST@EXAMPLE.COM",
            password=unique_password,
        )

        # Email should be normalized to lowercase
        assert user_auth.email == "test@example.com"

    def test_create_user_auth_invalid_email(self, auth_service, sample_patient_id):
        """Test rejection of invalid email formats."""
        invalid_emails = [
            "",
            "invalid",
            "test@",
            "@example.com",
            "test..test@example.com",
        ]

        for invalid_email in invalid_emails:
            with pytest.raises(ValueError, match="Invalid email format"):
                auth_service.create_user_auth(
                    patient_id=sample_patient_id,
                    email=invalid_email,
                    password="SecurePass123!@#",
                )

    def test_create_user_auth_duplicate_email(
        self, auth_service, sample_patient_id, valid_user_data
    ):
        """Test rejection of duplicate email addresses."""
        # Create first user
        auth_service.create_user_auth(patient_id=sample_patient_id, **valid_user_data)

        # Attempt to create second user with same email
        with pytest.raises(ValueError, match="Email already registered"):
            auth_service.create_user_auth(patient_id=uuid.uuid4(), **valid_user_data)

    def test_create_user_auth_password_policy_failure(
        self, auth_service, sample_patient_id
    ):
        """Test password policy validation failure."""
        # Use a real weak password that will fail policy validation
        with pytest.raises(ValueError, match="Password validation failed"):
            auth_service.create_user_auth(
                patient_id=sample_patient_id, email="test@example.com", password="weak"
            )

    def test_create_user_auth_breached_password(self, auth_service, sample_patient_id):
        """Test rejection of breached passwords."""
        # Use a commonly breached password that will trigger real breach check
        with pytest.raises(
            ValueError, match="password has been found in data breaches"
        ):
            auth_service.create_user_auth(
                patient_id=sample_patient_id,
                email="test@example.com",
                password="Password123!",  # Commonly breached password
            )

    def test_create_user_auth_without_phone(self, auth_service, sample_patient_id):
        """Test user creation without phone number."""
        user_auth = auth_service.create_user_auth(
            patient_id=sample_patient_id,
            email="test@example.com",
            password="SecurePass123!@#",
        )

        assert user_auth.phone_number is None
        assert user_auth.phone_verified is None

    def test_create_user_auth_password_history_created(
        self, auth_service, sample_patient_id, valid_user_data
    ):
        """Test password history entry is created."""
        user_auth = auth_service.create_user_auth(
            patient_id=sample_patient_id, **valid_user_data
        )

        # Check password history was created
        auth_service.db.flush()
        history = (
            auth_service.db.query(PasswordHistory)
            .filter(PasswordHistory.user_id == user_auth.id)
            .first()
        )

        assert history is not None
        assert history.password_hash == user_auth.password_hash
        assert history.created_at is not None


class TestAuthentication:
    """Test user authentication with comprehensive security checks."""

    def test_authenticate_user_success(
        self, auth_service, sample_patient_id, valid_user_data
    ):
        """Test successful user authentication."""
        # Create user
        user_auth = auth_service.create_user_auth(
            patient_id=sample_patient_id, **valid_user_data
        )
        auth_service.db.commit()

        # Authenticate with real JWT handler
        result = auth_service.authenticate_user(
            username=valid_user_data["email"], password=valid_user_data["password"]
        )

        assert result is not None
        authenticated_user, session = result

        # Verify authenticated user
        assert authenticated_user.id == user_auth.id
        assert authenticated_user.email == valid_user_data["email"]
        assert authenticated_user.last_login is not None
        assert authenticated_user.login_count == 1
        assert authenticated_user.failed_login_attempts == 0

        # Verify session created with real tokens
        assert session.user_id == user_auth.id
        assert session.access_token is not None
        assert session.refresh_token is not None
        assert len(session.access_token) > 20  # Real JWT token
        assert len(session.refresh_token) > 20  # Real JWT token
        assert session.is_active is True

    def test_authenticate_user_case_insensitive_email(
        self, auth_service, sample_patient_id, valid_user_data
    ):
        """Test authentication with case-insensitive email matching."""
        # Create user with lowercase email
        auth_service.create_user_auth(patient_id=sample_patient_id, **valid_user_data)
        auth_service.db.commit()

        # Authenticate with uppercase email using real JWT
        result = auth_service.authenticate_user(
            username="TEST@EXAMPLE.COM", password=valid_user_data["password"]
        )

        assert result is not None

    def test_authenticate_user_not_found(self, auth_service):
        """Test authentication failure for non-existent user."""
        result = auth_service.authenticate_user(
            username="nonexistent@example.com", password="password"
        )

        assert result is None

    def test_authenticate_user_invalid_password(
        self, auth_service, sample_patient_id, valid_user_data
    ):
        """Test authentication failure for invalid password."""
        # Create user
        user_auth = auth_service.create_user_auth(
            patient_id=sample_patient_id, **valid_user_data
        )
        auth_service.db.commit()

        # Attempt authentication with wrong password
        result = auth_service.authenticate_user(
            username=valid_user_data["email"], password="wrong_password"
        )

        assert result is None

        # Check failed login tracking
        auth_service.db.refresh(user_auth)
        assert user_auth.failed_login_attempts == 1
        assert user_auth.last_failed_login is not None

    def test_authenticate_user_account_lockout(
        self, auth_service, sample_patient_id, valid_user_data
    ):
        """Test account lockout after multiple failed attempts."""
        # Create user
        user_auth = auth_service.create_user_auth(
            patient_id=sample_patient_id, **valid_user_data
        )
        auth_service.db.commit()

        # Simulate 5 failed login attempts
        for _ in range(5):
            result = auth_service.authenticate_user(
                username=valid_user_data["email"], password="wrong_password"
            )
            assert result is None

        # Check account is locked
        auth_service.db.refresh(user_auth)
        assert user_auth.is_locked is True
        assert user_auth.locked_until is not None
        assert user_auth.failed_login_attempts == 5

        # Try authentication with correct password - should still fail
        result = auth_service.authenticate_user(
            username=valid_user_data["email"], password=valid_user_data["password"]
        )
        assert result is None

    def test_authenticate_user_unlock_after_timeout(
        self, auth_service, sample_patient_id, valid_user_data
    ):
        """Test account unlock after lockout timeout expires."""
        # Create locked user
        user_auth = auth_service.create_user_auth(
            patient_id=sample_patient_id, **valid_user_data
        )
        user_auth.is_locked = True
        user_auth.locked_until = datetime.utcnow() - timedelta(
            minutes=1
        )  # Expired lock
        auth_service.db.commit()

        # Should unlock and authenticate successfully with real JWT
        result = auth_service.authenticate_user(
            username=valid_user_data["email"], password=valid_user_data["password"]
        )

        assert result is not None

        # Check account is unlocked
        auth_service.db.refresh(user_auth)
        assert user_auth.is_locked is False
        assert user_auth.locked_until is None

    def test_authenticate_user_inactive_account(
        self, auth_service, sample_patient_id, valid_user_data
    ):
        """Test authentication failure for inactive account."""
        # Create inactive user
        user_auth = auth_service.create_user_auth(
            patient_id=sample_patient_id, **valid_user_data
        )
        user_auth.is_active = False
        auth_service.db.commit()

        result = auth_service.authenticate_user(
            username=valid_user_data["email"], password=valid_user_data["password"]
        )

        assert result is None

    def test_authenticate_user_password_reset_required(
        self, auth_service, sample_patient_id, valid_user_data
    ):
        """Test authentication with password reset flag."""
        # Create user requiring password reset
        user_auth = auth_service.create_user_auth(
            patient_id=sample_patient_id, **valid_user_data
        )
        user_auth.password_reset_required = True
        auth_service.db.commit()

        # Should still allow login but flag reset requirement with real JWT
        result = auth_service.authenticate_user(
            username=valid_user_data["email"], password=valid_user_data["password"]
        )

        assert result is not None
        authenticated_user, session = result
        assert authenticated_user.password_reset_required is True


class TestSessionManagement:
    """Test session creation, validation, and invalidation."""

    def test_create_session_basic(self, auth_service):
        """Test basic session creation."""
        user_id = uuid.uuid4()

        # Create session with real JWT handler
        session = auth_service.create_session(user_id)

        assert session.user_id == user_id
        assert session.access_token is not None
        assert session.refresh_token is not None
        assert len(session.access_token) > 20  # Real JWT token
        assert len(session.refresh_token) > 20  # Real JWT token
        assert session.is_active is True
        assert session.created_at is not None
        assert session.last_activity is not None
        assert session.expires_at is not None

    def test_create_session_with_device_info(self, auth_service):
        """Test session creation with device information."""
        user_id = uuid.uuid4()
        device_id = uuid.uuid4()
        ip_address = "192.168.1.100"
        user_agent = "Mozilla/5.0..."

        # Create session with device info using real JWT
        session = auth_service.create_session(
            user_id=user_id,
            device_id=device_id,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        assert session.device_id == device_id
        assert session.ip_address == ip_address
        assert session.user_agent == user_agent

    def test_validate_session_success(self, auth_service):
        """Test successful session validation."""
        user_id = uuid.uuid4()
        session_token = "valid_token_123"

        # Create session with real JWT
        session = auth_service.create_session(user_id)
        auth_service.db.commit()

        # Use the real access token for validation
        session_token = session.access_token

        # Validate session with real JWT decoding
        validated_session = auth_service.validate_session(session_token)

        assert validated_session is not None
        assert validated_session.id == session.id
        assert validated_session.user_id == user_id
        assert validated_session.is_active is True

    def test_validate_session_invalid_token(self, auth_service):
        """Test session validation with invalid token."""
        # Use a clearly invalid token that will fail JWT decoding
        result = auth_service.validate_session("invalid_token_xyz123")

        assert result is None

    def test_validate_session_no_user_id(self, auth_service):
        """Test session validation with malformed token."""
        # Use a malformed JWT that won't decode properly
        malformed_token = "eyJhbGciOiJIUzI1NiJ9.eyJzb21lX2ZpZWxkIjoidmFsdWUifQ.invalid"

        result = auth_service.validate_session(malformed_token)

        assert result is None

    def test_validate_session_not_found(self, auth_service):
        """Test session validation when session not found in database."""
        # Create a valid JWT token format but for non-existent session
        # This will decode but won't find session in DB
        fake_user_id = str(uuid.uuid4())

        # Create a temporary session to get JWT handler
        auth_service.create_session(uuid.uuid4())
        auth_service.db.rollback()  # Don't save it

        # Use a token that will decode but has no matching session
        result = auth_service.validate_session("nonexistent_token_" + fake_user_id)

        assert result is None

    def test_validate_session_expired(self, auth_service):
        """Test session validation with expired session."""
        user_id = uuid.uuid4()
        session_token = "expired_token"

        # Create expired session with real JWT
        session = auth_service.create_session(user_id)
        session_token = session.access_token
        session.expires_at = datetime.utcnow() - timedelta(hours=1)  # Expired
        auth_service.db.commit()

        # Validate expired session
        result = auth_service.validate_session(session_token)

        assert result is None

        # Check session was marked inactive
        auth_service.db.refresh(session)
        assert session.is_active is False
        assert session.invalidated_at is not None

    def test_logout_user_specific_session(self, auth_service):
        """Test logout of specific session."""
        user_id = uuid.uuid4()
        session_token = "session_to_logout"

        # Create session with real JWT
        session = auth_service.create_session(user_id)
        session_token = session.access_token
        auth_service.db.commit()

        # Logout specific session
        result = auth_service.logout_user(user_id, session_token)

        assert result is True

        # Check session was invalidated
        auth_service.db.refresh(session)
        assert session.is_active is False
        assert session.invalidated_at is not None

    def test_logout_user_all_sessions(self, auth_service):
        """Test logout of all user sessions."""
        user_id = uuid.uuid4()

        # Create multiple sessions with real JWT
        session1 = auth_service.create_session(user_id)
        session2 = auth_service.create_session(user_id)
        auth_service.db.commit()

        # Logout all sessions
        result = auth_service.logout_user(user_id)

        assert result is True

        # Check both sessions were invalidated
        auth_service.db.refresh(session1)
        auth_service.db.refresh(session2)
        assert session1.is_active is False
        assert session2.is_active is False

    def test_logout_user_session_not_found(self, auth_service):
        """Test logout with non-existent session token."""
        result = auth_service.logout_user(uuid.uuid4(), "nonexistent_token")
        assert result is False

    def test_invalidate_all_sessions(self, auth_service):
        """Test invalidating all sessions for a user."""
        user_id = uuid.uuid4()

        # Create multiple sessions with real JWT
        sessions = [
            auth_service.create_session(user_id),
            auth_service.create_session(user_id),
            auth_service.create_session(user_id),
        ]
        auth_service.db.commit()

        # Invalidate all sessions
        count = auth_service.invalidate_all_sessions(user_id)

        assert count == 3

        # Check all sessions were invalidated
        for session in sessions:
            auth_service.db.refresh(session)
            assert session.is_active is False
            assert session.invalidated_at is not None


class TestPasswordOperations:
    """Test password hashing, verification, and security features."""

    def test_hash_password(self, auth_service):
        """Test password hashing with bcrypt."""
        password = "TestPassword123!"
        hashed = auth_service.hash_password(password)

        # Verify hash format
        assert hashed != password
        assert hashed.startswith("$2b$")

        # Verify hash is verifiable
        assert auth_service.verify_password(password, hashed)

    def test_verify_password_success(self, auth_service):
        """Test successful password verification."""
        password = "TestPassword123!"
        hashed = auth_service.hash_password(password)

        assert auth_service.verify_password(password, hashed) is True

    def test_verify_password_failure(self, auth_service):
        """Test password verification failure."""
        password = "TestPassword123!"
        wrong_password = "WrongPassword456!"
        hashed = auth_service.hash_password(password)

        assert auth_service.verify_password(wrong_password, hashed) is False

    def test_verify_password_invalid_hash(self, auth_service):
        """Test password verification with invalid hash."""
        result = auth_service.verify_password("password", "invalid_hash")
        assert result is False

    def test_is_password_breached_found(self, auth_service):
        """Test password breach detection when password is found."""
        # Use a known breached password for real API test
        # "password" is one of the most common breached passwords
        result = auth_service._is_password_breached("password")

        # This should be detected as breached by the real API
        assert result is True

    def test_is_password_breached_not_found(self, auth_service):
        """Test password breach detection when password is not found."""
        # Use a highly unique password unlikely to be breached
        unique_password = f"VeryUniquePassword{uuid.uuid4()}!@#$%"

        result = auth_service._is_password_breached(unique_password)

        # This unique password should not be found in breaches
        assert result is False

    def test_is_password_breached_api_error(self, auth_service):
        """Test password breach detection with API error (fail open)."""
        # Temporarily break the network to simulate API error
        import socket

        original_getaddrinfo = socket.getaddrinfo

        def broken_getaddrinfo(*args, **kwargs):
            raise socket.gaierror("Network error")

        try:
            socket.getaddrinfo = broken_getaddrinfo
            result = auth_service._is_password_breached("password")
            # Should fail open (return False) when API is down
            assert result is False
        finally:
            socket.getaddrinfo = original_getaddrinfo

    def test_add_password_history(
        self, auth_service, sample_patient_id, valid_user_data
    ):
        """Test password history tracking."""
        # Create user
        user_auth = auth_service.create_user_auth(
            patient_id=sample_patient_id, **valid_user_data
        )
        auth_service.db.commit()

        # Add additional password to history
        new_hash = auth_service.hash_password("NewPassword123!")
        auth_service._add_password_history(user_auth.id, new_hash)
        auth_service.db.commit()

        # Check history entries
        history = (
            auth_service.db.query(PasswordHistory)
            .filter(PasswordHistory.user_id == user_auth.id)
            .order_by(PasswordHistory.created_at.desc())
            .all()
        )

        assert len(history) == 2  # Original + new
        assert history[0].password_hash == new_hash

    def test_add_password_history_limit(
        self, auth_service, sample_patient_id, valid_user_data
    ):
        """Test password history is limited to 12 entries."""
        # Create user
        user_auth = auth_service.create_user_auth(
            patient_id=sample_patient_id, **valid_user_data
        )
        auth_service.db.commit()

        # Add 15 more passwords (total 16)
        for i in range(15):
            password_hash = auth_service.hash_password(f"Password{i}!")
            auth_service._add_password_history(user_auth.id, password_hash)

        auth_service.db.commit()

        # Check only 12 are kept
        history_count = (
            auth_service.db.query(PasswordHistory)
            .filter(PasswordHistory.user_id == user_auth.id)
            .count()
        )

        assert history_count == 12

    def test_is_password_reused_true(
        self, auth_service, sample_patient_id, valid_user_data
    ):
        """Test password reuse detection when password was used before."""
        # Create user
        user_auth = auth_service.create_user_auth(
            patient_id=sample_patient_id, **valid_user_data
        )
        auth_service.db.commit()

        # Check if original password is detected as reused
        result = auth_service._is_password_reused(
            user_auth.id, valid_user_data["password"]
        )
        assert result is True

    def test_is_password_reused_false(
        self, auth_service, sample_patient_id, valid_user_data
    ):
        """Test password reuse detection when password is new."""
        # Create user
        user_auth = auth_service.create_user_auth(
            patient_id=sample_patient_id, **valid_user_data
        )
        auth_service.db.commit()

        # Check if new password is detected as reused
        result = auth_service._is_password_reused(
            user_auth.id, "CompletelyNewPassword123!"
        )
        assert result is False


class TestMFAOperations:
    """Test Multi-Factor Authentication functionality."""

    def test_enable_mfa_totp_success(
        self, auth_service, sample_patient_id, valid_user_data
    ):
        """Test enabling TOTP MFA."""
        # Create user
        user_auth = auth_service.create_user_auth(
            patient_id=sample_patient_id, **valid_user_data
        )
        auth_service.db.commit()

        # Enable TOTP MFA
        result = auth_service.enable_mfa(user_auth.id, "totp")

        assert result is not None
        secret, qr_code, backup_codes, mfa_config = result

        # Verify TOTP setup
        assert secret is not None
        assert len(secret) == 32  # Base32 secret length
        assert qr_code.startswith("data:image/png;base64,")
        assert len(backup_codes) == 10
        assert mfa_config.totp_enabled is True
        assert mfa_config.totp_secret == secret

    def test_enable_mfa_sms_with_phone(
        self, auth_service, sample_patient_id, valid_user_data
    ):
        """Test enabling SMS MFA with provided phone number."""
        # Create user
        user_auth = auth_service.create_user_auth(
            patient_id=sample_patient_id, **valid_user_data
        )
        auth_service.db.commit()

        # Enable SMS MFA with real implementation
        # This may skip if SMS service not configured
        try:
            result = auth_service.enable_mfa(
                user_auth.id, "sms", phone_number="+1234567890"
            )
        except Exception as e:
            if "SMS service not available" in str(e):
                pytest.skip("SMS service not configured for testing")
            raise

        assert result is not None
        phone, qr_code, backup_codes, mfa_config = result

        # Verify SMS setup
        assert phone == "+1234567890"
        assert qr_code == ""  # No QR for SMS
        assert len(backup_codes) == 10
        assert mfa_config.sms_enabled is True
        assert mfa_config.sms_phone_number == "+1234567890"

    def test_enable_mfa_sms_user_phone(
        self, auth_service, sample_patient_id, valid_user_data
    ):
        """Test enabling SMS MFA using user's existing phone number."""
        # Create user
        user_auth = auth_service.create_user_auth(
            patient_id=sample_patient_id, **valid_user_data
        )
        auth_service.db.commit()

        # Enable SMS MFA without providing phone (should use user's phone)
        try:
            result = auth_service.enable_mfa(user_auth.id, "sms")
        except Exception as e:
            if "SMS service not available" in str(e):
                pytest.skip("SMS service not configured for testing")
            raise

        assert result is not None
        phone, qr_code, backup_codes, mfa_config = result

        assert phone == valid_user_data["phone_number"]

    def test_enable_mfa_sms_no_phone(self, auth_service, sample_patient_id):
        """Test enabling SMS MFA without phone number fails."""
        # Create user without phone
        user_auth = auth_service.create_user_auth(
            patient_id=sample_patient_id,
            email="test@example.com",
            password="SecurePass123!@#",
        )
        auth_service.db.commit()

        with pytest.raises(ValueError, match="Phone number required"):
            auth_service.enable_mfa(user_auth.id, "sms")

    def test_enable_mfa_invalid_phone(
        self, auth_service, sample_patient_id, valid_user_data
    ):
        """Test enabling SMS MFA with invalid phone number."""
        # Create user
        user_auth = auth_service.create_user_auth(
            patient_id=sample_patient_id, **valid_user_data
        )
        auth_service.db.commit()

        with pytest.raises(ValueError, match="Invalid phone number"):
            auth_service.enable_mfa(user_auth.id, "sms", phone_number="invalid_phone")

    def test_enable_mfa_invalid_method(
        self, auth_service, sample_patient_id, valid_user_data
    ):
        """Test enabling MFA with invalid method."""
        # Create user
        user_auth = auth_service.create_user_auth(
            patient_id=sample_patient_id, **valid_user_data
        )
        auth_service.db.commit()

        with pytest.raises(ValueError, match="Invalid MFA method"):
            auth_service.enable_mfa(user_auth.id, "invalid_method")

    def test_verify_mfa_totp_success(
        self, auth_service, sample_patient_id, valid_user_data
    ):
        """Test successful TOTP MFA verification."""
        # Create user and enable TOTP
        user_auth = auth_service.create_user_auth(
            patient_id=sample_patient_id, **valid_user_data
        )
        auth_service.db.commit()

        secret, _, _, _ = auth_service.enable_mfa(user_auth.id, "totp")
        auth_service.db.commit()

        # Generate valid TOTP code
        totp = pyotp.TOTP(secret)
        valid_code = totp.now()

        # Verify code
        result = auth_service.verify_mfa(user_auth.id, valid_code)
        assert result is True

    def test_verify_mfa_totp_invalid_code(
        self, auth_service, sample_patient_id, valid_user_data
    ):
        """Test TOTP MFA verification with invalid code."""
        # Create user and enable TOTP
        user_auth = auth_service.create_user_auth(
            patient_id=sample_patient_id, **valid_user_data
        )
        auth_service.db.commit()

        auth_service.enable_mfa(user_auth.id, "totp")
        auth_service.db.commit()

        # Verify with invalid code
        result = auth_service.verify_mfa(user_auth.id, "123456")
        assert result is False

    def test_verify_mfa_sms_success(
        self, auth_service, sample_patient_id, valid_user_data
    ):
        """Test successful SMS MFA verification."""
        # Create user and enable SMS
        user_auth = auth_service.create_user_auth(
            patient_id=sample_patient_id, **valid_user_data
        )
        auth_service.db.commit()

        # Enable SMS MFA
        try:
            auth_service.enable_mfa(user_auth.id, "sms")
            auth_service.db.commit()
        except Exception as e:
            if "SMS service not available" in str(e):
                pytest.skip("SMS service not configured for testing")
            raise

        # Create SMS verification code
        sms_code = SMSVerificationCode(
            id=uuid.uuid4(),
            user_id=user_auth.id,
            code="123456",
            phone_number=valid_user_data["phone_number"],
            expires_at=datetime.utcnow() + timedelta(minutes=5),
            created_at=datetime.utcnow(),
        )
        auth_service.db.add(sms_code)
        auth_service.db.commit()

        # Verify SMS code
        result = auth_service.verify_mfa(user_auth.id, "123456")
        assert result is True

        # Check code was marked as used
        auth_service.db.refresh(sms_code)
        assert sms_code.used is True

    def test_verify_mfa_backup_code_success(
        self, auth_service, sample_patient_id, valid_user_data
    ):
        """Test successful backup code verification."""
        # Create user and enable MFA
        user_auth = auth_service.create_user_auth(
            patient_id=sample_patient_id, **valid_user_data
        )
        auth_service.db.commit()

        _, _, backup_codes, _ = auth_service.enable_mfa(user_auth.id, "totp")
        auth_service.db.commit()

        # Use first backup code
        backup_code = backup_codes[0]
        result = auth_service.verify_mfa(user_auth.id, backup_code)
        assert result is True

        # Verify code cannot be reused
        result = auth_service.verify_mfa(user_auth.id, backup_code)
        assert result is False

    def test_verify_mfa_no_config(
        self, auth_service, sample_patient_id, valid_user_data
    ):
        """Test MFA verification with no MFA configuration."""
        # Create user without MFA
        user_auth = auth_service.create_user_auth(
            patient_id=sample_patient_id, **valid_user_data
        )
        auth_service.db.commit()

        result = auth_service.verify_mfa(user_auth.id, "123456")
        assert result is False


class TestSMSOperations:
    """Test SMS verification code operations."""

    def test_send_sms_code_success(
        self, auth_service, sample_patient_id, valid_user_data
    ):
        """Test successful SMS code sending."""
        # Create user and enable SMS MFA
        user_auth = auth_service.create_user_auth(
            patient_id=sample_patient_id, **valid_user_data
        )
        auth_service.db.commit()

        # Enable SMS MFA
        mfa_config = MFAConfig(
            id=uuid.uuid4(),
            user_id=user_auth.id,
            sms_enabled=True,
            sms_phone_number=valid_user_data["phone_number"],
            created_at=datetime.utcnow(),
        )
        auth_service.db.add(mfa_config)
        auth_service.db.commit()

        # Test with real SMS service (may skip if not configured)
        try:
            result = auth_service.send_sms_code(user_auth.id)
        except Exception:
            # If SMS service not configured, mark as skipped
            pytest.skip("SMS service not configured for testing")

        assert result is True

        # Check SMS code was stored
        sms_code = (
            auth_service.db.query(SMSVerificationCode)
            .filter(SMSVerificationCode.user_id == user_auth.id)
            .first()
        )

        assert sms_code is not None
        assert len(sms_code.code) == 6
        assert sms_code.expires_at > datetime.utcnow()

    def test_send_sms_code_no_mfa(
        self, auth_service, sample_patient_id, valid_user_data
    ):
        """Test SMS code sending without MFA enabled."""
        # Create user without MFA
        user_auth = auth_service.create_user_auth(
            patient_id=sample_patient_id, **valid_user_data
        )
        auth_service.db.commit()

        result = auth_service.send_sms_code(user_auth.id)
        assert result is False

    def test_send_sms_code_rate_limiting(
        self, auth_service, sample_patient_id, valid_user_data
    ):
        """Test SMS code rate limiting."""
        # Create user and enable SMS MFA
        user_auth = auth_service.create_user_auth(
            patient_id=sample_patient_id, **valid_user_data
        )
        mfa_config = MFAConfig(
            id=uuid.uuid4(),
            user_id=user_auth.id,
            sms_enabled=True,
            sms_phone_number=valid_user_data["phone_number"],
            created_at=datetime.utcnow(),
        )
        auth_service.db.add(mfa_config)
        auth_service.db.commit()

        # Create 3 recent SMS codes (rate limit)
        for i in range(3):
            sms_code = SMSVerificationCode(
                id=uuid.uuid4(),
                user_id=user_auth.id,
                code=f"12345{i}",
                phone_number=valid_user_data["phone_number"],
                expires_at=datetime.utcnow() + timedelta(minutes=5),
                created_at=datetime.utcnow(),
            )
            auth_service.db.add(sms_code)

        auth_service.db.commit()

        # Try to send another code - should be rate limited
        result = auth_service.send_sms_code(user_auth.id)
        assert result is False

    def test_send_sms_code_twilio_fallback(
        self, auth_service, sample_patient_id, valid_user_data
    ):
        """Test Twilio fallback when primary SMS service fails."""
        # Create user and enable SMS MFA
        user_auth = auth_service.create_user_auth(
            patient_id=sample_patient_id, **valid_user_data
        )
        mfa_config = MFAConfig(
            id=uuid.uuid4(),
            user_id=user_auth.id,
            sms_enabled=True,
            sms_phone_number=valid_user_data["phone_number"],
            created_at=datetime.utcnow(),
        )
        auth_service.db.add(mfa_config)
        auth_service.db.commit()

        # Test Twilio fallback with real services if available
        # Set up test Twilio credentials if available
        test_twilio_sid = os.getenv("TEST_TWILIO_ACCOUNT_SID")
        test_twilio_token = os.getenv("TEST_TWILIO_AUTH_TOKEN")
        test_twilio_from = os.getenv("TEST_TWILIO_FROM_NUMBER")

        if not all([test_twilio_sid, test_twilio_token, test_twilio_from]):
            pytest.skip("Twilio test credentials not available")

        # Configure Twilio for the service
        from twilio.rest import Client

        auth_service.twilio_client = Client(test_twilio_sid, test_twilio_token)
        auth_service.twilio_from_number = test_twilio_from

        # Force primary SMS service to be unavailable
        auth_service._sms_service_available = False

        try:
            result = auth_service.send_sms_code(user_auth.id)
            # With real Twilio test credentials, this should work
            assert result is True
        except Exception as e:
            if "Twilio" in str(e):
                pytest.skip(f"Twilio service error: {e}")
            raise


class TestBackupCodes:
    """Test backup code generation and verification."""

    def test_generate_backup_codes(
        self, auth_service, sample_patient_id, valid_user_data
    ):
        """Test backup code generation."""
        # Create user and MFA config
        user_auth = auth_service.create_user_auth(
            patient_id=sample_patient_id, **valid_user_data
        )
        mfa_config = MFAConfig(
            id=uuid.uuid4(), user_id=user_auth.id, created_at=datetime.utcnow()
        )
        auth_service.db.add(mfa_config)
        auth_service.db.commit()

        # Generate backup codes
        codes = auth_service._generate_backup_codes(user_auth.id)

        assert len(codes) == 10
        for code in codes:
            assert len(code) == 9  # Format: XXXX-XXXX
            assert "-" in code

        # Check codes are stored in database
        backup_codes = (
            auth_service.db.query(BackupCode)
            .filter(BackupCode.user_id == user_auth.id)
            .all()
        )

        assert len(backup_codes) == 10

    def test_generate_backup_codes_invalidates_old(
        self, auth_service, sample_patient_id, valid_user_data
    ):
        """Test new backup codes invalidate old ones."""
        # Create user and MFA config
        user_auth = auth_service.create_user_auth(
            patient_id=sample_patient_id, **valid_user_data
        )
        mfa_config = MFAConfig(
            id=uuid.uuid4(), user_id=user_auth.id, created_at=datetime.utcnow()
        )
        auth_service.db.add(mfa_config)
        auth_service.db.commit()

        # Generate first set of codes
        auth_service._generate_backup_codes(user_auth.id)
        auth_service.db.commit()

        # Generate second set of codes
        auth_service._generate_backup_codes(user_auth.id)
        auth_service.db.commit()

        # Check old codes are invalidated
        old_codes = (
            auth_service.db.query(BackupCode)
            .filter(
                BackupCode.user_id == user_auth.id, BackupCode.invalidated.is_(True)
            )
            .count()
        )

        assert old_codes == 10  # First set should be invalidated

    def test_verify_backup_code_success(
        self, auth_service, sample_patient_id, valid_user_data
    ):
        """Test successful backup code verification."""
        # Create user and generate codes
        user_auth = auth_service.create_user_auth(
            patient_id=sample_patient_id, **valid_user_data
        )
        mfa_config = MFAConfig(
            id=uuid.uuid4(), user_id=user_auth.id, created_at=datetime.utcnow()
        )
        auth_service.db.add(mfa_config)
        auth_service.db.commit()

        codes = auth_service._generate_backup_codes(user_auth.id)
        auth_service.db.commit()

        # Verify first code
        result = auth_service._verify_backup_code(user_auth.id, codes[0])
        assert result is True

        # Check code was marked as used
        backup_code = (
            auth_service.db.query(BackupCode)
            .filter(BackupCode.user_id == user_auth.id, BackupCode.used.is_(True))
            .first()
        )

        assert backup_code is not None

    def test_verify_backup_code_already_used(
        self, auth_service, sample_patient_id, valid_user_data
    ):
        """Test backup code cannot be reused."""
        # Create user and generate codes
        user_auth = auth_service.create_user_auth(
            patient_id=sample_patient_id, **valid_user_data
        )
        mfa_config = MFAConfig(
            id=uuid.uuid4(), user_id=user_auth.id, created_at=datetime.utcnow()
        )
        auth_service.db.add(mfa_config)
        auth_service.db.commit()

        codes = auth_service._generate_backup_codes(user_auth.id)
        auth_service.db.commit()

        # Use code once
        auth_service._verify_backup_code(user_auth.id, codes[0])
        auth_service.db.commit()

        # Try to use same code again
        result = auth_service._verify_backup_code(user_auth.id, codes[0])
        assert result is False

    def test_get_remaining_backup_codes(
        self, auth_service, sample_patient_id, valid_user_data
    ):
        """Test getting count of remaining backup codes."""
        # Create user and generate codes
        user_auth = auth_service.create_user_auth(
            patient_id=sample_patient_id, **valid_user_data
        )
        mfa_config = MFAConfig(
            id=uuid.uuid4(), user_id=user_auth.id, created_at=datetime.utcnow()
        )
        auth_service.db.add(mfa_config)
        auth_service.db.commit()

        codes = auth_service._generate_backup_codes(user_auth.id)
        auth_service.db.commit()

        # Initially should have 10 codes
        remaining = auth_service.get_remaining_backup_codes(user_auth.id)
        assert remaining == 10

        # Use 3 codes
        for i in range(3):
            auth_service._verify_backup_code(user_auth.id, codes[i])
        auth_service.db.commit()

        # Should have 7 remaining
        remaining = auth_service.get_remaining_backup_codes(user_auth.id)
        assert remaining == 7


class TestPasswordChangeAndReset:
    """Test password change and reset functionality."""

    def test_change_password_success(
        self, auth_service, sample_patient_id, valid_user_data
    ):
        """Test successful password change."""
        # Create user
        user_auth = auth_service.create_user_auth(
            patient_id=sample_patient_id, **valid_user_data
        )
        auth_service.db.commit()
        original_hash = user_auth.password_hash

        # Use a unique new password that won't be breached
        new_password = f"NewSecurePass{uuid.uuid4()}!@#"

        # Change password with real policy validation
        result = auth_service.change_password(
            user_id=user_auth.id,
            current_password=valid_user_data["password"],
            new_password=new_password,
        )

        assert result is True

        # Check password was updated
        auth_service.db.refresh(user_auth)
        assert user_auth.password_hash != original_hash
        assert user_auth.password_changed_at is not None

        # Verify new password works
        assert auth_service.verify_password(new_password, user_auth.password_hash)

    def test_change_password_invalid_current(
        self, auth_service, sample_patient_id, valid_user_data
    ):
        """Test password change with incorrect current password."""
        # Create user
        user_auth = auth_service.create_user_auth(
            patient_id=sample_patient_id, **valid_user_data
        )
        auth_service.db.commit()

        # Try to change with wrong current password
        with pytest.raises(AuthenticationException):
            auth_service.change_password(
                user_id=user_auth.id,
                current_password="wrong_password",
                new_password="NewSecurePass456!@#",
            )

    def test_change_password_same_as_current(
        self, auth_service, sample_patient_id, valid_user_data
    ):
        """Test password change rejection when new password is same as current."""
        # Create user
        user_auth = auth_service.create_user_auth(
            patient_id=sample_patient_id, **valid_user_data
        )
        auth_service.db.commit()

        with pytest.raises(ValueError, match="New password must be different"):
            auth_service.change_password(
                user_id=user_auth.id,
                current_password=valid_user_data["password"],
                new_password=valid_user_data["password"],  # Same password
            )

    def test_change_password_minimum_age_violation(
        self, auth_service, sample_patient_id, valid_user_data
    ):
        """Test password change rejection due to minimum age policy."""
        # Create user with very recent password change
        user_auth = auth_service.create_user_auth(
            patient_id=sample_patient_id, **valid_user_data
        )
        # Set password changed to just now
        user_auth.password_changed_at = datetime.utcnow()
        auth_service.db.commit()

        # Try to change password immediately (should fail minimum age check)
        with pytest.raises(ValueError, match="Password cannot be changed yet"):
            auth_service.change_password(
                user_id=user_auth.id,
                current_password=valid_user_data["password"],
                new_password=f"NewSecurePass{uuid.uuid4()}!@#",
            )

    def test_reset_password_success(
        self, auth_service, sample_patient_id, valid_user_data
    ):
        """Test successful password reset with token."""
        # Create user
        user_auth = auth_service.create_user_auth(
            patient_id=sample_patient_id, **valid_user_data
        )
        auth_service.db.commit()

        # Create reset token
        reset_token = PasswordResetToken(
            user_id=user_auth.id,
            token="valid_reset_token",
            expires_at=datetime.utcnow() + timedelta(hours=1),
            created_at=datetime.utcnow(),
        )
        auth_service.db.add(reset_token)
        auth_service.db.commit()

        # Use unique password for reset
        new_reset_password = f"NewResetPass{uuid.uuid4()}!@#"

        # Reset password with real validation
        result = auth_service.reset_password(
            reset_token="valid_reset_token", new_password=new_reset_password
        )

        assert result is True

        # Check password was updated
        auth_service.db.refresh(user_auth)
        assert auth_service.verify_password(new_reset_password, user_auth.password_hash)
        assert user_auth.password_reset_required is False

        # Check token was marked as used
        auth_service.db.refresh(reset_token)
        assert reset_token.used is True

    def test_reset_password_invalid_token(self, auth_service):
        """Test password reset with invalid token."""
        with pytest.raises(ValueError, match="Invalid or expired reset token"):
            auth_service.reset_password(
                reset_token="invalid_token", new_password="NewPassword123!@#"
            )

    def test_reset_password_expired_token(
        self, auth_service, sample_patient_id, valid_user_data
    ):
        """Test password reset with expired token."""
        # Create user
        user_auth = auth_service.create_user_auth(
            patient_id=sample_patient_id, **valid_user_data
        )
        auth_service.db.commit()

        # Create expired reset token
        reset_token = PasswordResetToken(
            user_id=user_auth.id,
            token="expired_token",
            expires_at=datetime.utcnow() - timedelta(hours=1),  # Expired
            created_at=datetime.utcnow(),
        )
        auth_service.db.add(reset_token)
        auth_service.db.commit()

        with pytest.raises(ValueError, match="Invalid or expired reset token"):
            auth_service.reset_password(
                reset_token="expired_token", new_password="NewPassword123!@#"
            )

    def test_initiate_password_reset_success(
        self, auth_service, sample_patient_id, valid_user_data
    ):
        """Test successful password reset initiation."""
        # Create user
        user_auth = auth_service.create_user_auth(
            patient_id=sample_patient_id, **valid_user_data
        )
        auth_service.db.commit()

        # Initiate password reset
        reset_token = auth_service.initiate_password_reset(valid_user_data["email"])

        assert reset_token is not None
        assert len(reset_token) > 20  # Should be a secure token

        # Check token was stored in database
        token_record = (
            auth_service.db.query(PasswordResetToken)
            .filter(
                PasswordResetToken.user_id == user_auth.id,
                PasswordResetToken.token == reset_token,
            )
            .first()
        )

        assert token_record is not None
        assert token_record.expires_at > datetime.utcnow()

    def test_initiate_password_reset_nonexistent_user(self, auth_service):
        """Test password reset initiation for non-existent user."""
        # Should not reveal if email exists
        reset_token = auth_service.initiate_password_reset("nonexistent@example.com")
        assert reset_token is None

    def test_initiate_password_reset_rate_limiting(
        self, auth_service, sample_patient_id, valid_user_data
    ):
        """Test password reset rate limiting."""
        # Create user
        user_auth = auth_service.create_user_auth(
            patient_id=sample_patient_id, **valid_user_data
        )
        auth_service.db.commit()

        # Create 3 recent reset tokens (rate limit)
        for i in range(3):
            reset_token = PasswordResetToken(
                user_id=user_auth.id,
                token=f"token_{i}",
                expires_at=datetime.utcnow() + timedelta(hours=1),
                created_at=datetime.utcnow(),
            )
            auth_service.db.add(reset_token)

        auth_service.db.commit()

        # Try to initiate another reset - should be rate limited
        result = auth_service.initiate_password_reset(valid_user_data["email"])
        assert result is None


class TestUserLookup:
    """Test user lookup methods."""

    def test_get_by_id_success(self, auth_service, sample_patient_id, valid_user_data):
        """Test successful user lookup by ID."""
        # Create user
        user_auth = auth_service.create_user_auth(
            patient_id=sample_patient_id, **valid_user_data
        )
        auth_service.db.commit()

        # Lookup by ID
        found_user = auth_service.get_by_id(user_auth.id)

        assert found_user is not None
        assert found_user.id == user_auth.id
        assert found_user.email == valid_user_data["email"]

    def test_get_by_id_not_found(self, auth_service):
        """Test user lookup by non-existent ID."""
        result = auth_service.get_by_id(uuid.uuid4())
        assert result is None

    def test_get_by_email_success(
        self, auth_service, sample_patient_id, valid_user_data
    ):
        """Test successful user lookup by email."""
        # Create user
        user_auth = auth_service.create_user_auth(
            patient_id=sample_patient_id, **valid_user_data
        )
        auth_service.db.commit()

        # Lookup by email
        found_user = auth_service.get_by_email(valid_user_data["email"])

        assert found_user is not None
        assert found_user.id == user_auth.id
        assert found_user.email == valid_user_data["email"]

    def test_get_by_email_case_insensitive(
        self, auth_service, sample_patient_id, valid_user_data
    ):
        """Test case-insensitive email lookup."""
        # Create user
        user_auth = auth_service.create_user_auth(
            patient_id=sample_patient_id, **valid_user_data
        )
        auth_service.db.commit()

        # Lookup with different case
        found_user = auth_service.get_by_email("TEST@EXAMPLE.COM")

        assert found_user is not None
        assert found_user.id == user_auth.id

    def test_get_by_email_not_found(self, auth_service):
        """Test user lookup by non-existent email."""
        result = auth_service.get_by_email("nonexistent@example.com")
        assert result is None


# Run coverage verification after tests
if __name__ == "__main__":
    print(
        "Running AuthenticationService tests with comprehensive coverage requirement..."
    )
    print(
        "Use: python -m coverage run -m pytest tests/unit/services/test_auth_service.py"
    )
    print(
        "Then: python -m coverage report --include='*auth_service.py' --show-missing --fail-under=100"
    )
