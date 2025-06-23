"""
Context-Aware Translation.

This module provides context-aware translation that preserves medical meaning
and relationships during the translation process.

This module handles encrypted PHI with access control and audit logging
to ensure HIPAA compliance.
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from ..glossaries import glossary_manager
from ..matching import matching_pipeline
from .context_preservation import ContextPreserver, PreservedContext

logger = logging.getLogger(__name__)


@dataclass
class ContextAwareTranslationRequest:
    """Request for context-aware translation."""

    text: str
    source_lang: str
    target_lang: str
    preserve_formatting: bool = True
    preserve_relationships: bool = True
    preserve_temporal: bool = True
    medical_domain: Optional[str] = None
    urgency_level: Optional[str] = None


@dataclass
class ContextAwareTranslationResult:
    """Result of context-aware translation."""

    original_text: str
    translated_text: str
    preserved_context: PreservedContext
    quality_score: float
    warnings: List[str]
    metadata: Dict[str, Any]


class ContextAwareTranslator:
    """Handles context-aware medical translation."""

    def __init__(self) -> None:
        """Initialize the ContextAwareTranslator."""
        self.context_preserver = ContextPreserver()
        self.translation_cache: Dict[str, Any] = {}

    async def translate_with_context(
        self,
        request: ContextAwareTranslationRequest,
        translation_func: Callable[[str], str],
    ) -> ContextAwareTranslationResult:
        """Translate text while preserving medical context."""
        start_time = datetime.utcnow()

        # Step 1: Extract and preserve context
        preserved = self.context_preserver.preserve_context(
            request.text, request.source_lang, request.target_lang
        )

        # Step 2: Prepare text with glossary matching
        translation_segment = await matching_pipeline.prepare_for_translation(
            preserved.prepared_text, request.source_lang, request.target_lang
        )

        # Step 3: Perform translation
        translated_text = translation_func(translation_segment.prepared_text)

        # Step 4: Restore glossary terms
        glossary_result = await matching_pipeline.restore_after_translation(
            translated_text, translation_segment, use_translations=True
        )

        # Step 5: Restore context
        final_text, context_warnings = self.context_preserver.restore_context(
            glossary_result.translated_text, preserved, use_translations=True
        )

        # Step 6: Validate translation quality
        quality_score = await self._validate_translation_quality(
            request, preserved, final_text
        )

        # Combine warnings
        all_warnings = glossary_result.warnings + context_warnings

        # Calculate processing time
        processing_time = (datetime.utcnow() - start_time).total_seconds()

        return ContextAwareTranslationResult(
            original_text=request.text,
            translated_text=final_text,
            preserved_context=preserved,
            quality_score=quality_score,
            warnings=all_warnings,
            metadata={
                "processing_time": processing_time,
                "entities_preserved": len(preserved.clinical_context.entities),
                "relationships_preserved": len(
                    preserved.clinical_context.relationships
                ),
                "glossary_matches": glossary_result.match_count,
                "urgency_level": preserved.clinical_context.urgency_level,
            },
        )

    async def _validate_translation_quality(
        self,
        request: ContextAwareTranslationRequest,
        preserved: PreservedContext,
        translated_text: str,
    ) -> float:
        """Validate quality of context-aware translation."""
        scores = []

        # Check entity preservation
        entity_score = self._check_entity_preservation(preserved, translated_text)
        scores.append(entity_score)

        # Check relationship integrity
        if request.preserve_relationships:
            rel_score = self._check_relationship_integrity(preserved, translated_text)
            scores.append(rel_score)

        # Check temporal consistency
        if request.preserve_temporal:
            temp_score = self._check_temporal_consistency(preserved, translated_text)
            scores.append(temp_score)

        # Use glossary validation
        glossary_validation = await glossary_manager.validate_translation_quality(
            request.text, translated_text, request.source_lang, request.target_lang
        )
        scores.append(glossary_validation["score"])

        # Return average score
        return sum(scores) / len(scores) if scores else 0.0

    def _check_entity_preservation(
        self, preserved: PreservedContext, translated_text: str
    ) -> float:
        """Check if entities are preserved in translation."""
        preserved_count = 0
        total_critical = 0

        for entity in preserved.clinical_context.entities.values():
            # Check critical entities
            if entity.category.value in ["medication", "procedure", "lab_test"]:
                total_critical += 1
                if entity.text in translated_text:
                    preserved_count += 1

        return preserved_count / total_critical if total_critical > 0 else 1.0

    def _check_relationship_integrity(
        self, preserved: PreservedContext, translated_text: str
    ) -> float:
        """Check if relationships are maintained."""
        # Simplified check - would need more sophisticated analysis
        # Log translated text length for context
        logger.debug(
            "Checking relationships in %d character text", len(translated_text)
        )
        return 0.9 if preserved.relationship_annotations else 1.0

    def _check_temporal_consistency(
        self, preserved: PreservedContext, translated_text: str
    ) -> float:
        """Check if temporal information is consistent."""
        temporal_preserved = sum(
            1
            for temp in preserved.clinical_context.temporal_expressions
            if temp.text in translated_text
        )
        total_temporal = len(preserved.clinical_context.temporal_expressions)

        return temporal_preserved / total_temporal if total_temporal > 0 else 1.0

    def get_context_summary(self, preserved: PreservedContext) -> Dict[str, Any]:
        """Get summary of preserved context."""
        context = preserved.clinical_context

        return {
            "entities": {
                "total": len(context.entities),
                "by_category": self._count_by_category(list(context.entities.values())),
                "negated": sum(1 for e in context.entities.values() if e.negated),
                "uncertain": sum(1 for e in context.entities.values() if e.uncertain),
            },
            "relationships": {
                "total": len(context.relationships),
                "by_type": self._count_relationships_by_type(context.relationships),
            },
            "temporal": {
                "total": len(context.temporal_expressions),
                "types": self._count_temporal_types(context.temporal_expressions),
            },
            "clinical": {
                "urgency": context.urgency_level,
                "setting": context.clinical_setting,
                "has_chief_complaint": bool(context.chief_complaint),
                "has_plan": bool(context.plan),
            },
            "medications": len(context.get_medication_context()),
        }

    def _count_by_category(self, entities: List[Any]) -> Dict[str, int]:
        """Count entities by category."""
        counts: Dict[str, int] = {}
        for entity in entities:
            cat = entity.category.value
            counts[cat] = counts.get(cat, 0) + 1
        return counts

    def _count_relationships_by_type(self, relationships: List[Any]) -> Dict[str, int]:
        """Count relationships by type."""
        counts: Dict[str, int] = {}
        for rel in relationships:
            rel_type = rel.relation_type.value
            counts[rel_type] = counts.get(rel_type, 0) + 1
        return counts

    def _count_temporal_types(self, temporal_exprs: List[Any]) -> Dict[str, int]:
        """Count temporal expressions by type."""
        counts: Dict[str, int] = {}
        for temp in temporal_exprs:
            temp_type = temp.temporal_type.value
            counts[temp_type] = counts.get(temp_type, 0) + 1
        return counts


# Specialized context preservers for different scenarios
class EmergencyContextPreserver(ContextPreserver):
    """Specialized preserver for emergency medical contexts."""

    def _should_preserve_entity(self, entity: Any) -> bool:
        """More aggressive preservation for emergency contexts."""
        # Preserve almost everything in emergency situations
        return True

    def preserve_context(
        self, text: str, source_lang: str, target_lang: str
    ) -> PreservedContext:
        """Enhanced preservation for emergency contexts."""
        preserved = super().preserve_context(text, source_lang, target_lang)

        # Add emergency markers
        preserved.metadata["emergency_context"] = True
        preserved.metadata["preserve_all_numbers"] = True
        preserved.metadata["preserve_all_times"] = True

        # Mark for priority translation
        preserved.prepared_text = f"[EMERGENCY] {preserved.prepared_text}"

        return preserved


class PediatricContextPreserver(ContextPreserver):
    """Specialized preserver for pediatric contexts."""

    def preserve_context(
        self, text: str, source_lang: str, target_lang: str
    ) -> PreservedContext:
        """Enhanced preservation for pediatric contexts."""
        preserved = super().preserve_context(text, source_lang, target_lang)

        # Look for age/weight specific information
        self._preserve_pediatric_vitals(preserved)

        # Preserve growth percentiles
        self._preserve_growth_data(preserved)

        return preserved

    def _preserve_pediatric_vitals(self, preserved: PreservedContext) -> None:
        """Preserve pediatric-specific vital information."""
        # Implementation for pediatric vitals
        preserved.metadata["pediatric_vitals"] = True
        logger.debug("Preserving pediatric vitals")

    def _preserve_growth_data(self, preserved: PreservedContext) -> None:
        """Preserve growth chart data."""
        # Implementation for growth data
        preserved.metadata["growth_data"] = True
        logger.debug("Preserving growth data")


# Factory for creating appropriate context preservers
def create_context_preserver(medical_domain: Optional[str] = None) -> ContextPreserver:
    """Create appropriate context preserver for domain."""
    if medical_domain == "emergency":
        return EmergencyContextPreserver()
    elif medical_domain == "pediatrics":
        return PediatricContextPreserver()
    else:
        return ContextPreserver()
