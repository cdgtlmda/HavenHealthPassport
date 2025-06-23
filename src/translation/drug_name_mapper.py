"""Drug Name Mapping and Translation.

This module handles drug name mapping between generic names, brand names,
and translations for multiple languages, ensuring medication safety.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.healthcare.hipaa_access_control import AccessLevel, require_phi_access
from src.security.encryption import EncryptionService
from src.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class DrugTranslation:
    """Drug with multilingual translations and brand mappings."""

    generic_name: str
    atc_code: str  # WHO ATC classification
    drug_class: str
    translations: Dict[str, str]
    brand_names: List[str] = field(default_factory=list)
    dosage_forms: List[str] = field(default_factory=list)
    is_essential: bool = True  # WHO Essential Medicines List
    is_controlled: bool = False
    refugee_health_priority: bool = True


class DrugNameMapper:
    """Manages drug name mappings and translations."""

    # WHO Essential Medicines for refugee health
    ESSENTIAL_DRUGS = {
        # Analgesics
        "paracetamol": DrugTranslation(
            generic_name="paracetamol",
            atc_code="N02BE01",
            drug_class="Analgesic/Antipyretic",
            translations={
                "ar": "باراسيتامول",
                "fr": "paracétamol",
                "es": "paracetamol",
                "sw": "paracetamol",
                "fa": "پاراستامول",
                "ps": "پاراسیټامول",
                "ur": "پیراسیٹامول",
                "bn": "প্যারাসিটামল",
                "hi": "पैरासिटामोल",
            },
            brand_names=["Tylenol", "Panadol", "Calpol"],
            dosage_forms=["tablet", "syrup", "suppository"],
        ),
        "ibuprofen": DrugTranslation(
            generic_name="ibuprofen",
            atc_code="M01AE01",
            drug_class="NSAID",
            translations={
                "ar": "إيبوبروفين",
                "fr": "ibuprofène",
                "es": "ibuprofeno",
                "sw": "ibuprofen",
                "fa": "ایبوپروفن",
                "ps": "آیبوپروفین",
                "ur": "آئبوپروفین",
                "bn": "আইবুপ্রোফেন",
                "hi": "आइबूप्रोफेन",
            },
            brand_names=["Advil", "Motrin", "Nurofen"],
            dosage_forms=["tablet", "syrup", "gel"],
        ),
        # Antibiotics
        "amoxicillin": DrugTranslation(
            generic_name="amoxicillin",
            atc_code="J01CA04",
            drug_class="Penicillin antibiotic",
            translations={
                "ar": "أموكسيسيلين",
                "fr": "amoxicilline",
                "es": "amoxicilina",
                "sw": "amoxicillin",
                "fa": "آموکسی‌سیلین",
                "ps": "اموکسیسیلین",
                "ur": "اموکسیسلن",
                "bn": "অ্যামক্সিসিলিন",
                "hi": "एमोक्सिसिलिन",
            },
            brand_names=["Amoxil", "Trimox"],
            dosage_forms=["capsule", "tablet", "suspension"],
        ),
        "azithromycin": DrugTranslation(
            generic_name="azithromycin",
            atc_code="J01FA10",
            drug_class="Macrolide antibiotic",
            translations={
                "ar": "أزيثروميسين",
                "fr": "azithromycine",
                "es": "azitromicina",
                "sw": "azithromycin",
                "fa": "آزیترومایسین",
                "ps": "ازیترومایسین",
                "ur": "ایزیتھرومائسن",
                "bn": "অ্যাজিথ্রোমাইসিন",
                "hi": "एज़िथ्रोमाइसिन",
            },
            brand_names=["Zithromax", "Z-Pak"],
            dosage_forms=["tablet", "suspension"],
        ),
        # Antimalarials
        "artemether_lumefantrine": DrugTranslation(
            generic_name="artemether + lumefantrine",
            atc_code="P01BF01",
            drug_class="Antimalarial combination",
            translations={
                "ar": "أرتيميثر + لوميفانترين",
                "fr": "artéméther + luméfantrine",
                "es": "arteméter + lumefantrina",
                "sw": "artemether + lumefantrine",
                "fa": "آرتمتر + لومفانترین",
                "ps": "ارټیمیتر + لومیفانټرین",
                "ur": "آرٹیمیتھر + لومیفینٹرین",
                "bn": "আর্টেমেথার + লুমেফ্যান্ট্রিন",
                "hi": "आर्टेमेथर + लुमेफैंट्रिन",
            },
            brand_names=["Coartem", "Riamet"],
            dosage_forms=["tablet"],
            refugee_health_priority=True,
        ),
        # Vaccines
        "bcg_vaccine": DrugTranslation(
            generic_name="BCG vaccine",
            atc_code="J07AN01",
            drug_class="Vaccine",
            translations={
                "ar": "لقاح السل",
                "fr": "vaccin BCG",
                "es": "vacuna BCG",
                "sw": "chanjo ya BCG",
                "fa": "واکسن بی‌سی‌جی",
                "ps": "د بي سي جي واکسین",
                "ur": "بی سی جی ویکسین",
                "bn": "বিসিজি টিকা",
                "hi": "बीसीजी टीका",
            },
            brand_names=["TICE BCG"],
            dosage_forms=["injection"],
            refugee_health_priority=True,
        ),
        # ORS
        "ors": DrugTranslation(
            generic_name="oral rehydration salts",
            atc_code="A07CA",
            drug_class="Electrolyte replacement",
            translations={
                "ar": "أملاح الإماهة الفموية",
                "fr": "sels de réhydratation orale",
                "es": "sales de rehidratación oral",
                "sw": "chumvi za kurudisha maji mwilini",
                "fa": "املاح بازآبرسانی خوراکی",
                "ps": "د خولې د اوبو بیا ورکولو مالګې",
                "ur": "او آر ایس",
                "bn": "ওআরএস",
                "hi": "ओआरएस",
            },
            brand_names=["Pedialyte", "Dioralyte"],
            dosage_forms=["powder"],
            refugee_health_priority=True,
        ),
    }

    def __init__(self) -> None:
        """Initialize drug name mapper."""
        self.drugs = self.ESSENTIAL_DRUGS.copy()
        self._generic_to_brands = self._build_generic_brand_index()
        self._brand_to_generic = self._build_brand_generic_index()
        self.encryption_service = EncryptionService(
            kms_key_id="alias/haven-health-default"
        )
        self._atc_index = self._build_atc_index()

    def _build_generic_brand_index(self) -> Dict[str, List[str]]:
        """Build mapping from generic names to brand names."""
        index = {}
        for generic, drug in self.drugs.items():
            index[generic.lower()] = [b.lower() for b in drug.brand_names]
        return index

    def _build_brand_generic_index(self) -> Dict[str, str]:
        """Build mapping from brand names to generic names."""
        index = {}
        for generic, drug in self.drugs.items():
            for brand in drug.brand_names:
                index[brand.lower()] = generic
        return index

    def _build_atc_index(self) -> Dict[str, str]:
        """Build mapping from ATC codes to generic names."""
        return {drug.atc_code: generic for generic, drug in self.drugs.items()}

    def get_generic_name(self, drug_name: str) -> Optional[str]:
        """
        Get generic name from any drug name (generic or brand).

        Args:
            drug_name: Drug name to look up

        Returns:
            Generic name or None
        """
        drug_lower = drug_name.lower()

        # Check if it's already a generic name
        if drug_lower in self.drugs:
            return drug_lower

        # Check if it's a brand name
        return self._brand_to_generic.get(drug_lower)

    def get_brand_names(self, generic_name: str) -> List[str]:
        """Get all brand names for a generic drug."""
        drug = self.drugs.get(generic_name.lower())
        return drug.brand_names if drug else []

    @require_phi_access(AccessLevel.READ)
    def get_translation(self, drug_name: str, target_language: str) -> Optional[str]:
        """Get translation for drug name."""
        generic = self.get_generic_name(drug_name)
        if not generic:
            return None

        drug = self.drugs[generic]

        if target_language == "en":
            return drug.generic_name

        return drug.translations.get(target_language)

    def get_drug_info(self, drug_name: str) -> Optional[Dict[str, Any]]:
        """Get complete drug information."""
        generic = self.get_generic_name(drug_name)
        if not generic:
            return None

        drug = self.drugs[generic]
        return {
            "generic_name": drug.generic_name,
            "atc_code": drug.atc_code,
            "drug_class": drug.drug_class,
            "brand_names": drug.brand_names,
            "dosage_forms": drug.dosage_forms,
            "is_essential": drug.is_essential,
            "is_controlled": drug.is_controlled,
            "refugee_health_priority": drug.refugee_health_priority,
        }

    def search_drugs(self, query: str, language: str = "en") -> List[Dict[str, str]]:
        """Search drugs by name in any language."""
        query_lower = query.lower()
        results = []

        for generic, drug in self.drugs.items():
            # Search in generic name
            if query_lower in generic:
                results.append(
                    {
                        "generic_name": drug.generic_name,
                        "drug_class": drug.drug_class,
                        "match_type": "generic",
                    }
                )
                continue

            # Search in brand names
            for brand in drug.brand_names:
                if query_lower in brand.lower():
                    results.append(
                        {
                            "generic_name": drug.generic_name,
                            "brand_name": brand,
                            "drug_class": drug.drug_class,
                            "match_type": "brand",
                        }
                    )
                    break

            # Search in translations
            if language != "en":
                translation = drug.translations.get(language, "")
                if query_lower in translation.lower():
                    results.append(
                        {
                            "generic_name": drug.generic_name,
                            "translated_name": translation,
                            "drug_class": drug.drug_class,
                            "match_type": "translation",
                        }
                    )

        return results

    def get_refugee_priority_drugs(self) -> List[str]:
        """Get list of refugee health priority drugs."""
        return [
            generic
            for generic, drug in self.drugs.items()
            if drug.refugee_health_priority
        ]

    def is_essential_medicine(self, drug_name: str) -> bool:
        """Check if drug is on WHO Essential Medicines List."""
        generic = self.get_generic_name(drug_name)
        if not generic:
            return False

        drug = self.drugs.get(generic)
        return drug.is_essential if drug else False


# Global instance
drug_mapper = DrugNameMapper()
