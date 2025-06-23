# Similarity Metrics Documentation

## Overview

The similarity metrics module provides a comprehensive framework for measuring similarity between vector embeddings in the Haven Health Passport system. It includes:

- **Basic Metrics**: Cosine, Euclidean, Dot Product, Manhattan, Jaccard
- **Medical-Specific Metrics**: Medical term matching, clinical relevance, semantic similarity
- **Hybrid Approaches**: Weighted combinations, ensemble methods
- **Re-ranking**: Medical and cross-encoder based re-ranking

## Architecture

### Core Components

1. **Base Classes** (`base.py`)
   - `SimilarityConfig`: Configuration for all similarity scorers
   - `BaseSimilarityScorer`: Abstract base class with common functionality

2. **Basic Metrics** (`metrics.py`)
   - `CosineSimilarity`: Most common for embeddings (range: -1 to 1)
   - `EuclideanDistance`: Straight-line distance
   - `DotProductSimilarity`: Inner product
   - `ManhattanDistance`: L1 distance
   - `JaccardSimilarity`: For sparse/binary features

3. **Medical Metrics** (`medical.py`)
   - `MedicalSimilarityScorer`: Enhanced scoring with medical knowledge
   - `ClinicalRelevanceScorer`: Prioritizes clinical importance
   - `SemanticMedicalSimilarity`: Uses medical ontologies

4. **Hybrid Metrics** (`hybrid.py`)
   - `HybridSimilarityScorer`: Combines multiple metrics
   - `WeightedSimilarityScorer`: Dynamic weight adjustment
   - `EnsembleSimilarityScorer`: Voting or stacking approaches

5. **Re-ranking** (`reranking.py`)
   - `MedicalReRanker`: Re-ranks based on medical relevance
   - `CrossEncoderReRanker`: Uses cross-encoder models

## Usage Examples

### Basic Similarity Scoring

```python
from src.ai.llamaindex.similarity import SimilarityFactory, SimilarityMetric

# Create cosine similarity scorer
scorer = SimilarityFactory.create_scorer(SimilarityMetric.COSINE)

# Score single pair
score = scorer.score(query_embedding, doc_embedding)

# Score batch
scores = scorer.batch_score(query_embedding, doc_embeddings)
```

### Medical Similarity with Metadata

```python
from src.ai.llamaindex.similarity import get_similarity_scorer

# Create medical scorer
medical_scorer = get_similarity_scorer("medical")

# Define metadata
query_metadata = {
    "medical_terms": ["diabetes", "insulin"],
    "disease_terms": ["diabetes mellitus"],
    "semantic_types": ["T047"],  # Disease
    "urgency_level": 2
}

doc_metadata = {
    "medical_terms": ["diabetes", "metformin"],
    "disease_terms": ["type 2 diabetes"],
    "semantic_types": ["T047"],
    "urgency_level": 2
}

# Score with metadata boost
score = medical_scorer.score(
    query_embedding,
    doc_embedding,
    query_metadata,
    doc_metadata
)
```

### Hybrid Scoring

```python
# Create hybrid scorer with custom weights
hybrid_scorer = SimilarityFactory.create_hybrid_scorer(
    base_metrics=["cosine", "euclidean", "medical"],
    weights=[0.5, 0.2, 0.3]
)

# Create ensemble scorer
ensemble_scorer = SimilarityFactory.create_ensemble_scorer(
    base_metrics=["cosine", "medical"],
    ensemble_method="voting"
)
```

### Re-ranking Results

```python
from src.ai.llamaindex.similarity import create_reranker

# Create medical re-ranker
reranker = create_reranker("medical", top_k=20)

# Re-rank search results
results = [
    ("doc1", 0.85, {"text": "...", "clinical_urgency": "emergency"}),
    ("doc2", 0.82, {"text": "...", "clinical_urgency": "routine"}),
]

reranked = reranker.rerank(query_text, results)
```

## Predefined Use Cases

The module provides optimized configurations for common use cases:

```python
# General purpose
scorer = get_similarity_scorer("general")

# Medical document search
scorer = get_similarity_scorer("medical")

# Clinical decision support
scorer = get_similarity_scorer("clinical")

# Multilingual medical content
scorer = get_similarity_scorer("multilingual")

# High precision search
scorer = get_similarity_scorer("high_precision")

# Fast similarity (for real-time)
scorer = get_similarity_scorer("fast")

# Research applications
scorer = get_similarity_scorer("research")
```

