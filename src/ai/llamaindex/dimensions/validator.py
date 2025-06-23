"""Dimension Validation and Compatibility Checking.

Ensures embedding dimensions are compatible with vector stores,
models, and downstream applications.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class DimensionValidator:
    """Validates dimension compatibility."""

    # Known vector store dimension constraints
    VECTOR_STORE_CONSTRAINTS = {
        "opensearch": {
            "min_dimension": 1,
            "max_dimension": 16000,
            "optimal_range": (100, 2048),
            "notes": "OpenSearch handles up to 16k dimensions but performs best under 2048",
        },
        "faiss": {
            "min_dimension": 1,
            "max_dimension": 8192,
            "optimal_range": (64, 1024),
            "notes": "FAISS is optimized for dimensions up to 1024",
        },
        "pinecone": {
            "min_dimension": 1,
            "max_dimension": 20000,
            "optimal_range": (64, 1536),
            "notes": "Pinecone supports high dimensions but costs increase",
        },
        "weaviate": {
            "min_dimension": 1,
            "max_dimension": 65535,
            "optimal_range": (100, 1536),
            "notes": "Weaviate has flexible dimension support",
        },
        "qdrant": {
            "min_dimension": 1,
            "max_dimension": 65536,
            "optimal_range": (100, 1536),
            "notes": "Qdrant optimized for moderate dimensions",
        },
        "chroma": {
            "min_dimension": 1,
            "max_dimension": 10000,
            "optimal_range": (64, 1536),
            "notes": "ChromaDB works well with standard embedding dimensions",
        },
    }

    # Model dimension constraints
    MODEL_DIMENSIONS = {
        # Bedrock Titan
        "amazon.titan-embed-text-v1": 1536,
        "amazon.titan-embed-text-v2:0": 1024,
        "amazon.titan-embed-g1-text-02": 384,
        "amazon.titan-embed-image-v1": 1024,
        # OpenAI
        "text-embedding-ada-002": 1536,
        "text-embedding-3-small": 1536,
        "text-embedding-3-large": 3072,
        # Medical models
        "haven-medical-embed": 768,
        "Bio_ClinicalBERT": 768,
        # Custom reduced
        "custom-512": 512,
        "custom-256": 256,
    }

    @classmethod
    def validate_dimension(
        cls,
        dimension: int,
        vector_store: Optional[str] = None,
        model_name: Optional[str] = None,
    ) -> Tuple[bool, List[str]]:
        """Validate if dimension is compatible.

        Args:
            dimension: Embedding dimension
            vector_store: Target vector store name
            model_name: Embedding model name

        Returns:
            (is_valid, list_of_issues)
        """
        issues = []

        # Check if dimension is positive
        if dimension <= 0:
            issues.append(f"Dimension must be positive, got {dimension}")
        # Check vector store compatibility
        if vector_store:
            if vector_store.lower() in cls.VECTOR_STORE_CONSTRAINTS:
                constraints: Dict[str, Any] = cls.VECTOR_STORE_CONSTRAINTS[
                    vector_store.lower()
                ]

                if dimension < constraints["min_dimension"]:
                    issues.append(
                        f"{vector_store} requires minimum {constraints['min_dimension']} dimensions"
                    )

                if dimension > constraints["max_dimension"]:
                    issues.append(
                        f"{vector_store} supports maximum {constraints['max_dimension']} dimensions"
                    )

                optimal_min, optimal_max = constraints["optimal_range"]
                if not optimal_min <= dimension <= optimal_max:
                    issues.append(
                        f"{vector_store} performs best with {optimal_min}-{optimal_max} dimensions. "
                        f"Current: {dimension}"
                    )
            else:
                logger.warning("Unknown vector store: %s", vector_store)

        # Check model compatibility
        if model_name:
            if model_name in cls.MODEL_DIMENSIONS:
                expected_dim = cls.MODEL_DIMENSIONS[model_name]
                if dimension != expected_dim:
                    issues.append(
                        f"Model {model_name} produces {expected_dim} dimensions, "
                        f"but {dimension} requested"
                    )
            else:
                logger.warning("Unknown model: %s", model_name)

        return len(issues) == 0, issues

    @classmethod
    def check_dimension_compatibility(
        cls, source_dimension: int, target_dimension: int, allow_reduction: bool = True
    ) -> Tuple[bool, Optional[str]]:
        """Check if dimensions are compatible for operations.

        Args:
            source_dimension: Source embedding dimension
            target_dimension: Target dimension
            allow_reduction: Whether dimension reduction is allowed

        Returns:
            (is_compatible, compatibility_message)
        """
        if source_dimension == target_dimension:
            return True, "Dimensions match perfectly"

        if source_dimension < target_dimension:
            return (
                False,
                f"Cannot expand from {source_dimension} to {target_dimension} dimensions",
            )

        if source_dimension > target_dimension:
            if allow_reduction:
                reduction_factor = source_dimension / target_dimension
                if reduction_factor == int(reduction_factor):
                    return True, f"Can reduce by factor of {int(reduction_factor)}"
                else:
                    return True, "Can reduce using PCA or similar methods"
            else:
                return (
                    False,
                    f"Dimension reduction not allowed: {source_dimension} to {target_dimension}",
                )

        return False, "Unknown compatibility issue"

    @classmethod
    def get_compatible_vector_stores(
        cls, dimension: int, optimal_only: bool = False
    ) -> List[str]:
        """Get list of compatible vector stores for dimension."""
        compatible = []

        for store, constraints_dict in cls.VECTOR_STORE_CONSTRAINTS.items():
            constraints: Dict[str, Any] = constraints_dict
            if (
                constraints["min_dimension"]
                <= dimension
                <= constraints["max_dimension"]
            ):
                if optimal_only:
                    optimal_min, optimal_max = constraints["optimal_range"]
                    if optimal_min <= dimension <= optimal_max:
                        compatible.append(store)
                else:
                    compatible.append(store)

        return compatible

    @classmethod
    def suggest_compatible_dimensions(
        cls, vector_store: str, available_models: List[str]
    ) -> List[int]:
        """Suggest dimensions compatible with both vector store and models."""
        if vector_store.lower() not in cls.VECTOR_STORE_CONSTRAINTS:
            return []

        constraints: Dict[str, Any] = cls.VECTOR_STORE_CONSTRAINTS[vector_store.lower()]
        optimal_min, optimal_max = constraints["optimal_range"]

        compatible_dims = []
        for model in available_models:
            if model in cls.MODEL_DIMENSIONS:
                dim = cls.MODEL_DIMENSIONS[model]
                if optimal_min <= dim <= optimal_max:
                    compatible_dims.append(dim)

        return sorted(list(set(compatible_dims)))


def validate_dimension_compatibility(
    dimension: int, vector_store: str, model_name: Optional[str] = None
) -> bool:
    """Quick validation function.

    Returns:
        True if dimension is compatible
    """
    is_valid, issues = DimensionValidator.validate_dimension(
        dimension, vector_store, model_name
    )

    if not is_valid:
        logger.warning("Dimension validation failed: %s", "; ".join(issues))

    return is_valid


def check_vector_store_compatibility(
    dimension: int, vector_stores: List[str]
) -> Dict[str, bool]:
    """Check compatibility with multiple vector stores.

    Returns:
        Dict mapping vector store to compatibility status
    """
    results = {}

    for store in vector_stores:
        is_valid, _ = DimensionValidator.validate_dimension(
            dimension, vector_store=store
        )
        results[store] = is_valid

    return results
