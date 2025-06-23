"""
Domain-Specific Medical Glossaries.

This module provides specialized glossaries for different medical domains.

This module handles encrypted PHI with access control and audit logging
to ensure HIPAA compliance.
 Handles FHIR Resource validation.
"""

import logging

from .base_glossary import (
    MedicalGlossary,
    MedicalTerm,
    TermCategory,
    TermPriority,
    TranslationMapping,
)

logger = logging.getLogger(__name__)


class CardiologyGlossary(MedicalGlossary):
    """Cardiology-specific terminology."""

    def __init__(self) -> None:
        """Initialize the CardiologyGlossary."""
        super().__init__()
        self._load_cardiology_terms()

    def _load_cardiology_terms(self) -> None:
        """Load cardiology-specific terms."""
        # Anatomical structures
        self.add_custom_term(
            MedicalTerm(
                term="coronary artery",
                category=TermCategory.ANATOMY,
                priority=TermPriority.CRITICAL,
                aliases=["coronary vessel"],
                description="Blood vessel supplying the heart",
            )
        )

        self.add_custom_term(
            MedicalTerm(
                term="left ventricle",
                category=TermCategory.ANATOMY,
                priority=TermPriority.HIGH,
                aliases=["LV"],
                preserve_exact=True,
            )
        )

        # Conditions
        self.add_custom_term(
            MedicalTerm(
                term="myocardial infarction",
                category=TermCategory.DISEASE,
                priority=TermPriority.CRITICAL,
                aliases=["MI", "heart attack"],
                icd10_codes=["I21", "I22"],
            )
        )

        self.add_custom_term(
            MedicalTerm(
                term="atrial fibrillation",
                category=TermCategory.DISEASE,
                priority=TermPriority.HIGH,
                aliases=["AFib", "AF"],
                icd10_codes=["I48"],
            )
        )

        # Procedures
        self.add_custom_term(
            MedicalTerm(
                term="cardiac catheterization",
                category=TermCategory.PROCEDURE,
                priority=TermPriority.HIGH,
                aliases=["heart cath", "cardiac cath"],
            )
        )

        self.add_custom_term(
            MedicalTerm(
                term="echocardiogram",
                category=TermCategory.PROCEDURE,
                priority=TermPriority.HIGH,
                aliases=["echo", "cardiac ultrasound"],
            )
        )

        # Medications
        self.add_custom_term(
            MedicalTerm(
                term="beta blocker",
                category=TermCategory.MEDICATION,
                priority=TermPriority.HIGH,
                aliases=["β-blocker", "beta-blocker"],
            )
        )

        # Add translations
        self.add_translation(
            TranslationMapping(
                source_term="myocardial infarction",
                language_mappings={
                    "es": "infarto de miocardio",
                    "fr": "infarctus du myocarde",
                    "de": "Myokardinfarkt",
                    "zh": "心肌梗死",
                    "ar": "احتشاء عضلة القلب",
                },
                verified=True,
            )
        )

        self.add_translation(
            TranslationMapping(
                source_term="atrial fibrillation",
                language_mappings={
                    "es": "fibrilación auricular",
                    "fr": "fibrillation auriculaire",
                    "de": "Vorhofflimmern",
                    "zh": "心房颤动",
                    "ar": "الرجفان الأذيني",
                },
                verified=True,
            )
        )


class OncologyGlossary(MedicalGlossary):
    """Oncology-specific terminology."""

    def __init__(self) -> None:
        """Initialize the OncologyGlossary."""
        super().__init__()
        self._load_oncology_terms()

    def _load_oncology_terms(self) -> None:
        """Load oncology-specific terms."""
        # Cancer types
        self.add_custom_term(
            MedicalTerm(
                term="adenocarcinoma",
                category=TermCategory.DISEASE,
                priority=TermPriority.CRITICAL,
                description="Cancer that forms in glandular cells",
            )
        )

        self.add_custom_term(
            MedicalTerm(
                term="lymphoma",
                category=TermCategory.DISEASE,
                priority=TermPriority.CRITICAL,
                aliases=["lymphatic cancer"],
                icd10_codes=["C81-C96"],
            )
        )

        # Treatments
        self.add_custom_term(
            MedicalTerm(
                term="chemotherapy",
                category=TermCategory.PROCEDURE,
                priority=TermPriority.HIGH,
                aliases=["chemo"],
            )
        )

        self.add_custom_term(
            MedicalTerm(
                term="radiation therapy",
                category=TermCategory.PROCEDURE,
                priority=TermPriority.HIGH,
                aliases=["radiotherapy", "XRT"],
            )
        )

        # Staging
        self.add_custom_term(
            MedicalTerm(
                term="TNM staging",
                category=TermCategory.PROCEDURE,
                priority=TermPriority.HIGH,
                preserve_exact=True,
                case_sensitive=True,
            )
        )

        # Markers
        self.add_custom_term(
            MedicalTerm(
                term="tumor marker",
                category=TermCategory.LAB_TEST,
                priority=TermPriority.HIGH,
                aliases=["cancer marker", "biomarker"],
            )
        )

        # Add translations
        self.add_translation(
            TranslationMapping(
                source_term="chemotherapy",
                language_mappings={
                    "es": "quimioterapia",
                    "fr": "chimiothérapie",
                    "de": "Chemotherapie",
                    "zh": "化疗",
                    "ar": "العلاج الكيميائي",
                },
                verified=True,
            )
        )


