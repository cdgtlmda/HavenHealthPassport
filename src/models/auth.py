"""Authentication and authorization models.

This module defines database models for user authentication, sessions,
device tracking, MFA configuration, and login attempts. Handles FHIR
Patient Resource references for user authentication.
"""

from datetime import datetime, timezone
from enum import Enum as PyEnum
from typing import List, Optional
from uuid import UUID as PyUUID

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.healthcare.fhir_validator import FHIRValidator
from src.models.base import BaseModel
from src.models.db_types import ARRAY, UUID

# FHIR resource type for this module
__fhir_resource__ = "Patient"


class UserRole(PyEnum):
    """User role enumeration."""

    PATIENT = "patient"
    HEALTHCARE_PROVIDER = "healthcare_provider"
    NGO_WORKER = "ngo_worker"
    ADMIN = "admin"
    SUPER_ADMIN = "super_admin"


class UserAuth(BaseModel):
    """User authentication model."""

    __tablename__ = "user_auth"

    # Initialize FHIR validator
    _validator = FHIRValidator()

    # User identification
    patient_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patients.id"), unique=True, nullable=False
    )
    email = Column(String(255), unique=True, nullable=False, index=True)
    phone_number = Column(String(50), unique=True, index=True)

    # Authentication
    password_hash = Column(String(255), nullable=False)
    password_changed_at = Column(
        DateTime, nullable=False, default=datetime.now(timezone.utc)
    )
    password_reset_token = Column(String(255), unique=True)
    password_reset_expires = Column(DateTime)
    password_reset_required = Column(Boolean, default=False)

    # Role and permissions
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole), default=UserRole.PATIENT, nullable=False
    )
    custom_permissions = Column(JSON, default=list)  # Additional permissions

    # Account status
    is_active = Column(Boolean, default=True, nullable=False)
    is_locked = Column(Boolean, default=False)
    locked_at = Column(DateTime)
    locked_reason = Column(String(500))

    # Verification status
    email_verified = Column(Boolean, default=False)
    email_verified_at = Column(DateTime)
    email_verification_token = Column(String(255), unique=True)
    email_verification_sent_at = Column(DateTime)
    phone_verified = Column(Boolean, default=False)
    phone_verified_at = Column(DateTime)
    phone_verification_code = Column(String(10))
    phone_verification_expires = Column(DateTime)

    # Login tracking
    last_login_at = Column(DateTime)
    last_login_ip = Column(String(45))  # IPv4 or IPv6
    failed_login_attempts = Column(Integer, default=0)
    last_failed_login_at = Column(DateTime)

    # Metadata
    created_by: Mapped[PyUUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    notes = Column(Text)

    # Relationships
    patient = relationship("Patient", back_populates="auth")
    sessions = relationship(
        "UserSession", back_populates="user", cascade="all, delete-orphan"
    )
    devices = relationship(
        "DeviceInfo", back_populates="user", cascade="all, delete-orphan"
    )
    mfa_config = relationship(
        "MFAConfig", back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    password_history = relationship(
        "PasswordHistory", back_populates="user", cascade="all, delete-orphan"
    )
    login_attempts = relationship(
        "LoginAttempt", back_populates="user", cascade="all, delete-orphan"
    )
    biometric_templates = relationship(
        "BiometricTemplate", back_populates="user", cascade="all, delete-orphan"
    )
    webauthn_credentials = relationship(
        "WebAuthnCredential", back_populates="user", cascade="all, delete-orphan"
    )
    api_keys = relationship(
        "APIKey", back_populates="user", cascade="all, delete-orphan"
    )
    sms_logs = relationship(
        "SMSLog", back_populates="user", cascade="all, delete-orphan"
    )

    # Indexes
    __table_args__ = (
        Index("idx_auth_email_active", "email", "is_active"),
        Index("idx_auth_phone_active", "phone_number", "is_active"),
        Index("idx_auth_patient_id", "patient_id"),
    )

    def __repr__(self) -> str:
        """Return string representation."""
        return f"<UserAuth(id={self.id}, email={self.email}, role={self.role.value})>"

    @property
    def is_admin(self) -> bool:
        """Check if user has admin privileges."""
        return bool(self.role in [UserRole.ADMIN, UserRole.SUPER_ADMIN])

    @property
    def is_healthcare_provider(self) -> bool:
        """Check if user is a healthcare provider."""
        return bool(self.role == UserRole.HEALTHCARE_PROVIDER)

    def has_permission(self, permission: str) -> bool:
        """Check if user has a specific permission."""
        # Check role-based permissions
        role_permissions = self._get_role_permissions()
        if permission in role_permissions:
            return True

        # Check custom permissions
        return permission in (self.custom_permissions or [])

    def _get_role_permissions(self) -> List[str]:
        """Get permissions for user role."""
        # Define role-based permissions
        permissions_map = {
            UserRole.PATIENT: [
                "read:own_records",
                "update:own_profile",
                "grant:access",
                "revoke:access",
            ],
            UserRole.HEALTHCARE_PROVIDER: [
                "read:patient_records",
                "create:health_records",
                "update:health_records",
                "verify:records",
            ],
            UserRole.NGO_WORKER: [
                "read:patient_records",
                "create:patients",
                "update:patients",
                "create:verifications",
            ],
            UserRole.ADMIN: [
                "read:all",
                "create:all",
                "update:all",
                "delete:soft",
                "manage:users",
                "view:analytics",
            ],
            UserRole.SUPER_ADMIN: [
                "read:all",
                "create:all",
                "update:all",
                "delete:all",
                "manage:all",
                "system:all",
            ],
        }

        # Use role value since self.role is a Column
        role_value = (
            self.role if isinstance(self.role, UserRole) else UserRole(self.role)
        )
        return list(permissions_map.get(role_value, []))


class UserSession(BaseModel):
    """User session model."""

    __tablename__ = "user_sessions"

    # Session identification
    user_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user_auth.id"), nullable=False
    )
    token = Column(String(255), unique=True, nullable=False, index=True)
    refresh_token = Column(String(255), unique=True, index=True)

    # Session type and policy
    session_type = Column(String(50), default="web", nullable=False)
    timeout_policy = Column(String(50), default="sliding", nullable=False)

    # Device information
    device_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("device_info.id"), nullable=True
    )
    device_fingerprint = Column(String(255))
    ip_address = Column(String(45))
    user_agent = Column(String(500))

    # Session metadata
    created_at = Column(DateTime, default=datetime.now(timezone.utc), nullable=False)
    expires_at = Column(DateTime, nullable=False)
    absolute_expires_at = Column(DateTime)  # Absolute maximum lifetime
    last_activity_at = Column(DateTime, default=datetime.now(timezone.utc))
    is_active = Column(Boolean, default=True, nullable=False)
    invalidated_at = Column(DateTime)
    invalidation_reason = Column(String(255))

    # Additional metadata (JSON)
    session_metadata = Column(JSON, default=dict)

    # Relationships
    user = relationship("UserAuth", back_populates="sessions")
    device = relationship("DeviceInfo", back_populates="sessions")

    # Indexes
    __table_args__ = (
        Index("idx_session_user_active", "user_id", "is_active"),
        Index("idx_session_token_active", "token", "is_active"),
        Index("idx_session_expires", "expires_at"),
    )

    def __repr__(self) -> str:
        """Return string representation."""
        return f"<UserSession(id={self.id}, user_id={self.user_id}, active={self.is_active})>"

    @property
    def is_expired(self) -> bool:
        """Check if session has expired."""
        return bool(datetime.now(timezone.utc) > self.expires_at)

    @property
    def is_valid(self) -> bool:
        """Check if session is valid."""
        return bool(self.is_active and not self.is_expired)


