"""API endpoints for Translation Memory management."""

import io
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.api.auth_endpoints import get_current_user
from src.core.database import get_db
from src.models.auth import UserAuth
from src.services.translation_service import TranslationDirection, TranslationService
from src.translation.translation_memory import get_translation_memory_service
from src.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/translation-memory", tags=["translation-memory"])

# Module-level dependency variables to avoid B008 errors
db_dependency = Depends(get_db)
current_user_dependency = Depends(get_current_user)
file_upload_dependency = File(..., description="TMX, JSON, or CSV file")
form_file_format_dependency = Form(..., description="File format")
# Query dependencies
query_file_format_dependency = Query(default="tmx", description="Export format")
query_source_language_dependency = Query(None, description="Filter by source language")
query_target_language_dependency = Query(None, description="Filter by target language")
query_min_quality_dependency = Query(
    default=0.5, ge=0.0, le=1.0, description="Minimum quality"
)
query_min_quality_cleanup_dependency = Query(default=0.3, ge=0.0, le=1.0)
query_max_age_days_dependency = Query(default=365, ge=1)
query_min_usage_dependency = Query(default=0, ge=0)
query_texts_dependency = Query(..., description="Texts to translate")
query_target_language_required_dependency = Query(..., description="Target language")
query_source_language_optional_dependency = Query(None, description="Source language")
query_threshold_dependency = Query(
    default=0.85, ge=0.0, le=1.0, description="Match threshold"
)


class TMSearchRequest(BaseModel):
    """Request model for TM search."""

    text: str = Field(..., description="Text to search for")
    target_language: TranslationDirection = Field(..., description="Target language")
    source_language: Optional[TranslationDirection] = Field(
        None, description="Source language"
    )
    min_score: float = Field(
        default=0.7, ge=0.0, le=1.0, description="Minimum similarity score"
    )
    max_results: int = Field(default=5, ge=1, le=50, description="Maximum results")


class TMSearchResult(BaseModel):
    """Translation memory search result."""

    source_text: str
    target_text: str
    match_type: str
    score: float
    metadata: Dict[str, Any]
    usage_count: int
    last_used: str


class TMImportRequest(BaseModel):
    """Request model for TM import."""

    file_format: str = Field(..., description="Import format (tmx, json, csv)")
    data: str = Field(..., description="Import data")
    source_type: str = Field(default="import", description="Source type")


class TMExportRequest(BaseModel):
    """Request model for TM export."""

    file_format: str = Field(
        default="tmx", description="Export format (tmx, json, csv)"
    )
    source_language: Optional[str] = Field(
        None, description="Filter by source language"
    )
    target_language: Optional[str] = Field(
        None, description="Filter by target language"
    )
    min_quality: float = Field(
        default=0.5, ge=0.0, le=1.0, description="Minimum quality score"
    )


class TMQualityUpdateRequest(BaseModel):
    """Request model for quality update."""

    quality_delta: float = Field(
        ..., ge=-1.0, le=1.0, description="Change in quality score"
    )
    reason: str = Field(..., description="Reason for update")


class TMCoverageRequest(BaseModel):
    """Request model for coverage calculation."""

    text: str = Field(..., description="Text to analyze")
    target_language: TranslationDirection = Field(..., description="Target language")
    source_language: Optional[TranslationDirection] = Field(
        None, description="Source language"
    )


@router.post("/search", response_model=List[TMSearchResult])
async def search_translation_memory(
    request: TMSearchRequest,
    db: Session = db_dependency,
    current_user: UserAuth = current_user_dependency,
) -> List[TMSearchResult]:
    """
    Search translation memory for similar translations.

    Returns matches with similarity scores and metadata.
    """
    try:
        translation_service = TranslationService(db)
        translation_service.current_user_id = current_user.id

        results = translation_service.search_translation_memory(
            text=request.text,
            target_language=request.target_language,
            source_language=request.source_language,
            min_score=request.min_score,
            max_results=request.max_results,
        )

        return [TMSearchResult(**result) for result in results]

    except Exception as e:
        logger.error(f"TM search error: {e}")
        raise HTTPException(
            status_code=500, detail="Translation memory search failed"
        ) from e


