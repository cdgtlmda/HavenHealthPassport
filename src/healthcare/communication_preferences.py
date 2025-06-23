"""Patient Communication Preferences.

This module handles patient communication preferences including language
preferences, interpreter needs, communication methods, and accessibility
requirements for diverse refugee populations. All PHI data is encrypted
and access is controlled through role-based permissions.
"""

import logging
from enum import Enum
from typing import Any, Dict, List, Optional

from src.healthcare.fhir_types import FHIRCommunication as FHIRCommunicationType
from src.healthcare.fhir_types import (
    FHIRTypedResource,
)
from src.healthcare.fhir_validator import FHIRValidator
from src.healthcare.hipaa_access_control import (
    AccessLevel,
    audit_phi_access,
    require_phi_access,
)
from src.security.encryption import EncryptionService

# FHIR resource type for this module
__fhir_resource__ = "Communication"
__fhir_type__ = "Communication"

logger = logging.getLogger(__name__)


class FHIRCommunication(FHIRCommunicationType):
    """FHIR Communication resource type definition."""

    # Additional Haven-specific fields can be added here


class LanguageProficiency(Enum):
    """Language proficiency levels based on CEFR scale."""

    NATIVE = "native"  # Native speaker
    FLUENT = "fluent"  # C2 - Mastery
    ADVANCED = "advanced"  # C1 - Advanced
    INTERMEDIATE = "intermediate"  # B1-B2 - Independent user
    BASIC = "basic"  # A1-A2 - Basic user
    NONE = "none"  # No proficiency

    # Special cases
    RECEPTIVE_ONLY = "receptive"  # Can understand but not speak
    WRITTEN_ONLY = "written"  # Can read/write but not speak


class CommunicationMode(Enum):
    """Modes of communication."""

    SPOKEN = "spoken"
    WRITTEN = "written"
    SIGNED = "signed"
    TACTILE = "tactile"
    VISUAL = "visual"
    ASSISTED = "assisted"


class InterpreterNeed(Enum):
    """Types of interpreter services needed."""

    NONE = "none"
    PREFERRED = "preferred"  # Preferred but not required
    REQUIRED = "required"  # Required for effective communication
    CRITICAL = "critical"  # Critical for safety/consent

    # Specific types
    MEDICAL = "medical"  # Medical interpreter needed
    LEGAL = "legal"  # Legal interpreter needed
    MENTAL_HEALTH = "mental-health"  # Mental health specialized
    GENDER_SPECIFIC = "gender-specific"  # Same gender interpreter


class CommunicationBarrier(Enum):
    """Common communication barriers."""

    # Language barriers
    LANGUAGE = "language"
    DIALECT = "dialect"
    LITERACY = "literacy"

    # Sensory barriers
    HEARING_LOSS = "hearing-loss"
    VISION_LOSS = "vision-loss"
    SPEECH_IMPAIRMENT = "speech-impairment"

    # Cognitive barriers
    COGNITIVE_IMPAIRMENT = "cognitive-impairment"
    DEVELOPMENTAL_DELAY = "developmental-delay"
    DEMENTIA = "dementia"

    # Cultural barriers
    CULTURAL_TABOO = "cultural-taboo"
    GENDER_RESTRICTION = "gender-restriction"
    RELIGIOUS_RESTRICTION = "religious-restriction"

    # Technical barriers
    NO_PHONE = "no-phone"
    NO_INTERNET = "no-internet"
    TECHNOLOGY_UNFAMILIAR = "technology-unfamiliar"


class PreferredContactTime(Enum):
    """Preferred times for contact."""

    ANYTIME = "anytime"
    MORNING = "morning"  # 6 AM - 12 PM
    AFTERNOON = "afternoon"  # 12 PM - 6 PM
    EVENING = "evening"  # 6 PM - 10 PM
    WEEKDAYS = "weekdays"
    WEEKENDS = "weekends"
    EMERGENCY_ONLY = "emergency-only"


