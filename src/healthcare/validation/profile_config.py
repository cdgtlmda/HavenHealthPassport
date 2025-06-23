"""FHIR Profile Validation Configuration.

This module configures and manages FHIR profile validation for healthcare
standards compliance in the Haven Health Passport system.
All PHI data is encrypted and access is controlled through role-based permissions.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
from uuid import uuid4

from src.healthcare.fhir_profiles import (
    REFUGEE_CONDITION_PROFILE as CONDITION_PROFILE_URL,
)
from src.healthcare.fhir_profiles import (
    REFUGEE_DIAGNOSTIC_REPORT_PROFILE as DIAGNOSTIC_REPORT_PROFILE_URL,
)
from src.healthcare.fhir_profiles import (
    REFUGEE_MEDICATION_REQUEST_PROFILE as MEDICATION_REQUEST_PROFILE_URL,
)
from src.healthcare.fhir_profiles import (
    REFUGEE_OBSERVATION_PROFILE as OBSERVATION_PROFILE_URL,
)
from src.healthcare.fhir_profiles import REFUGEE_PATIENT_PROFILE as PATIENT_PROFILE_URL
from src.healthcare.fhir_profiles import (
    REFUGEE_PROCEDURE_PROFILE as PROCEDURE_PROFILE_URL,
)
from src.healthcare.validation.fhir_validators import (
    FHIRValidator,
    ValidationIssue,
    ValidationProfile,
    ValidationSeverity,
    ValidationType,
)

logger = logging.getLogger(__name__)


class ProfileValidationConfig:
    """Configuration for FHIR profile validation."""

    def __init__(self) -> None:
        """Initialize profile validation configuration."""
        self.validator = FHIRValidator()
        self.profiles: Dict[str, ValidationProfile] = {}
        self.profile_mappings: Dict[str, str] = {}
        self.validation_rules: Dict[str, List[Dict[str, Any]]] = {}
        self.custom_value_sets: Dict[str, Set[str]] = {}
        self.validation_options: Dict[str, Any] = {
            "strict_mode": False,
            "warn_on_unknown_extensions": True,
            "require_narrative": False,
            "validate_references": True,
            "check_cardinality": True,
            "validate_terminology": True,
        }

        # Initialize profiles
        self._initialize_core_profiles()
        self._initialize_healthcare_profiles()
        self._load_custom_value_sets()

    def _initialize_core_profiles(self) -> None:
        """Initialize core FHIR profiles."""
        # Base resource profiles
        base_profiles = {
            "Patient": self._create_patient_profile(),
            "Observation": self._create_observation_profile(),
            "Condition": self._create_condition_profile(),
            "MedicationRequest": self._create_medication_request_profile(),
            "Procedure": self._create_procedure_profile(),
            "DiagnosticReport": self._create_diagnostic_report_profile(),
        }

        for resource_type, profile in base_profiles.items():
            self.profiles[profile.url] = profile
            self.profile_mappings[resource_type] = profile.url
            self.validator.register_profile(profile)

    def _initialize_healthcare_profiles(self) -> None:
        """Initialize healthcare-specific profiles."""
        # Haven Health Passport specific profiles
        haven_profiles = {
            "RefugeePatient": self._create_refugee_patient_profile(),
            "VitalSignsObservation": self._create_vital_signs_profile(),
            "ImmunizationRecord": self._create_immunization_profile(),
            "EmergencyContact": self._create_emergency_contact_profile(),
        }

        for _, profile in haven_profiles.items():
            self.profiles[profile.url] = profile
            self.validator.register_profile(profile)

    def _create_patient_profile(self) -> ValidationProfile:
        """Create patient validation profile."""
        profile = ValidationProfile(
            profile_id="patient-base",
            name="Base Patient Profile",
            resource_type="Patient",
            url=PATIENT_PROFILE_URL,
            version="1.0.0",
        )

        # Required elements
        profile.add_constraint("Patient.identifier", min_cardinality=1)
        profile.add_constraint("Patient.name", min_cardinality=1)
        profile.add_constraint(
            "Patient.gender",
            min_cardinality=1,
            value_set="http://hl7.org/fhir/ValueSet/administrative-gender",
        )
        profile.add_constraint("Patient.birthDate", min_cardinality=1)

        # Recommended elements
        profile.add_constraint("Patient.communication", min_cardinality=0)
        profile.add_constraint("Patient.contact", min_cardinality=0)

        # Invariants
        profile.add_invariant(
            key="pat-1",
            description="Patient name must have either family or given name",
            expression="Patient.name.family.exists() or Patient.name.given.exists()",
            severity=ValidationSeverity.ERROR,
        )

        return profile

    def _create_observation_profile(self) -> ValidationProfile:
        """Create observation validation profile."""
        profile = ValidationProfile(
            profile_id="observation-base",
            name="Base Observation Profile",
            resource_type="Observation",
            url=OBSERVATION_PROFILE_URL,
            version="1.0.0",
        )

        # Required elements
        profile.add_constraint(
            "Observation.status",
            min_cardinality=1,
            value_set="http://hl7.org/fhir/ValueSet/observation-status",
        )
        profile.add_constraint("Observation.code", min_cardinality=1)
        profile.add_constraint("Observation.subject", min_cardinality=1)

        # Must have value or reason for no value
        profile.add_invariant(
            key="obs-1",
            description="Observation must have value or dataAbsentReason",
            expression="Observation.value.exists() or Observation.dataAbsentReason.exists()",
            severity=ValidationSeverity.ERROR,
        )

        return profile

    def _create_condition_profile(self) -> ValidationProfile:
        """Create condition validation profile."""
        profile = ValidationProfile(
            profile_id="condition-base",
            name="Base Condition Profile",
            resource_type="Condition",
            url=CONDITION_PROFILE_URL,
            version="1.0.0",
        )

        # Required elements
        profile.add_constraint("Condition.code", min_cardinality=1)
        profile.add_constraint("Condition.subject", min_cardinality=1)
        profile.add_constraint(
            "Condition.clinicalStatus",
            min_cardinality=0,
            value_set="http://terminology.hl7.org/CodeSystem/condition-clinical",
        )

        return profile

    def _create_medication_request_profile(self) -> ValidationProfile:
        """Create medication request validation profile."""
        profile = ValidationProfile(
            profile_id="medication-request-base",
            name="Base MedicationRequest Profile",
            resource_type="MedicationRequest",
            url=MEDICATION_REQUEST_PROFILE_URL,
            version="1.0.0",
        )

        # Required elements
        profile.add_constraint(
            "MedicationRequest.status",
            min_cardinality=1,
            value_set="http://hl7.org/fhir/ValueSet/medicationrequest-status",
        )
        profile.add_constraint("MedicationRequest.intent", min_cardinality=1)
        profile.add_constraint(
            "MedicationRequest.medicationCodeableConcept", min_cardinality=1
        )
        profile.add_constraint("MedicationRequest.subject", min_cardinality=1)
        profile.add_constraint("MedicationRequest.authoredOn", min_cardinality=1)

        # Dosage instructions required
        profile.add_constraint("MedicationRequest.dosageInstruction", min_cardinality=1)

        return profile

    def _create_procedure_profile(self) -> ValidationProfile:
        """Create procedure validation profile."""
        profile = ValidationProfile(
            profile_id="procedure-base",
            name="Base Procedure Profile",
            resource_type="Procedure",
            url=PROCEDURE_PROFILE_URL,
            version="1.0.0",
        )

        # Required elements
        profile.add_constraint("Procedure.status", min_cardinality=1)
        profile.add_constraint("Procedure.subject", min_cardinality=1)
        profile.add_constraint("Procedure.code", min_cardinality=1)
        profile.add_constraint("Procedure.performedDateTime", min_cardinality=0)

        return profile

    def _create_diagnostic_report_profile(self) -> ValidationProfile:
        """Create diagnostic report validation profile."""
        profile = ValidationProfile(
            profile_id="diagnostic-report-base",
            name="Base DiagnosticReport Profile",
            resource_type="DiagnosticReport",
            url=DIAGNOSTIC_REPORT_PROFILE_URL,
            version="1.0.0",
        )

        # Required elements
        profile.add_constraint("DiagnosticReport.status", min_cardinality=1)
        profile.add_constraint("DiagnosticReport.code", min_cardinality=1)
        profile.add_constraint("DiagnosticReport.subject", min_cardinality=1)
        profile.add_constraint("DiagnosticReport.issued", min_cardinality=1)

        return profile

    def _create_refugee_patient_profile(self) -> ValidationProfile:
        """Create refugee patient validation profile."""
        profile = ValidationProfile(
            profile_id="refugee-patient",
            name="Refugee Patient Profile",
            resource_type="Patient",
            url="https://havenhealthpassport.org/fhir/StructureDefinition/refugee-patient",
            version="1.0.0",
        )

        # Inherit from base patient
        profile.add_constraint("Patient.identifier", min_cardinality=1)
        profile.add_constraint("Patient.name", min_cardinality=1)
        profile.add_constraint("Patient.gender", min_cardinality=1)
        profile.add_constraint("Patient.birthDate", min_cardinality=1)

        # Additional requirements
        profile.add_constraint("Patient.communication", min_cardinality=1)
        profile.add_constraint(
            "Patient.extension", min_cardinality=1
        )  # For refugee status

        return profile

    def _create_vital_signs_profile(self) -> ValidationProfile:
        """Create vital signs observation profile."""
        profile = ValidationProfile(
            profile_id="vital-signs",
            name="Vital Signs Profile",
            resource_type="Observation",
            url="https://havenhealthpassport.org/fhir/StructureDefinition/vital-signs",
            version="1.0.0",
        )

        # Base observation requirements
        profile.add_constraint("Observation.status", min_cardinality=1)
        profile.add_constraint("Observation.category", min_cardinality=1)
        profile.add_constraint(
            "Observation.code",
            min_cardinality=1,
            value_set="http://hl7.org/fhir/ValueSet/observation-vitalsignresult",
        )
        profile.add_constraint("Observation.subject", min_cardinality=1)
        profile.add_constraint("Observation.effectiveDateTime", min_cardinality=1)
        profile.add_constraint("Observation.valueQuantity", min_cardinality=1)

        return profile

    def _create_immunization_profile(self) -> ValidationProfile:
        """Create immunization record profile."""
        profile = ValidationProfile(
            profile_id="immunization-record",
            name="Immunization Record Profile",
            resource_type="Immunization",
            url="https://havenhealthpassport.org/fhir/StructureDefinition/immunization-record",
            version="1.0.0",
        )

        # Required elements
        profile.add_constraint("Immunization.status", min_cardinality=1)
        profile.add_constraint("Immunization.vaccineCode", min_cardinality=1)
        profile.add_constraint("Immunization.patient", min_cardinality=1)
        profile.add_constraint("Immunization.occurrenceDateTime", min_cardinality=1)

        return profile

    def _create_emergency_contact_profile(self) -> ValidationProfile:
        """Create emergency contact profile."""
        profile = ValidationProfile(
            profile_id="emergency-contact",
            name="Emergency Contact Profile",
            resource_type="RelatedPerson",
            url="https://havenhealthpassport.org/fhir/StructureDefinition/emergency-contact",
            version="1.0.0",
        )

        # Required elements
        profile.add_constraint("RelatedPerson.patient", min_cardinality=1)
        profile.add_constraint("RelatedPerson.relationship", min_cardinality=1)
        profile.add_constraint("RelatedPerson.name", min_cardinality=1)
        profile.add_constraint("RelatedPerson.telecom", min_cardinality=1)

        return profile

    def _load_custom_value_sets(self) -> None:
        """Load custom value sets for validation."""
        # Language codes for refugees
        self.custom_value_sets["language-codes"] = {
            "en",
            "ar",
            "fr",
            "es",
            "sw",
            "am",
            "ti",
            "so",
            "ur",
            "ps",
            "fa",
            "ku",
            "tr",
            "bn",
            "hi",
            "ta",
            "my",
            "th",
            "vi",
            "zh",
        }

        # Refugee status codes
        self.custom_value_sets["refugee-status"] = {
            "refugee",
            "asylum-seeker",
            "idp",
            "stateless",
            "returnee",
        }

        # Emergency relationship types
        self.custom_value_sets["emergency-relationship"] = {
            "spouse",
            "parent",
            "child",
            "sibling",
            "friend",
            "guardian",
            "emergency",
            "next-of-kin",
            "case-worker",
        }

        # Register with validator
        for name, codes in self.custom_value_sets.items():
            url = f"https://havenhealthpassport.org/ValueSet/{name}"
            self.validator.register_value_set(url, codes)

    def add_validation_rule(
        self, resource_type: str, rule_name: str, rule_config: Dict[str, Any]
    ) -> None:
        """Add custom validation rule.

        Args:
            resource_type: Resource type
            rule_name: Rule name
            rule_config: Rule configuration
        """
        if resource_type not in self.validation_rules:
            self.validation_rules[resource_type] = []

        rule_config["name"] = rule_name
        rule_config["active"] = rule_config.get("active", True)
        self.validation_rules[resource_type].append(rule_config)

        logger.info("Added validation rule '%s' for %s", rule_name, resource_type)

    def set_validation_option(self, option: str, value: Any) -> None:
        """Set validation option.

        Args:
            option: Option name
            value: Option value
        """
        if option in self.validation_options:
            self.validation_options[option] = value
            logger.info("Set validation option '%s' to %s", option, value)
        else:
            logger.warning("Unknown validation option: %s", option)

    def validate_with_profile(
        self, resource: Dict[str, Any], profile_url: Optional[str] = None
    ) -> Tuple[bool, List[Any]]:
        """Validate resource with profile.

        Args:
            resource: FHIR resource
            profile_url: Profile URL (auto-detect if None)

        Returns:
            Tuple of (is_valid, issues)
        """
        # Auto-detect profile if not specified
        if not profile_url:
            resource_type = resource.get("resourceType")
            profile_url = (
                self.profile_mappings.get(resource_type) if resource_type else None
            )

            # Check meta.profile
            if not profile_url and "meta" in resource and "profile" in resource["meta"]:
                profiles = resource["meta"]["profile"]
                if profiles and isinstance(profiles, list):
                    profile_url = profiles[0]

        # Apply validation options
        strict = self.validation_options.get("strict_mode", False)

        # Validate
        is_valid, issues = self.validator.validate_resource(
            resource, profile_url, strict
        )

        # Apply custom rules
        resource_type = resource.get("resourceType")
        if resource_type in self.validation_rules:
            for rule in self.validation_rules[resource_type]:
                if rule.get("active", True):
                    rule_issues = self._apply_custom_rule(resource, rule)
                    issues.extend(rule_issues)
                    if any(
                        issue.severity == ValidationSeverity.ERROR
                        for issue in rule_issues
                    ):
                        is_valid = False

        return is_valid, issues

    def validate_bundle_with_profiles(
        self, bundle: Dict[str, Any]
    ) -> Tuple[bool, Dict[str, List[Any]]]:
        """Validate bundle with appropriate profiles.

        Args:
            bundle: FHIR bundle

        Returns:
            Tuple of (is_valid, issues_by_entry)
        """
        # Build profile map from known mappings
        profile_map = {}

        entries = bundle.get("entry", [])
        for entry in entries:
            resource = entry.get("resource", {})
            resource_type = resource.get("resourceType")

            if resource_type in self.profile_mappings:
                profile_map[resource_type] = self.profile_mappings[resource_type]

        # Validate bundle
        return self.validator.validate_bundle(bundle, profile_map)

    def _apply_custom_rule(
        self, resource: Dict[str, Any], rule: Dict[str, Any]
    ) -> List[Any]:
        """Apply custom validation rule.

        Args:
            resource: FHIR resource
            rule: Validation rule

        Returns:
            Validation issues
        """
        issues = []

        # Example custom rules
        if rule["name"] == "require-documentation":
            if "text" not in resource or not resource["text"].get("div"):
                issues.append(
                    ValidationIssue(
                        ValidationSeverity.WARNING,
                        ValidationType.BUSINESS_RULE,
                        "Resource.text",
                        "Resource should include narrative documentation",
                    )
                )

        elif rule["name"] == "refugee-identifier":
            if resource.get("resourceType") == "Patient":
                has_refugee_id = False
                for identifier in resource.get("identifier", []):
                    if (
                        identifier.get("system")
                        == "https://havenhealthpassport.org/refugee-id"
                    ):
                        has_refugee_id = True
                        break

                if not has_refugee_id:
                    issues.append(
                        ValidationIssue(
                            ValidationSeverity.ERROR,
                            ValidationType.BUSINESS_RULE,
                            "Patient.identifier",
                            "Refugee patients must have a refugee ID",
                        )
                    )

        return issues

    def export_profile_definitions(self, output_dir: Path) -> None:
        """Export profile definitions to files.

        Args:
            output_dir: Output directory
        """
        output_dir.mkdir(parents=True, exist_ok=True)

        for _, profile in self.profiles.items():
            # Create StructureDefinition
            structure_def = {
                "resourceType": "StructureDefinition",
                "id": profile.profile_id,
                "url": profile.url,
                "version": profile.version,
                "name": profile.name,
                "status": "active",
                "kind": "resource",
                "abstract": False,
                "type": profile.resource_type,
                "baseDefinition": f"http://hl7.org/fhir/StructureDefinition/{profile.resource_type}",
                "derivation": "constraint",
                "differential": {"element": self._create_element_definitions(profile)},
            }

            # Write to file
            filename = f"{profile.profile_id}.json"
            output_path = output_dir / filename

            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(structure_def, f, indent=2)

            logger.info("Exported profile %s to %s", profile.name, output_path)

    def _create_element_definitions(
        self, profile: ValidationProfile
    ) -> List[Dict[str, Any]]:
        """Create element definitions for StructureDefinition.

        Args:
            profile: Validation profile

        Returns:
            Element definitions
        """
        elements = []

        # Root element
        elements.append(
            {
                "id": profile.resource_type,
                "path": profile.resource_type,
                "short": profile.name,
                "definition": f"Constraints on {profile.resource_type} for {profile.name}",
            }
        )

        # Constraint elements
        for constraint in profile.constraints:
            element = {
                "id": constraint["path"].replace(".", "-"),
                "path": constraint["path"],
                "min": constraint["min"],
                "max": str(constraint["max"]),
            }

            if constraint.get("valueSet"):
                element["binding"] = {
                    "strength": "required",
                    "valueSet": constraint["valueSet"],
                }

            elements.append(element)

        return elements

    def generate_validation_report(
        self, validation_results: List[Tuple[str, bool, List[Any]]]
    ) -> Dict[str, Any]:
        """Generate validation summary report.

        Args:
            validation_results: List of (resource_id, is_valid, issues)

        Returns:
            Validation report
        """
        report = {
            "report_id": f"VAL-REPORT-{uuid4().hex[:8]}",
            "generated_date": datetime.now().isoformat(),
            "total_resources": len(validation_results),
            "valid_resources": sum(1 for _, valid, _ in validation_results if valid),
            "invalid_resources": sum(
                1 for _, valid, _ in validation_results if not valid
            ),
            "total_issues": sum(len(issues) for _, _, issues in validation_results),
            "issues_by_severity": {"error": 0, "warning": 0, "information": 0},
            "issues_by_type": {},
            "profile_usage": {},
            "common_issues": [],
        }

        # Analyze issues
        issue_counts: Dict[str, int] = {}

        for _, _, issues in validation_results:
            for issue in issues:
                # Count by severity
                severity = issue.severity.value
                report["issues_by_severity"][severity] = (  # type: ignore
                    report["issues_by_severity"].get(severity, 0) + 1  # type: ignore
                )

                # Count by type
                val_type = issue.validation_type.value
                report["issues_by_type"][val_type] = (  # type: ignore
                    report["issues_by_type"].get(val_type, 0) + 1  # type: ignore
                )

                # Track common issues
                issue_key = f"{issue.location}:{issue.message}"
                issue_counts[issue_key] = issue_counts.get(issue_key, 0) + 1

        # Identify most common issues
        sorted_issues = sorted(issue_counts.items(), key=lambda x: x[1], reverse=True)
        report["common_issues"] = [
            {"issue": key, "count": count} for key, count in sorted_issues[:10]
        ]

        # Calculate validation rate
        if report["total_resources"] > 0:  # type: ignore
            report["validation_rate"] = (
                report["valid_resources"] / report["total_resources"] * 100  # type: ignore
            )
        else:
            report["validation_rate"] = 0

        return report


# Export public API
__all__ = ["ProfileValidationConfig"]
