"""
Medical Procedure Names Translation.

This module handles medical procedure name translations for multiple languages,
ensuring accurate communication of medical interventions.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional

from src.healthcare.hipaa_access_control import AccessLevel, require_phi_access
from src.security.encryption import EncryptionService
from src.utils.logging import get_logger

logger = get_logger(__name__)


class ProcedureCategory(str, Enum):
    """Categories of medical procedures."""

    DIAGNOSTIC = "diagnostic"
    THERAPEUTIC = "therapeutic"
    SURGICAL = "surgical"
    PREVENTIVE = "preventive"
    EMERGENCY = "emergency"
    OBSTETRIC = "obstetric"
    PEDIATRIC = "pediatric"
    IMAGING = "imaging"
    LABORATORY = "laboratory"


@dataclass
class ProcedureTranslation:
    """Medical procedure with multilingual translations."""

    procedure_name: str
    category: ProcedureCategory
    translations: Dict[str, str]
    cpt_code: Optional[str] = None  # Current Procedural Terminology
    is_emergency: bool = False
    requires_consent: bool = True
    typical_duration: Optional[str] = None


class ProcedureNameTranslator:
    """Manages medical procedure name translations."""

    # Common procedures in refugee health settings
    COMMON_PROCEDURES = {
        # Diagnostic procedures
        "physical_examination": ProcedureTranslation(
            procedure_name="Physical examination",
            category=ProcedureCategory.DIAGNOSTIC,
            translations={
                "ar": "الفحص البدني",
                "fr": "Examen physique",
                "es": "Examen físico",
                "sw": "Uchunguzi wa mwili",
                "fa": "معاینه فیزیکی",
                "ps": "فزیکي معاینه",
                "ur": "جسمانی معائنہ",
                "bn": "শারীরিক পরীক্ষা",
                "hi": "शारीरिक परीक्षा",
            },
            typical_duration="15-30 minutes",
        ),
        "blood_test": ProcedureTranslation(
            procedure_name="Blood test",
            category=ProcedureCategory.LABORATORY,
            translations={
                "ar": "فحص الدم",
                "fr": "Analyse de sang",
                "es": "Análisis de sangre",
                "sw": "Kipimo cha damu",
                "fa": "آزمایش خون",
                "ps": "د وینې معاینه",
                "ur": "خون کا ٹیسٹ",
                "bn": "রক্ত পরীক্ষা",
                "hi": "रक्त परीक्षण",
            },
            cpt_code="80050",
            typical_duration="5-10 minutes",
        ),
        "urine_test": ProcedureTranslation(
            procedure_name="Urine test",
            category=ProcedureCategory.LABORATORY,
            translations={
                "ar": "فحص البول",
                "fr": "Analyse d'urine",
                "es": "Análisis de orina",
                "sw": "Kipimo cha mkojo",
                "fa": "آزمایش ادرار",
                "ps": "د ادرار معاینه",
                "ur": "پیشاب کا ٹیسٹ",
                "bn": "প্রস্রাব পরীক্ষা",
                "hi": "मूत्र परीक्षण",
            },
            cpt_code="81001",
            typical_duration="5 minutes",
        ),
        "chest_xray": ProcedureTranslation(
            procedure_name="Chest X-ray",
            category=ProcedureCategory.IMAGING,
            translations={
                "ar": "أشعة الصدر السينية",
                "fr": "Radiographie thoracique",
                "es": "Radiografía de tórax",
                "sw": "Eksirei ya kifua",
                "fa": "عکس قفسه سینه",
                "ps": "د سینې ایکسرې",
                "ur": "سینے کا ایکسرے",
                "bn": "বুকের এক্স-রে",
                "hi": "छाती का एक्स-रे",
            },
            cpt_code="71020",
            typical_duration="10-15 minutes",
        ),
        # Therapeutic procedures
        "vaccination": ProcedureTranslation(
            procedure_name="Vaccination",
            category=ProcedureCategory.PREVENTIVE,
            translations={
                "ar": "التطعيم",
                "fr": "Vaccination",
                "es": "Vacunación",
                "sw": "Chanjo",
                "fa": "واکسیناسیون",
                "ps": "واکسین ورکول",
                "ur": "ٹیکہ لگانا",
                "bn": "টিকা দেওয়া",
                "hi": "टीकाकरण",
            },
            cpt_code="90460",
            typical_duration="5-10 minutes",
        ),
        "wound_dressing": ProcedureTranslation(
            procedure_name="Wound dressing",
            category=ProcedureCategory.THERAPEUTIC,
            translations={
                "ar": "تضميد الجروح",
                "fr": "Pansement",
                "es": "Vendaje de heridas",
                "sw": "Kufunga jeraha",
                "fa": "پانسمان زخم",
                "ps": "د زخم پټول",
                "ur": "زخم کی مرہم پٹی",
                "bn": "ক্ষত ড্রেসিং",
                "hi": "घाव की मरहम पट्टी",
            },
            typical_duration="10-20 minutes",
        ),
        "iv_fluids": ProcedureTranslation(
            procedure_name="Intravenous fluid administration",
            category=ProcedureCategory.THERAPEUTIC,
            translations={
                "ar": "إعطاء السوائل الوريدية",
                "fr": "Perfusion intraveineuse",
                "es": "Administración de líquidos intravenosos",
                "sw": "Kuweka maji ya mishipa",
                "fa": "تزریق مایعات وریدی",
                "ps": "د رګ له لارې مایعات",
                "ur": "رگوں میں سیال چڑھانا",
                "bn": "শিরায় তরল প্রদান",
                "hi": "नसों में द्रव चढ़ाना",
            },
            is_emergency=True,
            typical_duration="30-60 minutes",
        ),
        # Emergency procedures
        "cpr": ProcedureTranslation(
            procedure_name="Cardiopulmonary resuscitation",
            category=ProcedureCategory.EMERGENCY,
            translations={
                "ar": "الإنعاش القلبي الرئوي",
                "fr": "Réanimation cardio-pulmonaire",
                "es": "Reanimación cardiopulmonar",
                "sw": "Kurudisha pumzi na moyo",
                "fa": "احیای قلبی ریوی",
                "ps": "د زړه او سږو بیا راژوندي کول",
                "ur": "دل اور پھیپھڑوں کی بحالی",
                "bn": "কার্ডিওপালমোনারি রিসাসিটেশন",
                "hi": "हृदय फुफ्फुसीय पुनर्जीवन",
            },
            is_emergency=True,
            requires_consent=False,
            typical_duration="Until stabilized",
        ),
        # Obstetric procedures
        "prenatal_checkup": ProcedureTranslation(
            procedure_name="Prenatal checkup",
            category=ProcedureCategory.OBSTETRIC,
            translations={
                "ar": "فحص ما قبل الولادة",
                "fr": "Consultation prénatale",
                "es": "Control prenatal",
                "sw": "Uchunguzi wa ujauzito",
                "fa": "معاینه دوران بارداری",
                "ps": "د امیندوارۍ معاینه",
                "ur": "دوران حمل معائنہ",
                "bn": "প্রসবপূর্ব পরীক্ষা",
                "hi": "प्रसवपूर्व जांच",
            },
            typical_duration="20-30 minutes",
        ),
        "delivery": ProcedureTranslation(
            procedure_name="Delivery",
            category=ProcedureCategory.OBSTETRIC,
            translations={
                "ar": "الولادة",
                "fr": "Accouchement",
                "es": "Parto",
                "sw": "Kujifungua",
                "fa": "زایمان",
                "ps": "زیږون",
                "ur": "زچگی",
                "bn": "প্রসব",
                "hi": "प्रसव",
            },
            is_emergency=True,
            typical_duration="Variable",
        ),
    }

    def __init__(self) -> None:
        """Initialize procedure translator."""
        self.procedures = self.COMMON_PROCEDURES.copy()
        self._category_index = self._build_category_index()
        self.encryption_service = EncryptionService(
            kms_key_id="alias/haven-health-default"
        )
        self._emergency_procedures = self._build_emergency_index()

    def _build_category_index(self) -> Dict[ProcedureCategory, List[str]]:
        """Build index of procedures by category."""
        index: Dict[ProcedureCategory, List[str]] = {}
        for proc_key, procedure in self.procedures.items():
            if procedure.category not in index:
                index[procedure.category] = []
            index[procedure.category].append(proc_key)
        return index

    def _build_emergency_index(self) -> List[str]:
        """Build list of emergency procedures."""
        return [
            proc_key
            for proc_key, procedure in self.procedures.items()
            if procedure.is_emergency
        ]

    @require_phi_access(AccessLevel.READ)
    def get_translation(
        self, procedure_key: str, target_language: str
    ) -> Optional[str]:
        """Get translation for procedure."""
        if procedure_key not in self.procedures:
            return None

        procedure = self.procedures[procedure_key]

        if target_language == "en":
            return procedure.procedure_name

        return procedure.translations.get(target_language)

    def get_procedures_by_category(
        self, category: ProcedureCategory
    ) -> List[Dict[str, Any]]:
        """Get all procedures in a category."""
        proc_keys = self._category_index.get(category, [])
        return [
            {
                "key": key,
                "name": self.procedures[key].procedure_name,
                "duration": self.procedures[key].typical_duration,
                "is_emergency": self.procedures[key].is_emergency,
            }
            for key in proc_keys
        ]

    def get_emergency_procedures(self) -> List[Dict[str, str]]:
        """Get all emergency procedures."""
        return [
            {
                "key": key,
                "name": self.procedures[key].procedure_name,
                "category": self.procedures[key].category.value,
            }
            for key in self._emergency_procedures
        ]

    def search_procedures(
        self, query: str, language: str = "en"
    ) -> List[Dict[str, Any]]:
        """Search procedures by name."""
        query_lower = query.lower()
        results = []

        for proc_key, procedure in self.procedures.items():
            # Search in procedure name or translation
            search_term = (
                procedure.procedure_name.lower()
                if language == "en"
                else procedure.translations.get(language, "").lower()
            )

            if query_lower in search_term:
                results.append(
                    {
                        "key": proc_key,
                        "name": procedure.procedure_name,
                        "translated_name": procedure.translations.get(language),
                        "category": procedure.category.value,
                        "is_emergency": procedure.is_emergency,
                        "duration": procedure.typical_duration,
                    }
                )

        return results


# Global instance
procedure_translator = ProcedureNameTranslator()
