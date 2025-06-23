"""
AWS Comprehend Medical Integration for Translation Validation.

This module provides integration with AWS Comprehend Medical to validate
medical entity extraction and ensure translation accuracy.
"""

import asyncio
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import boto3
from botocore.exceptions import ClientError

from src.healthcare.hipaa_access_control import AccessLevel, require_phi_access
from src.translation.medical_terminology import MedicalTerminologyManager
from src.utils.logging import get_logger

logger = get_logger(__name__)


class EntityType(str, Enum):
    """Medical entity types recognized by Comprehend Medical."""

    MEDICATION = "MEDICATION"
    MEDICAL_CONDITION = "MEDICAL_CONDITION"
    ANATOMY = "ANATOMY"
    TEST_TREATMENT_PROCEDURE = "TEST_TREATMENT_PROCEDURE"
    PROTECTED_HEALTH_INFORMATION = "PROTECTED_HEALTH_INFORMATION"
    TIME_EXPRESSION = "TIME_EXPRESSION"


class EntityCategory(str, Enum):
    """Entity categories for medical terms."""

    MEDICATION = "MEDICATION"
    MEDICAL_CONDITION = "MEDICAL_CONDITION"
    ANATOMY = "ANATOMY"
    TEST_TREATMENT_PROCEDURE = "TEST_TREATMENT_PROCEDURE"


@dataclass
class MedicalEntity:
    """Represents a medical entity extracted from text."""

    text: str
    type: EntityType
    category: EntityCategory
    score: float
    begin_offset: int
    end_offset: int
    traits: List[Dict[str, Any]] = field(default_factory=list)
    attributes: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def is_negated(self) -> bool:
        """Check if entity is negated."""
        return any(trait.get("Name") == "NEGATION" for trait in self.traits)

    @property
    def is_diagnosis(self) -> bool:
        """Check if entity is a diagnosis."""
        return any(trait.get("Name") == "DIAGNOSIS" for trait in self.traits)


@dataclass
class ValidationResult:
    """Result of medical translation validation."""

    is_valid: bool
    confidence: float
    missing_entities: List[str]
    additional_entities: List[str]
    mismatched_types: List[Tuple[str, str, str]]  # (text, source_type, target_type)
    warnings: List[str]
    entity_mapping: Dict[str, str]


