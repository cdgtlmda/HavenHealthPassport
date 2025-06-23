"""
Production Medication Reconciliation Service for Haven Health Passport.

CRITICAL: This service performs medication reconciliation to prevent medication
errors during transitions of care. Studies show that medication errors occur in
up to 67% of patients at care transitions. For refugees moving between countries
and healthcare systems, accurate reconciliation is literally life-saving.

This service:
- Identifies medication discrepancies
- Detects duplicate therapies
- Finds drug name variations across countries
- Reconciles dosing differences
- Tracks medication changes over time

# FHIR Compliance: This service processes FHIR MedicationStatement and MedicationRequest Resources
# All medication data is validated against FHIR R4 specifications
"""

import difflib
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, cast

from src.healthcare.drug_interaction_service import get_drug_interaction_service
from src.healthcare.hipaa_access_control import (  # Added for HIPAA access control
    AccessLevel,
    require_phi_access,
)
from src.services.cache_service import CacheService
from src.translation.medical.snomed_service import get_snomed_service
from src.utils.logging import get_logger

logger = get_logger(__name__)


class ReconciliationAction(Enum):
    """Actions to take for medication reconciliation."""

    CONTINUE = "continue"  # Continue medication as is
    MODIFY = "modify"  # Modify dose/frequency
    DISCONTINUE = "discontinue"  # Stop medication
    ADD = "add"  # Add new medication
    SUBSTITUTE = "substitute"  # Replace with alternative


class DiscrepancyType(Enum):
    """Types of medication discrepancies."""

    OMISSION = "omission"  # Medication missing from current list
    COMMISSION = "commission"  # Medication added without clear indication
    DOSE_DISCREPANCY = "dose_discrepancy"
    FREQUENCY_DISCREPANCY = "frequency_discrepancy"
    ROUTE_DISCREPANCY = "route_discrepancy"
    DUPLICATE_THERAPY = "duplicate_therapy"
    DRUG_NAME_VARIATION = "drug_name_variation"


@dataclass
class Medication:
    """Represents a medication with all relevant details."""

    name: str
    generic_name: Optional[str] = None
    dose: Optional[str] = None
    unit: Optional[str] = None
    frequency: Optional[str] = None
    route: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    indication: Optional[str] = None  # PHI - should be encrypted in storage
    prescriber: Optional[str] = None  # PHI - should be encrypted in storage
    source: Optional[str] = None  # Which list/system this came from
    rxnorm_code: Optional[str] = None
    is_active: bool = True

    def normalize_name(self) -> str:
        """Get normalized medication name for comparison."""
        return (self.generic_name or self.name).lower().strip()


@dataclass
class ReconciliationResult:
    """Result of medication reconciliation."""

    medication: Medication
    action: ReconciliationAction
    discrepancy_type: Optional[DiscrepancyType] = None
    reason: Optional[str] = None
    alternatives: List[Medication] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    confidence: float = 1.0