class LanguageService:
    """Language and interpreter service management."""

    # Common languages in refugee contexts
    REFUGEE_LANGUAGES = {
        # Middle East
        "ar": {"name": "Arabic", "script": "Arab", "regions": ["SY", "IQ", "YE", "PS"]},
        "ku": {
            "name": "Kurdish",
            "script": "Arab",
            "regions": ["SY", "IQ", "TR", "IR"],
        },
        "kmr": {"name": "Kurmanji", "script": "Latn", "regions": ["SY", "TR"]},
        "ckb": {"name": "Sorani", "script": "Arab", "regions": ["IQ", "IR"]},
        "fa": {"name": "Farsi/Persian", "script": "Arab", "regions": ["IR", "AF"]},
        "ps": {"name": "Pashto", "script": "Arab", "regions": ["AF", "PK"]},
        "ur": {"name": "Urdu", "script": "Arab", "regions": ["PK", "IN"]},
        # Africa
        "so": {"name": "Somali", "script": "Latn", "regions": ["SO", "ET", "KE"]},
        "am": {"name": "Amharic", "script": "Ethi", "regions": ["ET"]},
        "ti": {"name": "Tigrinya", "script": "Ethi", "regions": ["ER", "ET"]},
        "om": {"name": "Oromo", "script": "Latn", "regions": ["ET", "KE"]},
        "sw": {
            "name": "Swahili",
            "script": "Latn",
            "regions": ["KE", "TZ", "UG", "CD"],
        },
        "rn": {"name": "Kirundi", "script": "Latn", "regions": ["BI"]},
        "rw": {"name": "Kinyarwanda", "script": "Latn", "regions": ["RW"]},
        "lg": {"name": "Luganda", "script": "Latn", "regions": ["UG"]},
        "ln": {"name": "Lingala", "script": "Latn", "regions": ["CD", "CG"]},
        # Asia
        "my": {"name": "Burmese", "script": "Mymr", "regions": ["MM"]},
        "bn": {"name": "Bengali", "script": "Beng", "regions": ["BD", "IN"]},
        "roh": {"name": "Rohingya", "script": "Arab", "regions": ["MM", "BD"]},
        "ne": {"name": "Nepali", "script": "Deva", "regions": ["NP", "IN"]},
        "si": {"name": "Sinhala", "script": "Sinh", "regions": ["LK"]},
        "ta": {"name": "Tamil", "script": "Taml", "regions": ["LK", "IN"]},
        # Sign languages
        "ase": {"name": "American Sign Language", "script": "Sgnw", "regions": ["US"]},
        "bfi": {"name": "British Sign Language", "script": "Sgnw", "regions": ["GB"]},
        "fsl": {"name": "French Sign Language", "script": "Sgnw", "regions": ["FR"]},
        "asl-ea": {
            "name": "East African Sign Language",
            "script": "Sgnw",
            "regions": ["KE", "UG", "TZ"],
        },
    }

    @classmethod
    def get_language_info(cls, language_code: str) -> Optional[Dict]:
        """Get information about a language."""
        return cls.REFUGEE_LANGUAGES.get(language_code)

    @classmethod
    def get_languages_for_region(cls, region_code: str) -> List[str]:
        """Get common languages for a region."""
        languages = []
        for code, info in cls.REFUGEE_LANGUAGES.items():
            if region_code in info.get("regions", []):
                languages.append(code)
        return languages

    @classmethod
    def is_sign_language(cls, language_code: str) -> bool:
        """Check if a language is a sign language."""
        info = cls.get_language_info(language_code)
        if info and isinstance(info, dict):
            return info.get("script") == "Sgnw"
        return False


