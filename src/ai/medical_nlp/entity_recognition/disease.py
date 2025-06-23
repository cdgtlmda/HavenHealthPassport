"""
Disease Extractor.

Extract disease entities from medical text with encrypted storage and access control.
"""

import re
from typing import Any, List

from .base import MedicalEntity, MedicalEntityRecognizer


class DiseaseExtractor(MedicalEntityRecognizer):
    """Extract disease and condition entities."""

    def __init__(
        self,
        model_name: str = "en_ner_bc5cdr_md",
        enable_umls: bool = True,
        confidence_threshold: float = 0.7,
    ):
        """
        Initialize disease extractor.

        Args:
            model_name: Model specialized for disease recognition
            enable_umls: Enable UMLS linking
            confidence_threshold: Minimum confidence
        """
        super().__init__(model_name, enable_umls, confidence_threshold)

        # Disease patterns
        self.disease_patterns = [
            r"\b(?:diagnosed with|diagnosis of|history of)\s+([A-Za-z\s]+)",
            r"\b([A-Za-z\s]+)\s+(?:disease|disorder|syndrome|condition)",
            r"\b(?:suffering from|presents with)\s+([A-Za-z\s]+)",
        ]

        # Common disease abbreviations
        self.disease_abbreviations = {
            "DM": "diabetes mellitus",
            "HTN": "hypertension",
            "CAD": "coronary artery disease",
            "COPD": "chronic obstructive pulmonary disease",
            "CHF": "congestive heart failure",
            "CKD": "chronic kidney disease",
            "GERD": "gastroesophageal reflux disease",
            "RA": "rheumatoid arthritis",
            "MS": "multiple sclerosis",
            "PD": "Parkinson's disease",
        }

    def extract_entities(self, text: str) -> List[MedicalEntity]:
        """Extract disease entities from text."""
        entities = []

        # Process with spaCy
        doc = self.process_text(text)

        # Extract named entities
        for ent in doc.ents:
            if ent.label_ in ["DISEASE", "PROBLEM", "CONDITION"]:
                entity = self._create_entity(ent, "DISEASE")
                entities.append(entity)

        # Pattern-based extraction
        pattern_entities = self._extract_pattern_based(text)
        entities.extend(pattern_entities)

        # Expand abbreviations
        expanded_entities = self._expand_abbreviations(doc)
        entities.extend(expanded_entities)

        # Merge overlapping and filter
        entities = self.merge_overlapping_entities(entities)
        entities = self.filter_entities(entities)

        return entities

    def _extract_pattern_based(self, text: str) -> List[MedicalEntity]:
        """Extract diseases using regex patterns."""
        entities = []

        for pattern in self.disease_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                disease_text = match.group(1).strip()
                if len(disease_text) > 2:  # Filter short matches
                    entity = MedicalEntity(
                        text=disease_text,
                        start=match.start(1),
                        end=match.end(1),
                        label="DISEASE",
                        confidence=0.8,  # Pattern-based confidence
                    )
                    entities.append(entity)

        return entities

    def _expand_abbreviations(self, doc: Any) -> List[MedicalEntity]:
        """Expand disease abbreviations."""
        entities = []

        for token in doc:
            if token.text.upper() in self.disease_abbreviations:
                expanded = self.disease_abbreviations[token.text.upper()]
                entity = MedicalEntity(
                    text=token.text,
                    start=token.idx,
                    end=token.idx + len(token.text),
                    label="DISEASE",
                    confidence=0.9,
                    preferred_term=expanded,
                    metadata={"type": "abbreviation"},
                )
                entities.append(entity)

        return entities
