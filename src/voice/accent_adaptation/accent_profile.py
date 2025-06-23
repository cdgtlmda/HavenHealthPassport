"""
Accent Profile Module.

This module defines accent profiles, regions, and characteristics
for medical voice transcription adaptation.
"""

import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union


class AccentRegion(Enum):
    """Major accent regions for English language."""

    # North American
    US_GENERAL = "us_general"
    US_SOUTHERN = "us_southern"
    US_NORTHEASTERN = "us_northeastern"
    US_MIDWESTERN = "us_midwestern"
    US_WESTERN = "us_western"
    CANADIAN = "canadian"

    # British Isles
    UK_RP = "uk_rp"  # Received Pronunciation
    UK_COCKNEY = "uk_cockney"
    UK_SCOTTISH = "uk_scottish"
    UK_IRISH = "uk_irish"
    UK_WELSH = "uk_welsh"
    UK_NORTHERN = "uk_northern"

    # Other English-speaking regions
    AUSTRALIAN = "australian"
    NEW_ZEALAND = "new_zealand"
    SOUTH_AFRICAN = "south_african"
    INDIAN = "indian"
    SINGAPOREAN = "singaporean"
    FILIPINO = "filipino"

    # Non-native English accents
    SPANISH_ACCENT = "spanish_accent"
    FRENCH_ACCENT = "french_accent"
    GERMAN_ACCENT = "german_accent"
    CHINESE_ACCENT = "chinese_accent"
    JAPANESE_ACCENT = "japanese_accent"
    KOREAN_ACCENT = "korean_accent"
    ARABIC_ACCENT = "arabic_accent"
    RUSSIAN_ACCENT = "russian_accent"


class AccentStrength(Enum):
    """Strength/intensity of accent characteristics."""

    NATIVE = "native"  # Native speaker
    MILD = "mild"  # Slight accent
    MODERATE = "moderate"  # Noticeable accent
    STRONG = "strong"  # Heavy accent
    VERY_STRONG = "very_strong"  # Very heavy accent


@dataclass
class PronunciationVariant:
    """Represents a pronunciation variant for a word or phrase."""

    standard_form: str
    variant_form: str
    phonetic_representation: Optional[str] = None
    accent_regions: List[AccentRegion] = field(default_factory=list)
    frequency: float = 1.0  # How common this variant is (0-1)
    medical_term: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "standard_form": self.standard_form,
            "variant_form": self.variant_form,
            "phonetic_representation": self.phonetic_representation,
            "accent_regions": [region.value for region in self.accent_regions],
            "frequency": self.frequency,
            "medical_term": self.medical_term,
        }


