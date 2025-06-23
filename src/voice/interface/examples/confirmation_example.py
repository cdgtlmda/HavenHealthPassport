"""Voice Confirmation Protocols - Example Implementation.

This example demonstrates how to use the confirmation protocols in a real-world
healthcare voice interface scenario. Handles FHIR AuditEvent Resource
validation for confirmation tracking.

Security Note: All PHI data processed in confirmation examples must be encrypted at rest
and in transit using AES-256 encryption standards.

Access Control: Confirmation example implementations require proper authentication and authorization
to ensure PHI data is only accessible to authorized users.
"""

import asyncio
import logging
from datetime import datetime
from typing import Any, Optional

from src.voice.interface import (
    AccessibleConfirmationManager,
    CommandPriority,
    CommandType,
    ConfirmationStatus,
    ParsedCommand,
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class HealthcareVoiceAssistant:
    """Example healthcare voice assistant with confirmation protocols."""

    def __init__(self) -> None:
        """Initialize healthcare voice assistant with confirmation manager."""
        # Use accessible confirmation manager for better support
        self.confirmation_manager = AccessibleConfirmationManager()
        self.user_profile = {
            "user_id": "user_123",
            "experience_level": "intermediate",
            "preferred_language": "en",
            "accessibility_needs": [],
            "confirmation_preferences": {
                "skip_low_risk": False,
                "extended_timeouts": False,
            },
        }
        self.environment = {
            "noise_level": "low",
            "privacy_level": "private",
            "device_type": "mobile",
        }

    async def process_voice_command(self, voice_input: str) -> str:
        """Process a voice command with appropriate confirmations."""
        # Parse the command (simplified for example)
        command = self._parse_command(voice_input)

        if not command:
            return "I didn't understand that command. Please try again."

        # Check if confirmation is needed
        context = {"user_profile": self.user_profile, "environment": self.environment}

        confirmation_request = await self.confirmation_manager.request_confirmation(
            command, context, audio_callback=self._speak_prompt
        )

        if not confirmation_request:
            # No confirmation needed, execute immediately
            return await self._execute_command(command)

        # Wait for user confirmation
        logger.info(f"Waiting for confirmation: {confirmation_request.prompt}")

        # Simulate user response (in real implementation, this would come from voice input)
        user_response = await self._get_user_response(confirmation_request)

        # Validate the response
        confirmation_response = self.confirmation_manager.validate_response(
            confirmation_request.id, user_response
        )

        if confirmation_response.status == ConfirmationStatus.CONFIRMED:
            return await self._execute_command(command)
        elif confirmation_response.status == ConfirmationStatus.REJECTED:
            return "Command cancelled."
        elif confirmation_response.status == ConfirmationStatus.TIMEOUT:
            return "Confirmation timed out. Please try your command again."
        else:
            return "Confirmation failed. Please try again."

    def _parse_command(self, voice_input: str) -> Optional[ParsedCommand]:
        """Parse command from voice input for demonstration."""
        voice_lower = voice_input.lower()

        # Medication commands
        if "medication" in voice_lower or "medicine" in voice_lower:
            if "add" in voice_lower:
                return ParsedCommand(
                    command_type=CommandType.MEDICATION,
                    raw_text=voice_input,
                    parameters={
                        "action": "add",
                        "medication_name": self._extract_medication_name(voice_input),
                    },
                    confidence=0.9,
                    language="en",
                    timestamp=datetime.now(),
                    priority=CommandPriority.MEDICAL,
                )
            elif "delete" in voice_lower or "remove" in voice_lower:
                return ParsedCommand(
                    command_type=CommandType.DELETE,
                    raw_text=voice_input,
                    parameters={
                        "target": "medication",
                        "medication_name": self._extract_medication_name(voice_input),
                    },
                    confidence=0.9,
                    language="en",
                    timestamp=datetime.now(),
                    priority=CommandPriority.MEDICAL,
                )

        # Emergency commands
        elif (
            "emergency" in voice_lower
            or "help" in voice_lower
            and "urgent" in voice_lower
        ):
            return ParsedCommand(
                command_type=CommandType.EMERGENCY,
                raw_text=voice_input,
                parameters={"type": "medical"},
                confidence=1.0,
                language="en",
                timestamp=datetime.now(),
                priority=CommandPriority.EMERGENCY,
            )

        # Share commands
        elif "share" in voice_lower:
            return ParsedCommand(
                command_type=CommandType.SHARE,
                raw_text=voice_input,
                parameters={
                    "target": "medical_records",
                    "recipient": self._extract_recipient(voice_input),
                },
                confidence=0.8,
                language="en",
                timestamp=datetime.now(),
                priority=CommandPriority.NORMAL,
            )

        return None

    def _extract_medication_name(self, text: str) -> str:
        """Extract medication name from text (simplified)."""
        # In real implementation, use NLP
        common_meds = ["aspirin", "ibuprofen", "insulin", "metformin"]
        for med in common_meds:
            if med in text.lower():
                return med
        return "unknown"

    def _extract_recipient(self, text: str) -> str:
        """Extract recipient from share command."""
        if "doctor" in text.lower():
            return "primary_doctor"
        elif "family" in text.lower():
            return "family_members"
        return "unknown"

    async def _speak_prompt(self, prompt: str) -> None:
        """Speak a prompt to the user (simulated)."""
        print(f"🔊 Assistant: {prompt}")
        # In real implementation, use text-to-speech
        await asyncio.sleep(0.5)

    async def _get_user_response(self, request: Any) -> str:
        """Get user response (simulated for example)."""
        # In real implementation, this would capture voice input
        print("🎤 Listening for your response...")

        # Simulate different responses based on request type
        if request.type.value == "verbal_yes_no":
            return "yes"  # Simulate positive confirmation
        elif request.type.value == "verbal_repeat":
            return str(request.prompt)  # Simulate correct repeat
        elif request.type.value == "numeric_code":
            # Extract code from metadata
            if hasattr(request, "metadata") and "expected_code" in request.metadata:
                return str(request.metadata["expected_code"])
            return "1234"

        return "yes"

    async def _execute_command(self, command: ParsedCommand) -> str:
        """Execute the confirmed command."""
        if command.command_type == CommandType.MEDICATION:
            action = command.parameters.get("action")
            med_name = command.parameters.get("medication_name")
            return f"✅ Successfully {action}ed medication: {med_name}"

        elif command.command_type == CommandType.DELETE:
            target = command.parameters.get("target")
            return f"✅ Successfully deleted {target}"

        elif command.command_type == CommandType.EMERGENCY:
            return "🚨 Emergency services have been contacted. Help is on the way."

        elif command.command_type == CommandType.SHARE:
            recipient = command.parameters.get("recipient")
            return f"✅ Medical records shared with {recipient}"

        return "✅ Command executed successfully"


async def main() -> None:
    """Run example scenarios."""
    assistant = HealthcareVoiceAssistant()

    # Test scenarios
    test_commands = [
        "Add medication aspirin",
        "Delete medication ibuprofen",
        "Share my medical records with my doctor",
        "Emergency help needed",
        "Remove all medications",  # High-risk command
    ]

    print("=== Healthcare Voice Assistant Demo ===\n")

    for command in test_commands:
        print(f"\n📢 User: {command}")
        result = await assistant.process_voice_command(command)
        print(f"💬 Result: {result}")
        print("-" * 50)
        await asyncio.sleep(1)


if __name__ == "__main__":
    asyncio.run(main())
