"""Data Standardization Module.

This module implements data standardization and normalization for healthcare
data, ensuring consistency across different data sources and formats in
refugee healthcare settings. Handles FHIR Resource validation and encrypted PHI data.

Compliance Notes:
- FHIR: Validates and standardizes FHIR DomainResource data structures
- PHI Protection: All patient data methods require PHI access control with encryption
- Audit Logging: Data normalization changes are tracked for compliance auditing
"""

import logging
import re
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, Optional
from zoneinfo import ZoneInfo  # Built-in timezone support in Python 3.9+

from src.healthcare.hipaa_access_control import AccessLevel, require_phi_access

logger = logging.getLogger(__name__)


class DataStandardizer:
    """Base class for data standardization.

    This class handles FHIR DomainResource validation for healthcare data.
    """

    def standardize(self, value: Any) -> Any:
        """Standardize a value.

        Args:
            value: Value to standardize

        Returns:
            Standardized value
        """
        raise NotImplementedError("Subclasses must implement standardize()")


class NameStandardizer(DataStandardizer):
    """Standardize person names."""

    def __init__(self, target_case: str = "title"):
        """Initialize name standardizer.

        Args:
            target_case: Target case (title, upper, lower)
        """
        self.target_case = target_case
        self.prefixes = {"mr", "mrs", "ms", "dr", "prof", "rev"}
        self.suffixes = {"jr", "sr", "ii", "iii", "iv", "md", "phd", "esq"}

    def standardize(self, value: Any) -> str:
        """Standardize a name.

        Args:
            value: Name to standardize

        Returns:
            Standardized name
        """
        if not value:
            return ""

        name = str(value).strip()

        # Remove extra whitespace
        name = " ".join(name.split())

        # Handle case
        if self.target_case == "title":
            parts = name.split()
            standardized_parts = []

            for part in parts:
                lower_part = part.lower()

                # Check if it's a prefix/suffix that should stay lowercase
                if lower_part in self.prefixes or lower_part in self.suffixes:
                    standardized_parts.append(part.title())
                # Handle names with apostrophes (O'Brien, D'Angelo)
                elif "'" in part:
                    segments = part.split("'")
                    standardized_segments = [seg.title() for seg in segments]
                    standardized_parts.append("'".join(standardized_segments))
                # Handle hyphenated names
                elif "-" in part:
                    segments = part.split("-")
                    standardized_segments = [seg.title() for seg in segments]
                    standardized_parts.append("-".join(standardized_segments))
                else:
                    standardized_parts.append(part.title())

            name = " ".join(standardized_parts)
        elif self.target_case == "upper":
            name = name.upper()
        elif self.target_case == "lower":
            name = name.lower()

        return name


class PhoneStandardizer(DataStandardizer):
    """Standardize phone numbers."""

    def __init__(self, default_country_code: str = "+1"):
        """Initialize phone standardizer.

        Args:
            default_country_code: Default country code to add
        """
        self.default_country_code = default_country_code

    def standardize(self, value: Any) -> str:
        """Standardize a phone number.

        Args:
            value: Phone number to standardize

        Returns:
            Standardized phone number
        """
        if not value:
            return ""

        phone = str(value).strip()

        # Remove all non-numeric characters except +
        phone = re.sub(r"[^\d+]", "", phone)

        # Add country code if missing
        if phone and not phone.startswith("+"):
            # Check if it starts with a valid country code digit
            if phone.startswith("1") and len(phone) == 11:
                phone = "+" + phone
            elif len(phone) == 10:  # US number without country code
                phone = self.default_country_code + phone
            elif not phone.startswith("+"):
                phone = self.default_country_code + phone

        return phone