@dataclass
class AccentProfile:
    """
    Complete accent profile for a speaker or accent type.

    This profile contains phonetic characteristics, pronunciation patterns,
    and adaptation parameters for improving transcription accuracy.
    """

    accent_region: AccentRegion
    accent_strength: AccentStrength = AccentStrength.MODERATE

    # Phonetic characteristics
    vowel_shifts: Dict[str, str] = field(default_factory=dict)
    consonant_variations: Dict[str, str] = field(default_factory=dict)
    stress_patterns: List[str] = field(default_factory=list)
    intonation_patterns: List[str] = field(default_factory=list)

    # Pronunciation variants
    pronunciation_variants: List[PronunciationVariant] = field(default_factory=list)

    # Speech characteristics
    speaking_rate_adjustment: float = 1.0  # Multiplier for speaking rate
    pitch_range: Tuple[float, float] = (80.0, 250.0)  # Hz
    formant_adjustments: Dict[str, float] = field(default_factory=dict)

    # Common modifications
    r_dropping: bool = False  # e.g., British "car" → "cah"
    h_dropping: bool = False  # e.g., "'ello" instead of "hello"
    g_dropping: bool = False  # e.g., "goin'" instead of "going"
    th_substitution: Optional[str] = None  # e.g., "th" → "d" or "f"
    l_vocalization: bool = False  # e.g., "milk" → "miwk"

    # Medical term adaptations
    medical_term_variants: Dict[str, List[str]] = field(default_factory=dict)

    # Confidence adjustments
    base_confidence_adjustment: float = 0.0  # -0.2 to 0.2

    def add_pronunciation_variant(self, variant: PronunciationVariant) -> None:
        """Add a pronunciation variant to this profile."""
        # Check if variant already exists
        for existing in self.pronunciation_variants:
            if (
                existing.standard_form == variant.standard_form
                and existing.phonetic_representation == variant.phonetic_representation
            ):
                # Update existing variant
                existing.frequency = max(existing.frequency, variant.frequency)
                existing.medical_term = existing.medical_term or variant.medical_term
                return

        # Add new variant
        self.pronunciation_variants.append(variant)

    def get_variants_for_word(self, word: str) -> List[PronunciationVariant]:
        """Get all pronunciation variants for a specific word."""
        return [
            v
            for v in self.pronunciation_variants
            if v.standard_form.lower() == word.lower()
        ]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "accent_region": self.accent_region.value,
            "accent_strength": self.accent_strength.value,
            "vowel_shifts": self.vowel_shifts,
            "consonant_variations": self.consonant_variations,
            "stress_patterns": self.stress_patterns,
            "intonation_patterns": self.intonation_patterns,
            "pronunciation_variants": [
                v.to_dict() for v in self.pronunciation_variants
            ],
            "speaking_rate_adjustment": self.speaking_rate_adjustment,
            "pitch_range": self.pitch_range,
            "formant_adjustments": self.formant_adjustments,
            "r_dropping": self.r_dropping,
            "h_dropping": self.h_dropping,
            "g_dropping": self.g_dropping,
            "th_substitution": self.th_substitution,
            "l_vocalization": self.l_vocalization,
            "medical_term_variants": self.medical_term_variants,
            "base_confidence_adjustment": self.base_confidence_adjustment,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AccentProfile":
        """Create AccentProfile from dictionary."""
        profile = cls(
            accent_region=AccentRegion(data["accent_region"]),
            accent_strength=AccentStrength(data.get("accent_strength", "moderate")),
        )

        # Load all attributes
        profile.vowel_shifts = data.get("vowel_shifts", {})
        profile.consonant_variations = data.get("consonant_variations", {})
        profile.stress_patterns = data.get("stress_patterns", [])
        profile.intonation_patterns = data.get("intonation_patterns", [])
        profile.speaking_rate_adjustment = data.get("speaking_rate_adjustment", 1.0)
        profile.pitch_range = tuple(data.get("pitch_range", [80.0, 250.0]))
        profile.formant_adjustments = data.get("formant_adjustments", {})
        profile.r_dropping = data.get("r_dropping", False)
        profile.h_dropping = data.get("h_dropping", False)
        profile.g_dropping = data.get("g_dropping", False)
        profile.th_substitution = data.get("th_substitution")
        profile.l_vocalization = data.get("l_vocalization", False)
        profile.medical_term_variants = data.get("medical_term_variants", {})
        profile.base_confidence_adjustment = data.get("base_confidence_adjustment", 0.0)

        # Load pronunciation variants
        for variant_data in data.get("pronunciation_variants", []):
            variant = PronunciationVariant(
                standard_form=variant_data["standard_form"],
                variant_form=variant_data["variant_form"],
                phonetic_representation=variant_data.get("phonetic_representation"),
                accent_regions=[
                    AccentRegion(r) for r in variant_data.get("accent_regions", [])
                ],
                frequency=variant_data.get("frequency", 1.0),
                medical_term=variant_data.get("medical_term", False),
            )
            profile.pronunciation_variants.append(variant)

        return profile


