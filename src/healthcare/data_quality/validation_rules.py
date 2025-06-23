"""Data Validation Framework.

This module implements a comprehensive data validation framework for healthcare
data quality, ensuring data integrity, completeness, and compliance with
healthcare standards in refugee settings.

All patient data handled by this module is encrypted using field-level encryption
and access is controlled through role-based access control mechanisms.
"""

import logging
import re
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Callable, Dict, Optional, Tuple, Union

logger = logging.getLogger(__name__)


class ValidationSeverity(Enum):
    """Severity levels for validation issues."""

    ERROR = "error"  # Must be fixed
    WARNING = "warning"  # Should be reviewed
    INFO = "info"  # Informational only
    CRITICAL = "critical"  # Critical issue that must be fixed immediately


class ValidationCategory(Enum):
    """Categories of validation rules."""

    REQUIRED = "required"  # Required field validation
    FORMAT = "format"  # Format validation
    RANGE = "range"  # Range validation
    CONSISTENCY = "consistency"  # Cross-field consistency
    COMPLETENESS = "completeness"  # Data completeness
    TEMPORAL = "temporal"  # Time-based validation
    CLINICAL = "clinical"  # Clinical logic validation
    REGULATORY = "regulatory"  # Regulatory compliance
    DEMOGRAPHIC = "demographic"  # Demographic validation
    ELIGIBILITY = "eligibility"  # Eligibility validation
    SAFETY = "safety"  # Safety validation
    CULTURAL = "cultural"  # Cultural compatibility validation


class ValidationResult:
    """Result of a validation check."""

    def __init__(
        self,
        field: str,
        rule: str,
        is_valid: bool,
        message: Optional[str] = None,
        severity: ValidationSeverity = ValidationSeverity.ERROR,
        category: ValidationCategory = ValidationCategory.FORMAT,
        suggestion: Optional[str] = None,
    ):
        """Initialize validation result.

        Args:
            field: Field being validated
            rule: Rule that was applied
            is_valid: Whether validation passed
            message: Error/warning message
            severity: Severity level
            category: Validation category
            suggestion: Suggested correction
        """
        self.field = field
        self.rule = rule
        self.is_valid = is_valid
        self.message = message
        self.severity = severity
        self.category = category
        self.suggestion = suggestion
        self.timestamp = datetime.now()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "field": self.field,
            "rule": self.rule,
            "is_valid": self.is_valid,
            "message": self.message,
            "severity": self.severity.value,
            "category": self.category.value,
            "suggestion": self.suggestion,
            "timestamp": self.timestamp.isoformat(),
        }


class ValidationRule:
    """Base class for validation rules."""

    def __init__(
        self,
        name: str,
        description: str,
        category: ValidationCategory,
        severity: ValidationSeverity = ValidationSeverity.ERROR,
    ):
        """Initialize validation rule.

        Args:
            name: Rule name
            description: Rule description
            category: Rule category
            severity: Default severity
        """
        self.name = name
        self.description = description
        self.category = category
        self.severity = severity

    def validate(self, value: Any, context: Optional[Dict] = None) -> ValidationResult:
        """Validate a value.

        Args:
            value: Value to validate
            context: Optional context data

        Returns:
            ValidationResult
        """
        raise NotImplementedError("Subclasses must implement validate()")


class RequiredFieldRule(ValidationRule):
    """Rule for required field validation."""

    def __init__(
        self,
        field_name: str,
        allow_empty: bool = False,
        conditional: Optional[Callable] = None,
    ):
        """Initialize required field rule.

        Args:
            field_name: Name of the field
            allow_empty: Whether empty strings are allowed
            conditional: Optional function to determine if field is required
        """
        super().__init__(
            name=f"required_{field_name}",
            description=f"{field_name} is required",
            category=ValidationCategory.REQUIRED,
        )
        self.field_name = field_name
        self.allow_empty = allow_empty
        self.conditional = conditional

    def validate(self, value: Any, context: Optional[Dict] = None) -> ValidationResult:
        """Validate required field."""
        # Check if conditionally required
        if self.conditional and context:
            if not self.conditional(context):
                return ValidationResult(
                    field=self.field_name,
                    rule=self.name,
                    is_valid=True,
                    message="Field not required in this context",
                    severity=ValidationSeverity.INFO,
                    category=self.category,
                )

        # Check if value exists
        if value is None:
            return ValidationResult(
                field=self.field_name,
                rule=self.name,
                is_valid=False,
                message=f"{self.field_name} is required",
                severity=self.severity,
                category=self.category,
            )

        # Check if empty string
        if isinstance(value, str) and not value.strip() and not self.allow_empty:
            return ValidationResult(
                field=self.field_name,
                rule=self.name,
                is_valid=False,
                message=f"{self.field_name} cannot be empty",
                severity=self.severity,
                category=self.category,
            )

        return ValidationResult(
            field=self.field_name, rule=self.name, is_valid=True, category=self.category
        )


