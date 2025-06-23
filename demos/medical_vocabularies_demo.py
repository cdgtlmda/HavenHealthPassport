"""
Demo script for Medical Specialty Vocabularies

This script demonstrates the configuration and use of medical specialty
vocabularies for Amazon Transcribe Medical.
"""

import asyncio
from pathlib import Path

from src.voice.medical_vocabularies import (
    LanguageCode,
    MedicalSpecialty,
    MedicalTerm,
    MedicalVocabularyManager,
)


async def demo_medical_vocabularies():
    """Demonstrate medical vocabulary functionality."""

    print("🏥 Initializing Medical Vocabulary Manager...")
    manager = MedicalVocabularyManager()

    # Show available vocabularies
    print("\n📚 Available Medical Specialty Vocabularies:")
    for specialty in MedicalSpecialty:
        info = manager.get_vocabulary_info(specialty)
        if info:
            print(f"   - {info['specialty']}: {info['term_count']} terms")

    # Demo vocabulary terms
    print("\n🔍 Sample Terms from Each Specialty:")

    # Primary Care
    print("\n1️⃣ Primary Care Terms:")
    primary_care_vocab = manager.vocabularies.get("primarycare")
    if primary_care_vocab:
        for term in primary_care_vocab.terms[:3]:
            print(f"   - {term.term}")
            if term.sounds_like:
                print(f"     Sounds like: {', '.join(term.sounds_like)}")

    # Cardiology
    print("\n2️⃣ Cardiology Terms:")
    cardiology_vocab = manager.vocabularies.get("cardiology")
    if cardiology_vocab:
        for term in cardiology_vocab.terms[:3]:
            print(f"   - {term.term}")
            if term.display_as:
                print(f"     Display as: {term.display_as}")

    # Add custom terms
    print("\n➕ Adding Custom Terms:")
    custom_terms = [
        MedicalTerm(
            term="COVID-19", sounds_like=["koh-vid-nine-teen"], display_as="COVID-19"
        ),
        MedicalTerm(
            term="telemedicine",
            sounds_like=["tel-eh-med-ih-sin"],
            display_as="telemedicine",
        ),
    ]

    manager.add_custom_terms(MedicalSpecialty.PRIMARYCARE, custom_terms)
    print(f"   Added {len(custom_terms)} custom terms to Primary Care vocabulary")

    # Configure vocabularies
    print("\n🔧 Configuring Vocabularies in Transcribe Medical...")
    print("   (In production, this would create/update vocabularies in AWS)")

    # Simulate configuration
    for specialty in [MedicalSpecialty.PRIMARYCARE, MedicalSpecialty.CARDIOLOGY]:
        info = manager.get_vocabulary_info(specialty)
        if info:
            print(
                f"   - Would configure {info['name']} with {info['term_count']} terms"
            )

    # Export vocabulary
    print("\n💾 Exporting Vocabulary:")
    export_path = Path("cardiology_vocabulary.json")

    # Note: In demo, we'll skip actual export to avoid file creation
    print(f"   Would export cardiology vocabulary to: {export_path}")

    # Show vocabulary benefits
    print("\n✨ Benefits of Medical Vocabularies:")
    print("   - Improved accuracy for medical terminology")
    print("   - Better recognition of drug names")
    print("   - Accurate transcription of medical procedures")
    print("   - Support for medical abbreviations")
    print("   - Customizable for specific practices")

    print("\n✅ Medical Vocabularies Demo Complete!")


if __name__ == "__main__":
    asyncio.run(demo_medical_vocabularies())
