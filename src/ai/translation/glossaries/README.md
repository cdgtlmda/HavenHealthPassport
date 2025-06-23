# Medical Translation Glossaries

This directory contains the comprehensive medical terminology glossary system for the Haven Health Passport translation pipeline.

## Overview

The glossary system ensures accurate medical translations by:
- Preserving critical medical terminology
- Maintaining medical accuracy across 50+ languages
- Adapting content for cultural contexts
- Validating translation quality

## Components

### 1. Base Glossary (`base_glossary.py`)
- Core medical term management
- Term categorization and prioritization
- Placeholder-based preservation system
- Unit and regulatory term handling

### 2. Domain Glossaries (`domain_glossaries.py`)
Specialized glossaries for:
- Cardiology
- Oncology
- Pediatrics
- Emergency Medicine
- Infectious Disease
- Mental Health

### 3. Multilingual Glossary (`multilingual_glossary.py`)
- 50+ language support
- Cultural context adaptation
- Medical accuracy validation
- Measurement conversions

### 4. Integrated Manager (`glossary_manager.py`)
- Unified access to all glossaries
- Translation workflow management
- Quality validation
- Import/export functionality

## Usage

```python
from src.ai.translation.glossaries import glossary_manager, data_loader

# Load pre-populated data
data_loader.load_all_data(glossary_manager)

# Prepare text for translation
text = "Patient has severe chest pain, needs 500mg aspirin STAT"
prepared, preservation_map = glossary_manager.prepare_text_for_translation(
    text, source_lang="en", target_lang="es"
)

# After translation, restore preserved terms
translated = "Paciente tiene dolor de pecho severo..."
final = glossary_manager.restore_preserved_terms(
    translated, preservation_map
)

# Validate translation quality
validation = await glossary_manager.validate_translation_quality(
    text, final, "en", "es"
)
```

## Term Categories

- **CRITICAL**: Must never be mistranslated (e.g., "emergency", "cardiac arrest")
- **HIGH**: Should preserve exact form (e.g., "MRI", "aspirin")
- **MEDIUM**: Can adapt with care (e.g., "mild pain", "tablet")
- **LOW**: Can be translated normally

## Supported Languages

Major languages:
- English, Spanish, French, Arabic, Chinese
- Hindi, Portuguese, Russian, Japanese, German

Common refugee languages:
- Persian/Farsi, Pashto, Urdu, Somali
- Amharic, Tigrinya, Swahili, Hausa

And 35+ additional languages...

## Data Files

Pre-populated glossaries in `data/`:
- `emergency_pain_terms.json`: Emergency and pain terminology
- `body_parts.json`: Anatomical terms
- `medications.json`: Common medications and instructions

## Testing

```bash
# Run glossary tests
pytest tests/ai/translation/glossaries/test_glossaries.py -v

# Test data integrity
python -m src.ai.translation.glossaries.data validate
```

## Adding Custom Terms

```python
from src.ai.translation.glossaries import MedicalTerm, TermCategory, TermPriority

# Add custom term
term = MedicalTerm(
    term="COVID-19",
    category=TermCategory.DISEASE,
    priority=TermPriority.HIGH,
    aliases=["coronavirus", "SARS-CoV-2"],
    preserve_exact=True
)

glossary_manager.base_glossary.add_custom_term(term)

# Add translation
glossary_manager.multilingual_glossary.add_translation(
    "COVID-19", "es", ["COVID-19", "coronavirus"], verified=True
)
```

## Performance Considerations

- Terms are cached for fast lookup
- Async validation for better performance
- Configurable preservation thresholds
- Batch processing support

## Integration with Translation Pipeline

The glossary system integrates seamlessly with:
- LangChain translation chains
- Amazon Bedrock models
- Quality assurance systems
- Offline translation fallbacks

## Compliance

- HIPAA-compliant term handling
- PHI protection in preserved terms
- Audit trails for term modifications
- Secure export/import procedures
