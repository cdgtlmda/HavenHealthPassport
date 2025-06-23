"""
Symptom Detector.

Detect symptom entities from medical text.
"""

import re
from typing import Any, Dict, List

from .base import MedicalEntity, MedicalEntityRecognizer


class SymptomDetector(MedicalEntityRecognizer):
    """Detect symptom and sign entities."""

    def __init__(
        self,
        model_name: str = "en_core_sci_md",
        enable_umls: bool = True,
        confidence_threshold: float = 0.7,
    ):
        """Initialize symptom detector."""
        super().__init__(model_name, enable_umls, confidence_threshold)

        # Symptom patterns
        self.symptom_patterns = [
            r"(?:complains of|reports|denies|experiences?)\s+([A-Za-z\s]+)",
            r"(?:no|positive for|negative for)\s+([A-Za-z\s]+)",
            r"([A-Za-z\s]+)\s+(?:pain|ache|discomfort|tenderness)",
        ]

        # Common symptoms
        self.common_symptoms = [
            "pain",
            "fever",
            "cough",
            "fatigue",
            "nausea",
            "vomiting",
            "diarrhea",
            "constipation",
            "headache",
            "dizziness",
            "weakness",
            "shortness of breath",
            "chest pain",
            "abdominal pain",
            "back pain",
            "joint pain",
            "swelling",
            "rash",
            "itching",
        ]

        # Severity modifiers
        self.severity_modifiers: Dict[str, float] = {
            "mild": 0.3,
            "moderate": 0.6,
            "severe": 0.9,
            "acute": 0.8,
            "chronic": 0.7,
            "intermittent": 0.5,
        }

    def extract_entities(self, text: str) -> List[MedicalEntity]:
        """Extract symptom entities from text."""
        entities = []

        # Process with spaCy
        doc = self.process_text(text)

        # Extract named entities
        for ent in doc.ents:
            if ent.label_ in ["SYMPTOM", "SIGN", "PROBLEM"]:
                entity = self._create_entity(ent, "SYMPTOM")
                # Add severity information
                entity.metadata = self._extract_severity(text, ent)
                entities.append(entity)

        # Pattern-based extraction
        pattern_entities = self._extract_pattern_based(text)
        entities.extend(pattern_entities)

        # Extract common symptoms
        common_entities = self._extract_common_symptoms(doc)
        entities.extend(common_entities)

        # Merge and filter
        entities = self.merge_overlapping_entities(entities)
        entities = self.filter_entities(entities)

        return entities

    def _extract_pattern_based(self, text: str) -> List[MedicalEntity]:
        """Extract symptoms using patterns."""
        entities = []

        for pattern in self.symptom_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                symptom_text = match.group(1).strip()

                if len(symptom_text) > 2:
                    entity = MedicalEntity(
                        text=symptom_text,
                        start=match.start(1),
                        end=match.end(1),
                        label="SYMPTOM",
                        confidence=0.8,
                    )
                    entities.append(entity)

        return entities

    def _extract_common_symptoms(self, doc: Any) -> List[MedicalEntity]:
        """Extract common symptom mentions."""
        entities = []
        text_lower = doc.text.lower()

        for symptom in self.common_symptoms:
            # Find all occurrences
            start = 0
            while True:
                pos = text_lower.find(symptom, start)
                if pos == -1:
                    break

                # Check word boundaries
                if (pos == 0 or not text_lower[pos - 1].isalnum()) and (
                    pos + len(symptom) == len(text_lower)
                    or not text_lower[pos + len(symptom)].isalnum()
                ):

                    entity = MedicalEntity(
                        text=doc.text[pos : pos + len(symptom)],
                        start=pos,
                        end=pos + len(symptom),
                        label="SYMPTOM",
                        confidence=0.85,
                        metadata={"type": "common_symptom"},
                    )
                    entities.append(entity)

                start = pos + 1

        return entities

    def _extract_severity(self, text: str, entity_span: Any) -> Dict[str, Any]:
        """Extract severity information for symptom."""
        metadata: Dict[str, Any] = {}

        # Look for severity modifiers near the symptom
        context_start = max(0, entity_span.start_char - 30)
        context_end = min(len(text), entity_span.end_char + 30)
        context = text[context_start:context_end].lower()

        for modifier, score in self.severity_modifiers.items():
            if modifier in context:
                metadata["severity"] = modifier
                metadata["severity_score"] = score
                break

        # Check for negation
        negation_words = ["no", "denies", "without", "negative for"]
        for neg_word in negation_words:
            if neg_word in context:
                metadata["negated"] = True
                break

        return metadata
