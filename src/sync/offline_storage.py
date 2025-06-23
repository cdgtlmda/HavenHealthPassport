"""Offline storage implementation for sync service."""

import json
import os
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.utils.encryption import EncryptionService
from src.utils.logging import get_logger

logger = get_logger(__name__)


class OfflineStorage:
    """SQLite-based offline storage for mobile/desktop apps."""

    def __init__(self, storage_path: Optional[str] = None):
        """Initialize offline storage.

        Args:
            storage_path: Path to storage directory
        """
        if storage_path:
            self.storage_path = Path(storage_path)
        else:
            # Default to user's app data directory
            self.storage_path = Path.home() / ".haven_health" / "offline"

        self.storage_path.mkdir(parents=True, exist_ok=True)
        self.db_path = self.storage_path / "offline_data.db"

        # Initialize database
        self._init_database()

    def _init_database(self) -> None:
        """Initialize SQLite database schema."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        # Create tables
        cursor.executescript(
            """
            CREATE TABLE IF NOT EXISTS offline_records (
                id TEXT PRIMARY KEY,
                record_type TEXT NOT NULL,
                record_id TEXT NOT NULL,
                data TEXT NOT NULL,
                encrypted INTEGER DEFAULT 1,
                version INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                synced_at TIMESTAMP,
                sync_status TEXT DEFAULT 'pending',
                UNIQUE(record_type, record_id)
            );

            CREATE INDEX IF NOT EXISTS idx_record_type ON offline_records(record_type);
            CREATE INDEX IF NOT EXISTS idx_sync_status ON offline_records(sync_status);
            CREATE INDEX IF NOT EXISTS idx_updated_at ON offline_records(updated_at);
        """
        )

        cursor.executescript(
            """
            CREATE TABLE IF NOT EXISTS sync_metadata (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                device_id TEXT NOT NULL,
                last_sync_timestamp TIMESTAMP,
                sync_token TEXT,
                sync_status TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS conflict_records (
                id TEXT PRIMARY KEY,
                record_type TEXT NOT NULL,
                record_id TEXT NOT NULL,
                local_data TEXT NOT NULL,
                server_data TEXT NOT NULL,
                conflict_type TEXT,
                resolved INTEGER DEFAULT 0,
                resolution_strategy TEXT,
                resolved_data TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                resolved_at TIMESTAMP
            );
        """
        )

        conn.commit()
        conn.close()

    def store_record(
        self,
        record_type: str,
        record_id: str,
        data: Dict[str, Any],
        encrypt: bool = True,
    ) -> bool:
        """Store a record offline.

        Args:
            record_type: Type of record
            record_id: Record ID
            data: Record data
            encrypt: Whether to encrypt the data

        Returns:
            True if stored successfully
        """
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()

            # Serialize data
            data_str = json.dumps(data)

            # Encrypt if requested
            if encrypt:
                encryption_service = EncryptionService()
                encrypted_data = encryption_service.encrypt(data_str)
                data_str = encrypted_data  # Already a string

            # Store or update record
            cursor.execute(
                """
                INSERT OR REPLACE INTO offline_records
                (id, record_type, record_id, data, encrypted, version, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    f"{record_type}:{record_id}",
                    record_type,
                    record_id,
                    data_str,
                    1 if encrypt else 0,
                    data.get("version", 1),
                    datetime.utcnow(),
                ),
            )

            conn.commit()
            conn.close()

            return True

        except (sqlite3.Error, ValueError, OSError) as e:
            logger.error("Failed to store offline record: %s", str(e), exc_info=True)
            return False

    def retrieve_record(
        self,
        record_type: str,
        record_id: str,
    ) -> Optional[Dict[str, Any]]:
        """Retrieve a record from offline storage.

        Args:
            record_type: Type of record
            record_id: Record ID

        Returns:
            Record data or None
        """
        try:
            conn = sqlite3.connect(str(self.db_path))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT data, encrypted
                FROM offline_records
                WHERE record_type = ? AND record_id = ?
            """,
                (record_type, record_id),
            )

            row = cursor.fetchone()
            conn.close()

            if not row:
                return None

            # Decrypt if necessary
            data_str = row["data"]
            if row["encrypted"]:
                try:
                    data_bytes = bytes.fromhex(data_str)
                    encryption_service = EncryptionService()
                    data_str = encryption_service.decrypt(
                        data_bytes.decode()
                    )  # decrypt expects string
                except (ValueError, OSError) as e:
                    logger.error("Failed to decrypt record: %s", str(e), exc_info=True)
                    return None

            # Parse JSON
            return json.loads(data_str)  # type: ignore[no-any-return]

        except (sqlite3.Error, json.JSONDecodeError, ValueError) as e:
            logger.error("Failed to retrieve offline record: %s", str(e), exc_info=True)
            return None

    def query_records(
        self,
        record_type: Optional[str] = None,
        sync_status: Optional[str] = None,
        updated_after: Optional[datetime] = None,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Query offline records.

        Args:
            record_type: Filter by record type
            sync_status: Filter by sync status
            updated_after: Filter by update timestamp
            limit: Maximum records to return

        Returns:
            List of records
        """
        try:
            conn = sqlite3.connect(str(self.db_path))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Build query
            query = "SELECT * FROM offline_records WHERE 1=1"
            params = []

            if record_type:
                query += " AND record_type = ?"
                params.append(record_type)

            if sync_status:
                query += " AND sync_status = ?"
                params.append(sync_status)

            if updated_after:
                query += " AND updated_at > ?"
                params.append(str(updated_after))

            query += " ORDER BY updated_at DESC"

            if limit:
                query += f" LIMIT {limit}"

            cursor.execute(query, params)
            rows = cursor.fetchall()
            conn.close()

            # Process records
            records = []
            for row in rows:
                data_str = row["data"]

                # Decrypt if necessary
                if row["encrypted"]:
                    try:
                        data_bytes = bytes.fromhex(data_str)
                        encryption_service = EncryptionService()
                        data_str = encryption_service.decrypt(
                            data_bytes.decode()
                        )  # decrypt expects string
                    except (ValueError, OSError) as e:
                        logger.error(
                            "Failed to decrypt record: %s", str(e), exc_info=True
                        )
                        continue

                # Parse and add metadata
                try:
                    data = json.loads(data_str)
                    data["_offline_metadata"] = {
                        "id": row["id"],
                        "version": row["version"],
                        "sync_status": row["sync_status"],
                        "synced_at": row["synced_at"],
                        "updated_at": row["updated_at"],
                    }
                    records.append(data)
                except (json.JSONDecodeError, KeyError, ValueError) as e:
                    logger.error("Failed to parse record: %s", str(e), exc_info=True)

            return records

        except (sqlite3.Error, ValueError) as e:
            logger.error("Failed to query offline records: %s", str(e), exc_info=True)
            return []

    def store_conflict(
        self,
        record_type: str,
        record_id: str,
        local_data: Dict[str, Any],
        server_data: Dict[str, Any],
        conflict_type: str = "version_mismatch",
    ) -> str:
        """Store a conflict for later resolution.

        Args:
            record_type: Type of record
            record_id: Record ID
            local_data: Local version of data
            server_data: Server version of data
            conflict_type: Type of conflict

        Returns:
            Conflict ID
        """
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()

            conflict_id = f"conflict_{record_type}_{record_id}_{int(datetime.utcnow().timestamp())}"

            cursor.execute(
                """
                INSERT INTO conflict_records
                (id, record_type, record_id, local_data, server_data, conflict_type)
                VALUES (?, ?, ?, ?, ?, ?)
            """,
                (
                    conflict_id,
                    record_type,
                    record_id,
                    json.dumps(local_data),
                    json.dumps(server_data),
                    conflict_type,
                ),
            )

            conn.commit()
            conn.close()

            return conflict_id

        except (sqlite3.Error, ValueError) as e:
            logger.error("Failed to store conflict: %s", str(e), exc_info=True)
            return ""

    def resolve_conflict(
        self,
        conflict_id: str,
        resolution_strategy: str,
        resolved_data: Dict[str, Any],
    ) -> bool:
        """Resolve a stored conflict.

        Args:
            conflict_id: Conflict ID
            resolution_strategy: Strategy used to resolve
            resolved_data: Resolved data

        Returns:
            True if resolved successfully
        """
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()

            cursor.execute(
                """
                UPDATE conflict_records
                SET resolved = 1,
                    resolution_strategy = ?,
                    resolved_data = ?,
                    resolved_at = ?
                WHERE id = ?
            """,
                (
                    resolution_strategy,
                    json.dumps(resolved_data),
                    datetime.utcnow(),
                    conflict_id,
                ),
            )

            conn.commit()
            conn.close()

            return True

        except (sqlite3.Error, ValueError) as e:
            logger.error("Failed to resolve conflict: %s", str(e), exc_info=True)
            return False

    def get_storage_info(self) -> Dict[str, Any]:
        """Get offline storage information.

        Returns:
            Storage statistics
        """
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()

            info: Dict[str, Any] = {
                "db_size": os.path.getsize(self.db_path),
                "record_counts": {},
                "sync_status_counts": {},
                "unresolved_conflicts": 0,
                "last_sync": None,
            }

            # Count records by type
            cursor.execute(
                """
                SELECT record_type, COUNT(*) as count
                FROM offline_records
                GROUP BY record_type
            """
            )

            for row in cursor.fetchall():
                info["record_counts"][row[0]] = row[1]

            # Count by sync status
            cursor.execute(
                """
                SELECT sync_status, COUNT(*) as count
                FROM offline_records
                GROUP BY sync_status
            """
            )

            for row in cursor.fetchall():
                info["sync_status_counts"][row[0]] = row[1]

            # Count unresolved conflicts
            cursor.execute(
                """
                SELECT COUNT(*) FROM conflict_records WHERE resolved = 0
            """
            )
            info["unresolved_conflicts"] = cursor.fetchone()[0]

            # Get last sync time
            cursor.execute(
                """
                SELECT MAX(synced_at) FROM offline_records WHERE synced_at IS NOT NULL
            """
            )
            last_sync = cursor.fetchone()[0]
            if last_sync:
                info["last_sync"] = last_sync

            conn.close()

            return info

        except (sqlite3.Error, OSError) as e:
            logger.error("Failed to get storage info: %s", str(e), exc_info=True)
            return {}

    def clear_synced_records(self, older_than_days: int = 7) -> int:
        """Clear synced records older than specified days.

        Args:
            older_than_days: Clear records synced more than this many days ago

        Returns:
            Number of records cleared
        """
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()

            cutoff_date = datetime.utcnow() - timedelta(days=older_than_days)

            cursor.execute(
                """
                DELETE FROM offline_records
                WHERE sync_status = 'completed'
                AND synced_at < ?
            """,
                (cutoff_date,),
            )

            count = cursor.rowcount

            conn.commit()
            conn.close()

            return count

        except (sqlite3.Error, ValueError) as e:
            logger.error("Failed to clear synced records: %s", str(e), exc_info=True)
            return 0
