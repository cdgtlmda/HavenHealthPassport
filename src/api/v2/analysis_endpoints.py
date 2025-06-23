"""AI-powered health analysis REST API endpoints.

This module provides endpoints for AI-driven health record analysis,
pattern detection, and recommendations in the Haven Health Passport system.
Handles encrypted patient health information with proper access control.
Supports FHIR Resource validation for healthcare data interoperability.
"""

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.auth.jwt_handler import jwt_handler
from src.auth.rbac import RBACManager
from src.core.database import get_db
from src.utils.logging import get_logger

router = APIRouter(prefix="/analysis", tags=["analysis"])
logger = get_logger(__name__)
security = HTTPBearer()

# Dependency injection
db_dependency = Depends(get_db)
security_dependency = Depends(security)
rbac_manager = RBACManager()


# Request/Response Models
class HealthInsight(BaseModel):
    """Health insight from AI analysis."""

    category: str = Field(
        ..., description="Insight category (risk, recommendation, pattern)"
    )
    severity: str = Field(
        ..., description="Severity level (low, medium, high, critical)"
    )
    title: str = Field(..., description="Brief title of the insight")
    description: str = Field(..., description="Detailed description")
    confidence: float = Field(..., ge=0, le=1, description="Confidence score (0-1)")
    evidence: List[Dict[str, Any]] = Field(
        default=[], description="Supporting evidence"
    )
    recommendations: List[str] = Field(default=[], description="Action recommendations")


class AnalysisRequest(BaseModel):
    """Request for manual health analysis."""

    patient_id: uuid.UUID = Field(..., description="Patient ID to analyze")
    analysis_type: str = Field(
        ..., description="Type of analysis (comprehensive, risk, medication)"
    )
    time_range_days: int = Field(default=365, description="Days of history to analyze")
    focus_areas: Optional[List[str]] = Field(
        None, description="Specific areas to focus on"
    )
    include_predictions: bool = Field(
        default=True, description="Include predictive insights"
    )


class AnalysisResponse(BaseModel):
    """Health analysis response."""

    analysis_id: uuid.UUID
    patient_id: uuid.UUID
    analysis_type: str
    status: str = Field(
        ..., description="Analysis status (completed, in_progress, failed)"
    )
    insights: List[HealthInsight]
    summary: str = Field(..., description="Executive summary of findings")
    risk_score: Optional[float] = Field(
        None, ge=0, le=100, description="Overall risk score"
    )
    created_at: datetime
    analyzed_records_count: int
    processing_time_ms: int


class RecommendationRequest(BaseModel):
    """Request for AI recommendations."""

    patient_id: uuid.UUID
    condition_codes: List[str] = Field(..., description="ICD-10 or SNOMED codes")
    current_medications: Optional[List[str]] = None
    allergies: Optional[List[str]] = None
    preferences: Optional[Dict[str, Any]] = None


class Recommendation(BaseModel):
    """AI-generated recommendation."""

    type: str = Field(
        ..., description="Recommendation type (treatment, lifestyle, followup)"
    )
    priority: str = Field(..., description="Priority level (low, medium, high)")
    title: str
    description: str
    rationale: str = Field(..., description="Medical rationale")
    evidence_based: bool = Field(default=True)
    references: List[str] = Field(default=[], description="Medical references")
    contraindications: List[str] = Field(
        default=[], description="Known contraindications"
    )


class RecommendationResponse(BaseModel):
    """AI recommendations response."""

    patient_id: uuid.UUID
    recommendations: List[Recommendation]
    generated_at: datetime
    model_version: str
    disclaimer: str = Field(
        default="These are AI-generated recommendations. Always consult with healthcare providers."
    )


class FeedbackRequest(BaseModel):
    """Feedback on AI analysis."""

    analysis_id: uuid.UUID
    feedback_type: str = Field(..., pattern="^(helpful|not_helpful|incorrect)$")
    comments: Optional[str] = Field(None, max_length=1000)
    corrected_insights: Optional[List[Dict[str, Any]]] = None


# Helper functions
async def get_current_user(
    credentials: HTTPAuthorizationCredentials = security_dependency,
    db: Session = db_dependency,  # pylint: disable=unused-argument
) -> Dict[str, Any]:
    """Extract and validate current user from JWT token."""
    try:
        token = credentials.credentials
        payload = jwt_handler.verify_token(token)
        return {
            "user_id": payload.get("sub"),
            "email": payload.get("email"),
            "role": payload.get("role"),
            "organization": payload.get("organization"),
        }
    except Exception as e:
        logger.error("Token validation failed: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
        ) from e
