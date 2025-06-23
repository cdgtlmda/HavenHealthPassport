"""Example Integration of Embeddings with Dimension Selection.

Shows how to use embeddings with intelligent dimension selection
for optimal performance and compatibility.
 Handles FHIR Resource validation.
"""

import asyncio
from typing import Any, Tuple

try:
    from haven_health_passport.ai.llamaindex.dimensions import (
        DimensionSelector,
        PerformanceRequirement,
        SelectionCriteria,
        StorageConstraint,
        UseCase,
        optimize_dimensions,
        reduce_embedding_dimension,
        validate_dimension_compatibility,
    )
except ImportError:
    # Handle import error for external usage
    DimensionSelector = None
    PerformanceRequirement = None
    SelectionCriteria = None
    UseCase = None
    validate_dimension_compatibility = None
    reduce_embedding_dimension = None
    StorageConstraint = None
    optimize_dimensions = None

try:
    from haven_health_passport.ai.llamaindex.embeddings import get_embedding_model
except ImportError:
    get_embedding_model = None


async def setup_embeddings_with_optimal_dimensions() -> Tuple[Any, Any]:
    """Set up embeddings with optimal dimensions."""
    # 1. Define your requirements
    criteria = SelectionCriteria(
        use_case=UseCase.SEMANTIC_SEARCH,
        performance_requirement=PerformanceRequirement.STANDARD,
        expected_documents=100000,
        languages=["en", "es", "fr"],
        medical_accuracy_required=True,
    )

    # 2. Get dimension recommendation
    recommendation = DimensionSelector.select_dimensions(criteria)

    print("Recommended configuration:")
    print(f"  Dimension: {recommendation.primary_config.dimension}")
    print(f"  Model: {recommendation.primary_config.model_name}")
    print(f"  Provider: {recommendation.primary_config.provider}")
    print(f"  Reasoning: {recommendation.reasoning}")
    print(f"  Estimated storage: {recommendation.estimated_storage_gb}GB")

    # 3. Validate with your vector store
    vector_store = "opensearch"
    is_valid = validate_dimension_compatibility(
        recommendation.primary_config.dimension,
        vector_store,
        recommendation.primary_config.model_name,
    )

    if not is_valid:
        print(f"Warning: Dimension not optimal for {vector_store}")
        # Use alternative
        recommendation.primary_config = recommendation.alternative_configs[0]

    # 4. Create embedding model
    embeddings = get_embedding_model(
        use_case=(
            "medical"
            if recommendation.primary_config.provider == "medical"
            else "general"
        )
    )

    # 5. Test embeddings
    test_texts = [
        "Patient has type 2 diabetes mellitus",
        "El paciente tiene diabetes mellitus tipo 2",
        "Le patient a un diabète sucré de type 2",
    ]

    embeddings_list = await embeddings._aget_text_embeddings(
        test_texts
    )  # pylint: disable=protected-access

    print(f"\nGenerated {len(embeddings_list)} embeddings")
    print(f"Dimension per embedding: {len(embeddings_list[0])}")

    return embeddings, recommendation


async def emergency_medical_setup() -> Any:
    """Handle emergency medical scenario with ultra-low latency."""
    # 1. Emergency criteria
    criteria = SelectionCriteria(
        use_case=UseCase.EMERGENCY_MEDICAL,
        performance_requirement=PerformanceRequirement.ULTRA_LOW_LATENCY,
        medical_accuracy_required=True,
    )

    # 2. Get fast, reliable configuration
    recommendation = DimensionSelector.select_dimensions(criteria)

    print("Emergency configuration:")
    print(f"  Dimension: {recommendation.primary_config.dimension}")
    print(
        f"  Latency: {recommendation.primary_config.estimated_performance['latency_ms']}ms"
    )

    # 3. Create optimized embeddings
    embeddings = get_embedding_model("medical")

    # 4. If dimensions don't match, use reduction
    if embeddings.config.dimension != recommendation.primary_config.dimension:
        # Example reduction
        original_embedding = (
            await embeddings._aget_query_embedding(  # pylint: disable=protected-access
                "Emergency medical text"
            )
        )
        reduced = reduce_embedding_dimension(
            original_embedding,
            recommendation.primary_config.dimension,
            method="truncation",  # Fast for emergency
        )

        print(f"Reduced from {len(original_embedding)} to {len(reduced)} dimensions")

    return embeddings


async def research_analysis_setup() -> Any:
    """Set up research use case prioritizing quality."""
    # 1. Start with high quality
    criteria = SelectionCriteria(
        use_case=UseCase.RESEARCH_ANALYSIS,
        storage_constraint=StorageConstraint.QUALITY_FIRST,
        expected_documents=50000,
    )

    recommendation = DimensionSelector.select_dimensions(criteria)

    # 2. Check if we need to optimize
    if recommendation.estimated_storage_gb > 10:  # Storage limit
        # Optimize for storage while maintaining quality
        optimized_dim, metrics = optimize_dimensions(
            recommendation.primary_config.dimension,
            strategy="balanced",
            min_quality_score=0.9,
            max_storage_gb=10,
        )

        print(
            f"Optimized from {recommendation.primary_config.dimension} to {optimized_dim}"
        )
        print(f"Metrics: {metrics}")

    # 3. Create high-quality embeddings
    embeddings = get_embedding_model("medical", multilingual=True)

    return embeddings


if __name__ == "__main__":
    # Run examples
    asyncio.run(setup_embeddings_with_optimal_dimensions())
    print("\n" + "=" * 50 + "\n")
    asyncio.run(emergency_medical_setup())
    print("\n" + "=" * 50 + "\n")
    asyncio.run(research_analysis_setup())
