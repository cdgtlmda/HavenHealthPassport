"""Authentication REST API endpoints.

CRITICAL: This is a healthcare application handling refugee medical data.
Authentication must be secure and compliant with HIPAA requirements.
"""

import re
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field, validator
from sqlalchemy.orm import Session

from src.auth.jwt_handler import JWTHandler
from src.auth.mfa import MFAManager
from src.config import get_settings
from src.core.database import get_db
from src.models.auth import PasswordResetToken, UserAuth, UserSession
from src.security.encryption import EncryptionService
from src.services.audit_service import AuditService
from src.services.auth_service import AuthenticationService
from src.services.cache_service import cache_service
from src.services.device_tracking_service import DeviceTrackingService
from src.services.email_service import EmailService
from src.services.risk_based_auth_integration import RiskBasedAuthIntegration
from src.services.sms import SMSService
from src.services.token_blacklist_service import TokenBlacklistService
from src.utils.logging import get_logger
from src.utils.rate_limiter import RateLimiter

if TYPE_CHECKING:
    from pydantic import EmailStr
else:
    try:
        from pydantic import EmailStr
    except ImportError:
        EmailStr = str

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])
logger = get_logger(__name__)
security = HTTPBearer()
settings = get_settings()
rate_limiter = RateLimiter()
encryption_service = EncryptionService(kms_key_id="alias/haven-health-auth")

# Module-level dependency variables
db_dependency = Depends(get_db)
security_dependency = Depends(security)


# Dependency to get audit service instance
async def get_audit_service(db: Session = Depends(get_db)) -> AuditService:
    """Get audit service instance with database session."""
    return AuditService(db)


