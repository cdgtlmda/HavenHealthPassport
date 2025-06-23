"""Medical terminology handling for accurate healthcare translations."""

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple, cast

from sqlalchemy.orm import Session

from src.healthcare.fhir_validator import FHIRValidator
from src.healthcare.hipaa_access_control import (
    AccessLevel,
    audit_phi_access,
    require_phi_access,
)
from src.translation.medical_glossary import get_medical_glossary_service
from src.utils.encryption import EncryptionService
from src.utils.logging import get_logger

if TYPE_CHECKING:
    from src.services.translation_service import TranslationDirection

logger = get_logger(__name__)


class MedicalTerminologyManager:
    """Manager for medical terminology and translations."""

    glossary_service: Optional[Any]

    def __init__(self) -> None:
        """Initialize medical terminology manager."""
        self.glossary_service = None  # Will be initialized when session is available
        self.encryption_service = EncryptionService()

    def get_medical_term_translation(
        self, term: str, source_lang: str, target_lang: str
    ) -> Optional[str]:
        """Get translation for a medical term."""
        if self.glossary_service is not None:
            if hasattr(self.glossary_service, "get_translation"):
                result = self.glossary_service.get_translation(
                    term, source_lang, target_lang
                )
                return cast(Optional[str], result)
        return None

    def add_medical_term(self, term: str, language: str, definition: str) -> bool:
        """Add a new medical term to the glossary."""
        if self.glossary_service is not None:
            if hasattr(self.glossary_service, "add_term"):
                result = self.glossary_service.add_term(term, language, definition)
                return cast(bool, result)
        return False


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


class MedicalCategory(str, Enum):
    """Categories of medical terms."""

    ANATOMY = "anatomy"
    CONDITION = "condition"
    MEDICATION = "medication"
    PROCEDURE = "procedure"
    DIAGNOSTIC = "diagnostic"
    SYMPTOM = "symptom"
    VITAL_SIGN = "vital_sign"
    LAB_TEST = "lab_test"
    EQUIPMENT = "equipment"
    DOSAGE = "dosage"
    ROUTE = "route"  # Route of administration
    FREQUENCY = "frequency"  # Medication frequency
    UNIT = "unit"  # Medical units


@dataclass
class MedicalTerm:
    """Represents a medical term with translations."""

    term: str
    category: MedicalCategory
    who_code: Optional[str] = None
    icd_code: Optional[str] = None
    snomed_code: Optional[str] = None
    translations: Dict[str, str] = field(default_factory=dict)
    synonyms: List[str] = field(default_factory=list)
    abbreviations: List[str] = field(default_factory=list)
    context_hints: List[str] = field(default_factory=list)
    usage_notes: Optional[str] = None
    fhir_resource_types: List[FHIRResourceType] = field(default_factory=list)
    contains_phi: bool = False


