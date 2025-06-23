# Custom Embeddings Documentation

## Overview

The custom embeddings module provides a flexible framework for implementing domain-specific, experimental, or proprietary embedding models in the Haven Health Passport system. This allows for:

- Integration of external embedding services
- Implementation of novel embedding techniques
- Domain-specific optimizations
- Hybrid approaches combining multiple models
- Complete control over the embedding pipeline

## Architecture

### Base Classes

1. **CustomEmbeddingConfig**: Extended configuration for custom embeddings
   - Model settings (path, type, pooling strategy)
   - Preprocessing options (lowercase, stopwords, stemming)
   - Advanced features (subword embeddings, positional encoding)
   - Domain-specific options
   - Performance optimization settings

2. **CustomEmbeddingBase**: Abstract base class providing common functionality
   - Preprocessing pipeline
   - Postprocessing pipeline
   - Dimension adjustment
   - Caching support
   - Batch processing

### Implementations

1. **TransformerCustomEmbeddings**: For transformer-based models
   - Support for any transformer architecture
   - Configurable pooling strategies
   - Token-level embeddings
   - Attention weight utilization

2. **Word2VecCustomEmbeddings**: For word embedding approaches
   - Custom vocabulary support
   - Multiple pooling strategies (mean, max, first)
   - Out-of-vocabulary handling
   - Efficient for simple use cases

3. **HybridCustomEmbeddings**: Combines multiple embedding models
   - Weighted combination of base models
   - Automatic dimension adjustment
   - Flexible weighting schemes
   - Ensemble benefits

4. **DomainAdaptiveEmbeddings**: Adapts to content domain
   - Automatic domain detection
   - Domain-specific model selection
   - Fallback mechanisms
   - Extensible domain definitions

## Usage Examples

### Basic Custom Embedding

```python
from src.ai.llamaindex.embeddings import create_custom_embeddings, CustomEmbeddingConfig

# Create configuration
config = CustomEmbeddingConfig(
    model_name="my-custom-model",
    dimension=512,
    pooling_strategy="mean",
    normalize=True
)

# Create embeddings
embeddings = create_custom_embeddings(
    embedding_type="transformer",
    config=config
)

# Generate embeddings
texts = ["Medical report for patient", "Diagnóstico del paciente"]
vectors = await embeddings._aget_text_embeddings(texts)
```

### Using Custom Embedding Function

```python
def my_embedding_function(text: str) -> List[float]:
    """Custom logic for generating embeddings"""
    # Call external API, use proprietary model, etc.
    return embedding_vector

# Create embeddings with custom function
embeddings = TransformerCustomEmbeddings(
    config=config,
    embedding_function=my_embedding_function
)
```

### Hybrid Embeddings

```python
from src.ai.llamaindex.embeddings import (
    HybridCustomEmbeddings,
    MedicalEmbeddings,
    BedrockEmbeddings
)

# Create base models
medical = MedicalEmbeddings()
bedrock = BedrockEmbeddings()

# Create hybrid with weighted combination
hybrid = HybridCustomEmbeddings(
    base_embeddings=[medical, bedrock],
    combination_weights=[0.7, 0.3],  # 70% medical, 30% bedrock
    config=CustomEmbeddingConfig(dimension=768)
)
```

### Domain-Adaptive Embeddings

```python
# Create domain-specific models
domain_models = {
    "medical": MedicalEmbeddings(),
    "legal": create_custom_embeddings("transformer",
                                    config=legal_config),
    "general": BedrockEmbeddings()
}

# Create adaptive embeddings
adaptive = DomainAdaptiveEmbeddings(
    domain_models=domain_models,
    domain_detector=my_domain_detector_function  # Optional
)

# Automatically uses appropriate model based on content
embeddings = await adaptive._aget_text_embeddings([
    "Patient diagnosis report",  # Uses medical model
    "Legal contract terms",      # Uses legal model
    "General conversation"       # Uses general model
])
```

## Configuration Options

### Model Configuration

```python
config = CustomEmbeddingConfig(
    # Model settings
    model_path="/path/to/model",
    model_type="transformer",  # transformer, word2vec, glove, fasttext, custom
    dimension=768,

    # Pooling strategies
    pooling_strategy="mean",  # mean, max, cls, weighted
    combine_strategies=["mean", "max"],  # For advanced pooling

    # Preprocessing
    lowercase=True,
    remove_stopwords=True,
    stem_words=False,
    lemmatize=True,
    max_sequence_length=512,

    # Advanced features
    use_subword_embeddings=True,
    use_positional_encoding=True,
    use_attention_weights=True,

    # Performance
    batch_size=32,
    use_gpu=True,
    quantization_bits=8,  # 8, 16, or None
    dynamic_batching=True,
    cache_embeddings=True
)
```

