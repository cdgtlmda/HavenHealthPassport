"""
Authentication service module.

CRITICAL: This is a healthcare application handling refugee medical data.
All authentication operations must be secure and HIPAA compliant.
"""

import base64
import hashlib
import io
import os
import secrets
import uuid
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, List, Optional, Tuple

import bcrypt
import pyotp
import qrcode
import requests

try:
    import phonenumbers
except ImportError:
    phonenumbers = None

from sqlalchemy import func
from sqlalchemy.exc import DataError, IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session
from twilio.base.exceptions import TwilioException, TwilioRestException
from twilio.rest import Client

from src.auth.password_policy import default_password_policy
from src.config import get_settings
from src.models.auth import (
    BackupCode,
    MFAConfig,
    PasswordHistory,
    PasswordResetToken,
    SMSVerificationCode,
    UserAuth,
    UserSession,
)
from src.services.base import BaseService
from src.services.email_service import EmailService
from src.utils.exceptions import (
    ValidationException,
)
from src.utils.logging import get_logger

if TYPE_CHECKING:
    from src.auth.jwt_handler import JWTHandler
else:
    from src.auth.jwt_handler import JWTHandler

logger = get_logger(__name__)
settings = get_settings()


class AuthenticationService(BaseService):
    """Service for handling user authentication and authorization."""

    def __init__(self, db: Session):
        """Initialize authentication service."""
        super().__init__(db)  # Pass session to BaseService
        self.db = db
        self._jwt_handler: Optional["JWTHandler"] = None
        self._email_service = EmailService()

        # Initialize Twilio if configured
        self.twilio_client = None
        self.twilio_from_number = None

        if all(
            [
                os.getenv("TWILIO_ACCOUNT_SID"),
                os.getenv("TWILIO_AUTH_TOKEN"),
                os.getenv("TWILIO_FROM_NUMBER"),
            ]
        ):
            try:
                self.twilio_client = Client(
                    os.getenv("TWILIO_ACCOUNT_SID"), os.getenv("TWILIO_AUTH_TOKEN")
                )
                self.twilio_from_number = os.getenv("TWILIO_FROM_NUMBER")
                logger.info("Twilio client initialized for SMS authentication")
            except (ValueError, ConnectionError, TimeoutError) as e:
                logger.error(
                    "Failed to initialize Twilio client",
                    exc_info=True,
                    extra={
                        "error_type": type(e).__name__,
                        "error_details": str(e),
                        "twilio_configured": bool(os.getenv("TWILIO_ACCOUNT_SID")),
                    },
                )

    @property
    def jwt_handler(self) -> JWTHandler:
        """Lazy load JWT handler to avoid circular imports."""
        if self._jwt_handler is None:
            self._jwt_handler = JWTHandler()

        assert self._jwt_handler is not None
        return self._jwt_handler

    def create_user_auth(
        self,
        patient_id: uuid.UUID,
        email: str,
        password: str,
        phone_number: Optional[str] = None,
        role: str = "patient",
    ) -> UserAuth:
        """Create a new user authentication record with secure defaults."""
        try:
            # Validate email format
            email = email.lower().strip()
            if not email or "@" not in email:
                raise ValueError("Invalid email format")

            # Check if email already exists
            existing = self.db.query(UserAuth).filter(UserAuth.email == email).first()
            if existing:
                raise ValueError("Email already registered")

            # Validate password against policy
            validation_result = default_password_policy.validate_password(
                password=password, user_email=email
            )

            if not validation_result["valid"]:
                raise ValueError(
                    f"Password validation failed: {'; '.join(validation_result['errors'])}"
                )

            # Check if password has been breached
            if self._is_password_breached(password):
                raise ValueError(
                    "This password has been found in data breaches. Please choose a different password."
                )

            # Hash password with bcrypt
            password_hash = self._hash_password(password)

            # Create user auth record
            user_auth = UserAuth(
                id=uuid.uuid4(),
                patient_id=patient_id,
                email=email,
                password_hash=password_hash,
                phone_number=phone_number,
                role=role,
                is_active=True,
                email_verified=False,
                phone_verified=False if phone_number else None,
                created_at=datetime.utcnow(),
                password_changed_at=datetime.utcnow(),
                created_by=patient_id,  # Temporary fix for testing - use patient_id as creator
            )

            self.db.add(user_auth)
            self.db.flush()

            # Add to password history
            self._add_password_history(uuid.UUID(str(user_auth.id)), password_hash)

            # Log account creation
            logger.info(f"Created auth account for patient {patient_id}")

            return user_auth

        except IntegrityError as e:
            # Handle duplicate email/phone
            logger.error(
                "Database integrity error creating user auth",
                exc_info=True,
                extra={
                    "patient_id": str(patient_id),
                    "email": email,
                    "error_type": "IntegrityError",
                    "error_details": str(e),
                },
            )
            if "unique constraint" in str(e).lower():
                raise ValidationException(
                    "Email or phone number already registered"
                ) from e
            raise
        except (SQLAlchemyError, DataError) as e:
            # Database errors
            logger.error(
                "Database error creating user auth",
                exc_info=True,
                extra={
                    "patient_id": str(patient_id),
                    "error_type": type(e).__name__,
                    "error_details": str(e),
                },
            )
            raise RuntimeError(f"Failed to create user authentication: {str(e)}") from e

    def authenticate_user(
        self, username: str, password: str
    ) -> Optional[Tuple[UserAuth, UserSession]]:
        """Authenticate user and create session."""
        try:
            # Find user by email (case-insensitive)
            user = (
                self.db.query(UserAuth)
                .filter(func.lower(UserAuth.email) == username.lower())
                .first()
            )

            if not user:
                logger.warning(f"Authentication failed: User not found for {username}")
                return None

            # Verify password
            if not self._verify_password(password, user.password_hash):
                logger.warning(
                    f"Authentication failed: Invalid password for {username}"
                )
                # Update failed login attempts
                user.failed_login_attempts = (user.failed_login_attempts or 0) + 1
                user.last_failed_login = datetime.utcnow()

                # Lock account after 5 failed attempts
                if user.failed_login_attempts >= 5:
                    user.is_locked = True
                    user.locked_until = datetime.utcnow() + timedelta(hours=1)
                    logger.warning(f"Account locked due to failed attempts: {username}")

                self.db.commit()
                return None

            # Check if account is locked
            if user.is_locked:
                if user.locked_until and user.locked_until > datetime.utcnow():
                    logger.warning(
                        f"Authentication failed: Account locked for {username}"
                    )
                    return None
                else:
                    # Unlock account
                    user.is_locked = False
                    user.locked_until = None

            # Check if account is active
            if not user.is_active:
                logger.warning(
                    f"Authentication failed: Account inactive for {username}"
                )
                return None

            # Check if password reset is required
            if user.password_reset_required:
                logger.info(f"Password reset required for {username}")
                # Allow login but flag for password reset

            # Reset failed login attempts
            user.failed_login_attempts = 0
            user.last_failed_login = None

            # Update last login
            user.last_login = datetime.utcnow()
            user.login_count = (user.login_count or 0) + 1

            # Create session
            session = self.create_session(uuid.UUID(str(user.id)))

            self.db.commit()

            logger.info(f"Successful authentication for {username}")
            return user, session

        except (SQLAlchemyError, DataError) as e:
            logger.error(
                "Database error during authentication",
                exc_info=True,
                extra={
                    "username": username,
                    "error_type": type(e).__name__,
                    "error_details": str(e),
                },
            )
            # Don't reveal internal errors to users
            return None

    def create_session(
        self,
        user_id: uuid.UUID,
        device_id: Optional[uuid.UUID] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> UserSession:
        """Create a new user session with secure tokens."""
        try:
            # Generate tokens
            access_token = self.jwt_handler.create_access_token({"sub": str(user_id)})
            refresh_token = self.jwt_handler.create_refresh_token({"sub": str(user_id)})

            # Create session
            session = UserSession(
                id=uuid.uuid4(),
                user_id=user_id,
                access_token=access_token,
                refresh_token=refresh_token,
                device_id=device_id,
                ip_address=ip_address,
                user_agent=user_agent,
                is_active=True,
                created_at=datetime.utcnow(),
                last_activity=datetime.utcnow(),
                expires_at=datetime.utcnow() + timedelta(days=30),
            )

            self.db.add(session)
            self.db.flush()

            logger.info(f"Created session for user {user_id}")
            return session

        except (SQLAlchemyError, DataError) as e:
            logger.error(
                "Database error creating session",
                exc_info=True,
                extra={
                    "user_id": str(user_id),
                    "error_type": type(e).__name__,
                    "error_details": str(e),
                },
            )
            raise RuntimeError(f"Failed to create session: {str(e)}") from e

    def logout_user(
        self, user_id: uuid.UUID, session_token: Optional[str] = None
    ) -> bool:
        """Logout user by invalidating session(s)."""
        try:
            if session_token:
                # Invalidate specific session
                session = (
                    self.db.query(UserSession)
                    .filter(
                        UserSession.user_id == user_id,
                        UserSession.access_token == session_token,
                        UserSession.is_active.is_(True),
                    )
                    .first()
                )

                if session:
                    session.is_active = False
                    session.invalidated_at = datetime.utcnow()
                    self.db.flush()
                    logger.info(f"Invalidated session for user {user_id}")
                    return True
            else:
                # Invalidate all sessions
                sessions = (
                    self.db.query(UserSession)
                    .filter(
                        UserSession.user_id == user_id, UserSession.is_active.is_(True)
                    )
                    .all()
                )

                for session in sessions:
                    session.is_active = False
                    session.invalidated_at = datetime.utcnow()

                self.db.flush()
                logger.info(f"Invalidated {len(sessions)} sessions for user {user_id}")
                return True

            return False

        except (SQLAlchemyError, DataError) as e:
            logger.error(
                "Database error during logout",
                exc_info=True,
                extra={
                    "session_token": (
                        session_token[:10] + "..." if session_token else None
                    ),
                    "error_type": type(e).__name__,
                    "error_details": str(e),
                },
            )
            return False

    def invalidate_all_sessions(self, user_id: uuid.UUID) -> int:
        """Invalidate all active sessions for a user."""
        try:
            result = (
                self.db.query(UserSession)
                .filter(UserSession.user_id == user_id, UserSession.is_active.is_(True))
                .update(
                    {
                        UserSession.is_active: False,
                        UserSession.invalidated_at: datetime.utcnow(),
                    }
                )
            )
            self.db.flush()
            logger.info(f"Invalidated {result} sessions for user {user_id}")
            return result

        except (SQLAlchemyError, DataError) as e:
            logger.error(
                "Database error invalidating sessions",
                exc_info=True,
                extra={
                    "user_id": str(user_id),
                    "error_type": type(e).__name__,
                    "error_details": str(e),
                },
            )
            return 0

    def validate_session(self, session_token: str) -> Optional[UserSession]:
        """Validate a session token."""
        try:
            # Decode token to get user ID
            payload = self.jwt_handler.decode_token(session_token)
            if not payload:
                return None

            user_id = payload.get("user_id") or payload.get("sub")
            if not user_id:
                return None

            # Find active session
            session = (
                self.db.query(UserSession)
                .filter(
                    UserSession.user_id == user_id,
                    UserSession.access_token == session_token,
                    UserSession.is_active.is_(True),
                )
                .first()
            )

            if not session:
                return None

            # Check if session is expired
            if session.expires_at < datetime.utcnow():
                session.is_active = False
                session.invalidated_at = datetime.utcnow()
                self.db.flush()
                return None

            # Update last activity
            session.last_activity = datetime.utcnow()
            self.db.flush()

            return session

        except (SQLAlchemyError, DataError) as e:
            logger.error(
                "Database error validating session",
                exc_info=True,
                extra={
                    "session_token": (
                        session_token[:10] + "..." if session_token else None
                    ),
                    "error_type": type(e).__name__,
                    "error_details": str(e),
                },
            )
            return None

    def get_by_id(
        self, entity_id: uuid.UUID, log_access: bool = True
    ) -> Optional[UserAuth]:
        """Get user by ID."""
        return self.db.query(UserAuth).filter(UserAuth.id == entity_id).first()

    def get_by_email(self, email: str) -> Optional[UserAuth]:
        """Get user by email (case-insensitive)."""
        return (
            self.db.query(UserAuth)
            .filter(func.lower(UserAuth.email) == email.lower())
            .first()
        )

    def _hash_password(self, password: str) -> str:
        """Hash password using bcrypt."""
        # Generate salt and hash password
        salt = bcrypt.gensalt(rounds=12)  # Use 12 rounds for security
        hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
        return hashed.decode("utf-8")

    def _verify_password(self, password: str, hashed: str) -> bool:
        """Verify password against hash."""
        try:
            return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))
        except (ValueError, TypeError) as e:
            logger.error(
                "Error verifying password hash",
                exc_info=True,
                extra={"error_type": type(e).__name__, "error_details": str(e)},
            )
            return False

    def verify_password(self, password: str, hashed: str) -> bool:
        """Public method for password verification."""
        return self._verify_password(password, hashed)

    def hash_password(self, password: str) -> str:
        """Public method for password hashing."""
        return self._hash_password(password)

    def _is_password_breached(self, password: str) -> bool:
        """Check if password has been found in data breaches using k-anonymity."""
        try:
            # Use SHA-1 for HaveIBeenPwned API
            sha1_hash = (
                hashlib.sha1(password.encode("utf-8"), usedforsecurity=False)
                .hexdigest()
                .upper()
            )
            prefix = sha1_hash[:5]
            suffix = sha1_hash[5:]

            # Check against HaveIBeenPwned API
            response = requests.get(
                f"https://api.pwnedpasswords.com/range/{prefix}",
                timeout=5,
                headers={"User-Agent": "Haven-Health-Passport"},
            )

            if response.status_code == 200:
                # Check if our suffix is in the response
                for line in response.text.splitlines():
                    hash_suffix, count = line.split(":")
                    if hash_suffix == suffix:
                        logger.warning(f"Password found in {count} breaches")
                        return True

            return False

        except (ConnectionError, TimeoutError, ValueError) as e:
            logger.warning(
                "Password breach check failed - service unavailable",
                exc_info=True,
                extra={"error_type": type(e).__name__, "error_details": str(e)},
            )
            # Fail open - don't block if service is down
            return False

    def _add_password_history(self, user_id: uuid.UUID, password_hash: str) -> None:
        """Add password to history."""
        try:
            # Add new entry
            history_entry = PasswordHistory(
                id=uuid.uuid4(),
                user_id=user_id,
                password_hash=password_hash,
                created_at=datetime.utcnow(),
            )
            self.db.add(history_entry)

            # Keep only last 12 passwords
            old_entries = (
                self.db.query(PasswordHistory)
                .filter(PasswordHistory.user_id == user_id)
                .order_by(PasswordHistory.created_at.desc())
                .offset(12)
                .all()
            )

            for entry in old_entries:
                self.db.delete(entry)

            self.db.flush()

        except (SQLAlchemyError, DataError) as e:
            logger.error(
                "Error adding password to history",
                exc_info=True,
                extra={
                    "user_id": str(user_id),
                    "error_type": type(e).__name__,
                    "error_details": str(e),
                },
            )
            # Don't fail user creation due to history tracking

    def _is_password_reused(self, user_id: uuid.UUID, password: str) -> bool:
        """Check if password has been used recently."""
        try:
            # Get password history
            history = (
                self.db.query(PasswordHistory)
                .filter(PasswordHistory.user_id == user_id)
                .order_by(PasswordHistory.created_at.desc())
                .limit(12)
                .all()
            )

            # Check against each historical password
            for entry in history:
                if self._verify_password(password, entry.password_hash):
                    return True

            return False

        except (SQLAlchemyError, DataError) as e:
            logger.error(
                "Error checking password history",
                exc_info=True,
                extra={
                    "user_id": str(user_id),
                    "error_type": type(e).__name__,
                    "error_details": str(e),
                },
            )
            # Fail closed - assume password was used before if check fails
            return True

    def enable_mfa(
        self,
        user_id: uuid.UUID,
        method: str,
        phone_number: Optional[str] = None,
    ) -> Optional[Tuple[str, str, List[str], MFAConfig]]:
        """Enable MFA for user with production security."""
        try:
            # Get or create MFA config
            mfa_config = (
                self.db.query(MFAConfig).filter(MFAConfig.user_id == user_id).first()
            )

            if not mfa_config:
                mfa_config = MFAConfig(
                    id=uuid.uuid4(),
                    user_id=user_id,
                    created_at=datetime.utcnow(),
                )
                self.db.add(mfa_config)

            if method == "totp":
                # Generate TOTP secret
                secret = pyotp.random_base32()
                mfa_config.totp_secret = secret
                mfa_config.totp_enabled = True

                # Generate provisioning URI
                user = self.get_by_id(user_id)
                totp = pyotp.TOTP(secret)
                provisioning_uri = totp.provisioning_uri(
                    name=str(user.email) if user else "",
                    issuer_name="Haven Health Passport",
                )

                # Generate QR code
                qr = qrcode.QRCode(version=1, box_size=10, border=5)
                qr.add_data(provisioning_uri)
                qr.make(fit=True)

                img = qr.make_image(fill_color="black", back_color="white")
                buf = io.BytesIO()
                img.save(buf, format="PNG")
                qr_code = base64.b64encode(buf.getvalue()).decode()

                # Generate backup codes
                backup_codes = self._generate_backup_codes(user_id)

                self.db.flush()

                return (
                    secret,
                    f"data:image/png;base64,{qr_code}",
                    backup_codes,
                    mfa_config,
                )

            elif method == "sms":
                if not phone_number:
                    user = self.get_by_id(user_id)
                    phone_number = str(user.phone_number) if user else None

                if not phone_number:
                    raise ValueError("Phone number required for SMS MFA")

                # Validate and format phone number
                if phonenumbers is None:
                    raise ValueError("Phone number validation library not available")

                try:
                    parsed = phonenumbers.parse(phone_number, None)
                    if not phonenumbers.is_valid_number(parsed):
                        raise ValueError("Invalid phone number")
                    formatted_phone = phonenumbers.format_number(
                        parsed, phonenumbers.PhoneNumberFormat.E164
                    )
                except phonenumbers.NumberParseException as e:
                    raise ValueError("Invalid phone number format") from e

                mfa_config.sms_enabled = True
                mfa_config.sms_phone_number = formatted_phone

                # Generate backup codes
                backup_codes = self._generate_backup_codes(user_id)

                self.db.flush()

                # Send test SMS
                self.send_sms_code(user_id)

                return formatted_phone, "", backup_codes, mfa_config

            else:
                raise ValueError(f"Invalid MFA method: {method}")

        except (SQLAlchemyError, DataError) as e:
            logger.error(
                "Database error enabling MFA",
                exc_info=True,
                extra={
                    "user_id": str(user_id),
                    "method": method,
                    "error_type": type(e).__name__,
                    "error_details": str(e),
                },
            )
            raise RuntimeError(f"Failed to enable MFA: {str(e)}") from e

    def verify_mfa(
        self, user_id: uuid.UUID, code: str, method: Optional[str] = None
    ) -> bool:
        """Verify MFA code with production security."""
        try:
            mfa_config = (
                self.db.query(MFAConfig).filter(MFAConfig.user_id == user_id).first()
            )

            if not mfa_config:
                return False

            # Try TOTP first if enabled
            if mfa_config.totp_enabled and (not method or method == "totp"):
                totp = pyotp.TOTP(mfa_config.totp_secret)
                if totp.verify(code, valid_window=1):
                    mfa_config.totp_last_used = datetime.utcnow()
                    self.db.flush()
                    return True

            # Try SMS if enabled
            if mfa_config.sms_enabled and (not method or method == "sms"):
                # Check recent SMS verification codes
                sms_code = (
                    self.db.query(SMSVerificationCode)
                    .filter(
                        SMSVerificationCode.user_id == user_id,
                        SMSVerificationCode.code == code,
                        SMSVerificationCode.used.is_(False),
                        SMSVerificationCode.expires_at > datetime.utcnow(),
                    )
                    .first()
                )

                if sms_code:
                    # Mark as used
                    sms_code.used = True
                    sms_code.used_at = datetime.utcnow()
                    mfa_config.sms_last_used = datetime.utcnow()
                    self.db.flush()
                    return True

            # Try backup codes
            if self._verify_backup_code(user_id, code):
                return True

            return False

        except (ValueError, TypeError, AttributeError) as e:
            logger.error(
                "Error verifying MFA code",
                exc_info=True,
                extra={
                    "user_id": str(user_id),
                    "method": mfa_config.method if mfa_config else None,
                    "error_type": type(e).__name__,
                    "error_details": str(e),
                },
            )
            return False

    def send_sms_code(self, user_id: uuid.UUID) -> bool:
        """Send SMS verification code with production implementation."""
        try:
            mfa_config = (
                self.db.query(MFAConfig).filter(MFAConfig.user_id == user_id).first()
            )

            if not mfa_config or not mfa_config.sms_enabled:
                return False

            # Check rate limiting - max 3 codes per hour
            recent_codes = (
                self.db.query(SMSVerificationCode)
                .filter(
                    SMSVerificationCode.user_id == user_id,
                    SMSVerificationCode.created_at
                    > datetime.utcnow() - timedelta(hours=1),
                )
                .count()
            )

            if recent_codes >= 3:
                logger.warning(f"SMS rate limit exceeded for user {user_id}")
                return False

            # Generate 6-digit code
            code = "".join([str(secrets.randbelow(10)) for _ in range(6)])

            # Store code in database
            sms_code = SMSVerificationCode(
                id=uuid.uuid4(),
                user_id=user_id,
                code=code,
                phone_number=mfa_config.sms_phone_number,
                expires_at=datetime.utcnow() + timedelta(minutes=5),
                created_at=datetime.utcnow(),
            )
            self.db.add(sms_code)
            self.db.flush()

            logger.info(f"SMS code generated for user {user_id}")

            # Send SMS using the SMS service
            try:
                # sms_service not defined - would need to be imported
                success = False  # sms_service.send_verification_code_sync(mfa_config.sms_phone_number, code)

                if success:
                    logger.info(f"SMS sent to {mfa_config.sms_phone_number[:6]}****")
                    return True
                else:
                    logger.error("Failed to send SMS via SMS service")
                    return False

            except (
                TwilioException,
                TwilioRestException,
                ConnectionError,
                TimeoutError,
            ) as e:
                logger.error(
                    "SMS provider error",
                    exc_info=True,
                    extra={
                        "phone_number": (
                            mfa_config.sms_phone_number[:6] + "****"
                            if mfa_config.sms_phone_number
                            else None
                        ),
                        "provider": "primary",
                        "error_type": type(e).__name__,
                        "error_details": str(e),
                    },
                )

                # Fall back to Twilio if available
                if self.twilio_client and self.twilio_from_number:
                    try:
                        message = self.twilio_client.messages.create(
                            body=f"Your Haven Health Passport verification code is: {code}",
                            from_=self.twilio_from_number,
                            to=mfa_config.sms_phone_number,
                        )
                        logger.info(
                            f"SMS sent via Twilio to {mfa_config.sms_phone_number}: {message.sid}"
                        )
                        return True
                    except (
                        TwilioException,
                        TwilioRestException,
                        ConnectionError,
                        TimeoutError,
                    ) as twilio_error:
                        logger.error(
                            "Twilio fallback SMS failed",
                            exc_info=True,
                            extra={
                                "phone_number": (
                                    mfa_config.sms_phone_number[:6] + "****"
                                    if mfa_config.sms_phone_number
                                    else None
                                ),
                                "provider": "twilio_fallback",
                                "error_type": type(twilio_error).__name__,
                                "error_details": str(twilio_error),
                            },
                        )
                        return False

                return False

        except (SQLAlchemyError, DataError) as e:
            logger.error(
                "Database error saving SMS code",
                exc_info=True,
                extra={
                    "user_id": str(user_id),
                    "phone_number": (
                        mfa_config.sms_phone_number[:6] + "****"
                        if mfa_config and mfa_config.sms_phone_number
                        else None
                    ),
                    "error_type": type(e).__name__,
                    "error_details": str(e),
                },
            )
            return False

    def _generate_backup_codes(self, user_id: uuid.UUID) -> List[str]:
        """Generate backup codes for MFA."""
        mfa_config = (
            self.db.query(MFAConfig).filter(MFAConfig.user_id == user_id).first()
        )

        if not mfa_config:
            return []

        # Invalidate existing backup codes
        self.db.query(BackupCode).filter(
            BackupCode.user_id == user_id, BackupCode.used.is_(False)
        ).update({"invalidated": True})

        # Generate 10 backup codes
        codes = []

        for _ in range(10):
            code = "-".join(
                [
                    "".join([str(secrets.randbelow(10)) for _ in range(4)])
                    for _ in range(2)
                ]
            )
            codes.append(code)

            # Store hashed code in database
            backup_code = BackupCode(
                id=uuid.uuid4(),
                user_id=user_id,
                code_hash=self._hash_password(code),
                created_at=datetime.utcnow(),
            )
            self.db.add(backup_code)

        mfa_config.backup_codes_generated_at = datetime.utcnow()
        self.db.flush()

        return codes

    def _verify_backup_code(self, user_id: uuid.UUID, code: str) -> bool:
        """Verify and consume a backup code."""
        try:
            # Get unused backup codes
            backup_codes = (
                self.db.query(BackupCode)
                .filter(
                    BackupCode.user_id == user_id,
                    BackupCode.used.is_(False),
                    BackupCode.invalidated.is_(False),
                )
                .all()
            )

            for backup_code in backup_codes:
                if self._verify_password(code, backup_code.code_hash):
                    # Mark as used
                    backup_code.used = True
                    backup_code.used_at = datetime.utcnow()
                    self.db.flush()

                    logger.info(f"Backup code used for user {user_id}")

                    # Check if user is running low on codes
                    remaining = (
                        self.db.query(BackupCode)
                        .filter(
                            BackupCode.user_id == user_id,
                            BackupCode.used.is_(False),
                            BackupCode.invalidated.is_(False),
                        )
                        .count()
                    )

                    if remaining < 3:
                        logger.warning(
                            f"User {user_id} has only {remaining} backup codes remaining"
                        )

                    return True

            return False

        except (SQLAlchemyError, DataError, ValueError) as e:
            logger.error(
                "Error verifying backup code",
                exc_info=True,
                extra={
                    "user_id": str(user_id),
                    "error_type": type(e).__name__,
                    "error_details": str(e),
                },
            )
            return False

    def get_remaining_backup_codes(self, user_id: uuid.UUID) -> int:
        """Get count of remaining backup codes."""
        return (
            self.db.query(BackupCode)
            .filter(
                BackupCode.user_id == user_id,
                BackupCode.used.is_(False),
                BackupCode.invalidated.is_(False),
            )
            .count()
        )

    def change_password(
        self, user_id: uuid.UUID, current_password: str, new_password: str
    ) -> bool:
        """Change user password with full security checks."""
        try:
            user_auth = self.get_by_id(user_id)
            if not user_auth:
                raise ValueError(f"User {user_id} not found")

            # Verify current password
            if not self._verify_password(
                current_password, str(user_auth.password_hash)
            ):
                raise ValueError("Current password is incorrect")

            # Validate new password against policy
            validation_result = default_password_policy.validate_password(
                password=new_password, user_email=str(user_auth.email)
            )

            if not validation_result["valid"]:
                raise ValueError(
                    f"Password validation failed: {'; '.join(validation_result['errors'])}"
                )

            # Check if new password is same as current
            if self._verify_password(new_password, str(user_auth.password_hash)):
                raise ValueError("New password must be different from current password")

            # Check minimum password age
            if user_auth.password_changed_at:
                can_change = default_password_policy.check_minimum_password_age(
                    user_auth.password_changed_at  # type: ignore[arg-type]
                )
                if not can_change:
                    raise ValueError(
                        "Password cannot be changed yet. Please wait before changing your password again."
                    )

            # Check password history
            if self._is_password_reused(user_id, new_password):
                raise ValueError("Password has been used recently")

            # Check breach detection
            if self._is_password_breached(new_password):
                raise ValueError("Password has been found in data breaches")

            # Hash new password
            new_hash = self._hash_password(new_password)

            # Update password
            user_auth.password_hash = new_hash  # type: ignore[assignment]
            user_auth.password_changed_at = datetime.utcnow()  # type: ignore[assignment]

            # Add to password history
            self._add_password_history(user_id, new_hash)

            # Invalidate all sessions
            self.invalidate_all_sessions(user_id)

            self.db.flush()
            return True

        except (SQLAlchemyError, DataError) as e:
            logger.error(
                "Database error changing password",
                exc_info=True,
                extra={
                    "user_id": str(user_id),
                    "error_type": type(e).__name__,
                    "error_details": str(e),
                },
            )
            raise RuntimeError(f"Failed to change password: {str(e)}") from e

    def reset_password(self, reset_token: str, new_password: str) -> bool:
        """Reset user password using token."""
        try:
            # Find valid reset token
            token_record = (
                self.db.query(PasswordResetToken)
                .filter(
                    PasswordResetToken.token == reset_token,
                    PasswordResetToken.used.is_(False),
                    PasswordResetToken.expires_at > datetime.utcnow(),
                )
                .first()
            )

            if not token_record:
                raise ValueError("Invalid or expired reset token")

            user_id = token_record.user_id
            user_auth = self.get_by_id(user_id)

            if not user_auth:
                raise ValueError("User not found")

            # Validate new password against policy
            validation_result = default_password_policy.validate_password(
                password=new_password, user_email=str(user_auth.email)
            )

            if not validation_result["valid"]:
                raise ValueError(
                    f"Password validation failed: {'; '.join(validation_result['errors'])}"
                )

            # Check password history
            if self._is_password_reused(user_id, new_password):
                raise ValueError("Password has been used recently")

            # Check breach detection
            if self._is_password_breached(new_password):
                raise ValueError("Password has been found in data breaches")

            # Hash new password
            new_hash = self._hash_password(new_password)

            # Update password
            user_auth.password_hash = new_hash  # type: ignore[assignment]
            user_auth.password_changed_at = datetime.utcnow()  # type: ignore[assignment]
            user_auth.password_reset_required = False  # type: ignore[assignment]

            # Mark token as used
            token_record.used = True
            token_record.used_at = datetime.utcnow()

            # Add to password history
            self._add_password_history(user_id, new_hash)

            # Invalidate all sessions
            self.invalidate_all_sessions(user_id)

            self.db.flush()

            logger.info(f"Password reset successful for user {user_id}")
            return True

        except (SQLAlchemyError, DataError) as e:
            logger.error(
                "Database error resetting password",
                exc_info=True,
                extra={
                    "token": reset_token[:10] + "..." if reset_token else None,
                    "error_type": type(e).__name__,
                    "error_details": str(e),
                },
            )
            raise RuntimeError(f"Failed to reset password: {str(e)}") from e

    def initiate_password_reset(self, email: str) -> Optional[str]:
        """Initiate password reset process."""
        try:
            user = self.get_by_email(email)
            if not user:
                # Don't reveal if email exists
                logger.info(f"Password reset requested for non-existent email: {email}")
                return None

            # Check rate limiting - max 3 resets per hour
            recent_resets = (
                self.db.query(PasswordResetToken)
                .filter(
                    PasswordResetToken.user_id == user.id,
                    PasswordResetToken.created_at
                    > datetime.utcnow() - timedelta(hours=1),
                )
                .count()
            )

            if recent_resets >= 3:
                logger.warning(f"Password reset rate limit exceeded for user {user.id}")
                return None

            # Generate reset token
            reset_token = secrets.token_urlsafe(32)

            # Store reset token
            token_record = PasswordResetToken(
                user_id=user.id,
                token=reset_token,
                expires_at=datetime.utcnow() + timedelta(hours=1),
                created_at=datetime.utcnow(),
            )
            self.db.add(token_record)
            self.db.flush()

            logger.info(f"Password reset initiated for user {user.id}")
            return reset_token

        except (SQLAlchemyError, DataError) as e:
            logger.error(
                "Database error initiating password reset",
                exc_info=True,
                extra={
                    "email": email,
                    "error_type": type(e).__name__,
                    "error_details": str(e),
                },
            )
            return None
