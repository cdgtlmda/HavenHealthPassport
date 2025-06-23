"""Additional tests for authentication models."""

import uuid
from datetime import date, datetime

import pytest

from src.models.auth import BackupCode, UserAuth, UserRole
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
    db_session.delete(user_auth)
    db_session.commit()


@pytest.mark.hipaa_required
def test_backup_code_is_valid_final(db_session, test_user_auth):
    """Test BackupCode validation method."""
    # Test valid (unused) code
    valid_code = BackupCode(user_id=test_user_auth.id, code_hash="test_valid_code_hash")
    db_session.add(valid_code)
    db_session.commit()

    # Test is_valid returns True for unused code
    assert valid_code.is_valid() is True

    # Test invalid (used) code
    used_code = BackupCode(
        user_id=test_user_auth.id,
        code_hash="test_used_code_hash",
        used_at=datetime.utcnow(),
    )
    db_session.add(used_code)
    db_session.commit()

    # Test is_valid returns False for used code
    assert used_code.is_valid() is False

    # Cleanup
    db_session.delete(valid_code)
    db_session.delete(used_code)
    db_session.commit()
