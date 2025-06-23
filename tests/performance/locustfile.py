"""
Real load testing for Haven Health Passport with actual services.

CRITICAL: These tests create real load on actual services including:
- Real database operations with encryption
- Real authentication with JWT tokens
- Real file uploads to S3
- Real FHIR validation
- Real audit trail creation

This is used to verify the system can handle refugee camp scenarios
with hundreds of simultaneous registrations.
"""

import base64
import os
import random
import time

from faker import Faker
from locust import HttpUser, between, events, task

fake = Faker()

# Test configuration
BASE_URL = os.getenv("LOAD_TEST_URL", "http://localhost:8000")
TEST_USERS = [
    {"email": "loadtest1@example.com", "password": "LoadTest123!"},
    {"email": "loadtest2@example.com", "password": "LoadTest123!"},
    {"email": "loadtest3@example.com", "password": "LoadTest123!"},
    {"email": "loadtest4@example.com", "password": "LoadTest123!"},
    {"email": "loadtest5@example.com", "password": "LoadTest123!"},
]

# Generate test document (small PDF)
TEST_DOCUMENT = base64.b64encode(
    b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n3 0 obj\n<< /Type /Page /Parent 2 0 R /Resources << >> /MediaBox [0 0 612 792] >>\nendobj\nxref\n0 4\n0000000000 65535 f\n0000000009 00000 n\n0000000058 00000 n\n0000000115 00000 n\ntrailer\n<< /Size 4 /Root 1 0 R >>\nstartxref\n205\n%%EOF"
).decode()


