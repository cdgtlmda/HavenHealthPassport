"""Refugee status extension implementation.

This module handles FHIR Extension Resource validation for refugee status.
"""

from datetime import date
from typing import Any, Dict, Optional

from fhirclient.models.codeableconcept import CodeableConcept
from fhirclient.models.coding import Coding
from fhirclient.models.extension import Extension
from fhirclient.models.fhirdate import FHIRDate

from ..fhir_profiles import REFUGEE_STATUS_EXTENSION
from ..fhir_validator import FHIRValidator


class RefugeeStatusExtension:
    """Handler for refugee status FHIR extension."""

    def __init__(self) -> None:
        """Initialize with FHIR validator."""
        self.validator = FHIRValidator()

    def validate_extension(self, extension: Extension) -> bool:
        """Validate refugee status extension.

        Args:
            extension: FHIR Extension object to validate

        Returns:
            True if valid, False otherwise
        """
        try:
            # Validate URL
            if extension.url != REFUGEE_STATUS_EXTENSION:
                return False

            # Validate sub-extensions
            if not extension.extension:
                return False

            has_status = False
            for sub_ext in extension.extension:
                if sub_ext.url == "status":
                    has_status = True
                    if (
                        not sub_ext.valueCodeableConcept
                        or not sub_ext.valueCodeableConcept.coding
                    ):
                        return False

            return has_status
        except (AttributeError, KeyError, TypeError, ValueError):
            return False

    @staticmethod
    def create_extension(
        status: str,
        country_of_origin: Optional[str] = None,
        date_of_arrival: Optional[date] = None,
    ) -> Extension:
        """Create refugee status extension.

        Args:
            status: Refugee status code (refugee, asylum-seeker, etc.)
            country_of_origin: ISO 3166-1 alpha-3 country code
            date_of_arrival: Date of arrival in host country

        Returns:
            FHIR Extension object
        """
        ext = Extension()
        ext.url = REFUGEE_STATUS_EXTENSION
        ext.extension = []

        # Add status sub-extension
        status_ext = Extension()
        status_ext.url = "status"
        status_concept = CodeableConcept()
        status_concept.coding = [
            Coding(
                {
                    "system": "https://havenhealthpassport.org/fhir/CodeSystem/refugee-status",
                    "code": status,
                    "display": RefugeeStatusExtension._get_status_display(status),
                }
            )
        ]
        status_ext.valueCodeableConcept = status_concept
        ext.extension.append(status_ext)

        # Add country of origin if provided
        if country_of_origin:
            country_ext = Extension()
            country_ext.url = "countryOfOrigin"
            country_concept = CodeableConcept()
            country_concept.coding = [
                Coding(
                    {
                        "system": "urn:iso:std:iso:3166",
                        "code": country_of_origin,
                    }
                )
            ]
            country_ext.valueCodeableConcept = country_concept
            ext.extension.append(country_ext)

        # Add date of arrival if provided
        if date_of_arrival:
            date_ext = Extension()
            date_ext.url = "dateOfArrival"
            date_ext.valueDate = FHIRDate(date_of_arrival.isoformat())
            ext.extension.append(date_ext)

        return ext

    @staticmethod
    def parse_extension(extension: Extension) -> Dict[str, Any]:
        """Parse refugee status extension into dictionary.

        Args:
            extension: FHIR Extension object

        Returns:
            Dictionary with parsed values
        """
        result: Dict[str, Any] = {}

        if not extension.extension:
            return result

        for sub_ext in extension.extension:
            if sub_ext.url == "status" and sub_ext.valueCodeableConcept:
                if sub_ext.valueCodeableConcept.coding:
                    result["status"] = sub_ext.valueCodeableConcept.coding[0].code
                    result["status_display"] = sub_ext.valueCodeableConcept.coding[
                        0
                    ].display
            elif sub_ext.url == "countryOfOrigin" and sub_ext.valueCodeableConcept:
                if sub_ext.valueCodeableConcept.coding:
                    result["country_of_origin"] = sub_ext.valueCodeableConcept.coding[
                        0
                    ].code
            elif sub_ext.url == "dateOfArrival" and sub_ext.valueDate:
                result["date_of_arrival"] = sub_ext.valueDate.as_json()

        return result

    @staticmethod
    def _get_status_display(status: str) -> str:
        """Get display text for status code."""
        status_map = {
            "refugee": "Refugee",
            "asylum-seeker": "Asylum Seeker",
            "internally-displaced": "Internally Displaced Person",
            "stateless": "Stateless Person",
            "returnee": "Returnee",
        }
        return status_map.get(status, status)
