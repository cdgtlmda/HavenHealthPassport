"""SNOMED CT Translation Configuration.

This module handles SNOMED CT (Systematized Nomenclature of Medicine Clinical Terms)
translations across multiple languages for medical terminology standardization.

This module handles PHI with encryption and access control to ensure HIPAA compliance.
It includes FHIR Resource typing and validation for healthcare data.
"""

import asyncio
import json
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

from src.config import settings
from src.healthcare.fhir.validators import FHIRValidator
from src.security.access_control import AccessPermission, require_permission
from src.security.audit import audit_phi_access
from src.security.encryption import EncryptionService
from src.translation.medical.dictionary_importer import (
    DictionaryType,
    medical_dictionary_importer,
)
from src.translation.medical.snomed_service import get_snomed_service
from src.utils.logging import get_logger

logger = get_logger(__name__)


class SNOMEDHierarchy(str, Enum):
    """SNOMED CT concept hierarchies."""

    CLINICAL_FINDING = "404684003"
    PROCEDURE = "71388002"
    OBSERVABLE_ENTITY = "363787002"
    BODY_STRUCTURE = "123037004"
    ORGANISM = "410607006"
    SUBSTANCE = "105590001"
    PHARMACEUTICAL = "373873005"
    SPECIMEN = "123038009"
    SPECIAL_CONCEPT = "370115009"
    PHYSICAL_OBJECT = "260787004"
    PHYSICAL_FORCE = "78621006"
    EVENT = "272379006"
    ENVIRONMENT = "308916002"
    SITUATION = "243796009"
    SOCIAL_CONTEXT = "48176007"


@dataclass
class SNOMEDConcept:
    """SNOMED CT concept with translations."""

    concept_id: str
    fsn: str  # Fully Specified Name
    preferred_term: str
    semantic_tag: str
    hierarchy: SNOMEDHierarchy
    parent_concepts: List[str]
    translations: Dict[str, str]  # language -> translation
    synonyms: Dict[str, List[str]]  # language -> synonyms
    is_active: bool
    definition: Optional[str]
    clinical_usage_notes: Dict[str, str]  # language -> notes


