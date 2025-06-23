# Vector Store Integrations for Haven Health Passport

## Overview

This module provides HIPAA-compliant vector store implementations for medical document indexing and retrieval. Each vector store is optimized for healthcare data with features like PHI filtering, medical synonym expansion, and multi-language support.

## Supported Vector Stores

### 1. OpenSearch (Primary - Production)
- **Use Case**: Enterprise production deployments
- **Features**: AWS managed, medical analyzers, scalable
- **Configuration**: See `opensearch.py`

### 2. Pinecone
- **Use Case**: Fully managed cloud solution
- **Features**: Zero infrastructure, global deployment
- **Configuration**: See `pinecone.py`

### 3. Qdrant
- **Use Case**: High-performance self-hosted
- **Features**: Fast similarity search, efficient memory usage
- **Configuration**: See `qdrant.py`

### 4. Chroma
- **Use Case**: Local development and testing
- **Features**: Embedded database, simple setup
- **Configuration**: See `chroma.py`

### 5. PostgreSQL + pgvector
- **Use Case**: Hybrid SQL/vector workloads
- **Features**: Combine structured and vector data
- **Configuration**: See `postgres.py`

### 6. FAISS
- **Use Case**: Efficient similarity search
- **Features**: Multiple index types, GPU support
- **Configuration**: See `faiss.py`

### 7. Redis
- **Use Case**: Caching and real-time operations
- **Features**: In-memory performance, pub/sub
- **Configuration**: See `redis.py`

## Installation

```bash
# Install all vector store integrations
pip install -r requirements-vector-stores.txt

# Install specific vector store only
pip install llama-index-vector-stores-opensearch  # For OpenSearch
pip install llama-index-vector-stores-pinecone   # For Pinecone
# etc...
```

## Quick Start

```python
from haven_health_passport.ai.llamaindex.vector_stores import create_vector_store, OpenSearchConfig

# Create vector store with default config
vector_store = create_vector_store("opensearch")

# Create with custom configuration
config = OpenSearchConfig(
    endpoint="your-opensearch-domain.us-east-1.es.amazonaws.com",
    index_name="medical-documents",
    enable_medical_analyzer=True,
    enable_phi_filtering=True
)
vector_store = create_vector_store("opensearch", config)

# Use with LlamaIndex
from llama_index.core import VectorStoreIndex, StorageContext

storage_context = StorageContext.from_defaults(vector_store=vector_store)
index = VectorStoreIndex.from_documents(
    documents,
    storage_context=storage_context
)
```

## Medical Optimizations

All vector stores include:

1. **PHI Filtering**: Automatic removal of Protected Health Information
2. **Medical Synonyms**: Expansion of medical terms (e.g., "MI" → "myocardial infarction")
3. **Multi-language Support**: Handle 50+ languages for global healthcare
4. **Compliance Logging**: Full audit trail for HIPAA compliance

## Configuration Examples

### OpenSearch (Production)
```python
config = OpenSearchConfig(
    endpoint="search-domain.region.es.amazonaws.com",
    index_name="haven-health-prod",
    shards=3,
    replicas=2,
    enable_medical_analyzer=True,
    custom_analyzers={
        "medical_analyzer": {
            "tokenizer": "standard",
            "filter": ["lowercase", "medical_synonyms", "stop"]
        }
    }
)
```

### Development Setup (Chroma)
```python
config = ChromaConfig(
    persist_dir="./local_db",
    collection_name="dev_medical_docs"
)
```

### High-Performance (Qdrant)
```python
config = QdrantConfig(
    url="http://qdrant-server:6333",
    collection_name="medical_vectors",
    enable_https=True
)
```

## Best Practices

1. **Choose the Right Store**:
   - Production: OpenSearch or Pinecone
   - Development: Chroma
   - High-performance: Qdrant or FAISS
   - Hybrid needs: PostgreSQL

2. **Configure for Medical Data**:
   - Always enable PHI filtering
   - Use medical analyzers for better search
   - Set appropriate embedding dimensions

3. **Monitor Performance**:
   - Track query latencies
   - Monitor index sizes
   - Set up alerts for errors

4. **Security**:
   - Use encryption in transit and at rest
   - Enable audit logging
   - Implement access controls

## Testing

```bash
# Run vector store tests
pytest src/ai/llamaindex/vector_stores/tests/

# Test specific vector store
pytest src/ai/llamaindex/vector_stores/tests/test_opensearch.py
```

## Troubleshooting

### OpenSearch Connection Issues
```python
# Check endpoint connectivity
import requests
response = requests.get(f"https://{endpoint}")
print(response.status_code)

# Verify AWS credentials
import boto3
sts = boto3.client('sts')
print(sts.get_caller_identity())
```

### Index Creation Failures
- Check embedding dimensions match
- Verify sufficient permissions
- Ensure index name follows conventions

### Performance Issues
- Adjust batch sizes for indexing
- Configure appropriate shard counts
- Use caching for frequently accessed data

## Future Enhancements

- [ ] Automatic index optimization
- [ ] Multi-vector support for documents
- [ ] Hybrid search combining vector and keyword
- [ ] Real-time index updates
- [ ] Cross-region replication
