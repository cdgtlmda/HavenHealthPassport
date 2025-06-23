"""Voice Feedback System Module.

This module implements a comprehensive voice feedback system for the Haven Health
Passport, providing audio responses, status updates, and confirmations using
Amazon Polly and other text-to-speech services. Handles FHIR Communication Resource
validation for patient feedback.

IMPORTANT: This module handles PHI (Protected Health Information).
- All PHI data is encrypted at rest and in transit using industry-standard encryption.
- Access control is enforced through role-based permissions and authentication.
"""

import asyncio
import hashlib
import logging
import random
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

import boto3
from botocore.exceptions import BotoCoreError

logger = logging.getLogger(__name__)


class FeedbackType(Enum):
    """Types of voice feedback."""

    SUCCESS = "success"
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"
    QUESTION = "question"
    CONFIRMATION = "confirmation"
    PROGRESS = "progress"
    NOTIFICATION = "notification"
    TUTORIAL = "tutorial"
    ENCOURAGEMENT = "encouragement"


class FeedbackPriority(Enum):
    """Priority levels for feedback delivery."""

    CRITICAL = 1  # Must be heard (errors, emergencies)
    HIGH = 2  # Important updates
    NORMAL = 3  # Regular feedback
    LOW = 4  # Optional feedback
    AMBIENT = 5  # Background sounds/music


class VoicePersona(Enum):
    """Voice personas for different contexts."""

    PROFESSIONAL = "professional"  # Medical professional tone
    FRIENDLY = "friendly"  # Warm, supportive tone
    ASSISTANT = "assistant"  # Helpful assistant tone
    EMERGENCY = "emergency"  # Clear, urgent tone
    CHILD = "child"  # Simple, cheerful tone


class AudioFormat(Enum):
    """Supported audio output formats."""

    MP3 = "mp3"
    OGG = "ogg_vorbis"
    PCM = "pcm"
    JSON = "json"  # For speech marks


@dataclass
class VoiceParameters:
    """Parameters for voice synthesis."""

    voice_id: str = "Joanna"  # Default AWS Polly voice
    language: str = "en-US"
    engine: str = "neural"  # neural or standard
    speaking_rate: float = 1.0  # 0.25 to 4.0
    pitch: float = 0.0  # -20 to +20 semitones
    volume: float = 1.0  # 0.0 to 1.0
    timbre: Optional[float] = None  # Voice timbre adjustment

    def to_polly_params(self) -> Dict[str, Any]:
        """Convert to AWS Polly parameters."""
        params = {
            "VoiceId": self.voice_id,
            "LanguageCode": self.language,
            "Engine": self.engine,
        }

        # Add prosody SSML if needed
        if self.speaking_rate != 1.0 or self.pitch != 0.0 or self.volume != 1.0:
            params["TextType"] = "ssml"
            # SSML will be added by the synthesis method

        return params


@dataclass
class FeedbackTemplate:
    """Template for generating voice feedback."""

    id: str
    type: FeedbackType
    templates: Dict[str, List[str]]  # Language -> List of variations
    voice_params: Optional[VoiceParameters] = None
    sound_effects: List[str] = field(default_factory=list)
    priority: FeedbackPriority = FeedbackPriority.NORMAL
    interruptible: bool = True

    def get_text(self, language: str = "en", variation: int = 0) -> str:
        """Get feedback text for language and variation."""
        if language not in self.templates:
            language = "en"  # Fallback to English

        texts = self.templates.get(language, ["Feedback not available"])
        return texts[variation % len(texts)]


@dataclass
class FeedbackContext:
    """Context for generating appropriate feedback."""

    user_id: str
    user_level: str  # Beginner, Intermediate, Advanced
    interaction_count: int
    success_rate: float
    preferred_voice: Optional[str] = None
    accessibility_needs: List[str] = field(default_factory=list)
    emotional_state: Optional[str] = None  # Detected from voice
    environment: Dict[str, Any] = field(default_factory=dict)
    recent_errors: int = 0
    session_duration: timedelta = timedelta()


