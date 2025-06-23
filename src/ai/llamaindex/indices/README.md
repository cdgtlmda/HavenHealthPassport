# Vector Indices Documentation

## Overview

The vector indices module provides a comprehensive framework for creating and managing various types of vector indices optimized for different use cases in the Haven Health Passport system.

## Index Types

### 1. Dense Vector Indices

**DenseVectorIndex**
- Standard dense vector index using embeddings
- Full similarity search capabilities
- Suitable for semantic search

**OptimizedDenseIndex**
- Performance-optimized with quantization
- Approximate search support (HNSW)
- Reduced memory usage

**ShardedDenseIndex**
- Horizontally sharded for scalability
- Distributed search across shards
- Suitable for large-scale deployments

### 2. Sparse Vector Indices

**SparseVectorIndex**
- TF-IDF based sparse vectors
- Efficient keyword matching
- Low memory footprint

**BM25Index**
- BM25 ranking algorithm
- Better performance than TF-IDF
- Optimized for document retrieval

**TFIDFIndex**
- Enhanced TF-IDF with medical term weighting
- Medical terminology optimization
- Multi-language support

### 3. Hybrid Indices

**HybridVectorIndex**
- Combines dense and sparse search
- Configurable weighting
- Best of both approaches

**DenseSparseFusionIndex**
- Advanced fusion techniques (RRF)
- Better result combination
- Reduced bias

**MultiStageIndex**
- Two-stage retrieval process
- Sparse for candidates, dense for ranking
- Optimized for large collections

### 4. Medical Indices

**MedicalVectorIndex**
- Medical entity recognition
- PHI protection
- Ontology expansion
- Clinical context awareness

**ClinicalTrialsIndex**
- Specialized for clinical trials
- Phase and intervention extraction
- NCT ID recognition

**PatientRecordsIndex**
- Enhanced privacy controls
- Access control integration
- Record section extraction

**DrugInteractionIndex**
- Drug interaction checking
- Contraindication detection
- Drug class recognition

### 5. Multimodal Indices

**MultiModalIndex**
- Text and image support
- Cross-modal search
- Unified embeddings

**TextImageIndex**
- Optimized for text-image pairs
- CLIP-style embeddings
- Visual-semantic search

**MedicalImagingIndex**
- DICOM metadata support
- Modality-specific search
- Medical image retrieval

## Usage Examples

### Basic Usage

```python
from src.ai.llamaindex.indices import create_vector_index

# Create a dense vector index
index = create_vector_index("dense")

# Build index with documents
documents = [...]  # Your documents
index.build_index(documents)

# Search
results = index.search("patient symptoms", top_k=10)
```

### Medical Index

```python
from src.ai.llamaindex.indices import get_index_for_use_case

# Create medical index
medical_index = get_index_for_use_case("medical_records")

# Build with PHI protection
medical_index.build_index(patient_documents)

# Search with authorization
results = medical_index.search(
    "diabetes treatment plan",
    top_k=5,
    authorized_user="dr_smith"
)
```

### Hybrid Search

```python
# Create hybrid index
hybrid_index = create_vector_index(
    "hybrid",
    dense_weight=0.7,
    sparse_weight=0.3
)

# Build index
hybrid_index.build_index(documents)

# Get detailed results
results = hybrid_index.search(
    "chest pain emergency",
    top_k=10,
    return_hybrid_results=True
)

# Access component scores
for result in results:
    print(f"Dense: {result.dense_score:.3f}")
    print(f"Sparse: {result.sparse_score:.3f}")
    print(f"Combined: {result.combined_score:.3f}")
```

### Multimodal Search

```python
from src.ai.llamaindex.indices import MultiModalDocument

# Create multimodal index
mm_index = create_vector_index("medical_imaging")

# Create multimodal documents
docs = [
    MultiModalDocument(
        text="Chest X-ray showing pneumonia",
        image_path="/path/to/xray.jpg",
        metadata={"modality": "xray"}
    )
]

# Build index
mm_index.build_index(docs)

# Search with text
results = mm_index.search("pneumonia findings")

# Search with image
query_doc = MultiModalDocument(
    image_path="/path/to/query_image.jpg"
)
results = mm_index.search(query_doc)
```

## Configuration

### Index Configuration

