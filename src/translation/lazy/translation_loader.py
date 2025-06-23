"""Lazy Translation Loader.

This module provides lazy loading functionality for translation resources,
optimizing performance by loading language data on-demand.
"""

import asyncio
import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Optional, Set

from src.utils.logging import get_logger

logger = get_logger(__name__)


class LoadStrategy(str, Enum):
    """Translation loading strategies."""

    EAGER = "eager"  # Load immediately
    LAZY = "lazy"  # Load on first use
    PRELOAD = "preload"  # Load in background
    ON_DEMAND = "on_demand"  # Load only when requested


class ResourceType(str, Enum):
    """Types of translation resources."""

    COMMON = "common"  # Common UI strings
    MEDICAL = "medical"  # Medical terminology
    ERRORS = "errors"  # Error messages
    HELP = "help"  # Help content
    DOCUMENTS = "documents"  # Document templates
    VOICE = "voice"  # Voice prompts


@dataclass
class TranslationResource:
    """Translation resource metadata."""

    language: str
    namespace: str
    resource_type: ResourceType
    file_path: str
    size_bytes: int
    last_modified: datetime
    checksum: str
    is_loaded: bool = False
    load_count: int = 0
    last_accessed: Optional[datetime] = None


@dataclass
class LoadConfig:
    """Configuration for lazy loading."""

    preload_languages: Set[str]  # Languages to preload
    preload_namespaces: Set[str]  # Namespaces to preload
    cache_duration: timedelta
    max_memory_mb: int
    load_timeout_seconds: int
    parallel_loads: int


