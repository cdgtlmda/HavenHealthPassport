"""ML-based phone number parser for medical records."""

import re
from typing import Any, Dict, List, Optional

from src.utils.logging import get_logger

# Try to import ML libraries
try:
    # ML imports would go here if needed
    TRANSFORMERS_AVAILABLE = False
except ImportError:
    TRANSFORMERS_AVAILABLE = False

logger = get_logger(__name__)


class PhoneNumberMLParser:
    """Machine Learning enhanced phone number parser."""

    def __init__(self) -> None:
        """Initialize ML parser with patterns and models."""
        self.country_patterns = self._load_country_patterns()
        self.carrier_patterns = self._load_carrier_patterns()

    def _load_country_patterns(self) -> Dict[str, Dict]:
        """Load comprehensive country-specific phone patterns."""
        return {
            "US": {
                "patterns": [
                    r"^\+?1?\s*\(?(\d{3})\)?[\s.-]?(\d{3})[\s.-]?(\d{4})$",
                    r"^1?\s*(\d{3})[\s.-]?(\d{3})[\s.-]?(\d{4})$",
                    r"^\(?(\d{3})\)?[\s.-]?(\d{3})[\s.-]?(\d{4})$",
                ],
                "area_codes": self._load_us_area_codes(),
                "toll_free": ["800", "888", "877", "866", "855", "844", "833"],
                "premium": ["900", "976"],
            },
            "IN": {
                "patterns": [
                    r"^\+?91?\s*([6-9]\d{9})$",
                    r"^0?([6-9]\d{9})$",
                    r"^\+?91?\s*(\d{2,4})[\s.-]?(\d{6,8})$",
                ],
                "mobile_series": {
                    "6": ["Jio"],
                    "7": ["Airtel", "Vi", "BSNL"],
                    "8": ["Airtel", "Vi", "Jio"],
                    "9": ["Airtel", "Vi", "BSNL", "Jio"],
                },
                "landline_std": self._load_india_std_codes(),
            },
            "PK": {
                "patterns": [
                    r"^\+?92?\s*([3]\d{9})$",
                    r"^0?([3]\d{9})$",
                    r"^\+?92?\s*(\d{2,3})[\s.-]?(\d{7,8})$",
                ],
                "mobile_prefixes": {
                    "300-303": "Jazz",
                    "304-309": "Jazz",
                    "320-323": "Jazz",
                    "330-337": "Telenor",
                    "340-349": "Telenor",
                    "311-316": "Zong",
                    "331-336": "Ufone",
                },
            },
            "BD": {
                "patterns": [
                    r"^\+?880?\s*([1]\d{9})$",
                    r"^0?([1]\d{9})$",
                    r"^\+?880?\s*(\d{2})[\s.-]?(\d{7,8})$",
                ],
                "mobile_prefixes": {
                    "13": "Grameenphone",
                    "17": "Grameenphone",
                    "18": "Robi",
                    "16": "Robi",
                    "19": "Banglalink",
                    "14": "Banglalink",
                    "15": "Teletalk",
                },
            },
        }

    def _load_us_area_codes(self) -> Dict[str, str]:
        """Load US area codes with state mappings."""
        return {
            "201": "NJ",
            "202": "DC",
            "203": "CT",
            "205": "AL",
            "206": "WA",
            "207": "ME",
            "208": "ID",
            "209": "CA",
            "210": "TX",
            "212": "NY",
            "213": "CA",
            "214": "TX",
            "215": "PA",
            "216": "OH",
            "217": "IL",
            "218": "MN",
            "219": "IN",
            "224": "IL",
            "225": "LA",
            "228": "MS",
            "229": "GA",
            "231": "MI",
            "234": "OH",
            "239": "FL",
            "240": "MD",
            # ... abbreviated for space
        }

    def _load_india_std_codes(self) -> Dict[str, str]:
        """Load India STD codes with city mappings."""
        return {
            "11": "Delhi",
            "22": "Mumbai",
            "33": "Kolkata",
            "44": "Chennai",
            "80": "Bangalore",
            "40": "Hyderabad",
            "79": "Ahmedabad",
            "20": "Pune",
            "135": "Lucknow",
            "141": "Jaipur",
            # ... abbreviated for space
        }

    def _load_carrier_patterns(self) -> Dict[str, List[str]]:
        """Load carrier-specific patterns for validation."""
        return {
            "emergency_patterns": [
                r"^911$",
                r"^999$",
                r"^112$",
                r"^110$",
                r"^119$",
                r"^100$",
                r"^101$",
                r"^102$",
                r"^103$",
                r"^108$",
            ],
            "short_codes": [r"^\d{3,6}$"],  # General short code pattern
        }

    def parse_phone_advanced(
        self,
        phone_text: str,
        default_country: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Advanced phone number parsing with ML and context awareness.

        Args:
            phone_text: Raw phone number text
            default_country: Default country code if not detected
            context: Additional context (e.g., address country)

        Returns:
            Detailed phone number information
        """
        result = {
            "original": phone_text,
            "valid": False,
            "country": None,
            "number": None,
            "type": None,
            "carrier": None,
            "location": None,
            "formatted": {},
            "confidence": 0.0,
        }

        # Clean the input
        cleaned = self._clean_phone_number(phone_text)
        if not cleaned:
            return result

        # Detect country
        detected_country = self._detect_country_from_number(
            cleaned, default_country or "", context or {}
        )
        if not detected_country:
            return result

        result["country"] = detected_country

        # Parse based on country patterns
        parsed = self._parse_by_country(cleaned, detected_country)
        if parsed:
            result.update(parsed)
            result["valid"] = True

            # Detect number type
            result["type"] = self._detect_number_type(
                str(result["number"]), detected_country
            )

            # Detect carrier if mobile
            if result["type"] == "mobile":
                result["carrier"] = self._detect_carrier(
                    str(result["number"]), detected_country
                )

            # Get location information
            result["location"] = self._get_location_info(
                str(result["number"]), detected_country, str(result["type"])
            )

            # Generate formatted versions
            result["formatted"] = self._generate_formats(
                str(result["number"]), detected_country
            )

            # Calculate confidence score
            result["confidence"] = self._calculate_confidence(result)

        return result

    def _clean_phone_number(self, text: str) -> str:
        """Clean and normalize phone number text."""
        # Remove common words
        text = re.sub(
            r"\b(phone|mobile|cell|tel|telephone|contact|number)\b",
            "",
            text,
            flags=re.IGNORECASE,
        )

        # Keep only digits, +, and common separators
        cleaned = re.sub(r"[^0-9+\s\-().,]", "", text)

        # Remove excessive separators
        cleaned = re.sub(r"[\s\-().,]+", " ", cleaned).strip()

        return cleaned

    def _detect_country_from_number(
        self, number: str, default_country: str, context: Dict
    ) -> Optional[str]:
        """Detect country from number format and context."""
        # Check for explicit country code
        if number.startswith("+"):
            # Try to match country codes (sorted by length descending)
            country_codes = [
                ("+880", "BD"),
                ("+964", "IQ"),
                ("+966", "SA"),
                ("+963", "SY"),
                ("+251", "ET"),
                ("+254", "KE"),
                ("+92", "PK"),
                ("+91", "IN"),
                ("+98", "IR"),
                ("+93", "AF"),
                ("+44", "GB"),
                ("+33", "FR"),
                ("+1", "US"),
            ]

            for code, country in country_codes:
                if number.startswith(code):
                    return country

        # Use context if available
        if context and "country" in context:
            return str(context["country"])

        # Check number patterns
        if re.match(r"^[6-9]\d{9}$", number):
            return "IN"  # Indian mobile pattern
        elif re.match(r"^3\d{9}$", number):
            return "PK"  # Pakistani mobile pattern
        elif re.match(r"^1\d{9}$", number):
            return "BD"  # Bangladeshi mobile pattern
        elif re.match(r"^\d{10}$", number) and number[0] in "23456789":
            return "US"  # US pattern

        return default_country

    def _parse_by_country(self, number: str, country: str) -> Optional[Dict]:
        """Parse number according to country-specific patterns."""
        if country not in self.country_patterns:
            return None

        country_info = self.country_patterns[country]

        # Remove country code if present
        if number.startswith("+"):
            for pattern in [
                "+1",
                "+44",
                "+91",
                "+92",
                "+880",
                "+251",
                "+254",
                "+93",
                "+98",
                "+963",
                "+964",
                "+966",
                "+33",
            ]:
                if number.startswith(pattern):
                    number = number[len(pattern) :].strip()
                    break

        # Try each pattern
        for pattern in country_info["patterns"]:
            match = re.match(pattern, number)
            if match:
                groups = match.groups()

                # Format the number parts
                if country == "US":
                    if len(groups) == 3:
                        return {
                            "number": "".join(groups),
                            "area_code": groups[0],
                            "exchange": groups[1],
                            "subscriber": groups[2],
                        }
                elif country in ["IN", "PK", "BD"]:
                    return {
                        "number": "".join(groups),
                        "prefix": groups[0][:3] if groups else None,
                    }
                else:
                    return {"number": "".join(groups)}

        return None

    def _detect_number_type(self, number: str, country: str) -> str:
        """Detect if number is mobile, landline, toll-free, etc."""
        if country == "US":
            area_code = number[:3]
            if area_code in self.country_patterns["US"]["toll_free"]:
                return "toll_free"
            elif area_code in self.country_patterns["US"]["premium"]:
                return "premium"
            else:
                return "fixed_or_mobile"  # US doesn't distinguish

        elif country == "IN":
            first_digit = number[0]
            if first_digit in "6789":
                return "mobile"
            else:
                return "landline"

        elif country in ["PK", "BD"]:
            if number.startswith("3") and country == "PK":
                return "mobile"
            elif number.startswith("1") and country == "BD":
                return "mobile"
            else:
                return "landline"

        return "unknown"

    def _detect_carrier(self, number: str, country: str) -> Optional[str]:
        """Detect mobile carrier from number prefix."""
        if country == "IN" and "mobile_series" in self.country_patterns["IN"]:
            first_digit = number[0]
            if first_digit in self.country_patterns["IN"]["mobile_series"]:
                carriers = self.country_patterns["IN"]["mobile_series"][first_digit]
                # In reality, would need more digits or a lookup service
                return carriers[0] if carriers else None

        elif country == "PK" and "mobile_prefixes" in self.country_patterns["PK"]:
            prefix = number[:3]
            for range_str, carrier in self.country_patterns["PK"][
                "mobile_prefixes"
            ].items():
                if "-" in range_str:
                    start, end = map(int, range_str.split("-"))
                    if start <= int(prefix) <= end:
                        return str(carrier)

        elif country == "BD" and "mobile_prefixes" in self.country_patterns["BD"]:
            prefix = number[:2]
            result = self.country_patterns["BD"]["mobile_prefixes"].get(prefix)
            return str(result) if result is not None else None

        return None

    def _get_location_info(
        self, number: str, country: str, number_type: str
    ) -> Optional[Dict]:
        """Get location information from number."""
        location = {}

        if country == "US" and number_type != "toll_free":
            area_code = number[:3]
            if area_code in self.country_patterns["US"]["area_codes"]:
                location["state"] = self.country_patterns["US"]["area_codes"][area_code]

        elif country == "IN" and number_type == "landline":
            # Extract STD code (variable length)
            std_codes = self.country_patterns["IN"]["landline_std"]
            for length in [4, 3, 2]:  # Try longest first
                potential_std = number[:length]
                if potential_std in std_codes:
                    location["city"] = std_codes[potential_std]
                    location["std_code"] = potential_std
                    break

        return location if location else None

    def _generate_formats(self, number: str, country: str) -> Dict[str, str]:
        """Generate various formatted versions of the phone number."""
        formats = {}

        # E.164 format
        country_codes = {
            "US": "1",
            "GB": "44",
            "IN": "91",
            "PK": "92",
            "BD": "880",
            "AF": "93",
            "IR": "98",
            "SA": "966",
            "SY": "963",
            "IQ": "964",
            "ET": "251",
            "KE": "254",
            "FR": "33",
        }

        if country in country_codes:
            formats["e164"] = f"+{country_codes[country]}{number}"

        # National format
        if country == "US" and len(number) == 10:
            formats["national"] = f"({number[:3]}) {number[3:6]}-{number[6:]}"
            formats["national_simple"] = f"{number[:3]}-{number[3:6]}-{number[6:]}"
        elif country == "IN" and len(number) == 10:
            formats["national"] = f"{number[:5]} {number[5:]}"
        elif country == "PK" and len(number) == 10:
            formats["national"] = f"{number[:4]}-{number[4:]}"
        elif country == "BD" and len(number) == 10:
            formats["national"] = f"{number[:5]}-{number[5:]}"
        else:
            formats["national"] = number

        # International format
        if "e164" in formats:
            if country == "US":
                formats["international"] = (
                    f"+1 ({number[:3]}) {number[3:6]}-{number[6:]}"
                )
            elif country == "IN":
                formats["international"] = f"+91 {number[:5]} {number[5:]}"
            else:
                formats["international"] = formats["e164"]

        return formats

    def _calculate_confidence(self, result: Dict) -> float:
        """Calculate confidence score for the parsed number."""
        confidence = 0.0

        # Base confidence for valid parse
        if result["valid"]:
            confidence = 0.6

            # Add confidence for known patterns
            if result["type"] != "unknown":
                confidence += 0.1

            # Add confidence for carrier detection
            if result.get("carrier"):
                confidence += 0.1

            # Add confidence for location info
            if result.get("location"):
                confidence += 0.1

            # Add confidence for proper length
            expected_lengths = {
                "US": [10],
                "IN": [10],
                "PK": [10],
                "BD": [10],
                "GB": [10, 11],
                "FR": [9],
                "SA": [9],
                "AF": [9],
            }

            if result["country"] in expected_lengths:
                if len(result["number"]) in expected_lengths[result["country"]]:
                    confidence += 0.1

        return min(confidence, 1.0)
