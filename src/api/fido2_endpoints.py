"""FIDO2 key management endpoints.

This module provides REST API endpoints for FIDO2 security key registration
and authentication, including support for hardware tokens like YubiKey.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.api.auth_endpoints import get_current_user
from src.core.database import get_db
from src.models.auth import UserAuth, WebAuthnCredential
from src.services.webauthn_service import WebAuthnService
from src.utils.logging import get_logger

router = APIRouter(prefix="/auth/fido2", tags=["fido2"])
logger = get_logger(__name__)

# Module-level dependency variables to avoid B008 errors
db_dependency = Depends(get_db)
current_user_dependency = Depends(get_current_user)


# Request/Response Models
class Fido2RegistrationBeginRequest(BaseModel):
    """FIDO2 registration initialization request."""

    authenticator_type: str = Field(
        default="cross-platform", pattern="^(cross-platform|platform)$"
    )
    device_name: Optional[str] = None


class Fido2RegistrationBeginResponse(BaseModel):
    """FIDO2 registration initialization response."""

    challenge: str
    rp: Dict[str, str]
    user: Dict[str, str]
    pubKeyCredParams: List[Dict[str, Any]]
    timeout: int
    attestation: str
    authenticatorSelection: Dict[str, Any]
    excludeCredentials: List[Dict[str, Any]]


class Fido2RegistrationCompleteRequest(BaseModel):
    """FIDO2 registration completion request."""

    id: str
    rawId: str
    type: str
    response: Dict[str, str]
    authenticatorAttachment: Optional[str] = None
    device_name: Optional[str] = None


class Fido2RegistrationCompleteResponse(BaseModel):
    """FIDO2 registration completion response."""

    success: bool
    credential_id: str
    device_name: str
    message: str


class Fido2AuthenticationBeginRequest(BaseModel):
    """FIDO2 authentication initialization request."""

    user_verification: Optional[str] = "required"


class Fido2AuthenticationBeginResponse(BaseModel):
    """FIDO2 authentication initialization response."""

    challenge: str
    timeout: int
    rpId: str
    allowCredentials: List[Dict[str, Any]]
    userVerification: str


class Fido2AuthenticationCompleteRequest(BaseModel):
    """FIDO2 authentication completion request."""

    id: str
    rawId: str
    type: str
    response: Dict[str, str]
    authenticatorAttachment: Optional[str] = None


class Fido2AuthenticationCompleteResponse(BaseModel):
    """FIDO2 authentication completion response."""

    success: bool
    verified: bool
    message: str


class Fido2KeyInfo(BaseModel):
    """FIDO2 key information."""

    credential_id: str
    device_name: str
    authenticator_type: str
    created_at: datetime
    last_used_at: Optional[datetime]
    usage_count: int
    is_active: bool


class Fido2KeysListResponse(BaseModel):
    """FIDO2 keys list response."""

    keys: List[Fido2KeyInfo]
    total: int


class Fido2KeyUpdateRequest(BaseModel):
    """FIDO2 key update request."""

    device_name: Optional[str] = None
    is_active: Optional[bool] = None


@router.post("/register/begin", response_model=Fido2RegistrationBeginResponse)
async def begin_fido2_registration(
    request: Fido2RegistrationBeginRequest,
    current_user: UserAuth = current_user_dependency,
    db: Session = db_dependency,
) -> Fido2RegistrationBeginResponse:
    """Begin FIDO2 key registration process."""
    try:
        # Create WebAuthn service instance
        webauthn_service = WebAuthnService(db)

        # Override authenticator attachment for FIDO2 keys
        webauthn_service.settings.authenticator_attachment = request.authenticator_type

        # Create registration options
        options = await webauthn_service.create_registration_options(current_user)

        # Ensure proper FIDO2 key configuration
        options["authenticatorSelection"] = {
            "authenticatorAttachment": request.authenticator_type,
            "requireResidentKey": False,
            "residentKey": "discouraged",  # For security keys
            "userVerification": "required",
        }

        # Add FIDO2-specific attestation preference
        options["attestation"] = "direct"  # Get attestation for security keys

        return Fido2RegistrationBeginResponse(**options)

    except Exception as e:
        logger.error(f"FIDO2 registration begin error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to start FIDO2 registration",
        ) from e


@router.post("/register/complete", response_model=Fido2RegistrationCompleteResponse)
async def complete_fido2_registration(
    request: Fido2RegistrationCompleteRequest,
    current_user: UserAuth = current_user_dependency,
    db: Session = db_dependency,
) -> Fido2RegistrationCompleteResponse:
    """Complete FIDO2 key registration process."""
    try:
        # Create WebAuthn service instance
        webauthn_service = WebAuthnService(db)

        # Prepare credential data
        credential_data = {
            "id": request.id,
            "rawId": request.rawId,
            "type": request.type,
            "response": request.response,
        }

        # Set device name for FIDO2 key
        device_name = request.device_name or "FIDO2 Security Key"

        # Verify registration
        success, result = await webauthn_service.verify_registration(
            current_user, credential_data, device_name
        )

        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Registration failed: {result}",
            )

        # Log successful registration
        logger.info(f"FIDO2 key registered for user {current_user.id}: {device_name}")

        return Fido2RegistrationCompleteResponse(
            success=True,
            credential_id=str(result) if result else "",
            device_name=device_name,
            message="FIDO2 key registered successfully",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"FIDO2 registration complete error: {e}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to complete FIDO2 registration",
        ) from e


@router.post("/authenticate/begin", response_model=Fido2AuthenticationBeginResponse)
async def begin_fido2_authentication(
    request: Fido2AuthenticationBeginRequest,
    current_user: UserAuth = current_user_dependency,
    db: Session = db_dependency,
) -> Fido2AuthenticationBeginResponse:
    """Begin FIDO2 authentication process."""
    try:
        # Create WebAuthn service instance
        webauthn_service = WebAuthnService(db)

        # Check if user has any FIDO2 keys registered
        fido2_keys = (
            db.query(WebAuthnCredential)
            .filter(
                WebAuthnCredential.user_id == current_user.id,
                WebAuthnCredential.is_active.is_(True),  # noqa: E712
                WebAuthnCredential.authenticator_attachment == "cross-platform",
            )
            .all()
        )

        if not fido2_keys:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No FIDO2 keys registered for this account",
            )

        # Create authentication options
        options = await webauthn_service.create_authentication_options(current_user)

        # Ensure user verification is set
        options["userVerification"] = request.user_verification

        return Fido2AuthenticationBeginResponse(**options)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"FIDO2 authentication begin error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to start FIDO2 authentication",
        ) from e


@router.post(
    "/authenticate/complete", response_model=Fido2AuthenticationCompleteResponse
)
async def complete_fido2_authentication(
    request: Fido2AuthenticationCompleteRequest,
    current_user: UserAuth = current_user_dependency,
    db: Session = db_dependency,
) -> Fido2AuthenticationCompleteResponse:
    """Complete FIDO2 authentication process."""
    try:
        # Create WebAuthn service instance
        webauthn_service = WebAuthnService(db)

        # Prepare assertion data
        assertion_data = {
            "id": request.id,
            "rawId": request.rawId,
            "type": request.type,
            "response": request.response,
        }

        # Verify authentication
        success, error_msg = await webauthn_service.verify_authentication(
            current_user, assertion_data
        )

        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Authentication failed: {error_msg}",
            )

        # Log successful authentication
        logger.info(f"FIDO2 authentication successful for user {current_user.id}")

        return Fido2AuthenticationCompleteResponse(
            success=True, verified=True, message="FIDO2 authentication successful"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"FIDO2 authentication complete error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to complete FIDO2 authentication",
        ) from e


@router.get("/keys", response_model=Fido2KeysListResponse)
async def list_fido2_keys(
    current_user: UserAuth = current_user_dependency, db: Session = db_dependency
) -> Fido2KeysListResponse:
    """List all FIDO2 keys for the current user."""
    try:
        # Query FIDO2 keys (cross-platform authenticators)
        fido2_keys = (
            db.query(WebAuthnCredential)
            .filter(
                WebAuthnCredential.user_id == current_user.id,
                WebAuthnCredential.authenticator_attachment == "cross-platform",
            )
            .order_by(WebAuthnCredential.created_at.desc())
            .all()
        )

        # Format key information
        keys_info = []
        for key in fido2_keys:
            keys_info.append(
                Fido2KeyInfo(
                    credential_id=key.credential_id,
                    device_name=key.device_name or "FIDO2 Security Key",
                    authenticator_type=key.authenticator_attachment or "cross-platform",
                    created_at=key.created_at,  # type: ignore[arg-type]
                    last_used_at=key.last_used_at,
                    usage_count=key.usage_count or 0,
                    is_active=key.is_active,
                )
            )

        return Fido2KeysListResponse(keys=keys_info, total=len(keys_info))

    except Exception as e:
        logger.error(f"List FIDO2 keys error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve FIDO2 keys",
        ) from e


@router.put("/keys/{credential_id}", response_model=Dict[str, str])
async def update_fido2_key(
    credential_id: str,
    request: Fido2KeyUpdateRequest,
    current_user: UserAuth = current_user_dependency,
    db: Session = db_dependency,
) -> Dict[str, str]:
    """Update FIDO2 key information."""
    try:
        # Find the credential
        credential = (
            db.query(WebAuthnCredential)
            .filter(
                WebAuthnCredential.user_id == current_user.id,
                WebAuthnCredential.credential_id == credential_id,
            )
            .first()
        )

        if not credential:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="FIDO2 key not found"
            )

        # Update fields if provided
        if request.device_name is not None:
            credential.device_name = request.device_name

        if request.is_active is not None:
            credential.is_active = request.is_active
            if not request.is_active:
                credential.revoked_at = datetime.utcnow()
                credential.revocation_reason = "User deactivated"

        db.commit()

        logger.info(f"FIDO2 key updated: {credential_id} for user {current_user.id}")

        return {"message": "FIDO2 key updated successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Update FIDO2 key error: {e}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update FIDO2 key",
        ) from e


@router.delete("/keys/{credential_id}", response_model=Dict[str, str])
async def revoke_fido2_key(
    credential_id: str,
    current_user: UserAuth = current_user_dependency,
    db: Session = db_dependency,
) -> Dict[str, str]:
    """Revoke a FIDO2 key."""
    try:
        # Find the credential
        credential = (
            db.query(WebAuthnCredential)
            .filter(
                WebAuthnCredential.user_id == current_user.id,
                WebAuthnCredential.credential_id == credential_id,
            )
            .first()
        )

        if not credential:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="FIDO2 key not found"
            )

        # Check if this is the last active FIDO2 key
        active_keys_count = (
            db.query(WebAuthnCredential)
            .filter(
                WebAuthnCredential.user_id == current_user.id,
                WebAuthnCredential.is_active.is_(True),  # noqa: E712
                WebAuthnCredential.authenticator_attachment == "cross-platform",
            )
            .count()
        )

        if active_keys_count == 1:
            # Check if user has other MFA methods enabled
            if not current_user.mfa_config or not current_user.mfa_config.is_enabled:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot revoke the last FIDO2 key without other MFA methods enabled",
                )

        # Revoke the key
        credential.is_active = False
        credential.revoked_at = datetime.utcnow()
        credential.revocation_reason = "User revoked"
        db.commit()

        logger.info(f"FIDO2 key revoked: {credential_id} for user {current_user.id}")

        return {"message": "FIDO2 key revoked successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Revoke FIDO2 key error: {e}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to revoke FIDO2 key",
        ) from e


@router.get("/supported-authenticators", response_model=Dict[str, List[Dict[str, str]]])
async def get_supported_authenticators() -> Dict[str, List[Dict[str, str]]]:
    """Get list of recommended FIDO2 authenticators."""
    return {
        "recommended_authenticators": [
            {
                "name": "YubiKey 5 Series",
                "vendor": "Yubico",
                "protocols": "FIDO2, WebAuthn, U2F",
                "transports": "USB-A, USB-C, NFC, Lightning",
            },
            {
                "name": "Titan Security Key",
                "vendor": "Google",
                "protocols": "FIDO2, WebAuthn, U2F",
                "transports": "USB-A, USB-C, NFC, Bluetooth",
            },
            {
                "name": "Solo V2",
                "vendor": "SoloKeys",
                "protocols": "FIDO2, WebAuthn, U2F",
                "transports": "USB-A, USB-C, NFC",
            },
            {
                "name": "Feitian ePass",
                "vendor": "Feitian",
                "protocols": "FIDO2, WebAuthn, U2F",
                "transports": "USB-A, USB-C, NFC, Bluetooth",
            },
        ]
    }
