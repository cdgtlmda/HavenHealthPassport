"""Healthcare data transformers between different formats."""

from datetime import datetime
from typing import Any, Dict, List

from src.healthcare.fhir_validator import FHIRValidator
from src.healthcare.hipaa_access_control import AccessLevel, require_phi_access
from src.healthcare.terminology import TerminologyService
from src.security.encryption import EncryptionService


class HealthcareTransformer:
    """Transform healthcare data between different formats (FHIR, HL7, custom)."""

    # FHIR resource type
    __fhir_resource__ = "Bundle"

    def __init__(self) -> None:
        """Initialize transformer with terminology service."""
        self.terminology = TerminologyService()
        self.fhir_validator = FHIRValidator()
        self.encryption_service = EncryptionService(
            kms_key_id="alias/haven-health-default"
        )  # For encrypting PHI data

    @require_phi_access(AccessLevel.READ)
    def hl7_to_fhir_patient(self, hl7_patient: Dict[str, Any]) -> Dict[str, Any]:
        """Transform HL7 patient data to FHIR format."""
        fhir_patient = {"resourceType": "Patient", "active": True}

        # Patient ID
        if patient_id := hl7_patient.get("patient_id"):
            if "^^^" in patient_id:
                # Parse HL7 identifier format
                parts = patient_id.split("^^^")
                fhir_patient["identifier"] = [
                    {
                        "value": parts[0],
                        "system": f"urn:oid:{parts[1]}" if len(parts) > 1 else None,
                    }
                ]
            else:
                fhir_patient["identifier"] = [{"value": patient_id}]

        # Name
        if hl7_patient.get("family_name") or hl7_patient.get("given_name"):
            fhir_patient["name"] = [
                {
                    "family": hl7_patient.get("family_name"),
                    "given": (
                        [hl7_patient.get("given_name")]
                        if hl7_patient.get("given_name")
                        else []
                    ),
                }
            ]

        # Birth date
        if birth_date := hl7_patient.get("birth_date"):
            fhir_patient["birthDate"] = birth_date

        # Gender
        if gender := hl7_patient.get("gender"):
            gender_map = {"M": "male", "F": "female", "O": "other", "U": "unknown"}
            fhir_patient["gender"] = gender_map.get(gender.upper(), "unknown")

        # Address
        if address := hl7_patient.get("address"):
            fhir_patient["address"] = [
                {
                    "use": "home",
                    "line": [address.get("street")] if address.get("street") else [],
                    "city": address.get("city"),
                    "state": address.get("state"),
                    "country": address.get("country"),
                }
            ]

        # Validate the FHIR patient resource
        validation_result = self.fhir_validator.validate_patient(fhir_patient)
        if not validation_result["valid"]:
            # Log validation errors
            for error in validation_result["errors"]:
                print(f"FHIR validation error: {error}")

        return fhir_patient

    def fhir_to_hl7_patient(self, fhir_patient: Dict[str, Any]) -> Dict[str, Any]:
        """Transform FHIR patient data to HL7 format."""
        hl7_patient = {}

        # Patient ID
        if identifiers := fhir_patient.get("identifier"):
            # Use first identifier
            id_data = identifiers[0]
            hl7_patient["patient_id"] = id_data.get("value")
            if system := id_data.get("system"):
                if system == "https://www.unhcr.org/identifiers":
                    hl7_patient["patient_id"] += "^^^UNHCR^PI"

        # Name
        if names := fhir_patient.get("name"):
            name = names[0]
            hl7_patient["family_name"] = name.get("family", "")
            if given := name.get("given"):
                hl7_patient["given_name"] = (
                    given[0] if isinstance(given, list) else given
                )

        # Birth date
        if birth_date := fhir_patient.get("birthDate"):
            hl7_patient["birth_date"] = birth_date.replace("-", "")

        # Gender
        if gender := fhir_patient.get("gender"):
            gender_map = {"male": "M", "female": "F", "other": "O", "unknown": "U"}
            hl7_patient["gender"] = gender_map.get(gender, "U")

        # Address
        if addresses := fhir_patient.get("address"):
            addr = addresses[0]
            hl7_patient["address"] = {
                "street": addr.get("line", [""])[0] if addr.get("line") else "",
                "city": addr.get("city", ""),
                "state": addr.get("state", ""),
                "country": addr.get("country", ""),
            }

        return hl7_patient

    def normalize_vital_signs(self, raw_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Normalize vital signs data to FHIR observations."""
        observations = []

        vital_mappings = {
            "temperature": "body-temperature",
            "temp": "body-temperature",
            "bp_systolic": "blood-pressure-systolic",
            "bp_diastolic": "blood-pressure-diastolic",
            "pulse": "heart-rate",
            "heart_rate": "heart-rate",
            "resp_rate": "respiratory-rate",
            "respiratory_rate": "respiratory-rate",
            "spo2": "oxygen-saturation",
            "oxygen_sat": "oxygen-saturation",
            "weight": "body-weight",
            "height": "body-height",
        }

        patient_id = raw_data.get("patient_id")
        observation_date = raw_data.get("date", datetime.now().isoformat())

        for field, value in raw_data.items():
            if field in vital_mappings and value is not None:
                # Get the standard code
                vital_type = vital_mappings[field]
                if code_info := self.terminology.get_vital_sign_code(vital_type):
                    observation = {
                        "resourceType": "Observation",
                        "status": "final",
                        "code": {
                            "coding": [
                                {
                                    "system": code_info["system"],
                                    "code": code_info["code"],
                                    "display": code_info["display"],
                                }
                            ]
                        },
                        "subject": {"reference": f"Patient/{patient_id}"},
                        "effectiveDateTime": observation_date,
                        "valueQuantity": {
                            "value": float(value),
                            "unit": code_info.get("unit", ""),
                            "system": "http://unitsofmeasure.org",
                            "code": code_info.get("unit", ""),
                        },
                    }
                    observations.append(observation)

        # Validate all observations
        for obs in observations:
            validation_result = self.fhir_validator.validate_observation(obs)
            if not validation_result["valid"]:
                for error in validation_result["errors"]:
                    print(f"FHIR observation validation error: {error}")

        return observations

    def normalize_immunization(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize immunization data to FHIR format."""
        # Map common vaccine names to standard codes
        vaccine_name = raw_data.get("vaccine", "").lower()
        vaccine_code_info = self.terminology.get_vaccine_code(vaccine_name)

        if not vaccine_code_info:
            # Try to find by searching
            search_results = self.terminology.search_codes(vaccine_name, "vaccine")
            if search_results:
                vaccine_code_info = search_results[0]

        immunization = {
            "resourceType": "Immunization",
            "status": raw_data.get("status", "completed"),
            "patient": {"reference": f"Patient/{raw_data.get('patient_id')}"},
            "occurrenceDateTime": raw_data.get("date", datetime.now().isoformat()),
            "primarySource": raw_data.get("primary_source", True),
            "lotNumber": raw_data.get("lot_number"),
        }

        if vaccine_code_info:
            immunization["vaccineCode"] = {
                "coding": [
                    {
                        "system": vaccine_code_info["system"],
                        "code": vaccine_code_info["code"],
                        "display": vaccine_code_info["display"],
                    }
                ]
            }
        else:
            # Fallback to text
            immunization["vaccineCode"] = {"text": raw_data.get("vaccine")}

        # Add location/facility if provided
        if facility := raw_data.get("facility"):
            immunization["location"] = {"display": facility}

        # Add performer if provided
        if provider := raw_data.get("provider"):
            immunization["performer"] = [{"actor": {"display": provider}}]

        # Validate the FHIR immunization resource
        validation_result = self.fhir_validator.validate_immunization(immunization)
        if not validation_result["valid"]:
            for error in validation_result["errors"]:
                print(f"FHIR immunization validation error: {error}")

        return immunization

    def extract_summary(self, fhir_bundle: Dict[str, Any]) -> Dict[str, Any]:
        """Extract a summary from a FHIR bundle for display."""
        summary: Dict[str, Any] = {
            "patient": None,
            "conditions": [],
            "medications": [],
            "immunizations": [],
            "recent_vitals": {},
            "allergies": [],
        }

        if not fhir_bundle.get("entry"):
            return summary

        for entry in fhir_bundle["entry"]:
            resource = entry.get("resource", {})
            resource_type = resource.get("resourceType")

            if resource_type == "Patient":
                # Extract patient summary
                name = resource.get("name", [{}])[0]
                summary["patient"] = {
                    "name": f"{name.get('given', [''])[0]} {name.get('family', '')}".strip(),
                    "gender": resource.get("gender"),
                    "birthDate": resource.get("birthDate"),
                    "id": resource.get("id"),
                }

            elif resource_type == "Condition":
                # Extract conditions
                condition = {
                    "code": resource.get("code", {})
                    .get("coding", [{}])[0]
                    .get("display"),
                    "status": resource.get("clinicalStatus", {})
                    .get("coding", [{}])[0]
                    .get("code"),
                    "onset": resource.get("onsetDateTime"),
                }
                summary["conditions"].append(condition)

            elif resource_type == "MedicationStatement":
                # Extract medications
                med = {
                    "medication": resource.get("medicationCodeableConcept", {}).get(
                        "text"
                    ),
                    "status": resource.get("status"),
                    "dosage": resource.get("dosage", [{}])[0].get("text"),
                }
                summary["medications"].append(med)

            elif resource_type == "Immunization":
                # Extract immunizations
                imm = {
                    "vaccine": resource.get("vaccineCode", {})
                    .get("coding", [{}])[0]
                    .get("display"),
                    "date": resource.get("occurrenceDateTime"),
                    "status": resource.get("status"),
                }
                summary["immunizations"].append(imm)

            elif resource_type == "Observation":
                # Extract recent vital signs
                code = resource.get("code", {}).get("coding", [{}])[0].get("code")
                if code in [
                    "8310-5",
                    "8480-6",
                    "8462-4",
                    "8867-4",
                    "9279-1",
                ]:  # Common vital signs
                    display = (
                        resource.get("code", {}).get("coding", [{}])[0].get("display")
                    )
                    value = resource.get("valueQuantity", {})
                    summary["recent_vitals"][
                        display
                    ] = f"{value.get('value')} {value.get('unit')}"

            elif resource_type == "AllergyIntolerance":
                # Extract allergies
                allergy = {
                    "substance": resource.get("code", {})
                    .get("coding", [{}])[0]
                    .get("display"),
                    "severity": resource.get("criticality"),
                    "status": resource.get("clinicalStatus", {})
                    .get("coding", [{}])[0]
                    .get("code"),
                }
                summary["allergies"].append(allergy)

        return summary

    def validate_fhir_resource(self, resource: Dict[str, Any]) -> Dict[str, Any]:
        """Validate a FHIR resource based on its type.

        Args:
            resource: FHIR resource to validate

        Returns:
            Validation result with 'valid', 'errors', and 'warnings' keys
        """
        resource_type = resource.get("resourceType")

        if resource_type == "Patient":
            result = self.fhir_validator.validate_patient(resource)
            return dict(result) if result else {}
        elif resource_type == "Observation":
            return self.fhir_validator.validate_observation(resource)
        elif resource_type == "Immunization":
            return self.fhir_validator.validate_immunization(resource)
        elif resource_type == "Bundle":
            return self.fhir_validator.validate_bundle(resource)
        else:
            return {
                "valid": False,
                "errors": [f"Unknown resource type: {resource_type}"],
                "warnings": [],
            }
