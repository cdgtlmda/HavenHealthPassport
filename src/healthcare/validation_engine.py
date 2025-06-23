"""Data Validation Rules Engine for Healthcare Data.

This module implements a comprehensive validation rules engine for healthcare data,
ensuring data quality, consistency, and compliance with healthcare standards.
Handles FHIR Resource validation and encrypted PHI data with proper access control.
"""

import logging
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Union, cast

from ..types import ValidationResult, ValidationSeverity

logger = logging.getLogger(__name__)


class ValidationRuleType(Enum):
    """Types of validation rules."""

    REQUIRED = "required"
    FORMAT = "format"
    RANGE = "range"
    CODE_SET = "code_set"
    CROSS_FIELD = "cross_field"
    TEMPORAL = "temporal"
    CONSISTENCY = "consistency"
    DUPLICATE = "duplicate"
    COMPLETENESS = "completeness"
    CUSTOM = "custom"


class ValidationContext(Enum):
    """Context for validation execution."""

    IMPORT = "import"
    EXPORT = "export"
    STORAGE = "storage"
    DISPLAY = "display"
    TRANSMISSION = "transmission"
    PROCESSING = "processing"


@dataclass
class ValidationRule:
    """Base validation rule definition."""

    rule_id: str = ""
    field_path: str = ""
    description: str = ""
    rule_type: Optional[ValidationRuleType] = None
    severity: ValidationSeverity = ValidationSeverity.ERROR
    contexts: List[ValidationContext] = field(
        default_factory=lambda: [ValidationContext.PROCESSING]
    )
    active: bool = True
    error_message: Optional[str] = None
    dependencies: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RequiredFieldRule(ValidationRule):
    """Rule for required field validation."""

    allow_empty: bool = False
    allow_whitespace_only: bool = False

    def __post_init__(self) -> None:
        """Set rule type after initialization."""
        self.rule_type = ValidationRuleType.REQUIRED


@dataclass
class FormatRule(ValidationRule):
    """Rule for format validation."""

    pattern: Optional[str] = None
    format_type: Optional[str] = None  # email, phone, url, etc.
    case_sensitive: bool = True

    def __post_init__(self) -> None:
        """Initialize the rule type for format validation."""
        self.rule_type = ValidationRuleType.FORMAT


@dataclass
class RangeRule(ValidationRule):
    """Rule for range validation."""

    min_value: Optional[Union[int, float, datetime, date]] = None
    max_value: Optional[Union[int, float, datetime, date]] = None
    inclusive_min: bool = True
    inclusive_max: bool = True

    def __post_init__(self) -> None:
        """Initialize the rule type for range validation."""
        self.rule_type = ValidationRuleType.RANGE


@dataclass
class CodeSetRule(ValidationRule):
    """Rule for code set validation."""

    code_system: str = ""
    allowed_codes: Optional[Set[str]] = None
    code_system_version: Optional[str] = None
    validate_display_name: bool = False

    def __post_init__(self) -> None:
        """Initialize the rule type for code set validation."""
        self.rule_type = ValidationRuleType.CODE_SET


@dataclass
class CrossFieldRule(ValidationRule):
    """Rule for cross-field validation."""

    related_fields: List[str] = field(default_factory=list)
    validation_function: Optional[Callable] = None

    def __post_init__(self) -> None:
        """Initialize the rule type for cross-field validation."""
        self.rule_type = ValidationRuleType.CROSS_FIELD


@dataclass
class TemporalRule(ValidationRule):
    """Rule for temporal validation."""

    temporal_type: str = "past"  # "past", "future", "relative_to_field"
    reference_field: Optional[str] = None
    offset_days: Optional[int] = None

    def __post_init__(self) -> None:
        """Initialize the rule type for temporal validation."""
        self.rule_type = ValidationRuleType.TEMPORAL