class DeviceInfo(BaseModel):
    """Device information model."""

    __tablename__ = "device_info"

    # Device identification
    user_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user_auth.id"), nullable=False
    )
    device_fingerprint = Column(String(255), nullable=False, index=True)
    device_name = Column(String(255))
    device_type = Column(String(50))  # mobile, tablet, desktop, etc.

    # Device details
    platform = Column(String(50))  # iOS, Android, Windows, etc.
    platform_version = Column(String(50))
    browser = Column(String(50))
    browser_version = Column(String(50))

    # Network information
    ip_address = Column(String(45))
    user_agent = Column(String(500))

    # Trust status
    is_trusted = Column(Boolean, default=False)
    trusted_at = Column(DateTime)
    trust_expires_at = Column(DateTime)

    # Activity tracking
    first_seen_at = Column(DateTime, default=datetime.now(timezone.utc))
    last_seen_at = Column(DateTime, default=datetime.now(timezone.utc))
    login_count = Column(Integer, default=0)

    # Relationships
    user = relationship("UserAuth", back_populates="devices")
    sessions = relationship("UserSession", back_populates="device")

    # Indexes
    __table_args__ = (
        UniqueConstraint("user_id", "device_fingerprint", name="uq_user_device"),
        Index("idx_device_user_trusted", "user_id", "is_trusted"),
        Index("idx_device_fingerprint", "device_fingerprint"),
    )

    def __repr__(self) -> str:
        """Return string representation."""
        return f"<DeviceInfo(id={self.id}, device={self.device_name}, trusted={self.is_trusted})>"


