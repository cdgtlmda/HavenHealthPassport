"""GDPR Compliance Configuration.

This module configures GDPR compliance settings for international healthcare
data protection requirements.
"""

import logging
import uuid
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class GDPRJurisdiction(Enum):
    """GDPR jurisdictions and adequacy decisions."""

    # EU Countries (Sample)
    EU = "european_union"
    GERMANY = "germany"
    FRANCE = "france"
    ITALY = "italy"
    SPAIN = "spain"
    NETHERLANDS = "netherlands"
    BELGIUM = "belgium"
    POLAND = "poland"
    SWEDEN = "sweden"

    # Adequate Countries
    UK = "united_kingdom"
    SWITZERLAND = "switzerland"
    JAPAN = "japan"
    CANADA = "canada"


class TransferMechanism(Enum):
    """Legal mechanisms for international transfers."""

    ADEQUACY_DECISION = "adequacy_decision"
    STANDARD_CONTRACTUAL_CLAUSES = "standard_contractual_clauses"
    BINDING_CORPORATE_RULES = "binding_corporate_rules"
    EXPLICIT_CONSENT = "explicit_consent"
    VITAL_INTERESTS = "vital_interests"
    PUBLIC_INTEREST = "public_interest"
    LEGAL_CLAIMS = "legal_claims"
    DEROGATION = "derogation"


class DataCategory(Enum):
    """Categories of personal data under GDPR."""

    # Regular personal data
    IDENTIFICATION = "identification_data"
    CONTACT = "contact_data"
    PROFESSIONAL = "professional_data"
    FINANCIAL = "financial_data"

    # Special categories (Article 9)
    HEALTH = "health_data"
    GENETIC = "genetic_data"
    BIOMETRIC = "biometric_data"
    RACIAL_ETHNIC = "racial_ethnic_origin"
    POLITICAL = "political_opinions"
    RELIGIOUS = "religious_beliefs"
    UNION_MEMBERSHIP = "trade_union_membership"
    SEX_LIFE = "sex_life_orientation"

    # Criminal data (Article 10)
    CRIMINAL = "criminal_convictions"


