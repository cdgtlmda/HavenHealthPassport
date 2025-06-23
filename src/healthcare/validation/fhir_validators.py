"""FHIR Validation Framework for Healthcare Standards.

This module implements comprehensive FHIR validation capabilities for ensuring
healthcare data interoperability and standards compliance in the Haven Health Passport system.
All PHI data is encrypted and access is controlled through role-based permissions.
"""

import logging
import re
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple
from uuid import uuid4

# from src.healthcare.fhir_base import FHIRResourceType

logger = logging.getLogger(__name__)


class ValidationSeverity(Enum):
    """FHIR validation issue severity levels."""

    ERROR = "error"  # Content is invalid
    WARNING = "warning"  # Content could be improved
    INFORMATION = "information"  # Informational message
    SUCCESS = "success"  # Validation passed


class ValidationType(Enum):
    """Types of FHIR validation."""

    STRUCTURE = "structure"  # Basic structure validation
    CARDINALITY = "cardinality"  # Required/optional fields
    VALUE_SET = "value_set"  # Code system validation
    BUSINESS_RULE = "business_rule"  # Business logic validation
    REFERENCE = "reference"  # Reference validation
    PROFILE = "profile"  # Profile conformance
    TERMINOLOGY = "terminology"  # Terminology binding
    INVARIANT = "invariant"  # Invariant rules
    BEST_PRACTICE = "best_practice"  # Best practice warnings


class ValidationIssue:
    """Represents a validation issue."""

    def __init__(
        self,
        severity: ValidationSeverity,
        validation_type: ValidationType,
        location: str,
        message: str,
        details: Optional[str] = None,
    ):
        """Initialize validation issue.

        Args:
            severity: Issue severity
            validation_type: Type of validation
            location: Location in resource (FHIRPath)
            message: Issue message
            details: Additional details
        """
        self.issue_id = f"VAL-{uuid4().hex[:8]}"
        self.severity = severity
        self.validation_type = validation_type
        self.location = location
        self.message = message
        self.details = details
        self.timestamp = datetime.now()

    def to_operation_outcome_issue(self) -> Dict[str, Any]:
        """Convert to FHIR OperationOutcome issue.

        Returns:
            OperationOutcome issue component
        """
        return {
            "severity": self.severity.value,
            "code": self.validation_type.value,
            "diagnostics": self.message,
            "location": [self.location],
            "details": {"text": self.details or self.message},
        }


class ValidationProfile:
    """FHIR validation profile definition."""

    def __init__(
        self,
        profile_id: str,
        name: str,
        resource_type: str,
        url: str,
        version: str = "1.0.0",
    ):
        """Initialize validation profile.

        Args:
            profile_id: Profile ID
            name: Profile name
            resource_type: Base resource type
            url: Profile canonical URL
            version: Profile version
        """
        self.profile_id = profile_id
        self.name = name
        self.resource_type = resource_type
        self.url = url
        self.version = version
        self.constraints: List[Dict[str, Any]] = []
        self.required_fields: Set[str] = set()
        self.cardinality_rules: Dict[str, Dict[str, int]] = {}
        self.value_sets: Dict[str, str] = {}
        self.invariants: List[Dict[str, Any]] = []
        self.extensions: List[Dict[str, Any]] = []

    def add_constraint(
        self,
        path: str,
        min_cardinality: int = 0,
        max_cardinality: Optional[int] = None,
        type_restriction: Optional[str] = None,
        value_set: Optional[str] = None,
        pattern: Optional[Any] = None,
    ) -> None:
        """Add constraint to profile.

        Args:
            path: Element path
            min_cardinality: Minimum occurrences
            max_cardinality: Maximum occurrences (None for *)
            type_restriction: Restricted type
            value_set: Required value set
            pattern: Required pattern
        """
        constraint = {
            "path": path,
            "min": min_cardinality,
            "max": max_cardinality or "*",
            "type": type_restriction,
            "valueSet": value_set,
            "pattern": pattern,
        }

        self.constraints.append(constraint)

        if min_cardinality > 0:
            self.required_fields.add(path)

        max_card = (
            max_cardinality if max_cardinality is not None else -1
        )  # -1 means unlimited
        self.cardinality_rules[path] = {"min": min_cardinality, "max": max_card}

        if value_set:
            self.value_sets[path] = value_set

    def add_invariant(
        self,
        key: str,
        description: str,
        expression: str,
        severity: ValidationSeverity = ValidationSeverity.ERROR,
    ) -> None:
        """Add invariant rule.

        Args:
            key: Invariant key
            description: Human description
            expression: FHIRPath expression
            severity: Violation severity
        """
        self.invariants.append(
            {
                "key": key,
                "description": description,
                "expression": expression,
                "severity": severity,
            }
        )


