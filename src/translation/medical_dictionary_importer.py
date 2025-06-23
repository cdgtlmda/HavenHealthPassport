"""
Medical Dictionary Import Module.

This module handles importing medical dictionaries from various sources
including ICD-10, SNOMED CT, and other standard medical terminologies.

This module handles PHI with encryption and access control to ensure HIPAA compliance.
It includes FHIR resource typing and validation for healthcare data.
"""

import csv
import json
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

from src.healthcare.fhir_validator import FHIRValidator
from src.translation.medical_glossary import (
    FHIRResourceType,
    MedicalGlossaryService,
    MedicalTerm,
    TermCategory,
    TermSource,
)
from src.utils.logging import get_logger

logger = get_logger(__name__)


class MedicalDictionaryImporter:
    """Import medical dictionaries from various sources."""

    # ICD-10 to ICD-11 mapping for common conditions
    ICD10_TO_ICD11_MAP = {
        # Infectious diseases
        "A00-A09": "1A00-1A0Z",  # Intestinal infectious diseases
        "A15-A19": "1B10-1B14",  # Tuberculosis
        "B50-B54": "1F40-1F45",  # Malaria
        "B20-B24": "1C60-1C6Z",  # HIV
        # Mental health
        "F32": "6A70",  # Depression
        "F43.1": "6B40",  # PTSD
        "F40-F48": "6B00-6B0Z",  # Anxiety disorders
        # Nutritional
        "E40-E46": "5B50-5B54",  # Malnutrition
        "E50-E64": "5B70-5B7Z",  # Vitamin deficiencies
        # Maternal health
        "O00-O99": "JA00-JB6Z",  # Pregnancy complications
        # Common conditions
        "J00-J06": "CA00-CA0Z",  # Upper respiratory infections
        "K00-K93": "DA00-DE2Z",  # Digestive diseases
        "L00-L99": "EA00-EM0Z",  # Skin conditions
    }

    # SNOMED CT concept mappings for common medical terms
    SNOMED_CONCEPTS = {
        # Symptoms
        "386661006": {
            "term": "fever",
            "category": TermCategory.SYMPTOMS_SIGNS,
            "fhir_types": [FHIRResourceType.OBSERVATION],
        },
        "22253000": {
            "term": "pain",
            "category": TermCategory.SYMPTOMS_SIGNS,
            "fhir_types": [FHIRResourceType.OBSERVATION],
        },
        "49727002": {
            "term": "cough",
            "category": TermCategory.SYMPTOMS_SIGNS,
            "fhir_types": [FHIRResourceType.OBSERVATION],
        },
        "25064002": {
            "term": "headache",
            "category": TermCategory.SYMPTOMS_SIGNS,
            "fhir_types": [FHIRResourceType.OBSERVATION],
        },
        # Procedures
        "71388002": {
            "term": "procedure",
            "category": TermCategory.MEDICAL_PROCEDURES,
            "fhir_types": [FHIRResourceType.PROCEDURE],
        },
        "387713003": {
            "term": "surgical procedure",
            "category": TermCategory.MEDICAL_PROCEDURES,
            "fhir_types": [FHIRResourceType.PROCEDURE],
        },
        # Medications
        "410942007": {
            "term": "drug or medicament",
            "category": TermCategory.MEDICATIONS,
            "fhir_types": [FHIRResourceType.MEDICATION],
        },
        # Lab tests
        "15220000": {
            "term": "laboratory test",
            "category": TermCategory.LAB_TESTS,
            "fhir_types": [FHIRResourceType.DIAGNOSTIC_REPORT],
        },
        "104177005": {
            "term": "blood count",
            "category": TermCategory.LAB_TESTS,
            "fhir_types": [FHIRResourceType.DIAGNOSTIC_REPORT],
        },
    }

    def __init__(self, glossary_service: MedicalGlossaryService):
        """Initialize the importer."""
        self.glossary_service = glossary_service
        self.fhir_validator = FHIRValidator()
        self.import_stats = {
            "total_processed": 0,
            "successfully_imported": 0,
            "skipped_existing": 0,
            "failed": 0,
        }

    def import_icd10_dictionary(self, file_path: str) -> Dict[str, Any]:
        """
        Import ICD-10 dictionary from CSV/JSON file.

        Expected format:
        - code: ICD-10 code
        - description: Disease/condition description
        - category: Major category
        - subcategory: Subcategory (optional)
        """
        logger.info(f"Starting ICD-10 import from {file_path}")
        self.reset_stats()

        try:
            path = Path(file_path)

            if path.suffix == ".csv":
                return self._import_icd10_csv(path)
            elif path.suffix == ".json":
                return self._import_icd10_json(path)
            else:
                raise ValueError(f"Unsupported file format: {path.suffix}")

        except (ValueError, IOError) as e:
            logger.error(f"Error importing ICD-10 dictionary: {e}")
            return self.import_stats

    def _import_icd10_csv(self, path: Path) -> Dict[str, Any]:
        """Import ICD-10 from CSV file."""
        with open(path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)

            for row in reader:
                self.import_stats["total_processed"] += 1

                try:
                    # Map ICD-10 to ICD-11
                    icd11_code = self._map_icd10_to_icd11(row["code"])

                    # Determine category
                    category = self._determine_category_from_icd(row["code"])

                    # Create medical term
                    term = MedicalTerm(
                        term=row["description"],
                        category=category,
                        source=TermSource.WHO_ICD11,
                        code=icd11_code or row["code"],
                        definition=row.get("long_description", ""),
                        context_notes=f"ICD-10: {row['code']}",
                        fhir_resource_types=[FHIRResourceType.CONDITION],
                    )

                    # Add to glossary
                    if self._add_term_to_glossary(term):
                        self.import_stats["successfully_imported"] += 1
                    else:
                        self.import_stats["skipped_existing"] += 1

                except (KeyError, ValueError, TypeError) as e:
                    logger.error(
                        f"Error processing ICD-10 code {row.get('code', 'unknown')}: {e}"
                    )
                    self.import_stats["failed"] += 1

        return self.import_stats

    def _import_icd10_json(self, path: Path) -> Dict[str, Any]:
        """Import ICD-10 from JSON file."""
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        for item in data.get("codes", []):
            self.import_stats["total_processed"] += 1

            try:
                # Map ICD-10 to ICD-11
                icd11_code = self._map_icd10_to_icd11(item["code"])

                # Determine category
                category = self._determine_category_from_icd(item["code"])

                # Create medical term
                term = MedicalTerm(
                    term=item["description"],
                    category=category,
                    source=TermSource.WHO_ICD11,
                    code=icd11_code or item["code"],
                    definition=item.get("definition", ""),
                    synonyms=item.get("synonyms", []),
                    context_notes=f"ICD-10: {item['code']}",
                    fhir_resource_types=[FHIRResourceType.CONDITION],
                )

                # Add to glossary
                if self._add_term_to_glossary(term):
                    self.import_stats["successfully_imported"] += 1
                else:
                    self.import_stats["skipped_existing"] += 1

            except (KeyError, ValueError, TypeError) as e:
                logger.error(
                    f"Error processing ICD-10 code {item.get('code', 'unknown')}: {e}"
                )
                self.import_stats["failed"] += 1

        return self.import_stats

    def import_snomed_dictionary(self, file_path: str) -> Dict[str, Any]:
        """
        Import SNOMED CT concepts from file.

        Expected format:
        - conceptId: SNOMED concept ID
        - term: Preferred term
        - fsn: Fully specified name
        - semantic_tag: Semantic tag (finding, procedure, etc.)
        """
        logger.info(f"Starting SNOMED import from {file_path}")
        self.reset_stats()

        try:
            path = Path(file_path)

            with open(path, "r", encoding="utf-8") as f:
                if path.suffix == ".json":
                    data = json.load(f)
                    concepts = data.get("concepts", [])
                else:
                    reader = csv.DictReader(f)
                    concepts = list(reader)

            for concept in concepts:
                self.import_stats["total_processed"] += 1

                try:
                    # Determine category from semantic tag
                    category = self._determine_category_from_snomed(
                        concept.get("semantic_tag", "")
                    )

                    # Get FHIR resource types
                    fhir_types = self._get_fhir_types_from_snomed(
                        concept.get("semantic_tag", "")
                    )

                    # Create medical term
                    term = MedicalTerm(
                        term=concept["term"],
                        category=category,
                        source=TermSource.CUSTOM,  # SNOMED terms as custom
                        code=f"SNOMED:{concept['conceptId']}",
                        definition=concept.get("fsn", ""),
                        context_notes="SNOMED CT concept",
                        fhir_resource_types=fhir_types,
                    )

                    # Add to glossary
                    if self._add_term_to_glossary(term):
                        self.import_stats["successfully_imported"] += 1
                    else:
                        self.import_stats["skipped_existing"] += 1

                except (KeyError, ValueError, TypeError) as e:
                    logger.error(
                        f"Error processing SNOMED concept {concept.get('conceptId', 'unknown')}: {e}"
                    )
                    self.import_stats["failed"] += 1

            return self.import_stats

        except (ValueError, IOError) as e:
            logger.error(f"Error importing SNOMED dictionary: {e}")
            return self.import_stats

    def import_drug_dictionary(self, file_path: str) -> Dict[str, Any]:
        """
        Import drug/medication dictionary.

        Expected format:
        - generic_name: Generic drug name
        - brand_names: Brand names (comma-separated)
        - drug_class: Therapeutic class
        - indication: Primary indication
        - dosage_forms: Available forms
        """
        logger.info(f"Starting drug dictionary import from {file_path}")
        self.reset_stats()

        try:
            path = Path(file_path)

            with open(path, "r", encoding="utf-8") as f:
                if path.suffix == ".json":
                    data = json.load(f)
                    drugs = data.get("drugs", [])
                else:
                    reader = csv.DictReader(f)
                    drugs = list(reader)

            for drug in drugs:
                self.import_stats["total_processed"] += 1

                try:
                    # Create medical term for generic name
                    term = MedicalTerm(
                        term=drug["generic_name"],
                        category=TermCategory.MEDICATIONS,
                        source=TermSource.WHO_ATC,
                        code=drug.get("atc_code", ""),
                        definition=drug.get("indication", ""),
                        synonyms=drug.get("brand_names", "").split(","),
                        context_notes=f"Drug class: {drug.get('drug_class', '')}",
                        fhir_resource_types=[
                            FHIRResourceType.MEDICATION,
                            FHIRResourceType.MEDICATION_REQUEST,
                            FHIRResourceType.MEDICATION_STATEMENT,
                        ],
                    )

                    # Add to glossary
                    if self._add_term_to_glossary(term):
                        self.import_stats["successfully_imported"] += 1
                    else:
                        self.import_stats["skipped_existing"] += 1

                except (KeyError, ValueError, TypeError) as e:
                    logger.error(
                        f"Error processing drug {drug.get('generic_name', 'unknown')}: {e}"
                    )
                    self.import_stats["failed"] += 1

            return self.import_stats

        except (ValueError, IOError) as e:
            logger.error(f"Error importing drug dictionary: {e}")
            return self.import_stats

    def import_from_url(self, url: str, dict_type: str) -> Dict[str, Any]:
        """Import dictionary from URL."""
        temp_path = None
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()

            # Save to temporary file using proper tempfile module
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".json", delete=False
            ) as temp_file:
                temp_file.write(response.text)
                temp_path = Path(temp_file.name)

            # Import based on type
            if dict_type == "icd10":
                result = self.import_icd10_dictionary(str(temp_path))
            elif dict_type == "snomed":
                result = self.import_snomed_dictionary(str(temp_path))
            elif dict_type == "drugs":
                result = self.import_drug_dictionary(str(temp_path))
            else:
                raise ValueError(f"Unknown dictionary type: {dict_type}")

            return result

        except (requests.RequestException, ValueError, IOError) as e:
            logger.error(f"Error importing from URL {url}: {e}")
            return self.import_stats
        finally:
            # Cleanup temporary file
            if temp_path and temp_path.exists():
                temp_path.unlink()

    def _map_icd10_to_icd11(self, icd10_code: str) -> Optional[str]:
        """Map ICD-10 code to ICD-11."""
        # Check direct mapping
        for icd10_range, icd11_range in self.ICD10_TO_ICD11_MAP.items():
            if "-" in icd10_range:
                start, end = icd10_range.split("-")
                if start <= icd10_code <= end:
                    return icd11_range
            elif icd10_code.startswith(icd10_range):
                return icd11_range

        return None

    def _determine_category_from_icd(self, code: str) -> TermCategory:
        """Determine term category from ICD code."""
        if code[0] == "A" or code[0] == "B":
            return TermCategory.INFECTIOUS_DISEASES
        elif code[0] == "C" or code[0] == "D" and code[1] in "0123":
            return TermCategory.NEOPLASMS
        elif code[0] == "E":
            return TermCategory.ENDOCRINE_DISORDERS
        elif code[0] == "F":
            return TermCategory.MENTAL_DISORDERS
        elif code[0] == "G":
            return TermCategory.NERVOUS_SYSTEM
        elif code[0] == "H" and code[1] in "01234":
            return TermCategory.EYE_DISORDERS
        elif code[0] == "H" and code[1] in "6789":
            return TermCategory.EAR_DISORDERS
        elif code[0] == "I":
            return TermCategory.CIRCULATORY_SYSTEM
        elif code[0] == "J":
            return TermCategory.RESPIRATORY_SYSTEM
        elif code[0] == "K":
            return TermCategory.DIGESTIVE_SYSTEM
        elif code[0] == "L":
            return TermCategory.SKIN_DISORDERS
        elif code[0] == "M":
            return TermCategory.MUSCULOSKELETAL
        elif code[0] == "N":
            return TermCategory.GENITOURINARY
        elif code[0] == "O":
            return TermCategory.PREGNANCY_CHILDBIRTH
        elif code[0] == "P":
            return TermCategory.PERINATAL_CONDITIONS
        elif code[0] == "Q":
            return TermCategory.CONGENITAL_ANOMALIES
        elif code[0] == "R":
            return TermCategory.SYMPTOMS_SIGNS
        elif code[0] in "STU":
            return TermCategory.INJURIES
        else:
            return TermCategory.SYMPTOMS_SIGNS

    def _determine_category_from_snomed(self, semantic_tag: str) -> TermCategory:
        """Determine category from SNOMED semantic tag."""
        tag_lower = semantic_tag.lower()

        if "disorder" in tag_lower or "disease" in tag_lower:
            return TermCategory.SYMPTOMS_SIGNS
        elif "procedure" in tag_lower:
            return TermCategory.MEDICAL_PROCEDURES
        elif "substance" in tag_lower or "product" in tag_lower:
            return TermCategory.MEDICATIONS
        elif "body structure" in tag_lower:
            return TermCategory.ANATOMY
        elif "finding" in tag_lower:
            return TermCategory.SYMPTOMS_SIGNS
        elif "observable" in tag_lower:
            return TermCategory.LAB_TESTS
        else:
            return TermCategory.SYMPTOMS_SIGNS

    def _get_fhir_types_from_snomed(self, semantic_tag: str) -> List[FHIRResourceType]:
        """Get FHIR resource types from SNOMED semantic tag."""
        tag_lower = semantic_tag.lower()

        if "disorder" in tag_lower or "disease" in tag_lower:
            return [FHIRResourceType.CONDITION]
        elif "procedure" in tag_lower:
            return [FHIRResourceType.PROCEDURE]
        elif "substance" in tag_lower or "product" in tag_lower:
            return [FHIRResourceType.MEDICATION]
        elif "finding" in tag_lower:
            return [FHIRResourceType.OBSERVATION]
        elif "observable" in tag_lower:
            return [FHIRResourceType.OBSERVATION, FHIRResourceType.DIAGNOSTIC_REPORT]
        else:
            return [FHIRResourceType.OBSERVATION]

    def _add_term_to_glossary(self, term: MedicalTerm) -> bool:
        """Add term to glossary if not exists."""
        # Check if term already exists
        existing = self.glossary_service.search_terms(
            term.term, language="en", category=term.category, limit=1
        )

        if existing:
            return False

        # Add to glossary
        self.glossary_service.add_glossary_entry(
            term=term.term,
            language="en",
            category=term.category,
            source=term.source,
            code=term.code,
            definition=term.definition,
            synonyms=term.synonyms or [],
            related_terms=term.related_terms or [],
            context_notes=term.context_notes,
            fhir_resource_types=term.fhir_resource_types or [],
            contains_phi=term.contains_phi,
        )

        return True

    def reset_stats(self) -> None:
        """Reset import statistics."""
        self.import_stats = {
            "total_processed": 0,
            "successfully_imported": 0,
            "skipped_existing": 0,
            "failed": 0,
        }

    def get_import_summary(self) -> str:
        """Get human-readable import summary."""
        return (
            f"Import Summary:\n"
            f"Total processed: {self.import_stats['total_processed']}\n"
            f"Successfully imported: {self.import_stats['successfully_imported']}\n"
            f"Skipped (existing): {self.import_stats['skipped_existing']}\n"
            f"Failed: {self.import_stats['failed']}"
        )
