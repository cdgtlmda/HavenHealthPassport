"""ICD-10 Implementation.

This module implements ICD-10 code management, including ICD-10-CM (Clinical Modification)
and ICD-10-PCS (Procedure Coding System) with support for code hierarchy, validation,
and refugee health-specific mappings.
"""

import logging
import re
from enum import Enum
from typing import Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


class ICD10Category(Enum):
    """Major ICD-10 categories."""

    INFECTIOUS = "A00-B99"  # Certain infectious and parasitic diseases
    NEOPLASMS = "C00-D49"  # Neoplasms
    BLOOD = "D50-D89"  # Blood and blood-forming organs
    ENDOCRINE = "E00-E89"  # Endocrine, nutritional and metabolic
    MENTAL = "F01-F99"  # Mental, behavioral and neurodevelopmental
    NERVOUS = "G00-G99"  # Nervous system
    EYE = "H00-H59"  # Eye and adnexa
    EAR = "H60-H95"  # Ear and mastoid process
    CIRCULATORY = "I00-I99"  # Circulatory system
    RESPIRATORY = "J00-J99"  # Respiratory system
    DIGESTIVE = "K00-K95"  # Digestive system
    SKIN = "L00-L99"  # Skin and subcutaneous tissue
    MUSCULOSKELETAL = "M00-M99"  # Musculoskeletal and connective tissue
    GENITOURINARY = "N00-N99"  # Genitourinary system
    PREGNANCY = "O00-O9A"  # Pregnancy, childbirth and puerperium
    PERINATAL = "P00-P96"  # Certain conditions originating in perinatal period
    CONGENITAL = "Q00-Q99"  # Congenital malformations
    SYMPTOMS = "R00-R99"  # Symptoms not elsewhere classified
    INJURY = "S00-T88"  # Injury, poisoning and external causes
    EXTERNAL = "V00-Y99"  # External causes of morbidity
    FACTORS = "Z00-Z99"  # Factors influencing health status


class ICD10Code:
    """Represents an ICD-10 code with its properties."""

    def __init__(
        self,
        code: str,
        description: str,
        category: Optional[str] = None,
        parent_code: Optional[str] = None,
        is_billable: bool = True,
        inclusion_terms: Optional[List[str]] = None,
        exclusion_notes: Optional[List[str]] = None,
        code_first: Optional[List[str]] = None,
        use_additional: Optional[List[str]] = None,
    ):
        """Initialize ICD-10 code.

        Args:
            code: ICD-10 code
            description: Code description
            category: Major category
            parent_code: Parent code in hierarchy
            is_billable: Whether code is billable
            inclusion_terms: Terms included in this code
            exclusion_notes: Conditions excluded from this code
            code_first: Codes that should be coded first
            use_additional: Additional codes to use
        """
        self.code = self._normalize_code(code)
        self.description = description
        self.category = category
        self.parent_code = parent_code
        self.is_billable = is_billable
        self.inclusion_terms = inclusion_terms or []
        self.exclusion_notes = exclusion_notes or []
        self.code_first = code_first or []
        self.use_additional = use_additional or []
        self.children: List[str] = []
        self.laterality: Optional[str] = None
        self._extract_laterality()

    def _normalize_code(self, code: str) -> str:
        """Normalize ICD-10 code format."""
        # Remove dots and spaces
        normalized = code.replace(".", "").replace(" ", "").upper()

        # Add decimal point after 3rd character if applicable
        if len(normalized) > 3:
            normalized = f"{normalized[:3]}.{normalized[3:]}"

        return normalized

    def _extract_laterality(self) -> None:
        """Extract laterality from code if present."""
        if len(self.code) >= 7:
            last_char = self.code[-1]
            if last_char == "1":
                self.laterality = "right"
            elif last_char == "2":
                self.laterality = "left"
            elif last_char == "3":
                self.laterality = "bilateral"
            elif last_char == "9":
                self.laterality = "unspecified"

    def is_valid(self) -> bool:
        """Check if code format is valid."""
        # Basic format validation
        pattern = r"^[A-Z]\d{2}(\.\d{1,4})?$"
        return bool(re.match(pattern, self.code))

    def get_category_code(self) -> str:
        """Get the 3-character category code."""
        return self.code[:3]

    def get_subcategory_code(self) -> Optional[str]:
        """Get the subcategory code if present."""
        if len(self.code) > 3:
            return self.code[:5]
        return None

    def is_placeholder(self) -> bool:
        """Check if this is a placeholder 'X' code."""
        return "X" in self.code


