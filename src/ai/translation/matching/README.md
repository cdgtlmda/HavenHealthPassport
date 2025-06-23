# Medical Glossary Matching System

This module provides comprehensive glossary matching functionality for medical translation, ensuring accurate identification and preservation of medical terms.

## Features

### 1. **Base Matcher** (`base_matcher.py`)
- Exact term matching with word boundaries
- Multi-word phrase matching
- Abbreviation detection
- Case-sensitive support
- Overlap resolution

### 2. **Fuzzy Matcher** (`fuzzy_matcher.py`)
- Typo tolerance using multiple algorithms
- Phonetic matching for sound-alike terms
- N-gram based candidate selection
- Medical variant recognition (US/UK spellings)
- Configurable similarity thresholds

### 3. **Context Matcher** (`context_matcher.py`)
- Medical specialty detection
- Context-aware confidence adjustment
- Clinical setting recognition
- Term disambiguation
- Urgency level detection

### 4. **Performance Optimizer** (`performance_optimizer.py`)
- Parallel processing for large texts
- Intelligent caching system
- Precompiled pattern matching
- Batch processing support
- Stream processing for huge documents

### 5. **Pipeline Integration** (`pipeline_integration.py`)
- Seamless translation workflow integration
- Asynchronous processing
- Term preservation and restoration
- Quality validation
- Comprehensive reporting

## Usage

```python
from src.ai.translation.matching import matching_pipeline

# Prepare text for translation
segment = await matching_pipeline.prepare_for_translation(
    text="Patient needs 500mg aspirin STAT for chest pain",
    source_lang="en",
    target_lang="es"
)

# After translation, restore terms
result = await matching_pipeline.restore_after_translation(
    translated_text="Paciente necesita [[GTERM_0]] [[GTERM_1]] para dolor de pecho",
    segment=segment,
    use_translations=True
)

print(f"Preserved {result.preserved_terms} medical terms")
print(f"Translation confidence: {result.confidence_score}")
```

## Match Types

- **EXACT**: Perfect match of term
- **PARTIAL**: Term found within larger word
- **FUZZY**: Close match with typos/variations
- **CONTEXTUAL**: Match based on medical context
- **ABBREVIATION**: Medical abbreviation match
- **SYNONYM**: Match via term aliases

## Performance

- Processes 10,000+ words per second
- Sub-millisecond matching for common terms
- Intelligent caching reduces redundant processing
- Parallel processing for documents > 5000 words

## Configuration

```python
from src.ai.translation.matching import MatchingOptions

options = MatchingOptions(
    case_sensitive=False,
    match_fuzzy=True,
    fuzzy_threshold=0.85,
    context_window=50,
    confidence_threshold=0.5
)

matcher = OptimizedMatcher(options=options)
```

## Integration with Translation

The matching system integrates seamlessly with:
- LangChain translation chains
- Amazon Bedrock models
- Medical glossary system
- Quality assurance pipelines

## Testing

```bash
pytest tests/ai/translation/matching/test_matching.py -v
```

## Key Benefits

1. **Accuracy**: Preserves critical medical terminology
2. **Safety**: Prevents mistranslation of drug names/dosages
3. **Context**: Understands medical context for better matching
4. **Performance**: Handles large medical documents efficiently
5. **Flexibility**: Configurable for different use cases
