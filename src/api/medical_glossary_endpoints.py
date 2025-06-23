"""API endpoints for Medical Glossary management."""

import io
import os
import tempfile
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Body, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.auth.jwt_handler import JWTHandler
from src.core.database import get_db
from src.models.user import User
from src.translation.medical_glossary import (
    TermCategory,
    get_medical_glossary_service,
)
from src.utils.logging import get_logger

# Create JWT handler instance
jwt_handler = JWTHandler()
logger = get_logger(__name__)


# Module-level dependency variables to avoid B008 errors
decode_token_dependency = Depends(jwt_handler.decode_token)


def get_current_user(token: str = decode_token_dependency) -> str:
    """Get current user from JWT token."""
    return token


# Module-level dependency variables to avoid B008 errors
db_dependency = Depends(get_db)
current_user_dependency = Depends(get_current_user)

# Query parameter dependencies
query_required_dependency = Query(..., description="Search query")
query_language_dependency = Query(default="en", description="Language")
query_language_source_dependency = Query(default="en", description="Source language")
query_target_language_dependency = Query(..., description="Target language")
query_category_optional_dependency = Query(None, description="Category filter")
query_include_synonyms_dependency = Query(default=True)
query_limit_dependency = Query(default=10, ge=1, le=50)
query_emergency_only_dependency = Query(default=False)
query_export_format_dependency = Query(
    default="json", description="Export format (json, csv)", alias="format"
)
query_include_translations_dependency = Query(default=True)

# File and Body dependencies
file_upload_dependency = File(..., description="CSV or JSON file with WHO terminology")
body_notes_optional_dependency = Body(None, description="Verification notes")

router = APIRouter(prefix="/api/v1/medical-glossary", tags=["medical-glossary"])


class TermSearchRequest(BaseModel):
    """Request model for term search."""

    query: str = Field(..., description="Search query")
    language: str = Field(default="en", description="Language code")
    category: Optional[str] = Field(None, description="Filter by category")
    include_synonyms: bool = Field(default=True, description="Search in synonyms")
    limit: int = Field(default=10, ge=1, le=50, description="Maximum results")


class TermTranslationRequest(BaseModel):
    """Request model for term translation."""

    term: str = Field(..., description="Medical term")
    target_language: str = Field(..., description="Target language code")
    source_language: str = Field(default="en", description="Source language code")


class AddTranslationRequest(BaseModel):
    """Request model for adding translation."""

    term: str = Field(..., description="Source term")
    translation: str = Field(..., description="Translation")
    target_language: str = Field(..., description="Target language")
    source_language: str = Field(default="en", description="Source language")
    verified: bool = Field(default=False, description="Is verified translation")


class TermInfo(BaseModel):
    """Medical term information."""

    id: str
    term: str
    language: str
    category: str
    definition: Optional[str]
    synonyms: List[str]
    translations: Dict[str, str]
    who_code: Optional[str]
    verified: bool
    usage_count: int


@router.get("/search", response_model=List[TermInfo])
async def search_medical_terms(
    query: str = query_required_dependency,
    language: str = query_language_dependency,
    category: Optional[str] = query_category_optional_dependency,
    include_synonyms: bool = query_include_synonyms_dependency,
    limit: int = query_limit_dependency,
    db: Session = db_dependency,
) -> List[TermInfo]:
    """
    Search for medical terms in the glossary.

    Returns matching terms with translations and metadata.
    """
    try:
        glossary_service = get_medical_glossary_service(db)

        # Convert category string to enum if provided
        category_enum = None
        if category:
            try:
                category_enum = TermCategory(category)
            except ValueError:
                raise HTTPException(
                    status_code=400, detail=f"Invalid category: {category}"
                ) from None

        results = glossary_service.search_terms(
            query=query,
            language=language,
            category=category_enum,
            include_synonyms=include_synonyms,
            limit=limit,
        )

        # Convert to response format
        terms = []
        for result in results:
            terms.append(
                TermInfo(
                    id=str(result.id),
                    term=str(result.term_display),
                    language=str(result.language),
                    category=str(result.category),
                    definition=str(result.definition) if result.definition else None,
                    synonyms=list(result.synonyms) if result.synonyms else [],
                    translations=(
                        dict(result.translations) if result.translations else {}
                    ),
                    who_code=str(result.who_code) if result.who_code else None,
                    verified=bool(result.verified),
                    usage_count=int(result.usage_count),
                )
            )

        return terms

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Medical term search error: {e}")
        raise HTTPException(status_code=500, detail="Search failed") from e


