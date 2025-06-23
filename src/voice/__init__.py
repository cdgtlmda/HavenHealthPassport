"""
Voice Processing Module.

This module provides voice processing capabilities for Haven Health Passport,
including medical transcription, voice analysis, and multi-language support.
"""

from .interface.voice_command_grammar import (
    CommandGrammar,
    CommandGrammarEngine,
    CommandParameter,
    CommandPriority,
    CommandType,
    MultilingualGrammarEngine,
    ParameterType,
    ParsedCommand,
)
from .interface.voice_shortcuts import (
    PersonalizedShortcutEngine,
    ShortcutCategory,
    ShortcutConfig,
    ShortcutEngine,
    ShortcutMatch,
    ShortcutScope,
    VoiceShortcut,
)
from .interface.wake_word_detection import (
    MultilingualWakeWordEngine,
    WakeWord,
    WakeWordConfig,
    WakeWordDetection,
    WakeWordEngine,
    WakeWordModel,
    WakeWordStatus,
)
from .medical_vocabularies import (
    MedicalTerm,
    MedicalVocabularyManager,
    SpecialtyVocabulary,
    VocabularyState,
)
from .transcribe_medical import (
    AudioFormat,
    LanguageCode,
    MedicalSpecialty,
    TranscribeMedicalConfig,
    TranscribeMedicalService,
    TranscriptionResult,
    TranscriptionStatus,
)

__all__ = [
    # Transcription
    "TranscribeMedicalConfig",
    "TranscribeMedicalService",
    "MedicalSpecialty",
    "TranscriptionResult",
    "TranscriptionStatus",
    "AudioFormat",
    "LanguageCode",
    # Medical Vocabularies
    "MedicalTerm",
    "SpecialtyVocabulary",
    "VocabularyState",
    "MedicalVocabularyManager",
    # Command Grammar
    "CommandType",
    "CommandPriority",
    "ParameterType",
    "CommandParameter",
    "CommandGrammar",
    "ParsedCommand",
    "CommandGrammarEngine",
    "MultilingualGrammarEngine",
    # Wake Word Detection
    "WakeWordStatus",
    "WakeWordModel",
    "WakeWord",
    "WakeWordDetection",
    "WakeWordConfig",
    "WakeWordEngine",
    "MultilingualWakeWordEngine",
    # Voice Shortcuts
    "ShortcutCategory",
    "ShortcutScope",
    "VoiceShortcut",
    "ShortcutMatch",
    "ShortcutConfig",
    "ShortcutEngine",
    "PersonalizedShortcutEngine",
]
