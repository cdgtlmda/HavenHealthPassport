"""Translation Version Control.

This module provides version control capabilities for translation files,
tracking changes, managing versions, and enabling rollbacks.
"""

import gzip
import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class TranslationChange:
    """Represents a change to a translation."""

    key: str
    old_value: Optional[str]
    new_value: Optional[str]
    change_type: str  # 'added', 'modified', 'deleted'
    timestamp: datetime = field(default_factory=datetime.now)
    author: Optional[str] = None
    comment: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        data = asdict(self)
        data["timestamp"] = self.timestamp.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TranslationChange":
        """Create from dictionary."""
        data["timestamp"] = datetime.fromisoformat(data["timestamp"])
        return cls(**data)


@dataclass
class TranslationVersion:
    """Represents a version of translations."""

    version_id: str
    timestamp: datetime
    author: str
    comment: str
    language: str
    namespace: str
    changes: List[TranslationChange]
    parent_version: Optional[str] = None
    checksum: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "version_id": self.version_id,
            "timestamp": self.timestamp.isoformat(),
            "author": self.author,
            "comment": self.comment,
            "language": self.language,
            "namespace": self.namespace,
            "changes": [c.to_dict() for c in self.changes],
            "parent_version": self.parent_version,
            "checksum": self.checksum,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TranslationVersion":
        """Create from dictionary."""
        data["timestamp"] = datetime.fromisoformat(data["timestamp"])
        data["changes"] = [TranslationChange.from_dict(c) for c in data["changes"]]
        return cls(**data)


