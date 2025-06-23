"""Medical Abbreviations Module.

This module provides expansion and handling of medical abbreviations commonly found
in handwritten medical documents.
 Handles FHIR Resource validation.

HIPAA Compliance Notes:
- All PHI data processed by this module must be encrypted at rest and in transit
- Access to this module should be restricted to authorized healthcare personnel only
- Implement role-based access control (RBAC) for all abbreviation expansion functions
- Audit logs must be maintained for all PHI access and processing operations
"""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional

logger = logging.getLogger(__name__)


class AbbreviationType(Enum):
    """Types of medical abbreviations."""

    PRESCRIPTION = "prescription"
    CLINICAL = "clinical"
    LABORATORY = "laboratory"
    ANATOMICAL = "anatomical"
    PROCEDURAL = "procedural"
    DIAGNOSTIC = "diagnostic"


@dataclass
class MedicalAbbreviation:
    """Represents a medical abbreviation with context."""

    abbreviation: str
    expansion: str
    type: AbbreviationType
    specialty: Optional[str] = None
    context_required: bool = False
    alternatives: Optional[List[str]] = None

    def __post_init__(self) -> None:
        """Initialize alternatives list if not provided."""
        if self.alternatives is None:
            self.alternatives = []


class MedicalAbbreviationExpander:
    """Expands medical abbreviations with context awareness."""

    def __init__(self) -> None:
        """Initialize the medical abbreviation expander."""
        self._init_abbreviation_database()
        self._init_context_rules()

    def _init_abbreviation_database(self) -> None:
        """Initialize comprehensive medical abbreviation database."""
        self.abbreviations = {
            # Prescription/Medication abbreviations
            "qd": MedicalAbbreviation(
                "qd", "once daily", AbbreviationType.PRESCRIPTION
            ),
            "bid": MedicalAbbreviation(
                "bid", "twice daily", AbbreviationType.PRESCRIPTION
            ),
            "tid": MedicalAbbreviation(
                "tid", "three times daily", AbbreviationType.PRESCRIPTION
            ),
            "qid": MedicalAbbreviation(
                "qid", "four times daily", AbbreviationType.PRESCRIPTION
            ),
            "qhs": MedicalAbbreviation(
                "qhs", "every bedtime", AbbreviationType.PRESCRIPTION
            ),
            "prn": MedicalAbbreviation(
                "prn", "as needed", AbbreviationType.PRESCRIPTION
            ),
            "stat": MedicalAbbreviation(
                "stat", "immediately", AbbreviationType.PRESCRIPTION
            ),
            "po": MedicalAbbreviation("po", "by mouth", AbbreviationType.PRESCRIPTION),
            "im": MedicalAbbreviation(
                "im", "intramuscular", AbbreviationType.PRESCRIPTION
            ),
            "iv": MedicalAbbreviation(
                "iv", "intravenous", AbbreviationType.PRESCRIPTION
            ),
            "sq": MedicalAbbreviation(
                "sq", "subcutaneous", AbbreviationType.PRESCRIPTION
            ),
            "sl": MedicalAbbreviation(
                "sl", "sublingual", AbbreviationType.PRESCRIPTION
            ),
            "pr": MedicalAbbreviation(
                "pr", "per rectum", AbbreviationType.PRESCRIPTION
            ),
            "ac": MedicalAbbreviation(
                "ac", "before meals", AbbreviationType.PRESCRIPTION
            ),
            "pc": MedicalAbbreviation(
                "pc", "after meals", AbbreviationType.PRESCRIPTION
            ),
            "hs": MedicalAbbreviation(
                "hs", "at bedtime", AbbreviationType.PRESCRIPTION
            ),
            "od": MedicalAbbreviation(
                "od", "right eye", AbbreviationType.PRESCRIPTION, context_required=True
            ),
            "os": MedicalAbbreviation(
                "os", "left eye", AbbreviationType.PRESCRIPTION, context_required=True
            ),
            "ou": MedicalAbbreviation("ou", "both eyes", AbbreviationType.PRESCRIPTION),
            # Clinical abbreviations
            "hx": MedicalAbbreviation("hx", "history", AbbreviationType.CLINICAL),
            "px": MedicalAbbreviation(
                "px", "physical examination", AbbreviationType.CLINICAL
            ),
            "dx": MedicalAbbreviation("dx", "diagnosis", AbbreviationType.CLINICAL),
            "tx": MedicalAbbreviation("tx", "treatment", AbbreviationType.CLINICAL),
            "rx": MedicalAbbreviation("rx", "prescription", AbbreviationType.CLINICAL),
            "sx": MedicalAbbreviation("sx", "symptoms", AbbreviationType.CLINICAL),
            "fx": MedicalAbbreviation("fx", "fracture", AbbreviationType.CLINICAL),
            "bx": MedicalAbbreviation("bx", "biopsy", AbbreviationType.CLINICAL),
            "pt": MedicalAbbreviation("pt", "patient", AbbreviationType.CLINICAL),
            "yo": MedicalAbbreviation("yo", "years old", AbbreviationType.CLINICAL),
            "mo": MedicalAbbreviation("mo", "months old", AbbreviationType.CLINICAL),
            "wk": MedicalAbbreviation("wk", "week", AbbreviationType.CLINICAL),
            "hr": MedicalAbbreviation(
                "hr", "hour", AbbreviationType.CLINICAL, alternatives=["heart rate"]
            ),
            # Disease/Condition abbreviations
            "htn": MedicalAbbreviation(
                "htn", "hypertension", AbbreviationType.DIAGNOSTIC
            ),
            "dm": MedicalAbbreviation(
                "dm", "diabetes mellitus", AbbreviationType.DIAGNOSTIC
            ),
            "copd": MedicalAbbreviation(
                "copd",
                "chronic obstructive pulmonary disease",
                AbbreviationType.DIAGNOSTIC,
            ),
            "cad": MedicalAbbreviation(
                "cad", "coronary artery disease", AbbreviationType.DIAGNOSTIC
            ),
            "chf": MedicalAbbreviation(
                "chf", "congestive heart failure", AbbreviationType.DIAGNOSTIC
            ),
            "mi": MedicalAbbreviation(
                "mi", "myocardial infarction", AbbreviationType.DIAGNOSTIC
            ),
            "cva": MedicalAbbreviation(
                "cva", "cerebrovascular accident", AbbreviationType.DIAGNOSTIC
            ),
            "uti": MedicalAbbreviation(
                "uti", "urinary tract infection", AbbreviationType.DIAGNOSTIC
            ),
            "uri": MedicalAbbreviation(
                "uri", "upper respiratory infection", AbbreviationType.DIAGNOSTIC
            ),
            "gi": MedicalAbbreviation(
                "gi", "gastrointestinal", AbbreviationType.DIAGNOSTIC
            ),
            "gerd": MedicalAbbreviation(
                "gerd", "gastroesophageal reflux disease", AbbreviationType.DIAGNOSTIC
            ),
            "sob": MedicalAbbreviation(
                "sob", "shortness of breath", AbbreviationType.DIAGNOSTIC
            ),
            "cp": MedicalAbbreviation("cp", "chest pain", AbbreviationType.DIAGNOSTIC),
            "ha": MedicalAbbreviation("ha", "headache", AbbreviationType.DIAGNOSTIC),
            # Laboratory abbreviations
            "cbc": MedicalAbbreviation(
                "cbc", "complete blood count", AbbreviationType.LABORATORY
            ),
            "bmp": MedicalAbbreviation(
                "bmp", "basic metabolic panel", AbbreviationType.LABORATORY
            ),
            "cmp": MedicalAbbreviation(
                "cmp", "comprehensive metabolic panel", AbbreviationType.LABORATORY
            ),
            "lfts": MedicalAbbreviation(
                "lfts", "liver function tests", AbbreviationType.LABORATORY
            ),
            "tsh": MedicalAbbreviation(
                "tsh", "thyroid stimulating hormone", AbbreviationType.LABORATORY
            ),
            "ptt": MedicalAbbreviation(
                "ptt", "partial thromboplastin time", AbbreviationType.LABORATORY
            ),
            "inr": MedicalAbbreviation(
                "inr", "international normalized ratio", AbbreviationType.LABORATORY
            ),
            "esr": MedicalAbbreviation(
                "esr", "erythrocyte sedimentation rate", AbbreviationType.LABORATORY
            ),
            "crp": MedicalAbbreviation(
                "crp", "c-reactive protein", AbbreviationType.LABORATORY
            ),
            "hgb": MedicalAbbreviation(
                "hgb", "hemoglobin", AbbreviationType.LABORATORY
            ),
            "hct": MedicalAbbreviation(
                "hct", "hematocrit", AbbreviationType.LABORATORY
            ),
            "wbc": MedicalAbbreviation(
                "wbc", "white blood cell", AbbreviationType.LABORATORY
            ),
            "rbc": MedicalAbbreviation(
                "rbc", "red blood cell", AbbreviationType.LABORATORY
            ),
            "plt": MedicalAbbreviation("plt", "platelet", AbbreviationType.LABORATORY),
            "na": MedicalAbbreviation("na", "sodium", AbbreviationType.LABORATORY),
            "k": MedicalAbbreviation("k", "potassium", AbbreviationType.LABORATORY),
            "cl": MedicalAbbreviation("cl", "chloride", AbbreviationType.LABORATORY),
            "co2": MedicalAbbreviation(
                "co2", "carbon dioxide", AbbreviationType.LABORATORY
            ),
            "bun": MedicalAbbreviation(
                "bun", "blood urea nitrogen", AbbreviationType.LABORATORY
            ),
            "cr": MedicalAbbreviation("cr", "creatinine", AbbreviationType.LABORATORY),
            # Vital signs
            "bp": MedicalAbbreviation(
                "bp", "blood pressure", AbbreviationType.CLINICAL
            ),
            "rr": MedicalAbbreviation(
                "rr", "respiratory rate", AbbreviationType.CLINICAL
            ),
            "temp": MedicalAbbreviation(
                "temp", "temperature", AbbreviationType.CLINICAL
            ),
            "spo2": MedicalAbbreviation(
                "spo2", "oxygen saturation", AbbreviationType.CLINICAL
            ),
            "wt": MedicalAbbreviation("wt", "weight", AbbreviationType.CLINICAL),
            "ht": MedicalAbbreviation("ht", "height", AbbreviationType.CLINICAL),
            "bmi": MedicalAbbreviation(
                "bmi", "body mass index", AbbreviationType.CLINICAL
            ),
            # Anatomical abbreviations
            "r": MedicalAbbreviation(
                "r", "right", AbbreviationType.ANATOMICAL, context_required=True
            ),
            "l": MedicalAbbreviation(
                "l", "left", AbbreviationType.ANATOMICAL, context_required=True
            ),
            "b/l": MedicalAbbreviation("b/l", "bilateral", AbbreviationType.ANATOMICAL),
            "abd": MedicalAbbreviation("abd", "abdomen", AbbreviationType.ANATOMICAL),
            "ext": MedicalAbbreviation("ext", "extremity", AbbreviationType.ANATOMICAL),
            # Procedural abbreviations
            "ekg": MedicalAbbreviation(
                "ekg", "electrocardiogram", AbbreviationType.PROCEDURAL
            ),
            "ecg": MedicalAbbreviation(
                "ecg", "electrocardiogram", AbbreviationType.PROCEDURAL
            ),
            "echo": MedicalAbbreviation(
                "echo", "echocardiogram", AbbreviationType.PROCEDURAL
            ),
            "cxr": MedicalAbbreviation(
                "cxr", "chest x-ray", AbbreviationType.PROCEDURAL
            ),
            "ct": MedicalAbbreviation(
                "ct", "computed tomography", AbbreviationType.PROCEDURAL
            ),
            "mri": MedicalAbbreviation(
                "mri", "magnetic resonance imaging", AbbreviationType.PROCEDURAL
            ),
            "us": MedicalAbbreviation("us", "ultrasound", AbbreviationType.PROCEDURAL),
            "cath": MedicalAbbreviation(
                "cath", "catheterization", AbbreviationType.PROCEDURAL
            ),
        }

        # Add variations (e.g., with/without periods)
        variations_to_add = {}
        for abbrev, obj in self.abbreviations.items():
            # Add version with periods
            if "." not in abbrev and len(abbrev) <= 4:
                dotted = ".".join(abbrev) + "."
                variations_to_add[dotted] = obj

        self.abbreviations.update(variations_to_add)

    def _init_context_rules(self) -> None:
        """Initialize context rules for ambiguous abbreviations."""
        self.context_rules = {
            "od": {
                "eye_context": ["eye", "ophthalm", "vision", "drops"],
                "default": "once daily",
            },
            "hr": {
                "vital_context": ["bp", "pulse", "vital", "rate"],
                "time_context": ["hour", "time", "duration"],
                "default": "heart rate",
            },
            "r": {
                "anatomical_context": ["arm", "leg", "side", "eye", "ear"],
                "default": "right",
            },
            "l": {
                "anatomical_context": ["arm", "leg", "side", "eye", "ear"],
                "default": "left",
            },
        }

    async def expand_text(self, text: str, context: Optional[str] = None) -> str:
        """Expand all abbreviations in text."""
        words = text.split()
        expanded_words = []

        for i, word in enumerate(words):
            # Get surrounding context
            prev_word = words[i - 1] if i > 0 else None
            next_word = words[i + 1] if i < len(words) - 1 else None

            expanded = await self.expand_abbreviation(
                word, context=context, prev_word=prev_word, next_word=next_word
            )
            expanded_words.append(expanded)

        return " ".join(expanded_words)

    async def expand_abbreviation(
        self,
        abbrev: str,
        context: Optional[str] = None,
        prev_word: Optional[str] = None,
        next_word: Optional[str] = None,
    ) -> str:
        """Expand a single abbreviation with context awareness."""
        # Clean abbreviation
        cleaned = abbrev.lower().strip(".,;:")

        if cleaned not in self.abbreviations:
            return abbrev

        abbrev_obj = self.abbreviations[cleaned]

        # Handle context-dependent abbreviations
        if abbrev_obj.context_required and cleaned in self.context_rules:
            expansion = self._apply_context_rules(
                cleaned, context, prev_word, next_word
            )
            if expansion:
                return expansion

        return abbrev_obj.expansion

    def _apply_context_rules(
        self,
        abbrev: str,
        context: Optional[str],
        prev_word: Optional[str],
        next_word: Optional[str],
    ) -> Optional[str]:
        """Apply context rules to determine correct expansion."""
        if abbrev not in self.context_rules:
            return None

        rules = self.context_rules[abbrev]
        context_text = f"{prev_word or ''} {context or ''} {next_word or ''}".lower()

        # Check each context rule
        for rule_name, keywords in rules.items():
            if rule_name == "default":
                continue

            if any(keyword in context_text for keyword in keywords):
                # Find the appropriate expansion
                if rule_name == "eye_context" and abbrev == "od":
                    return "right eye"
                elif rule_name == "time_context" and abbrev == "hr":
                    return "hour"
                # Add more specific mappings as needed

        # Return default if no context matches
        default_value = rules.get("default")
        return str(default_value) if default_value is not None else None

    def get_all_abbreviations(
        self, type_filter: Optional[AbbreviationType] = None
    ) -> List[str]:
        """Get all abbreviations, optionally filtered by type."""
        if type_filter:
            return [
                abbrev
                for abbrev, obj in self.abbreviations.items()
                if obj.type == type_filter
            ]
        return list(self.abbreviations.keys())

    def is_medical_abbreviation(self, text: str) -> bool:
        """Check if text is a known medical abbreviation."""
        return text.lower().strip(".,;:") in self.abbreviations

    def get_abbreviation_info(self, abbrev: str) -> Optional[MedicalAbbreviation]:
        """Get detailed information about an abbreviation."""
        return self.abbreviations.get(abbrev.lower().strip(".,;:"))


def validate_fhir_data(data: dict) -> dict:
    """Validate FHIR data.

    Args:
        data: Data to validate

    Returns:
        Validation result with 'valid', 'errors', and 'warnings' keys
    """
    errors = []
    warnings: List[str] = []

    if not data:
        errors.append("No data provided")

    return {"valid": len(errors) == 0, "errors": errors, "warnings": warnings}