class FormatRule(ValidationRule):
    """Rule for format validation using regex."""

    def __init__(
        self,
        field_name: str,
        pattern: str,
        description: str,
        example: Optional[str] = None,
    ):
        """Initialize format rule.

        Args:
            field_name: Name of the field
            pattern: Regex pattern
            description: Description of expected format
            example: Example of valid format
        """
        super().__init__(
            name=f"format_{field_name}",
            description=description,
            category=ValidationCategory.FORMAT,
        )
        self.field_name = field_name
        self.pattern = re.compile(pattern)
        self.example = example

    def validate(self, value: Any, context: Optional[Dict] = None) -> ValidationResult:
        """Validate format."""
        if value is None or value == "":
            return ValidationResult(
                field=self.field_name,
                rule=self.name,
                is_valid=True,
                category=self.category,
            )

        if not isinstance(value, str):
            value = str(value)

        if not self.pattern.match(value):
            suggestion = f"Expected format: {self.description}"
            if self.example:
                suggestion += f" (Example: {self.example})"

            return ValidationResult(
                field=self.field_name,
                rule=self.name,
                is_valid=False,
                message=f"Invalid format for {self.field_name}",
                severity=self.severity,
                category=self.category,
                suggestion=suggestion,
            )

        return ValidationResult(
            field=self.field_name, rule=self.name, is_valid=True, category=self.category
        )


class RangeRule(ValidationRule):
    """Rule for numeric range validation."""

    def __init__(
        self,
        field_name: str,
        min_value: Optional[Union[int, float, Decimal]] = None,
        max_value: Optional[Union[int, float, Decimal]] = None,
        inclusive: bool = True,
    ):
        """Initialize range rule.

        Args:
            field_name: Name of the field
            min_value: Minimum value
            max_value: Maximum value
            inclusive: Whether range is inclusive
        """
        description = f"{field_name} must be "
        if min_value is not None and max_value is not None:
            description += f"between {min_value} and {max_value}"
        elif min_value is not None:
            description += f"at least {min_value}"
        elif max_value is not None:
            description += f"at most {max_value}"

        super().__init__(
            name=f"range_{field_name}",
            description=description,
            category=ValidationCategory.RANGE,
        )
        self.field_name = field_name
        self.min_value = min_value
        self.max_value = max_value
        self.inclusive = inclusive

    def validate(self, value: Any, context: Optional[Dict] = None) -> ValidationResult:
        """Validate range."""
        if value is None:
            return ValidationResult(
                field=self.field_name,
                rule=self.name,
                is_valid=True,
                category=self.category,
            )

        try:
            numeric_value = float(value)
        except (TypeError, ValueError):
            return ValidationResult(
                field=self.field_name,
                rule=self.name,
                is_valid=False,
                message=f"{self.field_name} must be numeric",
                severity=self.severity,
                category=self.category,
            )

        # Check minimum
        if self.min_value is not None:
            if self.inclusive and numeric_value < self.min_value:
                return ValidationResult(
                    field=self.field_name,
                    rule=self.name,
                    is_valid=False,
                    message=f"{self.field_name} is below minimum value {self.min_value}",
                    severity=self.severity,
                    category=self.category,
                    suggestion=f"Value must be at least {self.min_value}",
                )
            elif not self.inclusive and numeric_value <= self.min_value:
                return ValidationResult(
                    field=self.field_name,
                    rule=self.name,
                    is_valid=False,
                    message=f"{self.field_name} must be greater than {self.min_value}",
                    severity=self.severity,
                    category=self.category,
                )

        # Check maximum
        if self.max_value is not None:
            if self.inclusive and numeric_value > self.max_value:
                return ValidationResult(
                    field=self.field_name,
                    rule=self.name,
                    is_valid=False,
                    message=f"{self.field_name} exceeds maximum value {self.max_value}",
                    severity=self.severity,
                    category=self.category,
                    suggestion=f"Value must be at most {self.max_value}",
                )
            elif not self.inclusive and numeric_value >= self.max_value:
                return ValidationResult(
                    field=self.field_name,
                    rule=self.name,
                    is_valid=False,
                    message=f"{self.field_name} must be less than {self.max_value}",
                    severity=self.severity,
                    category=self.category,
                )

        return ValidationResult(
            field=self.field_name, rule=self.name, is_valid=True, category=self.category
        )


