"""Voice Profile Management Module.

This module manages user voice profiles for the Haven Health Passport system,
including voice preferences, settings, language choices, accessibility options,
and personalization features.
"""

import dataclasses
import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

from src.healthcare.hipaa_access_control import (
    AccessLevel,
    audit_phi_access,
    require_phi_access,
)
from src.services.encryption_service import EncryptionService
from src.storage.secure_storage import SecureStorage
from src.voice.accent_adaptation import AccentProfile, AccentRegion
from src.voice.interface.voice_authentication import (
    AuthenticationMethod,
    VoicePrint,
)
from src.voice.language_codes import LanguageCode
from src.voice.speaker_profile import SpeakerProfile

logger = logging.getLogger(__name__)


class VoiceGender(Enum):
    """Voice gender preferences for synthesis."""

    MALE = "male"
    FEMALE = "female"
    NEUTRAL = "neutral"
    NOT_SPECIFIED = "not_specified"


class SpeechRate(Enum):
    """Speech rate preferences."""

    VERY_SLOW = 0.5
    SLOW = 0.75
    NORMAL = 1.0
    FAST = 1.25
    VERY_FAST = 1.5


class AudioQuality(Enum):
    """Audio quality settings."""

    LOW = "low"  # 8kHz, lower bandwidth
    MEDIUM = "medium"  # 16kHz, standard
    HIGH = "high"  # 24kHz, high quality
    ULTRA = "ultra"  # 48kHz, ultra quality


class AccessibilityFeature(Enum):
    """Accessibility features for voice interaction."""

    VISUAL_IMPAIRMENT = "visual_impairment"
    HEARING_IMPAIRMENT = "hearing_impairment"
    COGNITIVE_SUPPORT = "cognitive_support"
    MOTOR_IMPAIRMENT = "motor_impairment"
    SPEECH_IMPAIRMENT = "speech_impairment"
    ELDERLY_MODE = "elderly_mode"


@dataclass
class VoicePreferences:
    """User's voice interaction preferences."""

    primary_language: LanguageCode = LanguageCode.EN_US
    secondary_languages: List[LanguageCode] = field(default_factory=list)
    preferred_accent: Optional[AccentRegion] = None
    speech_rate: SpeechRate = SpeechRate.NORMAL
    voice_gender: VoiceGender = VoiceGender.NOT_SPECIFIED
    audio_quality: AudioQuality = AudioQuality.MEDIUM
    volume_level: float = 1.0  # 0.0 to 2.0
    enable_voice_feedback: bool = True
    enable_sound_effects: bool = True
    enable_haptic_feedback: bool = True
    wake_word_enabled: bool = True
    wake_word_phrase: str = "Hey Haven"
    continuous_listening: bool = False
    noise_suppression: bool = True
    echo_cancellation: bool = True

    def to_dict(self) -> Dict[str, Any]:
        """Convert preferences to dictionary."""
        return {
            "primary_language": self.primary_language.value,
            "secondary_languages": [lang.value for lang in self.secondary_languages],
            "preferred_accent": (
                self.preferred_accent.value if self.preferred_accent else None
            ),
            "speech_rate": self.speech_rate.value,
            "voice_gender": self.voice_gender.value,
            "audio_quality": self.audio_quality.value,
            "volume_level": self.volume_level,
            "enable_voice_feedback": self.enable_voice_feedback,
            "enable_sound_effects": self.enable_sound_effects,
            "enable_haptic_feedback": self.enable_haptic_feedback,
            "wake_word_enabled": self.wake_word_enabled,
            "wake_word_phrase": self.wake_word_phrase,
            "continuous_listening": self.continuous_listening,
            "noise_suppression": self.noise_suppression,
            "echo_cancellation": self.echo_cancellation,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "VoicePreferences":
        """Create preferences from dictionary."""
        return cls(
            primary_language=LanguageCode(data.get("primary_language", "en-US")),
            secondary_languages=[
                LanguageCode(lang) for lang in data.get("secondary_languages", [])
            ],
            preferred_accent=(
                AccentRegion(data["preferred_accent"])
                if data.get("preferred_accent")
                else None
            ),
            speech_rate=SpeechRate(data.get("speech_rate", 1.0)),
            voice_gender=VoiceGender(data.get("voice_gender", "not_specified")),
            audio_quality=AudioQuality(data.get("audio_quality", "medium")),
            volume_level=data.get("volume_level", 1.0),
            enable_voice_feedback=data.get("enable_voice_feedback", True),
            enable_sound_effects=data.get("enable_sound_effects", True),
            enable_haptic_feedback=data.get("enable_haptic_feedback", True),
            wake_word_enabled=data.get("wake_word_enabled", True),
            wake_word_phrase=data.get("wake_word_phrase", "Hey Haven"),
            continuous_listening=data.get("continuous_listening", False),
            noise_suppression=data.get("noise_suppression", True),
            echo_cancellation=data.get("echo_cancellation", True),
        )


@dataclass
class AccessibilitySettings:
    """Accessibility settings for voice interaction."""

    enabled_features: Set[AccessibilityFeature] = field(default_factory=set)
    high_contrast_voice_ui: bool = False
    voice_guidance_level: str = "normal"  # minimal, normal, detailed
    repeat_confirmations: bool = False
    extended_timeouts: bool = False
    simplified_commands: bool = False
    phonetic_spelling: bool = False
    number_word_conversion: bool = False  # "123" -> "one two three"
    clear_enunciation: bool = False
    background_description: bool = False  # Describe background sounds
    emotional_tone_description: bool = False  # Describe speaker emotions

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "enabled_features": [f.value for f in self.enabled_features],
            "high_contrast_voice_ui": self.high_contrast_voice_ui,
            "voice_guidance_level": self.voice_guidance_level,
            "repeat_confirmations": self.repeat_confirmations,
            "extended_timeouts": self.extended_timeouts,
            "simplified_commands": self.simplified_commands,
            "phonetic_spelling": self.phonetic_spelling,
            "number_word_conversion": self.number_word_conversion,
            "clear_enunciation": self.clear_enunciation,
            "background_description": self.background_description,
            "emotional_tone_description": self.emotional_tone_description,
        }