class MFAConfig(BaseModel):
    """Multi-factor authentication configuration."""

    __tablename__ = "mfa_config"

    # User reference
    user_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user_auth.id"), unique=True, nullable=False
    )

    # TOTP configuration
    totp_enabled = Column(Boolean, default=False)
    totp_secret = Column(String(255))
    totp_verified = Column(Boolean, default=False)
    totp_verified_at = Column(DateTime)

    # SMS configuration
    sms_enabled = Column(Boolean, default=False)
    sms_phone_number = Column(String(50))
    sms_verified = Column(Boolean, default=False)
    sms_verified_at = Column(DateTime)

    # Email configuration
    email_enabled = Column(Boolean, default=False)
    email_verified = Column(Boolean, default=False)
    email_verified_at = Column(DateTime)

    # Backup codes
    backup_codes: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(String), nullable=True
    )  # Hashed backup codes
    backup_codes_generated_at = Column(DateTime)
    backup_codes_used_count = Column(Integer, default=0)

    # Recovery options
    recovery_email = Column(String(255))
    recovery_phone = Column(String(50))
    security_questions = Column(JSON)  # List of Q&A pairs

    # Metadata
    last_used_at = Column(DateTime)
    last_used_method = Column(String(50))

    # Relationships
    user = relationship("UserAuth", back_populates="mfa_config")

    def __repr__(self) -> str:
        """Return string representation."""
        return f"<MFAConfig(user_id={self.user_id}, totp={self.totp_enabled}, sms={self.sms_enabled})>"

    @property
    def is_enabled(self) -> bool:
        """Check if any MFA method is enabled."""
        return bool(self.totp_enabled or self.sms_enabled or self.email_enabled)

    @property
    def enabled_methods(self) -> List[str]:
        """Get list of enabled MFA methods."""
        methods = []
        if self.totp_enabled:
            methods.append("totp")
        if self.sms_enabled:
            methods.append("sms")
        if self.email_enabled:
            methods.append("email")
        return methods


class PasswordHistory(BaseModel):
    """Password history for preventing reuse."""

    __tablename__ = "password_history"

    # User reference
    user_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user_auth.id"), nullable=False
    )

    # Password hash
    password_hash = Column(String(255), nullable=False)

    # Metadata
    created_at = Column(DateTime, default=datetime.now(timezone.utc), nullable=False)

    # Relationships
    user = relationship("UserAuth", back_populates="password_history")

    # Indexes
    __table_args__ = (Index("idx_password_history_user", "user_id", "created_at"),)

    def __repr__(self) -> str:
        """Return string representation."""
        return (
            f"<PasswordHistory(user_id={self.user_id}, created_at={self.created_at})>"
        )


