"""Patient Name Structure Configuration.

This module defines name structures and handling for diverse naming conventions
across different cultures and regions, with special consideration for refugee
populations and multi-script name representations.
"""

import logging
import re
import unicodedata
from enum import Enum
from typing import Any, Dict, List, Literal, Optional, Tuple, TypedDict

# FHIR resource type for this module
__fhir_resource__ = "HumanName"

logger = logging.getLogger(__name__)


class FHIRHumanName(TypedDict, total=False):
    """FHIR HumanName resource type definition."""

    use: Literal["usual", "official", "temp", "nickname", "anonymous", "old", "maiden"]
    text: str
    family: str
    given: List[str]
    prefix: List[str]
    suffix: List[str]
    period: Dict[str, str]
    __fhir_resource__: Literal["HumanName"]


class NameUse(Enum):
    """FHIR name use codes with refugee-specific extensions."""

    USUAL = "usual"  # Known as/conventional/the one used
    OFFICIAL = "official"  # Official name as registered
    TEMP = "temp"  # Temporary name
    NICKNAME = "nickname"  # Nickname/alias
    ANONYMOUS = "anonymous"  # Anonymous identifier
    OLD = "old"  # Name no longer in use
    MAIDEN = "maiden"  # Maiden name

    # Custom extensions for refugees
    CAMP_REGISTRATION = "camp-registration"  # Name used for camp registration
    TRADITIONAL = "traditional"  # Traditional/tribal name
    RELIGIOUS = "religious"  # Religious name
    PHONETIC = "phonetic"  # Phonetic spelling


class NameScript(Enum):
    """Supported scripts for name representation."""

    LATIN = "Latn"
    ARABIC = "Arab"
    CYRILLIC = "Cyrl"
    CHINESE = "Hans"
    DEVANAGARI = "Deva"
    ETHIOPIC = "Ethi"
    BENGALI = "Beng"
    TAMIL = "Taml"
    THAI = "Thai"
    MYANMAR = "Mymr"
    KHMER = "Khmr"
    LAO = "Laoo"
    TIBETAN = "Tibt"
    GEORGIAN = "Geor"
    ARMENIAN = "Armn"
    HEBREW = "Hebr"


class NameOrder(Enum):
    """Cultural name ordering patterns."""

    WESTERN = "given-middle-family"  # John Robert Smith
    EASTERN = "family-given"  # Smith John
    SPANISH = "given-paternal-maternal"  # Juan García López
    ARABIC = "given-father-grandfather"  # Ahmed bin Mohammed bin Abdullah
    ICELANDIC = "given-patronymic"  # Björk Guðmundsdóttir
    ETHIOPIAN = "given-father-given"  # Haile Selassie (Haile of Selassie)
    INDONESIAN = "single"  # Sukarno (single name)


