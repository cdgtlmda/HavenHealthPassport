"""Re-ranking Module.

Provides re-ranking capabilities to improve search results.
"""

import datetime
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple, Type, cast

logger = logging.getLogger(__name__)


@dataclass
class RerankResult:
    """Result from re-ranking."""

    doc_id: str
    original_score: float
    rerank_score: float
    metadata: Dict[str, Any]


class ReRanker(ABC):
    """Base class for re-ranking implementations."""

    def __init__(self, top_k: int = 20):
        """Initialize re-ranker.

        Args:
            top_k: Number of top results to re-rank
        """
        self.top_k = top_k
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    @abstractmethod
    def rerank(
        self,
        query: str,
        results: List[Tuple[str, float, Dict[str, Any]]],
        query_metadata: Optional[Dict[str, Any]] = None,
    ) -> List[RerankResult]:
        """Re-rank search results.

        Args:
            query: Original query text
            results: List of (doc_id, score, metadata) tuples
            query_metadata: Optional query metadata

        Returns:
            List of re-ranked results
        """

    def _get_top_k_results(
        self, results: List[Tuple[str, float, Dict[str, Any]]]
    ) -> List[Tuple[str, float, Dict[str, Any]]]:
        """Get top K results for re-ranking."""
        # Sort by score (descending)
        sorted_results = sorted(results, key=lambda x: x[1], reverse=True)
        return sorted_results[: self.top_k]


class MedicalReRanker(ReRanker):
    """Medical-specific re-ranker.

    Re-ranks based on medical relevance and clinical importance.
    """

    def __init__(self, top_k: int = 20):
        """Initialize the medical re-ranker."""
        super().__init__(top_k)
        self._init_medical_priorities()

    def _init_medical_priorities(self) -> None:
        """Initialize medical priority rules."""
        self.condition_priorities = {
            "emergency": 3.0,
            "urgent": 2.0,
            "routine": 1.0,
            "preventive": 0.8,
        }

        self.specialty_relevance = {
            "cardiology": ["heart", "cardiac", "cardiovascular"],
            "neurology": ["brain", "neurological", "stroke"],
            "oncology": ["cancer", "tumor", "malignant"],
            "pediatrics": ["child", "pediatric", "infant"],
        }

    def rerank(
        self,
        query: str,
        results: List[Tuple[str, float, Dict[str, Any]]],
        query_metadata: Optional[Dict[str, Any]] = None,
    ) -> List[RerankResult]:
        """Re-rank based on medical relevance."""
        # Get top K results
        top_results = self._get_top_k_results(results)

        reranked = []
        for doc_id, original_score, doc_metadata in top_results:
            # Calculate medical relevance boost
            relevance_boost = self._calculate_medical_relevance(
                query, doc_metadata, query_metadata
            )

            # Calculate clinical priority boost
            priority_boost = self._calculate_clinical_priority(
                doc_metadata, query_metadata
            )

            # Calculate specialty match
            specialty_boost = self._calculate_specialty_match(
                query, doc_metadata, query_metadata
            )

            # Combine scores
            rerank_score = (
                original_score * relevance_boost * priority_boost * specialty_boost
            )

            reranked.append(
                RerankResult(
                    doc_id=doc_id,
                    original_score=original_score,
                    rerank_score=rerank_score,
                    metadata=doc_metadata,
                )
            )

        # Sort by re-rank score
        reranked.sort(key=lambda x: x.rerank_score, reverse=True)

        return reranked

    def _calculate_medical_relevance(
        self,
        query: str,  # pylint: disable=unused-argument # Reserved for query-specific relevance calculation
        doc_metadata: Dict[str, Any],
        _query_metadata: Optional[
            Dict[str, Any]
        ] = None,  # pylint: disable=unused-argument # Reserved for query metadata
    ) -> float:
        """Calculate medical relevance boost."""
        boost = 1.0

        # Check for medical evidence level
        evidence_level = doc_metadata.get("evidence_level", "low")
        evidence_boosts = {
            "systematic_review": 2.0,
            "rct": 1.8,
            "cohort": 1.5,
            "case_control": 1.3,
            "expert_opinion": 1.1,
            "low": 1.0,
        }
        boost *= evidence_boosts.get(evidence_level, 1.0)

        # Check publication recency
        pub_year = doc_metadata.get("publication_year")
        if pub_year:
            current_year = datetime.datetime.now().year
            years_old = current_year - pub_year

            if years_old <= 2:
                boost *= 1.3  # Very recent
            elif years_old <= 5:
                boost *= 1.1  # Recent
            elif years_old > 10:
                boost *= 0.8  # Older publication

        # Check source credibility
        source_type = doc_metadata.get("source_type", "unknown")
        source_boosts = {
            "journal": 1.5,
            "textbook": 1.4,
            "guideline": 1.6,
            "hospital_protocol": 1.3,
            "patient_education": 1.1,
            "unknown": 1.0,
        }
        boost *= source_boosts.get(source_type, 1.0)

        return boost

    def _calculate_clinical_priority(
        self, doc_metadata: Dict[str, Any], query_metadata: Optional[Dict[str, Any]]
    ) -> float:
        """Calculate clinical priority boost."""
        boost = 1.0

        # Get urgency levels
        doc_urgency = doc_metadata.get("clinical_urgency", "routine")
        query_urgency = (
            query_metadata.get("urgency", "routine") if query_metadata else "routine"
        )

        # Apply priority boosts
        doc_priority = self.condition_priorities.get(doc_urgency, 1.0)
        query_priority = self.condition_priorities.get(query_urgency, 1.0)

        # Match urgency levels
        if doc_urgency == query_urgency:
            boost *= 1.5
        elif abs(doc_priority - query_priority) < 0.5:
            boost *= 1.2

        # Additional boost for emergency content when query is urgent
        if query_priority >= 2.0 and doc_priority >= 2.0:
            boost *= 1.5

        return boost

    def _calculate_specialty_match(
        self,
        query: str,
        doc_metadata: Dict[str, Any],
        query_metadata: Optional[Dict[str, Any]],
    ) -> float:
        """Calculate specialty match boost."""
        boost = 1.0

        # Get specialties
        doc_specialty = doc_metadata.get("medical_specialty")
        query_specialty = query_metadata.get("specialty") if query_metadata else None

        # Direct specialty match
        if doc_specialty and query_specialty and doc_specialty == query_specialty:
            boost *= 1.5

        # Check query terms for specialty relevance
        query_lower = query.lower()
        for specialty, terms in self.specialty_relevance.items():
            if any(term in query_lower for term in terms):
                if doc_specialty == specialty:
                    boost *= 1.3
                    break

        return boost


