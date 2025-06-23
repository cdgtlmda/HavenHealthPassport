"""Expanded Medical Glossary Generator - Part 1: Additional Disease Terms.

This script extends the glossary generator with more comprehensive medical terms.
"""

from typing import List

# Import from the main generator
from src.translation.medical.glossary_generator import (
    LanguageCode,
    MedicalConcept,
    MedicalGlossaryGenerator,
    MedicalTermTranslation,
    TermCategory,
)


class ExpandedMedicalGlossaryGenerator(MedicalGlossaryGenerator):
    """Extended generator with comprehensive medical terms."""

    def _generate_infectious_disease_terms(self) -> List[MedicalConcept]:
        """Generate comprehensive infectious disease terms."""
        concepts = []

        # Call parent method to get malaria
        concepts.extend(super()._generate_infectious_disease_terms())

        # Tuberculosis
        tb_concept = MedicalConcept(
            code="A15-A19",
            system="ICD-10",
            primary_term="Tuberculosis",
            category=TermCategory.INFECTIOUS_DISEASES,
            definition="An infectious disease caused by Mycobacterium tuberculosis affecting primarily the lungs",
            patient_explanation="A contagious disease that mainly affects the lungs and spreads through the air when infected people cough",
            synonyms=["TB", "Consumption", "Phthisis"],
            emergency_relevant=False,
            common_in_refugees=True,
            cultural_considerations={
                "stigma": "High stigma in many communities; confidentiality is crucial",
                "treatment": "Long treatment duration requires cultural support systems",
            },
        )

        # Add translations for TB in multiple languages
        tb_concept.translations[LanguageCode.UR] = MedicalTermTranslation(
            term="Tuberculosis",
            language=LanguageCode.UR,
            translation="تپ دق",
            transliteration="tap-e-diq",
            patient_friendly="پھیپھڑوں کی ایک متعدی بیماری جو کھانسی سے پھیلتی ہے",
            cultural_notes="اس بیماری میں سماجی رسوائی کا خطرہ ہے",
            regional_variants={"Pakistan": "ٹی بی", "India": "دق"},
            verified=True,
            confidence_score=0.94,
        )

        concepts.append(tb_concept)
        return concepts