class PatientLoadTest(HttpUser):
    """Load test for patient registration and operations."""

    wait_time = between(1, 3)  # Simulate real user think time

    def __init__(self, *args, **kwargs):
        """Initialize the performance test user."""
        super().__init__(*args, **kwargs)
        self.token = None
        self.user_data = None
        self.created_patients = []

    def on_start(self):
        """Login before starting tasks."""
        # Select random test user
        self.user_data = random.choice(TEST_USERS)

        # Real authentication
        response = self.client.post(
            "/auth/login",
            json={
                "email": self.user_data["email"],
                "password": self.user_data["password"],
            },
        )

        if response.status_code == 200:
            data = response.json()
            self.token = data["access_token"]
            self.headers = {"Authorization": f"Bearer {self.token}"}
        else:
            print(f"Login failed for {self.user_data['email']}: {response.status_code}")

    @task(3)
    def test_real_patient_creation_under_load(self):
        """Create patient with real encrypted data and verify database write."""
        if not self.token:
            return

        # Generate realistic patient data
        patient_data = {
            "firstName": fake.first_name(),
            "lastName": fake.last_name(),
            "dateOfBirth": fake.date_of_birth(
                minimum_age=18, maximum_age=80
            ).isoformat(),
            "gender": random.choice(["male", "female", "other"]),
            "ssn": fake.ssn(),  # Will be encrypted by real service
            "phone": fake.phone_number(),
            "email": fake.email(),
            "bloodType": random.choice(
                ["A+", "A-", "B+", "B-", "O+", "O-", "AB+", "AB-"]
            ),
            "address": {
                "street": fake.street_address(),
                "city": fake.city(),
                "state": fake.state_abbr(),
                "postalCode": fake.postcode(),
                "country": fake.country_code(),
            },
            "medicalHistory": fake.text(max_nb_chars=500),
            "allergies": [fake.word() for _ in range(random.randint(0, 3))],
            "medications": [
                {
                    "name": fake.word(),
                    "dosage": f"{random.randint(5, 500)}mg",
                    "frequency": random.choice(["daily", "twice daily", "as needed"]),
                }
                for _ in range(random.randint(0, 5))
            ],
            "emergencyContact": {
                "name": fake.name(),
                "relationship": random.choice(
                    ["spouse", "parent", "sibling", "friend"]
                ),
                "phone": fake.phone_number(),
            },
        }

        start_time = time.time()

        with self.client.post(
            "/api/patients",
            json=patient_data,
            headers=self.headers,
            catch_response=True,
        ) as response:
            total_time = time.time() - start_time

            if response.status_code == 201:
                patient_id = response.json()["id"]
                self.created_patients.append(patient_id)

                # Performance criteria
                if total_time > 0.5:
                    response.failure(
                        f"Patient creation took {total_time:.2f}s (> 500ms)"
                    )
                else:
                    response.success()

                # Verify real database write with separate request
                verify_response = self.client.get(
                    f"/api/patients/{patient_id}",
                    headers=self.headers,
                    name="/api/patients/[id] (verify)",
                )

                if verify_response.status_code != 200:
                    response.failure(
                        f"Could not verify patient in database: {verify_response.status_code}"
                    )
            else:
                response.failure(f"Failed to create patient: {response.status_code}")

    @task(2)
    def test_patient_search_performance(self):
        """Test search functionality under load."""
        if not self.token:
            return

        # Search with various criteria
        search_params = random.choice(
            [
                {"firstName": fake.first_name()[:3]},  # Partial name search
                {"lastName": fake.last_name()[:3]},
                {"bloodType": random.choice(["A+", "B+", "O+", "AB+"])},
                {"dateOfBirthFrom": "1970-01-01", "dateOfBirthTo": "1990-12-31"},
                {"phone": "+1"},  # Country code search
            ]
        )

        with self.client.get(
            "/api/patients/search",
            params=search_params,
            headers=self.headers,
            catch_response=True,
            name="/api/patients/search",
        ) as response:
            if response.elapsed.total_seconds() > 1.0:
                response.failure(
                    f"Search took {response.elapsed.total_seconds():.2f}s (> 1s)"
                )
            elif response.status_code != 200:
                response.failure(f"Search failed: {response.status_code}")
            else:
                response.success()

    @task(1)
    def test_document_upload_performance(self):
        """Test document upload to S3 under load."""
        if not self.token or not self.created_patients:
            return

        patient_id = random.choice(self.created_patients)

        files = {
            "document": (
                "test_document.pdf",
                base64.b64decode(TEST_DOCUMENT),
                "application/pdf",
            )
        }

        data = {
            "documentType": random.choice(
                ["passport", "medical_record", "vaccination_card"]
            ),
            "description": fake.sentence(),
        }

        with self.client.post(
            f"/api/patients/{patient_id}/documents",
            files=files,
            data=data,
            headers=self.headers,
            catch_response=True,
            name="/api/patients/[id]/documents",
        ) as response:
            if response.elapsed.total_seconds() > 2.0:
                response.failure(
                    f"Document upload took {response.elapsed.total_seconds():.2f}s (> 2s)"
                )
            elif response.status_code not in [200, 201]:
                response.failure(f"Upload failed: {response.status_code}")
            else:
                response.success()

    @task(2)
    def test_health_record_creation(self):
        """Test creating health records with FHIR validation."""
        if not self.token or not self.created_patients:
            return

        patient_id = random.choice(self.created_patients)

        # Create various types of health records
        record_type = random.choice(
            ["vitals", "lab_results", "vaccination", "diagnosis"]
        )

        if record_type == "vitals":
            record_data = {
                "recordType": "vitals",
                "data": {
                    "bloodPressure": f"{random.randint(90, 140)}/{random.randint(60, 90)}",
                    "heartRate": random.randint(60, 100),
                    "temperature": round(random.uniform(36.0, 38.0), 1),
                    "respiratoryRate": random.randint(12, 20),
                    "oxygenSaturation": random.randint(95, 100),
                },
            }
        elif record_type == "lab_results":
            record_data = {
                "recordType": "lab_results",
                "data": {
                    "testName": random.choice(
                        ["CBC", "Metabolic Panel", "Lipid Panel"]
                    ),
                    "results": {
                        "hemoglobin": round(random.uniform(12.0, 17.0), 1),
                        "whiteBloodCells": random.randint(4000, 11000),
                        "platelets": random.randint(150000, 400000),
                    },
                    "labName": fake.company(),
                    "collectionDate": fake.date_this_year().isoformat(),
                },
            }
        elif record_type == "vaccination":
            record_data = {
                "recordType": "vaccination",
                "data": {
                    "vaccineName": random.choice(
                        ["COVID-19", "Influenza", "Hepatitis B", "MMR"]
                    ),
                    "manufacturer": random.choice(
                        ["Pfizer", "Moderna", "J&J", "AstraZeneca"]
                    ),
                    "lotNumber": fake.bothify(text="??####"),
                    "administrationDate": fake.date_this_year().isoformat(),
                    "site": random.choice(["left_arm", "right_arm"]),
                    "doseNumber": random.randint(1, 3),
                },
            }
        else:  # diagnosis
            record_data = {
                "recordType": "diagnosis",
                "data": {
                    "condition": random.choice(
                        ["Hypertension", "Diabetes Type 2", "Asthma", "GERD"]
                    ),
                    "icdCode": random.choice(["I10", "E11.9", "J45.909", "K21.9"]),
                    "diagnosisDate": fake.date_this_year().isoformat(),
                    "severity": random.choice(["mild", "moderate", "severe"]),
                    "notes": fake.text(max_nb_chars=200),
                },
            }

        with self.client.post(
            f"/api/patients/{patient_id}/health-records",
            json=record_data,
            headers=self.headers,
            catch_response=True,
            name="/api/patients/[id]/health-records",
        ) as response:
            if response.elapsed.total_seconds() > 1.0:
                response.failure(
                    f"Health record creation took {response.elapsed.total_seconds():.2f}s (> 1s)"
                )
            elif response.status_code not in [200, 201]:
                response.failure(
                    f"Health record creation failed: {response.status_code}"
                )
            else:
                response.success()

    @task(1)
    def test_emergency_access_request(self):
        """Test emergency access under load."""
        if not self.token or not self.created_patients:
            return

        patient_id = random.choice(self.created_patients)

        emergency_data = {
            "reason": fake.sentence(),
            "urgencyLevel": random.choice(["urgent", "life_threatening"]),
            "expectedDuration": random.randint(30, 180),  # minutes
        }

        with self.client.post(
            f"/api/patients/{patient_id}/emergency-access",
            json=emergency_data,
            headers=self.headers,
            catch_response=True,
            name="/api/patients/[id]/emergency-access",
        ) as response:
            # Emergency access should be fast
            if response.elapsed.total_seconds() > 0.3:
                response.failure(
                    f"Emergency access took {response.elapsed.total_seconds():.2f}s (> 300ms)"
                )
            elif response.status_code not in [
                200,
                201,
                403,
            ]:  # 403 if not emergency provider
                response.failure(
                    f"Emergency access request failed: {response.status_code}"
                )
            else:
                response.success()

    def on_stop(self):
        """Cleanup created test data."""
        if self.token and self.created_patients:
            # Clean up in batches to avoid overwhelming the system
            for patient_id in self.created_patients[:10]:  # Limit cleanup
                try:
                    self.client.delete(
                        f"/api/patients/{patient_id}", headers=self.headers
                    )
                except Exception:
                    pass  # Ignore cleanup errors


