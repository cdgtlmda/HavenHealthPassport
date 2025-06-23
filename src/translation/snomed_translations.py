"""SNOMED CT Translation Configuration.

This module handles SNOMED CT concept translations for multiple languages,
ensuring medical accuracy for clinical terminology.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Set

from src.utils.logging import get_logger

logger = get_logger(__name__)


class SNOMEDHierarchy(str, Enum):
    """SNOMED CT concept hierarchies."""

    CLINICAL_FINDING = "404684003"
    PROCEDURE = "71388002"
    BODY_STRUCTURE = "123037004"
    ORGANISM = "410607006"
    SUBSTANCE = "105590001"
    PHARMACEUTICAL = "373873005"
    SPECIMEN = "123038009"
    OBSERVABLE_ENTITY = "363787002"
    EVENT = "272379006"
    SITUATION = "243796009"


@dataclass
class SNOMEDTranslation:
    """SNOMED CT concept with multilingual translations."""

    concept_id: str
    fsn: str  # Fully Specified Name
    preferred_term_en: str
    translations: Dict[str, str]
    hierarchy: SNOMEDHierarchy
    is_emergency: bool = False
    synonyms: Optional[List[str]] = None


class SNOMEDTranslationManager:
    """Manages SNOMED CT translations for multiple languages."""

    # Common SNOMED CT concepts for refugee health
    COMMON_SNOMED_TRANSLATIONS = {
        # Clinical findings
        "386661006": SNOMEDTranslation(
            concept_id="386661006",
            fsn="Fever (finding)",
            preferred_term_en="Fever",
            translations={
                "ar": "حمى",
                "fr": "Fièvre",
                "es": "Fiebre",
                "sw": "Homa",
                "fa": "تب",
                "ps": "تبه",
                "ur": "بخار",
                "bn": "জ্বর",
                "hi": "बुखार",
            },
            hierarchy=SNOMEDHierarchy.CLINICAL_FINDING,
            synonyms=["Pyrexia", "Elevated temperature"],
        ),
        "22253000": SNOMEDTranslation(
            concept_id="22253000",
            fsn="Pain (finding)",
            preferred_term_en="Pain",
            translations={
                "ar": "ألم",
                "fr": "Douleur",
                "es": "Dolor",
                "sw": "Maumivu",
                "fa": "درد",
                "ps": "درد",
                "ur": "درد",
                "bn": "ব্যথা",
                "hi": "दर्द",
            },
            hierarchy=SNOMEDHierarchy.CLINICAL_FINDING,
            is_emergency=True,
        ),
        "49727002": SNOMEDTranslation(
            concept_id="49727002",
            fsn="Cough (finding)",
            preferred_term_en="Cough",
            translations={
                "ar": "سعال",
                "fr": "Toux",
                "es": "Tos",
                "sw": "Kikohozi",
                "fa": "سرفه",
                "ps": "ټوخی",
                "ur": "کھانسی",
                "bn": "কাশি",
                "hi": "खांसी",
            },
            hierarchy=SNOMEDHierarchy.CLINICAL_FINDING,
        ),
        "267036007": SNOMEDTranslation(
            concept_id="267036007",
            fsn="Dyspnea (finding)",
            preferred_term_en="Shortness of breath",
            translations={
                "ar": "ضيق التنفس",
                "fr": "Essoufflement",
                "es": "Falta de aire",
                "sw": "Kupumua kwa shida",
                "fa": "تنگی نفس",
                "ps": "د ساه اخیستلو ستونزه",
                "ur": "سانس پھولنا",
                "bn": "শ্বাসকষ্ট",
                "hi": "सांस की तकलीफ",
            },
            hierarchy=SNOMEDHierarchy.CLINICAL_FINDING,
            is_emergency=True,
        ),
        "422587007": SNOMEDTranslation(
            concept_id="422587007",
            fsn="Nausea (finding)",
            preferred_term_en="Nausea",
            translations={
                "ar": "غثيان",
                "fr": "Nausée",
                "es": "Náusea",
                "sw": "Kichefuchefu",
                "fa": "تهوع",
                "ps": "زړه بدوالی",
                "ur": "متلی",
                "bn": "বমি বমি ভাব",
                "hi": "मिचली",
            },
            hierarchy=SNOMEDHierarchy.CLINICAL_FINDING,
        ),
        # Procedures
        "5880005": SNOMEDTranslation(
            concept_id="5880005",
            fsn="Physical examination procedure (procedure)",
            preferred_term_en="Physical examination",
            translations={
                "ar": "الفحص البدني",
                "fr": "Examen physique",
                "es": "Examen físico",
                "sw": "Uchunguzi wa mwili",
                "fa": "معاینه فیزیکی",
                "ps": "فزیکي معاینه",
                "ur": "جسمانی معائنہ",
                "bn": "শারীরিক পরীক্ষা",
                "hi": "शारीरिक परीक्षण",
            },
            hierarchy=SNOMEDHierarchy.PROCEDURE,
        ),
        "33879002": SNOMEDTranslation(
            concept_id="33879002",
            fsn="Administration of vaccine to produce active immunity (procedure)",
            preferred_term_en="Vaccination",
            translations={
                "ar": "التطعيم",
                "fr": "Vaccination",
                "es": "Vacunación",
                "sw": "Chanjo",
                "fa": "واکسیناسیون",
                "ps": "واکسین",
                "ur": "ٹیکہ لگانا",
                "bn": "টিকাদান",
                "hi": "टीकाकरण",
            },
            hierarchy=SNOMEDHierarchy.PROCEDURE,
        ),
        # Observable entities
        "271649006": SNOMEDTranslation(
            concept_id="271649006",
            fsn="Systolic blood pressure (observable entity)",
            preferred_term_en="Systolic blood pressure",
            translations={
                "ar": "ضغط الدم الانقباضي",
                "fr": "Pression artérielle systolique",
                "es": "Presión arterial sistólica",
                "sw": "Shinikizo la damu la juu",
                "fa": "فشار خون سیستولیک",
                "ps": "سیستولیک د وینې فشار",
                "ur": "سسٹولک بلڈ پریشر",
                "bn": "সিস্টোলিক রক্তচাপ",
                "hi": "सिस्टोलिक रक्तचाप",
            },
            hierarchy=SNOMEDHierarchy.OBSERVABLE_ENTITY,
        ),
        "271650006": SNOMEDTranslation(
            concept_id="271650006",
            fsn="Diastolic blood pressure (observable entity)",
            preferred_term_en="Diastolic blood pressure",
            translations={
                "ar": "ضغط الدم الانبساطي",
                "fr": "Pression artérielle diastolique",
                "es": "Presión arterial diastólica",
                "sw": "Shinikizo la damu la chini",
                "fa": "فشار خون دیاستولیک",
                "ps": "ډیاستولیک د وینې فشار",
                "ur": "ڈائیسٹولک بلڈ پریشر",
                "bn": "ডায়াস্টোলিক রক্তচাপ",
                "hi": "डायस्टोलिक रक्तचाप",
            },
            hierarchy=SNOMEDHierarchy.OBSERVABLE_ENTITY,
        ),
    }

    def __init__(self) -> None:
        """Initialize SNOMED translation manager."""
        self.translations = self.COMMON_SNOMED_TRANSLATIONS.copy()

        # Load extended translations if available
        # Extended translations removed - will be implemented later

        self._hierarchy_index = self._build_hierarchy_index()
        self._emergency_concepts = self._build_emergency_index()

    def _build_hierarchy_index(self) -> Dict[SNOMEDHierarchy, List[str]]:
        """Build index of SNOMED concepts by hierarchy."""
        index: Dict[SNOMEDHierarchy, List[str]] = {}
        for concept_id, translation in self.translations.items():
            hierarchy = translation.hierarchy
            if hierarchy not in index:
                index[hierarchy] = []
            index[hierarchy].append(concept_id)
        return index

    def _build_emergency_index(self) -> Set[str]:
        """Build set of emergency SNOMED concepts."""
        return {
            concept_id
            for concept_id, translation in self.translations.items()
            if translation.is_emergency
        }

    def get_translation(self, concept_id: str, target_language: str) -> Optional[str]:
        """Get translation for SNOMED concept."""
        if concept_id not in self.translations:
            return None

        translation_data = self.translations[concept_id]

        if target_language == "en":
            return translation_data.preferred_term_en

        return translation_data.translations.get(
            target_language, translation_data.preferred_term_en
        )

    def get_by_hierarchy(self, hierarchy: SNOMEDHierarchy) -> List[str]:
        """Get all SNOMED concepts in a hierarchy."""
        return self._hierarchy_index.get(hierarchy, [])

    def is_emergency_concept(self, concept_id: str) -> bool:
        """Check if SNOMED concept is emergency-related."""
        return concept_id in self._emergency_concepts

    def search_by_term(self, query: str, language: str = "en") -> List[Dict[str, Any]]:
        """Search SNOMED concepts by term."""
        query_lower = query.lower()
        results = []

        for concept_id, translation_data in self.translations.items():
            # Search in preferred term
            term = (
                translation_data.preferred_term_en
                if language == "en"
                else translation_data.translations.get(language, "")
            )

            # Also search in FSN and synonyms for English
            search_terms = [term.lower()]
            if language == "en":
                search_terms.append(translation_data.fsn.lower())
                if translation_data.synonyms:
                    search_terms.extend([s.lower() for s in translation_data.synonyms])

            if any(query_lower in st for st in search_terms):
                results.append(
                    {
                        "concept_id": concept_id,
                        "term": term,
                        "fsn": translation_data.fsn,
                        "hierarchy": translation_data.hierarchy.value,
                        "is_emergency": translation_data.is_emergency,
                    }
                )

        return results


# Global instance
snomed_manager = SNOMEDTranslationManager()
