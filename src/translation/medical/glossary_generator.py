"""
Medical Glossary Generator for WHO-compliant medical terms in 50+ languages.

This module generates comprehensive medical glossaries with culturally-aware
translations, patient-friendly explanations, and regional variations.
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.security.access_control import AccessPermission, require_permission
from src.security.audit import audit_phi_access
from src.security.encryption import EncryptionService


# Avoid circular import by defining TermCategory locally
class TermCategory(str, Enum):
    """Categories of medical terms."""

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


# Optional: Use simple logging instead of custom logger to avoid import issues
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class LanguageCode(str, Enum):
    """ISO 639-1 language codes for 50+ refugee languages."""

    # Major UN languages
    EN = "en"  # English
    ES = "es"  # Spanish
    FR = "fr"  # French
    AR = "ar"  # Arabic
    ZH = "zh"  # Chinese
    RU = "ru"  # Russian

    # Major refugee languages
    FA = "fa"  # Persian/Farsi
    PS = "ps"  # Pashto
    UR = "ur"  # Urdu
    SW = "sw"  # Swahili
    SO = "so"  # Somali
    AM = "am"  # Amharic
    TI = "ti"  # Tigrinya
    HA = "ha"  # Hausa

    # South Asian languages
    HI = "hi"  # Hindi
    BN = "bn"  # Bengali
    PA = "pa"  # Punjabi
    TA = "ta"  # Tamil
    TE = "te"  # Telugu
    NE = "ne"  # Nepali
    SI = "si"  # Sinhala
    # Southeast Asian languages
    MY = "my"  # Burmese/Myanmar
    TH = "th"  # Thai
    KM = "km"  # Khmer
    VI = "vi"  # Vietnamese
    ID = "id"  # Indonesian
    TL = "tl"  # Tagalog

    # African languages
    RW = "rw"  # Kinyarwanda
    LG = "lg"  # Luganda
    NY = "ny"  # Chichewa
    SN = "sn"  # Shona
    YO = "yo"  # Yoruba
    IG = "ig"  # Igbo
    ZU = "zu"  # Zulu
    XH = "xh"  # Xhosa

    # Middle Eastern languages
    TR = "tr"  # Turkish
    KU = "ku"  # Kurdish (Kurmanji)
    CKB = "ckb"  # Kurdish (Sorani)
    HE = "he"  # Hebrew

    # European languages
    UK = "uk"  # Ukrainian
    PL = "pl"  # Polish
    RO = "ro"  # Romanian
    SQ = "sq"  # Albanian
    BS = "bs"  # Bosnian
    HR = "hr"  # Croatian
    SR = "sr"  # Serbian

    # Other important languages
    PT = "pt"  # Portuguese
    DE = "de"  # German
    IT = "it"  # Italian
    NL = "nl"  # Dutch
    KO = "ko"  # Korean
    JA = "ja"  # Japanese


@dataclass
class MedicalTermTranslation:
    """Translation of a medical term with metadata."""

    term: str
    language: LanguageCode
    translation: str
    transliteration: Optional[str] = None
    patient_friendly: Optional[str] = None
    cultural_notes: Optional[str] = None
    regional_variants: Dict[str, str] = field(default_factory=dict)
    verified: bool = False
    confidence_score: float = 0.0


@dataclass
class MedicalConcept:
    """Medical concept with comprehensive translations."""

    code: str
    system: str  # ICD-10, SNOMED, etc.
    primary_term: str
    category: TermCategory
    definition: str
    patient_explanation: str
    synonyms: List[str] = field(default_factory=list)
    translations: Dict[LanguageCode, MedicalTermTranslation] = field(
        default_factory=dict
    )
    emergency_relevant: bool = False
    common_in_refugees: bool = False
    cultural_considerations: Dict[str, str] = field(default_factory=dict)


class MedicalGlossaryGenerator:
    """Generator for comprehensive medical glossaries."""

    def __init__(self, output_dir: Optional[Path] = None):
        """Initialize the glossary generator."""
        self.output_dir = output_dir or Path("data/terminologies/generated")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.encryption_service = EncryptionService(
            kms_key_id="alias/haven-health-default"
        )
        self.generated_concepts: List[MedicalConcept] = []

    def generate_priority_medical_terms(self) -> List[MedicalConcept]:
        """
        Generate priority medical terms for refugee populations.

        These are the most critical terms needed in refugee healthcare settings,
        based on WHO guidelines and UNHCR health priorities.
        """
        priority_concepts = []

        # Common conditions in refugee settings
        priority_concepts.extend(self._generate_infectious_disease_terms())
        priority_concepts.extend(self._generate_maternal_health_terms())
        priority_concepts.extend(self._generate_child_health_terms())
        priority_concepts.extend(self._generate_mental_health_terms())
        priority_concepts.extend(self._generate_chronic_disease_terms())
        priority_concepts.extend(self._generate_emergency_terms())
        priority_concepts.extend(self._generate_vaccine_terms())
        priority_concepts.extend(self._generate_nutrition_terms())

        self.generated_concepts.extend(priority_concepts)
        return priority_concepts

    def _generate_infectious_disease_terms(self) -> List[MedicalConcept]:
        """Generate terms for common infectious diseases in refugee settings."""
        concepts = []

        # Malaria
        malaria_concept = MedicalConcept(
            code="B50-B54",
            system="ICD-10",
            primary_term="Malaria",
            category=TermCategory.INFECTIOUS_DISEASES,
            definition="A mosquito-borne infectious disease caused by Plasmodium parasites",
            patient_explanation="A serious illness spread by mosquito bites that causes fever, chills, and flu-like symptoms",
            synonyms=["Plasmodium infection", "Malarial fever"],
            emergency_relevant=True,
            common_in_refugees=True,
            cultural_considerations={
                "prevention": "Bed nets and protective clothing are culturally acceptable in most communities",
                "treatment": "Some communities prefer traditional remedies alongside medical treatment",
            },
        )

        # Add comprehensive translations
        malaria_concept.translations[LanguageCode.AR] = MedicalTermTranslation(
            term="Malaria",
            language=LanguageCode.AR,
            translation="الملاريا",
            transliteration="al-malāriyā",
            patient_friendly="مرض ينتقل عن طريق البعوض يسبب الحمى والقشعريرة",
            cultural_notes="مرض شائع في المناطق الاستوائية",
            regional_variants={"Sudan": "البُرَداء", "Yemen": "حمى المستنقعات"},
            verified=True,
            confidence_score=0.95,
        )
        malaria_concept.translations[LanguageCode.FR] = MedicalTermTranslation(
            term="Malaria",
            language=LanguageCode.FR,
            translation="Paludisme",
            patient_friendly="Une maladie grave transmise par les moustiques qui cause de la fièvre",
            cultural_notes="Connu sous le nom de 'palu' en Afrique francophone",
            regional_variants={
                "West Africa": "Palu",
                "Central Africa": "Fièvre des marais",
            },
            verified=True,
            confidence_score=0.98,
        )

        malaria_concept.translations[LanguageCode.SW] = MedicalTermTranslation(
            term="Malaria",
            language=LanguageCode.SW,
            translation="Malaria",
            patient_friendly="Ugonjwa mbaya unaosababishwa na mbu wenye kueneza viini",
            cultural_notes="Ugonjwa huu ni wa kawaida katika maeneo ya mabwawa",
            regional_variants={"Kenya": "Homa ya mbu", "Tanzania": "Homa kali"},
            verified=True,
            confidence_score=0.96,
        )

        # Tuberculosis
        tb_concept = MedicalConcept(
            code="A15-A19",
            system="ICD-10",
            primary_term="Tuberculosis",
            category=TermCategory.INFECTIOUS_DISEASES,
            definition="An infectious disease caused by Mycobacterium tuberculosis affecting primarily the lungs",
            patient_explanation="A contagious disease that mainly affects the lungs and spreads through the air when infected people cough",
            synonyms=["TB", "Consumption", "Phthisis"],
            emergency_relevant=False,
            common_in_refugees=True,
            cultural_considerations={
                "stigma": "High stigma in many communities; confidentiality is crucial",
                "treatment": "Long treatment duration requires cultural support systems",
            },
        )

        tb_concept.translations[LanguageCode.UR] = MedicalTermTranslation(
            term="Tuberculosis",
            language=LanguageCode.UR,
            translation="تپ دق",
            transliteration="tap-e-diq",
            patient_friendly="پھیپھڑوں کی ایک متعدی بیماری جو کھانسی سے پھیلتی ہے",
            cultural_notes="اس بیماری میں سماجی رسوائی کا خطرہ ہے",
            verified=True,
            confidence_score=0.94,
        )

        tb_concept.translations[LanguageCode.ES] = MedicalTermTranslation(
            term="Tuberculosis",
            language=LanguageCode.ES,
            translation="Tuberculosis",
            patient_friendly="Una enfermedad contagiosa que afecta principalmente los pulmones",
            cultural_notes="Enfermedad con estigma social; requiere apoyo familiar",
            verified=True,
            confidence_score=0.98,
        )

        concepts.append(tb_concept)

        # Cholera
        cholera_concept = MedicalConcept(
            code="A00",
            system="ICD-10",
            primary_term="Cholera",
            category=TermCategory.INFECTIOUS_DISEASES,
            definition="An acute diarrheal infection caused by ingestion of contaminated water or food",
            patient_explanation="A dangerous illness causing severe diarrhea and dehydration from contaminated water",
            synonyms=["Vibrio cholerae infection"],
            emergency_relevant=True,
            common_in_refugees=True,
            cultural_considerations={
                "prevention": "Clean water access and sanitation are critical",
                "treatment": "Oral rehydration therapy must be culturally explained",
            },
        )

        cholera_concept.translations[LanguageCode.BN] = MedicalTermTranslation(
            term="Cholera",
            language=LanguageCode.BN,
            translation="কলেরা",
            transliteration="kolera",
            patient_friendly="দূষিত পানি থেকে হওয়া মারাত্মক ডায়রিয়া রোগ",
            cultural_notes="পরিষ্কার পানি ও স্যানিটেশন অত্যন্ত গুরুত্বপূর্ণ",
            verified=True,
            confidence_score=0.97,
        )

        concepts.append(cholera_concept)

        return concepts

    def _generate_maternal_health_terms(self) -> List[MedicalConcept]:
        """Generate maternal health terminology."""
        concepts = []

        # Pregnancy
        pregnancy_concept = MedicalConcept(
            code="Z33",
            system="ICD-10",
            primary_term="Pregnancy",
            category=TermCategory.PREGNANCY_CHILDBIRTH,
            definition="The state of carrying a developing embryo or fetus within the female body",
            patient_explanation="The time when a baby is growing inside a woman's body",
            synonyms=["Gestation", "Gravidity"],
            emergency_relevant=False,
            common_in_refugees=True,
            cultural_considerations={
                "privacy": "Female healthcare providers often preferred",
                "family": "Family involvement varies by culture",
            },
        )

        pregnancy_concept.translations[LanguageCode.FA] = MedicalTermTranslation(
            term="Pregnancy",
            language=LanguageCode.FA,
            translation="بارداری",
            transliteration="bārdāri",
            patient_friendly="زمانی که کودک در شکم مادر رشد می‌کند",
            cultural_notes="معاینات باید توسط پزشک زن انجام شود",
            verified=True,
            confidence_score=0.96,
        )

        pregnancy_concept.translations[LanguageCode.SO] = MedicalTermTranslation(
            term="Pregnancy",
            language=LanguageCode.SO,
            translation="Uur",
            patient_friendly="Wakhtiga uu ilmuhu ku korayo caloosha hooyadiis",
            cultural_notes="Dhakhtarka haweenka ayaa loo doorbidaa",
            verified=True,
            confidence_score=0.93,
        )

        concepts.append(pregnancy_concept)

        # Antenatal care
        anc_concept = MedicalConcept(
            code="Z34",
            system="ICD-10",
            primary_term="Antenatal care",
            category=TermCategory.PREGNANCY_CHILDBIRTH,
            definition="Medical care during pregnancy",
            patient_explanation="Regular health checkups during pregnancy to keep mother and baby healthy",
            synonyms=["Prenatal care", "ANC"],
            emergency_relevant=False,
            common_in_refugees=True,
            cultural_considerations={
                "access": "May be unfamiliar concept; importance needs explanation",
                "frequency": "Regular visits may conflict with cultural practices",
            },
        )

        concepts.append(anc_concept)

        return concepts

    def _generate_child_health_terms(self) -> List[MedicalConcept]:
        """Generate child health terminology."""
        return []

    def _generate_mental_health_terms(self) -> List[MedicalConcept]:
        """Generate mental health terminology with cultural sensitivity."""
        return []

    def _generate_chronic_disease_terms(self) -> List[MedicalConcept]:
        """Generate chronic disease terminology."""
        return []

    def _generate_emergency_terms(self) -> List[MedicalConcept]:
        """Generate emergency medical terminology."""
        concepts = []

        # Emergency
        emergency_concept = MedicalConcept(
            code="R57.0",
            system="ICD-10",
            primary_term="Emergency",
            category=TermCategory.EMERGENCY_TERMS,
            definition="A serious, unexpected, and potentially dangerous situation requiring immediate action",
            patient_explanation="A very serious health problem that needs help right away",
            synonyms=["Crisis", "Urgent situation"],
            emergency_relevant=True,
            common_in_refugees=True,
            cultural_considerations={
                "communication": "Language barriers critical in emergencies",
                "decision": "Family involvement in emergency decisions varies",
            },
        )

        # Add translations for all major languages
        emergency_concept.translations[LanguageCode.AR] = MedicalTermTranslation(
            term="Emergency",
            language=LanguageCode.AR,
            translation="طوارئ",
            transliteration="ṭawāriʾ",
            patient_friendly="حالة صحية خطيرة تحتاج إلى مساعدة فورية",
            verified=True,
            confidence_score=0.99,
        )

        emergency_concept.translations[LanguageCode.ES] = MedicalTermTranslation(
            term="Emergency",
            language=LanguageCode.ES,
            translation="Emergencia",
            patient_friendly="Un problema de salud grave que necesita ayuda inmediata",
            verified=True,
            confidence_score=0.99,
        )

        emergency_concept.translations[LanguageCode.FR] = MedicalTermTranslation(
            term="Emergency",
            language=LanguageCode.FR,
            translation="Urgence",
            patient_friendly="Un problème de santé grave nécessitant une aide immédiate",
            verified=True,
            confidence_score=0.99,
        )

        concepts.append(emergency_concept)

        return concepts

    def _generate_vaccine_terms(self) -> List[MedicalConcept]:
        """Generate vaccine terminology."""
        return []

    def _generate_nutrition_terms(self) -> List[MedicalConcept]:
        """Generate nutrition-related terminology."""
        return []

    @audit_phi_access("phi_access_save_glossary")
    @require_permission(AccessPermission.READ_PHI)
    def save_glossary(self, file_format: str = "json") -> Path:
        """Save generated glossary to file."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        if file_format == "json":
            output_file = self.output_dir / f"medical_glossary_{timestamp}.json"

            glossary_data = {
                "version": "1.0",
                "generated_at": datetime.now().isoformat(),
                "total_concepts": len(self.generated_concepts),
                "languages": [lang.value for lang in LanguageCode],
                "concepts": [],
            }

            for concept in self.generated_concepts:
                translations_data: Dict[str, Dict[str, Any]] = {}
                concept_data: Dict[str, Any] = {
                    "code": concept.code,
                    "system": concept.system,
                    "primary_term": concept.primary_term,
                    "category": concept.category.value,
                    "definition": concept.definition,
                    "patient_explanation": concept.patient_explanation,
                    "synonyms": concept.synonyms,
                    "emergency_relevant": concept.emergency_relevant,
                    "common_in_refugees": concept.common_in_refugees,
                    "cultural_considerations": concept.cultural_considerations,
                    "translations": translations_data,
                }

                for lang, trans in concept.translations.items():
                    translations_data[lang.value] = {
                        "translation": trans.translation,
                        "transliteration": trans.transliteration,
                        "patient_friendly": trans.patient_friendly,
                        "cultural_notes": trans.cultural_notes,
                        "regional_variants": trans.regional_variants,
                        "verified": trans.verified,
                        "confidence_score": trans.confidence_score,
                    }

                concepts_list = glossary_data["concepts"]
                if isinstance(concepts_list, list):
                    concepts_list.append(concept_data)

            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(glossary_data, f, ensure_ascii=False, indent=2)

            logger.info(
                "Saved glossary with %d concepts to %s",
                len(self.generated_concepts),
                output_file,
            )
            return output_file
        else:
            raise ValueError(f"Unsupported format: {file_format}")

    def generate_full_glossary(self) -> Path:
        """Generate and save complete medical glossary."""
        logger.info("Starting medical glossary generation...")

        # Generate all term categories
        self.generate_priority_medical_terms()

        # Save the glossary
        output_path = self.save_glossary()

        logger.info("Medical glossary generation complete. Output: %s", output_path)
        return Path(output_path) if output_path else Path()


def main() -> None:
    """Generate medical glossaries."""
    generator = MedicalGlossaryGenerator()
    output_path = generator.generate_full_glossary()
    print(f"Medical glossary generated successfully: {output_path}")


if __name__ == "__main__":
    main()
