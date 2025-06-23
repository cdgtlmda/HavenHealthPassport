"""Biometric authentication API endpoints.

This module provides REST API endpoints for biometric authentication
including enrollment, verification, management, and WebAuthn support.
"""

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field, validator
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.auth.authentication_flow import AuthenticationFlow
from src.auth.biometric_auth import BiometricAuthManager, BiometricType
from src.auth.jwt_handler import JWTHandler
from src.core.database import get_db
from src.models.auth import UserAuth
from src.services.webauthn_service import WebAuthnService
from src.utils.exceptions import (
    BiometricNotEnrolledException,
    BiometricVerificationException,
)
from src.utils.logging import get_logger

router = APIRouter(prefix="/biometric", tags=["biometric"])
logger = get_logger(__name__)
security = HTTPBearer()

# Module-level dependency variables to avoid B008 errors
db_dependency = Depends(get_db)
security_dependency = Depends(security)


# Request/Response Models
class BiometricEnrollRequest(BaseModel):
    """Biometric enrollment request."""

    biometric_type: str = Field(
        ..., description="Type of biometric: fingerprint, face, voice, iris, palm"
    )
    biometric_data: Dict[str, Any] = Field(
        ..., description="Raw biometric data from device"
    )
    device_info: Optional[Dict[str, str]] = Field(
        None, description="Capture device information"
    )

    @validator("biometric_type")
    @classmethod
    def validate_biometric_type(cls, v: str) -> str:
        """Validate biometric type."""
        valid_types = ["fingerprint", "face", "voice", "iris", "palm"]
        if v not in valid_types:
            raise ValueError(
                f"Invalid biometric type. Must be one of: {', '.join(valid_types)}"
            )
        return v

    @validator("biometric_data")
    @classmethod
    def validate_biometric_data(cls, v: Dict[str, Any]) -> Dict[str, Any]:
        """Validate biometric data structure."""
        if not isinstance(v, dict) or not v:
            raise ValueError("Biometric data must be a non-empty dictionary")
        return v


class BiometricEnrollResponse(BaseModel):
    """Biometric enrollment response."""

    success: bool
    template_id: Optional[str] = None
    message: str
    enrolled_at: Optional[datetime] = None


class BiometricVerifyRequest(BaseModel):
    """Biometric verification request."""

    biometric_type: str = Field(..., description="Type of biometric")
    biometric_data: Dict[str, Any] = Field(..., description="Raw biometric data")
    device_info: Optional[Dict[str, str]] = None
    device_fingerprint: Optional[str] = None

    @validator("biometric_type")
    @classmethod
    def validate_biometric_type(cls, v: str) -> str:
        """Validate biometric type."""
        valid_types = ["fingerprint", "face", "voice", "iris", "palm"]
        if v not in valid_types:
            raise ValueError(
                f"Invalid biometric type. Must be one of: {', '.join(valid_types)}"
            )
        return v


class BiometricVerifyResponse(BaseModel):
    """Biometric verification response."""

    verified: bool
    message: str
    access_token: Optional[str] = None
    session_id: Optional[str] = None
    matched_template_id: Optional[str] = None


class BiometricUpdateRequest(BaseModel):
    """Biometric template update request."""

    template_id: str
    new_biometric_data: Dict[str, Any]


class BiometricListResponse(BaseModel):
    """List of enrolled biometrics."""

    biometrics: List[Dict[str, Any]]
    total_count: int


class WebAuthnRegisterRequest(BaseModel):
    """WebAuthn registration request."""

    # Will be populated by WebAuthn client data


class WebAuthnRegisterResponse(BaseModel):
    """WebAuthn registration response."""

    challenge: str
    rp: Dict[str, str]
    user: Dict[str, str]
    pubKeyCredParams: List[Dict[str, Any]]
    authenticatorSelection: Dict[str, str]
    timeout: int
    attestation: str


class WebAuthnVerifyRequest(BaseModel):
    """WebAuthn authentication request."""

    assertion: Dict[str, Any]


class WebAuthnVerifyResponse(BaseModel):
    """WebAuthn authentication response."""

    verified: bool
    message: str
    access_token: Optional[str] = None
    session_id: Optional[str] = None


