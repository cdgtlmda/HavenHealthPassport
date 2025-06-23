"""Azure Cognitive Services Text-to-Speech Implementation.

CRITICAL: This module handles voice synthesis for medical instructions.
Accurate pronunciation and clear audio are essential for patient safety.
"""

import os
from typing import Any, Dict, List, Optional

from azure.cognitiveservices.speech import (
    AudioConfig,
    CancellationReason,
    ResultReason,
    SpeechConfig,
    SpeechSynthesisOutputFormat,
    SpeechSynthesizer,
)
from azure.cognitiveservices.speech.audio import AudioOutputStream

from src.utils.logging import get_logger

logger = get_logger(__name__)


class AzureTTSEngine:
    """Production Azure Cognitive Services TTS implementation."""

    # Language-specific voice configurations
    VOICE_CONFIGS = {
        "en-US": {
            "voices": [
                {
                    "name": "en-US-JennyNeural",
                    "gender": "Female",
                    "style": "professional",
                },
                {"name": "en-US-AriaNeural", "gender": "Female", "style": "friendly"},
                {"name": "en-US-GuyNeural", "gender": "Male", "style": "professional"},
                {"name": "en-US-DavisNeural", "gender": "Male", "style": "friendly"},
            ],
            "speaking_rate": "0.9",  # Slightly slower for medical content
        },
        "es-ES": {
            "voices": [
                {"name": "es-ES-ElviraNeural", "gender": "Female"},
                {"name": "es-ES-AlvaroNeural", "gender": "Male"},
            ],
            "speaking_rate": "0.9",
        },
        "ar-SA": {
            "voices": [
                {"name": "ar-SA-ZariyahNeural", "gender": "Female"},
                {"name": "ar-SA-HamedNeural", "gender": "Male"},
            ],
            "speaking_rate": "0.85",
        },
        "hi-IN": {
            "voices": [
                {"name": "hi-IN-SwaraNeural", "gender": "Female"},
                {"name": "hi-IN-MadhurNeural", "gender": "Male"},
            ],
            "speaking_rate": "0.9",
        },
        "fr-FR": {
            "voices": [
                {"name": "fr-FR-DeniseNeural", "gender": "Female"},
                {"name": "fr-FR-HenriNeural", "gender": "Male"},
            ],
            "speaking_rate": "0.9",
        },
        "bn-IN": {
            "voices": [
                {"name": "bn-IN-TanishaaNeural", "gender": "Female"},
                {"name": "bn-IN-BashkarNeural", "gender": "Male"},
            ],
            "speaking_rate": "0.85",
        },
        "sw-KE": {
            "voices": [
                {"name": "sw-KE-ZuriNeural", "gender": "Female"},
                {"name": "sw-KE-RafikiNeural", "gender": "Male"},
            ],
            "speaking_rate": "0.9",
        },
    }

    # Medical terminology SSML substitutions
    MEDICAL_SSML = {
        "mg": '<say-as interpret-as="unit">mg</say-as>',
        "mcg": '<say-as interpret-as="unit">mcg</say-as>',
        "mL": '<say-as interpret-as="unit">mL</say-as>',
        "kg": '<say-as interpret-as="unit">kg</say-as>',
    }

    def __init__(self) -> None:
        """Initialize Azure TTS engine."""
        self.speech_config: Optional[SpeechConfig] = None
        self._initialized = False
        self._subscription_key: Optional[str] = None
        self._region: Optional[str] = None

    async def initialize(self) -> None:
        """Initialize Azure Cognitive Services client."""
        if self._initialized:
            return

        try:
            # Get credentials from environment
            self._subscription_key = os.environ.get("AZURE_SPEECH_KEY")
            self._region = os.environ.get("AZURE_SPEECH_REGION", "eastus")

            if not self._subscription_key:
                # Try alternative environment variable names
                self._subscription_key = os.environ.get("AZURE_COGNITIVE_SERVICES_KEY")

            if not self._subscription_key:
                raise ValueError(
                    "No Azure Speech subscription key found. "
                    "Set AZURE_SPEECH_KEY environment variable."
                )

            # Create speech config
            self.speech_config = SpeechConfig(
                subscription=self._subscription_key, region=self._region
            )

            # Set default output format
            self.speech_config.set_speech_synthesis_output_format(
                SpeechSynthesisOutputFormat.Audio16Khz32KBitRateMonoMp3
            )

            logger.info(f"Azure TTS initialized successfully. Region: {self._region}")

            self._initialized = True

        except Exception as e:
            logger.error(f"Failed to initialize Azure TTS: {e}")
            raise RuntimeError(f"Azure TTS initialization failed: {e}")

    async def synthesize(
        self,
        text: str,
        language: str,
        voice_id: Optional[str] = None,
        speaking_rate: Optional[float] = None,
        pitch: Optional[str] = None,
        output_format: str = "mp3",
        style: Optional[str] = None,
        style_degree: float = 1.0,
    ) -> Dict[str, Any]:
        """Synthesize speech using Azure Cognitive Services.

        Args:
            text: Text to synthesize
            language: Language code (e.g., 'en-US')
            voice_id: Specific voice name or None for default
            speaking_rate: Speaking rate (0.5 to 2.0)
            pitch: Voice pitch adjustment (e.g., "+10%", "-5%")
            output_format: Audio format (mp3, wav, ogg)
            style: Speaking style (e.g., "professional", "friendly")
            style_degree: Style intensity (0.01 to 2.0)

        Returns:
            Dictionary with audio_data, format, and metadata
        """
        if not self._initialized:
            await self.initialize()

        try:
            # Select voice
            voice_name = voice_id
            if not voice_name and language in self.VOICE_CONFIGS:
                voices = self.VOICE_CONFIGS[language]["voices"]
                if voices and isinstance(voices, list) and len(voices) > 0:
                    first_voice = voices[0]
                    if isinstance(first_voice, dict):
                        voice_name = first_voice.get("name")

            if not voice_name:
                # Default to first available voice for language
                voice_name = f"{language}-Neural"

            # Build SSML
            ssml = self._build_ssml(
                text=text,
                voice_name=voice_name,
                language=language,
                speaking_rate=speaking_rate,
                pitch=pitch,
                style=style,
                style_degree=style_degree,
            )

            # Configure output format
            output_format_enum = self._get_output_format(output_format)
            if not self.speech_config:
                raise RuntimeError("Azure TTS not initialized")
            self.speech_config.set_speech_synthesis_output_format(output_format_enum)

            # Create synthesizer with memory output
            audio_stream = AudioOutputStream()
            audio_config = AudioConfig(stream=audio_stream)

            synthesizer = SpeechSynthesizer(
                speech_config=self.speech_config, audio_config=audio_config
            )

            # Perform synthesis
            result = synthesizer.speak_ssml_async(ssml).get()

            if result.reason == ResultReason.SynthesizingAudioCompleted:
                # Get audio data
                audio_data = result.audio_data

                return {
                    "success": True,
                    "audio_data": audio_data,
                    "format": output_format,
                    "voice_used": voice_name,
                    "language": language,
                    "audio_length_bytes": len(audio_data),
                    "duration_ms": result.audio_duration.total_seconds() * 1000,
                    "synthesis_metadata": {
                        "engine": "azure_cognitive",
                        "neural_voice": True,
                        "speaking_rate": speaking_rate,
                        "pitch": pitch,
                        "style": style,
                    },
                }
            else:
                error_msg = f"Synthesis failed: {result.reason}"
                if result.reason == ResultReason.Canceled:
                    cancellation = result.cancellation_details
                    error_msg = f"Synthesis canceled: {cancellation.reason}"
                    if cancellation.reason == CancellationReason.Error:
                        error_msg += f" - {cancellation.error_details}"

                logger.error(error_msg)
                return {
                    "success": False,
                    "error": error_msg,
                    "engine": "azure_cognitive",
                }

        except Exception as e:
            logger.error(f"Azure TTS synthesis error: {e}")
            return {
                "success": False,
                "error": str(e),
                "engine": "azure_cognitive",
            }

    def _build_ssml(
        self,
        text: str,
        voice_name: str,
        language: str,
        speaking_rate: Optional[float] = None,
        pitch: Optional[str] = None,
        style: Optional[str] = None,
        style_degree: float = 1.0,
    ) -> str:
        """Build SSML markup for Azure TTS."""
        # Escape XML special characters
        text = text.replace("&", "&amp;")
        text = text.replace("<", "&lt;")
        text = text.replace(">", "&gt;")
        text = text.replace('"', "&quot;")
        text = text.replace("'", "&apos;")

        # Apply medical terminology substitutions
        for term, ssml_replacement in self.MEDICAL_SSML.items():
            import re

            text = re.sub(r"\b" + re.escape(term) + r"\b", ssml_replacement, text)

        # Get default speaking rate if not specified
        if speaking_rate is None and language in self.VOICE_CONFIGS:
            language_config = self.VOICE_CONFIGS[language]
            if isinstance(language_config, dict):
                rate_value = language_config.get("speaking_rate", "1.0")
                if isinstance(rate_value, (str, int, float)):
                    speaking_rate = float(rate_value)

        # Build prosody attributes
        prosody_attrs = []
        if speaking_rate:
            prosody_attrs.append(f'rate="{speaking_rate}"')
        if pitch:
            prosody_attrs.append(f'pitch="{pitch}"')

        # Build voice element
        voice_attrs = [f'name="{voice_name}"']

        # Build express-as element for style (if supported)
        express_as = ""
        if style and self._voice_supports_style(voice_name):
            express_as = (
                f'<mstts:express-as style="{style}" styledegree="{style_degree}">'
            )
            express_as_close = "</mstts:express-as>"
        else:
            express_as_close = ""

        # Build complete SSML
        ssml_parts = [
            '<speak version="1.0"',
            ' xmlns="http://www.w3.org/2001/10/synthesis"',
            ' xmlns:mstts="https://www.w3.org/2001/mstts"',
            f' xml:lang="{language}">',
            f'<voice {" ".join(voice_attrs)}>',
        ]

        if express_as:
            ssml_parts.append(express_as)

        if prosody_attrs:
            ssml_parts.append(f'<prosody {" ".join(prosody_attrs)}>')

        # Add text with medical emphasis
        processed_text = self._add_medical_emphasis(text)
        ssml_parts.append(processed_text)

        if prosody_attrs:
            ssml_parts.append("</prosody>")

        if express_as:
            ssml_parts.append(express_as_close)

        ssml_parts.extend(["</voice>", "</speak>"])

        return "".join(ssml_parts)

    def _add_medical_emphasis(self, text: str) -> str:
        """Add emphasis to important medical terms."""
        # Important medical terms that need emphasis
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
            "danger",
        ]

        for term in important_terms:
            import re

            pattern = re.compile(r"\b" + re.escape(term) + r"\b", re.IGNORECASE)
            text = pattern.sub(
                lambda m: f'<emphasis level="strong">{m.group(0)}</emphasis>', text
            )

        # Add pauses after important punctuation
        text = text.replace(". ", '. <break time="500ms"/> ')
        text = text.replace("! ", '! <break time="500ms"/> ')
        text = text.replace("? ", '? <break time="500ms"/> ')
        text = text.replace(": ", ': <break time="300ms"/> ')

        return text

    def _voice_supports_style(self, voice_name: str) -> bool:
        """Check if a voice supports style expressions."""
        # Azure neural voices that support styles
        style_supporting_voices = [
            "en-US-JennyNeural",
            "en-US-AriaNeural",
            "en-US-GuyNeural",
            "en-US-DavisNeural",
            "zh-CN-XiaoxiaoNeural",
            "zh-CN-YunyangNeural",
            "zh-CN-YunxiNeural",
            "zh-CN-YunyeNeural",
        ]
        return voice_name in style_supporting_voices

    def _get_output_format(self, format: str) -> SpeechSynthesisOutputFormat:
        """Get Azure output format enum from string."""
        format_mapping = {
            "mp3": SpeechSynthesisOutputFormat.Audio16Khz32KBitRateMonoMp3,
            "wav": SpeechSynthesisOutputFormat.Riff16Khz16BitMonoPcm,
            "ogg": SpeechSynthesisOutputFormat.Ogg16Khz16BitMonoOpus,
        }

        format_enum = format_mapping.get(format.lower())
        if not format_enum:
            logger.warning(f"Unknown format {format}, defaulting to MP3")
            format_enum = SpeechSynthesisOutputFormat.Audio16Khz32KBitRateMonoMp3

        return format_enum

    def get_available_voices(
        self, language: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get available voices for a language."""
        available_voices = []

        if language and language in self.VOICE_CONFIGS:
            voices = self.VOICE_CONFIGS[language]["voices"]
            if isinstance(voices, list):
                for voice in voices:
                    if isinstance(voice, dict):
                        voice_info = {
                            "voice_id": voice.get("name", ""),
                            "name": voice.get("name", ""),
                            "language": language,
                            "gender": voice.get("gender", "Unknown"),
                            "neural": True,
                            "styles": (
                                [voice.get("style")] if voice.get("style") else []
                            ),
                        }
                        available_voices.append(voice_info)
        else:
            # Return all configured voices
            for lang, config in self.VOICE_CONFIGS.items():
                voices = config.get("voices", [])
                if isinstance(voices, list):
                    for voice in voices:
                        if isinstance(voice, dict):
                            voice_info = {
                                "voice_id": voice.get("name", ""),
                                "name": voice.get("name", ""),
                                "language": lang,
                                "gender": voice.get("gender", "Unknown"),
                                "neural": True,
                                "styles": (
                                    [voice.get("style")] if voice.get("style") else []
                                ),
                            }
                            available_voices.append(voice_info)

        return available_voices

    def is_language_supported(self, language: str) -> bool:
        """Check if a language is supported."""
        return language in self.VOICE_CONFIGS

    async def cleanup(self) -> None:
        """Clean up resources."""
        self.speech_config = None
        self._initialized = False
        logger.info("Azure TTS client cleaned up")


# Global instance
azure_tts_engine = AzureTTSEngine()
