"""Audio Localization System.

This module provides comprehensive audio localization including translations,
guides, alerts, cultural sounds, and accessibility features.

This module handles PHI with encryption and access control to ensure HIPAA compliance.
It includes FHIR Resource typing and validation for healthcare data.
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from src.healthcare.fhir.validators import FHIRValidator
from src.security.access_control import AccessPermission, require_permission
from src.security.audit import audit_phi_access
from src.security.encryption import EncryptionService
from src.utils.logging import get_logger

logger = get_logger(__name__)


class AudioType(str, Enum):
    """Types of audio content."""

    GUIDE = "guide"  # Audio guides/tutorials
    ALERT = "alert"  # Alert sounds
    NOTIFICATION = "notification"  # Notification sounds
    CONFIRMATION = "confirmation"  # Success/confirmation sounds
    ERROR = "error"  # Error sounds
    CULTURAL = "cultural"  # Culturally specific sounds
    ACCESSIBILITY = "accessibility"  # Screen reader audio
    AMBIENT = "ambient"  # Background/ambient sounds
    INSTRUCTION = "instruction"  # Medical instructions


class AudioPriority(str, Enum):
    """Audio playback priority."""

    CRITICAL = "critical"  # Emergency alerts
    HIGH = "high"  # Important notifications
    NORMAL = "normal"  # Regular sounds
    LOW = "low"  # Background sounds


class CulturalSoundType(str, Enum):
    """Types of cultural sounds."""

    PRAYER_CALL = "prayer_call"
    GREETING = "greeting"
    CELEBRATION = "celebration"
    COMFORT = "comfort"
    RESPECT = "respect"


@dataclass
class LocalizedAudio:
    """Localized audio resource."""

    audio_id: str
    type: AudioType
    default_url: str
    localized_urls: Dict[str, str]  # language/culture -> URL
    descriptions: Dict[str, str]  # language -> description
    duration_seconds: float
    priority: AudioPriority
    cultural_appropriateness: Dict[str, bool] = field(default_factory=dict)
    accessibility_text: Dict[str, str] = field(default_factory=dict)


@dataclass
class AudioGuide:
    """Audio guide for app features."""

    guide_id: str
    feature: str
    audio_urls: Dict[str, str]  # language -> URL
    transcripts: Dict[str, str]  # language -> text transcript
    duration: Dict[str, float]  # language -> duration
    steps: List[str]  # Guide steps/sections
    prerequisites: List[str] = field(default_factory=list)


@dataclass
class ScreenReaderContent:
    """Screen reader specific content."""

    element_id: str
    element_type: str  # button, input, image, etc.
    labels: Dict[str, str]  # language -> label
    descriptions: Dict[str, str]  # language -> description
    hints: Dict[str, str]  # language -> interaction hint
    shortcuts: Optional[Dict[str, str]] = None


class AudioLocalizationManager:
    """Manages audio localization for healthcare app."""

    # Localized audio database
    AUDIO_LIBRARY = {
        # Alert sounds
        "emergency_alert": LocalizedAudio(
            audio_id="emergency_alert",
            type=AudioType.ALERT,
            default_url="audio/alerts/emergency_default.mp3",
            localized_urls={
                "en": "audio/alerts/emergency_en.mp3",
                "ar": "audio/alerts/emergency_ar.mp3",  # Different tone for cultural preference
                "hi": "audio/alerts/emergency_hi.mp3",
            },
            descriptions={
                "en": "Emergency medical alert",
                "ar": "تنبيه طبي طارئ",
                "es": "Alerta médica de emergencia",
                "hi": "आपातकालीन चिकित्सा चेतावनी",
            },
            duration_seconds=2.5,
            priority=AudioPriority.CRITICAL,
            accessibility_text={
                "en": "Emergency alert sound playing",
                "ar": "يتم تشغيل صوت التنبيه الطارئ",
            },
        ),
        # Notification sounds
        "appointment_reminder": LocalizedAudio(
            audio_id="appointment_reminder",
            type=AudioType.NOTIFICATION,
            default_url="audio/notifications/appointment_default.mp3",
            localized_urls={
                "en": "audio/notifications/appointment_gentle.mp3",
                "ar": "audio/notifications/appointment_melodic.mp3",
                "hi": "audio/notifications/appointment_traditional.mp3",
            },
            descriptions={
                "en": "Appointment reminder notification",
                "ar": "تذكير بالموعد",
                "es": "Recordatorio de cita",
            },
            duration_seconds=1.5,
            priority=AudioPriority.NORMAL,
        ),
        # Confirmation sounds
        "task_complete": LocalizedAudio(
            audio_id="task_complete",
            type=AudioType.CONFIRMATION,
            default_url="audio/confirmations/complete_default.mp3",
            localized_urls={
                "en": "audio/confirmations/complete_chime.mp3",
                "ar": "audio/confirmations/complete_soft.mp3",
                "ja": "audio/confirmations/complete_zen.mp3",
            },
            descriptions={
                "en": "Task completed successfully",
                "ar": "تمت المهمة بنجاح",
            },
            duration_seconds=0.8,
            priority=AudioPriority.NORMAL,
        ),
        # Error sounds
        "input_error": LocalizedAudio(
            audio_id="input_error",
            type=AudioType.ERROR,
            default_url="audio/errors/input_default.mp3",
            localized_urls={
                "en": "audio/errors/input_subtle.mp3",
                "ar": "audio/errors/input_gentle.mp3",
            },
            descriptions={
                "en": "Input validation error",
                "ar": "خطأ في التحقق من الإدخال",
            },
            duration_seconds=0.5,
            priority=AudioPriority.NORMAL,
            cultural_appropriateness={
                "middle_eastern": True,  # Softer error sounds
                "south_asian": True,
            },
        ),
    }

    # Cultural sound library
    CULTURAL_SOUNDS = {
        "prayer_time": {
            "islamic": LocalizedAudio(
                audio_id="prayer_time_islamic",
                type=AudioType.CULTURAL,
                default_url="audio/cultural/prayer_notification.mp3",
                localized_urls={
                    "ar": "audio/cultural/adhan_notification.mp3",
                    "ur": "audio/cultural/namaz_time.mp3",
                },
                descriptions={
                    "en": "Prayer time notification",
                    "ar": "حان وقت الصلاة",
                    "ur": "نماز کا وقت",
                },
                duration_seconds=3.0,
                priority=AudioPriority.HIGH,
                cultural_appropriateness={"middle_eastern": True, "south_asian": True},
            )
        },
        "greeting": {
            "general": LocalizedAudio(
                audio_id="greeting_general",
                type=AudioType.CULTURAL,
                default_url="audio/cultural/greeting_default.mp3",
                localized_urls={
                    "ar": "audio/cultural/greeting_arabic.mp3",
                    "hi": "audio/cultural/greeting_namaste.mp3",
                    "sw": "audio/cultural/greeting_swahili.mp3",
                },
                descriptions={
                    "en": "Welcome greeting",
                    "ar": "تحية ترحيب",
                    "hi": "स्वागत अभिवादन",
                },
                duration_seconds=1.5,
                priority=AudioPriority.LOW,
            )
        },
    }

    # Audio guides for app features
    AUDIO_GUIDES = {
        "registration_guide": AudioGuide(
            guide_id="registration_guide",
            feature="patient_registration",
            audio_urls={
                "en": "audio/guides/registration_en.mp3",
                "es": "audio/guides/registration_es.mp3",
                "ar": "audio/guides/registration_ar.mp3",
                "hi": "audio/guides/registration_hi.mp3",
            },
            transcripts={
                "en": "Welcome to patient registration. We'll guide you through the process step by step...",
                "es": "Bienvenido al registro de pacientes. Le guiaremos paso a paso...",
                "ar": "مرحباً بك في تسجيل المرضى. سنرشدك خلال العملية خطوة بخطوة...",
                "hi": "रोगी पंजीकरण में आपका स्वागत है। हम आपको चरण दर चरण मार्गदर्शन करेंगे...",
            },
            duration={"en": 45.0, "es": 48.0, "ar": 50.0, "hi": 47.0},
            steps=[
                "introduction",
                "personal_information",
                "medical_history",
                "contact_details",
                "confirmation",
            ],
        ),
        "medication_guide": AudioGuide(
            guide_id="medication_guide",
            feature="medication_instructions",
            audio_urls={
                "en": "audio/guides/medication_en.mp3",
                "es": "audio/guides/medication_es.mp3",
                "ar": "audio/guides/medication_ar.mp3",
            },
            transcripts={
                "en": "This guide will help you understand your medication instructions...",
                "es": "Esta guía le ayudará a entender las instrucciones de su medicamento...",
                "ar": "سيساعدك هذا الدليل على فهم تعليمات الدواء الخاصة بك...",
            },
            duration={"en": 60.0, "es": 65.0, "ar": 62.0},
            steps=[
                "medication_name",
                "dosage",
                "timing",
                "side_effects",
                "precautions",
            ],
        ),
    }

    # Screen reader content
    SCREEN_READER_CONTENT = {
        "main_menu_button": ScreenReaderContent(
            element_id="main_menu_button",
            element_type="button",
            labels={
                "en": "Main menu",
                "es": "Menú principal",
                "ar": "القائمة الرئيسية",
                "hi": "मुख्य मेनू",
            },
            descriptions={
                "en": "Opens the main navigation menu",
                "es": "Abre el menú de navegación principal",
                "ar": "يفتح قائمة التنقل الرئيسية",
            },
            hints={
                "en": "Double tap to open menu",
                "es": "Toque dos veces para abrir el menú",
                "ar": "انقر مرتين لفتح القائمة",
            },
            shortcuts={"en": "Alt+M", "ar": "Alt+M"},
        ),
        "patient_photo": ScreenReaderContent(
            element_id="patient_photo",
            element_type="image",
            labels={
                "en": "Patient photograph",
                "es": "Fotografía del paciente",
                "ar": "صورة المريض",
            },
            descriptions={
                "en": "Profile photo of the patient",
                "es": "Foto de perfil del paciente",
                "ar": "صورة الملف الشخصي للمريض",
            },
            hints={
                "en": "Double tap to view full size",
                "es": "Toque dos veces para ver en tamaño completo",
                "ar": "انقر مرتين لعرض الحجم الكامل",
            },
        ),
    }

    def __init__(self) -> None:
        """Initialize audio localization manager."""
        self.user_preferences: Dict[str, Dict[str, Any]] = {}
        self.audio_cache: Dict[str, bytes] = {}
        self.culture_mapping = {
            "ar": "middle_eastern",
            "ur": "south_asian",
            "hi": "south_asian",
            "bn": "south_asian",
            "sw": "east_african",
        }
        self.fhir_validator = FHIRValidator()
        self.encryption_service = EncryptionService(
            kms_key_id="alias/haven-health-default"
        )

    def validate_fhir_resource(self, resource: dict) -> bool:
        """Validate FHIR resource structure and requirements."""
        # Resource type could be used for type-specific validation
        # resource_type = resource.get("resourceType", "")
        return self.fhir_validator.validate_resource(resource)

    @audit_phi_access("process_phi_data")
    @require_permission(AccessPermission.READ_PHI)
    def process_with_phi_protection(self, data: dict) -> dict:
        """Process data with PHI protection and audit logging."""
        # Encrypt sensitive fields
        sensitive_fields = ["name", "birthDate", "ssn", "address"]
        encrypted_data = data.copy()

        for field_name in sensitive_fields:
            if field_name in encrypted_data:
                encrypted_data[field_name] = self.encryption_service.encrypt(
                    str(encrypted_data[field_name]).encode()
                )

        return encrypted_data

    def get_localized_audio(
        self, audio_id: str, language: str, culture_code: Optional[str] = None
    ) -> Optional[LocalizedAudio]:
        """Get localized audio for a specific language/culture."""
        # Check main audio library
        audio = self.AUDIO_LIBRARY.get(audio_id)

        # Check cultural sounds if not found
        if not audio:
            for sound_category in self.CULTURAL_SOUNDS.values():
                if audio_id in sound_category:
                    audio = sound_category[audio_id]
                    break

        if not audio:
            return None

        # Check cultural appropriateness
        if culture_code and culture_code in audio.cultural_appropriateness:
            if not audio.cultural_appropriateness[culture_code]:
                logger.warning(
                    f"Audio {audio_id} not appropriate for culture {culture_code}"
                )
                return None

        return audio

    def get_audio_url(
        self, audio_id: str, language: str, fallback_to_default: bool = True
    ) -> Optional[str]:
        """Get audio URL for specific language."""
        audio = self.get_localized_audio(audio_id, language)
        if not audio:
            return None

        # Try to get localized version
        if language in audio.localized_urls:
            return audio.localized_urls[language]

        # Try language family (e.g., 'en' for 'en-US')
        lang_base = language.split("-")[0]
        if lang_base in audio.localized_urls:
            return audio.localized_urls[lang_base]

        # Return default if fallback enabled
        if fallback_to_default:
            return audio.default_url

        return None

    def get_cultural_sound(
        self, sound_type: CulturalSoundType, culture_code: str, language: str
    ) -> Optional[LocalizedAudio]:
        """Get culturally appropriate sound."""
        sound_category = self.CULTURAL_SOUNDS.get(sound_type.value, {})

        # Find appropriate sound for culture
        for _, sound in sound_category.items():
            if culture_code in sound.cultural_appropriateness:
                if sound.cultural_appropriateness[culture_code]:
                    return sound

        # Return general version if available
        return sound_category.get("general")

    def get_audio_guide(self, feature: str, language: str) -> Optional[AudioGuide]:
        """Get audio guide for a feature."""
        for guide in self.AUDIO_GUIDES.values():
            if guide.feature == feature:
                # Check if language is supported
                if language in guide.audio_urls:
                    return guide

                # Try base language
                lang_base = language.split("-")[0]
                if lang_base in guide.audio_urls:
                    return guide

        return None

    def get_audio_guide_transcript(
        self, guide_id: str, language: str, step: Optional[str] = None
    ) -> Optional[str]:
        """Get transcript for audio guide."""
        guide = self.AUDIO_GUIDES.get(guide_id)
        if not guide:
            return None

        # Get full transcript
        transcript = guide.transcripts.get(language)
        if not transcript:
            # Try base language
            lang_base = language.split("-")[0]
            transcript = guide.transcripts.get(lang_base)

        if not transcript:
            return None

        # If specific step requested, would parse transcript
        # For now, return full transcript
        return transcript

    def get_screen_reader_content(
        self, element_id: str, language: str
    ) -> Optional[ScreenReaderContent]:
        """Get screen reader content for UI element."""
        content = self.SCREEN_READER_CONTENT.get(element_id)
        if not content:
            return None

        # Create localized version
        localized = ScreenReaderContent(
            element_id=content.element_id,
            element_type=content.element_type,
            labels={
                language: content.labels.get(language, content.labels.get("en", ""))
            },
            descriptions={
                language: content.descriptions.get(
                    language, content.descriptions.get("en", "")
                )
            },
            hints={language: content.hints.get(language, content.hints.get("en", ""))},
            shortcuts=content.shortcuts,
        )

        return localized

    def generate_accessibility_announcement(
        self,
        message: str,
        language: str,
        priority: AudioPriority = AudioPriority.NORMAL,
    ) -> Dict[str, Any]:
        """Generate accessibility announcement."""
        # Localize common accessibility phrases
        accessibility_phrases = {
            "loading": {
                "en": "Loading, please wait",
                "es": "Cargando, por favor espere",
                "ar": "جاري التحميل، يرجى الانتظار",
                "hi": "लोड हो रहा है, कृपया प्रतीक्षा करें",
            },
            "error": {
                "en": "Error occurred",
                "es": "Se produjo un error",
                "ar": "حدث خطأ",
                "hi": "त्रुटि हुई",
            },
            "success": {
                "en": "Action completed successfully",
                "es": "Acción completada con éxito",
                "ar": "تمت العملية بنجاح",
                "hi": "कार्रवाई सफलतापूर्वक पूरी हुई",
            },
        }

        # Check if message is a common phrase
        localized_message = message
        for phrase_key, translations in accessibility_phrases.items():
            if phrase_key in message.lower():
                localized_message = translations.get(language, message)
                break

        return {
            "message": localized_message,
            "language": language,
            "priority": priority.value,
            "speak_immediately": priority
            in [AudioPriority.CRITICAL, AudioPriority.HIGH],
        }

    def configure_alert_sounds(self, user_id: str, preferences: Dict[str, Any]) -> bool:
        """Configure user's alert sound preferences."""
        if user_id not in self.user_preferences:
            self.user_preferences[user_id] = {}

        self.user_preferences[user_id].update(
            {
                "alert_volume": preferences.get("alert_volume", 0.8),
                "enable_vibration": preferences.get("enable_vibration", True),
                "quiet_hours": preferences.get("quiet_hours", None),
                "cultural_sounds": preferences.get("cultural_sounds", True),
                "emergency_override": preferences.get("emergency_override", True),
            }
        )

        logger.info(f"Updated alert preferences for user {user_id}")
        return True

    def should_play_sound(
        self,
        audio_type: AudioType,
        user_id: Optional[str] = None,
        current_time: Optional[datetime] = None,
    ) -> bool:
        """Determine if sound should be played based on preferences."""
        if not user_id or user_id not in self.user_preferences:
            return True

        prefs = self.user_preferences[user_id]

        # Check quiet hours
        if current_time and prefs.get("quiet_hours"):
            quiet_start = prefs["quiet_hours"]["start"]
            quiet_end = prefs["quiet_hours"]["end"]
            current_hour = current_time.hour

            if quiet_start <= current_hour < quiet_end:
                # During quiet hours, only play critical sounds
                if audio_type != AudioType.ALERT or not prefs.get(
                    "emergency_override", True
                ):
                    return False

        # Check if cultural sounds are enabled
        if audio_type == AudioType.CULTURAL and not prefs.get("cultural_sounds", True):
            return False

        return True

    def get_notification_settings(
        self, notification_type: str, culture_code: str, language: str
    ) -> Dict[str, Any]:
        """Get culturally appropriate notification settings."""
        # Default settings
        settings: Dict[str, Any] = {
            "sound_enabled": True,
            "vibration_enabled": True,
            "visual_alert": False,
            "repeat_count": 1,
            "interval_seconds": 0,
        }

        # Cultural adjustments
        if culture_code == "middle_eastern":
            if notification_type == "prayer_reminder":
                settings.update(
                    {
                        "sound_enabled": True,
                        "vibration_enabled": False,  # More respectful
                        "repeat_count": 3,
                        "interval_seconds": 2,
                    }
                )
        elif culture_code == "south_asian":
            if notification_type == "medication_reminder":
                settings.update({"repeat_count": 2, "interval_seconds": 3})

        # Add appropriate sound
        if notification_type == "appointment_reminder":
            audio = self.get_localized_audio(
                "appointment_reminder", language, culture_code
            )
            if audio:
                settings["audio_url"] = self.get_audio_url(
                    "appointment_reminder", language
                )
                settings["audio_description"] = audio.descriptions.get(language, "")

        return settings

    def create_audio_package(
        self, feature: str, language: str, culture_code: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create complete audio package for a feature."""
        package: Dict[str, Any] = {
            "feature": feature,
            "language": language,
            "culture_code": culture_code,
            "audio_files": {},
            "screen_reader": {},
            "guides": {},
        }

        # Add relevant audio files
        audio_mapping = {
            "registration": ["task_complete", "input_error"],
            "appointment": ["appointment_reminder", "task_complete"],
            "emergency": ["emergency_alert"],
            "medication": ["task_complete", "input_error"],
        }

        if feature in audio_mapping:
            for audio_id in audio_mapping[feature]:
                url = self.get_audio_url(audio_id, language)
                if url:
                    package["audio_files"][audio_id] = url

        # Add audio guide if available
        guide = self.get_audio_guide(feature, language)
        if guide:
            package["guides"][guide.guide_id] = {
                "url": guide.audio_urls.get(language),
                "transcript": guide.transcripts.get(language),
                "duration": guide.duration.get(language),
            }

        # Add cultural sounds if appropriate
        if culture_code:
            # Add greeting sound
            greeting = self.get_cultural_sound(
                CulturalSoundType.GREETING, culture_code, language
            )
            if greeting:
                package["audio_files"]["greeting"] = self.get_audio_url(
                    greeting.audio_id, language
                )

        return package

    async def preload_audio_files(
        self, audio_ids: List[str], language: str
    ) -> Dict[str, bool]:
        """Preload audio files for offline use."""
        results = {}

        for audio_id in audio_ids:
            try:
                url = self.get_audio_url(audio_id, language)
                if url:
                    # In production, would actually download and cache
                    await asyncio.sleep(0.1)  # Simulate download
                    self.audio_cache[f"{audio_id}_{language}"] = b"CACHED_AUDIO_DATA"
                    results[audio_id] = True
                else:
                    results[audio_id] = False
            except Exception as e:
                logger.error(f"Failed to preload {audio_id}: {e}")
                results[audio_id] = False

        return results


# Global audio localization manager
audio_manager = AudioLocalizationManager()