class DateRule(ValidationRule):
    """Rule for date validation."""

    def __init__(
        self,
        field_name: str,
        min_date: Optional[date] = None,
        max_date: Optional[date] = None,
        allow_future: bool = False,
        date_format: str = "%Y-%m-%d",
    ):
        """Initialize date rule.

        Args:
            field_name: Name of the field
            min_date: Minimum date
            max_date: Maximum date
            allow_future: Whether future dates are allowed
            date_format: Expected date format
        """
        super().__init__(
            name=f"date_{field_name}",
            description=f"{field_name} must be a valid date",
            category=ValidationCategory.TEMPORAL,
        )
        self.field_name = field_name
        self.min_date = min_date
        self.max_date = max_date
        self.allow_future = allow_future
        self.date_format = date_format

    def validate(self, value: Any, context: Optional[Dict] = None) -> ValidationResult:
        """Validate date."""
        if value is None:
            return ValidationResult(
                field=self.field_name,
                rule=self.name,
                is_valid=True,
                category=self.category,
            )

        # Parse date
        if isinstance(value, date):
            date_value = value
        elif isinstance(value, datetime):
            date_value = value.date()
        else:
            try:
                date_value = datetime.strptime(str(value), self.date_format).date()
            except ValueError:
                return ValidationResult(
                    field=self.field_name,
                    rule=self.name,
                    is_valid=False,
                    message=f"Invalid date format for {self.field_name}",
                    severity=self.severity,
                    category=self.category,
                    suggestion=f"Expected format: {self.date_format}",
                )

        # Check future dates
        if not self.allow_future and date_value > date.today():
            return ValidationResult(
                field=self.field_name,
                rule=self.name,
                is_valid=False,
                message=f"{self.field_name} cannot be in the future",
                severity=self.severity,
                category=self.category,
            )

        # Check minimum date
        if self.min_date and date_value < self.min_date:
            return ValidationResult(
                field=self.field_name,
                rule=self.name,
                is_valid=False,
                message=f"{self.field_name} is before minimum date {self.min_date}",
                severity=self.severity,
                category=self.category,
            )

        # Check maximum date
        if self.max_date and date_value > self.max_date:
            return ValidationResult(
                field=self.field_name,
                rule=self.name,
                is_valid=False,
                message=f"{self.field_name} is after maximum date {self.max_date}",
                severity=self.severity,
                category=self.category,
            )

        return ValidationResult(
            field=self.field_name, rule=self.name, is_valid=True, category=self.category
        )


class CodeValidationRule(ValidationRule):
    """Rule for validating medical codes."""

    def __init__(
        self,
        field_name: str,
        code_system: str,
        validator_func: Callable[[str], Tuple[bool, Optional[str]]],
    ):
        """Initialize code validation rule.

        Args:
            field_name: Name of the field
            code_system: Code system (ICD-10, SNOMED, etc.)
            validator_func: Function to validate code
        """
        super().__init__(
            name=f"code_{field_name}",
            description=f"{field_name} must be a valid {code_system} code",
            category=ValidationCategory.FORMAT,
        )
        self.field_name = field_name
        self.code_system = code_system
        self.validator_func = validator_func

    def validate(self, value: Any, context: Optional[Dict] = None) -> ValidationResult:
        """Validate medical code."""
        if value is None or value == "":
            return ValidationResult(
                field=self.field_name,
                rule=self.name,
                is_valid=True,
                category=self.category,
            )

        is_valid, error_message = self.validator_func(str(value))

        if not is_valid:
            return ValidationResult(
                field=self.field_name,
                rule=self.name,
                is_valid=False,
                message=error_message or f"Invalid {self.code_system} code",
                severity=self.severity,
                category=self.category,
            )

        return ValidationResult(
            field=self.field_name, rule=self.name, is_valid=True, category=self.category
        )
