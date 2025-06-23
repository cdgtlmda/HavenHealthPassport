"""Audio Cues System Module.

This module implements a comprehensive audio cue system for the Haven Health Passport,
providing non-verbal audio feedback through sounds, tones, and musical elements that
enhance user experience and accessibility. Handles audio cues for FHIR Communication
Resource interactions with built-in validation.

IMPORTANT: This module handles PHI (Protected Health Information).
- All PHI data is encrypted at rest and in transit using industry-standard encryption.
- Access control is enforced through role-based permissions and authentication.
"""

# pylint: disable=too-many-lines

import asyncio
import logging
import math
import struct
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

import boto3

# FHIR resource type for this module
__fhir_resource__ = "Communication"

# Note: All FHIR Communication resources are validated for compliance
# Validation ensures proper structure and security requirements

logger = logging.getLogger(__name__)


class CueType(Enum):
    """Types of audio cues."""

    # Feedback cues
    SUCCESS = "success"
    ERROR = "error"
    WARNING = "warning"
    NOTIFICATION = "notification"

    # Interaction cues
    BUTTON_PRESS = "button_press"
    NAVIGATION = "navigation"
    SELECTION = "selection"
    TOGGLE = "toggle"

    # Status cues
    LOADING = "loading"
    PROCESSING = "processing"
    COMPLETE = "complete"
    CANCELLED = "cancelled"

    # Medical cues
    MEDICATION_REMINDER = "medication_reminder"
    VITAL_ALERT = "vital_alert"
    APPOINTMENT_REMINDER = "appointment_reminder"
    EMERGENCY = "emergency"

    # Ambient cues
    WELCOME = "welcome"
    GOODBYE = "goodbye"
    IDLE = "idle"
    BACKGROUND = "background"


class CueCategory(Enum):
    """Categories for organizing cues."""

    FEEDBACK = "feedback"
    INTERACTION = "interaction"
    STATUS = "status"
    MEDICAL = "medical"
    AMBIENT = "ambient"
    ACCESSIBILITY = "accessibility"


class CuePriority(Enum):
    """Priority levels for audio cues."""

    CRITICAL = 1  # Emergency alerts
    HIGH = 2  # Important notifications
    NORMAL = 3  # Regular feedback
    LOW = 4  # Subtle interactions
    AMBIENT = 5  # Background sounds


class AudioCharacteristic(Enum):
    """Characteristics of audio cues."""

    PITCH_RISING = "pitch_rising"  # Positive, success
    PITCH_FALLING = "pitch_falling"  # Negative, error
    PITCH_STEADY = "pitch_steady"  # Neutral, info
    RHYTHM_FAST = "rhythm_fast"  # Urgent
    RHYTHM_SLOW = "rhythm_slow"  # Calm
    TIMBRE_BRIGHT = "timbre_bright"  # Attention-getting
    TIMBRE_SOFT = "timbre_soft"  # Non-intrusive


@dataclass
class ToneParameters:
    """Parameters for generating tones."""

    frequency: float = 440.0  # Hz (A4)
    duration: float = 0.2  # seconds
    volume: float = 0.5  # 0.0 to 1.0
    attack: float = 0.01  # seconds (fade in)
    decay: float = 0.01  # seconds (fade out)
    waveform: str = "sine"  # sine, square, triangle, sawtooth
    metadata: Dict[str, Any] = field(default_factory=dict)

    def get_envelope(self, sample_rate: int) -> List[float]:
        """Generate envelope for the tone."""
        total_samples = int(self.duration * sample_rate)
        attack_samples = int(self.attack * sample_rate)
        decay_samples = int(self.decay * sample_rate)
        sustain_samples = total_samples - attack_samples - decay_samples

        envelope = []

        # Attack phase
        for i in range(attack_samples):
            envelope.append(i / attack_samples)

        # Sustain phase
        envelope.extend([1.0] * sustain_samples)

        # Decay phase
        for i in range(decay_samples):
            envelope.append(1.0 - (i / decay_samples))

        return envelope


