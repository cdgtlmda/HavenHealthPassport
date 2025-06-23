"""Drug Name Mapping System.

This module handles drug name translations and mappings across multiple languages,
including brand names, generic names, and international non-proprietary names (INN).
"""

import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from src.security.access_control import AccessPermission, require_permission
from src.security.audit import audit_phi_access
from src.security.encryption import EncryptionService
from src.translation.medical.dictionary_importer import (
    DictionaryType,
    medical_dictionary_importer,
)
from src.utils.logging import get_logger

logger = get_logger(__name__)


class DrugNameType(str, Enum):
    """Types of drug names."""

    GENERIC = "generic"  # Generic/INN name
    BRAND = "brand"  # Brand/trade name
    CHEMICAL = "chemical"  # Chemical name
    STREET = "street"  # Street/colloquial name
    LOCAL = "local"  # Local/regional name


class DrugCategory(str, Enum):
    """Drug therapeutic categories."""

    ANALGESIC = "analgesic"
    ANTIBIOTIC = "antibiotic"
    ANTIVIRAL = "antiviral"
    ANTIFUNGAL = "antifungal"
    ANTIPARASITIC = "antiparasitic"
    CARDIOVASCULAR = "cardiovascular"
    RESPIRATORY = "respiratory"
    GASTROINTESTINAL = "gastrointestinal"
    NEUROLOGICAL = "neurological"
    PSYCHIATRIC = "psychiatric"
    ENDOCRINE = "endocrine"
    IMMUNOLOGICAL = "immunological"
    ONCOLOGICAL = "oncological"
    NUTRITIONAL = "nutritional"
    EMERGENCY = "emergency"


@dataclass
class DrugTranslation:
    """Drug name translation entry."""

    rxcui: str  # RxNorm Concept Unique Identifier
    generic_name: str  # International Non-Proprietary Name (INN)
    brand_names: List[str] = field(default_factory=list)
    translations: Dict[str, Dict[str, str]] = field(
        default_factory=dict
    )  # lang -> {generic, brand}
    category: DrugCategory = DrugCategory.ANALGESIC
    dosage_forms: List[str] = field(default_factory=list)
    common_strengths: List[str] = field(default_factory=list)
    warnings: Dict[str, str] = field(default_factory=dict)  # lang -> warning text
    pediatric_safe: bool = True
    pregnancy_category: Optional[str] = None
    controlled_substance: bool = False
    refugee_essential: bool = False  # Part of refugee essential medicines list


@dataclass
class DrugInteraction:
    """Drug interaction information."""

    drug1_rxcui: str
    drug2_rxcui: str
    severity: str  # major, moderate, minor
    description: Dict[str, str]  # lang -> description