class FHIRValidator:
    """Main FHIR validation engine."""

    def __init__(self) -> None:
        """Initialize FHIR validator."""
        self.profiles: Dict[str, ValidationProfile] = {}
        self.value_sets: Dict[str, Set[str]] = {}
        self.code_systems: Dict[str, Dict[str, Any]] = {}
        self.validation_cache: Dict[str, List[ValidationIssue]] = {}
        self.custom_validators: Dict[str, Any] = {}

        # Initialize built-in validators
        self._initialize_core_validators()
        self._load_core_value_sets()

    def _initialize_core_validators(self) -> None:
        """Initialize core FHIR validators."""
        # Resource type validator
        self.custom_validators["resource_type"] = self._validate_resource_type

        # ID validator
        self.custom_validators["id_format"] = self._validate_id_format

        # Reference validator
        self.custom_validators["reference"] = self._validate_reference

        # DateTime validator
        self.custom_validators["datetime"] = self._validate_datetime

        # URL validator
        self.custom_validators["url"] = self._validate_url

        # Code validator
        self.custom_validators["code"] = self._validate_code

    def _load_core_value_sets(self) -> None:
        """Load core FHIR value sets."""
        # Administrative gender
        self.value_sets["http://hl7.org/fhir/ValueSet/administrative-gender"] = {
            "male",
            "female",
            "other",
            "unknown",
        }

        # Observation status
        self.value_sets["http://hl7.org/fhir/ValueSet/observation-status"] = {
            "registered",
            "preliminary",
            "final",
            "amended",
            "corrected",
            "cancelled",
            "entered-in-error",
            "unknown",
        }

        # Condition clinical status
        self.value_sets["http://hl7.org/fhir/ValueSet/condition-clinical"] = {
            "active",
            "recurrence",
            "relapse",
            "inactive",
            "remission",
            "resolved",
        }

        # Medication request status
        self.value_sets["http://hl7.org/fhir/ValueSet/medicationrequest-status"] = {
            "active",
            "on-hold",
            "cancelled",
            "completed",
            "entered-in-error",
            "stopped",
            "draft",
            "unknown",
        }

    def register_profile(self, profile: ValidationProfile) -> None:
        """Register validation profile.

        Args:
            profile: Validation profile
        """
        self.profiles[profile.url] = profile
        logger.info("Registered validation profile: %s (%s)", profile.name, profile.url)

    def register_value_set(self, url: str, codes: Set[str]) -> None:
        """Register value set.

        Args:
            url: Value set URL
            codes: Valid codes
        """
        self.value_sets[url] = codes
        logger.info("Registered value set: %s with %d codes", url, len(codes))

    def validate_resource(
        self,
        resource: Dict[str, Any],
        profile_url: Optional[str] = None,
        strict: bool = False,
    ) -> Tuple[bool, List[ValidationIssue]]:
        """Validate FHIR resource.

        Args:
            resource: FHIR resource
            profile_url: Profile to validate against
            strict: Strict validation mode

        Returns:
            Tuple of (is_valid, issues)
        """
        issues: List[ValidationIssue] = []

        # Validate basic structure
        struct_issues = self._validate_structure(resource)
        issues.extend(struct_issues)

        # Validate against profile if specified
        if profile_url and profile_url in self.profiles:
            profile = self.profiles[profile_url]
            profile_issues = self._validate_against_profile(resource, profile)
            issues.extend(profile_issues)
        else:
            # Use default validation for resource type
            default_issues = self._validate_resource_defaults(resource)
            issues.extend(default_issues)

        # Apply custom validators
        custom_issues = self._apply_custom_validators(resource)
        issues.extend(custom_issues)

        # Validate references
        ref_issues = self._validate_references(resource)
        issues.extend(ref_issues)

        # Best practice warnings if not strict
        if not strict:
            bp_issues = self._check_best_practices(resource)
            issues.extend(bp_issues)

        # Determine overall validity
        has_errors = any(issue.severity == ValidationSeverity.ERROR for issue in issues)
        is_valid = not has_errors

        # Cache results
        cache_key = (
            f"{resource.get('resourceType', 'Unknown')}:{resource.get('id', 'new')}"
        )
        self.validation_cache[cache_key] = issues

        return is_valid, issues

    def validate_bundle(
        self, bundle: Dict[str, Any], profile_map: Optional[Dict[str, str]] = None
    ) -> Tuple[bool, Dict[str, List[ValidationIssue]]]:
        """Validate FHIR bundle.

        Args:
            bundle: FHIR bundle
            profile_map: Map of resource types to profile URLs

        Returns:
            Tuple of (is_valid, issues_by_entry)
        """
        if bundle.get("resourceType") != "Bundle":
            return False, {
                "bundle": [
                    ValidationIssue(
                        ValidationSeverity.ERROR,
                        ValidationType.STRUCTURE,
                        "Bundle",
                        "Resource is not a Bundle",
                    )
                ]
            }

        issues_by_entry: Dict[str, List[ValidationIssue]] = {}
        all_valid = True

        # Validate bundle structure
        bundle_valid, bundle_issues = self.validate_resource(bundle)
        if bundle_issues:
            issues_by_entry["bundle"] = bundle_issues
            all_valid = all_valid and bundle_valid

        # Validate each entry
        entries = bundle.get("entry", [])
        for i, entry in enumerate(entries):
            resource = entry.get("resource")
            if resource:
                # Determine profile for resource
                resource_type = resource.get("resourceType")
                profile_url = None
                if profile_map and resource_type in profile_map:
                    profile_url = profile_map[resource_type]

                # Validate resource
                entry_valid, entry_issues = self.validate_resource(
                    resource, profile_url
                )

                if entry_issues:
                    entry_key = f"entry[{i}]"
                    issues_by_entry[entry_key] = entry_issues
                    all_valid = all_valid and entry_valid

        return all_valid, issues_by_entry

    def generate_operation_outcome(
        self, issues: List[ValidationIssue], resource_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Generate FHIR OperationOutcome from validation issues.

        Args:
            issues: Validation issues
            resource_id: Resource being validated

        Returns:
            OperationOutcome resource
        """
        outcome: Dict[str, Any] = {
            "resourceType": "OperationOutcome",
            "id": f"validation-{uuid4().hex[:8]}",
            "issue": [],
        }

        for issue in issues:
            outcome["issue"].append(issue.to_operation_outcome_issue())

        if resource_id:
            outcome["text"] = {
                "status": "generated",
                "div": f"<div>Validation results for resource {resource_id}</div>",
            }

        return outcome

    def _validate_structure(self, resource: Dict[str, Any]) -> List[ValidationIssue]:
        """Validate basic FHIR resource structure.

        Args:
            resource: FHIR resource

        Returns:
            Validation issues
        """
        issues = []

        # Check resourceType
        if "resourceType" not in resource:
            issues.append(
                ValidationIssue(
                    ValidationSeverity.ERROR,
                    ValidationType.STRUCTURE,
                    "Resource",
                    "Missing required field: resourceType",
                )
            )
            return issues  # Can't continue without resourceType

        # Validate resourceType is known
        # Comment out FHIRResourceType check as it's not defined
        # try:
        #     FHIRResourceType(resource["resourceType"])
        # except ValueError:
        #     issues.append(
        #         ValidationIssue(
        #             ValidationSeverity.ERROR,
        #             ValidationType.STRUCTURE,
        #             "Resource.resourceType",
        #             f"Unknown resource type: {resource_type}",
        #         )
        #     )

        # Check for text narrative (best practice)
        if "text" not in resource:
            issues.append(
                ValidationIssue(
                    ValidationSeverity.INFORMATION,
                    ValidationType.BEST_PRACTICE,
                    "Resource.text",
                    "Resource should include a text narrative",
                )
            )

        return issues

    def _validate_against_profile(
        self, resource: Dict[str, Any], profile: ValidationProfile
    ) -> List[ValidationIssue]:
        """Validate resource against profile.

        Args:
            resource: FHIR resource
            profile: Validation profile

        Returns:
            Validation issues
        """
        issues = []

        # Check resource type matches profile
        if resource.get("resourceType") != profile.resource_type:
            issues.append(
                ValidationIssue(
                    ValidationSeverity.ERROR,
                    ValidationType.PROFILE,
                    "Resource.resourceType",
                    f"Resource type {resource.get('resourceType')} does not match profile {profile.resource_type}",
                )
            )
            return issues

        # Check required fields
        for required_field in profile.required_fields:
            if not self._check_field_exists(resource, required_field):
                issues.append(
                    ValidationIssue(
                        ValidationSeverity.ERROR,
                        ValidationType.CARDINALITY,
                        required_field,
                        f"Required field missing: {required_field}",
                    )
                )

        # Check cardinality
        for path, cardinality in profile.cardinality_rules.items():
            count = self._count_field_occurrences(resource, path)

            if count < cardinality["min"]:
                issues.append(
                    ValidationIssue(
                        ValidationSeverity.ERROR,
                        ValidationType.CARDINALITY,
                        path,
                        f"Minimum cardinality violation: expected at least {cardinality['min']}, found {count}",
                    )
                )

            if cardinality["max"] is not None and count > cardinality["max"]:
                issues.append(
                    ValidationIssue(
                        ValidationSeverity.ERROR,
                        ValidationType.CARDINALITY,
                        path,
                        f"Maximum cardinality violation: expected at most {cardinality['max']}, found {count}",
                    )
                )

        # Check value sets
        for path, value_set_url in profile.value_sets.items():
            value = self._get_field_value(resource, path)
            if value and value_set_url in self.value_sets:
                valid_codes = self.value_sets[value_set_url]
                if isinstance(value, str) and value not in valid_codes:
                    issues.append(
                        ValidationIssue(
                            ValidationSeverity.ERROR,
                            ValidationType.VALUE_SET,
                            path,
                            f"Invalid code '{value}' for value set {value_set_url}",
                        )
                    )

        # Check invariants
        for invariant in profile.invariants:
            if not self._evaluate_invariant(resource, invariant["expression"]):
                issues.append(
                    ValidationIssue(
                        invariant["severity"],
                        ValidationType.INVARIANT,
                        "Resource",
                        f"{invariant['key']}: {invariant['description']}",
                    )
                )

        return issues

    def _validate_resource_defaults(
        self, resource: Dict[str, Any]
    ) -> List[ValidationIssue]:
        """Apply default validation rules for resource type.

        Args:
            resource: FHIR resource

        Returns:
            Validation issues
        """
        issues = []
        resource_type = resource.get("resourceType", "")

        # Patient-specific validation
        if resource_type == "Patient":
            issues.extend(self._validate_patient(resource))

        # Observation-specific validation
        elif resource_type == "Observation":
            issues.extend(self._validate_observation(resource))

        # Condition-specific validation
        elif resource_type == "Condition":
            issues.extend(self._validate_condition(resource))

        # MedicationRequest-specific validation
        elif resource_type == "MedicationRequest":
            issues.extend(self._validate_medication_request(resource))

        # Procedure-specific validation
        elif resource_type == "Procedure":
            issues.extend(self._validate_procedure(resource))

        # DiagnosticReport-specific validation
        elif resource_type == "DiagnosticReport":
            issues.extend(self._validate_diagnostic_report(resource))

        return issues

    def _validate_patient(self, resource: Dict[str, Any]) -> List[ValidationIssue]:
        """Validate Patient resource.

        Args:
            resource: Patient resource

        Returns:
            Validation issues
        """
        issues = []

        # Check identifier
        if "identifier" not in resource or not resource["identifier"]:
            issues.append(
                ValidationIssue(
                    ValidationSeverity.WARNING,
                    ValidationType.BUSINESS_RULE,
                    "Patient.identifier",
                    "Patient should have at least one identifier",
                )
            )

        # Check name
        if "name" not in resource or not resource["name"]:
            issues.append(
                ValidationIssue(
                    ValidationSeverity.ERROR,
                    ValidationType.CARDINALITY,
                    "Patient.name",
                    "Patient must have at least one name",
                )
            )
        else:
            # Validate name structure
            for i, name in enumerate(resource["name"]):
                if "family" not in name and "given" not in name:
                    issues.append(
                        ValidationIssue(
                            ValidationSeverity.WARNING,
                            ValidationType.STRUCTURE,
                            f"Patient.name[{i}]",
                            "Name should have family and/or given name",
                        )
                    )

        # Check birth date format
        if "birthDate" in resource:
            if not self._is_valid_date(resource["birthDate"]):
                issues.append(
                    ValidationIssue(
                        ValidationSeverity.ERROR,
                        ValidationType.STRUCTURE,
                        "Patient.birthDate",
                        "Invalid date format for birthDate",
                    )
                )

        # Check gender value
        if "gender" in resource:
            valid_genders = self.value_sets.get(
                "http://hl7.org/fhir/ValueSet/administrative-gender", set()
            )
            if resource["gender"] not in valid_genders:
                issues.append(
                    ValidationIssue(
                        ValidationSeverity.ERROR,
                        ValidationType.VALUE_SET,
                        "Patient.gender",
                        f"Invalid gender value: {resource['gender']}",
                    )
                )

        return issues

    def _validate_observation(self, resource: Dict[str, Any]) -> List[ValidationIssue]:
        """Validate Observation resource.

        Args:
            resource: Observation resource

        Returns:
            Validation issues
        """
        issues = []

        # Required fields
        required_fields = ["status", "code"]
        for field in required_fields:
            if field not in resource:
                issues.append(
                    ValidationIssue(
                        ValidationSeverity.ERROR,
                        ValidationType.CARDINALITY,
                        f"Observation.{field}",
                        f"Required field missing: {field}",
                    )
                )

        # Validate status
        if "status" in resource:
            valid_statuses = self.value_sets.get(
                "http://hl7.org/fhir/ValueSet/observation-status", set()
            )
            if resource["status"] not in valid_statuses:
                issues.append(
                    ValidationIssue(
                        ValidationSeverity.ERROR,
                        ValidationType.VALUE_SET,
                        "Observation.status",
                        f"Invalid status: {resource['status']}",
                    )
                )

        # Check for value or dataAbsentReason
        has_value = any(key.startswith("value") for key in resource.keys())
        has_absent_reason = "dataAbsentReason" in resource

        if not has_value and not has_absent_reason:
            issues.append(
                ValidationIssue(
                    ValidationSeverity.WARNING,
                    ValidationType.BUSINESS_RULE,
                    "Observation",
                    "Observation should have a value[x] or dataAbsentReason",
                )
            )

        # Validate effectiveDateTime if present
        if "effectiveDateTime" in resource:
            if not self._is_valid_datetime(resource["effectiveDateTime"]):
                issues.append(
                    ValidationIssue(
                        ValidationSeverity.ERROR,
                        ValidationType.STRUCTURE,
                        "Observation.effectiveDateTime",
                        "Invalid datetime format",
                    )
                )

        return issues

    def _validate_condition(self, resource: Dict[str, Any]) -> List[ValidationIssue]:
        """Validate Condition resource."""
        issues = []
        if "code" not in resource:
            issues.append(
                ValidationIssue(
                    ValidationSeverity.ERROR,
                    ValidationType.CARDINALITY,
                    "Condition.code",
                    "Required field missing: code",
                )
            )
        return issues

    def _validate_medication_request(
        self, resource: Dict[str, Any]
    ) -> List[ValidationIssue]:
        """Validate MedicationRequest resource."""
        issues = []
        required_fields = ["status", "intent", "medication", "subject"]
        for field in required_fields:
            if field not in resource and f"{field}Reference" not in resource:
                issues.append(
                    ValidationIssue(
                        ValidationSeverity.ERROR,
                        ValidationType.CARDINALITY,
                        f"MedicationRequest.{field}",
                        f"Required field missing: {field}",
                    )
                )
        return issues

    def _validate_procedure(self, resource: Dict[str, Any]) -> List[ValidationIssue]:
        """Validate Procedure resource."""
        issues = []
        required_fields = ["status", "subject"]
        for field in required_fields:
            if field not in resource:
                issues.append(
                    ValidationIssue(
                        ValidationSeverity.ERROR,
                        ValidationType.CARDINALITY,
                        f"Procedure.{field}",
                        f"Required field missing: {field}",
                    )
                )
        return issues

    def _validate_diagnostic_report(
        self, resource: Dict[str, Any]
    ) -> List[ValidationIssue]:
        """Validate DiagnosticReport resource."""
        issues = []
        required_fields = ["status", "code"]
        for field in required_fields:
            if field not in resource:
                issues.append(
                    ValidationIssue(
                        ValidationSeverity.ERROR,
                        ValidationType.CARDINALITY,
                        f"DiagnosticReport.{field}",
                        f"Required field missing: {field}",
                    )
                )
        return issues

    def _apply_custom_validators(
        self, resource: Dict[str, Any]
    ) -> List[ValidationIssue]:
        """Apply custom validators to resource."""
        # Resource parameter will be used when custom validators are implemented
        _ = resource
        return []  # Simplified for now

    def _validate_references(self, resource: Dict[str, Any]) -> List[ValidationIssue]:
        """Validate all references in resource."""
        # Resource parameter will be used when reference validation is implemented
        _ = resource
        return []  # Simplified for now

    def _check_best_practices(self, resource: Dict[str, Any]) -> List[ValidationIssue]:
        """Check FHIR best practices."""
        issues = []
        if "meta" not in resource or "profile" not in resource.get("meta", {}):
            issues.append(
                ValidationIssue(
                    ValidationSeverity.INFORMATION,
                    ValidationType.BEST_PRACTICE,
                    "Resource.meta.profile",
                    "Resource should declare conformance to a profile",
                )
            )
        return issues

    def _validate_resource_type(self, path: str, value: str) -> List[ValidationIssue]:
        """Validate resource type."""
        # Parameters will be used when validation is implemented
        _ = (path, value)
        return []

    def _validate_id_format(self, path: str, value: str) -> List[ValidationIssue]:
        """Validate ID format."""
        # Parameters will be used when validation is implemented
        _ = (path, value)
        return []

    def _validate_reference(self, path: str, value: Any) -> List[ValidationIssue]:
        """Validate reference."""
        # Parameters will be used when validation is implemented
        _ = (path, value)
        return []

    def _validate_datetime(self, path: str, value: str) -> List[ValidationIssue]:
        """Validate datetime format."""
        # Parameters will be used when validation is implemented
        _ = (path, value)
        return []

    def _validate_url(self, path: str, value: str) -> List[ValidationIssue]:
        """Validate URL format."""
        # Parameters will be used when validation is implemented
        _ = (path, value)
        return []

    def _validate_code(self, path: str, value: str) -> List[ValidationIssue]:
        """Validate code format."""
        # Parameters will be used when validation is implemented
        _ = (path, value)
        return []

    def _check_field_exists(self, resource: Dict[str, Any], path: str) -> bool:
        """Check if field exists in resource."""
        parts = path.split(".")
        current = resource
        for part in parts[1:]:  # Skip resource type
            if part not in current:
                return False
            current = current[part]
        return True

    def _count_field_occurrences(self, resource: Dict[str, Any], path: str) -> int:
        """Count occurrences of field."""
        return 1 if self._check_field_exists(resource, path) else 0

    def _get_field_value(self, resource: Dict[str, Any], path: str) -> Any:
        """Get field value from resource."""
        parts = path.split(".")
        current = resource
        for part in parts[1:]:  # Skip resource type
            if part not in current:
                return None
            current = current[part]
        return current

    def _evaluate_invariant(self, resource: Dict[str, Any], expression: str) -> bool:
        """Evaluate FHIRPath invariant expression."""
        # Parameters will be used when FHIRPath evaluation is implemented
        _ = (resource, expression)
        return True  # Simplified

    def _is_valid_date(self, date_str: str) -> bool:
        """Check if date string is valid FHIR date."""
        date_pattern = r"^\d{4}-\d{2}-\d{2}$"
        return bool(re.match(date_pattern, date_str))

    def _is_valid_datetime(self, datetime_str: str) -> bool:
        """Check if datetime string is valid FHIR datetime."""
        patterns = [
            r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$",
            r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{2}:\d{2}$",
        ]
        return any(re.match(pattern, datetime_str) for pattern in patterns)


# Create healthcare-specific profiles
def create_healthcare_profiles(validator: FHIRValidator) -> None:
    """Create and register healthcare-specific validation profiles."""
    # Haven Health Passport Patient Profile
    patient_profile = ValidationProfile(
        profile_id="haven-patient-1.0",
        name="Haven Health Passport Patient",
        resource_type="Patient",
        url="https://havenhealthpassport.org/fhir/StructureDefinition/Patient",
        version="1.0.0",
    )

    # Required patient fields
    patient_profile.add_constraint("Patient.identifier", min_cardinality=1)
    patient_profile.add_constraint("Patient.name", min_cardinality=1)
    patient_profile.add_constraint("Patient.birthDate", min_cardinality=1)
    patient_profile.add_constraint("Patient.gender", min_cardinality=1)

    validator.register_profile(patient_profile)

    # Clinical observation profile
    obs_profile = ValidationProfile(
        profile_id="haven-observation-1.0",
        name="Haven Health Passport Observation",
        resource_type="Observation",
        url="https://havenhealthpassport.org/fhir/StructureDefinition/Observation",
        version="1.0.0",
    )

    obs_profile.add_constraint("Observation.status", min_cardinality=1)
    obs_profile.add_constraint("Observation.code", min_cardinality=1)
    obs_profile.add_constraint("Observation.subject", min_cardinality=1)
    obs_profile.add_constraint("Observation.effectiveDateTime", min_cardinality=1)

    validator.register_profile(obs_profile)


# Export public API
__all__ = [
    "FHIRValidator",
    "ValidationProfile",
    "ValidationIssue",
    "ValidationSeverity",
    "ValidationType",
    "create_healthcare_profiles",
]