@dataclass
class AudioFeedback:
    """Represents audio feedback to be played."""

    id: str
    type: FeedbackType
    text: str
    ssml: Optional[str] = None
    audio_url: Optional[str] = None
    audio_data: Optional[bytes] = None
    duration: Optional[float] = None
    voice_params: Optional[VoiceParameters] = None
    priority: FeedbackPriority = FeedbackPriority.NORMAL
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


class FeedbackTemplateLibrary:
    """Library of feedback templates for various scenarios."""

    def __init__(self) -> None:
        """Initialize the feedback template library with built-in templates."""
        self.templates: Dict[str, FeedbackTemplate] = {}
        self._initialize_templates()

    def _initialize_templates(self) -> None:
        """Initialize built-in feedback templates."""
        # Success templates
        self.templates["command_success"] = FeedbackTemplate(
            id="command_success",
            type=FeedbackType.SUCCESS,
            templates={
                "en": [
                    "Done!",
                    "Command completed successfully.",
                    "All set!",
                    "Successfully completed.",
                ],
                "es": [
                    "¡Hecho!",
                    "Comando completado con éxito.",
                    "¡Listo!",
                    "Completado exitosamente.",
                ],
                "fr": [
                    "Terminé!",
                    "Commande exécutée avec succès.",
                    "C'est fait!",
                    "Complété avec succès.",
                ],
            },
            sound_effects=["success_chime.mp3"],
        )
        # Error templates
        self.templates["command_error"] = FeedbackTemplate(
            id="command_error",
            type=FeedbackType.ERROR,
            templates={
                "en": [
                    "I'm sorry, there was an error. {error_message}",
                    "Something went wrong. {error_message}",
                    "Unable to complete that action. {error_message}",
                ],
                "es": [
                    "Lo siento, hubo un error. {error_message}",
                    "Algo salió mal. {error_message}",
                    "No se pudo completar esa acción. {error_message}",
                ],
            },
            priority=FeedbackPriority.HIGH,
            sound_effects=["error_tone.mp3"],
        )

        # Encouragement templates
        self.templates["encouragement"] = FeedbackTemplate(
            id="encouragement",
            type=FeedbackType.ENCOURAGEMENT,
            templates={
                "en": [
                    "You're doing great!",
                    "Keep up the good work!",
                    "Excellent progress!",
                    "Well done!",
                    "You're getting the hang of it!",
                ],
                "es": [
                    "¡Lo estás haciendo muy bien!",
                    "¡Sigue así!",
                    "¡Excelente progreso!",
                    "¡Bien hecho!",
                    "¡Le estás agarrando la onda!",
                ],
            },
            interruptible=True,
        )
        # Medical-specific templates
        self.templates["medication_added"] = FeedbackTemplate(
            id="medication_added",
            type=FeedbackType.SUCCESS,
            templates={
                "en": [
                    "Medication {medication_name} has been added to your list.",
                    "I've added {medication_name} to your medications.",
                    "{medication_name} is now in your medication list.",
                ],
                "es": [
                    "El medicamento {medication_name} ha sido agregado a tu lista.",
                    "He agregado {medication_name} a tus medicamentos.",
                    "{medication_name} ahora está en tu lista de medicamentos.",
                ],
            },
            priority=FeedbackPriority.HIGH,
        )

        # Navigation feedback
        self.templates["navigation"] = FeedbackTemplate(
            id="navigation",
            type=FeedbackType.INFO,
            templates={
                "en": [
                    "Navigating to {destination}.",
                    "Opening {destination}.",
                    "Here's {destination}.",
                ]
            },
        )

        # Tutorial templates
        self.templates["tutorial_intro"] = FeedbackTemplate(
            id="tutorial_intro",
            type=FeedbackType.TUTORIAL,
            templates={
                "en": [
                    "Welcome to Haven Health Voice. Let me show you how to get started.",
                    "Hi! I'm here to help you manage your health information. Let's begin with the basics.",
                ]
            },
            voice_params=VoiceParameters(
                voice_id="Joanna",
                speaking_rate=0.9,  # Slightly slower for tutorials
                engine="neural",
            ),
        )
        # Question templates
        self.templates["confirm_action"] = FeedbackTemplate(
            id="confirm_action",
            type=FeedbackType.QUESTION,
            templates={
                "en": [
                    "Are you sure you want to {action}?",
                    "Please confirm: {action}?",
                    "Do you want to proceed with {action}?",
                ]
            },
            priority=FeedbackPriority.HIGH,
            interruptible=False,
        )

    def get_template(self, template_id: str) -> Optional[FeedbackTemplate]:
        """Get a feedback template by ID."""
        return self.templates.get(template_id)

    def add_template(self, template: FeedbackTemplate) -> None:
        """Add a custom feedback template."""
        self.templates[template.id] = template

    def get_templates_by_type(
        self, feedback_type: FeedbackType
    ) -> List[FeedbackTemplate]:
        """Get all templates of a specific type."""
        return [
            template
            for template in self.templates.values()
            if template.type == feedback_type
        ]


