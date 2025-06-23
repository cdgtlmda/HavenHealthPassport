"""
Inclusive language support for gender-aware translation.

This module provides support for inclusive and non-binary language options,
including custom pronoun sets and gender-neutral alternatives.
"""

import logging
import re
from dataclasses import dataclass
from typing import Dict, List, Optional

from ..config import Language
from .core import Gender, GenderAdaptationResult, GenderAdapter

logger = logging.getLogger(__name__)


@dataclass
class PronounSet:
    """A complete set of pronouns for a person."""

    subject: str  # they
    object: str  # them
    possessive_determiner: str  # their
    possessive_pronoun: str  # theirs
    reflexive: str  # themself

    @classmethod
    def from_string(cls, pronoun_string: str) -> "PronounSet":
        """Create PronounSet from string like 'they/them'."""
        parts = pronoun_string.lower().split("/")
        if len(parts) >= 2:
            subject = parts[0].strip()
            _ = parts[1].strip()  # Object form not used in current implementation

            # Infer other forms
            if subject == "they":
                return cls(
                    subject="they",
                    object="them",
                    possessive_determiner="their",
                    possessive_pronoun="theirs",
                    reflexive="themself",
                )
            elif subject == "she":
                return cls(
                    subject="she",
                    object="her",
                    possessive_determiner="her",
                    possessive_pronoun="hers",
                    reflexive="herself",
                )
            elif subject == "he":
                return cls(
                    subject="he",
                    object="him",
                    possessive_determiner="his",
                    possessive_pronoun="his",
                    reflexive="himself",
                )
            elif subject == "ze":
                return cls(
                    subject="ze",
                    object="zir",
                    possessive_determiner="zir",
                    possessive_pronoun="zirs",
                    reflexive="zirself",
                )
            elif subject == "xe":
                return cls(
                    subject="xe",
                    object="xem",
                    possessive_determiner="xyr",
                    possessive_pronoun="xyrs",
                    reflexive="xemself",
                )

        # Default to they/them
        return cls(
            subject="they",
            object="them",
            possessive_determiner="their",
            possessive_pronoun="theirs",
            reflexive="themself",
        )


@dataclass
class InclusiveOptions:
    """Options for inclusive language adaptation."""

    use_neutral_pronouns: bool = True
    avoid_binary_terms: bool = True
    use_person_first: bool = True  # "person with autism" vs "autistic person"
    include_all_genders: bool = True
    respect_neopronouns: bool = True
    cultural_sensitivity: bool = True
    medical_accuracy: bool = True  # Maintain medical accuracy over inclusivity