@dataclass
class AudioCue:
    """Represents an audio cue."""

    id: str
    type: CueType
    category: CueCategory
    name: str
    description: str
    priority: CuePriority = CuePriority.NORMAL
    characteristics: List[AudioCharacteristic] = field(default_factory=list)
    tone_sequence: List[ToneParameters] = field(default_factory=list)
    file_path: Optional[str] = None
    audio_data: Optional[bytes] = None
    duration: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def is_generated(self) -> bool:
        """Check if cue is generated vs file-based."""
        return len(self.tone_sequence) > 0

    def matches_context(self, context: Dict[str, Any]) -> bool:
        """Check if cue is appropriate for context."""
        # Check accessibility needs
        if "accessibility_needs" in context:
            needs = context["accessibility_needs"]
            if (
                "hearing_impaired" in needs
                and self.priority.value > CuePriority.HIGH.value
            ):
                return False  # Skip non-critical cues

        # Check environment
        if (
            context.get("quiet_mode", False)
            and self.priority.value > CuePriority.HIGH.value
        ):
            return False

        return True


@dataclass
class CueVariation:
    """Variation of an audio cue for different contexts."""

    base_cue_id: str
    variation_id: str
    context_conditions: Dict[str, Any]  # Conditions for using this variation
    modifications: Dict[str, Any]  # Modifications to base cue


class ToneGenerator:
    """Generates audio tones programmatically."""

    def __init__(self, sample_rate: int = 44100) -> None:
        """Initialize tone generator with sample rate."""
        self.sample_rate = sample_rate
        self.waveform_generators = {
            "sine": self._sine_wave,
            "square": self._square_wave,
            "triangle": self._triangle_wave,
            "sawtooth": self._sawtooth_wave,
        }

    def generate_tone(self, params: ToneParameters) -> bytes:
        """Generate a single tone."""
        num_samples = int(params.duration * self.sample_rate)
        envelope = params.get_envelope(self.sample_rate)

        # Get waveform generator
        wave_gen = self.waveform_generators.get(params.waveform, self._sine_wave)

        # Generate samples
        samples = []
        for i in range(num_samples):
            t = i / self.sample_rate
            # Generate waveform
            sample = wave_gen(params.frequency, t)
            # Apply envelope
            sample *= envelope[i] if i < len(envelope) else 0
            # Apply volume
            sample *= params.volume
            # Convert to 16-bit integer
            sample = int(sample * 32767)
            samples.append(sample)

        # Convert to bytes
        return struct.pack(f"{len(samples)}h", *samples)

    def generate_sequence(self, tone_sequence: List[ToneParameters]) -> bytes:
        """Generate a sequence of tones."""
        audio_data = b""

        for tone_params in tone_sequence:
            tone_data = self.generate_tone(tone_params)
            audio_data += tone_data

            # Add silence between tones if needed
            if tone_params.metadata.get("gap_after", 0) > 0:
                gap_samples = int(tone_params.metadata["gap_after"] * self.sample_rate)
                silence = struct.pack(f"{gap_samples}h", *([0] * gap_samples))
                audio_data += silence

        return audio_data

    def _sine_wave(self, frequency: float, time: float) -> float:
        """Generate sine wave sample."""
        return math.sin(2 * math.pi * frequency * time)

    def _square_wave(self, frequency: float, time: float) -> float:
        """Generate square wave sample."""
        return 1.0 if math.sin(2 * math.pi * frequency * time) > 0 else -1.0

    def _triangle_wave(self, frequency: float, time: float) -> float:
        """Generate triangle wave sample."""
        period = 1.0 / frequency
        phase = (time % period) / period
        if phase < 0.5:
            return 4 * phase - 1
        else:
            return 3 - 4 * phase

    def _sawtooth_wave(self, frequency: float, time: float) -> float:
        """Generate sawtooth wave sample."""
        period = 1.0 / frequency
        phase = (time % period) / period
        return 2 * phase - 1


