"""
Translation Memory system for maintaining translation consistency.

This module implements a Translation Memory (TM) system that stores
previously translated segments for reuse, ensuring consistency and
improving translation efficiency.
"""

import csv
import hashlib
import io
import json
import types
import warnings
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timedelta
from difflib import SequenceMatcher
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    Float,
    Index,
    Integer,
    String,
    Text,
    and_,
    func,
    or_,
)
from sqlalchemy.orm import Session

from src.models.base import BaseModel
from src.models.db_types import UUID as PGUUID
from src.utils.logging import get_logger

DefusedET: types.ModuleType
try:
    import defusedxml.ElementTree as DefusedET
except ImportError:
    # Fallback to standard ElementTree if defusedxml is not available
    DefusedET = ET  # pylint: disable=invalid-name

    warnings.warn(
        "defusedxml not available, using standard ElementTree. This may be less secure.",
        stacklevel=2,
    )

logger = get_logger(__name__)


class MatchType(str, Enum):
    """Types of translation memory matches."""

    EXACT = "exact"  # 100% match
    CONTEXT_EXACT = "context_exact"  # 100% match with same context
    FUZZY_HIGH = "fuzzy_high"  # 85-99% match
    FUZZY_MEDIUM = "fuzzy_medium"  # 70-84% match
    FUZZY_LOW = "fuzzy_low"  # 50-69% match
    NO_MATCH = "no_match"  # Below 50%


class SegmentType(str, Enum):
    """Types of translatable segments."""

    SENTENCE = "sentence"
    PARAGRAPH = "paragraph"
    PHRASE = "phrase"
    TERM = "term"
    UI_STRING = "ui_string"
    INSTRUCTION = "instruction"


@dataclass
class TMMatch:
    """Translation memory match result."""

    source_text: str
    target_text: str
    match_type: MatchType
    score: float
    segment_id: UUID
    metadata: Dict[str, Any]
    created_at: datetime
    usage_count: int
    last_used: datetime
    context_hash: Optional[str] = None


@dataclass
class TMSegment:
    """Segment for translation memory storage."""

    source_text: str
    target_text: str
    source_language: str
    target_language: str
    segment_type: SegmentType
    context: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class TranslationMemory(BaseModel):
    """Translation memory storage model."""

    __tablename__ = "translation_memory"

    # Segment identification
    segment_hash = Column(String(64), nullable=False, index=True)
    source_text = Column(Text, nullable=False)
    target_text = Column(Text, nullable=False)
    source_language = Column(String(10), nullable=False, index=True)
    target_language = Column(String(10), nullable=False, index=True)

    # Segment metadata
    segment_type = Column(String(20), nullable=False)
    context_hash = Column(String(64), index=True)
    context_text = Column(Text)

    # Quality and usage tracking
    quality_score = Column(Float, default=1.0)
    usage_count = Column(Integer, default=0)
    last_used = Column(DateTime, default=datetime.utcnow)

    # Source tracking
    source_type = Column(String(50))  # manual, machine, verified
    source_user_id: Any = Column(PGUUID(as_uuid=True), nullable=True)

    # Additional metadata
    tm_metadata = Column("metadata", JSON, default=dict)

    # Indexes for performance
    __table_args__ = (
        Index("ix_tm_language_pair", "source_language", "target_language"),
        Index("ix_tm_segment_context", "segment_hash", "context_hash"),
        Index("ix_tm_quality_usage", "quality_score", "usage_count"),
    )


