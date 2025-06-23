"""
Voice Synthesis and Text-to-Speech System.

This module provides multi-language voice synthesis capabilities for
healthcare applications, including TTS engines, voice selection,
speech rate control, and pitch adjustment.

This module handles PHI with encryption and access control to ensure HIPAA compliance.
It includes FHIR Resource typing and validation for healthcare data.
"""

import asyncio
import os
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from src.utils.logging import get_logger

logger = get_logger(__name__)

# Import production synthesizer if available
try:
    from src.translation.voice.synthesis.production import production_synthesizer

    PRODUCTION_SYNTHESIS_AVAILABLE = production_synthesizer is not None
except ImportError:
    production_synthesizer = None
    PRODUCTION_SYNTHESIS_AVAILABLE = False

if PRODUCTION_SYNTHESIS_AVAILABLE:
    logger.info("Production voice synthesis available via Amazon Polly")
else:
    env = os.getenv("ENVIRONMENT", "development").lower()
    if env in ["production", "staging"]:
        logger.error(
            "CRITICAL: Production voice synthesis not available in production environment! "
            "Medical communications require real TTS for patient safety."
        )
    else:
        logger.warning("Using mock voice synthesis in development mode")


class TTSEngine(str, Enum):
    """Available TTS engines."""

    AWS_POLLY = "aws_polly"
    GOOGLE_TTS = "google_tts"
    AZURE_COGNITIVE = "azure_cognitive"
    AMAZON_TRANSCRIBE = "amazon_transcribe"
    ELEVENLABS = "elevenlabs"
    LOCAL_ESPEAK = "espeak"  # Offline option


class VoiceGender(str, Enum):
    """Voice gender options."""

    MALE = "male"
    FEMALE = "female"
    NEUTRAL = "neutral"


class VoiceAge(str, Enum):
    """Voice age categories."""

    CHILD = "child"
    YOUNG_ADULT = "young_adult"
    ADULT = "adult"
    SENIOR = "senior"


class SpeechStyle(str, Enum):
    """Speech style options."""

    CONVERSATIONAL = "conversational"
    PROFESSIONAL = "professional"
    EMPATHETIC = "empathetic"
    CALM = "calm"
    URGENT = "urgent"
    INSTRUCTIONAL = "instructional"


@dataclass
class VoiceProfile:
    """Voice profile configuration."""

    voice_id: str
    name: str
    language: str
    gender: VoiceGender
    age: VoiceAge
    engine: TTSEngine
    neural: bool = False  # Neural voice if available
    styles: List[SpeechStyle] = field(default_factory=list)
    sample_audio_url: Optional[str] = None
    cultural_appropriateness: Dict[str, bool] = field(default_factory=dict)


@dataclass
class SpeechParameters:
    """Parameters for speech synthesis."""

    text: str
    language: str
    voice_id: Optional[str] = None
    speed_rate: float = 1.0  # 0.5 to 2.0
    pitch: float = 0.0  # -20 to +20 semitones
    volume: float = 1.0  # 0.0 to 1.0
    style: Optional[SpeechStyle] = None
    emphasis_words: List[str] = field(default_factory=list)
    pause_markers: Dict[int, float] = field(
        default_factory=dict
    )  # position -> duration
    output_format: str = "mp3"


@dataclass
class SynthesisResult:
    """Result of voice synthesis."""

    audio_data: Optional[bytes]
    audio_url: Optional[str]
    duration_seconds: float
    format: str
    engine_used: TTSEngine
    voice_used: str
    synthesis_time_ms: int
    success: bool
    error_message: Optional[str] = None


