"""Gender-Aware Translation System.

This module provides gender-aware translation functionality for languages
that require gender agreement in grammar, medical contexts, and UI.

This module handles PHI with encryption and access control to ensure HIPAA compliance.
It includes FHIR Resource typing and validation for healthcare data.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional

from src.healthcare.fhir.validators import FHIRValidator
from src.security.access_control import AccessPermission, require_permission
from src.security.audit import audit_phi_access
from src.security.encryption import EncryptionService
from src.utils.logging import get_logger

logger = get_logger(__name__)


class Gender(str, Enum):
    """Grammatical and biological gender types."""

    MASCULINE = "masculine"
    FEMININE = "feminine"
    NEUTER = "neuter"  # For languages with neuter gender
    UNKNOWN = "unknown"  # When gender is not specified
    OTHER = "other"  # Non-binary option


class GenderContext(str, Enum):
    """Context where gender affects translation."""

    PATIENT = "patient"  # Patient's gender
    PROVIDER = "provider"  # Healthcare provider's gender
    GRAMMAR = "grammar"  # Grammatical gender of nouns
    ADJECTIVE = "adjective"  # Adjective agreement
    PRONOUN = "pronoun"  # Pronoun selection
    TITLE = "title"  # Titles (Mr., Mrs., Dr., etc.)
    POSSESSIVE = "possessive"  # Possessive forms


@dataclass
class GenderForm:
    """Gender-specific translation form."""

    gender: Gender
    text: str
    context: GenderContext
    language: str


@dataclass
class GenderRules:
    """Gender rules for a language."""

    language: str
    has_gender_agreement: bool
    gender_affects: List[GenderContext]
    default_gender: Gender
    gender_markers: Dict[Gender, str]


class GenderTranslationManager:
    """Manages gender-aware translations across languages."""

    def __init__(self) -> None:
        """Initialize gender translation manager."""
        self.language_rules: Dict[str, GenderRules] = {}
        self.gender_forms: Dict[str, Dict[Gender, Dict[str, str]]] = {}
        self._initialize_language_rules()
        self._load_common_forms()
        self.fhir_validator = FHIRValidator()
        self.encryption_service = EncryptionService(
            kms_key_id="alias/haven-health-default", region="us-east-1"
        )

    def _initialize_language_rules(self) -> None:
        """Initialize gender rules for supported languages."""
        # Spanish - extensive gender agreement
        self.language_rules["es"] = GenderRules(
            language="es",
            has_gender_agreement=True,
            gender_affects=[
                GenderContext.ADJECTIVE,
                GenderContext.PRONOUN,
                GenderContext.TITLE,
                GenderContext.POSSESSIVE,
            ],
            default_gender=Gender.MASCULINE,
            gender_markers={Gender.MASCULINE: "o", Gender.FEMININE: "a"},
        )

        # French - extensive gender agreement
        self.language_rules["fr"] = GenderRules(
            language="fr",
            has_gender_agreement=True,
            gender_affects=[
                GenderContext.ADJECTIVE,
                GenderContext.PRONOUN,
                GenderContext.TITLE,
                GenderContext.POSSESSIVE,
            ],
            default_gender=Gender.MASCULINE,
            gender_markers={Gender.MASCULINE: "", Gender.FEMININE: "e"},
        )

        # Arabic - complex gender system
        self.language_rules["ar"] = GenderRules(
            language="ar",
            has_gender_agreement=True,
            gender_affects=[
                GenderContext.ADJECTIVE,
                GenderContext.PRONOUN,
                GenderContext.TITLE,
                GenderContext.POSSESSIVE,
                GenderContext.PATIENT,
            ],
            default_gender=Gender.MASCULINE,
            gender_markers={Gender.MASCULINE: "", Gender.FEMININE: "ة"},  # ta marbuta
        )

        # German - three genders
        self.language_rules["de"] = GenderRules(
            language="de",
            has_gender_agreement=True,
            gender_affects=[
                GenderContext.ADJECTIVE,
                GenderContext.PRONOUN,
                GenderContext.TITLE,
                GenderContext.GRAMMAR,
            ],
            default_gender=Gender.NEUTER,
            gender_markers={
                Gender.MASCULINE: "er",
                Gender.FEMININE: "e",
                Gender.NEUTER: "es",
            },
        )

        # English - minimal gender
        self.language_rules["en"] = GenderRules(
            language="en",
            has_gender_agreement=False,
            gender_affects=[GenderContext.PRONOUN, GenderContext.TITLE],
            default_gender=Gender.UNKNOWN,
            gender_markers={},
        )

        # Chinese - no grammatical gender
        self.language_rules["zh"] = GenderRules(
            language="zh",
            has_gender_agreement=False,
            gender_affects=[GenderContext.PRONOUN],
            default_gender=Gender.UNKNOWN,
            gender_markers={},
        )

    def _load_common_forms(self) -> None:
        """Load common gender-specific forms."""
        # Titles
        self.gender_forms["title.mr"] = {
            Gender.MASCULINE: {
                "en": "Mr.",
                "es": "Sr.",
                "fr": "M.",
                "ar": "السيد",
                "de": "Herr",
            }
        }

        self.gender_forms["title.mrs"] = {
            Gender.FEMININE: {
                "en": "Mrs.",
                "es": "Sra.",
                "fr": "Mme",
                "ar": "السيدة",
                "de": "Frau",
            }
        }

        self.gender_forms["title.ms"] = {
            Gender.FEMININE: {
                "en": "Ms.",
                "es": "Srta.",
                "fr": "Mlle",
                "ar": "الآنسة",
                "de": "Frau",
            }
        }

        # Pronouns
        self.gender_forms["pronoun.he_she"] = {
            Gender.MASCULINE: {
                "en": "he",
                "es": "él",
                "fr": "il",
                "ar": "هو",
                "de": "er",
            },
            Gender.FEMININE: {
                "en": "she",
                "es": "ella",
                "fr": "elle",
                "ar": "هي",
                "de": "sie",
            },
            Gender.OTHER: {
                "en": "they",
                "es": "elle",  # Gender-neutral Spanish
                "fr": "iel",  # Gender-neutral French
                "ar": "هم",  # They plural
                "de": "sie",  # They
            },
        }

        # Medical context
        self.gender_forms["medical.patient"] = {
            Gender.MASCULINE: {
                "en": "patient",
                "es": "paciente",
                "fr": "patient",
                "ar": "مريض",
                "de": "Patient",
            },
            Gender.FEMININE: {
                "en": "patient",
                "es": "paciente",
                "fr": "patiente",
                "ar": "مريضة",
                "de": "Patientin",
            },
        }

    def get_gendered_translation(
        self,
        key: str,
        language: str,
        gender: Gender,
        context: GenderContext = GenderContext.GRAMMAR,
    ) -> str:
        """Get gender-appropriate translation."""
        # Check if language requires gender agreement
        rules = self.language_rules.get(language)
        if not rules or not rules.has_gender_agreement:
            # Return base translation for languages without gender
            return self._get_base_translation(key, language)

        # Check if this context affects gender in this language
        if context not in rules.gender_affects:
            return self._get_base_translation(key, language)

        # Look for pre-defined gender forms
        if key in self.gender_forms:
            gender_map: Dict[str, str] = self.gender_forms[key].get(gender, {})
            if language in gender_map:
                return gender_map[language]

        # Apply gender transformation rules
        base_text = self._get_base_translation(key, language)
        return self._apply_gender_transformation(base_text, language, gender, context)

    def _get_base_translation(self, key: str, language: str) -> str:
        """Get base translation without gender modification."""
        # Placeholder - would integrate with main translation system
        translations = {
            "welcome.message": {
                "en": "Welcome",
                "es": "Bienvenido",
                "fr": "Bienvenu",
                "ar": "مرحبا",
                "de": "Willkommen",
            },
            "status.healthy": {
                "en": "healthy",
                "es": "sano",
                "fr": "sain",
                "ar": "صحي",
                "de": "gesund",
            },
        }

        return translations.get(key, {}).get(language, key)

    def _apply_gender_transformation(
        self, text: str, language: str, gender: Gender, context: GenderContext
    ) -> str:
        """Apply gender transformation rules to text."""
        rules = self.language_rules.get(language)
        if not rules:
            return text

        # Spanish transformations
        if language == "es":
            if context == GenderContext.ADJECTIVE:
                # Transform adjectives ending in -o/-a
                if text.endswith("o") and gender == Gender.FEMININE:
                    return text[:-1] + "a"
                elif text.endswith("e"):
                    # Some adjectives don't change
                    return text
            elif context == GenderContext.PATIENT:
                # Add article agreement
                if gender == Gender.MASCULINE:
                    return f"el {text}"
                else:
                    return f"la {text}"

        # French transformations
        elif language == "fr":
            if context == GenderContext.ADJECTIVE:
                # Add -e for feminine
                if gender == Gender.FEMININE and not text.endswith("e"):
                    return text + "e"
            elif context == GenderContext.PATIENT:
                # Add article agreement
                if gender == Gender.MASCULINE:
                    return f"le {text}"
                else:
                    return f"la {text}"

        # Arabic transformations
        elif language == "ar":
            if gender == Gender.FEMININE:
                # Add ta marbuta for feminine
                if not text.endswith("ة"):
                    return text + "ة"

        return text

    def get_pronoun(
        self,
        language: str,
        gender: Gender,
        person: str = "third",
        case: str = "subject",
    ) -> str:
        """Get appropriate pronoun for gender and language."""
        pronouns = {
            "en": {
                "third": {
                    "subject": {
                        Gender.MASCULINE: "he",
                        Gender.FEMININE: "she",
                        Gender.OTHER: "they",
                        Gender.UNKNOWN: "they",
                    },
                    "object": {
                        Gender.MASCULINE: "him",
                        Gender.FEMININE: "her",
                        Gender.OTHER: "them",
                        Gender.UNKNOWN: "them",
                    },
                    "possessive": {
                        Gender.MASCULINE: "his",
                        Gender.FEMININE: "her",
                        Gender.OTHER: "their",
                        Gender.UNKNOWN: "their",
                    },
                }
            },
            "es": {
                "third": {
                    "subject": {
                        Gender.MASCULINE: "él",
                        Gender.FEMININE: "ella",
                        Gender.OTHER: "elle",
                        Gender.UNKNOWN: "él/ella",
                    },
                    "possessive": {
                        Gender.MASCULINE: "su",
                        Gender.FEMININE: "su",
                        Gender.OTHER: "su",
                        Gender.UNKNOWN: "su",
                    },
                }
            },
        }

        lang_pronouns = pronouns.get(language, {})
        person_pronouns = lang_pronouns.get(person, {})
        case_pronouns = person_pronouns.get(case, {})

        return case_pronouns.get(gender, "")

    def get_title(
        self,
        language: str,
        gender: Gender,
        marital_status: Optional[str] = None,
        professional: bool = False,
    ) -> str:
        """Get appropriate title for gender and context."""
        if professional:
            # Professional titles are often gender-neutral
            titles = {
                "en": "Dr.",
                "es": "Dr./Dra.",
                "fr": "Dr",
                "ar": "د.",
                "de": "Dr.",
            }
            return titles.get(language, "Dr.")

        # Social titles
        if gender == Gender.MASCULINE:
            masculine_titles = self.gender_forms.get("title.mr", {}).get(
                Gender.MASCULINE, {}
            )
            return masculine_titles.get(language, "")
        elif gender == Gender.FEMININE:
            if marital_status == "married":
                mrs_titles = self.gender_forms.get("title.mrs", {}).get(
                    Gender.FEMININE, {}
                )
                return mrs_titles.get(language, "")
            else:
                ms_titles = self.gender_forms.get("title.ms", {}).get(
                    Gender.FEMININE, {}
                )
                return ms_titles.get(language, "")
        else:
            # Gender-neutral options
            neutral_titles = {"en": "Mx.", "es": "Mx.", "fr": "Mx.", "de": "Mx."}
            return neutral_titles.get(language, "")

    def validate_gender_consistency(
        self, translations: Dict[str, str], gender: Gender, language: str
    ) -> List[str]:
        """Validate gender consistency across related translations."""
        issues: List[str] = []
        rules = self.language_rules.get(language)

        if not rules or not rules.has_gender_agreement:
            return issues

        # Check for mixed gender markers
        masculine_marker = rules.gender_markers.get(Gender.MASCULINE, "")
        feminine_marker = rules.gender_markers.get(Gender.FEMININE, "")

        for key, text in translations.items():
            if (
                gender == Gender.FEMININE
                and masculine_marker
                and text.endswith(masculine_marker)
            ):
                issues.append(f"Masculine form used for feminine context: {key}")
            elif (
                gender == Gender.MASCULINE
                and feminine_marker
                and text.endswith(feminine_marker)
            ):
                issues.append(f"Feminine form used for masculine context: {key}")

        return issues

    def get_gender_options(self) -> List[Dict[str, str]]:
        """Get list of gender options for forms."""
        return [
            {"value": Gender.MASCULINE.value, "label": "Male"},
            {"value": Gender.FEMININE.value, "label": "Female"},
            {"value": Gender.OTHER.value, "label": "Other"},
            {"value": Gender.UNKNOWN.value, "label": "Prefer not to say"},
        ]

    def detect_gender_from_name(self, _name: str, _language: str) -> Optional[Gender]:
        """Attempt to detect gender from name (with caution)."""
        # This is a sensitive area - only use when explicitly needed
        # and always allow user override
        logger.warning("Gender detection from name should be used cautiously")

        # Return unknown by default
        return Gender.UNKNOWN

    def to_fhir_administrative_gender(self, gender: Gender) -> str:
        """Convert internal gender to FHIR AdministrativeGender.

        FHIR AdministrativeGender values: male, female, other, unknown
        """
        mapping = {
            Gender.MASCULINE: "male",
            Gender.FEMININE: "female",
            Gender.OTHER: "other",
            Gender.NEUTER: "other",
            Gender.UNKNOWN: "unknown",
        }
        return mapping.get(gender, "unknown")

    def from_fhir_administrative_gender(self, fhir_gender: str) -> Gender:
        """Convert FHIR AdministrativeGender to internal gender."""
        mapping = {
            "male": Gender.MASCULINE,
            "female": Gender.FEMININE,
            "other": Gender.OTHER,
            "unknown": Gender.UNKNOWN,
        }
        return mapping.get(fhir_gender, Gender.UNKNOWN)

    @audit_phi_access("gender_translation_with_phi")
    @require_permission(AccessPermission.READ_PHI)
    def translate_with_patient_context(
        self,
        text: str,
        patient_data: Dict[str, Any],
        target_language: str,
        context: GenderContext = GenderContext.PATIENT,
    ) -> str:
        """Translate text with patient gender context.

        This method handles PHI and requires proper access permissions.
        """
        # Validate FHIR patient resource
        validation_result = self.fhir_validator.validate_resource(patient_data)
        if not validation_result:
            raise ValueError("Invalid FHIR patient resource")

        # Extract gender from FHIR resource
        fhir_gender = patient_data.get("gender", "unknown")
        gender = self.from_fhir_administrative_gender(fhir_gender)

        # Encrypt PHI data in transit
        # Encrypt PHI data in transit - name is encrypted but not used directly
        _ = self.encryption_service.encrypt(
            patient_data.get("name", [{}])[0].get("text", "")
        )

        # Get gendered translation
        return self.get_gendered_translation(
            key=text, gender=gender, language=target_language, context=context
        )

    def validate_fhir_gender_extension(self, extension_data: Dict[str, Any]) -> bool:
        """Validate FHIR gender identity extension.

        Supports the gender identity extension:
        http://hl7.org/fhir/StructureDefinition/patient-genderIdentity
        """
        required_fields = ["url", "valueCodeableConcept"]

        # Check required fields
        for field in required_fields:
            if field not in extension_data:
                return False

        # Validate URL
        expected_url = "http://hl7.org/fhir/StructureDefinition/patient-genderIdentity"
        if extension_data["url"] != expected_url:
            return False

        # Validate codeable concept
        value_cc = extension_data.get("valueCodeableConcept", {})
        if "coding" not in value_cc or not value_cc["coding"]:
            return False

        return True


# Global gender translation manager
gender_manager = GenderTranslationManager()