class MedicalTerminologyHandler:
    """Handles medical terminology identification, validation, and translation."""

    def __init__(self, db_session: Optional[Session] = None):
        """Initialize with optional database session for glossary integration."""
        self._db_session = db_session
        self._glossary_service = None
        self._fhir_validator: Optional[FHIRValidator] = (
            None  # Lazy load to avoid circular import
        )
        self._encryption_service = EncryptionService()
        self.terminology_db: Dict[str, MedicalTerm] = {}
        self._load_core_terminology()
        self._compile_patterns()

        if db_session:
            try:
                self._glossary_service = get_medical_glossary_service(db_session)
            except (ImportError, AttributeError, ValueError) as e:
                logger.warning(f"Could not initialize glossary service: {e}")

    @property
    def fhir_validator(self) -> FHIRValidator:
        """Get FHIR validator instance (lazy loaded)."""
        if self._fhir_validator is None:
            self._fhir_validator = FHIRValidator()
        # At this point, _fhir_validator is guaranteed to be FHIRValidator
        return self._fhir_validator

    # Common medical abbreviations that should be preserved
    PRESERVE_ABBREVIATIONS = {
        # Vital signs
        "BP",
        "HR",
        "RR",
        "T",
        "O2",
        "SpO2",
        "BMI",
        # Routes
        "PO",
        "IV",
        "IM",
        "SC",
        "SQ",
        "PR",
        "SL",
        "TD",
        # Frequencies
        "QD",
        "BID",
        "TID",
        "QID",
        "PRN",
        "STAT",
        "QHS",
        # Units
        "mg",
        "g",
        "kg",
        "mcg",
        "mL",
        "L",
        "IU",
        "mEq",
        # Tests
        "CBC",
        "BMP",
        "CMP",
        "ECG",
        "EKG",
        "MRI",
        "CT",
        "CXR",
        # Conditions
        "HIV",
        "AIDS",
        "TB",
        "DM",
        "HTN",
        "COPD",
        "UTI",
        "MI",
        # Other
        "NPO",
        "DNR",
        "CPR",
        "ICU",
        "ER",
        "OR",
    }

    # Medical units and their variations
    MEDICAL_UNITS = {
        # Weight
        "kilogram": ["kg", "kilograms", "kilo", "kilos"],
        "gram": ["g", "grams", "gm"],
        "milligram": ["mg", "milligrams"],
        "microgram": ["mcg", "µg", "micrograms"],
        # Volume
        "liter": ["L", "l", "liters", "litre", "litres"],
        "milliliter": ["mL", "ml", "milliliters", "millilitre"],
        "cubic_centimeter": ["cc", "cm³"],
        # Temperature
        "celsius": ["°C", "C", "celsius", "centigrade"],
        "fahrenheit": ["°F", "F", "fahrenheit"],
        # Pressure
        "mmHg": ["mmHg", "mm Hg", "millimeters of mercury"],
        # Time
        "hour": ["hr", "hrs", "hour", "hours"],
        "minute": ["min", "mins", "minute", "minutes"],
        "day": ["d", "day", "days"],
        "week": ["wk", "week", "weeks"],
        "month": ["mo", "month", "months"],
        "year": ["yr", "year", "years"],
    }

    # Dosage patterns
    DOSAGE_PATTERNS = [
        # Standard dosage: number + unit
        re.compile(r"\b(\d+(?:\.\d+)?)\s*(mg|g|mcg|mL|L|IU|mEq)\b", re.IGNORECASE),
        # Range dosage: number-number unit
        re.compile(
            r"\b(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)\s*(mg|g|mcg|mL|L)\b",
            re.IGNORECASE,
        ),
        # Concentration: number unit/unit
        re.compile(
            r"\b(\d+(?:\.\d+)?)\s*(mg|mcg)/(\d+(?:\.\d+)?)\s*(mL|L)\b", re.IGNORECASE
        ),
        # Percentage
        re.compile(r"\b(\d+(?:\.\d+)?)\s*%\b"),
    ]

    def _load_core_terminology(self) -> None:
        """Load core medical terminology database."""
        # Core medical terms with translations
        core_terms = [
            # Vital Signs
            MedicalTerm(
                term="blood pressure",
                category=MedicalCategory.VITAL_SIGN,
                who_code="VITAL_BP_001",
                translations={
                    "ar": "ضغط الدم",
                    "es": "presión arterial",
                    "fr": "pression artérielle",
                    "sw": "shinikizo la damu",
                    "so": "cadaadiska dhiigga",
                },
                abbreviations=["BP"],
                synonyms=["arterial pressure", "blood pressure reading"],
                fhir_resource_types=[FHIRResourceType.OBSERVATION],
            ),
            MedicalTerm(
                term="heart rate",
                category=MedicalCategory.VITAL_SIGN,
                who_code="VITAL_HR_001",
                translations={
                    "ar": "معدل ضربات القلب",
                    "es": "frecuencia cardíaca",
                    "fr": "fréquence cardiaque",
                    "sw": "kiwango cha mapigo ya moyo",
                },
                abbreviations=["HR", "pulse"],
                synonyms=["pulse rate", "cardiac rate"],
                fhir_resource_types=[FHIRResourceType.OBSERVATION],
            ),
            MedicalTerm(
                term="temperature",
                category=MedicalCategory.VITAL_SIGN,
                who_code="VITAL_T_001",
                translations={
                    "ar": "درجة الحرارة",
                    "es": "temperatura",
                    "fr": "température",
                    "sw": "joto la mwili",
                },
                abbreviations=["T", "temp"],
                fhir_resource_types=[FHIRResourceType.OBSERVATION],
            ),
            # Common Conditions
            MedicalTerm(
                term="diabetes",
                category=MedicalCategory.CONDITION,
                who_code="WHO_DIA_001",
                icd_code="E11",
                translations={
                    "ar": "السكري",
                    "es": "diabetes",
                    "fr": "diabète",
                    "sw": "kisukari",
                    "so": "sokorow",
                },
                synonyms=["diabetes mellitus", "DM"],
                context_hints=["chronic", "blood sugar", "insulin"],
                fhir_resource_types=[FHIRResourceType.CONDITION],
                contains_phi=True,
            ),
            MedicalTerm(
                term="hypertension",
                category=MedicalCategory.CONDITION,
                who_code="WHO_HTN_001",
                icd_code="I10",
                translations={
                    "ar": "ارتفاع ضغط الدم",
                    "es": "hipertensión",
                    "fr": "hypertension",
                    "sw": "shinikizo la juu la damu",
                },
                abbreviations=["HTN"],
                synonyms=["high blood pressure"],
                fhir_resource_types=[FHIRResourceType.CONDITION],
                contains_phi=True,
            ),
            MedicalTerm(
                term="tuberculosis",
                category=MedicalCategory.CONDITION,
                who_code="WHO_TB_001",
                icd_code="A15",
                translations={
                    "ar": "السل",
                    "es": "tuberculosis",
                    "fr": "tuberculose",
                    "sw": "kifua kikuu",
                    "so": "qaaxo",
                },
                abbreviations=["TB"],
                context_hints=["infectious", "lungs", "cough"],
                fhir_resource_types=[FHIRResourceType.CONDITION],
                contains_phi=True,
            ),
            MedicalTerm(
                term="malaria",
                category=MedicalCategory.CONDITION,
                who_code="WHO_MAL_001",
                icd_code="B50",
                translations={
                    "ar": "الملاريا",
                    "es": "malaria",
                    "fr": "paludisme",
                    "sw": "malaria",
                    "so": "duumo",
                },
                context_hints=["mosquito", "fever", "parasitic"],
                fhir_resource_types=[FHIRResourceType.CONDITION],
                contains_phi=True,
            ),
            # Common Medications
            MedicalTerm(
                term="paracetamol",
                category=MedicalCategory.MEDICATION,
                translations={
                    "ar": "باراسيتامول",
                    "es": "paracetamol",
                    "fr": "paracétamol",
                    "sw": "paracetamol",
                },
                synonyms=["acetaminophen", "tylenol"],
                context_hints=["pain", "fever", "analgesic"],
                fhir_resource_types=[
                    FHIRResourceType.MEDICATION,
                    FHIRResourceType.MEDICATION_STATEMENT,
                ],
            ),
            MedicalTerm(
                term="antibiotic",
                category=MedicalCategory.MEDICATION,
                translations={
                    "ar": "مضاد حيوي",
                    "es": "antibiótico",
                    "fr": "antibiotique",
                    "sw": "dawa ya kuua viini",
                },
                context_hints=["infection", "bacteria"],
                fhir_resource_types=[
                    FHIRResourceType.MEDICATION,
                    FHIRResourceType.MEDICATION_STATEMENT,
                ],
            ),
            # Routes of Administration
            MedicalTerm(
                term="by mouth",
                category=MedicalCategory.ROUTE,
                translations={
                    "ar": "عن طريق الفم",
                    "es": "por vía oral",
                    "fr": "par voie orale",
                    "sw": "kwa mdomo",
                },
                abbreviations=["PO", "p.o."],
                synonyms=["oral", "orally"],
            ),
            MedicalTerm(
                term="injection",
                category=MedicalCategory.ROUTE,
                translations={
                    "ar": "حقن",
                    "es": "inyección",
                    "fr": "injection",
                    "sw": "sindano",
                },
                abbreviations=["inj"],
                synonyms=["shot"],
            ),
            # Frequencies
            MedicalTerm(
                term="once daily",
                category=MedicalCategory.FREQUENCY,
                translations={
                    "ar": "مرة واحدة يوميا",
                    "es": "una vez al día",
                    "fr": "une fois par jour",
                    "sw": "mara moja kwa siku",
                },
                abbreviations=["QD", "OD"],
                synonyms=["once a day", "daily"],
            ),
            MedicalTerm(
                term="twice daily",
                category=MedicalCategory.FREQUENCY,
                translations={
                    "ar": "مرتين يوميا",
                    "es": "dos veces al día",
                    "fr": "deux fois par jour",
                    "sw": "mara mbili kwa siku",
                },
                abbreviations=["BID", "BD"],
                synonyms=["twice a day"],
            ),
            # Common Symptoms
            MedicalTerm(
                term="fever",
                category=MedicalCategory.SYMPTOM,
                translations={
                    "ar": "حمى",
                    "es": "fiebre",
                    "fr": "fièvre",
                    "sw": "homa",
                    "so": "qandho",
                },
                synonyms=["pyrexia", "elevated temperature"],
            ),
            MedicalTerm(
                term="pain",
                category=MedicalCategory.SYMPTOM,
                translations={
                    "ar": "ألم",
                    "es": "dolor",
                    "fr": "douleur",
                    "sw": "maumivu",
                    "so": "xanuun",
                },
                synonyms=["ache", "discomfort"],
            ),
            MedicalTerm(
                term="cough",
                category=MedicalCategory.SYMPTOM,
                translations={
                    "ar": "سعال",
                    "es": "tos",
                    "fr": "toux",
                    "sw": "kikohozi",
                    "so": "qufac",
                },
                synonyms=["tussis"],
            ),
        ]

        # Build terminology database
        for term in core_terms:
            # Index by primary term
            self.terminology_db[term.term.lower()] = term

            # Index by synonyms
            for synonym in term.synonyms:
                self.terminology_db[synonym.lower()] = term

            # Index by abbreviations
            for abbr in term.abbreviations:
                self.terminology_db[abbr.upper()] = term

    def _compile_patterns(self) -> None:
        """Compile regex patterns for efficiency."""
        # Pattern for detecting medical measurements
        self.measurement_pattern = re.compile(
            r"\b(\d+(?:\.\d+)?)\s*(?:/|over)\s*(\d+(?:\.\d+)?)\s*(mmHg|bpm|°[CF]|/min)\b",
            re.IGNORECASE,
        )

        # Pattern for vital sign values
        self.vital_sign_pattern = re.compile(
            r"\b(BP|blood pressure|HR|heart rate|RR|respiratory rate|T|temp|temperature|O2|SpO2)\s*:?\s*(\d+(?:\.\d+)?(?:\s*/\s*\d+(?:\.\d+)?)?)\s*([a-zA-Z°/%]+)?\b",
            re.IGNORECASE,
        )

        # Pattern for medication instructions
        self.medication_pattern = re.compile(
            r"\b(take|give|administer|inject)\s+(\d+(?:\.\d+)?)\s*(tablet|capsule|pill|mL|mg|mcg|unit)s?\b",
            re.IGNORECASE,
        )

    @require_phi_access(AccessLevel.READ)
    @audit_phi_access("identify_medical_terms")
    def identify_medical_terms(
        self, text: str
    ) -> List[Tuple[str, MedicalTerm, int, int]]:
        """
        Identify medical terms in text.

        Args:
            text: Text to analyze

        Returns:
            List of (matched_text, medical_term, start_pos, end_pos)
        """
        identified_terms = []
        text_lower = text.lower()

        # First check glossary if available
        if self._glossary_service:
            try:
                # Search for medical terms in glossary
                words = text.split()
                for _, word in enumerate(words):
                    if len(word) >= 3:  # Skip very short words
                        glossary_matches = self._glossary_service.search_terms(
                            query=word, include_synonyms=True, limit=1
                        )
                        if glossary_matches:
                            match = glossary_matches[0]
                            # Convert to MedicalTerm
                            medical_term = MedicalTerm(
                                term=match.term_display,
                                category=MedicalCategory.CONDITION,  # Map from glossary category
                                who_code=match.who_code,
                                translations={
                                    lang: trans
                                    for lang, trans in match.translations.items()
                                },
                                synonyms=match.synonyms,
                            )
                            # Find position in original text
                            start = text_lower.find(word.lower())
                            if start != -1:
                                identified_terms.append(
                                    (word, medical_term, start, start + len(word))
                                )
            except (KeyError, AttributeError, ValueError) as e:
                logger.debug(f"Glossary search error: {e}")

        # Check for exact matches in local database
        for term_key, medical_term in self.terminology_db.items():
            # Use word boundaries for exact matching
            pattern = re.compile(r"\b" + re.escape(term_key) + r"\b", re.IGNORECASE)

            for match in pattern.finditer(text):
                identified_terms.append(
                    (match.group(), medical_term, match.start(), match.end())
                )

        # Remove overlapping matches (prefer longer matches)
        identified_terms.sort(key=lambda x: (x[2], -len(x[0])))

        non_overlapping = []
        last_end = -1

        for term in identified_terms:
            if term[2] >= last_end:
                non_overlapping.append(term)
                last_end = term[3]

        return non_overlapping

    def extract_dosages(self, text: str) -> List[Dict[str, Any]]:
        """
        Extract medication dosages from text.

        Args:
            text: Text to analyze

        Returns:
            List of dosage information dictionaries
        """
        dosages = []

        for pattern in self.DOSAGE_PATTERNS:
            for match in pattern.finditer(text):
                dosage_info = {
                    "matched_text": match.group(),
                    "position": (match.start(), match.end()),
                    "components": match.groups(),
                }

                # Determine dosage type
                if "-" in match.group():
                    dosage_info["type"] = "range"
                elif "/" in match.group():
                    dosage_info["type"] = "concentration"
                elif "%" in match.group():
                    dosage_info["type"] = "percentage"
                else:
                    dosage_info["type"] = "standard"

                dosages.append(dosage_info)

        return dosages

    def extract_vital_signs(self, text: str) -> List[Dict[str, Any]]:
        """
        Extract vital sign measurements from text.

        Args:
            text: Text to analyze

        Returns:
            List of vital sign measurements
        """
        vital_signs = []

        for match in self.vital_sign_pattern.finditer(text):
            vital_type = match.group(1)
            value = match.group(2)
            unit = match.group(3) if match.group(3) else ""

            # Normalize vital type
            vital_type_normalized = vital_type.upper()
            if vital_type_normalized in ["T", "TEMP", "TEMPERATURE"]:
                vital_type_normalized = "temperature"
            elif vital_type_normalized in ["BP", "BLOOD PRESSURE"]:
                vital_type_normalized = "blood_pressure"
            elif vital_type_normalized in ["HR", "HEART RATE"]:
                vital_type_normalized = "heart_rate"
            elif vital_type_normalized in ["RR", "RESPIRATORY RATE"]:
                vital_type_normalized = "respiratory_rate"
            elif vital_type_normalized in ["O2", "SPO2"]:
                vital_type_normalized = "oxygen_saturation"

            vital_signs.append(
                {
                    "type": vital_type_normalized,
                    "value": value,
                    "unit": unit,
                    "matched_text": match.group(),
                    "position": (match.start(), match.end()),
                }
            )

        return vital_signs

    def normalize_units(self, text: str, target_system: str = "metric") -> str:
        """
        Normalize medical units in text.

        Args:
            text: Text containing medical units
            target_system: Target unit system ("metric" or "imperial")

        Returns:
            Text with normalized units
        """
        normalized_text = text

        # Temperature conversions
        if target_system == "metric":
            # Convert Fahrenheit to Celsius
            f_pattern = re.compile(
                r"(\d+(?:\.\d+)?)\s*°?\s*F(?:ahrenheit)?", re.IGNORECASE
            )
            for match in f_pattern.finditer(text):
                f_value = float(match.group(1))
                c_value = (f_value - 32) * 5 / 9
                normalized_text = normalized_text.replace(
                    match.group(), f"{c_value:.1f}°C"
                )
        else:
            # Convert Celsius to Fahrenheit
            c_pattern = re.compile(
                r"(\d+(?:\.\d+)?)\s*°?\s*C(?:elsius)?", re.IGNORECASE
            )
            for match in c_pattern.finditer(text):
                c_value = float(match.group(1))
                f_value = (c_value * 9 / 5) + 32
                normalized_text = normalized_text.replace(
                    match.group(), f"{f_value:.1f}°F"
                )

        # Weight conversions
        if target_system == "metric":
            # Convert pounds to kilograms
            lb_pattern = re.compile(
                r"(\d+(?:\.\d+)?)\s*(?:lb|lbs|pound)s?", re.IGNORECASE
            )
            for match in lb_pattern.finditer(text):
                lb_value = float(match.group(1))
                kg_value = lb_value * 0.453592
                normalized_text = normalized_text.replace(
                    match.group(), f"{kg_value:.1f} kg"
                )

        return normalized_text

    def get_translation(
        self,
        term: str,
        target_language: str,
        _category: Optional[MedicalCategory] = None,
    ) -> Optional[str]:
        """
        Get translation for a medical term.

        Args:
            term: Medical term to translate
            target_language: Target language
            category: Optional category hint

        Returns:
            Translated term or None if not found
        """
        # First check medical glossary if available
        if self._glossary_service:
            try:
                glossary_translation = self._glossary_service.get_term_translation(
                    term=term, target_language=target_language, source_language="en"
                )
                if glossary_translation:
                    return glossary_translation
            except (KeyError, AttributeError, ValueError) as e:
                logger.debug(f"Glossary translation lookup error: {e}")

        # Fall back to local terminology database
        term_lower = term.lower()

        if term_lower in self.terminology_db:
            medical_term = self.terminology_db[term_lower]
            return medical_term.translations.get(target_language)

        # Check abbreviations (case-sensitive)
        if term.upper() in self.terminology_db:
            medical_term = self.terminology_db[term.upper()]
            return medical_term.translations.get(target_language)

        return None

    def preserve_medical_formatting(
        self, text: str
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """
        Preserve medical formatting and extract replaceable segments.

        Args:
            text: Text to process

        Returns:
            Tuple of (processed_text, preservation_map)
        """
        preservation_map = []
        processed_text = text
        placeholder_counter = 0

        # Preserve abbreviations
        for abbr in self.PRESERVE_ABBREVIATIONS:
            pattern = re.compile(r"\b" + re.escape(abbr) + r"\b")
            for match in pattern.finditer(text):
                placeholder = f"__MEDABBR_{placeholder_counter}__"
                preservation_map.append(
                    {
                        "placeholder": placeholder,
                        "original": match.group(),
                        "type": "abbreviation",
                        "position": (match.start(), match.end()),
                    }
                )
                processed_text = processed_text.replace(match.group(), placeholder, 1)
                placeholder_counter += 1

        # Preserve dosages
        dosages = self.extract_dosages(processed_text)
        for dosage in dosages:
            placeholder = f"__MEDDOSE_{placeholder_counter}__"
            preservation_map.append(
                {
                    "placeholder": placeholder,
                    "original": dosage["matched_text"],
                    "type": "dosage",
                    "dosage_info": [dosage],
                }
            )
            processed_text = processed_text.replace(
                dosage["matched_text"], placeholder, 1
            )
            placeholder_counter += 1

        # Preserve vital signs
        vital_signs = self.extract_vital_signs(processed_text)
        for vital in vital_signs:
            placeholder = f"__MEDVITAL_{placeholder_counter}__"
            preservation_map.append(
                {
                    "placeholder": placeholder,
                    "original": vital["matched_text"],
                    "type": "vital_sign",
                    "vital_info": [vital],
                }
            )
            processed_text = processed_text.replace(
                vital["matched_text"], placeholder, 1
            )
            placeholder_counter += 1

        return processed_text, preservation_map

    @require_phi_access(AccessLevel.WRITE)
    @audit_phi_access("restore_medical_formatting")
    def restore_medical_formatting(
        self, translated_text: str, preservation_map: List[Dict[str, Any]]
    ) -> str:
        """
        Restore medical formatting after translation.

        Args:
            translated_text: Translated text with placeholders
            preservation_map: Map of preserved elements

        Returns:
            Text with restored medical formatting
        """
        restored_text = translated_text

        # Restore in reverse order to maintain positions
        for item in reversed(preservation_map):
            if item["placeholder"] in restored_text:
                restored_text = restored_text.replace(
                    item["placeholder"], item["original"]
                )

        return restored_text

    def validate_medical_translation(
        self,
        source_text: str,
        translated_text: str,
        _source_lang: "TranslationDirection",
        _target_lang: "TranslationDirection",
    ) -> Dict[str, Any]:
        """
        Validate medical translation for accuracy and completeness.

        Args:
            source_text: Original text
            translated_text: Translated text
            source_lang: Source language
            target_lang: Target language

        Returns:
            Validation results
        """
        validation_results: Dict[str, Any] = {
            "is_valid": True,
            "warnings": [],
            "errors": [],
            "metrics": {},
        }

        # Extract medical elements from both texts
        source_dosages = self.extract_dosages(source_text)
        translated_dosages = self.extract_dosages(translated_text)

        source_vitals = self.extract_vital_signs(source_text)
        translated_vitals = self.extract_vital_signs(translated_text)

        # Check dosage preservation
        if len(source_dosages) != len(translated_dosages):
            validation_results["errors"].append(
                {
                    "type": "dosage_count_mismatch",
                    "source_count": len(source_dosages),
                    "translated_count": len(translated_dosages),
                }
            )
            validation_results["is_valid"] = False

        # Check vital signs preservation
        if len(source_vitals) != len(translated_vitals):
            validation_results["warnings"].append(
                {
                    "type": "vital_sign_count_mismatch",
                    "source_count": len(source_vitals),
                    "translated_count": len(translated_vitals),
                }
            )

        # Check for preserved abbreviations
        for abbr in self.PRESERVE_ABBREVIATIONS:
            source_count = len(re.findall(r"\b" + abbr + r"\b", source_text))
            translated_count = len(re.findall(r"\b" + abbr + r"\b", translated_text))

            if source_count > 0 and source_count != translated_count:
                validation_results["warnings"].append(
                    {
                        "type": "abbreviation_mismatch",
                        "abbreviation": abbr,
                        "source_count": source_count,
                        "translated_count": translated_count,
                    }
                )

        # Calculate metrics
        validation_results["metrics"]["dosage_preservation_rate"] = (
            len(translated_dosages) / len(source_dosages) if source_dosages else 1.0
        )
        validation_results["metrics"]["vital_preservation_rate"] = (
            len(translated_vitals) / len(source_vitals) if source_vitals else 1.0
        )

        return validation_results

    def get_category_terms(self, category: MedicalCategory) -> List[MedicalTerm]:
        """Get all terms in a specific category."""
        return [
            term for term in self.terminology_db.values() if term.category == category
        ]

    def export_glossary(self, language: str) -> Dict[str, str]:
        """Export glossary for a specific language."""
        glossary = {}

        # First get terms from medical glossary if available
        if self._glossary_service:
            try:
                # Get all terms without filtering by category
                entries: List[Any] = (
                    []
                )  # Placeholder - glossary service implementation needed
                for entry in entries:
                    if language in entry.translations:
                        glossary[entry.term_display] = entry.translations[language]
            except (KeyError, AttributeError, ValueError) as e:
                logger.debug(f"Error exporting from glossary service: {e}")

        # Add terms from local database
        for term_key, medical_term in self.terminology_db.items():
            if medical_term.term == term_key:  # Only primary terms
                translation = medical_term.translations.get(language)
                if translation and medical_term.term not in glossary:
                    glossary[medical_term.term] = translation

        return dict(glossary)

    async def is_medical_term(self, text: str, _language: str) -> bool:
        """Check if a text is a medical term."""
        # Normalize text
        normalized = text.lower().strip()

        # Check in terminology database
        if normalized in self.terminology_db:
            return True

        # Check if it's a medical abbreviation
        if text.upper() in self.PRESERVE_ABBREVIATIONS:
            return True

        # Check in glossary service if available
        if self._glossary_service:
            try:
                # Check if term exists in glossary service
                # Placeholder - method not available in current implementation
                return False
            except (AttributeError, KeyError, ValueError) as e:
                logger.debug(f"Error checking term in glossary: {e}")

        return False

    async def translate_term(
        self,
        text: str,
        source_language: str,
        target_language: str,
        category: Optional[str] = None,
    ) -> str:
        """Translate a medical term.

        Args:
            text: The term to translate
            source_language: Source language code (used for context)
            target_language: Target language code
            category: Optional category filter for more accurate translation
        """
        # Normalize text
        normalized = text.lower().strip()

        # Log the translation request with all parameters for audit
        logger.debug(
            f"Translating term '{text}' from {source_language} to {target_language}"
            + (f" in category {category}" if category else "")
        )

        # Check in terminology database
        if normalized in self.terminology_db:
            term = self.terminology_db[normalized]
            translation = term.translations.get(target_language)
            if translation:
                return str(translation)

        # Use glossary service if available
        if self._glossary_service:
            try:
                # Get term translation from glossary service
                # Placeholder - method not available in current implementation
                pass
            except (AttributeError, KeyError, ValueError) as e:
                logger.debug(f"Error getting term translation from glossary: {e}")

        # Return original text if no translation found
        return text
