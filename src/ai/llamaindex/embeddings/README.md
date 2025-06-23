# LlamaIndex Embeddings Module

## Overview

This module provides comprehensive embedding models for the Haven Health Passport system, with special focus on medical document processing and multilingual support.

## Features

- **Multiple Providers**: AWS Bedrock (Titan), OpenAI, and custom medical models
- **Medical Optimization**: CUI augmentation, medical term preservation, semantic types
- **Multilingual Support**: 50+ languages with medical accuracy
- **Multimodal**: Text and image embeddings for medical documents
- **Performance**: Caching, batching, and dimension optimization
- **HIPAA Compliant**: PII sanitization and secure processing

## Quick Start

### Basic Usage

```python
from haven_health_passport.ai.llamaindex.embeddings import get_embedding_model

# Get general-purpose embeddings
embeddings = get_embedding_model("general")

# Embed a single text
text = "Patient has diabetes mellitus type 2"
embedding = await embeddings._aget_query_embedding(text)

# Embed multiple texts
texts = ["Hypertension", "Blood pressure 140/90", "Lisinopril 10mg"]
embeddings_list = await embeddings._aget_text_embeddings(texts)
```

### Medical Embeddings

```python
# Get medical-specific embeddings
medical_embeddings = get_embedding_model("medical")

# Embeddings include medical context
text = "Patient diagnosed with E11.9 and prescribed metformin 500mg BID"
embedding = await medical_embeddings._aget_query_embedding(text)
```

### Multilingual Medical

```python
# Get multilingual medical embeddings
multilingual = get_embedding_model("multilingual")

# Works with 50+ languages
texts = [
    "Diabetes mellitus",  # English
    "Diabète sucré",      # French
    "السكري",             # Arabic
    "糖尿病"              # Chinese
]
embeddings = await multilingual._aget_text_embeddings(texts)
```

## Available Models

### 1. AWS Bedrock (Titan)

```python
from haven_health_passport.ai.llamaindex.embeddings import BedrockEmbeddings

embeddings = BedrockEmbeddings(
    model_id="amazon.titan-embed-text-v2:0",  # 1024 dimensions
    region_name="us-east-1"
)
```

Available models:
- `amazon.titan-embed-text-v1` (1536 dims)
- `amazon.titan-embed-text-v2:0` (1024 dims) - Recommended
- `amazon.titan-embed-g1-text-02` (384 dims) - Fast/cheap
- `amazon.titan-embed-image-v1` (1024 dims) - Multimodal

### 2. OpenAI

```python
from haven_health_passport.ai.llamaindex.embeddings import OpenAIEmbeddings

embeddings = OpenAIEmbeddings(
    model="text-embedding-3-small",
    api_key="your-api-key"  # Or set OPENAI_API_KEY env var
)
```

Available models:
- `text-embedding-ada-002` (1536 dims)
- `text-embedding-3-small` (1536 dims) - Recommended
- `text-embedding-3-large` (3072 dims)

### 3. Medical Embeddings

```python
from haven_health_passport.ai.llamaindex.embeddings import MedicalEmbeddings

embeddings = MedicalEmbeddings(
    use_medical_tokenizer=True,
    use_cui_augmentation=True,
    use_semantic_types=True
)
```

Features:
- Medical term preservation
- CUI (Concept Unique Identifier) integration
- UMLS semantic type encoding
- ICD-10/SNOMED-CT awareness

## Use Case Configurations

### Predefined Configurations

```python
from haven_health_passport.ai.llamaindex.embeddings import get_embedding_config

# Get predefined configs
general_config = get_embedding_config("general")
medical_config = get_embedding_config("medical")
emergency_config = get_embedding_config("emergency")

# Override specific settings
custom_config = get_embedding_config(
    "medical",
    dimension=512,  # Smaller for speed
    batch_size=50   # Larger batches
)
```

