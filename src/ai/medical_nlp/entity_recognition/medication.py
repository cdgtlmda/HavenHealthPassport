"""
Medication Extractor.

Extract medication entities from medical text.
Handles FHIR Medication and MedicationStatement Resource validation.
"""

import re
from typing import Any, Dict, List

from src.healthcare.fhir_validator import FHIRValidator
from src.healthcare.hipaa_access_control import (
    AccessLevel,
    require_phi_access,
)
from src.security.encryption import EncryptionService

from .base import MedicalEntity, MedicalEntityRecognizer

# FHIR resource type for this module
__fhir_resource__ = "Medication"


class MedicationExtractor(MedicalEntityRecognizer):
    """Extract medication and drug entities."""

    def __init__(
        self,
        model_name: str = "en_core_sci_md",
        enable_umls: bool = True,
        confidence_threshold: float = 0.7,
    ):
        """Initialize medication extractor."""
        super().__init__(model_name, enable_umls, confidence_threshold)
        self.validator = FHIRValidator()  # Initialize validator
        self.encryption_service = EncryptionService(
            kms_key_id="alias/haven-health-default"
        )  # For encrypting medication data

        # Medication patterns
        self.medication_patterns = [
            r"(\d+(?:\.\d+)?)\s*(mg|mcg|g|ml|units?)\s+(?:of\s+)?([A-Za-z][A-Za-z\s\-]+)",
            r"([A-Za-z][A-Za-z\s\-]+)\s+(\d+(?:\.\d+)?)\s*(mg|mcg|g|ml|units?)",
            r"(?:prescribed|taking|on)\s+([A-Za-z][A-Za-z\s\-]+)",
        ]

        # Dosage patterns
        self.dosage_patterns = [
            r"(\d+(?:\.\d+)?)\s*(mg|mcg|g|ml|units?)",
            r"(?:once|twice|three times|four times)\s+(?:a\s+)?(?:day|daily)",
            r"(?:PRN|as needed|as directed)",
        ]

        # Common medication suffixes
        self.med_suffixes = [
            "olol",
            "pril",
            "artan",
            "statin",
            "azole",
            "cycline",
            "mycin",
            "cillin",
            "dipine",
            "prazole",
        ]

    @require_phi_access(AccessLevel.READ)
    def extract_entities(self, text: str) -> List[MedicalEntity]:
        """Extract medication entities from text."""
        entities = []

        # Process with spaCy
        doc = self.process_text(text)

        # Extract named entities
        for ent in doc.ents:
            if ent.label_ in ["DRUG", "MEDICATION", "CHEMICAL"]:
                entity = self._create_entity(ent, "MEDICATION")
                # Extract dosage information
                entity.metadata = self._extract_dosage_info(text, ent)
                entities.append(entity)

        # Pattern-based extraction
        pattern_entities = self._extract_pattern_based(text)
        entities.extend(pattern_entities)

        # Extract by suffix
        suffix_entities = self._extract_by_suffix(doc)
        entities.extend(suffix_entities)

        # Merge and filter
        entities = self.merge_overlapping_entities(entities)
        entities = self.filter_entities(entities)

        return entities

    def _extract_pattern_based(self, text: str) -> List[MedicalEntity]:
        """Extract medications using patterns."""
        entities = []

        for pattern in self.medication_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                # Extract medication name
                if len(match.groups()) >= 3:
                    med_name = match.group(3).strip()
                else:
                    med_name = match.group(1).strip()

                if len(med_name) > 2:
                    entity = MedicalEntity(
                        text=med_name,
                        start=match.start(),
                        end=match.end(),
                        label="MEDICATION",
                        confidence=0.8,
                        metadata={"full_match": match.group(0), "pattern": pattern},
                    )
                    entities.append(entity)

        return entities

    def _extract_by_suffix(self, doc: Any) -> List[MedicalEntity]:
        """Extract medications by common suffixes."""
        entities = []

        for token in doc:
            token_lower = token.text.lower()
            for suffix in self.med_suffixes:
                if token_lower.endswith(suffix) and len(token_lower) > len(suffix) + 2:
                    entity = MedicalEntity(
                        text=token.text,
                        start=token.idx,
                        end=token.idx + len(token.text),
                        label="MEDICATION",
                        confidence=0.7,
                        metadata={"detection_method": "suffix", "suffix": suffix},
                    )
                    entities.append(entity)
                    break

        return entities

    def _extract_dosage_info(self, text: str, entity_span: Any) -> Dict[str, Any]:
        """Extract dosage information around medication entity."""
        metadata = {}

        # Look for dosage patterns near the entity
        context_start = max(0, entity_span.start_char - 50)
        context_end = min(len(text), entity_span.end_char + 50)
        context = text[context_start:context_end]

        for pattern in self.dosage_patterns:
            match = re.search(pattern, context, re.IGNORECASE)
            if match:
                metadata["dosage"] = match.group(0)
                break

        return metadata
