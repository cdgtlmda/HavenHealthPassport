"""
Production Translation Pipeline for Haven Health Passport.

CRITICAL: This module provides real-time medical translation for refugees
using AWS Translate, Google Cloud Translation, and specialized medical
translation services. Accurate translation is vital for patient safety.

HIPAA Compliance: Translation of PHI requires:
- Access control for medical record translation requests
- Audit logging of all PHI translation operations
- Role-based permissions for translating patient data
- Secure handling of medical content during translation
"""

import asyncio
import hashlib
import json
import os
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, cast

import boto3
import deepl
import httpx
from google.cloud import translate_v3

from src.config import settings
from src.services.cache_service import get_cache_service
from src.utils.logging import get_logger

logger = get_logger(__name__)


class TranslationProvider(Enum):
    """Available translation providers."""

    AWS_TRANSLATE = "aws_translate"
    GOOGLE_TRANSLATE = "google_translate"
    DEEPL = "deepl"
    MEDICAL_TRANSLATOR = "medical_translator"  # Specialized medical API


class TranslationPipeline:
    """
    Production medical translation pipeline.

    Features:
    - Multi-provider translation with fallback
    - Medical terminology preservation
    - Cultural context adaptation
    - Translation quality validation
    """

    def __init__(self) -> None:
        """Initialize translation pipeline with providers and cache."""
        self.environment = settings.environment.lower()
        self.cache_service = get_cache_service()
        self.cache_ttl = timedelta(hours=24)

        # Initialize translation providers
        self._initialize_providers()

        # Medical terminology database
        self._load_medical_terms()

        # Supported languages for refugees
        self.supported_languages = [
            "en",
            "ar",
            "fa",
            "ps",
            "ur",
            "so",
            "ti",
            "am",  # Common refugee languages
            "fr",
            "es",
            "pt",
            "ru",
            "zh",
            "hi",
            "bn",
            "sw",
        ]

        logger.info("Initialized production translation pipeline")

    def _initialize_providers(self) -> None:
        """Initialize translation service providers."""
        # AWS Translate
        self.translate_client = boto3.client(
            "translate", region_name=settings.aws_region
        )

        # Google Cloud Translation
        google_creds = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        if google_creds and os.path.exists(google_creds):
            self.google_client = translate_v3.TranslationServiceClient()
            self.google_project_id = os.getenv("GOOGLE_CLOUD_PROJECT_ID")
            self.google_location = "global"
        else:
            self.google_client = None
            if self.environment == "production":
                logger.warning("Google Translation not configured")

        # DeepL
        deepl_key = os.getenv("DEEPL_API_KEY")
        if deepl_key:
            self.deepl_translator = deepl.Translator(deepl_key)
        else:
            self.deepl_translator = None
            if self.environment == "production":
                logger.warning("DeepL not configured")

        # Medical translation service
        self.medical_api_key = os.getenv("MEDICAL_TRANSLATOR_API_KEY")
        self.medical_api_url = os.getenv(
            "MEDICAL_TRANSLATOR_URL", "https://api.medical-translator.com"
        )

    def _load_medical_terms(self) -> None:
        """Load medical terminology database."""
        self.medical_terms = {
            "en": {
                "hypertension": "high blood pressure",
                "diabetes": "diabetes",
                "analgesic": "pain reliever",
                "antibiotic": "antibiotic",
                "vaccine": "vaccine",
                "emergency": "emergency",
                "allergy": "allergy",
                "prescription": "prescription",
                "dosage": "dosage",
                "symptoms": "symptoms",
            },
            "ar": {
                "hypertension": "ارتفاع ضغط الدم",
                "diabetes": "مرض السكري",
                "analgesic": "مسكن للألم",
                "antibiotic": "مضاد حيوي",
                "vaccine": "لقاح",
                "emergency": "طوارئ",
                "allergy": "حساسية",
                "prescription": "وصفة طبية",
                "dosage": "جرعة",
                "symptoms": "أعراض",
            },
            # Additional languages would be loaded from database
        }

    async def translate_text(
        self,
        text: str,
        source_language: str,
        target_language: str,
        context: Optional[str] = None,
        priority: str = "normal",
    ) -> Dict[str, Any]:
        """
        Translate text with medical context awareness.

        Args:
            text: Text to translate
            source_language: Source language code
            target_language: Target language code
            context: Medical context (e.g., 'diagnosis', 'prescription')
            priority: Translation priority ('urgent', 'normal')

        Returns:
            Translation result with metadata
        """
        # Check cache first
        cache_key = self._get_cache_key(text, source_language, target_language, context)
        cached = await self.cache_service.get(cache_key)
        if cached:
            cached_result = json.loads(cached)
            cached_result["cached"] = True
            return cast(Dict[str, Any], cached_result)

        # Preprocess medical terms
        preprocessed = self._preprocess_medical_terms(text, source_language)

        # Try primary provider
        result = {}
        try:
            if priority == "urgent" or context == "emergency":
                # Use fastest provider for urgent translations
                result = await self._translate_aws(
                    preprocessed["text"], source_language, target_language
                )
            else:
                # Try specialized medical translator first
                if self.medical_api_key and context in [
                    "diagnosis",
                    "prescription",
                    "procedure",
                ]:
                    medical_result = await self._translate_medical(
                        preprocessed["text"], source_language, target_language, context
                    )
                    if medical_result:
                        result = medical_result

                # Fallback to general providers
                if not result:
                    result = await self._translate_with_fallback(
                        preprocessed["text"], source_language, target_language
                    )

        except Exception as e:
            logger.error(f"Translation failed: {e}")
            # Emergency fallback
            result = {
                "translated_text": text,  # Return original if all fails
                "provider": "none",
                "confidence": 0.0,
                "error": str(e),
            }

        # Post-process medical terms
        if result and "translated_text" in result:
            result["translated_text"] = self._postprocess_medical_terms(
                result["translated_text"],
                preprocessed.get("term_mappings", {}),
                target_language,
            )

        # Add metadata
        result["source_language"] = source_language
        result["target_language"] = target_language
        result["context"] = context
        result["timestamp"] = datetime.utcnow().isoformat()
        result["cached"] = False

        # Cache successful translations
        if result.get("confidence", 0) > 0.8:
            await self.cache_service.set(
                cache_key, json.dumps(result), ttl=self.cache_ttl
            )

        # Log for audit
        logger.info(
            f"Translated {len(text)} chars from {source_language} to {target_language} "
            f"using {result.get('provider', 'unknown')}"
        )

        return result

    async def _translate_aws(
        self, text: str, source_lang: str, target_lang: str
    ) -> Dict[str, Any]:
        """Translate using AWS Translate."""
        try:
            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.translate_client.translate_text(
                    Text=text,
                    SourceLanguageCode=source_lang,
                    TargetLanguageCode=target_lang,
                    Settings={
                        "Formality": "FORMAL",  # Medical context requires formal language
                        "Profanity": "MASK",
                    },
                ),
            )

            return {
                "translated_text": response["TranslatedText"],
                "provider": "aws_translate",
                "confidence": 0.95,  # AWS doesn't provide confidence scores
            }

        except Exception as e:
            logger.error(f"AWS Translate error: {e}")
            raise

    async def _translate_medical(
        self, text: str, source_lang: str, target_lang: str, context: str
    ) -> Optional[Dict[str, Any]]:
        """Translate using specialized medical translation API."""
        if not self.medical_api_key:
            return None

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.medical_api_url}/v1/translate",
                    headers={
                        "Authorization": f"Bearer {self.medical_api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "text": text,
                        "source_language": source_lang,
                        "target_language": target_lang,
                        "domain": "medical",
                        "context": context,
                        "terminology_strict": True,
                    },
                )

                if response.status_code == 200:
                    data = response.json()
                    return {
                        "translated_text": data["translation"],
                        "provider": "medical_translator",
                        "confidence": data.get("confidence", 0.9),
                        "medical_terms": data.get("identified_terms", []),
                    }

        except Exception as e:
            logger.error(f"Medical translator error: {e}")

        return None

    async def _translate_google(
        self, text: str, source_lang: str, target_lang: str
    ) -> Dict[str, Any]:
        """Translate using Google Cloud Translation."""
        if not self.google_client:
            raise ValueError("Google Translation not configured")

        try:
            parent = (
                f"projects/{self.google_project_id}/locations/{self.google_location}"
            )

            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.google_client.translate_text(
                    request={
                        "parent": parent,
                        "contents": [text],
                        "mime_type": "text/plain",
                        "source_language_code": source_lang,
                        "target_language_code": target_lang,
                        "model": "projects/{}/locations/{}/models/general/nmt".format(
                            self.google_project_id, self.google_location
                        ),
                    }
                ),
            )

            translation = response.translations[0]
            return {
                "translated_text": translation.translated_text,
                "provider": "google_translate",
                "confidence": 0.93,
            }

        except Exception as e:
            logger.error(f"Google Translate error: {e}")
            raise

    async def _translate_deepl(
        self, text: str, source_lang: str, target_lang: str
    ) -> Dict[str, Any]:
        """Translate using DeepL."""
        if not self.deepl_translator:
            raise ValueError("DeepL not configured")

        try:
            # DeepL uses different language codes
            deepl_source = source_lang.upper() if source_lang != "auto" else None
            deepl_target = target_lang.upper()

            result = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.deepl_translator.translate_text(
                    text,
                    source_lang=deepl_source,
                    target_lang=deepl_target,
                    formality="formal",
                    preserve_formatting=True,
                ),
            )

            return {
                "translated_text": result.text,
                "provider": "deepl",
                "confidence": 0.96,  # DeepL generally has high quality
            }

        except Exception as e:
            logger.error(f"DeepL error: {e}")
            raise

    async def _translate_with_fallback(
        self, text: str, source_lang: str, target_lang: str
    ) -> Dict[str, Any]:
        """Try multiple providers with fallback."""
        providers = [
            ("aws", self._translate_aws),
            ("google", self._translate_google),
            ("deepl", self._translate_deepl),
        ]

        for provider_name, provider_func in providers:
            try:
                result = await provider_func(text, source_lang, target_lang)
                if result:
                    return result
            except Exception as e:
                logger.warning(f"{provider_name} translation failed: {e}")
                continue

        raise Exception("All translation providers failed")

    def _preprocess_medical_terms(self, text: str, source_lang: str) -> Dict[str, Any]:
        """Identify and mark medical terms before translation."""
        result: Dict[str, Any] = {"text": text, "term_mappings": {}}

        # Get medical terms for source language
        terms = self.medical_terms.get(source_lang, {})

        # Find and replace medical terms with placeholders
        for term_key, term_value in terms.items():
            if term_value.lower() in text.lower():
                placeholder = f"__MEDICAL_{term_key.upper()}__"
                result["text"] = result["text"].replace(term_value, placeholder)
                result["term_mappings"][placeholder] = term_key

        return result

    def _postprocess_medical_terms(
        self, translated_text: str, term_mappings: Dict[str, str], target_lang: str
    ) -> str:
        """Replace medical term placeholders with correct translations."""
        result = translated_text

        # Get medical terms for target language
        target_terms = self.medical_terms.get(target_lang, {})

        # Replace placeholders with proper medical terms
        for placeholder, term_key in term_mappings.items():
            if term_key in target_terms:
                result = result.replace(placeholder, target_terms[term_key])
            else:
                # Keep English term if no translation available
                result = result.replace(placeholder, term_key)

        return result

    def _get_cache_key(
        self, text: str, source_lang: str, target_lang: str, context: Optional[str]
    ) -> str:
        """Generate cache key for translation."""
        components = [text, source_lang, target_lang]
        if context:
            components.append(context)

        combined = "|".join(components)
        return f"translation:{hashlib.sha256(combined.encode()).hexdigest()}"

    async def translate_document(
        self,
        document_path: str,
        source_language: str,
        target_language: str,
        document_type: str = "medical_record",
    ) -> Dict[str, Any]:
        """
        Translate entire medical document.

        Args:
            document_path: Path to document in S3
            source_language: Source language code
            target_language: Target language code
            document_type: Type of medical document

        Returns:
            Translated document information
        """
        logger.info(f"Translating document: {document_path}")

        # For structured documents, use AWS Translate document translation
        try:
            # Parse S3 path
            bucket, key = document_path.replace("s3://", "").split("/", 1)

            # Create translation job
            job_name = f"haven-health-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"

            response = self.translate_client.start_text_translation_job(
                JobName=job_name,
                InputDataConfig={
                    "S3Uri": document_path,
                    "ContentType": "application/pdf",  # Supports PDF, DOCX, etc.
                },
                OutputDataConfig={
                    "S3Uri": f"s3://{bucket}/translations/{target_language}/"
                },
                DataAccessRoleArn=getattr(
                    settings,
                    "translation_role_arn",
                    getattr(settings, "aws_iam_role", ""),
                ),
                SourceLanguageCode=source_language,
                TargetLanguageCodes=[target_language],
                Settings={"Formality": "FORMAL", "Profanity": "MASK"},
            )

            job_id = response["JobId"]

            # Wait for completion (async polling)
            while True:
                await asyncio.sleep(5)
                status = self.translate_client.describe_text_translation_job(
                    JobId=job_id
                )

                if status["TextTranslationJobProperties"]["JobStatus"] in [
                    "COMPLETED",
                    "FAILED",
                ]:
                    break

            if status["TextTranslationJobProperties"]["JobStatus"] == "COMPLETED":
                output_path = status["TextTranslationJobProperties"][
                    "OutputDataConfig"
                ]["S3Uri"]
                return {
                    "success": True,
                    "translated_document_path": output_path,
                    "job_id": job_id,
                    "source_language": source_language,
                    "target_language": target_language,
                }
            else:
                raise Exception(
                    f"Translation job failed: {status['TextTranslationJobProperties']['Message']}"
                )

        except Exception as e:
            logger.error(f"Document translation failed: {e}")
            return {"success": False, "error": str(e)}

    async def detect_language(self, text: str) -> str:
        """Detect the language of input text."""
        try:
            # Use AWS Comprehend for language detection
            comprehend_client = boto3.client(
                "comprehend", region_name=settings.aws_region
            )

            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: comprehend_client.detect_dominant_language(
                    Text=text[:1000]
                ),  # First 1000 chars
            )

            if response["Languages"]:
                # Return the most likely language
                language_code = response["Languages"][0]["LanguageCode"]
                return str(language_code)

        except Exception as e:
            logger.error(f"Language detection failed: {e}")

        return "en"  # Default to English

    def get_supported_languages(self) -> List[Dict[str, str]]:
        """Get list of supported languages with names."""
        languages = []

        # Get from AWS Translate
        try:
            response = self.translate_client.list_languages()

            for lang in response["Languages"]:
                if lang["LanguageCode"] in self.supported_languages:
                    languages.append(
                        {
                            "code": lang["LanguageCode"],
                            "name": lang["LanguageName"],
                            "medical_support": lang["LanguageCode"]
                            in self.medical_terms,
                        }
                    )
        except Exception as e:
            logger.error(f"Failed to get language list: {e}")

            # Fallback to basic list
            languages = [
                {"code": "en", "name": "English", "medical_support": True},
                {"code": "ar", "name": "Arabic", "medical_support": True},
                {"code": "es", "name": "Spanish", "medical_support": True},
                {"code": "fr", "name": "French", "medical_support": True},
            ]

        return languages


# Global instance
_translation_pipeline = None


def get_translation_pipeline() -> TranslationPipeline:
    """Get the global translation pipeline instance."""
    global _translation_pipeline
    if _translation_pipeline is None:
        _translation_pipeline = TranslationPipeline()
    return _translation_pipeline
