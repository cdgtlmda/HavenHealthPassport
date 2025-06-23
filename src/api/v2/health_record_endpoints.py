"""Health records management REST API endpoints.

This module provides CRUD operations for health records (observations, conditions,
medications, etc.) in the Haven Health Passport system.
"""

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field, validator
from sqlalchemy.orm import Session

from src.auth.jwt_handler import jwt_handler
from src.auth.permissions import Permission
from src.auth.rbac import AuthorizationContext as ResourceContext
from src.auth.rbac import RBACManager
from src.core.database import get_db
from src.healthcare.fhir_validator import FHIRValidator
from src.models.health_record import RecordType
from src.services.audit_service import AuditService
from src.services.blockchain_factory import get_blockchain_service
from src.services.health_record_service import HealthRecordService
from src.utils.logging import get_logger
from src.utils.pagination import PaginatedResponse

router = APIRouter(prefix="/health-records", tags=["health-records"])
logger = get_logger(__name__)
security = HTTPBearer()

# Dependency injection
db_dependency = Depends(get_db)
security_dependency = Depends(security)
rbac_manager = RBACManager()
fhir_validator = FHIRValidator()


# Request/Response Models
class CodeableConcept(BaseModel):
    """FHIR CodeableConcept model."""

    coding: List[Dict[str, str]] = Field(..., description="Coding system and code")
    text: Optional[str] = Field(None, description="Plain text representation")


class Reference(BaseModel):
    """FHIR Reference model."""

    reference: str = Field(..., description="Resource reference (e.g., Patient/123)")
    display: Optional[str] = Field(None, description="Display text")


class HealthRecordCreateRequest(BaseModel):
    """Health record creation request."""

    resourceType: str = Field(
        ..., description="FHIR resource type (Observation, Condition, etc.)"
    )
    patientId: uuid.UUID = Field(..., description="Patient ID this record belongs to")
    status: str = Field(..., description="Record status")
    code: CodeableConcept = Field(..., description="What is being recorded")
    effectiveDateTime: Optional[datetime] = Field(
        None, description="When the observation was made"
    )
    valueQuantity: Optional[Dict[str, Any]] = Field(
        None, description="Numeric value with unit"
    )
    valueString: Optional[str] = Field(None, description="String value")
    valueBoolean: Optional[bool] = Field(None, description="Boolean value")
    note: Optional[List[Dict[str, str]]] = Field(None, description="Additional notes")
    category: Optional[List[CodeableConcept]] = Field(
        None, description="Classification of type"
    )

    @validator("resourceType")
    def validate_resource_type(cls, v: str) -> str:  # pylint: disable=no-self-argument
        """Validate FHIR resource type."""
        allowed_types = [
            "Observation",
            "Condition",
            "MedicationRequest",
            "Immunization",
            "Procedure",
            "AllergyIntolerance",
        ]
        if v not in allowed_types:
            raise ValueError(f"Resource type must be one of: {allowed_types}")
        return v


class HealthRecordUpdateRequest(BaseModel):
    """Health record update request."""

    status: Optional[str] = None
    valueQuantity: Optional[Dict[str, Any]] = None
    valueString: Optional[str] = None
    valueBoolean: Optional[bool] = None
    note: Optional[List[Dict[str, str]]] = None


class HealthRecordResponse(BaseModel):
    """Health record response model."""

    id: uuid.UUID
    resourceType: str
    patientId: uuid.UUID
    status: str
    code: CodeableConcept
    effectiveDateTime: Optional[datetime]
    valueQuantity: Optional[Dict[str, Any]]
    valueString: Optional[str]
    valueBoolean: Optional[bool]
    note: Optional[List[Dict[str, str]]]
    category: Optional[List[CodeableConcept]]
    createdAt: datetime
    updatedAt: datetime
    createdBy: str
    version: int
    verificationStatus: str = Field(default="unverified")
    blockchainHash: Optional[str] = None
    isEncrypted: bool = Field(default=True)


# Helper functions
async def get_current_user(
    credentials: HTTPAuthorizationCredentials = security_dependency,
    db: Session = db_dependency,
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
        logger.error(f"Token validation failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
        ) from e


async def check_health_record_permission(
    user: Dict[str, Any],
    permission: Permission,
    patient_id: uuid.UUID,
    record_id: Optional[uuid.UUID] = None,
    db: Optional[Session] = None,
) -> bool:
    """Check if user has permission for health record operations."""
    # Create context for permission check
    roles: List[Any] = []  # Convert user roles to RoleAssignment objects
    context = ResourceContext(
        user_id=user["user_id"],
        roles=roles,
        attributes={
            "resource_type": "HealthRecord",
            "resource_id": str(record_id) if record_id else None,
            "patient_id": str(patient_id),
            "organization_id": user.get("organization"),
            "user_role": user.get("role"),
        },
    )

    if not rbac_manager.check_permission(context=context, permission=permission):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions for this operation",
        )
    return True


