"""MFA API endpoints.

This module provides REST API endpoints for multi-factor authentication
operations including setup, verification, and management.

CRITICAL: This is a healthcare application handling refugee medical data.
MFA is essential for HIPAA compliance and data protection.
"""

import base64
import io
import json
import secrets
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

try:
    import pyotp

    HAS_PYOTP = True
except ImportError:
    pyotp = None  # type: ignore[assignment]
    HAS_PYOTP = False

try:
    import qrcode
    from qrcode.image.pure import PyPNGImage  # noqa: F401

    HAS_QRCODE = True
except ImportError:
    qrcode = None
    HAS_QRCODE = False

import os

import redis.asyncio as redis
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import StreamingResponse
from passlib.context import CryptContext
from pydantic import BaseModel, Field, validator
from sqlalchemy.orm import Session

from src.auth.jwt_handler import JWTHandler
from src.auth.mfa import MFAManager, MFAMethod
from src.auth.totp_config import get_totp_manager
from src.core.database import get_db
from src.models.auth import UserAuth
from src.security.encryption import EncryptionService
from src.services.audit_service import AuditService
from src.services.sms.sms_service import SMSService
from src.utils.exceptions import (
    InvalidMFACodeException,
    MFAMethodNotEnabledException,
    TooManyAttemptsException,
)
from src.utils.logging import get_logger
from src.utils.rate_limiter import RateLimiter

# Initialize audit service
audit_service = AuditService(db_session=None)  # type: ignore[arg-type] # Will get session from context

# SMS service will be initialized per request with DB session
sms_service = None

logger = get_logger(__name__)

# Verify required packages
if not HAS_PYOTP:
    raise ImportError(
        "CRITICAL: pyotp is required for MFA in production. "
        "Install with: pip install pyotp"
    )

if not HAS_QRCODE:
    raise ImportError(
        "CRITICAL: qrcode is required for MFA setup in production. "
        "Install with: pip install qrcode[pil]"
    )

# Create instances
jwt_handler = JWTHandler()
encryption_service = EncryptionService(kms_key_id="alias/haven-health-mfa")
rate_limiter = RateLimiter()

# Module-level dependency variables
decode_token_dependency = Depends(jwt_handler.decode_token)
db_dependency = Depends(get_db)


def get_current_user(token: str = decode_token_dependency) -> str:
    """Get current user from JWT token."""
    return token


current_user_dependency = Depends(get_current_user)

router = APIRouter(prefix="/api/v1/auth/mfa", tags=["MFA"])

# Redis client for session storage
redis_client: Optional[redis.Redis] = None


async def get_redis_client() -> redis.Redis:
    """Get Redis client for session storage."""
    global redis_client
    if not redis_client:
        redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/1")
        redis_client = await redis.from_url(redis_url, decode_responses=True)
    assert redis_client is not None
    return redis_client


# Request/Response Models
class MFARequirementResponse(BaseModel):
    """MFA requirement check response."""

    required: bool
    enforcement_level: str
    configured_methods: List[str]
    available_methods: List[str]
    grace_period_remaining: Optional[int] = None  # Days remaining
    message: Optional[str] = None


class TOTPSetupResponse(BaseModel):
    """TOTP setup response."""

    session_id: str  # Secure session ID for QR code retrieval
    provisioning_uri: str
    qr_code: Optional[str] = None  # Base64 encoded QR code image
    manual_entry_key: str  # For manual entry
    algorithm: str = "SHA1"
    digits: int = 6
    period: int = 30


class MFAVerifyRequest(BaseModel):
    """MFA verification request."""

    method: str = Field(..., description="MFA method (totp, sms, email, backup_code)")
    code: str = Field(..., description="Verification code")
    session_id: Optional[str] = Field(
        None, description="Session ID for stateful operations"
    )

    @validator("code")
    @classmethod
    def validate_code(cls, v: str) -> str:
        """Validate code format."""
        if not v or not v.strip():
            raise ValueError("Code cannot be empty")
        # Remove spaces and validate format
        code = v.replace(" ", "").strip()
        if len(code) < 6 or len(code) > 12:
            raise ValueError("Invalid code length")
        if not code.replace("-", "").isalnum():
            raise ValueError("Code must be alphanumeric")
        return code


