"""
Procedure Extractor.

Extract medical procedure entities from text.
"""

import re
from typing import Any, List

from .base import MedicalEntity, MedicalEntityRecognizer


class ProcedureExtractor(MedicalEntityRecognizer):
    """Extract medical procedure entities."""

    def __init__(
        self,
        model_name: str = "en_core_sci_md",
        enable_umls: bool = True,
        confidence_threshold: float = 0.7,
    ):
        """Initialize procedure extractor."""
        super().__init__(model_name, enable_umls, confidence_threshold)

        # Procedure patterns
        self.procedure_patterns = [
            r"(?:underwent|scheduled for|had|performed)\s+(?:a\s+)?([A-Za-z\s]+)",
            r"([A-Za-z\s]+)\s+(?:surgery|procedure|operation|examination)",
            r"(?:CT|MRI|X-ray|ultrasound|biopsy)\s+(?:of\s+)?(?:the\s+)?([A-Za-z\s]+)?",
        ]

        # Common procedure keywords
        self.procedure_keywords = [
            "surgery",
            "operation",
            "procedure",
            "examination",
            "scan",
            "imaging",
            "biopsy",
            "resection",
            "removal",
            "repair",
            "replacement",
            "transplant",
            "catheterization",
        ]

        # Imaging procedures
        self.imaging_procedures = {
            "CT": "computed tomography",
            "MRI": "magnetic resonance imaging",
            "PET": "positron emission tomography",
            "EKG": "electrocardiogram",
            "ECG": "electrocardiogram",
            "EEG": "electroencephalogram",
            "US": "ultrasound",
        }

    def extract_entities(self, text: str) -> List[MedicalEntity]:
        """Extract procedure entities from text."""
        entities = []

        # Process with spaCy
        doc = self.process_text(text)

        # Extract named entities
        for ent in doc.ents:
            if ent.label_ in ["PROCEDURE", "TEST", "TREATMENT"]:
                entity = self._create_entity(ent, "PROCEDURE")
                entities.append(entity)

        # Pattern-based extraction
        pattern_entities = self._extract_pattern_based(text)
        entities.extend(pattern_entities)

        # Extract imaging procedures
        imaging_entities = self._extract_imaging_procedures(doc)
        entities.extend(imaging_entities)

        # Extract by keywords
        keyword_entities = self._extract_by_keywords(doc)
        entities.extend(keyword_entities)

        # Merge and filter
        entities = self.merge_overlapping_entities(entities)
        entities = self.filter_entities(entities)

        return entities

    def _extract_pattern_based(self, text: str) -> List[MedicalEntity]:
        """Extract procedures using patterns."""
        entities = []

        for pattern in self.procedure_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                if len(match.groups()) > 0:
                    procedure_text = (
                        match.group(1).strip() if match.group(1) else match.group(0)
                    )

                    if len(procedure_text) > 2:
                        entity = MedicalEntity(
                            text=procedure_text,
                            start=match.start(),
                            end=match.end(),
                            label="PROCEDURE",
                            confidence=0.8,
                        )
                        entities.append(entity)

        return entities

    def _extract_imaging_procedures(self, doc: Any) -> List[MedicalEntity]:
        """Extract imaging procedure abbreviations."""
        entities = []

        for token in doc:
            if token.text.upper() in self.imaging_procedures:
                expanded = self.imaging_procedures[token.text.upper()]
                entity = MedicalEntity(
                    text=token.text,
                    start=token.idx,
                    end=token.idx + len(token.text),
                    label="PROCEDURE",
                    confidence=0.9,
                    preferred_term=expanded,
                    metadata={"type": "imaging", "subtype": token.text.upper()},
                )
                entities.append(entity)

        return entities

    def _extract_by_keywords(self, doc: Any) -> List[MedicalEntity]:
        """Extract procedures containing keywords."""
        entities = []

        # Look for noun phrases containing procedure keywords
        for chunk in doc.noun_chunks:
            chunk_lower = chunk.text.lower()
            for keyword in self.procedure_keywords:
                if keyword in chunk_lower:
                    entity = MedicalEntity(
                        text=chunk.text,
                        start=chunk.start_char,
                        end=chunk.end_char,
                        label="PROCEDURE",
                        confidence=0.75,
                        metadata={"keyword": keyword},
                    )
                    entities.append(entity)
                    break

        return entities
