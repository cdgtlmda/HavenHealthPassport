"""Base Classes for Similarity Metrics.

Provides the foundation for all similarity scoring in the Haven Health Passport system.
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Union

import numpy as np

logger = logging.getLogger(__name__)


class SimilarityMetric(str, Enum):
    """Available similarity metrics."""

    COSINE = "cosine"
    EUCLIDEAN = "euclidean"
    DOT_PRODUCT = "dot_product"
    MANHATTAN = "manhattan"
    JACCARD = "jaccard"
    MEDICAL = "medical"
    HYBRID = "hybrid"


@dataclass
class SimilarityConfig:
    """Configuration for similarity scoring."""

    # Basic settings
    metric: SimilarityMetric = SimilarityMetric.COSINE
    normalize_scores: bool = True
    score_threshold: float = 0.0

    # Advanced settings
    use_idf_weighting: bool = False
    use_bm25_scoring: bool = False
    consider_metadata: bool = True

    # Medical-specific settings
    boost_medical_terms: bool = True
    medical_term_weight: float = 1.5
    consider_semantic_types: bool = True
    use_cui_matching: bool = True

    # Performance settings
    batch_size: int = 100
    use_approximate_search: bool = False
    approximate_search_params: Dict[str, Any] = field(default_factory=dict)

    # Re-ranking settings
    enable_reranking: bool = False
    rerank_top_k: int = 20
    reranker_model: Optional[str] = None


class BaseSimilarityScorer(ABC):
    """Base class for similarity scoring.

    Provides common functionality for all similarity scorers
    including normalization, thresholding, and metadata handling.
    """

    def __init__(self, config: Optional[SimilarityConfig] = None):
        """Initialize similarity scorer."""
        self.config = config or SimilarityConfig()
        self._setup_logging()
        self._initialize()

    def _setup_logging(self) -> None:
        """Set up scorer-specific logging."""
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    @abstractmethod
    def _initialize(self) -> None:
        """Initialize scorer-specific components."""

    @abstractmethod
    def score(
        self,
        query_embedding: Union[List[float], np.ndarray],
        doc_embedding: Union[List[float], np.ndarray],
        query_metadata: Optional[Dict[str, Any]] = None,
        doc_metadata: Optional[Dict[str, Any]] = None,
    ) -> float:
        """Calculate similarity score between query and document.

        Args:
            query_embedding: Query vector
            doc_embedding: Document vector
            query_metadata: Optional query metadata
            doc_metadata: Optional document metadata

        Returns:
            Similarity score
        """

    def batch_score(
        self,
        query_embedding: Union[List[float], np.ndarray],
        doc_embeddings: List[Union[List[float], np.ndarray]],
        query_metadata: Optional[Dict[str, Any]] = None,
        doc_metadatas: Optional[List[Dict[str, Any]]] = None,
    ) -> List[float]:
        """Calculate similarity scores for multiple documents.

        Args:
            query_embedding: Query vector
            doc_embeddings: List of document vectors
            query_metadata: Optional query metadata
            doc_metadatas: Optional list of document metadata

        Returns:
            List of similarity scores
        """
        if doc_metadatas is None:
            doc_metadatas = [{}] * len(doc_embeddings)

        scores = []
        for doc_emb, doc_meta in zip(doc_embeddings, doc_metadatas):
            score = self.score(query_embedding, doc_emb, query_metadata, doc_meta)
            scores.append(score)

        return scores

    def _normalize_score(self, score: float) -> float:
        """Normalize score to [0, 1] range."""
        if not self.config.normalize_scores:
            return score

        # Default normalization - subclasses can override
        return max(0.0, min(1.0, score))

    def _apply_threshold(self, score: float) -> float:
        """Apply minimum score threshold."""
        if score < self.config.score_threshold:
            return 0.0
        return score

    def _convert_to_numpy(
        self, embedding: Union[List[float], np.ndarray]
    ) -> np.ndarray:
        """Convert embedding to numpy array."""
        if isinstance(embedding, list):
            return np.array(embedding)
        return embedding

    def _apply_metadata_boost(
        self,
        base_score: float,
        query_metadata: Optional[Dict[str, Any]],
        doc_metadata: Optional[Dict[str, Any]],
    ) -> float:
        """Apply metadata-based score boosting."""
        if not self.config.consider_metadata:
            return base_score

        if query_metadata is None or doc_metadata is None:
            return base_score

        boost_factor = 1.0

        # Medical term matching
        if self.config.boost_medical_terms:
            query_terms = set(query_metadata.get("medical_terms", []))
            doc_terms = set(doc_metadata.get("medical_terms", []))

            if query_terms and doc_terms:
                overlap = len(query_terms.intersection(doc_terms))
                if overlap > 0:
                    boost_factor *= 1 + (
                        overlap * 0.1 * self.config.medical_term_weight
                    )

        # Language matching
        query_lang = query_metadata.get("language")
        doc_lang = doc_metadata.get("language")
        if query_lang and doc_lang and query_lang == doc_lang:
            boost_factor *= 1.1

        # Recency boost
        doc_date = doc_metadata.get("date")
        if doc_date:
            # Implement recency scoring
            pass

        return base_score * boost_factor

    def get_stats(self) -> Dict[str, Any]:
        """Get scorer statistics."""
        return {
            "metric": self.config.metric.value,
            "normalize_scores": self.config.normalize_scores,
            "threshold": self.config.score_threshold,
            "consider_metadata": self.config.consider_metadata,
        }
