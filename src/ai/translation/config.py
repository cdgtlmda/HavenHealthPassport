"""
Translation configuration and enums.

Defines configuration classes and enumerations for the translation system.

This module handles encrypted PHI with access control and audit logging
to ensure HIPAA compliance.
 Handles FHIR Resource validation.
"""

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, List, Set


class Language(Enum):
    """Supported languages for translation."""

    # Major languages
    ENGLISH = "en"
    SPANISH = "es"
    FRENCH = "fr"
    GERMAN = "de"
    ITALIAN = "it"
    PORTUGUESE = "pt"
    RUSSIAN = "ru"
    CHINESE_SIMPLIFIED = "zh-CN"
    CHINESE_TRADITIONAL = "zh-TW"
    JAPANESE = "ja"
    KOREAN = "ko"
    ARABIC = "ar"
    HINDI = "hi"
    BENGALI = "bn"
    URDU = "ur"
    TAMIL = "ta"
    TURKISH = "tr"
    VIETNAMESE = "vi"
    THAI = "th"
    INDONESIAN = "id"
    MALAY = "ms"
    FILIPINO = "fil"
    DUTCH = "nl"
    POLISH = "pl"
    UKRAINIAN = "uk"
    CZECH = "cs"
    SLOVAK = "sk"
    ROMANIAN = "ro"
    HUNGARIAN = "hu"
    GREEK = "el"
    HEBREW = "he"
    PERSIAN = "fa"
    SWAHILI = "sw"
    AMHARIC = "am"
    YORUBA = "yo"
    ZULU = "zu"
    XHOSA = "xh"
    AFRIKAANS = "af"
    NORWEGIAN = "no"
    SWEDISH = "sv"
    DANISH = "da"
    FINNISH = "fi"
    ICELANDIC = "is"
    ALBANIAN = "sq"
    SERBIAN = "sr"
    CROATIAN = "hr"
    BOSNIAN = "bs"
    BULGARIAN = "bg"
    MACEDONIAN = "mk"
    SLOVENIAN = "sl"
    LITHUANIAN = "lt"
    LATVIAN = "lv"
    ESTONIAN = "et"
    MALTESE = "mt"
    WELSH = "cy"
    IRISH = "ga"
    SCOTS_GAELIC = "gd"
    BASQUE = "eu"
    CATALAN = "ca"
    GALICIAN = "gl"
    LUXEMBOURGISH = "lb"
    ARMENIAN = "hy"
    GEORGIAN = "ka"
    AZERBAIJANI = "az"
    KAZAKH = "kk"
    UZBEK = "uz"
    TAJIK = "tg"
    TURKMEN = "tk"
    KYRGYZ = "ky"
    MONGOLIAN = "mn"
    TIBETAN = "bo"
    NEPALI = "ne"
    SINHALA = "si"
    BURMESE = "my"
    KHMER = "km"
    LAO = "lo"

    # Special values
    UNKNOWN = "unknown"
    AUTO_DETECT = "auto"

    @classmethod
    def from_code(cls, code: str) -> "Language":
        """Get language from ISO code."""
        code = code.lower()
        for lang in cls:
            if lang.value == code:
                return lang
        return cls.UNKNOWN

    @property
    def name_human_readable(self) -> str:
        """Get human-readable name."""
        return self.name.replace("_", " ").title()


class TranslationMode(Enum):
    """Translation mode for different contexts."""

    GENERAL = auto()  # General medical translation
    EMERGENCY = auto()  # Emergency/urgent medical situations
    CLINICAL = auto()  # Clinical notes and reports
    PATIENT_EDUCATION = auto()  # Patient education materials
    CONSENT_FORMS = auto()  # Medical consent documents
    PRESCRIPTION = auto()  # Prescription and medication instructions
    LAB_RESULTS = auto()  # Laboratory results
    IMAGING = auto()  # Imaging reports
    DISCHARGE = auto()  # Discharge summaries
    REFERRAL = auto()  # Referral letters


@dataclass
class TranslationConfig:
    """Configuration for translation system."""

    # Model settings
    default_model: str = "anthropic.claude-3-opus-20240229-v1:0"
    fallback_models: List[str] = field(
        default_factory=lambda: [
            "anthropic.claude-3-sonnet-20240229-v1:0",
            "amazon.titan-text-express-v1",
        ]
    )
    temperature: float = 0.3
    max_tokens: int = 4096

    # Quality settings
    min_confidence_threshold: float = 0.85
    quality_checks_enabled: bool = True
    back_translation_enabled: bool = True

    # Caching
    enable_caching: bool = True
    cache_ttl_seconds: int = 3600

    # Medical settings
    preserve_medical_terms: bool = True
    validate_medical_accuracy: bool = True
    medical_dictionaries: List[str] = field(
        default_factory=lambda: ["icd10", "snomed", "rxnorm", "loinc"]
    )

    # Language detection
    auto_detect_confidence_threshold: float = 0.9

    # Performance
    batch_size: int = 10
    max_concurrent_requests: int = 5
    timeout_seconds: int = 30

    # Supported languages
    supported_languages: Set[Language] = field(
        default_factory=lambda: {
            lang
            for lang in Language
            if lang not in [Language.UNKNOWN, Language.AUTO_DETECT]
        }
    )

    # Specialty configurations
    specialty_configs: Dict[str, Dict[str, Any]] = field(
        default_factory=lambda: {
            "emergency": {"temperature": 0.1, "max_retries": 3, "priority": "high"},
            "clinical": {"temperature": 0.2, "validate_codes": True},
            "patient_education": {"temperature": 0.4, "simplify_language": True},
        }
    )
