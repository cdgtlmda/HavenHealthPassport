"""Clinical Negation Context.

Enhanced clinical context for negation detection with section awareness.
 Handles FHIR Resource validation.

Security Note: This module processes PHI data. All clinical data must be:
- Encrypted at rest using AES-256 encryption
- Subject to role-based access control (RBAC) for PHI protection
"""

import re
from typing import Dict, List, Optional

from .negation_detector import MedicalNegationDetector
from .negation_types import NegatedConcept


class ClinicalNegationContext:
    """Enhanced clinical context for negation detection.

    Handles complex clinical scenarios and section-aware negation.
    """

    def __init__(self, detector: MedicalNegationDetector):
        """Initialize clinical negation context with detector."""
        self.detector = detector
        self.section_patterns = self._init_section_patterns()

    def _init_section_patterns(self) -> Dict[str, re.Pattern]:
        """Initialize clinical section patterns."""
        return {
            "chief_complaint": re.compile(
                r"(chief complaint|cc|presenting complaint|reason for visit)",
                re.IGNORECASE,
            ),
            "history": re.compile(
                r"(history of|past medical history|pmh|hx|medical history)",
                re.IGNORECASE,
            ),
            "allergies": re.compile(r"(allergies|nkda|nka|allergic to)", re.IGNORECASE),
            "review_of_systems": re.compile(
                r"(review of systems|ros|systems review)", re.IGNORECASE
            ),
            "physical_exam": re.compile(
                r"(physical exam|pe|examination|exam findings)", re.IGNORECASE
            ),
            "assessment": re.compile(
                r"(assessment|impression|a/p|assessment and plan)", re.IGNORECASE
            ),
            "medications": re.compile(
                r"(medications|meds|current medications|home meds)", re.IGNORECASE
            ),
            "social_history": re.compile(
                r"(social history|sh|social hx)", re.IGNORECASE
            ),
            "family_history": re.compile(
                r"(family history|fh|family hx)", re.IGNORECASE
            ),
        }

    def detect_with_context(
        self, text: str, section: Optional[str] = None
    ) -> List[NegatedConcept]:
        """Detect negations with clinical section awareness.

        Args:
            text: Clinical text
            section: Optional section identifier

        Returns:
            Context-aware negated concepts
        """
        # If no section provided, try to detect it
        if not section:
            section = self._detect_section(text)

        # Standard detection
        negated_concepts = self.detector.detect_negations(text)

        # Adjust based on section
        if section:
            negated_concepts = self._adjust_for_section(negated_concepts, section)

        return negated_concepts

    def _detect_section(self, text: str) -> Optional[str]:
        """Try to detect clinical section from text."""
        # Check first 50 characters for section headers
        text_start = text[:50].lower()

        for section, pattern in self.section_patterns.items():
            if pattern.search(text_start):
                return section

        return None

    def _adjust_for_section(
        self, concepts: List[NegatedConcept], section: str
    ) -> List[NegatedConcept]:
        """Adjust negation confidence based on section."""
        for concept in concepts:
            if section == "allergies":
                # In allergies section, "no" usually means absence of allergies
                if concept.negation_trigger.lower() in ["no", "none", "nkda", "denies"]:
                    concept.confidence = 0.95

            elif section == "review_of_systems":
                # In ROS, negations are very common and reliable
                concept.confidence = min(concept.confidence * 1.1, 1.0)

            elif section == "history":
                # Historical negations might be less relevant to current state
                if "history" not in concept.context.lower():
                    concept.confidence *= 0.8

            elif section == "medications":
                # Medication negations often mean not taking
                if concept.negation_trigger.lower() in [
                    "no",
                    "not taking",
                    "discontinued",
                ]:
                    concept.confidence = 0.9

            elif section == "physical_exam":
                # Physical exam negations are usually reliable
                concept.confidence = min(concept.confidence * 1.05, 1.0)

            elif section == "social_history":
                # Social history negations (no smoking, no alcohol) are important
                if any(
                    term in concept.concept.lower()
                    for term in ["smoking", "tobacco", "alcohol", "drugs"]
                ):
                    concept.confidence = 0.95

        return concepts

    def extract_pertinent_negatives(
        self, text: str, section: Optional[str] = None
    ) -> List[NegatedConcept]:
        """Extract clinically significant negative findings.

        Pertinent negatives are important absent findings that help
        rule out conditions.
        """
        negated_concepts = self.detect_with_context(text, section)

        # Filter for high-confidence, non-pseudo negations
        pertinent = [
            concept
            for concept in negated_concepts
            if concept.confidence >= 0.7 and not concept.is_pseudo_negation
        ]

        # Additional filtering based on clinical relevance
        pertinent = [
            concept for concept in pertinent if self._is_clinically_relevant(concept)
        ]

        return pertinent

    def _is_clinically_relevant(self, concept: NegatedConcept) -> bool:
        """Determine if a negated concept is clinically relevant."""
        # List of clinically important negative findings
        important_negatives = [
            "chest pain",
            "shortness of breath",
            "fever",
            "chills",
            "nausea",
            "vomiting",
            "diarrhea",
            "bleeding",
            "trauma",
            "loss of consciousness",
            "seizure",
            "headache",
            "dizziness",
            "weakness",
            "numbness",
            "vision changes",
            "hearing loss",
            "rash",
            "swelling",
            "pain",
            "tenderness",
            "discharge",
        ]

        concept_lower = concept.concept.lower()
        return any(neg in concept_lower for neg in important_negatives)


def validate_fhir_data(data: dict) -> dict:
    """Validate FHIR data.

    Args:
        data: Data to validate

    Returns:
        Validation result with 'valid', 'errors', and 'warnings' keys
    """
    errors: List[str] = []
    warnings: List[str] = []

    if not data:
        errors.append("No data provided")

    return {"valid": len(errors) == 0, "errors": errors, "warnings": warnings}
