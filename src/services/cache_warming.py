"""Cache warming service for preloading frequently accessed data.

This module implements cache warming strategies to reduce cold cache penalties
and improve initial response times after system startup or cache flushes.
"""

import asyncio
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from pydantic import BaseModel, Field

from src.config import get_settings
from src.services.cache_service import cache_service
from src.services.cache_ttl_config import CacheCategory
from src.utils.logging import get_logger

logger = get_logger(__name__)


class WarmingPriority(int, Enum):
    """Priority levels for cache warming."""

    CRITICAL = 1  # Must be warmed immediately
    HIGH = 2  # Warm as soon as possible
    MEDIUM = 3  # Warm after high priority
    LOW = 4  # Warm when resources available
    BACKGROUND = 5  # Warm in background continuously


class WarmingStrategy(str, Enum):
    """Strategies for cache warming."""

    EAGER = "eager"  # Warm all at once
    LAZY = "lazy"  # Warm on first access
    PROGRESSIVE = "progressive"  # Warm gradually
    SCHEDULED = "scheduled"  # Warm at specific times
    PREDICTIVE = "predictive"  # Warm based on usage patterns


class CacheWarmingTask(BaseModel):
    """Definition of a cache warming task."""

    name: str = Field(..., description="Task name")
    description: str = Field(..., description="Task description")
    priority: WarmingPriority = Field(default=WarmingPriority.MEDIUM)
    strategy: WarmingStrategy = Field(default=WarmingStrategy.EAGER)
    category: Optional[CacheCategory] = Field(None, description="Cache category")
    enabled: bool = Field(default=True)

    # Scheduling options
    schedule_cron: Optional[str] = Field(
        None, description="Cron expression for scheduled warming"
    )
    warm_on_startup: bool = Field(default=True, description="Warm on system startup")

    # Task configuration
    batch_size: int = Field(default=100, description="Items to warm per batch")
    concurrency: int = Field(default=5, description="Concurrent warming operations")
    retry_on_failure: bool = Field(default=True, description="Retry failed warming")
    max_retries: int = Field(default=3, description="Maximum retry attempts")


