"""Dimension Performance Profiler.

Profiles and analyzes performance characteristics of different
embedding dimensions.
"""

import logging
import time
from typing import Dict, List

import numpy as np

logger = logging.getLogger(__name__)


class DimensionProfiler:
    """Profiles dimension performance characteristics."""

    @staticmethod
    def profile_dimension_performance(
        dimension: int, num_vectors: int = 10000, num_queries: int = 100
    ) -> Dict[str, float]:
        """Profile performance for a specific dimension.

        Args:
            dimension: Embedding dimension to profile
            num_vectors: Number of vectors to test with
            num_queries: Number of queries to simulate

        Returns:
            Performance metrics
        """
        # Generate test data
        vectors = np.random.randn(num_vectors, dimension).astype(np.float32)
        queries = np.random.randn(num_queries, dimension).astype(np.float32)

        # Test similarity computation time
        start_time = time.time()
        for query in queries:
            # Compute cosine similarity
            similarities = np.dot(vectors, query) / (
                np.linalg.norm(vectors, axis=1) * np.linalg.norm(query)
            )
            # Find top-k
            _ = np.argpartition(similarities, -10)[-10:]  # top_k

        similarity_time = time.time() - start_time
        avg_query_time = similarity_time / num_queries * 1000  # ms

        # Calculate storage
        storage_mb = (num_vectors * dimension * 4) / (1024 * 1024)

        # Test memory bandwidth
        start_time = time.time()
        for _ in range(10):
            _ = np.sum(vectors, axis=1)
        memory_time = time.time() - start_time
        bandwidth_gbps = (vectors.nbytes * 10 / memory_time) / (1024**3)

        # Calculate index building time estimate
        index_build_estimate = num_vectors * dimension * 0.0001  # ms

        return {
            "dimension": dimension,
            "avg_query_time_ms": round(avg_query_time, 2),
            "storage_mb": round(storage_mb, 2),
            "memory_bandwidth_gbps": round(bandwidth_gbps, 2),
            "index_build_time_estimate_s": round(index_build_estimate / 1000, 2),
            "queries_per_second": round(1000 / avg_query_time, 2),
        }

    @staticmethod
    def compare_dimensions(
        dimensions: List[int], num_vectors: int = 10000
    ) -> Dict[int, Dict[str, float]]:
        """Compare performance across multiple dimensions."""
        results = {}

        for dim in dimensions:
            logger.info("Profiling dimension %d", dim)
            results[dim] = DimensionProfiler.profile_dimension_performance(
                dim, num_vectors
            )

        return results

    @staticmethod
    def estimate_scaling(
        base_dimension: int, target_vectors: List[int]
    ) -> Dict[int, Dict[str, float]]:
        """Estimate performance scaling with number of vectors."""
        results = {}

        for num_vectors in target_vectors:
            profile = DimensionProfiler.profile_dimension_performance(
                base_dimension, num_vectors, min(100, num_vectors // 100)
            )
            results[num_vectors] = profile

        return results


def profile_dimension_performance(
    dimension: int, num_vectors: int = 10000
) -> Dict[str, float]:
    """Profile dimension performance."""
    return DimensionProfiler.profile_dimension_performance(dimension, num_vectors)


def estimate_storage_requirements(
    dimension: int, num_documents: int, include_overhead: bool = True
) -> Dict[str, float]:
    """Estimate storage requirements for embeddings.

    Args:
        dimension: Embedding dimension
        num_documents: Number of documents
        include_overhead: Include index overhead

    Returns:
        Storage estimates
    """
    # Base storage (float32)
    base_storage_bytes = dimension * num_documents * 4

    # Convert to different units
    storage_mb = base_storage_bytes / (1024 * 1024)
    storage_gb = base_storage_bytes / (1024 * 1024 * 1024)

    # Add overhead if requested (typically 10-20% for indices)
    if include_overhead:
        overhead_factor = 1.15
        storage_mb *= overhead_factor
        storage_gb *= overhead_factor

    # Calculate per-document storage
    bytes_per_doc = dimension * 4 * (overhead_factor if include_overhead else 1)

    return {
        "total_storage_mb": round(storage_mb, 2),
        "total_storage_gb": round(storage_gb, 3),
        "bytes_per_document": round(bytes_per_doc, 0),
        "dimension": dimension,
        "num_documents": num_documents,
        "includes_overhead": include_overhead,
    }
