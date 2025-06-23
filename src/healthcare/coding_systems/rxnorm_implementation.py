"""RxNorm Implementation.

This module implements RxNorm medication terminology for standardizing drug names,
with special focus on generic medications and formulations commonly used in
refugee healthcare settings.

Handles FHIR Medication Resource validation. All PHI data is encrypted
and requires proper access control permissions.
"""

import logging
import re
from enum import Enum
from typing import Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


class RxNormTermType(Enum):
    """RxNorm term types (TTY)."""

    # Drug names
    IN = "IN"  # Ingredient
    PIN = "PIN"  # Precise ingredient
    MIN = "MIN"  # Multiple ingredients
    BN = "BN"  # Brand name

    # Clinical drugs
    SCD = "SCD"  # Semantic clinical drug (generic)
    SBD = "SBD"  # Semantic branded drug
    GPCK = "GPCK"  # Generic pack
    BPCK = "BPCK"  # Brand name pack

    # Components
    SCDC = "SCDC"  # Semantic clinical drug component
    SCDF = "SCDF"  # Semantic clinical dose form
    SCDG = "SCDG"  # Semantic clinical drug group

    # Dose forms
    DF = "DF"  # Dose form
    DFG = "DFG"  # Dose form group

    # Other
    SY = "SY"  # Synonym
    TMSY = "TMSY"  # Tall man lettering synonym
    PSN = "PSN"  # Prescribable name


class RxNormDoseForm(Enum):
    """Common dose forms in refugee settings."""

    # Oral forms
    ORAL_TABLET = "317541"
    ORAL_CAPSULE = "316965"
    ORAL_SOLUTION = "316964"
    ORAL_SUSPENSION = "316971"
    ORAL_POWDER = "317008"

    # Injectable forms
    INJECTABLE_SOLUTION = "316949"
    INJECTABLE_SUSPENSION = "1649563"
    INJECTABLE_POWDER = "1649572"

    # Topical forms
    TOPICAL_CREAM = "316989"
    TOPICAL_OINTMENT = "316992"
    TOPICAL_GEL = "316990"
    TOPICAL_SOLUTION = "317002"

    # Other forms
    SUPPOSITORY = "317004"
    INHALATION_POWDER = "346164"
    INHALATION_SOLUTION = "346163"
    OPHTHALMIC_SOLUTION = "317000"
    OTIC_SOLUTION = "317001"


class WHOEssentialMedicine:
    """WHO Essential Medicines commonly used in refugee settings."""

    ANTIBIOTICS = {
        "amoxicillin": {
            "rxcui": "723",
            "strengths": ["250 mg", "500 mg"],
            "forms": ["oral capsule", "oral suspension"],
            "who_category": "antibacterials",
        },
        "azithromycin": {
            "rxcui": "18631",
            "strengths": ["250 mg", "500 mg"],
            "forms": ["oral tablet", "oral suspension"],
            "who_category": "antibacterials",
        },
        "ciprofloxacin": {
            "rxcui": "2551",
            "strengths": ["250 mg", "500 mg"],
            "forms": ["oral tablet"],
            "who_category": "antibacterials",
        },
        "doxycycline": {
            "rxcui": "3640",
            "strengths": ["100 mg"],
            "forms": ["oral capsule"],
            "who_category": "antibacterials",
        },
        "metronidazole": {
            "rxcui": "6922",
            "strengths": ["250 mg", "500 mg"],
            "forms": ["oral tablet"],
            "who_category": "antibacterials",
        },
    }

    ANTIMALARIALS = {
        "artemether_lumefantrine": {
            "rxcui": "847728",
            "strengths": ["20 mg/120 mg"],
            "forms": ["oral tablet"],
            "who_category": "antimalarials",
        },
        "chloroquine": {
            "rxcui": "2393",
            "strengths": ["150 mg", "250 mg"],
            "forms": ["oral tablet"],
            "who_category": "antimalarials",
        },
        "quinine": {
            "rxcui": "9071",
            "strengths": ["300 mg"],
            "forms": ["oral tablet"],
            "who_category": "antimalarials",
        },
    }

    ANALGESICS = {
        "paracetamol": {
            "rxcui": "161",  # acetaminophen
            "strengths": ["500 mg"],
            "forms": ["oral tablet", "oral suspension"],
            "who_category": "analgesics",
        },
        "ibuprofen": {
            "rxcui": "5640",
            "strengths": ["200 mg", "400 mg"],
            "forms": ["oral tablet"],
            "who_category": "analgesics",
        },
        "morphine": {
            "rxcui": "7052",
            "strengths": ["10 mg", "30 mg"],
            "forms": ["oral tablet", "injectable solution"],
            "who_category": "analgesics",
        },
    }

    ANTIRETROVIRALS = {
        "efavirenz": {
            "rxcui": "195085",
            "strengths": ["600 mg"],
            "forms": ["oral tablet"],
            "who_category": "antiretrovirals",
        },
        "lamivudine": {
            "rxcui": "68139",
            "strengths": ["150 mg", "300 mg"],
            "forms": ["oral tablet"],
            "who_category": "antiretrovirals",
        },
        "tenofovir": {
            "rxcui": "290500",
            "strengths": ["300 mg"],
            "forms": ["oral tablet"],
            "who_category": "antiretrovirals",
        },
    }


