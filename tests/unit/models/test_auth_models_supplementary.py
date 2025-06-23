"""Supplementary tests for authentication models.

This file tests the remaining uncovered lines from test_auth_models.py
to ensure comprehensive test coverage for this security-critical file.

Uses real database operations without mocks as per medical compliance requirements.
"""

import uuid
from datetime import date, datetime, timedelta

import pytest

from src.models.auth import (
    BackupCode,
    PasswordResetToken,
    SMSVerificationCode,
    UserAuth,
    UserRole,
)
from src.models.patient import Gender, Patient


@pytest.fixture
def test_patient(db_session):
    """Create a test patient for user authentication."""
    patient = Patient(
        given_name="Test",
        family_name="Patient",
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
        email="test@example.com",
        phone_number="+1234567890",
        password_hash="$2b$12$test_hash",
        role=UserRole.PATIENT,
        created_by=str(uuid.uuid4()),
    )
    db_session.add(user_auth)
    db_session.commit()
    yield user_auth
    # Cleanup
    db_session.delete(user_auth)
    db_session.commit()


class TestPasswordResetTokenCoverage:
    """Test PasswordResetToken model functionality."""

    @pytest.mark.hipaa_required
    def test_password_reset_token_repr(self, db_session, test_user_auth):
        """Test PasswordResetToken string representation."""
        token = PasswordResetToken(
            user_id=test_user_auth.id,
            token="test_token_12345",
            expires_at=datetime.utcnow() + timedelta(hours=1),
        )
        db_session.add(token)
        db_session.commit()

        # Test __repr__ method
        repr_str = repr(token)
        assert f"user_id={test_user_auth.id}" in repr_str
        assert "expires_at=" in repr_str
        assert "<PasswordResetToken(" in repr_str

        # Cleanup
        db_session.delete(token)
        db_session.commit()

    @pytest.mark.hipaa_required
    def test_password_reset_token_is_valid(self, db_session, test_user_auth):
        """Test PasswordResetToken is_valid method."""
        # Test valid token
        valid_token = PasswordResetToken(
            user_id=test_user_auth.id,
            token="valid_token_12345",
            expires_at=datetime.utcnow() + timedelta(hours=1),
        )
        db_session.add(valid_token)
        db_session.commit()

        assert valid_token.is_valid() is True

        # Test used token
        used_token = PasswordResetToken(
            user_id=test_user_auth.id,
            token="used_token_12345",
            expires_at=datetime.utcnow() + timedelta(hours=1),
            used_at=datetime.utcnow(),
        )
        db_session.add(used_token)
        db_session.commit()

        assert used_token.is_valid() is False

        # Test expired token
        expired_token = PasswordResetToken(
            user_id=test_user_auth.id,
            token="expired_token_12345",
            expires_at=datetime.utcnow() - timedelta(hours=1),
        )
        db_session.add(expired_token)
        db_session.commit()

        assert expired_token.is_valid() is False

        # Cleanup
        db_session.delete(valid_token)
        db_session.delete(used_token)
        db_session.delete(expired_token)
        db_session.commit()


class TestSMSVerificationCodeCoverage:
    """Test SMSVerificationCode model functionality."""

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

        # Test __repr__ method
        repr_str = repr(code)
        assert "phone=+1234567890" in repr_str
        assert "purpose=registration" in repr_str
        assert "<SMSVerificationCode(" in repr_str

        # Cleanup
        db_session.delete(code)
        db_session.commit()

    @pytest.mark.hipaa_required
    def test_sms_verification_code_is_valid(self, db_session):
        """Test SMSVerificationCode is_valid method."""
        # Test valid code
        valid_code = SMSVerificationCode(
            phone_number="+1234567890",
            code="123456",
            purpose="login",
            expires_at=datetime.utcnow() + timedelta(minutes=10),
            attempts=0,
        )
        db_session.add(valid_code)
        db_session.commit()

        assert valid_code.is_valid() is True

        # Test verified code
        verified_code = SMSVerificationCode(
            phone_number="+1234567891",
            code="234567",
            purpose="login",
            expires_at=datetime.utcnow() + timedelta(minutes=10),
            attempts=0,
            verified_at=datetime.utcnow(),
        )
        db_session.add(verified_code)
        db_session.commit()

        assert verified_code.is_valid() is False

        # Test expired code
        expired_code = SMSVerificationCode(
            phone_number="+1234567892",
            code="345678",
            purpose="login",
            expires_at=datetime.utcnow() - timedelta(minutes=10),
            attempts=0,
        )
        db_session.add(expired_code)
        db_session.commit()

        assert expired_code.is_valid() is False

        # Test code with too many attempts
        too_many_attempts_code = SMSVerificationCode(
            phone_number="+1234567893",
            code="456789",
            purpose="login",
            expires_at=datetime.utcnow() + timedelta(minutes=10),
            attempts=3,
        )
        db_session.add(too_many_attempts_code)
        db_session.commit()

        assert too_many_attempts_code.is_valid() is False

        # Cleanup
        db_session.delete(valid_code)
        db_session.delete(verified_code)
        db_session.delete(expired_code)
        db_session.delete(too_many_attempts_code)
        db_session.commit()


class TestBackupCodeCoverage:
    """Test BackupCode model functionality."""

    @pytest.mark.hipaa_required
    def test_backup_code_repr(self, db_session, test_user_auth):
        """Test BackupCode string representation."""
        # Test unused code
        unused_code = BackupCode(
            user_id=test_user_auth.id, code_hash="hashed_backup_code_1"
        )
        db_session.add(unused_code)
        db_session.commit()

        repr_str = repr(unused_code)
        assert f"user_id={test_user_auth.id}" in repr_str
        assert "used=No" in repr_str
        assert "<BackupCode(" in repr_str

        # Test used code
        used_code = BackupCode(
            user_id=test_user_auth.id,
            code_hash="hashed_backup_code_2",
            used_at=datetime.utcnow(),
        )
        db_session.add(used_code)
        db_session.commit()

        repr_str_used = repr(used_code)
        assert f"user_id={test_user_auth.id}" in repr_str_used
        assert "used=Yes" in repr_str_used

        # Cleanup
        db_session.delete(unused_code)
        db_session.delete(used_code)
        db_session.commit()

    @pytest.mark.hipaa_required
    def test_backup_code_is_valid(self, db_session, test_user_auth):
        """Test BackupCode is_valid method."""
        # Test valid (unused) code
        valid_code = BackupCode(
            user_id=test_user_auth.id, code_hash="hashed_backup_code_valid"
        )
        db_session.add(valid_code)
        db_session.commit()

        assert valid_code.is_valid() is True

        # Test invalid (used) code
        used_code = BackupCode(
            user_id=test_user_auth.id,
            code_hash="hashed_backup_code_used",
            used_at=datetime.utcnow(),
        )
        db_session.add(used_code)
        db_session.commit()

        assert used_code.is_valid() is False

        # Cleanup
        db_session.delete(valid_code)
        db_session.delete(used_code)
        db_session.commit()
