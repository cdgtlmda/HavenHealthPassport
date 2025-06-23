"""
Gender rules for different languages.

This module contains language-specific rules for gender handling,
including grammatical gender, agreement rules, and cultural conventions.
"""

import logging
import re
from dataclasses import dataclass
from enum import Enum, auto
from typing import Dict, List, Optional

from ..config import Language
from .core import Gender, GenderProfile

logger = logging.getLogger(__name__)


class GrammaticalGender(Enum):
    """Grammatical gender categories."""

    MASCULINE = auto()
    FEMININE = auto()
    NEUTER = auto()
    COMMON = auto()  # Some languages have common gender


@dataclass
class GenderRule:
    """A single gender transformation rule."""

    name: str
    pattern: str  # Regex pattern
    replacements: Dict[Gender, str]  # Gender -> replacement
    rule_type: str  # "pronoun", "noun", "adjective", "verb"
    context_required: Optional[str] = None
    language: Optional[Language] = None

    def apply(self, text: str, target_gender: Gender) -> Optional[str]:
        """Apply rule to text for target gender."""
        if target_gender not in self.replacements:
            return None

        replacement = self.replacements[target_gender]
        if callable(replacement):
            return re.sub(self.pattern, replacement, text, flags=re.I)
        else:
            return re.sub(self.pattern, replacement, text, flags=re.I)


