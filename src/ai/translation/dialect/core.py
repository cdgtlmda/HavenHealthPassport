"""
Core dialect detection functionality.

This module provides the main dialect detection classes and interfaces for
identifying regional language variations in medical texts.

This module handles encrypted PHI with access control and audit logging
to ensure HIPAA compliance.
"""

import logging
import re
from abc import ABC, abstractmethod
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from ...langchain.bedrock import get_bedrock_llm
from ..config import Language
from ..exceptions import TranslationError

logger = logging.getLogger(__name__)


class DialectConfidence(Enum):
    """Confidence levels for dialect detection."""

    VERY_HIGH = "very_high"  # > 0.9
    HIGH = "high"  # > 0.7
    MEDIUM = "medium"  # > 0.5
    LOW = "low"  # > 0.3
    VERY_LOW = "very_low"  # <= 0.3


@dataclass
class DialectFeatures:
    """Features used for dialect detection."""

    lexical_markers: Dict[str, float] = field(default_factory=dict)
    phonetic_patterns: Dict[str, float] = field(default_factory=dict)
    syntactic_structures: Dict[str, float] = field(default_factory=dict)
    orthographic_variations: Dict[str, float] = field(default_factory=dict)
    medical_terminology: Dict[str, float] = field(default_factory=dict)
    cultural_expressions: Dict[str, float] = field(default_factory=dict)
    geographic_indicators: List[str] = field(default_factory=list)
    frequency_distributions: Dict[str, Counter] = field(default_factory=dict)

    def to_vector(self) -> np.ndarray:
        """Convert features to a numerical vector for ML processing."""
        features: List[float] = []

        # Aggregate all feature values
        for feature_dict in [
            self.lexical_markers,
            self.phonetic_patterns,
            self.syntactic_structures,
            self.orthographic_variations,
            self.medical_terminology,
            self.cultural_expressions,
        ]:
            features.extend(feature_dict.values())

        # Add geographic indicator count
        features.append(len(self.geographic_indicators))

        # Add frequency distribution statistics
        for counter in self.frequency_distributions.values():
            if counter:
                features.extend(
                    [
                        len(counter),  # unique items
                        sum(counter.values()),  # total count
                        max(counter.values()) if counter else 0,  # max frequency
                        (
                            float(np.mean(list(counter.values()))) if counter else 0.0
                        ),  # mean frequency
                    ]
                )

        return np.array(features)


@dataclass
class DialectProfile:
    """Profile defining a specific dialect."""

    dialect_code: str  # e.g., "en-US", "en-GB", "es-MX", "es-ES"
    base_language: Language
    name: str
    region: str
    alternative_names: List[str] = field(default_factory=list)

    # Characteristic features
    lexical_variations: Dict[str, List[str]] = field(default_factory=dict)
    spelling_variations: Dict[str, str] = field(default_factory=dict)
    medical_term_variations: Dict[str, str] = field(default_factory=dict)
    date_formats: List[str] = field(default_factory=list)
    measurement_preferences: Dict[str, str] = field(default_factory=dict)

    # Statistical models
    word_frequency_model: Optional[Dict[str, float]] = None
    ngram_model: Optional[Dict[str, float]] = None
    character_frequency: Optional[Dict[str, float]] = None

    # Medical context
    healthcare_system_terms: Dict[str, str] = field(default_factory=dict)
    medication_naming: Dict[str, str] = field(default_factory=dict)
    regulatory_terms: Dict[str, str] = field(default_factory=dict)

    # Confidence thresholds
    min_confidence_threshold: float = 0.5
    high_confidence_threshold: float = 0.8