class InclusiveLanguageAdapter:
    """Adapter for inclusive and non-binary language."""

    def __init__(self, base_adapter: Optional[GenderAdapter] = None):
        """
        Initialize inclusive language adapter.

        Args:
            base_adapter: Base gender adapter to use
        """
        self.base_adapter = base_adapter or GenderAdapter()
        self.pronoun_sets = self._load_pronoun_sets()
        self.inclusive_alternatives = self._load_inclusive_alternatives()
        self.binary_terms = self._load_binary_terms()

    def make_inclusive(
        self,
        text: str,
        language: Language,
        options: Optional[InclusiveOptions] = None,
        custom_pronouns: Optional[PronounSet] = None,
    ) -> GenderAdaptationResult:
        """
        Make text more inclusive and gender-neutral.

        Args:
            text: Text to make inclusive
            language: Language of the text
            options: Inclusive language options
            custom_pronouns: Custom pronoun set to use

        Returns:
            GenderAdaptationResult with inclusive text
        """
        options = options or InclusiveOptions()
        adapted_text = text
        modifications = []

        # Replace binary terms if requested
        if options.avoid_binary_terms:
            for binary, inclusive in self.binary_terms.items():
                if binary in adapted_text.lower():
                    pattern = rf"\b{re.escape(binary)}\b"
                    adapted_text = re.sub(pattern, inclusive, adapted_text, flags=re.I)
                    modifications.append((binary, inclusive))

        # Apply custom pronouns if provided
        if custom_pronouns:
            adapted_text = self._apply_custom_pronouns(adapted_text, custom_pronouns)

        # Use neutral pronouns for generic references
        elif options.use_neutral_pronouns:
            result = self.base_adapter.adapt(adapted_text, Gender.NEUTRAL, language)
            adapted_text = result.adapted_text
            modifications.extend(result.modifications)

        # Apply inclusive alternatives
        for exclusive, inclusive in self.inclusive_alternatives.get(
            language, {}
        ).items():
            if exclusive in adapted_text:
                adapted_text = adapted_text.replace(exclusive, inclusive)
                modifications.append((exclusive, inclusive))

        # Use person-first language if requested
        if options.use_person_first:
            adapted_text = self._apply_person_first(adapted_text, language)

        return GenderAdaptationResult(
            adapted_text=adapted_text,
            source_gender=Gender.UNKNOWN,
            target_gender=Gender.NEUTRAL,
            modifications=modifications,
            confidence=0.9,
        )

    def _apply_custom_pronouns(self, text: str, pronouns: PronounSet) -> str:
        """Apply custom pronoun set to text."""
        # Replace common pronoun patterns
        replacements = [
            (r"\b(he|she|they)\b", pronouns.subject),
            (r"\b(him|her|them)\b", pronouns.object),
            (r"\b(his|her|their)\b", pronouns.possessive_determiner),
            (r"\b(his|hers|theirs)\b", pronouns.possessive_pronoun),
            (r"\b(himself|herself|themself)\b", pronouns.reflexive),
        ]

        adapted_text = text
        for pattern, replacement in replacements:
            adapted_text = re.sub(pattern, replacement, adapted_text, flags=re.I)

        return adapted_text

    def _apply_person_first(self, text: str, language: Language) -> str:
        """Apply person-first language."""
        if language == Language.ENGLISH:
            # Convert identity-first to person-first
            replacements = {
                "autistic person": "person with autism",
                "disabled person": "person with disabilities",
                "diabetic patient": "patient with diabetes",
                "schizophrenic patient": "patient with schizophrenia",
            }

            adapted_text = text
            for identity_first, person_first in replacements.items():
                adapted_text = adapted_text.replace(identity_first, person_first)

            return adapted_text

        return text

    def _load_pronoun_sets(self) -> Dict[str, PronounSet]:
        """Load common pronoun sets."""
        return {
            "they/them": PronounSet(
                subject="they",
                object="them",
                possessive_determiner="their",
                possessive_pronoun="theirs",
                reflexive="themself",
            ),
            "ze/zir": PronounSet(
                subject="ze",
                object="zir",
                possessive_determiner="zir",
                possessive_pronoun="zirs",
                reflexive="zirself",
            ),
            "xe/xem": PronounSet(
                subject="xe",
                object="xem",
                possessive_determiner="xyr",
                possessive_pronoun="xyrs",
                reflexive="xemself",
            ),
        }

    def _load_inclusive_alternatives(self) -> Dict[Language, Dict[str, str]]:
        """Load inclusive language alternatives."""
        return {
            Language.ENGLISH: {
                "ladies and gentlemen": "everyone",
                "boys and girls": "children",
                "brothers and sisters": "siblings",
                "mother and father": "parents",
                "husband and wife": "spouses",
                "boyfriend or girlfriend": "partner",
                "men and women": "people",
                "male or female": "all genders",
                "sir or madam": "dear guest",
            },
            Language.SPANISH: {
                "todos y todas": "todes",
                "niños y niñas": "niñes",
                "amigos y amigas": "amigues",
                "ellos y ellas": "elles",
                "señores y señoras": "personas",
            },
            Language.FRENCH: {
                "tous et toutes": "toustes",
                "ceux et celles": "celleux",
                "ils et elles": "iels",
                "messieurs et mesdames": "tout le monde",
            },
        }

    def _load_binary_terms(self) -> Dict[str, str]:
        """Load binary terms and their inclusive alternatives."""
        return {
            "both genders": "all genders",
            "opposite sex": "another gender",
            "same sex": "same gender",
            "gender binary": "gender spectrum",
            "biological sex": "sex assigned at birth",
        }


def get_inclusive_alternatives(term: str, language: Language) -> List[str]:
    """
    Get inclusive alternatives for a gendered term.

    Args:
        term: Gendered term
        language: Language

    Returns:
        List of inclusive alternatives
    """
    adapter = InclusiveLanguageAdapter()
    alternatives = []

    # Check direct alternatives
    lang_alternatives = adapter.inclusive_alternatives.get(language, {})
    if term.lower() in lang_alternatives:
        alternatives.append(lang_alternatives[term.lower()])

    # Check binary terms
    if term.lower() in adapter.binary_terms:
        alternatives.append(adapter.binary_terms[term.lower()])

    return alternatives


def create_pronoun_set(pronoun_string: str) -> PronounSet:
    """
    Create a pronoun set from a pronoun string.

    Args:
        pronoun_string: String like "they/them" or "ze/zir"

    Returns:
        PronounSet object
    """
    return PronounSet.from_string(pronoun_string)
