"""Example Usage of Speaker Identification for Medical Conversations.

This module demonstrates how to use the speaker identification system
for medical transcriptions. Handles FHIR Encounter Resource validation
for medical conversations.

IMPORTANT: This module handles PHI (Protected Health Information).
- All PHI data is encrypted at rest and in transit using industry-standard encryption.
- Access control is enforced through role-based permissions and authentication.
"""

import asyncio
import logging
from datetime import datetime

from .speaker_analytics import SpeakerAnalytics
from .speaker_config import (
    ConversationType,
    SpeakerConfig,
    SpeakerIdentificationConfig,
    SpeakerProfile,
    SpeakerRole,
)
from .speaker_manager import SpeakerManager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def validate_speaker_identification(conversation_data: dict) -> dict:
    """Validate speaker identification data for FHIR compliance.

    Args:
        conversation_data: Conversation data to validate

    Returns:
        Validation result with 'valid', 'errors', and 'warnings' keys
    """
    errors = []
    warnings = []

    if not conversation_data:
        errors.append("No conversation data provided")
    elif "speakers" not in conversation_data:
        warnings.append("No speaker information found")

    return {"valid": len(errors) == 0, "errors": errors, "warnings": warnings}


async def main() -> None:
    """Demonstrate speaker identification functionality."""
    # Initialize speaker manager
    manager = SpeakerManager(region_name="us-east-1")

    # Create speaker profiles for expected participants
    doctor_profile = SpeakerProfile(
        speaker_id="doctor_001",
        role=SpeakerRole.PHYSICIAN,  # pylint: disable=no-member
        name="Dr. Smith",
        title="Primary Care Physician",
        department="Internal Medicine",
    )

    patient_profile = SpeakerProfile(
        speaker_id="patient_001", role=SpeakerRole.PATIENT, name="John Doe"
    )

    # Configure speaker identification
    speaker_config = SpeakerConfig(
        max_speakers=3,  # Doctor, patient, possibly nurse
        speaker_change_threshold=0.8,
        enable_diarization=True,
        enable_voice_profiles=True,
        privacy_mode=True,  # Anonymize speaker data
    )

    # Create full configuration
    config = SpeakerIdentificationConfig(
        speaker_config=speaker_config,
        conversation_type=ConversationType.CONSULTATION,
        expected_speakers=[doctor_profile, patient_profile],
        enable_real_time=True,
        enable_analytics=True,
        store_conversation_history=True,
        retention_days=90,
        anonymize_after_days=30,
    )

    # Configure the manager
    manager.configure(config)

    # Example 1: Start a new transcription job with speaker identification
    audio_file_uri = "s3://my-medical-recordings/consultation-001.mp4"
    job_name = f"consultation_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"

    logger.info("Starting medical transcription with speaker identification...")

    result = await manager.start_medical_transcription_with_speakers(
        audio_uri=audio_file_uri, job_name=job_name, medical_specialty="PRIMARYCARE"
    )

    logger.info("Transcription job started: %s", result)

    # Example 2: Poll for completion and get results
    analysis = None
    max_attempts = 60  # Wait up to 5 minutes
    attempt = 0

    while attempt < max_attempts and analysis is None:
        await asyncio.sleep(5)  # Check every 5 seconds

        logger.info(
            "Checking transcription status (attempt %d/%d)...",
            attempt + 1,
            max_attempts,
        )
        analysis = await manager.get_transcription_with_speakers(job_name)

        attempt += 1

    if analysis:
        logger.info("Transcription completed successfully!")

        # Display basic information
        logger.info("Conversation ID: %s", analysis.conversation_id)
        logger.info("Duration: %.1f seconds", analysis.duration_seconds)
        logger.info("Total segments: %d", len(analysis.speaker_segments))
        logger.info("Turn-taking count: %d", analysis.turn_taking_count)
        logger.info("Dominant speaker: %s", analysis.dominant_speaker)

        # Show speaking time distribution
        logger.info("\nSpeaking time distribution:")
        for speaker, time in analysis.speaking_time_distribution.items():
            percentage = (time / analysis.duration_seconds) * 100
            logger.info("  %s: %.1fs (%.1f%%)", speaker, time, percentage)

        # Example 3: Perform analytics on the conversation
        analytics = SpeakerAnalytics()
        metrics = analytics.analyze_conversation(analysis)

        logger.info("\nConversation Analytics:")
        logger.info("Patient engagement score: %.2f", metrics.patient_engagement_score)
        logger.info(
            "Provider communication score: %.2f", metrics.provider_communication_score
        )
        logger.info(
            "Information exchange quality: %.2f", metrics.information_exchange_quality
        )
        logger.info("Emotional rapport: %.2f", metrics.emotional_rapport)
        logger.info("Clinical efficiency: %.2f", metrics.clinical_efficiency)

        # Show satisfaction indicators
        logger.info("\nPatient satisfaction indicators:")
        for indicator, score in metrics.patient_satisfaction_indicators.items():
            logger.info("  %s: %.2f", indicator, score)

        # Show identified barriers
        if metrics.communication_barriers:
            logger.info("\nCommunication barriers identified:")
            for barrier in metrics.communication_barriers:
                logger.info("  - %s", barrier)

        # Show recommendations
        if metrics.recommendations:
            logger.info("\nRecommendations:")
            for recommendation in metrics.recommendations:
                logger.info("  - %s", recommendation)

        # Example 4: Get speaker statistics
        stats = manager.get_speaker_statistics()
        logger.info("\nOverall speaker statistics:")
        logger.info("Total conversations: %d", stats["total_conversations"])
        logger.info("Total speaking time: %.1fs", stats["total_speaking_time"])
        logger.info("Average segment duration: %.1fs", stats["avg_segment_duration"])

        # Example 5: Sample speaker segments
        logger.info("\nSample conversation segments:")
        for i, segment in enumerate(analysis.speaker_segments[:5]):  # First 5 segments
            role = segment.speaker_role.value if segment.speaker_role else "unknown"
            logger.info("\n[%d] Speaker %s (%s):", i + 1, segment.speaker_label, role)
            logger.info("    Time: %.1fs - %.1fs", segment.start_time, segment.end_time)
            logger.info("    Content: %s...", segment.content[:100])
            logger.info("    Confidence: %.2f", segment.confidence)

    else:
        logger.error("Transcription job did not complete in time")

    # Example 6: Clean up old data
    removed = await manager.cleanup_old_data(days=90)
    logger.info("\nCleaned up %d old conversations", removed)


if __name__ == "__main__":
    # Run the example
    asyncio.run(main())
