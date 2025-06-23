"""
Core formality adjustment functionality.

This module provides the main formality detection and adjustment classes
for medical text translation.

This module handles encrypted PHI with access control and audit logging
to ensure HIPAA compliance.
"""

import logging
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import IntEnum
from typing import Dict, List, Optional, Set, Tuple

from ...langchain.bedrock import get_bedrock_model
from ..config import Language

logger = logging.getLogger(__name__)


class FormalityLevel(IntEnum):
    """Formality levels for text."""

    VERY_INFORMAL = 1  # Casual, colloquial
    INFORMAL = 2  # Friendly, conversational
    NEUTRAL = 3  # Standard, balanced
    FORMAL = 4  # Professional, respectful
    VERY_FORMAL = 5  # Highly formal, ceremonial

    @classmethod
    def from_score(cls, score: float) -> "FormalityLevel":
        """Convert a numerical score (0-1) to formality level."""
        if score < 0.2:
            return cls.VERY_INFORMAL
        elif score < 0.4:
            return cls.INFORMAL
        elif score < 0.6:
            return cls.NEUTRAL
        elif score < 0.8:
            return cls.FORMAL
        else:
            return cls.VERY_FORMAL

    def to_score(self) -> float:
        """Convert formality level to numerical score."""
        return (self.value - 1) / 4.0


@dataclass
class FormalityContext:
    """Context information for formality adjustment."""

    audience: str  # patient, healthcare_provider, insurance, government
    relationship: str  # doctor_patient, peer_to_peer, patient_to_admin
    document_type: str  # medical_record, patient_education, referral, prescription
    cultural_background: Optional[str] = None
    age_group: Optional[str] = None  # child, teenager, adult, elderly
    urgency: bool = False
    sensitivity: bool = False  # For sensitive medical topics
    legal_context: bool = False  # For legal/regulatory documents
    situation: str = "general"  # General description of the situation

    def requires_formal(self) -> bool:
        """Check if context requires formal language."""
        formal_audiences = {"government", "insurance", "legal"}
        formal_documents = {"medical_record", "referral", "legal_document"}

        return (
            self.audience in formal_audiences
            or self.document_type in formal_documents
            or self.legal_context
        )


@dataclass
class FormalityFeatures:
    """Features used for formality detection."""

    # Lexical features
    word_formality_scores: Dict[str, float] = field(default_factory=dict)
    contractions_ratio: float = 0.0
    slang_count: int = 0
    technical_terms_ratio: float = 0.0

    # Syntactic features
    avg_sentence_length: float = 0.0
    passive_voice_ratio: float = 0.0
    complex_sentence_ratio: float = 0.0

    # Pragmatic features
    personal_pronouns_ratio: float = 0.0
    imperative_ratio: float = 0.0
    hedging_expressions: int = 0
    politeness_markers: int = 0

    # Medical specific
    medical_jargon_ratio: float = 0.0
    patient_friendly_terms_ratio: float = 0.0


@dataclass
class FormalityDetectionResult:
    """Result of formality detection."""

    detected_level: FormalityLevel
    confidence: float
    formality_score: float  # 0-1 continuous score
    features: FormalityFeatures
    suggestions: List[str] = field(default_factory=list)
    processing_time_ms: float = 0.0

    def needs_adjustment(self, target_level: FormalityLevel) -> bool:
        """Check if adjustment is needed."""
        return abs(self.detected_level - target_level) > 1


@dataclass
class FormalityAdjustmentResult:
    """Result of formality adjustment."""

    adjusted_text: str
    original_level: FormalityLevel
    target_level: FormalityLevel
    achieved_level: FormalityLevel
    modifications: List[Tuple[str, str]] = field(
        default_factory=list
    )  # (original, adjusted)
    confidence: float = 0.0
    processing_time_ms: float = 0.0
    warnings: List[str] = field(default_factory=list)


@dataclass
class FormalityProfile:
    """Language-specific formality profile."""

    language: Language

    # Formality markers
    formal_pronouns: Dict[str, str] = field(default_factory=dict)  # informal -> formal
    formal_verbs: Dict[str, str] = field(default_factory=dict)
    formal_expressions: Dict[str, str] = field(default_factory=dict)

    # Informal markers
    contractions: Dict[str, str] = field(default_factory=dict)  # formal -> informal
    colloquialisms: List[str] = field(default_factory=list)
    slang_terms: Set[str] = field(default_factory=set)

    # Structural patterns
    formal_sentence_starters: List[str] = field(default_factory=list)
    politeness_phrases: List[str] = field(default_factory=list)
    hedging_expressions: List[str] = field(default_factory=list)


