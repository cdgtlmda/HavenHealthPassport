"""Custom memory implementations for specialized use cases.

All memory implementations containing PHI are encrypted and access controlled per HIPAA requirements.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from langchain.llms.base import BaseLLM
from langchain.schema import BaseMessage

from .base import BaseMemoryStore
from .conversation import ConversationMemory
from .entity import EntityMemory, MedicalEntityMemory
from .summary import MedicalSummaryMemory, SummaryMemory

logger = logging.getLogger(__name__)


class HybridMemory:
    """Combines conversation, entity, and summary memory."""

    def __init__(
        self,
        session_id: str,
        user_id: str,
        llm: BaseLLM,
        memory_store: BaseMemoryStore,
        max_token_limit: int = 4000,
    ):
        """Initialize hybrid memory."""
        self.session_id = session_id
        self.user_id = user_id

        self.conversation_memory = ConversationMemory(
            session_id, user_id, memory_store, max_token_limit=max_token_limit
        )
        self.entity_memory = EntityMemory(session_id, user_id, memory_store)
        self.summary_memory = SummaryMemory(session_id, user_id, llm, memory_store)

    def add_exchange(self, human_message: str, ai_message: str) -> None:
        """Add a conversation exchange to all memories."""
        # Add to conversation
        self.conversation_memory.add_user_message(human_message)
        self.conversation_memory.add_ai_message(ai_message)

        # Extract entities
        human_entities = self.entity_memory.extract_entities(human_message)
        ai_entities = self.entity_memory.extract_entities(ai_message)

        for entity, info in {**human_entities, **ai_entities}.items():
            self.entity_memory.update_entity(entity, info)
        # Update summary if needed
        messages = self.conversation_memory.get_messages()
        if len(messages) % 10 == 0:  # Summarize every 10 messages
            summary = self.summary_memory.summarize_messages(messages[-10:])
            self.summary_memory.add_summary(summary, 10)

    def get_context(self) -> Dict[str, Any]:
        """Get combined context from all memories."""
        return {
            "conversation": self.conversation_memory.get_buffer_string(),
            "entities": self.entity_memory.get_all_entities(),
            "summary": self.summary_memory.current_summary,
            "message_count": len(self.conversation_memory.get_messages()),
        }

    def clear_all(self) -> None:
        """Clear all memory types."""
        self.conversation_memory.clear()
        self.entity_memory.clear()
        self.summary_memory.clear()


class MedicalContextMemory(HybridMemory):
    """Medical-specific memory with enhanced tracking."""

    def __init__(self, patient_id: str, **kwargs: Any) -> None:
        """Initialize medical context memory."""
        self.patient_id = patient_id
        super().__init__(**kwargs)

        # Use medical-specific memories
        self.entity_memory = MedicalEntityMemory(
            session_id=self.session_id,
            user_id=self.user_id,
            memory_store=kwargs.get("memory_store"),
        )
        self.summary_memory: MedicalSummaryMemory = MedicalSummaryMemory(
            self.session_id, self.user_id, kwargs.get("llm", None), kwargs.get("memory_store")  # type: ignore[arg-type]
        )

        # Track medical context
        self.medical_context: Dict[str, Any] = {
            "current_complaint": None,
            "vital_signs": {},
            "active_symptoms": [],
            "recent_tests": [],
            "current_medications": [],
        }

    def update_medical_context(self, updates: Dict[str, Any]) -> None:
        """Update medical context information."""
        for key, value in updates.items():
            if key in self.medical_context:
                if isinstance(self.medical_context[key], list):
                    if value not in self.medical_context[key]:
                        self.medical_context[key].append(value)
                else:
                    self.medical_context[key] = value

    def get_medical_summary(self) -> Dict[str, Any]:
        """Get comprehensive medical summary."""
        messages = self.conversation_memory.get_messages()
        medical_summary = self.summary_memory.summarize_medical_conversation(messages)

        return {
            **medical_summary,
            "context": self.medical_context,
            "entities": self.entity_memory.get_entities_by_type("MEDICATION"),
        }


class EmergencyMemory:
    """Rapid-access memory for emergency situations."""

    def __init__(self, patient_id: str, memory_store: BaseMemoryStore):
        """Initialize emergency memory."""
        self.patient_id = patient_id
        self.memory_store = memory_store
        self.emergency_key = f"emergency:{patient_id}"

        # Critical information cache
        self.critical_info: Dict[str, Any] = {
            "blood_type": None,
            "allergies": [],
            "emergency_contacts": [],
            "medical_conditions": [],
            "current_medications": [],
            "dnr_status": None,
            "last_updated": None,
        }
        self._load_emergency_info()

    def _load_emergency_info(self) -> None:
        """Load emergency information."""
        data = self.memory_store.load(self.emergency_key)
        if data:
            self.critical_info.update(data)

    def update_critical_info(self, updates: Dict[str, Any]) -> None:
        """Update critical emergency information."""
        self.critical_info.update(updates)
        self.critical_info["last_updated"] = datetime.now(timezone.utc).isoformat()
        self.memory_store.save(self.emergency_key, self.critical_info)

    def get_emergency_summary(self) -> str:
        """Get formatted emergency summary."""
        summary = f"PATIENT ID: {self.patient_id}\n"

        if self.critical_info["blood_type"]:
            summary += f"BLOOD TYPE: {self.critical_info['blood_type']}\n"

        if self.critical_info["allergies"]:
            summary += f"ALLERGIES: {', '.join(self.critical_info['allergies'])}\n"

        if self.critical_info["medical_conditions"]:
            summary += (
                f"CONDITIONS: {', '.join(self.critical_info['medical_conditions'])}\n"
            )

        if self.critical_info["current_medications"]:
            summary += (
                f"MEDICATIONS: {', '.join(self.critical_info['current_medications'])}\n"
            )

        return summary


class MultilingualMemory:
    """Memory system with multilingual support."""

    def __init__(
        self,
        session_id: str,
        user_id: str,
        memory_store: BaseMemoryStore,
        primary_language: str = "en",
        supported_languages: Optional[List[str]] = None,
    ):
        """Initialize multilingual memory."""
        self.session_id = session_id
        self.user_id = user_id
        self.memory_store = memory_store
        self.primary_language = primary_language
        self.supported_languages = supported_languages or ["en", "es", "fr", "ar", "zh"]

        # Language-specific memories
        self.language_memories: Dict[str, ConversationMemory] = {}
        self.translation_cache: Dict[str, Dict[str, str]] = {}

        # Initialize primary language memory
        self.language_memories[primary_language] = ConversationMemory(
            f"{session_id}_{primary_language}", user_id, memory_store
        )

    def add_message(self, message: str, language: str, is_human: bool = True) -> None:
        """Add message in specific language."""
        # Initialize language memory if needed
        if language not in self.language_memories:
            self.language_memories[language] = ConversationMemory(
                f"{self.session_id}_{language}", self.user_id, self.memory_store
            )

        # Add to language-specific memory
        if is_human:
            self.language_memories[language].add_user_message(message)
        else:
            self.language_memories[language].add_ai_message(message)

    def get_conversation(self, language: str) -> List[BaseMessage]:
        """Get conversation in specific language."""
        if language in self.language_memories:
            return self.language_memories[language].get_messages()
        return []

    def cache_translation(
        self, source_text: str, target_lang: str, translation: str
    ) -> None:
        """Cache translation for reuse."""
        cache_key = f"{source_text}:{target_lang}"
        self.translation_cache[cache_key] = {
            "translation": translation,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def get_cached_translation(
        self, source_text: str, target_lang: str
    ) -> Optional[str]:
        """Get cached translation if available."""
        cache_key = f"{source_text}:{target_lang}"
        if cache_key in self.translation_cache:
            return self.translation_cache[cache_key]["translation"]
        return None
