"""Patient FHIR Resource Implementation.

This module implements the Patient FHIR resource for Haven Health Passport,
extending the base FHIR resource class with patient-specific functionality.
"""

import logging
from datetime import date, datetime
from typing import Any, Dict, List, Union

from fhirclient.models.address import Address
from fhirclient.models.attachment import Attachment
from fhirclient.models.codeableconcept import CodeableConcept
from fhirclient.models.coding import Coding
from fhirclient.models.contactpoint import ContactPoint
from fhirclient.models.extension import Extension
from fhirclient.models.fhirdate import FHIRDate
from fhirclient.models.fhirreference import FHIRReference
from fhirclient.models.humanname import HumanName
from fhirclient.models.identifier import Identifier
from fhirclient.models.patient import Patient, PatientCommunication, PatientLink

from src.healthcare.hipaa_access_control import (
    AccessLevel,
    audit_phi_access,
    require_phi_access,
)

from .fhir_base import BaseFHIRResource
from .fhir_profiles import (
    CAMP_SETTLEMENT_EXTENSION,
    DISPLACEMENT_DATE_EXTENSION,
    MULTI_LANGUAGE_NAME_EXTENSION,
    REFUGEE_PATIENT_PROFILE,
    REFUGEE_STATUS_EXTENSION,
    UNHCR_REGISTRATION_EXTENSION,
)

logger = logging.getLogger(__name__)

# FHIR resource type for this module
__fhir_resource__ = "Patient"