# Request/Response Models
class RegisterRequest(BaseModel):
    """User registration request."""

    email: str = Field(..., description="User email address")
    password: str = Field(..., min_length=12, description="Strong password required")
    patient_id: uuid.UUID = Field(..., description="Associated patient ID")
    phone_number: Optional[str] = Field(None, description="Phone for SMS verification")
    role: str = Field("patient", pattern="^(patient|provider|admin|aid_worker)$")
    language_preference: str = Field("en", description="Preferred language code")

    @validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        """Validate email format."""
        v = v.lower().strip()
        if "@" not in v or len(v) < 5:
            raise ValueError("Invalid email format")
        # Basic email regex
        email_regex = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        if not re.match(email_regex, v):
            raise ValueError("Invalid email format")
        return v

    @validator("password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        """Ensure password meets security requirements."""
        if len(v) < 12:
            raise ValueError("Password must be at least 12 characters")

        # Check complexity
        has_upper = any(c.isupper() for c in v)
        has_lower = any(c.islower() for c in v)
        has_digit = any(c.isdigit() for c in v)
        has_special = any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in v)

        if not all([has_upper, has_lower, has_digit, has_special]):
            raise ValueError(
                "Password must contain uppercase, lowercase, digit, and special character"
            )

        # Check for common patterns
        common_patterns = ["password", "12345", "qwerty", "admin", "user"]
        if any(pattern in v.lower() for pattern in common_patterns):
            raise ValueError("Password contains common patterns")

        return v


class RegisterResponse(BaseModel):
    """User registration response."""

    user_id: str  # Changed from uuid.UUID to str
    message: str
    verification_required: bool = True
    verification_method: str = "email"  # email or sms


class LoginRequest(BaseModel):
    """User login request."""

    email: str
    password: str
    mfa_code: Optional[str] = None
    device_fingerprint: Optional[str] = None
    remember_me: bool = False

    @validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        """Validate and normalize email."""
        return v.lower().strip()


class LoginResponse(BaseModel):
    """User login response."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: Dict[str, Any]
    mfa_required: bool = False
    mfa_session_token: Optional[str] = None


class MFALoginRequest(BaseModel):
    """MFA login completion request."""

    mfa_session_token: str
    mfa_code: str
    method: str = Field(..., pattern="^(totp|sms|backup_code)$")


class RefreshRequest(BaseModel):
    """Token refresh request."""

    refresh_token: str


class RefreshResponse(BaseModel):
    """Token refresh response."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class VerifyRequest(BaseModel):
    """Email/phone verification request."""

    type: str = Field(..., pattern="^(email|phone)$")
    token: str
    code: Optional[str] = None  # For SMS verification


class VerifyResponse(BaseModel):
    """Verification response."""

    verified: bool
    message: str
    next_step: Optional[str] = None


class ResendVerificationRequest(BaseModel):
    """Resend verification request."""

    identifier: str  # Email or phone
    type: str = Field("email", pattern="^(email|phone)$")


class ForgotPasswordRequest(BaseModel):
    """Forgot password request."""

    email: str

    @validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        """Validate email format."""
        return v.lower().strip()


class ResetPasswordRequest(BaseModel):
    """Reset password request."""

    token: str
    password: str = Field(..., min_length=12)

    @validator("password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        """Ensure password meets security requirements."""
        if len(v) < 12:
            raise ValueError("Password must be at least 12 characters")

        # Check complexity
        has_upper = any(c.isupper() for c in v)
        has_lower = any(c.islower() for c in v)
        has_digit = any(c.isdigit() for c in v)
        has_special = any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in v)

        if not all([has_upper, has_lower, has_digit, has_special]):
            raise ValueError(
                "Password must contain uppercase, lowercase, digit, and special character"
            )
        return v


class ChangePasswordRequest(BaseModel):
    """Change password request."""

    current_password: str
    new_password: str = Field(..., min_length=12)
    logout_other_sessions: bool = True

    @validator("new_password")
    @classmethod
    def validate_password_strength(cls, v: str, values: Dict[str, Any]) -> str:
        """Ensure password meets security requirements."""
        # Check it's different from current
        if "current_password" in values and v == values["current_password"]:
            raise ValueError("New password must be different from current password")

        if len(v) < 12:
            raise ValueError("Password must be at least 12 characters")

        # Check complexity
        has_upper = any(c.isupper() for c in v)
        has_lower = any(c.islower() for c in v)
        has_digit = any(c.isdigit() for c in v)
        has_special = any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in v)

        if not all([has_upper, has_lower, has_digit, has_special]):
            raise ValueError(
                "Password must contain uppercase, lowercase, digit, and special character"
            )
        return v


# Dependency for getting current user
async def get_current_user(
    credentials: HTTPAuthorizationCredentials = security_dependency,
    db: Session = db_dependency,
) -> UserAuth:
    """Get current authenticated user with comprehensive validation."""
    jwt_handler = JWTHandler()

    try:
        payload = jwt_handler.decode_token(credentials.credentials)
    except Exception as e:
        logger.warning(f"Token decode failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
        ) from e

    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token"
        )

    # Check if token is blacklisted
    blacklist_service = TokenBlacklistService(db)
    jti = payload.get("jti") or payload.get("sub")
    if jti and blacklist_service.is_token_blacklisted(jti):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has been revoked"
        )

    # Get user ID
    user_id = payload.get("user_id") or payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload"
        )

    # Get user from database
    auth_service = AuthenticationService(db)
    try:
        user = auth_service.get_by_id(uuid.UUID(user_id))
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid user ID format"
        ) from exc

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    # Check if user is active
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Account is deactivated"
        )

    # Check if user is verified (unless they're accessing verification endpoints)
    if not user.email_verified and not user.phone_verified:
        # Allow access to verification endpoints
        # allowed_paths = ["/verify", "/resend-verification", "/logout"]
        # This check would need request context - simplified here
        logger.warning(f"Unverified user {user.id} attempting access")

    return user


# Module-level dependency
current_user_dependency = Depends(get_current_user)


@router.post(
    "/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED
)
@rate_limiter.limit("5/hour")
async def register(
    request: RegisterRequest,
    req: Request,
    db: Session = db_dependency,
    audit_service: AuditService = Depends(get_audit_service),
) -> RegisterResponse:
    """Register a new user with comprehensive validation."""
    try:
        auth_service = AuthenticationService(db)

        # Check if email already exists
        existing = db.query(UserAuth).filter(UserAuth.email == request.email).first()
        if existing:
            # Don't reveal that email exists for security
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Registration failed. Please check your information.",
            )

        # Check if patient ID already has an account
        existing_patient = (
            db.query(UserAuth).filter(UserAuth.patient_id == request.patient_id).first()
        )
        if existing_patient:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This patient already has an account",
            )

        # Create user auth with strong security
        user_auth = auth_service.create_user_auth(
            patient_id=request.patient_id,
            email=request.email,
            password=request.password,
            phone_number=request.phone_number,
            role=request.role,
        )

        # Set language preference
        user_auth.language_preference = request.language_preference

        # Generate secure verification token
        verification_token = secrets.token_urlsafe(32)
        user_auth.email_verification_token = verification_token  # type: ignore[assignment]
        user_auth.email_verification_expires = datetime.utcnow() + timedelta(hours=24)

        db.commit()

        # Determine verification method
        verification_method = "email"
        if not request.email or "@" not in request.email:
            if request.phone_number:
                verification_method = "sms"

        # Send verification
        if verification_method == "email":
            email_service = EmailService()
            email_sent = email_service.send_verification_email(user_auth)

            if not email_sent:
                logger.warning(
                    f"Failed to send verification email to {user_auth.email}"
                )
                # Still continue with registration
        else:
            # Send SMS verification
            sms_service = SMSService(db)

            code = "".join(secrets.choice("0123456789") for _ in range(6))
            # Create SMS message
            message_body = f"Your Haven Health verification code is: {code}"
            sms_sent = await sms_service.send_sms(
                request.phone_number or "", message_body
            )

            if sms_sent:
                # Store code securely
                user_auth.phone_verification_code = auth_service.hash_password(code)  # type: ignore[assignment]
                user_auth.phone_verification_expires = datetime.utcnow() + timedelta(  # type: ignore[assignment]
                    minutes=10
                )
                db.commit()

        # Audit log
        await audit_service.log_event(
            event_type="user_registration",
            user_id=str(user_auth.id),
            details={
                "email": user_auth.email,
                "role": user_auth.role,
                "verification_method": verification_method,
            },
            ip_address=req.client.host if req.client else None,  # type: ignore[arg-type]
        )

        return RegisterResponse(
            user_id=str(user_auth.id),
            message=f"Registration successful. Please verify your {verification_method}.",
            verification_required=True,
            verification_method=verification_method,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Registration error: {e}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration failed",
        ) from e


@router.post("/login", response_model=LoginResponse)
@rate_limiter.limit("20/minute")
async def login(
    request: LoginRequest,
    req: Request,
    response: Response,
    db: Session = db_dependency,
    audit_service: AuditService = Depends(get_audit_service),
) -> LoginResponse:
    """User login with risk-based authentication and MFA support."""
    try:
        # Initialize services
        auth_service = AuthenticationService(db)
        risk_integration = RiskBasedAuthIntegration(db)
        device_service = DeviceTrackingService(db)

        # Get user for risk assessment
        user = db.query(UserAuth).filter(UserAuth.email == request.email).first()

        if not user:
            # Don't reveal if user exists
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials"
            )

        # Perform risk assessment
        risk_result = await risk_integration.check_authentication_risk(
            req, request.email, user
        )

        # Check if login is allowed based on risk
        if not risk_result["auth_requirements"]["allow_login"]:
            logger.warning(f"Login blocked due to high risk: {request.email}")

            # Audit log
            await audit_service.log_event(
                event_type="login_blocked_high_risk",
                user_id=str(user.id),
                details={"risk_score": risk_result["risk_score"]},
                ip_address=req.client.host if req.client else None,  # type: ignore[arg-type]
            )

            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Login temporarily blocked due to security concerns. Please contact support.",
            )

        # Authenticate user
        auth_result = auth_service.authenticate_user(
            username=request.email, password=request.password
        )

        if not auth_result:
            # Log failed attempt
            await audit_service.log_event(
                event_type="login_failed",
                details={"email": request.email},
                ip_address=req.client.host if req.client else None,  # type: ignore[arg-type]
            )

            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials"
            )

        user_auth, session = auth_result

        # Check if MFA is required
        mfa_required = risk_result["auth_requirements"]["mfa_required"] or (
            user_auth.mfa_config and user_auth.mfa_config.enabled_methods
        )

        if mfa_required and not request.mfa_code:
            # Generate MFA session token
            mfa_session_token = secrets.token_urlsafe(32)

            # Store MFA session in cache
            await cache_service.set(
                f"mfa_session:{mfa_session_token}",
                {
                    "user_id": str(user_auth.id),
                    "session_id": str(session.id),
                    "risk_level": risk_result["risk_level"],
                    "expires": (datetime.utcnow() + timedelta(minutes=5)).isoformat(),
                },
                ttl=300,  # 5 minutes
            )

            # Return response indicating MFA required
            return LoginResponse(
                access_token="",
                refresh_token="",
                token_type="bearer",
                expires_in=0,
                user={
                    "id": str(user_auth.id),
                    "email": user_auth.email,
                    "role": user_auth.role,
                },
                mfa_required=True,
                mfa_session_token=mfa_session_token,
            )

        # Track device
        device_fingerprint = request.device_fingerprint or req.headers.get(
            "X-Device-Fingerprint"
        )
        if not device_fingerprint:
            device_fingerprint = device_service.generate_device_fingerprint(
                dict(req.headers)
            )

        device = await device_service.track_device(
            user_auth,
            device_fingerprint,
            req.client.host if req.client else None,  # type: ignore[arg-type]
            req.headers.get("User-Agent", ""),
            dict(req.headers),
        )

        # Update session with device ID
        session.device_id = device.id
        session.risk_level = risk_result["risk_level"]
        session.risk_score = risk_result["risk_score"]

        # Set session expiry based on remember_me
        if request.remember_me:
            session.expires_at = datetime.utcnow() + timedelta(days=30)  # type: ignore[assignment]
        else:
            session.expires_at = datetime.utcnow() + timedelta(hours=24)  # type: ignore[assignment]

        db.commit()

        # Set secure cookies
        if request.remember_me:
            max_age = 30 * 24 * 60 * 60  # 30 days
        else:
            max_age = None  # Session cookie

        response.set_cookie(
            key="refresh_token",
            value=str(session.refresh_token),
            max_age=max_age,
            httponly=True,
            secure=True,
            samesite="strict",
            path="/api/v1/auth/refresh",
        )

        # Audit successful login
        await audit_service.log_event(
            event_type="login_success",
            user_id=str(user_auth.id),
            details={
                "risk_level": risk_result["risk_level"],
                "device_id": str(device.id),
                "remember_me": request.remember_me,
            },
            ip_address=req.client.host if req.client else None,  # type: ignore[arg-type]
        )

        return LoginResponse(
            access_token=str(session.token),
            refresh_token=str(session.refresh_token),
            token_type="bearer",
            expires_in=settings.access_token_expire_minutes * 60,
            user={
                "id": str(user_auth.id),
                "email": user_auth.email,
                "role": user_auth.role,
                "risk_level": risk_result["risk_level"],
                "verified": user_auth.email_verified or user_auth.phone_verified,
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Login failed"
        ) from e


@router.post("/mfa/login", response_model=LoginResponse)
@rate_limiter.limit("10/minute")
async def mfa_login(
    request: MFALoginRequest,
    req: Request,
    response: Response,
    db: Session = db_dependency,
    audit_service: AuditService = Depends(get_audit_service),
) -> LoginResponse:
    """Complete login with MFA verification."""
    try:
        # Get MFA session from cache
        session_data = await cache_service.get(
            f"mfa_session:{request.mfa_session_token}"
        )

        if not session_data:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired MFA session",
            )

        # Check expiry
        expires = datetime.fromisoformat(session_data["expires"])
        if datetime.utcnow() > expires:
            await cache_service.delete(f"mfa_session:{request.mfa_session_token}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="MFA session expired"
            )

        # Get user and session
        user_id = uuid.UUID(session_data["user_id"])
        session_id = uuid.UUID(session_data["session_id"])

        user = db.query(UserAuth).filter(UserAuth.id == user_id).first()
        session = db.query(UserSession).filter(UserSession.id == session_id).first()

        if not user or not session:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session"
            )

        # Verify MFA code
        mfa_manager = MFAManager(db)

        if request.method == "totp":
            verified = mfa_manager.verify_totp(user, request.mfa_code)
        elif request.method == "sms":
            verified = mfa_manager.verify_sms_code(user, request.mfa_code)
        elif request.method == "backup_code":
            verified = mfa_manager.verify_backup_code(user, request.mfa_code)
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported MFA method: {request.method}",
            )

        if not verified:
            # Log failed attempt
            await audit_service.log_event(
                event_type="mfa_login_failed",
                user_id=str(user.id),
                details={"method": request.method},
                ip_address=req.client.host if req.client else None,  # type: ignore[arg-type]
            )

            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid MFA code"
            )

        # MFA verified - activate session
        session.mfa_verified = True
        session.mfa_verified_at = datetime.utcnow()
        db.commit()

        # Clean up MFA session
        await cache_service.delete(f"mfa_session:{request.mfa_session_token}")

        # Set secure cookie
        response.set_cookie(
            key="refresh_token",
            value=str(session.refresh_token),
            httponly=True,
            secure=True,
            samesite="strict",
            path="/api/v1/auth/refresh",
        )

        # Audit successful MFA login
        await audit_service.log_event(
            event_type="mfa_login_success",
            user_id=str(user.id),
            details={
                "method": request.method,
                "risk_level": session_data.get("risk_level", "unknown"),
            },
            ip_address=req.client.host if req.client else None,  # type: ignore[arg-type]
        )

        return LoginResponse(
            access_token=str(session.token),
            refresh_token=str(session.refresh_token),
            token_type="bearer",
            expires_in=settings.access_token_expire_minutes * 60,
            user={
                "id": str(user.id),
                "email": user.email,
                "role": user.role,
                "verified": True,
                "mfa_verified": True,
            },
            mfa_required=False,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"MFA login error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="MFA login failed"
        )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    req: Request,
    response: Response,
    credentials: HTTPAuthorizationCredentials = security_dependency,
    current_user: UserAuth = current_user_dependency,
    db: Session = db_dependency,
    audit_service: AuditService = Depends(get_audit_service),
) -> None:
    """User logout - comprehensive session termination."""
    try:
        # auth_service = AuthenticationService(db)  # TODO: Use for session cleanup
        blacklist_service = TokenBlacklistService(db)

        # Get the current token
        current_token = credentials.credentials

        # Decode token to get claims
        jwt_handler = JWTHandler()
        try:
            payload = jwt_handler.decode_token(current_token)
            jti = payload.get("jti", str(uuid.uuid4()))
            exp = payload.get("exp")

            if exp:
                expires_at = datetime.fromtimestamp(exp, tz=timezone.utc)

                # Add token to blacklist
                blacklist_service.blacklist_token(
                    token=current_token,
                    jti=jti,
                    user_id=str(current_user.id),
                    expires_at=expires_at,
                    reason="User logout",
                    blacklisted_by=str(current_user.id),
                )
        except Exception as e:
            logger.warning(f"Could not blacklist token during logout: {e}")

        # Find and invalidate all active sessions
        active_sessions = (
            db.query(UserSession)
            .filter(
                UserSession.user_id == current_user.id, UserSession.is_active.is_(True)
            )
            .all()
        )

        for session in active_sessions:
            session.is_active = False
            session.invalidated_at = datetime.utcnow()

            # Blacklist session tokens
            if session.access_token:
                try:
                    blacklist_service.blacklist_token(
                        token=session.access_token,
                        jti=f"session_{session.id}",
                        user_id=str(current_user.id),
                        expires_at=session.expires_at,
                        reason="Session logout",
                        blacklisted_by=str(current_user.id),
                    )
                except Exception as e:
                    logger.warning(f"Could not blacklist session token: {e}")

        db.commit()

        # Clear cookies
        response.delete_cookie(key="refresh_token", path="/api/v1/auth/refresh")
        response.delete_cookie(key="mfa_verified", path="/")

        # Audit log
        await audit_service.log_event(
            event_type="user_logout",
            user_id=str(current_user.id),
            details={"sessions_invalidated": len(active_sessions)},
            ip_address=req.client.host if req.client else None,  # type: ignore[arg-type]
        )

        logger.info(f"User {current_user.id} successfully logged out")

    except Exception as e:
        logger.error(f"Logout error for user {current_user.id}: {e}", exc_info=True)
        db.rollback()
        # Still return 204 to avoid leaking information


@router.post("/refresh", response_model=RefreshResponse)
@rate_limiter.limit("30/minute")
async def refresh_token(
    request: RefreshRequest,
    req: Request,
    response: Response,
    db: Session = db_dependency,
    audit_service: AuditService = Depends(get_audit_service),
) -> RefreshResponse:
    """Refresh access token with secure token rotation."""
    try:
        jwt_handler = JWTHandler()
        blacklist_service = TokenBlacklistService(db)

        # Verify refresh token
        try:
            payload = jwt_handler.decode_token(request.refresh_token)
        except Exception:  # e captured for debugging but not used
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token"
            )

        # Check if token is blacklisted
        jti = payload.get("jti", payload.get("sub"))
        if jti and blacklist_service.is_token_blacklisted(jti):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token has been revoked",
            )

        # Get user
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload"
            )

        # Find the session
        session = (
            db.query(UserSession)
            .filter(
                UserSession.user_id == user_id,
                UserSession.refresh_token == request.refresh_token,
                UserSession.is_active.is_(True),
            )
            .first()
        )

        if not session:
            # Possible token reuse attack
            logger.warning(f"Invalid refresh token reuse attempt for user {user_id}")

            # Invalidate all sessions for this user as a security measure
            db.query(UserSession).filter(UserSession.user_id == user_id).update(
                {"is_active": False}
            )
            db.commit()

            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token"
            )

        # Check session expiry
        if session.expires_at < datetime.utcnow():
            session.is_active = False
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired"
            )

        # Rotate tokens
        new_tokens = jwt_handler.rotate_refresh_token(request.refresh_token)

        # Blacklist old refresh token
        blacklist_service.blacklist_token(
            token=request.refresh_token,
            jti=jti or str(user_id),
            user_id=str(user_id),
            expires_at=datetime.fromtimestamp(payload.get("exp", 0), tz=timezone.utc),
            reason="Token rotation",
            blacklisted_by="system",
        )

        # Update session
        session.access_token = new_tokens["access_token"]
        session.refresh_token = new_tokens["refresh_token"]
        session.last_activity = datetime.utcnow()
        session.token_rotations = (session.token_rotations or 0) + 1
        db.commit()

        # Update cookie
        response.set_cookie(
            key="refresh_token",
            value=new_tokens["refresh_token"],
            httponly=True,
            secure=True,
            samesite="strict",
            path="/api/v1/auth/refresh",
        )

        # Audit log
        await audit_service.log_event(
            event_type="token_refresh",
            user_id=str(user_id),
            details={"rotation_count": session.token_rotations},
            ip_address=req.client.host if req.client else None,  # type: ignore[arg-type]
        )

        return RefreshResponse(
            access_token=new_tokens["access_token"],
            refresh_token=new_tokens["refresh_token"],
            token_type="bearer",
            expires_in=settings.access_token_expire_minutes * 60,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Token refresh error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Token refresh failed",
        )


@router.post("/verify", response_model=VerifyResponse)
@rate_limiter.limit("10/minute")
async def verify_email_phone(
    request: VerifyRequest,
    req: Request,
    db: Session = db_dependency,
    audit_service: AuditService = Depends(get_audit_service),
) -> VerifyResponse:
    """Verify email or phone number."""
    try:
        if request.type == "email":
            # Find user by verification token
            user = (
                db.query(UserAuth)
                .filter(UserAuth.email_verification_token == request.token)
                .first()
            )

            if not user:
                return VerifyResponse(
                    verified=False, message="Invalid verification token"
                )

            # Check token expiry
            if user.email_verification_expires < datetime.utcnow():
                return VerifyResponse(
                    verified=False,
                    message="Verification token expired",
                    next_step="resend",
                )

            # Mark as verified
            user.email_verified = True
            user.email_verified_at = datetime.utcnow()
            user.email_verification_token = None
            user.email_verification_expires = None

            # Also mark user as verified
            user.verified = True
            user.verified_at = datetime.utcnow()

            db.commit()

            # Audit log
            await audit_service.log_event(
                event_type="email_verified", user_id=str(user.id), ip_address=req.client.host if req.client else None  # type: ignore[arg-type]
            )

            return VerifyResponse(
                verified=True, message="Email verified successfully", next_step="login"
            )

        else:  # Phone verification
            if not request.code:
                return VerifyResponse(
                    verified=False, message="Verification code required"
                )

            # Find user by phone number in token (contains phone)
            # Token format: phone_number:timestamp:signature
            try:
                phone_number = request.token.split(":")[0]
            except (IndexError, ValueError, AttributeError):
                return VerifyResponse(
                    verified=False, message="Invalid verification token"
                )

            user = (
                db.query(UserAuth).filter(UserAuth.phone_number == phone_number).first()
            )

            if not user:
                return VerifyResponse(verified=False, message="Invalid phone number")

            # Check code expiry
            if (
                user.phone_verification_expires
                and user.phone_verification_expires < datetime.utcnow()
            ):
                return VerifyResponse(
                    verified=False,
                    message="Verification code expired",
                    next_step="resend",
                )

            # Verify code
            auth_service = AuthenticationService(db)
            if not auth_service.verify_password(
                request.code, user.phone_verification_code
            ):
                return VerifyResponse(
                    verified=False, message="Invalid verification code"
                )

            # Mark as verified
            user.phone_verified = True
            user.phone_verified_at = datetime.utcnow()
            user.phone_verification_code = None
            user.phone_verification_expires = None

            # Also mark user as verified if no email
            if not user.email:
                user.verified = True
                user.verified_at = datetime.utcnow()

            db.commit()

            # Audit log
            await audit_service.log_event(
                event_type="phone_verified", user_id=str(user.id), ip_address=req.client.host if req.client else None  # type: ignore[arg-type]
            )

            return VerifyResponse(
                verified=True,
                message="Phone number verified successfully",
                next_step="login",
            )

    except Exception as e:
        logger.error(f"Verification error: {e}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Verification failed",
        )


@router.post("/resend-verification")
@rate_limiter.limit("3/hour")
async def resend_verification(
    request: ResendVerificationRequest,
    req: Request,
    db: Session = db_dependency,
    audit_service: AuditService = Depends(get_audit_service),
) -> Dict[str, str]:
    """Resend verification email or SMS."""
    try:
        # Find user
        if request.type == "email":
            user = (
                db.query(UserAuth).filter(UserAuth.email == request.identifier).first()
            )
        else:
            user = (
                db.query(UserAuth)
                .filter(UserAuth.phone_number == request.identifier)
                .first()
            )

        if not user:
            # Don't reveal if user exists
            return {
                "message": f"If the {request.type} exists and is unverified, a new verification has been sent."
            }

        # Check if already verified
        if request.type == "email" and user.email_verified:
            return {"message": "Email is already verified."}
        elif request.type == "phone" and user.phone_verified:
            return {"message": "Phone number is already verified."}

        # Send verification
        if request.type == "email":
            # Generate new token
            verification_token = secrets.token_urlsafe(32)
            user.email_verification_token = verification_token
            user.email_verification_expires = datetime.utcnow() + timedelta(hours=24)
            db.commit()

            # Send email
            email_service = EmailService()
            email_service.send_verification_email(user)

            message = "Verification email has been resent. Please check your inbox."
        else:
            # Generate new SMS code
            code = "".join(secrets.choice("0123456789") for _ in range(6))
            auth_service = AuthenticationService(db)
            user.phone_verification_code = auth_service.hash_password(code)
            user.phone_verification_expires = datetime.utcnow() + timedelta(minutes=10)
            db.commit()

            # Send SMS
            sms_service = SMSService(db)

            # Create SMS message
            message_body = f"Your Haven Health verification code is: {code}"
            await sms_service.send_sms(user.phone_number or "", message_body)

            message = "Verification code has been sent to your phone."

        # Audit log
        await audit_service.log_event(
            event_type=f"{request.type}_verification_resent",
            user_id=str(user.id),
            ip_address=req.client.host if req.client else None,  # type: ignore[arg-type]
        )

        return {"message": message}

    except Exception as e:
        logger.error(f"Resend verification error: {e}")
        db.rollback()
        return {
            "message": f"If the {request.type} exists and is unverified, a new verification has been sent."
        }


@router.post("/forgot-password", status_code=status.HTTP_202_ACCEPTED)
@rate_limiter.limit("5/hour")
async def forgot_password(
    request: ForgotPasswordRequest,
    req: Request,
    db: Session = db_dependency,
    audit_service: AuditService = Depends(get_audit_service),
) -> Dict[str, str]:
    """Request password reset - always returns success for security."""
    try:
        # Find user
        user = db.query(UserAuth).filter(UserAuth.email == request.email).first()

        if user:
            # Generate reset token
            reset_token = secrets.token_urlsafe(32)
            expires = datetime.utcnow() + timedelta(hours=1)

            # Store reset token
            password_reset = PasswordResetToken(
                user_id=str(user.id),
                token=reset_token,
                expires_at=expires,
                ip_address=req.client.host if req.client else None,
                user_agent=req.headers.get("User-Agent", ""),
            )
            db.add(password_reset)
            db.commit()

            # Send reset email
            email_service = EmailService()
            # Send password reset email
            reset_link = f"{settings.frontend_url}/reset-password?token={reset_token}"
            await email_service.send_email(
                to_email=user.email,
                subject="Password Reset Request",
                body=f'<p>Click the following link to reset your password:</p><p><a href="{reset_link}">Reset Password</a></p><p>This link will expire in 1 hour.</p>',
            )

            # Audit log
            await audit_service.log_event(
                event_type="password_reset_requested",
                user_id=str(user.id),
                ip_address=req.client.host if req.client else None,  # type: ignore[arg-type]
            )

        # Always return same message for security
        return {"message": "If the email exists, a password reset link has been sent."}

    except Exception as e:
        logger.error(f"Forgot password error: {e}")
        # Still return success message for security
        return {"message": "If the email exists, a password reset link has been sent."}


@router.post("/reset-password")
@rate_limiter.limit("10/hour")
async def reset_password(
    request: ResetPasswordRequest,
    req: Request,
    db: Session = db_dependency,
    audit_service: AuditService = Depends(get_audit_service),
) -> Dict[str, str]:
    """Reset password using token."""
    try:
        # Find reset token
        reset_token = (
            db.query(PasswordResetToken)
            .filter(
                PasswordResetToken.token == request.token,
                PasswordResetToken.used.is_(False),
            )
            .first()
        )

        if not reset_token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired token",
            )

        # Check expiry
        if reset_token.expires_at < datetime.utcnow():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Reset token has expired",
            )

        # Get user
        user = db.query(UserAuth).filter(UserAuth.id == reset_token.user_id).first()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid token",
            )

        # Update password
        auth_service = AuthenticationService(db)
        user.password_hash = auth_service.hash_password(request.password)
        user.password_changed_at = datetime.utcnow()

        # Mark token as used
        reset_token.used = True
        reset_token.used_at = datetime.utcnow()
        reset_token.used_ip = req.client.host if req.client else None

        # Invalidate all sessions
        db.query(UserSession).filter(UserSession.user_id == user.id).update(
            {"is_active": False}
        )

        db.commit()

        # Send confirmation email
        email_service = EmailService()
        # Send password changed notification
        await email_service.send_email(
            to_email=user.email,
            subject="Password Changed Successfully",
            body="<p>Your password has been successfully changed. If you did not make this change, please contact support immediately.</p>",
        )

        # Audit log
        await audit_service.log_event(
            event_type="password_reset_completed",
            user_id=str(user.id),
            ip_address=req.client.host if req.client else None,  # type: ignore[arg-type]
        )

        return {
            "message": "Password reset successful. Please login with your new password."
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Password reset error: {e}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Password reset failed",
        )


@router.post("/change-password")
async def change_password(
    request: ChangePasswordRequest,
    req: Request,
    current_user: UserAuth = current_user_dependency,
    db: Session = db_dependency,
    audit_service: AuditService = Depends(get_audit_service),
) -> Dict[str, str]:
    """Change current user password."""
    try:
        auth_service = AuthenticationService(db)

        # Verify current password
        if not auth_service.verify_password(
            request.current_password, current_user.password_hash  # type: ignore[arg-type]
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current password is incorrect",
            )

        # Update password
        current_user.password_hash = auth_service.hash_password(request.new_password)  # type: ignore[assignment]
        current_user.password_changed_at = datetime.utcnow()  # type: ignore[assignment]

        # Invalidate other sessions if requested
        if request.logout_other_sessions:
            # Get current session token to preserve it
            current_token = req.headers.get("Authorization", "").replace("Bearer ", "")

            sessions = (
                db.query(UserSession)
                .filter(
                    UserSession.user_id == current_user.id,
                    UserSession.is_active.is_(True),
                )
                .all()
            )

            for session in sessions:
                if session.access_token != current_token:
                    session.is_active = False
                    session.invalidated_at = datetime.utcnow()

        db.commit()

        # Send notification email
        email_service = EmailService()
        await email_service.send_password_changed_email_async(current_user)

        # Audit log
        await audit_service.log_event(
            event_type="password_changed",
            user_id=str(current_user.id),
            details={"logout_others": request.logout_other_sessions},
            ip_address=req.client.host if req.client else None,  # type: ignore[arg-type]
        )

        return {"message": "Password changed successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Change password error: {e}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Password change failed",
        )


@router.get("/me")
async def get_current_user_info(
    current_user: UserAuth = current_user_dependency, db: Session = db_dependency
) -> Dict[str, Any]:
    """Get current user information."""
    try:
        # Get additional user info
        mfa_enabled = bool(
            current_user.mfa_config and current_user.mfa_config.enabled_methods
        )

        # Get active sessions count
        active_sessions = (
            db.query(UserSession)
            .filter(
                UserSession.user_id == current_user.id, UserSession.is_active.is_(True)
            )
            .count()
        )

        return {
            "id": str(current_user.id),
            "email": current_user.email,
            "phone_number": current_user.phone_number,
            "role": current_user.role,
            "verified": current_user.email_verified or current_user.phone_verified,
            "email_verified": current_user.email_verified,
            "phone_verified": current_user.phone_verified,
            "mfa_enabled": mfa_enabled,
            "language_preference": current_user.language_preference,
            "created_at": current_user.created_at.isoformat(),
            "last_login": (
                current_user.last_login.isoformat() if current_user.last_login else None
            ),
            "active_sessions": active_sessions,
        }

    except Exception as e:
        logger.error(f"Get user info error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get user information",
        )


@router.get("/sessions")
async def get_user_sessions(
    current_user: UserAuth = current_user_dependency, db: Session = db_dependency
) -> List[Dict[str, Any]]:
    """Get all active sessions for current user."""
    try:
        sessions = (
            db.query(UserSession)
            .filter(
                UserSession.user_id == current_user.id, UserSession.is_active.is_(True)
            )
            .order_by(UserSession.created_at.desc())
            .all()
        )

        return [
            {
                "id": str(session.id),
                "device_id": str(session.device_id) if session.device_id else None,
                "ip_address": session.ip_address,
                "user_agent": session.user_agent,
                "created_at": session.created_at.isoformat(),
                "last_activity": session.last_activity.isoformat(),
                "expires_at": session.expires_at.isoformat(),
                "mfa_verified": session.mfa_verified,
                "risk_level": session.risk_level,
            }
            for session in sessions
        ]

    except Exception as e:
        logger.error(f"Get sessions error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get sessions",
        )


@router.delete("/sessions/{session_id}")
async def revoke_session(
    session_id: uuid.UUID,
    req: Request,
    current_user: UserAuth = current_user_dependency,
    db: Session = db_dependency,
    audit_service: AuditService = Depends(get_audit_service),
) -> Dict[str, str]:
    """Revoke a specific session."""
    try:
        session = (
            db.query(UserSession)
            .filter(
                UserSession.id == session_id, UserSession.user_id == current_user.id
            )
            .first()
        )

        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Session not found"
            )

        # Invalidate session
        session.is_active = False
        session.invalidated_at = datetime.utcnow()

        # Blacklist tokens
        blacklist_service = TokenBlacklistService(db)
        if session.access_token:
            blacklist_service.blacklist_token(
                token=session.access_token,
                jti=f"session_{session.id}",
                user_id=str(current_user.id),
                expires_at=session.expires_at,
                reason="Session revoked by user",
                blacklisted_by=str(current_user.id),
            )

        db.commit()

        # Audit log
        await audit_service.log_event(
            event_type="session_revoked",
            user_id=str(current_user.id),
            details={"session_id": str(session_id)},
            ip_address=req.client.host if req.client else None,  # type: ignore[arg-type]
        )

        return {"message": "Session revoked successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Revoke session error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to revoke session",
        )