class SMSSetupRequest(BaseModel):
    """SMS setup request."""

    phone_number: Optional[str] = Field(
        None, description="Phone number for SMS (uses account phone if not provided)"
    )
    country_code: Optional[str] = Field("US", description="ISO country code")

    @validator("phone_number")
    @classmethod
    def validate_phone(cls, v: Optional[str]) -> Optional[str]:
        """Validate phone number format."""
        if v:
            # Remove common formatting
            cleaned = (
                v.replace("-", "").replace(" ", "").replace("(", "").replace(")", "")
            )
            if not cleaned.startswith("+"):
                cleaned = "+" + cleaned
            if len(cleaned) < 10 or len(cleaned) > 16:
                raise ValueError("Invalid phone number length")
            if not cleaned[1:].isdigit():
                raise ValueError("Phone number must contain only digits")
            return cleaned
        return v


class BackupCodesResponse(BaseModel):
    """Backup codes response."""

    codes: List[str]
    generated_at: str
    warning: str = "Store these codes securely. Each can only be used once."


class MFAMethodInfo(BaseModel):
    """MFA method information."""

    method: str
    enabled: bool
    verified: bool
    name: str
    description: str
    phone: Optional[str] = None
    email: Optional[str] = None
    remaining: Optional[int] = None  # For backup codes
    last_used: Optional[str] = None
    setup_required: bool = False


class MFADisableRequest(BaseModel):
    """MFA disable request."""

    method: str = Field(..., description="MFA method to disable")
    password: str = Field(..., description="Current password for verification")
    reason: Optional[str] = Field(None, description="Reason for disabling")


