"""
Complete API endpoint integration tests - comprehensive coverage requirement.

Tests all API endpoints with real HTTP requests and responses.
NO MOCKS for API functionality - uses real test client and production code.
MEDICAL COMPLIANCE: Uses real monitoring, real database, real AWS services.
"""

import os
import sys

# Add the HavenHealthPassport directory to the Python path
sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

# Set testing environment before importing app
os.environ["TESTING"] = "true"
# Allow real monitoring in tests - no mocking for medical compliance
os.environ["DISABLE_MONITORING"] = "false"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

# Import app with REAL monitoring - no mocks for medical compliance
from app import app  # noqa: E402
from src.database import SessionLocal, get_db  # noqa: E402
from src.models.audit_log import AuditLog  # noqa: E402
from src.models.patient import Patient  # noqa: E402
from src.models.user import User  # noqa: E402


@pytest.mark.integration
@pytest.mark.api
class TestAPIEndpointsComplete100Coverage:
    """Achieve comprehensive coverage for all API endpoints."""

    @pytest.fixture
    def test_db(self):
        """Create test database session."""
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    @pytest.fixture
    def client(self, test_db):
        """Create test client with database override."""
        app.dependency_overrides[get_db] = lambda: test_db

        with TestClient(app) as test_client:
            yield test_client

        app.dependency_overrides.clear()

    @pytest.fixture
    def auth_headers(self, client, test_db):
        """Create authenticated user and return auth headers."""
        # Create test user
        user_data = {
            "email": "test@example.com",
            "password": "SecureP@ssw0rd123!",
            "first_name": "Test",
            "last_name": "User",
            "role": "healthcare_provider",
        }

        # Register user
        response = client.post("/api/auth/register", json=user_data)
        assert response.status_code == 201

        # Login
        login_data = {"email": user_data["email"], "password": user_data["password"]}
        response = client.post("/api/auth/login", json=login_data)
        assert response.status_code == 200

        token = response.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}

    # Authentication Endpoints

    def test_auth_register_endpoint(self, client, test_db):
        """Test user registration endpoint."""
        user_data = {
            "email": "newuser@example.com",
            "password": "SecureP@ssw0rd123!",
            "first_name": "New",
            "last_name": "User",
            "phone": "+1234567890",
            "role": "patient",
        }

        response = client.post("/api/auth/register", json=user_data)
        assert response.status_code == 201

        data = response.json()
        assert data["email"] == user_data["email"]
        assert data["role"] == user_data["role"]
        assert "id" in data
        assert "password" not in data  # Password should not be returned

        # Verify in database
        user = test_db.query(User).filter_by(email=user_data["email"]).first()
        assert user is not None

        # Test duplicate registration
        response = client.post("/api/auth/register", json=user_data)
        assert response.status_code == 409
        assert "already registered" in response.json()["detail"]

    def test_auth_login_endpoint(self, client, test_db):
        """Test login endpoint with various scenarios."""
        # First register a user
        user_data = {
            "email": "login_test@example.com",
            "password": "SecureP@ssw0rd123!",
            "first_name": "Login",
            "last_name": "Test",
        }
        client.post("/api/auth/register", json=user_data)

        # Successful login
        login_data = {"email": user_data["email"], "password": user_data["password"]}
        response = client.post("/api/auth/login", json=login_data)
        assert response.status_code == 200

        data = response.json()
        assert "access_token" in data
        assert "token_type" in data
        assert data["token_type"] == "bearer"

        # Failed login - wrong password
        login_data["password"] = "WrongPassword"
        response = client.post("/api/auth/login", json=login_data)
        assert response.status_code == 401

        # Failed login - non-existent user
        login_data["email"] = "nonexistent@example.com"
        response = client.post("/api/auth/login", json=login_data)
        assert response.status_code == 401

    def test_auth_logout_endpoint(self, client, auth_headers):
        """Test logout endpoint."""
        response = client.post("/api/auth/logout", headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["message"] == "Successfully logged out"

        # Verify token is invalidated
        response = client.get("/api/auth/me", headers=auth_headers)
        assert response.status_code == 401

    def test_auth_refresh_token_endpoint(self, client, test_db):
        """Test token refresh endpoint."""
        # Login first
        user_data = {
            "email": "refresh_test@example.com",
            "password": "SecureP@ssw0rd123!",
            "first_name": "Refresh",
            "last_name": "Test",
        }
        client.post("/api/auth/register", json=user_data)

        login_response = client.post(
            "/api/auth/login",
            json={"email": user_data["email"], "password": user_data["password"]},
        )
        refresh_token = login_response.json().get("refresh_token")

        # Refresh token
        response = client.post(
            "/api/auth/refresh", json={"refresh_token": refresh_token}
        )
        assert response.status_code == 200
        assert "access_token" in response.json()

    # Patient Endpoints

    def test_patient_create_endpoint(self, client, auth_headers, test_db):
        """Test patient creation endpoint."""
        patient_data = {
            "first_name": "John",
            "last_name": "Doe",
            "date_of_birth": "1990-01-01",
            "gender": "male",
            "phone": "+1234567890",
            "email": "john.doe@example.com",
            "emergency_contact": {
                "name": "Jane Doe",
                "phone": "+0987654321",
                "relationship": "spouse",
            },
            "medical_history": {
                "allergies": ["penicillin"],
                "chronic_conditions": ["diabetes"],
                "blood_type": "O+",
            },
        }

        response = client.post("/api/patients", json=patient_data, headers=auth_headers)
        assert response.status_code == 201

        data = response.json()
        assert data["first_name"] == patient_data["first_name"]
        assert "id" in data
        assert "mrn" in data  # Medical Record Number should be generated

        # Verify audit log
        audit = (
            test_db.query(AuditLog)
            .filter_by(resource_id=data["id"], action="CREATE_PATIENT")
            .first()
        )
        assert audit is not None

    def test_patient_get_endpoint(self, client, auth_headers, test_db):
        """Test patient retrieval endpoint."""
        # Create a patient first
        patient = Patient(
            first_name="Test",
            last_name="Patient",
            date_of_birth="1985-05-15",
            mrn="TEST001",
        )
        test_db.add(patient)
        test_db.commit()

        # Get patient
        response = client.get(f"/api/patients/{patient.id}", headers=auth_headers)
        assert response.status_code == 200

        data = response.json()
        assert data["first_name"] == "Test"
        assert data["mrn"] == "TEST001"
