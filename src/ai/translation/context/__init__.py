"""Medical Context Preservation Package."""

from .context_aware_translation import (
    ContextAwareTranslationRequest,
    ContextAwareTranslationResult,
    ContextAwareTranslator,
    create_context_preserver,
)
from .context_extraction import MedicalContextExtractor
from .context_preservation import ContextPreserver, ContextValidator, PreservedContext
from .medical_context import (
    ClinicalContext,
    ClinicalStatus,
    ContextPreservationRule,
    MedicalEntity,
    MedicalRelationship,
    RelationType,
    TemporalExpression,
    TemporalType,
)

__version__ = "1.0.0"
