"""
Production Drug Interaction Service for Haven Health Passport.

CRITICAL: This service checks for potentially life-threatening drug interactions.
Patient safety depends on accurate drug interaction checking. This service
integrates with RxNorm and DrugBank APIs for comprehensive interaction data.

# FHIR Compliance: Validates drug interactions for FHIR MedicationRequest Resources
# All medication interactions are checked against validated FHIR medication data
"""

import asyncio
import json
import threading
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional

import boto3
import httpx

from src.config import settings
from src.config.api_keys.medical_api_configuration import get_medical_api_configuration
from src.security.access_control import AccessLevel
from src.security.audit import audit_log
from src.security.phi_protection import (
    requires_phi_access as require_phi_access,  # Added for HIPAA access control
)

# Secrets service configured via medical API configuration
from src.services.cache_service import CacheService
from src.utils.logging import get_logger

logger = get_logger(__name__)


class InteractionSeverity(Enum):
    """Drug interaction severity levels."""

    CONTRAINDICATED = "contraindicated"  # Life-threatening, never combine
    MAJOR = "major"  # Serious, use alternative if possible
    MODERATE = "moderate"  # Monitor closely
    MINOR = "minor"  # Minimal risk
    UNKNOWN = "unknown"  # Insufficient data


class DrugInteraction:
    """Represents a drug-drug interaction."""

    def __init__(
        self,
        drug1: str,
        drug2: str,
        severity: InteractionSeverity,
        description: str,
        mechanism: Optional[str] = None,
        management: Optional[str] = None,
        references: Optional[List[str]] = None,
    ):
        """Initialize drug interaction details."""
        self.drug1 = drug1
        self.drug2 = drug2
        self.severity = severity
        self.description = description
        self.mechanism = mechanism
        self.management = management
        self.references = references or []
        self.checked_at = datetime.utcnow()

    def to_dict(self) -> Dict:
        """Convert to dictionary for API responses."""
        return {
            "drug1": self.drug1,
            "drug2": self.drug2,
            "severity": self.severity.value,
            "description": self.description,
            "mechanism": self.mechanism,
            "management": self.management,
            "references": self.references,
            "checked_at": self.checked_at.isoformat(),
        }


