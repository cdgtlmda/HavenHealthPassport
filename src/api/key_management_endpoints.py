"""Key Management REST API endpoints.

This module provides administrative endpoints for JWT key rotation
and key management operations.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.auth.jwt_handler import jwt_handler
from src.auth.key_rotation import KeyRotationManager
from src.auth.permissions import require_admin
from src.core.database import get_db
from src.utils.logging import get_logger

router = APIRouter(prefix="/admin/keys", tags=["admin", "key-management"])
logger = get_logger(__name__)

# Dependency injection
db_dependency = Depends(get_db)
admin_dependency = Depends(require_admin)


# Response models
class KeyInfo(BaseModel):
    """Key information model."""

    kid: str
    created_at: str
    expires_at: str
    algorithm: str
    is_current: bool
    is_expired: bool


class KeyRotationStatus(BaseModel):
    """Key rotation status model."""

    current_key: KeyInfo
    previous_keys: List[KeyInfo]
    rotation_needed: bool
    last_rotation: str
    next_rotation: str


class RotateKeysResponse(BaseModel):
    """Key rotation response model."""

    success: bool
    message: str
    old_kid: str
    new_kid: str


@router.get(
    "/status",
    response_model=KeyRotationStatus,
    summary="Get key rotation status",
    dependencies=[admin_dependency],
)
async def get_key_rotation_status(db: Session = db_dependency) -> KeyRotationStatus:
    """Get current key rotation status."""
    try:
        key_manager = KeyRotationManager(db)

        # Get current key info
        current = key_manager.keys["current"]
        current_info = KeyInfo(
            kid=current["kid"],
            created_at=current["created_at"],
            expires_at=current["expires_at"],
            algorithm=current["algorithm"],
            is_current=True,
            is_expired=False,
        )

        # Get previous keys info
        now = datetime.now(timezone.utc)

        previous_keys = []
        for key in key_manager.keys["previous"]:
            expires_at = datetime.fromisoformat(key["expires_at"])
            previous_keys.append(
                KeyInfo(
                    kid=key["kid"],
                    created_at=key["created_at"],
                    expires_at=key["expires_at"],
                    algorithm=key["algorithm"],
                    is_current=False,
                    is_expired=expires_at <= now,
                )
            )

        # Calculate next rotation date
        created_at = datetime.fromisoformat(current["created_at"])
        next_rotation = created_at + timedelta(days=key_manager.rotation_interval_days)

        # Get last rotation from history
        last_rotation = "Never"
        if key_manager.keys["rotation_history"]:
            last_rotation = key_manager.keys["rotation_history"][-1]["rotated_at"]

        return KeyRotationStatus(
            current_key=current_info,
            previous_keys=previous_keys,
            rotation_needed=key_manager.check_rotation_needed(),
            last_rotation=last_rotation,
            next_rotation=next_rotation.isoformat(),
        )

    except Exception as e:
        logger.error(f"Error getting key rotation status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get key rotation status",
        ) from e


@router.post(
    "/rotate",
    response_model=RotateKeysResponse,
    summary="Rotate JWT signing keys",
    dependencies=[admin_dependency],
)
async def rotate_keys(
    force: bool = False, db: Session = db_dependency
) -> RotateKeysResponse:
    """Manually trigger key rotation."""
    try:
        key_manager = KeyRotationManager(db)

        # Get old key ID
        old_kid = key_manager.keys["current"]["kid"]

        # Perform rotation
        rotated = key_manager.rotate_keys(force=force)

        if not rotated:
            return RotateKeysResponse(
                success=False,
                message="Key rotation not needed yet. Use force=true to override.",
                old_kid=old_kid,
                new_kid=old_kid,
            )

        # Get new key ID
        new_kid = key_manager.keys["current"]["kid"]

        # Update JWT handler to use new keys
        jwt_handler.key_manager = key_manager

        logger.info(f"Keys rotated successfully: {old_kid} -> {new_kid}")

        return RotateKeysResponse(
            success=True,
            message="Keys rotated successfully",
            old_kid=old_kid,
            new_kid=new_kid,
        )

    except Exception as e:
        logger.error(f"Error rotating keys: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to rotate keys: {str(e)}",
        ) from e


@router.get(
    "/history",
    response_model=List[Dict],
    summary="Get key rotation history",
    dependencies=[admin_dependency],
)
async def get_rotation_history(
    limit: int = 20, db: Session = db_dependency
) -> List[Dict]:
    """Get key rotation history."""
    try:
        key_manager = KeyRotationManager(db)

        # Get rotation history
        history = key_manager.keys["rotation_history"]

        # Return most recent entries
        result: list[dict[Any, Any]] = (
            history[-limit:] if len(history) > limit else history
        )
        return result

    except Exception as e:
        logger.error(f"Error getting rotation history: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get rotation history",
        ) from e


# Export router
__all__ = ["router"]
