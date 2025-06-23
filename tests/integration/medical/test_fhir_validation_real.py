"""Test FHIR Validation with Real FHIR Server.

Tests actual FHIR resource validation against a real FHIR server instance.
"""

import uuid
from datetime import datetime

import pytest
import requests


@pytest.mark.integration
@pytest.mark.fhir_compliance
class TestFHIRValidationReal:
    """Test FHIR resources against real FHIR validation server."""

    @pytest.fixture
    def fhir_server_url(self):
        """Get FHIR server URL from test config."""
        # In production, this would connect to the real FHIR server
        # For testing, we use the test FHIR server instance
        return "http://localhost:8080/fhir"

    @pytest.fixture
    def fhir_headers(self):
        """Return standard FHIR headers for API requests."""
        return {
            "Content-Type": "application/fhir+json",
            "Accept": "application/fhir+json",
        }

    def test_fhir_patient_resource_with_real_validator(
        self, fhir_server_url, fhir_headers, real_test_services
    ):
        """Test patient resource validation against real FHIR server."""
        # Create valid patient resource
        patient_resource = {
            "resourceType": "Patient",
            "id": str(uuid.uuid4()),
            "meta": {
                "profile": [
                    "http://haven-health.org/fhir/StructureDefinition/refugee-patient"
                ]
            },
            "identifier": [
                {
                    "system": "http://unhcr.org/refugee-id",
                    "value": f"UNHCR-{uuid.uuid4().hex[:8]}",
                },
                {
                    "system": "http://hospital.org/mrn",
                    "value": f"MRN{uuid.uuid4().hex[:8]}",
                },
            ],
            "name": [
                {
                    "use": "official",
                    "family": "الأحمد",  # Arabic family name
                    "given": ["محمد", "أحمد"],  # Arabic given names
                }
            ],
            "gender": "male",
            "birthDate": "1990-01-15",
            "address": [
                {
                    "use": "home",
                    "type": "physical",
                    "text": "Zaatari Refugee Camp, Sector 7, Unit 42",
                    "city": "Mafraq",
                    "country": "Jordan",
                }
            ],
            "communication": [
                {
                    "language": {
                        "coding": [
                            {
                                "system": "urn:ietf:bcp:47",
                                "code": "ar",
                                "display": "Arabic",
                            }
                        ]
                    },
                    "preferred": True,
                }
            ],
            "extension": [
                {
                    "url": "http://haven-health.org/fhir/extension/refugee-status",
                    "valueCodeableConcept": {
                        "coding": [
                            {
                                "system": "http://unhcr.org/refugee-status",
                                "code": "recognized",
                                "display": "Recognized Refugee",
                            }
                        ]
                    },
                }
            ],
        }

        # Validate against real FHIR server
        validation_url = f"{fhir_server_url}/$validate"
        response = requests.post(
            validation_url,
            json={
                "resourceType": "Parameters",
                "parameter": [{"name": "resource", "resource": patient_resource}],
            },
            headers=fhir_headers,
        )

        # Check validation response
        assert response.status_code == 200
        validation_result = response.json()

        # Check for validation outcome
        assert validation_result["resourceType"] == "OperationOutcome"

        # Look for errors
        issues = validation_result.get("issue", [])
        errors = [issue for issue in issues if issue.get("severity") == "error"]

        # Should have no errors
        assert len(errors) == 0, f"Validation errors: {errors}"

        print("✅ Patient resource validated successfully against FHIR server")

    def test_invalid_fhir_resource_fails_validation(
        self, fhir_server_url, fhir_headers
    ):
        """Test that invalid resources fail FHIR validation."""
        # Create invalid patient resource (missing required fields)
        invalid_patient = {
            "resourceType": "Patient",
            "id": str(uuid.uuid4()),
            # Missing required identifier
            # Missing name
            "gender": "invalid-gender",  # Invalid gender code
            "birthDate": "invalid-date-format",  # Invalid date
            "deceasedBoolean": "not-a-boolean",  # Invalid boolean
        }

        # Validate against real FHIR server
        validation_url = f"{fhir_server_url}/$validate"
        response = requests.post(
            validation_url,
            json={
                "resourceType": "Parameters",
                "parameter": [{"name": "resource", "resource": invalid_patient}],
            },
            headers=fhir_headers,
        )

        # Should still return 200, but with validation errors
        assert response.status_code == 200
        validation_result = response.json()

        # Check for errors
        issues = validation_result.get("issue", [])
        errors = [issue for issue in issues if issue.get("severity") == "error"]

        # Should have validation errors
        assert len(errors) > 0

        # Verify specific errors
        error_paths = [error.get("location", [""])[0] for error in errors]
        assert any("birthDate" in path for path in error_paths)
        assert any("gender" in path for path in error_paths)

        print(
            f"✅ Invalid resource correctly failed validation with {len(errors)} errors"
        )

    def test_observation_resource_validation(self, fhir_server_url, fhir_headers):
        """Test Observation resource validation with real FHIR server."""
        patient_id = str(uuid.uuid4())

        # Create valid Observation (blood pressure)
        observation = {
            "resourceType": "Observation",
            "id": str(uuid.uuid4()),
            "status": "final",
            "category": [
                {
                    "coding": [
                        {
                            "system": "http://terminology.hl7.org/CodeSystem/observation-category",
                            "code": "vital-signs",
                            "display": "Vital Signs",
                        }
                    ]
                }
            ],
            "code": {
                "coding": [
                    {
                        "system": "http://loinc.org",
                        "code": "85354-9",
                        "display": "Blood pressure panel with all children optional",
                    }
                ]
            },
            "subject": {
                "reference": f"Patient/{patient_id}",
                "display": "Test Patient",
            },
            "effectiveDateTime": datetime.utcnow().isoformat() + "Z",
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

        # Validate against real FHIR server
        validation_url = f"{fhir_server_url}/$validate"
        response = requests.post(
            validation_url,
            json={
                "resourceType": "Parameters",
                "parameter": [{"name": "resource", "resource": observation}],
            },
            headers=fhir_headers,
        )

        assert response.status_code == 200
        validation_result = response.json()

        # Check for errors
        issues = validation_result.get("issue", [])
        errors = [issue for issue in issues if issue.get("severity") == "error"]

        assert len(errors) == 0, f"Validation errors: {errors}"
        print("✅ Observation resource validated successfully")

    def test_medication_request_validation(self, fhir_server_url, fhir_headers):
        """Test MedicationRequest resource validation."""
        patient_id = str(uuid.uuid4())
        practitioner_id = str(uuid.uuid4())

        # Create valid MedicationRequest
        medication_request = {
            "resourceType": "MedicationRequest",
            "id": str(uuid.uuid4()),
            "status": "active",
            "intent": "order",
            "medicationCodeableConcept": {
                "coding": [
                    {
                        "system": "http://www.nlm.nih.gov/research/umls/rxnorm",
                        "code": "1719",
                        "display": "Amoxicillin 500 MG Oral Tablet",
                    }
                ]
            },
            "subject": {
                "reference": f"Patient/{patient_id}",
                "display": "Test Patient",
            },
            "authoredOn": datetime.utcnow().isoformat() + "Z",
            "requester": {
                "reference": f"Practitioner/{practitioner_id}",
                "display": "Dr. Test",
            },
            "dosageInstruction": [
                {
                    "text": "Take 1 tablet by mouth 3 times daily for 7 days",
                    "timing": {
                        "repeat": {
                            "frequency": 3,
                            "period": 1,
                            "periodUnit": "d",
                            "duration": 7,
                            "durationUnit": "d",
                        }
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
                                "value": 1,
                                "unit": "tablet",
                                "system": "http://unitsofmeasure.org",
                                "code": "{tablet}",
                            },
                        }
                    ],
                }
            ],
            "dispenseRequest": {
                "quantity": {
                    "value": 21,
                    "unit": "tablet",
                    "system": "http://unitsofmeasure.org",
                    "code": "{tablet}",
                }
            },
        }

        # Validate against real FHIR server
        validation_url = f"{fhir_server_url}/$validate"
        response = requests.post(
            validation_url,
            json={
                "resourceType": "Parameters",
                "parameter": [{"name": "resource", "resource": medication_request}],
            },
            headers=fhir_headers,
        )

        assert response.status_code == 200
        validation_result = response.json()

        # Check for errors
        issues = validation_result.get("issue", [])
        errors = [issue for issue in issues if issue.get("severity") == "error"]

        assert len(errors) == 0, f"Validation errors: {errors}"
        print("✅ MedicationRequest resource validated successfully")

    def test_bundle_transaction_validation(self, fhir_server_url, fhir_headers):
        """Test Bundle transaction with multiple resources."""
        patient_id = str(uuid.uuid4())
        observation_id = str(uuid.uuid4())

        # Create transaction bundle
        bundle = {
            "resourceType": "Bundle",
            "type": "transaction",
            "entry": [
                {
                    "fullUrl": f"urn:uuid:{patient_id}",
                    "resource": {
                        "resourceType": "Patient",
                        "id": patient_id,
                        "identifier": [
                            {
                                "system": "http://hospital.org/mrn",
                                "value": f"MRN{uuid.uuid4().hex[:8]}",
                            }
                        ],
                        "name": [{"family": "Test", "given": ["Bundle"]}],
                        "gender": "female",
                        "birthDate": "1985-05-15",
                    },
                    "request": {"method": "POST", "url": "Patient"},
                },
                {
                    "fullUrl": f"urn:uuid:{observation_id}",
                    "resource": {
                        "resourceType": "Observation",
                        "id": observation_id,
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
                        "subject": {"reference": f"urn:uuid:{patient_id}"},
                        "effectiveDateTime": datetime.utcnow().isoformat() + "Z",
                        "valueQuantity": {
                            "value": 70,
                            "unit": "kg",
                            "system": "http://unitsofmeasure.org",
                            "code": "kg",
                        },
                    },
                    "request": {"method": "POST", "url": "Observation"},
                },
            ],
        }

        # Validate bundle
        validation_url = f"{fhir_server_url}/$validate"
        response = requests.post(
            validation_url,
            json={
                "resourceType": "Parameters",
                "parameter": [{"name": "resource", "resource": bundle}],
            },
            headers=fhir_headers,
        )

        assert response.status_code == 200
        validation_result = response.json()

        # Check for errors
        issues = validation_result.get("issue", [])
        errors = [issue for issue in issues if issue.get("severity") == "error"]

        assert len(errors) == 0, f"Validation errors: {errors}"
        print("✅ Bundle transaction validated successfully")

    def test_profile_validation(self, fhir_server_url, fhir_headers):
        """Test resource validation against custom profiles."""
        # Create patient that should validate against refugee profile
        refugee_patient = {
            "resourceType": "Patient",
            "id": str(uuid.uuid4()),
            "meta": {
                "profile": [
                    "http://haven-health.org/fhir/StructureDefinition/refugee-patient"
                ]
            },
            "identifier": [
                {
                    "system": "http://unhcr.org/refugee-id",
                    "value": f"UNHCR-{uuid.uuid4().hex[:8]}",
                }
            ],
            "name": [{"family": "Refugee", "given": ["Test"]}],
            "gender": "other",
            "birthDate": "1990-01-01",
            # Required extensions for refugee profile
            "extension": [
                {
                    "url": "http://haven-health.org/fhir/extension/refugee-status",
                    "valueCodeableConcept": {
                        "coding": [
                            {
                                "system": "http://unhcr.org/refugee-status",
                                "code": "asylum-seeker",
                            }
                        ]
                    },
                },
                {
                    "url": "http://haven-health.org/fhir/extension/country-of-origin",
                    "valueString": "Syria",
                },
            ],
        }

        # Validate with profile
        validation_url = f"{fhir_server_url}/$validate"
        response = requests.post(
            validation_url,
            json={
                "resourceType": "Parameters",
                "parameter": [
                    {"name": "resource", "resource": refugee_patient},
                    {
                        "name": "profile",
                        "valueCanonical": "http://haven-health.org/fhir/StructureDefinition/refugee-patient",
                    },
                ],
            },
            headers=fhir_headers,
        )

        assert response.status_code == 200
        validation_result = response.json()

        # Check for errors
        issues = validation_result.get("issue", [])
        errors = [issue for issue in issues if issue.get("severity") == "error"]

        assert len(errors) == 0, f"Profile validation errors: {errors}"
        print("✅ Resource validated successfully against custom profile")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