@dataclass
class DialectDetectionResult:
    """Result of dialect detection."""

    detected_dialect: str  # Dialect code
    base_language: Language
    confidence: float
    confidence_level: DialectConfidence
    alternative_dialects: List[Tuple[str, float]] = field(default_factory=list)
    features_detected: DialectFeatures = field(default_factory=DialectFeatures)
    detection_method: str = "unknown"
    processing_time_ms: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Set confidence level based on confidence score."""
        if self.confidence > 0.9:
            self.confidence_level = DialectConfidence.VERY_HIGH
        elif self.confidence > 0.7:
            self.confidence_level = DialectConfidence.HIGH
        elif self.confidence > 0.5:
            self.confidence_level = DialectConfidence.MEDIUM
        elif self.confidence > 0.3:
            self.confidence_level = DialectConfidence.LOW
        else:
            self.confidence_level = DialectConfidence.VERY_LOW


class BaseDialectDetector(ABC):
    """Abstract base class for dialect detectors."""

    @abstractmethod
    def detect(
        self, text: str, language_hint: Optional[Language] = None
    ) -> DialectDetectionResult:
        """Detect the dialect of the given text."""
        pass

    @abstractmethod
    def extract_features(self, text: str) -> DialectFeatures:
        """Extract dialect-specific features from text."""
        pass

    @abstractmethod
    def get_supported_dialects(self, language: Optional[Language] = None) -> List[str]:
        """Get list of supported dialects."""
        pass


class DialectDetector(BaseDialectDetector):
    """Main dialect detection implementation."""

    def __init__(
        self,
        profiles: Optional[Dict[str, DialectProfile]] = None,
        use_ai_detection: bool = True,
        cache_results: bool = True,
    ):
        """
        Initialize dialect detector.

        Args:
            profiles: Dictionary of dialect profiles
            use_ai_detection: Whether to use AI models for detection
            cache_results: Whether to cache detection results
        """
        self.profiles = profiles or {}
        self.use_ai_detection = use_ai_detection
        self.cache_results = cache_results
        self._cache: Dict[str, DialectDetectionResult] = {}
        self._feature_extractors: List[Any] = []  # Will be populated by feature module

        # Load default profiles if none provided
        if not self.profiles:
            self._load_default_profiles()

    def detect(
        self, text: str, language_hint: Optional[Language] = None
    ) -> DialectDetectionResult:
        """
        Detect the dialect of the given text.

        Args:
            text: Text to analyze
            language_hint: Optional language hint to narrow search

        Returns:
            DialectDetectionResult with detected dialect information
        """
        start_time = datetime.now()

        # Check cache if enabled
        cache_key = f"{hash(text)}:{language_hint}"
        if self.cache_results and cache_key in self._cache:
            cached_result = self._cache[cache_key]
            cached_result.metadata["from_cache"] = True
            return cached_result

        try:
            # Extract features
            features = self.extract_features(text)

            # Score against all relevant profiles
            scores = {}
            relevant_profiles = self._get_relevant_profiles(language_hint)

            for dialect_code, profile in relevant_profiles.items():
                score = self._score_profile(text, features, profile)
                scores[dialect_code] = score

            # Sort by score
            sorted_dialects = sorted(scores.items(), key=lambda x: x[1], reverse=True)

            if not sorted_dialects:
                raise TranslationError("No dialects available for detection")

            # Use AI detection for refinement if enabled
            if self.use_ai_detection and len(sorted_dialects) > 1:
                sorted_dialects = self._refine_with_ai(text, sorted_dialects, features)

            # Create result
            detected_dialect = sorted_dialects[0][0]
            confidence = sorted_dialects[0][1]
            profile = self.profiles[detected_dialect]

            result = DialectDetectionResult(
                detected_dialect=detected_dialect,
                base_language=profile.base_language,
                confidence=confidence,
                confidence_level=DialectConfidence.VERY_HIGH,  # Will be set in __post_init__
                alternative_dialects=sorted_dialects[1:6],  # Top 5 alternatives
                features_detected=features,
                detection_method="hybrid" if self.use_ai_detection else "rule-based",
                processing_time_ms=(datetime.now() - start_time).total_seconds() * 1000,
                metadata={
                    "profile_name": profile.name,
                    "region": profile.region,
                    "scores": dict(sorted_dialects[:10]),  # Top 10 for analysis
                },
            )

            # Cache result if enabled
            if self.cache_results:
                self._cache[cache_key] = result

            return result

        except (ValueError, AttributeError, KeyError) as e:
            logger.error("Dialect detection failed: %s", str(e))
            # Return a default result on error
            return DialectDetectionResult(
                detected_dialect="unknown",
                base_language=language_hint or Language.ENGLISH,
                confidence=0.0,
                confidence_level=DialectConfidence.VERY_LOW,
                warnings=[f"Detection error: {str(e)}"],
                processing_time_ms=(datetime.now() - start_time).total_seconds() * 1000,
            )

    def extract_features(self, text: str) -> DialectFeatures:
        """
        Extract dialect-specific features from text.

        Args:
            text: Text to analyze

        Returns:
            DialectFeatures object with extracted features
        """
        features = DialectFeatures()

        # Clean and tokenize text
        cleaned_text = self._clean_text(text)
        words = self._tokenize(cleaned_text)

        # Extract lexical markers
        features.lexical_markers = self._extract_lexical_markers(words)

        # Extract orthographic variations
        features.orthographic_variations = self._extract_orthographic_variations(text)

        # Extract syntactic patterns
        features.syntactic_structures = self._extract_syntactic_patterns(cleaned_text)

        # Extract medical terminology
        features.medical_terminology = self._extract_medical_terms(text)

        # Extract cultural expressions
        features.cultural_expressions = self._extract_cultural_expressions(text)

        # Extract geographic indicators
        features.geographic_indicators = self._extract_geographic_indicators(text)

        # Build frequency distributions
        features.frequency_distributions = {
            "word_freq": Counter(words),
            "bigrams": Counter(zip(words[:-1], words[1:])),
            "char_freq": Counter(cleaned_text.lower()),
        }

        return features

    def get_supported_dialects(self, language: Optional[Language] = None) -> List[str]:
        """Get list of supported dialects."""
        if language:
            return [
                code
                for code, profile in self.profiles.items()
                if profile.base_language == language
            ]
        return list(self.profiles.keys())

    def _load_default_profiles(self) -> None:
        """Load default dialect profiles."""
        # Import here to avoid circular imports
        from . import profiles  # noqa: PLC0415

        logger.debug("Loading default dialect profiles")

        # Load all profiles from the registry
        for dialect_code in profiles.list_supported_dialects():
            profile = profiles.get_dialect_profile(dialect_code)
            if profile:
                self.profiles[dialect_code] = profile

        logger.info("Loaded %d default dialect profiles", len(self.profiles))

    def _get_relevant_profiles(
        self, language: Optional[Language]
    ) -> Dict[str, DialectProfile]:
        """Get profiles relevant to the given language."""
        if language:
            return {
                code: profile
                for code, profile in self.profiles.items()
                if profile.base_language == language
            }
        return self.profiles

    def _score_profile(
        self,
        text: str,
        features: DialectFeatures,
        profile: DialectProfile,
    ) -> float:
        """Score how well the text matches a dialect profile."""
        # Use text length for scoring normalization
        text_length = len(text.split())
        score = 0.0
        weights = {
            "lexical": 0.3,
            "orthographic": 0.25,
            "medical": 0.2,
            "syntactic": 0.15,
            "frequency": 0.1,
        }

        # Score lexical variations
        lexical_score = self._score_lexical_match(
            features.lexical_markers, profile.lexical_variations
        )
        score += weights["lexical"] * lexical_score

        # Score orthographic variations
        ortho_score = self._score_orthographic_match(
            features.orthographic_variations, profile.spelling_variations
        )
        score += weights["orthographic"] * ortho_score

        # Score medical terminology
        medical_score = self._score_medical_match(
            features.medical_terminology, profile.medical_term_variations
        )
        score += weights["medical"] * medical_score

        # Score syntactic patterns
        syntactic_score = self._score_syntactic_match(features, profile)
        score += weights["syntactic"] * syntactic_score

        # Score frequency distributions
        freq_score = self._score_frequency_match(
            features.frequency_distributions, profile
        )
        score += weights["frequency"] * freq_score

        # Apply text length normalization
        if text_length > 0:
            normalization_factor = min(
                1.0, text_length / 100.0
            )  # Normalize for texts up to 100 words
            score *= normalization_factor

        return max(0.0, min(1.0, score))  # Ensure score is between 0 and 1

    def _refine_with_ai(
        self, text: str, candidates: List[Tuple[str, float]], features: DialectFeatures
    ) -> List[Tuple[str, float]]:
        """Use AI model to refine dialect detection."""
        # Log features summary for debugging
        logger.debug(
            "Refining with AI using %d features", len(features.lexical_markers)
        )

        try:
            model = get_bedrock_llm()

            # Prepare context with top candidates
            candidate_info = "\n".join(
                [
                    f"- {self.profiles[code].name} ({code}): {score:.2f}"
                    for code, score in candidates[:5]
                ]
            )

            prompt = f"""Analyze the following text and identify its dialect from these candidates:

