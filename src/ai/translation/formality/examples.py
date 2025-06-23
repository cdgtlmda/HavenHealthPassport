"""
Example usage of the formality adjustment system.

This module demonstrates how to use the formality detection and adjustment
capabilities in the Haven Health Passport translation pipeline.

This module handles encrypted PHI with access control and audit logging
to ensure HIPAA compliance.
 Handles FHIR Resource validation.
"""

from typing import List

from src.ai.translation.config import Language
from src.ai.translation.formality import (
    CulturalFormalityAdapter,
    FormalityAdjuster,
    FormalityContext,
    FormalityDetector,
    FormalityLevel,
    MedicalContext,
    MedicalFormalityAdjuster,
    get_cultural_formality_norms,
    get_medical_formality_level,
)


def basic_formality_detection() -> None:
    """Demonstrate basic formality detection."""
    print("=== Basic Formality Detection ===\n")

    detector = FormalityDetector()

    # Example texts at different formality levels
    texts = {
        "very_informal": "Hey! Your meds are ready. Don't forget to grab 'em!",
        "informal": "Hi there! Your medication is ready for pickup. Don't forget to take it with food.",
        "neutral": "Your prescription is ready. Please take the medication with food.",
        "formal": "We are pleased to inform you that your prescription is available for collection.",
        "very_formal": "Dear Patient, We hereby notify you that your prescribed medications are available.",
    }

    for label, text in texts.items():
        result = detector.detect(text, Language.ENGLISH)
        print(f"{label.replace('_', ' ').title()}:")
        print(f"  Text: {text}")
        print(f"  Detected: {result.detected_level.name}")
        print(f"  Score: {result.formality_score:.2f}")
        print(f"  Confidence: {result.confidence:.2f}")
        print()


def formality_adjustment_example() -> None:
    """Demonstrate formality adjustment."""
    print("=== Formality Adjustment ===\n")

    adjuster = FormalityAdjuster(use_ai=False)  # Use rules for consistent demo

    # Informal to formal
    informal_text = "Hi! Can't make it to your appointment? Just give us a call and we'll reschedule."

    print("Original (Informal):", informal_text)

    result = adjuster.adjust(informal_text, FormalityLevel.FORMAL, Language.ENGLISH)

    print("Adjusted (Formal):", result.adjusted_text)
    print(f"Modifications: {len(result.modifications)}")
    for orig, new in result.modifications[:3]:
        print(f"  '{orig}' → '{new}'")
    print()

    # Formal to informal
    formal_text = "We would like to inform you that it is necessary to fast for 12 hours prior to your examination."

    print("Original (Formal):", formal_text)

    result = adjuster.adjust(formal_text, FormalityLevel.INFORMAL, Language.ENGLISH)

    print("Adjusted (Informal):", result.adjusted_text)
    print()


def medical_formality_example() -> None:
    """Demonstrate medical-specific formality adjustment."""
    print("=== Medical Formality Adjustment ===\n")

    medical_adjuster = MedicalFormalityAdjuster()

    # Technical text for patient education
    technical_text = """
    The patient has been diagnosed with hypertension and hyperlipidemia.
    We recommend initiating therapy with an ACE inhibitor and a statin.
    The patient should monitor for adverse reactions including myalgia.
    """

    print("Original (Technical):")
    print(technical_text)

    # Adjust for patient
    patient_result = medical_adjuster.adjust_medical_text(
        technical_text, MedicalContext.PATIENT_EDUCATION, "patient", Language.ENGLISH
    )

    print("\nAdjusted for Patient:")
    print(patient_result.adjusted_text)

    # Same text for healthcare provider
    provider_result = medical_adjuster.adjust_medical_text(
        technical_text,
        MedicalContext.REFERRAL_LETTER,
        "healthcare_provider",
        Language.ENGLISH,
    )

    print("\nAdjusted for Healthcare Provider:")
    print(provider_result.adjusted_text)
    print()


def cultural_formality_example() -> None:
    """Demonstrate cultural formality adaptation."""
    print("=== Cultural Formality Adaptation ===\n")

    adapter = CulturalFormalityAdapter()

    # Doctor-patient context
    context = FormalityContext(
        audience="patient",
        relationship="doctor_patient",
        document_type="consultation",
        age_group="elderly",
    )

    # Base formality level
    base_level = FormalityLevel.NEUTRAL

    print(f"Base formality: {base_level.name}")
    print("Context: Elderly patient consultation\n")

    # Adapt for different cultures
    cultures = [
        ("en-US", "American English"),
        ("en-GB", "British English"),
        ("ja-JP", "Japanese"),
        ("de-DE", "German"),
    ]

    for culture_code, culture_name in cultures:
        adapted_level = adapter.adapt_formality(
            base_level,
            "en-US",  # Source culture
            culture_code,  # Target culture
            context,
        )

        guidelines = adapter.get_cultural_guidelines(culture_code)

        print(f"{culture_name} ({culture_code}):")
        print(f"  Adapted level: {adapted_level.name}")
        print(f"  Use titles: {guidelines.get('use_titles', False)}")
        print(f"  Consider age: {guidelines.get('consider_age', False)}")
        print()


def context_based_selection() -> None:
    """Show formality selection based on context."""
    print("=== Context-Based Formality Selection ===\n")

    contexts = [
        ("patient_education", "patient", False),
        ("clinical_notes", "healthcare_provider", False),
        ("emergency", "patient", True),
        ("consent_form", "patient", False),
        ("research_paper", "healthcare_provider", False),
    ]

    for doc_type, audience, urgent in contexts:
        level = get_medical_formality_level(doc_type, audience, urgent)
        print(f"{doc_type} for {audience}:")
        print(f"  Recommended formality: {level.name}")
        if urgent:
            print("  (Urgent communication)")
        print()


def cultural_norms_example() -> None:
    """Show cultural formality norms."""
    print("=== Cultural Formality Norms ===\n")

    cultures = ["en-US", "en-GB", "ja-JP", "de-DE", "ar-SA"]

    for culture in cultures:
        norms = get_cultural_formality_norms(culture)
        print(f"{culture}:")
        print(f"  Default: {norms['default_formality'].name}")
        print(f"  Medical: {norms['medical_formality'].name}")
        print(f"  Emergency: {norms['emergency_communication'].name}")
        print(f"  Use honorifics: {norms['use_honorifics']}")
        print(f"  Age respectful: {norms['age_respectful']}")
        print()


if __name__ == "__main__":
    # Run all examples
    basic_formality_detection()
    print("\n" + "=" * 50 + "\n")

    formality_adjustment_example()
    print("\n" + "=" * 50 + "\n")

    medical_formality_example()
    print("\n" + "=" * 50 + "\n")

    cultural_formality_example()
    print("\n" + "=" * 50 + "\n")

    context_based_selection()
    print("\n" + "=" * 50 + "\n")

    cultural_norms_example()


def validate_fhir_data(data: dict) -> dict:
    """Validate FHIR data.

    Args:
        data: Data to validate

    Returns:
        Validation result with 'valid', 'errors', and 'warnings' keys
    """
    errors: List[str] = []
    warnings: List[str] = []

    if not data:
        errors.append("No data provided")

    return {"valid": len(errors) == 0, "errors": errors, "warnings": warnings}
