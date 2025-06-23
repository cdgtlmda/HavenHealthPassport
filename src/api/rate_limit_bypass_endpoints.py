"""Rate limit bypass management endpoints.

This module provides REST API endpoints for managing rate limit bypass rules
dynamically without requiring server restarts.
"""

# flake8: noqa: B008  # FastAPI Depends() is designed to be used in function defaults

from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from src.api.auth_endpoints import get_current_user
from src.middleware.rate_limit_bypass import RateLimitBypassRule, bypass_config
from src.models.auth import UserAuth, UserRole
from src.utils.logging import get_logger

router = APIRouter(prefix="/rate-limit/bypass", tags=["rate-limit", "admin"])
logger = get_logger(__name__)


# Request/Response Models
class CreateBypassRuleRequest(BaseModel):
    """Request model for creating a bypass rule."""

    name: str = Field(..., min_length=1, max_length=100)
    description: str = Field(..., min_length=1, max_length=500)
    enabled: bool = Field(default=True)
    ip_addresses: List[str] = Field(default_factory=list)
    ip_ranges: List[str] = Field(default_factory=list)
    user_agents: List[str] = Field(default_factory=list)
    api_key_prefixes: List[str] = Field(default_factory=list)
    api_key_tiers: List[str] = Field(default_factory=list)
    paths: List[str] = Field(default_factory=list)
    headers: dict = Field(default_factory=dict)


class BypassRuleResponse(BaseModel):
    """Response model for bypass rule."""

    name: str
    description: str
    enabled: bool
    ip_addresses: List[str]
    ip_ranges: List[str]
    user_agents: List[str]
    api_key_prefixes: List[str]
    api_key_tiers: List[str]
    paths: List[str]
    headers: dict


class UpdateBypassRuleRequest(BaseModel):
    """Request model for updating a bypass rule."""

    description: Optional[str] = Field(None, min_length=1, max_length=500)
    enabled: Optional[bool] = None
    ip_addresses: Optional[List[str]] = None
    ip_ranges: Optional[List[str]] = None
    user_agents: Optional[List[str]] = None
    api_key_prefixes: Optional[List[str]] = None
    api_key_tiers: Optional[List[str]] = None
    paths: Optional[List[str]] = None
    headers: Optional[Dict[str, str]] = None


# Admin check dependency
async def require_admin(current_user: UserAuth = Depends(get_current_user)) -> UserAuth:
    """Require admin role for accessing these endpoints."""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return current_user


# Endpoints
@router.get("/rules", response_model=List[BypassRuleResponse])
async def list_bypass_rules(
    _: UserAuth = Depends(require_admin),
) -> List[BypassRuleResponse]:
    """List all rate limit bypass rules."""
    return [
        BypassRuleResponse(
            name=rule.name,
            description=rule.description,
            enabled=rule.enabled,
            ip_addresses=rule.ip_addresses or [],
            ip_ranges=rule.ip_ranges or [],
            user_agents=rule.user_agents or [],
            api_key_prefixes=rule.api_key_prefixes or [],
            api_key_tiers=rule.api_key_tiers or [],
            paths=rule.paths or [],
            headers=rule.headers or {},
        )
        for rule in bypass_config.rules
    ]


