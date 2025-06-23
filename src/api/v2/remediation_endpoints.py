"""Remediation and treatment plan REST API endpoints.

This module provides endpoints for managing treatment plans, corrective actions,
and medical interventions in the Haven Health Passport system.
All patient data is encrypted and access controlled for HIPAA compliance.
"""

import uuid
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

router = APIRouter(prefix="/remediation", tags=["remediation"])


# Request/Response Models
class ActionItem(BaseModel):
    """Individual action item in a treatment plan."""

    action_type: str = Field(
        ..., description="Type of action (medication, procedure, lifestyle)"
    )
    description: str
    priority: str = Field(..., pattern="^(low|medium|high|critical)$")
    due_date: Optional[datetime] = None
    assigned_to: Optional[str] = Field(None, description="Healthcare provider ID")
    status: str = Field(
        default="pending", pattern="^(pending|in_progress|completed|cancelled)$"
    )
    notes: Optional[str] = None


class RemediationPlan(BaseModel):
    """Treatment/remediation plan."""

    plan_id: uuid.UUID
    patient_id: uuid.UUID
    condition_codes: List[str] = Field(..., description="Related condition codes")
    plan_type: str = Field(
        ..., description="Plan type (treatment, prevention, management)"
    )
    title: str
    description: str
    actions: List[ActionItem]
    created_by: str
    created_at: datetime
    updated_at: datetime
    status: str = Field(..., pattern="^(draft|active|completed|cancelled)$")
    approval_status: str = Field(
        default="pending", pattern="^(pending|approved|rejected)$"
    )
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None


class ExecuteActionRequest(BaseModel):
    """Request to execute a remediation action."""

    plan_id: uuid.UUID
    action_index: int = Field(..., ge=0, description="Index of action in plan")
    execution_notes: Optional[str] = None
    completed: bool = Field(default=False)
    outcome: Optional[str] = Field(None, description="Outcome of the action")


class RollbackRequest(BaseModel):
    """Request to rollback a remediation action."""

    plan_id: uuid.UUID
    action_index: int = Field(..., ge=0)
    reason: str = Field(..., min_length=10, description="Reason for rollback")
    rollback_to_status: str = Field(default="pending")
