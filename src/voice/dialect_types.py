"""
Dialect Identification Type Definitions.

This module contains enum definitions and basic types for dialect identification.
"""

from enum import Enum


class DialectRegion(Enum):
    """Major dialect regions for English and Spanish."""

    # English dialects
    US_GENERAL = "us_general"  # General American
    US_SOUTHERN = "us_southern"  # Southern US
    US_NORTHEASTERN = "us_northeastern"  # Boston, New York
    US_MIDWESTERN = "us_midwestern"  # Midwest
    US_WESTERN = "us_western"  # California, Pacific Northwest
    UK_RP = "uk_rp"  # Received Pronunciation
    UK_COCKNEY = "uk_cockney"  # London Cockney
    UK_SCOTTISH = "uk_scottish"  # Scottish English
    UK_IRISH = "uk_irish"  # Irish English
    UK_WELSH = "uk_welsh"  # Welsh English
    AUSTRALIAN = "australian"  # Australian English
    NEW_ZEALAND = "new_zealand"  # New Zealand English
    CANADIAN = "canadian"  # Canadian English
    INDIAN = "indian"  # Indian English
    SOUTH_AFRICAN = "south_african"  # South African English

    # Spanish dialects
    SPAIN_CASTILIAN = "spain_castilian"  # Castilian Spanish
    SPAIN_ANDALUSIAN = "spain_andalusian"  # Andalusian Spanish
    MEXICO = "mexican"  # Mexican Spanish
    CARIBBEAN = "caribbean"  # Caribbean Spanish
    ARGENTINA = "argentinian"  # Argentinian Spanish
    COLOMBIA = "colombian"  # Colombian Spanish
    PERU = "peruvian"  # Peruvian Spanish
    CHILE = "chilean"  # Chilean Spanish
    VENEZUELA = "venezuelan"  # Venezuelan Spanish


class DialectFeatureType(Enum):
    """Types of features used for dialect identification."""

    PHONETIC = "phonetic"
    PROSODIC = "prosodic"
    LEXICAL = "lexical"
    MORPHOLOGICAL = "morphological"
    SYNTACTIC = "syntactic"


class DialectIndicator(Enum):
    """Specific dialect indicators."""

    # Phonetic indicators
    RHOTICITY = "rhoticity"  # R-dropping patterns
    VOWEL_SHIFT = "vowel_shift"  # Vowel pronunciations
    CONSONANT_VARIATION = "consonant_variation"
    DIPHTHONGIZATION = "diphthongization"
    MONOPHTHONGIZATION = "monophthongization"

    # Prosodic indicators
    INTONATION_PATTERN = "intonation_pattern"
    STRESS_PATTERN = "stress_pattern"
    RHYTHM_TYPE = "rhythm_type"

    # Lexical indicators
    VOCABULARY_CHOICE = "vocabulary_choice"
    IDIOM_USAGE = "idiom_usage"