# GET /health-records - List health records
@router.get(
    "/",
    response_model=PaginatedResponse[HealthRecordResponse],
    summary="List health records",
    description="Retrieve paginated health records with filtering",
)
async def list_health_records(
    current_user: Dict[str, Any] = Depends(get_current_user),  # noqa: B008
    db: Session = db_dependency,
    patient_id: Optional[uuid.UUID] = Query(
        None, description="Filter by patient ID"
    ),  # noqa: B008
    resource_type: Optional[str] = Query(  # noqa: B008
        None, description="Filter by FHIR resource type"
    ),
    record_status: Optional[str] = Query(
        None, description="Filter by status"
    ),  # noqa: B008
    page: int = Query(1, ge=1, description="Page number"),  # noqa: B008
    page_size: int = Query(
        20, ge=1, le=100, description="Items per page"
    ),  # noqa: B008
    start_date: Optional[datetime] = Query(
        None, description="Filter by start date"
    ),  # noqa: B008
    end_date: Optional[datetime] = Query(
        None, description="Filter by end date"
    ),  # noqa: B008
) -> PaginatedResponse[HealthRecordResponse]:
    """List health records with pagination and filtering."""
    try:
        service = HealthRecordService(db)
        audit_service = AuditService(db)

        # Build filters
        filters: Dict[str, Any] = {}
        if patient_id:
            # Check permission for specific patient
            await check_health_record_permission(
                current_user,
                Permission.READ_HEALTH_RECORD,
                patient_id=patient_id,
                db=db,
            )
            filters["patient_id"] = patient_id
        if resource_type:
            filters["resource_type"] = resource_type
        if record_status:
            filters["status"] = record_status
        if start_date:
            filters["start_date"] = start_date
        if end_date:
            filters["end_date"] = end_date

        # Get paginated results using search_records
        records, total = service.search_records(
            filters=filters, limit=page_size, offset=(page - 1) * page_size
        )

        # Audit log
        await audit_service.log_event(
            event_type="LIST_HEALTH_RECORDS",
            user_id=current_user["user_id"],
            details={
                "resource_type": "HealthRecord",
                "filters": filters,
                "count": len(records),
            },
        )

        return PaginatedResponse.create(
            items=records, total=total, page=page, page_size=page_size  # type: ignore[arg-type]
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing health records: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve health records",
        ) from e


# GET /health-records/{id} - Get health record by ID
@router.get(
    "/{record_id}",
    response_model=HealthRecordResponse,
    summary="Get health record by ID",
    description="Retrieve specific health record by ID",
)
async def get_health_record(
    record_id: uuid.UUID,
    current_user: Dict[str, Any] = Depends(get_current_user),  # noqa: B008
    db: Session = db_dependency,
) -> HealthRecordResponse:
    """Get health record by ID."""
    try:
        service = HealthRecordService(db)
        audit_service = AuditService(db)

        # Get record to check patient ID
        record = service.get_by_id(record_id)

        if not record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Health record with ID {record_id} not found",
            )

        # Check permission
        await check_health_record_permission(
            current_user,
            Permission.READ_HEALTH_RECORD,
            patient_id=uuid.UUID(str(record.patient_id)),
            record_id=record_id,
            db=db,
        )

        # Audit log
        await audit_service.log_event(
            event_type="READ_HEALTH_RECORD",
            user_id=current_user["user_id"],
            details={
                "resource_type": "HealthRecord",
                "resource_id": str(record_id),
                "record_id": str(record_id),
            },
        )

        return record

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving health record {record_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve health record",
        ) from e