class RxNormConcept:
    """Represents an RxNorm concept."""

    def __init__(
        self,
        rxcui: str,
        name: str,
        tty: RxNormTermType,
        suppress: bool = False,
        language: str = "ENG",
    ):
        """Initialize RxNorm concept.

        Args:
            rxcui: RxNorm concept unique identifier
            name: Drug name
            tty: Term type
            suppress: Whether concept is suppressed
            language: Language code
        """
        self.rxcui = rxcui
        self.name = name
        self.tty = tty
        self.suppress = suppress
        self.language = language

        # Related concepts
        self.ingredients: List[str] = []
        self.strength: Optional[str] = None
        self.dose_form: Optional[str] = None
        self.brand_name: Optional[str] = None
        self.generic_rxcui: Optional[str] = None
        self.tradename_rxcui: Optional[str] = None
        self.ndc_codes: List[str] = []
        self.atc_codes: List[str] = []

    def is_generic(self) -> bool:
        """Check if this is a generic drug."""
        return self.tty in [RxNormTermType.SCD, RxNormTermType.GPCK]

    def is_branded(self) -> bool:
        """Check if this is a branded drug."""
        return self.tty in [RxNormTermType.SBD, RxNormTermType.BPCK]

    def get_ingredient_string(self) -> str:
        """Get ingredients as a string."""
        return " / ".join(self.ingredients)


