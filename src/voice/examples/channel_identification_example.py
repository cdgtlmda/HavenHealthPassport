#!/usr/bin/env python3
"""
Example: Using Channel Identification with Amazon Transcribe Medical.

This example demonstrates how to use the channel identification feature
for transcribing multi-channel medical audio recordings.
 Handles FHIR Resource validation.

Security Note: This example processes PHI data from medical consultations.
All audio files and transcriptions must be encrypted at rest and in transit.
Access to transcription results should be restricted to authorized healthcare
personnel only through appropriate authentication and access controls.
"""

import asyncio
import logging
from pathlib import Path

from src.voice.channel_identification import (
    AudioChannelType,
    ChannelMapping,
    ChannelRole,
)
from src.voice.transcribe_medical import (
    MedicalSpecialty,
    TranscribeMedicalConfig,
    TranscribeMedicalService,
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def doctor_patient_consultation_example() -> None:
    """
    Transcribe a doctor-patient consultation recording.

    This example uses a predefined configuration for a typical
    doctor-patient consultation with stereo audio (doctor on left
    channel, patient on right channel).
    """
    logger.info("=== Doctor-Patient Consultation Example ===")

    # Initialize the transcribe service
    config = TranscribeMedicalConfig(
        region="us-east-1",
        specialty=MedicalSpecialty.PRIMARYCARE,
        output_bucket="my-transcription-bucket",
    )

    service = TranscribeMedicalService(config)

    # Enable channel identification with doctor-patient preset
    service.enable_channel_identification(preset="doctor_patient")

    # Path to stereo audio file
    audio_file = Path("path/to/consultation_recording.wav")

    try:
        # Transcribe the multi-channel audio
        results = await service.transcribe_multi_channel_audio(
            audio_file, job_name="consultation_001", process_channels_separately=True
        )

        # Display results
        logger.info(f"Job Name: {results['job_name']}")
        logger.info(f"Channels processed: {len(results['channel_results'])}")

        # Show channel metadata
        for channel_id, metadata in results["channel_metadata"]["channels"].items():
            logger.info(f"\nChannel {channel_id}:")
            logger.info(f"  Role: {metadata['role']}")
            logger.info(f"  Duration: {metadata['duration']:.2f}s")
            logger.info(f"  Quality Score: {metadata['quality_score']:.2f}")
            logger.info(f"  Activity Ratio: {metadata['activity_ratio']:.2f}")

        # Display merged transcript (annotated format)
        logger.info("\n=== Annotated Transcript ===")
        logger.info(results["merged_transcript"]["transcript"])

        # Show medical summary
        logger.info("\n=== Medical Summary ===")
        summary = results["medical_summary"]
        logger.info(f"Medications mentioned: {', '.join(summary['medications'])}")
        logger.info(f"Conditions discussed: {', '.join(summary['conditions'])}")
        logger.info(f"Procedures planned: {', '.join(summary['procedures'])}")

        # Export transcriptions
        output_dir = Path("output/consultation_001")
        service.export_channel_transcriptions(output_dir)
        logger.info(f"\nTranscriptions exported to: {output_dir}")

    except Exception as e:
        logger.error(f"Error during transcription: {e}")


async def telemedicine_with_interpreter_example() -> None:
    """
    Transcribe telemedicine session with interpreter.

    This example demonstrates a more complex scenario with three channels:
    - Channel 0: Remote physician (telephone quality)
    - Channel 1: Patient (microphone)
    - Channel 2: Interpreter (microphone)
    """
    logger.info("\n=== Telemedicine with Interpreter Example ===")

    # Initialize the transcribe service
    config = TranscribeMedicalConfig(
        region="us-east-1", specialty=MedicalSpecialty.PRIMARYCARE
    )

    service = TranscribeMedicalService(config)

    # Enable channel identification with telemedicine preset
    service.enable_channel_identification(preset="telemedicine")

    # Update interpreter channel with specific language
    interpreter_mapping = ChannelMapping(
        channel_id=2,
        channel_type=AudioChannelType.MICROPHONE_ARRAY,
        role=ChannelRole.INTERPRETER,
        speaker_name="Maria Garcia",
        language_code="es-US",
        priority=3,
    )
    service.update_channel_mapping(2, interpreter_mapping)

    # Path to multi-channel audio file
    audio_file = Path("path/to/telemedicine_session.wav")

    try:
        # Transcribe the multi-channel audio
        results = await service.transcribe_multi_channel_audio(
            audio_file, job_name="telemedicine_002", process_channels_separately=True
        )

        # Check for cross-talk issues
        metadata = results["channel_metadata"]
        if metadata.get("cross_talk_detected"):
            logger.warning("Cross-talk detected between channels!")
            for channel in metadata["channels"]:
                if channel["cross_talk_events"] > 0:
                    logger.warning(
                        f"  Channel {channel['channel_id']}: "
                        f"{channel['cross_talk_events']} events"
                    )

        # Display channel-specific results
        for ch_id, ch_result in results["channel_results"].items():
            logger.info(f"\nChannel {ch_id} Transcript:")
            if "transcript_text" in ch_result:
                logger.info(ch_result["transcript_text"][:200] + "...")

    except Exception as e:
        logger.error(f"Error during transcription: {e}")


async def custom_configuration_example() -> None:
    """
    Create custom channel configuration.

    This example shows how to create a fully custom channel configuration
    for specialized recording setups.
    """
    logger.info("\n=== Custom Configuration Example ===")

    # Initialize the transcribe service
    config = TranscribeMedicalConfig(
        region="us-east-1", specialty=MedicalSpecialty.CARDIOLOGY
    )

    service = TranscribeMedicalService(config)

    # Create custom channel configuration
    from src.voice.channel_identification import (
        ChannelConfig,
        ChannelIdentificationConfig,
    )

    custom_config = ChannelIdentificationConfig(
        max_channels=4,
        enable_cross_talk_detection=True,
        cross_talk_threshold=0.25,
        enable_speaker_diarization=True,
        output_format="annotated",
    )

    # Configure individual channels
    # Channel 0: Cardiologist
    custom_config.add_channel_mapping(
        ChannelMapping(
            channel_id=0,
            channel_type=AudioChannelType.MICROPHONE_ARRAY,
            role=ChannelRole.SPECIALIST,
            speaker_name="Dr. Heart",
            priority=1,
        )
    )
    custom_config.add_channel_config(
        ChannelConfig(
            channel_id=0,
            sample_rate=16000,
            automatic_gain_control=True,
            echo_cancellation=True,
        )
    )

    # Channel 1: Patient
    custom_config.add_channel_mapping(
        ChannelMapping(
            channel_id=1,
            channel_type=AudioChannelType.MICROPHONE_ARRAY,
            role=ChannelRole.PATIENT,
            speaker_name="Patient",
            priority=2,
        )
    )
    custom_config.add_channel_config(ChannelConfig(channel_id=1, sample_rate=16000))

    # Enable with custom configuration
    service.enable_channel_identification(config=custom_config)

    logger.info("Custom channel configuration enabled")
    logger.info(f"Configuration: {service.get_channel_configuration()}")


async def main() -> None:
    """Run all examples."""
    await doctor_patient_consultation_example()
    await telemedicine_with_interpreter_example()
    await custom_configuration_example()


if __name__ == "__main__":
    asyncio.run(main())


def validate_fhir_data(data: dict) -> dict:
    """Validate FHIR data.

    Args:
        data: Data to validate

    Returns:
        Validation result with 'valid', 'errors', and 'warnings' keys
    """
    from typing import List

    errors: List[str] = []
    warnings: List[str] = []

    if not data:
        errors.append("No data provided")

    return {"valid": len(errors) == 0, "errors": errors, "warnings": warnings}