class LoginAttempt(BaseModel):
    """Login attempt tracking."""

    __tablename__ = "login_attempts"

    # Attempt details
    user_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user_auth.id"), nullable=False
    )
    username = Column(String(255))  # Email or phone used
    success = Column(Boolean, nullable=False)
    failure_reason = Column(String(255))

    # Request information
    ip_address = Column(String(45))
    user_agent = Column(String(500))
    device_fingerprint = Column(String(255))

    # Metadata
    attempted_at = Column(DateTime, default=datetime.now(timezone.utc), nullable=False)
    session_id: Mapped[Optional[PyUUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )  # If successful
    event_metadata = Column(JSON, default=dict)  # Additional event data

    # Relationships
    user = relationship("UserAuth", back_populates="login_attempts")

    # Indexes
    __table_args__ = (
        Index("idx_login_attempt_user", "user_id", "attempted_at"),
        Index("idx_login_attempt_ip", "ip_address", "attempted_at"),
        Index("idx_login_attempt_success", "success", "attempted_at"),
    )

    def __repr__(self) -> str:
        """Return string representation."""
        return f"<LoginAttempt(user_id={self.user_id}, success={self.success}, at={self.attempted_at})>"


class BiometricTemplate(BaseModel):
    """Biometric template storage for authentication."""

    __tablename__ = "biometric_templates"

    # Template identification
    template_id = Column(String(100), unique=True, nullable=False, index=True)
    user_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user_auth.id"), nullable=False
    )

    # Biometric details
    biometric_type = Column(
        String(50), nullable=False
    )  # fingerprint, face, voice, etc.
    encrypted_template = Column(Text, nullable=False)  # Encrypted biometric template
    quality_score = Column(Float, nullable=False)  # Template quality score (0.0-1.0)

    # Device information
    device_info = Column(JSON)  # Capture device details
    device_model = Column(String(255))
    sdk_version = Column(String(50))

    # Status
    is_active = Column(Boolean, default=True, nullable=False)
    deactivated_at = Column(DateTime)
    deactivation_reason = Column(String(255))

    # Usage tracking
    last_used_at = Column(DateTime)
    usage_count = Column(Integer, default=0)
    last_match_score = Column(Float)  # Last successful match score

    # Metadata
    created_at = Column(DateTime, default=datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, onupdate=datetime.now(timezone.utc))
    expires_at = Column(DateTime)  # Optional expiration

    # Relationships
    user = relationship("UserAuth", back_populates="biometric_templates")

    # Indexes
    __table_args__ = (
        Index("idx_biometric_user_type", "user_id", "biometric_type", "is_active"),
        Index("idx_biometric_template_id", "template_id"),
        UniqueConstraint("user_id", "template_id", name="uq_user_template"),
    )

    def __repr__(self) -> str:
        """Return string representation."""
        return f"<BiometricTemplate(user_id={self.user_id}, type={self.biometric_type}, active={self.is_active})>"


class BiometricAuditLog(BaseModel):
    """Audit log for biometric authentication events."""

    __tablename__ = "biometric_audit_log"

    # User reference
    user_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user_auth.id"), nullable=False
    )
    template_id = Column(String(100))

    # Event details
    event_type = Column(String(50), nullable=False)  # enrolled, verified, failed, etc.
    biometric_type = Column(String(50), nullable=False)
    success = Column(Boolean, nullable=False)

    # Additional information
    match_score = Column(Float)
    quality_score = Column(Float)
    failure_reason = Column(String(500))
    device_info = Column(JSON)

    # Request information
    ip_address = Column(String(45))
    user_agent = Column(String(500))
    session_id: Mapped[PyUUID] = mapped_column(UUID(as_uuid=True), nullable=False)

    # Timestamps
    event_timestamp = Column(
        DateTime, default=datetime.now(timezone.utc), nullable=False
    )

    # Relationships
    user = relationship("UserAuth")

    # Indexes
    __table_args__ = (
        Index("idx_biometric_audit_user", "user_id", "event_timestamp"),
        Index("idx_biometric_audit_event", "event_type", "event_timestamp"),
        Index("idx_biometric_audit_success", "success", "event_timestamp"),
        Index("idx_biometric_audit_template", "template_id"),
    )

    def __repr__(self) -> str:
        """Return string representation."""
        return f"<BiometricAuditLog(user_id={self.user_id}, event={self.event_type}, success={self.success})>"


