"""
Linguistic formality analysis.

This module provides language-specific formality analysis tools for
different linguistic systems (pronouns, honorifics, verb conjugations).
"""

import logging
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from ..config import Language
from .core import FormalityLevel

logger = logging.getLogger(__name__)


@dataclass
class PronounSystem:
    """Pronoun system for a language."""

    language: Language

    # Pronoun categories
    first_person_singular: Dict[str, FormalityLevel] = field(default_factory=dict)
    second_person_singular: Dict[str, FormalityLevel] = field(default_factory=dict)
    third_person_singular: Dict[str, FormalityLevel] = field(default_factory=dict)
    first_person_plural: Dict[str, FormalityLevel] = field(default_factory=dict)
    second_person_plural: Dict[str, FormalityLevel] = field(default_factory=dict)
    third_person_plural: Dict[str, FormalityLevel] = field(default_factory=dict)

    def get_formality_for_pronoun(self, pronoun: str) -> Optional[FormalityLevel]:
        """Get formality level for a specific pronoun."""
        for category in [
            self.first_person_singular,
            self.second_person_singular,
            self.third_person_singular,
            self.first_person_plural,
            self.second_person_plural,
            self.third_person_plural,
        ]:
            if pronoun in category:
                return category[pronoun]
        return None


@dataclass
class HonorificSystem:
    """Honorific system for a language."""

    language: Language

    # Title honorifics
    titles: Dict[str, FormalityLevel] = field(default_factory=dict)
    # Name suffixes (e.g., -san, -sama in Japanese)
    name_suffixes: Dict[str, FormalityLevel] = field(default_factory=dict)
    # Professional titles
    professional_titles: Dict[str, FormalityLevel] = field(default_factory=dict)
    # Family honorifics
    family_honorifics: Dict[str, FormalityLevel] = field(default_factory=dict)

    def get_formality_for_honorific(self, honorific: str) -> Optional[FormalityLevel]:
        """Get formality level for a specific honorific."""
        for category in [
            self.titles,
            self.name_suffixes,
            self.professional_titles,
            self.family_honorifics,
        ]:
            if honorific in category:
                return category[honorific]
        return None


@dataclass
class VerbConjugation:
    """Verb conjugation formality levels."""

    language: Language

    # Conjugation patterns by formality
    formal_patterns: List[str] = field(default_factory=list)
    neutral_patterns: List[str] = field(default_factory=list)
    informal_patterns: List[str] = field(default_factory=list)

    # Specific verb forms
    formal_endings: List[str] = field(default_factory=list)
    informal_endings: List[str] = field(default_factory=list)

    def get_formality_for_verb_form(self, verb_form: str) -> Optional[FormalityLevel]:
        """Determine formality level of a verb form."""
        verb_lower = verb_form.lower()

        # Check endings
        for ending in self.formal_endings:
            if verb_lower.endswith(ending):
                return FormalityLevel.FORMAL

        for ending in self.informal_endings:
            if verb_lower.endswith(ending):
                return FormalityLevel.INFORMAL

        return None