class AccentDatabase:
    """
    Database of accent profiles for different regions and speakers.

    This class manages a collection of accent profiles and provides
    methods for loading, saving, and querying accent information.
    """

    def __init__(self) -> None:
        """Initialize accent database."""
        self.profiles: Dict[AccentRegion, AccentProfile] = {}
        self._initialize_default_profiles()

    def _initialize_default_profiles(self) -> None:
        """Initialize with common accent profiles."""
        # US Southern accent
        southern = AccentProfile(
            accent_region=AccentRegion.US_SOUTHERN,
            accent_strength=AccentStrength.MODERATE,
            vowel_shifts={
                "i": "ah",  # "time" → "tahm"
                "ai": "ah",  # "I" → "Ah"
            },
            g_dropping=True,
            speaking_rate_adjustment=0.9,
            medical_term_variants={
                "diabetes": ["dah-uh-bee-tees", "dah-bee-tus"],
                "medicine": ["med-sin", "med-i-sin"],
            },
        )
        self.profiles[AccentRegion.US_SOUTHERN] = southern

        # British RP accent
        british_rp = AccentProfile(
            accent_region=AccentRegion.UK_RP,
            accent_strength=AccentStrength.MODERATE,
            r_dropping=True,
            vowel_shifts={
                "a": "ah",  # "bath" → "bahth"
                "o": "ou",  # "go" → "gou"
            },
            medical_term_variants={
                "vitamin": ["vit-a-min"],  # vs American "vahy-tuh-min"
                "laboratory": ["lab-or-a-tree"],  # vs American "lab-ruh-tor-ee"
            },
        )
        self.profiles[AccentRegion.UK_RP] = british_rp

        # Indian English accent
        indian = AccentProfile(
            accent_region=AccentRegion.INDIAN,
            accent_strength=AccentStrength.MODERATE,
            consonant_variations={
                "v": "w",  # "very" → "wery"
                "w": "v",  # "what" → "vhat"
            },
            th_substitution="d",  # "this" → "dis"
            stress_patterns=["first_syllable_stress"],
            medical_term_variants={
                "hospital": ["hos-pi-tal"],  # Clear syllables
                "doctor": ["doc-tor"],
                "patient": ["pay-shent"],
            },
        )
        self.profiles[AccentRegion.INDIAN] = indian

        # Spanish-accented English
        spanish_accent = AccentProfile(
            accent_region=AccentRegion.SPANISH_ACCENT,
            accent_strength=AccentStrength.MODERATE,
            vowel_shifts={
                "i": "ee",  # "bit" → "beet"
            },
            consonant_variations={
                "z": "s",  # "zero" → "sero"
                "j": "y",  # "just" → "yust"
            },
            h_dropping=False,  # Actually adds 'h' sound sometimes
            medical_term_variants={
                "injection": ["in-yek-shun"],
                "prescription": ["preh-scrip-shun"],
            },
        )
        self.profiles[AccentRegion.SPANISH_ACCENT] = spanish_accent

    def add_profile(self, profile: AccentProfile) -> None:
        """Add or update an accent profile."""
        self.profiles[profile.accent_region] = profile

    def get_profile(self, accent_region: AccentRegion) -> Optional[AccentProfile]:
        """Get accent profile for a specific region."""
        return self.profiles.get(accent_region)

    def get_profiles_by_strength(self, strength: AccentStrength) -> List[AccentProfile]:
        """Get all profiles with a specific accent strength."""
        return [p for p in self.profiles.values() if p.accent_strength == strength]

    def search_pronunciation_variant(
        self, word: str
    ) -> Dict[AccentRegion, List[PronunciationVariant]]:
        """Search for pronunciation variants across all profiles."""
        results = {}
        for region, profile in self.profiles.items():
            variants = profile.get_variants_for_word(word)
            if variants:
                results[region] = variants
        return results

    def get_medical_term_variants(self, term: str) -> Dict[AccentRegion, List[str]]:
        """Get medical term pronunciation variants across accents."""
        results = {}
        for region, profile in self.profiles.items():
            if term.lower() in profile.medical_term_variants:
                results[region] = profile.medical_term_variants[term.lower()]
        return results

    def save_to_file(self, file_path: Union[str, Path]) -> None:
        """Save accent database to JSON file."""
        data = {
            region.value: profile.to_dict() for region, profile in self.profiles.items()
        }

        file_path = Path(file_path)
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    @classmethod
    def load_from_file(cls, file_path: Union[str, Path]) -> "AccentDatabase":
        """Load accent database from JSON file."""
        file_path = Path(file_path)
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        db = cls()
        db.profiles.clear()  # Clear default profiles

        for region_str, profile_data in data.items():
            region = AccentRegion(region_str)
            profile = AccentProfile.from_dict(profile_data)
            db.profiles[region] = profile

        return db
