"""Test Medical Terminology with Real Code System Validation.

Tests actual medical code validation against real terminology services.
"""

from typing import Any, Dict, List

import pytest

# Import the REAL medical terminology service
from src.services.medical.terminology_service import MedicalTerminologyService


@pytest.mark.integration
@pytest.mark.medical_codes
class TestMedicalTerminologyReal:
    """Test medical code systems with real validation services."""

    @pytest.fixture
    def terminology_service(self):
        """Get real terminology service instance."""
        return MedicalTerminologyService()

    def test_icd10_code_validation_with_real_data(self, terminology_service):
        """Test ICD-10 code validation against real terminology service."""
        # Valid ICD-10 codes
        valid_codes = [
            ("I10", "Essential (primary) hypertension"),
            ("E11.9", "Type 2 diabetes mellitus without complications"),
            ("J45.909", "Unspecified asthma, uncomplicated"),
            ("F32.9", "Major depressive disorder, single episode, unspecified"),
            ("M79.3", "Myalgia"),
        ]

        for code, expected_display in valid_codes:
            # Validate code using real service
            assert terminology_service.validate_icd10_code(code) is True
            description = terminology_service.get_icd10_description(code)
            assert description == expected_display
            print(f"✅ ICD-10 code {code}: {description}")

        # Test invalid codes
        invalid_codes = ["ZZZ99", "InvalidCode", "I99.99"]

        for code in invalid_codes:
            # Should return False for invalid codes
            assert terminology_service.validate_icd10_code(code) is False
            assert terminology_service.get_icd10_description(code) is None
            print(f"✅ Invalid ICD-10 code {code} correctly rejected")

        # Test hierarchical validation
        assert (
            terminology_service.is_child_of_icd10("I10", "I10-I16") is True
        )  # Hypertensive diseases
        print("✅ ICD-10 hierarchical validation working")

    def test_snomed_ct_hierarchy_validation(self, terminology_service):
        """Test SNOMED CT code validation and hierarchy."""
        # Test SNOMED CT codes with hierarchy
        snomed_codes = [
            {
                "code": "38341003",
                "display": "Hypertensive disorder",
                "parents": ["64572001"],  # Disease
            },
            {
                "code": "73211009",
                "display": "Diabetes mellitus",
                "parents": ["64572001"],  # Disease
            },
            {
                "code": "386661006",
                "display": "Fever",
                "parents": ["404684003"],  # Clinical finding
            },
        ]

        for code_info in snomed_codes:
            # Validate code
            assert terminology_service.validate_snomed_code(code_info["code"]) is True
            description = terminology_service.get_snomed_description(code_info["code"])
            assert description == code_info["display"]
            print(f"✅ SNOMED CT code {code_info['code']}: {description}")

            # Test subsumption (is-a relationship)
            for parent in code_info.get("parents", []):
                is_subsumed = terminology_service.check_snomed_subsumption(
                    parent, code_info["code"]
                )
                assert is_subsumed is True
                print(f"✅ {parent} subsumes {code_info['code']}")

    def test_rxnorm_drug_codes(self, terminology_service):
        """Test RxNorm drug code validation."""
        # Common medications with RxNorm codes
        medications = [
            {
                "code": "1049683",
                "display": "Acetaminophen 325 MG Oral Tablet",
                "ingredient": "161",  # Acetaminophen
            },
            {
                "code": "197361",
                "display": "Amoxicillin 500 MG Oral Capsule",
                "ingredient": "723",  # Amoxicillin
            },
            {
                "code": "312961",
                "display": "Metformin hydrochloride 500 MG Oral Tablet",
                "ingredient": "6809",  # Metformin
            },
        ]

        for med in medications:
            # Validate RxNorm code
            assert terminology_service.validate_rxnorm_code(med["code"]) is True
            description = terminology_service.get_rxnorm_description(med["code"])
            assert description == med["display"]
            print(f"✅ RxNorm code {med['code']}: {description}")

    def test_loinc_lab_codes(self, terminology_service):
        """Test LOINC laboratory code validation."""
        # Common lab tests with LOINC codes
        lab_tests = [
            {
                "code": "2345-7",
                "display": "Glucose [Mass/volume] in Serum or Plasma",
                "category": "Chemistry",
            },
            {
                "code": "718-7",
                "display": "Hemoglobin [Mass/volume] in Blood",
                "category": "Hematology",
            },
            {
                "code": "2951-2",
                "display": "Sodium [Moles/volume] in Serum or Plasma",
                "category": "Chemistry",
            },
            {
                "code": "33914-3",
                "display": "Glomerular filtration rate/1.73 sq M.predicted",
                "category": "Chemistry",
            },
        ]

        for test in lab_tests:
            # Validate LOINC code
            assert terminology_service.validate_loinc_code(test["code"]) is True
            description = terminology_service.get_loinc_description(test["code"])
            assert description == test["display"]
            print(f"✅ LOINC code {test['code']}: {description}")

    def test_drug_interaction_check_with_real_service(self, terminology_service):
        """Test drug-drug interaction checking."""
        # Known drug interactions to test
        interaction_pairs: List[Dict[str, Any]] = [
            {
                "drug1": {"code": "1719", "name": "Lithium"},
                "drug2": {"code": "29046", "name": "Lisinopril"},
                "severity": "major",
                "description": "increased lithium levels",
            },
            {
                "drug1": {"code": "70618", "name": "Warfarin"},
                "drug2": {"code": "161", "name": "Acetaminophen"},
                "severity": "moderate",
                "description": "increased INR",
            },
        ]

        for pair in interaction_pairs:
            # Check for interactions using real service
            drug_codes = [pair["drug1"]["code"], pair["drug2"]["code"]]
            interactions = terminology_service.check_drug_interactions(drug_codes)

            assert len(interactions) > 0
            interaction = interactions[0]
            assert interaction["severity"] == pair["severity"]
            assert pair["description"] in interaction["description"]

            print(
                f"✅ Drug interaction check: {pair['drug1']['name']} + {pair['drug2']['name']}"
            )
            print(
                f"   Severity: {interaction['severity']}, Effect: {interaction['description']}"
            )

    def test_allergy_code_validation(self, terminology_service):
        """Test allergy and substance code validation."""
        # Common allergens
        allergens = [
            {
                "system": "http://www.nlm.nih.gov/research/umls/rxnorm",
                "code": "7980",
                "display": "Penicillin",
            },
            {
                "system": "http://snomed.info/sct",
                "code": "91935009",
                "display": "Allergy to peanut",
            },
            {
                "system": "http://snomed.info/sct",
                "code": "414285001",
                "display": "Food allergy",
            },
        ]

        for allergen in allergens:
            is_valid, description = terminology_service.validate_medical_code(
                allergen["system"], allergen["code"]
            )
            assert is_valid is True
            print(f"✅ Allergy code validated: {allergen['display']}")

    def test_procedure_code_validation(self, terminology_service):
        """Test procedure code validation (CPT/SNOMED)."""
        procedures = [
            {
                "system": "http://www.ama-assn.org/go/cpt",
                "code": "99213",
                "display": "Office visit, established patient, 15 minutes",
            },
            {
                "system": "http://snomed.info/sct",
                "code": "103693007",
                "display": "Diagnostic procedure",
            },
            {
                "system": "http://snomed.info/sct",
                "code": "46680005",
                "display": "Vital signs",
            },
        ]

        for procedure in procedures:
            # For CPT codes, we'd need a separate validation method
            # For now, validate SNOMED codes
            if procedure["system"] == "http://snomed.info/sct":
                is_valid, description = terminology_service.validate_medical_code(
                    procedure["system"], procedure["code"]
                )
                assert is_valid is True
                assert description == procedure["display"]
                print(f"✅ Procedure code validated: {procedure['display']}")

    def test_refugee_specific_codes(self, terminology_service):
        """Test refugee-specific medical codes and conditions."""
        # Conditions common in refugee populations
        refugee_conditions = [
            {
                "system": "http://snomed.info/sct",
                "code": "47505003",
                "display": "Posttraumatic stress disorder",
            },
            {
                "system": "http://snomed.info/sct",
                "code": "40956001",
                "display": "Tuberculosis",
            },
            {
                "system": "http://snomed.info/sct",
                "code": "386661006",
                "display": "Fever",
            },
            {
                "system": "http://snomed.info/sct",
                "code": "271737000",
                "display": "Malnutrition",
            },
        ]

        for condition in refugee_conditions:
            is_valid, description = terminology_service.validate_medical_code(
                condition["system"], condition["code"]
            )
            assert is_valid is True
            print(f"✅ Refugee health condition validated: {condition['display']}")

        # Test getting refugee-specific code sets
        refugee_codes = terminology_service.get_refugee_health_codes()
        assert "mental_health" in refugee_codes
        assert "infectious_diseases" in refugee_codes
        assert "nutritional" in refugee_codes
        assert "screening" in refugee_codes

        print(
            "✅ Refugee-specific code sets available for mental health, infectious diseases, nutrition, and screening"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
