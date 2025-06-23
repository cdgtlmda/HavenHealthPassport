"""Medical terminology validation for healthcare documentation.

Note: This module handles PHI-related medical terminology.
- Encryption: All medical terms and patient data must be encrypted at rest and in transit
- Access Control: Implement role-based access control (RBAC) for medical terminology data
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Set


@dataclass
class MedicalTerm:
    """Represents a validated medical term."""

    term: str
    category: str
    confidence: float
    alternatives: Optional[List[str]] = None


class MedicalTerminologyValidator:
    """Validates medical terminology in healthcare documentation."""

    def __init__(self) -> None:
        """Initialize medical terminology service."""
        self.medical_terms: Set[str] = set()
        self.abbreviations: Dict[str, str] = {}
        self.synonyms: Dict[str, List[str]] = {}
        self._initialize_terms()

    def _initialize_terms(self) -> None:
        """Initialize common medical terms and abbreviations."""
        # Common medical terms
        self.medical_terms.update(
            [
                "hypertension",
                "diabetes",
                "asthma",
                "pneumonia",
                "bronchitis",
                "arthritis",
                "migraine",
                "anemia",
                "infection",
                "inflammation",
                "fracture",
                "allergy",
            ]
        )

        # Common medical abbreviations
        self.abbreviations.update(
            {
                "BP": "blood pressure",
                "HR": "heart rate",
                "RR": "respiratory rate",
                "O2": "oxygen",
                "Rx": "prescription",
                "Dx": "diagnosis",
                "Tx": "treatment",
                "Hx": "history",
            }
        )

    def validate_term(self, term: str) -> bool:
        """Validate if a term is a recognized medical term."""
        return term.lower() in self.medical_terms

    def expand_abbreviation(self, abbr: str) -> Optional[str]:
        """Expand medical abbreviations."""
        return self.abbreviations.get(abbr.upper())

    def get_synonyms(self, term: str) -> List[str]:
        """Get synonyms for a medical term."""
        return self.synonyms.get(term.lower(), [])
