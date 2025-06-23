"""Patient management REST API endpoints.

This module provides CRUD operations for patient health records in the
Haven Health Passport system, with proper FHIR compliance and security.
All patient data is encrypted for PHI protection and HIPAA compliance.

Data retention: Patient records are retained according to HIPAA requirements.
Records are automatically archived after the retention period and permanently
deleted after the required legal hold period. All data operations are logged.
"""

import csv
import io
import json
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field, validator
from sqlalchemy.orm import Session

from src.auth.jwt_handler import jwt_handler
from src.auth.permissions import Permission
from src.auth.rbac import AuthorizationContext as ResourceContext
from src.auth.rbac import RBACManager
from src.auth.scope_validation import (
    require_patient_admin,
    require_patient_read,
    require_patient_write,
)
from src.core.database import get_db
from src.healthcare.fhir_validator import FHIRValidator

# Data retention compliance
from src.healthcare.regulatory.right_to_deletion_config import (
    DataCategory,
    RightToDeletionConfiguration,
)
from src.models.patient import Gender
from src.services.audit_service import AuditService
from src.services.patient_service import PatientService
from src.utils.logging import get_logger
from src.utils.pagination import PaginatedResponse

router = APIRouter(prefix="/patients", tags=["patients"])
logger = get_logger(__name__)
security = HTTPBearer()

# Dependency injection
db_dependency = Depends(get_db)
security_dependency = Depends(security)
rbac_manager = RBACManager()
fhir_validator = FHIRValidator()


# Request/Response Models
class PatientIdentifier(BaseModel):
    """Patient identifier model."""

    system: str = Field(..., description="Identifier system (e.g., UNHCR, national ID)")
    value: str = Field(..., description="Identifier value")
    type: Optional[str] = Field(None, description="Identifier type")


class PatientName(BaseModel):
    """Patient name model."""

    given: List[str] = Field(..., description="Given names")
    family: str = Field(..., description="Family name")
    prefix: Optional[List[str]] = None
    suffix: Optional[List[str]] = None
    use: str = Field(
        default="official", description="Name use (official, nickname, etc.)"
    )


class PatientContact(BaseModel):
    """Patient contact information."""

    system: str = Field(..., description="Contact system (phone, email, etc.)")
    value: str = Field(..., description="Contact value")
    use: Optional[str] = Field(None, description="Contact use (home, work, etc.)")


class Address(BaseModel):
    """Patient address model."""

    line: Optional[List[str]] = None
    city: Optional[str] = None
    district: Optional[str] = None
    state: Optional[str] = None
    postalCode: Optional[str] = None
    country: Optional[str] = None
    use: str = Field(default="home")
    type: str = Field(default="physical")


class EmergencyContact(BaseModel):
    """Emergency contact information."""

    name: PatientName
    relationship: str
    contact: List[PatientContact]


class PatientCreateRequest(BaseModel):
    """Patient creation request model."""

    identifier: List[PatientIdentifier] = Field(..., min_length=1)
    name: List[PatientName] = Field(..., min_length=1)
    birthDate: str = Field(..., description="Birth date in YYYY-MM-DD format")
    gender: str = Field(..., pattern="^(male|female|other|unknown)$")
    contact: Optional[List[PatientContact]] = None
    address: Optional[List[Address]] = None
    language: List[str] = Field(default=["en"], description="Preferred languages")
    emergencyContact: Optional[List[EmergencyContact]] = None
    active: bool = Field(default=True)

    @validator("birthDate")
    def validate_birth_date(cls, v: str) -> str:  # pylint: disable=no-self-argument
        """Validate birth date format."""
        try:
            datetime.strptime(v, "%Y-%m-%d")
        except ValueError as exc:
            raise ValueError("Birth date must be in YYYY-MM-DD format") from exc
        return v


class PatientUpdateRequest(BaseModel):
    """Patient update request model."""

    name: Optional[List[PatientName]] = None
    contact: Optional[List[PatientContact]] = None
    address: Optional[List[Address]] = None
    language: Optional[List[str]] = None
    emergencyContact: Optional[List[EmergencyContact]] = None
    active: Optional[bool] = None


