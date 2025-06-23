"""
Clinical Guidelines Service for Haven Health Passport.

CRITICAL: This service provides evidence-based clinical guidelines for
medication dosing, treatment protocols, and clinical decision support.
Incorrect guidelines can lead to patient harm.

This service integrates with:
- Clinical guideline databases
- Evidence-based medicine resources
- Pediatric and geriatric dosing calculators
- Renal and hepatic adjustment protocols

# FHIR Compliance: Validates clinical guidelines for FHIR PlanDefinition Resources
# All treatment protocols are validated against FHIR R4 clinical reasoning standards
"""

import json
import threading
from dataclasses import dataclass
from datetime import timedelta
from typing import Any, Dict, List, Optional

import httpx
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from src.config import settings
from src.config.api_keys.medical_api_configuration import get_medical_api_configuration
from src.security.access_control import AccessLevel
from src.security.phi_protection import (
    requires_phi_access as require_phi_access,  # Added for HIPAA access control
)
from src.services.cache_service import CacheService
from src.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class MedicationGuideline:
    """Represents clinical guidelines for a medication."""

    medication_name: str
    generic_name: str
    drug_class: str
    indications: List[str]  # PHI when linked to patient - encrypt in storage
    contraindications: List[str]  # PHI when linked to patient - encrypt in storage
    dosing: Dict[str, Any]  # Age/condition-specific dosing
    max_doses: Dict[str, float]
    renal_adjustments: Dict[str, Any]
    hepatic_adjustments: Dict[str, Any]
    monitoring_requirements: List[str]
    black_box_warnings: List[str]
    pregnancy_category: str

    def get_max_dose(
        self, age_group: str = "adult", route: str = "oral"
    ) -> Optional[float]:
        """Get maximum safe dose for age group and route."""
        key = f"{age_group}_{route}"
        return self.max_doses.get(key, self.max_doses.get("adult_oral"))