class CommunicationPreferences(FHIRTypedResource):
    """Patient communication preferences structure."""

    # FHIR resource type
    __fhir_resource__ = "Communication"

    def __init__(self) -> None:
        """Initialize communication preferences."""
        self.languages: List[Dict[str, Any]] = []
        self.interpreter_need: InterpreterNeed = InterpreterNeed.NONE
        self.preferred_modes: List[CommunicationMode] = []
        self.barriers: List[CommunicationBarrier] = []
        self.contact_times: List[PreferredContactTime] = []
        self.emergency_contact_ok: bool = True
        self.sms_ok: bool = True
        self.encryption_service = EncryptionService(
            kms_key_id="alias/haven-health-default", region="us-east-1"
        )
        self.voice_call_ok: bool = True
        self.video_call_ok: bool = False
        self.written_materials_ok: bool = True
        self.family_interpreter_ok: bool = True
        self.child_interpreter_ok: bool = False
        self.preferred_interpreter_gender: Optional[str] = None
        self.cultural_considerations: List[str] = []
        self.assistive_devices: List[str] = []
        self.notes: Optional[str] = None
        self.fhir_validator = FHIRValidator()

    @property
    def __fhir_resource_type__(self) -> str:
        """Return the FHIR resource type."""
        return "Communication"

    def validate_fhir(self) -> Dict[str, Any]:
        """Validate the FHIR resource (required by FHIRTypedResource)."""
        return self.validate_fhir_communication()

    @require_phi_access(AccessLevel.WRITE)
    @audit_phi_access("add_communication_language")
    def add_language(
        self,
        code: str,
        proficiency: LanguageProficiency,
        is_preferred: bool = False,
        modes: Optional[List[CommunicationMode]] = None,
    ) -> "CommunicationPreferences":
        """Add a language preference.

        self._encryption_service = EncryptionService(kms_key_id="alias/haven-health-default")
        Args:
            code: ISO 639 language code
            proficiency: Proficiency level
            is_preferred: Whether this is the preferred language
            modes: Specific modes available for this language
        """
        language_info = LanguageService.get_language_info(code)

        language_pref = {
            "code": code,
            "display": language_info["name"] if language_info else code,
            "proficiency": proficiency.value,
            "preferred": is_preferred,
        }

        if modes:
            language_pref["modes"] = [mode.value for mode in modes]
        elif LanguageService.is_sign_language(code):
            language_pref["modes"] = [CommunicationMode.SIGNED.value]
        else:
            language_pref["modes"] = [
                CommunicationMode.SPOKEN.value,
                CommunicationMode.WRITTEN.value,
            ]

        # If preferred, move to front of list
        if is_preferred:
            self.languages.insert(0, language_pref)
            # Update other languages to not be preferred
            for _, lang in enumerate(self.languages[1:], 1):
                lang["preferred"] = False
        else:
            self.languages.append(language_pref)

        return self

    @require_phi_access(AccessLevel.WRITE)
    @audit_phi_access("set_interpreter_need")
    def set_interpreter_need(
        self, need: InterpreterNeed, languages: Optional[List[str]] = None
    ) -> "CommunicationPreferences":
        """Set interpreter need level.

        Args:
            need: Level of interpreter need
            languages: Specific languages needing interpretation
        """
        self.interpreter_need = need

        if languages:
            # Mark specific languages as needing interpretation
            for lang in self.languages:
                if lang["code"] in languages:
                    lang["interpreter_needed"] = True

        return self

    @require_phi_access(AccessLevel.WRITE)
    @audit_phi_access("add_communication_mode")
    def add_communication_mode(
        self, mode: CommunicationMode
    ) -> "CommunicationPreferences":
        """Add preferred communication mode."""
        if mode not in self.preferred_modes:
            self.preferred_modes.append(mode)
        return self

    def add_barrier(self, barrier: CommunicationBarrier) -> "CommunicationPreferences":
        """Add communication barrier."""
        if barrier not in self.barriers:
            self.barriers.append(barrier)

            # Auto-adjust preferences based on barrier
            if barrier == CommunicationBarrier.HEARING_LOSS:
                self.voice_call_ok = False
                self.add_communication_mode(CommunicationMode.WRITTEN)
                self.add_communication_mode(CommunicationMode.VISUAL)
            elif barrier == CommunicationBarrier.VISION_LOSS:
                self.written_materials_ok = False
                self.video_call_ok = False
                self.add_communication_mode(CommunicationMode.SPOKEN)
            elif barrier == CommunicationBarrier.LITERACY:
                self.written_materials_ok = False
                self.sms_ok = False
                self.add_communication_mode(CommunicationMode.SPOKEN)
            elif barrier == CommunicationBarrier.NO_PHONE:
                self.sms_ok = False
                self.voice_call_ok = False
                self.video_call_ok = False

        return self

    def set_contact_preferences(
        self,
        sms: bool = True,
        voice: bool = True,
        video: bool = False,
        written: bool = True,
    ) -> "CommunicationPreferences":
        """Set contact method preferences."""
        self.sms_ok = sms
        self.voice_call_ok = voice
        self.video_call_ok = video
        self.written_materials_ok = written
        return self

    def add_contact_time(
        self, time_preference: PreferredContactTime
    ) -> "CommunicationPreferences":
        """Add preferred contact time."""
        if time_preference not in self.contact_times:
            self.contact_times.append(time_preference)
        return self

    def set_interpreter_preferences(
        self,
        family_ok: bool = True,
        child_ok: bool = False,
        gender_preference: Optional[str] = None,
    ) -> "CommunicationPreferences":
        """Set interpreter preferences."""
        self.family_interpreter_ok = family_ok
        self.child_interpreter_ok = child_ok
        self.preferred_interpreter_gender = gender_preference
        return self

    def add_cultural_consideration(
        self, consideration: str
    ) -> "CommunicationPreferences":
        """Add cultural consideration."""
        self.cultural_considerations.append(consideration)
        return self

    def add_assistive_device(self, device: str) -> "CommunicationPreferences":
        """Add assistive device used."""
        self.assistive_devices.append(device)
        return self

    def set_notes(self, notes: str) -> "CommunicationPreferences":
        """Set additional notes."""
        self.notes = notes
        return self

    def to_fhir(self) -> List[Dict[str, Any]]:
        """Convert to FHIR communication array."""
        communications = []

        for lang in self.languages:
            comm = {
                "language": {
                    "coding": [
                        {
                            "system": "urn:ietf:bcp:47",
                            "code": lang["code"],
                            "display": lang["display"],
                        }
                    ]
                },
                "preferred": lang.get("preferred", False),
            }

            # Add extensions
            extensions = []

            # Proficiency extension
            extensions.append(
                {
                    "url": "http://havenhealthpassport.org/fhir/extension/language-proficiency",
                    "valueCode": lang["proficiency"],
                }
            )

            # Communication modes
            if "modes" in lang:
                for mode in lang["modes"]:
                    extensions.append(
                        {
                            "url": "http://havenhealthpassport.org/fhir/extension/communication-mode",
                            "valueCode": mode,
                        }
                    )

            # Interpreter need
            if lang.get("interpreter_needed"):
                extensions.append(
                    {
                        "url": "http://havenhealthpassport.org/fhir/extension/interpreter-needed",
                        "valueBoolean": True,
                    }
                )

            if extensions:
                comm["extension"] = extensions

            communications.append(comm)

        return communications

    @require_phi_access(AccessLevel.READ)
    @audit_phi_access("get_effective_languages")
    def get_effective_languages(self) -> List[str]:
        """Get list of languages patient can effectively communicate in."""
        effective = []

        for lang in self.languages:
            proficiency = LanguageProficiency(lang["proficiency"])
            if proficiency not in [LanguageProficiency.NONE, LanguageProficiency.BASIC]:
                effective.append(lang["code"])

        return effective

    def needs_interpreter(self) -> bool:
        """Check if patient needs interpreter services."""
        return self.interpreter_need not in [
            InterpreterNeed.NONE,
            InterpreterNeed.PREFERRED,
        ]

    @require_phi_access(AccessLevel.READ)
    @audit_phi_access("get_communication_summary")
    def get_communication_summary(self) -> str:
        """Get human-readable communication summary."""
        parts = []

        # Primary language
        if self.languages:
            primary = next(
                (lang for lang in self.languages if lang.get("preferred")),
                self.languages[0],
            )
            parts.append(f"Primary language: {primary['display']}")

        # Interpreter need
        if self.needs_interpreter():
            parts.append(f"Interpreter {self.interpreter_need.value}")

        # Communication barriers
        if self.barriers:
            barrier_names = [b.value.replace("-", " ") for b in self.barriers]
            parts.append(f"Barriers: {', '.join(barrier_names)}")

        # Contact preferences
        contact_methods = []
        if self.sms_ok:
            contact_methods.append("SMS")
        if self.voice_call_ok:
            contact_methods.append("voice")
        if self.video_call_ok:
            contact_methods.append("video")
        if contact_methods:
            parts.append(f"Contact: {', '.join(contact_methods)}")

        return "; ".join(parts)

    def validate_fhir_communication(self) -> Dict[str, Any]:
        """Validate FHIR communication resources.

        Returns:
            Validation result with 'valid', 'errors', and 'warnings' keys
        """
        validation_result: Dict[str, Any] = {
            "valid": True,
            "errors": [],
            "warnings": [],
        }

        # Validate each communication entry
        communications = self.to_fhir()

        for idx, comm in enumerate(communications):
            # Check required fields
            if "language" not in comm:
                validation_result["errors"].append(
                    f"Communication {idx}: Missing required 'language' field"
                )
                validation_result["valid"] = False
            else:
                # Validate language structure
                lang = comm["language"]
                if "coding" not in lang or not lang["coding"]:
                    validation_result["errors"].append(
                        f"Communication {idx}: Language must have at least one coding"
                    )
                    validation_result["valid"] = False
                else:
                    # Validate each coding
                    for coding_idx, coding in enumerate(lang["coding"]):
                        if "code" not in coding:
                            validation_result["errors"].append(
                                f"Communication {idx}, coding {coding_idx}: Missing required 'code'"
                            )
                            validation_result["valid"] = False
                        if "system" not in coding:
                            validation_result["warnings"].append(
                                f"Communication {idx}, coding {coding_idx}: Missing 'system' identifier"
                            )

            # Validate extensions if present
            if "extension" in comm:
                for ext_idx, ext in enumerate(comm["extension"]):
                    if "url" not in ext:
                        validation_result["errors"].append(
                            f"Communication {idx}, extension {ext_idx}: Missing required 'url'"
                        )
                        validation_result["valid"] = False

                    # Check for value[x]
                    value_fields = [k for k in ext.keys() if k.startswith("value")]
                    if not value_fields:
                        validation_result["errors"].append(
                            f"Communication {idx}, extension {ext_idx}: Extension must have a value[x] field"
                        )
                        validation_result["valid"] = False

        return validation_result


