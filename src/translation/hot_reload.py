"""Hot Reloading for Translation Resources.

This module provides hot reloading functionality for translation resources
during development, allowing real-time updates without application restart.
"""

import asyncio
import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Set

try:
    from watchdog.events import FileSystemEventHandler
    from watchdog.observers import Observer
except ImportError:
    Observer = None
    FileSystemEventHandler = object

from src.translation.lazy.translation_loader import LoadStrategy, lazy_loader
from src.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class FileChange:
    """Represents a file change event."""

    file_path: str
    change_type: str  # modified, created, deleted
    timestamp: datetime
    language: Optional[str] = None
    namespace: Optional[str] = None


class TranslationFileHandler(FileSystemEventHandler):
    """Handles file system events for translation files."""

    def __init__(self, callback: Callable[[FileChange], None]):
        """Initialize handler with callback."""
        self.callback = callback
        self.debounce_delay = 0.5  # seconds
        self.pending_changes: Dict[str, datetime] = {}

    def on_modified(self, event: Any) -> None:
        """Handle file modification events."""
        if event.is_directory:
            return

        file_path = Path(event.src_path)

        # Only process JSON files
        if file_path.suffix != ".json":
            return

        # Debounce rapid changes
        current_time = datetime.now()
        last_change = self.pending_changes.get(event.src_path)

        if (
            last_change
            and (current_time - last_change).total_seconds() < self.debounce_delay
        ):
            return

        self.pending_changes[event.src_path] = current_time

        # Extract language and namespace from path
        try:
            parts = file_path.parts
            if len(parts) >= 2:
                language = parts[-2]
                namespace = file_path.stem

                change = FileChange(
                    file_path=str(file_path),
                    change_type="modified",
                    timestamp=current_time,
                    language=language,
                    namespace=namespace,
                )

                self.callback(change)
        except (OSError, ValueError) as e:
            logger.error(f"Error processing file change: {e}")


