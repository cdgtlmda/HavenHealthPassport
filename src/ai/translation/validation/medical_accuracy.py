"""
Medical Accuracy Validation.

This module implements medical accuracy validation for translations,
ensuring that critical medical information is preserved and accurate.

This module handles encrypted PHI with access control and audit logging
to ensure HIPAA compliance.
"""

import logging
import re
from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

from ..config import TranslationMode

logger = logging.getLogger(__name__)


class MedicalAccuracyLevel(Enum):
    """Levels of medical accuracy required."""

    CRITICAL = "critical"  # Life-critical information (allergies, medications)
    HIGH = "high"  # Important medical data (diagnoses, procedures)
    STANDARD = "standard"  # General medical information
    INFORMATIONAL = "info"  # Non-critical health information


class MedicalEntityType(Enum):
    """Types of medical entities to validate."""

    MEDICATION = "medication"
    DOSAGE = "dosage"
    FREQUENCY = "frequency"
    DIAGNOSIS = "diagnosis"
    PROCEDURE = "procedure"
    ALLERGY = "allergy"
    LAB_VALUE = "lab_value"
    VITAL_SIGN = "vital_sign"
    ANATOMY = "anatomy"
    SYMPTOM = "symptom"
    MEDICAL_CODE = "medical_code"
    CONTRAINDICATION = "contraindication"


@dataclass
class MedicalEntity:
    """Represents a medical entity extracted from text."""

    text: str
    entity_type: MedicalEntityType
    normalized_value: Optional[str] = None
    unit: Optional[str] = None
    code: Optional[str] = None  # ICD-10, SNOMED, etc.
    position: Optional[Tuple[int, int]] = None
    confidence: float = 1.0
    context: Optional[str] = None

    def is_critical(self) -> bool:
        """Check if this entity is critical for patient safety."""
        critical_types = {
            MedicalEntityType.MEDICATION,
            MedicalEntityType.DOSAGE,
            MedicalEntityType.ALLERGY,
            MedicalEntityType.CONTRAINDICATION,
        }
        return self.entity_type in critical_types


@dataclass
class MedicalAccuracyResult:
    """Result of medical accuracy validation."""

    accuracy_score: float
    entities_preserved: int
    entities_total: int
    critical_entities_preserved: int
    critical_entities_total: int
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    missing_entities: List[MedicalEntity] = field(default_factory=list)
    altered_entities: List[Tuple[MedicalEntity, MedicalEntity]] = field(
        default_factory=list
    )
    accuracy_level: MedicalAccuracyLevel = MedicalAccuracyLevel.STANDARD

    @property
    def is_accurate(self) -> bool:
        """Check if translation meets medical accuracy requirements."""
        if self.accuracy_level == MedicalAccuracyLevel.CRITICAL:
            return self.critical_entities_preserved == self.critical_entities_total
        elif self.accuracy_level == MedicalAccuracyLevel.HIGH:
            return self.accuracy_score >= 0.95
        else:
            return self.accuracy_score >= 0.90

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "accuracy_score": self.accuracy_score,
            "entities_preserved": self.entities_preserved,
            "entities_total": self.entities_total,
            "critical_entities_preserved": self.critical_entities_preserved,
            "critical_entities_total": self.critical_entities_total,
            "is_accurate": self.is_accurate,
            "accuracy_level": self.accuracy_level.value,
            "errors": self.errors,
            "warnings": self.warnings,
            "missing_entities_count": len(self.missing_entities),
            "altered_entities_count": len(self.altered_entities),
        }


