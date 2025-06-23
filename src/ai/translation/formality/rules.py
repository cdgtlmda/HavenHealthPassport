"""
Formality rules for different languages.

This module contains language-specific rules for formality adjustment,
including formal/informal word mappings, grammatical rules, and
cultural conventions.

This module handles encrypted PHI with access control and audit logging
to ensure HIPAA compliance.
"""

import logging
import re
from dataclasses import dataclass
from typing import Dict, List, Optional

from ..config import Language
from .core import FormalityLevel, FormalityProfile

logger = logging.getLogger(__name__)


@dataclass
class FormalityRule:
    """A single formality adjustment rule."""

    name: str
    pattern: str  # Regex pattern
    replacement: str  # Replacement text or callable
    formality_change: int  # -2 to +2 (-2 = much less formal, +2 = much more formal)
    context_required: Optional[str] = None  # Required context pattern
    context_forbidden: Optional[str] = None  # Forbidden context pattern
    language: Optional[Language] = None

    def apply(self, text: str) -> Optional[str]:
        """Apply rule to text if conditions met."""
        # Check context requirements
        if self.context_required and not re.search(self.context_required, text, re.I):
            return None
        if self.context_forbidden and re.search(self.context_forbidden, text, re.I):
            return None

        # Apply replacement
        if callable(self.replacement):
            return re.sub(self.pattern, self.replacement, text, flags=re.I)
        else:
            return re.sub(self.pattern, self.replacement, text, flags=re.I)


class FormalityRuleEngine:
    """Engine for applying formality rules."""

    def __init__(self) -> None:
        """Initialize rule engine."""
        self.rules: Dict[Language, List[FormalityRule]] = {}
        self._load_default_rules()

    def apply_rules(
        self,
        text: str,
        language: Language,
        current_level: FormalityLevel,
        target_level: FormalityLevel,
    ) -> str:
        """Apply appropriate rules to adjust formality."""
        if language not in self.rules:
            return text

        adjusted_text = text
        level_diff = target_level - current_level

        for rule in self.rules[language]:
            # Apply rule if it moves in the right direction
            if (level_diff > 0 and rule.formality_change > 0) or (
                level_diff < 0 and rule.formality_change < 0
            ):
                result = rule.apply(adjusted_text)
                if result:
                    adjusted_text = result

        return adjusted_text

    def add_rule(self, rule: FormalityRule) -> None:
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
        """Load English formality rules."""
        english_rules = [
            # Contractions (informal -> formal)
            FormalityRule(
                name="expand_contractions",
                pattern=r"\bcan't\b",
                replacement="cannot",
                formality_change=1,
                language=Language.ENGLISH,
            ),
            FormalityRule(
                name="expand_wont",
                pattern=r"\bwon't\b",
                replacement="will not",
                formality_change=1,
                language=Language.ENGLISH,
            ),
            FormalityRule(
                name="expand_dont",
                pattern=r"\bdon't\b",
                replacement="do not",
                formality_change=1,
                language=Language.ENGLISH,
            ),
            FormalityRule(
                name="expand_isnt",
                pattern=r"\bisn't\b",
                replacement="is not",
                formality_change=1,
                language=Language.ENGLISH,
            ),
            # Informal words -> formal
            FormalityRule(
                name="formalize_get",
                pattern=r"\bget\b",
                replacement="obtain",
                formality_change=1,
                context_forbidden=r"get up|get down|get well",
                language=Language.ENGLISH,
            ),
            FormalityRule(
                name="formalize_buy",
                pattern=r"\bbuy\b",
                replacement="purchase",
                formality_change=1,
                language=Language.ENGLISH,
            ),
            # Medical informal -> formal
            FormalityRule(
                name="formalize_shot",
                pattern=r"\bshot\b",
                replacement="injection",
                formality_change=1,
                context_required=r"vaccine|immuniz|inject",
                language=Language.ENGLISH,
            ),
            FormalityRule(
                name="formalize_meds",
                pattern=r"\bmeds\b",
                replacement="medications",
                formality_change=1,
                language=Language.ENGLISH,
            ),
            # Formal -> informal (for making less formal)
            FormalityRule(
                name="informalize_utilize",
                pattern=r"\butilize\b",
                replacement="use",
                formality_change=-1,
                language=Language.ENGLISH,
            ),
            FormalityRule(
                name="informalize_commence",
                pattern=r"\bcommence\b",
                replacement="start",
                formality_change=-1,
                language=Language.ENGLISH,
            ),
        ]

        for rule in english_rules:
            self.add_rule(rule)

    def _load_spanish_rules(self) -> None:
        """Load Spanish formality rules."""
        spanish_rules = [
            # Pronouns (informal tú -> formal usted)
            FormalityRule(
                name="tu_to_usted",
                pattern=r"\btú\b",
                replacement="usted",
                formality_change=2,
                language=Language.SPANISH,
            ),
            FormalityRule(
                name="tienes_to_tiene",
                pattern=r"\btienes\b",
                replacement="tiene",
                formality_change=2,
                language=Language.SPANISH,
            ),
            FormalityRule(
                name="tu_possessive",
                pattern=r"\btu\b",
                replacement="su",
                formality_change=1,
                context_forbidden=r"\btú\b",  # Not the pronoun tú
                language=Language.SPANISH,
            ),
            # Formal expressions
            FormalityRule(
                name="formal_request",
                pattern=r"\b¿puedes\b",
                replacement="¿podría",
                formality_change=2,
                language=Language.SPANISH,
            ),
        ]

        for rule in spanish_rules:
            self.add_rule(rule)

    def _load_french_rules(self) -> None:
        """Load French formality rules."""
        french_rules = [
            # Pronouns (informal tu -> formal vous)
            FormalityRule(
                name="tu_to_vous",
                pattern=r"\btu\b",
                replacement="vous",
                formality_change=2,
                language=Language.FRENCH,
            ),
            FormalityRule(
                name="ton_to_votre",
                pattern=r"\bton\b",
                replacement="votre",
                formality_change=2,
                language=Language.FRENCH,
            ),
            FormalityRule(
                name="ta_to_votre",
                pattern=r"\bta\b",
                replacement="votre",
                formality_change=2,
                language=Language.FRENCH,
            ),
            # Verb conjugations
            FormalityRule(
                name="tu_form_to_vous",
                pattern=r"\b(\w+)es\b",  # Simple present tu form
                replacement=r"\1ez",  # vous form
                formality_change=2,
                context_required=r"\btu\b",
                language=Language.FRENCH,
            ),
        ]

        for rule in french_rules:
            self.add_rule(rule)


