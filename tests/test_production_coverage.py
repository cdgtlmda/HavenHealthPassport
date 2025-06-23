"""Test that properly imports production code DURING test execution for coverage."""

import os

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.auth.password_policy import default_password_policy
from src.database import Base
from src.services.auth_service import AuthenticationService


@pytest.fixture
def real_db_session():
    """Create real database session for production code testing."""
    # Use in-memory SQLite for testing
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)

    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()

    yield db

    db.close()


def test_auth_service_coverage(db_session):  # noqa: F811
    """Import and test production code during test execution, not collection."""
    # Set environment variables needed by production code
    os.environ["JWT_SECRET_KEY"] = "test-secret-key-for-testing"
    os.environ["FERNET_KEY"] = "zH8F0WgeF-xyaGdG0XrNwkLq1RwSJHPFanJq3LgQTfY="

    # Test 1: Create AuthenticationService instance with real database (executes __init__)
    auth_service = AuthenticationService(db_session)
    assert auth_service is not None
    assert auth_service.db is db_session

    # Test 2: Execute password policy validation
    validation_result = default_password_policy.validate_password("WeakPass")
    assert validation_result["valid"] is False  # Weak password should fail
    assert len(validation_result["errors"]) > 0

    validation_result = default_password_policy.validate_password("StrongPass123!@#")
    assert validation_result["valid"] is True  # Strong password should pass

    # Test 3: Execute password hashing function from auth service
    test_password = "TestPassword123!@#"
    hashed = auth_service.hash_password(test_password)
    assert hashed != test_password
    assert auth_service.verify_password(test_password, hashed) is True

    print("✅ Successfully tested production code with REAL database")
    print("   - AuthenticationService initialized with real DB session")
    print("   - Password policy validated with real validation logic")
    print("   - Password hashing and verification tested with real cryptography")