class CacheWarmingService:
    """Service for managing cache warming operations."""

    def __init__(self) -> None:
        """Initialize the warming service."""
        self.tasks: Dict[str, CacheWarmingTask] = {}
        self.warming_functions: Dict[str, Callable] = {}
        self.warming_stats: Dict[str, Dict[str, Any]] = {}
        self.is_warming = False
        self._initialize_default_tasks()

    def _initialize_default_tasks(self) -> None:
        """Initialize default warming tasks."""
        # System configuration warming
        self.register_task(
            CacheWarmingTask(
                name="system_config",
                description="Warm system configuration and feature flags",
                priority=WarmingPriority.CRITICAL,
                strategy=WarmingStrategy.EAGER,
                category=CacheCategory.SYSTEM_CONFIG,
                batch_size=50,
                schedule_cron=None,
            ),
            self._warm_system_config,
        )

        # Active user sessions
        self.register_task(
            CacheWarmingTask(
                name="active_sessions",
                description="Warm active user sessions",
                priority=WarmingPriority.HIGH,
                strategy=WarmingStrategy.PROGRESSIVE,
                category=CacheCategory.USER_SESSION,
                batch_size=200,
                concurrency=10,
                schedule_cron=None,
            ),
            self._warm_active_sessions,
        )

        # Frequently accessed patients
        self.register_task(
            CacheWarmingTask(
                name="frequent_patients",
                description="Warm frequently accessed patient records",
                priority=WarmingPriority.HIGH,
                strategy=WarmingStrategy.PROGRESSIVE,
                category=CacheCategory.PATIENT_BASIC,
                batch_size=100,
                schedule_cron=None,
            ),
            self._warm_frequent_patients,
        )

        # Medical glossary
        self.register_task(
            CacheWarmingTask(
                name="medical_glossary",
                description="Warm medical translation glossary",
                priority=WarmingPriority.MEDIUM,
                strategy=WarmingStrategy.EAGER,
                category=CacheCategory.TRANSLATION_GLOSSARY,
                warm_on_startup=True,
                schedule_cron=None,
            ),
            self._warm_medical_glossary,
        )

        # Recent health records
        self.register_task(
            CacheWarmingTask(
                name="recent_health_records",
                description="Warm recently accessed health records",
                priority=WarmingPriority.LOW,
                strategy=WarmingStrategy.SCHEDULED,
                category=CacheCategory.HEALTH_RECORD,
                schedule_cron="0 */4 * * *",  # Every 4 hours
                warm_on_startup=False,
            ),
            self._warm_recent_health_records,
        )

    def register_task(self, task: CacheWarmingTask, warming_func: Callable) -> None:
        """Register a cache warming task.

        Args:
            task: The warming task configuration
            warming_func: Async function that performs the warming
        """
        self.tasks[task.name] = task
        self.warming_functions[task.name] = warming_func
        logger.info(f"Registered warming task: {task.name}")

    async def warm_cache(self, task_names: Optional[List[str]] = None) -> None:
        """Warm the cache for specified tasks or all tasks.

        Args:
            task_names: Optional list of task names to warm
        """
        if self.is_warming:
            logger.warning("Cache warming already in progress")
            return

        self.is_warming = True
        start_time = datetime.utcnow()

        try:
            # Determine which tasks to run
            if task_names:
                tasks_to_run = [
                    (name, self.tasks[name])
                    for name in task_names
                    if name in self.tasks and self.tasks[name].enabled
                ]
            else:
                tasks_to_run = [
                    (name, task)
                    for name, task in self.tasks.items()
                    if task.enabled and task.warm_on_startup
                ]

            # Sort by priority
            tasks_to_run.sort(key=lambda x: x[1].priority.value)

            logger.info(f"Starting cache warming for {len(tasks_to_run)} tasks")

            # Run tasks according to strategy
            for task_name, task in tasks_to_run:
                await self._run_warming_task(task_name, task)

            duration = (datetime.utcnow() - start_time).total_seconds()
            logger.info(f"Cache warming completed in {duration:.2f} seconds")

        except (ValueError, AttributeError, KeyError, RuntimeError) as e:
            logger.error(f"Cache warming failed: {e}")
        finally:
            self.is_warming = False

    async def _run_warming_task(self, task_name: str, task: CacheWarmingTask) -> None:
        """Run a single warming task."""
        logger.info(f"Running warming task: {task_name}")

        start_time = datetime.utcnow()
        items_warmed = 0
        errors = 0

        try:
            warming_func = self.warming_functions.get(task_name)
            if not warming_func:
                logger.error(f"No warming function found for task: {task_name}")
                return

            # Execute warming function
            if task.strategy == WarmingStrategy.EAGER:
                items_warmed = await warming_func(task)

            elif task.strategy == WarmingStrategy.PROGRESSIVE:
                items_warmed = await self._warm_progressive(warming_func, task)

            elif task.strategy == WarmingStrategy.PREDICTIVE:
                items_warmed = await self._warm_predictive(warming_func, task)

            else:
                # Default to eager
                items_warmed = await warming_func(task)

        except (ValueError, AttributeError, KeyError, RuntimeError) as e:
            logger.error(f"Error in warming task {task_name}: {e}")
            errors += 1

            if task.retry_on_failure and task.max_retries > 0:
                for retry in range(task.max_retries):
                    try:
                        logger.info(
                            f"Retrying warming task {task_name} (attempt {retry + 1})"
                        )
                        items_warmed = await warming_func(task) if warming_func else 0
                        errors = 0
                        break
                    except (
                        ValueError,
                        AttributeError,
                        KeyError,
                        RuntimeError,
                    ) as retry_e:
                        logger.error(f"Retry {retry + 1} failed: {retry_e}")
                        errors += 1

        # Update statistics
        duration = (datetime.utcnow() - start_time).total_seconds()
        self.warming_stats[task_name] = {
            "last_run": datetime.utcnow(),
            "duration_seconds": duration,
            "items_warmed": items_warmed,
            "errors": errors,
            "success": errors == 0,
        }

        logger.info(
            f"Warming task {task_name} completed: "
            f"{items_warmed} items in {duration:.2f}s"
        )

    async def _warm_progressive(
        self, warming_func: Callable, task: CacheWarmingTask
    ) -> int:
        """Warm cache progressively in batches."""
        total_warmed = 0

        # This is a simplified implementation
        # In practice, warming_func would need to support pagination
        batch_result = await warming_func(task)
        total_warmed += batch_result

        # Add delay between batches to avoid overload
        if task.batch_size > 0:
            await asyncio.sleep(0.1)  # 100ms between batches

        return int(total_warmed) if isinstance(total_warmed, (int, float)) else 0

    async def _warm_predictive(
        self, warming_func: Callable, task: CacheWarmingTask
    ) -> int:
        """Warm cache based on predicted usage patterns."""
        # This would analyze usage patterns and warm accordingly
        # For now, just use the standard warming function
        result = await warming_func(task)
        return int(result) if isinstance(result, (int, float)) else 0

    # Default warming functions
    async def _warm_system_config(self, task: CacheWarmingTask) -> int:
        """Warm system configuration."""
        _ = task  # Reserved for future use
        items_warmed = 0

        try:
            # Example: Load and cache system settings
            settings = get_settings()

            # Cache various config values
            configs = {
                "system:config:app_name": settings.app_name,
                "system:config:environment": settings.environment,
                "system:config:version": settings.app_version,
            }

            for key, value in configs.items():
                await cache_service.set(
                    key, value, category=CacheCategory.SYSTEM_CONFIG
                )
                items_warmed += 1

        except (ImportError, AttributeError, KeyError, RuntimeError) as e:
            logger.error(f"Error warming system config: {e}")

        return items_warmed

    async def _warm_active_sessions(self, task: CacheWarmingTask) -> int:
        """Warm active user sessions."""
        _ = task  # Reserved for future use
        # This would query the database for active sessions
        # For now, return a placeholder
        logger.info("Warming active sessions (placeholder)")
        return 0

    async def _warm_frequent_patients(self, task: CacheWarmingTask) -> int:
        """Warm frequently accessed patient records."""
        _ = task  # Reserved for future use
        # This would analyze access patterns and warm top patients
        logger.info("Warming frequent patients (placeholder)")
        return 0

    async def _warm_medical_glossary(self, task: CacheWarmingTask) -> int:
        """Warm medical translation glossary."""
        _ = task  # Reserved for future use
        # This would load glossary terms into cache
        logger.info("Warming medical glossary (placeholder)")
        return 0

    async def _warm_recent_health_records(self, task: CacheWarmingTask) -> int:
        """Warm recently accessed health records."""
        _ = task  # Reserved for future use
        # This would query recent records and cache them
        logger.info("Warming recent health records (placeholder)")
        return 0

    def get_warming_stats(self) -> Dict[str, Any]:
        """Get cache warming statistics."""
        return {
            "is_warming": self.is_warming,
            "total_tasks": len(self.tasks),
            "enabled_tasks": sum(1 for t in self.tasks.values() if t.enabled),
            "task_stats": self.warming_stats,
        }


# Global warming service instance
warming_service = CacheWarmingService()


# Helper function to warm cache on startup
async def warm_cache_on_startup() -> None:
    """Warm cache on application startup."""
    logger.info("Starting cache warming on startup")
    await warming_service.warm_cache()


# Export components
__all__ = [
    "WarmingPriority",
    "WarmingStrategy",
    "CacheWarmingTask",
    "CacheWarmingService",
    "warming_service",
    "warm_cache_on_startup",
]