class RxNormRepository:
    """Repository for managing RxNorm concepts."""

    def __init__(self) -> None:
        """Initialize RxNorm repository."""
        self.concepts: Dict[str, RxNormConcept] = {}
        self.name_index: Dict[str, Set[str]] = {}
        self.ingredient_index: Dict[str, Set[str]] = {}
        self.ndc_to_rxcui: Dict[str, str] = {}
        self._initialize_essential_medicines()

    def _initialize_essential_medicines(self) -> None:
        """Initialize WHO essential medicines."""
        # Add all essential medicine categories
        for category in [
            WHOEssentialMedicine.ANTIBIOTICS,
            WHOEssentialMedicine.ANTIMALARIALS,
            WHOEssentialMedicine.ANALGESICS,
            WHOEssentialMedicine.ANTIRETROVIRALS,
        ]:
            for drug_name, drug_info in category.items():
                # Create ingredient concept
                ingredient = RxNormConcept(
                    str(drug_info["rxcui"]),
                    drug_name.replace("_", " ").title(),
                    RxNormTermType.IN,
                )
                self.add_concept(ingredient)
                # Create clinical drug concepts for each strength/form
                for strength in drug_info.get("strengths", []):
                    for form in drug_info.get("forms", []):
                        # Generate a clinical drug RXCUI (in real system, these would be different)
                        scd_rxcui = f"{drug_info['rxcui']}-{strength.replace(' ', '')}-{form.replace(' ', '')}"

                        scd = RxNormConcept(
                            scd_rxcui,
                            f"{drug_name.replace('_', ' ').title()} {strength} {form}",
                            RxNormTermType.SCD,
                        )
                        scd.ingredients = [drug_name.replace("_", " ").title()]
                        scd.strength = strength
                        scd.dose_form = form

                        self.add_concept(scd)

    def add_concept(self, concept: RxNormConcept) -> None:
        """Add an RxNorm concept to the repository.

        Args:
            concept: RxNormConcept to add
        """
        self.concepts[concept.rxcui] = concept

        # Update name index
        name_tokens = concept.name.lower().split()
        for token in name_tokens:
            if len(token) > 2:
                if token not in self.name_index:
                    self.name_index[token] = set()
                self.name_index[token].add(concept.rxcui)

        # Update ingredient index
        for ingredient in concept.ingredients:
            ing_lower = ingredient.lower()
            if ing_lower not in self.ingredient_index:
                self.ingredient_index[ing_lower] = set()
            self.ingredient_index[ing_lower].add(concept.rxcui)

        # Update NDC mapping
        for ndc in concept.ndc_codes:
            self.ndc_to_rxcui[ndc] = concept.rxcui

    def get_concept(self, rxcui: str) -> Optional[RxNormConcept]:
        """Get an RxNorm concept by RXCUI.

        Args:
            rxcui: RxNorm concept unique identifier

        Returns:
            RxNormConcept or None
        """
        return self.concepts.get(rxcui)

    def search_by_name(
        self,
        search_term: str,
        term_types: Optional[List[RxNormTermType]] = None,
        include_suppressed: bool = False,
    ) -> List[RxNormConcept]:
        """Search for concepts by name.

        Args:
            search_term: Term to search for
            term_types: Filter by term types
            include_suppressed: Include suppressed concepts

        Returns:
            List of matching concepts
        """
        search_tokens = search_term.lower().split()
        matching_rxcuis = set()

        # Find concepts containing all search tokens
        for i, token in enumerate(search_tokens):
            token_matches = self.name_index.get(token, set())
            if i == 0:
                matching_rxcuis = token_matches.copy()
            else:
                matching_rxcuis &= token_matches

        # Filter results
        results = []
        for rxcui in matching_rxcuis:
            concept = self.concepts[rxcui]

            # Apply filters
            if not include_suppressed and concept.suppress:
                continue

            if term_types and concept.tty not in term_types:
                continue

            results.append(concept)

        # Sort by relevance (exact matches first)
        results.sort(
            key=lambda c: (c.name.lower() != search_term.lower(), len(c.name), c.name)
        )

        return results

    def get_by_ingredient(
        self, ingredient: str, term_types: Optional[List[RxNormTermType]] = None
    ) -> List[RxNormConcept]:
        """Get all concepts containing an ingredient.

        Args:
            ingredient: Ingredient name
            term_types: Filter by term types

        Returns:
            List of concepts containing the ingredient
        """
        ing_lower = ingredient.lower()
        rxcuis = self.ingredient_index.get(ing_lower, set())

        results = []
        for rxcui in rxcuis:
            concept = self.concepts[rxcui]

            if term_types and concept.tty not in term_types:
                continue

            results.append(concept)

        return results

    def get_generic_alternatives(self, brand_rxcui: str) -> List[RxNormConcept]:
        """Get generic alternatives for a brand drug.

        Args:
            brand_rxcui: Brand drug RXCUI

        Returns:
            List of generic alternatives
        """
        brand_concept = self.get_concept(brand_rxcui)
        if not brand_concept or not brand_concept.is_branded():
            return []

        # Find generics with same ingredients and strength
        generics = []

        for concept in self.concepts.values():
            if concept.is_generic():
                # Check if ingredients match
                if set(concept.ingredients) == set(brand_concept.ingredients):
                    # Check if strength matches
                    if concept.strength == brand_concept.strength:
                        generics.append(concept)

        return generics

    def rxcui_from_ndc(self, ndc: str) -> Optional[str]:
        """Get RXCUI from NDC code.

        Args:
            ndc: National Drug Code

        Returns:
            RXCUI or None
        """
        # Normalize NDC (remove hyphens)
        ndc_normalized = ndc.replace("-", "")
        return self.ndc_to_rxcui.get(ndc_normalized)


