"""Translation queue REST API endpoints."""

from datetime import datetime
from typing import Any, Dict, List, Optional, cast
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.api.auth_endpoints import get_current_user
from src.core.database import get_db
from src.models.auth import UserAuth
from src.models.translation_queue import (
    TranslationQueuePriority,
)
from src.services.translation_queue_service import TranslationQueueService
from src.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/translation-queue", tags=["translation-queue"])

# Module-level dependency variables to avoid B008 errors
db_dependency = Depends(get_db)
current_user_dependency = Depends(get_current_user)
query_language_pair_dependency = Query(None, pattern="^[a-z]{2,3}-[a-z]{2,3}$")
query_limit_dependency = Query(10, ge=1, le=100)
query_retry_reason_dependency = Query(..., min_length=1)


class QueuedTranslationResponse(BaseModel):
    """Response model for queued translation."""

    id: UUID
    source_text: str
    source_language: str
    target_language: str
    translation_type: str
    status: str
    priority: str
    queue_reason: str
    bedrock_translation: Optional[str]
    bedrock_confidence_score: Optional[float]
    human_translation: Optional[str]
    translator_id: Optional[UUID]
    quality_score: Optional[float]
    created_at: datetime
    assigned_at: Optional[datetime]
    completed_at: Optional[datetime]
    expires_at: Optional[datetime]


class TranslationAssignmentRequest(BaseModel):
    """Request model for assigning translation."""

    translator_id: UUID
    language_pair_certified: bool = False
    medical_specialty_match: Optional[str] = None
    dialect_expertise: Optional[str] = None
    assignment_reason: Optional[str] = None


class TranslationCompletionRequest(BaseModel):
    """Request model for completing translation."""

    human_translation: str = Field(..., min_length=1)
    translation_notes: Optional[str] = None
    quality_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    cultural_notes: Optional[List[str]] = None


class TranslationFeedbackRequest(BaseModel):
    """Request model for translation feedback."""

    feedback_type: str = Field(..., pattern="^(accuracy|clarity|terminology)$")
    rating: int = Field(..., ge=1, le=5)
    feedback_role: str = Field(..., pattern="^(patient|provider|reviewer)$")
    comments: Optional[str] = None
    terminology_issues: Optional[List[Dict[str, str]]] = None
    suggested_corrections: Optional[Dict[str, str]] = None


@router.get("/pending", response_model=List[QueuedTranslationResponse])
async def get_pending_translations(
    language_pair: Optional[str] = query_language_pair_dependency,
    priority: Optional[TranslationQueuePriority] = None,
    medical_category: Optional[str] = None,
    assigned_to_me: bool = False,
    limit: int = query_limit_dependency,
    current_user: UserAuth = current_user_dependency,
    db: Session = db_dependency,
) -> List[QueuedTranslationResponse]:
    """
    Get pending translations from the queue.

    Requires: translate:queue:read permission
    """
    if not current_user.has_permission("translate:queue:read"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions"
        )

    service = TranslationQueueService(db)

    # Parse language pair if provided
    source_lang = None
    target_lang = None
    if language_pair:
        parts = language_pair.split("-")
        if len(parts) == 2:
            source_lang, target_lang = parts

    # Get translator ID if filtering by assignment
    translator_id = current_user.id if assigned_to_me else None

    entries = service.get_pending_translations(
        translator_id=translator_id,
        language_pair=(
            (source_lang, target_lang)
            if language_pair and source_lang and target_lang
            else None
        ),
        priority=priority,
        medical_category=medical_category,
        limit=limit,
    )

    return [
        QueuedTranslationResponse(
            id=entry.id,
            source_text=str(entry.source_text),
            source_language=str(entry.source_language),
            target_language=str(entry.target_language),
            translation_type=str(entry.translation_type),
            status=str(entry.status),
            priority=str(entry.priority),
            queue_reason=str(entry.queue_reason),
            bedrock_translation=(
                str(entry.bedrock_translation) if entry.bedrock_translation else None
            ),
            bedrock_confidence_score=(
                float(entry.bedrock_confidence_score)
                if entry.bedrock_confidence_score
                else None
            ),
            human_translation=(
                str(entry.human_translation) if entry.human_translation else None
            ),
            translator_id=entry.translator_id,
            quality_score=float(entry.quality_score) if entry.quality_score else None,
            created_at=cast(datetime, entry.created_at),
            assigned_at=cast(Optional[datetime], entry.assigned_at),
            completed_at=cast(Optional[datetime], entry.completed_at),
            expires_at=cast(datetime, entry.expires_at),
        )
        for entry in entries
    ]


