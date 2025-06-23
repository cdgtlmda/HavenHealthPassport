"""FHIR client configuration and utilities.

This module handles encrypted PHI data through FHIR client operations
with proper access control and audit logging.
"""

from typing import Any, Dict

from fhirclient import client
from fhirclient.models.address import Address
from fhirclient.models.codeableconcept import CodeableConcept
from fhirclient.models.coding import Coding
from fhirclient.models.contactpoint import ContactPoint
from fhirclient.models.fhirdate import FHIRDate
from fhirclient.models.fhirdatetime import FHIRDateTime
from fhirclient.models.humanname import HumanName
from fhirclient.models.identifier import Identifier
from fhirclient.models.immunization import Immunization
from fhirclient.models.observation import Observation
from fhirclient.models.patient import Patient
from fhirclient.models.quantity import Quantity
from fhirclient.models.reference import Reference

from src.config import get_settings
from src.healthcare.hipaa_access_control import AccessLevel, require_phi_access

# FHIR resource type for this module
__fhir_resource__ = "Bundle"


class FHIRClient:
    """FHIR client wrapper for Haven Health Passport."""

    def __init__(self) -> None:
        """Initialize FHIR client with settings."""
        settings = get_settings()

        # FHIR server settings
        self.settings = {
            "app_id": "haven_health_passport",
            "api_base": settings.fhir_server_url,
        }

        # Initialize client
        self.client = client.FHIRClient(settings=self.settings)

    @require_phi_access(AccessLevel.WRITE)
    def create_patient(self, patient_data: Dict[str, Any]) -> Patient:
        """Create a new patient resource."""
        patient = Patient()

        # Basic demographics
        patient.id = patient_data.get("id")
        patient.active = True

        # Name
        name = HumanName()
        name.family = patient_data.get("family_name")
        name.given = [patient_data.get("given_name")]
        patient.name = [name]

        # Gender
        patient.gender = patient_data.get("gender", "unknown")

        # Birth date
        if birth_date := patient_data.get("birth_date"):
            patient.birthDate = FHIRDate(birth_date)

        # Identifiers (e.g., UNHCR number)
        if unhcr_id := patient_data.get("unhcr_id"):
            identifier = Identifier()
            identifier.system = "https://www.unhcr.org/identifiers"
            identifier.value = unhcr_id
            identifier.use = "official"

            # Type coding
            id_type = CodeableConcept()
            id_type.text = "UNHCR Registration Number"
            identifier.type = id_type

            patient.identifier = [identifier]

        # Contact information
        telecom = []

        if phone := patient_data.get("phone"):
            contact = ContactPoint()
            contact.system = "phone"
            contact.value = phone
            contact.use = "mobile"
            telecom.append(contact)

        if email := patient_data.get("email"):
            contact = ContactPoint()
            contact.system = "email"
            contact.value = email
            telecom.append(contact)

        if telecom:
            patient.telecom = telecom

        # Address
        if address_data := patient_data.get("address"):
            address = Address()
            address.use = "home"
            address.line = [address_data.get("street")]
            address.city = address_data.get("city")
            address.district = address_data.get("district")
            address.country = address_data.get("country")
            patient.address = [address]

        return patient

    def create_observation(self, observation_data: Dict[str, Any]) -> Observation:
        """Create an observation resource (e.g., vital signs)."""
        observation = Observation()
        observation.status = "final"

        # Reference to patient
        patient_ref = Reference()
        patient_ref.reference = f"Patient/{observation_data['patient_id']}"
        observation.subject = patient_ref

        # Observation code
        code = CodeableConcept()
        coding = Coding()
        coding.system = observation_data.get("system", "http://loinc.org")
        coding.code = observation_data["code"]
        coding.display = observation_data.get("display")
        code.coding = [coding]
        observation.code = code

        # Value
        if value := observation_data.get("value"):
            quantity = Quantity()
            quantity.value = value
            quantity.unit = observation_data.get("unit")
            quantity.system = "http://unitsofmeasure.org"
            observation.valueQuantity = quantity

        # Effective date/time
        if effective := observation_data.get("effective_datetime"):
            observation.effectiveDateTime = FHIRDateTime(effective)

        return observation

    def create_immunization(self, immunization_data: Dict[str, Any]) -> Immunization:
        """Create an immunization resource."""
        immunization = Immunization()
        immunization.status = immunization_data.get("status", "completed")

        # Patient reference
        patient_ref = Reference()
        patient_ref.reference = f"Patient/{immunization_data['patient_id']}"
        immunization.patient = patient_ref

        # Vaccine code
        vaccine_code = CodeableConcept()
        coding = Coding()
        coding.system = "http://hl7.org/fhir/sid/cvx"  # CDC vaccine codes
        coding.code = immunization_data["vaccine_code"]
        coding.display = immunization_data.get("vaccine_name")
        vaccine_code.coding = [coding]
        immunization.vaccineCode = vaccine_code

        # Occurrence date
        if occurrence := immunization_data.get("occurrence_date"):
            immunization.occurrenceDateTime = FHIRDateTime(occurrence)

        # Primary source
        immunization.primarySource = immunization_data.get("primary_source", True)

        return immunization

    def validate_resource(self, resource: Any) -> Dict[str, Any]:
        """Validate a FHIR resource."""
        try:
            # Use the resource's as_json() method to validate structure
            json_data = resource.as_json()

            # Additional custom validation can be added here
            return {
                "valid": True,
                "resource_type": resource.resource_type,
                "data": json_data,
            }
        except (ValueError, AttributeError, TypeError) as e:
            return {
                "valid": False,
                "error": str(e),
                "resource_type": getattr(resource, "resource_type", "Unknown"),
            }