class HotReloadManager:
    """Manages hot reloading of translation resources."""

    def __init__(
        self, translations_dir: str = "./public/locales", enabled: bool = True
    ):
        """Initialize hot reload manager."""
        self.translations_dir = Path(translations_dir)
        self.enabled = enabled
        self.observer: Optional[Observer] = None
        self.reload_callbacks: Set[Callable] = set()
        self.file_checksums: Dict[str, str] = {}
        self.reload_stats: Dict[str, Any] = {
            "total_reloads": 0,
            "successful_reloads": 0,
            "failed_reloads": 0,
            "last_reload": None,
        }

    def start(self) -> None:
        """Start watching for file changes."""
        if not self.enabled:
            logger.info("Hot reloading is disabled")
            return

        if not self.translations_dir.exists():
            logger.warning(f"Translations directory not found: {self.translations_dir}")
            return

        # Calculate initial checksums
        self._calculate_checksums()

        # Set up file watcher
        self.observer = Observer()
        handler = TranslationFileHandler(self._handle_file_change)

        self.observer.schedule(handler, str(self.translations_dir), recursive=True)

        self.observer.start()
        logger.info(f"Hot reloading started for: {self.translations_dir}")

    def stop(self) -> None:
        """Stop watching for file changes."""
        if self.observer and self.observer.is_alive():
            self.observer.stop()
            self.observer.join()
            logger.info("Hot reloading stopped")

    def _calculate_checksums(self) -> None:
        """Calculate checksums for all translation files."""
        for json_file in self.translations_dir.rglob("*.json"):
            try:
                with open(json_file, "rb") as f:
                    # MD5 is used here only for file checksum, not for security
                    checksum = hashlib.md5(f.read(), usedforsecurity=False).hexdigest()
                self.file_checksums[str(json_file)] = checksum
            except OSError as e:
                logger.error(f"Error calculating checksum for {json_file}: {e}")

    def _handle_file_change(self, change: FileChange) -> None:
        """Handle file change event."""
        asyncio.create_task(self._reload_translation(change))

    async def _reload_translation(self, change: FileChange) -> None:
        """Reload a specific translation file."""
        logger.info(f"Reloading translation: {change.language}:{change.namespace}")

        self.reload_stats["total_reloads"] += 1

        try:
            # Verify file actually changed
            if not self._verify_change(change.file_path):
                logger.debug(f"File content unchanged: {change.file_path}")
                return

            # Check if language and namespace are not None
            if change.language is None or change.namespace is None:
                logger.error("Language or namespace is None, cannot reload")
                self.reload_stats["failed_reloads"] += 1
                return

            # Reload through lazy loader
            await lazy_loader.refresh_resource(change.language, change.namespace)

            # Reload the resource
            result = await lazy_loader.load_translations(
                change.language, change.namespace, strategy=LoadStrategy.EAGER
            )

            if result:
                self.reload_stats["successful_reloads"] += 1
                self.reload_stats["last_reload"] = datetime.now()

                # Notify callbacks
                await self._notify_callbacks(change)

                logger.info(
                    f"Successfully reloaded: {change.language}:{change.namespace}"
                )
            else:
                self.reload_stats["failed_reloads"] += 1
                logger.error(f"Failed to reload: {change.language}:{change.namespace}")

        except (FileNotFoundError, json.JSONDecodeError, ValueError) as e:
            self.reload_stats["failed_reloads"] += 1
            logger.error(f"Error reloading translation: {e}")

    def _verify_change(self, file_path: str) -> bool:
        """Verify file content actually changed."""
        try:
            with open(file_path, "rb") as f:
                # MD5 is used here only for file checksum, not for security
                new_checksum = hashlib.md5(f.read(), usedforsecurity=False).hexdigest()

            old_checksum = self.file_checksums.get(file_path)

            if new_checksum != old_checksum:
                self.file_checksums[file_path] = new_checksum
                return True

            return False

        except OSError as e:
            logger.error(f"Error verifying file change: {e}")
            return False

    async def _notify_callbacks(self, change: FileChange) -> None:
        """Notify registered callbacks of reload."""
        for callback in self.reload_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(change)
                else:
                    callback(change)
            except (TypeError, AttributeError, RuntimeError) as e:
                logger.error(f"Error in reload callback: {e}")

    def register_callback(self, callback: Callable) -> None:
        """Register a callback for reload events."""
        self.reload_callbacks.add(callback)
        logger.debug(f"Registered reload callback: {callback.__name__}")

    def unregister_callback(self, callback: Callable) -> None:
        """Unregister a reload callback."""
        self.reload_callbacks.discard(callback)

    def get_stats(self) -> Dict[str, Any]:
        """Get hot reload statistics."""
        return {
            **self.reload_stats,
            "enabled": self.enabled,
            "watching": self.observer.is_alive() if self.observer else False,
            "registered_callbacks": len(self.reload_callbacks),
        }

    async def reload_all_languages(self, languages: Optional[Set[str]] = None) -> None:
        """Force reload all or specific languages."""
        if languages is None:
            languages = set()
            for path in self.translations_dir.iterdir():
                if path.is_dir():
                    languages.add(path.name)

        reload_tasks = []
        for language in languages:
            lang_dir = self.translations_dir / language
            if lang_dir.exists():
                for json_file in lang_dir.glob("*.json"):
                    change = FileChange(
                        file_path=str(json_file),
                        change_type="manual_reload",
                        timestamp=datetime.now(),
                        language=language,
                        namespace=json_file.stem,
                    )
                    reload_tasks.append(self._reload_translation(change))

        if reload_tasks:
            await asyncio.gather(*reload_tasks, return_exceptions=True)


# Global hot reload manager
class _HotReloadSingleton:
    """Singleton holder for HotReloadManager."""

    _instance = HotReloadManager(enabled=True)  # Enable by default in development

    @classmethod
    def get_instance(cls) -> HotReloadManager:
        """Get the singleton instance."""
        return cls._instance

    @classmethod
    def set_instance(cls, instance: HotReloadManager) -> None:
        """Set the singleton instance."""
        cls._instance = instance


def configure_hot_reload(
    enabled: bool = True, translations_dir: Optional[str] = None
) -> HotReloadManager:
    """Configure and return hot reload manager."""
    if translations_dir:
        _HotReloadSingleton.set_instance(HotReloadManager(translations_dir, enabled))
    else:
        _HotReloadSingleton.get_instance().enabled = enabled

    instance = _HotReloadSingleton.get_instance()
    if enabled:
        instance.start()
    else:
        instance.stop()

    return instance
