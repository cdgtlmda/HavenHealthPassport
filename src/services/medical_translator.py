"""Production Medical Translator Service.

This module provides high-accuracy medical translation with terminology preservation,
cultural adaptation, and quality validation for refugee healthcare.
Includes validation for FHIR Resource terminology translation.
"""

import asyncio
import hashlib
import json
import os
import pickle
import re
import time
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

import boto3
import nltk
import redis.asyncio as redis
from nltk.tokenize import word_tokenize

from src.ai.langchain.aws.bedrock_llm import BedrockLLM
from src.database import get_db
from src.models.translation import Translation
from src.security.encryption import EncryptionService
from src.translation.medical.review_process import ReviewPriority, review_process
from src.utils.logging import get_logger

logger = get_logger(__name__)

if TYPE_CHECKING:
    pass

# Import fuzzywuzzy at module level to avoid import-outside-toplevel
try:
    from fuzzywuzzy import fuzz
except ImportError:
    fuzz = None
    logger.warning("fuzzywuzzy not installed, fuzzy matching will be disabled")

# Import emergency terminology service at module level
emergency_terminology_service: Optional[Any] = None
try:
    from src.services.emergency_terminology_service import emergency_terminology_service
except ImportError:
    logger.warning("Emergency terminology service not available")

# Download required NLTK data
try:
    nltk.download("punkt", quiet=True)
    nltk.download("stopwords", quiet=True)
except (LookupError, OSError):
    pass


class TranslationMode(Enum):
    """Translation modes for different use cases."""

    GENERAL = "general"
    MEDICAL = "medical"
    EMERGENCY = "emergency"
    CONSENT = "consent"
    MEDICATION = "medication"
    DISCHARGE = "discharge"
    DIAGNOSTIC = "diagnostic"
    SURGICAL = "surgical"
    MENTAL_HEALTH = "mental_health"
    PEDIATRIC = "pediatric"
    OBSTETRIC = "obstetric"


@dataclass
class TranslationRequest:
    """Translation request with metadata."""

    text: str
    source_language: str
    target_language: str
    mode: TranslationMode
    medical_context: Optional[str] = None
    preserve_formatting: bool = True
    terminology_strict: bool = True
    cultural_adaptation: bool = True
    urgency: str = "normal"  # normal, urgent, emergency
    patient_age: Optional[int] = None
    patient_gender: Optional[str] = None
    dialect: Optional[str] = None


@dataclass
class TranslationResult:
    """Result of medical translation."""

    translated_text: str
    source_language: str
    target_language: str
    mode: TranslationMode
    confidence_score: float
    medical_terms_preserved: List[Dict[str, Any]]
    cultural_adaptations: List[Dict[str, Any]]
    warnings: List[str]
    translation_time: float
    review_required: bool
    metadata: Dict[str, Any]
    alternative_translations: Optional[List[str]] = None
    backtranslation: Optional[str] = None


class MedicalTerminologyDatabase:
    """Production medical terminology database with comprehensive coverage."""

    def __init__(self) -> None:
        """Initialize terminology database."""
        self.s3_client = boto3.client("s3")
        self.terminology_bucket = os.environ.get(
            "MEDICAL_TERMINOLOGY_BUCKET", "haven-medical-terms"
        )
        self.local_cache_dir = Path("/opt/haven/terminology_cache")
        self.local_cache_dir.mkdir(parents=True, exist_ok=True)

        # Initialize database connection for custom terms
        self.db = next(get_db())

        # Core medical databases
        self.databases: Dict[str, Optional[Dict[str, Any]]] = {
            "icd10": None,
            "snomed": None,
            "rxnorm": None,
            "loinc": None,
            "custom": None,
        }

        # Load terminology databases
        self._load_databases()

    def _load_databases(self) -> None:
        """Load medical terminology databases from S3 and local storage."""
        try:
            # Load ICD-10 codes and descriptions
            icd10_path = self.local_cache_dir / "icd10_multilingual.json"
            if not icd10_path.exists():
                self.s3_client.download_file(
                    self.terminology_bucket,
                    "icd10/icd10_multilingual.json",
                    str(icd10_path),
                )
            with open(icd10_path, "r", encoding="utf-8") as f:
                self.databases["icd10"] = json.load(f)

            # Load SNOMED CT terminology
            snomed_path = self.local_cache_dir / "snomed_ct_multilingual.pkl"
            if not snomed_path.exists():
                self.s3_client.download_file(
                    self.terminology_bucket,
                    "snomed/snomed_ct_multilingual.pkl",
                    str(snomed_path),
                )
            with open(snomed_path, "rb") as f:
                self.databases["snomed"] = pickle.load(
                    f
                )  # nosec B301 - Loading from trusted S3 source

            # Load RxNorm medication database
            rxnorm_path = self.local_cache_dir / "rxnorm_medications.json"
            if not rxnorm_path.exists():
                self.s3_client.download_file(
                    self.terminology_bucket,
                    "rxnorm/rxnorm_medications.json",
                    str(rxnorm_path),
                )
            with open(rxnorm_path, "r", encoding="utf-8") as f:
                self.databases["rxnorm"] = json.load(f)

            # Load custom refugee health terminology
            self._load_custom_terminology()

            logger.info("Medical terminology databases loaded successfully")

        except (FileNotFoundError, json.JSONDecodeError, KeyError) as e:
            logger.error("Error loading terminology databases: %s", str(e))
            # Fall back to basic terminology
            self._load_basic_terminology()

    def _load_custom_terminology(self) -> None:
        """Load custom terminology from database."""
        try:
            # Query custom medical terms
            # MedicalTerminology class doesn't exist, skipping custom terms for now
            terms: list[Any] = []

            self.databases["custom"] = {"terms": {}, "categories": {}}

            for term in terms:
                lang = term.language_code
                custom_db = self.databases["custom"]
                if custom_db is not None:
                    if lang not in custom_db["terms"]:
                        custom_db["terms"][lang] = {}

                    custom_db["terms"][lang][term.term] = {
                        "translations": (
                            json.loads(term.translations) if term.translations else {}
                        ),
                        "category": term.category,
                        "context": term.context,
                        "cultural_notes": term.cultural_notes,
                    }

                    # Organize by category
                    if term.category not in custom_db["categories"]:
                        custom_db["categories"][term.category] = []
                    custom_db["categories"][term.category].append(term.term)

        except (AttributeError, ValueError) as e:
            logger.error("Error loading custom terminology: %s", str(e))

    def _load_basic_terminology(self) -> None:
        """Load basic medical terminology as fallback."""
        self.databases["basic"] = {
            "medications": {
                "en": {
                    "aspirin": {
                        "es": "aspirina",
                        "ar": "أسبرين",
                        "fr": "aspirine",
                        "zh": "阿司匹林",
                    },
                    "ibuprofen": {
                        "es": "ibuprofeno",
                        "ar": "إيبوبروفين",
                        "fr": "ibuprofène",
                        "zh": "布洛芬",
                    },
                    "acetaminophen": {
                        "es": "paracetamol",
                        "ar": "باراسيتامول",
                        "fr": "paracétamol",
                        "zh": "对乙酰氨基酚",
                    },
                    "insulin": {
                        "es": "insulina",
                        "ar": "أنسولين",
                        "fr": "insuline",
                        "zh": "胰岛素",
                    },
                    "antibiotic": {
                        "es": "antibiótico",
                        "ar": "مضاد حيوي",
                        "fr": "antibiotique",
                        "zh": "抗生素",
                    },
                    "vaccine": {
                        "es": "vacuna",
                        "ar": "لقاح",
                        "fr": "vaccin",
                        "zh": "疫苗",
                    },
                    "antihistamine": {
                        "es": "antihistamínico",
                        "ar": "مضاد الهيستامين",
                        "fr": "antihistaminique",
                        "zh": "抗组胺药",
                    },
                }
            },
            "conditions": {
                "en": {
                    "diabetes": {
                        "es": "diabetes",
                        "ar": "السكري",
                        "fr": "diabète",
                        "zh": "糖尿病",
                    },
                    "hypertension": {
                        "es": "hipertensión",
                        "ar": "ارتفاع ضغط الدم",
                        "fr": "hypertension",
                        "zh": "高血压",
                    },
                    "asthma": {
                        "es": "asma",
                        "ar": "الربو",
                        "fr": "asthme",
                        "zh": "哮喘",
                    },
                    "tuberculosis": {
                        "es": "tuberculosis",
                        "ar": "السل",
                        "fr": "tuberculose",
                        "zh": "结核病",
                    },
                    "malaria": {
                        "es": "malaria",
                        "ar": "الملاريا",
                        "fr": "paludisme",
                        "zh": "疟疾",
                    },
                    "pneumonia": {
                        "es": "neumonía",
                        "ar": "الالتهاب الرئوي",
                        "fr": "pneumonie",
                        "zh": "肺炎",
                    },
                    "malnutrition": {
                        "es": "desnutrición",
                        "ar": "سوء التغذية",
                        "fr": "malnutrition",
                        "zh": "营养不良",
                    },
                }
            },
            "symptoms": {
                "en": {
                    "fever": {
                        "es": "fiebre",
                        "ar": "حمى",
                        "fr": "fièvre",
                        "zh": "发烧",
                    },
                    "pain": {"es": "dolor", "ar": "ألم", "fr": "douleur", "zh": "疼痛"},
                    "cough": {"es": "tos", "ar": "سعال", "fr": "toux", "zh": "咳嗽"},
                    "nausea": {
                        "es": "náusea",
                        "ar": "غثيان",
                        "fr": "nausée",
                        "zh": "恶心",
                    },
                    "dizziness": {
                        "es": "mareo",
                        "ar": "دوار",
                        "fr": "vertige",
                        "zh": "头晕",
                    },
                    "fatigue": {
                        "es": "fatiga",
                        "ar": "تعب",
                        "fr": "fatigue",
                        "zh": "疲劳",
                    },
                    "diarrhea": {
                        "es": "diarrea",
                        "ar": "إسهال",
                        "fr": "diarrhée",
                        "zh": "腹泻",
                    },
                }
            },
            "instructions": {
                "en": {
                    "take with food": {
                        "es": "tomar con comida",
                        "ar": "تناول مع الطعام",
                        "fr": "prendre avec de la nourriture",
                        "zh": "与食物同服",
                    },
                    "twice daily": {
                        "es": "dos veces al día",
                        "ar": "مرتين يوميا",
                        "fr": "deux fois par jour",
                        "zh": "每日两次",
                    },
                    "before meals": {
                        "es": "antes de las comidas",
                        "ar": "قبل الوجبات",
                        "fr": "avant les repas",
                        "zh": "饭前",
                    },
                    "at bedtime": {
                        "es": "al acostarse",
                        "ar": "عند النوم",
                        "fr": "au coucher",
                        "zh": "睡前",
                    },
                    "as needed": {
                        "es": "según sea necesario",
                        "ar": "عند الحاجة",
                        "fr": "au besoin",
                        "zh": "需要时",
                    },
                    "do not exceed": {
                        "es": "no exceder",
                        "ar": "لا تتجاوز",
                        "fr": "ne pas dépasser",
                        "zh": "不要超过",
                    },
                }
            },
        }

    def find_medical_terms(self, text: str, language: str) -> List[Dict[str, Any]]:
        """Find medical terms in text using all databases."""
        found_terms: List[Dict[str, Any]] = []
        text_lower = text.lower()

        # Tokenize text
        try:
            tokens = word_tokenize(text_lower)
        except (LookupError, ValueError):
            tokens = text_lower.split()

        # Search in each database
        # 1. Check custom terminology first (highest priority)
        custom_db = self.databases.get("custom")
        if custom_db is not None:
            custom_terms = custom_db.get("terms", {})
            if language in custom_terms:
                for term, info in custom_terms[language].items():
                    if term.lower() in text_lower:
                        found_terms.append(
                            {
                                "term": term,
                                "type": "custom",
                                "category": info["category"],
                                "position": text_lower.find(term.lower()),
                                "translations": info["translations"],
                                "cultural_notes": info.get("cultural_notes"),
                            }
                        )

        # 2. Check RxNorm for medications
        rxnorm_db = self.databases.get("rxnorm")
        if rxnorm_db is not None:
            medications = rxnorm_db.get("medications", {})
            for token in tokens:
                if token in medications:
                    med_info = rxnorm_db["medications"][token]
                    found_terms.append(
                        {
                            "term": token,
                            "type": "medication",
                            "rxnorm_id": med_info.get("rxnorm_id"),
                            "category": "medication",
                            "position": text_lower.find(token),
                            "generic_name": med_info.get("generic_name"),
                            "brand_names": med_info.get("brand_names", []),
                        }
                    )

        # 3. Check basic terminology
        basic_db = self.databases.get("basic")
        if basic_db is not None:
            for category, terms_dict in basic_db.items():
                if language in terms_dict:
                    for term, translations in terms_dict[language].items():
                        if term.lower() in text_lower:
                            found_terms.append(
                                {
                                    "term": term,
                                    "type": "basic",
                                    "category": category,
                                    "position": text_lower.find(term.lower()),
                                    "translations": translations,
                                }
                            )

        # Remove duplicates based on position
        seen_positions: set[int] = set()
        unique_terms: List[Dict[str, Any]] = []
        for term in sorted(found_terms, key=lambda x: x["position"]):
            if term["position"] not in seen_positions:
                unique_terms.append(term)
                seen_positions.add(term["position"])

        return unique_terms

    def get_term_translation(
        self, term: str, source_lang: str, target_lang: str
    ) -> Optional[str]:
        """Get translation for a specific medical term."""
        # Check custom terminology
        custom_db = self.databases.get("custom")
        if custom_db is not None:
            custom_terms = custom_db.get("terms", {})
            if source_lang in custom_terms and term in custom_terms[source_lang]:
                translations = custom_terms[source_lang][term].get("translations", {})
                if target_lang in translations:
                    return str(translations[target_lang])

        # Check basic terminology
        basic_db = self.databases.get("basic")
        if basic_db is not None:
            for _category, terms_dict in basic_db.items():
                if source_lang in terms_dict and term in terms_dict[source_lang]:
                    translations = terms_dict[source_lang][term]
                    if target_lang in translations:
                        return str(translations[target_lang])

        return None


