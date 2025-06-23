"""Validation types for Haven Health Passport."""

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional


class ValidationSeverity(Enum):
    """Severity levels for validation results."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class ValidationResult:
    """Result of a validation check."""

    is_valid: bool
    severity: ValidationSeverity
    message: str
    field_path: Optional[str] = None
    rule_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

    def __str__(self) -> str:
        """Return string representation of validation result."""
        prefix = f"[{self.severity.value.upper()}]"
        location = f" at {self.field_path}" if self.field_path else ""
        rule = f" (rule: {self.rule_id})" if self.rule_id else ""
        return f"{prefix} {self.message}{location}{rule}"
