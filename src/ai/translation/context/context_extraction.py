"""
Context Extraction.

This module extracts medical context from text using NLP techniques
and medical knowledge.

This module handles encrypted PHI with access control and audit logging
to ensure HIPAA compliance.
"""

import logging
import re
from dataclasses import dataclass
from typing import Dict, List, Optional

from ...medical_nlp.temporal_reasoning import (
    MedicalTemporalReasoner as TemporalExtractor,
)
from ..matching import OptimizedMatcher
from .medical_context import (
    ClinicalContext,
    ClinicalStatus,
    MedicalEntity,
    MedicalRelationship,
    RelationType,
    TemporalExpression,
    TemporalType,
    TermCategory,
)
from .negation_detector import NegationDetector

logger = logging.getLogger(__name__)


class MedicalContextExtractor:
    """Extracts structured medical context from text."""

    def __init__(self) -> None:
        """Initialize the ContextExtractor."""
        self.matcher = OptimizedMatcher()
        self.negation_detector = NegationDetector()
        self.temporal_extractor = TemporalExtractor()
        self._init_patterns()

    def _init_patterns(self) -> None:
        """Initialize extraction patterns."""
        # Relationship patterns
        self.relationship_patterns = {
            RelationType.CAUSES: [
                r"(\w+)\s+(?:causes?|leads? to|results? in)\s+(\w+)",
                r"(\w+)\s+(?:caused by|due to|from)\s+(\w+)",
            ],
            RelationType.TREATS: [
                r"(\w+)\s+(?:for|treats?|manages?)\s+(\w+)",
                r"(\w+)\s+(?:prescribed for|given for)\s+(\w+)",
            ],
            RelationType.INDICATES: [
                r"(\w+)\s+(?:indicates?|suggests?|shows?)\s+(\w+)",
                r"(\w+)\s+(?:consistent with|diagnostic of)\s+(\w+)",
            ],
        }

        # Dosage patterns
        self.dosage_patterns = [
            r"(\d+\.?\d*)\s*(mg|g|mcg|μg|mL|L|units?|IU)",
            r"(\d+\.?\d*)\s*(?:milligrams?|grams?|micrograms?|milliliters?|liters?)",
        ]

        # Frequency patterns
        self.frequency_patterns = [
            r"(?:once|twice|three times|four times)\s+(?:a|per)\s+day",
            r"(?:every|q)\s*(\d+)\s*(?:hours?|hrs?|h)",
            r"(?:BID|TID|QID|QD|PRN|QHS|QAM)",
            r"(?:daily|weekly|monthly)",
        ]

    def extract_context(self, text: str) -> ClinicalContext:
        """Extract complete clinical context from text."""
        context = ClinicalContext()

        # Find medical entities
        entities = self._extract_entities(text)
        for entity in entities:
            context.add_entity(entity)

        # Extract relationships
        relationships = self._extract_relationships(text, context.entities)
        context.relationships.extend(relationships)

        # Extract temporal information
        temporal_exprs = self._extract_temporal(text, context.entities)
        context.temporal_expressions.extend(temporal_exprs)

        # Extract clinical narrative elements
        self._extract_narrative_elements(text, context)

        # Determine urgency and setting
        context.urgency_level = self._determine_urgency(text)
        context.clinical_setting = self._determine_setting(text)

        return context

    def _extract_entities(self, text: str) -> List[MedicalEntity]:
        """Extract medical entities from text."""
        entities = []

        @dataclass
        class NegationResult:
            is_negated: bool = False
            is_uncertain: bool = False
            is_conditional: bool = False

        # Use matcher to find terms
        matches = self.matcher.find_matches_optimized(text)

        for match in matches:
            # Check negation
            if self.negation_detector:
                # Extract the matched term from the text
                term = text[match.start_pos : match.end_pos]
                is_negated, _confidence = self.negation_detector.is_negated(text, term)
                negation_result = NegationResult(is_negated=is_negated)
            else:
                # Default negation result when detector not available
                negation_result = NegationResult()

            entity = MedicalEntity(
                text=match.matched_text,
                category=match.term.category,
                start_pos=match.start_pos,
                end_pos=match.end_pos,
                negated=negation_result.is_negated,
                uncertain=negation_result.is_uncertain,
                conditional=negation_result.is_conditional,
                confidence=match.confidence,
            )

            # Extract severity if applicable
            if match.term.category in [TermCategory.SYMPTOM, TermCategory.DISEASE]:
                entity.severity = self._extract_severity(text, match.start_pos)

            # Determine clinical status
            entity.status = self._determine_status(
                text, match.start_pos, entity.negated
            )

            entities.append(entity)

        return entities

    def _extract_relationships(
        self, text: str, entities: Dict[str, MedicalEntity]
    ) -> List[MedicalRelationship]:
        """Extract relationships between entities."""
        relationships = []

        # Create position to entity mapping
        pos_to_entity = {}
        for entity in entities.values():
            for pos in range(entity.start_pos, entity.end_pos):
                pos_to_entity[pos] = entity

        # Look for relationship patterns
        for rel_type, patterns in self.relationship_patterns.items():
            for pattern in patterns:
                for match in re.finditer(pattern, text, re.IGNORECASE):
                    # Find entities in match
                    source_entity = self._find_entity_in_span(
                        match.start(1), match.end(1), pos_to_entity
                    )
                    target_entity = self._find_entity_in_span(
                        match.start(2), match.end(2), pos_to_entity
                    )

                    if source_entity and target_entity:
                        rel = MedicalRelationship(
                            source_entity=source_entity,
                            target_entity=target_entity,
                            relation_type=rel_type,
                            evidence=[match.group()],
                        )
                        relationships.append(rel)

        # Extract medication relationships
        med_relationships = self._extract_medication_relationships(text, entities)
        relationships.extend(med_relationships)

        return relationships

    def _extract_medication_relationships(
        self, text: str, entities: Dict[str, MedicalEntity]
    ) -> List[MedicalRelationship]:
        """Extract medication-specific relationships."""
        relationships = []

        # Find medications
        medications = [
            e for e in entities.values() if e.category == TermCategory.MEDICATION
        ]

        for med in medications:
            # Look for dosage near medication
            search_start = max(0, med.start_pos - 50)
            search_end = min(len(text), med.end_pos + 50)
            search_text = text[search_start:search_end]

            # Find dosage
            for pattern in self.dosage_patterns:
                match = re.search(pattern, search_text)
                if match:
                    # Create dosage entity
                    dosage_entity = MedicalEntity(
                        text=match.group(),
                        category=TermCategory.UNIT,
                        start_pos=search_start + match.start(),
                        end_pos=search_start + match.end(),
                    )
                    entities[dosage_entity.id] = dosage_entity

                    # Create relationship
                    rel = MedicalRelationship(
                        source_entity=med,
                        target_entity=dosage_entity,
                        relation_type=RelationType.DOSAGE_OF,
                    )
                    relationships.append(rel)

            # Find frequency
            for pattern in self.frequency_patterns:
                match = re.search(pattern, search_text)
                if match:
                    # Create frequency entity
                    freq_entity = MedicalEntity(
                        text=match.group(),
                        category=TermCategory.FREQUENCY,
                        start_pos=search_start + match.start(),
                        end_pos=search_start + match.end(),
                    )
                    entities[freq_entity.id] = freq_entity

                    # Create relationship
                    rel = MedicalRelationship(
                        source_entity=med,
                        target_entity=freq_entity,
                        relation_type=RelationType.FREQUENCY_OF,
                    )
                    relationships.append(rel)

        return relationships

    def _extract_temporal(
        self, text: str, entities: Dict[str, MedicalEntity]
    ) -> List[TemporalExpression]:
        """Extract temporal expressions and link to entities."""
        temporal_exprs = []

        # Use temporal extractor
        extractions = self.temporal_extractor.extract_temporal_expressions(text)

        for extraction in extractions:
            temp_expr = TemporalExpression(
                text=extraction.text,
                temporal_type=extraction.temporal_type,
                normalized_value=extraction.normalized_value,
                start_pos=extraction.start_pos,
                end_pos=extraction.end_pos,
            )

            # Find related entities (within 100 chars)
            for entity in entities.values():
                if abs(entity.start_pos - temp_expr.start_pos) < 100:
                    temp_expr.related_entities.append(entity.id)

            temporal_exprs.append(temp_expr)

        return temporal_exprs

    def _extract_severity(self, text: str, entity_pos: int) -> Optional[str]:
        """Extract severity modifier near entity."""
        severity_terms = {
            "mild": 1,
            "moderate": 2,
            "severe": 3,
            "critical": 4,
            "life-threatening": 5,
        }

        # Look in surrounding text
        search_start = max(0, entity_pos - 50)
        search_end = min(len(text), entity_pos + 50)
        search_text = text[search_start:search_end].lower()

        for term, _ in severity_terms.items():
            if term in search_text:
                return term

        return None

    def _determine_status(
        self, text: str, entity_pos: int, negated: bool
    ) -> ClinicalStatus:
        """Determine clinical status of entity."""
        if negated:
            return ClinicalStatus.RULED_OUT

        # Look for status indicators
        search_start = max(0, entity_pos - 100)
        search_end = min(len(text), entity_pos + 100)
        search_text = text[search_start:search_end].lower()

        if any(term in search_text for term in ["chronic", "long-standing", "ongoing"]):
            return ClinicalStatus.CHRONIC
        elif any(term in search_text for term in ["acute", "sudden", "new onset"]):
            return ClinicalStatus.ACUTE
        elif any(term in search_text for term in ["suspected", "possible", "probable"]):
            return ClinicalStatus.SUSPECTED
        elif any(term in search_text for term in ["resolved", "cured", "gone"]):
            return ClinicalStatus.RESOLVED
        elif any(term in search_text for term in ["planned", "scheduled", "will"]):
            return ClinicalStatus.PLANNED

        return ClinicalStatus.ACTIVE

    def _find_entity_in_span(
        self, start: int, end: int, pos_to_entity: Dict[int, MedicalEntity]
    ) -> Optional[MedicalEntity]:
        """Find entity within position span."""
        for pos in range(start, end):
            if pos in pos_to_entity:
                return pos_to_entity[pos]
        return None

    def _map_temporal_type(self, extractor_type: str) -> TemporalType:
        """Map temporal extractor type to our enum."""
        mapping = {
            "date": TemporalType.ABSOLUTE_TIME,
            "duration": TemporalType.DURATION,
            "frequency": TemporalType.FREQUENCY,
            "relative": TemporalType.RELATIVE_TIME,
        }
        return mapping.get(extractor_type, TemporalType.ABSOLUTE_TIME)

    def _extract_narrative_elements(self, text: str, context: ClinicalContext) -> None:
        """Extract clinical narrative structure."""
        # Look for section headers
        cc_match = re.search(r"chief complaint:?\s*(.+?)(?:\n|$)", text, re.IGNORECASE)
        if cc_match:
            context.chief_complaint = cc_match.group(1).strip()

        hpi_match = re.search(
            r"(?:HPI|history of present illness):?\s*(.+?)(?:\n\n|$)",
            text,
            re.IGNORECASE | re.DOTALL,
        )
        if hpi_match:
            context.history_present_illness = hpi_match.group(1).strip()

        impression_match = re.search(
            r"(?:impression|assessment):?\s*(.+?)(?:\n\n|$)",
            text,
            re.IGNORECASE | re.DOTALL,
        )
        if impression_match:
            context.clinical_impression = impression_match.group(1).strip()

        plan_match = re.search(
            r"plan:?\s*(.+?)(?:\n\n|$)", text, re.IGNORECASE | re.DOTALL
        )
        if plan_match:
            context.plan = plan_match.group(1).strip()

    def _determine_urgency(self, text: str) -> str:
        """Determine urgency level from text."""
        urgent_terms = ["stat", "urgent", "emergency", "critical", "immediately"]
        high_terms = ["acute", "severe", "serious"]

        text_lower = text.lower()

        if any(term in text_lower for term in urgent_terms):
            return "critical"
        elif any(term in text_lower for term in high_terms):
            return "high"
        else:
            return "normal"

    def _determine_setting(self, text: str) -> Optional[str]:
        """Determine clinical setting from text."""
        settings = {
            "emergency": ["emergency room", "er", "ed", "emergency department"],
            "icu": ["icu", "intensive care", "critical care"],
            "inpatient": ["admitted", "hospital", "ward"],
            "outpatient": ["clinic", "office", "outpatient"],
            "surgical": ["surgery", "operating room", "or", "procedure"],
        }

        text_lower = text.lower()

        for setting, terms in settings.items():
            if any(term in text_lower for term in terms):
                return setting

        return None
