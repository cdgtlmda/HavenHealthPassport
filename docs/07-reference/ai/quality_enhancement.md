# Document Quality Enhancement Module

## Overview

The Document Quality Enhancement module provides advanced image preprocessing capabilities to improve the quality of medical documents before OCR processing. It automatically detects quality issues and applies appropriate enhancements to maximize text extraction accuracy.

## Features

- **Automatic Quality Assessment**: Analyzes documents for quality issues
- **Multi-Enhancement Pipeline**: Applies multiple enhancement techniques
- **Document-Type Optimization**: Tailors enhancements based on document type
- **Real-time Processing**: Fast enhancement for immediate results
- **Quality Metrics**: Detailed before/after quality measurements

## Enhancement Types

### 1. Brightness Correction
- Adjusts under/over-exposed documents
- Normalizes lighting variations
- Preserves text contrast

### 2. Contrast Enhancement
- Uses CLAHE (Contrast Limited Adaptive Histogram Equalization)
- Improves text visibility
- Handles uneven lighting

### 3. Sharpness Enhancement
- Unsharp masking for clearer text
- Reduces blur from poor scans
- Configurable intensity

### 4. Noise Reduction
- Removes scan artifacts
- Reduces graininess
- Preserves text edges

### 5. Deskew Correction
- Automatically detects document rotation
- Corrects skewed scans
- Maintains aspect ratio

### 6. Shadow Removal
- Eliminates shadows from photos
- Normalizes background
- Improves OCR accuracy

### 7. Text Enhancement
- Optimizes specifically for text
- Improves character definition
- Reduces background interference

### 8. Binarization
- Converts to pure black/white
- Ideal for text-only documents
- Maximum OCR accuracy

## Usage

```python
from src.ai.document_processing import DocumentQualityEnhancer

# Initialize enhancer
enhancer = DocumentQualityEnhancer(
    audit_logger=audit_logger,
    metrics_collector=metrics_collector
)

# Automatic enhancement
result = await enhancer.enhance_document(image_data)

# Custom enhancement
params = EnhancementParameters(
    enhancement_types=[EnhancementType.CONTRAST, EnhancementType.DENOISE],
    contrast_factor=1.5,
    denoise_strength=10
)
result = await enhancer.enhance_document(image_data, params=params)

# Check results
print(f"Quality improved: {result.improvement_score:.2%}")
print(f"Operations applied: {result.operations_applied}")
```

## Quality Metrics

The module assesses documents using multiple metrics:

- **Brightness Score**: 0-1 (optimal ~0.6)
- **Contrast Score**: 0-1 (higher is better)
- **Sharpness Score**: 0-1 (higher is better)
- **Noise Level**: 0-1 (lower is better)
- **Text Clarity**: 0-1 (higher is better)
- **Overall Quality**: EXCELLENT, GOOD, FAIR, POOR, VERY_POOR

## Performance

- Average processing time: 200-500ms per document
- Supports images up to 10000x10000 pixels
- Memory efficient processing
- GPU acceleration ready (when available)

## Best Practices

1. **Let Auto-Enhancement Decide**: The automatic mode usually produces best results
2. **Document-Specific Settings**: Use document type hints for optimization
3. **Preserve Originals**: Always keep original images for reference
4. **Monitor Quality Metrics**: Track improvement scores over time
5. **Batch Processing**: Process similar documents together

## Integration with OCR Pipeline

```python
# Complete OCR pipeline with enhancement
async def process_document(image_data):
    # 1. Enhance quality
    enhancement_result = await enhancer.enhance_document(image_data)

    # 2. Perform OCR on enhanced image
    ocr_result = await textract_client.analyze_document(
        enhancement_result.enhanced_image
    )

    # 3. Return results with quality metrics
    return {
        'text': ocr_result.text,
        'quality_improvement': enhancement_result.improvement_score,
        'original_quality': enhancement_result.original_metrics.overall_quality
    }
```

## Configuration

Default parameters can be customized:

```python
params = EnhancementParameters(
    contrast_factor=1.2,        # Contrast multiplier
    brightness_factor=1.1,      # Brightness multiplier
    sharpness_factor=1.5,       # Sharpness intensity
    denoise_strength=5,         # Noise reduction (1-20)
    deskew_threshold=0.5,       # Minimum angle for correction
    binarization_threshold=128, # Binary threshold
    target_dpi=300,            # Target resolution
    enable_shadow_removal=True, # Remove shadows
    preserve_color=False       # Keep color information
)
```

## Error Handling

The module gracefully handles various error conditions:
- Invalid image formats
- Corrupted image data
- Processing failures
- Memory constraints

On error, the original image is returned with appropriate error messages.

## Testing

Comprehensive test coverage includes:
- Unit tests for each enhancement type
- Integration tests with OCR pipeline
- Performance benchmarks
- Quality metric validation

Run tests:
```bash
pytest tests/ai/document_processing/test_quality_enhancement.py
```

## Future Enhancements

- Deep learning-based super-resolution
- Document-specific ML models
- Real-time quality feedback
- Batch optimization algorithms
- Mobile device optimization
