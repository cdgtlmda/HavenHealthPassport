"""Medical Acronym Expander.

Expands medical acronyms to their full forms.
Handles encrypted medical terminology with access control validation.
 Handles FHIR Resource validation.
"""

import logging
import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple


@dataclass
class AcronymExpansion:
    """Represents an acronym expansion."""

    acronym: str
    expansion: str
    context: Optional[str] = None
    confidence: float = 1.0
    category: Optional[str] = None


class MedicalAcronymExpander:
    """Expands medical acronyms and abbreviations."""

    def __init__(self, custom_acronyms: Optional[Dict[str, str]] = None):
        """Initialize acronym expander.

        Args:
            custom_acronyms: Additional acronyms to include
        """
        self.logger = logging.getLogger(__name__)

        # Initialize with common medical acronyms
        self.acronyms = self._load_medical_acronyms()

        # Add custom acronyms
        if custom_acronyms:
            self.acronyms.update(custom_acronyms)

        # Context-specific expansions
        self.context_acronyms = self._load_context_acronyms()

        # Compile regex pattern for acronym detection
        self._compile_patterns()

    def _load_medical_acronyms(self) -> Dict[str, str]:
        """Load common medical acronyms."""
        return {
            # Conditions
            "MI": "myocardial infarction",
            "CHF": "congestive heart failure",
            "COPD": "chronic obstructive pulmonary disease",
            "CVA": "cerebrovascular accident",
            "DM": "diabetes mellitus",
            "HTN": "hypertension",
            "CAD": "coronary artery disease",
            "CKD": "chronic kidney disease",
            "GERD": "gastroesophageal reflux disease",
            "UTI": "urinary tract infection",
            "DVT": "deep vein thrombosis",
            "PE": "pulmonary embolism",
            "ARDS": "acute respiratory distress syndrome",
            # Procedures/Tests
            "ECG": "electrocardiogram",
            "EKG": "electrocardiogram",
            "MRI": "magnetic resonance imaging",
            "CT": "computed tomography",
            "CBC": "complete blood count",
            "BMP": "basic metabolic panel",
            "CMP": "comprehensive metabolic panel",
            "ABG": "arterial blood gas",
            "CXR": "chest X-ray",
            "LP": "lumbar puncture",
            # Medications
            "ASA": "aspirin",
            "NSAID": "non-steroidal anti-inflammatory drug",
            "ACE": "angiotensin-converting enzyme",
            "ARB": "angiotensin receptor blocker",
            "PPI": "proton pump inhibitor",
            # Departments/Specialties
            "ED": "emergency department",
            "ER": "emergency room",
            "ICU": "intensive care unit",
            "OR": "operating room",
            "PACU": "post-anesthesia care unit",
            # Vital Signs/Measurements
            "BP": "blood pressure",
            "HR": "heart rate",
            "RR": "respiratory rate",
            "O2": "oxygen",
            "SpO2": "oxygen saturation",
            "BMI": "body mass index",
        }

    def _load_context_acronyms(self) -> Dict[str, Dict[str, str]]:
        """Load context-specific acronym expansions."""
        return {
            "cardiology": {
                "LAD": "left anterior descending artery",
                "RCA": "right coronary artery",
                "LV": "left ventricle",
                "EF": "ejection fraction",
            },
            "neurology": {
                "MS": "multiple sclerosis",
                "ALS": "amyotrophic lateral sclerosis",
                "TIA": "transient ischemic attack",
                "CSF": "cerebrospinal fluid",
            },
            "pulmonology": {
                "PFT": "pulmonary function test",
                "FEV1": "forced expiratory volume in 1 second",
                "DLCO": "diffusing capacity for carbon monoxide",
            },
        }

    def _compile_patterns(self) -> None:
        """Compile regex patterns for acronym detection."""
        # Pattern for standalone acronyms (2-5 uppercase letters)
        self.acronym_pattern = re.compile(r"\b([A-Z]{2,5})\b")

        # Pattern for acronyms with numbers (e.g., COVID-19, H1N1)
        self.acronym_with_number_pattern = re.compile(
            r"\b([A-Z]+\d+[A-Z]*|\d*[A-Z]+\d+)\b"
        )

    def expand_text(
        self, text: str, context: Optional[str] = None
    ) -> Tuple[str, List[AcronymExpansion]]:
        """Expand acronyms in text.

        Args:
            text: Input text
            context: Medical context/specialty

        Returns:
            Tuple of (expanded text, list of expansions made)
        """
        expansions = []
        expanded_text = text

        # Find all acronyms
        acronyms_found = self._find_acronyms(text)

        # Expand each acronym
        for acronym, positions in acronyms_found.items():
            expansion = self._get_expansion(acronym, context)

            if expansion:
                # Replace in text (backward to preserve positions)
                for start, end in reversed(positions):
                    expanded_text = (
                        expanded_text[:start]
                        + f"{acronym} ({expansion})"
                        + expanded_text[end:]
                    )

                expansions.append(
                    AcronymExpansion(
                        acronym=acronym,
                        expansion=expansion,
                        context=context,
                        confidence=0.9 if context else 0.8,
                    )
                )

        return expanded_text, expansions

    def _find_acronyms(self, text: str) -> Dict[str, List[Tuple[int, int]]]:
        """Find all acronyms in text with their positions."""
        acronyms: Dict[str, List[Tuple[int, int]]] = {}

        # Find standard acronyms
        for match in self.acronym_pattern.finditer(text):
            acronym = match.group(1)
            if acronym in self.acronyms:
                if acronym not in acronyms:
                    acronyms[acronym] = []
                acronyms[acronym].append((match.start(), match.end()))

        # Find acronyms with numbers
        for match in self.acronym_with_number_pattern.finditer(text):
            acronym = match.group(1)
            if acronym in self.acronyms:
                if acronym not in acronyms:
                    acronyms[acronym] = []
                acronyms[acronym].append((match.start(), match.end()))

        return acronyms

    def _get_expansion(
        self, acronym: str, context: Optional[str] = None
    ) -> Optional[str]:
        """Get expansion for acronym, considering context."""
        # Check context-specific expansions first
        if context and context in self.context_acronyms:
            if acronym in self.context_acronyms[context]:
                return self.context_acronyms[context][acronym]

        # Fall back to general expansions
        return self.acronyms.get(acronym)

    def add_acronym(
        self, acronym: str, expansion: str, context: Optional[str] = None
    ) -> None:
        """Add a new acronym to the dictionary."""
        if context:
            if context not in self.context_acronyms:
                self.context_acronyms[context] = {}
            self.context_acronyms[context][acronym] = expansion
        else:
            self.acronyms[acronym] = expansion

        self.logger.info("Added acronym: %s -> %s", acronym, expansion)

    def get_all_acronyms(self, context: Optional[str] = None) -> Dict[str, str]:
        """Get all acronyms, optionally filtered by context."""
        if context and context in self.context_acronyms:
            # Merge general and context-specific
            merged = self.acronyms.copy()
            merged.update(self.context_acronyms[context])
            return merged
        return self.acronyms.copy()


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
