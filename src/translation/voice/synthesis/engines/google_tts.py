"""Google Cloud Text-to-Speech Implementation.

CRITICAL: This module handles voice synthesis for medical instructions.
Accurate pronunciation and clear audio are essential for patient safety.
"""

import os
from typing import Any, Dict, List, Optional, Set

from google.cloud import texttospeech
from google.oauth2 import service_account

from src.utils.logging import get_logger

logger = get_logger(__name__)


class GoogleTTSEngine:
    """Production Google Cloud TTS implementation for medical voice synthesis."""

    # Medical terminology pronunciation customizations
    MEDICAL_SUBSTITUTIONS = {
        "mg": "milligrams",
        "mcg": "micrograms",
        "mL": "milliliters",
        "kg": "kilograms",
        "IV": "intravenous",
        "IM": "intramuscular",
        "PO": "by mouth",
        "PRN": "as needed",
        "QD": "once daily",
        "BID": "twice daily",
        "TID": "three times daily",
        "QID": "four times daily",
        "q4h": "every four hours",
        "q6h": "every six hours",
        "q8h": "every eight hours",
        "q12h": "every twelve hours",
    }

    # Language-specific voice configurations
    VOICE_CONFIGS = {
        "en-US": {
            "voices": [
                {"name": "en-US-Neural2-F", "gender": "FEMALE", "type": "Neural2"},
                {"name": "en-US-Neural2-D", "gender": "MALE", "type": "Neural2"},
                {"name": "en-US-Wavenet-F", "gender": "FEMALE", "type": "WaveNet"},
                {"name": "en-US-Wavenet-D", "gender": "MALE", "type": "WaveNet"},
            ],
            "speaking_rate": 0.9,  # Slightly slower for medical content
        },
        "es-ES": {
            "voices": [
                {"name": "es-ES-Neural2-A", "gender": "FEMALE", "type": "Neural2"},
                {"name": "es-ES-Neural2-B", "gender": "MALE", "type": "Neural2"},
                {"name": "es-ES-Wavenet-A", "gender": "FEMALE", "type": "WaveNet"},
            ],
            "speaking_rate": 0.9,
        },
        "ar-XA": {
            "voices": [
                {"name": "ar-XA-Wavenet-A", "gender": "FEMALE", "type": "WaveNet"},
                {"name": "ar-XA-Wavenet-B", "gender": "MALE", "type": "WaveNet"},
                {"name": "ar-XA-Wavenet-C", "gender": "MALE", "type": "WaveNet"},
            ],
            "speaking_rate": 0.85,  # Slower for Arabic medical terms
        },
        "hi-IN": {
            "voices": [
                {"name": "hi-IN-Neural2-A", "gender": "FEMALE", "type": "Neural2"},
                {"name": "hi-IN-Neural2-B", "gender": "MALE", "type": "Neural2"},
                {"name": "hi-IN-Wavenet-A", "gender": "FEMALE", "type": "WaveNet"},
            ],
            "speaking_rate": 0.9,
        },
        "fr-FR": {
            "voices": [
                {"name": "fr-FR-Neural2-A", "gender": "FEMALE", "type": "Neural2"},
                {"name": "fr-FR-Neural2-B", "gender": "MALE", "type": "Neural2"},
                {"name": "fr-FR-Wavenet-A", "gender": "FEMALE", "type": "WaveNet"},
            ],
            "speaking_rate": 0.9,
        },
        "bn-IN": {
            "voices": [
                {"name": "bn-IN-Wavenet-A", "gender": "FEMALE", "type": "WaveNet"},
                {"name": "bn-IN-Wavenet-B", "gender": "MALE", "type": "WaveNet"},
            ],
            "speaking_rate": 0.85,
        },
        "sw-KE": {
            "voices": [
                {"name": "sw-KE-Standard-A", "gender": "FEMALE", "type": "Standard"},
                {"name": "sw-KE-Standard-B", "gender": "MALE", "type": "Standard"},
            ],
            "speaking_rate": 0.9,
        },
    }

    def __init__(self) -> None:
        """Initialize Google TTS engine."""
        self.client: Optional[texttospeech.TextToSpeechClient] = None
        self.credentials: Optional[service_account.Credentials] = None
        self._initialized = False
        self._supported_languages: Set[str] = set()
        self._voice_cache: Dict[str, texttospeech.Voice] = {}

    async def initialize(self) -> None:
        """Initialize Google Cloud TTS client."""
        if self._initialized:
            return

        try:
            # Get credentials from environment or service account file
            credentials_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")

            if not credentials_path:
                # Try to use credentials from environment variable
                credentials_json = os.environ.get("GOOGLE_CREDENTIALS_JSON")
                if credentials_json:
                    import json

                    credentials_info = json.loads(credentials_json)
                    self.credentials = (
                        service_account.Credentials.from_service_account_info(
                            credentials_info
                        )
                    )
                else:
                    raise ValueError(
                        "No Google Cloud credentials found. Set GOOGLE_APPLICATION_CREDENTIALS "
                        "or GOOGLE_CREDENTIALS_JSON environment variable."
                    )
            else:
                self.credentials = (
                    service_account.Credentials.from_service_account_file(
                        credentials_path
                    )
                )

            # Initialize client
            self.client = texttospeech.TextToSpeechClient(credentials=self.credentials)

            # List available voices to verify connection
            if self.client:
                voices_response = self.client.list_voices()
            else:
                raise RuntimeError("Failed to initialize Google TTS client")

            # Cache supported languages
            for voice in voices_response.voices:
                for language_code in voice.language_codes:
                    self._supported_languages.add(language_code)

            logger.info(
                f"Google TTS initialized successfully. "
                f"Supported languages: {len(self._supported_languages)}"
            )

            self._initialized = True

        except Exception as e:
            logger.error(f"Failed to initialize Google TTS: {e}")
            raise RuntimeError(f"Google TTS initialization failed: {e}")

    async def synthesize(
        self,
        text: str,
        language: str,
        voice_id: Optional[str] = None,
        speaking_rate: Optional[float] = None,
        pitch: Optional[float] = None,
        volume_gain_db: Optional[float] = None,
        output_format: str = "mp3",
        enable_time_pointing: bool = False,
    ) -> Dict[str, Any]:
        """Synthesize speech using Google Cloud TTS.

        Args:
            text: Text to synthesize
            language: Language code (e.g., 'en-US', 'es-ES')
            voice_id: Specific voice name or None for default
            speaking_rate: Speaking rate (0.25 to 4.0, default 1.0)
            pitch: Voice pitch (-20.0 to 20.0 semitones)
            volume_gain_db: Volume gain in dB (-96.0 to 16.0)
            output_format: Audio format (mp3, wav, ogg_opus)
            enable_time_pointing: Return time points for words

        Returns:
            Dictionary with audio_data, format, and metadata
        """
        if not self._initialized:
            await self.initialize()

        try:
            # Preprocess text for medical terminology
            processed_text = self._preprocess_medical_text(text, language)

            # Select voice
            voice_name = voice_id
            if not voice_name and language in self.VOICE_CONFIGS:
                # Use first available voice for language
                voices = self.VOICE_CONFIGS[language]["voices"]
                if voices and isinstance(voices, list) and len(voices) > 0:
                    voice_name = (
                        voices[0].get("name") if isinstance(voices[0], dict) else None
                    )

            if not voice_name:
                # Fallback to any voice for the language
                voice_name = self._find_voice_for_language(language)

            if not voice_name:
                raise ValueError(f"No voice available for language: {language}")

            # Build synthesis input
            synthesis_input = texttospeech.SynthesisInput(
                ssml=self._build_ssml(processed_text)
            )

            # Build voice selection
            voice = texttospeech.VoiceSelectionParams(
                language_code=language,
                name=voice_name,
            )

            # Build audio config
            audio_encoding = self._get_audio_encoding(output_format)

            audio_config_params = {
                "audio_encoding": audio_encoding,
            }

            # Apply speaking rate
            if speaking_rate is None and language in self.VOICE_CONFIGS:
                language_config = self.VOICE_CONFIGS[language]
                if isinstance(language_config, dict):
                    rate_value = language_config.get("speaking_rate", 1.0)
                    if isinstance(rate_value, (int, float)):
                        speaking_rate = float(rate_value)
            if speaking_rate is not None:
                audio_config_params["speaking_rate"] = speaking_rate

            # Apply pitch
            if pitch is not None:
                audio_config_params["pitch"] = pitch

            # Apply volume gain
            if volume_gain_db is not None:
                audio_config_params["volume_gain_db"] = volume_gain_db

            audio_config = texttospeech.AudioConfig(**audio_config_params)

            # Enable time pointing if requested
            if enable_time_pointing:
                audio_config.enable_time_pointing = [
                    texttospeech.SynthesizeSpeechRequest.TimepointType.SSML_MARK
                ]

            # Perform synthesis
            if self.client is None:
                raise RuntimeError("TTS client not initialized")
            response = self.client.synthesize_speech(
                input=synthesis_input,
                voice=voice,
                audio_config=audio_config,
            )

            # Extract timepoints if available
            timepoints = []
            if enable_time_pointing and hasattr(response, "timepoints"):
                timepoints = [
                    {"mark_name": tp.mark_name, "time_seconds": tp.time_seconds}
                    for tp in response.timepoints
                ]

            return {
                "success": True,
                "audio_data": response.audio_content,
                "format": output_format,
                "voice_used": voice_name,
                "language": language,
                "audio_length_bytes": len(response.audio_content),
                "timepoints": timepoints,
                "synthesis_metadata": {
                    "engine": "google_tts",
                    "neural_voice": "Neural" in voice_name,
                    "speaking_rate": speaking_rate,
                    "pitch": pitch,
                    "volume_gain_db": volume_gain_db,
                },
            }

        except Exception as e:
            logger.error(f"Google TTS synthesis error: {e}")
            return {
                "success": False,
                "error": str(e),
                "engine": "google_tts",
            }

    def _preprocess_medical_text(self, text: str, language: str) -> str:
        """Preprocess text for medical terminology pronunciation."""
        # Apply medical substitutions for English
        if language.startswith("en"):
            for abbrev, full in self.MEDICAL_SUBSTITUTIONS.items():
                # Use word boundaries to avoid partial replacements
                import re

                text = re.sub(r"\b" + re.escape(abbrev) + r"\b", full, text)

        # Handle decimal numbers with units
        import re

        # Pattern: number + optional decimal + unit
        pattern = r"(\d+(?:\.\d+)?)\s*(mg|mcg|mL|kg|g|L)\b"

        def replace_with_full_unit(match: re.Match[str]) -> str:
            number = match.group(1)
            unit = match.group(2)

            # Get full unit name
            if language.startswith("en"):
                unit_full = self.MEDICAL_SUBSTITUTIONS.get(unit, unit)
                return f"{number} {unit_full}"
            else:
                # For other languages, keep as is
                return match.group(0)

        text = re.sub(pattern, replace_with_full_unit, text)

        return text

    def _build_ssml(self, text: str) -> str:
        """Build SSML markup for enhanced pronunciation."""
        # Escape XML special characters
        text = text.replace("&", "&amp;")
        text = text.replace("<", "&lt;")
        text = text.replace(">", "&gt;")
        text = text.replace('"', "&quot;")
        text = text.replace("'", "&apos;")

        # Add pauses after sentences for clarity
        text = text.replace(". ", '. <break time="500ms"/> ')
        text = text.replace("! ", '! <break time="500ms"/> ')
        text = text.replace("? ", '? <break time="500ms"/> ')

        # Add emphasis to important medical terms
        important_terms = [
            "warning",
            "caution",
            "do not",
            "must not",
            "immediately",
            "emergency",
            "allergic",
            "allergy",
            "reaction",
        ]

        for term in important_terms:
            # Case insensitive replacement with emphasis
            import re

            pattern = re.compile(r"\b" + re.escape(term) + r"\b", re.IGNORECASE)
            text = pattern.sub(
                lambda m: f'<emphasis level="strong">{m.group(0)}</emphasis>', text
            )

        # Wrap in speak tags
        ssml = f"<speak>{text}</speak>"

        return ssml

    def _get_audio_encoding(self, format: str) -> texttospeech.AudioEncoding:
        """Get Google TTS audio encoding from format string."""
        format_mapping = {
            "mp3": texttospeech.AudioEncoding.MP3,
            "wav": texttospeech.AudioEncoding.LINEAR16,
            "ogg": texttospeech.AudioEncoding.OGG_OPUS,
            "ogg_opus": texttospeech.AudioEncoding.OGG_OPUS,
        }

        encoding = format_mapping.get(format.lower())
        if not encoding:
            logger.warning(f"Unknown format {format}, defaulting to MP3")
            encoding = texttospeech.AudioEncoding.MP3

        return encoding

    def _find_voice_for_language(self, language: str) -> Optional[str]:
        """Find any available voice for a language."""
        if not self.client:
            return None

        try:
            # List all voices
            voices = self.client.list_voices()

            # Find exact match first
            for voice in voices.voices:
                if language in voice.language_codes:
                    voice_name = str(voice.name)
                    return voice_name

            # Try language prefix match (e.g., 'en' for 'en-US')
            lang_prefix = language.split("-")[0]
            for voice in voices.voices:
                for voice_lang in voice.language_codes:
                    if voice_lang.startswith(lang_prefix):
                        voice_name = str(voice.name)
                        return voice_name

            return None

        except Exception as e:
            logger.error(f"Error finding voice: {e}")
            return None

    def get_available_voices(
        self, language: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get available voices for a language or all languages."""
        if not self._initialized:
            logger.warning("Google TTS not initialized")
            return []

        try:
            if not self.client:
                logger.warning("Google TTS client not initialized")
                return []
            voices = self.client.list_voices()
            available_voices = []

            for voice in voices.voices:
                # Filter by language if specified
                if language and language not in voice.language_codes:
                    continue

                voice_info = {
                    "voice_id": voice.name,
                    "name": voice.name,
                    "languages": list(voice.language_codes),
                    "gender": voice.ssml_gender.name,
                    "natural_sample_rate": voice.natural_sample_rate_hertz,
                }

                available_voices.append(voice_info)

            return available_voices

        except Exception as e:
            logger.error(f"Error listing voices: {e}")
            return []

    def is_language_supported(self, language: str) -> bool:
        """Check if a language is supported."""
        if not self._initialized:
            return False

        # Check exact match
        if language in self._supported_languages:
            return True

        # Check prefix match
        lang_prefix = language.split("-")[0]
        for supported_lang in self._supported_languages:
            if supported_lang.startswith(lang_prefix):
                return True

        return False

    async def cleanup(self) -> None:
        """Clean up resources."""
        if self.client:
            # Google Cloud client doesn't need explicit cleanup
            self.client = None
            self._initialized = False
            logger.info("Google TTS client cleaned up")


# Global instance
google_tts_engine = GoogleTTSEngine()