class GenderRuleEngine:
    """Engine for applying gender transformation rules."""

    def __init__(self) -> None:
        """Initialize rule engine."""
        self.rules: Dict[Language, List[GenderRule]] = {}
        self._load_default_rules()

    def apply_rules(
        self,
        text: str,
        language: Language,
        source_gender: Gender,
        target_gender: Gender,
    ) -> str:
        """Apply gender transformation rules."""
        if language not in self.rules:
            return text

        adjusted_text = text
        for rule in self.rules[language]:
            if rule.rule_type == "pronoun" or source_gender in rule.replacements:
                result = rule.apply(adjusted_text, target_gender)
                if result:
                    adjusted_text = result

        return adjusted_text

    def add_rule(self, rule: GenderRule) -> None:
        """Add a rule to the engine."""
        language = rule.language or Language.ENGLISH
        if language not in self.rules:
            self.rules[language] = []
        self.rules[language].append(rule)

    def _load_default_rules(self) -> None:
        """Load default rules for each language."""
        self._load_english_rules()
        self._load_spanish_rules()
        self._load_french_rules()

    def _load_english_rules(self) -> None:
        """Load English gender rules."""
        english_rules = [
            # Subject pronouns
            GenderRule(
                name="subject_pronouns",
                pattern=r"\b(he|she|they)\b",
                replacements={
                    Gender.MASCULINE: "he",
                    Gender.FEMININE: "she",
                    Gender.NEUTRAL: "they",
                },
                rule_type="pronoun",
                language=Language.ENGLISH,
            ),
            # Object pronouns
            GenderRule(
                name="object_pronouns",
                pattern=r"\b(him|her|them)\b",
                replacements={
                    Gender.MASCULINE: "him",
                    Gender.FEMININE: "her",
                    Gender.NEUTRAL: "them",
                },
                rule_type="pronoun",
                language=Language.ENGLISH,
            ),
            # Possessive pronouns
            GenderRule(
                name="possessive_pronouns",
                pattern=r"\b(his|her|their)\b",
                replacements={
                    Gender.MASCULINE: "his",
                    Gender.FEMININE: "her",
                    Gender.NEUTRAL: "their",
                },
                rule_type="pronoun",
                language=Language.ENGLISH,
            ),
            # Reflexive pronouns
            GenderRule(
                name="reflexive_pronouns",
                pattern=r"\b(himself|herself|themself|themselves)\b",
                replacements={
                    Gender.MASCULINE: "himself",
                    Gender.FEMININE: "herself",
                    Gender.NEUTRAL: "themself",
                },
                rule_type="pronoun",
                language=Language.ENGLISH,
            ),
        ]

        for rule in english_rules:
            self.add_rule(rule)

    def _load_spanish_rules(self) -> None:
        """Load Spanish gender rules."""
        spanish_rules = [
            # Subject pronouns
            GenderRule(
                name="subject_pronouns_es",
                pattern=r"\b(él|ella|elle)\b",
                replacements={
                    Gender.MASCULINE: "él",
                    Gender.FEMININE: "ella",
                    Gender.NEUTRAL: "elle",  # Inclusive form
                },
                rule_type="pronoun",
                language=Language.SPANISH,
            ),
            # Articles
            GenderRule(
                name="definite_articles_es",
                pattern=r"\b(el|la|le)\s+(\w+)",
                replacements={
                    Gender.MASCULINE: r"el \2",
                    Gender.FEMININE: r"la \2",
                    Gender.NEUTRAL: r"le \2",
                },
                rule_type="article",
                language=Language.SPANISH,
            ),
            # Adjective endings
            GenderRule(
                name="adjective_o_a_es",
                pattern=r"\b(\w+)o\b",
                replacements={
                    Gender.MASCULINE: r"\1o",
                    Gender.FEMININE: r"\1a",
                    Gender.NEUTRAL: r"\1e",
                },
                rule_type="adjective",
                context_required=r"(artículo|adjetivo)",
                language=Language.SPANISH,
            ),
        ]

        for rule in spanish_rules:
            self.add_rule(rule)

    def _load_french_rules(self) -> None:
        """Load French gender rules."""
        french_rules = [
            # Subject pronouns
            GenderRule(
                name="subject_pronouns_fr",
                pattern=r"\b(il|elle|iel)\b",
                replacements={
                    Gender.MASCULINE: "il",
                    Gender.FEMININE: "elle",
                    Gender.NEUTRAL: "iel",  # Inclusive form
                },
                rule_type="pronoun",
                language=Language.FRENCH,
            ),
            # Articles
            GenderRule(
                name="definite_articles_fr",
                pattern=r"\b(le|la)\s+(\w+)",
                replacements={
                    Gender.MASCULINE: r"le \2",
                    Gender.FEMININE: r"la \2",
                    Gender.NEUTRAL: r"le·la \2",  # Inclusive form
                },
                rule_type="article",
                language=Language.FRENCH,
            ),
            # Past participle agreement
            GenderRule(
                name="past_participle_e_fr",
                pattern=r"\b(\w+)é\b",
                replacements={
                    Gender.MASCULINE: r"\1é",
                    Gender.FEMININE: r"\1ée",
                    Gender.NEUTRAL: r"\1é·e",
                },
                rule_type="verb",
                context_required=r"(être|avoir)",
                language=Language.FRENCH,
            ),
        ]

        for rule in french_rules:
            self.add_rule(rule)


# Global rule engine instance
_rule_engine = GenderRuleEngine()


def get_language_gender_rules(language: Language) -> List[GenderRule]:
    """Get gender rules for a specific language."""
    return _rule_engine.rules.get(language, [])


def register_gender_rule(rule: GenderRule) -> None:
    """Register a custom gender rule."""
    _rule_engine.add_rule(rule)