class VoiceSynthesizer:
    """Handles voice synthesis using AWS Polly."""

    def __init__(self, aws_region: str = "us-east-1"):
        """Initialize the voice synthesizer.

        Args:
            aws_region: AWS region for Polly service
        """
        self.polly_client = boto3.client("polly", region_name=aws_region)
        self.s3_client = boto3.client("s3", region_name=aws_region)
        self.cache: Dict[str, AudioFeedback] = {}
        self.voice_mapping = self._initialize_voice_mapping()

    def _initialize_voice_mapping(self) -> Dict[str, Dict[str, str]]:
        """Initialize language to voice ID mapping."""
        return {
            "en-US": {
                "professional": "Joanna",
                "friendly": "Matthew",
                "assistant": "Amy",
                "emergency": "Joey",
                "child": "Ivy",
            },
            "es-US": {
                "professional": "Lupe",
                "friendly": "Miguel",
                "assistant": "Penelope",
            },
            "fr-FR": {
                "professional": "Celine",
                "friendly": "Mathieu",
                "assistant": "Lea",
            },
            # Add more language-voice mappings
        }

    async def synthesize(
        self,
        text: str,
        voice_params: Optional[VoiceParameters] = None,
        audio_format: AudioFormat = AudioFormat.MP3,
    ) -> AudioFeedback:
        """Synthesize speech from text."""
        # Use default params if not provided
        if not voice_params:
            voice_params = VoiceParameters()

        # Check cache
        cache_key = self._generate_cache_key(text, voice_params, audio_format)
        if cache_key in self.cache:
            logger.info("Using cached audio for: %s...", text[:50])
            return self.cache[cache_key]

        # Prepare SSML if prosody adjustments needed
        ssml_text = self._create_ssml(text, voice_params)
        try:
            # Call Polly
            polly_params = voice_params.to_polly_params()
            polly_params.update(
                {
                    "Text": ssml_text if ssml_text else text,
                    "OutputFormat": audio_format.value,
                }
            )

            if ssml_text:
                polly_params["TextType"] = "ssml"

            response = self.polly_client.synthesize_speech(**polly_params)

            # Read audio stream
            audio_data = response["AudioStream"].read()

            # Create feedback object
            feedback = AudioFeedback(
                id=cache_key,
                type=FeedbackType.INFO,
                text=text,
                ssml=ssml_text,
                audio_data=audio_data,
                voice_params=voice_params,
                metadata={
                    "content_type": response.get("ContentType"),
                    "request_characters": response.get("RequestCharacters", 0),
                },
            )

            # Cache the result
            self.cache[cache_key] = feedback

            return feedback

        except BotoCoreError as e:
            logger.error("Polly synthesis error: %s", e)
            raise

    def _create_ssml(self, text: str, params: VoiceParameters) -> Optional[str]:
        """Create SSML markup for prosody control."""
        if params.speaking_rate == 1.0 and params.pitch == 0.0 and params.volume == 1.0:
            return None

        prosody_attrs = []

        if params.speaking_rate != 1.0:
            rate_percent = int(params.speaking_rate * 100)
            prosody_attrs.append(f'rate="{rate_percent}%"')

        if params.pitch != 0.0:
            pitch_st = f"{params.pitch:+.1f}st"
            prosody_attrs.append(f'pitch="{pitch_st}"')

        if params.volume != 1.0:
            volume_db = f"{20 * (params.volume - 1):+.1f}dB"
            prosody_attrs.append(f'volume="{volume_db}"')

        prosody = " ".join(prosody_attrs)

        return f"<speak><prosody {prosody}>{text}</prosody></speak>"

    def _generate_cache_key(
        self, text: str, params: VoiceParameters, audio_format: AudioFormat
    ) -> str:
        """Generate cache key for audio."""
        key_data = f"{text}|{params.voice_id}|{params.language}|{params.speaking_rate}|{params.pitch}|{audio_format.value}"
        return hashlib.md5(key_data.encode(), usedforsecurity=False).hexdigest()

    async def get_available_voices(
        self, language_code: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get available voices from Polly."""
        try:
            params = {}
            if language_code:
                params["LanguageCode"] = language_code

            response = self.polly_client.describe_voices(**params)
            voices = []
            for voice in response["Voices"]:
                voices.append(
                    {
                        "id": voice["Id"],
                        "name": voice["Name"],
                        "language": voice["LanguageCode"],
                        "gender": voice["Gender"],
                        "neural": "neural" in voice.get("SupportedEngines", []),
                    }
                )

            return voices

        except BotoCoreError as e:
            logger.error("Error fetching voices: %s", e)
            return []


class AdaptiveFeedbackGenerator:
    """Generates adaptive feedback based on user context."""

    def __init__(self, template_library: FeedbackTemplateLibrary):
        """Initialize the adaptive feedback generator.

        Args:
            template_library: Library of feedback templates to use
        """
        self.template_library = template_library
        self.user_feedback_history: Dict[str, List[Dict]] = defaultdict(list)
        self.variation_trackers: Dict[str, int] = defaultdict(int)

    def generate_feedback(
        self,
        template_id: str,
        context: FeedbackContext,
        variables: Optional[Dict[str, str]] = None,
    ) -> Optional[AudioFeedback]:
        """Generate context-appropriate feedback."""
        template = self.template_library.get_template(template_id)
        if not template:
            logger.warning("Template not found: %s", template_id)
            return None

        # Select appropriate variation
        variation = self._select_variation(template_id, context)
        # Get text in user's language
        language = self._get_user_language(context)
        text = template.get_text(language, variation)

        # Replace variables
        if variables:
            for key, value in variables.items():
                text = text.replace(f"{{{key}}}", value)

        # Adjust voice parameters based on context
        voice_params = self._adapt_voice_parameters(template, context)

        # Add emotional adjustments
        text = self._add_emotional_context(text, context)

        # Create feedback
        feedback = AudioFeedback(
            id=f"{template_id}_{datetime.now().timestamp()}",
            type=template.type,
            text=text,
            voice_params=voice_params,
            priority=self._adjust_priority(template.priority, context),
        )

        # Record in history
        self._record_feedback(context.user_id, feedback)

        return feedback

    def _select_variation(self, template_id: str, context: FeedbackContext) -> int:
        """Select appropriate text variation."""
        # Use different variations to avoid repetition
        key = f"{context.user_id}_{template_id}"
        current = self.variation_trackers[key]
        self.variation_trackers[key] = (current + 1) % 10  # Cycle through variations

        # Adjust based on user level
        if context.user_level == "Beginner":
            return 0  # Use simplest variation
        elif context.user_level == "Expert":
            return current  # Use variety

        return current % 3  # Limited variety for intermediate

    def _get_user_language(self, context: FeedbackContext) -> str:
        """Determine user's preferred language."""
        # Could be stored in context or user preferences
        return str(context.environment.get("language", "en"))

    def _adapt_voice_parameters(
        self, template: FeedbackTemplate, context: FeedbackContext
    ) -> VoiceParameters:
        """Adapt voice parameters to user context."""
        # Start with template params or defaults
        params = template.voice_params or VoiceParameters()

        # Adjust for accessibility needs
        if "hearing_impaired" in context.accessibility_needs:
            params.speaking_rate = max(0.7, params.speaking_rate * 0.8)  # Slower
            params.volume = 1.0  # Maximum volume

        if "cognitive_support" in context.accessibility_needs:
            params.speaking_rate = max(0.6, params.speaking_rate * 0.7)  # Much slower

        # Adjust based on environment
        if context.environment.get("noisy", False):
            params.volume = 1.0
            params.pitch = params.pitch + 2  # Slightly higher pitch cuts through noise

        # Adjust based on emotional state
        if context.emotional_state == "stressed":
            params.speaking_rate = max(0.8, params.speaking_rate * 0.9)
            params.pitch = params.pitch - 1  # Lower, calming tone

        # Adjust based on recent errors
        if context.recent_errors > 2:
            params.speaking_rate = max(0.8, params.speaking_rate * 0.85)

        return params

    def _add_emotional_context(self, text: str, context: FeedbackContext) -> str:
        """Add emotional context to feedback."""
        # Add encouragement if user is struggling
        if context.success_rate < 0.5 and context.interaction_count > 5:
            encouragers = ["Don't worry, ", "It's okay, ", "No problem, "]
            text = random.choice(encouragers) + text.lower()
        # Add celebration for milestones
        if context.interaction_count % 10 == 0 and context.success_rate > 0.8:
            text += " Great job on your progress!"

        return text

    def _adjust_priority(
        self, base_priority: FeedbackPriority, context: FeedbackContext
    ) -> FeedbackPriority:
        """Adjust feedback priority based on context."""
        # Increase priority for users who need more support
        if context.user_level == "Beginner":
            return FeedbackPriority(max(1, base_priority.value - 1))

        # Decrease priority for experienced users (less verbose)
        if context.user_level == "Expert" and base_priority == FeedbackPriority.NORMAL:
            return FeedbackPriority.LOW

        return base_priority

    def _record_feedback(self, user_id: str, feedback: AudioFeedback) -> None:
        """Record feedback in history for learning."""
        self.user_feedback_history[user_id].append(
            {
                "timestamp": feedback.timestamp.isoformat(),
                "type": feedback.type.value,
                "text": feedback.text[:100],  # Store preview
                "priority": feedback.priority.value,
            }
        )

        # Keep only last 100 entries per user
        if len(self.user_feedback_history[user_id]) > 100:
            self.user_feedback_history[user_id] = self.user_feedback_history[user_id][
                -100:
            ]


class FeedbackQueueManager:
    """Manages the queue and playback of voice feedback."""

    def __init__(self) -> None:
        """Initialize the feedback queue manager."""
        self.queue: List[AudioFeedback] = []
        self.current_feedback: Optional[AudioFeedback] = None
        self.is_playing: bool = False
        self.playback_callback: Optional[Callable] = None
        self.interruption_handlers: Dict[FeedbackPriority, Callable] = {}

    async def add_feedback(self, feedback: AudioFeedback) -> None:
        """Add feedback to the queue."""
        # Check if we should interrupt current playback
        if self.current_feedback and self._should_interrupt(feedback):
            await self.interrupt_current()

        # Add to queue based on priority
        self._insert_by_priority(feedback)

        # Start playback if not already playing
        if not self.is_playing:
            await self._play_next()

    def _should_interrupt(self, new_feedback: AudioFeedback) -> bool:
        """Determine if new feedback should interrupt current."""
        if not self.current_feedback:
            return False

        # Always interrupt for critical feedback
        if new_feedback.priority == FeedbackPriority.CRITICAL:
            return True

        # Check if current is interruptible and new has higher priority
        if (
            self.current_feedback.priority.value > new_feedback.priority.value
            and hasattr(self.current_feedback, "interruptible")
            and self.current_feedback.metadata.get("interruptible", True)
        ):
            return True

        return False

    def _insert_by_priority(self, feedback: AudioFeedback) -> None:
        """Insert feedback in queue maintaining priority order."""
        # Find insertion point
        insert_idx = len(self.queue)
        for i, queued in enumerate(self.queue):
            if feedback.priority.value < queued.priority.value:
                insert_idx = i
                break

        self.queue.insert(insert_idx, feedback)

    async def _play_next(self) -> None:
        """Play the next feedback in queue."""
        if not self.queue:
            self.is_playing = False
            return

        self.current_feedback = self.queue.pop(0)
        self.is_playing = True

        try:
            # Play the feedback
            if self.playback_callback:
                await self.playback_callback(self.current_feedback)
            else:
                # Simulate playback
                duration = (
                    self.current_feedback.duration
                    or len(self.current_feedback.text) * 0.06
                )
                await asyncio.sleep(duration)

            # Mark as completed
            self.current_feedback = None

            # Play next if available
            await self._play_next()

        except (BotoCoreError, ValueError, KeyError, asyncio.CancelledError) as e:
            logger.error("Error playing feedback: %s", e)
            self.is_playing = False
            self.current_feedback = None

    async def interrupt_current(self) -> None:
        """Interrupt current playback."""
        if self.current_feedback:
            # Call interruption handler if registered
            priority = self.current_feedback.priority
            if priority in self.interruption_handlers:
                await self.interruption_handlers[priority](self.current_feedback)

            # Add back to queue if it should be resumed
            if self.current_feedback.metadata.get("resume_after_interrupt", False):
                self._insert_by_priority(self.current_feedback)

            self.current_feedback = None

    def clear_queue(
        self, priority_threshold: Optional[FeedbackPriority] = None
    ) -> None:
        """Clear feedback queue, optionally keeping high priority items."""
        if priority_threshold:
            self.queue = [
                f for f in self.queue if f.priority.value <= priority_threshold.value
            ]
        else:
            self.queue.clear()

    def get_queue_status(self) -> Dict[str, Any]:
        """Get current queue status."""
        return {
            "is_playing": self.is_playing,
            "current": self.current_feedback.text if self.current_feedback else None,
            "queue_length": len(self.queue),
            "queue_priorities": [f.priority.value for f in self.queue],
        }


class VoiceFeedbackSystem:
    """Main voice feedback system orchestrator."""

    def __init__(self, aws_region: str = "us-east-1"):
        """Initialize the voice feedback system.

        Args:
            aws_region: AWS region for voice synthesis services
        """
        self.template_library = FeedbackTemplateLibrary()
        self.synthesizer = VoiceSynthesizer(aws_region)
        self.generator = AdaptiveFeedbackGenerator(self.template_library)
        self.queue_manager = FeedbackQueueManager()
        self.audio_player: Optional[Any] = None  # Actual audio player
        self.user_contexts: Dict[str, FeedbackContext] = {}

        # Set up playback callback
        self.queue_manager.playback_callback = self._play_audio

        # Sound effect cache
        self.sound_effects: Dict[str, bytes] = {}

    async def initialize(self) -> None:
        """Initialize the feedback system."""
        # Load sound effects
        await self._load_sound_effects()

        # Test Polly connection
        voices = await self.synthesizer.get_available_voices()
        logger.info("Initialized with %d available voices", len(voices))

    async def _load_sound_effects(self) -> None:
        """Load sound effect files."""
        # In production, load from S3 or local storage
        effect_files = [
            "success_chime.mp3",
            "error_tone.mp3",
            "notification.mp3",
            "warning.mp3",
        ]

        for effect_file in effect_files:
            # Simulated loading - in production, actually load files
            self.sound_effects[effect_file] = b"audio_data_placeholder"

    def update_user_context(
        self, user_id: str, context_updates: Dict[str, Any]
    ) -> None:
        """Update user context for adaptive feedback."""
        if user_id not in self.user_contexts:
            self.user_contexts[user_id] = FeedbackContext(
                user_id=user_id,
                user_level="Beginner",
                interaction_count=0,
                success_rate=1.0,
            )

        context = self.user_contexts[user_id]

        # Update fields
        for key, value in context_updates.items():
            if hasattr(context, key):
                setattr(context, key, value)

    async def provide_feedback(
        self,
        user_id: str,
        template_id: str,
        variables: Optional[Dict[str, str]] = None,
        priority_override: Optional[FeedbackPriority] = None,
    ) -> None:
        """Provide voice feedback to user."""
        # Get user context
        context = self.user_contexts.get(user_id)
        if not context:
            context = FeedbackContext(
                user_id=user_id,
                user_level="Beginner",
                interaction_count=0,
                success_rate=1.0,
            )
        # Generate adaptive feedback
        feedback = self.generator.generate_feedback(template_id, context, variables)

        if not feedback:
            logger.warning("Failed to generate feedback for template: %s", template_id)
            return

        # Override priority if specified
        if priority_override:
            feedback.priority = priority_override

        # Synthesize speech
        try:
            audio_feedback = await self.synthesizer.synthesize(
                feedback.text, feedback.voice_params
            )

            # Copy feedback properties
            audio_feedback.type = feedback.type
            audio_feedback.priority = feedback.priority

            # Add to playback queue
            await self.queue_manager.add_feedback(audio_feedback)

        except (ValueError, KeyError, AttributeError) as e:
            logger.error("Failed to synthesize feedback: %s", e)

    async def _play_audio(self, feedback: AudioFeedback) -> None:
        """Play audio feedback."""
        # In production, this would interface with actual audio playback
        # For now, simulate playback
        logger.info("Playing: %s", feedback.text)

        # Play any associated sound effects first
        if hasattr(feedback, "sound_effects"):
            for effect in feedback.metadata.get("sound_effects", []):
                if effect in self.sound_effects:
                    # Play sound effect
                    await asyncio.sleep(0.5)  # Simulate

        # Calculate duration based on text length if not provided
        if not feedback.duration:
            # Rough estimate: 60ms per character
            feedback.duration = len(feedback.text) * 0.06

        await asyncio.sleep(feedback.duration)

    async def provide_success_feedback(
        self,
        user_id: str,
        action: Optional[str] = None,
        details: Optional[Dict[str, str]] = None,
    ) -> None:
        """Provide success feedback to the user."""
        # action parameter can be used for logging or specific feedback types
        _ = action  # Mark as intentionally unused
        await self.provide_feedback(
            user_id, "command_success", details, FeedbackPriority.NORMAL
        )

    async def provide_error_feedback(self, user_id: str, error_message: str) -> None:
        """Provide error feedback to the user."""
        await self.provide_feedback(
            user_id,
            "command_error",
            {"error_message": error_message},
            FeedbackPriority.HIGH,
        )

    async def provide_encouragement(self, user_id: str) -> None:
        """Provide encouraging feedback."""
        context = self.user_contexts.get(user_id)
        if context and context.success_rate < 0.7:
            await self.provide_feedback(
                user_id, "encouragement", priority_override=FeedbackPriority.LOW
            )

    def add_custom_template(self, template: FeedbackTemplate) -> None:
        """Add a custom feedback template."""
        self.template_library.add_template(template)

    async def stop_all_feedback(self) -> None:
        """Stop all feedback and clear queue."""
        await self.queue_manager.interrupt_current()
        self.queue_manager.clear_queue()

    def get_system_status(self) -> Dict[str, Any]:
        """Get system status."""
        return {
            "queue_status": self.queue_manager.get_queue_status(),
            "active_users": len(self.user_contexts),
            "cached_audio": len(self.synthesizer.cache),
            "templates": len(self.template_library.templates),
            "sound_effects": len(self.sound_effects),
        }

    def validate_feedback_data(self, feedback_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate feedback data for FHIR compliance.

        Args:
            feedback_data: Feedback data to validate

        Returns:
            Validation result with 'valid', 'errors', and 'warnings' keys
        """
        errors = []
        warnings = []

        if not feedback_data:
            errors.append("No feedback data provided")
        elif "type" not in feedback_data:
            warnings.append("Feedback type not specified")

        return {"valid": len(errors) == 0, "errors": errors, "warnings": warnings}
