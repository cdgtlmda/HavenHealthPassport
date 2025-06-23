"""
Demo script for Amazon Transcribe Medical Service

This script demonstrates the functionality of the Transcribe Medical service
for medical voice transcription.
"""

import asyncio
from pathlib import Path

from src.voice.transcribe_medical import (
    LanguageCode,
    MedicalSpecialty,
    TranscribeMedicalConfig,
    TranscribeMedicalService,
    TranscriptionType,
)


async def demo_transcribe_medical():
    """Demonstrate Transcribe Medical functionality."""

    print("🎤 Initializing Amazon Transcribe Medical Service...")

    # Create configuration
    config = TranscribeMedicalConfig(
        region="us-east-1",
        specialty=MedicalSpecialty.PRIMARYCARE,
        type=TranscriptionType.CONVERSATION,
        language_code=LanguageCode.EN_US,
        show_speaker_labels=True,
        content_redaction=True,  # Redact PHI
    )

    # Initialize service
    service = TranscribeMedicalService(config)

    # Check service status
    print("\n📊 Service Information:")
    service_info = service.get_service_info()
    print(f"   Service Available: {service_info['service_available']}")
    print(f"   Region: {service_info['region']}")
    print(
        f"   Supported Specialties: {', '.join(service_info['supported_specialties'])}"
    )
    print(f"   Supported Languages: {', '.join(service_info['supported_languages'])}")
    # Enable service
    print("\n🔧 Enabling Transcribe Medical Service...")
    enabled = await service.enable_service()

    if enabled:
        print("✅ Service successfully enabled!")
    else:
        print("❌ Failed to enable service")
        return

    # Demo transcription workflow
    print("\n📝 Demo Transcription Workflow:")

    # Example 1: Configure for different specialties
    print("\n1️⃣ Configuring for Different Medical Specialties:")

    specialties_demo = [
        (MedicalSpecialty.CARDIOLOGY, "Cardiology consultation"),
        (MedicalSpecialty.NEUROLOGY, "Neurology examination"),
        (MedicalSpecialty.RADIOLOGY, "Radiology report dictation"),
    ]

    for specialty, description in specialties_demo:
        print(f"   - {specialty.value}: {description}")

    # Example 2: Transcription settings
    print("\n2️⃣ Transcription Settings:")
    print(f"   - Speaker Identification: {config.show_speaker_labels}")
    print(f"   - Max Speakers: {config.max_speaker_labels}")
    print(f"   - PHI Redaction: {config.content_redaction}")
    print(f"   - Output Encryption: {config.output_encryption}")

    # Example 3: Mock transcription
    print("\n3️⃣ Mock Transcription Example:")
    print("   Input: 'Patient presents with chest pain radiating to left arm'")
    print("   Medical Entities Detected:")
    print("   - Symptom: 'chest pain' (Confidence: 0.95)")
    print("   - Anatomy: 'left arm' (Confidence: 0.92)")
    print("   - Clinical Finding: 'pain radiating' (Confidence: 0.88)")

    # Show configuration options
    print("\n⚙️  Configuration Options:")
    print(
        f"   - Supported Audio Formats: {', '.join(service_info['supported_formats'])}"
    )
    print(f"   - Sample Rate: {config.sample_rate} Hz")
    print(f"   - Output Bucket: {config.output_bucket}")

    print("\n✅ Transcribe Medical Demo Complete!")
    print("\nThe service provides:")
    print("   - High accuracy medical transcription")
    print("   - Medical entity recognition")
    print("   - PHI redaction for HIPAA compliance")
    print("   - Multi-speaker identification")
    print("   - Specialty-specific vocabularies")
    print("   - Real-time and batch processing options")


if __name__ == "__main__":
    asyncio.run(demo_transcribe_medical())
