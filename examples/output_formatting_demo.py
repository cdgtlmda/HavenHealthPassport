"""
Output Formatting Demo for Medical Transcriptions

This demonstrates formatting transcription results into various formats.
"""

from datetime import datetime
from pathlib import Path

from src.voice.confidence_thresholds import (
    MedicalTermType,
    TranscriptionResult,
    TranscriptionWord,
)
from src.voice.output_formatting import FormattingConfig, OutputFormat, OutputFormatter


def create_sample_transcription() -> TranscriptionResult:
    """Create a sample transcription result for demo."""
    words = [
        TranscriptionWord(
            text="Patient", confidence=0.95, start_time=0.0, end_time=0.5,
            speaker="Doctor"
        ),
        TranscriptionWord(
            text="presents", confidence=0.92, start_time=0.5, end_time=1.0,
            speaker="Doctor"
        ),
        TranscriptionWord(
            text="with", confidence=0.98, start_time=1.0, end_time=1.2,
            speaker="Doctor"
        ),
        TranscriptionWord(
            text="chest", confidence=0.89, start_time=1.2, end_time=1.5,
            speaker="Doctor"
        ),
        TranscriptionWord(
            text="pain", confidence=0.87, start_time=1.5, end_time=1.8,
            speaker="Doctor", term_type=MedicalTermType.SYMPTOM
        ),
        TranscriptionWord(
            text="and", confidence=0.99, start_time=1.8, end_time=2.0,
            speaker="Doctor"
        )        TranscriptionWord(
            text="shortness", confidence=0.72, start_time=2.0, end_time=2.5,
            speaker="Doctor"
        ),
        TranscriptionWord(
            text="of", confidence=0.95, start_time=2.5, end_time=2.6,
            speaker="Doctor"
        ),
        TranscriptionWord(
            text="breath.", confidence=0.78, start_time=2.6, end_time=3.0,
            speaker="Doctor", term_type=MedicalTermType.SYMPTOM
        ),
        TranscriptionWord(
            text="Blood", confidence=0.91, start_time=3.5, end_time=3.8,
            speaker="Doctor"
        ),
        TranscriptionWord(
            text="pressure", confidence=0.88, start_time=3.8, end_time=4.2,
            speaker="Doctor", term_type=MedicalTermType.VITAL_SIGN
        ),
        TranscriptionWord(
            text="is", confidence=0.99, start_time=4.2, end_time=4.3,
            speaker="Doctor"
        ),
        TranscriptionWord(
            text="140/90.", confidence=0.85, start_time=4.3, end_time=5.0,
            speaker="Doctor", term_type=MedicalTermType.LAB_VALUE
        ),
        TranscriptionWord(
            text="Prescribed", confidence=0.68, start_time=5.5, end_time=6.0,
            speaker="Doctor"
        ),
        TranscriptionWord(
            text="lisinopril", confidence=0.65, start_time=6.0, end_time=6.5,
            speaker="Doctor", term_type=MedicalTermType.MEDICATION
        ),
        TranscriptionWord(
            text="10mg", confidence=0.71, start_time=6.5, end_time=6.8,
            speaker="Doctor", term_type=MedicalTermType.DOSAGE
        ),
        TranscriptionWord(
            text="daily.", confidence=0.89, start_time=6.8, end_time=7.2,
            speaker="Doctor"
        )
    ]
    # Calculate transcript
    transcript = " ".join(w.text for w in words)

    # Identify words needing review (low confidence)
    words_needing_review = [w for w in words if w.confidence < 0.75]
    critical_terms = [w for w in words if w.term_type in [
        MedicalTermType.MEDICATION, MedicalTermType.DOSAGE
    ] and w.confidence < 0.80]

    return TranscriptionResult(
        transcript=transcript,
        words=words,
        overall_confidence=0.84,
        language_code="en-US",
        average_confidence=0.84,
        min_confidence=0.65,
        max_confidence=0.99,
        words_needing_review=words_needing_review,
        critical_terms_flagged=critical_terms
    )


def demonstrate_formats():
    """Demonstrate different output formats."""
    print("Medical Transcription Output Formatting Demo")
    print("=" * 50)

    # Create formatter with config
    config = FormattingConfig(
        include_timestamps=True,
        include_confidence_scores=True,
        include_speaker_labels=True,
        highlight_low_confidence=True,
        confidence_threshold=0.80,
        auto_section_detection=True,
        standardize_medical_terms=True
    )

    formatter = OutputFormatter(config)

    # Create sample transcription
    result = create_sample_transcription()

    # Additional metadata
    metadata = {
        "patient_id": "PAT001",
        "provider_id": "DOC123",
        "encounter_id": "ENC456",
        "facility": "Haven Health Clinic"
    }
    # Output directory
    output_dir = Path("output/formatted_transcriptions")
    output_dir.mkdir(parents=True, exist_ok=True)

    # Demonstrate each format
    formats = [
        OutputFormat.JSON,
        OutputFormat.XML,
        OutputFormat.TEXT,
        OutputFormat.MARKDOWN,
        OutputFormat.CSV,
        OutputFormat.SRT,
        OutputFormat.HL7,
        OutputFormat.FHIR
    ]

    for format_type in formats:
        print(f"\n{format_type.value.upper()} Format:")
        print("-" * 30)

        try:
            # Format the transcription
            formatted_doc = formatter.format_transcription(
                result, format_type, metadata
            )

            # Save to file
            filename = f"sample_transcription{formatted_doc.file_extension}"
            filepath = output_dir / filename
            formatted_doc.save(filepath)

            print(f"✓ Saved to: {filepath}")

            # Show preview
            if format_type in [OutputFormat.TEXT, OutputFormat.MARKDOWN]:
                preview = str(formatted_doc.content)[:200] + "..."
                print(f"Preview: {preview}")
            elif format_type == OutputFormat.JSON:
                print(f"Keys: {list(formatted_doc.content.keys())}")

        except Exception as e:
            print(f"✗ Error: {str(e)}")

    # Show statistics
    print(f"\n\nTranscription Statistics:")
    print(f"- Total words: {len(result.words)}")
    print(f"- Average confidence: {result.average_confidence:.2f}")
    print(f"- Words needing review: {len(result.words_needing_review)}")
    print(f"- Critical terms flagged: {len(result.critical_terms_flagged)}")
    # Show low confidence words
    if result.words_needing_review:
        print("\nWords needing review:")
        for word in result.words_needing_review:
            print(f"  - '{word.text}' (confidence: {word.confidence:.2f})")

    # Show critical medical terms
    if result.critical_terms_flagged:
        print("\nCritical medical terms with low confidence:")
        for term in result.critical_terms_flagged:
            print(f"  - '{term.text}' ({term.term_type.value}, confidence: {term.confidence:.2f})")


def main():
    """Run the output formatting demo."""
    demonstrate_formats()
    print("\n\nDemo completed!")


if __name__ == "__main__":
    main()
