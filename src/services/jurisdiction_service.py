"""Jurisdiction Detection Service for Haven Health Passport.

This service determines the legal jurisdiction for a patient based on their location,
which is critical for compliance with data protection laws.
Includes validation for FHIR Resource jurisdiction requirements.
"""

import logging
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from src.models.organization import Organization
from src.models.patient import Patient

logger = logging.getLogger(__name__)


class JurisdictionService:
    """Service for determining legal jurisdiction based on patient location."""

    # Country to jurisdiction mapping
    COUNTRY_JURISDICTION_MAP = {
        # European Union countries - GDPR
        "AT": "EU",
        "BE": "EU",
        "BG": "EU",
        "HR": "EU",
        "CY": "EU",
        "CZ": "EU",
        "DK": "EU",
        "EE": "EU",
        "FI": "EU",
        "FR": "EU",
        "DE": "EU",
        "GR": "EU",
        "HU": "EU",
        "IE": "EU",
        "IT": "EU",
        "LV": "EU",
        "LT": "EU",
        "LU": "EU",
        "MT": "EU",
        "NL": "EU",
        "PL": "EU",
        "PT": "EU",
        "RO": "EU",
        "SK": "EU",
        "SI": "EU",
        "ES": "EU",
        "SE": "EU",
        # United States - HIPAA
        "US": "US",
        # United Kingdom - UK GDPR
        "GB": "UK",
        # Canada - PIPEDA
        "CA": "CA",
        # Australia - Privacy Act
        "AU": "AU",
        # Other major jurisdictions
        "CN": "CN",  # China - PIPL
        "IN": "IN",  # India - DPDP
        "JP": "JP",  # Japan - APPI
        "KR": "KR",  # South Korea - PIPA
        "BR": "BR",  # Brazil - LGPD
        "ZA": "ZA",  # South Africa - POPIA
        "RU": "RU",  # Russia - Federal Law 152-FZ
        # Common refugee host countries
        "JO": "JO",  # Jordan
        "LB": "LB",  # Lebanon
        "TR": "TR",  # Turkey
        "UG": "UG",  # Uganda
        "KE": "KE",  # Kenya
        "ET": "ET",  # Ethiopia
        "SD": "SD",  # Sudan
        "BD": "BD",  # Bangladesh
        "PK": "PK",  # Pakistan
        "IR": "IR",  # Iran
    }

    # Default jurisdiction for unknown countries
    DEFAULT_JURISDICTION = "INTL"  # International/Unknown

    def __init__(self, db: Session):
        """Initialize the Jurisdiction Service.

        Args:
            db: SQLAlchemy database session
        """
        self.db = db

    def validate_jurisdiction_requirements(
        self, jurisdiction_data: Dict[str, Any]
    ) -> bool:
        """Validate jurisdiction data for FHIR Location resource compliance.

        Args:
            jurisdiction_data: Dictionary containing jurisdiction information

        Returns:
            bool: True if jurisdiction data is valid, False otherwise
        """
        if not jurisdiction_data:
            logger.error("Jurisdiction validation failed: empty data")
            return False

        # Validate required fields for FHIR Location resource
        required_fields = ["country_code", "jurisdiction_type"]
        for field in required_fields:
            if field not in jurisdiction_data:
                logger.error(
                    "Missing required field for FHIR Location Resource: %s", field
                )
                return False

        # Validate country code format (ISO 3166-1 alpha-2)
        country_code = jurisdiction_data["country_code"]
        if not isinstance(country_code, str) or len(country_code) != 2:
            logger.error("Invalid country code format: %s", country_code)
            return False

        # Validate jurisdiction type
        valid_types = ["country", "region", "state", "international"]
        if jurisdiction_data["jurisdiction_type"] not in valid_types:
            logger.error(
                "Invalid jurisdiction type: %s", jurisdiction_data["jurisdiction_type"]
            )
            return False

        return True

    def get_patient_jurisdiction(self, patient_id: str) -> str:
        """Get the legal jurisdiction for a patient based on their location.

        Args:
            patient_id: UUID of the patient

        Returns:
            str: Jurisdiction code (e.g., 'US', 'EU', 'UK')
        """
        try:
            # Get patient record
            patient = self.db.query(Patient).filter(Patient.id == patient_id).first()

            if not patient:
                logger.warning(
                    "Patient %s not found for jurisdiction detection", patient_id
                )
                return self.DEFAULT_JURISDICTION

            # Try multiple methods to determine jurisdiction
            jurisdiction = None

            # Method 1: Check current location from GPS coordinates
            if patient.gps_coordinates:
                # GPS coordinates contain PHI and must be encrypted at rest
                jurisdiction = self._get_jurisdiction_from_gps(patient.gps_coordinates)
                if jurisdiction:
                    return jurisdiction

            # Method 2: Check country of origin
            if hasattr(patient, "country_of_origin") and patient.country_of_origin:
                jurisdiction = self.COUNTRY_JURISDICTION_MAP.get(
                    patient.country_of_origin.upper(), None
                )
                if jurisdiction:
                    return jurisdiction

            # Method 3: Check current camp location
            if patient.current_camp:
                country_code = self._extract_country_from_camp(patient.current_camp)
                if country_code:
                    jurisdiction = self.COUNTRY_JURISDICTION_MAP.get(
                        country_code.upper(), None
                    )
                    if jurisdiction:
                        return jurisdiction

            # Method 4: Check cross-border permissions
            if patient.cross_border_permissions:
                countries = patient.cross_border_permissions.get("countries", [])
                if countries:
                    # Use the first country in the list
                    jurisdiction = self.COUNTRY_JURISDICTION_MAP.get(
                        countries[0].upper(), None
                    )
                    if jurisdiction:
                        return jurisdiction

            # Method 5: Check managing organization's country
            if patient.managing_organization:
                org_jurisdiction = self._get_organization_jurisdiction(
                    patient.managing_organization
                )
                if org_jurisdiction:
                    return org_jurisdiction

            # Default to international jurisdiction
            logger.info(
                "Could not determine specific jurisdiction for patient %s, "
                "using default: %s",
                patient_id,
                self.DEFAULT_JURISDICTION,
            )
            return self.DEFAULT_JURISDICTION

        except (AttributeError, KeyError, TypeError, ValueError) as e:
            logger.error("Error determining patient jurisdiction: %s", str(e))
            return self.DEFAULT_JURISDICTION

    def _get_jurisdiction_from_gps(
        self, gps_coordinates: Dict[str, float]
    ) -> Optional[str]:
        """Determine jurisdiction from GPS coordinates.

        Args:
            gps_coordinates: Dict with 'lat' and 'lng' keys

        Returns:
            Optional[str]: Jurisdiction code or None
        """
        try:
            lat = gps_coordinates.get("lat")
            lng = gps_coordinates.get("lng")

            if lat is None or lng is None:
                return None

            # This is a simplified implementation
            # In production, you would use a reverse geocoding service
            # For now, we'll use rough geographic boundaries

            # Europe (rough boundaries)
            if 35 <= lat <= 70 and -10 <= lng <= 40:
                return "EU"

            # United States (continental)
            elif 25 <= lat <= 49 and -125 <= lng <= -66:
                return "US"

            # Middle East (rough boundaries)
            elif 15 <= lat <= 42 and 25 <= lng <= 63:
                # Check specific countries
                if 29 <= lat <= 33 and 34 <= lng <= 39:
                    return "JO"  # Jordan
                elif 33 <= lat <= 37 and 35 <= lng <= 43:
                    return "LB"  # Lebanon
                elif 36 <= lat <= 42 and 26 <= lng <= 45:
                    return "TR"  # Turkey

            # East Africa
            elif -5 <= lat <= 15 and 28 <= lng <= 52:
                if -2 <= lat <= 5 and 29 <= lng <= 35:
                    return "UG"  # Uganda
                elif -5 <= lat <= 5 and 33 <= lng <= 42:
                    return "KE"  # Kenya
                elif 3 <= lat <= 15 and 33 <= lng <= 48:
                    return "ET"  # Ethiopia

            # Default to international
            return None

        except (KeyError, TypeError, ValueError) as e:
            logger.error("Error parsing GPS coordinates: %s", str(e))
            return None

    def _extract_country_from_camp(self, camp_name: str) -> Optional[str]:
        """Extract country code from camp name.

        Args:
            camp_name: Name of the refugee camp

        Returns:
            Optional[str]: Two-letter country code or None
        """
        # Common camp name patterns
        camp_country_patterns = {
            "kakuma": "KE",  # Kenya
            "dadaab": "KE",  # Kenya
            "zaatari": "JO",  # Jordan
            "azraq": "JO",  # Jordan
            "bidi bidi": "UG",  # Uganda
            "nakivale": "UG",  # Uganda
            "cox's bazar": "BD",  # Bangladesh
            "kutupalong": "BD",  # Bangladesh
        }

        camp_lower = camp_name.lower()
        for pattern, country in camp_country_patterns.items():
            if pattern in camp_lower:
                return country

        return None

    def _get_organization_jurisdiction(self, organization_name: str) -> Optional[str]:
        """Get jurisdiction based on organization.

        Args:
            organization_name: Name of the managing organization

        Returns:
            Optional[str]: Jurisdiction code or None
        """
        try:
            org = (
                self.db.query(Organization)
                .filter(Organization.name == organization_name)
                .first()
            )

            if org and org.country:
                return self.COUNTRY_JURISDICTION_MAP.get(org.country.upper(), None)

            return None

        except (ImportError, AttributeError, ValueError) as e:
            logger.error("Error getting organization jurisdiction: %s", str(e))
            return None

    def get_data_retention_requirements(self, jurisdiction: str) -> Dict[str, Any]:
        """Get data retention requirements for a jurisdiction.

        Args:
            jurisdiction: Jurisdiction code

        Returns:
            Dict with retention requirements
        """
        retention_policies = {
            "US": {
                "medical_records": "6 years",
                "audit_logs": "7 years",
                "consent_records": "6 years",
                "allows_deletion": True,
            },
            "EU": {
                "medical_records": "10 years",
                "audit_logs": "3 years",
                "consent_records": "as long as processing continues",
                "allows_deletion": True,  # GDPR right to erasure
            },
            "UK": {
                "medical_records": "8 years",
                "audit_logs": "3 years",
                "consent_records": "6 years",
                "allows_deletion": True,
            },
            "CA": {
                "medical_records": "10 years",
                "audit_logs": "7 years",
                "consent_records": "7 years",
                "allows_deletion": True,
            },
            "AU": {
                "medical_records": "7 years",
                "audit_logs": "7 years",
                "consent_records": "7 years",
                "allows_deletion": True,
            },
            "INTL": {
                "medical_records": "10 years",  # Conservative default
                "audit_logs": "7 years",
                "consent_records": "10 years",
                "allows_deletion": False,  # Conservative approach
            },
        }

        return retention_policies.get(jurisdiction, retention_policies["INTL"])