### Factory Integration

The custom embeddings are fully integrated with the embedding factory:

```python
from src.ai.llamaindex.embeddings import EmbeddingFactory, get_embedding_model

# Using factory
custom = EmbeddingFactory.create_embedding_model(
    provider="custom",
    embedding_type="transformer",
    config=config
)

# Using predefined use cases
transformer = get_embedding_model("custom_transformer")
word2vec = get_embedding_model("custom_word2vec")
hybrid = get_embedding_model("custom_hybrid")
adaptive = get_embedding_model("custom_domain_adaptive")
```

## Advanced Features

### Preprocessing Pipeline

Custom embeddings support a flexible preprocessing pipeline:

1. **Text normalization**: Lowercase, accent removal
2. **Stopword removal**: Multilingual support
3. **Stemming**: Language-specific stemmers
4. **Lemmatization**: Advanced morphological analysis
5. **Custom preprocessing**: Add your own functions

### Dimension Management

Automatic dimension adjustment ensures compatibility:

- **Padding**: Zero-padding for smaller embeddings
- **Truncation**: Intelligent truncation for larger embeddings
- **Projection**: Linear projection for dimension reduction
- **Expansion**: Feature expansion techniques

### Caching System

Built-in caching for performance:

- Text-level caching with SHA256 keys
- Configurable cache size
- Cache statistics and monitoring
- Manual cache management

### Batch Processing

Efficient batch processing with:

- Dynamic batching based on available memory
- Automatic batch size optimization
- Progress tracking for large batches
- Error recovery and retry logic

## Integration with Haven Health Passport

### Medical Context

Custom embeddings can be optimized for medical content:

```python
class MedicalCustomEmbeddings(TransformerCustomEmbeddings):
    def _init_model(self):
        # Load medical-specific transformer
        self.model = load_medical_bert()

    def _preprocess_text(self, text: str) -> str:
        # Preserve medical terms
        text = preserve_medical_terminology(text)
        return super()._preprocess_text(text)
```

### Multilingual Support

Support for 50+ languages with:

- Language detection
- Language-specific preprocessing
- Cross-lingual embeddings
- Language-aware pooling

### Privacy and Security

- PII sanitization before embedding
- Secure model loading
- Encrypted model storage
- Audit logging for compliance

## Performance Optimization

### GPU Acceleration

```python
config = CustomEmbeddingConfig(
    use_gpu=True,
    quantization_bits=8  # Reduce memory usage
)
```

### Batching Strategies

```python
config = CustomEmbeddingConfig(
    batch_size=64,
    dynamic_batching=True,  # Adjust based on input
    max_sequence_length=256  # Reduce for speed
)
```

### Caching

```python
# Enable caching
config.cache_embeddings = True

# Check cache performance
stats = embeddings.get_cache_stats()
print(f"Cache hit rate: {stats['hits'] / stats['total']}")
```

## Troubleshooting

### Common Issues

1. **Dimension mismatch**: Ensure config.dimension matches model output
2. **Memory errors**: Reduce batch_size or enable quantization
3. **Slow performance**: Enable GPU, optimize batch size, use caching
4. **Quality issues**: Check preprocessing, try different pooling strategies

### Debugging

```python
import logging
logging.basicConfig(level=logging.DEBUG)

# Enable debug logging
embeddings.logger.setLevel(logging.DEBUG)

# Check preprocessing
processed = embeddings._preprocess_text("Test text")
print(f"Preprocessed: {processed}")

# Check dimensions
embedding = await embeddings._aget_query_embedding("Test")
print(f"Dimension: {len(embedding)}")
```

## Best Practices

1. **Start simple**: Use TransformerCustomEmbeddings with defaults
2. **Test thoroughly**: Verify embeddings quality on your data
3. **Monitor performance**: Track latency and resource usage
4. **Use caching**: Enable for repeated texts
5. **Batch when possible**: Process multiple texts together
6. **Handle errors gracefully**: Implement fallback strategies
7. **Document domain logic**: Clearly document custom implementations

## Future Enhancements

- [ ] Support for ONNX models
- [ ] Integration with TensorFlow models
- [ ] Automatic model optimization
- [ ] Federated learning support
- [ ] Zero-shot domain adaptation
- [ ] Active learning integration
