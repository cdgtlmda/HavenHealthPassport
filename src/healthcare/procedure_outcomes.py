"""Procedure Outcomes Implementation.

This module defines procedure outcomes, complications, and follow-up requirements
with special considerations for tracking outcomes in resource-limited settings
and refugee healthcare contexts. Handles FHIR Procedure Resource validation.

COMPLIANCE NOTE: This module processes PHI including surgical procedures,
medical interventions, complications, and patient outcomes. All procedure
data must be encrypted at rest and in transit using approved encryption
methods. Access control is mandatory - only authorized healthcare providers
involved in patient care should access procedure records. Audit logs must
track all access to procedure outcome data.
"""

import logging
import re
from datetime import date, datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional

# FHIR resource type for this module
__fhir_resource__ = "Procedure"

logger = logging.getLogger(__name__)


class ProcedureOutcomeCode(Enum):
    """Standard procedure outcome codes."""

    # General outcomes
    SUCCESSFUL = "385669000"  # Successful
    PARTIALLY_SUCCESSFUL = "385670004"  # Partially successful
    UNSUCCESSFUL = "385671000"  # Unsuccessful
    COMPLETED_WITH_COMPLICATIONS = "182842007"  # Completed with complications

    # Clinical outcomes
    RESOLVED = "182840000"  # Problem resolved
    IMPROVED = "385425000"  # Improved
    UNCHANGED = "260388006"  # No change
    DETERIORATED = "230993007"  # Deteriorated

    # Procedural outcomes
    ABORTED = "410546004"  # Procedure aborted
    INCOMPLETE = "255599008"  # Incomplete procedure
    CONVERTED = "443391002"  # Converted to open procedure

    # Patient outcomes
    DISCHARGED = "182840000"  # Discharged
    TRANSFERRED = "107724000"  # Transferred
    DIED = "419099009"  # Patient died
    LEFT_AMA = "225928004"  # Left against medical advice

    # Refugee-specific outcomes
    REFERRED_HIGHER_CARE = "REF001"  # Referred to higher level care
    LOST_TO_FOLLOWUP = "LOST001"  # Lost to follow-up
    RELOCATED = "RELOC001"  # Patient relocated
    REPATRIATED = "REPAT001"  # Patient repatriated


class ComplicationSeverity(Enum):
    """Severity levels for complications."""

    MILD = "mild"  # Mild, self-limiting
    MODERATE = "moderate"  # Moderate, requires intervention
    SEVERE = "severe"  # Severe, life-threatening
    FATAL = "fatal"  # Fatal complication


class CommonComplications:
    """Common complications by procedure type."""

    COMPLICATIONS = {
        # Surgical complications
        "bleeding": {
            "code": "131148009",
            "display": "Bleeding",
            "severity_range": ["mild", "moderate", "severe", "fatal"],
            "procedures": ["surgical", "delivery", "cesarean"],
        },
        "infection": {
            "code": "68566005",
            "display": "Surgical site infection",
            "severity_range": ["mild", "moderate", "severe"],
            "procedures": ["surgical", "wound_suturing", "cesarean"],
        },
        "wound_dehiscence": {
            "code": "225565000",
            "display": "Wound dehiscence",
            "severity_range": ["mild", "moderate", "severe"],
            "procedures": ["surgical", "wound_suturing", "cesarean"],
        },
        # Anesthesia complications
        "anesthesia_reaction": {
            "code": "241938005",
            "display": "Anesthesia reaction",
            "severity_range": ["mild", "moderate", "severe", "fatal"],
            "procedures": ["surgical", "cesarean"],
        },
        # Maternal complications
        "postpartum_hemorrhage": {
            "code": "47821001",
            "display": "Postpartum hemorrhage",
            "severity_range": ["moderate", "severe", "fatal"],
            "procedures": ["delivery", "cesarean"],
        },
        "retained_placenta": {
            "code": "206089005",
            "display": "Retained placenta",
            "severity_range": ["moderate", "severe"],
            "procedures": ["delivery"],
        },
        # Immunization complications
        "allergic_reaction": {
            "code": "419076005",
            "display": "Allergic reaction",
            "severity_range": ["mild", "moderate", "severe"],
            "procedures": ["immunization", "injection"],
        },
        "injection_site_reaction": {
            "code": "95376002",
            "display": "Injection site reaction",
            "severity_range": ["mild", "moderate"],
            "procedures": ["immunization", "injection"],
        },
        # Field-specific complications
        "inadequate_sterility": {
            "code": "FIELD001",
            "display": "Procedure performed under non-sterile conditions",
            "severity_range": ["mild", "moderate", "severe"],
            "procedures": ["field_surgery", "emergency"],
        },
        "equipment_failure": {
            "code": "FIELD002",
            "display": "Equipment failure during procedure",
            "severity_range": ["mild", "moderate", "severe"],
            "procedures": ["field_surgery", "emergency"],
        },
    }

    @classmethod
    def get_complication_info(cls, complication_name: str) -> Optional[Dict]:
        """Get information about a complication."""
        return cls.COMPLICATIONS.get(complication_name.lower().replace(" ", "_"))

    @classmethod
    def get_complications_for_procedure(cls, procedure_type: str) -> List[Dict]:
        """Get potential complications for a procedure type."""
        complications = []

        for comp_name, comp_info in cls.COMPLICATIONS.items():
            if procedure_type.lower() in [p.lower() for p in comp_info["procedures"]]:
                complications.append({"name": comp_name, "info": comp_info})

        return complications