# POST /health-records - Create health record
@router.post(
    "/",
    response_model=HealthRecordResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create health record",
)
async def create_health_record(
    request: HealthRecordCreateRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),  # noqa: B008
    db: Session = Depends(get_db),  # noqa: B008
) -> HealthRecordResponse:
    """Create a new health record with blockchain verification."""
    try:
        # Initialize services
        health_service = HealthRecordService(db)
        audit_service = AuditService(db)
        blockchain_service = get_blockchain_service()

        # Check permission
        await check_health_record_permission(
            current_user,
            Permission.CREATE_HEALTH_RECORD,
            patient_id=request.patientId,
            db=db,
        )

        # Validate FHIR compliance
        fhir_data = request.dict()
        fhir_validator.validate_resource(request.resourceType, fhir_data)

        # Create health record
        record = health_service.create_health_record(
            patient_id=request.patientId,
            record_type=RecordType(request.resourceType.lower().replace(" ", "_")),
            title=f"{request.resourceType}: {request.code.text or 'Untitled'}",
            content=fhir_data,
            provider_id=current_user["user_id"],
            provider_name=current_user.get("name", "Unknown Provider"),
        )

        # Create blockchain verification hash
        try:
            verification_hash = blockchain_service.create_record_hash(  # type: ignore[attr-defined]
                {
                    "record_id": str(record.id),
                    "patient_id": str(request.patientId),
                    "record_type": request.resourceType,
                    "created_at": datetime.utcnow().isoformat(),
                    "provider_id": current_user["user_id"],
                }
            )

            # Update record with blockchain hash
            record.blockchainHash = verification_hash
            db.commit()

        except Exception as e:
            logger.warning(f"Blockchain verification failed: {e}")
            # Continue without blockchain verification

        # Audit log
        await audit_service.log_event(
            event_type="CREATE_HEALTH_RECORD",
            user_id=current_user["user_id"],
            details={
                "action": "CREATE_HEALTH_RECORD",
                "resource_type": "HealthRecord",
                "resource_id": str(record.id),
                "record_id": str(record.id),
                "patient_id": str(request.patientId),
                "record_type": request.resourceType,
            },
        )

        return record

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating health record: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create health record",
        ) from e


# PUT /health-records/{id} - Update health record
@router.put(
    "/{record_id}",
    response_model=HealthRecordResponse,
    summary="Update health record",
)
async def update_health_record(
    record_id: uuid.UUID,
    request: HealthRecordUpdateRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),  # noqa: B008
    db: Session = Depends(get_db),  # noqa: B008
) -> HealthRecordResponse:
    """Update an existing health record."""
    try:
        # Initialize services
        health_service = HealthRecordService(db)
        audit_service = AuditService(db)
        blockchain_service = get_blockchain_service()

        # Get existing record
        record = health_service.get_by_id(record_id)
        if not record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Health record not found",
            )

        # Check permission
        await check_health_record_permission(
            current_user,
            Permission.UPDATE_HEALTH_RECORD,
            patient_id=uuid.UUID(str(record.patient_id)),
            record_id=record_id,
            db=db,
        )

        # Update fields
        update_data = request.dict(exclude_unset=True)
        if update_data:
            for field, value in update_data.items():
                if hasattr(record, field):
                    setattr(record, field, value)

            # Update version
            record.version = record.version + 1  # type: ignore[assignment]
            record.updatedAt = datetime.utcnow()

            # Create new blockchain hash for updated record
            try:
                verification_hash = blockchain_service.create_record_hash(  # type: ignore[attr-defined]
                    {
                        "record_id": str(record.id),
                        "patient_id": str(record.patient_id),
                        "version": record.version,
                        "updated_at": datetime.utcnow().isoformat(),
                        "updater_id": current_user["user_id"],
                    }
                )
                record.blockchainHash = verification_hash
            except Exception as e:
                logger.warning(f"Blockchain update failed: {e}")

            db.commit()

        # Audit log
        await audit_service.log_event(
            event_type="UPDATE_HEALTH_RECORD",
            user_id=current_user["user_id"],
            details={
                "resource_type": "HealthRecord",
                "resource_id": str(record_id),
                "record_id": str(record_id),
                "updated_fields": list(update_data.keys()),
                "version": record.version,
            },
        )

        return record

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating health record {record_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update health record",
        )


# DELETE /health-records/{id} - Delete health record
@router.delete(
    "/{record_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete health record",
)
async def delete_health_record(
    record_id: uuid.UUID,
    current_user: Dict[str, Any] = Depends(get_current_user),  # noqa: B008
    db: Session = Depends(get_db),  # noqa: B008
) -> None:
    """Soft delete a health record."""
    try:
        # Initialize services
        health_service = HealthRecordService(db)
        audit_service = AuditService(db)

        # Get record
        record = health_service.get_by_id(record_id)
        if not record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Health record not found",
            )

        # Check permission
        await check_health_record_permission(
            current_user,
            Permission.DELETE_HEALTH_RECORD,
            patient_id=uuid.UUID(str(record.patient_id)),
            record_id=record_id,
            db=db,
        )

        # Soft delete
        health_service.delete(record_id)

        # Audit log
        await audit_service.log_event(
            event_type="DELETE_HEALTH_RECORD",
            user_id=current_user["user_id"],
            details={
                "resource_type": "HealthRecord",
                "resource_id": str(record_id),
                "record_id": str(record_id),
                "patient_id": str(record.patient_id),
            },
        )

        return None

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting health record {record_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete health record",
        )