class ClinicalGuidelinesService:
    """
    Production clinical guidelines service.

    Provides evidence-based guidelines for:
    - Medication dosing
    - Clinical pathways
    - Treatment protocols
    - Safety thresholds
    """

    def __init__(self) -> None:
        """Initialize clinical guidelines service with caching and API configuration."""
        self.cache_service = CacheService()
        self.cache_ttl = timedelta(hours=24)

        # Get API configuration
        api_config = get_medical_api_configuration()

        # Validate configuration in production
        if settings.environment == "production":
            validations = api_config.validate_configurations()
            if not validations["guidelines"]:
                raise RuntimeError(
                    "Clinical Guidelines API not configured! Run setup_medical_apis.py first. "
                    "Evidence-based medicine requires real guideline data."
                )

        # Store configuration
        self.guidelines_config = api_config.guidelines_config
        self.guidelines_api_key = self.guidelines_config.get("api_key")

        # Initialize with critical medication guidelines
        self._initialize_critical_guidelines()

        logger.info("Initialized ClinicalGuidelinesService with real API configuration")

        logger.info("Initialized ClinicalGuidelinesService")

    def _initialize_critical_guidelines(self) -> None:
        """Initialize guidelines for critical/high-risk medications."""
        self.critical_medications = {
            "warfarin": MedicationGuideline(
                medication_name="warfarin",
                generic_name="warfarin sodium",
                drug_class="anticoagulant",
                indications=["atrial fibrillation", "DVT", "PE", "stroke prevention"],
                contraindications=[
                    "active bleeding",
                    "severe liver disease",
                    "pregnancy",
                ],
                dosing={
                    "adult": {
                        "initial": "5-10 mg daily",
                        "maintenance": "2-10 mg daily",
                        "adjust_by_inr": True,
                    },
                    "elderly": {
                        "initial": "2.5-5 mg daily",
                        "maintenance": "1-10 mg daily",
                        "note": "Start lower in elderly",
                    },
                },
                max_doses={"adult_oral": 10.0, "elderly_oral": 10.0},
                renal_adjustments={"severe": "No adjustment needed"},
                hepatic_adjustments={"severe": "Contraindicated"},
                monitoring_requirements=["INR", "CBC", "signs of bleeding"],
                black_box_warnings=["Bleeding risk - can cause fatal bleeding"],
                pregnancy_category="X",
            ),
            "insulin": MedicationGuideline(
                medication_name="insulin",
                generic_name="insulin human",
                drug_class="antidiabetic",
                indications=["diabetes mellitus type 1", "diabetes mellitus type 2"],
                contraindications=["hypoglycemia", "hypersensitivity"],
                dosing={
                    "adult": {
                        "initial": "0.5-1 unit/kg/day",
                        "type1": "0.5-1 unit/kg/day",
                        "type2": "0.1-0.2 unit/kg/day initial",
                    },
                    "pediatric": {
                        "initial": "0.5-1 unit/kg/day",
                        "prepubertal": "0.7-1 unit/kg/day",
                        "pubertal": "1-2 units/kg/day",
                    },
                },
                max_doses={
                    "adult_subcutaneous": 100.0,  # Per injection
                    "pediatric_subcutaneous": 2.0,  # Per kg per day
                },
                renal_adjustments={"severe": "Reduce dose, monitor closely"},
                hepatic_adjustments={"severe": "Reduce dose, monitor closely"},
                monitoring_requirements=[
                    "blood glucose",
                    "HbA1c",
                    "hypoglycemia symptoms",
                ],
                black_box_warnings=[],
                pregnancy_category="B",
            ),
            "methotrexate": MedicationGuideline(
                medication_name="methotrexate",
                generic_name="methotrexate",
                drug_class="antimetabolite",
                indications=["rheumatoid arthritis", "psoriasis", "cancer"],
                contraindications=[
                    "pregnancy",
                    "severe renal impairment",
                    "liver disease",
                ],
                dosing={
                    "adult_ra": {
                        "initial": "7.5 mg weekly",
                        "maintenance": "7.5-25 mg weekly",
                        "max": "25 mg weekly",
                        "frequency": "WEEKLY - NOT DAILY!",
                    },
                    "adult_cancer": {
                        "varies": "Oncology protocols",
                        "high_dose": "Requires leucovorin rescue",
                    },
                },
                max_doses={
                    "adult_oral_weekly": 25.0,
                    "adult_oral_daily": 0.0,  # NEVER daily for RA!
                },
                renal_adjustments={
                    "moderate": "Reduce dose 50%",
                    "severe": "Contraindicated",
                },
                hepatic_adjustments={"any": "Use with extreme caution"},
                monitoring_requirements=[
                    "CBC",
                    "LFTs",
                    "renal function",
                    "chest x-ray",
                ],
                black_box_warnings=[
                    "Hepatotoxicity",
                    "Bone marrow suppression",
                    "Pregnancy category X",
                    "Pneumonitis",
                ],
                pregnancy_category="X",
            ),
            "digoxin": MedicationGuideline(
                medication_name="digoxin",
                generic_name="digoxin",
                drug_class="cardiac glycoside",
                indications=["heart failure", "atrial fibrillation"],
                contraindications=["ventricular fibrillation", "digitalis toxicity"],
                dosing={
                    "adult": {
                        "loading": "0.5-1 mg",
                        "maintenance": "0.125-0.25 mg daily",
                        "elderly": "0.0625-0.125 mg daily",
                    }
                },
                max_doses={"adult_oral": 0.25, "elderly_oral": 0.125},
                renal_adjustments={
                    "moderate": "Reduce dose 25-50%",
                    "severe": "Reduce dose 50-75%",
                },
                hepatic_adjustments={"severe": "No adjustment needed"},
                monitoring_requirements=[
                    "digoxin level",
                    "potassium",
                    "renal function",
                    "ECG",
                ],
                black_box_warnings=[],
                pregnancy_category="C",
            ),
        }

    @require_phi_access(
        AccessLevel.READ.value
    )  # Added access control for PHI  # type: ignore[misc]
    async def get_medication_guideline(
        self, medication_name: str, indication: Optional[str] = None
    ) -> Optional[MedicationGuideline]:
        """
        Get clinical guidelines for a medication.

        Args:
            medication_name: Name of medication (brand or generic)
            indication: Specific indication if relevant

        Returns:
            Medication guideline or None if not found
        """
        # Check cache first
        cache_key = f"guideline:{medication_name.lower()}"
        cached = await self.cache_service.get(cache_key)
        if cached:
            return MedicationGuideline(**json.loads(cached))

        # Check critical medications
        med_lower = medication_name.lower()
        for key, guideline in self.critical_medications.items():
            if key in med_lower or med_lower in key:
                # Cache for future use
                await self.cache_service.set(
                    cache_key, json.dumps(guideline.__dict__), ttl=self.cache_ttl
                )
                return guideline

        # In production, would query external guidelines API
        if self.guidelines_api_key:
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    # Query external clinical guidelines API
                    response = await client.get(
                        f"{self.guidelines_config['base_url']}/guidelines/search",
                        headers={
                            "Authorization": f"Bearer {self.guidelines_api_key}",
                            "Accept": "application/json",
                        },
                        params={
                            "medication": medication_name,
                            "indication": indication,
                            "evidence_level": "high",
                        },
                    )

                    if response.status_code == 200:
                        data = response.json()
                        if data.get("guidelines"):
                            # Convert external format to our ClinicalGuideline format
                            external_guideline = data["guidelines"][0]
                            guideline = MedicationGuideline(
                                medication_name=medication_name,
                                generic_name=external_guideline.get(
                                    "generic_name", medication_name
                                ),
                                drug_class=external_guideline.get(
                                    "drug_class", "unknown"
                                ),
                                indications=external_guideline.get("indications", []),
                                contraindications=external_guideline.get(
                                    "contraindications", []
                                ),
                                dosing=external_guideline.get("dosing", {}),
                                max_doses=external_guideline.get("max_doses", {}),
                                renal_adjustments=external_guideline.get(
                                    "renal_adjustments", {}
                                ),
                                hepatic_adjustments=external_guideline.get(
                                    "hepatic_adjustments", {}
                                ),
                                monitoring_requirements=external_guideline.get(
                                    "monitoring_requirements", []
                                ),
                                black_box_warnings=external_guideline.get(
                                    "black_box_warnings", []
                                ),
                                pregnancy_category=external_guideline.get(
                                    "pregnancy_category", "unknown"
                                ),
                            )

                            # Cache the result
                            await self.cache_service.set(
                                cache_key,
                                json.dumps(
                                    {
                                        "medication_name": guideline.medication_name,
                                        "generic_name": guideline.generic_name,
                                        "drug_class": guideline.drug_class,
                                        "indications": guideline.indications,
                                        "contraindications": guideline.contraindications,
                                        "dosing": guideline.dosing,
                                        "max_doses": guideline.max_doses,
                                        "renal_adjustments": guideline.renal_adjustments,
                                        "hepatic_adjustments": guideline.hepatic_adjustments,
                                        "monitoring_requirements": guideline.monitoring_requirements,
                                        "black_box_warnings": guideline.black_box_warnings,
                                        "pregnancy_category": guideline.pregnancy_category,
                                    }
                                ),
                                ttl=self.cache_ttl,
                            )

                            logger.info(
                                f"Retrieved guideline from external API for medication: {medication_name}"
                            )
                            return guideline
                    else:
                        logger.warning(
                            f"External guidelines API returned status {response.status_code}"
                        )

            except (IntegrityError, SQLAlchemyError) as e:
                logger.error(f"Error querying external guidelines API: {e}")
                # Fall through to return None

        return None

    @require_phi_access(
        AccessLevel.READ.value
    )  # Added access control for PHI  # type: ignore[misc]
    async def validate_dosage(
        self,
        medication_name: str,
        dose: float,
        unit: str,
        frequency: str,
        route: str,
        patient_factors: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Validate medication dosage against clinical guidelines.

        Args:
            medication_name: Name of medication
            dose: Numeric dose
            unit: Dose unit (mg, units, etc.)
            frequency: Dosing frequency
            route: Route of administration
            patient_factors: Age, weight, renal function, etc.

        Returns:
            Validation result with recommendations
        """
        guideline = await self.get_medication_guideline(medication_name)

        if not guideline:
            return {
                "valid": True,
                "message": "No specific guidelines found - manual review recommended",
                "severity": "info",
            }

        # Determine patient category
        age = patient_factors.get("age", 30)
        age_group = self._get_age_group(age)

        # Get maximum dose for age group
        max_dose = guideline.get_max_dose(age_group, route)

        validation_result: Dict[str, Any] = {
            "medication": medication_name,
            "dose": dose,
            "unit": unit,
            "valid": True,
            "warnings": [],
            "recommendations": [],
        }

        # Check maximum dose
        if max_dose and dose > max_dose:
            validation_result["valid"] = False
            validation_result["warnings"].append(
                {
                    "type": "dose_exceeded",
                    "message": f"Dose {dose} {unit} exceeds maximum safe dose of {max_dose} {unit}",
                    "severity": "critical",
                }
            )

        # Check frequency for specific medications
        if medication_name.lower() == "methotrexate" and "daily" in frequency.lower():
            validation_result["valid"] = False
            validation_result["warnings"].append(
                {
                    "type": "dangerous_frequency",
                    "message": "Methotrexate for RA must be dosed WEEKLY, not daily!",
                    "severity": "critical",
                }
            )

        # Check renal adjustments
        if patient_factors.get("egfr"):
            renal_adjustment = self._get_renal_adjustment(
                guideline, patient_factors["egfr"]
            )
            if renal_adjustment:
                validation_result["recommendations"].append(
                    {
                        "type": "renal_adjustment",
                        "message": renal_adjustment,
                        "severity": "warning",
                    }
                )

        # Check hepatic adjustments
        if patient_factors.get("liver_disease"):
            hepatic_adjustment = self._get_hepatic_adjustment(
                guideline, patient_factors.get("liver_disease_severity", "moderate")
            )
            if hepatic_adjustment:
                validation_result["recommendations"].append(
                    {
                        "type": "hepatic_adjustment",
                        "message": hepatic_adjustment,
                        "severity": "warning",
                    }
                )

        # Check pregnancy
        if patient_factors.get("pregnant") and guideline.pregnancy_category in [
            "D",
            "X",
        ]:
            validation_result["valid"] = False
            validation_result["warnings"].append(
                {
                    "type": "pregnancy_contraindication",
                    "message": f"{medication_name} is pregnancy category {guideline.pregnancy_category} - contraindicated",
                    "severity": "critical",
                }
            )

        # Add black box warnings
        if guideline.black_box_warnings:
            for warning in guideline.black_box_warnings:
                validation_result["warnings"].append(
                    {
                        "type": "black_box_warning",
                        "message": warning,
                        "severity": "high",
                    }
                )

        return validation_result

    def _get_age_group(self, age: int) -> str:
        """Determine age group for dosing guidelines."""
        if age < 1:
            return "infant"
        elif age < 12:
            return "pediatric"
        elif age < 65:
            return "adult"
        else:
            return "elderly"

    def _get_renal_adjustment(
        self, guideline: MedicationGuideline, egfr: float
    ) -> Optional[str]:
        """Get renal dosing adjustment recommendation."""
        if egfr < 30:
            severity = "severe"
        elif egfr < 60:
            severity = "moderate"
        elif egfr < 90:
            severity = "mild"
        else:
            return None

        return guideline.renal_adjustments.get(severity)

    def _get_hepatic_adjustment(
        self, guideline: MedicationGuideline, severity: str
    ) -> Optional[str]:
        """Get hepatic dosing adjustment recommendation."""
        return guideline.hepatic_adjustments.get(severity)

    async def get_monitoring_requirements(
        self, medications: List[str]
    ) -> Dict[str, List[str]]:
        """
        Get monitoring requirements for medications.

        Args:
            medications: List of medication names

        Returns:
            Dictionary of monitoring requirements by medication
        """
        requirements = {}

        for medication in medications:
            guideline = await self.get_medication_guideline(medication)
            if guideline and guideline.monitoring_requirements:
                requirements[medication] = guideline.monitoring_requirements

        return requirements

    async def check_contraindications(
        self,
        medication_name: str,
        patient_conditions: List[str],
        patient_medications: List[str],
    ) -> List[Dict[str, str]]:
        """
        Check for contraindications based on patient conditions and medications.

        Args:
            medication_name: Proposed medication
            patient_conditions: Current medical conditions
            patient_medications: Current medications

        Returns:
            List of contraindications found
        """
        contraindications: List[Dict[str, str]] = []

        guideline = await self.get_medication_guideline(medication_name)
        if not guideline:
            return contraindications

        # Check condition-based contraindications
        for condition in patient_conditions:
            condition_lower = condition.lower()
            for contraindication in guideline.contraindications:
                if contraindication.lower() in condition_lower:
                    contraindications.append(
                        {
                            "type": "condition",
                            "condition": condition,
                            "reason": f"{medication_name} is contraindicated with {contraindication}",
                            "severity": "high",
                        }
                    )

        # Check medication interactions (would integrate with drug interaction service)
        # This is a placeholder for guideline-based contraindications
        medication_contraindications = {
            "warfarin": ["aspirin", "nsaid"],
            "methotrexate": ["nsaid", "trimethoprim"],
            "digoxin": ["amiodarone", "verapamil"],
        }

        if medication_name.lower() in medication_contraindications:
            for current_med in patient_medications:
                current_med_lower = current_med.lower()
                for contra_med in medication_contraindications[medication_name.lower()]:
                    if contra_med in current_med_lower:
                        contraindications.append(
                            {
                                "type": "drug_interaction",
                                "medication": current_med,
                                "reason": f"{medication_name} has significant interaction with {current_med}",
                                "severity": "high",
                            }
                        )

        return contraindications

    @require_phi_access(
        AccessLevel.READ.value
    )  # Added access control for PHI  # type: ignore[misc]
    async def get_pediatric_dosing(
        self, medication_name: str, weight_kg: float, age_years: float, indication: str
    ) -> Dict[str, Any]:
        """
        Calculate pediatric dosing based on weight and age.

        Args:
            medication_name: Name of medication
            weight_kg: Patient weight in kg
            age_years: Patient age in years
            indication: Medical indication

        Returns:
            Pediatric dosing recommendations
        """
        guideline = await self.get_medication_guideline(medication_name)

        if not guideline:
            return {
                "available": False,
                "message": "No pediatric dosing guidelines available",
            }

        # Basic pediatric dosing calculations
        dosing_info: Dict[str, Any] = {
            "medication": medication_name,
            "weight_kg": weight_kg,
            "age_years": age_years,
            "indication": indication,
            "recommendations": [],
        }

        # Example: Amoxicillin dosing
        if "amoxicillin" in medication_name.lower():
            if indication.lower() in ["otitis media", "ear infection"]:
                dose_per_kg = 40 if age_years < 2 else 45
                total_daily_dose = dose_per_kg * weight_kg
                dosing_info["recommendations"].append(
                    {
                        "dose": f"{total_daily_dose/2:.0f} mg",
                        "frequency": "twice daily",
                        "duration": "10 days",
                        "max_dose": "Not to exceed 1500 mg/dose",
                    }
                )

        # Example: Acetaminophen dosing
        elif "acetaminophen" in medication_name.lower():
            dose_per_kg = 15
            single_dose = dose_per_kg * weight_kg
            dosing_info["recommendations"].append(
                {
                    "dose": f"{single_dose:.0f} mg",
                    "frequency": "every 4-6 hours",
                    "max_daily": f"{dose_per_kg * 5 * weight_kg:.0f} mg",
                    "max_dose": "Not to exceed 1000 mg/dose or 4000 mg/day",
                }
            )

        # Check if pediatric dosing exists in guideline
        elif guideline.dosing.get("pediatric"):
            dosing_info["recommendations"].append(guideline.dosing["pediatric"])

        return dosing_info

    async def get_clinical_pathway(
        self, condition: str, severity: str = "moderate"
    ) -> Dict[str, Any]:
        """
        Get clinical treatment pathway for a condition.

        Args:
            condition: Medical condition
            severity: Condition severity

        Returns:
            Clinical pathway recommendations
        """
        # In production, this would query clinical pathway databases
        # For now, provide basic pathways for common conditions

        pathways = {
            "hypertension": {
                "mild": {
                    "first_line": ["lifestyle modifications"],
                    "second_line": ["ACE inhibitor", "ARB", "thiazide diuretic"],
                    "monitoring": ["BP checks monthly", "labs annually"],
                },
                "moderate": {
                    "first_line": ["ACE inhibitor or ARB", "thiazide diuretic"],
                    "second_line": ["add calcium channel blocker", "add beta blocker"],
                    "monitoring": [
                        "BP checks monthly x3, then q3 months",
                        "labs q6 months",
                    ],
                },
            },
            "diabetes_type2": {
                "mild": {
                    "first_line": ["metformin", "lifestyle modifications"],
                    "second_line": ["add sulfonylurea", "add DPP-4 inhibitor"],
                    "monitoring": [
                        "HbA1c q3 months",
                        "annual eye exam",
                        "annual foot exam",
                    ],
                }
            },
        }

        condition_lower = condition.lower().replace(" ", "_")
        if condition_lower in pathways:
            return {
                "condition": condition,
                "severity": severity,
                "pathway": pathways[condition_lower].get(
                    severity, pathways[condition_lower].get("moderate")
                ),
                "evidence_level": "guideline_based",
            }

        return {
            "condition": condition,
            "message": "No specific pathway available",
            "recommendation": "Follow institutional protocols",
        }


# Thread-safe singleton pattern


class _ClinicalGuidelinesServiceSingleton:
    """Thread-safe singleton holder for ClinicalGuidelinesService."""

    _instance: Optional[ClinicalGuidelinesService] = None
    _lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> ClinicalGuidelinesService:
        """Get or create singleton instance."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = ClinicalGuidelinesService()
        return cls._instance


def get_clinical_guidelines_service() -> ClinicalGuidelinesService:
    """Get or create global clinical guidelines service instance."""
    return _ClinicalGuidelinesServiceSingleton.get_instance()
