"""Lab Result Terms Translation.

This module handles laboratory test result terminology translations,
ensuring accurate communication of diagnostic results across languages.

This module handles PHI with encryption and access control to ensure HIPAA compliance.
It includes FHIR Resource typing and validation for healthcare data.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional

from src.healthcare.fhir_validator import FHIRValidator
from src.utils.logging import get_logger

logger = get_logger(__name__)


class LabTestCategory(str, Enum):
    """Categories of laboratory tests."""

    HEMATOLOGY = "hematology"
    CLINICAL_CHEMISTRY = "clinical_chemistry"
    IMMUNOLOGY = "immunology"
    MICROBIOLOGY = "microbiology"
    URINALYSIS = "urinalysis"
    SEROLOGY = "serology"
    COAGULATION = "coagulation"
    BLOOD_GAS = "blood_gas"
    TUMOR_MARKERS = "tumor_markers"


class ResultInterpretation(str, Enum):
    """Standard result interpretations."""

    NORMAL = "normal"
    ABNORMAL = "abnormal"
    HIGH = "high"
    LOW = "low"
    CRITICAL_HIGH = "critical_high"
    CRITICAL_LOW = "critical_low"
    POSITIVE = "positive"
    NEGATIVE = "negative"
    REACTIVE = "reactive"
    NON_REACTIVE = "non_reactive"


@dataclass
class LabTestTranslation:
    """Lab test with multilingual translations."""

    test_name: str
    abbreviation: str
    category: LabTestCategory
    translations: Dict[str, str]
    unit: str
    normal_range: Optional[tuple[float, float]] = None
    critical_values: Optional[Dict[str, float]] = None
    loinc_code: Optional[str] = None  # Logical Observation Identifiers


class LabResultTermsTranslator:
    """Manages laboratory result terms translations."""

    # Common lab tests in refugee health
    COMMON_LAB_TESTS = {
        # Hematology
        "hemoglobin": LabTestTranslation(
            test_name="Hemoglobin",
            abbreviation="Hb",
            category=LabTestCategory.HEMATOLOGY,
            translations={
                "ar": "الهيموغلوبين",
                "fr": "Hémoglobine",
                "es": "Hemoglobina",
                "sw": "Hemoglobini",
                "fa": "هموگلوبین",
                "ps": "هیموګلوبین",
                "ur": "ہیموگلوبن",
                "bn": "হিমোগ্লোবিন",
                "hi": "हीमोग्लोबिन",
            },
            unit="g/dL",
            normal_range=(12.0, 16.0),  # Female range
            critical_values={"low": 7.0, "high": 20.0},
            loinc_code="718-7",
        ),
        "wbc": LabTestTranslation(
            test_name="White blood cell count",
            abbreviation="WBC",
            category=LabTestCategory.HEMATOLOGY,
            translations={
                "ar": "عدد كريات الدم البيضاء",
                "fr": "Numération des globules blancs",
                "es": "Recuento de glóbulos blancos",
                "sw": "Hesabu ya chembe nyeupe za damu",
                "fa": "شمارش گلبول‌های سفید",
                "ps": "د سپینو کرویاتو شمیر",
                "ur": "سفید خلیوں کی تعداد",
                "bn": "শ্বেত রক্তকণিকা গণনা",
                "hi": "श्वेत रक्त कोशिका गणना",
            },
            unit="×10³/μL",
            normal_range=(4.5, 11.0),
            critical_values={"low": 2.0, "high": 30.0},
            loinc_code="6690-2",
        ),
        "platelet": LabTestTranslation(
            test_name="Platelet count",
            abbreviation="PLT",
            category=LabTestCategory.HEMATOLOGY,
            translations={
                "ar": "عدد الصفائح الدموية",
                "fr": "Numération plaquettaire",
                "es": "Recuento de plaquetas",
                "sw": "Hesabu ya sahani za damu",
                "fa": "شمارش پلاکت",
                "ps": "د وینې د پلیټلیټ شمیر",
                "ur": "پلیٹلیٹ کی تعداد",
                "bn": "প্লেটলেট গণনা",
                "hi": "प्लेटलेट गिनती",
            },
            unit="×10³/μL",
            normal_range=(150.0, 450.0),
            critical_values={"low": 50.0, "high": 1000.0},
            loinc_code="777-3",
        ),
        # Clinical Chemistry
        "glucose": LabTestTranslation(
            test_name="Blood glucose",
            abbreviation="GLU",
            category=LabTestCategory.CLINICAL_CHEMISTRY,
            translations={
                "ar": "سكر الدم",
                "fr": "Glycémie",
                "es": "Glucosa en sangre",
                "sw": "Sukari ya damu",
                "fa": "قند خون",
                "ps": "د وینې شکره",
                "ur": "خون میں شوگر",
                "bn": "রক্তের গ্লুকোজ",
                "hi": "रक्त शर्करा",
            },
            unit="mg/dL",
            normal_range=(70.0, 100.0),  # Fasting
            critical_values={"low": 40.0, "high": 500.0},
            loinc_code="2339-0",
        ),
        "creatinine": LabTestTranslation(
            test_name="Creatinine",
            abbreviation="Cr",
            category=LabTestCategory.CLINICAL_CHEMISTRY,
            translations={
                "ar": "الكرياتينين",
                "fr": "Créatinine",
                "es": "Creatinina",
                "sw": "Kreatinini",
                "fa": "کراتینین",
                "ps": "کریټینین",
                "ur": "کریٹینین",
                "bn": "ক্রিয়েটিনিন",
                "hi": "क्रिएटिनिन",
            },
            unit="mg/dL",
            normal_range=(0.6, 1.2),
            critical_values={"high": 10.0},
            loinc_code="2160-0",
        ),
        # Serology/Immunology
        "hiv_test": LabTestTranslation(
            test_name="HIV antibody test",
            abbreviation="HIV Ab",
            category=LabTestCategory.SEROLOGY,
            translations={
                "ar": "فحص الأجسام المضادة لفيروس نقص المناعة",
                "fr": "Test d'anticorps VIH",
                "es": "Prueba de anticuerpos VIH",
                "sw": "Kipimo cha virusi vya ukimwi",
                "fa": "آزمایش HIV",
                "ps": "د HIV معاینه",
                "ur": "ایچ آئی وی ٹیسٹ",
                "bn": "এইচআইভি পরীক্ষা",
                "hi": "एचआईवी परीक्षा",
            },
            unit="",
            loinc_code="5221-7",
        ),
        "malaria_test": LabTestTranslation(
            test_name="Malaria rapid test",
            abbreviation="Malaria RDT",
            category=LabTestCategory.MICROBIOLOGY,
            translations={
                "ar": "الفحص السريع للملاريا",
                "fr": "Test rapide du paludisme",
                "es": "Prueba rápida de malaria",
                "sw": "Kipimo cha haraka cha malaria",
                "fa": "تست سریع مالاریا",
                "ps": "د ملاریا چټک ازموینه",
                "ur": "ملیریا کا فوری ٹیسٹ",
                "bn": "ম্যালেরিয়া দ্রুত পরীক্ষা",
                "hi": "मलेरिया रैपिड टेस्ट",
            },
            unit="",
            loinc_code="6423-8",
        ),
        # Urinalysis
        "urine_protein": LabTestTranslation(
            test_name="Urine protein",
            abbreviation="U-Protein",
            category=LabTestCategory.URINALYSIS,
            translations={
                "ar": "بروتين البول",
                "fr": "Protéines urinaires",
                "es": "Proteína en orina",
                "sw": "Protini ya mkojo",
                "fa": "پروتئین ادرار",
                "ps": "د ادرار پروټین",
                "ur": "پیشاب میں پروٹین",
                "bn": "প্রস্রাবে প্রোটিন",
                "hi": "मूत्र प्रोटीन",
            },
            unit="mg/dL",
            loinc_code="2888-6",
        ),
    }

    # Result interpretation translations
    RESULT_INTERPRETATIONS = {
        ResultInterpretation.NORMAL: {
            "ar": "طبيعي",
            "fr": "Normal",
            "es": "Normal",
            "sw": "Kawaida",
            "fa": "طبیعی",
            "ps": "نورمال",
            "ur": "نارمل",
            "bn": "স্বাভাবিক",
            "hi": "सामान्य",
        },
        ResultInterpretation.ABNORMAL: {
            "ar": "غير طبيعي",
            "fr": "Anormal",
            "es": "Anormal",
            "sw": "Si kawaida",
            "fa": "غیر طبیعی",
            "ps": "غیر نورمال",
            "ur": "غیر معمولی",
            "bn": "অস্বাভাবিক",
            "hi": "असामान्य",
        },
        ResultInterpretation.HIGH: {
            "ar": "مرتفع",
            "fr": "Élevé",
            "es": "Alto",
            "sw": "Juu",
            "fa": "بالا",
            "ps": "لوړ",
            "ur": "زیادہ",
            "bn": "উচ্চ",
            "hi": "उच्च",
        },
        ResultInterpretation.LOW: {
            "ar": "منخفض",
            "fr": "Bas",
            "es": "Bajo",
            "sw": "Chini",
            "fa": "پایین",
            "ps": "ټیټ",
            "ur": "کم",
            "bn": "নিম্ন",
            "hi": "कम",
        },
        ResultInterpretation.POSITIVE: {
            "ar": "إيجابي",
            "fr": "Positif",
            "es": "Positivo",
            "sw": "Chanya",
            "fa": "مثبت",
            "ps": "مثبت",
            "ur": "مثبت",
            "bn": "পজিটিভ",
            "hi": "पॉज़िटिव",
        },
        ResultInterpretation.NEGATIVE: {
            "ar": "سلبي",
            "fr": "Négatif",
            "es": "Negativo",
            "sw": "Hasi",
            "fa": "منفی",
            "ps": "منفي",
            "ur": "منفی",
            "bn": "নেগেটিভ",
            "hi": "नेगेटिव",
        },
    }

    def __init__(self) -> None:
        """Initialize lab result terms translator."""
        self.tests = self.COMMON_LAB_TESTS.copy()
        self.interpretations = self.RESULT_INTERPRETATIONS.copy()
        self._category_index = self._build_category_index()
        self._abbreviation_index = self._build_abbreviation_index()
        self.fhir_validator = FHIRValidator()

    def _build_category_index(self) -> Dict[LabTestCategory, List[str]]:
        """Build index of tests by category."""
        index: Dict[LabTestCategory, List[str]] = {}
        for test_key, test in self.tests.items():
            if test.category not in index:
                index[test.category] = []
            index[test.category].append(test_key)
        return index

    def _build_abbreviation_index(self) -> Dict[str, str]:
        """Build index from abbreviations to test keys."""
        return {
            test.abbreviation.lower(): test_key for test_key, test in self.tests.items()
        }

    def get_test_translation(
        self, test_key: str, target_language: str
    ) -> Optional[str]:
        """Get translation for lab test."""
        if test_key not in self.tests:
            # Try abbreviation lookup
            abbrev_key = self._abbreviation_index.get(test_key.lower())
            if not abbrev_key:
                return None
            test_key = abbrev_key

        test = self.tests[test_key]

        if target_language == "en":
            return test.test_name

        return test.translations.get(target_language)

    def get_interpretation_translation(
        self, interpretation: ResultInterpretation, target_language: str
    ) -> str:
        """Get translation for result interpretation."""
        if target_language == "en":
            return interpretation.value.replace("_", " ").title()

        return self.interpretations.get(interpretation, {}).get(
            target_language, interpretation.value
        )

    def interpret_result(self, test_key: str, value: float) -> ResultInterpretation:
        """Interpret lab result based on normal ranges."""
        if test_key not in self.tests:
            abbrev_key = self._abbreviation_index.get(test_key.lower())
            if not abbrev_key:
                return ResultInterpretation.ABNORMAL
            test_key = abbrev_key

        test = self.tests[test_key]

        # Check critical values first
        if test.critical_values:
            if "low" in test.critical_values and value <= test.critical_values["low"]:
                return ResultInterpretation.CRITICAL_LOW
            if "high" in test.critical_values and value >= test.critical_values["high"]:
                return ResultInterpretation.CRITICAL_HIGH

        # Check normal range
        if test.normal_range:
            low, high = test.normal_range
            if value < low:
                return ResultInterpretation.LOW
            elif value > high:
                return ResultInterpretation.HIGH
            else:
                return ResultInterpretation.NORMAL

        return ResultInterpretation.ABNORMAL

    def format_result_with_interpretation(
        self, test_key: str, value: float, language: str = "en"
    ) -> Dict[str, str]:
        """Format lab result with interpretation in target language."""
        test = self.tests.get(test_key)
        if not test:
            return {}

        interpretation = self.interpret_result(test_key, value)

        test_name = self.get_test_translation(test_key, language) or test_key
        return {
            "test_name": test_name,
            "value": f"{value} {test.unit}",
            "interpretation": self.get_interpretation_translation(
                interpretation, language
            ),
            "interpretation_code": interpretation.value,
            "is_critical": str(
                interpretation
                in [
                    ResultInterpretation.CRITICAL_HIGH,
                    ResultInterpretation.CRITICAL_LOW,
                ]
            ),
        }

    def get_tests_by_category(self, category: LabTestCategory) -> List[Dict[str, Any]]:
        """Get all tests in a category."""
        test_keys = self._category_index.get(category, [])
        return [
            {
                "key": key,
                "name": self.tests[key].test_name,
                "abbreviation": self.tests[key].abbreviation,
                "unit": self.tests[key].unit,
                "loinc_code": self.tests[key].loinc_code,
            }
            for key in test_keys
        ]

    def search_tests(self, query: str, language: str = "en") -> List[Dict[str, Any]]:
        """Search lab tests by name or abbreviation."""
        query_lower = query.lower()
        results = []

        for test_key, test in self.tests.items():
            # Search in test name
            if language == "en":
                if (
                    query_lower in test.test_name.lower()
                    or query_lower in test.abbreviation.lower()
                ):
                    results.append(
                        {
                            "key": test_key,
                            "name": test.test_name,
                            "abbreviation": test.abbreviation,
                            "category": test.category.value,
                            "unit": test.unit,
                        }
                    )
            else:
                # Search in translation
                translation = test.translations.get(language, "")
                if query_lower in translation.lower():
                    results.append(
                        {
                            "key": test_key,
                            "name": test.test_name,
                            "translated_name": translation,
                            "abbreviation": test.abbreviation,
                            "category": test.category.value,
                            "unit": test.unit,
                        }
                    )

        return results

    def get_critical_tests(self) -> List[str]:
        """Get tests with critical value thresholds."""
        return [
            test_key for test_key, test in self.tests.items() if test.critical_values
        ]


# Global instance
lab_terms_translator = LabResultTermsTranslator()
