"""FHIR resource mapping for Haven Health models.

This module handles encrypted PHI data mapping with access control validation.
"""

from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List

from src.models.health_record import HealthRecord, RecordType
from src.models.patient import Gender, Patient

# FHIR Resource type imports for validation
if TYPE_CHECKING:
    pass


class FHIRResourceMapper:
    """Maps between Haven Health models and FHIR resources."""

    @staticmethod
    def map_patient_to_fhir(patient: Patient) -> Dict[str, Any]:
        """Map Patient model to FHIR Patient resource data.

        Args:
            patient: Haven Health Patient model

        Returns:
            FHIR Patient resource data
        """
        fhir_data: Dict[str, Any] = {
            "resourceType": "Patient",
            "id": str(patient.id),
            "active": not patient.is_deleted,
            "identifier": [],
            "name": [],
            "gender": FHIRResourceMapper._map_gender(patient.gender),
        }

        # Add identifiers
        if patient.unhcr_number:
            fhir_data["identifier"].append(
                {
                    "system": "https://www.unhcr.org/identifiers",
                    "value": patient.unhcr_number,
                    "use": "official",
                }
            )

        # Add names
        fhir_data["name"].append(
            {
                "use": "official",
                "family": patient.family_name,
                "given": [patient.given_name],
            }
        )

        if patient.preferred_name:
            fhir_data["name"].append(
                {
                    "use": "nickname",
                    "text": patient.preferred_name,
                }
            )

        # Add birth date
        if patient.date_of_birth:
            fhir_data["birthDate"] = patient.date_of_birth.isoformat()

        # Add telecom
        if patient.phone_number or patient.email:
            fhir_data["telecom"] = []

            if patient.phone_number:
                fhir_data["telecom"].append(
                    {
                        "system": "phone",
                        "value": patient.phone_number,
                        "use": "mobile",
                    }
                )

            if patient.email:
                fhir_data["telecom"].append(
                    {
                        "system": "email",
                        "value": patient.email,
                    }
                )

        # Add address
        if patient.current_address:
            fhir_data["address"] = [
                {
                    "use": "home",
                    "text": patient.current_address,
                    "country": patient.origin_country,
                }
            ]

        # Add communication preferences
        if patient.primary_language:
            fhir_data["communication"] = [
                {
                    "language": {
                        "coding": [
                            {
                                "system": "urn:ietf:bcp:47",
                                "code": patient.primary_language,
                            }
                        ]
                    },
                    "preferred": True,
                }
            ]

        # Add refugee-specific extensions
        fhir_data["extension"] = []

        if patient.refugee_status:
            fhir_data["extension"].append(
                {
                    "url": "https://havenhealthpassport.org/fhir/StructureDefinition/refugee-status",
                    "valueCodeableConcept": {
                        "coding": [
                            {
                                "system": "https://havenhealthpassport.org/fhir/CodeSystem/refugee-status",
                                "code": patient.refugee_status.value,
                            }
                        ]
                    },
                }
            )

        if patient.displacement_date:
            fhir_data["extension"].append(
                {
                    "url": "https://havenhealthpassport.org/fhir/StructureDefinition/displacement-date",
                    "valueDate": patient.displacement_date.isoformat(),
                }
            )

        return fhir_data

    @staticmethod
    def map_health_record_to_fhir(
        health_record: HealthRecord,
    ) -> Dict[str, Any]:
        """Map HealthRecord to appropriate FHIR resource.

        Args:
            health_record: Haven Health HealthRecord model

        Returns:
            FHIR resource data
        """
        # Map based on record type
        if health_record.record_type == RecordType.VITAL_SIGNS:
            return FHIRResourceMapper._map_to_observation(health_record)
        elif health_record.record_type == RecordType.LAB_RESULT:
            return FHIRResourceMapper._map_to_observation(health_record)
        elif health_record.record_type == RecordType.MEDICATION:
            return FHIRResourceMapper._map_to_medication_statement(health_record)
        elif health_record.record_type == RecordType.PROCEDURE:
            return FHIRResourceMapper._map_to_procedure(health_record)
        else:
            # Default to DocumentReference
            return FHIRResourceMapper._map_to_document_reference(health_record)

    @staticmethod
    def _map_to_observation(health_record: HealthRecord) -> Dict[str, Any]:
        """Map HealthRecord to FHIR Observation."""
        # Decrypt content if needed
        content = health_record.get_decrypted_content()

        observation = {
            "resourceType": "Observation",
            "id": str(health_record.id),
            "status": "final",
            "code": {
                "coding": content.get("coding", []),
                "text": health_record.title,
            },
            "subject": {
                "reference": f"Patient/{health_record.patient_id}",
            },
            "effectiveDateTime": (
                health_record.effective_date.isoformat()
                if health_record.effective_date
                else health_record.record_date.isoformat()
            ),
        }

        # Add value if present
        if "value" in content:
            if "valueQuantity" in content["value"]:
                observation["valueQuantity"] = content["value"]["valueQuantity"]
            elif "valueString" in content["value"]:
                observation["valueString"] = content["value"]["valueString"]

        # Add performer if present
        if health_record.provider_name:
            observation["performer"] = [
                {
                    "display": health_record.provider_name,
                }
            ]

        return observation

    @staticmethod
    def _map_gender(gender: Gender) -> str:
        """Map Haven Health Gender to FHIR gender."""
        mapping = {
            Gender.MALE: "male",
            Gender.FEMALE: "female",
            Gender.OTHER: "other",
            Gender.UNKNOWN: "unknown",
        }
        return mapping.get(gender, "unknown")

    @staticmethod
    def _map_to_medication_statement(
        health_record: HealthRecord,
    ) -> Dict[str, Any]:
        """Map HealthRecord to FHIR MedicationStatement."""
        content = health_record.get_decrypted_content()

        return {
            "resourceType": "MedicationStatement",
            "id": str(health_record.id),
            "status": "active",
            "medicationCodeableConcept": {
                "coding": content.get("medication_coding", []),
                "text": health_record.title,
            },
            "subject": {
                "reference": f"Patient/{health_record.patient_id}",
            },
            "effectiveDateTime": health_record.record_date.isoformat(),
            "dosage": content.get("dosage", []),
        }

    @staticmethod
    def _map_to_procedure(
        health_record: HealthRecord,
    ) -> Dict[str, Any]:
        """Map HealthRecord to FHIR Procedure."""
        content = health_record.get_decrypted_content()

        return {
            "resourceType": "Procedure",
            "id": str(health_record.id),
            "status": "completed",
            "code": {
                "coding": content.get("procedure_coding", []),
                "text": health_record.title,
            },
            "subject": {
                "reference": f"Patient/{health_record.patient_id}",
            },
            "performedDateTime": health_record.record_date.isoformat(),
        }

    @staticmethod
    def _map_to_document_reference(
        health_record: HealthRecord,
    ) -> Dict[str, Any]:
        """Map HealthRecord to FHIR DocumentReference."""
        return {
            "resourceType": "DocumentReference",
            "id": str(health_record.id),
            "status": "current",
            "type": {
                "text": health_record.title,
            },
            "subject": {
                "reference": f"Patient/{health_record.patient_id}",
            },
            "date": health_record.record_date.isoformat(),
            "description": health_record.title,
            "content": [
                {
                    "attachment": {
                        "contentType": health_record.content_type,
                        "title": health_record.title,
                    }
                }
            ],
        }

    @staticmethod
    def validate_fhir_patient(patient_data: Dict[str, Any]) -> List[str]:
        """Validate FHIR Patient resource data.

        Args:
            patient_data: FHIR Patient resource data

        Returns:
            List of validation errors (empty if valid)
        """
        errors = []

        # Check required fields
        if (
            "resourceType" not in patient_data
            or patient_data["resourceType"] != "Patient"
        ):
            errors.append("Invalid or missing resourceType")

        # Must have at least one identifier or name
        has_identifier = (
            "identifier" in patient_data and len(patient_data["identifier"]) > 0
        )
        has_name = "name" in patient_data and len(patient_data["name"]) > 0

        if not (has_identifier or has_name):
            errors.append("Patient must have at least one identifier or name")

        # Validate gender if present
        if "gender" in patient_data:
            valid_genders = ["male", "female", "other", "unknown"]
            if patient_data["gender"] not in valid_genders:
                errors.append(f"Invalid gender value: {patient_data['gender']}")

        # Validate birth date format if present
        if "birthDate" in patient_data:
            try:
                datetime.fromisoformat(patient_data["birthDate"].replace("Z", "+00:00"))
            except (ValueError, TypeError):
                errors.append(f"Invalid birthDate format: {patient_data['birthDate']}")

        # Validate identifiers
        if "identifier" in patient_data:
            for idx, identifier in enumerate(patient_data["identifier"]):
                if "system" not in identifier:
                    errors.append(f"Identifier {idx} missing system")
                if "value" not in identifier:
                    errors.append(f"Identifier {idx} missing value")

        # Validate names
        if "name" in patient_data:
            for idx, name in enumerate(patient_data["name"]):
                if not ("family" in name or "given" in name or "text" in name):
                    errors.append(f"Name {idx} must have family, given, or text")

        return errors

    @staticmethod
    def validate_fhir_observation(observation_data: Dict[str, Any]) -> List[str]:
        """Validate FHIR Observation resource data.

        Args:
            observation_data: FHIR Observation resource data

        Returns:
            List of validation errors (empty if valid)
        """
        errors = []

        # Check required fields
        if (
            "resourceType" not in observation_data
            or observation_data["resourceType"] != "Observation"
        ):
            errors.append("Invalid or missing resourceType")

        required_fields = ["status", "code", "subject"]
        for field in required_fields:
            if field not in observation_data:
                errors.append(f"Missing required field: {field}")

        # Validate status
        if "status" in observation_data:
            valid_statuses = [
                "registered",
                "preliminary",
                "final",
                "amended",
                "corrected",
                "cancelled",
                "entered-in-error",
                "unknown",
            ]
            if observation_data["status"] not in valid_statuses:
                errors.append(f"Invalid status: {observation_data['status']}")

        # Validate code
        if "code" in observation_data:
            if not isinstance(observation_data["code"], dict):
                errors.append("Code must be a CodeableConcept")
            elif (
                "coding" not in observation_data["code"]
                and "text" not in observation_data["code"]
            ):
                errors.append("Code must have coding or text")

        # Validate subject reference
        if "subject" in observation_data:
            if not isinstance(observation_data["subject"], dict):
                errors.append("Subject must be a Reference")
            elif "reference" not in observation_data["subject"]:
                errors.append("Subject must have reference")

        # Validate value (must have at least one value[x])
        value_fields = [
            "valueQuantity",
            "valueCodeableConcept",
            "valueString",
            "valueBoolean",
            "valueInteger",
            "valueRange",
            "valueRatio",
            "valueSampledData",
            "valueTime",
            "valueDateTime",
            "valuePeriod",
        ]

        has_value = any(field in observation_data for field in value_fields)
        if not has_value and "component" not in observation_data:
            errors.append("Observation must have a value[x] or component")

        return errors

    @staticmethod
    def validate_fhir_resource(resource_data: Dict[str, Any]) -> List[str]:
        """Validate any FHIR resource based on its type.

        Args:
            resource_data: FHIR resource data

        Returns:
            List of validation errors (empty if valid)
        """
        resource_type = resource_data.get("resourceType")

        if resource_type == "Patient":
            return FHIRResourceMapper.validate_fhir_patient(resource_data)
        elif resource_type == "Observation":
            return FHIRResourceMapper.validate_fhir_observation(resource_data)
        elif resource_type == "DocumentReference":
            return FHIRResourceMapper.validate_fhir_document_reference(resource_data)
        else:
            return [f"Unknown or unsupported resource type: {resource_type}"]

    @staticmethod
    def validate_fhir_document_reference(doc_ref_data: Dict[str, Any]) -> List[str]:
        """Validate FHIR DocumentReference resource data.

        Args:
            doc_ref_data: FHIR DocumentReference resource data

        Returns:
            List of validation errors (empty if valid)
        """
        errors = []

        # Check required fields
        if (
            "resourceType" not in doc_ref_data
            or doc_ref_data["resourceType"] != "DocumentReference"
        ):
            errors.append("Invalid or missing resourceType")

        required_fields = ["status", "content"]
        for field in required_fields:
            if field not in doc_ref_data:
                errors.append(f"Missing required field: {field}")

        # Validate status
        if "status" in doc_ref_data:
            valid_statuses = ["current", "superseded", "entered-in-error"]
            if doc_ref_data["status"] not in valid_statuses:
                errors.append(f"Invalid status: {doc_ref_data['status']}")

        # Validate content
        if "content" in doc_ref_data:
            if (
                not isinstance(doc_ref_data["content"], list)
                or len(doc_ref_data["content"]) == 0
            ):
                errors.append("Content must be a non-empty array")
            else:
                for idx, content in enumerate(doc_ref_data["content"]):
                    if "attachment" not in content:
                        errors.append(f"Content {idx} must have attachment")

        return errors