class LinguisticFormalityAnalyzer:
    """Analyzes linguistic features for formality assessment."""

    def __init__(self, language: Language):
        """Initialize analyzer for specific language."""
        self.language = language
        self.pronoun_system = self._load_pronoun_system()
        self.honorific_system = self._load_honorific_system()
        self.verb_conjugation = self._load_verb_conjugation()

    def analyze_pronouns(self, text: str) -> Dict[str, float]:
        """Analyze pronoun usage for formality."""
        if not self.pronoun_system:
            return {}

        pronoun_scores = {}
        words = re.findall(r"\b\w+\b", text.lower())

        for word in words:
            formality = self.pronoun_system.get_formality_for_pronoun(word)
            if formality is not None:
                pronoun_scores[word] = formality.value / 4.0  # Normalize to 0-1

        return pronoun_scores

    def analyze_honorifics(self, text: str) -> Dict[str, float]:
        """Analyze honorific usage for formality."""
        if not self.honorific_system:
            return {}

        honorific_scores = {}

        # Check for honorifics in text
        for honorific_type in [
            self.honorific_system.titles,
            self.honorific_system.name_suffixes,
            self.honorific_system.professional_titles,
        ]:
            for honorific, formality_level in honorific_type.items():
                if honorific in text:
                    honorific_scores[honorific] = formality_level.value / 4.0

        return honorific_scores

    def analyze_verb_forms(self, text: str) -> Dict[str, float]:
        """Analyze verb forms for formality."""
        if not self.verb_conjugation:
            return {}

        verb_scores = {}
        # Extract potential verb forms (language-specific)
        words = re.findall(r"\b\w+\b", text)

        for word in words:
            formality = self.verb_conjugation.get_formality_for_verb_form(word)
            if formality is not None:
                verb_scores[word] = formality.value / 4.0

        return verb_scores

    def _load_pronoun_system(self) -> Optional[PronounSystem]:
        """Load pronoun system for language."""
        systems = {
            Language.SPANISH: PronounSystem(
                language=Language.SPANISH,
                second_person_singular={
                    "tú": FormalityLevel.INFORMAL,
                    "usted": FormalityLevel.FORMAL,
                    "vos": FormalityLevel.INFORMAL,
                },
                second_person_plural={
                    "vosotros": FormalityLevel.INFORMAL,
                    "ustedes": FormalityLevel.NEUTRAL,
                },
            ),
            Language.FRENCH: PronounSystem(
                language=Language.FRENCH,
                second_person_singular={
                    "tu": FormalityLevel.INFORMAL,
                    "vous": FormalityLevel.FORMAL,
                },
                second_person_plural={"vous": FormalityLevel.NEUTRAL},
            ),
            Language.GERMAN: PronounSystem(
                language=Language.GERMAN,
                second_person_singular={
                    "du": FormalityLevel.INFORMAL,
                    "Sie": FormalityLevel.FORMAL,
                },
                second_person_plural={
                    "ihr": FormalityLevel.INFORMAL,
                    "Sie": FormalityLevel.FORMAL,
                },
            ),
        }

        return systems.get(self.language)

    def _load_honorific_system(self) -> Optional[HonorificSystem]:
        """Load honorific system for language."""
        systems = {
            Language.JAPANESE: HonorificSystem(
                language=Language.JAPANESE,
                name_suffixes={
                    "-san": FormalityLevel.NEUTRAL,
                    "-sama": FormalityLevel.VERY_FORMAL,
                    "-kun": FormalityLevel.INFORMAL,
                    "-chan": FormalityLevel.VERY_INFORMAL,
                    "-sensei": FormalityLevel.FORMAL,
                    "-senpai": FormalityLevel.NEUTRAL,
                },
                professional_titles={
                    "先生": FormalityLevel.FORMAL,
                    "医師": FormalityLevel.FORMAL,
                    "博士": FormalityLevel.VERY_FORMAL,
                },
            ),
            Language.KOREAN: HonorificSystem(
                language=Language.KOREAN,
                name_suffixes={
                    "-nim": FormalityLevel.FORMAL,
                    "-ssi": FormalityLevel.NEUTRAL,
                },
                professional_titles={
                    "선생님": FormalityLevel.FORMAL,
                    "의사": FormalityLevel.FORMAL,
                    "박사": FormalityLevel.VERY_FORMAL,
                },
            ),
        }

        return systems.get(self.language)

    def _load_verb_conjugation(self) -> Optional[VerbConjugation]:
        """Load verb conjugation system for language."""
        systems = {
            Language.SPANISH: VerbConjugation(
                language=Language.SPANISH,
                formal_endings=["ría", "ría", "ríamos", "rían"],
                informal_endings=["as", "es", "ás", "és"],
            ),
            Language.JAPANESE: VerbConjugation(
                language=Language.JAPANESE,
                formal_endings=["ます", "です", "ございます"],
                informal_endings=["だ", "だよ", "だね", "よ", "ね"],
            ),
        }

        return systems.get(self.language)
