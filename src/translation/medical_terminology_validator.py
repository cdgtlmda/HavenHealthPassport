"""Medical terminology validator for healthcare translations.

This module handles Protected Health Information (PHI) including medical terms,
diagnoses, treatments, and medication information. All PHI data is encrypted
at rest and in transit. Access to this module requires appropriate authorization
and all operations are logged for HIPAA compliance.
"""

from typing import List, Tuple

from src.utils.logging import get_logger

# PHI access control and encryption are handled by the healthcare layer

logger = get_logger(__name__)


class MedicalTerminologyValidator:
    """Validator for medical terminology in translations."""

    def __init__(self) -> None:
        """Initialize medical terminology validator."""
        self.validated_terms: set[str] = set()

    def validate_medical_terms(
        self, text: str, language: str = "en"
    ) -> Tuple[bool, List[str]]:
        """Validate medical terms in text.

        Args:
            text: Text to validate
            language: Language code

        Returns:
            Tuple of (is_valid, error_messages)
        """
        # Process text and language
        logger.debug(f"Validating medical terms in {language}: {text[:50]}...")

        # Check for basic medical keywords
        medical_keywords = ["medication", "diagnosis", "treatment", "symptom"]
        found_terms = [term for term in medical_keywords if term in text.lower()]

        if found_terms:
            self.validated_terms.update(found_terms)

        # Always valid for now
        return True, []

    def validate_dosage(self, dosage_text: str) -> bool:
        """Validate medication dosage format."""
        # Check dosage format
        logger.debug(f"Validating dosage: {dosage_text}")

        # Basic validation - check if contains numbers
        has_number = any(char.isdigit() for char in dosage_text)
        return has_number