@router.get("/{queue_id}", response_model=QueuedTranslationResponse)
async def get_queued_translation(
    queue_id: UUID,
    current_user: UserAuth = current_user_dependency,
    db: Session = db_dependency,
) -> QueuedTranslationResponse:
    """
    Get a specific queued translation.

    Requires: translate:queue:read permission
    """
    if not current_user.has_permission("translate:queue:read"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions"
        )

    service = TranslationQueueService(db)
    entry = service.get_by_id(queue_id)

    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Translation queue entry {queue_id} not found",
        )

    return QueuedTranslationResponse(
        id=entry.id,
        source_text=str(entry.source_text),
        source_language=str(entry.source_language),
        target_language=str(entry.target_language),
        translation_type=str(entry.translation_type),
        status=str(entry.status),
        priority=str(entry.priority),
        queue_reason=str(entry.queue_reason),
        bedrock_translation=(
            str(entry.bedrock_translation) if entry.bedrock_translation else None
        ),
        bedrock_confidence_score=(
            float(entry.bedrock_confidence_score)
            if entry.bedrock_confidence_score
            else None
        ),
        human_translation=(
            str(entry.human_translation) if entry.human_translation else None
        ),
        translator_id=entry.translator_id,
        quality_score=float(entry.quality_score) if entry.quality_score else None,
        created_at=cast(datetime, entry.created_at),
        assigned_at=cast(Optional[datetime], entry.assigned_at),
        completed_at=cast(Optional[datetime], entry.completed_at),
        expires_at=cast(datetime, entry.expires_at),
    )


@router.post("/{queue_id}/assign", response_model=Dict[str, Any])
async def assign_translation(
    queue_id: UUID,
    request: TranslationAssignmentRequest,
    current_user: UserAuth = current_user_dependency,
    db: Session = db_dependency,
) -> Dict[str, Any]:
    """
    Assign a translation to a translator.

    Requires: translate:queue:assign permission
    """
    if not current_user.has_permission("translate:queue:assign"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions"
        )

    service = TranslationQueueService(db)

    try:
        assignment = service.assign_translation(
            queue_entry_id=queue_id,
            translator_id=request.translator_id,
            assigned_by=current_user.id,
            language_pair_certified=request.language_pair_certified,
            medical_specialty_match=request.medical_specialty_match,
            dialect_expertise=request.dialect_expertise,
            assignment_reason=request.assignment_reason,
        )

        return {
            "success": True,
            "assignment_id": str(assignment.id),
            "translator_id": str(assignment.translator_id),
            "assigned_at": datetime.utcnow().isoformat(),
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        ) from e


@router.post("/{queue_id}/start", response_model=Dict[str, Any])
async def start_translation(
    queue_id: UUID,
    current_user: UserAuth = current_user_dependency,
    db: Session = db_dependency,
) -> Dict[str, Any]:
    """
    Start working on a translation.

    Requires: translate:queue:work permission
    """
    if not current_user.has_permission("translate:queue:work"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions"
        )

    service = TranslationQueueService(db)

    try:
        entry = service.start_translation(queue_id, current_user.id)

        return {
            "success": True,
            "status": entry.status,
            "started_at": entry.started_at.isoformat(),
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        ) from e


