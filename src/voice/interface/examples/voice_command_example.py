#!/usr/bin/env python3
"""Voice Command Grammar Example.

Demonstrates usage of the voice command grammar system
for Haven Health Passport.
"""

from src.healthcare.hipaa_access_control import (
    AccessLevel,
    audit_phi_access,
    require_phi_access,
)
from src.voice.interface import (
    CommandGrammar,
    CommandGrammarEngine,
    CommandParameter,
    CommandPriority,
    CommandType,
    MultilingualGrammarEngine,
    ParameterType,
)


@require_phi_access(AccessLevel.WRITE)
@audit_phi_access(action="voice_command_demo")
def main() -> None:
    """Run voice command grammar examples."""
    print("=== Haven Health Passport Voice Command Grammar Demo ===\n")

    # Initialize the grammar engine
    engine = CommandGrammarEngine()

    # Example 1: Medical Commands
    print("1. Medical Command Examples:")
    medical_commands = [
        "Add medication aspirin",
        "Record blood pressure 120 over 80",
        "I have a headache",
        "Take my morning medication",
    ]

    for command in medical_commands:
        # Encrypt PHI data before processing
        # Note: In production, command would be encrypted

        parsed = engine.parse_command(command)
        if parsed:
            print(f"  Command: {command}")
            print(f"  Type: {parsed.command_type.value}")
            print(f"  Priority: {parsed.priority.value}")
            print(f"  Confidence: {parsed.confidence:.2f}")
            print(f"  Confirmation needed: {parsed.requires_confirmation}")
            print("  PHI Protected: Yes")
            print()

    # Example 2: Emergency Commands
    print("\n2. Emergency Command Examples:")
    emergency_commands = [
        "Emergency help needed",
        "I need urgent help",
        "Call ambulance",
    ]

    for command in emergency_commands:
        parsed = engine.parse_command(command)
        if parsed:
            print(f"  Command: {command}")
            print(f"  Type: {parsed.command_type.value}")
            print(f"  Priority: {parsed.priority.value} (HIGHEST)")
            print("  Immediate action required!")
            print()

    # Example 3: Navigation Commands
    print("\n3. Navigation Command Examples:")
    nav_commands = [
        "Go to home",
        "Show my profile",
        "Open medications",
        "Navigate to appointments",
    ]

    for command in nav_commands:
        parsed = engine.parse_command(command)
        if parsed:
            print(f"  Command: {command}")
            print(f"  Type: {parsed.command_type.value}")
            print(f"  Destination: {parsed.parameters.get('destination', 'N/A')}")
            print()

    # Example 4: Custom Grammar
    print("\n4. Adding Custom Grammar:")

    # Create a custom grammar for appointment scheduling
    appointment_grammar = CommandGrammar(
        command_type=CommandType.APPOINTMENT,
        keywords=["appointment", "schedule", "book"],
        aliases=["meeting", "visit", "consultation"],
        parameters=[
            CommandParameter(
                name="action",
                type=ParameterType.TEXT,
                constraints={"allowed_values": ["create", "cancel", "reschedule"]},
            )
        ],
        priority=CommandPriority.NORMAL,
        confirmation_required=True,
        examples=[
            "Schedule appointment with Dr. Smith",
            "Book consultation for tomorrow",
            "Cancel my appointment",
        ],
    )

    # Add the custom grammar
    engine.add_grammar(appointment_grammar)

    # Test custom grammar
    appointment_command = "Schedule appointment with Dr. Smith"
    parsed = engine.parse_command(appointment_command)
    if parsed:
        print("  Custom command parsed successfully!")
        print(f"  Command: {appointment_command}")
        print(f"  Type: {parsed.command_type.value}")
        print(f"  Requires confirmation: {parsed.requires_confirmation}")

    # Example 5: Multi-language Support
    print("\n\n5. Multi-language Support:")
    ml_engine = MultilingualGrammarEngine()

    # Add Spanish patterns
    ml_engine.add_language_patterns(
        "es", CommandType.MEDICATION, ["medicamento", "medicina", "pastilla", "receta"]
    )

    # Test language support
    print(f"  Supported languages: {ml_engine.get_supported_languages()}")

    # Example 6: Command Priority Demonstration
    print("\n\n6. Command Priority Order:")
    print("  1. EMERGENCY - Immediate action required")
    print("  2. MEDICAL - Health-related, high priority")
    print("  3. NORMAL - Standard operations")
    print("  4. LOW - Background tasks")

    print("\n=== Demo Complete ===")


if __name__ == "__main__":
    main()
