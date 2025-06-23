"""ICD-10 Translation Configuration.

This module handles ICD-10 code translations across multiple languages,
ensuring accurate medical classification in healthcare records.

This module handles PHI with encryption and access control to ensure HIPAA compliance.
It includes FHIR Resource typing and validation for healthcare data.
"""

import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from src.healthcare.fhir.validators import FHIRValidator
from src.security.access_control import AccessPermission, require_permission
from src.security.audit import audit_phi_access
from src.security.encryption import EncryptionService
from src.translation.medical.dictionary_importer import (
    DictionaryType,
    medical_dictionary_importer,
)
from src.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class ICD10Translation:
    """ICD-10 code with translations."""

    code: str
    chapter: str
    category: str
    subcategory: Optional[str]
    english_description: str
    translations: Dict[str, str]  # language -> translation
    clinical_notes: Dict[str, str]  # language -> clinical notes
    is_billable: bool
    valid_for_submission: bool
    age_restrictions: Optional[Dict[str, Any]]
    sex_restrictions: Optional[str]  # M, F, or None


class ICD10TranslationManager:
    """Manages ICD-10 translations across languages."""

    # ICD-10 chapters
    ICD10_CHAPTERS = {
        "A00-B99": "Certain infectious and parasitic diseases",
        "C00-D49": "Neoplasms",
        "D50-D89": "Diseases of blood and blood-forming organs",
        "E00-E89": "Endocrine, nutritional and metabolic diseases",
        "F01-F99": "Mental and behavioral disorders",
        "G00-G99": "Diseases of the nervous system",
        "H00-H59": "Diseases of the eye and adnexa",
        "H60-H95": "Diseases of the ear and mastoid process",
        "I00-I99": "Diseases of the circulatory system",
        "J00-J99": "Diseases of the respiratory system",
        "K00-K95": "Diseases of the digestive system",
        "L00-L99": "Diseases of the skin and subcutaneous tissue",
        "M00-M99": "Diseases of the musculoskeletal system",
        "N00-N99": "Diseases of the genitourinary system",
        "O00-O9A": "Pregnancy, childbirth and the puerperium",
        "P00-P96": "Certain conditions originating in perinatal period",
        "Q00-Q99": "Congenital malformations and chromosomal abnormalities",
        "R00-R99": "Symptoms, signs and abnormal findings",
        "S00-T88": "Injury, poisoning and external causes",
        "V00-Y99": "External causes of morbidity",
        "Z00-Z99": "Factors influencing health status",
    }

    # Common ICD-10 codes for refugees/displaced populations
    REFUGEE_COMMON_CODES = {
        "Z59.0": "Homelessness",
        "Z59.5": "Extreme poverty",
        "Z60.2": "Problems related to living alone",
        "Z60.3": "Acculturation difficulty",
        "Z65.5": "Exposure to disaster, war and other hostilities",
        "F43.1": "Post-traumatic stress disorder",
        "F43.8": "Other reactions to severe stress",
        "Z91.5": "Personal history of self-harm",
        "B20-B24": "HIV disease",
        "A15-A19": "Tuberculosis",
        "B15-B19": "Viral hepatitis",
        "E40-E46": "Malnutrition",
        "F32": "Depressive episode",
        "F41": "Other anxiety disorders",
    }

    def __init__(self) -> None:
        """Initialize ICD-10 translation manager."""
        self.translations: Dict[str, ICD10Translation] = {}
        self.language_mappings: Dict[str, Dict[str, str]] = {}
        self.fhir_validator = FHIRValidator()
        self.encryption_service = EncryptionService(
            kms_key_id="alias/haven-health-default"
        )
        self._load_base_translations()

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
                encrypted_data[field] = self.encryption_service.encrypt(
                    str(encrypted_data[field]).encode()
                )

        return encrypted_data

    def _load_base_translations(self) -> None:
        """Load base ICD-10 translations."""
        # Load common refugee-related codes with translations
        self._initialize_refugee_codes()

    def _initialize_refugee_codes(self) -> None:
        """Initialize translations for common refugee conditions."""
        # Example translations for Z65.5 (war exposure)
        self.translations["Z65.5"] = ICD10Translation(
            code="Z65.5",
            chapter="Z00-Z99",
            category="Z65",
            subcategory="5",
            english_description="Exposure to disaster, war and other hostilities",
            translations={
                "es": "Exposición a desastres, guerra y otras hostilidades",
                "fr": "Exposition aux catastrophes, à la guerre et autres hostilités",
                "ar": "التعرض للكوارث والحرب والأعمال العدائية الأخرى",
                "sw": "Kuathiriwa na majanga, vita na uhasama mwingine",
                "fa": "قرار گرفتن در معرض بلایا، جنگ و سایر خصومت‌ها",
                "ps": "د ناورین، جګړې او نورو دښمنیو سره مخامخ کیدل",
                "ur": "آفات، جنگ اور دیگر دشمنیوں کا سامنا",
                "bn": "দুর্যোগ, যুদ্ধ এবং অন্যান্য শত্রুতার সম্মুখীন হওয়া",
                "hi": "आपदा, युद्ध और अन्य शत्रुता के संपर्क में आना",
            },
            clinical_notes={
                "en": "Document specific exposures and duration",
                "es": "Documentar exposiciones específicas y duración",
                "ar": "توثيق التعرضات المحددة والمدة",
            },
            is_billable=True,
            valid_for_submission=True,
            age_restrictions=None,
            sex_restrictions=None,
        )

        # F43.1 - PTSD
        self.translations["F43.1"] = ICD10Translation(
            code="F43.1",
            chapter="F01-F99",
            category="F43",
            subcategory="1",
            english_description="Post-traumatic stress disorder",
            translations={
                "es": "Trastorno de estrés postraumático",
                "fr": "Trouble de stress post-traumatique",
                "ar": "اضطراب ما بعد الصدمة",
                "sw": "Ugonjwa wa msongo wa mawazo baada ya kiwewe",
                "fa": "اختلال استرس پس از سانحه",
                "ps": "د صدمې وروسته فشار ګډوډي",
                "ur": "صدمے کے بعد کا تناؤ کی خرابی",
                "bn": "মানসিক আঘাত পরবর্তী চাপ ব্যাধি",
                "hi": "अभिघातजन्य तनाव विकार",
            },
            clinical_notes={
                "en": "Screen for trauma history, nightmares, avoidance behaviors",
                "es": "Evaluar historia de trauma, pesadillas, conductas de evitación",
                "ar": "فحص تاريخ الصدمة والكوابيس وسلوكيات التجنب",
            },
            is_billable=True,
            valid_for_submission=True,
            age_restrictions=None,
            sex_restrictions=None,
        )

    async def import_icd10_translations(
        self, file_path: str, source_language: str = "en"
    ) -> Dict[str, Any]:
        """Import ICD-10 translations from file."""
        logger.info(f"Importing ICD-10 translations from {file_path}")

        # Use the medical dictionary importer
        result = await medical_dictionary_importer.import_dictionary(
            DictionaryType.ICD10, file_path, language=source_language
        )

        if result["status"] == "success":
            # Load translations into our manager
            self._process_imported_codes(source_language)

        return result

    def _process_imported_codes(self, language: str) -> None:
        """Process imported ICD-10 codes."""
        # Get codes from importer
        codes = medical_dictionary_importer.search_term(
            "",  # Get all
            dictionary_type=DictionaryType.ICD10,
            language=language,
            fuzzy=False,
        )

        for code_entry in codes:
            if code_entry.code not in self.translations:
                self.translations[code_entry.code] = ICD10Translation(
                    code=code_entry.code,
                    chapter=self._get_chapter(code_entry.code),
                    category=code_entry.category or "",
                    subcategory=None,
                    english_description=code_entry.primary_term,
                    translations={language: code_entry.primary_term},
                    clinical_notes={},
                    is_billable=self._is_billable_code(code_entry.code),
                    valid_for_submission=True,
                    age_restrictions=None,
                    sex_restrictions=None,
                )

    def _get_chapter(self, code: str) -> str:
        """Get ICD-10 chapter for a code."""
        # Extract letter and number parts
        if not code:
            return ""

        code_upper = code.upper()

        for chapter_range, _ in self.ICD10_CHAPTERS.items():
            start, end = chapter_range.split("-")
            if self._is_code_in_range(code_upper, start, end):
                return chapter_range

        return "Unknown"

    def _is_code_in_range(self, code: str, start: str, end: str) -> bool:
        """Check if code is within range."""
        try:
            # Simple comparison for ICD-10 codes
            return start <= code <= end
        except (TypeError, ValueError):
            return False

    def _is_billable_code(self, code: str) -> bool:
        """Check if ICD-10 code is billable."""
        # Billable codes typically have specific character lengths
        # This is a simplified check
        code_clean = code.replace(".", "")
        return len(code_clean) >= 3

    def get_translation(
        self, code: str, language: str, include_clinical_notes: bool = False
    ) -> Optional[Dict[str, str]]:
        """Get ICD-10 translation for a specific language."""
        icd_translation = self.translations.get(code)
        if not icd_translation:
            return None

        result = {
            "code": code,
            "description": icd_translation.translations.get(
                language, icd_translation.english_description
            ),
            "chapter": icd_translation.chapter,
            "is_billable": icd_translation.is_billable,
        }

        if include_clinical_notes:
            result["clinical_notes"] = icd_translation.clinical_notes.get(
                language, icd_translation.clinical_notes.get("en", "")
            )

        return result  # type: ignore[return-value]

    def search_by_description(
        self, search_term: str, language: str, limit: int = 10
    ) -> List[Dict[str, str]]:
        """Search ICD-10 codes by description."""
        results = []
        search_lower = search_term.lower()

        for code, translation in self.translations.items():
            # Search in the specified language
            description = translation.translations.get(
                language, translation.english_description
            )

            if search_lower in description.lower():
                results.append(
                    {
                        "code": code,
                        "description": description,
                        "english": translation.english_description,
                        "chapter": translation.chapter,
                        "is_billable": translation.is_billable,
                    }
                )

                if len(results) >= limit:
                    break

        return results  # type: ignore[return-value]

    def get_chapter_codes(self, chapter: str, language: str) -> List[Dict[str, Any]]:
        """Get all codes in a chapter with translations."""
        codes = []

        for code, translation in self.translations.items():
            if translation.chapter == chapter:
                codes.append(
                    {
                        "code": code,
                        "description": translation.translations.get(
                            language, translation.english_description
                        ),
                        "category": translation.category,
                        "is_billable": translation.is_billable,
                    }
                )

        return sorted(codes, key=lambda x: x["code"])

    def validate_code(
        self,
        code: str,
        patient_age: Optional[int] = None,
        patient_sex: Optional[str] = None,
    ) -> Tuple[bool, List[str]]:
        """Validate ICD-10 code for patient demographics."""
        issues = []

        translation = self.translations.get(code)
        if not translation:
            return False, ["Invalid ICD-10 code"]

        # Check age restrictions
        if patient_age and translation.age_restrictions:
            min_age = translation.age_restrictions.get("min")
            max_age = translation.age_restrictions.get("max")

            if min_age and patient_age < min_age:
                issues.append(f"Patient too young (min age: {min_age})")
            if max_age and patient_age > max_age:
                issues.append(f"Patient too old (max age: {max_age})")

        # Check sex restrictions
        if patient_sex and translation.sex_restrictions:
            if patient_sex != translation.sex_restrictions:
                issues.append(f"Code restricted to {translation.sex_restrictions}")

        # Check if billable
        if not translation.is_billable:
            issues.append("Code is not billable")

        return len(issues) == 0, issues

    def get_refugee_specific_codes(self, language: str) -> List[Dict[str, str]]:
        """Get ICD-10 codes commonly used for refugee populations."""
        codes = []

        for code, description in self.REFUGEE_COMMON_CODES.items():
            translation = self.translations.get(code)
            if translation:
                codes.append(
                    {
                        "code": code,
                        "description": translation.translations.get(
                            language, description
                        ),
                        "english": description,
                        "category": "refugee_common",
                    }
                )

        return codes

    def export_translations(
        self, output_path: str, languages: List[str], codes: Optional[List[str]] = None
    ) -> bool:
        """Export ICD-10 translations to file."""
        export_data = []

        codes_to_export = codes or list(self.translations.keys())

        for code in codes_to_export:
            translation = self.translations.get(code)
            if not translation:
                continue

            row = {
                "code": code,
                "english": translation.english_description,
                "chapter": translation.chapter,
                "is_billable": translation.is_billable,
            }

            # Add translations for each language
            for lang in languages:
                row[f"translation_{lang}"] = translation.translations.get(lang, "")

            export_data.append(row)

        # Write to JSON
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(export_data, f, ensure_ascii=False, indent=2)

        logger.info(f"Exported {len(export_data)} ICD-10 translations")
        return True


# Global ICD-10 manager
icd10_manager = ICD10TranslationManager()