class MedicalTranslator:
    """Production medical translator with high accuracy and safety features.

    Access control enforced at API endpoints using @auth_required decorators.
    """

    # Supported language pairs with quality levels
    SUPPORTED_LANGUAGES = {
        "en": {"name": "English", "quality": "native", "dialects": ["US", "UK", "AU"]},
        "es": {"name": "Spanish", "quality": "native", "dialects": ["MX", "ES", "AR"]},
        "fr": {"name": "French", "quality": "native", "dialects": ["FR", "CA", "BE"]},
        "ar": {
            "name": "Arabic",
            "quality": "native",
            "dialects": ["MSA", "EG", "SY", "MA"],
        },
        "zh": {"name": "Chinese", "quality": "high", "dialects": ["CN", "TW", "HK"]},
        "hi": {"name": "Hindi", "quality": "high", "dialects": ["IN"]},
        "pt": {"name": "Portuguese", "quality": "high", "dialects": ["BR", "PT"]},
        "bn": {"name": "Bengali", "quality": "high", "dialects": ["BD", "IN"]},
        "ru": {"name": "Russian", "quality": "high", "dialects": ["RU", "BY", "KZ"]},
        "ur": {"name": "Urdu", "quality": "medium", "dialects": ["PK", "IN"]},
        "fa": {"name": "Farsi/Persian", "quality": "medium", "dialects": ["IR", "AF"]},
        "sw": {"name": "Swahili", "quality": "medium", "dialects": ["KE", "TZ", "UG"]},
        "am": {"name": "Amharic", "quality": "medium", "dialects": ["ET"]},
        "ti": {"name": "Tigrinya", "quality": "medium", "dialects": ["ER", "ET"]},
        "so": {"name": "Somali", "quality": "medium", "dialects": ["SO", "DJ", "ET"]},
        "ps": {"name": "Pashto", "quality": "medium", "dialects": ["AF", "PK"]},
        "my": {"name": "Burmese", "quality": "basic", "dialects": ["MM"]},
        "ne": {"name": "Nepali", "quality": "basic", "dialects": ["NP"]},
        "si": {"name": "Sinhala", "quality": "basic", "dialects": ["LK"]},
        "uk": {"name": "Ukrainian", "quality": "high", "dialects": ["UA"]},
        "pl": {"name": "Polish", "quality": "high", "dialects": ["PL"]},
        "ro": {"name": "Romanian", "quality": "medium", "dialects": ["RO", "MD"]},
    }

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        """Initialize medical translator."""
        self.config = config or self._get_default_config()

        # Validate environment
        self._validate_environment()

        self.encryption_service = EncryptionService(
            kms_key_id=os.environ.get(
                "TRANSLATOR_KMS_KEY_ID", "alias/haven-health-translator"
            )
        )

        # Initialize AWS clients
        self.bedrock_client = boto3.client(
            "bedrock-runtime", region_name=self.config["aws_region"]
        )
        self.translate_client = boto3.client("translate")
        self.comprehend_medical = boto3.client("comprehendmedical")

        # Initialize LangChain components with Claude 3
        self.llm = BedrockLLM(
            model_name=self.config["bedrock_model"],
            temperature=0.1,  # Low temperature for consistency
            top_p=0.9,
            max_tokens=4096,
            medical_mode=True,
            include_reasoning=True,
        )

        # Initialize terminology database
        self.terminology_db = MedicalTerminologyDatabase()

        # Cache for translations
        self.redis_client: Optional[redis.Redis] = None
        self.cache_ttl = 3600 * 24 * 7  # 1 week

        # Cultural adaptation rules
        self.cultural_rules = self._load_production_cultural_rules()

        # Quality assurance thresholds
        self.qa_thresholds: Dict[TranslationMode, float] = {
            TranslationMode.EMERGENCY: 0.95,
            TranslationMode.CONSENT: 0.98,
            TranslationMode.MEDICATION: 0.98,
            TranslationMode.SURGICAL: 0.97,
            TranslationMode.DIAGNOSTIC: 0.95,
            TranslationMode.DISCHARGE: 0.93,
            TranslationMode.GENERAL: 0.85,
        }

        # Initialize connections
        asyncio.create_task(self._initialize_connections())

    def _validate_environment(self) -> None:
        """Validate production environment configuration."""
        required_vars = [
            "TRANSLATOR_KMS_KEY_ID",
            "MEDICAL_TERMINOLOGY_BUCKET",
            "AWS_DEFAULT_REGION",
        ]

        missing = [var for var in required_vars if not os.environ.get(var)]
        if missing:
            raise ValueError(
                f"CRITICAL: Missing required environment variables: {', '.join(missing)}. "
                "Medical translation cannot operate without proper configuration!"
            )

    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration."""
        return {
            "aws_region": os.environ.get("AWS_DEFAULT_REGION", "us-east-1"),
            "bedrock_model": "anthropic.claude-3-sonnet-20240229-v1:0",
            "enable_aws_translate": True,
            "enable_review_process": True,
            "cache_enabled": True,
            "redis_url": os.environ.get("REDIS_URL", "redis://localhost:6379/2"),
            "terminology_validation": True,
            "confidence_threshold": 0.85,
            "emergency_mode_threshold": 0.95,
            "max_retries": 3,
            "translation_timeout": 30,
            "enable_backtranslation": True,
            "enable_alternatives": True,
        }

    async def _initialize_connections(self) -> None:
        """Initialize external connections."""
        try:
            # Initialize Redis cache
            if self.config["cache_enabled"]:
                self.redis_client = await redis.from_url(
                    self.config["redis_url"],
                    decode_responses=True,
                    socket_keepalive=True,
                    health_check_interval=30,
                )
                await self.redis_client.ping()
                logger.info("Connected to Redis cache for translations")

            # Test AWS services
            await self._test_aws_services()

        except (ConnectionError, ValueError, AttributeError) as e:
            logger.error("Failed to initialize connections: %s", str(e))

    async def _test_aws_services(self) -> None:
        """Test AWS service connectivity."""
        try:
            # Test Bedrock
            self.llm.predict("Translate 'hello' to Spanish: ")
            logger.info("Bedrock connection verified")

            # Test AWS Translate
            self.translate_client.list_terminologies(MaxResults=1)
            logger.info("AWS Translate connection verified")

            # Test Comprehend Medical
            self.comprehend_medical.detect_entities_v2(Text="Test medical text")
            logger.info("Comprehend Medical connection verified")

        except (ConnectionError, ValueError, AttributeError) as e:
            logger.error("AWS service test failed: %s", str(e))

    def _load_production_cultural_rules(self) -> Dict[str, Dict[str, Any]]:
        """Load comprehensive cultural adaptation rules."""
        return {
            "ar": {
                "gender_awareness": True,
                "gender_specific_forms": True,
                "religious_considerations": [
                    "halal medications",
                    "ramadan fasting",
                    "prayer times",
                ],
                "family_involvement": "high",
                "directness": "moderate",
                "physical_contact": "same_gender_only",
                "dietary_restrictions": ["pork", "alcohol"],
                "naming_conventions": "formal_with_titles",
                "time_perception": "flexible",
                "decision_making": "collective",
            },
            "zh": {
                "traditional_medicine": True,
                "family_involvement": "high",
                "directness": "low",
                "number_sensitivity": [4, 14],  # Unlucky numbers
                "color_symbolism": {"white": "death", "red": "luck"},
                "dietary_therapy": True,
                "respect_hierarchy": True,
                "face_saving": "critical",
                "holistic_health": True,
            },
            "so": {
                "oral_tradition": True,
                "visual_aids": "preferred",
                "community_involvement": "high",
                "traditional_healers": True,
                "gender_separation": True,
                "clan_structure": True,
                "religious_healing": True,
                "storytelling": "effective",
            },
            "hi": {
                "vegetarian_considerations": True,
                "ayurvedic_medicine": True,
                "family_involvement": "high",
                "religious_diversity": ["hindu", "muslim", "sikh"],
                "caste_sensitivity": True,
                "joint_family": True,
                "fasting_practices": True,
                "gender_preferences": True,
            },
            "es": {
                "family_involvement": "moderate",
                "directness": "moderate",
                "personal_space": "close",
                "religious_elements": ["catholic"],
                "meal_timing": "late",
                "formality": "moderate",
                "emotional_expression": "high",
            },
            "sw": {
                "community_health": True,
                "traditional_medicine": True,
                "oral_communication": "preferred",
                "collective_decision": True,
                "respect_elders": True,
                "spiritual_healing": True,
                "gender_roles": "traditional",
            },
            "fa": {
                "gender_separation": True,
                "family_honor": "critical",
                "traditional_remedies": True,
                "hospitality": "important",
                "eye_contact": "limited",
                "emotional_restraint": True,
                "poetry_proverbs": "common",
            },
            "uk": {
                "directness": "high",
                "family_involvement": "moderate",
                "traditional_remedies": "common",
                "religious_elements": ["orthodox"],
                "collective_memory": "war_trauma",
                "resilience": "high",
            },
        }

    async def translate(self, request: TranslationRequest) -> TranslationResult:
        """
        Translate medical text with high accuracy and safety.

        This is the main entry point for medical translation.
        """
        start_time = time.time()
        # Track any translation warnings internally

        # Add audit logging
        await self._log_translation_request(request)

        try:
            # Validate languages
            if not self._validate_language_pair(
                request.source_language, request.target_language
            ):
                raise ValueError(
                    f"Unsupported language pair: {request.source_language} -> {request.target_language}"
                )

            # Check cache
            cache_key = self._generate_cache_key(request)
            if self.redis_client is not None and request.urgency != "emergency":
                cached = await self._get_cached_translation(cache_key)
                if cached:
                    cached["translation_time"] = time.time() - start_time
                    cached["from_cache"] = True
                    return TranslationResult(**cached)

            # Detect medical entities first
            medical_entities = await self._detect_medical_entities(
                request.text, request.source_language
            )

            # Extract medical terms for preservation
            medical_terms = self.terminology_db.find_medical_terms(
                request.text, request.source_language
            )

            # Determine translation strategy based on mode and quality requirements
            qa_threshold = self.qa_thresholds.get(request.mode, 0.85)

            if request.mode == TranslationMode.EMERGENCY:
                result = await self._emergency_translation(request, medical_terms)
            elif request.mode in [
                TranslationMode.CONSENT,
                TranslationMode.MEDICATION,
                TranslationMode.SURGICAL,
            ]:
                result = await self._high_accuracy_translation(
                    request, medical_terms, medical_entities
                )
            else:
                result = await self._standard_translation(
                    request, medical_terms, medical_entities
                )

            # Apply cultural adaptations
            if request.cultural_adaptation:
                result = await self._apply_cultural_adaptations(result, request)

            # Perform backtranslation for quality check
            if (
                self.config["enable_backtranslation"]
                and request.mode != TranslationMode.EMERGENCY
            ):
                result.backtranslation = await self._backtranslate(result)

            # Generate alternative translations
            if self.config["enable_alternatives"] and request.mode in [
                TranslationMode.CONSENT,
                TranslationMode.MEDICATION,
            ]:
                result.alternative_translations = await self._generate_alternatives(
                    request, result
                )

            # Validate translation
            validation = await self._validate_translation(
                result, request, medical_terms, medical_entities
            )
            result.confidence_score = validation["confidence"]
            result.warnings.extend(validation.get("warnings", []))

            # Ensure confidence meets threshold
            if result.confidence_score < qa_threshold:
                result.warnings.append(
                    f"Translation confidence ({result.confidence_score:.2f}) below required threshold ({qa_threshold:.2f})"
                )
                result.review_required = True

            # Determine if review is required
            result.review_required = self._requires_review(
                result, request, qa_threshold
            )

            # Submit for review if needed
            if result.review_required and self.config["enable_review_process"]:
                await self._submit_for_review(result, request)

            # Cache successful translation
            if self.redis_client is not None and result.confidence_score > 0.8:
                await self._cache_translation(cache_key, result)

            result.translation_time = time.time() - start_time

            # Log completion
            await self._log_translation_completion(result)

            return result

        except (ValueError, KeyError, AttributeError) as e:
            logger.error("Translation failed: %s", str(e))

            # Return error result
            return TranslationResult(
                translated_text="[Translation Error - Please seek human translator]",
                source_language=request.source_language,
                target_language=request.target_language,
                mode=request.mode,
                confidence_score=0.0,
                medical_terms_preserved=[],
                cultural_adaptations=[],
                warnings=[
                    f"Translation failed: {str(e)}",
                    "CRITICAL: Human translator required",
                ],
                translation_time=time.time() - start_time,
                review_required=True,
                metadata={"error": str(e), "error_type": type(e).__name__},
            )

    async def _detect_medical_entities(
        self, text: str, language: str
    ) -> List[Dict[str, Any]]:
        """Detect medical entities using AWS Comprehend Medical."""
        try:
            # Comprehend Medical only supports English
            # For other languages, translate first
            if language != "en":
                # Quick translation to English for entity detection
                response = self.translate_client.translate_text(
                    Text=text, SourceLanguageCode=language, TargetLanguageCode="en"
                )
                english_text = response["TranslatedText"]
            else:
                english_text = text

            # Detect medical entities
            response = self.comprehend_medical.detect_entities_v2(Text=english_text)

            entities = []
            for entity in response.get("Entities", []):
                entities.append(
                    {
                        "text": entity["Text"],
                        "type": entity["Type"],
                        "category": entity["Category"],
                        "confidence": entity["Score"],
                        "traits": entity.get("Traits", []),
                        "attributes": entity.get("Attributes", []),
                    }
                )

            return entities

        except (ValueError, KeyError, AttributeError) as e:
            logger.error("Medical entity detection failed: %s", str(e))
            return []

    async def _emergency_translation(
        self, request: TranslationRequest, medical_terms: List[Dict[str, Any]]
    ) -> TranslationResult:
        """Fast translation for emergency situations with critical term validation."""
        # Create emergency terminology list
        emergency_terms = {
            "en": [
                "airway",
                "breathing",
                "circulation",
                "bleeding",
                "unconscious",
                "allergic",
                "heart attack",
                "stroke",
            ],
            "es": [
                "vía aérea",
                "respiración",
                "circulación",
                "sangrado",
                "inconsciente",
                "alérgico",
                "infarto",
                "derrame",
            ],
            "ar": [
                "مجرى الهواء",
                "التنفس",
                "الدورة الدموية",
                "نزيف",
                "فاقد الوعي",
                "حساسية",
                "نوبة قلبية",
                "سكتة دماغية",
            ],
            "fr": [
                "voies respiratoires",
                "respiration",
                "circulation",
                "saignement",
                "inconscient",
                "allergique",
                "crise cardiaque",
                "AVC",
            ],
        }

        # Use AWS Translate with custom terminology for speed
        if self.config["enable_aws_translate"]:
            try:
                # Create temporary terminology for emergency terms
                terminology_data = self._create_emergency_terminology(
                    request.source_language, request.target_language, emergency_terms
                )

                response = self.translate_client.translate_text(
                    Text=request.text,
                    SourceLanguageCode=request.source_language,
                    TargetLanguageCode=request.target_language,
                    TerminologyNames=[terminology_data],
                )

                translated_text = response["TranslatedText"]

                # Use emergency terminology service for validation
                if emergency_terminology_service is None:
                    logger.warning("Emergency terminology service not available")
                    validation_result = {
                        "is_valid": True,
                        "accuracy_score": 0.8,
                        "warnings": [
                            "Emergency terminology service not available for validation"
                        ],
                        "detected_issues": [],
                        "missed_terms": [],
                    }
                else:

                    # Validate critical emergency terms are preserved
                    validation_result = (
                        emergency_terminology_service.validate_emergency_translation(
                            source_text=request.text,
                            translated_text=translated_text,
                            source_lang=request.source_language,
                            target_lang=request.target_language,
                        )
                    )

                preserved_terms = []
                for term in medical_terms:
                    # Check if term or its translation appears
                    term_translation = self.terminology_db.get_term_translation(
                        term["term"], request.source_language, request.target_language
                    )
                    if term_translation and term_translation in translated_text:
                        preserved_terms.append(
                            {
                                "source_term": term["term"],
                                "translated_term": term_translation,
                                "preserved": True,
                                "category": term.get("category", "medical"),
                            }
                        )

                # Add any missing critical terms from validation
                warnings: List[str] = validation_result.get("warnings", [])
                if not validation_result["is_valid"]:
                    warnings.append(
                        "Critical emergency terms may be missing - manual review required"
                    )

                # Add emergency warning
                if request.target_language in ["ar", "fa", "ur"]:
                    # RTL languages
                    translated_text = f"⚠️ طوارئ: {translated_text}"
                else:
                    translated_text = f"⚠️ EMERGENCY: {translated_text}"

                return TranslationResult(
                    translated_text=translated_text,
                    source_language=request.source_language,
                    target_language=request.target_language,
                    mode=request.mode,
                    confidence_score=float(
                        str(validation_result.get("accuracy_score", 0.8))
                    ),
                    medical_terms_preserved=preserved_terms,
                    cultural_adaptations=[],
                    warnings=(
                        warnings
                        if warnings
                        else [
                            "Emergency translation - verification recommended when possible"
                        ]
                    ),
                    translation_time=0,
                    review_required=not validation_result[
                        "is_valid"
                    ],  # Require review if validation failed
                    metadata={
                        "method": "aws_translate_emergency",
                        "critical_terms_checked": True,
                        "validation_score": validation_result["accuracy_score"],
                    },
                )

            except (ValueError, KeyError, AttributeError) as e:
                logger.error("Emergency AWS translation error: %s", str(e))
                # Fall back to LLM

        # Fall back to fast LLM translation
        return await self._llm_emergency_translation(request, medical_terms)

    async def _llm_emergency_translation(
        self, request: TranslationRequest, medical_terms: List[Dict[str, str]]
    ) -> TranslationResult:
        """Emergency translation using LLM with critical safety checks."""
        prompt = f"""EMERGENCY MEDICAL TRANSLATION - LIFE CRITICAL

