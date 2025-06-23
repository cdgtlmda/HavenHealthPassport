"""Translation Memory.

This module implements translation memory functionality for
reusing previous translations and maintaining consistency.
"""

import hashlib
import json
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class TranslationUnit:
    """A unit in translation memory."""

    source_text: str
    target_text: str
    source_language: str
    target_language: str
    context: Optional[str] = None
    domain: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    usage_count: int = 0
    quality_score: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def get_fingerprint(self) -> str:
        """Get unique fingerprint for this translation unit."""
        content = f"{self.source_language}:{self.target_language}:{self.source_text}:{self.context or ''}"
        return hashlib.sha256(content.encode()).hexdigest()


@dataclass
class TranslationMatch:
    """A match found in translation memory."""

    unit: TranslationUnit
    score: float  # 0.0 to 1.0
    match_type: str  # 'exact', 'fuzzy', 'substring'


class TranslationMemory:
    """Translation memory for storing and retrieving translations."""

    def __init__(self, db_path: str):
        """Initialize translation memory with database path."""
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # Initialize database
        self._init_database()

    def _init_database(self) -> None:
        """Initialize SQLite database schema."""
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.cursor()

            # Create translations table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS translations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    fingerprint TEXT UNIQUE NOT NULL,
                    source_text TEXT NOT NULL,
                    target_text TEXT NOT NULL,
                    source_language TEXT NOT NULL,
                    target_language TEXT NOT NULL,
                    context TEXT,
                    domain TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    usage_count INTEGER DEFAULT 0,
                    quality_score REAL DEFAULT 1.0,
                    metadata TEXT
                )
            """
            )

            # Create indexes
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_source_text
                ON translations(source_text)
            """
            )
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_languages
                ON translations(source_language, target_language)
            """
            )
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_domain
                ON translations(domain)
            """
            )

            conn.commit()

    def add(self, unit: TranslationUnit) -> bool:
        """Add a translation unit to memory."""
        fingerprint = unit.get_fingerprint()

        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                cursor = conn.cursor()

                cursor.execute(
                    """
                    INSERT OR REPLACE INTO translations (
                        fingerprint, source_text, target_text,
                        source_language, target_language, context,
                        domain, created_at, updated_at, usage_count,
                        quality_score, metadata
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        fingerprint,
                        unit.source_text,
                        unit.target_text,
                        unit.source_language,
                        unit.target_language,
                        unit.context,
                        unit.domain,
                        unit.created_at.isoformat(),
                        unit.updated_at.isoformat(),
                        unit.usage_count,
                        unit.quality_score,
                        json.dumps(unit.metadata),
                    ),
                )

                conn.commit()
                return True

        except (sqlite3.Error, ValueError) as e:
            logger.error(f"Error adding to translation memory: {e}")
            return False

    def _row_to_unit(self, row: tuple) -> TranslationUnit:
        """Convert database row to TranslationUnit."""
        return TranslationUnit(
            source_text=row[2],
            target_text=row[3],
            source_language=row[4],
            target_language=row[5],
            context=row[6],
            domain=row[7],
            created_at=datetime.fromisoformat(row[8]),
            updated_at=datetime.fromisoformat(row[9]),
            usage_count=row[10],
            quality_score=row[11],
            metadata=json.loads(row[12]) if row[12] else {},
        )

    def search(
        self,
        source_text: str,
        source_language: str,
        target_language: str,
        min_score: float = 0.7,
        max_results: int = 10,
        domain: Optional[str] = None,
    ) -> List[TranslationMatch]:
        """Search for matching translations."""
        matches = []

        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.cursor()

            # Build query
            query = """
                SELECT * FROM translations
                WHERE source_language = ? AND target_language = ?
            """
            params = [source_language, target_language]

            if domain:
                query += " AND domain = ?"
                params.append(domain)

            cursor.execute(query, params)

            for row in cursor.fetchall():
                unit = self._row_to_unit(row)

                # Calculate similarity score
                score = self._calculate_similarity(source_text, unit.source_text)

                if score >= min_score:
                    match_type = self._determine_match_type(score)
                    matches.append(
                        TranslationMatch(unit=unit, score=score, match_type=match_type)
                    )

            # Sort by score and limit results
            matches.sort(key=lambda m: m.score, reverse=True)
            return matches[:max_results]

    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """Calculate similarity score between two texts."""
        # Exact match
        if text1 == text2:
            return 1.0

        # Normalize texts
        text1_norm = text1.lower().strip()
        text2_norm = text2.lower().strip()

        if text1_norm == text2_norm:
            return 0.95  # Case/whitespace differences

        # Use sequence matcher for fuzzy matching
        matcher = SequenceMatcher(None, text1_norm, text2_norm)
        return matcher.ratio()

    def _determine_match_type(self, score: float) -> str:
        """Determine match type based on score."""
        if score >= 1.0:
            return "exact"
        elif score >= 0.85:
            return "fuzzy"
        else:
            return "substring"

    def update_usage(self, fingerprint: str) -> None:
        """Update usage count for a translation."""
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE translations
                SET usage_count = usage_count + 1,
                    updated_at = ?
                WHERE fingerprint = ?
            """,
                (datetime.now().isoformat(), fingerprint),
            )
            conn.commit()

    def update_quality_score(self, fingerprint: str, score: float) -> None:
        """Update quality score for a translation."""
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE translations
                SET quality_score = ?,
                    updated_at = ?
                WHERE fingerprint = ?
            """,
                (score, datetime.now().isoformat(), fingerprint),
            )
            conn.commit()

    def import_tmx(self, _tmx_path: str) -> int:
        """Import translations from TMX file format."""
        # TMX import would be implemented here
        # For now, return 0 as placeholder
        logger.warning("TMX import not yet implemented")
        return 0

    def export_tmx(self, _output_path: str, **_filters: Any) -> int:
        """Export translations to TMX file format."""
        # TMX export would be implemented here
        # For now, return 0 as placeholder
        logger.warning("TMX export not yet implemented")
        return 0

    def get_stats(self) -> Dict[str, Any]:
        """Get translation memory statistics."""
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.cursor()

            # Total translations
            cursor.execute("SELECT COUNT(*) FROM translations")
            total = cursor.fetchone()[0]

            # By language pair
            cursor.execute(
                """
                SELECT source_language, target_language, COUNT(*)
                FROM translations
                GROUP BY source_language, target_language
            """
            )
            by_language_pair = {
                f"{row[0]}-{row[1]}": row[2] for row in cursor.fetchall()
            }

            # By domain
            cursor.execute(
                """
                SELECT domain, COUNT(*)
                FROM translations
                WHERE domain IS NOT NULL
                GROUP BY domain
            """
            )
            by_domain = {row[0]: row[1] for row in cursor.fetchall()}

            # Average quality score
            cursor.execute("SELECT AVG(quality_score) FROM translations")
            avg_quality = cursor.fetchone()[0] or 0

            return {
                "total_translations": total,
                "by_language_pair": by_language_pair,
                "by_domain": by_domain,
                "average_quality_score": avg_quality,
            }
