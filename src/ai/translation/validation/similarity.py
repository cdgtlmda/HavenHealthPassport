"""
Similarity Scoring for Translation Validation.

This module implements various similarity scoring methods to validate
the quality of medical translations by comparing semantic, syntactic,
and structural similarity between source and translated texts.
"""

import logging
import re
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import editdistance
import nltk
import numpy as np
from nltk.translate.bleu_score import SmoothingFunction, sentence_bleu
from nltk.translate.meteor_score import meteor_score
from rouge_score import rouge_scorer
from sentence_transformers import SentenceTransformer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# Download required NLTK data
try:
    nltk.download("wordnet", quiet=True)
    nltk.download("punkt", quiet=True)
    nltk.download("punkt_tab", quiet=True)  # Add punkt_tab for newer NLTK versions
    nltk.download("stopwords", quiet=True)
except (OSError, LookupError):
    pass

logger = logging.getLogger(__name__)


class SimilarityMetric(Enum):
    """Available similarity metrics."""

    SEMANTIC = "semantic"  # Embedding-based semantic similarity
    BLEU = "bleu"  # BiLingual Evaluation Understudy
    ROUGE = "rouge"  # Recall-Oriented Understudy for Gisting Evaluation
    METEOR = "meteor"  # Metric for Evaluation of Translation with Explicit ORdering
    LEVENSHTEIN = "levenshtein"  # Edit distance
    JACCARD = "jaccard"  # Token overlap
    COSINE = "cosine"  # Cosine similarity
    MEDICAL = "medical"  # Medical-specific similarity


@dataclass
class SimilarityScore:
    """Container for similarity scores."""

    metric: SimilarityMetric
    score: float
    details: Dict[str, Any]
    confidence: float = 1.0

    def is_acceptable(self, threshold: float = 0.8) -> bool:
        """Check if score meets threshold."""
        return self.score >= threshold


@dataclass
class SimilarityConfig:
    """Configuration for similarity scoring."""

    # Model settings
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    medical_embedding_model: str = "cambridgeltl/SapBERT-from-PubMedBERT-fulltext"

    # Metric weights for composite scoring
    metric_weights: Optional[Dict[SimilarityMetric, float]] = None

    # Thresholds
    min_semantic_similarity: float = 0.85
    min_bleu_score: float = 0.6
    min_rouge_score: float = 0.7
    min_medical_similarity: float = 0.9

    # Processing options
    use_cache: bool = True
    normalize_scores: bool = True
    include_subword_analysis: bool = True

    def __post_init__(self) -> None:
        """Initialize default weights if not provided."""
        if self.metric_weights is None:
            self.metric_weights = {
                SimilarityMetric.SEMANTIC: 0.3,
                SimilarityMetric.BLEU: 0.2,
                SimilarityMetric.ROUGE: 0.2,
                SimilarityMetric.MEDICAL: 0.3,
            }


