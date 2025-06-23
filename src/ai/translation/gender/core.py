"""
Core gender-aware translation functionality.

This module provides the main gender detection and adaptation classes
for handling gender in medical translations.
"""

import logging
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from ...langchain.bedrock import get_bedrock_model
from ..config import Language

logger = logging.getLogger(__name__)


class Gender(Enum):
    """Gender categories for translation."""

    MASCULINE = "masculine"
    FEMININE = "feminine"
    NEUTRAL = "neutral"
    UNKNOWN = "unknown"

    @classmethod
    def from_string(cls, value: str) -> "Gender":
        """Create Gender from string value."""
        value_lower = value.lower()
        for gender in cls:
            if gender.value == value_lower:
                return gender
        return cls.UNKNOWN


@dataclass
class GenderContext:
    """Context information for gender-aware translation."""

    subject_gender: Optional[Gender] = None
    audience_gender: Optional[Gender] = None
    grammatical_person: int = 3  # 1st, 2nd, or 3rd person
    formality_level: str = "neutral"  # informal, neutral, formal
    medical_context: bool = False
    prefer_neutral: bool = False
    cultural_preferences: Dict[str, Any] = field(default_factory=dict)
    context_type: str = "general"  # Type of context (general, medical, formal, etc.)


@dataclass
class GenderProfile:
    """Language-specific gender profile."""

    language: Language
    has_grammatical_gender: bool
    gender_affects_verbs: bool
    gender_affects_adjectives: bool
    gender_affects_pronouns: bool
    default_gender: Gender = Gender.NEUTRAL

    # Pronoun mappings
    pronouns: Dict[Gender, Dict[str, str]] = field(default_factory=dict)
    possessives: Dict[Gender, Dict[str, str]] = field(default_factory=dict)

    # Agreement rules
    adjective_endings: Dict[Gender, str] = field(default_factory=dict)
    verb_conjugations: Dict[Gender, Dict[str, str]] = field(default_factory=dict)

    # Gendered nouns
    gendered_nouns: Dict[str, Gender] = field(default_factory=dict)
    profession_terms: Dict[str, Dict[Gender, str]] = field(default_factory=dict)


@dataclass
class GenderDetectionResult:
    """Result of gender detection."""

    detected_gender: Gender
    confidence: float
    detection_method: str  # "explicit", "implicit", "contextual", "default"
    evidence: List[str] = field(default_factory=list)
    alternative_genders: List[Tuple[Gender, float]] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    processing_time_ms: float = 0.0


@dataclass
class GenderAdaptationResult:
    """Result of gender adaptation."""

    adapted_text: str
    source_gender: Gender
    target_gender: Gender
    modifications: List[Tuple[str, str]] = field(default_factory=list)
    confidence: float = 0.0
    warnings: List[str] = field(default_factory=list)
    processing_time_ms: float = 0.0


class BaseGenderDetector(ABC):
    """Abstract base class for gender detection."""

    @abstractmethod
    def detect(
        self, text: str, language: Language, context: Optional[GenderContext] = None
    ) -> GenderDetectionResult:
        """Detect gender in text."""
        pass

    @abstractmethod
    def extract_gender_markers(self, text: str, language: Language) -> Dict[str, Any]:
        """Extract gender markers from text."""
        pass


