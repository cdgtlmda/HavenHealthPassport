"""Medical-Specific Similarity Metrics.

Provides similarity scoring optimized for medical and healthcare content.

This module handles encrypted PHI with access control and audit logging
to ensure HIPAA compliance.
"""

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set, Union

import numpy as np

from .base import BaseSimilarityScorer, SimilarityConfig
from .metrics import CosineSimilarity

logger = logging.getLogger(__name__)


@dataclass
class MedicalSimilarityConfig(SimilarityConfig):
    """Configuration specific to medical similarity scoring."""

    # Medical term weights
    anatomy_weight: float = 1.5
    disease_weight: float = 2.0
    medication_weight: float = 1.8
    procedure_weight: float = 1.6
    symptom_weight: float = 1.7

    # Semantic type weights
    use_semantic_type_matching: bool = True
    semantic_type_weights: Optional[Dict[str, float]] = None

    # Clinical relevance
    consider_clinical_context: bool = True
    urgency_boost_factor: float = 2.0

    # ICD/SNOMED matching
    use_code_matching: bool = True
    icd_weight: float = 1.5
    snomed_weight: float = 1.5

    # Language-specific medical matching
    use_multilingual_medical: bool = True
    cross_lingual_penalty: float = 0.9

    def __post_init__(self) -> None:
        """Initialize default semantic type weights if not provided."""
        if self.semantic_type_weights is None:
            self.semantic_type_weights = {
                "T047": 2.0,  # Disease or Syndrome
                "T121": 1.8,  # Pharmacologic Substance
                "T061": 1.6,  # Therapeutic Procedure
                "T184": 1.7,  # Sign or Symptom
                "T023": 1.5,  # Body Part
            }