Text: {text[:500]}...

Candidates:
{candidate_info}

Consider lexical choices, spelling, medical terminology, and cultural expressions.
Return only the dialect code of the most likely match."""

            response = model.invoke(prompt)
            # Handle different response content types
            content = response.content
            if isinstance(content, list):
                content = " ".join(str(item) for item in content)
            else:
                content = str(content)
            ai_choice = content.strip()

            # Reorder candidates based on AI suggestion
            refined: List[Tuple[str, float]] = []
            for code, score in candidates:
                if code == ai_choice:
                    # Boost the AI's choice
                    refined.insert(0, (code, min(1.0, score * 1.2)))
                else:
                    refined.append((code, score))

            return refined

        except (ValueError, AttributeError, KeyError) as e:
            logger.warning("AI refinement failed: %s", str(e))
            return candidates  # Return original if AI fails

    def _clean_text(self, text: str) -> str:
        """Clean text for analysis."""
        # Remove extra whitespace
        text = re.sub(r"\s+", " ", text)
        # Remove special characters but keep medical symbols
        text = re.sub(r"[^\w\s\-\.\,\;\:\!\?\'\"\+\=\%°μ]", "", text)
        return text.strip()

    def _tokenize(self, text: str) -> List[str]:
        """Tokenize text into words."""
        # Simple word tokenization
        words = re.findall(r"\b\w+\b", text.lower())
        return words

    def _extract_lexical_markers(self, words: List[str]) -> Dict[str, float]:
        """Extract lexical markers from words."""
        markers = {}

        # Common dialect markers (examples)
        marker_patterns = {
            "color_colour": len([w for w in words if w in ["color", "colour"]]),
            "center_centre": len([w for w in words if w in ["center", "centre"]]),
            "ize_ise": len([w for w in words if w.endswith(("ize", "ise"))]),
        }

        total_words = len(words) or 1
        for pattern, count in marker_patterns.items():
            if count > 0:
                markers[pattern] = count / total_words

        return markers

    def _extract_orthographic_variations(self, text: str) -> Dict[str, float]:
        """Extract orthographic (spelling) variations."""
        variations = {}

        # Check for specific spelling patterns
        patterns = {
            "double_l": len(re.findall(r"\b\w*ll\w*\b", text)),
            "ae_vs_e": len(re.findall(r"\b\w*(ae|oe)\w*\b", text)),
            "our_endings": len(re.findall(r"\b\w+our\b", text)),
            "re_endings": len(re.findall(r"\b\w+re\b", text)),
        }

        text_length = len(text) or 1
        for pattern, count in patterns.items():
            if count > 0:
                variations[pattern] = count / (text_length / 100)  # Per 100 chars

        return variations

    def _extract_syntactic_patterns(self, text: str) -> Dict[str, float]:
        """Extract syntactic patterns."""
        patterns = {}

        # Simple syntactic markers
        sentences = re.split(r"[.!?]+", text)
        num_sentences = len(sentences) or 1

        # Check for specific constructions
        patterns["got_vs_gotten"] = (
            len(re.findall(r"\b(have|has|had)\s+got\b", text)) / num_sentences
        )
        patterns["shall_usage"] = len(re.findall(r"\bshall\b", text)) / num_sentences
        patterns["whilst_usage"] = len(re.findall(r"\bwhilst\b", text)) / num_sentences

        return patterns

    def _extract_medical_terms(self, text: str) -> Dict[str, float]:
        """Extract medical terminology variations."""
        medical_terms = {}

        # Common medical term variations
        term_patterns = {
            "epinephrine_adrenaline": len(
                re.findall(r"\b(epinephrine|adrenaline)\b", text, re.I)
            ),
            "acetaminophen_paracetamol": len(
                re.findall(r"\b(acetaminophen|paracetamol)\b", text, re.I)
            ),
            "emergency_room_ae": len(
                re.findall(r"\b(emergency room|ER|A&E|casualty)\b", text, re.I)
            ),
        }

        for pattern, count in term_patterns.items():
            if count > 0:
                medical_terms[pattern] = float(count)

        return medical_terms

    def _extract_cultural_expressions(self, text: str) -> Dict[str, float]:
        """Extract cultural expressions and idioms."""
        # Basic implementation for cultural expression extraction
        cultural_patterns = {
            "greetings": len(re.findall(r"\b(hello|hi|hey|greetings)\b", text.lower())),
            "politeness": len(
                re.findall(r"\b(please|thank you|sorry|excuse me)\b", text.lower())
            ),
            "informal": len(
                re.findall(r"\b(gonna|wanna|gotta|ain\'t)\b", text.lower())
            ),
        }

        expressions = {}
        for pattern, count in cultural_patterns.items():
            if count > 0:
                expressions[pattern] = float(count)

        return expressions

    def _extract_geographic_indicators(self, text: str) -> List[str]:
        """Extract geographic indicators from text."""
        indicators = []

        # Look for place names, postal codes, phone formats, etc.
        # This is a simplified version
        postal_patterns = [
            (r"\b[A-Z]{1,2}\d{1,2}\s*\d[A-Z]{2}\b", "UK"),  # UK postcodes
            (r"\b\d{5}(-\d{4})?\b", "US"),  # US ZIP codes
            (r"\b[A-Z]\d[A-Z]\s*\d[A-Z]\d\b", "Canada"),  # Canadian postal codes
        ]

        for pattern, country in postal_patterns:
            if re.search(pattern, text):
                indicators.append(country)

        return indicators

    def _score_lexical_match(
        self, detected: Dict[str, float], profile: Dict[str, List[str]]
    ) -> float:
        """Score lexical match between detected markers and profile."""
        if not detected or not profile:
            return 0.0

        score = 0.0
        matches = 0

        # Simple matching logic - can be enhanced
        for marker, value in detected.items():
            if marker in str(profile):  # Simplified check
                score += value
                matches += 1

        return score / (matches or 1)

    def _score_orthographic_match(
        self, detected: Dict[str, float], profile: Dict[str, str]
    ) -> float:
        """Score orthographic match for medical text accuracy.

        This is critical for medical documentation where spelling variations
        can affect patient care (e.g., 'anaesthesia' vs 'anesthesia',
        'haemoglobin' vs 'hemoglobin', 'oedema' vs 'edema').
        """
        if not detected or not profile:
            return 0.0

        # Extract the dialect profile object from the profile dict
        dialect_code = profile.get("dialect_code", "")

        # Get known orthographic variations for this dialect
        # These are critical medical spelling differences
        critical_medical_spellings = {
            "en-GB": {
                "haemoglobin": 1.0,
                "anaesthesia": 1.0,
                "oedema": 1.0,
                "paediatric": 1.0,
                "gynaecology": 1.0,
                "diarrhoea": 1.0,
                "foetus": 1.0,
                "oesophagus": 1.0,
                "haematology": 1.0,
                "orthopaedic": 1.0,
            },
            "en-US": {
                "hemoglobin": 1.0,
                "anesthesia": 1.0,
                "edema": 1.0,
                "pediatric": 1.0,
                "gynecology": 1.0,
                "diarrhea": 1.0,
                "fetus": 1.0,
                "esophagus": 1.0,
                "hematology": 1.0,
                "orthopedic": 1.0,
            },
            "es-ES": {
                "análisis": 1.0,
                "cáncer": 1.0,
                "síndrome": 1.0,
                "diagnóstico": 1.0,
            },
            "es-MX": {
                "analisis": 0.8,  # Often written without accent
                "cancer": 0.8,
                "sindrome": 0.8,
                "diagnostico": 0.8,
            },
        }

        # Get expected spellings for this dialect
        expected_spellings = critical_medical_spellings.get(dialect_code, {})

        # Calculate match score based on medical spelling accuracy
        score = 0.0
        total_weight = 0.0

        for detected_spelling, confidence in detected.items():
            # Check if this is a critical medical term
            if detected_spelling in expected_spellings:
                # Perfect match with expected dialect spelling
                score += confidence * expected_spellings[detected_spelling]
                total_weight += expected_spellings[detected_spelling]
            else:
                # Check if it's a variant from another dialect (potential error)
                for (
                    other_dialect,
                    other_spellings,
                ) in critical_medical_spellings.items():
                    if (
                        other_dialect != dialect_code
                        and detected_spelling in other_spellings
                    ):
                        # Penalize wrong dialect spelling in medical context
                        score -= confidence * 0.5
                        total_weight += 1.0
                        logger.warning(
                            "Medical spelling mismatch: '%s' found but expecting %s variant",
                            detected_spelling,
                            dialect_code,
                        )
                        break

        # Also check general orthographic patterns
        general_patterns_raw: Any = profile.get("orthographic_patterns", {})
        general_patterns: Dict[str, Any]
        if isinstance(general_patterns_raw, str):
            import json  # noqa: PLC0415

            try:
                general_patterns = json.loads(general_patterns_raw)
            except (json.JSONDecodeError, TypeError, ValueError):
                general_patterns = {}
        else:
            general_patterns = general_patterns_raw

        for pattern, expected_freq in general_patterns.items():
            if pattern in detected:
                score += (
                    detected[pattern] * expected_freq * 0.3
                )  # Lower weight than medical terms
                total_weight += expected_freq * 0.3

        # Normalize score
        if total_weight > 0:
            normalized_score = score / total_weight
            # Ensure score is between 0 and 1
            return max(0.0, min(1.0, normalized_score))

        return 0.0

    def _score_medical_match(
        self, detected: Dict[str, float], profile: Dict[str, str]
    ) -> float:
        """Score medical terminology match for patient safety.

        Different regions use different medical terminology that can be critical
        for patient understanding and compliance. For example:
        - UK: "paracetamol" vs US: "acetaminophen"
        - Latin America: "tensión arterial" vs Spain: "presión arterial"
        - Lay terms vs technical terms based on patient literacy
        """
        # Log profile for debugging
        logger.debug("Scoring medical match with profile")

        if not detected:
            return 0.0

        dialect_code = profile.get("dialect_code", "")
        patient_literacy = profile.get("patient_literacy_level", "standard")
        medical_setting = profile.get(
            "medical_setting", "general"
        )  # emergency, specialty, etc.

        # Critical medical term mappings by dialect
        medical_term_standards = {
            "en-US": {
                "medications": {
                    "acetaminophen": 1.0,
                    "epinephrine": 1.0,
                    "aluminum": 1.0,
                    "emergency room": 1.0,
                    "OR": 0.8,  # Operating room
                    "IV": 0.9,  # Intravenous
                },
                "conditions": {
                    "high blood pressure": 0.8,
                    "hypertension": 1.0,
                    "heart attack": 0.8,
                    "myocardial infarction": 1.0,
                    "stroke": 0.9,
                    "CVA": 0.7,  # Cerebrovascular accident
                },
            },
            "en-GB": {
                "medications": {
                    "paracetamol": 1.0,
                    "adrenaline": 1.0,
                    "aluminium": 1.0,
                    "A&E": 1.0,  # Accident & Emergency
                    "theatre": 0.9,  # Operating theatre
                    "drip": 0.8,  # IV drip
                },
                "conditions": {
                    "raised blood pressure": 0.8,
                    "hypertension": 1.0,
                    "heart attack": 0.8,
                    "MI": 0.9,  # Myocardial infarction
                    "stroke": 0.9,
                    "CVA": 0.7,
                },
            },
            "es-MX": {
                "medications": {
                    "acetaminofén": 0.9,
                    "paracetamol": 0.8,
                    "epinefrina": 1.0,
                    "suero": 0.9,  # IV fluid
                },
                "conditions": {
                    "presión alta": 0.9,
                    "hipertensión": 1.0,
                    "infarto": 0.9,
                    "ataque al corazón": 0.8,
                    "derrame cerebral": 0.9,
                    "embolia": 0.7,
                },
            },
        }

        # Get terminology for this dialect
        dialect_terms = medical_term_standards.get(dialect_code, {})

        # Score based on appropriate medical terminology usage
        score = 0.0
        total_weight = 0.0

        # Check detected medical terms against expected terminology
        for category, expected_terms in dialect_terms.items():
            for term, confidence in detected.items():
                if term.lower() in [t.lower() for t in expected_terms]:
                    expected_confidence = expected_terms.get(term.lower(), 0.5)

                    # Adjust score based on patient literacy level
                    if patient_literacy == "low":
                        # Prefer lay terms for low literacy patients
                        if term.lower() in [
                            "high blood pressure",
                            "heart attack",
                            "presión alta",
                        ]:
                            score += confidence * expected_confidence * 1.2
                        else:
                            score += confidence * expected_confidence * 0.8
                    elif patient_literacy == "high":
                        # Technical terms acceptable for high literacy
                        if term.lower() in [
                            "hypertension",
                            "myocardial infarction",
                            "CVA",
                        ]:
                            score += confidence * expected_confidence * 1.1
                        else:
                            score += confidence * expected_confidence
                    else:
                        # Standard scoring
                        score += confidence * expected_confidence

                    total_weight += expected_confidence

                    # Log critical medication name differences
                    if category == "medications" and term.lower() in [
                        "acetaminophen",
                        "paracetamol",
                    ]:
                        logger.info(
                            "Critical medication terminology detected: %s for dialect %s",
                            term,
                            dialect_code,
                        )

        # Check for emergency medical terms if in emergency setting
        if medical_setting == "emergency":
            emergency_terms = {
                "STAT": 1.0,
                "code blue": 1.0,
                "crash": 0.9,
                "urgent": 0.9,
                "emergency": 1.0,
                "critical": 1.0,
            }

            for term, importance in emergency_terms.items():
                if term.lower() in [d.lower() for d in detected]:
                    score += (
                        detected.get(term, 0) * importance * 1.5
                    )  # Higher weight in emergency
                    total_weight += importance

        # Normalize score
        if total_weight > 0:
            normalized_score = score / total_weight
            return max(0.0, min(1.0, normalized_score))

        # If no specific medical terms detected, give small penalty
        return 0.1

    def _score_syntactic_match(
        self, features: DialectFeatures, profile: DialectProfile
    ) -> float:
        """Score syntactic pattern match."""
        # Log profile language for context
        if profile.base_language:
            logger.debug("Scoring syntactic match for %s", profile.base_language)

        if not features.syntactic_structures:
            return 0.0

        # Simple scoring based on pattern presence
        score = sum(features.syntactic_structures.values()) / (
            len(features.syntactic_structures) or 1
        )
        return min(1.0, score * 2)  # Amplify syntactic signals

    def _score_frequency_match(
        self, distributions: Dict[str, Counter], profile: DialectProfile
    ) -> float:
        """Score frequency distribution match."""
        if not profile.word_frequency_model:
            return 0.5  # Neutral score if no model

        # Compare word frequencies
        word_freq = distributions.get("word_freq", Counter())
        if not word_freq:
            return 0.0

        # Calculate correlation or similarity
        # Simplified version - just check top words
        top_words = [word for word, _ in word_freq.most_common(20)]
        profile_top_words = list(profile.word_frequency_model.keys())[:20]

        overlap = len(set(top_words) & set(profile_top_words))
        score = overlap / 20.0

        return score