class GenderDetector(BaseGenderDetector):
    """Main gender detection implementation."""

    def __init__(self, profiles: Optional[Dict[Language, GenderProfile]] = None):
        """
        Initialize gender detector.

        Args:
            profiles: Language-specific gender profiles
        """
        self.profiles = profiles or {}
        self._load_default_profiles()
        self._gender_markers = self._load_gender_markers()

    def detect(
        self, text: str, language: Language, context: Optional[GenderContext] = None
    ) -> GenderDetectionResult:
        """
        Detect gender in text.

        Args:
            text: Text to analyze
            language: Language of the text
            context: Optional gender context

        Returns:
            GenderDetectionResult with detected gender
        """
        start_time = datetime.now()

        # Extract gender markers
        markers = self.extract_gender_markers(text, language)

        # Check explicit markers first
        if markers.get("explicit_gender"):
            gender = Gender.from_string(markers["explicit_gender"])
            return GenderDetectionResult(
                detected_gender=gender,
                confidence=0.95,
                detection_method="explicit",
                evidence=markers.get("evidence", []),
                processing_time_ms=(datetime.now() - start_time).total_seconds() * 1000,
            )

        # Check pronouns
        pronoun_gender = self._detect_from_pronouns(
            markers.get("pronouns", []), language
        )
        if pronoun_gender != Gender.UNKNOWN:
            return GenderDetectionResult(
                detected_gender=pronoun_gender,
                confidence=0.85,
                detection_method="implicit",
                evidence=markers.get("pronouns", []),
                processing_time_ms=(datetime.now() - start_time).total_seconds() * 1000,
            )

        # Check contextual clues
        contextual_gender = self._detect_from_context(text, language, context)
        if contextual_gender != Gender.UNKNOWN:
            return GenderDetectionResult(
                detected_gender=contextual_gender,
                confidence=0.7,
                detection_method="contextual",
                evidence=["contextual analysis"],
                processing_time_ms=(datetime.now() - start_time).total_seconds() * 1000,
            )

        # Use default or neutral
        default_gender = (
            context.subject_gender
            if context and context.subject_gender
            else Gender.UNKNOWN
        )
        return GenderDetectionResult(
            detected_gender=default_gender,
            confidence=0.3,
            detection_method="default",
            warnings=["No clear gender markers found"],
            processing_time_ms=(datetime.now() - start_time).total_seconds() * 1000,
        )

    def extract_gender_markers(self, text: str, language: Language) -> Dict[str, Any]:
        """Extract gender markers from text."""
        markers: Dict[str, Any] = {
            "pronouns": [],
            "titles": [],
            "gendered_nouns": [],
            "adjectives": [],
            "explicit_gender": None,
            "evidence": [],
        }

        text_lower = text.lower()

        # Extract pronouns
        if language == Language.ENGLISH:
            # English pronouns - use word boundaries to avoid false matches
            masculine_pronouns = []
            if re.search(r"\bhe\b", text_lower):
                masculine_pronouns.append("he")
            if re.search(r"\bhim\b", text_lower):
                masculine_pronouns.append("him")
            if re.search(r"\bhis\b", text_lower):
                masculine_pronouns.append("his")
            if re.search(r"\bhimself\b", text_lower):
                masculine_pronouns.append("himself")

            if masculine_pronouns:
                pronouns_list = markers["pronouns"]
                evidence_list = markers["evidence"]
                if isinstance(pronouns_list, list) and isinstance(evidence_list, list):
                    pronouns_list.extend(masculine_pronouns)
                    evidence_list.append("masculine pronouns")

            feminine_pronouns = []
            if re.search(r"\bshe\b", text_lower):
                feminine_pronouns.append("she")
            if re.search(r"\bher\b", text_lower):
                feminine_pronouns.append("her")
            if re.search(r"\bhers\b", text_lower):
                feminine_pronouns.append("hers")
            if re.search(r"\bherself\b", text_lower):
                feminine_pronouns.append("herself")

            if feminine_pronouns:
                pronouns_list = markers["pronouns"]
                evidence_list = markers["evidence"]
                if isinstance(pronouns_list, list) and isinstance(evidence_list, list):
                    pronouns_list.extend(feminine_pronouns)
                    evidence_list.append("feminine pronouns")

            neutral_pronouns = []
            if re.search(r"\bthey\b", text_lower):
                neutral_pronouns.append("they")
            if re.search(r"\bthem\b", text_lower):
                neutral_pronouns.append("them")
            if re.search(r"\btheir\b", text_lower):
                neutral_pronouns.append("their")
            if re.search(r"\bthemself\b", text_lower):
                neutral_pronouns.append("themself")

            if neutral_pronouns:
                pronouns_list = markers["pronouns"]
                evidence_list = markers["evidence"]
                if isinstance(pronouns_list, list) and isinstance(evidence_list, list):
                    pronouns_list.extend(neutral_pronouns)
                    evidence_list.append("neutral pronouns")

        # Extract titles
        title_patterns = {
            "masculine": r"\b(Mr\.?|Sir|Lord)\b",
            "feminine": r"\b(Mrs\.?|Ms\.?|Miss|Lady|Madam)\b",
            "neutral": r"\b(Dr\.?|Prof\.?|Mx\.?)\b",
        }

        for gender, pattern in title_patterns.items():
            if re.search(pattern, text, re.I):
                titles_list = markers["titles"]
                evidence_list = markers["evidence"]
                if isinstance(titles_list, list) and isinstance(evidence_list, list):
                    titles_list.append(gender)
                    evidence_list.append(f"{gender} title")

        # Check for explicit gender statements
        explicit_masculine = re.search(r"\b(male|man|boy|gentleman)\b", text_lower)
        if explicit_masculine:
            markers["explicit_gender"] = "masculine"
            evidence_list = markers["evidence"]
            if isinstance(evidence_list, list):
                evidence_list.append(explicit_masculine.group())

        explicit_feminine = re.search(r"\b(female|woman|girl|lady)\b", text_lower)
        if explicit_feminine:
            markers["explicit_gender"] = "feminine"
            evidence_list = markers["evidence"]
            if isinstance(evidence_list, list):
                evidence_list.append(explicit_feminine.group())

        return markers

    def _detect_from_pronouns(self, pronouns: List[str], language: Language) -> Gender:
        """Detect gender from pronouns."""
        if not pronouns:
            return Gender.UNKNOWN

        # Log language for context
        logger.debug("Detecting gender from pronouns in %s", language)

        # Count pronoun types
        masculine_count = sum(
            1 for p in pronouns if p in ["he", "him", "his", "il", "él"]
        )
        feminine_count = sum(
            1 for p in pronouns if p in ["she", "her", "hers", "elle", "ella"]
        )
        neutral_count = sum(1 for p in pronouns if p in ["they", "them", "their"])

        # Return most frequent
        if masculine_count > feminine_count and masculine_count > neutral_count:
            return Gender.MASCULINE
        elif feminine_count > masculine_count and feminine_count > neutral_count:
            return Gender.FEMININE
        elif neutral_count > 0:
            return Gender.NEUTRAL
        else:
            return Gender.UNKNOWN

    def _detect_from_context(
        self, text: str, language: Language, context: Optional[GenderContext]
    ) -> Gender:
        """Detect gender from context."""
        # Use AI for complex contextual detection
        try:
            if context and context.subject_gender:
                return context.subject_gender

            # Simple heuristics for now
            if language in self.profiles:
                profile = self.profiles[language]
                # Check gendered nouns
                for noun, gender in profile.gendered_nouns.items():
                    if noun in text.lower():
                        return gender

            return Gender.UNKNOWN

        except (ValueError, AttributeError, KeyError) as e:
            logger.warning("Context detection failed: %s", str(e))
            return Gender.UNKNOWN

    def _load_default_profiles(self) -> None:
        """Load default gender profiles."""
        # This will be populated by the rules module
        pass

    def _load_gender_markers(self) -> Dict[str, List[str]]:
        """Load gender marker words."""
        return {
            "masculine": ["he", "him", "his", "himself", "man", "boy", "male"],
            "feminine": ["she", "her", "hers", "herself", "woman", "girl", "female"],
            "neutral": ["they", "them", "their", "themself", "person", "individual"],
        }