@dataclass
class VoiceAnalytics:
    """Analytics data for voice usage."""

    total_interactions: int = 0
    successful_commands: int = 0
    failed_commands: int = 0
    average_confidence: float = 0.0
    most_used_commands: Dict[str, int] = field(default_factory=dict)
    language_usage: Dict[str, int] = field(default_factory=dict)
    daily_usage_pattern: Dict[int, int] = field(default_factory=dict)  # hour -> count
    average_session_duration: float = 0.0
    last_interaction: Optional[datetime] = None
    error_types: Dict[str, int] = field(default_factory=dict)

    def record_interaction(
        self, command: str, success: bool, confidence: float, language: str
    ) -> None:
        """Record a voice interaction."""
        self.total_interactions += 1

        if success:
            self.successful_commands += 1
        else:
            self.failed_commands += 1

        # Update average confidence
        self.average_confidence = (
            self.average_confidence * (self.total_interactions - 1) + confidence
        ) / self.total_interactions

        # Track command usage
        self.most_used_commands[command] = self.most_used_commands.get(command, 0) + 1

        # Track language usage
        self.language_usage[language] = self.language_usage.get(language, 0) + 1

        # Track hourly pattern
        hour = datetime.now().hour
        self.daily_usage_pattern[hour] = self.daily_usage_pattern.get(hour, 0) + 1

        self.last_interaction = datetime.now()

    def get_success_rate(self) -> float:
        """Calculate command success rate."""
        if self.total_interactions == 0:
            return 0.0
        return self.successful_commands / self.total_interactions