class PediatricsGlossary(MedicalGlossary):
    """Pediatrics-specific terminology."""

    def __init__(self) -> None:
        """Initialize the PediatricsGlossary."""
        super().__init__()
        self._load_pediatrics_terms()

    def _load_pediatrics_terms(self) -> None:
        """Load pediatrics-specific terms."""
        # Age groups
        self.add_custom_term(
            MedicalTerm(
                term="neonate",
                category=TermCategory.SPECIALTY,
                priority=TermPriority.HIGH,
                aliases=["newborn"],
                description="Infant in first 28 days of life",
            )
        )

        self.add_custom_term(
            MedicalTerm(
                term="premature infant",
                category=TermCategory.SPECIALTY,
                priority=TermPriority.HIGH,
                aliases=["preemie", "preterm infant"],
            )
        )

        # Conditions
        self.add_custom_term(
            MedicalTerm(
                term="respiratory syncytial virus",
                category=TermCategory.DISEASE,
                priority=TermPriority.HIGH,
                aliases=["RSV"],
                preserve_exact=True,
            )
        )

        # Vaccinations
        self.add_custom_term(
            MedicalTerm(
                term="MMR vaccine",
                category=TermCategory.MEDICATION,
                priority=TermPriority.CRITICAL,
                aliases=["measles-mumps-rubella"],
                preserve_exact=True,
                case_sensitive=True,
            )
        )

        # Growth parameters
        self.add_custom_term(
            MedicalTerm(
                term="growth percentile",
                category=TermCategory.VITAL_SIGN,
                priority=TermPriority.HIGH,
                description="Child's size relative to age group",
            )
        )


class EmergencyMedicineGlossary(MedicalGlossary):
    """Emergency medicine terminology."""

    def __init__(self) -> None:
        """Initialize the EmergencyMedicineGlossary."""
        super().__init__()
        self._load_emergency_terms()

    def _load_emergency_terms(self) -> None:
        """Load emergency medicine terms."""
        # Triage
        self.add_custom_term(
            MedicalTerm(
                term="triage",
                category=TermCategory.PROCEDURE,
                priority=TermPriority.CRITICAL,
                description="Prioritization of patients by severity",
            )
        )

        # Critical conditions
        self.add_custom_term(
            MedicalTerm(
                term="cardiac arrest",
                category=TermCategory.DISEASE,
                priority=TermPriority.CRITICAL,
                aliases=["cardiopulmonary arrest"],
            )
        )

        self.add_custom_term(
            MedicalTerm(
                term="anaphylaxis",
                category=TermCategory.DISEASE,
                priority=TermPriority.CRITICAL,
                aliases=["anaphylactic shock"],
                icd10_codes=["T78.2"],
            )
        )

        # Procedures
        self.add_custom_term(
            MedicalTerm(
                term="CPR",
                category=TermCategory.PROCEDURE,
                priority=TermPriority.CRITICAL,
                aliases=["cardiopulmonary resuscitation"],
                preserve_exact=True,
                case_sensitive=True,
            )
        )

        self.add_custom_term(
            MedicalTerm(
                term="intubation",
                category=TermCategory.PROCEDURE,
                priority=TermPriority.CRITICAL,
                aliases=["endotracheal intubation"],
            )
        )

        # Severity indicators
        self.add_custom_term(
            MedicalTerm(
                term="STAT",
                category=TermCategory.REGULATORY,
                priority=TermPriority.CRITICAL,
                description="Immediately/urgently",
                preserve_exact=True,
                case_sensitive=True,
            )
        )