# Production Session Management
class MFASessionManager:
    """Manage MFA setup sessions securely."""

    def __init__(self) -> None:
        """Initialize MFA session manager with default TTL values."""
        self.ttl = 600  # 10 minutes for setup sessions
        self.verification_ttl = 300  # 5 minutes for verification

    async def create_setup_session(
        self, user_id: int, method: str, data: Dict[str, Any]
    ) -> str:
        """Create secure setup session."""
        session_id = str(uuid.uuid4())
        redis_conn = await get_redis_client()

        session_data = {
            "user_id": user_id,
            "method": method,
            "created_at": datetime.utcnow().isoformat(),
            **data,
        }

        # Encrypt sensitive data
        encrypted_data = await encryption_service.encrypt(
            json.dumps(session_data).encode()
        )

        await redis_conn.setex(
            f"mfa_setup:{session_id}",
            self.ttl,
            base64.b64encode(json.dumps(encrypted_data).encode()).decode(),
        )

        return session_id

    async def get_setup_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve setup session data."""
        redis_conn = await get_redis_client()

        encrypted_b64 = await redis_conn.get(f"mfa_setup:{session_id}")
        if not encrypted_b64:
            return None

        try:
            encrypted_data = base64.b64decode(encrypted_b64)
            decrypted = await encryption_service.decrypt(encrypted_data)
            result = json.loads(decrypted)
            return dict(result)
        except Exception as e:
            logger.error(f"Failed to decrypt session data: {e}")
            return None

    async def delete_setup_session(self, session_id: str) -> None:
        """Delete setup session."""
        redis_conn = await get_redis_client()
        await redis_conn.delete(f"mfa_setup:{session_id}")


session_manager = MFASessionManager()


# Endpoints
@router.get("/requirement", response_model=MFARequirementResponse)
async def check_mfa_requirement(
    current_user: UserAuth = current_user_dependency, db: Session = db_dependency
) -> MFARequirementResponse:
    """Check MFA requirement for current user."""
    mfa_manager = MFAManager(db)

    try:
        enforcement_level = mfa_manager.check_mfa_requirement(current_user)
        mfa_config = current_user.mfa_config

        configured_methods = []
        if mfa_config:
            configured_methods = mfa_config.enabled_methods

        # Get available methods
        available_methods = []
        all_methods = mfa_manager.get_available_methods(current_user)
        for method in all_methods:
            available_methods.append(method["method"])

        # Calculate grace period if applicable
        grace_period_remaining = None
        if enforcement_level.value == "mandatory" and not configured_methods:
            # Check when user was created/last notified
            created_date = current_user.created_at
            grace_period_days = 7  # 7-day grace period
            days_since_created = (datetime.utcnow() - created_date).days
            if days_since_created < grace_period_days:
                grace_period_remaining = grace_period_days - days_since_created

        message = f"MFA enforcement level: {enforcement_level.value}"
        if grace_period_remaining:
            message += f". You have {grace_period_remaining} days to configure MFA."

        return MFARequirementResponse(
            required=enforcement_level.value != "disabled",
            enforcement_level=enforcement_level.value,
            configured_methods=configured_methods,
            available_methods=available_methods,
            grace_period_remaining=grace_period_remaining,
            message=message,
        )

    except Exception as e:
        logger.error(f"Error checking MFA requirement: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to check MFA requirements",
        ) from e


@router.get("/methods", response_model=List[MFAMethodInfo])
async def get_available_methods(
    current_user: UserAuth = current_user_dependency, db: Session = db_dependency
) -> List[MFAMethodInfo]:
    """Get available MFA methods for current user."""
    mfa_manager = MFAManager(db)

    try:
        methods = mfa_manager.get_available_methods(current_user)
        method_infos = []

        for method in methods:
            # Add additional information
            info = MFAMethodInfo(**method)

            # Add last used information
            if current_user.mfa_config:
                last_used = getattr(
                    current_user.mfa_config, f"{method['method']}_last_used", None
                )
                if last_used:
                    info.last_used = last_used.isoformat()

            method_infos.append(info)

        return method_infos

    except Exception as e:
        logger.error(f"Error getting MFA methods: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve MFA methods",
        )


@router.post("/totp/setup", response_model=TOTPSetupResponse)
@rate_limiter.limit("5/minute")
async def setup_totp(
    request: Request,
    current_user: UserAuth = current_user_dependency,
    db: Session = db_dependency,
) -> TOTPSetupResponse:
    """Generate TOTP secret and setup instructions."""
    mfa_manager = MFAManager(db)
    totp_manager = get_totp_manager()

    try:
        # Generate secret and provisioning URI
        secret, provisioning_uri = mfa_manager.generate_totp_secret(current_user)

        # Generate QR code
        qr_code_bytes = totp_manager.generate_qr_code(provisioning_uri)
        qr_code_base64 = base64.b64encode(qr_code_bytes).decode("utf-8")

        # Create secure session for setup
        session_data = {
            "secret": secret,
            "provisioning_uri": provisioning_uri,
            "qr_code": qr_code_base64,
        }
        session_id = await session_manager.create_setup_session(
            str(current_user.id), "totp", session_data  # type: ignore[arg-type]
        )

        # Audit log
        await audit_service.log_event(
            event_type="mfa_setup_initiated",
            user_id=str(current_user.id),
            details={"method": "totp"},
            ip_address=request.client.host if request.client else "",
        )

        return TOTPSetupResponse(
            session_id=session_id,
            provisioning_uri=provisioning_uri,
            qr_code=f"data:image/png;base64,{qr_code_base64}",
            manual_entry_key=secret,
            algorithm="SHA1",
            digits=6,
            period=30,
        )

    except Exception as e:
        logger.error(f"TOTP setup error for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to setup TOTP",
        )


@router.post("/totp/verify")
@rate_limiter.limit("10/minute")
async def verify_totp_setup(
    request: MFAVerifyRequest,
    req: Request,
    current_user: UserAuth = current_user_dependency,
    db: Session = db_dependency,
) -> Dict[str, Any]:
    """Verify TOTP setup with user-provided code."""
    if request.method != MFAMethod.TOTP.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid method for TOTP verification",
        )

    mfa_manager = MFAManager(db)

    try:
        # Get session data if provided
        session_data = None
        if request.session_id:
            session_data = await session_manager.get_setup_session(request.session_id)
            if not session_data or session_data["user_id"] != current_user.id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid or expired session",
                )

        success = mfa_manager.verify_totp_setup(current_user, request.code)

        if success:
            # Clean up session
            if request.session_id:
                await session_manager.delete_setup_session(request.session_id)

            # Audit log
            await audit_service.log_event(
                event_type="mfa_setup_completed",
                user_id=str(current_user.id),
                details={"method": "totp"},
                ip_address=req.client.host if req.client else "",
            )

            return {
                "success": True,
                "message": "TOTP successfully configured. Please store your secret key securely.",
            }
        else:
            return {"success": False, "message": "Invalid code. Please try again."}

    except InvalidMFACodeException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"TOTP verification error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Verification failed",
        )


@router.post("/sms/setup")
@rate_limiter.limit("3/minute")
async def setup_sms(
    request: SMSSetupRequest,
    req: Request,
    current_user: UserAuth = current_user_dependency,
    db: Session = db_dependency,
) -> Dict[str, Any]:
    """Initiate SMS verification."""
    mfa_manager = MFAManager(db)

    try:
        # Validate phone number
        phone_number = request.phone_number
        if not phone_number:
            # Use account phone number
            if not current_user.phone_number:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="No phone number available. Please provide a phone number.",
                )
            phone_number = str(current_user.phone_number)

        # Initiate SMS verification
        masked_phone = mfa_manager.initiate_sms_verification(current_user, phone_number)

        # Create session for verification
        session_data = {
            "phone_number": phone_number,
            "masked_phone": masked_phone,
            "attempts": 0,
        }
        session_id = await session_manager.create_setup_session(
            str(current_user.id), "sms", session_data  # type: ignore[arg-type]
        )

        # Audit log
        await audit_service.log_event(
            event_type="mfa_sms_setup_initiated",
            user_id=str(current_user.id),
            details={"masked_phone": masked_phone},
            ip_address=req.client.host if req.client else "",
        )

        return {
            "success": True,
            "message": f"Verification code sent to {masked_phone}",
            "phone": masked_phone,
            "session_id": session_id,
            "expires_in": 300,  # 5 minutes
        }

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"SMS setup error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send SMS",
        )


@router.post("/sms/verify")
@rate_limiter.limit("10/minute")
async def verify_sms_setup(
    request: MFAVerifyRequest,
    req: Request,
    current_user: UserAuth = current_user_dependency,
    db: Session = db_dependency,
) -> Dict[str, Any]:
    """Verify SMS setup with code."""
    if request.method != MFAMethod.SMS.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid method for SMS verification",
        )

    mfa_manager = MFAManager(db)

    try:
        # Get session data
        if not request.session_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Session ID required for SMS verification",
            )

        session_data = await session_manager.get_setup_session(request.session_id)
        if not session_data or session_data["user_id"] != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired session",
            )

        # Check attempts
        if session_data.get("attempts", 0) >= 5:
            await session_manager.delete_setup_session(request.session_id)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many attempts. Please start over.",
            )

        # Verify code
        success = mfa_manager.verify_sms_code(current_user, request.code)

        if success:
            # Clean up session
            await session_manager.delete_setup_session(request.session_id)

            # Audit log
            await audit_service.log_event(
                event_type="mfa_sms_setup_completed",
                user_id=str(current_user.id),
                details={"phone": session_data["masked_phone"]},
                ip_address=req.client.host if req.client else "",
            )

            return {
                "success": True,
                "message": "SMS verification successfully configured",
            }
        else:
            # Increment attempts
            session_data["attempts"] = session_data.get("attempts", 0) + 1
            await session_manager.create_setup_session(
                str(current_user.id), "sms", session_data  # type: ignore[arg-type]
            )

            return {
                "success": False,
                "message": "Invalid code. Please try again.",
                "attempts_remaining": 5 - session_data["attempts"],
            }

    except Exception as e:
        logger.error(f"SMS verification error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Verification failed",
        )


@router.post("/backup-codes/generate", response_model=BackupCodesResponse)
@rate_limiter.limit("2/hour")
async def generate_backup_codes(
    req: Request,
    current_user: UserAuth = current_user_dependency,
    db: Session = db_dependency,
) -> BackupCodesResponse:
    """Generate new backup codes."""
    mfa_manager = MFAManager(db)

    try:
        # Check if user has at least one other MFA method enabled
        if not current_user.mfa_config or not current_user.mfa_config.enabled_methods:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Must have at least one MFA method enabled before generating backup codes",
            )

        codes = mfa_manager.generate_backup_codes(current_user)

        # Audit log
        await audit_service.log_event(
            event_type="mfa_backup_codes_generated",
            user_id=str(current_user.id),
            details={"count": len(codes)},
            ip_address=req.client.host if req.client else "",
        )

        return BackupCodesResponse(
            codes=codes,
            generated_at=datetime.utcnow().isoformat(),
            warning="Store these codes securely offline. Each code can only be used once.",
        )

    except Exception as e:
        logger.error(f"Backup code generation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate backup codes",
        )


@router.post("/verify")
@rate_limiter.limit("20/minute")
async def verify_mfa(
    request: MFAVerifyRequest,
    req: Request,
    response: Response,
    current_user: UserAuth = current_user_dependency,
    db: Session = db_dependency,
) -> Dict[str, Any]:
    """Verify MFA code during authentication."""
    mfa_manager = MFAManager(db)

    try:
        success = False
        method_used = request.method

        if request.method == MFAMethod.TOTP.value:
            success = mfa_manager.verify_totp(current_user, request.code)
        elif request.method == MFAMethod.SMS.value:
            success = mfa_manager.verify_sms_code(current_user, request.code)
        elif request.method == MFAMethod.BACKUP_CODE.value:
            success = mfa_manager.verify_backup_code(current_user, request.code)
            if success:
                # Backup codes are single use
                remaining = mfa_manager.get_remaining_backup_codes(current_user)  # type: ignore[attr-defined]
                if remaining == 0:
                    logger.warning(
                        f"User {current_user.id} has no backup codes remaining"
                    )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported MFA method: {request.method}",
            )

        if success:
            # Update last used timestamp
            if current_user.mfa_config:
                setattr(
                    current_user.mfa_config,
                    f"{method_used}_last_used",
                    datetime.utcnow(),
                )
                db.commit()

            # Generate MFA-verified token
            mfa_token = jwt_handler.create_access_token(
                {"user_id": str(current_user.id), "mfa_verified": True}
            )
            response.set_cookie(
                key="mfa_verified",
                value=mfa_token,
                max_age=3600,  # 1 hour
                httponly=True,
                secure=True,
                samesite="strict",
            )

            # Audit log
            await audit_service.log_event(
                event_type="mfa_verification_success",
                user_id=str(current_user.id),
                details={"method": method_used},
                ip_address=req.client.host if req.client else "",
            )

            return {"success": True, "method": method_used, "mfa_token": mfa_token}
        else:
            # Audit failed attempt
            await audit_service.log_event(
                event_type="mfa_verification_failed",
                user_id=str(current_user.id),
                details={"method": method_used},
                ip_address=req.client.host if req.client else "",
            )

            return {"success": False, "message": "Invalid code"}

    except (
        InvalidMFACodeException,
        MFAMethodNotEnabledException,
        TooManyAttemptsException,
    ) as e:
        logger.warning(f"MFA verification error for user {current_user.id}: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"MFA verification error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Verification failed",
        )


@router.get("/totp/qr-code/{session_id}")
async def get_totp_qr_code(
    session_id: str,
    current_user: UserAuth = current_user_dependency,
) -> StreamingResponse:
    """Get TOTP QR code as image file."""
    try:
        # Get session data
        session_data = await session_manager.get_setup_session(session_id)
        if not session_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found or expired",
            )

        # Verify session belongs to current user
        if session_data["user_id"] != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Access denied"
            )

        # Get QR code from session
        qr_code_base64 = session_data.get("qr_code")
        if not qr_code_base64:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="QR code not found"
            )

        # Decode QR code
        qr_code_bytes = base64.b64decode(qr_code_base64)

        return StreamingResponse(
            io.BytesIO(qr_code_bytes),
            media_type="image/png",
            headers={
                "Content-Disposition": "inline; filename=totp-qr.png",
                "Cache-Control": "no-store, no-cache, must-revalidate",
                "Pragma": "no-cache",
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving QR code: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve QR code",
        )


@router.get("/totp/instructions")
async def get_totp_instructions() -> Dict[str, Any]:
    """Get TOTP setup instructions."""
    totp_manager = get_totp_manager()
    instructions = totp_manager.get_setup_instructions()

    # Add app recommendations
    instructions["recommended_apps"] = {
        "ios": [
            {
                "name": "Microsoft Authenticator",
                "url": "https://apps.apple.com/app/id983156458",
            },
            {
                "name": "Google Authenticator",
                "url": "https://apps.apple.com/app/id388497605",
            },
            {"name": "Authy", "url": "https://apps.apple.com/app/id494168017"},
        ],
        "android": [
            {
                "name": "Microsoft Authenticator",
                "url": "https://play.google.com/store/apps/details?id=com.azure.authenticator",
            },
            {
                "name": "Google Authenticator",
                "url": "https://play.google.com/store/apps/details?id=com.google.android.apps.authenticator2",
            },
            {
                "name": "Authy",
                "url": "https://play.google.com/store/apps/details?id=com.authy.authy",
            },
        ],
    }

    instructions["security_tips"] = [
        "Never share your TOTP secret key with anyone",
        "Store backup codes in a secure location offline",
        "Enable TOTP on a device you control and trust",
        "Consider using a password manager that supports TOTP",
    ]

    return instructions


@router.post("/disable/{method}")
@rate_limiter.limit("5/hour")
async def disable_mfa_method(
    method: str,
    request: MFADisableRequest,
    req: Request,
    current_user: UserAuth = current_user_dependency,
    db: Session = db_dependency,
) -> Dict[str, Any]:
    """Disable a specific MFA method."""
    mfa_manager = MFAManager(db)

    try:
        # Verify password first
        pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

        if not pwd_context.verify(request.password, current_user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid password"
            )

        # Check if this would leave user without MFA when required
        if current_user.mfa_config:
            enabled_methods = current_user.mfa_config.enabled_methods
            if method in enabled_methods and len(enabled_methods) == 1:
                # Check if MFA is mandatory
                enforcement = mfa_manager.check_mfa_requirement(current_user)
                if enforcement.value == "mandatory":
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Cannot disable last MFA method when MFA is mandatory",
                    )

        # Disable the method
        success = mfa_manager.disable_mfa_method(current_user, method)  # type: ignore[attr-defined]

        if success:
            # Audit log
            await audit_service.log_event(
                event_type="mfa_method_disabled",
                user_id=str(current_user.id),
                details={
                    "method": method,
                    "reason": request.reason or "User requested",
                },
                ip_address=req.client.host if req.client else "",
            )

            return {
                "success": True,
                "message": f"{method.upper()} authentication disabled",
            }
        else:
            return {
                "success": False,
                "message": "Method was not enabled or could not be disabled",
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error disabling MFA method: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to disable MFA method",
        )


@router.post("/resend-sms")
@rate_limiter.limit("3/hour")
async def resend_sms_code(
    session_id: str,
    req: Request,
    current_user: UserAuth = current_user_dependency,
    db: Session = db_dependency,
) -> Dict[str, Any]:
    """Resend SMS verification code."""
    try:
        # Get session data
        session_data = await session_manager.get_setup_session(session_id)
        if not session_data or session_data["user_id"] != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired session",
            )

        # Check if method is SMS
        if session_data.get("method") != "sms":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid session type"
            )

        # Resend code
        phone_number = session_data.get("phone_number")
        if not phone_number:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Phone number not found in session",
            )

        # Generate new code
        code = "".join(secrets.choice("0123456789") for _ in range(6))

        # Send SMS using the correct method
        message_body = f"Your Haven Health verification code is: {code}"
        db = req.state.db  # Get DB session from request
        sms_service_instance = SMSService(db)
        await sms_service_instance.send_sms(phone_number, message_body)

        # Update session with new code (encrypted)
        session_data["resend_count"] = session_data.get("resend_count", 0) + 1
        await session_manager.create_setup_session(str(current_user.id), "sms", session_data)  # type: ignore[arg-type]

        # Audit log
        await audit_service.log_event(
            event_type="mfa_sms_code_resent",
            user_id=str(current_user.id),
            details={"masked_phone": session_data["masked_phone"]},
            ip_address=req.client.host if req.client else "",
        )

        return {
            "success": True,
            "message": f"New code sent to {session_data['masked_phone']}",
            "expires_in": 300,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error resending SMS code: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to resend code",
        )


@router.get("/status")
async def get_mfa_status(
    current_user: UserAuth = current_user_dependency, db: Session = db_dependency
) -> Dict[str, Any]:
    """Get comprehensive MFA status for current user."""
    try:
        mfa_config = current_user.mfa_config

        if not mfa_config:
            return {
                "enabled": False,
                "methods": [],
                "last_verified": None,
                "backup_codes_remaining": 0,
            }

        methods = []
        for method in mfa_config.enabled_methods:
            method_info = {"method": method, "enabled": True, "verified": True}

            # Add last used info
            last_used = getattr(mfa_config, f"{method}_last_used", None)
            if last_used:
                method_info["last_used"] = last_used.isoformat()

            # Add method-specific info
            if method == "sms" and mfa_config.sms_phone:
                method_info["phone"] = mfa_config.sms_phone
            elif method == "backup_code":
                method_info["remaining"] = (
                    len([c for c in mfa_config.backup_codes if not c.used])
                    if mfa_config.backup_codes
                    else 0
                )

            methods.append(method_info)

        return {
            "enabled": True,
            "methods": methods,
            "last_verified": (
                mfa_config.last_verified.isoformat()
                if mfa_config.last_verified
                else None
            ),
            "backup_codes_remaining": (
                len([c for c in mfa_config.backup_codes if not c.used])
                if mfa_config.backup_codes
                else 0
            ),
        }

    except Exception as e:
        logger.error(f"Error getting MFA status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get MFA status",
        )


# Initialize Redis connection on startup
@router.on_event("startup")
async def startup_event() -> None:
    """Initialize connections on startup."""
    await get_redis_client()
    logger.info("MFA endpoints initialized")


# Cleanup on shutdown
@router.on_event("shutdown")
async def shutdown_event() -> None:
    """Cleanup connections on shutdown."""
    if redis_client:
        await redis_client.close()
    logger.info("MFA endpoints shutdown")