class CrossEncoderReRanker(ReRanker):
    """Cross-encoder based re-ranker.

    Uses a cross-encoder model to re-score query-document pairs.
    """

    def __init__(
        self,
        model_name: str = "cross-encoder/ms-marco-MiniLM-L-12-v2",
        top_k: int = 20,
        use_gpu: bool = True,
    ):
        """Initialize cross-encoder re-ranker.

        Args:
            model_name: Model to use for re-ranking
            top_k: Number of top results to return
            use_gpu: Whether to use GPU if available
        """
        super().__init__(top_k)
        self.model_name = model_name
        self.use_gpu = use_gpu
        self.model = None
        self._init_model()

    def _init_model(self) -> None:
        """Initialize cross-encoder model."""
        # In production, load actual cross-encoder model
        # from sentence_transformers import CrossEncoder
        # self.model = CrossEncoder(self.model_name)
        self.logger.info("Initialized cross-encoder: %s", self.model_name)

    def rerank(
        self,
        query: str,
        results: List[Tuple[str, float, Dict[str, Any]]],
        query_metadata: Optional[Dict[str, Any]] = None,
    ) -> List[RerankResult]:
        """Re-rank using cross-encoder."""
        # Get top K results
        top_results = self._get_top_k_results(results)

        # Currently using fallback re-ranking
        # When model is implemented, will use cross-encoder
        return self._fallback_rerank(query, top_results, query_metadata)

    def _fallback_rerank(
        self,
        query: str,
        results: List[Tuple[str, float, Dict[str, Any]]],
        _query_metadata: Optional[
            Dict[str, Any]
        ] = None,  # pylint: disable=unused-argument # Reserved for metadata-based reranking
    ) -> List[RerankResult]:
        """Fallback re-ranking without model."""
        reranked = []

        for doc_id, original_score, metadata in results:
            # Simple text similarity boost
            doc_text = metadata.get("text", "").lower()
            query_lower = query.lower()

            # Count query term occurrences
            query_terms = query_lower.split()
            term_count = sum(1 for term in query_terms if term in doc_text)
            term_boost = 1 + (term_count * 0.1)

            rerank_score = original_score * term_boost

            reranked.append(
                RerankResult(
                    doc_id=doc_id,
                    original_score=original_score,
                    rerank_score=rerank_score,
                    metadata=metadata,
                )
            )

        reranked.sort(key=lambda x: x.rerank_score, reverse=True)
        return reranked

    def _mock_cross_encoder_scores(self, pairs: List[List[str]]) -> List[float]:
        """Mock cross-encoder scores for testing."""
        scores = []
        for query, doc in pairs:
            # Simple similarity based on shared terms
            query_terms = set(query.lower().split())
            doc_terms = set(doc.lower().split())

            if not query_terms or not doc_terms:
                scores.append(0.5)
            else:
                overlap = len(query_terms.intersection(doc_terms))
                score = overlap / len(query_terms)
                scores.append(score)

        return scores


def create_reranker(
    reranker_type: str = "medical",
    top_k: int = 20,
    model_name: Optional[str] = None,
    use_gpu: bool = True,
) -> ReRanker:
    """Create a re-ranker instance.

    Args:
        reranker_type: Type of re-ranker (medical, cross_encoder)
        **kwargs: Additional arguments for the re-ranker

    Returns:
        Re-ranker instance
    """
    rerankers: Dict[str, Type[ReRanker]] = {
        "medical": MedicalReRanker,
        "cross_encoder": CrossEncoderReRanker,
    }

    if reranker_type not in rerankers:
        raise ValueError(f"Unknown re-ranker type: {reranker_type}")

    reranker_class = rerankers[reranker_type]

    if reranker_type == "medical":
        return reranker_class(top_k=top_k)
    elif reranker_type == "cross_encoder":
        # Cast to CrossEncoderReRanker for proper type checking
        cross_encoder_class = cast(Type[CrossEncoderReRanker], reranker_class)
        if model_name is None:
            return cross_encoder_class(top_k=top_k, use_gpu=use_gpu)
        else:
            return cross_encoder_class(
                model_name=model_name, top_k=top_k, use_gpu=use_gpu
            )

    # This should never be reached due to the earlier validation
    raise ValueError(f"Unknown re-ranker type: {reranker_type}")