@router.post(
    "/rules", response_model=BypassRuleResponse, status_code=status.HTTP_201_CREATED
)
async def create_bypass_rule(
    request: CreateBypassRuleRequest,
    _: UserAuth = Depends(require_admin),
) -> BypassRuleResponse:
    """Create a new rate limit bypass rule."""
    try:
        # Check if rule with same name exists
        existing = next(
            (r for r in bypass_config.rules if r.name == request.name), None
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Rule with name '{request.name}' already exists",
            )

        # Create the rule
        rule = RateLimitBypassRule(
            name=request.name,
            description=request.description,
            enabled=request.enabled,
            ip_addresses=request.ip_addresses if request.ip_addresses else None,
            ip_ranges=request.ip_ranges if request.ip_ranges else None,
            user_agents=request.user_agents if request.user_agents else None,
            api_key_prefixes=(
                request.api_key_prefixes if request.api_key_prefixes else None
            ),
            api_key_tiers=request.api_key_tiers if request.api_key_tiers else None,
            paths=request.paths if request.paths else None,
            headers=request.headers if request.headers else None,
        )

        # Add the rule
        bypass_config.add_rule(rule)

        logger.info(f"Created bypass rule: {rule.name}")

        return BypassRuleResponse(
            name=rule.name,
            description=rule.description,
            enabled=rule.enabled,
            ip_addresses=rule.ip_addresses or [],
            ip_ranges=rule.ip_ranges or [],
            user_agents=rule.user_agents or [],
            api_key_prefixes=rule.api_key_prefixes or [],
            api_key_tiers=rule.api_key_tiers or [],
            paths=rule.paths or [],
            headers=rule.headers or {},
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@router.get("/rules/{rule_name}", response_model=BypassRuleResponse)
async def get_bypass_rule(
    rule_name: str,
    _: UserAuth = Depends(require_admin),
) -> BypassRuleResponse:
    """Get a specific bypass rule by name."""
    rule = next((r for r in bypass_config.rules if r.name == rule_name), None)

    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Rule '{rule_name}' not found",
        )

    return BypassRuleResponse(
        name=rule.name,
        description=rule.description,
        enabled=rule.enabled,
        ip_addresses=rule.ip_addresses or [],
        ip_ranges=rule.ip_ranges or [],
        user_agents=rule.user_agents or [],
        api_key_prefixes=rule.api_key_prefixes or [],
        api_key_tiers=rule.api_key_tiers or [],
        paths=rule.paths or [],
        headers=rule.headers or {},
    )


@router.patch("/rules/{rule_name}", response_model=BypassRuleResponse)
async def update_bypass_rule(
    rule_name: str,
    request: UpdateBypassRuleRequest,
    _: UserAuth = Depends(require_admin),
) -> BypassRuleResponse:
    """Update an existing bypass rule."""
    # Find the rule
    rule_index = next(
        (i for i, r in enumerate(bypass_config.rules) if r.name == rule_name), None
    )

    if rule_index is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Rule '{rule_name}' not found",
        )

    rule = bypass_config.rules[rule_index]

    # Update fields if provided
    if request.description is not None:
        rule.description = request.description
    if request.enabled is not None:
        rule.enabled = request.enabled
    if request.ip_addresses is not None:
        rule.ip_addresses = request.ip_addresses if request.ip_addresses else None
    if request.ip_ranges is not None:
        rule.ip_ranges = request.ip_ranges if request.ip_ranges else None
    if request.user_agents is not None:
        rule.user_agents = request.user_agents if request.user_agents else None
    if request.api_key_prefixes is not None:
        rule.api_key_prefixes = (
            request.api_key_prefixes if request.api_key_prefixes else None
        )
    if request.api_key_tiers is not None:
        rule.api_key_tiers = request.api_key_tiers if request.api_key_tiers else None
    if request.paths is not None:
        rule.paths = request.paths if request.paths else None
    if request.headers is not None:
        rule.headers = request.headers if request.headers else None

    # Update caches
    # Note: _update_caches is a protected method but we need to call it
    # Consider adding a public method for cache updates in BypassConfiguration
    if hasattr(bypass_config, "_update_caches"):
        bypass_config._update_caches()  # pylint: disable=protected-access

    logger.info(f"Updated bypass rule: {rule_name}")

    return BypassRuleResponse(
        name=rule.name,
        description=rule.description,
        enabled=rule.enabled,
        ip_addresses=rule.ip_addresses or [],
        ip_ranges=rule.ip_ranges or [],
        user_agents=rule.user_agents or [],
        api_key_prefixes=rule.api_key_prefixes or [],
        api_key_tiers=rule.api_key_tiers or [],
        paths=rule.paths or [],
        headers=rule.headers or {},
    )


@router.delete("/rules/{rule_name}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_bypass_rule(
    rule_name: str,
    _: UserAuth = Depends(require_admin),
) -> None:
    """Delete a bypass rule."""
    # Check if rule exists
    rule = next((r for r in bypass_config.rules if r.name == rule_name), None)

    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Rule '{rule_name}' not found",
        )

    # Don't allow deletion of core rules
    core_rules = ["health_checks", "monitoring", "load_balancer"]
    if rule_name in core_rules:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot delete core rule '{rule_name}'",
        )

    # Remove the rule
    bypass_config.remove_rule(rule_name)

    logger.info(f"Deleted bypass rule: {rule_name}")
