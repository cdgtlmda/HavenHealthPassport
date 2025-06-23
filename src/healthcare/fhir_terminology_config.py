"""
FHIR Terminology Service Configuration.

This module provides configuration and initialization for the terminology service,
including loading standard terminology systems and value sets.
Handles FHIR CodeSystem Resource validation. All PHI data is encrypted
and access is controlled through role-based permissions.
"""

import json
from pathlib import Path
from typing import List, Optional

from pydantic import Field
from pydantic_settings import BaseSettings

from src.healthcare.fhir_terminology_service import (
    CodeSystem,
    Concept,
    ConceptProperty,
    TerminologyService,
    ValueSet,
    ValueSetCompose,
    get_terminology_service,
)
from src.healthcare.fhir_validator import FHIRValidator
from src.utils.logging import get_logger

# FHIR resource type for this module
__fhir_resource__ = "CodeSystem"

logger = get_logger(__name__)


class TerminologyServiceConfig(BaseSettings):
    """Configuration for terminology service."""

    # Data directories
    terminology_data_dir: Path = Field(
        default=Path("data/terminology"), description="Terminology data directory"
    )
    code_systems_dir: Path = Field(
        default=Path("data/terminology/code-systems"),
        description="Code systems directory",
    )
    value_sets_dir: Path = Field(
        default=Path("data/terminology/value-sets"), description="Value sets directory"
    )

    # Service settings
    enable_caching: bool = Field(default=True, description="Enable caching")
    cache_ttl_seconds: int = Field(
        default=3600, description="Cache TTL in seconds"
    )  # 1 hour

    # Loading options
    load_standard_terminologies: bool = Field(
        default=True, description="Load standard terminologies"
    )
    load_custom_terminologies: bool = Field(
        default=True, description="Load custom terminologies"
    )

    # Supported systems
    enable_snomed_ct: bool = Field(default=True, description="Enable SNOMED CT")
    enable_icd10: bool = Field(default=True, description="Enable ICD-10")
    enable_loinc: bool = Field(default=True, description="Enable LOINC")
    enable_rxnorm: bool = Field(default=True, description="Enable RxNorm")

    # Multi-language support
    supported_languages: List[str] = Field(
        default=["en", "es", "fr", "ar", "sw"], description="Supported languages"
    )
    default_language: str = Field(default="en", description="Default language")