Available configurations:
- `general`: General-purpose text (1024 dims)
- `medical`: Medical documents (768 dims)
- `multilingual_medical`: 50+ languages (768 dims)
- `high_performance`: Speed optimized (384 dims)
- `cost_optimized`: Cost efficient with caching
- `research`: High accuracy, no caching
- `multimodal`: Text + images (1024 dims)
- `emergency`: Critical medical situations

### Recommended Configuration

```python
from haven_health_passport.ai.llamaindex.embeddings import get_recommended_config

# Get recommendation based on context
config = get_recommended_config(
    document_type="medical",
    language="es",
    urgency=4  # 1-5 scale
)
# Returns: emergency config for high urgency
```

## Medical Features

### Entity Extraction

Medical embeddings automatically extract and encode:
- ICD-10 codes
- SNOMED-CT concepts
- Drug names (RxNorm)
- Medical procedures
- Symptoms and conditions

### Semantic Types

UMLS semantic types are encoded:
- T047: Disease or Syndrome
- T121: Pharmacologic Substance
- T061: Therapeutic Procedure
- T184: Sign or Symptom

### Multilingual Support

Supports medical terminology in:
- English, Spanish, French, Portuguese
- Arabic, Chinese, Japanese, Hindi
- Russian, German, Italian, Dutch
- 40+ additional languages

## Performance Optimization

### Caching

```python
# Enable caching (default)
embeddings = get_embedding_model("general")

# Check cache statistics
stats = embeddings.get_cache_stats()
print(f"Cache size: {stats['cache_size']}")

# Clear cache if needed
embeddings.clear_cache()
```

### Batching

```python
# Configure batch size
config = get_embedding_config("general", batch_size=50)
embeddings = get_embedding_model("general", config=config)

# Process large document sets efficiently
documents = ["doc1", "doc2", ..., "doc1000"]
embeddings_list = await embeddings._aget_text_embeddings(documents)
```

### Dimension Selection

| Use Case | Recommended Dimension | Model |
|----------|----------------------|-------|
| General | 1024 | Titan V2 |
| Medical | 768 | Medical BERT |
| Speed | 384 | Titan G1 |
| Research | 3072 | OpenAI Large |

## Integration with LlamaIndex

```python
from llama_index.core import VectorStoreIndex, Document
from haven_health_passport.ai.llamaindex.embeddings import get_embedding_model

# Create embedding model
embed_model = get_embedding_model("medical")

# Create index with custom embeddings
documents = [Document(text="Medical record content")]
index = VectorStoreIndex.from_documents(
    documents,
    embed_model=embed_model
)

# Query with same embeddings
query_engine = index.as_query_engine()
response = query_engine.query("Find diabetes medications")
```

## Error Handling

```python
from haven_health_passport.ai.llamaindex.embeddings import get_embedding_model

try:
    embeddings = get_embedding_model("medical")
    result = await embeddings._aget_query_embedding("text")
except Exception as e:
    logger.error(f"Embedding error: {e}")
    # Fallback to general embeddings
    embeddings = get_embedding_model("general")
```

## Testing

Run embedding tests:
```bash
pytest src/ai/llamaindex/embeddings/tests/
```

## Environment Variables

```bash
# AWS Bedrock
AWS_DEFAULT_REGION=us-east-1
BEDROCK_EMBEDDING_MODEL=amazon.titan-embed-text-v2:0

# OpenAI (optional)
OPENAI_API_KEY=your-key
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
```

## Best Practices

1. **Choose the right model**: Medical content needs medical embeddings
2. **Enable caching**: Reduces API calls and costs
3. **Use appropriate dimensions**: Balance quality vs performance
4. **Batch when possible**: Process multiple texts together
5. **Handle errors gracefully**: Have fallback strategies
6. **Monitor costs**: Track API usage for cloud providers

## Future Enhancements

- [ ] Local medical embedding models
- [ ] Fine-tuning on Haven Health data
- [ ] Real-time embedding updates
- [ ] Cross-lingual alignment
- [ ] Federated embedding learning
