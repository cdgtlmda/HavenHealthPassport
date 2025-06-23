"""
AWS Comprehend Integration for Sentiment and Tone Preservation.

This module ensures that emotional tone and sentiment are preserved
during medical translations, especially important for patient communications.
"""

import asyncio
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import boto3
from botocore.exceptions import ClientError

from src.healthcare.hipaa_access_control import AccessLevel, require_phi_access
from src.utils.logging import get_logger

logger = get_logger(__name__)


class Sentiment(str, Enum):
    """Sentiment types detected by Comprehend."""

    POSITIVE = "POSITIVE"
    NEGATIVE = "NEGATIVE"
    NEUTRAL = "NEUTRAL"
    MIXED = "MIXED"


class EmotionalTone(str, Enum):
    """Emotional tones in medical communications."""

    EMPATHETIC = "empathetic"
    REASSURING = "reassuring"
    URGENT = "urgent"
    INFORMATIVE = "informative"
    CAUTIONARY = "cautionary"
    SUPPORTIVE = "supportive"


@dataclass
class SentimentAnalysis:
    """Result of sentiment analysis."""

    sentiment: Sentiment
    confidence_scores: Dict[str, float]
    dominant_language: str
    key_phrases: List[str]
    entities: List[Dict[str, Any]]


@dataclass
class TonePreservationResult:
    """Result of tone preservation validation."""

    source_sentiment: SentimentAnalysis
    target_sentiment: SentimentAnalysis
    tone_preserved: bool
    tone_shift: Optional[str]
    confidence: float
    recommendations: List[str]


