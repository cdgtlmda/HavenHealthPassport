"""
Security Base Types.

Common types used across security validators.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class SecurityControlStatus(Enum):
    """Security control validation status."""

    COMPLIANT = "compliant"
    NON_COMPLIANT = "non_compliant"
    PARTIALLY_COMPLIANT = "partially_compliant"
    NOT_APPLICABLE = "not_applicable"
    ERROR = "error"
    # Also support the other format
    NOT_IMPLEMENTED = "not_implemented"
    PARTIALLY_IMPLEMENTED = "partially_implemented"
    FULLY_IMPLEMENTED = "fully_implemented"


class SecurityControlCategory(Enum):
    """Categories of security controls."""

    ACCESS_CONTROL = "access_control"
    ENCRYPTION = "encryption"
    AUDIT_LOGGING = "audit_logging"
    DATA_INTEGRITY = "data_integrity"
    TRANSMISSION_SECURITY = "transmission_security"
    PHYSICAL_SAFEGUARDS = "physical_safeguards"
    ADMINISTRATIVE_SAFEGUARDS = "administrative_safeguards"
    TECHNICAL_SAFEGUARDS = "technical_safeguards"


@dataclass
class SecurityControl:
    """Individual security control specification."""

    id: str
    name: str
    category: SecurityControlCategory
    description: str
    hipaa_reference: str
    validation_method: str
    critical: bool = True
    dependencies: List[str] = field(default_factory=list)
    # Alternative fields for compatibility
    priority: Optional[str] = None  # Critical, High, Medium, Low
    status: Optional[SecurityControlStatus] = None
    evidence: List[str] = field(default_factory=list)
    notes: Optional[str] = None


@dataclass
class ValidationResult:
    """Result of security control validation."""

    control: SecurityControl
    status: SecurityControlStatus
    timestamp: datetime
    details: Dict[str, Any]
    evidence: List[Dict[str, Any]]
    remediation_required: bool = False
    remediation_steps: List[str] = field(default_factory=list)
    # Alternative fields for compatibility
    control_id: Optional[str] = None
    passed: Optional[bool] = None
    findings: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_compliant(self) -> bool:
        """Check if control is compliant."""
        return self.status == SecurityControlStatus.COMPLIANT
