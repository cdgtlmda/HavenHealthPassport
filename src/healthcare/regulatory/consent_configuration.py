"""Consent Management Configuration.

This module defines configuration settings for the consent management system
including templates, policies, and jurisdictional requirements.

All patient data access requires appropriate permission and role-based access control.
"""

from datetime import timedelta
from typing import List, Optional

from src.healthcare.regulatory.consent_management import (
    ConsentMethod,
    ConsentScope,
    ConsentType,
)


class ConsentConfiguration:
    """Configuration for consent management system."""

    # Consent validity periods by type
    CONSENT_VALIDITY_PERIODS = {
        ConsentType.GENERAL_HEALTHCARE: timedelta(days=365),  # 1 year
        ConsentType.EMERGENCY_CARE: timedelta(days=90),  # 90 days
        ConsentType.RESEARCH: None,  # Study-specific
        ConsentType.DATA_SHARING: timedelta(days=730),  # 2 years
        ConsentType.MARKETING: timedelta(days=365),  # 1 year
        ConsentType.COOKIES: timedelta(days=365),  # 1 year
        ConsentType.THIRD_PARTY: timedelta(days=365),  # 1 year
        ConsentType.INTERNATIONAL_TRANSFER: timedelta(days=730),  # 2 years
        ConsentType.AUTOMATED_PROCESSING: timedelta(days=365),  # 1 year
        ConsentType.SPECIAL_CATEGORY: timedelta(days=365),  # 1 year
        ConsentType.CHILD_DATA: timedelta(days=365),  # 1 year
        ConsentType.BIOMETRIC: timedelta(days=1825),  # 5 years
        ConsentType.GENETIC: timedelta(days=3650),  # 10 years
    }

    # Renewal requirements
    CONSENT_RENEWAL_REQUIRED = {
        ConsentType.GENERAL_HEALTHCARE: True,
        ConsentType.EMERGENCY_CARE: False,
        ConsentType.RESEARCH: False,
        ConsentType.DATA_SHARING: True,
        ConsentType.MARKETING: True,
        ConsentType.COOKIES: True,
        ConsentType.THIRD_PARTY: True,
        ConsentType.INTERNATIONAL_TRANSFER: True,
        ConsentType.AUTOMATED_PROCESSING: True,
        ConsentType.SPECIAL_CATEGORY: True,
        ConsentType.CHILD_DATA: True,
        ConsentType.BIOMETRIC: True,
        ConsentType.GENETIC: True,
    }

    # Renewal notice periods (days before expiry)
    RENEWAL_NOTICE_DAYS = {
        ConsentType.GENERAL_HEALTHCARE: 30,
        ConsentType.DATA_SHARING: 60,
        ConsentType.MARKETING: 30,
        ConsentType.INTERNATIONAL_TRANSFER: 90,
        ConsentType.BIOMETRIC: 90,
        ConsentType.GENETIC: 180,
    }

    # Methods allowed by consent type
    ALLOWED_CONSENT_METHODS = {
        ConsentType.GENERAL_HEALTHCARE: [
            ConsentMethod.WRITTEN,
            ConsentMethod.ELECTRONIC,
            ConsentMethod.VERBAL,
        ],
        ConsentType.EMERGENCY_CARE: [
            ConsentMethod.VERBAL,
            ConsentMethod.IMPLIED,
            ConsentMethod.EMERGENCY_OVERRIDE,
        ],
        ConsentType.RESEARCH: [ConsentMethod.WRITTEN, ConsentMethod.ELECTRONIC],
        ConsentType.GENETIC: [ConsentMethod.WRITTEN, ConsentMethod.ELECTRONIC],
        ConsentType.BIOMETRIC: [ConsentMethod.WRITTEN, ConsentMethod.ELECTRONIC],
    }

    # Minimum data retention after withdrawal (days)
    POST_WITHDRAWAL_RETENTION = {
        ConsentType.GENERAL_HEALTHCARE: 180,  # 6 months
        ConsentType.EMERGENCY_CARE: 365,  # 1 year
        ConsentType.RESEARCH: 0,  # Immediate deletion
        ConsentType.DATA_SHARING: 30,  # 30 days
        ConsentType.MARKETING: 0,  # Immediate deletion
        ConsentType.BIOMETRIC: 90,  # 90 days
        ConsentType.GENETIC: 365,  # 1 year
    }

    # Scope hierarchy (higher level includes lower levels)
    SCOPE_HIERARCHY = {
        ConsentScope.FULL_RECORD: [
            ConsentScope.BASIC_DEMOGRAPHIC,
            ConsentScope.MEDICAL_HISTORY,
            ConsentScope.CURRENT_CONDITIONS,
            ConsentScope.MEDICATIONS,
            ConsentScope.LAB_RESULTS,
            ConsentScope.IMAGING,
            ConsentScope.GENETIC_DATA,
            ConsentScope.MENTAL_HEALTH,
            ConsentScope.SUBSTANCE_USE,
            ConsentScope.SEXUAL_HEALTH,
        ],
        ConsentScope.MEDICAL_HISTORY: [
            ConsentScope.CURRENT_CONDITIONS,
            ConsentScope.MEDICATIONS,
        ],
    }

    # Age of consent by jurisdiction (in years)
    AGE_OF_CONSENT = {
        "default": 18,
        "US": {
            "default": 18,
            "AL": 19,  # Alabama
            "NE": 19,  # Nebraska
            "MS": 21,  # Mississippi (for certain medical decisions)
        },
        "EU": {
            "default": 16,
            "AT": 14,  # Austria
            "BE": 13,  # Belgium
            "BG": 14,  # Bulgaria
            "HR": 16,  # Croatia
            "CY": 14,  # Cyprus
            "CZ": 15,  # Czech Republic
            "DK": 13,  # Denmark
            "EE": 13,  # Estonia
            "FI": 13,  # Finland
            "FR": 15,  # France
            "DE": 16,  # Germany
            "GR": 15,  # Greece
            "HU": 16,  # Hungary
            "IE": 16,  # Ireland
            "IT": 14,  # Italy
            "LV": 13,  # Latvia
            "LT": 14,  # Lithuania
            "LU": 16,  # Luxembourg
            "MT": 13,  # Malta
            "NL": 16,  # Netherlands
            "PL": 16,  # Poland
            "PT": 13,  # Portugal
            "RO": 16,  # Romania
            "SK": 16,  # Slovakia
            "SI": 15,  # Slovenia
            "ES": 14,  # Spain
            "SE": 13,  # Sweden
        },
        "UK": 16,
        "CA": {
            "default": 16,
            "BC": 12,  # British Columbia (mature minor)
            "ON": 16,  # Ontario
            "QC": 14,  # Quebec
        },
        "AU": 16,
        "NZ": 16,
        "JP": 15,
        "KR": 14,
        "IN": 18,
        "CN": 14,
        "BR": 18,
        "MX": 18,
        "ZA": 12,  # South Africa (for certain medical decisions)
    }

    # Consent form languages required by region
    REQUIRED_LANGUAGES = {
        "US": ["en", "es"],
        "CA": ["en", "fr"],
        "CH": ["de", "fr", "it", "rm"],  # Switzerland
        "BE": ["nl", "fr", "de"],  # Belgium
        "LU": ["fr", "de", "lb"],  # Luxembourg
        "IN": ["en", "hi"],
        "ZA": ["en", "af", "zu", "xh"],  # South Africa
        "default": ["en"],
    }

    # Witness requirements
    WITNESS_REQUIREMENTS = {
        ConsentType.RESEARCH: {
            "required": True,
            "count": 1,
            "independent": True,
            "qualified": True,
        },
        ConsentType.GENETIC: {
            "required": True,
            "count": 1,
            "independent": True,
            "qualified": False,
        },
        ConsentType.BIOMETRIC: {
            "required": False,
            "count": 0,
            "independent": False,
            "qualified": False,
        },
    }

    # Notarization requirements by jurisdiction
    NOTARIZATION_REQUIRED = {
        "international_transfer": {
            "from_EU_to_non_adequate": True,
            "from_US_to_non_HIPAA": True,
            "default": False,
        },
        "genetic_testing": {"US": False, "EU": False, "default": False},
        "research": {"clinical_trials": True, "observational": False, "default": False},
    }

    # Special consent requirements
    SPECIAL_REQUIREMENTS = {
        "mature_minor": {
            "age_threshold": 12,
            "allowed_decisions": [
                "contraception",
                "mental_health",
                "substance_abuse",
                "sexual_health",
            ],
            "requires_assessment": True,
        },
        "emergency_override": {
            "allowed_scenarios": [
                "life_threatening",
                "unconscious_patient",
                "immediate_danger",
                "public_health_emergency",
            ],
            "documentation_required": True,
            "review_period_hours": 24,
        },
        "proxy_consent": {
            "allowed_relationships": [
                "parent",
                "legal_guardian",
                "healthcare_proxy",
                "power_of_attorney",
                "next_of_kin",
            ],
            "verification_required": True,
        },
    }

    # Consent audit requirements
    AUDIT_REQUIREMENTS = {
        "retention_period_years": 7,
        "include_access_logs": True,
        "include_modifications": True,
        "include_verification_checks": True,
        "encrypt_audit_logs": True,
        "tamper_evident": True,
    }

    # Consent form templates
    CONSENT_FORM_ELEMENTS = {
        "header": {
            "organization_name": True,
            "organization_logo": True,
            "form_title": True,
            "form_version": True,
            "effective_date": True,
        },
        "patient_information": {
            "full_name": True,
            "date_of_birth": True,
            "identification_number": False,
            "contact_information": True,
            "preferred_language": True,
        },
        "consent_details": {
            "purpose_statement": True,
            "data_categories": True,
            "data_recipients": True,
            "retention_period": True,
            "data_sources": True,
            "automated_processing": True,
            "international_transfers": True,
        },
        "rights_section": {
            "right_to_access": True,
            "right_to_rectification": True,
            "right_to_erasure": True,
            "right_to_restrict": True,
            "right_to_portability": True,
            "right_to_object": True,
            "right_to_withdraw": True,
            "complaint_process": True,
        },
        "signature_section": {
            "patient_signature": True,
            "patient_name_print": True,
            "date_signed": True,
            "witness_signature": False,
            "witness_name_print": False,
            "guardian_section": True,
        },
    }

    @classmethod
    def get_age_of_consent(
        cls, jurisdiction: str, sub_jurisdiction: Optional[str] = None
    ) -> int:
        """Get age of consent for jurisdiction.

        Args:
            jurisdiction: Main jurisdiction (country)
            sub_jurisdiction: Sub-jurisdiction (state/province)

        Returns:
            Age of consent in years
        """
        if jurisdiction in cls.AGE_OF_CONSENT:
            juris_data = cls.AGE_OF_CONSENT[jurisdiction]
            if isinstance(juris_data, dict):
                if sub_jurisdiction and sub_jurisdiction in juris_data:
                    age = juris_data[sub_jurisdiction]
                    return int(age) if isinstance(age, (int, str)) else 18
                default_age = juris_data.get("default", cls.AGE_OF_CONSENT["default"])
                return int(default_age) if isinstance(default_age, (int, str)) else 18
            return int(juris_data) if isinstance(juris_data, (int, str)) else 18
        default = cls.AGE_OF_CONSENT.get("default", 18)
        return int(default) if isinstance(default, (int, str)) else 18

    @classmethod
    def get_required_languages(cls, region: str) -> List[str]:
        """Get required consent form languages for region.

        Args:
            region: Region code

        Returns:
            List of required language codes
        """
        return cls.REQUIRED_LANGUAGES.get(region, cls.REQUIRED_LANGUAGES["default"])

    @classmethod
    def get_validity_period(cls, consent_type: ConsentType) -> timedelta:
        """Get default validity period for consent type.

        Args:
            consent_type: Type of consent

        Returns:
            Validity period as timedelta
        """
        validity = cls.CONSENT_VALIDITY_PERIODS.get(consent_type, timedelta(days=365))
        if validity is None:
            return timedelta(days=365)
        return validity

    @classmethod
    def requires_renewal(cls, consent_type: ConsentType) -> bool:
        """Check if consent type requires renewal.

        Args:
            consent_type: Type of consent

        Returns:
            Whether renewal is required
        """
        return cls.CONSENT_RENEWAL_REQUIRED.get(consent_type, True)

    @classmethod
    def get_allowed_methods(cls, consent_type: ConsentType) -> List[ConsentMethod]:
        """Get allowed consent methods for type.

        Args:
            consent_type: Type of consent

        Returns:
            List of allowed methods
        """
        return cls.ALLOWED_CONSENT_METHODS.get(
            consent_type, [ConsentMethod.WRITTEN, ConsentMethod.ELECTRONIC]
        )

    @classmethod
    def get_retention_after_withdrawal(cls, consent_type: ConsentType) -> int:
        """Get data retention period after consent withdrawal.

        Args:
            consent_type: Type of consent

        Returns:
            Retention period in days
        """
        return cls.POST_WITHDRAWAL_RETENTION.get(consent_type, 30)


# Export configuration
__all__ = ["ConsentConfiguration"]
