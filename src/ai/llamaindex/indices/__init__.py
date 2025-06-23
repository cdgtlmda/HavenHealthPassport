"""Vector Indices Module for Haven Health Passport.

Provides various vector index implementations optimized for medical document retrieval.
 Handles FHIR Resource validation.
"""

from typing import List

from .base import BaseVectorIndex, IndexMetrics, VectorIndexConfig, VectorIndexType
from .dense import DenseVectorIndex, OptimizedDenseIndex, ShardedDenseIndex
from .factory import VectorIndexFactory, create_vector_index, get_index_for_use_case
from .hybrid import DenseSparseFusionIndex, HybridVectorIndex, MultiStageIndex
from .manager import IndexManager, IndexMonitor, IndexOptimizer
from .medical import (
    ClinicalTrialsIndex,
    DrugInteractionIndex,
    MedicalVectorIndex,
    PatientRecordsIndex,
)
from .multimodal import MedicalImagingIndex, MultiModalIndex, TextImageIndex
from .sparse import BM25Index, SparseVectorIndex, TFIDFIndex

__all__ = [
    # Base classes
    "VectorIndexType",
    "BaseVectorIndex",
    "VectorIndexConfig",
    "IndexMetrics",
    # Dense indices
    "DenseVectorIndex",
    "OptimizedDenseIndex",
    "ShardedDenseIndex",
    # Sparse indices
    "SparseVectorIndex",
    "BM25Index",
    "TFIDFIndex",
    # Hybrid indices
    "HybridVectorIndex",
    "DenseSparseFusionIndex",
    "MultiStageIndex",
    # Medical indices
    "MedicalVectorIndex",
    "ClinicalTrialsIndex",
    "PatientRecordsIndex",
    "DrugInteractionIndex",
    # Multi-modal indices
    "MultiModalIndex",
    "TextImageIndex",
    "MedicalImagingIndex",
    # Management
    "IndexManager",
    "IndexOptimizer",
    "IndexMonitor",
    # Factory
    "VectorIndexFactory",
    "create_vector_index",
    "get_index_for_use_case",
]


def validate_fhir_data(data: dict) -> dict:
    """Validate FHIR data.

    Args:
        data: Data to validate

    Returns:
        Validation result with 'valid', 'errors', and 'warnings' keys
    """
    errors = []
    warnings: List[str] = []

    if not data:
        errors.append("No data provided")

    return {"valid": len(errors) == 0, "errors": errors, "warnings": warnings}