class PatientResource(BaseFHIRResource):
    """Patient FHIR resource implementation for Haven Health Passport.

    This class implements the Patient resource with specific extensions
    and validations for refugee healthcare management.
    """

    def __init__(self) -> None:
        """Initialize Patient resource handler."""
        super().__init__(Patient)
        self._encrypted_fields = [
            "identifier[0].value",  # Primary ID
            "name[0].family",  # Family name
            "name[0].given[0]",  # Given name
            "telecom[0].value",  # Phone number
            "address[0].line[0]",  # Address line
            "address[0].postalCode",  # Postal code
        ]

    @require_phi_access(AccessLevel.WRITE)
    @audit_phi_access("create_patient_resource")
    def create_resource(self, data: Dict[str, Any]) -> Patient:
        """Create a new Patient resource.

        Args:
            data: Dictionary containing patient data with fields:
                - identifier: Patient identifiers
                - name: Patient names
                - gender: Patient gender
                - birthDate: Date of birth
                - telecom: Contact information
                - address: Addresses
                - communication: Language preferences
                - refugee_status: Refugee-specific information

        Returns:
            Created Patient resource
        """
        patient = Patient()

        # Set basic demographics
        patient.id = data.get("id")
        patient.active = data.get("active", True)

        # Set identifiers
        if "identifier" in data:
            patient.identifier = self._create_identifiers(data["identifier"])

        # Set names
        if "name" in data:
            patient.name = self._create_names(data["name"])

        # Set gender
        if "gender" in data:
            patient.gender = data["gender"]

        # Set birth date
        if "birthDate" in data:
            patient.birthDate = self._create_fhir_date(data["birthDate"])

        # Set deceased status
        if "deceasedBoolean" in data:
            patient.deceasedBoolean = data["deceasedBoolean"]
        elif "deceasedDateTime" in data:
            patient.deceasedDateTime = self._create_fhir_date(data["deceasedDateTime"])

        # Set contact information
        if "telecom" in data:
            patient.telecom = self._create_telecoms(data["telecom"])

        # Set addresses
        if "address" in data:
            patient.address = self._create_addresses(data["address"])

        # Set marital status
        if "maritalStatus" in data:
            patient.maritalStatus = self._create_codeable_concept(data["maritalStatus"])

        # Set communication preferences
        if "communication" in data:
            patient.communication = self._create_communications(data["communication"])

        # Set photo
        if "photo" in data:
            patient.photo = self._create_photos(data["photo"])

        # Set patient links
        if "link" in data:
            patient.link = self._create_links(data["link"])

        # Add refugee-specific extensions
        if "refugee_status" in data:
            self._add_refugee_extensions(patient, data["refugee_status"])

        # Add profile and validate
        self.add_meta_profile(patient, REFUGEE_PATIENT_PROFILE)
        self.add_refugee_extensions(patient)

        # Store and validate
        self._resource = patient
        self.validate()

        # Add audit entry
        self.add_audit_entry("create", data.get("created_by", "system"))

        return patient

    def get_encrypted_fields(self) -> List[str]:
        """Return list of fields that should be encrypted."""
        return self._encrypted_fields

    def _create_identifiers(
        self, identifiers: List[Dict[str, Any]]
    ) -> List[Identifier]:
        """Create Identifier objects from data."""
        result = []
        for id_data in identifiers:
            identifier = Identifier()

            if "use" in id_data:
                identifier.use = id_data["use"]

            if "type" in id_data:
                identifier.type = self._create_codeable_concept(id_data["type"])

            if "system" in id_data:
                identifier.system = id_data["system"]

            if "value" in id_data:
                identifier.value = id_data["value"]

            if "period" in id_data:
                identifier.period = self._create_period(id_data["period"])

            if "assigner" in id_data:
                identifier.assigner = FHIRReference({"reference": id_data["assigner"]})

            result.append(identifier)
        return result

    def _create_names(self, names: List[Dict[str, Any]]) -> List[HumanName]:
        """Create HumanName objects from data."""
        result = []
        for name_data in names:
            name = HumanName()

            if "use" in name_data:
                name.use = name_data["use"]

            if "text" in name_data:
                name.text = name_data["text"]

            if "family" in name_data:
                name.family = name_data["family"]

            if "given" in name_data:
                name.given = (
                    name_data["given"]
                    if isinstance(name_data["given"], list)
                    else [name_data["given"]]
                )

            if "prefix" in name_data:
                name.prefix = (
                    name_data["prefix"]
                    if isinstance(name_data["prefix"], list)
                    else [name_data["prefix"]]
                )

            if "suffix" in name_data:
                name.suffix = (
                    name_data["suffix"]
                    if isinstance(name_data["suffix"], list)
                    else [name_data["suffix"]]
                )

            if "period" in name_data:
                name.period = self._create_period(name_data["period"])

            # Add multi-language extension if provided
            if "language" in name_data or "script" in name_data:
                self._add_multi_language_extension(name, name_data)

            result.append(name)
        return result

    def _create_telecoms(self, telecoms: List[Dict[str, Any]]) -> List[ContactPoint]:
        """Create ContactPoint objects from data."""
        result = []
        for telecom_data in telecoms:
            contact = ContactPoint()

            if "system" in telecom_data:
                contact.system = telecom_data["system"]

            if "value" in telecom_data:
                contact.value = telecom_data["value"]

            if "use" in telecom_data:
                contact.use = telecom_data["use"]

            if "rank" in telecom_data:
                contact.rank = telecom_data["rank"]

            if "period" in telecom_data:
                contact.period = self._create_period(telecom_data["period"])

            result.append(contact)
        return result

    def _create_addresses(self, addresses: List[Dict[str, Any]]) -> List[Address]:
        """Create Address objects from data."""
        result = []
        for addr_data in addresses:
            address = Address()

            if "use" in addr_data:
                address.use = addr_data["use"]

            if "type" in addr_data:
                address.type = addr_data["type"]

            if "text" in addr_data:
                address.text = addr_data["text"]

            if "line" in addr_data:
                address.line = (
                    addr_data["line"]
                    if isinstance(addr_data["line"], list)
                    else [addr_data["line"]]
                )

            if "city" in addr_data:
                address.city = addr_data["city"]

            if "district" in addr_data:
                address.district = addr_data["district"]

            if "state" in addr_data:
                address.state = addr_data["state"]

            if "postalCode" in addr_data:
                address.postalCode = addr_data["postalCode"]

            if "country" in addr_data:
                address.country = addr_data["country"]

            if "period" in addr_data:
                address.period = self._create_period(addr_data["period"])

            result.append(address)
        return result

    def _create_communications(
        self, communications: List[Dict[str, Any]]
    ) -> List[PatientCommunication]:
        """Create PatientCommunication objects from data."""
        result = []
        for comm_data in communications:
            comm = PatientCommunication()

            if "language" in comm_data:
                comm.language = self._create_codeable_concept(comm_data["language"])

            if "preferred" in comm_data:
                comm.preferred = comm_data["preferred"]

            result.append(comm)
        return result

    def _create_photos(self, photos: List[Dict[str, Any]]) -> List[Attachment]:
        """Create Attachment objects for patient photos."""
        result = []
        for photo_data in photos:
            attachment = Attachment()

            if "contentType" in photo_data:
                attachment.contentType = photo_data["contentType"]

            if "data" in photo_data:
                attachment.data = photo_data["data"]

            if "url" in photo_data:
                attachment.url = photo_data["url"]

            if "title" in photo_data:
                attachment.title = photo_data["title"]

            if "creation" in photo_data:
                attachment.creation = self._create_fhir_date(photo_data["creation"])

            result.append(attachment)
        return result

    def _create_links(self, links: List[Dict[str, Any]]) -> List[PatientLink]:
        """Create PatientLink objects from data."""
        result = []
        for link_data in links:
            link = PatientLink()

            if "other" in link_data:
                link.other = FHIRReference({"reference": link_data["other"]})

            if "type" in link_data:
                link.type = link_data["type"]

            result.append(link)
        return result

    def _add_refugee_extensions(
        self, patient: Patient, refugee_data: Dict[str, Any]
    ) -> None:
        """Add refugee-specific extensions to patient."""
        if not patient.extension:
            patient.extension = []

        # Add refugee status
        if "status" in refugee_data:
            status_ext = Extension()
            status_ext.url = REFUGEE_STATUS_EXTENSION
            status_ext.valueString = refugee_data["status"]
            patient.extension.append(status_ext)

        # Add displacement date
        if "displacement_date" in refugee_data:
            date_ext = Extension()
            date_ext.url = DISPLACEMENT_DATE_EXTENSION
            date_ext.valueDate = self._create_fhir_date(
                refugee_data["displacement_date"]
            )
            patient.extension.append(date_ext)

        # Add camp/settlement identifier
        if "camp_settlement" in refugee_data:
            camp_ext = Extension()
            camp_ext.url = CAMP_SETTLEMENT_EXTENSION
            camp_ext.valueString = refugee_data["camp_settlement"]
            patient.extension.append(camp_ext)

        # Add UNHCR registration
        if "unhcr_registration" in refugee_data:
            unhcr_ext = Extension()
            unhcr_ext.url = UNHCR_REGISTRATION_EXTENSION
            unhcr_ext.valueIdentifier = Identifier()
            unhcr_ext.valueIdentifier.system = "http://unhcr.org/registration"
            unhcr_ext.valueIdentifier.value = refugee_data["unhcr_registration"]
            patient.extension.append(unhcr_ext)

    def _add_multi_language_extension(
        self, name: HumanName, name_data: Dict[str, Any]
    ) -> None:
        """Add multi-language name extension."""
        if not name.extension:
            name.extension = []

        ext = Extension()
        ext.url = MULTI_LANGUAGE_NAME_EXTENSION

        # Add sub-extensions
        if "language" in name_data:
            lang_ext = Extension()
            lang_ext.url = "language"
            lang_ext.valueCode = name_data["language"]
            if not ext.extension:
                ext.extension = []
            ext.extension.append(lang_ext)

        if "script" in name_data:
            script_ext = Extension()
            script_ext.url = "script"
            script_ext.valueCode = name_data["script"]
            if not ext.extension:
                ext.extension = []
            ext.extension.append(script_ext)

        name.extension.append(ext)

    def _create_codeable_concept(
        self, data: Union[str, Dict[str, Any]]
    ) -> CodeableConcept:
        """Create CodeableConcept from data."""
        concept = CodeableConcept()

        if isinstance(data, str):
            concept.text = data
        else:
            if "coding" in data:
                concept.coding = []
                for coding_data in data["coding"]:
                    coding = Coding()
                    if "system" in coding_data:
                        coding.system = coding_data["system"]
                    if "code" in coding_data:
                        coding.code = coding_data["code"]
                    if "display" in coding_data:
                        coding.display = coding_data["display"]
                    concept.coding.append(coding)

            if "text" in data:
                concept.text = data["text"]

        return concept

    def _create_fhir_date(self, date_value: Union[str, date, datetime]) -> FHIRDate:
        """Create FHIRDate from various date formats."""
        if isinstance(date_value, str):
            return FHIRDate(date_value)
        elif isinstance(date_value, datetime):
            return FHIRDate(date_value.date().isoformat())
        elif isinstance(date_value, date):
            return FHIRDate(date_value.isoformat())
        else:
            raise ValueError(f"Invalid date format: {type(date_value)}")

    def _create_period(self, period_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create Period object from data."""
        period = {}

        if "start" in period_data:
            period["start"] = self._create_fhir_date(period_data["start"]).as_json()

        if "end" in period_data:
            period["end"] = self._create_fhir_date(period_data["end"]).as_json()

        return period

    def update_patient(self, patient_id: str, updates: Dict[str, Any]) -> Patient:
        """Update existing patient resource.

        Args:
            patient_id: ID of patient to update
            updates: Dictionary of fields to update

        Returns:
            Updated patient resource
        """
        if not self._resource or self._resource.id != patient_id:
            raise ValueError(f"Patient {patient_id} not loaded")

        # Apply updates
        for field, value in updates.items():
            if field == "name":
                self._resource.name = self._create_names(value)
            elif field == "telecom":
                self._resource.telecom = self._create_telecoms(value)
            elif field == "address":
                self._resource.address = self._create_addresses(value)
            elif field == "communication":
                self._resource.communication = self._create_communications(value)
            elif field == "refugee_status":
                self._add_refugee_extensions(self._resource, value)
            elif hasattr(self._resource, field):
                setattr(self._resource, field, value)

        # Validate and audit
        self.validate()
        self.add_audit_entry(
            "update",
            updates.get("updated_by", "system"),
            {"fields": list(updates.keys())},
        )

        return self._resource