class NameStructure:
    """Name structure definitions for different cultural contexts."""

    STRUCTURES = {
        "western": {
            "order": NameOrder.WESTERN,
            "components": ["given", "middle", "family"],
            "example": "John Robert Smith",
            "regions": ["US", "UK", "CA", "AU", "NZ"],
            "notes": "Middle name optional",
        },
        "chinese": {
            "order": NameOrder.EASTERN,
            "components": ["family", "given"],
            "example": "王伟 (Wang Wei)",
            "regions": ["CN", "TW", "HK", "SG"],
            "notes": "Family name typically 1 character, given name 1-2 characters",
        },
        "korean": {
            "order": NameOrder.EASTERN,
            "components": ["family", "given"],
            "example": "김민수 (Kim Min-su)",
            "regions": ["KR", "KP"],
            "notes": "Family name typically 1 syllable, given name 2 syllables",
        },
        "japanese": {
            "order": NameOrder.EASTERN,
            "components": ["family", "given"],
            "example": "山田太郎 (Yamada Taro)",
            "regions": ["JP"],
            "notes": "May use kanji, hiragana, or katakana",
        },
        "arabic": {
            "order": NameOrder.ARABIC,
            "components": ["given", "father", "grandfather", "family/tribe"],
            "example": "أحمد بن محمد بن عبد الله العتيبي",
            "regions": ["SA", "AE", "EG", "JO", "SY", "IQ"],
            "notes": "May include 'bin/ibn' (son of) or 'bint' (daughter of)",
        },
        "ethiopian": {
            "order": NameOrder.ETHIOPIAN,
            "components": ["given", "father_given", "grandfather_given"],
            "example": "ሀይሌ ሥላሴ መኮንን (Haile Selassie Makonnen)",
            "regions": ["ET"],
            "notes": "No family name; father's given name used as second name",
        },
        "eritrean": {
            "order": NameOrder.ETHIOPIAN,
            "components": ["given", "father_given", "grandfather_given"],
            "example": "ሳራ ተስፋይ ገብረ (Sara Tesfay Gebre)",
            "regions": ["ER"],
            "notes": "Similar to Ethiopian naming",
        },
        "somali": {
            "order": NameOrder.ARABIC,
            "components": ["given", "father", "grandfather"],
            "example": "Maxamed Cabdullahi Xasan",
            "regions": ["SO"],
            "notes": "Patronymic system, no fixed family name",
        },
        "afghan": {
            "order": NameOrder.WESTERN,
            "components": ["given", "father/tribe", "location/profession"],
            "example": "احمد شاه درانی (Ahmad Shah Durrani)",
            "regions": ["AF"],
            "notes": "May include tribal or location-based identifiers",
        },
        "myanmar": {
            "order": NameOrder.WESTERN,
            "components": ["honorific", "given"],
            "example": "ဒေါ်အောင်ဆန်းစုကြည် (Daw Aung San Suu Kyi)",
            "regions": ["MM"],
            "notes": "No family names; honorifics indicate age/status",
        },
        "indonesian": {
            "order": NameOrder.INDONESIAN,
            "components": ["given", "father", "grandfather"],
            "example": "Sukarno or Joko Widodo",
            "regions": ["ID"],
            "notes": "May have single name or patronymic pattern",
        },
        "south_indian": {
            "order": NameOrder.WESTERN,
            "components": ["given", "father", "hometown/caste"],
            "example": "Rajesh Kumar Sharma",
            "regions": ["IN-TN", "IN-KA", "IN-AP", "IN-KL"],
            "notes": "Father's name often abbreviated as initial",
        },
        "hispanic": {
            "order": NameOrder.SPANISH,
            "components": ["given", "paternal_family", "maternal_family"],
            "example": "María García López",
            "regions": ["ES", "MX", "AR", "CO", "PE"],
            "notes": "Both parents' family names used",
        },
    }

    @classmethod
    def get_structure(cls, region_code: str) -> Optional[Dict[str, Any]]:
        """Get name structure for a given region code."""
        for structure in cls.STRUCTURES.values():
            regions = structure.get("regions", [])
            if isinstance(regions, list) and region_code in regions:
                return structure
        return None

    @classmethod
    def identify_structure(cls, name_data: Dict[str, Any]) -> Optional[str]:
        """Identify the likely name structure from name data."""
        # Logic to identify structure based on patterns
        if "bin" in str(name_data.get("text", "")) or "ibn" in str(
            name_data.get("text", "")
        ):
            return "arabic"

        # Check for single name
        if name_data.get("given") and not name_data.get("family"):
            parts = name_data["given"]
            if len(parts) == 1:
                return "indonesian"

        # Default to western if unclear
        return "western"


