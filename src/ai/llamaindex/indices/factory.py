"""
Vector Index Factory.

Provides factory methods for creating various types of vector indices.
Handles FHIR Resource validation.

Security Note: This module processes PHI data. All index data must be:
- Subject to role-based access control (RBAC) for PHI protection
"""

import logging
from typing import Any, Dict, List, Optional, Type

from ..embeddings import get_embedding_model
from ..similarity import get_similarity_scorer
from .base import BaseVectorIndex, VectorIndexConfig
from .dense import DenseVectorIndex, OptimizedDenseIndex, ShardedDenseIndex
from .hybrid import DenseSparseFusionIndex, HybridVectorIndex, MultiStageIndex
from .manager import IndexManager
from .medical import (
    ClinicalTrialsIndex,
    DrugInteractionIndex,
    MedicalIndexConfig,
    MedicalVectorIndex,
    PatientRecordsIndex,
)
from .multimodal import MedicalImagingIndex, MultiModalIndex, TextImageIndex
from .sparse import BM25Index, SparseVectorIndex, TFIDFIndex

logger = logging.getLogger(__name__)


class VectorIndexFactory:
    """Factory for creating vector indices."""

    # Index type to class mapping
    INDEX_CLASSES: Dict[str, Type[BaseVectorIndex]] = {
        # Dense indices
        "dense": DenseVectorIndex,
        "dense_optimized": OptimizedDenseIndex,
        "dense_sharded": ShardedDenseIndex,
        # Sparse indices
        "sparse": SparseVectorIndex,
        "bm25": BM25Index,
        "tfidf": TFIDFIndex,
        # Hybrid indices
        "hybrid": HybridVectorIndex,
        "dense_sparse_fusion": DenseSparseFusionIndex,
        "multistage": MultiStageIndex,
        # Medical indices
        "medical": MedicalVectorIndex,
        "clinical_trials": ClinicalTrialsIndex,
        "patient_records": PatientRecordsIndex,
        "drug_interactions": DrugInteractionIndex,
        # Multimodal indices
        "multimodal": MultiModalIndex,
        "text_image": TextImageIndex,
        "medical_imaging": MedicalImagingIndex,
    }

    @staticmethod
    def create_index(
        index_type: str, config: Optional[VectorIndexConfig] = None, **kwargs: Any
    ) -> BaseVectorIndex:
        """
        Create a vector index.

        Args:
            index_type: Type of index to create
            config: Optional configuration
            **kwargs: Additional index-specific arguments

        Returns:
            Created vector index
        """
        if index_type not in VectorIndexFactory.INDEX_CLASSES:
            raise ValueError(
                f"Unknown index type: {index_type}. "
                f"Available types: {list(VectorIndexFactory.INDEX_CLASSES.keys())}"
            )

        index_class = VectorIndexFactory.INDEX_CLASSES[index_type]

        # Create appropriate config if not provided
        if config is None:
            if index_type in [
                "medical",
                "clinical_trials",
                "patient_records",
                "drug_interactions",
            ]:
                config = MedicalIndexConfig()
            else:
                config = VectorIndexConfig()

        # Set up embedding model if not provided
        if "embedding_model" not in kwargs:
            if index_type.startswith("medical") or index_type in [
                "clinical_trials",
                "patient_records",
                "drug_interactions",
            ]:
                kwargs["embedding_model"] = get_embedding_model("medical")
            elif index_type in ["multimodal", "text_image", "medical_imaging"]:
                kwargs["embedding_model"] = get_embedding_model("multimodal")
            else:
                kwargs["embedding_model"] = get_embedding_model("general")

        # Set up similarity scorer if not provided
        if "similarity_scorer" not in kwargs:
            if index_type.startswith("medical") or index_type in [
                "clinical_trials",
                "patient_records",
                "drug_interactions",
            ]:
                kwargs["similarity_scorer"] = get_similarity_scorer("medical")
            else:
                kwargs["similarity_scorer"] = get_similarity_scorer("general")

        # Create index
        logger.info("Creating %s index", index_type)
        return index_class(config=config, **kwargs)

    @staticmethod
    def create_medical_index(
        specialty: Optional[str] = None,
        config: Optional[MedicalIndexConfig] = None,
        **kwargs: Any,
    ) -> MedicalVectorIndex:
        """
        Create a medical index for specific specialty.

        Args:
            specialty: Medical specialty (cardiology, oncology, etc.)
            config: Optional configuration
            **kwargs: Additional arguments

        Returns:
            Medical vector index
        """
        if config is None:
            config = MedicalIndexConfig()

        # Configure for specialty if provided
        if specialty:
            config.clinical_specialties = [specialty]
            config.index_name = f"medical_{specialty}_index"

        # Map specialty to specific index type
        specialty_indices = {
            "clinical_trials": ClinicalTrialsIndex,
            "patient_records": PatientRecordsIndex,
            "pharmacy": DrugInteractionIndex,
        }

        if specialty in specialty_indices:
            index_class = specialty_indices[specialty]
            return index_class(config=config, **kwargs)

        # Default medical index
        return MedicalVectorIndex(config=config, **kwargs)

    @staticmethod
    def create_hybrid_index(
        dense_weight: float = 0.7,
        sparse_weight: float = 0.3,
        fusion_method: Optional[str] = None,
        config: Optional[VectorIndexConfig] = None,
        **kwargs: Any,
    ) -> BaseVectorIndex:
        """
        Create a hybrid index with custom weights.

        Args:
            dense_weight: Weight for dense component
            sparse_weight: Weight for sparse component
            fusion_method: Fusion method (rrf, linear)
            config: Optional configuration
            **kwargs: Additional arguments

        Returns:
            Hybrid vector index
        """
        if fusion_method == "rrf":
            return DenseSparseFusionIndex(config=config, fusion_method="rrf", **kwargs)
        elif fusion_method == "multistage":
            return MultiStageIndex(config=config, **kwargs)
        else:
            return HybridVectorIndex(
                config=config,
                dense_weight=dense_weight,
                sparse_weight=sparse_weight,
                **kwargs,
            )


