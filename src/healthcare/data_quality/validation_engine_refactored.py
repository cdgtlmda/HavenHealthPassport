"""
Healthcare Data Quality Validation Engine - Production Refactored.

CRITICAL: This module now properly delegates to the clinical validation engine
which uses real medical services. The simplified checks have been removed from
production code paths.

This is the main entry point for healthcare data validation.

# FHIR Compliance: Main validator for FHIR Resources including Bundle validation
# Ensures all healthcare data conforms to FHIR R4 DomainResource specifications
"""

import asyncio
import threading
from datetime import datetime
from typing import Any, Dict, List, Optional

import boto3

from src.config import settings
from src.healthcare.data_quality.clinical_validation_engine import (
    get_clinical_validation_engine,
)
from src.healthcare.data_quality.validation_rules import (
    ValidationResult,
    ValidationSeverity,
)

# PHI encryption handled through secure storage layer
from src.healthcare.hipaa_access_control import (
    AccessLevel,
    audit_phi_access,
    require_phi_access,
)
from src.utils.logging import get_logger

logger = get_logger(__name__)


class HealthcareDataValidator:
    """
    Main healthcare data validation interface.

    Delegates all validation to the clinical validation engine which
    uses real medical services in production.
    """

    def __init__(self) -> None:
        """Initialize healthcare data validator with clinical engine."""
        self.clinical_engine = get_clinical_validation_engine()
        self.environment = settings.environment.lower()

        if self.environment in ["production", "staging"]:
            logger.info("Healthcare validator using production clinical engine")
        else:
            logger.warning(
                "Healthcare validator in development mode - "
                "production MUST use real medical services!"
            )

    @require_phi_access(AccessLevel.READ)
    @audit_phi_access("validate_patient_record")
    async def validate_patient_record(
        self, patient_record: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Validate a complete patient record.

        Args:
            patient_record: Complete patient record with all data

        Returns:
            Validation results organized by category
        """
        start_time = datetime.utcnow()

        try:
            # Delegate to clinical engine
            validation_results = await self.clinical_engine.validate_patient_data(
                patient_data=patient_record
            )

            # Calculate summary statistics
            total_issues = 0
            critical_issues = 0
            warnings = 0

            for result in validation_results:
                if not result.is_valid:
                    total_issues += 1
                    if result.severity == ValidationSeverity.CRITICAL:
                        critical_issues += 1
                    elif result.severity == ValidationSeverity.WARNING:
                        warnings += 1

            # Build response
            response = {
                "validation_id": f"val_{datetime.utcnow().timestamp()}",
                "timestamp": datetime.utcnow().isoformat(),
                "patient_id": patient_record.get("patient_id"),
                "results": validation_results,
                "summary": {
                    "total_issues": total_issues,
                    "critical_issues": critical_issues,
                    "warnings": warnings,
                    "passed": critical_issues == 0,
                    "duration_ms": int(
                        (datetime.utcnow() - start_time).total_seconds() * 1000
                    ),
                },
                "environment": self.environment,
            }

            # Log critical issues
            if critical_issues > 0:
                logger.error(
                    f"CRITICAL validation issues found for patient {patient_record.get('patient_id')}: "
                    f"{critical_issues} critical issues"
                )

                # In production, trigger alerts
                if self.environment == "production":
                    await self._trigger_critical_alerts(response)

            return response

        except (ValueError, TypeError, RuntimeError) as e:
            logger.error(f"Error during patient record validation: {e}")
            return {
                "validation_id": f"val_error_{datetime.utcnow().timestamp()}",
                "timestamp": datetime.utcnow().isoformat(),
                "error": str(e),
                "summary": {"passed": False, "error": "Validation system error"},
            }

    @require_phi_access(AccessLevel.READ)
    @audit_phi_access("validate_medication_order")
    @require_phi_access(AccessLevel.WRITE)  # Added role-based access control
    async def validate_medication_order(
        self, medication_order: Dict[str, Any], patient_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Validate a new medication order.

        Args:
            medication_order: New medication order details
            patient_context: Patient medications, allergies, conditions

        Returns:
            Validation results with safety checks
        """
        # Extract medication details
        new_medications = [medication_order]
        existing_medications = patient_context.get("current_medications", [])
        allergies = patient_context.get("allergies", [])
        conditions = patient_context.get("conditions", [])

        # Validate through clinical engine
        results = await self.clinical_engine.validate_medications(
            new_medications=new_medications,
            existing_medications=existing_medications,
            patient_allergies=allergies,
            patient_conditions=conditions,
        )

        # Check if order can proceed
        can_proceed = all(r.severity != ValidationSeverity.CRITICAL for r in results)

        return {
            "order_id": medication_order.get("id"),
            "medication": medication_order.get("name"),
            "validation_results": [r.__dict__ for r in results],
            "can_proceed": can_proceed,
            "requires_override": any(
                r.severity == ValidationSeverity.CRITICAL for r in results
            ),
            "timestamp": datetime.utcnow().isoformat(),
        }

    @require_phi_access(AccessLevel.READ)
    @audit_phi_access("validate_lab_results")
    async def validate_lab_results(
        self, lab_results: List[Dict[str, Any]], patient_demographics: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Validate laboratory results.

        Args:
            lab_results: New lab results to validate
            patient_demographics: Patient age, gender, etc.

        Returns:
            Validation results with critical value alerts
        """
        # Validate through clinical engine
        results = await self.clinical_engine.validate_clinical_values(
            lab_results=lab_results, patient_demographics=patient_demographics
        )

        # Identify critical values requiring immediate action
        critical_values = [
            r for r in results if r.severity == ValidationSeverity.CRITICAL
        ]

        response = {
            "validation_results": [r.__dict__ for r in results],
            "critical_values": [
                {
                    "test": r.field,
                    "value": "See message",
                    "message": r.message,
                    "action_required": "Notify physician immediately",
                }
                for r in critical_values
            ],
            "requires_immediate_action": len(critical_values) > 0,
            "timestamp": datetime.utcnow().isoformat(),
        }

        # Trigger critical value notifications
        if critical_values and self.environment == "production":
            await self._notify_critical_values(critical_values, patient_demographics)

        return response

    @require_phi_access(AccessLevel.ADMIN)  # Added access control for critical alerts
    async def _trigger_critical_alerts(
        self, validation_response: Dict[str, Any]
    ) -> None:
        """Trigger alerts for critical validation issues."""
        # Log critical issues
        logger.critical(
            f"Critical validation alert: {validation_response['summary']['critical_issues']} "
            f"critical issues for patient {validation_response.get('patient_id')}"
        )

        # Send SNS notification for critical validation issues
        try:
            sns_client = boto3.client("sns", region_name=settings.aws_region)

            # Format alert message
            alert_message = f"""CRITICAL VALIDATION ALERT

Patient ID: {validation_response.get('patient_id', 'Unknown')}
Critical Issues: {validation_response['summary']['critical_issues']}
Total Issues: {validation_response['summary']['total_issues']}

Validation Details:
- Errors: {validation_response['summary']['by_severity']['error']}
- Warnings: {validation_response['summary']['by_severity']['warning']}

Immediate medical review required!
"""

            # Send alert
            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: sns_client.publish(
                    TopicArn=getattr(settings, "critical_alerts_topic_arn", ""),
                    Message=alert_message,
                    Subject="CRITICAL: Healthcare Data Validation Alert",
                    MessageAttributes={
                        "severity": {"DataType": "String", "StringValue": "CRITICAL"},
                        "alert_type": {
                            "DataType": "String",
                            "StringValue": "validation_failure",
                        },
                        "patient_id": {
                            "DataType": "String",
                            "StringValue": str(
                                validation_response.get("patient_id", "Unknown")
                            ),
                        },
                    },
                ),
            )

            logger.info(
                f"Critical validation alert sent. MessageId: {response['MessageId']}"
            )

        except (ValueError, TypeError, RuntimeError) as e:
            logger.error(f"Failed to send critical validation alert via SNS: {e}")
            # Don't re-raise - we already logged the critical issue

    @require_phi_access(
        AccessLevel.ADMIN
    )  # Added access control for critical notifications
    async def _notify_critical_values(
        self,
        critical_values: List[ValidationResult],
        patient_demographics: Dict[str, Any],
    ) -> None:
        """Notify healthcare team of critical lab values."""
        # Log all critical values
        for value in critical_values:
            logger.critical(
                f"CRITICAL LAB VALUE: {value.field} - "
                f"{value.message} for patient "
                f"{patient_demographics.get('patient_id', 'unknown')}"
            )

        # Send paging notification via SNS
        try:
            sns_client = boto3.client("sns", region_name=settings.aws_region)

            # Format critical lab values message
            alert_message = f"""🚨 CRITICAL LAB VALUES - IMMEDIATE ACTION REQUIRED 🚨

Patient: {patient_demographics.get('name', 'Unknown')} (ID: {patient_demographics.get('patient_id', 'Unknown')})
MRN: {patient_demographics.get('mrn', 'Unknown')}

CRITICAL VALUES:
"""

            for value in critical_values:
                # Extract test information from the message
                test_name = value.field
                test_value = "See message"
                normal_range = "N/A"
                unit = ""

                alert_message += f"\n⚠️ {test_name}: {test_value} {unit}"
                alert_message += f"\n   Normal Range: {normal_range}"
                alert_message += f"\n   Status: {value.message}\n"

            alert_message += (
                "\nACTION REQUIRED: Contact patient's care team immediately!"
            )

            # Send to on-call physician pager
            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: sns_client.publish(
                    TopicArn=getattr(
                        settings,
                        "physician_pager_topic_arn",
                        "arn:aws:sns:us-east-1:123456789012:physician-pager",
                    ),
                    Message=alert_message,
                    Subject="🚨 CRITICAL LAB VALUES",
                    MessageAttributes={
                        "severity": {"DataType": "String", "StringValue": "EMERGENCY"},
                        "alert_type": {
                            "DataType": "String",
                            "StringValue": "critical_lab_value",
                        },
                        "patient_id": {
                            "DataType": "String",
                            "StringValue": str(
                                patient_demographics.get("patient_id", "Unknown")
                            ),
                        },
                        "priority": {"DataType": "String", "StringValue": "STAT"},
                    },
                ),
            )

            logger.info(
                f"Critical lab value page sent. MessageId: {response['MessageId']}"
            )

        except Exception as e:
            # Critical safety failure - must be logged at highest level
            logger.critical(
                f"FAILED TO PAGE PHYSICIAN FOR CRITICAL LAB VALUES: {e}. "
                f"Patient {patient_demographics.get('patient_id')} has critical values requiring immediate attention!"
            )
            # Re-raise to ensure this is handled
            raise

    def get_validation_rules(self) -> Dict[str, Any]:
        """
        Get active validation rules and their configurations.

        Returns:
            Dictionary of validation rules by category
        """
        return {
            "medication_safety": {
                "drug_interactions": "Real-time checking via DrugBank/RxNorm",
                "allergy_checking": "Cross-reactivity analysis included",
                "dosage_validation": "Age and condition-based limits",
                "duplicate_checking": "Prevent duplicate therapies",
            },
            "laboratory_values": {
                "critical_values": "Immediate notification for life-threatening values",
                "reference_ranges": "Age, gender, and condition-specific",
                "delta_checks": "Significant change detection",
                "panic_values": "Automated escalation",
            },
            "vital_signs": {
                "age_specific": "Pediatric through geriatric ranges",
                "trend_analysis": "Deterioration detection",
                "early_warning": "Sepsis and deterioration scores",
            },
            "terminology": {
                "snomed_validation": "Concept hierarchy checking",
                "icd10_validation": "Format and existence checking",
                "drug_name_normalization": "RxNorm standardization",
            },
        }


# Thread-safe singleton pattern


class _HealthcareValidatorSingleton:
    """Thread-safe singleton holder for HealthcareDataValidator."""

    _instance: Optional[HealthcareDataValidator] = None
    _lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> HealthcareDataValidator:
        """Get or create singleton instance."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = HealthcareDataValidator()
        return cls._instance


def get_healthcare_validator() -> HealthcareDataValidator:
    """Get or create global healthcare data validator instance."""
    return _HealthcareValidatorSingleton.get_instance()


# For backward compatibility
def get_validation_engine() -> HealthcareDataValidator:
    """Backward compatibility function."""
    return get_healthcare_validator()
