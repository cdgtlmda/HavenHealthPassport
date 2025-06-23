"""Medical Terminology Module.

Handles medical acronyms, abbreviations, and terminology mapping.
"""

from .acronym_expander import MedicalAcronymExpander as AcronymExpander
from .icd10_mapper import ICD10Mapper, create_icd10_mapper
from .rxnorm_mapper import RxNormMapper, create_rxnorm_mapper
from .snomed_ct_integration import SnomedCTIntegration, create_snomed_ct_integration

__all__ = [
    "AcronymExpander",
    "ICD10Mapper",
    "create_icd10_mapper",
    "SnomedCTIntegration",
    "create_snomed_ct_integration",
    "RxNormMapper",
    "create_rxnorm_mapper",
]
