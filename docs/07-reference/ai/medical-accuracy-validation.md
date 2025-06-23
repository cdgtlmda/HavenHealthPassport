# Medical Accuracy Validation

## Overview

The medical accuracy validation system ensures that critical medical information is preserved and accurately translated. This is essential for patient safety and regulatory compliance in healthcare translations.

## Features

### Medical Entity Extraction
- **Medications**: Drug names, both generic and brand
- **Dosages**: Numeric values with units (mg, g, mcg, ml, etc.)
- **Frequencies**: Dosing schedules (BID, TID, daily, etc.)
- **Diagnoses**: Medical conditions and ICD-10 codes
- **Lab Values**: Test results with units and ranges
- **Vital Signs**: Blood pressure, heart rate, temperature
- **Allergies**: Drug and substance allergies
- **Medical Codes**: ICD-10, CPT, SNOMED CT codes

### Accuracy Levels

1. **CRITICAL**: For life-critical information
   - 100% preservation of critical entities required
   - Zero tolerance for medication/allergy errors

2. **HIGH**: For important medical data
   - 95% accuracy threshold
   - Warnings for non-critical discrepancies

3. **STANDARD**: For general medical information
   - 90% accuracy threshold
   - More lenient validation

## Integration

The medical accuracy validator is integrated into the translation validation pipeline:

```python
from src.ai.translation.validation import ValidationConfig, ValidationLevel

config = ValidationConfig(
    level=ValidationLevel.STRICT,
    validate_medical_accuracy=True
)
```

## Entity Matching

The system uses sophisticated matching algorithms:

### Medication Matching
- Generic/brand name equivalence
- Common abbreviations (ASA = aspirin)
- Partial name matching

### Dosage Matching
- Unit normalization (mg = milligrams)
- Numeric precision handling
- Concentration equivalence

### Code Matching
- ICD-10 validation
- Format normalization
- Version compatibility

## Validation Process

1. **Entity Extraction**: Identifies medical entities in source text
2. **Translation Scanning**: Finds corresponding entities in translation
3. **Matching**: Determines if entities are preserved/equivalent
4. **Scoring**: Calculates accuracy metrics
5. **Reporting**: Generates detailed validation results

## Error Detection

The system detects:
- Missing critical entities (medications, allergies)
- Altered dosages or frequencies
- Lost medical codes
- Negation errors (no/not preservation)
- Safety term omissions

## Usage Example

```python
from src.ai.translation.validation.medical_accuracy import MedicalAccuracyValidator

validator = MedicalAccuracyValidator()
result = validator.validate_medical_accuracy(
    source_text="Patient allergic to penicillin. Prescribe azithromycin 500mg.",
    translated_text="Paciente alérgico a penicilina. Prescribir azitromicina 500mg.",
    accuracy_level=MedicalAccuracyLevel.HIGH
)

print(f"Accuracy: {result.accuracy_score:.2%}")
print(f"Critical entities preserved: {result.critical_entities_preserved}/{result.critical_entities_total}")
```

## Configuration

Customize validation behavior:

```python
# In ValidationConfig
verify_dosage_accuracy=True      # Strict dosage checking
check_drug_interactions=True      # Validate interaction warnings
check_allergy_info=True          # Ensure allergy preservation
require_term_preservation=True    # Medical terminology must match
```

## Best Practices

1. Use CRITICAL level for:
   - Prescription information
   - Allergy documentation
   - Dosing instructions
   - Emergency protocols

2. Use HIGH level for:
   - Diagnostic reports
   - Clinical notes
   - Lab results
   - Treatment plans

3. Use STANDARD level for:
   - General health information
   - Educational materials
   - Non-clinical content

## Limitations

- Requires medical entity recognition models
- Language-specific medical terminology databases needed
- May not catch subtle semantic changes
- Limited to pattern-based extraction

## Future Enhancements

1. ML-based entity recognition
2. Semantic equivalence checking
3. Drug interaction validation
4. Clinical guideline compliance
5. Multi-language medical dictionaries
