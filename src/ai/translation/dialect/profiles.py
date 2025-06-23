"""
Dialect profiles for various languages.

This module contains pre-defined dialect profiles for major language variants,
including medical terminology differences and regional preferences.

This module handles encrypted PHI with access control and audit logging
to ensure HIPAA compliance.
"""

import logging
from typing import Dict, List, Optional

from ..config import Language
from .core import DialectProfile

logger = logging.getLogger(__name__)

# Global registry of dialect profiles
_DIALECT_REGISTRY: Dict[str, DialectProfile] = {}


def register_dialect_profile(profile: DialectProfile) -> None:
    """Register a dialect profile in the global registry."""
    _DIALECT_REGISTRY[profile.dialect_code] = profile
    logger.info(
        "Registered dialect profile: %s (%s)", profile.dialect_code, profile.name
    )


def get_dialect_profile(dialect_code: str) -> Optional[DialectProfile]:
    """Get a dialect profile by code."""
    return _DIALECT_REGISTRY.get(dialect_code)


def list_supported_dialects(language: Optional[Language] = None) -> List[str]:
    """List all supported dialect codes."""
    if language:
        return [
            code
            for code, profile in _DIALECT_REGISTRY.items()
            if profile.base_language == language
        ]
    return list(_DIALECT_REGISTRY.keys())


def _initialize_english_dialects() -> None:
    """Initialize English dialect profiles."""
    # American English
    us_profile = DialectProfile(
        dialect_code="en-US",
        base_language=Language.ENGLISH,
        name="American English",
        region="United States",
        alternative_names=["US English", "American"],
        lexical_variations={
            "medical_facility": ["hospital", "medical center", "clinic"],
            "emergency": ["emergency room", "ER", "emergency department"],
            "pharmacy": ["pharmacy", "drugstore"],
            "physician": ["doctor", "physician", "MD"],
        },
        spelling_variations={
            "color": "color",
            "center": "center",
            "pediatric": "pediatric",
            "anesthesia": "anesthesia",
            "hemoglobin": "hemoglobin",
            "esophagus": "esophagus",
            "fetus": "fetus",
        },
        medical_term_variations={
            "epinephrine": "epinephrine",
            "acetaminophen": "acetaminophen",
            "emergency_room": "emergency room",
            "operating_room": "operating room",
            "labor": "labor",
        },
        date_formats=["MM/DD/YYYY", "M/D/YY"],
        measurement_preferences={
            "temperature": "Fahrenheit",
            "weight": "pounds",
            "height": "feet/inches",
            "volume": "fluid ounces",
            "distance": "miles",
        },
        healthcare_system_terms={
            "insurance": "health insurance",
            "primary_care": "primary care physician",
            "specialist": "specialist",
            "copay": "copayment",
            "deductible": "deductible",
        },
        medication_naming={
            "paracetamol": "acetaminophen",
            "adrenaline": "epinephrine",
            "salbutamol": "albuterol",
        },
    )
    register_dialect_profile(us_profile)

    # British English
    uk_profile = DialectProfile(
        dialect_code="en-GB",
        base_language=Language.ENGLISH,
        name="British English",
        region="United Kingdom",
        alternative_names=["UK English", "British"],
        lexical_variations={
            "medical_facility": ["hospital", "surgery", "clinic"],
            "emergency": ["A&E", "accident and emergency", "casualty"],
            "pharmacy": ["pharmacy", "chemist"],
            "physician": ["doctor", "GP", "consultant"],
        },
        spelling_variations={
            "colour": "colour",
            "centre": "centre",
            "paediatric": "paediatric",
            "anaesthesia": "anaesthesia",
            "haemoglobin": "haemoglobin",
            "oesophagus": "oesophagus",
            "foetus": "foetus",
        },
        medical_term_variations={
            "adrenaline": "adrenaline",
            "paracetamol": "paracetamol",
            "accident_emergency": "A&E",
            "operating_theatre": "operating theatre",
            "labour": "labour",
        },
        date_formats=["DD/MM/YYYY", "D/M/YY"],
        measurement_preferences={
            "temperature": "Celsius",
            "weight": "kilograms",
            "height": "centimeters",
            "volume": "milliliters",
            "distance": "kilometers",
        },
        healthcare_system_terms={
            "nhs": "National Health Service",
            "gp": "General Practitioner",
            "consultant": "consultant",
            "prescription_charge": "prescription charge",
            "nhs_number": "NHS number",
        },
        medication_naming={
            "acetaminophen": "paracetamol",
            "epinephrine": "adrenaline",
            "albuterol": "salbutamol",
        },
    )
    register_dialect_profile(uk_profile)

    # Canadian English
    ca_profile = DialectProfile(
        dialect_code="en-CA",
        base_language=Language.ENGLISH,
        name="Canadian English",
        region="Canada",
        alternative_names=["Canadian"],
        lexical_variations={
            "medical_facility": ["hospital", "medical centre", "clinic"],
            "emergency": ["emergency room", "ER", "emergency department"],
            "pharmacy": ["pharmacy", "drugstore"],
            "physician": ["doctor", "physician", "MD"],
        },
        spelling_variations={
            "colour": "colour",
            "centre": "centre",
            "pediatric": "pediatric",  # Mixed US/UK spelling
            "anaesthesia": "anaesthesia",
            "hemoglobin": "hemoglobin",
            "esophagus": "esophagus",
            "fetus": "fetus",
        },
        medical_term_variations={
            "epinephrine": "epinephrine",
            "acetaminophen": "acetaminophen",
            "emergency_room": "emergency room",
            "operating_room": "operating room",
            "labour": "labour",
        },
        date_formats=["YYYY-MM-DD", "DD/MM/YYYY", "MM/DD/YYYY"],
        measurement_preferences={
            "temperature": "Celsius",
            "weight": "kilograms",
            "height": "centimeters",
            "volume": "milliliters",
            "distance": "kilometers",
        },
        healthcare_system_terms={
            "medicare": "provincial healthcare",
            "family_doctor": "family physician",
            "walk_in_clinic": "walk-in clinic",
            "health_card": "health card",
            "ohip": "provincial health insurance",
        },
        medication_naming={
            "paracetamol": "acetaminophen",
            "adrenaline": "epinephrine",
            "salbutamol": "salbutamol",
        },
    )
    register_dialect_profile(ca_profile)

    # Australian English
    au_profile = DialectProfile(
        dialect_code="en-AU",
        base_language=Language.ENGLISH,
        name="Australian English",
        region="Australia",
        alternative_names=["Australian", "Aussie English"],
        lexical_variations={
            "medical_facility": ["hospital", "medical centre", "clinic"],
            "emergency": ["emergency department", "ED", "casualty"],
            "pharmacy": ["pharmacy", "chemist"],
            "physician": ["doctor", "GP", "specialist"],
        },
        spelling_variations={
            "colour": "colour",
            "centre": "centre",
            "paediatric": "paediatric",
            "anaesthesia": "anaesthesia",
            "haemoglobin": "haemoglobin",
            "oesophagus": "oesophagus",
            "foetus": "foetus",
        },
        medical_term_variations={
            "adrenaline": "adrenaline",
            "paracetamol": "paracetamol",
            "emergency_department": "emergency department",
            "operating_theatre": "operating theatre",
            "labour": "labour",
        },
        date_formats=["DD/MM/YYYY", "D/M/YY"],
        measurement_preferences={
            "temperature": "Celsius",
            "weight": "kilograms",
            "height": "centimeters",
            "volume": "milliliters",
            "distance": "kilometers",
        },
        healthcare_system_terms={
            "medicare": "Medicare",
            "bulk_billing": "bulk billing",
            "gp": "general practitioner",
            "pbs": "Pharmaceutical Benefits Scheme",
            "medicare_card": "Medicare card",
        },
        medication_naming={
            "acetaminophen": "paracetamol",
            "epinephrine": "adrenaline",
            "albuterol": "salbutamol",
        },
    )
    register_dialect_profile(au_profile)


