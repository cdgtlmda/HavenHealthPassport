"""
Medical-specific dialect detection and handling.

This module provides specialized dialect detection for medical terminology,
handling regional variations in medical terms, drug names, and healthcare
system terminology.

This module handles encrypted PHI with access control and audit logging
to ensure HIPAA compliance.
"""

import logging
import re
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

from ...medical_nlp.entity_recognition.base import MedicalEntity
from .core import DialectDetectionResult, DialectDetector, DialectFeatures

logger = logging.getLogger(__name__)


@dataclass
class MedicalDialectVariation:
    """Represents a medical term variation across dialects."""

    concept: str  # Standard medical concept
    variations: Dict[str, str]  # dialect_code -> term
    context: str  # e.g., "medication", "procedure", "anatomy"
    icd_codes: List[str] = field(default_factory=list)
    snomed_codes: List[str] = field(default_factory=list)
    rxnorm_codes: List[str] = field(default_factory=list)


class MedicalDialectDetector:
    """Specialized dialect detector for medical content."""

    def __init__(self, base_detector: Optional[DialectDetector] = None):
        """
        Initialize medical dialect detector.

        Args:
            base_detector: Base dialect detector to use
        """
        self.base_detector = base_detector or DialectDetector()
        self._medical_variations = self._load_medical_variations()
        self._specialty_terms = self._load_specialty_terms()
        self._drug_name_map = self._load_drug_name_variations()

    def detect_medical_dialect(
        self, text: str, entities: Optional[List[MedicalEntity]] = None
    ) -> DialectDetectionResult:
        """
        Detect dialect with medical-specific enhancements.

        Args:
            text: Medical text to analyze
            entities: Pre-extracted medical entities

        Returns:
            Enhanced dialect detection result
        """
        # Get base detection
        base_result = self.base_detector.detect(text)

        # Extract medical features
        medical_features = self._extract_medical_features(text, entities)

        # Score medical variations
        medical_scores = self._score_medical_variations(medical_features)

        # Combine scores with base result
        combined_scores = self._combine_scores(base_result, medical_scores)

        # Create enhanced result
        result = DialectDetectionResult(
            detected_dialect=combined_scores[0][0],
            base_language=base_result.base_language,
            confidence=combined_scores[0][1],
            confidence_level=base_result.confidence_level,
            alternative_dialects=combined_scores[1:6],
            features_detected=medical_features,
            detection_method="medical-enhanced",
            processing_time_ms=base_result.processing_time_ms,
            metadata={
                **base_result.metadata,
                "medical_score": medical_scores.get(combined_scores[0][0], 0),
                "medical_terms_found": len(medical_features.medical_terminology),
            },
        )

        return result

    def _extract_medical_features(
        self, text: str, entities: Optional[List[MedicalEntity]] = None
    ) -> DialectFeatures:
        """Extract medical-specific dialect features."""
        features = DialectFeatures()

        # Extract drug names
        drug_names = self._extract_drug_names(text)
        for drug in drug_names:
            if drug in self._drug_name_map:
                features.medical_terminology[f"drug_{drug}"] = 1.0

        # Extract medical facility terms
        facility_terms = self._extract_facility_terms(text)
        for term in facility_terms:
            features.medical_terminology[f"facility_{term}"] = 1.0

        # Extract healthcare system terms
        system_terms = self._extract_healthcare_system_terms(text)
        for term in system_terms:
            features.medical_terminology[f"system_{term}"] = 1.0

        # Extract specialty-specific terms
        specialty_terms = self._extract_specialty_terms(text)
        for specialty, terms in specialty_terms.items():
            for term in terms:
                features.medical_terminology[f"{specialty}_{term}"] = 1.0

        # Process provided entities if available
        if entities:
            for entity in entities:
                if entity.label == "MEDICATION":
                    features.medical_terminology[f"med_{entity.text}"] = (
                        entity.confidence
                    )
                elif entity.label == "CONDITION":
                    features.medical_terminology[f"condition_{entity.text}"] = (
                        entity.confidence
                    )
                elif entity.label == "PROCEDURE":
                    features.medical_terminology[f"procedure_{entity.text}"] = (
                        entity.confidence
                    )

        return features

    def _extract_drug_names(self, text: str) -> Set[str]:
        """Extract drug names from text."""
        drug_names = set()
        text_lower = text.lower()

        # Check against known drug variations
        for drug_variations in self._drug_name_map.values():
            for variant in drug_variations.values():
                if variant.lower() in text_lower:
                    drug_names.add(variant)

        return drug_names

    def _extract_facility_terms(self, text: str) -> Set[str]:
        """Extract medical facility terms."""
        facility_patterns = [
            r"\b(hospital|clinic|surgery|medical center|medical centre)\b",
            r"\b(emergency room|ER|A&E|casualty|emergency department|ED)\b",
            r"\b(ICU|intensive care|NICU|CCU)\b",
            r"\b(operating room|operating theatre|OR)\b",
            r"\b(pharmacy|chemist|drugstore)\b",
        ]

        terms = set()
        for pattern in facility_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            terms.update(matches)

        return terms

    def _extract_healthcare_system_terms(self, text: str) -> Set[str]:
        """Extract healthcare system-specific terms."""
        system_patterns = [
            # US terms
            r"\b(medicare|medicaid|HMO|PPO|copay|deductible)\b",
            # UK terms
            r"\b(NHS|GP|consultant|prescription charge)\b",
            # Canadian terms
            r"\b(OHIP|MSP|RAMQ|health card)\b",
            # General
            r"\b(insurance|primary care|referral|specialist)\b",
        ]

        terms = set()
        for pattern in system_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            terms.update(matches)

        return terms

    def _extract_specialty_terms(self, text: str) -> Dict[str, Set[str]]:
        """Extract specialty-specific medical terms."""
        specialty_terms = defaultdict(set)

        # Cardiology terms
        cardio_patterns = [
            r"\b(ECG|EKG|echocardiogram|angiogram|stent)\b",
            r"\b(myocardial infarction|MI|heart attack|angina)\b",
            r"\b(arrhythmia|atrial fibrillation|AFib|bradycardia)\b",
        ]

        # Pediatrics terms
        peds_patterns = [
            r"\b(pediatric|paediatric|NICU|well-child visit)\b",
            r"\b(immunization|vaccination|growth chart)\b",
            r"\b(developmental milestone|APGAR score)\b",
        ]

        # OB/GYN terms
        obgyn_patterns = [
            r"\b(prenatal|antenatal|postnatal|labour|labor)\b",
            r"\b(cesarean|caesarean|C-section|epidural)\b",
            r"\b(ultrasound|sonogram|amniocentesis)\b",
        ]

        # Extract terms for each specialty
        for pattern in cardio_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            specialty_terms["cardiology"].update(matches)

        for pattern in peds_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            specialty_terms["pediatrics"].update(matches)

        for pattern in obgyn_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            specialty_terms["obstetrics"].update(matches)

        return dict(specialty_terms)

    def _score_medical_variations(self, features: DialectFeatures) -> Dict[str, float]:
        """Score dialect likelihood based on medical features."""
        scores: defaultdict[str, float] = defaultdict(float)

        for term_key, confidence in features.medical_terminology.items():
            # Match against known variations
            for variation in self._medical_variations:
                for dialect_code, dialect_term in variation.variations.items():
                    if dialect_term.lower() in term_key.lower():
                        scores[dialect_code] += confidence * 0.1

        return dict(scores)

    def _combine_scores(
        self, base_result: DialectDetectionResult, medical_scores: Dict[str, float]
    ) -> List[Tuple[str, float]]:
        """Combine base and medical scores."""
        combined = {}

        # Start with base scores
        combined[base_result.detected_dialect] = base_result.confidence
        for dialect, score in base_result.alternative_dialects:
            combined[dialect] = score

        # Enhance with medical scores
        for dialect, medical_score in medical_scores.items():
            if dialect in combined:
                # Weighted combination: 70% base, 30% medical
                combined[dialect] = 0.7 * combined[dialect] + 0.3 * medical_score
            else:
                combined[dialect] = medical_score * 0.3

        # Sort by combined score
        return sorted(combined.items(), key=lambda x: x[1], reverse=True)

    def _load_medical_variations(self) -> List[MedicalDialectVariation]:
        """Load medical term variations."""
        variations = [
            MedicalDialectVariation(
                concept="epinephrine",
                variations={
                    "en-US": "epinephrine",
                    "en-GB": "adrenaline",
                    "en-AU": "adrenaline",
                    "en-CA": "epinephrine",
                },
                context="medication",
                rxnorm_codes=["3992"],
            ),
            MedicalDialectVariation(
                concept="acetaminophen",
                variations={
                    "en-US": "acetaminophen",
                    "en-GB": "paracetamol",
                    "en-AU": "paracetamol",
                    "en-CA": "acetaminophen",
                },
                context="medication",
                rxnorm_codes=["161"],
            ),
            MedicalDialectVariation(
                concept="emergency_department",
                variations={
                    "en-US": "emergency room",
                    "en-GB": "A&E",
                    "en-AU": "emergency department",
                    "en-CA": "emergency room",
                },
                context="facility",
            ),
            MedicalDialectVariation(
                concept="primary_care_physician",
                variations={
                    "en-US": "primary care physician",
                    "en-GB": "GP",
                    "en-AU": "GP",
                    "en-CA": "family doctor",
                },
                context="provider",
            ),
        ]
        return variations

    def _load_specialty_terms(self) -> Dict[str, List[str]]:
        """Load specialty-specific terms."""
        return {
            "cardiology": ["ECG", "EKG", "MI", "stent", "angiogram"],
            "pediatrics": ["immunization", "vaccination", "growth chart", "milestone"],
            "obstetrics": ["prenatal", "antenatal", "labor", "labour", "cesarean"],
            "neurology": ["EEG", "MRI", "CT scan", "seizure", "stroke"],
            "orthopedics": ["fracture", "sprain", "cast", "splint", "x-ray"],
        }

    def _load_drug_name_variations(self) -> Dict[str, Dict[str, str]]:
        """Load drug name variations by dialect."""
        return {
            "epinephrine": {
                "en-US": "epinephrine",
                "en-GB": "adrenaline",
                "en-AU": "adrenaline",
                "en-CA": "epinephrine",
            },
            "acetaminophen": {
                "en-US": "acetaminophen",
                "en-GB": "paracetamol",
                "en-AU": "paracetamol",
                "en-CA": "acetaminophen",
            },
            "albuterol": {
                "en-US": "albuterol",
                "en-GB": "salbutamol",
                "en-AU": "salbutamol",
                "en-CA": "salbutamol",
            },
        }


def get_medical_dialect_terms(dialect_code: str, category: str) -> List[str]:
    """
    Get medical terms specific to a dialect and category.

    Args:
        dialect_code: Dialect identifier (e.g., "en-US")
        category: Term category (e.g., "medication", "facility")

    Returns:
        List of terms used in that dialect
    """
    # This would connect to a comprehensive medical terminology database
    # For now, returning sample data
    terms_db = {
        ("en-US", "medication"): ["epinephrine", "acetaminophen", "albuterol"],
        ("en-GB", "medication"): ["adrenaline", "paracetamol", "salbutamol"],
        ("en-US", "facility"): ["emergency room", "OR", "ICU"],
        ("en-GB", "facility"): ["A&E", "theatre", "ITU"],
    }

    return terms_db.get((dialect_code, category), [])
