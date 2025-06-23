"""Phone number formatter for various country formats."""

import re
from typing import Any, Dict, Optional

from src.utils.logging import get_logger

from .phone_ml import PhoneNumberMLParser
from .types import CountryPhoneFormat

logger = get_logger(__name__)


class PhoneNumberFormatter:
    """Formats phone numbers for different countries with ML enhancements."""

    # Country phone formats (keeping existing data structure)
    COUNTRY_FORMATS = {
        "US": CountryPhoneFormat(
            country_code="1",
            international_prefix="+1",
            national_prefix="1",
            number_length=[10],
            area_code_length=3,
            format_pattern="(XXX) XXX-XXXX",
            mobile_prefixes=[],  # No distinction
            emergency_numbers={"police": "911", "medical": "911", "fire": "911"},
            regex_patterns=[r"^\d{10}$", r"^1\d{10}$"],
        ),
        "GB": CountryPhoneFormat(
            country_code="44",
            international_prefix="+44",
            national_prefix="0",
            number_length=[10, 11],
            area_code_length=None,  # Variable
            format_pattern="XXXX XXX XXXX",
            mobile_prefixes=["7"],
            emergency_numbers={
                "police": "999",
                "medical": "999",
                "fire": "999",
                "nhs": "111",
            },
            regex_patterns=[r"^[0-9]{10,11}$"],
        ),
        "FR": CountryPhoneFormat(
            country_code="33",
            international_prefix="+33",
            national_prefix="0",
            number_length=[9],
            area_code_length=1,
            format_pattern="X XX XX XX XX",
            mobile_prefixes=["6", "7"],
            emergency_numbers={
                "police": "17",
                "medical": "15",
                "fire": "18",
                "eu": "112",
            },
            regex_patterns=[r"^[0-9]{9}$"],
        ),
        "SA": CountryPhoneFormat(
            country_code="966",
            international_prefix="+966",
            national_prefix="0",
            number_length=[9],
            area_code_length=2,
            format_pattern="XX XXX XXXX",
            mobile_prefixes=["5"],
            emergency_numbers={
                "police": "999",
                "medical": "997",
                "fire": "998",
                "traffic": "993",
            },
            regex_patterns=[r"^[0-9]{9}$"],
        ),
        "IR": CountryPhoneFormat(
            country_code="98",
            international_prefix="+98",
            national_prefix="0",
            number_length=[10],
            area_code_length=3,
            format_pattern="XXX XXX XXXX",
            mobile_prefixes=["9"],
            emergency_numbers={"police": "110", "medical": "115", "fire": "125"},
            regex_patterns=[r"^[0-9]{10}$"],
        ),
        "AF": CountryPhoneFormat(
            country_code="93",
            international_prefix="+93",
            national_prefix="0",
            number_length=[9],
            area_code_length=2,
            format_pattern="XX XXX XXXX",
            mobile_prefixes=["7"],
            emergency_numbers={"police": "119", "medical": "102", "fire": "119"},
            regex_patterns=[r"^[0-9]{9}$"],
        ),
        "PK": CountryPhoneFormat(
            country_code="92",
            international_prefix="+92",
            national_prefix="0",
            number_length=[10],
            area_code_length=3,
            format_pattern="XXX XXX XXXX",
            mobile_prefixes=["3"],
            emergency_numbers={
                "police": "15",
                "medical": "1122",
                "fire": "16",
                "rescue": "1122",
            },
            regex_patterns=[r"^[0-9]{10}$"],
        ),
        "BD": CountryPhoneFormat(
            country_code="880",
            international_prefix="+880",
            national_prefix="0",
            number_length=[10, 11],
            area_code_length=2,
            format_pattern="XX XXXX XXXX",
            mobile_prefixes=["1"],
            emergency_numbers={
                "police": "999",
                "medical": "199",
                "fire": "199",
                "rab": "100",
            },
            regex_patterns=[r"^[0-9]{10,11}$"],
        ),
        "IN": CountryPhoneFormat(
            country_code="91",
            international_prefix="+91",
            national_prefix="0",
            number_length=[10],
            area_code_length=None,
            format_pattern="XXXXX XXXXX",
            mobile_prefixes=["6", "7", "8", "9"],
            emergency_numbers={
                "police": "100",
                "medical": "108",
                "fire": "101",
                "disaster": "108",
            },
            regex_patterns=[r"^[6-9][0-9]{9}$"],
        ),
        "KE": CountryPhoneFormat(
            country_code="254",
            international_prefix="+254",
            national_prefix="0",
            number_length=[9],
            area_code_length=2,
            format_pattern="XXX XXX XXX",
            mobile_prefixes=["7", "1"],
            emergency_numbers={"police": "999", "medical": "999", "fire": "999"},
            regex_patterns=[r"^[0-9]{9}$"],
        ),
        "ET": CountryPhoneFormat(
            country_code="251",
            international_prefix="+251",
            national_prefix="0",
            number_length=[9],
            area_code_length=2,
            format_pattern="XX XXX XXXX",
            mobile_prefixes=["9"],
            emergency_numbers={
                "police": "991",
                "medical": "907",
                "fire": "939",
                "traffic": "945",
            },
            regex_patterns=[r"^[0-9]{9}$"],
        ),
        "SY": CountryPhoneFormat(
            country_code="963",
            international_prefix="+963",
            national_prefix="0",
            number_length=[9],
            area_code_length=2,
            format_pattern="XX XXX XXXX",
            mobile_prefixes=["9"],
            emergency_numbers={"police": "112", "medical": "110", "fire": "113"},
            regex_patterns=[r"^[0-9]{9}$"],
        ),
        "IQ": CountryPhoneFormat(
            country_code="964",
            international_prefix="+964",
            national_prefix="0",
            number_length=[10],
            area_code_length=3,
            format_pattern="XXX XXX XXXX",
            mobile_prefixes=["7"],
            emergency_numbers={"police": "104", "medical": "122", "fire": "115"},
            regex_patterns=[r"^[0-9]{10}$"],
        ),
    }

    def __init__(self) -> None:
        """Initialize formatter with ML parser."""
        self.ml_parser = PhoneNumberMLParser()

    def format_phone_number(
        self, number: str, country_code: str, format_type: str = "national"
    ) -> str:
        """
        Format phone number for display with ML enhancements.

        Args:
            number: Phone number (digits only)
            country_code: ISO country code
            format_type: "national", "international", "e164"

        Returns:
            Formatted phone number
        """
        # Try ML parsing first for better accuracy
        ml_result = self.ml_parser.parse_phone_advanced(
            number, default_country=country_code
        )

        formatted = ml_result.get("formatted", {})
        if (
            ml_result["valid"]
            and isinstance(formatted, dict)
            and format_type in formatted
        ):
            return str(formatted[format_type])

        # Fall back to traditional formatting
        # Clean input
        cleaned = re.sub(r"\D", "", number)

        # Get country format
        country_format = self.COUNTRY_FORMATS.get(country_code)
        if not country_format:
            return number

        # Remove country code if present
        if cleaned.startswith(country_format.country_code):
            cleaned = cleaned[len(country_format.country_code) :]

        # Remove national prefix if present
        if country_format.national_prefix and cleaned.startswith(
            country_format.national_prefix
        ):
            cleaned = cleaned[len(country_format.national_prefix) :]

        # Validate length
        if len(cleaned) not in country_format.number_length:
            logger.warning(
                f"Invalid phone number length for {country_code}: {len(cleaned)}"
            )
            return number

        # Format based on type
        if format_type == "e164":
            return f"+{country_format.country_code}{cleaned}"

        elif format_type == "international":
            formatted = self._apply_format_pattern(
                cleaned, country_format.format_pattern
            )
            return f"{country_format.international_prefix} {formatted}"

        else:  # national
            # Add national prefix for some countries
            if country_format.national_prefix and country_code != "US":
                cleaned = country_format.national_prefix + cleaned

            return self._apply_format_pattern(cleaned, country_format.format_pattern)

    def _apply_format_pattern(self, number: str, pattern: str) -> str:
        """Apply format pattern to number."""
        result = []
        num_idx = 0

        for char in pattern:
            if char == "X" and num_idx < len(number):
                result.append(number[num_idx])
                num_idx += 1
            elif char != "X":
                result.append(char)

        # Append any remaining digits
        if num_idx < len(number):
            result.append(number[num_idx:])

        return "".join(result)

    def is_mobile_number(self, number: str, country_code: str) -> bool:
        """Check if number is a mobile number using ML detection."""
        # Try ML parser first
        ml_result = self.ml_parser.parse_phone_advanced(
            number, default_country=country_code
        )

        if ml_result["valid"] and ml_result.get("type"):
            return bool(ml_result["type"] == "mobile")

        # Fall back to traditional detection
        country_format = self.COUNTRY_FORMATS.get(country_code)
        if not country_format or not country_format.mobile_prefixes:
            return False

        # Clean and normalize
        cleaned = re.sub(r"\D", "", number)
        if cleaned.startswith(country_format.country_code):
            cleaned = cleaned[len(country_format.country_code) :]
        if country_format.national_prefix and cleaned.startswith(
            country_format.national_prefix
        ):
            cleaned = cleaned[len(country_format.national_prefix) :]

        # Check mobile prefixes
        return any(
            cleaned.startswith(prefix) for prefix in country_format.mobile_prefixes
        )

    def get_emergency_numbers(self, country_code: str) -> Dict[str, str]:
        """Get emergency numbers for a country."""
        country_format = self.COUNTRY_FORMATS.get(country_code)
        return country_format.emergency_numbers if country_format else {}

    def parse_phone_number(
        self, number: str, default_country: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Parse phone number into components using ML.

        Args:
            number: Phone number to parse
            default_country: Default country if not in number

        Returns:
            Dictionary with country_code, national_number, etc.
        """
        # Use ML parser for comprehensive parsing
        ml_result = self.ml_parser.parse_phone_advanced(
            number, default_country=default_country
        )

        if ml_result["valid"]:
            formatted_data = ml_result.get("formatted", {})
            return {
                "country_code": str(ml_result["country"]),
                "national_number": str(ml_result["number"]),
                "is_mobile": str(ml_result["type"] == "mobile"),
                "carrier": str(ml_result.get("carrier") or ""),
                "location": str(ml_result.get("location") or ""),
                "formatted_national": str(
                    formatted_data.get("national", "")
                    if isinstance(formatted_data, dict)
                    else ""
                ),
                "formatted_international": str(
                    formatted_data.get("international", "")
                    if isinstance(formatted_data, dict)
                    else ""
                ),
                "confidence": str(ml_result["confidence"]),
            }

        # Fall back to basic parsing if ML fails
        cleaned = re.sub(r"\D", "", number)

        # Try to detect country code
        country_code = None
        national_number = cleaned

        if cleaned.startswith("+"):
            cleaned = cleaned[1:]

        # Try matching country codes (longest first)
        for cc, format_info in sorted(
            self.COUNTRY_FORMATS.items(),
            key=lambda x: len(x[1].country_code),
            reverse=True,
        ):
            if cleaned.startswith(format_info.country_code):
                country_code = cc
                national_number = cleaned[len(format_info.country_code) :]
                break

        if not country_code and default_country:
            country_code = default_country

        if not country_code:
            return None

        return {
            "country_code": country_code,
            "national_number": national_number,
            "is_mobile": self.is_mobile_number(national_number, country_code),
            "formatted_national": self.format_phone_number(
                national_number, country_code, "national"
            ),
            "formatted_international": self.format_phone_number(
                national_number, country_code, "international"
            ),
            "confidence": 0.7,  # Lower confidence for basic parsing
        }
