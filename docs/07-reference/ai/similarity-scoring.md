# Similarity Scoring Configuration

## Overview

The similarity scoring system has been implemented to validate the quality of medical translations by comparing semantic, syntactic, and structural similarity between source and translated texts. This ensures that translations maintain medical accuracy while preserving the original meaning.

## Architecture

### Components

1. **SimilarityScorer** (`src/ai/translation/validation/similarity.py`)
   - Main class for calculating similarity scores
   - Supports multiple similarity metrics
   - Configurable thresholds and weights

2. **SimilarityValidator** (`src/ai/translation/validation/similarity_validator.py`)
   - Integrates similarity scoring with the validation pipeline
   - Validates translations against configured thresholds
   - Reports issues and suggestions

3. **Integration with ValidationPipeline**
   - Added `validate_similarity` flag to ValidationConfig
   - Automatically calculates similarity metrics during validation
   - Updates TranslationMetrics with similarity scores

## Similarity Metrics

The system implements eight different similarity metrics:

### 1. Semantic Similarity
- Uses sentence embeddings to measure meaning preservation
- Model: `sentence-transformers/all-MiniLM-L6-v2`
- Threshold: 0.85 (configurable)

### 2. Medical Similarity
- Specialized medical embeddings for healthcare terminology
- Model: `cambridgeltl/SapBERT-from-PubMedBERT-fulltext`
- Includes medical term preservation checks
- Threshold: 0.9 (configurable)

### 3. BLEU Score
- Measures n-gram overlap between translations
- Uses smoothing for short texts
- Good for structural similarity

### 4. ROUGE Score
- Recall-oriented metric for translation quality
- Includes ROUGE-1, ROUGE-2, and ROUGE-L
- Focus on content coverage

### 5. METEOR Score
- Considers synonyms and paraphrases
- Language-aware evaluation

### 6. Levenshtein Similarity
- Character-level edit distance
- Normalized by text length

### 7. Jaccard Similarity
- Token-level overlap measurement
- Simple but effective for word preservation

### 8. Cosine Similarity
- TF-IDF based similarity
- Captures document-level similarity

## Configuration

### Basic Configuration

```python
from src.ai.translation.validation import ValidationConfig, ValidationLevel

config = ValidationConfig(
    level=ValidationLevel.STRICT,
    validate_similarity=True,  # Enable similarity validation
    min_confidence_threshold=0.85
)
```

### Advanced Configuration

```python
from src.ai.translation.validation.similarity import SimilarityConfig, SimilarityMetric

similarity_config = SimilarityConfig(
    # Model selection
    embedding_model="sentence-transformers/all-MiniLM-L6-v2",
    medical_embedding_model="cambridgeltl/SapBERT-from-PubMedBERT-fulltext",

    # Thresholds
    min_semantic_similarity=0.85,
    min_bleu_score=0.6,
    min_rouge_score=0.7,
    min_medical_similarity=0.9,

    # Metric weights for composite scoring
    metric_weights={
        SimilarityMetric.SEMANTIC: 0.3,
        SimilarityMetric.MEDICAL: 0.4,
        SimilarityMetric.BLEU: 0.15,
        SimilarityMetric.ROUGE: 0.15
    }
)
```

## Usage Examples

### Direct Similarity Scoring

```python
from src.ai.translation.validation.similarity import SimilarityScorer

scorer = SimilarityScorer()
scores = scorer.calculate_similarity(
    source_text="The patient has hypertension",
    translated_text="El paciente tiene hipertensión",
    metrics=[SimilarityMetric.SEMANTIC, SimilarityMetric.MEDICAL]
)

for metric, score in scores.items():
    print(f"{metric.value}: {score.score:.3f}")
```

### Validation Pipeline Integration

```python
from src.ai.translation.validation import TranslationValidationPipeline

pipeline = TranslationValidationPipeline()
result = pipeline.validate(
    source_text="Administer 500mg amoxicillin",
    translated_text="Administrar 500mg de amoxicilina",
    source_lang="en",
    target_lang="es"
)

# Access similarity scores
if result.metrics.semantic_similarity:
    print(f"Semantic similarity: {result.metrics.semantic_similarity:.3f}")
```

## Medical Term Preservation

The medical similarity metric specifically checks for:

- Dosage preservation (e.g., "500mg")
- Medical code preservation (e.g., ICD-10 codes)
- Drug name accuracy
- Measurement units
- Vital signs formats

## Performance Considerations

1. **Model Loading**: Embedding models are loaded lazily on first use
2. **Caching**: Embeddings are cached for repeated texts
3. **Batch Processing**: Use `validate_batch()` for multiple translations

## Thresholds and Quality Levels

| Metric | Critical | Strict | Standard | Basic |
|--------|----------|---------|-----------|--------|
| Semantic | 0.95 | 0.90 | 0.85 | 0.80 |
| Medical | 0.98 | 0.95 | 0.90 | 0.85 |
| BLEU | 0.80 | 0.70 | 0.60 | 0.50 |
| ROUGE | 0.85 | 0.75 | 0.70 | 0.60 |

## Error Handling

The system handles various error scenarios:

- Missing models: Downloads on first use
- Network errors: Falls back to cached embeddings
- Invalid text: Returns low confidence scores
- Language mismatches: Adjusts thresholds accordingly

## Monitoring and Metrics

Similarity scores are tracked in:

1. `TranslationMetrics.semantic_similarity`
2. `TranslationMetrics.terminology_accuracy` (medical similarity)
3. `ValidationResult.metadata["similarity_scores"]`
4. CloudWatch metrics (if configured)

## Future Enhancements

1. Custom medical embedding fine-tuning
2. Language-specific similarity models
3. Domain-specific vocabulary handling
4. Real-time similarity feedback
5. A/B testing for threshold optimization

## Dependencies

Required packages (already added to `requirements-ai.txt`):

- sentence-transformers>=2.2.0
- scikit-learn>=1.3.0
- nltk>=3.8.0
- rouge-score>=0.1.2
- editdistance>=0.6.0
- numpy>=1.24.0

## Testing

Run the test script to verify configuration:

```bash
python tests/test_similarity_scoring.py
```

This will validate that similarity scoring is properly integrated and functioning correctly.