# Dependency for getting current user
async def get_current_user(
    credentials: HTTPAuthorizationCredentials = security_dependency,
    db: Session = db_dependency,
) -> UserAuth:
    """Get current authenticated user."""
    jwt_handler = JWTHandler()
    payload = jwt_handler.decode_token(credentials.credentials)

    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token"
        )

    user_id = payload.get("user_id")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload"
        )

    user = db.query(UserAuth).filter(UserAuth.id == uuid.UUID(user_id)).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    return user


# Module-level dependency for current user (must be after get_current_user definition)
current_user_dependency = Depends(get_current_user)


# Biometric Enrollment Endpoints
@router.post(
    "/enroll",
    response_model=BiometricEnrollResponse,
    status_code=status.HTTP_201_CREATED,
)
async def enroll_biometric(
    request: BiometricEnrollRequest,
    current_user: UserAuth = current_user_dependency,
    db: Session = db_dependency,
) -> BiometricEnrollResponse:
    """Enroll a new biometric template.

    Args:
        request: Biometric enrollment request
        current_user: Current authenticated user
        db: Database session

    Returns:
        Enrollment response with template ID
    """
    try:
        biometric_manager = BiometricAuthManager(db)
        biometric_type = BiometricType(request.biometric_type)

        # Log enrollment attempt
        logger.info(
            f"User {current_user.id} enrolling {biometric_type.value} biometric"
        )

        # Enroll biometric
        success, result = biometric_manager.enroll_biometric(
            user=current_user,
            biometric_type=biometric_type,
            biometric_data=request.biometric_data,
            device_info=request.device_info,
        )

        if success:
            return BiometricEnrollResponse(
                success=True,
                template_id=result,
                message="Biometric enrolled successfully",
                enrolled_at=datetime.utcnow(),
            )
        else:
            return BiometricEnrollResponse(success=False, message=result)

    except Exception as e:
        logger.error(f"Biometric enrollment error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Biometric enrollment failed",
        ) from e


# Biometric Verification Endpoints
@router.post("/verify", response_model=BiometricVerifyResponse)
async def verify_biometric(
    request: BiometricVerifyRequest,
    current_user: UserAuth = current_user_dependency,
    db: Session = db_dependency,
) -> BiometricVerifyResponse:
    """Verify biometric data against enrolled templates.

    Args:
        request: Biometric verification request
        current_user: Current authenticated user
        db: Database session

    Returns:
        Verification response with authentication tokens if successful
    """
    try:
        biometric_manager = BiometricAuthManager(db)
        biometric_type = BiometricType(request.biometric_type)

        # Log verification attempt
        logger.info(
            f"User {current_user.id} verifying {biometric_type.value} biometric"
        )

        # Verify biometric
        success, result = biometric_manager.verify_biometric(
            user=current_user,
            biometric_type=biometric_type,
            biometric_data=request.biometric_data,
            device_info=request.device_info,
        )

        if success:
            # Create authentication tokens if verification successful
            auth_flow = AuthenticationFlow(db)
            auth_response = auth_flow.authenticate_with_biometric(
                user_id=str(current_user.id),
                biometric_data=request.biometric_data,
                device_fingerprint=request.device_fingerprint,
            )

            return BiometricVerifyResponse(
                verified=True,
                message="Biometric verification successful",
                access_token=auth_response["access_token"],
                session_id=auth_response["session_id"],
                matched_template_id=result,
            )
        else:
            return BiometricVerifyResponse(
                verified=False, message=result or "Verification failed"
            )

    except BiometricNotEnrolledException as e:
        logger.warning(f"Biometric not enrolled: {e}")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except BiometricVerificationException as e:
        logger.warning(f"Biometric verification failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e)
        ) from e
    except Exception as e:
        logger.error(f"Biometric verification error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Biometric verification failed",
        ) from e