class CommunicationAssessment:
    """Assess communication needs and make recommendations."""

    @staticmethod
    def assess_needs(preferences: CommunicationPreferences) -> Dict[str, Any]:
        """Perform comprehensive communication needs assessment.

        Args:
            preferences: Patient's communication preferences

        Returns:
            Assessment with recommendations
        """
        assessment = {
            "interpreter_required": preferences.needs_interpreter(),
            "languages_available": preferences.get_effective_languages(),
            "barriers_identified": [b.value for b in preferences.barriers],
            "recommendations": [],
            "risk_level": "low",
        }

        # Check for critical combinations
        if preferences.interpreter_need == InterpreterNeed.CRITICAL:
            assessment["risk_level"] = "high"
            assessment["recommendations"].append(
                "Always use professional medical interpreter"
            )

        # Language-specific recommendations
        if not preferences.languages:
            assessment["risk_level"] = "high"
            assessment["recommendations"].append(
                "Identify patient's primary language urgently"
            )

        # Barrier-specific recommendations
        for barrier in preferences.barriers:
            if barrier == CommunicationBarrier.HEARING_LOSS:
                assessment["recommendations"].append(
                    "Use written materials and visual aids"
                )
                assessment["recommendations"].append(
                    "Consider sign language interpreter"
                )
            elif barrier == CommunicationBarrier.VISION_LOSS:
                assessment["recommendations"].append("Provide audio materials")
                assessment["recommendations"].append("Ensure verbal consent processes")
            elif barrier == CommunicationBarrier.LITERACY:
                assessment["recommendations"].append("Use pictographic materials")
                assessment["recommendations"].append("Provide verbal explanations")
            elif barrier == CommunicationBarrier.COGNITIVE_IMPAIRMENT:
                assessment["recommendations"].append("Use simple language")
                assessment["recommendations"].append("Allow extra time")
                assessment["recommendations"].append("Include caregiver if appropriate")

        # Cultural considerations
        if preferences.cultural_considerations:
            assessment["recommendations"].append(
                "Review cultural considerations before interaction"
            )

        # Gender preferences
        if preferences.preferred_interpreter_gender:
            assessment["recommendations"].append(
                f"Use {preferences.preferred_interpreter_gender} interpreter when possible"
            )

        # Child interpreter warning
        if preferences.child_interpreter_ok:
            assessment["recommendations"].append(
                "WARNING: Avoid using children as interpreters for medical information"
            )
            assessment["risk_level"] = "medium"

        return assessment