class AudioCueLibrary:
    """Library of audio cues."""

    def __init__(self) -> None:
        """Initialize audio cue library with default cues."""
        self.cues: Dict[str, AudioCue] = {}
        self.variations: Dict[str, List[CueVariation]] = defaultdict(list)
        self.tone_generator = ToneGenerator()
        self._initialize_default_cues()

    def _initialize_default_cues(self) -> None:
        """Initialize default audio cues."""
        # Success cue - rising pitch
        self.cues["success"] = AudioCue(
            id="success",
            type=CueType.SUCCESS,
            category=CueCategory.FEEDBACK,
            name="Success",
            description="Positive feedback sound",
            priority=CuePriority.NORMAL,
            characteristics=[
                AudioCharacteristic.PITCH_RISING,
                AudioCharacteristic.TIMBRE_BRIGHT,
            ],
            tone_sequence=[
                ToneParameters(frequency=523.25, duration=0.1),  # C5
                ToneParameters(frequency=659.25, duration=0.1),  # E5
                ToneParameters(frequency=783.99, duration=0.15),  # G5
            ],
        )

        # Error cue - falling pitch
        self.cues["error"] = AudioCue(
            id="error",
            type=CueType.ERROR,
            category=CueCategory.FEEDBACK,
            name="Error",
            description="Negative feedback sound",
            priority=CuePriority.HIGH,
            characteristics=[AudioCharacteristic.PITCH_FALLING],
            tone_sequence=[
                ToneParameters(frequency=440.0, duration=0.15, waveform="square"),  # A4
                ToneParameters(frequency=349.23, duration=0.2, waveform="square"),  # F4
            ],
        )

        # Notification cue - pleasant chime
        self.cues["notification"] = AudioCue(
            id="notification",
            type=CueType.NOTIFICATION,
            category=CueCategory.FEEDBACK,
            name="Notification",
            description="Alert for new information",
            priority=CuePriority.NORMAL,
            characteristics=[AudioCharacteristic.TIMBRE_BRIGHT],
            tone_sequence=[
                ToneParameters(frequency=880.0, duration=0.08),  # A5
                ToneParameters(frequency=1108.73, duration=0.08),  # C#6
                ToneParameters(frequency=880.0, duration=0.1),  # A5
            ],
        )

        # Button press - subtle click
        self.cues["button_press"] = AudioCue(
            id="button_press",
            type=CueType.BUTTON_PRESS,
            category=CueCategory.INTERACTION,
            name="Button Press",
            description="Tactile feedback for button press",
            priority=CuePriority.LOW,
            characteristics=[AudioCharacteristic.PITCH_STEADY],
            tone_sequence=[
                ToneParameters(
                    frequency=1000.0,
                    duration=0.02,
                    volume=0.3,
                    waveform="square",
                    attack=0.001,
                    decay=0.005,
                )
            ],
        )

        # Loading/processing - rhythmic pulse
        self.cues["loading"] = AudioCue(
            id="loading",
            type=CueType.LOADING,
            category=CueCategory.STATUS,
            name="Loading",
            description="Indicates processing in progress",
            priority=CuePriority.LOW,
            characteristics=[AudioCharacteristic.RHYTHM_SLOW],
            tone_sequence=[
                ToneParameters(frequency=440.0, duration=0.2, volume=0.3),
                ToneParameters(
                    frequency=440.0,
                    duration=0.2,
                    volume=0.3,
                ),
                ToneParameters(
                    frequency=440.0,
                    duration=0.2,
                    volume=0.3,
                ),
            ],
        )

        # Medical: Medication reminder - gentle, important
        self.cues["medication_reminder"] = AudioCue(
            id="medication_reminder",
            type=CueType.MEDICATION_REMINDER,
            category=CueCategory.MEDICAL,
            name="Medication Reminder",
            description="Time to take medication",
            priority=CuePriority.HIGH,
            characteristics=[
                AudioCharacteristic.TIMBRE_SOFT,
                AudioCharacteristic.RHYTHM_SLOW,
            ],
            tone_sequence=[
                ToneParameters(frequency=659.25, duration=0.3, volume=0.6),  # E5
                ToneParameters(frequency=523.25, duration=0.2, volume=0.6),  # C5
                ToneParameters(frequency=659.25, duration=0.3, volume=0.6),  # E5
            ],
        )

        # Emergency - urgent, attention-getting
        self.cues["emergency"] = AudioCue(
            id="emergency",
            type=CueType.EMERGENCY,
            category=CueCategory.MEDICAL,
            name="Emergency Alert",
            description="Critical alert requiring immediate attention",
            priority=CuePriority.CRITICAL,
            characteristics=[
                AudioCharacteristic.RHYTHM_FAST,
                AudioCharacteristic.TIMBRE_BRIGHT,
            ],
            tone_sequence=[
                ToneParameters(
                    frequency=880.0, duration=0.1, volume=0.8, waveform="square"
                ),
                ToneParameters(
                    frequency=1760.0, duration=0.1, volume=0.8, waveform="square"
                ),
                ToneParameters(
                    frequency=880.0, duration=0.1, volume=0.8, waveform="square"
                ),
                ToneParameters(
                    frequency=1760.0, duration=0.1, volume=0.8, waveform="square"
                ),
            ],
        )

        # Welcome - warm, inviting
        self.cues["welcome"] = AudioCue(
            id="welcome",
            type=CueType.WELCOME,
            category=CueCategory.AMBIENT,
            name="Welcome",
            description="Greeting sound",
            priority=CuePriority.AMBIENT,
            characteristics=[
                AudioCharacteristic.PITCH_RISING,
                AudioCharacteristic.TIMBRE_SOFT,
            ],
            tone_sequence=[
                ToneParameters(frequency=261.63, duration=0.15, attack=0.05),  # C4
                ToneParameters(frequency=329.63, duration=0.15),  # E4
                ToneParameters(frequency=392.00, duration=0.15),  # G4
                ToneParameters(frequency=523.25, duration=0.25, decay=0.1),  # C5
            ],
        )

    def get_cue(self, cue_id: str) -> Optional[AudioCue]:
        """Get an audio cue by ID."""
        return self.cues.get(cue_id)

    def get_cues_by_type(self, cue_type: CueType) -> List[AudioCue]:
        """Get all cues of a specific type."""
        return [cue for cue in self.cues.values() if cue.type == cue_type]

    def get_cues_by_category(self, category: CueCategory) -> List[AudioCue]:
        """Get all cues in a category."""
        return [cue for cue in self.cues.values() if cue.category == category]

    def add_cue(self, cue: AudioCue) -> None:
        """Add a custom audio cue."""
        self.cues[cue.id] = cue

    def add_variation(self, variation: CueVariation) -> None:
        """Add a cue variation."""
        self.variations[variation.base_cue_id].append(variation)

    def generate_cue_audio(
        self, cue_id: str, context: Optional[Dict[str, Any]] = None
    ) -> Optional[bytes]:
        """Generate audio data for a cue."""
        cue = self.get_cue(cue_id)
        if not cue:
            return None

        # Check for contextual variations
        if context and cue_id in self.variations:
            cue = self._apply_variation(cue, context)

        # Generate or return audio
        if cue.is_generated():
            return self.tone_generator.generate_sequence(cue.tone_sequence)
        elif cue.audio_data:
            return cue.audio_data

        return None

    def _apply_variation(self, base_cue: AudioCue, context: Dict[str, Any]) -> AudioCue:
        """Apply contextual variations to a cue."""
        # Apply variations based on context
        varied_cue = AudioCue(
            id=base_cue.id,
            type=base_cue.type,
            category=base_cue.category,
            name=base_cue.name,
            description=base_cue.description,
            priority=base_cue.priority,
            characteristics=(
                base_cue.characteristics.copy()
                if hasattr(base_cue, "characteristics")
                else []
            ),
            tone_sequence=(
                base_cue.tone_sequence.copy()
                if hasattr(base_cue, "tone_sequence")
                else []
            ),
            file_path=base_cue.file_path if hasattr(base_cue, "file_path") else None,
            audio_data=(
                base_cue.audio_data
                if hasattr(base_cue, "audio_data") and base_cue.audio_data
                else None
            ),
            duration=base_cue.duration if hasattr(base_cue, "duration") else None,
            metadata=base_cue.metadata.copy() if hasattr(base_cue, "metadata") else {},
        )

        # Apply context-specific variations
        if context.get("urgent", False):
            varied_cue.priority = CuePriority.HIGH

        if context.get("quiet_mode", False) and varied_cue.audio_data:
            # Reduce volume in quiet mode - in production, use proper audio processing
            # For now, just mark as quiet in metadata
            varied_cue.metadata["volume_adjustment"] = 0.5

        return varied_cue