@dataclass
class VoiceProfile:
    """Complete voice profile for a user."""

    profile_id: str
    user_id: str
    preferences: VoicePreferences
    accessibility: AccessibilitySettings
    voice_prints: Dict[str, VoicePrint] = field(default_factory=dict)  # method -> print
    speaker_profile: Optional[SpeakerProfile] = None
    accent_profile: Optional[AccentProfile] = None
    analytics: VoiceAnalytics = field(default_factory=VoiceAnalytics)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    is_active: bool = True
    version: int = 1
    custom_vocabulary: List[str] = field(default_factory=list)
    blocked_commands: List[str] = field(default_factory=list)
    trusted_devices: List[str] = field(default_factory=list)
    privacy_settings: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert profile to dictionary."""
        return {
            "profile_id": self.profile_id,
            "user_id": self.user_id,
            "preferences": self.preferences.to_dict(),
            "accessibility": self.accessibility.to_dict(),
            "voice_prints": {
                method: vp.to_dict() for method, vp in self.voice_prints.items()
            },
            "speaker_profile": (
                dataclasses.asdict(self.speaker_profile)
                if self.speaker_profile
                else None
            ),
            "accent_profile": (
                self.accent_profile.to_dict() if self.accent_profile else None
            ),
            "analytics": {
                "total_interactions": self.analytics.total_interactions,
                "success_rate": self.analytics.get_success_rate(),
                "average_confidence": self.analytics.average_confidence,
                "last_interaction": (
                    self.analytics.last_interaction.isoformat()
                    if self.analytics.last_interaction
                    else None
                ),
            },
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "is_active": self.is_active,
            "version": self.version,
            "custom_vocabulary": self.custom_vocabulary,
            "blocked_commands": self.blocked_commands,
            "trusted_devices": self.trusted_devices,
            "privacy_settings": self.privacy_settings,
        }

    def add_voice_print(
        self, method: AuthenticationMethod, voice_print: VoicePrint
    ) -> None:
        """Add or update a voice print."""
        self.voice_prints[method.value] = voice_print
        self.updated_at = datetime.now()
        self.version += 1

    def update_preferences(self, preferences: VoicePreferences) -> None:
        """Update voice preferences."""
        self.preferences = preferences
        self.updated_at = datetime.now()
        self.version += 1

    def enable_accessibility_feature(self, feature: AccessibilityFeature) -> None:
        """Enable an accessibility feature."""
        self.accessibility.enabled_features.add(feature)
        self.updated_at = datetime.now()
        self.version += 1

    def disable_accessibility_feature(self, feature: AccessibilityFeature) -> None:
        """Disable an accessibility feature."""
        self.accessibility.enabled_features.discard(feature)
        self.updated_at = datetime.now()
        self.version += 1


class VoiceProfileManager:
    """Manages voice profiles for all users."""

    def __init__(
        self,
        storage: Optional[SecureStorage] = None,
        encryption_service: Optional[EncryptionService] = None,
    ):
        """Initialize the voice profile manager.

        Args:
            storage: Secure storage service for persisting profiles
            encryption_service: Service for encrypting profile data
        """
        self.storage = storage
        self.encryption_service = encryption_service
        self.profiles: Dict[str, VoiceProfile] = {}
        self.profile_cache_ttl = timedelta(hours=1)
        self.last_cache_update: Dict[str, datetime] = {}

    @require_phi_access(AccessLevel.WRITE)
    @audit_phi_access(action="create_voice_profile")
    async def create_profile(
        self, user_id: str, preferences: Optional[VoicePreferences] = None
    ) -> VoiceProfile:
        """Create a new voice profile for a user."""
        profile_id = str(uuid.uuid4())

        profile = VoiceProfile(
            profile_id=profile_id,
            user_id=user_id,
            preferences=preferences or VoicePreferences(),
            accessibility=AccessibilitySettings(),
        )

        # Store profile
        self.profiles[user_id] = profile

        # Persist to storage
        if self.storage:
            await self._save_profile(profile)

        logger.info("Created voice profile for user %s", user_id)

        return profile

    @require_phi_access(AccessLevel.READ)
    @audit_phi_access(action="get_voice_profile")
    async def get_profile(self, user_id: str) -> Optional[VoiceProfile]:
        """Get user's voice profile."""
        # Check cache
        if user_id in self.profiles:
            # Check if cache is still valid
            if user_id in self.last_cache_update:
                if (
                    datetime.now() - self.last_cache_update[user_id]
                    < self.profile_cache_ttl
                ):
                    return self.profiles[user_id]

        # Load from storage
        if self.storage:
            profile = await self._load_profile(user_id)
            if profile:
                self.profiles[user_id] = profile
                self.last_cache_update[user_id] = datetime.now()
                return profile

        return None

    @require_phi_access(AccessLevel.WRITE)
    @audit_phi_access(action="update_voice_profile")
    async def update_profile(
        self, user_id: str, updates: Dict[str, Any]
    ) -> Optional[VoiceProfile]:
        """Update user's voice profile."""
        profile: Optional[VoiceProfile] = await self.get_profile(user_id)
        if not profile:
            return None

        # Apply updates
        if "preferences" in updates:
            profile.update_preferences(
                VoicePreferences.from_dict(updates["preferences"])
            )

        if "accessibility" in updates:
            profile.accessibility = AccessibilitySettings(**updates["accessibility"])
            profile.updated_at = datetime.now()
            profile.version += 1

        if "custom_vocabulary" in updates:
            profile.custom_vocabulary = updates["custom_vocabulary"]
            profile.updated_at = datetime.now()
            profile.version += 1

        if "blocked_commands" in updates:
            profile.blocked_commands = updates["blocked_commands"]
            profile.updated_at = datetime.now()
            profile.version += 1

        if "privacy_settings" in updates:
            profile.privacy_settings.update(updates["privacy_settings"])
            profile.updated_at = datetime.now()
            profile.version += 1

        # Save updates
        if self.storage:
            await self._save_profile(profile)

        return profile

    async def delete_profile(self, user_id: str) -> bool:
        """Delete user's voice profile."""
        if user_id in self.profiles:
            del self.profiles[user_id]

        if user_id in self.last_cache_update:
            del self.last_cache_update[user_id]

        # Delete from storage
        if self.storage:
            return await self._delete_profile(user_id)

        return True

    async def add_custom_vocabulary(self, user_id: str, words: List[str]) -> bool:
        """Add custom vocabulary words to user's profile."""
        profile = await self.get_profile(user_id)
        if not profile:
            return False

        # Add unique words
        existing = set(profile.custom_vocabulary)
        new_words = [w for w in words if w not in existing]

        if new_words:
            profile.custom_vocabulary.extend(new_words)
            profile.updated_at = datetime.now()
            profile.version += 1

            if self.storage:
                await self._save_profile(profile)

        return True

    async def block_command(self, user_id: str, command: str) -> bool:
        """Block a specific command for user."""
        profile = await self.get_profile(user_id)
        if not profile:
            return False

        if command not in profile.blocked_commands:
            profile.blocked_commands.append(command)
            profile.updated_at = datetime.now()
            profile.version += 1

            if self.storage:
                await self._save_profile(profile)

        return True

    async def unblock_command(self, user_id: str, command: str) -> bool:
        """Unblock a specific command for user."""
        profile = await self.get_profile(user_id)
        if not profile:
            return False

        if command in profile.blocked_commands:
            profile.blocked_commands.remove(command)
            profile.updated_at = datetime.now()
            profile.version += 1

            if self.storage:
                await self._save_profile(profile)

        return True

    async def add_trusted_device(self, user_id: str, device_id: str) -> bool:
        """Add a trusted device for voice authentication."""
        profile = await self.get_profile(user_id)
        if not profile:
            return False

        if device_id not in profile.trusted_devices:
            profile.trusted_devices.append(device_id)
            profile.updated_at = datetime.now()
            profile.version += 1

            if self.storage:
                await self._save_profile(profile)

        return True

    async def record_interaction(
        self,
        user_id: str,
        command: str,
        success: bool,
        confidence: float,
        language: str,
        error_type: Optional[str] = None,
    ) -> None:
        """Record a voice interaction in user's analytics."""
        profile = await self.get_profile(user_id)
        if not profile:
            return

        profile.analytics.record_interaction(command, success, confidence, language)

        if error_type and not success:
            profile.analytics.error_types[error_type] = (
                profile.analytics.error_types.get(error_type, 0) + 1
            )

        # Save periodically (every 10 interactions)
        if profile.analytics.total_interactions % 10 == 0:
            if self.storage:
                await self._save_profile(profile)

    async def get_analytics_summary(self, user_id: str) -> Dict[str, Any]:
        """Get analytics summary for user."""
        profile = await self.get_profile(user_id)
        if not profile:
            return {}

        analytics = profile.analytics

        # Get top commands
        top_commands = sorted(
            analytics.most_used_commands.items(), key=lambda x: x[1], reverse=True
        )[:5]

        # Get peak usage hours
        peak_hours = sorted(
            analytics.daily_usage_pattern.items(), key=lambda x: x[1], reverse=True
        )[:3]

        return {
            "total_interactions": analytics.total_interactions,
            "success_rate": analytics.get_success_rate(),
            "average_confidence": analytics.average_confidence,
            "top_commands": top_commands,
            "primary_language": (
                max(analytics.language_usage.items(), key=lambda x: x[1])[0]
                if analytics.language_usage
                else None
            ),
            "peak_usage_hours": [h[0] for h in peak_hours],
            "last_interaction": (
                analytics.last_interaction.isoformat()
                if analytics.last_interaction
                else None
            ),
            "common_errors": sorted(
                analytics.error_types.items(), key=lambda x: x[1], reverse=True
            )[:3],
        }

    async def export_profile(self, user_id: str) -> Dict[str, Any]:
        """Export user's complete voice profile."""
        profile: Optional[VoiceProfile] = await self.get_profile(user_id)
        if not profile:
            return {}

        return profile.to_dict()

    async def import_profile(self, user_id: str, profile_data: Dict[str, Any]) -> bool:
        """Import a voice profile from exported data."""
        try:
            # Create profile from data
            profile = VoiceProfile(
                profile_id=profile_data.get("profile_id", str(uuid.uuid4())),
                user_id=user_id,
                preferences=VoicePreferences.from_dict(
                    profile_data.get("preferences", {})
                ),
                accessibility=AccessibilitySettings(
                    **profile_data.get("accessibility", {})
                ),
                created_at=datetime.fromisoformat(
                    profile_data.get("created_at", datetime.now().isoformat())
                ),
                updated_at=datetime.now(),
                is_active=profile_data.get("is_active", True),
                version=profile_data.get("version", 1) + 1,
                custom_vocabulary=profile_data.get("custom_vocabulary", []),
                blocked_commands=profile_data.get("blocked_commands", []),
                trusted_devices=profile_data.get("trusted_devices", []),
                privacy_settings=profile_data.get("privacy_settings", {}),
            )

            # Store profile
            self.profiles[user_id] = profile

            if self.storage:
                await self._save_profile(profile)

            return True

        except (ValueError, KeyError) as e:
            logger.error("Failed to import profile: %s", str(e))
            return False

    # Storage methods

    async def _save_profile(self, profile: VoiceProfile) -> None:
        """Save profile to secure storage."""
        if not self.storage:
            return

        # Serialize profile
        profile_data = json.dumps(profile.to_dict())

        # Encrypt if service available
        if self.encryption_service:
            profile_data = self.encryption_service.encrypt(profile_data)

        # Save to storage
        key = f"voice_profile:{profile.user_id}"
        self.storage.store(key, profile_data)

    async def _load_profile(self, user_id: str) -> Optional[VoiceProfile]:
        """Load profile from secure storage."""
        if not self.storage:
            return None

        key = f"voice_profile:{user_id}"
        profile_data = self.storage.retrieve(key)

        if not profile_data:
            return None

        # Decrypt if needed
        if self.encryption_service and isinstance(profile_data, bytes):
            profile_data = self.encryption_service.decrypt(profile_data.decode())
            # profile_data is already a string after decrypt

        # Deserialize
        try:
            data = json.loads(profile_data)
            # Import the profile
            success = await self.import_profile(user_id, data)
            if success:
                return self.profiles.get(user_id)
            return None
        except (ValueError, json.JSONDecodeError) as e:
            logger.error("Failed to load profile: %s", str(e))
            return None

    async def _delete_profile(self, user_id: str) -> bool:
        """Delete profile from storage."""
        if not self.storage:
            return True

        key = f"voice_profile:{user_id}"
        return self.storage.delete(key)


