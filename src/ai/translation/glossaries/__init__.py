"""
Medical Translation Glossaries Package.

This package provides comprehensive medical terminology glossaries
for accurate healthcare translation across 50+ languages.
"""

from .base_glossary import (
    MedicalGlossary,
    MedicalTerm,
    TermCategory,
    TermPriority,
    TranslationMapping,
)
from .domain_glossaries import (
    CardiologyGlossary,
    EmergencyMedicineGlossary,
    GlossaryFactory,
    InfectiousDiseaseGlossary,
    MentalHealthGlossary,
    OncologyGlossary,
    PediatricsGlossary,
)
from .glossary_manager import GlossaryMatch, IntegratedGlossaryManager, glossary_manager
from .multilingual_glossary import (
    SUPPORTED_LANGUAGES,
    CulturalContext,
    LanguageVariant,
    MultilingualMedicalGlossary,
)

__all__ = [
    # Base classes
    "MedicalGlossary",
    "MedicalTerm",
    "TermCategory",
    "TermPriority",
    "TranslationMapping",
    # Domain glossaries
    "CardiologyGlossary",
    "OncologyGlossary",
    "PediatricsGlossary",
    "EmergencyMedicineGlossary",
    "InfectiousDiseaseGlossary",
    "MentalHealthGlossary",
    "GlossaryFactory",
    # Multilingual support
    "MultilingualMedicalGlossary",
    "SUPPORTED_LANGUAGES",
    "LanguageVariant",
    "CulturalContext",
    # Manager
    "IntegratedGlossaryManager",
    "GlossaryMatch",
    "glossary_manager",
]

__version__ = "1.0.0"
