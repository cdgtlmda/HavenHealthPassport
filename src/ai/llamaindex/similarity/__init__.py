"""Similarity Metrics Module for Haven Health Passport.

Provides various similarity metrics and scoring functions optimized
for medical document retrieval and healthcare content matching.
"""

from .base import BaseSimilarityScorer, SimilarityConfig, SimilarityMetric
from .factory import SimilarityFactory, get_similarity_scorer
from .hybrid import (
    EnsembleSimilarityScorer,
    HybridSimilarityScorer,
    WeightedSimilarityScorer,
)
from .medical import (
    ClinicalRelevanceScorer,
    MedicalSimilarityScorer,
    SemanticMedicalSimilarity,
)
from .metrics import (
    CosineSimilarity,
    DotProductSimilarity,
    EuclideanDistance,
    JaccardSimilarity,
    ManhattanDistance,
)
from .reranking import CrossEncoderReRanker, MedicalReRanker, ReRanker

__all__ = [
    # Base classes
    "SimilarityMetric",
    "BaseSimilarityScorer",
    "SimilarityConfig",
    # Metrics
    "CosineSimilarity",
    "EuclideanDistance",
    "DotProductSimilarity",
    "ManhattanDistance",
    "JaccardSimilarity",
    # Medical scorers
    "MedicalSimilarityScorer",
    "ClinicalRelevanceScorer",
    "SemanticMedicalSimilarity",
    # Hybrid scorers
    "HybridSimilarityScorer",
    "WeightedSimilarityScorer",
    "EnsembleSimilarityScorer",
    # Re-ranking
    "ReRanker",
    "MedicalReRanker",
    "CrossEncoderReRanker",
    # Factory
    "SimilarityFactory",
    "get_similarity_scorer",
]
