"""API endpoints for UI translation functionality."""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.api.auth_endpoints import get_current_user
from src.core.database import get_db
from src.models.auth import UserAuth
from src.services.translation_service import (
    TranslationContext,
    TranslationDirection,
    TranslationService,
    TranslationType,
)
from src.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/translations", tags=["translations"])

# Module-level dependency variables to avoid B008 errors
db_dependency = Depends(get_db)
current_user_dependency = Depends(get_current_user)

# Module-level Query and Body parameters
older_than_query = Query(None, description="Clear entries older than this date")
phrases_body = Body(..., description="List of phrases to cache")
text_body = Body(..., description="Text to analyze")
hint_body = Body(None, description="Language hint")


class UITranslationRequest(BaseModel):
    """Request model for UI translations."""

    text: str = Field(..., description="Text to translate")
    target_language: TranslationDirection = Field(
        ..., description="Target language code"
    )
    source_language: Optional[TranslationDirection] = Field(
        None, description="Source language code"
    )
    translation_type: str = Field(default="ui_text", description="Type of translation")
    context: str = Field(default="patient_facing", description="Translation context")
    namespace: Optional[str] = Field(None, description="UI namespace")
    key: Optional[str] = Field(None, description="Translation key")
    session_id: Optional[str] = Field(None, description="Translation session ID")


class UITranslationResponse(BaseModel):
    """Response model for UI translations."""

    translated_text: str
    source_language: str
    target_language: str
    cached: bool
    confidence_score: float
    medical_terms_detected: Optional[Dict[str, Any]] = None
    session_id: Optional[str] = None


class BatchTranslationRequest(BaseModel):
    """Request model for batch translations."""

    texts: List[Dict[str, Any]] = Field(..., description="List of texts to translate")
    target_language: TranslationDirection = Field(
        ..., description="Target language for all texts"
    )
    source_language: Optional[TranslationDirection] = Field(
        None, description="Source language"
    )
    translation_type: str = Field(default="ui_text", description="Type of translation")
    namespace: Optional[str] = Field(None, description="UI namespace")


class TranslationSessionRequest(BaseModel):
    """Request model for creating translation session."""

    user_id: str = Field(..., description="User ID")
    source_language: Optional[TranslationDirection] = Field(
        None, description="Default source language"
    )
    target_language: Optional[TranslationDirection] = Field(
        None, description="Default target language"
    )
    context_type: str = Field(default="patient_facing", description="Context type")


class LanguageInfo(BaseModel):
    """Language information model."""

    code: str
    name: str
    native_name: str
    rtl: bool


@router.post("/translate", response_model=UITranslationResponse)
async def translate_ui_text(
    request: UITranslationRequest,
    db: Session = db_dependency,
    current_user: Optional[UserAuth] = current_user_dependency,
) -> UITranslationResponse:
    """
    Translate UI text dynamically.

    This endpoint is optimized for UI translations with caching and
    session support for maintaining context across multiple translations.
    """
    try:
        translation_service = TranslationService(db)

        # Set user context if authenticated
        if current_user:
            translation_service.current_user_id = current_user.id

        # Set session context if provided
        if request.session_id:
            translation_service.set_context_scope(
                session_id=request.session_id, patient_id=None, document_id=None
            )

        # Store UI namespace and key for better context
        metadata = {}
        if request.namespace:
            metadata["namespace"] = request.namespace
        if request.key:
            metadata["key"] = request.key

        # Perform translation
        result = translation_service.translate(
            text=request.text,
            target_language=request.target_language,
            source_language=request.source_language,
            translation_type=TranslationType.UI_TEXT,
            context=TranslationContext(request.context),
            preserve_formatting=False,  # UI text typically doesn't need formatting preservation
        )

        # Add session ID to response if available
        if request.session_id:
            result["session_id"] = request.session_id

        return UITranslationResponse(**result)

    except ValueError as e:
        logger.error(f"Invalid translation request: {e}")
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.error(f"Translation error: {e}")
        raise HTTPException(status_code=500, detail="Translation service error") from e