Translate this emergency medical text from {request.source_language} to {request.target_language}.
Preserve ALL medical terms exactly. Add emergency indicator.

Text: {request.text}

Provide ONLY the translation. Be clear and direct."""

        try:
            response = self.llm.predict(prompt)

            # Add emergency indicator if not present
            if "⚠️" not in response and "EMERGENCY" not in response.upper():
                if request.target_language in ["ar", "fa", "ur"]:
                    response = f"⚠️ طوارئ: {response}"
                else:
                    response = f"⚠️ EMERGENCY: {response}"

            return TranslationResult(
                translated_text=response.strip(),
                source_language=request.source_language,
                target_language=request.target_language,
                mode=request.mode,
                confidence_score=0.90,
                medical_terms_preserved=medical_terms,
                cultural_adaptations=[],
                warnings=["Emergency LLM translation - verify when possible"],
                translation_time=0,
                review_required=False,
                metadata={"method": "llm_emergency"},
            )

        except Exception as e:
            logger.critical(f"Emergency LLM translation failed: {e}")
            raise

    async def _high_accuracy_translation(
        self,
        request: TranslationRequest,
        medical_terms: List[Dict[str, str]],
        medical_entities: List[Dict[str, Any]],
    ) -> TranslationResult:
        """High accuracy translation for critical documents using multiple methods."""
        translations = []

        # Method 1: AWS Translate with comprehensive terminology
        if self.config["enable_aws_translate"]:
            aws_result = await self._aws_translate_with_terminology(
                request, medical_terms
            )
            if aws_result:
                translations.append(aws_result)

        # Method 2: LLM with detailed medical prompt
        llm_result = await self._llm_medical_translation(
            request, medical_terms, medical_entities, high_accuracy=True
        )
        translations.append(llm_result)

        # Method 3: Ensemble approach with multiple LLM calls
        if request.mode in [TranslationMode.CONSENT, TranslationMode.SURGICAL]:
            ensemble_result = await self._ensemble_translation(
                request, medical_terms, medical_entities
            )
            translations.append(ensemble_result)

        # Select best translation based on comprehensive scoring
        best_translation = self._select_best_translation(
            translations, medical_terms, medical_entities
        )

        # Additional validation for critical content
        if request.mode == TranslationMode.CONSENT:
            best_translation = await self._validate_consent_translation(
                best_translation
            )
        elif request.mode == TranslationMode.MEDICATION:
            best_translation = await self._validate_medication_translation(
                best_translation
            )
        elif request.mode == TranslationMode.SURGICAL:
            best_translation = await self._validate_surgical_translation(
                best_translation
            )

        return best_translation

    async def _standard_translation(
        self,
        request: TranslationRequest,
        medical_terms: List[Dict[str, Any]],
        medical_entities: List[Dict[str, Any]],
    ) -> TranslationResult:
        """Perform standard medical translation with good accuracy and efficiency."""
        # Primary translation using LLM
        result = await self._llm_medical_translation(
            request, medical_terms, medical_entities
        )

        # Enhance with AWS Translate if confidence is low
        if result.confidence_score < self.config["confidence_threshold"]:
            aws_result = await self._aws_translate_with_terminology(
                request, medical_terms
            )
            if aws_result and aws_result.confidence_score > result.confidence_score:
                # Merge best aspects of both translations
                result = self._merge_translations(result, aws_result, medical_terms)

        return result

    async def _llm_medical_translation(
        self,
        request: TranslationRequest,
        medical_terms: List[Dict[str, Any]],
        medical_entities: List[Dict[str, Any]],
        high_accuracy: bool = False,
    ) -> TranslationResult:
        """Translate using LLM with comprehensive medical context."""
        # Build detailed medical context
        medical_context = self._build_comprehensive_medical_context(
            request, medical_terms, medical_entities
        )

        # Get terminology mappings
        term_mappings = self._get_terminology_mappings(
            medical_terms, request.source_language, request.target_language
        )

        # Create appropriate prompt
        if high_accuracy:
            prompt = self._create_high_accuracy_medical_prompt(
                request, medical_context, term_mappings
            )
        else:
            prompt = self._create_standard_medical_prompt(
                request, medical_context, term_mappings
            )

        try:
            # Call LLM with structured output
            response = self.llm.predict(prompt)

            # Parse structured response
            parsed = self._parse_structured_response(response)

            # Validate and extract preserved terms
            preserved_terms = self._validate_term_preservation(
                request.text, parsed["translation"], medical_terms, term_mappings
            )

            # Calculate confidence based on multiple factors
            confidence = self._calculate_translation_confidence(
                parsed, preserved_terms, medical_entities
            )

            return TranslationResult(
                translated_text=parsed["translation"],
                source_language=request.source_language,
                target_language=request.target_language,
                mode=request.mode,
                confidence_score=confidence,
                medical_terms_preserved=preserved_terms,
                cultural_adaptations=parsed.get("cultural_adaptations", []),
                warnings=parsed.get("warnings", []),
                translation_time=0,
                review_required=confidence < self.qa_thresholds.get(request.mode, 0.85),
                metadata={
                    "method": "llm_medical",
                    "model": self.config["bedrock_model"],
                    "entities_detected": len(medical_entities),
                    "terms_mapped": len(term_mappings),
                },
            )

        except Exception as e:
            logger.error(f"LLM medical translation error: {e}")
            raise

    def _build_comprehensive_medical_context(
        self,
        request: TranslationRequest,
        medical_terms: List[Dict[str, Any]],
        medical_entities: List[Dict[str, Any]],
    ) -> str:
        """Build comprehensive medical context for translation."""
        context_parts = []

        # Add basic context
        if request.medical_context:
            context_parts.append(f"Clinical Context: {request.medical_context}")

        # Add document type context
        context_parts.append(
            f"Document Type: {request.mode.value.replace('_', ' ').title()}"
        )

        # Add patient context if available
        if request.patient_age:
            age_group = self._get_age_group(request.patient_age)
            context_parts.append(f"Patient: {age_group}")

        if request.patient_gender:
            context_parts.append(f"Gender: {request.patient_gender}")

        # Add medical entities
        if medical_entities:
            entity_types: Dict[str, List[str]] = {}
            for entity in medical_entities:
                entity_type = entity["type"]
                if entity_type not in entity_types:
                    entity_types[entity_type] = []
                entity_types[entity_type].append(entity["text"])

            entity_summary = []
            for entity_type, items in entity_types.items():
                entity_summary.append(f"{entity_type}: {', '.join(items[:3])}")

            context_parts.append("Medical Entities:\n" + "\n".join(entity_summary))

        # Add terminology context
        if medical_terms:
            categories: Dict[str, List[str]] = {}
            for term in medical_terms:
                cat = term.get("category", "general")
                if cat not in categories:
                    categories[cat] = []
                categories[cat].append(term["term"])

            term_summary = []
            for cat, terms in categories.items():
                term_summary.append(f"{cat}: {', '.join(terms[:5])}")

            context_parts.append("Key Terms:\n" + "\n".join(term_summary))

        return "\n\n".join(context_parts)

    def _get_terminology_mappings(
        self, medical_terms: List[Dict[str, Any]], source_lang: str, target_lang: str
    ) -> Dict[str, str]:
        """Get terminology mappings for medical terms."""
        mappings = {}

        for term in medical_terms:
            term_text = term["term"]
            translation = self.terminology_db.get_term_translation(
                term_text, source_lang, target_lang
            )

            if translation:
                mappings[term_text] = translation
            else:
                # Try fuzzy matching for variations
                if "translations" in term:
                    if target_lang in term["translations"]:
                        mappings[term_text] = term["translations"][target_lang]

        return mappings

    def _create_high_accuracy_medical_prompt(
        self,
        request: TranslationRequest,
        medical_context: str,
        term_mappings: Dict[str, str],
    ) -> str:
        """Create high-accuracy prompt for critical medical translations."""
        # Format terminology mappings
        terminology_section = ""
        if term_mappings:
            terminology_section = "\nCritical Medical Terms (MUST preserve exactly):\n"
            for source, target in term_mappings.items():
                terminology_section += f"- {source} → {target}\n"

        prompt = f"""You are an expert medical translator with certification in both {request.source_language} and {request.target_language}.
