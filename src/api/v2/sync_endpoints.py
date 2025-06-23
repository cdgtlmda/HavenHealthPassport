"""Sync API endpoints for offline data synchronization.

This module provides endpoints for syncing offline data between mobile devices
and the server, handling conflicts and ensuring data consistency.
"""

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.auth.jwt_handler import jwt_handler
from src.auth.permissions import Permission
from src.auth.rbac import AuthorizationContext, RBACManager
from src.core.database import get_db
from src.services.audit_service import AuditService
from src.sync.sync_service import (
    ConflictResolution,
    SyncDirection,
    SyncService,
    SyncStatus,
)
from src.utils.logging import get_logger

router = APIRouter(prefix="/sync", tags=["sync"])
logger = get_logger(__name__)
security = HTTPBearer()

# Dependency injection
db_dependency = Depends(get_db)
security_dependency = Depends(security)
rbac_manager = RBACManager()


# Request/Response Models
class SyncRequest(BaseModel):
    """Sync request model."""

    device_id: str = Field(..., description="Unique device identifier")
    last_sync_timestamp: Optional[datetime] = Field(
        None, description="Last successful sync time"
    )
    local_changes: List[Dict[str, Any]] = Field(
        default_factory=list, description="Local changes to sync"
    )
    sync_direction: SyncDirection = Field(
        SyncDirection.BIDIRECTIONAL, description="Sync direction"
    )
    conflict_resolution: ConflictResolution = Field(
        ConflictResolution.LAST_WRITE_WINS, description="Conflict resolution strategy"
    )


class SyncResponse(BaseModel):
    """Sync response model."""

    sync_id: str = Field(..., description="Unique sync operation ID")
    status: SyncStatus = Field(..., description="Sync operation status")
    server_changes: List[Dict[str, Any]] = Field(
        default_factory=list, description="Changes from server"
    )
    conflicts: List[Dict[str, Any]] = Field(
        default_factory=list, description="Conflicts requiring resolution"
    )
    next_sync_token: Optional[str] = Field(
        None, description="Token for next sync operation"
    )
    sync_timestamp: datetime = Field(..., description="Server timestamp for this sync")


class ConflictResolutionRequest(BaseModel):
    """Conflict resolution request."""

    sync_id: str = Field(..., description="Sync operation ID")
    conflict_id: str = Field(..., description="Conflict identifier")
    resolution: str = Field(..., description="Resolution choice: 'local' or 'server'")
    merged_data: Optional[Dict[str, Any]] = Field(
        None, description="Manually merged data if applicable"
    )


# Helper functions
async def get_current_user(
    credentials: HTTPAuthorizationCredentials = security_dependency,
) -> Dict[str, Any]:
    """Get current authenticated user."""
    try:
        payload = jwt_handler.decode_token(credentials.credentials)
        return payload
    except Exception as e:
        logger.error(f"Authentication error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
        ) from e


# POST /sync - Initiate sync operation
@router.post(
    "/",
    response_model=SyncResponse,
    summary="Initiate data synchronization",
)
async def sync_data(
    request: SyncRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),  # noqa: B008
    db: Session = Depends(get_db),  # noqa: B008
) -> SyncResponse:
    """Synchronize offline data with server."""
    try:
        # Initialize services
        from src.sync.sync_service import SyncService

        sync_service = SyncService(db)
        audit_service = AuditService(db)

        # Check permission
        context = AuthorizationContext(
            user_id=current_user["user_id"],
            roles=[],  # In a real implementation, would fetch user's roles
        )

        if not rbac_manager.check_permission(
            context=context,
            permission=Permission.BULK_OPERATIONS,  # Using bulk operations permission for sync
            resource_type="sync",
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions to sync data",
            )

        # Start sync operation
        sync_id = str(uuid.uuid4())

        # Process local changes
        processed_changes = []
        conflicts = []

        for change in request.local_changes:
            try:
                # Process the change using sync service
                result = sync_service.process_change(change)

                if result.get("conflict"):
                    conflicts.append(result)
                else:
                    processed_changes.append(result)

            except Exception as e:
                logger.error(f"Error processing change: {e}")
                conflicts.append(
                    {
                        "conflict_id": str(uuid.uuid4()),
                        "resource_id": change.get("resource_id"),
                        "error": str(e),
                        "local_data": change,
                    }
                )

        # Get server changes since last sync
        server_changes = []
        if request.sync_direction in [
            SyncDirection.DOWNLOAD,
            SyncDirection.BIDIRECTIONAL,
        ]:
            # Get server changes using sync service
            server_changes = sync_service.get_changes_since(
                device_id=request.device_id,
                last_sync_token=(
                    str(request.last_sync_timestamp)
                    if request.last_sync_timestamp
                    else ""
                ),
                limit=100,
            )

        # Generate next sync token
        next_sync_token = jwt_handler.create_access_token(
            data={
                "user_id": current_user["user_id"],
                "device_id": request.device_id,
                "sync_id": sync_id,
            }
        )

        # Audit log
        await audit_service.log_event(
            event_type="SYNC_DATA",
            user_id=current_user["user_id"],
            details={
                "resource_type": "Sync",
                "resource_id": sync_id,
                "device_id": request.device_id,
                "local_changes_count": len(request.local_changes),
                "server_changes_count": len(server_changes),
                "conflicts_count": len(conflicts),
            },
        )

        return SyncResponse(
            sync_id=sync_id,
            status=SyncStatus.COMPLETED if not conflicts else SyncStatus.CONFLICT,
            server_changes=server_changes,
            conflicts=conflicts,
            next_sync_token=next_sync_token,
            sync_timestamp=datetime.utcnow(),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Sync operation failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Sync operation failed",
        ) from e