class NameNormalizer:
    """Utilities for normalizing names across different scripts and formats."""

    @staticmethod
    def normalize_unicode(text: str) -> str:
        """Normalize Unicode text to NFD form."""
        return unicodedata.normalize("NFD", text)

    @staticmethod
    def remove_diacritics(text: str) -> str:
        """Remove diacritical marks from text."""
        nfd = unicodedata.normalize("NFD", text)
        return "".join(char for char in nfd if unicodedata.category(char) != "Mn")

    @staticmethod
    def transliterate_arabic(text: str) -> str:
        """Perform basic Arabic to Latin transliteration."""
        # Simplified mapping - in production would use full transliteration library
        arabic_to_latin = {
            "ا": "a",
            "ب": "b",
            "ت": "t",
            "ث": "th",
            "ج": "j",
            "ح": "h",
            "خ": "kh",
            "د": "d",
            "ذ": "dh",
            "ر": "r",
            "ز": "z",
            "س": "s",
            "ش": "sh",
            "ص": "s",
            "ض": "d",
            "ط": "t",
            "ظ": "z",
            "ع": "a",
            "غ": "gh",
            "ف": "f",
            "ق": "q",
            "ك": "k",
            "ل": "l",
            "م": "m",
            "ن": "n",
            "ه": "h",
            "و": "w",
            "ي": "y",
            "أ": "a",
            "إ": "i",
            "آ": "aa",
            "ة": "h",
            "ى": "a",
            "ئ": "e",
            "ؤ": "o",
            "ء": "'",
            " ": " ",
        }

        result = []
        for char in text:
            result.append(arabic_to_latin.get(char, char))
        return "".join(result)

    @staticmethod
    def create_phonetic_representation(name: str, source_script: NameScript) -> str:
        """Create phonetic representation of a name."""
        # In production, would use proper phonetic libraries
        # This is a simplified version
        if source_script == NameScript.ARABIC:
            return NameNormalizer.transliterate_arabic(name)
        elif source_script in [NameScript.CHINESE, NameScript.CYRILLIC]:
            # Would use pinyin for Chinese, standard transliteration for Cyrillic
            return NameNormalizer.remove_diacritics(name)
        else:
            return NameNormalizer.remove_diacritics(name)


class NameValidator:
    """Validation rules for patient names."""

    # Minimum name length by component
    MIN_LENGTHS = {"given": 1, "family": 1, "prefix": 1, "suffix": 1}

    # Maximum name length by component
    MAX_LENGTHS = {"given": 50, "family": 50, "prefix": 20, "suffix": 20, "text": 200}

    # Characters that should trigger additional validation
    SUSPICIOUS_PATTERNS = [
        r"\d{3,}",  # Three or more consecutive digits
        r"[^\w\s\-\'\.\,]{3,}",  # Three or more special characters
        r"(.)\1{4,}",  # Same character repeated 5+ times
        r"^[^a-zA-Z\u0080-\uFFFF]+$",  # No letters at all
    ]

    @classmethod
    def validate_name_component(
        cls, component: str, value: str
    ) -> Tuple[bool, Optional[str]]:
        """Validate a single name component.

        Args:
            component: Type of name component (given, family, etc.)
            value: The name value to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not value:
            return False, f"{component} name cannot be empty"

        # Check length
        min_length = cls.MIN_LENGTHS.get(component, 1)
        max_length = cls.MAX_LENGTHS.get(component, 100)

        if len(value) < min_length:
            return (
                False,
                f"{component} name too short (minimum {min_length} characters)",
            )

        if len(value) > max_length:
            return False, f"{component} name too long (maximum {max_length} characters)"

        # Check for suspicious patterns
        for pattern in cls.SUSPICIOUS_PATTERNS:
            if re.search(pattern, value):
                logger.warning("Suspicious pattern in %s name: %s", component, value)
                # Don't reject, just log warning

        return True, None

    @classmethod
    def validate_name_structure(
        cls, name_data: Dict[str, Any]
    ) -> Tuple[bool, List[str]]:
        """Validate complete name structure.

        Args:
            name_data: Dictionary containing name components

        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []

        # Must have at least one name component
        has_name = any(
            [name_data.get("given"), name_data.get("family"), name_data.get("text")]
        )

        if not has_name:
            errors.append(
                "Name must have at least one component (given, family, or text)"
            )

        # Validate individual components
        for component in ["given", "family"]:
            if component in name_data:
                values = (
                    name_data[component]
                    if isinstance(name_data[component], list)
                    else [name_data[component]]
                )
                for value in values:
                    is_valid, error = cls.validate_name_component(component, value)
                    if not is_valid and error is not None:
                        errors.append(error)

        # Validate text representation
        if "text" in name_data:
            is_valid, error = cls.validate_name_component("text", name_data["text"])
            if not is_valid and error is not None:
                errors.append(error)

        return len(errors) == 0, errors


