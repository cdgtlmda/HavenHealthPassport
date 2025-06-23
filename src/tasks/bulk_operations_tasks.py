"""Celery Tasks for Bulk Operations Maintenance.

This module contains periodic tasks for maintaining bulk operations.
"""

from datetime import datetime, timedelta
from typing import Dict

from celery import shared_task
from sqlalchemy import and_
from sqlalchemy.exc import DataError, IntegrityError, SQLAlchemyError

from src.database import SessionLocal
from src.models.bulk_operation import BulkOperation, BulkOperationStatus
from src.utils.logging_config import get_logger

logger = get_logger(__name__)


@shared_task  # type: ignore[misc]
def cleanup_old_operations() -> Dict[str, int]:
    """Clean up completed operations older than 30 days."""
    db = SessionLocal()
    try:
        cutoff_date = datetime.utcnow() - timedelta(days=30)

        # Delete old completed operations
        deleted_count = (
            db.query(BulkOperation)
            .filter(
                and_(
                    BulkOperation.status.in_(
                        [
                            BulkOperationStatus.COMPLETED,
                            BulkOperationStatus.FAILED,
                            BulkOperationStatus.CANCELLED,
                        ]
                    ),
                    BulkOperation.completed_at < cutoff_date,
                )
            )
            .delete()
        )

        db.commit()
        logger.info("Cleaned up %s old bulk operations", deleted_count)

        return {"deleted": deleted_count}

    except (DataError, IntegrityError, SQLAlchemyError) as e:
        logger.error("Error cleaning up old operations: %s", str(e))
        db.rollback()
        raise
    finally:
        db.close()


@shared_task  # type: ignore[misc]
def check_stuck_operations() -> Dict[str, int]:
    """Check for operations that are stuck in processing state."""
    db = SessionLocal()
    try:
        # Find operations that have been processing for more than 2 hours
        stuck_threshold = datetime.utcnow() - timedelta(hours=2)

        stuck_operations = (
            db.query(BulkOperation)
            .filter(
                and_(
                    BulkOperation.status == BulkOperationStatus.PROCESSING,
                    BulkOperation.started_at < stuck_threshold,
                )
            )
            .all()
        )

        stuck_count = 0
        for operation in stuck_operations:
            # Mark as failed
            operation.status = BulkOperationStatus.FAILED
            operation.error_message = "Operation timed out after 2 hours"  # type: ignore[assignment]
            operation.completed_at = datetime.utcnow()  # type: ignore[assignment]
            stuck_count += 1

            logger.warning("Marked operation %s as failed due to timeout", operation.id)

        if stuck_count > 0:
            db.commit()

        logger.info("Checked for stuck operations, found %s", stuck_count)

        return {"stuck_operations": stuck_count}

    except (DataError, IntegrityError, SQLAlchemyError, TypeError, ValueError) as e:
        logger.error("Error checking stuck operations: %s", str(e))
        db.rollback()
        raise
    finally:
        db.close()