class ICD10Repository:
    """Repository for managing ICD-10 codes."""

    def __init__(self) -> None:
        """Initialize ICD-10 repository."""
        self.codes: Dict[str, ICD10Code] = {}
        self.category_index: Dict[str, List[str]] = {}
        self.description_index: Dict[str, List[str]] = {}
        self.billable_codes: Set[str] = set()
        self.code_hierarchy: Dict[str, List[str]] = {}
        self._initialize_common_codes()

    def _initialize_common_codes(self) -> None:
        """Initialize common ICD-10 codes for refugee health."""
        # Infectious diseases common in refugee populations
        self.add_code(
            ICD10Code(
                "A15.0",
                "Tuberculosis of lung",
                ICD10Category.INFECTIOUS.value,
                parent_code="A15",
                inclusion_terms=["Tuberculous bronchiectasis", "Tuberculous pneumonia"],
            )
        )

        self.add_code(
            ICD10Code(
                "B54",
                "Unspecified malaria",
                ICD10Category.INFECTIOUS.value,
                inclusion_terms=[
                    "Clinically diagnosed malaria without parasitological confirmation"
                ],
            )
        )

        # Nutritional conditions
        self.add_code(
            ICD10Code(
                "E43",
                "Unspecified severe protein-calorie malnutrition",
                ICD10Category.ENDOCRINE.value,
                inclusion_terms=[
                    "Severe malnutrition NOS",
                    "Severe protein-energy malnutrition",
                ],
            )
        )

        self.add_code(
            ICD10Code(
                "E44.0",
                "Moderate protein-calorie malnutrition",
                ICD10Category.ENDOCRINE.value,
                parent_code="E44",
            )
        )

        # Mental health conditions
        self.add_code(
            ICD10Code(
                "F43.10",
                "Post-traumatic stress disorder, unspecified",
                ICD10Category.MENTAL.value,
                parent_code="F43.1",
                inclusion_terms=["PTSD"],
            )
        )

        # Pregnancy-related
        self.add_code(
            ICD10Code(
                "Z33.1",
                "Pregnant state, incidental",
                ICD10Category.FACTORS.value,
                parent_code="Z33",
                inclusion_terms=["Pregnant NOS"],
            )
        )

    def add_code(self, code: ICD10Code) -> None:
        """Add an ICD-10 code to the repository.

        Args:
            code: ICD10Code object to add
        """
        if not code.is_valid():
            raise ValueError(f"Invalid ICD-10 code format: {code.code}")

        self.codes[code.code] = code

        # Update indexes
        category = code.get_category_code()
        if category not in self.category_index:
            self.category_index[category] = []
        self.category_index[category].append(code.code)

        # Update description index (tokenized for search)
        tokens = code.description.lower().split()
        for token in tokens:
            if len(token) > 2:  # Ignore very short words
                if token not in self.description_index:
                    self.description_index[token] = []
                self.description_index[token].append(code.code)

        # Update billable codes set
        if code.is_billable:
            self.billable_codes.add(code.code)

        # Update hierarchy
        if code.parent_code:
            if code.parent_code not in self.code_hierarchy:
                self.code_hierarchy[code.parent_code] = []
            self.code_hierarchy[code.parent_code].append(code.code)

            # Update parent's children list
            if code.parent_code in self.codes:
                self.codes[code.parent_code].children.append(code.code)

    def get_code(self, code: str) -> Optional[ICD10Code]:
        """Get an ICD-10 code by its code value.

        Args:
            code: ICD-10 code to retrieve

        Returns:
            ICD10Code object or None
        """
        normalized = self._normalize_code(code)
        return self.codes.get(normalized)

    def _normalize_code(self, code: str) -> str:
        """Normalize ICD-10 code format."""
        return code.strip().upper().replace(".", "")

    def search_by_description(self, search_term: str) -> List[ICD10Code]:
        """Search for ICD-10 codes by description.

        Args:
            search_term: Term to search for

        Returns:
            List of matching ICD10Code objects
        """
        search_tokens = search_term.lower().split()
        matching_codes = set()

        for token in search_tokens:
            if token in self.description_index:
                matching_codes.update(self.description_index[token])

        # Return codes sorted by relevance (number of matching tokens)
        results = []
        for code_str in matching_codes:
            code = self.codes[code_str]
            relevance = sum(
                1 for token in search_tokens if token in code.description.lower()
            )
            results.append((relevance, code))

        results.sort(key=lambda x: x[0], reverse=True)
        return [code for _, code in results]

    def get_category_codes(self, category: str) -> List[ICD10Code]:
        """Get all codes in a category.

        Args:
            category: Category code (e.g., "A15")

        Returns:
            List of ICD10Code objects in the category
        """
        code_list = self.category_index.get(category, [])
        return [self.codes[code] for code in code_list]

    def get_children(self, parent_code: str) -> List[ICD10Code]:
        """Get all child codes of a parent code.

        Args:
            parent_code: Parent ICD-10 code

        Returns:
            List of child ICD10Code objects
        """
        children_codes = self.code_hierarchy.get(parent_code, [])
        return [self.codes[code] for code in children_codes]

    def validate_code_sequence(self, codes: List[str]) -> Tuple[bool, List[str]]:
        """Validate a sequence of ICD-10 codes for proper sequencing.

        Args:
            codes: List of ICD-10 codes to validate

        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []

        for i, code_str in enumerate(codes):
            code = self.get_code(code_str)

            if not code:
                errors.append(f"Code {code_str} not found")
                continue

            # Check code_first requirements
            for required_first in code.code_first:
                if required_first not in codes[:i]:
                    errors.append(
                        f"Code {required_first} must be coded before {code_str}"
                    )

            # Check if additional codes are needed
            if code.use_additional and i == len(codes) - 1:
                errors.append(
                    f"Code {code_str} requires additional codes: {', '.join(code.use_additional)}"
                )

        return len(errors) == 0, errors


class ICD10Mapper:
    """Maps between ICD-10 and other coding systems."""

    def __init__(self) -> None:
        """Initialize ICD-10 mapper."""
        self.icd10_to_snomed: Dict[str, str] = {}
        self.snomed_to_icd10: Dict[str, str] = {}
        self._initialize_mappings()

    def _initialize_mappings(self) -> None:
        """Initialize common mappings."""
        # Example mappings (in production, these would be loaded from files)
        mappings = [
            ("A15.0", "154283005"),  # TB of lung -> TB of lung SNOMED
            ("B54", "61462000"),  # Malaria -> Malaria SNOMED
            ("E43", "70241007"),  # Severe malnutrition -> Severe malnutrition SNOMED
            ("F43.10", "47505003"),  # PTSD -> PTSD SNOMED
        ]

        for icd10, snomed in mappings:
            self.icd10_to_snomed[icd10] = snomed
            self.snomed_to_icd10[snomed] = icd10

    def map_to_snomed(self, icd10_code: str) -> Optional[str]:
        """Map ICD-10 code to SNOMED CT.

        Args:
            icd10_code: ICD-10 code

        Returns:
            SNOMED CT code or None
        """
        return self.icd10_to_snomed.get(icd10_code)

    def map_from_snomed(self, snomed_code: str) -> Optional[str]:
        """Map SNOMED CT code to ICD-10.

        Args:
            snomed_code: SNOMED CT code

        Returns:
            ICD-10 code or None
        """
        return self.snomed_to_icd10.get(snomed_code)


class ICD10Validator:
    """Validates ICD-10 codes and coding practices."""

    @staticmethod
    def validate_format(code: str) -> Tuple[bool, Optional[str]]:
        """Validate ICD-10 code format.

        Args:
            code: ICD-10 code to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Remove any whitespace
        code = code.strip()

        # Check basic format
        if not re.match(r"^[A-Z]\d{2}(\.\d{1,4})?$", code):
            return (
                False,
                "Invalid format. Expected: Letter + 2 digits + optional decimal extension",
            )

        # Check length
        if len(code.replace(".", "")) > 7:
            return False, "Code too long. Maximum 7 characters (excluding decimal)"

        return True, None

    @staticmethod
    def validate_laterality(
        code: str, laterality: Optional[str]
    ) -> Tuple[bool, Optional[str]]:
        """Validate laterality specification.

        Args:
            code: ICD-10 code
            laterality: Specified laterality

        Returns:
            Tuple of (is_valid, error_message)
        """
        if len(code) < 7:
            return True, None  # No laterality required

        last_char = code[-1]

        if last_char in ["1", "2", "3", "9"]:
            if not laterality:
                return False, "Laterality must be specified for this code"

            expected_laterality = {
                "1": "right",
                "2": "left",
                "3": "bilateral",
                "9": "unspecified",
            }

            if laterality != expected_laterality.get(last_char):
                return (
                    False,
                    f"Laterality mismatch. Code indicates {expected_laterality.get(last_char)}",
                )

        return True, None


# Create global repository instance
icd10_repository = ICD10Repository()
icd10_mapper = ICD10Mapper()
icd10_validator = ICD10Validator()