class NameBuilder:
    """Builder for constructing properly formatted patient names."""

    def __init__(self) -> None:
        """Initialize name builder."""
        self.components: Dict[str, Any] = {}
        self.use = NameUse.OFFICIAL
        self.script = NameScript.LATIN
        self.structure = "western"

    def with_given_names(self, *names: str) -> "NameBuilder":
        """Add given names."""
        self.components["given"] = list(names)
        return self

    def with_family_name(self, name: str) -> "NameBuilder":
        """Add family name."""
        self.components["family"] = name
        return self

    def with_prefix(self, prefix: str) -> "NameBuilder":
        """Add prefix (Mr., Dr., etc.)."""
        if "prefix" not in self.components:
            self.components["prefix"] = []
        self.components["prefix"].append(prefix)
        return self

    def with_suffix(self, suffix: str) -> "NameBuilder":
        """Add suffix (Jr., III, etc.)."""
        if "suffix" not in self.components:
            self.components["suffix"] = []
        self.components["suffix"].append(suffix)
        return self

    def with_use(self, use: NameUse) -> "NameBuilder":
        """Set name use."""
        self.use = use
        return self

    def with_script(self, script: NameScript) -> "NameBuilder":
        """Set script."""
        self.script = script
        return self

    def with_structure(self, structure: str) -> "NameBuilder":
        """Set cultural structure."""
        self.structure = structure
        return self

    def build(self) -> Dict[str, Any]:
        """Build the name structure.

        Returns:
            Dictionary representing the name
        """
        # Validate the name
        is_valid, errors = NameValidator.validate_name_structure(self.components)
        if not is_valid:
            raise ValueError(f"Invalid name structure: {', '.join(errors)}")

        # Build the text representation based on structure
        structure_info = NameStructure.STRUCTURES.get(
            self.structure, NameStructure.STRUCTURES["western"]
        )
        order = structure_info["order"]

        # Create text representation
        text_parts = []

        if order == NameOrder.WESTERN:
            if "prefix" in self.components:
                text_parts.extend(self.components["prefix"])
            if "given" in self.components:
                text_parts.extend(self.components["given"])
            if "family" in self.components:
                text_parts.append(self.components["family"])
            if "suffix" in self.components:
                text_parts.extend(self.components["suffix"])

        elif order == NameOrder.EASTERN:
            if "family" in self.components:
                text_parts.append(self.components["family"])
            if "given" in self.components:
                text_parts.extend(self.components["given"])

        text = " ".join(text_parts)

        # Build final structure
        result = {
            "use": self.use.value,
            "text": text,
            "script": self.script.value,
            "structure": self.structure,
        }

        # Add components
        result.update(self.components)

        return result


def format_name_for_display(
    name_data: Dict[str, Any], target_script: Optional[NameScript] = None
) -> str:
    """Format a name for display, handling different cultural contexts.

    Args:
        name_data: Name data structure
        target_script: Target script for display (optional)

    Returns:
        Formatted name string
    """
    # If text representation exists, use it
    if "text" in name_data:
        text = name_data["text"]

        # Transliterate if needed
        if target_script and "script" in name_data:
            source_script = NameScript(name_data["script"])
            if source_script != target_script and target_script == NameScript.LATIN:
                text = NameNormalizer.create_phonetic_representation(
                    text, source_script
                )

        return str(text)

    # Otherwise build from components
    builder = NameBuilder()

    if "given" in name_data:
        builder.with_given_names(*name_data["given"])
    if "family" in name_data:
        builder.with_family_name(name_data["family"])
    if "prefix" in name_data:
        for prefix in name_data["prefix"]:
            builder.with_prefix(prefix)
    if "suffix" in name_data:
        for suffix in name_data["suffix"]:
            builder.with_suffix(suffix)

    if "structure" in name_data:
        builder.with_structure(name_data["structure"])

    return str(builder.build()["text"])


