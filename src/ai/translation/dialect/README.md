# Dialect Detection System

## Overview

The dialect detection system provides comprehensive capabilities for identifying regional language variations in medical texts. It supports detection of dialectal differences in vocabulary, spelling, medical terminology, and healthcare system terminology.

## Architecture

### Core Components

1. **DialectDetector** (`core.py`)
   - Main dialect detection implementation
   - Supports rule-based and AI-enhanced detection
   - Caching for performance optimization
   - Confidence scoring with multiple levels

2. **DialectProfile** (`profiles.py`)
   - Pre-defined profiles for major dialects
   - Includes medical terminology variations
   - Healthcare system terminology
   - Measurement preferences
   - Date format preferences

3. **MedicalDialectDetector** (`medical.py`)
   - Specialized detector for medical content
   - Drug name variation detection
   - Healthcare facility terminology
   - Medical specialty terms
   - Enhanced scoring for medical contexts

4. **DialectFeatureExtractor** (`features.py`)
   - Comprehensive feature extraction
   - Lexical, phonetic, syntactic, and orthographic features
   - Medical-specific feature detection
   - Statistical analysis of text characteristics

## Supported Dialects

### English
- **en-US**: American English
- **en-GB**: British English
- **en-CA**: Canadian English
- **en-AU**: Australian English

### Spanish
- **es-MX**: Mexican Spanish
- **es-ES**: Peninsular Spanish

### French
- **fr-FR**: Metropolitan French- **fr-CA**: Canadian French

## Key Features

### 1. Multi-Level Detection
```python
from src.ai.translation.dialect import DialectDetector

detector = DialectDetector()
result = detector.detect(text, language_hint=Language.ENGLISH)

# Access results
print(f"Dialect: {result.detected_dialect}")
print(f"Confidence: {result.confidence} ({result.confidence_level.value})")
print(f"Alternatives: {result.alternative_dialects}")
```

### 2. Medical-Enhanced Detection
```python
from src.ai.translation.dialect import MedicalDialectDetector

medical_detector = MedicalDialectDetector()
result = medical_detector.detect_medical_dialect(text)

# Medical-specific metadata
print(f"Medical terms found: {result.metadata['medical_terms_found']}")
print(f"Medical score: {result.metadata['medical_score']}")
```

### 3. Feature Extraction
```python
from src.ai.translation.dialect import DialectFeatureExtractor

extractor = DialectFeatureExtractor()
features = extractor.extract_all_features(text)

# Access different feature types
lexical = features["lexical"]
syntactic = features["syntactic"]
orthographic = features["orthographic"]
```

### 4. Dialect Profiles
```python
from src.ai.translation.dialect import get_dialect_profile, list_supported_dialects

# Get specific profile
us_profile = get_dialect_profile("en-US")
print(f"Medical terms: {us_profile.medical_term_variations}")

# List all dialects
all_dialects = list_supported_dialects()
english_dialects = list_supported_dialects(Language.ENGLISH)```

## Medical Terminology Variations

### Drug Names
- **Epinephrine/Adrenaline**: US/CA use "epinephrine", UK/AU use "adrenaline"
- **Acetaminophen/Paracetamol**: US/CA use "acetaminophen", UK/AU use "paracetamol"
- **Albuterol/Salbutamol**: US uses "albuterol", others use "salbutamol"

### Healthcare Facilities
- **Emergency Department**: US "emergency room/ER", UK "A&E", AU "emergency department"
- **Primary Care**: US "primary care physician", UK/AU "GP", CA "family doctor"
- **Pharmacy**: US "pharmacy/drugstore", UK "chemist", others "pharmacy"

### Medical Procedures
- **Surgery Location**: US "operating room/OR", UK "operating theatre"
- **Childbirth**: US "labor and delivery", UK "labour ward"
- **Immunizations**: US "shots/vaccinations", UK "jabs/immunisations"

## Confidence Levels

The system provides five confidence levels:
- **VERY_HIGH** (>0.9): Clear dialect identification with strong indicators
- **HIGH** (>0.7): Good confidence with multiple supporting features
- **MEDIUM** (>0.5): Moderate confidence, some ambiguity
- **LOW** (>0.3): Low confidence, significant ambiguity
- **VERY_LOW** (≤0.3): Minimal confidence, unclear dialect

## Performance Optimization

### Caching
The detector supports result caching to improve performance for repeated texts:
```python
detector = DialectDetector(cache_results=True)
```

### AI Enhancement
Enable AI-based refinement for improved accuracy:
```python
detector = DialectDetector(use_ai_detection=True)
```

## Integration with Translation Pipeline

The dialect detection system integrates seamlessly with the translation pipeline:
```python
# Detect dialect
dialect_result = detector.detect(source_text, source_language)
# Use dialect information for translation
profile = get_dialect_profile(dialect_result.detected_dialect)

# Apply dialect-specific terminology
translated_text = translator.translate(
    source_text,
    target_dialect=dialect_result.detected_dialect,
    medical_variations=profile.medical_term_variations
)
```

## Error Handling

The system handles various error cases gracefully:
- Empty or invalid text returns low confidence result
- Missing dialect profiles fall back to base language
- AI detection failures fall back to rule-based detection
- Caching errors are logged but don't affect detection

## Testing

Comprehensive test suite included:
```bash
pytest tests/ai/translation/dialect/test_dialect_detection.py -v
```

Test coverage includes:
- Basic dialect detection for all supported dialects
- Medical-specific detection
- Feature extraction validation
- Edge cases (empty text, mixed dialects, short text)
- Performance benchmarks

## Examples

See `examples.py` for detailed usage examples:
```bash
python src/ai/translation/dialect/examples.py
```

Examples demonstrate:
- Basic dialect detection
- Medical dialect detection
- Feature extraction
- Dialect profile usage
- Mixed dialect handling

## Future Enhancements

Planned improvements:
- Additional dialect support (Indian English, South African English)
- More medical specialty terminology
- Improved phonetic analysis
- Machine learning model training
- Real-time dialect adaptation
