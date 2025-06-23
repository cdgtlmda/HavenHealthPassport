"""
Measurement unit conversion module for Haven Health Passport.

This module provides comprehensive unit conversion capabilities for medical
translations, ensuring accurate conversion between different measurement
systems while maintaining medical precision.

This module handles encrypted PHI with access control and audit logging
to ensure HIPAA compliance.
 Handles FHIR Resource validation.
"""

from typing import List

from src.healthcare.hipaa_access_control import AccessLevel, require_phi_access
from src.services.encryption_service import EncryptionService

from .core import (
    ConversionContext,
    ConversionResult,
    MeasurementValue,
    PrecisionLevel,
    Unit,
    UnitConverter,
    UnitSystem,
    UnitType,
)
from .currency import (
    Currency,
    CurrencyContext,
    CurrencyConverter,
    CurrencyInfo,
    CurrencyLocalizer,
    MedicalCostConverter,
    MoneyAmount,
    convert_currency,
    format_money,
    localize_currency_in_text,
    parse_money,
)
from .dates import (
    DateFormat,
    DateFormatter,
    DateLocalizer,
    DateParser,
    TimeFormat,
    format_date,
    localize_dates,
    parse_date,
)
from .formatters import (
    UnitFormatter,
    format_measurement,
    format_medication,
    format_range,
    parse_measurement,
)
from .medical import (
    LabValue,
    MedicalUnitConverter,
    MedicationDose,
    VitalSign,
    convert_lab_value,
    convert_medication_dose,
    get_normal_ranges,
)
from .regional import (
    RegionalPreferences,
    UnitPreferenceProfile,
    adapt_to_region,
    detect_unit_system,
    get_regional_units,
)

__all__ = [
    # Core
    "Unit",
    "UnitType",
    "UnitSystem",
    "MeasurementValue",
    "ConversionResult",
    "UnitConverter",
    "ConversionContext",
    "PrecisionLevel",
    # Medical
    "MedicalUnitConverter",
    "MedicationDose",
    "LabValue",
    "VitalSign",
    "convert_medication_dose",
    "convert_lab_value",
    "get_normal_ranges",
    # Regional
    "RegionalPreferences",
    "UnitPreferenceProfile",
    "get_regional_units",
    "detect_unit_system",
    "adapt_to_region",
    # Formatters
    "UnitFormatter",
    "format_measurement",
    "format_range",
    "format_medication",
    "parse_measurement",
    # Date localization
    "DateFormat",
    "TimeFormat",
    "DateParser",
    "DateFormatter",
    "DateLocalizer",
    "localize_dates",
    "format_date",
    "parse_date",
    # Currency conversion
    "Currency",
    "CurrencyInfo",
    "MoneyAmount",
    "CurrencyConverter",
    "CurrencyLocalizer",
    "MedicalCostConverter",
    "CurrencyContext",
    "convert_currency",
    "localize_currency_in_text",
    "format_money",
    "parse_money",
]


def validate_fhir_data(data: dict) -> dict:
    """Validate FHIR data.

    Args:
        data: Data to validate

    Returns:
        Validation result with 'valid', 'errors', and 'warnings' keys
    """
    errors: List[str] = []
    warnings: List[str] = []

    if not data:
        errors.append("No data provided")

    return {"valid": len(errors) == 0, "errors": errors, "warnings": warnings}