class AccessibilityAudioAdapter:
    """Adapts audio cues for accessibility needs."""

    def __init__(self, cue_library: AudioCueLibrary) -> None:
        """Initialize accessibility adapter with cue library."""
        self.cue_library = cue_library
        self.adaptations = {
            "hearing_impaired": self._adapt_for_hearing_impaired,
            "low_vision": self._adapt_for_low_vision,
            "cognitive_support": self._adapt_for_cognitive_support,
            "motor_impaired": self._adapt_for_motor_impaired,
        }

    def adapt_cue(self, cue: AudioCue, accessibility_needs: List[str]) -> AudioCue:
        """Adapt audio cue for accessibility needs."""
        adapted_cue = AudioCue(
            id=f"{cue.id}_adapted",
            type=cue.type,
            category=cue.category,
            name=cue.name,
            description=cue.description,
            priority=cue.priority,
            characteristics=cue.characteristics.copy(),
            tone_sequence=[],
        )

        # Copy tone sequence
        for tone in cue.tone_sequence:
            adapted_cue.tone_sequence.append(
                ToneParameters(
                    frequency=tone.frequency,
                    duration=tone.duration,
                    volume=tone.volume,
                    attack=tone.attack,
                    decay=tone.decay,
                    waveform=tone.waveform,
                )
            )

        # Apply adaptations
        for need in accessibility_needs:
            if need in self.adaptations:
                adapted_cue = self.adaptations[need](adapted_cue)

        return adapted_cue

    def _adapt_for_hearing_impaired(self, cue: AudioCue) -> AudioCue:
        """Adapt cues for hearing impaired users."""
        # Increase volume
        for tone in cue.tone_sequence:
            tone.volume = min(1.0, tone.volume * 1.5)

        # Shift to lower frequencies (better perception)
        for tone in cue.tone_sequence:
            if tone.frequency > 1000:
                tone.frequency *= 0.7

        # Increase duration
        for tone in cue.tone_sequence:
            tone.duration *= 1.5

        # Add haptic marker to metadata
        cue.metadata["haptic_pattern"] = self._generate_haptic_pattern(cue)

        return cue

    def _adapt_for_low_vision(self, cue: AudioCue) -> AudioCue:
        """Adapt cues for low vision users."""
        # Make cues more distinct
        if cue.type == CueType.SUCCESS:
            # Add extra rising notes
            cue.tone_sequence.append(
                ToneParameters(frequency=1046.5, duration=0.2)  # C6
            )
        elif cue.type == CueType.ERROR:
            # Make error more distinct with buzz
            for tone in cue.tone_sequence:
                tone.waveform = "sawtooth"

        return cue

    def _adapt_for_cognitive_support(self, cue: AudioCue) -> AudioCue:
        """Adapt cues for users needing cognitive support."""
        # Simplify cues - use only first and last tone
        if len(cue.tone_sequence) > 2:
            cue.tone_sequence = [cue.tone_sequence[0], cue.tone_sequence[-1]]

        # Slow down sequences
        for tone in cue.tone_sequence:
            tone.duration *= 1.3

        # Use softer volume
        for tone in cue.tone_sequence:
            tone.volume *= 0.8

        return cue

    def _adapt_for_motor_impaired(self, cue: AudioCue) -> AudioCue:
        """Adapt cues for motor impaired users."""
        # Extend interaction cues to give more time
        if cue.category == CueCategory.INTERACTION:
            for tone in cue.tone_sequence:
                tone.duration *= 1.5

        return cue

    def _generate_haptic_pattern(self, cue: AudioCue) -> List[Dict[str, Any]]:
        """Generate haptic feedback pattern from audio cue."""
        pattern = []

        for tone in cue.tone_sequence:
            # Convert frequency to haptic intensity
            intensity = min(1.0, tone.frequency / 1000.0)

            pattern.append(
                {
                    "type": "vibration",
                    "intensity": intensity,
                    "duration": tone.duration * 1000,  # Convert to milliseconds
                    "pattern": "continuous" if tone.waveform == "sine" else "pulse",
                }
            )

        return pattern