class WebAuthnCredential(BaseModel):
    """WebAuthn/FIDO2 credential storage."""

    __tablename__ = "webauthn_credentials"

    # User reference
    user_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user_auth.id"), nullable=False
    )

    # Credential details
    credential_id = Column(Text, unique=True, nullable=False)
    public_key = Column(Text, nullable=False)
    aaguid = Column(String(100))  # Authenticator Attestation GUID
    sign_count = Column(Integer, default=0, nullable=False)

    # Authenticator information
    authenticator_attachment = Column(String(50))  # platform or cross-platform
    credential_type = Column(String(50), default="public-key", nullable=False)
    transports: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(String), nullable=True
    )  # usb, nfc, ble, internal

    # Device information
    device_name = Column(String(255))
    last_used_device = Column(String(255))
    last_used_ip = Column(String(45))

    # Status
    is_active = Column(Boolean, default=True, nullable=False)
    revoked_at = Column(DateTime)
    revocation_reason = Column(String(255))

    # Usage tracking
    last_used_at = Column(DateTime)
    usage_count = Column(Integer, default=0)

    # Metadata
    created_at = Column(DateTime, default=datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, onupdate=datetime.now(timezone.utc))

    # Relationships
    user = relationship("UserAuth", back_populates="webauthn_credentials")

    # Indexes
    __table_args__ = (
        Index("idx_webauthn_user", "user_id", "is_active"),
        Index("idx_webauthn_credential_id", "credential_id"),
    )

    def __repr__(self) -> str:
        """Return string representation."""
        return f"<WebAuthnCredential(user_id={self.user_id}, device={self.device_name}, active={self.is_active})>"


class APIKey(BaseModel):
    """API Key model for programmatic access to the Haven Health Passport API.

    API keys provide secure, revocable access to the API for third-party integrations,
    automated systems, and external applications. Each key has specific permissions,
    rate limits, and usage tracking capabilities.
    """

    __tablename__ = "api_keys"

    # Key identification
    id: Mapped[PyUUID] = mapped_column(UUID(as_uuid=True), primary_key=True, index=True)
    user_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user_auth.id"), nullable=False
    )

    # Key details
    name: Mapped[str] = mapped_column(
        String(255), nullable=False
    )  # Human-readable name for the key
    description: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True
    )  # Optional description of key purpose
    key_prefix: Mapped[str] = mapped_column(
        String(10), nullable=False
    )  # Public prefix (e.g., "hhp_live_")
    key_hash: Mapped[str] = mapped_column(
        String(255), nullable=False, unique=True
    )  # Hashed API key
    last_four: Mapped[str] = mapped_column(
        String(4), nullable=False
    )  # Last 4 characters for identification

    # Permissions and scope
    scopes: Mapped[List[str]] = mapped_column(
        ARRAY(String), nullable=False, default=[]
    )  # List of permitted scopes
    tier: Mapped[str] = mapped_column(
        String(50), default="basic", nullable=False
    )  # basic, standard, premium, enterprise
    ip_whitelist: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(String), nullable=True
    )  # Optional IP restrictions
    allowed_origins: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(String), nullable=True
    )  # Optional CORS origin restrictions

    # Validity
    is_active = Column(Boolean, default=True, nullable=False)
    expires_at = Column(DateTime)  # Optional expiration date
    revoked_at = Column(DateTime)  # Timestamp when key was revoked
    revocation_reason = Column(String(255))  # Reason for revocation

    # Usage tracking
    last_used_at = Column(DateTime)
    last_used_ip = Column(String(45))  # IPv4 or IPv6
    last_used_user_agent = Column(String(500))
    usage_count = Column(Integer, default=0, nullable=False)

    # Rate limiting
    rate_limit_override = Column(Integer)  # Custom rate limit (overrides tier default)
    rate_limit_window = Column(Integer)  # Custom window in seconds

    # Metadata
    created_at = Column(DateTime, default=datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, onupdate=datetime.now(timezone.utc))

    # Relationships
    user = relationship("UserAuth", back_populates="api_keys")

    # Indexes
    __table_args__ = (
        Index("idx_api_key_user", "user_id", "is_active"),
        Index("idx_api_key_prefix", "key_prefix"),
        Index("idx_api_key_expires", "expires_at"),
        Index("idx_api_key_last_used", "last_used_at"),
    )

    def __repr__(self) -> str:
        """Return string representation."""
        return f"<APIKey(name={self.name}, user_id={self.user_id}, tier={self.tier}, active={self.is_active})>"

    def is_valid(self) -> bool:
        """Check if the API key is currently valid."""
        if not self.is_active:
            return False
        if self.revoked_at:
            return False
        if self.expires_at and self.expires_at < datetime.now(timezone.utc):
            return False
        return True

    def has_scope(self, scope: str) -> bool:
        """Check if the API key has a specific scope."""
        return bool(scope in (self.scopes or []))


