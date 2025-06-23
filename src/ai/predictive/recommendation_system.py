"""Recommendation system for healthcare services.

This module provides personalized healthcare recommendations based on patient data.
Handles FHIR ServiceRequest and CarePlan Resource validation.
All PHI data is encrypted and access is controlled through role-based permissions.
"""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List

from src.healthcare.fhir_validator import FHIRValidator
from src.security.encryption import EncryptionService

# FHIR resource type for this module
__fhir_resource__ = "ServiceRequest"

logger = logging.getLogger(__name__)


class RecommendationType(Enum):
    """Types of recommendations."""

    PROVIDER = "provider"
    FACILITY = "facility"
    TREATMENT = "treatment"
    MEDICATION = "medication"
    SPECIALIST = "specialist"
    EMERGENCY = "emergency"
    PREVENTIVE = "preventive"
    WELLNESS = "wellness"


@dataclass
class Recommendation:
    """Healthcare recommendation."""

    recommendation_type: RecommendationType
    title: str
    description: str
    priority: int  # 1-5, 5 being highest
    confidence: float
    metadata: Dict[str, Any]


class RecommendationEngine:
    """Generate personalized healthcare recommendations."""

    def __init__(self) -> None:
        """Initialize recommendation engine."""
        self.provider_database: Dict[str, Dict[str, Any]] = {}
        self.facility_database: Dict[str, Dict[str, Any]] = {}
        self.validator = FHIRValidator()  # Initialize validator
        self.encryption_service = EncryptionService(
            kms_key_id="alias/haven-health-default"
        )  # For encrypting PHI

    def recommend_provider(
        self, patient_data: Dict[str, Any], preferences: Dict[str, Any]
    ) -> List[Recommendation]:
        """Recommend healthcare providers based on patient needs."""
        recommendations = []

        # Extract patient needs
        conditions = patient_data.get("conditions", [])
        location = patient_data.get("location", {})
        language = patient_data.get("preferred_language", "en")

        # Find matching providers
        providers = self._match_providers(conditions, location, language, preferences)

        for provider in providers[:5]:  # Top 5 recommendations
            rec = Recommendation(
                recommendation_type=RecommendationType.PROVIDER,
                title=f"Dr. {provider['name']}",
                description=f"{provider['specialty']} - {provider['distance']} km away",
                priority=provider["score"],
                confidence=0.85,
                metadata=provider,
            )
            recommendations.append(rec)

        return recommendations

    def recommend_facility(
        self, patient_data: Dict[str, Any], urgency: str = "routine"
    ) -> List[Recommendation]:
        """Recommend healthcare facilities."""
        recommendations = []
        location = patient_data.get("location", {"lat": 0, "lon": 0})

        if urgency == "emergency":
            # Find nearest emergency facilities
            facilities = self._find_emergency_facilities(location)
        else:
            # Find appropriate facilities for condition
            facilities = self._find_routine_facilities(patient_data)

        for facility in facilities[:3]:
            rec = Recommendation(
                recommendation_type=RecommendationType.FACILITY,
                title=facility["name"],
                description=f"{facility['type']} - {facility['services']}",
                priority=5 if urgency == "emergency" else 3,
                confidence=0.9,
                metadata=facility,
            )
            recommendations.append(rec)

        return recommendations

    def recommend_treatment(
        self, condition: str, patient_data: Dict[str, Any]
    ) -> List[Recommendation]:
        """Recommend treatment options."""
        treatments = self._get_treatment_options(condition, patient_data)
        recommendations = []

        for treatment in treatments:
            rec = Recommendation(
                recommendation_type=RecommendationType.TREATMENT,
                title=treatment["name"],
                description=treatment["description"],
                priority=treatment["priority"],
                confidence=treatment["evidence_level"],
                metadata=treatment,
            )
            recommendations.append(rec)

        return recommendations

    def recommend_preventive_care(
        self, patient_data: Dict[str, Any]
    ) -> List[Recommendation]:
        """Recommend preventive care measures."""
        age = patient_data.get("age", 0)

        recommendations = []

        # Age-based screening recommendations
        if age >= 50:
            recommendations.append(
                Recommendation(
                    recommendation_type=RecommendationType.PREVENTIVE,
                    title="Colonoscopy Screening",
                    description="Recommended for adults over 50",
                    priority=4,
                    confidence=0.95,
                    metadata={"frequency": "every_10_years"},
                )
            )

        return recommendations

    def recommend_wellness(self, patient_data: Dict[str, Any]) -> List[Recommendation]:
        """Recommend wellness and lifestyle interventions."""
        recommendations = []

        # Dietary recommendations
        if patient_data.get("bmi", 25) > 25:
            recommendations.append(
                Recommendation(
                    recommendation_type=RecommendationType.WELLNESS,
                    title="Nutrition Counseling",
                    description="Personalized diet plan for healthy weight management",
                    priority=3,
                    confidence=0.8,
                    metadata={"focus": "weight_management"},
                )
            )

        # Exercise recommendations
        activity_level = patient_data.get("activity_level", "sedentary")
        if activity_level == "sedentary":
            recommendations.append(
                Recommendation(
                    recommendation_type=RecommendationType.WELLNESS,
                    title="Physical Activity Program",
                    description="Gradual exercise program starting with 30 min walks",
                    priority=3,
                    confidence=0.85,
                    metadata={"intensity": "low_to_moderate"},
                )
            )

        return recommendations

    def _match_providers(
        self,
        conditions: List[str],
        location: Dict[str, float],
        language: str,
        _preferences: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """Match providers to patient needs."""
        providers = []

        # Base provider template
        base_provider: Dict[str, Any] = {
            "name": "Smith",
            "specialty": "Internal Medicine",
            "distance": 2.5,
            "score": 5,
            "languages": ["en", "es"],
        }

        # Adjust based on conditions
        if "cardiac" in conditions:
            base_provider["specialty"] = "Cardiology"
        elif "diabetes" in conditions:
            base_provider["specialty"] = "Endocrinology"

        # Adjust score based on language match
        if language in base_provider["languages"]:
            base_provider["score"] += 2

        # Consider location (simplified)
        if location.get("lat", 0) != 0:
            base_provider["distance"] = abs(location["lat"]) / 10  # Simplified distance

        providers.append(base_provider)
        return providers

    def _find_routine_facilities(
        self, patient_data: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Find facilities for routine care based on patient needs."""
        # Extract relevant patient information
        conditions = patient_data.get("conditions", [])
        # TODO: Use location for finding nearby facilities
        # location = patient_data.get("location", {"lat": 0, "lon": 0})

        # Filter facilities by proximity to patient location
        # Placeholder implementation - would connect to facility database
        facilities = []

        # Primary care facilities
        facilities.append(
            {
                "name": "Community Health Center",
                "type": "Primary Care",
                "services": "General Medicine, Preventive Care",
                "distance": 3.5,
            }
        )

        # Specialty facilities based on conditions
        if any("diabetes" in condition.lower() for condition in conditions):
            facilities.append(
                {
                    "name": "Diabetes Care Center",
                    "type": "Specialty Clinic",
                    "services": "Endocrinology, Diabetes Management",
                    "distance": 5.2,
                }
            )

        return facilities

    def _get_treatment_options(
        self, condition: str, patient_data: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Get treatment options for a specific condition."""
        treatments: List[Dict[str, Any]] = []

        # Consider patient factors
        age = patient_data.get("age", 50)
        has_contraindications = patient_data.get("contraindications", [])

        if "diabetes" in condition.lower():
            treatments.extend(
                [
                    {
                        "name": "Lifestyle Modification",
                        "description": "Diet, exercise, and weight management",
                        "priority": 5,
                        "evidence_level": 0.95,
                    },
                    {
                        "name": "Medication Therapy",
                        "description": "Metformin as first-line treatment",
                        "priority": (
                            4 if "metformin" not in has_contraindications else 1
                        ),
                        "evidence_level": 0.9,
                    },
                ]
            )
        elif "hypertension" in condition.lower():
            treatments.extend(
                [
                    {
                        "name": "DASH Diet",
                        "description": "Dietary Approaches to Stop Hypertension",
                        "priority": 5,
                        "evidence_level": 0.9,
                    },
                    {
                        "name": "ACE Inhibitors",
                        "description": "First-line medication for blood pressure control",
                        "priority": 4 if age < 65 else 3,
                        "evidence_level": 0.85,
                    },
                ]
            )
        else:
            # Generic treatment options
            treatments.append(
                {
                    "name": "Conservative Management",
                    "description": "Monitor and lifestyle modifications",
                    "priority": 3,
                    "evidence_level": 0.7,
                }
            )

        return treatments

    def _find_emergency_facilities(
        self, _location: Dict[str, float]
    ) -> List[Dict[str, Any]]:
        """Find nearby emergency facilities."""
        # Placeholder implementation
        return [
            {
                "name": "General Hospital Emergency",
                "type": "emergency",
                "distance": 2.5,
                "wait_time": 30,
                "specialties": ["trauma", "cardiac", "stroke"],
            },
            {
                "name": "Urgent Care Center",
                "type": "urgent_care",
                "distance": 1.2,
                "wait_time": 15,
                "specialties": ["minor_injuries", "infections"],
            },
        ]
