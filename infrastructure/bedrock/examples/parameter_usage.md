# Bedrock Model Inference Parameters - Usage Guide

## Overview
The inference parameter system provides optimized configurations for different use cases in the Haven Health Passport application.

## Parameter Categories

### Base Parameters (by Model Family)
- **Claude**: Optimized for conversational AI and analysis
- **Titan**: Optimized for translation and embeddings
- **Embedding**: Specialized for vector generation

### Medical Use Cases
- **medical_analysis**: Low temperature (0.2), high accuracy
- **medical_translation**: Terminology preservation, back-translation checks
- **voice_transcription**: Accent handling, medical vocabulary
- **document_extraction**: Layout preservation, high OCR confidence

### Context Profiles
- **emergency**: Speed-optimized, shorter responses
- **detailed_analysis**: Accuracy-focused, multi-pass processing
- **cost_optimized**: Balanced performance, caching enabled

## API Usage
```json
{
    "model_family": "claude",
    "use_case": "medical_analysis",
    "profile": "detailed_analysis",
    "format_for_model": true
}
```

## Safety Features
1. Medical use cases automatically cap temperature at 0.3
2. Token limits enforced based on environment
3. Confidence thresholds elevated for healthcare content
4. Required parameters cannot be overridden for compliance

## Integration
The parameter selector Lambda function automatically:
- Merges base, use-case, and profile parameters
- Applies safety validations
- Formats parameters for specific model APIs
- Logs all parameter selections for audit