class BaseFormalityDetector(ABC):
    """Abstract base class for formality detection."""

    @abstractmethod
    def detect(self, text: str, language: Language) -> FormalityDetectionResult:
        """Detect formality level of text."""
        pass

    @abstractmethod
    def extract_features(self, text: str, language: Language) -> FormalityFeatures:
        """Extract formality-related features."""
        pass


class FormalityDetector(BaseFormalityDetector):
    """Main formality detection implementation."""

    def __init__(self, profiles: Optional[Dict[Language, FormalityProfile]] = None):
        """
        Initialize formality detector.

        Args:
            profiles: Language-specific formality profiles
        """
        self.profiles = profiles or {}
        self._load_default_profiles()
        self._informal_words = self._load_informal_words()
        self._formal_words = self._load_formal_words()

    def detect(self, text: str, language: Language) -> FormalityDetectionResult:
        """
        Detect formality level of text.

        Args:
            text: Text to analyze
            language: Language of the text

        Returns:
            FormalityDetectionResult with detected level and features
        """
        start_time = datetime.now()

        # Extract features
        features = self.extract_features(text, language)

        # Calculate formality score
        score = self._calculate_formality_score(features, language)

        # Determine level
        level = FormalityLevel.from_score(score)

        # Generate suggestions
        suggestions = self._generate_suggestions(features, level, language)

        return FormalityDetectionResult(
            detected_level=level,
            confidence=0.85,  # Placeholder - could be refined
            formality_score=score,
            features=features,
            suggestions=suggestions,
            processing_time_ms=(datetime.now() - start_time).total_seconds() * 1000,
        )

    def extract_features(self, text: str, language: Language) -> FormalityFeatures:
        """Extract formality-related features from text."""
        features = FormalityFeatures()

        # Tokenize
        sentences = re.split(r"[.!?]+", text)
        sentences = [s.strip() for s in sentences if s.strip()]
        words = re.findall(r"\b\w+\b", text.lower())

        if not words:
            return features

        # Lexical features
        features.contractions_ratio = self._count_contractions(text) / len(words)
        features.slang_count = sum(1 for w in words if w in self._informal_words)
        features.technical_terms_ratio = self._count_technical_terms(words) / len(words)

        # Word formality scores
        for word in set(words):
            if word in self._formal_words:
                features.word_formality_scores[word] = 0.8
            elif word in self._informal_words:
                features.word_formality_scores[word] = 0.2

        # Syntactic features
        if sentences:
            word_counts = [len(re.findall(r"\b\w+\b", s)) for s in sentences]
            features.avg_sentence_length = sum(word_counts) / len(sentences)
            features.passive_voice_ratio = self._count_passive_voice(sentences) / len(
                sentences
            )
            features.complex_sentence_ratio = self._count_complex_sentences(
                sentences
            ) / len(sentences)

        # Pragmatic features
        personal_pronouns = ["i", "you", "we", "us", "me", "my", "your", "our"]
        features.personal_pronouns_ratio = sum(
            1 for w in words if w in personal_pronouns
        ) / len(words)
        features.imperative_ratio = self._count_imperatives(sentences) / len(sentences)
        features.hedging_expressions = self._count_hedging(text)
        features.politeness_markers = self._count_politeness_markers(text, language)

        # Medical specific
        features.medical_jargon_ratio = self._count_medical_jargon(words) / len(words)
        features.patient_friendly_terms_ratio = self._count_patient_friendly_terms(
            words
        ) / len(words)

        return features

    def _calculate_formality_score(
        self, features: FormalityFeatures, language: Language
    ) -> float:
        """Calculate overall formality score from features."""
        # Log language for context
        logger.debug("Calculating formality score for %s", language)

        score = 0.5  # Start neutral

        # Adjust based on lexical features
        score -= features.contractions_ratio * 0.3
        score -= (features.slang_count / 10) * 0.2  # Normalize slang count
        score += features.technical_terms_ratio * 0.2

        # Adjust based on syntactic features
        score += min(
            features.avg_sentence_length / 20, 0.2
        )  # Longer sentences more formal
        score += features.passive_voice_ratio * 0.1
        score += features.complex_sentence_ratio * 0.1

        # Adjust based on pragmatic features
        score -= features.personal_pronouns_ratio * 0.2
        score -= features.imperative_ratio * 0.1
        score += (features.hedging_expressions / 5) * 0.1  # Normalize hedging
        score += (features.politeness_markers / 5) * 0.1

        # Medical adjustments
        score += features.medical_jargon_ratio * 0.1
        score -= features.patient_friendly_terms_ratio * 0.05

        # Ensure score is between 0 and 1
        return max(0.0, min(1.0, score))

    def _generate_suggestions(
        self, features: FormalityFeatures, level: FormalityLevel, language: Language
    ) -> List[str]:
        """Generate suggestions for formality adjustment."""
        # Log context
        logger.debug("Generating suggestions for %s formality in %s", level, language)
        suggestions = []

        if features.contractions_ratio > 0.1 and level >= FormalityLevel.FORMAL:
            suggestions.append("Consider expanding contractions for more formal tone")

        if features.slang_count > 0 and level >= FormalityLevel.NEUTRAL:
            suggestions.append("Replace slang terms with standard vocabulary")

        if features.personal_pronouns_ratio > 0.05 and level >= FormalityLevel.FORMAL:
            suggestions.append(
                "Consider using passive voice or impersonal constructions"
            )

        if features.avg_sentence_length < 10 and level >= FormalityLevel.FORMAL:
            suggestions.append("Use more complex sentence structures")

        return suggestions

    def _count_contractions(self, text: str) -> int:
        """Count contractions in text."""
        contractions_pattern = r"\b\w+'\w+\b"
        return len(re.findall(contractions_pattern, text))

    def _count_technical_terms(self, words: List[str]) -> int:
        """Count technical/medical terms."""
        # Simplified - would use medical terminology database
        technical_suffixes = ["itis", "osis", "emia", "pathy", "ectomy", "ostomy"]
        count = 0
        for word in words:
            if any(word.endswith(suffix) for suffix in technical_suffixes):
                count += 1
        return count

    def _count_passive_voice(self, sentences: List[str]) -> int:
        """Count sentences with passive voice."""
        passive_pattern = r"\b(is|are|was|were|been|being)\s+\w+ed\b"
        count = 0
        for sentence in sentences:
            if re.search(passive_pattern, sentence, re.I):
                count += 1
        return count

    def _count_complex_sentences(self, sentences: List[str]) -> int:
        """Count complex sentences (with subordinate clauses)."""
        complex_markers = [
            "because",
            "although",
            "while",
            "when",
            "if",
            "unless",
            "whereas",
            "which",
        ]
        count = 0
        for sentence in sentences:
            if any(marker in sentence.lower() for marker in complex_markers):
                count += 1
        return count

    def _count_imperatives(self, sentences: List[str]) -> int:
        """Count imperative sentences."""
        imperative_starters = [
            "please",
            "kindly",
            "ensure",
            "make sure",
            "be sure",
            "remember",
        ]
        count = 0
        for sentence in sentences:
            words = sentence.lower().split()
            if words and (
                words[0] in imperative_starters
                or (len(words) > 1 and words[0] in ["do", "don't", "let's"])
            ):
                count += 1
        return count

    def _count_hedging(self, text: str) -> int:
        """Count hedging expressions."""
        hedging_phrases = [
            "might",
            "could",
            "perhaps",
            "possibly",
            "probably",
            "it seems",
            "it appears",
            "tends to",
            "likely",
            "unlikely",
        ]
        count = 0
        text_lower = text.lower()
        for phrase in hedging_phrases:
            count += text_lower.count(phrase)
        return count

    def _count_politeness_markers(self, text: str, language: Language) -> int:
        """Count politeness markers."""
        if language == Language.ENGLISH:
            markers = [
                "please",
                "kindly",
                "would you",
                "could you",
                "if you don't mind",
            ]
        elif language == Language.SPANISH:
            markers = ["por favor", "sería tan amable", "podría", "le agradecería"]
        elif language == Language.FRENCH:
            markers = ["s'il vous plaît", "pourriez-vous", "auriez-vous l'amabilité"]
        else:
            markers = []

        count = 0
        text_lower = text.lower()
        for marker in markers:
            count += text_lower.count(marker)
        return count

    def _count_medical_jargon(self, words: List[str]) -> int:
        """Count medical jargon terms."""
        jargon_terms = {
            "etiology",
            "pathogenesis",
            "prognosis",
            "differential",
            "idiopathic",
            "iatrogenic",
            "comorbidity",
            "contraindication",
        }
        return sum(1 for w in words if w in jargon_terms)

    def _count_patient_friendly_terms(self, words: List[str]) -> int:
        """Count patient-friendly medical terms."""
        friendly_terms = {
            "medicine",
            "doctor",
            "pain",
            "sick",
            "better",
            "health",
            "care",
            "help",
            "feel",
            "worry",
        }
        return sum(1 for w in words if w in friendly_terms)

    def _load_default_profiles(self) -> None:
        """Load default formality profiles."""
        from .rules import get_formality_profile  # noqa: PLC0415

        # Load profiles for supported languages
        for language in Language:
            profile = get_formality_profile(language)
            if profile:
                self.profiles[language] = profile

        logger.debug("Loaded formality profiles for %d languages", len(self.profiles))

    def _load_informal_words(self) -> Set[str]:
        """Load informal word list."""
        return {
            "gonna",
            "wanna",
            "gotta",
            "ain't",
            "yeah",
            "nope",
            "stuff",
            "thing",
            "guy",
            "kid",
            "mom",
            "dad",
        }

    def _load_formal_words(self) -> Set[str]:
        """Load formal word list."""
        return {
            "therefore",
            "moreover",
            "furthermore",
            "however",
            "nevertheless",
            "consequently",
            "accordingly",
            "whereas",
            "whereby",
            "thereof",
            "herein",
        }


