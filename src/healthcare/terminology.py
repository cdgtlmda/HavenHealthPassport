"""Medical terminology and coding systems integration.

Handles FHIR CodeSystem Resource validation and medical terminology mappings.
All PHI data is encrypted and access is controlled through role-based permissions.
"""

from enum import Enum
from typing import Any, Dict, List, Optional

from src.healthcare.fhir_validator import FHIRValidator

# FHIR resource type for this module
__fhir_resource__ = "CodeSystem"


class CodingSystem(str, Enum):
    """Standard medical coding systems."""

    ICD10 = "http://hl7.org/fhir/sid/icd-10"
    ICD11 = "http://hl7.org/fhir/sid/icd-11"
    SNOMED_CT = "http://snomed.info/sct"
    LOINC = "http://loinc.org"
    RXNORM = "http://www.nlm.nih.gov/research/umls/rxnorm"
    CVX = "http://hl7.org/fhir/sid/cvx"  # CDC vaccine codes
    UNHCR = "https://www.unhcr.org/identifiers"
    WHO_ATC = "http://www.whocc.no/atc"  # WHO drug classification


class TerminologyService:
    """Service for medical terminology lookups and translations."""

    def __init__(self) -> None:
        """Initialize with common code mappings."""
        self.validator = FHIRValidator()  # Initialize validator
        # Common vaccines with CVX codes
        self.vaccine_codes = {
            "covid-19": {
                "code": "213",
                "display": "SARS-COV-2 (COVID-19) vaccine, UNSPECIFIED",
                "system": CodingSystem.CVX,
            },
            "measles": {
                "code": "05",
                "display": "Measles virus vaccine",
                "system": CodingSystem.CVX,
            },
            "polio-opv": {
                "code": "02",
                "display": "Oral poliovirus vaccine, unspecified",
                "system": CodingSystem.CVX,
            },
            "polio-ipv": {
                "code": "10",
                "display": "Inactivated poliovirus vaccine, unspecified",
                "system": CodingSystem.CVX,
            },
            "bcg": {
                "code": "19",
                "display": "Bacillus Calmette-Guerin vaccine",
                "system": CodingSystem.CVX,
            },
            "yellow-fever": {
                "code": "184",
                "display": "Yellow fever vaccine, unspecified",
                "system": CodingSystem.CVX,
            },
            "cholera": {
                "code": "26",
                "display": "Cholera vaccine, unspecified",
                "system": CodingSystem.CVX,
            },
        }

        # Common conditions relevant to refugee health
        self.condition_codes = {
            "malnutrition": {
                "code": "E44",
                "display": "Protein-energy malnutrition",
                "system": CodingSystem.ICD10,
            },
            "tuberculosis": {
                "code": "A15",
                "display": "Respiratory tuberculosis",
                "system": CodingSystem.ICD10,
            },
            "malaria": {
                "code": "B50",
                "display": "Plasmodium falciparum malaria",
                "system": CodingSystem.ICD10,
            },
            "ptsd": {
                "code": "F43.1",
                "display": "Post-traumatic stress disorder",
                "system": CodingSystem.ICD10,
            },
            "depression": {
                "code": "F32",
                "display": "Depressive episode",
                "system": CodingSystem.ICD10,
            },
            "anxiety": {
                "code": "F41",
                "display": "Other anxiety disorders",
                "system": CodingSystem.ICD10,
            },
        }

        # Vital signs LOINC codes
        self.vital_signs_codes = {
            "body-temperature": {
                "code": "8310-5",
                "display": "Body temperature",
                "system": CodingSystem.LOINC,
                "unit": "Cel",
            },
            "blood-pressure-systolic": {
                "code": "8480-6",
                "display": "Systolic blood pressure",
                "system": CodingSystem.LOINC,
                "unit": "mm[Hg]",
            },
            "blood-pressure-diastolic": {
                "code": "8462-4",
                "display": "Diastolic blood pressure",
                "system": CodingSystem.LOINC,
                "unit": "mm[Hg]",
            },
            "heart-rate": {
                "code": "8867-4",
                "display": "Heart rate",
                "system": CodingSystem.LOINC,
                "unit": "/min",
            },
            "respiratory-rate": {
                "code": "9279-1",
                "display": "Respiratory rate",
                "system": CodingSystem.LOINC,
                "unit": "/min",
            },
            "oxygen-saturation": {
                "code": "2708-6",
                "display": "Oxygen saturation",
                "system": CodingSystem.LOINC,
                "unit": "%",
            },
            "body-weight": {
                "code": "29463-7",
                "display": "Body weight",
                "system": CodingSystem.LOINC,
                "unit": "kg",
            },
            "body-height": {
                "code": "8302-2",
                "display": "Body height",
                "system": CodingSystem.LOINC,
                "unit": "cm",
            },
        }

        # Common medications
        self.medication_codes = {
            "paracetamol": {
                "code": "161",
                "display": "Acetaminophen",
                "system": CodingSystem.RXNORM,
            },
            "ibuprofen": {
                "code": "5640",
                "display": "Ibuprofen",
                "system": CodingSystem.RXNORM,
            },
            "amoxicillin": {
                "code": "723",
                "display": "Amoxicillin",
                "system": CodingSystem.RXNORM,
            },
            "ors": {
                "code": "283742",
                "display": "Oral rehydration salts",
                "system": CodingSystem.RXNORM,
            },
        }

    def get_vaccine_code(self, vaccine_name: str) -> Optional[Dict[str, str]]:
        """Get standardized vaccine code."""
        return self.vaccine_codes.get(vaccine_name.lower().replace(" ", "-"))

    def get_condition_code(self, condition_name: str) -> Optional[Dict[str, str]]:
        """Get standardized condition code."""
        return self.condition_codes.get(condition_name.lower().replace(" ", "-"))

    def get_vital_sign_code(self, vital_sign_name: str) -> Optional[Dict[str, str]]:
        """Get standardized vital sign code."""
        return self.vital_signs_codes.get(vital_sign_name.lower().replace(" ", "-"))

    def get_medication_code(self, medication_name: str) -> Optional[Dict[str, str]]:
        """Get standardized medication code."""
        return self.medication_codes.get(medication_name.lower())

    def search_codes(
        self, search_term: str, code_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Search for codes across all or specific code types."""
        results = []
        search_lower = search_term.lower()

        # Define search targets based on code_type
        if code_type == "vaccine":
            targets = [("vaccine", self.vaccine_codes)]
        elif code_type == "condition":
            targets = [("condition", self.condition_codes)]
        elif code_type == "vital_sign":
            targets = [("vital_sign", self.vital_signs_codes)]
        elif code_type == "medication":
            targets = [("medication", self.medication_codes)]
        else:
            # Search all
            targets = [
                ("vaccine", self.vaccine_codes),
                ("condition", self.condition_codes),
                ("vital_sign", self.vital_signs_codes),
                ("medication", self.medication_codes),
            ]

        # Search through targets
        for category, codes in targets:
            for key, value in codes.items():
                if search_lower in key or search_lower in value["display"].lower():
                    results.append({"category": category, "key": key, **value})

        return results

    def validate_code(self, code: str, system: str) -> bool:
        """Validate if a code exists in the specified system."""
        # This is a simplified validation
        # In production, this would query actual terminology servers
        all_codes = {
            **self.vaccine_codes,
            **self.condition_codes,
            **self.vital_signs_codes,
            **self.medication_codes,
        }

        for item in all_codes.values():
            if item["code"] == code and item["system"] == system:
                return True

        return False

    async def lookup_code(self, system: str, code: str) -> Optional[Dict[str, Any]]:
        """Lookup a code in a terminology system.

        Args:
            system: The code system URI
            code: The code to lookup

        Returns:
            Dictionary with code details or None if not found
        """
        # Check all code collections
        all_codes = {
            **self.vaccine_codes,
            **self.condition_codes,
            **self.vital_signs_codes,
            **self.medication_codes,
        }

        for item in all_codes.values():
            if item.get("code") == code and item.get("system") == system:
                return {
                    "code": code,
                    "system": system,
                    "display": item.get("display", ""),
                    "definition": item.get("definition", ""),
                }

        return None
