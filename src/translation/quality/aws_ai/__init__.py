"""AWS AI Services Integration for Medical Translation Quality."""

from .comprehend_medical import (
    ComprehendMedicalValidator,
    EntityCategory,
    EntityType,
    MedicalEntity,
    ValidationResult,
    get_comprehend_validator,
)
from .comprehend_tone import (
    ComprehendTonePreserver,
    EmotionalTone,
    Sentiment,
    SentimentAnalysis,
    TonePreservationResult,
    get_tone_preserver,
)
from .healthlake_reference import (
    ClinicalConcept,
    CrossReferenceResult,
    HealthLakeCrossReference,
    ResourceType,
    get_healthlake_reference,
)
from .rekognition_medical import (
    AnnotationType,
    ImageAnalysisResult,
    ImageAnnotation,
    ImageTranslationResult,
    ImageType,
    RekognitionMedicalTranslator,
    get_rekognition_translator,
)
from .textract_medical import (
    TextractMedicalProcessor,
    get_textract_processor,
)

__all__ = [
    # Comprehend Medical
    "ComprehendMedicalValidator",
    "EntityType",
    "EntityCategory",
    "MedicalEntity",
    "ValidationResult",
    "get_comprehend_validator",
    # HealthLake
    "HealthLakeCrossReference",
    "ClinicalConcept",
    "CrossReferenceResult",
    "ResourceType",
    "get_healthlake_reference",
    # Comprehend Tone
    "ComprehendTonePreserver",
    "Sentiment",
    "EmotionalTone",
    "SentimentAnalysis",
    "TonePreservationResult",
    "get_tone_preserver",
    # Rekognition Medical
    "RekognitionMedicalTranslator",
    "ImageType",
    "AnnotationType",
    "ImageAnnotation",
    "ImageAnalysisResult",
    "ImageTranslationResult",
    "get_rekognition_translator",
    # Textract Medical
    "TextractMedicalProcessor",
    "get_textract_processor",
]
