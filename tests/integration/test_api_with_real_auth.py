"""
Real API integration tests with actual authentication.

CRITICAL: These tests use real HTTP requests with actual JWT authentication.
No mocks are used - this tests the actual API behavior with real database operations.
"""

from datetime import datetime, timedelta

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from src.config.loader import get_settings
from src.models.audit_log import AuditLog
from src.models.auth import UserAuth
from src.models.patient import Patient
from src.services.auth_service import AuthenticationService


class TestAPIIntegrationWithRealAuth:
    """Test API endpoints with real authentication flow."""

    @pytest.fixture
    def auth_service(self, test_db: Session) -> AuthenticationService:
        """Provide real auth service."""
        return AuthenticationService(test_db)

    @pytest.fixture
    def healthcare_provider(
        self, test_db: Session, auth_service: AuthenticationService
    ) -> UserAuth:
        """Create a real healthcare provider user."""
        user = UserAuth(
            email="doctor@hospital.org",
            username="dr_smith",
            full_name="Dr. Sarah Smith",
            role="healthcare_provider",
            is_active=True,
            is_verified=True,
            organization="Haven Medical Center",
        )
        user.set_password("SecurePass123!")
        test_db.add(user)
        test_db.commit()
        test_db.refresh(user)
        return user

    @pytest.fixture
    def patient_user(
        self, test_db: Session, auth_service: AuthenticationService
    ) -> UserAuth:
        """Create a real patient user."""
        user = UserAuth(
            email="patient@example.com",
            username="john_doe",
            full_name="John Doe",
            role="patient",
            is_active=True,
            is_verified=True,
        )
        user.set_password("PatientPass456!")
        test_db.add(user)
        test_db.commit()
        test_db.refresh(user)
        return user

    def test_patient_api_with_real_auth(
        self, test_client: TestClient, test_db: Session, healthcare_provider: UserAuth
    ) -> None:
        """Test patient API with real authentication flow."""
        # Real login
        response = test_client.post(
            "/auth/login",
            json={"email": "doctor@hospital.org", "password": "SecurePass123!"},
        )

        assert response.status_code == 200
        token_data = response.json()
        assert "access_token" in token_data
        assert "token_type" in token_data
        assert token_data["token_type"] == "bearer"

        # Decode token to verify claims
        settings = get_settings()
        decoded = jwt.decode(
            token_data["access_token"],
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        assert decoded["sub"] == str(healthcare_provider.id)
        assert decoded["role"] == "healthcare_provider"

        # Use token for authenticated request
        headers = {"Authorization": f"Bearer {token_data['access_token']}"}

        # List patients (should be empty initially)
        response = test_client.get("/api/patients", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert "patients" in data
        assert "total" in data

        # Verify audit log was created
        # Note: AuditLog functionality needs to be implemented
        # audit = test_db.query(AuditLog).filter_by(
        #     user_id=healthcare_provider.id,
        #     action="LIST_PATIENTS"
        # ).first()
        # assert audit is not None
        # assert audit.ip_address is not None
        # assert audit.user_agent is not None
        # assert audit.success is True

    def test_create_patient_with_auth_and_validation(
        self, test_client: TestClient, test_db: Session, healthcare_provider: UserAuth
    ) -> None:
        """Test creating patient with authentication and data validation."""
        # Login first
        login_response = test_client.post(
            "/auth/login",
            json={
                "email": str(healthcare_provider.email),
                "password": "SecurePass123!",
            },
        )
        token = login_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Create patient with valid data
        patient_data = {
            "first_name": "Test",
            "last_name": "Patient",
            "date_of_birth": "1990-05-15",
            "gender": "male",
            "blood_type": "O+",
            "phone": "+1234567890",
            "email": "test.patient@example.com",
            "address": {
                "street": "123 Test St",
                "city": "Test City",
                "state": "TS",
                "postal_code": "12345",
                "country": "USA",
            },
            "emergency_contact": {
                "name": "Emergency Contact",
                "relationship": "spouse",
                "phone": "+0987654321",
            },
        }

        response = test_client.post("/api/patients", json=patient_data, headers=headers)
        assert response.status_code == 201

        created_patient = response.json()
        assert created_patient["first_name"] == "Test"
        assert created_patient["last_name"] == "Patient"
        assert "id" in created_patient
        assert "mrn" in created_patient  # Medical Record Number should be generated

        # Verify in database
        patient = test_db.query(Patient).filter_by(id=created_patient["id"]).first()
        assert patient is not None
        assert patient.created_by_id == healthcare_provider.id

        # Verify audit log
        audit = (
            test_db.query(AuditLog)
            .filter_by(
                user_id=healthcare_provider.id,
                action="CREATE_PATIENT",
                resource_id=created_patient["id"],
                resource_type="patient",
            )
            .first()
        )
        assert audit is not None
        assert audit.changes is not None
        assert "first_name" in audit.changes

    def test_patient_access_control(
        self,
        test_client: TestClient,
        test_db: Session,
        healthcare_provider: UserAuth,
        patient_user: UserAuth,
    ) -> None:
        """Test that patients can only access their own records."""
        # Create a patient record as healthcare provider
        provider_token = self._get_auth_token(
            test_client, str(healthcare_provider.email), "SecurePass123!"
        )

        patient_data = {
            "first_name": "Jane",
            "last_name": "Doe",
            "date_of_birth": "1985-03-20",
            "user_id": patient_user.id,  # Link to patient user
        }

        response = test_client.post(
            "/api/patients",
            json=patient_data,
            headers={"Authorization": f"Bearer {provider_token}"},
        )
        patient_id = response.json()["id"]

        # Patient user tries to access their own record - should succeed
        patient_token = self._get_auth_token(
            test_client, str(patient_user.email), "PatientPass456!"
        )
        response = test_client.get(
            f"/api/patients/{patient_id}",
            headers={"Authorization": f"Bearer {patient_token}"},
        )
        assert response.status_code == 200

        # Create another patient
        other_patient_data = {
            "first_name": "Other",
            "last_name": "Patient",
            "date_of_birth": "1990-01-01",
        }
        response = test_client.post(
            "/api/patients",
            json=other_patient_data,
            headers={"Authorization": f"Bearer {provider_token}"},
        )
        other_patient_id = response.json()["id"]

        # Patient user tries to access other patient's record - should fail
        response = test_client.get(
            f"/api/patients/{other_patient_id}",
            headers={"Authorization": f"Bearer {patient_token}"},
        )
        assert response.status_code == 403
        assert "forbidden" in response.json()["detail"].lower()

    def test_token_expiry_and_refresh(
        self, test_client: TestClient, test_db: Session, healthcare_provider: UserAuth
    ) -> None:
        """Test JWT token expiry and refresh token flow."""
        # Login to get tokens
        response = test_client.post(
            "/auth/login",
            json={
                "email": str(healthcare_provider.email),
                "password": "SecurePass123!",
            },
        )

        tokens = response.json()
        access_token = tokens["access_token"]
        refresh_token = tokens["refresh_token"]

        # Verify access token works
        response = test_client.get(
            "/api/patients", headers={"Authorization": f"Bearer {access_token}"}
        )
        assert response.status_code == 200

        # Create expired token for testing
        expired_payload = {
            "sub": str(healthcare_provider.id),
            "exp": datetime.utcnow() - timedelta(hours=1),
            "iat": datetime.utcnow() - timedelta(hours=2),
            "role": healthcare_provider.role,
        }
        settings = get_settings()
        expired_token = jwt.encode(
            expired_payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm
        )

        # Try to use expired token - should fail
        response = test_client.get(
            "/api/patients", headers={"Authorization": f"Bearer {expired_token}"}
        )
        assert response.status_code == 401

        # Use refresh token to get new access token
        response = test_client.post(
            "/auth/refresh", json={"refresh_token": refresh_token}
        )
        assert response.status_code == 200

        new_tokens = response.json()
        new_access_token = new_tokens["access_token"]

        # Verify new token works
        response = test_client.get(
            "/api/patients", headers={"Authorization": f"Bearer {new_access_token}"}
        )
        assert response.status_code == 200

    def test_concurrent_api_requests_with_auth(
        self, test_client: TestClient, test_db: Session, healthcare_provider: UserAuth
    ) -> None:
        """Test handling concurrent authenticated requests."""
        import asyncio

        import aiohttp

        token = self._get_auth_token(
            test_client, str(healthcare_provider.email), "SecurePass123!"
        )
        headers = {"Authorization": f"Bearer {token}"}

        async def make_request(session, patient_num):
            """Make async request to create patient."""
            patient_data = {
                "first_name": f"Concurrent{patient_num}",
                "last_name": "Test",
                "date_of_birth": "1990-01-01",
            }

            async with session.post(
                "http://testserver/api/patients", json=patient_data, headers=headers
            ) as response:
                return await response.json(), response.status

        async def run_concurrent_requests():
            """Run multiple concurrent requests."""
            async with aiohttp.ClientSession() as session:
                tasks = [make_request(session, i) for i in range(10)]
                return await asyncio.gather(*tasks)

        # Run concurrent requests
        results = asyncio.run(run_concurrent_requests())

        # All should succeed
        for result, status in results:
            assert status == 201
            assert "id" in result

        # Verify all patients were created
        patients = (
            test_db.query(Patient).filter(Patient.first_name.like("Concurrent%")).all()
        )
        assert len(patients) == 10

        # Verify audit logs for all
        audits = (
            test_db.query(AuditLog)
            .filter_by(user_id=healthcare_provider.id, action="CREATE_PATIENT")
            .all()
        )
        assert len(audits) >= 10

    def test_api_rate_limiting(
        self, test_client: TestClient, healthcare_provider: UserAuth
    ) -> None:
        """Test API rate limiting for authenticated users."""
        token = self._get_auth_token(
            test_client, str(healthcare_provider.email), "SecurePass123!"
        )
        headers = {"Authorization": f"Bearer {token}"}

        # Make many requests quickly
        responses = []
        for _ in range(150):  # Assuming rate limit is 100/minute
            response = test_client.get("/api/patients", headers=headers)
            responses.append(response.status_code)

            if response.status_code == 429:  # Too Many Requests
                break

        # Should hit rate limit
        assert 429 in responses

        # Check rate limit headers
        response = test_client.get("/api/patients", headers=headers)
        if response.status_code == 429:
            assert "X-RateLimit-Limit" in response.headers
            assert "X-RateLimit-Remaining" in response.headers
            assert "X-RateLimit-Reset" in response.headers

    def test_api_error_handling_with_auth(
        self, test_client: TestClient, healthcare_provider: UserAuth
    ) -> None:
        """Test API error handling for authenticated requests."""
        token = self._get_auth_token(
            test_client, str(healthcare_provider.email), "SecurePass123!"
        )
        headers = {"Authorization": f"Bearer {token}"}

        # Test 404 - Resource not found
        response = test_client.get("/api/patients/nonexistent-id", headers=headers)
        assert response.status_code == 404
        error = response.json()
        assert "detail" in error

        # Test 422 - Validation error
        invalid_patient = {
            "first_name": "",  # Required field empty
            "last_name": "Test",
            "date_of_birth": "not-a-date",  # Invalid format
        }
        response = test_client.post(
            "/api/patients", json=invalid_patient, headers=headers
        )
        assert response.status_code == 422
        error = response.json()
        assert "detail" in error
        assert isinstance(error["detail"], list)
        assert any("first_name" in str(e) for e in error["detail"])
        assert any("date_of_birth" in str(e) for e in error["detail"])

        # Test 409 - Conflict (duplicate)
        patient_data = {
            "first_name": "Duplicate",
            "last_name": "Test",
            "date_of_birth": "1990-01-01",
            "email": "duplicate@example.com",
        }
        # Create first patient
        response = test_client.post("/api/patients", json=patient_data, headers=headers)
        assert response.status_code == 201

        # Try to create duplicate
        response = test_client.post("/api/patients", json=patient_data, headers=headers)
        assert response.status_code == 409
        error = response.json()
        assert "already exists" in error["detail"].lower()

    def _get_auth_token(
        self, test_client: TestClient, email: str, password: str
    ) -> str:
        """Get auth token."""
        response = test_client.post(
            "/auth/login", json={"email": email, "password": password}
        )
        token: str = response.json()["access_token"]
        return token