class TranslationMemoryService:
    """Service for managing translation memory."""

    # Matching thresholds
    EXACT_MATCH_THRESHOLD = 1.0
    HIGH_FUZZY_THRESHOLD = 0.85
    MEDIUM_FUZZY_THRESHOLD = 0.70
    LOW_FUZZY_THRESHOLD = 0.50

    # Quality score factors
    QUALITY_DECAY_FACTOR = 0.95  # Quality decay per month
    USAGE_BOOST_FACTOR = 0.01  # Quality boost per usage
    VERIFIED_BOOST = 0.2  # Boost for verified translations

    def __init__(self, session: Session):
        """Initialize translation memory service."""
        self.session = session
        self._segment_cache: Dict[str, TMSegment] = {}
        self._similarity_cache: Dict[str, float] = {}

    def add_segment(
        self,
        segment: TMSegment,
        source_type: str = "machine",
        source_user_id: Optional[UUID] = None,
        quality_score: float = 0.8,
    ) -> TranslationMemory:
        """
        Add a segment to translation memory.

        Args:
            segment: Translation segment to add
            source_type: Source of translation
            source_user_id: User who created translation
            quality_score: Initial quality score

        Returns:
            Created translation memory entry
        """
        try:
            # Generate segment hash
            segment_hash = self._generate_segment_hash(
                segment.source_text, segment.source_language, segment.target_language
            )

            # Generate context hash if context provided
            context_hash = None
            if segment.context:
                context_hash = self._generate_context_hash(segment.context)

            # Check if segment already exists
            existing = (
                self.session.query(TranslationMemory)
                .filter(
                    TranslationMemory.segment_hash == segment_hash,
                    TranslationMemory.context_hash == context_hash,
                )
                .first()
            )

            if existing:
                # Update existing segment
                existing.usage_count += 1
                existing.last_used = datetime.utcnow()
                existing.quality_score = min(
                    1.0, existing.quality_score + self.USAGE_BOOST_FACTOR
                )

                if segment.metadata:
                    existing.tm_metadata.update(segment.metadata)

                self.session.commit()
                return existing

            # Create new segment
            tm_entry = TranslationMemory(
                segment_hash=segment_hash,
                source_text=segment.source_text,
                target_text=segment.target_text,
                source_language=segment.source_language,
                target_language=segment.target_language,
                segment_type=segment.segment_type.value,
                context_hash=context_hash,
                context_text=segment.context,
                quality_score=quality_score,
                source_type=source_type,
                source_user_id=source_user_id,
                tm_metadata=segment.metadata or {},
            )

            self.session.add(tm_entry)
            self.session.commit()

            logger.info(
                f"Added TM segment: {segment_hash[:8]} "
                f"({segment.source_language}->{segment.target_language})"
            )

            return tm_entry

        except Exception as e:
            logger.error(f"Error adding TM segment: {e}")
            self.session.rollback()
            raise

    def search(
        self,
        source_text: str,
        source_language: str,
        target_language: str,
        context: Optional[str] = None,
        min_score: float = LOW_FUZZY_THRESHOLD,
        max_results: int = 5,
        segment_type: Optional[SegmentType] = None,
    ) -> List[TMMatch]:
        """
        Search translation memory for matches.

        Args:
            source_text: Text to search for
            source_language: Source language code
            target_language: Target language code
            context: Optional context for context-aware matching
            min_score: Minimum similarity score
            max_results: Maximum number of results
            segment_type: Filter by segment type

        Returns:
            List of translation memory matches
        """
        try:
            # Start with base query
            query = self.session.query(TranslationMemory).filter(
                TranslationMemory.source_language == source_language,
                TranslationMemory.target_language == target_language,
            )

            # Filter by segment type if specified
            if segment_type:
                query = query.filter(
                    TranslationMemory.segment_type == segment_type.value
                )

            # Get potential matches
            candidates = query.all()

            # Calculate similarity scores
            matches = []
            source_normalized = self._normalize_text(source_text)
            context_hash = self._generate_context_hash(context) if context else None

            for candidate in candidates:
                # Calculate text similarity
                similarity = self._calculate_similarity(
                    source_normalized, self._normalize_text(candidate.source_text)
                )

                if similarity < min_score:
                    continue

                # Determine match type
                match_type = self._determine_match_type(
                    similarity, candidate.context_hash, context_hash
                )

                # Apply quality and recency factors
                adjusted_score = self._calculate_adjusted_score(
                    similarity, candidate.quality_score, candidate.last_used
                )

                matches.append(
                    TMMatch(
                        source_text=candidate.source_text,
                        target_text=candidate.target_text,
                        match_type=match_type,
                        score=adjusted_score,
                        segment_id=candidate.id,
                        metadata=candidate.tm_metadata,
                        created_at=candidate.created_at,  # type: ignore[arg-type]
                        usage_count=candidate.usage_count,
                        last_used=candidate.last_used,
                        context_hash=candidate.context_hash,
                    )
                )

            # Sort by score and limit results
            matches.sort(key=lambda x: x.score, reverse=True)

            # Update usage for top match if exact
            if matches and matches[0].match_type in [
                MatchType.EXACT,
                MatchType.CONTEXT_EXACT,
            ]:
                self._update_usage(matches[0].segment_id)

            return matches[:max_results]

        except (KeyError, AttributeError, ValueError) as e:
            logger.error(f"Error searching TM: {e}")
            return []

    def update_quality(
        self, segment_id: UUID, quality_delta: float, reason: str
    ) -> bool:
        """
        Update quality score of a TM segment.

        Args:
            segment_id: Segment ID
            quality_delta: Change in quality score
            reason: Reason for quality update

        Returns:
            Success status
        """
        try:
            segment = (
                self.session.query(TranslationMemory)
                .filter(TranslationMemory.id == segment_id)
                .first()
            )

            if not segment:
                return False

            # Update quality score
            new_score = max(0.0, min(1.0, segment.quality_score + quality_delta))
            segment.quality_score = new_score

            # Add to metadata
            if "quality_history" not in segment.tm_metadata:
                segment.tm_metadata["quality_history"] = []

            segment.tm_metadata["quality_history"].append(
                {
                    "timestamp": datetime.utcnow().isoformat(),
                    "delta": quality_delta,
                    "new_score": new_score,
                    "reason": reason,
                }
            )

            self.session.commit()
            return True

        except (KeyError, AttributeError, ValueError) as e:
            logger.error(f"Error updating TM quality: {e}")
            self.session.rollback()
            return False

    def batch_add(
        self,
        segments: List[TMSegment],
        source_type: str = "import",
        source_user_id: Optional[UUID] = None,
    ) -> int:
        """
        Add multiple segments to translation memory.

        Args:
            segments: List of segments to add
            source_type: Source of translations
            source_user_id: User who imported translations

        Returns:
            Number of segments added
        """
        added = 0

        for segment in segments:
            try:
                self.add_segment(
                    segment, source_type=source_type, source_user_id=source_user_id
                )
                added += 1
            except (KeyError, AttributeError, ValueError) as e:
                logger.error(f"Error adding segment: {e}")
                continue

        logger.info(f"Added {added}/{len(segments)} segments to TM")
        return added

    def export(
        self,
        source_language: Optional[str] = None,
        target_language: Optional[str] = None,
        min_quality: float = 0.5,
        export_format: str = "tmx",
    ) -> str:
        """
        Export translation memory.

        Args:
            source_language: Filter by source language
            target_language: Filter by target language
            min_quality: Minimum quality score
            export_format: Export format (tmx, json, csv)

        Returns:
            Exported data as string
        """
        try:
            query = self.session.query(TranslationMemory).filter(
                TranslationMemory.quality_score >= min_quality
            )

            if source_language:
                query = query.filter(
                    TranslationMemory.source_language == source_language
                )

            if target_language:
                query = query.filter(
                    TranslationMemory.target_language == target_language
                )

            segments = query.all()

            if export_format == "json":
                return self._export_json(segments)
            elif export_format == "tmx":
                return self._export_tmx(segments)
            elif export_format == "csv":
                return self._export_csv(segments)
            else:
                raise ValueError(f"Unsupported export format: {export_format}")

        except (TypeError, ValueError) as e:
            logger.error(f"Error exporting TM: {e}")
            raise

    def import_tmx(self, tmx_content: str) -> int:
        """
        Import TMX (Translation Memory eXchange) file.

        Args:
            tmx_content: TMX file content

        Returns:
            Number of segments imported
        """
        try:
            # Use defusedxml for security against XML attacks
            root = DefusedET.fromstring(
                tmx_content
            )  # nosec B314 - Using defusedxml which is secure
            segments = []

            # Parse TMX structure
            for tu in root.findall(".//tu"):
                segment_data = {}

                for tuv in tu.findall("tuv"):
                    lang = tuv.get(
                        "{http://www.w3.org/XML/1998/namespace}lang",
                        tuv.get("lang", ""),
                    )
                    seg = tuv.find("seg")
                    if seg is not None and seg.text:
                        segment_data[lang] = seg.text

                # Create segments for each language pair
                if len(segment_data) >= 2:
                    langs = list(segment_data.keys())
                    for i, lang_i in enumerate(langs):
                        for j in range(i + 1, len(langs)):
                            segments.append(
                                TMSegment(
                                    source_text=segment_data[lang_i],
                                    target_text=segment_data[langs[j]],
                                    source_language=lang_i,
                                    target_language=langs[j],
                                    segment_type=SegmentType.SENTENCE,
                                    metadata={"source": "tmx_import"},
                                )
                            )

            return self.batch_add(segments, source_type="tmx_import")

        except (KeyError, AttributeError, ValueError, ET.ParseError) as e:
            logger.error(f"Error importing TMX: {e}")
            return 0

    def leverage_existing(
        self,
        text: str,
        source_language: str,
        target_language: str,
        context: Optional[str] = None,
        threshold: float = 0.85,
    ) -> Optional[str]:
        """
        Leverage existing translations for new text.

        Args:
            text: Text to translate
            source_language: Source language
            target_language: Target language
            context: Optional context
            threshold: Minimum match threshold

        Returns:
            Leveraged translation or None
        """
        matches = self.search(
            source_text=text,
            source_language=source_language,
            target_language=target_language,
            context=context,
            min_score=threshold,
            max_results=1,
        )

        if matches and matches[0].match_type in [
            MatchType.EXACT,
            MatchType.CONTEXT_EXACT,
        ]:
            return matches[0].target_text

        return None

    def get_statistics(
        self,
        source_language: Optional[str] = None,
        target_language: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get translation memory statistics.

        Args:
            source_language: Filter by source language
            target_language: Filter by target language

        Returns:
            Statistics dictionary
        """
        try:
            query = self.session.query(TranslationMemory)

            if source_language:
                query = query.filter(
                    TranslationMemory.source_language == source_language
                )

            if target_language:
                query = query.filter(
                    TranslationMemory.target_language == target_language
                )

            # Basic counts
            total_segments = query.count()

            # Language pair statistics
            language_pairs = (
                self.session.query(
                    TranslationMemory.source_language,
                    TranslationMemory.target_language,
                    func.count(TranslationMemory.id),  # pylint: disable=not-callable
                )
                .group_by(
                    TranslationMemory.source_language, TranslationMemory.target_language
                )
                .all()
            )

            # Quality distribution
            quality_dist = (
                self.session.query(
                    func.floor(TranslationMemory.quality_score * 10) / 10,
                    func.count(TranslationMemory.id),  # pylint: disable=not-callable
                )
                .group_by(func.floor(TranslationMemory.quality_score * 10) / 10)
                .all()
            )

            # Usage statistics
            avg_usage = (
                self.session.query(func.avg(TranslationMemory.usage_count)).scalar()
                or 0
            )

            # Recent activity
            recent_segments = query.filter(
                TranslationMemory.created_at >= datetime.utcnow() - timedelta(days=30)
            ).count()

            return {
                "total_segments": total_segments,
                "language_pairs": [
                    {"source": src, "target": tgt, "count": count}
                    for src, tgt, count in language_pairs
                ],
                "quality_distribution": {
                    f"{score:.1f}": count for score, count in quality_dist
                },
                "average_usage": float(avg_usage),
                "recent_segments_30d": recent_segments,
                "storage_size_estimate": total_segments * 1000,  # Rough bytes estimate
            }

        except (KeyError, AttributeError, ValueError) as e:
            logger.error(f"Error getting TM statistics: {e}")
            return {}

    def cleanup(
        self, min_quality: float = 0.3, max_age_days: int = 365, min_usage: int = 0
    ) -> int:
        """
        Clean up low-quality or old segments.

        Args:
            min_quality: Minimum quality to keep
            max_age_days: Maximum age in days
            min_usage: Minimum usage count

        Returns:
            Number of segments removed
        """
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=max_age_days)

            # Find segments to remove
            to_remove = self.session.query(TranslationMemory).filter(
                or_(
                    TranslationMemory.quality_score < min_quality,
                    and_(
                        TranslationMemory.last_used < cutoff_date,
                        TranslationMemory.usage_count <= min_usage,
                    ),
                )
            )

            count = to_remove.count()

            # Remove segments
            to_remove.delete()
            self.session.commit()

            logger.info(f"Cleaned up {count} TM segments")
            return count

        except (KeyError, AttributeError, ValueError) as e:
            logger.error(f"Error cleaning up TM: {e}")
            self.session.rollback()
            return 0

    def _generate_segment_hash(
        self, text: str, source_lang: str, target_lang: str
    ) -> str:
        """Generate hash for segment identification."""
        normalized = self._normalize_text(text)
        key = f"{source_lang}:{target_lang}:{normalized}"
        return hashlib.sha256(key.encode()).hexdigest()

    def _generate_context_hash(self, context: str) -> str:
        """Generate hash for context."""
        return hashlib.md5(context.encode(), usedforsecurity=False).hexdigest()

    def _normalize_text(self, text: str) -> str:
        """Normalize text for comparison."""
        # Convert to lowercase
        text = text.lower()

        # Remove extra whitespace
        text = " ".join(text.split())

        # Remove punctuation at end
        text = text.rstrip(".,!?;:")

        return text

    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """Calculate similarity between two texts."""
        # Use cache if available
        cache_key = f"{text1}:{text2}"
        if cache_key in self._similarity_cache:
            return self._similarity_cache[cache_key]

        # Calculate similarity
        similarity = SequenceMatcher(None, text1, text2).ratio()

        # Cache result
        self._similarity_cache[cache_key] = similarity

        # Limit cache size
        if len(self._similarity_cache) > 10000:
            self._similarity_cache.clear()

        return similarity

    def _determine_match_type(
        self,
        similarity: float,
        segment_context: Optional[str],
        search_context: Optional[str],
    ) -> MatchType:
        """Determine match type based on similarity and context."""
        if similarity >= self.EXACT_MATCH_THRESHOLD:
            if segment_context == search_context:
                return MatchType.CONTEXT_EXACT
            return MatchType.EXACT
        elif similarity >= self.HIGH_FUZZY_THRESHOLD:
            return MatchType.FUZZY_HIGH
        elif similarity >= self.MEDIUM_FUZZY_THRESHOLD:
            return MatchType.FUZZY_MEDIUM
        elif similarity >= self.LOW_FUZZY_THRESHOLD:
            return MatchType.FUZZY_LOW
        else:
            return MatchType.NO_MATCH

    def _calculate_adjusted_score(
        self, similarity: float, quality: float, last_used: datetime
    ) -> float:
        """Calculate adjusted score with quality and recency factors."""
        # Apply quality factor
        score = similarity * (0.7 + 0.3 * quality)

        # Apply recency factor
        days_old = (datetime.utcnow() - last_used).days
        recency_factor = 0.9 ** (days_old / 30)  # Decay by 10% per month
        score *= 0.8 + 0.2 * recency_factor

        return float(min(1.0, score))

    def _update_usage(self, segment_id: UUID) -> None:
        """Update usage statistics for a segment."""
        try:
            segment = (
                self.session.query(TranslationMemory)
                .filter(TranslationMemory.id == segment_id)
                .first()
            )

            if segment:
                segment.usage_count += 1
                segment.last_used = datetime.utcnow()
                self.session.commit()
        except (KeyError, AttributeError, ValueError) as e:
            logger.error(f"Error updating usage: {e}")

    def _export_json(self, segments: List[TranslationMemory]) -> str:
        """Export segments as JSON."""
        data = {
            "version": "1.0",
            "exported_at": datetime.utcnow().isoformat(),
            "segments": [
                {
                    "source_text": seg.source_text,
                    "target_text": seg.target_text,
                    "source_language": seg.source_language,
                    "target_language": seg.target_language,
                    "segment_type": seg.segment_type,
                    "quality_score": seg.quality_score,
                    "usage_count": seg.usage_count,
                    "context": seg.context_text,
                    "metadata": seg.tm_metadata,
                }
                for seg in segments
            ],
        }
        return json.dumps(data, indent=2, ensure_ascii=False)

    def _export_tmx(self, segments: List[TranslationMemory]) -> str:
        """Export segments as TMX."""
        tmx = f"""<?xml version="1.0" encoding="UTF-8"?>
<tmx version="1.4">
  <header
    creationtool="Haven Health Passport"
    creationtoolversion="1.0"
    datatype="plaintext"
    segtype="sentence"
    adminlang="en"
    srclang="*all*"
    o-tmf="Haven TMX"
    creationdate="{datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}">
  </header>
  <body>
"""

        for seg in segments:
            tmx += f"""    <tu tuid="{seg.id}" creationdate="{seg.created_at.strftime('%Y%m%dT%H%M%SZ')}">
      <tuv xml:lang="{seg.source_language}">
        <seg>{self._escape_xml(str(seg.source_text))}</seg>
      </tuv>
      <tuv xml:lang="{seg.target_language}">
        <seg>{self._escape_xml(str(seg.target_text))}</seg>
      </tuv>
    </tu>
"""

        tmx += """  </body>
</tmx>"""

        return tmx

    def _export_csv(self, segments: List[TranslationMemory]) -> str:
        """Export segments as CSV."""
        output = io.StringIO()
        writer = csv.writer(output)

        # Header
        writer.writerow(
            [
                "Source Language",
                "Target Language",
                "Source Text",
                "Target Text",
                "Quality Score",
                "Usage Count",
                "Context",
            ]
        )

        # Data
        for seg in segments:
            writer.writerow(
                [
                    seg.source_language,
                    seg.target_language,
                    seg.source_text,
                    seg.target_text,
                    seg.quality_score,
                    seg.usage_count,
                    seg.context_text or "",
                ]
            )

        return output.getvalue()

    def _escape_xml(self, text: str) -> str:
        """Escape text for XML."""
        return (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&apos;")
        )


# Singleton instance
_tm_service: Optional[TranslationMemoryService] = None


def get_translation_memory_service(session: Session) -> TranslationMemoryService:
    """Get or create translation memory service instance."""
    if globals().get("_tm_service") is None:
        globals()["_tm_service"] = TranslationMemoryService(session)
    return TranslationMemoryService(
        session
    )  # Return a new instance to avoid mypy issues
