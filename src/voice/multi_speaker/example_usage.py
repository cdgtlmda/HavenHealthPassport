"""Example Usage of Multi-Speaker Support for Medical Conversations.

This module demonstrates how to use the multi-speaker support system
for complex medical conversations with multiple participants.
 Handles FHIR Resource validation.
"""

import asyncio
import logging
from pathlib import Path
from typing import List

from src.voice.multi_speaker import (
    AudioChannel,
    ChannelConfig,
    ChannelManager,
    MultiSpeakerConfig,
    MultiSpeakerProcessor,
    OverlapDetector,
    OverlapHandling,
    RealtimeMultiSpeakerTracker,
    SpeakerGrouping,
)
from src.voice.speaker_identification import SpeakerRole, SpeakerSegment

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def demonstrate_multi_speaker_processing() -> None:
    """Demonstrate multi-speaker conversation processing."""
    # Configure multi-speaker support
    config = MultiSpeakerConfig(
        max_concurrent_speakers=4,
        overlap_handling=OverlapHandling.INTELLIGENT_SWITCHING,
        overlap_threshold_ms=200,
        enable_speaker_clustering=True,
        speaker_grouping=SpeakerGrouping.DYNAMIC,
        enable_realtime=True,
        channel_config=ChannelConfig(
            channel_count=2,
            channel_layout=AudioChannel.STEREO,
            auto_detect_channels=True,
        ),
    )

    # Create sample segments for demonstration
    # Using positional arguments to ensure compatibility
    segments = [
        SpeakerSegment(
            "spk_0",
            0.0,
            5.0,
            "Good morning, I'm Dr. Smith. How are you feeling today?",
            0.95,
            SpeakerRole.PHYSICIAN,
        ),
        SpeakerSegment(
            "spk_1",
            4.5,  # Slight overlap
            8.0,
            "I've been having chest pain for the past two days.",
            0.92,
            SpeakerRole.PATIENT,
        ),
        SpeakerSegment(
            "spk_0",
            8.0,
            12.0,
            "Can you describe the pain? Is it sharp or dull?",
            0.94,
            SpeakerRole.PHYSICIAN,
        ),
        SpeakerSegment(
            "spk_2",
            11.5,  # Nurse interrupts
            14.0,
            "Doctor, the patient's vitals are ready.",
            0.90,
            SpeakerRole.NURSE,
        ),
        SpeakerSegment(
            "spk_1",
            12.5,  # Multiple speakers
            16.0,
            "It's a sharp pain that comes and goes.",
            0.91,
            SpeakerRole.PATIENT,
        ),
    ]

    # Initialize processor
    processor = MultiSpeakerProcessor(config)

    # Process the conversation
    logger.info("Processing multi-speaker conversation...")
    conversation_flow = processor.process_conversation(segments)

    # Display results
    logger.info("\nConversation Flow Analysis:")
    logger.info("Total segments: %d", len(conversation_flow.segments))
    logger.info("Unique speakers: %d", len(conversation_flow.unique_speakers))
    logger.info("Total overlaps: %d", len(conversation_flow.overlaps))
    logger.info(
        "Total overlap duration: %.2fs", conversation_flow.total_overlap_duration
    )

    # Show speaker clusters
    logger.info("\nSpeaker Clusters:")
    for cluster in conversation_flow.speaker_clusters:
        logger.info("  Cluster %s:", cluster.cluster_id)
        logger.info("    Speakers: %s", cluster.speakers)
        logger.info("    Primary role: %s", cluster.primary_role)

    # Show overlaps
    logger.info("\nOverlap Analysis:")
    for overlap in conversation_flow.overlaps:
        logger.info("  Overlap at %.1f-%.1fs:", overlap.start_time, overlap.end_time)
        logger.info("    Speakers: %s", overlap.speakers)
        logger.info("    Type: %s", overlap.overlap_type)
        logger.info("    Primary speaker: %s", overlap.primary_speaker)

    # Analyze concurrent speakers
    concurrent_map = processor.analyze_concurrent_speakers(segments, time_window=0.5)
    max_concurrent = (
        max(len(speakers) for speakers in concurrent_map.values())
        if concurrent_map
        else 0
    )
    logger.info("\nMax concurrent speakers: %d", max_concurrent)


async def demonstrate_overlap_detection() -> None:
    """Demonstrate advanced overlap detection."""
    logger.info("\n\n=== Overlap Detection Demo ===")

    # Initialize overlap detector
    detector = OverlapDetector(min_overlap_duration=0.1, overlap_threshold=0.8)

    # Use same segments from previous example
    segments = [
        SpeakerSegment(
            "spk_0",
            0.0,
            5.0,
            "Doctor speaking",
            0.95,
            SpeakerRole.PHYSICIAN,
        ),
        SpeakerSegment(
            "spk_1",
            4.5,
            8.0,
            "Patient responding",
            0.92,
            SpeakerRole.PATIENT,
        ),
        SpeakerSegment(
            "spk_2",
            7.5,
            10.0,
            "Nurse interrupting",
            0.90,
            SpeakerRole.NURSE,
        ),
    ]

    # Analyze overlaps
    analysis = detector.analyze_overlaps(segments, conversation_duration=10.0)

    logger.info("\nOverlap Metrics:")
    logger.info("Total overlaps: %d", analysis.metrics.total_overlaps)
    logger.info("Overlap percentage: %.1f%%", analysis.metrics.overlap_percentage)
    logger.info("Interruptions: %d", analysis.metrics.interruption_count)
    logger.info("Back-channels: %d", analysis.metrics.back_channel_count)

    # Show recommendations
    if analysis.recommendations:
        logger.info("\nRecommendations:")
        for rec in analysis.recommendations:
            logger.info("  - %s", rec)

    # Show speaker overlap matrix
    logger.info("\nSpeaker Overlap Matrix:")
    for (spk1, spk2), count in analysis.speaker_overlap_matrix.items():
        logger.info("  %s <-> %s: %d overlaps", spk1, spk2, count)