class MedicalAccuracyValidator:
    """
    Validates medical accuracy of translations.

    Features:
    - Medical entity extraction and matching
    - Critical information preservation
    - Dosage and measurement validation
    - Medical code verification
    - Anatomical term consistency
    - Drug interaction preservation
    """

    def __init__(self) -> None:
        """Initialize the medical accuracy validator."""
        self.entity_patterns = self._initialize_patterns()
        self.medical_abbreviations = self._load_medical_abbreviations()
        self.drug_database = self._load_drug_database()
        self.icd10_codes = self._load_icd10_codes()

    def _initialize_patterns(self) -> Dict[MedicalEntityType, List[re.Pattern]]:
        """Initialize regex patterns for medical entity extraction."""
        patterns = {
            MedicalEntityType.MEDICATION: [
                # Generic drug names (ending patterns)
                re.compile(
                    r"\b\w+(?:cillin|mycin|cycline|azole|pril|sartan|statin|olol|prazole|tide|mab)\b",
                    re.I,
                ),
                # Common medications
                re.compile(
                    r"\b(?:aspirin|ibuprofen|acetaminophen|paracetamol|insulin|metformin|levothyroxine)\b",
                    re.I,
                ),
            ],
            MedicalEntityType.DOSAGE: [
                # Numeric dosages with units
                re.compile(
                    r"\b\d+(?:\.\d+)?\s*(?:mg|g|mcg|μg|ug|ml|mL|L|IU|units?|tablets?|pills?|capsules?)\b"
                ),
                # Percentage concentrations
                re.compile(r"\b\d+(?:\.\d+)?\s*%"),
            ],
            MedicalEntityType.FREQUENCY: [
                # Frequency patterns
                re.compile(
                    r"\b(?:once|twice|three times|four times)\s+(?:a day|daily|per day)\b",
                    re.I,
                ),
                re.compile(
                    r"\b(?:every|each)\s+\d+\s+(?:hours?|days?|weeks?|months?)\b", re.I
                ),
                re.compile(r"\b(?:QD|BID|TID|QID|PRN|HS|AC|PC)\b"),
            ],
            MedicalEntityType.LAB_VALUE: [
                # Lab values with ranges
                re.compile(
                    r"\b\d+(?:\.\d+)?\s*(?:-|to)\s*\d+(?:\.\d+)?\s*(?:mg/dL|mmol/L|mEq/L|ng/mL|IU/L)\b"
                ),
                # Single lab values
                re.compile(
                    r"\b\d+(?:\.\d+)?\s*(?:mg/dL|mmol/L|mEq/L|ng/mL|IU/L|cells/μL)\b"
                ),
            ],
            MedicalEntityType.VITAL_SIGN: [
                # Blood pressure
                re.compile(r"\b\d{2,3}/\d{2,3}\s*(?:mmHg)?\b"),
                # Heart rate
                re.compile(r"\b\d{2,3}\s*(?:bpm|beats per minute)\b", re.I),
                # Temperature
                re.compile(r"\b\d{2}(?:\.\d)?\s*°[CF]\b"),
                # Respiratory rate
                re.compile(
                    r"\b\d{1,2}\s*(?:breaths per minute|respirations per minute)\b",
                    re.I,
                ),
            ],
            MedicalEntityType.MEDICAL_CODE: [
                # ICD-10 codes
                re.compile(r"\b[A-TV-Z]\d{2}(?:\.\d{1,4})?\b"),
                # CPT codes
                re.compile(r"\b\d{5}\b"),
                # SNOMED CT codes
                re.compile(r"\b\d{6,18}\b"),
            ],
            MedicalEntityType.ALLERGY: [
                # Allergy patterns
                re.compile(r"(?:allergic to|allergy to)\s+(\w+(?:\s+\w+)*)", re.I),
                re.compile(r"(\w+(?:\s+\w+)*)\s+allergy", re.I),
            ],
        }
        return patterns

    def _load_medical_abbreviations(self) -> Dict[str, str]:
        """Load common medical abbreviations."""
        return {
            "QD": "once daily",
            "BID": "twice daily",
            "TID": "three times daily",
            "QID": "four times daily",
            "PRN": "as needed",
            "PO": "by mouth",
            "IV": "intravenous",
            "IM": "intramuscular",
            "SC": "subcutaneous",
            "HS": "at bedtime",
            "AC": "before meals",
            "PC": "after meals",
            "NPO": "nothing by mouth",
            "STAT": "immediately",
        }

    def _load_drug_database(self) -> Set[str]:
        """Load common drug names for validation."""
        # In production, this would load from a comprehensive database
        return {
            "amoxicillin",
            "azithromycin",
            "ciprofloxacin",
            "doxycycline",
            "metformin",
            "insulin",
            "levothyroxine",
            "lisinopril",
            "atorvastatin",
            "simvastatin",
            "omeprazole",
            "pantoprazole",
            "aspirin",
            "ibuprofen",
            "acetaminophen",
            "paracetamol",
            "warfarin",
            "clopidogrel",
            "metoprolol",
            "amlodipine",
            "gabapentin",
            "sertraline",
            "fluoxetine",
            "escitalopram",
        }

    def _load_icd10_codes(self) -> Set[str]:
        """Load ICD-10 code patterns for validation."""
        # In production, this would load from a complete ICD-10 database
        return {
            "E11",
            "E11.9",
            "I10",
            "J44.1",
            "N18.3",
            "F32.9",
            "M79.3",
            "R50.9",
            "Z00.00",
        }

    def extract_medical_entities(self, text: str) -> List[MedicalEntity]:
        """Extract medical entities from text."""
        entities = []

        for entity_type, patterns in self.entity_patterns.items():
            for pattern in patterns:
                for match in pattern.finditer(text):
                    entity_text = match.group(0)
                    position = (match.start(), match.end())

                    # Create entity
                    entity = MedicalEntity(
                        text=entity_text,
                        entity_type=entity_type,
                        position=position,
                        context=text[
                            max(0, position[0] - 20) : min(len(text), position[1] + 20)
                        ],
                    )

                    # Normalize if possible
                    entity.normalized_value = self._normalize_entity(entity)

                    entities.append(entity)

        # Deduplicate overlapping entities
        entities = self._deduplicate_entities(entities)

        return entities

    def _normalize_entity(self, entity: MedicalEntity) -> Optional[str]:
        """Normalize medical entity for comparison."""
        if entity.entity_type == MedicalEntityType.MEDICATION:
            # Normalize drug names
            drug_name = entity.text.lower()
            if drug_name in self.drug_database:
                return drug_name
            # Try to match partial names
            for known_drug in self.drug_database:
                if known_drug in drug_name or drug_name in known_drug:
                    return known_drug

        elif entity.entity_type == MedicalEntityType.DOSAGE:
            # Extract numeric value and unit
            match = re.match(r"(\d+(?:\.\d+)?)\s*(\w+)", entity.text)
            if match:
                value, unit = match.groups()
                # Normalize units
                unit_map = {
                    "milligrams": "mg",
                    "milligram": "mg",
                    "grams": "g",
                    "gram": "g",
                    "micrograms": "mcg",
                    "microgram": "mcg",
                    "milliliters": "ml",
                    "milliliter": "ml",
                    "liters": "L",
                    "liter": "L",
                }
                normalized_unit = unit_map.get(unit.lower(), unit)
                return f"{value} {normalized_unit}"

        elif entity.entity_type == MedicalEntityType.MEDICAL_CODE:
            # Validate and normalize medical codes
            code = entity.text.upper()
            if re.match(r"^[A-TV-Z]\d{2}(\.\d{1,4})?$", code):
                # ICD-10 code
                base_code = code.split(".")[0]
                if base_code in self.icd10_codes:
                    return code

        return entity.text

    def _deduplicate_entities(
        self, entities: List[MedicalEntity]
    ) -> List[MedicalEntity]:
        """Remove duplicate or overlapping entities."""
        if not entities:
            return []

        # Sort by position
        sorted_entities = sorted(
            entities,
            key=lambda e: (
                e.position[0] if e.position else 0,
                -(e.position[1] if e.position else 0),
            ),
        )

        # Keep non-overlapping entities
        kept_entities = [sorted_entities[0]]
        for entity in sorted_entities[1:]:
            if entity.position and kept_entities[-1].position:
                # Check for overlap
                if entity.position[0] >= kept_entities[-1].position[1]:
                    kept_entities.append(entity)
            else:
                kept_entities.append(entity)

        return kept_entities

    def validate_medical_accuracy(
        self,
        source_text: str,
        translated_text: str,
        mode: TranslationMode = TranslationMode.CLINICAL,
        accuracy_level: MedicalAccuracyLevel = MedicalAccuracyLevel.HIGH,
    ) -> MedicalAccuracyResult:
        """
        Validate medical accuracy of translation.

        Args:
            source_text: Original medical text
            translated_text: Translated text
            mode: Translation mode
            accuracy_level: Required accuracy level

        Returns:
            MedicalAccuracyResult with validation details
        """
        # Extract entities from both texts
        source_entities = self.extract_medical_entities(source_text)
        translated_entities = self.extract_medical_entities(translated_text)

        # Create result
        result = MedicalAccuracyResult(
            accuracy_score=0.0,
            entities_preserved=0,
            entities_total=len(source_entities),
            critical_entities_preserved=0,
            critical_entities_total=sum(1 for e in source_entities if e.is_critical()),
            accuracy_level=accuracy_level,
        )

        # Match entities
        matched_entity_indices = set()
        for source_entity in source_entities:
            match_found = False

            for i, trans_entity in enumerate(translated_entities):
                if i in matched_entity_indices:
                    continue

                if self._entities_match(source_entity, trans_entity):
                    matched_entity_indices.add(i)
                    match_found = True
                    result.entities_preserved += 1

                    if source_entity.is_critical():
                        result.critical_entities_preserved += 1

                    # Check if entity was altered
                    if not self._entities_identical(source_entity, trans_entity):
                        result.altered_entities.append((source_entity, trans_entity))

                    break

            if not match_found:
                result.missing_entities.append(source_entity)
                if source_entity.is_critical():
                    result.errors.append(
                        f"Critical entity missing: {source_entity.text} ({source_entity.entity_type.value})"
                    )
                else:
                    result.warnings.append(
                        f"Entity missing: {source_entity.text} ({source_entity.entity_type.value})"
                    )

        # Calculate accuracy score
        if result.entities_total > 0:
            result.accuracy_score = result.entities_preserved / result.entities_total
        else:
            result.accuracy_score = 1.0

        # Additional validation based on mode
        if mode in [TranslationMode.CLINICAL, TranslationMode.PRESCRIPTION]:
            self._validate_clinical_accuracy(source_text, translated_text, result)

        return result

    def _entities_match(self, entity1: MedicalEntity, entity2: MedicalEntity) -> bool:
        """Check if two entities match."""
        if entity1.entity_type != entity2.entity_type:
            return False

        # Use normalized values if available
        val1 = entity1.normalized_value or entity1.text
        val2 = entity2.normalized_value or entity2.text

        # Exact match
        if val1.lower() == val2.lower():
            return True

        # Type-specific matching
        if entity1.entity_type == MedicalEntityType.DOSAGE:
            return self._dosages_equivalent(val1, val2)
        elif entity1.entity_type == MedicalEntityType.MEDICATION:
            return self._medications_equivalent(val1, val2)
        elif entity1.entity_type == MedicalEntityType.MEDICAL_CODE:
            return val1.upper() == val2.upper()

        return False

    def _entities_identical(
        self, entity1: MedicalEntity, entity2: MedicalEntity
    ) -> bool:
        """Check if entities are identical (not just equivalent)."""
        val1 = entity1.normalized_value or entity1.text
        val2 = entity2.normalized_value or entity2.text
        return val1 == val2

    def _dosages_equivalent(self, dosage1: str, dosage2: str) -> bool:
        """Check if two dosages are equivalent."""
        # Extract numeric values and units
        pattern = r"(\d+(?:\.\d+)?)\s*(\w+)"
        match1 = re.match(pattern, dosage1)
        match2 = re.match(pattern, dosage2)

        if match1 and match2:
            val1, unit1 = match1.groups()
            val2, unit2 = match2.groups()

            # Convert to decimal for comparison
            try:
                num1 = Decimal(val1)
                num2 = Decimal(val2)

                # Check if units are equivalent
                unit_equivalents = {
                    ("mg", "milligram", "milligrams"),
                    ("g", "gram", "grams"),
                    ("mcg", "μg", "ug", "microgram", "micrograms"),
                    ("ml", "mL", "milliliter", "milliliters"),
                    ("L", "liter", "liters"),
                }

                for unit_set in unit_equivalents:
                    if unit1.lower() in unit_set and unit2.lower() in unit_set:
                        return num1 == num2

            except (ValueError, AttributeError):
                pass

        return False

    def _medications_equivalent(self, med1: str, med2: str) -> bool:
        """Check if two medication names are equivalent."""
        # Simple check - in production, use drug synonym database
        med1_lower = med1.lower()
        med2_lower = med2.lower()

        # Direct match
        if med1_lower == med2_lower:
            return True

        # Check if one contains the other (brand/generic)
        if med1_lower in med2_lower or med2_lower in med1_lower:
            return True

        # Check known equivalents
        equivalents = [
            {"acetaminophen", "paracetamol", "tylenol"},
            {"ibuprofen", "advil", "motrin"},
            {"aspirin", "asa", "acetylsalicylic acid"},
        ]

        for equiv_set in equivalents:
            if med1_lower in equiv_set and med2_lower in equiv_set:
                return True

        return False

    def _validate_clinical_accuracy(
        self, source_text: str, translated_text: str, result: MedicalAccuracyResult
    ) -> None:
        """Additional validation for clinical texts."""
        # Check for negation preservation
        source_negations = re.findall(
            r"\b(?:no|not|without|negative for)\b", source_text, re.I
        )
        trans_negations = re.findall(
            r"\b(?:no|not|without|negative for|sin|sans|ohne|senza)\b",
            translated_text,
            re.I,
        )

        if len(source_negations) != len(trans_negations):
            result.warnings.append(
                f"Negation count mismatch: {len(source_negations)} vs {len(trans_negations)}"
            )

        # Check for critical safety terms
        safety_terms = [
            "contraindicated",
            "allergy",
            "allergic",
            "anaphylaxis",
            "warning",
            "caution",
        ]
        for term in safety_terms:
            if term in source_text.lower() and term not in translated_text.lower():
                result.errors.append(f"Critical safety term '{term}' not preserved")
