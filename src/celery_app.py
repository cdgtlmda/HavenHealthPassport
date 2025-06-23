"""Celery Configuration for Bulk Operations.

This module configures Celery for handling scheduled bulk operations.
"""

import os

from celery import Celery
from celery.schedules import crontab

# Get Redis URL from environment or use default
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

# Create Celery app
celery_app = Celery(
    "haven_health_passport",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=["src.api.endpoints.bulk_operations_scheduling"],
)

# Configure Celery
celery_app.conf.update(
    # Task serialization
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    # Timezone
    timezone="UTC",
    enable_utc=True,
    # Task execution
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    # Result backend
    result_expires=3600,  # Results expire after 1 hour
    # Worker configuration
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
    # Task routes
    task_routes={
        "src.api.endpoints.bulk_operations_scheduling.execute_bulk_import": {
            "queue": "bulk_operations"
        },
        "src.api.endpoints.bulk_operations_scheduling.execute_bulk_export": {
            "queue": "bulk_operations"
        },
        "src.api.endpoints.bulk_operations_scheduling.execute_bulk_update": {
            "queue": "bulk_operations"
        },
    },
    # Beat schedule for periodic tasks
    beat_schedule={
        # Clean up old completed operations every day at 2 AM
        "cleanup-old-operations": {
            "task": "src.tasks.cleanup_old_operations",
            "schedule": crontab(hour=2, minute=0),
        },
        # Check for stuck operations every hour
        "check-stuck-operations": {
            "task": "src.tasks.check_stuck_operations",
            "schedule": crontab(minute=0),
        },
    },
)

# Export the app
app = celery_app