def create_vector_index(index_type: str = "dense", **kwargs: Any) -> BaseVectorIndex:
    """
    Create a vector index.

    Args:
        index_type: Type of index
        **kwargs: Index configuration

    Returns:
        Vector index instance
    """
    return VectorIndexFactory.create_index(index_type, **kwargs)


def get_index_for_use_case(use_case: str, **kwargs: Any) -> BaseVectorIndex:
    """
    Get appropriate index for specific use case.

    Args:
        use_case: Use case identifier
        **kwargs: Additional configuration

    Returns:
        Configured vector index
    """
    use_case_mappings = {
        # General use cases
        "general": {
            "index_type": "dense",
            "config": VectorIndexConfig(enable_caching=True, similarity_threshold=0.7),
        },
        "large_scale": {
            "index_type": "dense_sharded",
            "num_shards": 4,
            "config": VectorIndexConfig(
                enable_approximate_search=True, enable_compression=True
            ),
        },
        "keyword_search": {
            "index_type": "bm25",
            "config": VectorIndexConfig(enable_caching=True),
        },
        "semantic_search": {
            "index_type": "dense_optimized",
            "config": VectorIndexConfig(
                enable_approximate_search=True, similarity_threshold=0.8
            ),
        },
        "hybrid_search": {
            "index_type": "hybrid",
            "dense_weight": 0.7,
            "sparse_weight": 0.3,
        },
        # Medical use cases
        "medical_records": {
            "index_type": "patient_records",
            "config": MedicalIndexConfig(
                enable_phi_detection=True,
                phi_handling="encrypt",
                enable_medical_ner=True,
            ),
        },
        "clinical_research": {
            "index_type": "clinical_trials",
            "config": MedicalIndexConfig(
                enable_ontology_expansion=True, enable_medical_ner=True
            ),
        },
        "drug_safety": {
            "index_type": "drug_interactions",
            "config": MedicalIndexConfig(
                enable_drug_interaction_check=True, enable_medical_ner=True
            ),
        },
        "medical_general": {
            "index_type": "medical",
            "config": MedicalIndexConfig(
                enable_medical_ner=True, enable_multilingual=True
            ),
        },
        # Multimodal use cases
        "medical_imaging": {
            "index_type": "medical_imaging",
            "config": VectorIndexConfig(
                enable_caching=True, enable_medical_expansion=True
            ),
        },
        "document_imaging": {
            "index_type": "text_image",
            "config": VectorIndexConfig(enable_caching=True),
        },
        # Performance-optimized
        "real_time": {
            "index_type": "dense",
            "config": VectorIndexConfig(
                enable_caching=True, cache_size=5000, enable_approximate_search=False
            ),
        },
        "batch_processing": {
            "index_type": "dense_optimized",
            "config": VectorIndexConfig(batch_size=1000, enable_compression=True),
        },
    }

    if use_case not in use_case_mappings:
        raise ValueError(
            f"Unknown use case: {use_case}. "
            f"Available use cases: {list(use_case_mappings.keys())}"
        )

    # Get use case configuration
    use_case_config = use_case_mappings[use_case]

    # Merge with provided kwargs
    merged_config = {**use_case_config, **kwargs}

    # Extract index type
    index_type = merged_config.pop("index_type")

    # Create index
    return create_vector_index(index_type, **merged_config)


