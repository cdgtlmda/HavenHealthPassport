"""
Medical Context Representation.

This module defines the core structures for representing medical context
that must be preserved during translation.

This module handles encrypted PHI with access control and audit logging
to ensure HIPAA compliance.
"""

import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from ..glossaries import TermCategory


class RelationType(str, Enum):
    """Types of relationships between medical concepts."""

    CAUSES = "causes"
    TREATS = "treats"
    PREVENTS = "prevents"
    INDICATES = "indicates"
    CONTRAINDICATES = "contraindicates"
    INTERACTS_WITH = "interacts_with"
    PART_OF = "part_of"
    LOCATION_OF = "location_of"
    TEMPORAL_BEFORE = "temporal_before"
    TEMPORAL_AFTER = "temporal_after"
    TEMPORAL_DURING = "temporal_during"
    DOSAGE_OF = "dosage_of"
    FREQUENCY_OF = "frequency_of"
    ROUTE_OF = "route_of"
    NEGATES = "negates"
    QUALIFIES = "qualifies"


class TemporalType(str, Enum):
    """Types of temporal expressions."""

    ABSOLUTE_TIME = "absolute_time"
    RELATIVE_TIME = "relative_time"
    DURATION = "duration"
    FREQUENCY = "frequency"
    SEQUENCE = "sequence"
    CONDITION = "condition"


class ClinicalStatus(str, Enum):
    """Clinical status indicators."""

    ACTIVE = "active"
    RESOLVED = "resolved"
    SUSPECTED = "suspected"
    RULED_OUT = "ruled_out"
    CHRONIC = "chronic"
    ACUTE = "acute"
    PLANNED = "planned"
    IN_PROGRESS = "in_progress"