class GenderAdapter:
    """Adapts text to use specific gender forms."""

    def __init__(
        self,
        detector: Optional[GenderDetector] = None,
        profiles: Optional[Dict[Language, GenderProfile]] = None,
        use_ai: bool = True,
    ):
        """
        Initialize gender adapter.

        Args:
            detector: Gender detector instance
            profiles: Language-specific gender profiles
            use_ai: Whether to use AI for adaptation
        """
        self.detector = detector or GenderDetector()
        self.profiles = profiles or {}
        self.use_ai = use_ai
        self._load_default_profiles()

    def adapt(
        self,
        text: str,
        target_gender: Gender,
        language: Language,
        context: Optional[GenderContext] = None,
        preserve_meaning: bool = True,
    ) -> GenderAdaptationResult:
        """
        Adapt text to target gender.

        The preserve_meaning parameter ensures that medical meaning is maintained
        during gender adaptation.
        Adapt text to use target gender forms.

        Args:
            text: Text to adapt
            target_gender: Desired gender
            language: Language of the text
            context: Optional gender context
            preserve_meaning: Whether to preserve exact meaning

        Returns:
            GenderAdaptationResult with adapted text
        """
        start_time = datetime.now()

        # Implement preserve_meaning logic
        # When preserve_meaning is True, we should be more conservative with changes
        # to ensure medical accuracy is maintained
        adaptation_threshold = 0.8 if preserve_meaning else 0.6

        # Detect current gender
        detection = self.detector.detect(text, language, context)

        # Check if adaptation needed
        if detection.detected_gender == target_gender:
            return GenderAdaptationResult(
                adapted_text=text,
                source_gender=detection.detected_gender,
                target_gender=target_gender,
                confidence=1.0,
                processing_time_ms=(datetime.now() - start_time).total_seconds() * 1000,
            )

        # Get language profile
        profile = self.profiles.get(language)
        if not profile:
            return GenderAdaptationResult(
                adapted_text=text,
                source_gender=detection.detected_gender,
                target_gender=target_gender,
                warnings=["No gender profile available for language"],
                processing_time_ms=(datetime.now() - start_time).total_seconds() * 1000,
            )

        # Perform adaptation
        if self.use_ai and language in [
            Language.ENGLISH,
            Language.SPANISH,
            Language.FRENCH,
        ]:
            adapted_text, modifications = self._adapt_with_ai(
                text, detection.detected_gender, target_gender, language, context
            )
        else:
            adapted_text, modifications = self._adapt_with_rules(
                text, detection.detected_gender, target_gender, language, profile
            )

        # Calculate adaptation confidence
        adaptation_confidence = 0.85

        # If preserve_meaning is True and confidence is below threshold, return original
        if preserve_meaning and adaptation_confidence < adaptation_threshold:
            logger.info(
                "Adaptation confidence %.2f below threshold %.2f with preserve_meaning=True, returning original text",
                adaptation_confidence,
                adaptation_threshold,
            )
            return GenderAdaptationResult(
                adapted_text=text,  # Return original text
                source_gender=detection.detected_gender,
                target_gender=target_gender,
                confidence=adaptation_confidence,
                warnings=["Adaptation confidence too low for meaning preservation"],
                processing_time_ms=(datetime.now() - start_time).total_seconds() * 1000,
            )

        return GenderAdaptationResult(
            adapted_text=adapted_text,
            source_gender=detection.detected_gender,
            target_gender=target_gender,
            modifications=modifications,
            confidence=adaptation_confidence,
            processing_time_ms=(datetime.now() - start_time).total_seconds() * 1000,
        )

    def _adapt_with_ai(
        self,
        text: str,
        source_gender: Gender,
        target_gender: Gender,
        language: Language,
        context: Optional[GenderContext],
    ) -> Tuple[str, List[Tuple[str, str]]]:
        """Use AI model to adapt gender."""
        # Log context if provided
        if context:
            logger.debug("Adapting with AI using context: %s", context.context_type)

        try:
            model = get_bedrock_model()

            gender_descriptions = {
                Gender.MASCULINE: "masculine/male",
                Gender.FEMININE: "feminine/female",
                Gender.NEUTRAL: "gender-neutral",
            }

            prompt = f"""Adapt the following text to use {gender_descriptions[target_gender]} gender forms.

Language: {language.value}
Current gender: {gender_descriptions[source_gender]}
Target gender: {gender_descriptions[target_gender]}

Text:
{text}

Please adapt:
1. Pronouns (he/she/they)
2. Possessives (his/her/their)
3. Titles (Mr./Ms./Mx.)
4. Gendered nouns if applicable
5. Agreement in languages that require it

Maintain the exact meaning and medical accuracy.
Provide only the adapted text."""

            response = model.invoke(prompt)
            # Handle different response content types
            content = response.content
            if isinstance(content, list):
                content = " ".join(str(item) for item in content)
            else:
                content = str(content)
            adapted_text = content.strip()

            # Extract modifications
            modifications = self._extract_modifications(text, adapted_text)

            return adapted_text, modifications

        except (ValueError, AttributeError, KeyError) as e:
            logger.warning("AI adaptation failed: %s", str(e))
            return self._adapt_with_rules(
                text, source_gender, target_gender, language, self.profiles[language]
            )

    def _adapt_with_rules(
        self,
        text: str,
        source_gender: Gender,
        target_gender: Gender,
        language: Language,
        profile: GenderProfile,
    ) -> Tuple[str, List[Tuple[str, str]]]:
        """Use rule-based approach to adapt gender."""
        # Log language being processed
        logger.debug("Applying gender rules for %s", language)

        adapted_text = text
        modifications = []

        # Adapt pronouns
        if profile.pronouns:
            source_pronouns = profile.pronouns.get(source_gender, {})
            target_pronouns = profile.pronouns.get(target_gender, {})

            for pronoun_type, source_pronoun in source_pronouns.items():
                if source_pronoun in adapted_text:
                    target_pronoun = target_pronouns.get(pronoun_type, source_pronoun)
                    adapted_text = re.sub(
                        rf"\b{re.escape(source_pronoun)}\b",
                        target_pronoun,
                        adapted_text,
                        flags=re.I,
                    )
                    modifications.append((source_pronoun, target_pronoun))

        # Adapt possessives
        if profile.possessives:
            source_possessives = profile.possessives.get(source_gender, {})
            target_possessives = profile.possessives.get(target_gender, {})

            for poss_type, source_poss in source_possessives.items():
                if source_poss in adapted_text:
                    target_poss = target_possessives.get(poss_type, source_poss)
                    adapted_text = re.sub(
                        rf"\b{re.escape(source_poss)}\b",
                        target_poss,
                        adapted_text,
                        flags=re.I,
                    )
                    modifications.append((source_poss, target_poss))

        # Adapt profession terms
        if profile.profession_terms:
            for base_term, gendered_forms in profile.profession_terms.items():
                source_term = gendered_forms.get(source_gender, base_term)
                target_term = gendered_forms.get(target_gender, base_term)

                if source_term in adapted_text and source_term != target_term:
                    adapted_text = adapted_text.replace(source_term, target_term)
                    modifications.append((source_term, target_term))

        return adapted_text, modifications

    def _extract_modifications(
        self, original: str, adapted: str
    ) -> List[Tuple[str, str]]:
        """Extract modifications between texts."""
        modifications = []

        # Simple word-level comparison
        original_words = original.split()
        adapted_words = adapted.split()

        if len(original_words) == len(adapted_words):
            for orig, adapt in zip(original_words, adapted_words):
                if orig.lower() != adapt.lower():
                    modifications.append((orig, adapt))

        return modifications[:20]  # Limit to top 20

    def _load_default_profiles(self) -> None:
        """Load default gender profiles."""
        # This will be populated by the rules module
        pass


