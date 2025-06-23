"""FHIR extensions for refugee healthcare.

Compliance Notes:
- FHIR: All extensions implement FHIR DomainResource compliant structures
- PHI Protection: Extensions containing patient data use encryption for sensitive fields
- Audit Logging: Extension usage is tracked for compliance auditing
"""

# Import access control for PHI protection
from src.healthcare.hipaa_access_control import AccessLevel, require_phi_access

from .camp_settlement import CampSettlementExtension
from .cross_border_access import CrossBorderAccessExtension
from .cultural_context import CulturalContextExtension
from .displacement_date import DisplacementDateExtension
from .multi_language_name import MultiLanguageNameExtension
from .refugee_status import RefugeeStatusExtension
from .unhcr_registration import UNHCRRegistrationExtension
from .verification_status import VerificationStatusExtension

__all__ = [
    "RefugeeStatusExtension",
    "DisplacementDateExtension",
    "CampSettlementExtension",
    "UNHCRRegistrationExtension",
    "MultiLanguageNameExtension",
    "VerificationStatusExtension",
    "CrossBorderAccessExtension",
    "CulturalContextExtension",
]