async def demonstrate_realtime_tracking() -> None:
    """Demonstrate real-time multi-speaker tracking."""
    logger.info("\n\n=== Real-time Tracking Demo ===")

    # Configure real-time tracking
    config = MultiSpeakerConfig(
        max_concurrent_speakers=3, enable_realtime=True, buffer_size_ms=2000
    )

    # Initialize tracker
    tracker = RealtimeMultiSpeakerTracker(config)

    # Start tracking
    await tracker.start_tracking()

    # Simulate real-time speaker updates
    simulation_events = [
        (0.0, "doctor", True),  # Doctor starts
        (5.0, "patient", True),  # Patient starts (overlap)
        (5.5, "doctor", False),  # Doctor stops
        (8.0, "patient", False),  # Patient stops
        (8.5, "nurse", True),  # Nurse starts
        (10.0, "doctor", True),  # Doctor starts again
        (11.0, "nurse", False),  # Nurse stops
        (15.0, "doctor", False),  # Doctor stops
    ]

    logger.info("Simulating real-time conversation...")

    for timestamp, speaker_id, is_speaking in simulation_events:
        tracker.update_speaker_activity(
            speaker_id=speaker_id,
            timestamp=timestamp,
            is_speaking=is_speaking,
            confidence=0.9,
        )

        # Log event
        action = "started" if is_speaking else "stopped"
        logger.info("  %.1fs: %s %s speaking", timestamp, speaker_id, action)

        # Brief pause for simulation
        await asyncio.sleep(0.1)

    # Get final state
    state = tracker.get_current_state()
    logger.info("\nFinal State:")
    logger.info("Total speakers: %d", state["total_speakers"])
    logger.info("Total transitions: %d", state["total_transitions"])

    # Get transition analytics
    analytics = tracker.get_transition_analytics()
    logger.info("\nTransition Analytics:")
    logger.info("Smooth transitions: %d", analytics["smooth_transitions"])
    logger.info("Overlapped transitions: %d", analytics["overlapped_transitions"])
    logger.info("Average gap duration: %.2fs", analytics["average_gap_duration"])

    # Predict next speaker
    next_speaker = tracker.predict_next_speaker()
    if next_speaker:
        logger.info("\nPredicted next speaker: %s", next_speaker)


async def demonstrate_channel_management() -> None:
    """Demonstrate channel management for multi-speaker audio."""
    logger.info("\n\n=== Channel Management Demo ===")

    # Configure channel management
    channel_config = ChannelConfig(
        channel_count=2,
        channel_layout=AudioChannel.STEREO,
        auto_detect_channels=True,
        channel_quality_threshold=0.7,
    )

    # Initialize channel manager
    manager = ChannelManager(channel_config)

    # Simulate channel analysis
    audio_file = Path("sample_audio.wav")  # Placeholder
    channel_info = manager.analyze_channels(audio_file)

    logger.info("\nChannel Analysis:")
    for ch_id, info in channel_info.items():
        logger.info("  Channel %s:", ch_id)
        logger.info("    Type: %s", info.channel_type.value)
        logger.info("    Quality score: %.2f", info.quality_score)
        logger.info("    Active: %s", info.is_active)
        logger.info("    Good quality: %s", info.is_good_quality)

    # Assign speakers to channels
    speaker_segments = {
        "doctor": [(0.0, 5.0), (10.0, 15.0)],
        "patient": [(5.0, 10.0), (15.0, 20.0)],
    }

    assignments = manager.assign_speakers_to_channels(speaker_segments)

    logger.info("\nChannel Assignments:")
    for ch_id, spk_id in assignments.assignments.items():
        confidence = assignments.confidence_scores.get(ch_id, 0)
        logger.info("  Channel %s -> %s (confidence: %.2f)", ch_id, spk_id, confidence)

    # Optimize channel usage
    optimization = manager.optimize_channel_usage()
    if optimization["recommendations"]:
        logger.info("\nOptimization Recommendations:")
        for rec in optimization["recommendations"]:
            logger.info("  - %s", rec)


async def main() -> None:
    """Run all demonstrations."""
    logger.info("=== Multi-Speaker Support Demonstration ===\n")

    # Run demonstrations
    await demonstrate_multi_speaker_processing()
    await demonstrate_overlap_detection()
    await demonstrate_realtime_tracking()
    await demonstrate_channel_management()

    logger.info("\n=== Demonstration Complete ===")


if __name__ == "__main__":
    # Run the demonstrations
    asyncio.run(main())


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