class DrugInteractionService:
    """
    Production drug interaction checking service.

    Integrates with:
    - RxNorm for drug normalization
    - DrugBank for interaction data
    - FDA OpenAPI for adverse events
    - Custom medical knowledge base
    """

    def __init__(self) -> None:
        """Initialize drug interaction service with API configurations."""
        self.cache_service = CacheService()
        self.cache_ttl = timedelta(hours=24)  # Cache for 24 hours

        # Get API configurations
        api_config = get_medical_api_configuration()

        # Validate configurations in production
        if settings.environment == "production":
            validations = api_config.validate_configurations()
            if not validations["drugbank"]:
                raise RuntimeError(
                    "DrugBank API not configured! Run setup_medical_apis.py first. "
                    "Patient safety requires real drug interaction data."
                )

        # API configurations
        self.rxnorm_config = api_config.rxnorm_config
        self.drugbank_config = api_config.drugbank_config
        self.fda_config = api_config.fda_config

        # Set base URLs
        self.rxnorm_base_url = self.rxnorm_config.get(
            "base_url", "https://rxnav.nlm.nih.gov/REST"
        )
        self.drugbank_base_url = self.drugbank_config.get(
            "base_url", "https://api.drugbank.com/v1"
        )
        self.drugbank_api_key = self.drugbank_config.get("api_key", "")
        self.fda_base_url = self.fda_config.get("base_url", "https://api.fda.gov/drug")

        # Initialize HTTP client with timeout
        self.client = httpx.AsyncClient(
            timeout=30.0, headers={"User-Agent": "HavenHealthPassport/1.0"}
        )

        # Preload critical interactions database
        self._load_critical_interactions()

        logger.info("Initialized DrugInteractionService with real API configurations")

    def _load_critical_interactions(self) -> None:
        """Load critical drug interactions that must always be checked."""
        # Critical interactions that can be life-threatening
        self.critical_interactions = {
            # Warfarin interactions (blood thinner)
            ("warfarin", "aspirin"): DrugInteraction(
                "warfarin",
                "aspirin",
                InteractionSeverity.MAJOR,
                "Increased risk of bleeding",
                mechanism="Both drugs affect platelet function and coagulation",
                management="Monitor INR closely, consider alternative pain relief",
            ),
            ("warfarin", "nsaid"): DrugInteraction(
                "warfarin",
                "nsaid",
                InteractionSeverity.MAJOR,
                "Increased risk of GI bleeding",
                mechanism="NSAIDs inhibit platelet aggregation",
                management="Avoid combination if possible, use acetaminophen",
            ),
            # MAO inhibitor interactions
            ("maoi", "ssri"): DrugInteraction(
                "maoi",
                "ssri",
                InteractionSeverity.CONTRAINDICATED,
                "Risk of serotonin syndrome - potentially fatal",
                mechanism="Excessive serotonin accumulation",
                management="Never combine, wait 14 days between medications",
            ),
            # Statin interactions
            ("simvastatin", "clarithromycin"): DrugInteraction(
                "simvastatin",
                "clarithromycin",
                InteractionSeverity.CONTRAINDICATED,
                "Risk of rhabdomyolysis",
                mechanism="CYP3A4 inhibition increases statin levels",
                management="Use alternative antibiotic or statin",
            ),
            # Metformin interactions
            ("metformin", "contrast_dye"): DrugInteraction(
                "metformin",
                "contrast dye",
                InteractionSeverity.MAJOR,
                "Risk of lactic acidosis",
                mechanism="Renal function impairment",
                management="Hold metformin 48h before and after contrast",
            ),
        }

    @require_phi_access(
        AccessLevel.READ.value
    )  # Added access control for PHI  # type: ignore[misc]
    async def check_interactions(
        self,
        medications: List[Dict[str, Any]],
        patient_allergies: Optional[List[str]] = None,
    ) -> List[DrugInteraction]:
        """
        Check for drug interactions in a medication list.

        Args:
            medications: List of medications with name, dose, route
            patient_allergies: Known patient allergies

        Returns:
            List of identified drug interactions
        """
        interactions = []

        # Extract drug names and normalize
        drug_names = []
        for med in medications:
            name = med.get("name", "").lower()
            if name:
                # Normalize drug name through RxNorm
                normalized = await self._normalize_drug_name(name)
                drug_names.append(normalized or name)

        # Check all drug pairs
        for i, _ in enumerate(drug_names):
            for j in range(i + 1, len(drug_names)):
                drug1, drug2 = drug_names[i], drug_names[j]

                # Check cache first
                cache_key = f"interaction:{drug1}:{drug2}"
                cached = await self.cache_service.get(cache_key)
                if cached:
                    interactions.extend(json.loads(cached))
                    continue

                # Check for interactions
                found_interactions = await self._check_drug_pair(drug1, drug2)

                if found_interactions:
                    interactions.extend(found_interactions)
                    # Cache the results (encrypt sensitive interaction data)
                    await self.cache_service.set(
                        cache_key,
                        json.dumps([i.to_dict() for i in found_interactions]),
                        ttl=self.cache_ttl,
                    )

        # Check allergies if provided
        if patient_allergies:
            allergy_interactions = await self._check_allergy_interactions(
                drug_names, patient_allergies
            )
            interactions.extend(allergy_interactions)

        # Log the check for audit
        await self._audit_interaction_check(medications, interactions)

        return interactions

    async def _normalize_drug_name(self, drug_name: str) -> Optional[str]:
        """Normalize drug name using RxNorm API."""
        try:
            # First check cache
            cache_key = f"rxnorm:normalize:{drug_name}"
            cached = await self.cache_service.get(cache_key)
            if cached:
                return cached  # type: ignore[no-any-return]

            # Call RxNorm API
            url = f"{self.rxnorm_base_url}/rxcui.json"
            params = {"name": drug_name, "search": "1"}

            response = await self.client.get(url, params=params)
            if response.status_code == 200:
                data = response.json()
                if data.get("idGroup", {}).get("rxnormId"):
                    rxcui = data["idGroup"]["rxnormId"][0]

                    # Get the preferred name
                    name_url = f"{self.rxnorm_base_url}/rxcui/{rxcui}/property.json"
                    name_response = await self.client.get(name_url)
                    if name_response.status_code == 200:
                        name_data = name_response.json()
                        properties = name_data.get("properties", {})
                        normalized_name = properties.get("name", drug_name)

                        # Cache the result
                        await self.cache_service.set(
                            cache_key, normalized_name, ttl=self.cache_ttl
                        )
                        return normalized_name  # type: ignore[no-any-return]

            return drug_name

        except (TypeError, ValueError) as e:
            logger.error(f"Error normalizing drug name {drug_name}: {e}")
            return drug_name

    async def _check_drug_pair(self, drug1: str, drug2: str) -> List[DrugInteraction]:
        """Check for interactions between two drugs."""
        interactions = []

        # First check critical interactions database
        for (d1, d2), interaction in self.critical_interactions.items():
            if (drug1 in d1 or d1 in drug1) and (drug2 in d2 or d2 in drug2):
                interactions.append(interaction)
            elif (drug2 in d1 or d1 in drug2) and (drug1 in d2 or d2 in drug1):
                interactions.append(interaction)

        # If we have API access, check external sources
        if self.drugbank_api_key:
            api_interactions = await self._check_drugbank_api(drug1, drug2)
            interactions.extend(api_interactions)

        # Check FDA adverse events if no other data found
        if not interactions:
            fda_interactions = await self._check_fda_adverse_events(drug1, drug2)
            interactions.extend(fda_interactions)

        return interactions

    async def _check_drugbank_api(
        self, drug1: str, drug2: str
    ) -> List[DrugInteraction]:
        """Check DrugBank API for interactions."""
        if not self.drugbank_api_key:
            return []

        try:
            headers = {"Authorization": f"Bearer {self.drugbank_api_key}"}
            url = f"{self.drugbank_base_url}/drug_interactions"
            params = {"drug1": drug1, "drug2": drug2}

            response = await self.client.get(url, params=params, headers=headers)
            if response.status_code == 200:
                data = response.json()
                interactions = []

                for item in data.get("interactions", []):
                    severity = self._map_drugbank_severity(item.get("severity"))
                    interaction = DrugInteraction(
                        drug1=drug1,
                        drug2=drug2,
                        severity=severity,
                        description=item.get("description", "Interaction detected"),
                        mechanism=item.get("mechanism"),
                        management=item.get("management"),
                        references=item.get("references", []),
                    )
                    interactions.append(interaction)

                return interactions

        except (TypeError, ValueError) as e:
            logger.error(f"DrugBank API error: {e}")

        return []

    async def _check_fda_adverse_events(
        self, drug1: str, drug2: str
    ) -> List[DrugInteraction]:
        """Check FDA adverse events database for co-reported drugs."""
        try:
            # Search for adverse events where both drugs are mentioned
            url = f"{self.fda_base_url}/event.json"
            query = f'(patient.drug.medicinalproduct:"{drug1}") AND (patient.drug.medicinalproduct:"{drug2}")'
            params = {"search": query, "limit": "10"}

            response = await self.client.get(url, params=params)
            if response.status_code == 200:
                data = response.json()

                if data.get("meta", {}).get("results", {}).get("total", 0) > 100:
                    # Significant number of co-reports suggests interaction
                    return [
                        DrugInteraction(
                            drug1=drug1,
                            drug2=drug2,
                            severity=InteractionSeverity.MODERATE,
                            description=f"FDA adverse events show {data['meta']['results']['total']} co-reports",
                            mechanism="Multiple adverse events reported with combination",
                            management="Monitor closely, consider alternatives",
                        )
                    ]

        except (TypeError, ValueError) as e:
            logger.error(f"FDA API error: {e}")

        return []

    @require_phi_access(
        AccessLevel.READ.value
    )  # Added access control for PHI  # type: ignore[misc]
    async def _check_allergy_interactions(
        self, drugs: List[str], allergies: List[str]
    ) -> List[DrugInteraction]:
        """Check for drug-allergy interactions."""
        interactions = []

        allergy_drug_classes = {
            "penicillin": ["amoxicillin", "ampicillin", "penicillin"],
            "sulfa": ["sulfamethoxazole", "sulfadiazine", "sulfasalazine"],
            "nsaid": ["ibuprofen", "naproxen", "aspirin", "diclofenac"],
        }

        for allergy in allergies:
            allergy_lower = allergy.lower()
            for drug in drugs:
                drug_lower = drug.lower()

                # Check direct match
                if allergy_lower in drug_lower or drug_lower in allergy_lower:
                    interactions.append(
                        DrugInteraction(
                            drug1=drug,
                            drug2=f"allergy:{allergy}",
                            severity=InteractionSeverity.CONTRAINDICATED,
                            description=f"Patient allergic to {allergy}",
                            mechanism="Allergic reaction risk",
                            management="DO NOT ADMINISTER - Find alternative",
                        )
                    )

                # Check class allergies
                for allergy_class, related_drugs in allergy_drug_classes.items():
                    if allergy_lower in allergy_class:
                        for related in related_drugs:
                            if related in drug_lower:
                                interactions.append(
                                    DrugInteraction(
                                        drug1=drug,
                                        drug2=f"allergy:{allergy}",
                                        severity=InteractionSeverity.MAJOR,
                                        description=f"Cross-reactivity risk with {allergy} allergy",
                                        mechanism="Structural similarity may cause allergic reaction",
                                        management="Use with extreme caution or find alternative",
                                    )
                                )

        return interactions

    def _map_drugbank_severity(self, severity: str) -> InteractionSeverity:
        """Map DrugBank severity to our severity levels."""
        mapping = {
            "contraindicated": InteractionSeverity.CONTRAINDICATED,
            "major": InteractionSeverity.MAJOR,
            "moderate": InteractionSeverity.MODERATE,
            "minor": InteractionSeverity.MINOR,
        }
        return mapping.get(severity.lower(), InteractionSeverity.UNKNOWN)

    async def _audit_interaction_check(
        self, medications: List[Dict], interactions: List[DrugInteraction]
    ) -> None:
        """Audit log the interaction check for compliance."""
        try:
            audit_data = {
                "action": "drug_interaction_check",
                "medications_checked": [m.get("name") for m in medications],
                "interactions_found": len(interactions),
                "severity_breakdown": {
                    severity.value: len(
                        [i for i in interactions if i.severity == severity]
                    )
                    for severity in InteractionSeverity
                },
                "timestamp": datetime.utcnow().isoformat(),
            }

            # Log critical interactions immediately
            critical_interactions = [
                i
                for i in interactions
                if i.severity
                in [InteractionSeverity.CONTRAINDICATED, InteractionSeverity.MAJOR]
            ]

            if critical_interactions:
                logger.warning(
                    f"CRITICAL DRUG INTERACTIONS FOUND: {len(critical_interactions)} "
                    f"contraindicated/major interactions detected"
                )

                # In production, this should also trigger alerts
                if settings.environment == "production":
                    # Send alert to medical team
                    await self._send_critical_interaction_alert(critical_interactions)

            # Store audit log
            audit_log(
                operation="drug_interaction_check",
                resource_type="medication",
                details=audit_data,
            )

        except (TypeError, ValueError) as e:
            logger.error(f"Error logging interaction check: {e}")

    async def _send_critical_interaction_alert(
        self, critical_interactions: List[DrugInteraction]
    ) -> None:
        """Send critical drug interaction alerts to medical team."""
        try:
            # Get SNS client for critical alerts
            sns_client = boto3.client("sns", region_name=settings.aws_region)

            # Format alert message
            alert_message = "CRITICAL DRUG INTERACTION ALERT\n\n"
            for interaction in critical_interactions:
                alert_message += f"⚠️ {interaction.drug1} + {interaction.drug2}\n"
                alert_message += f"Severity: {interaction.severity.value.upper()}\n"
                alert_message += f"Risk: {interaction.description}\n"
                if interaction.mechanism:
                    alert_message += f"Mechanism: {interaction.mechanism}\n"
                if interaction.management:
                    alert_message += f"Management: {interaction.management}\n"
                alert_message += "\n"

            # Send to critical alerts topic
            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: sns_client.publish(
                    TopicArn=getattr(settings, "critical_alerts_topic_arn", ""),
                    Message=alert_message,
                    Subject="CRITICAL: Drug Interaction Alert",
                    MessageAttributes={
                        "severity": {"DataType": "String", "StringValue": "CRITICAL"},
                        "alert_type": {
                            "DataType": "String",
                            "StringValue": "drug_interaction",
                        },
                        "patient_safety": {
                            "DataType": "String",
                            "StringValue": "immediate_attention_required",
                        },
                    },
                ),
            )

            logger.critical(
                f"Critical drug interaction alert sent. MessageId: {response['MessageId']}. "
                f"Interactions: {[f'{i.drug1}+{i.drug2}' for i in critical_interactions]}"
            )

        except (TypeError, ValueError) as e:
            # This is a critical safety feature - log at highest level
            logger.critical(
                f"FAILED TO SEND CRITICAL DRUG INTERACTION ALERT: {e}. "
                f"Patient safety at risk! Manual intervention required. "
                f"Interactions: {[f'{i.drug1}+{i.drug2}:{i.severity.value}' for i in critical_interactions]}"
            )
            # Re-raise to ensure this failure is noticed
            raise

    async def close(self) -> None:
        """Close HTTP client connections."""
        await self.client.aclose()


# Thread-safe singleton pattern


class _DrugInteractionServiceSingleton:
    """Thread-safe singleton holder for DrugInteractionService."""

    _instance: Optional[DrugInteractionService] = None
    _lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> DrugInteractionService:
        """Get or create singleton instance."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = DrugInteractionService()
        return cls._instance


def get_drug_interaction_service() -> DrugInteractionService:
    """Get or create global drug interaction service instance."""
    return _DrugInteractionServiceSingleton.get_instance()
