"""Cultural Adaptation Package."""

from .adaptation_rules import (
    AdaptationResult,
    AdaptationRule,
    AdaptationType,
    CulturalAdaptationEngine,
    cultural_adapter,
)
from .cultural_integration import (
    CulturallyAdaptedTranslationRequest as CulturalTranslationRequest,
)
from .cultural_integration import (
    CulturallyAdaptedTranslationResult as CulturalTranslationResult,
)
from .cultural_integration import (
    CulturalTranslationPipeline,
)
from .cultural_profiles import (
    AuthorityRelation,
    CommunicationStyle,
    CulturalProfile,
    CulturalProfileManager,
    HealthcareBelief,
    PrivacyLevel,
    ReligiousConsiderations,
    TimeOrientation,
)
from .healthcare_systems import (
    HealthcareSystem,
    HealthcareSystemAdapter,
)

__version__ = "1.0.0"

__all__ = [
    "AdaptationType",
    "AdaptationRule",
    "AdaptationResult",
    "CulturalAdaptationEngine",
    "cultural_adapter",
    "CulturalTranslationRequest",
    "CulturalTranslationResult",
    "CulturalTranslationPipeline",
    "CommunicationStyle",
    "AuthorityRelation",
    "PrivacyLevel",
    "TimeOrientation",
    "ReligiousConsiderations",
    "HealthcareBelief",
    "CulturalProfile",
    "CulturalProfileManager",
    "HealthcareSystem",
    "HealthcareSystemAdapter",
]