@router.post("/batch", response_model=List[UITranslationResponse])
async def translate_batch(
    request: BatchTranslationRequest,
    db: Session = db_dependency,
    current_user: Optional[UserAuth] = current_user_dependency,
) -> List[UITranslationResponse]:
    """
    Translate multiple UI texts in batch.

    Optimized for translating multiple UI elements at once,
    such as when loading a new screen or component.
    """
    try:
        translation_service = TranslationService(db)

        if current_user:
            translation_service.current_user_id = current_user.id

        results = []

        # Create temporary session for batch consistency
        session_id = f"batch_{datetime.utcnow().timestamp()}"
        translation_service.set_context_scope(session_id=session_id)

        for item in request.texts:
            text = item.get("text", "")
            key = item.get("key", "")
            default_value = item.get("defaultValue", "")

            if not text and default_value:
                text = default_value
            elif not text:
                text = key

            if text:
                result = translation_service.translate(
                    text=text,
                    target_language=request.target_language,
                    source_language=request.source_language,
                    translation_type=TranslationType.UI_TEXT,
                    context=TranslationContext.PATIENT_FACING,
                    preserve_formatting=False,
                )

                # Add key to result for client mapping
                result["key"] = key
                results.append(UITranslationResponse(**result))

        return results

    except Exception as e:
        logger.error(f"Batch translation error: {e}")
        raise HTTPException(status_code=500, detail="Batch translation error") from e


@router.post("/session")
async def create_translation_session(
    request: TranslationSessionRequest,
    db: Session = db_dependency,
    current_user: Optional[UserAuth] = current_user_dependency,
) -> Dict[str, Any]:
    """
    Create a translation session for maintaining context.

    Sessions help maintain translation consistency across
    multiple related translations in a user session.
    """
    try:
        translation_service = TranslationService(db)

        # Verify user access
        if current_user and str(current_user.id) != request.user_id:
            raise HTTPException(
                status_code=403, detail="Cannot create session for another user"
            )

        # Create session using the translation service's method
        session_info = await translation_service.create_translation_session(
            user_id=UUID(request.user_id),
            source_language=request.source_language,
            target_language=request.target_language,
            context_type=TranslationContext(request.context_type),
        )

        return session_info

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.error(f"Session creation error: {e}")
        raise HTTPException(status_code=500, detail="Failed to create session") from e


@router.delete("/session/{session_id}")
async def close_translation_session(
    session_id: str,
    db: Session = db_dependency,
) -> Dict[str, Any]:
    """Close a translation session."""
    try:
        translation_service = TranslationService(db)

        success = await translation_service.close_translation_session(session_id)

        return {"success": success, "session_id": session_id}

    except Exception as e:
        logger.error(f"Session close error: {e}")
        raise HTTPException(status_code=500, detail="Failed to close session") from e


@router.get("/languages", response_model=List[LanguageInfo])
async def get_supported_languages(db: Session = db_dependency) -> List[LanguageInfo]:
    """
    Get list of supported languages with metadata.

    Returns language codes, names, native names, and RTL information.
    """
    try:
        translation_service = TranslationService(db)
        languages = translation_service.get_supported_languages()

        return [LanguageInfo(**lang) for lang in languages]

    except Exception as e:
        logger.error(f"Error fetching languages: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch languages") from e


