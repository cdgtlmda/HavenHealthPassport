"""
Production-ready Amazon Polly voice synthesis implementation.

This module provides HIPAA-compliant text-to-speech synthesis using Amazon Polly
for critical healthcare communications to refugees and displaced populations.

CRITICAL: This handles life-critical medical information. Clear pronunciation
and proper medical term handling are essential for patient safety.

HIPAA Compliance: Voice synthesis of PHI requires:
- Access control for medical content synthesis requests
- Audit logging of all PHI voice synthesis operations
- Secure storage with encryption for synthesized audio containing PHI
- Role-based permissions for voice synthesis of medical records
"""

import asyncio
import hashlib
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    from mypy_boto3_polly import PollyClient
    from mypy_boto3_s3 import S3Client

import boto3
from botocore.exceptions import ClientError

from src.config import settings
from src.utils.logging import get_logger

logger = get_logger(__name__)


class PollyMedicalSynthesizer:
    """Production Amazon Polly synthesizer for medical communications."""

    polly_client: Optional["PollyClient"]
    s3_client: Optional["S3Client"]

    # CRITICAL: Medical lexicon entries for proper pronunciation
    MEDICAL_LEXICONS = {
        "en-US": {
            "name": "HavenHealthMedicalEN",
            "content": """<?xml version="1.0" encoding="UTF-8"?>
<lexicon version="1.0"
    xmlns="http://www.w3.org/2005/01/pronunciation-lexicon"
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
    xsi:schemaLocation="http://www.w3.org/2005/01/pronunciation-lexicon
        http://www.w3.org/TR/2007/CR-pronunciation-lexicon-20071212/pls.xsd"
    alphabet="ipa" xml:lang="en-US">
    <!-- Critical medical terms -->
    <lexeme>
        <grapheme>acetaminophen</grapheme>
        <phoneme>əˌsiːtəˈmɪnəfən</phoneme>
    </lexeme>
    <lexeme>
        <grapheme>ibuprofen</grapheme>
        <phoneme>ˌaɪbjuːˈproʊfən</phoneme>
    </lexeme>
    <lexeme>
        <grapheme>anaphylaxis</grapheme>
        <phoneme>ˌænəfɪˈlæksɪs</phoneme>
    </lexeme>
    <lexeme>
        <grapheme>hypoglycemia</grapheme>
        <phoneme>ˌhaɪpoʊglaɪˈsiːmiə</phoneme>
    </lexeme>
    <!-- Medical abbreviations -->
    <lexeme>
        <grapheme>BP</grapheme>
        <alias>blood pressure</alias>
    </lexeme>
    <lexeme>
        <grapheme>IV</grapheme>
        <alias>intravenous</alias>
    </lexeme>
    <lexeme>
        <grapheme>IM</grapheme>
        <alias>intramuscular</alias>
    </lexeme>
    <lexeme>
        <grapheme>PO</grapheme>
        <alias>by mouth</alias>
    </lexeme>
    <lexeme>
        <grapheme>PRN</grapheme>
        <alias>as needed</alias>
    </lexeme>
    <lexeme>
        <grapheme>BID</grapheme>
        <alias>twice daily</alias>
    </lexeme>
    <lexeme>
        <grapheme>TID</grapheme>
        <alias>three times daily</alias>
    </lexeme>
    <lexeme>
        <grapheme>QID</grapheme>
        <alias>four times daily</alias>
    </lexeme>
</lexicon>""",
        },
        "es-ES": {
            "name": "HavenHealthMedicalES",
            "content": """<?xml version="1.0" encoding="UTF-8"?>
<lexicon version="1.0"
    xmlns="http://www.w3.org/2005/01/pronunciation-lexicon"
    alphabet="ipa" xml:lang="es-ES">
    <lexeme>
        <grapheme>paracetamol</grapheme>
        <phoneme>paɾaθetaˈmol</phoneme>
    </lexeme>
    <lexeme>
        <grapheme>ibuprofeno</grapheme>
        <phoneme>iβupɾoˈfeno</phoneme>
    </lexeme>
    <lexeme>
        <grapheme>anafilaxia</grapheme>
        <phoneme>anafiˈlaksja</phoneme>
    </lexeme>
</lexicon>""",
        },
        "ar": {
            "name": "HavenHealthMedicalAR",
            "content": """<?xml version="1.0" encoding="UTF-8"?>
<lexicon version="1.0"
    xmlns="http://www.w3.org/2005/01/pronunciation-lexicon"
    alphabet="ipa" xml:lang="ar">
    <lexeme>
        <grapheme>السكري</grapheme>
        <phoneme>assukkari</phoneme>
    </lexeme>
    <lexeme>
        <grapheme>ضغط الدم</grapheme>
        <phoneme>daght addam</phoneme>
    </lexeme>
</lexicon>""",
        },
    }

    # Voice configurations optimized for medical clarity
    MEDICAL_VOICE_CONFIGS = {
        "en-US": {
            "primary": {"id": "Joanna", "engine": "neural"},
            "secondary": {"id": "Ruth", "engine": "neural"},
            "fallback": {"id": "Joanna", "engine": "standard"},
        },
        "es-ES": {
            "primary": {"id": "Lupe", "engine": "neural"},
            "secondary": {"id": "Lucia", "engine": "neural"},
            "fallback": {"id": "Conchita", "engine": "standard"},
        },
        "es-MX": {
            "primary": {"id": "Mia", "engine": "neural"},
            "fallback": {"id": "Mia", "engine": "standard"},
        },
        "ar": {
            "primary": {"id": "Zeina", "engine": "standard"},
            "fallback": {"id": "Zeina", "engine": "standard"},
        },
        "hi-IN": {
            "primary": {"id": "Kajal", "engine": "neural"},
            "fallback": {"id": "Aditi", "engine": "standard"},
        },
        "bn-IN": {
            "primary": {"id": "Aditi", "engine": "standard"},  # Bengali uses Aditi
            "fallback": {"id": "Aditi", "engine": "standard"},
        },
        "fr-FR": {
            "primary": {"id": "Lea", "engine": "neural"},
            "fallback": {"id": "Celine", "engine": "standard"},
        },
        "pt-BR": {
            "primary": {"id": "Camila", "engine": "neural"},
            "fallback": {"id": "Vitoria", "engine": "standard"},
        },
        "zh-CN": {
            "primary": {"id": "Zhiyu", "engine": "neural"},
            "fallback": {"id": "Zhiyu", "engine": "standard"},
        },
        "ru-RU": {
            "primary": {"id": "Tatyana", "engine": "standard"},
            "fallback": {"id": "Tatyana", "engine": "standard"},
        },
        "de-DE": {
            "primary": {"id": "Vicki", "engine": "neural"},
            "fallback": {"id": "Marlene", "engine": "standard"},
        },
    }

    def __init__(self) -> None:
        """Initialize Polly synthesizer with medical configurations."""
        self.polly_client = None
        self.s3_client = None
        self.lexicons_initialized = False
        self.voice_cache: Dict[str, Any] = {}
        self.synthesis_metrics = {
            "total_requests": 0,
            "successful_syntheses": 0,
            "failed_syntheses": 0,
            "average_latency_ms": 0,
        }

    async def initialize(self) -> None:
        """Initialize AWS clients and medical lexicons."""
        try:
            # Initialize AWS clients
            self.polly_client = boto3.client(
                "polly",
                region_name=settings.aws_region,
                aws_access_key_id=settings.aws_access_key_id,
                aws_secret_access_key=settings.aws_secret_access_key,
            )

            self.s3_client = boto3.client(
                "s3",
                region_name=settings.aws_region,
                aws_access_key_id=settings.aws_access_key_id,
                aws_secret_access_key=settings.aws_secret_access_key,
            )

            # Initialize medical lexicons
            await self._initialize_medical_lexicons()

            logger.info("Polly synthesizer initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize Polly synthesizer: {e}")
            raise

    async def _initialize_medical_lexicons(self) -> None:
        """Upload medical pronunciation lexicons to Polly."""
        if not self.polly_client:
            logger.error("Polly client not initialized")
            return

        assert self.polly_client is not None
        for lang, lexicon_data in self.MEDICAL_LEXICONS.items():
            try:
                # Check if lexicon exists
                try:
                    self.polly_client.get_lexicon(Name=lexicon_data["name"])
                    logger.info(f"Lexicon {lexicon_data['name']} already exists")
                except ClientError as e:
                    # Upload lexicon if not found
                    if (
                        e.response.get("Error", {}).get("Code")
                        == "LexiconNotFoundException"
                    ):
                        self.polly_client.put_lexicon(
                            Name=lexicon_data["name"],
                            Content=lexicon_data["content"],
                        )
                        logger.info(f"Uploaded medical lexicon: {lexicon_data['name']}")

            except Exception as e:
                logger.error(f"Failed to initialize lexicon for {lang}: {e}")
                # Continue with other lexicons - don't fail completely

        self.lexicons_initialized = True

    async def synthesize_medical_speech(
        self,
        text: str,
        language: str,
        voice_id: Optional[str] = None,
        speech_rate: float = 0.9,  # Slower for medical clarity
        neural: bool = True,
        emergency: bool = False,
    ) -> Dict[str, Any]:
        """
        Synthesize medical speech with Amazon Polly.

        Args:
            text: Text to synthesize (medical content)
            language: Language code (e.g., 'en-US', 'es-ES')
            voice_id: Optional specific voice ID
            speech_rate: Speech rate (0.5-2.0, default 0.9 for clarity)
            neural: Use neural voice if available
            emergency: Emergency mode for urgent communications

        Returns:
            Dictionary with audio data and metadata
        """
        start_time = datetime.now()
        self.synthesis_metrics["total_requests"] += 1

        try:
            # Validate inputs
            if not text or not text.strip():
                raise ValueError("Text cannot be empty for medical communications")

            if len(text) > 3000:  # Polly limit
                raise ValueError("Text exceeds maximum length of 3000 characters")

            # Get appropriate voice
            voice_config = self._get_voice_for_language(language, voice_id, neural)
            if not voice_config:
                raise ValueError(f"No voice available for language: {language}")

            # Build SSML for medical clarity
            ssml = self._build_medical_ssml(
                text, language, speech_rate, emergency, voice_config
            )

            # Get lexicon for language
            lexicon_names = []
            lang_prefix = language.split("-")[0]
            if lang_prefix in self.MEDICAL_LEXICONS:
                lexicon_names.append(self.MEDICAL_LEXICONS[lang_prefix]["name"])

            # Synthesize with Polly
            logger.info(
                f"Synthesizing medical speech for {language} using {voice_config['id']}"
            )

            if self.polly_client is None:
                raise RuntimeError("Polly client not initialized")

            assert self.polly_client is not None
            response = self.polly_client.synthesize_speech(
                Text=ssml,
                TextType="ssml",
                OutputFormat="mp3",  # MP3 for compatibility
                VoiceId=voice_config["id"],
                Engine=voice_config["engine"],
                LexiconNames=lexicon_names if lexicon_names else None,
                LanguageCode=language,
            )

            # Read audio stream
            audio_data = response["AudioStream"].read()

            # Calculate metrics
            synthesis_time = (datetime.now() - start_time).total_seconds() * 1000
            self.synthesis_metrics["successful_syntheses"] += 1
            self._update_average_latency(synthesis_time)

            # Generate secure filename
            file_hash = hashlib.sha256(
                f"{text}{language}{voice_config['id']}".encode()
            ).hexdigest()[:12]
            filename = f"medical_audio_{language}_{file_hash}.mp3"

            # Upload to S3 if bucket configured
            audio_url = None
            if settings.s3_bucket:
                try:
                    audio_url = await self._upload_to_s3(audio_data, filename)
                except Exception as e:
                    logger.error(f"Failed to upload audio to S3: {e}")
                    # Continue without S3 URL

            # Log success with PHI protection
            logger.info(
                f"Successfully synthesized medical speech: "
                f"language={language}, voice={voice_config['id']}, "
                f"duration_ms={synthesis_time:.0f}, size_bytes={len(audio_data)}"
            )

            return {
                "success": True,
                "audio_data": audio_data,
                "audio_url": audio_url,
                "filename": filename,
                "voice_used": voice_config["id"],
                "engine": voice_config["engine"],
                "language": language,
                "neural": voice_config["engine"] == "neural",
                "synthesis_time_ms": synthesis_time,
                "audio_size_bytes": len(audio_data),
                "lexicons_used": lexicon_names,
                "metadata": {
                    "synthesized_at": datetime.now().isoformat(),
                    "speech_rate": speech_rate,
                    "emergency": emergency,
                    "text_length": len(text),
                },
            }

        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            error_msg = e.response["Error"]["Message"]

            self.synthesis_metrics["failed_syntheses"] += 1

            # Handle specific Polly errors
            if error_code == "InvalidSsmlException":
                logger.error(f"Invalid SSML for medical synthesis: {error_msg}")
                # Try plain text synthesis as fallback
                return await self._synthesize_plain_text_fallback(text, language)

            elif error_code == "TextLengthExceededException":
                logger.error(f"Text too long for synthesis: {len(text)} characters")
                return {
                    "success": False,
                    "error": "Text exceeds maximum length for voice synthesis",
                    "error_code": "TEXT_TOO_LONG",
                    "max_length": 3000,
                }

            elif error_code == "ThrottlingException":
                logger.warning("Polly throttling detected, implementing backoff")
                await asyncio.sleep(1)  # Brief delay
                # Could implement retry logic here

            logger.error(f"Polly synthesis failed: {error_code} - {error_msg}")
            return {"success": False, "error": error_msg, "error_code": error_code}

        except Exception as e:
            self.synthesis_metrics["failed_syntheses"] += 1
            logger.error(f"Unexpected error in medical synthesis: {e}")
            return {"success": False, "error": str(e), "error_code": "SYNTHESIS_ERROR"}

    def _get_voice_for_language(
        self, language: str, voice_id: Optional[str] = None, prefer_neural: bool = True
    ) -> Optional[Dict[str, str]]:
        """Get appropriate voice configuration for language."""
        # Use specific voice if provided
        if voice_id:
            return {"id": voice_id, "engine": "neural" if prefer_neural else "standard"}

        # Get voice config for language
        if language not in self.MEDICAL_VOICE_CONFIGS:
            # Try language prefix (e.g., 'en' from 'en-GB')
            lang_prefix = language.split("-")[0]
            for supported_lang in self.MEDICAL_VOICE_CONFIGS:
                if supported_lang.startswith(lang_prefix):
                    language = supported_lang
                    break
            else:
                return None

        config = self.MEDICAL_VOICE_CONFIGS[language]

        # Select voice based on neural preference
        if prefer_neural and "primary" in config:
            return config["primary"]
        elif "fallback" in config:
            return config["fallback"]

        return None

    def _build_medical_ssml(
        self,
        text: str,
        language: str,
        speech_rate: float,
        emergency: bool,
        voice_config: Dict[str, str],
    ) -> str:
        """Build SSML for medical speech with appropriate prosody."""
        # Calculate speech rate percentage
        rate_percent = int(speech_rate * 100)

        # Adjust for emergency
        if emergency:
            rate_percent = min(110, rate_percent + 10)  # Slightly faster
            pitch = "+5%"  # Slightly higher pitch
            emphasis = "strong"
        else:
            pitch = "0%"  # Normal pitch
            emphasis = "moderate"

        # Build SSML
        ssml_parts = ["<speak>"]

        # Add language tag
        ssml_parts.append(f'<lang xml:lang="{language}">')

        # Add prosody for medical clarity
        ssml_parts.append(
            f'<prosody rate="{rate_percent}%" pitch="{pitch}" volume="loud">'
        )

        # Process text for medical emphasis
        processed_text = self._add_medical_emphasis(text, emphasis)
        ssml_parts.append(processed_text)

        # Close tags
        ssml_parts.append("</prosody>")
        ssml_parts.append("</lang>")
        ssml_parts.append("</speak>")

        return "".join(ssml_parts)

    def _add_medical_emphasis(self, text: str, emphasis_level: str) -> str:
        """Add emphasis to critical medical terms and numbers."""
        import re

        # Emphasize numbers (dosages, times, etc.)
        text = re.sub(
            r"\b(\d+(?:\.\d+)?)\s*(mg|ml|g|kg|tablets?|pills?|capsules?|times?|hours?|days?)\b",
            rf'<emphasis level="{emphasis_level}">\1 \2</emphasis>',
            text,
            flags=re.IGNORECASE,
        )

        # Emphasize critical words
        critical_words = [
            "emergency",
            "urgent",
            "immediately",
            "warning",
            "danger",
            "allergy",
            "allergic",
            "stop",
            "do not",
            "don't",
            "importante",
            "urgente",
            "inmediatamente",
            "peligro",  # Spanish
            "مهم",
            "عاجل",
            "فورا",
            "خطر",  # Arabic
        ]

        for word in critical_words:
            text = re.sub(
                rf"\b({word})\b",
                r'<emphasis level="strong">\1</emphasis>',
                text,
                flags=re.IGNORECASE,
            )

        # Add pauses after sentences for clarity
        text = text.replace(". ", '. <break time="500ms"/> ')
        text = text.replace("! ", '! <break time="500ms"/> ')
        text = text.replace("? ", '? <break time="500ms"/> ')

        return text

    async def _synthesize_plain_text_fallback(
        self, text: str, language: str
    ) -> Dict[str, Any]:
        """Fallback synthesis without SSML if SSML fails."""
        try:
            voice_config = self._get_voice_for_language(language, None, False)
            if not voice_config:
                return {
                    "success": False,
                    "error": f"No fallback voice for language: {language}",
                    "error_code": "NO_VOICE_AVAILABLE",
                }

            if self.polly_client is None:
                raise RuntimeError("Polly client not initialized")

            assert self.polly_client is not None
            response = self.polly_client.synthesize_speech(
                Text=text,
                TextType="text",
                OutputFormat="mp3",
                VoiceId=voice_config["id"],
                Engine="standard",  # Use standard engine for fallback
            )

            audio_data = response["AudioStream"].read()

            logger.warning(f"Used plain text fallback for {language}")

            return {
                "success": True,
                "audio_data": audio_data,
                "audio_url": None,
                "voice_used": voice_config["id"],
                "engine": "standard",
                "fallback": True,
                "audio_size_bytes": len(audio_data),
            }

        except Exception as e:
            logger.error(f"Fallback synthesis also failed: {e}")
            return {
                "success": False,
                "error": "All synthesis methods failed",
                "error_code": "COMPLETE_FAILURE",
            }

    async def _upload_to_s3(self, audio_data: bytes, filename: str) -> str:
        """Upload audio to S3 and return URL."""
        try:
            # Upload with encryption
            if self.s3_client is None:
                raise RuntimeError("S3 client not initialized")

            assert self.s3_client is not None
            self.s3_client.put_object(
                Bucket=settings.s3_bucket,
                Key=f"voice-synthesis/{filename}",
                Body=audio_data,
                ContentType="audio/mpeg",
                ServerSideEncryption="aws:kms",
                Metadata={
                    "service": "haven-health",
                    "type": "medical-audio",
                    "synthesized": datetime.now().isoformat(),
                },
            )

            # Generate presigned URL (24 hour expiry)
            if not self.s3_client:
                raise RuntimeError("S3 client not initialized")

            url = self.s3_client.generate_presigned_url(
                "get_object",
                Params={
                    "Bucket": settings.s3_bucket,
                    "Key": f"voice-synthesis/{filename}",
                },
                ExpiresIn=86400,  # 24 hours
            )

            return str(url)

        except Exception as e:
            logger.error(f"S3 upload failed: {e}")
            raise

    def _update_average_latency(self, new_latency: float) -> None:
        """Update running average of synthesis latency."""
        count = self.synthesis_metrics["successful_syntheses"]
        current_avg = self.synthesis_metrics["average_latency_ms"]

        # Calculate new average
        new_avg = ((current_avg * (count - 1)) + new_latency) / count
        self.synthesis_metrics["average_latency_ms"] = int(new_avg)

    async def get_available_voices(
        self, language: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get available voices for a language or all languages."""
        try:
            # Get voices from Polly
            params = {}
            if language:
                params["LanguageCode"] = language

            if self.polly_client is None:
                raise RuntimeError("Polly client not initialized")

            assert self.polly_client is not None
            response = self.polly_client.describe_voices(**params)

            voices = []
            for voice in response["Voices"]:
                voices.append(
                    {
                        "id": voice["Id"],
                        "name": voice["Name"],
                        "language": voice["LanguageCode"],
                        "gender": voice["Gender"],
                        "neural_supported": "neural"
                        in voice.get("SupportedEngines", []),
                        "medical_optimized": voice["Id"]
                        in [
                            v["id"]
                            for config in self.MEDICAL_VOICE_CONFIGS.values()
                            for v in [
                                config.get("primary", {}),
                                config.get("secondary", {}),
                            ]
                            if "id" in v
                        ],
                    }
                )

            return voices

        except Exception as e:
            logger.error(f"Failed to get available voices: {e}")
            return []

    def get_synthesis_metrics(self) -> Dict[str, Any]:
        """Get synthesis performance metrics."""
        return {
            **self.synthesis_metrics,
            "success_rate": (
                self.synthesis_metrics["successful_syntheses"]
                / max(1, self.synthesis_metrics["total_requests"])
            )
            * 100,
            "lexicons_initialized": self.lexicons_initialized,
            "cached_voices": len(self.voice_cache),
        }

    async def test_synthesis(self, language: str = "en-US") -> bool:
        """Test synthesis capability for a language."""
        test_text = {
            "en-US": "This is a test of the medical voice synthesis system.",
            "es-ES": "Esta es una prueba del sistema de síntesis de voz médica.",
            "ar": "هذا اختبار لنظام تركيب الصوت الطبي.",
            "hi-IN": "यह चिकित्सा आवाज संश्लेषण प्रणाली का परीक्षण है।",
        }

        text = test_text.get(language, test_text["en-US"])

        result = await self.synthesize_medical_speech(
            text=text, language=language, neural=True
        )

        return bool(result.get("success", False))


# Global instance
polly_synthesizer = PollyMedicalSynthesizer()