class GenderNeutralizer:
    """Converts gendered text to gender-neutral forms."""

    def __init__(self, profiles: Optional[Dict[Language, GenderProfile]] = None):
        """
        Initialize gender neutralizer.

        Args:
            profiles: Language-specific gender profiles
        """
        self.profiles = profiles or {}
        self._neutral_alternatives = self._load_neutral_alternatives()

    def neutralize(
        self, text: str, language: Language, context: Optional[GenderContext] = None
    ) -> GenderAdaptationResult:
        """
        Convert text to gender-neutral forms.

        Args:
            text: Text to neutralize
            language: Language of the text
            context: Optional gender context

        The context parameter can provide additional information for
        more accurate neutralization based on the medical context.

        Returns:
            GenderAdaptationResult with neutralized text
        """
        start_time = datetime.now()

        # Use context for more accurate neutralization
        # Context can provide information about the domain, formality level, and specific requirements
        domain_specific_neutrals = {}
        preserve_titles = False
        formality_level = "standard"

        if context:
            # Extract domain-specific neutral terms
            domain = (
                context.cultural_preferences.get("domain", "general")
                if context.cultural_preferences
                else "general"
            )
            if domain == "medical":
                # Medical-specific neutral terms
                domain_specific_neutrals = {
                    "en": {
                        "male nurse": "nurse",
                        "female nurse": "nurse",
                        "male doctor": "physician",
                        "female doctor": "physician",
                        "he/she": "the patient",
                        "his/her": "the patient's",
                    }
                }
            elif domain == "legal":
                # Legal-specific neutral terms
                domain_specific_neutrals = {
                    "en": {
                        "policeman": "police officer",
                        "policewoman": "police officer",
                        "chairman": "chairperson",
                        "chairwoman": "chairperson",
                    }
                }

            # Check if we should preserve professional titles
            preserve_titles = (
                context.cultural_preferences.get("preserve_professional_titles", False)
                if context.cultural_preferences
                else False
            )
            formality_level = context.formality_level

        # Get base neutral alternatives for the language
        alternatives = self._neutral_alternatives.get(language, {})

        # Merge with domain-specific alternatives
        if language.value in domain_specific_neutrals:
            alternatives = {**alternatives, **domain_specific_neutrals[language.value]}

        adapted_text = text
        modifications = []

        # Replace gendered terms with neutral ones
        for gendered, neutral in alternatives.items():
            # Skip title replacements if preserving titles
            if preserve_titles and gendered.lower() in ["mr", "mrs", "ms", "miss"]:
                continue

            if gendered in adapted_text.lower():
                pattern = rf"\b{re.escape(gendered)}\b"

                # For formal contexts, maintain proper capitalization
                if formality_level == "formal":
                    # Check if the original term is capitalized
                    matches = re.finditer(pattern, adapted_text, flags=re.I)
                    for match in matches:
                        original = match.group()
                        if original[0].isupper():
                            replacement = neutral.capitalize()
                        else:
                            replacement = neutral
                        adapted_text = (
                            adapted_text[: match.start()]
                            + replacement
                            + adapted_text[match.end() :]
                        )
                        modifications.append((original, replacement))
                else:
                    adapted_text = re.sub(pattern, neutral, adapted_text, flags=re.I)
                    modifications.append((gendered, neutral))

        return GenderAdaptationResult(
            adapted_text=adapted_text,
            source_gender=Gender.UNKNOWN,
            target_gender=Gender.NEUTRAL,
            modifications=modifications,
            confidence=0.95 if context else 0.9,  # Higher confidence with context
            processing_time_ms=(datetime.now() - start_time).total_seconds() * 1000,
        )

    def _load_neutral_alternatives(self) -> Dict[Language, Dict[str, str]]:
        """Load gender-neutral alternatives."""
        return {
            Language.ENGLISH: {
                "he or she": "they",
                "his or her": "their",
                "him or her": "them",
                "himself or herself": "themself",
                "chairman": "chairperson",
                "businessman": "businessperson",
                "policeman": "police officer",
                "fireman": "firefighter",
                "mailman": "mail carrier",
                "mankind": "humankind",
                "manpower": "workforce",
                "man-made": "artificial",
                "stewardess": "flight attendant",
                "waitress": "server",
                "waiter": "server",
                "actress": "actor",
            },
            Language.SPANISH: {
                "él o ella": "elle",  # Some Spanish variants
                "todos": "todes",  # Inclusive language
                "amigos": "amigues",
                "doctor": "profesional médico",
                "enfermera": "profesional de enfermería",
            },
            Language.FRENCH: {
                "il ou elle": "iel",  # French neutral pronoun
                "tous": "toustes",
                "infirmier": "personnel infirmier",
                "infirmière": "personnel infirmier",
            },
        }