@router.post("/import")
async def import_translation_memory(
    request: TMImportRequest,
    db: Session = db_dependency,
    current_user: UserAuth = current_user_dependency,
) -> Dict[str, Any]:
    """
    Import translations into translation memory.

    Supports TMX, JSON, and CSV formats.
    """
    try:
        # Check user permissions
        if not current_user.is_superuser:
            # Check if user has translation management permission
            # This could be implemented with a role-based system
            pass

        translation_service = TranslationService(db)
        translation_service.current_user_id = current_user.id

        result = translation_service.import_translation_memory(
            file_format=request.file_format,
            data=request.data,
            source_type=request.source_type,
        )

        return result

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.error(f"TM import error: {e}")
        raise HTTPException(
            status_code=500, detail="Translation memory import failed"
        ) from e


@router.post("/import/file")
async def import_translation_memory_file(
    file: UploadFile = file_upload_dependency,
    file_format: str = form_file_format_dependency,
    db: Session = db_dependency,
    current_user: UserAuth = current_user_dependency,
) -> Dict[str, Any]:
    """Import translation memory from uploaded file."""
    try:
        # Validate file format
        allowed_formats = ["tmx", "json", "csv"]
        if file_format not in allowed_formats:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid format. Allowed: {', '.join(allowed_formats)}",
            )

        # Read file content
        content = await file.read()
        data = content.decode("utf-8")

        translation_service = TranslationService(db)
        translation_service.current_user_id = current_user.id

        result = translation_service.import_translation_memory(
            file_format=file_format, data=data, source_type=f"{file_format}_file_import"
        )

        return {**result, "filename": file.filename, "size": len(content)}

    except UnicodeDecodeError as exc:
        raise HTTPException(
            status_code=400, detail="Invalid file encoding. Expected UTF-8"
        ) from exc
    except Exception as e:
        logger.error(f"TM file import error: {e}")
        raise HTTPException(status_code=500, detail="File import failed") from e


@router.get("/export")
async def export_translation_memory(
    file_format: str = query_file_format_dependency,
    source_language: Optional[str] = query_source_language_dependency,
    target_language: Optional[str] = query_target_language_dependency,
    min_quality: float = query_min_quality_dependency,
    db: Session = db_dependency,
    current_user: UserAuth = current_user_dependency,
) -> StreamingResponse:
    """Export translation memory in specified format."""
    try:
        translation_service = TranslationService(db)
        translation_service.current_user_id = current_user.id

        data = translation_service.export_translation_memory_to_file(
            file_format=file_format,
            source_language=source_language,
            target_language=target_language,
            min_quality=min_quality,
        )

        # Set appropriate content type
        content_types = {
            "tmx": "application/x-tmx+xml",
            "json": "application/json",
            "csv": "text/csv",
        }

        content_type = content_types.get(file_format, "text/plain")

        # Generate filename
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filename = f"translation_memory_{timestamp}.{file_format}"

        # Return as streaming response
        return StreamingResponse(
            io.StringIO(data),
            media_type=content_type,
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )

    except Exception as e:
        logger.error(f"TM export error: {e}")
        raise HTTPException(status_code=500, detail="Export failed") from e


@router.get("/statistics")
async def get_translation_memory_statistics(
    source_language: Optional[str] = query_source_language_dependency,
    target_language: Optional[str] = query_target_language_dependency,
    db: Session = db_dependency,
    current_user: UserAuth = current_user_dependency,
) -> Dict[str, Any]:
    """Get translation memory statistics."""
    # Currently unused parameters - will be used for filtering when implemented
    _ = (
        source_language,
        target_language,
        current_user,
    )  # Acknowledge unused parameters
    try:
        translation_service = TranslationService(db)
        stats = translation_service.get_translation_memory_statistics()

        return stats

    except Exception as e:
        logger.error(f"TM statistics error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get statistics") from e


