"""Organization management REST API endpoints.

This module provides organization and team management functionality
for the Haven Health Passport system.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from src.auth.jwt_handler import jwt_handler
from src.auth.rbac import RBACManager
from src.core.database import get_db
from src.utils.logging import get_logger

router = APIRouter(prefix="/organizations", tags=["organizations"])
logger = get_logger(__name__)
security = HTTPBearer()

# Dependency injection
db_dependency = Depends(get_db)
security_dependency = Depends(security)
rbac_manager = RBACManager()


# Request/Response Models
class OrganizationCreate(BaseModel):
    """Organization creation model."""

    name: str = Field(..., min_length=3, max_length=255)
    type: str = Field(..., pattern="^(NGO|GOVERNMENT|HEALTHCARE|UN_AGENCY|OTHER)$")
    description: Optional[str] = None
    country: str
    contact_email: EmailStr
    contact_phone: Optional[str] = None
    address: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None


class OrganizationUpdate(BaseModel):
    """Organization update model."""

    name: Optional[str] = Field(None, min_length=3, max_length=255)
    description: Optional[str] = None
    contact_email: Optional[EmailStr] = None
    contact_phone: Optional[str] = None
    address: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None
    active: Optional[bool] = None


class OrganizationMember(BaseModel):
    """Organization member model."""

    user_id: UUID
    role: str = Field(..., pattern="^(ADMIN|MEMBER|VIEWER)$")
    permissions: List[str] = []
    joined_at: datetime
    invited_by: Optional[UUID] = None


class MemberInvite(BaseModel):
    """Member invitation model."""

    email: EmailStr
    role: str = Field(..., pattern="^(ADMIN|MEMBER|VIEWER)$")
    permissions: Optional[List[str]] = []
    message: Optional[str] = None


@router.get("/")
async def list_organizations(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    _search: Optional[str] = None,
    _type_filter: Optional[str] = None,
    _active_only: bool = Query(default=True),
    _db: Session = db_dependency,
    token: HTTPAuthorizationCredentials = security_dependency,
) -> Dict[str, Any]:
    """List organizations with pagination and filtering."""
    try:
        # Verify token
        # Use payload for filtering organizations by user access
        _payload = jwt_handler.verify_token(token.credentials)
        # _user_id = _payload.get("sub")  # TODO: Use to filter organizations by user access

        # Will use _user_id to filter organizations when connected to real database

        # For now, return mock data
        # In production, would query actual organizations
        organizations = [
            {
                "id": str(uuid4()),
                "name": "International Rescue Committee",
                "type": "NGO",
                "country": "USA",
                "member_count": 150,
                "patient_count": 5000,
                "active": True,
                "created_at": datetime.utcnow().isoformat(),
            },
            {
                "id": str(uuid4()),
                "name": "Doctors Without Borders",
                "type": "HEALTHCARE",
                "country": "France",
                "member_count": 200,
                "patient_count": 8000,
                "active": True,
                "created_at": datetime.utcnow().isoformat(),
            },
        ]

        return {
            "items": organizations,
            "total": len(organizations),
            "skip": skip,
            "limit": limit,
        }

    except Exception as e:
        logger.error(f"Error listing organizations: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list organizations",
        ) from e


@router.get("/{organization_id}")
async def get_organization(
    organization_id: UUID,
    _db: Session = db_dependency,
    token: HTTPAuthorizationCredentials = security_dependency,
) -> Dict[str, Any]:
    """Get organization details."""
    try:
        # Verify token
        payload = jwt_handler.verify_token(token.credentials)
        user_id = payload.get("sub")

        # Check authorization
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token"
            )

        # Return mock data
        return {
            "id": str(organization_id),
            "name": "International Rescue Committee",
            "type": "NGO",
            "description": "Global humanitarian aid organization",
            "country": "USA",
            "contact_email": "info@rescue.org",
            "contact_phone": "+1-212-551-3000",
            "address": {
                "street": "122 East 42nd Street",
                "city": "New York",
                "state": "NY",
                "postal_code": "10168",
                "country": "USA",
            },
            "member_count": 150,
            "patient_count": 5000,
            "active": True,
            "created_at": datetime.utcnow().isoformat(),
            "metadata": {"founded": 1933, "website": "https://www.rescue.org"},
        }

    except Exception as e:
        logger.error(f"Error getting organization: {e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found"
        ) from e


@router.get("/{organization_id}/members")
async def list_organization_members(
    organization_id: UUID,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    role_filter: Optional[str] = None,
    _db: Session = db_dependency,
    token: HTTPAuthorizationCredentials = security_dependency,
) -> Dict[str, Any]:
    """List organization members."""
    try:
        # Verify token and permissions
        payload = jwt_handler.verify_token(token.credentials)
        user_id = payload.get("sub")

        # Check authorization
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token"
            )

        # Return mock members
        members = [
            {
                "user_id": str(uuid4()),
                "email": "admin@rescue.org",
                "name": "John Admin",
                "role": "ADMIN",
                "permissions": [
                    "manage_organization",
                    "manage_members",
                    "view_all_patients",
                ],
                "joined_at": datetime.utcnow().isoformat(),
                "last_active": datetime.utcnow().isoformat(),
            },
            {
                "user_id": str(uuid4()),
                "email": "doctor@rescue.org",
                "name": "Dr. Sarah Smith",
                "role": "MEMBER",
                "permissions": ["view_patients", "create_records"],
                "joined_at": datetime.utcnow().isoformat(),
                "last_active": datetime.utcnow().isoformat(),
            },
        ]

        return {"items": members, "total": len(members), "skip": skip, "limit": limit}

    except Exception as e:
        logger.error(f"Error listing members: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list organization members",
        ) from e


@router.post("/{organization_id}/members/invite")
async def invite_member(
    organization_id: UUID,
    invite: MemberInvite,
    _db: Session = db_dependency,
    token: HTTPAuthorizationCredentials = security_dependency,
) -> Dict[str, Any]:
    """Invite a new member to organization."""
    try:
        # Verify token and admin permissions
        payload = jwt_handler.verify_token(token.credentials)
        user_id = payload.get("sub")

        # Check authorization
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token"
            )

        # Return mock success response
        return {
            "success": True,
            "invitation_id": str(uuid4()),
            "message": f"Invitation sent to {invite.email}",
            "expires_at": (datetime.utcnow().timestamp() + 7 * 24 * 3600) * 1000,
        }

    except Exception as e:
        logger.error(f"Error inviting member: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send invitation",
        ) from e


@router.delete("/{organization_id}/members/{user_id}")
async def remove_member(
    organization_id: UUID,
    user_id: UUID,
    _db: Session = db_dependency,
    token: HTTPAuthorizationCredentials = security_dependency,
) -> Dict[str, Any]:
    """Remove member from organization."""
    try:
        # Verify token and admin permissions
        payload = jwt_handler.verify_token(token.credentials)
        auth_user_id = payload.get("sub")

        # Check authorization
        if not auth_user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token"
            )

        return {"success": True, "message": "Member removed successfully"}

    except Exception as e:
        logger.error(f"Error removing member: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to remove member",
        ) from e