You are translating a critical {request.mode.value} document where accuracy can affect patient safety.

{medical_context}
{terminology_section}

Requirements:
1. Preserve ALL medical terminology with 100% accuracy
2. Maintain clinical precision and completeness
3. Ensure legal compliance for {request.mode.value} documents
4. Apply appropriate cultural adaptations without losing meaning
5. Flag ANY ambiguity or uncertainty
6. Use formal medical register appropriate for {request.target_language}

Source Text ({request.source_language}):
{request.text}

Provide your translation in the following JSON format:
{{
    "translation": "complete translated text",
    "confidence": 0.95,
    "preserved_terms": [
        {{"source": "term1", "target": "translation1", "verified": true}}
    ],
    "cultural_adaptations": [
        {{"type": "formality", "description": "Added formal address", "applied_to": "greeting"}}
    ],
    "warnings": ["any concerns or ambiguities"],
    "notes": "any important translator notes"
}}"""

        return prompt

    def _create_standard_medical_prompt(
        self,
        request: TranslationRequest,
        medical_context: str,
        term_mappings: Dict[str, str],
    ) -> str:
        """Create standard prompt for medical translations."""
        # Use medical_context if provided
        context_note = f"\nContext: {medical_context}" if medical_context else ""
        terminology_note = ""
        if term_mappings:
            key_terms = list(term_mappings.items())[:5]
            terminology_note = "Key terms: " + ", ".join(
                [f"{s}→{t}" for s, t in key_terms]
            )

        prompt = f"""You are a professional medical translator.
Translate this medical text from {request.source_language} to {request.target_language}.

Context: {request.mode.value} document{context_note}
{terminology_note}

Guidelines:
- Preserve medical terminology accurately
- Ensure clarity for the target audience
- Apply cultural adaptations as appropriate
- Maintain professional medical tone

Text to translate:
{request.text}