def validate_fhir_human_name(name_data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate name data as FHIR HumanName type.

    Args:
        name_data: Name data to validate

    Returns:
        Validation result with 'valid', 'errors', and 'warnings' keys
    """
    errors = []
    warnings = []

    # Check use code if present
    if "use" in name_data:
        valid_uses = [
            "usual",
            "official",
            "temp",
            "nickname",
            "anonymous",
            "old",
            "maiden",
        ]
        if name_data["use"] not in valid_uses:
            errors.append(f"Invalid use code: {name_data['use']}")

    # Check that at least one name component is present
    has_name_component = any(
        ["text" in name_data, "family" in name_data, "given" in name_data]
    )

    if not has_name_component:
        errors.append("HumanName must have at least one of: text, family, or given")

    # Validate given names are in list format
    if "given" in name_data and not isinstance(name_data["given"], list):
        errors.append("Given names must be a list")

    # Validate period if present
    if "period" in name_data:
        period = name_data["period"]
        if "start" in period or "end" in period:
            # Basic date format check
            pass
        else:
            warnings.append("Period should have start and/or end date")

    return {"valid": len(errors) == 0, "errors": errors, "warnings": warnings}


def create_fhir_human_name(
    given_names: List[str],
    family_name: Optional[str] = None,
    use: str = "official",
    prefix: Optional[List[str]] = None,
    suffix: Optional[List[str]] = None,
) -> FHIRHumanName:
    """Create FHIR HumanName structure.

    Args:
        given_names: List of given names
        family_name: Family/surname
        use: Name use code
        prefix: Name prefixes (Dr., Mr., etc.)
        suffix: Name suffixes (Jr., III, etc.)

    Returns:
        FHIR HumanName structure
    """
    # Type cast to satisfy TypedDict literal requirement
    name: FHIRHumanName = {
        "use": use,  # type: ignore[typeddict-item]
        "given": given_names,
        "__fhir_resource__": "HumanName",
    }

    if family_name:
        name["family"] = family_name

    if prefix:
        name["prefix"] = prefix

    if suffix:
        name["suffix"] = suffix

    # Create text representation
    text_parts = []
    if prefix:
        text_parts.extend(prefix)
    text_parts.extend(given_names)
    if family_name:
        text_parts.append(family_name)
    if suffix:
        text_parts.extend(suffix)

    name["text"] = " ".join(text_parts)

    return name


def validate_fhir(fhir_data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate FHIR data for HumanName resources.

    Args:
        fhir_data: FHIR data to validate

    Returns:
        Validation results
    """
    errors = []
    warnings: List[str] = []

    # Check if it's a HumanName structure
    if (
        "__fhir_resource__" in fhir_data
        and fhir_data["__fhir_resource__"] != "HumanName"
    ):
        errors.append("Resource must be HumanName type")

    # Validate use field
    if "use" in fhir_data:
        valid_uses = [
            "usual",
            "official",
            "temp",
            "nickname",
            "anonymous",
            "old",
            "maiden",
        ]
        if fhir_data["use"] not in valid_uses:
            errors.append(f"Invalid use: {fhir_data['use']}")

    # Check for at least one name component
    has_name_component = any(key in fhir_data for key in ["text", "family", "given"])
    if not has_name_component:
        errors.append("At least one of 'text', 'family', or 'given' is required")

    # Validate given names are list
    if "given" in fhir_data and not isinstance(fhir_data["given"], list):
        errors.append("'given' must be a list of strings")

    # Validate prefix/suffix are lists
    for field in ["prefix", "suffix"]:
        if field in fhir_data and not isinstance(fhir_data[field], list):
            errors.append(f"'{field}' must be a list of strings")

    return {"valid": len(errors) == 0, "errors": errors, "warnings": warnings}