## Configuration Options

### Basic Configuration

```python
from src.ai.llamaindex.similarity import SimilarityConfig, SimilarityMetric

config = SimilarityConfig(
    metric=SimilarityMetric.COSINE,
    normalize_scores=True,
    score_threshold=0.5,
    consider_metadata=True,
    batch_size=100
)
```

### Medical Configuration

```python
from src.ai.llamaindex.similarity.medical import MedicalSimilarityConfig

config = MedicalSimilarityConfig(
    # Medical term weights
    disease_weight=2.0,
    medication_weight=1.8,
    symptom_weight=1.7,

    # Features
    use_semantic_type_matching=True,
    consider_clinical_context=True,
    use_code_matching=True,

    # Clinical settings
    urgency_boost_factor=2.0,
    cross_lingual_penalty=0.9
)
```

### Hybrid Configuration

```python
from src.ai.llamaindex.similarity.hybrid import HybridSimilarityConfig

config = HybridSimilarityConfig(
    base_scorers=["cosine", "euclidean"],
    scorer_weights=[0.7, 0.3],
    aggregation_method="weighted_mean",
    use_adaptive_weights=True
)
```

## Medical Features

### Medical Term Matching

The medical scorer enhances similarity based on:
- **Disease terms**: Exact and synonym matching
- **Medications**: Drug name and class matching
- **Procedures**: Medical procedure overlap
- **Anatomy**: Body part references
- **Symptoms**: Clinical presentation matching

### Semantic Type Matching

Uses UMLS semantic types:
- T047: Disease or Syndrome (weight: 2.0)
- T121: Pharmacologic Substance (weight: 1.8)
- T061: Therapeutic Procedure (weight: 1.6)
- T184: Sign or Symptom (weight: 1.7)
- T023: Body Part (weight: 1.5)

### Clinical Context

Considers:
- **Urgency levels**: Emergency > Urgent > Routine
- **Medical specialty**: Cardiology, Neurology, etc.
- **Evidence level**: Systematic review > RCT > Expert opinion
- **Publication recency**: Recent publications get boost

### Code Matching

Supports medical coding systems:
- **ICD-10**: International Classification of Diseases
- **SNOMED CT**: Systematized Nomenclature of Medicine
- **RxNorm**: Medication codes
- **LOINC**: Laboratory codes

## Performance Optimization

### Caching

All scorers support result caching:

```python
# Scores are automatically cached
score1 = scorer.score(query, doc)  # Calculates
score2 = scorer.score(query, doc)  # Returns cached
```

### Batch Processing

Process multiple documents efficiently:

```python
# Process in optimized batches
scores = scorer.batch_score(
    query_embedding,
    doc_embeddings,  # List of embeddings
    doc_metadatas    # Optional metadata list
)
```

### Approximate Search

For large-scale applications:

```python
config = SimilarityConfig(
    use_approximate_search=True,
    approximate_search_params={
        "nlist": 100,
        "nprobe": 10
    }
)
```

## Integration with LlamaIndex

The similarity metrics integrate seamlessly with LlamaIndex:

```python
from llama_index.core import VectorStoreIndex
from src.ai.llamaindex.similarity import get_similarity_scorer

# Create custom scorer
scorer = get_similarity_scorer("medical")

# Use in vector store query
index = VectorStoreIndex.from_documents(documents)
query_engine = index.as_query_engine(
    similarity_top_k=10,
    similarity_scorer=scorer
)
```

## Best Practices

1. **Choose appropriate metric**: Cosine for general, medical for healthcare
2. **Use metadata**: Always provide metadata for better scoring
3. **Configure thresholds**: Set appropriate score thresholds
4. **Enable re-ranking**: For critical applications
5. **Monitor performance**: Track scoring latency
6. **Test configurations**: Validate on your specific data

## Troubleshooting

### Low Scores

- Check embedding quality
- Verify metadata is provided
- Adjust weights and thresholds
- Consider different metrics

### Performance Issues

- Enable batch processing
- Use approximate search
- Reduce re-ranking top_k
- Cache frequently used embeddings

### Medical Matching Issues

- Verify medical term extraction
- Check synonym dictionaries
- Validate semantic type assignments
- Test with known medical pairs