def create_english_gender_profile() -> GenderProfile:
    """Create English gender profile."""
    return GenderProfile(
        language=Language.ENGLISH,
        has_grammatical_gender=False,
        gender_affects_verbs=False,
        gender_affects_adjectives=False,
        gender_affects_pronouns=True,
        pronouns={
            Gender.MASCULINE: {
                "subject": "he",
                "object": "him",
                "possessive": "his",
                "possessive_adj": "his",
                "reflexive": "himself",
            },
            Gender.FEMININE: {
                "subject": "she",
                "object": "her",
                "possessive": "hers",
                "possessive_adj": "her",
                "reflexive": "herself",
            },
            Gender.NEUTRAL: {
                "subject": "they",
                "object": "them",
                "possessive": "theirs",
                "possessive_adj": "their",
                "reflexive": "themself",
            },
        },
        profession_terms={
            "doctor": {
                Gender.MASCULINE: "doctor",
                Gender.FEMININE: "doctor",
                Gender.NEUTRAL: "doctor",
            },
            "nurse": {
                Gender.MASCULINE: "nurse",
                Gender.FEMININE: "nurse",
                Gender.NEUTRAL: "nurse",
            },
            "actor": {
                Gender.MASCULINE: "actor",
                Gender.FEMININE: "actress",
                Gender.NEUTRAL: "actor",
            },
        },
    )


def create_spanish_gender_profile() -> GenderProfile:
    """Create Spanish gender profile."""
    return GenderProfile(
        language=Language.SPANISH,
        has_grammatical_gender=True,
        gender_affects_verbs=False,
        gender_affects_adjectives=True,
        gender_affects_pronouns=True,
        pronouns={
            Gender.MASCULINE: {
                "subject": "él",
                "object": "lo",
                "indirect": "le",
                "possessive": "suyo",
                "reflexive": "sí mismo",
            },
            Gender.FEMININE: {
                "subject": "ella",
                "object": "la",
                "indirect": "le",
                "possessive": "suya",
                "reflexive": "sí misma",
            },
            Gender.NEUTRAL: {
                "subject": "elle",
                "object": "le",
                "indirect": "le",
                "possessive": "suye",
                "reflexive": "sí misme",
            },
        },
        adjective_endings={
            Gender.MASCULINE: "o",
            Gender.FEMININE: "a",
            Gender.NEUTRAL: "e",
        },
        profession_terms={
            "doctor": {
                Gender.MASCULINE: "doctor",
                Gender.FEMININE: "doctora",
                Gender.NEUTRAL: "doctore",
            },
            "enfermero": {
                Gender.MASCULINE: "enfermero",
                Gender.FEMININE: "enfermera",
                Gender.NEUTRAL: "enfermere",
            },
        },
    )


def create_french_gender_profile() -> GenderProfile:
    """Create French gender profile."""
    return GenderProfile(
        language=Language.FRENCH,
        has_grammatical_gender=True,
        gender_affects_verbs=True,  # Past participle agreement
        gender_affects_adjectives=True,
        gender_affects_pronouns=True,
        pronouns={
            Gender.MASCULINE: {
                "subject": "il",
                "object": "le",
                "indirect": "lui",
                "possessive": "son",
                "stressed": "lui",
            },
            Gender.FEMININE: {
                "subject": "elle",
                "object": "la",
                "indirect": "lui",
                "possessive": "sa",
                "stressed": "elle",
            },
            Gender.NEUTRAL: {
                "subject": "iel",
                "object": "lea",
                "indirect": "lui",
                "possessive": "saon",
                "stressed": "ellui",
            },
        },
        adjective_endings={
            Gender.MASCULINE: "",
            Gender.FEMININE: "e",
            Gender.NEUTRAL: "·e",
        },
        profession_terms={
            "médecin": {
                Gender.MASCULINE: "médecin",
                Gender.FEMININE: "médecin",
                Gender.NEUTRAL: "médecin",
            },
            "infirmier": {
                Gender.MASCULINE: "infirmier",
                Gender.FEMININE: "infirmière",
                Gender.NEUTRAL: "infirmier·ère",
            },
        },
    )


# Initialize default profiles
_DEFAULT_PROFILES = {
    Language.ENGLISH: create_english_gender_profile(),
    Language.SPANISH: create_spanish_gender_profile(),
    Language.FRENCH: create_french_gender_profile(),
}


def get_gender_profile(language: Language) -> Optional[GenderProfile]:
    """Get gender profile for a language."""
    return _DEFAULT_PROFILES.get(language)
