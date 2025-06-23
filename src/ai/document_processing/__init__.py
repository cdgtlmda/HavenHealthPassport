"""
Document Processing Module.

This module provides document analysis and extraction capabilities for the Haven Health
Passport system, including OCR, form recognition, and medical document processing.
"""

from .document_classification import (
    ClassificationConfidence,
    ClassificationMethod,
    ClassificationResult,
    ClassificationRule,
    DocumentClassifier,
    DocumentFeatures,
)
from .handwriting_recognition import (
    HandwritingAnalysisResult,
    HandwritingContext,
    HandwritingQuality,
    HandwritingRecognizer,
    HandwritingType,
    HandwrittenText,
)
from .layout_analysis import (
    BoundingBox,
    DocumentLayout,
    DocumentLayoutAnalyzer,
    LayoutElement,
    LayoutElementType,
)
from .medical_form_recognition import (
    ExtractedFormField,
    FormFieldMapping,
    FormFieldType,
    MedicalFormData,
    MedicalFormRecognizer,
    MedicalFormType,
)
from .multilanguage_ocr import (
    LanguageConfig,
    MultiLanguageOCR,
    OCRResult,
    SupportedLanguage,
    TextBlock,
)
from .quality_enhancement import (
    DocumentQualityEnhancer,
    EnhancementParameters,
    EnhancementResult,
    EnhancementType,
    QualityLevel,
    QualityMetrics,
)
from .textract_config import (
    DocumentAnalysisResult,
    DocumentType,
    ExtractedForm,
    ExtractedTable,
    ExtractedText,
    ExtractionConfidence,
    FeatureType,
    TextractClient,
    TextractConfig,
)

__all__ = [
    # Textract Configuration
    "TextractConfig",
    "TextractClient",
    "DocumentType",
    "DocumentAnalysisResult",
    "ExtractedText",
    "ExtractedForm",
    "ExtractedTable",
    "ExtractionConfidence",
    "FeatureType",
    # Medical Form Recognition
    "MedicalFormRecognizer",
    "MedicalFormType",
    "MedicalFormData",
    "FormFieldType",
    "ExtractedFormField",
    "FormFieldMapping",
    # Handwriting Recognition
    "HandwritingRecognizer",
    "HandwritingType",
    "HandwritingQuality",
    "HandwritingContext",
    "HandwrittenText",
    "HandwritingAnalysisResult",
    # Multi-Language OCR
    "MultiLanguageOCR",
    "SupportedLanguage",
    "LanguageConfig",
    "OCRResult",
    "TextBlock",
    # Document Classification
    "DocumentClassifier",
    "ClassificationResult",
    "ClassificationMethod",
    "ClassificationConfidence",
    "DocumentFeatures",
    "ClassificationRule",
    # Quality Enhancement
    "DocumentQualityEnhancer",
    "EnhancementType",
    "QualityLevel",
    "QualityMetrics",
    "EnhancementParameters",
    "EnhancementResult",
    # Layout Analysis
    "DocumentLayoutAnalyzer",
    "LayoutElementType",
    "BoundingBox",
    "LayoutElement",
    "DocumentLayout",
]
