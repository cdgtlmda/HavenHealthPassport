"""Medical terms translation module."""

from typing import Dict, List, Optional

from src.healthcare.hipaa_access_control import (
    AccessLevel,
    audit_phi_access,
    require_phi_access,
)
from src.utils.encryption import EncryptionService


class MedicalTermTranslator:
    """Handles translation of medical terms between languages."""

    def __init__(self) -> None:
        """Initialize medical term translator."""
        self.translations: Dict[str, Dict[str, str]] = {}
        self._encryption_service = EncryptionService()
        self._initialize_translations()

    def _initialize_translations(self) -> None:
        """Initialize basic medical term translations."""
        # Example translations (English -> Spanish)
        self.translations["es"] = {
            "fever": "fiebre",
            "pain": "dolor",
            "headache": "dolor de cabeza",
            "cough": "tos",
            "medication": "medicación",
            "prescription": "receta",
            "diagnosis": "diagnóstico",
            "treatment": "tratamiento",
        }

    @require_phi_access(AccessLevel.READ)
    @audit_phi_access("translate_medical_term")
    def translate_term(self, term: str, target_language: str) -> Optional[str]:
        """Translate a medical term to the target language."""
        if target_language in self.translations:
            translated = self.translations[target_language].get(term.lower())
            return translated
        return None

    def get_available_languages(self) -> List[str]:
        """Get list of available translation languages."""
        return list(self.translations.keys())

    def _contains_phi(self, text: str) -> bool:
        """Check if text might contain PHI."""
        phi_indicators = [
            "patient",
            "name",
            "dob",
            "diagnosis",
            "medication",
            "ssn",
            "mrn",
        ]
        return any(indicator in text.lower() for indicator in phi_indicators)
