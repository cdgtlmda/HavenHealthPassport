"""Test BackupCode validation functionality.

This test uses real database operations without mocks as required for medical compliance.
"""

import uuid
from datetime import date, datetime

import pytest

from src.models.auth import BackupCode, UserAuth, UserRole
from src.models.patient import Gender, Patient


@pytest.fixture
def db_patient(db_session):
    """Create a test patient."""
    patient = Patient(
        given_name="Coverage",
        family_name="Test",
        date_of_birth=date(1990, 1, 1),
        gender=Gender.MALE,
    )
    db_session.add(patient)
    db_session.commit()
    yield patient


@pytest.fixture
def db_user(db_session, db_patient):
    """Create a test user."""
    user = UserAuth(
        patient_id=db_patient.id,
        email="coverage@test.com",
        phone_number="+19999999999",
        password_hash="test_hash",
        role=UserRole.PATIENT,
        created_by=str(uuid.uuid4()),
    )
    db_session.add(user)
    db_session.commit()
    yield user


@pytest.mark.hipaa_required
def test_backup_code_is_valid_coverage(db_session, db_user):
    """Test BackupCode.is_valid() method to cover line 789."""
    # Create an unused backup code
    unused_code = BackupCode(user_id=db_user.id, code_hash="unused_code_hash_12345")
    db_session.add(unused_code)
    db_session.commit()

    assert unused_code.is_valid() is True

    # Create a used backup code
    used_code = BackupCode(
        user_id=db_user.id, code_hash="used_code_hash_67890", used_at=datetime.utcnow()
    )
    db_session.add(used_code)
    db_session.commit()

    # Test is_valid returns False for used code
    assert used_code.is_valid() is False

    # Verify we're testing real database records
    stored_unused = (
        db_session.query(BackupCode)
        .filter_by(code_hash="unused_code_hash_12345")
        .first()
    )
    assert stored_unused is not None
    assert stored_unused.is_valid() is True

    stored_used = (
        db_session.query(BackupCode).filter_by(code_hash="used_code_hash_67890").first()
    )
    assert stored_used is not None
    assert stored_used.is_valid() is False