def create_default_preferences_for_language(
    language_code: str,
) -> CommunicationPreferences:
    """Create default communication preferences for a language.

    Args:
        language_code: ISO 639 language code

    Returns:
        Pre-configured CommunicationPreferences
    """
    prefs = CommunicationPreferences()

    # Add primary language
    prefs.add_language(language_code, LanguageProficiency.NATIVE, is_preferred=True)

    # Add common secondary languages based on region
    language_info = LanguageService.get_language_info(language_code)
    if language_info:
        regions = language_info.get("regions", [])

        # Add regional lingua francas
        if any(r in regions for r in ["KE", "UG", "TZ"]):
            prefs.add_language("sw", LanguageProficiency.BASIC)  # Swahili
        if any(r in regions for r in ["SY", "IQ", "JO", "LB"]):
            prefs.add_language("ar", LanguageProficiency.INTERMEDIATE)  # Arabic

        # Add English/French for former colonies
        if any(r in ["KE", "UG", "NG", "GH"] for r in regions):
            prefs.add_language("en", LanguageProficiency.BASIC)  # English
        if any(r in ["CD", "BI", "RW", "ML"] for r in regions):
            prefs.add_language("fr", LanguageProficiency.BASIC)  # French

    # Set interpreter need if not a major language
    if language_code not in ["en", "fr", "ar", "sw", "es"]:
        prefs.set_interpreter_need(InterpreterNeed.PREFERRED)

    return prefs
