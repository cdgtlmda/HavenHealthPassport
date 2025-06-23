"""Name Ordering and Honorifics Management.

This module handles culturally appropriate name ordering and honorific
systems for global healthcare applications.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from src.utils.logging import get_logger

logger = get_logger(__name__)


class NameOrder(str, Enum):
    """Name ordering patterns."""

    GIVEN_FAMILY = "given_family"  # John Smith (Western)
    FAMILY_GIVEN = "family_given"  # Smith John (East Asian)
    GIVEN_FATHER_FAMILY = "given_father_family"  # Ahmed bin Mohammed Al-Rashid (Arabic)
    SINGLE_NAME = "single_name"  # Mononymous cultures


class HonorificPosition(str, Enum):
    """Position of honorific relative to name."""

    PREFIX = "prefix"  # Mr. John Smith
    SUFFIX = "suffix"  # John Smith-san
    BOTH = "both"  # Dr. John Smith Jr.


@dataclass
class NameFormat:
    """Name formatting rules for a culture."""

    culture_code: str
    name_order: NameOrder
    uses_middle_name: bool
    uses_patronymic: bool
    family_name_first: bool
    capitalize_family: bool  # SMITH vs Smith
    joining_words: List[str]  # von, de, bin, etc.


@dataclass
class Honorific:
    """Honorific title information."""

    code: str
    title: Dict[str, str]  # language -> title
    position: HonorificPosition
    gender_specific: bool
    professional: bool
    formal_only: bool


class NameManager:
    """Manages name formatting and honorifics."""

    # Name formats by culture
    NAME_FORMATS = {
        "western": NameFormat(
            culture_code="western",
            name_order=NameOrder.GIVEN_FAMILY,
            uses_middle_name=True,
            uses_patronymic=False,
            family_name_first=False,
            capitalize_family=False,
            joining_words=["de", "van", "von", "della", "du", "da"],
        ),
        "chinese": NameFormat(
            culture_code="chinese",
            name_order=NameOrder.FAMILY_GIVEN,
            uses_middle_name=False,
            uses_patronymic=False,
            family_name_first=True,
            capitalize_family=False,
            joining_words=[],
        ),
        "japanese": NameFormat(
            culture_code="japanese",
            name_order=NameOrder.FAMILY_GIVEN,
            uses_middle_name=False,
            uses_patronymic=False,
            family_name_first=True,
            capitalize_family=False,
            joining_words=[],
        ),
        "korean": NameFormat(
            culture_code="korean",
            name_order=NameOrder.FAMILY_GIVEN,
            uses_middle_name=False,
            uses_patronymic=False,
            family_name_first=True,
            capitalize_family=False,
            joining_words=[],
        ),
        "arabic": NameFormat(
            culture_code="arabic",
            name_order=NameOrder.GIVEN_FATHER_FAMILY,
            uses_middle_name=False,
            uses_patronymic=True,
            family_name_first=False,
            capitalize_family=False,
            joining_words=["bin", "ibn", "bint", "al", "el"],
        ),
        "russian": NameFormat(
            culture_code="russian",
            name_order=NameOrder.GIVEN_FAMILY,
            uses_middle_name=False,
            uses_patronymic=True,
            family_name_first=False,
            capitalize_family=False,
            joining_words=[],
        ),
        "hispanic": NameFormat(
            culture_code="hispanic",
            name_order=NameOrder.GIVEN_FAMILY,
            uses_middle_name=True,
            uses_patronymic=False,
            family_name_first=False,
            capitalize_family=False,
            joining_words=["de", "del", "de la", "y"],
        ),
    }

    # Honorifics database
    HONORIFICS = {
        "mr": Honorific(
            code="mr",
            title={
                "en": "Mr.",
                "es": "Sr.",
                "fr": "M.",
                "ar": "السيد",
                "de": "Herr",
                "ja": "さん",
                "zh": "先生",
            },
            position=HonorificPosition.PREFIX,
            gender_specific=True,
            professional=False,
            formal_only=False,
        ),
        "mrs": Honorific(
            code="mrs",
            title={
                "en": "Mrs.",
                "es": "Sra.",
                "fr": "Mme",
                "ar": "السيدة",
                "de": "Frau",
                "ja": "さん",
                "zh": "女士",
            },
            position=HonorificPosition.PREFIX,
            gender_specific=True,
            professional=False,
            formal_only=False,
        ),
        "ms": Honorific(
            code="ms",
            title={
                "en": "Ms.",
                "es": "Srta.",
                "fr": "Mlle",
                "ar": "الآنسة",
                "de": "Frau",
                "ja": "さん",
                "zh": "女士",
            },
            position=HonorificPosition.PREFIX,
            gender_specific=True,
            professional=False,
            formal_only=False,
        ),
        "dr": Honorific(
            code="dr",
            title={
                "en": "Dr.",
                "es": "Dr./Dra.",
                "fr": "Dr",
                "ar": "د.",
                "de": "Dr.",
                "ja": "医師",
                "zh": "医生",
            },
            position=HonorificPosition.PREFIX,
            gender_specific=False,
            professional=True,
            formal_only=False,
        ),
        "prof": Honorific(
            code="prof",
            title={
                "en": "Prof.",
                "es": "Prof.",
                "fr": "Pr",
                "ar": "أ.د.",
                "de": "Prof.",
                "ja": "教授",
                "zh": "教授",
            },
            position=HonorificPosition.PREFIX,
            gender_specific=False,
            professional=True,
            formal_only=True,
        ),
    }

    # Language-specific name ordering
    LANGUAGE_NAME_ORDER = {
        "en": "western",
        "es": "hispanic",
        "fr": "western",
        "de": "western",
        "ar": "arabic",
        "zh": "chinese",
        "ja": "japanese",
        "ko": "korean",
        "ru": "russian",
        "hi": "western",
        "bn": "western",
        "ur": "arabic",
        "fa": "arabic",
    }

    def format_name(
        self,
        given_name: str,
        family_name: str,
        middle_name: Optional[str] = None,
        culture: Optional[str] = None,
        language: Optional[str] = None,
        formal: bool = True,
    ) -> str:
        """Format name according to cultural conventions."""
        # Determine culture from language if not specified
        if not culture and language:
            culture = self.LANGUAGE_NAME_ORDER.get(language, "western")
        elif not culture:
            culture = "western"

        format_spec = self.NAME_FORMATS.get(culture, self.NAME_FORMATS["western"])

        # Build name parts
        parts = []

        if format_spec.name_order == NameOrder.FAMILY_GIVEN:
            # East Asian style: Family Given
            parts.append(family_name)
            parts.append(given_name)

        elif format_spec.name_order == NameOrder.GIVEN_FATHER_FAMILY:
            # Arabic style: Given [bin Father] Family
            parts.append(given_name)
            if middle_name and format_spec.uses_patronymic:
                # Assume middle name is father's name
                if culture == "arabic":
                    parts.append(f"bin {middle_name}")
            parts.append(family_name)

        else:
            # Western style: Given [Middle] Family
            parts.append(given_name)
            if middle_name and format_spec.uses_middle_name:
                if formal:
                    parts.append(middle_name)
                else:
                    # Use initial only
                    parts.append(f"{middle_name[0]}.")
            parts.append(family_name)

        # Join parts
        name = " ".join(parts)

        # Apply capitalization rules
        if format_spec.capitalize_family and formal:
            # Capitalize family name (some cultures)
            name = name.replace(family_name, family_name.upper())

        return name

    def parse_full_name(
        self,
        full_name: str,
        culture: Optional[str] = None,
        language: Optional[str] = None,
    ) -> Dict[str, Optional[str]]:
        """Parse full name into components."""
        # Determine culture
        if not culture and language:
            culture = self.LANGUAGE_NAME_ORDER.get(language, "western")
        elif not culture:
            culture = "western"

        format_spec = self.NAME_FORMATS.get(culture, self.NAME_FORMATS["western"])

        # Split name
        parts = full_name.strip().split()

        result = {
            "given_name": None,
            "middle_name": None,
            "family_name": None,
            "full_name": full_name,
        }

        if not parts:
            return result

        # Parse based on culture
        if format_spec.family_name_first:
            # Family name comes first
            result["family_name"] = parts[0]
            if len(parts) > 1:
                result["given_name"] = " ".join(parts[1:])
        else:
            # Given name comes first
            result["given_name"] = parts[0]

            if len(parts) == 2:
                result["family_name"] = parts[1]
            elif len(parts) == 3:
                # Check for joining words
                if parts[1].lower() in format_spec.joining_words:
                    result["family_name"] = " ".join(parts[1:])
                else:
                    result["middle_name"] = parts[1]
                    result["family_name"] = parts[2]
            elif len(parts) > 3:
                # Complex name - take last as family, rest as given/middle
                result["family_name"] = parts[-1]
                result["middle_name"] = " ".join(parts[1:-1])

        return result

    def get_display_name(
        self,
        given_name: str,
        family_name: str,
        honorific: Optional[str] = None,
        language: str = "en",
        formal: bool = True,
        include_honorific: bool = True,
    ) -> str:
        """Get display name with appropriate formatting."""
        # Format base name
        culture = self.LANGUAGE_NAME_ORDER.get(language, "western")
        base_name = self.format_name(
            given_name, family_name, culture=culture, formal=formal
        )

        # Add honorific if requested
        if include_honorific and honorific:
            honorific_obj = self.HONORIFICS.get(honorific)
            if honorific_obj:
                title = honorific_obj.title.get(language, honorific_obj.title["en"])

                if honorific_obj.position == HonorificPosition.PREFIX:
                    return f"{title} {base_name}"
                elif honorific_obj.position == HonorificPosition.SUFFIX:
                    return f"{base_name} {title}"

        return base_name

    def get_sorting_name(
        self, given_name: str, family_name: str, culture: Optional[str] = None
    ) -> str:
        """Get name formatted for sorting (typically Family, Given)."""
        # Always use family name first for sorting
        return f"{family_name}, {given_name}"

    def get_honorific_options(
        self,
        language: str = "en",
        gender: Optional[str] = None,
        professional_only: bool = False,
    ) -> List[Dict[str, Any]]:
        """Get available honorific options."""
        options = []

        for code, honorific in self.HONORIFICS.items():
            # Filter by professional status
            if professional_only and not honorific.professional:
                continue

            # Filter by gender if specified
            if gender and honorific.gender_specific:
                if gender == "male" and code in ["mrs", "ms"]:
                    continue
                elif gender == "female" and code == "mr":
                    continue

            # Get localized title
            title = honorific.title.get(language, honorific.title["en"])

            options.append(
                {"code": code, "title": title, "formal": honorific.formal_only}
            )

        return options

    def validate_name(
        self, name: str, name_type: str = "given"  # given, family, full
    ) -> Tuple[bool, Optional[str]]:
        """Validate name format."""
        # Basic validation rules
        if not name or not name.strip():
            return False, f"{name_type.capitalize()} name is required"

        # Check length
        if len(name) < 1:
            return False, f"{name_type.capitalize()} name too short"

        if len(name) > 50:
            return False, f"{name_type.capitalize()} name too long"

        # Check for invalid characters
        invalid_chars = ["<", ">", "@", "#", "$", "%", "^", "&", "*", "=", "+"]
        for char in invalid_chars:
            if char in name:
                return False, f"Invalid character '{char}' in name"

        # Check for numbers (usually not allowed in names)
        if any(char.isdigit() for char in name):
            return False, "Names should not contain numbers"

        return True, None


# Global name manager instance
name_manager = NameManager()