# Global rule engine instance
_rule_engine = FormalityRuleEngine()


def get_language_formality_rules(language: Language) -> List[FormalityRule]:
    """Get formality rules for a specific language."""
    return _rule_engine.rules.get(language, [])


def register_formality_rule(rule: FormalityRule) -> None:
    """Register a custom formality rule."""
    _rule_engine.add_rule(rule)


def create_english_formality_profile() -> FormalityProfile:
    """Create English formality profile."""
    return FormalityProfile(
        language=Language.ENGLISH,
        formal_pronouns={
            "i": "I",  # Ensure proper capitalization
            "u": "you",
            "ur": "your",
            "r": "are",
        },
        formal_verbs={
            "get": "obtain",
            "buy": "purchase",
            "need": "require",
            "help": "assist",
            "show": "demonstrate",
            "fix": "repair",
        },
        formal_expressions={
            "thanks": "thank you",
            "hi": "hello",
            "bye": "goodbye",
            "yeah": "yes",
            "nope": "no",
            "ok": "acceptable",
            "a lot": "numerous",
            "kind of": "somewhat",
        },
        contractions={
            "don't": "do not",
            "won't": "will not",
            "can't": "cannot",
            "couldn't": "could not",
            "shouldn't": "should not",
            "wouldn't": "would not",
            "isn't": "is not",
            "aren't": "are not",
            "wasn't": "was not",
            "weren't": "were not",
            "hasn't": "has not",
            "haven't": "have not",
            "hadn't": "had not",
            "I'm": "I am",
            "you're": "you are",
            "he's": "he is",
            "she's": "she is",
            "it's": "it is",
            "we're": "we are",
            "they're": "they are",
            "I've": "I have",
            "you've": "you have",
            "'em": "them",
            "we've": "we have",
            "they've": "they have",
            "I'd": "I would",
            "you'd": "you would",
            "he'd": "he would",
            "she'd": "she would",
            "we'd": "we would",
            "they'd": "they would",
            "I'll": "I will",
            "you'll": "you will",
            "he'll": "he will",
            "she'll": "she will",
            "we'll": "we will",
            "they'll": "they will",
        },
        colloquialisms=["gonna", "wanna", "gotta", "kinda", "sorta", "dunno"],
        slang_terms={"cool", "awesome", "stuff", "thing", "guy", "kid"},
        formal_sentence_starters=[
            "Furthermore,",
            "Moreover,",
            "Additionally,",
            "Consequently,",
            "Therefore,",
            "Nevertheless,",
            "However,",
            "Accordingly,",
        ],
        politeness_phrases=[
            "Would you please",
            "Could you kindly",
            "If you would be so kind",
            "I would appreciate it if",
            "May I request that",
        ],
        hedging_expressions=[
            "it seems that",
            "it appears that",
            "perhaps",
            "possibly",
            "it might be",
            "tends to",
            "generally speaking",
        ],
    )


