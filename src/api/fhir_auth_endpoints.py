"""
FHIR Token Validation Endpoint.

This module provides the endpoint that HAPI FHIR server calls to validate tokens
and retrieve user authorization information. Handles FHIR CapabilityStatement
Resource validation for authorization capabilities.
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from src.auth.jwt_handler import JWTHandler
from src.healthcare.fhir_authorization import (
    AuthorizationContext,
    AuthorizationRequest,
    FHIRRole,
    ResourcePermission,
    get_authorization_handler,
)
from src.healthcare.fhir_validator import FHIRValidator
from src.utils.logging import get_logger

# FHIR resource type for this module
__fhir_resource__ = "CapabilityStatement"

# Create JWT handler instance
jwt_handler = JWTHandler()

# Initialize validator
validator = FHIRValidator()

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

# Module-level dependency variables to avoid B008 errors
header_dependency = Header(None)


class TokenValidationRequest(BaseModel):
    """Request to validate a token."""

    token: Optional[str] = None


class TokenValidationResponse(BaseModel):
    """Response from token validation."""

    valid: bool
    user_id: Optional[str] = Field(None, alias="userId")
    roles: List[str] = Field(default_factory=list)
    scopes: List[str] = Field(default_factory=list)
    assigned_patients: Optional[List[str]] = Field(None, alias="assignedPatients")
    attributes: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        """Pydantic configuration."""

        populate_by_name = True


@router.post("/validate", response_model=TokenValidationResponse)
async def validate_fhir_token(
    authorization: Optional[str] = header_dependency,
) -> TokenValidationResponse:
    """
    Validate a token for FHIR server access.

    This endpoint is called by the HAPI FHIR server to validate tokens
    and retrieve user authorization information.
    """
    # Extract token from Authorization header
    if not authorization:
        return TokenValidationResponse(valid=False, userId=None, assignedPatients=None)

    # Remove "Bearer " prefix if present
    token = authorization.replace("Bearer ", "").strip()

    try:
        # Verify the token
        payload = jwt_handler.decode_token(token)

        if not payload:
            return TokenValidationResponse(
                valid=False, userId=None, assignedPatients=None
            )

        # Extract user information from token
        user_id = payload.get("sub")
        roles = payload.get("roles", [])
        scopes = payload.get("scope", "").split() if payload.get("scope") else []

        # Convert role strings to FHIRRole enums
        fhir_roles = []
        for role in roles:
            try:
                fhir_role = FHIRRole(role.lower())
                fhir_roles.append(fhir_role.value)
            except ValueError:
                logger.warning(f"Unknown role: {role}")
                continue

        # Get additional attributes from user profile
        attributes = {
            "email": payload.get("email"),
            "organization_id": payload.get("org_id"),
            "emergency_access": payload.get("emergency_access", False),
            "token_type": payload.get("token_type", "access"),
        }

        # For caregivers, get assigned patients
        assigned_patients = None
        if "caregiver" in fhir_roles:
            assigned_patients = payload.get("assigned_patients", [])

        response = TokenValidationResponse(
            valid=True,
            userId=user_id,
            roles=fhir_roles,
            scopes=scopes,
            assignedPatients=assigned_patients,
            attributes=attributes,
        )

        # Log successful validation
        logger.info(f"Token validated for user: {user_id} with roles: {fhir_roles}")

        return response
    except (ValueError, KeyError, AttributeError) as e:
        logger.error("Token validation failed: %s", e, exc_info=True)
        return TokenValidationResponse(valid=False, userId=None, assignedPatients=None)


@router.get("/check-authorization")
async def check_fhir_authorization(
    resource_type: str,
    action: str,
    resource_id: Optional[str] = None,
    authorization: Optional[str] = header_dependency,
) -> Dict[str, Any]:
    """
    Check if a user is authorized to perform an action on a FHIR resource.

    This is an additional endpoint that can be used for fine-grained
    authorization checks.
    """
    # Validate token first
    validation_response = await validate_fhir_token(authorization)

    if not validation_response.valid:
        raise HTTPException(status_code=401, detail="Invalid token")

    # Create authorization context
    context = AuthorizationContext(
        user_id=validation_response.user_id or "",
        roles=[FHIRRole(role) for role in validation_response.roles],
        organization_id=validation_response.attributes.get("organization_id"),
        emergency_access=validation_response.attributes.get("emergency_access", False),
    )

    # Get authorization handler
    auth_handler = get_authorization_handler()

    # Create authorization request
    auth_request = AuthorizationRequest(
        context=context,
        resource_type=resource_type,
        action=ResourcePermission(action.lower()),
        resource_id=resource_id,
    )

    # Check authorization
    decision = auth_handler.check_authorization(auth_request)

    return {
        "allowed": decision.allowed,
        "reasons": decision.reasons,
        "applicable_roles": [role.value for role in decision.applicable_roles],
        "conditions_applied": decision.conditions_applied,
    }