class VoiceProfileMigration:
    """Handles voice profile migrations between versions."""

    @staticmethod
    def migrate_v1_to_v2(profile_data: Dict[str, Any]) -> Dict[str, Any]:
        """Migrate profile from v1 to v2 format."""
        # Add new fields with defaults
        if "accessibility" not in profile_data:
            profile_data["accessibility"] = AccessibilitySettings().to_dict()

        if "analytics" not in profile_data:
            profile_data["analytics"] = {}

        if "privacy_settings" not in profile_data:
            profile_data["privacy_settings"] = {}

        profile_data["version"] = 2

        return profile_data

    @staticmethod
    def migrate_profile(profile_data: Dict[str, Any]) -> Dict[str, Any]:
        """Migrate profile to latest version."""
        version = profile_data.get("version", 1)

        if version < 2:
            profile_data = VoiceProfileMigration.migrate_v1_to_v2(profile_data)

        # Add future migrations here

        return profile_data


# Preset profiles for common use cases
class VoiceProfilePresets:
    """Predefined voice profile configurations."""

    @staticmethod
    def elderly_profile() -> VoicePreferences:
        """Profile optimized for elderly users."""
        return VoicePreferences(
            speech_rate=SpeechRate.SLOW,
            volume_level=1.5,
            enable_voice_feedback=True,
            enable_sound_effects=True,
            continuous_listening=False,
            noise_suppression=True,
        )

    @staticmethod
    def visually_impaired_profile() -> Tuple[VoicePreferences, AccessibilitySettings]:
        """Profile optimized for visually impaired users."""
        preferences = VoicePreferences(
            speech_rate=SpeechRate.NORMAL,
            enable_voice_feedback=True,
            enable_sound_effects=True,
            enable_haptic_feedback=True,
        )

        accessibility = AccessibilitySettings(
            enabled_features={AccessibilityFeature.VISUAL_IMPAIRMENT},
            voice_guidance_level="detailed",
            repeat_confirmations=True,
            phonetic_spelling=True,
            background_description=True,
        )

        return preferences, accessibility

    @staticmethod
    def multilingual_profile(languages: List[LanguageCode]) -> VoicePreferences:
        """Profile for multilingual users."""
        return VoicePreferences(
            primary_language=languages[0] if languages else LanguageCode.EN_US,
            secondary_languages=languages[1:] if len(languages) > 1 else [],
            speech_rate=SpeechRate.NORMAL,
        )

    @staticmethod
    def privacy_focused_profile() -> Tuple[VoicePreferences, Dict[str, Any]]:
        """Profile with enhanced privacy settings."""
        preferences = VoicePreferences(
            wake_word_enabled=False, continuous_listening=False
        )

        privacy_settings = {
            "store_recordings": False,
            "share_analytics": False,
            "local_processing_only": True,
            "auto_delete_after_days": 7,
            "require_explicit_consent": True,
        }

        return preferences, privacy_settings


