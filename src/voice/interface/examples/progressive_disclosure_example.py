"""Voice Progressive Disclosure - Example Implementation.

This example demonstrates how progressive disclosure works in a healthcare
voice interface, showing user progression and feature unlocking.

Security Note: All PHI data processed in examples must be encrypted at rest
and in transit using AES-256 encryption standards.

Access Control: Example implementations require proper authentication and authorization
to ensure PHI data is only accessible to authorized users.
"""

import asyncio
import logging
import random
from datetime import datetime
from typing import Any, Dict

from src.voice.interface import CommandPriority, CommandType, ParsedCommand
from src.voice.interface.progressive_disclosure import (
    AccessibilityDisclosureAdapter,
    AdaptiveDisclosureManager,
    DisclosureLevel,
    DisclosureMetrics,
    InteractionContext,
    OnboardingFlowManager,
    VoiceInterfaceAdapter,
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class HealthcareVoiceDemo:
    """Demo healthcare voice interface with progressive disclosure."""

    def __init__(self) -> None:
        """Initialize progressive disclosure demo with all components."""
        self.disclosure_engine = AdaptiveDisclosureManager()
        self.interface_adapter = VoiceInterfaceAdapter(self.disclosure_engine)
        self.onboarding = OnboardingFlowManager(self.disclosure_engine)
        self.accessibility = AccessibilityDisclosureAdapter(self.disclosure_engine)
        self.metrics = DisclosureMetrics()

    async def simulate_new_user_experience(self, user_id: str = "demo_user") -> None:
        """Simulate a new user's first experience."""
        print(f"\n{'='*60}")
        print(f"NEW USER EXPERIENCE - {user_id}")
        print(f"{'='*60}\n")

        # Check if onboarding needed
        current_step = self.onboarding.get_current_step(user_id)

        if current_step:
            print("📚 Starting Onboarding Process")
            print("-" * 40)

            while current_step:
                print(f"\nStep {current_step['step']}: {current_step['title']}")
                print(f"📢 System: {current_step['instruction']}")

                # Simulate user following instruction
                await asyncio.sleep(1)
                success = random.random() > 0.2  # 80% success rate

                if success:
                    print("✅ User: Successfully completed!")
                    print(f"💬 System: {current_step['success_message']}")
                    self.onboarding.complete_step(user_id, current_step["step"])
                else:
                    print("❌ User: Had trouble with command")
                    print(f"💡 System: {current_step['failure_hint']}")

                await asyncio.sleep(0.5)
                current_step = self.onboarding.get_current_step(user_id)

            print("\n🎉 Onboarding Complete! You're now at BASIC level.")

        # Show available features
        await self.show_available_features(user_id)

    async def show_available_features(self, user_id: str) -> None:
        """Display features available to user."""
        profile = self.disclosure_engine.get_user_profile(user_id)
        features = self.disclosure_engine.get_available_features(user_id)

        print("\n📊 User Profile")
        print(f"  Level: {profile.current_level.name}")
        print(f"  Proficiency: {profile.calculate_proficiency():.1%}")
        print(f"  Total Interactions: {profile.total_interactions}")
        print(
            f"  Success Rate: {profile.successful_interactions / profile.total_interactions * 100 if profile.total_interactions > 0 else 0:.1f}%"
        )

        print(f"\n🎯 Available Features ({len(features)} total):")

        # Group by category
        by_category: Dict[Any, Any] = {}
        for feature in features:
            if feature.category not in by_category:
                by_category[feature.category] = []
            by_category[feature.category].append(feature)

        for category, cat_features in by_category.items():
            print(f"\n  {category.value.upper()}:")
            for feature in cat_features[:3]:  # Limit display
                print(f"    • {feature.name}")
                if feature.command_examples:
                    print(f'      Example: "{feature.command_examples[0]}"')

    async def simulate_user_progression(
        self, user_id: str = "progressing_user"
    ) -> None:
        """Simulate a user progressing through levels."""
        print(f"\n{'='*60}")
        print(f"USER PROGRESSION SIMULATION - {user_id}")
        print(f"{'='*60}\n")

        # Simulate interactions over time
        interaction_count = 0
        success_count = 0

        command_types = [
            (CommandType.MEDICATION, "show medications", "show_medications"),
            (CommandType.MEDICATION, "add medication", "add_medication"),
            (CommandType.APPOINTMENT, "check appointments", "check_appointment"),
            (CommandType.VITALS, "record blood pressure", "record_vitals"),
        ]

        for day in range(5):  # Simulate 5 days
            print(f"\n📅 Day {day + 1}")
            print("-" * 30)

            # Multiple interactions per day
            daily_interactions = random.randint(3, 8)

            for _ in range(daily_interactions):
                # Pick a command
                cmd_type, cmd_text, feature_id = random.choice(command_types)

                # Check if feature is available
                available_features = self.disclosure_engine.get_available_features(
                    user_id
                )
                feature_available = any(f.id == feature_id for f in available_features)

                if not feature_available and random.random() > 0.3:
                    # Skip unavailable features most of the time
                    continue

                # Create command
                command = ParsedCommand(
                    command_type=cmd_type,
                    raw_text=cmd_text,
                    parameters={},
                    confidence=random.uniform(0.7, 1.0),
                    language="en",
                    timestamp=datetime.now(),
                    priority=CommandPriority.NORMAL,
                )

                # Simulate success/failure
                success = random.random() > 0.2  # 80% success rate

                # Record interaction
                self.disclosure_engine.record_interaction(
                    user_id, command, success, feature_id if feature_available else None
                )

                interaction_count += 1
                if success:
                    success_count += 1

                # Show interaction
                icon = "✅" if success else "❌"
                print(f"  {icon} {cmd_text}")

                await asyncio.sleep(0.1)

            # Check for progression
            profile = self.disclosure_engine.get_user_profile(user_id)
            if profile.preferences.get("last_progression_message"):
                print(
                    f"\n🎊 LEVEL UP! {profile.preferences['last_progression_message']}"
                )
                profile.preferences["last_progression_message"] = None

            # Show daily summary
            print(f"\n  Daily Summary: {daily_interactions} interactions")
            await self.show_brief_status(user_id)

    async def show_brief_status(self, user_id: str) -> None:
        """Show brief status update."""
        profile = self.disclosure_engine.get_user_profile(user_id)
        features = self.disclosure_engine.get_available_features(user_id)
        suggestions = self.disclosure_engine.suggest_next_features(user_id, limit=2)

        print(f"  Current Level: {profile.current_level.name}")
        print(f"  Features Available: {len(features)}")

        if suggestions:
            print(f"  Try Next: {', '.join(s.name for s in suggestions)}")

    async def demonstrate_contextual_help(self, user_id: str = "help_user") -> None:
        """Demonstrate contextual help system."""
        print(f"\n{'='*60}")
        print("CONTEXTUAL HELP DEMONSTRATION")
        print(f"{'='*60}\n")

        # Set up user at intermediate level
        profile = self.disclosure_engine.get_user_profile(user_id)
        profile.current_level = DisclosureLevel.INTERMEDIATE
        profile.total_interactions = 50
        profile.successful_interactions = 40

        # Get help in different contexts
        contexts = [
            (InteractionContext.ROUTINE_USE, "Regular Use"),
            (InteractionContext.EMERGENCY, "Emergency Situation"),
            (InteractionContext.FIRST_TIME, "First Time Context"),
        ]

        for context, context_name in contexts:
            print(f"\n🔍 Help in {context_name}")
            print("-" * 40)

            help_info = self.disclosure_engine.get_contextual_help(user_id, context)

            # Show available commands
            print("\nAvailable Commands:")
            for category, commands in help_info["available_commands"].items():
                if commands:
                    print(f"\n  {category.upper()}:")
                    for cmd in commands[:2]:  # Limit display
                        print(f"    • {cmd['name']}")
                        print(f"      \"{cmd['examples'][0]}\"")

            # Show suggestions
            if help_info["suggested_next"]:
                print("\n💡 Suggested Next:")
                for suggestion in help_info["suggested_next"]:
                    print(f"  • {suggestion['name']}: {suggestion['why']}")

            # Show tips
            if help_info["tips"]:
                print("\n📝 Tips:")
                for tip in help_info["tips"]:
                    print(f"  • {tip}")

            await asyncio.sleep(1)

    async def demonstrate_accessibility(self) -> None:
        """Demonstrate accessibility adaptations."""
        print(f"\n{'='*60}")
        print("ACCESSIBILITY ADAPTATIONS")
        print(f"{'='*60}\n")

        # Cognitive support user
        print("👤 User with Cognitive Support Needs")
        print("-" * 40)

        user_id = "cognitive_user"
        adaptations = self.accessibility.adapt_for_accessibility(
            user_id, ["cognitive_support"]
        )

        print("Adaptations Applied:")
        print(f"  • Disclosure Speed: {adaptations['disclosure_speed']}x (slower)")
        print(f"  • Feature Limit: {adaptations['feature_limit']} features max")
        print(f"  • Simplified Options: {adaptations['simplify_options']}")
        print(f"  • Extended Help: {adaptations['extended_help']}")

        # Show simplified features
        simplified = self.accessibility.get_simplified_features(user_id, limit=3)
        print("\nSimplified Feature Set:")
        for feature in simplified:
            print(f"  • {feature.name}")
            print(f'    Simple command: "{feature.command_examples[0]}"')

    async def show_analytics(self) -> None:
        """Display system analytics."""
        print(f"\n{'='*60}")
        print("SYSTEM ANALYTICS")
        print(f"{'='*60}\n")

        # Simulate some metric data
        for i in range(5):
            user_id = f"user_{i}"
            self.metrics.track_progression(
                user_id, DisclosureLevel.ESSENTIAL, DisclosureLevel.BASIC
            )

            for _ in range(10):
                self.metrics.track_feature_adoption(
                    "show_medications", user_id, success=random.random() > 0.2
                )

        summary = self.metrics.get_analytics_summary()

        print("📊 Analytics Summary:")
        print(f"  Total Users: {summary['total_users']}")
        print("\n  Level Distribution:")
        for level, count in summary["level_distribution"].items():
            print(f"    {level}: {count} users")

        print("\n  Feature Success Rates:")
        for feature, stats in list(summary["feature_success_rates"].items())[:3]:
            print(f"    {feature}: {stats['success_rate']:.1%} success")


async def main() -> None:
    """Run all demonstrations."""
    demo = HealthcareVoiceDemo()

    # 1. New user experience
    await demo.simulate_new_user_experience("alice")
    await asyncio.sleep(2)

    # 2. User progression
    await demo.simulate_user_progression("bob")
    await asyncio.sleep(2)

    # 3. Contextual help
    await demo.demonstrate_contextual_help("charlie")
    await asyncio.sleep(2)

    # 4. Accessibility
    await demo.demonstrate_accessibility()
    await asyncio.sleep(2)

    # 5. Analytics
    await demo.show_analytics()

    print(f"\n{'='*60}")
    print("DEMONSTRATION COMPLETE")
    print(f"{'='*60}")


if __name__ == "__main__":
    asyncio.run(main())