@router.get("/static/{language}/{namespace}")
async def get_static_translations(
    language: str,
    namespace_param: str,
) -> JSONResponse:
    """
    Get static translations for a language and namespace.

    This endpoint serves pre-translated UI strings that can be
    cached by the client for offline use.
    """
    _ = namespace_param  # Mark as used
    try:
        # Validate language
        if language not in [lang.value for lang in TranslationDirection]:
            raise HTTPException(status_code=404, detail="Language not supported")

        # For now, return empty object if translations don't exist
        # In production, this would load from a translations database or files
        static_translations: Dict[str, Any] = {}

        # You could load from database here
        # Example:
        # translations = db.query(UITranslation).filter(
        #     UITranslation.language == language,
        #     UITranslation.namespace == namespace
        # ).all()

        return JSONResponse(content=static_translations)

    except Exception as e:
        logger.error(f"Error loading static translations: {e}")
        raise HTTPException(
            status_code=500, detail="Failed to load translations"
        ) from e


@router.post("/cache/warmup")
async def warmup_translation_cache(
    phrases: List[Dict[str, str]] = phrases_body,
    db: Session = db_dependency,
    current_user: UserAuth = current_user_dependency,
) -> Dict[str, Any]:
    """
    Warm up translation cache with common phrases.

    Admin endpoint to pre-populate cache with frequently used translations.
    """
    try:
        # Check admin permission
        if not current_user.is_superuser:
            raise HTTPException(status_code=403, detail="Admin access required")

        translation_service = TranslationService(db)
        translation_service.current_user_id = current_user.id

        # Convert phrases to format expected by service
        common_phrases = [
            (phrase["text"], phrase["source_lang"], phrase["target_lang"])
            for phrase in phrases
        ]

        warmed_count = translation_service.warmup_cache(common_phrases)

        return {
            "success": True,
            "warmed_count": warmed_count,
            "total_phrases": len(common_phrases),
        }

    except Exception as e:
        logger.error(f"Cache warmup error: {e}")
        raise HTTPException(status_code=500, detail="Failed to warm up cache") from e


@router.delete("/cache")
async def clear_translation_cache(
    older_than: Optional[datetime] = older_than_query,
    db: Session = db_dependency,
    current_user: UserAuth = current_user_dependency,
) -> Dict[str, Any]:
    """
    Clear translation cache.

    Admin endpoint to clear translation cache entries.
    """
    try:
        # Check admin permission
        if not current_user.is_superuser:
            raise HTTPException(status_code=403, detail="Admin access required")

        translation_service = TranslationService(db)
        cleared_count = translation_service.clear_cache(older_than=older_than)

        return {"success": True, "cleared_count": cleared_count}

    except Exception as e:
        logger.error(f"Cache clear error: {e}")
        raise HTTPException(status_code=500, detail="Failed to clear cache") from e


@router.get("/cache/stats")
async def get_cache_statistics(
    db: Session = db_dependency, current_user: UserAuth = current_user_dependency
) -> Dict[str, Any]:
    """
    Get translation cache statistics.

    Admin endpoint to monitor cache performance and usage.
    """
    try:
        # Check admin permission
        if not current_user.is_superuser:
            raise HTTPException(status_code=403, detail="Admin access required")

        translation_service = TranslationService(db)
        stats = translation_service.get_cache_statistics()

        return stats

    except Exception as e:
        logger.error(f"Error fetching cache stats: {e}")
        raise HTTPException(
            status_code=500, detail="Failed to fetch cache statistics"
        ) from e


@router.post("/detect-language")
async def detect_language(
    text: str = text_body,
    hint: Optional[str] = hint_body,
    db: Session = db_dependency,
) -> Dict[str, Any]:
    """
    Detect the language of provided text.

    Useful for auto-detecting source language in UI.
    """
    try:
        translation_service = TranslationService(db)

        # Validate hint if provided
        hint_enum = None
        if hint:
            try:
                hint_enum = TranslationDirection(hint)
            except ValueError as exc:
                raise HTTPException(
                    status_code=400, detail="Invalid language hint"
                ) from exc

        result = await translation_service.detect_language_with_confidence(
            text=text, hint=hint_enum
        )

        return result

    except Exception as e:
        logger.error(f"Language detection error: {e}")
        raise HTTPException(status_code=500, detail="Failed to detect language") from e


# Include router in main app
__all__ = ["router"]