class PasswordResetToken(BaseModel):
    """Password reset token model."""

    __tablename__ = "password_reset_tokens"

    # Token information
    user_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user_auth.id"), nullable=False
    )
    token = Column(String(255), nullable=False, unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    # Usage tracking
    used_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)

    # User relationship
    user = relationship("UserAuth", backref="password_reset_tokens")

    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.now(timezone.utc),
        onupdate=datetime.now(timezone.utc),
    )

    # Indexes
    __table_args__ = (
        Index("idx_password_reset_token", "token"),
        Index("idx_password_reset_user", "user_id"),
        Index("idx_password_reset_expires", "expires_at"),
    )

    def __repr__(self) -> str:
        """Return string representation."""
        return f"<PasswordResetToken(user_id={self.user_id}, expires_at={self.expires_at})>"

    def is_valid(self) -> bool:
        """Check if the token is still valid."""
        # Check if already used
        if self.used_at is not None:
            return False

        # Check if expired
        current_time = datetime.now(timezone.utc)
        return self.expires_at > current_time


class SMSVerificationCode(BaseModel):
    """SMS verification code model."""

    __tablename__ = "sms_verification_codes"

    # Code information
    phone_number = Column(String(20), nullable=False, index=True)
    code = Column(String(10), nullable=False)
    purpose = Column(
        String(50),
        nullable=False,
        comment="Purpose: registration, login, password_reset, phone_change",
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    # Usage tracking
    attempts = Column(Integer, nullable=False, default=0)
    verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    ip_address = Column(String(45), nullable=True)

    # User association (optional)
    user_id: Mapped[Optional[PyUUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user_auth.id"), nullable=True
    )
    user = relationship("UserAuth", backref="sms_verification_codes")

    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.now(timezone.utc),
        onupdate=datetime.now(timezone.utc),
    )

    # Indexes
    __table_args__ = (
        Index("idx_sms_verification_phone", "phone_number"),
        Index("idx_sms_verification_user", "user_id"),
        Index("idx_sms_verification_expires", "expires_at"),
    )

    def __repr__(self) -> str:
        """Return string representation."""
        return (
            f"<SMSVerificationCode(phone={self.phone_number}, purpose={self.purpose})>"
        )

    def is_valid(self) -> bool:
        """Check if the code is still valid."""
        # Check if already verified
        if self.verified_at is not None:
            return False

        # Check if too many attempts
        if self.attempts >= 3:
            return False

        # Check if expired
        current_time = datetime.now(timezone.utc)
        return self.expires_at > current_time


class BackupCode(BaseModel):
    """Backup code for MFA recovery."""

    __tablename__ = "backup_codes"

    # Code information
    user_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user_auth.id"), nullable=False
    )
    code_hash = Column(String(255), nullable=False)

    # Usage tracking
    used_at = Column(DateTime, nullable=True)
    used_ip = Column(String(45), nullable=True)
    used_user_agent = Column(Text, nullable=True)

    # User relationship
    user = relationship("UserAuth", backref="backup_codes")

    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.now(timezone.utc))

    # Indexes
    __table_args__ = (
        Index("idx_backup_code_user", "user_id"),
        UniqueConstraint("user_id", "code_hash", name="uq_user_backup_code"),
    )

    def __repr__(self) -> str:
        """Return string representation."""
        return f"<BackupCode(user_id={self.user_id}, used={'Yes' if self.used_at else 'No'})>"

    def is_valid(self) -> bool:
        """Check if the backup code is still valid."""
        return bool(self.used_at is None)