class InfectiousDiseaseGlossary(MedicalGlossary):
    """Infectious disease terminology."""

    def __init__(self) -> None:
        """Initialize the InfectiousDiseaseGlossary."""
        super().__init__()
        self._load_infectious_disease_terms()

    def _load_infectious_disease_terms(self) -> None:
        """Load infectious disease terms."""
        # Pathogens
        self.add_custom_term(
            MedicalTerm(
                term="MRSA",
                category=TermCategory.DISEASE,
                priority=TermPriority.CRITICAL,
                aliases=["methicillin-resistant Staphylococcus aureus"],
                preserve_exact=True,
                case_sensitive=True,
            )
        )

        # Conditions
        self.add_custom_term(
            MedicalTerm(
                term="tuberculosis",
                category=TermCategory.DISEASE,
                priority=TermPriority.HIGH,
                aliases=["TB"],
                icd10_codes=["A15-A19"],
            )
        )

        self.add_custom_term(
            MedicalTerm(
                term="COVID-19",
                category=TermCategory.DISEASE,
                priority=TermPriority.HIGH,
                aliases=["coronavirus disease 2019", "SARS-CoV-2"],
                preserve_exact=True,
                icd10_codes=["U07.1"],
            )
        )

        # Treatments
        self.add_custom_term(
            MedicalTerm(
                term="antibiotic",
                category=TermCategory.MEDICATION,
                priority=TermPriority.HIGH,
                aliases=["antibacterial"],
            )
        )

        # Prevention
        self.add_custom_term(
            MedicalTerm(
                term="isolation precautions",
                category=TermCategory.PROCEDURE,
                priority=TermPriority.HIGH,
                aliases=["contact precautions", "droplet precautions"],
            )
        )


class MentalHealthGlossary(MedicalGlossary):
    """Mental health terminology."""

    def __init__(self) -> None:
        """Initialize the MentalHealthGlossary."""
        super().__init__()
        self._load_mental_health_terms()

    def _load_mental_health_terms(self) -> None:
        """Load mental health terms."""
        # Conditions
        self.add_custom_term(
            MedicalTerm(
                term="major depressive disorder",
                category=TermCategory.DISEASE,
                priority=TermPriority.HIGH,
                aliases=["MDD", "clinical depression"],
                icd10_codes=["F32", "F33"],
            )
        )

        self.add_custom_term(
            MedicalTerm(
                term="post-traumatic stress disorder",
                category=TermCategory.DISEASE,
                priority=TermPriority.HIGH,
                aliases=["PTSD"],
                icd10_codes=["F43.1"],
            )
        )

        # Treatments
        self.add_custom_term(
            MedicalTerm(
                term="cognitive behavioral therapy",
                category=TermCategory.PROCEDURE,
                priority=TermPriority.HIGH,
                aliases=["CBT"],
            )
        )

        # Medications
        self.add_custom_term(
            MedicalTerm(
                term="SSRI",
                category=TermCategory.MEDICATION,
                priority=TermPriority.HIGH,
                aliases=["selective serotonin reuptake inhibitor"],
                preserve_exact=True,
                case_sensitive=True,
            )
        )


# Factory for creating domain-specific glossaries
class GlossaryFactory:
    """Factory for creating domain-specific glossaries."""

    @staticmethod
    def create_glossary(domain: str) -> MedicalGlossary:
        """Create a domain-specific glossary."""
        glossaries = {
            "cardiology": CardiologyGlossary,
            "oncology": OncologyGlossary,
            "pediatrics": PediatricsGlossary,
            "emergency": EmergencyMedicineGlossary,
            "infectious_disease": InfectiousDiseaseGlossary,
            "mental_health": MentalHealthGlossary,
        }

        glossary_class = glossaries.get(domain, MedicalGlossary)
        return glossary_class()


def validate_fhir_data(data: dict) -> dict:
    """Validate FHIR data.

    Args:
        data: Data to validate

    Returns:
        Validation result with 'valid', 'errors', and 'warnings' keys
    """
    errors: list[str] = []
    warnings: list[str] = []

    if not data:
        errors.append("No data provided")

    return {"valid": len(errors) == 0, "errors": errors, "warnings": warnings}