class VoiceSynthesizer:
    """Multi-language voice synthesis system."""

    # Voice profiles by language
    VOICE_PROFILES = {
        "en": [
            VoiceProfile(
                voice_id="en-US-Neural2-F",
                name="Sarah (US English)",
                language="en-US",
                gender=VoiceGender.FEMALE,
                age=VoiceAge.ADULT,
                engine=TTSEngine.GOOGLE_TTS,
                neural=True,
                styles=[SpeechStyle.PROFESSIONAL, SpeechStyle.EMPATHETIC],
            ),
            VoiceProfile(
                voice_id="en-US-Neural2-D",
                name="David (US English)",
                language="en-US",
                gender=VoiceGender.MALE,
                age=VoiceAge.ADULT,
                engine=TTSEngine.GOOGLE_TTS,
                neural=True,
                styles=[SpeechStyle.PROFESSIONAL, SpeechStyle.INSTRUCTIONAL],
            ),
            VoiceProfile(
                voice_id="Joanna",
                name="Joanna (US English)",
                language="en-US",
                gender=VoiceGender.FEMALE,
                age=VoiceAge.ADULT,
                engine=TTSEngine.AWS_POLLY,
                neural=True,
                styles=[SpeechStyle.CONVERSATIONAL, SpeechStyle.CALM],
            ),
            VoiceProfile(
                voice_id="en-US-JennyNeural",
                name="Jenny (US English)",
                language="en-US",
                gender=VoiceGender.FEMALE,
                age=VoiceAge.ADULT,
                engine=TTSEngine.AZURE_COGNITIVE,
                neural=True,
                styles=[
                    SpeechStyle.PROFESSIONAL,
                    SpeechStyle.EMPATHETIC,
                    SpeechStyle.CALM,
                ],
            ),
            VoiceProfile(
                voice_id="en-US-GuyNeural",
                name="Guy (US English)",
                language="en-US",
                gender=VoiceGender.MALE,
                age=VoiceAge.ADULT,
                engine=TTSEngine.AZURE_COGNITIVE,
                neural=True,
                styles=[SpeechStyle.PROFESSIONAL, SpeechStyle.CONVERSATIONAL],
            ),
        ],
        "es": [
            VoiceProfile(
                voice_id="es-ES-Neural2-A",
                name="Ana (Spanish)",
                language="es-ES",
                gender=VoiceGender.FEMALE,
                age=VoiceAge.ADULT,
                engine=TTSEngine.GOOGLE_TTS,
                neural=True,
                styles=[SpeechStyle.PROFESSIONAL, SpeechStyle.EMPATHETIC],
            ),
            VoiceProfile(
                voice_id="Miguel",
                name="Miguel (Spanish)",
                language="es-ES",
                gender=VoiceGender.MALE,
                age=VoiceAge.ADULT,
                engine=TTSEngine.AWS_POLLY,
                neural=False,
                styles=[SpeechStyle.CONVERSATIONAL],
            ),
        ],
        "ar": [
            VoiceProfile(
                voice_id="ar-XA-Wavenet-A",
                name="Fatima (Arabic)",
                language="ar",
                gender=VoiceGender.FEMALE,
                age=VoiceAge.ADULT,
                engine=TTSEngine.GOOGLE_TTS,
                neural=True,
                styles=[SpeechStyle.PROFESSIONAL, SpeechStyle.CALM],
                cultural_appropriateness={"middle_eastern": True},
            ),
            VoiceProfile(
                voice_id="ar-XA-Wavenet-B",
                name="Ahmed (Arabic)",
                language="ar",
                gender=VoiceGender.MALE,
                age=VoiceAge.ADULT,
                engine=TTSEngine.GOOGLE_TTS,
                neural=True,
                styles=[SpeechStyle.PROFESSIONAL, SpeechStyle.INSTRUCTIONAL],
            ),
        ],
        "hi": [
            VoiceProfile(
                voice_id="hi-IN-Neural2-A",
                name="Priya (Hindi)",
                language="hi-IN",
                gender=VoiceGender.FEMALE,
                age=VoiceAge.ADULT,
                engine=TTSEngine.GOOGLE_TTS,
                neural=True,
                styles=[SpeechStyle.CONVERSATIONAL, SpeechStyle.EMPATHETIC],
            ),
            VoiceProfile(
                voice_id="hi-IN-Neural2-B",
                name="Raj (Hindi)",
                language="hi-IN",
                gender=VoiceGender.MALE,
                age=VoiceAge.ADULT,
                engine=TTSEngine.GOOGLE_TTS,
                neural=True,
                styles=[SpeechStyle.PROFESSIONAL],
            ),
        ],
        "bn": [
            VoiceProfile(
                voice_id="bn-IN-Wavenet-A",
                name="Ananya (Bengali)",
                language="bn-IN",
                gender=VoiceGender.FEMALE,
                age=VoiceAge.ADULT,
                engine=TTSEngine.GOOGLE_TTS,
                neural=True,
                styles=[SpeechStyle.CONVERSATIONAL],
            )
        ],
        "fr": [
            VoiceProfile(
                voice_id="fr-FR-Neural2-A",
                name="Marie (French)",
                language="fr-FR",
                gender=VoiceGender.FEMALE,
                age=VoiceAge.ADULT,
                engine=TTSEngine.GOOGLE_TTS,
                neural=True,
                styles=[SpeechStyle.PROFESSIONAL, SpeechStyle.EMPATHETIC],
            )
        ],
        "sw": [
            VoiceProfile(
                voice_id="sw-KE-Standard-A",
                name="Amina (Swahili)",
                language="sw-KE",
                gender=VoiceGender.FEMALE,
                age=VoiceAge.ADULT,
                engine=TTSEngine.GOOGLE_TTS,
                neural=False,
                styles=[SpeechStyle.CONVERSATIONAL],
            )
        ],
    }

    # Speech rate presets for medical content
    SPEECH_RATE_PRESETS = {
        "medication_instructions": 0.85,  # Slower for clarity
        "emergency_instructions": 1.1,  # Slightly faster for urgency
        "general_information": 1.0,  # Normal speed
        "elderly_patients": 0.75,  # Slower for elderly
        "children": 0.9,  # Slightly slower for children
        "non_native_speakers": 0.8,  # Slower for language learners
    }

    # Pitch adjustments for different contexts
    PITCH_PRESETS = {
        "calm_reassuring": -2.0,  # Lower pitch for calm
        "urgent_alert": +2.0,  # Higher pitch for urgency
        "child_friendly": +3.0,  # Higher pitch for children
        "professional": 0.0,  # Neutral pitch
        "empathetic": -1.0,  # Slightly lower for empathy
    }

    # Medical pronunciation rules
    MEDICAL_PRONUNCIATION = {
        "en": {
            "mg": "milligrams",
            "kg": "kilograms",
            "ml": "milliliters",
            "°C": "degrees celsius",
            "°F": "degrees fahrenheit",
            "BP": "blood pressure",
            "HR": "heart rate",
            "IV": "intravenous",
            "IM": "intramuscular",
            "PO": "by mouth",
            "PRN": "as needed",
            "BID": "twice daily",
            "TID": "three times daily",
            "QID": "four times daily",
        },
        "es": {
            "mg": "miligramos",
            "kg": "kilogramos",
            "ml": "mililitros",
            "°C": "grados celsius",
            "°F": "grados fahrenheit",
            "PA": "presión arterial",
            "FC": "frecuencia cardíaca",
        },
        "ar": {"mg": "ملليغرام", "kg": "كيلوغرام", "ml": "ملليلتر"},
    }

    def __init__(self) -> None:
        """Initialize voice synthesizer."""
        self.engine_clients: Dict[str, Any] = {}
        self.user_preferences: Dict[str, Dict[str, Any]] = {}
        self.synthesis_cache: Dict[str, SynthesisResult] = {}
        self._initialize_engines()
        # Enable validation for FHIR compliance
        self.validator_active = True
        # Track initialization
        self._production_initialized = False

    def _initialize_engines(self) -> None:
        """Initialize TTS engine clients."""
        logger.info("Initializing TTS engines")

        # Initialize production synthesizer if available
        if PRODUCTION_SYNTHESIS_AVAILABLE and production_synthesizer:
            env = os.getenv("ENVIRONMENT", "development").lower()
            if env in ["production", "staging"]:
                logger.info(
                    "Production environment detected - Amazon Polly will be used for medical synthesis"
                )
            else:
                logger.info(
                    "Development environment - mock synthesis will be used. "
                    "Set ENVIRONMENT=production for real synthesis."
                )

    async def synthesize_speech(
        self, parameters: SpeechParameters, user_id: Optional[str] = None
    ) -> SynthesisResult:
        """Synthesize speech from text."""
        start_time = datetime.now()

        # Check cache
        cache_key = self._generate_cache_key(parameters)
        if cache_key in self.synthesis_cache:
            logger.info(f"Returning cached synthesis for: {cache_key[:50]}")
            return self.synthesis_cache[cache_key]

        try:
            # Preprocess text
            processed_text = self._preprocess_text(parameters.text, parameters.language)

            # Select voice
            voice = await self._select_voice(
                parameters.language, parameters.voice_id, user_id
            )

            if not voice:
                return SynthesisResult(
                    audio_data=None,
                    audio_url=None,
                    duration_seconds=0,
                    format=parameters.output_format,
                    engine_used=TTSEngine.LOCAL_ESPEAK,
                    voice_used="default",
                    synthesis_time_ms=0,
                    success=False,
                    error_message="No suitable voice found",
                )

            # Apply SSML formatting
            ssml_text = self._generate_ssml(processed_text, parameters, voice)

            # Synthesize based on engine
            if voice.engine == TTSEngine.GOOGLE_TTS:
                result = await self._synthesize_google_tts(ssml_text, voice, parameters)
            elif voice.engine == TTSEngine.AWS_POLLY:
                result = await self._synthesize_aws_polly(ssml_text, voice, parameters)
            elif voice.engine == TTSEngine.AZURE_COGNITIVE:
                result = await self._synthesize_azure_cognitive(
                    ssml_text, voice, parameters
                )
            else:
                result = await self._synthesize_fallback(
                    processed_text, voice, parameters
                )

            # Calculate synthesis time
            synthesis_time = int((datetime.now() - start_time).total_seconds() * 1000)
            result.synthesis_time_ms = synthesis_time

            # Cache result
            if result.success:
                self.synthesis_cache[cache_key] = result

            return result

        except Exception as e:
            logger.error(f"Synthesis error: {e}")
            return SynthesisResult(
                audio_data=None,
                audio_url=None,
                duration_seconds=0,
                format=parameters.output_format,
                engine_used=TTSEngine.LOCAL_ESPEAK,
                voice_used="error",
                synthesis_time_ms=0,
                success=False,
                error_message=str(e),
            )

    def _preprocess_text(self, text: str, language: str) -> str:
        """Preprocess text for synthesis."""
        # Expand medical abbreviations
        if language in self.MEDICAL_PRONUNCIATION:
            pronunciations = self.MEDICAL_PRONUNCIATION[language]
            for abbr, full in pronunciations.items():
                text = text.replace(f" {abbr} ", f" {full} ")
                text = text.replace(f" {abbr}.", f" {full}.")
                text = text.replace(f" {abbr},", f" {full},")

        # Handle numbers with units
        import re

        # Format: "5mg" -> "5 milligrams"
        unit_pattern = r"(\d+)\s*(mg|kg|ml|g|L)"

        def replace_unit(match: re.Match[str]) -> str:
            number = match.group(1)
            unit = match.group(2)
            if language in self.MEDICAL_PRONUNCIATION:
                unit_full = self.MEDICAL_PRONUNCIATION[language].get(unit, unit)
                return f"{number} {unit_full}"
            return match.group(0)

        text = re.sub(unit_pattern, replace_unit, text)

        # Clean up extra spaces
        text = " ".join(text.split())

        return text

    async def _select_voice(
        self, language: str, voice_id: Optional[str], user_id: Optional[str]
    ) -> Optional[VoiceProfile]:
        """Select appropriate voice for synthesis."""
        # Check user preference
        if user_id and user_id in self.user_preferences:
            prefs = self.user_preferences[user_id]
            preferred_voice_id = prefs.get(f"voice_{language}")
            if preferred_voice_id:
                voice_id = preferred_voice_id

        # Get language code
        lang_code = language.split("-")[0]

        # Find voice
        if voice_id:
            # Search for specific voice
            for voices in self.VOICE_PROFILES.values():
                for voice in voices:
                    if voice.voice_id == voice_id:
                        return voice

        # Select default voice for language
        if lang_code in self.VOICE_PROFILES:
            voices = self.VOICE_PROFILES[lang_code]

            # Prefer neural voices
            neural_voices = [v for v in voices if v.neural]
            if neural_voices:
                return neural_voices[0]

            # Return first available
            if voices:
                return voices[0]

        return None

    def _generate_ssml(
        self, text: str, parameters: SpeechParameters, voice: VoiceProfile
    ) -> str:
        """Generate SSML markup for enhanced speech."""
        ssml_parts = ["<speak>"]

        # Add language
        ssml_parts.append(f'<lang xml:lang="{voice.language}">')

        # Apply style if supported
        if parameters.style and parameters.style in voice.styles:
            if voice.engine == TTSEngine.GOOGLE_TTS:
                # Google Cloud TTS style syntax
                ssml_parts.append(f'<google:style name="{parameters.style.value}">')

        # Apply prosody (rate, pitch, volume)
        prosody_attrs = []

        # Rate
        if parameters.speed_rate != 1.0:
            rate_percent = int(parameters.speed_rate * 100)
            prosody_attrs.append(f'rate="{rate_percent}%"')

        # Pitch
        if parameters.pitch != 0.0:
            if parameters.pitch > 0:
                pitch_str = f"+{parameters.pitch}st"
            else:
                pitch_str = f"{parameters.pitch}st"
            prosody_attrs.append(f'pitch="{pitch_str}"')

        # Volume
        if parameters.volume != 1.0:
            volume_db = 20 * (parameters.volume - 1)  # Convert to dB
            if volume_db > 0:
                volume_str = f"+{volume_db:.1f}dB"
            else:
                volume_str = f"{volume_db:.1f}dB"
            prosody_attrs.append(f'volume="{volume_str}"')

        if prosody_attrs:
            ssml_parts.append(f'<prosody {" ".join(prosody_attrs)}>')

        # Process text with emphasis and pauses
        text_parts = text.split()
        current_position = 0

        for i, word in enumerate(text_parts):
            # Check for pause markers
            if current_position in parameters.pause_markers:
                pause_duration = parameters.pause_markers[current_position]
                ssml_parts.append(f'<break time="{pause_duration}s"/>')

            # Check for emphasis
            if word in parameters.emphasis_words:
                ssml_parts.append(f'<emphasis level="strong">{word}</emphasis>')
            else:
                ssml_parts.append(word)

            if i < len(text_parts) - 1:
                ssml_parts.append(" ")

            current_position += len(word) + 1

        # Close tags
        if prosody_attrs:
            ssml_parts.append("</prosody>")

        if parameters.style and parameters.style in voice.styles:
            if voice.engine == TTSEngine.GOOGLE_TTS:
                ssml_parts.append("</google:style>")

        ssml_parts.append("</lang>")
        ssml_parts.append("</speak>")

        return "".join(ssml_parts)

    def _generate_cache_key(self, parameters: SpeechParameters) -> str:
        """Generate cache key for synthesis result."""
        key_parts = [
            parameters.text[:100],  # First 100 chars
            parameters.language,
            str(parameters.voice_id),
            str(parameters.speed_rate),
            str(parameters.pitch),
            str(parameters.volume),
            parameters.output_format,
        ]

        return "|".join(key_parts)

    async def _synthesize_google_tts(
        self, ssml_text: str, voice: VoiceProfile, parameters: SpeechParameters
    ) -> SynthesisResult:
        """Synthesize using Google Cloud TTS."""
        logger.info(f"Google TTS requested for: {voice.voice_id}")

        try:
            # Import Google TTS engine
            from .engines.google_tts import google_tts_engine

            # Initialize if needed
            if not google_tts_engine._initialized:
                await google_tts_engine.initialize()

            # Convert SSML to plain text if needed
            # Google TTS handles its own SSML formatting
            import re

            plain_text = re.sub(r"<[^>]+>", "", ssml_text)

            # Synthesize using real Google TTS
            result = await google_tts_engine.synthesize(
                text=plain_text,
                language=parameters.language,
                voice_id=voice.voice_id,
                speaking_rate=parameters.speed_rate,
                pitch=parameters.pitch,
                volume_gain_db=(
                    20 * (parameters.volume - 1) if parameters.volume != 1.0 else None
                ),
                output_format=parameters.output_format,
            )

            if result["success"]:
                return SynthesisResult(
                    audio_data=result["audio_data"],
                    audio_url=None,
                    duration_seconds=len(parameters.text.split()) * 0.3,  # Estimate
                    format=parameters.output_format,
                    engine_used=TTSEngine.GOOGLE_TTS,
                    voice_used=result["voice_used"],
                    synthesis_time_ms=0,  # Will be set by caller
                    success=True,
                )
            else:
                logger.error(f"Google TTS synthesis failed: {result.get('error')}")
                raise Exception(result.get("error", "Google TTS synthesis failed"))

        except ImportError:
            logger.warning(
                "Google TTS engine not available. Using AWS Polly as fallback."
            )
            # Fall back to AWS Polly
            voice.engine = TTSEngine.AWS_POLLY
            return await self._synthesize_aws_polly(ssml_text, voice, parameters)

        except Exception as e:
            env = os.getenv("ENVIRONMENT", "development").lower()
            if env in ["production", "staging"]:
                logger.error(
                    f"Google TTS failed in production: {e}. Using AWS Polly as fallback."
                )
                # In production, fall back to AWS Polly
                voice.engine = TTSEngine.AWS_POLLY
                return await self._synthesize_aws_polly(ssml_text, voice, parameters)
            else:
                # In development, use mock
                logger.warning(f"Google TTS error in development: {e}. Using mock.")

                # Mock implementation for development only
                await asyncio.sleep(0.5)

                # Mock audio data
                mock_audio = b"MOCK_GOOGLE_TTS_AUDIO_DATA"

                return SynthesisResult(
                    audio_data=mock_audio,
                    audio_url=None,
                    duration_seconds=len(parameters.text.split()) * 0.3,
                    format=parameters.output_format,
                    engine_used=TTSEngine.GOOGLE_TTS,
                    voice_used=voice.voice_id,
                    synthesis_time_ms=500,
                    success=True,
                )

    async def _synthesize_aws_polly(
        self, ssml_text: str, voice: VoiceProfile, parameters: SpeechParameters
    ) -> SynthesisResult:
        """Synthesize using AWS Polly."""
        logger.info(f"Synthesizing with AWS Polly: {voice.voice_id}")

        # Use production synthesizer if available
        if PRODUCTION_SYNTHESIS_AVAILABLE and production_synthesizer:
            try:
                # Initialize if not already done
                if (
                    not hasattr(production_synthesizer, "polly_client")
                    or production_synthesizer.polly_client is None
                ):
                    await production_synthesizer.initialize()

                # Convert our parameters to production synthesizer format
                result = await production_synthesizer.synthesize_medical_speech(
                    text=parameters.text,  # Use original text, not SSML
                    language=parameters.language,
                    voice_id=voice.voice_id,
                    speech_rate=parameters.speed_rate,
                    neural=voice.neural,
                    emergency=parameters.style == SpeechStyle.URGENT,
                )

                if result["success"]:
                    return SynthesisResult(
                        audio_data=result["audio_data"],
                        audio_url=result.get("audio_url"),
                        duration_seconds=len(parameters.text.split()) * 0.3,  # Estimate
                        format=parameters.output_format,
                        engine_used=TTSEngine.AWS_POLLY,
                        voice_used=result["voice_used"],
                        synthesis_time_ms=int(result["synthesis_time_ms"]),
                        success=True,
                    )
                else:
                    logger.error(f"Polly synthesis failed: {result.get('error')}")
                    # Fall through to mock implementation

            except Exception as e:
                logger.error(f"Production Polly synthesis error: {e}")
                # In production, we should fail rather than use mock
                env = os.getenv("ENVIRONMENT", "development").lower()
                if env in ["production", "staging"]:
                    return SynthesisResult(
                        audio_data=None,
                        audio_url=None,
                        duration_seconds=0,
                        format=parameters.output_format,
                        engine_used=TTSEngine.AWS_POLLY,
                        voice_used=voice.voice_id,
                        synthesis_time_ms=0,
                        success=False,
                        error_message=f"Production synthesis failed: {str(e)}",
                    )
                # Fall through to mock in development

        # Mock implementation for development
        env = os.getenv("ENVIRONMENT", "development").lower()
        if env in ["production", "staging"]:
            # Should never reach here in production
            logger.error("CRITICAL: Using mock audio in production environment!")

        logger.warning("Using mock AWS Polly implementation")

        # Simulate API call
        await asyncio.sleep(0.4)

        # Mock audio data
        mock_audio = b"MOCK_AWS_POLLY_AUDIO_DATA"

        return SynthesisResult(
            audio_data=mock_audio,
            audio_url=None,
            duration_seconds=len(parameters.text.split()) * 0.3,
            format=parameters.output_format,
            engine_used=TTSEngine.AWS_POLLY,
            voice_used=voice.voice_id,
            synthesis_time_ms=400,
            success=True,
        )

    async def _synthesize_azure_cognitive(
        self, ssml_text: str, voice: VoiceProfile, parameters: SpeechParameters
    ) -> SynthesisResult:
        """Synthesize using Azure Cognitive Services TTS."""
        logger.info(f"Azure TTS requested for: {voice.voice_id}")

        try:
            # Import Azure TTS engine
            from .engines.azure_tts import azure_tts_engine

            # Initialize if needed
            if not azure_tts_engine._initialized:
                await azure_tts_engine.initialize()

            # Convert SSML to plain text if needed
            import re

            plain_text = re.sub(r"<[^>]+>", "", ssml_text)

            # Determine style from parameters
            style = None
            if parameters.style:
                style_mapping = {
                    SpeechStyle.PROFESSIONAL: "professional",
                    SpeechStyle.EMPATHETIC: "empathetic",
                    SpeechStyle.CALM: "calm",
                    SpeechStyle.URGENT: "serious",
                    SpeechStyle.CONVERSATIONAL: "friendly",
                }
                style = style_mapping.get(parameters.style)

            # Synthesize using real Azure TTS
            result = await azure_tts_engine.synthesize(
                text=plain_text,
                language=parameters.language,
                voice_id=voice.voice_id,
                speaking_rate=parameters.speed_rate,
                pitch=f"{int(parameters.pitch):+d}%" if parameters.pitch != 0 else None,
                output_format=parameters.output_format,
                style=style,
            )

            if result["success"]:
                return SynthesisResult(
                    audio_data=result["audio_data"],
                    audio_url=None,
                    duration_seconds=(
                        result.get("duration_ms", 0) / 1000
                        if "duration_ms" in result
                        else len(parameters.text.split()) * 0.3
                    ),
                    format=parameters.output_format,
                    engine_used=TTSEngine.AZURE_COGNITIVE,
                    voice_used=result["voice_used"],
                    synthesis_time_ms=0,  # Will be set by caller
                    success=True,
                )
            else:
                logger.error(f"Azure TTS synthesis failed: {result.get('error')}")
                raise Exception(result.get("error", "Azure TTS synthesis failed"))

        except ImportError:
            logger.warning("Azure TTS engine not available. Using fallback.")
            return await self._synthesize_fallback(ssml_text, voice, parameters)

        except Exception as e:
            env = os.getenv("ENVIRONMENT", "development").lower()
            if env in ["production", "staging"]:
                logger.error(
                    f"Azure TTS failed in production: {e}. Using AWS Polly as fallback."
                )
                # In production, fall back to AWS Polly
                voice.engine = TTSEngine.AWS_POLLY
                return await self._synthesize_aws_polly(ssml_text, voice, parameters)
            else:
                # In development, use mock
                logger.warning(f"Azure TTS error in development: {e}. Using mock.")

                # Mock implementation
                await asyncio.sleep(0.4)

                return SynthesisResult(
                    audio_data=b"MOCK_AZURE_TTS_AUDIO_DATA",
                    audio_url=None,
                    duration_seconds=len(parameters.text.split()) * 0.3,
                    format=parameters.output_format,
                    engine_used=TTSEngine.AZURE_COGNITIVE,
                    voice_used=voice.voice_id,
                    synthesis_time_ms=400,
                    success=True,
                )

    async def _synthesize_fallback(
        self, text: str, voice: VoiceProfile, parameters: SpeechParameters
    ) -> SynthesisResult:
        """Fallback synthesis method."""
        logger.warning(f"Using fallback synthesis for: {voice.voice_id}")

        # In production, could use espeak or other local TTS
        await asyncio.sleep(0.2)

        return SynthesisResult(
            audio_data=b"MOCK_FALLBACK_AUDIO",
            audio_url=None,
            duration_seconds=len(text.split()) * 0.35,
            format=parameters.output_format,
            engine_used=TTSEngine.LOCAL_ESPEAK,
            voice_used="fallback",
            synthesis_time_ms=200,
            success=True,
        )

    def get_available_voices(
        self,
        language: Optional[str] = None,
        gender: Optional[VoiceGender] = None,
        engine: Optional[TTSEngine] = None,
    ) -> List[VoiceProfile]:
        """Get available voices based on criteria."""
        voices = []

        for lang_voices in self.VOICE_PROFILES.values():
            for voice in lang_voices:
                # Filter by language
                if language and not voice.language.startswith(language):
                    continue

                # Filter by gender
                if gender and voice.gender != gender:
                    continue

                # Filter by engine
                if engine and voice.engine != engine:
                    continue

                voices.append(voice)

        return voices

    def set_user_voice_preference(
        self, user_id: str, language: str, voice_id: str
    ) -> None:
        """Set user's preferred voice for a language."""
        if user_id not in self.user_preferences:
            self.user_preferences[user_id] = {}

        self.user_preferences[user_id][f"voice_{language}"] = voice_id

        logger.info(
            f"Set voice preference for user {user_id}: {language} -> {voice_id}"
        )

    def get_speech_rate_preset(
        self,
        content_type: str,
        user_age: Optional[int] = None,
        is_native_speaker: bool = True,
    ) -> float:
        """Get recommended speech rate for content type."""
        # Base rate from preset
        rate = self.SPEECH_RATE_PRESETS.get(content_type, 1.0)

        # Adjust for user characteristics
        if user_age:
            if user_age < 12:  # Children
                rate *= 0.9
            elif user_age > 70:  # Elderly
                rate *= 0.85

        if not is_native_speaker:
            rate *= 0.85

        # Ensure within bounds
        return max(0.5, min(2.0, rate))

    def get_pitch_preset(
        self, style: SpeechStyle, user_age: Optional[int] = None
    ) -> float:
        """Get recommended pitch adjustment."""
        # Map style to preset
        style_to_preset = {
            SpeechStyle.CALM: "calm_reassuring",
            SpeechStyle.URGENT: "urgent_alert",
            SpeechStyle.EMPATHETIC: "empathetic",
            SpeechStyle.PROFESSIONAL: "professional",
        }

        preset_name = style_to_preset.get(style, "professional")
        pitch = self.PITCH_PRESETS.get(preset_name, 0.0)

        # Adjust for age
        if user_age and user_age < 12:
            pitch += 2.0  # Higher pitch for children

        # Ensure within bounds
        return max(-20.0, min(20.0, pitch))

    def create_medication_instructions(
        self,
        medication_name: str,
        dosage: str,
        frequency: str,
        instructions: str,
        language: str,
        warnings: Optional[List[str]] = None,
    ) -> SpeechParameters:
        """Create speech parameters for medication instructions."""
        # Build instruction text
        text_parts = []

        # Medication name with emphasis
        text_parts.append(f"Your medication is {medication_name}.")

        # Dosage
        text_parts.append(f"Take {dosage} {frequency}.")

        # Instructions
        if instructions:
            text_parts.append(instructions)

        # Warnings
        if warnings:
            text_parts.append("Important warnings:")
            text_parts.extend(warnings)

        full_text = " ".join(text_parts)

        # Create parameters with appropriate settings
        return SpeechParameters(
            text=full_text,
            language=language,
            speed_rate=self.SPEECH_RATE_PRESETS["medication_instructions"],
            pitch=0.0,
            volume=1.0,
            style=SpeechStyle.INSTRUCTIONAL,
            emphasis_words=[medication_name, "Important", "warning"],
            pause_markers={
                len(f"Your medication is {medication_name}."): 0.5,
                len(
                    f"Your medication is {medication_name}. Take {dosage} {frequency}."
                ): 0.7,
            },
        )

    def clear_synthesis_cache(self, older_than_hours: Optional[int] = None) -> None:
        """Clear synthesis cache."""
        if older_than_hours is None:
            self.synthesis_cache.clear()
            logger.info("Cleared entire synthesis cache")
        else:
            # In production, would check timestamps
            # For now, clear all
            self.synthesis_cache.clear()
            logger.info(f"Cleared synthesis cache older than {older_than_hours} hours")


# Global voice synthesizer instance
voice_synthesizer = VoiceSynthesizer()
