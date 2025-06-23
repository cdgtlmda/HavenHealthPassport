"""Advanced NLP-based address parser for medical records."""

import re
from typing import Any, Dict, Optional

from src.utils.logging import get_logger

# Try to import NLP libraries
try:
    import spacy

    nlp = spacy.load("en_core_web_sm")
    SPACY_AVAILABLE = True
except ImportError:
    SPACY_AVAILABLE = False
    nlp = None

try:
    from transformers import pipeline

    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False

logger = get_logger(__name__)


class AddressNLPParser:
    """Advanced NLP-based address parser for medical records."""

    def __init__(self) -> None:
        """Initialize the NLP parser with pre-trained models if available."""
        self.address_patterns = self._load_address_patterns()
        self.location_indicators = self._load_location_indicators()
        self.ner_pipeline: Optional[Any] = None

        # Initialize transformer model for address parsing if available
        if TRANSFORMERS_AVAILABLE:
            try:
                self.ner_pipeline = pipeline(
                    "ner",
                    model="dbmdz/bert-large-cased-finetuned-conll03-english",
                    aggregation_strategy="simple",
                )
            except (AttributeError, KeyError, TypeError, ValueError) as e:
                logger.warning(f"Could not load NER model: {e}")
                self.ner_pipeline = None

    def _load_address_patterns(self) -> Dict[str, Any]:
        """Load common address patterns for different regions."""
        return {
            "street_types": [
                "street",
                "st",
                "road",
                "rd",
                "avenue",
                "ave",
                "boulevard",
                "blvd",
                "lane",
                "ln",
                "drive",
                "dr",
                "court",
                "ct",
                "place",
                "pl",
                "circle",
                "cir",
                "highway",
                "hwy",
                "parkway",
                "pkwy",
                "alley",
                "way",
                "path",
                "terrace",
                "square",
                "sq",
                "plaza",
            ],
            "unit_types": [
                "apartment",
                "apt",
                "suite",
                "ste",
                "unit",
                "room",
                "rm",
                "floor",
                "fl",
                "building",
                "bldg",
                "house",
                "flat",
            ],
            "direction_abbr": {
                "north": ["n", "north", "northern"],
                "south": ["s", "south", "southern"],
                "east": ["e", "east", "eastern"],
                "west": ["w", "west", "western"],
                "northeast": ["ne", "northeast", "northeastern"],
                "northwest": ["nw", "northwest", "northwestern"],
                "southeast": ["se", "southeast", "southeastern"],
                "southwest": ["sw", "southwest", "southwestern"],
            },
            "ordinal_indicators": [
                "1st",
                "2nd",
                "3rd",
                "4th",
                "5th",
                "6th",
                "7th",
                "8th",
                "9th",
                "first",
                "second",
                "third",
                "fourth",
                "fifth",
                "sixth",
                "seventh",
            ],
        }

    def _load_location_indicators(self) -> Dict[str, Any]:
        """Load location indicators for different countries."""
        return {
            "AF": {
                "province_indicators": ["province", "ولایت", "wilayat"],
                "district_indicators": ["district", "ولسوالی", "woleswali"],
                "village_indicators": ["village", "قریه", "qarya", "ده"],
            },
            "BD": {
                "division_indicators": ["division", "বিভাগ"],
                "district_indicators": ["district", "জেলা", "zila"],
                "thana_indicators": ["thana", "থানা", "upazila", "উপজেলা"],
                "union_indicators": ["union", "ইউনিয়ন"],
            },
            "PK": {
                "province_indicators": ["province", "صوبہ", "suba"],
                "district_indicators": ["district", "ضلع", "zila"],
                "tehsil_indicators": ["tehsil", "تحصیل", "taluka"],
                "union_council_indicators": ["uc", "union council", "یونین کونسل"],
            },
            "IN": {
                "state_indicators": ["state", "राज्य", "pradesh"],
                "district_indicators": ["district", "जिला", "zilla"],
                "taluk_indicators": ["taluk", "taluka", "tehsil", "mandal"],
                "village_indicators": ["village", "गांव", "gram", "panchayat"],
            },
            "ET": {
                "region_indicators": ["region", "ክልል", "kilil"],
                "zone_indicators": ["zone", "ዞን"],
                "woreda_indicators": ["woreda", "ወረዳ", "district"],
                "kebele_indicators": ["kebele", "ቀበሌ", "neighborhood"],
            },
        }

    def parse_address_advanced(
        self, address_text: str, country_code: str, language: str = "en"
    ) -> Dict[str, str]:
        """
        Advanced address parsing using NLP techniques.

        Args:
            address_text: Raw address text
            country_code: Country code for context
            language: Language of the address

        Returns:
            Parsed address components
        """
        components = {}

        # Normalize the text
        normalized = self._normalize_address_text(address_text)

        # Try NER-based parsing first if available
        if self.ner_pipeline and language == "en":
            ner_results = self._parse_with_ner(normalized)
            components.update(ner_results)

        # Apply country-specific parsing rules
        country_results = self._apply_country_specific_parsing(
            normalized, country_code, components
        )
        components.update(country_results)

        # Extract postal code
        postal_code = self._extract_postal_code(normalized, country_code)
        if postal_code:
            components["postal_code"] = postal_code
            normalized = normalized.replace(postal_code, "").strip()

        # Extract unit/apartment information
        unit_info = self._extract_unit_info(normalized)
        if unit_info:
            components["unit"] = unit_info
            normalized = normalized.replace(unit_info, "").strip()

        # Parse remaining components using pattern matching
        pattern_results = self._parse_with_patterns(normalized, country_code)

        # Merge results, preferring more specific matches
        for key, value in pattern_results.items():
            if key not in components or len(value) > len(components.get(key, "")):
                components[key] = value

        # Validate and clean results
        return self._validate_and_clean_components(components, country_code)

    def _normalize_address_text(self, text: str) -> str:
        """Normalize address text for parsing."""
        # Convert to lowercase for matching
        normalized = text.lower()

        # Standardize punctuation
        normalized = re.sub(r"\s+", " ", normalized)  # Multiple spaces to single
        normalized = re.sub(r"[,\s]+,", ",", normalized)  # Clean up commas
        normalized = re.sub(r"\.$", "", normalized)  # Remove trailing period

        # Expand common abbreviations
        abbreviations = {
            r"\bst\b": "street",
            r"\brd\b": "road",
            r"\bave\b": "avenue",
            r"\bapt\b": "apartment",
            r"\bfl\b": "floor",
            r"\bbldg\b": "building",
            r"\bn\b": "north",
            r"\bs\b": "south",
            r"\be\b": "east",
            r"\bw\b": "west",
        }

        for abbr, full in abbreviations.items():
            normalized = re.sub(abbr, full, normalized)

        return normalized.strip()

    def _parse_with_ner(self, text: str) -> Dict[str, str]:
        """Parse address using Named Entity Recognition."""
        components: Dict[str, str] = {}

        try:
            # Get NER predictions
            if self.ner_pipeline is None:
                return components
            entities = self.ner_pipeline(text)

            # Group entities by type
            locations = []
            organizations = []

            for entity in entities:
                if entity["entity_group"] == "LOC":
                    locations.append(entity["word"])
                elif entity["entity_group"] == "ORG":
                    organizations.append(entity["word"])

            # Heuristically assign locations to address components
            if locations:
                # Last location is often the city
                components["city"] = locations[-1]

                # If multiple locations, second-to-last might be state/region
                if len(locations) > 1:
                    components["state"] = locations[-2]

                # First locations might be street names
                if len(locations) > 2:
                    components["street"] = " ".join(locations[:-2])

            # Organizations might be building names
            if organizations:
                components["building"] = " ".join(organizations)

        except (RuntimeError, TypeError, ValueError) as e:
            logger.debug(f"NER parsing failed: {e}")

        return components

    def _apply_country_specific_parsing(
        self, text: str, country_code: str, existing_components: Dict[str, str]
    ) -> Dict[str, str]:
        """Apply country-specific parsing rules."""
        components = existing_components.copy()

        if country_code in self.location_indicators:
            indicators = self.location_indicators[country_code]

            # Look for country-specific administrative divisions
            for division_type, keywords in indicators.items():
                for keyword in keywords:
                    pattern = rf"{keyword}\s+([^,\n]+)"
                    match = re.search(pattern, text, re.IGNORECASE)
                    if match:
                        # Extract the division name
                        division_name = match.group(1).strip()

                        # Map to standard field names
                        if "province" in division_type or "state" in division_type:
                            components["state"] = division_name
                        elif "district" in division_type:
                            components["district"] = division_name
                        elif "city" in division_type or "thana" in division_type:
                            components["city"] = division_name
                        elif "village" in division_type or "kebele" in division_type:
                            components["locality"] = division_name
                        elif "woreda" in division_type:
                            components["area"] = division_name

        return components

    def _extract_postal_code(self, text: str, country_code: str) -> Optional[str]:
        """Extract postal code based on country-specific patterns."""
        postal_patterns = {
            "US": r"\b\d{5}(-\d{4})?\b",
            "CA": r"\b[A-Z]\d[A-Z]\s?\d[A-Z]\d\b",
            "GB": r"\b[A-Z]{1,2}\d[A-Z\d]?\s?\d[A-Z]{2}\b",
            "IN": r"\b\d{6}\b",
            "PK": r"\b\d{5}\b",
            "BD": r"\b\d{4}\b",
            "AF": r"\b\d{4,5}\b",
            "SA": r"\b\d{5}\b",
            "ET": r"\b\d{4}\b",
            "KE": r"\b\d{5}\b",
            "IR": r"\b\d{10}\b",
            "IQ": r"\b\d{5}\b",
            "SY": r"\b\d{5}\b",
            "FR": r"\b\d{5}\b",
            "DE": r"\b\d{5}\b",
            "JP": r"\b\d{3}-?\d{4}\b",
            "CN": r"\b\d{6}\b",
            "AU": r"\b\d{4}\b",
            "BR": r"\b\d{5}-?\d{3}\b",
            "MX": r"\b\d{5}\b",
            "RU": r"\b\d{6}\b",
            "ZA": r"\b\d{4}\b",
            "NL": r"\b\d{4}\s?[A-Z]{2}\b",
            "BE": r"\b\d{4}\b",
            "ES": r"\b\d{5}\b",
            "IT": r"\b\d{5}\b",
        }

        pattern = postal_patterns.get(country_code)
        if pattern:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(0).upper()

        return None

    def _extract_unit_info(self, text: str) -> Optional[str]:
        """Extract unit/apartment information."""
        # Look for unit indicators
        unit_patterns = [
            r"(?:apartment|apt|unit|suite|ste|room|rm|flat)\s*#?\s*(\w+)",
            r"#\s*(\w+)",
            r"(\d+)(?:st|nd|rd|th)\s+(?:floor|fl)",
            r"(?:floor|fl)\s+(\d+)",
            r"(?:building|bldg)\s+(\w+)",
        ]

        for pattern in unit_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(0)

        return None

    def _parse_with_patterns(self, text: str, country_code: str) -> Dict[str, str]:
        """Parse address using pattern matching and heuristics."""
        components: Dict[str, str] = {}
        parts = [p.strip() for p in re.split(r"[,\n]+", text) if p.strip()]

        if not parts:
            return components

        # Check for street patterns in the first parts
        street_found = False
        for i, part in enumerate(parts):
            # Check if this part contains a street indicator
            for street_type in self.address_patterns["street_types"]:
                if re.search(rf"\b{street_type}\b", part, re.IGNORECASE):
                    components["street"] = part
                    street_found = True
                    parts.pop(i)
                    break
            if street_found:
                break

        # If no street found, assume first part might be street/building
        if not street_found and parts:
            # Check if first part has numbers (likely a street address)
            if re.search(r"\d+", parts[0]):
                components["street"] = parts.pop(0)

        # Process remaining parts based on country format
        if country_code in ["US", "CA", "GB", "AU"]:  # Western format
            # Last part is often country (if multiple parts remain)
            if len(parts) > 2:
                components["country"] = parts.pop()

            # Second to last is often state/province with postal code
            if parts and re.search(r"\d", parts[-1]):
                # Contains numbers, might include postal code
                state_postal = parts.pop()
                # Try to separate state and postal code
                postal_match = self._extract_postal_code(state_postal, country_code)
                if postal_match:
                    components["postal_code"] = postal_match
                    state_part = state_postal.replace(postal_match, "").strip()
                    if state_part:
                        components["state"] = state_part
                else:
                    components["state"] = state_postal
            elif parts:
                components["state"] = parts.pop()

            # What remains is likely the city
            if parts:
                components["city"] = parts.pop()

        elif country_code in ["IN", "PK", "BD", "AF"]:  # South Asian format
            # These often have area/locality information
            if len(parts) >= 3:
                components["area"] = parts.pop(0)
                components["city"] = parts.pop(0)
                if parts:
                    components["state"] = parts.pop(0)
            elif len(parts) == 2:
                components["city"] = parts.pop(0)
                components["state"] = parts.pop(0)
            elif parts:
                components["city"] = parts.pop(0)

        elif country_code in ["SA", "AE", "EG", "IQ", "SY"]:  # Middle Eastern format
            # Often includes district information
            if len(parts) >= 2:
                components["district"] = parts.pop(0)
                components["city"] = parts.pop(0)
                if parts:
                    components["state"] = parts.pop(0)
            elif parts:
                components["city"] = parts.pop(0)

        else:  # Default parsing
            # Assume: city, state/region, country
            if parts:
                components["city"] = parts.pop(0)
            if parts:
                components["state"] = parts.pop(0)
            if parts:
                components["country"] = parts.pop(0)

        return components

    def _validate_and_clean_components(
        self, components: Dict[str, str], _country_code: str
    ) -> Dict[str, str]:
        """Validate and clean parsed components."""
        cleaned = {}

        for key, value in components.items():
            # Clean whitespace and punctuation
            value = value.strip(" ,.-")

            # Skip empty values
            if not value:
                continue

            # Capitalize appropriately
            if key in ["street", "city", "state", "district", "area"]:
                # Title case for most fields
                value = " ".join(word.capitalize() for word in value.split())
            elif key == "postal_code":
                # Uppercase for postal codes
                value = value.upper()

            # Validate postal code format
            if key == "postal_code":
                # Use instance method directly if validation is needed
                # Skip validation for now to avoid circular dependency
                pass

            cleaned[key] = value

        return cleaned