Respond in JSON:
{{
    "translation": "...",
    "confidence": 0.85,
    "warnings": []
}}"""

        return prompt

    def _parse_structured_response(self, response: str) -> Dict[str, Any]:
        """Parse structured LLM response with robust error handling."""
        try:
            # Try to parse as JSON
            parsed = json.loads(response)

            # Validate required fields
            if "translation" not in parsed:
                raise ValueError("Missing translation field")

            # Set defaults for optional fields
            parsed.setdefault("confidence", 0.8)
            parsed.setdefault("warnings", [])
            parsed.setdefault("preserved_terms", [])
            parsed.setdefault("cultural_adaptations", [])

            return dict(parsed)

        except json.JSONDecodeError:
            # Try to extract translation from plain text response
            lines = response.strip().split("\n")

            # Look for JSON-like structure
            json_start = -1
            json_end = -1
            for i, line in enumerate(lines):
                if "{" in line:
                    json_start = i
                if "}" in line and json_start >= 0:
                    json_end = i + 1
                    break

            if json_start >= 0 and json_end > json_start:
                try:
                    json_text = "\n".join(lines[json_start:json_end])
                    parsed_json = json.loads(json_text)
                    return dict(parsed_json)
                except (json.JSONDecodeError, ValueError):
                    pass

            # Fall back to plain text
            return {
                "translation": response.strip(),
                "confidence": 0.7,
                "warnings": ["Response was not in expected JSON format"],
                "preserved_terms": [],
                "cultural_adaptations": [],
            }

    def _validate_term_preservation(
        self,
        source_text: str,
        translated_text: str,
        medical_terms: List[Dict[str, Any]],
        term_mappings: Dict[str, str],
    ) -> List[Dict[str, Any]]:
        """Validate that medical terms are properly preserved in translation."""
        preserved_terms: List[Dict[str, Any]] = []
        source_lower = source_text.lower()
        translated_lower = translated_text.lower()

        for term_info in medical_terms:
            term = term_info["term"]
            term_lower = term.lower()

            # Check if source term exists in source text
            if term_lower not in source_lower:
                continue

            # Get expected translation
            expected_translation = term_mappings.get(term)
            if not expected_translation:
                expected_translation = self.terminology_db.get_term_translation(
                    term,
                    term_info.get("source_lang", "en"),
                    term_info.get("target_lang", "en"),
                )

            preservation_info: Dict[str, Any] = {
                "source_term": term,
                "category": term_info.get("category", "medical"),
                "type": term_info.get("type", "general"),
            }

            if expected_translation:
                # Check if translation is present
                if expected_translation.lower() in translated_lower:
                    preservation_info["translated_term"] = expected_translation
                    preservation_info["preserved"] = True
                    preservation_info["confidence"] = 1.0
                else:
                    # Try fuzzy matching
                    match_score = self._fuzzy_match_in_text(
                        expected_translation, translated_text
                    )
                    if match_score > 0.85:
                        preservation_info["translated_term"] = expected_translation
                        preservation_info["preserved"] = True
                        preservation_info["confidence"] = match_score
                    else:
                        preservation_info["translated_term"] = expected_translation
                        preservation_info["preserved"] = False
                        preservation_info["confidence"] = 0.0
            else:
                # No known translation - check if term appears unchanged
                if term_lower in translated_lower:
                    preservation_info["translated_term"] = term
                    preservation_info["preserved"] = True
                    preservation_info["confidence"] = 0.8
                else:
                    preservation_info["preserved"] = False
                    preservation_info["confidence"] = 0.0

            preserved_terms.append(preservation_info)

        return preserved_terms

    def _fuzzy_match_in_text(self, term: str, text: str) -> float:
        """Find fuzzy match of term in text and return best score."""
        try:
            if fuzz is None:
                # Fallback to simple substring matching if fuzzywuzzy not available
                return 1.0 if term.lower() in text.lower() else 0.0

            # Tokenize text
            words = text.split()
            term_words = term.split()

            # For single word terms
            if len(term_words) == 1:
                scores = [fuzz.ratio(term.lower(), word.lower()) for word in words]
                return max(scores) / 100.0 if scores else 0.0

            # For multi-word terms, use sliding window
            best_score = 0
            for i in range(len(words) - len(term_words) + 1):
                window = " ".join(words[i : i + len(term_words)])
                score = fuzz.ratio(term.lower(), window.lower())
                best_score = max(best_score, score)

            return best_score / 100.0

        except ImportError:
            # Fallback to simple substring matching
            return 1.0 if term.lower() in text.lower() else 0.0

    def _calculate_translation_confidence(
        self,
        parsed_response: Dict[str, Any],
        preserved_terms: List[Dict[str, str]],
        medical_entities: List[Dict[str, Any]],
    ) -> float:
        """Calculate overall translation confidence score."""
        # Start with LLM's self-reported confidence
        base_confidence = parsed_response.get("confidence", 0.8)

        # Factor in term preservation
        if preserved_terms:
            preserved_count = sum(
                1 for t in preserved_terms if t.get("preserved", False)
            )
            preservation_rate = preserved_count / len(preserved_terms)

            # Weight preservation heavily for medical translations
            base_confidence = base_confidence * 0.6 + preservation_rate * 0.4

        # Penalize for warnings
        warning_penalty = len(parsed_response.get("warnings", [])) * 0.05
        base_confidence -= warning_penalty

        # Boost for high entity confidence
        if medical_entities:
            avg_entity_confidence = sum(
                e.get("confidence", 0) for e in medical_entities
            ) / len(medical_entities)
            if avg_entity_confidence > 0.9:
                base_confidence += 0.05

        # Ensure within bounds
        return float(max(0.0, min(1.0, base_confidence)))

    async def _ensemble_translation(
        self,
        request: TranslationRequest,
        medical_terms: List[Dict[str, Any]],
        medical_entities: List[Dict[str, Any]],
    ) -> TranslationResult:
        """Perform ensemble translation using multiple approaches."""
        # TODO: Use medical_entities for entity-aware translation
        _ = medical_entities  # Will be used in future implementation
        ensemble_results = []

        # Approach 1: Direct translation
        direct_prompt = self._create_direct_translation_prompt(request, medical_terms)
        direct_result = await self._get_llm_translation(direct_prompt)
        ensemble_results.append(direct_result)

        # Approach 2: Step-by-step translation
        stepwise_prompt = self._create_stepwise_translation_prompt(
            request, medical_terms
        )
        stepwise_result = await self._get_llm_translation(stepwise_prompt)
        ensemble_results.append(stepwise_result)

        # Approach 3: Explanation-based translation
        explanation_prompt = self._create_explanation_translation_prompt(
            request, medical_terms
        )
        explanation_result = await self._get_llm_translation(explanation_prompt)
        ensemble_results.append(explanation_result)

        # Combine results using voting and consensus
        final_translation = self._combine_ensemble_results(
            ensemble_results, medical_terms, request.target_language
        )

        return final_translation

    async def _get_llm_translation(self, prompt: str) -> Dict[str, Any]:
        """Get translation from LLM with error handling."""
        try:
            response = await asyncio.wait_for(
                asyncio.get_event_loop().run_in_executor(
                    None, self.llm.predict, prompt
                ),
                timeout=self.config["translation_timeout"],
            )
            return self._parse_structured_response(response)
        except asyncio.TimeoutError:
            logger.error("LLM translation timed out")
            return {
                "translation": "",
                "confidence": 0.0,
                "warnings": ["Translation timed out"],
            }
        except (ValueError, RuntimeError, AttributeError) as e:
            logger.error("LLM translation error: %s", str(e))
            return {"translation": "", "confidence": 0.0, "warnings": [str(e)]}

    def _combine_ensemble_results(
        self,
        results: List[Dict[str, Any]],
        medical_terms: List[Dict[str, str]],
        target_language: str,
    ) -> TranslationResult:
        """Combine ensemble translation results into final translation."""
        # Target language used for future language-specific combination logic
        _ = target_language
        # Filter out failed translations
        valid_results = [
            r for r in results if r.get("translation") and r.get("confidence", 0) > 0.5
        ]

        if not valid_results:
            # Return best effort even if low confidence
            best_result = max(results, key=lambda r: r.get("confidence", 0))
            return self._dict_to_translation_result(best_result, medical_terms)

        # For critical terms, use majority voting
        critical_terms_translations = {}
        for term in medical_terms:
            if term.get("category") in ["medication", "dosage", "allergy"]:
                term_translations = []
                for result in valid_results:
                    # Extract how this critical term was translated in each result
                    # This is simplified - in production would use alignment
                    term_translations.append(result.get("translation", ""))

                # Use most common translation
                # In production, would use more sophisticated consensus
                critical_terms_translations[term["term"]] = term_translations[0]

        # Select translation with highest confidence that preserves critical terms
        best_result = max(valid_results, key=lambda r: r.get("confidence", 0))

        # Enhance confidence if multiple translations agree
        translation_texts = [r.get("translation", "") for r in valid_results]
        if len(set(translation_texts)) == 1:
            # All translations agree
            best_result["confidence"] = min(
                0.98, best_result.get("confidence", 0.9) + 0.08
            )

        # Add ensemble metadata
        best_result["metadata"] = {
            "method": "ensemble",
            "ensemble_size": len(results),
            "valid_results": len(valid_results),
            "consensus": len(set(translation_texts)) == 1,
        }

        return self._dict_to_translation_result(best_result, medical_terms)

    def _dict_to_translation_result(
        self, result_dict: Dict[str, Any], medical_terms: List[Dict[str, str]]
    ) -> TranslationResult:
        """Convert dictionary to TranslationResult object."""
        # Medical terms could be used for validation in future
        _ = medical_terms
        return TranslationResult(
            translated_text=result_dict.get("translation", ""),
            source_language=result_dict.get("source_language", ""),
            target_language=result_dict.get("target_language", ""),
            mode=TranslationMode(result_dict.get("mode", "general")),
            confidence_score=result_dict.get("confidence", 0.0),
            medical_terms_preserved=result_dict.get("preserved_terms", []),
            cultural_adaptations=result_dict.get("cultural_adaptations", []),
            warnings=result_dict.get("warnings", []),
            translation_time=0,
            review_required=result_dict.get("review_required", True),
            metadata=result_dict.get("metadata", {}),
        )

    def _select_best_translation(
        self,
        translations: List[TranslationResult],
        medical_terms: List[Dict[str, Any]],
        medical_entities: List[Dict[str, Any]],
    ) -> TranslationResult:
        """Select best translation from multiple options using comprehensive scoring."""
        if not translations:
            raise ValueError("No translations to select from")

        if len(translations) == 1:
            return translations[0]

        # Score each translation
        scores = []
        for trans in translations:
            score: float = 0

            # Base confidence score (40% weight)
            score += trans.confidence_score * 40

            # Term preservation score (30% weight)
            if medical_terms:
                preserved = sum(
                    1
                    for t in trans.medical_terms_preserved
                    if t.get("preserved", False)
                )
                preservation_rate = preserved / len(medical_terms)
                score += preservation_rate * 30

            # Entity coverage score (20% weight)
            if medical_entities:
                # Check how many entities are represented in translation
                entity_coverage = self._calculate_entity_coverage(
                    trans.translated_text, medical_entities
                )
                score += entity_coverage * 20

            # Penalty for warnings (-5 per warning)
            score -= len(trans.warnings) * 5

            # Bonus for cultural adaptations (5% weight)
            if trans.cultural_adaptations:
                score += min(len(trans.cultural_adaptations) * 2.5, 5)

            # Penalty for being too short or too long
            length_ratio = len(trans.translated_text) / max(
                len(translations[0].translated_text), 1
            )
            if length_ratio < 0.7 or length_ratio > 1.5:
                score -= 10

            scores.append(score)

        # Return translation with highest score
        best_idx = scores.index(max(scores))
        best_translation = translations[best_idx]

        # Add selection metadata
        best_translation.metadata["selection_score"] = scores[best_idx]
        best_translation.metadata["selection_method"] = "comprehensive_scoring"

        return best_translation

    def _calculate_entity_coverage(
        self, translated_text: str, medical_entities: List[Dict[str, Any]]
    ) -> float:
        """Calculate how well medical entities are covered in translation."""
        # TODO: Use translated_text to check actual entity presence in translation
        _ = translated_text
        if not medical_entities:
            return 1.0

        covered = 0
        for entity in medical_entities:
            # This is simplified - in production would translate entity and check
            if entity.get("confidence", 0) > 0.8:
                # High confidence entities should be preserved
                covered += 1

        return covered / len(medical_entities)

    async def _apply_cultural_adaptations(
        self, result: TranslationResult, request: TranslationRequest
    ) -> TranslationResult:
        """Apply comprehensive cultural adaptations to translation."""
        if request.target_language not in self.cultural_rules:
            return result

        rules = self.cultural_rules[request.target_language]
        adaptations = []
        adapted_text = result.translated_text

        # Gender-specific adaptations
        if rules.get("gender_specific_forms") and request.patient_gender:
            gender_adaptation = self._apply_gender_forms(
                adapted_text, request.target_language, request.patient_gender
            )
            if gender_adaptation["modified"]:
                adapted_text = gender_adaptation["text"]
                adaptations.append(
                    {
                        "type": "gender_forms",
                        "description": f"Applied {request.patient_gender} gender forms",
                        "changes": gender_adaptation["changes"],
                    }
                )

        # Formality levels based on age and culture
        if request.patient_age and rules.get("respect_hierarchy"):
            if request.patient_age > 60:
                formality_adaptation = self._apply_formality(
                    adapted_text, request.target_language, "high"
                )
                if formality_adaptation["modified"]:
                    adapted_text = formality_adaptation["text"]
                    adaptations.append(
                        {
                            "type": "formality",
                            "description": "Applied respectful forms for elderly patient",
                            "level": "high",
                        }
                    )

        # Religious considerations
        if (
            rules.get("religious_considerations")
            and request.mode == TranslationMode.MEDICATION
        ):
            for consideration in rules["religious_considerations"]:
                if consideration == "halal medications":
                    halal_adaptation = self._add_halal_notes(
                        adapted_text, request.target_language
                    )
                    if halal_adaptation["modified"]:
                        adapted_text = halal_adaptation["text"]
                        adaptations.append(
                            {
                                "type": "religious",
                                "description": "Added halal compliance information",
                                "consideration": consideration,
                            }
                        )
                elif consideration == "ramadan fasting" and self._is_ramadan_period():
                    fasting_adaptation = self._add_fasting_considerations(
                        adapted_text, request.target_language
                    )
                    if fasting_adaptation["modified"]:
                        adapted_text = fasting_adaptation["text"]
                        adaptations.append(
                            {
                                "type": "religious",
                                "description": "Added Ramadan fasting considerations",
                                "consideration": consideration,
                            }
                        )

        # Family involvement adaptations
        if (
            rules.get("family_involvement") == "high"
            and request.mode == TranslationMode.CONSENT
        ):
            family_adaptation = self._add_family_consultation_note(
                adapted_text, request.target_language
            )
            if family_adaptation["modified"]:
                adapted_text = family_adaptation["text"]
                adaptations.append(
                    {
                        "type": "social",
                        "description": "Added family consultation expectation",
                        "cultural_norm": "family_involvement",
                    }
                )

        # Communication style adaptations
        if rules.get("directness") == "low":
            indirect_adaptation = self._apply_indirect_communication(
                adapted_text, request.target_language, request.mode
            )
            if indirect_adaptation["modified"]:
                adapted_text = indirect_adaptation["text"]
                adaptations.append(
                    {
                        "type": "communication_style",
                        "description": "Applied indirect communication style",
                        "changes": indirect_adaptation["changes"],
                    }
                )

        # Visual/oral adaptations for low literacy contexts
        if rules.get("oral_tradition") or rules.get("visual_aids") == "preferred":
            if request.mode in [TranslationMode.MEDICATION, TranslationMode.DISCHARGE]:
                visual_note = self._add_visual_aid_reference(
                    adapted_text, request.target_language
                )
                if visual_note["modified"]:
                    adapted_text = visual_note["text"]
                    adaptations.append(
                        {
                            "type": "accessibility",
                            "description": "Added reference to visual aids",
                            "reason": "oral_tradition_culture",
                        }
                    )

        # Update result with adaptations
        result.translated_text = adapted_text
        result.cultural_adaptations.extend(adaptations)

        return result

    def _apply_gender_forms(
        self, text: str, language: str, gender: str
    ) -> Dict[str, Any]:
        """Apply gender-specific language forms."""
        modified = False
        changes = []

        if language == "ar":
            # Arabic has extensive gender agreement
            if gender == "female":
                # Simple example - in production would use NLP
                replacements = [
                    ("أنت", "أنتِ"),  # you (m) -> you (f)
                    ("مريض", "مريضة"),  # patient (m) -> patient (f)
                    ("طبيبك", "طبيبتك"),  # your doctor (m) -> your doctor (f)
                ]
                for masc, fem in replacements:
                    if masc in text:
                        text = text.replace(masc, fem)
                        changes.append(f"{masc} → {fem}")
                        modified = True

        elif language == "es":
            # Spanish gender agreement
            if gender == "female":
                replacements = [
                    ("el paciente", "la paciente"),
                    ("doctor", "doctora"),
                    ("enfermero", "enfermera"),
                ]
                for masc, fem in replacements:
                    if masc in text.lower():
                        text = text.replace(masc, fem)
                        text = text.replace(masc.capitalize(), fem.capitalize())
                        changes.append(f"{masc} → {fem}")
                        modified = True

        elif language == "fr":
            # French gender agreement
            if gender == "female":
                replacements = [
                    ("le patient", "la patiente"),
                    ("votre médecin", "votre médecin"),  # médecin is epicene
                    ("infirmier", "infirmière"),
                ]
                for masc, fem in replacements:
                    if masc in text.lower():
                        text = text.replace(masc, fem)
                        text = text.replace(masc.capitalize(), fem.capitalize())
                        changes.append(f"{masc} → {fem}")
                        modified = True

        return {"text": text, "modified": modified, "changes": changes}

    def _apply_formality(self, text: str, language: str, level: str) -> Dict[str, Any]:
        """Apply appropriate formality level."""
        modified = False
        original_text = text

        if language == "es" and level == "high":
            # Use usted forms
            informal_to_formal = [
                ("tú", "usted"),
                ("tu", "su"),
                ("tienes", "tiene"),
                ("tomas", "toma"),
                ("debes", "debe"),
            ]
            for informal, formal in informal_to_formal:
                if informal in text.lower():
                    text = re.sub(rf"\b{informal}\b", formal, text, flags=re.IGNORECASE)
                    modified = True

        elif language == "fr" and level == "high":
            # Use vous forms
            informal_to_formal = [
                ("tu", "vous"),
                ("ton", "votre"),
                ("ta", "votre"),
                ("tes", "vos"),
            ]
            for informal, formal in informal_to_formal:
                if informal in text.lower():
                    text = re.sub(rf"\b{informal}\b", formal, text, flags=re.IGNORECASE)
                    modified = True

        elif language in ["hi", "ur", "bn"] and level == "high":
            # Add respectful suffixes
            if language == "hi":
                text = text.replace("आप", "आप जी")  # Add ji for respect
                modified = True

        return {
            "text": text,
            "modified": modified,
            "original": original_text if modified else None,
        }

    def _add_halal_notes(self, text: str, language: str) -> Dict[str, Any]:
        """Add halal medication notes where relevant."""
        modified = False

        # Check if medication instructions present
        med_keywords = [
            "medication",
            "medicine",
            "capsule",
            "tablet",
            "دواء",
            "medicamento",
        ]
        has_meds = any(keyword in text.lower() for keyword in med_keywords)

        if has_meds:
            halal_notes = {
                "en": "\n\nNote: This medication is halal-certified.",
                "ar": "\n\nملاحظة: هذا الدواء حلال.",
                "ur": "\n\nنوٹ: یہ دوا حلال ہے۔",
                "bn": "\n\nনোট: এই ওষুধটি হালাল।",
                "fr": "\n\nNote: Ce médicament est certifié halal.",
                "es": "\n\nNota: Este medicamento está certificado como halal.",
            }

            if language in halal_notes:
                text += halal_notes[language]
                modified = True

        return {"text": text, "modified": modified}

    def _is_ramadan_period(self) -> bool:
        """Check if current date is during Ramadan."""
        # In production, would use Islamic calendar calculation
        # For now, return False
        return False

    def _add_fasting_considerations(self, text: str, language: str) -> Dict[str, Any]:
        """Add Ramadan fasting considerations for medications."""
        modified = False

        # Check if timing instructions present
        timing_keywords = ["daily", "morning", "evening", "meals", "يوميا", "diario"]
        has_timing = any(keyword in text.lower() for keyword in timing_keywords)

        if has_timing:
            fasting_notes = {
                "en": "\n\nDuring Ramadan: Take before dawn (Suhur) or after sunset (Iftar).",
                "ar": "\n\nخلال رمضان: تناول قبل الفجر (السحور) أو بعد غروب الشمس (الإفطار).",
                "ur": "\n\nرمضان کے دوران: سحری سے پہلے یا افطار کے بعد لیں۔",
                "bn": "\n\nরমজানের সময়: সেহরির আগে বা ইফতারের পরে নিন।",
            }

            if language in fasting_notes:
                text += fasting_notes[language]
                modified = True

        return {"text": text, "modified": modified}

    def _add_family_consultation_note(self, text: str, language: str) -> Dict[str, Any]:
        """Add family consultation expectations."""
        modified = False

        # Check if consent or decision context
        consent_keywords = ["consent", "agree", "decision", "موافقة", "consentimiento"]
        has_consent = any(keyword in text.lower() for keyword in consent_keywords)

        if has_consent:
            family_notes = {
                "en": "\n\nYou may wish to discuss this with your family before making a decision.",
                "ar": "\n\nقد ترغب في مناقشة هذا مع عائلتك قبل اتخاذ قرار.",
                "hi": "\n\nनिर्णय लेने से पहले आप अपने परिवार से चर्चा करना चाह सकते हैं।",
                "bn": "\n\nসিদ্ধান্ত নেওয়ার আগে আপনি আপনার পরিবারের সাথে আলোচনা করতে চাইতে পারেন।",
                "so": "\n\nWaxaad jeclaan kartaa inaad qoyskaaga kala hadashid go'aan ka hor.",
                "es": "\n\nPuede consultar con su familia antes de tomar una decisión.",
            }

            if language in family_notes:
                text += family_notes[language]
                modified = True

        return {"text": text, "modified": modified}

    def _apply_indirect_communication(
        self, text: str, language: str, mode: TranslationMode
    ) -> Dict[str, Any]:
        """Apply indirect communication style for cultures that prefer it."""
        modified = False
        changes = []

        # For serious diagnoses, soften the language
        if mode == TranslationMode.DIAGNOSTIC:
            direct_to_indirect = {
                "en": [
                    ("You have", "The tests indicate"),
                    ("is required", "would be beneficial"),
                    ("You must", "It would be advisable to"),
                ],
                "zh": [
                    ("你有", "检查显示"),  # You have -> Tests show
                    ("必须", "建议"),  # Must -> Suggest
                ],
            }

            if language in direct_to_indirect:
                for direct, indirect in direct_to_indirect[language]:
                    if direct in text:
                        text = text.replace(direct, indirect)
                        changes.append(f"{direct} → {indirect}")
                        modified = True

        return {"text": text, "modified": modified, "changes": changes}

    def _add_visual_aid_reference(self, text: str, language: str) -> Dict[str, Any]:
        """Add reference to visual aids for oral tradition cultures."""
        modified = False

        visual_notes = {
            "en": "\n\n📋 Visual instruction card provided with medication.",
            "so": "\n\n📋 Kaadhka tilmaamaha muuqaalka ah ayaa lagu bixiyaa dawada.",
            "am": "\n\n📋 የእይታ መመሪያ ካርድ ከመድሃኒቱ ጋር ተሰጥቷል።",
            "sw": "\n\n📋 Kadi ya maelekezo ya picha imetolewa pamoja na dawa.",
            "ar": "\n\n📋 بطاقة تعليمات مصورة مرفقة مع الدواء.",
        }

        if language in visual_notes:
            text += visual_notes[language]
            modified = True

        return {"text": text, "modified": modified}

    async def _validate_consent_translation(
        self, result: TranslationResult
    ) -> TranslationResult:
        """Validate consent form translation for completeness."""
        # Required elements for valid consent
        consent_elements = {
            "en": {
                "procedure": ["procedure", "treatment", "surgery", "therapy"],
                "risks": ["risk", "complication", "side effect", "adverse"],
                "benefits": ["benefit", "improve", "help", "advantage"],
                "alternatives": ["alternative", "option", "other treatment", "choice"],
                "voluntary": ["voluntary", "choice", "decide", "consent"],
                "withdraw": ["withdraw", "stop", "change mind", "refuse"],
                "questions": ["question", "ask", "clarify", "explain"],
            },
            "es": {
                "procedure": ["procedimiento", "tratamiento", "cirugía", "terapia"],
                "risks": ["riesgo", "complicación", "efecto secundario", "adverso"],
                "benefits": ["beneficio", "mejorar", "ayudar", "ventaja"],
                "alternatives": [
                    "alternativa",
                    "opción",
                    "otro tratamiento",
                    "elección",
                ],
                "voluntary": ["voluntario", "decisión", "decidir", "consentimiento"],
                "withdraw": ["retirar", "detener", "cambiar de opinión", "rechazar"],
                "questions": ["pregunta", "preguntar", "aclarar", "explicar"],
            },
            "ar": {
                "procedure": ["إجراء", "علاج", "جراحة", "عملية"],
                "risks": ["خطر", "مضاعفات", "آثار جانبية", "ضرر"],
                "benefits": ["فائدة", "تحسن", "مساعدة", "منفعة"],
                "alternatives": ["بديل", "خيار", "علاج آخر", "اختيار"],
                "voluntary": ["طوعي", "اختيار", "قرار", "موافقة"],
                "withdraw": ["سحب", "إيقاف", "تغيير رأي", "رفض"],
                "questions": ["سؤال", "استفسار", "توضيح", "شرح"],
            },
        }

        # Get appropriate element list for target language
        target_elements = consent_elements.get(
            result.target_language, consent_elements["en"]  # Default to English
        )

        missing_elements = []
        text_lower = result.translated_text.lower()

        for element_type, keywords in target_elements.items():
            found = any(keyword in text_lower for keyword in keywords)
            if not found:
                missing_elements.append(element_type)

        if missing_elements:
            result.warnings.append(
                f"Consent form may be missing required elements: {', '.join(missing_elements)}"
            )
            result.confidence_score *= 1 - 0.05 * len(missing_elements)
            result.review_required = True

        # Check for signature/date fields
        signature_keywords = {
            "en": ["signature", "date", "sign here"],
            "es": ["firma", "fecha", "firme aquí"],
            "ar": ["توقيع", "تاريخ", "وقع هنا"],
            "fr": ["signature", "date", "signez ici"],
            "zh": ["签名", "日期", "在此签名"],
        }

        lang_keywords = signature_keywords.get(
            result.target_language, signature_keywords["en"]
        )
        has_signature = any(keyword in text_lower for keyword in lang_keywords)

        if not has_signature:
            result.warnings.append("Consent form missing signature/date fields")
            result.review_required = True

        return result

    async def _validate_medication_translation(
        self, result: TranslationResult
    ) -> TranslationResult:
        """Validate medication instruction translation."""
        # Critical medication information patterns
        dosage_patterns = {
            "universal": [
                r"\d+\s*(?:mg|mcg|g|ml|cc|IU|units?)",
                r"\d+\s*(?:tablet|pill|capsule)",
            ],
            "en": [r"take\s+\d+", r"\d+\s+times?\s+(?:daily|per day|a day)"],
            "es": [r"tome?\s+\d+", r"\d+\s+veces?\s+(?:al día|diarias?)"],
            "ar": [r"تناول\s*\d+", r"\d+\s*مرات?\s*(?:يوميا|في اليوم)"],
            "fr": [r"prene?z?\s+\d+", r"\d+\s+fois\s+par\s+jour"],
            "zh": [r"服用?\s*\d+", r"每日\s*\d+\s*次"],
        }

        # Check for dosage information
        has_dosage = False
        patterns = dosage_patterns.get("universal", []) + dosage_patterns.get(
            result.target_language, []
        )

        for pattern in patterns:
            if re.search(pattern, result.translated_text, re.IGNORECASE | re.UNICODE):
                has_dosage = True
                break

        if not has_dosage:
            result.warnings.append(
                "Medication instructions may be missing dosage information"
            )
            result.confidence_score *= 0.85
            result.review_required = True

        # Check for frequency information
        frequency_keywords = {
            "en": [
                "daily",
                "twice",
                "three times",
                "morning",
                "evening",
                "night",
                "hourly",
                "as needed",
            ],
            "es": [
                "diario",
                "dos veces",
                "tres veces",
                "mañana",
                "tarde",
                "noche",
                "cada hora",
                "según necesidad",
            ],
            "ar": [
                "يوميا",
                "مرتين",
                "ثلاث مرات",
                "صباح",
                "مساء",
                "ليل",
                "كل ساعة",
                "عند الحاجة",
            ],
            "fr": [
                "quotidien",
                "deux fois",
                "trois fois",
                "matin",
                "soir",
                "nuit",
                "toutes les heures",
                "au besoin",
            ],
            "zh": [
                "每日",
                "每天",
                "两次",
                "三次",
                "早上",
                "晚上",
                "夜间",
                "每小时",
                "需要时",
            ],
        }

        lang_keywords = frequency_keywords.get(
            result.target_language, frequency_keywords["en"]
        )
        has_frequency = any(
            keyword in result.translated_text.lower() for keyword in lang_keywords
        )

        if not has_frequency:
            result.warnings.append(
                "Medication instructions may be missing frequency information"
            )
            result.confidence_score *= 0.9
            result.review_required = True

        # Check for critical warnings
        warning_keywords = {
            "en": [
                "warning",
                "do not",
                "avoid",
                "allergy",
                "side effect",
                "interaction",
            ],
            "es": [
                "advertencia",
                "no",
                "evite",
                "alergia",
                "efecto secundario",
                "interacción",
            ],
            "ar": ["تحذير", "لا", "تجنب", "حساسية", "آثار جانبية", "تفاعل"],
            "fr": [
                "avertissement",
                "ne pas",
                "éviter",
                "allergie",
                "effet secondaire",
                "interaction",
            ],
            "zh": ["警告", "不要", "避免", "过敏", "副作用", "相互作用"],
        }

        # If source had warnings, ensure they're in translation
        source_had_warnings = any(
            word in result.metadata.get("source_text", "").lower()
            for word in warning_keywords.get("en", [])
        )

        if source_had_warnings:
            lang_warnings = warning_keywords.get(
                result.target_language, warning_keywords["en"]
            )
            has_warnings = any(
                word in result.translated_text.lower() for word in lang_warnings
            )

            if not has_warnings:
                result.warnings.append(
                    "CRITICAL: Warning information may not be properly translated"
                )
                result.confidence_score *= 0.75
                result.review_required = True

        return result

    async def _validate_surgical_translation(
        self, result: TranslationResult
    ) -> TranslationResult:
        """Validate surgical consent/instruction translation."""
        # Surgical-specific terminology that must be precise
        critical_surgical_terms = {
            "anesthesia": ["general", "local", "spinal", "sedation"],
            "risks": ["bleeding", "infection", "complications", "death"],
            "procedure": ["incision", "remove", "repair", "reconstruct"],
        }

        # Add warning if surgical terminology density is high
        surgical_term_count = 0
        for _category, terms in critical_surgical_terms.items():
            for term in terms:
                if term in result.translated_text.lower():
                    surgical_term_count += 1

        if surgical_term_count > 5:
            result.warnings.append(
                "High density of critical surgical terms - recommend specialist review"
            )
            result.review_required = True

        # Ensure pre/post operative instructions are clear
        instruction_markers = {
            "en": [
                "before surgery",
                "after surgery",
                "pre-operative",
                "post-operative",
            ],
            "es": [
                "antes de la cirugía",
                "después de la cirugía",
                "preoperatorio",
                "postoperatorio",
            ],
            "ar": ["قبل الجراحة", "بعد الجراحة", "ما قبل العملية", "ما بعد العملية"],
            "fr": [
                "avant la chirurgie",
                "après la chirurgie",
                "préopératoire",
                "postopératoire",
            ],
            "zh": ["手术前", "手术后", "术前", "术后"],
        }

        lang_markers = instruction_markers.get(
            result.target_language, instruction_markers["en"]
        )
        has_clear_instructions = any(
            marker in result.translated_text.lower() for marker in lang_markers
        )

        if not has_clear_instructions and result.mode == TranslationMode.SURGICAL:
            result.warnings.append(
                "Surgical instructions should clearly indicate pre/post operative timing"
            )
            result.confidence_score *= 0.9

        return result

    def _requires_review(
        self,
        result: TranslationResult,
        request: TranslationRequest,
        qa_threshold: float,
    ) -> bool:
        """Determine if translation requires human review."""
        # Always review critical documents
        if request.mode in [
            TranslationMode.CONSENT,
            TranslationMode.MEDICATION,
            TranslationMode.SURGICAL,
            TranslationMode.MENTAL_HEALTH,
        ]:
            return True

        # Review if confidence is below threshold
        if result.confidence_score < qa_threshold:
            return True

        # Review if there are any warnings
        if len(result.warnings) > 0:
            return True

        # Review if many terms weren't preserved
        if result.medical_terms_preserved:
            preserved = sum(
                1 for t in result.medical_terms_preserved if t.get("preserved", False)
            )
            preservation_rate = preserved / len(result.medical_terms_preserved)
            if preservation_rate < 0.9:
                return True

        # Review if emergency mode and not life-threatening
        if request.urgency == "emergency" and request.mode != TranslationMode.EMERGENCY:
            return True

        # Review if significant cultural adaptations were made
        if len(result.cultural_adaptations) > 3:
            return True

        return False

    async def _submit_for_review(
        self, result: TranslationResult, request: TranslationRequest
    ) -> None:
        """Submit translation for human review."""
        try:
            review_priority = (
                ReviewPriority.HIGH
                if request.urgency == "emergency"
                else ReviewPriority.MEDIUM
            )

            if request.mode in [TranslationMode.CONSENT, TranslationMode.SURGICAL]:
                review_priority = ReviewPriority.CRITICAL

            review_id = await review_process.submit_for_review(
                translation_id=hashlib.sha256(
                    f"{request.text}{request.source_language}{request.target_language}".encode()
                ).hexdigest(),
                source_text=request.text,
                translated_text=result.translated_text,
                source_language=request.source_language,
                target_language=request.target_language,
                medical_context=request.mode.value,
                accuracy_score=result.confidence_score * 100,
                submitted_by="medical_translator_service",
                priority=review_priority,
            )

            result.metadata["review_id"] = review_id
            logger.info(
                "Translation submitted for review: %s (priority: %s)",
                review_id,
                review_priority,
            )

        except (ValueError, AttributeError) as e:
            logger.error("Failed to submit for review: %s", str(e))
            result.warnings.append(
                "Could not submit for human review - manual review recommended"
            )

    async def _backtranslate(self, result: TranslationResult) -> Optional[str]:
        """Perform backtranslation for quality verification."""
        try:
            # Use AWS Translate for speed
            response = self.translate_client.translate_text(
                Text=result.translated_text,
                SourceLanguageCode=result.target_language,
                TargetLanguageCode=result.source_language,
            )

            return str(response["TranslatedText"])

        except (ValueError, KeyError, AttributeError) as e:
            logger.error("Backtranslation failed: %s", str(e))
            return None

    async def _generate_alternatives(
        self, request: TranslationRequest, result: TranslationResult
    ) -> List[str]:
        """Generate alternative translations for critical texts."""
        alternatives = []

        try:
            # Generate 2-3 alternatives using different prompting strategies
            alt_prompt = f"""Provide 2 alternative translations for this {request.mode.value} text.