class TranslationVersionControl:
    """Manages version control for translation files."""

    def __init__(self, repository_path: str):
        """Initialize version control with repository path."""
        self.repository_path = Path(repository_path)
        self.versions_dir = self.repository_path / ".translation_versions"
        self.versions_dir.mkdir(parents=True, exist_ok=True)

        # Version index file
        self.index_file = self.versions_dir / "index.json"
        self.index = self._load_index()

    def _load_index(self) -> Dict[str, Any]:
        """Load version index."""
        if self.index_file.exists():
            with open(self.index_file, "r", encoding="utf-8") as f:
                data: Dict[str, Any] = json.load(f)
                return data
        return {"versions": {}, "latest": {}, "branches": {"main": {}}}

    def _save_index(self) -> None:
        """Save version index."""
        with open(self.index_file, "w", encoding="utf-8") as f:
            json.dump(self.index, f, indent=2)

    def _generate_version_id(self) -> str:
        """Generate unique version ID."""
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        # MD5 is used here only for generating unique identifiers, not for security
        random_part = hashlib.md5(
            f"{timestamp}{len(self.index['versions'])}".encode(), usedforsecurity=False
        ).hexdigest()[:8]
        return f"v_{timestamp}_{random_part}"

    def _calculate_checksum(self, content: Dict[str, Any]) -> str:
        """Calculate checksum for content."""
        json_str = json.dumps(content, sort_keys=True)
        return hashlib.sha256(json_str.encode()).hexdigest()

    def _flatten_translations(
        self, obj: Dict[str, Any], prefix: str = ""
    ) -> Dict[str, str]:
        """Flatten nested translation structure."""
        flat = {}

        for key, value in obj.items():
            new_key = f"{prefix}.{key}" if prefix else key

            if isinstance(value, dict):
                flat.update(self._flatten_translations(value, new_key))
            else:
                flat[new_key] = str(value)

        return flat

    def _detect_changes(
        self, old_content: Dict[str, Any], new_content: Dict[str, Any]
    ) -> List[TranslationChange]:
        """Detect changes between two translation contents."""
        changes = []

        # Flatten nested structures for comparison
        old_flat = self._flatten_translations(old_content)
        new_flat = self._flatten_translations(new_content)

        # Find additions and modifications
        for key, new_value in new_flat.items():
            if key not in old_flat:
                changes.append(
                    TranslationChange(
                        key=key,
                        old_value=None,
                        new_value=new_value,
                        change_type="added",
                    )
                )
            elif old_flat[key] != new_value:
                changes.append(
                    TranslationChange(
                        key=key,
                        old_value=old_flat[key],
                        new_value=new_value,
                        change_type="modified",
                    )
                )

        # Find deletions
        for key, old_value in old_flat.items():
            if key not in new_flat:
                changes.append(
                    TranslationChange(
                        key=key,
                        old_value=old_value,
                        new_value=None,
                        change_type="deleted",
                    )
                )

        return changes

    def _save_version_content(self, version_id: str, content: Dict[str, Any]) -> None:
        """Save version content to compressed file."""
        version_file = self.versions_dir / f"{version_id}.json.gz"

        json_data = json.dumps(content, ensure_ascii=False, indent=2)

        with gzip.open(version_file, "wt", encoding="utf-8") as f:
            f.write(json_data)

    def _load_version_content(self, version_id: str) -> Dict[str, Any]:
        """Load version content from compressed file."""
        version_file = self.versions_dir / f"{version_id}.json.gz"

        if not version_file.exists():
            return {}

        with gzip.open(version_file, "rt", encoding="utf-8") as f:
            data: Dict[str, Any] = json.load(f)
            return data

    def _save_version_metadata(self, version: TranslationVersion) -> None:
        """Save version metadata."""
        metadata_file = self.versions_dir / f"{version.version_id}.meta.json"

        with open(metadata_file, "w", encoding="utf-8") as f:
            json.dump(version.to_dict(), f, indent=2)

    def _load_version_metadata(self, version_id: str) -> Optional[TranslationVersion]:
        """Load version metadata."""
        metadata_file = self.versions_dir / f"{version_id}.meta.json"

        if not metadata_file.exists():
            return None

        with open(metadata_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        return TranslationVersion.from_dict(data)

    def commit(
        self,
        language: str,
        namespace: str,
        content: Dict[str, Any],
        author: str,
        comment: str,
        branch: str = "main",
    ) -> Optional[TranslationVersion]:
        """Commit a new version of translations."""
        # Get current version for this language/namespace
        lang_ns_key = f"{language}_{namespace}"
        current_version_id = self.index["branches"][branch].get(lang_ns_key)

        # Load current content for comparison
        if current_version_id:
            current_content = self._load_version_content(current_version_id)
        else:
            current_content = {}

        # Detect changes
        changes = self._detect_changes(current_content, content)

        if not changes:
            logger.info(f"No changes detected for {language}/{namespace}")
            return None

        # Create new version
        version = TranslationVersion(
            version_id=self._generate_version_id(),
            timestamp=datetime.now(),
            author=author,
            comment=comment,
            language=language,
            namespace=namespace,
            changes=changes,
            parent_version=current_version_id,
            checksum=self._calculate_checksum(content),
        )

        # Save version content
        self._save_version_content(version.version_id, content)

        # Save version metadata
        self._save_version_metadata(version)

        # Update index
        self.index["versions"][version.version_id] = version.to_dict()
        self.index["branches"][branch][lang_ns_key] = version.version_id
        self.index["latest"][lang_ns_key] = version.version_id
        self._save_index()

        logger.info(
            f"Committed version {version.version_id} for {language}/{namespace} "
            f"with {len(changes)} changes"
        )

        return version

    def get_version(self, version_id: str) -> Optional[TranslationVersion]:
        """Get a specific version."""
        if version_id not in self.index["versions"]:
            return None

        return self._load_version_metadata(version_id)

    def get_latest(self, language: str, namespace: str) -> Optional[TranslationVersion]:
        """Get latest version for language/namespace."""
        lang_ns_key = f"{language}_{namespace}"
        version_id = self.index["latest"].get(lang_ns_key)

        if not version_id:
            return None

        return self.get_version(version_id)

    def get_history(
        self, language: str, namespace: str, limit: Optional[int] = None
    ) -> List[TranslationVersion]:
        """Get version history for language/namespace."""
        history: List[TranslationVersion] = []
        lang_ns_key = f"{language}_{namespace}"

        # Start from latest version
        version_id = self.index["latest"].get(lang_ns_key)

        while version_id and (limit is None or len(history) < limit):
            version = self.get_version(version_id)
            if not version:
                break

            history.append(version)
            version_id = version.parent_version

        return history

    def diff(self, version_id1: str, version_id2: str) -> List[TranslationChange]:
        """Get diff between two versions."""
        content1 = self._load_version_content(version_id1)
        content2 = self._load_version_content(version_id2)

        return self._detect_changes(content1, content2)

    def checkout(
        self,
        language: str,
        namespace: str,
        version_id: Optional[str] = None,
        branch: str = "main",
    ) -> Dict[str, Any]:
        """Checkout a specific version or latest."""
        if version_id:
            return self._load_version_content(version_id)

        # Get latest from branch
        lang_ns_key = f"{language}_{namespace}"
        latest_version_id = self.index["branches"][branch].get(lang_ns_key)

        if not latest_version_id:
            return {}

        return self._load_version_content(latest_version_id)

    def create_branch(self, name: str, from_branch: str = "main") -> None:
        """Create a new branch."""
        if name in self.index["branches"]:
            raise ValueError(f"Branch '{name}' already exists")

        # Copy branch state
        self.index["branches"][name] = self.index["branches"][from_branch].copy()
        self._save_index()

        logger.info(f"Created branch '{name}' from '{from_branch}'")

    def get_stats(self) -> Dict[str, Any]:
        """Get repository statistics."""
        total_versions = len(self.index["versions"])

        # Count by language/namespace
        by_lang_ns: Dict[str, int] = {}
        for version_data in self.index["versions"].values():
            lang_ns = f"{version_data['language']}/{version_data['namespace']}"
            by_lang_ns[lang_ns] = by_lang_ns.get(lang_ns, 0) + 1

        return {
            "total_versions": total_versions,
            "total_branches": len(self.index["branches"]),
            "by_language_namespace": by_lang_ns,
            "repository_size": sum(
                f.stat().st_size for f in self.versions_dir.iterdir()
            ),
        }