@router.get("/term/{term}/translate")
async def get_term_translation(
    term: str,
    target_language: str = query_target_language_dependency,
    source_language: str = query_language_source_dependency,
    db: Session = db_dependency,
) -> Dict[str, str]:
    """Get translation for a specific medical term."""
    try:
        glossary_service = get_medical_glossary_service(db)

        translation = glossary_service.get_term_translation(
            term=term, target_language=target_language, source_language=source_language
        )

        if not translation:
            raise HTTPException(
                status_code=404,
                detail=f"No translation found for '{term}' in {target_language}",
            )

        return {
            "term": term,
            "source_language": source_language,
            "target_language": target_language,
            "translation": translation,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Term translation error: {e}")
        raise HTTPException(status_code=500, detail="Translation lookup failed") from e


@router.post("/term/{term}/translate")
async def add_term_translation(
    term: str,
    request: AddTranslationRequest,
    db: Session = db_dependency,
    current_user: User = current_user_dependency,
) -> Dict[str, Any]:
    """
    Add or update a translation for a medical term.

    Requires authentication. Verified translations require admin privileges.
    """
    try:
        # Check if user can verify translations
        can_verify = getattr(current_user, "is_superuser", False) or hasattr(
            current_user, "is_medical_professional"
        )

        if request.verified and not can_verify:
            raise HTTPException(
                status_code=403,
                detail="Only medical professionals can verify translations",
            )

        glossary_service = get_medical_glossary_service(db)

        success = glossary_service.add_term_translation(
            term=term,
            translation=request.translation,
            target_language=request.target_language,
            source_language=request.source_language,
            verified=request.verified and can_verify,
        )

        if not success:
            raise HTTPException(status_code=404, detail="Term not found in glossary")

        return {
            "success": True,
            "term": term,
            "translation": request.translation,
            "target_language": request.target_language,
            "verified": request.verified and can_verify,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Add translation error: {e}")
        raise HTTPException(status_code=500, detail="Failed to add translation") from e


@router.get("/categories")
async def get_categories() -> List[Dict[str, str]]:
    """Get all available medical term categories."""
    return [
        {"code": category.value, "name": category.name.replace("_", " ").title()}
        for category in TermCategory
    ]


@router.get("/category/{category}/terms", response_model=List[TermInfo])
async def get_terms_by_category(
    category: str,
    language: str = query_language_dependency,
    emergency_only: bool = query_emergency_only_dependency,
    db: Session = db_dependency,
) -> List[TermInfo]:
    """Get all terms in a specific category."""
    try:
        # Validate category
        try:
            category_enum = TermCategory(category)
        except ValueError:
            raise HTTPException(
                status_code=400, detail=f"Invalid category: {category}"
            ) from None

        glossary_service = get_medical_glossary_service(db)

        results = glossary_service.get_terms_by_category(
            category=category_enum, language=language, emergency_only=emergency_only
        )

        # Convert to response format
        terms = []
        for result in results:
            terms.append(
                TermInfo(
                    id=str(result.id),
                    term=str(result.term_display),
                    language=str(result.language),
                    category=str(result.category),
                    definition=str(result.definition) if result.definition else None,
                    synonyms=list(result.synonyms) if result.synonyms else [],
                    translations=(
                        dict(result.translations) if result.translations else {}
                    ),
                    who_code=str(result.who_code) if result.who_code else None,
                    verified=bool(result.verified),
                    usage_count=int(result.usage_count),
                )
            )

        return terms

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get category terms error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get terms") from e


@router.get("/emergency-terms")
async def get_emergency_terms(
    language: str = query_language_dependency, db: Session = db_dependency
) -> Dict[str, Any]:
    """Get emergency-relevant medical terms with translations."""
    try:
        glossary_service = get_medical_glossary_service(db)
        terms = glossary_service.get_emergency_terms(language)

        return {"language": language, "terms": terms, "count": len(terms)}

    except Exception as e:
        logger.error(f"Get emergency terms error: {e}")
        raise HTTPException(
            status_code=500, detail="Failed to get emergency terms"
        ) from e


@router.post("/import")
async def import_medical_terminology(
    file: UploadFile = file_upload_dependency,
    db: Session = db_dependency,
    current_user: User = current_user_dependency,
) -> Dict[str, Any]:
    """
    Import WHO/UN medical terminology from file.

    Admin only endpoint.
    """
    try:
        # Check admin permission
        if not getattr(current_user, "is_superuser", False):
            raise HTTPException(status_code=403, detail="Admin access required")

        # Validate file type
        if not file.filename or not file.filename.endswith((".csv", ".json")):
            raise HTTPException(
                status_code=400, detail="Only CSV and JSON files are supported"
            )

        # Save temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix=file.filename) as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name

        glossary_service = get_medical_glossary_service(db)
        imported = glossary_service.import_who_terminology(tmp_path)

        # Clean up
        os.unlink(tmp_path)

        return {"success": True, "imported_terms": imported, "filename": file.filename}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Import terminology error: {e}")
        raise HTTPException(status_code=500, detail="Import failed") from e


@router.get("/export")
async def export_glossary(
    export_format: str = query_export_format_dependency,
    language: str = query_language_dependency,
    include_translations: bool = query_include_translations_dependency,
    db: Session = db_dependency,
) -> StreamingResponse:
    """Export medical glossary in specified format."""
    try:
        glossary_service = get_medical_glossary_service(db)

        data = glossary_service.export_glossary(
            language=language, include_translations=include_translations
        )

        # Set appropriate content type
        content_types = {"json": "application/json", "csv": "text/csv"}

        content_type = content_types.get(export_format, "text/plain")

        # Generate filename
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filename = f"medical_glossary_{language}_{timestamp}.{export_format}"

        return StreamingResponse(
            io.StringIO(data),
            media_type=content_type,
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )

    except Exception as e:
        logger.error(f"Export glossary error: {e}")
        raise HTTPException(status_code=500, detail="Export failed") from e


@router.post("/term/{term_id}/verify")
async def verify_medical_term(
    term_id: UUID,
    notes: Optional[str] = body_notes_optional_dependency,
    db: Session = db_dependency,
    current_user: User = current_user_dependency,
) -> Dict[str, Any]:
    """
    Mark a medical term as verified.

    Requires medical professional privileges.
    """
    try:
        # Check medical professional permission
        if not (
            getattr(current_user, "is_superuser", False)
            or hasattr(current_user, "is_medical_professional")
        ):
            raise HTTPException(
                status_code=403, detail="Only medical professionals can verify terms"
            )

        glossary_service = get_medical_glossary_service(db)

        success = glossary_service.verify_term(
            term_id=term_id, verified_by=uuid.UUID(str(current_user.id)), notes=notes
        )

        if not success:
            raise HTTPException(status_code=404, detail="Term not found")

        return {
            "success": True,
            "term_id": str(term_id),
            "verified_by": str(current_user.id),
            "verified_at": datetime.utcnow().isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Verify term error: {e}")
        raise HTTPException(status_code=500, detail="Verification failed") from e


@router.get("/statistics")
async def get_glossary_statistics(db: Session = db_dependency) -> Dict[str, Any]:
    """Get medical glossary statistics."""
    try:
        glossary_service = get_medical_glossary_service(db)
        stats = glossary_service.get_statistics()

        return stats

    except Exception as e:
        logger.error(f"Get statistics error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get statistics") from e


# Include router in main app
__all__ = ["router"]
