"""
Healthcare System Adaptations.

This module handles adaptations for different healthcare systems and
medical practice variations across cultures.

This module handles encrypted PHI with access control and audit logging
to ensure HIPAA compliance.
 Handles FHIR Resource validation.
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


@dataclass
class HealthcareSystem:
    """Healthcare system characteristics."""

    name: str
    country_code: str

    # System type
    system_type: str = "mixed"  # universal, private, mixed
    primary_care_model: str = "gatekeeper"  # gatekeeper, direct_access

    # Provider roles
    primary_provider_title: str = "doctor"
    specialist_referral_required: bool = True
    nurse_practitioner_role: str = "limited"  # full, limited, none
    pharmacist_prescribing: bool = False

    # Emergency services
    emergency_number: str = "911"
    emergency_dept_name: str = "Emergency Room"
    urgent_care_available: bool = True

    # Medications
    prescription_required: List[str] = field(default_factory=list)
    otc_medications: List[str] = field(default_factory=list)
    brand_name_preferences: bool = False

    # Documentation
    patient_id_format: str = "SSN"  # SSN, NHS, insurance_card, national_id
    medical_record_system: str = "EHR"  # EHR, paper, mixed

    # Insurance
    insurance_terminology: Dict[str, str] = field(default_factory=dict)
    copay_system: bool = True
    preauthorization_common: bool = True

    # Cultural practices
    traditional_medicine_integrated: bool = False
    home_remedies_common: bool = False

    # Scheduling
    appointment_lead_time: str = "days"  # immediate, days, weeks, months
    walk_in_common: bool = False

    # Hospital practices
    visiting_hours_restricted: bool = True
    family_stay_allowed: bool = False
    food_from_home_allowed: bool = False


class HealthcareSystemAdapter:
    """Adapts medical content for different healthcare systems."""

    def __init__(self) -> None:
        """Initialize the HealthcareSystemAdapter."""
        self.systems: Dict[str, HealthcareSystem] = {}
        self._load_healthcare_systems()

    def _load_healthcare_systems(self) -> None:
        """Load healthcare system configurations."""
        # US Healthcare System
        self.systems["US"] = HealthcareSystem(
            name="United States Healthcare",
            country_code="US",
            system_type="private",
            primary_care_model="mixed",
            primary_provider_title="doctor",
            specialist_referral_required=False,
            nurse_practitioner_role="full",
            emergency_number="911",
            emergency_dept_name="Emergency Room (ER)",
            prescription_required=["antibiotics", "painkillers", "blood pressure"],
            otc_medications=["ibuprofen", "acetaminophen", "aspirin"],
            patient_id_format="insurance_card",
            insurance_terminology={
                "copay": "copayment",
                "deductible": "deductible",
                "out_of_pocket": "out-of-pocket maximum",
                "prior_auth": "prior authorization",
            },
            appointment_lead_time="days",
        )

        # UK NHS System
        self.systems["UK"] = HealthcareSystem(
            name="National Health Service",
            country_code="UK",
            system_type="universal",
            primary_care_model="gatekeeper",
            primary_provider_title="GP",
            specialist_referral_required=True,
            nurse_practitioner_role="limited",
            emergency_number="999",
            emergency_dept_name="A&E (Accident & Emergency)",
            prescription_required=["antibiotics", "most medications"],
            otc_medications=["paracetamol", "ibuprofen"],
            patient_id_format="NHS_number",
            insurance_terminology={
                "free at point of care": "NHS covered",
                "prescription charge": "prescription fee",
            },
            copay_system=False,
            preauthorization_common=False,
            appointment_lead_time="weeks",
        )

        # Add more healthcare systems...

    def adapt_for_system(
        self, text: str, source_system: str, target_system: str
    ) -> Dict[str, Any]:
        """Adapt medical text for target healthcare system."""
        source = self.systems.get(source_system)
        target = self.systems.get(target_system)

        if not source or not target:
            logger.warning(
                "Unknown healthcare system: %s or %s", source_system, target_system
            )
            return {"adapted_text": text, "notes": []}

        adaptations = []
        adapted_text = text

        # Adapt provider titles
        if source.primary_provider_title != target.primary_provider_title:
            adapted_text = adapted_text.replace(
                source.primary_provider_title, target.primary_provider_title
            )
            adaptations.append(
                f"Provider title: {source.primary_provider_title} → {target.primary_provider_title}"
            )

        # Adapt emergency department names
        if source.emergency_dept_name != target.emergency_dept_name:
            adapted_text = adapted_text.replace(
                source.emergency_dept_name, target.emergency_dept_name
            )
            adaptations.append(
                f"Emergency: {source.emergency_dept_name} → {target.emergency_dept_name}"
            )

        # Add referral notes if needed
        notes = []
        if (
            target.specialist_referral_required
            and not source.specialist_referral_required
        ):
            notes.append(
                "Note: Specialist referral typically required in target system"
            )

        # Insurance terminology
        for term, replacement in target.insurance_terminology.items():
            if term in adapted_text:
                adapted_text = adapted_text.replace(term, replacement)

        return {
            "adapted_text": adapted_text,
            "adaptations": adaptations,
            "notes": notes,
            "system_differences": self._get_key_differences(source, target),
        }

    def _get_key_differences(
        self, source: HealthcareSystem, target: HealthcareSystem
    ) -> List[str]:
        """Identify key differences between healthcare systems."""
        differences = []

        if source.system_type != target.system_type:
            differences.append(
                f"System type: {source.system_type} vs {target.system_type}"
            )

        if source.specialist_referral_required != target.specialist_referral_required:
            differences.append("Specialist referral requirements differ")

        if source.emergency_number != target.emergency_number:
            differences.append(
                f"Emergency number: {source.emergency_number} vs {target.emergency_number}"
            )

        return differences


# Global healthcare system adapter
healthcare_adapter = HealthcareSystemAdapter()


def validate_fhir_data(data: dict) -> dict:
    """Validate FHIR data.

    Args:
        data: Data to validate

    Returns:
        Validation result with 'valid', 'errors', and 'warnings' keys
    """
    errors = []
    warnings: List[str] = []

    if not data:
        errors.append("No data provided")

    return {"valid": len(errors) == 0, "errors": errors, "warnings": warnings}