class FollowUpRequirement(Enum):
    """Types of follow-up requirements."""

    # Timing-based
    ROUTINE = "routine"  # Routine follow-up
    URGENT = "urgent"  # Urgent follow-up needed
    SCHEDULED = "scheduled"  # Scheduled follow-up
    PRN = "prn"  # As needed

    # Type-based
    WOUND_CHECK = "wound-check"  # Wound check
    SUTURE_REMOVAL = "suture-removal"  # Suture removal
    MEDICATION_REVIEW = "medication-review"  # Medication review
    LAB_RESULTS = "lab-results"  # Lab results review
    IMAGING_REVIEW = "imaging-review"  # Imaging review

    # Specialty referral
    SPECIALIST_REFERRAL = "specialist"  # Specialist referral
    MENTAL_HEALTH = "mental-health"  # Mental health follow-up
    NUTRITION = "nutrition"  # Nutrition follow-up

    # Community-based
    COMMUNITY_HEALTH = "community"  # Community health worker
    HOME_VISIT = "home-visit"  # Home visit required


class ProcedureOutcome:
    """Represents a procedure outcome with complications and follow-up."""

    # FHIR resource type
    __fhir_resource__ = "Procedure"

    def __init__(self, outcome_code: ProcedureOutcomeCode):
        """Initialize procedure outcome.

        Args:
            outcome_code: Primary outcome code
        """
        self.outcome_code = outcome_code
        self.outcome_date = datetime.now()
        self.complications: List[Dict] = []
        self.follow_up_requirements: List[Dict] = []
        self.notes: Optional[str] = None
        self.assessed_by: Optional[str] = None
        self.next_assessment_date: Optional[date] = None

    def add_complication(
        self,
        complication_type: str,
        severity: ComplicationSeverity,
        onset_date: Optional[datetime] = None,
        resolved: bool = False,
        treatment: Optional[str] = None,
    ) -> "ProcedureOutcome":
        """Add a complication to the outcome.

        Args:
            complication_type: Type of complication
            severity: Severity level
            onset_date: When complication occurred
            resolved: Whether complication is resolved
            treatment: Treatment provided
        """
        comp_info = CommonComplications.get_complication_info(complication_type)

        complication = {
            "type": complication_type,
            "code": (
                comp_info["code"] if comp_info else f"COMP-{complication_type.upper()}"
            ),
            "display": comp_info["display"] if comp_info else complication_type,
            "severity": severity.value,
            "onset_date": (onset_date or datetime.now()).isoformat(),
            "resolved": resolved,
            "treatment": treatment,
        }

        self.complications.append(complication)
        return self

    def add_follow_up(
        self,
        requirement_type: FollowUpRequirement,
        timeframe_days: int,
        location: Optional[str] = None,
        provider_type: Optional[str] = None,
        instructions: Optional[str] = None,
    ) -> "ProcedureOutcome":
        """Add follow-up requirement.

        Args:
            requirement_type: Type of follow-up needed
            timeframe_days: Days until follow-up needed
            location: Where follow-up should occur
            provider_type: Type of provider needed
            instructions: Specific instructions
        """
        follow_up_date = date.today() + timedelta(days=timeframe_days)

        follow_up = {
            "type": requirement_type.value,
            "date": follow_up_date.isoformat(),
            "timeframe_days": timeframe_days,
            "location": location,
            "provider_type": provider_type,
            "instructions": instructions,
            "scheduled": False,
        }

        self.follow_up_requirements.append(follow_up)
        return self

    def set_notes(self, notes: str) -> "ProcedureOutcome":
        """Set outcome notes."""
        self.notes = notes
        return self

    def set_assessed_by(self, assessor: str) -> "ProcedureOutcome":
        """Set who assessed the outcome."""
        self.assessed_by = assessor
        return self

    def set_next_assessment(self, assessment_date: date) -> "ProcedureOutcome":
        """Set next assessment date."""
        self.next_assessment_date = assessment_date
        return self

    def is_successful(self) -> bool:
        """Check if outcome was successful."""
        return self.outcome_code in [
            ProcedureOutcomeCode.SUCCESSFUL,
            ProcedureOutcomeCode.RESOLVED,
            ProcedureOutcomeCode.IMPROVED,
        ]

    def has_complications(self) -> bool:
        """Check if there were complications."""
        return len(self.complications) > 0

    def has_severe_complications(self) -> bool:
        """Check if there were severe complications."""
        return any(
            comp["severity"] in ["severe", "fatal"] for comp in self.complications
        )

    def get_unresolved_complications(self) -> List[Dict]:
        """Get list of unresolved complications."""
        return [comp for comp in self.complications if not comp.get("resolved", False)]

    def get_urgent_follow_ups(self) -> List[Dict]:
        """Get urgent follow-up requirements."""
        return [
            fu
            for fu in self.follow_up_requirements
            if fu["type"] == FollowUpRequirement.URGENT.value
            or fu["timeframe_days"] <= 2
        ]

    def to_fhir_outcome(self) -> Dict[str, Any]:
        """Convert to FHIR outcome structure."""
        outcome: Dict[str, Any] = {
            "coding": [
                {
                    "system": "http://snomed.info/sct",
                    "code": self.outcome_code.value,
                    "display": self.outcome_code.name.replace("_", " ").title(),
                }
            ]
        }

        if self.notes:
            outcome["text"] = self.notes

        return outcome

    def to_fhir_complications(self) -> List[Dict[str, Any]]:
        """Convert complications to FHIR format."""
        fhir_complications = []

        for comp in self.complications:
            fhir_comp = {
                "coding": [
                    {
                        "system": (
                            "http://snomed.info/sct"
                            if not comp["code"].startswith("FIELD")
                            else "http://havenhealthpassport.org/fhir/CodeSystem/field-complications"
                        ),
                        "code": comp["code"],
                        "display": comp["display"],
                    }
                ],
                "text": f"{comp['display']} - Severity: {comp['severity']}",
            }

            fhir_complications.append(fhir_comp)

        return fhir_complications

    def to_fhir_follow_up(self) -> List[Dict[str, Any]]:
        """Convert follow-up requirements to FHIR format."""
        fhir_follow_ups = []

        for fu in self.follow_up_requirements:
            fhir_fu: Dict[str, Any] = {
                "coding": [
                    {
                        "system": "http://havenhealthpassport.org/fhir/CodeSystem/follow-up-requirements",
                        "code": fu["type"],
                        "display": fu["type"].replace("-", " ").title(),
                    }
                ],
                "text": f"{fu['type']} required by {fu['date']}",
            }

            if fu.get("instructions"):
                fhir_fu["text"] += f" - {fu['instructions']}"

            fhir_follow_ups.append(fhir_fu)

        return fhir_follow_ups

    def validate_fhir(self, procedure_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate FHIR Procedure resource with outcome data.

        Args:
            procedure_data: FHIR Procedure resource data

        Returns:
            Validation result with 'valid', 'errors', and 'warnings' keys
        """
        errors = []
        warnings = []

        # Check for outcome in procedure
        if "outcome" not in procedure_data:
            warnings.append("Procedure should have outcome")
        else:
            outcome = procedure_data["outcome"]
            if not isinstance(outcome, dict):
                errors.append("Outcome must be an object")
            elif "coding" not in outcome:
                warnings.append("Outcome should have coding")

        # Check for complications if present
        if "complication" in procedure_data:
            complications = procedure_data["complication"]
            if not isinstance(complications, list):
                errors.append("Complications must be an array")
            else:
                for i, comp in enumerate(complications):
                    if not isinstance(comp, dict):
                        errors.append(f"Complication {i} must be an object")
                    elif "coding" not in comp:
                        warnings.append(f"Complication {i} should have coding")

        # Check for follow-up if present
        if "followUp" in procedure_data:
            follow_ups = procedure_data["followUp"]
            if not isinstance(follow_ups, list):
                errors.append("Follow-ups must be an array")

        return {"valid": len(errors) == 0, "errors": errors, "warnings": warnings}


class OutcomePredictor:
    """Predicts procedure outcomes based on context."""

    @staticmethod
    def predict_complications(
        procedure_type: str,
        patient_factors: Dict[str, Any],
        environmental_factors: Dict[str, Any],
    ) -> List[Dict]:
        """Predict potential complications based on factors.

        Args:
            procedure_type: Type of procedure
            patient_factors: Patient risk factors
            environmental_factors: Environmental risk factors

        Returns:
            List of predicted complications with risk levels
        """
        predictions = []

        # Get base complications for procedure
        base_complications = CommonComplications.get_complications_for_procedure(
            procedure_type
        )

        for comp in base_complications:
            risk_score = 0.1  # Base 10% risk

            # Adjust for patient factors
            if patient_factors.get("age", 0) < 5 or patient_factors.get("age", 0) > 65:
                risk_score += 0.1

            if patient_factors.get("malnourished"):
                risk_score += 0.2

            if patient_factors.get("immunocompromised"):
                risk_score += 0.15

            if patient_factors.get("comorbidities", 0) > 0:
                risk_score += 0.05 * patient_factors["comorbidities"]

            # Adjust for environmental factors
            if environmental_factors.get("field_conditions"):
                risk_score += 0.25

            if environmental_factors.get("limited_equipment"):
                risk_score += 0.15

            if environmental_factors.get("inexperienced_provider"):
                risk_score += 0.2

            # Cap at 90% risk
            risk_score = min(risk_score, 0.9)

            predictions.append(
                {
                    "complication": comp["name"],
                    "risk_score": risk_score,
                    "risk_level": OutcomePredictor._categorize_risk(risk_score),
                    "preventive_measures": OutcomePredictor._get_preventive_measures(
                        comp["name"], risk_score
                    ),
                }
            )

        return sorted(predictions, key=lambda x: x["risk_score"], reverse=True)

    @staticmethod
    def _categorize_risk(risk_score: float) -> str:
        """Categorize risk score into levels."""
        if risk_score < 0.2:
            return "low"
        elif risk_score < 0.5:
            return "moderate"
        elif risk_score < 0.7:
            return "high"
        else:
            return "very_high"

    @staticmethod
    def _get_preventive_measures(
        complication_type: str, risk_score: float
    ) -> List[str]:
        """Get preventive measures for complications."""
        measures = []

        if complication_type == "infection":
            measures.extend(
                [
                    "Ensure sterile technique",
                    "Prophylactic antibiotics if available",
                    "Monitor for signs of infection",
                ]
            )
            if risk_score > 0.5:
                measures.append(
                    "Consider referral to facility with better sterile conditions"
                )

        elif complication_type == "bleeding":
            measures.extend(
                [
                    "Ensure adequate hemostasis",
                    "Have blood products available if possible",
                    "Monitor vital signs closely",
                ]
            )

        elif complication_type == "postpartum_hemorrhage":
            measures.extend(
                [
                    "Active management of third stage labor",
                    "Oxytocin available",
                    "Skilled birth attendant present",
                ]
            )

        return measures


class OutcomeTracker:
    """Tracks and analyzes procedure outcomes over time."""

    def __init__(self) -> None:
        """Initialize outcome tracker."""
        self.outcomes: Dict[str, List[ProcedureOutcome]] = {}

    def record_outcome(self, procedure_id: str, outcome: ProcedureOutcome) -> None:
        """Record a procedure outcome."""
        if procedure_id not in self.outcomes:
            self.outcomes[procedure_id] = []

        self.outcomes[procedure_id].append(outcome)

    def get_success_rate(self, procedure_type: Optional[str] = None) -> float:
        """Calculate success rate for procedures.

        Args:
            procedure_type: Optional filter by procedure type

        Returns:
            Success rate as percentage
        """
        # Implement procedure type filtering
        total = 0
        successful = 0

        # Define procedure hierarchy for filtering
        PROCEDURE_HIERARCHY = {
            "surgical": {
                "cardiovascular": [
                    "CABG",
                    "valve_replacement",
                    "angioplasty",
                    "stent_placement",
                ],
                "orthopedic": [
                    "joint_replacement",
                    "fracture_repair",
                    "arthroscopy",
                    "spinal_fusion",
                ],
                "general": [
                    "appendectomy",
                    "hernia_repair",
                    "cholecystectomy",
                    "bowel_resection",
                ],
            },
            "diagnostic": {
                "imaging": ["MRI", "CT", "ultrasound", "x-ray", "PET_scan"],
                "laboratory": ["blood_test", "biopsy", "culture", "genetic_testing"],
                "functional": ["ECG", "spirometry", "stress_test", "sleep_study"],
            },
            "therapeutic": {
                "radiation": ["external_beam", "brachytherapy", "proton_therapy"],
                "infusion": [
                    "chemotherapy",
                    "immunotherapy",
                    "blood_transfusion",
                    "IV_antibiotics",
                ],
                "physical": [
                    "physical_therapy",
                    "occupational_therapy",
                    "speech_therapy",
                ],
            },
        }

        # Get all procedures matching the type
        matching_procedures = set()
        if procedure_type:
            for category, subcategories in PROCEDURE_HIERARCHY.items():
                if procedure_type.lower() == category:
                    # Add all procedures in this category
                    for procedures in subcategories.values():
                        matching_procedures.update(procedures)
                else:
                    # Check subcategories
                    for subcat, procedures in subcategories.items():
                        if procedure_type.lower() == subcat:
                            matching_procedures.update(procedures)
                        # Also check individual procedures
                        elif procedure_type.lower() in [p.lower() for p in procedures]:
                            matching_procedures.add(procedure_type)

        for _procedure_id, outcomes in self.outcomes.items():
            for outcome in outcomes:
                # Filter by procedure type if specified
                if procedure_type:
                    # Check if this outcome's procedure matches the filter
                    # In production, this would check outcome.procedure_type or lookup procedure details
                    procedure_name = getattr(outcome, "procedure_name", "").lower()
                    procedure_code = getattr(outcome, "procedure_code", "").lower()

                    # Check if procedure matches any in our filter set
                    matches_filter = False
                    for match_proc in matching_procedures:
                        if (
                            match_proc.lower() in procedure_name
                            or match_proc.lower() in procedure_code
                            or procedure_name in match_proc.lower()
                        ):
                            matches_filter = True
                            break

                    if not matches_filter:
                        continue

                total += 1
                if outcome.is_successful():
                    successful += 1

        # Add statistical analysis for filtered results
        if total > 0:
            success_rate = successful / total * 100

            # Log statistics for monitoring
            logger.info(
                "Procedure success rate for type '%s': %.1f%% (%d/%d procedures)",
                procedure_type,
                success_rate,
                successful,
                total,
            )

            return success_rate

        return 0

    def get_complication_rate(self, complication_type: Optional[str] = None) -> float:
        """Calculate complication rate.

        Args:
            complication_type: Optional filter by complication type

        Returns:
            Complication rate as percentage
        """
        total = 0
        with_complications = 0

        for outcomes in self.outcomes.values():
            for outcome in outcomes:
                total += 1

                if complication_type:
                    # Check for specific complication
                    has_comp = any(
                        comp["type"] == complication_type
                        for comp in outcome.complications
                    )
                    if has_comp:
                        with_complications += 1
                else:
                    # Any complication
                    if outcome.has_complications():
                        with_complications += 1

        return (with_complications / total * 100) if total > 0 else 0

    def get_follow_up_compliance(self) -> Dict[str, float]:
        """Calculate follow-up compliance rates.

        Returns:
            Dictionary of compliance rates by follow-up type
        """
        compliance: Dict[str, float] = {}

        # In production, would track actual follow-up completion
        # This is a placeholder showing the structure

        return compliance


def create_standard_outcome(
    procedure_type: str,
    was_successful: bool = True,
    complications: Optional[List[str]] = None,
) -> ProcedureOutcome:
    """Create a standard procedure outcome.

    Args:
        procedure_type: Type of procedure performed
        was_successful: Whether procedure was successful
        complications: List of complications that occurred

    Returns:
        ProcedureOutcome instance
    """
    # Determine outcome code
    if was_successful and not complications:
        outcome_code = ProcedureOutcomeCode.SUCCESSFUL
    elif was_successful and complications:
        outcome_code = ProcedureOutcomeCode.COMPLETED_WITH_COMPLICATIONS
    else:
        outcome_code = ProcedureOutcomeCode.UNSUCCESSFUL

    outcome = ProcedureOutcome(outcome_code)

    # Add complications if any
    if complications:
        for comp in complications:
            outcome.add_complication(
                comp,
                ComplicationSeverity.MODERATE,  # Default severity
                treatment="Managed per protocol",
            )

    # Add standard follow-up based on procedure
    if procedure_type in ["wound_suturing", "surgical"]:
        outcome.add_follow_up(
            FollowUpRequirement.WOUND_CHECK,
            timeframe_days=3,
            instructions="Check for signs of infection",
        )
        outcome.add_follow_up(
            FollowUpRequirement.SUTURE_REMOVAL,
            timeframe_days=7,
            instructions="Remove sutures if healing well",
        )
    elif procedure_type == "immunization":
        outcome.add_follow_up(
            FollowUpRequirement.PRN,
            timeframe_days=1,
            instructions="Return if severe reaction occurs",
        )

    return outcome


class ProcedureTypeManager:
    """Manages procedure categorization and filtering."""

    # Standard procedure taxonomy with CPT/ICD-10-PCS mappings
    PROCEDURE_TAXONOMY = {
        "surgical": {
            "cardiovascular": {
                "CABG": {"cpt": ["33510-33536"], "icd10": ["021108*", "021109*"]},
                "valve_replacement": {
                    "cpt": ["33361-33365"],
                    "icd10": ["02RF*", "02RG*"],
                },
                "angioplasty": {"cpt": ["92920-92944"], "icd10": ["027*"]},
                "stent_placement": {
                    "cpt": ["37236-37239"],
                    "icd10": ["027*3DZ", "027*4DZ"],
                },
                "pacemaker": {"cpt": ["33206-33208"], "icd10": ["0JH6*", "0JH8*"]},
            },
            "orthopedic": {
                "joint_replacement": {
                    "cpt": ["27130", "27447"],
                    "icd10": ["0SR*", "0SS*"],
                },
                "fracture_repair": {"cpt": ["25605-25609"], "icd10": ["0PS*", "0QS*"]},
                "arthroscopy": {"cpt": ["29866-29889"], "icd10": ["0SJ*"]},
                "spinal_fusion": {"cpt": ["22612-22614"], "icd10": ["0SG*"]},
            },
            "general": {
                "appendectomy": {"cpt": ["44970"], "icd10": ["0DTJ*"]},
                "hernia_repair": {"cpt": ["49505-49507"], "icd10": ["0YQ*", "0WQ*"]},
                "cholecystectomy": {"cpt": ["47562-47564"], "icd10": ["0FT4*"]},
                "bowel_resection": {"cpt": ["44140-44160"], "icd10": ["0DT*"]},
            },
            "emergency": {
                "trauma_surgery": {"cpt": ["20100-20103"], "icd10": ["0W9*"]},
                "emergency_laparotomy": {"cpt": ["49000"], "icd10": ["0WJG*"]},
            },
        },
        "diagnostic": {
            "imaging": {
                "MRI": {"cpt": ["70551-70559"], "modality": "MR"},
                "CT": {"cpt": ["70450-70498"], "modality": "CT"},
                "ultrasound": {"cpt": ["76700-76857"], "modality": "US"},
                "x-ray": {"cpt": ["70010-73660"], "modality": "XR"},
                "PET_scan": {"cpt": ["78608-78816"], "modality": "PT"},
            },
            "laboratory": {
                "blood_test": {"cpt": ["80047-80076"], "loinc_category": "CHEM"},
                "biopsy": {"cpt": ["88104-88309"], "loinc_category": "PATH"},
                "culture": {"cpt": ["87040-87158"], "loinc_category": "MICRO"},
                "genetic_testing": {"cpt": ["81200-81479"], "loinc_category": "GEN"},
            },
            "functional": {
                "ECG": {"cpt": ["93000-93010"], "loinc": ["11524-6"]},
                "spirometry": {"cpt": ["94010"], "loinc": ["19758-0"]},
                "stress_test": {"cpt": ["93015-93018"], "loinc": ["18752-6"]},
                "sleep_study": {"cpt": ["95810-95811"], "loinc": ["93832-4"]},
            },
        },
        "therapeutic": {
            "radiation": {
                "external_beam": {"cpt": ["77385-77387"], "modality": "EBRT"},
                "brachytherapy": {"cpt": ["77750-77799"], "modality": "BT"},
                "proton_therapy": {"cpt": ["77520-77525"], "modality": "PT"},
            },
            "infusion": {
                "chemotherapy": {
                    "cpt": ["96413-96417"],
                    "drug_category": "antineoplastic",
                },
                "immunotherapy": {"cpt": ["90460-90474"], "drug_category": "immune"},
                "blood_transfusion": {"cpt": ["36430"], "product": "blood"},
                "IV_antibiotics": {
                    "cpt": ["96365-96368"],
                    "drug_category": "antibiotic",
                },
            },
            "physical": {
                "physical_therapy": {"cpt": ["97110-97546"], "provider": "PT"},
                "occupational_therapy": {"cpt": ["97129-97546"], "provider": "OT"},
                "speech_therapy": {"cpt": ["92507-92609"], "provider": "SLP"},
            },
        },
    }

    def __init__(self) -> None:
        """Initialize procedure type manager."""
        self._build_code_index()
        self._load_clinical_guidelines()

    def _build_code_index(self) -> None:
        """Build reverse index for quick code lookups."""
        self.cpt_to_procedure = {}
        self.icd10_to_procedure = {}

        for category, subcategories in self.PROCEDURE_TAXONOMY.items():
            if isinstance(subcategories, dict):
                for subcat, procedures in subcategories.items():
                    for proc_name, codes in procedures.items():
                        # Index CPT codes
                        if "cpt" in codes:
                            for cpt_range in codes["cpt"]:
                                if "-" in cpt_range:
                                    start, end = cpt_range.split("-")
                                    for code in range(int(start), int(end) + 1):
                                        self.cpt_to_procedure[str(code)] = {
                                            "name": proc_name,
                                            "category": category,
                                            "subcategory": subcat,
                                        }
                                else:
                                    self.cpt_to_procedure[cpt_range] = {
                                        "name": proc_name,
                                        "category": category,
                                        "subcategory": subcat,
                                    }

                        # Index ICD-10 codes
                        if "icd10" in codes:
                            for icd_pattern in codes["icd10"]:
                                self.icd10_to_procedure[icd_pattern] = {
                                    "name": proc_name,
                                    "category": category,
                                    "subcategory": subcat,
                                }

    def _load_clinical_guidelines(self) -> None:
        """Load clinical guidelines for procedures."""
        self.clinical_guidelines = {
            "CABG": {
                "indications": ["multi-vessel CAD", "left main disease"],
                "contraindications": [
                    "poor surgical candidate",
                    "limited life expectancy",
                ],
                "expected_los": 5,  # Length of stay in days
                "success_rate": 0.95,
                "major_complications": ["bleeding", "infection", "stroke"],
            },
            "joint_replacement": {
                "indications": [
                    "severe arthritis",
                    "joint deformity",
                    "failed conservative treatment",
                ],
                "contraindications": ["active infection", "severe vascular disease"],
                "expected_los": 3,
                "success_rate": 0.90,
                "major_complications": ["infection", "DVT", "dislocation"],
            },
            # Add more guidelines as needed
        }

    def categorize_procedure(
        self, procedure_code: str, code_type: str = "auto"
    ) -> Dict[str, str]:
        """Categorize a procedure based on its code.

        Args:
            procedure_code: The procedure code
            code_type: Type of code ("cpt", "icd10", or "auto" to detect)

        Returns:
            Dictionary with category, subcategory, and procedure name
        """
        # Auto-detect code type
        if code_type == "auto":
            if procedure_code.isdigit() and len(procedure_code) == 5:
                code_type = "cpt"
            else:
                code_type = "icd10"

        if code_type == "cpt":
            return self.cpt_to_procedure.get(
                procedure_code,
                {"name": "unknown", "category": "other", "subcategory": "unclassified"},
            )
        else:
            # For ICD-10, need pattern matching
            for pattern, info in self.icd10_to_procedure.items():
                if self._matches_icd10_pattern(procedure_code, pattern):
                    return info

        return {"name": "unknown", "category": "other", "subcategory": "unclassified"}

    def _matches_icd10_pattern(self, code: str, pattern: str) -> bool:
        """Check if ICD-10 code matches pattern with wildcards."""
        regex_pattern = pattern.replace("*", ".*")
        return bool(re.match(f"^{regex_pattern}$", code))

    def filter_outcomes_by_type(
        self, outcomes: List[Any], procedure_type: str, filter_level: str = "any"
    ) -> List[Any]:
        """Filter outcomes by procedure type.

        Args:
            outcomes: List of procedure outcomes
            procedure_type: Type to filter by (category, subcategory, or specific procedure)
            filter_level: "category", "subcategory", "procedure", or "any"

        Returns:
            Filtered list of outcomes
        """
        filtered = []

        for outcome in outcomes:
            # Get procedure classification
            proc_code = getattr(outcome, "procedure_code", None)
            if not proc_code:
                continue

            categorization = self.categorize_procedure(proc_code)

            # Check if matches filter
            matches = False
            if filter_level == "any":
                matches = (
                    procedure_type.lower() == categorization.get("category", "").lower()
                    or procedure_type.lower()
                    == categorization.get("subcategory", "").lower()
                    or procedure_type.lower() == categorization.get("name", "").lower()
                )
            elif filter_level == "category":
                matches = (
                    procedure_type.lower() == categorization.get("category", "").lower()
                )
            elif filter_level == "subcategory":
                matches = (
                    procedure_type.lower()
                    == categorization.get("subcategory", "").lower()
                )
            elif filter_level == "procedure":
                matches = (
                    procedure_type.lower() == categorization.get("name", "").lower()
                )

            if matches:
                filtered.append(outcome)

        return filtered

    def get_procedure_statistics(
        self, outcomes: List[Any], procedure_type: str
    ) -> Dict[str, Any]:
        """Generate statistics for a specific procedure type.

        Args:
            outcomes: List of procedure outcomes
            procedure_type: Type to analyze

        Returns:
            Dictionary with statistics
        """
        filtered_outcomes = self.filter_outcomes_by_type(outcomes, procedure_type)

        if not filtered_outcomes:
            return {
                "count": 0,
                "success_rate": 0.0,
                "complication_rate": 0.0,
                "average_los": 0,
                "common_complications": [],
            }

        # Calculate statistics
        total = len(filtered_outcomes)
        successful = sum(
            1 for o in filtered_outcomes if getattr(o, "successful", False)
        )
        complications = []
        total_los = 0

        for outcome in filtered_outcomes:
            if hasattr(outcome, "complications") and outcome.complications:
                complications.extend(outcome.complications)
            if hasattr(outcome, "length_of_stay"):
                total_los += outcome.length_of_stay

        # Count complication types
        complication_counts: Dict[str, int] = {}
        for comp in complications:
            comp_type = comp.get("type", "unknown")
            complication_counts[comp_type] = complication_counts.get(comp_type, 0) + 1

        # Sort complications by frequency
        common_complications = sorted(
            complication_counts.items(), key=lambda x: x[1], reverse=True
        )[
            :5
        ]  # Top 5

        return {
            "count": total,
            "success_rate": (successful / total * 100) if total > 0 else 0,
            "complication_rate": (len(complications) / total * 100) if total > 0 else 0,
            "average_los": (total_los / total) if total > 0 else 0,
            "common_complications": common_complications,
            "clinical_guidelines": self.clinical_guidelines.get(procedure_type, {}),
        }

    def predict_outcome(
        self, procedure_type: str, patient_factors: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Predict procedure outcome based on patient factors.

        Args:
            procedure_type: Type of procedure
            patient_factors: Patient risk factors

        Returns:
            Prediction with confidence score
        """
        # Get baseline statistics
        guidelines = self.clinical_guidelines.get(procedure_type, {})
        success_rate_value = guidelines.get("success_rate", 0.85)
        # Ensure the value is a float
        if isinstance(success_rate_value, (int, float, str)):
            try:
                base_success_rate = float(success_rate_value)
            except (ValueError, TypeError):
                base_success_rate = 0.85
        else:
            base_success_rate = 0.85

        # Adjust based on patient factors
        risk_adjustment = 0.0

        # Age factor
        age = patient_factors.get("age", 50)
        if age > 80:
            risk_adjustment -= 0.15
        elif age > 70:
            risk_adjustment -= 0.10
        elif age < 18:
            risk_adjustment -= 0.05

        # Comorbidities
        comorbidities = patient_factors.get("comorbidities", [])
        if "diabetes" in comorbidities:
            risk_adjustment -= 0.05
        if "heart_disease" in comorbidities:
            risk_adjustment -= 0.10
        if "immunosuppression" in comorbidities:
            risk_adjustment -= 0.15

        # Calculate final prediction
        predicted_success = max(0.1, min(0.99, base_success_rate + risk_adjustment))

        return {
            "predicted_success_rate": predicted_success * 100,
            "confidence": 0.75,  # Would be calculated based on data quality
            "risk_factors": {
                "age_risk": "high" if age > 70 else "low",
                "comorbidity_risk": "high" if len(comorbidities) > 2 else "low",
            },
            "recommendations": self._generate_recommendations(
                procedure_type, predicted_success, patient_factors
            ),
        }

    def _generate_recommendations(
        self, _procedure_type: str, success_rate: float, patient_factors: Dict[str, Any]
    ) -> List[str]:
        """Generate procedure-specific recommendations."""
        recommendations = []

        if success_rate < 0.7:
            recommendations.append(
                "Consider alternative treatments due to elevated risk"
            )

        if patient_factors.get("age", 0) > 70:
            recommendations.append("Ensure comprehensive pre-operative evaluation")
            recommendations.append("Consider extended monitoring post-procedure")

        if "diabetes" in patient_factors.get("comorbidities", []):
            recommendations.append("Optimize glycemic control pre-procedure")
            recommendations.append("Monitor for infection post-procedure")

        return recommendations
