"""Translation Pluralization System.

This module provides comprehensive pluralization support for multiple languages,
handling complex pluralization rules across different language families.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Union

from src.utils.logging import get_logger

logger = get_logger(__name__)


class PluralForm(str, Enum):
    """Standard plural forms across languages."""

    ZERO = "zero"  # 0 items
    ONE = "one"  # 1 item (singular)
    TWO = "two"  # 2 items (dual - Arabic, Hebrew)
    FEW = "few"  # Few items (2-4 in Polish, etc.)
    MANY = "many"  # Many items
    OTHER = "other"  # Default/other cases


@dataclass
class PluralRule:
    """Pluralization rule for a language."""

    language: str
    rule_function: Callable[[int], PluralForm]
    forms: List[PluralForm]
    examples: Dict[PluralForm, List[Union[int, float]]]


class PluralizationManager:
    """Manages pluralization rules for all supported languages."""

    def __init__(self) -> None:
        """Initialize pluralization manager."""
        self.rules: Dict[str, PluralRule] = {}
        self._initialize_rules()

    def _initialize_rules(self) -> None:
        """Initialize pluralization rules for all languages."""
        # English: 1 = one, everything else = other
        self.rules["en"] = PluralRule(
            language="en",
            rule_function=self._rule_english,
            forms=[PluralForm.ONE, PluralForm.OTHER],
            examples={PluralForm.ONE: [1], PluralForm.OTHER: [0, 2, 3, 4, 5, 10, 100]},
        )

        # Spanish/French: 0,1 = one, everything else = other
        self.rules["es"] = PluralRule(
            language="es",
            rule_function=self._rule_spanish,
            forms=[PluralForm.ONE, PluralForm.OTHER],
            examples={PluralForm.ONE: [0, 1], PluralForm.OTHER: [2, 3, 4, 5, 10, 100]},
        )

        self.rules["fr"] = PluralRule(
            language="fr",
            rule_function=self._rule_french,
            forms=[PluralForm.ONE, PluralForm.OTHER],
            examples={PluralForm.ONE: [0, 1], PluralForm.OTHER: [2, 3, 4, 5, 10, 100]},
        )

        # Arabic: Complex with 6 forms
        self.rules["ar"] = PluralRule(
            language="ar",
            rule_function=self._rule_arabic,
            forms=[
                PluralForm.ZERO,
                PluralForm.ONE,
                PluralForm.TWO,
                PluralForm.FEW,
                PluralForm.MANY,
                PluralForm.OTHER,
            ],
            examples={
                PluralForm.ZERO: [0],
                PluralForm.ONE: [1],
                PluralForm.TWO: [2],
                PluralForm.FEW: [3, 4, 5, 6, 7, 8, 9, 10],
                PluralForm.MANY: [11, 12, 20, 25, 99],
                PluralForm.OTHER: [100, 101, 102, 200],
            },
        )

        # Polish: Complex with 4 forms
        self.rules["pl"] = PluralRule(
            language="pl",
            rule_function=self._rule_polish,
            forms=[PluralForm.ONE, PluralForm.FEW, PluralForm.MANY, PluralForm.OTHER],
            examples={
                PluralForm.ONE: [1],
                PluralForm.FEW: [2, 3, 4, 22, 23, 24],
                PluralForm.MANY: [0, 5, 6, 7, 8, 9, 10, 11, 12],
                PluralForm.OTHER: [1.5, 2.5],
            },
        )

        # Chinese/Japanese/Korean: No plurals
        for lang in ["zh", "ja", "ko"]:
            self.rules[lang] = PluralRule(
                language=lang,
                rule_function=self._rule_no_plural,
                forms=[PluralForm.OTHER],
                examples={PluralForm.OTHER: [0, 1, 2, 3, 10, 100]},
            )

        # Russian: Complex with 4 forms
        self.rules["ru"] = PluralRule(
            language="ru",
            rule_function=self._rule_russian,
            forms=[PluralForm.ONE, PluralForm.FEW, PluralForm.MANY, PluralForm.OTHER],
            examples={
                PluralForm.ONE: [1, 21, 31, 41, 51],
                PluralForm.FEW: [2, 3, 4, 22, 23, 24],
                PluralForm.MANY: [0, 5, 6, 7, 8, 9, 10, 11, 12],
                PluralForm.OTHER: [1.5, 2.5],
            },
        )

        # Hindi: Simple dual system
        self.rules["hi"] = PluralRule(
            language="hi",
            rule_function=self._rule_hindi,
            forms=[PluralForm.ONE, PluralForm.OTHER],
            examples={PluralForm.ONE: [0, 1], PluralForm.OTHER: [2, 3, 4, 5, 10, 100]},
        )

    # Rule functions for each language
    def _rule_english(self, n: int) -> PluralForm:
        """English pluralization rule."""
        return PluralForm.ONE if n == 1 else PluralForm.OTHER

    def _rule_spanish(self, n: int) -> PluralForm:
        """Spanish pluralization rule."""
        return PluralForm.ONE if n in [0, 1] else PluralForm.OTHER

    def _rule_french(self, n: int) -> PluralForm:
        """French pluralization rule."""
        return PluralForm.ONE if n in [0, 1] else PluralForm.OTHER

    def _rule_arabic(self, n: int) -> PluralForm:
        """Arabic pluralization rule."""
        if n == 0:
            return PluralForm.ZERO
        elif n == 1:
            return PluralForm.ONE
        elif n == 2:
            return PluralForm.TWO
        elif n % 100 >= 3 and n % 100 <= 10:
            return PluralForm.FEW
        elif n % 100 >= 11 and n % 100 <= 99:
            return PluralForm.MANY
        else:
            return PluralForm.OTHER

    def _rule_polish(self, n: int) -> PluralForm:
        """Polish pluralization rule."""
        if n == 1:
            return PluralForm.ONE
        elif n % 10 >= 2 and n % 10 <= 4 and (n % 100 < 12 or n % 100 > 14):
            return PluralForm.FEW
        elif (
            n != 1
            and n % 10 >= 0
            and n % 10 <= 1
            or n % 10 >= 5
            and n % 10 <= 9
            or n % 100 >= 12
            and n % 100 <= 14
        ):
            return PluralForm.MANY
        else:
            return PluralForm.OTHER

    def _rule_russian(self, n: int) -> PluralForm:
        """Russian pluralization rule."""
        if n % 10 == 1 and n % 100 != 11:
            return PluralForm.ONE
        elif n % 10 >= 2 and n % 10 <= 4 and (n % 100 < 12 or n % 100 > 14):
            return PluralForm.FEW
        elif (
            n % 10 == 0
            or n % 10 >= 5
            and n % 10 <= 9
            or n % 100 >= 11
            and n % 100 <= 14
        ):
            return PluralForm.MANY
        else:
            return PluralForm.OTHER

    def _rule_no_plural(self, _n: int) -> PluralForm:
        """Rule for languages without plurals."""
        return PluralForm.OTHER

    def _rule_hindi(self, n: int) -> PluralForm:
        """Hindi pluralization rule."""
        return PluralForm.ONE if n in [0, 1] else PluralForm.OTHER

    def get_plural_form(self, language: str, count: int) -> PluralForm:
        """Get the appropriate plural form for a count in a language."""
        rule = self.rules.get(language)
        if not rule:
            logger.warning(f"No pluralization rule for language: {language}")
            return PluralForm.OTHER

        return rule.rule_function(count)

    def pluralize(
        self,
        language: str,
        translations: Dict[str, str],
        count: int,
        variables: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Pluralize a translation based on count.

        Args:
            language: Language code
            translations: Dict of plural forms to translations
            count: The count to pluralize for
            variables: Optional variables to interpolate

        Returns:
            Pluralized and interpolated string
        """
        plural_form = self.get_plural_form(language, count)

        # Try to get translation for specific form
        translation = translations.get(plural_form.value)

        # Fallback to other form if specific not found
        if not translation:
            translation = translations.get(PluralForm.OTHER.value)

        # Final fallback to any available translation
        if not translation and translations:
            translation = next(iter(translations.values()))

        if not translation:
            logger.error(f"No translation found for {language} with count {count}")
            return f"[Missing translation: {count}]"

        # Interpolate count
        translation = translation.replace("{{count}}", str(count))
        translation = translation.replace("{count}", str(count))

        # Interpolate other variables
        if variables:
            for key, value in variables.items():
                translation = translation.replace(f"{{{key}}}", str(value))
                translation = translation.replace(f"{{{{{key}}}}}", str(value))

        return translation

    def format_number_with_noun(
        self, language: str, count: int, noun_forms: Dict[str, str]
    ) -> str:
        """
        Format a number with the appropriate noun form.

        Example:
            format_number_with_noun("en", 5, {"one": "day", "other": "days"})
            => "5 days"
        """
        plural_form = self.get_plural_form(language, count)
        noun = noun_forms.get(
            plural_form.value, noun_forms.get(PluralForm.OTHER.value, "")
        )

        # Language-specific formatting
        if language == "fr" and count > 1:
            # French adds 's' for plural
            if not noun.endswith("s") and not noun.endswith("x"):
                noun += "s"

        return f"{count} {noun}"

    def get_ordinal(self, language: str, number: int) -> str:
        """Get ordinal number (1st, 2nd, 3rd, etc.) for a language."""
        ordinals = {
            "en": self._get_ordinal_english,
            "es": self._get_ordinal_spanish,
            "fr": self._get_ordinal_french,
        }

        ordinal_func = ordinals.get(language, self._get_ordinal_default)
        return ordinal_func(number)

    def _get_ordinal_english(self, n: int) -> str:
        """Get English ordinal."""
        if 10 <= n % 100 <= 20:
            suffix = "th"
        else:
            suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
        return f"{n}{suffix}"

    def _get_ordinal_spanish(self, n: int) -> str:
        """Get Spanish ordinal."""
        # Simplified - full implementation would have all forms
        if n == 1:
            return "1º"  # primero
        elif n == 2:
            return "2º"  # segundo
        else:
            return f"{n}º"

    def _get_ordinal_french(self, n: int) -> str:
        """Get French ordinal."""
        if n == 1:
            return "1er"  # premier
        else:
            return f"{n}e"  # deuxième, troisième, etc.

    def _get_ordinal_default(self, n: int) -> str:
        """Return default ordinal formatting."""
        return f"{n}."

    def get_plural_examples(
        self, language: str
    ) -> Dict[PluralForm, List[Union[int, float]]]:
        """Get examples of numbers for each plural form in a language."""
        rule = self.rules.get(language)
        if not rule:
            return {}
        return rule.examples

    def validate_plural_translations(
        self, language: str, translations: Dict[str, str]
    ) -> List[str]:
        """
        Validate that all required plural forms are provided.

        Returns list of missing forms.
        """
        rule = self.rules.get(language)
        if not rule:
            return []

        missing = []
        for form in rule.forms:
            if form.value not in translations:
                missing.append(form.value)

        return missing


# Global pluralization manager
pluralization_manager = PluralizationManager()
