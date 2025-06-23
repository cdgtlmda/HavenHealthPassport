"""
AWS HealthLake Integration for Clinical Data Cross-Referencing.

This module provides integration with AWS HealthLake for FHIR-compliant
clinical data storage and cross-referencing in translations.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import boto3
from botocore.exceptions import ClientError

from src.healthcare.fhir_client import FHIRClient
from src.healthcare.hipaa_access_control import audit_phi_access
from src.security.access_control import AccessPermission, require_permission
from src.services.encryption_service import EncryptionService
from src.utils.logging import get_logger

logger = get_logger(__name__)


class ResourceType(str, Enum):
    """FHIR resource types supported by HealthLake."""

    PATIENT = "Patient"
    CONDITION = "Condition"
    MEDICATION = "Medication"
    MEDICATION_REQUEST = "MedicationRequest"
    OBSERVATION = "Observation"
    PROCEDURE = "Procedure"
    IMMUNIZATION = "Immunization"
    ALLERGY_INTOLERANCE = "AllergyIntolerance"
    DIAGNOSTIC_REPORT = "DiagnosticReport"


@dataclass
class ClinicalConcept:
    """Represents a clinical concept with cross-references."""

    concept_id: str
    display_name: str
    system: str  # coding system (SNOMED, ICD-10, etc.)
    code: str
    translations: Dict[str, str]  # language -> translated name
    synonyms: List[str]
    related_concepts: List[str]

    def get_translation(self, language: str) -> str:
        """Get translation for specified language."""
        return self.translations.get(language, self.display_name)


@dataclass
class CrossReferenceResult:
    """Result of clinical data cross-referencing."""

    term: str
    language: str
    matches: List[ClinicalConcept]
    confidence_scores: Dict[str, float]
    suggested_translation: Optional[str]
    warnings: List[str]


class HealthLakeCrossReference:
    """Cross-references clinical data using AWS HealthLake."""

    def __init__(self, datastore_id: str, region: str = "us-east-1"):
        """
        Initialize HealthLake cross-reference service.

        Args:
            datastore_id: HealthLake datastore ID
            region: AWS region
        """
        self.healthlake = boto3.client("healthlake", region_name=region)
        self.datastore_id = datastore_id
        self.fhir_client = FHIRClient()
        self._concept_cache: Dict[str, List[ClinicalConcept]] = {}
        self.encryption_service = EncryptionService()

    async def cross_reference_term(
        self,
        term: str,
        source_language: str,
        target_language: str,
        context: Optional[str] = None,
    ) -> CrossReferenceResult:
        """
        Cross-reference a medical term across languages.

        Args:
            term: Medical term to cross-reference
            source_language: Source language code
            target_language: Target language code
            context: Additional context for disambiguation

        Returns:
            Cross-reference result with matches and translations
        """
        try:
            # Search for matching concepts
            concepts = await self._search_concepts(term, source_language, context)

            # Score and rank matches
            scored_concepts = self._score_concepts(concepts, term, context)

            # Get translations
            translated_concepts = await self._get_translations(
                scored_concepts, target_language
            )

            # Select best translation
            suggested = self._select_best_translation(
                translated_concepts, target_language
            )

            return CrossReferenceResult(
                term=term,
                language=source_language,
                matches=translated_concepts,
                confidence_scores={c.concept_id: s for c, s in scored_concepts},
                suggested_translation=suggested,
                warnings=[],
            )

        except (ClientError, ValueError, RuntimeError) as e:
            logger.error(f"Error cross-referencing term '{term}': {e}")
            return CrossReferenceResult(
                term=term,
                language=source_language,
                matches=[],
                confidence_scores={},
                suggested_translation=None,
                warnings=[f"Cross-reference error: {str(e)}"],
            )

    async def _search_concepts(
        self, term: str, language: str, context: Optional[str]
    ) -> List[ClinicalConcept]:
        """Search for clinical concepts matching the term."""
        # Check cache
        cache_key = f"{term}:{language}:{context}"
        if cache_key in self._concept_cache:
            return self._concept_cache[cache_key]

        concepts = []

        try:
            # Search in HealthLake datastore
            # This would use the FHIR search API
            search_params = {"_text": term, "_language": language}

            # Search different resource types
            for resource_type in [ResourceType.CONDITION, ResourceType.MEDICATION]:
                results = await self._search_resource(resource_type, search_params)

                for result in results:
                    concept = self._extract_concept(result, resource_type)
                    if concept:
                        concepts.append(concept)

            # Cache results
            self._concept_cache[cache_key] = concepts

        except (ClientError, ValueError, RuntimeError) as e:
            logger.error(f"Error searching concepts: {e}")

        return concepts

    async def _search_resource(
        self, _resource_type: ResourceType, _params: Dict[str, str]
    ) -> List[Dict[str, Any]]:
        """Search FHIR resources in HealthLake."""
        try:
            # This would use the actual HealthLake API
            # For now, returning empty list
            return []

        except ClientError as e:
            logger.error(f"HealthLake search error: {e}")
            return []

    def _extract_concept(
        self, resource: Dict[str, Any], resource_type: ResourceType
    ) -> Optional[ClinicalConcept]:
        """Extract clinical concept from FHIR resource."""
        try:
            if resource_type == ResourceType.CONDITION:
                result = self._extract_condition_concept(resource)
                return (
                    result
                    if isinstance(result, ClinicalConcept) or result is None
                    else None
                )
            elif resource_type == ResourceType.MEDICATION:
                return self._extract_medication_concept(resource)
            else:
                return None

        except (ClientError, KeyError, ValueError, AttributeError) as e:
            logger.error(f"Error extracting concept: {e}")
            return None

    @audit_phi_access("phi_access__extract_condition_concept")
    @require_permission(AccessPermission.READ_PHI)
    def _extract_condition_concept(self, condition: Dict[str, Any]) -> ClinicalConcept:
        """Extract concept from Condition resource."""
        coding = condition.get("code", {}).get("coding", [{}])[0]

        return ClinicalConcept(
            concept_id=f"condition-{coding.get('code', '')}",
            display_name=coding.get("display", ""),
            system=coding.get("system", ""),
            code=coding.get("code", ""),
            translations={},
            synonyms=self._get_synonyms(condition),
            related_concepts=[],
        )

    def _extract_medication_concept(
        self, medication: Dict[str, Any]
    ) -> ClinicalConcept:
        """Extract concept from Medication resource."""
        coding = medication.get("code", {}).get("coding", [{}])[0]

        return ClinicalConcept(
            concept_id=f"medication-{coding.get('code', '')}",
            display_name=coding.get("display", ""),
            system=coding.get("system", ""),
            code=coding.get("code", ""),
            translations={},
            synonyms=self._get_synonyms(medication),
            related_concepts=[],
        )

    def _get_synonyms(self, resource: Dict[str, Any]) -> List[str]:
        """Extract synonyms from FHIR resource."""
        synonyms = []

        # Get alternative codings
        codings = resource.get("code", {}).get("coding", [])
        for coding in codings:
            display = coding.get("display", "")
            if display and display not in synonyms:
                synonyms.append(display)

        # Get text representation
        text = resource.get("code", {}).get("text", "")
        if text and text not in synonyms:
            synonyms.append(text)

        return synonyms

    def _score_concepts(
        self, concepts: List[ClinicalConcept], term: str, context: Optional[str]
    ) -> List[Tuple[ClinicalConcept, float]]:
        """Score and rank concept matches."""
        scored = []

        for concept in concepts:
            score = self._calculate_match_score(concept, term, context)
            scored.append((concept, score))

        # Sort by score descending
        scored.sort(key=lambda x: x[1], reverse=True)

        return scored

    def _calculate_match_score(
        self, concept: ClinicalConcept, term: str, context: Optional[str]
    ) -> float:
        """Calculate match score for a concept."""
        score = 0.0
        term_lower = term.lower()

        # Exact match
        if concept.display_name.lower() == term_lower:
            score = 1.0
        # Partial match
        elif term_lower in concept.display_name.lower():
            score = 0.8
        # Synonym match
        elif any(term_lower == syn.lower() for syn in concept.synonyms):
            score = 0.7
        # Partial synonym match
        elif any(term_lower in syn.lower() for syn in concept.synonyms):
            score = 0.5

        # Context bonus
        if context and score > 0:
            context_lower = context.lower()
            if any(ctx in context_lower for ctx in ["diagnosis", "condition"]):
                if concept.concept_id.startswith("condition-"):
                    score += 0.1
            elif any(
                ctx in context_lower for ctx in ["medication", "drug", "prescription"]
            ):
                if concept.concept_id.startswith("medication-"):
                    score += 0.1

        return min(score, 1.0)

    async def _get_translations(
        self, scored_concepts: List[Tuple[ClinicalConcept, float]], target_language: str
    ) -> List[ClinicalConcept]:
        """Get translations for concepts."""
        translated = []

        for concept, _ in scored_concepts:
            # Get translations from various sources
            translations = await self._fetch_translations(concept, target_language)

            # Update concept with translations
            concept.translations.update(translations)
            translated.append(concept)

        return translated

    async def _fetch_translations(
        self, concept: ClinicalConcept, target_language: str
    ) -> Dict[str, str]:
        """Fetch translations for a concept."""
        translations = {}

        # This would integrate with translation services
        # For now, return empty translations
        translations[target_language] = concept.display_name

        return translations

    def _select_best_translation(
        self, concepts: List[ClinicalConcept], target_language: str
    ) -> Optional[str]:
        """Select the best translation from matches."""
        if not concepts:
            return None

        # Use the first concept's translation
        best_concept = concepts[0]
        return best_concept.get_translation(target_language)

    async def validate_clinical_terms(
        self, text: str, language: str, expected_concepts: List[str]
    ) -> Tuple[bool, List[str]]:
        """
        Validate that clinical terms are properly used.

        Args:
            text: Text to validate
            language: Language code
            expected_concepts: Expected clinical concepts

        Returns:
            Tuple of (is_valid, missing_concepts)
        """
        # Extract concepts from text
        found_concepts = set()

        for expected in expected_concepts:
            result = await self.cross_reference_term(
                expected, language, language  # Same language for validation
            )

            if result.matches:
                # Check if any match appears in text
                text_lower = text.lower()
                for match in result.matches:
                    if match.display_name.lower() in text_lower:
                        found_concepts.add(expected)
                        break
                    for synonym in match.synonyms:
                        if synonym.lower() in text_lower:
                            found_concepts.add(expected)
                            break

        missing = set(expected_concepts) - found_concepts
        return len(missing) == 0, list(missing)

    async def enrich_translation_with_clinical_data(
        self,
        translation: str,
        source_language: str,
        target_language: str,
        clinical_terms: List[str],
    ) -> str:
        """
        Enrich translation with standardized clinical terminology.

        Args:
            translation: Initial translation
            source_language: Source language
            target_language: Target language
            clinical_terms: Clinical terms to standardize

        Returns:
            Enriched translation
        """
        enriched = translation

        for term in clinical_terms:
            result = await self.cross_reference_term(
                term, source_language, target_language
            )

            if result.suggested_translation:
                # Replace with standardized translation
                # This is simplified - would need proper text replacement
                enriched = enriched.replace(term, result.suggested_translation)

        return enriched


# Singleton instance storage
class _HealthLakeReferenceSingleton:
    """Singleton storage for HealthLakeCrossReference."""

    instance: Optional[HealthLakeCrossReference] = None
    datastore_id: Optional[str] = None


def get_healthlake_reference(datastore_id: str) -> HealthLakeCrossReference:
    """Get or create HealthLake cross-reference instance."""
    if (
        _HealthLakeReferenceSingleton.instance is None
        or _HealthLakeReferenceSingleton.datastore_id != datastore_id
    ):
        _HealthLakeReferenceSingleton.instance = HealthLakeCrossReference(datastore_id)
        _HealthLakeReferenceSingleton.datastore_id = datastore_id
    return _HealthLakeReferenceSingleton.instance
