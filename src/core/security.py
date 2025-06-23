"""Security configuration module."""

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional


class SecurityControlCategory(str, Enum):
    """Categories of security controls."""

    ACCESS_CONTROL = "access_control"
    AUDIT_LOGGING = "audit_logging"
    ENCRYPTION = "encryption"
    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"


class SecurityControlStatus(str, Enum):
    """Status of security controls."""

    COMPLIANT = "compliant"
    NON_COMPLIANT = "non_compliant"
    PARTIAL = "partial"
    NOT_APPLICABLE = "not_applicable"


@dataclass
class SecurityControl:
    """Security control definition."""

    id: str
    name: str
    category: SecurityControlCategory
    description: str
    requirement: str
    implementation: Optional[str] = None


@dataclass
class ValidationResult:
    """Security validation result."""

    control_id: str
    status: SecurityControlStatus
    message: str
    details: Optional[Dict[str, Any]] = None


@dataclass
class SecurityConfig:
    """Security configuration settings."""

    encryption_enabled: bool = True
    encryption_algorithm: str = "AES-256-GCM"
    key_rotation_days: int = 90
    min_password_length: int = 12
    require_mfa: bool = True
    session_timeout_minutes: int = 30
    max_login_attempts: int = 5
    audit_logging_enabled: bool = True
