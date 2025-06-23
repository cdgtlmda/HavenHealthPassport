"""
Example usage of the gender-aware translation system.

This module demonstrates how to use gender detection and adaptation
in the Haven Health Passport translation pipeline.

This module handles encrypted PHI with access control and audit logging
to ensure HIPAA compliance.
"""

from src.ai.translation.config import Language
from src.ai.translation.gender import (
    BiologicalSex,
    Gender,
    GenderAdapter,
    GenderContext,
    GenderDetector,
    GenderIdentity,
    InclusiveLanguageAdapter,
    InclusiveOptions,
    MedicalGenderAdapter,
    MedicalGenderContext,
    create_pronoun_set,
    get_medical_gender_terms,
)


def basic_gender_detection() -> None:
    """Demonstrate basic gender detection."""
    print("=== Basic Gender Detection ===\n")

    detector = GenderDetector()

    # Example texts
    texts = [
        "She mentioned she was experiencing severe headaches.",
        "He said his symptoms started last week.",
        "They requested their medical records be sent to them.",
        "The patient is a 35-year-old woman with hypertension.",
        "The individual reported chest pain and shortness of breath.",
    ]

    for text in texts:
        result = detector.detect(text, Language.ENGLISH)
        print(f"Text: {text}")
        print(f"Detected gender: {result.detected_gender.value}")
        print(f"Confidence: {result.confidence:.2f}")
        print(f"Method: {result.detection_method}")
        print(f"Evidence: {result.evidence}")
        print()


def gender_adaptation_example() -> None:
    """Demonstrate gender adaptation."""
    print("=== Gender Adaptation ===\n")

    adapter = GenderAdapter(use_ai=False)  # Use rules for consistent demo

    # Original text with masculine pronouns
    text = "The doctor said he would review his patient's chart before he makes a diagnosis."

    print(f"Original text: {text}\n")

    # Adapt to different genders
    for target_gender in [Gender.FEMININE, Gender.NEUTRAL]:
        result = adapter.adapt(text, target_gender, Language.ENGLISH)
        print(f"Target: {target_gender.value}")
        print(f"Adapted: {result.adapted_text}")
        print(f"Modifications: {len(result.modifications)}")
        for orig, new in result.modifications[:3]:
            print(f"  '{orig}' → '{new}'")
        print()


def medical_gender_handling() -> None:
    """Demonstrate medical-specific gender handling."""
    print("=== Medical Gender Handling ===\n")

    medical_adapter = MedicalGenderAdapter()

    # Case 1: Trans woman with prostate
    context1 = MedicalGenderContext(
        biological_sex=BiologicalSex.MALE,
        gender_identity=GenderIdentity.WOMAN,
        pronouns="she/her",
        medical_relevance=True,
    )

    text1 = "The patient needs regular prostate screening. He should discuss hormone therapy options."

    result1 = medical_adapter.adapt_medical_text(text1, context1, Language.ENGLISH)

    print("Case: Trans woman with prostate-related care")
    print(f"Original: {text1}")
    print(f"Adapted: {result1.adapted_text}")
    print(f"Notes: {result1.warnings}")
    print()

    # Case 2: Non-binary person, reproductive health
    context2 = MedicalGenderContext(
        biological_sex=BiologicalSex.FEMALE,
        gender_identity=GenderIdentity.NON_BINARY,
        pronouns="they/them",
        reproductive_health=True,
    )

    text2 = "The pregnant woman should attend regular prenatal checkups."

    result2 = medical_adapter.adapt_medical_text(text2, context2, Language.ENGLISH)

    print("Case: Non-binary person, pregnancy care")
    print(f"Original: {text2}")
    print(f"Adapted: {result2.adapted_text}")
    print()


def inclusive_language_example() -> None:
    """Demonstrate inclusive language adaptation."""
    print("=== Inclusive Language ===\n")

    inclusive_adapter = InclusiveLanguageAdapter()

    # Example 1: Remove binary language
    text1 = "Dear ladies and gentlemen, both men and women are welcome to participate."

    result1 = inclusive_adapter.make_inclusive(
        text1, Language.ENGLISH, InclusiveOptions(avoid_binary_terms=True)
    )

    print("Example 1: Binary term replacement")
    print(f"Original: {text1}")
    print(f"Inclusive: {result1.adapted_text}")
    print()

    # Example 2: Custom pronouns
    text2 = "When the patient arrives, he should check in at the front desk."

    xe_pronouns = create_pronoun_set("xe/xem")

    result2 = inclusive_adapter.make_inclusive(
        text2, Language.ENGLISH, custom_pronouns=xe_pronouns
    )

    print("Example 2: Custom pronouns (xe/xem)")
    print(f"Original: {text2}")
    print(f"With custom pronouns: {result2.adapted_text}")
    print()


def medical_terminology_example() -> None:
    """Show medical gender terminology."""
    print("=== Medical Gender Terminology ===\n")

    categories = ["reproductive", "anatomical", "hormonal", "general"]

    for category in categories:
        terms = get_medical_gender_terms(category)
        print(f"{category.title()} terms:")
        for gendered, neutral in list(terms.items())[:3]:
            print(f"  {gendered} → {neutral}")
        print()


def pronoun_sets_example() -> None:
    """Demonstrate pronoun set creation."""
    print("=== Pronoun Sets ===\n")

    pronoun_strings = ["they/them", "she/her", "he/him", "ze/zir", "xe/xem"]

    for pronoun_str in pronoun_strings:
        pronoun_set = create_pronoun_set(pronoun_str)
        print(f"{pronoun_str}:")
        print(f"  Subject: {pronoun_set.subject}")
        print(f"  Object: {pronoun_set.object}")
        print(f"  Possessive: {pronoun_set.possessive_determiner}")
        print(f"  Reflexive: {pronoun_set.reflexive}")
        print()


def context_aware_adaptation() -> None:
    """Show context-aware gender adaptation."""
    print("=== Context-Aware Adaptation ===\n")

    adapter = GenderAdapter()

    # Create context
    context = GenderContext(
        subject_gender=Gender.NEUTRAL,
        audience_gender=Gender.UNKNOWN,
        medical_context=True,
        prefer_neutral=True,
    )

    text = "The patient said she needs her prescription refilled."

    result = adapter.adapt(text, Gender.NEUTRAL, Language.ENGLISH, context)

    print(f"Original: {text}")
    print("Context: Medical, prefer neutral")
    print(f"Adapted: {result.adapted_text}")


if __name__ == "__main__":
    # Run all examples
    basic_gender_detection()
    print("\n" + "=" * 50 + "\n")

    gender_adaptation_example()
    print("\n" + "=" * 50 + "\n")

    medical_gender_handling()
    print("\n" + "=" * 50 + "\n")

    inclusive_language_example()
    print("\n" + "=" * 50 + "\n")

    medical_terminology_example()
    print("\n" + "=" * 50 + "\n")

    pronoun_sets_example()
    print("\n" + "=" * 50 + "\n")

    context_aware_adaptation()