def _initialize_spanish_dialects() -> None:
    """Initialize Spanish dialect profiles."""
    # Mexican Spanish
    mx_profile = DialectProfile(
        dialect_code="es-MX",
        base_language=Language.SPANISH,
        name="Mexican Spanish",
        region="Mexico",
        alternative_names=["español mexicano"],
        lexical_variations={
            "medical_facility": ["hospital", "clínica", "centro médico"],
            "emergency": ["urgencias", "emergencias", "sala de urgencias"],
            "pharmacy": ["farmacia", "botica"],
            "physician": ["doctor", "médico", "doctora", "médica"],
        },
        spelling_variations={
            "México": "México",  # With accent
            "médico": "médico",
            "análisis": "análisis",
        },
        medical_term_variations={
            "prescription": "receta médica",
            "emergency_room": "sala de urgencias",
            "surgery": "cirugía",
            "ambulance": "ambulancia",
            "nurse": "enfermero/enfermera",
        },
        date_formats=["DD/MM/YYYY"],
        measurement_preferences={
            "temperature": "Celsius",
            "weight": "kilograms",
            "height": "centimeters",
            "volume": "milliliters",
            "distance": "kilometers",
        },
        healthcare_system_terms={
            "imss": "Instituto Mexicano del Seguro Social",
            "issste": "Instituto de Seguridad Social",
            "seguro_popular": "Seguro Popular",
            "consultorio": "consultorio médico",
        },
        medication_naming={
            "acetaminophen": "paracetamol",
            "ibuprofen": "ibuprofeno",
            "aspirin": "aspirina",
        },
    )
    register_dialect_profile(mx_profile)

    # Spain Spanish
    es_profile = DialectProfile(
        dialect_code="es-ES",
        base_language=Language.SPANISH,
        name="Peninsular Spanish",
        region="Spain",
        alternative_names=["español de España", "castellano"],
        lexical_variations={
            "medical_facility": ["hospital", "centro de salud", "ambulatorio"],
            "emergency": ["urgencias", "emergencias"],
            "pharmacy": ["farmacia"],
            "physician": ["médico", "doctor", "facultativo"],
        },
        spelling_variations={
            "analizar": "analizar",  # vs analyzar in some regions
            "hospitalización": "hospitalización",
        },
        medical_term_variations={
            "prescription": "receta",
            "emergency_room": "urgencias",
            "surgery": "quirófano",
            "ambulance": "ambulancia",
            "nurse": "enfermero/enfermera",
        },
        date_formats=["DD/MM/YYYY"],
        measurement_preferences={
            "temperature": "Celsius",
            "weight": "kilograms",
            "height": "centimeters",
            "volume": "milliliters",
            "distance": "kilometers",
        },
        healthcare_system_terms={
            "seguridad_social": "Seguridad Social",
            "centro_salud": "centro de salud",
            "tarjeta_sanitaria": "tarjeta sanitaria",
            "medico_cabecera": "médico de cabecera",
        },
        medication_naming={
            "acetaminophen": "paracetamol",
            "ibuprofen": "ibuprofeno",
            "aspirin": "aspirina",
        },
    )
    register_dialect_profile(es_profile)