# Example usage
if __name__ == "__main__":
    import asyncio

    async def demo_profile_management() -> None:
        """Demonstrate voice profile management functionality."""
        # Initialize manager
        manager = VoiceProfileManager()

        # Create a new profile
        user_id = "user123"
        profile = await manager.create_profile(user_id)
        print(f"Created profile: {profile.profile_id}")

        # Update preferences
        new_preferences = VoicePreferences(
            primary_language=LanguageCode.ES_US,
            speech_rate=SpeechRate.SLOW,
            voice_gender=VoiceGender.FEMALE,
        )

        await manager.update_profile(
            user_id, {"preferences": new_preferences.to_dict()}
        )
        print("Updated preferences")

        # Enable accessibility features
        profile = await manager.get_profile(user_id)
        profile.enable_accessibility_feature(AccessibilityFeature.VISUAL_IMPAIRMENT)
        profile.enable_accessibility_feature(AccessibilityFeature.ELDERLY_MODE)

        # Add custom vocabulary
        await manager.add_custom_vocabulary(
            user_id, ["metformin", "hypertension", "Dr. Johnson"]
        )

        # Record some interactions
        await manager.record_interaction(
            user_id,
            "check_medications",
            success=True,
            confidence=0.92,
            language="es-US",
        )

        await manager.record_interaction(
            user_id,
            "schedule_appointment",
            success=False,
            confidence=0.45,
            language="es-US",
            error_type="low_confidence",
        )

        # Get analytics
        analytics = await manager.get_analytics_summary(user_id)
        print(f"Analytics: {analytics}")

        # Export profile
        exported = await manager.export_profile(user_id)
        print(f"Exported profile with {len(exported)} fields")

        # Apply preset
        elderly_prefs = VoiceProfilePresets.elderly_profile()
        await manager.update_profile(user_id, {"preferences": elderly_prefs.to_dict()})
        print("Applied elderly preset")

    # Run demo
    asyncio.run(demo_profile_management())