# POST /sync/resolve-conflict - Resolve sync conflicts
@router.post(
    "/resolve-conflict",
    summary="Resolve synchronization conflicts",
)
async def resolve_conflict(
    request: ConflictResolutionRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),  # noqa: B008
    db: Session = Depends(get_db),  # noqa: B008
) -> Dict[str, Any]:
    """Resolve conflicts from sync operation."""
    try:
        # Initialize services
        from src.sync.sync_service import ConflictResolution, SyncService

        sync_service = SyncService(db)
        audit_service = AuditService(db)

        # Resolve the conflict
        resolution_strategy = ConflictResolution[request.resolution.upper()]

        # Find the sync queue entry
        from src.sync.sync_service import SyncQueue

        sync_entry = (
            db.query(SyncQueue).filter(SyncQueue.sync_id == request.sync_id).first()
        )

        if sync_entry and sync_entry.conflict_data:
            # Resolve the conflict
            resolved_data = sync_service.resolve_conflict(
                sync_entry=sync_entry,
                local_record=sync_entry.data_payload,
                server_record=sync_entry.conflict_data.get("server_data", {}),
                resolution=resolution_strategy,
            )

            # Update the sync entry
            sync_entry.has_conflict = False
            sync_entry.conflict_data = None
            sync_entry.data_payload = (
                request.merged_data if request.merged_data else resolved_data
            )
            sync_entry.status = "resolved"
            db.commit()

            result = {
                "resolved": True,
                "sync_id": request.sync_id,
                "conflict_id": request.conflict_id,
                "resolution": request.resolution,
                "merged_data": resolved_data,
            }
        else:
            result = {
                "resolved": False,
                "sync_id": request.sync_id,
                "conflict_id": request.conflict_id,
                "resolution": request.resolution,
                "error": "Sync entry not found or no conflict data",
            }

        # Audit log
        await audit_service.log_event(
            event_type="RESOLVE_SYNC_CONFLICT",
            user_id=current_user["user_id"],
            details={
                "resource_type": "Sync",
                "resource_id": request.sync_id,
                "conflict_id": request.conflict_id,
                "resolution": request.resolution,
            },
        )

        return {"success": True, "result": result}

    except Exception as e:
        logger.error(f"Conflict resolution failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to resolve conflict",
        ) from e


# GET /sync/status/{device_id} - Get sync status
@router.get(
    "/status/{device_id}",
    summary="Get device sync status",
)
async def get_sync_status(
    device_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),  # noqa: B008
    db: Session = Depends(get_db),  # noqa: B008
) -> Dict[str, Any]:
    """Get synchronization status for a device."""
    try:
        # Initialize sync service
        sync_service = SyncService(db)

        # Get device sync status
        sync_status = sync_service.get_device_sync_status(
            device_id=device_id, user_id=current_user.get("user_id")
        )

        return sync_status

    except Exception as e:
        logger.error(f"Failed to get sync status: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve sync status",
        ) from e