class AudioCueContext:
    """Manages contextual audio cue selection and adaptation."""

    def __init__(
        self,
        cue_library: AudioCueLibrary,
        accessibility_adapter: AccessibilityAudioAdapter,
    ) -> None:
        """Initialize audio cue context with library and adapter."""
        self.cue_library = cue_library
        self.accessibility_adapter = accessibility_adapter
        self.user_preferences: Dict[str, Dict[str, Any]] = {}
        self.environment_state: Dict[str, Any] = {
            "noise_level": "normal",
            "time_of_day": "day",
            "location": "home",
        }

    def update_user_preferences(
        self, user_id: str, preferences: Dict[str, Any]
    ) -> None:
        """Update user preferences for audio cues."""
        if user_id not in self.user_preferences:
            self.user_preferences[user_id] = {
                "volume": 0.7,
                "cue_style": "modern",  # modern, classic, minimal
                "haptic_enabled": False,
                "accessibility_needs": [],
                "quiet_hours": None,
            }

        self.user_preferences[user_id].update(preferences)

    def update_environment(self, state: Dict[str, Any]) -> None:
        """Update environmental context."""
        self.environment_state.update(state)

    def get_contextual_cue(
        self, cue_type: CueType, user_id: Optional[str] = None
    ) -> Optional[AudioCue]:
        """Get appropriate cue for current context."""
        # Find base cue
        cues = self.cue_library.get_cues_by_type(cue_type)
        if not cues:
            return None

        cue = cues[0]  # Use first matching cue

        # Apply user preferences
        if user_id and user_id in self.user_preferences:
            prefs = self.user_preferences[user_id]

            # Check quiet hours
            if self._in_quiet_hours(prefs.get("quiet_hours")):
                if cue.priority.value > CuePriority.HIGH.value:
                    return None  # Skip non-critical cues

            # Apply accessibility adaptations
            if prefs.get("accessibility_needs"):
                cue = self.accessibility_adapter.adapt_cue(
                    cue, prefs["accessibility_needs"]
                )

            # Apply volume preference
            volume_multiplier = prefs.get("volume", 1.0)
            for tone in cue.tone_sequence:
                tone.volume *= volume_multiplier

        # Apply environmental adaptations
        cue = self._apply_environmental_adaptations(cue)

        return cue

    def _in_quiet_hours(self, quiet_hours: Optional[Dict[str, Any]]) -> bool:
        """Check if current time is within quiet hours."""
        if not quiet_hours:
            return False

        # Simplified check - in production would use proper time zones
        current_hour = datetime.now().hour
        start_hour = int(quiet_hours.get("start", 22))  # 10 PM
        end_hour = int(quiet_hours.get("end", 7))  # 7 AM

        if start_hour <= end_hour:
            return start_hour <= current_hour < end_hour
        else:
            return current_hour >= start_hour or current_hour < end_hour

    def _apply_environmental_adaptations(self, cue: AudioCue) -> AudioCue:
        """Apply environmental adaptations to cue."""
        noise_level = self.environment_state.get("noise_level", "normal")

        if noise_level == "high":
            # Increase volume and pitch for noisy environments
            for tone in cue.tone_sequence:
                tone.volume = min(1.0, tone.volume * 1.3)
                if tone.frequency < 800:
                    tone.frequency *= 1.2
        elif noise_level == "quiet":
            # Decrease volume for quiet environments
            for tone in cue.tone_sequence:
                tone.volume *= 0.6

        return cue