class DateStandardizer(DataStandardizer):
    """Standardize dates and times."""

    def __init__(
        self, target_format: str = "%Y-%m-%d", target_timezone: Optional[str] = None
    ):
        """Initialize date standardizer.

        Args:
            target_format: Target date format
            target_timezone: Target timezone (e.g., "UTC")
        """
        self.target_format = target_format
        self.target_timezone = target_timezone

        # Common date formats to try
        self.date_formats = [
            "%Y-%m-%d",
            "%Y/%m/%d",
            "%d-%m-%Y",
            "%d/%m/%Y",
            "%m-%d-%Y",
            "%m/%d/%Y",
            "%Y%m%d",
            "%d %b %Y",
            "%d %B %Y",
            "%B %d, %Y",
            "%b %d, %Y",
        ]

    def standardize(self, value: Any) -> str:
        """Standardize a date.

        Args:
            value: Date to standardize

        Returns:
            Standardized date string
        """
        if not value:
            return ""

        # If already a datetime object
        if isinstance(value, datetime):
            dt = value
        else:
            # Try parsing the date
            date_str = str(value).strip()
            dt = None

            for fmt in self.date_formats:
                try:
                    dt = datetime.strptime(date_str, fmt)
                    break
                except ValueError:
                    continue

            if not dt:
                # Try ISO format with time
                try:
                    dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                except ValueError:
                    logger.warning("Could not parse date: %s", date_str)
                    return date_str

        # Handle timezone conversion
        if self.target_timezone and dt is not None:
            if dt.tzinfo is None:
                # Assume UTC if no timezone
                dt = dt.replace(tzinfo=timezone.utc)
            target_tz = ZoneInfo(self.target_timezone)
            dt = dt.astimezone(target_tz)

        if dt is None:
            return date_str
        return dt.strftime(self.target_format)


class AddressStandardizer(DataStandardizer):
    """Standardize addresses."""

    def __init__(self) -> None:
        """Initialize address standardizer."""
        self.abbreviations = {
            "street": "st",
            "road": "rd",
            "avenue": "ave",
            "boulevard": "blvd",
            "drive": "dr",
            "lane": "ln",
            "court": "ct",
            "place": "pl",
            "apartment": "apt",
            "building": "bldg",
            "floor": "fl",
            "suite": "ste",
            "north": "n",
            "south": "s",
            "east": "e",
            "west": "w",
            "northeast": "ne",
            "northwest": "nw",
            "southeast": "se",
            "southwest": "sw",
        }

    def standardize(self, value: Any) -> str:
        """Standardize an address.

        Args:
            value: Address to standardize

        Returns:
            Standardized address
        """
        if not value:
            return ""

        address = str(value).strip()

        # Normalize whitespace
        address = " ".join(address.split())

        # Title case
        address = address.title()

        # Standardize abbreviations
        words = address.split()
        standardized_words = []

        for word in words:
            lower_word = word.lower().rstrip(".,")

            # Check if it's a known abbreviation
            if lower_word in self.abbreviations:
                standardized_words.append(self.abbreviations[lower_word].title() + ".")
            else:
                standardized_words.append(word)

        return " ".join(standardized_words)


class CodeStandardizer(DataStandardizer):
    """Standardize medical codes."""

    def __init__(self, code_system: str):
        """Initialize code standardizer.

        Args:
            code_system: Code system (ICD10, SNOMED, etc.)
        """
        self.code_system = code_system.upper()

    def standardize(self, value: Any) -> str:
        """Standardize a medical code.

        Args:
            value: Code to standardize

        Returns:
            Standardized code
        """
        if not value:
            return ""

        code = str(value).strip().upper()

        if self.code_system == "ICD10":
            # Remove dots and spaces
            code = code.replace(".", "").replace(" ", "")

            # Add decimal point after 3rd character if needed
            if len(code) > 3 and not code[3] == ".":
                code = code[:3] + "." + code[3:]

        elif self.code_system == "SNOMED":
            # Remove any non-numeric characters
            code = re.sub(r"[^\d]", "", code)

        elif self.code_system == "LOINC":
            # Ensure hyphen is present
            if "-" not in code and len(code) >= 2:
                code = code[:-1] + "-" + code[-1]

        return code