```python
from src.ai.llamaindex.indices import VectorIndexConfig

config = VectorIndexConfig(
    index_name="my_medical_index",
    dimension=768,

    # Storage
    persist_path="/path/to/index",
    enable_persistence=True,

    # Search
    default_top_k=10,
    similarity_threshold=0.7,
    enable_reranking=True,

    # Medical
    enable_medical_expansion=True,
    enable_multilingual=True,

    # Performance
    enable_caching=True,
    cache_size=1000,
    enable_approximate_search=False
)
```

### Medical Configuration

```python
from src.ai.llamaindex.indices import MedicalIndexConfig

config = MedicalIndexConfig(
    # Medical NER
    enable_medical_ner=True,
    ner_models=["biobert", "scispacy"],

    # Ontologies
    enable_ontology_expansion=True,
    ontologies=["umls", "icd10", "snomed"],

    # Privacy
    enable_phi_detection=True,
    phi_handling="encrypt",

    # Clinical
    enable_clinical_context=True,
    clinical_specialties=["cardiology", "oncology"]
)
```

## Index Management

### Using IndexManager

```python
from src.ai.llamaindex.indices import IndexManager

# Create manager
manager = IndexManager()

# Register indices
manager.register_index("main", dense_index)
manager.register_index("medical", medical_index)

# Check health
health = manager.get_health_status()
for name, status in health.items():
    print(f"{name}: {status.status}")
    if status.issues:
        print(f"  Issues: {status.issues}")

# Optimize indices
manager.optimize_all()

# Get statistics
stats = manager.get_statistics()
```

### Monitoring

```python
from src.ai.llamaindex.indices import IndexMonitor

# Create monitor
monitor = IndexMonitor(manager)

# Start monitoring
monitor.start_monitoring(interval_seconds=60)

# Get alerts
alerts = monitor.get_alerts()
for alert in alerts:
    print(f"{alert['severity']}: {alert['message']}")

# Get metrics summary
summary = monitor.get_metrics_summary("main", hours=24)
```

### Optimization

```python
from src.ai.llamaindex.indices import IndexOptimizer

# Create optimizer
optimizer = IndexOptimizer(manager)

# Analyze index
analysis = optimizer.analyze_index("main")
print(f"Recommendations: {analysis['recommendations']}")

# Auto-optimize
optimizer.auto_optimize("main")
```

## Use Case Templates

### Medical System

```python
# Create complete medical system
from src.ai.llamaindex.indices import create_from_template

system = create_from_template("medical_system")

# Access indices
patient_index = system["manager"].get_index("patient_records")
knowledge_index = system["manager"].get_index("medical_knowledge")
drug_index = system["manager"].get_index("drug_database")
```

### Research Platform

```python
system = create_from_template("research_platform")

# Access specialized indices
papers_index = system["manager"].get_index("papers")
trials_index = system["manager"].get_index("clinical_trials")
```

## Performance Optimization

### Sharding for Scale

```python
# Create sharded index for large datasets
sharded_index = create_vector_index(
    "dense_sharded",
    num_shards=8,
    config=VectorIndexConfig(
        enable_compression=True,
        enable_approximate_search=True
    )
)
```

### Caching Strategy

```python
config = VectorIndexConfig(
    enable_caching=True,
    cache_size=5000,  # Adjust based on memory
    cache_ttl_seconds=3600  # 1 hour
)
```

### Batch Processing

```python
# Efficient batch operations
doc_ids = index.add_documents(documents)  # Batch add

# Batch search
queries = ["query1", "query2", "query3"]
results = index.batch_search(queries)
```

## Best Practices

1. **Choose the Right Index Type**
   - Dense: Semantic search, concept matching
   - Sparse: Keyword search, exact matching
   - Hybrid: Balanced approach
   - Medical: Healthcare-specific needs

2. **Configure for Your Use Case**
   - Enable caching for repeated queries
   - Use sharding for large datasets
   - Enable compression for storage savings
   - Use approximate search for speed

3. **Monitor Performance**
   - Track query times
   - Monitor cache hit rates
   - Watch for degradation
   - Regular optimization

4. **Handle Medical Data Properly**
   - Always enable PHI protection
   - Use appropriate encryption
   - Implement access controls
   - Audit data access

5. **Optimize Search Quality**
   - Tune similarity thresholds
   - Configure re-ranking
   - Use appropriate embeddings
   - Test with real queries
