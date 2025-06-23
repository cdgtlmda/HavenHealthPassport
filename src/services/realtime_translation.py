"""Real-time translation service with WebSocket integration."""

from typing import Any, Callable, Dict, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from src.api.subscriptions import (
    publish_translation_session,
    publish_translation_update,
)
from src.services.translation_service import (
    TranslationContext,
    TranslationDirection,
    TranslationService,
    TranslationType,
)
from src.utils.logging import get_logger

logger = get_logger(__name__)


class RealtimeTranslationService:
    """Service for handling real-time translations with WebSocket streaming."""

    def __init__(self, session: Session):
        """Initialize real-time translation service."""
        self.translation_service = TranslationService(session)
        self.active_sessions: Dict[str, Dict[str, Any]] = {}

    async def create_streaming_callback(self, session_id: str) -> Callable:
        """
        Create a streaming callback that publishes to WebSocket subscribers.

        Args:
            session_id: Translation session ID

        Returns:
            Async callback function
        """

        async def stream_callback(result: Dict[str, Any]) -> None:
            """Publish translation update to WebSocket subscribers."""
            try:
                # Add session ID to result
                result["session_id"] = session_id

                # Publish to WebSocket channel
                await publish_translation_update(result)

                # Log streaming update
                if result.get("is_final"):
                    logger.info(f"Final translation for session {session_id}")
                else:
                    logger.debug(
                        f"Partial translation for session {session_id}: {len(result.get('partial_text', ''))} chars"
                    )

            except (ValueError, AttributeError, KeyError) as e:
                logger.error(f"Error publishing translation update: {e}")

        return stream_callback

    async def start_translation_session(
        self,
        user_id: UUID,
        source_language: Optional[TranslationDirection] = None,
        target_language: Optional[TranslationDirection] = None,
        context_type: TranslationContext = TranslationContext.PATIENT_FACING,
    ) -> Dict[str, Any]:
        """
        Start a new real-time translation session.

        Args:
            user_id: User ID creating the session
            source_language: Default source language
            target_language: Default target language
            context_type: Translation context

        Returns:
            Session information
        """
        # Create session through translation service
        session_info = await self.translation_service.create_translation_session(
            user_id=user_id,
            source_language=source_language,
            target_language=target_language,
            context_type=context_type,
        )

        # Store session info
        self.active_sessions[session_info["session_id"]] = session_info

        # Publish session creation event
        await publish_translation_session(session_info)

        return session_info

    async def translate_text_streaming(
        self,
        session_id: str,
        text: str,
        target_language: Optional[TranslationDirection] = None,
        source_language: Optional[TranslationDirection] = None,
        translation_type: TranslationType = TranslationType.UI_TEXT,
        context: Optional[TranslationContext] = None,
    ) -> Dict[str, Any]:
        """
        Translate text with real-time streaming updates.

        Args:
            session_id: Translation session ID
            text: Text to translate
            target_language: Target language (uses session default if not provided)
            source_language: Source language (auto-detect if not provided)
            translation_type: Type of content
            context: Translation context (uses session default if not provided)

        Returns:
            Final translation result
        """
        # Get session info
        session_info = self.active_sessions.get(session_id)
        if not session_info:
            raise ValueError(f"Invalid session ID: {session_id}")

        # Use session defaults if not provided
        if not target_language and session_info.get("target_language"):
            target_language = TranslationDirection(session_info["target_language"])
        if not source_language and session_info.get("source_language"):
            source_language = TranslationDirection(session_info["source_language"])
        if not context and session_info.get("context_type"):
            context = TranslationContext(session_info["context_type"])

        # Validate target language
        if not target_language:
            raise ValueError("Target language must be specified")

        # Create streaming callback
        stream_callback = await self.create_streaming_callback(session_id)

        # Perform real-time translation
        result = await self.translation_service.translate_realtime(
            text=text,
            target_language=target_language,
            source_language=source_language,
            translation_type=translation_type,
            context=context or TranslationContext.PATIENT_FACING,
            stream_callback=stream_callback,
            session_id=session_id,
        )

        return result

    async def translate_conversation_streaming(
        self,
        session_id: str,
        messages: list[Dict[str, str]],
        target_language: Optional[TranslationDirection] = None,
        source_language: Optional[TranslationDirection] = None,
        maintain_context: bool = True,
    ) -> Dict[str, Any]:
        """
        Translate a conversation with streaming updates.

        Args:
            session_id: Translation session ID
            messages: List of messages to translate
            target_language: Target language
            source_language: Source language
            maintain_context: Whether to maintain conversation context

        Returns:
            Conversation translation results
        """
        # Get session info
        session_info = self.active_sessions.get(session_id)
        if not session_info:
            raise ValueError(f"Invalid session ID: {session_id}")

        # Use session defaults
        if not target_language and session_info.get("target_language"):
            target_language = TranslationDirection(session_info["target_language"])

        if not target_language:
            raise ValueError("Target language must be specified")

        # Translate conversation
        results = await self.translation_service.translate_conversation(
            messages=messages,
            target_language=target_language,
            source_language=source_language,
            maintain_context=maintain_context,
            session_id=session_id,
        )

        # Publish final conversation result
        await publish_translation_update(
            {
                "session_id": session_id,
                "is_final": True,
                "conversation_complete": True,
                "message_count": len(results.get("messages", [])),
                "target_language": target_language.value,
            }
        )

        return results

    async def close_session(self, session_id: str) -> bool:
        """
        Close a translation session.

        Args:
            session_id: Session ID to close

        Returns:
            True if session was closed
        """
        if session_id in self.active_sessions:
            # Remove from active sessions
            del self.active_sessions[session_id]

            # Close in translation service
            return await self.translation_service.close_translation_session(session_id)

        return False

    def get_active_sessions(
        self, user_id: Optional[UUID] = None
    ) -> list[Dict[str, Any]]:
        """
        Get active translation sessions.

        Args:
            user_id: Filter by user ID (optional)

        Returns:
            List of active sessions
        """
        sessions = list(self.active_sessions.values())

        if user_id:
            sessions = [s for s in sessions if s.get("user_id") == str(user_id)]

        return sessions


# Singleton instance management
class RealtimeTranslationServiceManager:
    """Manager for singleton instance of RealtimeTranslationService."""

    _instance: Optional[RealtimeTranslationService] = None

    @classmethod
    def get_instance(cls, session: Session) -> RealtimeTranslationService:
        """Get or create the real-time translation service instance."""
        if cls._instance is None:
            cls._instance = RealtimeTranslationService(session)
        return cls._instance


def get_realtime_translation_service(session: Session) -> RealtimeTranslationService:
    """Get or create the real-time translation service instance."""
    return RealtimeTranslationServiceManager.get_instance(session)
