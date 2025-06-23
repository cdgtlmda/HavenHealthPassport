"""
Medical Pronunciation Database.

This module provides medical term pronunciation variants for different
accents and regions, improving medical transcription accuracy.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from .accent_profile import AccentRegion


@dataclass
class MedicalTermVariant:
    """Represents a pronunciation variant of a medical term."""

    standard_term: str
    variant: str
    phonetic: Optional[str] = None
    accent_regions: List[AccentRegion] = field(default_factory=list)
    specialty: Optional[str] = None  # Medical specialty
    frequency: float = 1.0  # Usage frequency

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "standard_term": self.standard_term,
            "variant": self.variant,
            "phonetic": self.phonetic,
            "accent_regions": [r.value for r in self.accent_regions],
            "specialty": self.specialty,
            "frequency": self.frequency,
        }


class MedicalPronunciationDatabase:
    """
    Database of medical term pronunciations across different accents.

    This class maintains a comprehensive collection of medical terminology
    pronunciation variants to improve recognition accuracy.
    """

    def __init__(self) -> None:
        """Initialize medical pronunciation database."""
        self.terms: Dict[str, List[MedicalTermVariant]] = {}
        self._initialize_common_terms()

    def _initialize_common_terms(self) -> None:
        """Initialize with common medical term variations."""
        # Common medical terms with accent variations

        # Diabetes variations
        self.add_variant(
            MedicalTermVariant(
                standard_term="diabetes",
                variant="dah-uh-bee-tees",
                phonetic="dɑːəbiːtiːz",
                accent_regions=[AccentRegion.US_SOUTHERN],
                frequency=0.8,
            )
        )
        self.add_variant(
            MedicalTermVariant(
                standard_term="diabetes",
                variant="die-uh-bee-teez",
                phonetic="daɪəbiːtiːz",
                accent_regions=[AccentRegion.UK_RP],
                frequency=0.9,
            )
        )

        # Laboratory variations
        self.add_variant(
            MedicalTermVariant(
                standard_term="laboratory",
                variant="lab-ruh-tor-ee",
                phonetic="læbrətɔri",
                accent_regions=[AccentRegion.US_GENERAL],
                frequency=0.9,
            )
        )
        self.add_variant(
            MedicalTermVariant(
                standard_term="laboratory",
                variant="lab-or-a-tree",
                phonetic="ləbɒrətri",
                accent_regions=[AccentRegion.UK_RP],
                frequency=0.9,
            )
        )

        # Medicine variations
        self.add_variant(
            MedicalTermVariant(
                standard_term="medicine",
                variant="med-sin",
                phonetic="medsɪn",
                accent_regions=[AccentRegion.UK_RP, AccentRegion.UK_COCKNEY],
                frequency=0.7,
            )
        )
        self.add_variant(
            MedicalTermVariant(
                standard_term="medicine",
                variant="med-i-sin",
                phonetic="medɪsɪn",
                accent_regions=[AccentRegion.US_GENERAL],
                frequency=0.9,
            )
        )

        # Vitamin variations
        self.add_variant(
            MedicalTermVariant(
                standard_term="vitamin",
                variant="vahy-tuh-min",
                phonetic="vaɪtəmɪn",
                accent_regions=[AccentRegion.US_GENERAL],
                frequency=0.9,
            )
        )
        self.add_variant(
            MedicalTermVariant(
                standard_term="vitamin",
                variant="vit-a-min",
                phonetic="vɪtəmɪn",
                accent_regions=[AccentRegion.UK_RP],
                frequency=0.9,
            )
        )

        # Hospital variations (with accent-specific pronunciations)
        self.add_variant(
            MedicalTermVariant(
                standard_term="hospital",
                variant="hos-pi-tal",
                phonetic="hɒspɪtəl",
                accent_regions=[AccentRegion.INDIAN],
                frequency=0.8,
            )
        )

        # Prescription variations
        self.add_variant(
            MedicalTermVariant(
                standard_term="prescription",
                variant="preh-scrip-shun",
                phonetic="preskrɪpʃən",
                accent_regions=[AccentRegion.SPANISH_ACCENT],
                frequency=0.7,
            )
        )

        # Anesthesia variations
        self.add_variant(
            MedicalTermVariant(
                standard_term="anesthesia",
                variant="an-es-thee-zhuh",
                phonetic="ænəsθiːʒə",
                accent_regions=[AccentRegion.US_GENERAL],
                frequency=0.9,
            )
        )
        self.add_variant(
            MedicalTermVariant(
                standard_term="anesthesia",
                variant="an-es-thee-see-uh",
                phonetic="ænəsθiːsiə",
                accent_regions=[AccentRegion.UK_RP],
                frequency=0.9,
            )
        )

    def add_variant(self, variant: MedicalTermVariant) -> None:
        """Add a pronunciation variant to the database."""
        term = variant.standard_term.lower()
        if term not in self.terms:
            self.terms[term] = []
        self.terms[term].append(variant)

    def get_variants(
        self, term: str, accent_region: Optional[AccentRegion] = None
    ) -> List[MedicalTermVariant]:
        """Get pronunciation variants for a medical term."""
        term_lower = term.lower()
        if term_lower not in self.terms:
            return []

        variants = self.terms[term_lower]

        # Filter by accent region if specified
        if accent_region:
            variants = [v for v in variants if accent_region in v.accent_regions]

        return sorted(variants, key=lambda v: v.frequency, reverse=True)

    def get_all_variants_for_accent(
        self, accent_region: AccentRegion
    ) -> Dict[str, List[str]]:
        """Get all term variants for a specific accent."""
        result = {}

        for term, variants in self.terms.items():
            accent_variants = [
                v.variant for v in variants if accent_region in v.accent_regions
            ]
            if accent_variants:
                result[term] = accent_variants

        return result

    def search_by_phonetic(self, phonetic_pattern: str) -> List[MedicalTermVariant]:
        """Search for terms by phonetic pattern."""
        results = []

        for term_variants in self.terms.values():
            for variant in term_variants:
                if variant.phonetic and phonetic_pattern in variant.phonetic:
                    results.append(variant)

        return results

    def export_to_file(self, file_path: Union[str, Path]) -> None:
        """Export database to JSON file."""
        data = {}
        for term, variants in self.terms.items():
            data[term] = [v.to_dict() for v in variants]

        file_path = Path(file_path)
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    @classmethod
    def load_from_file(
        cls, file_path: Union[str, Path]
    ) -> "MedicalPronunciationDatabase":
        """Load database from JSON file."""
        file_path = Path(file_path)
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        db = cls()
        db.terms.clear()  # Clear default terms

        for _, variant_list in data.items():
            for variant_data in variant_list:
                variant = MedicalTermVariant(
                    standard_term=variant_data["standard_term"],
                    variant=variant_data["variant"],
                    phonetic=variant_data.get("phonetic"),
                    accent_regions=[
                        AccentRegion(r) for r in variant_data.get("accent_regions", [])
                    ],
                    specialty=variant_data.get("specialty"),
                    frequency=variant_data.get("frequency", 1.0),
                )
                db.add_variant(variant)

        return db


# Helper function for quick access
def get_medical_term_variants(
    term: str, accent_region: Optional[AccentRegion] = None
) -> List[str]:
    """Get pronunciation variants for a medical term."""
    db = MedicalPronunciationDatabase()
    variants = db.get_variants(term, accent_region)
    return [v.variant for v in variants]