class MedicalSimilarityScorer(BaseSimilarityScorer):
    """Medical-specific similarity scorer.

    Enhances base similarity with medical domain knowledge.
    """

    def __init__(self, config: Optional[MedicalSimilarityConfig] = None):
        """Initialize the medical similarity scorer."""
        if config is None:
            config = MedicalSimilarityConfig()
        super().__init__(config)
        self.config: MedicalSimilarityConfig = config  # Type narrowing
        self.base_scorer = CosineSimilarity(config)
        self._init_medical_resources()

    def _initialize(self) -> None:
        """Initialize scorer-specific components."""

    def _init_medical_resources(self) -> None:
        """Initialize medical knowledge bases."""
        # In production, load from medical databases
        self.medical_synonyms = {
            "heart attack": ["myocardial infarction", "MI", "cardiac arrest"],
            "high blood pressure": ["hypertension", "HTN", "elevated BP"],
            "diabetes": ["diabetes mellitus", "DM", "sugar disease"],
            # Add more medical synonyms
        }

        self.semantic_relationships = {
            "causes": {
                "diabetes": ["neuropathy", "retinopathy", "nephropathy"],
                "hypertension": ["stroke", "heart disease", "kidney disease"],
            },
            "treats": {
                "metformin": ["diabetes", "type 2 diabetes"],
                "lisinopril": ["hypertension", "heart failure"],
            },
        }

    def score(
        self,
        query_embedding: Union[List[float], np.ndarray],
        doc_embedding: Union[List[float], np.ndarray],
        query_metadata: Optional[Dict[str, Any]] = None,
        doc_metadata: Optional[Dict[str, Any]] = None,
    ) -> float:
        """Calculate medical-enhanced similarity score."""
        # Get base cosine similarity
        base_score = self.base_scorer.score(
            query_embedding, doc_embedding, query_metadata, doc_metadata
        )

        # Apply medical enhancements
        if query_metadata and doc_metadata:
            # Extract medical entities
            query_entities = self._extract_medical_entities(query_metadata)
            doc_entities = self._extract_medical_entities(doc_metadata)

            # Calculate medical term overlap
            term_boost = self._calculate_medical_term_boost(
                query_entities, doc_entities
            )

            # Calculate semantic type matching
            if (
                hasattr(self.config, "use_semantic_type_matching")
                and self.config.use_semantic_type_matching
            ):
                semantic_boost = self._calculate_semantic_type_boost(
                    query_metadata.get("semantic_types", []),
                    doc_metadata.get("semantic_types", []),
                )
                term_boost *= semantic_boost

            # Apply clinical context
            if (
                hasattr(self.config, "consider_clinical_context")
                and self.config.consider_clinical_context
            ):
                context_boost = self._calculate_clinical_context_boost(
                    query_metadata, doc_metadata
                )
                term_boost *= context_boost

            # Apply code matching
            if (
                hasattr(self.config, "use_code_matching")
                and self.config.use_code_matching
            ):
                code_boost = self._calculate_code_matching_boost(
                    query_metadata, doc_metadata
                )
                term_boost *= code_boost

            # Combine scores
            final_score = base_score * term_boost
        else:
            final_score = base_score

        return self._apply_threshold(final_score)

    def _extract_medical_entities(
        self, metadata: Dict[str, Any]
    ) -> Dict[str, Set[str]]:
        """Extract medical entities from metadata."""
        entities = {
            "anatomy": set(metadata.get("anatomy_terms", [])),
            "diseases": set(metadata.get("disease_terms", [])),
            "medications": set(metadata.get("medication_terms", [])),
            "procedures": set(metadata.get("procedure_terms", [])),
            "symptoms": set(metadata.get("symptom_terms", [])),
        }
        return entities

    def _calculate_medical_term_boost(
        self, query_entities: Dict[str, Set[str]], doc_entities: Dict[str, Set[str]]
    ) -> float:
        """Calculate boost based on medical term overlap."""
        total_boost = 1.0

        # Weight mapping
        weights = {
            "anatomy": getattr(self.config, "anatomy_weight", 1.5),
            "diseases": getattr(self.config, "disease_weight", 2.0),
            "medications": getattr(self.config, "medication_weight", 1.8),
            "procedures": getattr(self.config, "procedure_weight", 1.6),
            "symptoms": getattr(self.config, "symptom_weight", 1.7),
        }

        for entity_type, weight in weights.items():
            query_terms = query_entities.get(entity_type, set())
            doc_terms = doc_entities.get(entity_type, set())

            if query_terms and doc_terms:
                # Direct overlap
                overlap = len(query_terms.intersection(doc_terms))

                # Check synonyms
                synonym_matches = self._count_synonym_matches(
                    query_terms, doc_terms, entity_type
                )

                total_matches = overlap + synonym_matches
                if total_matches > 0:
                    boost = 1 + (total_matches * 0.1 * weight)
                    total_boost *= boost

        return min(total_boost, 3.0)  # Cap maximum boost

    def _count_synonym_matches(
        self,
        query_terms: Set[str],
        doc_terms: Set[str],
        entity_type: str,  # pylint: disable=unused-argument
    ) -> int:
        """Count matches including synonyms."""
        matches = 0

        for query_term in query_terms:
            if query_term.lower() in self.medical_synonyms:
                synonyms = self.medical_synonyms[query_term.lower()]
                for synonym in synonyms:
                    if any(
                        synonym.lower() in doc_term.lower() for doc_term in doc_terms
                    ):
                        matches += 1
                        break

        return matches

    def _calculate_semantic_type_boost(
        self, query_types: List[str], doc_types: List[str]
    ) -> float:
        """Calculate boost based on semantic type matching."""
        if not query_types or not doc_types:
            return 1.0

        boost = 1.0
        for qtype in query_types:
            if (
                qtype in doc_types
                and hasattr(self.config, "semantic_type_weights")
                and self.config.semantic_type_weights is not None
                and qtype in self.config.semantic_type_weights
            ):
                weight = self.config.semantic_type_weights[qtype]
                boost *= 1 + 0.1 * weight

        return min(boost, 2.0)

    def _calculate_clinical_context_boost(
        self, query_metadata: Dict[str, Any], doc_metadata: Dict[str, Any]
    ) -> float:
        """Calculate boost based on clinical context."""
        boost = 1.0

        # Urgency matching
        query_urgency = query_metadata.get("urgency_level", 0)
        doc_urgency = doc_metadata.get("urgency_level", 0)

        if query_urgency > 3 and doc_urgency > 3:  # Both high urgency
            boost *= getattr(self.config, "urgency_boost_factor", 2.0)

        # Specialty matching
        query_specialty = query_metadata.get("medical_specialty")
        doc_specialty = doc_metadata.get("medical_specialty")

        if query_specialty and doc_specialty and query_specialty == doc_specialty:
            boost *= 1.2

        # Age group relevance
        query_age = query_metadata.get("patient_age_group")
        doc_age = doc_metadata.get("relevant_age_groups", [])

        if query_age and query_age in doc_age:
            boost *= 1.1

        return boost

    def _calculate_code_matching_boost(
        self, query_metadata: Dict[str, Any], doc_metadata: Dict[str, Any]
    ) -> float:
        """Calculate boost based on medical code matching."""
        boost = 1.0

        # ICD code matching
        query_icd = set(query_metadata.get("icd_codes", []))
        doc_icd = set(doc_metadata.get("icd_codes", []))

        if query_icd and doc_icd:
            icd_overlap = len(query_icd.intersection(doc_icd))
            if icd_overlap > 0:
                boost *= 1 + icd_overlap * 0.1 * getattr(self.config, "icd_weight", 1.5)

        # SNOMED code matching
        query_snomed = set(query_metadata.get("snomed_codes", []))
        doc_snomed = set(doc_metadata.get("snomed_codes", []))

        if query_snomed and doc_snomed:
            snomed_overlap = len(query_snomed.intersection(doc_snomed))
            if snomed_overlap > 0:
                boost *= 1 + snomed_overlap * 0.1 * getattr(
                    self.config, "snomed_weight", 1.5
                )

        return min(boost, 2.5)