class PatientResponse(BaseModel):
    """Patient response model."""

    id: uuid.UUID
    identifier: List[PatientIdentifier]
    name: List[PatientName]
    birthDate: str
    gender: str
    contact: Optional[List[PatientContact]]
    address: Optional[List[Address]]
    language: List[str]
    emergencyContact: Optional[List[EmergencyContact]]
    active: bool
    createdAt: datetime
    updatedAt: datetime
    version: int
    verificationStatus: str


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


async def check_patient_permission(
    user: Dict[str, Any],
    permission: Permission,
    patient_id: Optional[uuid.UUID] = None,
    db: Optional[Session] = None,
) -> bool:
    """Check if user has permission for patient operations."""
    context = ResourceContext(
        user_id=user["user_id"],
        roles=[],  # In a real implementation, would fetch user's roles
        attributes={
            "resource_type": "Patient",
            "resource_id": str(patient_id) if patient_id else None,
            "organization_id": user.get("organization"),
        },
    )

    if not rbac_manager.check_permission(context=context, permission=permission):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions for this operation",
        )
    return True


# GET /patients - List all patients with pagination
@router.get(
    "/",
    response_model=PaginatedResponse[PatientResponse],
    summary="List all patients",
    description="Retrieve a paginated list of patients with optional filtering",
    dependencies=[Depends(require_patient_read)],  # Add scope validation
)
async def list_patients(
    current_user: Dict[str, Any] = Depends(get_current_user),  # noqa: B008
    db: Session = db_dependency,
    page: int = Query(1, ge=1, description="Page number"),  # noqa: B008
    page_size: int = Query(
        20, ge=1, le=100, description="Items per page"
    ),  # noqa: B008
    search: Optional[str] = Query(
        None, description="Search in name or identifier"
    ),  # noqa: B008
    active: Optional[bool] = Query(
        None, description="Filter by active status"
    ),  # noqa: B008
    verification_status: Optional[str] = Query(  # noqa: B008
        None, description="Filter by verification status"
    ),
) -> PaginatedResponse[PatientResponse]:
    """List all patients with pagination and filtering."""
    # Permission check still performed for additional security
    await check_patient_permission(current_user, Permission.READ_PATIENT, db=db)

    try:
        patient_service = PatientService(db)
        audit_service = AuditService(db)

        # Build filters
        filters: Dict[str, Any] = {}
        if active is not None:
            filters["active"] = active
        if verification_status:
            filters["verification_status"] = verification_status

        # Get paginated results
        patients, total = patient_service.search_patients(
            query=search,
            filters=filters,
            limit=page_size,
            offset=(page - 1) * page_size,
        )

        # Audit log
        await audit_service.log_event(
            event_type="LIST_PATIENTS",
            user_id=current_user["user_id"],
            details={
                "resource_type": "Patient",
                "filters": filters,
                "count": len(patients),
            },
        )

        return PaginatedResponse.create(
            items=patients, total=total, page=page, page_size=page_size  # type: ignore[arg-type]
        )

    except Exception as e:
        logger.error(f"Error listing patients: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve patients",
        ) from e


# GET /patients/{id} - Get patient by ID
@router.get(
    "/{patient_id}",
    response_model=PatientResponse,
    summary="Get patient by ID",
    description="Retrieve detailed patient information by ID",
)
async def get_patient(
    patient_id: uuid.UUID,
    current_user: Dict[str, Any] = Depends(get_current_user),  # noqa: B008
    db: Session = db_dependency,
) -> PatientResponse:
    """Get patient by ID."""
    # Check permission
    await check_patient_permission(
        current_user, Permission.READ_PATIENT, patient_id=patient_id, db=db
    )

    try:
        patient_service = PatientService(db)
        audit_service = AuditService(db)

        patient = patient_service.get_by_id(patient_id)

        if not patient:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Patient with ID {patient_id} not found",
            )

        # Audit log
        await audit_service.log_event(
            event_type="READ_PATIENT",
            user_id=current_user["user_id"],
            details={
                "resource_type": "Patient",
                "resource_id": str(patient_id),
                "patient_id": str(patient_id),
            },
        )

        return patient

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving patient {patient_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve patient",
        ) from e


