# LlamaIndex Dimension Selection Module

## Overview

This module provides intelligent dimension selection for embeddings in the Haven Health Passport system. It helps choose optimal embedding dimensions based on use case, performance requirements, storage constraints, and compatibility with vector stores.

## Features

- **Intelligent Selection**: Automatically selects optimal dimensions based on criteria
- **Performance Profiling**: Profiles query latency and throughput for different dimensions
- **Storage Optimization**: Calculates and optimizes storage requirements
- **Compatibility Checking**: Validates dimensions against vector stores and models
- **Dimension Reduction**: Multiple methods to reduce embedding dimensions
- **Medical Optimization**: Special handling for medical use cases

## Quick Start

### Basic Dimension Selection

```python
from haven_health_passport.ai.llamaindex.dimensions import (
    DimensionSelector,
    SelectionCriteria,
    UseCase
)

# Define your criteria
criteria = SelectionCriteria(
    use_case=UseCase.SEMANTIC_SEARCH,
    expected_documents=100000,
    languages=["en", "es"],
    medical_accuracy_required=True
)

# Get recommendation
recommendation = DimensionSelector.select_dimensions(criteria)

print(f"Recommended: {recommendation.primary_config.dimension}d")
print(f"Model: {recommendation.primary_config.model_name}")
print(f"Reasoning: {recommendation.reasoning}")
```

### Emergency Medical Selection

```python
# For emergency medical situations
emergency_criteria = SelectionCriteria(
    use_case=UseCase.EMERGENCY_MEDICAL,
    performance_requirement=PerformanceRequirement.ULTRA_LOW_LATENCY,    medical_accuracy_required=True
)

recommendation = DimensionSelector.select_dimensions(emergency_criteria)
# Recommends fast, reliable dimensions (typically 384-768)
```

## Use Cases

### 1. Semantic Search
```python
criteria = SelectionCriteria(
    use_case=UseCase.SEMANTIC_SEARCH,
    expected_documents=50000
)
# Typically recommends: 768-1024 dimensions
```

### 2. Document Clustering
```python
criteria = SelectionCriteria(
    use_case=UseCase.DOCUMENT_CLUSTERING,
    storage_constraint=StorageConstraint.BALANCED
)
# Typically recommends: 512-768 dimensions
```

### 3. Research Analysis
```python
criteria = SelectionCriteria(
    use_case=UseCase.RESEARCH_ANALYSIS,
    storage_constraint=StorageConstraint.QUALITY_FIRST
)
# Typically recommends: 1536-3072 dimensions
```

## Dimension Optimization

### Optimize for Different Goals

```python
from haven_health_passport.ai.llamaindex.dimensions import optimize_dimensions

# Optimize for quality
optimized_dim, metrics = optimize_dimensions(
    current_dimension=768,
    strategy="quality_maximization",
    max_storage_per_vector=8192
)

# Optimize for storage
optimized_dim, metrics = optimize_dimensions(
    current_dimension=1536,
    strategy="storage_minimization",
    min_quality_score=0.85
)
# Optimize for latency
optimized_dim, metrics = optimize_dimensions(
    current_dimension=1024,
    strategy="latency_minimization",
    min_quality_score=0.8
)
```

## Dimension Validation

### Check Vector Store Compatibility

```python
from haven_health_passport.ai.llamaindex.dimensions import validate_dimension_compatibility

# Check single store
is_valid = validate_dimension_compatibility(
    dimension=768,
    vector_store="opensearch",
    model_name="amazon.titan-embed-text-v2:0"
)

# Check multiple stores
from haven_health_passport.ai.llamaindex.dimensions import check_vector_store_compatibility

compatibility = check_vector_store_compatibility(
    dimension=1536,
    vector_stores=["opensearch", "faiss", "pinecone", "weaviate"]
)
# Returns: {"opensearch": True, "faiss": False, ...}
```

### Find Compatible Dimensions

```python
from haven_health_passport.ai.llamaindex.dimensions import DimensionValidator

# Get compatible stores for a dimension
stores = DimensionValidator.get_compatible_vector_stores(768, optimal_only=True)

# Suggest dimensions for store and models
dimensions = DimensionValidator.suggest_compatible_dimensions(
    vector_store="opensearch",
    available_models=["amazon.titan-embed-text-v2:0", "medical-bert-768"]
)
```

## Dimension Reduction

### Reduce Embedding Dimensions