def create_index_pipeline(
    indices: List[Dict[str, Any]], routing_strategy: str = "round_robin"
) -> Dict[str, Any]:
    """
    Create a pipeline of multiple indices.

    Args:
        indices: List of index configurations
        routing_strategy: How to route queries

    Returns:
        Index pipeline configuration
    """
    # Create index manager
    manager = IndexManager()

    # Create indices
    created_indices = []
    for i, index_config in enumerate(indices):
        index_type = index_config.get("type", "dense")
        name = index_config.get("name", f"index_{i}")

        # Create index
        index = create_vector_index(index_type, **index_config)

        # Register with manager
        manager.register_index(name, index)

        created_indices.append({"name": name, "type": index_type, "index": index})

    return {
        "manager": manager,
        "indices": created_indices,
        "routing_strategy": routing_strategy,
        "stats": manager.get_statistics(),
    }


# Pre-configured index templates
INDEX_TEMPLATES: Dict[str, Any] = {
    "medical_system": {
        "indices": [
            {
                "name": "patient_records",
                "type": "patient_records",
                "config": MedicalIndexConfig(
                    enable_phi_detection=True, phi_handling="encrypt"
                ),
            },
            {
                "name": "medical_knowledge",
                "type": "medical",
                "config": MedicalIndexConfig(
                    enable_medical_ner=True, enable_ontology_expansion=True
                ),
            },
            {
                "name": "drug_database",
                "type": "drug_interactions",
                "config": MedicalIndexConfig(enable_drug_interaction_check=True),
            },
        ],
        "routing_strategy": "content_based",
    },
    "research_platform": {
        "indices": [
            {
                "name": "papers",
                "type": "hybrid",
                "dense_weight": 0.6,
                "sparse_weight": 0.4,
            },
            {"name": "clinical_trials", "type": "clinical_trials"},
            {"name": "datasets", "type": "multimodal"},
        ],
        "routing_strategy": "type_based",
    },
    "enterprise_search": {
        "indices": [
            {"name": "documents", "type": "hybrid"},
            {"name": "knowledge_base", "type": "dense_optimized"},
            {"name": "archives", "type": "dense_sharded", "num_shards": 8},
        ],
        "routing_strategy": "load_balanced",
    },
}


def create_from_template(template_name: str, **kwargs: Any) -> Dict[str, Any]:
    """
    Create index system from template.

    Args:
        template_name: Name of template
        **kwargs: Override parameters

    Returns:
        Index system configuration
    """
    if template_name not in INDEX_TEMPLATES:
        raise ValueError(
            f"Unknown template: {template_name}. "
            f"Available templates: {list(INDEX_TEMPLATES.keys())}"
        )

    template = INDEX_TEMPLATES[template_name]

    # Merge with overrides
    indices = template["indices"]
    routing_strategy = kwargs.get("routing_strategy", template["routing_strategy"])

    return create_index_pipeline(indices, routing_strategy)


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