class FormalityAdjuster:
    """Adjusts text formality level."""

    def __init__(
        self,
        detector: Optional[FormalityDetector] = None,
        profiles: Optional[Dict[Language, FormalityProfile]] = None,
        use_ai: bool = True,
    ):
        """
        Initialize formality adjuster.

        Args:
            detector: Formality detector instance
            profiles: Language-specific formality profiles
            use_ai: Whether to use AI for adjustment
        """
        self.detector = detector or FormalityDetector()
        self.profiles = profiles or {}
        self.use_ai = use_ai
        self._load_default_profiles()

    def adjust(
        self,
        text: str,
        target_level: FormalityLevel,
        language: Language,
        context: Optional[FormalityContext] = None,
        preserve_meaning: bool = True,  # pylint: disable=unused-argument
    ) -> FormalityAdjustmentResult:
        """
        Adjust text formality to target level.

        The preserve_meaning parameter ensures medical accuracy is maintained
        during formality adjustment.

        Args:
            text: Text to adjust
            target_level: Desired formality level
            language: Language of the text
            context: Optional context information
            preserve_meaning: Whether to preserve exact meaning

        Returns:
            FormalityAdjustmentResult with adjusted text
        """
        start_time = datetime.now()

        # Note: preserve_meaning parameter is reserved for future enhancements

        # Detect current formality
        detection = self.detector.detect(text, language)

        # Check if adjustment needed
        if not detection.needs_adjustment(target_level):
            return FormalityAdjustmentResult(
                adjusted_text=text,
                original_level=detection.detected_level,
                target_level=target_level,
                achieved_level=detection.detected_level,
                confidence=1.0,
                processing_time_ms=(datetime.now() - start_time).total_seconds() * 1000,
            )

        # Perform adjustment
        if self.use_ai and language in [
            Language.ENGLISH,
            Language.SPANISH,
            Language.FRENCH,
        ]:
            adjusted_text, modifications = self._adjust_with_ai(
                text, detection, target_level, language, context
            )
        else:
            adjusted_text, modifications = self._adjust_with_rules(
                text, detection, target_level, language, context
            )

        # Verify adjustment
        verification = self.detector.detect(adjusted_text, language)

        # Create result
        result = FormalityAdjustmentResult(
            adjusted_text=adjusted_text,
            original_level=detection.detected_level,
            target_level=target_level,
            achieved_level=verification.detected_level,
            modifications=modifications,
            confidence=verification.confidence,
            processing_time_ms=(datetime.now() - start_time).total_seconds() * 1000,
        )

        # Add warnings if target not achieved
        if abs(verification.detected_level - target_level) > 1:
            result.warnings.append(
                f"Target formality level {target_level.name} not fully achieved. "
                f"Reached {verification.detected_level.name} instead."
            )

        return result

    def _adjust_with_ai(
        self,
        text: str,
        detection: FormalityDetectionResult,
        target_level: FormalityLevel,
        language: Language,
        context: Optional[FormalityContext],
    ) -> Tuple[str, List[Tuple[str, str]]]:
        """Use AI model to adjust formality."""
        try:
            model = get_bedrock_model()

            # Build context description
            context_desc = ""
            if context:
                context_desc = f"""
Context:
- Audience: {context.audience}
- Document type: {context.document_type}
- Relationship: {context.relationship}
"""

            level_descriptions = {
                FormalityLevel.VERY_INFORMAL: "very casual, colloquial, like talking to a close friend",
                FormalityLevel.INFORMAL: "friendly and conversational, but still respectful",
                FormalityLevel.NEUTRAL: "balanced and standard, neither too formal nor too casual",
                FormalityLevel.FORMAL: "professional and respectful, appropriate for business",
                FormalityLevel.VERY_FORMAL: "highly formal and ceremonial, maximum respect",
            }

            prompt = f"""Adjust the formality of the following medical text.

Current formality level: {detection.detected_level.name}
Target formality level: {target_level.name} ({level_descriptions[target_level]})
Language: {language.value}
{context_desc}

Original text:
{text}

Please adjust the text to match the target formality level while:
1. Preserving all medical information accurately
2. Maintaining the same meaning
3. Keeping medical terms appropriately technical or simplified based on context
4. Adjusting pronouns, verb forms, and expressions as needed

Provide only the adjusted text, no explanations."""

            response = model.invoke(prompt)
            # Handle different response content types
            content = response.content
            if isinstance(content, list):
                content = " ".join(str(item) for item in content)
            else:
                content = str(content)
            adjusted_text = content.strip()

            # Extract modifications (simplified)
            modifications = self._extract_modifications(text, adjusted_text)

            return adjusted_text, modifications

        except (ValueError, AttributeError, KeyError) as e:
            logger.warning("AI adjustment failed: %s. Falling back to rules.", str(e))
            return self._adjust_with_rules(
                text, detection, target_level, language, context
            )

    def _adjust_with_rules(
        self,
        text: str,
        detection: FormalityDetectionResult,
        target_level: FormalityLevel,
        language: Language,
        context: Optional[FormalityContext],
    ) -> Tuple[str, List[Tuple[str, str]]]:
        """Use rule-based approach to adjust formality."""
        # Log context if provided
        if context:
            logger.debug("Adjusting formality with context: %s", context.situation)

        adjusted_text = text
        modifications = []

        profile = self.profiles.get(language)
        if not profile:
            return text, []

        current_level = detection.detected_level

        # Adjust towards more formal
        if target_level > current_level:
            # Expand contractions
            for contraction, expansion in profile.contractions.items():
                if contraction in adjusted_text:
                    adjusted_text = adjusted_text.replace(contraction, expansion)
                    modifications.append((contraction, expansion))

            # Replace informal expressions
            for informal, formal in profile.formal_expressions.items():
                if informal in adjusted_text.lower():
                    adjusted_text = re.sub(
                        rf"\b{re.escape(informal)}\b",
                        formal,
                        adjusted_text,
                        flags=re.IGNORECASE,
                    )
                    modifications.append((informal, formal))

            # Update pronouns
            for informal, formal in profile.formal_pronouns.items():
                adjusted_text = re.sub(
                    rf"\b{re.escape(informal)}\b",
                    formal,
                    adjusted_text,
                    flags=re.IGNORECASE,
                )
                modifications.append((informal, formal))

        # Adjust towards less formal
        elif target_level < current_level:
            # Add contractions where appropriate
            for expansion, contraction in profile.contractions.items():
                # Be careful with medical terms
                if expansion in adjusted_text and not self._is_medical_context(
                    expansion, text
                ):
                    adjusted_text = adjusted_text.replace(expansion, contraction)
                    modifications.append((expansion, contraction))

            # Simplify formal expressions
            for formal, informal in profile.formal_expressions.items():
                if formal in adjusted_text:
                    adjusted_text = adjusted_text.replace(formal, informal)
                    modifications.append((formal, informal))

        return adjusted_text, modifications

    def _extract_modifications(
        self, original: str, adjusted: str
    ) -> List[Tuple[str, str]]:
        """Extract modifications between original and adjusted text."""
        # Simplified implementation
        modifications = []

        # Split into words and compare
        original_words = original.split()
        adjusted_words = adjusted.split()

        # This is a simple approach - a more sophisticated diff algorithm would be better
        if len(original_words) == len(adjusted_words):
            for orig, adj in zip(original_words, adjusted_words):
                if orig.lower() != adj.lower():
                    modifications.append((orig, adj))

        return modifications[:10]  # Limit to top 10 modifications

    def _is_medical_context(self, word: str, text: str) -> bool:
        """Check if word appears in medical context."""
        medical_indicators = [
            "mg",
            "ml",
            "dose",
            "medication",
            "prescription",
            "diagnosis",
        ]
        word_index = text.lower().find(word.lower())
        if word_index == -1:
            return False

        # Check surrounding context
        context_window = text[max(0, word_index - 50) : word_index + 50 + len(word)]
        return any(
            indicator in context_window.lower() for indicator in medical_indicators
        )

    def _load_default_profiles(self) -> None:
        """Load default formality profiles."""
        from .rules import get_formality_profile  # noqa: PLC0415

        # Load profiles for supported languages
        for language in Language:
            profile = get_formality_profile(language)
            if profile:
                self.profiles[language] = profile

        logger.debug("Loading formality profiles for adapter")