class LazyTranslationLoader:
    """Manages lazy loading of translation resources."""

    def __init__(
        self,
        translations_dir: str = "./public/locales",
    ):
        """Initialize lazy loader."""
        self.translations_dir = Path(translations_dir)
        self.cache: Dict[str, Any] = {}  # Simple in-memory cache
        self.resources: Dict[str, TranslationResource] = {}
        self.loaded_data: Dict[str, Dict[str, Any]] = {}
        self.load_config = self._get_default_config()
        self.loading_locks: Dict[str, asyncio.Lock] = {}
        self._initialize_resources()

    def _get_default_config(self) -> LoadConfig:
        """Get default loading configuration."""
        return LoadConfig(
            preload_languages={"en"},  # Always preload English
            preload_namespaces={"common", "errors"},  # Essential namespaces
            cache_duration=timedelta(hours=24),
            max_memory_mb=100,
            load_timeout_seconds=30,
            parallel_loads=3,
        )

    def _initialize_resources(self) -> None:
        """Scan and index all translation resources."""
        logger.info("Initializing translation resources")

        if not self.translations_dir.exists():
            logger.warning(f"Translations directory not found: {self.translations_dir}")
            return

        # Scan all language directories
        for lang_dir in self.translations_dir.iterdir():
            if not lang_dir.is_dir():
                continue

            language = lang_dir.name

            # Scan all namespace files
            for file_path in lang_dir.glob("*.json"):
                namespace = file_path.stem
                resource = self._create_resource(language, namespace, file_path)

                if resource:
                    resource_key = f"{language}:{namespace}"
                    self.resources[resource_key] = resource

        logger.info(f"Indexed {len(self.resources)} translation resources")

    def _create_resource(
        self, language: str, namespace: str, file_path: Path
    ) -> Optional[TranslationResource]:
        """Create resource metadata."""
        try:
            stat = file_path.stat()

            # Calculate checksum
            with open(file_path, "rb") as f:
                # MD5 is used here only for file checksum, not for security
                checksum = hashlib.md5(f.read(), usedforsecurity=False).hexdigest()

            # Determine resource type
            resource_type = self._get_resource_type(namespace)

            return TranslationResource(
                language=language,
                namespace=namespace,
                resource_type=resource_type,
                file_path=str(file_path),
                size_bytes=stat.st_size,
                last_modified=datetime.fromtimestamp(stat.st_mtime),
                checksum=checksum,
            )
        except OSError as e:
            logger.error(f"Error creating resource for {file_path}: {e}")
            return None

    def _get_resource_type(self, namespace: str) -> ResourceType:
        """Determine resource type from namespace."""
        type_mapping = {
            "common": ResourceType.COMMON,
            "medical": ResourceType.MEDICAL,
            "errors": ResourceType.ERRORS,
            "help": ResourceType.HELP,
            "documents": ResourceType.DOCUMENTS,
            "voice": ResourceType.VOICE,
        }

        for key, resource_type in type_mapping.items():
            if key in namespace.lower():
                return resource_type

        return ResourceType.COMMON

    async def load_translations(
        self, language: str, namespace: str, strategy: LoadStrategy = LoadStrategy.LAZY
    ) -> Optional[Dict[str, Any]]:
        """Load translations for a language and namespace."""
        resource_key = f"{language}:{namespace}"

        # Check if already loaded
        if resource_key in self.loaded_data:
            self._update_access_stats(resource_key)
            return self.loaded_data[resource_key]

        # Check cache
        cached_data = await self._get_from_cache(resource_key)
        if cached_data:
            self.loaded_data[resource_key] = cached_data
            self._update_access_stats(resource_key)
            return cached_data

        # Load based on strategy
        if strategy == LoadStrategy.EAGER:
            return await self._load_immediately(resource_key)
        elif strategy == LoadStrategy.PRELOAD:
            asyncio.create_task(self._load_in_background(resource_key))
            return None
        else:  # LAZY or ON_DEMAND
            return await self._load_with_lock(resource_key)

    async def _load_immediately(self, resource_key: str) -> Optional[Dict[str, Any]]:
        """Load resource immediately."""
        return await self._load_resource(resource_key)

    async def _load_in_background(self, resource_key: str) -> None:
        """Load resource in background."""
        try:
            await self._load_resource(resource_key)
        except OSError as e:
            logger.error(f"Background loading failed for {resource_key}: {e}")

    async def _load_with_lock(self, resource_key: str) -> Optional[Dict[str, Any]]:
        """Load resource with locking to prevent duplicate loads."""
        # Create lock if not exists
        if resource_key not in self.loading_locks:
            self.loading_locks[resource_key] = asyncio.Lock()

        async with self.loading_locks[resource_key]:
            # Check again if loaded while waiting for lock
            if resource_key in self.loaded_data:
                return self.loaded_data[resource_key]

            return await self._load_resource(resource_key)

    async def _load_resource(self, resource_key: str) -> Optional[Dict[str, Any]]:
        """Load translation resource from file."""
        resource = self.resources.get(resource_key)
        if not resource:
            logger.warning(f"Resource not found: {resource_key}")
            return None

        try:
            # Check memory limit
            if not self._check_memory_limit(resource.size_bytes):
                await self._evict_least_used()

            # Load file
            with open(resource.file_path, "r", encoding="utf-8") as f:
                data: Dict[str, Any] = json.load(f)

            # Store in memory
            self.loaded_data[resource_key] = data
            resource.is_loaded = True
            resource.load_count += 1
            resource.last_accessed = datetime.now()

            # Cache for future use
            await self._save_to_cache(resource_key, data)

            logger.info(f"Loaded translation resource: {resource_key}")
            return data

        except (IOError, json.JSONDecodeError) as e:
            logger.error(f"Error loading resource {resource_key}: {e}")
            return None

    def _check_memory_limit(self, additional_bytes: int) -> bool:
        """Check if loading would exceed memory limit."""
        current_size = sum(self.resources[key].size_bytes for key in self.loaded_data)

        max_bytes = self.load_config.max_memory_mb * 1024 * 1024
        return (current_size + additional_bytes) <= max_bytes

    async def _evict_least_used(self) -> None:
        """Evict least recently used resources."""
        if not self.loaded_data:
            return

        # Sort by last accessed time
        loaded_keys = [
            key for key in self.loaded_data if key not in self._get_protected_keys()
        ]

        if not loaded_keys:
            logger.warning("No resources available for eviction")
            return

        # Sort by access time
        loaded_keys.sort(key=lambda k: self.resources[k].last_accessed or datetime.min)

        # Evict oldest
        evict_key = loaded_keys[0]
        del self.loaded_data[evict_key]
        self.resources[evict_key].is_loaded = False

        logger.info(f"Evicted translation resource: {evict_key}")

    def _get_protected_keys(self) -> Set[str]:
        """Get resource keys that should not be evicted."""
        protected = set()

        for lang in self.load_config.preload_languages:
            for ns in self.load_config.preload_namespaces:
                protected.add(f"{lang}:{ns}")

        return protected

    async def _get_from_cache(self, resource_key: str) -> Optional[Dict[str, Any]]:
        """Get translations from cache."""
        return self.cache.get(resource_key)

    async def _save_to_cache(self, resource_key: str, data: Dict[str, Any]) -> None:
        """Save translations to cache."""
        self.cache[resource_key] = data

    def _update_access_stats(self, resource_key: str) -> None:
        """Update resource access statistics."""
        resource = self.resources.get(resource_key)
        if resource:
            resource.last_accessed = datetime.now()

    async def preload_essential(self) -> None:
        """Preload essential translation resources."""
        logger.info("Preloading essential translations")

        tasks = []
        for language in self.load_config.preload_languages:
            for namespace in self.load_config.preload_namespaces:
                task = self.load_translations(language, namespace, LoadStrategy.EAGER)
                tasks.append(task)

        # Load in parallel with limit
        semaphore = asyncio.Semaphore(self.load_config.parallel_loads)

        async def load_with_semaphore(task: Any) -> Any:
            async with semaphore:
                return await task

        results = await asyncio.gather(
            *[load_with_semaphore(task) for task in tasks], return_exceptions=True
        )

        # Log results
        successful = sum(1 for r in results if r and not isinstance(r, Exception))
        logger.info(f"Preloaded {successful}/{len(tasks)} essential resources")

    def get_loaded_languages(self) -> Set[str]:
        """Get currently loaded languages."""
        return {key.split(":")[0] for key in self.loaded_data}

    def get_loaded_namespaces(self, language: str) -> Set[str]:
        """Get loaded namespaces for a language."""
        return {
            key.split(":")[1]
            for key in self.loaded_data
            if key.startswith(f"{language}:")
        }

    def get_memory_usage(self) -> Dict[str, Any]:
        """Get current memory usage statistics."""
        loaded_size = sum(self.resources[key].size_bytes for key in self.loaded_data)

        total_size = sum(resource.size_bytes for resource in self.resources.values())

        return {
            "loaded_mb": loaded_size / (1024 * 1024),
            "total_mb": total_size / (1024 * 1024),
            "loaded_resources": len(self.loaded_data),
            "total_resources": len(self.resources),
            "usage_percentage": (
                (loaded_size / total_size * 100) if total_size > 0 else 0
            ),
        }

    async def unload_language(self, language: str) -> None:
        """Unload all resources for a language."""
        keys_to_unload = [
            key for key in self.loaded_data if key.startswith(f"{language}:")
        ]

        for key in keys_to_unload:
            del self.loaded_data[key]
            self.resources[key].is_loaded = False

        logger.info(
            f"Unloaded {len(keys_to_unload)} resources for language: {language}"
        )

    async def refresh_resource(self, language: str, namespace: str) -> None:
        """Refresh a specific resource from disk."""
        resource_key = f"{language}:{namespace}"

        # Remove from memory and cache
        if resource_key in self.loaded_data:
            del self.loaded_data[resource_key]

        # Clear cache
        if resource_key in self.cache:
            del self.cache[resource_key]

        # Reload
        await self.load_translations(language, namespace, LoadStrategy.EAGER)


# Global lazy loader instance
lazy_loader = LazyTranslationLoader()