```python
from haven_health_passport.ai.llamaindex.dimensions import reduce_embedding_dimension

# Simple truncation
embedding = [0.1, 0.2, 0.3, ...] # 1536 dimensions
reduced = reduce_embedding_dimension(embedding, 768, method="truncation")
# Average pooling
reduced = reduce_embedding_dimension(embedding, 512, method="average_pooling")

# Batch reduction
embeddings = [emb1, emb2, emb3, ...]  # List of embeddings
reduced_batch = DimensionReducer.batch_reduce(embeddings, 768)
```

### Available Reduction Methods

- **Truncation**: Simple dimension cutting (fastest)
- **Average Pooling**: Averages groups of dimensions
- **Max Pooling**: Takes maximum from dimension groups
- **PCA**: Principal Component Analysis (requires model)
- **Matryoshka**: For models trained with nested representations

## Performance Profiling

### Profile Dimension Performance

```python
from haven_health_passport.ai.llamaindex.dimensions import profile_dimension_performance

# Profile single dimension
profile = profile_dimension_performance(
    dimension=768,
    num_vectors=100000  # 100k documents
)

print(f"Average query time: {profile['avg_query_time_ms']}ms")
print(f"Storage required: {profile['storage_mb']}MB")
print(f"Queries per second: {profile['queries_per_second']}")
```

### Compare Multiple Dimensions

```python
from haven_health_passport.ai.llamaindex.dimensions import DimensionProfiler

# Compare performance
results = DimensionProfiler.compare_dimensions(
    dimensions=[256, 384, 512, 768, 1024],
    num_vectors=50000
)

for dim, metrics in results.items():
    print(f"{dim}d: {metrics['avg_query_time_ms']}ms, {metrics['storage_mb']}MB")
```

## Storage Estimation

```python
from haven_health_passport.ai.llamaindex.dimensions import estimate_storage_requirements
# Estimate storage for your use case
estimate = estimate_storage_requirements(
    dimension=768,
    num_documents=1000000,  # 1M documents
    include_overhead=True    # Include index overhead
)

print(f"Total storage: {estimate['total_storage_gb']}GB")
print(f"Per document: {estimate['bytes_per_document']} bytes")
```

## Recommended Dimensions by Use Case

| Use Case | Recommended Dimension | Model | Notes |
|----------|----------------------|-------|-------|
| Emergency Medical | 384-768 | Titan G1/Medical BERT | Low latency priority |
| Semantic Search | 768-1024 | Titan V2/Medical BERT | Balance of quality and speed |
| Research Analysis | 1536-3072 | Titan V1/OpenAI Large | Quality priority |
| Real-time Chat | 384-512 | Titan G1 | Speed priority |
| Document Clustering | 512-768 | Medical BERT | Good clustering performance |
| Batch Processing | 1024-1536 | Titan V2 | Throughput optimized |

## Vector Store Compatibility

| Vector Store | Max Dimension | Optimal Range | Notes |
|--------------|---------------|---------------|-------|
| OpenSearch | 16,000 | 100-2048 | Best under 2048 |
| FAISS | 8,192 | 64-1024 | CPU optimized for ≤1024 |
| Pinecone | 20,000 | 64-1536 | Cost increases with dimension |
| Weaviate | 65,535 | 100-1536 | Flexible support |
| Qdrant | 65,536 | 100-1536 | Good for moderate dims |
| ChromaDB | 10,000 | 64-1536 | Standard dimensions work best |

## Best Practices

1. **Start with use case**: Let your use case drive dimension selection
2. **Profile before deciding**: Test with realistic data volumes
3. **Consider growth**: Plan for 2-3x document growth
4. **Validate compatibility**: Check vector store and model alignment
5. **Monitor performance**: Track query latency and storage usage
6. **Use reduction wisely**: Only reduce when necessary

## Advanced Configuration

```python
# Custom scoring weights
class CustomSelector(DimensionSelector):
    @classmethod
    def _score_config(cls, config, criteria):
        # Override scoring logic
        score = super()._score_config(config, criteria)

        # Add custom factors
        if criteria.medical_accuracy_required:
            if config.provider == "medical":
                score *= 1.5  # Boost medical models

        return score
```

## Testing

Run dimension tests:
```bash
pytest src/ai/llamaindex/dimensions/tests/
```

## Future Enhancements

- [ ] Learned dimension reduction models
- [ ] Auto-scaling based on load
- [ ] Dynamic dimension adjustment
- [ ] Cross-model dimension alignment
- [ ] Dimension compression techniques
