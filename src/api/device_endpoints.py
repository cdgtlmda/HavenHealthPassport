"""Device management REST API endpoints.

This module provides endpoints for device tracking, trust management,
and device-related security operations.
"""

import uuid
from datetime import datetime
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.api.auth_endpoints import get_current_user
from src.core.database import get_db
from src.models.auth import UserAuth
from src.services.device_tracking_service import DeviceTrackingService
from src.utils.logging import get_logger

router = APIRouter(prefix="/auth/devices", tags=["devices"])
logger = get_logger(__name__)

# Module-level dependency variables to avoid B008 errors
db_dependency = Depends(get_db)
current_user_dependency = Depends(get_current_user)


# Request/Response Models
class DeviceInfoResponse(BaseModel):
    """Device information response."""

    id: uuid.UUID
    device_name: str
    device_type: str
    platform: str
    browser: str
    is_trusted: bool
    trust_expires_at: Optional[datetime]
    first_seen_at: datetime
    last_seen_at: datetime
    login_count: int
    is_current: bool = False


class DeviceListResponse(BaseModel):
    """Device list response."""

    devices: List[DeviceInfoResponse]
    total: int
    trusted_count: int


class TrustDeviceRequest(BaseModel):
    """Trust device request."""

    duration_days: Optional[int] = Field(None, ge=1, le=365)


class DeviceFingerprintRequest(BaseModel):
    """Device fingerprint request."""

    screen_resolution: Optional[str] = None
    timezone: Optional[str] = None
    canvas_fingerprint: Optional[str] = None
    webgl_vendor: Optional[str] = None
    plugins: Optional[List[str]] = None


@router.get("/", response_model=DeviceListResponse)
async def list_devices(
    request: Request,
    include_inactive: bool = False,
    current_user: UserAuth = current_user_dependency,
    db: Session = db_dependency,
) -> DeviceListResponse:
    """List all devices for the current user."""
    try:
        device_service = DeviceTrackingService(db)

        # Get all user devices
        devices = device_service.get_user_devices(current_user, include_inactive)

        # Get current device fingerprint if available
        current_fingerprint = None
        if "X-Device-Fingerprint" in request.headers:
            current_fingerprint = request.headers["X-Device-Fingerprint"]

        # Format response
        device_responses = []
        trusted_count = 0

        for device in devices:
            if device.is_trusted:
                trusted_count += 1

            device_response = DeviceInfoResponse(
                id=device.id,
                device_name=str(device.device_name),
                device_type=str(device.device_type),
                platform=str(device.platform),
                browser=str(device.browser),
                is_trusted=bool(device.is_trusted),
                trust_expires_at=device.trust_expires_at,  # type: ignore[arg-type]
                first_seen_at=device.first_seen_at,  # type: ignore[arg-type]
                last_seen_at=device.last_seen_at,  # type: ignore[arg-type]
                login_count=int(device.login_count),
                is_current=bool(device.device_fingerprint == current_fingerprint),
            )
            device_responses.append(device_response)
        return DeviceListResponse(
            devices=device_responses, total=len(devices), trusted_count=trusted_count
        )

    except Exception as e:
        logger.error(f"List devices error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve devices",
        ) from e


@router.post("/{device_id}/trust", response_model=Dict[str, str])
async def trust_device(
    device_id: uuid.UUID,
    request: TrustDeviceRequest,
    current_user: UserAuth = current_user_dependency,
    db: Session = db_dependency,
) -> Dict[str, str]:
    """Mark a device as trusted."""
    try:
        device_service = DeviceTrackingService(db)

        success = device_service.trust_device(
            current_user, str(device_id), request.duration_days
        )

        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to trust device. Check device limits.",
            )

        logger.info(f"Device {device_id} trusted by user {current_user.id}")

        return {"message": "Device trusted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Trust device error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to trust device",
        ) from e


@router.post("/{device_id}/revoke-trust", response_model=Dict[str, str])
async def revoke_device_trust(
    device_id: uuid.UUID,
    current_user: UserAuth = current_user_dependency,
    db: Session = db_dependency,
) -> Dict[str, str]:
    """Revoke trust for a device."""
    try:
        device_service = DeviceTrackingService(db)

        success = device_service.revoke_device_trust(current_user, str(device_id))

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Device not found"
            )

        logger.info(f"Device trust revoked for {device_id} by user {current_user.id}")

        return {"message": "Device trust revoked successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Revoke device trust error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to revoke device trust",
        ) from e


@router.delete("/{device_id}", response_model=Dict[str, str])
async def delete_device(
    device_id: uuid.UUID,
    current_user: UserAuth = current_user_dependency,
    db: Session = db_dependency,
) -> Dict[str, str]:
    """Delete a device."""
    try:
        device_service = DeviceTrackingService(db)

        success = device_service.delete_device(current_user, str(device_id))
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot delete device. It may be active or not found.",
            )

        logger.info(f"Device {device_id} deleted by user {current_user.id}")

        return {"message": "Device deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Delete device error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete device",
        ) from e


@router.post("/fingerprint", response_model=Dict[str, str])
async def generate_fingerprint(
    fingerprint_data: DeviceFingerprintRequest,
    request: Request,
    db: Session = db_dependency,
) -> Dict[str, str]:
    """Generate a device fingerprint from client data."""
    try:
        device_service = DeviceTrackingService(db)

        client_data = {
            "screen_resolution": fingerprint_data.screen_resolution,
            "timezone": fingerprint_data.timezone,
            "canvas_fingerprint": fingerprint_data.canvas_fingerprint,
            "webgl_vendor": fingerprint_data.webgl_vendor,
            "plugins": fingerprint_data.plugins,
        }

        fingerprint = device_service.generate_device_fingerprint(
            dict(request.headers), client_data
        )

        return {"fingerprint": fingerprint}

    except Exception as e:
        logger.error(f"Generate fingerprint error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate fingerprint",
        ) from e
