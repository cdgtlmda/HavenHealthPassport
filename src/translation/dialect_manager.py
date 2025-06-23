"""Dialect support for refugee languages.

This module provides comprehensive dialect support for the top 10 refugee languages,
including regional variations, script differences, and cultural adaptations.
"""

import re
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional

from src.utils.encryption import EncryptionService
from src.utils.logging import get_logger

logger = get_logger(__name__)


class Script(str, Enum):
    """Writing scripts used by different languages."""

    ARABIC = "Arab"
    LATIN = "Latn"
    CYRILLIC = "Cyrl"
    DEVANAGARI = "Deva"
    ETHIOPIC = "Ethi"
    MYANMAR = "Mymr"
    PERSIAN = "Aran"  # Arabic script for Persian languages


@dataclass
class DialectInfo:
    """Information about a specific dialect."""

    code: str  # BCP 47 language tag
    name: str
    native_name: str
    script: Script
    region: str
    variants: List[str]
    population: int  # Approximate speakers
    medical_terminology_differences: Dict[str, str]
    cultural_considerations: List[str]


class DialectManager:
    """Manages dialect variations for refugee languages."""

    # Comprehensive dialect mapping for top 10 refugee languages
    DIALECTS = {
        # Arabic dialects
        "ar": {
            "ar-EG": DialectInfo(
                code="ar-EG",
                name="Egyptian Arabic",
                native_name="مصري",
                script=Script.ARABIC,
                region="Egypt",
                variants=["Cairene", "Sa'idi", "Bedawi"],
                population=100_000_000,
                medical_terminology_differences={
                    "hospital": "مستشفى",
                    "doctor": "دكتور",
                    "medicine": "دوا",
                    "injection": "حقنة",
                },
                cultural_considerations=[
                    "Prefer same-gender healthcare providers",
                    "Family involvement in medical decisions",
                ],
            ),
            "ar-SY": DialectInfo(
                code="ar-SY",
                name="Syrian Arabic",
                native_name="شامي",
                script=Script.ARABIC,
                region="Syria",
                variants=["Damascene", "Aleppine", "Coastal"],
                population=20_000_000,
                medical_terminology_differences={
                    "hospital": "مشفى",
                    "doctor": "حكيم",
                    "medicine": "دواء",
                    "pain": "وجع",
                },
                cultural_considerations=[
                    "Extended family consultation common",
                    "Traditional remedies may be preferred initially",
                ],
            ),
            "ar-IQ": DialectInfo(
                code="ar-IQ",
                name="Iraqi Arabic",
                native_name="عراقي",
                script=Script.ARABIC,
                region="Iraq",
                variants=["Baghdadi", "Basrawi", "Moslawi"],
                population=40_000_000,
                medical_terminology_differences={
                    "hospital": "مستشفى",
                    "clinic": "عيادة",
                    "pharmacy": "صيدلية",
                    "emergency": "طوارئ",
                },
                cultural_considerations=[
                    "Privacy highly valued in medical settings",
                    "Herbal medicine commonly used alongside modern medicine",
                ],
            ),
            "ar-SD": DialectInfo(
                code="ar-SD",
                name="Sudanese Arabic",
                native_name="سوداني",
                script=Script.ARABIC,
                region="Sudan",
                variants=["Khartoum", "Kassala", "Darfur"],
                population=30_000_000,
                medical_terminology_differences={
                    "fever": "حمى",
                    "headache": "صداع",
                    "stomach": "بطن",
                    "blood": "دم",
                },
                cultural_considerations=[
                    "Traditional healing practices common",
                    "Community elders consulted for major decisions",
                ],
            ),
            "ar-YE": DialectInfo(
                code="ar-YE",
                name="Yemeni Arabic",
                native_name="يمني",
                script=Script.ARABIC,
                region="Yemen",
                variants=["San'ani", "Ta'izzi", "Hadhrami"],
                population=30_000_000,
                medical_terminology_differences={
                    "sick": "مريض",
                    "healthy": "صحي",
                    "treatment": "علاج",
                    "examination": "فحص",
                },
                cultural_considerations=[
                    "Gender separation strictly observed",
                    "Traditional medicine highly regarded",
                ],
            ),
        },
        # Kurdish dialects
        "ku": {
            "ku-ckb": DialectInfo(
                code="ku-ckb",
                name="Central Kurdish (Sorani)",
                native_name="سۆرانی",
                script=Script.PERSIAN,
                region="Iraq/Iran",
                variants=["Sulaimani", "Hawleri", "Mukryani"],
                population=8_000_000,
                medical_terminology_differences={
                    "hospital": "نەخۆشخانە",
                    "doctor": "پزیشک",
                    "nurse": "پەرستار",
                    "patient": "نەخۆش",
                },
                cultural_considerations=[
                    "Family presence important during treatment",
                    "Respect for medical authority",
                ],
            ),
            "ku-kmr": DialectInfo(
                code="ku-kmr",
                name="Northern Kurdish (Kurmanji)",
                native_name="Kurmancî",
                script=Script.LATIN,
                region="Turkey/Syria",
                variants=["Bohtan", "Mardin", "Badini"],
                population=15_000_000,
                medical_terminology_differences={
                    "hospital": "nexweşxane",
                    "doctor": "bijîşk",
                    "medicine": "derman",
                    "health": "tenduristî",
                },
                cultural_considerations=[
                    "Traditional remedies used alongside modern medicine",
                    "Community support during illness",
                ],
            ),
            "ku-sdh": DialectInfo(
                code="ku-sdh",
                name="Southern Kurdish",
                native_name="کوردی خوارین",
                script=Script.PERSIAN,
                region="Iran/Iraq",
                variants=["Feyli", "Kalhori", "Kermanshahi"],
                population=3_000_000,
                medical_terminology_differences={
                    "pain": "ئازار",
                    "fever": "تا",
                    "cold": "سەرما",
                    "cough": "کۆخە",
                },
                cultural_considerations=[
                    "Herbal medicine traditions",
                    "Elder consultation for health decisions",
                ],
            ),
        },
        # Dari/Farsi dialects
        "prs": {
            "prs-AF": DialectInfo(
                code="prs-AF",
                name="Afghan Dari",
                native_name="دری",
                script=Script.PERSIAN,
                region="Afghanistan",
                variants=["Kabuli", "Herati", "Mazari"],
                population=12_000_000,
                medical_terminology_differences={
                    "hospital": "شفاخانه",
                    "doctor": "داکتر",
                    "medicine": "دوا",
                    "injection": "پیچکاری",
                },
                cultural_considerations=[
                    "Gender-specific healthcare providers preferred",
                    "Family involvement in medical decisions",
                ],
            ),
            "prs-TJ": DialectInfo(
                code="prs-TJ",
                name="Tajik Persian",
                native_name="тоҷикӣ",
                script=Script.CYRILLIC,
                region="Tajikistan",
                variants=["Northern", "Southern", "Central"],
                population=8_000_000,
                medical_terminology_differences={
                    "hospital": "беморхона",
                    "doctor": "духтур",
                    "nurse": "ҳамшираи тиббӣ",
                    "pharmacy": "дорухона",
                },
                cultural_considerations=[
                    "Soviet medical system influence",
                    "Traditional medicine parallel use",
                ],
            ),
        },
        # Pashto dialects
        "ps": {
            "ps-AF": DialectInfo(
                code="ps-AF",
                name="Afghan Pashto",
                native_name="افغان پښتو",
                script=Script.PERSIAN,
                region="Afghanistan",
                variants=["Kandahari", "Jalalabadi", "Wardaki"],
                population=20_000_000,
                medical_terminology_differences={
                    "hospital": "روغتون",
                    "doctor": "ډاکټر",
                    "patient": "ناروغ",
                    "healthy": "روغ",
                },
                cultural_considerations=[
                    "Tribal consultation for major decisions",
                    "Traditional healing respected",
                ],
            ),
            "ps-PK": DialectInfo(
                code="ps-PK",
                name="Pakistani Pashto",
                native_name="پاکستاني پښتو",
                script=Script.PERSIAN,
                region="Pakistan",
                variants=["Peshawari", "Waziri", "Bannuchi"],
                population=30_000_000,
                medical_terminology_differences={
                    "fever": "تبه",
                    "pain": "درد",
                    "medicine": "دوا",
                    "sick": "ناجوړ",
                },
                cultural_considerations=[
                    "Family collective decisions",
                    "Religious considerations in treatment",
                ],
            ),
        },
        # Somali dialects
        "so": {
            "so-SO": DialectInfo(
                code="so-SO",
                name="Standard Somali",
                native_name="Af-Soomaali",
                script=Script.LATIN,
                region="Somalia",
                variants=["Northern", "Benaadir", "Maay"],
                population=16_000_000,
                medical_terminology_differences={
                    "hospital": "isbitaal",
                    "doctor": "dhakhtar",
                    "medicine": "dawo",
                    "sick": "buka",
                },
                cultural_considerations=[
                    "Oral consent preferred",
                    "Community support during illness",
                ],
            ),
            "so-ET": DialectInfo(
                code="so-ET",
                name="Ethiopian Somali",
                native_name="Soomaali Itoobiya",
                script=Script.LATIN,
                region="Ethiopia",
                variants=["Ogaden", "Issa"],
                population=5_000_000,
                medical_terminology_differences={
                    "clinic": "killinik",
                    "nurse": "kalkaaliye",
                    "injection": "irbad",
                    "blood": "dhiig",
                },
                cultural_considerations=[
                    "Traditional medicine integration",
                    "Clan elder involvement",
                ],
            ),
            "so-KE": DialectInfo(
                code="so-KE",
                name="Kenyan Somali",
                native_name="Soomaali Kenya",
                script=Script.LATIN,
                region="Kenya",
                variants=["NFD Somali"],
                population=2_500_000,
                medical_terminology_differences={
                    "health": "caafimaad",
                    "disease": "cudur",
                    "treatment": "daaweyn",
                    "recovery": "bogsasho",
                },
                cultural_considerations=[
                    "Multi-generational decision making",
                    "Religious healing practices",
                ],
            ),
        },
        # Swahili dialects
        "sw": {
            "sw-TZ": DialectInfo(
                code="sw-TZ",
                name="Tanzanian Swahili",
                native_name="Kiswahili cha Tanzania",
                script=Script.LATIN,
                region="Tanzania",
                variants=["Dar es Salaam", "Zanzibar", "Mombasa"],
                population=50_000_000,
                medical_terminology_differences={
                    "hospital": "hospitali",
                    "doctor": "daktari",
                    "medicine": "dawa",
                    "patient": "mgonjwa",
                },
                cultural_considerations=[
                    "Traditional healers consulted",
                    "Community health workers trusted",
                ],
            ),
            "sw-KE": DialectInfo(
                code="sw-KE",
                name="Kenyan Swahili",
                native_name="Kiswahili cha Kenya",
                script=Script.LATIN,
                region="Kenya",
                variants=["Nairobi", "Coastal", "Western"],
                population=40_000_000,
                medical_terminology_differences={
                    "clinic": "kliniki",
                    "nurse": "muuguzi",
                    "pharmacy": "duka la dawa",
                    "emergency": "dharura",
                },
                cultural_considerations=[
                    "Family consultation important",
                    "Preventive care emphasis",
                ],
            ),
            "sw-CD": DialectInfo(
                code="sw-CD",
                name="Congolese Swahili",
                native_name="Kiswahili cha Kongo",
                script=Script.LATIN,
                region="DRC",
                variants=["Lubumbashi", "Goma", "Bukavu"],
                population=10_000_000,
                medical_terminology_differences={
                    "sick": "maladi",
                    "healthy": "muzima",
                    "injection": "sindano",
                    "bandage": "bandeji",
                },
                cultural_considerations=[
                    "Community health emphasis",
                    "Traditional medicine parallel use",
                ],
            ),
        },
        # French dialects (African variants)
        "fr": {
            "fr-CD": DialectInfo(
                code="fr-CD",
                name="Congolese French",
                native_name="Français congolais",
                script=Script.LATIN,
                region="DRC",
                variants=["Kinshasa", "Katanga"],
                population=30_000_000,
                medical_terminology_differences={
                    "hospital": "hôpital",
                    "clinic": "dispensaire",
                    "medicine": "médicament",
                    "malaria": "palu",
                },
                cultural_considerations=[
                    "Traditional medicine integration",
                    "Community health workers",
                ],
            ),
            "fr-BF": DialectInfo(
                code="fr-BF",
                name="Burkinabe French",
                native_name="Français burkinabè",
                script=Script.LATIN,
                region="Burkina Faso",
                variants=["Ouagadougou", "Bobo-Dioulasso"],
                population=5_000_000,
                medical_terminology_differences={
                    "fever": "fièvre",
                    "cough": "toux",
                    "diarrhea": "diarrhée",
                    "vaccination": "vaccination",
                },
                cultural_considerations=[
                    "Village health committees",
                    "Oral health education preferred",
                ],
            ),
            "fr-RW": DialectInfo(
                code="fr-RW",
                name="Rwandan French",
                native_name="Français rwandais",
                script=Script.LATIN,
                region="Rwanda",
                variants=["Kigali"],
                population=2_000_000,
                medical_terminology_differences={
                    "health center": "centre de santé",
                    "nurse": "infirmière",
                    "appointment": "rendez-vous",
                    "prescription": "ordonnance",
                },
                cultural_considerations=[
                    "Community health insurance",
                    "Preventive care focus",
                ],
            ),
        },
        # Spanish dialects (Central American)
        "es": {
            "es-GT": DialectInfo(
                code="es-GT",
                name="Guatemalan Spanish",
                native_name="Español guatemalteco",
                script=Script.LATIN,
                region="Guatemala",
                variants=["Central", "Eastern", "Western"],
                population=17_000_000,
                medical_terminology_differences={
                    "shot": "inyección",
                    "pills": "pastillas",
                    "checkup": "chequeo",
                    "pregnancy": "embarazo",
                },
                cultural_considerations=[
                    "Indigenous medicine respect",
                    "Family-centered care",
                ],
            ),
            "es-HN": DialectInfo(
                code="es-HN",
                name="Honduran Spanish",
                native_name="Español hondureño",
                script=Script.LATIN,
                region="Honduras",
                variants=["Tegucigalpa", "San Pedro Sula"],
                population=9_000_000,
                medical_terminology_differences={
                    "sick": "enfermo",
                    "pain": "dolor",
                    "fever": "calentura",
                    "cough": "tos",
                },
                cultural_considerations=[
                    "Traditional remedies common",
                    "Extended family involvement",
                ],
            ),
            "es-SV": DialectInfo(
                code="es-SV",
                name="Salvadoran Spanish",
                native_name="Español salvadoreño",
                script=Script.LATIN,
                region="El Salvador",
                variants=["San Salvador", "Eastern"],
                population=6_500_000,
                medical_terminology_differences={
                    "doctor": "doctor",
                    "nurse": "enfermera",
                    "medicine": "medicina",
                    "hospital": "hospital",
                },
                cultural_considerations=[
                    "Community health promoters",
                    "Preventive care education",
                ],
            ),
        },
        # Tigrinya dialects
        "ti": {
            "ti-ER": DialectInfo(
                code="ti-ER",
                name="Eritrean Tigrinya",
                native_name="ትግርኛ ኤርትራ",
                script=Script.ETHIOPIC,
                region="Eritrea",
                variants=["Asmara", "Keren", "Massawa"],
                population=3_500_000,
                medical_terminology_differences={
                    "hospital": "ሆስፒታል",
                    "doctor": "ሓኪም",
                    "medicine": "መድሃኒት",
                    "sick": "ሓሚመ",
                },
                cultural_considerations=[
                    "Traditional medicine respect",
                    "Community support systems",
                ],
            ),
            "ti-ET": DialectInfo(
                code="ti-ET",
                name="Ethiopian Tigrinya",
                native_name="ትግርኛ ኢትዮጵያ",
                script=Script.ETHIOPIC,
                region="Ethiopia",
                variants=["Tigray", "Mekele"],
                population=7_000_000,
                medical_terminology_differences={
                    "clinic": "ክሊኒክ",
                    "nurse": "ነርስ",
                    "patient": "ሕሙም",
                    "health": "ጥዕና",
                },
                cultural_considerations=[
                    "Religious healing practices",
                    "Family consultation norm",
                ],
            ),
        },
        # Burmese dialects
        "my": {
            "my-MM": DialectInfo(
                code="my-MM",
                name="Standard Burmese",
                native_name="မြန်မာဘာသာ",
                script=Script.MYANMAR,
                region="Myanmar",
                variants=["Yangon", "Mandalay", "Shan"],
                population=32_000_000,
                medical_terminology_differences={
                    "hospital": "ဆေးရုံ",
                    "doctor": "ဆရာဝန်",
                    "medicine": "ဆေး",
                    "patient": "လူနာ",
                },
                cultural_considerations=[
                    "Buddhist healing practices",
                    "Respect for medical authority",
                ],
            ),
            "my-TH": DialectInfo(
                code="my-TH",
                name="Thai Burmese",
                native_name="ထိုင်းမြန်မာ",
                script=Script.MYANMAR,
                region="Thailand",
                variants=["Mae Sot", "Bangkok"],
                population=2_000_000,
                medical_terminology_differences={
                    "clinic": "ဆေးခန်း",
                    "pharmacy": "ဆေးဆိုင်",
                    "injection": "ဆေးထိုး",
                    "blood test": "သွေးစစ်",
                },
                cultural_considerations=[
                    "Cross-border health access",
                    "Language barrier considerations",
                ],
            ),
        },
    }

    def __init__(self) -> None:
        """Initialize dialect manager."""
        self._dialect_cache: Dict[str, Any] = {}
        self._initialize_dialect_patterns()
        self.encryption_service = EncryptionService()
        self._access_control_enabled = True

    def _initialize_dialect_patterns(self) -> None:
        """Initialize regex patterns for dialect detection."""
        self.dialect_patterns = {
            # Arabic dialect markers
            "ar-EG": [
                (r"\bعايز\b", 0.8),  # Egyptian "want"
                (r"\bدلوقتي\b", 0.9),  # Egyptian "now"
                (r"\bإزيك\b", 0.9),  # Egyptian greeting
            ],
            "ar-SY": [
                (r"\bشو\b", 0.8),  # Syrian "what"
                (r"\bهلق\b", 0.9),  # Syrian "now"
                (r"\bمنيح\b", 0.8),  # Syrian "good"
            ],
            "ar-IQ": [
                (r"\bشكو\b", 0.9),  # Iraqi "what's up"
                (r"\bآني\b", 0.8),  # Iraqi "I"
                (r"\bچا\b", 0.7),  # Iraqi tea
            ],
            # Kurdish dialect markers
            "ku-ckb": [
                (r"[\u0600-\u06FF]", 0.3),  # Arabic script
                (r"\bپزیشک\b", 0.9),  # Sorani "doctor"
            ],
            "ku-kmr": [
                (r"[a-zA-Z]", 0.3),  # Latin script
                (r"\bbijîşk\b", 0.9),  # Kurmanji "doctor"
            ],
        }

    def detect_dialect(
        self, text: str, base_language: str, context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Detect the specific dialect of a language.

        Args:
            text: Text to analyze
            base_language: Base language code (e.g., "ar", "ku")
            context: Optional context (region, user preferences)

        Returns:
            Specific dialect code (e.g., "ar-SY", "ku-ckb")
        """
        if base_language not in self.DIALECTS:
            return base_language

        # Check context hints first
        if context:
            if context.get("region"):
                region_hint = context["region"].upper()
                for dialect_code, info in self.DIALECTS[base_language].items():
                    if region_hint in info.region.upper():
                        return dialect_code

            if context.get("script"):
                script_hint = context["script"]
                for dialect_code, info in self.DIALECTS[base_language].items():
                    if info.script.value == script_hint:
                        return dialect_code

        # Pattern-based detection
        scores = {}
        for dialect_code in self.DIALECTS[base_language]:
            if dialect_code in self.dialect_patterns:
                score = 0.0
                for pattern, weight in self.dialect_patterns[dialect_code]:
                    if re.search(pattern, text):
                        score += weight
                scores[dialect_code] = score

        # Return highest scoring dialect or default
        if scores:
            best_dialect = max(scores, key=lambda k: scores[k])
            if scores[best_dialect] > 0.5:
                return best_dialect

        # Default to first dialect
        return list(self.DIALECTS[base_language].keys())[0]

    def get_dialect_info(self, dialect_code: str) -> Optional[DialectInfo]:
        """Get detailed information about a dialect."""
        parts = dialect_code.split("-")
        base_lang = parts[0]

        if base_lang in self.DIALECTS and dialect_code in self.DIALECTS[base_lang]:
            return self.DIALECTS[base_lang][dialect_code]

        return None

    def get_medical_terminology(self, dialect_code: str) -> Dict[str, str]:
        """Get medical terminology specific to a dialect."""
        info = self.get_dialect_info(dialect_code)
        if info:
            return info.medical_terminology_differences
        return {}

    def get_cultural_considerations(self, dialect_code: str) -> List[str]:
        """Get cultural considerations for healthcare in this dialect."""
        info = self.get_dialect_info(dialect_code)
        if info:
            return info.cultural_considerations
        return []

    def adapt_translation(
        self, text: str, source_dialect: str, target_dialect: str
    ) -> str:
        """
        Adapt translation between dialects of the same language.

        Args:
            text: Text to adapt
            source_dialect: Source dialect code
            target_dialect: Target dialect code

        Returns:
            Adapted text
        """
        # Get base languages
        source_base = source_dialect.split("-")[0]
        target_base = target_dialect.split("-")[0]

        # Only adapt within same language family
        if source_base != target_base:
            return text

        # Get terminology differences
        source_terms = self.get_medical_terminology(source_dialect)
        target_terms = self.get_medical_terminology(target_dialect)

        # Create mapping of different terms
        adaptations = {}
        for concept in source_terms:
            if (
                concept in target_terms
                and source_terms[concept] != target_terms[concept]
            ):
                adaptations[source_terms[concept]] = target_terms[concept]

        # Apply adaptations
        adapted_text = text
        for source_term, target_term in adaptations.items():
            # Use word boundary regex to avoid partial replacements
            pattern = r"\b" + re.escape(source_term) + r"\b"
            adapted_text = re.sub(
                pattern, target_term, adapted_text, flags=re.IGNORECASE
            )

        return adapted_text

    def get_script_direction(self, dialect_code: str) -> str:
        """Get text direction for the dialect's script."""
        info = self.get_dialect_info(dialect_code)
        if info:
            rtl_scripts = [Script.ARABIC, Script.PERSIAN, Script.ETHIOPIC]
            return "rtl" if info.script in rtl_scripts else "ltr"
        return "ltr"

    def format_for_dialect(self, text: str, dialect_code: str) -> str:
        """Format text appropriately for the dialect's script and conventions."""
        info = self.get_dialect_info(dialect_code)
        if not info:
            return text

        # Add appropriate formatting based on script
        if info.script in [Script.ARABIC, Script.PERSIAN]:
            # Add RTL marks if needed
            if not text.startswith("\u202b"):  # RTL embedding
                text = "\u202b" + text + "\u202c"  # Pop directional formatting

        return text

    def get_all_dialects(self, base_language: str) -> List[str]:
        """Get all available dialects for a base language."""
        if base_language in self.DIALECTS:
            return list(self.DIALECTS[base_language].keys())
        return [base_language]

    def get_dialect_name(
        self, dialect_code: str, in_language: Optional[str] = None
    ) -> str:
        """
        Get human-readable name for a dialect.

        Args:
            dialect_code: Dialect code
            in_language: Language to return name in (default: English)

        Returns:
            Dialect name
        """
        info = self.get_dialect_info(dialect_code)
        if info:
            if in_language == dialect_code or in_language == dialect_code.split("-")[0]:
                return info.native_name
            return info.name
        return dialect_code

    def suggest_dialect(
        self,
        base_language: str,
        region: Optional[str] = None,
        script: Optional[str] = None,
    ) -> str:
        """
        Suggest most appropriate dialect based on context.

        Args:
            base_language: Base language code
            region: Geographic region
            script: Preferred script

        Returns:
            Suggested dialect code
        """
        if base_language not in self.DIALECTS:
            return base_language

        candidates = []

        for dialect_code, info in self.DIALECTS[base_language].items():
            score = 0.0

            # Region matching
            if region and region.upper() in info.region.upper():
                score += 10

            # Script matching
            if script and info.script.value == script:
                score += 5

            # Population weight (prefer larger populations)
            score += info.population / 10_000_000

            candidates.append((dialect_code, score))

        # Sort by score and return best match
        candidates.sort(key=lambda x: x[1], reverse=True)
        return candidates[0][0] if candidates else base_language

    def _check_access_permission(
        self, operation: str, data: Optional[Dict] = None
    ) -> bool:
        """Check if current user has permission for the operation.

        Args:
            operation: Operation being performed
            data: Optional data being accessed

        Returns:
            True if access is permitted
        """
        # Note: 'data' parameter reserved for future use
        _ = data  # Mark as intentionally unused

        if not self._access_control_enabled:
            return True

        # In production, this would check actual user permissions
        # For now, log access attempts
        logger.info(f"Access check for operation: {operation}")
        return True

    def _encrypt_sensitive_data(self, data: str) -> str:
        """Encrypt sensitive data if it contains PHI.

        Args:
            data: Data to potentially encrypt

        Returns:
            Encrypted data if sensitive, original otherwise
        """
        # Check if data might contain PHI (names, medical terms, etc.)
        phi_indicators = ["patient", "name", "dob", "diagnosis", "medication"]

        if any(indicator in data.lower() for indicator in phi_indicators):
            return self.encryption_service.encrypt(data)

        return data

    def _decrypt_sensitive_data(self, data: str) -> str:
        """Decrypt sensitive data if encrypted.

        Args:
            data: Data to potentially decrypt

        Returns:
            Decrypted data if encrypted, original otherwise
        """
        if data.startswith("ENC:"):  # Encrypted data marker
            return self.encryption_service.decrypt(data)

        return data


# Singleton instance
_dialect_manager = DialectManager()


def get_dialect_manager() -> DialectManager:
    """Get the singleton dialect manager instance."""
    return _dialect_manager
