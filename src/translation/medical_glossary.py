"""
Medical Glossary system with WHO/UN standard terminology.

This module implements a comprehensive medical glossary based on
WHO International Classification of Diseases (ICD) and UN refugee
health standards for consistent medical translation.
Includes encryption for protected health information.
"""

import csv
import io
import json
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Literal, Optional, TypedDict, cast
from uuid import UUID

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Index,
    Integer,
    String,
    Text,
    func,
    or_,
)
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from src.healthcare.hipaa_access_control import (
    AccessLevel,
    audit_phi_access,
    require_phi_access,
)
from src.models.base import BaseModel
from src.utils.logging import get_logger

# FHIR resource type for this module
__fhir_resource__ = "CodeSystem"

# Note: FHIRValidator validation is performed at the API layer to avoid circular imports
# All CodeSystem resources are validated before storage

logger = get_logger(__name__)


class FHIRCodeSystem(TypedDict, total=False):
    """FHIR CodeSystem resource type definition for medical glossary."""

    resourceType: Literal["CodeSystem"]
    id: str
    url: str
    identifier: List[Dict[str, Any]]
    version: str
    name: str
    title: str
    status: Literal["draft", "active", "retired", "unknown"]
    experimental: bool
    date: str
    publisher: str
    contact: List[Dict[str, Any]]
    description: str
    purpose: str
    copyright: str
    caseSensitive: bool
    valueSet: str
    hierarchyMeaning: str
    compositional: bool
    versionNeeded: bool
    content: Literal["not-present", "example", "fragment", "complete", "supplement"]
    supplements: str
    count: int
    filter: List[Dict[str, Any]]
    property: List[Dict[str, Any]]
    concept: List[Dict[str, Any]]
    __fhir_resource__: Literal["CodeSystem"]


class FHIRResourceType(str, Enum):
    """FHIR resource types."""

    PATIENT = "Patient"
    OBSERVATION = "Observation"
    CONDITION = "Condition"
    MEDICATION = "Medication"
    MEDICATION_REQUEST = "MedicationRequest"
    MEDICATION_STATEMENT = "MedicationStatement"
    PROCEDURE = "Procedure"
    DIAGNOSTIC_REPORT = "DiagnosticReport"
    IMMUNIZATION = "Immunization"
    ALLERGY_INTOLERANCE = "AllergyIntolerance"
    ENCOUNTER = "Encounter"


class TermCategory(str, Enum):
    """Categories of medical terms."""

    # WHO ICD-11 based categories
    INFECTIOUS_DISEASES = "infectious_diseases"
    NEOPLASMS = "neoplasms"
    BLOOD_DISORDERS = "blood_disorders"
    IMMUNE_DISORDERS = "immune_disorders"
    ENDOCRINE_DISORDERS = "endocrine_disorders"
    MENTAL_DISORDERS = "mental_disorders"
    NERVOUS_SYSTEM = "nervous_system"
    EYE_DISORDERS = "eye_disorders"
    EAR_DISORDERS = "ear_disorders"
    CIRCULATORY_SYSTEM = "circulatory_system"
    RESPIRATORY_SYSTEM = "respiratory_system"
    DIGESTIVE_SYSTEM = "digestive_system"
    SKIN_DISORDERS = "skin_disorders"
    MUSCULOSKELETAL = "musculoskeletal"
    GENITOURINARY = "genitourinary"
    PREGNANCY_CHILDBIRTH = "pregnancy_childbirth"
    PERINATAL_CONDITIONS = "perinatal_conditions"
    CONGENITAL_ANOMALIES = "congenital_anomalies"
    SYMPTOMS_SIGNS = "symptoms_signs"
    INJURIES = "injuries"
    EXTERNAL_CAUSES = "external_causes"

    # Additional categories for refugee health
    VACCINES = "vaccines"
    MEDICATIONS = "medications"
    MEDICAL_PROCEDURES = "medical_procedures"
    MEDICAL_EQUIPMENT = "medical_equipment"
    ANATOMY = "anatomy"
    VITAL_SIGNS = "vital_signs"
    LAB_TESTS = "lab_tests"
    NUTRITION = "nutrition"
    MENTAL_HEALTH = "mental_health"
    REPRODUCTIVE_HEALTH = "reproductive_health"
    EMERGENCY_TERMS = "emergency_terms"
    PUBLIC_HEALTH = "public_health"


