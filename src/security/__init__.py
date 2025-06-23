"""
Security module for Haven Health Passport.

Provides encryption, access control, and audit logging for PHI data.
"""

from .access_control import (
    AccessLevel,
    AccessPermission,
    require_permission,
    require_phi_access,
)
from .audit import audit_log, audit_phi_access
from .phi_protection import (
    PHIAccessControl,
    PHIEncryption,
    decrypt_phi,
    encrypt_phi,
    protect_phi_field,
    requires_phi_access,
)

__all__ = [
    "AccessLevel",
    "AccessPermission",
    "audit_log",
    "audit_phi_access",
    "PHIEncryption",
    "PHIAccessControl",
    "encrypt_phi",
    "decrypt_phi",
    "require_permission",
    "require_phi_access",
    "requires_phi_access",
    "protect_phi_field",
]