class ComprehendMedicalValidator:
    """Validates medical translations using AWS Comprehend Medical."""

    def __init__(self, region: str = "us-east-1"):
        """
        Initialize Comprehend Medical validator.

        Args:
            region: AWS region for Comprehend Medical
        """
        self.comprehend_medical = boto3.client("comprehendmedical", region_name=region)
        self.terminology_manager = MedicalTerminologyManager()
        self._entity_cache: Dict[str, List[MedicalEntity]] = {}

    @require_phi_access(AccessLevel.READ)
    async def validate_translation(
        self,
        source_text: str,
        source_lang: str,
        translated_text: str,
        target_lang: str,
        strict_mode: bool = False,
    ) -> ValidationResult:
        """
        Validate medical translation by comparing entities.

        Args:
            source_text: Original text
            source_lang: Source language code
            translated_text: Translated text
            target_lang: Target language code
            strict_mode: If True, require exact entity matching

        Returns:
            Validation result with details
        """
        try:
            # Extract entities from source and translated texts
            source_entities = await self._extract_entities(source_text, source_lang)
            target_entities = await self._extract_entities(translated_text, target_lang)

            # Compare entities
            result = self._compare_entities(
                source_entities, target_entities, source_lang, target_lang, strict_mode
            )

            return result

        except (ClientError, ValueError, AttributeError) as e:
            logger.error(f"Error validating translation: {e}")
            return ValidationResult(
                is_valid=False,
                confidence=0.0,
                missing_entities=[],
                additional_entities=[],
                mismatched_types=[],
                warnings=[f"Validation error: {str(e)}"],
                entity_mapping={},
            )

    async def _extract_entities(self, text: str, language: str) -> List[MedicalEntity]:
        """Extract medical entities from text."""
        # Check cache first
        cache_key = f"{language}:{hash(text)}"
        if cache_key in self._entity_cache:
            return self._entity_cache[cache_key]

        try:
            # For non-English text, we need to translate first
            # (Comprehend Medical only supports English)
            if language != "en":
                # This would integrate with translation service
                # For now, return empty list for non-English
                logger.warning(
                    f"Comprehend Medical only supports English. Language {language} not supported."
                )
                return []

            # Call Comprehend Medical
            response = await asyncio.get_event_loop().run_in_executor(
                None, lambda: self.comprehend_medical.detect_entities_v2(Text=text)
            )

            # Parse entities
            entities = []
            for entity_data in response.get("Entities", []):
                entity = MedicalEntity(
                    text=entity_data["Text"],
                    type=EntityType(entity_data["Type"]),
                    category=EntityCategory(entity_data["Category"]),
                    score=entity_data["Score"],
                    begin_offset=entity_data["BeginOffset"],
                    end_offset=entity_data["EndOffset"],
                    traits=entity_data.get("Traits", []),
                    attributes=entity_data.get("Attributes", []),
                )
                entities.append(entity)

            # Cache results
            self._entity_cache[cache_key] = entities

            return entities

        except ClientError as e:
            logger.error(f"AWS Comprehend Medical error: {e}")
            return []
        except (TypeError, RuntimeError) as e:
            logger.error(f"Error extracting entities: {e}")
            return []

    def _compare_entities(
        self,
        source_entities: List[MedicalEntity],
        target_entities: List[MedicalEntity],
        source_lang: str,
        target_lang: str,
        strict_mode: bool,
    ) -> ValidationResult:
        """Compare source and target entities."""
        # Group entities by type
        source_by_type = self._group_entities_by_type(source_entities)
        target_by_type = self._group_entities_by_type(target_entities)

        missing_entities = []
        additional_entities = []
        mismatched_types: List[Tuple[str, str, str]] = []
        entity_mapping = {}
        warnings = []

        # Check each entity type
        for entity_type in EntityType:
            source_set = set(
                e.text.lower() for e in source_by_type.get(entity_type, [])
            )
            target_set = set(
                e.text.lower() for e in target_by_type.get(entity_type, [])
            )

            # Find missing entities
            missing = source_set - target_set
            if missing:
                missing_entities.extend(list(missing))
                if entity_type in [EntityType.MEDICATION, EntityType.MEDICAL_CONDITION]:
                    warnings.append(
                        f"Critical {entity_type.value} missing in translation"
                    )

            # Find additional entities
            additional = target_set - source_set
            if additional and strict_mode:
                additional_entities.extend(list(additional))

            # Map entities
            for source_entity in source_by_type.get(entity_type, []):
                # Try to find corresponding entity in target
                matched = False
                for target_entity in target_by_type.get(entity_type, []):
                    if self._entities_match(
                        source_entity, target_entity, source_lang, target_lang
                    ):
                        entity_mapping[source_entity.text] = target_entity.text
                        matched = True
                        break

                if not matched and source_entity.type in [
                    EntityType.MEDICATION,
                    EntityType.MEDICAL_CONDITION,
                ]:
                    warnings.append(
                        f"No match found for critical entity: {source_entity.text}"
                    )

        # Calculate confidence score
        total_entities = len(source_entities)
        if total_entities == 0:
            confidence = 1.0
        else:
            matched_entities = len(entity_mapping)
            confidence = matched_entities / total_entities

        # Determine validity
        is_valid = (
            confidence >= 0.8  # At least 80% entities matched
            and len(missing_entities) == 0  # No missing entities
            and (
                not strict_mode or len(additional_entities) == 0
            )  # No additional entities in strict mode
        )

        return ValidationResult(
            is_valid=is_valid,
            confidence=confidence,
            missing_entities=missing_entities,
            additional_entities=additional_entities,
            mismatched_types=mismatched_types,
            warnings=warnings,
            entity_mapping=entity_mapping,
        )

    def _group_entities_by_type(
        self, entities: List[MedicalEntity]
    ) -> Dict[EntityType, List[MedicalEntity]]:
        """Group entities by their type."""
        grouped: Dict[EntityType, List[MedicalEntity]] = {}
        for entity in entities:
            if entity.type not in grouped:
                grouped[entity.type] = []
            grouped[entity.type].append(entity)
        return grouped

    def _entities_match(
        self,
        source: MedicalEntity,
        target: MedicalEntity,
        source_lang: str,
        target_lang: str,
    ) -> bool:
        """Check if two entities match across languages."""
        # Same type required
        if source.type != target.type:
            return False

        # Check if it's a known translation
        translation = self.terminology_manager.get_medical_term_translation(
            source.text, source_lang, target_lang
        )

        if translation and target.text.lower() == translation.lower():
            return True

        # For medications, check active ingredients
        if source.type == EntityType.MEDICATION:
            return self._medications_match(source.text, target.text)

        # For conditions, check ICD mappings
        if source.type == EntityType.MEDICAL_CONDITION:
            return self._conditions_match(source.text, target.text)

        return False

    def _medications_match(self, med1: str, med2: str) -> bool:
        """Check if two medications match (brand/generic)."""
        # This would check drug databases
        # For now, simple string comparison
        return med1.lower() == med2.lower()

    def _conditions_match(self, cond1: str, cond2: str) -> bool:
        """Check if two medical conditions match."""
        # This would check ICD codes and synonyms
        # For now, simple string comparison
        return cond1.lower() == cond2.lower()

    async def extract_medical_concepts(
        self, text: str, language: str = "en"
    ) -> Dict[str, List[str]]:
        """
        Extract medical concepts from text.

        Args:
            text: Input text
            language: Language code

        Returns:
            Dictionary of concept types to concept lists
        """
        entities = await self._extract_entities(text, language)

        concepts: Dict[str, List[str]] = {
            "medications": [],
            "conditions": [],
            "anatomy": [],
            "procedures": [],
            "symptoms": [],
        }

        for entity in entities:
            if entity.type == EntityType.MEDICATION:
                concepts["medications"].append(entity.text)
            elif entity.type == EntityType.MEDICAL_CONDITION:
                if entity.is_diagnosis:
                    concepts["conditions"].append(entity.text)
                else:
                    concepts["symptoms"].append(entity.text)
            elif entity.type == EntityType.ANATOMY:
                concepts["anatomy"].append(entity.text)
            elif entity.type == EntityType.TEST_TREATMENT_PROCEDURE:
                concepts["procedures"].append(entity.text)

        return concepts

    async def validate_medical_terminology(
        self, text: str, expected_terms: List[str], language: str = "en"
    ) -> Tuple[bool, List[str]]:
        """
        Validate that expected medical terms are present.

        Args:
            text: Text to validate
            expected_terms: Expected medical terms
            language: Language code

        Returns:
            Tuple of (is_valid, missing_terms)
        """
        entities = await self._extract_entities(text, language)
        extracted_terms = {entity.text.lower() for entity in entities}

        missing_terms = []
        for term in expected_terms:
            if term.lower() not in extracted_terms:
                # Check for variations
                found = False
                for extracted in extracted_terms:
                    if term.lower() in extracted or extracted in term.lower():
                        found = True
                        break

                if not found:
                    missing_terms.append(term)

        return len(missing_terms) == 0, missing_terms


# Singleton instance storage
class _ComprehendValidatorSingleton:
    """Singleton storage for ComprehendMedicalValidator."""

    instance: Optional[ComprehendMedicalValidator] = None


def get_comprehend_validator() -> ComprehendMedicalValidator:
    """Get or create the global Comprehend Medical validator instance."""
    if _ComprehendValidatorSingleton.instance is None:
        _ComprehendValidatorSingleton.instance = ComprehendMedicalValidator()
    return _ComprehendValidatorSingleton.instance
