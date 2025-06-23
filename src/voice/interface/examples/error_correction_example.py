"""Voice Error Correction - Example Implementation.

This example demonstrates how to use error correction flows in a healthcare
voice interface with real-world scenarios.

Security Note: All PHI data processed in error correction examples must be encrypted at rest
and in transit using AES-256 encryption standards.

Access Control: Error correction example implementations require proper authentication and authorization
to ensure PHI data is only accessible to authorized users.
"""

import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, Optional

from src.voice.interface import CommandGrammarEngine
from src.voice.interface.error_correction_flows import (
    AdaptiveErrorCorrection,
    ErrorContext,
    ErrorType,
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class HealthcareVoiceInterface:
    """Healthcare voice interface with error correction."""

    def __init__(self) -> None:
        """Initialize healthcare voice interface with error correction."""
        self.grammar_engine = CommandGrammarEngine()
        self.error_manager = AdaptiveErrorCorrection()
        self.session_context: Dict[str, Any] = {
            "start_time": datetime.now(),
            "error_count": 0,
            "success_count": 0,
        }

    async def process_voice_input(
        self, voice_input: str, confidence: float = 1.0
    ) -> str:
        """Process voice input with error handling."""
        logger.info(f"Processing: '{voice_input}' (confidence: {confidence})")

        # Check for various error conditions
        error_context = self._detect_errors(voice_input, confidence)

        if error_context:
            # Handle the error
            return await self._handle_error(error_context)

        # Try to parse command normally
        command = self.grammar_engine.parse_command(voice_input)

        if command:
            self.session_context["success_count"] += 1
            return f"✅ Command recognized: {command.command_type.value}"
        else:
            # Command not recognized
            error_context = ErrorContext(
                error_type=ErrorType.OUT_OF_CONTEXT,
                original_input=voice_input,
                timestamp=datetime.now(),
                confidence_score=confidence,
            )
            return await self._handle_error(error_context)

    def _detect_errors(
        self, voice_input: str, confidence: float
    ) -> Optional[ErrorContext]:
        """Detect various error conditions."""
        # No speech detected
        if not voice_input or voice_input.strip() == "":
            return ErrorContext(
                error_type=ErrorType.NO_SPEECH_DETECTED,
                original_input="",
                timestamp=datetime.now(),
                confidence_score=0.0,
            )

        # Low confidence
        if confidence < 0.5:
            return ErrorContext(
                error_type=ErrorType.LOW_CONFIDENCE,
                original_input=voice_input,
                timestamp=datetime.now(),
                confidence_score=confidence,
            )

        # Check for ambiguity
        ambiguous_terms = ["it", "that", "this", "thing"]
        if any(term in voice_input.lower() for term in ambiguous_terms):
            return ErrorContext(
                error_type=ErrorType.AMBIGUOUS_COMMAND,
                original_input=voice_input,
                timestamp=datetime.now(),
                confidence_score=confidence,
                possible_interpretations=self._generate_interpretations(voice_input),
            )

        # Check for incomplete commands
        incomplete_patterns = ["add", "remove", "update", "check", "schedule"]
        words = voice_input.lower().split()
        if len(words) == 1 and words[0] in incomplete_patterns:
            return ErrorContext(
                error_type=ErrorType.INCOMPLETE_COMMAND,
                original_input=voice_input,
                timestamp=datetime.now(),
                confidence_score=confidence,
            )

        return None

    def _generate_interpretations(self, voice_input: str) -> list:
        """Generate possible interpretations for ambiguous input."""
        if "it" in voice_input.lower():
            return [
                voice_input.replace("it", "medication"),
                voice_input.replace("it", "appointment"),
                voice_input.replace("it", "record"),
            ]
        return []

    async def _handle_error(self, error_context: ErrorContext) -> str:
        """Handle error with correction flow."""
        self.session_context["error_count"] += 1

        # Get correction flow
        flow = await self.error_manager.handle_error(error_context, user_id="demo_user")

        logger.info(f"Error correction strategy: {flow.strategy.value}")
        logger.info(f"Prompt: {flow.prompt}")

        if flow.options:
            for i, option in enumerate(flow.options):
                logger.info(f"  {i+1}. {option}")

        # Simulate user response
        user_response = await self._simulate_user_response(flow, error_context)
        logger.info(f"User response: '{user_response}'")

        # Process correction
        result = await self.error_manager.process_correction(
            flow.id, user_response, user_id="demo_user"
        )

        if result.success:
            return f"✅ Corrected: {result.corrected_input}"
        else:
            return "❌ Unable to understand. Please try again or say 'help'."

    async def _simulate_user_response(
        self, flow: Any, error_context: ErrorContext
    ) -> str:
        """Simulate user responses for demo."""
        await asyncio.sleep(0.5)  # Simulate thinking time

        if flow.strategy.value == "clarification" and flow.options:
            # Choose first option
            return "1"
        elif flow.strategy.value == "repetition":
            # Repeat with better clarity
            return str(error_context.original_input) + " medication"
        elif flow.strategy.value == "spelling":
            # Spell out a word
            return "A S P I R I N"
        elif flow.strategy.value == "guided_completion":
            # Provide missing info
            return "aspirin 100mg"

        return "yes"


async def demonstrate_scenarios() -> None:
    """Demonstrate various error correction scenarios."""
    interface = HealthcareVoiceInterface()

    print("=== Healthcare Voice Interface Error Correction Demo ===\n")

    # Scenario 1: Low confidence
    print("📍 Scenario 1: Low Confidence Recognition")
    print("-" * 50)
    result = await interface.process_voice_input("abd meication aspirn", confidence=0.3)
    print(f"Result: {result}\n")

    # Scenario 2: Ambiguous command
    print("📍 Scenario 2: Ambiguous Command")
    print("-" * 50)
    result = await interface.process_voice_input("remove it", confidence=0.8)
    print(f"Result: {result}\n")

    # Scenario 3: Incomplete command
    print("📍 Scenario 3: Incomplete Command")
    print("-" * 50)
    result = await interface.process_voice_input("schedule", confidence=0.9)
    print(f"Result: {result}\n")

    # Scenario 4: No speech detected
    print("📍 Scenario 4: No Speech Detected")
    print("-" * 50)
    result = await interface.process_voice_input("", confidence=0.0)
    print(f"Result: {result}\n")

    # Scenario 5: Medical term pronunciation
    print("📍 Scenario 5: Medical Term Mispronunciation")
    print("-" * 50)
    result = await interface.process_voice_input(
        "add medication meh-for-min", confidence=0.4
    )
    print(f"Result: {result}\n")

    # Show session statistics
    print("📊 Session Statistics")
    print("-" * 50)
    stats = interface.error_manager.get_user_statistics("demo_user")
    print(f"Total errors: {stats['total_errors']}")
    print(f"Success rate: {stats['success_rate']:.1%}")
    print(f"Capability level: {stats['capability_level']}")
    print(f"Error types: {stats['error_types']}")


async def interactive_demo() -> None:
    """Interactive demo with simulated voice inputs."""
    interface = HealthcareVoiceInterface()

    print("\n=== Interactive Voice Error Correction Demo ===")
    print("Simulating voice commands with various error conditions...\n")

    # Simulate a conversation with errors
    conversation = [
        ("Check my...", 0.4),  # Incomplete with low confidence
        ("Check my vitals", 0.9),  # Corrected version
        ("Add medcin", 0.3),  # Misspelled/mispronounced
        ("Add medication ibuprofen", 0.95),  # Corrected
        ("Delete that", 0.8),  # Ambiguous reference
        ("Delete medication aspirin", 0.9),  # Clarified
    ]

    for voice_input, confidence in conversation:
        print(f"\n🎤 User: '{voice_input}' (confidence: {confidence})")
        result = await interface.process_voice_input(voice_input, confidence)
        print(f"🤖 System: {result}")
        await asyncio.sleep(1)  # Pause between interactions


async def accessibility_demo() -> None:
    """Demonstrate accessibility features."""
    print("\n=== Accessibility-Focused Error Correction ===\n")

    # Create manager with accessibility profile
    manager = AdaptiveErrorCorrection()

    # Simulate user with motor impairment (needs more time)
    error = ErrorContext(
        error_type=ErrorType.INCOMPLETE_COMMAND,
        original_input="medication",
        timestamp=datetime.now(),
        user_history={
            "accessibility_needs": ["motor_impaired"],
            "average_response_time": 45.0,  # seconds
        },
    )

    flow = await manager.handle_error(error, "motor_impaired_user")
    print(f"⏱️  Extended timeout for motor accessibility: {flow.timeout_seconds}s")
    print(f"📝 Simplified prompt: {flow.prompt}")

    # Simulate user with cognitive support needs
    error2 = ErrorContext(
        error_type=ErrorType.AMBIGUOUS_COMMAND,
        original_input="take medicine",
        timestamp=datetime.now(),
        user_history={
            "accessibility_needs": ["cognitive_support"],
            "preferred_complexity": "simple",
        },
    )

    flow2 = await manager.handle_error(error2, "cognitive_support_user")
    print("\n🧠 Cognitive support mode:")
    print(f"📝 Clear, simple prompt: {flow2.prompt}")
    if flow2.options:
        print("📋 Limited options for easier choice:")
        for i, opt in enumerate(flow2.options[:2]):  # Show only first 2
            print(f"   {i+1}. {opt}")


async def main() -> None:
    """Run all demonstrations."""
    await demonstrate_scenarios()
    await asyncio.sleep(2)
    await interactive_demo()
    await asyncio.sleep(2)
    await accessibility_demo()


if __name__ == "__main__":
    asyncio.run(main())