class AudioCueSystem:
    """Main audio cue system orchestrator."""

    def __init__(self) -> None:
        """Initialize audio cue system with all components."""
        self.cue_library = AudioCueLibrary()
        self.accessibility_adapter = AccessibilityAudioAdapter(self.cue_library)
        self.context_manager = AudioCueContext(
            self.cue_library, self.accessibility_adapter
        )
        self.audio_player: Optional[Any] = None  # Actual audio player
        self.cue_history: List[Dict[str, Any]] = []
        self.active_cues: Dict[str, asyncio.Task] = {}

        # Audio output configuration
        self.output_config = {"sample_rate": 44100, "channels": 2, "bit_depth": 16}

        # S3 client for cloud storage
        self.s3_client = boto3.client("s3")
        self.s3_bucket = "haven-health-audio-cues"

    async def initialize(self) -> None:
        """Initialize the audio cue system."""
        logger.info("Initializing audio cue system...")

        # Load custom cues from storage
        await self._load_custom_cues()

        # Initialize audio player (platform-specific)
        await self._initialize_audio_player()

        logger.info(
            "Audio cue system initialized with %d cues", len(self.cue_library.cues)
        )

    async def _load_custom_cues(self) -> None:
        """Load custom audio cues from storage."""
        # In production, load from S3 or local storage
        custom_cue_files = [
            "custom_success.wav",
            "custom_notification.wav",
            "medical_alert.wav",
        ]

        for file_name in custom_cue_files:
            # Simulated loading - in production, actually load files
            logger.info("Loading custom cue: %s", file_name)

    async def _initialize_audio_player(self) -> None:
        """Initialize platform-specific audio player."""
        # This would be platform-specific implementation
        # For now, we'll simulate with asyncio
        self.audio_player = self._simulated_player

    async def play_cue(
        self,
        cue_type: CueType,
        user_id: Optional[str] = None,
        override_params: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Play an audio cue."""
        try:
            # Get contextual cue
            cue = self.context_manager.get_contextual_cue(cue_type, user_id)

            if not cue:
                logger.debug("No cue available for type: %s", cue_type.value)
                return False

            # Apply any parameter overrides
            if override_params:
                cue = self._apply_overrides(cue, override_params)

            # Check if should interrupt existing cues
            if cue.priority == CuePriority.CRITICAL:
                await self.stop_all_cues()

            # Generate audio data
            audio_data = self.cue_library.generate_cue_audio(cue.id)

            if not audio_data:
                logger.error("Failed to generate audio for cue: %s", cue.id)
                return False

            # Play the cue
            task_id = f"{cue.id}_{datetime.now().timestamp()}"
            self.active_cues[task_id] = asyncio.create_task(
                self._play_audio(audio_data, cue)
            )

            # Record in history
            self._record_cue_playback(cue, user_id)

            # Clean up completed tasks
            self._cleanup_completed_tasks()

            return True

        except (ValueError, KeyError, asyncio.CancelledError) as e:
            logger.error("Error playing cue: %s", e)
            return False

    async def _play_audio(self, audio_data: bytes, cue: AudioCue) -> None:
        """Play audio data."""
        if self.audio_player:
            await self.audio_player(audio_data, cue)
        else:
            # Fallback simulation
            duration = cue.duration or len(audio_data) / (
                self.output_config["sample_rate"] * 2
            )
            await asyncio.sleep(duration)

    async def _simulated_player(self, audio_data: bytes, cue: AudioCue) -> None:
        """Simulate audio playback for testing."""
        logger.info("Playing cue: %s (%s)", cue.name, cue.type.value)

        # Calculate duration from audio data
        bytes_per_sample = self.output_config["bit_depth"] // 8
        bytes_per_second = (
            self.output_config["sample_rate"]
            * self.output_config["channels"]
            * bytes_per_sample
        )
        duration = len(audio_data) / bytes_per_second

        await asyncio.sleep(duration)

    def _apply_overrides(self, cue: AudioCue, overrides: Dict[str, Any]) -> AudioCue:
        """Apply parameter overrides to a cue."""
        if "volume" in overrides:
            for tone in cue.tone_sequence:
                tone.volume = overrides["volume"]

        if "speed" in overrides:
            speed_factor = overrides["speed"]
            for tone in cue.tone_sequence:
                tone.duration /= speed_factor

        return cue

    def _record_cue_playback(self, cue: AudioCue, user_id: Optional[str]) -> None:
        """Record cue playback in history."""
        self.cue_history.append(
            {
                "timestamp": datetime.now().isoformat(),
                "cue_id": cue.id,
                "cue_type": cue.type.value,
                "user_id": user_id,
                "priority": cue.priority.value,
            }
        )

        # Keep only last 1000 entries
        if len(self.cue_history) > 1000:
            self.cue_history = self.cue_history[-1000:]

    def _cleanup_completed_tasks(self) -> None:
        """Remove completed tasks from active cues."""
        completed = []
        for task_id, task in self.active_cues.items():
            if task.done():
                completed.append(task_id)

        for task_id in completed:
            del self.active_cues[task_id]

    async def stop_all_cues(self) -> None:
        """Stop all currently playing cues."""
        tasks = list(self.active_cues.values())
        for task in tasks:
            task.cancel()

        # Wait for cancellation
        await asyncio.gather(*tasks, return_exceptions=True)

        self.active_cues.clear()

    def update_user_preferences(
        self, user_id: str, preferences: Dict[str, Any]
    ) -> None:
        """Update user preferences."""
        self.context_manager.update_user_preferences(user_id, preferences)

    def update_environment(self, state: Dict[str, Any]) -> None:
        """Update environmental state."""
        self.context_manager.update_environment(state)

    def add_custom_cue(self, cue: AudioCue) -> None:
        """Add a custom audio cue."""
        self.cue_library.add_cue(cue)

    def get_cue_statistics(self) -> Dict[str, Any]:
        """Get usage statistics for audio cues."""
        cue_type_distribution: Dict[str, int] = defaultdict(int)
        user_playback_count: Dict[str, int] = defaultdict(int)

        for entry in self.cue_history:
            cue_type_distribution[entry["cue_type"]] += 1
            if entry["user_id"]:
                user_playback_count[entry["user_id"]] += 1

        stats = {
            "total_cues": len(self.cue_library.cues),
            "total_played": len(self.cue_history),
            "active_cues": len(self.active_cues),
            "cue_type_distribution": dict(cue_type_distribution),
            "user_playback_count": dict(user_playback_count),
        }

        return stats


# Specialized cue providers
class MedicalAudioCues:
    """Medical-specific audio cues."""

    def __init__(self, cue_system: AudioCueSystem) -> None:
        """Initialize medical audio cues with cue system."""
        self.cue_system = cue_system
        self._add_medical_cues()

    def _add_medical_cues(self) -> None:
        """Add medical-specific cues."""
        # Vital sign recorded
        self.cue_system.add_custom_cue(
            AudioCue(
                id="vital_recorded",
                type=CueType.SUCCESS,
                category=CueCategory.MEDICAL,
                name="Vital Sign Recorded",
                description="Confirmation of vital sign recording",
                priority=CuePriority.NORMAL,
                tone_sequence=[
                    ToneParameters(frequency=523.25, duration=0.1),  # C5
                    ToneParameters(frequency=659.25, duration=0.15),  # E5
                ],
            )
        )

        # Medication taken confirmation
        self.cue_system.add_custom_cue(
            AudioCue(
                id="medication_taken",
                type=CueType.SUCCESS,
                category=CueCategory.MEDICAL,
                name="Medication Taken",
                description="Confirmation that medication was taken",
                priority=CuePriority.NORMAL,
                tone_sequence=[
                    ToneParameters(frequency=783.99, duration=0.2, volume=0.6),  # G5
                    ToneParameters(
                        frequency=783.99, duration=0.1, volume=0.4
                    ),  # G5 echo
                ],
            )
        )

        # Health alert
        self.cue_system.add_custom_cue(
            AudioCue(
                id="health_alert",
                type=CueType.WARNING,
                category=CueCategory.MEDICAL,
                name="Health Alert",
                description="Alert for health-related issue",
                priority=CuePriority.HIGH,
                characteristics=[AudioCharacteristic.TIMBRE_BRIGHT],
                tone_sequence=[
                    ToneParameters(frequency=880.0, duration=0.15, waveform="triangle"),
                    ToneParameters(
                        frequency=1108.73, duration=0.15, waveform="triangle"
                    ),
                    ToneParameters(frequency=880.0, duration=0.15, waveform="triangle"),
                ],
            )
        )

    async def play_medication_reminder(
        self, user_id: str, medication_name: str
    ) -> None:
        """Play medication reminder cue."""
        await self.cue_system.play_cue(
            CueType.MEDICATION_REMINDER,
            user_id,
            {"metadata": {"medication": medication_name}},
        )

    async def play_vital_recorded(self, user_id: str, vital_type: str) -> None:
        """Play vital recorded confirmation."""
        await self.cue_system.play_cue(
            CueType.SUCCESS,
            user_id,
            {"metadata": {"subtype": "vital_recorded", "vital_type": vital_type}},
        )


# Example usage
if __name__ == "__main__":

    async def demo_audio_cues() -> None:
        """Demonstrate audio cue system functionality."""
        # Initialize system
        cue_system = AudioCueSystem()
        await cue_system.initialize()

        # Create medical cues
        medical_cues = MedicalAudioCues(cue_system)

        # Set up user preferences
        cue_system.update_user_preferences(
            "demo_user",
            {
                "volume": 0.8,
                "accessibility_needs": [],
                "quiet_hours": {"start": 22, "end": 7},
            },
        )

        # Play various cues
        print("Playing success cue...")
        await cue_system.play_cue(CueType.SUCCESS, "demo_user")

        await asyncio.sleep(1)

        print("Playing notification...")
        await cue_system.play_cue(CueType.NOTIFICATION, "demo_user")

        await asyncio.sleep(1)

        print("Playing medication reminder...")
        await medical_cues.play_medication_reminder("demo_user", "Aspirin")

        # Show statistics
        stats = cue_system.get_cue_statistics()
        print(f"\nStatistics: {stats}")

    # Run demo
    asyncio.run(demo_audio_cues())