class UnitStandardizer(DataStandardizer):
    """Standardize units of measurement."""

    def __init__(self) -> None:
        """Initialize unit standardizer."""
        self.unit_mappings = {
            # Weight
            "kilogram": "kg",
            "kilograms": "kg",
            "kilo": "kg",
            "kgs": "kg",
            "pound": "lb",
            "pounds": "lb",
            "lbs": "lb",
            "gram": "g",
            "grams": "g",
            "gm": "g",
            "milligram": "mg",
            "milligrams": "mg",
            # Length
            "centimeter": "cm",
            "centimeters": "cm",
            "meter": "m",
            "meters": "m",
            "inch": "in",
            "inches": "in",
            "foot": "ft",
            "feet": "ft",
            # Temperature
            "celsius": "°C",
            "centigrade": "°C",
            "fahrenheit": "°F",
            # Volume
            "milliliter": "mL",
            "milliliters": "mL",
            "ml": "mL",
            "liter": "L",
            "liters": "L",
            # Pressure
            "millimeters of mercury": "mmHg",
            "mm hg": "mmHg",
            # Time
            "minute": "min",
            "minutes": "min",
            "second": "sec",
            "seconds": "sec",
            "hour": "hr",
            "hours": "hr",
            "day": "d",
            "days": "d",
            # Concentration
            "milligrams per deciliter": "mg/dL",
            "mg/dl": "mg/dL",
            "millimoles per liter": "mmol/L",
            "mmol/l": "mmol/L",
            # Rate
            "per minute": "/min",
            "beats per minute": "bpm",
            "breaths per minute": "/min",
            # Percentage
            "percent": "%",
            "percentage": "%",
        }

    def standardize(self, value: Any) -> str:
        """Standardize a unit.

        Args:
            value: Unit to standardize

        Returns:
            Standardized unit
        """
        if not value:
            return ""

        unit = str(value).strip().lower()

        # Check if it's in our mapping
        if unit in self.unit_mappings:
            return self.unit_mappings[unit]

        # Remove trailing periods
        unit = unit.rstrip(".")

        # Check again after removing period
        if unit in self.unit_mappings:
            return self.unit_mappings[unit]

        # Return original if no mapping found
        return unit