# Passwordless Biometric Authentication
@router.post("/authenticate", response_model=BiometricVerifyResponse)
async def authenticate_biometric(
    request: BiometricVerifyRequest, db: Session = db_dependency
) -> BiometricVerifyResponse:
    """Authenticate user with biometric only (passwordless).

    This endpoint requires user_id in the request for initial identification.

    Args:
        request: Biometric verification request
        db: Database session

    Returns:
        Authentication response with tokens
    """
    try:
        # Extract user_id from biometric_data (client should include it)
        user_id = request.biometric_data.get("user_id")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User ID required for passwordless authentication",
            )

        # Validate user exists
        user = db.query(UserAuth).filter(UserAuth.id == uuid.UUID(user_id)).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )

        # Authenticate with biometric
        auth_flow = AuthenticationFlow(db)
        auth_response = auth_flow.authenticate_with_biometric(
            user_id=user_id,
            biometric_data=request.biometric_data,
            device_fingerprint=request.device_fingerprint,
        )

        return BiometricVerifyResponse(
            verified=True,
            message="Authentication successful",
            access_token=auth_response["access_token"],
            session_id=auth_response["session_id"],
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Passwordless authentication error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication failed",
        ) from e


# Biometric Management Endpoints
@router.get("/list", response_model=BiometricListResponse)
async def list_enrolled_biometrics(
    current_user: UserAuth = current_user_dependency, db: Session = db_dependency
) -> BiometricListResponse:
    """List all enrolled biometrics for the current user.

    Args:
        current_user: Current authenticated user
        db: Database session

    Returns:
        List of enrolled biometrics
    """
    try:
        biometric_manager = BiometricAuthManager(db)
        enrolled = biometric_manager.get_enrolled_biometrics(current_user)

        return BiometricListResponse(biometrics=enrolled, total_count=len(enrolled))

    except Exception as e:
        logger.error(f"List biometrics error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve biometrics",
        ) from e


@router.put("/update", response_model=BiometricEnrollResponse)
async def update_biometric(
    request: BiometricUpdateRequest,
    current_user: UserAuth = current_user_dependency,
    db: Session = db_dependency,
) -> BiometricEnrollResponse:
    """Update an existing biometric template.

    Args:
        request: Biometric update request
        current_user: Current authenticated user
        db: Database session

    Returns:
        Update response
    """
    try:
        biometric_manager = BiometricAuthManager(db)

        success, message = biometric_manager.update_biometric(
            user=current_user,
            template_id=request.template_id,
            new_biometric_data=request.new_biometric_data,
        )

        return BiometricEnrollResponse(
            success=success,
            template_id=request.template_id if success else None,
            message=message,
        )

    except Exception as e:
        logger.error(f"Update biometric error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update biometric",
        ) from e


@router.delete("/revoke/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_biometric(
    template_id: str,
    current_user: UserAuth = current_user_dependency,
    db: Session = db_dependency,
) -> None:
    """Revoke a specific biometric template.

    Args:
        template_id: Template ID to revoke
        current_user: Current authenticated user
        db: Database session
    """
    try:
        biometric_manager = BiometricAuthManager(db)

        success, message = biometric_manager.revoke_biometric(
            user=current_user, template_id=template_id
        )

        if not success:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=message)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Revoke biometric error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to revoke biometric",
        ) from e


@router.delete("/revoke-all/{biometric_type}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_all_biometrics(
    biometric_type: str,
    current_user: UserAuth = current_user_dependency,
    db: Session = db_dependency,
) -> None:
    """Revoke all biometric templates of a specific type.

    Args:
        biometric_type: Type of biometrics to revoke
        current_user: Current authenticated user
        db: Database session
    """
    try:
        biometric_manager = BiometricAuthManager(db)
        bio_type = BiometricType(biometric_type)

        success, message = biometric_manager.revoke_biometric(
            user=current_user, biometric_type=bio_type
        )

        if not success:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=message)

    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid biometric type"
        ) from None
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Revoke all biometrics error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to revoke biometrics",
        ) from e


# WebAuthn/FIDO2 Endpoints
@router.post("/webauthn/register/begin", response_model=WebAuthnRegisterResponse)
async def webauthn_register_begin(
    current_user: UserAuth = current_user_dependency, db: Session = db_dependency
) -> WebAuthnRegisterResponse:
    """Begin WebAuthn registration process.

    Args:
        current_user: Current authenticated user
        db: Database session

    Returns:
        WebAuthn registration options
    """
    try:
        webauthn_service = WebAuthnService(db)
        options = await webauthn_service.create_registration_options(current_user)

        return WebAuthnRegisterResponse(**options)

    except Exception as e:
        logger.error(f"WebAuthn registration begin error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to start WebAuthn registration",
        ) from e