class SimilarityScorer:
    """
    Calculates similarity scores between source and translated texts.

    Implements multiple similarity metrics optimized for medical translations.
    """

    def __init__(self, config: Optional[SimilarityConfig] = None):
        """Initialize similarity scorer with configuration."""
        self.config = config or SimilarityConfig()

        # Initialize models lazily
        self._general_model: Optional[SentenceTransformer] = None
        self._medical_model: Optional[SentenceTransformer] = None

        # Initialize scorers
        self.rouge_scorer = rouge_scorer.RougeScorer(
            ["rouge1", "rouge2", "rougeL"], use_stemmer=True
        )

        # Cache for embeddings
        self._embedding_cache: Optional[Dict[str, np.ndarray]] = (
            {} if self.config.use_cache else None
        )

    @property
    def general_model(self) -> SentenceTransformer:
        """Lazy load general embedding model."""
        if self._general_model is None:
            logger.info("Loading embedding model: %s", self.config.embedding_model)
            self._general_model = SentenceTransformer(self.config.embedding_model)
        return self._general_model

    @property
    def medical_model(self) -> SentenceTransformer:
        """Lazy load medical embedding model."""
        if self._medical_model is None:
            logger.info(
                "Loading medical model: %s", self.config.medical_embedding_model
            )
            self._medical_model = SentenceTransformer(
                self.config.medical_embedding_model
            )
        return self._medical_model

    def calculate_similarity(
        self,
        source_text: str,
        translated_text: str,
        metrics: Optional[List[SimilarityMetric]] = None,
        source_lang: Optional[str] = None,
        target_lang: Optional[str] = None,
    ) -> Dict[SimilarityMetric, SimilarityScore]:
        """
        Calculate similarity scores using specified metrics.

        Args:
            source_text: Original text
            translated_text: Translated text
            metrics: List of metrics to calculate (None = all)
            source_lang: Source language code
            target_lang: Target language code

        Returns:
            Dictionary of metric to similarity scores
        """
        if metrics is None:
            metrics = list(SimilarityMetric)

        # source_lang is kept for API consistency and future language-specific processing
        _ = source_lang

        scores: Dict[SimilarityMetric, SimilarityScore] = {}

        for metric in metrics:
            try:
                if metric == SimilarityMetric.SEMANTIC:
                    scores[metric] = self._calculate_semantic_similarity(
                        source_text, translated_text
                    )
                elif metric == SimilarityMetric.BLEU:
                    scores[metric] = self._calculate_bleu_score(
                        source_text, translated_text
                    )
                elif metric == SimilarityMetric.ROUGE:
                    scores[metric] = self._calculate_rouge_score(
                        source_text, translated_text
                    )
                elif metric == SimilarityMetric.METEOR:
                    scores[metric] = self._calculate_meteor_score(
                        source_text, translated_text, target_lang
                    )
                elif metric == SimilarityMetric.LEVENSHTEIN:
                    scores[metric] = self._calculate_levenshtein_similarity(
                        source_text, translated_text
                    )
                elif metric == SimilarityMetric.JACCARD:
                    scores[metric] = self._calculate_jaccard_similarity(
                        source_text, translated_text
                    )
                elif metric == SimilarityMetric.COSINE:
                    scores[metric] = self._calculate_cosine_similarity(
                        source_text, translated_text
                    )
                elif metric == SimilarityMetric.MEDICAL:
                    scores[metric] = self._calculate_medical_similarity(
                        source_text, translated_text
                    )
            except (ValueError, AttributeError, KeyError) as e:
                logger.error("Error calculating %s similarity: %s", metric.value, e)
                scores[metric] = SimilarityScore(
                    metric=metric, score=0.0, details={"error": str(e)}, confidence=0.0
                )

        return scores

    def calculate_composite_score(
        self,
        scores: Dict[SimilarityMetric, SimilarityScore],
        weights: Optional[Dict[SimilarityMetric, float]] = None,
    ) -> float:
        """Calculate weighted composite similarity score."""
        if not scores:
            return 0.0

        weights = weights or self.config.metric_weights

        total_weight = 0.0
        weighted_score = 0.0

        for metric, score in scores.items():
            if weights and metric in weights:
                weight = weights[metric] * score.confidence
                weighted_score += score.score * weight
                total_weight += weight

        return weighted_score / total_weight if total_weight > 0 else 0.0

    def _get_embedding(self, text: str, use_medical_model: bool = False) -> np.ndarray:
        """Get cached text embedding."""
        cache_key = f"{text}_{use_medical_model}"

        if self._embedding_cache is not None and cache_key in self._embedding_cache:
            return np.asarray(self._embedding_cache[cache_key])

        model = self.medical_model if use_medical_model else self.general_model
        embedding = model.encode(text, convert_to_numpy=True)

        if self._embedding_cache is not None:
            # Limit cache size to prevent memory issues
            if len(self._embedding_cache) > 1000:
                # Remove oldest entries
                oldest_keys = list(self._embedding_cache.keys())[:100]
                for key in oldest_keys:
                    del self._embedding_cache[key]
            self._embedding_cache[cache_key] = embedding

        return embedding

    def _calculate_semantic_similarity(
        self, source_text: str, translated_text: str
    ) -> SimilarityScore:
        """Calculate semantic similarity using embeddings."""
        # Get embeddings
        source_embedding = self._get_embedding(source_text)
        translated_embedding = self._get_embedding(translated_text)

        # Calculate cosine similarity
        similarity = cosine_similarity(
            source_embedding.reshape(1, -1), translated_embedding.reshape(1, -1)
        )[0][0]

        return SimilarityScore(
            metric=SimilarityMetric.SEMANTIC,
            score=float(similarity),
            details={
                "model": self.config.embedding_model,
                "embedding_dim": len(source_embedding),
            },
        )

    def _calculate_bleu_score(
        self, source_text: str, translated_text: str
    ) -> SimilarityScore:
        """Calculate BLEU score."""
        # Tokenize texts
        source_tokens = nltk.word_tokenize(source_text.lower())
        translated_tokens = nltk.word_tokenize(translated_text.lower())

        # Calculate BLEU with smoothing
        smoothing = SmoothingFunction().method4
        bleu_score = sentence_bleu(
            [source_tokens], translated_tokens, smoothing_function=smoothing
        )

        return SimilarityScore(
            metric=SimilarityMetric.BLEU,
            score=float(bleu_score),
            details={
                "source_length": len(source_tokens),
                "translated_length": len(translated_tokens),
            },
        )

    def _calculate_rouge_score(
        self, source_text: str, translated_text: str
    ) -> SimilarityScore:
        """Calculate ROUGE scores."""
        scores = self.rouge_scorer.score(source_text, translated_text)

        # Use ROUGE-L F1 as primary score
        rouge_l_f1 = scores["rougeL"].fmeasure

        return SimilarityScore(
            metric=SimilarityMetric.ROUGE,
            score=float(rouge_l_f1),
            details={
                "rouge1_f1": scores["rouge1"].fmeasure,
                "rouge2_f1": scores["rouge2"].fmeasure,
                "rougeL_f1": scores["rougeL"].fmeasure,
                "rouge1_precision": scores["rouge1"].precision,
                "rouge1_recall": scores["rouge1"].recall,
            },
        )

    def _calculate_meteor_score(
        self, source_text: str, translated_text: str, language: Optional[str] = None
    ) -> SimilarityScore:
        """Calculate METEOR score."""
        # Tokenize texts
        source_tokens = nltk.word_tokenize(source_text.lower())
        translated_tokens = nltk.word_tokenize(translated_text.lower())

        # Calculate METEOR
        try:
            score = meteor_score([source_tokens], translated_tokens)
        except (ValueError, TypeError, LookupError):
            # Fallback if METEOR fails
            score = 0.0

        return SimilarityScore(
            metric=SimilarityMetric.METEOR,
            score=float(score),
            details={"language": language or "en"},
        )

    def _calculate_levenshtein_similarity(
        self, source_text: str, translated_text: str
    ) -> SimilarityScore:
        """Calculate normalized Levenshtein similarity."""
        distance = editdistance.eval(source_text, translated_text)
        max_len = max(len(source_text), len(translated_text))

        similarity = 1.0 - (distance / max_len) if max_len > 0 else 1.0

        return SimilarityScore(
            metric=SimilarityMetric.LEVENSHTEIN,
            score=float(similarity),
            details={"edit_distance": distance, "max_length": max_len},
        )

    def _calculate_jaccard_similarity(
        self, source_text: str, translated_text: str
    ) -> SimilarityScore:
        """Calculate Jaccard similarity on tokens."""
        # Tokenize and create sets
        source_tokens = set(nltk.word_tokenize(source_text.lower()))
        translated_tokens = set(nltk.word_tokenize(translated_text.lower()))

        # Calculate Jaccard
        intersection = source_tokens.intersection(translated_tokens)
        union = source_tokens.union(translated_tokens)

        similarity = len(intersection) / len(union) if union else 0.0

        return SimilarityScore(
            metric=SimilarityMetric.JACCARD,
            score=float(similarity),
            details={"intersection_size": len(intersection), "union_size": len(union)},
        )

    def _calculate_cosine_similarity(
        self, source_text: str, translated_text: str
    ) -> SimilarityScore:
        """Calculate TF-IDF based cosine similarity."""
        # Create TF-IDF vectors
        vectorizer = TfidfVectorizer()
        tfidf_matrix = vectorizer.fit_transform([source_text, translated_text])

        # Calculate cosine similarity
        similarity = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])[0][0]

        return SimilarityScore(
            metric=SimilarityMetric.COSINE,
            score=float(similarity),
            details={"vocabulary_size": len(vectorizer.vocabulary_)},
        )

    def _calculate_medical_similarity(
        self, source_text: str, translated_text: str
    ) -> SimilarityScore:
        """Calculate medical-specific similarity using medical embeddings."""
        # Extract medical terms
        medical_terms_source = self._extract_medical_terms(source_text)
        medical_terms_translated = self._extract_medical_terms(translated_text)

        # Get medical embeddings
        source_embedding = self._get_embedding(source_text, use_medical_model=True)
        translated_embedding = self._get_embedding(
            translated_text, use_medical_model=True
        )

        # Calculate similarity
        similarity = cosine_similarity(
            source_embedding.reshape(1, -1), translated_embedding.reshape(1, -1)
        )[0][0]

        # Adjust score based on medical term preservation
        term_preservation = len(medical_terms_translated) / max(
            len(medical_terms_source), 1
        )
        adjusted_score = similarity * (0.7 + 0.3 * min(term_preservation, 1.0))

        return SimilarityScore(
            metric=SimilarityMetric.MEDICAL,
            score=float(adjusted_score),
            details={
                "raw_similarity": float(similarity),
                "medical_terms_source": len(medical_terms_source),
                "medical_terms_translated": len(medical_terms_translated),
                "term_preservation_ratio": term_preservation,
                "model": self.config.medical_embedding_model,
            },
        )

    def _extract_medical_terms(self, text: str) -> List[str]:
        """Extract medical terms from text."""
        # Simple extraction - in production, use medical NER

        # Common medical patterns
        patterns = [
            r"\b\d+\s*(?:mg|g|mcg|ml|mL|L|IU|units?)\b",  # Dosages
            r"\b[A-Z][a-z]+(?:in|ol|ide|ate|ine)\b",  # Drug names
            r"\b(?:hyper|hypo|brady|tachy|dys)\w+\b",  # Medical prefixes
            r"\b\w+(?:itis|osis|emia|pathy)\b",  # Medical suffixes
        ]

        terms = []
        for pattern in patterns:
            terms.extend(re.findall(pattern, text, re.IGNORECASE))

        return list(set(terms))

    def validate_similarity(
        self,
        source_text: str,
        translated_text: str,
        required_metrics: Optional[List[SimilarityMetric]] = None,
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Validate translation similarity against configured thresholds.

        Returns:
            Tuple of (is_valid, details)
        """
        # Calculate scores
        scores = self.calculate_similarity(
            source_text, translated_text, metrics=required_metrics
        )

        # Check thresholds
        failures = []

        if SimilarityMetric.SEMANTIC in scores:
            if (
                scores[SimilarityMetric.SEMANTIC].score
                < self.config.min_semantic_similarity
            ):
                failures.append(
                    f"Semantic similarity too low: {scores[SimilarityMetric.SEMANTIC].score:.2f}"
                )

        if SimilarityMetric.MEDICAL in scores:
            if (
                scores[SimilarityMetric.MEDICAL].score
                < self.config.min_medical_similarity
            ):
                failures.append(
                    f"Medical similarity too low: {scores[SimilarityMetric.MEDICAL].score:.2f}"
                )

        # Calculate composite score
        composite_score = self.calculate_composite_score(scores)

        is_valid = len(failures) == 0

        return is_valid, {
            "composite_score": composite_score,
            "scores": {metric.value: score.score for metric, score in scores.items()},
            "failures": failures,
            "details": {
                metric.value: score.details for metric, score in scores.items()
            },
        }
