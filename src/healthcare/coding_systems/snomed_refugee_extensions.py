"""SNOMED CT Refugee Health Extensions.

This module provides SNOMED CT expressions and value sets specifically
tailored for refugee health documentation, including post-coordinated
expressions for complex clinical situations.
"""

from typing import Dict, List, Optional

from .snomed_implementation import SNOMEDExpression


class RefugeeHealthExpressions:
    """Pre-defined SNOMED expressions for common refugee health scenarios."""

    @staticmethod
    def malnutrition_with_edema(severity: str = "severe") -> SNOMEDExpression:
        """Create expression for malnutrition with edema.

        Args:
            severity: "mild", "moderate", or "severe"

        Returns:
            SNOMED expression
        """
        severity_map = {
            "mild": "255604002",
            "moderate": "6736007",
            "severe": "24484000",
        }

        expr = SNOMEDExpression("70241007")  # Protein-calorie malnutrition
        expr.add_refinement(
            "246112005", severity_map.get(severity, "24484000")  # Severity
        )
        expr.add_refinement("42752001", "423666004")  # Associated with  # Edema
        return expr

    @staticmethod
    def tuberculosis_with_resistance(
        site: str = "lung", resistance: Optional[List[str]] = None
    ) -> SNOMEDExpression:
        """Create expression for TB with drug resistance.

        Args:
            site: Body site affected
            resistance: List of drugs with resistance

        Returns:
            SNOMED expression
        """
        site_map = {
            "lung": "39607008",
            "lymph_node": "59441001",
            "spine": "421060004",
            "meninges": "363824000",
        }

        drug_map = {
            "isoniazid": "387207008",
            "rifampin": "387467008",
            "ethambutol": "387135004",
            "pyrazinamide": "387094005",
        }

        expr = SNOMEDExpression("56717001")  # Tuberculosis
        expr.add_refinement("363698007", site_map.get(site, "39607008"))  # Finding site

        if resistance:
            for drug in resistance:
                if drug in drug_map:
                    expr.add_refinement("726553008", drug_map[drug])  # Drug resistance

        return expr

    @staticmethod
    def conflict_related_injury(
        injury_type: str, mechanism: str = "blast", body_site: Optional[str] = None
    ) -> SNOMEDExpression:
        """Create expression for conflict-related injuries.

        Args:
            injury_type: Type of injury
            mechanism: Mechanism of injury
            body_site: Optional body site

        Returns:
            SNOMED expression
        """
        injury_map = {
            "amputation": "90485000",
            "burn": "125666000",
            "fracture": "125605004",
            "shrapnel": "283545005",
            "gunshot": "283545005",
        }

        mechanism_map = {
            "blast": "242630007",
            "gunshot": "242876004",
            "landmine": "242630007",
            "torture": "95381002",
        }

        body_map = {
            "head": "69536005",
            "chest": "51185008",
            "abdomen": "113345001",
            "limb": "61685007",
        }

        expr = SNOMEDExpression(injury_map.get(injury_type, "417746004"))

        if mechanism in mechanism_map:
            expr.add_refinement("246204009", mechanism_map[mechanism])  # Mechanism

        if body_site and body_site in body_map:
            expr.add_refinement("363698007", body_map[body_site])  # Finding site

        return expr


class RefugeeHealthValueSets:
    """Value sets for refugee health documentation."""

    ENDEMIC_DISEASES = {
        "name": "Endemic Diseases in Refugee Settings",
        "concepts": [
            ("56717001", "Tuberculosis"),
            ("61462000", "Malaria"),
            ("76272004", "Dengue fever"),
            ("4834000", "Typhoid fever"),
            ("14189004", "Measles"),
            ("25225006", "Meningitis"),
            ("40468003", "Hepatitis A"),
            ("66071002", "Hepatitis B"),
            ("50711007", "Hepatitis C"),
            ("111797002", "Leishmaniasis"),
            ("63650001", "Cholera"),
            ("38362002", "Schistosomiasis"),
        ],
    }

    MENTAL_HEALTH_CONDITIONS = {
        "name": "Mental Health Conditions in Refugees",
        "concepts": [
            ("47505003", "Post-traumatic stress disorder"),
            ("35489007", "Depressive disorder"),
            ("197480006", "Anxiety disorder"),
            ("43568002", "Adjustment disorder"),
            ("44376007", "Acute stress disorder"),
            ("248005005", "Complicated grief"),
            ("268621008", "Somatic symptom disorder"),
            ("18818009", "Sleep disorder"),
            ("66344007", "Substance use disorder"),
        ],
    }

    NUTRITIONAL_CONDITIONS = {
        "name": "Nutritional Conditions",
        "concepts": [
            ("70241007", "Severe protein-calorie malnutrition"),
            ("88569008", "Moderate protein-calorie malnutrition"),
            ("238107002", "Kwashiorkor"),
            ("29740003", "Marasmus"),
            ("190606006", "Marasmic kwashiorkor"),
            ("190597007", "Vitamin A deficiency"),
            ("271737000", "Iron deficiency anemia"),
            ("4598005", "Vitamin D deficiency"),
            ("52675001", "Vitamin B12 deficiency"),
            ("85649008", "Iodine deficiency"),
        ],
    }

    REFUGEE_SPECIFIC_SITUATIONS = {
        "name": "Refugee-Specific Situations",
        "concepts": [
            ("446654005", "Refugee"),
            ("446874008", "Asylum seeker"),
            ("161140005", "Internally displaced person"),
            ("95381002", "Victim of torture"),
            ("397776005", "Victim of human trafficking"),
            ("422186009", "Victim of sexual violence"),
            ("699218002", "Child soldier"),
            ("160518006", "Unaccompanied minor"),
            ("365876005", "Separated family member"),
        ],
    }

    @classmethod
    def get_value_set(cls, name: str) -> Optional[Dict]:
        """Get a value set by name.

        Args:
            name: Value set name

        Returns:
            Value set dictionary or None
        """
        value_sets = {
            "endemic_diseases": cls.ENDEMIC_DISEASES,
            "mental_health": cls.MENTAL_HEALTH_CONDITIONS,
            "nutritional": cls.NUTRITIONAL_CONDITIONS,
            "refugee_situations": cls.REFUGEE_SPECIFIC_SITUATIONS,
        }
        return value_sets.get(name)

    @classmethod
    def is_in_value_set(cls, concept_id: str, value_set_name: str) -> bool:
        """Check if a concept is in a value set.

        Args:
            concept_id: SNOMED concept ID
            value_set_name: Name of value set

        Returns:
            True if concept is in value set
        """
        value_set = cls.get_value_set(value_set_name)
        if not value_set:
            return False

        concept_ids = [c[0] for c in value_set["concepts"]]
        return concept_id in concept_ids