@router.post("/webauthn/register/complete")
async def webauthn_register_complete(
    credential: Dict[str, Any],
    current_user: UserAuth = current_user_dependency,
    db: Session = db_dependency,
) -> Dict[str, str]:
    """Complete WebAuthn registration process.

    Args:
        credential: Registration credential from client
        current_user: Current authenticated user
        db: Database session

    Returns:
        Registration result
    """
    try:
        webauthn_service = WebAuthnService(db)
        device_name = credential.get("deviceName", "WebAuthn Device")
        success, result = await webauthn_service.verify_registration(
            current_user, credential, device_name
        )

        if success:
            return {
                "success": "true",
                "credential_id": result or "",
                "message": "WebAuthn device registered successfully",
            }
        else:
            return {"success": "false", "message": result or "Registration failed"}

    except Exception as e:
        logger.error(f"WebAuthn registration complete error: {e}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to complete WebAuthn registration",
        ) from e


@router.post("/webauthn/authenticate/begin")
async def webauthn_authenticate_begin(
    user_id: str, db: Session = db_dependency
) -> Dict[str, Any]:
    """Begin WebAuthn authentication process.

    Args:
        user_id: User ID for authentication
        db: Database session

    Returns:
        WebAuthn authentication options
    """
    try:
        # Validate user exists
        user = db.query(UserAuth).filter(UserAuth.id == uuid.UUID(user_id)).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )

        webauthn_service = WebAuthnService(db)
        options = await webauthn_service.create_authentication_options(user)

        return options

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"WebAuthn authentication begin error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to start WebAuthn authentication",
        ) from e


@router.post("/webauthn/authenticate/complete", response_model=WebAuthnVerifyResponse)
async def webauthn_authenticate_complete(
    request: WebAuthnVerifyRequest, db: Session = db_dependency
) -> WebAuthnVerifyResponse:
    """Complete WebAuthn authentication process.

    Args:
        request: WebAuthn verification request
        db: Database session

    Returns:
        Authentication response with tokens
    """
    try:
        # Extract user_id from assertion
        user_id = request.assertion.get("user_id")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User ID required in assertion",
            )

        # Get user
        user = db.query(UserAuth).filter(UserAuth.id == uuid.UUID(user_id)).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )

        # Verify WebAuthn assertion
        webauthn_service = WebAuthnService(db)
        success, error = await webauthn_service.verify_authentication(
            user, request.assertion
        )

        if success:
            # Use AuthenticationFlow for proper authentication
            auth_flow = AuthenticationFlow(db)

            # Prepare biometric data for authentication
            biometric_data = {"type": "webauthn", "assertion": request.assertion}

            # Authenticate with biometric
            auth_result = auth_flow.authenticate_with_biometric(
                user_id=str(user.id),
                biometric_data=biometric_data,
                device_fingerprint=getattr(request, "device_fingerprint", None),
                ip_address=getattr(request, "client_ip", None),
                user_agent=getattr(request, "user_agent", None),
            )

            access_token = auth_result["access_token"]
            session_id = auth_result["session_id"]

            return WebAuthnVerifyResponse(
                verified=True,
                message="WebAuthn authentication successful",
                access_token=access_token,
                session_id=session_id,
            )
        else:
            return WebAuthnVerifyResponse(
                verified=False, message=error or "WebAuthn authentication failed"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"WebAuthn authentication complete error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to complete WebAuthn authentication",
        ) from e


# Health check endpoint for biometric services
@router.get("/health")
async def biometric_health_check(db: Session = db_dependency) -> Dict[str, Any]:
    """Check health of biometric services.

    Returns:
        Health status of biometric components
    """
    try:
        # Check database connectivity
        with db as session:
            session.execute(text("SELECT 1"))

        return {
            "status": "healthy",
            "services": {
                "database": "connected",
                "biometric_auth": "operational",
                "webauthn": "operational",
            },
            "timestamp": datetime.utcnow().isoformat(),
        }

    except (KeyError, ValueError, OSError) as e:
        logger.error("Health check error: %s", str(e), exc_info=True)
        return {
            "status": "unhealthy",
            "error": "Service check failed",
            "timestamp": datetime.utcnow().isoformat(),
        }
