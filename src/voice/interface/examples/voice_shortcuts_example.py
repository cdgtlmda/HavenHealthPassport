#!/usr/bin/env python3
"""Voice Shortcuts Example.

Demonstrates usage of the voice shortcuts system
for Haven Health Passport.

Note: Voice shortcuts may contain PHI when personalized. Implement proper
access control to ensure only authorized users can access and manage shortcuts.
All PHI data is encrypted at rest and in transit.
"""

from src.healthcare.hipaa_access_control import (
    AccessLevel,
    audit_phi_access,
    require_phi_access,
)
from src.voice.interface import (
    CommandPriority,
    PersonalizedShortcutEngine,
    ShortcutCategory,
    ShortcutConfig,
    ShortcutEngine,
    VoiceShortcut,
)


@require_phi_access(AccessLevel.READ)
@audit_phi_access(action="voice_shortcuts_demo")
def main() -> None:
    """Run voice shortcuts examples."""
    print("=== Haven Health Passport Voice Shortcuts Demo ===\n")

    # Example 1: Basic shortcut usage
    print("1. Basic Shortcut Usage:")

    config = ShortcutConfig()
    engine = ShortcutEngine(config)

    # Show some default shortcuts
    print("Available shortcuts:")
    for category in ShortcutCategory:
        shortcuts = engine.get_shortcuts_by_category(category)
        if shortcuts:
            print(f"\n{category.value.title()}:")
            for shortcut in shortcuts[:3]:  # Show first 3
                print(f"  '{shortcut.phrase}' → {shortcut.full_command}")

    # Test shortcut matching
    print("\n\nTesting shortcuts:")
    test_phrases = ["home", "meds", "help", "vitals", "appointments"]

    for phrase in test_phrases:
        match = engine.find_shortcut(phrase)
        if match:
            print(f"  '{phrase}' → {match.to_command()}")
        else:
            print(f"  '{phrase}' → No match found")

    # Example 2: Custom shortcuts
    print("\n\n2. Custom Shortcuts:")

    # Create custom shortcuts
    custom_shortcuts = [
        VoiceShortcut(
            phrase="bp",
            full_command="record blood pressure",
            category=ShortcutCategory.QUICK_ACTION,
            description="Quick BP recording",
        ),
        VoiceShortcut(
            phrase="sugar",
            full_command="record blood glucose",
            category=ShortcutCategory.QUICK_ACTION,
            description="Quick glucose check",
        ),
        VoiceShortcut(
            phrase="sos",
            full_command="emergency medical assistance",
            category=ShortcutCategory.EMERGENCY,
            priority=CommandPriority.EMERGENCY,
            description="Emergency shortcut",
        ),
    ]

    # Add custom shortcuts
    for shortcut in custom_shortcuts:
        if engine.add_custom_shortcut(shortcut):
            print(f"  Added: '{shortcut.phrase}' → {shortcut.full_command}")

    # Test custom shortcuts
    print("\nTesting custom shortcuts:")
    for phrase in ["bp", "sugar", "sos"]:
        match = engine.find_shortcut(phrase)
        if match:
            print(
                f"  '{phrase}' → {match.to_command()} (Priority: {match.shortcut.priority.value})"
            )

    # Example 3: Fuzzy matching
    print("\n\n3. Fuzzy Matching:")

    fuzzy_tests = [
        "need help",  # Should match "help"
        "my meds",  # Should match "meds"
        "show appointments",  # Should match "appointments"
    ]

    for phrase in fuzzy_tests:
        match = engine.find_shortcut(phrase)
        if match:
            print(
                f"  '{phrase}' → {match.shortcut.phrase} (confidence: {match.confidence:.2f})"
            )
        else:
            print(f"  '{phrase}' → No fuzzy match found")

    # Example 4: Personalized shortcuts
    print("\n\n4. Personalized Shortcuts:")

    personalized = PersonalizedShortcutEngine(config, "demo_user")

    # Simulate user patterns
    user_patterns = [
        ("check bp", "record blood pressure"),
        ("my bp", "record blood pressure"),
        ("pressure check", "record blood pressure"),
        ("med list", "show my medications"),
        ("my drugs", "show my medications"),
    ]

    print("Learning user patterns...")
    for user_phrase, command in user_patterns:
        personalized.learn_pattern(user_phrase, command)
        print(f"  Learned: '{user_phrase}' means '{command}'")

    # Check for suggestions
    print("\nChecking for shortcut suggestions:")
    suggestion = personalized.suggest_shortcut("record blood pressure")
    if suggestion:
        print(f"  Suggested shortcut: '{suggestion.phrase}' for frequent command")
        print(f"  Description: {suggestion.description}")

    # Example 5: Usage statistics
    print("\n\n5. Usage Statistics:")

    # Simulate usage
    usage_simulation = ["home", "home", "meds", "vitals", "home", "help", "meds"]
    for phrase in usage_simulation:
        engine.find_shortcut(phrase)

    # Get statistics
    print("Most used shortcuts:")
    most_used = engine.get_most_used_shortcuts(5)
    for phrase, count in most_used:
        print(f"  '{phrase}': {count} times")

    # Example 6: Shortcut management
    print("\n\n6. Shortcut Management:")

    # Disable/enable shortcuts
    print("Disabling 'home' shortcut...")
    engine.disable_shortcut("home")
    match = engine.find_shortcut("home")
    print(f"  'home' shortcut active: {match is not None}")

    print("Re-enabling 'home' shortcut...")
    engine.enable_shortcut("home")
    match = engine.find_shortcut("home")
    print(f"  'home' shortcut active: {match is not None}")

    print("\n=== Demo Complete ===")


if __name__ == "__main__":
    main()