# POST /patients - Create new patient
@router.post(
    "/",
    response_model=PatientResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create new patient",
    description="Create a new patient record",
    dependencies=[Depends(require_patient_write)],  # Add scope validation
)
async def create_patient(
    patient_data: PatientCreateRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),  # noqa: B008
    db: Session = db_dependency,
) -> PatientResponse:
    """Create new patient."""
    # Permission check still performed for additional security
    await check_patient_permission(current_user, Permission.CREATE_PATIENT, db=db)

    try:
        patient_service = PatientService(db)
        audit_service = AuditService(db)

        # Validate FHIR compliance
        fhir_data = patient_data.model_dump()
        validation_result = fhir_validator.validate_resource(
            resource_type="Patient", resource_data=fhir_data
        )

        if not validation_result.get("is_valid", False):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"FHIR validation failed: {validation_result.get('errors', [])}",
            )

        # Create patient
        # Extract required fields from patient data
        name = patient_data.name[0] if patient_data.name else None
        given_name = " ".join(name.given) if name and name.given else ""
        family_name = name.family if name else ""

        patient = patient_service.create_patient(
            given_name=given_name,
            family_name=family_name,
            gender=Gender(patient_data.gender),
            date_of_birth=(
                datetime.strptime(patient_data.birthDate, "%Y-%m-%d").date()
                if patient_data.birthDate
                else None
            ),
            **patient_data.model_dump(),
        )

        # Audit log
        await audit_service.log_event(
            event_type="CREATE_PATIENT",
            user_id=current_user["user_id"],
            details={
                "resource_type": "Patient",
                "resource_id": str(patient.id),
                "patient_id": str(patient.id),
            },
        )

        return patient

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating patient: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create patient",
        ) from e


# PUT /patients/{id} - Update patient
@router.put(
    "/{patient_id}",
    response_model=PatientResponse,
    summary="Update patient",
    description="Update patient information",
)
async def update_patient(
    patient_id: uuid.UUID,
    update_data: PatientUpdateRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),  # noqa: B008
    db: Session = db_dependency,
) -> PatientResponse:
    """Update patient information."""
    # Check permission
    await check_patient_permission(
        current_user, Permission.UPDATE_PATIENT, patient_id=patient_id, db=db
    )

    try:
        patient_service = PatientService(db)
        audit_service = AuditService(db)

        # Get existing patient
        existing_patient = patient_service.get_patient_with_records(
            patient_id=patient_id,
            include_health_records=False,
            include_verifications=False,
            include_family=False,
        )

        if not existing_patient:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Patient with ID {patient_id} not found",
            )

        # Update patient
        updated_patient = patient_service.update_patient_demographics(
            patient_id=patient_id,
            demographics=update_data.model_dump(exclude_unset=True),
        )

        # Audit log
        await audit_service.log_event(
            event_type="UPDATE_PATIENT",
            user_id=current_user["user_id"],
            details={
                "action": "UPDATE_PATIENT",
                "resource_type": "Patient",
                "resource_id": str(patient_id),
                "patient_id": str(patient_id),
                "updated_fields": list(
                    update_data.model_dump(exclude_unset=True).keys()
                ),
            },
        )

        return PatientResponse.from_orm(updated_patient) if updated_patient else None  # type: ignore[return-value]

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating patient {patient_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update patient",
        ) from e