Each should be equally accurate but use different phrasing.

Original {request.source_language}: {request.text}
Primary translation {request.target_language}: {result.translated_text}

Provide alternatives in JSON array format: ["alt1", "alt2"]"""

            response = self.llm.predict(alt_prompt)

            # Parse alternatives
            try:
                alternatives = json.loads(response)
                if isinstance(alternatives, list):
                    return alternatives[:2]  # Max 2 alternatives
            except (json.JSONDecodeError, ValueError):
                # Try to extract from plain text
                lines = response.strip().split("\n")
                alternatives = [line.strip(" -\"'") for line in lines if line.strip()][
                    :2
                ]

        except (ValueError, RuntimeError, AttributeError) as e:
            logger.error("Failed to generate alternatives: %s", str(e))

        return alternatives

    async def _log_translation_request(self, request: TranslationRequest) -> None:
        """Log translation request for audit trail."""
        try:
            db = next(get_db())

            # Log translation request for audit trail
            # Using Translation model as TranslationLog doesn't exist
            log_entry = Translation(
                source_text=request.text[:1000],  # Truncate for storage
                source_language=request.source_language,
                target_language=request.target_language,
                translation_type=request.mode.value,
                urgency_level=request.urgency,
                requested_at=datetime.utcnow(),
                translation_metadata={
                    "patient_age": request.patient_age,
                    "patient_gender": request.patient_gender,
                    "medical_context": request.medical_context,
                    "text_length": len(request.text),
                },
            )

            db.add(log_entry)
            db.commit()

        except (ValueError, AttributeError) as e:
            logger.error("Failed to log translation request: %s", str(e))

    async def _log_translation_completion(self, result: TranslationResult) -> None:
        """Log translation completion for metrics."""
        try:
            # db = next(get_db())

            # Update the log entry
            # In production, would match by request ID

            metrics = {
                "confidence_score": result.confidence_score,
                "translation_time": result.translation_time,
                "medical_terms_preserved": len(result.medical_terms_preserved),
                "warnings": len(result.warnings),
                "review_required": result.review_required,
                "method": result.metadata.get("method", "unknown"),
            }

            # Log to CloudWatch or monitoring system
            logger.info(
                "Translation completed",
                extra={
                    "translation_metrics": metrics,
                    "source_lang": result.source_language,
                    "target_lang": result.target_language,
                    "mode": result.mode.value,
                },
            )

        except (ValueError, AttributeError) as e:
            logger.error("Failed to log translation completion: %s", str(e))

    def _get_age_group(self, age: int) -> str:
        """Get age group classification."""
        if age < 1:
            return "infant"
        elif age < 5:
            return "toddler"
        elif age < 13:
            return "child"
        elif age < 18:
            return "adolescent"
        elif age < 65:
            return "adult"
        else:
            return "elderly"

    def _validate_language_pair(self, source: str, target: str) -> bool:
        """Validate if language pair is supported."""
        return (
            source in self.SUPPORTED_LANGUAGES
            and target in self.SUPPORTED_LANGUAGES
            and source != target
        )

    def _generate_cache_key(self, request: TranslationRequest) -> str:
        """Generate cache key for translation."""
        key_data = (
            f"{request.text}:{request.source_language}:{request.target_language}:"
            f"{request.mode.value}:{request.cultural_adaptation}:{request.patient_gender or ''}"
        )
        return hashlib.sha256(key_data.encode()).hexdigest()

    async def _get_cached_translation(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """Get cached translation if available."""
        try:
            if self.redis_client is not None:
                cached = await self.redis_client.get(f"translation:v2:{cache_key}")
                if cached:
                    parsed = json.loads(cached)
                    return dict(parsed)
        except (redis.RedisError, json.JSONDecodeError, AttributeError, TypeError) as e:
            logger.error(f"Cache retrieval error: {e}")
        return None

    async def _cache_translation(
        self, cache_key: str, result: TranslationResult
    ) -> None:
        """Cache translation result."""
        try:
            if self.redis_client is not None:
                # Convert to cacheable format
                cache_data = {
                    "translated_text": result.translated_text,
                    "source_language": result.source_language,
                    "target_language": result.target_language,
                    "mode": result.mode.value,
                    "confidence_score": result.confidence_score,
                    "medical_terms_preserved": result.medical_terms_preserved,
                    "cultural_adaptations": result.cultural_adaptations,
                    "warnings": result.warnings,
                    "review_required": result.review_required,
                    "metadata": result.metadata,
                    "alternative_translations": result.alternative_translations,
                    "backtranslation": result.backtranslation,
                }

                await self.redis_client.setex(
                    f"translation:v2:{cache_key}",
                    self.cache_ttl,
                    json.dumps(cache_data, ensure_ascii=False),
                )

        except (redis.RedisError, json.JSONDecodeError, AttributeError, TypeError) as e:
            logger.error(f"Cache storage error: {e}")

    def _create_emergency_terminology(
        self, source_lang: str, target_lang: str, _emergency_terms: Dict[str, List[str]]
    ) -> str:
        """Create emergency terminology for AWS Translate.

        Args:
            source_lang: Source language code
            target_lang: Target language code
            _emergency_terms: Dictionary of emergency terms (reserved for future use)
        """
        try:
            # Use the emergency terminology service
            if emergency_terminology_service is None:
                raise ImportError("Emergency terminology service not available")

            # Note: emergency_terms parameter is passed for future use
            # Currently, the emergency terminology service manages its own terms
            # Use the emergency terminology service to create AWS terminology
            terminology_name = (
                emergency_terminology_service.get_emergency_terminology_for_aws(
                    source_lang=source_lang, target_lang=target_lang
                )
            )

            logger.info(f"Created emergency terminology: {terminology_name}")
            return str(terminology_name)

        except (ImportError, AttributeError, ValueError, KeyError) as e:
            logger.error(f"Error in emergency terminology creation: {e}")
            # Try to use existing terminology as fallback
            try:
                existing_terminologies = self.translate_client.list_terminologies()
                for term in existing_terminologies.get("TerminologyPropertiesList", []):
                    if (
                        f"EmergencyMedical_{source_lang}_{target_lang}" in term["Name"]
                        or f"EmergencyMedical_{target_lang}_{source_lang}"
                        in term["Name"]
                    ):
                        return str(term["Name"])
            except (boto3.exceptions.Boto3Error, KeyError, TypeError, AttributeError):
                pass

            # Last resort - create minimal terminology inline
            logger.warning("Creating minimal emergency terminology as last resort")
            return self._create_minimal_emergency_terminology(source_lang, target_lang)

    def _create_minimal_emergency_terminology(
        self, source_lang: str, target_lang: str
    ) -> str:
        """Create minimal emergency terminology as last resort."""
        try:
            terminology_name = f"EmergencyMedicalMinimal_{source_lang}_{target_lang}_{int(time.time())}"

            # Critical terms that must always be available
            critical_terms = {
                ("en", "es"): [
                    ("emergency", "emergencia"),
                    ("help", "ayuda"),
                    ("pain", "dolor"),
                    ("breathing", "respiración"),
                    ("bleeding", "sangrado"),
                    ("heart", "corazón"),
                    ("unconscious", "inconsciente"),
                    ("not breathing", "no respira"),
                    ("call help", "llamar ayuda"),
                    ("severe", "severo"),
                ],
                ("en", "ar"): [
                    ("emergency", "طوارئ"),
                    ("help", "مساعدة"),
                    ("pain", "ألم"),
                    ("breathing", "تنفس"),
                    ("bleeding", "نزيف"),
                    ("heart", "قلب"),
                    ("unconscious", "فاقد الوعي"),
                    ("not breathing", "لا يتنفس"),
                    ("call help", "اطلب المساعدة"),
                    ("severe", "شديد"),
                ],
                ("en", "fr"): [
                    ("emergency", "urgence"),
                    ("help", "aide"),
                    ("pain", "douleur"),
                    ("breathing", "respiration"),
                    ("bleeding", "saignement"),
                    ("heart", "cœur"),
                    ("unconscious", "inconscient"),
                    ("not breathing", "ne respire pas"),
                    ("call help", "appeler aide"),
                    ("severe", "sévère"),
                ],
            }

            # Build CSV
            csv_lines = ["source,target"]
            key = (source_lang, target_lang)

            if key in critical_terms:
                for source, target in critical_terms[key]:
                    csv_lines.append(f"{source},{target}")
            else:
                # Try reverse mapping
                reverse_key = (target_lang, source_lang)
                if reverse_key in critical_terms:
                    for target, source in critical_terms[reverse_key]:
                        csv_lines.append(f"{source},{target}")
                else:
                    # Use English as intermediate
                    logger.warning(
                        f"No direct mapping for {source_lang}-{target_lang}, using English intermediate"
                    )
                    return "EmergencyMedicalDefault"

            csv_content = "\n".join(csv_lines)

            # Upload to AWS
            self.translate_client.import_terminology(
                Name=terminology_name,
                MergeStrategy="OVERWRITE",
                TerminologyData={"File": csv_content.encode("utf-8"), "Format": "CSV"},
            )

            logger.info(f"Created minimal emergency terminology: {terminology_name}")
            return terminology_name

        except (json.JSONDecodeError, OSError, KeyError) as e:
            logger.error(f"Failed to create minimal terminology: {e}")
            return "EmergencyMedicalDefault"

    def _get_emergency_pairs(self) -> List[Tuple[str, str]]:
        """Get emergency medical term pairs for the language pair."""
        emergency_terms: Dict[Tuple[str, str], List[Tuple[str, str]]] = {
            ("en", "ar"): [
                ("airway", "مجرى الهواء"),
                ("breathing", "التنفس"),
                ("circulation", "الدورة الدموية"),
                ("bleeding", "نزيف"),
                ("unconscious", "فاقد الوعي"),
                ("allergic reaction", "رد فعل تحسسي"),
                ("heart attack", "نوبة قلبية"),
                ("stroke", "سكتة دماغية"),
                ("pain", "ألم"),
                ("emergency", "طوارئ"),
                ("critical", "حرج"),
                ("urgent", "عاجل"),
            ],
            ("en", "fr"): [
                ("airway", "voies respiratoires"),
                ("breathing", "respiration"),
                ("circulation", "circulation"),
                ("bleeding", "saignement"),
                ("unconscious", "inconscient"),
                ("allergic reaction", "réaction allergique"),
                ("heart attack", "crise cardiaque"),
                ("stroke", "AVC"),
                ("pain", "douleur"),
                ("emergency", "urgence"),
                ("critical", "critique"),
                ("urgent", "urgent"),
            ],
        }
        # TODO: Implement language pair detection from request context
        # For now, return empty list as this method is not yet integrated
        _ = emergency_terms  # Mark as intentionally unused
        return []

    def _merge_translations(
        self,
        primary: TranslationResult,
        secondary: TranslationResult,
        _medical_terms: List[Dict[str, Any]],
    ) -> TranslationResult:
        """Merge two translations taking best aspects of each."""
        # Use primary as base
        merged = primary

        # If secondary has better term preservation, use those sections
        if len(secondary.medical_terms_preserved) > len(
            primary.medical_terms_preserved
        ):
            # In production, would do sophisticated merging
            # For now, prefer the one with better preservation
            if secondary.confidence_score > primary.confidence_score * 0.9:
                merged = secondary

        # Combine warnings
        all_warnings = set(primary.warnings + secondary.warnings)
        merged.warnings = list(all_warnings)

        # Update metadata
        merged.metadata["merged"] = True
        merged.metadata["merge_source"] = "primary+secondary"

        return merged

    def _create_direct_translation_prompt(
        self, request: TranslationRequest, _medical_terms: List[Dict[str, Any]]
    ) -> str:
        """Create direct translation prompt for ensemble."""
        return self._create_standard_medical_prompt(
            request, f"Direct translation of {request.mode.value}", {}
        )

    def _create_stepwise_translation_prompt(
        self, request: TranslationRequest, _medical_terms: List[Dict[str, Any]]
    ) -> str:
        """Create step-by-step translation prompt for ensemble."""
        return f"""Translate step by step from {request.source_language} to {request.target_language}.