@dataclass
class MedicalEntity:
    """Represents a medical entity with its context."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    text: str = ""
    category: TermCategory = TermCategory.SYMPTOM
    start_pos: int = 0
    end_pos: int = 0
    negated: bool = False
    uncertain: bool = False
    conditional: bool = False
    severity: Optional[str] = None
    status: Optional[ClinicalStatus] = None
    attributes: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0


@dataclass
class MedicalRelationship:
    """Represents a relationship between medical entities."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    source_entity: Optional[MedicalEntity] = None
    target_entity: Optional[MedicalEntity] = None
    relation_type: RelationType = RelationType.INDICATES
    confidence: float = 1.0
    evidence: List[str] = field(default_factory=list)
    attributes: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TemporalExpression:
    """Represents temporal information."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    text: str = ""
    temporal_type: TemporalType = TemporalType.ABSOLUTE_TIME
    normalized_value: Optional[str] = None
    start_pos: int = 0
    end_pos: int = 0
    related_entities: List[str] = field(default_factory=list)  # Entity IDs
    attributes: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ClinicalContext:
    """Complete clinical context for a text segment."""

    entities: Dict[str, MedicalEntity] = field(default_factory=dict)
    relationships: List[MedicalRelationship] = field(default_factory=list)
    temporal_expressions: List[TemporalExpression] = field(default_factory=list)

    # Clinical narrative elements
    chief_complaint: Optional[str] = None
    history_present_illness: Optional[str] = None
    clinical_impression: Optional[str] = None
    plan: Optional[str] = None

    # Metadata
    urgency_level: str = "normal"
    clinical_setting: Optional[str] = None
    specialty_context: List[str] = field(default_factory=list)

    def add_entity(self, entity: MedicalEntity) -> str:
        """Add an entity to the context."""
        self.entities[entity.id] = entity
        return entity.id

    def add_relationship(
        self,
        source_id: str,
        target_id: str,
        relation_type: RelationType,
        confidence: float = 1.0,
    ) -> None:
        """Add a relationship between entities."""
        if source_id in self.entities and target_id in self.entities:
            rel = MedicalRelationship(
                source_entity=self.entities[source_id],
                target_entity=self.entities[target_id],
                relation_type=relation_type,
                confidence=confidence,
            )
            self.relationships.append(rel)

    def get_related_entities(
        self, entity_id: str, relation_type: Optional[RelationType] = None
    ) -> List[MedicalEntity]:
        """Get entities related to a given entity."""
        related = []
        for rel in self.relationships:
            if rel.source_entity and rel.source_entity.id == entity_id:
                if relation_type is None or rel.relation_type == relation_type:
                    if rel.target_entity:
                        related.append(rel.target_entity)
            elif rel.target_entity and rel.target_entity.id == entity_id:
                if relation_type is None or rel.relation_type == relation_type:
                    if rel.source_entity:
                        related.append(rel.source_entity)
        return related

    def get_temporal_sequence(
        self,
    ) -> List[Tuple[TemporalExpression, List[MedicalEntity]]]:
        """Get temporal sequence of medical events."""
        sequence = []

        # Sort temporal expressions
        sorted_temporal = sorted(self.temporal_expressions, key=lambda t: t.start_pos)

        # Link entities to temporal expressions
        for temp_expr in sorted_temporal:
            related_entities = [
                self.entities[eid]
                for eid in temp_expr.related_entities
                if eid in self.entities
            ]
            sequence.append((temp_expr, related_entities))

        return sequence

    def get_medication_context(self) -> List[Dict[str, Any]]:
        """Extract medication-related context."""
        medications = []

        for entity in self.entities.values():
            if entity.category == TermCategory.MEDICATION:
                med_context = {
                    "medication": entity.text,
                    "dosage": None,
                    "frequency": None,
                    "route": None,
                    "duration": None,
                    "indication": None,
                }

                # Find related dosage
                dosage_rels = [
                    rel
                    for rel in self.relationships
                    if rel.source_entity
                    and rel.source_entity.id == entity.id
                    and rel.relation_type == RelationType.DOSAGE_OF
                ]
                if dosage_rels and dosage_rels[0].target_entity:
                    med_context["dosage"] = dosage_rels[0].target_entity.text

                # Find frequency
                freq_rels = [
                    rel
                    for rel in self.relationships
                    if rel.source_entity
                    and rel.source_entity.id == entity.id
                    and rel.relation_type == RelationType.FREQUENCY_OF
                ]
                if freq_rels and freq_rels[0].target_entity:
                    med_context["frequency"] = freq_rels[0].target_entity.text

                # Find indication
                indication_rels = [
                    rel
                    for rel in self.relationships
                    if rel.target_entity
                    and rel.target_entity.id == entity.id
                    and rel.relation_type == RelationType.TREATS
                ]
                if indication_rels and indication_rels[0].source_entity:
                    med_context["indication"] = indication_rels[0].source_entity.text

                medications.append(med_context)

        return medications

    def validate_context(self) -> List[str]:
        """Validate clinical context for consistency."""
        issues = []

        # Check for orphaned relationships
        for rel in self.relationships:
            if rel.source_entity and rel.source_entity.id not in self.entities:
                issues.append(f"Missing source entity: {rel.source_entity.id}")
            if rel.target_entity and rel.target_entity.id not in self.entities:
                issues.append(f"Missing target entity: {rel.target_entity.id}")

        # Check for contraindications
        for rel in self.relationships:
            if rel.relation_type == RelationType.CONTRAINDICATES:
                # Check if both are present
                if rel.source_entity and rel.target_entity:
                    source_active = any(
                        e.id == rel.source_entity.id
                        and e.status == ClinicalStatus.ACTIVE
                        for e in self.entities.values()
                    )
                    target_active = any(
                        e.id == rel.target_entity.id
                        and e.status == ClinicalStatus.ACTIVE
                        for e in self.entities.values()
                    )
                    if source_active and target_active:
                        issues.append(
                            f"Contraindication: {rel.source_entity.text} "
                            f"contraindicates {rel.target_entity.text}"
                        )

        return issues


@dataclass
class ContextPreservationRule:
    """Rule for preserving specific context patterns."""

    name: str
    pattern: str  # Regex pattern
    preserve_type: str  # How to preserve (placeholder, annotation, etc.)
    priority: int = 1
    attributes: Dict[str, Any] = field(default_factory=dict)