class DrugNameMapper:
    """Manages drug name translations and mappings."""

    # WHO Essential Medicines for Refugee Settings
    REFUGEE_ESSENTIAL_DRUGS = {
        # Pain management
        "1191": {  # Paracetamol/Acetaminophen
            "generic": "Paracetamol",
            "category": DrugCategory.ANALGESIC,
            "strengths": ["500mg", "100mg/5ml"],
            "essential": True,
        },
        "5640": {  # Ibuprofen
            "generic": "Ibuprofen",
            "category": DrugCategory.ANALGESIC,
            "strengths": ["200mg", "400mg", "100mg/5ml"],
            "essential": True,
        },
        # Antibiotics
        "392151": {  # Amoxicillin
            "generic": "Amoxicillin",
            "category": DrugCategory.ANTIBIOTIC,
            "strengths": ["250mg", "500mg", "125mg/5ml"],
            "essential": True,
        },
        "25033": {  # Ciprofloxacin
            "generic": "Ciprofloxacin",
            "category": DrugCategory.ANTIBIOTIC,
            "strengths": ["250mg", "500mg"],
            "essential": True,
        },
        "4450": {  # Metronidazole
            "generic": "Metronidazole",
            "category": DrugCategory.ANTIBIOTIC,
            "strengths": ["250mg", "500mg"],
            "essential": True,
        },
        # Mental health
        "42347": {  # Fluoxetine
            "generic": "Fluoxetine",
            "category": DrugCategory.PSYCHIATRIC,
            "strengths": ["20mg"],
            "essential": True,
        },
        "679314": {  # Sertraline
            "generic": "Sertraline",
            "category": DrugCategory.PSYCHIATRIC,
            "strengths": ["50mg", "100mg"],
            "essential": True,
        },
        # Chronic conditions
        "6809": {  # Metformin
            "generic": "Metformin",
            "category": DrugCategory.ENDOCRINE,
            "strengths": ["500mg", "850mg", "1000mg"],
            "essential": True,
        },
        "1998": {  # Atenolol
            "generic": "Atenolol",
            "category": DrugCategory.CARDIOVASCULAR,
            "strengths": ["50mg", "100mg"],
            "essential": True,
        },
    }

    def __init__(self) -> None:
        """Initialize drug name mapper."""
        self.drug_translations: Dict[str, DrugTranslation] = {}
        self.brand_to_generic: Dict[str, str] = {}
        self.interactions: List[DrugInteraction] = []
        self.encryption_service = EncryptionService(
            kms_key_id="alias/haven-health-default"
        )
        self._initialize_essential_drugs()

    def _initialize_essential_drugs(self) -> None:
        """Initialize translations for essential refugee medicines."""
        # Paracetamol/Acetaminophen
        self.drug_translations["1191"] = DrugTranslation(
            rxcui="1191",
            generic_name="Paracetamol",
            brand_names=["Tylenol", "Panadol", "Calpol"],
            translations={
                "en": {"generic": "Acetaminophen", "brand": "Tylenol"},
                "es": {"generic": "Paracetamol", "brand": "Tylenol"},
                "fr": {"generic": "Paracétamol", "brand": "Doliprane"},
                "ar": {"generic": "باراسيتامول", "brand": "تايلينول"},
                "sw": {"generic": "Paracetamol", "brand": "Panadol"},
                "fa": {"generic": "پاراستامول", "brand": "تایلنول"},
                "ps": {"generic": "پاراسیتامول", "brand": "ټایلینول"},
                "ur": {"generic": "پیراسیٹامول", "brand": "ٹائلینول"},
                "bn": {"generic": "প্যারাসিটামল", "brand": "টাইলেনল"},
                "hi": {"generic": "पैरासिटामोल", "brand": "टाइलेनॉल"},
            },
            category=DrugCategory.ANALGESIC,
            dosage_forms=["tablet", "liquid", "suppository"],
            common_strengths=["500mg", "650mg", "100mg/5ml"],
            warnings={
                "en": "Do not exceed 4g per day. May cause liver damage with overdose.",
                "es": "No exceder 4g por día. Puede causar daño hepático con sobredosis.",
                "ar": "لا تتجاوز 4 جرام في اليوم. قد يسبب تلف الكبد مع الجرعة الزائدة.",
            },
            pediatric_safe=True,
            pregnancy_category="B",
            controlled_substance=False,
            refugee_essential=True,
        )

        # Amoxicillin
        self.drug_translations["392151"] = DrugTranslation(
            rxcui="392151",
            generic_name="Amoxicillin",
            brand_names=["Amoxil", "Trimox", "Moxatag"],
            translations={
                "en": {"generic": "Amoxicillin", "brand": "Amoxil"},
                "es": {"generic": "Amoxicilina", "brand": "Amoxil"},
                "fr": {"generic": "Amoxicilline", "brand": "Clamoxyl"},
                "ar": {"generic": "أموكسيسيلين", "brand": "أموكسيل"},
                "sw": {"generic": "Amoxicillin", "brand": "Amoxil"},
                "fa": {"generic": "آموکسی‌سیلین", "brand": "آموکسیل"},
                "ps": {"generic": "اموکسیسیلین", "brand": "اموکسیل"},
                "ur": {"generic": "اموکسیسلن", "brand": "اموکسل"},
                "bn": {"generic": "অ্যামোক্সিসিলিন", "brand": "অ্যামোক্সিল"},
                "hi": {"generic": "एमोक्सिसिलिन", "brand": "एमोक्सिल"},
            },
            category=DrugCategory.ANTIBIOTIC,
            dosage_forms=["capsule", "tablet", "liquid"],
            common_strengths=["250mg", "500mg", "125mg/5ml"],
            warnings={
                "en": "Complete full course. May cause allergic reactions in penicillin-sensitive patients.",
                "es": "Complete el curso completo. Puede causar reacciones alérgicas en pacientes sensibles a la penicilina.",
                "ar": "أكمل الدورة الكاملة. قد يسبب ردود فعل تحسسية في المرضى الحساسين للبنسلين.",
            },
            pediatric_safe=True,
            pregnancy_category="B",
            controlled_substance=False,
            refugee_essential=True,
        )

    async def import_rxnorm_data(
        self, file_path: str, language: str = "en"
    ) -> Dict[str, Any]:
        """Import RxNorm drug data."""
        logger.info(f"Importing RxNorm data from {file_path}")

        result = await medical_dictionary_importer.import_dictionary(
            DictionaryType.RXNORM, file_path, language=language
        )

        if result["status"] == "success":
            self._process_imported_drugs(language)

        return result

    @audit_phi_access("phi_access__process_imported_drugs")
    @require_permission(AccessPermission.READ_PHI)
    def _process_imported_drugs(self, language: str) -> None:
        """Process imported drug data."""
        drugs = medical_dictionary_importer.search_term(
            "", dictionary_type=DictionaryType.RXNORM, language=language, fuzzy=False
        )

        for drug_entry in drugs:
            if drug_entry.code not in self.drug_translations:
                self.drug_translations[drug_entry.code] = DrugTranslation(
                    rxcui=drug_entry.code,
                    generic_name=drug_entry.primary_term,
                    brand_names=[],
                    translations={language: {"generic": drug_entry.primary_term}},
                    category=self._determine_category(drug_entry.primary_term),
                    dosage_forms=[],
                    common_strengths=[],
                    warnings={},
                    pediatric_safe=True,
                    pregnancy_category=None,
                    controlled_substance=False,
                    refugee_essential=drug_entry.code in self.REFUGEE_ESSENTIAL_DRUGS,
                )

    def _determine_category(self, drug_name: str) -> DrugCategory:
        """Determine drug category from name."""
        drug_lower = drug_name.lower()

        category_keywords = {
            DrugCategory.ANTIBIOTIC: ["cillin", "mycin", "floxacin", "cycline"],
            DrugCategory.ANALGESIC: [
                "acetaminophen",
                "ibuprofen",
                "aspirin",
                "morphine",
            ],
            DrugCategory.CARDIOVASCULAR: [
                "atenolol",
                "metoprolol",
                "amlodipine",
                "statin",
            ],
            DrugCategory.PSYCHIATRIC: [
                "fluoxetine",
                "sertraline",
                "diazepam",
                "olanzapine",
            ],
            DrugCategory.ENDOCRINE: ["metformin", "insulin", "thyroxine"],
        }

        for category, keywords in category_keywords.items():
            if any(keyword in drug_lower for keyword in keywords):
                return category

        return DrugCategory.ANALGESIC  # Default

    def translate_drug_name(
        self,
        drug_name: str,
        source_language: str,  # pylint: disable=unused-argument
        target_language: str,
        name_type: DrugNameType = DrugNameType.GENERIC,
    ) -> Optional[str]:
        """Translate a drug name between languages."""
        # First try to find by generic name
        for _, drug in self.drug_translations.items():
            if drug.generic_name.lower() == drug_name.lower():
                translations = drug.translations.get(target_language, {})
                return translations.get(name_type.value, drug.generic_name)

            # Check brand names
            if drug_name in drug.brand_names:
                translations = drug.translations.get(target_language, {})
                return translations.get("brand", drug_name)

        return None

    def search_drug(
        self, search_term: str, language: str, include_brands: bool = True
    ) -> List[Dict[str, Any]]:
        """Search for drugs by name in specified language."""
        results = []
        search_lower = search_term.lower()

        for _, drug in self.drug_translations.items():
            # Search in generic name
            translations = drug.translations.get(language, {})
            generic_name = translations.get("generic", drug.generic_name)

            if search_lower in generic_name.lower():
                results.append(self._format_drug_result(drug, language))
                continue

            # Search in brand names
            if include_brands:
                brand_name = translations.get("brand", "")
                if brand_name and search_lower in brand_name.lower():
                    results.append(self._format_drug_result(drug, language))
                    continue

                # Check original brand names
                for brand in drug.brand_names:
                    if search_lower in brand.lower():
                        results.append(self._format_drug_result(drug, language))
                        break

        return results

    def _format_drug_result(
        self, drug: DrugTranslation, language: str
    ) -> Dict[str, Any]:
        """Format drug information for search results."""
        translations = drug.translations.get(language, {})

        return {
            "rxcui": drug.rxcui,
            "generic_name": translations.get("generic", drug.generic_name),
            "brand_name": translations.get(
                "brand", drug.brand_names[0] if drug.brand_names else ""
            ),
            "category": drug.category.value,
            "dosage_forms": drug.dosage_forms,
            "common_strengths": drug.common_strengths,
            "refugee_essential": drug.refugee_essential,
            "warnings": drug.warnings.get(language, ""),
        }

    def get_drug_info(self, rxcui: str, language: str) -> Optional[Dict[str, Any]]:
        """Get complete drug information in specified language."""
        drug = self.drug_translations.get(rxcui)
        if not drug:
            return None

        translations = drug.translations.get(language, {})

        return {
            "rxcui": rxcui,
            "generic_name": translations.get("generic", drug.generic_name),
            "brand_names": (
                [translations.get("brand")]
                if translations.get("brand")
                else drug.brand_names
            ),
            "category": drug.category.value,
            "dosage_forms": drug.dosage_forms,
            "common_strengths": drug.common_strengths,
            "warnings": drug.warnings.get(language, drug.warnings.get("en", "")),
            "pediatric_safe": drug.pediatric_safe,
            "pregnancy_category": drug.pregnancy_category,
            "controlled_substance": drug.controlled_substance,
            "refugee_essential": drug.refugee_essential,
        }

    def get_generic_name(self, brand_name: str, language: str = "en") -> Optional[str]:
        """Get generic name for a brand name."""
        brand_lower = brand_name.lower()

        for drug in self.drug_translations.values():
            if any(brand.lower() == brand_lower for brand in drug.brand_names):
                translations = drug.translations.get(language, {})
                return translations.get("generic", drug.generic_name)

        return None

    def get_refugee_essential_drugs(
        self, language: str, category: Optional[DrugCategory] = None
    ) -> List[Dict[str, Any]]:
        """Get list of essential drugs for refugee settings."""
        results = []

        for drug in self.drug_translations.values():
            if not drug.refugee_essential:
                continue

            if category and drug.category != category:
                continue

            results.append(self._format_drug_result(drug, language))

        return sorted(results, key=lambda x: x["generic_name"])

    def check_drug_interaction(
        self, drug1_rxcui: str, drug2_rxcui: str
    ) -> Optional[Dict[str, Any]]:
        """Check for drug interactions."""
        for interaction in self.interactions:
            if (
                interaction.drug1_rxcui == drug1_rxcui
                and interaction.drug2_rxcui == drug2_rxcui
            ) or (
                interaction.drug1_rxcui == drug2_rxcui
                and interaction.drug2_rxcui == drug1_rxcui
            ):
                return {
                    "severity": interaction.severity,
                    "description": interaction.description,
                }

        return None

    def validate_prescription(
        self,
        rxcui: str,
        patient_age: Optional[int] = None,
        is_pregnant: bool = False,
        other_drugs: Optional[List[str]] = None,
    ) -> Tuple[bool, List[str]]:
        """Validate prescription for patient."""
        issues = []

        drug = self.drug_translations.get(rxcui)
        if not drug:
            return False, ["Unknown drug"]

        # Check pediatric safety
        if patient_age and patient_age < 18 and not drug.pediatric_safe:
            issues.append("Not recommended for pediatric use")

        # Check pregnancy safety
        if is_pregnant and drug.pregnancy_category in ["D", "X"]:
            issues.append(
                f"Pregnancy category {drug.pregnancy_category} - not recommended"
            )

        # Check interactions
        if other_drugs:
            for other_rxcui in other_drugs:
                interaction = self.check_drug_interaction(rxcui, other_rxcui)
                if interaction and interaction["severity"] == "major":
                    issues.append(f"Major interaction with drug {other_rxcui}")

        return len(issues) == 0, issues

    def export_drug_list(
        self, output_path: str, languages: List[str], essential_only: bool = False
    ) -> bool:
        """Export drug list with translations."""
        export_data = []

        for drug in self.drug_translations.values():
            if essential_only and not drug.refugee_essential:
                continue

            row = {
                "rxcui": drug.rxcui,
                "category": drug.category.value,
                "dosage_forms": "; ".join(drug.dosage_forms),
                "strengths": "; ".join(drug.common_strengths),
                "refugee_essential": drug.refugee_essential,
            }

            # Add translations for each language
            for lang in languages:
                translations = drug.translations.get(lang, {})
                row[f"generic_{lang}"] = translations.get("generic", drug.generic_name)
                row[f"brand_{lang}"] = translations.get("brand", "")
                row[f"warning_{lang}"] = drug.warnings.get(lang, "")

            export_data.append(row)

        # Write to JSON
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(export_data, f, ensure_ascii=False, indent=2)

        logger.info(f"Exported {len(export_data)} drugs to {output_path}")
        return True


# Global drug mapper instance
drug_mapper = DrugNameMapper()
