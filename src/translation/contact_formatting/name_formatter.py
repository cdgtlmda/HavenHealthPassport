"""Name formatter for cultural conventions."""

from typing import Dict, List, Optional, Tuple

from src.utils.logging import get_logger

logger = get_logger(__name__)


class NameFormatter:
    """Formats personal names according to cultural conventions with ML enhancements."""

    # Name order by culture
    NAME_ORDERS = {
        "western": [
            "title",
            "given",
            "middle",
            "family",
            "suffix",
        ],  # Dr. John David Smith Jr.
        "eastern": ["family", "given"],  # Smith John
        "arabic": [
            "title",
            "given",
            "father",
            "grandfather",
            "family",
            "tribal",
        ],  # Sheikh Ahmed bin Mohammed bin Abdullah Al-Rashid Al-Tamimi
        "icelandic": ["given", "patronymic"],  # Björn Jónsson
        "spanish": [
            "given",
            "middle",
            "paternal",
            "maternal",
        ],  # Juan Carlos García López
        "russian": ["given", "patronymic", "family"],  # Ivan Ivanovich Petrov
        "ethiopian": ["given", "father", "grandfather"],  # Abebe Bikila Demissie
        "indonesian": ["given"],  # Sukarno (single name)
        "thai": ["title", "given", "family"],  # Khun Somchai Jaidee
    }

    # Country to name order mapping
    COUNTRY_NAME_ORDERS = {
        "US": "western",
        "GB": "western",
        "FR": "western",
        "DE": "western",
        "CA": "western",
        "AU": "western",
        "NZ": "western",
        "IE": "western",
        "SA": "arabic",
        "AE": "arabic",
        "EG": "arabic",
        "IQ": "arabic",
        "SY": "arabic",
        "JO": "arabic",
        "LB": "arabic",
        "KW": "arabic",
        "QA": "arabic",
        "BH": "arabic",
        "OM": "arabic",
        "YE": "arabic",
        "CN": "eastern",
        "JP": "eastern",
        "KR": "eastern",
        "VN": "eastern",
        "ES": "spanish",
        "MX": "spanish",
        "AR": "spanish",
        "CO": "spanish",
        "CL": "spanish",
        "PE": "spanish",
        "VE": "spanish",
        "CU": "spanish",
        "RU": "russian",
        "UA": "russian",
        "BY": "russian",
        "KZ": "russian",
        "IS": "icelandic",
        "ET": "ethiopian",
        "ID": "indonesian",
        "TH": "thai",
        "IN": "western",
        "PK": "western",
        "BD": "western",
        "AF": "arabic",
        "IR": "arabic",
        "KE": "western",
        "NG": "western",
        "ZA": "western",
    }

    # Common name particles by language/culture
    NAME_PARTICLES = {
        "arabic": {
            "prefixes": ["al", "el", "bin", "ibn", "bint", "abu", "umm", "abd"],
            "connectors": ["bin", "ibn", "bint", "ben", "ould", "wuld"],
        },
        "dutch": {
            "prefixes": ["van", "de", "der", "van der", "van den", "te", "ter", "ten"]
        },
        "german": {"prefixes": ["von", "zu", "van", "de", "der"]},
        "french": {"prefixes": ["de", "du", "de la", "des", "le", "la"]},
        "spanish": {"prefixes": ["de", "del", "de la", "de los", "de las"]},
        "portuguese": {"prefixes": ["de", "do", "da", "dos", "das"]},
        "italian": {
            "prefixes": ["di", "de", "del", "della", "dello", "dei", "degli", "delle"]
        },
    }

    def __init__(self) -> None:
        """Initialize name formatter with cultural awareness."""
        self.honorific_patterns = self._load_honorific_patterns()
        self.name_validators = self._load_name_validators()

    def _load_honorific_patterns(self) -> Dict[str, Dict]:
        """Load patterns for detecting honorifics in different languages."""
        return {
            "en": {
                "academic": ["Dr", "Prof", "Professor"],
                "religious": [
                    "Rev",
                    "Fr",
                    "Sister",
                    "Brother",
                    "Pastor",
                    "Rabbi",
                    "Imam",
                ],
                "professional": ["Eng", "Arch", "Atty", "CPA"],
                "social": ["Mr", "Mrs", "Ms", "Miss", "Mx"],
                "noble": ["Sir", "Dame", "Lord", "Lady"],
                "military": ["Gen", "Col", "Maj", "Capt", "Lt", "Sgt"],
            },
            "ar": {
                "academic": ["د", "دكتور", "أستاذ", "بروفيسور"],
                "religious": ["شيخ", "سيد", "حاج", "إمام", "قس"],
                "professional": ["مهندس", "محامي", "طبيب"],
                "social": ["السيد", "السيدة", "الآنسة"],
                "noble": ["أمير", "أميرة", "شيخ", "شيخة"],
            },
            "es": {
                "academic": ["Dr", "Dra", "Prof", "Lic"],
                "professional": ["Ing", "Arq", "Abg"],
                "social": ["Sr", "Sra", "Srta", "Don", "Doña"],
            },
        }

    def _load_name_validators(self) -> Dict[str, List]:
        """Load validation patterns for names in different cultures."""
        return {
            "arabic": [
                r"^[a-zA-Z\s\-\']+$",  # Romanized
                r"^[\u0600-\u06FF\s]+$",  # Arabic script
            ],
            "chinese": [
                r"^[a-zA-Z\s\-]+$",  # Pinyin
                r"^[\u4e00-\u9fa5]+$",  # Chinese characters
            ],
            "cyrillic": [r"^[а-яА-ЯёЁ\s\-]+$"],  # Cyrillic
            "latin": [
                r"^[a-zA-ZàáäâèéëêìíïîòóöôùúüûñçÀÁÄÂÈÉËÊÌÍÏÎÒÓÖÔÙÚÜÛÑÇ\s\-\'\.]+$"
            ],
        }

    def format_name(
        self,
        name_parts: Dict[str, str],
        country_code: str,
        format_type: str = "full",
        formality: str = "formal",
    ) -> str:
        """
        Format personal name for medical records.

        Args:
            name_parts: Dictionary with given, family, etc.
            country_code: Country code for conventions
            format_type: "full", "short", "initials", "legal"
            formality: "formal", "informal", "medical"

        Returns:
            Formatted name
        """
        # Get name order
        name_order_type = self.COUNTRY_NAME_ORDERS.get(country_code, "western")
        name_order = self.NAME_ORDERS[name_order_type]

        # Clean and validate name parts
        cleaned_parts = self._clean_name_parts(name_parts, country_code)

        if format_type == "full":
            # Build full name
            parts: List[str] = []
            for component in name_order:
                if component in cleaned_parts and cleaned_parts[component]:
                    value = cleaned_parts[component]

                    # Handle special formatting for Arabic names
                    if name_order_type == "arabic" and component in [
                        "father",
                        "grandfather",
                    ]:
                        # Add appropriate connector
                        if parts:  # Not the first part
                            parts.append(
                                "bin"
                                if self._is_male_name(cleaned_parts.get("given", ""))
                                else "bint"
                            )

                    parts.append(value)

            return " ".join(parts)

        elif format_type == "short":
            # Usually given + family
            if formality == "informal" and "given" in cleaned_parts:
                return cleaned_parts["given"]

            parts = []
            if name_order_type == "eastern":
                if "family" in cleaned_parts:
                    parts.append(cleaned_parts["family"])
                if "given" in cleaned_parts:
                    parts.append(cleaned_parts["given"])
            else:
                if "title" in cleaned_parts and formality in ["formal", "medical"]:
                    parts.append(cleaned_parts["title"])
                if "given" in cleaned_parts:
                    parts.append(cleaned_parts["given"])
                if "family" in cleaned_parts:
                    parts.append(cleaned_parts["family"])

            return " ".join(parts)

        elif format_type == "initials":
            # Format with initials - important for medical records
            parts = []

            if name_order_type == "eastern":
                if "family" in cleaned_parts:
                    parts.append(cleaned_parts["family"])
                if "given" in cleaned_parts:
                    initials = self._get_initials(cleaned_parts["given"])
                    parts.append(initials)
            else:
                if "given" in cleaned_parts:
                    initials = self._get_initials(cleaned_parts["given"])
                    parts.append(initials)
                if "middle" in cleaned_parts:
                    initials = self._get_initials(cleaned_parts["middle"])
                    parts.append(initials)
                if "family" in cleaned_parts:
                    parts.append(cleaned_parts["family"])

            return " ".join(parts)

        elif format_type == "legal":
            # Legal format - typically FAMILY, Given Middle
            parts = []

            if "family" in cleaned_parts:
                parts.append(cleaned_parts["family"].upper())

            given_parts = []
            for field in ["given", "middle"]:
                if field in cleaned_parts:
                    given_parts.append(cleaned_parts[field])

            if given_parts:
                parts.append(", " + " ".join(given_parts))

            return "".join(parts)

        return ""

    def _clean_name_parts(
        self, name_parts: Dict[str, str], country_code: str
    ) -> Dict[str, str]:
        """Clean and validate name parts."""
        cleaned = {}

        for key, value in name_parts.items():
            if not value:
                continue

            # Trim whitespace
            value = value.strip()

            # Handle capitalization based on culture
            if country_code in ["US", "GB", "CA", "AU", "IN", "PK", "BD", "KE"]:
                # Title case for Western names
                value = self._title_case_name(value)
            elif country_code in ["CN", "JP", "KR", "VN"]:
                # Keep as-is for Eastern names
                pass
            elif country_code in ["SA", "AE", "EG", "IQ", "SY", "AF", "IR"]:
                # Handle Arabic name particles
                value = self._format_arabic_name(value)

            cleaned[key] = value

        return cleaned

    def _title_case_name(self, name: str) -> str:
        """Title case a name while preserving particles."""
        words = name.split()
        result = []

        particles = set()
        for lang_particles in self.NAME_PARTICLES.values():
            if "prefixes" in lang_particles:
                particles.update(lang_particles["prefixes"])

        for i, word in enumerate(words):
            if word.lower() in particles and i > 0:
                result.append(word.lower())
            elif "-" in word:
                # Handle hyphenated names
                parts = word.split("-")
                result.append("-".join(p.capitalize() for p in parts))
            elif "'" in word:
                # Handle names with apostrophes (O'Brien, D'Angelo)
                parts = word.split("'")
                result.append("'".join(p.capitalize() for p in parts))
            else:
                result.append(word.capitalize())

        return " ".join(result)

    def _format_arabic_name(self, name: str) -> str:
        """Format Arabic names with proper particles."""
        words = name.split()
        result = []

        arabic_particles = self.NAME_PARTICLES["arabic"]

        for word in words:
            lower_word = word.lower()

            # Check if it's a particle
            if lower_word in arabic_particles["prefixes"]:
                if lower_word in ["al", "el"]:
                    # Always capitalize Al/El
                    result.append(word.capitalize())
                else:
                    # Keep other particles lowercase
                    result.append(lower_word)
            else:
                # Capitalize regular words
                result.append(word.capitalize())

        return " ".join(result)

    def _get_initials(self, name: str) -> str:
        """Extract initials from a name."""
        words = name.split()
        initials = []

        for word in words:
            # Skip particles
            if word.lower() in ["de", "van", "von", "la", "el"]:
                continue

            if word:
                initials.append(word[0].upper() + ".")

        return "".join(initials)

    def _is_male_name(self, name: str) -> bool:
        """Heuristic to determine if an Arabic name is male."""
        # Common endings for female Arabic names
        female_endings = ["a", "ah", "aa", "ة", "اء", "ى"]

        name_lower = name.lower()
        for ending in female_endings:
            if name_lower.endswith(ending):
                return False

        return True

    def get_honorifics(
        self, country_code: str, language: str = "en"
    ) -> Dict[str, List[str]]:
        """Get honorifics for a country/language."""
        # Map country to primary language
        country_languages = {
            "US": "en",
            "GB": "en",
            "CA": "en",
            "AU": "en",
            "SA": "ar",
            "AE": "ar",
            "EG": "ar",
            "IQ": "ar",
            "ES": "es",
            "MX": "es",
            "AR": "es",
            "CO": "es",
            "FR": "fr",
            "DE": "de",
            "IT": "it",
            "PT": "pt",
            "IN": "en",
            "PK": "en",
            "BD": "en",  # Often use English honorifics
        }

        lang = country_languages.get(country_code, language)

        if lang not in self.honorific_patterns:
            lang = "en"

        # Convert to expected format
        honorifics = self.honorific_patterns[lang]

        return {
            "male": honorifics.get("social", []) + honorifics.get("academic", []),
            "female": honorifics.get("social", []) + honorifics.get("academic", []),
            "neutral": honorifics.get("academic", [])
            + honorifics.get("professional", []),
        }

    def parse_full_name(
        self, full_name: str, country_code: str, _detect_components: bool = True
    ) -> Dict[str, str]:
        """
        Parse a full name into components.

        Args:
            full_name: Complete name string
            country_code: Country for cultural context
            detect_components: Whether to use ML to detect components

        Returns:
            Dictionary of name components
        """
        components = {}
        name_order_type = self.COUNTRY_NAME_ORDERS.get(country_code, "western")

        # Remove and extract honorifics
        honorific, name_without_title = self._extract_honorific(full_name, country_code)
        if honorific:
            components["title"] = honorific

        # Split the remaining name
        parts = name_without_title.split()

        if not parts:
            return components

        # Parse based on cultural pattern
        if name_order_type == "western":
            # Assume: [Given] [Middle]* [Family]
            if len(parts) == 1:
                components["given"] = parts[0]
            elif len(parts) == 2:
                components["given"] = parts[0]
                components["family"] = parts[1]
            else:
                components["given"] = parts[0]
                components["family"] = parts[-1]
                if len(parts) > 2:
                    components["middle"] = " ".join(parts[1:-1])

        elif name_order_type == "eastern":
            # Assume: [Family] [Given]
            if len(parts) == 1:
                components["family"] = parts[0]
            elif len(parts) == 2:
                components["family"] = parts[0]
                components["given"] = parts[1]
            else:
                components["family"] = parts[0]
                components["given"] = " ".join(parts[1:])

        elif name_order_type == "arabic":
            # Complex parsing for Arabic names
            components = self._parse_arabic_name(parts)

        elif name_order_type == "spanish":
            # Assume: [Given] [Middle]? [Paternal] [Maternal]
            if len(parts) >= 3:
                components["given"] = parts[0]
                if len(parts) == 3:
                    components["paternal"] = parts[1]
                    components["maternal"] = parts[2]
                else:
                    components["paternal"] = parts[-2]
                    components["maternal"] = parts[-1]
                    if len(parts) > 3:
                        components["middle"] = " ".join(parts[1:-2])
            else:
                # Fall back to western style
                if len(parts) == 2:
                    components["given"] = parts[0]
                    components["family"] = parts[1]
                else:
                    components["given"] = parts[0]

        return components

    def _extract_honorific(
        self, full_name: str, country_code: str
    ) -> Tuple[Optional[str], str]:
        """Extract honorific from name if present."""
        lang = "en"  # Default

        # Get language for country
        country_languages = {
            "SA": "ar",
            "AE": "ar",
            "EG": "ar",
            "ES": "es",
            "MX": "es",
            "AR": "es",
            "FR": "fr",
            "DE": "de",
        }

        lang = country_languages.get(country_code, "en")

        if lang not in self.honorific_patterns:
            lang = "en"

        # Check all honorific categories
        all_honorifics = []
        for category in self.honorific_patterns[lang].values():
            all_honorifics.extend(category)

        # Sort by length (longest first) to match properly
        all_honorifics.sort(key=len, reverse=True)

        # Check if name starts with any honorific
        name_lower = full_name.lower()
        for honorific in all_honorifics:
            if name_lower.startswith(honorific.lower() + " "):
                # Found honorific
                remaining_name = full_name[len(honorific) :].strip()
                return honorific, remaining_name

        return None, full_name

    def _parse_arabic_name(self, parts: List[str]) -> Dict[str, str]:
        """Parse Arabic name components."""
        components: Dict[str, str] = {}

        if not parts:
            return components

        # First part is usually given name
        components["given"] = parts[0]

        # Look for family/tribal names (usually with Al-, El-)
        family_indices = []
        for i, part in enumerate(parts):
            if part.lower().startswith(("al-", "el-", "al", "el")):
                family_indices.append(i)

        if family_indices:
            # Last Al-/El- name is usually the family name
            family_idx = family_indices[-1]
            components["family"] = parts[family_idx]

            # Check for tribal name (another Al- after family)
            if len(family_indices) > 1:
                components["tribal"] = parts[family_indices[-2]]

            # Names between given and family are patronymic
            patronymic_parts = []
            for i in range(1, family_idx):
                if i not in family_indices[:-1] and parts[i].lower() not in [
                    "bin",
                    "ibn",
                    "bint",
                ]:
                    patronymic_parts.append(parts[i])

            if patronymic_parts:
                if len(patronymic_parts) >= 2:
                    components["father"] = patronymic_parts[0]
                    components["grandfather"] = patronymic_parts[1]
                else:
                    components["father"] = patronymic_parts[0]
        else:
            # No clear family name, use patronymic pattern
            if len(parts) >= 2:
                components["father"] = parts[1]
            if len(parts) >= 3:
                components["grandfather"] = parts[2]
            if len(parts) >= 4:
                components["family"] = parts[3]

        return components