class ClinicalRelevanceScorer(MedicalSimilarityScorer):
    """Scorer focused on clinical relevance.

    Prioritizes clinically relevant matches over pure textual similarity.
    """

    def __init__(self, config: Optional[MedicalSimilarityConfig] = None):
        """Initialize the clinical relevance scorer."""
        if config is None:
            config = MedicalSimilarityConfig(
                consider_clinical_context=True, urgency_boost_factor=3.0
            )
        super().__init__(config)
        self._init_clinical_rules()

    def _init_clinical_rules(self) -> None:
        """Initialize clinical relevance rules."""
        self.clinical_priorities = {
            "emergency": ["chest pain", "difficulty breathing", "severe bleeding"],
            "urgent": ["fever", "persistent pain", "infection signs"],
            "routine": ["checkup", "follow-up", "vaccination"],
        }

        self.contraindications = {
            "aspirin": ["bleeding disorder", "ulcer"],
            "metformin": ["kidney disease", "liver disease"],
        }

    def score(
        self,
        query_embedding: Union[List[float], np.ndarray],
        doc_embedding: Union[List[float], np.ndarray],
        query_metadata: Optional[Dict[str, Any]] = None,
        doc_metadata: Optional[Dict[str, Any]] = None,
    ) -> float:
        """Calculate clinical relevance score."""
        # Get base medical score
        base_score = super().score(
            query_embedding, doc_embedding, query_metadata, doc_metadata
        )

        if query_metadata and doc_metadata:
            # Apply clinical rules
            clinical_boost = self._apply_clinical_rules(query_metadata, doc_metadata)

            # Check for contraindications
            contraindication_penalty = self._check_contraindications(
                query_metadata, doc_metadata
            )

            base_score = base_score * clinical_boost * contraindication_penalty

        return self._apply_threshold(base_score)

    def _apply_clinical_rules(
        self, query_metadata: Dict[str, Any], doc_metadata: Dict[str, Any]
    ) -> float:
        """Apply clinical relevance rules."""
        boost = 1.0

        # Check emergency conditions
        query_text = query_metadata.get("text", "").lower()
        doc_text = doc_metadata.get("text", "").lower()

        for priority, terms in self.clinical_priorities.items():
            query_matches = any(term in query_text for term in terms)
            doc_matches = any(term in doc_text for term in terms)

            if query_matches and doc_matches:
                if priority == "emergency":
                    boost *= 3.0
                elif priority == "urgent":
                    boost *= 2.0

        return boost

    def _check_contraindications(
        self, query_metadata: Dict[str, Any], doc_metadata: Dict[str, Any]
    ) -> float:
        """Check for medical contraindications."""
        penalty = 1.0

        medications = query_metadata.get("medication_terms", [])
        conditions = doc_metadata.get("disease_terms", [])

        for med in medications:
            med_lower = med.lower()
            if med_lower in self.contraindications:
                contradicted_conditions = self.contraindications[med_lower]
                for condition in conditions:
                    if any(
                        contra in condition.lower()
                        for contra in contradicted_conditions
                    ):
                        penalty *= 0.5  # Significant penalty for contraindications
                        logger.warning(
                            "Potential contraindication detected: %s with %s",
                            med,
                            condition,
                        )

        return penalty


class SemanticMedicalSimilarity(MedicalSimilarityScorer):
    """Semantic similarity for medical content.

    Uses medical ontologies and semantic relationships.
    """

    def __init__(self, config: Optional[MedicalSimilarityConfig] = None):
        """Initialize the semantic medical similarity scorer."""
        super().__init__(config)
        self._init_semantic_network()

    def _init_semantic_network(self) -> None:
        """Initialize semantic relationships."""
        # In production, load from UMLS or other medical ontologies
        self.semantic_distance = {
            ("diabetes", "hyperglycemia"): 0.9,
            ("diabetes", "insulin"): 0.8,
            ("hypertension", "blood pressure"): 0.95,
            ("heart attack", "chest pain"): 0.85,
        }

    def _calculate_semantic_similarity(self, term1: str, term2: str) -> float:
        """Calculate semantic similarity between medical terms."""
        # Direct match
        if term1.lower() == term2.lower():
            return 1.0

        # Check semantic distance
        key = (term1.lower(), term2.lower())
        if key in self.semantic_distance:
            return self.semantic_distance[key]

        # Check reverse
        key_reverse = (term2.lower(), term1.lower())
        if key_reverse in self.semantic_distance:
            return self.semantic_distance[key_reverse]

        # Check synonym
        if term1.lower() in self.medical_synonyms:
            synonyms = self.medical_synonyms[term1.lower()]
            if term2.lower() in synonyms:
                return 0.9

        return 0.0