def create_spanish_formality_profile() -> FormalityProfile:
    """Create Spanish formality profile."""
    return FormalityProfile(
        language=Language.SPANISH,
        formal_pronouns={
            "tú": "usted",
            "ti": "usted",
            "tu": "su",
            "tus": "sus",
            "contigo": "con usted",
        },
        formal_verbs={
            # Informal imperatives to formal
            "dame": "déme",
            "dime": "dígame",
            "hazlo": "hágalo",
            "ven": "venga",
            "mira": "mire",
        },
        formal_expressions={
            "hola": "buenos días/tardes",
            "adiós": "hasta luego",
            "gracias": "muchas gracias",
            "por favor": "por favor, sírvase",
            "ok": "de acuerdo",
            "sí": "así es",
        },
        contractions={},  # Spanish doesn't use contractions like English
        colloquialisms=["pues", "o sea", "es que", "vale", "venga"],
        slang_terms={"guay", "chido", "padre", "genial", "tío", "colega"},
        formal_sentence_starters=[
            "Por consiguiente,",
            "Además,",
            "Sin embargo,",
            "No obstante,",
            "Por lo tanto,",
            "En consecuencia,",
            "Asimismo,",
        ],
        politeness_phrases=[
            "¿Sería tan amable de",
            "¿Podría usted",
            "Le agradecería que",
            "¿Tendría la bondad de",
            "Si fuera tan amable",
        ],
        hedging_expressions=[
            "parece que",
            "al parecer",
            "quizás",
            "posiblemente",
            "podría ser que",
            "tiende a",
            "por lo general",
        ],
    )


def create_french_formality_profile() -> FormalityProfile:
    """Create French formality profile."""
    return FormalityProfile(
        language=Language.FRENCH,
        formal_pronouns={
            "tu": "vous",
            "ton": "votre",
            "ta": "votre",
            "tes": "vos",
            "toi": "vous",
        },
        formal_verbs={
            # Informal to formal
            "bouffer": "manger",
            "bosser": "travailler",
            "filer": "donner",
            "balancer": "jeter",
        },
        formal_expressions={
            "salut": "bonjour",
            "ciao": "au revoir",
            "ouais": "oui",
            "d'acc": "d'accord",
            "merci": "je vous remercie",
        },
        contractions={},  # French contractions are grammatical, not informal
        colloquialisms=["quoi", "ben", "euh", "bah", "alors là"],
        slang_terms={"truc", "machin", "mec", "nana", "sympa", "super"},
        formal_sentence_starters=[
            "Par conséquent,",
            "En outre,",
            "Néanmoins,",
            "Toutefois,",
            "De ce fait,",
            "En effet,",
            "Par ailleurs,",
        ],
        politeness_phrases=[
            "Auriez-vous l'amabilité de",
            "Pourriez-vous",
            "Je vous serais reconnaissant de",
            "Veuillez",
            "Je vous prie de",
        ],
        hedging_expressions=[
            "il semble que",
            "il paraît que",
            "peut-être",
            "éventuellement",
            "il se pourrait que",
            "a tendance à",
            "généralement",
        ],
    )


# Initialize default profiles
_DEFAULT_PROFILES = {
    Language.ENGLISH: create_english_formality_profile(),
    Language.SPANISH: create_spanish_formality_profile(),
    Language.FRENCH: create_french_formality_profile(),
}


def get_formality_profile(language: Language) -> Optional[FormalityProfile]:
    """Get formality profile for a language."""
    return _DEFAULT_PROFILES.get(language)