class HealthcareProviderUser(HttpUser):
    """Simulates healthcare provider activities."""

    wait_time = between(2, 5)

    def on_start(self):
        """Login as healthcare provider."""
        response = self.client.post(
            "/auth/login",
            json={"email": "provider@clinic.org", "password": "Provider123!"},
        )

        if response.status_code == 200:
            self.token = response.json()["access_token"]
            self.headers = {"Authorization": f"Bearer {self.token}"}

    @task(3)
    def view_patient_list(self):
        """View patient list with pagination."""
        if not hasattr(self, "token"):
            return

        page = random.randint(1, 10)
        limit = random.choice([10, 20, 50])

        with self.client.get(
            f"/api/patients?page={page}&limit={limit}",
            headers=self.headers,
            catch_response=True,
            name="/api/patients (list)",
        ) as response:
            if response.elapsed.total_seconds() > 1.5:
                response.failure(
                    f"Patient list took {response.elapsed.total_seconds():.2f}s"
                )
            else:
                response.success()

    @task(2)
    def view_patient_details(self):
        """View detailed patient record."""
        if not hasattr(self, "token"):
            return

        # Get a patient ID from the list
        list_response = self.client.get(
            "/api/patients?limit=50",
            headers=self.headers,
            name="/api/patients (for selection)",
        )

        if list_response.status_code == 200:
            patients = list_response.json().get("patients", [])
            if patients:
                patient = random.choice(patients)

                with self.client.get(
                    f"/api/patients/{patient['id']}",
                    headers=self.headers,
                    catch_response=True,
                    name="/api/patients/[id] (details)",
                ) as response:
                    if response.elapsed.total_seconds() > 0.5:
                        response.failure(
                            f"Patient details took {response.elapsed.total_seconds():.2f}s"
                        )
                    else:
                        response.success()

    @task(1)
    def export_patient_data(self):
        """Export patient data in various formats."""
        if not hasattr(self, "token"):
            return

        # Get a patient ID
        list_response = self.client.get("/api/patients?limit=10", headers=self.headers)

        if list_response.status_code == 200:
            patients = list_response.json().get("patients", [])
            if patients:
                patient = random.choice(patients)
                format_type = random.choice(["fhir", "pdf", "csv"])

                with self.client.get(
                    f"/api/patients/{patient['id']}/export?format={format_type}",
                    headers=self.headers,
                    catch_response=True,
                    name=f"/api/patients/[id]/export ({format_type})",
                ) as response:
                    # Export operations can take longer
                    if response.elapsed.total_seconds() > 3.0:
                        response.failure(
                            f"Export took {response.elapsed.total_seconds():.2f}s"
                        )
                    else:
                        response.success()


# Event hooks for aggregate statistics
@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """Initialize test metrics."""
    print(f"Starting load test against {BASE_URL}")
    print("Test will simulate refugee camp registration scenario")


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Print summary statistics."""
    print("\n=== Load Test Summary ===")
    print(f"Total requests: {environment.stats.total.num_requests}")
    print(f"Failed requests: {environment.stats.total.num_failures}")
    print(f"Median response time: {environment.stats.total.median_response_time}ms")
    print(
        f"95th percentile: {environment.stats.total.get_response_time_percentile(0.95)}ms"
    )
    print(
        f"99th percentile: {environment.stats.total.get_response_time_percentile(0.99)}ms"
    )


if __name__ == "__main__":
    # Can be run directly for debugging
    from locust.env import Environment as LocalEnvironment
    from locust.stats import stats_printer

    # Setup Environment
    env = LocalEnvironment(user_classes=[PatientLoadTest, HealthcareProviderUser])
    env.create_local_runner()

    # Start test
    env.runner.start(100, spawn_rate=10)  # 100 users, 10 per second

    # Run for 60 seconds
    time.sleep(60)

    # Stop test
    env.runner.quit()

    # Print stats
    stats_printer(env.stats)
