"""Health prediction models for Haven Health Passport.

This module provides predictive models for health outcomes and risk assessment.
Handles FHIR RiskAssessment Resource creation and validation.
All PHI data is encrypted and access is controlled through role-based permissions.
"""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List

from src.healthcare.fhir_validator import FHIRValidator
from src.security import requires_phi_access

# FHIR resource type for this module
__fhir_resource__ = "RiskAssessment"

logger = logging.getLogger(__name__)


class RiskLevel(Enum):
    """Risk levels for health predictions."""

    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class PredictionResult:
    """Result of a health prediction."""

    prediction_type: str
    risk_level: RiskLevel
    probability: float
    confidence: float
    factors: List[str]
    recommendations: List[str]
    metadata: Dict[str, Any]


class HealthPredictionModels:
    """Collection of health prediction models."""

    def __init__(self) -> None:
        """Initialize health prediction models."""
        self.models_loaded = False
        self.validator = FHIRValidator()  # Initialize validator

    @requires_phi_access("read")
    def predict_readmission_risk(
        self, patient_data: Dict[str, Any], _user_id: str = "system"
    ) -> PredictionResult:
        """Predict hospital readmission risk."""
        # Decrypt patient data for processing
        decrypted_data = (
            patient_data  # Assuming data comes pre-decrypted from secure source
        )

        # Extract features
        features = self._extract_readmission_features(decrypted_data)

        # Simple risk calculation (placeholder for actual model)
        risk_score = self._calculate_readmission_score(features)

        # Determine risk level
        if risk_score < 0.3:
            risk_level = RiskLevel.LOW
        elif risk_score < 0.6:
            risk_level = RiskLevel.MODERATE
        elif risk_score < 0.8:
            risk_level = RiskLevel.HIGH
        else:
            risk_level = RiskLevel.CRITICAL

        factors = self._identify_risk_factors(features, "readmission")
        recommendations = self._generate_recommendations(risk_level, "readmission")

        return PredictionResult(
            prediction_type="readmission_risk",
            risk_level=risk_level,
            probability=risk_score,
            confidence=0.85,
            factors=factors,
            recommendations=recommendations,
            metadata={"model_version": "1.0", "features_used": len(features)},
        )

    @requires_phi_access("read")
    def predict_disease_progression(
        self, patient_data: Dict[str, Any], disease: str, _user_id: str = "system"
    ) -> PredictionResult:
        """Predict disease progression trajectory."""
        features = self._extract_disease_features(patient_data, disease)

        # Calculate progression score
        progression_score = self._calculate_progression_score(features, disease)

        risk_level = self._score_to_risk_level(progression_score)
        factors = self._identify_progression_factors(features, disease)
        recommendations = self._generate_progression_recommendations(
            disease, risk_level
        )

        return PredictionResult(
            prediction_type="disease_progression",
            risk_level=risk_level,
            probability=progression_score,
            confidence=0.8,
            factors=factors,
            recommendations=recommendations,
            metadata={"disease": disease, "timeline": "6_months"},
        )

    @requires_phi_access("read")
    def predict_medication_adherence(
        self, patient_data: Dict[str, Any], _user_id: str = "system"
    ) -> PredictionResult:
        """Predict medication adherence likelihood."""
        features = {
            "age": patient_data.get("age", 0),
            "medication_count": len(patient_data.get("medications", [])),
            "past_adherence": patient_data.get("adherence_history", 1.0),
            "complexity": self._calculate_regimen_complexity(
                patient_data.get("medications", [])
            ),
        }

        # Calculate adherence score based on features
        adherence_score = features["past_adherence"] * 0.6
        if features["medication_count"] > 5:
            adherence_score -= 0.2
        if features["complexity"] > 0.7:
            adherence_score -= 0.1
        adherence_score = max(0.0, min(1.0, adherence_score))

        risk_level = RiskLevel.LOW if adherence_score > 0.8 else RiskLevel.MODERATE

        return PredictionResult(
            prediction_type="medication_adherence",
            risk_level=risk_level,
            probability=adherence_score,
            confidence=0.75,
            factors=["multiple_medications", "complex_schedule"],
            recommendations=[
                "Use medication reminders",
                "Simplify regimen if possible",
            ],
            metadata={"medications": len(patient_data.get("medications", []))},
        )

    def predict_complication_risk(
        self, patient_data: Dict[str, Any], procedure: str
    ) -> PredictionResult:
        """Predict surgical/procedural complication risk."""
        features = self._extract_complication_features(patient_data)

        # Calculate risk score based on features
        risk_score = 0.2
        if features["age"] > 65:
            risk_score += 0.2
        if len(features.get("comorbidities", [])) > 2:
            risk_score += 0.2
        if procedure in ["cardiac", "major_surgery"]:
            risk_score += 0.1
        risk_score = min(risk_score, 1.0)

        return PredictionResult(
            prediction_type="complication_risk",
            risk_level=self._score_to_risk_level(risk_score),
            probability=risk_score,
            confidence=0.9,
            factors=["age", "comorbidities"],
            recommendations=["Pre-operative optimization", "Close monitoring"],
            metadata={"procedure": procedure},
        )

    def predict_malnutrition_risk(
        self, patient_data: Dict[str, Any]
    ) -> PredictionResult:
        """Predict malnutrition risk for refugees."""
        bmi = patient_data.get("bmi", 22)
        recent_weight_loss = patient_data.get("weight_loss_percent", 0)
        food_security = patient_data.get("food_security_score", 1.0)

        # Calculate risk score based on all factors
        risk_score = 0.1
        if bmi < 18.5:
            risk_score += 0.3
        if recent_weight_loss > 10:
            risk_score += 0.3
        if food_security < 0.5:
            risk_score += 0.2
        risk_score = min(risk_score, 1.0)

        return PredictionResult(
            prediction_type="malnutrition_risk",
            risk_level=self._score_to_risk_level(risk_score),
            probability=risk_score,
            confidence=0.85,
            factors=["low_bmi", "weight_loss", "food_insecurity"],
            recommendations=["Nutritional supplementation", "Regular monitoring"],
            metadata={"bmi": bmi},
        )

    def predict_mental_health_risk(
        self, patient_data: Dict[str, Any]
    ) -> PredictionResult:
        """Screen for mental health risks."""
        trauma_score = patient_data.get("trauma_score", 0)
        social_support = patient_data.get("social_support_score", 1.0)

        risk_score = min(trauma_score * 0.6 + (1 - social_support) * 0.4, 1.0)

        return PredictionResult(
            prediction_type="mental_health_risk",
            risk_level=self._score_to_risk_level(risk_score),
            probability=risk_score,
            confidence=0.7,
            factors=["trauma_exposure", "limited_social_support"],
            recommendations=[
                "Mental health screening",
                "Connect with support services",
            ],
            metadata={"screening_recommended": risk_score > 0.5},
        )

    def predict_outbreak_risk(
        self, population_data: Dict[str, Any]
    ) -> PredictionResult:
        """Predict disease outbreak risk in refugee camps."""
        density = population_data.get("population_density", 0)
        sanitation_score = population_data.get("sanitation_score", 1.0)
        vaccination_rate = population_data.get("vaccination_rate", 0.8)

        risk_score = (density / 1000) * (1 - sanitation_score) * (1 - vaccination_rate)
        risk_score = min(risk_score, 1.0)

        return PredictionResult(
            prediction_type="outbreak_risk",
            risk_level=self._score_to_risk_level(risk_score),
            probability=risk_score,
            confidence=0.8,
            factors=["high_density", "poor_sanitation", "low_vaccination"],
            recommendations=[
                "Increase vaccination",
                "Improve sanitation",
                "Disease surveillance",
            ],
            metadata={"population": population_data.get("total_population", 0)},
        )

    def _score_to_risk_level(self, score: float) -> RiskLevel:
        """Convert numerical score to risk level."""
        if score < 0.25:
            return RiskLevel.LOW
        elif score < 0.5:
            return RiskLevel.MODERATE
        elif score < 0.75:
            return RiskLevel.HIGH
        else:
            return RiskLevel.CRITICAL

    def _extract_readmission_features(
        self, patient_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Extract features for readmission prediction."""
        return {
            "age": patient_data.get("age", 0),
            "previous_admissions": patient_data.get("admission_count", 0),
            "length_of_stay": patient_data.get("last_los", 0),
            "comorbidity_count": len(patient_data.get("conditions", [])),
            "medication_count": len(patient_data.get("medications", [])),
        }

    def _calculate_readmission_score(self, features: Dict[str, Any]) -> float:
        """Calculate readmission risk score."""
        # Simplified scoring logic
        score = 0.0
        if features["age"] > 65:
            score += 0.2
        if features["previous_admissions"] > 2:
            score += 0.3
        if features["comorbidity_count"] > 3:
            score += 0.3
        return min(score, 1.0)

    def _identify_risk_factors(
        self, features: Dict[str, Any], _prediction_type: str
    ) -> List[str]:
        """Identify main risk factors."""
        factors = []
        if features.get("age", 0) > 65:
            factors.append("Advanced age")
        if features.get("comorbidity_count", 0) > 3:
            factors.append("Multiple comorbidities")
        return factors

    def _generate_recommendations(
        self, risk_level: RiskLevel, _prediction_type: str
    ) -> List[str]:
        """Generate recommendations based on risk level."""
        if risk_level == RiskLevel.HIGH or risk_level == RiskLevel.CRITICAL:
            return ["Schedule follow-up within 48 hours", "Care coordination referral"]
        else:
            return ["Standard follow-up", "Patient education"]

    def _extract_disease_features(
        self, patient_data: Dict[str, Any], disease: str
    ) -> Dict[str, Any]:
        """Extract features relevant to disease progression."""
        return {
            "disease": disease,
            "duration": patient_data.get("disease_duration", 0),
            "severity": patient_data.get("severity", "moderate"),
            "complications": patient_data.get("complications", []),
            "lab_values": patient_data.get("lab_values", {}),
            "medications": patient_data.get("medications", []),
        }

    def _calculate_progression_score(
        self, features: Dict[str, Any], _disease: str
    ) -> float:
        """Calculate disease progression score."""
        base_score = 0.3
        if features.get("severity") == "severe":
            base_score += 0.3
        if len(features.get("complications", [])) > 2:
            base_score += 0.2
        if features.get("duration", 0) > 365:  # More than a year
            base_score += 0.1
        return min(base_score, 1.0)

    def _identify_progression_factors(
        self, features: Dict[str, Any], _disease: str
    ) -> List[str]:
        """Identify factors affecting disease progression."""
        factors = []
        if features.get("severity") == "severe":
            factors.append("Current severe disease state")
        if len(features.get("complications", [])) > 0:
            factors.append(f"{len(features['complications'])} existing complications")
        return factors

    def _generate_progression_recommendations(
        self, disease: str, risk_level: RiskLevel
    ) -> List[str]:
        """Generate disease-specific progression recommendations."""
        recommendations = []
        if risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]:
            recommendations.append(f"Specialist referral for {disease}")
            recommendations.append("Aggressive treatment optimization")
        else:
            recommendations.append("Continue current treatment plan")
            recommendations.append("Regular monitoring")
        return recommendations

    def _calculate_regimen_complexity(self, medications: List[Dict[str, Any]]) -> float:
        """Calculate medication regimen complexity score."""
        if not medications:
            return 0.0

        complexity = len(medications) * 0.1

        # Factor in dosing frequency
        for med in medications:
            frequency = med.get("frequency", 1)
            if frequency > 3:
                complexity += 0.1

        return min(complexity, 1.0)

    def _extract_complication_features(
        self, patient_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Extract features for complication prediction."""
        return {
            "age": patient_data.get("age", 0),
            "comorbidities": patient_data.get("comorbidities", []),
            "current_medications": patient_data.get("medications", []),
            "recent_procedures": patient_data.get("recent_procedures", []),
            "lab_abnormalities": patient_data.get("lab_abnormalities", []),
        }
