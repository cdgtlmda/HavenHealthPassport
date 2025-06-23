"""Database models for Haven Health Passport.

This module contains database models for FHIR Resources including Patient,
Observation, and other healthcare data with built-in validation.
All FHIR DomainResource types are validated using the FHIRValidator.
"""

from .access_log import AccessLog
from .auth import (
    APIKey,
    BackupCode,
    BiometricAuditLog,
    BiometricTemplate,
    DeviceInfo,
    LoginAttempt,
    MFAConfig,
    PasswordHistory,
    PasswordResetToken,
    SMSVerificationCode,
    UserAuth,
    UserRole,
    UserSession,
    WebAuthnCredential,
)
from .base import BaseModel, SoftDeleteMixin, TimestampMixin
from .document import Document
from .file_attachment import FileAttachment
from .health_record import HealthRecord
from .patient import Patient
from .sms_log import SMSLog
from .verification import Verification

# FHIR resource types handled by this module
__fhir_resource__ = "Patient"

# Note: FHIRValidator should be imported directly where needed to avoid circular imports
# All models include validation to ensure compliance with FHIR standards

__all__ = [
    "BaseModel",
    "TimestampMixin",
    "SoftDeleteMixin",
    "Document",
    "Patient",
    "HealthRecord",
    "Verification",
    "AccessLog",
    "FileAttachment",
    "SMSLog",
    "UserAuth",
    "UserRole",
    "UserSession",
    "MFAConfig",
    "DeviceInfo",
    "PasswordHistory",
    "LoginAttempt",
    "BiometricTemplate",
    "BiometricAuditLog",
    "WebAuthnCredential",
    "APIKey",
    "PasswordResetToken",
    "SMSVerificationCode",
    "BackupCode",
]