class GDPRConfiguration:
    """Configures GDPR compliance settings."""

    def __init__(self) -> None:
        """Initialize GDPR configuration."""
        self.config = self._initialize_default_config()
        self.jurisdiction_settings = self._initialize_jurisdictions()
        self.transfer_agreements: Dict[str, Any] = {}
        self.processing_records: List[Dict[str, Any]] = []
        self.privacy_settings = self._initialize_privacy_settings()

    def _initialize_default_config(self) -> Dict[str, Any]:
        """Initialize default GDPR configuration."""
        return {
            "data_controller": {
                "name": "Healthcare Organization",
                "address": "",
                "contact": "",
                "dpo_contact": "",
                "registration_number": "",
            },
            "retention_periods": {
                DataCategory.HEALTH.value: 10 * 365,  # 10 years
                DataCategory.IDENTIFICATION.value: 5 * 365,  # 5 years
                DataCategory.CONTACT.value: 3 * 365,  # 3 years
                DataCategory.GENETIC.value: 30 * 365,  # 30 years
                DataCategory.BIOMETRIC.value: 5 * 365,  # 5 years
            },
            "privacy_by_design": True,
            "privacy_by_default": True,
            "data_minimization": True,
            "purpose_limitation": True,
            "consent_required_for_processing": True,
            "explicit_consent_for_special_categories": True,
            "children_age_threshold": 16,  # Can be 13-16 depending on member state
            "breach_notification_threshold": 72,  # hours
            "dpia_required_threshold": "high_risk",
            "cross_border_transfers_allowed": False,
            "automated_decision_making": False,
            "profiling_allowed": False,
        }

    def _initialize_jurisdictions(self) -> Dict[str, Dict[str, Any]]:
        """Initialize jurisdiction-specific settings."""
        return {
            GDPRJurisdiction.EU.value: {
                "applicable": True,
                "supervisory_authority": "European Data Protection Board",
                "adequacy_decision": False,
                "additional_requirements": [],
            },
            GDPRJurisdiction.GERMANY.value: {
                "applicable": True,
                "supervisory_authority": "BfDI",
                "children_age": 16,
                "additional_requirements": ["Employee data protection"],
            },
            GDPRJurisdiction.UK.value: {
                "applicable": True,
                "supervisory_authority": "ICO",
                "adequacy_decision": True,
                "children_age": 13,
                "additional_requirements": ["UK GDPR specifics"],
            },
            GDPRJurisdiction.CANADA.value: {
                "applicable": False,
                "supervisory_authority": "OPC",
                "adequacy_decision": True,
                "alternative_framework": "PIPEDA",
                "additional_requirements": [],
            },
        }

    def _initialize_privacy_settings(self) -> Dict[str, Any]:
        """Initialize privacy-by-design settings."""
        return {
            "encryption_at_rest": True,
            "encryption_in_transit": True,
            "pseudonymization": True,
            "access_controls": True,
            "audit_logging": True,
            "data_minimization_checks": True,
            "purpose_limitation_enforcement": True,
            "consent_management": True,
            "automated_data_deletion": True,
            "privacy_impact_assessments": True,
        }

    def configure_controller(
        self,
        name: str,
        address: str,
        contact: str,
        dpo_contact: str,
        registration_number: Optional[str] = None,
    ) -> None:
        """Configure data controller information.

        Args:
            name: Controller name
            address: Controller address
            contact: General contact
            dpo_contact: Data Protection Officer contact
            registration_number: Company registration
        """
        self.config["data_controller"] = {
            "name": name,
            "address": address,
            "contact": contact,
            "dpo_contact": dpo_contact,
            "registration_number": registration_number or "",
            "configured_date": datetime.now().isoformat(),
        }

        logger.info("Configured data controller: %s", name)

    def configure_jurisdiction(
        self,
        jurisdiction: GDPRJurisdiction,
        supervisory_authority: str,
        additional_requirements: Optional[List[str]] = None,
    ) -> None:
        """Configure jurisdiction-specific settings.

        Args:
            jurisdiction: Target jurisdiction
            supervisory_authority: Supervisory authority name
            additional_requirements: Additional local requirements
        """
        if jurisdiction.value not in self.jurisdiction_settings:
            self.jurisdiction_settings[jurisdiction.value] = {}

        self.jurisdiction_settings[jurisdiction.value].update(
            {
                "applicable": True,
                "supervisory_authority": supervisory_authority,
                "additional_requirements": additional_requirements or [],
                "configured_date": datetime.now().isoformat(),
            }
        )

        logger.info("Configured jurisdiction: %s", jurisdiction.value)

    def configure_retention(
        self, data_category: DataCategory, retention_days: int, justification: str
    ) -> None:
        """Configure retention period for data category.

        Args:
            data_category: Category of data
            retention_days: Retention period in days
            justification: Legal justification
        """
        self.config["retention_periods"][data_category.value] = retention_days

        # Log configuration
        logger.info(
            "Configured retention for %s: %d days - %s",
            data_category.value,
            retention_days,
            justification,
        )

    def configure_international_transfer(
        self, destination: str, mechanism: TransferMechanism, details: Dict[str, Any]
    ) -> str:
        """Configure international data transfer.

        Args:
            destination: Destination country/organization
            mechanism: Legal transfer mechanism
            details: Transfer details

        Returns:
            Transfer agreement ID
        """
        transfer_id = self._generate_transfer_id()

        transfer_agreement = {
            "transfer_id": transfer_id,
            "destination": destination,
            "mechanism": mechanism.value,
            "details": details,
            "created_date": datetime.now(),
            "active": True,
            "review_date": datetime.now() + timedelta(days=365),
        }

        self.transfer_agreements[transfer_id] = transfer_agreement

        # Update global setting
        self.config["cross_border_transfers_allowed"] = True

        logger.info("Configured transfer to %s using %s", destination, mechanism.value)

        return transfer_id

    def enable_privacy_feature(self, feature: str, enabled: bool = True) -> None:
        """Enable or disable privacy feature.

        Args:
            feature: Feature name
            enabled: Whether to enable
        """
        if feature in self.privacy_settings:
            self.privacy_settings[feature] = enabled
            logger.info("Privacy feature '%s' set to %s", feature, enabled)
        else:
            logger.warning("Unknown privacy feature: %s", feature)

    def record_processing_activity(
        self,
        activity_name: str,
        purpose: str,
        categories: List[DataCategory],
        recipients: List[str],
        retention_period: int,
        security_measures: List[str],
    ) -> str:
        """Record processing activity for Article 30.

        Args:
            activity_name: Name of processing activity
            purpose: Purpose of processing
            categories: Data categories processed
            recipients: Data recipients
            retention_period: Retention in days
            security_measures: Security measures applied

        Returns:
            Processing record ID
        """
        record_id = self._generate_record_id()

        processing_record = {
            "record_id": record_id,
            "activity_name": activity_name,
            "purpose": purpose,
            "data_categories": [cat.value for cat in categories],
            "recipients": recipients,
            "retention_period": retention_period,
            "security_measures": security_measures,
            "created_date": datetime.now(),
            "last_reviewed": datetime.now(),
        }

        self.processing_records.append(processing_record)

        logger.info("Recorded processing activity: %s", activity_name)

        return record_id

    def validate_configuration(self) -> Dict[str, Any]:
        """Validate GDPR configuration completeness.

        Returns:
            Validation results
        """
        results: Dict[str, Any] = {
            "valid": True,
            "missing": [],
            "warnings": [],
            "compliance_score": 100,
        }

        # Check controller configuration
        controller = self.config["data_controller"]
        if not controller["name"] or not controller["dpo_contact"]:
            results["missing"].append("Data controller information")
            results["valid"] = False
            results["compliance_score"] -= 20

        # Check retention configuration
        if not self.config["retention_periods"]:
            results["missing"].append("Retention periods")
            results["valid"] = False
            results["compliance_score"] -= 15

        # Check privacy settings
        privacy_enabled = sum(1 for v in self.privacy_settings.values() if v)
        if privacy_enabled < len(self.privacy_settings) * 0.8:
            results["warnings"].append("Not all privacy features enabled")
            results["compliance_score"] -= 10

        # Check processing records
        if not self.processing_records:
            results["warnings"].append("No processing activities recorded")
            results["compliance_score"] -= 10

        # Check transfer agreements
        if (
            self.config["cross_border_transfers_allowed"]
            and not self.transfer_agreements
        ):
            results["warnings"].append(
                "Cross-border transfers enabled without agreements"
            )
            results["compliance_score"] -= 15

        return results

    def audit_compliance(self) -> Dict[str, Any]:
        """Audit GDPR compliance status.

        Returns:
            Compliance audit report
        """
        audit_date = datetime.now()

        # Validate configuration
        validation = self.validate_configuration()

        # Check retention compliance
        retention_compliance = self._check_retention_compliance()

        # Check transfer compliance
        transfer_compliance = self._check_transfer_compliance()

        # Check privacy measures
        privacy_compliance = self._check_privacy_compliance()

        audit_report = {
            "audit_date": audit_date,
            "overall_compliance": validation["compliance_score"],
            "configuration_valid": validation["valid"],
            "compliance_areas": {
                "configuration": validation,
                "retention": retention_compliance,
                "transfers": transfer_compliance,
                "privacy": privacy_compliance,
            },
            "recommendations": self._generate_recommendations(
                validation, retention_compliance, transfer_compliance
            ),
            "next_audit_date": audit_date + timedelta(days=90),
        }

        return audit_report

    def _check_retention_compliance(self) -> Dict[str, Any]:
        """Check retention period compliance."""
        compliant_categories = 0
        total_categories = len(DataCategory)

        for category in DataCategory:
            if category.value in self.config["retention_periods"]:
                compliant_categories += 1

        return {
            "compliant": compliant_categories == total_categories,
            "coverage": f"{compliant_categories}/{total_categories}",
            "percentage": (compliant_categories / total_categories) * 100,
        }

    def _check_transfer_compliance(self) -> Dict[str, Any]:
        """Check international transfer compliance."""
        if not self.config["cross_border_transfers_allowed"]:
            return {"compliant": True, "transfers": 0}

        active_transfers = sum(
            1 for t in self.transfer_agreements.values() if t["active"]
        )

        expired_transfers = sum(
            1
            for t in self.transfer_agreements.values()
            if t["review_date"] < datetime.now()
        )

        return {
            "compliant": expired_transfers == 0,
            "active_transfers": active_transfers,
            "expired_transfers": expired_transfers,
            "mechanisms_used": list(
                set(t["mechanism"] for t in self.transfer_agreements.values())
            ),
        }

    def _check_privacy_compliance(self) -> Dict[str, Any]:
        """Check privacy measures compliance."""
        enabled_features = sum(1 for v in self.privacy_settings.values() if v)
        total_features = len(self.privacy_settings)

        return {
            "compliant": enabled_features >= total_features * 0.9,
            "enabled_features": enabled_features,
            "total_features": total_features,
            "percentage": (enabled_features / total_features) * 100,
            "disabled_features": [k for k, v in self.privacy_settings.items() if not v],
        }

    def _generate_recommendations(
        self,
        validation: Dict[str, Any],
        retention: Dict[str, Any],
        transfers: Dict[str, Any],
    ) -> List[str]:
        """Generate compliance recommendations."""
        recommendations = []

        if validation["missing"]:
            recommendations.append(
                f"Complete missing configuration: {', '.join(validation['missing'])}"
            )

        if not retention["compliant"]:
            recommendations.append("Define retention periods for all data categories")

        if transfers.get("expired_transfers", 0) > 0:
            recommendations.append(
                f"Review and renew {transfers['expired_transfers']} expired transfer agreements"
            )

        disabled_privacy = self.privacy_settings.get("disabled_features", [])
        if disabled_privacy:
            recommendations.append(
                f"Enable privacy features: {', '.join(disabled_privacy[:3])}"
            )

        if not recommendations:
            recommendations.append("GDPR compliance configuration is satisfactory")

        return recommendations

    def _generate_transfer_id(self) -> str:
        """Generate unique transfer ID."""
        return f"GDPR-TRANSFER-{uuid.uuid4()}"

    def _generate_record_id(self) -> str:
        """Generate unique record ID."""
        return f"GDPR-RECORD-{uuid.uuid4()}"