class ComprehendTonePreserver:
    """Preserves sentiment and tone in medical translations."""

    # Sentiment preservation thresholds
    SENTIMENT_MATCH_THRESHOLD = 0.7
    CONFIDENCE_THRESHOLD = 0.8

    # Medical context sentiment mappings
    MEDICAL_TONE_MAPPINGS = {
        "diagnosis_delivery": {
            "preferred_tone": EmotionalTone.EMPATHETIC,
            "avoid_tones": ["blunt", "dismissive"],
            "key_phrases": ["I understand", "We will support", "Together we can"],
        },
        "treatment_explanation": {
            "preferred_tone": EmotionalTone.INFORMATIVE,
            "avoid_tones": ["overly_technical", "condescending"],
            "key_phrases": ["This means", "In simple terms", "What this does"],
        },
        "emergency_instructions": {
            "preferred_tone": EmotionalTone.URGENT,
            "required_elements": ["immediate", "now", "urgent"],
            "preserve_intensity": True,
        },
        "follow_up_care": {
            "preferred_tone": EmotionalTone.REASSURING,
            "key_phrases": [
                "You're doing well",
                "Normal part of recovery",
                "Expected progress",
            ],
        },
    }

    def __init__(self, region: str = "us-east-1"):
        """
        Initialize Comprehend tone preserver.

        Args:
            region: AWS region for Comprehend
        """
        self.comprehend = boto3.client("comprehend", region_name=region)
        self._sentiment_cache: Dict[str, Any] = {}

    @require_phi_access(AccessLevel.READ)
    async def preserve_tone(
        self,
        source_text: str,
        source_lang: str,
        translated_text: str,
        target_lang: str,
        context_type: Optional[str] = None,
    ) -> TonePreservationResult:
        """
        Validate that tone is preserved in translation.

        Args:
            source_text: Original text
            source_lang: Source language code
            translated_text: Translated text
            target_lang: Target language code
            context_type: Type of medical context

        Returns:
            Tone preservation analysis result
        """
        try:
            # Analyze sentiment in both texts
            source_sentiment = await self._analyze_sentiment(source_text, source_lang)
            target_sentiment = await self._analyze_sentiment(
                translated_text, target_lang
            )

            # Compare sentiments
            tone_preserved, tone_shift = self._compare_sentiments(
                source_sentiment, target_sentiment
            )

            # Calculate confidence
            confidence = self._calculate_confidence(source_sentiment, target_sentiment)

            # Generate recommendations
            recommendations = self._generate_recommendations(
                source_sentiment, target_sentiment, context_type, tone_preserved
            )

            return TonePreservationResult(
                source_sentiment=source_sentiment,
                target_sentiment=target_sentiment,
                tone_preserved=tone_preserved,
                tone_shift=tone_shift,
                confidence=confidence,
                recommendations=recommendations,
            )

        except (ValueError, AttributeError, RuntimeError) as e:
            logger.error(f"Error preserving tone: {e}")
            # Return neutral result on error
            neutral_sentiment = SentimentAnalysis(
                sentiment=Sentiment.NEUTRAL,
                confidence_scores={"NEUTRAL": 1.0},
                dominant_language=source_lang,
                key_phrases=[],
                entities=[],
            )

            return TonePreservationResult(
                source_sentiment=neutral_sentiment,
                target_sentiment=neutral_sentiment,
                tone_preserved=False,
                tone_shift="unknown",
                confidence=0.0,
                recommendations=["Error analyzing sentiment"],
            )

    async def _analyze_sentiment(self, text: str, language: str) -> SentimentAnalysis:
        """Analyze sentiment of text."""
        # Check cache
        cache_key = f"{hash(text)}:{language}"
        if cache_key in self._sentiment_cache:
            cached_result = self._sentiment_cache[cache_key]
            if isinstance(cached_result, SentimentAnalysis):
                return cached_result

        try:
            # Call AWS Comprehend
            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.comprehend.detect_sentiment(
                    Text=text, LanguageCode=self._map_language_code(language)
                ),
            )

            # Extract key phrases
            key_phrases_response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.comprehend.detect_key_phrases(
                    Text=text, LanguageCode=self._map_language_code(language)
                ),
            )

            # Extract entities
            entities_response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.comprehend.detect_entities(
                    Text=text, LanguageCode=self._map_language_code(language)
                ),
            )

            analysis = SentimentAnalysis(
                sentiment=Sentiment(response["Sentiment"]),
                confidence_scores=response["SentimentScore"],
                dominant_language=language,
                key_phrases=[
                    kp["Text"] for kp in key_phrases_response.get("KeyPhrases", [])
                ],
                entities=entities_response.get("Entities", []),
            )

            # Cache result
            self._sentiment_cache[cache_key] = analysis

            return analysis

        except ClientError as e:
            logger.error(f"AWS Comprehend error: {e}")
            # Return neutral sentiment on error
            return SentimentAnalysis(
                sentiment=Sentiment.NEUTRAL,
                confidence_scores={"NEUTRAL": 1.0},
                dominant_language=language,
                key_phrases=[],
                entities=[],
            )

    def _map_language_code(self, language: str) -> str:
        """Map language codes to AWS Comprehend supported codes."""
        # Comprehend supports limited languages
        supported_mappings = {
            "en": "en",
            "es": "es",
            "fr": "fr",
            "de": "de",
            "it": "it",
            "pt": "pt",
            "ar": "ar",
            "hi": "hi",
            "ja": "ja",
            "ko": "ko",
            "zh": "zh",
            "zh-TW": "zh-TW",
        }

        return supported_mappings.get(language, "en")

    def _compare_sentiments(
        self, source: SentimentAnalysis, target: SentimentAnalysis
    ) -> Tuple[bool, Optional[str]]:
        """Compare source and target sentiments."""
        # Check if sentiments match
        if source.sentiment == target.sentiment:
            return True, None

        # Check if sentiments are compatible
        compatible_shifts = {
            (Sentiment.NEGATIVE, Sentiment.NEUTRAL): "softened",
            (Sentiment.NEUTRAL, Sentiment.POSITIVE): "enhanced",
            (Sentiment.MIXED, Sentiment.NEUTRAL): "clarified",
            (Sentiment.MIXED, Sentiment.POSITIVE): "positive_clarified",
            (Sentiment.MIXED, Sentiment.NEGATIVE): "negative_clarified",
        }

        shift = compatible_shifts.get((source.sentiment, target.sentiment))
        if shift:
            # Some shifts might be acceptable in medical context
            return True, shift

        # Incompatible shift
        shift_description = f"{source.sentiment.value} → {target.sentiment.value}"
        return False, shift_description

    def _calculate_confidence(
        self, source: SentimentAnalysis, target: SentimentAnalysis
    ) -> float:
        """Calculate confidence in tone preservation."""
        # Get dominant sentiment scores
        source_score = source.confidence_scores.get(source.sentiment.value, 0)
        target_score = target.confidence_scores.get(target.sentiment.value, 0)

        # Calculate similarity
        if source.sentiment == target.sentiment:
            # Same sentiment - check score similarity
            score_diff = abs(source_score - target_score)
            confidence = 1.0 - score_diff
        else:
            # Different sentiments - lower confidence
            confidence = 0.5 * min(source_score, target_score)

        return max(0.0, min(1.0, confidence))

    def _generate_recommendations(
        self,
        source: SentimentAnalysis,
        target: SentimentAnalysis,
        context_type: Optional[str],
        tone_preserved: bool,
    ) -> List[str]:
        """Generate recommendations for improving tone preservation."""
        recommendations = []

        if not tone_preserved:
            recommendations.append(
                f"Tone shift detected: {source.sentiment.value} → {target.sentiment.value}"
            )

            # Suggest adjustments based on context
            if context_type in self.MEDICAL_TONE_MAPPINGS:
                context_config = self.MEDICAL_TONE_MAPPINGS[context_type]

                # Check for required phrases
                if isinstance(context_config, dict) and "key_phrases" in context_config:
                    missing_phrases = []
                    key_phrases = context_config.get("key_phrases", [])
                    if isinstance(key_phrases, list):
                        for phrase in key_phrases:
                            if not any(
                                phrase.lower() in kp.lower()
                                for kp in target.key_phrases
                            ):
                                missing_phrases.append(phrase)

                    if missing_phrases:
                        recommendations.append(
                            f"Consider including: {', '.join(missing_phrases)}"
                        )

            # General recommendations
            if (
                source.sentiment == Sentiment.POSITIVE
                and target.sentiment != Sentiment.POSITIVE
            ):
                recommendations.append(
                    "Add reassuring language to maintain positive tone"
                )

            elif (
                source.sentiment == Sentiment.NEGATIVE
                and target.sentiment == Sentiment.NEUTRAL
            ):
                recommendations.append(
                    "Ensure serious concerns are adequately conveyed"
                )

        # Check confidence
        if (
            target.confidence_scores.get(target.sentiment.value, 0)
            < self.CONFIDENCE_THRESHOLD
        ):
            recommendations.append(
                "Translation sentiment is ambiguous - consider clarifying"
            )

        return recommendations

    async def suggest_tone_adjustments(
        self, text: str, target_tone: EmotionalTone, language: str
    ) -> List[str]:
        """
        Suggest adjustments to achieve target tone.

        Args:
            text: Text to adjust
            target_tone: Desired emotional tone
            language: Language code

        Returns:
            List of suggested adjustments
        """
        suggestions = []

        # Analyze current sentiment
        current = await self._analyze_sentiment(text, language)

        # Get tone requirements
        tone_phrases = {
            EmotionalTone.EMPATHETIC: [
                "I understand how you feel",
                "This must be difficult",
                "We're here to help",
            ],
            EmotionalTone.REASSURING: [
                "This is completely normal",
                "You're making good progress",
                "There's no need to worry",
            ],
            EmotionalTone.URGENT: [
                "It's important to act now",
                "Please seek help immediately",
                "This requires urgent attention",
            ],
            EmotionalTone.SUPPORTIVE: [
                "We'll work through this together",
                "You're not alone",
                "We're here every step of the way",
            ],
        }

        # Check if target tone phrases are present
        if target_tone in tone_phrases:
            target_phrases = tone_phrases[target_tone]
            text_lower = text.lower()

            missing_tone = True
            for phrase in target_phrases:
                if phrase.lower() in text_lower:
                    missing_tone = False
                    break

            if missing_tone:
                suggestions.append(
                    f"Add {target_tone.value} language, such as: '{target_phrases[0]}'"
                )

        # Check sentiment alignment
        expected_sentiment = self._get_expected_sentiment(target_tone)
        if current.sentiment != expected_sentiment:
            suggestions.append(
                f"Adjust tone from {current.sentiment.value} to {expected_sentiment.value}"
            )

        return suggestions

    def _get_expected_sentiment(self, tone: EmotionalTone) -> Sentiment:
        """Get expected sentiment for a tone."""
        tone_sentiment_map = {
            EmotionalTone.EMPATHETIC: Sentiment.POSITIVE,
            EmotionalTone.REASSURING: Sentiment.POSITIVE,
            EmotionalTone.URGENT: Sentiment.NEGATIVE,
            EmotionalTone.INFORMATIVE: Sentiment.NEUTRAL,
            EmotionalTone.CAUTIONARY: Sentiment.NEGATIVE,
            EmotionalTone.SUPPORTIVE: Sentiment.POSITIVE,
        }

        return tone_sentiment_map.get(tone, Sentiment.NEUTRAL)

    def validate_cultural_sensitivity(
        self, text: str, target_culture: str, _language: str
    ) -> Tuple[bool, List[str]]:
        """
        Validate cultural sensitivity of translated text.

        Args:
            text: Text to validate
            target_culture: Target culture code
            language: Language code

        Returns:
            Tuple of (is_appropriate, concerns)
        """
        concerns = []

        # Cultural sensitivity rules
        cultural_rules = {
            "conservative": {
                "avoid_terms": ["intimate", "private parts"],
                "preferred_terms": ["personal health", "medical condition"],
            },
            "direct_communication": {
                "avoid_terms": ["maybe", "possibly", "might"],
                "preferred_terms": ["will", "should", "recommend"],
            },
        }

        # Check against cultural rules
        if target_culture in cultural_rules:
            rules = cultural_rules[target_culture]
            text_lower = text.lower()

            for avoid_term in rules.get("avoid_terms", []):
                if avoid_term in text_lower:
                    concerns.append(
                        f"Term '{avoid_term}' may not be culturally appropriate"
                    )

        return len(concerns) == 0, concerns


# Global instance
class _TonePreserverSingleton:
    """Singleton holder for ComprehendTonePreserver."""

    _instance: Optional[ComprehendTonePreserver] = None

    @classmethod
    def get_instance(cls) -> Optional[ComprehendTonePreserver]:
        """Get the singleton instance."""
        return cls._instance

    @classmethod
    def set_instance(cls, instance: ComprehendTonePreserver) -> None:
        """Set the singleton instance."""
        cls._instance = instance


def get_tone_preserver() -> ComprehendTonePreserver:
    """Get or create global tone preserver instance."""
    if _TonePreserverSingleton.get_instance() is None:
        _TonePreserverSingleton.set_instance(ComprehendTonePreserver())

    instance = _TonePreserverSingleton.get_instance()
    if instance is None:
        raise RuntimeError("Failed to create ComprehendTonePreserver instance")

    return instance