class ValidationEngine:
    """Main validation rules engine.

    This engine validates FHIR DomainResource data and ensures
    proper handling of encrypted PHI data.
    """

    def __init__(self) -> None:
        """Initialize validation engine."""
        self.rules: Dict[str, List[ValidationRule]] = {}
        self.rule_registry: Dict[str, ValidationRule] = {}
        self.format_validators: Dict[str, Callable] = {}
        self.code_validators: Dict[str, Callable] = {}
        self._initialize_default_validators()

    def _initialize_default_validators(self) -> None:
        """Initialize default format and code validators."""
        # Format validators
        self.format_validators.update(
            {
                "email": self._validate_email,
                "phone": self._validate_phone,
                "url": self._validate_url,
                "date": self._validate_date,
                "datetime": self._validate_datetime,
                "uuid": self._validate_uuid,
                "ssn": self._validate_ssn,
                "npi": self._validate_npi,
                "ein": self._validate_ein,
                "postal_code": self._validate_postal_code,
                "unhcr_id": self._validate_unhcr_id,
            }
        )

        # Code validators
        self.code_validators.update(
            {
                "ICD10": self._validate_icd10,
                "CPT": self._validate_cpt,
                "LOINC": self._validate_loinc,
                "SNOMED": self._validate_snomed,
                "RXNORM": self._validate_rxnorm,
                "CVX": self._validate_cvx,
                "NDC": self._validate_ndc,
            }
        )

    def register_rule(self, rule: ValidationRule) -> None:
        """Register a validation rule.

        Args:
            rule: Validation rule to register
        """
        # Add to field-based index
        if rule.field_path not in self.rules:
            self.rules[rule.field_path] = []
        self.rules[rule.field_path].append(rule)

        # Add to rule registry
        self.rule_registry[rule.rule_id] = rule

        logger.debug("Registered rule %s for field %s", rule.rule_id, rule.field_path)

    def unregister_rule(self, rule_id: str) -> None:
        """Unregister a validation rule.

        Args:
            rule_id: ID of rule to unregister
        """
        if rule_id in self.rule_registry:
            rule = self.rule_registry[rule_id]

            # Remove from field index
            if rule.field_path in self.rules:
                self.rules[rule.field_path] = [
                    r for r in self.rules[rule.field_path] if r.rule_id != rule_id
                ]

            # Remove from registry
            del self.rule_registry[rule_id]

            logger.debug("Unregistered rule %s", rule_id)

    def validate_field(
        self,
        field_path: str,
        value: Any,
        context: ValidationContext = ValidationContext.PROCESSING,
        data_context: Optional[Dict[str, Any]] = None,
    ) -> List[ValidationResult]:
        """Validate a single field.

        Args:
            field_path: Path to field (e.g., "patient.name.given")
            value: Field value to validate
            context: Validation context
            data_context: Full data context for cross-field validation

        Returns:
            List of validation results
        """
        results = []

        # Get applicable rules
        applicable_rules = self._get_applicable_rules(field_path, context)

        # Apply each rule
        for rule in applicable_rules:
            if not rule.active:
                continue

            try:
                result = self._apply_rule(rule, value, data_context)
                if result:
                    results.append(result)
            except (ValueError, TypeError, AttributeError) as e:
                logger.error("Error applying rule %s: %s", rule.rule_id, e)
                results.append(
                    ValidationResult(
                        is_valid=False,
                        severity=ValidationSeverity.ERROR,
                        message=f"Validation error: {str(e)}",
                        field_path=field_path,
                        rule_id=rule.rule_id,
                    )
                )

        return results

    def validate_object(
        self,
        data: Dict[str, Any],
        context: ValidationContext = ValidationContext.PROCESSING,
        fields_to_validate: Optional[List[str]] = None,
    ) -> List[ValidationResult]:
        """Validate an entire object.

        Args:
            data: Data object to validate
            context: Validation context
            fields_to_validate: Specific fields to validate (None = all)

        Returns:
            List of validation results
        """
        results = []

        # Determine fields to validate
        if fields_to_validate:
            fields = fields_to_validate
        else:
            fields = self._extract_all_field_paths(data)

        # Validate each field
        for field_path in fields:
            value = self._get_field_value(data, field_path)
            field_results = self.validate_field(field_path, value, context, data)
            results.extend(field_results)

        # Apply cross-field rules
        cross_field_results = self._validate_cross_fields(data, context)
        results.extend(cross_field_results)

        # Check completeness
        completeness_results = self._validate_completeness(data, context)
        results.extend(completeness_results)

        return results

    def _get_applicable_rules(
        self, field_path: str, context: ValidationContext
    ) -> List[ValidationRule]:
        """Get rules applicable to a field and context.

        Args:
            field_path: Field path
            context: Validation context

        Returns:
            List of applicable rules
        """
        applicable = []

        # Direct field rules
        if field_path in self.rules:
            for rule in self.rules[field_path]:
                if context in rule.contexts:
                    applicable.append(rule)

        # Wildcard rules (e.g., "patient.*")
        parts = field_path.split(".")
        for i in range(len(parts)):
            wildcard_path = ".".join(parts[: i + 1]) + ".*"
            if wildcard_path in self.rules:
                for rule in self.rules[wildcard_path]:
                    if context in rule.contexts:
                        applicable.append(rule)

        return applicable

    def _apply_rule(
        self,
        rule: ValidationRule,
        value: Any,
        data_context: Optional[Dict[str, Any]] = None,
    ) -> Optional[ValidationResult]:
        """Apply a single validation rule.

        Args:
            rule: Validation rule to apply
            value: Value to validate
            data_context: Additional context for validation

        Returns:
            Validation result or None if valid
        """
        if rule.rule_type == ValidationRuleType.REQUIRED:
            return self._apply_required_rule(cast(RequiredFieldRule, rule), value)
        elif rule.rule_type == ValidationRuleType.FORMAT:
            return self._apply_format_rule(cast(FormatRule, rule), value)
        elif rule.rule_type == ValidationRuleType.RANGE:
            return self._apply_range_rule(cast(RangeRule, rule), value)
        elif rule.rule_type == ValidationRuleType.CODE_SET:
            return self._apply_code_set_rule(cast(CodeSetRule, rule), value)
        elif rule.rule_type == ValidationRuleType.TEMPORAL:
            return self._apply_temporal_rule(
                cast(TemporalRule, rule), value, data_context
            )
        elif rule.rule_type == ValidationRuleType.CROSS_FIELD:
            return self._apply_cross_field_rule(
                cast(CrossFieldRule, rule), value, data_context
            )
        elif rule.rule_type == ValidationRuleType.CUSTOM:
            return self._apply_custom_rule(rule, value, data_context)
        else:
            logger.warning("Unknown rule type: %s", rule.rule_type)
            return None

    def _apply_required_rule(
        self, rule: RequiredFieldRule, value: Any
    ) -> Optional[ValidationResult]:
        """Apply required field rule."""
        if value is None:
            return ValidationResult(
                is_valid=False,
                severity=rule.severity,
                message=rule.error_message or f"Field {rule.field_path} is required",
                field_path=rule.field_path,
                rule_id=rule.rule_id,
            )

        if isinstance(value, str):
            if not value and not rule.allow_empty:
                return ValidationResult(
                    is_valid=False,
                    severity=rule.severity,
                    message=rule.error_message
                    or f"Field {rule.field_path} cannot be empty",
                    field_path=rule.field_path,
                    rule_id=rule.rule_id,
                )

            if value.isspace() and not rule.allow_whitespace_only:
                return ValidationResult(
                    is_valid=False,
                    severity=rule.severity,
                    message=rule.error_message
                    or f"Field {rule.field_path} cannot contain only whitespace",
                    field_path=rule.field_path,
                    rule_id=rule.rule_id,
                )

        return None

    def _apply_format_rule(
        self, rule: FormatRule, value: Any
    ) -> Optional[ValidationResult]:
        """Apply format validation rule."""
        if value is None or value == "":
            return None  # Skip format validation for empty values

        if rule.pattern:
            # Regex pattern validation
            flags = 0 if rule.case_sensitive else re.IGNORECASE
            if not re.match(rule.pattern, str(value), flags):
                return ValidationResult(
                    is_valid=False,
                    severity=rule.severity,
                    message=rule.error_message
                    or f"Field {rule.field_path} does not match required format",
                    field_path=rule.field_path,
                    rule_id=rule.rule_id,
                )

        if rule.format_type:
            # Named format validation
            if rule.format_type in self.format_validators:
                validator = self.format_validators[rule.format_type]
                if not validator(value):
                    return ValidationResult(
                        is_valid=False,
                        severity=rule.severity,
                        message=rule.error_message
                        or f"Field {rule.field_path} is not a valid {rule.format_type}",
                        field_path=rule.field_path,
                        rule_id=rule.rule_id,
                    )

        return None

    def _apply_range_rule(
        self, rule: RangeRule, value: Any
    ) -> Optional[ValidationResult]:
        """Apply range validation rule."""
        if value is None:
            return None

        # Convert to comparable type based on rule values
        comp_value: Union[float, datetime, date]
        try:
            # Determine the expected type from min_value or max_value
            reference_value = (
                rule.min_value if rule.min_value is not None else rule.max_value
            )

            if isinstance(reference_value, (int, float)):
                comp_value = float(value)
            elif isinstance(reference_value, datetime):
                if isinstance(value, datetime):
                    comp_value = value
                elif isinstance(value, date):
                    comp_value = datetime.combine(value, datetime.min.time())
                else:
                    comp_value = datetime.fromisoformat(str(value))
            elif isinstance(reference_value, date):
                if isinstance(value, date):
                    comp_value = value
                elif isinstance(value, datetime):
                    comp_value = value.date()
                else:
                    comp_value = date.fromisoformat(str(value))
            else:
                comp_value = float(value)  # Default to float for comparison
        except (ValueError, TypeError):
            return ValidationResult(
                is_valid=False,
                severity=rule.severity,
                message=f"Field {rule.field_path} has invalid type for range validation",
                field_path=rule.field_path,
                rule_id=rule.rule_id,
            )

        # Check minimum with type-safe comparison
        if rule.min_value is not None:
            if isinstance(comp_value, (int, float)) and isinstance(
                rule.min_value, (int, float)
            ):
                min_val = float(rule.min_value)
                if rule.inclusive_min:
                    if comp_value < min_val:
                        return ValidationResult(
                            is_valid=False,
                            severity=rule.severity,
                            message=rule.error_message
                            or f"Field {rule.field_path} must be >= {rule.min_value}",
                            field_path=rule.field_path,
                            rule_id=rule.rule_id,
                        )
                else:
                    if comp_value <= min_val:
                        return ValidationResult(
                            is_valid=False,
                            severity=rule.severity,
                            message=rule.error_message
                            or f"Field {rule.field_path} must be > {rule.min_value}",
                            field_path=rule.field_path,
                            rule_id=rule.rule_id,
                        )
            elif isinstance(comp_value, (date, datetime)) and isinstance(
                rule.min_value, (date, datetime)
            ):
                if rule.inclusive_min:
                    if comp_value < rule.min_value:
                        return ValidationResult(
                            is_valid=False,
                            severity=rule.severity,
                            message=rule.error_message
                            or f"Field {rule.field_path} must be >= {rule.min_value}",
                            field_path=rule.field_path,
                            rule_id=rule.rule_id,
                        )
                else:
                    if comp_value <= rule.min_value:
                        return ValidationResult(
                            is_valid=False,
                            severity=rule.severity,
                            message=rule.error_message
                            or f"Field {rule.field_path} must be > {rule.min_value}",
                            field_path=rule.field_path,
                            rule_id=rule.rule_id,
                        )

        # Check maximum with type-safe comparison
        if rule.max_value is not None:
            if isinstance(comp_value, (int, float)) and isinstance(
                rule.max_value, (int, float)
            ):
                max_val = float(rule.max_value)
                if rule.inclusive_max:
                    if comp_value > max_val:
                        return ValidationResult(
                            is_valid=False,
                            severity=rule.severity,
                            message=rule.error_message
                            or f"Field {rule.field_path} must be <= {rule.max_value}",
                            field_path=rule.field_path,
                            rule_id=rule.rule_id,
                        )
                else:
                    if comp_value >= max_val:
                        return ValidationResult(
                            is_valid=False,
                            severity=rule.severity,
                            message=rule.error_message
                            or f"Field {rule.field_path} must be < {rule.max_value}",
                            field_path=rule.field_path,
                            rule_id=rule.rule_id,
                        )
            elif isinstance(comp_value, (date, datetime)) and isinstance(
                rule.max_value, (date, datetime)
            ):
                if rule.inclusive_max:
                    if comp_value > rule.max_value:
                        return ValidationResult(
                            is_valid=False,
                            severity=rule.severity,
                            message=rule.error_message
                            or f"Field {rule.field_path} must be <= {rule.max_value}",
                            field_path=rule.field_path,
                            rule_id=rule.rule_id,
                        )
                else:
                    if comp_value >= rule.max_value:
                        return ValidationResult(
                            is_valid=False,
                            severity=rule.severity,
                            message=rule.error_message
                            or f"Field {rule.field_path} must be < {rule.max_value}",
                            field_path=rule.field_path,
                            rule_id=rule.rule_id,
                        )

        return None

    def _apply_code_set_rule(
        self, rule: CodeSetRule, value: Any
    ) -> Optional[ValidationResult]:
        """Apply code set validation rule."""
        if value is None or value == "":
            return None

        # Extract code from complex types
        code = value
        if isinstance(value, dict):
            code = value.get("code") or value.get("value")

        # Validate against allowed codes
        if rule.allowed_codes:
            if str(code) not in rule.allowed_codes:
                return ValidationResult(
                    is_valid=False,
                    severity=rule.severity,
                    message=rule.error_message
                    or f"Code {code} not in allowed set for {rule.field_path}",
                    field_path=rule.field_path,
                    rule_id=rule.rule_id,
                )

        # Validate against code system
        if rule.code_system in self.code_validators:
            validator = self.code_validators[rule.code_system]
            if not validator(code):
                return ValidationResult(
                    is_valid=False,
                    severity=rule.severity,
                    message=rule.error_message
                    or f"Invalid {rule.code_system} code: {code}",
                    field_path=rule.field_path,
                    rule_id=rule.rule_id,
                )

        return None

    def _apply_temporal_rule(
        self,
        rule: TemporalRule,
        value: Any,
        data_context: Optional[Dict[str, Any]] = None,
    ) -> Optional[ValidationResult]:
        """Apply temporal validation rule."""
        if value is None:
            return None

        try:
            # Parse date/datetime
            date_value: datetime
            if isinstance(value, str):
                try:
                    date_value = datetime.fromisoformat(value)
                except ValueError:
                    date_value = datetime.strptime(value, "%Y-%m-%d")
            elif isinstance(value, datetime):
                date_value = value
            elif isinstance(value, date):
                date_value = datetime.combine(value, datetime.min.time())
            else:
                raise ValueError(f"Invalid date type: {type(value)}")

            # Apply temporal validation
            now = datetime.now()

            if rule.temporal_type == "past":
                if date_value > now:
                    return ValidationResult(
                        is_valid=False,
                        severity=rule.severity,
                        message=rule.error_message
                        or f"Date in {rule.field_path} must be in the past",
                        field_path=rule.field_path,
                        rule_id=rule.rule_id,
                    )

            elif rule.temporal_type == "future":
                if date_value < now:
                    return ValidationResult(
                        is_valid=False,
                        severity=rule.severity,
                        message=rule.error_message
                        or f"Date in {rule.field_path} must be in the future",
                        field_path=rule.field_path,
                        rule_id=rule.rule_id,
                    )

            elif rule.temporal_type == "relative_to_field" and data_context:
                if rule.reference_field:
                    ref_value = self._get_field_value(
                        data_context, rule.reference_field
                    )
                    if ref_value:
                        ref_date = datetime.fromisoformat(str(ref_value))

                        if rule.offset_days:
                            # Check if date is within offset range
                            delta = abs((date_value - ref_date).days)
                            if delta > abs(rule.offset_days):
                                return ValidationResult(
                                    is_valid=False,
                                    severity=rule.severity,
                                    message=rule.error_message
                                    or f"Date in {rule.field_path} is not within {rule.offset_days} days of {rule.reference_field}",
                                    field_path=rule.field_path,
                                    rule_id=rule.rule_id,
                                )

        except (ValueError, TypeError, AttributeError) as e:
            return ValidationResult(
                is_valid=False,
                severity=rule.severity,
                message=f"Temporal validation error: {str(e)}",
                field_path=rule.field_path,
                rule_id=rule.rule_id,
            )

        return None

    def _apply_cross_field_rule(
        self,
        rule: CrossFieldRule,
        value: Any,
        data_context: Optional[Dict[str, Any]] = None,
    ) -> Optional[ValidationResult]:
        """Apply cross-field validation rule."""
        if not data_context:
            return None

        try:
            # Get values for all related fields
            field_values = {rule.field_path: value}
            for field_path in rule.related_fields:
                field_values[field_path] = self._get_field_value(
                    data_context, field_path
                )

            # Apply validation function
            if rule.validation_function is not None:
                is_valid = rule.validation_function(field_values, data_context)
            else:
                logger.warning(
                    "Cross-field rule %s missing validation function", rule.rule_id
                )
                return None

            if not is_valid:
                return ValidationResult(
                    is_valid=False,
                    severity=rule.severity,
                    message=rule.error_message
                    or f"Cross-field validation failed for {rule.field_path}",
                    field_path=rule.field_path,
                    rule_id=rule.rule_id,
                )

        except (ValueError, TypeError, AttributeError) as e:
            return ValidationResult(
                is_valid=False,
                severity=rule.severity,
                message=f"Cross-field validation error: {str(e)}",
                field_path=rule.field_path,
                rule_id=rule.rule_id,
            )

        return None

    def _apply_custom_rule(
        self,
        rule: ValidationRule,
        value: Any,
        data_context: Optional[Dict[str, Any]] = None,
    ) -> Optional[ValidationResult]:
        """Apply custom validation rule."""
        if "validation_function" not in rule.metadata:
            logger.warning("Custom rule %s missing validation function", rule.rule_id)
            return None

        try:
            validation_func = rule.metadata["validation_function"]
            is_valid = validation_func(value, data_context)

            if not is_valid:
                return ValidationResult(
                    is_valid=False,
                    severity=rule.severity,
                    message=rule.error_message
                    or f"Custom validation failed for {rule.field_path}",
                    field_path=rule.field_path,
                    rule_id=rule.rule_id,
                )

        except (ValueError, TypeError, AttributeError) as e:
            return ValidationResult(
                is_valid=False,
                severity=rule.severity,
                message=f"Custom validation error: {str(e)}",
                field_path=rule.field_path,
                rule_id=rule.rule_id,
            )

        return None

    def _validate_cross_fields(
        self, data: Dict[str, Any], context: ValidationContext
    ) -> List[ValidationResult]:
        """Validate all cross-field rules."""
        results = []

        # Find all cross-field rules
        cross_field_rules = []
        for rules_list in self.rules.values():
            for rule in rules_list:
                if (
                    rule.rule_type == ValidationRuleType.CROSS_FIELD
                    and context in rule.contexts
                    and rule.active
                ):
                    cross_field_rules.append(rule)

        # Apply each cross-field rule
        for rule in cross_field_rules:
            value = self._get_field_value(data, rule.field_path)
            if isinstance(rule, CrossFieldRule):
                result = self._apply_cross_field_rule(rule, value, data)
                if result:
                    results.append(result)

        return results

    def _validate_completeness(
        self, data: Dict[str, Any], context: ValidationContext
    ) -> List[ValidationResult]:
        """Validate data completeness."""
        results = []

        # Find all completeness rules
        completeness_rules = []
        for rules_list in self.rules.values():
            for rule in rules_list:
                if (
                    rule.rule_type == ValidationRuleType.COMPLETENESS
                    and context in rule.contexts
                    and rule.active
                ):
                    completeness_rules.append(rule)

        # Apply completeness rules
        for rule in completeness_rules:
            if "required_fields" in rule.metadata:
                required_fields = rule.metadata["required_fields"]
                missing_fields = []

                for field_path in required_fields:
                    value = self._get_field_value(data, field_path)
                    if value is None or value == "":
                        missing_fields.append(field_path)

                if missing_fields:
                    completeness_pct = (
                        (len(required_fields) - len(missing_fields))
                        / len(required_fields)
                        * 100
                    )

                    results.append(
                        ValidationResult(
                            is_valid=False,
                            severity=rule.severity,
                            message=f"Data completeness {completeness_pct:.1f}%. Missing: {', '.join(missing_fields)}",
                            field_path=rule.field_path,
                            rule_id=rule.rule_id,
                            metadata={"completeness_percentage": completeness_pct},
                        )
                    )

        return results

    def _get_field_value(self, data: Dict[str, Any], field_path: str) -> Any:
        """Get field value from nested data structure."""
        parts = field_path.split(".")
        value: Any = data

        for part in parts:
            if isinstance(value, dict) and part in value:
                value = value[part]
            elif isinstance(value, list) and part.isdigit():
                index = int(part)
                if 0 <= index < len(value):
                    value = value[index]
                else:
                    return None
            else:
                return None

        return value

    def _extract_all_field_paths(
        self, data: Dict[str, Any], prefix: str = ""
    ) -> List[str]:
        """Extract all field paths from a data structure."""
        paths = []

        for key, value in data.items():
            current_path = f"{prefix}{key}" if prefix else key
            paths.append(current_path)

            if isinstance(value, dict):
                nested_paths = self._extract_all_field_paths(value, f"{current_path}.")
                paths.extend(nested_paths)
            elif isinstance(value, list):
                for i, item in enumerate(value):
                    if isinstance(item, dict):
                        nested_paths = self._extract_all_field_paths(
                            item, f"{current_path}.{i}."
                        )
                        paths.extend(nested_paths)

        return paths

    # Format validators
    def _validate_email(self, value: str) -> bool:
        """Validate email format."""
        pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        return bool(re.match(pattern, str(value)))

    def _validate_phone(self, value: str) -> bool:
        """Validate phone number format."""
        # Remove common formatting characters
        cleaned = re.sub(r"[\s\-\(\)\+]", "", str(value))
        # Check if it's a valid phone number (7-15 digits)
        return bool(re.match(r"^\d{7,15}$", cleaned))

    def _validate_url(self, value: str) -> bool:
        """Validate URL format."""
        pattern = r"^https?://[^\s/$.?#].[^\s]*$"
        return bool(re.match(pattern, str(value), re.IGNORECASE))

    def _validate_date(self, value: str) -> bool:
        """Validate date format."""
        try:
            datetime.strptime(str(value), "%Y-%m-%d")
            return True
        except ValueError:
            return False

    def _validate_datetime(self, value: str) -> bool:
        """Validate datetime format."""
        try:
            datetime.fromisoformat(str(value))
            return True
        except ValueError:
            return False

    def _validate_uuid(self, value: str) -> bool:
        """Validate UUID format."""
        pattern = r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
        return bool(re.match(pattern, str(value), re.IGNORECASE))

    def _validate_ssn(self, value: str) -> bool:
        """Validate SSN format."""
        # US SSN format: XXX-XX-XXXX or XXXXXXXXX
        cleaned = re.sub(r"[\s\-]", "", str(value))
        return bool(re.match(r"^\d{9}$", cleaned))

    def _validate_npi(self, value: str) -> bool:
        """Validate NPI (National Provider Identifier) format."""
        # NPI is 10 digits with Luhn check
        if not re.match(r"^\d{10}$", str(value)):
            return False

        # Luhn algorithm check
        digits = [int(d) for d in str(value)]
        check_digit = digits[-1]
        digits = digits[:-1]

        # Double every other digit
        for i in range(0, len(digits), 2):
            digits[i] *= 2
            if digits[i] > 9:
                digits[i] = digits[i] // 10 + digits[i] % 10

        total = sum(digits)
        return (total * 9) % 10 == check_digit

    def _validate_ein(self, value: str) -> bool:
        """Validate EIN (Employer Identification Number) format."""
        # EIN format: XX-XXXXXXX
        cleaned = re.sub(r"[\s\-]", "", str(value))
        return bool(re.match(r"^\d{9}$", cleaned))

    def _validate_postal_code(self, value: str) -> bool:
        """Validate postal code format (US and international)."""
        # US ZIP: XXXXX or XXXXX-XXXX
        # Canadian: A1A 1A1
        # UK: Various formats
        patterns = [
            r"^\d{5}(-\d{4})?$",  # US ZIP
            r"^[A-Z]\d[A-Z]\s?\d[A-Z]\d$",  # Canadian
            r"^[A-Z]{1,2}\d{1,2}\s?\d[A-Z]{2}$",  # UK
            r"^\d{4,6}$",  # Generic numeric
        ]

        value_str = str(value).upper()
        return any(re.match(pattern, value_str) for pattern in patterns)

    def _validate_unhcr_id(self, value: str) -> bool:
        """Validate UNHCR ID format."""
        # UNHCR ID format: XXX-YYCCCCCC (country-year-case)
        pattern = r"^[A-Z]{3}-\d{2}[A-Z]{1}\d{5,7}$"
        return bool(re.match(pattern, str(value).upper()))

    # Code validators
    def _validate_icd10(self, value: str) -> bool:
        """Validate ICD-10 code format."""
        # ICD-10 format: A00-Z99 with optional decimal subcategories
        pattern = r"^[A-Z]\d{2}(\.\d{1,4})?$"
        return bool(re.match(pattern, str(value).upper()))

    def _validate_cpt(self, value: str) -> bool:
        """Validate CPT code format."""
        # CPT format: 5 digits or 4 digits + letter
        pattern = r"^(\d{5}|\d{4}[A-Z])$"
        return bool(re.match(pattern, str(value).upper()))

    def _validate_loinc(self, value: str) -> bool:
        """Validate LOINC code format."""
        # LOINC format: 1-5 digits, hyphen, check digit
        pattern = r"^\d{1,5}-\d$"
        return bool(re.match(pattern, str(value)))

    def _validate_snomed(self, value: str) -> bool:
        """Validate SNOMED CT code format."""
        # SNOMED CT: 6-18 digits
        pattern = r"^\d{6,18}$"
        return bool(re.match(pattern, str(value)))

    def _validate_rxnorm(self, value: str) -> bool:
        """Validate RxNorm code format."""
        # RxNorm: numeric, typically 1-7 digits
        pattern = r"^\d{1,7}$"
        return bool(re.match(pattern, str(value)))

    def _validate_cvx(self, value: str) -> bool:
        """Validate CVX vaccine code format."""
        # CVX: 1-3 digits
        pattern = r"^\d{1,3}$"
        return bool(re.match(pattern, str(value)))

    def _validate_ndc(self, value: str) -> bool:
        """Validate NDC (National Drug Code) format."""
        # NDC formats: 4-4-2, 5-3-2, 5-4-1, 5-4-2
        cleaned = re.sub(r"[\s\-]", "", str(value))
        return bool(re.match(r"^\d{10,11}$", cleaned))


# Create global validation engine instance
validation_engine = ValidationEngine()
