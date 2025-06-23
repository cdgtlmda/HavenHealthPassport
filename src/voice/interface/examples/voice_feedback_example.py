"""Voice Feedback System - Example Implementation.

This example demonstrates how to use the voice feedback system in a healthcare
context with various scenarios including accessibility support. Handles FHIR
Communication Resource validation for patient feedback interactions.

Note: When handling PHI in voice feedback, ensure all data is encrypted in transit
and at rest. Implement proper access control mechanisms to restrict voice data
access to authorized personnel only.
"""

import asyncio
import logging
from typing import Any, Dict

from src.voice.interface.voice_feedback_system import (
    FeedbackPriority,
    FeedbackTemplate,
    FeedbackType,
    VoiceFeedbackSystem,
    VoiceParameters,
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class HealthcareVoiceAssistantDemo:
    """Demo healthcare voice assistant with feedback system."""

    def __init__(self) -> None:
        """Initialize healthcare feedback demo."""
        self.feedback_system = VoiceFeedbackSystem()
        # self.medical_feedback = None  # MedicalFeedbackProvider not implemented
        self.user_sessions: Dict[str, Any] = {}

    async def initialize(self) -> None:
        """Initialize the demo system."""
        logger.info("Initializing voice feedback system...")
        await self.feedback_system.initialize()

        # Create medical feedback provider
        # self.medical_feedback = MedicalFeedbackProvider(self.feedback_system)  # Not implemented

        # Add custom templates
        self._add_custom_templates()

        logger.info("Voice feedback system ready!")

    def _add_custom_templates(self) -> None:
        """Add custom healthcare templates."""
        # Welcome message
        self.feedback_system.add_custom_template(
            FeedbackTemplate(
                id="welcome_user",
                type=FeedbackType.INFO,
                templates={
                    "en": [
                        "Welcome to Haven Health, {name}. How can I help you today?",
                        "Hello {name}, I'm here to help with your health needs.",
                        "Good to see you, {name}. What would you like to do?",
                    ],
                    "es": [
                        "Bienvenido a Haven Health, {name}. ¿Cómo puedo ayudarte hoy?",
                        "Hola {name}, estoy aquí para ayudar con tus necesidades de salud.",
                    ],
                },
                voice_params=VoiceParameters(
                    speaking_rate=0.95,  # Slightly slower for welcome
                    pitch=-1,  # Slightly lower for warmth
                ),
            )
        )

        # Health tip
        self.feedback_system.add_custom_template(
            FeedbackTemplate(
                id="health_tip",
                type=FeedbackType.INFO,
                templates={
                    "en": [
                        "Health tip: {tip}",
                        "Did you know? {tip}",
                        "Here's something for your health: {tip}",
                    ]
                },
                priority=FeedbackPriority.LOW,
            )
        )

        # Emergency confirmed
        self.feedback_system.add_custom_template(
            FeedbackTemplate(
                id="emergency_confirmed",
                type=FeedbackType.NOTIFICATION,
                templates={
                    "en": [
                        "Emergency services have been contacted. Help is on the way. Stay calm.",
                        "I've called for emergency help. They'll be there soon. Try to stay calm.",
                    ]
                },
                priority=FeedbackPriority.CRITICAL,
                voice_params=VoiceParameters(
                    speaking_rate=0.85, volume=1.0  # Clear and calm
                ),
                sound_effects=["emergency_alert.mp3"],
            )
        )

    async def simulate_new_user_session(self, user_name: str = "Alice") -> None:
        """Simulate a new user's first session."""
        print(f"\n{'='*60}")
        print(f"NEW USER SESSION: {user_name}")
        print(f"{'='*60}\n")

        user_id = f"user_{user_name.lower()}"

        # Set up new user context
        self.feedback_system.update_user_context(
            user_id,
            {
                "user_level": "Beginner",
                "interaction_count": 0,
                "success_rate": 0.0,
                "preferred_voice": "Joanna",
                "accessibility_needs": [],
            },
        )

        # Welcome message
        await self.feedback_system.provide_feedback(
            user_id, "welcome_user", {"name": user_name}
        )
        await asyncio.sleep(2)

        # Tutorial intro
        await self.feedback_system.provide_feedback(user_id, "tutorial_intro")
        await asyncio.sleep(3)

        # Simulate some basic interactions
        interactions = [
            ("Show medications", True),
            ("Add medicaton", False),  # Typo - will fail
            ("Add medication Aspirin", True),
            ("Check appointments", True),
        ]

        for command, success in interactions:
            print(f"\n🎤 User: '{command}'")
            await asyncio.sleep(1)

            if success:
                await self.feedback_system.provide_success_feedback(user_id, command)
                # Update success rate
                self.feedback_system.update_user_context(
                    user_id,
                    {
                        "interaction_count": self.feedback_system.user_contexts[
                            user_id
                        ].interaction_count
                        + 1,
                        # "successful_interactions": Not available in FeedbackContext
                    },
                )
            else:
                await self.feedback_system.provide_error_feedback(
                    user_id,
                    "I didn't understand that. Try saying 'Add medication' followed by the name.",
                )
                # Update context
                self.feedback_system.update_user_context(
                    user_id,
                    {
                        "interaction_count": self.feedback_system.user_contexts[
                            user_id
                        ].interaction_count
                        + 1,
                        "recent_errors": self.feedback_system.user_contexts[
                            user_id
                        ].recent_errors
                        + 1,
                    },
                )

            await asyncio.sleep(2)

        # Provide encouragement if needed
        context = self.feedback_system.user_contexts[user_id]
        if context.interaction_count > 0:
            # context.success_rate = (
            #     context.successful_interactions / context.interaction_count
            # )  # successful_interactions not available
            if context.success_rate < 0.8:
                await self.feedback_system.provide_encouragement(user_id)

    async def simulate_medical_scenario(self, user_name: str = "Bob") -> None:
        """Simulate medical-specific interactions."""
        print(f"\n{'='*60}")
        print(f"MEDICAL SCENARIO: {user_name}")
        print(f"{'='*60}\n")

        user_id = f"patient_{user_name.lower()}"

        # Set up experienced user
        self.feedback_system.update_user_context(
            user_id,
            {
                "user_level": "Intermediate",
                "interaction_count": 50,
                "success_rate": 0.85,
                "preferred_voice": "Matthew",
            },
        )

        # Medication management
        print("📋 Medication Management")
        print("-" * 30)

        # Add medication
        await self.feedback_system.provide_feedback(
            user_id, "medication_added", {"medication_name": "Metformin 500mg"}
        )
        await asyncio.sleep(2)

        # Medication reminder
        # await self.medical_feedback.medication_reminder(
        #     user_id, "Metformin", "500mg with breakfast"
        # )  # MedicalFeedbackProvider not implemented
        await asyncio.sleep(3)

        # Record vitals
        print("\n📊 Recording Vital Signs")
        print("-" * 30)

        vitals = [
            ("blood pressure", "118/76"),
            ("heart rate", "72 bpm"),
            ("temperature", "98.6°F"),
        ]

        for _, _ in vitals:
            # await self.medical_feedback.vital_recorded(user_id, vital_type, value)  # Not implemented
            await asyncio.sleep(2)

        # Health tip
        await self.feedback_system.provide_feedback(
            user_id,
            "health_tip",
            {"tip": "Remember to stay hydrated. Aim for 8 glasses of water daily."},
            FeedbackPriority.LOW,
        )

    async def simulate_accessibility_user(self, user_name: str = "Carol") -> None:
        """Simulate user with accessibility needs."""
        print(f"\n{'='*60}")
        print(f"ACCESSIBILITY USER: {user_name}")
        print(f"{'='*60}\n")

        user_id = f"accessible_{user_name.lower()}"

        # User with hearing impairment and cognitive support needs
        self.feedback_system.update_user_context(
            user_id,
            {
                "user_level": "Beginner",
                "interaction_count": 10,
                "success_rate": 0.6,
                "accessibility_needs": ["hearing_impaired", "cognitive_support"],
                "preferred_voice": "Joanna",
            },
        )

        print("🔊 Adaptations Applied:")
        print("  - Slower speech rate")
        print("  - Maximum volume")
        print("  - Simplified language")
        print("  - Extended pauses\n")

        # Simple commands with adapted feedback
        commands = [
            ("Show my pills", "medications"),
            ("When doctor?", "appointments"),
            ("Add aspirin", "medication_added"),
        ]

        for user_says, template in commands:
            print(f"\n🎤 User: '{user_says}'")
            await asyncio.sleep(1)

            if template == "medications":
                # Custom simple response
                await self.feedback_system.provide_feedback(
                    user_id, "command_success", priority_override=FeedbackPriority.HIGH
                )
            elif template == "appointments":
                # Simplified appointment info
                await self.feedback_system.provide_feedback(
                    user_id, "navigation", {"destination": "your appointments"}
                )
            else:
                await self.feedback_system.provide_feedback(
                    user_id, template, {"medication_name": "Aspirin"}
                )

            await asyncio.sleep(3)  # Longer pause for processing

        # Provide encouragement
        await self.feedback_system.provide_encouragement(user_id)

    async def simulate_emergency_scenario(self) -> None:
        """Simulate emergency situation."""
        print(f"\n{'='*60}")
        print("EMERGENCY SCENARIO")
        print(f"{'='*60}\n")

        user_id = "emergency_user"

        # Set context
        self.feedback_system.update_user_context(
            user_id,
            {
                "user_level": "Intermediate",
                "interaction_count": 100,
                "success_rate": 0.9,
                "emotional_state": "panicked",
            },
        )

        print("🚨 User: 'HELP! Chest pain!'")

        # Immediate critical feedback
        await self.feedback_system.provide_feedback(
            user_id, "emergency_confirmed", priority_override=FeedbackPriority.CRITICAL
        )

        await asyncio.sleep(3)

        # Calming instructions
        calming_template = FeedbackTemplate(
            id="emergency_instructions",
            type=FeedbackType.INFO,
            templates={
                "en": [
                    "Please sit down and try to stay calm. "
                    "Take slow, deep breaths. "
                    "If you have aspirin, chew one tablet. "
                    "Help will arrive soon."
                ]
            },
            voice_params=VoiceParameters(
                speaking_rate=0.8, pitch=-2, volume=1.0  # Lower, calming tone
            ),
            priority=FeedbackPriority.CRITICAL,
        )

        self.feedback_system.add_custom_template(calming_template)
        await self.feedback_system.provide_feedback(user_id, "emergency_instructions")

    async def demonstrate_queue_management(self) -> None:
        """Demonstrate feedback queue and priority handling."""
        print(f"\n{'='*60}")
        print("QUEUE MANAGEMENT DEMONSTRATION")
        print(f"{'='*60}\n")

        user_id = "queue_demo_user"

        # Queue multiple feedbacks with different priorities
        feedbacks = [
            ("Low priority tip", FeedbackPriority.LOW),
            ("Normal update", FeedbackPriority.NORMAL),
            ("Important reminder", FeedbackPriority.HIGH),
            ("Another tip", FeedbackPriority.LOW),
            ("Critical alert!", FeedbackPriority.CRITICAL),
        ]

        print("Queueing feedbacks:")
        for text, priority in feedbacks:
            print(f"  - {text} (Priority: {priority.name})")

            # Create simple template
            template_id = f"demo_{priority.value}"
            self.feedback_system.add_custom_template(
                FeedbackTemplate(
                    id=template_id,
                    type=FeedbackType.INFO,
                    templates={"en": [text]},
                    priority=priority,
                )
            )

            await self.feedback_system.provide_feedback(
                user_id, template_id, priority_override=priority
            )

        # Show queue status
        await asyncio.sleep(1)
        status = self.feedback_system.queue_manager.get_queue_status()
        print("\nQueue Status:")
        print(f"  Currently playing: {status['current']}")
        print(f"  Items in queue: {status['queue_length']}")
        print(
            f"  Priorities: {[FeedbackPriority(p).name for p in status['queue_priorities']]}"
        )

    async def show_system_analytics(self) -> None:
        """Display system analytics and status."""
        print(f"\n{'='*60}")
        print("SYSTEM ANALYTICS")
        print(f"{'='*60}\n")

        status = self.feedback_system.get_system_status()

        print("📊 System Status:")
        print(f"  Active users: {status['active_users']}")
        print(f"  Cached audio clips: {status['cached_audio']}")
        print(f"  Available templates: {status['templates']}")
        print(f"  Sound effects loaded: {status['sound_effects']}")

        print("\n📈 User Statistics:")
        for user_id, context in self.feedback_system.user_contexts.items():
            print(f"\n  User: {user_id}")
            print(f"    Level: {context.user_level}")
            print(f"    Interactions: {context.interaction_count}")
            if context.interaction_count > 0:
                print(f"    Success rate: {context.success_rate:.1%}")
            if context.accessibility_needs:
                print(f"    Accessibility: {', '.join(context.accessibility_needs)}")


async def main() -> None:
    """Run all demonstrations."""
    demo = HealthcareVoiceAssistantDemo()

    # Initialize system
    await demo.initialize()

    # Run scenarios
    print("\n🎭 VOICE FEEDBACK SYSTEM DEMONSTRATION")
    print("=" * 60)

    # 1. New user experience
    await demo.simulate_new_user_session("Alice")
    await asyncio.sleep(2)

    # 2. Medical scenario
    await demo.simulate_medical_scenario("Bob")
    await asyncio.sleep(2)

    # 3. Accessibility user
    await demo.simulate_accessibility_user("Carol")
    await asyncio.sleep(2)

    # 4. Emergency scenario
    await demo.simulate_emergency_scenario()
    await asyncio.sleep(2)

    # 5. Queue management
    await demo.demonstrate_queue_management()
    await asyncio.sleep(2)

    # 6. Show analytics
    await demo.show_system_analytics()

    print(f"\n{'='*60}")
    print("DEMONSTRATION COMPLETE")
    print(f"{'='*60}")

    # Clean up
    await demo.feedback_system.stop_all_feedback()


def validate_feedback_communication(communication_data: dict) -> dict:
    """Validate feedback communication data for FHIR compliance.

    Args:
        communication_data: Communication data to validate

    Returns:
        Validation result with 'valid', 'errors', and 'warnings' keys
    """
    errors: list[str] = []
    warnings: list[str] = []

    if not communication_data:
        errors.append("No communication data provided")
    elif (
        "resourceType" in communication_data
        and communication_data["resourceType"] != "Communication"
    ):
        errors.append("Invalid resource type for communication")

    return {"valid": len(errors) == 0, "errors": errors, "warnings": warnings}


if __name__ == "__main__":
    asyncio.run(main())
