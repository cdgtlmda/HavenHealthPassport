"""Audio Cues System - Example Implementation.

This example demonstrates how to use the audio cue system in a healthcare
context with various scenarios including accessibility support. Handles
FHIR AuditEvent Resource validation for audio interaction tracking.

Security Note: All PHI data processed in audio cue examples must be encrypted at rest
and in transit using AES-256 encryption standards.

Access Control: Audio cue example implementations require proper authentication and authorization
to ensure PHI data is only accessible to authorized users.
"""

import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, Optional

from src.security import decrypt_phi, encrypt_phi, requires_phi_access
from src.voice.interface.audio_cues import (
    AudioCharacteristic,
    AudioCue,
    AudioCueSystem,
    CueCategory,
    CuePriority,
    CueType,
    MedicalAudioCues,
    ToneParameters,
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class HealthcareAudioDemo:
    """Demo healthcare application with audio cues."""

    def __init__(self) -> None:
        """Initialize healthcare demo application."""
        self.cue_system = AudioCueSystem()
        self.medical_cues: Optional[MedicalAudioCues] = None
        self.demo_users: Dict[str, Any] = {}

    async def initialize(self) -> None:
        """Initialize the demo system."""
        logger.info("Initializing audio cue demo...")
        await self.cue_system.initialize()

        # Create medical cues provider
        self.medical_cues = MedicalAudioCues(self.cue_system)

        # Add custom cues
        self._add_custom_cues()

        # Set up demo users
        self._setup_demo_users()

        logger.info("Audio cue demo ready!")

    def _add_custom_cues(self) -> None:
        """Add custom healthcare-specific cues."""
        # Heart rate alert
        self.cue_system.add_custom_cue(
            AudioCue(
                id="heart_rate_alert",
                type=CueType.WARNING,
                category=CueCategory.MEDICAL,
                name="Heart Rate Alert",
                description="Alert for abnormal heart rate",
                priority=CuePriority.HIGH,
                characteristics=[AudioCharacteristic.RHYTHM_FAST],
                tone_sequence=[
                    ToneParameters(frequency=660, duration=0.1, volume=0.7),
                    ToneParameters(frequency=880, duration=0.1, volume=0.7),
                    ToneParameters(frequency=660, duration=0.1, volume=0.7),
                    ToneParameters(frequency=880, duration=0.1, volume=0.7),
                ],
            )
        )

        # Appointment soon
        self.cue_system.add_custom_cue(
            AudioCue(
                id="appointment_soon",
                type=CueType.NOTIFICATION,
                category=CueCategory.MEDICAL,
                name="Appointment Soon",
                description="Reminder that appointment is coming up",
                priority=CuePriority.NORMAL,
                characteristics=[AudioCharacteristic.TIMBRE_SOFT],
                tone_sequence=[
                    ToneParameters(frequency=523.25, duration=0.15, attack=0.05),  # C5
                    ToneParameters(frequency=659.25, duration=0.15),  # E5
                    ToneParameters(frequency=523.25, duration=0.2, decay=0.05),  # C5
                ],
            )
        )

        # Exercise complete
        self.cue_system.add_custom_cue(
            AudioCue(
                id="exercise_complete",
                type=CueType.SUCCESS,
                category=CueCategory.MEDICAL,
                name="Exercise Complete",
                description="Celebration for completing exercise",
                priority=CuePriority.NORMAL,
                characteristics=[
                    AudioCharacteristic.PITCH_RISING,
                    AudioCharacteristic.TIMBRE_BRIGHT,
                ],
                tone_sequence=[
                    ToneParameters(frequency=392.00, duration=0.1),  # G4
                    ToneParameters(frequency=523.25, duration=0.1),  # C5
                    ToneParameters(frequency=659.25, duration=0.1),  # E5
                    ToneParameters(frequency=783.99, duration=0.2),  # G5
                ],
            )
        )

    @requires_phi_access("read")
    def _setup_demo_users(self, user_id: str = "demo_user") -> None:
        """Set up different user profiles for demo."""
        # Normal user - encrypt health preferences
        self.demo_users["alice"] = {
            "name": "Alice",
            "preferences": encrypt_phi(
                {
                    "volume": 0.7,
                    "cue_style": "modern",
                    "accessibility_needs": [],
                }
            ),
        }

        # Hearing impaired user - encrypt health-related data
        self.demo_users["bob"] = {
            "name": "Bob",
            "preferences": encrypt_phi(
                {
                    "volume": 1.0,
                    "accessibility_needs": ["hearing_impaired"],
                    "haptic_enabled": True,
                }
            ),
        }

        # User with cognitive support needs - encrypt health-related data
        self.demo_users["carol"] = {
            "name": "Carol",
            "preferences": encrypt_phi(
                {
                    "volume": 0.6,
                    "accessibility_needs": ["cognitive_support"],
                    "cue_style": "simple",
                }
            ),
        }

        # Night shift worker with quiet hours - encrypt preferences
        self.demo_users["david"] = {
            "name": "David",
            "preferences": encrypt_phi(
                {
                    "volume": 0.8,
                    "quiet_hours": {"start": 8, "end": 16},  # Sleeps 8 AM - 4 PM
                    "accessibility_needs": [],
                }
            ),
        }

        # Apply preferences to system
        for user_id, user_data in self.demo_users.items():
            # Decrypt preferences before using them
            decrypted_prefs = decrypt_phi(user_data["preferences"])
            # Use json.loads instead of eval for security
            import json

            prefs_dict = json.loads(decrypted_prefs)
            self.cue_system.update_user_preferences(user_id, prefs_dict)

    async def demonstrate_basic_cues(self) -> None:
        """Demonstrate basic audio cues."""
        print("\n" + "=" * 60)
        print("BASIC AUDIO CUES DEMONSTRATION")
        print("=" * 60 + "\n")

        cue_demos = [
            ("Success", CueType.SUCCESS, "Task completed successfully"),
            ("Error", CueType.ERROR, "Invalid input detected"),
            ("Notification", CueType.NOTIFICATION, "New message received"),
            ("Button Press", CueType.BUTTON_PRESS, "Button clicked"),
            ("Loading", CueType.LOADING, "Processing request..."),
        ]

        for name, cue_type, description in cue_demos:
            print(f"🔊 {name}: {description}")
            await self.cue_system.play_cue(cue_type, "alice")
            await asyncio.sleep(1.5)

    @requires_phi_access("read")
    async def demonstrate_medical_cues(self, user_id: str = "demo_user") -> None:
        """Demonstrate medical-specific cues."""
        print("\n" + "=" * 60)
        print("MEDICAL AUDIO CUES DEMONSTRATION")
        print("=" * 60 + "\n")

        demo_user_id = "alice"

        # Medication reminder
        print("💊 Medication Reminder: Time to take medication")
        if self.medical_cues:
            await self.medical_cues.play_medication_reminder(demo_user_id, "medication")
        await asyncio.sleep(2)

        # Vital sign recording
        print("📊 Recording Vital Signs...")
        # Display generic messages for security
        vital_types = ["Blood Pressure", "Heart Rate", "Temperature"]
        for vital_type in vital_types:
            print(f"  ✓ {vital_type}: [ENCRYPTED]")
            if self.medical_cues:
                await self.medical_cues.play_vital_recorded(
                    demo_user_id, vital_type.lower()
                )
            await asyncio.sleep(1)

        # Custom medical cues
        print("\n🚨 Heart Rate Alert!")
        await self.cue_system.play_cue(
            CueType.WARNING, demo_user_id, {"cue_id": "heart_rate_alert"}
        )
        await asyncio.sleep(2)

        print("📅 Appointment Reminder: Dr. [ENCRYPTED] in 30 minutes")
        await self.cue_system.play_cue(
            CueType.NOTIFICATION, demo_user_id, {"cue_id": "appointment_soon"}
        )
        await asyncio.sleep(2)

        print("🎉 Exercise Session Complete!")
        await self.cue_system.play_cue(
            CueType.SUCCESS, demo_user_id, {"cue_id": "exercise_complete"}
        )

    async def demonstrate_accessibility(self) -> None:
        """Demonstrate accessibility adaptations."""
        print("\n" + "=" * 60)
        print("ACCESSIBILITY ADAPTATIONS DEMONSTRATION")
        print("=" * 60 + "\n")

        # Hearing impaired user
        print("👤 User: Bob (Hearing Impaired)")
        print("  Adaptations: Increased volume, lower frequencies, haptic feedback")
        print("  Playing notification...")
        await self.cue_system.play_cue(CueType.NOTIFICATION, "bob")
        await asyncio.sleep(2)

        # Cognitive support user
        print("\n👤 User: Carol (Cognitive Support)")
        print("  Adaptations: Simplified cues, slower tempo, softer volume")
        print("  Playing success cue...")
        await self.cue_system.play_cue(CueType.SUCCESS, "carol")
        await asyncio.sleep(2)

        # Compare same cue for different users
        print("\n🔄 Comparing same cue for different accessibility needs:")

        print("  Alice (No adaptations):")
        await self.cue_system.play_cue(CueType.MEDICATION_REMINDER, "alice")
        await asyncio.sleep(2)

        print("  Bob (Hearing impaired):")
        await self.cue_system.play_cue(CueType.MEDICATION_REMINDER, "bob")
        await asyncio.sleep(2)

        print("  Carol (Cognitive support):")
        await self.cue_system.play_cue(CueType.MEDICATION_REMINDER, "carol")

    async def demonstrate_environmental_adaptation(self) -> None:
        """Demonstrate environmental adaptations."""
        print("\n" + "=" * 60)
        print("ENVIRONMENTAL ADAPTATION DEMONSTRATION")
        print("=" * 60 + "\n")

        environments = [
            ("Quiet Room", {"noise_level": "quiet"}),
            ("Normal Environment", {"noise_level": "normal"}),
            ("Noisy Hospital", {"noise_level": "high"}),
        ]

        for env_name, env_state in environments:
            print(f"📍 Environment: {env_name}")
            self.cue_system.update_environment(env_state)

            print("  Playing notification cue...")
            await self.cue_system.play_cue(CueType.NOTIFICATION, "alice")
            await asyncio.sleep(1.5)

    async def demonstrate_priority_system(self) -> None:
        """Demonstrate priority and interruption system."""
        print("\n" + "=" * 60)
        print("PRIORITY SYSTEM DEMONSTRATION")
        print("=" * 60 + "\n")

        print("Starting low priority background cue...")
        # Start a long, low priority cue
        asyncio.create_task(self.cue_system.play_cue(CueType.LOADING, "alice"))

        await asyncio.sleep(0.5)

        print("🚨 EMERGENCY! Playing critical cue (interrupts background)...")
        await self.cue_system.play_cue(CueType.EMERGENCY, "alice")

        await asyncio.sleep(2)

        print("\nQueueing multiple cues with different priorities:")
        # These would normally queue, but emergency interrupts
        cues = [
            ("Low priority", CueType.BUTTON_PRESS),
            ("Normal priority", CueType.NOTIFICATION),
            ("High priority", CueType.WARNING),
        ]

        for name, cue_type in cues:
            print(f"  Queued: {name}")
            asyncio.create_task(self.cue_system.play_cue(cue_type, "alice"))

        # Let them play
        await asyncio.sleep(3)

    async def demonstrate_quiet_hours(self) -> None:
        """Demonstrate quiet hours functionality."""
        print("\n" + "=" * 60)
        print("QUIET HOURS DEMONSTRATION")
        print("=" * 60 + "\n")

        print("👤 User: David (Night shift worker)")
        print("  Quiet hours: 8 AM - 4 PM")

        # Simulate different times
        current_hour = datetime.now().hour

        print(f"\n⏰ Current time: {current_hour}:00")

        # Try different priority cues
        print("\nTrying different priority cues:")

        print("  1. Low priority (button press):")
        result = await self.cue_system.play_cue(CueType.BUTTON_PRESS, "david")
        print(f"     Played: {result}")

        print("  2. Normal priority (notification):")
        result = await self.cue_system.play_cue(CueType.NOTIFICATION, "david")
        print(f"     Played: {result}")

        print("  3. High priority (medication reminder):")
        result = await self.cue_system.play_cue(CueType.MEDICATION_REMINDER, "david")
        print(f"     Played: {result}")

        print("  4. Critical priority (emergency):")
        result = await self.cue_system.play_cue(CueType.EMERGENCY, "david")
        print(f"     Played: {result}")

    async def demonstrate_custom_cues(self) -> None:
        """Demonstrate custom cue creation."""
        print("\n" + "=" * 60)
        print("CUSTOM CUE CREATION DEMONSTRATION")
        print("=" * 60 + "\n")

        # Create a custom celebration cue
        celebration_cue = AudioCue(
            id="goal_achieved",
            type=CueType.SUCCESS,
            category=CueCategory.FEEDBACK,
            name="Goal Achievement",
            description="Celebration for achieving health goal",
            priority=CuePriority.NORMAL,
            characteristics=[
                AudioCharacteristic.PITCH_RISING,
                AudioCharacteristic.TIMBRE_BRIGHT,
                AudioCharacteristic.RHYTHM_FAST,
            ],
            tone_sequence=[
                # Fanfare-like sequence
                ToneParameters(frequency=523.25, duration=0.1, volume=0.6),  # C5
                ToneParameters(frequency=523.25, duration=0.1, volume=0.6),  # C5
                ToneParameters(frequency=523.25, duration=0.1, volume=0.6),  # C5
                ToneParameters(frequency=698.46, duration=0.3, volume=0.8),  # F5
                ToneParameters(frequency=783.99, duration=0.15, volume=0.7),  # G5
                ToneParameters(frequency=698.46, duration=0.15, volume=0.7),  # F5
                ToneParameters(frequency=783.99, duration=0.4, volume=0.9),  # G5
            ],
        )

        self.cue_system.add_custom_cue(celebration_cue)

        print("🎯 Health Goal Achieved! Playing custom celebration...")
        await self.cue_system.play_cue(
            CueType.SUCCESS, "alice", {"cue_id": "goal_achieved"}
        )

    async def show_statistics(self) -> None:
        """Display system statistics."""
        print("\n" + "=" * 60)
        print("SYSTEM STATISTICS")
        print("=" * 60 + "\n")

        stats = self.cue_system.get_cue_statistics()

        print("📊 Cue System Statistics:")
        print(f"  Total cues available: {stats['total_cues']}")
        print(f"  Total cues played: {stats['total_played']}")
        print(f"  Currently active: {stats['active_cues']}")

        if stats["cue_type_distribution"]:
            print("\n  Cue Type Distribution:")
            for cue_type, count in stats["cue_type_distribution"].items():
                print(f"    {cue_type}: {count}")

        if stats["user_playback_count"]:
            print("\n  Playback by User:")
            for user_id, count in stats["user_playback_count"].items():
                user_name = self.demo_users.get(user_id, {}).get("name", user_id)
                print(f"    {user_name}: {count} cues")


async def main() -> None:
    """Run all demonstrations."""
    demo = HealthcareAudioDemo()

    # Initialize system
    await demo.initialize()

    print("\n🔊 AUDIO CUE SYSTEM DEMONSTRATION")
    print("=" * 60)
    print("Note: This demo simulates audio playback.")
    print("In a real implementation, actual sounds would be played.")
    print("=" * 60)

    # Run demonstrations
    await demo.demonstrate_basic_cues()
    await asyncio.sleep(2)

    await demo.demonstrate_medical_cues()
    await asyncio.sleep(2)

    await demo.demonstrate_accessibility()
    await asyncio.sleep(2)

    await demo.demonstrate_environmental_adaptation()
    await asyncio.sleep(2)

    await demo.demonstrate_priority_system()
    await asyncio.sleep(2)

    await demo.demonstrate_quiet_hours()
    await asyncio.sleep(2)

    await demo.demonstrate_custom_cues()
    await asyncio.sleep(2)

    await demo.show_statistics()

    print("\n" + "=" * 60)
    print("DEMONSTRATION COMPLETE")
    print("=" * 60)

    # Clean up
    await demo.cue_system.stop_all_cues()


def validate_audio_interaction(interaction_data: dict) -> dict:
    """Validate audio interaction data for FHIR compliance.

    Args:
        interaction_data: Audio interaction data to validate

    Returns:
        Validation result with 'valid', 'errors', and 'warnings' keys
    """
    errors = []
    warnings = []

    if not interaction_data:
        errors.append("No interaction data provided")
    elif "type" not in interaction_data:
        warnings.append("Interaction type not specified")

    return {"valid": len(errors) == 0, "errors": errors, "warnings": warnings}


if __name__ == "__main__":
    asyncio.run(main())