# DELETE /patients/{id} - Delete patient
@router.delete(
    "/{patient_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete patient",
    description="Soft delete a patient record",
    dependencies=[Depends(require_patient_admin)],  # Require admin scope for deletion
)
async def delete_patient(
    patient_id: uuid.UUID,
    current_user: Dict[str, Any] = Depends(get_current_user),  # noqa: B008
    db: Session = db_dependency,
) -> None:
    """Delete patient (soft delete)."""
    # Permission check still performed for additional security
    await check_patient_permission(
        current_user, Permission.DELETE_PATIENT, patient_id=patient_id, db=db
    )

    try:
        patient_service = PatientService(db)
        audit_service = AuditService(db)
        retention_config = RightToDeletionConfiguration()

        # Check if patient exists
        existing_patient = patient_service.get_patient_with_records(
            patient_id=patient_id,
            include_health_records=False,
            include_verifications=False,
            include_family=False,
        )

        if not existing_patient:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Patient with ID {patient_id} not found",
            )

        # Check retention policy before deletion
        retention_requirements = retention_config.check_retention_requirement(
            category=DataCategory.MEDICAL_HISTORY,
            jurisdiction="US",
            patient_age=None,  # Would calculate from birth date in production
        )

        # Perform compliance delete with retention policy check
        if retention_requirements:
            # Archive for retention instead of immediate deletion
            # In production, would archive the patient data
            patient_service.update_patient_demographics(
                patient_id=patient_id, demographics={"active": False, "archived": True}
            )
        else:
            # Soft delete patient after retention compliance check
            patient_service.delete(entity_id=patient_id, hard=False)  # Soft delete

        # Audit log
        await audit_service.log_event(
            event_type="DELETE_PATIENT",
            user_id=current_user["user_id"],
            details={
                "action": "DELETE_PATIENT",
                "resource_type": "Patient",
                "resource_id": str(patient_id),
                "patient_id": str(patient_id),
            },
        )

        return None

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting patient {patient_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete patient",
        ) from e


@router.get("/export", response_class=StreamingResponse)
async def export_patients(
    export_format: str = Query(default="csv", pattern="^(csv|json)$"),  # noqa: B008
    search: Optional[str] = Query(None),  # noqa: B008
    patient_status: Optional[str] = Query(None),  # noqa: B008
    nationality: Optional[str] = Query(None),  # noqa: B008
    gender: Optional[str] = Query(None),  # noqa: B008
    limit: int = Query(default=10000, le=50000),  # noqa: B008
    current_user: Dict[str, Any] = Depends(get_current_user),  # noqa: B008
    db: Session = db_dependency,
) -> StreamingResponse:
    """Export patients to CSV or JSON format."""
    # Permission check
    await check_patient_permission(current_user, Permission.VIEW_PATIENT, db=db)

    try:
        # Build filters
        filters = {}
        if search:
            filters["search"] = search
        if patient_status:
            filters["status"] = patient_status
        if nationality:
            filters["nationality"] = nationality
        if gender:
            filters["gender"] = gender

        # Get patients (mock data for now)
        patients = [
            {
                "id": str(uuid.uuid4()),
                "firstName": "John",
                "lastName": "Doe",
                "dateOfBirth": "1990-01-01",
                "gender": "male",
                "nationality": "Syrian",
                "status": "active",
                "refugeeId": "UNHCR123456",
                "lastVisit": datetime.utcnow().isoformat(),
                "recordsCount": 5,
                "verificationStatus": "verified",
            },
            {
                "id": str(uuid.uuid4()),
                "firstName": "Jane",
                "lastName": "Smith",
                "dateOfBirth": "1985-05-15",
                "gender": "female",
                "nationality": "Afghan",
                "status": "active",
                "refugeeId": "UNHCR789012",
                "lastVisit": datetime.utcnow().isoformat(),
                "recordsCount": 3,
                "verificationStatus": "pending",
            },
        ]

        if export_format == "csv":
            # Generate CSV
            output = io.StringIO()
            writer = csv.DictWriter(
                output, fieldnames=patients[0].keys() if patients else []
            )
            writer.writeheader()
            writer.writerows(patients)

            return StreamingResponse(
                io.BytesIO(output.getvalue().encode()),
                media_type="text/csv",
                headers={
                    "Content-Disposition": f"attachment; filename=patients_export_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
                },
            )
        else:
            # Generate JSON
            return StreamingResponse(
                io.BytesIO(json.dumps(patients, indent=2).encode()),
                media_type="application/json",
                headers={
                    "Content-Disposition": f"attachment; filename=patients_export_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
                },
            )

    except Exception as e:
        logger.error(f"Error exporting patients: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to export patients",
        ) from e