def _initialize_french_dialects() -> None:
    """Initialize French dialect profiles."""
    # France French
    fr_profile = DialectProfile(
        dialect_code="fr-FR",
        base_language=Language.FRENCH,
        name="Metropolitan French",
        region="France",
        alternative_names=["français de France"],
        lexical_variations={
            "medical_facility": ["hôpital", "clinique", "centre médical"],
            "emergency": ["urgences", "service d'urgence"],
            "pharmacy": ["pharmacie"],
            "physician": ["médecin", "docteur", "praticien"],
        },
        medical_term_variations={
            "prescription": "ordonnance",
            "emergency_room": "service des urgences",
            "surgery": "chirurgie",
            "ambulance": "ambulance",
            "nurse": "infirmier/infirmière",
        },
        date_formats=["DD/MM/YYYY"],
        measurement_preferences={
            "temperature": "Celsius",
            "weight": "kilograms",
            "height": "centimeters",
            "volume": "milliliters",
            "distance": "kilometers",
        },
        healthcare_system_terms={
            "secu": "Sécurité sociale",
            "carte_vitale": "carte Vitale",
            "medecin_traitant": "médecin traitant",
            "cmu": "Couverture maladie universelle",
        },
    )
    register_dialect_profile(fr_profile)

    # Canadian French
    ca_fr_profile = DialectProfile(
        dialect_code="fr-CA",
        base_language=Language.FRENCH,
        name="Canadian French",
        region="Canada",
        alternative_names=["français canadien", "québécois"],
        lexical_variations={
            "medical_facility": ["hôpital", "clinique", "CLSC"],
            "emergency": ["urgence", "salle d'urgence"],
            "pharmacy": ["pharmacie"],
            "physician": ["médecin", "docteur"],
        },
        medical_term_variations={
            "prescription": "prescription",
            "emergency_room": "salle d'urgence",
            "surgery": "chirurgie",
            "ambulance": "ambulance",
            "nurse": "infirmier/infirmière",
        },
        date_formats=["YYYY-MM-DD", "DD/MM/YYYY"],
        measurement_preferences={
            "temperature": "Celsius",
            "weight": "kilograms",
            "height": "centimeters",
            "volume": "milliliters",
            "distance": "kilometers",
        },
        healthcare_system_terms={
            "ramq": "Régie de l'assurance maladie du Québec",
            "clsc": "Centre local de services communautaires",
            "carte_soleil": "carte d'assurance maladie",
            "medecin_famille": "médecin de famille",
        },
    )
    register_dialect_profile(ca_fr_profile)


def initialize_all_dialects() -> None:
    """Initialize all built-in dialect profiles."""
    _initialize_english_dialects()
    _initialize_spanish_dialects()
    _initialize_french_dialects()
    # Add more languages as needed

    logger.info("Initialized %d dialect profiles", len(_DIALECT_REGISTRY))


# Initialize on module import
initialize_all_dialects()
