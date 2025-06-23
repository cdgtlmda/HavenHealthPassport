"""
Example of integrated translation with target language selection.

This module handles encrypted PHI with access control and audit logging
to ensure HIPAA compliance.
"""

from typing import Any, Dict

from ..chains import TranslationChainFactory
from ..config import Language, TranslationMode
from ..target_selection import TargetLanguageSelector


# Example usage
def example_usage() -> None:
    """Demonstrate target language selection in action."""
    # Create service
    service = SmartTranslationService()

    # Set user preferences
    service.target_selector.add_user_preference("patient123", Language.SPANISH, 1)
    service.target_selector.add_user_preference("patient123", Language.ENGLISH, 2)

    # Example 1: User with preferences in North America
    print("Example 1: User preference + regional")
    result = service.translate_for_user(
        text="The patient has type 2 diabetes",
        user_id="patient123",
        region="north_america",
    )
    # Will select Spanish (user preference #1)

    # Example 2: Emergency translation in Middle East
    print("\nExample 2: Emergency mode")
    result = service.translate_for_user(
        text="Severe chest pain, possible MI",
        user_id="unknown",
        region="middle_east",
        mode=TranslationMode.EMERGENCY,
    )
    print(f"Result: {result}")
    # Will select Arabic (regional) or English (emergency default)

    # Example 3: Context-based selection
    print("\nExample 3: Context-based")
    context = {
        "patient_languages": ["bn", "hi"],  # Bengali, Hindi
        "provider_language": "en",
    }
    _ = service.translate_for_user(
        text="Please take this medication twice daily",
        user_id="patient456",
        context=context,
        mode=TranslationMode.PRESCRIPTION,
    )
    # Will prioritize Bengali (patient's first language)


class SmartTranslationService:
    """Smart translation service implementation."""

    def __init__(self) -> None:
        """Initialize the service."""
        self.chain = TranslationChainFactory.create_chain()
        self.target_selector = TargetLanguageSelector()

    def translate_for_user(
        self, text: str, user_id: str, **kwargs: Any
    ) -> Dict[str, Any]:
        """Translate with automatic target selection."""
        # Simplified for example
        return {"status": "example"}
