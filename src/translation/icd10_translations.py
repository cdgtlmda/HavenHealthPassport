"""ICD-10 Translation Configuration.

This module handles ICD-10 code translations for multiple languages,
ensuring medical accuracy for disease and condition classifications.
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from src.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class ICD10Translation:
    """ICD-10 code with multilingual translations."""

    code: str
    description_en: str
    translations: Dict[str, str]
    category: str
    is_emergency: bool = False


class ICD10TranslationManager:
    """Manages ICD-10 translations for multiple languages."""

    # Common ICD-10 codes for refugee health with translations
    COMMON_ICD10_TRANSLATIONS = {
        # Infectious diseases
        "A00": ICD10Translation(
            code="A00",
            description_en="Cholera",
            translations={
                "ar": "الكوليرا",
                "fr": "Choléra",
                "es": "Cólera",
                "sw": "Kipindupindu",
                "fa": "وبا",
                "ps": "کولرا",
                "ur": "ہیضہ",
                "bn": "কলেরা",
                "hi": "हैजा",
            },
            category="Infectious diseases",
            is_emergency=True,
        ),
        "A06": ICD10Translation(
            code="A06",
            description_en="Amoebiasis",
            translations={
                "ar": "داء الأميبات",
                "fr": "Amibiase",
                "es": "Amebiasis",
                "sw": "Ugonjwa wa amiba",
                "fa": "آمیبیاز",
                "ps": "امیبیاسیس",
                "ur": "امیبیاسس",
                "bn": "অ্যামিবিয়াসিস",
                "hi": "अमीबियासिस",
            },
            category="Infectious diseases",
        ),
        "A15": ICD10Translation(
            code="A15",
            description_en="Respiratory tuberculosis",
            translations={
                "ar": "السل الرئوي",
                "fr": "Tuberculose respiratoire",
                "es": "Tuberculosis respiratoria",
                "sw": "Kifua kikuu",
                "fa": "سل ریوی",
                "ps": "د سږو نري رنځ",
                "ur": "پھیپھڑوں کی تپ دق",
                "bn": "শ্বাসযন্ত্রের যক্ষ্মা",
                "hi": "श्वसन तपेदिक",
            },
            category="Infectious diseases",
        ),
        "B50": ICD10Translation(
            code="B50",
            description_en="Plasmodium falciparum malaria",
            translations={
                "ar": "ملاريا المتصورة المنجلية",
                "fr": "Paludisme à Plasmodium falciparum",
                "es": "Malaria por Plasmodium falciparum",
                "sw": "Malaria ya falciparum",
                "fa": "مالاریای فالسیپاروم",
                "ps": "د فالسیپارم ملاریا",
                "ur": "فالسیپیرم ملیریا",
                "bn": "প্লাজমোডিয়াম ফ্যালসিপেরাম ম্যালেরিয়া",
                "hi": "प्लाज्मोडियम फाल्सीपेरम मलेरिया",
            },
            category="Infectious diseases",
            is_emergency=True,
        ),
        # Nutritional conditions
        "E43": ICD10Translation(
            code="E43",
            description_en="Unspecified severe protein-energy malnutrition",
            translations={
                "ar": "سوء تغذية حاد شديد غير محدد",
                "fr": "Malnutrition protéino-énergétique sévère",
                "es": "Desnutrición proteico-energética severa",
                "sw": "Utapiamlo mkali",
                "fa": "سوء تغذیه شدید",
                "ps": "شدید خوارځواکي",
                "ur": "شدید غذائی کمی",
                "bn": "গুরুতর প্রোটিন-শক্তি অপুষ্টি",
                "hi": "गंभीर प्रोटीन-ऊर्जा कुपोषण",
            },
            category="Nutritional disorders",
            is_emergency=True,
        ),
        "E44.0": ICD10Translation(
            code="E44.0",
            description_en="Moderate protein-energy malnutrition",
            translations={
                "ar": "سوء تغذية بروتيني طاقي متوسط",
                "fr": "Malnutrition protéino-énergétique modérée",
                "es": "Desnutrición proteico-energética moderada",
                "sw": "Utapiamlo wa wastani",
                "fa": "سوء تغذیه متوسط",
                "ps": "منځنی خوارځواکي",
                "ur": "متوسط غذائی کمی",
                "bn": "মাঝারি প্রোটিন-শক্তি অপুষ্টি",
                "hi": "मध्यम प्रोटीन-ऊर्जा कुपोषण",
            },
            category="Nutritional disorders",
        ),
        # Mental health
        "F32": ICD10Translation(
            code="F32",
            description_en="Depressive episode",
            translations={
                "ar": "نوبة اكتئاب",
                "fr": "Épisode dépressif",
                "es": "Episodio depresivo",
                "sw": "Kipindi cha unyogovu",
                "fa": "دوره افسردگی",
                "ps": "د خپګان دوره",
                "ur": "ڈپریشن کا دورہ",
                "bn": "বিষণ্নতার পর্ব",
                "hi": "अवसादग्रस्तता प्रकरण",
            },
            category="Mental health",
        ),
        "F43.1": ICD10Translation(
            code="F43.1",
            description_en="Post-traumatic stress disorder",
            translations={
                "ar": "اضطراب ما بعد الصدمة",
                "fr": "Trouble de stress post-traumatique",
                "es": "Trastorno de estrés postraumático",
                "sw": "Shida ya msongo baada ya kiwewe",
                "fa": "اختلال استرس پس از سانحه",
                "ps": "د صدمې وروسته فشار اختلال",
                "ur": "صدمے کے بعد کا تناؤ",
                "bn": "পোস্ট-ট্রমাটিক স্ট্রেস ডিসঅর্ডার",
                "hi": "अभिघातजन्य तनाव विकार",
            },
            category="Mental health",
        ),
        # Maternal health
        "O14": ICD10Translation(
            code="O14",
            description_en="Pre-eclampsia",
            translations={
                "ar": "ما قبل تسمم الحمل",
                "fr": "Pré-éclampsie",
                "es": "Preeclampsia",
                "sw": "Hali ya kabla ya kifafa cha uzazi",
                "fa": "پره اکلامپسی",
                "ps": "د حمل مسمومیت",
                "ur": "حمل کی زہریت",
                "bn": "প্রি-এক্লাম্পসিয়া",
                "hi": "प्री-एक्लेम्पसिया",
            },
            category="Maternal health",
            is_emergency=True,
        ),
        "O72": ICD10Translation(
            code="O72",
            description_en="Postpartum hemorrhage",
            translations={
                "ar": "نزيف ما بعد الولادة",
                "fr": "Hémorragie du post-partum",
                "es": "Hemorragia posparto",
                "sw": "Kutokwa damu baada ya kuzaa",
                "fa": "خونریزی پس از زایمان",
                "ps": "د زیږون وروسته وینه بهیدل",
                "ur": "زچگی کے بعد خون بہنا",
                "bn": "প্রসবোত্তর রক্তপাত",
                "hi": "प्रसवोत्तर रक्तस्राव",
            },
            category="Maternal health",
            is_emergency=True,
        ),
        # Common symptoms
        "R50": ICD10Translation(
            code="R50",
            description_en="Fever of other and unknown origin",
            translations={
                "ar": "حمى من أصل آخر وغير معروف",
                "fr": "Fièvre d'origine autre et inconnue",
                "es": "Fiebre de otro origen y desconocido",
                "sw": "Homa isiyojulikana chanzo",
                "fa": "تب با منشأ ناشناخته",
                "ps": "د نامعلوم سبب تبه",
                "ur": "نامعلوم وجہ سے بخار",
                "bn": "অজানা উৎসের জ্বর",
                "hi": "अज्ञात कारण का बुखार",
            },
            category="Symptoms",
        ),
        "R06.0": ICD10Translation(
            code="R06.0",
            description_en="Dyspnoea",
            translations={
                "ar": "ضيق التنفس",
                "fr": "Dyspnée",
                "es": "Disnea",
                "sw": "Ugumu wa kupumua",
                "fa": "تنگی نفس",
                "ps": "د تنفس ستونزه",
                "ur": "سانس کی تکلیف",
                "bn": "শ্বাসকষ্ট",
                "hi": "सांस फूलना",
            },
            category="Symptoms",
            is_emergency=True,
        ),
    }

    def __init__(self) -> None:
        """Initialize ICD-10 translation manager."""
        self.translations = self.COMMON_ICD10_TRANSLATIONS.copy()

        # Load extended translations if available
        # Extended translations removed - will be implemented later

        self._category_index = self._build_category_index()
        self._emergency_codes = self._build_emergency_index()

    def _build_category_index(self) -> Dict[str, List[str]]:
        """Build index of ICD-10 codes by category."""
        index: Dict[str, List[str]] = {}
        for code, translation in self.translations.items():
            category = translation.category
            if category not in index:
                index[category] = []
            index[category].append(code)
        return index

    def _build_emergency_index(self) -> List[str]:
        """Build list of emergency ICD-10 codes."""
        return [
            code
            for code, translation in self.translations.items()
            if translation.is_emergency
        ]

    def get_translation(self, icd10_code: str, target_language: str) -> Optional[str]:
        """
        Get translation for ICD-10 code.

        Args:
            icd10_code: ICD-10 code
            target_language: Target language code

        Returns:
            Translated description or None
        """
        if icd10_code not in self.translations:
            return None

        translation_data = self.translations[icd10_code]

        # Return English if target language not available
        if target_language == "en":
            return translation_data.description_en

        return translation_data.translations.get(
            target_language, translation_data.description_en
        )

    def get_all_translations(self, icd10_code: str) -> Optional[Dict[str, str]]:
        """Get all translations for an ICD-10 code."""
        if icd10_code not in self.translations:
            return None

        translation_data = self.translations[icd10_code]
        result = {"en": translation_data.description_en}
        result.update(translation_data.translations)
        return result

    def get_codes_by_category(self, category: str) -> List[str]:
        """Get all ICD-10 codes in a category."""
        return self._category_index.get(category, [])

    def get_emergency_codes(self) -> List[str]:
        """Get all emergency ICD-10 codes."""
        return self._emergency_codes.copy()

    def is_emergency_code(self, icd10_code: str) -> bool:
        """Check if ICD-10 code is emergency-related."""
        return icd10_code in self._emergency_codes

    def add_translation(self, icd10_code: str, language: str, translation: str) -> bool:
        """
        Add or update translation for ICD-10 code.

        Args:
            icd10_code: ICD-10 code
            language: Language code
            translation: Translated description

        Returns:
            Success status
        """
        if icd10_code not in self.translations:
            logger.warning(f"ICD-10 code {icd10_code} not found")
            return False

        self.translations[icd10_code].translations[language] = translation
        return True

    def search_by_description(
        self, query: str, language: str = "en"
    ) -> List[Dict[str, Any]]:
        """
        Search ICD-10 codes by description.

        Args:
            query: Search query
            language: Language to search in

        Returns:
            List of matching codes with descriptions
        """
        query_lower = query.lower()
        results = []

        for code, translation_data in self.translations.items():
            description = (
                translation_data.description_en
                if language == "en"
                else translation_data.translations.get(language, "")
            )

            if query_lower in description.lower():
                results.append(
                    {
                        "code": code,
                        "description": description,
                        "category": translation_data.category,
                        "is_emergency": translation_data.is_emergency,
                    }
                )

        return results

    def export_translations(
        self, language: str, category: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Export ICD-10 translations for a language.

        Args:
            language: Target language
            category: Optional category filter

        Returns:
            List of code-translation pairs
        """
        results = []

        codes = (
            self.get_codes_by_category(category)
            if category
            else self.translations.keys()
        )

        for code in codes:
            translation = self.get_translation(code, language)
            if translation:
                results.append(
                    {
                        "code": code,
                        "description": translation,
                        "category": self.translations[code].category,
                        "is_emergency": self.translations[code].is_emergency,
                    }
                )

        return results


# Global instance
icd10_manager = ICD10TranslationManager()
