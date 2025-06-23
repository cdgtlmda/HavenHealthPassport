"""Timeout policy management API endpoints.

This module provides REST API endpoints for managing session timeout policies,
including creating, updating, and retrieving timeout configurations.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional, cast

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, validator
from sqlalchemy.orm import Session

from src.api.auth_endpoints import get_current_user
from src.auth.timeout_config import (
    TimeoutConfigManager,
    TimeoutPolicyConfig,
    TimeoutSettings,
)
from src.auth.timeout_config import get_timeout_settings as get_settings
from src.core.database import get_db
from src.models.auth import UserAuth
from src.utils.logging import get_logger

router = APIRouter(prefix="/auth/timeout-policies", tags=["timeout-policies"])
logger = get_logger(__name__)

# Module-level dependency variables to avoid B008 errors
db_dependency = Depends(get_db)
current_user_dependency = Depends(get_current_user)
query_active_only_dependency = Query(True, description="Only return active policies")
query_session_type_dependency = Query(None, description="Filter by session type")
query_days_dependency = Query(30, ge=1, le=365, description="Number of days to analyze")


# Request/Response Models
class TimeoutSettingsModel(BaseModel):
    """Timeout settings model."""

    idle_timeout: int = Field(..., gt=0, description="Idle timeout in minutes")
    absolute_timeout: int = Field(..., gt=0, description="Absolute timeout in minutes")
    renewal_window: int = Field(..., gt=0, description="Renewal window in minutes")
    warning_time: int = Field(..., gt=0, description="Warning time in minutes")
    grace_period: int = Field(..., ge=0, description="Grace period in minutes")

    @validator("absolute_timeout")
    def validate_absolute_timeout(
        cls, v: int, values: Dict[str, Any]
    ) -> int:  # pylint: disable=no-self-argument
        """Ensure absolute timeout is greater than idle timeout."""
        if "idle_timeout" in values and v < values["idle_timeout"]:
            raise ValueError(
                "Absolute timeout must be greater than or equal to idle timeout"
            )
        return v


class CreatePolicyRequest(BaseModel):
    """Create timeout policy request."""

    name: str = Field(..., min_length=3, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    settings: TimeoutSettingsModel
    user_roles: Optional[List[str]] = Field(default_factory=list)
    session_types: Optional[List[str]] = Field(default_factory=list)
    risk_levels: Optional[List[str]] = Field(default_factory=list)
    compliance_levels: Optional[List[str]] = Field(default_factory=list)
    priority: int = Field(0, ge=0, le=1000)


class UpdatePolicyRequest(BaseModel):
    """Update timeout policy request."""

    description: Optional[str] = None
    settings: Optional[TimeoutSettingsModel] = None
    user_roles: Optional[List[str]] = None
    session_types: Optional[List[str]] = None
    risk_levels: Optional[List[str]] = None
    compliance_levels: Optional[List[str]] = None
    priority: Optional[int] = None
    is_active: Optional[bool] = None


class PolicyResponse(BaseModel):
    """Timeout policy response."""

    id: str
    name: str
    description: Optional[str]
    settings: Dict[str, int]
    user_roles: List[str]
    session_types: List[str]
    risk_levels: List[str]
    compliance_levels: List[str]
    priority: int
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime]
    created_by: str

    class Config:
        """Pydantic configuration."""

        from_attributes = True


class GetTimeoutRequest(BaseModel):
    """Get timeout settings request."""

    session_type: str
    user_role: Optional[str] = None
    risk_level: Optional[str] = None
    compliance_level: Optional[str] = None


class TimeoutResponse(BaseModel):
    """Timeout settings response."""

    idle_timeout: int
    absolute_timeout: int
    renewal_window: int
    warning_time: int
    grace_period: int
    policy_name: Optional[str] = None
    applied_adjustments: List[str] = Field(default_factory=list)


class PolicyAnalyticsResponse(BaseModel):
    """Policy analytics response."""

    total_sessions: int
    timeout_distribution: Dict[str, int]
    policy_effectiveness: Dict[str, float]
    risk_level_impact: Dict[str, Any]
    recommendations: List[str]


# Endpoints
@router.post("/", response_model=PolicyResponse)
async def create_timeout_policy(
    request: CreatePolicyRequest,
    current_user: UserAuth = current_user_dependency,
    db: Session = db_dependency,
) -> PolicyResponse:
    """Create a new timeout policy. Requires admin role."""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required"
        )

    try:
        config_manager = TimeoutConfigManager(db)

        # Convert settings to TimeoutSettings object
        settings = TimeoutSettings(
            idle_timeout=request.settings.idle_timeout,
            absolute_timeout=request.settings.absolute_timeout,
            renewal_window=request.settings.renewal_window,
            warning_time=request.settings.warning_time,
            grace_period=request.settings.grace_period,
        )

        # Create policy
        policy = config_manager.create_custom_policy(
            name=request.name,
            settings=settings,
            description=request.description,
            user_roles=request.user_roles,
            session_types=request.session_types,
            risk_levels=request.risk_levels,
            compliance_levels=request.compliance_levels,
            priority=request.priority,
            created_by=str(current_user.id),
        )

        return PolicyResponse(
            id=str(policy.id),
            name=cast(str, policy.name),
            description=cast(Optional[str], policy.description),
            settings=cast(Dict[str, int], policy.settings),
            user_roles=cast(Optional[List[str]], policy.user_roles) or [],
            session_types=cast(Optional[List[str]], policy.session_types) or [],
            risk_levels=cast(Optional[List[str]], policy.risk_levels) or [],
            compliance_levels=cast(Optional[List[str]], policy.compliance_levels) or [],
            priority=cast(int, policy.priority),
            is_active=cast(bool, policy.is_active),
            created_at=cast(datetime, policy.created_at),
            updated_at=cast(Optional[datetime], policy.updated_at),
            created_by=cast(str, policy.created_by),
        )

    except Exception as e:
        logger.error(f"Failed to create timeout policy: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create policy: {str(e)}",
        ) from e


@router.get("/", response_model=List[PolicyResponse])
async def list_timeout_policies(
    active_only: bool = query_active_only_dependency,
    session_type: Optional[str] = query_session_type_dependency,
    current_user: UserAuth = current_user_dependency,
    db: Session = db_dependency,
) -> List[PolicyResponse]:
    """List all timeout policies. Requires admin role."""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required"
        )

    try:
        query = db.query(TimeoutPolicyConfig)

        if active_only:
            query = query.filter(TimeoutPolicyConfig.is_active.is_(True))

        if session_type:
            query = query.filter(
                TimeoutPolicyConfig.session_types.contains([session_type])
            )

        policies = query.order_by(TimeoutPolicyConfig.priority.desc()).all()

        return [
            PolicyResponse(
                id=str(policy.id),
                name=cast(str, policy.name),
                description=cast(Optional[str], policy.description),
                settings=cast(Dict[str, int], policy.settings),
                user_roles=cast(Optional[List[str]], policy.user_roles) or [],
                session_types=cast(Optional[List[str]], policy.session_types) or [],
                risk_levels=cast(Optional[List[str]], policy.risk_levels) or [],
                compliance_levels=cast(Optional[List[str]], policy.compliance_levels)
                or [],
                priority=cast(int, policy.priority),
                is_active=cast(bool, policy.is_active),
                created_at=cast(datetime, policy.created_at),
                updated_at=cast(Optional[datetime], policy.updated_at),
                created_by=cast(str, policy.created_by),
            )
            for policy in policies
        ]

    except Exception as e:
        logger.error(f"Failed to list timeout policies: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve policies",
        ) from e


@router.get("/calculate", response_model=TimeoutResponse)
async def calculate_timeout_settings(
    request: GetTimeoutRequest,
    db: Session = db_dependency,
) -> TimeoutResponse:
    """Calculate timeout settings for given context."""
    try:
        settings = get_settings(
            db=db,
            session_type=request.session_type,
            user_role=request.user_role,
            risk_level=request.risk_level,
            compliance_level=request.compliance_level,
        )

        # Track applied adjustments
        adjustments = []
        if request.risk_level:
            adjustments.append(f"Risk level: {request.risk_level}")
        if request.compliance_level:
            adjustments.append(f"Compliance: {request.compliance_level}")

        return TimeoutResponse(
            idle_timeout=settings.idle_timeout,
            absolute_timeout=settings.absolute_timeout,
            renewal_window=settings.renewal_window,
            warning_time=settings.warning_time,
            grace_period=settings.grace_period,
            applied_adjustments=adjustments,
        )

    except Exception as e:
        logger.error(f"Failed to calculate timeout settings: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to calculate timeout settings",
        ) from e


@router.get("/analytics", response_model=PolicyAnalyticsResponse)
async def get_policy_analytics(
    days: int = query_days_dependency,
    current_user: UserAuth = current_user_dependency,
    db: Session = db_dependency,
) -> PolicyAnalyticsResponse:
    """Get analytics on timeout policy effectiveness. Requires admin role."""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required"
        )

    try:
        config_manager = TimeoutConfigManager(db)
        analytics = config_manager.get_policy_analytics(days=days)

        return PolicyAnalyticsResponse(
            total_sessions=analytics["total_sessions"],
            timeout_distribution=analytics["timeout_distribution"],
            policy_effectiveness=analytics["policy_effectiveness"],
            risk_level_impact=analytics["risk_level_impact"],
            recommendations=analytics["recommendations"],
        )

    except Exception as e:
        logger.error(f"Failed to get policy analytics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve analytics",
        ) from e


@router.get("/{policy_name}", response_model=PolicyResponse)
async def get_timeout_policy(
    policy_name: str,
    current_user: UserAuth = current_user_dependency,
    db: Session = db_dependency,
) -> PolicyResponse:
    """Get a specific timeout policy by name. Requires admin role."""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required"
        )

    try:
        policy = (
            db.query(TimeoutPolicyConfig)
            .filter(TimeoutPolicyConfig.name == policy_name)
            .first()
        )

        if not policy:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Policy '{policy_name}' not found",
            )

        return PolicyResponse(
            id=str(policy.id),
            name=cast(str, policy.name),
            description=cast(Optional[str], policy.description),
            settings=cast(Dict[str, int], policy.settings),
            user_roles=cast(Optional[List[str]], policy.user_roles) or [],
            session_types=cast(Optional[List[str]], policy.session_types) or [],
            risk_levels=cast(Optional[List[str]], policy.risk_levels) or [],
            compliance_levels=cast(Optional[List[str]], policy.compliance_levels) or [],
            priority=cast(int, policy.priority),
            is_active=cast(bool, policy.is_active),
            created_at=cast(datetime, policy.created_at),
            updated_at=cast(Optional[datetime], policy.updated_at),
            created_by=cast(str, policy.created_by),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get timeout policy: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve policy",
        ) from e


@router.put("/{policy_name}", response_model=PolicyResponse)
async def update_timeout_policy(
    policy_name: str,
    request: UpdatePolicyRequest,
    current_user: UserAuth = current_user_dependency,
    db: Session = db_dependency,
) -> PolicyResponse:
    """Update an existing timeout policy. Requires admin role."""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required"
        )

    try:
        config_manager = TimeoutConfigManager(db)

        # Prepare update data
        update_data: Dict[str, Any] = {}
        if request.description is not None:
            update_data["description"] = request.description
        if request.user_roles is not None:
            update_data["user_roles"] = request.user_roles
        if request.session_types is not None:
            update_data["session_types"] = request.session_types
        if request.risk_levels is not None:
            update_data["risk_levels"] = request.risk_levels
        if request.compliance_levels is not None:
            update_data["compliance_levels"] = request.compliance_levels
        if request.priority is not None:
            update_data["priority"] = request.priority
        if request.is_active is not None:
            update_data["is_active"] = request.is_active

        # Convert settings if provided
        settings = None
        if request.settings:
            settings = TimeoutSettings(
                idle_timeout=request.settings.idle_timeout,
                absolute_timeout=request.settings.absolute_timeout,
                renewal_window=request.settings.renewal_window,
                warning_time=request.settings.warning_time,
                grace_period=request.settings.grace_period,
            )

        # Update policy
        policy = config_manager.update_policy(
            name=policy_name, settings=settings, **update_data
        )

        if not policy:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Policy '{policy_name}' not found",
            )

        return PolicyResponse(
            id=str(policy.id),
            name=cast(str, policy.name),
            description=cast(Optional[str], policy.description),
            settings=cast(Dict[str, int], policy.settings),
            user_roles=cast(Optional[List[str]], policy.user_roles) or [],
            session_types=cast(Optional[List[str]], policy.session_types) or [],
            risk_levels=cast(Optional[List[str]], policy.risk_levels) or [],
            compliance_levels=cast(Optional[List[str]], policy.compliance_levels) or [],
            priority=cast(int, policy.priority),
            is_active=cast(bool, policy.is_active),
            created_at=cast(datetime, policy.created_at),
            updated_at=cast(Optional[datetime], policy.updated_at),
            created_by=cast(str, policy.created_by),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update timeout policy: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update policy: {str(e)}",
        ) from e


@router.delete("/{policy_name}")
async def deactivate_timeout_policy(
    policy_name: str,
    current_user: UserAuth = current_user_dependency,
    db: Session = db_dependency,
) -> Dict[str, str]:
    """Deactivate a timeout policy. Requires admin role."""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required"
        )

    try:
        config_manager = TimeoutConfigManager(db)

        if config_manager.deactivate_policy(policy_name):
            return {"message": f"Policy '{policy_name}' deactivated successfully"}
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Policy '{policy_name}' not found",
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to deactivate timeout policy: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to deactivate policy",
        ) from e