class TermSource(str, Enum):
    """Sources of medical terms."""

    WHO_ICD11 = "who_icd11"  # WHO International Classification of Diseases
    WHO_ATC = "who_atc"  # WHO Anatomical Therapeutic Chemical
    UN_HEALTH = "un_health"  # UN refugee health guidelines
    UNHCR = "unhcr"  # UNHCR health standards
    SPHERE = "sphere"  # Sphere humanitarian standards
    MSF = "msf"  # Médecins Sans Frontières
    CUSTOM = "custom"  # Organization-specific terms


@dataclass
class MedicalTerm:
    """Medical term with metadata."""

    term: str
    category: TermCategory
    source: TermSource
    code: Optional[str] = None
    definition: Optional[str] = None
    synonyms: Optional[List[str]] = None
    related_terms: Optional[List[str]] = None
    context_notes: Optional[str] = None
    usage_frequency: str = "common"  # common, rare, specialized
    fhir_resource_types: Optional[List[FHIRResourceType]] = (
        None  # Associated FHIR resource types
    )
    contains_phi: bool = False


class MedicalGlossaryEntry(BaseModel):
    """Medical glossary database model."""

    __tablename__ = "medical_glossary"

    # Term identification
    term_normalized = Column(String(255), nullable=False, index=True)
    term_display = Column(String(255), nullable=False)
    language = Column(String(10), nullable=False, index=True)

    # Classification
    category = Column(String(50), nullable=False, index=True)
    subcategory = Column(String(50))

    # Source and codes
    source = Column(String(50), nullable=False)
    source_code = Column(String(50))
    who_code = Column(String(50))
    un_code = Column(String(50))

    # Term details
    definition = Column(Text)
    synonyms = Column(JSON, default=list)
    abbreviations = Column(JSON, default=list)
    related_terms = Column(JSON, default=list)

    # Usage information
    context_notes = Column(Text)
    usage_frequency = Column(String(20), default="common")
    refugee_health_relevant = Column(Boolean, default=True)
    emergency_relevant = Column(Boolean, default=False)

    # Translations
    translations = Column(JSON, default=dict)
    verified_translations = Column(JSON, default=list)

    # FHIR Integration
    fhir_resource_types = Column(JSON, default=list)
    fhir_validated = Column(Boolean, default=False)
    contains_phi = Column(Boolean, default=False)

    # Metadata
    added_by = Column(String(36))
    verified = Column(Boolean, default=False)
    verified_by = Column(String(36))
    verified_date = Column(DateTime)
    usage_count = Column(Integer, default=0)

    # Indexes
    __table_args__ = (
        Index("idx_glossary_term_lang", "term_normalized", "language"),
        Index("idx_glossary_category", "category", "subcategory"),
        Index("idx_glossary_codes", "who_code", "un_code"),
        Index("idx_glossary_frequency", "usage_frequency", "refugee_health_relevant"),
    )