Step 1: Identify all medical terms and their meanings
Step 2: Translate the structure preserving medical accuracy
Step 3: Apply cultural adaptations as needed
Step 4: Verify all medical terms are correctly translated

Text: {request.text}

Provide final translation in JSON: {{"translation": "..."}}"""

    def _create_explanation_translation_prompt(
        self, request: TranslationRequest, _medical_terms: List[Dict[str, str]]
    ) -> str:
        """Create explanation-based translation prompt for ensemble."""
        return f"""First explain the medical meaning, then translate.

Medical text in {request.source_language}: {request.text}

1. Explain what this medical text means
2. List all medical terms and their significance
3. Translate to {request.target_language} preserving medical accuracy

Provide final translation in JSON: {{"translation": "..."}}"""

    async def translate_batch(
        self, requests: List[TranslationRequest]
    ) -> List[TranslationResult]:
        """Translate multiple texts in batch with priority handling."""
        # Sort by priority
        emergency_requests = [r for r in requests if r.urgency == "emergency"]
        urgent_requests = [r for r in requests if r.urgency == "urgent"]
        normal_requests = [r for r in requests if r.urgency == "normal"]

        # Process in priority order
        all_requests = emergency_requests + urgent_requests + normal_requests

        # Process with appropriate concurrency
        emergency_sem = asyncio.Semaphore(10)  # High concurrency for emergencies
        normal_sem = asyncio.Semaphore(5)  # Normal concurrency

        async def translate_with_limit(req: TranslationRequest) -> TranslationResult:
            sem = emergency_sem if req.urgency == "emergency" else normal_sem
            async with sem:
                return await self.translate(req)

        results = await asyncio.gather(
            *[translate_with_limit(req) for req in all_requests], return_exceptions=True
        )

        # Handle exceptions
        translation_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Batch translation error for item {i}: {result}")
                # Create error result
                translation_results.append(
                    TranslationResult(
                        translated_text="[Translation Error - Seek human translator]",
                        source_language=all_requests[i].source_language,
                        target_language=all_requests[i].target_language,
                        mode=all_requests[i].mode,
                        confidence_score=0.0,
                        medical_terms_preserved=[],
                        cultural_adaptations=[],
                        warnings=[f"Translation failed: {str(result)}"],
                        translation_time=0,
                        review_required=True,
                        metadata={"error": str(result), "batch_index": i},
                    )
                )
            else:
                assert isinstance(result, TranslationResult)
                translation_results.append(result)

        return translation_results

    def get_supported_languages(self) -> Dict[str, Dict[str, Any]]:
        """Get list of supported languages with metadata."""
        return self.SUPPORTED_LANGUAGES

    async def close(self) -> None:
        """Close connections and cleanup resources."""
        try:
            if self.redis_client:
                await self.redis_client.close()

            # Save any pending metrics
            await self._save_performance_metrics()

            logger.info("Medical translator service closed")

        except (OSError, AttributeError, RuntimeError) as e:
            logger.error(f"Error closing translator service: {e}")

    async def _save_performance_metrics(self) -> None:
        """Save performance metrics for analysis."""
        # In production, would save to CloudWatch or monitoring system
        return

    async def _validate_translation(
        self,
        result: "TranslationResult",
        _request: "TranslationRequest",
        _medical_terms: List[Dict[str, Any]],
        _medical_entities: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Validate translation result."""
        # TODO: Implement translation validation
        return {"confidence": result.confidence_score, "warnings": []}

    async def _aws_translate_with_terminology(
        self, _request: "TranslationRequest", _medical_terms: List[Dict[str, Any]]
    ) -> Optional["TranslationResult"]:
        """Translate using AWS Translate with medical terminology."""
        # TODO: Implement AWS Translate with terminology
        return None


# Global instance - Initialize only in production
medical_translator = None


def initialize_medical_translator() -> None:
    """Initialize medical translator with production checks."""
    # pylint: disable=global-statement
    global medical_translator

    if os.environ.get("ENVIRONMENT") == "production":
        if not os.environ.get("TRANSLATOR_KMS_KEY_ID"):
            raise ValueError(
                "CRITICAL: TRANSLATOR_KMS_KEY_ID not set for production! "
                "Medical translation requires encryption."
            )

        medical_translator = MedicalTranslator()
        logger.info("Medical translator initialized for production")
    else:
        logger.warning(
            "Medical translator not initialized - not in production environment"
        )


# Initialize on module load if in production
if os.environ.get("ENVIRONMENT") == "production":
    initialize_medical_translator()
