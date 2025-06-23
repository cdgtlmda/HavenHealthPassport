"""Import all models for test database creation.

This ensures all SQLAlchemy relationships are properly resolved
before creating test database tables.
"""

# Import base first
from src.database import Base

# Audit models
from src.models.audit_log import AuditAction, AuditLog

# Import all models in dependency order
# Auth models
from src.models.auth import (
    BackupCode,
    LoginAttempt,
    MFAConfig,
    PasswordHistory,
    PasswordResetToken,
    SMSVerificationCode,
    UserAuth,
    UserRole,
    UserSession,
)

# File models
from src.models.file_attachment import FileAttachment

# Health record models
from src.models.health_record import HealthRecord

# Organization models
from src.models.organization import Organization

# Patient models
from src.models.patient import (
    FamilyRelationship,
    Gender,
    Patient,
    RefugeeStatus,
    VerificationStatus,
)

# SMS models (depends on UserAuth)
from src.models.sms_log import SMSLog

# Additional models that might have relationships
try:
    from src.models.document import Document
except ImportError:
    pass

try:
    from src.models.notification import Notification
except ImportError:
    pass

# Translation model has a reserved field name issue
# try:
#     from src.models.translation import Translation
# except ImportError:
#     pass

try:
    from src.models.emergency_access import EmergencyAccessLog
except ImportError:
    pass

# Export all models for test database creation
__all__ = [
    "Base",
    "AuditAction",
    "AuditLog",
    "BackupCode",
    "LoginAttempt",
    "MFAConfig",
    "PasswordHistory",
    "PasswordResetToken",
    "SMSVerificationCode",
    "UserAuth",
    "UserRole",
    "UserSession",
    "FileAttachment",
    "HealthRecord",
    "Organization",
    "FamilyRelationship",
    "Gender",
    "Patient",
    "RefugeeStatus",
    "VerificationStatus",
    "SMSLog",
    "Document",
    "Notification",
    "EmergencyAccessLog",
]
