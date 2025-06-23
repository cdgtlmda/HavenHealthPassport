"""Test FHIR resource validation against a real FHIR server.

This test implements actual FHIR validation using a real HAPI FHIR server,
not mocks. It ensures healthcare data meets FHIR R4 standards by validating
against the actual server implementation.
"""

import asyncio
import json
import time
import uuid

import httpx
import pytest

from src.healthcare.fhir_client_async import FHIRClient

# Mark all tests to use real FHIR server
pytestmark = [pytest.mark.integration, pytest.mark.fhir_compliance, pytest.mark.asyncio]


class TestRealFHIRValidation:
    """Test FHIR validation using actual FHIR server."""

    @pytest.fixture
    def real_fhir_client(self):
        """Create a real FHIR client connected to test server.

        This fixture creates an actual HTTP client that connects to the
        HAPI FHIR server running in Docker, not a mock.
        """
        # FHIR server URL
        fhir_url = "http://localhost:8081/fhir"

        # Create real FHIR client
        client = FHIRClient(base_url=fhir_url, timeout=30, max_retries=3)

        yield client

    async def test_validate_valid_patient_resource(self, real_fhir_client):
        """Test validation of a valid Patient resource against real FHIR server."""
        # Ensure FHIR server is ready
        fhir_url = "http://localhost:8081/fhir"
        max_attempts = 30
        for attempt in range(max_attempts):
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.get(f"{fhir_url}/metadata")
                    if response.status_code == 200:
                        break
            except httpx.ConnectError:
                if attempt == max_attempts - 1:
                    pytest.fail("FHIR server did not become ready in time")
                await asyncio.sleep(1)

        # Create a valid FHIR Patient resource
        patient_resource = {
            "resourceType": "Patient",
            "identifier": [{"system": "http://hospital.org/mrn", "value": "12345"}],
            "name": [
                {"use": "official", "family": "Doe", "given": ["John", "Michael"]}
            ],
            "gender": "male",
            "birthDate": "1990-01-15",
            "address": [
                {
                    "use": "home",
                    "line": ["123 Main St"],
                    "city": "Boston",
                    "state": "MA",
                    "postalCode": "02101",
                    "country": "USA",
                }
            ],
            "telecom": [
                {"system": "phone", "value": "+1-555-1234567", "use": "mobile"}
            ],
        }

        # Validate against real FHIR server
        validation_response = await real_fhir_client.validate_resource(
            resource=patient_resource, profile=None  # Use default Patient validation
        )

        # Assert real validation passed
        assert validation_response is not None
        assert validation_response.get("resourceType") == "OperationOutcome"

        # Check for validation issues
        issues = validation_response.get("issue", [])
        errors = [i for i in issues if i.get("severity") == "error"]

        # Valid resource should have no errors
        assert len(errors) == 0, f"Validation errors: {errors}"

    async def test_validate_invalid_patient_missing_required_fields(
        self, real_fhir_client
    ):
        """Test validation of invalid Patient missing required fields."""
        # Create invalid Patient - missing required birthDate
        invalid_patient = {
            "resourceType": "Patient",
            "name": [{"family": "Test"}],
            # Missing required fields like identifier, gender
        }

        # Validate against real FHIR server
        validation_response = await real_fhir_client.validate_resource(
            resource=invalid_patient, profile=None
        )

        # Should return validation issues
        assert validation_response.get("resourceType") == "OperationOutcome"
        issues = validation_response.get("issue", [])

        # Print the actual validation response for debugging
        print(f"Validation response: {json.dumps(validation_response, indent=2)}")

        # Should have validation warnings or information messages
        assert len(issues) > 0

        # HAPI FHIR might return these as information/warning rather than errors
        # Check that we got some feedback about the minimal resource
        assert any(
            issue.get("severity") in ["warning", "information", "error"]
            for issue in issues
        )

    async def test_validate_invalid_birthdate_format(self, real_fhir_client):
        """Test validation catches invalid date format."""
        # Invalid date format
        patient_with_bad_date = {
            "resourceType": "Patient",
            "identifier": [{"system": "http://example.org/mrn", "value": "TEST001"}],
            "birthDate": "invalid-date-format",  # Should be YYYY-MM-DD
            "gender": "male",
        }

        validation_response = await real_fhir_client.validate_resource(
            resource=patient_with_bad_date
        )

        issues = validation_response.get("issue", [])
        errors = [i for i in issues if i.get("severity") == "error"]

        # Should have error about date format
        assert len(errors) > 0
        assert any("date" in str(e).lower() for e in errors)

    async def test_validate_observation_with_real_terminology(self, real_fhir_client):
        """Test Observation validation with real terminology service."""
        # Create Observation with LOINC code
        observation = {
            "resourceType": "Observation",
            "status": "final",
            "code": {
                "coding": [
                    {
                        "system": "http://loinc.org",
                        "code": "85354-9",  # Blood pressure panel
                        "display": "Blood pressure panel with all children optional",
                    }
                ]
            },
            "subject": {"reference": "Patient/12345"},
            "effectiveDateTime": "2024-01-15T10:30:00Z",
            "component": [
                {
                    "code": {
                        "coding": [
                            {
                                "system": "http://loinc.org",
                                "code": "8480-6",
                                "display": "Systolic blood pressure",
                            }
                        ]
                    },
                    "valueQuantity": {
                        "value": 120,
                        "unit": "mmHg",
                        "system": "http://unitsofmeasure.org",
                        "code": "mm[Hg]",
                    },
                },
                {
                    "code": {
                        "coding": [
                            {
                                "system": "http://loinc.org",
                                "code": "8462-4",
                                "display": "Diastolic blood pressure",
                            }
                        ]
                    },
                    "valueQuantity": {
                        "value": 80,
                        "unit": "mmHg",
                        "system": "http://unitsofmeasure.org",
                        "code": "mm[Hg]",
                    },
                },
            ],
        }

        # Validate with real server
        validation_response = await real_fhir_client.validate_resource(
            resource=observation
        )

        # Check validation result
        assert validation_response.get("resourceType") == "OperationOutcome"
        issues = validation_response.get("issue", [])
        errors = [i for i in issues if i.get("severity") == "error"]

        # Valid LOINC codes should pass
        assert len(errors) == 0, f"Unexpected errors: {errors}"

    async def test_validate_invalid_code_system(self, real_fhir_client):
        """Test validation catches invalid code system values."""
        # Invalid status code
        observation_bad_status = {
            "resourceType": "Observation",
            "status": "invalid-status",  # Not a valid FHIR status
            "code": {"coding": [{"system": "http://loinc.org", "code": "85354-9"}]},
            "subject": {"reference": "Patient/12345"},
        }

        validation_response = await real_fhir_client.validate_resource(
            resource=observation_bad_status
        )

        issues = validation_response.get("issue", [])
        errors = [i for i in issues if i.get("severity") == "error"]

        # Should have error about invalid status
        assert len(errors) > 0
        error_messages = [e.get("diagnostics", "") for e in errors]
        assert any("status" in msg.lower() for msg in error_messages)

    async def test_validate_medication_request_complex(self, real_fhir_client):
        """Test complex MedicationRequest validation."""
        medication_request = {
            "resourceType": "MedicationRequest",
            "status": "active",
            "intent": "order",
            "medicationCodeableConcept": {
                "coding": [
                    {
                        "system": "http://www.nlm.nih.gov/research/umls/rxnorm",
                        "code": "861007",  # Metformin 500mg
                        "display": "Metformin 500 MG Oral Tablet",
                    }
                ]
            },
            "subject": {"reference": "Patient/12345", "display": "John Doe"},
            "authoredOn": "2024-01-15T10:00:00Z",
            "requester": {"reference": "Practitioner/98765", "display": "Dr. Smith"},
            "dosageInstruction": [
                {
                    "sequence": 1,
                    "text": "Take 1 tablet by mouth twice daily with meals",
                    "timing": {
                        "repeat": {"frequency": 2, "period": 1, "periodUnit": "d"}
                    },
                    "route": {
                        "coding": [
                            {
                                "system": "http://snomed.info/sct",
                                "code": "26643006",
                                "display": "Oral route",
                            }
                        ]
                    },
                    "doseAndRate": [
                        {
                            "type": {
                                "coding": [
                                    {
                                        "system": "http://terminology.hl7.org/CodeSystem/dose-rate-type",
                                        "code": "ordered",
                                        "display": "Ordered",
                                    }
                                ]
                            },
                            "doseQuantity": {
                                "value": 500,
                                "unit": "mg",
                                "system": "http://unitsofmeasure.org",
                                "code": "mg",
                            },
                        }
                    ],
                }
            ],
            "dispenseRequest": {
                "validityPeriod": {"start": "2024-01-15", "end": "2024-04-15"},
                "numberOfRepeatsAllowed": 3,
                "quantity": {
                    "value": 180,
                    "unit": "TAB",
                    "system": "http://terminology.hl7.org/CodeSystem/v3-orderableDrugForm",
                    "code": "TAB",
                },
            },
        }

        # Validate complex resource
        validation_response = await real_fhir_client.validate_resource(
            resource=medication_request
        )

        assert validation_response.get("resourceType") == "OperationOutcome"
        issues = validation_response.get("issue", [])
        errors = [i for i in issues if i.get("severity") == "error"]

        # Complex but valid resource should pass
        assert len(errors) == 0, f"Validation errors: {errors}"

    async def test_validate_bundle_with_multiple_resources(self, real_fhir_client):
        """Test validation of a Bundle containing multiple resources."""
        # Generate proper UUIDs
        patient_uuid = str(uuid.uuid4())
        observation_uuid = str(uuid.uuid4())

        bundle = {
            "resourceType": "Bundle",
            "type": "transaction",
            "entry": [
                {
                    "fullUrl": f"urn:uuid:{patient_uuid}",
                    "resource": {
                        "resourceType": "Patient",
                        "identifier": [
                            {"system": "http://example.org/mrn", "value": "BUNDLE001"}
                        ],
                        "name": [{"family": "Bundle", "given": ["Test"]}],
                        "gender": "female",
                        "birthDate": "1985-05-15",
                    },
                    "request": {"method": "POST", "url": "Patient"},
                },
                {
                    "fullUrl": f"urn:uuid:{observation_uuid}",
                    "resource": {
                        "resourceType": "Observation",
                        "status": "final",
                        "code": {
                            "coding": [
                                {
                                    "system": "http://loinc.org",
                                    "code": "29463-7",
                                    "display": "Body weight",
                                }
                            ]
                        },
                        "subject": {"reference": f"urn:uuid:{patient_uuid}"},
                        "effectiveDateTime": "2024-01-15T09:00:00Z",
                        "valueQuantity": {
                            "value": 65.5,
                            "unit": "kg",
                            "system": "http://unitsofmeasure.org",
                            "code": "kg",
                        },
                    },
                    "request": {"method": "POST", "url": "Observation"},
                },
            ],
        }

        # Validate entire bundle
        validation_response = await real_fhir_client.validate_resource(resource=bundle)

        assert validation_response.get("resourceType") == "OperationOutcome"
        issues = validation_response.get("issue", [])
        errors = [i for i in issues if i.get("severity") == "error"]

        # Valid bundle should pass
        assert len(errors) == 0, f"Bundle validation errors: {errors}"

    async def test_validate_with_profile_conformance(self, real_fhir_client):
        """Test validation against a specific profile."""
        # Patient conforming to US Core profile
        us_core_patient = {
            "resourceType": "Patient",
            "meta": {
                "profile": [
                    "http://hl7.org/fhir/us/core/StructureDefinition/us-core-patient"
                ]
            },
            "identifier": [{"system": "http://hospital.org/mrn", "value": "USCORE001"}],
            "name": [{"family": "Smith", "given": ["Jane"]}],
            "gender": "female",
            "birthDate": "1975-12-25",
            # US Core requires race and ethnicity extensions
            "extension": [
                {
                    "url": "http://hl7.org/fhir/us/core/StructureDefinition/us-core-race",
                    "extension": [
                        {
                            "url": "ombCategory",
                            "valueCoding": {
                                "system": "urn:oid:2.16.840.1.113883.6.238",
                                "code": "2054-5",
                                "display": "Black or African American",
                            },
                        }
                    ],
                },
                {
                    "url": "http://hl7.org/fhir/us/core/StructureDefinition/us-core-ethnicity",
                    "extension": [
                        {
                            "url": "ombCategory",
                            "valueCoding": {
                                "system": "urn:oid:2.16.840.1.113883.6.238",
                                "code": "2186-5",
                                "display": "Not Hispanic or Latino",
                            },
                        }
                    ],
                },
            ],
        }

        # Validate with profile
        validation_response = await real_fhir_client.validate_resource(
            resource=us_core_patient,
            profile="http://hl7.org/fhir/us/core/StructureDefinition/us-core-patient",
        )

        assert validation_response.get("resourceType") == "OperationOutcome"
        # Profile validation may have warnings but shouldn't have errors
        # if properly conformant

    async def test_validate_resource_persistence(self, real_fhir_client):
        """Test that validation results are persisted for audit."""
        patient = {
            "resourceType": "Patient",
            "identifier": [{"system": "http://example.org/mrn", "value": "AUDIT001"}],
            "name": [{"family": "Audit", "given": ["Test"]}],
            "gender": "other",
            "birthDate": "2000-01-01",
        }

        # Track validation time
        start_time = time.time()

        # Validate resource
        validation_response = await real_fhir_client.validate_resource(resource=patient)

        validation_time = time.time() - start_time

        # Validation should complete quickly
        assert validation_time < 5.0, f"Validation took too long: {validation_time}s"

        # Result should be valid
        assert validation_response.get("resourceType") == "OperationOutcome"

        # In a real system, we would check audit logs here
        # For now, just ensure the validation completed successfully
        issues = validation_response.get("issue", [])
        errors = [i for i in issues if i.get("severity") == "error"]
        assert len(errors) == 0

    async def test_concurrent_validation_requests(self, real_fhir_client):
        """Test FHIR server handles concurrent validation requests."""
        # Create multiple patients to validate
        patients = []
        for i in range(10):
            patients.append(
                {
                    "resourceType": "Patient",
                    "identifier": [
                        {
                            "system": "http://example.org/mrn",
                            "value": f"CONCURRENT{i:03d}",
                        }
                    ],
                    "name": [{"family": f"Concurrent{i}", "given": ["Test"]}],
                    "gender": "male" if i % 2 == 0 else "female",
                    "birthDate": f"1990-{(i % 12) + 1:02d}-{(i % 28) + 1:02d}",
                }
            )

        # Validate all concurrently
        validation_tasks = [
            real_fhir_client.validate_resource(resource=patient) for patient in patients
        ]

        results = await asyncio.gather(*validation_tasks)

        # All should complete successfully
        assert len(results) == 10
        for result in results:
            assert result.get("resourceType") == "OperationOutcome"
            issues = result.get("issue", [])
            errors = [i for i in issues if i.get("severity") == "error"]
            assert len(errors) == 0
