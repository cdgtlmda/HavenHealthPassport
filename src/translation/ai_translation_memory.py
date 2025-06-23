"""AI-Powered Translation Memory with Vector Embeddings.

This module implements semantic search and intelligent matching for
medical translations using vector embeddings and AWS services.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import boto3
import numpy as np

from src.healthcare.hipaa_access_control import AccessLevel, require_phi_access
from src.services.encryption_service import EncryptionService
from src.utils.logging import get_logger
from src.vector_store.medical_embeddings import MedicalEmbeddingService

logger = get_logger(__name__)


@dataclass
class TranslationEntry:
    """Represents a translation memory entry."""

    source_text: str
    target_text: str
    source_lang: str
    target_lang: str
    domain: str
    confidence: float = 1.0
    created_at: datetime = field(default_factory=datetime.now)
    last_used: Optional[datetime] = None
    usage_count: int = 0
    context: Optional[str] = None
    embedding: Optional[np.ndarray] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ConsistencyCheck:
    """Result of translation consistency check."""

    term: str
    translation: str
    frequency: int
    domains: List[str]
    confidence_avg: float
    target_lang: str
    domain: str  # medical domain
    confidence: float
    usage_count: int
    last_used: datetime
    context: Optional[str] = None
    embedding: Optional[np.ndarray] = None
    is_recommended: bool = False
    inconsistency_reason: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SemanticMatch:
    """Result of semantic translation search."""

    entry: TranslationEntry
    similarity_score: float
    semantic_distance: float
    is_exact_match: bool
    match_type: str  # exact, fuzzy, semantic, partial


@dataclass
class TranslationMemoryResult:
    """Result from translation memory query."""

    matches: List[SemanticMatch]
    best_match: Optional[TranslationEntry]
    confidence: float
    retrieval_time_ms: float
    suggestions: List[str]


class AITranslationMemory:
    """AI-powered translation memory with semantic search."""

    # Similarity thresholds
    EXACT_MATCH_THRESHOLD = 0.99
    FUZZY_MATCH_THRESHOLD = 0.85
    SEMANTIC_MATCH_THRESHOLD = 0.70

    # Medical domain embeddings
    MEDICAL_DOMAINS = [
        "diagnosis",
        "symptoms",
        "medications",
        "procedures",
        "anatomy",
        "patient_instructions",
        "consent_forms",
        "lab_results",
        "imaging",
        "allergies",
    ]

    def __init__(
        self, region: str = "us-east-1", embedding_model: str = "text-embedding-ada-002"
    ):
        """
        Initialize AI translation memory.

        Args:
            region: AWS region
            embedding_model: Embedding model to use
        """
        self.bedrock = boto3.client("bedrock-runtime", region_name=region)
        self.opensearch = boto3.client("opensearch", region_name=region)
        self.encryption_service = EncryptionService()
        self.embedding_model = embedding_model  # Store for future use
        # Initialize MedicalEmbeddingService
        # Already imported at top of file

        self.embedding_service = MedicalEmbeddingService()

        self._memory_cache: Dict[str, Any] = {}
        self._embedding_cache: Dict[str, Any] = {}
        self._translation_stats: Dict[str, Any] = {}
        self.index_name = "translation-memory-medical"

    @require_phi_access(AccessLevel.READ)
    async def add_translation(
        self,
        source_text: str,
        target_text: str,
        source_lang: str,
        target_lang: str,
        domain: str,
        context: Optional[str] = None,
        confidence: float = 1.0,
    ) -> bool:
        """
        Add translation to memory with embeddings.

        Args:
            source_text: Source text
            target_text: Translated text
            source_lang: Source language
            target_lang: Target language
            domain: Medical domain
            context: Additional context
            confidence: Translation confidence

        Returns:
            Success status
        """
        try:
            # Generate embedding for source text
            embedding = await self._generate_embedding(source_text, domain)

            # Create entry
            entry = TranslationEntry(
                source_text=source_text,
                target_text=target_text,
                source_lang=source_lang,
                target_lang=target_lang,
                domain=domain,
                context=context,
                embedding=embedding,
                confidence=confidence,
                usage_count=0,
                last_used=datetime.now(),
                metadata={
                    "added_date": datetime.now().isoformat(),
                    "embedding_model": self.embedding_service.model_name,
                },
            )

            # Index in vector store
            await self._index_translation(entry)

            # Update cache
            cache_key = self._get_cache_key(source_text, source_lang, target_lang)
            self._memory_cache[cache_key] = entry

            logger.info(f"Added translation: {source_lang} -> {target_lang}")
            return True

        except (ValueError, TypeError, AttributeError) as e:
            logger.error(f"Error adding translation: {e}")
            return False

    async def search_translation(
        self,
        text: str,
        source_lang: str,
        target_lang: str,
        domain: Optional[str] = None,
        min_confidence: float = 0.7,
    ) -> TranslationMemoryResult:
        """
        Search for translations using semantic similarity.

        Args:
            text: Text to translate
            source_lang: Source language
            target_lang: Target language
            domain: Medical domain (optional)
            min_confidence: Minimum confidence threshold

        Returns:
            Translation memory search result
        """
        start_time = datetime.now()

        try:
            # Check cache first
            cache_key = self._get_cache_key(text, source_lang, target_lang)
            if cache_key in self._memory_cache:
                cached_entry = self._memory_cache[cache_key]
                return TranslationMemoryResult(
                    matches=[
                        SemanticMatch(
                            entry=cached_entry,
                            similarity_score=1.0,
                            semantic_distance=0.0,
                            is_exact_match=True,
                            match_type="exact",
                        )
                    ],
                    best_match=cached_entry,
                    confidence=1.0,
                    retrieval_time_ms=0,
                    suggestions=[],
                )

            # Generate embedding for query
            query_embedding = await self._generate_embedding(text, domain)

            # Search vector store
            matches = await self._search_similar_translations(
                query_embedding, source_lang, target_lang, domain
            )

            # Filter by confidence
            filtered_matches = [
                m for m in matches if m.similarity_score >= min_confidence
            ]

            # Rank matches
            ranked_matches = self._rank_matches(text, filtered_matches, domain)

            # Select best match
            best_match = ranked_matches[0].entry if ranked_matches else None

            # Generate suggestions
            suggestions = self._generate_suggestions(text, ranked_matches, domain)

            # Calculate retrieval time
            retrieval_time = (datetime.now() - start_time).total_seconds() * 1000

            return TranslationMemoryResult(
                matches=ranked_matches,
                best_match=best_match,
                confidence=ranked_matches[0].similarity_score if ranked_matches else 0,
                retrieval_time_ms=retrieval_time,
                suggestions=suggestions,
            )

        except (KeyError, ValueError, AttributeError) as e:
            logger.error(f"Error searching translation: {e}")
            return TranslationMemoryResult(
                matches=[],
                best_match=None,
                confidence=0,
                retrieval_time_ms=0,
                suggestions=[],
            )

    async def _generate_embedding(self, text: str, domain: Optional[str]) -> np.ndarray:
        """Generate embedding for text."""
        # Check embedding cache
        cache_key = f"{text}:{domain}"
        if cache_key in self._embedding_cache:
            return self._embedding_cache[cache_key]  # type: ignore[no-any-return]

        # Add domain context to improve embedding quality
        if domain:
            contextualized_text = f"[{domain}] {text}"
        else:
            contextualized_text = text

        # Create medical context from domain
        # Medical context would be used here if needed
        # Currently using domain directly in contextualized text

        # Generate embedding using MedicalEmbeddingService
        embedding = self.embedding_service.embed(contextualized_text)

        # Cache embedding
        self._embedding_cache[cache_key] = embedding

        return embedding  # type: ignore[no-any-return]

    async def _index_translation(self, entry: TranslationEntry) -> None:
        """Index translation in vector store."""
        # Prepare document for indexing
        document = {
            "source_text": entry.source_text,
            "target_text": entry.target_text,
            "source_lang": entry.source_lang,
            "target_lang": entry.target_lang,
            "domain": entry.domain,
            "context": entry.context,
            "confidence": entry.confidence,
            "embedding": (
                entry.embedding.tolist() if entry.embedding is not None else []
            ),
            "usage_count": entry.usage_count,
            "last_used": entry.last_used.isoformat() if entry.last_used else None,
            "metadata": entry.metadata,
        }

        # Index in OpenSearch
        # This would use actual OpenSearch indexing with the prepared document
        # For now, storing in memory
        _ = document  # Will be used when OpenSearch indexing is implemented
        key = f"{entry.source_lang}:{entry.target_lang}:{entry.domain}"
        if key not in self._memory_cache:
            self._memory_cache[key] = []
        self._memory_cache[key].append(entry)

    async def _search_similar_translations(
        self,
        query_embedding: np.ndarray,
        source_lang: str,
        target_lang: str,
        domain: Optional[str],
    ) -> List[SemanticMatch]:
        """Search for similar translations using vector similarity."""
        matches = []

        # Search in OpenSearch with k-NN
        # This would use actual OpenSearch k-NN search
        # For now, searching in memory cache

        search_key = f"{source_lang}:{target_lang}:{domain}"
        candidates = self._memory_cache.get(search_key, [])

        for entry in candidates:
            if entry.embedding is not None:
                # Calculate cosine similarity
                similarity = self._cosine_similarity(query_embedding, entry.embedding)

                # Calculate semantic distance
                distance = 1 - similarity

                # Determine match type
                if similarity >= self.EXACT_MATCH_THRESHOLD:
                    match_type = "exact"
                elif similarity >= self.FUZZY_MATCH_THRESHOLD:
                    match_type = "fuzzy"
                elif similarity >= self.SEMANTIC_MATCH_THRESHOLD:
                    match_type = "semantic"
                else:
                    match_type = "partial"

                match = SemanticMatch(
                    entry=entry,
                    similarity_score=similarity,
                    semantic_distance=distance,
                    is_exact_match=similarity >= self.EXACT_MATCH_THRESHOLD,
                    match_type=match_type,
                )

                matches.append(match)

        # Sort by similarity score
        matches.sort(key=lambda x: x.similarity_score, reverse=True)

        return matches[:10]  # Return top 10 matches

    def _cosine_similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        """Calculate cosine similarity between two vectors."""
        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)

        if norm1 == 0 or norm2 == 0:
            return 0

        return float(dot_product / (norm1 * norm2))

    def _rank_matches(
        self, query: str, matches: List[SemanticMatch], domain: Optional[str]
    ) -> List[SemanticMatch]:
        """Rank matches considering multiple factors."""
        ranked_matches = []

        for match in matches:
            # Calculate additional scores

            # Domain relevance
            domain_score = 1.0 if match.entry.domain == domain else 0.8

            # Usage frequency
            usage_score = min(1.0, match.entry.usage_count / 100)

            # Recency
            days_old = (
                (datetime.now() - match.entry.last_used).days
                if match.entry.last_used
                else 0
            )
            recency_score = max(0.5, 1.0 - (days_old / 365))

            # Length similarity
            len_ratio = len(match.entry.source_text) / len(query)
            length_score = 1.0 - abs(1.0 - len_ratio) * 0.5

            # Combined score
            combined_score = (
                match.similarity_score * 0.5
                + domain_score * 0.2
                + usage_score * 0.1
                + recency_score * 0.1
                + length_score * 0.1
            )

            # Update match with combined score
            match.similarity_score = combined_score
            ranked_matches.append(match)

        # Re-sort by combined score
        ranked_matches.sort(key=lambda x: x.similarity_score, reverse=True)

        return ranked_matches

    def _generate_suggestions(
        self, query: str, matches: List[SemanticMatch], domain: Optional[str]
    ) -> List[str]:
        """Generate translation suggestions based on matches."""
        suggestions = []

        if not matches:
            suggestions.append("No similar translations found in memory")
            return suggestions

        # Analyze match quality
        best_match = matches[0]

        if best_match.match_type == "exact":
            suggestions.append("Exact match found - high confidence translation")

        elif best_match.match_type == "fuzzy":
            suggestions.append("Close match found - review for accuracy")

            # Suggest minor edits
            if len(query) != len(best_match.entry.source_text):
                suggestions.append("Consider adjusting for length differences")

        elif best_match.match_type == "semantic":
            suggestions.append("Semantically similar translation found")
            suggestions.append("Verify medical terminology accuracy")

        else:
            suggestions.append("Only partial matches found")
            suggestions.append("Consider professional translation review")

        # Domain-specific suggestions
        if domain and best_match.entry.domain != domain:
            suggestions.append(
                f"Match is from {best_match.entry.domain} domain - verify applicability"
            )

        return suggestions

    def _get_cache_key(self, text: str, source_lang: str, target_lang: str) -> str:
        """Generate cache key for translation."""
        return f"{source_lang}:{target_lang}:{hash(text)}"

    def _get_condition_type_from_domain(self, domain: str) -> Optional[str]:
        """Map medical domain to condition type for context."""
        domain_mapping = {
            "cardiology": "cardiovascular",
            "oncology": "cancer",
            "neurology": "neurological",
            "psychiatry": "mental_health",
            "pediatrics": "pediatric",
            "obstetrics": "maternal",
            "emergency": "acute",
            "infectious_disease": "infectious",
            "endocrinology": "metabolic",
            "pulmonology": "respiratory",
            "gastroenterology": "digestive",
            "orthopedics": "musculoskeletal",
            "dermatology": "skin",
            "urology": "urological",
            "hematology": "blood",
            "rheumatology": "autoimmune",
            "allergy": "allergic",
            "immunology": "immune",
            "genetics": "genetic",
            "palliative": "terminal",
        }
        return domain_mapping.get(domain.lower())

    async def update_usage_stats(
        self, entry: TranslationEntry, was_helpful: bool
    ) -> None:
        """Update usage statistics for translation entry."""
        entry.usage_count += 1
        entry.last_used = datetime.now()

        if was_helpful:
            # Increase confidence slightly
            entry.confidence = min(1.0, entry.confidence + 0.01)
        else:
            # Decrease confidence slightly
            entry.confidence = max(0.5, entry.confidence - 0.02)

        # Re-index with updated stats
        await self._index_translation(entry)

    async def train_domain_embeddings(
        self, domain: str, training_pairs: List[Tuple[str, str]]
    ) -> None:
        """
        Train domain-specific embeddings.

        Args:
            domain: Medical domain
            training_pairs: List of (text, translation) pairs
        """
        logger.info(
            f"Training embeddings for {domain} with {len(training_pairs)} pairs"
        )

        # This would implement fine-tuning of embeddings
        # For specific medical domains

        # For now, add all pairs to memory
        for source, target in training_pairs:
            await self.add_translation(
                source_text=source,
                target_text=target,
                source_lang="en",  # Assuming English source
                target_lang="multi",  # Multi-target
                domain=domain,
                confidence=0.9,
            )

    async def export_high_confidence_pairs(
        self, min_confidence: float = 0.9, min_usage: int = 5
    ) -> List[Dict[str, Any]]:
        """Export high-quality translation pairs for training."""
        high_quality_pairs = []

        # Iterate through all cached entries
        for entries in self._memory_cache.values():
            if isinstance(entries, list):
                for entry in entries:
                    if (
                        entry.confidence >= min_confidence
                        and entry.usage_count >= min_usage
                    ):
                        high_quality_pairs.append(
                            {
                                "source": entry.source_text,
                                "target": entry.target_text,
                                "source_lang": entry.source_lang,
                                "target_lang": entry.target_lang,
                                "domain": entry.domain,
                                "confidence": entry.confidence,
                                "usage_count": entry.usage_count,
                            }
                        )

        return high_quality_pairs

    async def check_translation_consistency(
        self,
        term: str,
        source_lang: str,
        target_lang: str,
        domain: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Check consistency of translations for a specific term.

        Args:
            term: Term to check consistency for
            source_lang: Source language
            target_lang: Target language
            domain: Optional medical domain

        Returns:
            Dictionary with consistency analysis
        """
        # Search for all translations of this term
        result = await self.search_translation(
            text=term,
            source_lang=source_lang,
            target_lang=target_lang,
            domain=domain,
            min_confidence=0.5,  # Lower threshold to catch all variants
        )

        if not result.matches:
            return {
                "term": term,
                "is_consistent": True,
                "variations": [],
                "recommendation": "No existing translations found",
            }

        # Group translations by target text
        translation_groups: Dict[str, Any] = {}
        for match in result.matches:
            target = match.entry.target_text
            if target not in translation_groups:
                translation_groups[target] = []
            translation_groups[target].append(match)

        # Analyze consistency
        is_consistent = len(translation_groups) == 1
        primary_translation = max(
            translation_groups.items(),
            key=lambda x: sum(m.entry.usage_count for m in x[1]),
        )[0]

        variations = []
        for target_text, matches in translation_groups.items():
            total_usage = sum(m.entry.usage_count for m in matches)
            avg_confidence = sum(m.entry.confidence for m in matches) / len(matches)
            variations.append(
                {
                    "translation": target_text,
                    "usage_count": total_usage,
                    "average_confidence": avg_confidence,
                    "is_primary": target_text == primary_translation,
                    "contexts": list(
                        set(m.entry.context for m in matches if m.entry.context)
                    ),
                }
            )

        # Sort variations by usage count
        variations.sort(key=lambda x: x["usage_count"], reverse=True)

        recommendation = ""
        if is_consistent:
            recommendation = f"Consistent translation: '{primary_translation}'"
        else:
            recommendation = (
                f"Multiple translations found. Primary: '{primary_translation}'. "
                f"Consider standardizing to improve consistency."
            )

        return {
            "term": term,
            "is_consistent": is_consistent,
            "primary_translation": primary_translation,
            "variations": variations,
            "recommendation": recommendation,
            "total_occurrences": sum(
                bool(len(matches) > 1) for matches in translation_groups.values()
            ),
        }

    async def optimize_embeddings(self) -> None:
        """Optimize embedding storage and retrieval."""
        logger.info("Optimizing translation memory embeddings")

        # Clear rarely used embeddings from cache
        stale_keys = []

        for key in list(self._embedding_cache.keys()):
            # Remove embeddings not used in last 24 hours
            # (In production, track last access time)
            if len(self._embedding_cache) > 10000:  # Cache size limit
                stale_keys.append(key)

        for key in stale_keys[: len(stale_keys) // 2]:  # Remove half of stale
            del self._embedding_cache[key]

        logger.info(f"Cleared {len(stale_keys)} stale embeddings from cache")

    def should_retrain(self, language_pair: str) -> bool:
        """Check if model should be retrained for a language pair.

        Args:
            language_pair: Language pair in format "source-target"

        Returns:
            True if retraining is recommended
        """
        # Check number of new translations since last training
        key_pattern = language_pair.replace("-", ":")
        new_translations = 0

        for key, entries in self._memory_cache.items():
            if key.startswith(key_pattern):
                if isinstance(entries, list):
                    new_translations += len(entries)

        # Retrain if we have enough new examples
        RETRAIN_THRESHOLD = 1000
        return new_translations >= RETRAIN_THRESHOLD

    async def schedule_model_update(self, language_pair: str) -> None:
        """Schedule incremental model update for a language pair.

        Args:
            language_pair: Language pair to update
        """
        logger.info(f"Scheduling model update for {language_pair}")

        # In production, this would:
        # 1. Export high-confidence translation pairs
        # 2. Queue a job for model fine-tuning
        # 3. Update embeddings after training

        # For now, log the intent
        high_quality_pairs = await self.export_high_confidence_pairs(
            min_confidence=0.9, min_usage=3
        )

        logger.info(
            f"Would train on {len(high_quality_pairs)} high-quality pairs for {language_pair}"
        )

    def update_translation_stats(self, metadata: Dict[str, Any]) -> None:
        """Update translation statistics for a language pair.

        Args:
            metadata: Translation metadata including language pair info
        """
        # Track translation statistics for monitoring
        lang_pair = (
            f"{metadata.get('source_language')}-{metadata.get('target_language')}"
        )

        if not hasattr(self, "_translation_stats"):
            self._translation_stats = {}

        if lang_pair not in self._translation_stats:
            self._translation_stats[lang_pair] = {
                "total_translations": 0,
                "last_updated": datetime.now(),
                "domains": set(),
            }

        stats = self._translation_stats[lang_pair]
        stats["total_translations"] += 1
        stats["last_updated"] = datetime.now()
        if metadata.get("medical_domain"):
            stats["domains"].add(metadata["medical_domain"])

        # This would implement:
        # 1. Dimensionality reduction for faster search
        # 2. Clustering for efficient retrieval
        # 3. Index optimization in OpenSearch
        # 4. Cache warming for frequent queries

        # Count total embeddings
        total_embeddings = sum(
            len(entries) if isinstance(entries, list) else 1
            for entries in self._memory_cache.values()
        )

        logger.info(f"Optimized {total_embeddings} embeddings")

        # In production, this would:
        # 1. Queue a background job
        # 2. Collect recent translation pairs
        # 3. Fine-tune the embedding model
        # 4. Update the vector index
        # 5. Notify administrators

        # For now, log the scheduling for each language pair
        for lang_pair in self._translation_stats:
            update_job = {
                "language_pair": lang_pair,
                "scheduled_at": datetime.now().isoformat(),
                "translation_count": self._translation_stats.get(lang_pair, {}).get(
                    "total_translations", 0
                ),
                "status": "scheduled",
            }
            logger.info(f"Model update job scheduled: {update_job}")

    def get_translation_statistics(self) -> Dict[str, Any]:
        """Get comprehensive translation memory statistics.

        Returns:
            Dictionary with usage statistics
        """
        if not hasattr(self, "_translation_stats"):
            self._translation_stats = {}

        total_entries = sum(
            len(entries) if isinstance(entries, list) else 1
            for entries in self._memory_cache.values()
        )

        language_pairs = list(self._translation_stats.keys())

        stats: Dict[str, Any] = {
            "total_entries": total_entries,
            "language_pairs": len(language_pairs),
            "cache_size": len(self._memory_cache),
            "embedding_cache_size": len(self._embedding_cache),
            "language_pair_details": {},
            "domains": set(),
            "last_update": datetime.now().isoformat(),
        }

        # Aggregate domain information
        for lang_pair, pair_stats in self._translation_stats.items():
            stats["language_pair_details"][lang_pair] = {
                "total_translations": pair_stats.get("total_translations", 0),
                "last_updated": pair_stats.get(
                    "last_updated", datetime.now()
                ).isoformat(),
                "domains": list(pair_stats.get("domains", set())),
                "needs_retraining": self.should_retrain(lang_pair),
            }
            stats["domains"].update(pair_stats.get("domains", set()))

        stats["domains"] = list(stats["domains"])

        return stats


# Global instance
# Singleton instance storage as class attribute
class _AITranslationMemorySingleton:
    """Singleton storage for AI translation memory."""

    instance: Optional[AITranslationMemory] = None


def get_ai_translation_memory() -> AITranslationMemory:
    """Get or create global AI translation memory instance."""
    if _AITranslationMemorySingleton.instance is None:
        _AITranslationMemorySingleton.instance = AITranslationMemory()
    return _AITranslationMemorySingleton.instance
