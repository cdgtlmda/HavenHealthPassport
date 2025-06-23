# Medical Context Preservation System

This module provides comprehensive context preservation for medical translation, ensuring that clinical meaning, relationships, and temporal sequences are maintained across languages.

## Overview

The context preservation system identifies and preserves:
- Medical entities and their attributes (negation, severity, status)
- Relationships between medical concepts (causes, treats, indicates)
- Temporal sequences and medication instructions
- Clinical narrative structure
- Urgency levels and clinical settings

## Components

### 1. Medical Context Model (`medical_context.py`)
- `MedicalEntity`: Represents medical concepts with attributes
- `MedicalRelationship`: Captures relationships between entities
- `TemporalExpression`: Handles time-related information
- `ClinicalContext`: Complete clinical context representation

### 2. Context Extraction (`context_extraction.py`)
- Extracts medical entities using glossary matching
- Identifies relationships through pattern matching
- Detects temporal expressions and sequences
- Determines clinical urgency and setting
- Integrates with negation detection and temporal reasoning

### 3. Context Preservation (`context_preservation.py`)
- Preserves entities with semantic placeholders
- Maintains relationship annotations
- Preserves temporal markers
- Validates preservation integrity

### 4. Context-Aware Translation (`context_aware_translation.py`)
- Integrates with translation pipeline
- Coordinates glossary and context preservation
- Validates translation quality
- Provides specialized preservers for different domains

## Usage

```python
from src.ai.translation.context import ContextAwareTranslator, ContextAwareTranslationRequest

# Create translator
translator = ContextAwareTranslator()

# Create request
request = ContextAwareTranslationRequest(
    text="Patient has severe chest pain radiating to left arm. Give aspirin 325mg STAT.",
    source_lang="en",
    target_lang="es",
    medical_domain="emergency"
)

# Translate with context preservation
result = await translator.translate_with_context(request, translation_function)

print(f"Quality score: {result.quality_score}")
print(f"Preserved entities: {result.metadata['entities_preserved']}")
print(f"Urgency: {result.metadata['urgency_level']}")
```

## Key Features

### Entity Preservation
- Preserves medical terms with their attributes
- Handles negation: "no fever" → preserved as negated entity
- Maintains severity: "severe pain" → severity attribute preserved
- Tracks clinical status: active, resolved, suspected, chronic

### Relationship Preservation
- Medication → Indication: "aspirin for pain"
- Medication → Dosage: "aspirin 325mg"
- Symptom → Disease: "chest pain indicates MI"
- Contraindications: "allergy contraindicates penicillin"

### Temporal Preservation
- Absolute times: "at 10:30 AM"
- Relative times: "2 hours ago"
- Durations: "for 3 days"
- Frequencies: "twice daily"
- Sequences: "take before meals"

### Clinical Context
- Chief complaint identification
- History of present illness
- Clinical impressions
- Treatment plans
- Urgency detection (normal, high, critical)

## Domain-Specific Preservers

### Emergency Context
```python
preserver = create_context_preserver("emergency")
# More aggressive preservation
# Adds emergency markers
# Preserves all numbers and times
```

### Pediatric Context
```python
preserver = create_context_preserver("pediatrics")
# Preserves growth data
# Special handling for age/weight
# Vaccine schedule preservation
```

## Validation

The system validates:
- Entity coverage (>90% of entities preserved)
- Relationship integrity
- Temporal consistency
- Critical term preservation
- Clinical logic validation

## Integration

Works seamlessly with:
- Glossary matching system
- Translation pipeline
- Quality assurance
- Medical NLP components

## Performance

- Efficient extraction using optimized matchers
- Caching for repeated patterns
- Async processing support
- Minimal overhead on translation

## Testing

```bash
pytest tests/ai/translation/context/test_context.py -v
```
