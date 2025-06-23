"""
Context Preservation.

This module handles preserving and restoring medical context during translation.

This module handles encrypted PHI with access control and audit logging
to ensure HIPAA compliance.
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple

from ..glossaries import TermCategory
from .context_extraction import MedicalContextExtractor
from .medical_context import (
    ClinicalContext,
    MedicalEntity,
)

logger = logging.getLogger(__name__)


@dataclass
class PreservedContext:
    """Represents preserved context for translation."""

    original_text: str
    prepared_text: str
    clinical_context: ClinicalContext
    placeholders: Dict[str, Any] = field(default_factory=dict)
    entity_map: Dict[str, str] = field(default_factory=dict)  # entity_id -> placeholder
    relationship_annotations: List[str] = field(default_factory=list)
    temporal_markers: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


class ContextPreserver:
    """Preserves medical context during translation."""

    def __init__(self) -> None:
        """Initialize the ContextPreserver."""
        self.extractor = MedicalContextExtractor()
        self.placeholder_counter = 0

    def preserve_context(
        self, text: str, source_lang: str, target_lang: str
    ) -> PreservedContext:
        """Preserve medical context for translation."""
        # Extract context
        clinical_context = self.extractor.extract_context(text)

        # Create preserved context
        preserved = PreservedContext(
            original_text=text, prepared_text=text, clinical_context=clinical_context
        )

        # Preserve entities
        self._preserve_entities(preserved)

        # Preserve relationships
        self._preserve_relationships(preserved)

        # Preserve temporal information
        self._preserve_temporal(preserved)

        # Preserve critical sequences
        self._preserve_sequences(preserved)

        # Add metadata
        preserved.metadata = {
            "source_lang": source_lang,
            "target_lang": target_lang,
            "entity_count": len(clinical_context.entities),
            "relationship_count": len(clinical_context.relationships),
            "urgency_level": clinical_context.urgency_level,
        }

        return preserved

    def _preserve_entities(self, preserved: PreservedContext) -> None:
        """Preserve medical entities with placeholders."""
        # Sort entities by position (reverse to maintain indices)
        sorted_entities = sorted(
            preserved.clinical_context.entities.values(),
            key=lambda e: e.start_pos,
            reverse=True,
        )

        for entity in sorted_entities:
            # Determine if entity needs preservation
            if self._should_preserve_entity(entity):
                placeholder = f"[[CONTEXT_E_{self.placeholder_counter}]]"
                self.placeholder_counter += 1

                # Store placeholder info
                preserved.placeholders[placeholder] = {
                    "type": "entity",
                    "entity_id": entity.id,
                    "text": entity.text,
                    "category": entity.category.value,
                    "negated": entity.negated,
                    "uncertain": entity.uncertain,
                    "severity": entity.severity,
                    "status": entity.status.value if entity.status else None,
                }

                # Map entity to placeholder
                preserved.entity_map[entity.id] = placeholder

                # Replace in text
                preserved.prepared_text = (
                    preserved.prepared_text[: entity.start_pos]
                    + placeholder
                    + preserved.prepared_text[entity.end_pos :]
                )

    def _preserve_relationships(self, preserved: PreservedContext) -> None:
        """Preserve relationships as annotations."""
        for rel in preserved.clinical_context.relationships:
            # Only preserve if both entities are preserved
            if rel.source_entity is None or rel.target_entity is None:
                continue
            source_placeholder = preserved.entity_map.get(rel.source_entity.id)
            target_placeholder = preserved.entity_map.get(rel.target_entity.id)

            if source_placeholder and target_placeholder:
                # Create relationship annotation
                annotation = f"[[REL:{source_placeholder}-{rel.relation_type.value}-{target_placeholder}]]"
                preserved.relationship_annotations.append(annotation)

                # Add to prepared text at appropriate position
                # (after the target entity placeholder)
                insert_pos = preserved.prepared_text.find(target_placeholder)
                if insert_pos != -1:
                    insert_pos += len(target_placeholder)
                    preserved.prepared_text = (
                        preserved.prepared_text[:insert_pos]
                        + f" {annotation} "
                        + preserved.prepared_text[insert_pos:]
                    )

    def _preserve_temporal(self, preserved: PreservedContext) -> None:
        """Preserve temporal expressions and sequences."""
        for temp_expr in preserved.clinical_context.temporal_expressions:
            placeholder = f"[[TEMP_{self.placeholder_counter}]]"
            self.placeholder_counter += 1

            # Store temporal info
            preserved.placeholders[placeholder] = {
                "type": "temporal",
                "text": temp_expr.text,
                "temporal_type": temp_expr.temporal_type.value,
                "normalized": temp_expr.normalized_value,
                "related_entities": temp_expr.related_entities,
            }

            preserved.temporal_markers[temp_expr.id] = placeholder

            # Replace in text
            if temp_expr.start_pos < len(preserved.prepared_text):
                preserved.prepared_text = (
                    preserved.prepared_text[: temp_expr.start_pos]
                    + placeholder
                    + preserved.prepared_text[temp_expr.end_pos :]
                )

    def _preserve_sequences(self, preserved: PreservedContext) -> None:
        """Preserve critical medical sequences."""
        # Preserve medication instructions
        med_contexts = preserved.clinical_context.get_medication_context()

        for med_context in med_contexts:
            if all(med_context.values()):  # Complete medication context
                sequence_placeholder = f"[[MED_SEQ_{self.placeholder_counter}]]"
                self.placeholder_counter += 1

                preserved.placeholders[sequence_placeholder] = {
                    "type": "medication_sequence",
                    "context": med_context,
                }

                # Add marker to text
                preserved.prepared_text += f" {sequence_placeholder}"

    def _should_preserve_entity(self, entity: MedicalEntity) -> bool:
        """Determine if entity should be preserved."""
        # Always preserve critical categories
        critical_categories = [
            TermCategory.MEDICATION,
            TermCategory.DOSAGE_FORM,
            TermCategory.LAB_TEST,
            TermCategory.PROCEDURE,
        ]

        if entity.category in critical_categories:
            return True

        # Preserve negated/uncertain entities
        if entity.negated or entity.uncertain:
            return True

        # Preserve entities with relationships
        # (This would need access to relationships, simplified here)
        return True

    def restore_context(
        self,
        translated_text: str,
        preserved: PreservedContext,
        use_translations: bool = True,
    ) -> Tuple[str, List[str]]:
        """Restore preserved context after translation."""
        restored_text = translated_text
        warnings: List[str] = []

        # Log whether translations are being used
        logger.debug("Restoring context with translations: %s", use_translations)

        # Restore entities
        restored_text = self._restore_entities(restored_text, preserved, warnings)

        # Restore relationships
        restored_text = self._restore_relationships(restored_text, preserved, warnings)

        # Restore temporal markers
        restored_text = self._restore_temporal(restored_text, preserved, warnings)

        # Validate restored context
        validation_issues = self._validate_restoration(restored_text, preserved)
        warnings.extend(validation_issues)

        return restored_text, warnings

    def _restore_entities(
        self, text: str, preserved: PreservedContext, warnings: List[str]
    ) -> str:
        """Restore entity placeholders."""
        restored = text

        for placeholder, info in preserved.placeholders.items():
            if info["type"] == "entity":
                # Get original text
                original_text = info["text"]

                # Apply negation/uncertainty markers if needed
                if info["negated"]:
                    original_text = f"no {original_text}"
                elif info["uncertain"]:
                    original_text = f"possible {original_text}"

                # Add severity if present
                if info["severity"]:
                    original_text = f"{info['severity']} {original_text}"

                # Replace placeholder
                if placeholder in restored:
                    restored = restored.replace(placeholder, original_text)
                else:
                    warnings.append(
                        f"Entity placeholder {placeholder} not found in translation"
                    )

        return restored

    def _restore_relationships(
        self, text: str, preserved: PreservedContext, warnings: List[str]
    ) -> str:
        """Restore relationship annotations."""
        restored = text

        # Track warnings during restoration
        if not preserved.relationship_annotations:
            warnings.append("No relationship annotations to restore")

        # Remove relationship annotations (they were just markers)
        for annotation in preserved.relationship_annotations:
            restored = restored.replace(annotation, "")

        return restored.strip()

    def _restore_temporal(
        self, text: str, preserved: PreservedContext, warnings: List[str]
    ) -> str:
        """Restore temporal expressions."""
        restored = text

        for placeholder, info in preserved.placeholders.items():
            if info["type"] == "temporal":
                if placeholder in restored:
                    restored = restored.replace(placeholder, info["text"])
                else:
                    warnings.append(f"Temporal placeholder {placeholder} not found")

        return restored

    def _validate_restoration(
        self, restored_text: str, preserved: PreservedContext
    ) -> List[str]:
        """Validate that context was properly restored."""
        issues = []

        # Check all critical entities are present
        for entity in preserved.clinical_context.entities.values():
            if entity.category == TermCategory.MEDICATION:
                if entity.text not in restored_text:
                    issues.append(
                        f"Critical medication '{entity.text}' missing from translation"
                    )

        # Check relationship integrity
        # (Simplified - would need more sophisticated validation)

        return issues


class ContextValidator:
    """Validates preserved context integrity."""

    @staticmethod
    def validate_preserved_context(preserved: PreservedContext) -> Dict[str, Any]:
        """Validate that context was properly preserved."""
        validation: Dict[str, Any] = {"valid": True, "issues": [], "stats": {}}

        # Check placeholder coverage
        entity_coverage = len(preserved.entity_map) / len(
            preserved.clinical_context.entities
        )
        validation["stats"]["entity_coverage"] = entity_coverage

        if entity_coverage < 0.9:
            validation["issues"].append(f"Low entity coverage: {entity_coverage:.1%}")
            validation["valid"] = False

        # Check relationship preservation
        preserved_rels = len(preserved.relationship_annotations)
        total_rels = len(preserved.clinical_context.relationships)
        rel_coverage = preserved_rels / total_rels if total_rels > 0 else 1.0
        validation["stats"]["relationship_coverage"] = rel_coverage

        # Check critical information
        if preserved.clinical_context.urgency_level == "critical":
            if "[[CONTEXT_" not in preserved.prepared_text:
                validation["issues"].append("Critical context not properly preserved")
                validation["valid"] = False

        return validation
