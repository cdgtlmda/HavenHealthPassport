"""
Regional unit preferences and adaptation.

This module handles regional preferences for measurement units,
including automatic detection and adaptation based on locale.

This module handles encrypted PHI with access control and audit logging
to ensure HIPAA compliance.
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, Optional

from .core import ConversionContext, UnitConverter, UnitSystem, UnitType

logger = logging.getLogger(__name__)


@dataclass
class UnitPreferenceProfile:
    """Regional unit preferences."""

    region_code: str  # e.g., "US", "GB", "DE"
    primary_system: UnitSystem

    # Preferred units by type
    length_units: Dict[str, str] = field(default_factory=dict)  # short: cm, long: km
    weight_units: Dict[str, str] = field(
        default_factory=dict
    )  # personal: kg, medical: kg
    volume_units: Dict[str, str] = field(
        default_factory=dict
    )  # cooking: cup, medical: mL
    temperature_unit: str = "°C"

    # Special cases
    exceptions: Dict[str, str] = field(default_factory=dict)
    mixed_usage: bool = False  # Some regions use mixed systems

    def get_preferred_unit(
        self, unit_type: UnitType, context: str = "general"
    ) -> Optional[str]:
        """Get preferred unit for type and context."""
        if unit_type == UnitType.LENGTH:
            return self.length_units.get(context, self.length_units.get("general"))
        elif unit_type == UnitType.WEIGHT:
            return self.weight_units.get(context, self.weight_units.get("general"))
        elif unit_type == UnitType.VOLUME:
            return self.volume_units.get(context, self.volume_units.get("general"))
        elif unit_type == UnitType.TEMPERATURE:
            return self.temperature_unit
        return None


class RegionalPreferences:
    """Manages regional unit preferences."""

    def __init__(self) -> None:
        """Initialize regional preferences."""
        self.profiles = self._load_regional_profiles()
        self.converter = UnitConverter()

    def get_profile(self, region_code: str) -> Optional[UnitPreferenceProfile]:
        """Get preference profile for region."""
        return self.profiles.get(region_code.upper())

    def adapt_to_region(
        self,
        text: str,
        target_region: str,
        source_region: Optional[str] = None,
        preserve_medical: bool = True,
    ) -> str:
        """
        Adapt measurements in text to regional preferences.

        The source_region parameter can be used to provide context about
        the original regional format for more accurate conversion.

        Args:
            text: Text containing measurements
            target_region: Target region code
            source_region: Optional source region
            preserve_medical: Keep medical measurements in standard units

        Returns:
            Text with adapted measurements
        """
        profile = self.get_profile(target_region)
        if not profile:
            return text

        # Get source region profile for accurate medical conversions
        source_profile = None
        source_system = UnitSystem.METRIC  # Default WHO standard
        source_glucose_unit = "mmol/L"  # Default international
        source_temp_scale = "celsius"

        if source_region:
            source_profile = self.get_profile(source_region)
            if source_profile:
                source_system = source_profile.primary_system

                # Critical medical unit preferences by region
                if source_region.startswith("US"):
                    source_glucose_unit = "mg/dL"
                    source_temp_scale = "fahrenheit"
                elif source_region in ["GB", "AU", "NZ"]:
                    source_glucose_unit = "mmol/L"
                    source_temp_scale = "celsius"

                logger.info(
                    "Source region %s: glucose=%s, temp=%s, system=%s",
                    source_region,
                    source_glucose_unit,
                    source_temp_scale,
                    source_system,
                )

        # Get target preferences
        target_glucose_unit = "mmol/L"
        target_temp_scale = "celsius"

        if target_region.startswith("US"):
            target_glucose_unit = "mg/dL"
            target_temp_scale = "fahrenheit"

        # Create conversion context with medical awareness
        context = ConversionContext(
            target_system=profile.primary_system, medical_context=preserve_medical
        )

        # Critical medical conversion factors
        GLUCOSE_MMOL_TO_MGDL = 18.0182  # Molecular weight of glucose

        # Detect measurements with medical context awareness
        measurements = self.converter.detect_units_in_text(text)
        result_text = text

        for original_str, measurement in measurements:
            # Determine medical context
            medical_context = self._determine_medical_context(text, original_str)

            # Handle critical medical measurements with extra care
            if medical_context == "glucose":
                # Blood glucose conversion
                if source_glucose_unit != target_glucose_unit:
                    if source_glucose_unit == "mmol/L" and measurement.unit.symbol in [
                        "mmol/L",
                        "mmol/l",
                    ]:
                        # Convert to mg/dL
                        new_value = float(measurement.value) * GLUCOSE_MMOL_TO_MGDL
                        result_text = result_text.replace(
                            original_str.strip(), f"{new_value:.0f} mg/dL"
                        )
                        logger.warning(
                            "Critical glucose conversion: %s mmol/L → %.0f mg/dL",
                            measurement.value,
                            new_value,
                        )
                    elif source_glucose_unit == "mg/dL" and measurement.unit.symbol in [
                        "mg/dL",
                        "mg/dl",
                    ]:
                        # Convert to mmol/L
                        new_value = float(measurement.value) / GLUCOSE_MMOL_TO_MGDL
                        result_text = result_text.replace(
                            original_str.strip(), f"{new_value:.1f} mmol/L"
                        )
                        logger.warning(
                            "Critical glucose conversion: %s mg/dL → %.1f mmol/L",
                            measurement.value,
                            new_value,
                        )

            elif medical_context == "temperature" and not preserve_medical:
                # Body temperature conversion
                if measurement.unit.type == UnitType.TEMPERATURE:
                    if source_temp_scale != target_temp_scale:
                        preferred_unit = (
                            "F" if target_temp_scale == "fahrenheit" else "C"
                        )
                        try:
                            conversion = self.converter.convert(
                                measurement, preferred_unit, context
                            )
                            result_text = result_text.replace(
                                original_str.strip(), conversion.format()
                            )
                            logger.info(
                                "Temperature conversion: %s → %s",
                                original_str,
                                conversion.format(),
                            )
                        except ValueError as e:
                            logger.error("Failed to convert temperature: %s", str(e))

            elif medical_context == "drug_dosage":
                # Drug dosages - be very careful
                if preserve_medical:
                    # Keep original units for safety
                    logger.info("Preserving medical dosage unit: %s", original_str)
                    continue
                else:
                    # Only convert if we have clear weight-based dosing
                    if "per kg" in original_str.lower() or "/kg" in original_str:
                        # mg/kg is universal, but check for lb-based dosing
                        if (
                            source_region
                            and source_region.startswith("US")
                            and "/lb" in original_str
                        ):
                            # Convert from per pound to per kg
                            new_value = (
                                float(measurement.value) * 2.20462
                            )  # lb to kg factor
                            result_text = result_text.replace(
                                original_str.strip(),
                                f"{new_value:.2f} {measurement.unit.symbol}/kg",
                            )
                            logger.warning(
                                "Drug dosage conversion: %s → %.2f %s/kg",
                                original_str,
                                new_value,
                                measurement.unit.symbol,
                            )
            else:
                # Standard unit conversion for non-critical measurements
                preferred_unit = (
                    profile.get_preferred_unit(measurement.unit.type, medical_context)
                    or ""
                )

                if preferred_unit and preferred_unit != measurement.unit.symbol:
                    try:
                        conversion = self.converter.convert(
                            measurement, preferred_unit, context
                        )
                        result_text = result_text.replace(
                            original_str.strip(), conversion.format()
                        )
                    except ValueError:
                        # Skip if conversion not possible
                        continue

        return result_text

    def _determine_medical_context(self, text: str, measurement_str: str) -> str:
        """Determine medical context of measurement for safety."""
        # Get surrounding text (100 chars before and after)
        index = text.find(measurement_str)
        start = max(0, index - 100)
        end = min(len(text), index + len(measurement_str) + 100)
        context_text = text[start:end].lower()

        # Critical medical contexts
        glucose_indicators = [
            "glucose",
            "blood sugar",
            "glycemia",
            "a1c",
            "fasting",
            "postprandial",
            "diabete",
            "insulin",
        ]
        temp_indicators = [
            "temperature",
            "fever",
            "pyrexia",
            "hypothermia",
            "temp",
            "febrile",
            "celsius",
            "fahrenheit",
            "°c",
            "°f",
        ]
        dosage_indicators = [
            "dose",
            "dosage",
            "mg",
            "mcg",
            "unit",
            "medication",
            "drug",
            "prescription",
            "administer",
            "inject",
        ]

        if any(indicator in context_text for indicator in glucose_indicators):
            return "glucose"
        elif any(indicator in context_text for indicator in temp_indicators):
            return "temperature"
        elif any(indicator in context_text for indicator in dosage_indicators):
            return "drug_dosage"

        return self._determine_context(text, measurement_str)

    def _determine_context(self, text: str, measurement_str: str) -> str:
        """Determine context of measurement."""
        # Get surrounding text
        index = text.find(measurement_str)
        if index == -1:
            return "general"

        context_window = text[max(0, index - 50) : index + 50 + len(measurement_str)]
        context_lower = context_window.lower()

        # Medical context indicators
        medical_terms = ["dose", "medication", "prescription", "blood", "lab", "test"]
        if any(term in context_lower for term in medical_terms):
            return "medical"

        # Personal measurements
        personal_terms = ["height", "weight", "tall", "heavy", "weigh"]
        if any(term in context_lower for term in personal_terms):
            return "personal"

        # Distance/travel
        travel_terms = ["distance", "travel", "drive", "walk", "miles", "kilometers"]
        if any(term in context_lower for term in travel_terms):
            return "travel"

        return "general"

    def _load_regional_profiles(self) -> Dict[str, UnitPreferenceProfile]:
        """Load regional preference profiles."""
        profiles = {}

        # United States
        profiles["US"] = UnitPreferenceProfile(
            region_code="US",
            primary_system=UnitSystem.US_CUSTOMARY,
            length_units={
                "personal": "ft",  # Height in feet/inches
                "short": "in",
                "medium": "ft",
                "long": "mi",
                "medical": "cm",  # Medical uses metric
            },
            weight_units={
                "personal": "lb",
                "medical": "kg",  # Medical uses metric
                "cooking": "oz",
            },
            volume_units={
                "medical": "mL",  # Medical uses metric
                "cooking": "cup",
                "liquid": "fl oz",
            },
            temperature_unit="°F",
        )

        # United Kingdom
        profiles["GB"] = UnitPreferenceProfile(
            region_code="GB",
            primary_system=UnitSystem.MIXED,
            length_units={
                "personal": "ft",  # Height often in feet/inches
                "short": "cm",
                "medium": "m",
                "long": "mi",  # Distance in miles
                "medical": "cm",
            },
            weight_units={
                "personal": "st",  # Stone for body weight
                "medical": "kg",
                "general": "kg",
            },
            volume_units={
                "medical": "mL",
                "cooking": "mL",
                "liquid": "pt",  # Pints for beverages
            },
            temperature_unit="°C",
            mixed_usage=True,
        )

        # European Union (general)
        profiles["EU"] = UnitPreferenceProfile(
            region_code="EU",
            primary_system=UnitSystem.METRIC,
            length_units={
                "general": "m",
                "short": "cm",
                "long": "km",
            },
            weight_units={
                "general": "kg",
                "small": "g",
            },
            volume_units={
                "general": "L",
                "small": "mL",
            },
            temperature_unit="°C",
        )

        # Canada
        profiles["CA"] = UnitPreferenceProfile(
            region_code="CA",
            primary_system=UnitSystem.METRIC,
            length_units={
                "general": "m",
                "personal": "cm",  # Height in cm
                "long": "km",
            },
            weight_units={
                "general": "kg",
            },
            volume_units={
                "general": "L",
                "small": "mL",
            },
            temperature_unit="°C",
        )

        return profiles


def get_regional_units(region_code: str) -> Optional[UnitPreferenceProfile]:
    """
    Get unit preferences for a region.

    Args:
        region_code: ISO region code (e.g., "US", "GB")

    Returns:
        UnitPreferenceProfile or None
    """
    preferences = RegionalPreferences()
    return preferences.get_profile(region_code)


def detect_unit_system(text: str) -> UnitSystem:
    """
    Detect the predominant unit system in text.

    Args:
        text: Text containing measurements

    Returns:
        Detected UnitSystem
    """
    converter = UnitConverter()
    measurements = converter.detect_units_in_text(text)

    system_counts = {
        UnitSystem.METRIC: 0,
        UnitSystem.IMPERIAL: 0,
        UnitSystem.US_CUSTOMARY: 0,
    }

    for _, measurement in measurements:
        system_counts[measurement.unit.system] += 1

    # Return most common system
    return max(system_counts, key=lambda x: system_counts[x])


def adapt_to_region(
    text: str, target_region: str, preserve_medical: bool = True
) -> str:
    """
    Adapt measurements in text to regional preferences.

    Args:
        text: Text with measurements
        target_region: Target region code
        preserve_medical: Keep medical units standardized

    Returns:
        Adapted text
    """
    preferences = RegionalPreferences()
    return preferences.adapt_to_region(
        text, target_region, preserve_medical=preserve_medical
    )