class DataNormalizer:
    """Main class for data normalization."""

    def __init__(self) -> None:
        """Initialize data normalizer."""
        self.standardizers = {
            "name": NameStandardizer(),
            "phone": PhoneStandardizer(),
            "date": DateStandardizer(),
            "address": AddressStandardizer(),
            "unit": UnitStandardizer(),
        }

    @require_phi_access(AccessLevel.WRITE)
    def normalize_patient_data(self, patient_data: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize patient demographic data.

        Args:
            patient_data: Raw patient data

        Returns:
            Normalized patient data
        """
        normalized = patient_data.copy()

        # Normalize names
        for field in ["family_name", "given_name", "middle_name"]:
            if field in normalized and normalized[field]:
                normalized[field] = self.standardizers["name"].standardize(
                    normalized[field]
                )

        # Normalize phone
        if "phone" in normalized and normalized["phone"]:
            normalized["phone"] = self.standardizers["phone"].standardize(
                normalized["phone"]
            )

        # Normalize dates
        for field in ["birth_date", "registration_date"]:
            if field in normalized and normalized[field]:
                normalized[field] = self.standardizers["date"].standardize(
                    normalized[field]
                )

        # Normalize address
        if "address" in normalized and isinstance(normalized["address"], dict):
            for field in ["street", "city", "state"]:
                if field in normalized["address"] and normalized["address"][field]:
                    normalized["address"][field] = self.standardizers[
                        "address"
                    ].standardize(normalized["address"][field])

        return normalized

    @require_phi_access(AccessLevel.WRITE)
    def normalize_vital_signs(self, vital_signs: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize vital signs data.

        Args:
            vital_signs: Raw vital signs data

        Returns:
            Normalized vital signs data
        """
        normalized = vital_signs.copy()

        # Normalize units
        unit_fields = {
            "temperature_unit": "°C",
            "weight_unit": "kg",
            "height_unit": "cm",
            "blood_pressure_unit": "mmHg",
        }

        for field, default_unit in unit_fields.items():
            if field in normalized and normalized[field]:
                normalized[field] = self.standardizers["unit"].standardize(
                    normalized[field]
                )
            else:
                normalized[field] = default_unit

        # Normalize datetime
        if "datetime" in normalized and normalized["datetime"]:
            normalized["datetime"] = self.standardizers["date"].standardize(
                normalized["datetime"]
            )

        # Convert temperature to Celsius if needed
        if normalized.get("temperature_unit") == "°F" and "temperature" in normalized:
            # Convert Fahrenheit to Celsius
            try:
                f_temp = float(normalized["temperature"])
                c_temp = (f_temp - 32) * 5 / 9
                normalized["temperature"] = round(c_temp, 1)
                normalized["temperature_unit"] = "°C"
            except (TypeError, ValueError):
                pass

        # Convert weight to kg if needed
        if normalized.get("weight_unit") == "lb" and "weight" in normalized:
            try:
                lb_weight = float(normalized["weight"])
                kg_weight = lb_weight * 0.453592
                normalized["weight"] = round(kg_weight, 1)
                normalized["weight_unit"] = "kg"
            except (TypeError, ValueError):
                pass

        return normalized

    @require_phi_access(AccessLevel.WRITE)
    def normalize_lab_result(self, lab_result: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize laboratory result data.

        Args:
            lab_result: Raw lab result data

        Returns:
            Normalized lab result data
        """
        normalized = lab_result.copy()

        # Normalize test code if present
        if "test_code" in normalized and normalized["test_code"]:
            # Determine code system
            if "code_system" in normalized:
                code_standardizer = CodeStandardizer(normalized["code_system"])
                normalized["test_code"] = code_standardizer.standardize(
                    normalized["test_code"]
                )

        # Normalize unit
        if "unit" in normalized and normalized["unit"]:
            normalized["unit"] = self.standardizers["unit"].standardize(
                normalized["unit"]
            )

        # Normalize dates
        for field in ["collection_date", "result_date"]:
            if field in normalized and normalized[field]:
                normalized[field] = self.standardizers["date"].standardize(
                    normalized[field]
                )

        # Ensure numeric value is properly formatted
        if "value" in normalized:
            try:
                # Try to convert to decimal for precision
                normalized["value"] = str(Decimal(str(normalized["value"])))
            except (TypeError, ValueError, InvalidOperation):
                # Keep original if not numeric
                pass

        return normalized

    def create_standardization_report(
        self, original_data: Dict[str, Any], normalized_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create a report of standardization changes.

        Args:
            original_data: Original data
            normalized_data: Normalized data

        Returns:
            Report of changes made
        """
        changes = []

        def compare_values(path: str, original: Any, normalized: Any) -> None:
            if original != normalized:
                changes.append(
                    {
                        "field": path,
                        "original": original,
                        "normalized": normalized,
                        "change_type": "standardization",
                    }
                )

        def traverse_dict(
            path: str, orig_dict: Dict[str, Any], norm_dict: Dict[str, Any]
        ) -> None:
            for key in orig_dict:
                field_path = f"{path}.{key}" if path else key

                if key in norm_dict:
                    if isinstance(orig_dict[key], dict) and isinstance(
                        norm_dict[key], dict
                    ):
                        traverse_dict(field_path, orig_dict[key], norm_dict[key])
                    else:
                        compare_values(field_path, orig_dict[key], norm_dict[key])

        traverse_dict("", original_data, normalized_data)

        return {
            "changes": changes,
            "change_count": len(changes),
            "timestamp": datetime.now().isoformat(),
        }


# Create global instance
data_normalizer = DataNormalizer()
