"""
Translation Quality Enhancement Module.

This module provides comprehensive quality assurance and enhancement
capabilities for medical translations in the Haven Health Passport system.
"""

# AWS AI Services
from .aws_ai import (  # Comprehend Medical; HealthLake; Comprehend Tone; Rekognition; Textract
    ComprehendMedicalValidator,
    ComprehendTonePreserver,
    HealthLakeCrossReference,
    RekognitionMedicalTranslator,
    TextractMedicalProcessor,
    get_comprehend_validator,
    get_healthlake_reference,
    get_rekognition_translator,
    get_textract_processor,
    get_tone_preserver,
)

# Continuous Learning
from .continuous_learning import (
    ABTestExperiment,
    ContinuousLearningPipeline,
    ExperimentStatus,
    LearningOutcome,
    MetricType,
    ModelType,
    QualityMetrics,
    TranslationFeedback,
    get_learning_pipeline,
)

# Cultural Adaptation
try:
    from .cultural_adaptation_ai import (
        CommunicationStyle,
        CulturalAdaptationAI,
        CulturalAdaptationResult,
        CulturalContext,
        CulturalPattern,
        OffensiveContentResult,
        SensitivityLevel,
        get_cultural_adaptation_ai,
    )

    _CULTURAL_ADAPTATION_AVAILABLE = True
except ImportError as e:
    # Log but don't fail - cultural adaptation may work with fallback methods
    import logging

    logger = logging.getLogger(__name__)
    logger.warning(
        "Cultural adaptation module loaded with limited functionality: %s. "
        "Install spacy for full NLP capabilities: pip install -r requirements-ml-nlp.txt",
        e,
    )
    # Still import what we can
    from .cultural_adaptation_ai import (
        CommunicationStyle,
        CulturalAdaptationAI,
        CulturalAdaptationResult,
        CulturalContext,
        CulturalPattern,
        OffensiveContentResult,
        SensitivityLevel,
        get_cultural_adaptation_ai,
    )

    _CULTURAL_ADAPTATION_AVAILABLE = True

__all__ = [
    # AWS AI Services
    "ComprehendMedicalValidator",
    "get_comprehend_validator",
    "HealthLakeCrossReference",
    "get_healthlake_reference",
    "ComprehendTonePreserver",
    "get_tone_preserver",
    "RekognitionMedicalTranslator",
    "get_rekognition_translator",
    "TextractMedicalProcessor",
    "get_textract_processor",
    # Cultural Adaptation
    "CulturalAdaptationAI",
    "CulturalContext",
    "CommunicationStyle",
    "SensitivityLevel",
    "CulturalPattern",
    "CulturalAdaptationResult",
    "OffensiveContentResult",
    "get_cultural_adaptation_ai",
    # Continuous Learning
    "ContinuousLearningPipeline",
    "ExperimentStatus",
    "MetricType",
    "ModelType",
    "TranslationFeedback",
    "ABTestExperiment",
    "QualityMetrics",
    "LearningOutcome",
    "get_learning_pipeline",
]