class SNOMEDTranslationManager:
    """Manages SNOMED CT translations across languages."""

    # Common SNOMED concepts for refugee health
    REFUGEE_HEALTH_CONCEPTS = {
        # Symptoms
        "21522001": "Abdominal pain",
        "49727002": "Cough",
        "25064002": "Headache",
        "386661006": "Fever",
        "422587007": "Nausea",
        "422400008": "Vomiting",
        "62315008": "Diarrhea",
        "271807003": "Skin rash",
        "267036007": "Shortness of breath",
        "22253000": "Pain",
        # Conditions
        "38341003": "Hypertension",
        "73211009": "Diabetes mellitus",
        "195967001": "Asthma",
        "84114007": "Heart failure",
        "56717001": "Tuberculosis",
        "235856003": "Hepatitis B",
        "50920009": "Hepatitis C",
        "86406008": "HIV infection",
        "363346000": "Malignant neoplasm",
        "14183003": "Chronic obstructive pulmonary disease",
        # Mental Health
        "35489007": "Depression",
        "197480006": "Anxiety disorder",
        "47505003": "Post-traumatic stress disorder",
        "13746004": "Bipolar disorder",
        "58214004": "Schizophrenia",
        # Procedures
        "80146002": "Appendectomy",
        "387713003": "Surgical procedure",
        "103693007": "Diagnostic procedure",
        "18629005": "Administration of medication",
        "410546004": "Counseling",
        # Medications (substance)
        "387207008": "Ibuprofen",
        "387517004": "Paracetamol",
        "387151007": "Amoxicillin",
        "387531004": "Metformin",
        "386013003": "Insulin",
    }

    def __init__(self) -> None:
        """Initialize SNOMED translation manager."""
        self.concepts: Dict[str, SNOMEDConcept] = {}
        self.hierarchy_index: Dict[SNOMEDHierarchy, Set[str]] = {}
        self.fhir_validator = FHIRValidator()
        self.encryption_service = EncryptionService(
            kms_key_id="alias/haven-health-default"
        )
        self._initialize_common_concepts()

    def validate_fhir_resource(self, resource: dict) -> bool:
        """Validate FHIR resource structure and requirements."""
        return self.fhir_validator.validate_resource(resource)

    @audit_phi_access("process_phi_data")
    @require_permission(AccessPermission.READ_PHI)
    def process_with_phi_protection(self, data: dict) -> dict:
        """Process data with PHI protection and audit logging."""
        # Encrypt sensitive fields
        sensitive_fields = ["name", "birthDate", "ssn", "address"]
        encrypted_data = data.copy()

        for field in sensitive_fields:
            if field in encrypted_data:
                value_to_encrypt: str = str(encrypted_data[field])
                encrypted_data[field] = self.encryption_service.encrypt(
                    value_to_encrypt.encode("utf-8")
                )

        return encrypted_data

    def _initialize_common_concepts(self) -> None:
        """Initialize translations for common SNOMED concepts."""
        # Example: Fever concept
        self.concepts["386661006"] = SNOMEDConcept(
            concept_id="386661006",
            fsn="Fever (finding)",
            preferred_term="Fever",
            semantic_tag="finding",
            hierarchy=SNOMEDHierarchy.CLINICAL_FINDING,
            parent_concepts=["404684003"],  # Clinical finding
            translations={
                "es": "Fiebre",
                "fr": "Fièvre",
                "ar": "حمى",
                "sw": "Homa",
                "fa": "تب",
                "ps": "تبه",
                "ur": "بخار",
                "bn": "জ্বর",
                "hi": "बुखार",
            },
            synonyms={
                "en": ["Pyrexia", "Elevated temperature", "Febrile"],
                "es": ["Pirexia", "Temperatura elevada", "Febril"],
                "ar": ["ارتفاع الحرارة", "حرارة مرتفعة"],
            },
            is_active=True,
            definition="Body temperature above the normal range",
            clinical_usage_notes={
                "en": "Document temperature reading and associated symptoms",
                "es": "Documentar lectura de temperatura y síntomas asociados",
                "ar": "توثيق قراءة درجة الحرارة والأعراض المصاحبة",
            },
        )

        # PTSD concept
        self.concepts["47505003"] = SNOMEDConcept(
            concept_id="47505003",
            fsn="Post-traumatic stress disorder (disorder)",
            preferred_term="Post-traumatic stress disorder",
            semantic_tag="disorder",
            hierarchy=SNOMEDHierarchy.CLINICAL_FINDING,
            parent_concepts=["197480006"],  # Anxiety disorder
            translations={
                "es": "Trastorno de estrés postraumático",
                "fr": "Trouble de stress post-traumatique",
                "ar": "اضطراب ما بعد الصدمة",
                "sw": "Ugonjwa wa msongo baada ya kiwewe",
                "fa": "اختلال استرس پس از سانحه",
                "ps": "د صدمې وروسته فشار ګډوډي",
                "ur": "صدمے کے بعد کا تناؤ",
                "bn": "মানসিক আঘাত পরবর্তী চাপ",
                "hi": "अभिघातजन्य तनाव विकार",
            },
            synonyms={
                "en": ["PTSD", "Combat stress disorder"],
                "es": ["TEPT", "Trastorno por estrés traumático"],
            },
            is_active=True,
            definition="Anxiety disorder triggered by experiencing traumatic events",
            clinical_usage_notes={
                "en": "Screen for trauma history, nightmares, flashbacks, avoidance",
                "es": "Evaluar historia de trauma, pesadillas, flashbacks, evitación",
                "ar": "فحص تاريخ الصدمة والكوابيس والذكريات المؤلمة والتجنب",
            },
        )

        # Build hierarchy index
        for concept_id, concept in self.concepts.items():
            if concept.hierarchy not in self.hierarchy_index:
                self.hierarchy_index[concept.hierarchy] = set()
            self.hierarchy_index[concept.hierarchy].add(concept_id)

    async def import_snomed_translations(
        self, file_path: str, source_language: str = "en"
    ) -> None:
        """Import SNOMED CT translations from file."""
        logger.info(f"Importing SNOMED translations from {file_path}")

        result = await medical_dictionary_importer.import_dictionary(
            DictionaryType.SNOMED, file_path, language=source_language
        )

        if result["status"] == "success":
            self._process_imported_concepts(source_language)

    def _process_imported_concepts(self, language: str) -> None:
        """Process imported SNOMED concepts."""
        concepts = medical_dictionary_importer.search_term(
            "", dictionary_type=DictionaryType.SNOMED, language=language, fuzzy=False
        )

        for concept_entry in concepts:
            if concept_entry.code not in self.concepts:
                hierarchy = self._determine_hierarchy(concept_entry.metadata)

                self.concepts[concept_entry.code] = SNOMEDConcept(
                    concept_id=concept_entry.code,
                    fsn=concept_entry.metadata.get("fully_specified_name", ""),
                    preferred_term=concept_entry.primary_term,
                    semantic_tag=concept_entry.category or "",
                    hierarchy=hierarchy,
                    parent_concepts=[],
                    translations={language: concept_entry.primary_term},
                    synonyms={language: concept_entry.synonyms},
                    is_active=concept_entry.metadata.get("active", True),
                    definition=concept_entry.description,
                    clinical_usage_notes={},
                )

    def _determine_hierarchy(self, metadata: Dict[str, Any]) -> SNOMEDHierarchy:
        """Determine SNOMED hierarchy from metadata."""
        semantic_tag = metadata.get("semanticTag", "").lower()

        hierarchy_mapping = {
            "finding": SNOMEDHierarchy.CLINICAL_FINDING,
            "disorder": SNOMEDHierarchy.CLINICAL_FINDING,
            "procedure": SNOMEDHierarchy.PROCEDURE,
            "body structure": SNOMEDHierarchy.BODY_STRUCTURE,
            "substance": SNOMEDHierarchy.SUBSTANCE,
            "product": SNOMEDHierarchy.PHARMACEUTICAL,
            "organism": SNOMEDHierarchy.ORGANISM,
        }

        for tag, hierarchy in hierarchy_mapping.items():
            if tag in semantic_tag:
                return hierarchy

        return SNOMEDHierarchy.SPECIAL_CONCEPT

    def get_translation(
        self, concept_id: str, language: str, include_synonyms: bool = False
    ) -> Optional[Dict[str, Any]]:
        """Get SNOMED concept translation."""
        concept = self.concepts.get(concept_id)
        if not concept:
            return None

        result: Dict[str, Any] = {
            "concept_id": concept_id,
            "preferred_term": concept.translations.get(
                language, concept.preferred_term
            ),
            "semantic_tag": concept.semantic_tag,
            "hierarchy": concept.hierarchy.value,
            "is_active": concept.is_active,
        }

        if include_synonyms:
            result["synonyms"] = concept.synonyms.get(language, [])

        if concept.clinical_usage_notes.get(language):
            result["clinical_notes"] = concept.clinical_usage_notes[language]

        return result

    def search_concepts(
        self,
        search_term: str,
        language: str,
        hierarchy: Optional[SNOMEDHierarchy] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Search SNOMED concepts by term."""
        results = []
        search_lower = search_term.lower()

        # Get concepts to search
        if hierarchy:
            concept_ids = self.hierarchy_index.get(hierarchy, set())
        else:
            concept_ids = set(self.concepts.keys())

        for concept_id in concept_ids:
            concept = self.concepts[concept_id]

            # Search in preferred term
            term = concept.translations.get(language, concept.preferred_term)
            if search_lower in term.lower():
                results.append(self._format_concept_result(concept, language))
                if len(results) >= limit:
                    break
                continue

            # Search in synonyms
            synonyms = concept.synonyms.get(language, [])
            for synonym in synonyms:
                if search_lower in synonym.lower():
                    results.append(self._format_concept_result(concept, language))
                    break

            if len(results) >= limit:
                break

        return results

    def _format_concept_result(
        self, concept: SNOMEDConcept, language: str
    ) -> Dict[str, Any]:
        """Format concept for search results."""
        return {
            "concept_id": concept.concept_id,
            "preferred_term": concept.translations.get(
                language, concept.preferred_term
            ),
            "fsn": concept.fsn,
            "semantic_tag": concept.semantic_tag,
            "hierarchy": concept.hierarchy.value,
            "is_active": concept.is_active,
        }

    def get_concept_by_hierarchy(
        self, hierarchy: SNOMEDHierarchy, language: str, active_only: bool = True
    ) -> List[Dict[str, Any]]:
        """Get all concepts in a hierarchy."""
        results = []

        concept_ids = self.hierarchy_index.get(hierarchy, set())
        for concept_id in concept_ids:
            concept = self.concepts[concept_id]

            if active_only and not concept.is_active:
                continue

            results.append(self._format_concept_result(concept, language))

        return sorted(results, key=lambda x: x["preferred_term"])

    def get_refugee_health_concepts(
        self, language: str, category: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get SNOMED concepts relevant to refugee health."""
        results = []

        categories = {
            "symptoms": ["21522001", "49727002", "25064002", "386661006"],
            "conditions": ["38341003", "73211009", "195967001", "56717001"],
            "mental_health": ["35489007", "197480006", "47505003"],
            "procedures": ["387713003", "103693007", "18629005", "410546004"],
            "medications": ["387207008", "387517004", "387151007", "387531004"],
        }

        if category and category in categories:
            concept_ids = categories[category]
        else:
            concept_ids = list(self.REFUGEE_HEALTH_CONCEPTS.keys())

        for concept_id in concept_ids:
            concept = self.concepts.get(concept_id)
            if concept:
                result = self._format_concept_result(concept, language)
                result["english_term"] = self.REFUGEE_HEALTH_CONCEPTS.get(
                    concept_id, concept.preferred_term
                )
                results.append(result)

        return results

    def validate_concept_usage(
        self, concept_id: str, context: Dict[str, Any]
    ) -> Tuple[bool, List[str]]:
        """Validate SNOMED concept usage in clinical context."""
        issues = []

        concept = self.concepts.get(concept_id)
        if not concept:
            return False, ["Invalid SNOMED concept ID"]

        if not concept.is_active:
            issues.append("Concept is inactive/deprecated")

        # Validate hierarchy appropriateness
        if "expected_hierarchy" in context:
            expected = context["expected_hierarchy"]
            if concept.hierarchy != expected:
                issues.append(
                    f"Concept hierarchy mismatch: expected {expected}, "
                    f"got {concept.hierarchy}"
                )

        # Additional clinical validations could be added here

        return len(issues) == 0, issues

    def map_to_icd10(self, concept_id: str) -> List[str]:
        """Map SNOMED concept to ICD-10 codes."""
        # CRITICAL: Use real SNOMED service in production
        # settings imported at module level

        if settings.environment.lower() in ["production", "staging"]:
            try:
                # asyncio and get_snomed_service imported at module level

                service = get_snomed_service()

                # Run async method synchronously
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

                icd10_codes = loop.run_until_complete(service.map_to_icd10(concept_id))

                return icd10_codes

            except Exception as e:
                logger.error(f"Failed to use SNOMED service: {e}")
                # Don't fall back to simplified mapping in production
                raise RuntimeError(
                    "CRITICAL: SNOMED to ICD-10 mapping failed. "
                    "Cannot proceed without proper medical terminology mapping. "
                    "Configure SNOMED terminology server!"
                ) from e

        # Development only - simplified mapping
        logger.warning(
            "Using simplified SNOMED to ICD-10 mapping in development. "
            "Production MUST use real SNOMED service!"
        )

        # Simplified mapping - NEVER use in production
        snomed_to_icd10_map = {
            "38341003": ["I10"],  # Hypertension
            "73211009": ["E11"],  # Type 2 diabetes
            "195967001": ["J45"],  # Asthma
            "56717001": ["A15-A19"],  # TB range
            "47505003": ["F43.1"],  # PTSD
            "35489007": ["F32", "F33"],  # Depression
        }

        return snomed_to_icd10_map.get(concept_id, [])

    def export_concept_translations(
        self,
        output_path: str,
        languages: List[str],
        hierarchy: Optional[SNOMEDHierarchy] = None,
    ) -> None:
        """Export SNOMED translations."""
        export_data = []

        if hierarchy:
            concept_ids = self.hierarchy_index.get(hierarchy, set())
        else:
            concept_ids = set(self.concepts.keys())

        for concept_id in concept_ids:
            concept = self.concepts[concept_id]

            row = {
                "concept_id": concept_id,
                "fsn": concept.fsn,
                "semantic_tag": concept.semantic_tag,
                "hierarchy": concept.hierarchy.value,
                "is_active": concept.is_active,
            }

            # Add translations
            for lang in languages:
                row[f"term_{lang}"] = concept.translations.get(
                    lang, concept.preferred_term
                )
                row[f"synonyms_{lang}"] = "; ".join(concept.synonyms.get(lang, []))

            export_data.append(row)

        # Write to file
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(export_data, f, ensure_ascii=False, indent=2)

        logger.info(f"Exported {len(export_data)} SNOMED concepts")


# Global SNOMED manager
snomed_manager = SNOMEDTranslationManager()
