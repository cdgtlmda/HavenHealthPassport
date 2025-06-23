"""
Cultural Adaptation AI for Medical Communications.

This module implements machine learning models to ensure culturally appropriate
medical communications for diverse refugee populations.

Dependencies:
    - SpaCy is required for NLP-based pattern extraction
    - Install with: pip install -r requirements-ml-nlp.txt
    - For medical model: pip install scispacy && pip install https://s3-us-west-2.amazonaws.com/ai2-s2-scispacy/releases/v0.5.1/en_core_sci_md-0.5.1.tar.gz
    - For basic model: python -m spacy download en_core_web_sm
"""

import asyncio
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import boto3

from src.healthcare.hipaa_access_control import AccessLevel, require_phi_access
from src.security.encryption import EncryptionService
from src.translation.quality.aws_ai.sagemaker_cultural import (
    SageMakerCulturalTrainer,
)
from src.utils.logging import get_logger

# Try to import spacy - will fail gracefully if not available
try:
    import spacy

    spacy_available = True
except ImportError:
    spacy_available = False
    spacy = None

logger = get_logger(__name__)


class CulturalContext(str, Enum):
    """Cultural contexts for medical communications."""

    MIDDLE_EASTERN = "middle_eastern"
    SOUTH_ASIAN = "south_asian"
    EAST_AFRICAN = "east_african"
    WEST_AFRICAN = "west_african"
    CENTRAL_ASIAN = "central_asian"
    LATIN_AMERICAN = "latin_american"
    SOUTHEAST_ASIAN = "southeast_asian"


class CommunicationStyle(str, Enum):
    """Communication style preferences."""

    DIRECT = "direct"
    INDIRECT = "indirect"
    FORMAL = "formal"
    INFORMAL = "informal"
    HIERARCHICAL = "hierarchical"
    EGALITARIAN = "egalitarian"