@router.post("/{queue_id}/complete", response_model=Dict[str, Any])
async def complete_translation(
    queue_id: UUID,
    request: TranslationCompletionRequest,
    current_user: UserAuth = current_user_dependency,
    db: Session = db_dependency,
) -> Dict[str, Any]:
    """
    Complete a human translation.

    Requires: translate:queue:work permission
    """
    if not current_user.has_permission("translate:queue:work"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions"
        )

    service = TranslationQueueService(db)

    try:
        entry = service.complete_translation(
            queue_entry_id=queue_id,
            translator_id=current_user.id,
            human_translation=request.human_translation,
            translation_notes=request.translation_notes,
            quality_score=request.quality_score,
            cultural_notes=request.cultural_notes,
        )

        return {
            "success": True,
            "status": entry.status,
            "completed_at": entry.completed_at.isoformat(),
            "quality_score": entry.quality_score,
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        ) from e


@router.post("/{queue_id}/retry", response_model=Dict[str, Any])
async def retry_translation(
    queue_id: UUID,
    retry_reason: str = query_retry_reason_dependency,
    current_user: UserAuth = current_user_dependency,
    db: Session = db_dependency,
) -> Dict[str, Any]:
    """
    Retry a failed translation.

    Requires: translate:queue:manage permission
    """
    if not current_user.has_permission("translate:queue:manage"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions"
        )

    service = TranslationQueueService(db)

    try:
        entry = service.retry_translation(queue_id, retry_reason)

        return {
            "success": True,
            "status": entry.status,
            "retry_count": entry.retry_count,
            "last_retry_at": entry.last_retry_at.isoformat(),
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        ) from e


@router.post("/{queue_id}/feedback", response_model=Dict[str, Any])
async def add_feedback(
    queue_id: UUID,
    request: TranslationFeedbackRequest,
    current_user: UserAuth = current_user_dependency,
    db: Session = db_dependency,
) -> Dict[str, Any]:
    """
    Add feedback for a completed translation.

    Requires: translate:queue:feedback permission
    """
    if not current_user.has_permission("translate:queue:feedback"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions"
        )

    service = TranslationQueueService(db)

    try:
        feedback = service.add_feedback(
            queue_entry_id=queue_id,
            feedback_by=current_user.id,
            feedback_type=request.feedback_type,
            rating=request.rating,
            feedback_role=request.feedback_role,
            comments=request.comments,
            terminology_issues=request.terminology_issues,
            suggested_corrections=request.suggested_corrections,
        )

        return {
            "success": True,
            "feedback_id": str(feedback.id),
            "rating": feedback.rating,
            "created_at": feedback.created_at.isoformat(),
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        ) from e


@router.get("/statistics/summary", response_model=Dict[str, Any])
async def get_queue_statistics(
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    organization_id: Optional[UUID] = None,
    current_user: UserAuth = current_user_dependency,
    db: Session = db_dependency,
) -> Dict[str, Any]:
    """
    Get translation queue statistics.

    Requires: translate:queue:read permission
    """
    if not current_user.has_permission("translate:queue:read"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions"
        )

    service = TranslationQueueService(db)

    # If organization_id not provided, use user's organization
    if not organization_id and hasattr(current_user, "organization_id"):
        organization_id = current_user.organization_id

    stats = service.get_queue_statistics(
        start_date=start_date, end_date=end_date, organization_id=organization_id
    )

    return stats


@router.post("/cleanup/expired", response_model=Dict[str, Any])
async def cleanup_expired_entries(
    current_user: UserAuth = current_user_dependency, db: Session = db_dependency
) -> Dict[str, Any]:
    """
    Clean up expired queue entries.

    Requires: translate:queue:manage permission
    """
    if not current_user.has_permission("translate:queue:manage"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions"
        )

    service = TranslationQueueService(db)
    count = service.cleanup_expired_entries()

    return {
        "success": True,
        "expired_count": count,
        "cleanup_time": datetime.utcnow().isoformat(),
    }