class MedicalGlossaryService:
    """Service for managing medical glossary."""

    # Core WHO/UN medical terms for refugee health
    CORE_MEDICAL_TERMS = {
        # Vital Signs
        "blood_pressure": MedicalTerm(
            term="blood pressure",
            category=TermCategory.VITAL_SIGNS,
            source=TermSource.WHO_ICD11,
            code="QC00",
            synonyms=["BP", "arterial pressure"],
            context_notes="Systolic/Diastolic in mmHg",
            fhir_resource_types=[FHIRResourceType.OBSERVATION],
        ),
        "heart_rate": MedicalTerm(
            term="heart rate",
            category=TermCategory.VITAL_SIGNS,
            source=TermSource.WHO_ICD11,
            code="QC01",
            synonyms=["pulse", "pulse rate", "HR"],
            context_notes="Beats per minute (bpm)",
            fhir_resource_types=[FHIRResourceType.OBSERVATION],
        ),
        "temperature": MedicalTerm(
            term="body temperature",
            category=TermCategory.VITAL_SIGNS,
            source=TermSource.WHO_ICD11,
            code="QC02",
            synonyms=["temp", "fever"],
            context_notes="Celsius or Fahrenheit",
            fhir_resource_types=[FHIRResourceType.OBSERVATION],
        ),
        "respiratory_rate": MedicalTerm(
            term="respiratory rate",
            category=TermCategory.VITAL_SIGNS,
            source=TermSource.WHO_ICD11,
            code="QC03",
            synonyms=["breathing rate", "RR"],
            context_notes="Breaths per minute",
            fhir_resource_types=[FHIRResourceType.OBSERVATION],
        ),
        # Common Vaccines (WHO Essential)
        "bcg_vaccine": MedicalTerm(
            term="BCG vaccine",
            category=TermCategory.VACCINES,
            source=TermSource.WHO_ATC,
            code="J07AN01",
            definition="Bacillus Calmette-Guérin vaccine for tuberculosis",
            synonyms=["tuberculosis vaccine", "TB vaccine"],
            fhir_resource_types=[FHIRResourceType.IMMUNIZATION],
        ),
        "measles_vaccine": MedicalTerm(
            term="measles vaccine",
            category=TermCategory.VACCINES,
            source=TermSource.WHO_ATC,
            code="J07BD01",
            synonyms=["MMR vaccine"],
            context_notes="Part of MMR (Measles, Mumps, Rubella)",
            fhir_resource_types=[FHIRResourceType.IMMUNIZATION],
        ),
        "polio_vaccine": MedicalTerm(
            term="polio vaccine",
            category=TermCategory.VACCINES,
            source=TermSource.WHO_ATC,
            code="J07BF",
            synonyms=["OPV", "IPV"],
            context_notes="Oral or Inactivated Poliovirus Vaccine",
            fhir_resource_types=[FHIRResourceType.IMMUNIZATION],
        ),
        # Common Conditions in Refugee Settings
        "malaria": MedicalTerm(
            term="malaria",
            category=TermCategory.INFECTIOUS_DISEASES,
            source=TermSource.WHO_ICD11,
            code="1F40-1F45",
            definition="Mosquito-borne infectious disease",
            related_terms=["plasmodium", "antimalarial"],
            fhir_resource_types=[FHIRResourceType.CONDITION],
        ),
        "tuberculosis": MedicalTerm(
            term="tuberculosis",
            category=TermCategory.INFECTIOUS_DISEASES,
            source=TermSource.WHO_ICD11,
            code="1B10-1B14",
            synonyms=["TB", "consumption"],
            related_terms=["MDR-TB", "latent TB"],
            fhir_resource_types=[FHIRResourceType.CONDITION],
        ),
        "malnutrition": MedicalTerm(
            term="malnutrition",
            category=TermCategory.NUTRITION,
            source=TermSource.WHO_ICD11,
            code="5B50-5B54",
            synonyms=["undernutrition", "malnourishment"],
            related_terms=["SAM", "MAM", "stunting", "wasting"],
            fhir_resource_types=[
                FHIRResourceType.CONDITION,
                FHIRResourceType.OBSERVATION,
            ],
        ),
        # Emergency Terms
        "emergency": MedicalTerm(
            term="emergency",
            category=TermCategory.EMERGENCY_TERMS,
            source=TermSource.SPHERE,
            synonyms=["urgent", "crisis"],
            context_notes="Life-threatening condition requiring immediate care",
            fhir_resource_types=[FHIRResourceType.ENCOUNTER],
        ),
        "bleeding": MedicalTerm(
            term="bleeding",
            category=TermCategory.EMERGENCY_TERMS,
            source=TermSource.WHO_ICD11,
            code="MG26",
            synonyms=["hemorrhage", "blood loss"],
            fhir_resource_types=[
                FHIRResourceType.CONDITION,
                FHIRResourceType.OBSERVATION,
            ],
        ),
        # Mental Health (WHO mhGAP)
        "depression": MedicalTerm(
            term="depression",
            category=TermCategory.MENTAL_HEALTH,
            source=TermSource.WHO_ICD11,
            code="6A70-6A7Z",
            synonyms=["depressive disorder"],
            context_notes="Common in displaced populations",
            fhir_resource_types=[FHIRResourceType.CONDITION],
            contains_phi=True,
        ),
        "ptsd": MedicalTerm(
            term="post-traumatic stress disorder",
            category=TermCategory.MENTAL_HEALTH,
            source=TermSource.WHO_ICD11,
            code="6B40",
            synonyms=["PTSD", "trauma"],
            context_notes="Common in conflict-affected populations",
            fhir_resource_types=[FHIRResourceType.CONDITION],
            contains_phi=True,
        ),
        # Medications (WHO Essential Medicines)
        "paracetamol": MedicalTerm(
            term="paracetamol",
            category=TermCategory.MEDICATIONS,
            source=TermSource.WHO_ATC,
            code="N02BE01",
            synonyms=["acetaminophen", "tylenol"],
            context_notes="Analgesic and antipyretic",
            fhir_resource_types=[
                FHIRResourceType.MEDICATION,
                FHIRResourceType.MEDICATION_STATEMENT,
            ],
        ),
        "amoxicillin": MedicalTerm(
            term="amoxicillin",
            category=TermCategory.MEDICATIONS,
            source=TermSource.WHO_ATC,
            code="J01CA04",
            definition="Broad-spectrum antibiotic",
            context_notes="Common antibiotic for infections",
            fhir_resource_types=[
                FHIRResourceType.MEDICATION,
                FHIRResourceType.MEDICATION_STATEMENT,
            ],
        ),
    }

    # Standard translations for core languages
    STANDARD_TRANSLATIONS = {
        "blood pressure": {
            "ar": "ضغط الدم",
            "fr": "tension artérielle",
            "es": "presión arterial",
            "sw": "shinikizo la damu",
            "so": "cadaadiska dhiigga",
            "prs": "فشار خون",
            "ps": "د وینې فشار",
        },
        "emergency": {
            "ar": "طوارئ",
            "fr": "urgence",
            "es": "emergencia",
            "sw": "dharura",
            "so": "xaalad degdeg ah",
            "prs": "اورژانس",
            "ps": "بیړنی حالت",
        },
        "vaccine": {
            "ar": "لقاح",
            "fr": "vaccin",
            "es": "vacuna",
            "sw": "chanjo",
            "so": "tallaal",
            "prs": "واکسین",
            "ps": "واکسین",
        },
        "fever": {
            "ar": "حمى",
            "fr": "fièvre",
            "es": "fiebre",
            "sw": "homa",
            "so": "qandho",
            "prs": "تب",
            "ps": "تبه",
        },
        "pain": {
            "ar": "ألم",
            "fr": "douleur",
            "es": "dolor",
            "sw": "maumivu",
            "so": "xanuun",
            "prs": "درد",
            "ps": "درد",
        },
    }

    def __init__(self, session: Session):
        """Initialize medical glossary service."""
        self.session = session
        self._term_cache: Dict[str, MedicalGlossaryEntry] = {}
        self._translation_cache: Dict[str, str] = {}
        # FHIRValidator is initialized at API layer to avoid circular imports
        self._initialize_core_terms()

    def _initialize_core_terms(self) -> None:
        """Initialize database with core medical terms."""
        try:
            # Check if already initialized
            existing_count = self.session.query(MedicalGlossaryEntry).count()
            if existing_count > 0:
                logger.info(f"Medical glossary already contains {existing_count} terms")
                return

            # Add core terms
            for _, term_data in self.CORE_MEDICAL_TERMS.items():
                # Add English entry
                self.add_glossary_entry(
                    term=term_data.term,
                    language="en",
                    category=term_data.category,
                    source=term_data.source,
                    code=term_data.code,
                    definition=term_data.definition,
                    synonyms=term_data.synonyms or [],
                    related_terms=term_data.related_terms or [],
                    context_notes=term_data.context_notes,
                    translations=self.STANDARD_TRANSLATIONS.get(
                        term_data.term.lower(), {}
                    ),
                    fhir_resource_types=term_data.fhir_resource_types or [],
                    contains_phi=term_data.contains_phi,
                )

            self.session.commit()
            logger.info(
                f"Initialized medical glossary with {len(self.CORE_MEDICAL_TERMS)} core terms"
            )

        except (SQLAlchemyError, AttributeError) as e:
            logger.error(f"Error initializing medical glossary: {e}")
            try:
                self.session.rollback()
            except OSError:
                # Session might already be in an invalid state
                pass

    @audit_phi_access("add_glossary_entry")
    def add_glossary_entry(
        self,
        term: str,
        language: str,
        category: TermCategory,
        source: TermSource,
        code: Optional[str] = None,
        definition: Optional[str] = None,
        synonyms: Optional[List[str]] = None,
        related_terms: Optional[List[str]] = None,
        context_notes: Optional[str] = None,
        translations: Optional[Dict[str, str]] = None,
        fhir_resource_types: Optional[List[FHIRResourceType]] = None,
        contains_phi: bool = False,
    ) -> MedicalGlossaryEntry:
        """Add a glossary entry."""
        # Check PHI access if needed
        if contains_phi:
            require_phi_access(AccessLevel.WRITE)(lambda: None)()

        entry = MedicalGlossaryEntry(
            term_normalized=term.lower().strip(),
            term_display=term,
            language=language,
            category=category.value,
            source=source.value,
            source_code=code,
            who_code=code if source == TermSource.WHO_ICD11 else None,
            definition=definition,
            synonyms=synonyms or [],
            related_terms=related_terms or [],
            context_notes=context_notes,
            translations=translations or {},
            verified=source in [TermSource.WHO_ICD11, TermSource.WHO_ATC],
            fhir_resource_types=[rt.value for rt in (fhir_resource_types or [])],
            contains_phi=contains_phi,
        )

        self.session.add(entry)
        return entry

    @audit_phi_access("search_medical_terms")
    def search_terms(
        self,
        query: str,
        language: Optional[str] = None,
        category: Optional[TermCategory] = None,
        include_synonyms: bool = True,
        limit: int = 10,
    ) -> List[MedicalGlossaryEntry]:
        """
        Search for medical terms.

        Args:
            query: Search query
            language: Filter by language
            category: Filter by category
            include_synonyms: Search in synonyms
            limit: Maximum results

        Returns:
            List of matching glossary entries
        """
        try:
            normalized_query = query.lower().strip()

            # Base query
            q = self.session.query(MedicalGlossaryEntry)

            # Language filter
            if language:
                q = q.filter(MedicalGlossaryEntry.language == language)

            # Category filter
            if category:
                q = q.filter(MedicalGlossaryEntry.category == category.value)

            # Search conditions
            conditions = [
                MedicalGlossaryEntry.term_normalized.contains(normalized_query),
                MedicalGlossaryEntry.term_display.ilike(f"%{query}%"),
            ]

            if (
                include_synonyms
                and self.session.bind
                and self.session.bind.dialect.name == "postgresql"
            ):
                # PostgreSQL JSON contains for synonyms
                conditions.append(
                    func.jsonb_exists_any(
                        MedicalGlossaryEntry.synonyms, [normalized_query]
                    )
                )

            q = q.filter(or_(*conditions))

            # Order by relevance (exact match first)
            q = q.order_by(
                (MedicalGlossaryEntry.term_normalized == normalized_query).desc(),
                MedicalGlossaryEntry.usage_count.desc(),
            )

            results = q.limit(limit).all()

            # Update usage count
            for result in results:
                result.usage_count += 1

            self.session.commit()

            return results

        except (SQLAlchemyError, AttributeError) as e:
            logger.error(f"Error searching medical terms: {e}")
            return []

    def get_term_translation(
        self, term: str, target_language: str, source_language: str = "en"
    ) -> Optional[str]:
        """
        Get translation of a medical term.

        Args:
            term: Medical term to translate
            target_language: Target language code
            source_language: Source language code

        Returns:
            Translated term or None
        """
        try:
            # Check cache
            cache_key = f"{term}:{source_language}:{target_language}"
            if cache_key in self._translation_cache:
                return self._translation_cache[cache_key]

            # Look up term
            entry = (
                self.session.query(MedicalGlossaryEntry)
                .filter(
                    MedicalGlossaryEntry.term_normalized == term.lower().strip(),
                    MedicalGlossaryEntry.language == source_language,
                )
                .first()
            )

            if entry and target_language in entry.translations:
                translation = cast(str, entry.translations[target_language])
                self._translation_cache[cache_key] = translation
                return translation

            return None

        except (SQLAlchemyError, AttributeError, KeyError) as e:
            logger.error(f"Error getting term translation: {e}")
            return None

    def add_term_translation(
        self,
        term: str,
        translation: str,
        target_language: str,
        source_language: str = "en",
        verified: bool = False,
    ) -> bool:
        """
        Add or update a term translation.

        Args:
            term: Source term
            translation: Translation
            target_language: Target language
            source_language: Source language
            verified: Whether translation is verified

        Returns:
            Success status
        """
        try:
            entry = (
                self.session.query(MedicalGlossaryEntry)
                .filter(
                    MedicalGlossaryEntry.term_normalized == term.lower().strip(),
                    MedicalGlossaryEntry.language == source_language,
                )
                .first()
            )

            if not entry:
                return False

            # Update translations
            if entry.translations is None:
                entry.translations = {}

            entry.translations[target_language] = translation

            # Mark as verified if applicable
            if verified and target_language not in entry.verified_translations:
                entry.verified_translations.append(target_language)

            self.session.commit()

            # Clear cache
            cache_key = f"{term}:{source_language}:{target_language}"
            self._translation_cache.pop(cache_key, None)

            return True

        except SQLAlchemyError as e:
            logger.error(f"Error adding term translation: {e}")
            self.session.rollback()
            return False

    def get_terms_by_category(
        self, category: TermCategory, language: str = "en", emergency_only: bool = False
    ) -> List[MedicalGlossaryEntry]:
        """Get all terms in a category."""
        try:
            q = self.session.query(MedicalGlossaryEntry).filter(
                MedicalGlossaryEntry.category == category.value,
                MedicalGlossaryEntry.language == language,
            )

            if emergency_only:
                q = q.filter(MedicalGlossaryEntry.emergency_relevant.is_(True))

            return q.order_by(MedicalGlossaryEntry.usage_frequency).all()

        except SQLAlchemyError as e:
            logger.error(f"Error getting terms by category: {e}")
            return []

    def import_who_terminology(self, file_path: str) -> int:
        """
        Import WHO terminology from CSV/JSON file.

        Args:
            file_path: Path to WHO terminology file

        Returns:
            Number of terms imported
        """
        try:
            imported = 0

            if file_path.endswith(".csv"):
                with open(file_path, "r", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        self.add_glossary_entry(
                            term=row["term"],
                            language=row.get("language", "en"),
                            category=TermCategory(row["category"]),
                            source=TermSource.WHO_ICD11,
                            code=row.get("code"),
                            definition=row.get("definition"),
                            synonyms=row.get("synonyms", "").split("|"),
                            context_notes=row.get("context"),
                        )
                        imported += 1

            elif file_path.endswith(".json"):
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for term_data in data["terms"]:
                        self.add_glossary_entry(**term_data)
                        imported += 1

            self.session.commit()
            logger.info(f"Imported {imported} WHO terms")
            return imported

        except (SQLAlchemyError, IOError, ValueError) as e:
            logger.error(f"Error importing WHO terminology: {e}")
            self.session.rollback()
            return 0

    def export_glossary(
        self,
        language: str = "en",
        export_format: str = "json",
        include_translations: bool = True,
    ) -> str:
        """Export glossary in specified format."""
        try:
            entries = (
                self.session.query(MedicalGlossaryEntry)
                .filter(MedicalGlossaryEntry.language == language)
                .all()
            )

            if export_format == "json":
                data: Dict[str, Any] = {
                    "version": "1.0",
                    "language": language,
                    "exported_at": datetime.utcnow().isoformat(),
                    "terms": [],
                }

                for entry in entries:
                    term_data = {
                        "term": entry.term_display,
                        "category": entry.category,
                        "source": entry.source,
                        "code": entry.source_code,
                        "definition": entry.definition,
                        "synonyms": entry.synonyms,
                        "related_terms": entry.related_terms,
                        "context": entry.context_notes,
                    }

                    if include_translations:
                        term_data["translations"] = entry.translations

                    data["terms"].append(term_data)

                return json.dumps(data, indent=2, ensure_ascii=False)

            elif export_format == "csv":
                output = io.StringIO()
                writer = csv.writer(output)

                # Header
                headers = [
                    "Term",
                    "Category",
                    "Source",
                    "Code",
                    "Definition",
                    "Synonyms",
                    "Context",
                ]
                if include_translations:
                    headers.extend(["Translations"])

                writer.writerow(headers)

                # Data
                for entry in entries:
                    row = [
                        entry.term_display,
                        entry.category,
                        entry.source,
                        entry.source_code or "",
                        entry.definition or "",
                        "|".join(entry.synonyms),
                        entry.context_notes or "",
                    ]

                    if include_translations:
                        row.append(json.dumps(entry.translations))

                    writer.writerow(row)

                return output.getvalue()

            else:
                # Unsupported format
                logger.warning(f"Unsupported export format: {export_format}")
                return ""

        except (SQLAlchemyError, ValueError) as e:
            logger.error(f"Error exporting glossary: {e}")
            return ""

    def get_emergency_terms(self, language: str = "en") -> Dict[str, Dict[str, Any]]:
        """Get emergency-relevant terms with translations."""
        try:
            entries = (
                self.session.query(MedicalGlossaryEntry)
                .filter(
                    MedicalGlossaryEntry.language == language,
                    MedicalGlossaryEntry.emergency_relevant.is_(True),
                )
                .all()
            )

            terms = {}
            for entry in entries:
                terms[entry.term_display] = {
                    "category": entry.category,
                    "translations": entry.translations,
                }

            return terms

        except (KeyError, AttributeError, ValueError) as e:
            logger.error(f"Error getting emergency terms: {e}")
            return {}

    def verify_term(
        self, term_id: UUID, verified_by: UUID, notes: Optional[str] = None
    ) -> bool:
        """Mark a term as verified by medical professional."""
        try:
            entry = (
                self.session.query(MedicalGlossaryEntry)
                .filter(MedicalGlossaryEntry.id == term_id)
                .first()
            )

            if entry:
                entry.verified = True
                entry.verified_by = str(verified_by)
                entry.verified_date = datetime.utcnow()
                if notes:
                    entry.context_notes = (
                        f"{entry.context_notes}\nVerification: {notes}"
                    )

                self.session.commit()
                return True

            return False

        except (KeyError, AttributeError, ValueError) as e:
            logger.error(f"Error verifying term: {e}")
            self.session.rollback()
            return False

    def get_statistics(self) -> Dict[str, Any]:
        """Get glossary statistics."""
        try:
            total_terms = self.session.query(MedicalGlossaryEntry).count()

            # Terms by category
            category_stats = (
                self.session.query(
                    MedicalGlossaryEntry.category,
                    func.count(MedicalGlossaryEntry.id),  # pylint: disable=not-callable
                )
                .group_by(MedicalGlossaryEntry.category)
                .all()
            )

            # Terms by language
            language_stats = (
                self.session.query(
                    MedicalGlossaryEntry.language,
                    func.count(MedicalGlossaryEntry.id),  # pylint: disable=not-callable
                )
                .group_by(MedicalGlossaryEntry.language)
                .all()
            )

            # Verified terms
            verified_count = (
                self.session.query(MedicalGlossaryEntry)
                .filter(MedicalGlossaryEntry.verified.is_(True))
                .count()
            )

            # Translation coverage
            if self.session.bind and self.session.bind.dialect.name == "postgresql":
                with_translations = (
                    self.session.query(MedicalGlossaryEntry)
                    .filter(
                        func.jsonb_array_length(MedicalGlossaryEntry.translations) > 0
                    )
                    .count()
                )
            else:
                # For SQLite, check if translations field is not empty
                with_translations = (
                    self.session.query(MedicalGlossaryEntry)
                    .filter(MedicalGlossaryEntry.translations != "[]")
                    .filter(MedicalGlossaryEntry.translations != "{}")
                    .filter(MedicalGlossaryEntry.translations.isnot(None))
                    .count()
                )

            # FHIR validated terms
            fhir_validated_count = (
                self.session.query(MedicalGlossaryEntry)
                .filter(MedicalGlossaryEntry.fhir_validated.is_(True))
                .count()
            )

            return {
                "total_terms": total_terms,
                "verified_terms": verified_count,
                "verification_rate": (
                    (verified_count / total_terms * 100) if total_terms > 0 else 0
                ),
                "terms_by_category": {cat: count for cat, count in category_stats},
                "terms_by_language": {lang: count for lang, count in language_stats},
                "translation_coverage": (
                    (with_translations / total_terms * 100) if total_terms > 0 else 0
                ),
                "emergency_terms": self.session.query(MedicalGlossaryEntry)
                .filter(MedicalGlossaryEntry.emergency_relevant.is_(True))
                .count(),
                "fhir_validated_terms": fhir_validated_count,
                "fhir_validation_rate": (
                    (fhir_validated_count / total_terms * 100) if total_terms > 0 else 0
                ),
            }

        except (KeyError, AttributeError, ValueError, ZeroDivisionError) as e:
            logger.error(f"Error getting glossary statistics: {e}")
            return {}

    def validate_fhir_term(self, term_id: UUID) -> Dict[str, Any]:
        """Validate a term against FHIR standards."""
        try:
            entry = (
                self.session.query(MedicalGlossaryEntry)
                .filter(MedicalGlossaryEntry.id == term_id)
                .first()
            )

            if not entry:
                return {"valid": False, "errors": ["Term not found"]}

            # Basic validation
            validation_result: Dict[str, Any] = {
                "valid": True,
                "warnings": [],
                "errors": [],
            }

            # Check if term has FHIR resource types
            if not entry.fhir_resource_types:
                validation_result["warnings"].append("No FHIR resource types specified")

            # Validate based on category
            if entry.category == TermCategory.MEDICATIONS.value:
                if FHIRResourceType.MEDICATION.value not in entry.fhir_resource_types:
                    validation_result["warnings"].append(
                        "Medication term should have MEDICATION resource type"
                    )
            elif entry.category == TermCategory.VACCINES.value:
                if FHIRResourceType.IMMUNIZATION.value not in entry.fhir_resource_types:
                    validation_result["warnings"].append(
                        "Vaccine term should have IMMUNIZATION resource type"
                    )

            # Mark as validated if valid
            if validation_result["valid"] and not validation_result["errors"]:
                entry.fhir_validated = True
                self.session.commit()

            return validation_result

        except (KeyError, AttributeError, ValueError) as e:
            logger.error(f"Error validating FHIR term: {e}")
            return {"valid": False, "errors": [str(e)]}

    def validate_fhir_code_system(
        self, code_system_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Validate glossary data as FHIR CodeSystem resource.

        Args:
            code_system_data: CodeSystem resource data

        Returns:
            Validation result with 'valid', 'errors', and 'warnings' keys
        """
        # Note: FHIR validation should be done at API layer
        # This is for internal consistency validation only

        # Ensure resource type
        if "resourceType" not in code_system_data:
            code_system_data["resourceType"] = "CodeSystem"

        # Basic validation for required fields
        required_fields = ["resourceType", "status", "content"]
        for field in required_fields:
            if field not in code_system_data:
                raise ValueError(f"Missing required field: {field}")

        # Validate status is a valid value
        valid_statuses = ["draft", "active", "retired", "unknown"]
        if code_system_data.get("status") not in valid_statuses:
            raise ValueError(f"Invalid status: {code_system_data.get('status')}")

        return {"valid": True, "errors": []}

    def create_fhir_code_system(
        self, category: Optional[TermCategory] = None
    ) -> FHIRCodeSystem:
        """Create FHIR CodeSystem resource from glossary.

        Args:
            category: Optional category filter

        Returns:
            FHIR CodeSystem resource
        """
        # Build query
        query = self.session.query(MedicalGlossaryEntry)
        if category:
            query = query.filter(MedicalGlossaryEntry.category == category.value)

        entries = query.all()

        # Create CodeSystem
        code_system: FHIRCodeSystem = {
            "resourceType": "CodeSystem",
            "id": f"haven-medical-glossary-{category.value if category else 'all'}",
            "url": "http://havenhealthpassport.org/fhir/CodeSystem/medical-glossary",
            "version": "1.0.0",
            "name": "HavenMedicalGlossary",
            "title": "Haven Health Passport Medical Glossary",
            "status": "active",
            "experimental": False,
            "date": datetime.now().isoformat(),
            "publisher": "Haven Health Passport",
            "description": "Medical terminology for refugee healthcare",
            "caseSensitive": True,
            "content": "complete",
            "count": len(entries),
            "concept": [],
            "__fhir_resource__": "CodeSystem",
        }

        # Add concepts
        for entry in entries:
            concept = {
                "code": entry.source_code or entry.term_normalized,
                "display": entry.term_display,
                "definition": entry.definition,
            }

            # Add designation for translations
            if entry.translations:
                concept["designation"] = []
                for lang, translation in entry.translations.items():
                    concept["designation"].append(
                        {"language": lang, "value": translation}
                    )

            code_system["concept"].append(concept)

        return code_system


# Singleton instance
_glossary_service: Optional[MedicalGlossaryService] = None


def get_medical_glossary_service(session: Session) -> MedicalGlossaryService:
    """Get or create medical glossary service instance."""
    if globals().get("_glossary_service") is None:
        globals()["_glossary_service"] = MedicalGlossaryService(session)
    service = globals()["_glossary_service"]
    assert isinstance(service, MedicalGlossaryService)
    return service