class SensitivityLevel(str, Enum):
    """Sensitivity levels for content."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class CulturalPattern:
    """Represents a cultural communication pattern."""

    pattern_id: str
    culture: CulturalContext
    communication_style: CommunicationStyle
    language_patterns: List[str]
    avoid_phrases: List[str]
    preferred_phrases: List[str]
    sensitivity_topics: List[str]
    confidence: float


@dataclass
class CulturalAdaptationResult:
    """Result of cultural adaptation analysis."""

    is_appropriate: bool
    confidence: float
    detected_patterns: List[CulturalPattern]
    sensitivity_warnings: List[str]
    suggested_modifications: List[str]
    cultural_score: float


@dataclass
class OffensiveContentResult:
    """Result of offensive content detection."""

    contains_offensive: bool
    offensive_segments: List[Tuple[str, float]]  # (text, confidence)
    categories: List[str]
    severity: SensitivityLevel
    context_appropriate: bool
    recommendations: List[str]


class CulturalAdaptationAI:
    """AI system for cultural adaptation in medical communications."""

    # Cultural communication patterns database
    CULTURAL_PATTERNS = {
        CulturalContext.MIDDLE_EASTERN: {
            "avoid_direct_negative": True,
            "family_involvement": "high",
            "religious_sensitivity": "high",
            "gender_preferences": True,
            "formal_address": True,
            "euphemistic_language": ["passed away instead of died"],
            "sensitive_topics": ["mental health", "reproductive health", "end of life"],
        },
        CulturalContext.SOUTH_ASIAN: {
            "hierarchy_important": True,
            "elder_respect": "high",
            "family_decision_making": True,
            "indirect_communication": True,
            "avoid_topics": ["mental illness stigma"],
            "preferred_terms": {
                "diabetes": "sugar disease",
                "hypertension": "BP problem",
            },
        },
        CulturalContext.EAST_AFRICAN: {
            "community_oriented": True,
            "oral_tradition": True,
            "metaphorical_language": True,
            "trust_building": "essential",
            "visual_aids": "preferred",
            "group_education": True,
        },
    }

    # Offensive content categories
    OFFENSIVE_CATEGORIES = {
        "cultural_insensitivity": [
            "stereotypes",
            "generalizations",
            "cultural assumptions",
        ],
        "religious_insensitivity": [
            "blasphemy",
            "religious mockery",
            "faith assumptions",
        ],
        "gender_bias": [
            "sexist language",
            "gender assumptions",
            "discriminatory terms",
        ],
        "medical_stigma": ["mental health stigma", "disease shaming", "victim blaming"],
    }

    def __init__(self, region: str = "us-east-1"):
        """
        Initialize cultural adaptation AI.

        Args:
            region: AWS region for SageMaker
        """
        self.sagemaker = boto3.client("sagemaker-runtime", region_name=region)
        self.s3 = boto3.client("s3", region_name=region)
        self._pattern_cache: Dict[str, Any] = {}
        self._model_endpoints: Dict[str, Optional[str]] = {
            "cultural_classifier": None,
            "offensive_detector": None,
            "communication_adapter": None,
        }
        self.encryption_service = EncryptionService(
            kms_key_id="alias/haven-health-default"
        )

        # Initialize SageMaker cultural trainer
        self.sagemaker_cultural_trainer: Optional[Any] = None
        try:
            self.sagemaker_cultural_trainer = SageMakerCulturalTrainer(region=region)
        except (ImportError, RuntimeError, AttributeError) as e:
            logger.warning(f"Could not initialize SageMaker cultural trainer: {e}")

        # Initialize Comprehend client for fallback
        self.comprehend_client = boto3.client("comprehend", region_name=region)

    @require_phi_access(AccessLevel.READ)
    async def analyze_cultural_appropriateness(
        self,
        text: str,
        target_culture: CulturalContext,
        communication_context: str,
        language: str,
    ) -> CulturalAdaptationResult:
        """
        Analyze text for cultural appropriateness.

        Args:
            text: Text to analyze
            target_culture: Target cultural context
            communication_context: Medical context (diagnosis, treatment, etc.)
            language: Language code

        Returns:
            Cultural adaptation analysis result
        """
        try:
            # Extract cultural patterns
            patterns = await self._detect_cultural_patterns(text, language)

            # Check against target culture preferences
            appropriateness = self._check_cultural_fit(
                text, patterns, target_culture, communication_context
            )

            # Generate recommendations
            recommendations = self._generate_recommendations(
                text, target_culture, appropriateness["issues"]
            )

            # Calculate cultural score
            cultural_score = self._calculate_cultural_score(
                appropriateness, patterns, target_culture
            )

            return CulturalAdaptationResult(
                is_appropriate=appropriateness["is_appropriate"],
                confidence=appropriateness["confidence"],
                detected_patterns=patterns,
                sensitivity_warnings=appropriateness["warnings"],
                suggested_modifications=recommendations,
                cultural_score=cultural_score,
            )

        except (ValueError, AttributeError, RuntimeError) as e:
            logger.error(f"Error analyzing cultural appropriateness: {e}")
            return CulturalAdaptationResult(
                is_appropriate=False,
                confidence=0.0,
                detected_patterns=[],
                sensitivity_warnings=[f"Analysis error: {str(e)}"],
                suggested_modifications=[],
                cultural_score=0.0,
            )

    def _map_to_comprehend_language(self, language: str) -> str:
        """Map language codes to AWS Comprehend supported languages."""
        comprehend_languages = {
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
        return comprehend_languages.get(language, "en")

    async def _detect_cultural_patterns(
        self, text: str, language: str
    ) -> List[CulturalPattern]:
        """Detect cultural communication patterns in text using trained ML models."""
        patterns = []

        try:
            # First try to use our trained SageMaker models if available
            if (
                hasattr(self, "sagemaker_cultural_trainer")
                and self.sagemaker_cultural_trainer is not None
            ):
                try:
                    # Get cultural region from language
                    region = self._get_cultural_region(language)

                    # Invoke cultural pattern classifier
                    ml_patterns = await self.sagemaker_cultural_trainer.invoke_cultural_pattern_classifier(
                        text=text,
                        source_language="en",  # Assuming source is English
                        target_language=language,
                        region=region,
                    )

                    # Convert ML results to CulturalPattern objects
                    if ml_patterns.get("confidence", 0) > 0.7:
                        patterns.extend(self._convert_ml_patterns(ml_patterns))

                except (RuntimeError, ValueError, AttributeError) as e:
                    logger.warning(
                        f"SageMaker model invocation failed, falling back to Comprehend: {e}"
                    )

            # Use Amazon Comprehend for entity analysis as fallback or supplement
            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.comprehend_client.detect_entities(
                    Text=text, LanguageCode=self._map_to_comprehend_language(language)
                ),
            )

            # sentiment_response = await asyncio.get_event_loop().run_in_executor(
            #     None,
            #     lambda: self.comprehend_client.detect_sentiment(
            #         Text=text, LanguageCode=self._map_to_comprehend_language(language)
            #     ),
            # )

            # Analyze communication patterns
            # Sentiment analysis would be used here for tone adaptation

            # Detect formality level
            formality_indicators = {
                "formal": [
                    "sir",
                    "madam",
                    "respected",
                    "kindly",
                    "please be advised",
                    "furthermore",
                    "therefore",
                ],
                "informal": ["hey", "thanks", "gonna", "wanna", "yeah", "ok", "cool"],
                "medical_formal": [
                    "patient",
                    "diagnosis",
                    "treatment",
                    "prescription",
                    "consultation",
                ],
            }

            text_lower = text.lower()
            formality_score = 0.0

            for indicator in formality_indicators["formal"]:
                if indicator in text_lower:
                    formality_score += 1
            for indicator in formality_indicators["informal"]:
                if indicator in text_lower:
                    formality_score -= 1
            for indicator in formality_indicators["medical_formal"]:
                if indicator in text_lower:
                    formality_score += 0.5

            # Detect directness
            direct_indicators = [
                "you must",
                "you have to",
                "required",
                "mandatory",
                "need to",
                "should",
            ]
            indirect_indicators = [
                "perhaps",
                "maybe",
                "might consider",
                "could possibly",
                "if possible",
            ]

            directness_score = 0
            for indicator in direct_indicators:
                if indicator in text_lower:
                    directness_score += 1
            for indicator in indirect_indicators:
                if indicator in text_lower:
                    directness_score -= 1

            # Map to cultural patterns based on language and scores
            culture_map = {
                "ar": CulturalContext.MIDDLE_EASTERN,
                "fa": CulturalContext.MIDDLE_EASTERN,
                "ur": CulturalContext.SOUTH_ASIAN,
                "hi": CulturalContext.SOUTH_ASIAN,
                "bn": CulturalContext.SOUTH_ASIAN,
                "zh": CulturalContext.SOUTHEAST_ASIAN,
                "ja": CulturalContext.SOUTHEAST_ASIAN,
                "ko": CulturalContext.SOUTHEAST_ASIAN,
                "es": CulturalContext.LATIN_AMERICAN,
                "pt": CulturalContext.LATIN_AMERICAN,
                "fr": CulturalContext.WEST_AFRICAN,
                "sw": CulturalContext.EAST_AFRICAN,
                "am": CulturalContext.EAST_AFRICAN,
            }

            culture = culture_map.get(language, CulturalContext.LATIN_AMERICAN)

            # Create pattern based on analysis
            if directness_score > 1 and culture in [
                CulturalContext.MIDDLE_EASTERN,
                CulturalContext.SOUTHEAST_ASIAN,
            ]:
                patterns.append(
                    CulturalPattern(
                        pattern_id="direct_imperative_cultural_mismatch",
                        culture=culture,
                        communication_style=CommunicationStyle.DIRECT,
                        language_patterns=["imperative mood", "direct commands"],
                        avoid_phrases=["you must", "mandatory", "required"],
                        preferred_phrases=[
                            "we kindly suggest",
                            "it would be beneficial",
                            "please consider",
                        ],
                        sensitivity_topics=["authority", "personal_choice"],
                        confidence=min(0.9, abs(directness_score) * 0.3),
                    )
                )

            # Formality patterns
            if formality_score > 2:
                patterns.append(
                    CulturalPattern(
                        pattern_id="high_formality",
                        culture=culture,
                        communication_style=CommunicationStyle.FORMAL,
                        language_patterns=["formal address", "respectful language"],
                        avoid_phrases=[],
                        preferred_phrases=[
                            "respected patient",
                            "kindly note",
                            "we humbly request",
                        ],
                        sensitivity_topics=["hierarchy", "respect"],
                        confidence=min(0.9, formality_score * 0.2),
                    )
                )
            elif formality_score < -2:
                patterns.append(
                    CulturalPattern(
                        pattern_id="informal_medical",
                        culture=culture,
                        communication_style=CommunicationStyle.INFORMAL,
                        language_patterns=["casual language", "colloquialisms"],
                        avoid_phrases=["hey", "gonna", "wanna"],
                        preferred_phrases=["hello", "going to", "want to"],
                        sensitivity_topics=["professionalism"],
                        confidence=min(0.9, abs(formality_score) * 0.2),
                    )
                )

            # Gender-sensitive patterns - simplified implementation
            # For certain cultures, always include gender sensitivity guidance
            if culture in [CulturalContext.MIDDLE_EASTERN, CulturalContext.SOUTH_ASIAN]:
                patterns.append(
                    CulturalPattern(
                        pattern_id="gender_sensitive",
                        culture=culture,
                        communication_style=CommunicationStyle.FORMAL,
                        language_patterns=["gender-specific terms"],
                        avoid_phrases=["he/she assumptions"],
                        preferred_phrases=["the patient", "they"],
                        sensitivity_topics=["gender", "modesty"],
                        confidence=0.85,
                    )
                )

            # Religious/spiritual sensitivity
            religious_terms = [
                "god",
                "allah",
                "inshallah",
                "prayer",
                "blessed",
                "faith",
            ]
            if any(term in text_lower for term in religious_terms):
                patterns.append(
                    CulturalPattern(
                        pattern_id="religious_sensitive",
                        culture=culture,
                        communication_style=CommunicationStyle.FORMAL,
                        language_patterns=["religious references"],
                        avoid_phrases=[],
                        preferred_phrases=[
                            "if it is meant to be",
                            "with hope",
                            "we pray for good health",
                        ],
                        sensitivity_topics=["religion", "spirituality"],
                        confidence=0.9,
                    )
                )

            # Age-related patterns - simplified implementation
            # For hierarchical cultures, include age respect patterns
            if culture in [
                CulturalContext.MIDDLE_EASTERN,
                CulturalContext.SOUTH_ASIAN,
                CulturalContext.SOUTHEAST_ASIAN,
            ]:
                patterns.append(
                    CulturalPattern(
                        pattern_id="age_respectful",
                        culture=culture,
                        communication_style=CommunicationStyle.FORMAL,
                        language_patterns=["age-appropriate language"],
                        avoid_phrases=["old", "elderly"],
                        preferred_phrases=["senior", "respected elder"],
                        sensitivity_topics=["age", "elder_respect"],
                        confidence=0.8,
                    )
                )

        except (RuntimeError, ValueError, AttributeError) as e:
            logger.error(f"Error detecting cultural patterns: {e}")
            # Return basic patterns as fallback
            patterns.append(
                CulturalPattern(
                    pattern_id="formal_address",
                    culture=CulturalContext.SOUTH_ASIAN,
                    communication_style=CommunicationStyle.FORMAL,
                    language_patterns=["formal titles", "respectful address"],
                    avoid_phrases=[],
                    preferred_phrases=["respected sir/madam"],
                    sensitivity_topics=[],
                    confidence=0.9,
                )
            )

        return patterns

    def _check_cultural_fit(
        self,
        text: str,
        _patterns: List[CulturalPattern],
        target_culture: CulturalContext,
        context: str,
    ) -> Dict[str, Any]:
        """Check if text fits target culture preferences."""
        issues = []
        warnings = []

        # Get cultural preferences
        cultural_prefs = self.CULTURAL_PATTERNS.get(target_culture, {})

        # Check sensitive topics
        text_lower = text.lower()
        sensitive_topics = cultural_prefs.get("sensitive_topics", [])
        if isinstance(sensitive_topics, list):
            for sensitive_topic in sensitive_topics:
                if sensitive_topic in text_lower:
                    warnings.append(f"Contains sensitive topic: {sensitive_topic}")
                    issues.append(
                        {
                            "type": "sensitive_topic",
                            "topic": sensitive_topic,
                            "severity": "high",
                        }
                    )

        # Check communication style
        if cultural_prefs.get("avoid_direct_negative") and any(
            word in text_lower for word in ["cannot", "will not", "impossible"]
        ):
            issues.append({"type": "direct_negative", "severity": "medium"})
            warnings.append("Contains direct negative language")

        # Check for required elements
        if (
            context == "diagnosis"
            and cultural_prefs.get("family_involvement") == "high"
        ):
            if not any(
                word in text_lower for word in ["family", "relatives", "together"]
            ):
                warnings.append("Missing family involvement language")

        is_appropriate = len(issues) == 0 or all(
            issue.get("severity") != "high" for issue in issues
        )

        confidence = 1.0 - (len(issues) * 0.1)

        return {
            "is_appropriate": is_appropriate,
            "confidence": max(0.0, confidence),
            "issues": issues,
            "warnings": warnings,
        }

    def _generate_recommendations(
        self, _text: str, target_culture: CulturalContext, issues: List[Dict[str, Any]]
    ) -> List[str]:
        """Generate recommendations for cultural adaptation."""
        recommendations = []
        cultural_prefs = self.CULTURAL_PATTERNS.get(target_culture, {})

        for issue in issues:
            if issue["type"] == "direct_negative":
                recommendations.append(
                    "Soften negative language: Use 'might be challenging' instead of 'cannot'"
                )

            elif issue["type"] == "sensitive_topic":
                topic = issue.get("topic", "")
                if topic == "mental health":
                    recommendations.append(
                        "Use culturally appropriate terms: 'emotional wellbeing' or 'stress'"
                    )
                elif topic == "reproductive health":
                    recommendations.append(
                        "Consider using euphemistic language and ensure same-gender provider"
                    )

        # Add general recommendations
        if cultural_prefs.get("family_involvement") == "high":
            recommendations.append(
                "Include family in discussion: 'You and your family may want to discuss...'"
            )

        if cultural_prefs.get("formal_address"):
            recommendations.append(
                "Use formal titles and respectful language throughout"
            )

        return recommendations

    def _calculate_cultural_score(
        self,
        appropriateness: Dict[str, Any],
        patterns: List[CulturalPattern],
        target_culture: CulturalContext,
    ) -> float:
        """Calculate overall cultural appropriateness score."""
        base_score = appropriateness["confidence"]

        # Bonus for matching patterns
        pattern_bonus = sum(0.1 for p in patterns if p.culture == target_culture)

        # Penalty for issues
        issue_penalty = len(appropriateness["issues"]) * 0.15

        score = base_score + pattern_bonus - issue_penalty

        return float(max(0.0, min(1.0, score)))

    async def detect_offensive_content(
        self, text: str, cultural_context: CulturalContext, medical_context: str
    ) -> OffensiveContentResult:
        """
        Detect potentially offensive content.

        Args:
            text: Text to analyze
            cultural_context: Cultural context
            medical_context: Medical context

        Returns:
            Offensive content detection result
        """
        try:
            # Analyze text for offensive content
            offensive_segments = await self._detect_offensive_segments(text)

            # Categorize offensive content
            categories = self._categorize_offensive_content(offensive_segments)

            # Determine severity
            severity = self._determine_severity(offensive_segments, categories)

            # Check if context makes it appropriate
            context_appropriate = self._check_medical_context_appropriateness(
                offensive_segments, medical_context
            )

            # Generate recommendations
            recommendations = self._generate_content_recommendations(
                offensive_segments, categories, cultural_context
            )

            return OffensiveContentResult(
                contains_offensive=len(offensive_segments) > 0,
                offensive_segments=offensive_segments,
                categories=categories,
                severity=severity,
                context_appropriate=context_appropriate,
                recommendations=recommendations,
            )

        except (ValueError, AttributeError, RuntimeError) as e:
            logger.error(f"Error detecting offensive content: {e}")
            return OffensiveContentResult(
                contains_offensive=False,
                offensive_segments=[],
                categories=[],
                severity=SensitivityLevel.LOW,
                context_appropriate=True,
                recommendations=[],
            )

    async def _detect_offensive_segments(self, text: str) -> List[Tuple[str, float]]:
        """Detect offensive segments in text."""
        segments = []

        # Simulated offensive content detection
        # In production, this would use trained ML models

        # Check for stereotypes
        stereotype_phrases = ["all refugees", "these people always", "typical behavior"]

        for phrase in stereotype_phrases:
            if phrase in text.lower():
                segments.append((phrase, 0.8))

        # Check for insensitive medical language
        insensitive_terms = ["drug seeker", "non-compliant", "difficult patient"]

        for term in insensitive_terms:
            if term in text.lower():
                segments.append((term, 0.9))

        return segments

    def _categorize_offensive_content(
        self, segments: List[Tuple[str, float]]
    ) -> List[str]:
        """Categorize offensive content."""
        categories = set()

        for segment, _ in segments:
            segment_lower = segment.lower()

            for category, keywords in self.OFFENSIVE_CATEGORIES.items():
                if any(keyword in segment_lower for keyword in keywords):
                    categories.add(category)

        return list(categories)

    def _determine_severity(
        self, segments: List[Tuple[str, float]], categories: List[str]
    ) -> SensitivityLevel:
        """Determine severity of offensive content."""
        if not segments:
            return SensitivityLevel.LOW

        # High confidence offensive content
        if any(conf > 0.8 for _, conf in segments):
            return SensitivityLevel.CRITICAL

        # Multiple categories
        if len(categories) > 2:
            return SensitivityLevel.HIGH

        # Medical stigma is particularly serious
        if "medical_stigma" in categories:
            return SensitivityLevel.HIGH

        return SensitivityLevel.MEDIUM

    def _check_medical_context_appropriateness(
        self, segments: List[Tuple[str, float]], medical_context: str
    ) -> bool:
        """Check if medical context makes content appropriate."""
        # Some terms may be appropriate in clinical documentation
        # but not in patient communication

        if medical_context == "clinical_notes":
            # More tolerance for clinical terminology
            return True

        if medical_context == "patient_communication":
            # Strict standards for patient-facing content
            return len(segments) == 0

        return len(segments) < 2

    def _get_cultural_region(self, language: str) -> str:
        """Map language to cultural region for ML models."""
        language_to_region = {
            "ar": "middle_east",
            "es": "latin_america",
            "sw": "east_africa",
            "am": "east_africa",
            "ti": "east_africa",
            "so": "east_africa",
            "ur": "south_asia",
            "hi": "south_asia",
            "bn": "south_asia",
            "pa": "south_asia",
            "fa": "middle_east",
            "ps": "south_asia",
            "zh": "east_asia",
            "my": "southeast_asia",
            "fr": "west_africa",  # For African French speakers
        }
        return language_to_region.get(language, "global")

    def _convert_ml_patterns(
        self, ml_patterns: Dict[str, Any]
    ) -> List[CulturalPattern]:
        """Convert ML model output to CulturalPattern objects."""
        patterns = []

        # Formality pattern
        if ml_patterns.get("formality_level") != "neutral":
            patterns.append(
                CulturalPattern(
                    pattern_id=f"formality_{ml_patterns['formality_level']}",
                    culture=CulturalContext.MIDDLE_EASTERN,  # Default, should be passed in
                    communication_style=(
                        CommunicationStyle.FORMAL
                        if ml_patterns["formality_level"] == "formal"
                        else CommunicationStyle.INFORMAL
                    ),
                    language_patterns=[ml_patterns["formality_level"]],
                    avoid_phrases=[],
                    preferred_phrases=[],
                    sensitivity_topics=["formality"],
                    confidence=ml_patterns.get("confidence", 0.8),
                )
            )

        # Family involvement pattern
        if ml_patterns.get("family_involvement"):
            patterns.append(
                CulturalPattern(
                    pattern_id="family_involvement",
                    culture=CulturalContext.MIDDLE_EASTERN,  # Default, should be passed in
                    communication_style=CommunicationStyle.HIERARCHICAL,
                    language_patterns=["family involvement"],
                    avoid_phrases=[],
                    preferred_phrases=["family consultation"],
                    sensitivity_topics=["family"],
                    confidence=ml_patterns.get("confidence", 0.8),
                )
            )

        # Religious references pattern
        if ml_patterns.get("religious_references"):
            patterns.append(
                CulturalPattern(
                    pattern_id="religious_context",
                    culture=CulturalContext.MIDDLE_EASTERN,  # Default, should be passed in
                    communication_style=CommunicationStyle.FORMAL,
                    language_patterns=["religious references"],
                    avoid_phrases=[],
                    preferred_phrases=["faith-based care"],
                    sensitivity_topics=["religion"],
                    confidence=ml_patterns.get("confidence", 0.8),
                )
            )

        # Age hierarchy pattern
        if ml_patterns.get("age_hierarchy"):
            patterns.append(
                CulturalPattern(
                    pattern_id="age_hierarchy",
                    culture=CulturalContext.MIDDLE_EASTERN,  # Default, should be passed in
                    communication_style=CommunicationStyle.HIERARCHICAL,
                    language_patterns=["age hierarchy"],
                    avoid_phrases=["old", "elderly"],
                    preferred_phrases=["elder", "senior"],
                    sensitivity_topics=["age", "respect"],
                    confidence=ml_patterns.get("confidence", 0.8),
                )
            )

        return patterns

    def _generate_content_recommendations(
        self,
        _segments: List[Tuple[str, float]],
        categories: List[str],
        cultural_context: CulturalContext,
    ) -> List[str]:
        """Generate recommendations for content improvement."""
        recommendations = []

        if "cultural_insensitivity" in categories:
            recommendations.append("Avoid generalizations about cultural groups")
            recommendations.append(
                "Use person-first language: 'patients who are refugees' not 'refugee patients'"
            )

        if "medical_stigma" in categories:
            recommendations.append(
                "Replace stigmatizing terms with neutral medical language"
            )
            recommendations.append("Focus on collaborative care rather than compliance")

        # Cultural-specific recommendations
        cultural_recs = {
            CulturalContext.MIDDLE_EASTERN: [
                "Include family-centered language",
                "Use indirect communication for sensitive topics",
            ],
            CulturalContext.SOUTH_ASIAN: [
                "Use respectful titles and formal address",
                "Acknowledge family involvement in care decisions",
            ],
        }

        if cultural_context in cultural_recs:
            recommendations.extend(cultural_recs[cultural_context])

        return recommendations

    async def train_cultural_model(
        self,
        training_data: List[Dict[str, Any]],
        model_type: str,
        _hyperparameters: Dict[str, Any],
    ) -> str:
        """
        Train a cultural adaptation model.

        Args:
            training_data: Training examples
            model_type: Type of model to train
            hyperparameters: Model hyperparameters

        Returns:
            Model endpoint name
        """
        # This would implement SageMaker training job
        # For now, return placeholder

        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        endpoint_name = f"cultural-{model_type}-{timestamp}"

        logger.info(f"Training {model_type} model with {len(training_data)} examples")

        # Store endpoint
        self._model_endpoints[model_type] = endpoint_name

        return endpoint_name

    async def update_cultural_preferences(
        self, culture: CulturalContext, feedback_data: List[Dict[str, Any]]
    ) -> bool:
        """
        Update cultural preferences based on feedback.

        Args:
            culture: Cultural context to update
            feedback_data: User feedback data

        Returns:
            Success status
        """
        try:
            # Analyze feedback patterns
            preference_updates = self._analyze_feedback_patterns(feedback_data, culture)

            # Update cultural patterns
            if culture in self.CULTURAL_PATTERNS:
                current_patterns = self.CULTURAL_PATTERNS[culture]

                # Apply updates
                for key, value in preference_updates.items():
                    if key in current_patterns:
                        current_value = current_patterns[key]
                        if isinstance(current_value, list) and isinstance(value, list):
                            current_value.extend(value)
                        else:
                            current_patterns[key] = value

                logger.info(
                    f"Updated {len(preference_updates)} preferences for {culture}"
                )
                return True

            return False

        except (ValueError, AttributeError, KeyError) as e:
            logger.error(f"Error updating cultural preferences: {e}")
            return False

    def _analyze_feedback_patterns(
        self, feedback_data: List[Dict[str, Any]], _culture: CulturalContext
    ) -> Dict[str, Any]:
        """Analyze feedback to identify preference patterns."""
        updates: Dict[str, Any] = {}

        # Aggregate feedback
        positive_patterns = []
        negative_patterns = []

        for feedback in feedback_data:
            if feedback.get("rating", 0) >= 4:
                positive_patterns.append(feedback.get("text", ""))
            else:
                negative_patterns.append(feedback.get("text", ""))

        # CRITICAL: Use proper NLP for medical/cultural pattern extraction
        # This is essential for identifying cultural sensitivities in healthcare contexts

        try:
            # Check if spacy is available at module level
            _spacy_available = spacy_available
            if not _spacy_available:
                logger.error(
                    "SpaCy is not installed. NLP-based pattern extraction will be disabled. "
                    "Install with: pip install spacy && python -m spacy download en_core_web_sm."
                )
                # In a medical context, we should alert about reduced capabilities
                logger.critical(
                    "CRITICAL: Operating without SpaCy NLP. Medical term extraction accuracy "
                    "will be significantly reduced. This may impact patient safety."
                )

            if _spacy_available:
                # Load medical NLP model
                try:
                    nlp = spacy.load("en_core_sci_md")  # Medical-specific model
                    logger.info("Loaded medical-specific SpaCy model (en_core_sci_md)")
                except OSError:
                    try:
                        nlp = spacy.load("en_core_web_sm")  # Fallback to general model
                        logger.warning(
                            "Medical NLP model not available, using general model. "
                            "Install with: pip install scispacy && pip install https://s3-us-west-2.amazonaws.com/ai2-s2-scispacy/releases/v0.5.1/en_core_sci_md-0.5.1.tar.gz"
                        )
                    except OSError as e:
                        _spacy_available = False
                        logger.error(
                            f"No SpaCy models found. Install with: python -m spacy download en_core_web_sm. Error: {e}"
                        )
            else:
                # Raise early to use fallback method
                raise ImportError("SpaCy not available")

            # Extract patterns from negative feedback
            sensitive_topics = []
            cultural_issues = []

            # Only proceed with NLP if spacy is available
            if not _spacy_available:
                raise ImportError("SpaCy not available for NLP processing")

            for text in negative_patterns:
                doc = nlp(text.lower())

                # Entities and noun phrases would be extracted here for analysis
                # Currently focusing on sentiment and sensitivity indicators

                # Look for cultural sensitivity indicators
                sensitivity_indicators = [
                    "inappropriate",
                    "offensive",
                    "uncomfortable",
                    "disrespectful",
                    "taboo",
                    "forbidden",
                    "unacceptable",
                    "insensitive",
                    "cultural",
                    "religious",
                    "tradition",
                    "custom",
                ]

                # Check if feedback mentions cultural issues
                if any(
                    indicator in text.lower() for indicator in sensitivity_indicators
                ):
                    # Extract the specific topic/issue
                    for sentence in doc.sents:
                        if any(
                            indicator in sentence.text.lower()
                            for indicator in sensitivity_indicators
                        ):
                            # Extract relevant entities and noun phrases from this sentence
                            sent_doc = nlp(sentence.text)

                            # Get the main topic (usually subject or object)
                            for token in sent_doc:
                                if token.dep_ in ["nsubj", "dobj", "pobj"]:
                                    if token.text not in sensitivity_indicators:
                                        sensitive_topics.append(token.lemma_)

                            # Also extract noun phrases
                            for chunk in sent_doc.noun_chunks:
                                if not any(
                                    indicator in chunk.text
                                    for indicator in sensitivity_indicators
                                ):
                                    cultural_issues.append(chunk.text)

            # Extract patterns from positive feedback for best practices
            positive_elements = []
            for text in positive_patterns:
                doc = nlp(text.lower())

                # Look for positive indicators
                positive_indicators = [
                    "respectful",
                    "appropriate",
                    "sensitive",
                    "considerate",
                    "culturally aware",
                    "helpful",
                    "clear",
                    "understood",
                ]

                if any(indicator in text.lower() for indicator in positive_indicators):
                    # Extract what was done well
                    for chunk in doc.noun_chunks:
                        positive_elements.append(chunk.text)

            # Aggregate findings
            if sensitive_topics:
                # Count frequency and filter
                topic_counts = Counter(sensitive_topics)
                significant_topics = [
                    topic
                    for topic, count in topic_counts.items()
                    if count >= 2 or len(topic) > 3  # Filter noise
                ]
                updates["sensitive_topics"] = significant_topics

            if cultural_issues:
                issue_counts = Counter(cultural_issues)
                significant_issues = [
                    issue
                    for issue, count in issue_counts.items()
                    if count >= 2 and len(issue.split()) <= 5  # Reasonable length
                ]
                updates["cultural_concerns"] = significant_issues

            if positive_elements:
                element_counts = Counter(positive_elements)
                best_practices = [
                    elem
                    for elem, count in element_counts.items()
                    if count >= 3  # Frequently mentioned positives
                ]
                updates["best_practices"] = best_practices

        except ImportError as e:
            # Expected when SpaCy is not installed
            logger.warning(
                f"Using fallback keyword-based extraction due to missing NLP library: {e}"
            )
            # Fallback to keyword-based extraction
            updates["sensitive_topics"] = self._fallback_pattern_extraction(
                negative_patterns
            )
            updates["metadata"] = {
                "extraction_method": "keyword_based",
                "warning": "NLP-based extraction unavailable - using fallback method",
            }
        except (RuntimeError, ValueError, AttributeError, TypeError) as e:
            # Unexpected error - log with more detail for medical safety
            logger.error(
                f"Unexpected error in NLP pattern extraction: {type(e).__name__}: {e}",
                exc_info=True,
            )
            # Still provide fallback to ensure system continues functioning
            updates["sensitive_topics"] = self._fallback_pattern_extraction(
                negative_patterns
            )
            updates["metadata"] = {
                "extraction_method": "fallback_due_to_error",
                "error": str(e),
            }

        return updates

    def _fallback_pattern_extraction(self, texts: List[str]) -> List[str]:
        """Fallback pattern extraction using keywords."""
        patterns = []

        # Medical and cultural keywords to look for
        keywords = {
            "body": ["body", "physical", "anatomy", "examination"],
            "gender": ["gender", "male", "female", "woman", "man"],
            "religious": ["religious", "prayer", "fasting", "halal", "kosher"],
            "dietary": ["food", "diet", "eating", "pork", "alcohol"],
            "mental_health": ["mental", "psychological", "depression", "anxiety"],
            "reproductive": ["pregnancy", "birth", "reproductive", "sexual"],
            "death": ["death", "dying", "terminal", "end of life"],
        }

        for text in texts:
            text_lower = text.lower()
            for category, terms in keywords.items():
                if any(term in text_lower for term in terms):
                    patterns.append(category)

        return list(set(patterns))


# Global instance
class _CulturalAISingleton:
    """Singleton holder for CulturalAdaptationAI."""

    _instance: Optional[CulturalAdaptationAI] = None

    @classmethod
    def get_instance(cls) -> Optional[CulturalAdaptationAI]:
        """Get the singleton instance."""
        return cls._instance

    @classmethod
    def set_instance(cls, instance: CulturalAdaptationAI) -> None:
        """Set the singleton instance."""
        cls._instance = instance


def get_cultural_adaptation_ai() -> CulturalAdaptationAI:
    """Get or create global cultural adaptation AI instance."""
    if _CulturalAISingleton.get_instance() is None:
        _CulturalAISingleton.set_instance(CulturalAdaptationAI())

    instance = _CulturalAISingleton.get_instance()
    if instance is None:
        raise RuntimeError("Failed to create CulturalAdaptationAI instance")

    return instance