@router.patch("/segments/{segment_id}/quality")
async def update_segment_quality(
    segment_id: UUID,
    request: TMQualityUpdateRequest,
    db: Session = db_dependency,
    current_user: UserAuth = current_user_dependency,
) -> Dict[str, Any]:
    """Update quality score of a translation memory segment."""
    try:
        translation_service = TranslationService(db)
        translation_service.current_user_id = current_user.id

        success = translation_service.update_translation_quality(
            segment_id=segment_id,
            quality_delta=request.quality_delta,
            reason=request.reason,
        )

        if not success:
            raise HTTPException(status_code=404, detail="Segment not found")

        return {"success": True, "segment_id": str(segment_id)}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Quality update error: {e}")
        raise HTTPException(status_code=500, detail="Quality update failed") from e


@router.post("/coverage")
async def calculate_coverage(
    request: TMCoverageRequest,
    db: Session = db_dependency,
    current_user: UserAuth = current_user_dependency,
) -> Dict[str, Any]:
    """
    Calculate translation memory coverage for a text.

    Returns percentage of text covered by existing translations.
    """
    try:
        translation_service = TranslationService(db)
        translation_service.current_user_id = current_user.id

        coverage = translation_service.calculate_translation_coverage(
            text=request.text,
            target_language=request.target_language,
            source_language=request.source_language,
        )

        return coverage

    except Exception as e:
        logger.error(f"Coverage calculation error: {e}")
        raise HTTPException(
            status_code=500, detail="Coverage calculation failed"
        ) from e


@router.delete("/cleanup")
async def cleanup_translation_memory(
    min_quality: float = query_min_quality_cleanup_dependency,
    max_age_days: int = query_max_age_days_dependency,
    min_usage: int = query_min_usage_dependency,
    db: Session = db_dependency,
    current_user: UserAuth = current_user_dependency,
) -> Dict[str, Any]:
    """
    Clean up old or low-quality translation memory segments.

    Admin endpoint.
    """
    try:
        # Check admin permission
        if not current_user.is_superuser:
            raise HTTPException(status_code=403, detail="Admin access required")

        # Use TM service directly for cleanup
        tm_service = get_translation_memory_service(db)

        removed = tm_service.cleanup(
            min_quality=min_quality, max_age_days=max_age_days, min_usage=min_usage
        )

        return {
            "success": True,
            "removed_segments": removed,
            "criteria": {
                "min_quality": min_quality,
                "max_age_days": max_age_days,
                "min_usage": min_usage,
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"TM cleanup error: {e}")
        raise HTTPException(status_code=500, detail="Cleanup failed") from e


@router.post("/leverage")
async def leverage_translation_memory(
    texts: List[str] = query_texts_dependency,
    target_language: TranslationDirection = query_target_language_required_dependency,
    source_language: Optional[
        TranslationDirection
    ] = query_source_language_optional_dependency,
    threshold: float = query_threshold_dependency,
    db: Session = db_dependency,
    current_user: UserAuth = current_user_dependency,
) -> List[Dict[str, Any]]:
    """
    Leverage translation memory for batch translation.

    Returns texts with TM matches applied where available.
    """
    try:
        translation_service = TranslationService(db)
        translation_service.current_user_id = current_user.id

        results = []

        for text in texts:
            # Search for TM matches
            matches = translation_service.search_translation_memory(
                text=text,
                target_language=target_language,
                source_language=source_language,
                min_score=threshold,
                max_results=1,
            )

            if matches and matches[0]["score"] >= threshold:
                # Use TM match
                results.append(
                    {
                        "source_text": text,
                        "target_text": matches[0]["target_text"],
                        "match_type": matches[0]["match_type"],
                        "score": matches[0]["score"],
                        "from_tm": True,
                    }
                )
            else:
                # No suitable match
                results.append(
                    {
                        "source_text": text,
                        "target_text": None,
                        "match_type": "no_match",
                        "score": 0.0,
                        "from_tm": False,
                    }
                )

        # Statistics could be calculated here if needed
        # tm_matches = sum(1 for r in results if r["from_tm"])

        return results

    except Exception as e:
        logger.error(f"TM leverage error: {e}")
        raise HTTPException(status_code=500, detail="Leverage failed") from e


# Include router in main app
__all__ = ["router"]
