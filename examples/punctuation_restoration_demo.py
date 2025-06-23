"""
Punctuation Restoration Demo for Medical Transcriptions

This demonstrates intelligent punctuation restoration for
medical transcriptions.
"""

from src.voice.punctuation_restoration import PunctuationConfig, PunctuationRestorer


def demonstrate_punctuation_restoration():
    """Demonstrate punctuation restoration on medical text."""
    print("Medical Transcription Punctuation Restoration Demo")
    print("=" * 50)

    # Configure punctuation restorer
    config = PunctuationConfig(
        enable_sentence_boundaries=True,
        enable_commas=True,
        enable_medical_punctuation=True,
        preserve_medical_abbreviations=True,
        format_measurements=True,
        format_lists=True,
    )

    restorer = PunctuationRestorer(config)

    # Example medical transcriptions without punctuation
    examples = [
        # Basic medical consultation
        "patient presents with chest pain and shortness of breath blood pressure is 140 over 90 heart rate 85 prescribed lisinopril 10 mg daily",
        # Medical history
        "past medical history includes hypertension diabetes type 2 and hyperlipidemia current medications metformin 1000 mg twice daily atorvastatin 20 mg at bedtime",
        # Physical examination
        "on examination patient appears comfortable vital signs temperature 98 6 degrees F blood pressure 130 over 80 heart rate 72 respiratory rate 16",
        # Treatment plan with list
        "treatment plan includes first increase lisinopril to 20 mg daily second add hydrochlorothiazide 12 5 mg daily third follow up in 2 weeks",
        # Complex medical terms
        "patient diagnosed with COPD prescribed albuterol inhaler 2 puffs q i d prn and advair diskus 250 50 one puff b i d",
    ]
    # Process each example
    for i, text in enumerate(examples, 1):
        print(f"\nExample {i}:")
        print("-" * 40)
        print(f"Original: {text}")

        # Restore punctuation
        punctuated = restorer.restore_punctuation(text)
        print(f"\nPunctuated: {punctuated}")

        # Get statistics
        stats = restorer.get_statistics(text, punctuated)
        print(f"\nStatistics:")
        print(f"  - Sentences created: {stats['sentences_created']}")
        print(f"  - Commas added: {stats['punctuation_counts']['commas']}")
        print(f"  - Average sentence length: {stats['avg_sentence_length']:.1f} words")

    # Demonstrate segment-based restoration
    print("\n\nSegment-based Restoration:")
    print("=" * 50)

    segments = [
        {"text": "patient has history of diabetes", "confidence": 0.95},
        {"text": "blood sugar was 180 this morning", "confidence": 0.88},
        {"text": "prescribed insulin glargine", "confidence": 0.72},
        {"text": "20 units at bedtime", "confidence": 0.91},
    ]

    print("Input segments:")
    for seg in segments:
        print(f"  - '{seg['text']}' (confidence: {seg['confidence']})")

    # Restore with segments
    punctuated_segments = restorer.restore_from_segments(segments, join_segments=False)

    print("\nPunctuated segments:")
    for seg in punctuated_segments:
        print(f"  - '{seg}'")

    # Join into complete text
    complete_text = restorer.restore_from_segments(segments, join_segments=True)
    print(f"\nComplete punctuated text: {complete_text}")


def demonstrate_medical_formatting():
    """Demonstrate medical-specific formatting."""
    print("\n\nMedical Formatting Examples:")
    print("=" * 50)
    restorer = PunctuationRestorer()

    # Medical measurement examples
    measurements = [
        "blood pressure 120 over 80",
        "temperature 101 2 degrees F",
        "oxygen saturation 95 percent",
        "weight 150 pounds height 5 feet 10 inches",
        "glucose 126 mg per dl",
    ]

    print("\nMedical Measurements:")
    for measurement in measurements:
        punctuated = restorer.restore_punctuation(measurement)
        print(f"  {measurement} → {punctuated}")

    # Medication examples
    medications = [
        "metoprolol 50 mg twice daily",
        "insulin glargine 20 units subcutaneous at bedtime",
        "acetaminophen 650 mg p o q 6 hours prn pain",
        "albuterol 2 puffs q i d",
        "prednisone 40 mg daily times 5 days",
    ]

    print("\nMedication Instructions:")
    for medication in medications:
        punctuated = restorer.restore_punctuation(medication)
        print(f"  {medication} → {punctuated}")

    # List formatting
    list_text = "assessment and plan first continue current medications second order chest x ray third schedule follow up in one week fourth consider cardiology referral if symptoms persist"

    print("\nList Formatting:")
    print(f"Original: {list_text}")
    punctuated_list = restorer.restore_punctuation(list_text)
    print(f"Formatted: {punctuated_list}")


def main():
    """Run all demonstrations."""
    demonstrate_punctuation_restoration()
    demonstrate_medical_formatting()
    print("\n\nDemo completed!")


if __name__ == "__main__":
    main()