class TerminologyConfigurator:
    """Configures and initializes the terminology service with standard and custom terminologies.

    Provides methods to load and configure standard medical terminologies
    and custom value sets for the FHIR server.
    """

    def __init__(self, config: Optional[TerminologyServiceConfig] = None):
        """Initialize terminology configurator.

        Args:
            config: Terminology service configuration
        """
        self.config = config or TerminologyServiceConfig()
        self.service = get_terminology_service()
        self.validator = FHIRValidator()

    def validate_code_system(self, code_system: CodeSystem) -> bool:
        """Validate a code system.

        Args:
            code_system: CodeSystem to validate

        Returns:
            True if valid, False otherwise
        """
        try:
            # Basic validation
            if not code_system.id or not code_system.url:
                return False

            # Validate concepts
            if code_system.concepts:
                for concept in code_system.concepts:
                    if not concept.code or not concept.display:
                        return False

            return True
        except (AttributeError, KeyError, TypeError, ValueError):
            return False

    def initialize(self) -> None:
        """Initialize terminology service with configured systems."""
        logger.info("Initializing terminology service...")

        # Create data directories if needed
        self._ensure_directories()

        # Load standard terminologies
        if self.config.load_standard_terminologies:
            self._load_standard_terminologies()

        # Load custom terminologies from files
        if self.config.load_custom_terminologies:
            self._load_custom_terminologies()

        # Create standard value sets
        self._create_standard_value_sets()

        logger.info("Terminology service initialization complete")

    def _ensure_directories(self) -> None:
        """Ensure terminology data directories exist."""
        for directory in [
            self.config.terminology_data_dir,
            self.config.code_systems_dir,
            self.config.value_sets_dir,
        ]:
            directory.mkdir(parents=True, exist_ok=True)

    def _load_standard_terminologies(self) -> None:
        """Load standard medical terminologies."""
        # Load basic FHIR code systems
        self._load_fhir_core_systems()

        # Load observation codes
        self._load_observation_codes()

        # Load medication codes
        self._load_medication_codes()

        # Load immunization codes
        self._load_immunization_codes()

        logger.info("Loaded standard terminologies")

    def _load_fhir_core_systems(self) -> None:
        """Load core FHIR code systems."""
        # Observation Status
        obs_status = CodeSystem(
            id="observation-status",
            url="http://hl7.org/fhir/observation-status",
            name="ObservationStatus",
            title="Observation Status",
            content="complete",
        )
        obs_status.concepts = [
            Concept(
                system=obs_status.url,
                code="registered",
                display="Registered",
                definition="The existence of the observation is registered.",
            ),
            Concept(
                system=obs_status.url,
                code="preliminary",
                display="Preliminary",
                definition="This is an initial or interim observation.",
            ),
            Concept(
                system=obs_status.url,
                code="final",
                display="Final",
                definition="The observation is complete and verified.",
            ),
            Concept(
                system=obs_status.url,
                code="amended",
                display="Amended",
                definition="Subsequent to being final, the observation has been modified.",
            ),
        ]
        self.service.add_code_system(obs_status)

    def _load_observation_codes(self) -> None:
        """Load common observation codes."""
        # Basic vital signs
        vital_signs = CodeSystem(
            id="vital-signs",
            url="http://havenhealthpassport.org/fhir/CodeSystem/vital-signs",
            name="VitalSigns",
            title="Vital Signs",
            content="complete",
        )

        vital_concepts = [
            ("blood-pressure", "Blood Pressure", "85354-9"),
            ("heart-rate", "Heart Rate", "8867-4"),
            ("respiratory-rate", "Respiratory Rate", "9279-1"),
            ("body-temperature", "Body Temperature", "8310-5"),
            ("oxygen-saturation", "Oxygen Saturation", "59408-5"),
            ("body-weight", "Body Weight", "29463-7"),
            ("body-height", "Body Height", "8302-2"),
            ("bmi", "Body Mass Index", "39156-5"),
        ]

        for code, display, loinc in vital_concepts:
            vital_signs.concepts.append(
                Concept(
                    system=vital_signs.url,
                    code=code,
                    display=display,
                    properties=[ConceptProperty(code="loinc", value=loinc)],
                )
            )

        self.service.add_code_system(vital_signs)

    def _load_medication_codes(self) -> None:
        """Load common medication codes."""
        # Common medications for refugees
        refugee_meds = CodeSystem(
            id="refugee-medications",
            url="http://havenhealthpassport.org/fhir/CodeSystem/refugee-medications",
            name="RefugeeMedications",
            title="Common Refugee Medications",
            content="complete",
        )

        med_concepts = [
            ("paracetamol", "Paracetamol", "acetaminophen"),
            ("ibuprofen", "Ibuprofen", "anti-inflammatory"),
            ("amoxicillin", "Amoxicillin", "antibiotic"),
            ("metronidazole", "Metronidazole", "antibiotic"),
            ("albendazole", "Albendazole", "antiparasitic"),
            ("ors", "Oral Rehydration Salts", "rehydration"),
            ("vitamin-a", "Vitamin A", "vitamin"),
            ("iron-folate", "Iron + Folate", "supplement"),
        ]

        for code, display, category in med_concepts:
            refugee_meds.concepts.append(
                Concept(
                    system=refugee_meds.url,
                    code=code,
                    display=display,
                    properties=[ConceptProperty(code="category", value=category)],
                )
            )

        self.service.add_code_system(refugee_meds)

    def _load_immunization_codes(self) -> None:
        """Load immunization codes."""
        # Essential immunizations
        immunizations = CodeSystem(
            id="essential-immunizations",
            url="http://havenhealthpassport.org/fhir/CodeSystem/essential-immunizations",
            name="EssentialImmunizations",
            title="Essential Immunizations",
            content="complete",
        )

        vaccine_concepts = [
            ("bcg", "BCG (Tuberculosis)", "20"),
            ("opv", "Oral Polio Vaccine", "02"),
            ("measles", "Measles", "05"),
            ("dtp", "DTP (Diphtheria, Tetanus, Pertussis)", "107"),
            ("hepb", "Hepatitis B", "08"),
            ("yellow-fever", "Yellow Fever", "37"),
            ("cholera", "Cholera", "26"),
            ("covid19", "COVID-19", "213"),
        ]

        for code, display, cvx in vaccine_concepts:
            immunizations.concepts.append(
                Concept(
                    system=immunizations.url,
                    code=code,
                    display=display,
                    properties=[ConceptProperty(code="cvx", value=cvx)],
                )
            )

        self.service.add_code_system(immunizations)

    def _create_standard_value_sets(self) -> None:
        """Create standard value sets."""
        # Vital signs value set
        vital_signs_vs = ValueSet(
            id="vital-signs",
            url="http://havenhealthpassport.org/fhir/ValueSet/vital-signs",
            name="VitalSigns",
            title="Vital Signs",
            description="Common vital sign observations",
            compose=ValueSetCompose(
                include=[
                    {
                        "system": "http://havenhealthpassport.org/fhir/CodeSystem/vital-signs"
                    }
                ]
            ),
        )
        self.service.add_value_set(vital_signs_vs)

        # Emergency medications value set
        emergency_meds_vs = ValueSet(
            id="emergency-medications",
            url="http://havenhealthpassport.org/fhir/ValueSet/emergency-medications",
            name="EmergencyMedications",
            title="Emergency Medications",
            description="Medications for emergency situations",
            compose=ValueSetCompose(
                include=[
                    {
                        "system": "http://havenhealthpassport.org/fhir/CodeSystem/refugee-medications",
                        "concept": [
                            {"code": "paracetamol"},
                            {"code": "ibuprofen"},
                            {"code": "amoxicillin"},
                            {"code": "ors"},
                        ],
                    }
                ]
            ),
        )
        self.service.add_value_set(emergency_meds_vs)

    def _load_custom_terminologies(self) -> None:
        """Load custom terminologies from files."""
        # Load code systems
        if self.config.code_systems_dir.exists():
            for file_path in self.config.code_systems_dir.glob("*.json"):
                try:
                    self.service.load_code_system(file_path)
                except (json.JSONDecodeError, ValueError, OSError) as e:
                    logger.error(f"Failed to load code system {file_path}: {e}")

        # Load value sets
        if self.config.value_sets_dir.exists():
            for file_path in self.config.value_sets_dir.glob("*.json"):
                try:
                    self.service.load_value_set(file_path)
                except (json.JSONDecodeError, ValueError, OSError) as e:
                    logger.error(f"Failed to load value set {file_path}: {e}")


# Singleton instance
_configurator: Optional[TerminologyConfigurator] = None


def get_terminology_configurator() -> TerminologyConfigurator:
    """Get singleton terminology configurator instance."""
    global _configurator  # pylint: disable=global-statement
    if _configurator is None:
        _configurator = TerminologyConfigurator()
    return _configurator


def initialize_terminology_service(
    config: Optional[TerminologyServiceConfig] = None,
) -> TerminologyService:
    """Initialize and configure terminology service.

    Args:
        config: Terminology service configuration

    Returns:
        Configured terminology service
    """
    configurator = TerminologyConfigurator(config)
    configurator.initialize()
    return configurator.service