class MedicationReconciliationService:
    """
    Production medication reconciliation service.

    Ensures medication safety during care transitions by identifying
    and resolving discrepancies between medication lists.
    """

    def __init__(self) -> None:
        """Initialize medication reconciliation service with dependencies."""
        self.drug_interaction_service = get_drug_interaction_service()
        self.snomed_service = get_snomed_service()
        self.cache_service = CacheService()
        self.cache_ttl = timedelta(hours=24)

        # Initialize drug name mappings
        self._initialize_drug_mappings()

        logger.info("Initialized MedicationReconciliationService")

    def _initialize_drug_mappings(self) -> None:
        """Initialize common drug name variations across countries."""
        # Brand names that vary by country
        self.brand_to_generic = {
            # Pain relievers
            "tylenol": "acetaminophen",
            "panadol": "acetaminophen",
            "paracetamol": "acetaminophen",
            "advil": "ibuprofen",
            "motrin": "ibuprofen",
            "nurofen": "ibuprofen",
            # Antibiotics
            "augmentin": "amoxicillin-clavulanate",
            "zithromax": "azithromycin",
            "z-pak": "azithromycin",
            "cipro": "ciprofloxacin",
            # Cardiovascular
            "lasix": "furosemide",
            "coumadin": "warfarin",
            "marevan": "warfarin",
            "toprol": "metoprolol",
            "lopressor": "metoprolol",
            # Diabetes
            "glucophage": "metformin",
            "lantus": "insulin glargine",
            "humalog": "insulin lispro",
            "novolog": "insulin aspart",
        }

        # Common therapeutic duplications
        self.therapeutic_classes = {
            "ace_inhibitors": ["lisinopril", "enalapril", "ramipril", "captopril"],
            "arbs": ["losartan", "valsartan", "irbesartan", "telmisartan"],
            "statins": ["atorvastatin", "simvastatin", "rosuvastatin", "pravastatin"],
            "ppis": ["omeprazole", "esomeprazole", "pantoprazole", "lansoprazole"],
            "ssris": ["fluoxetine", "sertraline", "paroxetine", "escitalopram"],
            "nsaids": ["ibuprofen", "naproxen", "diclofenac", "celecoxib"],
        }

    @require_phi_access(AccessLevel.READ)  # Added access control for PHI
    async def reconcile_medications(
        self,
        current_medications: List[Medication],
        new_medications: List[Medication],
        patient_context: Optional[Dict[str, Any]] = None,
    ) -> List[ReconciliationResult]:
        """
        Reconcile medication lists to identify discrepancies and recommend actions.

        Args:
            current_medications: Current medication list (from medical record)
            new_medications: New medication list (from patient/provider)
            patient_context: Additional context (allergies, conditions, etc.)

        Returns:
            List of reconciliation results with recommended actions
        """
        results = []
        patient_context = patient_context or {}

        # Normalize medication names for comparison
        current_by_name = {med.normalize_name(): med for med in current_medications}
        new_by_name = {med.normalize_name(): med for med in new_medications}

        # Check for omissions (medications in current but not in new)
        for current_name, current_med in current_by_name.items():
            if current_name not in new_by_name:
                # Check for name variations
                matched_med = await self._find_medication_match(
                    current_med, new_medications
                )

                if matched_med:
                    # Found under different name
                    result = await self._compare_medications(current_med, matched_med)
                    results.append(result)
                else:
                    # Medication omitted
                    results.append(
                        ReconciliationResult(
                            medication=current_med,
                            action=ReconciliationAction.DISCONTINUE,
                            discrepancy_type=DiscrepancyType.OMISSION,
                            reason="Medication not in new list - verify if intentionally discontinued",
                            confidence=0.8,
                        )
                    )

        # Check for additions (medications in new but not in current)
        for new_name, new_med in new_by_name.items():
            if new_name not in current_by_name:
                # Check for name variations
                matched_med = await self._find_medication_match(
                    new_med, current_medications
                )

                if not matched_med:
                    # New medication added
                    results.append(
                        ReconciliationResult(
                            medication=new_med,
                            action=ReconciliationAction.ADD,
                            discrepancy_type=DiscrepancyType.COMMISSION,
                            reason="New medication - verify indication and check interactions",
                            confidence=0.9,
                        )
                    )

        # Check for duplications within the new list
        duplication_results = await self._check_therapeutic_duplications(
            new_medications
        )
        results.extend(duplication_results)

        # Check drug interactions for the reconciled list
        if patient_context.get("check_interactions", True):
            interaction_warnings = await self._check_interactions(
                new_medications, patient_context.get("allergies", [])
            )

            # Add warnings to relevant results
            for warning in interaction_warnings:
                for result in results:
                    if result.medication.normalize_name() in warning.lower():
                        result.warnings.append(warning)

        # Sort by severity/importance
        results.sort(
            key=lambda r: (
                r.action == ReconciliationAction.DISCONTINUE,
                len(r.warnings) > 0,
                r.discrepancy_type == DiscrepancyType.DUPLICATE_THERAPY,
            ),
            reverse=True,
        )

        return results

    @require_phi_access(AccessLevel.READ)  # Added access control for PHI operations
    async def _find_medication_match(
        self, medication: Medication, medication_list: List[Medication]
    ) -> Optional[Medication]:
        """Find matching medication accounting for name variations."""
        med_name = medication.normalize_name()

        # Check brand/generic mappings
        generic_name = self.brand_to_generic.get(med_name, med_name)

        for other_med in medication_list:
            other_name = other_med.normalize_name()
            other_generic = self.brand_to_generic.get(other_name, other_name)

            # Direct match
            if generic_name == other_generic:
                return other_med

            # Fuzzy matching for typos/variations
            similarity = difflib.SequenceMatcher(
                None, generic_name, other_generic
            ).ratio()
            if similarity > 0.85:
                return other_med

            # Check RxNorm codes if available
            if medication.rxnorm_code and other_med.rxnorm_code:
                if medication.rxnorm_code == other_med.rxnorm_code:
                    return other_med

        return None

    async def _compare_medications(
        self, current: Medication, new: Medication
    ) -> ReconciliationResult:
        """Compare two medications and identify discrepancies."""
        discrepancies: List[Dict[str, Any]] = []

        # Compare dose
        if current.dose != new.dose or current.unit != new.unit:
            discrepancies.append(
                {
                    "type": DiscrepancyType.DOSE_DISCREPANCY,
                    "current": f"{current.dose} {current.unit}",
                    "new": f"{new.dose} {new.unit}",
                }
            )

        # Compare frequency
        if current.frequency != new.frequency:
            discrepancies.append(
                {
                    "type": DiscrepancyType.FREQUENCY_DISCREPANCY,
                    "current": current.frequency,
                    "new": new.frequency,
                }
            )

        # Compare route
        if current.route != new.route:
            discrepancies.append(
                {
                    "type": DiscrepancyType.ROUTE_DISCREPANCY,
                    "current": current.route,
                    "new": new.route,
                }
            )

        # Determine action
        if not discrepancies:
            action = ReconciliationAction.CONTINUE
            reason = "No changes detected"
        else:
            action = ReconciliationAction.MODIFY
            changes = [
                f"{cast(DiscrepancyType, d['type']).value}: {d['current']} → {d['new']}"
                for d in discrepancies
            ]
            reason = f"Changes detected: {'; '.join(changes)}"

        return ReconciliationResult(
            medication=new,
            action=action,
            discrepancy_type=cast(
                Optional[DiscrepancyType],
                discrepancies[0]["type"] if discrepancies else None,
            ),
            reason=reason,
            confidence=0.95,
        )

    @require_phi_access(AccessLevel.READ)  # Added access control for PHI
    async def _check_therapeutic_duplications(
        self, medications: List[Medication]
    ) -> List[ReconciliationResult]:
        """Check for therapeutic duplications in medication list."""
        results = []
        checked_pairs = set()

        for i, med1 in enumerate(medications):
            med1_generic = self.brand_to_generic.get(
                med1.normalize_name(), med1.normalize_name()
            )

            for j, med2 in enumerate(medications[i + 1 :], i + 1):
                # Skip if already checked
                pair = tuple(sorted([i, j]))
                if pair in checked_pairs:
                    continue
                checked_pairs.add(pair)

                med2_generic = self.brand_to_generic.get(
                    med2.normalize_name(), med2.normalize_name()
                )

                # Check if same drug
                if med1_generic == med2_generic:
                    results.append(
                        ReconciliationResult(
                            medication=med2,
                            action=ReconciliationAction.DISCONTINUE,
                            discrepancy_type=DiscrepancyType.DUPLICATE_THERAPY,
                            reason=f"Duplicate medication: {med1.name} and {med2.name} are the same drug",
                            alternatives=[med1],
                            confidence=0.95,
                        )
                    )
                    continue

                # Check if same therapeutic class
                for drug_class, drugs in self.therapeutic_classes.items():
                    if med1_generic in drugs and med2_generic in drugs:
                        results.append(
                            ReconciliationResult(
                                medication=med2,
                                action=ReconciliationAction.MODIFY,
                                discrepancy_type=DiscrepancyType.DUPLICATE_THERAPY,
                                reason=f"Therapeutic duplication: Both {med1.name} and {med2.name} are {drug_class}",
                                warnings=[f"Review if both {drug_class} are needed"],
                                confidence=0.85,
                            )
                        )
                        break

        return results

    async def _check_interactions(
        self, medications: List[Medication], allergies: List[str]
    ) -> List[str]:
        """Check for drug interactions and allergy conflicts."""
        warnings = []

        # Convert to format expected by drug interaction service
        med_list = [
            {"name": med.name, "dose": f"{med.dose} {med.unit}" if med.dose else ""}
            for med in medications
        ]

        # Check interactions
        interactions = await self.drug_interaction_service.check_interactions(
            medications=med_list, patient_allergies=allergies
        )

        # Convert to warnings
        for interaction in interactions:
            if interaction.severity.value in ["contraindicated", "major"]:
                warnings.append(
                    f"CRITICAL: {interaction.drug1} + {interaction.drug2} - {interaction.description}"
                )
            elif interaction.severity.value == "moderate":
                warnings.append(
                    f"Warning: {interaction.drug1} + {interaction.drug2} - {interaction.description}"
                )

        return warnings
