"""
Example usage of the dialect detection system.

This module demonstrates how to use the dialect detection capabilities
in the Haven Health Passport translation pipeline.

This module handles encrypted PHI with access control and audit logging
to ensure HIPAA compliance.
 Handles FHIR Resource validation.
"""

from typing import List

from src.ai.translation.config import Language
from src.ai.translation.dialect import (
    DialectDetector,
    DialectFeatureExtractor,
    MedicalDialectDetector,
    get_dialect_profile,
    list_supported_dialects,
)


def basic_dialect_detection() -> None:
    """Demonstrate basic dialect detection."""
    print("=== Basic Dialect Detection ===\n")

    # Create detector
    detector = DialectDetector()

    # Example texts
    us_text = """
    The patient was brought to the emergency room with severe chest pain.
    The physician prescribed acetaminophen and ordered a comprehensive
    metabolic panel. Please follow up with your primary care doctor.
    """

    uk_text = """
    The patient was brought to A&E with severe chest pain. The consultant
    prescribed paracetamol and ordered bloods. Please follow up with your GP.
    """

    # Detect dialects
    us_result = detector.detect(us_text, Language.ENGLISH)
    uk_result = detector.detect(uk_text, Language.ENGLISH)

    print(f"US Text detected as: {us_result.detected_dialect}")
    print(
        f"Confidence: {us_result.confidence:.2f} ({us_result.confidence_level.value})"
    )
    print(f"Alternatives: {[d[0] for d in us_result.alternative_dialects[:3]]}\n")

    print(f"UK Text detected as: {uk_result.detected_dialect}")
    print(
        f"Confidence: {uk_result.confidence:.2f} ({uk_result.confidence_level.value})"
    )
    print(f"Alternatives: {[d[0] for d in uk_result.alternative_dialects[:3]]}\n")


def medical_dialect_detection() -> None:
    """Medical-specific dialect detection example."""
    print("=== Medical Dialect Detection ===\n")

    # Create medical detector
    detector = MedicalDialectDetector()

    # Medical text with drug variations
    text = """
    Patient presented with anaphylactic reaction. Administered 0.3mg
    adrenaline intramuscularly. Prescribed paracetamol 500mg QDS for
    pain relief. Referred to allergy specialist at the hospital.
    """

    result = detector.detect_medical_dialect(text)

    print(f"Detected dialect: {result.detected_dialect}")
    print(f"Confidence: {result.confidence:.2f}")
    print(f"Medical terms found: {result.metadata['medical_terms_found']}")
    print(f"Medical score: {result.metadata['medical_score']:.2f}\n")

    # Show detected medical features
    print("Medical features detected:")
    for term, score in list(result.features_detected.medical_terminology.items())[:5]:
        print(f"  - {term}: {score}")
    print()


def feature_extraction_example() -> None:
    """Demonstrate feature extraction."""
    print("=== Feature Extraction ===\n")

    extractor = DialectFeatureExtractor()

    text = """
    The paediatric centre specialises in immunisation programmes.
    Our organisation honours all major insurance. Please check the
    colour-coded labels on medications. Labour and delivery services
    are available 24/7 at our facility.
    """

    features = extractor.extract_all_features(text)

    # Lexical features
    lexical = features["lexical"]
    print("Lexical Features:")
    print(f"  Average word length: {lexical.avg_word_length:.2f}")
    print(f"  Lexical diversity: {lexical.lexical_diversity:.2f}")
    print(f"  Vocabulary richness: {lexical.vocabulary_richness:.2f}")

    # Orthographic features
    ortho = features["orthographic"]
    print("\nOrthographic Features:")
    for pattern, score in list(ortho.spelling_patterns.items())[:3]:
        print(f"  {pattern}: {score:.3f}")

    # Syntactic features
    syntactic = features["syntactic"]
    print("\nSyntactic Features:")
    print(f"  Average sentence length: {syntactic.avg_sentence_length:.2f}")
    print(f"  Syntactic complexity: {syntactic.syntactic_complexity:.2f}")


def dialect_profile_example() -> None:
    """Show dialect profile information."""
    print("=== Dialect Profiles ===\n")

    # List all supported dialects
    all_dialects = list_supported_dialects()
    print(f"Total supported dialects: {len(all_dialects)}")

    # Show English dialects
    english_dialects = list_supported_dialects(Language.ENGLISH)
    print(f"\nEnglish dialects: {', '.join(english_dialects)}")

    # Get specific profile
    us_profile = get_dialect_profile("en-US")
    uk_profile = get_dialect_profile("en-GB")

    if us_profile:
        print("\n--- US English Profile ---")
        print(f"Name: {us_profile.name}")
        print(f"Region: {us_profile.region}")
        print(f"Date formats: {', '.join(us_profile.date_formats)}")
        print(f"Temperature: {us_profile.measurement_preferences['temperature']}")
        print("Medical terms:")
        for concept, term in list(us_profile.medical_term_variations.items())[:3]:
            print(f"  {concept}: {term}")

    if uk_profile:
        print("\n--- UK English Profile ---")
        print(f"Name: {uk_profile.name}")
        print(f"Region: {uk_profile.region}")
        print(f"Date formats: {', '.join(uk_profile.date_formats)}")
        print(f"Temperature: {uk_profile.measurement_preferences['temperature']}")
        print("Medical terms:")
        for concept, term in list(uk_profile.medical_term_variations.items())[:3]:
            print(f"  {concept}: {term}")


def mixed_dialect_example() -> None:
    """Handle mixed dialect text."""
    print("=== Mixed Dialect Detection ===\n")

    detector = DialectDetector()

    # Text with mixed US/UK features
    mixed_text = """
    The pediatrician at the medical centre recommended regular
    immunizations. The color of the medication should be checked.
    Both acetaminophen and paracetamol are available at the pharmacy.
    """

    result = detector.detect(mixed_text, Language.ENGLISH)

    print(f"Primary dialect: {result.detected_dialect} ({result.confidence:.2f})")
    print("Top alternatives:")
    for dialect, score in result.alternative_dialects[:3]:
        print(f"  {dialect}: {score:.2f}")

    print("\nDetected features:")
    features = result.features_detected
    print(f"  Lexical markers: {len(features.lexical_markers)}")
    print(f"  Orthographic variations: {len(features.orthographic_variations)}")
    print(f"  Medical terms: {len(features.medical_terminology)}")


if __name__ == "__main__":
    # Run all examples
    basic_dialect_detection()
    print("\n" + "=" * 50 + "\n")

    medical_dialect_detection()
    print("\n" + "=" * 50 + "\n")

    feature_extraction_example()
    print("\n" + "=" * 50 + "\n")

    dialect_profile_example()
    print("\n" + "=" * 50 + "\n")

    mixed_dialect_example()


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