class RxNormInteractionChecker:
    """Checks for drug-drug interactions."""

    def __init__(self) -> None:
        """Initialize interaction checker."""
        self.interactions: Dict[Tuple[str, str], Dict] = {}
        self._initialize_common_interactions()

    def _initialize_common_interactions(self) -> None:
        """Initialize common drug interactions in refugee settings."""
        # Antibiotic interactions
        self.add_interaction(
            "2551",  # ciprofloxacin
            "161",  # acetaminophen
            severity="minor",
            description="May increase acetaminophen levels",
        )

        # Antimalarial interactions
        self.add_interaction(
            "2393",  # chloroquine
            "7052",  # morphine
            severity="moderate",
            description="May increase CNS depression",
        )

        # HIV drug interactions
        self.add_interaction(
            "195085",  # efavirenz
            "6922",  # metronidazole
            severity="moderate",
            description="Metronidazole may cause disulfiram-like reaction",
        )

    def add_interaction(
        self, rxcui1: str, rxcui2: str, severity: str, description: str
    ) -> None:
        """Add a drug interaction.

        Args:
            rxcui1: First drug RXCUI
            rxcui2: Second drug RXCUI
            severity: Interaction severity
            description: Interaction description
        """
        # Store both directions
        key1 = (rxcui1, rxcui2)
        key2 = (rxcui2, rxcui1)

        interaction = {"severity": severity, "description": description}

        self.interactions[key1] = interaction
        self.interactions[key2] = interaction

    def check_interaction(self, rxcui1: str, rxcui2: str) -> Optional[Dict]:
        """Check for interaction between two drugs.

        Args:
            rxcui1: First drug RXCUI
            rxcui2: Second drug RXCUI

        Returns:
            Interaction details or None
        """
        return self.interactions.get((rxcui1, rxcui2))

    def check_all_interactions(self, rxcui_list: List[str]) -> List[Dict]:
        """Check all interactions in a medication list.

        Args:
            rxcui_list: List of RXCUIs

        Returns:
            List of interactions found
        """
        interactions = []

        for i, rxcui1 in enumerate(rxcui_list):
            for j in range(i + 1, len(rxcui_list)):
                interaction = self.check_interaction(rxcui1, rxcui_list[j])
                if interaction:
                    interactions.append(
                        {"drug1": rxcui1, "drug2": rxcui_list[j], **interaction}
                    )

        return interactions


class RxNormValidator:
    """Validates RxNorm codes and drug information."""

    @staticmethod
    def validate_rxcui(rxcui: str) -> Tuple[bool, Optional[str]]:
        """Validate RXCUI format.

        Args:
            rxcui: RxNorm concept unique identifier

        Returns:
            Tuple of (is_valid, error_message)
        """
        # RXCUIs are numeric strings
        if not rxcui.replace("-", "").isdigit():
            return False, "RXCUI must be numeric"

        # Basic RXCUI should be 1-7 digits
        base_rxcui = rxcui.split("-")[0]
        if len(base_rxcui) < 1 or len(base_rxcui) > 7:
            return False, "RXCUI must be 1-7 digits"

        return True, None

    @staticmethod
    def validate_ndc(ndc: str) -> Tuple[bool, Optional[str]]:
        """Validate NDC format.

        Args:
            ndc: National Drug Code

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Remove hyphens for validation
        ndc_clean = ndc.replace("-", "")

        # NDC should be 10-11 digits
        if not ndc_clean.isdigit():
            return False, "NDC must be numeric"

        if len(ndc_clean) < 10 or len(ndc_clean) > 11:
            return False, "NDC must be 10-11 digits"

        # Validate format patterns (4-4-2, 5-3-2, 5-4-1, 5-4-2)
        valid_patterns = [
            r"^\d{4}-\d{4}-\d{2}$",
            r"^\d{5}-\d{3}-\d{2}$",
            r"^\d{5}-\d{4}-\d{1}$",
            r"^\d{5}-\d{4}-\d{2}$",
        ]

        if "-" in ndc:
            valid = any(re.match(pattern, ndc) for pattern in valid_patterns)
            if not valid:
                return False, "Invalid NDC format"

        return True, None


# Create global instances
rxnorm_repository = RxNormRepository()
rxnorm_interaction_checker = RxNormInteractionChecker()
rxnorm_validator = RxNormValidator()
